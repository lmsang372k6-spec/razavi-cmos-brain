#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Local SKILL-ANALOG control & OTA management CLI; Python 2.6.6+ and Python 3 stdlib only.

Commands:
  verify              Verify pinned local sources + library.manifest.json (or runtime/manifest.json on SSOT).
  doctor              Inspect nonsecret integration/tool paths across RHEL 6.5 or Windows Desktop.
  locate [DIRECTORY]  Find a project from cwd or path, checking logical/physical roots.
  init DIRECTORY      Add absent project templates; preserve every existing file.
  sync [options]      Run fail-closed atomic OTA sync (blocked with exit 2 if --offline / SKILL_ANALOG_OFFLINE=1).
  ota-status          Inspect local OTA sync state, commit SHA, cache receipt & local SVG count (zero network).
  self-test           Run hermetic control & OTA conflict self-tests.
"""
from __future__ import print_function

import errno
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from optparse import OptionParser

sys.dont_write_bytecode = True

TOOLS_DIR = os.path.dirname(os.path.realpath(__file__))
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

import ota_sync  # noqa: E402

LIBRARY = os.path.dirname(TOOLS_DIR)
try:
    TEXT_TYPES = (basestring,)  # noqa: F821
except NameError:
    TEXT_TYPES = (str,)


class CheckError(Exception):
    pass


def emit(value):
    print(json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True))


def load_json(path):
    stream = open(path, "rb")
    try:
        return json.loads(stream.read().decode("utf-8-sig"))
    finally:
        stream.close()


def inside(path, base):
    path = os.path.normcase(os.path.realpath(path))
    base = os.path.normcase(os.path.realpath(base))
    return path == base or path.startswith(base.rstrip(os.sep) + os.sep)


def library_path(relative, base=None):
    base = base or LIBRARY
    if not isinstance(relative, TEXT_TYPES) or not relative:
        raise CheckError("A nonempty library-relative file path is required.")
    if "\\" in relative or ":" in relative or relative.startswith("/"):
        raise CheckError("Nonportable or absolute path in manifest: " + relative)
    parts = relative.split("/")
    if any(piece in ("", ".", "..") for piece in parts):
        raise CheckError("Unsafe path in manifest: " + relative)
    path = os.path.join(base, *parts)
    if not inside(path, base):
        raise CheckError("Path leaves library: " + relative)
    return path


def sha256(path):
    result = hashlib.sha256()
    stream = open(path, "rb")
    try:
        while True:
            block = stream.read(1024 * 1024)
            if not block:
                break
            result.update(block)
    finally:
        stream.close()
    return result.hexdigest()


def verify_entries(entries, base, seen):
    checked = 0
    errors = []
    if not isinstance(entries, list):
        return 0, ["Manifest files must be a JSON array."]
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("Manifest file entry must be a JSON object.")
            continue
        relative = entry.get("path")
        try:
            path = library_path(relative, base)
            if relative in seen:
                raise CheckError("Duplicate manifest file: " + relative)
            seen.add(relative)
            expected = entry.get("sha256", "")
            if not re.match(r"^[0-9a-f]{64}$", expected):
                raise CheckError("Invalid SHA256: " + relative)
            if os.path.islink(path):
                raise CheckError("Manifest file must be a regular file, not a symlink: " + relative)
            if not os.path.isfile(path):
                raise CheckError("Missing file: " + relative)
            if "bytes" in entry and os.path.getsize(path) != entry["bytes"]:
                raise CheckError("Size mismatch: " + relative)
            if sha256(path) != expected:
                raise CheckError("Hash mismatch: " + relative)
            checked += 1
        except (CheckError, IOError, OSError, TypeError) as error:
            errors.append(str(error))
    return checked, errors


def verify(base=None):
    base = base or LIBRARY
    lock_path = os.path.join(base, "sources.lock.json")
    rt_manifest_path = os.path.join(base, "manifest.json")

    # Dual-layout support:
    # 1. Full RHEL 6.5 SKILL-ANALOG library (has sources.lock.json + library.manifest.json)
    # 2. Windows Git SSOT runtime/ tree (excludes unlicensed sources/, tracked by runtime/manifest.json)
    if not os.path.isfile(lock_path) and os.path.isfile(rt_manifest_path):
        rt_man = load_json(rt_manifest_path)
        if not isinstance(rt_man, dict):
            raise CheckError("Runtime manifest must contain a JSON object.")
        rt_count, issues = verify_entries(rt_man.get("files", []), base, set())
        if not rt_man.get("files"):
            issues.append("Runtime manifest contains no files.")
        tracked = set([entry.get("path") for entry in rt_man.get("files", []) if isinstance(entry, dict)])
        tracked.add("manifest.json")
        for directory, directories, filenames in os.walk(base):
            directories[:] = [d for d in directories if d != "__pycache__"]
            for name in directories:
                if os.path.islink(os.path.join(directory, name)):
                    issues.append("Unexpected runtime directory symlink: " + name)
            for name in filenames:
                relative = os.path.relpath(os.path.join(directory, name), base).replace(os.sep, "/")
                if relative not in tracked:
                    issues.append("Untracked runtime file: " + relative)
        return {
            "command": "verify",
            "ok": not issues,
            "mode": "ssot-runtime-manifest",
            "library": os.path.realpath(base),
            "version": rt_man.get("release", ""),
            "sources": 0,
            "source_files_verified": 0,
            "library_files_verified": rt_count,
            "errors": issues,
            "warnings": [],
        }

    lock = load_json(lock_path)
    if not isinstance(lock, dict):
        raise CheckError("Source lock must contain a JSON object.")
    sources = lock.get("sources", [])
    if not isinstance(sources, list):
        raise CheckError("Source lock sources must be a JSON array.")
    errors = []
    warnings = []
    seen_ids = set()
    seen_files = set()
    checked = 0
    if lock.get("schema") != "analog-sources-lock.v1":
        errors.append("Unsupported source lock schema.")
    if not sources:
        errors.append("Source lock contains no sources.")
    for source in sources:
        if not isinstance(source, dict):
            errors.append("Source entry must be a JSON object.")
            continue
        sid = source.get("id", "")
        if not sid or sid in seen_ids:
            errors.append("Missing or duplicate source id: " + sid)
        seen_ids.add(sid)
        if not re.match(r"^[0-9a-f]{40}$", source.get("commit", "")):
            errors.append("Invalid pinned commit for " + sid)
        files = source.get("files", [])
        if not files:
            errors.append("Source has no local files: " + sid)
        amount, issues = verify_entries(files, base, seen_files)
        checked += amount
        errors.extend(issues)
        if source.get("license", {}).get("status") == "no-repository-license-found":
            warnings.append("No repository license found; do not redistribute without checking: " + sid)
    amount, issues = verify_entries(lock.get("local_generated_files", []), base, seen_files)
    checked += amount
    errors.extend(issues)
    source_root = os.path.join(base, "sources")
    if os.path.isdir(source_root):
        for directory, directories, filenames in os.walk(source_root):
            for name in directories:
                if os.path.islink(os.path.join(directory, name)):
                    errors.append("Unexpected symlink directory in sources: " + name)
            for name in filenames:
                relative = os.path.relpath(os.path.join(directory, name), base).replace(os.sep, "/")
                if relative not in seen_files:
                    errors.append("Untracked source file: " + relative)
    own_manifest = os.path.join(base, "library.manifest.json")
    own_count = 0
    if os.path.isfile(own_manifest):
        own = load_json(own_manifest)
        if not isinstance(own, dict):
            raise CheckError("Library manifest must contain a JSON object.")
        own_count, issues = verify_entries(own.get("files", []), base, set())
        if not own.get("files"):
            issues.append("Library manifest contains no files.")
        tracked = set([entry.get("path") for entry in own.get("files", []) if isinstance(entry, dict)])
        tracked.add("library.manifest.json")
        for directory, directories, filenames in os.walk(base):
            for name in directories:
                if os.path.islink(os.path.join(directory, name)):
                    issues.append("Unexpected library directory symlink: " + name)
            for name in filenames:
                relative = os.path.relpath(os.path.join(directory, name), base).replace(os.sep, "/")
                if relative not in tracked:
                    issues.append("Untracked library file: " + relative)
        errors.extend(issues)
    else:
        warnings.append("library.manifest.json is absent; only upstream source files were verified.")
    return {
        "command": "verify",
        "ok": not errors,
        "library": os.path.realpath(base),
        "sources": len(sources),
        "source_files_verified": checked,
        "library_files_verified": own_count,
        "errors": errors,
        "warnings": warnings,
    }


def nearest_marker(start):
    current = os.path.abspath(start)
    fallback = None
    while True:
        evidence = []
        for marker in ("project.json", "cds.lib"):
            if os.path.isfile(os.path.join(current, marker)):
                evidence.append(marker)
        if "project.json" in evidence:
            return {"path": current, "real_path": os.path.realpath(current), "evidence": evidence}
        if "cds.lib" in evidence and fallback is None:
            fallback = {"path": current, "real_path": os.path.realpath(current), "evidence": evidence}
        parent = os.path.dirname(current)
        if current == parent:
            return fallback
        current = parent


def locate(start=None):
    logical = os.path.abspath(start or os.getcwd())
    if not os.path.isdir(logical):
        raise CheckError("Project search starts at an existing directory: " + logical)
    real = os.path.realpath(logical)
    logical_result = nearest_marker(logical)
    real_result = nearest_marker(real)
    candidates = {}
    for result in (logical_result, real_result):
        if result:
            candidates[os.path.normcase(result["real_path"])] = result
    if len(candidates) > 1:
        raise CheckError(
            "Ambiguous project roots through logical and physical paths: " + ", ".join(sorted(candidates))
        )
    if not candidates:
        raise CheckError("No project.json or cds.lib found in this directory or its ancestors.")
    result = list(candidates.values())[0]
    result.update(
        {
            "command": "locate",
            "ok": True,
            "start": logical,
            "start_real": real,
            "project_root": result["real_path"],
        }
    )
    metadata = os.path.join(result["real_path"], "project.json")
    if os.path.isfile(metadata):
        project = load_json(metadata)
        if not isinstance(project, dict):
            raise CheckError("project.json must contain a JSON object.")
        result["project_name"] = project.get("name", project.get("project_name"))
        result["metadata_root"] = project.get("root", project.get("project_root"))
        recorded_root = result["metadata_root"]
        if recorded_root and (
            not os.path.isabs(recorded_root)
            or os.path.normcase(os.path.realpath(recorded_root)) != os.path.normcase(result["real_path"])
        ):
            result["warnings"] = [
                "Recorded metadata root differs from the discovered physical project; inspect before changing files."
            ]
    return result


def replace_tokens(value, name, root):
    if isinstance(value, TEXT_TYPES):
        return value.replace("{{PROJECT_NAME}}", name).replace("{{PROJECT_ROOT}}", root)
    if isinstance(value, list):
        return [replace_tokens(item, name, root) for item in value]
    if isinstance(value, dict):
        return dict((key, replace_tokens(item, name, root)) for key, item in value.items())
    return value


def mkdir(path):
    try:
        os.makedirs(path)
    except OSError as error:
        if error.errno != errno.EEXIST or not os.path.isdir(path):
            raise


def exclusive_write(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 420)  # 0o644
    stream = os.fdopen(fd, "wb")
    try:
        stream.write(data)
    finally:
        stream.close()


def initialize(project, base=None):
    base = base or LIBRARY
    target = os.path.abspath(project)
    physical = os.path.realpath(target)
    if physical == os.path.dirname(physical):
        raise CheckError("Cannot initialize a filesystem root as a project.")
    if inside(physical, base):
        raise CheckError("Project data must be outside the SKILL-ANALOG library.")
    if os.path.lexists(target) and not os.path.isdir(target):
        raise CheckError("Project path is not a directory: " + target)
    template = os.path.join(base, "templates", "cadence-project")
    if not os.path.isdir(template):
        raise CheckError("Cadence project templates are missing.")
    pending = []
    for directory, directories, filenames in os.walk(template):
        for name in directories + filenames:
            if os.path.islink(os.path.join(directory, name)):
                raise CheckError("Template symlinks are not allowed: " + name)
        for filename in filenames:
            source = os.path.join(directory, filename)
            relative = os.path.relpath(source, template).replace(os.sep, "/")
            destination = library_path(relative, physical)
            stream = open(source, "rb")
            try:
                raw = stream.read()
            finally:
                stream.close()
            name = os.path.basename(physical)
            if filename.endswith(".json"):
                data = replace_tokens(json.loads(raw.decode("utf-8-sig")), name, physical)
                if relative == "project.json":
                    if not isinstance(data, dict):
                        raise CheckError("project.json template must contain a JSON object.")
                    data["name"] = name
                    data["project_root"] = physical
                raw = (json.dumps(data, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode("utf-8")
            else:
                raw = replace_tokens(raw.decode("utf-8-sig"), name, physical).encode("utf-8")
            pending.append((destination, relative, raw))
    if not pending:
        raise CheckError("Cadence project template is empty.")
    mkdir(physical)
    created = []
    skipped = []
    for destination, relative, raw in pending:
        if not inside(destination, physical):
            raise CheckError("Template destination leaves project: " + relative)
        if os.path.lexists(destination):
            skipped.append(relative)
            continue
        mkdir(os.path.dirname(destination))
        try:
            exclusive_write(destination, raw)
            created.append(relative)
        except OSError as error:
            if error.errno == errno.EEXIST:
                skipped.append(relative)
            else:
                raise
    return {
        "command": "init",
        "ok": True,
        "project_root": physical,
        "created": sorted(created),
        "preserved_existing": sorted(skipped),
        "note": "Existing files are preserved. No PDK, library, cell, or approved spec is inferred.",
    }


def path_status(path):
    return {
        "path": path,
        "exists": os.path.exists(path),
        "is_link": os.path.islink(path),
        "real_path": os.path.realpath(path),
    }


def doctor():
    home = os.path.expanduser("~")
    codex_home = os.environ.get("CODEX_HOME", os.path.join(home, ".codex"))
    ssot_root = ota_sync.get_ssot_repo_root(LIBRARY)
    if os.name == "nt" and ssot_root:
        expected_skill = os.path.join(ssot_root, "skills", "analog-design")
        paths = {
            "library": LIBRARY,
            "ssot_repo": ssot_root,
            "codex_skill": os.path.join(codex_home, "skills", "analog-design"),
            "antigravity_skill": os.path.join(home, ".gemini", "config", "skills", "analog-design"),
            "codex_home": codex_home,
        }
        status = dict((key, path_status(path)) for key, path in paths.items())
        required = ("library", "ssot_repo", "codex_skill", "antigravity_skill")
        missing = [key for key in required if not status[key]["exists"]]
        integration_errors = []
        for sk_key in ("codex_skill", "antigravity_skill"):
            if status[sk_key]["exists"] and (
                os.path.normcase(os.path.realpath(paths[sk_key]))
                != os.path.normcase(os.path.realpath(expected_skill))
            ):
                integration_errors.append(sk_key + " does not resolve to " + expected_skill)
        return {
            "command": "doctor",
            "platform": "windows-ssot",
            "ok": not missing and not integration_errors,
            "python": sys.version.split()[0],
            "python_executable": sys.executable,
            "paths": status,
            "missing_integration": missing,
            "integration_errors": integration_errors,
            "runtime_status": "Windows SSOT mode: KB & Python tools active locally; Cadence runs on RHEL 6.5.",
        }

    paths = {
        "library": LIBRARY,
        "native_skill": os.path.join(home, ".agents", "skills", "analog-design"),
        "global_agents": os.path.join(codex_home, "AGENTS.md"),
        "codex_home": codex_home,
        "virtuoso": "/opt/IC617/tools/dfII/bin/virtuoso",
        "spectre": "/opt/MMSIM151/tools/bin/spectre",
        "gpdk045": "/home/disk/eda/apps/cadence/pdks/gpdk045_v_5_0/gpdk045",
        "gpdk090": "/home/disk/eda/apps/cadence/pdks/gpdk090_v4.6/libs.oa22/gpdk090",
        "cadence_projects": "/home/disk/eda/projects/cadence",
    }
    status = dict((key, path_status(path)) for key, path in paths.items())
    required = ("library", "native_skill", "global_agents", "codex_home")
    missing = [key for key in required if not status[key]["exists"]]
    skill_target = os.path.join(LIBRARY, "skills", "analog-design")
    skill_matches = os.path.normcase(os.path.realpath(paths["native_skill"])) == os.path.normcase(
        os.path.realpath(skill_target)
    )
    integration_errors = []
    if status["native_skill"]["exists"] and not skill_matches:
        integration_errors.append("Native analog-design skill does not resolve to this library.")
    return {
        "command": "doctor",
        "ok": not missing and not integration_errors,
        "python": sys.version.split()[0],
        "python_executable": sys.executable,
        "paths": status,
        "missing_integration": missing,
        "integration_errors": integration_errors,
        "native_skill_matches_library": skill_matches,
        "runtime_status": "NOT VERIFIED: no Codex model, EDA binary, license, or simulation executed.",
        "filesystem_status": "NOT CHECKED: this command does not run fsck or repair filesystems.",
    }


def run_sync_command(sync_args):
    parser = OptionParser(add_help_option=False)
    parser.add_option("--offline", action="store_true", default=False)
    parser.add_option("--base-url", dest="base_url", default=None)
    parser.add_option("--target-library", dest="target_library", default=None)
    parser.add_option("--no-library-update", dest="no_library_update", action="store_true", default=False)
    parser.add_option("--cache-dir", dest="cache_dir", default=None)
    opts, extra = parser.parse_args(sync_args)
    if extra:
        raise CheckError("Unexpected arguments to sync: " + " ".join(extra))
    eff_offline = bool(opts.offline or ota_sync.is_offline_env())
    if eff_offline:
        raise CheckError(
            "Conflicting options: analogctl.py sync cannot run when --offline or SKILL_ANALOG_OFFLINE=1 is active."
        )
    res = ota_sync.sync_now(
        library_root=LIBRARY,
        cache_dir=opts.cache_dir,
        base_url_override=opts.base_url,
        target_library=opts.target_library,
        update_library=(not opts.no_library_update),
        offline=False,
    )
    res["command"] = "sync"
    return res


def run_self_test():
    tmp_dir = tempfile.mkdtemp(prefix="analogctl-selftest-")
    saved_env = os.environ.get("SKILL_ANALOG_OFFLINE")
    try:
        # 1. sync --offline -> exit 2
        try:
            run_sync_command(["--offline"])
            raise AssertionError("Expected CheckError for sync --offline")
        except CheckError:
            pass

        # 2. SKILL_ANALOG_OFFLINE=1 -> exit 2
        os.environ["SKILL_ANALOG_OFFLINE"] = "1"
        try:
            run_sync_command([])
            raise AssertionError("Expected CheckError when SKILL_ANALOG_OFFLINE=1")
        except CheckError:
            pass
        if saved_env is None:
            del os.environ["SKILL_ANALOG_OFFLINE"]
        else:
            os.environ["SKILL_ANALOG_OFFLINE"] = saved_env

        # 3. ota-status (zero network)
        st = ota_sync.get_ota_status(library_root=LIBRARY)
        if not st.get("ok"):
            raise AssertionError("ota-status failed: %r" % st)

        # 4. init + locate in isolated temp project
        proj_dir = os.path.join(tmp_dir, "demo_ota_proj")
        init_res = initialize(proj_dir)
        if not init_res.get("ok") or "project.json" not in init_res.get("created", []):
            raise AssertionError("init failed: %r" % init_res)
        loc_res = locate(proj_dir)
        if not loc_res.get("ok"):
            raise AssertionError("locate failed: %r" % loc_res)

        return {
            "command": "self-test",
            "ok": True,
            "release": ota_sync.RELEASE_VERSION,
            "tests_passed": 4,
        }
    finally:
        if saved_env is None:
            if "SKILL_ANALOG_OFFLINE" in os.environ:
                del os.environ["SKILL_ANALOG_OFFLINE"]
        else:
            os.environ["SKILL_ANALOG_OFFLINE"] = saved_env
        shutil.rmtree(tmp_dir)


HELP = """Usage: python tools/analogctl.py COMMAND [ARGS]

