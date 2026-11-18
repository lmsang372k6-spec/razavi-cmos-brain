#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Spectre 15.1 Strict Fail-Closed Operating-Point Auditor & Spec Metrics Sign-Off Engine.

100% Python 2.6.6+ and Python 3 standard-library compatible (`optparse` CLI, zero external deps).

Subcommands:
  op-audit  <run_or_psf_path> [--vds-margin 0.05] [--expect-triode M_R1,M_SW] [--fail-on-violation]
  metrics   <run_dir> [--spec spec.json] [--fail-on-spec]
  self-test (or --self-test)
"""
from __future__ import print_function

import json
import math
import os
from optparse import OptionParser
import re
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True

_TOOLS_DIR = os.path.dirname(os.path.realpath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

from psf_ascii_reader import parse_psf_file  # noqa: E402

try:
    TEXT_TYPES = (basestring,)  # noqa: F821
except NameError:
    TEXT_TYPES = (str,)

REGION_NAMES = {
    0: "cutoff",
    1: "triode",
    2: "saturation",
    3: "subthreshold",
    4: "breakdown",
}

MOS_MODEL_HINTS = (
    "bsim", "mos", "nmos", "pmos", "nch", "pch", "psp", "ekv", "hisim",
    "utsoi", "g45n", "g45p", "gpdk090_nmos", "gpdk090_pmos", "nfet", "pfet",
)

MOS_FIELD_ALIASES = {
    "ids": ("ids", "id", "idrain", "i_d"),
    "vgs": ("vgs",),
    "vds": ("vds",),
    "vbs": ("vbs",),
    "vth": ("vth", "vt", "vto"),
    "vdsat": ("vdsat", "vdssat"),
    "gm": ("gm",),
    "gds": ("gds", "go"),
    "gmb": ("gmb", "gmbs"),
    "cgg": ("cgg", "cggbo"),
    "cgd": ("cgd", "cgdbo"),
    "cgs": ("cgs", "cgsbo"),
    "region": ("region",),
}

# Case-sensitive overrides checked before lowercasing (e.g. Mohm=1e6 vs mohm=1e-3, MW=1e6 vs mW=1e-3)
UNIT_SCALE_CASE_SENSITIVE = {
    "Mohm": 1e6,
    "Mohms": 1e6,
    "MOhm": 1e6,
    "MOhms": 1e6,
    "MW": 1e6,
    "MA": 1e6,
    "MV": 1e6,
    "mHz": 1e-3,
}

UNIT_SCALE_TO_SI = {
    "": 1.0,
    # Frequency
    "hz": 1.0, "khz": 1e3, "mhz": 1e6, "ghz": 1e9, "thz": 1e12,
    # Time
    "s": 1.0, "sec": 1.0, "secs": 1.0, "second": 1.0, "seconds": 1.0,
    "ms": 1e-3, "us": 1e-6, "ns": 1e-9, "ps": 1e-12, "fs": 1e-15,
    # Power
    "w": 1.0, "kw": 1e3, "mw": 1e-3, "uw": 1e-6, "nw": 1e-9, "pw": 1e-12, "fw": 1e-15,
    # Voltage (DC, RMS, peak-to-peak)
    "v": 1.0, "kv": 1e3, "mv": 1e-3, "uv": 1e-6, "nv": 1e-9, "pv": 1e-12, "fv": 1e-15,
    "vrms": 1.0, "v_rms": 1.0, "mvrms": 1e-3, "mv_rms": 1e-3,
    "uvrms": 1e-6, "uv_rms": 1e-6, "nvrms": 1e-9, "nv_rms": 1e-9,
    "vpp": 1.0, "v_pp": 1.0, "mvpp": 1e-3, "mv_pp": 1e-3, "uvpp": 1e-6, "uv_pp": 1e-6,
    # Current (DC, RMS, peak-to-peak)
    "a": 1.0, "ka": 1e3, "ma": 1e-3, "ua": 1e-6, "na": 1e-9, "pa": 1e-12, "fa": 1e-15,
    "arms": 1.0, "a_rms": 1.0, "marms": 1e-3, "ma_rms": 1e-3,
    "uarms": 1e-6, "ua_rms": 1e-6, "narms": 1e-9, "na_rms": 1e-9, "parms": 1e-12, "pa_rms": 1e-12,
    # Resistance & Conductance
    "ohm": 1.0, "ohms": 1.0, "kohm": 1e3, "kohms": 1e3,
    "megohm": 1e6, "megohms": 1e6, "gohm": 1e9, "gohms": 1e9,
    "mohm": 1e-3, "mohms": 1e-3,
    "siemens": 1.0, "msiemens": 1e-3, "usiemens": 1e-6,
    "a/v": 1.0, "ma/v": 1e-3, "ua/v": 1e-6,
    # Capacitance & Inductance & Charge
    "f": 1.0, "mf": 1e-3, "uf": 1e-6, "nf": 1e-9, "pf": 1e-12, "ff": 1e-15, "af": 1e-18,
    "h": 1.0, "mh": 1e-3, "uh": 1e-6, "nh": 1e-9, "ph": 1e-12,
    "c": 1.0, "mc": 1e-3, "uc": 1e-6, "nc": 1e-9, "pc": 1e-12, "fc": 1e-15,
    # Slew rate
    "v/s": 1.0, "v/ms": 1e3, "v/us": 1e6, "v/ns": 1e9, "v/ps": 1e12,
    "mv/ms": 1.0, "mv/us": 1e3, "mv/ns": 1e6, "mv/ps": 1e9, "kv/us": 1e9,
    # Spectral noise density (ASD)
    "v/sqrt(hz)": 1.0, "v/rthz": 1.0,
    "mv/sqrt(hz)": 1e-3, "mv/rthz": 1e-3,
    "uv/sqrt(hz)": 1e-6, "uv/rthz": 1e-6,
    "nv/sqrt(hz)": 1e-9, "nv/rthz": 1e-9,
    "a/sqrt(hz)": 1.0, "a/rthz": 1.0,
    "ma/sqrt(hz)": 1e-3, "ma/rthz": 1e-3,
    "ua/sqrt(hz)": 1e-6, "ua/rthz": 1e-6,
    "na/sqrt(hz)": 1e-9, "na/rthz": 1e-9,
    "pa/sqrt(hz)": 1e-12, "pa/rthz": 1e-12,
    # Logarithmic, angular, dimensionless
    "db": 1.0, "dbc": 1.0, "dbfs": 1.0, "dbv": 1.0, "dbm": 1.0,
    "deg": 1.0, "degree": 1.0, "degrees": 1.0,
    "%": 1.0, "pct": 1.0, "percent": 1.0,
    "v/v": 1.0, "a/a": 1.0, "s/a": 1.0, "1/v": 1.0, "v^-1": 1.0,
}

# Strict separation: `phase_margin_deg` ONLY resolves to `.stb` phase margin (never `pm_ac_deg`).
METRIC_KEY_ALIASES = {
    "dc_power_w": ("dc_power_w", "power_w", "power", "pdc", "p_dc", "static_power"),
    "idd_a": ("idd_a", "idd", "iq", "i_q", "quiescent_current"),
    "dc_gain_db": ("dc_gain_db", "a0_db", "a0", "av_db", "dc_gain", "open_loop_gain_db"),
    "bw_3db_hz": ("bw_3db_hz", "f3db_hz", "f3db", "bw_3db", "bandwidth_3db", "bw_hz"),
    "ugf_hz": ("ugf_hz", "gbw_hz", "gbw", "ugbw", "ugf", "unity_gain_bw", "unity_gain_freq"),
    "pm_ac_deg": ("pm_ac_deg", "open_loop_pm_ac_deg"),
    "loop_dc_gain_db": ("loop_dc_gain_db", "t0_db", "stb_dc_gain_db", "loop_gain_dc_db"),
    "stb_ugf_hz": ("stb_ugf_hz", "loop_ugf_hz", "fc_hz", "crossover_freq_hz"),
    "phase_margin_deg": ("phase_margin_deg", "pm_deg", "pm", "phase_margin"),
    "gain_margin_db": ("gain_margin_db", "gm_db", "gain_margin"),
    "slew_rate_pos": ("slew_rate_pos", "sr_pos", "slew_rate", "sr_rising"),
    "slew_rate_neg": ("slew_rate_neg", "sr_neg", "sr_falling"),
    "overshoot_pct": ("overshoot_pct", "overshoot", "os_pct"),
    "settling_time_s": ("settling_time_s", "t_settle", "settling_time", "ts"),
    "ripple_pp": ("ripple_pp", "vout_ripple_pp", "ripple_vpp", "ripple"),
    "integrated_rms_noise_v": ("integrated_rms_noise_v", "rms_noise_v", "vnoise_rms", "noise_rms"),
    "integrated_rms_noise_a": ("integrated_rms_noise_a", "rms_noise_a", "inoise_rms_a", "current_noise_rms"),
}

SUPPLY_RAIL_PREFIXES = (
    "vdd", "avdd", "dvdd", "iovdd", "pvdd", "svdd", "tvdd", "rvdd", "cvdd",
    "vcc", "avcc", "dvcc", "vsup", "vpwr", "vbat", "vbatt", "vhv",
)

NON_SUPPLY_STIM_STEMS = (
    "vin", "vip", "vinp", "vinn", "vin_ac", "vin_p", "vin_n", "in", "inp", "inn",
    "vout", "vop", "von", "out", "outp", "outn",
    "vcm", "vocm", "vicm", "vbias", "vref", "vstep", "vpulse",
    "vclk", "clk", "ven", "en", "vctrl", "ctrl", "vfb", "fb", "vtest", "vprobe", "iprobe",
    "gnd", "agnd", "dgnd", "vss", "avss", "dvss", "0",
)


class _SilentOptionParser(OptionParser):
    def error(self, msg):
        raise ValueError(msg)


def _round_clean(val, digits=9):
    if val is None or isinstance(val, bool) or isinstance(val, int):
        return val
    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            return None
        fmt = "%%.%dg" % int(digits)
        return float(fmt % val)
    return val


def _leaf_inst_name(name):
    parts = re.split(r'[./:]', name)
    return parts[-1] if parts else name


def _is_mos_struct(type_name, fields):
    t_low = (type_name or "").lower()
    f_keys = set([k.lower() for k in fields.keys()])
    has_core = ("gm" in f_keys and "vds" in f_keys and ("ids" in f_keys or "id" in f_keys))
    if has_core:
        return True
    for hint in MOS_MODEL_HINTS:
        if hint in t_low and ("vgs" in f_keys or "gm" in f_keys or "region" in f_keys or "vds" in f_keys):
            return True
    return False


def _pick_field(fields_lc, canonical):
    for cand in MOS_FIELD_ALIASES.get(canonical, (canonical,)):
        if cand in fields_lc:
            val = fields_lc[cand]
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                return val
    if canonical == "gds" and "rout" in fields_lc:
        rv = fields_lc["rout"]
        if isinstance(rv, (int, float)) and abs(rv) > 1e-18:
            return 1.0 / float(rv)
    return None


def _is_pmos_device(inst_name, type_name, fields_lc, vgs, vth):
    joined = "%s %s %s" % (
        inst_name.lower(),
        (type_name or "").lower(),
        str(fields_lc.get("model", "")).lower(),
    )
    if any([tok in joined for tok in ("pmos", "pch", "pfet", "g45p")]):
        if vth is None or vth < 0.0:
            return True
    if vth is not None and vth < -1e-4 and (vgs is None or vgs <= 1e-3):
        return True
    return False


def _extract_mos_devices_from_parsed(parsed):
    """Extract raw MOSFET field dicts from either STRUCT instances or flat M1:param values."""
    mos_map = {}

    for inst_name, meta in parsed.get("instances", {}).items():
        fields = meta.get("fields", {})
        if _is_mos_struct(meta.get("type", ""), fields):
            mos_map[inst_name] = {
                "type": meta.get("type", "mos"),
                "fields_lc": dict([(k.lower(), v) for k, v in fields.items()]),
            }

    grouped_flat = {}
    for sig_name, arr in parsed.get("values", {}).items():
        if not arr or isinstance(arr[0], complex):
            continue
        sep = ":" if ":" in sig_name else ("." if "." in sig_name else None)
        if not sep:
            continue
        inst, param = sig_name.rsplit(sep, 1)
        if not inst or not param:
            continue
        grouped_flat.setdefault(inst, {})[param.lower()] = arr[0]

    for inst_name, flc in grouped_flat.items():
        if inst_name in mos_map:
            continue
        if _is_mos_struct("mos", flc):
            mos_map[inst_name] = {"type": "mos_flat", "fields_lc": flc}

    return mos_map


def audit_mos_op_parsed(parsed, vds_margin=0.05, expect_triode=None):
    """Strict fail-closed MOS operating-point auditor."""
    expect_set = set(expect_triode or [])
    expect_lc = set([x.lower() for x in expect_set])
    mos_raw = _extract_mos_devices_from_parsed(parsed)

    devices = {}
    flags = []
    buckets = {
        "saturation": [],
        "cutoff": [],
        "unintended_triode": [],
        "expected_triode": [],
        "subthreshold": [],
        "breakdown": [],
        "tight_headroom": [],
        "missing_op_fields": [],
    }

    min_sat_margin = None
    worst_headroom_dev = None
    any_hard_fail = False
    any_missing_op = False
    any_headroom_violation = False

    for inst_name in sorted(mos_raw.keys()):
        entry = mos_raw[inst_name]
        flc = entry["fields_lc"]
        dev_type = entry["type"]

        ids = _pick_field(flc, "ids")
        vgs = _pick_field(flc, "vgs")
        vds = _pick_field(flc, "vds")
        vth = _pick_field(flc, "vth")
        vdsat = _pick_field(flc, "vdsat")
        gm = _pick_field(flc, "gm")
        gds = _pick_field(flc, "gds")
        gmb = _pick_field(flc, "gmb")
        cgg = _pick_field(flc, "cgg")
        cgd = _pick_field(flc, "cgd")
        cgs = _pick_field(flc, "cgs")
        reg_raw = _pick_field(flc, "region")
        region = int(round(reg_raw)) if reg_raw is not None else None

        gm_id = (abs(gm) / abs(ids)) if (gm is not None and ids is not None and abs(ids) > 1e-18) else None
        gm_gds = (abs(gm) / abs(gds)) if (gm is not None and gds is not None and abs(gds) > 1e-18) else None

        vov = None
        if vgs is not None and vth is not None:
            if _is_pmos_device(inst_name, dev_type, flc, vgs, vth):
                vov = (-float(vgs)) - abs(float(vth))
            else:
                vov = float(vgs) - float(vth)

        sat_margin = None
        if vds is not None and vdsat is not None:
            sat_margin = abs(float(vds)) - abs(float(vdsat))

        ft_hz = None
        if gm is not None and cgg is not None and abs(cgg) > 1e-24:
            ft_hz = abs(float(gm)) / (2.0 * math.pi * abs(float(cgg)))

        leaf = _leaf_inst_name(inst_name)
        is_expected_triode = (
            inst_name in expect_set
            or leaf in expect_set
            or inst_name.lower() in expect_lc
            or leaf.lower() in expect_lc
        )

        # Infer region when explicit `region` is absent ONLY if (vgs, vth, vds, vdsat) are all present
        effective_region = region
        if effective_region is None and vov is not None and sat_margin is not None:
            if vov <= 0.0 and (ids is None or abs(float(ids)) < 1e-12):
                effective_region = 0
            elif sat_margin < 0.0:
                effective_region = 1
            else:
                effective_region = 2

        dev_flags = []
        status = "OK"

        # Fail-closed check for missing core OP evidence:
        # Must have `vds` AND `vdsat` AND (`region` OR `(vgs, vth)`).
        missing_fields = []
        if vds is None:
            missing_fields.append("vds")
        if vdsat is None:
            missing_fields.append("vdsat")
        if region is None and (vgs is None or vth is None):
            missing_fields.append("region_or_vgs_vth")

        if effective_region == 0:
            buckets["cutoff"].append(inst_name)
            dev_flags.append("CUTOFF")
            status = "FAIL"
            any_hard_fail = True
            flags.append({
                "device": inst_name,
                "code": "CUTOFF",
                "severity": "error",
                "region": effective_region,
                "sat_margin": _round_clean(sat_margin),
                "message": "%s is in cutoff (region=0, ids=%s)" % (inst_name, repr(_round_clean(ids))),
            })
        elif effective_region == 1:
            if is_expected_triode:
                buckets["expected_triode"].append(inst_name)
                dev_flags.append("EXPECTED_TRIODE")
                status = "EXPECTED_TRIODE"
            else:
                buckets["unintended_triode"].append(inst_name)
                dev_flags.append("UNINTENDED_TRIODE")
                status = "FAIL"
                any_hard_fail = True
                flags.append({
                    "device": inst_name,
                    "code": "UNINTENDED_TRIODE",
                    "severity": "error",
                    "region": effective_region,
                    "sat_margin": _round_clean(sat_margin),
                    "message": "%s is in unintended triode/linear region (region=1, |vds|=%s, |vdsat|=%s)" % (
                        inst_name,
                        repr(_round_clean(abs(vds) if vds is not None else None)),
                        repr(_round_clean(abs(vdsat) if vdsat is not None else None)),
                    ),
                })
        elif effective_region == 2:
            buckets["saturation"].append(inst_name)
        elif effective_region == 3:
            buckets["subthreshold"].append(inst_name)
            dev_flags.append("SUBTHRESHOLD")
            if status == "OK":
                status = "WARN"
            flags.append({
                "device": inst_name,
                "code": "SUBTHRESHOLD",
                "severity": "warning",
                "region": effective_region,
                "sat_margin": _round_clean(sat_margin),
                "message": "%s is operating in subthreshold/weak inversion (region=3, gm_id=%s)" % (
                    inst_name, repr(_round_clean(gm_id))
                ),
            })
        elif effective_region == 4:
            buckets["breakdown"].append(inst_name)
            dev_flags.append("BREAKDOWN")
            status = "FAIL"
            any_hard_fail = True
            flags.append({
                "device": inst_name,
                "code": "BREAKDOWN",
                "severity": "error",
                "region": effective_region,
                "sat_margin": _round_clean(sat_margin),
                "message": "%s is in breakdown (region=4)" % inst_name,
            })

        if missing_fields and not is_expected_triode and effective_region != 0:
            buckets["missing_op_fields"].append(inst_name)
            dev_flags.append("MISSING_OP_FIELDS")
            any_missing_op = True
            if status != "FAIL":
                status = "NOT_VERIFIED"
            flags.append({
                "device": inst_name,
                "code": "MISSING_OP_FIELDS",
                "severity": "error",
                "region": region,
                "sat_margin": _round_clean(sat_margin),
                "missing": missing_fields,
                "message": "%s is missing required OP verification fields: %s" % (
                    inst_name, ", ".join(missing_fields)
                ),
            })

        if (
            sat_margin is not None
            and effective_region not in (0,)
            and not is_expected_triode
        ):
            if min_sat_margin is None or sat_margin < min_sat_margin:
                min_sat_margin = sat_margin
                worst_headroom_dev = inst_name

            if effective_region != 1 and sat_margin < vds_margin:
                buckets["tight_headroom"].append(inst_name)
                dev_flags.append("TIGHT_HEADROOM")
                any_headroom_violation = True
                if sat_margin < 0.0:
                    sev = "error"
                    status = "FAIL"
                    any_hard_fail = True
                else:
                    sev = "warning"
                    if status == "OK":
                        status = "WARN"
                flags.append({
                    "device": inst_name,
                    "code": "TIGHT_HEADROOM",
                    "severity": sev,
                    "region": effective_region,
                    "sat_margin": _round_clean(sat_margin),
                    "message": "%s has tight Vds headroom: sat_margin=%.4g V < %.4g V" % (
                        inst_name, sat_margin, vds_margin
                    ),
                })

        devices[inst_name] = {
            "type": dev_type,
            "region": effective_region,
            "region_name": REGION_NAMES.get(effective_region, "unknown"),
            "ids": _round_clean(ids),
            "vgs": _round_clean(vgs),
            "vds": _round_clean(vds),
            "vth": _round_clean(vth),
            "vdsat": _round_clean(vdsat),
            "gm": _round_clean(gm),
            "gds": _round_clean(gds),
            "gmb": _round_clean(gmb),
            "cgg": _round_clean(cgg),
            "cgd": _round_clean(cgd),
            "cgs": _round_clean(cgs),
            "gm_id": _round_clean(gm_id),
            "gm_gds": _round_clean(gm_gds),
            "vov": _round_clean(vov),
            "sat_margin": _round_clean(sat_margin),
            "ft_hz": _round_clean(ft_hz),
            "status": status,
            "flags": dev_flags,
        }

    warn_flags = [f for f in flags if f["severity"] == "warning"]
    if any_hard_fail:
        overall = "FAIL"
    elif any_missing_op or len(devices) == 0:
        overall = "NOT_VERIFIED"
    elif any_headroom_violation or warn_flags:
        overall = "WARN"
    else:
        overall = "PASS"

    audit_pass = (
        len(devices) > 0
        and (not any_hard_fail)
        and (not any_missing_op)
        and (not any_headroom_violation)
    )

    return {
        "audit_pass": audit_pass,
        "status": overall,
        "device_count": len(devices),
        "devices": devices,
        "flags": flags,
        "summary": {
            "saturation": buckets["saturation"],
            "cutoff": buckets["cutoff"],
            "unintended_triode": buckets["unintended_triode"],
            "expected_triode": buckets["expected_triode"],
            "subthreshold": buckets["subthreshold"],
            "breakdown": buckets["breakdown"],
            "tight_headroom": buckets["tight_headroom"],
            "missing_op_fields": buckets["missing_op_fields"],
            "min_sat_margin_v": _round_clean(min_sat_margin),
            "worst_headroom_device": worst_headroom_dev,
        },
    }


def _find_op_psf_files(target_path):
    if os.path.isfile(target_path):
        return [("nominal", target_path)]
    if not os.path.isdir(target_path):
        return []

    candidates = []
    op_names = ("dcOpInfo.info", "oppoint.info", "op.info", "dcOp.dc", "op.dc")
    for root, dirs, files in os.walk(target_path):
        dirs.sort()
        files_set = set(files)
        picked = None
        for nm in op_names:
            if nm in files_set:
                picked = os.path.join(root, nm)
                break
        if picked is None:
            for fn in sorted(files):
                low = fn.lower()
                if low.endswith(".info") and ("op" in low or "dcop" in low):
                    picked = os.path.join(root, fn)
                    break
        if picked is not None:
            rel = os.path.relpath(os.path.dirname(picked), target_path).replace(os.sep, "/")
            parts = [p for p in rel.split("/") if p not in (".", "psf", "raw")]
            label = "/".join(parts) if parts else "nominal"
            candidates.append((label, picked))
    return candidates


def run_op_audit(target_path, vds_margin=0.05, expect_triode=None):
    op_files = _find_op_psf_files(target_path)
    if not op_files:
        raise ValueError("No operating-point PSF ASCII file found at: " + str(target_path))

    per_point = {}
    for label, fpath in op_files:
        parsed = parse_psf_file(
            fpath,
            reject_nonfinite=True,
            reject_truncated=True,
            fill_leading_missing=True,
        )
        rep = audit_mos_op_parsed(parsed, vds_margin=vds_margin, expect_triode=expect_triode)
        rep["psf_path"] = os.path.realpath(fpath)
        per_point[label] = rep

    primary_label = "nominal" if "nominal" in per_point else sorted(per_point.keys())[0]
    primary = dict(per_point[primary_label])
    primary["command"] = "op-audit"
    primary["ok"] = True
    primary["target"] = os.path.realpath(target_path)
    primary["vds_margin_target_v"] = vds_margin
    primary["expect_triode"] = sorted(list(expect_triode or []))

    if len(per_point) > 1:
        primary["points"] = per_point
        statuses = [p["status"] for p in per_point.values()]
        any_fail = ("FAIL" in statuses)
        any_nv = ("NOT_VERIFIED" in statuses) or any([p["device_count"] == 0 for p in per_point.values()])
        any_warn = ("WARN" in statuses)
        primary["audit_pass"] = all([
            bool(p.get("audit_pass")) and p.get("device_count", 0) > 0
            for p in per_point.values()
        ])
        if any_fail:
            primary["status"] = "FAIL"
        elif any_nv:
            primary["status"] = "NOT_VERIFIED"
        elif any_warn or (not primary["audit_pass"]):
            primary["status"] = "WARN"
        else:
            primary["status"] = "PASS"

    return primary


# ---------------------------------------------------------------------------
# Signal & Waveform Metric Extractors
# ---------------------------------------------------------------------------

def _unwrap_phase_deg(phases_deg):
    if not phases_deg:
        return []
    out = [phases_deg[0]]
    offset = 0.0
    for idx in range(1, len(phases_deg)):
        diff = phases_deg[idx] - phases_deg[idx - 1]
        while diff > 180.0:
            offset -= 360.0
            diff -= 360.0
        while diff < -180.0:
            offset += 360.0
            diff += 360.0
        out.append(phases_deg[idx] + offset)
    return out


def _log_interp_x(f0, f1, y0, y1, y_target):
    if f0 <= 0.0 or f1 <= 0.0:
        if abs(y1 - y0) < 1e-30:
            return f0, 0.0
        frac = (y_target - y0) / (y1 - y0)
        return (f0 + frac * (f1 - f0)), frac
    if abs(y1 - y0) < 1e-30:
        return f0, 0.0
    frac = (y_target - y0) / (y1 - y0)
    lf0 = math.log10(f0)
    lf1 = math.log10(f1)
    return (10.0 ** (lf0 + frac * (lf1 - lf0))), frac


def _pick_signal_key(values, preferred_names, exclude=()):
    excl = set([x.lower() for x in exclude if x])
    lc_map = {}
    for k in values.keys():
        if k.lower() not in excl:
            lc_map[k.lower()] = k
    for cand in preferred_names:
        if cand.lower() in lc_map:
            return lc_map[cand.lower()]
    for cand in preferred_names:
        cl = cand.lower()
        for kl, orig in sorted(lc_map.items()):
            if kl.endswith("/" + cl) or kl.endswith("." + cl) or kl == cl:
                return orig
    return None


def _normalize_rail_stem(raw_name):
    """Normalize voltage node or source probe name (`V_AVDD:p` -> `avdd`, `VDD18:p` -> `vdd18`)."""
    leaf = re.split(r'[/:.]', str(raw_name).strip())
    # Drop terminal suffix (`p`, `n`, `i`, `1`, `2`) if `:p` or `.p` was present
    if (":" in raw_name or "." in raw_name) and len(leaf) >= 2 and leaf[-1].lower() in ("p", "n", "i", "plus", "minus"):
        base = leaf[-2]
    else:
        base = leaf[-1]
    stem = base.strip().lower()
    for pref in ("vsrc_", "vsup_", "v_"):
        if stem.startswith(pref) and len(stem) > len(pref):
            stem = stem[len(pref):]
            break
    if stem.startswith("vv") and len(stem) > 2:
        stem = stem[1:]
    return stem


def _is_supply_rail_stem(stem):
    if not stem or stem in NON_SUPPLY_STIM_STEMS:
        return False
    for pref in SUPPLY_RAIL_PREFIXES:
        if stem == pref or stem.startswith(pref):
            return True
    return False


def _extract_dc_power(parsed_list):
    """Compute static DC power with strict multi-rail matching.

    - Sums `|V_k * I_k|` across all matched supply rails (`VDD:p` * `VDD` + `VDD18:p` * `VDD18`, etc.).
    - If multiple supply rails or probes exist and cannot be matched unambiguously, sets `dc_power_w = None`.
    - MOS `sum(|Vds * Ids|)` fallback is stored ONLY in `mos_power_estimate_w`, NEVER in `dc_power_w`.
    """
    for parsed in parsed_list:
        vals = parsed.get("values", {})
        field_units = parsed.get("field_units", {})
        if not vals:
            continue

        # Collect scalar real voltage nodes vs source terminal current probes
        voltage_nodes = {}  # stem -> list of (orig_key, float_val)
        supply_voltage_nodes = {}
        current_probes = []  # list of (orig_key, stem, float_val)

        for k in sorted(vals.keys()):
            arr = vals[k]
            if not arr or isinstance(arr[0], complex):
                continue
            try:
                fval = float(arr[0])
            except (TypeError, ValueError):
                continue
            kl = k.lower()
            unit_lc = str(field_units.get(k, "")).strip().lower()
            is_curr_term = (
                kl.endswith(":p") or kl.endswith(".p") or kl.endswith(":i") or kl.endswith(".i")
            )
            if is_curr_term:
                leaf0 = re.split(r'[/:.]', kl)[0]
                if leaf0.startswith("v") or unit_lc in ("a", "amp", "amps"):
                    stem = _normalize_rail_stem(k)
                    current_probes.append((k, stem, fval))
                continue

            # Skip flat device OP fields like `M1:vds` or `R1.i`
            if ":" in k:
                continue
            if unit_lc and unit_lc not in ("v", "volt", "volts"):
                continue
            stem = _normalize_rail_stem(k)
            if stem in ("0", "gnd", "agnd", "dgnd", "vss", "avss", "dvss"):
                continue
            voltage_nodes.setdefault(stem, []).append((k, fval))
            if _is_supply_rail_stem(stem):
                supply_voltage_nodes.setdefault(stem, []).append((k, fval))

        # Filter current probes: exclude explicit non-supply stimuli (`VIN:p`, `VBIAS:p`) if any supply rail/probe exists
        supply_named_probes = [cp for cp in current_probes if _is_supply_rail_stem(cp[1])]
        generic_src_probes = [
            cp for cp in current_probes
            if (cp[1] not in NON_SUPPLY_STIM_STEMS) and (not _is_supply_rail_stem(cp[1]))
        ]

        out = {}

        # Estimate MOS power separately (diagnostic only, never `dc_power_w`)
        mos_map = _extract_mos_devices_from_parsed(parsed)
        if mos_map:
            p_mos = 0.0
            mos_ok = False
            for m_entry in mos_map.values():
                flc = m_entry["fields_lc"]
                ids = _pick_field(flc, "ids")
                vds = _pick_field(flc, "vds")
                if ids is not None and vds is not None:
                    p_mos += abs(float(ids) * float(vds))
                    mos_ok = True
            if mos_ok:
                out["mos_power_estimate_w"] = _round_clean(p_mos)

        candidate_probes = []
        if supply_named_probes:
            # Include both supply-named probes AND any generic `V0:p` probes so unmatched extra rails aren't ignored
            candidate_probes = supply_named_probes + generic_src_probes
        else:
            candidate_probes = generic_src_probes

        num_supply_v = len(supply_voltage_nodes)
        num_cand_i = len(candidate_probes)

        if num_supply_v > 0 and num_cand_i > 0:
            # Attempt 1-to-1 stem matching between candidate current probes and voltage nodes
            matched_rails = []
            unmatched_probes = []
            matched_v_stems = set()
            ambiguous = False

            for c_key, c_stem, c_val in candidate_probes:
                v_cands = supply_voltage_nodes.get(c_stem) or voltage_nodes.get(c_stem)
                if v_cands and len(v_cands) == 1 and c_stem not in matched_v_stems:
                    matched_v_stems.add(c_stem)
                    matched_rails.append({
                        "rail": c_stem,
                        "voltage_node": v_cands[0][0],
                        "current_probe": c_key,
                        "vdd_v": _round_clean(abs(v_cands[0][1])),
                        "idd_a": _round_clean(abs(c_val)),
                        "power_w": _round_clean(abs(v_cands[0][1]) * abs(c_val)),
                    })
                elif v_cands and (len(v_cands) > 1 or c_stem in matched_v_stems):
                    ambiguous = True
                    unmatched_probes.append(c_key)
                else:
                    unmatched_probes.append(c_key)

            unmatched_supply_v = [st for st in sorted(supply_voltage_nodes.keys()) if st not in matched_v_stems]

            if (not ambiguous) and matched_rails and (not unmatched_probes) and (not unmatched_supply_v):
                total_p = sum([abs(float(vals[r["voltage_node"]][0])) * abs(float(vals[r["current_probe"]][0])) for r in matched_rails])
                total_i = sum([abs(float(vals[r["current_probe"]][0])) for r in matched_rails])
                out.update({
                    "vdd_v": matched_rails[0]["vdd_v"] if len(matched_rails) == 1 else None,
                    "idd_a": _round_clean(total_i),
                    "dc_power_w": _round_clean(total_p),
                    "power_method": "supply_terminal" if len(matched_rails) == 1 else "multi_rail_supply_terminal",
                    "supply_rails": matched_rails,
                })
                if len(matched_rails) == 1:
                    out["supply_node"] = matched_rails[0]["voltage_node"]
                    out["current_probe"] = matched_rails[0]["current_probe"]
                return out

            # Single supply voltage node + single generic supply probe (`vdd` + `V0:p`)
            if num_supply_v == 1 and num_cand_i == 1:
                only_v_stem = list(supply_voltage_nodes.keys())[0]
                v_list = supply_voltage_nodes[only_v_stem]
                if len(v_list) == 1:
                    v_key, v_val = v_list[0]
                    c_key, _, c_val = candidate_probes[0]
                    out.update({
                        "vdd_v": _round_clean(abs(v_val)),
                        "idd_a": _round_clean(abs(c_val)),
                        "dc_power_w": _round_clean(abs(v_val) * abs(c_val)),
                        "power_method": "supply_terminal",
                        "supply_node": v_key,
                        "current_probe": c_key,
                    })
                    return out

            # Multiple rails / probes could not be matched unambiguously -> fail closed!
            out.update({
                "dc_power_w": None,
                "idd_a": None,
                "power_method": "ambiguous_multi_rail",
                "unmatched_supply_nodes": unmatched_supply_v,
                "unmatched_current_probes": unmatched_probes,
            })
            return out

        if out:
            out["dc_power_w"] = None
            out["power_method"] = "mos_vds_ids_sum_estimate_only"
            return out

    return {}


def _usable_waveform_values(parsed):
    """Filter out signals that had missing leading sweep points backfilled by reader."""
    raw_vals = parsed.get("values", {})
    backfilled = set(parsed.get("backfilled_leading_signals", {}).keys())
    if not backfilled:
        return raw_vals, []
    clean = {}
    rejected = []
    for k, v in raw_vals.items():
        if k in backfilled:
            rejected.append(k)
        else:
            clean[k] = v
    return clean, sorted(rejected)


def _extract_ac_metrics(parsed, vout_hint=None, vin_hint=None):
    vals, rejected_bf = _usable_waveform_values(parsed)
    freq_key = parsed.get("sweep_name") or _pick_signal_key(vals, ("freq", "frequency", "f"))
    if not freq_key or freq_key not in vals:
        return {"rejected_backfilled_signals": rejected_bf} if rejected_bf else {}
    freqs = [float(x.real) if isinstance(x, complex) else float(x) for x in vals[freq_key]]
    if len(freqs) < 2:
        return {}

    if vout_hint and vout_hint in rejected_bf:
        return {"ac_output": vout_hint, "dc_gain_db": None, "bw_3db_hz": None, "ugf_hz": None, "pm_ac_deg": None, "rejected_backfilled_signals": rejected_bf}

    h_vec = None
    out_label = None
    if vout_hint and vout_hint in vals:
        h_vec = [complex(v) for v in vals[vout_hint]]
        out_label = vout_hint
    elif not vout_hint:
        vp = _pick_signal_key(vals, ("voutp", "vout_p", "outp", "out_p", "vop"), exclude=(freq_key,))
        vn = _pick_signal_key(vals, ("voutn", "vout_n", "outn", "out_n", "von"), exclude=(freq_key,))
        if vp and vn and len(vals[vp]) == len(freqs) and len(vals[vn]) == len(freqs):
            h_vec = [complex(vals[vp][i]) - complex(vals[vn][i]) for i in range(len(freqs))]
            out_label = "%s-%s" % (vp, vn)
        else:
            vo = _pick_signal_key(
                vals,
                ("vout", "out", "vo", "v_out", "vf", "y"),
                exclude=(freq_key, "vin", "in", "vdd", "vss"),
            )
            if vo is None:
                for k in sorted(vals.keys()):
                    if k != freq_key and vals[k] and isinstance(vals[k][0], complex):
                        vo = k
                        break
            if vo and len(vals[vo]) == len(freqs):
                h_vec = [complex(v) for v in vals[vo]]
                out_label = vo

    if not h_vec:
        return {"rejected_backfilled_signals": rejected_bf} if rejected_bf else {}

    vin_key = vin_hint if (vin_hint and vin_hint in vals) else _pick_signal_key(
        vals, ("vin", "vin_ac", "in", "v_in"), exclude=(freq_key, out_label or "")
    )
    if vin_key and len(vals[vin_key]) == len(freqs):
        vin_arr = [complex(v) for v in vals[vin_key]]
        if abs(vin_arr[0]) > 1e-15:
            h_vec = [
                (h_vec[i] / vin_arr[i]) if abs(vin_arr[i]) > 1e-30 else h_vec[i]
                for i in range(len(freqs))
            ]

    mags = [abs(c) for c in h_vec]
    if mags[0] <= 0.0:
        return {"ac_output": out_label, "dc_gain_db": None, "bw_3db_hz": None, "ugf_hz": None, "pm_ac_deg": None}

    mag_db = [20.0 * math.log10(m) if m > 1e-300 else -600.0 for m in mags]
    raw_phase = [math.degrees(math.atan2(c.imag, c.real)) for c in h_vec]
    unwrapped = _unwrap_phase_deg(raw_phase)

    dc_gain_db = mag_db[0]
    target_3db = dc_gain_db - 3.010299956639812
    bw_3db_hz = None
    for i in range(len(freqs) - 1):
        if mag_db[i] >= target_3db and mag_db[i + 1] < target_3db:
            bw_3db_hz, _ = _log_interp_x(freqs[i], freqs[i + 1], mag_db[i], mag_db[i + 1], target_3db)
            break

    ugf_hz = None
    pm_ac_deg = None
    phi_0 = unwrapped[0]
    for i in range(len(freqs) - 1):
        if mag_db[i] >= 0.0 and mag_db[i + 1] < 0.0:
            ugf_hz, frac = _log_interp_x(freqs[i], freqs[i + 1], mag_db[i], mag_db[i + 1], 0.0)
            phi_u = unwrapped[i] + frac * (unwrapped[i + 1] - unwrapped[i])
            delta_phi = phi_u - phi_0
            pm_ac_deg = 180.0 + delta_phi
            break

    res = {
        "ac_output": out_label,
        "dc_gain_db": _round_clean(dc_gain_db),
        "bw_3db_hz": _round_clean(bw_3db_hz),
        "ugf_hz": _round_clean(ugf_hz),
        "pm_ac_deg": _round_clean(pm_ac_deg),
    }
    if rejected_bf:
        res["rejected_backfilled_signals"] = rejected_bf
    return res


def _phase_margin_from_unwrapped(phi_deg):
    """Distance in degrees from nearest critical odd-multiple of 180 deg, signed consistently with standard Bode plot."""
    # Standard negative feedback loopGain starts near 0 deg and crosses -180 deg -> PM = 180 + phi.
    # If phase lags past -360 deg toward -540 deg, 180 + phi is already strongly negative (< -180 deg).
    # If phase leads above +180 deg, margin to +180 deg is 180 - phi.
    if phi_deg > 0.0:
        return min(180.0 + phi_deg, 180.0 - phi_deg)
    return 180.0 + phi_deg


def _extract_stb_metrics(stb_parsed, margin_parsed=None):
    vals, rejected_bf = _usable_waveform_values(stb_parsed) if stb_parsed else ({}, [])
    freq_key = (stb_parsed.get("sweep_name") if stb_parsed else None) or _pick_signal_key(
        vals, ("freq", "frequency", "f")
    )
    lg_key = _pick_signal_key(vals, ("loopGain", "loopgain", "T", "returnRatio"), exclude=(freq_key or "",))

    out = {}
    if rejected_bf:
        out["rejected_backfilled_signals"] = rejected_bf

    if freq_key and lg_key and len(vals[freq_key]) >= 2 and len(vals[lg_key]) == len(vals[freq_key]):
        freqs = [float(x.real) if isinstance(x, complex) else float(x) for x in vals[freq_key]]
        lg = [complex(v) for v in vals[lg_key]]
        mags = [abs(c) for c in lg]
        mag_db = [20.0 * math.log10(m) if m > 1e-300 else -600.0 for m in mags]
        raw_phase = [math.degrees(math.atan2(c.imag, c.real)) for c in lg]
        unwrapped = _unwrap_phase_deg(raw_phase)

        dc_pos_fb = (lg[0].real < 0.0 and mags[0] > 1.0)
        loop_dc_gain_db = mag_db[0] if mags[0] > 0.0 else None

        ugf_crossings = []
        for i in range(len(freqs) - 1):
            if (mag_db[i] >= 0.0 and mag_db[i + 1] < 0.0) or (mag_db[i] < 0.0 and mag_db[i + 1] >= 0.0):
                f_c, frac = _log_interp_x(freqs[i], freqs[i + 1], mag_db[i], mag_db[i + 1], 0.0)
                phi_c = unwrapped[i] + frac * (unwrapped[i + 1] - unwrapped[i])
                pm_c = _phase_margin_from_unwrapped(phi_c)
                ugf_crossings.append({
                    "freq_hz": _round_clean(f_c),
                    "phase_deg": _round_clean(phi_c),
                    "phase_margin_deg": _round_clean(pm_c),
                    "direction": "falling" if mag_db[i] >= mag_db[i + 1] else "rising",
                })

        falling_crossings = [c for c in ugf_crossings if c["direction"] == "falling"]
        primary_ugf = None
        worst_pm = None
        if falling_crossings:
            primary_ugf = falling_crossings[0]["freq_hz"]
            worst_pm = min([c["phase_margin_deg"] for c in falling_crossings])
        elif ugf_crossings:
            primary_ugf = ugf_crossings[0]["freq_hz"]
            worst_pm = min([c["phase_margin_deg"] for c in ugf_crossings])

        if dc_pos_fb and (worst_pm is None or worst_pm > 0.0):
            worst_pm = -abs(worst_pm) if worst_pm is not None else -180.0

        # Check ALL odd-multiple 180 deg phase crossings: 180 * (2*m - 1) = ..., -540, -180, +180, +540, ...
        phi_min = min(unwrapped)
        phi_max = max(unwrapped)
        m_lo = int(math.floor((phi_min + 180.0) / 360.0)) - 1
        m_hi = int(math.ceil((phi_max + 180.0) / 360.0)) + 1
        crit_targets = [180.0 * (2 * m - 1) for m in range(m_lo, m_hi + 1)]

        gm_db = None
        gm_freq_hz = None
        gm_crossings = []
        for crit_deg in crit_targets:
            if crit_deg < phi_min - 1e-12 or crit_deg > phi_max + 1e-12:
                continue
            for i in range(len(freqs) - 1):
                u0 = unwrapped[i]
                u1 = unwrapped[i + 1]
                crossed = False
                if abs(u0 - crit_deg) <= 1e-12:
                    f_g, mdb_g = freqs[i], mag_db[i]
                    crossed = True
                elif (u0 > crit_deg and u1 <= crit_deg) or (u0 < crit_deg and u1 >= crit_deg):
                    f_g, frac = _log_interp_x(freqs[i], freqs[i + 1], u0, u1, crit_deg)
                    mdb_g = mag_db[i] + frac * (mag_db[i + 1] - mag_db[i])
                    crossed = True
                if crossed:
                    cand_gm = -mdb_g
                    gm_crossings.append({
                        "phase_deg": crit_deg,
                        "freq_hz": _round_clean(f_g),
                        "gain_margin_db": _round_clean(cand_gm),
                    })
                    if gm_db is None or cand_gm < gm_db:
                        gm_db = cand_gm
                        gm_freq_hz = f_g

        out.update({
            "stb_probe_signal": lg_key,
            "loop_dc_gain_db": _round_clean(loop_dc_gain_db),
            "stb_ugf_hz": _round_clean(primary_ugf),
            "phase_margin_deg": _round_clean(worst_pm),
            "gain_margin_db": _round_clean(gm_db),
            "gm_freq_hz": _round_clean(gm_freq_hz),
            "dc_positive_feedback": dc_pos_fb,
            "ugf_crossing_count": len(ugf_crossings),
        })
        if len(ugf_crossings) > 1:
            out["all_ugf_crossings"] = ugf_crossings
        if len(gm_crossings) > 1:
            out["all_gm_crossings"] = gm_crossings

    if margin_parsed:
        mvals, _ = _usable_waveform_values(margin_parsed)
        if out.get("phase_margin_deg") is None and "phaseMargin" in mvals and mvals["phaseMargin"]:
            out["phase_margin_deg"] = _round_clean(float(mvals["phaseMargin"][0].real))
        if out.get("stb_ugf_hz") is None and "phaseMarginFreq" in mvals and mvals["phaseMarginFreq"]:
            out["stb_ugf_hz"] = _round_clean(float(mvals["phaseMarginFreq"][0].real))
        if out.get("gain_margin_db") is None and "gainMargin" in mvals and mvals["gainMargin"]:
            out["gain_margin_db"] = _round_clean(float(mvals["gainMargin"][0].real))
        if out.get("gm_freq_hz") is None and "gainMarginFreq" in mvals and mvals["gainMarginFreq"]:
            out["gm_freq_hz"] = _round_clean(float(mvals["gainMarginFreq"][0].real))

    return out


def _interp_level_crossing(times, vals, start_idx, end_idx, target, rising=True):
    for i in range(start_idx, min(end_idx, len(vals) - 1)):
        v0, v1 = vals[i], vals[i + 1]
        cond = (v0 <= target < v1 or (v0 < target <= v1)) if rising else (v0 >= target > v1 or (v0 > target >= v1))
        if cond:
            if abs(v1 - v0) < 1e-30:
                return times[i]
            frac = (target - v0) / (v1 - v0)
            return times[i] + frac * (times[i + 1] - times[i])
    return None


def _analyze_step_segment(times, vals, seg_start, seg_end, settling_tol_ratio=0.01, t_trig=None):
    """Extract slew rate (10%-90%), overshoot %, and settled plateau settling time on a step window."""
    if seg_end - seg_start < 3:
        return {}
    t_win = times[seg_start:seg_end + 1]
    v_win = vals[seg_start:seg_end + 1]
    v_init = v_win[0]

    # Require >= 6 samples and flat tail plateau over at least max(3, N//10) points for settling_time_s
    tail_n = max(3, len(v_win) // 10) if len(v_win) >= 3 else len(v_win)
    v_final = sum(v_win[-tail_n:]) / float(tail_n)
    step_amp = v_final - v_init
    abs_step = abs(step_amp)
    if abs_step < 1e-9:
        return {}

    rising = (step_amp > 0.0)
    lvl_01 = v_init + 0.01 * step_amp
    lvl_10 = v_init + 0.10 * step_amp
    lvl_90 = v_init + 0.90 * step_amp

    t_onset = t_trig if t_trig is not None else _interp_level_crossing(t_win, v_win, 0, len(v_win) - 1, lvl_01, rising=rising)
    if t_onset is None:
        t_onset = t_win[0]

    t_10 = _interp_level_crossing(t_win, v_win, 0, len(v_win) - 1, lvl_10, rising=rising)
    t_90 = _interp_level_crossing(t_win, v_win, 0, len(v_win) - 1, lvl_90, rising=rising)
    sr_10_90 = None
    if t_10 is not None and t_90 is not None and (t_90 - t_10) > 1e-18:
        sr_10_90 = (0.80 * abs_step) / (t_90 - t_10)

    if rising:
        v_ext = max(v_win)
        overshoot_pct = max(0.0, (v_ext - v_final) / abs_step * 100.0)
    else:
        v_ext = min(v_win)
        overshoot_pct = max(0.0, (v_final - v_ext) / abs_step * 100.0)

    tol = settling_tol_ratio * abs_step
    tail_slice = v_win[-tail_n:]
    tail_span = max(tail_slice) - min(tail_slice)
    tail_settled = (
        len(v_win) >= 6
        and tail_span <= tol
        and all([abs(x - v_final) <= tol for x in tail_slice])
    )
    if not tail_settled:
        settling_time_s = None
    else:
        last_out = -1
        for k in range(len(v_win)):
            if abs(v_win[k] - v_final) > tol:
                last_out = k
        if last_out < 0:
            settling_time_s = 0.0
        elif last_out >= len(v_win) - 1:
            settling_time_s = None
        else:
            v_a = v_win[last_out]
            v_b = v_win[last_out + 1]
            bound = (v_final + tol) if v_a > v_final else (v_final - tol)
            if abs(v_b - v_a) > 1e-30:
                frac = (bound - v_a) / (v_b - v_a)
                frac = max(0.0, min(1.0, frac))
                t_enter = t_win[last_out] + frac * (t_win[last_out + 1] - t_win[last_out])
            else:
                t_enter = t_win[last_out + 1]
            settling_time_s = max(0.0, t_enter - t_onset)

    return {
        "rising": rising,
        "slew_rate": sr_10_90,
        "overshoot_pct": overshoot_pct,
        "settling_time_s": settling_time_s,
        "step_amplitude_v": abs_step,
    }


def _extract_tran_metrics(parsed, vout_hint=None, settling_tol_ratio=0.01):
    vals, rejected_bf = _usable_waveform_values(parsed)
    t_key = parsed.get("sweep_name") or _pick_signal_key(vals, ("time", "t"))
    if not t_key or t_key not in vals:
        return {"rejected_backfilled_signals": rejected_bf} if rejected_bf else {}
    times = [float(x.real) if isinstance(x, complex) else float(x) for x in vals[t_key]]
    if len(times) < 4:
        return {}

    if vout_hint and vout_hint in rejected_bf:
        return {
            "tran_output": vout_hint,
            "slew_rate_pos": None,
            "slew_rate_neg": None,
            "overshoot_pct": None,
            "settling_time_s": None,
            "ripple_pp": None,
            "step_detected": True,
            "rejected_backfilled_signals": rejected_bf,
        }

    vo_key = vout_hint if (vout_hint and vout_hint in vals) else _pick_signal_key(
        vals,
        ("vout", "out", "vo", "v_out", "y"),
        exclude=(t_key, "vin", "in", "vstep", "clk", "en", "vdd", "vss"),
    )
    if vo_key is None and not vout_hint:
        for k in sorted(vals.keys()):
            if k != t_key and vals[k] and not isinstance(vals[k][0], complex):
                vo_key = k
                break
    if not vo_key or len(vals[vo_key]) != len(times):
        return {"rejected_backfilled_signals": rejected_bf} if rejected_bf else {}

    vout = [float(x.real) if isinstance(x, complex) else float(x) for x in vals[vo_key]]

    t_span = times[-1] - times[0]
    t_tail_start = times[0] + 0.80 * t_span
    tail_vals = [vout[i] for i in range(len(times)) if times[i] >= t_tail_start]
    if not tail_vals:
        tail_vals = vout[-max(2, len(vout) // 5):]
    ripple_pp = max(tail_vals) - min(tail_vals)

    max_dvdt_pos = None
    max_dvdt_neg = None
    for i in range(len(times) - 1):
        dt = times[i + 1] - times[i]
        if dt <= 1e-18:
            continue
        slope = (vout[i + 1] - vout[i]) / dt
        if slope > 0.0 and (max_dvdt_pos is None or slope > max_dvdt_pos):
            max_dvdt_pos = slope
        elif slope < 0.0 and (max_dvdt_neg is None or (-slope) > max_dvdt_neg):
            max_dvdt_neg = -slope

    trig_key = _pick_signal_key(vals, ("vin", "vstep", "in", "iload", "i_load"), exclude=(t_key, vo_key))
    trig_vals = None
    if trig_key and len(vals[trig_key]) == len(times):
        trig_vals = [float(x.real) if isinstance(x, complex) else float(x) for x in vals[trig_key]]

    v_min = min(vout)
    v_max = max(vout)
    swing = v_max - v_min
    sr_pos = None
    sr_neg = None
    overshoot_pct = None
    settling_time_s = None
    step_detected = (swing > 1e-6)

    if step_detected:
        returns_near_init = (abs(vout[-1] - vout[0]) < 0.35 * swing)
        if returns_near_init:
            idx_ext = vout.index(v_max) if abs(v_max - vout[0]) >= abs(vout[0] - v_min) else vout.index(v_min)
            mid_lvl = 0.5 * (vout[idx_ext] + vout[-1])
            going_down = (vout[idx_ext] > vout[-1])
            split_idx = len(vout) // 2
            for k in range(idx_ext + 1, len(vout) - 1):
                if (going_down and vout[k] >= mid_lvl > vout[k + 1]) or (
                    (not going_down) and vout[k] <= mid_lvl < vout[k + 1]
                ):
                    split_idx = max(idx_ext + 1, k - max(1, (k - idx_ext) // 5))
                    break

            seg1 = _analyze_step_segment(times, vout, 0, split_idx, settling_tol_ratio=settling_tol_ratio)
            seg2 = _analyze_step_segment(times, vout, split_idx, len(vout) - 1, settling_tol_ratio=settling_tol_ratio)
            for seg in (seg1, seg2):
                if not seg:
                    continue
                if seg.get("rising") and seg.get("slew_rate") is not None:
                    sr_pos = seg["slew_rate"]
                elif (not seg.get("rising")) and seg.get("slew_rate") is not None:
                    sr_neg = seg["slew_rate"]
            overshoot_candidates = [s["overshoot_pct"] for s in (seg1, seg2) if s and s.get("overshoot_pct") is not None]
            if overshoot_candidates:
                overshoot_pct = max(overshoot_candidates)

            # Dual-edge strict guard: if both edges exist, BOTH must settle within tolerance
            nonempty_segs = [s for s in (seg1, seg2) if s]
            if nonempty_segs and all([s.get("settling_time_s") is not None for s in nonempty_segs]):
                settling_time_s = max([s["settling_time_s"] for s in nonempty_segs])
            else:
                settling_time_s = None
        else:
            t_trig = None
            if trig_vals is not None:
                tr_swing = max(trig_vals) - min(trig_vals)
                if tr_swing > 1e-9:
                    tr_rising = (trig_vals[-1] > trig_vals[0])
                    tr_mid = trig_vals[0] + 0.5 * (trig_vals[-1] - trig_vals[0])
                    t_trig = _interp_level_crossing(times, trig_vals, 0, len(times) - 1, tr_mid, rising=tr_rising)
            seg = _analyze_step_segment(
                times, vout, 0, len(vout) - 1, settling_tol_ratio=settling_tol_ratio, t_trig=t_trig
            )
            if seg:
                if seg.get("rising"):
                    sr_pos = seg.get("slew_rate")
                else:
                    sr_neg = seg.get("slew_rate")
                overshoot_pct = seg.get("overshoot_pct")
                settling_time_s = seg.get("settling_time_s")

    if sr_pos is None and max_dvdt_pos is not None and step_detected and vout[-1] >= vout[0]:
        sr_pos = max_dvdt_pos
    if sr_neg is None and max_dvdt_neg is not None and step_detected and vout[-1] <= vout[0]:
        sr_neg = max_dvdt_neg

    res = {
        "tran_output": vo_key,
        "slew_rate_pos": _round_clean(sr_pos),
        "slew_rate_neg": _round_clean(sr_neg),
        "overshoot_pct": _round_clean(overshoot_pct),
        "settling_time_s": _round_clean(settling_time_s),
        "ripple_pp": _round_clean(ripple_pp),
        "step_detected": step_detected,
    }
    if rejected_bf:
        res["rejected_backfilled_signals"] = rejected_bf
    return res


def _classify_noise_unit(unit_raw, sig_name):
    """Return `(domain, is_psd)` where domain in `('voltage', 'current', 'unknown')`."""
    u = str(unit_raw or "").strip().lower().replace(" ", "")
    is_psd = ("^2" in u or "**2" in u or "v2/" in u or "a2/" in u or "i2/" in u or u.endswith("v2") or u.endswith("a2"))
    if not u:
        sl = str(sig_name or "").strip().lower()
        if sl in ("vout_noise", "vnoise") or sl.startswith("v"):
            return "voltage", False
        if sl in ("inoise_a", "iout_noise") or sl.startswith("i_"):
            return "current", False
        if sl in ("onoise", "inoise", "out"):
            return "voltage", False
        return "unknown", False

    if (
        u.startswith("a/") or u.startswith("a^") or u.startswith("a*") or u.startswith("a2")
        or u.startswith("i^") or u.startswith("i*") or u.startswith("i2")
        or "amp" in u or u in ("a", "ma", "ua", "na", "pa")
    ):
        return "current", is_psd
    if (
        u.startswith("v/") or u.startswith("v^") or u.startswith("v*") or u.startswith("v2")
        or "volt" in u or u in ("v", "mv", "uv", "nv")
    ):
        return "voltage", is_psd
    return "unknown", is_psd


def _extract_noise_metrics(parsed):
    vals, rejected_bf = _usable_waveform_values(parsed)
    f_key = parsed.get("sweep_name") or _pick_signal_key(vals, ("freq", "frequency", "f"))
    if not f_key or f_key not in vals:
        return {"rejected_backfilled_signals": rejected_bf} if rejected_bf else {}
    freqs = [float(x.real) if isinstance(x, complex) else float(x) for x in vals[f_key]]
    if len(freqs) < 2:
        return {}
    n_key = _pick_signal_key(vals, ("out", "onoise", "inoise", "vout_noise", "iout_noise"), exclude=(f_key,))
    if not n_key or len(vals[n_key]) != len(freqs):
        return {"rejected_backfilled_signals": rejected_bf} if rejected_bf else {}

    raw = [abs(float(x.real) if isinstance(x, complex) else float(x)) for x in vals[n_key]]
    unit = str(parsed.get("field_units", {}).get(n_key, ""))
    if not unit:
        for tr in parsed.get("traces", []):
            if tr["name"] == n_key:
                unit = str(tr.get("props", {}).get("units", ""))
                if not unit and tr.get("type") in parsed.get("types", {}):
                    unit = str(parsed["types"][tr["type"]].get("props", {}).get("units", ""))
                break

    domain, is_psd = _classify_noise_unit(unit, n_key)
    if domain == "unknown":
        res = {
            "noise_signal": n_key,
            "noise_unit": unit,
            "integrated_rms_noise_v": None,
            "integrated_rms_noise_a": None,
        }
        if rejected_bf:
            res["rejected_backfilled_signals"] = rejected_bf
        return res

    psd = [v if is_psd else (v * v) for v in raw]
    integ = 0.0
    for i in range(len(freqs) - 1):
        df = freqs[i + 1] - freqs[i]
        if df > 0.0:
            integ += 0.5 * (psd[i] + psd[i + 1]) * df
    rms_val = _round_clean(math.sqrt(max(0.0, integ)))
    res = {
        "noise_signal": n_key,
        "noise_unit": unit,
        "noise_domain": domain,
        "integrated_rms_noise_v": rms_val if domain == "voltage" else None,
        "integrated_rms_noise_a": rms_val if domain == "current" else None,
    }
    if rejected_bf:
        res["rejected_backfilled_signals"] = rejected_bf
    return res


def _stb_loop_stem(filepath):
    bn = os.path.basename(filepath)
    low = bn.lower()
    for suf in (".margin.stb", ".stb", ".pstb"):
        if low.endswith(suf):
            return bn[:len(bn) - len(suf)] or "stb"
    return bn


def _extract_point_metrics(psf_files_by_kind, vout_hint=None, vin_hint=None, settling_tol_ratio=0.01):
    metrics = {
        "dc_power_w": None,
        "idd_a": None,
        "vdd_v": None,
        "dc_gain_db": None,
        "bw_3db_hz": None,
        "ugf_hz": None,
        "pm_ac_deg": None,
        "loop_dc_gain_db": None,
        "stb_ugf_hz": None,
        "phase_margin_deg": None,
        "gain_margin_db": None,
        "slew_rate_pos": None,
        "slew_rate_neg": None,
        "overshoot_pct": None,
        "settling_time_s": None,
        "ripple_pp": None,
        "integrated_rms_noise_v": None,
        "integrated_rms_noise_a": None,
    }
    analyses_present = []

    parsed_dc = []
    for p in psf_files_by_kind.get("dc", []):
        parsed_dc.append(parse_psf_file(p, reject_nonfinite=True, reject_truncated=True, fill_leading_missing=True))
    if parsed_dc:
        analyses_present.append("dc")
        metrics.update(_extract_dc_power(parsed_dc))

    # Process ALL `.ac` files in this point and aggregate worst-case (min gain/BW/UGF/PM)
    ac_runs = {}
    for p in psf_files_by_kind.get("ac", []):
        ac_res = _extract_ac_metrics(
            parse_psf_file(p, reject_nonfinite=True, reject_truncated=True, fill_leading_missing=True),
            vout_hint=vout_hint,
            vin_hint=vin_hint,
        )
        if ac_res:
            ac_runs[os.path.basename(p)] = ac_res
    if ac_runs:
        analyses_present.append("ac")
        for m_k in ("dc_gain_db", "bw_3db_hz", "ugf_hz", "pm_ac_deg"):
            vals_k = [r[m_k] for r in ac_runs.values() if isinstance(r.get(m_k), (int, float))]
            any_none = any([r.get(m_k) is None for r in ac_runs.values()])
            if vals_k and not any_none:
                metrics[m_k] = _round_clean(min(vals_k))
            elif len(ac_runs) == 1 and vals_k:
                metrics[m_k] = _round_clean(vals_k[0])
            else:
                metrics[m_k] = None
        first_ac = ac_runs[sorted(ac_runs.keys())[0]]
        if first_ac.get("ac_output"):
            metrics["ac_output"] = first_ac["ac_output"]
        if len(ac_runs) > 1:
            metrics["ac_runs"] = ac_runs

    # Process ALL `.stb` + `.margin.stb` loops (`dm.stb`, `cmfb.stb`, etc.) and take worst-case
    margin_by_stem = {}
    for mp in psf_files_by_kind.get("stb_margin", []):
        margin_by_stem[_stb_loop_stem(mp)] = parse_psf_file(
            mp, reject_nonfinite=True, reject_truncated=True, fill_leading_missing=True
        )

    stb_loops = {}
    used_margins = set()
    for sp in psf_files_by_kind.get("stb", []):
        stem = _stb_loop_stem(sp)
        m_parsed = margin_by_stem.get(stem)
        if m_parsed is not None:
            used_margins.add(stem)
        elif len(psf_files_by_kind.get("stb", [])) == 1 and len(margin_by_stem) == 1:
            only_m_stem = list(margin_by_stem.keys())[0]
            m_parsed = margin_by_stem[only_m_stem]
            used_margins.add(only_m_stem)
        s_parsed = parse_psf_file(sp, reject_nonfinite=True, reject_truncated=True, fill_leading_missing=True)
        s_res = _extract_stb_metrics(s_parsed, margin_parsed=m_parsed)
        if s_res:
            stb_loops[os.path.basename(sp)] = s_res

    for m_stem, m_parsed in sorted(margin_by_stem.items()):
        if m_stem not in used_margins:
            s_res = _extract_stb_metrics(None, margin_parsed=m_parsed)
            if s_res:
                stb_loops[m_stem + ".margin.stb"] = s_res

    if stb_loops:
        analyses_present.append("stb")
        for m_k in ("loop_dc_gain_db", "stb_ugf_hz", "phase_margin_deg", "gain_margin_db"):
            vals_k = [r[m_k] for r in stb_loops.values() if isinstance(r.get(m_k), (int, float))]
            # Fail closed if one loop failed to yield PM/UGF while claiming positive DC loop gain
            tainted = False
            if m_k in ("phase_margin_deg", "stb_ugf_hz") and len(stb_loops) > 1:
                for r in stb_loops.values():
                    if r.get(m_k) is None and (r.get("loop_dc_gain_db") is None or r.get("loop_dc_gain_db", -1.0) >= 0.0):
                        tainted = True
                        break
            if vals_k and not tainted:
                metrics[m_k] = _round_clean(min(vals_k))
            else:
                metrics[m_k] = None
        metrics["dc_positive_feedback"] = any([bool(r.get("dc_positive_feedback")) for r in stb_loops.values()])
        if len(stb_loops) == 1:
            only_stb = stb_loops[list(stb_loops.keys())[0]]
            for extra_k in ("stb_probe_signal", "gm_freq_hz", "ugf_crossing_count", "all_ugf_crossings", "all_gm_crossings"):
                if extra_k in only_stb:
                    metrics[extra_k] = only_stb[extra_k]
        else:
            metrics["stb_loops"] = stb_loops

    # Process ALL `.tran` files and aggregate worst-case; fail-closed on unsettled step
    tran_runs = {}
    for tp in psf_files_by_kind.get("tran", []):
        tr_res = _extract_tran_metrics(
            parse_psf_file(tp, reject_nonfinite=True, reject_truncated=True, fill_leading_missing=True),
            vout_hint=vout_hint,
            settling_tol_ratio=settling_tol_ratio,
        )
        if tr_res:
            tran_runs[os.path.basename(tp)] = tr_res
    if tran_runs:
        analyses_present.append("tran")
        for min_k in ("slew_rate_pos", "slew_rate_neg"):
            vals_k = [r[min_k] for r in tran_runs.values() if isinstance(r.get(min_k), (int, float))]
            metrics[min_k] = _round_clean(min(vals_k)) if vals_k else None
        for max_k in ("overshoot_pct", "ripple_pp"):
            vals_k = [r[max_k] for r in tran_runs.values() if isinstance(r.get(max_k), (int, float))]
            metrics[max_k] = _round_clean(max(vals_k)) if vals_k else None

        step_runs = [r for r in tran_runs.values() if r.get("step_detected")]
        if step_runs:
            if any([r.get("settling_time_s") is None for r in step_runs]):
                metrics["settling_time_s"] = None
            else:
                metrics["settling_time_s"] = _round_clean(max([r["settling_time_s"] for r in step_runs]))
        else:
            metrics["settling_time_s"] = None

        first_tr = tran_runs[sorted(tran_runs.keys())[0]]
        if first_tr.get("tran_output"):
            metrics["tran_output"] = first_tr["tran_output"]
        if len(tran_runs) > 1:
            metrics["tran_runs"] = tran_runs

    # Process ALL `.noise` files and aggregate worst-case (`max`) separately for V and A
    noise_runs = {}
    for np_file in psf_files_by_kind.get("noise", []):
        ns_res = _extract_noise_metrics(
            parse_psf_file(np_file, reject_nonfinite=True, reject_truncated=True, fill_leading_missing=True)
        )
        if ns_res:
            noise_runs[os.path.basename(np_file)] = ns_res
    if noise_runs:
        analyses_present.append("noise")
        for nk in ("integrated_rms_noise_v", "integrated_rms_noise_a"):
            vals_k = [r[nk] for r in noise_runs.values() if isinstance(r.get(nk), (int, float))]
            metrics[nk] = _round_clean(max(vals_k)) if vals_k else None
        if len(noise_runs) == 1:
            only_ns = noise_runs[list(noise_runs.keys())[0]]
            for extra_k in ("noise_signal", "noise_unit", "noise_domain"):
                if extra_k in only_ns:
                    metrics[extra_k] = only_ns[extra_k]
        else:
            metrics["noise_runs"] = noise_runs

    metrics["analyses_present"] = analyses_present
    return metrics


def _classify_psf_filename(filename):
    low = filename.lower()
    if low.endswith(".cdslck") or low.endswith(".log") or low.endswith(".json") or low.endswith(".scs"):
        return None
    if "margin" in low and low.endswith(".stb"):
        return "stb_margin"
    if low.endswith(".stb") or low.endswith(".pstb"):
        return "stb"
    if low.endswith(".ac") or low.endswith(".pac"):
        return "ac"
    if low.endswith(".tran"):
        return "tran"
    if low.endswith(".noise") or low.endswith(".pnoise"):
        return "noise"
    if low.endswith(".dc") or (low.endswith(".info") and ("op" in low or "dcop" in low)):
        return "dc"
    return None


def _discover_run_points(run_dir):
    if os.path.isfile(run_dir):
        kind = _classify_psf_filename(os.path.basename(run_dir)) or "tran"
        return {"nominal": {kind: [run_dir]}}
    if not os.path.isdir(run_dir):
        raise ValueError("Run directory not found: " + str(run_dir))

    point_map = {}
    for root, dirs, files in os.walk(run_dir):
        dirs.sort()
        rel = os.path.relpath(root, run_dir).replace(os.sep, "/")
        parts = [p for p in rel.split("/") if p not in (".", "psf", "raw")]
        base_label = "/".join(parts) if parts else "nominal"

        for fn in sorted(files):
            kind = _classify_psf_filename(fn)
            if not kind:
                continue
            full_p = os.path.join(root, fn)
            m_flat = re.match(r'^(sw\d+-\d+)_.+$', fn)
            if m_flat:
                pt_label = "%s/%s" % (base_label, m_flat.group(1)) if base_label != "nominal" else m_flat.group(1)
            else:
                pt_label = base_label
            point_map.setdefault(pt_label, {}).setdefault(kind, []).append(full_p)

    return point_map


# ---------------------------------------------------------------------------
# Strict Fail-Closed Spec Evaluation (`PASS` / `FAIL` / `NOT_VERIFIED`)
# ---------------------------------------------------------------------------

def _resolve_metric_key(quantity_name, metrics_dict):
    """Resolve canonical metric key WITHOUT ever substituting `.ac` PM for `.stb` PM."""
    q_clean = re.sub(r'[^a-z0-9_]', '_', str(quantity_name).strip().lower()).strip('_')
    for canon, aliases in METRIC_KEY_ALIASES.items():
        if q_clean == canon or q_clean in aliases:
            return canon
    if q_clean in metrics_dict:
        return q_clean
    return q_clean


def _scale_target_to_si(target_val, unit_str):
    """Return `(scaled_float, error_reason_or_None)`. Unknown units fail closed (`None, 'unknown_unit'`)."""
    if target_val is None:
        return None, None
    raw_u = str(unit_str or "").strip().replace(" ", "")
    if raw_u in UNIT_SCALE_CASE_SENSITIVE:
        return float(target_val) * UNIT_SCALE_CASE_SENSITIVE[raw_u], None
    u_key = raw_u.lower()
    if u_key not in UNIT_SCALE_TO_SI:
        return None, "unknown_unit"
    return float(target_val) * UNIT_SCALE_TO_SI[u_key], None


def _compare_op(measured, operator, target_si, target_max_si=None):
    op = str(operator or ">=").strip().lower()
    rel_tol = 1e-12 * max(abs(target_si), 1e-30)
    if op in (">=", "min", "ge", "gte"):
        return measured >= target_si - rel_tol
    if op in (">", "gt"):
        return measured > target_si
    if op in ("<=", "max", "le", "lte"):
        return measured <= target_si + rel_tol
    if op in ("<", "lt"):
        return measured < target_si
    if op in ("==", "=", "eq"):
        tol = 0.01 * max(1e-30, abs(target_si))
        return abs(measured - target_si) <= tol
    if op in ("range", "between", "in") and target_max_si is not None:
        if target_si > target_max_si:
            return None
        tol_lo = 1e-12 * max(abs(target_si), 1e-30)
        tol_hi = 1e-12 * max(abs(target_max_si), 1e-30)
        return (measured >= target_si - tol_lo) and (measured <= target_max_si + tol_hi)
    return None


def _extract_condition_list(obj):
    """Extract condition/corner labels from a string, list of strings/dicts, or dict."""
    if obj is None:
        return []
    out = []
    if isinstance(obj, TEXT_TYPES):
        for tok in str(obj).split(","):
            t = tok.strip()
            if t:
                out.append(t)
        return out
    if isinstance(obj, list):
        for elem in obj:
            if isinstance(elem, TEXT_TYPES):
                t = str(elem).strip()
                if t:
                    out.append(t)
            elif isinstance(elem, dict):
                nm = elem.get("name") or elem.get("corner") or elem.get("id") or elem.get("label")
                if nm:
                    out.append(str(nm).strip())
        return out
    if isinstance(obj, dict):
        for k in ("corners", "conditions", "corner", "condition", "name", "id"):
            if k in obj:
                out.extend(_extract_condition_list(obj[k]))
    return out


def _extract_req_conditions(item):
    conds = []
    for k in ("conditions", "condition", "corners", "corner"):
        if k in item and item[k] is not None:
            conds.extend(_extract_condition_list(item[k]))
    seen = set()
    dedup = []
    for c in conds:
        if c not in seen:
            seen.add(c)
            dedup.append(c)
    return dedup


def _extract_global_conditions(spec_obj):
    if not isinstance(spec_obj, dict):
        return []
    conds = []
    for k in ("corners", "conditions"):
        if k in spec_obj:
            conds.extend(_extract_condition_list(spec_obj[k]))
    cov = spec_obj.get("coverage")
    if isinstance(cov, dict):
        for k in ("corners", "conditions"):
            if k in cov:
                conds.extend(_extract_condition_list(cov[k]))
    seen = set()
    dedup = []
    for c in conds:
        if c not in seen:
            seen.add(c)
            dedup.append(c)
    return dedup


def _extract_global_analyses(spec_obj):
    if not isinstance(spec_obj, dict):
        return []
    cov = spec_obj.get("coverage")
    raw = []
    if isinstance(cov, dict) and "analyses" in cov:
        raw.extend(_extract_condition_list(cov["analyses"]))
    if "analyses" in spec_obj:
        raw.extend(_extract_condition_list(spec_obj["analyses"]))
    return [x.lower() for x in raw if x]


def _is_spec_approval_pending(spec_obj):
    if not isinstance(spec_obj, dict) or "approval" not in spec_obj:
        return False
    app = spec_obj.get("approval")
    unapproved_tokens = ("pending", "draft", "unapproved", "false", "rejected", "no", "0")
    if isinstance(app, bool):
        return not app
    if isinstance(app, TEXT_TYPES):
        return str(app).strip().lower() in unapproved_tokens
    if isinstance(app, dict):
        if "approved" in app and isinstance(app["approved"], bool) and (not app["approved"]):
            return True
        st = app.get("status")
        if isinstance(st, bool) and (not st):
            return True
        if isinstance(st, TEXT_TYPES) and str(st).strip().lower() in unapproved_tokens:
            return True
    return False


def _match_condition_keys(req_cond, available_keys):
    """Match a required corner/condition label (e.g. `SS`, `TT_27C`) against discovered point keys."""
    rc = str(req_cond).strip()
    rc_low = rc.lower()
    exact = [k for k in available_keys if k == rc or k.lower() == rc_low]
    if exact:
        return sorted(exact)
    rc_tokens = [t for t in re.split(r'[/_\-\s]+', rc_low) if t]
    if not rc_tokens:
        return []
    matched = []
    for k in sorted(available_keys):
        k_tokens = set([t for t in re.split(r'[/_\-\s]+', k.lower()) if t])
        if all([rt in k_tokens for rt in rc_tokens]):
            matched.append(k)
    return matched


def _normalize_spec_requirements(spec_obj):
    reqs = []
    if isinstance(spec_obj, dict) and isinstance(spec_obj.get("requirements"), list) and spec_obj["requirements"]:
        for idx, item in enumerate(spec_obj["requirements"]):
            if not isinstance(item, dict):
                continue
            op = item.get("operator") or item.get("op")
            tgt = item.get("target")
            tgt_max = item.get("target_max")
            if "min" in item and "max" in item and item["min"] is not None and item["max"] is not None:
                op = "range"
                tgt = item["min"]
                tgt_max = item["max"]
            elif isinstance(tgt, (list, tuple)) and len(tgt) == 2 and (op is None or str(op).lower() in ("range", "between", "in")):
                op = "range"
                tgt_max = tgt[1]
                tgt = tgt[0]
            elif op is None:
                if "min" in item and item["min"] is not None:
                    op, tgt = ">=", item["min"]
                elif "max" in item and item["max"] is not None:
                    op, tgt = "<=", item["max"]
                else:
                    op = ">="
            reqs.append({
                "id": item.get("id", "REQ-%02d" % (idx + 1)),
                "quantity": item.get("quantity") or item.get("metric") or item.get("name") or "",
                "operator": op,
                "target": tgt,
                "target_max": tgt_max,
                "unit": item.get("unit", ""),
                "conditions": _extract_req_conditions(item),
                "analysis": str(item["analysis"]).strip().lower() if item.get("analysis") else None,
            })
        return reqs

    for list_key in ("hard_constraints", "constraints", "targets"):
        if isinstance(spec_obj, dict) and isinstance(spec_obj.get(list_key), list) and spec_obj[list_key]:
            for idx, item in enumerate(spec_obj[list_key]):
                if not isinstance(item, dict):
                    continue
                op = item.get("operator") or item.get("op")
                tgt = item.get("target")
                tgt_max = item.get("target_max")
                if "min" in item and "max" in item and item["min"] is not None and item["max"] is not None:
                    op = "range"
                    tgt = item["min"]
                    tgt_max = item["max"]
                elif op is None:
                    if "min" in item and item["min"] is not None:
                        op, tgt = ">=", item["min"]
                    elif "max" in item and item["max"] is not None:
                        op, tgt = "<=", item["max"]
                    else:
                        op = ">="
                reqs.append({
                    "id": item.get("id", "REQ-%02d" % (idx + 1)),
                    "quantity": item.get("quantity", item.get("metric", item.get("name", ""))),
                    "operator": op,
                    "target": tgt,
                    "target_max": tgt_max,
                    "unit": item.get("unit", ""),
                    "conditions": _extract_req_conditions(item),
                    "analysis": str(item["analysis"]).strip().lower() if item.get("analysis") else None,
                })
            return reqs

    src = spec_obj.get("targets") if (isinstance(spec_obj, dict) and isinstance(spec_obj.get("targets"), dict)) else spec_obj
    if isinstance(src, dict):
        skip_meta = set([
            "schema", "revision", "approval", "user_theory_constraints", "design_constraints",
            "requirements", "coverage", "measurement_contract", "notes", "optimization",
            "corners", "conditions", "analyses",
        ])
        idx = 0
        for key in sorted(src.keys()):
            if key in skip_meta:
                continue
            val = src[key]
            idx += 1
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                default_op = "<=" if any([t in key.lower() for t in ("power", "idd", "overshoot", "settl", "ripple", "noise")]) else ">="
                reqs.append({
                    "id": "REQ-%02d" % idx,
                    "quantity": key,
                    "operator": default_op,
                    "target": val,
                    "target_max": None,
                    "unit": "",
                    "conditions": [],
                    "analysis": None,
                })
            elif isinstance(val, dict):
                unit = val.get("unit", "")
                req_conds = _extract_req_conditions(val)
                req_an = str(val["analysis"]).strip().lower() if val.get("analysis") else None
                if "min" in val and "max" in val and val["min"] is not None and val["max"] is not None:
                    reqs.append({
                        "id": val.get("id", "REQ-%02d" % idx),
                        "quantity": key,
                        "operator": "range",
                        "target": val["min"],
                        "target_max": val["max"],
                        "unit": unit,
                        "conditions": req_conds,
                        "analysis": req_an,
                    })
                elif "operator" in val and "target" in val:
                    reqs.append({
                        "id": val.get("id", "REQ-%02d" % idx),
                        "quantity": key,
                        "operator": val["operator"],
                        "target": val["target"],
                        "target_max": val.get("target_max"),
                        "unit": unit,
                        "conditions": req_conds,
                        "analysis": req_an,
                    })
                else:
                    sub_ops = [op_c for op_c in (">=", "<=", ">", "<", "==", "min", "max") if op_c in val]
                    for s_i, op_cand in enumerate(sub_ops):
                        rid = val.get("id", "REQ-%02d" % idx)
                        if len(sub_ops) > 1:
                            rid = "%s-%d" % (rid, s_i + 1)
                        reqs.append({
                            "id": rid,
                            "quantity": key,
                            "operator": op_cand,
                            "target": val[op_cand],
                            "target_max": None,
                            "unit": unit,
                            "conditions": req_conds,
                            "analysis": req_an,
                        })
    return reqs


def evaluate_spec(points_metrics, spec_obj):
    approval_pending = _is_spec_approval_pending(spec_obj)
    global_conds = _extract_global_conditions(spec_obj)
    global_analyses = _extract_global_analyses(spec_obj)
    reqs = _normalize_spec_requirements(spec_obj)

    if not reqs:
        out = {
            "verdict": "NOT_VERIFIED",
            "requirements_count": 0,
            "pass_count": 0,
            "fail_count": 0,
            "not_verified_count": 0,
            "results": [],
        }
        if approval_pending:
            out["reason"] = "spec_approval_pending"
        else:
            out["reason"] = "no_requirements"
        return out

    available_keys = sorted(points_metrics.keys())
    missing_global_analyses = []
    for req_an in global_analyses:
        an_norm = "stb" if req_an in ("pstb", "stb") else ("ac" if req_an in ("pac", "ac") else ("noise" if req_an in ("pnoise", "noise") else req_an))
        for pk in available_keys:
            present = points_metrics[pk].get("analyses_present", [])
            if an_norm not in present and req_an not in missing_global_analyses:
                missing_global_analyses.append(req_an)

    results = []
    pass_n = 0
    fail_n = 0
    nv_n = 0

    for req in reqs:
        if req["target"] is None:
            nv_n += 1
            results.append({
                "id": req["id"],
                "quantity": req["quantity"],
                "status": "NOT_VERIFIED",
                "reason": "missing_target",
            })
            continue

        target_si, unit_err = _scale_target_to_si(req["target"], req.get("unit", ""))
        target_max_si, unit_max_err = _scale_target_to_si(req.get("target_max"), req.get("unit", ""))
        if unit_err or unit_max_err:
            nv_n += 1
            results.append({
                "id": req["id"],
                "quantity": req["quantity"],
                "operator": req["operator"],
                "target": req["target"],
                "unit": req.get("unit", ""),
                "status": "NOT_VERIFIED",
                "reason": "unknown_unit",
            })
            continue

        op = req["operator"]
        req_conds = req.get("conditions") or []
        req_an = req.get("analysis")

        per_cond = {}
        missing_conds = []
        eval_keys = []

        if req_conds:
            seen_ek = set()
            for rc in req_conds:
                matched_ks = _match_condition_keys(rc, available_keys)
                if not matched_ks:
                    missing_conds.append(rc)
                    per_cond[rc] = {"measured_si": None, "status": "NOT_VERIFIED", "reason": "missing_condition"}
                else:
                    for mk in matched_ks:
                        if mk not in seen_ek:
                            seen_ek.add(mk)
                            eval_keys.append(mk)
        else:
            eval_keys = list(available_keys)
            for gc in global_conds:
                matched_ks = _match_condition_keys(gc, available_keys)
                if not matched_ks:
                    missing_conds.append(gc)
                    per_cond[gc] = {"measured_si": None, "status": "NOT_VERIFIED", "reason": "missing_condition"}

        worst_cond = None
        worst_val = None
        any_missing = len(missing_conds) > 0
        any_failed = False
        req_reason = "missing_condition" if missing_conds else None

        for cond_name in eval_keys:
            m_dict = points_metrics[cond_name]
            if req_an:
                an_norm = "stb" if req_an in ("pstb", "stb") else ("ac" if req_an in ("pac", "ac") else ("noise" if req_an in ("pnoise", "noise") else req_an))
                if an_norm not in m_dict.get("analyses_present", []):
                    any_missing = True
                    req_reason = req_reason or "missing_analysis"
                    per_cond[cond_name] = {"measured_si": None, "status": "NOT_VERIFIED", "reason": "missing_analysis"}
                    continue

            m_key = _resolve_metric_key(req["quantity"], m_dict)
            m_val = m_dict.get(m_key)
            if m_val is None:
                any_missing = True
                req_reason = req_reason or "missing_metric"
                per_cond[cond_name] = {"measured_si": None, "status": "NOT_VERIFIED", "reason": "missing_metric"}
                continue

            ok_cmp = _compare_op(float(m_val), op, target_si, target_max_si=target_max_si)
            if ok_cmp is None:
                any_missing = True
                req_reason = req_reason or "invalid_operator_or_range"
                per_cond[cond_name] = {"measured_si": _round_clean(m_val), "status": "NOT_VERIFIED", "reason": "invalid_operator_or_range"}
                continue

            st = "PASS" if ok_cmp else "FAIL"
            if not ok_cmp:
                any_failed = True
            per_cond[cond_name] = {"measured_si": _round_clean(m_val), "status": st}

            if op in (">=", ">", "min", "ge", "gte", "gt"):
                if worst_val is None or float(m_val) < worst_val:
                    worst_val = float(m_val)
                    worst_cond = cond_name
            elif op in ("<=", "<", "max", "le", "lte", "lt"):
                if worst_val is None or float(m_val) > worst_val:
                    worst_val = float(m_val)
                    worst_cond = cond_name
            elif op in ("range", "between", "in") and target_max_si is not None:
                mid = 0.5 * (target_si + target_max_si)
                if worst_val is None or abs(float(m_val) - mid) > abs(worst_val - mid):
                    worst_val = float(m_val)
                    worst_cond = cond_name
            else:
                if worst_val is None or abs(float(m_val) - target_si) > abs(worst_val - target_si):
                    worst_val = float(m_val)
                    worst_cond = cond_name

        if any_failed:
            req_status = "FAIL"
            fail_n += 1
        elif any_missing or worst_val is None:
            req_status = "NOT_VERIFIED"
            nv_n += 1
        else:
            req_status = "PASS"
            pass_n += 1

        entry = {
            "id": req["id"],
            "quantity": req["quantity"],
            "operator": op,
            "target": req["target"],
            "unit": req.get("unit", ""),
            "target_si": _round_clean(target_si),
            "worst_case_si": _round_clean(worst_val),
            "worst_condition": worst_cond,
            "status": req_status,
            "conditions": per_cond,
        }
        if target_max_si is not None:
            entry["target_max"] = req.get("target_max")
            entry["target_max_si"] = _round_clean(target_max_si)
        if missing_conds:
            entry["missing_conditions"] = missing_conds
        if req_status == "NOT_VERIFIED" and req_reason:
            entry["reason"] = req_reason
        results.append(entry)

    overall_reason = None
    if fail_n > 0:
        verdict = "FAIL"
    elif approval_pending:
        verdict = "NOT_VERIFIED"
        overall_reason = "spec_approval_pending"
    elif missing_global_analyses:
        verdict = "NOT_VERIFIED"
        overall_reason = "missing_required_analyses"
    elif nv_n > 0:
        verdict = "NOT_VERIFIED"
        overall_reason = "incomplete_verification"
    else:
        verdict = "PASS"

    summary_out = {
        "verdict": verdict,
        "approval_pending": approval_pending,
        "requirements_count": len(results),
        "pass_count": pass_n,
        "fail_count": fail_n,
        "not_verified_count": nv_n,
        "results": results,
    }
    if overall_reason:
        summary_out["reason"] = overall_reason
    if missing_global_analyses:
        summary_out["missing_analyses"] = missing_global_analyses
    return summary_out


def run_metrics(run_dir, spec_path=None, vout_hint=None, vin_hint=None, settling_tol_ratio=0.01):
    point_files = _discover_run_points(run_dir)
    if not point_files:
        raise ValueError("No PSF ASCII simulation files found under: " + str(run_dir))

    points_metrics = {}
    for pt_label in sorted(point_files.keys()):
        points_metrics[pt_label] = _extract_point_metrics(
            point_files[pt_label],
            vout_hint=vout_hint,
            vin_hint=vin_hint,
            settling_tol_ratio=settling_tol_ratio,
        )

    primary_label = "nominal" if "nominal" in points_metrics else sorted(points_metrics.keys())[0]
    worst_case = {}
    low_is_worse = set([
        "dc_gain_db", "bw_3db_hz", "ugf_hz", "pm_ac_deg",
        "loop_dc_gain_db", "stb_ugf_hz", "phase_margin_deg", "gain_margin_db",
        "slew_rate_pos", "slew_rate_neg",
    ])
    high_is_worse = set([
        "dc_power_w", "idd_a", "overshoot_pct", "settling_time_s",
        "ripple_pp", "integrated_rms_noise_v", "integrated_rms_noise_a",
    ])

    for m_key in sorted(list(low_is_worse | high_is_worse)):
        vals = [pm.get(m_key) for pm in points_metrics.values() if isinstance(pm.get(m_key), (int, float))]
        if vals and len(vals) == len(points_metrics):
            worst_case[m_key] = _round_clean(min(vals) if m_key in low_is_worse else max(vals))
        elif vals:
            worst_case[m_key] = None

    payload = {
        "command": "metrics",
        "ok": True,
        "run_dir": os.path.realpath(run_dir),
        "point_count": len(points_metrics),
        "metrics": points_metrics[primary_label],
        "worst_case": worst_case,
    }
    if len(points_metrics) > 1 or primary_label != "nominal":
        payload["points"] = points_metrics

    if spec_path is not None:
        if not os.path.isfile(spec_path):
            raise ValueError("Spec file not found: " + str(spec_path))
        s_handle = open(spec_path, "rb")
        try:
            spec_obj = json.loads(s_handle.read().decode("utf-8-sig"))
        finally:
            s_handle.close()
        spec_eval = evaluate_spec(points_metrics, spec_obj)
        payload["spec_path"] = os.path.realpath(spec_path)
        payload["verdict"] = spec_eval["verdict"]
        payload["spec_evaluation"] = spec_eval
    else:
        payload["verdict"] = "NOT_VERIFIED"

    return payload


# ---------------------------------------------------------------------------
# Comprehensive Adversarial Self-Test (`--self-test` / `self-test`)
# ---------------------------------------------------------------------------

def _write_utf8(path, text):
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    fh = open(path, "wb")
    try:
        fh.write(text.encode("utf-8"))
    finally:
        fh.close()


def run_self_test():
    tmp_root = tempfile.mkdtemp(prefix="psf_audit_selftest_")
    try:
        # 1. MOS OP Fail-Closed Tests (missing region/vdsat, tight headroom 20mV < 50mV, empty corner point)
        op_missing_psf = os.path.join(tmp_root, "op_missing.info")
        _write_utf8(op_missing_psf, (
            'HEADER\n"PSFversion" "1.00"\n'
            'TYPE\n"bsim4" STRUCT( "gm" FLOAT DOUBLE "vds" FLOAT DOUBLE "ids" FLOAT DOUBLE )\n'
            'VALUE\n"M1" "bsim4" ( 1.0e-3 0.5 1.0e-4 )\nEND\n'
        ))
        rep_missing = run_op_audit(op_missing_psf, vds_margin=0.05)
        assert rep_missing["status"] == "NOT_VERIFIED", rep_missing
        assert rep_missing["audit_pass"] is False, rep_missing

        op_tight_psf = os.path.join(tmp_root, "op_tight.info")
        _write_utf8(op_tight_psf, (
            'HEADER\n"PSFversion" "1.00"\n'
            'TYPE\n"bsim4" STRUCT( "gm" FLOAT DOUBLE "vds" FLOAT DOUBLE "vdsat" FLOAT DOUBLE "ids" FLOAT DOUBLE "region" INT LONG )\n'
            'VALUE\n"M1" "bsim4" ( 1.0e-3 0.12 0.10 1.0e-4 2 )\nEND\n'
        ))
        rep_tight = run_op_audit(op_tight_psf, vds_margin=0.05)
        assert rep_tight["status"] == "WARN", rep_tight
        assert rep_tight["audit_pass"] is False, rep_tight

        # Multi-point OP where TT passes and SS has 0 MOS devices -> NOT_VERIFIED, audit_pass=False
        mp_dir = os.path.join(tmp_root, "mp_op")
        _write_utf8(os.path.join(mp_dir, "TT", "dcOpInfo.info"), (
            'HEADER\n"PSFversion" "1.00"\n'
            'TYPE\n"bsim4" STRUCT( "gm" FLOAT DOUBLE "vds" FLOAT DOUBLE "vdsat" FLOAT DOUBLE "ids" FLOAT DOUBLE "region" INT LONG )\n'
            'VALUE\n"M1" "bsim4" ( 1.0e-3 0.35 0.10 1.0e-4 2 )\nEND\n'
        ))
        _write_utf8(os.path.join(mp_dir, "SS", "dcOpInfo.info"), (
            'HEADER\n"PSFversion" "1.00"\nTYPE\n"node" FLOAT DOUBLE\nVALUE\n"vdd" 1.0\nEND\n'
        ))
        rep_mp = run_op_audit(mp_dir, vds_margin=0.05)
        assert rep_mp["status"] == "NOT_VERIFIED", rep_mp
        assert rep_mp["audit_pass"] is False, rep_mp

        # 2. Corner Coverage, Approval Pending, No AC-for-STB Substitution, Unknown Units, Sub-ps Tolerance, Range
        cov_dir = os.path.join(tmp_root, "cov_run")
        _write_utf8(os.path.join(cov_dir, "TT", "ac.ac"), (
            'HEADER\n"PSFversion" "1.00"\n'
            'TYPE\n"f_t" FLOAT DOUBLE\n"c_t" COMPLEX DOUBLE\n'
            'SWEEP\n"freq" "f_t"\n'
            'TRACE\n"Vout" "c_t"\n'
            'VALUE\n'
            '"freq" 1.0\n"Vout" (1000.0 0.0)\n'
            '"freq" 1.0e6\n"Vout" (0.0 -1.0)\n'
            '"freq" 1.0e7\n"Vout" (-0.05 -0.05)\n'
            'END\n'
        ))
        # Spec asks for PM >= 60 deg without `.stb` (only `.ac` exists) -> MUST be NOT_VERIFIED
        spec_pm = {"requirements": [{"id": "PM1", "quantity": "pm", "operator": ">=", "target": 60, "unit": "deg"}]}
        spec_pm_path = os.path.join(tmp_root, "spec_pm.json")
        _write_utf8(spec_pm_path, json.dumps(spec_pm))
        res_pm = run_metrics(os.path.join(cov_dir, "TT"), spec_path=spec_pm_path)
        assert res_pm["metrics"]["pm_ac_deg"] is not None, res_pm
        assert res_pm["metrics"]["phase_margin_deg"] is None, res_pm
        assert res_pm["verdict"] == "NOT_VERIFIED", res_pm
        assert main(["metrics", os.path.join(cov_dir, "TT"), "--spec", spec_pm_path, "--fail-on-spec"], quiet=True) == 1

        # Spec requires TT and SS, run only has TT -> NOT_VERIFIED
        spec_corners = {
            "corners": ["TT", "SS"],
            "requirements": [{"id": "G1", "quantity": "dc_gain_db", "operator": ">=", "target": 50, "unit": "dB"}],
        }
        spec_corners_path = os.path.join(tmp_root, "spec_corners.json")
        _write_utf8(spec_corners_path, json.dumps(spec_corners))
        res_corners = run_metrics(cov_dir, spec_path=spec_corners_path)
        assert res_corners["verdict"] == "NOT_VERIFIED", res_corners
        assert "SS" in res_corners["spec_evaluation"]["results"][0]["missing_conditions"]

        # Per-requirement `condition: "SS"` and `approval: "pending"` -> NOT_VERIFIED
        spec_pending = {
            "approval": {"status": "pending"},
            "requirements": [{"id": "G_SS", "quantity": "dc_gain_db", "operator": ">=", "target": 50, "unit": "dB", "condition": "SS"}],
        }
        eval_pend = evaluate_spec({"TT": {"dc_gain_db": 60.0, "analyses_present": ["ac"]}}, spec_pending)
        assert eval_pend["verdict"] == "NOT_VERIFIED", eval_pend
        assert eval_pend["results"][0]["status"] == "NOT_VERIFIED", eval_pend

        # Approval pending even when all requirements pass -> verdict NOT_VERIFIED, reason spec_approval_pending
        eval_pend_pass = evaluate_spec(
            {"TT": {"dc_gain_db": 60.0, "analyses_present": ["ac"]}},
            {"approval": "pending", "requirements": [{"id": "G_TT", "quantity": "dc_gain_db", "operator": ">=", "target": 50, "unit": "dB"}]},
        )
        assert eval_pend_pass["verdict"] == "NOT_VERIFIED", eval_pend_pass
        assert eval_pend_pass["reason"] == "spec_approval_pending", eval_pend_pass

        # Sub-ps strict comparison: 1.1 ps <= 1.0 ps MUST FAIL!
        eval_ps = evaluate_spec(
            {"TT": {"settling_time_s": 1.1e-12, "analyses_present": ["tran"]}},
            {"requirements": [{"id": "TS1", "quantity": "settling_time_s", "operator": "<=", "target": 1.0, "unit": "ps"}]},
        )
        assert eval_ps["verdict"] == "FAIL", eval_ps

        # Unknown unit -> NOT_VERIFIED (never multiplied by 1.0!)
        eval_unk = evaluate_spec(
            {"TT": {"dc_gain_db": 60.0, "analyses_present": ["ac"]}},
            {"requirements": [{"id": "U1", "quantity": "dc_gain_db", "operator": ">=", "target": 50, "unit": "dB_typo"}]},
        )
        assert eval_unk["verdict"] == "NOT_VERIFIED", eval_unk
        assert eval_unk["results"][0]["reason"] == "unknown_unit", eval_unk

        # Range constraint (`min` + `max`) in constraints list and targets dict
        eval_rng = evaluate_spec(
            {"TT": {"dc_gain_db": 75.0, "analyses_present": ["ac"]}},
            {"constraints": [{"id": "R1", "quantity": "dc_gain_db", "min": 50.0, "max": 70.0, "unit": "dB"}]},
        )
        assert eval_rng["verdict"] == "FAIL", eval_rng

        # 3. Multi-Loop `.stb` (`dm.stb` PM=68, `cmfb.stb` PM=22) + `-540 deg` Gain Margin Crossing
        stb_dir = os.path.join(tmp_root, "stb_multi")
        _write_utf8(os.path.join(stb_dir, "dm.stb"), (
            'HEADER\n"PSFversion" "1.00"\nTYPE\n"f_t" FLOAT DOUBLE\n"c_t" COMPLEX DOUBLE\n'
            'SWEEP\n"freq" "f_t"\nTRACE\n"loopGain" "c_t"\nVALUE\n'
            '"freq" 1.0\n"loopGain" (1000.0 0.0)\n'
            '"freq" 1.0e6\n"loopGain" (0.3746 -0.9272)\n'
            '"freq" 1.0e7\n"loopGain" (-0.1 0.0)\n'
            'END\n'
        ))
        # cmfb.stb: crosses 0 dB with PM ~ 22 deg, then spirals to -540 deg with |T| = 2.0 (+6.02 dB -> GM = -6.02 dB!)
        # Walk 60 deg steps clockwise so phase unwraps cleanly down to -540 deg
        _write_utf8(os.path.join(stb_dir, "cmfb.stb"), (
            'HEADER\n"PSFversion" "1.00"\nTYPE\n"f_t" FLOAT DOUBLE\n"c_t" COMPLEX DOUBLE\n'
            'SWEEP\n"freq" "f_t"\nTRACE\n"loopGain" "c_t"\nVALUE\n'
            '"freq" 1.0\n"loopGain" (500.0 0.0)\n'
            '"freq" 1.0e5\n"loopGain" (5.0 -8.66025)\n'
            '"freq" 5.0e5\n"loopGain" (-0.92718 -0.37461)\n'
            '"freq" 1.0e6\n"loopGain" (-0.5 0.0)\n'
            '"freq" 2.0e6\n"loopGain" (-0.25 0.43301)\n'
            '"freq" 4.0e6\n"loopGain" (0.25 0.43301)\n'
            '"freq" 8.0e6\n"loopGain" (0.5 0.0)\n'
            '"freq" 1.5e7\n"loopGain" (0.5 -0.866025)\n'
            '"freq" 3.0e7\n"loopGain" (-1.0 -1.73205)\n'
            '"freq" 5.0e7\n"loopGain" (-2.0 0.0)\n'
            '"freq" 8.0e7\n"loopGain" (-0.5 0.866025)\n'
            'END\n'
        ))
        res_stb = run_metrics(stb_dir)
        assert res_stb["metrics"]["phase_margin_deg"] < 25.0, res_stb["metrics"]
        assert res_stb["metrics"]["gain_margin_db"] < -5.5, res_stb["metrics"]
        assert "stb_loops" in res_stb["metrics"], res_stb["metrics"]

        # 4. Unsettled Linear Ramp (0 -> 80 mV) MUST return settling_time_s = None
        ramp_psf = os.path.join(tmp_root, "ramp.tran")
        ramp_lines = ['HEADER\n"PSFversion" "1.00"\nTYPE\n"r_t" FLOAT DOUBLE\nSWEEP\n"time" "r_t"\nTRACE\n"Vout" "r_t"\nVALUE\n']
        for k in range(20):
            t_k = k * 1.0e-9
            v_k = 0.08 * (float(k) / 19.0)
            ramp_lines.append('"time" %.6e\n"Vout" %.6e\n' % (t_k, v_k))
        ramp_lines.append("END\n")
        _write_utf8(ramp_psf, "".join(ramp_lines))
        res_ramp = run_metrics(ramp_psf)
        assert res_ramp["metrics"]["settling_time_s"] is None, res_ramp["metrics"]

        # 5. Multi-Rail DC Power (`1.0V*1uA + 1.8V*2mA = 3.601 mW`) + Current Noise (`A/sqrt(Hz)`)
        mr_dir = os.path.join(tmp_root, "multirail")
        _write_utf8(os.path.join(mr_dir, "dcOp.dc"), (
            'HEADER\n"PSFversion" "1.00"\n'
            'TYPE\n"v_t" FLOAT DOUBLE PROP( "units" "V" )\n"i_t" FLOAT DOUBLE PROP( "units" "A" )\n'
            'VALUE\n'
            '"VDD" "v_t" 1.0\n'
            '"VDD:p" "i_t" -1.0e-6\n'
            '"VDD18" "v_t" 1.8\n'
            '"VDD18:p" "i_t" -2.0e-3\n'
            'END\n'
        ))
        _write_utf8(os.path.join(mr_dir, "noise.noise"), (
            'HEADER\n"PSFversion" "1.00"\n'
            'TYPE\n"f_t" FLOAT DOUBLE PROP( "units" "Hz" )\n"in_t" FLOAT DOUBLE PROP( "units" "A/sqrt(Hz)" )\n'
            'SWEEP\n"freq" "f_t"\nTRACE\n"out" "in_t"\nVALUE\n'
            '"freq" 0.0\n"out" 1.0e-9\n'
            '"freq" 100.0\n"out" 1.0e-9\n'
            'END\n'
        ))
        res_mr = run_metrics(mr_dir)
        assert abs(res_mr["metrics"]["dc_power_w"] - 0.003601) < 1e-9, res_mr["metrics"]
        assert res_mr["metrics"]["integrated_rms_noise_v"] is None, res_mr["metrics"]
        assert abs(res_mr["metrics"]["integrated_rms_noise_a"] - 1.0e-8) < 1e-12, res_mr["metrics"]

        return {
            "command": "self-test",
            "ok": True,
            "self_test": "PASS",
            "checks_verified": [
                "mos_missing_op_fields_fail_closed",
                "mos_tight_headroom_audit_pass_false",
                "mos_multipoint_empty_corner_fail_closed",
                "no_ac_for_stb_substitution",
                "missing_corner_and_approval_pending_not_verified",
                "sub_ps_relative_tolerance_and_unknown_units",
                "range_min_max_constraint_normalization",
                "multi_loop_stb_and_minus540_gm_crossing",
                "unsettled_ramp_settling_none",
                "multi_rail_dc_power_and_current_noise_separation",
            ],
        }
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


HELP_TEXT = """Usage:
  python tools/psf_audit.py op-audit  <run_or_psf_path> [--vds-margin 0.05] [--expect-triode M_R1,M_SW] [--fail-on-violation]
  python tools/psf_audit.py metrics   <run_dir> [--spec spec.json] [--vout Vout] [--settling-tol 0.01] [--fail-on-spec]
  python tools/psf_audit.py self-test (or --self-test)
