#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Comprehensive Integrity Validator for Razavi CMOS Knowledge Brain (release 2026.11.18.1).

Pure Python 3 standard library, zero external dependencies, zero bytecode generation.
"""
import sys

sys.dont_write_bytecode = True

import argparse
import hashlib
import json
import os
import re
import xml.etree.ElementTree as ET
from collections import defaultdict

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB_ROOT = os.path.join(REPO_ROOT, "kb")

EXPECTED_DOMAINS = {
    "foundations",
    "stages-and-mirrors",
    "dynamics-noise-feedback",
    "opamps-and-compensation",
    "references-and-biasing",
    "sampled-and-clocked",
    "nonideal-and-physical",
}

REQUIRED_FRONTMATTER_KEYS = (
    "id",
    "kind",
    "domain",
    "title_vi",
    "title_en",
    "diagram",
    "razavi_refs",
    "process_agnostic",
    "roles",
    "symptoms_addressed",
    "limitations",
    "checklists",
)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def strip_code_blocks_and_spans(markdown_body):
    # Remove fenced code blocks ```...```
    lines = markdown_body.splitlines()
    kept_lines = []
    in_fence = False
    fence_marker = ""
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            marker = stripped[:3]
            if not in_fence:
                in_fence = True
                fence_marker = marker
            elif stripped.startswith(fence_marker):
                in_fence = False
            continue
        if not in_fence:
            kept_lines.append(line)
    text = "\n".join(kept_lines)
    # Remove inline backtick code spans `...`
    text = re.sub(r"`+[^`]*`+", "", text)
    return text


def check_balanced_math(markdown_body):
    clean = strip_code_blocks_and_spans(markdown_body)
    # Remove escaped \$
    clean = clean.replace(r"\$", "")
    # Count $$ display blocks first
    double_parts = clean.split("$$")
    if (len(double_parts) - 1) % 2 != 0:
        return False, f"Unbalanced '$$' display math delimiters (count={len(double_parts)-1})"
    # Outside display math blocks, check inline $ delimiters per paragraph/line
    outside = "\n".join(double_parts[0::2])
    single_count = outside.count("$")
    if single_count % 2 != 0:
        # Locate offending line for clear diagnostics
        for idx, line in enumerate(outside.splitlines(), 1):
            if line.count("$") % 2 != 0:
                return False, f"Unbalanced '$' inline math delimiter near non-code line {idx}: {line[:90]}"
        return False, f"Unbalanced '$' inline math delimiters (count={single_count})"
    return True, ""


def split_frontmatter(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, None, lines, "Missing opening '---' frontmatter delimiter"
    end_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break
    if end_idx is None:
        return None, None, lines, "Missing closing '---' frontmatter delimiter"
    fm_raw = "\n".join(lines[1:end_idx]).strip()
    try:
        meta = json.loads(fm_raw)
    except Exception as exc:
        return None, None, lines, f"Invalid JSON frontmatter: {exc}"
    if not isinstance(meta, dict):
        return None, None, lines, "Frontmatter JSON is not an object"
    body = "\n".join(lines[end_idx + 1 :])
    return meta, body, lines, ""


def has_cycle(adj):
    state = {}

    def dfs(u, trail):
        state[u] = 1
        for v in adj.get(u, ()):
            st = state.get(v, 0)
            if st == 1:
                return trail + [u, v]
            if st == 0:
                cyc = dfs(v, trail + [u])
                if cyc:
                    return cyc
        state[u] = 2
        return None

    for node in sorted(adj.keys()):
        if state.get(node, 0) == 0:
            cyc = dfs(node, [])
            if cyc:
                return cyc
    return None


def validate(expected_nodes=68, expected_diagrams=38, expected_checklists=13, min_lines=120):
    errors = []
    warnings = []

    # 1. Glossary validation
    glossary_fp = os.path.join(KB_ROOT, "glossary", "terms-vi-en.json")
    glossary_ids = set()
    if not os.path.isfile(glossary_fp):
        errors.append("Missing kb/glossary/terms-vi-en.json")
    else:
        try:
            with open(glossary_fp, "r", encoding="utf-8-sig") as f:
                gdata = json.load(f)
            terms = gdata.get("terms", [])
            for t in terms:
                tid = t.get("id")
                if not tid or tid in glossary_ids:
                    errors.append(f"Duplicate or empty glossary id: {tid}")
                glossary_ids.add(tid)
                if not t.get("en") or not t.get("vi"):
                    errors.append(f"Glossary term {tid} missing en/vi")
            for idx in range(1, 2135):
                code = f"T{idx:03d}" if idx < 1000 else f"T{idx}"
                if code not in glossary_ids:
                    errors.append(f"Missing base CLB glossary term: {code}")
            if len(terms) < 2190:
                errors.append(f"Expected >= 2190 glossary terms (2134 base + Ch.13-19), got {len(terms)}")
        except Exception as exc:
            errors.append(f"Glossary parse error: {exc}")

    # 2. Diagrams SVG XML validation
    diag_dir = os.path.join(KB_ROOT, "diagrams")
    svg_files = set()
    if not os.path.isdir(diag_dir):
        errors.append("Missing kb/diagrams/ directory")
    else:
        for fn in sorted(os.listdir(diag_dir)):
            if not fn.endswith(".svg"):
                continue
            svg_files.add(fn)
            fp = os.path.join(diag_dir, fn)
            try:
                tree = ET.parse(fp)
                root = tree.getroot()
                vb = root.attrib.get("viewBox", "").strip()
                if not vb:
                    errors.append(f"SVG {fn} missing viewBox attribute")
                elem_count = sum(1 for _ in root.iter())
                if elem_count < 8:
                    errors.append(f"SVG {fn} is trivially small ({elem_count} XML elements)")
            except Exception as exc:
                errors.append(f"SVG {fn} XML parse failure: {exc}")
        if expected_diagrams and len(svg_files) < expected_diagrams:
            errors.append(f"Expected >= {expected_diagrams} SVG diagrams, found {len(svg_files)}")

    # 3. Checklists validation
    cl_dir = os.path.join(KB_ROOT, "checklists")
    checklists = {}
    if not os.path.isdir(cl_dir):
        errors.append("Missing kb/checklists/ directory")
    else:
        for fn in sorted(os.listdir(cl_dir)):
            if not fn.endswith(".json"):
                continue
            fp = os.path.join(cl_dir, fn)
            try:
                with open(fp, "r", encoding="utf-8-sig") as f:
                    cdata = json.load(f)
                cid = cdata.get("checklist_id")
                expected_cid = os.path.splitext(fn)[0]
                if cid != expected_cid:
                    errors.append(f"Checklist {fn}: checklist_id={cid!r} != {expected_cid!r}")
                if cdata.get("process_agnostic") is not True:
                    errors.append(f"Checklist {fn}: process_agnostic must be true")
                checks = cdata.get("checks")
                if not isinstance(checks, list) or len(checks) < 3:
                    errors.append(f"Checklist {fn}: expected >= 3 checks")
                checklists[expected_cid] = cdata
            except Exception as exc:
                errors.append(f"Checklist {fn} parse error: {exc}")
        if expected_checklists and len(checklists) < expected_checklists:
            errors.append(f"Expected >= {expected_checklists} checklists, found {len(checklists)}")

    # 4. Node Markdown Cards validation
    nodes_root = os.path.join(KB_ROOT, "nodes")
    node_ids = set()
    chapters_covered = set()
    if not os.path.isdir(nodes_root):
        errors.append("Missing kb/nodes/ directory")
    else:
        present_domains = {
            d for d in os.listdir(nodes_root) if os.path.isdir(os.path.join(nodes_root, d))
        }
        missing_domains = EXPECTED_DOMAINS - present_domains
        if missing_domains:
            errors.append(f"Missing domain folders: {sorted(missing_domains)}")

        for dom in sorted(present_domains):
            dom_dir = os.path.join(nodes_root, dom)
            for fn in sorted(os.listdir(dom_dir)):
                if not fn.endswith(".md"):
                    continue
                fp = os.path.join(dom_dir, fn)
                rel = f"kb/nodes/{dom}/{fn}"
                with open(fp, "r", encoding="utf-8-sig") as f:
                    raw_text = f.read()
                meta, body, lines, err = split_frontmatter(raw_text)
                if err:
                    errors.append(f"{rel}: {err}")
                    continue

                if len(lines) < min_lines:
                    errors.append(f"{rel}: insufficient depth ({len(lines)} lines < {min_lines})")

                nid = meta.get("id")
                expected_id = os.path.splitext(fn)[0]
                if nid != expected_id:
                    errors.append(f"{rel}: id={nid!r} != filename {expected_id!r}")
                if nid in node_ids:
                    errors.append(f"{rel}: duplicate node id {nid!r}")
                node_ids.add(nid)

                if meta.get("domain") != dom:
                    errors.append(f"{rel}: domain={meta.get('domain')!r} != folder {dom!r}")

                summary_val = meta.get("summary")
                if not summary_val and meta.get("Summary"):
                    summary_val = meta.get("Summary")
                    warnings.append(f"{rel}: uses capitalized 'Summary' key instead of 'summary'")
                if not summary_val or not isinstance(summary_val, str):
                    errors.append(f"{rel}: missing non-empty 'summary' in frontmatter")

                for key in REQUIRED_FRONTMATTER_KEYS:
                    if key not in meta:
                        errors.append(f"{rel}: missing frontmatter key {key!r}")

                if meta.get("process_agnostic") is not True:
                    errors.append(f"{rel}: process_agnostic must be true")

                # Diagram resolution
                diag_rel = meta.get("diagram", "")
                if not diag_rel:
                    errors.append(f"{rel}: empty 'diagram' field")
                else:
                    resolved_diag = os.path.normpath(os.path.join(dom_dir, diag_rel))
                    if not os.path.isfile(resolved_diag):
                        errors.append(f"{rel}: diagram path does not exist: {diag_rel}")

                # Check inline markdown image links to diagrams
                for img_link in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", body):
                    clean_link = img_link.strip().split()[0]
                    if "://" in clean_link:
                        continue
                    resolved_img = os.path.normpath(os.path.join(dom_dir, clean_link))
                    if not os.path.isfile(resolved_img):
                        errors.append(f"{rel}: broken inline image path: {clean_link}")

                # Check all 6 required H2 sections exist and have non-trivial content
                sec_positions = []
                for sec_num in range(1, 7):
                    m = re.search(rf"^##\s+{sec_num}\.\s+.+$", body, re.M)
                    if not m:
                        errors.append(f"{rel}: missing required section '## {sec_num}. ...'")
                    else:
                        sec_positions.append((sec_num, m.start(), m.end()))
                if len(sec_positions) == 6:
                    for idx_s, (snum, s_start, s_end) in enumerate(sec_positions):
                        next_start = sec_positions[idx_s + 1][1] if idx_s + 1 < 6 else len(body)
                        sec_body = body[s_end:next_start].strip()
                        if len(sec_body) < 80:
                            errors.append(f"{rel}: section ## {snum}. is stub/too short ({len(sec_body)} chars)")

                # Balanced LaTeX math delimiters
                math_ok, math_msg = check_balanced_math(body)
                if not math_ok:
                    errors.append(f"{rel}: {math_msg}")

                # Checklists existence
                for cl_id in meta.get("checklists") or []:
                    if cl_id not in checklists:
                        errors.append(f"{rel}: references unknown checklist {cl_id!r}")

                # Razavi refs
                refs = meta.get("razavi_refs") or []
                if not isinstance(refs, list) or not refs:
                    errors.append(f"{rel}: razavi_refs must be a non-empty list")
                else:
                    for r in refs:
                        if isinstance(r, dict) and "chapter" in r:
                            ch = int(r["chapter"])
                            if 1 <= ch <= 19:
                                chapters_covered.add(ch)
                            else:
                                errors.append(f"{rel}: invalid chapter {ch} in razavi_refs")

                # Glossary codes if present
                for gc in meta.get("glossary_codes") or []:
                    if glossary_ids and gc not in glossary_ids:
                        errors.append(f"{rel}: unknown glossary code {gc!r}")

        if expected_nodes and len(node_ids) != expected_nodes:
            errors.append(f"Expected {expected_nodes} node cards, found {len(node_ids)}")
        if expected_nodes and chapters_covered != set(range(1, 20)):
            missing_ch = sorted(set(range(1, 20)) - chapters_covered)
            errors.append(f"Chapters missing across Razavi node cards: {missing_ch}")

    # Cross-check related_nodes in checklists now that node_ids is populated
    for cid, cdata in checklists.items():
        for chk in cdata.get("checks") or []:
            for rn in chk.get("related_nodes") or []:
                if node_ids and rn not in node_ids:
                    errors.append(f"Checklist {cid} check {chk.get('id')}: unknown related_node {rn!r}")

    # 5. Knowledge Graph edges.jsonl validation
    graph_dir = os.path.join(KB_ROOT, "graph")
    edges_fp = os.path.join(graph_dir, "edges.jsonl")
    edge_count = 0
    if not os.path.isdir(graph_dir):
        errors.append("Missing kb/graph/ directory")
    else:
        leftover_frags = [
            fn for fn in os.listdir(graph_dir) if fn.startswith("edges-d") and fn.endswith(".jsonl")
        ]
        if leftover_frags:
            errors.append(f"Temporary edge fragments still present in kb/graph/: {leftover_frags}")

        if not os.path.isfile(edges_fp):
            errors.append("Missing kb/graph/edges.jsonl")
        else:
            degree = defaultdict(int)
            upgrades_adj = defaultdict(list)
            with open(edges_fp, "r", encoding="utf-8-sig") as f:
                for line_no, line in enumerate(f, 1):
                    s = line.strip()
                    if not s:
                        continue
                    edge_count += 1
                    try:
                        e = json.loads(s)
                    except Exception as exc:
                        errors.append(f"edges.jsonl:{line_no}: invalid JSON ({exc})")
                        continue
                    u = e.get("from")
                    v = e.get("to")
                    rel = e.get("rel")
                    if not u or not v or not rel:
                        errors.append(f"edges.jsonl:{line_no}: missing from/to/rel")
                        continue
                    if u not in node_ids:
                        errors.append(f"edges.jsonl:{line_no}: broken 'from' node {u!r}")
                    if v not in node_ids:
                        errors.append(f"edges.jsonl:{line_no}: broken 'to' node {v!r}")
                    degree[u] += 1
                    degree[v] += 1
                    if rel == "upgrades_to":
                        upgrades_adj[u].append(v)

            orphans = sorted(nid for nid in node_ids if degree[nid] == 0)
            if orphans:
                errors.append(f"Orphan nodes with 0 graph edges ({len(orphans)}): {orphans}")

            cyc = has_cycle(upgrades_adj)
            if cyc:
                errors.append(f"Cycle detected in 'upgrades_to' subgraph: {' -> '.join(cyc)}")

    # 6. Router Index & Manifest SHA-256 validation
    router_fp = os.path.join(KB_ROOT, "router-index.json")
    manifest_fp = os.path.join(KB_ROOT, "manifest.json")
    if not os.path.isfile(router_fp):
        errors.append("Missing kb/router-index.json")
    else:
        try:
            with open(router_fp, "r", encoding="utf-8-sig") as f:
                ridx = json.load(f)
            if len(ridx.get("nodes", [])) != len(node_ids):
                errors.append("router-index.json node count out of sync with kb/nodes/")
        except Exception as exc:
            errors.append(f"router-index.json parse error: {exc}")

    if not os.path.isfile(manifest_fp):
        errors.append("Missing kb/manifest.json")
    else:
        try:
            with open(manifest_fp, "r", encoding="utf-8-sig") as f:
                man = json.load(f)
            if man.get("release") != "2026.11.18.1":
                errors.append(f"manifest.json unexpected release: {man.get('release')!r}")
            recorded = {}
            for entry in man.get("files", []):
                p = entry.get("path")
                recorded[p] = entry
                abs_p = os.path.join(REPO_ROOT, *p.split("/"))
                if not os.path.isfile(abs_p):
                    errors.append(f"manifest.json references missing file: {p}")
                else:
                    if os.path.getsize(abs_p) != entry.get("bytes"):
                        errors.append(f"manifest.json byte size mismatch: {p}")
                    if sha256_file(abs_p) != entry.get("sha256"):
                        errors.append(f"manifest.json SHA-256 mismatch: {p}")
            for root_dir, dirs, files in os.walk(KB_ROOT):
                dirs[:] = [d for d in dirs if d != "__pycache__"]
                for fn in files:
                    full = os.path.join(root_dir, fn)
                    if os.path.abspath(full) == os.path.abspath(manifest_fp):
                        continue
                    rel = os.path.relpath(full, REPO_ROOT).replace("\\", "/")
                    if rel not in recorded:
                        errors.append(f"Untracked file under kb/ missing from manifest.json: {rel}")
        except Exception as exc:
            errors.append(f"manifest.json parse error: {exc}")

    return {
        "ok": len(errors) == 0,
        "summary": {
            "nodes": len(node_ids),
            "chapters_covered": len(chapters_covered),
            "diagrams_svg": len(svg_files),
            "checklists": len(checklists),
            "edges": edge_count,
            "glossary_terms": len(glossary_ids),
        },
        "errors": errors,
        "warnings": warnings,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-nodes", type=int, default=68)
    parser.add_argument("--expected-diagrams", type=int, default=38)
    parser.add_argument("--expected-checklists", type=int, default=13)
    parser.add_argument("--min-lines", type=int, default=120)
    args = parser.parse_args()

    result = validate(
        expected_nodes=args.expected_nodes,
        expected_diagrams=args.expected_diagrams,
        expected_checklists=args.expected_checklists,
        min_lines=args.min_lines,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
