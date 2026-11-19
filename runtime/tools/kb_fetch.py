#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Hybrid Online GitHub + Offline Razavi/PMIC/AMS/EDA Card Fetcher & OTA Client (v4.0).

100% compatible with Python 2.6.6 (RHEL 6.5) and Python 3.x standard library.
- Strict --offline / SKILL_ANALOG_OFFLINE=1 precedence enforced FIRST:
  * Passing --sync (or --refresh) together with --offline or SKILL_ANALOG_OFFLINE=1
    immediately exits with code 2 and zero network activity.
- Transparently invokes ota_sync.maybe_auto_sync(ttl_sec=60, offline=offline_only)
  when running outside the live Windows Git SSOT checkout.
- Dual-layout path resolution:
  * Layout A (Windows Git SSOT: runtime/tools/kb_fetch.py -> ../../kb/): reads live
    cards, checklists, edges, and 72 SVG diagrams directly (< 15 ms warm in-process
    / direct SSOT lookup; cold CLI subprocess ~150-220 ms on RHEL 6.5 Python 2.6.6
    including interpreter startup; 0 ms network).
  * Layout B (RHEL 6.5 SKILL-ANALOG: tools/kb_fetch.py -> ../kb/ + ~/.cache/razavi-cmos-brain/synced):
    serves synced cache / HTTPS live cards with offline fallback from nodes-bundle.json.gz
    (< 15 ms warm in-process once loaded; ~150-220 ms cold CLI subprocess on RHEL 6.5
    Python 2.6.6 including interpreter startup and gzip bundle decompression) and
    local SVG resolution across all 72 diagrams.
