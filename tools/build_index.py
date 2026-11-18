#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compiler & Index Builder for Razavi CMOS Knowledge Brain (release 2026.11.18.4).

Pure Python 3 standard library, zero external dependencies, zero bytecode generation.
Builds across all 10 knowledge & EDA domains:
  - kb/graph/edges.jsonl (when --merge-edges is passed; cleans temporary edges-*.jsonl shards)
  - kb/router-index.json (with deterministic 22-column 2D coordinates, section_coords & 7-stage cycle tags)
  - kb/manifest.json (tracking all files under kb/, including coordinates/, checklists/ & github-skills/)
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
RELEASE_VERSION = "2026.11.18.4"

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
        "title_en": "Switched-Capacitor Circuits, Comparators/ADCs, Oscillators & PLLs",
        "chapters": [13, 15, 16],
    },
    {
        "id": "nonideal-and-physical",
        "layer": 7,
        "title_vi": "Tầng 7 · Phi tuyến, Mismatch, Công nghệ & Bố cục Layout",
        "title_en": "Nonlinearity, Pelgrom Mismatch, Latch-Up, Layout & ESD",
        "chapters": [14, 18, 19],
    },
    {
        "id": "power-management-ic",
        "layer": 8,
        "title_vi": "Tầng 8 · Quản lý Nguồn PMIC: Capless LDO, Buck, Boost, Buck-Boost & Bảo vệ",
        "title_en": "PMIC Power Management: Capless LDO, Buck, Boost, Buck-Boost & Protections",
        "chapters": [2, 8, 10, 12, 13, 18, 19],
    },
    {
        "id": "ams-filters-and-system",
        "layer": 9,
        "title_vi": "Tầng 9 · Bộ lọc Liên tục, DAC, ΔΣ/Pipeline ADC, AFE & Kiến trúc Hệ thống",
        "title_en": "Continuous-Time Filters, DAC, ΔΣ/Pipeline ADC, Precision AFE & Chip Architecture",
        "chapters": [4, 5, 6, 7, 8, 9, 12, 13, 14, 15, 16, 19],
    },
    {
        "id": "eda-and-github-skills",
        "layer": 10,
        "title_vi": "Tầng 10 · Chu trình Tối ưu Khép kín Cadence IC617, SpectreRF & GitHub Skills",
        "title_en": "Closed-Loop Cadence IC617, SpectreRF, gm/ID & Pareto Optimization Skills",
        "chapters": list(range(1, 20)),
    },
]

RAZAVI_CORE_DOMAINS = {
    "foundations",
    "stages-and-mirrors",
    "dynamics-noise-feedback",
    "opamps-and-compensation",
    "references-and-biasing",
    "sampled-and-clocked",
    "nonideal-and-physical",
}

DOMAIN_CHAPTER_MAP = {
    d["id"]: set(d["chapters"]) for d in DOMAIN_METADATA if d["id"] in RAZAVI_CORE_DOMAINS
}

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

DOMAIN_DEFAULT_DIAGRAM = {
    "power-management-ic": "../../diagrams/synchronous-buck-converter.svg",
    "ams-filters-and-system": "../../diagrams/deltasigma-ciff-modulator.svg",
    "eda-and-github-skills": "../../diagrams/closed-loop-cadence-codex-flow.svg",
}

NODE_ID_ALIASES = {
    "topo-telescopic-cascode-ota": "topo-telescopic-cascode-opamp",
    "topo-two-stage-miller-opamp": "topo-two-stage-opamp",
    "topo-gain-boosted-folded-cascode": "topo-gain-boosted-cascode",
    "tech-miller-nulling-resistor": "tech-miller-rhp-zero-nulling-and-cascode-comp",
    "trap-rhp-feedforward-zero": "law-miller-theorem-and-rhp-zero",
    "skill-hierarchical-chip-spec-budgeting-and-bias-distribution": "tech-hierarchical-chip-spec-budgeting-and-interfaces",
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
    "github_refs",
    "glossary_codes",
    "process_agnostic",
    "roles",
    "symptoms_addressed",
    "limitations",
    "checklists",
]

TRACK_LABELS = {
    0: "laws_and_physics",
    1: "circuit_topologies",
    2: "sizing_and_compensation",
    3: "github_eda_skills",
}

