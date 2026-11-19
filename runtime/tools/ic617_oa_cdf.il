;;; ic617_oa_cdf.il — Reusable Cadence Virtuoso IC617 OA / CDF / Schematic / OCEAN Helpers
;;; Managed by SKILL-ANALOG (release 2026.11.19.1).
;;;
;;; SAFETY CONTRACT:
;;; - Loading this file ONLY defines `sa*` helper procedures; it never mutates
;;;   any cellView, `.cdsinit`, PDK library, or simulator session on load.
;;; - Never destructively deletes user cellViews: `saPlaceAndWireFromPlan` backs
;;;   up any pre-existing target cellView to `<cell>_bak_<ts>` before writing
;;;   and aborts immediately with `error(...)` if verified backup creation fails.
;;; - Never saves schematics with check errors: `saCheckAndSave` and
;;;   `saPlaceAndWireFromPlan` gate `dbSave(cv)` and symbol generation strictly
;;;   on `errs == 0` (and verify `saved != nil`).
;;; - Parameter names (`w`, `fw`, `l`, `fingers`, `nf`, `m`, `simM`, `segW`, `segL`)
;;;   depend on the active PDK's CDF (`gpdk090`, `gpdk045`, etc.); `saApplyInstCdfCallbacks`
;;;   validates parameter names against `cdfData~>parameters` before mutating.

;;; ---------------------------------------------------------------------------
;;; 0. Core Geometry, String & Pure-SKILL JSON Formatting Utilities
;;; ---------------------------------------------------------------------------

