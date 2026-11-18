#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Standalone Zero-Dependency RHEL 6.5 (Python 2.6.6+) OTA Bootstrap & Upgrader (v4.0).

Designed to run directly on RHEL 6.5 via:
  curl -fsSL --cacert /home/disk/eda/apps/codex/support/mozilla-cacert.pem \\
    https://raw.githubusercontent.com/lmsang372k6-spec/razavi-cmos-brain/main/runtime/bootstrap_rhel6_ota.py | python -B -

Or locally with options:
  python -B bootstrap_rhel6_ota.py [--eda-root /home/disk/eda] [--home ~] [--self-test]

What it does atomically:
1. Resolves latest 40-hex commit SHA from GitHub Refs API (1.5s timeout, RHEL 6.5 CA bundle)
   and downloads runtime/manifest.json + kb/manifest.json.
2. Stages the full v4.0 SKILL-ANALOG library into a sibling .staging-* directory, preserving
   existing third-party sources/ + sources.lock.json, adding all 72 kb/diagrams/*.svg +
   diagrams-manifest.json and kb/nodes-bundle.json.gz, validating every file's SHA-256 +
   JSON syntax + Python 2.6 compile(), regenerating library.manifest.json (2026.11.18.6),
   and atomically swapping /home/disk/eda/references/SKILL-ANALOG.
3. Executes integration/install.py (when /home/disk/eda/admin/bin/eda is present),
   tools/analogctl.py verify, and tools/kb_fetch.py --sync.
4. Automatically detects and recompiles any existing Spectre PSF techsweep directories
   (~/.cache/skill-analog/techsweep-work/gpdk090_core_NN, gpdk045_core_tt, etc.) into
   ~/.cache/skill-analog/gmid-luts/ using the upgraded gpdk_techsweep.py!
"""
from __future__ import print_function

import errno
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zlib
from optparse import OptionParser

sys.dont_write_bytecode = True

RELEASE_VERSION = "2026.11.18.6"

PY2 = sys.version_info[0] < 3
if PY2:
    TEXT_TYPE = unicode  # noqa: F821
    import urllib2 as _urlreq  # noqa: F401
else:
    TEXT_TYPE = str
    import urllib.request as _urlreq  # noqa: F401

DEFAULT_API_REF_URL = "https://api.github.com/repos/lmsang372k6-spec/razavi-cmos-brain/git/refs/heads/main"
DEFAULT_RAW_SHA_TEMPLATE = "https://raw.githubusercontent.com/lmsang372k6-spec/razavi-cmos-brain/%s"
DEFAULT_RAW_MAIN_URL = "https://raw.githubusercontent.com/lmsang372k6-spec/razavi-cmos-brain/main"
DEFAULT_PAGES_URL = "https://lmsang372k6-spec.github.io/razavi-cmos-brain"
DEFAULT_CA_CANDIDATES = (
    "/home/disk/eda/apps/codex/support/mozilla-cacert.pem",
    "/home/work/cadence/tools/codex/mozilla-cacert.pem",
)


class BootstrapError(Exception):
    pass


def to_text(val):
    if val is None:
        return u""
    if isinstance(val, TEXT_TYPE):
        return val
    if isinstance(val, bytes):
        return val.decode("utf-8", "replace")
    return TEXT_TYPE(val)


def mkdir_p(path):
    if not path or os.path.isdir(path):
        return
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno != errno.EEXIST or not os.path.isdir(path):
            raise


def read_bytes(path):
    h = open(path, "rb")
    try:
        return h.read()
    finally:
        h.close()


def sha256_bytes(raw):
    d = hashlib.sha256()
    d.update(raw)
    return d.hexdigest()


def sha256_file(path):
    d = hashlib.sha256()
    h = open(path, "rb")
    try:
        while True:
            blk = h.read(131072)
            if not blk:
                break
            d.update(blk)
    finally:
        h.close()
    return d.hexdigest()


def is_offline_env():
    return os.environ.get("SKILL_ANALOG_OFFLINE", "").strip().lower() in ("1", "true", "yes", "on")


def find_ca_bundle():
    env_ca = os.environ.get("RAZAVI_CA_BUNDLE", "").strip()
    if env_ca and os.path.isfile(env_ca):
        return env_ca
    for cand in DEFAULT_CA_CANDIDATES:
        if os.path.isfile(cand):
            return cand
    return None


def find_curl():
    for d in os.environ.get("PATH", "").split(os.pathsep):
        if not d:
            continue
        for fn in ("curl", "curl.exe"):
            p = os.path.join(d, fn)
            if os.path.isfile(p):
                return p
    return None


def fetch_url_bytes(url, timeout_sec=8.0, headers=None):
    if is_offline_env():
        raise BootstrapError("Bootstrap blocked because SKILL_ANALOG_OFFLINE is enabled.")
    if os.path.isfile(url):
        return read_bytes(url)

    req_headers = {"User-Agent": "SKILL-ANALOG-RHEL6-Bootstrap/4.0"}
    if headers:
        for k, v in headers.items():
            req_headers[k] = v

    ca_bundle = find_ca_bundle()
    errors = []

    curl_bin = find_curl()
    if curl_bin and (url.lower().startswith("http://") or url.lower().startswith("https://")):
        max_t = max(2, int(round(float(timeout_sec) + 0.49)))
        conn_t = max(1, min(2, max_t))
        cmd = [curl_bin, "-fsSL", "--connect-timeout", str(conn_t), "--max-time", str(max_t)]
        if ca_bundle:
            cmd.extend(["--cacert", ca_bundle])
        for hk, hv in req_headers.items():
            cmd.extend(["-H", "%s: %s" % (hk, hv)])
        cmd.append(url)
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = proc.communicate()
        if proc.returncode == 0 and out:
            return out
        errors.append("curl rc=%s (%s)" % (proc.returncode, err.decode("utf-8", "replace").strip()[:120]))

    req = _urlreq.Request(url, headers=req_headers)
    try:
        if ca_bundle and (not PY2) and url.lower().startswith("https://"):
            resp = _urlreq.urlopen(req, timeout=float(timeout_sec), cafile=ca_bundle)
        else:
            resp = _urlreq.urlopen(req, timeout=float(timeout_sec))
        try:
            return resp.read()
        finally:
            resp.close()
    except Exception as exc:
        errors.append("urllib (%s)" % str(exc))
        raise IOError("; ".join(errors))


def resolve_bases(base_url_override=None):
    if base_url_override:
        return [to_text(base_url_override).strip().rstrip("/")], None
    commit_sha = None
    try:
        raw = fetch_url_bytes(
            DEFAULT_API_REF_URL,
            timeout_sec=1.5,
            headers={"Accept": "application/vnd.github.v3+json"},
        )
        obj = json.loads(raw.decode("utf-8-sig"))
        cand = to_text(obj.get("object", {}).get("sha") or obj.get("sha") or "").strip().lower()
        if re.match(r"^[0-9a-f]{40}$", cand):
            commit_sha = cand
    except Exception:
        commit_sha = None

    bases = []
    if commit_sha:
        bases.append((DEFAULT_RAW_SHA_TEMPLATE % commit_sha).rstrip("/"))
    bases.append(DEFAULT_RAW_MAIN_URL)
    bases.append(DEFAULT_PAGES_URL)
    return bases, commit_sha


def fetch_rel(rel_path, bases, timeout_sec=10.0):
    clean = to_text(rel_path).replace("\\", "/").lstrip("/")
    last_err = None
    for base in bases:
        if os.path.isdir(base):
            fp = os.path.join(*([base] + clean.split("/")))
            if os.path.isfile(fp):
                return read_bytes(fp), fp
            last_err = IOError("Missing local file: " + fp)
            continue
        url = "%s/%s" % (base.rstrip("/"), clean)
        try:
            return fetch_url_bytes(url, timeout_sec=timeout_sec), url
        except Exception as exc:
            last_err = exc
    if last_err is not None:
        raise last_err
    raise BootstrapError("No base URLs available for " + clean)


def map_kb_entry_to_library(kb_rel):
    if kb_rel == "kb/router-index.json":
        return "kb/router-index.json"
    if kb_rel == "kb/graph/edges.jsonl":
        return "kb/edges.jsonl"
    if kb_rel == "kb/glossary/terms-vi-en.json":
        return "kb/terms-vi-en.json"
    if kb_rel == "kb/coordinates/book-coordinates.json":
        return "kb/coordinates/book-coordinates.json"
    if kb_rel == "kb/github-skills/catalog.json":
        return "kb/github-skills/catalog.json"
    if kb_rel == "kb/nodes-bundle.json.gz":
        return "kb/nodes-bundle.json.gz"
    if kb_rel.startswith("kb/checklists/") and kb_rel.endswith(".json"):
        return "kb/checklists/" + os.path.basename(kb_rel)
    if kb_rel.startswith("kb/diagrams/") and (kb_rel.endswith(".svg") or kb_rel.endswith(".json")):
        return "kb/diagrams/" + os.path.basename(kb_rel)
    return None


def validate_blob(raw_bytes, rel_path, expected_sha="", expected_bytes=None):
    if expected_bytes is not None and len(raw_bytes) != int(expected_bytes):
        raise ValueError("Size mismatch on %s (%d != %d)" % (rel_path, len(raw_bytes), int(expected_bytes)))
    actual_sha = sha256_bytes(raw_bytes)
    if expected_sha and actual_sha != expected_sha:
        raise ValueError("SHA-256 mismatch on %s (%s != %s)" % (rel_path, actual_sha[:12], expected_sha[:12]))
    if rel_path.endswith(".json"):
        json.loads(raw_bytes.decode("utf-8-sig"))
    elif rel_path.endswith(".jsonl"):
        for ln in raw_bytes.decode("utf-8-sig").splitlines():
            if ln.strip():
                json.loads(ln)
    elif rel_path.endswith(".json.gz"):
        dec = zlib.decompress(raw_bytes, 16 + zlib.MAX_WBITS)
        json.loads(dec.decode("utf-8-sig"))
    elif rel_path.endswith(".py"):
        norm = raw_bytes.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        if not norm.endswith(b"\n"):
            norm = norm + b"\n"
        compile(norm, rel_path, "exec")
    return actual_sha


def copy_or_hardlink(src_fp, dst_fp):
    mkdir_p(os.path.dirname(dst_fp))
    if os.name != "nt" and hasattr(os, "link"):
        try:
            os.link(src_fp, dst_fp)
            return
        except OSError:
            pass
    shutil.copy2(src_fp, dst_fp)


def preserve_sources(existing_lib, staging_dir):
    count = 0
    if not existing_lib or not os.path.isdir(existing_lib):
        return count
    lock_fp = os.path.join(existing_lib, "sources.lock.json")
    if os.path.isfile(lock_fp) and not os.path.islink(lock_fp):
        copy_or_hardlink(lock_fp, os.path.join(staging_dir, "sources.lock.json"))
        count += 1
    src_root = os.path.join(existing_lib, "sources")
    if os.path.isdir(src_root) and not os.path.islink(src_root):
        for root_d, _, files in os.walk(src_root):
            rel_d = os.path.relpath(root_d, existing_lib)
            mkdir_p(os.path.join(staging_dir, rel_d))
            for fn in files:
                s_p = os.path.join(root_d, fn)
                if not os.path.islink(s_p):
                    copy_or_hardlink(s_p, os.path.join(staging_dir, rel_d, fn))
                    count += 1
    return count


def build_library_manifest(staging_dir, version_str):
    entries = []
    for root_d, dirs, files in os.walk(staging_dir):
        dirs[:] = sorted([d for d in dirs if d != "__pycache__"])
        for fn in sorted(files):
            if fn.endswith(".pyc") or fn.endswith(".pyo"):
                continue
            fp = os.path.join(root_d, fn)
            rel = os.path.relpath(fp, staging_dir).replace(os.sep, "/")
            if rel == "library.manifest.json":
                continue
            entries.append({"path": rel, "sha256": sha256_file(fp), "bytes": os.path.getsize(fp)})
    entries.sort(key=lambda x: x["path"])
    payload = {"schema": "skill-analog-library.v1", "version": version_str, "files": entries}
    return (json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode("utf-8"), len(entries)


def swap_atomic(staging_dir, target_dir):
    target_abs = os.path.abspath(target_dir)
    parent = os.path.dirname(target_abs)
    mkdir_p(parent)
    prev_dir = os.path.join(
        parent,
        ".prev-%s-%d-%d" % (os.path.basename(target_abs), os.getpid(), int(time.time() * 1000)),
    )
    existed = os.path.isdir(target_abs)
    if existed:
        os.rename(target_abs, prev_dir)
    try:
        os.rename(staging_dir, target_abs)
    except Exception:
        if existed and os.path.isdir(prev_dir) and not os.path.exists(target_abs):
            try:
                os.rename(prev_dir, target_abs)
            except OSError:
                pass
        raise
    if existed and os.path.isdir(prev_dir):
        shutil.rmtree(prev_dir)


def recompile_existing_psf_sweeps(target_lib, user_home):
    techsweep_py = os.path.join(target_lib, "tools", "gpdk_techsweep.py")
    work_root = os.path.join(user_home, ".cache", "skill-analog", "techsweep-work")
    lut_root = os.path.join(user_home, ".cache", "skill-analog", "gmid-luts")
    recompiled = []
    errors = []
    if not os.path.isfile(techsweep_py) or not os.path.isdir(work_root):
        return recompiled, errors

    preferred_names = ["gpdk090_core_NN", "gpdk045_core_tt"]
    for fn in sorted(os.listdir(work_root)):
        if fn not in preferred_names:
            preferred_names.append(fn)

    mkdir_p(lut_root)
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["HOME"] = user_home

    for name in preferred_names:
        sdir = os.path.join(work_root, name)
        if not os.path.isdir(sdir):
            continue
        has_raw = False
        for child in os.listdir(sdir):
            if child.startswith("raw"):
                has_raw = True
                break
        if not has_raw:
            continue

        pdk_val = "gpdk090"
        flavor_val = "core"
        corner_val = None
        spec_fp = os.path.join(sdir, "sweep_manifest.json")
        if not os.path.isfile(spec_fp):
            spec_fp = os.path.join(sdir, "sweep_spec.json")
        if os.path.isfile(spec_fp):
            try:
                sp = json.loads(read_bytes(spec_fp).decode("utf-8-sig"))
                pdk_val = to_text(sp.get("pdk_key") or sp.get("pdk") or pdk_val).lower()
                flavor_val = to_text(sp.get("flavor_key") or flavor_val).lower()
                corner_val = sp.get("corner")
            except Exception:
                pass
        else:
            parts = name.split("_")
            if len(parts) >= 3:
                pdk_val = parts[0].lower()
                flavor_val = parts[1].lower()
                corner_val = "_".join(parts[2:])

        cmd = [
            sys.executable,
            "-B",
            techsweep_py,
            "--pdk",
            pdk_val,
            "--flavor",
            flavor_val,
            "--compile-psf",
            sdir,
        ]
        if corner_val:
            cmd.extend(["--corner", str(corner_val)])
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        out, err = proc.communicate()
        parsed_out = {}
        try:
            parsed_out = json.loads(out.decode("utf-8", "replace"))
        except Exception:
            parsed_out = {}
        out_lut = parsed_out.get("lut_path", "")
        if proc.returncode == 0 and out_lut and os.path.isfile(out_lut):
            recompiled.append({"sweep_dir": sdir, "lut_path": out_lut, "bytes": os.path.getsize(out_lut)})
        else:
            errors.append(
                {
                    "sweep_dir": sdir,
                    "returncode": proc.returncode,
                    "error": (err.decode("utf-8", "replace") or out.decode("utf-8", "replace")).strip()[:300],
                }
            )
    return recompiled, errors


def run_bootstrap(
    eda_root="/home/disk/eda",
    target_library=None,
    user_home=None,
    base_url_override=None,
    cache_dir_override=None,
    skip_install=False,
    offline=False,
):
    if offline or is_offline_env():
        raise BootstrapError("Bootstrap cannot run when --offline or SKILL_ANALOG_OFFLINE=1 is active.")

    t0 = time.time()
    eda_abs = os.path.abspath(eda_root)
    lib_abs = os.path.abspath(target_library or os.path.join(eda_abs, "references", "SKILL-ANALOG"))
    home_abs = os.path.abspath(user_home or os.path.expanduser("~"))

    bases, commit_sha = resolve_bases(base_url_override=base_url_override)
    rt_man_bytes, rt_man_url = fetch_rel("runtime/manifest.json", bases)
    kb_man_bytes, kb_man_url = fetch_rel("kb/manifest.json", bases)
    validate_blob(rt_man_bytes, "runtime/manifest.json")
    validate_blob(kb_man_bytes, "kb/manifest.json")

    rt_man = json.loads(rt_man_bytes.decode("utf-8-sig"))
    kb_man = json.loads(kb_man_bytes.decode("utf-8-sig"))
    release_str = to_text(kb_man.get("release") or rt_man.get("release") or RELEASE_VERSION).strip()

    plan = {}
    for entry in rt_man.get("files", []):
        if not isinstance(entry, dict):
            continue
        p = to_text(entry.get("path", "")).strip()
        if not p or p == "manifest.json" or p.startswith("sources/") or p == "sources.lock.json":
            continue
        plan[p] = {
            "remote_rel": to_text(entry.get("repo_path") or ("runtime/" + p)).strip(),
            "local_rel": p,
            "sha256": to_text(entry.get("sha256", "")).strip().lower(),
            "bytes": entry.get("bytes"),
        }

    for entry in kb_man.get("files", []):
        if not isinstance(entry, dict):
            continue
        kp = to_text(entry.get("path", "")).strip()
        mapped = map_kb_entry_to_library(kp)
        if not mapped:
            continue
        plan[mapped] = {
            "remote_rel": kp,
            "local_rel": mapped,
            "sha256": to_text(entry.get("sha256", "")).strip().lower(),
            "bytes": entry.get("bytes"),
        }

    parent_dir = os.path.dirname(lib_abs)
    mkdir_p(parent_dir)
    staging_dir = os.path.join(
        parent_dir,
        ".staging-%s-%d-%d" % (os.path.basename(lib_abs), os.getpid(), int(time.time() * 1000)),
    )
    downloaded = 0
    reused = 0
    preserved_sources = 0
    manifest_total = 0

    try:
        mkdir_p(staging_dir)
        for local_rel in sorted(plan.keys()):
            spec = plan[local_rel]
            existing_fp = os.path.join(*([lib_abs] + local_rel.split("/")))
            blob = None
            if os.path.isfile(existing_fp) and not os.path.islink(existing_fp):
                try:
                    cand_raw = read_bytes(existing_fp)
                    if spec["sha256"] and sha256_bytes(cand_raw) == spec["sha256"]:
                        blob = cand_raw
                        reused += 1
                except OSError:
                    blob = None
            if blob is None:
                blob, _ = fetch_rel(spec["remote_rel"], bases)
                downloaded += 1

            validate_blob(blob, local_rel, spec["sha256"], spec["bytes"])
            dst_fp = os.path.join(*([staging_dir] + local_rel.split("/")))
            mkdir_p(os.path.dirname(dst_fp))
            wh = open(dst_fp, "wb")
            try:
                wh.write(blob)
            finally:
                wh.close()
            if local_rel.endswith(".py"):
                try:
                    os.chmod(dst_fp, 493)  # 0755
                except OSError:
                    pass
            validate_blob(read_bytes(dst_fp), local_rel, spec["sha256"], spec["bytes"])

        preserved_sources = preserve_sources(lib_abs, staging_dir)
        lib_man_raw, manifest_total = build_library_manifest(staging_dir, release_str)
        validate_blob(lib_man_raw, "library.manifest.json")
        mh = open(os.path.join(staging_dir, "library.manifest.json"), "wb")
        try:
            mh.write(lib_man_raw)
        finally:
            mh.close()

        swap_atomic(staging_dir, lib_abs)
    finally:
        if os.path.isdir(staging_dir):
            shutil.rmtree(staging_dir)

    sub_env = dict(os.environ)
    sub_env["PYTHONDONTWRITEBYTECODE"] = "1"
    if cache_dir_override:
        sub_env["RAZAVI_BRAIN_CACHE_DIR"] = os.path.abspath(cache_dir_override)

    # Post-step 1: integration/install.py (when RHEL EDA launcher is present)
    install_ran = False
    install_py = os.path.join(lib_abs, "integration", "install.py")
    eda_launcher = os.path.join(eda_abs, "admin", "bin", "eda")
    if (not skip_install) and os.path.isfile(install_py) and os.path.isfile(eda_launcher):
        p_inst = subprocess.Popen(
            [sys.executable, "-B", install_py, "--root", eda_abs, "--home", home_abs],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=sub_env,
        )
        out_i, err_i = p_inst.communicate()
        if p_inst.returncode != 0:
            raise BootstrapError(
                "install.py failed (rc=%d): %s"
                % (p_inst.returncode, (err_i or out_i).decode("utf-8", "replace").strip())
            )
        install_ran = True

    # Post-step 2: analogctl.py verify
    verify_ok = False
    analogctl_py = os.path.join(lib_abs, "tools", "analogctl.py")
    if os.path.isfile(analogctl_py) and os.path.isfile(os.path.join(lib_abs, "sources.lock.json")):
        p_ver = subprocess.Popen(
            [sys.executable, "-B", analogctl_py, "verify"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=sub_env,
        )
        out_v, err_v = p_ver.communicate()
        if p_ver.returncode != 0:
            raise BootstrapError(
                "analogctl.py verify failed (rc=%d): %s"
                % (p_ver.returncode, (out_v or err_v).decode("utf-8", "replace").strip())
            )
        verify_ok = True

    # Post-step 3: kb_fetch.py --sync (populate ~/.cache/razavi-cmos-brain/synced)
    sync_ok = False
    kb_fetch_py = os.path.join(lib_abs, "tools", "kb_fetch.py")
    if os.path.isfile(kb_fetch_py):
        sync_cmd = [sys.executable, "-B", kb_fetch_py, "--sync"]
        if base_url_override:
            sync_cmd.extend(["--base-url", base_url_override])
        p_syn = subprocess.Popen(sync_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=sub_env)
        out_s, err_s = p_syn.communicate()
        if p_syn.returncode != 0:
            raise BootstrapError(
                "kb_fetch.py --sync failed (rc=%d): %s"
                % (p_syn.returncode, (out_s or err_s).decode("utf-8", "replace").strip())
            )
        sync_ok = True

    # Post-step 4: Recompile existing PSF sweeps in ~/.cache/skill-analog/techsweep-work/
    recompiled_luts, lut_errors = recompile_existing_psf_sweeps(lib_abs, home_abs)

    return {
        "ok": True,
        "command": "bootstrap_rhel6_ota",
        "release": release_str,
        "commit_sha": commit_sha,
        "runtime_manifest_url": rt_man_url,
        "kb_manifest_url": kb_man_url,
        "target_library": lib_abs,
        "files_downloaded": downloaded,
        "files_reused_locally": reused,
        "preserved_source_files": preserved_sources,
        "library_manifest_files": manifest_total,
        "install_executed": install_ran,
        "analogctl_verify_ok": verify_ok,
        "kb_sync_ok": sync_ok,
        "recompiled_gmid_luts": recompiled_luts,
        "gmid_lut_warnings": lut_errors,
        "elapsed_ms": round((time.time() - t0) * 1000.0, 2),
    }


def _make_gz(obj):
    raw = json.dumps(obj, sort_keys=True).encode("utf-8")
    td = tempfile.mkdtemp(prefix="boot-gz-")
    try:
        fp = os.path.join(td, "n.gz")
        fh = open(fp, "wb")
        try:
            gz = gzip.GzipFile(filename="nodes-bundle.json", mode="wb", fileobj=fh, mtime=0)
            try:
                gz.write(raw)
            finally:
                gz.close()
        finally:
            fh.close()
        return read_bytes(fp)
    finally:
        shutil.rmtree(td)


def run_self_test():
    tmp_root = tempfile.mkdtemp(prefix="bootstrap-rhel6-selftest-")
    saved_env = os.environ.get("SKILL_ANALOG_OFFLINE")
    try:
        # 1. Offline guard -> exit code 2
        rc_off = main(["--offline", "--quiet-errors"])
        if rc_off != 2:
            raise AssertionError("Expected exit code 2 for --offline, got %s" % rc_off)

        if saved_env is not None:
            del os.environ["SKILL_ANALOG_OFFLINE"]

        # 2. Construct mock remote repo with real analogctl.py, ota_sync.py, kb_fetch.py + KB files
        script_dir = os.path.dirname(os.path.realpath(__file__))
        tools_src = os.path.join(script_dir, "tools")
        remote_dir = os.path.join(tmp_root, "remote_repo")

        kb_files = {
            "kb/router-index.json": json.dumps({"release": RELEASE_VERSION, "nodes": [], "diagrams": []}).encode("utf-8"),
            "kb/graph/edges.jsonl": (json.dumps({"from": "x", "to": "y", "rel": "fixes"}) + "\n").encode("utf-8"),
            "kb/glossary/terms-vi-en.json": json.dumps({"terms": []}).encode("utf-8"),
            "kb/coordinates/book-coordinates.json": json.dumps({"schema": "razavi-book-coordinates.v1"}).encode("utf-8"),
            "kb/github-skills/catalog.json": json.dumps({"schema": "razavi-github-skills-catalog.v1"}).encode("utf-8"),
            "kb/checklists/common-mos.json": json.dumps({"checklist_id": "common-mos", "checks": []}).encode("utf-8"),
            "kb/diagrams/synchronous-buck-converter.svg": b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 40"></svg>\n',
            "kb/diagrams/diagrams-manifest.json": json.dumps({"diagrams": [{"file": "synchronous-buck-converter.svg"}]}).encode("utf-8"),
            "kb/nodes-bundle.json.gz": _make_gz({"schema": "razavi-nodes-bundle.v1", "release": RELEASE_VERSION, "nodes": {}}),
        }
        kb_entries = []
        for rel_p in sorted(kb_files.keys()):
            raw = kb_files[rel_p]
            fp = os.path.join(*([remote_dir] + rel_p.split("/")))
            mkdir_p(os.path.dirname(fp))
            wh = open(fp, "wb")
            try:
                wh.write(raw)
            finally:
                wh.close()
            kb_entries.append({"path": rel_p, "bytes": len(raw), "sha256": sha256_bytes(raw)})
        km_raw = (json.dumps({"schema": "razavi-cmos-brain.manifest.v1", "release": RELEASE_VERSION, "files": kb_entries}, indent=2) + "\n").encode("utf-8")
        wh_km = open(os.path.join(remote_dir, "kb", "manifest.json"), "wb")
        try:
            wh_km.write(km_raw)
        finally:
            wh_km.close()

        rt_files = {
            "INSTALLATION.md": ("# Release %s\n" % RELEASE_VERSION).encode("utf-8"),
            "README.md": ("# SKILL-ANALOG %s\n" % RELEASE_VERSION).encode("utf-8"),
            "kb/config.json": read_bytes(os.path.join(script_dir, "kb", "config.json")),
            "kb/README.md": read_bytes(os.path.join(script_dir, "kb", "README.md")),
            "tools/ota_sync.py": read_bytes(os.path.join(tools_src, "ota_sync.py")),
            "tools/kb_fetch.py": read_bytes(os.path.join(tools_src, "kb_fetch.py")),
            "tools/analogctl.py": read_bytes(os.path.join(tools_src, "analogctl.py")),
        }
        rt_entries = []
        for rt_rel in sorted(rt_files.keys()):
            raw = rt_files[rt_rel]
            fp = os.path.join(*([remote_dir, "runtime"] + rt_rel.split("/")))
            mkdir_p(os.path.dirname(fp))
            wh = open(fp, "wb")
            try:
                wh.write(raw)
            finally:
                wh.close()
            rt_entries.append({"path": rt_rel, "repo_path": "runtime/" + rt_rel, "bytes": len(raw), "sha256": sha256_bytes(raw)})
        rm_raw = (json.dumps({"schema": "skill-analog-runtime.manifest.v1", "release": RELEASE_VERSION, "files": rt_entries}, indent=2) + "\n").encode("utf-8")
        wh_rm = open(os.path.join(remote_dir, "runtime", "manifest.json"), "wb")
        try:
            wh_rm.write(rm_raw)
        finally:
            wh_rm.close()

        # 3. Seed mock RHEL /home/disk/eda/references/SKILL-ANALOG with sources/ + sources.lock.json
        eda_dir = os.path.join(tmp_root, "eda")
        lib_dir = os.path.join(eda_dir, "references", "SKILL-ANALOG")
        home_dir = os.path.join(tmp_root, "home")
        cache_dir = os.path.join(home_dir, ".cache", "razavi-cmos-brain")
        mkdir_p(os.path.join(lib_dir, "sources", "upstream-demo"))
        s_bytes = b"# Upstream locked file\n"
        wh_s = open(os.path.join(lib_dir, "sources", "upstream-demo", "README.md"), "wb")
        try:
            wh_s.write(s_bytes)
        finally:
            wh_s.close()
        lock_payload = {
            "schema": "analog-sources-lock.v1",
            "sources": [
                {
                    "id": "upstream-demo",
                    "commit": "b" * 40,
                    "license": {"status": "MIT"},
                    "files": [
                        {
                            "path": "sources/upstream-demo/README.md",
                            "sha256": sha256_bytes(s_bytes),
                            "bytes": len(s_bytes),
                        }
                    ],
                }
            ],
            "local_generated_files": [],
        }
        wh_l = open(os.path.join(lib_dir, "sources.lock.json"), "wb")
        try:
            wh_l.write((json.dumps(lock_payload, indent=2) + "\n").encode("utf-8"))
        finally:
            wh_l.close()

        res = run_bootstrap(
            eda_root=eda_dir,
            target_library=lib_dir,
            user_home=home_dir,
            base_url_override=remote_dir,
            cache_dir_override=cache_dir,
            skip_install=True,
        )
        if not res.get("ok") or not res.get("analogctl_verify_ok") or not res.get("kb_sync_ok"):
            raise AssertionError("Bootstrap verification failed: %r" % res)
        if not os.path.isfile(os.path.join(lib_dir, "kb", "diagrams", "synchronous-buck-converter.svg")):
            raise AssertionError("SVG missing in bootstrapped library!")
        if not os.path.isfile(os.path.join(cache_dir, "synced", "sync-receipt.json")):
            raise AssertionError("Synced cache receipt missing after bootstrap!")

        return {
            "ok": True,
            "command": "self-test",
            "release": RELEASE_VERSION,
            "analogctl_verify_ok": True,
            "kb_sync_ok": True,
            "tests_passed": 3,
        }
    finally:
        if saved_env is None:
            if "SKILL_ANALOG_OFFLINE" in os.environ:
                del os.environ["SKILL_ANALOG_OFFLINE"]
        else:
            os.environ["SKILL_ANALOG_OFFLINE"] = saved_env
        shutil.rmtree(tmp_root)


def build_parser():
    p = OptionParser(usage="Usage: %prog [options]")
    p.add_option("--eda-root", dest="eda_root", default="/home/disk/eda", help="RHEL EDA root [default: %default]")
    p.add_option("--target-library", dest="target_library", default=None, help="Override target SKILL-ANALOG library path")
    p.add_option("--home", dest="user_home", default=os.path.expanduser("~"), help="User home directory")
    p.add_option("--base-url", dest="base_url", default=None, help="Override GitHub base URL or local dir")
    p.add_option("--cache-dir", dest="cache_dir", default=None, help="Override Razavi Brain cache directory")
    p.add_option("--skip-install", dest="skip_install", action="store_true", default=False, help="Skip integration/install.py")
    p.add_option("--offline", dest="offline", action="store_true", default=False, help="Block network (causes exit 2)")
    p.add_option("--self-test", dest="self_test", action="store_true", default=False, help="Run hermetic temp-dir self-test")
    p.add_option("--quiet-errors", dest="quiet_errors", action="store_true", default=False)
    return p


def main(argv=None):
    parser = build_parser()
    opts, extra = parser.parse_args(list(sys.argv[1:] if argv is None else argv))
    if extra:
        if not opts.quiet_errors:
            sys.stderr.write("Unexpected arguments: %s\n" % (" ".join(extra)))
        return 2

    if opts.self_test:
        res = run_self_test()
        print(json.dumps(res, indent=2, sort_keys=True))
        return 0 if res.get("ok") else 1

    if opts.offline or is_offline_env():
        if not opts.quiet_errors:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": "Conflicting options: bootstrap_rhel6_ota.py requires network access (--offline / SKILL_ANALOG_OFFLINE=1 is active).",
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        return 2

    try:
        res = run_bootstrap(
            eda_root=opts.eda_root,
            target_library=opts.target_library,
            user_home=opts.user_home,
            base_url_override=opts.base_url,
            cache_dir_override=opts.cache_dir,
            skip_install=opts.skip_install,
            offline=False,
        )
        print(json.dumps(res, indent=2, sort_keys=True))
        return 0 if res.get("ok") else 1
    except Exception as exc:
        if not opts.quiet_errors:
            print(json.dumps({"ok": False, "error": str(exc)}, indent=2, sort_keys=True))
        return 1


if __name__ == "__main__":
    sys.exit(main())
