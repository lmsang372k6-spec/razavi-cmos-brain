#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1-Command Authoring, Rebuilding & OTA Publishing Helper for Razavi CMOS Knowledge Brain (2026.11.19.1).

Pure Python 3 standard library. Zero external pip packages, zero bytecode clutter.

Usage:
  python -B tools/manage_kb.py status
  python -B tools/manage_kb.py new-card <domain> <node-id> "<title_vi>" "<title_en>" --chapter <N>
  python -B tools/manage_kb.py new-checklist <checklist-id> "<title_vi>" "<title_en>"
  python -B tools/manage_kb.py add-edge <from_id> <to_id> <rel> "<when>" "<cost>" "<ref>"
  python -B tools/manage_kb.py add-term "<en>" "<vi>" --chapter <N> [--context "..."]
  python -B tools/manage_kb.py add-repo <owner/repo> --commit <40hex> --license <spdx> --category <cat> --summary "<vi>" --nodes <id1,id2>
  python -B tools/manage_kb.py rebuild [--export-bundle PATH]
  python -B tools/manage_kb.py publish [-m "message"] [--no-push]
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
    "sampled-and-clocked",
    "nonideal-and-physical",
    "power-management-ic",
    "ams-filters-and-system",
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
        "domains": len(router.get("domains", [])),
        "nodes": len(router.get("nodes", [])),
        "razavi_core_nodes": stats.get("razavi_core_node_count"),
        "pmic_nodes": stats.get("pmic_node_count"),
        "ams_nodes": stats.get("ams_node_count"),
        "eda_domain_nodes": stats.get("eda_domain_node_count"),
        "razavi_nodes": stats.get("razavi_node_count"),
        "skill_nodes": stats.get("skill_node_count"),
        "chapters_covered": len(router.get("chapters", [])),
        "edges": manifest.get("edge_count"),
        "checklists": len(router.get("checklists", [])),
        "diagrams": len(router.get("diagrams", [])),
        "glossary_terms": manifest.get("glossary_count"),
        "book_sections": stats.get("book_section_count"),
        "book_equations": stats.get("book_equation_count"),
        "book_figures": stats.get("book_figure_count"),
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
    if kind == "skill" or args.domain in ("power-management-ic", "ams-filters-and-system"):
        frontmatter["github_refs"] = [
            {
                "repo": "owner/repo",
                "url": "https://github.com/owner/repo",
                "use": "Mô tả luồng kiểm chứng / kiến trúc mở tham chiếu từ kho mã nguồn.",
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


def cmd_new_checklist(args):
    cl_dir = os.path.join(KB_DIR, "checklists")
    os.makedirs(cl_dir, exist_ok=True)
    cid = args.checklist_id[:-5] if args.checklist_id.endswith(".json") else args.checklist_id
    dest = os.path.join(cl_dir, f"{cid}.json")
    if os.path.exists(dest):
        raise SystemExit(f"Checklist already exists: {dest}")
    prefix = "".join(part[0] for part in cid.split("-") if part).upper()[:4] or "CHK"
    payload = {
        "checklist_id": cid,
        "title_vi": args.title_vi,
        "applies_to": [],
        "process_agnostic": True,
        "checks": [
            {
                "id": f"CHK-{prefix}-01",
                "name": "Core structural invariant",
                "severity": "error",
                "method": "structural",
                "invariant": "Define exact process-agnostic branch/headroom/loop invariant here",
                "why_vi": "Giải thích cơ chế vật lý và hậu quả nếu vi phạm điều kiện bất biến.",
                "cadence_check": "Quy trình kiểm chứng cụ thể trên Cadence Spectre 15.1 (`dc`, `ac`, `stb`, `pss`/`pstb`, `tran`).",
                "related_nodes": [],
            },
            {
                "id": f"CHK-{prefix}-02",
                "name": "Operating-point saturation & headroom margin",
                "severity": "error",
                "method": "op-audit",
                "invariant": "Every active transistor operates in saturation (region == 2) with V_DS - V_DSAT >= 50 mV across PVT",
                "why_vi": "Transistor rơi vào vùng triode hoặc cắt dòng ở góc PVT biên làm sụp độ lợi vòng và méo tín hiệu.",
                "cadence_check": "Chạy `dcOp` qua mọi góc PVT và kiểm toán bằng `psf_audit.py op-audit`.",
                "related_nodes": [],
            },
            {
                "id": f"CHK-{prefix}-03",
                "name": "Stability & mismatch Monte Carlo verification",
                "severity": "warn",
                "method": "montecarlo",
                "invariant": "Closed-loop PM >= 60 deg, GM >= 10 dB, and 3-sigma mismatch yield meets spec",
                "why_vi": "Đảm bảo ổn định pha không bị vọt lố và chịu được sai lệch Pelgrom trên silicon.",
                "cadence_check": "Chạy `stb`/`pstb` đa góc và Monte Carlo `mismatch` (200 runs).",
                "related_nodes": [],
            },
        ],
    }
    with open(dest, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(f"Created checklist template: {dest}")
    return 0


def cmd_add_term(args):
    glossary_path = os.path.join(KB_DIR, "glossary", "terms-vi-en.json")
    with open(glossary_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    terms = data.get("terms", [])
    en_low = args.en.strip().lower()
    for t in terms:
        if t.get("en", "").strip().lower() == en_low:
            raise SystemExit(f"Term already exists as {t.get('id')}: {t.get('en')} -> {t.get('vi')}")
    max_num = max(int(t["id"][1:]) for t in terms if t.get("id", "").startswith("T"))
    new_id = f"T{max_num + 1:04d}"
    entry = {
        "id": new_id,
        "en": args.en.strip(),
        "vi": args.vi.strip(),
        "chapters": [args.chapter],
        "context": args.context.strip(),
        "curated_extension": True,
    }
    terms.append(entry)
    data["term_count"] = len(terms)
    with open(glossary_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(f"Added CLB glossary term {new_id}: {entry['en']} -> {entry['vi']}")
    return 0


def cmd_add_repo(args):
    cat_path = os.path.join(KB_DIR, "github-skills", "catalog.json")
    with open(cat_path, "r", encoding="utf-8") as f:
        cat = json.load(f)
    repos = cat.get("repositories", [])
    slug = args.repo.strip()
    if "/" not in slug or len(args.commit.strip()) != 40:
        raise SystemExit("Require <owner/repo> and exact 40-char commit SHA")
    for r in repos:
        if r.get("repo", "").lower() == slug.lower():
            raise SystemExit(f"Repository already in catalog.json: {slug}")
    rid = slug.replace("/", "--")
    linked = [x.strip() for x in args.nodes.split(",") if x.strip()]
    repos.append({
        "id": rid,
        "repo": slug,
        "url": f"https://github.com/{slug}",
        "pinned_commit_or_branch": args.commit.strip(),
        "license": args.license.strip(),
        "stars": args.stars,
        "category": args.category.strip(),
        "quality_tier": args.tier,
        "ic617_compatibility": args.ic617.strip(),
        "summary_vi": args.summary.strip(),
        "key_techniques": [x.strip() for x in args.techniques.split(",") if x.strip()] or ["analog-ic-design"],
        "linked_nodes": linked,
    })
    cat["repo_count"] = len(repos)
    with open(cat_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(cat, ensure_ascii=False, indent=2) + "\n")
    print(f"Added vetted GitHub repository: {slug} ({args.commit[:10]})")
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
        "release": router.get("release", "2026.11.19.1"),
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
    r1 = subprocess.call(
        [sys.executable, "-B", os.path.join(ROOT, "tools", "build_index.py"), "--merge-edges"],
        cwd=ROOT,
        env=env,
    )
    if r1 != 0:
        raise SystemExit(r1)
    if getattr(args, "export_bundle", None):
        export_offline_bundle(args.export_bundle)
    r2 = subprocess.call(
        [sys.executable, "-B", os.path.join(ROOT, "validators", "validate_brain.py")],
        cwd=ROOT,
        env=env,
    )
    if r2 != 0:
        raise SystemExit(r2)
    analogctl_fp = os.path.join(ROOT, "runtime", "tools", "analogctl.py")
    if os.path.isfile(analogctl_fp):
        r3 = subprocess.call([sys.executable, "-B", analogctl_fp, "verify"], cwd=ROOT, env=env)
        if r3 != 0:
            raise SystemExit(r3)
    print("Rebuild + full 10-domain/coordinate/equation/runtime/SVG/checklist/graph validation PASSED!")
    return 0


def cmd_publish(args):
    cmd_rebuild(args)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    check_refs_fp = os.path.join(ROOT, "runtime", "tools", "check_references.py")
    if os.path.isfile(check_refs_fp):
        rc = subprocess.call([sys.executable, "-B", check_refs_fp], cwd=ROOT, env=env)
        if rc != 0:
            raise SystemExit(rc)

    subprocess.check_call(["git", "add", "-A"], cwd=ROOT)
    st = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT).decode("utf-8", "replace").strip()
    if not st:
        print("Working tree already clean and up to date; nothing to commit.")
        return 0
    msg = args.message or "kb/runtime(2026.11.19.1): rebuild & publish verified OTA snapshot"
    subprocess.check_call(["git", "commit", "-m", msg], cwd=ROOT)
    if not args.no_push:
        subprocess.check_call(["git", "push", "origin", "main"], cwd=ROOT)
        print("Published verified SSOT snapshot to origin/main (RHEL 6.5 auto-syncs within 60s TTL).")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Manage Razavi CMOS Knowledge Brain (v4.0 · SSOT + OTA)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Show knowledge graph statistics")

    p_new = sub.add_parser("new-card", help="Scaffold a new 6-block Razavi, PMIC, AMS, or Skill card")
    p_new.add_argument("domain", choices=VALID_DOMAINS)
    p_new.add_argument("node_id")
    p_new.add_argument("title_vi")
    p_new.add_argument("title_en")
    p_new.add_argument("--chapter", type=int, required=True)
    p_new.add_argument("--section", default="1.1")
    p_new.add_argument("--diagram", default="upgrade-evolution-map.svg")

    p_cl = sub.add_parser("new-checklist", help="Scaffold a new process-agnostic structural checklist")
    p_cl.add_argument("checklist_id")
    p_cl.add_argument("title_vi")
    p_cl.add_argument("title_en")
    p_cl.add_argument("--chapter", type=int, default=12)

    p_edge = sub.add_parser("add-edge", help="Add a directed graph edge")
    p_edge.add_argument("from_id")
    p_edge.add_argument("to_id")
    p_edge.add_argument("rel", choices=VALID_RELS)
    p_edge.add_argument("when")
    p_edge.add_argument("cost")
    p_edge.add_argument("ref")

    p_term = sub.add_parser("add-term", help="Append a standardized bilingual term to terms-vi-en.json")
    p_term.add_argument("en")
    p_term.add_argument("vi")
    p_term.add_argument("--chapter", type=int, required=True)
    p_term.add_argument("--context", default="Extended CMOS/PMIC/AMS terminology")

    p_repo = sub.add_parser("add-repo", help="Register a SHA-pinned GitHub repository in catalog.json")
    p_repo.add_argument("repo")
    p_repo.add_argument("--commit", required=True)
    p_repo.add_argument("--license", required=True)
    p_repo.add_argument("--category", default="agentic-eda-and-automation")
    p_repo.add_argument("--tier", default="tier-1-core")
    p_repo.add_argument("--stars", type=int, default=10)
    p_repo.add_argument("--ic617", default="Compatible as architecture/testbench reference on IC617 + Spectre 15.1")
    p_repo.add_argument("--summary", required=True)
    p_repo.add_argument("--techniques", default="")
    p_repo.add_argument("--nodes", required=True, help="Comma-separated linked node IDs")

    p_reb = sub.add_parser("rebuild", help="Rebuild router-index.json + nodes-bundle + manifests and run full validator")
    p_reb.add_argument("--export-bundle", help="Optional extra path to export deterministic nodes-bundle.json.gz")

    p_pub = sub.add_parser("publish", help="Validate, rebuild, git commit, and push live OTA snapshot to origin/main")
    p_pub.add_argument("-m", "--message", default="", help="Git commit message")
    p_pub.add_argument("--no-push", action="store_true", help="Commit locally without running git push")

    args = parser.parse_args()
    if args.cmd == "status":
        return cmd_status()
    if args.cmd == "new-card":
        return cmd_new_card(args)
    if args.cmd == "new-checklist":
        return cmd_new_checklist(args)
    if args.cmd == "add-edge":
        return cmd_add_edge(args)
    if args.cmd == "add-term":
        return cmd_add_term(args)
    if args.cmd == "add-repo":
        return cmd_add_repo(args)
    if args.cmd == "rebuild":
        return cmd_rebuild(args)
    if args.cmd == "publish":
        return cmd_publish(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