unless(isCallable('centerBBox)
  procedure(centerBBox(bBox)
    if(isCallable('centerBox) && bBox then
      centerBox(bBox)
    else
      if(bBox then
        list(
          0.5 * (xCoord(lowerLeft(bBox)) + xCoord(upperRight(bBox)))
          0.5 * (yCoord(lowerLeft(bBox)) + yCoord(upperRight(bBox)))
        )
      else
        list(0.0 0.0)
      )
    )
  )
)

procedure(saValToSkillString(val)
  if(stringp(val) then
    val
  else
    sprintf(nil "%L" val)
  )
)

procedure(saSnapToGrid(coord @optional (grid 0.0625))
  let((fval gval)
    fval = float(coord)
    gval = if(grid && float(grid) > 0.0 float(grid) 0.0625)
    round(fval / gval) * gval
  )
)

procedure(saSnapPoint(pt @optional (grid 0.0625))
  list(saSnapToGrid(xCoord(pt) grid) saSnapToGrid(yCoord(pt) grid))
)

procedure(saTimestampCompact()
  let((raw out ch i n)
    raw = getCurrentTime()
    out = ""
    n = strlen(raw)
    for(i 1 n
      ch = substring(raw i 1)
      if(ch == " " || ch == ":" || ch == "/" || ch == "-" then
        out = strcat(out "_")
      else
        out = strcat(out ch)
      )
    )
    out
  )
)

procedure(saJsonEscapeString(val)
  let((str out i n ch bs dq lf cr tab)
    str = if(stringp(val) val sprintf(nil "%L" val))
    bs = buildString(list(intToChar(92)))
    dq = buildString(list(intToChar(34)))
    lf = buildString(list(intToChar(10)))
    cr = buildString(list(intToChar(13)))
    tab = buildString(list(intToChar(9)))
    out = ""
    n = strlen(str)
    for(i 1 n
      ch = substring(str i 1)
      cond(
        (ch == dq
          out = strcat(out bs dq)
        )
        (ch == bs
          out = strcat(out bs bs)
        )
        (ch == lf
          out = strcat(out bs "n")
        )
        (ch == cr
          out = strcat(out bs "r")
        )
        (ch == tab
          out = strcat(out bs "t")
        )
        (t
          out = strcat(out ch)
        )
      )
    )
    strcat(dq out dq)
  )
)

procedure(saJsonScalar(val)
  cond(
    (val == nil "null")
    (val == t "true")
    (stringp(val) saJsonEscapeString(val))
    (fixp(val) sprintf(nil "%d" val))
    (floatp(val) sprintf(nil "%.9g" val))
    (symbolp(val) saJsonEscapeString(symbolToString(val)))
    (t saJsonEscapeString(sprintf(nil "%L" val)))
  )
)

procedure(saJsonBool(flag)
  if(flag "true" "false")
)

procedure(saJsonPoint(pt)
  if(pt && listp(pt) && length(pt) >= 2 then
    sprintf(nil "[%.6g, %.6g]" float(xCoord(pt)) float(yCoord(pt)))
  else
    "null"
  )
)

procedure(saJsonBBox(bBox)
  if(bBox && listp(bBox) && length(bBox) == 2 then
    sprintf(nil "[%s, %s]" saJsonPoint(lowerLeft(bBox)) saJsonPoint(upperRight(bBox)))
  else
    "null"
  )
)

procedure(saJoinStrings(items sep)
  let((acc first)
    acc = ""
    first = t
    foreach(item items
      if(first then
        acc = item
        first = nil
      else
        acc = strcat(acc sep item)
      )
    )
    acc
  )
)

procedure(saJsonStringArray(items)
  strcat("[" saJoinStrings(mapcar('saJsonEscapeString items) ", ") "]")
)

;;; ---------------------------------------------------------------------------
;;; 1. Effective Instance CDF Callback Execution (MOS & Segmented Passives)
;;; ---------------------------------------------------------------------------
;;; Fixes `%L` string double-quoting: converts strings directly via
;;; `if(stringp(val) val sprintf(nil "%L" val))`, validates parameter names
;;; against `cdfData~>parameters`, initializes `PasCdfFormInit(cdfData)`,
;;; evaluates callbacks in dependency order, and runs `cdfUpdateInstParam(inst)`.

procedure(saValidateCdfParamNames(inst cdfData propPairs)
  let((validNames pname)
    when(cdfData && cdfData~>parameters
      validNames = mapcar(lambda((p) p~>name) cdfData~>parameters)
      foreach(pair propPairs
        pname = car(pair)
        unless(member(pname validNames) || cdfFindParamByName(cdfData pname)
          error(
            "Unknown CDF parameter %L on instance %s (%s/%s); valid parameters: %L\n"
            pname inst~>name inst~>libName inst~>cellName validNames
          )
        )
      )
    )
    t
  )
)

procedure(saCdfParamDbPropType(paramType)
  let((pt)
    pt = if(stringp(paramType) paramType "string")
    cond(
      (pt == "int" "int")
      (pt == "float" "float")
      (pt == "boolean" "boolean")
      (t "string")
    )
  )
)

procedure(saCoerceCdfParamValue(paramType val)
  let((pt lv parsed)
    pt = if(stringp(paramType) paramType "string")
    cond(
      (pt == "int"
        cond(
          (fixp(val) val)
          (floatp(val) round(val))
          (stringp(val) atoi(val))
          (t atoi(sprintf(nil "%L" val)))
        )
      )
      (pt == "float"
        cond(
          (floatp(val) val)
          (fixp(val) float(val))
          (stringp(val)
            parsed = if(isCallable('cdfParseFloatString) errset(cdfParseFloatString(val) nil) nil)
            parsed = if(parsed car(parsed) nil)
            if(numberp(parsed) float(parsed) atof(val))
          )
          (t atof(sprintf(nil "%L" val)))
        )
      )
      (pt == "boolean"
        cond(
          (val == nil nil)
          (val == t t)
          (fixp(val) val != 0)
          (floatp(val) val != 0.0)
          (stringp(val)
            lv = lowerCase(val)
            !(lv == "" || lv == "nil" || lv == "false" || lv == "0" || lv == "no" || lv == "off")
          )
          (t t)
        )
      )
      ((pt == "cyclic" || pt == "radio" || pt == "string")
        cond(
          (stringp(val) val)
          (symbolp(val) symbolToString(val))
          (t sprintf(nil "%L" val))
        )
      )
      (t
        if(stringp(val) val sprintf(nil "%L" val))
      )
    )
  )
)

procedure(saReplaceInstPropTyped(inst propName paramType rawVal)
  let((dbType typedVal existing)
    dbType = saCdfParamDbPropType(paramType)
    typedVal = saCoerceCdfParamValue(paramType rawVal)
    existing = dbGetPropByName(inst propName)
    when(existing && existing~>valueType && existing~>valueType != dbType
      errset(dbDeletePropByName(inst propName) nil)
    )
    dbReplaceProp(inst propName dbType typedVal)
    typedVal
  )
)

procedure(saApplyInstCdfCallbacks(inst propPairs @optional callbackOrder derivedProps)
  let((cdfData cdfgData cdfgForm param pname ptype val syncNames)
    unless(derivedProps
      derivedProps = list(
        "l" "w" "fw" "fingers" "nf" "m" "simM" "simW" "ad" "as" "pd" "ps"
        "r" "segR" "segW" "segL" "c" "effW" "effL"
      )
    )
    unless(callbackOrder
      callbackOrder = mapcar('car propPairs)
    )
    cdfData = cdfGetInstCDF(inst)
    saValidateCdfParamNames(inst cdfData propPairs)

    foreach(pair propPairs
      pname = car(pair)
      val = cadr(pair)
      param = if(cdfData cdfFindParamByName(cdfData pname) nil)
      ptype = if(param && stringp(param~>paramType) param~>paramType "string")
      saReplaceInstPropTyped(inst pname ptype val)
    )

    cdfData = cdfGetInstCDF(inst)
    when(cdfData
      foreach(pair propPairs
        pname = car(pair)
        param = cdfFindParamByName(cdfData pname)
        val = cadr(pair)
        when(param
          ptype = if(stringp(param~>paramType) param~>paramType "string")
          param~>value = saCoerceCdfParamValue(ptype val)
        )
      )
      cdfgData = cdfData
      cdfgForm = nil
      when(isCallable('PasCdfFormInit)
        PasCdfFormInit(cdfData)
      )
      foreach(name callbackOrder
        param = cdfFindParamByName(cdfData name)
        when(param && stringp(param~>callback) && param~>callback != ""
          evalstring(param~>callback)
        )
      )
      syncNames = copy(derivedProps)
      foreach(pair propPairs
        pname = car(pair)
        unless(member(pname syncNames)
          syncNames = append1(syncNames pname)
        )
      )
      foreach(name syncNames
        param = cdfFindParamByName(cdfData name)
        when(param
          ptype = if(stringp(param~>paramType) param~>paramType "string")
          when(ptype == "boolean" || param~>value != nil
            saReplaceInstPropTyped(inst name ptype param~>value)
          )
        )
      )
    )
    when(isCallable('cdfUpdateInstParam)
      cdfUpdateInstParam(inst)
    )
    t
  )
)

;;; Backward-compatible alias requested by SKILL-ANALOG adapters & prompts
procedure(saTriggerInstanceCdfCallbacks(inst @optional propPairs callbackOrder derivedProps)
  let((cdfData pairs ptype)
    if(propPairs then
      saApplyInstCdfCallbacks(inst propPairs callbackOrder derivedProps)
    else
      cdfData = cdfGetInstCDF(inst)
      pairs = nil
      when(cdfData && cdfData~>parameters
        foreach(p cdfData~>parameters
          ptype = if(stringp(p~>paramType) p~>paramType "string")
          when(p~>callback && p~>callback != "" && (ptype == "boolean" || p~>value != nil)
            pairs = append1(pairs list(p~>name p~>value))
          )
        )
      )
      saApplyInstCdfCallbacks(inst pairs callbackOrder derivedProps)
    )
  )
)

;;; Clean string-preserving variant when CDF values are already strings
procedure(saSyncInstStringCdf(inst propPairs @optional callbackOrder derivedProps)
  let((cdfData cdfgData cdfgForm param val)
    unless(callbackOrder
      callbackOrder = mapcar('car propPairs)
    )
    unless(derivedProps
      derivedProps = list("l" "w" "fw" "fingers" "nf" "m" "simM" "simW" "ad" "as" "pd" "ps" "r" "c")
    )
    cdfData = cdfGetInstCDF(inst)
    saValidateCdfParamNames(inst cdfData propPairs)
    foreach(pair propPairs
      val = cadr(pair)
      dbReplaceProp(inst car(pair) "string" if(stringp(val) val sprintf(nil "%L" val)))
    )
    cdfData = cdfGetInstCDF(inst)
    when(cdfData
      cdfgData = cdfData
      cdfgForm = nil
      when(isCallable('PasCdfFormInit)
        PasCdfFormInit(cdfData)
      )
      foreach(name callbackOrder
        param = cdfFindParamByName(cdfData name)
        when(param && stringp(param~>callback) && param~>callback != ""
          evalstring(param~>callback)
        )
      )
      foreach(name derivedProps
        param = cdfFindParamByName(cdfData name)
        when(param && param~>value != nil
          val = param~>value
          dbReplaceProp(inst name "string" if(stringp(val) val sprintf(nil "%L" val)))
        )
      )
    )
    when(isCallable('cdfUpdateInstParam)
      cdfUpdateInstParam(inst)
    )
    t
  )
)

;;; ---------------------------------------------------------------------------
;;; 2. Schematic Check, Save & Pure-SKILL JSON Inspection (`saDumpSchematicJson`)
;;; ---------------------------------------------------------------------------

procedure(saCountSchMarkers(cv)
  let((errs warns sev)
    errs = 0
    warns = 0
    foreach(m cv~>markers
      sev = lowerCase(sprintf(nil "%s" (or m~>severity "")))
      cond(
        (sev == "error" errs = errs + 1)
        (sev == "warning" warns = warns + 1)
      )
    )
    list(errs warns)
  )
)

procedure(saCollectSchErrorMarkersJson(cv @optional (fallbackErrs 0))
  let((items sev msgTxt)
    items = nil
    foreach(m cv~>markers
      sev = lowerCase(sprintf(nil "%s" (or m~>severity "")))
      when(sev == "error" || (sev != "warning" && sev != "info" && fallbackErrs > 0 && sev != "")
        msgTxt = sprintf(nil "%s" (or m~>msg m~>shortMsg m~>reason "schematic check error"))
        items = append1(
          items
          sprintf(
            nil
            "{\"msg\": %s, \"severity\": %s}"
            saJsonScalar(msgTxt)
            saJsonScalar(sev)
          )
        )
      )
    )
    when(fallbackErrs > 0 && items == nil
      items = list(
        sprintf(
          nil
          "{\"msg\": %s, \"severity\": \"error\"}"
          saJsonScalar(sprintf(nil "schCheck reported %d error(s)" fallbackErrs))
        )
      )
    )
    strcat("[" saJoinStrings(items ", ") "]")
  )
)

procedure(saCheckAndSave(cv @optional outJsonPath)
  let((chk counts errs warns saved errJson okFlag jsonTxt out)
    unless(cv error("saCheckAndSave requires a valid cellView dbObject\n"))
    chk = schCheck(cv)
    counts = saCountSchMarkers(cv)
    errs = car(counts)
    warns = cadr(counts)
    when(listp(chk) && length(chk) >= 2 && fixp(car(chk)) && fixp(cadr(chk))
      when(car(chk) > errs errs = car(chk))
      when(cadr(chk) > warns warns = cadr(chk))
    )
    errJson = saCollectSchErrorMarkersJson(cv errs)
    saved = nil
    when(errs == 0
      saved = dbSave(cv)
    )
    okFlag = (errs == 0 && saved != nil)
    jsonTxt = sprintf(
      nil
      "{\"ok\": %s, \"lib\": %s, \"cell\": %s, \"view\": %s, \"check_errors\": %d, \"check_warnings\": %d, \"saved\": %s, \"errors\": %s}"
      saJsonBool(okFlag)
      saJsonScalar(cv~>libName)
      saJsonScalar(cv~>cellName)
      saJsonScalar(cv~>viewName)
      errs
      warns
      saJsonBool(saved != nil)
      errJson
    )
    when(outJsonPath && stringp(outJsonPath) && outJsonPath != ""
      out = outfile(outJsonPath)
      unless(out error("Cannot open JSON output path: %s\n" outJsonPath))
      fprintf(out "%s\n" jsonTxt)
      close(out)
    )
    list(errs warns saved jsonTxt)
  )
)

procedure(saCheckAndSaveJson(cv outJsonPath)
  saCheckAndSave(cv outJsonPath)
)

procedure(saCheckAndReportSchematic(cv reportPath)
  let((out chk wireLabels)
    chk = schCheck(cv)
    out = outfile(reportPath)
    unless(out error("Cannot open report output path: %s\n" reportPath))
    fprintf(out "SCHCHECK %L\n" chk)
    fprintf(out "BBOX %L\n" cv~>bBox)
    wireLabels = setof(s cv~>shapes s~>objType == "label" && car(s~>lpp) == "wire")
    fprintf(out "WIRELABEL_COUNT %d\n" length(wireLabels))
    foreach(inst cv~>instances
      fprintf(out "INSTANCE %s %s/%s %L %L\n"
              inst~>name inst~>libName inst~>cellName inst~>xy inst~>orient)
      foreach(prop inst~>prop
        fprintf(out "PROP %s %L\n" prop~>name prop~>value)
      )
      foreach(term inst~>instTerms
        fprintf(out "CONNECT %s %L\n" term~>name term~>net~>name)
      )
    )
    close(out)
    chk
  )
)

procedure(saGetInstTermXY(inst termName)
  let((res fig)
    res = nil
    foreach(it inst~>instTerms
      when(it~>name == termName && res == nil
        fig = car(it~>term~>pins~>fig)
        when(fig && fig~>bBox
          res = dbTransformPoint(centerBBox(fig~>bBox) inst~>transform)
        )
      )
    )
    res
  )
)

procedure(saSerializeSchematicJson(cv)
  let((instJsonList netJsonList pinJsonList childJsonList seenChildren
       floatingNets singleTermNets counts checkErrs checkWarns
       cdfData cdfKeys storedItems cdfItems pinCenterItems
       connItems termPt childKey nlAct param pval)
    unless(cv error("saSerializeSchematicJson requires a valid cellView\n"))

    cdfKeys = list(
      "w" "fw" "l" "nf" "fingers" "m" "simM" "simW"
      "r" "segR" "segW" "segL" "c" "l_ind" "ind"
      "vdc" "vac" "acm" "idc" "srcType" "model"
    )

    instJsonList = nil
    childJsonList = nil
    seenChildren = nil

    foreach(inst cv~>instances
      storedItems = nil
      foreach(prop inst~>prop
        storedItems = append1(
          storedItems
          sprintf(nil "%s: %s" saJsonEscapeString(prop~>name) saJsonScalar(prop~>value))
        )
      )

      cdfItems = nil
      cdfData = errset(cdfGetInstCDF(inst) nil)
      cdfData = if(cdfData car(cdfData) nil)
      when(cdfData
        foreach(k cdfKeys
          param = cdfFindParamByName(cdfData k)
          when(param && param~>value != nil && param~>value != ""
            pval = param~>value
            cdfItems = append1(
              cdfItems
              sprintf(nil "%s: %s" saJsonEscapeString(k) saJsonScalar(pval))
            )
          )
        )
      )

      pinCenterItems = nil
      foreach(it inst~>instTerms
        termPt = saGetInstTermXY(inst it~>name)
        when(termPt
          pinCenterItems = append1(
            pinCenterItems
            sprintf(nil "%s: %s" saJsonEscapeString(it~>name) saJsonPoint(termPt))
          )
        )
      )

      nlAct = dbGetPropByName(inst "nlAction")
      nlAct = if(nlAct nlAct~>value nil)

      instJsonList = append1(
        instJsonList
        sprintf(
          nil
          "{\"name\": %s, \"lib\": %s, \"cell\": %s, \"view\": %s, \"master\": %s, \"xy\": %s, \"orient\": %s, \"nlAction\": %s, \"stored_props\": {%s}, \"effective_cdf\": {%s}, \"pin_centers\": {%s}}"
          saJsonScalar(inst~>name)
          saJsonScalar(inst~>libName)
          saJsonScalar(inst~>cellName)
          saJsonScalar(inst~>viewName)
          saJsonScalar(sprintf(nil "%s/%s/%s" (or inst~>libName "") (or inst~>cellName "") (or inst~>viewName "")))
          saJsonPoint(inst~>xy)
          saJsonScalar(inst~>orient)
          saJsonScalar(nlAct)
          saJoinStrings(storedItems ", ")
          saJoinStrings(cdfItems ", ")
          saJoinStrings(pinCenterItems ", ")
        )
      )

      when(inst~>libName && !member(inst~>libName list("basic" "analogLib")) &&
           ddGetObj(inst~>libName inst~>cellName "schematic")
        childKey = strcat(inst~>libName "/" inst~>cellName)
        unless(member(childKey seenChildren)
          seenChildren = append1(seenChildren childKey)
          childJsonList = append1(
            childJsonList
            sprintf(
              nil
              "{\"lib\": %s, \"cell\": %s, \"view\": \"schematic\"}"
              saJsonScalar(inst~>libName)
              saJsonScalar(inst~>cellName)
            )
          )
        )
      )
    )

    netJsonList = nil
    floatingNets = nil
    singleTermNets = nil

    foreach(net cv~>nets
      connItems = nil
      foreach(it net~>instTerms
        connItems = append1(
          connItems
          sprintf(
            nil
            "{\"inst\": %s, \"term\": %s}"
            saJsonScalar(it~>inst~>name)
            saJsonScalar(it~>name)
          )
        )
      )
      when(length(net~>instTerms) == 0 && net~>term == nil
        floatingNets = append1(floatingNets net~>name)
      )
      when(length(net~>instTerms) == 1 && net~>term == nil && !net~>isGlobal
        singleTermNets = append1(singleTermNets net~>name)
      )
      netJsonList = append1(
        netJsonList
        sprintf(
          nil
          "{\"name\": %s, \"isGlobal\": %s, \"hasPin\": %s, \"connections\": [%s]}"
          saJsonScalar(net~>name)
          saJsonBool(net~>isGlobal != nil)
          saJsonBool(net~>term != nil)
          saJoinStrings(connItems ", ")
        )
      )
    )

    pinJsonList = nil
    foreach(term cv~>terminals
      termPt = nil
      when(term~>pins
        let((pfig)
          pfig = car(term~>pins)~>fig
          when(pfig
            termPt = if(pfig~>bBox centerBBox(pfig~>bBox) pfig~>xy)
          )
        )
      )
      pinJsonList = append1(
        pinJsonList
        sprintf(
          nil
          "{\"name\": %s, \"direction\": %s, \"xy\": %s}"
          saJsonScalar(term~>name)
          saJsonScalar(term~>direction)
          saJsonPoint(termPt)
        )
      )
    )

    counts = saCountSchMarkers(cv)
    checkErrs = car(counts)
    checkWarns = cadr(counts)

    sprintf(
      nil
      "{\n  \"lib\": %s,\n  \"cell\": %s,\n  \"view\": %s,\n  \"bbox\": %s,\n  \"instances\": [%s],\n  \"nets\": [%s],\n  \"pins\": [%s],\n  \"diagnostics\": {\n    \"floating_nets\": %s,\n    \"single_term_nets\": %s,\n    \"check_errors\": %d,\n    \"check_warnings\": %d\n  },\n  \"child_cells\": [%s]\n}"
      saJsonScalar(cv~>libName)
      saJsonScalar(cv~>cellName)
      saJsonScalar(cv~>viewName)
      saJsonBBox(cv~>bBox)
      saJoinStrings(instJsonList ", ")
      saJoinStrings(netJsonList ", ")
      saJoinStrings(pinJsonList ", ")
      saJsonStringArray(floatingNets)
      saJsonStringArray(singleTermNets)
      checkErrs
      checkWarns
      saJoinStrings(childJsonList ", ")
    )
  )
)

procedure(saDumpSchematicJson(cv outJsonPath)
  let((targetCv jsonTxt out)
    targetCv = cv
    when(targetCv == nil && isCallable('geGetEditCellView)
      targetCv = geGetEditCellView()
    )
    unless(targetCv error("saDumpSchematicJson: no cellView supplied and no active GUI edit cellView\n"))
    jsonTxt = saSerializeSchematicJson(targetCv)
    if(outJsonPath && stringp(outJsonPath) && outJsonPath != "" then
      out = outfile(outJsonPath)
      unless(out error("Cannot open output JSON path: %s\n" outJsonPath))
      fprintf(out "%s\n" jsonTxt)
      close(out)
      outJsonPath
    else
      jsonTxt
    )
  )
)

;;; ---------------------------------------------------------------------------
;;; 3. Non-Destructive Grid-Snapped Schematic Placement & Orthogonal Routing
;;; ---------------------------------------------------------------------------
;;; Line-oriented key-value plan grammar (`#` or `;` starts comments):
;;;   LIB <libName> [TECH <techLibName>]
;;;   CELL <cellName> [VIEW <viewName>]
;;;   GRID 0.0625
;;;   SYMBOL true|false
;;;   INST <instName> <masterLib> <masterCell> <masterView> <x> <y> [orient]
;;;   PARAM <instName> <paramName> <paramValue>
;;;   PIN <pinName> <input|output|inputOutput> <x> <y> [orient]
;;;   STUB <netName> <instName>.<termName> <up|down|left|right> [len]
;;;   NET <netName> <ep1> <ep2> [<ep3> ...]   (endpoint: INST.TERM | PIN.<name> | x:y)
;;;   WIRE <netName_or_dash> <x1> <y1> <x2> <y2>

procedure(saRouteOrthogonalWire(cv p1 p2 @optional netName (grid 0.0625))
  let((sp1 sp2 midPts wires w0 lx ly)
    sp1 = saSnapPoint(p1 grid)
    sp2 = saSnapPoint(p2 grid)
    if(abs(xCoord(sp1) - xCoord(sp2)) < 1e-6 || abs(yCoord(sp1) - yCoord(sp2)) < 1e-6 then
      midPts = list(sp1 sp2)
    else
      midPts = list(sp1 list(xCoord(sp2) yCoord(sp1)) sp2)
    )
    wires = schCreateWire(cv "draw" "full" midPts grid grid 0.0)
    when(netName && netName != "" && netName != "-" && wires
      w0 = if(listp(wires) car(wires) wires)
      lx = 0.5 * (xCoord(sp1) + xCoord(sp2))
      ly = yCoord(sp1)
      schCreateWireLabel(cv w0 list(lx ly) netName "lowerCenter" "R0" "stick" 0.0625 nil)
    )
    wires
  )
)

procedure(saResolvePlanEndpoint(spec instTable pinTable grid)
  let((parts head tail inst pt coords)
    cond(
      (index(spec ":")
        coords = parseString(spec ":")
        when(length(coords) != 2 error("Malformed coordinate endpoint %L in plan\n" spec))
        saSnapPoint(list(atof(car(coords)) atof(cadr(coords))) grid)
      )
      (index(spec ".")
        parts = parseString(spec ".")
        when(length(parts) != 2 error("Malformed terminal endpoint %L in plan\n" spec))
        head = car(parts)
        tail = cadr(parts)
        if(head == "PIN" then
          pt = pinTable[tail]
          unless(pt error("Unknown PIN %L referenced in NET statement\n" tail))
          saSnapPoint(pt grid)
        else
          inst = instTable[head]
          unless(inst error("Unknown instance %L referenced in endpoint %L\n" head spec))
          pt = saGetInstTermXY(inst tail)
          unless(pt error("Terminal %L not found on instance %L\n" tail head))
          saSnapPoint(pt grid)
        )
      )
      (t
        error("Unsupported endpoint syntax %L (use INST.TERM, PIN.NAME, or X:Y)\n" spec)
      )
    )
  )
)

procedure(saBackupExistingView(libName cellName viewName suffixTag)
  let((existing srcCv bakCell bakCv saved srcOk copyOk saveOk verifiedObj)
    existing = ddGetObj(libName cellName viewName)
    bakCell = nil
    when(existing
      bakCell = sprintf(nil "%s_bak_%s" cellName suffixTag)
      srcCv = nil
      bakCv = nil
      saved = nil
      srcOk = nil
      copyOk = nil
      saveOk = nil
      unwindProtect(
        progn(
          let((rOpen rCopy rSave)
            rOpen = errset(dbOpenCellViewByType(libName cellName viewName "" "r") nil)
            srcCv = if(rOpen car(rOpen) nil)
            srcOk = (srcCv != nil)
            when(srcOk
              rCopy = errset(dbCopyCellView(srcCv libName bakCell viewName nil nil t) nil)
              bakCv = if(rCopy car(rCopy) nil)
              copyOk = (bakCv != nil)
              when(copyOk
                rSave = errset(dbSave(bakCv) nil)
                saved = if(rSave car(rSave) nil)
                saveOk = (saved != nil)
              )
            )
          )
        )
        progn(
          when(bakCv
            errset(dbClose(bakCv) nil)
          )
          when(srcCv
            errset(dbClose(srcCv) nil)
          )
        )
      )
      verifiedObj = ddGetObj(libName bakCell viewName)
      unless(srcOk && copyOk && saveOk && verifiedObj != nil
        error("saBackupExistingView failed to create verified backup %s/%s/%s\n" libName bakCell viewName)
      )
    )
    bakCell
  )
)

procedure(saEnsureLibrary(libName techLibName)
  let((libObj techObj)
    libObj = ddGetObj(libName)
    unless(libObj
      libObj = ddCreateLib(libName)
      unless(libObj error("Failed to create OA library %s\n" libName))
      when(techLibName && techLibName != ""
        techObj = ddGetObj(techLibName)
        unless(techObj error("Technology library %s not found\n" techLibName))
        when(isCallable('techBindTechFile)
          techBindTechFile(libObj techLibName "tech.db" t)
        )
      )
    )
    libObj
  )
)

procedure(saPlaceAndWireFromPlan(planPath outJsonPath)
  let((inPort rawLine trimmed tokens sep cmd
       libName techLib cellName viewName grid genSymbol
       instSpecs paramMap pinSpecs stubSpecs netSpecs wireSpecs
       instTable pinTable openedMasters
       cv bakCell symBakCell symGenerated ts chkResult counts errs warns saved errJson outPort resJson)

    inPort = infile(planPath)
    unless(inPort error("Cannot open schematic plan file: %s\n" planPath))

    sep = strcat(" " buildString(list(intToChar(9))) buildString(list(intToChar(10))) buildString(list(intToChar(13))))
    libName = nil
    techLib = nil
    cellName = nil
    viewName = "schematic"
    grid = 0.0625
    genSymbol = nil

    instSpecs = nil
    paramMap = makeTable('saParamTable nil)
    pinSpecs = nil
    stubSpecs = nil
    netSpecs = nil
    wireSpecs = nil

    while(gets(rawLine inPort)
      tokens = parseString(rawLine sep)
      when(tokens
        trimmed = car(tokens)
        unless(substring(trimmed 1 1) == "#" || substring(trimmed 1 1) == ";"
          cmd = upperCase(trimmed)
          cond(
            (cmd == "LIB"
              libName = cadr(tokens)
              when(length(tokens) >= 4 && upperCase(nth(2 tokens)) == "TECH"
                techLib = nth(3 tokens)
              )
            )
            (cmd == "CELL"
              cellName = cadr(tokens)
              when(length(tokens) >= 4 && upperCase(nth(2 tokens)) == "VIEW"
                viewName = nth(3 tokens)
              )
            )
            (cmd == "GRID"
              grid = atof(cadr(tokens))
            )
            (cmd == "SYMBOL"
              genSymbol = member(lowerCase(cadr(tokens)) list("true" "t" "1" "yes")) != nil
            )
            (cmd == "INST"
              when(length(tokens) < 7
                close(inPort)
                error("INST requires: INST <name> <lib> <cell> <view> <x> <y> [orient]\n")
              )
              instSpecs = append1(
                instSpecs
                list(
                  nth(1 tokens)
                  nth(2 tokens)
                  nth(3 tokens)
                  nth(4 tokens)
                  atof(nth(5 tokens))
                  atof(nth(6 tokens))
                  if(length(tokens) >= 8 nth(7 tokens) "R0")
                )
              )
            )
            (cmd == "PARAM"
              when(length(tokens) < 4
                close(inPort)
                error("PARAM requires: PARAM <instName> <paramName> <paramValue>\n")
              )
              paramMap[nth(1 tokens)] = append1(paramMap[nth(1 tokens)] list(nth(2 tokens) nth(3 tokens)))
            )
            (cmd == "PIN"
              when(length(tokens) < 5
                close(inPort)
                error("PIN requires: PIN <name> <direction> <x> <y> [orient]\n")
              )
              pinSpecs = append1(
                pinSpecs
                list(
                  nth(1 tokens)
                  nth(2 tokens)
                  atof(nth(3 tokens))
                  atof(nth(4 tokens))
                  if(length(tokens) >= 6 nth(5 tokens) "R0")
                )
              )
            )
            (cmd == "STUB"
              when(length(tokens) < 4
                close(inPort)
                error("STUB requires: STUB <netName> <inst.term> <up|down|left|right> [len]\n")
              )
              stubSpecs = append1(
                stubSpecs
                list(
                  nth(1 tokens)
                  nth(2 tokens)
                  lowerCase(nth(3 tokens))
                  if(length(tokens) >= 5 atof(nth(4 tokens)) 0.25)
                )
              )
            )
            (cmd == "NET"
              when(length(tokens) < 4
                close(inPort)
                error("NET requires: NET <netName> <ep1> <ep2> [...]\n")
              )
              netSpecs = append1(netSpecs cdr(tokens))
            )
            (cmd == "WIRE"
              when(length(tokens) < 6
                close(inPort)
                error("WIRE requires: WIRE <netName_or_-> <x1> <y1> <x2> <y2>\n")
              )
              wireSpecs = append1(
                wireSpecs
                list(nth(1 tokens) atof(nth(2 tokens)) atof(nth(3 tokens)) atof(nth(4 tokens)) atof(nth(5 tokens)))
              )
            )
            (t
              close(inPort)
              error("Unknown plan directive %L in %s\n" cmd planPath)
            )
          )
        )
      )
    )
    close(inPort)

    unless(libName && cellName
      error("Plan %s must define both LIB and CELL\n" planPath)
    )

    saEnsureLibrary(libName techLib)
    ts = saTimestampCompact()
    bakCell = saBackupExistingView(libName cellName viewName ts)
    symBakCell = nil
    symGenerated = nil

    cv = nil
    openedMasters = nil
    instTable = makeTable('saInstTable nil)
    pinTable = makeTable('saPinTable nil)

    unwindProtect(
      progn(
        cv = dbOpenCellViewByType(libName cellName viewName "schematic" "w")
        unless(cv error("Cannot open %s/%s/%s for schematic write\n" libName cellName viewName))

        ;;; 1. Place grid-snapped instances & run CDF callbacks
        foreach(ispec instSpecs
          let((iname mlib mcell mview ix iy orient masterCv pt inst pairs)
            iname = nth(0 ispec)
            mlib = nth(1 ispec)
            mcell = nth(2 ispec)
            mview = nth(3 ispec)
            ix = nth(4 ispec)
            iy = nth(5 ispec)
            orient = nth(6 ispec)
            masterCv = dbOpenCellViewByType(mlib mcell mview "" "r")
            unless(masterCv error("Cannot open master %s/%s/%s\n" mlib mcell mview))
            openedMasters = append1(openedMasters masterCv)
            pt = saSnapPoint(list(ix iy) grid)
            inst = dbCreateInst(cv masterCv iname pt orient)
            unless(inst error("Failed placing instance %s (%s/%s)\n" iname mlib mcell))
            instTable[iname] = inst
            pairs = paramMap[iname]
            when(pairs
              saApplyInstCdfCallbacks(inst pairs mapcar('car pairs))
            )
          )
        )

        ;;; 2. Create schematic pins (`basic/ipin`, `basic/opin`, `basic/iopin`)
        foreach(pspec pinSpecs
          let((pname pdir px py porient pinCell pinMaster pt)
            pname = nth(0 pspec)
            pdir = nth(1 pspec)
            px = nth(2 pspec)
            py = nth(3 pspec)
            porient = nth(4 pspec)
            pinCell = cond(
              (pdir == "input" "ipin")
              (pdir == "output" "opin")
              (t "iopin")
            )
            pinMaster = dbOpenCellViewByType("basic" pinCell "symbol" "" "r")
            unless(pinMaster error("Cannot open basic/%s/symbol\n" pinCell))
            openedMasters = append1(openedMasters pinMaster)
            pt = saSnapPoint(list(px py) grid)
            schCreatePin(cv pinMaster pname pdir nil pt porient)
            pinTable[pname] = pt
          )
        )

        ;;; 3. Route short terminal stubs + net labels
        foreach(sspec stubSpecs
          let((nname ep dir slen p0 ex ey)
            nname = nth(0 sspec)
            ep = nth(1 sspec)
            dir = nth(2 sspec)
            slen = saSnapToGrid(nth(3 sspec) grid)
            p0 = saResolvePlanEndpoint(ep instTable pinTable grid)
            ex = xCoord(p0)
            ey = yCoord(p0)
            cond(
              (dir == "up" ey = ey + slen)
              (dir == "down" ey = ey - slen)
              (dir == "left" ex = ex - slen)
              (dir == "right" ex = ex + slen)
              (t error("Invalid STUB direction %L\n" dir))
            )
            saRouteOrthogonalWire(cv p0 list(ex ey) nname grid)
          )
        )

        ;;; 4. Route multi-endpoint orthogonal nets
        foreach(nspec netSpecs
          let((nname eps prevPt curPt)
            nname = car(nspec)
            eps = cdr(nspec)
            prevPt = saResolvePlanEndpoint(car(eps) instTable pinTable grid)
            foreach(ep cdr(eps)
              curPt = saResolvePlanEndpoint(ep instTable pinTable grid)
              saRouteOrthogonalWire(cv prevPt curPt nname grid)
              prevPt = curPt
            )
          )
        )

        ;;; 5. Route explicit wire segments
        foreach(wspec wireSpecs
          saRouteOrthogonalWire(
            cv
            list(nth(1 wspec) nth(2 wspec))
            list(nth(3 wspec) nth(4 wspec))
            nth(0 wspec)
            grid
          )
        )

        ;;; 6. Check & Save schematic (ONLY call dbSave when errs == 0!)
        chkResult = schCheck(cv)
        counts = saCountSchMarkers(cv)
        errs = car(counts)
        warns = cadr(counts)
        when(listp(chkResult) && length(chkResult) >= 2 && fixp(car(chkResult)) && fixp(cadr(chkResult))
          when(car(chkResult) > errs errs = car(chkResult))
          when(cadr(chkResult) > warns warns = cadr(chkResult))
        )
        errJson = saCollectSchErrorMarkersJson(cv errs)
        saved = nil
        when(errs == 0
          saved = dbSave(cv)
        )

        ;;; 7. Optional non-destructive symbol generation (ONLY when errs == 0 and saved != nil)
        when(errs == 0 && saved != nil && genSymbol && isCallable('schSchemToPinList) && isCallable('schPinListToSymbolGen)
          let((pinList)
            symBakCell = saBackupExistingView(libName cellName "symbol" strcat("sym_" ts))
            pinList = schSchemToPinList(libName cellName viewName)
            when(pinList
              schPinListToSymbolGen(libName cellName "symbol" pinList)
              symGenerated = t
            )
          )
        )

        resJson = sprintf(
          nil
          "{\"ok\": %s, \"lib\": %s, \"cell\": %s, \"view\": %s, \"backup_cell\": %s, \"symbol_backup_cell\": %s, \"symbol_generated\": %s, \"saved\": %s, \"instance_count\": %d, \"pin_count\": %d, \"check_errors\": %d, \"check_warnings\": %d, \"errors\": %s}"
          saJsonBool(errs == 0 && saved != nil)
          saJsonScalar(libName)
          saJsonScalar(cellName)
          saJsonScalar(viewName)
          saJsonScalar(bakCell)
          saJsonScalar(symBakCell)
          saJsonBool(symGenerated)
          saJsonBool(saved != nil)
          length(instSpecs)
          length(pinSpecs)
          errs
          warns
          errJson
        )

        when(outJsonPath && stringp(outJsonPath) && outJsonPath != ""
          outPort = outfile(outJsonPath)
          unless(outPort error("Cannot open plan output JSON path: %s\n" outJsonPath))
          fprintf(outPort "%s\n" resJson)
          close(outPort)
        )
      )
      progn(
        foreach(mCv openedMasters
          errset(dbClose(mCv) nil)
        )
        when(cv
          errset(dbClose(cv) nil)
        )
      )
    )
    resJson
  )
)

;;; ---------------------------------------------------------------------------
;;; 4. Batch OCEAN Spectre Netlist Export (`ocean -nograph -restore ...`)
;;; ---------------------------------------------------------------------------
procedure(saExportSpectreNetlist(libName cellName viewName runDir modelScs sectionName outPathTxt @optional probeLib probeCell)
  let((probeCv netlistPath out)
    envSetVal("asimenv.startup" "projectDir" 'string runDir)
    when(probeLib && probeCell
      probeCv = dbOpenCellViewByType(probeLib probeCell "symbol" "" "r")
    )
    simulator('spectre)
    design(libName cellName viewName)
    resultsDir(runDir)
    when(modelScs && sectionName
      modelFile(list(list(modelScs sectionName)))
    )
    netlistPath = createNetlist(?recreateAll t ?display nil)
    out = outfile(outPathTxt)
    fprintf(out "%L\n" netlistPath)
    close(out)
    when(probeCv dbClose(probeCv))
    netlistPath
  )
)

;;; ---------------------------------------------------------------------------
;;; 5. OCEAN Spectre Stability (`stb`) Margin Reader (`iprobe` / `diffstbprobe`)
;;; ---------------------------------------------------------------------------
procedure(saExportStbMargins(psfDir stbResultName outPathTxt)
  let((out)
    out = outfile(outPathTxt)
    unless(out error("Cannot open STB output file: %s\n" outPathTxt))
    simulator('spectre)
    openResults(psfDir)
    selectResult(stbResultName)
    fprintf(out "PM_DEG %L\n" getData("phaseMargin"))
    fprintf(out "PM_FREQ_HZ %L\n" getData("phaseMarginFreq"))
    fprintf(out "GM_DB %L\n" getData("gainMargin"))
    fprintf(out "GM_FREQ_HZ %L\n" getData("gainMarginFreq"))
    close(out)
    t
  )
)

;;; Backward-compatible alias returning structured margin association list
procedure(saMeasureStbMargin(psfDir @optional (stbResultName "stb-margin.stb") outPathTxt)
  let((pm pmFreq gm gmFreq)
    when(outPathTxt && stringp(outPathTxt) && outPathTxt != ""
      saExportStbMargins(psfDir stbResultName outPathTxt)
    )
    simulator('spectre)
    openResults(psfDir)
    selectResult(stbResultName)
    pm = getData("phaseMargin")
    pmFreq = getData("phaseMarginFreq")
    gm = getData("gainMargin")
    gmFreq = getData("gainMarginFreq")
    list(
      list("phase_margin_deg" pm)
      list("ugf_hz" pmFreq)
      list("gain_margin_db" gm)
      list("gm_freq_hz" gmFreq)
    )
  )
)

;;; ---------------------------------------------------------------------------
;;; 6. Full-Design Schematic PNG Export (Live GUI Session or `-restore` Display)
;;; ---------------------------------------------------------------------------
procedure(saExportSchematicPng(libName cellName viewName pngPath @optional (width 2600) (height 1700))
  let((win)
    win = geOpen(?lib libName ?cell cellName ?view viewName ?viewType "schematic" ?mode "r")
    unless(win error("Cannot open schematic window for %s/%s/%s\n" libName cellName viewName))
    hiExportImage(
      ?fileName pngPath
      ?window win
      ?exportRegion 'entireDesign
      ?width width
      ?height height
      ?fileType "PNG"
    )
    hiCloseWindow(win)
    t
  )
)