"""
from __future__ import print_function

import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
import zlib
from optparse import OptionParser

sys.dont_write_bytecode = True

TOOLS_DIR = os.path.dirname(os.path.realpath(__file__))
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

import ota_sync  # noqa: E402

PY2 = sys.version_info[0] < 3
if PY2:
    TEXT_TYPE = unicode  # noqa: F821
else:
    TEXT_TYPE = str

LIBRARY_ROOT = os.path.dirname(TOOLS_DIR)
KB_DIR = os.path.join(LIBRARY_ROOT, "kb")
SSOT_REPO_ROOT = ota_sync.get_ssot_repo_root(LIBRARY_ROOT)
SSOT_KB_DIR = os.path.join(SSOT_REPO_ROOT, "kb") if SSOT_REPO_ROOT else None


def to_text(value):
    if value is None:
        return u""
    if isinstance(value, TEXT_TYPE):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return TEXT_TYPE(value)


def write_utf8(text):
    txt = to_text(text)
    if not txt.endswith(u"\n"):
        txt = txt + u"\n"
    raw = txt.encode("utf-8")
    if PY2:
        sys.stdout.write(raw)
    elif hasattr(sys.stdout, "buffer"):
        sys.stdout.buffer.write(raw)
    else:
        sys.stdout.write(txt)


def load_json_file(path):
    stream = open(path, "rb")
    try:
        return json.loads(stream.read().decode("utf-8-sig"))
    finally:
        stream.close()


def sha256_bytes(raw_bytes):
    h = hashlib.sha256()
    h.update(raw_bytes)
    return h.hexdigest()


def strip_frontmatter(md_text):
    txt = to_text(md_text)
    lines = txt.splitlines()
    if lines and lines[0].strip() == u"---":
        for idx in range(1, len(lines)):
            if lines[idx].strip() == u"---":
                return u"\n".join(lines[idx + 1 :]).strip()
    return txt.strip()


def load_config():
    return ota_sync.load_config(LIBRARY_ROOT)


def get_cache_dir(cfg):
    return ota_sync.get_cache_dir(cfg=cfg, library_root=LIBRARY_ROOT)


def sync_from_github(base_url_override=None, offline_only=False, update_library=True):
    return ota_sync.sync_now(
        library_root=LIBRARY_ROOT,
        base_url_override=base_url_override,
        update_library=bool(update_library),
        offline=offline_only,
    )


def clear_cache():
    cfg = load_config()
    cache_dir = get_cache_dir(cfg)
    removed = False
    if os.path.isdir(cache_dir):
        shutil.rmtree(cache_dir)
        removed = True
    return {"ok": True, "cleared": removed, "cache_dir": cache_dir}


def resolve_router_path(cfg):
    if SSOT_KB_DIR and os.path.isfile(os.path.join(SSOT_KB_DIR, "router-index.json")):
        return os.path.join(SSOT_KB_DIR, "router-index.json")
    synced_router = os.path.join(get_cache_dir(cfg), "synced", "router-index.json")
    if os.path.isfile(synced_router):
        return synced_router
    return os.path.join(KB_DIR, "router-index.json")


def load_active_router(cfg):
    return load_json_file(resolve_router_path(cfg))


def resolve_bundle_path(cfg):
    candidates = [
        os.path.join(get_cache_dir(cfg), "synced", "nodes-bundle.json.gz") if not SSOT_KB_DIR else "",
        os.path.join(KB_DIR, "nodes-bundle.json.gz"),
        os.path.join(SSOT_KB_DIR, "nodes-bundle.json.gz") if SSOT_KB_DIR else "",
    ]
    for cand in candidates:
        if cand and os.path.isfile(cand):
            return cand
    return os.path.join(KB_DIR, "nodes-bundle.json.gz")


def load_bundle(cfg):
    bundle_path = resolve_bundle_path(cfg)
    if not os.path.isfile(bundle_path):
        raise IOError("Missing offline snapshot bundle: " + bundle_path)
    stream = open(bundle_path, "rb")
    try:
        compressed = stream.read()
    finally:
        stream.close()
    raw_json = zlib.decompress(compressed, 16 + zlib.MAX_WBITS).decode("utf-8")
    return json.loads(raw_json), bundle_path


def resolve_edges_path(cfg):
    if SSOT_KB_DIR and os.path.isfile(os.path.join(SSOT_KB_DIR, "graph", "edges.jsonl")):
        return os.path.join(SSOT_KB_DIR, "graph", "edges.jsonl")
    synced_edges = os.path.join(get_cache_dir(cfg), "synced", "edges.jsonl")
    if os.path.isfile(synced_edges):
        return synced_edges
    return os.path.join(KB_DIR, "edges.jsonl")


def load_edges_for_node(cfg, node_id):
    edges_path = resolve_edges_path(cfg)
    incoming = []
    outgoing = []
    if not os.path.isfile(edges_path):
        return incoming, outgoing
    stream = open(edges_path, "rb")
    try:
        for raw_line in stream:
            line = raw_line.decode("utf-8-sig").strip()
            if not line:
                continue
            edge = json.loads(line)
            if edge.get("to") == node_id:
                incoming.append(edge)
            elif edge.get("from") == node_id:
                outgoing.append(edge)
    finally:
        stream.close()
    return incoming, outgoing


def load_checklists_by_ids(cfg, checklist_ids):
    synced_cl_dir = os.path.join(get_cache_dir(cfg), "synced", "checklists")
    cl_dir = os.path.join(KB_DIR, "checklists")
    ssot_cl_dir = os.path.join(SSOT_KB_DIR, "checklists") if SSOT_KB_DIR else None
    loaded = []
    for cid in checklist_ids:
        candidates = []
        if ssot_cl_dir:
            candidates.append(os.path.join(ssot_cl_dir, cid + ".json"))
        else:
            candidates.append(os.path.join(synced_cl_dir, cid + ".json"))
        candidates.append(os.path.join(cl_dir, cid + ".json"))
        if ssot_cl_dir:
            candidates.append(os.path.join(synced_cl_dir, cid + ".json"))
        for fp in candidates:
            if os.path.isfile(fp):
                loaded.append(load_json_file(fp))
                break
    return loaded


def resolve_local_diagram_path(cfg, diag_filename):
    if not diag_filename:
        return None
    base_fn = os.path.basename(to_text(diag_filename))
    candidates = []
    if SSOT_KB_DIR:
        candidates.append(os.path.join(SSOT_KB_DIR, "diagrams", base_fn))
    candidates.append(os.path.join(get_cache_dir(cfg), "synced", "diagrams", base_fn))
    candidates.append(os.path.join(KB_DIR, "diagrams", base_fn))
    for cand in candidates:
        if cand and os.path.isfile(cand):
            return cand
    return None


class AmbiguousNodeError(ValueError):
    def __init__(self, message, candidates=None):
        ValueError.__init__(self, message)
        self.candidates = list(candidates or [])


def resolve_node_entry(router, query_id):
    target = to_text(query_id).strip()
    if not target:
        return None
    nodes = router.get("nodes", [])
    for n in nodes:
        if n.get("id") == target:
            return n
    lower = target.lower()
    for n in nodes:
        if to_text(n.get("id", "")).lower() == lower:
            return n
    matches = []
    for n in nodes:
        if lower in to_text(n.get("id", "")).lower():
            matches.append(n)
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        cand_ids = sorted([to_text(m.get("id", "")) for m in matches])
        raise AmbiguousNodeError(
            "Ambiguous Razavi Knowledge Brain node %r matches %d candidates: %s"
            % (target, len(cand_ids), ", ".join(cand_ids)),
            candidates=cand_ids,
        )
    return None


def fetch_card(node_query, base_url_override=None, offline_only=False, refresh=False, update_library=True):
    eff_offline = bool(offline_only or ota_sync.is_offline_env())
    if refresh and eff_offline:
        raise ota_sync.OtaConflictError("--refresh cannot be used when offline mode is active.")

    # Resolve locally FIRST so unknown/ambiguous queries fail immediately with zero network sync
    cfg = load_config()
    router = load_active_router(cfg)
    node_meta = resolve_node_entry(router, node_query)
    if not node_meta:
        raise KeyError("Unknown Razavi Knowledge Brain node: " + to_text(node_query))

    # Transparent background TTL auto-sync ONLY after resolving a valid node (0 ms on SSOT / offline / 60s TTL)
    if not eff_offline:
        sync_res = ota_sync.maybe_auto_sync(
            ttl_sec=60,
            offline=eff_offline,
            library_root=LIBRARY_ROOT,
            base_url_override=base_url_override,
            update_library=bool(update_library),
        )
        if isinstance(sync_res, dict) and sync_res.get("action") in ("synced", "updated"):
            cfg = load_config()
            router = load_active_router(cfg)
            node_meta = resolve_node_entry(router, node_meta.get("id") or node_query)
            if not node_meta:
                raise KeyError("Unknown Razavi Knowledge Brain node: " + to_text(node_query))

    nid = node_meta["id"]
    rel_path = to_text(node_meta.get("raw_rel_path") or node_meta.get("path") or "").lstrip("/")
    expected_sha = to_text(node_meta.get("sha256", "")).strip().lower()
    verify_sha = bool(cfg.get("verify_sha256", True))
    timeout_sec = float(cfg.get("http_timeout_sec", 8))

    markdown_text = None
    source_used = None
    online_note = None
    diagram_info = None

    # Fast Path 1: Windows Git SSOT live card file (< 2 ms warm in-process, zero network) when not forcing --offline or --base-url
    if SSOT_REPO_ROOT and not eff_offline and not base_url_override and rel_path:
        ssot_md_path = os.path.join(*([SSOT_REPO_ROOT] + rel_path.split("/")))
        if os.path.isfile(ssot_md_path):
            raw_md = ota_sync.read_bytes(ssot_md_path)
            markdown_text = strip_frontmatter(raw_md.decode("utf-8-sig"))
            source_used = "ssot-local (" + ssot_md_path + ")"

    # Path 2: Online read-through cache / HTTPS fetch (ONLY when not offline_only)
    if markdown_text is None and not eff_offline:
        cache_dir = get_cache_dir(cfg)
        cards_cache_dir = os.path.join(cache_dir, "cards")
        cache_file = os.path.join(cards_cache_dir, nid + ".md")
        verified_cached_bytes = None
        if os.path.isfile(cache_file):
            try:
                cand_cached = ota_sync.read_bytes(cache_file)
                if verify_sha:
                    if re.match(r"^[0-9a-f]{64}$", expected_sha) and sha256_bytes(cand_cached) == expected_sha:
                        verified_cached_bytes = cand_cached
                else:
                    verified_cached_bytes = cand_cached
            except OSError:
                verified_cached_bytes = None

        if not refresh and not base_url_override and verified_cached_bytes is not None:
            markdown_text = strip_frontmatter(verified_cached_bytes.decode("utf-8-sig"))
            source_used = "read-through-cache (" + cache_file + ")"

        if markdown_text is None:
            try:
                base_urls, _, _ = ota_sync.resolve_remote_bases(cfg, base_url_override=base_url_override)
                live_bytes, used_url = ota_sync.fetch_from_bases(rel_path, base_urls, timeout_sec, cfg)
                actual_sha = sha256_bytes(live_bytes)
                if verify_sha:
                    if not re.match(r"^[0-9a-f]{64}$", expected_sha):
                        raise ValueError("Missing or invalid expected SHA-256 in router-index for " + nid)
                    if actual_sha != expected_sha:
                        raise ValueError(
                            "SHA-256 mismatch for live card %s (%s != %s); run `kb_fetch.py --sync` if remote updated"
                            % (nid, actual_sha[:12], expected_sha[:12])
                        )
                markdown_text = strip_frontmatter(live_bytes.decode("utf-8-sig"))
                source_used = "https-live (" + used_url + ")"
                try:
                    ota_sync.write_atomic_bytes(cache_file, live_bytes)
                except OSError:
                    pass
            except Exception as exc:
                if verified_cached_bytes is not None:
                    markdown_text = strip_frontmatter(verified_cached_bytes.decode("utf-8-sig"))
                    source_used = "read-through-cache (" + cache_file + ")"
                    online_note = "Rejected/unavailable live GitHub fetch (%s); served from verified read-through cache." % str(exc)
                else:
                    online_note = "HTTPS GitHub fetch rejected/unavailable (%s); served from local nodes-bundle.json.gz." % str(exc)

    # Path 3: Offline bundle fallback (< 15 ms warm in-process once loaded / ~150-220 ms cold CLI with gzip decompression, guaranteed zero network)
    if markdown_text is None:
        bundle, bundle_path = load_bundle(cfg)
        nodes_dict = bundle.get("nodes", {})
        if nid not in nodes_dict:
            if SSOT_REPO_ROOT and rel_path:
                ssot_md_path = os.path.join(*([SSOT_REPO_ROOT] + rel_path.split("/")))
                if os.path.isfile(ssot_md_path):
                    markdown_text = strip_frontmatter(ota_sync.read_bytes(ssot_md_path).decode("utf-8-sig"))
                    source_used = "ssot-local-offline (" + ssot_md_path + ")"
            if markdown_text is None:
                raise KeyError("Node missing from nodes-bundle.json.gz: " + nid)
        else:
            b_entry = nodes_dict[nid]
            markdown_text = strip_frontmatter(b_entry.get("markdown", ""))
            diagram_info = dict(b_entry.get("diagram_info") or {}) if b_entry.get("diagram_info") else None
            source_used = "local-bundle (" + bundle_path + ")"

    diag_name = os.path.basename(to_text(node_meta.get("diagram", "")))
    if diagram_info is None:
        for d in router.get("diagrams", []):
            fn = d.get("file") or d.get("filename") or ""
            if fn == diag_name:
                diagram_info = dict(d)
                break
        if diagram_info is None and diag_name:
            diagram_info = {"file": diag_name, "path": "kb/diagrams/" + diag_name}
    if diagram_info is not None and diag_name:
        local_svg = resolve_local_diagram_path(cfg, diag_name)
        if local_svg:
            diagram_info["local_path"] = local_svg

    incoming, outgoing = load_edges_for_node(cfg, nid)
    checklists = load_checklists_by_ids(cfg, node_meta.get("checklists", []))

    web_base = to_text(cfg.get("web_url") or cfg.get("base_url") or "").rstrip("/")
    return {
        "ok": True,
        "node_id": nid,
        "source": source_used,
        "web_url": ("%s/#node/%s" % (web_base, nid)) if web_base else "",
        "repo_url": cfg.get("repo_url", ""),
        "note": online_note,
        "metadata": node_meta,
        "diagram_info": diagram_info,
        "incoming_edges": incoming,
        "outgoing_edges": outgoing,
        "checklists": checklists,
        "markdown": markdown_text,
    }


def format_markdown_report(result, include_checklists=True):
    meta = result["metadata"]
    lines = []
    lines.append(
        u"<!-- RAZAVI KNOWLEDGE BRAIN CARD: %s | source: %s -->"
        % (result["node_id"], to_text(result["source"]))
    )
    if result.get("note"):
        lines.append(u"<!-- NOTE: %s -->" % to_text(result["note"]))
    lines.append(u"# [%s] %s" % (to_text(meta.get("id")), to_text(meta.get("title_vi"))))
    lines.append(u"**English Title:** %s  " % to_text(meta.get("title_en")))
    lines.append(
        u"**Domain:** `%s` | **Kind:** `%s` | **PDK-Agnostic:** `%s`"
        % (
            to_text(meta.get("domain")),
            to_text(meta.get("kind")),
            to_text(meta.get("process_agnostic")),
        )
    )
    if result.get("web_url"):
        lines.append(u"**GitHub Knowledge Map:** %s" % to_text(result["web_url"]))
    diag = result.get("diagram_info") or {}
    if diag:
        svg_line = u"**Vector Schematic:** `%s`" % to_text(
            diag.get("path") or diag.get("file") or meta.get("diagram")
        )
        if diag.get("local_path"):
            svg_line = svg_line + (u" (local: `%s`)" % to_text(diag.get("local_path")))
        lines.append(svg_line)
    gh_refs = meta.get("github_refs") or []
    if gh_refs:
        lines.append(u"**Vetted GitHub Skill References:**")
        for g in gh_refs:
            lines.append(
                u"- `%s` (%s) — %s"
                % (to_text(g.get("repo", "")), to_text(g.get("url", "")), to_text(g.get("use", "")))
            )
    lines.append(u"")
    lines.append(to_text(result["markdown"]).strip())
    lines.append(u"")
    lines.append(u"---")
    lines.append(u"## Đồ thị Liên kết & Đường Nâng cấp Trực tiếp (`edges.jsonl`)")
    if result["incoming_edges"]:
        lines.append(u"### Liên kết đi vào thẻ này:")
        for e in result["incoming_edges"]:
            lines.append(
                u"- `%s` --[**%s**]--> `%s` | Khi: %s | Đánh đổi: %s (%s)"
                % (
                    to_text(e.get("from")),
                    to_text(e.get("rel")),
                    to_text(e.get("to")),
                    to_text(e.get("when", "-")),
                    to_text(e.get("cost", "-")),
                    to_text(e.get("ref", "")),
                )
            )
    if result["outgoing_edges"]:
        lines.append(u"### Hướng nâng cấp / Khắc phục / Đánh đổi từ thẻ này:")
        for e in result["outgoing_edges"]:
            lines.append(
                u"- `%s` --[**%s**]--> `%s` | Khi: %s | Đánh đổi: %s (%s)"
                % (
                    to_text(e.get("from")),
                    to_text(e.get("rel")),
                    to_text(e.get("to")),
                    to_text(e.get("when", "-")),
                    to_text(e.get("cost", "-")),
                    to_text(e.get("ref", "")),
                )
            )

    if include_checklists and result["checklists"]:
        lines.append(u"")
        lines.append(u"---")
        lines.append(u"## Bảng kiểm Bất biến Cấu trúc Độc lập Tiến trình (`checklists`)")
        for cl in result["checklists"]:
            lines.append(
                u"### Checklist `%s` — %s"
                % (to_text(cl.get("checklist_id")), to_text(cl.get("title_vi")))
            )
            for chk in cl.get("checks", []):
                lines.append(
                    u"- **[%s | %s] `%s` (%s):** `%s` — %s"
                    % (
                        to_text(chk.get("severity", "error")).upper(),
                        to_text(chk.get("method", "structural")),
                        to_text(chk.get("id", "")),
                        to_text(chk.get("name", "")),
                        to_text(chk.get("invariant", "")),
                        to_text(chk.get("why_vi", "")),
                    )
                )
    return u"\n".join(lines)


def run_self_test():
    saved_env = os.environ.get("SKILL_ANALOG_OFFLINE")
    saved_outer_cache = os.environ.get("RAZAVI_BRAIN_CACHE_DIR")
    outer_tmp_cache = tempfile.mkdtemp(prefix="kb_fetch_selftest_cache_")
    os.environ["RAZAVI_BRAIN_CACHE_DIR"] = outer_tmp_cache
    orig_outer_auto = ota_sync.maybe_auto_sync
    orig_outer_fetch = ota_sync.fetch_from_bases

    def _hermetic_no_net(*_args, **_kwargs):
        raise IOError("hermetic_selftest_no_network")

    try:
        # 1. --sync + --offline -> exit code 2
        rc1 = main(["--sync", "--offline", "--quiet-errors"])
        if rc1 != 2:
            raise AssertionError("Expected exit 2 for --sync --offline, got %s" % rc1)

        # 2. SKILL_ANALOG_OFFLINE=1 + --sync -> exit code 2
        os.environ["SKILL_ANALOG_OFFLINE"] = "1"
        rc2 = main(["--sync", "--quiet-errors"])
        if rc2 != 2:
            raise AssertionError("Expected exit 2 for SKILL_ANALOG_OFFLINE=1 --sync, got %s" % rc2)

        # 3. Offline bundle card fetch with local SVG resolution
        card = fetch_card("topo-folded-cascode-ota", offline_only=True)
        if not card.get("ok") or "local-bundle" not in to_text(card.get("source", "")):
            raise AssertionError("Offline bundle fetch failed: %r" % card.get("source"))
        d_info = card.get("diagram_info") or {}
        if not d_info.get("local_path") or not os.path.isfile(d_info["local_path"]):
            raise AssertionError("Local SVG path missing in offline card fetch: %r" % d_info)

        if saved_env is None:
            del os.environ["SKILL_ANALOG_OFFLINE"]
        else:
            os.environ["SKILL_ANALOG_OFFLINE"] = saved_env

        # 4. Default dual-layout fetch speed (hermetic: stub network/OTA so library/ is never mutated)
        ota_sync.maybe_auto_sync = lambda **_kw: {"ok": True, "action": "noop_test"}
        ota_sync.fetch_from_bases = _hermetic_no_net
        try:
            t0 = time.time()
            card2 = fetch_card(
                "topo-synchronous-buck-converter-architecture",
                offline_only=False,
                update_library=False,
            )
            dt_ms = round((time.time() - t0) * 1000.0, 2)
        finally:
            ota_sync.maybe_auto_sync = orig_outer_auto
            ota_sync.fetch_from_bases = orig_outer_fetch
        if not card2.get("ok") or len(card2.get("markdown", "")) < 500:
            raise AssertionError("Default fetch returned invalid card")

        # 5. `--no-library-update` forwards update_library=False to ota_sync.sync_now
        sync_spy = {}
        orig_sync_now = ota_sync.sync_now

        def _spy_sync_now(**kwargs):
            sync_spy.update(kwargs)
            return {"ok": True, "library_updated": False}

        ota_sync.sync_now = _spy_sync_now
        orig_write_utf8 = globals()["write_utf8"]
        globals()["write_utf8"] = lambda _txt: None
        try:
            rc_nlu = main(["--sync", "--no-library-update", "--quiet-errors"])
        finally:
            globals()["write_utf8"] = orig_write_utf8
            ota_sync.sync_now = orig_sync_now
        if rc_nlu != 0 or sync_spy.get("update_library") is not False:
            raise AssertionError("--no-library-update did not pass update_library=False: %r" % sync_spy)

        # 6. Tampered live card bytes under verify_sha256=True are rejected (never cached or returned)
        tmp_tamp = tempfile.mkdtemp(prefix="kb_fetch_tamper_")
        saved_cache_env = os.environ.get("RAZAVI_BRAIN_CACHE_DIR")
        try:
            iso_cache = os.path.join(tmp_tamp, "isolated_cache")
            fake_remote = os.path.join(tmp_tamp, "tampered_remote")
            os.environ["RAZAVI_BRAIN_CACHE_DIR"] = iso_cache
            router_now = load_active_router(load_config())
            target_meta = resolve_node_entry(router_now, "topo-folded-cascode-ota")
            rel_md = to_text(target_meta.get("raw_rel_path") or target_meta.get("path")).lstrip("/")
            tampered_md_fp = os.path.join(*([fake_remote] + rel_md.split("/")))
            ota_sync.mkdir_p(os.path.dirname(tampered_md_fp))
            ota_sync.write_atomic_bytes(tampered_md_fp, b"---\nid: topo-folded-cascode-ota\n---\nTAMPERED_EVIL_MARKER_XYZ\n")

            orig_auto = ota_sync.maybe_auto_sync
            ota_sync.maybe_auto_sync = lambda **_kw: {"ok": True, "action": "noop_test"}
            try:
                safe_card = fetch_card("topo-folded-cascode-ota", base_url_override=fake_remote, offline_only=False, refresh=True)
            finally:
                ota_sync.maybe_auto_sync = orig_auto

            if "TAMPERED_EVIL_MARKER_XYZ" in to_text(safe_card.get("markdown", "")):
                raise AssertionError("kb_fetch returned tampered card bytes despite SHA-256 mismatch!")
            if "local-bundle" not in to_text(safe_card.get("source", "")):
                raise AssertionError("Expected fallback to verified local-bundle on SHA mismatch, got %r" % safe_card.get("source"))
            cached_fp = os.path.join(iso_cache, "cards", "topo-folded-cascode-ota.md")
            if os.path.exists(cached_fp):
                raise AssertionError("Tampered card bytes were written to read-through cache!")
        finally:
            if saved_cache_env is None:
                os.environ.pop("RAZAVI_BRAIN_CACHE_DIR", None)
            else:
                os.environ["RAZAVI_BRAIN_CACHE_DIR"] = saved_cache_env
            shutil.rmtree(tmp_tamp, ignore_errors=True)

        # 7. Finding #12 + #16: Gibberish & ambiguous IDs fail closed with ZERO calls to maybe_auto_sync
        sync_spy_calls = []
        captured_out = []
        orig_auto2 = ota_sync.maybe_auto_sync
        orig_fetch2 = ota_sync.fetch_from_bases
        orig_write = globals()["write_utf8"]
        orig_stderr = sys.stderr

        def _spy_auto2(**kwargs):
            sync_spy_calls.append(kwargs)
            return {"ok": True, "action": "noop_spy"}

        def _cap_write(txt):
            captured_out.append(to_text(txt))

        class _BufStderr(object):
            def __init__(self):
                self.chunks = []

            def write(self, s):
                self.chunks.append(to_text(s))

            def flush(self):
                pass

        ota_sync.maybe_auto_sync = _spy_auto2
        ota_sync.fetch_from_bases = _hermetic_no_net
        try:
            # 7a. Unknown query -> KeyError, 0 maybe_auto_sync calls
            unknown_caught = False
            try:
                fetch_card("xyzzy-nonexistent-card-9999", offline_only=False)
            except KeyError:
                unknown_caught = True
            if not unknown_caught or len(sync_spy_calls) != 0:
                raise AssertionError("Unknown query must fail with KeyError and 0 sync calls: caught=%r calls=%r" % (unknown_caught, sync_spy_calls))

            # 7b. Ambiguous substring 'charge-pump' -> AmbiguousNodeError with 3 candidates, 0 maybe_auto_sync calls
            ambig_exc = None
            try:
                fetch_card("charge-pump", offline_only=False)
            except AmbiguousNodeError as exc:
                ambig_exc = exc
            expected_cp = [
                "topo-charge-pump-type2-pll",
                "topo-pfd-deadzone-and-charge-pump-nonidealities",
                "topo-switched-capacitor-charge-pump-dcdc",
            ]
            if ambig_exc is None or ambig_exc.candidates != expected_cp or len(sync_spy_calls) != 0:
                raise AssertionError("Ambiguous charge-pump failed: exc=%r calls=%r" % (ambig_exc, sync_spy_calls))

            # 7c. CLI --offline --json charge-pump -> rc=1, ok=False, 3 candidates in JSON
            globals()["write_utf8"] = _cap_write
            del captured_out[:]
            rc_cp_json = main(["--offline", "--json", "charge-pump"])
            cp_payload = json.loads(captured_out[0]) if captured_out else {}
            if rc_cp_json != 1 or cp_payload.get("ok") is not False or cp_payload.get("candidates") != expected_cp or len(sync_spy_calls) != 0:
                raise AssertionError("CLI json charge-pump failed: rc=%r pay=%r calls=%r" % (rc_cp_json, cp_payload, sync_spy_calls))

            # 7d. CLI --offline charge-pump (text stderr) -> rc=1, lists all 3 candidates
            err_buf = _BufStderr()
            sys.stderr = err_buf
            rc_cp_txt = main(["--offline", "charge-pump"])
            sys.stderr = orig_stderr
            err_txt = u"".join(err_buf.chunks)
            if rc_cp_txt != 1 or any(cid not in err_txt for cid in expected_cp) or len(sync_spy_calls) != 0:
                raise AssertionError("CLI text charge-pump failed: rc=%r err=%r" % (rc_cp_txt, err_txt))

            # 7e. Valid fetch with offline_only=False invokes maybe_auto_sync AFTER resolving node (hermetic)
            del sync_spy_calls[:]
            ok_card = fetch_card("topo-charge-pump-type2-pll", offline_only=False, update_library=False)
            if not ok_card.get("ok") or len(sync_spy_calls) != 1:
                raise AssertionError("Valid fetch should invoke maybe_auto_sync once after resolution: calls=%r" % sync_spy_calls)
        finally:
            sys.stderr = orig_stderr
            globals()["write_utf8"] = orig_write
            ota_sync.maybe_auto_sync = orig_auto2
            ota_sync.fetch_from_bases = orig_fetch2

        return {
            "ok": True,
            "command": "self-test",
            "release": ota_sync.RELEASE_VERSION,
            "fetch_ms": dt_ms,
            "tests_passed": 11,
        }
    finally:
        ota_sync.maybe_auto_sync = orig_outer_auto
        ota_sync.fetch_from_bases = orig_outer_fetch
        if saved_outer_cache is None:
            os.environ.pop("RAZAVI_BRAIN_CACHE_DIR", None)
        else:
            os.environ["RAZAVI_BRAIN_CACHE_DIR"] = saved_outer_cache
        shutil.rmtree(outer_tmp_cache, ignore_errors=True)
        if saved_env is None:
            if "SKILL_ANALOG_OFFLINE" in os.environ:
                del os.environ["SKILL_ANALOG_OFFLINE"]
        else:
            os.environ["SKILL_ANALOG_OFFLINE"] = saved_env


HELP_TEXT = """Usage:
  python tools/kb_fetch.py <NODE_ID> [options]
  python tools/kb_fetch.py --sync [--no-library-update] [--base-url URL]
  python tools/kb_fetch.py --clear-cache
  python tools/kb_fetch.py --self-test

