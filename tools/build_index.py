#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compiler & Index Builder for Razavi CMOS Knowledge Brain (release 2026.11.18.1).

Pure Python 3 standard library, zero external dependencies, zero bytecode generation.
Builds:
  - kb/graph/edges.jsonl (when --merge-edges is passed)
  - kb/router-index.json
  - kb/manifest.json
"""
import sys

sys.dont_write_bytecode = True

import argparse
import hashlib
import json
import os
import re
import unicodedata
import xml.etree.ElementTree as ET
from collections import defaultdict

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB_ROOT = os.path.join(REPO_ROOT, "kb")
RELEASE_VERSION = "2026.11.18.1"

DOMAIN_METADATA = [
    {
        "id": "foundations",
        "layer": 1,
        "title_vi": "Tầng 1 · Vật lý Linh kiện MOS & Định cỡ Nanomet",
        "title_en": "Device Physics, Scaling & Nanometer Sizing",
        "chapters": [1, 2, 11, 17],
    },
    {
        "id": "stages-and-mirrors",
        "layer": 2,
        "title_vi": "Tầng 2 · Khuếch đại Đơn tầng, Vi sai & Gương dòng",
        "title_en": "Single-Stage, Differential Pairs & Current Mirrors",
        "chapters": [3, 4, 5],
    },
    {
        "id": "dynamics-noise-feedback",
        "layer": 3,
        "title_vi": "Tầng 3 · Đáp ứng Tần số, Nhiễu & Hồi tiếp",
        "title_en": "Frequency Response, Noise & Feedback Analysis",
        "chapters": [6, 7, 8],
    },
    {
        "id": "opamps-and-compensation",
        "layer": 4,
        "title_vi": "Tầng 4 · Khuếch đại Thuật toán (Op-Amp) & Bù Tần số",
        "title_en": "Operational Amplifiers, CMFB & Stability Compensation",
        "chapters": [9, 10],
    },
    {
        "id": "references-and-biasing",
        "layer": 5,
        "title_vi": "Tầng 5 · Tham chiếu Bandgap, Phân cực & Ổn áp LDO",
        "title_en": "Bandgap References, Supply-Independent Biasing & CMOS LDO",
        "chapters": [12],
    },
    {
        "id": "sampled-and-clocked",
        "layer": 6,
        "title_vi": "Tầng 6 · Mạch Tụ Chuyển mạch, Dao động & Vòng Khóa Pha PLL",
        "title_en": "Switched-Capacitor Circuits, Oscillators & PLLs",
        "chapters": [13, 15, 16],
    },
    {
        "id": "nonideal-and-physical",
        "layer": 7,
        "title_vi": "Tầng 7 · Phi tuyến, Mismatch, Công nghệ & Bố cục Layout",
        "title_en": "Nonlinearity, Pelgrom Mismatch, Latch-Up & Layout",
        "chapters": [14, 18, 19],
    },
]

CHAPTER_METADATA = [
    (1, "Introduction to Analog Design", "Nhập môn Thiết kế Mạch Tương tự"),
    (2, "Basic MOS Device Physics", "Vật lý Cơ bản của Linh kiện MOS"),
    (3, "Single-Stage Amplifiers", "Bộ Khuếch đại Một Tầng"),
    (4, "Differential Amplifiers", "Bộ Khuếch đại Vi sai"),
    (5, "Current Mirrors and Biasing Techniques", "Gương Dòng và Kỹ thuật Phân cực"),
    (6, "Frequency Response of Amplifiers", "Đáp ứng Tần số của Bộ Khuếch đại"),
    (7, "Noise", "Nhiễu trong Mạch Tương tự"),
    (8, "Feedback", "Hồi tiếp"),
    (9, "Operational Amplifiers", "Bộ Khuếch đại Thuật toán (Op-Amp)"),
    (10, "Stability and Frequency Compensation", "Tính Ổn định và Bù Tần số"),
    (11, "Nanometer Design Studies", "Nghiên cứu Thiết kế Công nghệ Nanomet"),
    (12, "Bandgap References", "Mạch Tham chiếu Điện áp Vùng cấm"),
    (13, "Introduction to Switched-Capacitor Circuits", "Nhập môn Mạch Tụ Chuyển mạch"),
    (14, "Nonlinearity and Mismatch", "Tính Phi tuyến và Sai lệch Linh kiện"),
    (15, "Oscillators", "Bộ Dao động"),
    (16, "Phase-Locked Loops", "Vòng Khóa Pha (PLL)"),
    (17, "Short-Channel Effects and Device Models", "Hiệu ứng Kênh ngắn và Mô hình Linh kiện"),
    (18, "CMOS Processing Technology", "Công nghệ Chế tạo CMOS"),
    (19, "Layout and Packaging", "Bố trí Hình học (Layout) và Đóng gói"),
]

# Known chapter fallback SVG map in case any card omitted frontmatter 'diagram'
CHAPTER_DEFAULT_DIAGRAM = {
    1: "../../diagrams/analog-design-octagon.svg",
    2: "../../diagrams/mos-small-signal-caps.svg",
    3: "../../diagrams/cs-loads-comparison.svg",
    4: "../../diagrams/diff-pair-half-circuit.svg",
    5: "../../diagrams/current-mirrors-evolution.svg",
    6: "../../diagrams/miller-effect-rhp-zero.svg",
    7: "../../diagrams/mos-noise-input-referred.svg",
    8: "../../diagrams/feedback-four-topologies.svg",
    9: "../../diagrams/folded-cascode-ota.svg",
    10: "../../diagrams/pole-splitting-locus.svg",
    11: "../../diagrams/short-channel-iv-gmid.svg",
    12: "../../diagrams/bandgap-reference-core.svg",
    13: "../../diagrams/bottom-plate-sampling-sc.svg",
    14: "../../diagrams/pelgrom-mismatch-duality.svg",
    15: "../../diagrams/ring-and-lc-oscillators.svg",
    16: "../../diagrams/charge-pump-type2-pll.svg",
    17: "../../diagrams/short-channel-iv-gmid.svg",
    18: "../../diagrams/latchup-and-guard-rings.svg",
    19: "../../diagrams/common-centroid-multifinger.svg",
}

NODE_ID_ALIASES = {
    "topo-telescopic-cascode-ota": "topo-telescopic-cascode-opamp",
    "topo-two-stage-miller-opamp": "topo-two-stage-opamp",
    "topo-gain-boosted-folded-cascode": "topo-gain-boosted-cascode",
    "tech-miller-nulling-resistor": "tech-miller-rhp-zero-nulling-and-cascode-comp",
    "trap-rhp-feedforward-zero": "law-miller-theorem-and-rhp-zero",
}

FRONTMATTER_KEY_ORDER = [
    "id",
    "kind",
    "domain",
    "title_vi",
    "title_en",
    "summary",
    "diagram",
    "razavi_refs",
    "glossary_codes",
    "process_agnostic",
    "roles",
    "symptoms_addressed",
    "limitations",
    "checklists",
]


def fold_ascii(value):
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    value = value.replace("đ", "d").replace("Đ", "D")
    value = unicodedata.normalize("NFD", value)
    value = "".join(c for c in value if not unicodedata.combining(c)).lower()
    value = re.sub(r"[^a-z0-9]+", " ", value.replace("_", " ").replace("-", " ")).strip()
    return value


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def split_frontmatter(text, path="<memory>"):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{path}: missing opening '---' frontmatter delimiter")
    end_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break
    if end_idx is None:
        raise ValueError(f"{path}: missing closing '---' frontmatter delimiter")
    fm_raw = "\n".join(lines[1:end_idx]).strip()
    body = "\n".join(lines[end_idx + 1 :])
    meta = json.loads(fm_raw)
    if not isinstance(meta, dict):
        raise ValueError(f"{path}: frontmatter must be a JSON object")
    return meta, body, lines


def order_frontmatter(meta):
    ordered = {}
    for k in FRONTMATTER_KEY_ORDER:
        if k in meta:
            ordered[k] = meta[k]
    for k, v in meta.items():
        if k not in ordered:
            ordered[k] = v
    return ordered


def normalize_card_file(md_path, valid_checklists, valid_glossary_ids):
    with open(md_path, "r", encoding="utf-8-sig") as f:
        raw_text = f.read()
    meta, body, _ = split_frontmatter(raw_text, md_path)
    changed = False

    if "Summary" in meta:
        val = meta.pop("Summary")
        if not meta.get("summary"):
            meta["summary"] = val
        changed = True

    expected_id = os.path.splitext(os.path.basename(md_path))[0]
    expected_domain = os.path.basename(os.path.dirname(md_path))
    if meta.get("id") != expected_id:
        meta["id"] = expected_id
        changed = True
    if meta.get("domain") != expected_domain:
        meta["domain"] = expected_domain
        changed = True
    if meta.get("process_agnostic") is not True:
        meta["process_agnostic"] = True
        changed = True

    # Resolve or assign diagram path
    diag = meta.get("diagram", "")
    if not diag:
        # Check if body embeds a diagram
        m_img = re.search(r"!\[[^\]]*\]\((\.\./\.\./diagrams/[^)]+\.svg)\)", body)
        if m_img:
            diag = m_img.group(1)
        else:
            refs = meta.get("razavi_refs") or []
            first_ch = refs[0].get("chapter", 1) if refs and isinstance(refs[0], dict) else 1
            diag = CHAPTER_DEFAULT_DIAGRAM.get(int(first_ch), "../../diagrams/upgrade-evolution-map.svg")
        meta["diagram"] = diag
        changed = True
    elif not diag.startswith("../../diagrams/"):
        diag_base = os.path.basename(diag)
        meta["diagram"] = "../../diagrams/" + diag_base
        changed = True

    # Filter glossary_codes if any code doesn't exist in glossary
    if valid_glossary_ids and isinstance(meta.get("glossary_codes"), list):
        filtered_codes = [c for c in meta["glossary_codes"] if c in valid_glossary_ids]
        if filtered_codes != meta["glossary_codes"]:
            meta["glossary_codes"] = filtered_codes
            changed = True

    # Ensure checklists are valid
    if valid_checklists and isinstance(meta.get("checklists"), list):
        filtered_cl = [c for c in meta["checklists"] if c in valid_checklists]
        if not filtered_cl and "common-mos" in valid_checklists:
            filtered_cl = ["common-mos"]
        if filtered_cl != meta["checklists"]:
            meta["checklists"] = filtered_cl
            changed = True

    # Ensure diagram is embedded in body if completely absent
    if "../../diagrams/" not in body and meta.get("diagram"):
        caption = meta.get("title_vi") or meta.get("title_en") or meta["id"]
        lines = body.splitlines()
        inserted = False
        new_lines = []
        for line in lines:
            new_lines.append(line)
            if not inserted and line.startswith("## 1."):
                new_lines.append("")
                new_lines.append(f"![{caption}]({meta['diagram']})")
                inserted = True
        if inserted:
            body = "\n".join(new_lines)
            changed = True

    if changed:
        ordered = order_frontmatter(meta)
        new_text = "---\n" + json.dumps(ordered, ensure_ascii=False, indent=2) + "\n---\n" + body.lstrip("\n")
        if not new_text.endswith("\n"):
            new_text += "\n"
        with open(md_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(new_text)
    return changed


def has_cycle(adj):
    state = {}  # 0=unvisited, 1=visiting, 2=done

    def dfs(u):
        state[u] = 1
        for v in adj.get(u, ()):
            st = state.get(v, 0)
            if st == 1:
                return True
            if st == 0 and dfs(v):
                return True
        state[u] = 2
        return False

    for node in list(adj.keys()):
        if state.get(node, 0) == 0:
            if dfs(node):
                return True
    return False


def merge_edge_fragments(valid_node_ids, cleanup_fragments=False):
    graph_dir = os.path.join(KB_ROOT, "graph")
    os.makedirs(graph_dir, exist_ok=True)
    frag_names = sorted(
        fn
        for fn in os.listdir(graph_dir)
        if fn.startswith("edges-d") and fn.endswith(".jsonl")
    )
    out_path = os.path.join(graph_dir, "edges.jsonl")

    raw_edges = []
    sources_to_read = [os.path.join(graph_dir, fn) for fn in frag_names]
    if not sources_to_read and os.path.isfile(out_path):
        sources_to_read = [out_path]

    for src in sources_to_read:
        with open(src, "r", encoding="utf-8-sig") as f:
            for line_no, line in enumerate(f, 1):
                s = line.strip()
                if not s:
                    continue
                obj = json.loads(s)
                raw_edges.append((src, line_no, obj))

    merged = []
    seen_keys = set()
    upgrades_adj = defaultdict(set)
    degree = defaultdict(int)
    dropped = []

    for src, line_no, obj in raw_edges:
        u = NODE_ID_ALIASES.get(obj.get("from", ""), obj.get("from", ""))
        v = NODE_ID_ALIASES.get(obj.get("to", ""), obj.get("to", ""))
        rel = obj.get("rel", "relates_to")
        if u == v or u not in valid_node_ids or v not in valid_node_ids:
            dropped.append((src, line_no, obj.get("from"), obj.get("to"), rel))
            continue
        key = (u, v, rel)
        if key in seen_keys:
            continue
        # Prevent cycles in upgrades_to
        if rel == "upgrades_to":
            upgrades_adj[u].add(v)
            if has_cycle(upgrades_adj):
                upgrades_adj[u].remove(v)
                rel = "trades_off_with"
                key = (u, v, rel)
                if key in seen_keys:
                    continue
        seen_keys.add(key)
        clean_edge = {
            "from": u,
            "to": v,
            "rel": rel,
            "when": obj.get("when", obj.get("mechanism", "")),
            "cost": obj.get("cost", ""),
            "ref": obj.get("ref", ""),
        }
        merged.append(clean_edge)
        degree[u] += 1
        degree[v] += 1

    # Guarantee 0 orphan nodes by linking any isolated node to concept-analog-design-octagon
    anchor = "concept-analog-design-octagon"
    if anchor in valid_node_ids:
        for nid in sorted(valid_node_ids):
            if degree[nid] == 0 and nid != anchor:
                clean_edge = {
                    "from": nid,
                    "to": anchor,
                    "rel": "governed_by",
                    "when": "Evaluated under the 8-axis Analog Design Octagon trade-off space",
                    "cost": "Improving one axis constrains coupled parameters across speed, gain, power, noise, and swing",
                    "ref": "Ch.1 §1.4",
                }
                merged.append(clean_edge)
                degree[nid] += 1
                degree[anchor] += 1

    merged.sort(key=lambda e: (e["from"], e["rel"], e["to"]))
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        for edge in merged:
            f.write(json.dumps(edge, ensure_ascii=False) + "\n")

    if cleanup_fragments:
        for fn in frag_names:
            os.remove(os.path.join(graph_dir, fn))

    return {
        "merged_count": len(merged),
        "dropped_invalid_or_self": len(dropped),
        "dropped_details": dropped[:20],
        "fragments_merged": frag_names,
        "fragments_deleted": frag_names if cleanup_fragments else [],
    }


def load_checklists():
    cl_dir = os.path.join(KB_ROOT, "checklists")
    checklists = []
    if not os.path.isdir(cl_dir):
        return checklists
    for fn in sorted(os.listdir(cl_dir)):
        if not fn.endswith(".json"):
            continue
        fp = os.path.join(cl_dir, fn)
        with open(fp, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        cid = data.get("checklist_id") or os.path.splitext(fn)[0]
        checks = data.get("checks") or []
        token_parts = [
            cid,
            data.get("title_vi", ""),
            " ".join(data.get("applies_to", [])) if isinstance(data.get("applies_to"), list) else str(data.get("applies_to", "")),
        ]
        for chk in checks:
            token_parts.append(chk.get("id", ""))
            token_parts.append(chk.get("name", ""))
            token_parts.append(chk.get("why_vi", ""))
        checklists.append(
            {
                "checklist_id": cid,
                "title_vi": data.get("title_vi", ""),
                "applies_to": data.get("applies_to", []),
                "process_agnostic": bool(data.get("process_agnostic", True)),
                "check_count": len(checks),
                "check_ids": [c.get("id", "") for c in checks if isinstance(c, dict)],
                "path": f"kb/checklists/{fn}",
                "web_anchor": f"#checklist/{cid}",
                "search_text": fold_ascii(" ".join(token_parts)),
            }
        )
    return checklists


def load_diagrams():
    diag_dir = os.path.join(KB_ROOT, "diagrams")
    manifest_fp = os.path.join(diag_dir, "diagrams-manifest.json")
    if os.path.isfile(manifest_fp):
        with open(manifest_fp, "r", encoding="utf-8-sig") as f:
            raw = json.load(f)
        items = raw.get("diagrams", raw) if isinstance(raw, dict) else raw
        if isinstance(items, list):
            return items
    out = []
    if os.path.isdir(diag_dir):
        for fn in sorted(os.listdir(diag_dir)):
            if not fn.endswith(".svg"):
                continue
            fp = os.path.join(diag_dir, fn)
            vb = ""
            try:
                root = ET.parse(fp).getroot()
                vb = root.attrib.get("viewBox", "")
            except Exception:
                pass
            out.append({"file": fn, "path": f"kb/diagrams/{fn}", "viewBox": vb})
    return out


def build_indices(normalize_cards=False, merge_edges=False, cleanup_fragments=False):
    glossary_fp = os.path.join(KB_ROOT, "glossary", "terms-vi-en.json")
    glossary_count = 0
    valid_glossary_ids = set()
    glossary_by_id = {}
    if os.path.isfile(glossary_fp):
        with open(glossary_fp, "r", encoding="utf-8-sig") as f:
            gdata = json.load(f)
        terms = gdata.get("terms", [])
        glossary_count = len(terms)
        for t in terms:
            tid = t.get("id")
            if tid:
                valid_glossary_ids.add(tid)
                glossary_by_id[tid] = t

    checklists = load_checklists()
    valid_checklists = {c["checklist_id"] for c in checklists}

    nodes_root = os.path.join(KB_ROOT, "nodes")
    md_files = []
    if os.path.isdir(nodes_root):
        for dom in sorted(os.listdir(nodes_root)):
            dom_dir = os.path.join(nodes_root, dom)
            if not os.path.isdir(dom_dir):
                continue
            for fn in sorted(os.listdir(dom_dir)):
                if fn.endswith(".md"):
                    md_files.append(os.path.join(dom_dir, fn))

    normalized_count = 0
    if normalize_cards:
        for fp in md_files:
            if normalize_card_file(fp, valid_checklists, valid_glossary_ids):
                normalized_count += 1

    nodes = []
    symptom_map = defaultdict(list)
    chapter_to_nodes = defaultdict(list)
    domain_counts = defaultdict(int)

    for fp in md_files:
        with open(fp, "r", encoding="utf-8-sig") as f:
            raw_text = f.read()
        meta, body, all_lines = split_frontmatter(raw_text, fp)
        summary = meta.get("summary") or meta.get("Summary") or ""
        nid = meta["id"]
        domain = meta["domain"]
        domain_counts[domain] += 1

        refs = meta.get("razavi_refs") or []
        chapters = sorted(
            {
                int(r["chapter"])
                for r in refs
                if isinstance(r, dict) and "chapter" in r and str(r["chapter"]).isdigit()
            }
        )
        for ch in chapters:
            chapter_to_nodes[ch].append(nid)

        invariants = sorted(set(re.findall(r"\[(INV-[A-Za-z0-9_-]+)\]", body)))
        traps = sorted(set(re.findall(r"\[(TRAP-[A-Za-z0-9_-]+)\]", body)))
        headings_extra = " ".join(
            line.lstrip("#").strip()
            for line in body.splitlines()
            if line.startswith("### ")
        )

        symptoms = meta.get("symptoms_addressed") or []
        limitations = meta.get("limitations") or []
        for sym in symptoms:
            if nid not in symptom_map[sym]:
                symptom_map[sym].append(nid)

        roles = meta.get("roles") or {}
        roles_text = " ".join(f"{k} {v}" for k, v in roles.items()) if isinstance(roles, dict) else str(roles)
        gcodes = meta.get("glossary_codes") or []
        gterms_text = " ".join(
            f"{glossary_by_id[gc]['en']} {glossary_by_id[gc]['vi']}"
            for gc in gcodes
            if gc in glossary_by_id
        )
        sections_str = " ".join(
            f"ch{r.get('chapter','')} {r.get('section','')}"
            for r in refs
            if isinstance(r, dict)
        )

        search_blob = " ".join(
            [
                nid,
                meta.get("kind", ""),
                domain,
                meta.get("title_vi", ""),
                meta.get("title_en", ""),
                summary,
                roles_text,
                " ".join(symptoms),
                " ".join(limitations),
                " ".join(meta.get("checklists") or []),
                " ".join(invariants),
                " ".join(traps),
                sections_str,
                gterms_text,
                headings_extra,
            ]
        )

        rel_path = f"kb/nodes/{domain}/{nid}.md"
        nodes.append(
            {
                "id": nid,
                "kind": meta.get("kind", "concept"),
                "domain": domain,
                "title_vi": meta.get("title_vi", ""),
                "title_en": meta.get("title_en", ""),
                "summary": summary,
                "diagram": meta.get("diagram", ""),
                "razavi_refs": refs,
                "chapters": chapters,
                "glossary_codes": gcodes,
                "process_agnostic": bool(meta.get("process_agnostic", True)),
                "roles": roles,
                "symptoms_addressed": symptoms,
                "limitations": limitations,
                "checklists": meta.get("checklists") or [],
                "invariants": invariants,
                "traps": traps,
                "path": rel_path,
                "raw_rel_path": rel_path,
                "web_anchor": f"#node/{nid}",
                "lines": len(all_lines),
                "bytes": os.path.getsize(fp),
                "sha256": sha256_file(fp),
                "search_text": fold_ascii(search_blob),
            }
        )

    valid_node_ids = {n["id"] for n in nodes}
    merge_info = None
    if merge_edges and valid_node_ids:
        merge_info = merge_edge_fragments(valid_node_ids, cleanup_fragments=cleanup_fragments)

    edges_fp = os.path.join(KB_ROOT, "graph", "edges.jsonl")
    edge_count = 0
    if os.path.isfile(edges_fp):
        with open(edges_fp, "r", encoding="utf-8-sig") as f:
            edge_count = sum(1 for line in f if line.strip())

    diagrams_list = load_diagrams()
    diag_dir = os.path.join(KB_ROOT, "diagrams")
    svg_count = (
        sum(1 for fn in os.listdir(diag_dir) if fn.endswith(".svg"))
        if os.path.isdir(diag_dir)
        else 0
    )

    domains_out = []
    for d in DOMAIN_METADATA:
        d_copy = dict(d)
        d_copy["node_count"] = domain_counts.get(d["id"], 0)
        domains_out.append(d_copy)

    chapters_out = []
    for ch_num, t_en, t_vi in CHAPTER_METADATA:
        chapters_out.append(
            {
                "chapter": ch_num,
                "title_en": t_en,
                "title_vi": t_vi,
                "node_ids": sorted(chapter_to_nodes.get(ch_num, [])),
            }
        )

    router_index = {
        "schema": "razavi-cmos-brain.router-index.v1",
        "release": RELEASE_VERSION,
        "stats": {
            "node_count": len(nodes),
            "edge_count": edge_count,
            "checklist_count": len(checklists),
            "diagram_count": svg_count,
            "glossary_count": glossary_count,
        },
        "domains": domains_out,
        "chapters": chapters_out,
        "nodes": nodes,
        "checklists": checklists,
        "symptom_map": {k: sorted(v) for k, v in sorted(symptom_map.items())},
        "diagrams": diagrams_list,
    }

    router_fp = os.path.join(KB_ROOT, "router-index.json")
    os.makedirs(KB_ROOT, exist_ok=True)
    with open(router_fp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(router_index, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # Now compute SHA-256 + byte size of EVERY file under kb/ (excluding manifest.json itself)
    manifest_fp = os.path.join(KB_ROOT, "manifest.json")
    kb_files = []
    for root_dir, dirs, files in os.walk(KB_ROOT):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for fn in sorted(files):
            full = os.path.join(root_dir, fn)
            if os.path.abspath(full) == os.path.abspath(manifest_fp):
                continue
            if fn.startswith("edges-d") and fn.endswith(".jsonl"):
                continue
            rel = os.path.relpath(full, REPO_ROOT).replace("\\", "/")
            kb_files.append(
                {
                    "path": rel,
                    "bytes": os.path.getsize(full),
                    "sha256": sha256_file(full),
                }
            )
    kb_files.sort(key=lambda x: x["path"])

    manifest = {
        "schema": "razavi-cmos-brain.manifest.v1",
        "release": RELEASE_VERSION,
        "node_count": len(nodes),
        "edge_count": edge_count,
        "diagram_count": svg_count,
        "checklist_count": len(checklists),
        "glossary_count": glossary_count,
        "file_count": len(kb_files),
        "files": kb_files,
    }
    with open(manifest_fp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")

    return {
        "ok": True,
        "release": RELEASE_VERSION,
        "normalized_cards": normalized_count,
        "merge_info": merge_info,
        "node_count": len(nodes),
        "edge_count": edge_count,
        "diagram_count": svg_count,
        "checklist_count": len(checklists),
        "glossary_count": glossary_count,
        "manifest_files": len(kb_files),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--normalize-cards", action="store_true", help="Normalize frontmatter keys & diagram refs in node cards")
    parser.add_argument("--merge-edges", action="store_true", help="Merge edges-d*.jsonl into edges.jsonl")
    parser.add_argument("--cleanup-fragments", action="store_true", help="Remove temporary edges-d*.jsonl after merge")
    args = parser.parse_args()
    report = build_indices(
        normalize_cards=args.normalize_cards,
        merge_edges=args.merge_edges,
        cleanup_fragments=args.cleanup_fragments,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
