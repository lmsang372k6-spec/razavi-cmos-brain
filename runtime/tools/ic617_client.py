#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Zero-Python3 Live Virtuoso IC617 CIW Bridge Helper & Client CLI.

Managed by SKILL-ANALOG (release 2026.11.19.1).
100% Python 2.6.6+ and Python 3 standard-library compatible (`optparse`, zero external deps).

Modes:
  1. Daemon helper spawned by Virtuoso CIW `(load ".../ic617_live_bridge.il")`:
       python tools/ic617_client.py --start-helper
     Creates `0700` `~/.cache/skill-analog/`, `0600` random session token
     `ic617-<user>.token`, and `0600` Unix domain socket `ic617-<user>.sock`.
  2. Client CLI invoked by Codex / scripts:
       python tools/ic617_client.py ping
       python tools/ic617_client.py active-cv
       python tools/ic617_client.py dump-json [--lib L --cell C --view V] [--out FILE]
       python tools/ic617_client.py set-param --inst M1 --param w=12u [--param fingers=4] [--lib L --cell C]
       python tools/ic617_client.py check-save [--lib L --cell C --view V] [--out FILE]
       python tools/ic617_client.py export-png --out PNG [--lib L --cell C --view V] [--width 2600 --height 1700]
       python tools/ic617_client.py eval "<skill_expression>"
       python tools/ic617_client.py --self-test