Options:
  --sync                 Atomically sync 100 KB files into ~/.cache/razavi-cmos-brain & update library/ when writable
  --no-library-update    Sync external user cache (~/.cache/razavi-cmos-brain) only without touching library/
  --clear-cache          Remove external user cache (~/.cache/razavi-cmos-brain)
  --json                 Emit structured JSON instead of formatted Markdown
  --raw                  Emit only the raw 6-block Markdown card without appended edges/checklists
  --no-checklists        Omit expanded checklists from Markdown output
  --offline              Force offline extraction from local kb/nodes-bundle.json.gz (conflicts with --sync)
  --refresh              Bypass read-through card cache and fetch fresh from GitHub
  --base-url URL         Override live GitHub base URL (or local staging path) for this call
  --self-test            Run built-in self-test suite
  -h, --help             Show this help message
"""


def build_parser():
    parser = OptionParser(add_help_option=False)
    parser.add_option("-h", "--help", action="store_true", default=False)
    parser.add_option("--sync", action="store_true", default=False)
    parser.add_option("--no-library-update", dest="no_library_update", action="store_true", default=False)
    parser.add_option("--clear-cache", dest="clear_cache", action="store_true", default=False)
    parser.add_option("--json", dest="as_json", action="store_true", default=False)
    parser.add_option("--raw", dest="raw_only", action="store_true", default=False)
    parser.add_option("--no-checklists", dest="no_checklists", action="store_true", default=False)
    parser.add_option("--offline", dest="offline", action="store_true", default=False)
    parser.add_option("--refresh", dest="refresh", action="store_true", default=False)
    parser.add_option("--base-url", dest="base_url", default=None)
    parser.add_option("--self-test", dest="self_test", action="store_true", default=False)
    parser.add_option("--quiet-errors", dest="quiet_errors", action="store_true", default=False)
    return parser


def main(argv=None):
    raw_args = list(sys.argv[1:] if argv is None else argv)
    if not raw_args or raw_args[0] in ("-h", "--help", "help"):
        print(HELP_TEXT)
        return 0

    parser = build_parser()
    try:
        opts, pos = parser.parse_args(raw_args)
    except SystemExit:
        return 2

    if opts.help:
        print(HELP_TEXT)
        return 0

    if opts.self_test:
        res = run_self_test()
        write_utf8(json.dumps(res, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if res.get("ok") else 1

    do_sync = bool(opts.sync)
    node_id = None
    for tok in pos:
        if tok == "sync":
            do_sync = True
        elif node_id is None:
            node_id = tok

    # CRITICAL FIX: Strict --offline / SKILL_ANALOG_OFFLINE=1 precedence BEFORE any sync or network call!
    eff_offline = bool(opts.offline or ota_sync.is_offline_env())
    if do_sync and eff_offline:
        err_msg = "Conflicting options: --sync cannot run when --offline or SKILL_ANALOG_OFFLINE=1 is active."
        if not opts.quiet_errors:
            write_utf8(json.dumps({"ok": False, "error": err_msg}, indent=2, sort_keys=True))
        return 2
    if opts.refresh and eff_offline:
        err_msg = "Conflicting options: --refresh cannot run when --offline or SKILL_ANALOG_OFFLINE=1 is active."
        if not opts.quiet_errors:
            sys.stderr.write("kb_fetch error: %s\n" % err_msg)
        return 2

    try:
        if opts.clear_cache:
            write_utf8(json.dumps(clear_cache(), ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        if do_sync:
            receipt = sync_from_github(
                base_url_override=opts.base_url,
                offline_only=eff_offline,
                update_library=(not opts.no_library_update),
            )
            write_utf8(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
            return 0 if receipt.get("ok") else 1
        if not node_id:
            if not opts.quiet_errors:
                sys.stderr.write("Error: a <NODE_ID> argument (or --sync) is required.\n")
            return 2

        result = fetch_card(
            node_id,
            base_url_override=opts.base_url,
            offline_only=eff_offline,
            refresh=opts.refresh,
            update_library=(not opts.no_library_update),
        )
        if opts.as_json:
            write_utf8(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        elif opts.raw_only:
            write_utf8(result["markdown"])
        else:
            write_utf8(format_markdown_report(result, include_checklists=(not opts.no_checklists)))
        return 0
    except AmbiguousNodeError as exc:
        if not opts.quiet_errors:
            if opts.as_json:
                write_utf8(
                    json.dumps(
                        {
                            "ok": False,
                            "node_id": node_id,
                            "error": str(exc),
                            "candidates": exc.candidates,
                        },
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=True,
                    )
                )
            else:
                sys.stderr.write("kb_fetch error: %s\n" % str(exc))
        return 1
    except ota_sync.OtaConflictError as exc:
        if not opts.quiet_errors:
            write_utf8(json.dumps({"ok": False, "node_id": node_id, "error": str(exc)}, indent=2, sort_keys=True))
        return 2
    except Exception as exc:
        if not opts.quiet_errors:
            if opts.as_json or do_sync or opts.clear_cache:
                write_utf8(json.dumps({"ok": False, "node_id": node_id, "error": str(exc)}, indent=2, sort_keys=True))
            else:
                sys.stderr.write("kb_fetch error: %s\n" % str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
