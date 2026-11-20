#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Safe Cadence IC617 / Spectre 15.1 Subprocess Wrapper for Codex on RHEL 6.5.

Managed by SKILL-ANALOG (release 2026.11.19.1).
100% Python 2.6.6+ and Python 3 standard-library compatible (`optparse`, zero external deps).

Supported tools:
  spectre        — Runs Spectre netlist with `-format psfascii` into `<project>/sim/runs/<run-id>/psf`
  ocean          — Runs `ocean -nograph -restore <script.ocn>`
  virtuoso-batch — Runs `virtuoso -nograph -restore <script.il>` (auto-routes via
                   `ic617_client.py` live CIW bridge when active or when `.cdslck` locks exist!)
  si             — Runs `si <run_dir> -batch -command netlist`

Guarantees:
  - Automatically sources `$HOME/cadence/env.sh` and exports `CDS_Netlisting_Mode=Analog`
  - Enforces output isolation inside `<project>/sim/runs/<run-id>/` (`cwd=run_dir`, never inside `SKILL-ANALOG`)
  - Prevents stale PSF mixing: blocks reusing non-empty `run_dir` unless `--overwrite-run` is passed
  - Enforces disk/PSF hygiene: blocks Spectre launch when free disk < `--min-free-mb`, warns on
    unfiltered `save=all` waveform decks, and prunes old `psf/` directories via `prune-runs`
  - Recursively parses `cds.lib` (`INCLUDE`, `SOFTINCLUDE`, `DEFINE`, `UNDEFINE`, `ASSIGN`) and matches
    `.cdslck` locks via relative OA library segments (`<cell>/<view>/...`)
  - Propagates semantic `op_ok: false` when live bridge SKILL evaluation returns JSON `{"ok": false}`