"""
from __future__ import print_function

import binascii
import errno
import getpass
import json
import os
from optparse import OptionParser
import select
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time

sys.dont_write_bytecode = True

RELEASE_VERSION = "2026.11.19.1"
_TOOLS_DIR = os.path.dirname(os.path.realpath(__file__))
_LIBRARY_ROOT = os.path.dirname(_TOOLS_DIR)
_MODE_0700 = int("700", 8)
_MODE_0600 = int("600", 8)

_REQ_ID_LOCK = threading.Lock()
_REQ_ID_SEQ = [0]

try:
    TEXT_TYPES = (basestring,)
except NameError:
    TEXT_TYPES = (str,)


class _SilentOptionParser(OptionParser):
    def error(self, msg):
        raise ValueError(msg)


def _to_bytes(val):
    if isinstance(val, bytes):
        return val
    return val.encode("utf-8")


def _to_text(val):
    if isinstance(val, bytes):
        return val.decode("utf-8", "replace")
    return val


def _next_req_id():
    now = time.time()
    usec = int((now - int(now)) * 1000000)
    _REQ_ID_LOCK.acquire()
    try:
        _REQ_ID_SEQ[0] += 1
        seq = _REQ_ID_SEQ[0]
    finally:
        _REQ_ID_LOCK.release()
    return "%d-%d-%06d-%d" % (os.getpid(), int(now) % 100000000, usec, seq)


def _inside_library(path):
    rp = os.path.normcase(os.path.realpath(path))
    lb = os.path.normcase(os.path.realpath(_LIBRARY_ROOT))
    return rp == lb or rp.startswith(lb.rstrip(os.sep) + os.sep)


def _current_user():
    for env_k in ("USER", "LOGNAME", "USERNAME"):
        val = os.environ.get(env_k)
        if val:
            return "".join(ch if (ch.isalnum() or ch in ("_", "-")) else "_" for ch in val)
    try:
        u = getpass.getuser()
        return "".join(ch if (ch.isalnum() or ch in ("_", "-")) else "_" for ch in u)
    except Exception:
        return "uid%d" % (os.getuid() if hasattr(os, "getuid") else 0)


def resolve_bridge_paths(socket_dir=None, user=None):
    base = socket_dir or os.environ.get("SA_BRIDGE_DIR")
    if not base:
        home = os.path.expanduser("~")
        base = os.path.join(home, ".cache", "skill-analog")
    base = os.path.abspath(base)
    if _inside_library(base):
        raise ValueError("Refusing to place runtime bridge socket inside SKILL-ANALOG library: " + base)
    uname = user or _current_user()
    return {
        "dir": base,
        "user": uname,
        "sock": os.path.join(base, "ic617-%s.sock" % uname),
        "token": os.path.join(base, "ic617-%s.token" % uname),
        "meta": os.path.join(base, "ic617-%s.meta.json" % uname),
    }


def _ensure_private_dir(path):
    if not os.path.isdir(path):
        try:
            os.makedirs(path, _MODE_0700)
        except OSError as err:
            if err.errno != errno.EEXIST or not os.path.isdir(path):
                raise
    try:
        os.chmod(path, _MODE_0700)
    except OSError:
        pass


def _write_private_file(path, raw_bytes):
    tmp_path = "%s.tmp.%d" % (path, os.getpid())
    fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, _MODE_0600)
    try:
        os.write(fd, raw_bytes)
    finally:
        os.close(fd)
    try:
        os.chmod(tmp_path, _MODE_0600)
    except OSError:
        pass
    if hasattr(os, "replace"):
        os.replace(tmp_path, path)
    else:
        if os.path.exists(path):
            os.unlink(path)
        os.rename(tmp_path, path)


def _constant_time_eq(a, b):
    ba = _to_bytes(a or "")
    bb = _to_bytes(b or "")
    if len(ba) != len(bb):
        return False
    acc = 0
    for idx in range(len(ba)):
        ca = ord(ba[idx]) if isinstance(ba[idx], str) else ba[idx]
        cb = ord(bb[idx]) if isinstance(bb[idx], str) else bb[idx]
        acc |= (ca ^ cb)
    return acc == 0


def _skill_quote(val):
    s = str(val)
    s = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    return '"%s"' % s


def _recv_line(sock, max_bytes=16 * 1024 * 1024, rx_buf=None):
    """Read a single newline-delimited UTF-8 frame while preserving buffered trailing bytes."""
    if rx_buf is not None and rx_buf[0]:
        existing = rx_buf[0]
        nl_idx = existing.find(b"\n")
        if nl_idx >= 0:
            line_bytes = existing[:nl_idx]
            rx_buf[0] = existing[nl_idx + 1:]
            return _to_text(line_bytes).strip()
        chunks = [existing]
        total = len(existing)
        rx_buf[0] = b""
    else:
        chunks = []
        total = 0

    while True:
        piece = sock.recv(65536)
        if not piece:
            break
        nl_idx = piece.find(b"\n")
        if nl_idx >= 0:
            chunks.append(piece[:nl_idx])
            if rx_buf is not None:
                rx_buf[0] = piece[nl_idx + 1:]
            break
        chunks.append(piece)
        total += len(piece)
        if total > max_bytes:
            raise ValueError("Bridge response exceeded maximum frame size")
    return _to_text(b"".join(chunks)).strip()


def _normalize_bridge_response(parsed, default_id=None):
    """Normalize `id`, `transport_ok`, `op_ok`, and semantic `ok` from SKILL result JSON."""
    if not isinstance(parsed, dict):
        return {
            "id": default_id,
            "transport_ok": False,
            "op_ok": False,
            "ok": False,
            "error": "Invalid non-dict bridge response",
        }
    if default_id is not None and not parsed.get("id"):
        parsed["id"] = default_id

    raw_ok = bool(parsed.get("ok"))
    transport_ok = bool(parsed.get("transport_ok", True))
    op_ok = raw_ok and (parsed.get("op_ok", True) is not False)

    res_val = parsed.get("result")
    if isinstance(res_val, TEXT_TYPES):
        trimmed = res_val.strip()
        if trimmed.startswith("{") and trimmed.endswith("}"):
            try:
                inner = json.loads(trimmed)
                if isinstance(inner, dict) and inner.get("ok") is False:
                    op_ok = False
                    if not parsed.get("error"):
                        parsed["error"] = inner.get("error") or "SKILL result JSON reported ok=false"
            except Exception:
                pass
    elif isinstance(res_val, dict):
        if res_val.get("ok") is False:
            op_ok = False
            if not parsed.get("error"):
                parsed["error"] = res_val.get("error") or "SKILL result JSON reported ok=false"

    parsed["transport_ok"] = transport_ok
    parsed["op_ok"] = op_ok
    parsed["ok"] = bool(raw_ok and transport_ok and op_ok)
    return parsed


def _connect_client_socket(sock_path, timeout=32.0):
    if hasattr(socket, "AF_UNIX"):
        cli = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        cli.settimeout(timeout)
        cli.connect(sock_path)
        return cli
    # Fallback on non-POSIX local test hosts where AF_UNIX is absent
    f = open(sock_path, "rb")
    try:
        endpoint = f.read().decode("utf-8").strip()
    finally:
        f.close()
    if not endpoint.startswith("tcp://"):
        raise ValueError("Unsupported bridge endpoint descriptor: " + endpoint)
    host_port = endpoint[len("tcp://"):]
    host, port_s = host_port.rsplit(":", 1)
    cli = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    cli.settimeout(timeout)
    cli.connect((host, int(port_s)))
    return cli


def send_bridge_request(skill_cmd, socket_dir=None, timeout=30.0, token_override=None):
    timeout_f = float(timeout)
    if timeout_f <= 0.0:
        raise ValueError("timeout must be > 0")
    sock_timeout = timeout_f + 2.0

    paths = resolve_bridge_paths(socket_dir=socket_dir)
    if not os.path.exists(paths["sock"]) or not os.path.isfile(paths["token"]):
        return {
            "ok": False,
            "transport_ok": False,
            "op_ok": False,
            "bridge_active": False,
            "error": (
                "Virtuoso live bridge socket not found (%s). In Virtuoso CIW run: "
                '(load "/home/disk/eda/references/SKILL-ANALOG/tools/ic617_live_bridge.il")'
            ) % paths["sock"],
        }

    if token_override is not None:
        token = token_override
    else:
        tf = open(paths["token"], "rb")
        try:
            token = tf.read().decode("utf-8").strip()
        finally:
            tf.close()

    req_id = _next_req_id()
    req_payload = {
        "id": req_id,
        "token": token,
        "cmd": skill_cmd,
        "timeout": timeout_f,
    }
    req_line = json.dumps(req_payload) + "\n"

    cli = None
    try:
        cli = _connect_client_socket(paths["sock"], timeout=sock_timeout)
        cli.sendall(_to_bytes(req_line))
        deadline = time.time() + sock_timeout
        rx_buf = [b""]
        stale_discarded = 0

        while True:
            rem = deadline - time.time()
            if rem <= 0.0:
                return {
                    "id": req_id,
                    "ok": False,
                    "transport_ok": False,
                    "op_ok": False,
                    "bridge_active": False,
                    "error": "Timed out waiting for matching bridge reply id=" + req_id,
                }
            cli.settimeout(max(0.05, rem))
            resp_txt = _recv_line(cli, rx_buf=rx_buf)
            if not resp_txt:
                return {
                    "id": req_id,
                    "ok": False,
                    "transport_ok": False,
                    "op_ok": False,
                    "bridge_active": False,
                    "error": "Empty response from live bridge helper",
                }
            try:
                parsed = json.loads(resp_txt)
            except ValueError:
                stale_discarded += 1
                continue
            if not isinstance(parsed, dict):
                stale_discarded += 1
                continue
            cand_id = parsed.get("id")
            if cand_id is None:
                if parsed.get("ok") is False:
                    parsed["id"] = req_id
                    parsed["transport_ok"] = False
                    parsed["op_ok"] = False
                    parsed["bridge_active"] = True
                    return parsed
                stale_discarded += 1
                continue
            if str(cand_id) != req_id:
                stale_discarded += 1
                continue

            parsed = _normalize_bridge_response(parsed, default_id=req_id)
            parsed["bridge_active"] = True
            if stale_discarded > 0:
                parsed["client_stale_discarded"] = stale_discarded
            return parsed
    except Exception as exc:
        return {
            "id": req_id,
            "ok": False,
            "transport_ok": False,
            "op_ok": False,
            "bridge_active": False,
            "error": str(exc),
        }
    finally:
        if cli is not None:
            try:
                cli.close()
            except Exception:
                pass


def is_bridge_active(socket_dir=None, timeout=2.0):
    res = send_bridge_request('(strcat "pong:" (sprintf nil "%d" (ipcGetPid)))', socket_dir=socket_dir, timeout=timeout)
    return bool(res.get("ok") and str(res.get("result", "")).startswith("pong:"))


# ---------------------------------------------------------------------------
# Helper Daemon (`--start-helper`, spawned by `ic617_live_bridge.il`)
# ---------------------------------------------------------------------------

def run_socket_helper(socket_dir=None):
    paths = resolve_bridge_paths(socket_dir=socket_dir)
    _ensure_private_dir(paths["dir"])

    if os.path.exists(paths["sock"]):
        if is_bridge_active(socket_dir=paths["dir"], timeout=1.0):
            sys.stderr.write("[SA-BRIDGE-ERROR] Live bridge already active at %s\n" % paths["sock"])
            sys.stderr.flush()
            return 1
        try:
            os.unlink(paths["sock"])
        except OSError:
            pass

    session_token = binascii.hexlify(os.urandom(24)).decode("ascii")
    _write_private_file(paths["token"], _to_bytes(session_token + "\n"))

    use_af_unix = hasattr(socket, "AF_UNIX")
    if use_af_unix:
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(paths["sock"])
        try:
            os.chmod(paths["sock"], _MODE_0600)
        except OSError:
            pass
        srv.listen(8)
        transport = "unix"
    else:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        port = srv.getsockname()[1]
        srv.listen(8)
        _write_private_file(paths["sock"], _to_bytes("tcp://127.0.0.1:%d\n" % port))
        transport = "tcp-loopback-fallback"

    started_at = time.time()
    meta = {
        "helper_pid": os.getpid(),
        "virtuoso_pid": int(os.environ.get("SA_VIRTUOSO_PID", "0") or 0),
        "virtuoso_cwd": os.environ.get("SA_VIRTUOSO_CWD", ""),
        "user": paths["user"],
        "sock": paths["sock"],
        "transport": transport,
        "started_at": started_at,
        "version": RELEASE_VERSION,
    }
    _write_private_file(paths["meta"], _to_bytes(json.dumps(meta, indent=2, sort_keys=True) + "\n"))

    stop_state = {"stop": False}

    def _handle_sig(signum, frame):
        stop_state["stop"] = True

    for sig_name in ("SIGINT", "SIGTERM"):
        if hasattr(signal, sig_name):
            try:
                signal.signal(getattr(signal, sig_name), _handle_sig)
            except Exception:
                pass

    # Line reader synchronized with Virtuoso IPC stdout->helper stdin
    stdin_lines = []
    stdin_cond = threading.Condition()

    def _stdin_reader():
        try:
            while not stop_state["stop"]:
                raw_line = sys.stdin.readline()
                if not raw_line:
                    stdin_cond.acquire()
                    try:
                        stop_state["stop"] = True
                        stdin_cond.notify_all()
                    finally:
                        stdin_cond.release()
                    break
                txt = _to_text(raw_line).strip()
                if not txt:
                    continue
                stdin_cond.acquire()
                try:
                    stdin_lines.append(txt)
                    stdin_cond.notify_all()
                finally:
                    stdin_cond.release()
        except Exception:
            stdin_cond.acquire()
            try:
                stop_state["stop"] = True
                stdin_cond.notify_all()
            finally:
                stdin_cond.release()

    reader_thread = threading.Thread(target=_stdin_reader)
    reader_thread.daemon = True
    reader_thread.start()

    srv.settimeout(0.25)
    sys.stderr.write("[SA-BRIDGE-READY] pid=%d sock=%s\n" % (os.getpid(), paths["sock"]))
    sys.stderr.flush()

    req_seq = 0
    try:
        while not stop_state["stop"]:
            try:
                if use_af_unix and os.name == "posix":
                    rlist, _, _ = select.select([srv], [], [], 0.25)
                    if not rlist:
                        continue
                conn, _ = srv.accept()
            except socket.timeout:
                continue
            except select.error:
                continue
            except socket.error as s_err:
                if getattr(s_err, "errno", None) == errno.EINTR:
                    continue
                if stop_state["stop"]:
                    break
                continue

            rid = None
            try:
                conn.settimeout(30.0)
                raw_req = _recv_line(conn)
                if not raw_req:
                    conn.close()
                    continue
                try:
                    req_obj = json.loads(raw_req)
                except ValueError:
                    conn.sendall(_to_bytes(json.dumps({"ok": False, "transport_ok": False, "op_ok": False, "error": "Invalid JSON request"}) + "\n"))
                    conn.close()
                    continue

                if not isinstance(req_obj, dict):
                    conn.sendall(_to_bytes(json.dumps({"ok": False, "transport_ok": False, "op_ok": False, "error": "Request payload must be JSON object"}) + "\n"))
                    conn.close()
                    continue

                req_seq += 1
                rid = str(req_obj.get("id") or ("r%d" % req_seq)).replace(" ", "_")

                if not _constant_time_eq(req_obj.get("token", ""), session_token):
                    conn.sendall(_to_bytes(json.dumps({"id": rid, "ok": False, "transport_ok": False, "op_ok": False, "error": "Authentication failed: invalid session token"}) + "\n"))
                    conn.close()
                    continue

                cmd_str = req_obj.get("cmd", "")
                if not isinstance(cmd_str, TEXT_TYPES) or not cmd_str.strip():
                    conn.sendall(_to_bytes(json.dumps({"id": rid, "ok": False, "transport_ok": False, "op_ok": False, "error": "Non-empty SKILL cmd required"}) + "\n"))
                    conn.close()
                    continue

                req_timeout = float(req_obj.get("timeout", 60.0))
                if req_timeout <= 0.0:
                    req_timeout = 0.001
                conn.settimeout(max(5.0, req_timeout + 5.0))

                hex_cmd = binascii.hexlify(_to_bytes(cmd_str)).decode("ascii")

                stdin_cond.acquire()
                try:
                    del stdin_lines[:]
                finally:
                    stdin_cond.release()

                sys.stdout.write("REQ %s %s\n" % (rid, hex_cmd))
                sys.stdout.flush()

                deadline = time.time() + req_timeout
                matched_obj = None
                stale_discarded = 0

                stdin_cond.acquire()
                try:
                    while matched_obj is None and not stop_state["stop"]:
                        while stdin_lines:
                            cand_line = stdin_lines.pop(0)
                            try:
                                cand_obj = json.loads(cand_line)
                            except ValueError:
                                stale_discarded += 1
                                continue
                            if not isinstance(cand_obj, dict):
                                stale_discarded += 1
                                continue
                            cand_id = cand_obj.get("id")
                            if cand_id is None or str(cand_id) != rid:
                                stale_discarded += 1
                                continue
                            matched_obj = cand_obj
                            break
                        if matched_obj is not None or stop_state["stop"]:
                            break
                        rem = deadline - time.time()
                        if rem <= 0.0:
                            break
                        stdin_cond.wait(min(0.25, rem))
                finally:
                    stdin_cond.release()

                if matched_obj is None:
                    err_msg = "Virtuoso IPC closed" if stop_state["stop"] else "Timed out waiting for Virtuoso CIW evaluation"
                    conn.sendall(_to_bytes(json.dumps({
                        "id": rid,
                        "transport_ok": False,
                        "op_ok": False,
                        "ok": False,
                        "error": err_msg,
                    }) + "\n"))
                else:
                    norm_obj = _normalize_bridge_response(matched_obj, default_id=rid)
                    if stale_discarded > 0:
                        norm_obj["stale_replies_discarded"] = stale_discarded
                    conn.sendall(_to_bytes(json.dumps(norm_obj) + "\n"))
            except Exception as c_err:
                try:
                    conn.sendall(_to_bytes(json.dumps({
                        "id": rid,
                        "transport_ok": False,
                        "op_ok": False,
                        "ok": False,
                        "error": str(c_err),
                    }) + "\n"))
                except Exception:
                    pass
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
    finally:
        try:
            srv.close()
        except Exception:
            pass
        for p_key in ("sock", "token", "meta"):
            try:
                if os.path.exists(paths[p_key]):
                    os.unlink(paths[p_key])
            except OSError:
                pass
    return 0


# ---------------------------------------------------------------------------
# Built-in SKILL Command Builders
# ---------------------------------------------------------------------------

def _skill_open_or_active_expr(lib, cell, view, mode, body_with_cv):
    """Build SKILL code that reuses `geGetEditCellView()` when matching, or opens safely in `unwindProtect`."""
    if not lib and not cell:
        return (
            "let((cv) "
            "cv = if(isCallable('geGetEditCellView) geGetEditCellView() nil) "
            "when(!cv && isCallable('geGetWindowCellView) cv = geGetWindowCellView()) "
            'unless(cv error("No active schematic cellView in Virtuoso GUI; pass --lib and --cell\\n")) '
            "%s)" % body_with_cv
        )
    v_str = view or "schematic"
    return (
        "let((cv activeCv opened) "
        "activeCv = if(isCallable('geGetEditCellView) geGetEditCellView() nil) "
        "if(activeCv && activeCv~>libName == %s && activeCv~>cellName == %s && activeCv~>viewName == %s then "
        "  cv = activeCv "
        "  opened = nil "
        "else "
        "  cv = dbOpenCellViewByType(%s %s %s \"\" %s) "
        '  unless(cv error("Cannot open cellView %%s/%%s/%%s in mode %%s\\n" %s %s %s %s)) '
        "  opened = t "
        ") "
        "unwindProtect(progn(%s) when(opened && cv errset(dbClose(cv) nil))))" % (
            _skill_quote(lib), _skill_quote(cell), _skill_quote(v_str),
            _skill_quote(lib), _skill_quote(cell), _skill_quote(v_str), _skill_quote(mode),
            _skill_quote(lib), _skill_quote(cell), _skill_quote(v_str), _skill_quote(mode),
            body_with_cv,
        )
    )


def cmd_ping(socket_dir=None, timeout=30.0):
    expr = (
        'sprintf(nil "{\\"pong\\": true, \\"virtuoso_pid\\": %d, \\"cwd\\": %s, \\"version\\": %s}" '
        "(ipcGetPid) (saJsonScalar (getWorkingDir)) "
        '(saJsonScalar (if (isCallable \'getVersion) (getVersion t) "IC617")))'
    )
    resp = send_bridge_request(expr, socket_dir=socket_dir, timeout=timeout)
    if resp.get("ok") and isinstance(resp.get("result"), TEXT_TYPES):
        try:
            resp["info"] = json.loads(resp["result"])
        except Exception:
            pass
    resp["command"] = "ping"
    return resp


def cmd_active_cv(socket_dir=None, timeout=30.0):
    expr = (
        "let((cv) "
        "cv = if(isCallable('geGetEditCellView) geGetEditCellView() nil) "
        "when(!cv && isCallable('geGetWindowCellView) cv = geGetWindowCellView()) "
        "if(cv then "
        '  sprintf(nil "{\\"lib\\": %s, \\"cell\\": %s, \\"view\\": %s, \\"mode\\": %s}" '
        "    (saJsonScalar cv~>libName) (saJsonScalar cv~>cellName) "
        "    (saJsonScalar cv~>viewName) (saJsonScalar cv~>mode)) "
        'else "null"))'
    )
    resp = send_bridge_request(expr, socket_dir=socket_dir, timeout=timeout)
    if resp.get("ok") and isinstance(resp.get("result"), TEXT_TYPES):
        try:
            resp["active_cellview"] = json.loads(resp["result"])
        except Exception:
            resp["active_cellview"] = None
    resp["command"] = "active-cv"
    return resp


def cmd_dump_json(lib=None, cell=None, view="schematic", out_path=None, socket_dir=None, timeout=60.0):
    out_arg = _skill_quote(os.path.abspath(out_path)) if out_path else "nil"
    body = "saDumpSchematicJson(cv nil)"
    if out_path:
        body = "progn(saDumpSchematicJson(cv %s) saSerializeSchematicJson(cv))" % out_arg
    expr = _skill_open_or_active_expr(lib, cell, view, "r", body)
    resp = send_bridge_request(expr, socket_dir=socket_dir, timeout=timeout)
    if resp.get("ok") and isinstance(resp.get("result"), TEXT_TYPES):
        try:
            resp["schematic"] = json.loads(resp["result"])
            del resp["result"]
        except Exception:
            pass
    if out_path and resp.get("ok"):
        resp["out_path"] = os.path.abspath(out_path)
    resp["command"] = "dump-json"
    return resp


def cmd_set_param(inst_name, param_pairs, order=None, lib=None, cell=None, view="schematic", socket_dir=None, timeout=60.0):
    skill_pairs = " ".join(
        "(list %s %s)" % (_skill_quote(k), _skill_quote(v)) for k, v in param_pairs
    )
    order_names = order if order else [k for k, _ in param_pairs]
    skill_order = " ".join(_skill_quote(k) for k in order_names)
    if lib or cell:
        body = (
            "let((inst cs okFlag savedFlag errsCnt) "
            "inst = dbFindAnyInstByName(cv %s) "
            'unless(inst error("Instance %%s not found in %%s/%%s\\n" %s cv~>libName cv~>cellName)) '
            "saApplyInstCdfCallbacks(inst (list %s) (list %s)) "
            "okFlag = t "
            "savedFlag = nil "
            "errsCnt = 0 "
            "if(opened then "
            "  cs = saCheckAndSave(cv nil) "
            "  errsCnt = car(cs) "
            "  savedFlag = (caddr(cs) != nil) "
            "  okFlag = (errsCnt == 0 && savedFlag) "
            "else "
            "  when(isCallable('hiRedraw) errset(hiRedraw() nil)) "
            ") "
            'sprintf(nil "{\\"ok\\": %%s, \\"inst\\": %%s, \\"updated\\": true, \\"check_errors\\": %%d, \\"saved\\": %%s}" '
            "  (saJsonBool okFlag) (saJsonScalar inst~>name) errsCnt (saJsonBool savedFlag)))" % (
                _skill_quote(inst_name),
                _skill_quote(inst_name),
                skill_pairs,
                skill_order,
            )
        )
    else:
        body = (
            "let((inst) "
            "inst = dbFindAnyInstByName(cv %s) "
            'unless(inst error("Instance %%s not found in %%s/%%s\\n" %s cv~>libName cv~>cellName)) '
            "saApplyInstCdfCallbacks(inst (list %s) (list %s)) "
            "when(isCallable('hiRedraw) errset(hiRedraw() nil)) "
            'sprintf(nil "{\\"ok\\": true, \\"inst\\": %%s, \\"updated\\": true}" (saJsonScalar inst~>name)))' % (
                _skill_quote(inst_name),
                _skill_quote(inst_name),
                skill_pairs,
                skill_order,
            )
        )
    expr = _skill_open_or_active_expr(lib, cell, view, "a", body)
    resp = send_bridge_request(expr, socket_dir=socket_dir, timeout=timeout)
    if isinstance(resp.get("result"), TEXT_TYPES):
        try:
            resp["update"] = json.loads(resp["result"])
        except Exception:
            pass
    resp["command"] = "set-param"
    return resp


def cmd_check_save(lib=None, cell=None, view="schematic", out_path=None, socket_dir=None, timeout=60.0):
    out_arg = _skill_quote(os.path.abspath(out_path)) if out_path else "nil"
    body = (
        "let((r) "
        "r = saCheckAndSave(cv %s) "
        "if(length(r) >= 4 then nth(3 r) else "
        'sprintf(nil "{\\"ok\\": %%s, \\"lib\\": %%s, \\"cell\\": %%s, \\"view\\": %%s, \\"check_errors\\": %%d, \\"check_warnings\\": %%d, \\"saved\\": %%s}" '
        "  (saJsonBool (and (equal (car r) 0) (nequal (caddr r) nil))) "
        "  (saJsonScalar cv~>libName) (saJsonScalar cv~>cellName) (saJsonScalar cv~>viewName) "
        "  (car r) (cadr r) (saJsonBool (nequal (caddr r) nil)))))" % out_arg
    )
    expr = _skill_open_or_active_expr(lib, cell, view, "a", body)
    resp = send_bridge_request(expr, socket_dir=socket_dir, timeout=timeout)
    if isinstance(resp.get("result"), TEXT_TYPES):
        try:
            resp["check_save"] = json.loads(resp["result"])
        except Exception:
            pass
    resp["command"] = "check-save"
    return resp


def cmd_export_png(out_png, lib=None, cell=None, view="schematic", width=2600, height=1700, socket_dir=None, timeout=60.0):
    abs_png = os.path.abspath(out_png)
    if lib and cell:
        expr = "saExportSchematicPng(%s %s %s %s %d %d)" % (
            _skill_quote(lib), _skill_quote(cell), _skill_quote(view or "schematic"),
            _skill_quote(abs_png), int(width), int(height),
        )
    else:
        expr = (
            "let((cv) "
            "cv = if(isCallable('geGetEditCellView) geGetEditCellView() nil) "
            "when(!cv && isCallable('geGetWindowCellView) cv = geGetWindowCellView()) "
            'unless(cv error("No active schematic window; specify --lib and --cell\\n")) '
            "saExportSchematicPng(cv~>libName cv~>cellName cv~>viewName %s %d %d))" % (
                _skill_quote(abs_png), int(width), int(height),
            )
        )
    resp = send_bridge_request(expr, socket_dir=socket_dir, timeout=timeout)
    if resp.get("ok"):
        resp["png_path"] = abs_png
    resp["command"] = "export-png"
    return resp


# ---------------------------------------------------------------------------
# Self-Test Suite (`--self-test`)
# ---------------------------------------------------------------------------

def _check_skill_syntax_and_contracts():
    """Verify balanced delimiters/strings, pure LF, and safety contracts on SKILL files."""
    bridge_il = os.path.join(_TOOLS_DIR, "ic617_live_bridge.il")
    oa_il = os.path.join(_TOOLS_DIR, "ic617_oa_cdf.il")
    for fpath in (bridge_il, oa_il):
        if not os.path.isfile(fpath):
            raise AssertionError("Missing companion SKILL file: " + fpath)
        fh = open(fpath, "rb")
        try:
            raw = fh.read()
        finally:
            fh.close()
        if b"\r" in raw:
            raise AssertionError("CR byte found in SKILL file: " + fpath)
        txt = raw.decode("utf-8")
        if RELEASE_VERSION not in txt:
            raise AssertionError("Release version %s missing in %s" % (RELEASE_VERSION, fpath))

        # Check balanced parentheses and double quotes ignoring `;` line comments
        depth = 0
        in_str = False
        in_comment = False
        esc = False
        for ch in txt:
            if in_comment:
                if ch == "\n":
                    in_comment = False
                continue
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == ";":
                in_comment = True
            elif ch == '"':
                in_str = True
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth < 0:
                    raise AssertionError("Unbalanced closing ')' in " + fpath)
        if in_str or depth != 0:
            raise AssertionError("Unbalanced SKILL syntax in %s (in_str=%s, depth=%d)" % (fpath, in_str, depth))

    fh_b = open(bridge_il, "rb")
    try:
        b_txt = fh_b.read().decode("utf-8")
    finally:
        fh_b.close()
    if "saBridgeJsonResultHasOkFalse" not in b_txt or '\\"transport_ok\\": true, \\"op_ok\\":' not in b_txt:
        raise AssertionError("ic617_live_bridge.il missing semantic op_ok JSON inspection")

    fh_o = open(oa_il, "rb")
    try:
        o_txt = fh_o.read().decode("utf-8")
    finally:
        fh_o.close()
    if "saBackupExistingView failed to create verified backup" not in o_txt:
        raise AssertionError("ic617_oa_cdf.il missing verified backup error guard")
    if "when(errs == 0" not in o_txt or "saCollectSchErrorMarkersJson" not in o_txt:
        raise AssertionError("ic617_oa_cdf.il missing errs == 0 save gate or error marker collector")


def run_self_test():
    checks = []
    tmp_root = tempfile.mkdtemp(prefix="sa_ic617_client_test_")
    helper_proc = None
    try:
        # 1. Verify SKILL companion contracts
        _check_skill_syntax_and_contracts()
        checks.append("skill_files_contracts_ok")

        # 2. Client-side payload `timeout`, socket `timeout + 2.0`, and buffered stale-ID discard
        direct_dir = os.path.join(tmp_root, "direct_sock")
        paths_direct = resolve_bridge_paths(socket_dir=direct_dir)
        _ensure_private_dir(paths_direct["dir"])
        _write_private_file(paths_direct["token"], _to_bytes("tok_direct_123\n"))

        observed = {}
        use_unix = hasattr(socket, "AF_UNIX")
        if use_unix:
            dsrv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            dsrv.bind(paths_direct["sock"])
            dsrv.listen(2)
        else:
            dsrv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            dsrv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            dsrv.bind(("127.0.0.1", 0))
            dport = dsrv.getsockname()[1]
            dsrv.listen(2)
            _write_private_file(paths_direct["sock"], _to_bytes("tcp://127.0.0.1:%d\n" % dport))

        def _direct_srv_worker():
            conn, _ = dsrv.accept()
            try:
                line = _recv_line(conn)
                req = json.loads(line)
                observed["req"] = req
                # Send a stale mismatched ID frame AND the matching frame in ONE sendall()
                stale_frame = json.dumps({"id": "stale-999", "ok": True, "result": "STALE_BAD"}) + "\n"
                good_frame = json.dumps({"id": req["id"], "ok": True, "result": "FRESH_OK"}) + "\n"
                conn.sendall(_to_bytes(stale_frame + good_frame))
            finally:
                conn.close()
                dsrv.close()

        t_direct = threading.Thread(target=_direct_srv_worker)
        t_direct.daemon = True
        t_direct.start()

        orig_connect = _connect_client_socket
        recorded_timeouts = []

        def _spy_connect(sp, timeout=32.0):
            recorded_timeouts.append(timeout)
            return orig_connect(sp, timeout=timeout)

        globals()["_connect_client_socket"] = _spy_connect
        try:
            d_resp = send_bridge_request("(plus 20 22)", socket_dir=direct_dir, timeout=4.5)
        finally:
            globals()["_connect_client_socket"] = orig_connect
        t_direct.join(3.0)

        if abs(float(observed.get("req", {}).get("timeout", 0.0)) - 4.5) > 1e-6:
            raise AssertionError("Expected payload timeout=4.5, got %r" % observed.get("req"))
        if not recorded_timeouts or abs(recorded_timeouts[0] - 6.5) > 1e-6:
            raise AssertionError("Expected socket timeout=6.5 (timeout+2.0), got %r" % recorded_timeouts)
        if not d_resp.get("ok") or d_resp.get("result") != "FRESH_OK" or d_resp.get("client_stale_discarded") != 1:
            raise AssertionError("Client stale ID discard failed: %r" % d_resp)
        checks.append("client_timeout_and_stale_id_discard_ok")

        # 3. End-to-end `--start-helper` daemon + mock Virtuoso IPC responder
        live_dir = os.path.join(tmp_root, "live_sock")
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        helper_proc = subprocess.Popen(
            [sys.executable, "-B", "-u", os.path.realpath(__file__), "--start-helper", "--socket-dir", live_dir],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

        ready_ok = [False]
        ready_evt = threading.Event()

        def _stderr_watcher():
            while True:
                ln = helper_proc.stderr.readline()
                if not ln:
                    break
                txt = _to_text(ln)
                if "[SA-BRIDGE-READY]" in txt:
                    ready_ok[0] = True
                    ready_evt.set()

        t_err = threading.Thread(target=_stderr_watcher)
        t_err.daemon = True
        t_err.start()
        ready_evt.wait(5.0)
        if not ready_ok[0]:
            raise AssertionError("Helper failed to emit [SA-BRIDGE-READY]")

        def _ipc_mock_responder():
            while True:
                raw_ln = helper_proc.stdout.readline()
                if not raw_ln:
                    break
                ln = _to_text(raw_ln).strip()
                if not ln.startswith("REQ "):
                    continue
                parts = ln.split(" ", 2)
                rid = parts[1]
                cmd_txt = binascii.unhexlify(_to_bytes(parts[2])).decode("utf-8", "replace")

                if "TRIGGER_STALE_IPC" in cmd_txt:
                    # Emit two stale replies before the matching reply
                    s1 = json.dumps({"id": "old-timeout-1", "ok": True, "result": "WRONG_1"}) + "\n"
                    s2 = json.dumps({"id": "old-timeout-2", "ok": True, "result": "WRONG_2"}) + "\n"
                    helper_proc.stdin.write(_to_bytes(s1 + s2))
                    helper_proc.stdin.flush()
                    time.sleep(0.03)
                    good = json.dumps({"id": rid, "transport_ok": True, "op_ok": True, "ok": True, "result": "RECOVERED_AFTER_STALE"}) + "\n"
                    helper_proc.stdin.write(_to_bytes(good))
                    helper_proc.stdin.flush()
                elif "SEMANTIC_FAIL_JSON" in cmd_txt:
                    inner_fail = json.dumps({
                        "ok": False,
                        "check_errors": 2,
                        "saved": False,
                        "errors": [{"msg": "floating net", "severity": "error"}],
                    })
                    # Even if raw IPC marks ok=True without op_ok, helper + client must detect inner ok=false
                    reply = json.dumps({"id": rid, "ok": True, "result": inner_fail}) + "\n"
                    helper_proc.stdin.write(_to_bytes(reply))
                    helper_proc.stdin.flush()
                elif "NESTED_OK_TRUE_JSON" in cmd_txt:
                    inner_ok = json.dumps({"ok": True, "nested": {"ok": False}})
                    reply = json.dumps({"id": rid, "ok": True, "result": inner_ok}) + "\n"
                    helper_proc.stdin.write(_to_bytes(reply))
                    helper_proc.stdin.flush()
                elif "pong:" in cmd_txt:
                    reply = json.dumps({"id": rid, "ok": True, "result": "pong:4242"}) + "\n"
                    helper_proc.stdin.write(_to_bytes(reply))
                    helper_proc.stdin.flush()
                else:
                    reply = json.dumps({"id": rid, "ok": True, "result": "eval_ok"}) + "\n"
                    helper_proc.stdin.write(_to_bytes(reply))
                    helper_proc.stdin.flush()

        t_ipc = threading.Thread(target=_ipc_mock_responder)
        t_ipc.daemon = True
        t_ipc.start()

        if not is_bridge_active(socket_dir=live_dir, timeout=3.0):
            raise AssertionError("is_bridge_active returned False on live helper")

        r_stale = send_bridge_request("(TRIGGER_STALE_IPC)", socket_dir=live_dir, timeout=5.0)
        if not r_stale.get("ok") or r_stale.get("result") != "RECOVERED_AFTER_STALE" or r_stale.get("stale_replies_discarded") != 2:
            raise AssertionError("Helper stale stdin_lines discard failed: %r" % r_stale)
        checks.append("helper_stale_stdin_discard_ok")

        r_sem_fail = send_bridge_request("(SEMANTIC_FAIL_JSON)", socket_dir=live_dir, timeout=5.0)
        if r_sem_fail.get("ok") is not False or r_sem_fail.get("op_ok") is not False or r_sem_fail.get("transport_ok") is not True:
            raise AssertionError("Expected transport_ok=True, op_ok=False, ok=False; got %r" % r_sem_fail)
        checks.append("semantic_op_ok_false_propagation_ok")

        r_nested = send_bridge_request("(NESTED_OK_TRUE_JSON)", socket_dir=live_dir, timeout=5.0)
        if r_nested.get("ok") is not True or r_nested.get("op_ok") is not True:
            raise AssertionError("Nested ok=false caused false failure: %r" % r_nested)
        checks.append("nested_ok_true_preserved_ok")

        r_auth = send_bridge_request("(1+1)", socket_dir=live_dir, timeout=3.0, token_override="wrong_token")
        if r_auth.get("ok") is not False or "Authentication failed" not in str(r_auth.get("error", "")):
            raise AssertionError("Expected auth rejection, got %r" % r_auth)
        checks.append("token_auth_rejection_ok")

        # Close stdin to trigger graceful helper exit and socket cleanup
        helper_proc.stdin.close()
        helper_proc.wait()
        paths_live = resolve_bridge_paths(socket_dir=live_dir)
        if os.path.exists(paths_live["sock"]):
            raise AssertionError("Helper did not clean up socket file on exit")
        helper_proc = None
        checks.append("helper_graceful_cleanup_ok")

        return {
            "ok": True,
            "tool": "ic617_client",
            "version": RELEASE_VERSION,
            "checks_passed": len(checks),
            "checks": checks,
        }
    finally:
        if helper_proc is not None:
            try:
                helper_proc.stdin.close()
            except Exception:
                pass
            try:
                helper_proc.terminate()
                helper_proc.wait()
            except Exception:
                pass
        shutil.rmtree(tmp_root, ignore_errors=True)


HELP_TEXT = """Usage:
  python tools/ic617_client.py --start-helper [--socket-dir DIR]
  python tools/ic617_client.py --self-test
  python tools/ic617_client.py ping [--socket-dir DIR]
  python tools/ic617_client.py active-cv [--socket-dir DIR]
  python tools/ic617_client.py dump-json [--lib L --cell C [--view schematic]] [--out FILE]
  python tools/ic617_client.py set-param --inst M1 --param w=12u [--param fingers=4] [--order l,fingers,w,m] [--lib L --cell C]
  python tools/ic617_client.py check-save [--lib L --cell C [--view schematic]] [--out FILE]
  python tools/ic617_client.py export-png --out FILE [--lib L --cell C [--view schematic]] [--width 2600 --height 1700]
  python tools/ic617_client.py eval "<skill_expression>"
