#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Razavi CMOS + PMIC + AMS + Closed-Loop Cadence/GitHub Skills Knowledge Brain Router for SKILL-ANALOG.

100% compatible with Python 2.6.6 (RHEL 6.5) and Python 3.x standard library.
No external packages, no network calls during lookup, no bytecode generation.
Automatically reads live-synced GitHub indices from user cache (created by
`kb_fetch.py --sync`) when present, otherwise uses `library/kb/`.

Commands:
  status               Show KB version, 10-domain counts, GitHub URLs & sync cache state
  domain [name]        List all 10 domains with card counts, or list all cards in a domain
  recipe <circuit>     1-command end-to-end RHEL design blueprint (cards + checklists + CLI tools)
  search <query>       Search all 162 nodes (accent-insensitive Vietnamese + English)
  coord <query>        Exact lookup by Section (9.2, §12.3), Equation (Eq. 2.10), Page (page 342), or Index term
  skills [query]       Search & list vetted GitHub/Cadence skills (27 skill-* cards + 52 catalog.json repos)
  stage <1..7>         List cards & tools for a stage of the 7-Stage Optimal Design Cycle
  node <id>            Inspect node metadata, Razavi/GitHub refs, 2D coords, checklists & edges
  upgrades <id>        Inspect incoming/outgoing upgrade, fix & trade-off paths
  diagnose <symptom>   Diagnose circuit symptom -> root causes, fixes, skills & checklists
  chapter <1..19>      List canonical cards, sections & checklists for a Razavi chapter
  checklist [name]     Show a process-agnostic structural checklist (or list all 21)
  term <query>         Search the 2,280 bilingual CLB glossary terms (T001-T2280)