verify              Verify pinned local sources + library.manifest.json (or runtime/manifest.json).
doctor              Inspect nonsecret integration/tool paths; no external programs.
locate [DIRECTORY]  Find a project from cwd or path, checking logical/physical roots.
init DIRECTORY      Add absent project templates; preserve every existing file.
sync [options]      Atomically sync KB + runtime tools via ota_sync (exit 2 if offline).
ota-status          Inspect local OTA state, synced receipt & local SVG count (no network).
self-test           Run built-in hermetic control & OTA conflict tests.
help                Show this help.

Commands emit JSON. Exit 0 means the requested check passed, 1 means a failed
check, and 2 means invalid/conflicting input or an I/O/JSON error.
"""


def main(arguments=None):
    arguments = list(sys.argv[1:] if arguments is None else arguments)
    if not arguments or arguments[0] in ("help", "-h", "--help"):
        print(HELP)
        return 0
    if arguments[0] == "--self-test":
        command = "self-test"
        arguments.pop(0)
    else:
        command = arguments.pop(0)
    try:
        if command == "verify" and not arguments:
            result = verify()
        elif command == "doctor" and not arguments:
            result = doctor()
        elif command == "locate" and len(arguments) <= 1:
            result = locate(arguments[0] if arguments else None)
        elif command == "init" and len(arguments) == 1:
            result = initialize(arguments[0])
        elif command == "sync":
            result = run_sync_command(arguments)
        elif command == "ota-status" and not arguments:
            result = ota_sync.get_ota_status(library_root=LIBRARY)
        elif command == "self-test" and not arguments:
            result = run_self_test()
        else:
            raise CheckError("Invalid command or arguments; use --help.")
        emit(result)
        return 0 if result["ok"] else 1
    except (CheckError, ota_sync.OtaConflictError, IOError, OSError, ValueError, TypeError, KeyError) as error:
        emit({"command": command, "ok": False, "error": str(error)})
        return 2


if __name__ == "__main__":
    sys.exit(main())