"""


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help", "help"):
        print(HELP_TEXT)
        return 0

    if "--self-test" in args or args[0] == "self-test":
        try:
            res = run_self_test()
            print(json.dumps(res, indent=2, sort_keys=True))
            return 0 if res.get("ok") else 1
        except Exception as exc:
            print(json.dumps({"ok": False, "tool": "ic617_client", "error": str(exc)}, indent=2, sort_keys=True))
            return 1

    if "--start-helper" in args:
        parser = _SilentOptionParser(add_help_option=False)
        parser.add_option("--start-helper", action="store_true", dest="start_helper", default=False)
        parser.add_option("--socket-dir", type="string", dest="socket_dir", default=None)
        try:
            opts, extra = parser.parse_args(args)
            if extra:
                raise ValueError("Unexpected extra arguments with --start-helper")
            return run_socket_helper(socket_dir=opts.socket_dir)
        except Exception as err:
            sys.stderr.write("[SA-BRIDGE-ERROR] %s\n" % str(err))
            sys.stderr.flush()
            return 2

    subcmd = args.pop(0)
    parser = _SilentOptionParser(add_help_option=False)
    parser.add_option("-h", "--help", action="store_true", dest="help", default=False)
    parser.add_option("--socket-dir", type="string", dest="socket_dir", default=None)
    parser.add_option("--lib", type="string", dest="lib", default=None)
    parser.add_option("--cell", type="string", dest="cell", default=None)
    parser.add_option("--view", type="string", dest="view", default="schematic")
    parser.add_option("--out", type="string", dest="out_path", default=None)
    parser.add_option("--inst", type="string", dest="inst", default=None)
    parser.add_option("--param", action="append", dest="params", default=[])
    parser.add_option("--order", type="string", dest="order", default=None)
    parser.add_option("--width", type="int", dest="width", default=2600)
    parser.add_option("--height", type="int", dest="height", default=1700)
    parser.add_option("--expr", type="string", dest="expr", default=None)
    parser.add_option("--timeout", type="float", dest="timeout", default=30.0)

    try:
        opts, pos = parser.parse_args(args)
    except ValueError as err:
        print(json.dumps({"command": subcmd, "ok": False, "error": str(err)}, indent=2, sort_keys=True))
        return 2

    if opts.help:
        print(HELP_TEXT)
        return 0

    try:
        if subcmd == "ping":
            res = cmd_ping(socket_dir=opts.socket_dir, timeout=opts.timeout)
        elif subcmd == "active-cv":
            res = cmd_active_cv(socket_dir=opts.socket_dir, timeout=opts.timeout)
        elif subcmd == "dump-json":
            res = cmd_dump_json(
                lib=opts.lib, cell=opts.cell, view=opts.view,
                out_path=opts.out_path, socket_dir=opts.socket_dir, timeout=opts.timeout,
            )
        elif subcmd == "set-param":
            if not opts.inst or not opts.params:
                raise ValueError("set-param requires --inst NAME and at least one --param KEY=VALUE")
            pairs = []
            for raw_p in opts.params:
                if "=" not in raw_p:
                    raise ValueError("Invalid --param %s (expected KEY=VALUE)" % repr(raw_p))
                k, v = raw_p.split("=", 1)
                pairs.append((k.strip(), v.strip()))
            order_list = [x.strip() for x in opts.order.split(",") if x.strip()] if opts.order else None
            res = cmd_set_param(
                opts.inst, pairs, order=order_list,
                lib=opts.lib, cell=opts.cell, view=opts.view,
                socket_dir=opts.socket_dir, timeout=opts.timeout,
            )
        elif subcmd == "check-save":
            res = cmd_check_save(
                lib=opts.lib, cell=opts.cell, view=opts.view,
                out_path=opts.out_path, socket_dir=opts.socket_dir, timeout=opts.timeout,
            )
        elif subcmd == "export-png":
            if not opts.out_path:
                raise ValueError("export-png requires --out PNG_PATH")
            res = cmd_export_png(
                opts.out_path, lib=opts.lib, cell=opts.cell, view=opts.view,
                width=opts.width, height=opts.height,
                socket_dir=opts.socket_dir, timeout=opts.timeout,
            )
        elif subcmd == "eval":
            expr_txt = opts.expr if opts.expr is not None else (" ".join(pos) if pos else "")
            if not expr_txt.strip():
                raise ValueError("eval requires a SKILL expression")
            res = send_bridge_request(expr_txt, socket_dir=opts.socket_dir, timeout=opts.timeout)
            res["command"] = "eval"
        else:
            print(json.dumps({"ok": False, "error": "Unknown subcommand: " + subcmd}, indent=2, sort_keys=True))
            return 2

        print(json.dumps(res, indent=2, sort_keys=True))
        return 0 if res.get("ok") else 1
    except ValueError as verr:
        print(json.dumps({"command": subcmd, "ok": False, "error": str(verr)}, indent=2, sort_keys=True))
        return 2
    except Exception as exc:
        print(json.dumps({"command": subcmd, "ok": False, "error": str(exc)}, indent=2, sort_keys=True))
        return 1


if __name__ == "__main__":
    sys.exit(main())