"""
from __future__ import print_function

import json
import os
import re
import sys
import time
import unicodedata

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


def _fmt_tool_cmd(script_name, tail_args=""):
    sp = os.path.join(TOOLS_DIR, script_name)
    quoted = ('"%s"' % sp) if (" " in sp or "\\" in sp) else sp
    if tail_args:
        return "python -B %s %s" % (quoted, tail_args)
    return "python -B %s" % quoted

# Explicit Unicode codepoints for Python 2.6 / Python 3 source safety
D_LOWER = u"\u0111"
D_UPPER = u"\u0110"
SECTION_SIGN = u"\u00a7"

PROCESS_QUERY_PRIORITIES = (
    "skill-gpdk-techsweep-and-gmid-lut-interpolator",
    "tech-nanometer-vdsmin-gmid-sizing",
    "skill-gm-id-lookup-table-sizing",
    "skill-closed-loop-sizing-and-pareto-optimization",
    "tech-channel-length-and-opamp-scaling",
    "tech-nanometer-opamp-design-case-studies",
    "law-short-channel-effects",
    "concept-bsim4-and-finfet-nanometer-models",
    "concept-process-corners-and-temperature",
    "topo-low-voltage-sub1v-bandgap",
    "topo-lvccml-wide-swing-mirror",
    "topo-bootstrapped-sampling-switch",
    "law-pelgrom-mismatch-and-sizing-duality",
    "tech-common-centroid-sti-wpe-layout",
)

# Priority routing rules: (include_regex_on_folded_query, exclude_regex_or_None, ordered_node_ids)
TOPIC_PRIORITY_RULES = (
    # --- PMIC: Buck-Boost, Buck, Boost, Charge-Pump, Power Stage, Control, Capless LDO & Protections ---
    (
        re.compile(r"\b(buck\s+boost|buckboost|4\s*switch|4switch|h\s+bridge)\b"),
        None,
        (
            "topo-boost-inverting-and-4switch-buckboost",
            "law-boost-buckboost-rhp-zero-and-bandwidth-limit",
            "law-dcdc-volt-second-ccm-dcm-and-state-space",
            "skill-dcdc-spectre-pss-pstb-and-averaged-veriloga-tb",
            "topo-power-stage-hs-bootstrap-driver-deadtime",
        ),
    ),
    (
        re.compile(r"\bbuck\b"),
        re.compile(r"\b(buck\s+boost|buckboost|bucket)\b"),
        (
            "topo-synchronous-buck-converter-architecture",
            "law-dcdc-volt-second-ccm-dcm-and-state-space",
            "topo-power-stage-hs-bootstrap-driver-deadtime",
            "tech-dcdc-vmc-type2-type3-compensator-synthesis",
            "tech-dcdc-cmc-subharmonic-slope-comp-and-cot",
            "topo-dcdc-ramp-sensefet-dcr-and-zcd-blocks",
            "skill-dcdc-spectre-pss-pstb-and-averaged-veriloga-tb",
        ),
    ),
    (
        re.compile(r"\bboost\b"),
        re.compile(r"\b(buck\s+boost|buckboost|gain\s+boost|gainboost|gain\s+boosted|impedance\s+boost)\b"),
        (
            "topo-boost-inverting-and-4switch-buckboost",
            "law-boost-buckboost-rhp-zero-and-bandwidth-limit",
            "law-dcdc-volt-second-ccm-dcm-and-state-space",
            "skill-dcdc-spectre-pss-pstb-and-averaged-veriloga-tb",
            "topo-switched-capacitor-charge-pump-dcdc",
        ),
    ),
    (
        re.compile(r"\b(capless\s+ldo|capless|output\s+capacitor\s+less|fvf\s+ldo|dfc|damping\s+factor\s+control|ahuja|dynamic\s+sre)\b"),
        None,
        (
            "topo-capless-ldo-fvf-ahuja-dfc-and-sre",
            "topo-cmos-ldo-regulator",
            "skill-ldo-stability-load-line-psrr-tb",
            "topo-regulated-cascode-super-source-follower",
        ),
    ),
    (
        re.compile(r"\b(type\s+iii|type\s+3|type3|type\s+ii|type\s+2|type2|k\s+factor|vmc|voltage\s+mode\s+control)\b"),
        None,
        (
            "tech-dcdc-vmc-type2-type3-compensator-synthesis",
            "skill-dcdc-spectre-pss-pstb-and-averaged-veriloga-tb",
            "topo-synchronous-buck-converter-architecture",
            "law-boost-buckboost-rhp-zero-and-bandwidth-limit",
        ),
    ),
    (
        re.compile(r"\b(slope\s+compensation|slope\s+comp|subharmonic|cmc|current\s+mode\s+control|cot|constant\s+on\s+time)\b"),
        None,
        (
            "tech-dcdc-cmc-subharmonic-slope-comp-and-cot",
            "topo-dcdc-ramp-sensefet-dcr-and-zcd-blocks",
            "skill-dcdc-spectre-pss-pstb-and-averaged-veriloga-tb",
            "topo-synchronous-buck-converter-architecture",
        ),
    ),
    (
        re.compile(r"\b(por|power\s+on\s+reset|uvlo|undervoltage|soft\s+start|softstart|foldback|ocp|overcurrent|tsd|thermal\s+shutdown|inrush)\b"),
        None,
        (
            "topo-pmic-protections-por-uvlo-softstart-ocp-tsd",
            "topo-central-bias-hub-powerup-and-sleep-gating",
            "topo-cmos-ldo-regulator",
            "topo-synchronous-buck-converter-architecture",
        ),
    ),
    (
        re.compile(r"\b(sensefet|dcr\s+sensing|inductor\s+dcr|zcd|zero\s+current|leb|leading\s+edge\s+blanking)\b"),
        None,
        (
            "topo-dcdc-ramp-sensefet-dcr-and-zcd-blocks",
            "topo-synchronous-buck-converter-architecture",
            "tech-dcdc-cmc-subharmonic-slope-comp-and-cot",
        ),
    ),
    (
        re.compile(r"\b(bootstrap\s+driver|hs\s+driver|high\s+side\s+driver|dead\s+time|deadtime|shoot\s+through)\b"),
        None,
        (
            "topo-power-stage-hs-bootstrap-driver-deadtime",
            "topo-synchronous-buck-converter-architecture",
            "topo-boost-inverting-and-4switch-buckboost",
        ),
    ),
    (
        re.compile(r"\b(dickson|charge\s+pump\s+dcdc|switched\s+capacitor\s+dc\s+dc|voltage\s+doubler|ssl|fsl)\b"),
        None,
        (
            "topo-switched-capacitor-charge-pump-dcdc",
            "law-dcdc-volt-second-ccm-dcm-and-state-space",
        ),
    ),
    (
        re.compile(r"\b(pwm\s+switch|averaged\s+switch|vorperian|volt\s+second|ccm|dcm|dcdc|dc\s+dc)\b"),
        None,
        (
            "law-dcdc-volt-second-ccm-dcm-and-state-space",
            "skill-dcdc-spectre-pss-pstb-and-averaged-veriloga-tb",
            "topo-synchronous-buck-converter-architecture",
            "topo-boost-inverting-and-4switch-buckboost",
        ),
    ),
    # --- AMS: DAC, Delta-Sigma, Pipeline/Flash, Active-RC/Tow-Thomas, Gm-C, INA/CFIA, Schmitt/Osc, Wireline, Bias Hub ---
    (
        re.compile(r"\b(current\s+steering|r\s+2r|r2r|resistor\s+string|kelvin\s+divider|segmented\s+dac|dac)\b"),
        re.compile(r"\b(cdac|sar\s+adc)\b"),
        (
            "topo-resistor-string-r2r-and-current-steering-dacs",
            "topo-deltasigma-modulator-sc-and-ct-architectures",
            "law-pelgrom-mismatch-and-sizing-duality",
        ),
    ),
    (
        re.compile(r"\b(delta\s+sigma|deltasigma|sigma\s+delta|ciff|cifb|ntf|dwa|data\s+weighted\s+averaging|excess\s+loop\s+delay)\b"),
        None,
        (
            "topo-deltasigma-modulator-sc-and-ct-architectures",
            "topo-resistor-string-r2r-and-current-steering-dacs",
            "topo-switched-capacitor-amplifiers-integrators",
        ),
    ),
    (
        re.compile(r"\b(pipelined\s+adc|pipeline\s+adc|mdac|flash\s+adc|rsd|1.5\s+bit|redundant\s+signed\s+digit)\b"),
        None,
        (
            "topo-flash-and-pipelined-mdac-rsd-adcs",
            "topo-analog-mux-and-adc-track-hold-drivers",
            "topo-sar-adc-architecture-and-cdac",
        ),
    ),
    (
        re.compile(r"\b(tow\s+thomas|fleischer\s+tow|sallen\s+key|active\s+rc|biquad)\b"),
        None,
        (
            "topo-active-rc-sallen-key-and-tow-thomas-biquads",
            "topo-gm-c-filters-and-automatic-rc-gmc-tuning",
        ),
    ),
    (
        re.compile(r"\b(gm\s+c|gmc|transconductance\s+c|gyrator|master\s+slave\s+tuning)\b"),
        None,
        (
            "topo-gm-c-filters-and-automatic-rc-gmc-tuning",
            "topo-active-rc-sallen-key-and-tow-thomas-biquads",
        ),
    ),
    (
        re.compile(r"\b(ina|cfia|instrumentation\s+amp|instrumentation\s+amplifier|chopper\s+cfia|3\s+op\s+amp|three\s+op\s+amp|dc\s+servo)\b"),
        None,
        (
            "topo-instrumentation-amp-3opamp-and-chopper-cfia",
            "tech-offset-autozero-and-chopping",
        ),
    ),
    (
        re.compile(r"\b(schmitt|hysteresis\s+comparator|window\s+comparator)\b"),
        None,
        (
            "topo-schmitt-trigger-and-hysteresis-comparators",
            "topo-relaxation-rc-sawtooth-and-crystal-oscillators",
            "topo-regenerative-latch-and-comparators",
        ),
    ),
    (
        re.compile(r"\b(relaxation\s+oscillator|sawtooth|pierce|crystal\s+oscillator|rc\s+oscillator)\b"),
        None,
        (
            "topo-relaxation-rc-sawtooth-and-crystal-oscillators",
            "topo-schmitt-trigger-and-hysteresis-comparators",
            "topo-central-bias-hub-powerup-and-sleep-gating",
        ),
    ),
    (
        re.compile(r"\b(lvds|cml|current\s+mode\s+logic|ctle|cdr|hogge|alexander)\b"),
        re.compile(r"\blvccml\b"),
        (
            "topo-high-speed-lvds-cml-ctle-and-cdr-basics",
        ),
    ),
    (
        re.compile(r"\b(i\s+ztc|iztc|ztc|bias\s+hub|current\s+star|sleep\s+gating|power\s+up\s+sequencing)\b"),
        None,
        (
            "topo-central-bias-hub-powerup-and-sleep-gating",
            "tech-hierarchical-chip-spec-budgeting-and-interfaces",
            "topo-bandgap-reference-core",
        ),
    ),
    (
        re.compile(r"\b(amux|analog\s+mux|t\s+switch|track\s+and\s+hold\s+driver|charge\s+bucket|adc\s+driver)\b"),
        None,
        (
            "topo-analog-mux-and-adc-track-hold-drivers",
            "topo-bootstrapped-sampling-switch",
            "skill-sar-adc-cdac-coherent-fft-calibration",
        ),
    ),
    # --- Cadence IC617 + Spectre 15.1 Closed-Loop Execution & Optimization Tools ---
    (
        re.compile(r"\b(psf\s+audit|psf\s+ascii|op\s+audit|dcopinfo|psf\s+struct)\b"),
        None,
        (
            "skill-psf-mos-op-waveform-and-spec-auditor",
            "skill-closed-loop-sizing-and-pareto-optimization",
            "skill-spectre-noise-dc-ac-tran-montecarlo",
            "skill-spectre-stb-diffstb-middlebrook",
        ),
    ),
    (
        re.compile(r"\b(gmid\s+lut|gpdk\s+techsweep|techsweep|monotone\s+cubic|pchip)\b"),
        None,
        (
            "skill-gpdk-techsweep-and-gmid-lut-interpolator",
            "skill-gm-id-lookup-table-sizing",
            "tech-nanometer-vdsmin-gmid-sizing",
            "skill-closed-loop-sizing-and-pareto-optimization",
        ),
    ),
    (
        re.compile(r"\b(sizing\s+opt|pareto|trust\s+region|nelder\s+mead|jacobian|ledro|closed\s+loop\s+sizing|7\s+stage)\b"),
        None,
        (
            "skill-closed-loop-sizing-and-pareto-optimization",
            "skill-gpdk-techsweep-and-gmid-lut-interpolator",
            "skill-psf-mos-op-waveform-and-spec-auditor",
            "tech-opamp-step-by-step-sizing-procedure",
            "tech-hierarchical-chip-spec-budgeting-and-interfaces",
        ),
    ),
    (
        re.compile(r"\b(live\s+bridge|ic617\s+live\s+bridge|ic617\s+client|cadence\s+exec|sadumpschematicjson|saplaceandwirefromplan|ipc\s+bridge|cdslck)\b"),
        None,
        (
            "skill-ic617-live-ipc-bridge-and-schematic-json",
            "skill-ic617-skill-sch-cdf-automation",
            "skill-ocean-parametric-testbench-runner",
        ),
    ),
)

DESIGN_STAGE_INFO = (
    (1, "1_spec_and_kb", u"Bước 1 · Đặc tả, Định tuyến Lý thuyết & Bảng kiểm Bất biến (kb_lookup + kb_fetch)"),
    (2, "2_hierarchical_budget", u"Bước 2 · Phân rã Kiến trúc Đa khối & Ngân sách Giao tiếp (project.json + spec.json)"),
    (3, "3_gmid_lut_sizing", u"Bước 3 · Định cỡ Vật lý bằng Bảng tra PDK gm/ID (< 5 ms gmid_lut.py)"),
    (4, "4_schematic_and_veriloga", u"Bước 4 · Dựng Schematic/Symbol OA & Mô hình Hành vi Hỗn hợp (ic617_client.py + Verilog-A)"),
    (5, "5_op_and_stb_audit", u"Bước 5 · Mô phỏng Spectre Baseline & Kiểm toán OP/STB/Tran (cadence_exec.py + psf_audit.py)"),
    (6, "6_sensitivity_pareto_opt", u"Bước 6 · Ma trận Độ nhạy Jacobian & Tối ưu Hóa Pareto Có Ràng buộc (sizing_opt.py)"),
    (7, "7_pvt_mc_pex_signoff", u"Bước 7 · Nghiệm thu Góc PVT, Nhiễu Mismatch Monte Carlo & Hậu Layout PEX"),
)


def to_text(value):
    if value is None:
        return u""
    if isinstance(value, TEXT_TYPE):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return TEXT_TYPE(value)


def write_utf8_json(payload):
    dumped = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    text = to_text(dumped) + u"\n"
    raw = text.encode("utf-8")
    if PY2:
        sys.stdout.write(raw)
    else:
        if hasattr(sys.stdout, "buffer"):
            sys.stdout.buffer.write(raw)
        else:
            sys.stdout.write(text)


def load_json_file(path):
    stream = open(path, "rb")
    try:
        raw = stream.read().decode("utf-8-sig")
        return json.loads(raw)
    finally:
        stream.close()


def fold_ascii(value):
    txt = to_text(value)
    if not txt:
        return u""
    txt = txt.replace(D_LOWER, u"d").replace(D_UPPER, u"D")
    decomp = unicodedata.normalize("NFD", txt)
    stripped = u"".join(ch for ch in decomp if not unicodedata.combining(ch)).lower()
    cleaned = re.sub(r"[^a-z0-9/+.]+", " ", stripped.replace("_", " ").replace("-", " "))
    return cleaned.strip()


def load_config():
    return ota_sync.load_config(LIBRARY_ROOT)


def get_cache_dir(cfg):
    return ota_sync.get_cache_dir(cfg=cfg, library_root=LIBRARY_ROOT)


def get_base_url(cfg):
    env_key = cfg.get("env_base_url", "RAZAVI_BRAIN_BASE_URL")
    val = os.environ.get(env_key, "").strip()
    if not val:
        val = to_text(cfg.get("base_url", "")).strip()
    return val.rstrip("/")


def get_raw_base_url(cfg):
    env_key = cfg.get("env_raw_base_url", "RAZAVI_BRAIN_RAW_URL")
    val = os.environ.get(env_key, "").strip()
    if not val:
        val = to_text(cfg.get("raw_base_url", "")).strip()
    return val.rstrip("/")


def resolve_data_file(cfg, synced_name, bundled_name, ssot_name=None):
    if SSOT_KB_DIR:
        ssot_rel = ssot_name or bundled_name
        ssot_parts = [p for p in to_text(ssot_rel).split("/") if p]
        ssot_path = os.path.join(*([SSOT_KB_DIR] + ssot_parts))
        if os.path.isfile(ssot_path):
            return ssot_path, False
    cache_dir = get_cache_dir(cfg)
    synced_parts = [p for p in to_text(synced_name).split("/") if p]
    bundled_parts = [p for p in to_text(bundled_name).split("/") if p]
    synced_path = os.path.join(*([cache_dir, "synced"] + synced_parts))
    if os.path.isfile(synced_path):
        return synced_path, True
    return os.path.join(*([KB_DIR] + bundled_parts)), False


def resolve_local_diagram_path(cfg, node):
    diag_name = os.path.basename(to_text(node.get("diagram", "")))
    if not diag_name:
        return ""
    candidates = []
    if SSOT_KB_DIR:
        candidates.append(os.path.join(SSOT_KB_DIR, "diagrams", diag_name))
    candidates.append(os.path.join(get_cache_dir(cfg), "synced", "diagrams", diag_name))
    candidates.append(os.path.join(KB_DIR, "diagrams", diag_name))
    for cand in candidates:
        if cand and os.path.isfile(cand):
            return cand
    return ""


def load_router(cfg=None):
    cfg = cfg or load_config()
    path, _ = resolve_data_file(cfg, "router-index.json", "router-index.json", "router-index.json")
    if not os.path.isfile(path):
        raise IOError("Missing router index: " + path)
    return load_json_file(path)


def load_edges(cfg=None):
    cfg = cfg or load_config()
    path, _ = resolve_data_file(cfg, "edges.jsonl", "edges.jsonl", "graph/edges.jsonl")
    edges = []
    if not os.path.isfile(path):
        return edges
    stream = open(path, "rb")
    try:
        for raw_line in stream:
            line = raw_line.decode("utf-8-sig").strip()
            if line:
                edges.append(json.loads(line))
    finally:
        stream.close()
    return edges


def load_glossary(cfg=None):
    cfg = cfg or load_config()
    path, _ = resolve_data_file(cfg, "terms-vi-en.json", "terms-vi-en.json", "glossary/terms-vi-en.json")
    if not os.path.isfile(path):
        return []
    data = load_json_file(path)
    return data.get("terms", [])


def load_coordinates(cfg=None):
    cfg = cfg or load_config()
    path, _ = resolve_data_file(
        cfg,
        "coordinates/book-coordinates.json",
        "coordinates/book-coordinates.json",
        "coordinates/book-coordinates.json",
    )
    if not os.path.isfile(path):
        return {}
    return load_json_file(path)


def load_skills_catalog(cfg=None):
    cfg = cfg or load_config()
    path, _ = resolve_data_file(
        cfg,
        "github-skills/catalog.json",
        "github-skills/catalog.json",
        "github-skills/catalog.json",
    )
    if not os.path.isfile(path):
        return {}
    return load_json_file(path)


def web_url_for_node(base_url, node_id):
    anchor = "#node/%s" % node_id
    if base_url:
        return "%s/%s" % (base_url, anchor)
    return anchor


def web_url_for_coord(base_url, kind_slug, target_id):
    anchor = "#%s/%s" % (kind_slug, target_id)
    if base_url:
        return "%s/%s" % (base_url, anchor)
    return anchor


def raw_url_for_node(raw_base_url, node):
    rel_path = to_text(node.get("raw_rel_path") or node.get("path") or "").lstrip("/")
    if raw_base_url and rel_path:
        return "%s/%s" % (raw_base_url, rel_path)
    return ""


def diagram_url_for_node(base_url, raw_base_url, node):
    diag_name = os.path.basename(to_text(node.get("diagram", "")))
    if not diag_name:
        return ""
    if base_url:
        return "%s/kb/diagrams/%s" % (base_url, diag_name)
    if raw_base_url:
        return "%s/kb/diagrams/%s" % (raw_base_url, diag_name)
    return ""


def score_node_match(node, q_fold, q_tokens):
    if not q_fold:
        return 1
    nid = to_text(node.get("id", ""))
    nid_f = fold_ascii(nid)
    vi_f = fold_ascii(node.get("title_vi", ""))
    en_f = fold_ascii(node.get("title_en", ""))
    hay = to_text(node.get("search_text", ""))
    if not hay:
        hay = fold_ascii(
            "%s %s %s %s"
            % (
                nid,
                node.get("title_vi", ""),
                node.get("title_en", ""),
                node.get("summary", ""),
            )
        )

    score = 0
    if nid_f == q_fold:
        score = 300
    elif q_fold in vi_f or q_fold in en_f:
        score = 145
    elif q_fold in nid_f:
        score = 130
    elif q_fold in hay:
        score = 105
    else:
        matched = 0
        for tok in q_tokens:
            if tok in hay:
                matched += 1
        if q_tokens and matched == len(q_tokens):
            score = 80 + matched * 5
        elif matched > 0 and len(q_tokens) >= 2 and matched >= len(q_tokens) - 1:
            score = 35 + matched * 5

    # Domain-specific priority boosts for PMIC, AMS, and Closed-Loop Cadence Tools
    for inc_re, exc_re, priority_ids in TOPIC_PRIORITY_RULES:
        if inc_re.search(q_fold):
            if exc_re is not None and exc_re.search(q_fold):
                continue
            if nid in priority_ids:
                rank_bonus = 240 - priority_ids.index(nid) * 8 + min(score, 25)
                if rank_bonus > score:
                    score = rank_bonus

    # Process-node queries ("90nm", "65nm", "45nm", "180nm", "nanometer", "pdk")
    if re.search(r"\b(180nm|130nm|90nm|65nm|45nm|28nm|nanomet|nanometer|pdk)\b", q_fold):
        if nid in PROCESS_QUERY_PRIORITIES:
            rank_bonus = 185 - PROCESS_QUERY_PRIORITIES.index(nid) * 6
            if rank_bonus > score:
                score = rank_bonus
        elif score == 0 and node.get("process_agnostic"):
            score = 25

    return score


def compact_node_hit(node, cfg, score=None):
    base_url = get_base_url(cfg)
    raw_base = get_raw_base_url(cfg)
    nid = node.get("id", "")
    out = {
        "id": nid,
        "kind": node.get("kind"),
        "domain": node.get("domain"),
        "title_vi": node.get("title_vi"),
        "title_en": node.get("title_en"),
        "summary": node.get("summary"),
        "chapters": node.get("chapters", []),
        "razavi_refs": node.get("razavi_refs", []),
        "checklists": node.get("checklists", []),
        "diagram": node.get("diagram", ""),
        "diagram_local_path": resolve_local_diagram_path(cfg, node),
        "diagram_url": diagram_url_for_node(base_url, raw_base, node),
        "symptoms_addressed": node.get("symptoms_addressed", []),
        "limitations": node.get("limitations", []),
        "web_url": web_url_for_node(base_url, nid),
        "github_raw_url": raw_url_for_node(raw_base, node),
        "fetch_cmd": _fmt_tool_cmd("kb_fetch.py", nid),
    }
    if node.get("github_refs"):
        out["github_refs"] = node.get("github_refs", [])
    if node.get("coord_2d"):
        out["coord_2d"] = node.get("coord_2d")
    if node.get("design_stages"):
        out["design_stages"] = node.get("design_stages", [])
    if score is not None:
        out["score"] = score
    return out


def cmd_status():
    cfg = load_config()
    router_path, using_synced = resolve_data_file(cfg, "router-index.json", "router-index.json", "router-index.json")
    router = load_json_file(router_path)
    edges = load_edges(cfg)
    terms = load_glossary(cfg)
    coords = load_coordinates(cfg)
    catalog = load_skills_catalog(cfg)
    nodes = router.get("nodes", [])
    skill_count = len([n for n in nodes if n.get("kind") == "skill" or n.get("domain") == "eda-and-github-skills"])
    pmic_count = len([n for n in nodes if n.get("domain") == "power-management-ic"])
    ams_count = len([n for n in nodes if n.get("domain") == "ams-filters-and-system"])
    eda_dom_count = len([n for n in nodes if n.get("domain") == "eda-and-github-skills"])
    razavi_core_count = len(nodes) - pmic_count - ams_count - eda_dom_count
    sync_meta_path = os.path.join(get_cache_dir(cfg), "synced", "sync-receipt.json")
    sync_meta = load_json_file(sync_meta_path) if os.path.isfile(sync_meta_path) else None
    if SSOT_KB_DIR:
        idx_source = "ssot-git-checkout"
    elif using_synced:
        idx_source = "github-synced-cache"
    else:
        idx_source = "local-bundled-kb"
    return {
        "ok": True,
        "command": "status",
        "client_release": cfg.get("release", ota_sync.RELEASE_VERSION),
        "kb_release": router.get("release", ""),
        "index_source": idx_source,
        "repo_url": cfg.get("repo_url", ""),
        "web_url": get_base_url(cfg),
        "raw_base_url": get_raw_base_url(cfg),
        "cache_dir": get_cache_dir(cfg),
        "sync_receipt": sync_meta,
        "counts": {
            "domains": len(router.get("domains", [])),
            "nodes": len(nodes),
            "razavi_core_nodes": razavi_core_count,
            "pmic_nodes": pmic_count,
            "ams_nodes": ams_count,
            "eda_domain_nodes": eda_dom_count,
            "razavi_nodes": len(nodes) - skill_count,
            "skill_nodes": skill_count,
            "chapters": len(router.get("chapters", [])),
            "edges": len(edges),
            "checklists": len(router.get("checklists", [])),
            "diagrams": len(router.get("diagrams", [])),
            "glossary_terms": len(terms),
            "book_sections": len(coords.get("sections", [])),
            "book_equations": len(coords.get("equations", [])),
            "book_figures": len(coords.get("figures", [])),
            "book_index_terms": len(coords.get("index_terms", [])),
            "github_repos": len(catalog.get("repositories", [])),
        },
        "sync_cmd": _fmt_tool_cmd("kb_fetch.py", "--sync"),
    }


def cmd_search(query_str, limit=8):
    cfg = load_config()
    router = load_router(cfg)
    q_fold = fold_ascii(query_str)
    q_tokens = [t for t in q_fold.split() if t]

    scored = []
    for node in router.get("nodes", []):
        sc = score_node_match(node, q_fold, q_tokens)
        if sc > 0:
            scored.append((sc, node))

    scored.sort(key=lambda pair: (-pair[0], pair[1].get("id", "")))
    hits = [compact_node_hit(n, cfg, sc) for sc, n in scored[:limit]]

    cl_hits = []
    for cl in router.get("checklists", []):
        cl_hay = to_text(cl.get("search_text", ""))
        cid_f = fold_ascii(cl.get("checklist_id", ""))
        if q_fold and (
            q_fold in cl_hay
            or q_fold in cid_f
            or (q_tokens and all(t in (cl_hay + u" " + cid_f) for t in q_tokens))
        ):
            cl_hits.append(
                {
                    "checklist_id": cl.get("checklist_id"),
                    "title_vi": cl.get("title_vi"),
                    "check_count": cl.get("check_count"),
                }
            )

    return {
        "ok": True,
        "command": "search",
        "query": to_text(query_str),
        "repo_url": cfg.get("repo_url", ""),
        "total_matches": len(scored),
        "results": hits,
        "matching_checklists": cl_hits[:5],
    }


def _enrich_section_record(sec, base_url):
    primary = sec.get("primary_nodes", [])
    first_nid = primary[0] if primary else ""
    return {
        "section_id": sec.get("section_id"),
        "chapter": sec.get("chapter"),
        "level": sec.get("level"),
        "title_en": sec.get("title_en"),
        "title_vi": sec.get("title_vi"),
        "book_pages": sec.get("book_pages"),
        "pdf_pages": sec.get("pdf_pages"),
        "key_equations": sec.get("key_equations", []),
        "key_figures": sec.get("key_figures", []),
        "worked_examples": sec.get("worked_examples", []),
        "summary_vi": sec.get("summary_vi", ""),
        "primary_nodes": primary,
        "web_url": web_url_for_node(base_url, first_nid) if first_nid else web_url_for_coord(base_url, "coord", sec.get("section_id", "")),
    }


def _enrich_equation_record(eq, base_url, ch_map=None):
    nid = eq.get("node_id", "")
    ch_obj = ch_map.get(eq.get("chapter")) if ch_map else None
    out = {
        "eq_id": eq.get("eq_id"),
        "eq_num": eq.get("eq_num"),
        "label": eq.get("label"),
        "chapter": eq.get("chapter"),
        "section": eq.get("section"),
        "book_page": eq.get("book_page"),
        "pdf_page": eq.get("pdf_page"),
        "latex": eq.get("latex"),
        "meaning_vi": eq.get("meaning_vi"),
        "node_id": nid,
        "related_nodes": eq.get("related_nodes", []),
        "web_url": web_url_for_node(base_url, nid) if nid else "",
    }
    if ch_obj and ch_obj.get("pdf_file"):
        out["pdf_file"] = ch_obj.get("pdf_file")
    return out


def _enrich_figure_record(fig, base_url, ch_map=None):
    nid = fig.get("node_id", "")
    ch_obj = ch_map.get(fig.get("chapter")) if ch_map else None
    cap = fig.get("caption") or fig.get("caption_en", "")
    out = {
        "fig_id": fig.get("fig_id"),
        "fig_num": fig.get("fig_num"),
        "label": fig.get("label"),
        "chapter": fig.get("chapter"),
        "section": fig.get("section"),
        "book_page": fig.get("book_page"),
        "pdf_page": fig.get("pdf_page"),
        "caption": cap,
        "caption_en": fig.get("caption_en") or cap,
        "node_id": nid,
        "related_nodes": fig.get("related_nodes", []),
        "web_url": web_url_for_node(base_url, nid) if nid else "",
    }
    if ch_obj and ch_obj.get("pdf_file"):
        out["pdf_file"] = ch_obj.get("pdf_file")
    return out


def cmd_coord(query_str, limit=12):
    cfg = load_config()
    base_url = get_base_url(cfg)
    router = load_router(cfg)
    coords = load_coordinates(cfg)
    if not coords:
        return {
            "ok": False,
            "command": "coord",
            "error": "Missing kb/coordinates/book-coordinates.json; run kb_fetch.py --sync",
        }

    q_raw = to_text(query_str).strip()
    q_clean = re.sub(u"^[%s\\ufffd]+" % SECTION_SIGN, u"sec ", q_raw).replace(SECTION_SIGN, u"sec ").strip()
    node_map = dict((n.get("id"), n) for n in router.get("nodes", []))

    sections_all = coords.get("sections", [])
    equations_all = coords.get("equations", [])
    figures_all = coords.get("figures", [])
    index_all = coords.get("index_terms", [])
    chapters_all = coords.get("chapters", [])
    ch_map = dict((c.get("chapter"), c) for c in chapters_all)
    sec_id_map = dict((to_text(s.get("section_id", "")).lower(), s) for s in sections_all)

    matched_sections = []
    matched_equations = []
    matched_figures = []
    matched_index_terms = []
    matched_chapters = []
    ordered_node_ids = []
    query_type = "subject_index"

    def add_nids(nids):
        for nid in nids:
            if nid and nid in node_map and nid not in ordered_node_ids:
                ordered_node_ids.append(nid)

    def add_chapter_num(cnum):
        c_obj = ch_map.get(cnum)
        if c_obj and all(x.get("chapter") != cnum for x in matched_chapters):
            matched_chapters.append(c_obj)

    # 1. Explicit Equation pattern: "Eq. 10.25", "Eq.2.10", "(2.10)", "pt 5.19", "phuong trinh 14.94"
    eq_num_resolved = None
    eq_match = re.match(
        r"^(?:(?:eqs?\.?|equations?|pt|phuong\s*trinh)\s*\(?(\d+\.\d+[a-z]?)\)?|\((\d+\.\d+[a-z]?)\))$",
        q_raw.strip(),
        re.IGNORECASE,
    )
    if not eq_match:
        eq_match = re.match(
            r"^(?:eqs?\.?|equations?|pt|phuong\s*trinh)\s*\(?(\d+\.\d+[a-z]?)\)?$",
            fold_ascii(q_raw),
            re.IGNORECASE,
        )
    if eq_match:
        eq_num_resolved = (
            eq_match.group(1) or (eq_match.group(2) if eq_match.lastindex and eq_match.lastindex >= 2 else "")
        ).strip()

    # 2. Page pattern: "page 342", "p. 342", "pp. 342", "trang 342", "pdf page 19", or bare integer > 19
    page_match = re.match(
        r"^(?:(pdf)\s*(?:page|p\.?|trang)?|(?:book\s*)?(?:pages?|pp?\.?|trang|tr\.?))\s*(\d+)$",
        fold_ascii(q_raw),
        re.IGNORECASE,
    )
    bare_int_match = re.match(r"^(\d+)$", q_raw)

    # 3. Figure or Worked Example pattern: "Fig. 16.43", "Figure 12.34", "Hình 16.43", "Fig. 12.34(a)", "Ex. 8.15"
    fig_ex_match = None
    if not eq_num_resolved and not page_match and not bare_int_match:
        fig_ex_match = re.match(
            r"^(fig(?:ure)?s?\.?|hinh|ex(?:ample)?s?\.?|vi\s*du)\s*\(?(\d+\.\d+)\s*([a-z])?\)?\.?$",
            fold_ascii(q_raw),
            re.IGNORECASE,
        )

    # 4. Section vs bare X.Y ("10.49", "14.94", "9.2", "§12.3", "16.3.1", "2.Problems")
    sec_id_resolved = None
    fig_num_resolved = None
    if not eq_num_resolved and not page_match and not bare_int_match and not fig_ex_match:
        explicit_sec_m = re.match(
            r"^(?:sec\.?|section|muc|ch\.?\s*\d+\s*sec\.?)\s*(\d+\.(?:\d+(?:\.\d+)?|problems))$",
            fold_ascii(q_clean),
            re.IGNORECASE,
        )
        bare_num_m = re.match(
            r"^(\d+\.(?:\d+[a-z]?(?:\.\d+)?|problems))$",
            fold_ascii(q_clean),
            re.IGNORECASE,
        )
        if explicit_sec_m:
            raw_tok = explicit_sec_m.group(1)
            if raw_tok in sec_id_map:
                sec_id_resolved = to_text(sec_id_map[raw_tok].get("section_id"))
            else:
                sec_id_resolved = raw_tok
        elif bare_num_m:
            cand_tok = bare_num_m.group(1)
            cand_base = re.sub(r"[a-z]$", "", cand_tok)
            if cand_tok in sec_id_map:
                sec_id_resolved = to_text(sec_id_map[cand_tok].get("section_id"))
            elif any(
                to_text(e.get("eq_num", "")).lower() in (cand_tok, cand_base)
                for e in equations_all
            ):
                eq_num_resolved = cand_tok
            elif any(
                to_text(fg.get("fig_num", "")).lower() in (cand_tok, cand_base)
                for fg in figures_all
            ):
                fig_num_resolved = cand_base
            else:
                sec_id_resolved = cand_tok

    if eq_num_resolved:
        query_type = "equation"
        eq_num = eq_num_resolved
        eq_base = re.sub(r"[a-z]$", "", eq_num.lower())
        eq_label = "(%s)" % eq_num
        parent_sec_ids = []
        for eq in equations_all:
            enum_low = to_text(eq.get("eq_num")).lower()
            eid_low = to_text(eq.get("eq_id")).lower()
            if enum_low == eq_num.lower() or enum_low == eq_base or eid_low == ("eq." + eq_num.lower()):
                matched_equations.append(_enrich_equation_record(eq, base_url, ch_map))
                add_chapter_num(eq.get("chapter"))
                if eq.get("section") and eq.get("section") not in parent_sec_ids:
                    parent_sec_ids.append(eq.get("section"))
                add_nids([eq.get("node_id")])
                add_nids(eq.get("related_nodes", []))

        # Put exact deepest assigned section(s) FIRST, then any ancestor sections
        for exact_sid in parent_sec_ids:
            sec_exact = sec_id_map.get(to_text(exact_sid).lower())
            if sec_exact:
                matched_sections.append(_enrich_section_record(sec_exact, base_url))
                add_nids(sec_exact.get("primary_nodes", []))

        for sec in sections_all:
            sid = sec.get("section_id", "")
            if any(ms.get("section_id") == sid for ms in matched_sections):
                continue
            key_eqs = [to_text(x).strip() for x in sec.get("key_equations", [])]
            if eq_label in key_eqs or ("(%s)" % eq_base) in key_eqs or eq_num in key_eqs:
                matched_sections.append(_enrich_section_record(sec, base_url))
                add_nids(sec.get("primary_nodes", []))

        # Also scan node razavi_refs.equations so every equation cited in cards resolves
        for n in router.get("nodes", []):
            for ref in n.get("razavi_refs", []):
                ref_eqs = [to_text(e).strip().strip("()").lower() for e in ref.get("equations", [])]
                if eq_num.lower() in ref_eqs or eq_base in ref_eqs:
                    add_nids([n.get("id")])
                    ref_sec = to_text(ref.get("section", "")).split(",")[0].split("-")[0].strip()
                    for sec in sections_all:
                        if sec.get("section_id") == ref_sec and all(
                            ms.get("section_id") != ref_sec for ms in matched_sections
                        ):
                            matched_sections.append(_enrich_section_record(sec, base_url))

    elif page_match or bare_int_match:
        is_pdf = bool(page_match and page_match.group(1))
        pg = int(page_match.group(2) if page_match else bare_int_match.group(1))
        query_type = "pdf_page" if is_pdf else "book_page"

        for ch in chapters_all:
            if is_pdf:
                if ch.get("pdf_page_start", 0) <= pg <= ch.get("pdf_page_end", 0):
                    matched_chapters.append(ch)
            else:
                if ch.get("book_page_start", 0) <= pg <= ch.get("book_page_end", 0) or (
                    pg <= 19 and ch.get("chapter") == pg
                ):
                    matched_chapters.append(ch)

        raw_page_secs = []
        for sec in sections_all:
            if is_pdf:
                if sec.get("pdf_page_start", 0) <= pg <= sec.get("pdf_page_end", 0):
                    raw_page_secs.append(sec)
            else:
                if sec.get("book_page_start", 0) <= pg <= sec.get("book_page_end", 0):
                    raw_page_secs.append(sec)
        raw_page_secs.sort(key=lambda s: (-int(s.get("level", 1)), s.get("book_page_start", 0)))
        for sec in raw_page_secs:
            matched_sections.append(_enrich_section_record(sec, base_url))
            add_nids(sec.get("primary_nodes", []))

        for eq in equations_all:
            if (is_pdf and eq.get("pdf_page") == pg) or (not is_pdf and eq.get("book_page") == pg):
                matched_equations.append(_enrich_equation_record(eq, base_url, ch_map))
                add_nids([eq.get("node_id")])
                add_nids(eq.get("related_nodes", []))

        for fg in figures_all:
            if (is_pdf and fg.get("pdf_page") == pg) or (not is_pdf and fg.get("book_page") == pg):
                matched_figures.append(_enrich_figure_record(fg, base_url, ch_map))
                add_nids([fg.get("node_id")])
                add_nids(fg.get("related_nodes", []))

        if not is_pdf:
            for it in index_all:
                hit_range = False
                for rng in it.get("page_ranges", []):
                    if isinstance(rng, list) and len(rng) == 2 and rng[0] <= pg <= rng[1]:
                        hit_range = True
                        break
                if hit_range:
                    matched_index_terms.append(
                        {
                            "term_en": it.get("term_en"),
                            "term_vi": it.get("term_vi"),
                            "book_pages": it.get("book_pages"),
                            "chapters": it.get("chapters", []),
                            "mapped_nodes": it.get("mapped_nodes", []),
                        }
                    )
                    add_nids(it.get("mapped_nodes", []))

        # Also check node razavi_refs page ranges & chapter fallback
        if not is_pdf:
            for n in router.get("nodes", []):
                for ref in n.get("razavi_refs", []):
                    for part in to_text(ref.get("pages", "")).split(","):
                        m_rng = re.match(r"^\s*(\d+)(?:\s*-\s*(\d+))?\s*$", part)
                        if m_rng:
                            p_lo = int(m_rng.group(1))
                            p_hi = int(m_rng.group(2) or m_rng.group(1))
                            if p_lo <= pg <= p_hi:
                                add_nids([n.get("id")])
        if matched_chapters and not matched_sections and not is_pdf:
            ch0 = matched_chapters[0]
            ch_secs = [s for s in sections_all if s.get("chapter") == ch0.get("chapter")]
            last_sec_end = max([s.get("book_page_end", 0) for s in ch_secs] or [ch0.get("book_page_start", pg)])
            est_pdf_pg = pg - int(ch0.get("book_page_start", 1)) + int(ch0.get("pdf_page_start", 1))
            matched_sections.append(
                {
                    "section_id": "%s.Problems" % ch0.get("chapter"),
                    "chapter": ch0.get("chapter"),
                    "level": 1,
                    "title_en": "Chapter %s References & Problems" % ch0.get("chapter"),
                    "title_vi": u"Tài liệu tham khảo & Bài tập cuối Chương %s (%s)" % (ch0.get("chapter"), to_text(ch0.get("title_vi", ""))),
                    "book_pages": "%s-%s" % (last_sec_end + 1, ch0.get("book_page_end")),
                    "pdf_pages": str(est_pdf_pg),
                    "key_equations": [],
                    "key_figures": [],
                    "worked_examples": [],
                    "summary_vi": u"Trang %s thuộc phần Bài tập / Tài liệu tham khảo cuối Chương %s (PDF trang %s trong %s)."
                    % (pg, ch0.get("chapter"), est_pdf_pg, to_text(ch0.get("pdf_file", ""))),
                    "primary_nodes": ch0.get("node_ids", []),
                    "web_url": web_url_for_node(base_url, ch0.get("node_ids", [""])[0]) if ch0.get("node_ids") else "",
                }
            )
        if matched_chapters and not ordered_node_ids:
            for ch in matched_chapters:
                add_nids(ch.get("node_ids", []))

    elif sec_id_resolved:
        query_type = "section"
        sec_id = sec_id_resolved
        ch_num = int(sec_id.split(".")[0])
        add_chapter_num(ch_num)
        for sec in sections_all:
            sid = to_text(sec.get("section_id", ""))
            if sid.lower() == sec_id.lower() or sid.lower().startswith(sec_id.lower() + "."):
                matched_sections.append(_enrich_section_record(sec, base_url))
                add_nids(sec.get("primary_nodes", []))
        for eq in equations_all:
            esec = to_text(eq.get("section", ""))
            if esec.lower() == sec_id.lower() or esec.lower().startswith(sec_id.lower() + "."):
                matched_equations.append(_enrich_equation_record(eq, base_url, ch_map))
                add_nids([eq.get("node_id")])
                add_nids(eq.get("related_nodes", []))
        for fg in figures_all:
            fsec = to_text(fg.get("section", ""))
            if fsec.lower() == sec_id.lower() or fsec.lower().startswith(sec_id.lower() + "."):
                matched_figures.append(_enrich_figure_record(fg, base_url, ch_map))
                add_nids([fg.get("node_id")])
                add_nids(fg.get("related_nodes", []))

    elif fig_ex_match or fig_num_resolved:
        if fig_ex_match:
            kind_tok = fig_ex_match.group(1).lower()
            base_num = fig_ex_match.group(2)
            sub_sfx = fig_ex_match.group(3) or ""
            full_num = base_num + sub_sfx
            is_fig = kind_tok.startswith("fig") or kind_tok.startswith("hinh")
        else:
            is_fig = True
            base_num = fig_num_resolved
            full_num = fig_num_resolved

        if is_fig:
            query_type = "figure"
            fig_sec_ids = []
            for fg in figures_all:
                fnum_low = to_text(fg.get("fig_num", "")).lower()
                if fnum_low == full_num.lower() or fnum_low == base_num.lower():
                    matched_figures.append(_enrich_figure_record(fg, base_url, ch_map))
                    add_chapter_num(fg.get("chapter"))
                    if fg.get("section") and fg.get("section") not in fig_sec_ids:
                        fig_sec_ids.append(fg.get("section"))
                    add_nids([fg.get("node_id")])
                    add_nids(fg.get("related_nodes", []))

            for exact_sid in fig_sec_ids:
                sec_exact = sec_id_map.get(to_text(exact_sid).lower())
                if sec_exact:
                    matched_sections.append(_enrich_section_record(sec_exact, base_url))
                    add_nids(sec_exact.get("primary_nodes", []))

            needle_full = "fig. " + full_num.lower()
            needle_base = "fig. " + base_num.lower()
            for sec in sorted(sections_all, key=lambda s: -int(s.get("level", 1))):
                sid = sec.get("section_id", "")
                if any(ms.get("section_id") == sid for ms in matched_sections):
                    continue
                pool = [to_text(item).lower() for item in sec.get("key_figures", [])]
                if needle_full in pool or needle_base in pool:
                    matched_sections.append(_enrich_section_record(sec, base_url))
                    add_nids(sec.get("primary_nodes", []))
                    add_chapter_num(sec.get("chapter"))
        else:
            query_type = "worked_example"
            needle = "ex. " + base_num.lower()
            for sec in sorted(sections_all, key=lambda s: -int(s.get("level", 1))):
                pool = [to_text(item).lower() for item in sec.get("worked_examples", [])]
                if needle in pool:
                    matched_sections.append(_enrich_section_record(sec, base_url))
                    add_nids(sec.get("primary_nodes", []))
                    add_chapter_num(sec.get("chapter"))

    else:
        query_type = "subject_index"
        q_fold = fold_ascii(q_raw)
        q_tokens = [t for t in q_fold.split() if t]

        scored_idx = []
        for it in index_all:
            en_f = fold_ascii(it.get("term_en", ""))
            vi_f = fold_ascii(it.get("term_vi", ""))
            hay = en_f + u" " + vi_f
            sc = 0
            if en_f == q_fold or vi_f == q_fold:
                sc = 200
            elif en_f.startswith(q_fold) or vi_f.startswith(q_fold):
                sc = 160
            elif q_fold and (q_fold in en_f or q_fold in vi_f):
                sc = 130
            elif q_tokens and all(tok in hay for tok in q_tokens):
                sc = 95 + len(q_tokens) * 5
            if sc > 0:
                scored_idx.append((sc, it))
        scored_idx.sort(key=lambda pair: (-pair[0], pair[1].get("term_en", "")))
        for _, it in scored_idx[:limit]:
            matched_index_terms.append(
                {
                    "term_en": it.get("term_en"),
                    "term_vi": it.get("term_vi"),
                    "book_pages": it.get("book_pages"),
                    "chapters": it.get("chapters", []),
                    "mapped_nodes": it.get("mapped_nodes", []),
                }
            )
            add_nids(it.get("mapped_nodes", []))

        scored_sec = []
        for sec in sections_all:
            en_f = fold_ascii(sec.get("title_en", ""))
            vi_f = fold_ascii(sec.get("title_vi", ""))
            sum_f = fold_ascii(sec.get("summary_vi", ""))
            hay = en_f + u" " + vi_f + u" " + sum_f
            sc = 0
            if q_fold and (q_fold in en_f or q_fold in vi_f):
                sc = 150
            elif q_fold and q_fold in sum_f:
                sc = 115
            elif q_tokens and all(tok in hay for tok in q_tokens):
                sc = 85 + len(q_tokens) * 5
            if sc > 0:
                scored_sec.append((sc, sec))
        scored_sec.sort(key=lambda pair: (-pair[0], pair[1].get("section_id", "")))
        for _, sec in scored_sec[:limit]:
            matched_sections.append(_enrich_section_record(sec, base_url))
            add_nids(sec.get("primary_nodes", []))

        scored_eq = []
        for eq in equations_all:
            m_f = fold_ascii(eq.get("meaning_vi", ""))
            l_f = to_text(eq.get("latex", "")).lower()
            sc = 0
            if q_fold and q_fold in m_f:
                sc = 120
            elif q_tokens and all(tok in (m_f + u" " + l_f) for tok in q_tokens):
                sc = 80 + len(q_tokens) * 5
            if sc > 0:
                scored_eq.append((sc, eq))
        scored_eq.sort(key=lambda pair: (-pair[0], pair[1].get("book_page", 0)))
        for _, eq in scored_eq[:limit]:
            matched_equations.append(_enrich_equation_record(eq, base_url, ch_map))
            add_nids([eq.get("node_id")])

        scored_fig = []
        for fg in figures_all:
            c_f = fold_ascii(fg.get("caption_en") or fg.get("caption", ""))
            sc = 0
            if q_fold and q_fold in c_f:
                sc = 125
            elif q_tokens and all(tok in c_f for tok in q_tokens):
                sc = 82 + len(q_tokens) * 5
            if sc > 0:
                scored_fig.append((sc, fg))
        scored_fig.sort(key=lambda pair: (-pair[0], pair[1].get("book_page", 0)))
        for _, fg in scored_fig[:limit]:
            matched_figures.append(_enrich_figure_record(fg, base_url, ch_map))
            add_nids([fg.get("node_id")])

    mapped_nodes = [compact_node_hit(node_map[nid], cfg) for nid in ordered_node_ids[:limit]]
    total_hits = (
        len(matched_sections)
        + len(matched_equations)
        + len(matched_figures)
        + len(matched_index_terms)
        + len(mapped_nodes)
    )

    return {
        "ok": total_hits > 0,
        "command": "coord",
        "query": q_raw,
        "query_type": query_type,
        "chapters": [
            {
                "chapter": c.get("chapter"),
                "title_en": c.get("title_en"),
                "title_vi": c.get("title_vi"),
                "book_pages": "%s-%s" % (c.get("book_page_start"), c.get("book_page_end")),
                "pdf_file": c.get("pdf_file"),
                "pdf_pages": c.get("pdf_page_range"),
            }
            for c in matched_chapters
        ],
        "sections": matched_sections[:limit],
        "equations": matched_equations[:limit],
        "figures": matched_figures[:limit],
        "index_terms": matched_index_terms[:limit],
        "mapped_nodes": mapped_nodes,
        "web_url": ("%s/#book" % base_url) if base_url else "#book",
    }


def _score_repo_match(repo_entry, q_fold, q_tokens):
    if not q_fold:
        return 1
    rid_f = fold_ascii(repo_entry.get("id", ""))
    rname_f = fold_ascii(repo_entry.get("repo", ""))
    cat_f = fold_ascii(repo_entry.get("category", ""))
    sum_f = fold_ascii(repo_entry.get("summary_vi", ""))
    compat_f = fold_ascii(repo_entry.get("ic617_compatibility", ""))
    tech_f = fold_ascii(" ".join(repo_entry.get("key_techniques", [])))
    linked_f = fold_ascii(" ".join(repo_entry.get("linked_nodes", [])))
    hay = "%s %s %s %s %s %s %s" % (rid_f, rname_f, cat_f, sum_f, compat_f, tech_f, linked_f)

    if rid_f == q_fold or rname_f == q_fold:
        return 200
    if q_fold in rname_f or q_fold in rid_f:
        return 155
    if q_fold in sum_f or q_fold in tech_f or q_fold in linked_f:
        return 125
    if q_fold in hay:
        return 105
    matched = 0
    for tok in q_tokens:
        if tok in hay:
            matched += 1
    if q_tokens and matched == len(q_tokens):
        return 85 + matched * 6
    if matched > 0 and len(q_tokens) >= 2 and matched >= len(q_tokens) - 1:
        return 40 + matched * 5
    return 0


def _compact_repo_entry(repo_entry, score=None):
    out = {
        "id": repo_entry.get("id"),
        "repo": repo_entry.get("repo"),
        "url": repo_entry.get("url"),
        "pinned_commit_or_branch": repo_entry.get("pinned_commit_or_branch"),
        "license": repo_entry.get("license"),
        "stars": repo_entry.get("stars"),
        "category": repo_entry.get("category"),
        "quality_tier": repo_entry.get("quality_tier"),
        "ic617_compatibility": repo_entry.get("ic617_compatibility"),
        "summary_vi": repo_entry.get("summary_vi"),
        "key_techniques": repo_entry.get("key_techniques", []),
        "linked_nodes": repo_entry.get("linked_nodes", []),
    }
    if score is not None:
        out["score"] = score
    return out


def cmd_skills(query_str="", limit=12):
    cfg = load_config()
    base_url = get_base_url(cfg)
    router = load_router(cfg)
    catalog = load_skills_catalog(cfg)
    skill_nodes = [
        n
        for n in router.get("nodes", [])
        if n.get("kind") == "skill" or n.get("domain") == "eda-and-github-skills"
    ]
    repos = catalog.get("repositories", [])

    q_raw = to_text(query_str).strip()
    if not q_raw or q_raw.lower() in ("list", "all"):
        cap = max(limit, len(skill_nodes))
        return {
            "ok": True,
            "command": "skills",
            "query": "",
            "release": catalog.get("release", router.get("release", "")),
            "vetted_repo_count": len(repos),
            "skill_card_count": len(skill_nodes),
            "categories": catalog.get("categories", []),
            "skill_cards": [compact_node_hit(n, cfg) for n in skill_nodes[:cap]],
            "repositories": [_compact_repo_entry(r) for r in repos[: max(limit, len(repos))]],
            "web_url": ("%s/#skills" % base_url) if base_url else "#skills",
        }

    q_fold = fold_ascii(q_raw)
    q_tokens = [t for t in q_fold.split() if t]

    scored_cards = []
    for n in skill_nodes:
        sc = score_node_match(n, q_fold, q_tokens)
        gh_hay = fold_ascii(
            " ".join(
                "%s %s" % (g.get("repo", ""), g.get("use", ""))
                for g in n.get("github_refs", [])
            )
        )
        if q_fold and q_fold in gh_hay:
            sc = max(sc, 120)
        elif sc == 0 and q_tokens and all(tok in gh_hay for tok in q_tokens):
            sc = 85 + len(q_tokens) * 5
        if sc > 0:
            scored_cards.append((sc, n))

    scored_cards.sort(key=lambda pair: (-pair[0], pair[1].get("id", "")))
    top_card_ids = set([n.get("id") for _, n in scored_cards[:limit]])
    referenced_repo_names = set()
    for _, n in scored_cards[:limit]:
        for g in n.get("github_refs", []):
            if g.get("repo"):
                referenced_repo_names.add(to_text(g.get("repo")).lower())

    scored_repos = []
    for r in repos:
        sc = _score_repo_match(r, q_fold, q_tokens)
        rname_low = to_text(r.get("repo", "")).lower()
        if rname_low in referenced_repo_names:
            sc = max(sc, 95)
        elif any(ln in top_card_ids for ln in r.get("linked_nodes", [])):
            sc = max(sc, 75)
        if sc > 0:
            scored_repos.append((sc, r))

    scored_repos.sort(key=lambda pair: (-pair[0], pair[1].get("id", "")))

    # If a repo matched directly (e.g., "LEDRO", "psf-parser", "open-pmic"), surface its linked skill-* cards too
    if not scored_cards and scored_repos:
        linked_skill_ids = set()
        for _, r in scored_repos[:limit]:
            for ln in r.get("linked_nodes", []):
                linked_skill_ids.add(ln)
        for n in skill_nodes:
            if n.get("id") in linked_skill_ids:
                scored_cards.append((90, n))

    return {
        "ok": True,
        "command": "skills",
        "query": q_raw,
        "skill_card_matches": len(scored_cards),
        "repo_matches": len(scored_repos),
        "skill_cards": [compact_node_hit(n, cfg, sc) for sc, n in scored_cards[:limit]],
        "repositories": [_compact_repo_entry(r, sc) for sc, r in scored_repos[:limit]],
        "web_url": ("%s/#skills" % base_url) if base_url else "#skills",
    }


def cmd_stage(stage_arg, limit=25):
    cfg = load_config()
    base_url = get_base_url(cfg)
    router = load_router(cfg)
    if not stage_arg or to_text(stage_arg).strip().lower() in ("list", "all"):
        stages_out = []
        for s_num, s_key, s_label in DESIGN_STAGE_INFO:
            cnt = len([n for n in router.get("nodes", []) if s_num in n.get("design_stages", [])])
            stages_out.append({"stage": s_num, "stage_key": s_key, "title_vi": s_label, "node_count": cnt})
        return {"ok": True, "command": "stage", "stages": stages_out}

    m = re.search(r"([1-7])", to_text(stage_arg))
    if not m:
        return {"ok": False, "command": "stage", "error": "Stage must be between 1 and 7 (or 'list')"}
    s_num = int(m.group(1))
    s_meta = DESIGN_STAGE_INFO[s_num - 1]
    matched = [compact_node_hit(n, cfg) for n in router.get("nodes", []) if s_num in n.get("design_stages", [])]
    return {
        "ok": True,
        "command": "stage",
        "stage": s_num,
        "stage_key": s_meta[1],
        "title_vi": s_meta[2],
        "total_matches": len(matched),
        "nodes": matched[:limit],
        "web_url": ("%s/#stage/%d" % (base_url, s_num)) if base_url else ("#stage/%d" % s_num),
    }


def resolve_node_by_id_or_slug(router, raw_id):
    nodes = router.get("nodes", [])
    target = to_text(raw_id).strip()
    for n in nodes:
        if n.get("id") == target:
            return n
    folded = fold_ascii(target)
    best = None
    best_sc = 0
    toks = [t for t in folded.split() if t]
    for n in nodes:
        sc = score_node_match(n, folded, toks)
        if sc > best_sc:
            best_sc = sc
            best = n
    return best


def cmd_node(node_query):
    cfg = load_config()
    router = load_router(cfg)
    edges = load_edges(cfg)
    node = resolve_node_by_id_or_slug(router, node_query)
    if not node:
        return {"ok": False, "command": "node", "error": "Node not found: " + to_text(node_query)}

    nid = node.get("id")
    incoming = [e for e in edges if e.get("to") == nid]
    outgoing = [e for e in edges if e.get("from") == nid]

    return {
        "ok": True,
        "command": "node",
        "node": compact_node_hit(node, cfg),
        "section_coords": node.get("section_coords", []),
        "roles": node.get("roles", {}),
        "invariants": node.get("invariants", []),
        "traps": node.get("traps", []),
        "incoming_edges": incoming,
        "outgoing_edges": outgoing,
    }


def cmd_upgrades(node_query):
    cfg = load_config()
    base_url = get_base_url(cfg)
    router = load_router(cfg)
    edges = load_edges(cfg)
    node = resolve_node_by_id_or_slug(router, node_query)
    if not node:
        return {"ok": False, "command": "upgrades", "error": "Node not found: " + to_text(node_query)}

    nid = node.get("id")
    node_map = dict((n.get("id"), n) for n in router.get("nodes", []))

    upgraded_from = []
    upgrades_to = []
    fixes_and_comp = []
    tradeoffs_and_constraints = []

    for e in edges:
        if e.get("to") == nid and e.get("rel") == "upgrades_to":
            src = node_map.get(e.get("from"), {})
            upgraded_from.append(
                {
                    "from": e.get("from"),
                    "title_vi": src.get("title_vi", ""),
                    "when": e.get("when", ""),
                    "cost": e.get("cost", ""),
                    "ref": e.get("ref", ""),
                    "web_url": web_url_for_node(base_url, e.get("from", "")),
                }
            )
        elif e.get("from") == nid:
            dst = node_map.get(e.get("to"), {})
            item = {
                "rel": e.get("rel"),
                "to": e.get("to"),
                "title_vi": dst.get("title_vi", ""),
                "when": e.get("when", ""),
                "cost": e.get("cost", ""),
                "ref": e.get("ref", ""),
                "web_url": web_url_for_node(base_url, e.get("to", "")),
            }
            if e.get("rel") == "upgrades_to":
                upgrades_to.append(item)
            elif e.get("rel") in ("fixes", "compensated_by"):
                fixes_and_comp.append(item)
            else:
                tradeoffs_and_constraints.append(item)
        elif e.get("to") == nid and e.get("rel") in ("fixes", "compensated_by"):
            src = node_map.get(e.get("from"), {})
            fixes_and_comp.append(
                {
                    "rel": e.get("rel") + " (incoming)",
                    "from": e.get("from"),
                    "title_vi": src.get("title_vi", ""),
                    "when": e.get("when", ""),
                    "cost": e.get("cost", ""),
                    "ref": e.get("ref", ""),
                    "web_url": web_url_for_node(base_url, e.get("from", "")),
                }
            )

    return {
        "ok": True,
        "command": "upgrades",
        "node_id": nid,
        "title_vi": node.get("title_vi"),
        "title_en": node.get("title_en"),
        "web_url": web_url_for_node(base_url, nid),
        "limitations": node.get("limitations", []),
        "upgraded_from": upgraded_from,
        "upgrades_to": upgrades_to,
        "fixes_and_compensation": fixes_and_comp,
        "other_relations": tradeoffs_and_constraints,
    }


def cmd_diagnose(symptom_query, limit=8):
    cfg = load_config()
    router = load_router(cfg)
    edges = load_edges(cfg)
    q_fold = fold_ascii(symptom_query)
    q_tokens = [t for t in q_fold.split() if t]

    node_scores = {}
    matched_symptoms = []
    for sym_key, nids in router.get("symptom_map", {}).items():
        sf = fold_ascii(sym_key)
        if q_fold in sf or sf in q_fold or (q_tokens and all(t in sf for t in q_tokens)):
            matched_symptoms.append(sym_key)
            for nid in nids:
                node_scores[nid] = node_scores.get(nid, 0) + 120

    for n in router.get("nodes", []):
        nid = n.get("id")
        lim_text = fold_ascii(" ".join(n.get("limitations", []) + n.get("traps", [])))
        sc = score_node_match(n, q_fold, q_tokens)
        if q_fold and (q_fold in lim_text or (q_tokens and all(t in lim_text for t in q_tokens))):
            sc += 55
        if sc > 0:
            node_scores[nid] = max(node_scores.get(nid, 0), sc)

    node_map = dict((n.get("id"), n) for n in router.get("nodes", []))
    ranked_ids = sorted(node_scores.keys(), key=lambda k: (-node_scores[k], k))[:limit]

    recommendations = []
    checklist_set = []
    for nid in ranked_ids:
        n = node_map[nid]
        rel_edges = [
            e
            for e in edges
            if (e.get("from") == nid or e.get("to") == nid)
            and e.get("rel") in ("upgrades_to", "fixes", "compensated_by")
        ]
        for cid in n.get("checklists", []):
            if cid not in checklist_set:
                checklist_set.append(cid)
        recommendations.append(
            {
                "node": compact_node_hit(n, cfg, node_scores[nid]),
                "actionable_edges": rel_edges[:6],
            }
        )

    return {
        "ok": True,
        "command": "diagnose",
        "symptom_query": to_text(symptom_query),
        "matched_symptom_tags": sorted(matched_symptoms),
        "recommended_checklists": checklist_set,
        "recommendations": recommendations,
    }


def cmd_chapter(chapter_arg):
    cfg = load_config()
    base_url = get_base_url(cfg)
    router = load_router(cfg)
    coords = load_coordinates(cfg)
    m = re.search(r"(\d+)", to_text(chapter_arg))
    if not m:
        return {"ok": False, "command": "chapter", "error": "Invalid chapter number: " + to_text(chapter_arg)}
    ch_num = int(m.group(1))
    if ch_num < 1 or ch_num > 19:
        return {"ok": False, "command": "chapter", "error": "Chapter must be between 1 and 19"}

    ch_info = None
    for c in router.get("chapters", []):
        if c.get("chapter") == ch_num:
            ch_info = c
            break

    ch_coord = None
    for c in coords.get("chapters", []):
        if c.get("chapter") == ch_num:
            ch_coord = c
            break

    nodes = [
        compact_node_hit(n, cfg)
        for n in router.get("nodes", [])
        if ch_num in n.get("chapters", [])
    ]
    sections = [
        _enrich_section_record(s, base_url)
        for s in coords.get("sections", [])
        if s.get("chapter") == ch_num and s.get("level", 1) == 1
    ]
    checklists = []
    for n in nodes:
        for cid in n.get("checklists", []):
            if cid not in checklists:
                checklists.append(cid)

    return {
        "ok": True,
        "command": "chapter",
        "chapter": ch_num,
        "title_en": ch_info.get("title_en", "") if ch_info else "",
        "title_vi": ch_info.get("title_vi", "") if ch_info else "",
        "book_pages": (
            "%s-%s" % (ch_coord.get("book_page_start"), ch_coord.get("book_page_end"))
            if ch_coord
            else ""
        ),
        "pdf_file": ch_coord.get("pdf_file", "") if ch_coord else "",
        "node_count": len(nodes),
        "major_sections": sections,
        "nodes": nodes,
        "related_checklists": checklists,
    }


def _resolve_checklist_path(cfg, cid):
    candidates = []
    if SSOT_KB_DIR:
        candidates.append(os.path.join(SSOT_KB_DIR, "checklists", cid + ".json"))
    candidates.append(os.path.join(get_cache_dir(cfg), "synced", "checklists", cid + ".json"))
    candidates.append(os.path.join(KB_DIR, "checklists", cid + ".json"))
    for cand in candidates:
        if cand and os.path.isfile(cand):
            return cand
    return os.path.join(KB_DIR, "checklists", cid + ".json")


def cmd_checklist(name_arg):
    cfg = load_config()
    router = load_router(cfg)
    if not name_arg or to_text(name_arg).strip().lower() in ("list", "all"):
        return {
            "ok": True,
            "command": "checklist",
            "checklists": router.get("checklists", []),
        }

    clean = to_text(name_arg).strip()
    if clean.endswith(".json"):
        clean = clean[:-5]

    direct_path = _resolve_checklist_path(cfg, clean)
    if not os.path.isfile(direct_path):
        q_f = fold_ascii(clean)
        for item in router.get("checklists", []):
            cid = item.get("checklist_id", "")
            if q_f in fold_ascii(cid) or q_f in to_text(item.get("search_text", "")):
                direct_path = _resolve_checklist_path(cfg, cid)
                break

    if not os.path.isfile(direct_path):
        return {
            "ok": False,
            "command": "checklist",
            "error": "Checklist not found: " + clean,
            "available": [c.get("checklist_id") for c in router.get("checklists", [])],
        }

    data = load_json_file(direct_path)
    return {
        "ok": True,
        "command": "checklist",
        "checklist": data,
    }


def cmd_term(query_str, limit=12):
    cfg = load_config()
    terms = load_glossary(cfg)
    q_raw = to_text(query_str).strip()
    q_fold = fold_ascii(q_raw)
    q_tokens = [t for t in q_fold.split() if t]
    code_match = re.match(r"^[tT]0*(\d+)$", q_raw)

    scored = []
    for entry in terms:
        if code_match and int(entry.get("id", "T0")[1:]) == int(code_match.group(1)):
            scored.append((0, entry))
            continue
        if not q_fold:
            continue
        en_f = fold_ascii(entry.get("en", ""))
        vi_f = fold_ascii(entry.get("vi", ""))
        key = to_text(entry.get("search_key", "")) or (en_f + u" " + vi_f)
        if en_f == q_fold or vi_f == q_fold:
            scored.append((1, entry))
        elif en_f.startswith(q_fold) or vi_f.startswith(q_fold):
            scored.append((2, entry))
        elif q_fold in en_f or q_fold in vi_f:
            scored.append((3, entry))
        elif q_tokens and all(tok in key for tok in q_tokens):
            scored.append((4, entry))
        elif q_fold in fold_ascii(entry.get("context", "")):
            scored.append((5, entry))

    scored.sort(key=lambda pair: (pair[0], int(pair[1].get("id", "T9999")[1:])))
    results = []
    for _, e in scored[:limit]:
        results.append(
            {
                "id": e.get("id"),
                "en": e.get("en"),
                "vi": e.get("vi"),
                "chapters": e.get("chapters", []),
                "context": e.get("context", ""),
                "curated_extension": bool(e.get("curated_extension", False)),
            }
        )

    return {
        "ok": True,
        "command": "term",
        "query": q_raw,
        "total_matches": len(scored),
        "results": results,
    }


def cmd_domain(domain_arg):
    cfg = load_config()
    router = load_router(cfg)
    domains = router.get("domains", [])
    nodes = router.get("nodes", [])
    if not domain_arg or to_text(domain_arg).strip().lower() in ("list", "all"):
        counts = {}
        for n in nodes:
            d = n.get("domain", "")
            counts[d] = counts.get(d, 0) + 1
        out_domains = []
        for d in domains:
            did = d.get("id", "")
            row = dict(d)
            row["node_count"] = counts.get(did, 0)
            out_domains.append(row)
        return {
            "ok": True,
            "command": "domain",
            "total_domains": len(out_domains),
            "domains": out_domains,
        }
    q_f = fold_ascii(domain_arg)
    chosen = None
    for d in domains:
        if d.get("id") == domain_arg.strip() or q_f in fold_ascii(d.get("id", "")) or q_f in fold_ascii(d.get("title_vi", "")) or q_f in fold_ascii(d.get("title_en", "")):
            chosen = d
            break
    if not chosen:
        return {
            "ok": False,
            "command": "domain",
            "error": "Unknown domain: " + to_text(domain_arg),
            "available": [d.get("id") for d in domains],
        }
    did = chosen.get("id")
    matched = [compact_node_hit(n, cfg) for n in nodes if n.get("domain") == did]
    return {
        "ok": True,
        "command": "domain",
        "domain": chosen,
        "node_count": len(matched),
        "nodes": matched,
    }


def cmd_recipe(circuit_query):
    search_res = cmd_search(circuit_query, limit=6)
    hits = search_res.get("results", [])
    checklists = ["common-mos"]
    theory_cards = []
    skill_cards = []
    for h in hits:
        for cid in h.get("checklists", []):
            if cid not in checklists:
                checklists.append(cid)
        if h.get("kind") == "skill" or to_text(h.get("id", "")).startswith("skill-"):
            skill_cards.append(h)
        else:
            theory_cards.append(h)
    if "closed-loop-sizing-and-signoff" not in checklists:
        checklists.append("closed-loop-sizing-and-signoff")

    qf = fold_ascii(circuit_query)
    is_switching_pmic = bool(re.search(r"\b(buck|boost|dcdc|dc\s+dc|pwm|charge\s+pump|cot|cmc|vmc)\b", qf))
    va_path = os.path.join(LIBRARY_ROOT, "models", "veriloga", "pwm_switch_avg_ccm_dcm.va")
    veriloga_note = (
        "%s (use for 0.3s .dc/.ac/.stb before transistor pss+pstb)" % va_path
        if is_switching_pmic
        else None
    )
    steps = [
        {
            "stage": 1,
            "name": "Locate project & fetch primary Razavi/PMIC/AMS cards + checklists",
            "cmds": [
                _fmt_tool_cmd("analogctl.py", "locate"),
                _fmt_tool_cmd("kb_fetch.py", hits[0]["id"] if hits else "topo-folded-cascode-ota"),
                _fmt_tool_cmd("kb_lookup.py", "checklist " + (checklists[1] if len(checklists) > 1 else "common-mos")),
            ],
        },
        {
            "stage": 2,
            "name": "Decompose multi-block hierarchy & interface contracts in project.json / spec.json",
            "cmds": [
                _fmt_tool_cmd("kb_fetch.py", "tech-hierarchical-chip-spec-budgeting-and-interfaces"),
            ],
        },
        {
            "stage": 3,
            "name": "Physics-based gm/ID initial sizing (< 1 ms per transistor)",
            "cmds": [
                _fmt_tool_cmd("gmid_lut.py", "size --lut ~/.cache/skill-analog/gmid-luts/gpdk090_1v2_NN.lut.json.gz --dev nmos --gm 1e-3 --gm-id 15 --l 180e-9 --vds 0.6"),
            ],
        },
        {
            "stage": 4,
            "name": "Inspect or update schematic via Live Virtuoso CIW Bridge (zero .cdslck conflict)",
            "cmds": [
                _fmt_tool_cmd("ic617_client.py", "ping"),
                _fmt_tool_cmd("ic617_client.py", "dump-json --out ./sim/runs/sch_dump.json"),
            ],
        },
        {
            "stage": 5,
            "name": "Run Spectre safely & audit MOS saturation regions + loop/waveform metrics",
            "cmds": [
                _fmt_tool_cmd("cadence_exec.py", "spectre --project . --netlist ./netlists/tb_top.scs --run-id run_01"),
                _fmt_tool_cmd("psf_audit.py", "op-audit ./sim/runs/run_01/psf --vds-margin 0.05"),
                _fmt_tool_cmd("psf_audit.py", "metrics ./sim/runs/run_01/psf --spec ./spec.json"),
            ],
        },
        {
            "stage": 6,
            "name": "Sensitivity Jacobian & Log-Space Constrained Pareto Optimization across PVT",
            "cmds": [
                _fmt_tool_cmd("sizing_opt.py", "--problem ./scripts/opt_problem.json --out ./sim/runs/opt_result.json"),
            ],
        },
        {
            "stage": 7,
            "name": "Worst-case PVT corners, Pelgrom Monte Carlo & Post-PEX Sign-off",
            "cmds": [
                _fmt_tool_cmd("kb_lookup.py", "checklist layout-and-matching"),
                _fmt_tool_cmd("kb_lookup.py", "checklist closed-loop-sizing-and-signoff"),
            ],
        },
    ]
    return {
        "ok": True,
        "command": "recipe",
        "circuit_query": to_text(circuit_query),
        "switching_converter_veriloga_helper": veriloga_note,
        "recommended_cards": hits,
        "theory_cards": [c.get("id") for c in theory_cards],
        "skill_playbooks": [c.get("id") for c in skill_cards],
        "mandatory_checklists": checklists,
        "closed_loop_7_stages": steps,
    }


HELP_TEXT = """Usage: python tools/kb_lookup.py COMMAND [ARGUMENTS] [--limit N] [--offline]

