;;; ic617_live_bridge.il — Zero-Python3 Live Virtuoso IC617 CIW Socket Bridge
;;; Managed by SKILL-ANALOG (release 2026.11.18.6).
;;;
;;; PURPOSE:
;;; Allows Codex on RHEL 6.5 (`Python 2.6.6`) to inspect, size, check-and-save,
;;; and export PNGs from the user's ALREADY-OPEN Virtuoso GUI session without
;;; `.cdslck` file lock collisions, extra Virtuoso license seats, or Python 3.
;;;
;;; USAGE IN VIRTUOSO CIW (opt-in per session; never modifies `.cdsinit`):
;;;   (load "/home/disk/eda/references/SKILL-ANALOG/tools/ic617_live_bridge.il")
;;;
;;; CONTROL PROCEDURES:
;;;   saBridgeStart()   — Start (or confirm running) Python 2.6.6 socket helper
;;;   saBridgeStop()    — Stop socket helper and remove `~/.cache/skill-analog/*.sock`
;;;   saBridgeStatus()  — Print current bridge IPC state in CIW

unless(boundp('saBridgeIpc) saBridgeIpc = nil)
unless(boundp('saBridgeRecvBuf) saBridgeRecvBuf = "")
unless(boundp('saBridgeHelperPid) saBridgeHelperPid = nil)
unless(boundp('saBridgeSockPath) saBridgeSockPath = "")
unless(boundp('saBridgeReqCount) saBridgeReqCount = 0)
unless(boundp('saBridgeErrCount) saBridgeErrCount = 0)

;;; Resolve tools directory dynamically from `(load ...)` port or environment
let((loadFile candidateTools rootEnv oaHelper)
  loadFile = if(boundp('piport) && piport get_filename(piport) nil)
  candidateTools = nil
  when(loadFile && stringp(loadFile) && strlen(loadFile) > 0
    let((lastSep i n ch)
      lastSep = 0
      n = strlen(loadFile)
      for(i 1 n
        ch = substring(loadFile i 1)
        when(ch == "/" || ch == "\\"
          lastSep = i
        )
      )
      when(lastSep > 1
        candidateTools = substring(loadFile 1 lastSep - 1)
      )
    )
  )
  unless(candidateTools
    rootEnv = getShellEnvVar("SKILL_ANALOG_ROOT")
    unless(rootEnv && strlen(rootEnv) > 0
      rootEnv = "/home/disk/eda/references/SKILL-ANALOG"
    )
    candidateTools = strcat(rootEnv "/tools")
  )
  saBridgeToolsDir = candidateTools
  oaHelper = strcat(saBridgeToolsDir "/ic617_oa_cdf.il")
  unless(isCallable('saDumpSchematicJson) && isCallable('saJsonEscapeString)
    when(isFile(oaHelper)
      load(oaHelper)
    )
  )
)

procedure(saBridgeShellQuote(arg)
  let((out i n ch sq)
    sq = "'"
    out = sq
    n = strlen(arg)
    for(i 1 n
      ch = substring(arg i 1)
      if(ch == sq then
        out = strcat(out "'\\''")
      else
        out = strcat(out ch)
      )
    )
    strcat(out sq)
  )
)

procedure(saHexNibble(ch)
  cond(
    (ch == "0" 0)
    (ch == "1" 1)
    (ch == "2" 2)
    (ch == "3" 3)
    (ch == "4" 4)
    (ch == "5" 5)
    (ch == "6" 6)
    (ch == "7" 7)
    (ch == "8" 8)
    (ch == "9" 9)
    (ch == "a" || ch == "A" 10)
    (ch == "b" || ch == "B" 11)
    (ch == "c" || ch == "C" 12)
    (ch == "d" || ch == "D" 13)
    (ch == "e" || ch == "E" 14)
    (ch == "f" || ch == "F" 15)
    (t -1)
  )
)

procedure(saHexDecode(hexStr)
  let((out n i hi lo byteVal)
    out = ""
    n = strlen(hexStr)
    i = 1
    while(i + 1 <= n
      hi = saHexNibble(substring(hexStr i 1))
      lo = saHexNibble(substring(hexStr i + 1 1))
      when(hi >= 0 && lo >= 0
        byteVal = 16 * hi + lo
        when(byteVal > 0
          out = strcat(out buildString(list(intToChar(byteVal))))
        )
      )
      i = i + 2
    )
    out
  )
)

procedure(saBridgeIsWs(ch)
  let((tabCh lfCh crCh)
    tabCh = buildString(list(intToChar(9)))
    lfCh = buildString(list(intToChar(10)))
    crCh = buildString(list(intToChar(13)))
    ch == " " || ch == tabCh || ch == lfCh || ch == crCh
  )
)

;;; Top-level JSON object inspector: returns `t` iff `val` is a JSON object string
;;; whose top-level `"ok"` key has boolean value `false` (ignoring nested objects/strings).
procedure(saBridgeJsonResultHasOkFalse(val)
  let((n i firstIdx lastIdx ch dq bs depth inStr tok expectKey afterOkColon foundFalse)
    foundFalse = nil
    when(stringp(val)
      n = strlen(val)
      firstIdx = 1
      while(firstIdx <= n && saBridgeIsWs(substring(val firstIdx 1))
        firstIdx = firstIdx + 1
      )
      lastIdx = n
      while(lastIdx >= firstIdx && saBridgeIsWs(substring(val lastIdx 1))
        lastIdx = lastIdx - 1
      )
      when(firstIdx < lastIdx &&
           substring(val firstIdx 1) == "{" &&
           substring(val lastIdx 1) == "}"
        dq = buildString(list(intToChar(34)))
        bs = buildString(list(intToChar(92)))
        depth = 0
        inStr = nil
        tok = ""
        expectKey = nil
        afterOkColon = nil
        i = firstIdx
        while(i <= lastIdx && !foundFalse
          ch = substring(val i 1)
          if(inStr then
            cond(
              (ch == bs
                when(i + 1 <= lastIdx
                  tok = strcat(tok substring(val i + 1 1))
                  i = i + 1
                )
              )
              (ch == dq
                inStr = nil
                when(depth == 1 && expectKey
                  expectKey = nil
                  if(tok == "ok" then
                    afterOkColon = 'needColon
                  else
                    afterOkColon = nil
                  )
                )
              )
              (t
                tok = strcat(tok ch)
              )
            )
          else
            cond(
              (saBridgeIsWs(ch)
                nil
              )
              (ch == "{"
                depth = depth + 1
                when(depth == 1
                  expectKey = t
                  afterOkColon = nil
                )
                when(depth > 1 && afterOkColon == 'needVal
                  afterOkColon = nil
                )
              )
              (ch == "}"
                depth = depth - 1
                afterOkColon = nil
                expectKey = nil
              )
              (ch == "["
                depth = depth + 1
                when(afterOkColon == 'needVal
                  afterOkColon = nil
                )
              )
              (ch == "]"
                depth = depth - 1
              )
              (ch == ","
                when(depth == 1
                  expectKey = t
                  afterOkColon = nil
                )
              )
              (ch == ":"
                when(depth == 1 && afterOkColon == 'needColon
                  afterOkColon = 'needVal
                )
              )
              (ch == dq
                inStr = t
                tok = ""
                when(depth == 1 && afterOkColon == 'needVal
                  afterOkColon = nil
                )
              )
              (t
                when(depth == 1 && afterOkColon == 'needVal
                  when(i + 4 <= lastIdx && substring(val i 5) == "false"
                    let((nextCh)
                      nextCh = if(i + 5 <= lastIdx substring(val i + 5 1) "}")
                      when(nextCh == "," || nextCh == "}" || saBridgeIsWs(nextCh)
                        foundFalse = t
                      )
                    )
                  )
                  afterOkColon = nil
                )
              )
            )
          )
          i = i + 1
        )
      )
    )
    foundFalse
  )
)

procedure(saBridgeEvalRequest(reqId hexCmd)
  let((safeId cmdStr wport evalOk opOk finalOk resVal stdoutTxt errTxt respJson)
    safeId = if(stringp(reqId) && strlen(reqId) > 0 reqId sprintf(nil "%L" reqId))
    saBridgeReqCount = saBridgeReqCount + 1
    cmdStr = saHexDecode(hexCmd)
    stdoutTxt = ""
    resVal = nil
    errTxt = nil

    wport = if(isCallable('outstring) outstring() nil)
    if(wport then
      unwindProtect(
        progn(
          let(((poport wport))
            evalOk = errset(resVal = evalstring(strcat("(progn " cmdStr ")")) t)
          )
          stdoutTxt = getOutString(wport)
        )
        close(wport)
      )
    else
      evalOk = errset(resVal = evalstring(strcat("(progn " cmdStr ")")) t)
    )

    opOk = (evalOk != nil)
    unless(evalOk
      saBridgeErrCount = saBridgeErrCount + 1
      errTxt = sprintf(nil "%L" errset.errset)
    )

    when(evalOk && saBridgeJsonResultHasOkFalse(resVal)
      opOk = nil
      saBridgeErrCount = saBridgeErrCount + 1
      unless(errTxt
        errTxt = "SKILL result JSON reported ok=false"
      )
    )
    finalOk = (evalOk != nil && opOk != nil)

    respJson = sprintf(
      nil
      "{\"id\": %s, \"transport_ok\": true, \"op_ok\": %s, \"ok\": %s, \"result\": %s, \"stdout\": %s, \"error\": %s}\n"
      saJsonScalar(safeId)
      saJsonBool(opOk)
      saJsonBool(finalOk)
      saJsonScalar(if(evalOk resVal nil))
      saJsonScalar(stdoutTxt)
      saJsonScalar(errTxt)
    )
    respJson
  )
)

procedure(saBridgeHandleLine(ipcId line)
  let((sep parts reqId hexCmd resp)
    sep = strcat(" " buildString(list(intToChar(9))) buildString(list(intToChar(13))))
    parts = parseString(line sep)
    when(parts && car(parts) == "REQ"
      if(length(parts) >= 3 then
        reqId = cadr(parts)
        hexCmd = caddr(parts)
        resp = saBridgeEvalRequest(reqId hexCmd)
        ipcWriteProcess(ipcId resp)
      else
        reqId = if(length(parts) >= 2 cadr(parts) "unknown")
        saBridgeErrCount = saBridgeErrCount + 1
        resp = sprintf(
          nil
          "{\"id\": %s, \"transport_ok\": true, \"op_ok\": false, \"ok\": false, \"result\": null, \"stdout\": \"\", \"error\": \"Malformed REQ frame\"}\n"
          saJsonScalar(reqId)
        )
        ipcWriteProcess(ipcId resp)
      )
    )
  )
)

procedure(saBridgeIpcDataHandler(ipcId data)
  let((nl tail nlPos line)
    nl = buildString(list(intToChar(10)))
    saBridgeRecvBuf = strcat(saBridgeRecvBuf data)
    while(tail = index(saBridgeRecvBuf nl)
      nlPos = strlen(saBridgeRecvBuf) - strlen(tail) + 1
      line = if(nlPos > 1 substring(saBridgeRecvBuf 1 nlPos - 1) "")
      saBridgeRecvBuf = if(strlen(tail) > 1 substring(tail 2) "")
      when(strlen(line) > 0
        saBridgeHandleLine(ipcId line)
      )
    )
  )
)

procedure(saBridgeIpcErrHandler(ipcId data)
  let((sep tokens)
    sep = strcat(" " buildString(list(intToChar(9))) buildString(list(intToChar(10))) buildString(list(intToChar(13))))
    tokens = parseString(data sep)
    when(member("[SA-BRIDGE-READY]" tokens)
      foreach(tok tokens
        when(strlen(tok) > 4 && substring(tok 1 4) == "pid="
          saBridgeHelperPid = atoi(substring(tok 5))
        )
        when(strlen(tok) > 5 && substring(tok 1 5) == "sock="
          saBridgeSockPath = substring(tok 6)
        )
      )
      printf(
        "[SKILL-ANALOG Bridge] Ready (ipc=%L helper_pid=%L sock=%s)\n"
        ipcId saBridgeHelperPid saBridgeSockPath
      )
    )
  )
)

procedure(saBridgeIpcFinishHandler(ipcId data)
  let((status)
    status = ipcGetExitStatus(ipcId)
    printf("[SKILL-ANALOG Bridge] Helper exited (ipc=%L status=%L)\n" ipcId status)
    saBridgeIpc = nil
    saBridgeRecvBuf = ""
    saBridgeHelperPid = nil
  )
)

procedure(saBridgeStart()
  let((pyBin clientScript sockDirEnv cmd)
    if(saBridgeIpc && ipcIsAliveProcess(saBridgeIpc) then
      printf(
        "[SKILL-ANALOG Bridge] Already running (ipc=%L helper_pid=%L sock=%s)\n"
        saBridgeIpc saBridgeHelperPid saBridgeSockPath
      )
      t
    else
      pyBin = getShellEnvVar("SA_BRIDGE_PYTHON")
      unless(pyBin && strlen(pyBin) > 0
        pyBin = "/usr/bin/python"
        unless(isFile(pyBin) pyBin = "python")
      )
      clientScript = strcat(saBridgeToolsDir "/ic617_client.py")
      unless(isFile(clientScript)
        error("SKILL-ANALOG bridge helper missing at: %s\n" clientScript)
      )
      sockDirEnv = getShellEnvVar("SA_BRIDGE_DIR")
      saBridgeRecvBuf = ""
      saBridgeHelperPid = nil
      saBridgeSockPath = ""
      cmd = sprintf(
        nil
        "/usr/bin/env -u LD_LIBRARY_PATH -u LD_PRELOAD SA_VIRTUOSO_PID=%d SA_VIRTUOSO_CWD=%s %s %s -B -u %s --start-helper"
        ipcGetPid()
        saBridgeShellQuote(getWorkingDir())
        if(sockDirEnv && strlen(sockDirEnv) > 0 strcat("SA_BRIDGE_DIR=" saBridgeShellQuote(sockDirEnv)) "")
        saBridgeShellQuote(pyBin)
        saBridgeShellQuote(clientScript)
      )
      saBridgeIpc = ipcBeginProcess(
        cmd
        ""
        'saBridgeIpcDataHandler
        'saBridgeIpcErrHandler
        'saBridgeIpcFinishHandler
        ""
      )
      printf("[SKILL-ANALOG Bridge] Launching Python 2.6+ helper (ipc=%L)...\n" saBridgeIpc)
      t
    )
  )
)

procedure(saBridgeStop()
  if(saBridgeIpc && ipcIsAliveProcess(saBridgeIpc) then
    printf("[SKILL-ANALOG Bridge] Stopping helper (ipc=%L helper_pid=%L)...\n" saBridgeIpc saBridgeHelperPid)
    ipcKillProcess(saBridgeIpc)
    saBridgeIpc = nil
    saBridgeRecvBuf = ""
    t
  else
    printf("[SKILL-ANALOG Bridge] Bridge is not running.\n")
    nil
  )
)

procedure(saBridgeStatus()
  let((alive)
    alive = saBridgeIpc && ipcIsAliveProcess(saBridgeIpc)
    printf(
      "[SKILL-ANALOG Bridge] alive=%L helper_pid=%L sock=%s requests=%d errors=%d\n"
      alive saBridgeHelperPid saBridgeSockPath saBridgeReqCount saBridgeErrCount
    )
    list(
      list("alive" alive)
      list("helper_pid" saBridgeHelperPid)
      list("sock" saBridgeSockPath)
      list("requests" saBridgeReqCount)
      list("errors" saBridgeErrCount)
    )
  )
)

unless(getShellEnvVar("SA_BRIDGE_NO_AUTOSTART") == "1"
  saBridgeStart()
)