"""
from __future__ import division, print_function

import binascii
import ctypes
import errno
import hashlib
import json
import os
from optparse import OptionParser
import re
import shutil
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
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

import ic617_client  # noqa: E402

VALID_TOOLS = ("spectre", "ocean", "virtuoso-batch", "si")
_RUN_ID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$')
_ENV_VAR_RE = re.compile(r'\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)')
_READONLY_SYSTEM_PREFIXES = ("/opt/", "/home/disk/eda/apps/")
_PARASITIC_RC_NAME_RE = re.compile(
    r'(?:^|[./:\s(])(?:'
    r'(?:cpar|rpar|c_par|r_par|c_pex|r_pex|cpex|rpex|c_qrc|r_qrc|cqrc|rqrc|c_rcx|r_rcx|crcx|rrcx|c_ext|r_ext|avc|avr|parasitic_[rc])\w*'
    r'|[rc]_(?:net|n)\d+\w*'
    r'|[rc]_\d+_\d+'
    r'|[rc]\d+[#$]\d+\w*'
    r')(?:$|[./:\s)])',
    re.IGNORECASE,
)
_PEX_VIEW_MARKER_RE = re.compile(
    r'(?:view(?:\s*name)?|cellview|extracted|extractor|simulator|tool|program|netlist|subckt|include|library)\b[^;\r\n]*\b(?:av_extracted|calibre|quantus|qrc|rcx|pex)\b',
    re.IGNORECASE,
)
_PEX_TOKEN_RE = re.compile(r'(?:^|[^a-z0-9_])(?:av_extracted|calibre|quantus|qrc|rcx|pex)(?:$|[^a-z0-9_])', re.IGNORECASE)
_MC_STMT_RE = re.compile(r'(?<![A-Za-z0-9_])montecarlo(?![A-Za-z0-9_])', re.IGNORECASE)
_MC_NUMRUNS_RE = re.compile(r'(?<![A-Za-z0-9_])numruns\s*=\s*(\d+)', re.IGNORECASE)
_NETLIST_SECTION_RE = re.compile(r'(?<![A-Za-z0-9_])section\s*=\s*["\']?([A-Za-z0-9_.-]+)["\']?', re.IGNORECASE)
_NETLIST_TEMP_RE = re.compile(r'(?<![A-Za-z0-9_])temp\s*=\s*([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)', re.IGNORECASE)
_BLOCK_COMMENT_RE = re.compile(r'/\*.*?\*/', re.DOTALL)
_LINE_CONT_RE = re.compile(r'\\\r?\n')
_CORNER_PREFIX_RE = re.compile(r'^(tt|nn|ss|ff|fs|sf)(?:$|[_.\s-])', re.IGNORECASE)

_RUN_SEQ_LOCK = threading.Lock()
_RUN_SEQ = [0]


class _SilentOptionParser(OptionParser):
    def error(self, msg):
        raise ValueError(msg)


def _inside_path(path, base):
    rp = os.path.normcase(os.path.realpath(path))
    rb = os.path.normcase(os.path.realpath(base))
    return rp == rb or rp.startswith(rb.rstrip(os.sep) + os.sep)


def _shell_quote(value):
    s = str(value)
    return "'" + s.replace("'", "'\"'\"'") + "'"


def _mkdir_p(path):
    if os.path.isdir(path):
        return
    try:
        os.makedirs(path)
    except OSError as err:
        if err.errno != errno.EEXIST or not os.path.isdir(path):
            raise


def _next_run_seq():
    _RUN_SEQ_LOCK.acquire()
    try:
        _RUN_SEQ[0] += 1
        return _RUN_SEQ[0]
    finally:
        _RUN_SEQ_LOCK.release()


def discover_project_root(start_dir=None):
    cur = os.path.abspath(start_dir or os.getcwd())
    if os.path.isfile(cur):
        cur = os.path.dirname(cur)
    if not os.path.isdir(cur):
        raise ValueError("Project search path does not exist: " + cur)

    fallback = None
    probe = cur
    while True:
        has_proj = os.path.isfile(os.path.join(probe, "project.json"))
        has_cds = os.path.isfile(os.path.join(probe, "cds.lib"))
        if has_proj:
            root = os.path.realpath(probe)
            break
        if has_cds and fallback is None:
            fallback = os.path.realpath(probe)
        parent = os.path.dirname(probe)
        if parent == probe:
            root = fallback
            break
        probe = parent

    if not root:
        raise ValueError(
            "Cannot locate Cadence project root (no project.json or cds.lib found from %s)" % cur
        )
    if _inside_path(root, _LIBRARY_ROOT):
        raise ValueError("Refusing to run simulations inside SKILL-ANALOG library: " + root)
    return root


def prepare_run_dir(project_root, run_id=None, tool_name="run", overwrite_run=False, dry_run=False):
    if not run_id:
        now = time.time()
        usec = int((now - int(now)) * 1000000)
        ts = time.strftime("%Y%m%d_%H%M%S", time.localtime(now))
        clean_tool = re.sub(r'[^A-Za-z0-9_]', '_', tool_name)
        seq = _next_run_seq()
        run_id = "%s_%06d_%s_%d_%d" % (ts, usec, clean_tool, os.getpid() % 10000, seq)
    if not _RUN_ID_RE.match(run_id) or ".." in run_id:
        raise ValueError("Unsafe --run-id %s (use alphanumeric, '_', '-', '.')" % repr(run_id))

    runs_base = os.path.join(project_root, "sim", "runs")
    run_dir = os.path.abspath(os.path.join(runs_base, run_id))
    if not _inside_path(run_dir, runs_base) or os.path.normcase(os.path.realpath(run_dir)) == os.path.normcase(os.path.realpath(runs_base)):
        raise ValueError("Run directory escapes <project>/sim/runs: " + run_dir)
    if _inside_path(run_dir, _LIBRARY_ROOT):
        raise ValueError("Run directory cannot reside inside SKILL-ANALOG library: " + run_dir)

    if not dry_run and os.path.exists(run_dir):
        if not os.path.isdir(run_dir):
            raise ValueError("Run path already exists and is not a directory: " + run_dir)
        if os.listdir(run_dir) and not overwrite_run:
            raise ValueError(
                "Run directory already exists and is non-empty (pass --overwrite-run to clean and reuse): "
                + run_dir
            )
    return run_id, run_dir


def _clean_run_dir_for_overwrite(run_dir, project_root, keep_paths=None):
    """Wipe stale `psf/`, logs, and simulation scratch outputs inside `run_dir` when `--overwrite-run` is active."""
    runs_base = os.path.join(project_root, "sim", "runs")
    if not _inside_path(run_dir, runs_base) or _inside_path(run_dir, _LIBRARY_ROOT):
        raise ValueError("Refusing to clean path outside <project>/sim/runs: " + run_dir)
    if os.path.normcase(os.path.realpath(run_dir)) == os.path.normcase(os.path.realpath(runs_base)):
        raise ValueError("Refusing to clean base runs directory: " + run_dir)
    if not os.path.isdir(run_dir):
        return

    keep_real = set()
    for kp in (keep_paths or []):
        if kp and os.path.exists(kp):
            keep_real.add(os.path.normcase(os.path.realpath(kp)))

    for entry in os.listdir(run_dir):
        full_entry = os.path.join(run_dir, entry)
        real_entry = os.path.normcase(os.path.realpath(full_entry))
        if real_entry in keep_real:
            continue
        if os.path.isdir(full_entry) and not os.path.islink(full_entry):
            shutil.rmtree(full_entry)
        else:
            os.unlink(full_entry)


def _format_cds_lib_path(path):
    """Format a `cds.lib` path token: unquoted unless whitespace is present."""
    s = str(path)
    if any(ch.isspace() for ch in s):
        return '"%s"' % s.replace('"', '\\"')
    return s


def _ensure_run_dir_cds_lib(project_root, run_dir):
    """Write a 1-line `INCLUDE <project_root>/cds.lib` into `<run_dir>/cds.lib` if needed."""
    proj_cds = os.path.join(project_root, "cds.lib")
    run_cds = os.path.join(run_dir, "cds.lib")
    if os.path.isfile(proj_cds) and not os.path.exists(run_cds):
        inc_line = "INCLUDE %s\n" % _format_cds_lib_path(proj_cds)
        fh = open(run_cds, "wb")
        try:
            fh.write(inc_line.encode("utf-8"))
        finally:
            fh.close()
        return run_cds
    return run_cds if os.path.isfile(run_cds) else None


_WAVEFORM_ANALYSIS_RE = re.compile(
    r'^\s*[A-Za-z0-9_.$]+\s+(?:\([^)]*\)\s+)?\b(tran|ac|stb|pstb|noise|pnoise|pss|pac)\b',
    re.IGNORECASE,
)
_OPTIONS_SAVE_RE = re.compile(r'(?<![A-Za-z0-9_])options\b[^\r\n]*?\bsave\s*=\s*([A-Za-z0-9_]+)', re.IGNORECASE)
_SAVE_STMT_RE = re.compile(r'^\s*save\s+\S', re.IGNORECASE)


def _get_free_disk_bytes(path):
    """Return available free disk bytes for `path` (POSIX statvfs + Windows GetDiskFreeSpaceExW), or None."""
    probe = os.path.abspath(path or os.getcwd())
    while probe and (not os.path.exists(probe)):
        parent = os.path.dirname(probe)
        if parent == probe:
            break
        probe = parent
    if not os.path.exists(probe):
        return None
    if hasattr(os, "statvfs"):
        try:
            st = os.statvfs(probe)
            return int(st.f_bavail) * int(st.f_frsize)
        except Exception:
            return None
    if os.name == "nt":
        try:
            free_avail = ctypes.c_ulonglong(0)
            total_bytes = ctypes.c_ulonglong(0)
            total_free = ctypes.c_ulonglong(0)
            u_probe = probe if isinstance(probe, type(u"")) else probe.decode("utf-8", "replace")
            ok = ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                ctypes.c_wchar_p(u_probe),
                ctypes.byref(free_avail),
                ctypes.byref(total_bytes),
                ctypes.byref(total_free),
            )
            if ok:
                return int(free_avail.value)
        except Exception:
            return None
    return None


def _dir_size_bytes(path):
    """Return total byte size of regular files inside `path` without following symlinks."""
    if not path or (not os.path.exists(path)) or os.path.islink(path):
        return 0
    if os.path.isfile(path):
        try:
            return int(os.path.getsize(path))
        except Exception:
            return 0
    total = 0
    for root, dirs, files in os.walk(path, followlinks=False):
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(root, d))]
        for fn in files:
            fp = os.path.join(root, fn)
            if os.path.islink(fp):
                continue
            try:
                total += int(os.path.getsize(fp))
            except Exception:
                pass
    return total


def _inspect_spectre_netlist_disk_hygiene(netlist_path):
    """Inspect a Spectre `.scs` deck for waveform analyses missing `options save=selected` / `save` filters."""
    out = {
        "has_waveform_analysis": False,
        "waveform_analyses": [],
        "has_save_selected": False,
        "has_save_stmt": False,
        "save_mode": None,
        "warnings": [],
    }
    if not netlist_path or (not os.path.isfile(netlist_path)):
        return out
    try:
        fh = open(netlist_path, "rb")
        try:
            raw = fh.read().decode("utf-8", "replace")
        finally:
            fh.close()
    except Exception:
        return out

    no_block = _BLOCK_COMMENT_RE.sub(" ", raw)
    joined = _LINE_CONT_RE.sub(" ", no_block)
    cleaned_lines = []
    found_wf = []
    seen_wf = set()
    for ln in joined.splitlines():
        s_ln = _strip_spectre_inline_comment(ln).strip()
        if not s_ln:
            continue
        cleaned_lines.append(s_ln)
        m_wf = _WAVEFORM_ANALYSIS_RE.match(s_ln)
        if m_wf:
            tok = m_wf.group(1).lower()
            if tok not in seen_wf:
                seen_wf.add(tok)
                found_wf.append(tok)
        if _SAVE_STMT_RE.match(s_ln):
            out["has_save_stmt"] = True

    cleaned_txt = "\n".join(cleaned_lines)
    last_save_mode = None
    for m_opt in _OPTIONS_SAVE_RE.finditer(cleaned_txt):
        last_save_mode = m_opt.group(1).strip().lower()

    out["waveform_analyses"] = found_wf
    out["has_waveform_analysis"] = bool(found_wf)
    out["save_mode"] = last_save_mode
    out["has_save_selected"] = bool(last_save_mode in ("selected", "lvl", "lvlpub"))

    if out["has_waveform_analysis"] and (not out["has_save_selected"]):
        out["warnings"].append(
            "Spectre deck runs waveform/sweep analyses (%s) in psfascii mode without "
            "`options save=selected`; unfiltered `save=all` waveforms can bloat PSF to 50-100 MB/point. "
            "Add `saveOptions options save=selected` and explicit `save <signals>` "
            "(MOS dcOpInfo still audits normally)." % ", ".join(found_wf)
        )
    elif out["has_waveform_analysis"] and out["has_save_selected"] and (not out["has_save_stmt"]):
        out["warnings"].append(
            "Spectre deck sets `options save=%s` without an explicit `save <signals>` statement; "
            "verify required waveform nodes/currents are explicitly saved." % (last_save_mode or "selected")
        )
    return out


def prune_project_runs(
    project_dir=None,
    keep=2,
    keep_run_ids=None,
    psf_only=True,
    min_psf_mb=0.0,
    dry_run=False,
):
    """Safely prune stale `psf/` data (or entire run dirs) under `<project>/sim/runs/`."""
    project_root = discover_project_root(project_dir or os.getcwd())
    runs_base = os.path.join(project_root, "sim", "runs")
    keep_n = max(0, int(keep))
    keep_set = set([str(k).strip() for k in (keep_run_ids or []) if str(k).strip()])
    min_bytes = max(0, int(round(float(min_psf_mb or 0.0) * 1024.0 * 1024.0)))

    if not os.path.isdir(runs_base):
        return {
            "ok": True,
            "tool": "prune-runs",
            "project_root": project_root,
            "runs_root": runs_base,
            "psf_only": bool(psf_only),
            "dry_run": bool(dry_run),
            "kept_runs": [],
            "pruned_count": 0,
            "freed_mb": 0.0,
            "runs_root_mb_before": 0.0,
            "runs_root_mb_after": 0.0,
            "pruned": [],
        }

    if _inside_path(runs_base, _LIBRARY_ROOT):
        raise ValueError("Refusing to prune inside SKILL-ANALOG library: " + runs_base)

    runs_mb_before = round(float(_dir_size_bytes(runs_base)) / (1024.0 * 1024.0), 3)

    run_entries = []
    for name in os.listdir(runs_base):
        full_p = os.path.join(runs_base, name)
        if os.path.islink(full_p) or (not os.path.isdir(full_p)):
            continue
        if not _inside_path(full_p, runs_base):
            continue
        if os.path.normcase(os.path.realpath(full_p)) == os.path.normcase(os.path.realpath(runs_base)):
            continue
        try:
            mtime = float(os.stat(full_p).st_mtime)
        except Exception:
            mtime = 0.0
        psf_p = os.path.join(full_p, "psf")
        if os.path.isdir(psf_p) and (not os.path.islink(psf_p)):
            try:
                p_mt = float(os.stat(psf_p).st_mtime)
                if p_mt > mtime:
                    mtime = p_mt
            except Exception:
                pass
        run_entries.append((mtime, name, full_p))

    run_entries.sort(key=lambda item: (item[0], item[1]))
    run_entries.reverse()

    kept_runs = []
    pruned = []
    freed_bytes = 0
    for idx, (_, name, full_p) in enumerate(run_entries):
        if idx < keep_n or (name in keep_set):
            kept_runs.append(name)
            continue
        target = os.path.join(full_p, "psf") if psf_only else full_p
        if not os.path.exists(target) or os.path.islink(target) or (not os.path.isdir(target)):
            continue
        if not _inside_path(target, runs_base) or _inside_path(target, _LIBRARY_ROOT):
            raise ValueError("Refusing to prune unsafe target: " + target)
        sz_bytes = _dir_size_bytes(target)
        if sz_bytes < min_bytes:
            kept_runs.append(name)
            continue
        if not dry_run:
            shutil.rmtree(target)
        freed_bytes += sz_bytes
        pruned.append({
            "run_id": name,
            "target": target,
            "freed_mb": round(float(sz_bytes) / (1024.0 * 1024.0), 3),
            "mode": "psf_only" if psf_only else "full_dir",
        })

    runs_mb_after = (
        round(max(0.0, runs_mb_before - float(freed_bytes) / (1024.0 * 1024.0)), 3)
        if dry_run
        else round(float(_dir_size_bytes(runs_base)) / (1024.0 * 1024.0), 3)
    )
    free_b = _get_free_disk_bytes(runs_base)
    out = {
        "ok": True,
        "tool": "prune-runs",
        "project_root": project_root,
        "runs_root": runs_base,
        "psf_only": bool(psf_only),
        "dry_run": bool(dry_run),
        "kept_runs": kept_runs,
        "pruned_count": len(pruned),
        "freed_mb": round(float(freed_bytes) / (1024.0 * 1024.0), 3),
        "runs_root_mb_before": runs_mb_before,
        "runs_root_mb_after": runs_mb_after,
        "pruned": pruned,
    }
    if free_b is not None:
        out["disk_free_mb"] = round(float(free_b) / (1024.0 * 1024.0), 1)
    return out


_FATAL_LOG_PATTERNS = (
    re.compile(r"\*Error\*"),
    re.compile(r"\*FATAL\*"),
    re.compile(r"(?:^|\s)(?:FATAL|ERROR)\s*\([A-Za-z0-9_]+-"),
    re.compile(r"^\s*FATAL\s*[:(]"),
    re.compile(r"^\s*ERROR\s*:\s+\S"),
    re.compile(r"spectre\s+completes\s+with\s+[1-9]\d*\s+errors?", re.IGNORECASE),
    re.compile(r"spectre\s+terminated\s+prematurely", re.IGNORECASE),
    re.compile(r"internal\s+error\s+found\s+in\s+spectre", re.IGNORECASE),
)


def _scan_subprocess_fatal_errors(log_file, stdout_txt, stderr_txt):
    """Scan tool log file, stdout, and stderr for fatal Cadence/Spectre error markers."""
    chunks = []
    if log_file and os.path.isfile(log_file):
        try:
            fh = open(log_file, "rb")
            try:
                chunks.append(fh.read().decode("utf-8", "replace"))
            finally:
                fh.close()
        except Exception:
            pass
    if stdout_txt:
        chunks.append(stdout_txt)
    if stderr_txt:
        chunks.append(stderr_txt)

    hits = []
    seen_lines = set()
    for blob in chunks:
        for raw_ln in blob.splitlines():
            ln = raw_ln.strip()
            if not ln or ln in seen_lines:
                continue
            for pat in _FATAL_LOG_PATTERNS:
                if pat.search(raw_ln):
                    seen_lines.add(ln)
                    hits.append(ln[:300])
                    break
            if len(hits) >= 10:
                return hits
    return hits


def _build_live_bridge_load_expr(run_dir, abs_script):
    """Wrap `(load <script>)` with `changeWorkingDir(run_dir)` inside `unwindProtect` restoring CWD."""
    q_run = ic617_client._skill_quote(run_dir)
    q_scr = ic617_client._skill_quote(abs_script)
    return (
        "let((saPrevCwd) "
        "saPrevCwd = getWorkingDir() "
        'unless(changeWorkingDir(%s) error("Cannot changeWorkingDir to %%s\\n" %s)) '
        "unwindProtect((load %s) when(stringp(saPrevCwd) errset(changeWorkingDir(saPrevCwd) nil))))"
        % (q_run, q_run, q_scr)
    )


def _is_pid_alive_local(pid):
    if not pid or pid <= 0:
        return False
    if os.name == "posix":
        try:
            os.kill(int(pid), 0)
            return True
        except OSError as err:
            return err.errno == errno.EPERM
    return True


def parse_cdslck_file(lock_path):
    info = {
        "lock_file": os.path.realpath(lock_path),
        "user": None,
        "host": None,
        "pid": None,
        "app": None,
        "pid_alive_on_host": None,
    }
    try:
        fh = open(lock_path, "rb")
        try:
            raw = fh.read(8192).decode("latin1", "replace")
        finally:
            fh.close()
    except Exception:
        return info

    patterns = (
        ("user", r'(?:LoginName|UserName|user)\s+([^\s\r\n"]+)'),
        ("host", r'(?:HostName|host)\s+([^\s\r\n"]+)'),
        ("pid", r'(?:ProcessIdentifier|pid)\s+(\d+)'),
        ("app", r'(?:AppName|ProgramName)\s+([^\s\r\n"]+)'),
    )
    for field, pat in patterns:
        m = re.search(pat, raw, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            info[field] = int(val) if field == "pid" else val

    local_host = socket.gethostname().split(".")[0].lower()
    lock_host = (info["host"] or "").split(".")[0].lower()
    if info["pid"] is not None and (not lock_host or lock_host in (local_host, "localhost", "127")):
        info["pid_alive_on_host"] = _is_pid_alive_local(info["pid"])
    return info


def _strip_cds_inline_comment(line):
    """Strip `#` or `--` comments outside quoted strings."""
    in_dq = False
    in_sq = False
    n = len(line)
    i = 0
    while i < n:
        ch = line[i]
        if ch == '"' and not in_sq:
            in_dq = not in_dq
        elif ch == "'" and not in_dq:
            in_sq = not in_sq
        elif not in_dq and not in_sq:
            if ch == "#":
                return line[:i].strip()
            if ch == "-" and i + 1 < n and line[i + 1] == "-":
                return line[:i].strip()
        i += 1
    return line.strip()


def _tokenize_cds_line(line):
    """Split a `cds.lib` directive line into tokens while preserving quoted paths with spaces."""
    tokens = []
    cur = []
    in_dq = False
    in_sq = False
    for ch in line:
        if ch == '"' and not in_sq:
            in_dq = not in_dq
        elif ch == "'" and not in_dq:
            in_sq = not in_sq
        elif ch.isspace() and not in_dq and not in_sq:
            if cur:
                tokens.append("".join(cur))
                cur = []
        else:
            cur.append(ch)
    if cur:
        tokens.append("".join(cur))
    return tokens


def _expand_cds_path(raw_path, base_dir):
    s = raw_path.strip()
    if (len(s) >= 2 and s[0] == '"' and s[-1] == '"') or (len(s) >= 2 and s[0] == "'" and s[-1] == "'"):
        s = s[1:-1].strip()

    def _repl(match):
        vname = match.group(1) if match.group(1) is not None else match.group(2)
        return os.environ.get(vname, match.group(0))

    s = _ENV_VAR_RE.sub(_repl, s)
    s = os.path.expanduser(s)
    if not os.path.isabs(s):
        s = os.path.abspath(os.path.join(base_dir, s))
    else:
        s = os.path.abspath(s)
    return s


def _is_readonly_system_tree(path):
    norm = os.path.realpath(path).replace("\\", "/")
    for pref in _READONLY_SYSTEM_PREFIXES:
        root_no_slash = pref.rstrip("/")
        if norm == root_no_slash or norm.startswith(pref):
            return True
    return False


def _parse_cds_lib_file_recursive(cds_path, lib_map, lib_order, visited_files):
    if not os.path.isfile(cds_path):
        return
    real_cds = os.path.normcase(os.path.realpath(cds_path))
    if real_cds in visited_files:
        return
    visited_files.add(real_cds)

    base_dir = os.path.dirname(os.path.realpath(cds_path))
    try:
        fh = open(cds_path, "rb")
        try:
            lines = fh.read().decode("latin1", "replace").splitlines()
        finally:
            fh.close()
    except Exception:
        return

    for raw_line in lines:
        cleaned = _strip_cds_inline_comment(raw_line)
        if not cleaned:
            continue
        tokens = _tokenize_cds_line(cleaned)
        if not tokens:
            continue
        kw = tokens[0].upper()

        if kw in ("INCLUDE", "SOFTINCLUDE") and len(tokens) >= 2:
            inc_path = _expand_cds_path(tokens[1], base_dir)
            if os.path.isfile(inc_path):
                _parse_cds_lib_file_recursive(inc_path, lib_map, lib_order, visited_files)
        elif kw == "DEFINE" and len(tokens) >= 3:
            lib_name = tokens[1]
            lib_dir = _expand_cds_path(tokens[2], base_dir)
            lib_map[lib_name] = [lib_dir]
            if lib_name not in lib_order:
                lib_order.append(lib_name)
        elif kw == "UNDEFINE" and len(tokens) >= 2:
            lib_name = tokens[1]
            if lib_name in lib_map:
                del lib_map[lib_name]
        elif kw == "ASSIGN" and len(tokens) >= 3:
            lib_name = tokens[1]
            if len(tokens) == 3:
                cand_dir = _expand_cds_path(tokens[2], base_dir)
                lib_map[lib_name] = [cand_dir]
                if lib_name not in lib_order:
                    lib_order.append(lib_name)
            elif len(tokens) >= 4 and tokens[2].upper() in ("TMP", "PATH"):
                attr = tokens[2].upper()
                cand_dir = _expand_cds_path(tokens[3], base_dir)
                if attr == "PATH":
                    lib_map[lib_name] = [cand_dir]
                else:
                    cur_list = lib_map.setdefault(lib_name, [])
                    sub_lib = os.path.join(cand_dir, lib_name)
                    if os.path.isdir(sub_lib):
                        if sub_lib not in cur_list:
                            cur_list.append(sub_lib)
                    elif cand_dir not in cur_list:
                        cur_list.append(cand_dir)
                if lib_name not in lib_order:
                    lib_order.append(lib_name)


def _parse_cds_lib_dirs(project_root, target_lib=None):
    """Return list of `(lib_name, real_lib_dir)` recursively resolved from `<project_root>/cds.lib`."""
    cds_lib = os.path.join(project_root, "cds.lib")
    if not os.path.isfile(cds_lib):
        return []

    lib_map = {}
    lib_order = []
    visited = set()
    _parse_cds_lib_file_recursive(cds_lib, lib_map, lib_order, visited)

    result = []
    seen_pairs = set()
    for lib_name in lib_order:
        if lib_name not in lib_map:
            continue
        for raw_dir in lib_map[lib_name]:
            if not os.path.isdir(raw_dir):
                continue
            real_dir = os.path.realpath(raw_dir)
            if _is_readonly_system_tree(real_dir) and target_lib != lib_name:
                continue
            pair_key = (lib_name, os.path.normcase(real_dir))
            if pair_key not in seen_pairs:
                seen_pairs.add(pair_key)
                result.append((lib_name, real_dir))
    return result


def _is_cdslck_filename(fn):
    if fn.endswith(".RSLK"):
        return False
    return fn.endswith(".cdslck") or (".cdslck." in fn)


def scan_project_cdslcks(project_root, target_cell_spec=None):
    """Find `.cdslck` files in project design libraries, accurately filtered by `lib[/cell[/view]]`."""
    want_lib = None
    want_cell = None
    want_view = None
    if target_cell_spec:
        parts = [p for p in target_cell_spec.replace("\\", "/").split("/") if p]
        if len(parts) >= 1:
            want_lib = parts[0]
        if len(parts) >= 2:
            want_cell = parts[1]
        if len(parts) >= 3:
            want_view = parts[2]

    runs_root = os.path.join(project_root, "sim", "runs")
    mapped_libs = _parse_cds_lib_dirs(project_root, target_lib=want_lib)

    lib_targets = []
    has_cds_file = os.path.isfile(os.path.join(project_root, "cds.lib"))
    if want_lib:
        for lib_name, lib_dir in mapped_libs:
            if lib_name == want_lib:
                lib_targets.append((lib_name, lib_dir))
        if not lib_targets and not has_cds_file:
            # Fallback only when project has no `cds.lib` (e.g. `project.json`-only layout)
            fallback_dir = os.path.join(project_root, want_lib)
            if os.path.isdir(fallback_dir) and not _inside_path(fallback_dir, runs_root):
                lib_targets.append((want_lib, os.path.realpath(fallback_dir)))
    else:
        lib_targets.extend(mapped_libs)

    locks = []
    seen = set()

    # 1. Scan mapped OA library directories using exact relative `<cell>/<view>/...` segment matching
    for lib_name, lib_dir in lib_targets:
        for root, subdirs, files in os.walk(lib_dir):
            subdirs[:] = [
                d for d in subdirs
                if d not in (".git", "__pycache__", "runs")
                and not _inside_path(os.path.join(root, d), runs_root)
            ]
            for fn in files:
                if not _is_cdslck_filename(fn):
                    continue
                full_p = os.path.realpath(os.path.join(root, fn))
                norm_p = os.path.normcase(full_p)
                if norm_p in seen:
                    continue

                rel_p = os.path.relpath(full_p, lib_dir)
                segs = [s for s in rel_p.replace("\\", "/").split("/") if s and s != "."]
                dir_segs = segs[:-1]

                if want_cell is not None:
                    if len(dir_segs) < 1 or dir_segs[0] != want_cell:
                        continue
                if want_view is not None:
                    if len(dir_segs) < 2 or dir_segs[1] != want_view:
                        continue

                seen.add(norm_p)
                info = parse_cdslck_file(full_p)
                info["lib"] = lib_name
                info["cell"] = dir_segs[0] if len(dir_segs) >= 1 else None
                info["view"] = dir_segs[1] if len(dir_segs) >= 2 else None
                locks.append(info)

    # 2. When no specific `want_lib` filter was passed, also catch any unmapped local `.cdslck` under project_root
    if not want_lib:
        mapped_real_dirs = [ld for _, ld in mapped_libs]
        for root, subdirs, files in os.walk(project_root):
            subdirs[:] = [
                d for d in subdirs
                if d not in (".git", "__pycache__", "runs")
                and not _inside_path(os.path.join(root, d), runs_root)
            ]
            for fn in files:
                if not _is_cdslck_filename(fn):
                    continue
                full_p = os.path.realpath(os.path.join(root, fn))
                norm_p = os.path.normcase(full_p)
                if norm_p in seen:
                    continue
                if any(_inside_path(full_p, mdir) for mdir in mapped_real_dirs):
                    continue
                seen.add(norm_p)
                locks.append(parse_cdslck_file(full_p))

    return locks


def build_tool_command(tool, run_dir, netlist=None, script=None, psf_ascii=True, extra_args=None, env_script=None):
    extra = list(extra_args or [])
    env_sh = env_script or os.path.join(os.path.expanduser("~"), "cadence", "env.sh")

    if tool == "spectre":
        if not netlist:
            raise ValueError("spectre requires --netlist <input.scs>")
        abs_net = os.path.abspath(netlist)
        psf_dir = os.path.join(run_dir, "psf")
        log_file = os.path.join(run_dir, "spectre.log")
        cmd_tokens = ["spectre", abs_net]
        if psf_ascii:
            cmd_tokens.extend(["-format", "psfascii"])
        cmd_tokens.extend(["-raw", psf_dir, "=log", log_file])
        cmd_tokens.extend(extra)
    elif tool == "ocean":
        if not script:
            raise ValueError("ocean requires --script <run.ocn>")
        abs_scr = os.path.abspath(script)
        log_file = os.path.join(run_dir, "ocean.log")
        cmd_tokens = ["ocean", "-nograph", "-restore", abs_scr, "-log", log_file]
        cmd_tokens.extend(extra)
    elif tool == "virtuoso-batch":
        if not script:
            raise ValueError("virtuoso-batch requires --script <batch.il>")
        abs_scr = os.path.abspath(script)
        log_file = os.path.join(run_dir, "virtuoso_batch.log")
        cmd_tokens = ["virtuoso", "-nograph", "-restore", abs_scr, "-log", log_file]
        cmd_tokens.extend(extra)
    elif tool == "si":
        log_file = os.path.join(run_dir, "si.log")
        cmd_tokens = ["si", run_dir, "-batch", "-command", "netlist"]
        cmd_tokens.extend(extra)
    else:
        raise ValueError("Unsupported tool %s (choose from: %s)" % (repr(tool), ", ".join(VALID_TOOLS)))

    quoted_cmd = " ".join(_shell_quote(t) for t in cmd_tokens)
    shell_lines = [
        "export CDS_Netlisting_Mode=Analog",
        "export CDS_UseNextLicense=never",
        "if [ -f %s ]; then . %s >/dev/null 2>&1; fi" % (_shell_quote(env_sh), _shell_quote(env_sh)),
        "exec %s" % quoted_cmd,
    ]
    bash_payload = "; ".join(shell_lines)
    return {
        "tool_argv": cmd_tokens,
        "env_script": env_sh,
        "bash_command": ["bash", "-lc", bash_payload],
        "bash_script": bash_payload,
        "log_file": log_file,
        "psf_dir": os.path.join(run_dir, "psf") if tool == "spectre" else None,
    }


def _sha256_file(path):
    """Compute lowercase SHA-256 hex digest of a file in Python 2.6.6+ compatible chunks."""
    digest = hashlib.sha256()
    fh = open(path, "rb")
    try:
        while True:
            chunk = fh.read(65536)
            if not chunk:
                break
            digest.update(chunk)
    finally:
        fh.close()
    return digest.hexdigest().lower()


def _strip_spectre_inline_comment(line):
    """Strip `//` inline comments outside quoted strings."""
    in_dq = False
    in_sq = False
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if ch == '"' and not in_sq:
            in_dq = not in_dq
        elif ch == "'" and not in_dq:
            in_sq = not in_sq
        elif not in_dq and not in_sq and ch == "/" and i + 1 < n and line[i + 1] == "/":
            return line[:i]
        i += 1
    return line


def _strip_spectre_comments(text):
    """Return `(raw_lines, stripped_body)` with Spectre block/line comments removed."""
    no_block = _BLOCK_COMMENT_RE.sub(" ", text)
    joined = _LINE_CONT_RE.sub(" ", no_block)
    raw_lines = joined.splitlines()
    clean_lines = []
    for raw_ln in raw_lines:
        if raw_ln.lstrip().startswith("*"):
            continue
        cleaned = _strip_spectre_inline_comment(raw_ln).strip()
        if cleaned:
            clean_lines.append(cleaned)
    return raw_lines, "\n".join(clean_lines)


def _normalize_corner_token(raw_val):
    s = str(raw_val or "").strip().strip('"').strip("'")
    if not s:
        return None
    s_low = s.lower()
    if s_low in ("tt", "nn", "ss", "ff", "fs", "sf"):
        return s_low.upper()
    m = _CORNER_PREFIX_RE.match(s_low)
    if m:
        return m.group(1).upper()
    return s.upper()


def _inspect_spectre_netlist_provenance(netlist_path):
    """Extract corner, temperature, Monte Carlo, and post-layout provenance from a Spectre netlist."""
    fh = open(netlist_path, "rb")
    try:
        raw_txt = fh.read().decode("utf-8", "replace")
    finally:
        fh.close()

    raw_lines, body = _strip_spectre_comments(raw_txt)

    # Extract section= corners
    std_corners = []
    other_sections = []
    for m in _NETLIST_SECTION_RE.finditer(body):
        raw_sec = m.group(1).strip()
        norm_sec = _normalize_corner_token(raw_sec)
        if norm_sec in ("TT", "NN", "SS", "FF", "FS", "SF"):
            canon = "TT" if norm_sec == "NN" else norm_sec
            if canon not in std_corners:
                std_corners.append((norm_sec, canon))
        elif raw_sec and raw_sec not in other_sections:
            other_sections.append(raw_sec)

    corner = None
    if std_corners:
        canon_set = set([c[1] for c in std_corners])
        if len(canon_set) == 1:
            corner = std_corners[0][0]
    elif len(other_sections) == 1:
        corner = other_sections[0]

    # Extract temp= temperature_c (never matches tnom=)
    temps = []
    for m in _NETLIST_TEMP_RE.finditer(body):
        try:
            t_val = float(m.group(1))
        except (TypeError, ValueError):
            continue
        if not any([abs(t_val - x) <= 0.01 for x in temps]):
            temps.append(t_val)
    temperature_c = temps[0] if len(temps) == 1 else None

    # Monte Carlo statement outside comments
    has_mc = bool(_MC_STMT_RE.search(body))
    mc_numruns = None
    if has_mc:
        m_nr = _MC_NUMRUNS_RE.search(body)
        if m_nr:
            try:
                mc_numruns = int(m_nr.group(1))
            except (TypeError, ValueError):
                mc_numruns = None

    # Post-layout / PEX markers (parasitic RC elements outside comments OR view/extractor markers)
    has_pex = False
    if _PARASITIC_RC_NAME_RE.search(body) or _PEX_TOKEN_RE.search(body):
        has_pex = True
    if not has_pex:
        for raw_ln in raw_lines:
            if _PEX_VIEW_MARKER_RE.search(raw_ln):
                has_pex = True
                break

    return {
        "corner": corner,
        "temperature_c": temperature_c,
        "has_mc": has_mc,
        "mc_numruns": mc_numruns,
        "has_pex": has_pex,
    }


def _is_ascii_mc_psf_file(fpath):
    """Best-effort check whether an ASCII PSF file contains Monte Carlo sweep/header metadata."""
    low = os.path.basename(fpath).lower()
    if (
        (low.startswith("mc") and (low.endswith(".psf") or low.endswith(".dc") or low.endswith(".ac") or low.endswith(".tran")))
        or low.startswith("mcdata")
        or low.endswith(".mcdata")
        or low.startswith("montecarlo")
        or low.endswith(".mc")
    ):
        return True
    try:
        fh = open(fpath, "rb")
        try:
            head = fh.read(2048).decode("latin1", "replace")
        finally:
            fh.close()
        if "HEADER" not in head:
            return False
        import psf_ascii_reader
        parsed = psf_ascii_reader.parse_psf_file(fpath, reject_nonfinite=False, reject_truncated=True)
        sw = str(parsed.get("sweep_name") or "").strip().lower()
        if sw in ("iteration", "mc_iteration", "montecarlo", "monte_carlo", "mc_iter", "mc_run", "mc_sample"):
            return True
        hdr = parsed.get("header") or {}
        if isinstance(hdr, dict):
            for hk, hv in hdr.items():
                hkl = str(hk).strip().lower()
                hvl = str(hv).strip().lower()
                if hkl in ("analysis", "analysis type", "analysis_type") and "montecarlo" in hvl:
                    return True
    except Exception:
        return False
    return False


def _write_spectre_run_manifest(run_dir, resolved_run_id, netlist_path, psf_dir, psf_ascii=True):
    """Write a cryptographically bound `run_manifest.json` inside `run_dir` after clean Spectre exit."""
    abs_net = os.path.realpath(netlist_path)
    netlist_sha256 = _sha256_file(abs_net)
    if _inside_path(abs_net, run_dir):
        manifest_net = os.path.relpath(abs_net, run_dir).replace(os.sep, "/")
    else:
        manifest_net = abs_net

    prov = _inspect_spectre_netlist_provenance(abs_net)

    psf_files_map = {}
    mc_psf_files = []
    if psf_dir and os.path.isdir(psf_dir):
        for root, dirs, files in os.walk(psf_dir):
            dirs.sort()
            for fn in sorted(files):
                fn_low = fn.lower()
                if _is_cdslck_filename(fn) or fn_low.endswith(".lck") or fn_low.endswith(".rslk") or fn_low.endswith(".lock"):
                    continue
                full_p = os.path.join(root, fn)
                if not os.path.isfile(full_p):
                    continue
                rel_p = os.path.relpath(full_p, run_dir).replace(os.sep, "/")
                psf_files_map[rel_p] = _sha256_file(full_p)
                if prov["has_mc"] and psf_ascii and _is_ascii_mc_psf_file(full_p):
                    mc_psf_files.append(rel_p)

    manifest = {
        "schema": "skill-analog.run-manifest.v1",
        "run_id": resolved_run_id,
        "tool": "spectre",
        "exit_code": 0,
        "netlist_path": manifest_net,
        "netlist_sha256": netlist_sha256,
        "psf_files": psf_files_map,
    }
    if prov["corner"] is not None:
        manifest["corner"] = prov["corner"]
    if prov["temperature_c"] is not None:
        manifest["temperature_c"] = prov["temperature_c"]
    if prov["has_mc"]:
        mc_obj = {
            "enabled": True,
            "netlist_backed": True,
            "mc_psf_files": mc_psf_files,
        }
        if prov["mc_numruns"] is not None:
            mc_obj["numruns_declared"] = prov["mc_numruns"]
        manifest["monte_carlo"] = mc_obj
    else:
        manifest["monte_carlo"] = {"enabled": False}
    if prov["has_pex"]:
        manifest["post_layout"] = {"enabled": True, "netlist_backed": True}
    else:
        manifest["post_layout"] = {"enabled": False}

    manifest_path = os.path.join(run_dir, "run_manifest.json")
    mf = open(manifest_path, "wb")
    try:
        mf.write((json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    finally:
        mf.close()
    return manifest_path


def execute_cadence_job(
    tool,
    project_dir=None,
    run_id=None,
    netlist=None,
    script=None,
    cell_spec=None,
    write_oa=False,
    psf_ascii=True,
    prefer_bridge=True,
    socket_dir=None,
    env_script=None,
    overwrite_run=False,
    dry_run=False,
    min_free_mb=512.0,
    require_save_selected=False,
    warn_psf_mb=15.0,
    warn_runs_mb=500.0,
    extra_args=None,
):
    if tool not in VALID_TOOLS:
        raise ValueError("Invalid tool %s; expected one of %s" % (repr(tool), ", ".join(VALID_TOOLS)))

    project_root = discover_project_root(project_dir or netlist or script or os.getcwd())
    resolved_run_id, run_dir = prepare_run_dir(
        project_root,
        run_id=run_id,
        tool_name=tool,
        overwrite_run=overwrite_run,
        dry_run=dry_run,
    )

    needs_oa_lock_check = bool(write_oa or tool in ("virtuoso-batch", "ocean", "si") or cell_spec)
    locks = scan_project_cdslcks(project_root, target_cell_spec=cell_spec) if needs_oa_lock_check else []
    active_locks = [lk for lk in locks if lk.get("pid_alive_on_host") is not False]

    bridge_alive = False
    if prefer_bridge and (tool == "virtuoso-batch" or (write_oa and active_locks)):
        bridge_alive = ic617_client.is_bridge_active(socket_dir=socket_dir)

    # Route SKILL batch scripts seamlessly through the live Virtuoso CIW bridge when active!
    if tool == "virtuoso-batch" and script and prefer_bridge and bridge_alive:
        abs_script = os.path.abspath(script)
        if not os.path.isfile(abs_script):
            raise ValueError("SKILL script not found: " + abs_script)
        skill_expr = _build_live_bridge_load_expr(run_dir, abs_script)
        if dry_run:
            return {
                "ok": True,
                "dry_run": True,
                "tool": tool,
                "execution_mode": "ic617_live_bridge",
                "project_root": project_root,
                "run_id": resolved_run_id,
                "run_dir": run_dir,
                "cwd": run_dir,
                "locks_detected": active_locks,
                "skill_expr": skill_expr,
            }
        if overwrite_run and os.path.isdir(run_dir):
            _clean_run_dir_for_overwrite(run_dir, project_root, keep_paths=[abs_script])
        _mkdir_p(run_dir)
        _ensure_run_dir_cds_lib(project_root, run_dir)

        b_resp = ic617_client.send_bridge_request(skill_expr, socket_dir=socket_dir, timeout=120.0)
        transport_ok = bool(b_resp.get("transport_ok", b_resp.get("bridge_active", False)))
        op_ok = bool(b_resp.get("ok")) and (b_resp.get("op_ok", True) is not False)
        parsed_res = None
        raw_res = b_resp.get("result")
        if isinstance(raw_res, ic617_client.TEXT_TYPES):
            s_res = raw_res.strip()
            if s_res.startswith("{") and s_res.endswith("}"):
                try:
                    cand = json.loads(s_res)
                    if isinstance(cand, dict):
                        parsed_res = cand
                        if cand.get("ok") is False:
                            op_ok = False
                except Exception:
                    pass
        elif isinstance(raw_res, dict):
            parsed_res = raw_res
            if raw_res.get("ok") is False:
                op_ok = False

        overall_ok = bool(b_resp.get("ok")) and op_ok
        ret = {
            "ok": overall_ok,
            "transport_ok": transport_ok,
            "op_ok": op_ok,
            "tool": tool,
            "execution_mode": "ic617_live_bridge",
            "project_root": project_root,
            "run_id": resolved_run_id,
            "run_dir": run_dir,
            "cwd": run_dir,
            "locks_detected": active_locks,
            "bridge_response": b_resp,
        }
        if parsed_res is not None:
            ret["skill_result_json"] = parsed_res
        if not overall_ok:
            ret["error"] = (
                b_resp.get("error")
                or (parsed_res.get("error") if isinstance(parsed_res, dict) else None)
                or "Live bridge SKILL operation returned ok=false"
            )
        return ret

    # Block unsafe batch OA writes when `.cdslck` is held and live bridge is unavailable
    if active_locks and (write_oa or tool == "virtuoso-batch"):
        return {
            "ok": False,
            "status": "BLOCKED_BY_CDSLCK",
            "tool": tool,
            "execution_mode": "blocked",
            "project_root": project_root,
            "run_id": resolved_run_id,
            "run_dir": run_dir,
            "cwd": run_dir,
            "locks_detected": active_locks,
            "error": (
                "OpenAccess .cdslck lock detected on project design files while Virtuoso live bridge is inactive. "
                'Load `(load "/home/disk/eda/references/SKILL-ANALOG/tools/ic617_live_bridge.il")` in Virtuoso CIW '
                "or save/close the locked cellView before batch OA mutation."
            ),
        }

    spec = build_tool_command(
        tool=tool,
        run_dir=run_dir,
        netlist=netlist,
        script=script,
        psf_ascii=psf_ascii,
        extra_args=extra_args,
        env_script=env_script,
    )

    if netlist and not os.path.isfile(netlist) and not dry_run:
        raise ValueError("Netlist file not found: " + str(netlist))
    if script and not os.path.isfile(script) and not dry_run:
        raise ValueError("Script file not found: " + str(script))

    disk_warnings = []
    if tool == "spectre" and netlist and os.path.isfile(netlist) and psf_ascii:
        hygiene = _inspect_spectre_netlist_disk_hygiene(netlist)
        if hygiene.get("has_waveform_analysis") and (not hygiene.get("has_save_selected")):
            if require_save_selected:
                return {
                    "ok": False,
                    "status": "BLOCKED_MISSING_SAVE_SELECTED",
                    "tool": tool,
                    "execution_mode": "blocked",
                    "project_root": project_root,
                    "run_id": resolved_run_id,
                    "run_dir": run_dir,
                    "cwd": run_dir,
                    "waveform_analyses": hygiene.get("waveform_analyses", []),
                    "error": (
                        hygiene["warnings"][0]
                        if hygiene.get("warnings")
                        else "Missing `options save=selected` with --require-save-selected active."
                    ),
                }
        for wmsg in hygiene.get("warnings") or []:
            disk_warnings.append(wmsg)

    free_bytes_before = _get_free_disk_bytes(os.path.dirname(run_dir))
    free_mb_before = round(float(free_bytes_before) / (1024.0 * 1024.0), 1) if free_bytes_before is not None else None
    if (
        tool == "spectre"
        and (not dry_run)
        and (min_free_mb is not None)
        and float(min_free_mb) > 0.0
        and (free_mb_before is not None)
        and (free_mb_before < float(min_free_mb))
    ):
        return {
            "ok": False,
            "status": "BLOCKED_LOW_DISK_SPACE",
            "tool": tool,
            "execution_mode": "blocked",
            "project_root": project_root,
            "run_id": resolved_run_id,
            "run_dir": run_dir,
            "cwd": run_dir,
            "disk_free_mb": free_mb_before,
            "min_free_mb": float(min_free_mb),
            "error": (
                "Insufficient free disk space to launch Spectre cleanly: %.1f MB free < %.1f MB minimum. "
                "Run `python -B %s prune-runs --project %s --keep 2` or add `options save=selected` first."
                % (free_mb_before, float(min_free_mb), os.path.join(_TOOLS_DIR, "cadence_exec.py"), project_root)
            ),
        }

    if dry_run:
        dry_ret = {
            "ok": True,
            "dry_run": True,
            "tool": tool,
            "execution_mode": "subprocess",
            "project_root": project_root,
            "run_id": resolved_run_id,
            "run_dir": run_dir,
            "cwd": run_dir,
            "overwrite_run": bool(overwrite_run),
            "psf_dir": spec["psf_dir"],
            "psf_ascii": bool(psf_ascii) if tool == "spectre" else None,
            "env_script": spec["env_script"],
            "cds_netlisting_mode": "Analog",
            "locks_detected": active_locks,
            "tool_argv": spec["tool_argv"],
            "bash_command": spec["bash_command"],
            "log_file": spec["log_file"],
        }
        if free_mb_before is not None:
            dry_ret["disk_free_mb"] = free_mb_before
        if disk_warnings:
            dry_ret["disk_warnings"] = disk_warnings
        return dry_ret

    if overwrite_run and os.path.isdir(run_dir):
        keep_list = [netlist, script]
        if tool == "si":
            keep_list.append(os.path.join(run_dir, "si.env"))
        _clean_run_dir_for_overwrite(run_dir, project_root, keep_paths=keep_list)

    _mkdir_p(run_dir)
    if spec["psf_dir"]:
        _mkdir_p(spec["psf_dir"])
    run_cds_lib = _ensure_run_dir_cds_lib(project_root, run_dir)

    env = dict(os.environ)
    env["CDS_Netlisting_Mode"] = "Analog"
    env["CDS_UseNextLicense"] = "never"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["SA_PROJECT_ROOT"] = project_root
    env["SA_RUN_DIR"] = run_dir

    t0 = time.time()
    proc = subprocess.Popen(
        spec["bash_command"],
        cwd=run_dir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    out_bytes, err_bytes = proc.communicate()
    elapsed = round(time.time() - t0, 4)

    stdout_txt = out_bytes.decode("utf-8", "replace")
    stderr_txt = err_bytes.decode("utf-8", "replace")

    wrapper_log = os.path.join(run_dir, "cadence_exec.log")
    lf = open(wrapper_log, "wb")
    try:
        lf.write(("COMMAND: %s\nCWD: %s\nEXIT_CODE: %d\nELAPSED_S: %.4f\n--- STDOUT ---\n%s\n--- STDERR ---\n%s\n" % (
            spec["bash_script"], run_dir, proc.returncode, elapsed, stdout_txt, stderr_txt
        )).encode("utf-8"))
    finally:
        lf.close()

    log_errors = _scan_subprocess_fatal_errors(spec["log_file"], stdout_txt, stderr_txt)
    sub_ok = (proc.returncode == 0) and (len(log_errors) == 0)

    manifest_path = None
    if tool == "spectre" and sub_ok and netlist:
        manifest_path = _write_spectre_run_manifest(
            run_dir=run_dir,
            resolved_run_id=resolved_run_id,
            netlist_path=netlist,
            psf_dir=spec["psf_dir"],
            psf_ascii=psf_ascii,
        )

    runs_base = os.path.join(project_root, "sim", "runs")
    psf_mb = round(float(_dir_size_bytes(spec["psf_dir"])) / (1024.0 * 1024.0), 3) if spec["psf_dir"] else None
    runs_root_mb = round(float(_dir_size_bytes(runs_base)) / (1024.0 * 1024.0), 3) if os.path.isdir(runs_base) else 0.0
    free_bytes_after = _get_free_disk_bytes(runs_base)
    disk_free_mb = round(float(free_bytes_after) / (1024.0 * 1024.0), 1) if free_bytes_after is not None else free_mb_before
    if psf_mb is not None and warn_psf_mb is not None and psf_mb > float(warn_psf_mb):
        disk_warnings.append(
            "Single run PSF size is %.2f MB (> %.1f MB budget); restrict `save` signals with `options save=selected`."
            % (psf_mb, float(warn_psf_mb))
        )
    if warn_runs_mb is not None and runs_root_mb > float(warn_runs_mb):
        disk_warnings.append(
            "Project sim/runs total size is %.1f MB (> %.1f MB threshold); run `cadence_exec.py prune-runs --project %s --keep 2`."
            % (runs_root_mb, float(warn_runs_mb), project_root)
        )

    ret = {
        "ok": sub_ok,
        "op_ok": sub_ok,
        "exit_code": proc.returncode,
        "elapsed_s": elapsed,
        "tool": tool,
        "execution_mode": "subprocess",
        "project_root": project_root,
        "run_id": resolved_run_id,
        "run_dir": run_dir,
        "cwd": run_dir,
        "run_cds_lib": run_cds_lib,
        "psf_dir": spec["psf_dir"],
        "log_file": spec["log_file"],
        "log_errors": log_errors,
        "wrapper_log": wrapper_log,
        "locks_detected": active_locks,
        "runs_root_mb": runs_root_mb,
        "stdout_tail": stdout_txt[-4000:],
        "stderr_tail": stderr_txt[-4000:],
    }
    if psf_mb is not None:
        ret["psf_mb"] = psf_mb
    if disk_free_mb is not None:
        ret["disk_free_mb"] = disk_free_mb
    if disk_warnings:
        ret["disk_warnings"] = disk_warnings
    if manifest_path is not None:
        ret["run_manifest"] = manifest_path
    if not sub_ok and log_errors:
        ret["error"] = "Fatal/error marker detected in %s log: %s" % (tool, log_errors[0])
    return ret


# ---------------------------------------------------------------------------
# Self-Test Suite (`--self-test`)
# ---------------------------------------------------------------------------

def _write_text_utf8(path, content):
    _mkdir_p(os.path.dirname(path))
    fh = open(path, "wb")
    try:
        fh.write(content.encode("utf-8"))
    finally:
        fh.close()


def run_self_test():
    checks = []
    tmp_root = tempfile.mkdtemp(prefix="sa_cadence_exec_test_")
    old_ext_env = os.environ.get("SA_TEST_EXT_LIBS")
    helper_proc = None
    try:
        # Project directory deliberately named `ota_core` to test that parent directory names
        # NEVER cause substring false positives during `.cdslck` filtering!
        proj_dir = os.path.join(tmp_root, "ota_core", "schematic", "proj_ws")
        ext_dir = os.path.join(tmp_root, "ext_shared_libs")
        os.environ["SA_TEST_EXT_LIBS"] = ext_dir

        _write_text_utf8(os.path.join(proj_dir, "project.json"), '{"name": "test_proj"}\n')
        _write_text_utf8(
            os.path.join(proj_dir, "cds.lib"),
            'INCLUDE "sub/inc_libs.cds.lib"\n'
            'SOFTINCLUDE "sub/nonexistent_optional.cds.lib"\n'
            'DEFINE sys_ro /opt/IC617/tools/dfII/etc/cdslib/basic\n',
        )
        _write_text_utf8(
            os.path.join(proj_dir, "sub", "inc_libs.cds.lib"),
            '# Cycle test back to root cds.lib\n'
            'INCLUDE "../cds.lib"\n'
            'DEFINE dropped_lib "${SA_TEST_EXT_LIBS}/dropped_phys"\n'
            'UNDEFINE dropped_lib\n'
            'DEFINE analog_lib "${SA_TEST_EXT_LIBS}/phys_analog_v2"\n',
        )

        # Create lock inside `phys_analog_v2/ota_core/schematic/sch.oa.cdslck` AND dropped_phys
        local_host = socket.gethostname()
        lock_body = "LoginName tester\nHostName %s\nProcessIdentifier %d\nAppName virtuoso\n" % (
            local_host, os.getpid()
        )
        _write_text_utf8(
            os.path.join(ext_dir, "phys_analog_v2", "ota_core", "schematic", "sch.oa.cdslck"),
            lock_body,
        )
        _mkdir_p(os.path.join(ext_dir, "phys_analog_v2", "ota_core_tb", "schematic"))
        _write_text_utf8(
            os.path.join(ext_dir, "dropped_phys", "ota_core", "schematic", "sch.oa.cdslck"),
            lock_body,
        )

        # 1. Monotonic auto-generated `run_id` uniqueness
        seen_ids = set()
        for _ in range(25):
            rid, _ = prepare_run_dir(proj_dir, tool_name="spectre")
            seen_ids.add(rid)
        if len(seen_ids) != 25:
            raise AssertionError("Expected 25 unique monotonic run_ids, got %d" % len(seen_ids))
        checks.append("monotonic_run_id_ok")

        # 2. Recursive `cds.lib` (`INCLUDE`, `SOFTINCLUDE`, `UNDEFINE`, `${ENV}`, cycle guard) + relative segment `.cdslck`
        lks_hit = scan_project_cdslcks(proj_dir, target_cell_spec="analog_lib/ota_core/schematic")
        if len(lks_hit) != 1 or lks_hit[0].get("lib") != "analog_lib" or lks_hit[0].get("cell") != "ota_core":
            raise AssertionError("Expected exact lock match on analog_lib/ota_core/schematic, got %r" % lks_hit)

        if scan_project_cdslcks(proj_dir, target_cell_spec="analog_lib/ota_core_tb/schematic"):
            raise AssertionError("False positive lock match on unlocked ota_core_tb")
        if scan_project_cdslcks(proj_dir, target_cell_spec="analog_lib/ota_core/symbol"):
            raise AssertionError("False positive lock match on unlocked symbol view")
        if scan_project_cdslcks(proj_dir, target_cell_spec="dropped_lib"):
            raise AssertionError("UNDEFINE library was still scanned for locks")
        if scan_project_cdslcks(proj_dir, target_cell_spec="other_lib/ota_core/schematic"):
            raise AssertionError("Substring in parent project path caused false lock match")
        checks.append("recursive_cds_lib_and_segment_cdslck_ok")

        # 3. `run_dir` non-empty reuse guard & `--overwrite-run` cleanup + `cwd=run_dir` + `<run_dir>/cds.lib`
        deck_path = os.path.join(proj_dir, "tb.scs")
        _write_text_utf8(deck_path, "simulator lang=spectre\n")
        stale_psf = os.path.join(proj_dir, "sim", "runs", "guard_run", "psf", "stale.tran")
        stale_log = os.path.join(proj_dir, "sim", "runs", "guard_run", "spectre.log")
        _write_text_utf8(stale_psf, "STALE_PSF\n")
        _write_text_utf8(stale_log, "STALE_LOG\n")

        raised_guard = False
        try:
            execute_cadence_job(
                "spectre",
                project_dir=proj_dir,
                run_id="guard_run",
                netlist=deck_path,
                overwrite_run=False,
                dry_run=False,
            )
        except ValueError as verr:
            if "--overwrite-run" in str(verr):
                raised_guard = True
        if not raised_guard:
            raise AssertionError("Expected ValueError blocking non-empty run_dir reuse without --overwrite-run")

        # Mock `subprocess.Popen` to verify `--overwrite-run`, `cwd=run_dir`, `SA_PROJECT_ROOT`, and `<run_dir>/cds.lib`
        popen_captured = {}
        orig_popen = subprocess.Popen

        class _DummyProc(object):
            def __init__(self):
                self.returncode = 0

            def communicate(self):
                return (b"MOCK_SPECTRE_OK\n", b"")

        def _mock_popen(cmd, cwd=None, env=None, stdout=None, stderr=None):
            popen_captured["cwd"] = cwd
            popen_captured["env"] = dict(env or {})
            popen_captured["stale_psf_existed"] = os.path.exists(stale_psf)
            popen_captured["stale_log_existed"] = os.path.exists(stale_log)
            popen_captured["run_cds_exists"] = os.path.isfile(os.path.join(cwd, "cds.lib"))
            return _DummyProc()

        subprocess.Popen = _mock_popen
        try:
            ow_res = execute_cadence_job(
                "spectre",
                project_dir=proj_dir,
                run_id="guard_run",
                netlist=deck_path,
                overwrite_run=True,
                dry_run=False,
            )
        finally:
            subprocess.Popen = orig_popen

        expected_run_dir = os.path.abspath(os.path.join(proj_dir, "sim", "runs", "guard_run"))
        if not ow_res.get("ok"):
            raise AssertionError("Expected mock spectre overwrite run ok=True, got %r" % ow_res)
        if popen_captured.get("stale_psf_existed") or popen_captured.get("stale_log_existed"):
            raise AssertionError("--overwrite-run failed to wipe stale psf/ or log before running")
        if os.path.normcase(os.path.realpath(popen_captured.get("cwd", ""))) != os.path.normcase(os.path.realpath(expected_run_dir)):
            raise AssertionError("Expected subprocess cwd == run_dir (%s), got %s" % (expected_run_dir, popen_captured.get("cwd")))
        if popen_captured.get("env", {}).get("SA_PROJECT_ROOT") != os.path.realpath(proj_dir):
            raise AssertionError("SA_PROJECT_ROOT env mismatch: %r" % popen_captured.get("env", {}).get("SA_PROJECT_ROOT"))
        if popen_captured.get("env", {}).get("SA_RUN_DIR") != expected_run_dir:
            raise AssertionError("SA_RUN_DIR env mismatch: %r" % popen_captured.get("env", {}).get("SA_RUN_DIR"))
        if not popen_captured.get("run_cds_exists"):
            raise AssertionError("<run_dir>/cds.lib INCLUDE bridge was not created")
        checks.append("run_dir_guard_overwrite_cwd_and_cds_lib_ok")

        # 4. Block batch OA write when `.cdslck` is active and live bridge is inactive
        il_script = os.path.join(proj_dir, "job.il")
        _write_text_utf8(il_script, '(println "batch job")\n')
        blk_res = execute_cadence_job(
            "virtuoso-batch",
            project_dir=proj_dir,
            script=il_script,
            cell_spec="analog_lib/ota_core/schematic",
            prefer_bridge=False,
        )
        if blk_res.get("ok") is not False or blk_res.get("status") != "BLOCKED_BY_CDSLCK":
            raise AssertionError("Expected BLOCKED_BY_CDSLCK, got %r" % blk_res)
        checks.append("cdslck_blocks_unsafe_batch_ok")

        # 5. Live bridge semantic `op_ok: false` propagation
        sock_dir = os.path.join(tmp_root, "bridge_sock")
        env_h = dict(os.environ)
        env_h["PYTHONDONTWRITEBYTECODE"] = "1"
        helper_proc = orig_popen(
            [sys.executable, "-B", "-u", os.path.join(_TOOLS_DIR, "ic617_client.py"), "--start-helper", "--socket-dir", sock_dir],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env_h,
        )
        ready_evt = threading.Event()

        def _watch_err():
            while True:
                ln = helper_proc.stderr.readline()
                if not ln:
                    break
                if b"[SA-BRIDGE-READY]" in ln:
                    ready_evt.set()

        t_err = threading.Thread(target=_watch_err)
        t_err.daemon = True
        t_err.start()
        ready_evt.wait(5.0)
        if not ready_evt.is_set():
            raise AssertionError("Bridge helper failed to start in cadence_exec self-test")

        def _mock_bridge_ipc():
            while True:
                raw_ln = helper_proc.stdout.readline()
                if not raw_ln:
                    break
                ln = raw_ln.decode("utf-8", "replace").strip()
                if not ln.startswith("REQ "):
                    continue
                parts = ln.split(" ", 2)
                rid = parts[1]
                cmd_txt = binascii.unhexlify(parts[2].encode("ascii")).decode("utf-8", "replace")
                if "pong:" in cmd_txt:
                    resp = json.dumps({"id": rid, "ok": True, "result": "pong:9001"}) + "\n"
                else:
                    inner = json.dumps({"ok": False, "check_errors": 1, "saved": False})
                    resp = json.dumps({"id": rid, "ok": True, "result": inner}) + "\n"
                helper_proc.stdin.write(resp.encode("utf-8"))
                helper_proc.stdin.flush()

        t_ipc = threading.Thread(target=_mock_bridge_ipc)
        t_ipc.daemon = True
        t_ipc.start()

        br_dry = execute_cadence_job(
            "virtuoso-batch",
            project_dir=proj_dir,
            run_id="bridge_cwd_check",
            script=il_script,
            cell_spec="analog_lib/ota_core/schematic",
            prefer_bridge=True,
            socket_dir=sock_dir,
            dry_run=True,
        )
        dry_expr = br_dry.get("skill_expr", "")
        if "changeWorkingDir" not in dry_expr or "unwindProtect" not in dry_expr or "bridge_cwd_check" not in dry_expr:
            raise AssertionError("Expected live-bridge skill_expr to wrap load in changeWorkingDir + unwindProtect, got %r" % dry_expr)
        checks.append("live_bridge_cwd_unwind_protect_ok")

        br_res = execute_cadence_job(
            "virtuoso-batch",
            project_dir=proj_dir,
            script=il_script,
            cell_spec="analog_lib/ota_core/schematic",
            prefer_bridge=True,
            socket_dir=sock_dir,
        )
        if br_res.get("execution_mode") != "ic617_live_bridge" or br_res.get("ok") is not False or br_res.get("op_ok") is not False:
            raise AssertionError("Expected live bridge semantic op_ok=False propagation, got %r" % br_res)
        checks.append("live_bridge_semantic_op_ok_false_ok")

        helper_proc.stdin.close()
        helper_proc.wait()
        helper_proc = None

        # 6. Subprocess fatal log error scanner (`*Error*`, `ERROR (SFE-`, `FATAL`) fails closed even on rc=0
        def _mock_popen_silent_fail(cmd, cwd=None, env=None, stdout=None, stderr=None):
            lf_path = os.path.join(cwd, "spectre.log")
            _write_text_utf8(lf_path, "Simulating...\nERROR (SFE-874): Unexpected keyword in netlist.\nspectre completes with 1 error, 0 warnings.\n")
            return _DummyProc()

        subprocess.Popen = _mock_popen_silent_fail
        try:
            sf_res = execute_cadence_job(
                "spectre",
                project_dir=proj_dir,
                run_id="silent_sfe_fail",
                netlist=deck_path,
                overwrite_run=True,
                dry_run=False,
            )
        finally:
            subprocess.Popen = orig_popen
        if sf_res.get("exit_code") != 0 or sf_res.get("ok") is not False or sf_res.get("op_ok") is not False or not sf_res.get("log_errors"):
            raise AssertionError("Expected rc=0 Spectre log with ERROR (SFE-874) to fail closed, got %r" % sf_res)

        ocn_script = os.path.join(proj_dir, "bad.ocn")
        _write_text_utf8(ocn_script, 'println("ocn")\n')

        def _mock_popen_skill_err(cmd, cwd=None, env=None, stdout=None, stderr=None):
            lf_path = os.path.join(cwd, "ocean.log")
            _write_text_utf8(lf_path, "*Error* eval: unbound variable - badVar\n")
            return _DummyProc()

        subprocess.Popen = _mock_popen_skill_err
        try:
            ocn_res = execute_cadence_job(
                "ocean",
                project_dir=proj_dir,
                run_id="silent_ocn_fail",
                script=ocn_script,
                prefer_bridge=False,
                overwrite_run=True,
                dry_run=False,
            )
        finally:
            subprocess.Popen = orig_popen
        if ocn_res.get("ok") is not False or not ocn_res.get("log_errors"):
            raise AssertionError("Expected rc=0 OCEAN log with *Error* to fail closed, got %r" % ocn_res)
        checks.append("subprocess_fatal_log_scanner_fail_closed_ok")

        # 7. `cds.lib` INCLUDE path quoting: unquoted without spaces, quoted only when spaces exist
        if _format_cds_lib_path("/home/disk/eda/proj/cds.lib") != "/home/disk/eda/proj/cds.lib":
            raise AssertionError("Expected unquoted cds.lib path when no spaces exist")
        if _format_cds_lib_path("/home/disk/eda/my proj/cds.lib") != '"/home/disk/eda/my proj/cds.lib"':
            raise AssertionError("Expected quoted cds.lib path when spaces exist")
        checks.append("cds_lib_conditional_quoting_ok")

        # 8. Cryptographically bound `run_manifest.json` on clean Spectre exit (and absent on failure)
        fail_manifest = os.path.join(proj_dir, "sim", "runs", "silent_sfe_fail", "run_manifest.json")
        if os.path.exists(fail_manifest):
            raise AssertionError("Failed Spectre run must NOT write run_manifest.json")
        if not ow_res.get("run_manifest") or not os.path.isfile(ow_res["run_manifest"]):
            raise AssertionError("Expected clean Spectre run to write run_manifest.json: %r" % ow_res)

        mc_pex_net = os.path.join(proj_dir, "tb_mc_pex.scs")
        _write_text_utf8(
            mc_pex_net,
            "// View name: av_extracted\n"
            "simulator lang=spectre\n"
            "include \"/models/gpdk090.scs\" section=ss\n"
            "options1 options tnom=27 temp=125\n"
            "cpar_out (vout 0) capacitor c=5f\n"
            "mc1 montecarlo variations=all numruns=2 {\n"
            "  dcOp dc\n"
            "}\n",
        )

        def _mock_popen_with_psf(cmd, cwd=None, env=None, stdout=None, stderr=None):
            psf_d = os.path.join(cwd, "psf")
            _mkdir_p(psf_d)
            _write_text_utf8(
                os.path.join(psf_d, "dcOp.dc"),
                'HEADER\n"PSFversion" "1.00"\n"analysis type" "montecarlo"\n'
                'TYPE\n"i_sw" INT LONG\n"v_t" FLOAT DOUBLE PROP( "units" "V" )\n"i_t" FLOAT DOUBLE PROP( "units" "A" )\n'
                'SWEEP\n"iteration" "i_sw"\nTRACE\n"VDD" "v_t"\n"VDD:p" "i_t"\nVALUE\n'
                '"iteration" 1\n"VDD" 0.9\n"VDD:p" -1.0e-4\n'
                '"iteration" 2\n"VDD" 0.9\n"VDD:p" -1.1e-4\nEND\n',
            )
            _write_text_utf8(os.path.join(psf_d, "dcOp.dc.cdslck"), "LOCK\n")
            return _DummyProc()

        subprocess.Popen = _mock_popen_with_psf
        try:
            mf_res = execute_cadence_job(
                "spectre",
                project_dir=proj_dir,
                run_id="bound_manifest_run",
                netlist=mc_pex_net,
                overwrite_run=True,
                dry_run=False,
            )
        finally:
            subprocess.Popen = orig_popen

        mf_path = mf_res.get("run_manifest")
        if not mf_res.get("ok") or not mf_path or not os.path.isfile(mf_path):
            raise AssertionError("Expected bound manifest run_manifest.json, got %r" % mf_res)
        mf_fh = open(mf_path, "rb")
        try:
            mf_obj = json.loads(mf_fh.read().decode("utf-8"))
        finally:
            mf_fh.close()
        if mf_obj.get("schema") != "skill-analog.run-manifest.v1" or mf_obj.get("exit_code") != 0:
            raise AssertionError("Unexpected manifest schema/exit_code: %r" % mf_obj)
        if mf_obj.get("netlist_sha256") != _sha256_file(mc_pex_net):
            raise AssertionError("Manifest netlist_sha256 mismatch")
        if mf_obj.get("corner") != "SS" or mf_obj.get("temperature_c") != 125.0:
            raise AssertionError("Expected SS / 125.0 from netlist, got %r" % mf_obj)
        if "psf/dcOp.dc" not in mf_obj.get("psf_files", {}) or "psf/dcOp.dc.cdslck" in mf_obj.get("psf_files", {}):
            raise AssertionError("Manifest psf_files must include psf/dcOp.dc and exclude lock files: %r" % mf_obj)
        if mf_obj["psf_files"]["psf/dcOp.dc"] != _sha256_file(os.path.join(mf_res["psf_dir"], "dcOp.dc")):
            raise AssertionError("Manifest PSF SHA-256 mismatch")
        if not mf_obj.get("monte_carlo", {}).get("enabled") or "psf/dcOp.dc" not in mf_obj["monte_carlo"].get("mc_psf_files", []):
            raise AssertionError("Expected netlist-backed monte_carlo provenance: %r" % mf_obj)
        if not mf_obj.get("post_layout", {}).get("enabled"):
            raise AssertionError("Expected netlist-backed post_layout provenance: %r" % mf_obj)
        checks.append("cryptographically_bound_run_manifest_ok")

        # 8. Disk / PSF budget hygiene, low-disk block, missing save=selected guard, and prune-runs
        unfiltered_net = os.path.join(proj_dir, "tb_unfiltered_tran.scs")
        _write_text_utf8(
            unfiltered_net,
            "simulator lang=spectre\n"
            "dcOp dc\n"
            "tr1 tran stop=5u\n",
        )
        hyg_bad = _inspect_spectre_netlist_disk_hygiene(unfiltered_net)
        if not hyg_bad.get("has_waveform_analysis") or hyg_bad.get("has_save_selected") or not hyg_bad.get("warnings"):
            raise AssertionError("Expected unfiltered tran deck warning: %r" % hyg_bad)

        blk_save = execute_cadence_job(
            "spectre",
            project_dir=proj_dir,
            run_id="blocked_save",
            netlist=unfiltered_net,
            overwrite_run=True,
            require_save_selected=True,
            dry_run=False,
        )
        if blk_save.get("ok") or blk_save.get("status") != "BLOCKED_MISSING_SAVE_SELECTED":
            raise AssertionError("Expected BLOCKED_MISSING_SAVE_SELECTED, got %r" % blk_save)

        filtered_net = os.path.join(proj_dir, "tb_filtered_tran.scs")
        _write_text_utf8(
            filtered_net,
            "simulator lang=spectre\n"
            "saveOptions options save=selected\n"
            "save vout vin\n"
            "dcOp dc\n"
            "tr1 tran stop=5u\n",
        )
        hyg_ok = _inspect_spectre_netlist_disk_hygiene(filtered_net)
        if not hyg_ok.get("has_save_selected") or not hyg_ok.get("has_save_stmt") or hyg_ok.get("warnings"):
            raise AssertionError("Expected clean filtered deck, got %r" % hyg_ok)

        blk_disk = execute_cadence_job(
            "spectre",
            project_dir=proj_dir,
            run_id="blocked_low_disk",
            netlist=filtered_net,
            overwrite_run=True,
            min_free_mb=999999999.0,
            dry_run=False,
        )
        if blk_disk.get("ok") or blk_disk.get("status") != "BLOCKED_LOW_DISK_SPACE":
            raise AssertionError("Expected BLOCKED_LOW_DISK_SPACE, got %r" % blk_disk)

        prune_proj = os.path.join(tmp_root, "prune_ws")
        _write_text_utf8(os.path.join(prune_proj, "project.json"), '{"name": "prune_test"}\n')
        base_t = time.time() - 1000.0
        for idx_r, rid in enumerate(("old_run_1", "old_run_2", "kept_pinned", "new_run_3")):
            r_d = os.path.join(prune_proj, "sim", "runs", rid)
            p_d = os.path.join(r_d, "psf")
            _write_text_utf8(os.path.join(p_d, "tran.tran"), "X" * 4096)
            _write_text_utf8(os.path.join(r_d, "spectre.log"), "OK\n")
            ts_r = base_t + float(idx_r) * 100.0
            os.utime(p_d, (ts_r, ts_r))
            os.utime(r_d, (ts_r, ts_r))

        pr_dry = prune_project_runs(project_dir=prune_proj, keep=1, keep_run_ids=["kept_pinned"], psf_only=True, dry_run=True)
        if pr_dry.get("pruned_count") != 2 or not os.path.isdir(os.path.join(prune_proj, "sim", "runs", "old_run_1", "psf")):
            raise AssertionError("Unexpected dry-run prune result: %r" % pr_dry)
        pr_real = prune_project_runs(project_dir=prune_proj, keep=1, keep_run_ids=["kept_pinned"], psf_only=True, dry_run=False)
        if (
            pr_real.get("pruned_count") != 2
            or os.path.exists(os.path.join(prune_proj, "sim", "runs", "old_run_1", "psf"))
            or (not os.path.isfile(os.path.join(prune_proj, "sim", "runs", "old_run_1", "spectre.log")))
            or (not os.path.isdir(os.path.join(prune_proj, "sim", "runs", "kept_pinned", "psf")))
            or (not os.path.isdir(os.path.join(prune_proj, "sim", "runs", "new_run_3", "psf")))
        ):
            raise AssertionError("Unexpected psf-only prune result: %r" % pr_real)
        checks.append("psf_disk_budget_guard_and_prune_runs_ok")

        return {
            "ok": True,
            "tool": "cadence_exec",
            "version": RELEASE_VERSION,
            "checks_passed": len(checks),
            "checks": checks,
        }
    finally:
        if old_ext_env is None:
            os.environ.pop("SA_TEST_EXT_LIBS", None)
        else:
            os.environ["SA_TEST_EXT_LIBS"] = old_ext_env
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
  python tools/cadence_exec.py spectre --netlist <deck.scs> [--project DIR] [--run-id ID] [--overwrite-run] [--psf-ascii] [--min-free-mb MB] [--require-save-selected]
  python tools/cadence_exec.py prune-runs [--project DIR] [--keep N] [--keep-run-id ID1,ID2] [--delete-dirs] [--min-psf-mb MB] [--dry-run]
  python tools/cadence_exec.py ocean --script <run.ocn> [--project DIR] [--run-id ID] [--overwrite-run]
  python tools/cadence_exec.py virtuoso-batch --script <job.il> [--project DIR] [--cell LIB/CELL] [--write-oa]
  python tools/cadence_exec.py si [--project DIR] [--run-id ID] [--overwrite-run]
  python tools/cadence_exec.py --self-test

Options:
  --project DIR             Cadence project root (auto-detected via project.json / cds.lib if omitted)
  --run-id ID               Subdirectory name under <project>/sim/runs/<run-id>/
  --overwrite-run           Cleanly wipe stale psf/ and logs in an existing run_dir before running
  --netlist FILE            Spectre input netlist (.scs)
  --script FILE             OCEAN (.ocn) or SKILL (.il) batch script
  --cell LIB/CELL           Target OA cell for .cdslck lock filtering (`lib`, `lib/cell`, or `lib/cell/view`)
  --write-oa                Enforce strict .cdslck write lock check (auto-routes via live bridge if active)
  --psf-ascii               Pass `-format psfascii` to Spectre (default: enabled)
  --no-psf-ascii            Allow binary PSF output from Spectre
  --min-free-mb MB          Minimum free disk MB before running Spectre (default: 512; 0 disables)
  --require-save-selected   Fail closed if waveform analyses omit `options save=selected`
  --keep N                  For `prune-runs`: newest N run dirs whose `psf/` is preserved (default: 2)
  --keep-run-id LIST        For `prune-runs`: comma-separated run IDs to always preserve
  --delete-dirs             For `prune-runs`: remove entire pruned run directories instead of only `psf/`
  --min-psf-mb MB           For `prune-runs`: only prune targets >= MB (default: 0)
  --no-bridge               Disable automatic routing through `ic617_client.py` live bridge
  --socket-dir DIR          Override bridge socket directory (`~/.cache/skill-analog` default)
  --env-script FILE         Override `$HOME/cadence/env.sh` path
  --dry-run                 Validate paths/locks (or preview prune-runs) without mutating/launching
  --self-test               Run built-in adversarial self-test suite
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
            print(json.dumps({"ok": False, "tool": "cadence_exec", "error": str(exc)}, indent=2, sort_keys=True))
            return 1

    tool = args.pop(0)
    if tool == "prune-runs":
        p_prune = _SilentOptionParser(add_help_option=False)
        p_prune.add_option("-h", "--help", action="store_true", dest="help", default=False)
        p_prune.add_option("--project", type="string", dest="project", default=None)
        p_prune.add_option("--keep", type="int", dest="keep", default=2)
        p_prune.add_option("--keep-run-id", type="string", dest="keep_ids", default="")
        p_prune.add_option("--delete-dirs", action="store_true", dest="delete_dirs", default=False)
        p_prune.add_option("--min-psf-mb", type="float", dest="min_psf_mb", default=0.0)
        p_prune.add_option("--dry-run", action="store_true", dest="dry_run", default=False)
        try:
            p_opts, _ = p_prune.parse_args(args)
        except ValueError as err:
            print(json.dumps({"tool": "prune-runs", "ok": False, "error": str(err)}, indent=2, sort_keys=True))
            return 2
        if p_opts.help:
            print(HELP_TEXT)
            return 0
        try:
            keep_list = [tok.strip() for tok in (p_opts.keep_ids or "").split(",") if tok.strip()]
            res = prune_project_runs(
                project_dir=p_opts.project,
                keep=p_opts.keep,
                keep_run_ids=keep_list,
                psf_only=(not p_opts.delete_dirs),
                min_psf_mb=p_opts.min_psf_mb,
                dry_run=p_opts.dry_run,
            )
            print(json.dumps(res, indent=2, sort_keys=True))
            return 0 if res.get("ok") else 1
        except ValueError as verr:
            print(json.dumps({"tool": "prune-runs", "ok": False, "error": str(verr)}, indent=2, sort_keys=True))
            return 2
        except Exception as exc:
            print(json.dumps({"tool": "prune-runs", "ok": False, "error": str(exc)}, indent=2, sort_keys=True))
            return 1

    parser = _SilentOptionParser(add_help_option=False)
    parser.add_option("-h", "--help", action="store_true", dest="help", default=False)
    parser.add_option("--project", type="string", dest="project", default=None)
    parser.add_option("--run-id", type="string", dest="run_id", default=None)
    parser.add_option("--overwrite-run", action="store_true", dest="overwrite_run", default=False)
    parser.add_option("--netlist", type="string", dest="netlist", default=None)
    parser.add_option("--script", type="string", dest="script", default=None)
    parser.add_option("--cell", type="string", dest="cell", default=None)
    parser.add_option("--write-oa", action="store_true", dest="write_oa", default=False)
    parser.add_option("--psf-ascii", action="store_true", dest="psf_ascii", default=True)
    parser.add_option("--no-psf-ascii", action="store_false", dest="psf_ascii")
    parser.add_option("--min-free-mb", type="float", dest="min_free_mb", default=512.0)
    parser.add_option("--require-save-selected", action="store_true", dest="require_save_selected", default=False)
    parser.add_option("--no-bridge", action="store_false", dest="prefer_bridge", default=True)
    parser.add_option("--socket-dir", type="string", dest="socket_dir", default=None)
    parser.add_option("--env-script", type="string", dest="env_script", default=None)
    parser.add_option("--dry-run", action="store_true", dest="dry_run", default=False)

    try:
        opts, pos = parser.parse_args(args)
    except ValueError as err:
        print(json.dumps({"tool": tool, "ok": False, "error": str(err)}, indent=2, sort_keys=True))
        return 2

    if opts.help:
        print(HELP_TEXT)
        return 0

    netlist = opts.netlist
    script = opts.script
    extra = list(pos)
    if tool == "spectre" and not netlist and extra:
        netlist = extra.pop(0)
    elif tool in ("ocean", "virtuoso-batch") and not script and extra:
        script = extra.pop(0)

    try:
        res = execute_cadence_job(
            tool=tool,
            project_dir=opts.project,
            run_id=opts.run_id,
            netlist=netlist,
            script=script,
            cell_spec=opts.cell,
            write_oa=opts.write_oa,
            psf_ascii=opts.psf_ascii,
            prefer_bridge=opts.prefer_bridge,
            socket_dir=opts.socket_dir,
            env_script=opts.env_script,
            overwrite_run=opts.overwrite_run,
            dry_run=opts.dry_run,
            min_free_mb=opts.min_free_mb,
            require_save_selected=opts.require_save_selected,
            extra_args=extra,
        )
        print(json.dumps(res, indent=2, sort_keys=True))
        return 0 if res.get("ok") else 1
    except ValueError as verr:
        print(json.dumps({"tool": tool, "ok": False, "error": str(verr)}, indent=2, sort_keys=True))
        return 2
    except Exception as exc:
        print(json.dumps({"tool": tool, "ok": False, "error": str(exc)}, indent=2, sort_keys=True))
        return 1


if __name__ == "__main__":
    sys.exit(main())