Commands:
  status               Show KB release (2026.11.18.7), 10-domain counts, GitHub URLs & OTA sync status
  domain [name]        List all 10 domains with counts, or list all cards in a domain
  recipe <circuit>     1-command 7-stage design blueprint (cards + checklists + CLI tools)
  search <query>       Accent-insensitive Vietnamese + English search across all 162 cards (Razavi + PMIC + AMS + EDA)
  coord <query>        Exact coordinate lookup by Section (9.2, §12.3), Equation (10.49, Eq. 14.94), Figure (Fig. 16.43), Page or 20_Index
  skills [query]       Search & list vetted GitHub/Cadence skills (27 skill-* cards + 52 catalog.json repos)
  stage [1..7]         List cards for a stage of the 7-Stage Optimal Design Cycle (or list all 7 stages)
  node <id>            Show full metadata, Razavi/GitHub refs, 2D coords, checklists & edges for a card
  upgrades <id>        Show topology evolution paths (upgrades_to, fixes, compensated_by)
  diagnose <symptom>   Map circuit symptom/failure mode to root causes, upgrades, skills & checklists
  chapter <1..19>      List all cards, major sections and checklists for a Razavi 2nd Ed. chapter
  checklist [name]     Inspect a process-agnostic checklist (or list all 21 checklists)
  term <query>         Search 2,280 standardized CLB bilingual glossary terms (T001-T2280)
  self-test            Run built-in dual-layout & offline conflict self-test suite
