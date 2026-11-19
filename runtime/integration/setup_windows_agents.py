#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Windows Multi-Agent Directory Junction Installer & Verifier (Codex Desktop + Antigravity Desktop).

100% Python 2.6.6+ and Python 3 standard-library compatible (`optparse` CLI, zero external deps).

Creates and verifies zero-latency (`0 ms`) NTFS Directory Junctions (`mklink /J`):
  - %USERPROFILE%\\.codex\\skills\\analog-design        -> <repo>\\skills\\analog-design
  - %USERPROFILE%\\.gemini\\config\\skills\\analog-design -> <repo>\\skills\\analog-design

Usage:
  python -B runtime/integration/setup_windows_agents.py --install
  python -B runtime/integration/setup_windows_agents.py --verify
  python -B runtime/integration/setup_windows_agents.py --self-test
"""
from __future__ import print_function

import errno
import json
import os
from optparse import OptionParser
import shutil
import stat
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True

_THIS_DIR = os.path.dirname(os.path.realpath(__file__))
_RUNTIME_DIR = os.path.dirname(_THIS_DIR)
_DEFAULT_REPO_ROOT = os.path.dirname(_RUNTIME_DIR)


def mkdir_p(path):
    if not path or os.path.isdir(path):
        return
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno != errno.EEXIST or not os.path.isdir(path):
            raise


def norm_real(path):
    return os.path.normcase(os.path.realpath(path))


def is_reparse_junction(path):
    if not os.path.lexists(path):
        return False
    if os.path.islink(path):
        return True
    try:
        st = os.lstat(path)
        attrs = getattr(st, "st_file_attributes", 0)
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if attrs & reparse_flag:
            return True
    except OSError:
        pass
    if os.path.isdir(path):
        return os.path.normcase(os.path.abspath(path)) != norm_real(path)
    return False


def remove_junction_only(link_path):
    """Remove an NTFS directory junction without touching target directory contents."""
    if os.name == "nt":
        proc = subprocess.Popen(
            ["cmd", "/c", "rmdir", link_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        _, err = proc.communicate()
        if proc.returncode != 0 and os.path.lexists(link_path):
            raise OSError("Failed to remove junction %s: %s" % (link_path, err.decode("utf-8", "replace").strip()))
    else:
        os.unlink(link_path)


def create_junction(link_path, target_dir):
    mkdir_p(os.path.dirname(link_path))
    if os.name == "nt":
        proc = subprocess.Popen(
            ["cmd", "/c", "mklink", "/J", link_path, target_dir],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out, err = proc.communicate()
        if proc.returncode != 0:
            msg = (err or out).decode("utf-8", "replace").strip()
            raise OSError("mklink /J failed for %s -> %s: %s" % (link_path, target_dir, msg))
    else:
        os.symlink(target_dir, link_path)


def default_agent_targets(user_home=None):
    home = os.path.abspath(user_home or os.path.expanduser("~"))
    return [
        {
            "agent": "codex-desktop",
            "link_path": os.path.join(home, ".codex", "skills", "analog-design"),
        },
        {
            "agent": "antigravity-desktop",
            "link_path": os.path.join(home, ".gemini", "config", "skills", "analog-design"),
        },
    ]


def resolve_ssot_skill_dir(repo_root=None):
    root = os.path.abspath(repo_root or _DEFAULT_REPO_ROOT)
    cand = os.path.join(root, "skills", "analog-design")
    if os.path.isfile(os.path.join(cand, "SKILL.md")):
        return cand
    alt = os.path.join(_RUNTIME_DIR, "skills", "analog-design")
    if os.path.isfile(os.path.join(alt, "SKILL.md")):
        return alt
    raise ValueError("SKILL.md not found under %s" % cand)


def install_junctions(repo_root=None, user_home=None):
    target_skill = resolve_ssot_skill_dir(repo_root)
    target_norm = norm_real(target_skill)
    results = []

    for spec in default_agent_targets(user_home=user_home):
        lpath = spec["link_path"]
        action = "unchanged"
        if os.path.lexists(lpath):
            if is_reparse_junction(lpath):
                if os.path.exists(lpath) and norm_real(lpath) == target_norm:
                    action = "already_linked"
                else:
                    remove_junction_only(lpath)
                    create_junction(lpath, target_skill)
                    action = "relinked"
            else:
                raise ValueError(
                    "Refusing to overwrite non-junction directory/file at %s; move it aside first." % lpath
                )
        else:
            create_junction(lpath, target_skill)
            action = "created"

        skill_md = os.path.join(lpath, "SKILL.md")
        ok = os.path.isfile(skill_md) and (norm_real(lpath) == target_norm)
        results.append({
            "agent": spec["agent"],
            "action": action,
            "link_path": lpath,
            "resolved_target": os.path.realpath(lpath),
            "skill_md_readable": os.path.isfile(skill_md),
            "ok": ok,
        })

    return {
        "command": "install",
        "ok": all([r["ok"] for r in results]),
        "ssot_skill_dir": os.path.realpath(target_skill),
        "agents": results,
    }


def verify_junctions(repo_root=None, user_home=None):
    target_skill = resolve_ssot_skill_dir(repo_root)
    target_norm = norm_real(target_skill)
    results = []
    errors = []

    for spec in default_agent_targets(user_home=user_home):
        lpath = spec["link_path"]
        exists = os.path.exists(lpath)
        reparse = is_reparse_junction(lpath)
        resolved = os.path.realpath(lpath) if exists else None
        skill_md = os.path.join(lpath, "SKILL.md")
        readable = os.path.isfile(skill_md)
        matched = bool(exists and reparse and norm_real(lpath) == target_norm and readable)
        if not matched:
            errors.append("%s junction invalid or missing at %s" % (spec["agent"], lpath))
        results.append({
            "agent": spec["agent"],
            "link_path": lpath,
            "is_junction_or_symlink": reparse,
            "resolved_target": resolved,
            "skill_md_readable": readable,
            "ok": matched,
        })

    return {
        "command": "verify",
        "ok": len(errors) == 0,
        "ssot_skill_dir": os.path.realpath(target_skill),
        "agents": results,
        "errors": errors,
    }


def run_self_test():
    tmp = tempfile.mkdtemp(prefix="win_agents_selftest_")
    try:
        fake_repo = os.path.join(tmp, "repo")
        fake_skill = os.path.join(fake_repo, "skills", "analog-design")
        mkdir_p(fake_skill)
        fh = open(os.path.join(fake_skill, "SKILL.md"), "wb")
        try:
            fh.write(b"---\nname: analog-design\n---\n# Test\n")
        finally:
            fh.close()

        fake_home = os.path.join(tmp, "home")
        inst1 = install_junctions(repo_root=fake_repo, user_home=fake_home)
        assert inst1["ok"] is True, inst1
        ver1 = verify_junctions(repo_root=fake_repo, user_home=fake_home)
        assert ver1["ok"] is True, ver1

        # Idempotent re-run
        inst2 = install_junctions(repo_root=fake_repo, user_home=fake_home)
        assert inst2["ok"] is True, inst2
        assert all([a["action"] == "already_linked" for a in inst2["agents"]]), inst2

        # Non-junction collision refusal
        bad_home = os.path.join(tmp, "bad_home")
        real_dir = os.path.join(bad_home, ".codex", "skills", "analog-design")
        mkdir_p(real_dir)
        refused = False
        try:
            install_junctions(repo_root=fake_repo, user_home=bad_home)
        except ValueError:
            refused = True
        assert refused, "Expected ValueError on non-junction collision"
        ver_bad = verify_junctions(repo_root=fake_repo, user_home=bad_home)
        assert ver_bad["ok"] is False, ver_bad

        # Clean up test junctions before rmtree so Windows Python < 3.8 never traverses junctions
        for a in inst1["agents"]:
            if os.path.lexists(a["link_path"]):
                remove_junction_only(a["link_path"])

        return {
            "command": "self-test",
            "ok": True,
            "self_test": "PASS",
            "junction_install_and_idempotency_verified": True,
            "non_junction_collision_guard_verified": True,
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    parser = OptionParser(usage="Usage: %prog [--install | --verify | --self-test] [--repo-root DIR] [--home DIR]")
    parser.add_option("--install", action="store_true", dest="do_install", default=False)
    parser.add_option("--verify", action="store_true", dest="do_verify", default=False)
    parser.add_option("--self-test", action="store_true", dest="do_selftest", default=False)
    parser.add_option("--repo-root", type="string", dest="repo_root", default=None)
    parser.add_option("--home", type="string", dest="user_home", default=None)
    opts, extra = parser.parse_args(list(sys.argv[1:] if argv is None else argv))

    if extra and extra[0] == "self-test":
        opts.do_selftest = True

    try:
        if opts.do_selftest:
            rep = run_self_test()
            print(json.dumps(rep, indent=2, sort_keys=True))
            return 0
        if opts.do_install:
            rep = install_junctions(repo_root=opts.repo_root, user_home=opts.user_home)
            print(json.dumps(rep, indent=2, sort_keys=True))
            return 0 if rep["ok"] else 1
        rep = verify_junctions(repo_root=opts.repo_root, user_home=opts.user_home)
        print(json.dumps(rep, indent=2, sort_keys=True))
        return 0 if rep["ok"] else 1
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2, sort_keys=True))
        return 1


if __name__ == "__main__":
    sys.exit(main())
