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
from __future__ import division, print_function

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
        re.compile(r"\b(capless\s+ldo|capless|capacitorless|cap\s+less|ocl\s+ldo|output\s+capacitor\s*less|fvf\s+ldo|dfc|damping\s+factor\s+control|ahuja|dynamic\s+sre)\b"),
        None,
        (
            "topo-capless-ldo-fvf-ahuja-dfc-and-sre",
            "topo-cmos-ldo-regulator",
            "skill-ldo-stability-load-line-psrr-tb",
            "topo-regulated-cascode-super-source-follower",
        ),
    ),
    (
        re.compile(r"\bldo\b"),
        re.compile(r"\b(capless|capacitorless|cap\s+less|ocl\s+ldo|output\s+capacitor\s*less|fvf\s+ldo|dfc|ahuja)\b"),
        (
            "topo-cmos-ldo-regulator",
            "topo-capless-ldo-fvf-ahuja-dfc-and-sre",
            "skill-ldo-stability-load-line-psrr-tb",
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
        re.compile(r"\bsong\s+hai\s+duoi\b"),
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
        re.compile(r"\b(pll|pfd|vco|cdr|dll|synthesizer|phase|jitter)\b"),
        (
            "topo-switched-capacitor-charge-pump-dcdc",
            "law-dcdc-volt-second-ccm-dcm-and-state-space",
        ),
    ),
    (
        re.compile(r"\b(?:(?:charge\s+pump).*\b(?:pll|pfd|vco|cdr|dll|synthesizer|phase|jitter)|(?:pll|pfd|vco|cdr|dll|synthesizer|phase|jitter).*\b(?:charge\s+pump)|pfd|phase\s+frequency\s+detector|type\s*2\s+pll|type\s*ii\s+pll|cp\s+pll)\b"),
        None,
        (
            "topo-charge-pump-type2-pll",
            "topo-pfd-deadzone-and-charge-pump-nonidealities",
            "tech-cp-pll-third-order-loop-filter-synthesis",
            "skill-pll-cp-loop-filter-lock-jitter-tb",
            "concept-pll-nonidealities-spurs-jitter",
        ),
    ),
    (
        re.compile(r"\bcurrent\s+mirror\b"),
        re.compile(r"\b(cascode|wide\s+swing|lvccml|wilson|regulated|diff\s*pair|differential\s+pair|active\s+current\s+mirror\s+load|tai\s+guong\s+dong)\b"),
        (
            "topo-basic-current-mirror",
            "topo-cascode-current-mirror",
            "topo-lvccml-wide-swing-mirror",
            "topo-wilson-and-regulated-current-mirrors",
        ),
    ),
    (
        re.compile(r"\b(bo\s+khuech?\s+dai\s+vi\s+sai\s+tai\s+guong\s+dong|vi\s+sai\s+tai\s+guong\s+dong|tai\s+guong\s+dong|diff\s*pair\s+active\s+current\s+mirror\s+load|differential\s+pair\s+with\s+active\s+current\s+mirror\s+load|active\s+current\s+mirror\s+load)\b"),
        None,
        (
            "topo-diff-pair-active-current-mirror-load",
            "concept-diffpair-mirror-pole-doublet",
            "topo-five-transistor-ota",
        ),
    ),
    (
        re.compile(r"\b(gain\s+boosted\s+cascode|gain\s+boosted|gain\s+boost|gainboost)\b"),
        None,
        (
            "topo-gain-boosted-cascode",
            "topo-regulated-cascode-super-source-follower",
            "skill-folded-cascode-and-gainboost-sizing-flow",
        ),
    ),
    (
        re.compile(r"\btelescopic(?:\s+(?:op\s*amp|opamp|cascode))?\b"),
        None,
        (
            "topo-telescopic-cascode-opamp",
            "topo-folded-cascode-ota",
            "topo-gain-boosted-cascode",
        ),
    ),
    (
        re.compile(r"\bsong\s+hai\s+duoi\b.*\b(chong|dao\s+dong|bu\s+doc|cmc|can\s+hai)\b|\b(chong|dao\s+dong|bu\s+doc|cmc|can\s+hai)\b.*\bsong\s+hai\s+duoi\b"),
        None,
        (
            "tech-dcdc-cmc-subharmonic-slope-comp-and-cot",
            "concept-diffpair-mirror-pole-doublet",
            "topo-dcdc-ramp-sensefet-dcr-and-zcd-blocks",
        ),
    ),
    (
        re.compile(r"\b(song\s+hai\s+duoi|cap\s+cuc\s+zero|doublet)\b"),
        re.compile(r"\b(chong|dao\s+dong|bu\s+doc|cmc|can\s+hai|slope\s+comp|slope\s+compensation|subharmonic|buck|boost|pwm|dcdc)\b"),
        (
            "concept-diffpair-mirror-pole-doublet",
            "topo-diff-pair-active-current-mirror-load",
            "tech-dcdc-cmc-subharmonic-slope-comp-and-cot",
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
        re.compile(r"\b(sub\s*1v\s+bandgap|sub1v\s+bandgap|fractional\s+bandgap|low\s+voltage\s+bandgap)\b"),
        None,
        (
            "topo-low-voltage-sub1v-bandgap",
            "topo-bandgap-reference-core",
            "law-ctat-ptat-temperature-cancellation",
            "tech-bandgap-curvature-compensation-and-speed",
            "skill-bandgap-startup-curvature-montecarlo-tb",
        ),
    ),
    (
        re.compile(r"\b(bgr|bandgap(?:\s+reference)?|brokaw|banba)\b"),
        re.compile(r"\b(sub\s*1v|sub1v|fractional\s+bandgap|low\s+voltage\s+bandgap|por|uvlo|soft\s*start|softstart|ocp|tsd)\b"),
        (
            "topo-bandgap-reference-core",
            "topo-low-voltage-sub1v-bandgap",
            "tech-bandgap-curvature-compensation-and-speed",
            "law-ctat-ptat-temperature-cancellation",
            "skill-bandgap-startup-curvature-montecarlo-tb",
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


_SYNONYM_PATTERNS = (
    (re.compile(r"\bbgr\b"), "bandgap reference"),
    (re.compile(r"\boutput\s+capacitor\s*less\b"), "capless"),
    (re.compile(r"\bcapacitor\s*less\b"), "capless"),
    (re.compile(r"\bcap\s+less\b"), "capless"),
    (re.compile(r"\bocl\s+ldo\b"), "capless ldo"),
    (re.compile(r"\bgainboosted\b"), "gain boosted"),
    (re.compile(r"\bgainboost\b"), "gain boost"),
    (re.compile(r"\bsub\s+harmonic\b"), "subharmonic"),
    (re.compile(r"\bdiffpair\b"), "diff pair"),
    (re.compile(r"\bbo\s+khuec\s+dai\b"), "bo khuech dai"),
    (re.compile(r"\btelescopic\s+op\s+amp\b"), "telescopic opamp"),
)
_WS_RE = re.compile(r"\s+")
_SUBWORD_SPLIT_RE = re.compile(r"[/+.\s]+")
_QUERY_STOPWORDS = set([
    "bo", "mach", "the", "a", "an", "of", "for", "with", "in", "on",
    "to", "by", "at", "from", "and", "or", "is", "are", "va", "cho", "cua",
])


def _normalize_query_synonyms(q_fold):
    if not q_fold:
        return u""
    s = to_text(q_fold)
    for pat, repl in _SYNONYM_PATTERNS:
        s = pat.sub(repl, s)
    s = _WS_RE.sub(" ", s).strip()
    return s


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

    sig_tokens = [t for t in q_tokens if t not in _QUERY_STOPWORDS]
    if not sig_tokens:
        sig_tokens = list(q_tokens)
    sig_cnt = len(sig_tokens)

    id_words = set(nid_f.split()) | set(_SUBWORD_SPLIT_RE.split(nid_f))
    title_f = vi_f + u" " + en_f
    title_words = set(title_f.split()) | set(_SUBWORD_SPLIT_RE.split(title_f))
    hay_words = set(hay.split()) | set(_SUBWORD_SPLIT_RE.split(hay))

    id_tok_hits = 0
    title_id_tok_hits = 0
    hay_tok_hits = 0
    exact_word_hits = 0
    for tok in sig_tokens:
        in_id = (tok in id_words) or (len(tok) >= 4 and tok in nid_f)
        in_title = (tok in title_words) or (len(tok) >= 4 and (tok in vi_f or tok in en_f))
        if in_id:
            id_tok_hits += 1
        if in_id or in_title:
            title_id_tok_hits += 1
        if (tok in hay_words) or (len(tok) >= 2 and tok in hay):
            hay_tok_hits += 1
        if tok in id_words or tok in title_words:
            exact_word_hits += 1

    score = 0
    if nid_f == q_fold:
        score = 400
    elif q_fold == vi_f or q_fold == en_f:
        score = 260
    elif q_fold in nid_f:
        score = 210
    elif q_fold in vi_f or q_fold in en_f:
        score = 180
    elif q_fold in hay:
        score = 115
    else:
        if sig_tokens and hay_tok_hits == sig_cnt:
            score = 80 + sig_cnt * 5
        elif hay_tok_hits > 0 and sig_cnt >= 2 and hay_tok_hits >= sig_cnt - 1:
            score = 35 + hay_tok_hits * 5

    if score > 0 and sig_cnt > 0:
        kind_bonus = 8 if node.get("kind") == "topology" else (4 if node.get("kind") == "technique" else 0)
        score += (
            (title_id_tok_hits * 40) // sig_cnt
            + (id_tok_hits * 24) // sig_cnt
            + (exact_word_hits * 12) // sig_cnt
            + kind_bonus
        )

    # Domain-specific priority boosts for PMIC, AMS, and Closed-Loop Cadence Tools
    for inc_re, exc_re, priority_ids in TOPIC_PRIORITY_RULES:
        if inc_re.search(q_fold):
            if exc_re is not None and exc_re.search(q_fold):
                continue
            if nid in priority_ids:
                rank_bonus = 320 - priority_ids.index(nid) * 16 + min(score // 25, 10)
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


def compact_node_hit(node, cfg, score=None, offline=False):
    base_url = get_base_url(cfg)
    raw_base = get_raw_base_url(cfg)
    nid = node.get("id", "")
    eff_offline = bool(offline or ota_sync.is_offline_env())
    fetch_args = nid + (" --offline" if eff_offline else "")
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
        "fetch_cmd": _fmt_tool_cmd("kb_fetch.py", fetch_args),
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


def cmd_status(offline=False):
    eff_offline = bool(offline or ota_sync.is_offline_env())
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
        "offline": eff_offline,
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


def cmd_search(query_str, limit=8, offline=False):
    eff_offline = bool(offline or ota_sync.is_offline_env())
    cfg = load_config()
    router = load_router(cfg)
    q_fold = _normalize_query_synonyms(fold_ascii(query_str))
    q_tokens = [t for t in q_fold.split() if t]

    scored = []
    for node in router.get("nodes", []):
        sc = score_node_match(node, q_fold, q_tokens)
        if sc > 0:
            scored.append((sc, node))

    scored.sort(key=lambda pair: (-pair[0], pair[1].get("id", "")))
    hits = [compact_node_hit(n, cfg, sc, offline=eff_offline) for sc, n in scored[:limit]]

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

    if to_text(query_str).strip() and len(scored) == 0 and len(cl_hits) == 0:
        return {
            "ok": False,
            "command": "search",
            "offline": eff_offline,
            "query": to_text(query_str),
            "repo_url": cfg.get("repo_url", ""),
            "error": "No matching cards or checklists found for query.",
            "total_matches": 0,
            "results": [],
            "matching_checklists": [],
        }

    return {
        "ok": True,
        "command": "search",
        "offline": eff_offline,
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


def cmd_coord(query_str, limit=12, offline=False):
    eff_offline = bool(offline or ota_sync.is_offline_env())
    cfg = load_config()
    base_url = get_base_url(cfg)
    router = load_router(cfg)
    coords = load_coordinates(cfg)
    if not coords:
        return {
            "ok": False,
            "command": "coord",
            "offline": eff_offline,
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

    mapped_nodes = [compact_node_hit(node_map[nid], cfg, offline=eff_offline) for nid in ordered_node_ids[:limit]]
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
        "offline": eff_offline,
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


def cmd_skills(query_str="", limit=12, offline=False):
    eff_offline = bool(offline or ota_sync.is_offline_env())
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
            "offline": eff_offline,
            "query": "",
            "release": catalog.get("release", router.get("release", "")),
            "vetted_repo_count": len(repos),
            "skill_card_count": len(skill_nodes),
            "categories": catalog.get("categories", []),
            "skill_cards": [compact_node_hit(n, cfg, offline=eff_offline) for n in skill_nodes[:cap]],
            "repositories": [_compact_repo_entry(r) for r in repos[: max(limit, len(repos))]],
            "web_url": ("%s/#skills" % base_url) if base_url else "#skills",
        }

    q_fold = _normalize_query_synonyms(fold_ascii(q_raw))
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
        "offline": eff_offline,
        "query": q_raw,
        "skill_card_matches": len(scored_cards),
        "repo_matches": len(scored_repos),
        "skill_cards": [compact_node_hit(n, cfg, sc, offline=eff_offline) for sc, n in scored_cards[:limit]],
        "repositories": [_compact_repo_entry(r, sc) for sc, r in scored_repos[:limit]],
        "web_url": ("%s/#skills" % base_url) if base_url else "#skills",
    }


def cmd_stage(stage_arg, limit=25, offline=False):
    eff_offline = bool(offline or ota_sync.is_offline_env())
    cfg = load_config()
    base_url = get_base_url(cfg)
    router = load_router(cfg)
    if not stage_arg or to_text(stage_arg).strip().lower() in ("list", "all"):
        stages_out = []
        for s_num, s_key, s_label in DESIGN_STAGE_INFO:
            cnt = len([n for n in router.get("nodes", []) if s_num in n.get("design_stages", [])])
            stages_out.append({"stage": s_num, "stage_key": s_key, "title_vi": s_label, "node_count": cnt})
        return {"ok": True, "command": "stage", "offline": eff_offline, "stages": stages_out}

    m = re.search(r"([1-7])", to_text(stage_arg))
    if not m:
        return {"ok": False, "command": "stage", "offline": eff_offline, "error": "Stage must be between 1 and 7 (or 'list')"}
    s_num = int(m.group(1))
    s_meta = DESIGN_STAGE_INFO[s_num - 1]
    matched = [compact_node_hit(n, cfg, offline=eff_offline) for n in router.get("nodes", []) if s_num in n.get("design_stages", [])]
    return {
        "ok": True,
        "command": "stage",
        "offline": eff_offline,
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
    folded = _normalize_query_synonyms(fold_ascii(target))
    best = None
    best_sc = 0
    toks = [t for t in folded.split() if t]
    for n in nodes:
        sc = score_node_match(n, folded, toks)
        if sc > best_sc:
            best_sc = sc
            best = n
    return best


def cmd_node(node_query, offline=False):
    eff_offline = bool(offline or ota_sync.is_offline_env())
    cfg = load_config()
    router = load_router(cfg)
    edges = load_edges(cfg)
    node = resolve_node_by_id_or_slug(router, node_query)
    if not node:
        return {"ok": False, "command": "node", "offline": eff_offline, "error": "Node not found: " + to_text(node_query)}

    nid = node.get("id")
    incoming = [e for e in edges if e.get("to") == nid]
    outgoing = [e for e in edges if e.get("from") == nid]

    return {
        "ok": True,
        "command": "node",
        "offline": eff_offline,
        "node": compact_node_hit(node, cfg, offline=eff_offline),
        "section_coords": node.get("section_coords", []),
        "roles": node.get("roles", {}),
        "invariants": node.get("invariants", []),
        "traps": node.get("traps", []),
        "incoming_edges": incoming,
        "outgoing_edges": outgoing,
    }


def cmd_upgrades(node_query, offline=False):
    eff_offline = bool(offline or ota_sync.is_offline_env())
    cfg = load_config()
    base_url = get_base_url(cfg)
    router = load_router(cfg)
    edges = load_edges(cfg)
    node = resolve_node_by_id_or_slug(router, node_query)
    if not node:
        return {"ok": False, "command": "upgrades", "offline": eff_offline, "error": "Node not found: " + to_text(node_query)}

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
        "offline": eff_offline,
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


_DIAGNOSE_SYMPTOM_ALIASES = (
    (
        re.compile(r"\b(chong\s+dao\s+dong\s+song\s+hai\s+duoi|dao\s+dong\s+song\s+hai\s+duoi)\b"),
        None,
        ("period-doubling-subharmonic-alternating-wide-narrow-pwm-pulses-when-duty-cycle-exceeds-50-percent",),
    ),
    (
        re.compile(r"\bsong\s+hai\s+duoi\b.*\b(chong|dao\s+dong|bu\s+doc|cmc|can\s+hai)\b|\b(chong|dao\s+dong|bu\s+doc|cmc|can\s+hai)\b.*\bsong\s+hai\s+duoi\b"),
        None,
        ("period-doubling-subharmonic-alternating-wide-narrow-pwm-pulses-when-duty-cycle-exceeds-50-percent",),
    ),
    (
        re.compile(r"\bsong\s+hai\s+duoi\b"),
        re.compile(r"\b(chong|dao\s+dong|bu\s+doc|cmc|can\s+hai)\b"),
        (
            "slow-settling-tail-from-pole-zero-doublet",
            "period-doubling-subharmonic-alternating-wide-narrow-pwm-pulses-when-duty-cycle-exceeds-50-percent",
        ),
    ),
    (
        re.compile(r"\bcap\s+cuc\s+zero\b"),
        None,
        (
            "slow-settling-tail-from-pole-zero-doublet",
            "slow-settling-tail-caused-by-active-mirror-pole-zero-doublet",
            "mirror-pole-doublet-in-single-ended-ota",
        ),
    ),
    (
        re.compile(r"\bduoi\s+xac\s+lap\b"),
        None,
        (
            "slow-settling-tail-from-pole-zero-doublet",
            "slow-settling-tail-caused-by-active-mirror-pole-zero-doublet",
            "slow-settling-tail-caused-by-misplaced-gain-boost-doublet",
            "mysterious-slow-settling-tail-despite-65-degree-phase-margin",
        ),
    ),
)


def cmd_diagnose(symptom_query, limit=8, offline=False):
    eff_offline = bool(offline or ota_sync.is_offline_env())
    cfg = load_config()
    router = load_router(cfg)
    edges = load_edges(cfg)
    q_fold = _normalize_query_synonyms(fold_ascii(symptom_query))
    q_tokens = [t for t in q_fold.split() if t]

    symptom_map = router.get("symptom_map", {})
    node_scores = {}
    matched_symptoms = []
    for sym_key, nids in symptom_map.items():
        sf = fold_ascii(sym_key)
        if q_fold and (q_fold in sf or sf in q_fold or (q_tokens and all(t in sf for t in q_tokens))):
            if sym_key not in matched_symptoms:
                matched_symptoms.append(sym_key)
            for nid in nids:
                node_scores[nid] = node_scores.get(nid, 0) + 120

    for inc_re, exc_re, alias_keys in _DIAGNOSE_SYMPTOM_ALIASES:
        if q_fold and inc_re.search(q_fold) and (exc_re is None or not exc_re.search(q_fold)):
            for sym_key in alias_keys:
                if sym_key in symptom_map and sym_key not in matched_symptoms:
                    matched_symptoms.append(sym_key)
                    for nid in symptom_map[sym_key]:
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
                "node": compact_node_hit(n, cfg, node_scores[nid], offline=eff_offline),
                "actionable_edges": rel_edges[:6],
            }
        )

    if len(recommendations) == 0 and len(matched_symptoms) == 0:
        return {
            "ok": False,
            "command": "diagnose",
            "offline": eff_offline,
            "symptom_query": to_text(symptom_query),
            "error": "No matching symptoms or circuit cards found for query.",
            "matched_symptom_tags": [],
            "recommended_checklists": [],
            "recommendations": [],
        }

    return {
        "ok": True,
        "command": "diagnose",
        "offline": eff_offline,
        "symptom_query": to_text(symptom_query),
        "matched_symptom_tags": sorted(matched_symptoms),
        "recommended_checklists": checklist_set,
        "recommendations": recommendations,
    }


def cmd_chapter(chapter_arg, offline=False):
    eff_offline = bool(offline or ota_sync.is_offline_env())
    cfg = load_config()
    base_url = get_base_url(cfg)
    router = load_router(cfg)
    coords = load_coordinates(cfg)
    m = re.search(r"(\d+)", to_text(chapter_arg))
    if not m:
        return {"ok": False, "command": "chapter", "offline": eff_offline, "error": "Invalid chapter number: " + to_text(chapter_arg)}
    ch_num = int(m.group(1))
    if ch_num < 1 or ch_num > 19:
        return {"ok": False, "command": "chapter", "offline": eff_offline, "error": "Chapter must be between 1 and 19"}

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
        compact_node_hit(n, cfg, offline=eff_offline)
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
        "offline": eff_offline,
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


def cmd_checklist(name_arg, offline=False):
    eff_offline = bool(offline or ota_sync.is_offline_env())
    cfg = load_config()
    router = load_router(cfg)
    if not name_arg or to_text(name_arg).strip().lower() in ("list", "all"):
        return {
            "ok": True,
            "command": "checklist",
            "offline": eff_offline,
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
            "offline": eff_offline,
            "error": "Checklist not found: " + clean,
            "available": [c.get("checklist_id") for c in router.get("checklists", [])],
        }

    data = load_json_file(direct_path)
    return {
        "ok": True,
        "command": "checklist",
        "offline": eff_offline,
        "checklist": data,
    }


def cmd_term(query_str, limit=12, offline=False):
    eff_offline = bool(offline or ota_sync.is_offline_env())
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
        "offline": eff_offline,
        "query": q_raw,
        "total_matches": len(scored),
        "results": results,
    }


def cmd_domain(domain_arg, offline=False):
    eff_offline = bool(offline or ota_sync.is_offline_env())
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
            "offline": eff_offline,
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
            "offline": eff_offline,
            "error": "Unknown domain: " + to_text(domain_arg),
            "available": [d.get("id") for d in domains],
        }
    did = chosen.get("id")
    matched = [compact_node_hit(n, cfg, offline=eff_offline) for n in nodes if n.get("domain") == did]
    return {
        "ok": True,
        "command": "domain",
        "offline": eff_offline,
        "domain": chosen,
        "node_count": len(matched),
        "nodes": matched,
    }


_RECIPE_STOPWORDS = set([
    "a", "an", "the", "of", "in", "on", "to", "for", "with",
    "and", "or", "by", "at", "from", "is", "are",
])


_FLAVOR_TO_TECHSWEEP = {
    "core_1v": "core",
    "io_2v5": "io",
    "core_1v_svt": "core",
    "core_1v_lvt": "lvt",
    "core_1v_hvt": "hvt",
    "io_1v8": "io",
}


_SUPPORTED_PDK_45_RE = re.compile(
    r"\b(gpdk045|gpdk045_\w*|gpdk\s*45|45\s*nm|g45|g45[np]\d\w*)\b",
    re.IGNORECASE,
)
_SUPPORTED_PDK_90_RE = re.compile(
    r"\b(gpdk090|gpdk090_\w*|gpdk\s*90|90\s*nm|g90)\b",
    re.IGNORECASE,
)
_UNSUPPORTED_PDK_RE = re.compile(
    r"\b(gpdk\s*\d+\w*|tsmc\s*\d*\w*|skywater(?:\s*\d+\w*)?|sky\s*\d+\w*|gf\s*\d+\w*|"
    r"umc\s*\d*\w*|smic\s*\d*\w*|ihp\s*\d*\w*|asap\s*\d+\w*|freepdk\s*\d*\w*|"
    r"samsung\s*\d*\w*|tower\s*\d*\w*|\d+\s*nm|0\.\d+\s*u(?:m)?)\b",
    re.IGNORECASE,
)


def _infer_recipe_lut_params(circuit_query):
    """Infer PDK, flavor, corner, temperature tag, device, L, Vds matching gpdk_techsweep.py."""
    raw_txt = to_text(circuit_query)
    q_low = raw_txt.lower()
    q_fold = fold_ascii(raw_txt)

    has_45 = bool(_SUPPORTED_PDK_45_RE.search(raw_txt))
    has_90 = bool(_SUPPORTED_PDK_90_RE.search(raw_txt))
    stripped_sup = _SUPPORTED_PDK_90_RE.sub(" ", _SUPPORTED_PDK_45_RE.sub(" ", raw_txt))
    m_unsup = _UNSUPPORTED_PDK_RE.search(stripped_sup)

    has_pmos = bool(re.search(r"\b(pmos|pfet)\b", q_fold))
    has_nmos = bool(re.search(r"\b(nmos|nfet)\b", q_fold))
    dev_type = "pmos" if (has_pmos and not has_nmos) else "nmos"

    if m_unsup is not None:
        return {
            "pdk_supported": False,
            "pdk_inferred_default": False,
            "requested_pdk": m_unsup.group(0).strip(),
            "supported_pdks": ["gpdk045", "gpdk090"],
            "pdk": None,
            "flavor": None,
            "techsweep_flavor": None,
            "corner": None,
            "temp_tag": None,
            "temp_c": None,
            "dev": dev_type,
            "l": None,
            "vds": None,
            "lut_path": None,
        }

    if has_45 and not has_90:
        pdk_key = "gpdk045"
        pdk_inferred_default = False
        requested_pdk = "gpdk045"
    elif has_90 and not has_45:
        pdk_key = "gpdk090"
        pdk_inferred_default = False
        requested_pdk = "gpdk090"
    elif has_45 and has_90:
        pdk_key = "gpdk045"
        pdk_inferred_default = False
        requested_pdk = "gpdk045"
    else:
        pdk_key = "gpdk090"
        pdk_inferred_default = True
        requested_pdk = None

    if pdk_key == "gpdk045":
        if re.search(r"\b(io|1v8|1\.8\s*v|io_?1v8|g45[np]2svt)\b", q_low):
            flavor_label = "io_1v8"
            l_arg = "240e-9"
            vds_arg = "0.9"
        elif re.search(r"\b(lvt|core_1v_lvt|g45[np]1lvt)\b", q_low):
            flavor_label = "core_1v_lvt"
            l_arg = "90e-9"
            vds_arg = "0.5"
        elif re.search(r"\b(hvt|core_1v_hvt|g45[np]1hvt)\b", q_low):
            flavor_label = "core_1v_hvt"
            l_arg = "90e-9"
            vds_arg = "0.5"
        else:
            flavor_label = "core_1v_svt"
            l_arg = "90e-9"
            vds_arg = "0.5"
    else:
        if re.search(r"\b(io|2v5|2\.5\s*v|io_?2v5|nmos2v|pmos2v)\b", q_low):
            flavor_label = "io_2v5"
            l_arg = "360e-9"
            vds_arg = "1.2"
        else:
            flavor_label = "core_1v"
            l_arg = "180e-9"
            vds_arg = "0.6"

    m_corner = re.search(r"\b(tt|nn|ss|ff|fs|sf)\b", q_fold)
    if pdk_key == "gpdk045":
        if m_corner:
            c_tok = m_corner.group(1).lower()
            corner = "tt" if c_tok == "nn" else c_tok
        else:
            corner = "tt"
    else:
        if m_corner:
            c_tok = m_corner.group(1).lower()
            corner = "NN" if c_tok in ("tt", "nn") else c_tok.upper()
        else:
            corner = "NN"

    temp_val = 27.0
    m_temp = re.search(u"(?<![a-z0-9])([+-]?\\d+(?:\\.\\d+)?)\\s*(?:deg\\s*c|\u00b0\\s*c|c)\\b", q_low)
    if m_temp:
        temp_val = float(m_temp.group(1))
    else:
        m_temp_m = re.search(r"(?<![a-z0-9])m(\d+(?:\.\d+)?)c\b", q_low)
        if m_temp_m:
            temp_val = -float(m_temp_m.group(1))
        else:
            m_temp_kw = re.search(r"(?<![a-z0-9])temp(?:erature)?\s*[:=]?\s*([+-]?\d+(?:\.\d+)?)\b", q_low)
            if m_temp_kw:
                temp_val = float(m_temp_kw.group(1))
    temp_tag = ("%g" % float(temp_val)).replace("-", "m").replace(".", "p")
    temp_c_num = int(temp_val) if temp_val == int(temp_val) else temp_val

    lut_filename = "%s_%s_%s_%sC.lut.json.gz" % (pdk_key, flavor_label, corner, temp_tag)
    lut_path = "~/.cache/skill-analog/gmid-luts/" + lut_filename
    return {
        "pdk_supported": True,
        "pdk_inferred_default": pdk_inferred_default,
        "requested_pdk": requested_pdk,
        "supported_pdks": ["gpdk045", "gpdk090"],
        "pdk": pdk_key,
        "flavor": flavor_label,
        "techsweep_flavor": _FLAVOR_TO_TECHSWEEP.get(flavor_label, "core"),
        "corner": corner,
        "temp_tag": temp_tag,
        "temp_c": temp_c_num,
        "dev": dev_type,
        "l": l_arg,
        "vds": vds_arg,
        "lut_path": lut_path,
    }


_STRIP_PVT_PATTERNS = (
    re.compile(u"(?<![a-z0-9])[+-]?\\d+(?:\\.\\d+)?\\s*(?:deg\\s*c|\u00b0\\s*c|c)\\b", re.IGNORECASE),
    re.compile(r"(?<![a-z0-9])m\d+(?:\.\d+)?c\b", re.IGNORECASE),
    _SUPPORTED_PDK_45_RE,
    _SUPPORTED_PDK_90_RE,
    _UNSUPPORTED_PDK_RE,
    re.compile(r"\b(core_1v_svt|core_1v_lvt|core_1v_hvt|core_1v|io_1v8|io_2v5|1v8|2v5|svt|lvt|hvt)\b", re.IGNORECASE),
    re.compile(r"\b(tt|nn|ss|ff|fs|sf)\b", re.IGNORECASE),
)


def _strip_recipe_pvt_qualifiers(circuit_query):
    """Strip PDK/flavor/corner/temperature qualifiers so topology search stays clean."""
    s = to_text(circuit_query)
    for pat in _STRIP_PVT_PATTERNS:
        s = pat.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def cmd_recipe(circuit_query, offline=False):
    eff_offline = bool(offline or ota_sync.is_offline_env())
    offline_tail = " --offline" if eff_offline else ""

    lut_info = _infer_recipe_lut_params(circuit_query)
    topo_query = _strip_recipe_pvt_qualifiers(circuit_query)
    eff_search_query = topo_query if topo_query else circuit_query
    search_res = cmd_search(eff_search_query, limit=6, offline=eff_offline)
    hits = search_res.get("results", [])

    qf_norm = _normalize_query_synonyms(fold_ascii(eff_search_query))
    q_tokens = [t for t in qf_norm.split() if t]
    meaningful_tokens = [t for t in q_tokens if len(t) >= 2 and t not in _RECIPE_STOPWORDS]

    valid_match = bool(hits)
    if valid_match and hits[0].get("score", 0) < 80:
        top_hay = fold_ascii(
            "%s %s %s %s"
            % (
                hits[0].get("id", ""),
                hits[0].get("title_en", ""),
                hits[0].get("title_vi", ""),
                hits[0].get("summary", ""),
            )
        )
        if not meaningful_tokens or not any(tok in top_hay for tok in meaningful_tokens):
            valid_match = False

    if not valid_match:
        return {
            "ok": False,
            "command": "recipe",
            "circuit_query": to_text(circuit_query),
            "offline": eff_offline,
            "error": "No matching circuit topology found for query.",
            "recommended_cards": [],
            "steps": [],
        }

    if eff_offline:
        for h in hits:
            h["fetch_cmd"] = _fmt_tool_cmd("kb_fetch.py", h["id"] + offline_tail)

    if not lut_info.get("pdk_supported", True):
        lut_exists = False
        warn_msg = (
            "Unsupported PDK/technology '%s' (built-in LUTs support gpdk045, gpdk090 only). "
            "Process-agnostic theory cards and checklists are returned; Stage 3 sizing commands omitted."
            % lut_info.get("requested_pdk")
        )
        lut_status = {
            "pdk_supported": False,
            "pdk_inferred_default": False,
            "requested_pdk": lut_info.get("requested_pdk"),
            "supported_pdks": list(lut_info.get("supported_pdks", ["gpdk045", "gpdk090"])),
            "lut_path": None,
            "resolved_path": None,
            "lut_exists": False,
            "ready": False,
            "pdk": None,
            "flavor": None,
            "corner": None,
            "temp_c": None,
            "generate_cmd": None,
            "warning": warn_msg,
        }
        stage3_dict = {
            "stage": 3,
            "name": "Physics-based gm/ID initial sizing (< 1 ms per transistor)",
            "sizing_available": False,
            "lut_ready": False,
            "prereq_cmds": [],
            "sizing_cmd": None,
            "cmds": [],
            "warning": warn_msg,
        }
    else:
        resolved_lut_path = os.path.expanduser(lut_info["lut_path"])
        lut_exists = os.path.isfile(resolved_lut_path)
        generate_cmd = _fmt_tool_cmd(
            "gpdk_techsweep.py",
            "--pdk %s --flavor %s --corner %s --temp %g --run --out %s"
            % (
                lut_info["pdk"],
                lut_info["techsweep_flavor"],
                lut_info["corner"],
                float(lut_info["temp_c"]),
                lut_info["lut_path"],
            ),
        )
        gmid_cmd = _fmt_tool_cmd(
            "gmid_lut.py",
            "size --lut %s --dev %s --gm 1e-3 --gm-id 15 --l %s --vds %s"
            % (lut_info["lut_path"], lut_info["dev"], lut_info["l"], lut_info["vds"]),
        )
        lut_status = {
            "pdk_supported": True,
            "pdk_inferred_default": bool(lut_info.get("pdk_inferred_default", False)),
            "requested_pdk": lut_info.get("requested_pdk"),
            "supported_pdks": list(lut_info.get("supported_pdks", ["gpdk045", "gpdk090"])),
            "lut_path": lut_info["lut_path"],
            "resolved_path": resolved_lut_path,
            "lut_exists": lut_exists,
            "ready": lut_exists,
            "pdk": lut_info["pdk"],
            "flavor": lut_info["flavor"],
            "corner": lut_info["corner"],
            "temp_c": lut_info["temp_c"],
            "generate_cmd": generate_cmd,
            "warning": (
                None
                if lut_exists
                else "Target LUT not found on disk; generate it with gpdk_techsweep.py before running gmid_lut.py."
            ),
        }
        stage3_dict = {
            "stage": 3,
            "name": "Physics-based gm/ID initial sizing (< 1 ms per transistor)",
            "sizing_available": True,
            "lut_ready": lut_exists,
            "prereq_cmds": ([] if lut_exists else [generate_cmd]),
            "sizing_cmd": gmid_cmd,
            "cmds": ([gmid_cmd] if lut_exists else [generate_cmd, gmid_cmd]),
        }

    qf = _normalize_query_synonyms(fold_ascii(circuit_query))
    is_ldo_query = bool(re.search(r"\b(ldo|capless|capacitorless)\b", qf))
    checklists = ["common-mos"]
    if is_ldo_query:
        checklists.append("ldo-regulator")

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

    is_pll_clock = bool(re.search(r"\b(pll|pfd|vco|cdr|dll|synthesizer|phase|jitter)\b", qf))
    if is_pll_clock:
        is_switching_pmic = bool(re.search(r"\b(buck|boost|dcdc|dc\s+dc|pwm|cot|cmc|vmc)\b", qf))
    else:
        is_switching_pmic = bool(re.search(r"\b(buck|boost|dcdc|dc\s+dc|pwm|charge\s+pump|cot|cmc|vmc)\b", qf))
    va_path = os.path.join(LIBRARY_ROOT, "models", "veriloga", "pwm_switch_avg_ccm_dcm.va")
    veriloga_note = (
        "%s (use for 0.3s .dc/.ac/.stb before transistor pss+pstb)" % va_path
        if is_switching_pmic
        else None
    )
    primary_cl = checklists[1] if len(checklists) > 1 else "common-mos"
    steps = [
        {
            "stage": 1,
            "name": "Locate project & fetch primary Razavi/PMIC/AMS cards + checklists",
            "cmds": [
                _fmt_tool_cmd("analogctl.py", "locate"),
                _fmt_tool_cmd("kb_fetch.py", hits[0]["id"] + offline_tail),
                _fmt_tool_cmd("kb_lookup.py", "checklist " + primary_cl + offline_tail),
            ],
        },
        {
            "stage": 2,
            "name": "Decompose multi-block hierarchy & interface contracts in project.json / spec.json",
            "cmds": [
                _fmt_tool_cmd("kb_fetch.py", "tech-hierarchical-chip-spec-budgeting-and-interfaces" + offline_tail),
            ],
        },
        stage3_dict,
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
                _fmt_tool_cmd("psf_audit.py", "op-audit ./sim/runs/run_01/psf --vds-margin 0.05 --fail-on-violation"),
                _fmt_tool_cmd("psf_audit.py", "metrics ./sim/runs/run_01/psf --spec ./spec.json --fail-on-spec"),
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
                _fmt_tool_cmd("kb_lookup.py", "checklist layout-and-matching" + offline_tail),
                _fmt_tool_cmd("kb_lookup.py", "checklist closed-loop-sizing-and-signoff" + offline_tail),
            ],
        },
    ]
    return {
        "ok": True,
        "command": "recipe",
        "circuit_query": to_text(circuit_query),
        "offline": eff_offline,
        "recipe_ready": lut_exists,
        "lut_status": lut_status,
        "switching_converter_veriloga_helper": veriloga_note,
        "recommended_cards": hits,
        "theory_cards": [c.get("id") for c in theory_cards],
        "skill_playbooks": [c.get("id") for c in skill_cards],
        "mandatory_checklists": checklists,
        "closed_loop_7_stages": steps,
    }


