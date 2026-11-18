#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check managed Markdown file links and curated-source replacements; Python 2.6+."""
from __future__ import print_function

import json
import os
import re
import sys

sys.dont_write_bytecode = True

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


def destinations(path):
    stream = open(path, "rb")
    try:
        body = stream.read().decode("utf-8")
    finally:
        stream.close()
    for raw in re.findall(r"\]\(([^)]+)\)", body):
        dest = raw.strip().strip("<>").split("#", 1)[0]
        if not dest or "://" in dest or dest.startswith(("mailto:", "data:")):
            continue
        if any(token in dest for token in (" ", "{{", "$", "*")):
            continue
        yield dest


def check(root=ROOT):
    errors = []
    links = 0
    deferred_external_sources = 0
    has_sources_tree = os.path.isdir(os.path.join(root, "sources"))
    registry_path = os.path.join(root, "references", "source-link-map.json")
    stream = open(registry_path, "rb")
    try:
        registry = json.loads(stream.read().decode("utf-8-sig"))
    finally:
        stream.close()
    replacements = {}
    valid_statuses = (
        "local-alternative",
        "remote-only-verified-tree",
        "unavailable-at-pinned-path",
        "not-verified-upstream",
    )
    for row in registry["links"]:
        key = (row["origin"], row["destination"])
        if key in replacements:
            errors.append("Duplicate replacement: " + repr(key))
        replacements[key] = row
        status = row.get("status")
        if status not in valid_statuses:
            errors.append("Unknown replacement status: " + repr(key))
        if status == "local-alternative":
            if (not has_sources_tree) and row.get("target", "").startswith("sources/"):
                deferred_external_sources += 1
            else:
                target = os.path.realpath(os.path.join(root, row["target"]))
                if not target.startswith(os.path.realpath(root) + os.sep) or not os.path.isfile(target):
                    errors.append("Missing or escaping local replacement: " + row["target"])
        elif status == "remote-only-verified-tree":
            if not re.match(
                r"^https://github\.com/[^/]+/[^/]+/(blob|tree)/[0-9a-f]{40}/",
                row.get("target", ""),
            ):
                errors.append("Remote replacement must pin a Git commit: " + repr(key))
    seen = set()
    for directory, dirs, files in os.walk(root):
        dirs[:] = [name for name in dirs if name not in (".git", "__pycache__")]
        for name in files:
            if not name.endswith(".md"):
                continue
            path = os.path.join(directory, name)
            relative = os.path.relpath(path, root).replace(os.sep, "/")
            upstream = relative.startswith("sources/")
            for dest in destinations(path):
                target = dest if os.path.isabs(dest) else os.path.join(directory, dest)
                if not upstream:
                    links += 1
                    if not os.path.exists(target):
                        target_rel = os.path.relpath(os.path.abspath(target), os.path.abspath(root)).replace(
                            os.sep, "/"
                        )
                        if (not has_sources_tree) and (
                            target_rel == "sources.lock.json" or target_rel.startswith("sources/")
                        ):
                            deferred_external_sources += 1
                        else:
                            errors.append("Missing managed link: " + relative + " -> " + dest)
                elif not os.path.exists(target):
                    key = (relative, dest)
                    seen.add(key)
                    if key not in replacements:
                        errors.append("Unmapped source link: " + relative + " -> " + dest)
    if has_sources_tree:
        for key in set(replacements) - seen:
            errors.append("Stale replacement: " + repr(key))
    return {
        "ok": not errors,
        "managed_file_links_checked": links,
        "source_missing_links_mapped": len(seen),
        "deferred_external_source_links": deferred_external_sources,
        "sources_tree_present": has_sources_tree,
        "errors": errors,
        "limits": "File existence and replacement coverage only. No anchor, network, model, EDA, or runtime checks.",
    }


if __name__ == "__main__":
    try:
        result = check()
    except (IOError, OSError, ValueError, KeyError, TypeError) as error:
        result = {"ok": False, "errors": [str(error)]}
    print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
    sys.exit(0 if result["ok"] else 1)
