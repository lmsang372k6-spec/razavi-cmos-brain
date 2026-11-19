#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Atomic Over-The-Air (OTA) Sync Engine for SKILL-ANALOG & Razavi CMOS Brain (v4.0).

100% compatible with Python 2.6.6 (RHEL 6.5) and Python 3.x standard library.
- Zero external dependencies, optparse CLI, pure LF, zero bytecode generation.
- Zero-overhead fast return (0 ms) when:
  * offline=True or SKILL_ANALOG_OFFLINE in ("1", "true", "yes", "on"), OR
  * running inside the live Windows Git SSOT checkout (.git + kb/nodes present), OR
  * last OTA check was within ttl_sec (default 60s).
- Resolves latest 40-hex commit SHA from GitHub Refs API (1.5s timeout, RHEL 6.5
  mozilla-cacert.pem support) to build immutable raw URLs with automatic fallback
  to main raw and GitHub Pages.
- Performs fail-closed Atomic Sibling Staging Swap for ~/.cache/razavi-cmos-brain/synced
  and (when writable outside SSOT) /home/disk/eda/references/SKILL-ANALOG, preserving
  sources/ + sources.lock.json and regenerating library.manifest.json (2026.11.19.1).
"""
from __future__ import print_function

import errno
import gzip
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import zlib
from optparse import OptionParser

try:
    import ssl
except ImportError:
    ssl = None

sys.dont_write_bytecode = True

RELEASE_VERSION = "2026.11.19.1"

PY2 = sys.version_info[0] < 3
if PY2:
    TEXT_TYPE = unicode  # noqa: F821
    import urllib2 as _urlreq  # noqa: F401
else:
    TEXT_TYPE = str
    import urllib.request as _urlreq  # noqa: F401

TOOLS_DIR = os.path.dirname(os.path.realpath(__file__))
LIBRARY_ROOT = os.path.dirname(TOOLS_DIR)

DEFAULT_API_REF_URL = "https://api.github.com/repos/lmsang372k6-spec/razavi-cmos-brain/git/refs/heads/main"
DEFAULT_RAW_SHA_TEMPLATE = "https://raw.githubusercontent.com/lmsang372k6-spec/razavi-cmos-brain/%s"
DEFAULT_RAW_MAIN_URL = "https://raw.githubusercontent.com/lmsang372k6-spec/razavi-cmos-brain/main"
DEFAULT_PAGES_URL = "https://lmsang372k6-spec.github.io/razavi-cmos-brain"
DEFAULT_CA_CANDIDATES = (
    "/home/disk/eda/apps/codex/support/mozilla-cacert.pem",
    "/home/work/cadence/tools/codex/mozilla-cacert.pem",
)


class OtaSyncError(Exception):
    pass


class OtaConflictError(OtaSyncError):
    pass


def to_text(value):
    if value is None:
        return u""
    if isinstance(value, TEXT_TYPE):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return TEXT_TYPE(value)


def emit_json(payload):
    txt = to_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)) + u"\n"
    raw = txt.encode("utf-8")
    if PY2:
        sys.stdout.write(raw)
    elif hasattr(sys.stdout, "buffer"):
        sys.stdout.buffer.write(raw)
    else:
        sys.stdout.write(txt)


def mkdir_p(path):
    if not path or os.path.isdir(path):
        return
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno != errno.EEXIST or not os.path.isdir(path):
            raise


def sha256_bytes(raw_bytes):
    h = hashlib.sha256()
    h.update(raw_bytes)
    return h.hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    handle = open(path, "rb")
    try:
        while True:
            chunk = handle.read(131072)
            if not chunk:
                break
            h.update(chunk)
    finally:
        handle.close()
    return h.hexdigest()


def read_bytes(path):
    handle = open(path, "rb")
    try:
        return handle.read()
    finally:
        handle.close()


def load_json_file(path):
    raw = read_bytes(path)
    return json.loads(raw.decode("utf-8-sig"))


def write_atomic_bytes(path, raw_bytes):
    parent = os.path.dirname(os.path.abspath(path))
    mkdir_p(parent)
    tmp_path = path + ".tmp-%d-%d" % (os.getpid(), int(time.time() * 1000))
    handle = open(tmp_path, "wb")
    try:
        handle.write(raw_bytes)
        handle.flush()
    finally:
        handle.close()
    try:
        if hasattr(os, "replace"):
            os.replace(tmp_path, path)
        else:
            if os.path.isfile(path):
                os.unlink(path)
            os.rename(tmp_path, path)
    except Exception:
        if os.path.isfile(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        raise


def is_offline_env():
    val = os.environ.get("SKILL_ANALOG_OFFLINE", "").strip().lower()
    return val in ("1", "true", "yes", "on")


def is_ssot_checkout(library_root=None):
    lib_real = os.path.realpath(library_root or LIBRARY_ROOT)
    if os.path.exists(os.path.join(lib_real, ".git")) and os.path.isdir(os.path.join(lib_real, "kb", "nodes")):
        return True
    if os.path.basename(lib_real).lower() == "runtime":
        repo_root = os.path.dirname(lib_real)
        if os.path.exists(os.path.join(repo_root, ".git")) and os.path.isdir(os.path.join(repo_root, "kb", "nodes")):
            return True
    return False


def get_ssot_repo_root(library_root=None):
    lib_real = os.path.realpath(library_root or LIBRARY_ROOT)
    if os.path.isdir(os.path.join(lib_real, "kb", "nodes")):
        return lib_real
    if os.path.basename(lib_real).lower() == "runtime":
        repo_root = os.path.dirname(lib_real)
        if os.path.isdir(os.path.join(repo_root, "kb", "nodes")):
            return repo_root
    return None


def load_config(library_root=None):
    lib_real = os.path.realpath(library_root or LIBRARY_ROOT)
    cfg_path = os.path.join(lib_real, "kb", "config.json")
    if os.path.isfile(cfg_path):
        try:
            return load_json_file(cfg_path)
        except Exception:
            return {}
    return {}


def _inside_dir(path_a, base_dir):
    pa = os.path.normcase(os.path.realpath(path_a))
    pb = os.path.normcase(os.path.realpath(base_dir))
    return pa == pb or pa.startswith(pb.rstrip(os.sep) + os.sep)


def get_cache_dir(cfg=None, library_root=None, cache_dir_override=None):
    lib_real = os.path.realpath(library_root or LIBRARY_ROOT)
    if cache_dir_override:
        cand = os.path.abspath(cache_dir_override)
        if _inside_dir(cand, lib_real):
            raise OtaSyncError("Cache directory must not be inside SKILL-ANALOG library: " + cand)
        return cand
    cfg = cfg or load_config(lib_real)
    env_key = cfg.get("env_cache_dir", "RAZAVI_BRAIN_CACHE_DIR")
    custom = os.environ.get(env_key, "").strip()
    if custom:
        cand = os.path.abspath(custom)
        if not _inside_dir(cand, lib_real):
            return cand
    home = os.path.expanduser("~")
    if home and home != "~" and os.path.isdir(home):
        cand = os.path.join(home, ".cache", "razavi-cmos-brain")
        if not _inside_dir(cand, lib_real):
            return cand
    uid_suffix = str(os.getuid()) if hasattr(os, "getuid") else "host"
    return os.path.join(tempfile.gettempdir(), "razavi-brain-cache-" + uid_suffix)


def load_ota_state(cache_dir):
    state_fp = os.path.join(cache_dir, "ota-state.json")
    if os.path.isfile(state_fp):
        try:
            data = load_json_file(state_fp)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {}


def save_ota_state(cache_dir, state_obj):
    state_fp = os.path.join(cache_dir, "ota-state.json")
    try:
        raw = (json.dumps(state_obj, indent=2, sort_keys=True) + "\n").encode("utf-8")
        write_atomic_bytes(state_fp, raw)
    except OSError:
        pass


def find_ca_bundle(cfg):
    env_ca = os.environ.get(cfg.get("env_ca_bundle", "RAZAVI_CA_BUNDLE"), "").strip()
    if env_ca and os.path.isfile(env_ca):
        return env_ca
    candidates = list(cfg.get("ca_bundle_candidates") or DEFAULT_CA_CANDIDATES)
    for cand in candidates:
        if cand and os.path.isfile(cand):
            return cand
    return None


def find_curl_binary():
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        if not directory:
            continue
        for name in ("curl", "curl.exe"):
            cand = os.path.join(directory, name)
            if os.path.isfile(cand):
                return cand
    return None


def fetch_url_bytes(url, timeout_sec, cfg, headers=None):
    if is_offline_env():
        raise OtaConflictError("Network access blocked by SKILL_ANALOG_OFFLINE")

    if os.path.isfile(url):
        return read_bytes(url)

    req_headers = {"User-Agent": "SKILL-ANALOG-OTA/4.0"}
    if headers:
        for k, v in headers.items():
            req_headers[k] = v

    errors = []
    ca_bundle = find_ca_bundle(cfg)

    static_bin = os.environ.get(cfg.get("env_https_client", "RAZAVI_HTTPS_CLIENT"), "").strip()
    if static_bin and os.path.isfile(static_bin) and os.access(static_bin, os.X_OK):
        proc = subprocess.Popen([static_bin, url], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, _ = proc.communicate()
        if proc.returncode == 0 and out:
            return out
        errors.append("static-client rc=%s" % proc.returncode)

    curl_bin = find_curl_binary()
    if curl_bin and (url.lower().startswith("http://") or url.lower().startswith("https://")):
        # RHEL 6.5 curl 7.19.7 requires integer seconds for --max-time / --connect-timeout
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
        err_txt = err.decode("utf-8", "replace").strip()
        errors.append("curl rc=%s (%s)" % (proc.returncode, err_txt[:120]))

    req = _urlreq.Request(url, headers=req_headers)
    try:
        if (
            ca_bundle
            and url.lower().startswith("https://")
            and ssl is not None
            and hasattr(ssl, "create_default_context")
            and ((not PY2) or sys.version_info >= (2, 7, 9))
        ):
            ctx = ssl.create_default_context(cafile=ca_bundle)
            resp = _urlreq.urlopen(req, timeout=float(timeout_sec), context=ctx)
        else:
            resp = _urlreq.urlopen(req, timeout=float(timeout_sec))
        try:
            return resp.read()
        finally:
            resp.close()
    except Exception as exc:
        errors.append("urllib (%s)" % str(exc))
        raise IOError("; ".join(errors))


def resolve_latest_commit_sha(cfg, timeout_sec=1.5):
    api_url = to_text(cfg.get("github_api_ref_url") or DEFAULT_API_REF_URL).strip()
    if not api_url:
        return None, "no_api_url"
    try:
        raw = fetch_url_bytes(
            api_url,
            timeout_sec=float(timeout_sec),
            cfg=cfg,
            headers={"Accept": "application/vnd.github.v3+json"},
        )
        payload = json.loads(raw.decode("utf-8-sig"))
        sha = ""
        if isinstance(payload, dict):
            obj = payload.get("object")
            if isinstance(obj, dict) and obj.get("sha"):
                sha = to_text(obj.get("sha")).strip().lower()
            elif payload.get("sha"):
                sha = to_text(payload.get("sha")).strip().lower()
        if re.match(r"^[0-9a-f]{40}$", sha):
            return sha, None
        return None, "invalid_sha_payload"
    except Exception as exc:
        return None, str(exc)


def resolve_remote_bases(cfg, base_url_override=None):
    if base_url_override:
        clean = to_text(base_url_override).strip().rstrip("/")
        return [clean], None, None

    env_base = os.environ.get(cfg.get("env_base_url", "RAZAVI_BRAIN_BASE_URL"), "").strip().rstrip("/")
    env_raw = os.environ.get(cfg.get("env_raw_base_url", "RAZAVI_BRAIN_RAW_URL"), "").strip().rstrip("/")
    if env_base and os.path.isdir(env_base):
        return [env_base], None, None
    if env_raw and os.path.isdir(env_raw):
        return [env_raw], None, None

    sha_timeout = float(cfg.get("sha_timeout_sec", 1.5))
    commit_sha, sha_err = resolve_latest_commit_sha(cfg, timeout_sec=sha_timeout)

    urls = []
    for candidate in (env_base, env_raw):
        if candidate and candidate not in urls:
            urls.append(candidate)

    if commit_sha:
        tmpl = to_text(cfg.get("raw_sha_template") or DEFAULT_RAW_SHA_TEMPLATE).strip()
        sha_url = (tmpl % commit_sha).rstrip("/")
        if sha_url not in urls:
            urls.append(sha_url)

    raw_main = to_text(cfg.get("raw_base_url") or DEFAULT_RAW_MAIN_URL).strip().rstrip("/")
    pages_url = to_text(cfg.get("base_url") or DEFAULT_PAGES_URL).strip().rstrip("/")
    for candidate in (raw_main, pages_url):
        if candidate and candidate not in urls:
            urls.append(candidate)

    return urls, commit_sha, sha_err


def fetch_from_bases(rel_path, base_urls, timeout_sec, cfg):
    clean_rel = to_text(rel_path).replace("\\", "/").lstrip("/")
    last_err = None
    for base in base_urls:
        if os.path.isdir(base):
            local_fp = os.path.join(*([base] + clean_rel.split("/")))
            if os.path.isfile(local_fp):
                return read_bytes(local_fp), local_fp
            last_err = IOError("Missing file in local base: " + local_fp)
            continue
        url = "%s/%s" % (base.rstrip("/"), clean_rel)
        try:
            raw = fetch_url_bytes(url, timeout_sec, cfg)
            return raw, url
        except Exception as exc:
            last_err = exc
    if last_err is not None:
        raise last_err
    raise OtaSyncError("No remote base URLs available for " + clean_rel)


def _validate_safe_rel(rel_path):
    if not rel_path or "\\" in rel_path or ":" in rel_path or rel_path.startswith("/"):
        raise OtaSyncError("Unsafe relative path in manifest: " + repr(rel_path))
    parts = rel_path.split("/")
    for part in parts:
        if part in ("", ".", ".."):
            raise OtaSyncError("Unsafe path segment in manifest: " + repr(rel_path))
    return parts


def map_kb_file_to_cache_rel(kb_rel):
    if kb_rel == "kb/router-index.json":
        return "router-index.json"
    if kb_rel == "kb/graph/edges.jsonl":
        return "edges.jsonl"
    if kb_rel == "kb/glossary/terms-vi-en.json":
        return "terms-vi-en.json"
    if kb_rel == "kb/coordinates/book-coordinates.json":
        return "coordinates/book-coordinates.json"
    if kb_rel == "kb/github-skills/catalog.json":
        return "github-skills/catalog.json"
    if kb_rel == "kb/nodes-bundle.json.gz":
        return "nodes-bundle.json.gz"
    if kb_rel.startswith("kb/checklists/") and kb_rel.endswith(".json"):
        return "checklists/" + os.path.basename(kb_rel)
    if kb_rel.startswith("kb/diagrams/") and (kb_rel.endswith(".svg") or kb_rel.endswith(".json")):
        return "diagrams/" + os.path.basename(kb_rel)
    return None


def build_cache_sync_plan(kb_manifest):
    plan = {}
    for entry in kb_manifest.get("files", []):
        if not isinstance(entry, dict):
            continue
        remote_rel = to_text(entry.get("path", "")).strip()
        cache_rel = map_kb_file_to_cache_rel(remote_rel)
        if not cache_rel:
            continue
        _validate_safe_rel(remote_rel)
        _validate_safe_rel(cache_rel)
        plan[cache_rel] = {
            "remote_rel": remote_rel,
            "local_rel": cache_rel,
            "sha256": to_text(entry.get("sha256", "")).strip().lower(),
            "bytes": entry.get("bytes"),
        }
    return plan


def build_library_sync_plan(kb_manifest, runtime_manifest):
    plan = {}
    if isinstance(runtime_manifest, dict):
        for entry in runtime_manifest.get("files", []):
            if not isinstance(entry, dict):
                continue
            rt_rel = to_text(entry.get("path", "")).strip()
            if not rt_rel or rt_rel == "manifest.json" or rt_rel.startswith("sources/") or rt_rel == "sources.lock.json":
                continue
            _validate_safe_rel(rt_rel)
            remote_rel = to_text(entry.get("repo_path") or ("runtime/" + rt_rel)).strip()
            _validate_safe_rel(remote_rel)
            plan[rt_rel] = {
                "remote_rel": remote_rel,
                "local_rel": rt_rel,
                "sha256": to_text(entry.get("sha256", "")).strip().lower(),
                "bytes": entry.get("bytes"),
            }

    for entry in kb_manifest.get("files", []):
        if not isinstance(entry, dict):
            continue
        remote_rel = to_text(entry.get("path", "")).strip()
        cache_rel = map_kb_file_to_cache_rel(remote_rel)
        if not cache_rel:
            continue
        lib_rel = "kb/" + cache_rel
        _validate_safe_rel(lib_rel)
        plan[lib_rel] = {
            "remote_rel": remote_rel,
            "local_rel": lib_rel,
            "sha256": to_text(entry.get("sha256", "")).strip().lower(),
            "bytes": entry.get("bytes"),
        }
    return plan


def _assert_inside_staging(dst_path, staging_dir, rel_label):
    st_real = os.path.normcase(os.path.realpath(staging_dir))
    dst_real = os.path.normcase(os.path.realpath(dst_path))
    if dst_real == st_real or not dst_real.startswith(st_real.rstrip(os.sep) + os.sep):
        raise OtaSyncError("Destination path escapes staging directory: " + repr(rel_label))


def validate_staged_bytes(raw_bytes, rel_path, expected_sha="", expected_bytes=None, verify_sha=True):
    if expected_bytes is not None and len(raw_bytes) != int(expected_bytes):
        raise ValueError(
            "Byte size mismatch for %s (%d != %d)" % (rel_path, len(raw_bytes), int(expected_bytes))
        )
    actual_sha = sha256_bytes(raw_bytes)
    if verify_sha:
        norm_sha = to_text(expected_sha or "").strip().lower()
        if not re.match(r"^[0-9a-f]{64}$", norm_sha):
            raise ValueError("Missing or invalid expected SHA-256 in manifest for " + to_text(rel_path))
        if actual_sha != norm_sha:
            raise ValueError(
                "SHA-256 mismatch for %s (%s != %s)" % (rel_path, actual_sha[:12], norm_sha[:12])
            )

    if rel_path.endswith(".json"):
        json.loads(raw_bytes.decode("utf-8-sig"))
    elif rel_path.endswith(".jsonl"):
        for ln in raw_bytes.decode("utf-8-sig").splitlines():
            if ln.strip():
                json.loads(ln)
    elif rel_path.endswith(".json.gz"):
        decompressed = zlib.decompress(raw_bytes, 16 + zlib.MAX_WBITS)
        json.loads(decompressed.decode("utf-8-sig"))
    elif rel_path.endswith(".py"):
        # Python 2.6 compile() requires LF line endings and trailing newline
        src_norm = raw_bytes.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        if not src_norm.endswith(b"\n"):
            src_norm = src_norm + b"\n"
        compile(src_norm, rel_path, "exec")
    return actual_sha


def _copy_or_link_regular_file(src_path, dst_path):
    mkdir_p(os.path.dirname(dst_path))
    if os.name != "nt" and hasattr(os, "link"):
        try:
            os.link(src_path, dst_path)
            return
        except OSError:
            pass
    shutil.copy2(src_path, dst_path)


def _preserve_sources_into_staging(existing_lib_dir, staging_dir):
    preserved = 0
    if not existing_lib_dir or not os.path.isdir(existing_lib_dir):
        return preserved
    lock_src = os.path.join(existing_lib_dir, "sources.lock.json")
    if os.path.isfile(lock_src) and not os.path.islink(lock_src):
        _copy_or_link_regular_file(lock_src, os.path.join(staging_dir, "sources.lock.json"))
        preserved += 1
    sources_src = os.path.join(existing_lib_dir, "sources")
    if os.path.isdir(sources_src) and not os.path.islink(sources_src):
        for root_d, dirs, files in os.walk(sources_src):
            rel_d = os.path.relpath(root_d, existing_lib_dir)
            mkdir_p(os.path.join(staging_dir, rel_d))
            for fn in files:
                s_fp = os.path.join(root_d, fn)
                if os.path.islink(s_fp):
                    continue
                d_fp = os.path.join(staging_dir, rel_d, fn)
                _copy_or_link_regular_file(s_fp, d_fp)
                preserved += 1
    return preserved


def generate_library_manifest_bytes(staging_dir, version_str):
    entries = []
    for root_d, dirs, files in os.walk(staging_dir):
        dirs[:] = sorted([d for d in dirs if d != "__pycache__"])
        for fn in sorted(files):
            if fn.endswith(".pyc") or fn.endswith(".pyo"):
                continue
            full_fp = os.path.join(root_d, fn)
            rel_p = os.path.relpath(full_fp, staging_dir).replace(os.sep, "/")
            if rel_p == "library.manifest.json":
                continue
            entries.append(
                {
                    "path": rel_p,
                    "sha256": sha256_file(full_fp),
                    "bytes": os.path.getsize(full_fp),
                }
            )
    entries.sort(key=lambda item: item["path"])
    manifest_obj = {
        "schema": "skill-analog-library.v1",
        "version": version_str,
        "files": entries,
    }
    return (json.dumps(manifest_obj, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode("utf-8"), len(entries)


def _is_link_or_junction(path):
    if not os.path.lexists(path):
        return False
    if os.path.islink(path):
        return True
    try:
        st = os.lstat(path)
        attrs = getattr(st, "st_file_attributes", 0)
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024)
        if attrs & reparse_flag:
            return True
    except OSError:
        pass
    return False


def _chmod_retry_onerror(func, path, _exc_info):
    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
    except OSError:
        pass
    func(path)


def _remove_tree_or_link(path):
    if not os.path.lexists(path):
        return
    if _is_link_or_junction(path):
        try:
            os.unlink(path)
            return
        except OSError:
            if os.path.lexists(path):
                os.rmdir(path)
            return
    if os.path.isdir(path):
        if sys.version_info >= (3, 12):
            shutil.rmtree(path, onexc=_chmod_retry_onerror)
        else:
            shutil.rmtree(path, onerror=_chmod_retry_onerror)
        return
    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        pass
    os.unlink(path)


def _is_pid_alive(pid):
    if not pid or int(pid) <= 0:
        return False
    if os.name == "posix":
        try:
            os.kill(int(pid), 0)
            return True
        except OSError as err:
            return err.errno == errno.EPERM
    return True


def _is_swap_lock_stale(lock_path, stale_sec):
    now = time.time()
    try:
        raw = read_bytes(lock_path)
        meta = json.loads(raw.decode("utf-8", "replace"))
        pid = int(meta.get("pid", 0) or 0)
        ts = float(meta.get("ts", 0.0) or 0.0)
        if os.name == "posix" and pid > 0 and not _is_pid_alive(pid):
            return True
        if ts > 0.0 and (now - ts) > stale_sec:
            return True
    except Exception:
        try:
            if (now - os.path.getmtime(lock_path)) > stale_sec:
                return True
        except OSError:
            return True
    return False


def _acquire_swap_lock(lock_path, stale_sec=120.0, timeout_sec=15.0):
    deadline = time.time() + float(timeout_sec)
    payload = (json.dumps({"pid": os.getpid(), "ts": time.time()}) + "\n").encode("utf-8")
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 384)
            try:
                os.write(fd, payload)
            finally:
                os.close(fd)
            return
        except OSError as err:
            if err.errno != errno.EEXIST:
                raise
            if _is_swap_lock_stale(lock_path, stale_sec):
                try:
                    os.unlink(lock_path)
                    continue
                except OSError:
                    pass
            if time.time() >= deadline:
                raise OtaSyncError("Timed out waiting for atomic swap lock: " + lock_path)
            time.sleep(0.05)


def _release_swap_lock(lock_path):
    try:
        if os.path.lexists(lock_path):
            os.unlink(lock_path)
    except OSError:
        pass


def swap_directory_atomic(staging_dir, target_dir, stale_lock_sec=120.0):
    target_abs = os.path.abspath(target_dir)
    parent_dir = os.path.dirname(target_abs)
    mkdir_p(parent_dir)
    lock_path = os.path.join(parent_dir, ".swap-%s.lock" % os.path.basename(target_abs))
    _acquire_swap_lock(lock_path, stale_sec=stale_lock_sec)
    try:
        backup_dir = os.path.join(
            parent_dir,
            ".prev-%s-%d-%d" % (os.path.basename(target_abs), os.getpid(), int(time.time() * 1000)),
        )
        had_existing = os.path.lexists(target_abs)
        if had_existing:
            if _is_link_or_junction(target_abs):
                _remove_tree_or_link(target_abs)
                had_existing = False
            else:
                os.rename(target_abs, backup_dir)
        try:
            os.rename(staging_dir, target_abs)
        except Exception:
            if had_existing and os.path.lexists(backup_dir) and not os.path.lexists(target_abs):
                try:
                    os.rename(backup_dir, target_abs)
                except OSError:
                    pass
            raise
        if had_existing and os.path.lexists(backup_dir):
            _remove_tree_or_link(backup_dir)
    finally:
        _release_swap_lock(lock_path)


def _find_reusable_local_bytes(expected_sha, candidate_paths):
    if not expected_sha:
        return None
    for cand in candidate_paths:
        if cand and os.path.isfile(cand) and not os.path.islink(cand):
            try:
                raw = read_bytes(cand)
                if sha256_bytes(raw) == expected_sha:
                    return raw
            except OSError:
                continue
    return None


def _is_writable_target_library(target_lib):
    if not target_lib:
        return False
    abs_lib = os.path.abspath(target_lib)
    if is_ssot_checkout(abs_lib):
        return False
    parent = os.path.dirname(abs_lib)
    if not parent or not os.path.isdir(parent) or not os.access(parent, os.W_OK):
        return False
    if os.path.isdir(abs_lib) and not os.access(abs_lib, os.W_OK):
        return False
    return True


def check_remote_updates(
    library_root=None,
    cache_dir=None,
    base_url_override=None,
    offline=False,
):
    if offline or is_offline_env():
        raise OtaConflictError("Cannot check remote updates while offline mode is active.")

    lib_real = os.path.realpath(library_root or LIBRARY_ROOT)
    cfg = load_config(lib_real)
    timeout_sec = float(cfg.get("http_timeout_sec", 8))
    c_dir = get_cache_dir(cfg=cfg, library_root=lib_real, cache_dir_override=cache_dir)
    synced_dir = os.path.join(c_dir, "synced")

    base_urls, commit_sha, sha_err = resolve_remote_bases(cfg, base_url_override=base_url_override)
    kb_man_bytes, kb_man_url = fetch_from_bases("kb/manifest.json", base_urls, timeout_sec, cfg)
    kb_manifest = json.loads(kb_man_bytes.decode("utf-8-sig"))

    rt_manifest = None
    rt_man_url = None
    try:
        rt_bytes, rt_man_url = fetch_from_bases("runtime/manifest.json", base_urls, timeout_sec, cfg)
        rt_manifest = json.loads(rt_bytes.decode("utf-8-sig"))
    except Exception:
        rt_manifest = None

    cache_plan = build_cache_sync_plan(kb_manifest)
    changed_cache = []
    for local_rel in sorted(cache_plan.keys()):
        spec = cache_plan[local_rel]
        cand_paths = [
            os.path.join(*([synced_dir] + local_rel.split("/"))),
            os.path.join(*([lib_real, "kb"] + local_rel.split("/"))),
        ]
        if _find_reusable_local_bytes(spec["sha256"], cand_paths) is None:
            changed_cache.append(local_rel)

    changed_lib = []
    if rt_manifest and _is_writable_target_library(lib_real):
        lib_plan = build_library_sync_plan(kb_manifest, rt_manifest)
        for local_rel in sorted(lib_plan.keys()):
            spec = lib_plan[local_rel]
            cand_paths = [os.path.join(*([lib_real] + local_rel.split("/")))]
            if _find_reusable_local_bytes(spec["sha256"], cand_paths) is None:
                changed_lib.append(local_rel)

    return {
        "ok": True,
        "command": "check",
        "commit_sha": commit_sha,
        "sha_resolution_note": sha_err,
        "manifest_url": kb_man_url,
        "runtime_manifest_url": rt_man_url,
        "remote_release": kb_manifest.get("release", ""),
        "cache_files_total": len(cache_plan),
        "cache_files_changed": len(changed_cache),
        "changed_cache_paths": changed_cache[:50],
        "library_writable": _is_writable_target_library(lib_real),
        "library_files_changed": len(changed_lib),
        "changed_library_paths": changed_lib[:50],
        "up_to_date": (len(changed_cache) == 0 and len(changed_lib) == 0),
    }


def sync_now(
    library_root=None,
    cache_dir=None,
    base_url_override=None,
    target_library=None,
    update_library=True,
    offline=False,
):
    if offline or is_offline_env():
        raise OtaConflictError(
            "Network sync blocked because --offline or SKILL_ANALOG_OFFLINE is enabled."
        )

    t0 = time.time()
    lib_real = os.path.realpath(library_root or LIBRARY_ROOT)
    cfg = load_config(lib_real)
    verify_sha = bool(cfg.get("verify_sha256", True))
    timeout_sec = float(cfg.get("http_timeout_sec", 8))
    c_dir = get_cache_dir(cfg=cfg, library_root=lib_real, cache_dir_override=cache_dir)
    synced_dir = os.path.join(c_dir, "synced")
    mkdir_p(c_dir)

    base_urls, commit_sha, sha_err = resolve_remote_bases(cfg, base_url_override=base_url_override)
    if not base_urls:
        raise OtaSyncError("No remote GitHub base URLs configured.")

    kb_man_bytes, kb_man_url = fetch_from_bases("kb/manifest.json", base_urls, timeout_sec, cfg)
    validate_staged_bytes(kb_man_bytes, "kb/manifest.json", verify_sha=False)
    kb_manifest = json.loads(kb_man_bytes.decode("utf-8-sig"))
    remote_release = to_text(kb_manifest.get("release") or RELEASE_VERSION).strip()

    rt_man_bytes = None
    rt_manifest = None
    rt_man_url = None
    try:
        rt_man_bytes, rt_man_url = fetch_from_bases("runtime/manifest.json", base_urls, timeout_sec, cfg)
        validate_staged_bytes(rt_man_bytes, "runtime/manifest.json", verify_sha=False)
        rt_manifest = json.loads(rt_man_bytes.decode("utf-8-sig"))
    except Exception:
        rt_man_bytes = None
        rt_manifest = None

    downloaded_blobs = {}
    downloaded_count = [0]
    reused_count = [0]

    def obtain_verified_blob(spec, local_candidates):
        r_rel = spec["remote_rel"]
        exp_sha = spec["sha256"]
        exp_bytes = spec["bytes"]
        if r_rel in downloaded_blobs:
            raw = downloaded_blobs[r_rel]
            validate_staged_bytes(raw, spec["local_rel"], exp_sha, exp_bytes, verify_sha)
            return raw

        reused = _find_reusable_local_bytes(exp_sha, local_candidates)
        if reused is not None:
            validate_staged_bytes(reused, spec["local_rel"], exp_sha, exp_bytes, verify_sha)
            reused_count[0] += 1
            downloaded_blobs[r_rel] = reused
            return reused

        raw, _ = fetch_from_bases(r_rel, base_urls, timeout_sec, cfg)
        validate_staged_bytes(raw, spec["local_rel"], exp_sha, exp_bytes, verify_sha)
        downloaded_blobs[r_rel] = raw
        downloaded_count[0] += 1
        return raw

    # 1. Stage & atomically swap user synced cache (~/.cache/razavi-cmos-brain/synced)
    cache_plan = build_cache_sync_plan(kb_manifest)
    cache_staging = os.path.join(
        c_dir,
        ".staging-synced-%d-%d" % (os.getpid(), int(time.time() * 1000)),
    )
    try:
        mkdir_p(cache_staging)
        for local_rel in sorted(cache_plan.keys()):
            spec = cache_plan[local_rel]
            cands = [
                os.path.join(*([synced_dir] + local_rel.split("/"))),
                os.path.join(*([lib_real, "kb"] + local_rel.split("/"))),
            ]
            blob = obtain_verified_blob(spec, cands)
            dst_fp = os.path.join(*([cache_staging] + local_rel.split("/")))
            _assert_inside_staging(dst_fp, cache_staging, local_rel)
            mkdir_p(os.path.dirname(dst_fp))
            h = open(dst_fp, "wb")
            try:
                h.write(blob)
            finally:
                h.close()
            # Re-verify written file on disk inside staging before swap
            disk_raw = read_bytes(dst_fp)
            validate_staged_bytes(disk_raw, local_rel, spec["sha256"], spec["bytes"], verify_sha)

        # Write manifests & sync receipt inside cache_staging
        h_man = open(os.path.join(cache_staging, "manifest.json"), "wb")
        try:
            h_man.write(kb_man_bytes)
        finally:
            h_man.close()

        if rt_man_bytes is not None:
            h_rt = open(os.path.join(cache_staging, "runtime-manifest.json"), "wb")
            try:
                h_rt.write(rt_man_bytes)
            finally:
                h_rt.close()

        receipt = {
            "ok": True,
            "schema": "razavi-ota-receipt.v4",
            "synced_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "commit_sha": commit_sha,
            "manifest_url": kb_man_url,
            "runtime_manifest_url": rt_man_url,
            "release": remote_release,
            "domain_count": kb_manifest.get("domain_count"),
            "node_count": kb_manifest.get("node_count"),
            "razavi_core_node_count": kb_manifest.get("razavi_core_node_count"),
            "pmic_node_count": kb_manifest.get("pmic_node_count"),
            "ams_node_count": kb_manifest.get("ams_node_count"),
            "eda_domain_node_count": kb_manifest.get("eda_domain_node_count"),
            "razavi_node_count": kb_manifest.get("razavi_node_count"),
            "skill_node_count": kb_manifest.get("skill_node_count"),
            "edge_count": kb_manifest.get("edge_count"),
            "diagram_count": kb_manifest.get("diagram_count"),
            "checklist_count": kb_manifest.get("checklist_count"),
            "glossary_count": kb_manifest.get("glossary_count"),
            "book_section_count": kb_manifest.get("book_section_count"),
            "book_equation_count": kb_manifest.get("book_equation_count"),
            "github_repo_count": kb_manifest.get("github_repo_count"),
            "cache_dir": synced_dir,
            "files_synced": len(cache_plan),
            "files_downloaded": downloaded_count[0],
            "files_reused_locally": reused_count[0],
        }
        rec_bytes = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8")
        h_rec = open(os.path.join(cache_staging, "sync-receipt.json"), "wb")
        try:
            h_rec.write(rec_bytes)
        finally:
            h_rec.close()

        swap_directory_atomic(cache_staging, synced_dir)
    finally:
        if os.path.lexists(cache_staging):
            _remove_tree_or_link(cache_staging)

    # 2. Optionally stage & atomically swap writable SKILL-ANALOG runtime library
    lib_target = os.path.abspath(target_library) if target_library else lib_real
    library_updated = False
    library_files_tracked = 0
    preserved_source_files = 0
    if update_library and rt_manifest is not None and (target_library or _is_writable_target_library(lib_target)):
        if is_ssot_checkout(lib_target):
            raise OtaSyncError("Refusing to overwrite live Git SSOT checkout: " + lib_target)
        lib_parent = os.path.dirname(lib_target)
        mkdir_p(lib_parent)
        lib_plan = build_library_sync_plan(kb_manifest, rt_manifest)
        lib_staging = os.path.join(
            lib_parent,
            ".staging-%s-%d-%d" % (os.path.basename(lib_target), os.getpid(), int(time.time() * 1000)),
        )
        try:
            mkdir_p(lib_staging)
            for local_rel in sorted(lib_plan.keys()):
                spec = lib_plan[local_rel]
                cands = [
                    os.path.join(*([lib_target] + local_rel.split("/"))),
                    os.path.join(*([synced_dir] + local_rel[3:].split("/"))) if local_rel.startswith("kb/") else "",
                ]
                blob = obtain_verified_blob(spec, cands)
                dst_fp = os.path.join(*([lib_staging] + local_rel.split("/")))
                _assert_inside_staging(dst_fp, lib_staging, local_rel)
                mkdir_p(os.path.dirname(dst_fp))
                h = open(dst_fp, "wb")
                try:
                    h.write(blob)
                finally:
                    h.close()
                if local_rel.endswith(".py"):
                    try:
                        os.chmod(dst_fp, 493)  # 0755
                    except OSError:
                        pass
                disk_raw = read_bytes(dst_fp)
                validate_staged_bytes(disk_raw, local_rel, spec["sha256"], spec["bytes"], verify_sha)

            preserved_source_files = _preserve_sources_into_staging(lib_target, lib_staging)
            lib_man_bytes, library_files_tracked = generate_library_manifest_bytes(lib_staging, remote_release)
            validate_staged_bytes(lib_man_bytes, "library.manifest.json", verify_sha=False)
            h_lm = open(os.path.join(lib_staging, "library.manifest.json"), "wb")
            try:
                h_lm.write(lib_man_bytes)
            finally:
                h_lm.close()

            swap_directory_atomic(lib_staging, lib_target)
            library_updated = True
        finally:
            if os.path.lexists(lib_staging):
                _remove_tree_or_link(lib_staging)

    now_ts = time.time()
    elapsed_ms = round((now_ts - t0) * 1000.0, 2)
    state_obj = {
        "schema": "razavi-ota-state.v4",
        "last_checked_at": now_ts,
        "last_synced_at": now_ts,
        "last_synced_utc": receipt["synced_at_utc"],
        "commit_sha": commit_sha,
        "release": remote_release,
        "library_updated": library_updated,
        "library_target": lib_target if library_updated else None,
        "files_downloaded": downloaded_count[0],
        "files_reused_locally": reused_count[0],
        "last_error": None,
    }
    save_ota_state(c_dir, state_obj)

    receipt["library_updated"] = library_updated
    receipt["library_target"] = lib_target if library_updated else None
    receipt["library_files_tracked"] = library_files_tracked
    receipt["preserved_source_files"] = preserved_source_files
    receipt["files_downloaded"] = downloaded_count[0]
    receipt["files_reused_locally"] = reused_count[0]
    receipt["elapsed_ms"] = elapsed_ms
    if sha_err and not commit_sha:
        receipt["sha_fallback_note"] = sha_err
    return receipt


def maybe_auto_sync(
    ttl_sec=60,
    offline=False,
    library_root=None,
    cache_dir=None,
    base_url_override=None,
    update_library=True,
):
    if offline:
        return {"ok": True, "action": "noop_offline_arg", "elapsed_ms": 0.0}
    if is_offline_env():
        return {"ok": True, "action": "noop_offline_env", "elapsed_ms": 0.0}

    lib_real = os.path.realpath(library_root or LIBRARY_ROOT)
    if base_url_override is None and is_ssot_checkout(lib_real):
        return {"ok": True, "action": "noop_ssot", "elapsed_ms": 0.0}

    cfg = load_config(lib_real)
    eff_ttl = float(cfg.get("ota_ttl_sec", 60) if ttl_sec is None else ttl_sec)
    c_dir = get_cache_dir(cfg=cfg, library_root=lib_real, cache_dir_override=cache_dir)
    state = load_ota_state(c_dir)
    now = time.time()
    last_chk = float(state.get("last_checked_at", 0.0) or 0.0)
    if eff_ttl > 0.0 and (now - last_chk) < eff_ttl:
        return {
            "ok": True,
            "action": "noop_ttl",
            "age_sec": round(now - last_chk, 2),
            "ttl_sec": eff_ttl,
            "release": state.get("release", ""),
        }

    try:
        res = sync_now(
            library_root=lib_real,
            cache_dir=c_dir,
            base_url_override=base_url_override,
            update_library=update_library,
            offline=False,
        )
        res["action"] = "synced"
        return res
    except Exception as exc:
        state["last_checked_at"] = time.time()
        state["last_error"] = str(exc)
        save_ota_state(c_dir, state)
        return {
            "ok": False,
            "action": "degraded_local_fallback",
            "error": str(exc),
        }


def get_ota_status(library_root=None, cache_dir=None):
    lib_real = os.path.realpath(library_root or LIBRARY_ROOT)
    cfg = load_config(lib_real)
    c_dir = get_cache_dir(cfg=cfg, library_root=lib_real, cache_dir_override=cache_dir)
    synced_dir = os.path.join(c_dir, "synced")
    state = load_ota_state(c_dir)
    receipt_fp = os.path.join(synced_dir, "sync-receipt.json")
    receipt = load_json_file(receipt_fp) if os.path.isfile(receipt_fp) else None
    ssot = is_ssot_checkout(lib_real)
    ssot_root = get_ssot_repo_root(lib_real) if ssot else None
    diag_dir = (
        os.path.join(ssot_root, "kb", "diagrams")
        if ssot_root
        else (
            os.path.join(synced_dir, "diagrams")
            if os.path.isdir(os.path.join(synced_dir, "diagrams"))
            else os.path.join(lib_real, "kb", "diagrams")
        )
    )
    svg_count = 0
    if os.path.isdir(diag_dir):
        svg_count = len([fn for fn in os.listdir(diag_dir) if fn.endswith(".svg")])
    return {
        "ok": True,
        "command": "ota-status",
        "client_release": cfg.get("release", RELEASE_VERSION),
        "library_root": lib_real,
        "is_ssot_git_checkout": ssot,
        "ssot_repo_root": ssot_root,
        "offline_env_active": is_offline_env(),
        "library_writable_for_ota": _is_writable_target_library(lib_real),
        "cache_dir": c_dir,
        "synced_dir_exists": os.path.isdir(synced_dir),
        "local_svg_diagrams": svg_count,
        "ota_ttl_sec": cfg.get("ota_ttl_sec", 60),
        "github_api_ref_url": cfg.get("github_api_ref_url", DEFAULT_API_REF_URL),
        "state": state,
        "last_receipt": receipt,
    }


def _make_gzip_json_bytes(obj):
    raw = json.dumps(obj, sort_keys=True).encode("utf-8")
    tmp_dir = tempfile.mkdtemp(prefix="ota-gz-")
    try:
        fp = os.path.join(tmp_dir, "b.gz")
        raw_f = open(fp, "wb")
        try:
            if sys.version_info >= (2, 7):
                gz = gzip.GzipFile(filename="nodes-bundle.json", mode="wb", fileobj=raw_f, mtime=0)
            else:
                gz = gzip.GzipFile(filename="nodes-bundle.json", mode="wb", fileobj=raw_f)
            try:
                gz.write(raw)
            finally:
                gz.close()
        finally:
            raw_f.close()
        return read_bytes(fp)
    finally:
        _remove_tree_or_link(tmp_dir)


def _write_mock_remote_tree(root_dir, version_str, router_extra_note=""):
    kb_files_data = {
        "kb/router-index.json": json.dumps(
            {"schema": "razavi-cmos-brain.router-index.v1", "release": version_str, "note": router_extra_note, "nodes": []},
            indent=2,
        ).encode("utf-8"),
        "kb/graph/edges.jsonl": (json.dumps({"from": "a", "to": "b", "rel": "upgrades_to"}) + "\n").encode("utf-8"),
        "kb/glossary/terms-vi-en.json": json.dumps({"terms": [{"id": "T001", "en": "MOS", "vi": "MOS"}]}).encode("utf-8"),
        "kb/coordinates/book-coordinates.json": json.dumps({"schema": "razavi-book-coordinates.v1", "sections": []}).encode("utf-8"),
        "kb/github-skills/catalog.json": json.dumps({"schema": "razavi-github-skills-catalog.v1", "repositories": []}).encode("utf-8"),
        "kb/checklists/common-mos.json": json.dumps({"checklist_id": "common-mos", "process_agnostic": True, "checks": []}).encode("utf-8"),
        "kb/diagrams/folded-cascode-ota.svg": b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50"><rect width="10" height="10"/></svg>\n',
        "kb/diagrams/diagrams-manifest.json": json.dumps({"diagrams": [{"file": "folded-cascode-ota.svg"}]}).encode("utf-8"),
        "kb/nodes-bundle.json.gz": _make_gzip_json_bytes({"schema": "razavi-nodes-bundle.v1", "release": version_str, "nodes": {}}),
    }
    kb_man_entries = []
    for rel_p in sorted(kb_files_data.keys()):
        raw = kb_files_data[rel_p]
        full_p = os.path.join(*([root_dir] + rel_p.split("/")))
        mkdir_p(os.path.dirname(full_p))
        h = open(full_p, "wb")
        try:
            h.write(raw)
        finally:
            h.close()
        kb_man_entries.append({"path": rel_p, "bytes": len(raw), "sha256": sha256_bytes(raw)})

    kb_man = {
        "schema": "razavi-cmos-brain.manifest.v1",
        "release": version_str,
        "domain_count": 10,
        "node_count": 162,
        "diagram_count": 1,
        "checklist_count": 1,
        "files": kb_man_entries,
    }
    kb_man_raw = (json.dumps(kb_man, indent=2, sort_keys=True) + "\n").encode("utf-8")
    h_km = open(os.path.join(root_dir, "kb", "manifest.json"), "wb")
    try:
        h_km.write(kb_man_raw)
    finally:
        h_km.close()

    rt_files_data = {
        "INSTALLATION.md": ("# Release %s\n" % version_str).encode("utf-8"),
        "README.md": ("# SKILL-ANALOG %s\n" % version_str).encode("utf-8"),
        "kb/config.json": json.dumps({"release": version_str, "verify_sha256": True}, indent=2).encode("utf-8"),
        "kb/README.md": b"# KB\n",
        "tools/sample_helper.py": b"from __future__ import print_function\nimport sys\nsys.dont_write_bytecode = True\nVAL = 42\n",
    }
    rt_man_entries = []
    for rt_rel in sorted(rt_files_data.keys()):
        raw = rt_files_data[rt_rel]
        full_p = os.path.join(*([root_dir, "runtime"] + rt_rel.split("/")))
        mkdir_p(os.path.dirname(full_p))
        h = open(full_p, "wb")
        try:
            h.write(raw)
        finally:
            h.close()
        rt_man_entries.append(
            {
                "path": rt_rel,
                "repo_path": "runtime/" + rt_rel,
                "bytes": len(raw),
                "sha256": sha256_bytes(raw),
            }
        )

    rt_man = {
        "schema": "skill-analog-runtime.manifest.v1",
        "release": version_str,
        "file_count": len(rt_man_entries),
        "files": rt_man_entries,
    }
    rt_man_raw = (json.dumps(rt_man, indent=2, sort_keys=True) + "\n").encode("utf-8")
    h_rm = open(os.path.join(root_dir, "runtime", "manifest.json"), "wb")
    try:
        h_rm.write(rt_man_raw)
    finally:
        h_rm.close()


def run_self_test():
    tmp_root = tempfile.mkdtemp(prefix="ota-sync-selftest-")
    saved_offline = os.environ.get("SKILL_ANALOG_OFFLINE")
    try:
        # 1. Conflict check: --sync + --offline -> exit code 2
        rc_conflict = main(["--sync", "--offline", "--quiet-errors"])
        if rc_conflict != 2:
            raise AssertionError("Expected exit code 2 for --sync --offline, got %s" % rc_conflict)

        # 2. SKILL_ANALOG_OFFLINE=1 blocks sync (exit 2) and makes maybe_auto_sync 0ms noop
        os.environ["SKILL_ANALOG_OFFLINE"] = "1"
        rc_env_block = main(["--sync", "--quiet-errors"])
        if rc_env_block != 2:
            raise AssertionError("Expected exit code 2 when SKILL_ANALOG_OFFLINE=1 with --sync, got %s" % rc_env_block)
        auto_off = maybe_auto_sync(ttl_sec=0, offline=False)
        if auto_off.get("action") != "noop_offline_env":
            raise AssertionError("Expected noop_offline_env, got %r" % auto_off)

        if saved_offline is None:
            del os.environ["SKILL_ANALOG_OFFLINE"]
        else:
            os.environ["SKILL_ANALOG_OFFLINE"] = saved_offline
        if is_offline_env():
            os.environ["SKILL_ANALOG_OFFLINE"] = "0"

        # 3. SSOT Git checkout fast noop check
        mock_ssot = os.path.join(tmp_root, "ssot_repo")
        mkdir_p(os.path.join(mock_ssot, ".git"))
        mkdir_p(os.path.join(mock_ssot, "kb", "nodes"))
        mkdir_p(os.path.join(mock_ssot, "runtime", "tools"))
        ssot_res = maybe_auto_sync(ttl_sec=0, offline=False, library_root=os.path.join(mock_ssot, "runtime"))
        if ssot_res.get("action") != "noop_ssot":
            raise AssertionError("Expected noop_ssot on git checkout, got %r" % ssot_res)

        # 4. Atomic staging swap + sources/ preservation + library.manifest.json regeneration
        remote_dir = os.path.join(tmp_root, "remote")
        _write_mock_remote_tree(remote_dir, RELEASE_VERSION, router_extra_note="v1")

        mock_lib = os.path.join(tmp_root, "SKILL-ANALOG")
        mock_cache = os.path.join(tmp_root, "cache")
        mkdir_p(os.path.join(mock_lib, "sources", "demo-repo"))
        src_readme = b"# Preserved third-party source\n"
        h_sr = open(os.path.join(mock_lib, "sources", "demo-repo", "README.md"), "wb")
        try:
            h_sr.write(src_readme)
        finally:
            h_sr.close()
        lock_obj = {
            "schema": "analog-sources-lock.v1",
            "sources": [
                {
                    "id": "demo-repo",
                    "commit": "a" * 40,
                    "license": {"status": "MIT"},
                    "files": [
                        {
                            "path": "sources/demo-repo/README.md",
                            "sha256": sha256_bytes(src_readme),
                            "bytes": len(src_readme),
                        }
                    ],
                }
            ],
            "local_generated_files": [],
        }
        h_lk = open(os.path.join(mock_lib, "sources.lock.json"), "wb")
        try:
            h_lk.write((json.dumps(lock_obj, indent=2) + "\n").encode("utf-8"))
        finally:
            h_lk.close()

        rec1 = sync_now(
            library_root=mock_lib,
            cache_dir=mock_cache,
            base_url_override=remote_dir,
            target_library=mock_lib,
            update_library=True,
        )
        if not rec1.get("ok") or not rec1.get("library_updated"):
            raise AssertionError("Initial atomic sync failed: %r" % rec1)
        if not os.path.isfile(os.path.join(mock_lib, "sources.lock.json")):
            raise AssertionError("sources.lock.json was not preserved!")
        if not os.path.isfile(os.path.join(mock_lib, "kb", "diagrams", "folded-cascode-ota.svg")):
            raise AssertionError("SVG diagram was not synced to library/kb/diagrams/!")
        lib_man = load_json_file(os.path.join(mock_lib, "library.manifest.json"))
        if lib_man.get("version") != RELEASE_VERSION:
            raise AssertionError("Unexpected library.manifest.json version: %r" % lib_man.get("version"))

        # Verify TTL fast return
        ttl_res = maybe_auto_sync(
            ttl_sec=60,
            offline=False,
            library_root=mock_lib,
            cache_dir=mock_cache,
            base_url_override=remote_dir,
        )
        if ttl_res.get("action") != "noop_ttl":
            raise AssertionError("Expected noop_ttl within 60s window, got %r" % ttl_res)

        # 5. Delta sync: update only router-index.json, verify only 1 file downloaded
        _write_mock_remote_tree(remote_dir, RELEASE_VERSION, router_extra_note="v2-delta")
        rec2 = sync_now(
            library_root=mock_lib,
            cache_dir=mock_cache,
            base_url_override=remote_dir,
            target_library=mock_lib,
            update_library=True,
        )
        if rec2.get("files_downloaded") != 1 or rec2.get("files_reused_locally", 0) < 8:
            raise AssertionError("Expected delta download=1 & reused>=8, got %r" % rec2)

        # 6. Adversarial rollback test: remote manifest advertises a new SHA-256, but remote payload is tampered
        expected_v3_bytes = b'{"release": "v3-expected"}\n'
        tampered_v3_bytes = b'{"release": "v3-tampered"}\n'
        h_bad = open(os.path.join(remote_dir, "kb", "router-index.json"), "wb")
        try:
            h_bad.write(tampered_v3_bytes)
        finally:
            h_bad.close()
        kb_man_fp = os.path.join(remote_dir, "kb", "manifest.json")
        kb_man_obj = load_json_file(kb_man_fp)
        for item in kb_man_obj["files"]:
            if item["path"] == "kb/router-index.json":
                item["sha256"] = sha256_bytes(expected_v3_bytes)
                item["bytes"] = len(expected_v3_bytes)
        h_km_bad = open(kb_man_fp, "wb")
        try:
            h_km_bad.write((json.dumps(kb_man_obj, indent=2) + "\n").encode("utf-8"))
        finally:
            h_km_bad.close()

        rolled_back = False
        try:
            sync_now(
                library_root=mock_lib,
                cache_dir=mock_cache,
                base_url_override=remote_dir,
                target_library=mock_lib,
                update_library=True,
            )
        except ValueError as exc:
            if "mismatch" in str(exc).lower():
                rolled_back = True
        if not rolled_back:
            raise AssertionError("Tampered SHA-256 was not rejected by atomic staging!")

        # Verify previous v2-delta state is 100% intact and zero .staging-* dirs remain
        preserved_router = load_json_file(os.path.join(mock_cache, "synced", "router-index.json"))
        if preserved_router.get("note") != "v2-delta":
            raise AssertionError("Target cache was corrupted despite failed staging: %r" % preserved_router)
        leftover = [
            n for n in (os.listdir(mock_cache) + os.listdir(tmp_root))
            if n.startswith(".staging-") or n.startswith(".prev-")
        ]
        if leftover:
            raise AssertionError("Leftover staging/backup dirs after rollback: %r" % leftover)

        # 7. Adversarial Python syntax rollback test: valid SHA-256 in manifest, broken Python syntax
        _write_mock_remote_tree(remote_dir, RELEASE_VERSION, router_extra_note="v3")
        broken_py = b"def broken_func(:\n    pass\n"
        broken_fp = os.path.join(remote_dir, "runtime", "tools", "sample_helper.py")
        h_bp = open(broken_fp, "wb")
        try:
            h_bp.write(broken_py)
        finally:
            h_bp.close()
        rt_man_fp = os.path.join(remote_dir, "runtime", "manifest.json")
        rt_man_obj = load_json_file(rt_man_fp)
        for item in rt_man_obj["files"]:
            if item["path"] == "tools/sample_helper.py":
                item["sha256"] = sha256_bytes(broken_py)
                item["bytes"] = len(broken_py)
        h_rm2 = open(rt_man_fp, "wb")
        try:
            h_rm2.write((json.dumps(rt_man_obj, indent=2) + "\n").encode("utf-8"))
        finally:
            h_rm2.close()

        syntax_caught = False
        try:
            sync_now(
                library_root=mock_lib,
                cache_dir=mock_cache,
                base_url_override=remote_dir,
                target_library=mock_lib,
                update_library=True,
            )
        except SyntaxError:
            syntax_caught = True
        if not syntax_caught:
            raise AssertionError("Broken Python syntax in staged runtime tool was not rejected!")
        good_py = read_bytes(os.path.join(mock_lib, "tools", "sample_helper.py"))
        if b"VAL = 42" not in good_py:
            raise AssertionError("Existing SKILL-ANALOG library tool was corrupted!")

        # 8. Empty SHA-256 rejection under verify_sha=True (fail-closed)
        empty_sha_caught = False
        try:
            validate_staged_bytes(b'{"tampered": true}\n', "router-index.json", expected_sha="", verify_sha=True)
        except ValueError:
            empty_sha_caught = True
        if not empty_sha_caught:
            raise AssertionError("Empty expected_sha was not rejected under verify_sha=True!")

        # 9. Path traversal rejection in manifest (`../../escaped_pwn.txt`)
        _write_mock_remote_tree(remote_dir, RELEASE_VERSION, router_extra_note="v4")
        rt_man_obj = load_json_file(rt_man_fp)
        rt_man_obj["files"].append(
            {
                "path": "../../escaped_pwn.txt",
                "repo_path": "runtime/README.md",
                "sha256": sha256_bytes(b"ESCAPED\n"),
                "bytes": 8,
            }
        )
        h_rm_trav = open(rt_man_fp, "wb")
        try:
            h_rm_trav.write((json.dumps(rt_man_obj, indent=2) + "\n").encode("utf-8"))
        finally:
            h_rm_trav.close()
        trav_caught = False
        try:
            sync_now(
                library_root=mock_lib,
                cache_dir=mock_cache,
                base_url_override=remote_dir,
                target_library=mock_lib,
                update_library=True,
            )
        except OtaSyncError:
            trav_caught = True
        if not trav_caught or os.path.exists(os.path.join(tmp_root, "escaped_pwn.txt")):
            raise AssertionError("Path traversal manifest entry was not blocked!")

        # 10. Python 3 SSL `context=` path (no deprecated/removed `cafile=` kwarg to urlopen)
        if ssl is not None and hasattr(ssl, "create_default_context") and ((not PY2) or sys.version_info >= (2, 7, 9)):
            fake_ca = os.path.join(tmp_root, "mock_ca.pem")
            h_ca = open(fake_ca, "wb")
            try:
                h_ca.write(b"FAKE_CA\n")
            finally:
                h_ca.close()
            ssl_calls = {}
            orig_find_curl = globals()["find_curl_binary"]
            orig_create_ctx = ssl.create_default_context
            orig_urlopen = _urlreq.urlopen

            class _DummyResp(object):
                def read(self):
                    return b"HTTPS_CTX_OK"

                def close(self):
                    pass

            def _mock_create_ctx(cafile=None):
                ssl_calls["cafile"] = cafile
                return "MOCK_SSL_CTX"

            def _mock_urlopen(req, timeout=None, **kwargs):
                if "cafile" in kwargs:
                    raise TypeError("urlopen() got an unexpected keyword argument 'cafile'")
                ssl_calls["context"] = kwargs.get("context")
                return _DummyResp()

            globals()["find_curl_binary"] = lambda: None
            ssl.create_default_context = _mock_create_ctx
            _urlreq.urlopen = _mock_urlopen
            try:
                got_https = fetch_url_bytes("https://example.invalid/test.json", 3.0, {"ca_bundle_candidates": [fake_ca]})
            finally:
                globals()["find_curl_binary"] = orig_find_curl
                ssl.create_default_context = orig_create_ctx
                _urlreq.urlopen = orig_urlopen
            if got_https != b"HTTPS_CTX_OK" or ssl_calls.get("cafile") != fake_ca or ssl_calls.get("context") != "MOCK_SSL_CTX":
                raise AssertionError("SSL context= path check failed: %r" % ssl_calls)

        # 11. `swap_directory_atomic` stale lock recovery, read-only file cleanup & symlink/junction safety
        swap_base = os.path.join(tmp_root, "swap_test")
        mkdir_p(swap_base)
        swap_target = os.path.join(swap_base, "target_dir")
        mkdir_p(swap_target)
        ro_fp = os.path.join(swap_target, "readonly.txt")
        h_ro = open(ro_fp, "wb")
        try:
            h_ro.write(b"RO_OLD\n")
        finally:
            h_ro.close()
        os.chmod(ro_fp, stat.S_IREAD)
        stale_lock = os.path.join(swap_base, ".swap-target_dir.lock")
        h_sl = open(stale_lock, "wb")
        try:
            h_sl.write((json.dumps({"pid": 999999, "ts": time.time() - 999.0}) + "\n").encode("utf-8"))
        finally:
            h_sl.close()
        swap_stage = os.path.join(swap_base, ".staging-new")
        mkdir_p(swap_stage)
        h_nw = open(os.path.join(swap_stage, "fresh.txt"), "wb")
        try:
            h_nw.write(b"FRESH_OK\n")
        finally:
            h_nw.close()
        swap_directory_atomic(swap_stage, swap_target, stale_lock_sec=10.0)
        if os.path.lexists(stale_lock) or not os.path.isfile(os.path.join(swap_target, "fresh.txt")):
            raise AssertionError("swap_directory_atomic failed stale lock recovery or read-only cleanup")

        return {
            "ok": True,
            "command": "self-test",
            "release": RELEASE_VERSION,
            "tests_passed": 11,
            "verified": [
                "sync_offline_conflict_exit_2",
                "skill_analog_offline_env_block",
                "ssot_git_checkout_0ms_noop",
                "atomic_staging_swap_with_sources_and_manifest",
                "ttl_60s_zero_network_guard",
                "delta_sha256_single_file_download",
                "sha256_and_python_compile_rollback_safety",
                "empty_sha256_rejected_fail_closed",
                "manifest_path_traversal_rejected",
                "py3_ssl_context_cafile_compat",
                "swap_lock_recovery_and_readonly_cleanup",
            ],
        }
    finally:
        if saved_offline is None:
            if "SKILL_ANALOG_OFFLINE" in os.environ:
                del os.environ["SKILL_ANALOG_OFFLINE"]
        else:
            os.environ["SKILL_ANALOG_OFFLINE"] = saved_offline
        _remove_tree_or_link(tmp_root)


def build_parser():
    parser = OptionParser(
        usage="Usage: %prog [--sync | --status | --check | --auto | --self-test] [options]"
    )
    parser.add_option("--sync", action="store_true", default=False, help="Run atomic OTA sync now")
    parser.add_option("--status", action="store_true", default=False, help="Show local OTA status without network")
    parser.add_option("--check", action="store_true", default=False, help="Check GitHub SHA & manifests for updates")
    parser.add_option("--auto", action="store_true", default=False, help="Run TTL-gated background auto-sync")
    parser.add_option("--offline", action="store_true", default=False, help="Disallow all network requests")
    parser.add_option("--ttl", type="float", default=60.0, help="Auto-sync TTL in seconds (default: 60)")
    parser.add_option("--base-url", dest="base_url", default=None, help="Override remote base URL or local dir")
    parser.add_option("--target-library", dest="target_library", default=None, help="Explicit SKILL-ANALOG dir to update")
    parser.add_option("--no-library-update", dest="no_library_update", action="store_true", default=False, help="Sync user cache only")
    parser.add_option("--cache-dir", dest="cache_dir", default=None, help="Override user cache directory")
    parser.add_option("--self-test", dest="self_test", action="store_true", default=False, help="Run hermetic OTA self-tests")
    parser.add_option("--quiet-errors", dest="quiet_errors", action="store_true", default=False, help="Suppress stderr in self-tests")
    return parser


def main(argv=None):
    parser = build_parser()
    opts, pos = parser.parse_args(list(sys.argv[1:] if argv is None else argv))
    if pos:
        if not opts.quiet_errors:
            sys.stderr.write("Unexpected positional arguments: %s\n" % (" ".join(pos)))
        return 2

    if opts.self_test:
        res = run_self_test()
        emit_json(res)
        return 0 if res.get("ok") else 1

    # Strict --offline / SKILL_ANALOG_OFFLINE=1 precedence check FIRST
    eff_offline = bool(opts.offline or is_offline_env())
    if (opts.sync or opts.check) and eff_offline:
        msg = (
            "Conflicting options: --sync/--check cannot run when --offline or SKILL_ANALOG_OFFLINE=1 is active."
        )
        if not opts.quiet_errors:
            emit_json({"ok": False, "error": msg})
        return 2

    try:
        if opts.sync:
            res = sync_now(
                cache_dir=opts.cache_dir,
                base_url_override=opts.base_url,
                target_library=opts.target_library,
                update_library=(not opts.no_library_update),
                offline=eff_offline,
            )
            emit_json(res)
            return 0 if res.get("ok") else 1
        if opts.check:
            res = check_remote_updates(
                cache_dir=opts.cache_dir,
                base_url_override=opts.base_url,
                offline=eff_offline,
            )
            emit_json(res)
            return 0 if res.get("ok") else 1
        if opts.auto:
            res = maybe_auto_sync(
                ttl_sec=opts.ttl,
                offline=eff_offline,
                cache_dir=opts.cache_dir,
                base_url_override=opts.base_url,
                update_library=(not opts.no_library_update),
            )
            emit_json(res)
            return 0
        # Default to --status
        res = get_ota_status(cache_dir=opts.cache_dir)
        emit_json(res)
        return 0
    except OtaConflictError as exc:
        if not opts.quiet_errors:
            emit_json({"ok": False, "error": str(exc)})
        return 2
    except Exception as exc:
        if not opts.quiet_errors:
            emit_json({"ok": False, "error": str(exc)})
        return 1


if __name__ == "__main__":
    sys.exit(main())