HELP_TEXT = """Usage: python tools/kb_lookup.py COMMAND [ARGUMENTS] [--limit N] [--offline]

Commands:
  status               Show KB release (2026.11.19.1), 10-domain counts, GitHub URLs & OTA sync status
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
    import shutil
    import tempfile

    saved_env = os.environ.get("SKILL_ANALOG_OFFLINE")
    tmp_home = tempfile.mkdtemp(prefix="kb_lookup_test_")
    orig_expanduser = os.path.expanduser
    orig_auto_sync = ota_sync.maybe_auto_sync
    orig_write_json = globals()["write_utf8_json"]
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

        # 5. Recipe Stage 3 & Stage 5 canonical LUT readiness (isolated empty cache -> not ready)
        if "SKILL_ANALOG_OFFLINE" in os.environ:
            del os.environ["SKILL_ANALOG_OFFLINE"]

        def _fake_expanduser(p):
            txt = to_text(p)
            if txt.startswith("~/") or txt.startswith("~\\"):
                return os.path.join(tmp_home, txt[2:].replace("/", os.sep))
            return orig_expanduser(p)

        os.path.expanduser = _fake_expanduser
        rec = cmd_recipe("folded cascode")
        rec_blob = json.dumps(rec)
        st3_fc = rec["closed_loop_7_stages"][2]
        if not rec.get("ok") or rec.get("offline") is not False:
            raise AssertionError("cmd_recipe('folded cascode') expected ok=True, offline=False: %r" % rec)
        if rec.get("recipe_ready") is not False or st3_fc.get("lut_ready") is not False:
            raise AssertionError("Expected recipe_ready=False when LUT missing on disk: %r" % rec.get("lut_status"))
        if "gpdk090_core_1v_NN_27C.lut.json.gz" not in rec_blob or "--fail-on-violation" not in rec_blob or "--fail-on-spec" not in rec_blob:
            raise AssertionError("cmd_recipe missing canonical LUT or fail-closed psf_audit flags: %r" % rec)
        if "--offline" in rec_blob:
            raise AssertionError("Online cmd_recipe must NOT emit --offline flags: %r" % rec)
        if len(st3_fc.get("cmds", [])) != 2 or "gpdk_techsweep.py" not in st3_fc["cmds"][0] or "gmid_lut.py" not in st3_fc["cmds"][1]:
            raise AssertionError("Expected prereq gpdk_techsweep.py before gmid_lut.py in Stage 3 cmds: %r" % st3_fc)
        if st3_fc.get("prereq_cmds") != [st3_fc["cmds"][0]] or st3_fc.get("sizing_cmd") != st3_fc["cmds"][1]:
            raise AssertionError("Stage 3 prereq_cmds/sizing_cmd mismatch: %r" % st3_fc)

        # 6. Dynamic PDK/Flavor/Corner/Temp/Device LUT generation (GPDK045) + LUT present vs missing
        rec_ldo45 = cmd_recipe("capless LDO GPDK045")
        st3_ldo45 = rec_ldo45["closed_loop_7_stages"][2]
        if (
            not rec_ldo45.get("ok")
            or "gpdk045_core_1v_svt_tt_27C.lut.json.gz" not in st3_ldo45["sizing_cmd"]
            or "--l 90e-9 --vds 0.5" not in st3_ldo45["sizing_cmd"]
        ):
            raise AssertionError("Unexpected GPDK045 capless LDO LUT cmd: %r" % st3_ldo45)

        rec_cm45 = cmd_recipe("NMOS current mirror GPDK045 SS 125 C")
        st3_cm45 = rec_cm45["closed_loop_7_stages"][2]
        if (
            not rec_cm45.get("ok")
            or rec_cm45.get("recipe_ready") is not False
            or "gpdk045_core_1v_svt_ss_125C.lut.json.gz" not in st3_cm45["sizing_cmd"]
            or "--dev nmos" not in st3_cm45["sizing_cmd"]
            or "--flavor core" not in st3_cm45["prereq_cmds"][0]
            or "--temp 125" not in st3_cm45["prereq_cmds"][0]
        ):
            raise AssertionError("Unexpected GPDK045 SS 125C LUT stage 3: %r" % st3_cm45)

        rec_pmos45 = cmd_recipe("PMOS current mirror GPDK045 FF -40C")
        st3_pmos45 = rec_pmos45["closed_loop_7_stages"][2]
        if (
            not rec_pmos45.get("ok")
            or "gpdk045_core_1v_svt_ff_m40C.lut.json.gz" not in st3_pmos45["sizing_cmd"]
            or "--dev pmos" not in st3_pmos45["sizing_cmd"]
            or "--temp -40" not in st3_pmos45["prereq_cmds"][0]
        ):
            raise AssertionError("Unexpected GPDK045 PMOS FF -40C LUT stage 3: %r" % st3_pmos45)

        # Verify recipe_ready=True when LUT file exists on disk
        dummy_lut = _fake_expanduser(rec_pmos45["lut_status"]["lut_path"])
        ota_sync.mkdir_p(os.path.dirname(dummy_lut))
        ota_sync.write_atomic_bytes(dummy_lut, b"DUMMY_LUT")
        rec_ready = cmd_recipe("PMOS current mirror GPDK045 FF -40C")
        st3_ready = rec_ready["closed_loop_7_stages"][2]
        if (
            rec_ready.get("recipe_ready") is not True
            or rec_ready["lut_status"].get("lut_exists") is not True
            or rec_ready["lut_status"].get("warning") is not None
            or st3_ready.get("lut_ready") is not True
            or st3_ready.get("prereq_cmds") != []
            or st3_ready.get("cmds") != [st3_ready.get("sizing_cmd")]
        ):
            raise AssertionError("Expected recipe_ready=True and no prereq when LUT exists: %r" % rec_ready["lut_status"])

        # 7. Synonym normalization: capacitorless LDO leads with Capless LDO card & ldo-regulator checklist (never DC-DC)
        rec_capless = cmd_recipe("capacitorless LDO")
        if not rec_capless.get("ok") or rec_capless["recommended_cards"][0]["id"] != "topo-capless-ldo-fvf-ahuja-dfc-and-sre":
            raise AssertionError("capacitorless LDO failed to route to Capless LDO card: %r" % rec_capless.get("recommended_cards"))
        if rec_capless["mandatory_checklists"][1] != "ldo-regulator":
            raise AssertionError("capacitorless LDO must prioritize ldo-regulator checklist: %r" % rec_capless.get("mandatory_checklists"))
        if rec_capless.get("switching_converter_veriloga_helper") is not None:
            raise AssertionError("capacitorless LDO must not attach DC-DC Verilog-A helper: %r" % rec_capless)

        # 8. Charge pump PLL routing: NOT switching PMIC, boosts PLL cards over DC-DC charge-pump
        rec_cppll = cmd_recipe("charge pump PLL")
        top2_pll = [c["id"] for c in rec_cppll.get("recommended_cards", [])[:2]]
        if not rec_cppll.get("ok") or rec_cppll.get("switching_converter_veriloga_helper") is not None:
            raise AssertionError("charge pump PLL must NOT trigger switching PMIC Verilog-A helper: %r" % rec_cppll)
        if "topo-charge-pump-type2-pll" not in top2_pll or "topo-pfd-deadzone-and-charge-pump-nonidealities" not in top2_pll:
            raise AssertionError("charge pump PLL must rank PLL CP/PFD cards at top: %r" % top2_pll)

        # 9. Gibberish rejection: unknown query returns ok=False, recommended_cards=[], steps=[]
        rec_gib = cmd_recipe("xyzzy nonexistent topology 12345")
        if rec_gib.get("ok") is not False or rec_gib.get("recommended_cards") != [] or rec_gib.get("steps") != []:
            raise AssertionError("Gibberish query must fail closed with ok=False and empty cards/steps: %r" % rec_gib)

        # 10. --offline propagation via explicit offline=True and SKILL_ANALOG_OFFLINE=1
        for mode_label, use_env in (("explicit", False), ("env", True)):
            if use_env:
                os.environ["SKILL_ANALOG_OFFLINE"] = "1"
                rec_off = cmd_recipe("capless LDO GPDK045")
            else:
                if "SKILL_ANALOG_OFFLINE" in os.environ:
                    del os.environ["SKILL_ANALOG_OFFLINE"]
                rec_off = cmd_recipe("capless LDO GPDK045", offline=True)
            if not rec_off.get("ok") or rec_off.get("offline") is not True:
                raise AssertionError("Offline recipe (%s) missing offline=True: %r" % (mode_label, rec_off))
            for stg in rec_off.get("closed_loop_7_stages", []):
                for cmd_s in stg.get("cmds", []):
                    if ("kb_fetch.py" in cmd_s or "kb_lookup.py" in cmd_s) and "--offline" not in cmd_s:
                        raise AssertionError("Offline recipe (%s) missing --offline in cmd: %r" % (mode_label, cmd_s))
            for card in rec_off.get("recommended_cards", []):
                if "--offline" not in card.get("fetch_cmd", ""):
                    raise AssertionError("Offline recipe (%s) missing --offline in fetch_cmd: %r" % (mode_label, card))

        if "SKILL_ANALOG_OFFLINE" in os.environ:
            del os.environ["SKILL_ANALOG_OFFLINE"]

        # 11. Finding #11 rankings, Vietnamese aliases, and diagnose symptom tags
        sr_dp = cmd_search(u"bo khu\u1ebfch \u0111\u1ea1i vi sai t\u1ea3i g\u01b0\u01a1ng d\u00f2ng", limit=5)
        if [x["id"] for x in sr_dp.get("results", [])[:3]] != [
            "topo-diff-pair-active-current-mirror-load",
            "concept-diffpair-mirror-pole-doublet",
            "topo-five-transistor-ota",
        ]:
            raise AssertionError("Diff-pair active current mirror ranking failed: %r" % [x["id"] for x in sr_dp.get("results", [])[:5]])

        sr_gb = cmd_search("gain boosted cascode", limit=5)
        if [x["id"] for x in sr_gb.get("results", [])[:3]] != [
            "topo-gain-boosted-cascode",
            "topo-regulated-cascode-super-source-follower",
            "skill-folded-cascode-and-gainboost-sizing-flow",
        ]:
            raise AssertionError("Gain-boosted cascode ranking failed: %r" % [x["id"] for x in sr_gb.get("results", [])[:5]])

        rec_tel = cmd_recipe("PMOS telescopic opamp GPDK090 FF -40C")
        if (
            not rec_tel.get("ok")
            or rec_tel["recommended_cards"][0]["id"] != "topo-telescopic-cascode-opamp"
            or "gpdk090_core_1v_FF_m40C.lut.json.gz" not in rec_tel["lut_status"]["lut_path"]
            or "--dev pmos" not in rec_tel["closed_loop_7_stages"][2]["sizing_cmd"]
        ):
            raise AssertionError("PMOS telescopic opamp recipe ranking/LUT failed: %r" % rec_tel)

        sr_sub = cmd_search("chong dao dong song hai duoi", limit=5)
        if [x["id"] for x in sr_sub.get("results", [])[:3]] != [
            "tech-dcdc-cmc-subharmonic-slope-comp-and-cot",
            "concept-diffpair-mirror-pole-doublet",
            "topo-dcdc-ramp-sensefet-dcr-and-zcd-blocks",
        ]:
            raise AssertionError("Subharmonic Vietnamese alias search failed: %r" % [x["id"] for x in sr_sub.get("results", [])[:5]])

        sr_dbl = cmd_search(u"s\u00f3ng hai \u0111u\u00f4i", limit=5)
        if [x["id"] for x in sr_dbl.get("results", [])[:3]] != [
            "concept-diffpair-mirror-pole-doublet",
            "topo-diff-pair-active-current-mirror-load",
            "tech-dcdc-cmc-subharmonic-slope-comp-and-cot",
        ]:
            raise AssertionError("Doublet Vietnamese alias search failed: %r" % [x["id"] for x in sr_dbl.get("results", [])[:5]])

        dg_sub = cmd_diagnose("chong dao dong song hai duoi", limit=5)
        if (
            not dg_sub.get("ok")
            or "period-doubling-subharmonic-alternating-wide-narrow-pwm-pulses-when-duty-cycle-exceeds-50-percent" not in dg_sub.get("matched_symptom_tags", [])
            or dg_sub["recommendations"][0]["node"]["id"] != "tech-dcdc-cmc-subharmonic-slope-comp-and-cot"
        ):
            raise AssertionError("Diagnose Vietnamese subharmonic failed: %r" % dg_sub)

        for v_sym in (u"s\u00f3ng hai \u0111u\u00f4i", "cap cuc zero", "duoi xac lap"):
            dg_v = cmd_diagnose(v_sym, limit=5)
            if not dg_v.get("ok") or "slow-settling-tail-from-pole-zero-doublet" not in dg_v.get("matched_symptom_tags", []):
                raise AssertionError("Diagnose Vietnamese doublet alias %r failed: %r" % (v_sym, dg_v))

        # 12. Finding #12: Gibberish CLI exit 1 + ZERO maybe_auto_sync calls + --offline propagation + quoted --offline
        sync_calls = []
        captured_payloads = []

        def _spy_auto_sync(**kwargs):
            sync_calls.append(kwargs)
            return {"ok": True, "action": "noop_spy"}

        def _capture_json(obj):
            captured_payloads.append(obj)

        ota_sync.maybe_auto_sync = _spy_auto_sync
        globals()["write_utf8_json"] = _capture_json

        for gib_argv in (
            ["search", "xyzzy qwerty blarg 9999"],
            ["diagnose", "xyzzy qwerty blarg 9999"],
            ["recipe", "xyzzy qwerty blarg 9999"],
        ):
            del sync_calls[:]
            del captured_payloads[:]
            rc_gib = main(gib_argv)
            if rc_gib != 1 or len(sync_calls) != 0 or not captured_payloads or captured_payloads[0].get("ok") is not False:
                raise AssertionError("Gibberish CLI %r must exit 1, ok=False, 0 sync calls: rc=%r sync=%r pay=%r" % (gib_argv, rc_gib, sync_calls, captured_payloads))

        # search --offline and diagnose --offline carry --offline in every fetch_cmd and offline=True
        for off_argv in (["search", "buck", "--offline"], ["diagnose", "rhp zero", "--offline"]):
            del sync_calls[:]
            del captured_payloads[:]
            rc_off = main(off_argv)
            if rc_off != 0 or len(sync_calls) != 0 or not captured_payloads or captured_payloads[0].get("offline") is not True:
                raise AssertionError("Offline CLI %r failed: rc=%r sync=%r pay=%r" % (off_argv, rc_off, sync_calls, captured_payloads))
            items = captured_payloads[0].get("results") if off_argv[0] == "search" else [r.get("node", {}) for r in captured_payloads[0].get("recommendations", [])]
            if not items or any("--offline" not in it.get("fetch_cmd", "") for it in items):
                raise AssertionError("Offline CLI %r missing --offline in fetch_cmd: %r" % (off_argv, items))

        # Quoted --offline inside recipe query arg
        del sync_calls[:]
        del captured_payloads[:]
        rc_qoff = main(["recipe", "capacitorless LDO --offline"])
        if (
            rc_qoff != 0
            or len(sync_calls) != 0
            or not captured_payloads
            or captured_payloads[0].get("offline") is not True
            or captured_payloads[0].get("circuit_query") != "capacitorless LDO"
            or "--offline" not in captured_payloads[0]["recommended_cards"][0]["fetch_cmd"]
            or "--offline" not in captured_payloads[0]["closed_loop_7_stages"][0]["cmds"][1]
        ):
            raise AssertionError("Quoted --offline failed: rc=%r sync=%r pay=%r" % (rc_qoff, sync_calls, captured_payloads))

        # --sync + quoted --offline -> exit code 2
        rc_qsync = main(["--sync", "foo --offline", "--quiet-errors"])
        if rc_qsync != 2:
            raise AssertionError("Expected exit 2 for --sync with quoted --offline, got %s" % rc_qsync)

        # Valid online search calls maybe_auto_sync AFTER local lookup (1 call)
        del sync_calls[:]
        del captured_payloads[:]
        rc_on = main(["search", "buck"])
        if rc_on != 0 or len(sync_calls) != 1 or not captured_payloads or captured_payloads[0].get("ok") is not True:
            raise AssertionError("Valid online search did not invoke post-lookup maybe_auto_sync cleanly: rc=%r sync=%r" % (rc_on, sync_calls))

        # 13. Finding #08 + BGR+capless LDO: Unsupported PDKs fail closed in Stage 3 & BGR+capless LDO hits both cards
        for u_query, u_tok, top_card in (
            ("capless LDO GPDK777", "GPDK777", "topo-capless-ldo-fvf-ahuja-dfc-and-sre"),
            ("gain boosted cascode 65nm", "65nm", "topo-gain-boosted-cascode"),
            ("bandgap tsmc28", "tsmc28", "topo-bandgap-reference-core"),
        ):
            rec_u = cmd_recipe(u_query, offline=True)
            st3_u = rec_u.get("closed_loop_7_stages", [{}, {}, {}])[2]
            lut_st_u = rec_u.get("lut_status", {})
            if (
                not rec_u.get("ok")
                or rec_u.get("recipe_ready") is not False
                or rec_u["recommended_cards"][0]["id"] != top_card
                or lut_st_u.get("pdk_supported") is not False
                or lut_st_u.get("requested_pdk") != u_tok
                or lut_st_u.get("lut_path") is not None
                or lut_st_u.get("generate_cmd") is not None
                or st3_u.get("sizing_available") is not False
                or st3_u.get("lut_ready") is not False
                or st3_u.get("prereq_cmds") != []
                or st3_u.get("sizing_cmd") is not None
                or st3_u.get("cmds") != []
                or "gpdk090_" in json.dumps(rec_u)
            ):
                raise AssertionError("Unsupported PDK %r leaked gpdk090 or failed Stage 3 gate: %r" % (u_query, rec_u))

        rec_bgr_ldo = cmd_recipe("BGR + capless LDO", offline=True)
        bgr_ldo_ids = [c["id"] for c in rec_bgr_ldo.get("recommended_cards", [])]
        if (
            not rec_bgr_ldo.get("ok")
            or "topo-capless-ldo-fvf-ahuja-dfc-and-sre" not in bgr_ldo_ids
            or "topo-bandgap-reference-core" not in bgr_ldo_ids
            or "ldo-regulator" not in rec_bgr_ldo.get("mandatory_checklists", [])
            or "bandgap-and-bias" not in rec_bgr_ldo.get("mandatory_checklists", [])
        ):
            raise AssertionError("BGR + capless LDO failed to surface both Capless LDO & Bandgap cards/checklists: %r" % rec_bgr_ldo)

        return {
            "ok": True,
            "command": "self-test",
            "release": ota_sync.RELEASE_VERSION,
            "lookup_ms": dt_ms,
            "tests_passed": 15,
        }
    finally:
        os.path.expanduser = orig_expanduser
        ota_sync.maybe_auto_sync = orig_auto_sync
        globals()["write_utf8_json"] = orig_write_json
        shutil.rmtree(tmp_home, ignore_errors=True)
        if saved_env is None:
            if "SKILL_ANALOG_OFFLINE" in os.environ:
                del os.environ["SKILL_ANALOG_OFFLINE"]
        else:
            os.environ["SKILL_ANALOG_OFFLINE"] = saved_env


_INLINE_OFFLINE_RE = re.compile(r"(?:^|\s)--offline(?=\s|$)")


def _strip_inline_offline(raw_val):
    txt = to_text(raw_val)
    if not _INLINE_OFFLINE_RE.search(txt):
        return txt, False
    stripped = _WS_RE.sub(" ", _INLINE_OFFLINE_RE.sub(" ", txt)).strip()
    return stripped, True


def _dispatch_lookup_command(cmd, rest, cleaned, limit, eff_offline):
    if cmd == "status":
        return cmd_status(offline=eff_offline)
    if cmd in ("domain", "domains"):
        return cmd_domain(rest, offline=eff_offline)
    if cmd in ("recipe", "workflow", "plan"):
        if not rest:
            raise ValueError("recipe requires a circuit query (e.g., 'buck', 'capless ldo', 'folded cascode')")
        return cmd_recipe(rest, offline=eff_offline)
    if cmd == "search":
        if not rest:
            raise ValueError("search requires a query string")
        return cmd_search(rest, limit=limit, offline=eff_offline)
    if cmd in ("coord", "coords", "coordinate", "coordinates"):
        if not rest:
            raise ValueError("coord requires a section, equation, page, or index query")
        return cmd_coord(rest, limit=limit, offline=eff_offline)
    if cmd in ("skills", "skill", "github-skills"):
        return cmd_skills(rest, limit=limit, offline=eff_offline)
    if cmd in ("stage", "stages"):
        return cmd_stage(rest, limit=max(limit, 25), offline=eff_offline)
    if cmd == "node":
        if not rest:
            raise ValueError("node requires a node_id")
        return cmd_node(rest, offline=eff_offline)
    if cmd in ("upgrades", "upgrade"):
        if not rest:
            raise ValueError("upgrades requires a node_id")
        return cmd_upgrades(rest, offline=eff_offline)
    if cmd == "diagnose":
        if not rest:
            raise ValueError("diagnose requires a symptom query")
        return cmd_diagnose(rest, limit=limit, offline=eff_offline)
    if cmd == "chapter":
        if not rest:
            raise ValueError("chapter requires a chapter number (1..19)")
        return cmd_chapter(rest, offline=eff_offline)
    if cmd in ("checklist", "checklists"):
        return cmd_checklist(rest, offline=eff_offline)
    if cmd in ("term", "terms", "glossary"):
        if not rest:
            raise ValueError("term requires a query string or T-code")
        return cmd_term(rest, limit=limit, offline=eff_offline)
    return cmd_search(" ".join(cleaned), limit=limit, offline=eff_offline)


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
            val_s, had_off = _strip_inline_offline(args[i + 1])
            if had_off:
                offline_flag = True
            if val_s:
                cleaned.append(val_s)
            i += 2
        elif tok in ("--coord", "--coordinate") and i + 1 < len(args):
            flag_cmd = "coord"
            val_s, had_off = _strip_inline_offline(args[i + 1])
            if had_off:
                offline_flag = True
            if val_s:
                cleaned.append(val_s)
            i += 2
        elif tok in ("--skills", "--skill") and i + 1 < len(args):
            flag_cmd = "skills"
            val_s, had_off = _strip_inline_offline(args[i + 1])
            if had_off:
                offline_flag = True
            if val_s:
                cleaned.append(val_s)
            i += 2
        elif tok in ("--stage",) and i + 1 < len(args):
            flag_cmd = "stage"
            val_s, had_off = _strip_inline_offline(args[i + 1])
            if had_off:
                offline_flag = True
            if val_s:
                cleaned.append(val_s)
            i += 2
        elif tok in ("--symptom", "--goal") and i + 1 < len(args):
            flag_cmd = "diagnose"
            val_s, had_off = _strip_inline_offline(args[i + 1])
            if had_off:
                offline_flag = True
            if val_s:
                cleaned.append(val_s)
            i += 2
        elif tok == "--chapter" and i + 1 < len(args):
            flag_cmd = "chapter"
            val_s, had_off = _strip_inline_offline(args[i + 1])
            if had_off:
                offline_flag = True
            if val_s:
                cleaned.append(val_s)
            i += 2
        elif tok in ("--json", "--text"):
            i += 1
        else:
            val_s, had_off = _strip_inline_offline(tok)
            if had_off:
                offline_flag = True
            if val_s:
                cleaned.append(val_s)
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

    try:
        payload = _dispatch_lookup_command(cmd, rest, cleaned, limit, eff_offline)
        if (not eff_offline) and (cmd == "status" or payload.get("ok") is True):
            sync_res = ota_sync.maybe_auto_sync(
                ttl_sec=60,
                offline=eff_offline,
                library_root=LIBRARY_ROOT,
                base_url_override=base_url_override,
            )
            if isinstance(sync_res, dict) and sync_res.get("action") in ("synced", "updated"):
                payload = _dispatch_lookup_command(cmd, rest, cleaned, limit, eff_offline)

        write_utf8_json(payload)
        return 0 if payload.get("ok") else 1
    except Exception as exc:
        if not quiet_errors:
            write_utf8_json({"ok": False, "command": cmd, "error": str(exc)})
        return 2


if __name__ == "__main__":
    sys.exit(main())