"""


def main(argv=None, quiet=False):
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help", "help"):
        print(HELP_TEXT)
        return 0

    if args[0] in ("--self-test", "self-test"):
        rep = run_self_test()
        print(json.dumps(rep, indent=2, sort_keys=True))
        return 0

    subcmd = args.pop(0)
    if subcmd == "op-audit":
        parser = _SilentOptionParser(add_help_option=False)
        parser.add_option("-h", "--help", action="store_true", dest="help", default=False)
        parser.add_option("--vds-margin", type="float", dest="vds_margin", default=0.05)
        parser.add_option("--expect-triode", type="string", dest="expect_triode", default="")
        parser.add_option("--fail-on-violation", action="store_true", dest="fail_on_violation", default=False)
        parser.add_option("--out", type="string", dest="out_path", default=None)
        try:
            opts, pos = parser.parse_args(args)
        except ValueError as err:
            print(json.dumps({"command": "op-audit", "ok": False, "error": str(err)}, indent=2, sort_keys=True))
            return 2
        if opts.help:
            print(HELP_TEXT)
            return 0
        if len(pos) != 1:
            print(json.dumps({"command": "op-audit", "ok": False, "error": "Expected <run_or_psf_path>"}, indent=2, sort_keys=True))
            return 2
        expect_list = [x.strip() for x in opts.expect_triode.split(",") if x.strip()]
        try:
            res = run_op_audit(pos[0], vds_margin=opts.vds_margin, expect_triode=expect_list)
            txt = json.dumps(res, indent=2, sort_keys=True)
            if opts.out_path:
                out_f = open(opts.out_path, "wb")
                try:
                    out_f.write((txt + "\n").encode("utf-8"))
                finally:
                    out_f.close()
            print(txt)
            if opts.fail_on_violation and not res.get("audit_pass", False):
                return 1
            return 0
        except Exception as exc:
            print(json.dumps({"command": "op-audit", "ok": False, "error": str(exc)}, indent=2, sort_keys=True))
            return 1

    if subcmd == "metrics":
        parser = _SilentOptionParser(add_help_option=False)
        parser.add_option("-h", "--help", action="store_true", dest="help", default=False)
        parser.add_option("--spec", type="string", dest="spec_path", default=None)
        parser.add_option("--vout", type="string", dest="vout_hint", default=None)
        parser.add_option("--vin", type="string", dest="vin_hint", default=None)
        parser.add_option("--settling-tol", type="float", dest="settling_tol", default=0.01)
        parser.add_option("--fail-on-spec", action="store_true", dest="fail_on_spec", default=False)
        parser.add_option("--out", type="string", dest="out_path", default=None)
        try:
            opts, pos = parser.parse_args(args)
        except ValueError as err:
            print(json.dumps({"command": "metrics", "ok": False, "error": str(err)}, indent=2, sort_keys=True))
            return 2
        if opts.help:
            print(HELP_TEXT)
            return 0
        if len(pos) != 1:
            print(json.dumps({"command": "metrics", "ok": False, "error": "Expected <run_dir>"}, indent=2, sort_keys=True))
            return 2
        try:
            res = run_metrics(
                pos[0],
                spec_path=opts.spec_path,
                vout_hint=opts.vout_hint,
                vin_hint=opts.vin_hint,
                settling_tol_ratio=opts.settling_tol,
            )
            txt = json.dumps(res, indent=2, sort_keys=True)
            if opts.out_path:
                out_f = open(opts.out_path, "wb")
                try:
                    out_f.write((txt + "\n").encode("utf-8"))
                finally:
                    out_f.close()
            if not quiet:
                print(txt)
            if opts.fail_on_spec and res.get("verdict") != "PASS":
                return 1
            return 0
        except Exception as exc:
            print(json.dumps({"command": "metrics", "ok": False, "error": str(exc)}, indent=2, sort_keys=True))
            return 1

    print(json.dumps({"ok": False, "error": "Unknown subcommand: " + subcmd}, indent=2, sort_keys=True))
    return 2


if __name__ == "__main__":
    sys.exit(main())