DESIGN_CYCLE_METADATA = [
    {
        "stage": 1,
        "id": "1_spec_and_kb",
        "title_vi": "1 · Tra cứu KB & Bất biến Cấu trúc",
        "title_en": "KB Lookup, Topology Selection & Structural Checklists",
        "tool": "kb_lookup.py + checklists/*.json",
    },
    {
        "stage": 2,
        "id": "2_hierarchical_budget",
        "title_vi": "2 · Phân bổ Chỉ tiêu & Hợp đồng Giao tiếp",
        "title_en": "Top-Down Spec Budgeting & Block Interface Contracts",
        "tool": "spec.json + project.json blocks[]",
    },
    {
        "stage": 3,
        "id": "3_gmid_physics_sizing",
        "title_vi": "3 · Định cỡ Vật lý gm/ID (< 5 ms)",
        "title_en": "PDK gm/ID Lookup-Table Inverse Sizing",
        "tool": "gpdk_techsweep.py + gmid_lut.py",
    },
    {
        "stage": 4,
        "id": "4_schematic_and_veriloga",
        "title_vi": "4 · Dựng Schematic OA & Mô hình Verilog-A",
        "title_en": "Virtuoso IC617 Live Bridge & Behavioral Shell",
        "tool": "ic617_live_bridge.il + ic617_client.py",
    },
    {
        "stage": 5,
        "id": "5_spectre_psf_audit",
        "title_vi": "5 · Kiểm toán OP Vùng Bão hòa & Vòng STB/PSTB",
        "title_en": "Spectre Simulation & Automated PSF OP/Waveform Audit",
        "tool": "cadence_exec.py + psf_audit.py",
    },
    {
        "stage": 6,
        "id": "6_pareto_optimization",
        "title_vi": "6 · Ma trận Độ nhạy & Tối ưu Vùng Tin cậy Pareto",
        "title_en": "Sensitivity Jacobian & Constrained Trust-Region Optimization",
        "tool": "sizing_opt.py",
    },
    {
        "stage": 7,
        "id": "7_pvt_mc_pex_signoff",
        "title_vi": "7 · Nghiệm thu Đa góc PVT, Monte Carlo & Hậu Layout PEX",
        "title_en": "Worst-Case PVT, Pelgrom Monte Carlo & Post-Layout PEX Signoff",
        "tool": "psf_audit.py + CACE Signoff",
    },
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


def normalize_card_file(md_path, valid_checklists, valid_glossary_ids, catalog_repos=None):
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

    diag = meta.get("diagram", "")
    if not diag:
        m_img = re.search(r"!\[[^\]]*\]\((\.\./\.\./diagrams/[^)]+\.svg)\)", body)
        if m_img:
            diag = m_img.group(1)
        elif expected_domain in DOMAIN_DEFAULT_DIAGRAM:
            diag = DOMAIN_DEFAULT_DIAGRAM[expected_domain]
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

    if "github_refs" in meta and isinstance(meta["github_refs"], list):
        norm_gh = []
        for entry in meta["github_refs"]:
            if isinstance(entry, str) and entry.strip():
                rname = entry.strip()
                norm_gh.append({
                    "repo": rname,
                    "url": f"https://github.com/{rname}",
                    "use": "Tham chiếu kiến trúc mạch và quy trình kiểm chứng mã nguồn mở đã kiểm định",
                })
            elif isinstance(entry, dict) and entry.get("repo"):
                rname = str(entry["repo"]).strip()
                norm_entry = dict(entry)
                norm_entry["repo"] = rname
                if not norm_entry.get("url"):
                    norm_entry["url"] = f"https://github.com/{rname}"
                if not norm_entry.get("use"):
                    norm_entry["use"] = "Tham chiếu kiến trúc mạch và quy trình kiểm chứng mã nguồn mở đã kiểm định"
                norm_gh.append(norm_entry)
        if catalog_repos and (expected_domain != "eda-and-github-skills" and meta.get("kind") != "skill"):
            # Keep all catalog-matched entries on theory cards; drop non-catalog typos if at least one valid remains
            in_cat = [g for g in norm_gh if g["repo"] in catalog_repos]
            if in_cat and len(in_cat) != len(norm_gh):
                norm_gh = in_cat
        if norm_gh != meta["github_refs"]:
            meta["github_refs"] = norm_gh
            changed = True

    if valid_glossary_ids and isinstance(meta.get("glossary_codes"), list):
        filtered_codes = [c for c in meta["glossary_codes"] if c in valid_glossary_ids]
        if filtered_codes != meta["glossary_codes"]:
            meta["glossary_codes"] = filtered_codes
            changed = True

    if valid_checklists and isinstance(meta.get("checklists"), list):
        filtered_cl = [c for c in meta["checklists"] if c in valid_checklists]
        if not filtered_cl and "common-mos" in valid_checklists:
            filtered_cl = ["common-mos"]
        if filtered_cl != meta["checklists"]:
            meta["checklists"] = filtered_cl
            changed = True

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
    state = {}

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


def merge_edge_fragments(valid_node_ids, cleanup_fragments=True):
    """Merges edges.jsonl + all edges-*.jsonl shards (edges-pmic-a/b, edges-ams-a/b, edges-gh-v3, etc.)."""
    graph_dir = os.path.join(KB_ROOT, "graph")
    os.makedirs(graph_dir, exist_ok=True)
    frag_names = sorted(
        fn
        for fn in os.listdir(graph_dir)
        if fn.startswith("edges-") and fn.endswith(".jsonl") and fn != "edges.jsonl"
    )
    out_path = os.path.join(graph_dir, "edges.jsonl")

    sources_to_read = []
    if os.path.isfile(out_path):
        sources_to_read.append(out_path)
    for fn in frag_names:
        sources_to_read.append(os.path.join(graph_dir, fn))

    raw_edges = []
    for src in sources_to_read:
        with open(src, "r", encoding="utf-8-sig") as f:
            for line_no, line in enumerate(f, 1):
                s = line.strip()
                if not s:
                    continue
                obj = json.loads(s)
                raw_edges.append((os.path.basename(src), line_no, obj))

    merged = []
    seen_keys = set()
    upgrades_adj = defaultdict(set)
    degree = defaultdict(int)
    dropped = []

    for src_name, line_no, obj in raw_edges:
        u = NODE_ID_ALIASES.get(obj.get("from", ""), obj.get("from", ""))
        v = NODE_ID_ALIASES.get(obj.get("to", ""), obj.get("to", ""))
        rel = obj.get("rel", "governed_by")
        if u == v or u not in valid_node_ids or v not in valid_node_ids:
            dropped.append((src_name, line_no, obj.get("from"), obj.get("to"), rel))
            continue
        key = (u, v, rel)
        if key in seen_keys:
            continue
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
        "dropped_details": dropped[:25],
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
            out = []
            for item in items:
                d_copy = dict(item)
                if "file" not in d_copy and "filename" in d_copy:
                    d_copy["file"] = d_copy["filename"]
                if "viewBox" not in d_copy and "width" in d_copy and "height" in d_copy:
                    d_copy["viewBox"] = f"0 0 {d_copy['width']} {d_copy['height']}"
                out.append(d_copy)
            return out
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


def load_book_coordinates():
    fp = os.path.join(KB_ROOT, "coordinates", "book-coordinates.json")
    if not os.path.isfile(fp):
        return {"sections": [], "equations": [], "index_terms": []}, defaultdict(list), defaultdict(list)
    with open(fp, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    node_to_sections = defaultdict(list)
    node_to_eqs = defaultdict(list)
    for sec in data.get("sections", []):
        sid = sec.get("section_id")
        for nid in sec.get("primary_nodes", []):
            if sid and sid not in node_to_sections[nid]:
                node_to_sections[nid].append(sid)
    for eq in data.get("equations", []):
        eid = eq.get("eq_id") or eq.get("eq_num")
        for nid in [eq.get("node_id")] + list(eq.get("related_nodes") or []):
            if nid and eid and eid not in node_to_eqs[nid]:
                node_to_eqs[nid].append(eid)
    return data, node_to_sections, node_to_eqs


def load_github_catalog():
    fp = os.path.join(KB_ROOT, "github-skills", "catalog.json")
    if not os.path.isfile(fp):
        return {"repositories": []}
    with open(fp, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def section_sort_tuple(sec_str):
    if not sec_str:
        return (999, 999, 999)
    m = re.search(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", str(sec_str))
    if not m:
        return (999, 999, 999)
    return (
        int(m.group(1)),
        int(m.group(2)) if m.group(2) is not None else 0,
        int(m.group(3)) if m.group(3) is not None else 0,
    )


def assign_design_cycle_stages(node):
    """Tags every card with its applicable stage(s) in the 7-Stage Optimal Design Cycle."""
    nid = node["id"]
    kind = node.get("kind", "concept")
    dom = node.get("domain", "")
    stages = set()

    if nid in ("concept-analog-design-octagon", "skill-25-topology-selection-decision-matrix") or kind in ("concept", "law"):
        stages.add(1)
    if kind == "topology":
        stages.add(1)
        stages.add(4)
    if re.search(r"budget|interface|central-bias-hub|protections-por-uvlo|cace", nid):
        stages.add(2)
    if re.search(r"gmid|gm-id|vdsmin|sizing|scaling|step-by-step-sizing|current-mirrors|pelgrom", nid):
        stages.add(3)
    if re.search(r"ic617|schematic|veriloga|averaged-veriloga|startup|cmfb", nid):
        stages.add(4)
    if re.search(r"stb|pss|pnoise|pstb|psf|ocean|middlebrook|nyquist|phase-margin|compensat|type2|type3|slope-comp", nid):
        stages.add(5)
    if re.search(r"closed-loop-sizing|pareto|slewing-vs-linear|octagon|tradeoff|charge-pump-dcdc|hs-bootstrap", nid):
        stages.add(6)
    if re.search(r"pvt|montecarlo|layout|pex|latchup|esd|mismatch|substrate|interconnect|cace|protections", nid) or dom == "nonideal-and-physical":
        stages.add(7)

    if not stages:
        stages.add(1 if kind != "skill" else 5)
    return sorted(stages)


def assign_2d_coordinates(nodes):
    """Assigns deterministic, collision-free 2D grid & pixel coordinates across 22 columns.

    X-axis (`grid_col` 1..22):
      - Columns 1..19: Primary Razavi Chapter (Ch.01 .. Ch.19) + Chapter-specific Skill Testbenches
      - Column 20: Layer 8 · PMIC Power Management (Buck, Boost, 4-SW Buck-Boost, Capless LDO, POR/UVLO/OCP)
      - Column 21: Layer 9 · AMS Filters, Data Converters (DAC, ΔΣ, Pipeline), Precision AFE & Bias Hub
      - Column 22: Layer 10 · Cross-Chapter Closed-Loop Cadence IC617, PSF Audit, gm/ID LUT & Pareto Optimization
    Y-axis (`grid_row` & `track`):
      - 4 Functional Sub-track Swimlanes:
        0: laws_and_physics (concept / law / physical_rule)
        1: circuit_topologies (topology)
        2: sizing_and_compensation (technique)
        3: github_eda_skills (skill)
    """
    cells = [defaultdict(list) for _ in range(4)]

    for node in nodes:
        nid = node["id"]
        kind = node.get("kind", "concept")
        dom = node.get("domain", "")
        is_skill = kind == "skill" or dom == "eda-and-github-skills" or nid.startswith("skill-")

        if dom == "power-management-ic":
            col = 20
            if is_skill:
                track_idx = 3
            elif kind == "topology":
                track_idx = 1
            elif kind == "technique":
                track_idx = 2
            else:
                track_idx = 0
        elif dom == "ams-filters-and-system":
            col = 21
            if is_skill:
                track_idx = 3
            elif kind == "topology":
                track_idx = 1
            elif kind == "technique":
                track_idx = 2
            else:
                track_idx = 0
        elif is_skill:
            track_idx = 3
            chs = node.get("chapters") or []
            if (
                re.search(
                    r"ic617|ocean|psf|techsweep|gmid-lut|gm-id-lookup|closed-loop-sizing|veriloga|pex|cace|25-topology|montecarlo|layout-common-centroid",
                    nid,
                )
                or not chs
                or len(chs) > 4
            ):
                col = 22
            else:
                col = int(chs[0])
        else:
            if kind == "topology":
                track_idx = 1
            elif kind == "technique":
                track_idx = 2
            else:
                track_idx = 0
            col = int(node["section_coords"]["primary_chapter"])

        col = max(1, min(22, col))
        cells[track_idx][col].append(node)

    for t in range(4):
        for col in cells[t]:
            cells[t][col].sort(
                key=lambda n: (section_sort_tuple(n["section_coords"]["primary_section"]), n["id"])
            )

    COL_W = 216
    LEFT_PAD = 150
    ROW_H = 58
    LANE_PAD_TOP = 36
    LANE_PAD_BOT = 20

    cur_y = 74
    global_row_offset = 0

    for t in range(4):
        max_rows = max((len(arr) for arr in cells[t].values()), default=0)
        if max_rows == 0:
            continue
        lane_h = LANE_PAD_TOP + max_rows * ROW_H + LANE_PAD_BOT
        for col, arr in sorted(cells[t].items()):
            cx = LEFT_PAD + (col - 1) * COL_W
            for r_idx, node in enumerate(arr):
                cy = cur_y + LANE_PAD_TOP + r_idx * ROW_H + 22
                grid_row = global_row_offset + r_idx + 1
                node["coord_2d"] = {
                    "x": cx,
                    "y": cy,
                    "grid_col": col,
                    "grid_row": grid_row,
                    "track": TRACK_LABELS[t],
                    "track_index": t,
                }
        cur_y += lane_h + 14
        global_row_offset += max_rows


def build_indices(normalize_cards=False, merge_edges=False, cleanup_fragments=True):
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
    coords_data, node_to_sections, node_to_eqs = load_book_coordinates()
    catalog_data = load_github_catalog()
    catalog_repos = {
        r["repo"]
        for r in (catalog_data.get("repositories") or catalog_data.get("repos") or [])
        if isinstance(r, dict) and r.get("repo")
    }

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
            if normalize_card_file(fp, valid_checklists, valid_glossary_ids, catalog_repos=catalog_repos):
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
        github_refs = meta.get("github_refs") or []
        chapters = sorted(
            {
                int(r["chapter"])
                for r in refs
                if isinstance(r, dict) and "chapter" in r and str(r["chapter"]).isdigit()
            }
        )
        for ch in chapters:
            chapter_to_nodes[ch].append(nid)

        dom_chs = DOMAIN_CHAPTER_MAP.get(domain, set())
        primary_ch = chapters[0] if chapters else 1
        primary_sec = ""
        for r in refs:
            if isinstance(r, dict) and int(r.get("chapter", 0)) in dom_chs:
                primary_ch = int(r["chapter"])
                primary_sec = str(r.get("section", ""))
                break
        if not primary_sec and refs and isinstance(refs[0], dict):
            primary_ch = int(refs[0].get("chapter", primary_ch))
            primary_sec = str(refs[0].get("section", ""))

        ref_sections = [str(r.get("section", "")) for r in refs if isinstance(r, dict) and r.get("section")]
        for extra_s in node_to_sections.get(nid, []):
            if extra_s not in ref_sections:
                ref_sections.append(extra_s)

        ref_pages = [str(r.get("pages", "")) for r in refs if isinstance(r, dict) and r.get("pages")]
        ref_eqs = []
        for r in refs:
            if isinstance(r, dict):
                for eq in r.get("equations") or []:
                    if str(eq) not in ref_eqs:
                        ref_eqs.append(str(eq))
        for extra_e in node_to_eqs.get(nid, []):
            clean_e = str(extra_e).replace("Eq.", "")
            if clean_e not in ref_eqs:
                ref_eqs.append(clean_e)

        section_coords = {
            "primary_chapter": primary_ch,
            "primary_section": primary_sec.split(",")[0].split("-")[0].strip() if primary_sec else f"{primary_ch}.1",
            "sections": ref_sections,
            "pages": ref_pages,
            "equations": ref_eqs,
        }

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
            f"ch{r.get('chapter','')} {r.get('section','')} {r.get('pages','')} {' '.join(str(x) for x in (r.get('equations') or []))}"
            for r in refs
            if isinstance(r, dict)
        )
        gh_str = " ".join(
            f"{g.get('repo','')} {g.get('use','')}" if isinstance(g, dict) else str(g)
            for g in github_refs
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
                gh_str,
                gterms_text,
                headings_extra,
            ]
        )

        rel_path = f"kb/nodes/{domain}/{nid}.md"
        node_entry = {
            "id": nid,
            "kind": meta.get("kind", "concept"),
            "domain": domain,
            "title_vi": meta.get("title_vi", ""),
            "title_en": meta.get("title_en", ""),
            "summary": summary,
            "diagram": meta.get("diagram", ""),
            "razavi_refs": refs,
            "github_refs": github_refs,
            "chapters": chapters,
            "section_coords": section_coords,
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
        node_entry["design_stages"] = assign_design_cycle_stages(node_entry)
        nodes.append(node_entry)

    assign_2d_coordinates(nodes)

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

    skill_node_count = sum(1 for n in nodes if n["domain"] == "eda-and-github-skills" or n["kind"] == "skill")
    razavi_node_count = len(nodes) - skill_node_count
    razavi_core_node_count = sum(1 for n in nodes if n["domain"] in RAZAVI_CORE_DOMAINS)
    pmic_node_count = domain_counts.get("power-management-ic", 0)
    ams_node_count = domain_counts.get("ams-filters-and-system", 0)
    eda_domain_node_count = domain_counts.get("eda-and-github-skills", 0)
    book_section_count = len(coords_data.get("sections", []))
    book_equation_count = len(coords_data.get("equations", []))
    book_index_term_count = len(coords_data.get("index_terms", []))
    github_repo_count = len(catalog_data.get("repositories") or catalog_data.get("repos") or [])

    router_index = {
        "schema": "razavi-cmos-brain.router-index.v1",
        "release": RELEASE_VERSION,
        "stats": {
            "node_count": len(nodes),
            "domain_count": len(domains_out),
            "razavi_core_node_count": razavi_core_node_count,
            "pmic_node_count": pmic_node_count,
            "ams_node_count": ams_node_count,
            "eda_domain_node_count": eda_domain_node_count,
            "razavi_node_count": razavi_node_count,
            "skill_node_count": skill_node_count,
            "edge_count": edge_count,
            "checklist_count": len(checklists),
            "diagram_count": svg_count,
            "glossary_count": glossary_count,
            "book_section_count": book_section_count,
            "book_equation_count": book_equation_count,
            "book_index_term_count": book_index_term_count,
            "github_repo_count": github_repo_count,
        },
        "design_cycle": DESIGN_CYCLE_METADATA,
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

    manifest_fp = os.path.join(KB_ROOT, "manifest.json")
    kb_files = []
    for root_dir, dirs, files in os.walk(KB_ROOT):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for fn in sorted(files):
            full = os.path.join(root_dir, fn)
            if os.path.abspath(full) == os.path.abspath(manifest_fp):
                continue
            if fn.startswith("edges-") and fn.endswith(".jsonl") and fn != "edges.jsonl":
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
        "domain_count": len(domains_out),
        "node_count": len(nodes),
        "razavi_core_node_count": razavi_core_node_count,
        "pmic_node_count": pmic_node_count,
        "ams_node_count": ams_node_count,
        "eda_domain_node_count": eda_domain_node_count,
        "razavi_node_count": razavi_node_count,
        "skill_node_count": skill_node_count,
        "edge_count": edge_count,
        "diagram_count": svg_count,
        "checklist_count": len(checklists),
        "glossary_count": glossary_count,
        "book_section_count": book_section_count,
        "book_equation_count": book_equation_count,
        "github_repo_count": github_repo_count,
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
        "domain_count": len(domains_out),
        "node_count": len(nodes),
        "razavi_core_node_count": razavi_core_node_count,
        "pmic_node_count": pmic_node_count,
        "ams_node_count": ams_node_count,
        "eda_domain_node_count": eda_domain_node_count,
        "razavi_node_count": razavi_node_count,
        "skill_node_count": skill_node_count,
        "edge_count": edge_count,
        "diagram_count": svg_count,
        "checklist_count": len(checklists),
        "glossary_count": glossary_count,
        "book_section_count": book_section_count,
        "book_equation_count": book_equation_count,
        "github_repo_count": github_repo_count,
        "manifest_files": len(kb_files),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--normalize-cards", action="store_true", help="Normalize frontmatter keys & diagram refs in node cards")
    parser.add_argument("--merge-edges", action="store_true", help="Merge edges-*.jsonl shards into edges.jsonl and remove shards")
    parser.add_argument("--cleanup-fragments", action="store_true", help="Backward-compatible alias (shards are cleaned automatically on --merge-edges)")
    parser.add_argument("--keep-fragments", action="store_true", help="Keep edges-*.jsonl shards on disk after --merge-edges")
    args = parser.parse_args()
    cleanup = not args.keep_fragments
    report = build_indices(
        normalize_cards=args.normalize_cards,
        merge_edges=args.merge_edges,
        cleanup_fragments=cleanup,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