"""


def run_self_test():
    saved_env = os.environ.get("SKILL_ANALOG_OFFLINE")
    try:
        # 1. --sync --offline -> exit code 2
        rc1 = main(["--sync", "--offline", "--quiet-errors"])
        if rc1 != 2:
            raise AssertionError("Expected exit 2 for --sync --offline, got %s" % rc1)

        # 2. SKILL_ANALOG_OFFLINE=1 + --sync -> exit code 2
        os.environ["SKILL_ANALOG_OFFLINE"] = "1"
        rc2 = main(["--sync", "--quiet-errors"])
        if rc2 != 2:
            raise AssertionError("Expected exit 2 for SKILL_ANALOG_OFFLINE=1 --sync, got %s" % rc2)

        # 3. Offline fast lookup (< 50 ms) with local SVG resolution
        t0 = time.time()
        st = cmd_status()
        sr = cmd_search("4-switch buck-boost", limit=3)
        dt_ms = round((time.time() - t0) * 1000.0, 2)
        if not st.get("ok") or st["counts"]["nodes"] != 162:
            raise AssertionError("Unexpected status counts: %r" % st)
        if not sr.get("results") or sr["results"][0]["id"] != "topo-boost-inverting-and-4switch-buckboost":
            raise AssertionError("Priority search mismatch: %r" % sr.get("results"))
        if not sr["results"][0].get("diagram_local_path") or not os.path.isfile(sr["results"][0]["diagram_local_path"]):
            raise AssertionError("Missing local SVG path in search hit: %r" % sr["results"][0])

        # 4. Exact coordinate lookup for equations and figures
        ce = cmd_coord("10.49", limit=5)
        cf = cmd_coord("Fig. 16.43", limit=5)
        if not ce.get("ok") or not ce.get("equations") or ce["equations"][0].get("section") != "10.7":
            raise AssertionError("Unexpected coord('10.49') result: %r" % ce)
        if not cf.get("ok") or not cf.get("figures") or cf["figures"][0].get("book_page") != 679:
            raise AssertionError("Unexpected coord('Fig. 16.43') result: %r" % cf)

        return {
            "ok": True,
            "command": "self-test",
            "release": ota_sync.RELEASE_VERSION,
            "lookup_ms": dt_ms,
            "tests_passed": 5,
        }
    finally:
        if saved_env is None:
            if "SKILL_ANALOG_OFFLINE" in os.environ:
                del os.environ["SKILL_ANALOG_OFFLINE"]
        else:
            os.environ["SKILL_ANALOG_OFFLINE"] = saved_env


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help", "help"):
        print(HELP_TEXT)
        return 0

    limit = 10
    offline_flag = False
    sync_flag = False
    self_test_flag = False
    quiet_errors = False
    base_url_override = None
    cleaned = []
    i = 0
    flag_cmd = None
    while i < len(args):
        tok = args[i]
        if tok == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])
            i += 2
        elif tok == "--offline":
            offline_flag = True
            i += 1
        elif tok == "--sync":
            sync_flag = True
            i += 1
        elif tok == "--self-test":
            self_test_flag = True
            i += 1
        elif tok == "--quiet-errors":
            quiet_errors = True
            i += 1
        elif tok == "--base-url" and i + 1 < len(args):
            base_url_override = args[i + 1]
            i += 2
        elif tok in ("--query", "--topology") and i + 1 < len(args):
            flag_cmd = "search"
            cleaned.append(args[i + 1])
            i += 2
        elif tok in ("--coord", "--coordinate") and i + 1 < len(args):
            flag_cmd = "coord"
            cleaned.append(args[i + 1])
            i += 2
        elif tok in ("--skills", "--skill") and i + 1 < len(args):
            flag_cmd = "skills"
            cleaned.append(args[i + 1])
            i += 2
        elif tok in ("--stage",) and i + 1 < len(args):
            flag_cmd = "stage"
            cleaned.append(args[i + 1])
            i += 2
        elif tok in ("--symptom", "--goal") and i + 1 < len(args):
            flag_cmd = "diagnose"
            cleaned.append(args[i + 1])
            i += 2
        elif tok == "--chapter" and i + 1 < len(args):
            flag_cmd = "chapter"
            cleaned.append(args[i + 1])
            i += 2
        elif tok in ("--json", "--text"):
            i += 1
        else:
            cleaned.append(tok)
            i += 1

    if self_test_flag or (cleaned and cleaned[0].lower() == "self-test"):
        payload = run_self_test()
        write_utf8_json(payload)
        return 0 if payload.get("ok") else 1

    # Strict --offline / SKILL_ANALOG_OFFLINE=1 precedence FIRST
    eff_offline = bool(offline_flag or ota_sync.is_offline_env())
    if (sync_flag or (cleaned and cleaned[0].lower() == "sync")) and eff_offline:
        if not quiet_errors:
            write_utf8_json(
                {
                    "ok": False,
                    "command": "sync",
                    "error": "Conflicting options: --sync cannot run when --offline or SKILL_ANALOG_OFFLINE=1 is active.",
                }
            )
        return 2

    if sync_flag or (cleaned and cleaned[0].lower() == "sync"):
        try:
            payload = ota_sync.sync_now(
                library_root=LIBRARY_ROOT,
                base_url_override=base_url_override,
                offline=eff_offline,
            )
            write_utf8_json(payload)
            return 0 if payload.get("ok") else 1
        except ota_sync.OtaConflictError as exc:
            if not quiet_errors:
                write_utf8_json({"ok": False, "command": "sync", "error": str(exc)})
            return 2
        except Exception as exc:
            if not quiet_errors:
                write_utf8_json({"ok": False, "command": "sync", "error": str(exc)})
            return 1

    if not cleaned and not flag_cmd:
        print(HELP_TEXT)
        return 0

    if flag_cmd:
        cmd = flag_cmd
        rest = " ".join(cleaned).strip()
    else:
        cmd = cleaned[0].lower()
        rest = " ".join(cleaned[1:]).strip()

    # Transparent background TTL auto-sync (0 ms on Windows SSOT, 0 ms when offline, 0 ms within 60s TTL)
    ota_sync.maybe_auto_sync(
        ttl_sec=60,
        offline=eff_offline,
        library_root=LIBRARY_ROOT,
        base_url_override=base_url_override,
    )

    try:
        if cmd == "status":
            payload = cmd_status()
        elif cmd in ("domain", "domains"):
            payload = cmd_domain(rest)
        elif cmd in ("recipe", "workflow", "plan"):
            if not rest:
                raise ValueError("recipe requires a circuit query (e.g., 'buck', 'capless ldo', 'folded cascode')")
            payload = cmd_recipe(rest)
        elif cmd == "search":
            if not rest:
                raise ValueError("search requires a query string")
            payload = cmd_search(rest, limit=limit)
        elif cmd in ("coord", "coords", "coordinate", "coordinates"):
            if not rest:
                raise ValueError("coord requires a section, equation, page, or index query")
            payload = cmd_coord(rest, limit=limit)
        elif cmd in ("skills", "skill", "github-skills"):
            payload = cmd_skills(rest, limit=limit)
        elif cmd in ("stage", "stages"):
            payload = cmd_stage(rest, limit=max(limit, 25))
        elif cmd == "node":
            if not rest:
                raise ValueError("node requires a node_id")
            payload = cmd_node(rest)
        elif cmd in ("upgrades", "upgrade"):
            if not rest:
                raise ValueError("upgrades requires a node_id")
            payload = cmd_upgrades(rest)
        elif cmd == "diagnose":
            if not rest:
                raise ValueError("diagnose requires a symptom query")
            payload = cmd_diagnose(rest, limit=limit)
        elif cmd == "chapter":
            if not rest:
                raise ValueError("chapter requires a chapter number (1..19)")
            payload = cmd_chapter(rest)
        elif cmd in ("checklist", "checklists"):
            payload = cmd_checklist(rest)
        elif cmd in ("term", "terms", "glossary"):
            if not rest:
                raise ValueError("term requires a query string or T-code")
            payload = cmd_term(rest, limit=limit)
        else:
            payload = cmd_search(" ".join(cleaned), limit=limit)

        write_utf8_json(payload)
        return 0 if payload.get("ok") else 1
    except Exception as exc:
        if not quiet_errors:
            write_utf8_json({"ok": False, "command": cmd, "error": str(exc)})
        return 2


if __name__ == "__main__":
    sys.exit(main())
