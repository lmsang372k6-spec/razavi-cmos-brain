#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1-Command Authoring, Rebuilding & Sync Helper for Razavi CMOS Knowledge Brain (2026.11.18.3).

Pure Python 3 standard library. Zero external pip packages, zero bytecode clutter.

Usage:
  python -B tools/manage_kb.py status
  python -B tools/manage_kb.py new-card <domain> <node-id> "<title_vi>" "<title_en>" --chapter <N>
  python -B tools/manage_kb.py add-edge <from_id> <to_id> <rel> "<when>" "<cost>" "<ref>"
  python -B tools/manage_kb.py rebuild [--export-bundle PATH]
"""
import argparse
import gzip
import json
import os
import subprocess
import sys

sys.dont_write_bytecode = True

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB_DIR = os.path.join(ROOT, "kb")
NODES_DIR = os.path.join(KB_DIR, "nodes")
EDGES_PATH = os.path.join(KB_DIR, "graph", "edges.jsonl")

VALID_DOMAINS = (
    "foundations",
    "stages-and-mirrors",
    "dynamics-noise-feedback",
    "opamps-and-compensation",
    "references-and-biasing",
    "sampled-and-github-skills" if False else "sampled-and-clocked",
    "nonideal-and-physical",
    "eda-and-github-skills",
)

VALID_RELS = (
    "upgrades_to",
    "fixes",
    "compensated_by",
    "trades_off_with",
    "requires",
    "governed_by",
    "layout_constrained_by",
)


def parse_frontmatter(md_text):
    lines = md_text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("Missing opening --- frontmatter delimiter")
    end_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break
    if end_idx is None:
        raise ValueError("Missing closing --- frontmatter delimiter")
    meta = json.loads("\n".join(lines[1:end_idx]))
    body = "\n".join(lines[end_idx + 1 :]).strip()
    return meta, body


def cmd_status():
    manifest_path = os.path.join(KB_DIR, "manifest.json")
    router_path = os.path.join(KB_DIR, "router-index.json")
    with open(manifest_path, "r", encoding="utf-8") as mf:
        manifest = json.load(mf)
    with open(router_path, "r", encoding="utf-8") as rf:
        router = json.load(rf)
    stats = router.get("stats", {})
    print(json.dumps({
        "release": manifest.get("release"),
        "nodes": len(router.get("nodes", [])),
        "razavi_nodes": stats.get("razavi_node_count"),
        "skill_nodes": stats.get("skill_node_count"),
        "chapters_covered": len(router.get("chapters", [])),
        "edges": manifest.get("edge_count"),
        "checklists": len(router.get("checklists", [])),
        "diagrams": len(router.get("diagrams", [])),
        "glossary_terms": manifest.get("glossary_count"),
        "book_sections": stats.get("book_section_count"),
        "book_equations": stats.get("book_equation_count"),
        "github_repos": stats.get("github_repo_count"),
        "tracked_kb_files": manifest.get("file_count", len(manifest.get("files", []))),
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_new_card(args):
    if args.domain not in VALID_DOMAINS:
        raise SystemExit(f"Invalid domain '{args.domain}'. Choose from: {', '.join(VALID_DOMAINS)}")
    if args.node_id.startswith("skill-") or args.domain == "eda-and-github-skills":
        kind = "skill"
    elif args.node_id.startswith("topo-"):
        kind = "topology"
    elif args.node_id.startswith("law-"):
        kind = "law"
    elif args.node_id.startswith("tech-"):
        kind = "technique"
    else:
        kind = "concept"

    dest_dir = os.path.join(NODES_DIR, args.domain)
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, f"{args.node_id}.md")
    if os.path.exists(dest_path):
        raise SystemExit(f"Card already exists: {dest_path}")

    frontmatter = {
        "id": args.node_id,
        "kind": kind,
        "domain": args.domain,
        "title_vi": args.title_vi,
        "title_en": args.title_en,
        "summary": "Tóm tắt ngắn gọn bản chất vật lý, vai trò cấu trúc và phạm vi ứng dụng của thẻ.",
        "diagram": f"../../diagrams/{args.diagram}",
        "razavi_refs": [
            {
                "chapter": args.chapter,
                "section": args.section,
                "pages": "TBD",
                "equations": [],
            }
        ],
    }
    if kind == "skill":
        frontmatter["github_refs"] = [
            {
                "repo": "owner/repo",
                "url": "https://github.com/owner/repo",
                "use": "Mô tả luồng kiểm chứng / tự động hóa thực chiến tham chiếu từ kho mã nguồn.",
            }
        ]
    frontmatter.update({
        "glossary_codes": ["T003"],
        "process_agnostic": True,
        "roles": {
            "core_element": "Mô tả chức năng cốt lõi của từng nhánh hoặc phần tử trong cấu trúc."
        },
        "symptoms_addressed": ["describe-addressed-symptom"],
        "limitations": ["describe-key-limitation"],
        "checklists": ["common-mos"],
    })

    template = (
        "---\n"
        + json.dumps(frontmatter, ensure_ascii=False, indent=2)
        + "\n---\n\n"
        + "## 1. Bản chất Nguyên lý, Sơ đồ Mạch & Vai trò Từng Nhánh Cấu trúc\n\n"
        + f"![{args.title_vi}](../../diagrams/{args.diagram})\n\n"
        + "- Trình bày trực giác vật lý, đường phân cực tĩnh (DC bias) và đường tín hiệu nhỏ (small-signal path).\n\n"
        + "## 2. Hệ Phương trình Cốt lõi & Tư duy \"Nhìn Mạch Đọc Nhanh\" (Analysis by Inspection)\n\n"
        + "- Trình bày đầy đủ phương trình giải tích và quy tắc ước lượng nhanh trở kháng, độ lợi, cực/zero.\n\n"
        + "## 3. Bất biến Cấu trúc & Các Bẫy Lỗi Kinh điển (Structural Invariants & Traps)\n\n"
        + "- **[INV-01]** Điều kiện bất biến bắt buộc để mạch hoạt động đúng trên mọi tiến trình.\n"
        + "- **[TRAP-01]** Bẫy thiết kế phổ biến, cơ chế vật lý gây lỗi và dấu hiệu nhận biết.\n\n"
        + "## 4. Lộ trình Nâng cấp Cấu trúc & Bát giác Đánh đổi (Upgrade Paths & Design Octagon)\n\n"
        + "- **Nâng cấp từ:** Nêu cấu trúc tiền nhiệm và giới hạn được giải quyết.\n"
        + "- **Hướng nâng cấp tiếp theo:** Nêu cấu trúc kế tiếp khi chạm trần hiệu năng và chi phí đánh đổi.\n\n"
        + "## 5. Thích ứng Đa Tiến trình (90nm / 65nm / 45nm) & Cách Kiểm chứng trong Cadence / Spectre\n\n"
        + "- Quy tắc định cỡ bất biến theo $V_{DS,\\min}$, $g_m/I_D$, $g_m r_o$ và quy trình dựng testbench kiểm chứng trên Virtuoso IC617 / Spectre.\n\n"
        + "## 6. Mốc Đối chiếu Sách Razavi & Thuật ngữ Chuẩn CLB\n\n"
        + f"- Behzad Razavi, *Design of Analog CMOS Integrated Circuits (2nd Ed.)*, Chapter {args.chapter}, §{args.section}.\n"
    )
    with open(dest_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(template)
    print(f"Created template card: {dest_path}")
    print("Fill all 6 sections (>=120 lines), then run: python -B tools/manage_kb.py rebuild")
    return 0


def cmd_add_edge(args):
    if args.rel not in VALID_RELS:
        raise SystemExit(f"Invalid relation '{args.rel}'. Choose from: {', '.join(VALID_RELS)}")
    new_edge = {
        "from": args.from_id,
        "to": args.to_id,
        "rel": args.rel,
        "when": args.when,
        "cost": args.cost,
        "ref": args.ref,
    }
    existing = []
    if os.path.isfile(EDGES_PATH):
        with open(EDGES_PATH, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if s:
                    existing.append(json.loads(s))
    for e in existing:
        if e.get("from") == args.from_id and e.get("to") == args.to_id and e.get("rel") == args.rel:
            raise SystemExit("Duplicate edge already exists in edges.jsonl")
    existing.append(new_edge)
    with open(EDGES_PATH, "w", encoding="utf-8", newline="\n") as f:
        for e in existing:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"Added edge: {args.from_id} --[{args.rel}]--> {args.to_id}")
    return 0


def export_offline_bundle(dest_gz_path):
    with open(os.path.join(KB_DIR, "router-index.json"), "r", encoding="utf-8") as rf:
        router = json.load(rf)
    diagrams_map = {d["file"]: d for d in router.get("diagrams", []) if "file" in d}
    nodes_payload = {}
    for n in router.get("nodes", []):
        nid = n["id"]
        rel_path = n.get("raw_rel_path") or n.get("path")
        full_md_path = os.path.join(ROOT, *rel_path.split("/"))
        with open(full_md_path, "r", encoding="utf-8") as mf:
            raw_md = mf.read()
        _, body = parse_frontmatter(raw_md)
        diag_file = os.path.basename(n.get("diagram", ""))
        nodes_payload[nid] = {
            "id": nid,
            "markdown": body,
            "diagram_info": diagrams_map.get(diag_file, {"file": diag_file, "path": f"kb/diagrams/{diag_file}"}),
        }
    bundle_obj = {
        "schema": "razavi-nodes-bundle.v1",
        "release": router.get("release", "2026.11.18.3"),
        "node_count": len(nodes_payload),
        "nodes": nodes_payload,
    }
    raw_bytes = json.dumps(bundle_obj, ensure_ascii=False, sort_keys=True).encode("utf-8")
    os.makedirs(os.path.dirname(os.path.abspath(dest_gz_path)), exist_ok=True)
    with open(dest_gz_path, "wb") as raw_f:
        with gzip.GzipFile(filename="nodes-bundle.json", mode="wb", fileobj=raw_f, mtime=0) as gz:
            gz.write(raw_bytes)
    print(f"Exported deterministic offline bundle: {dest_gz_path} ({os.path.getsize(dest_gz_path)} bytes)")


def cmd_rebuild(args):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    r1 = subprocess.call([sys.executable, "-B", os.path.join(ROOT, "tools", "build_index.py")], cwd=ROOT, env=env)
    if r1 != 0:
        raise SystemExit(r1)
    r2 = subprocess.call([sys.executable, "-B", os.path.join(ROOT, "validators", "validate_brain.py")], cwd=ROOT, env=env)
    if r2 != 0:
        raise SystemExit(r2)
    if args.export_bundle:
        export_offline_bundle(args.export_bundle)
    print("Rebuild + full 8-domain/coordinate/GitHub-skills/math/SVG/checklist/graph validation PASSED!")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Manage Razavi CMOS Knowledge Brain")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Show knowledge graph statistics")

    p_new = sub.add_parser("new-card", help="Scaffold a new 6-block Razavi or Skill card")
    p_new.add_argument("domain", choices=VALID_DOMAINS)
    p_new.add_argument("node_id")
    p_new.add_argument("title_vi")
    p_new.add_argument("title_en")
    p_new.add_argument("--chapter", type=int, required=True)
    p_new.add_argument("--section", default="1.1")
    p_new.add_argument("--diagram", default="upgrade-evolution-map.svg")

    p_edge = sub.add_parser("add-edge", help="Add a directed graph edge")
    p_edge.add_argument("from_id")
    p_edge.add_argument("to_id")
    p_edge.add_argument("rel", choices=VALID_RELS)
    p_edge.add_argument("when")
    p_edge.add_argument("cost")
    p_edge.add_argument("ref")

    p_reb = sub.add_parser("rebuild", help="Rebuild router-index.json + manifest.json and run full validator")
    p_reb.add_argument("--export-bundle", help="Optional path to export deterministic nodes-bundle.json.gz")

    args = parser.parse_args()
    if args.cmd == "status":
        return cmd_status()
    if args.cmd == "new-card":
        return cmd_new_card(args)
    if args.cmd == "add-edge":
        return cmd_add_edge(args)
    if args.cmd == "rebuild":
        return cmd_rebuild(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
