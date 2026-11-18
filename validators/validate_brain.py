#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Comprehensive Integrity Validator for Razavi CMOS Knowledge Brain & v4.0 Runtime (release 2026.11.18.6).

Validates all 10 domains (162 cards: 112 Razavi Ch.01-19 cards + 12 PMIC cards + 12 AMS/System cards
+ 26 Closed-Loop Cadence/GitHub Skill cards), 72 vector SVGs, 21 structural checklists, 2,280 CLB
glossary terms (T001-T2280), Exact Book Coordinates (`book-coordinates.json` with 100% section/equation
verification), 52-repo GitHub Skills Catalog (`catalog.json`), 22-column 2D coordinates, balanced LaTeX,
deterministic `nodes-bundle.json.gz`, `runtime/manifest.json` SHA-256 integrity, and Python 2.6 AST/LF safety.

Pure Python 3 standard library, zero external dependencies, zero bytecode generation.
"""
import sys

sys.dont_write_bytecode = True

import argparse
import ast
import gzip
import hashlib
import json
import os
import re
import xml.etree.ElementTree as ET
from collections import defaultdict

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB_ROOT = os.path.join(REPO_ROOT, "kb")
RUNTIME_ROOT = os.path.join(REPO_ROOT, "runtime")
EXPECTED_RELEASE = "2026.11.18.6"

EXPECTED_DOMAINS = {
    "foundations",
    "stages-and-mirrors",
    "dynamics-noise-feedback",
    "opamps-and-compensation",
    "references-and-biasing",
    "sampled-and-clocked",
    "nonideal-and-physical",
    "power-management-ic",
    "ams-filters-and-system",
    "eda-and-github-skills",
}

RAZAVI_CORE_DOMAINS = {
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
    text = re.sub(r"`+[^`]*`+", "", text)
    return text


def check_balanced_math(markdown_body):
    clean = strip_code_blocks_and_spans(markdown_body)
    clean = clean.replace(r"\$", "")
    double_parts = clean.split("$$")
    if (len(double_parts) - 1) % 2 != 0:
        return False, f"Unbalanced '$$' display math delimiters (count={len(double_parts)-1})"
    outside = "\n".join(double_parts[0::2])
    single_count = outside.count("$")
    if single_count % 2 != 0:
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


def validate(
    expected_nodes=162,
    expected_diagrams=72,
    expected_checklists=21,
    expected_glossary=2280,
    expected_repos=52,
    min_lines=120,
):
    errors = []
    warnings = []

    # 1. Glossary validation (T001-T2280)
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
            upper_bound = max(2134, expected_glossary)
            missing_codes = []
            for idx in range(1, upper_bound + 1):
                code = f"T{idx:03d}" if idx < 1000 else f"T{idx}"
                if code not in glossary_ids:
                    missing_codes.append(code)
            if missing_codes:
                errors.append(
                    f"Missing glossary term codes ({len(missing_codes)}, first 10): {missing_codes[:10]}"
                )
            if expected_glossary and len(terms) < expected_glossary:
                errors.append(f"Expected >= {expected_glossary} glossary terms, got {len(terms)}")
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
                if elem_count < 15:
                    errors.append(f"SVG {fn} is trivially small ({elem_count} XML elements)")
            except Exception as exc:
                errors.append(f"SVG {fn} XML parse failure: {exc}")
        if expected_diagrams and len(svg_files) != expected_diagrams:
            errors.append(f"Expected {expected_diagrams} SVG diagrams, found {len(svg_files)}")
        diag_man_fp = os.path.join(diag_dir, "diagrams-manifest.json")
        if not os.path.isfile(diag_man_fp):
            errors.append("Missing kb/diagrams/diagrams-manifest.json")
        else:
            try:
                with open(diag_man_fp, "r", encoding="utf-8-sig") as f:
                    dman = json.load(f)
                if len(dman.get("diagrams", [])) != len(svg_files):
                    errors.append(
                        f"diagrams-manifest.json count ({len(dman.get('diagrams', []))}) != SVG files ({len(svg_files)})"
                    )
            except Exception as exc:
                errors.append(f"diagrams-manifest.json parse error: {exc}")

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

    # 4. Pre-load GitHub catalog repo set (52 repos)
    catalog_fp = os.path.join(KB_ROOT, "github-skills", "catalog.json")
    catalog_repos = set()
    catalog_data = None
    if not os.path.isfile(catalog_fp):
        errors.append("Missing kb/github-skills/catalog.json")
    else:
        try:
            with open(catalog_fp, "r", encoding="utf-8-sig") as f:
                catalog_data = json.load(f)
            if catalog_data.get("schema") != "razavi-github-skills-catalog.v1":
                errors.append(f"catalog.json invalid schema: {catalog_data.get('schema')!r}")
            repos_list = catalog_data.get("repositories") or catalog_data.get("repos") or []
            if expected_repos and len(repos_list) < expected_repos:
                errors.append(f"catalog.json expected >= {expected_repos} vetted repos, found {len(repos_list)}")
            for r in repos_list:
                for rk in (
                    "id",
                    "repo",
                    "url",
                    "pinned_commit_or_branch",
                    "license",
                    "category",
                    "quality_tier",
                    "ic617_compatibility",
                    "summary_vi",
                    "key_techniques",
                    "linked_nodes",
                ):
                    if rk not in r:
                        errors.append(f"catalog.json repo {r.get('repo', '?')}: missing key {rk!r}")
                if r.get("repo"):
                    catalog_repos.add(r["repo"])
        except Exception as exc:
            errors.append(f"catalog.json parse error: {exc}")

    # 5. Node Markdown Cards validation across all 10 domains
    nodes_root = os.path.join(KB_ROOT, "nodes")
    node_ids = set()
    skill_node_ids = set()
    domain_node_counts = defaultdict(int)
    chapters_covered = set()
    if not os.path.isdir(nodes_root):
        errors.append("Missing kb/nodes/ directory")
    else:
        present_domains = {
            d for d in os.listdir(nodes_root) if os.path.isdir(os.path.join(nodes_root, d))
        }
        missing_domains = EXPECTED_DOMAINS - present_domains
        unexpected_domains = present_domains - EXPECTED_DOMAINS
        if missing_domains:
            errors.append(f"Missing domain folders: {sorted(missing_domains)}")
        if unexpected_domains:
            errors.append(f"Unexpected domain folders: {sorted(unexpected_domains)}")

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
                domain_node_counts[dom] += 1

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

                is_skill_card = dom == "eda-and-github-skills" or meta.get("kind") == "skill" or str(nid).startswith("skill-")
                if is_skill_card:
                    skill_node_ids.add(nid)
                    if meta.get("kind") != "skill":
                        errors.append(f"{rel}: skill card must have kind='skill', got {meta.get('kind')!r}")
                    gh_refs = meta.get("github_refs")
                    if not isinstance(gh_refs, list) or not gh_refs:
                        errors.append(f"{rel}: skill card must have non-empty 'github_refs' list")
                    else:
                        for gref in gh_refs:
                            if not isinstance(gref, dict) or not gref.get("repo") or not gref.get("url") or not gref.get("use"):
                                errors.append(f"{rel}: invalid github_refs entry {gref!r}")
                            elif catalog_repos and gref["repo"] not in catalog_repos:
                                errors.append(f"{rel}: github_refs repo {gref['repo']!r} not in catalog.json")
                elif "github_refs" in meta:
                    gh_refs = meta.get("github_refs")
                    if not isinstance(gh_refs, list):
                        errors.append(f"{rel}: 'github_refs' must be a list when present")
                    else:
                        for gref in gh_refs:
                            if not isinstance(gref, dict) or not gref.get("repo") or not gref.get("url") or not gref.get("use"):
                                errors.append(f"{rel}: invalid github_refs entry {gref!r}")

                diag_rel = meta.get("diagram", "")
                if not diag_rel:
                    errors.append(f"{rel}: empty 'diagram' field")
                else:
                    resolved_diag = os.path.normpath(os.path.join(dom_dir, diag_rel))
                    if not os.path.isfile(resolved_diag):
                        errors.append(f"{rel}: diagram path does not exist: {diag_rel}")

                for img_link in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", body):
                    clean_link = img_link.strip().split()[0]
                    if "://" in clean_link:
                        continue
                    resolved_img = os.path.normpath(os.path.join(dom_dir, clean_link))
                    if not os.path.isfile(resolved_img):
                        errors.append(f"{rel}: broken inline image path: {clean_link}")

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

                math_ok, math_msg = check_balanced_math(body)
                if not math_ok:
                    errors.append(f"{rel}: {math_msg}")

                for cl_id in meta.get("checklists") or []:
                    if cl_id not in checklists:
                        errors.append(f"{rel}: references unknown checklist {cl_id!r}")

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

                for gc in meta.get("glossary_codes") or []:
                    if glossary_ids and gc not in glossary_ids:
                        errors.append(f"{rel}: unknown glossary code {gc!r}")

        if expected_nodes and len(node_ids) != expected_nodes:
            errors.append(f"Expected {expected_nodes} node cards, found {len(node_ids)}")
        if expected_nodes >= 162:
            if domain_node_counts.get("power-management-ic", 0) < 12:
                errors.append(
                    f"Expected >= 12 cards in power-management-ic, found {domain_node_counts.get('power-management-ic', 0)}"
                )
            if domain_node_counts.get("ams-filters-and-system", 0) < 12:
                errors.append(
                    f"Expected >= 12 cards in ams-filters-and-system, found {domain_node_counts.get('ams-filters-and-system', 0)}"
                )
            if domain_node_counts.get("eda-and-github-skills", 0) < 26:
                errors.append(
                    f"Expected >= 26 cards in eda-and-github-skills, found {domain_node_counts.get('eda-and-github-skills', 0)}"
                )
        elif len(skill_node_ids) < 22:
            errors.append(f"Expected >= 22 skill-* cards, found {len(skill_node_ids)}")
        if expected_nodes and chapters_covered != set(range(1, 20)):
            missing_ch = sorted(set(range(1, 20)) - chapters_covered)
            errors.append(f"Chapters missing across node cards: {missing_ch}")

    # Cross-check related_nodes in checklists and linked_nodes in catalog.json
    for cid, cdata in checklists.items():
        for chk in cdata.get("checks") or []:
            for rn in chk.get("related_nodes") or []:
                if node_ids and rn not in node_ids:
                    errors.append(f"Checklist {cid} check {chk.get('id')}: unknown related_node {rn!r}")

    if catalog_data:
        for r in catalog_data.get("repositories") or catalog_data.get("repos") or []:
            for ln in r.get("linked_nodes") or []:
                if node_ids and ln not in node_ids:
                    errors.append(f"catalog.json repo {r.get('repo')}: unknown linked_node {ln!r}")

    # 6. Book Coordinates validation (kb/coordinates/book-coordinates.json) + 100% card ref check
    coords_fp = os.path.join(KB_ROOT, "coordinates", "book-coordinates.json")
    sec_count = 0
    eq_count = 0
    idx_term_count = 0
    if not os.path.isfile(coords_fp):
        errors.append("Missing kb/coordinates/book-coordinates.json")
    else:
        try:
            with open(coords_fp, "r", encoding="utf-8-sig") as f:
                bcoords = json.load(f)
            if bcoords.get("schema") != "razavi-book-coordinates.v1":
                errors.append(f"book-coordinates.json unexpected schema: {bcoords.get('schema')!r}")
            if bcoords.get("release") != EXPECTED_RELEASE:
                errors.append(f"book-coordinates.json unexpected release: {bcoords.get('release')!r}")
            b_chapters = bcoords.get("chapters") or []
            ch_by_num = {int(c["chapter"]): c for c in b_chapters if "chapter" in c}
            if len(b_chapters) != 19:
                errors.append(f"book-coordinates.json expected 19 chapters, got {len(b_chapters)}")
            for ch_obj in b_chapters:
                for nid in ch_obj.get("node_ids") or []:
                    if node_ids and nid not in node_ids:
                        errors.append(f"book-coordinates.json ch.{ch_obj.get('chapter')}: unknown node_id {nid!r}")

            b_sections = bcoords.get("sections") or []
            sec_count = len(b_sections)
            sec_by_id = {}
            if sec_count < 290:
                errors.append(f"book-coordinates.json expected >= 290 sections, got {sec_count}")
            for s_obj in b_sections:
                sid = str(s_obj.get("section_id", ""))
                if not sid or not s_obj.get("chapter"):
                    errors.append(f"book-coordinates.json section missing section_id/chapter: {s_obj!r}")
                else:
                    sec_by_id[sid] = s_obj
                for nid in s_obj.get("primary_nodes") or []:
                    if node_ids and nid not in node_ids:
                        errors.append(
                            f"book-coordinates.json section {s_obj.get('section_id')}: unknown primary_node {nid!r}"
                        )

            b_eqs = bcoords.get("equations") or []
            eq_count = len(b_eqs)
            eq_nums_present = set()
            if eq_count < 1400:
                errors.append(f"book-coordinates.json expected >= 1400 equations, got {eq_count}")
            for e_obj in b_eqs:
                enum_val = str(e_obj.get("eq_num", ""))
                if not e_obj.get("eq_id") or not enum_val or not e_obj.get("latex"):
                    errors.append(f"book-coordinates.json equation missing eq_id/eq_num/latex: {e_obj!r}")
                if enum_val in eq_nums_present:
                    errors.append(f"book-coordinates.json duplicate eq_num: {enum_val!r}")
                eq_nums_present.add(enum_val)
                nid_primary = e_obj.get("node_id")
                if nid_primary and node_ids and nid_primary not in node_ids:
                    errors.append(f"book-coordinates.json {e_obj.get('eq_id')}: unknown node_id {nid_primary!r}")
                for rn in e_obj.get("related_nodes") or []:
                    if node_ids and rn not in node_ids:
                        errors.append(f"book-coordinates.json {e_obj.get('eq_id')}: unknown related_node {rn!r}")

            for s_obj in b_sections:
                for ke in s_obj.get("key_equations") or []:
                    ke_clean = str(ke).strip("() ")
                    if ke_clean not in eq_nums_present:
                        errors.append(
                            f"book-coordinates.json section {s_obj.get('section_id')} key_equation {ke!r} missing from equations[]"
                        )

            # Verify 100% of razavi_refs sections, page bounds & equations across all 162 cards
            for dom in sorted(EXPECTED_DOMAINS):
                dom_dir = os.path.join(nodes_root, dom)
                if not os.path.isdir(dom_dir):
                    continue
                for fn in sorted(os.listdir(dom_dir)):
                    if not fn.endswith(".md"):
                        continue
                    rel = f"kb/nodes/{dom}/{fn}"
                    with open(os.path.join(dom_dir, fn), "r", encoding="utf-8-sig") as nf:
                        m_card, _, _, _ = split_frontmatter(nf.read())
                    if not m_card:
                        continue
                    for r in m_card.get("razavi_refs") or []:
                        ch = int(r["chapter"])
                        ch_info = ch_by_num.get(ch)
                        sec_raw = str(r.get("section", ""))
                        for tok in [t.strip().lstrip("§") for t in re.split(r"[,;–-]", sec_raw) if t.strip()]:
                            if tok not in sec_by_id or int(sec_by_id[tok]["chapter"]) != ch:
                                errors.append(f"{rel}: razavi_refs section token {tok!r} (ch.{ch}) missing in book-coordinates.json")
                        if ch_info:
                            for pno in [int(x) for x in re.findall(r"\d+", str(r.get("pages", "")))]:
                                if not (ch_info["book_page_start"] <= pno <= ch_info["book_page_end"]):
                                    errors.append(
                                        f"{rel}: razavi_refs page {pno} outside ch.{ch} ({ch_info['book_page_start']}-{ch_info['book_page_end']})"
                                    )
                                    break
                        for eq_r in r.get("equations") or []:
                            eq_clean = re.sub(r"^Eq\.?\s*", "", str(eq_r).strip("() "))
                            if eq_clean not in eq_nums_present:
                                errors.append(f"{rel}: razavi_refs equation {eq_r!r} missing from book-coordinates.json")

            b_idx = bcoords.get("index_terms") or []
            idx_term_count = len(b_idx)
            if idx_term_count < 300:
                errors.append(f"book-coordinates.json expected >= 300 index_terms, got {idx_term_count}")
            for it_obj in b_idx:
                for mn in it_obj.get("mapped_nodes") or []:
                    if node_ids and mn not in node_ids:
                        errors.append(f"book-coordinates.json index term {it_obj.get('term_en')!r}: unknown mapped_node {mn!r}")
        except Exception as exc:
            errors.append(f"book-coordinates.json parse error: {exc}")

    # 7. Knowledge Graph edges.jsonl validation
    graph_dir = os.path.join(KB_ROOT, "graph")
    edges_fp = os.path.join(graph_dir, "edges.jsonl")
    edge_count = 0
    if not os.path.isdir(graph_dir):
        errors.append("Missing kb/graph/ directory")
    else:
        leftover_frags = sorted(
            fn
            for fn in os.listdir(graph_dir)
            if fn.startswith("edges-") and fn.endswith(".jsonl") and fn != "edges.jsonl"
        )
        if leftover_frags:
            errors.append(f"Temporary edge fragments still present in kb/graph/: {leftover_frags}")

        if not os.path.isfile(edges_fp):
            errors.append("Missing kb/graph/edges.jsonl")
        else:
            degree = defaultdict(int)
            upgrades_adj = defaultdict(list)
            seen_edges = set()
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
                    if u == v:
                        errors.append(f"edges.jsonl:{line_no}: self-loop on {u!r}")
                    if u not in node_ids:
                        errors.append(f"edges.jsonl:{line_no}: broken 'from' node {u!r}")
                    if v not in node_ids:
                        errors.append(f"edges.jsonl:{line_no}: broken 'to' node {v!r}")
                    ekey = (u, v, rel)
                    if ekey in seen_edges:
                        errors.append(f"edges.jsonl:{line_no}: duplicate edge {ekey!r}")
                    seen_edges.add(ekey)
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

    # 8. Router Index & Manifest SHA-256 validation
    router_fp = os.path.join(KB_ROOT, "router-index.json")
    manifest_fp = os.path.join(KB_ROOT, "manifest.json")
    if not os.path.isfile(router_fp):
        errors.append("Missing kb/router-index.json")
    else:
        try:
            with open(router_fp, "r", encoding="utf-8-sig") as f:
                ridx = json.load(f)
            if ridx.get("release") != EXPECTED_RELEASE:
                errors.append(f"router-index.json unexpected release: {ridx.get('release')!r}")
            rnodes = ridx.get("nodes", [])
            if len(rnodes) != len(node_ids):
                errors.append("router-index.json node count out of sync with kb/nodes/")
            if len(ridx.get("domains", [])) != 10:
                errors.append(f"router-index.json expected 10 domains, got {len(ridx.get('domains', []))}")
            seen_grid_cells = {}
            seen_pixels = {}
            for rn in rnodes:
                c2d = rn.get("coord_2d")
                if not isinstance(c2d, dict) or "grid_col" not in c2d or "grid_row" not in c2d:
                    errors.append(f"router-index.json node {rn.get('id')}: missing coord_2d")
                else:
                    col = c2d["grid_col"]
                    row = c2d["grid_row"]
                    if not (1 <= int(col) <= 22):
                        errors.append(f"router-index.json node {rn.get('id')}: grid_col {col} out of 1..22")
                    cell = (col, row)
                    if cell in seen_grid_cells:
                        errors.append(
                            f"router-index.json duplicate 2D grid cell {cell}: {seen_grid_cells[cell]} vs {rn.get('id')}"
                        )
                    seen_grid_cells[cell] = rn.get("id")
                    px = (c2d.get("x"), c2d.get("y"))
                    if px in seen_pixels:
                        errors.append(
                            f"router-index.json overlapping 2D pixel coordinate {px}: {seen_pixels[px]} vs {rn.get('id')}"
                        )
                    seen_pixels[px] = rn.get("id")
                if not isinstance(rn.get("section_coords"), dict):
                    errors.append(f"router-index.json node {rn.get('id')}: missing section_coords")
        except Exception as exc:
            errors.append(f"router-index.json parse error: {exc}")

    if not os.path.isfile(manifest_fp):
        errors.append("Missing kb/manifest.json")
    else:
        try:
            with open(manifest_fp, "r", encoding="utf-8-sig") as f:
                man = json.load(f)
            if man.get("release") != EXPECTED_RELEASE:
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
            for req_rel in (
                "kb/coordinates/book-coordinates.json",
                "kb/github-skills/catalog.json",
                "kb/nodes-bundle.json.gz",
                "kb/diagrams/diagrams-manifest.json",
            ):
                if req_rel not in recorded:
                    errors.append(f"manifest.json missing required file: {req_rel}")
            bundle_fp = os.path.join(KB_ROOT, "nodes-bundle.json.gz")
            if os.path.isfile(bundle_fp):
                with gzip.open(bundle_fp, "rb") as gzf:
                    bdata = json.loads(gzf.read().decode("utf-8"))
                if bdata.get("release") != EXPECTED_RELEASE or bdata.get("node_count") != len(node_ids):
                    errors.append("nodes-bundle.json.gz out of sync with release or node_count")
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

    # 9. Runtime Engine Manifest & Python 2.6.6 Compatibility Validation (`runtime/`)
    rt_manifest_fp = os.path.join(RUNTIME_ROOT, "manifest.json")
    rt_file_count = 0
    if not os.path.isdir(RUNTIME_ROOT) or not os.path.isfile(rt_manifest_fp):
        errors.append("Missing runtime/manifest.json")
    else:
        try:
            with open(rt_manifest_fp, "r", encoding="utf-8-sig") as rf:
                rt_man = json.load(rf)
            if rt_man.get("schema") != "skill-analog-runtime.v4":
                errors.append(f"runtime/manifest.json unexpected schema: {rt_man.get('schema')!r}")
            if rt_man.get("release") != EXPECTED_RELEASE:
                errors.append(f"runtime/manifest.json unexpected release: {rt_man.get('release')!r}")
            rt_recorded = {}
            for entry in rt_man.get("files", []):
                p = entry.get("path")
                rt_recorded[p] = entry
                abs_p = os.path.join(RUNTIME_ROOT, *p.split("/"))
                if not os.path.isfile(abs_p):
                    errors.append(f"runtime/manifest.json references missing file: {p}")
                else:
                    if os.path.getsize(abs_p) != entry.get("bytes"):
                        errors.append(f"runtime/manifest.json byte size mismatch: {p}")
                    if sha256_file(abs_p) != entry.get("sha256"):
                        errors.append(f"runtime/manifest.json SHA-256 mismatch: {p}")
            rt_file_count = len(rt_recorded)

            py26_forbidden = {
                "JoinedStr", "DictComp", "SetComp", "Set",
                "AsyncFunctionDef", "Await", "Nonlocal", "YieldFrom", "AnnAssign",
            }
            for root_dir, dirs, files in os.walk(RUNTIME_ROOT):
                if "__pycache__" in dirs:
                    errors.append(f"Bytecode directory __pycache__ found in runtime/: {root_dir}")
                dirs[:] = [d for d in dirs if d not in ("__pycache__", "sources")]
                for fn in sorted(files):
                    full = os.path.join(root_dir, fn)
                    if fn.endswith((".pyc", ".pyo", ".tmp", ".lock")):
                        errors.append(f"Trash file found in runtime/: {full}")
                        continue
                    if os.path.abspath(full) == os.path.abspath(rt_manifest_fp):
                        continue
                    rel_rt = os.path.relpath(full, RUNTIME_ROOT).replace("\\", "/")
                    if rel_rt != "sources.lock.json" and rel_rt not in rt_recorded:
                        errors.append(f"Untracked file under runtime/ missing from runtime/manifest.json: {rel_rt}")
                    raw_b = open(full, "rb").read()
                    if b"\r" in raw_b and not fn.endswith(".gz"):
                        errors.append(f"CRLF/CR line endings in runtime/{rel_rt} (must be pure LF)")
                    if fn.endswith(".py"):
                        src_txt = raw_b.decode("utf-8")
                        tree = ast.parse(src_txt, filename=rel_rt)
                        for ast_node in ast.walk(tree):
                            cname = type(ast_node).__name__
                            if cname in py26_forbidden:
                                errors.append(
                                    f"Python 2.6 incompatible syntax {cname} in runtime/{rel_rt}:{getattr(ast_node, 'lineno', 0)}"
                                )
                            elif cname == "Import" and any(a.name == "argparse" for a in ast_node.names):
                                errors.append(f"Forbidden argparse import in runtime/{rel_rt}:{ast_node.lineno}")
                            elif cname == "ImportFrom" and ast_node.module == "argparse":
                                errors.append(f"Forbidden argparse import in runtime/{rel_rt}:{ast_node.lineno}")
        except Exception as exc:
            errors.append(f"runtime/manifest.json validation error: {exc}")

    razavi_core_cnt = sum(domain_node_counts.get(d, 0) for d in RAZAVI_CORE_DOMAINS)
    return {
        "ok": len(errors) == 0,
        "summary": {
            "release": EXPECTED_RELEASE,
            "domains": len(EXPECTED_DOMAINS),
            "nodes": len(node_ids),
            "razavi_core_nodes": razavi_core_cnt,
            "pmic_nodes": domain_node_counts.get("power-management-ic", 0),
            "ams_nodes": domain_node_counts.get("ams-filters-and-system", 0),
            "eda_domain_nodes": domain_node_counts.get("eda-and-github-skills", 0),
            "razavi_nodes": len(node_ids) - len(skill_node_ids),
            "skill_nodes": len(skill_node_ids),
            "chapters_covered": len(chapters_covered),
            "diagrams_svg": len(svg_files),
            "checklists": len(checklists),
            "edges": edge_count,
            "glossary_terms": len(glossary_ids),
            "book_sections": sec_count,
            "book_equations": eq_count,
            "book_index_terms": idx_term_count,
            "github_repos": len(catalog_repos),
        },
        "errors": errors,
        "warnings": warnings,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-nodes", type=int, default=162)
    parser.add_argument("--expected-diagrams", type=int, default=72)
    parser.add_argument("--expected-checklists", type=int, default=21)
    parser.add_argument("--expected-glossary", type=int, default=2280)
    parser.add_argument("--expected-repos", type=int, default=52)
    parser.add_argument("--min-lines", type=int, default=120)
    args = parser.parse_args()

    result = validate(
        expected_nodes=args.expected_nodes,
        expected_diagrams=args.expected_diagrams,
        expected_checklists=args.expected_checklists,
        expected_glossary=args.expected_glossary,
        expected_repos=args.expected_repos,
        min_lines=args.min_lines,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
