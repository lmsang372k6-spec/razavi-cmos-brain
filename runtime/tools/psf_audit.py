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

UNIT_DIM_CASE_SENSITIVE = {
    "Mohm": "resistance",
    "Mohms": "resistance",
    "MOhm": "resistance",
    "MOhms": "resistance",
    "MW": "power",
    "MA": "current",
    "MV": "voltage",
    "mHz": "freq",
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

UNIT_DIM_LOWER = {
    "": None,
    "hz": "freq", "khz": "freq", "mhz": "freq", "ghz": "freq", "thz": "freq",
    "s": "time", "sec": "time", "secs": "time", "second": "time", "seconds": "time",
    "ms": "time", "us": "time", "ns": "time", "ps": "time", "fs": "time",
    "w": "power", "kw": "power", "mw": "power", "uw": "power", "nw": "power", "pw": "power", "fw": "power",
    "v": "voltage", "kv": "voltage", "mv": "voltage", "uv": "voltage", "nv": "voltage", "pv": "voltage", "fv": "voltage",
    "vrms": "voltage", "v_rms": "voltage", "mvrms": "voltage", "mv_rms": "voltage",
    "uvrms": "voltage", "uv_rms": "voltage", "nvrms": "voltage", "nv_rms": "voltage",
    "vpp": "voltage", "v_pp": "voltage", "mvpp": "voltage", "mv_pp": "voltage", "uvpp": "voltage", "uv_pp": "voltage",
    "a": "current", "ka": "current", "ma": "current", "ua": "current", "na": "current", "pa": "current", "fa": "current",
    "arms": "current", "a_rms": "current", "marms": "current", "ma_rms": "current",
    "uarms": "current", "ua_rms": "current", "narms": "current", "na_rms": "current", "parms": "current", "pa_rms": "current",
    "ohm": "resistance", "ohms": "resistance", "kohm": "resistance", "kohms": "resistance",
    "megohm": "resistance", "megohms": "resistance", "gohm": "resistance", "gohms": "resistance",
    "mohm": "resistance", "mohms": "resistance",
    "siemens": "conductance", "msiemens": "conductance", "usiemens": "conductance",
    "a/v": "conductance", "ma/v": "conductance", "ua/v": "conductance",
    "f": "capacitance", "mf": "capacitance", "uf": "capacitance", "nf": "capacitance", "pf": "capacitance", "ff": "capacitance", "af": "capacitance",
    "h": "inductance", "mh": "inductance", "uh": "inductance", "nh": "inductance", "ph": "inductance",
    "c": "charge", "mc": "charge", "uc": "charge", "nc": "charge", "pc": "charge", "fc": "charge",
    "v/s": "slew_rate", "v/ms": "slew_rate", "v/us": "slew_rate", "v/ns": "slew_rate", "v/ps": "slew_rate",
    "mv/ms": "slew_rate", "mv/us": "slew_rate", "mv/ns": "slew_rate", "mv/ps": "slew_rate", "kv/us": "slew_rate",
    "v/sqrt(hz)": "voltage_asd", "v/rthz": "voltage_asd",
    "mv/sqrt(hz)": "voltage_asd", "mv/rthz": "voltage_asd",
    "uv/sqrt(hz)": "voltage_asd", "uv/rthz": "voltage_asd",
    "nv/sqrt(hz)": "voltage_asd", "nv/rthz": "voltage_asd",
    "a/sqrt(hz)": "current_asd", "a/rthz": "current_asd",
    "ma/sqrt(hz)": "current_asd", "ma/rthz": "current_asd",
    "ua/sqrt(hz)": "current_asd", "ua/rthz": "current_asd",
    "na/sqrt(hz)": "current_asd", "na/rthz": "current_asd",
    "pa/sqrt(hz)": "current_asd", "pa/rthz": "current_asd",
    "db": "db", "dbc": "db", "dbfs": "db", "dbv": "db", "dbm": "db",
    "deg": "angle", "degree": "angle", "degrees": "angle",
    "%": "percent", "pct": "percent", "percent": "percent",
    "v/v": "ratio", "a/a": "ratio", "s/a": "inv_voltage", "1/v": "inv_voltage", "v^-1": "inv_voltage",
}

METRIC_DIMENSIONS = {
    "dc_power_w": "power",
    "idd_a": "current",
    "vdd_v": "voltage",
    "dc_gain_db": "db",
    "bw_3db_hz": "freq",
    "ugf_hz": "freq",
    "pm_ac_deg": "angle",
    "loop_dc_gain_db": "db",
    "stb_ugf_hz": "freq",
    "phase_margin_deg": "angle",
    "gain_margin_db": "db",
    "gm_freq_hz": "freq",
    "slew_rate_pos": "slew_rate",
    "slew_rate_neg": "slew_rate",
    "overshoot_pct": "percent",
    "settling_time_s": "time",
    "ripple_pp": "voltage",
    "integrated_rms_noise_v": "voltage",
    "integrated_rms_noise_a": "current",
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
    label_counts = {}
    for label, _ in op_files:
        label_counts[label] = label_counts.get(label, 0) + 1
    for label, fpath in op_files:
        parsed = parse_psf_file(
            fpath,
            reject_nonfinite=True,
            reject_truncated=True,
            fill_leading_missing=True,
        )
        rep = audit_mos_op_parsed(parsed, vds_margin=vds_margin, expect_triode=expect_triode)
        rep["psf_path"] = os.path.realpath(fpath)
        pt_key = label
        if label_counts.get(label, 0) > 1:
            rel_f = os.path.relpath(fpath, target_path).replace(os.sep, "/") if os.path.isdir(target_path) else os.path.basename(fpath)
            pt_key = "%s:%s" % (label, rel_f)
        per_point[pt_key] = rep

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


def _extract_dc_power_single(parsed):
    """Compute worst-case static DC power across ALL sweep points of a single DC PSF file."""
    vals = parsed.get("values", {})
    field_units = parsed.get("field_units", {})
    sweep_name = parsed.get("sweep_name")
    if not vals:
        return {}

    # Collect real voltage nodes vs source terminal current probes (preserving full sweep arrays)
    voltage_nodes = {}        # stem -> list of (orig_key, float_list)
    supply_voltage_nodes = {}
    current_probes = []       # list of (orig_key, stem, float_list)

    for k in sorted(vals.keys()):
        if sweep_name and k == sweep_name:
            continue
        arr = vals[k]
        if not arr or isinstance(arr[0], complex):
            continue
        f_arr = []
        valid_arr = True
        for elem in arr:
            if isinstance(elem, complex):
                valid_arr = False
                break
            try:
                f_arr.append(float(elem))
            except (TypeError, ValueError):
                valid_arr = False
                break
        if (not valid_arr) or (not f_arr):
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
                current_probes.append((k, stem, f_arr))
            continue

        # Skip flat device OP fields like `M1:vds` or `R1.i`
        if ":" in k:
            continue
        if unit_lc and unit_lc not in ("v", "volt", "volts"):
            continue
        stem = _normalize_rail_stem(k)
        if stem in ("0", "gnd", "agnd", "dgnd", "vss", "avss", "dvss"):
            continue
        voltage_nodes.setdefault(stem, []).append((k, f_arr))
        if _is_supply_rail_stem(stem):
            supply_voltage_nodes.setdefault(stem, []).append((k, f_arr))

    # Filter current probes: exclude explicit non-supply stimuli (`VIN:p`, `VBIAS:p`)
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

    if supply_named_probes:
        candidate_probes = supply_named_probes + generic_src_probes
    else:
        candidate_probes = generic_src_probes

    num_supply_v = len(supply_voltage_nodes)
    num_cand_i = len(candidate_probes)

    def _eval_worst_across_sweep(rail_pairs):
        # rail_pairs: list of (rail_stem, v_key, v_arr, c_key, c_arr)
        n_pts = 1
        for _, _, v_arr, _, c_arr in rail_pairs:
            if len(v_arr) > n_pts:
                n_pts = len(v_arr)
            if len(c_arr) > n_pts:
                n_pts = len(c_arr)
        best_p = None
        best_i = None
        best_idx = 0
        best_rails = None
        for idx in range(n_pts):
            tot_p = 0.0
            tot_i = 0.0
            rails_i = []
            for r_stem, v_key, v_arr, c_key, c_arr in rail_pairs:
                vv = abs(v_arr[idx] if idx < len(v_arr) else v_arr[0])
                cc = abs(c_arr[idx] if idx < len(c_arr) else c_arr[0])
                pp = vv * cc
                tot_p += pp
                tot_i += cc
                rails_i.append({
                    "rail": r_stem,
                    "voltage_node": v_key,
                    "current_probe": c_key,
                    "vdd_v": _round_clean(vv),
                    "idd_a": _round_clean(cc),
                    "power_w": _round_clean(pp),
                })
            if best_p is None or tot_p > best_p:
                best_p = tot_p
                best_i = tot_i
                best_idx = idx
                best_rails = rails_i
        return best_p, best_i, best_idx, n_pts, best_rails

    if num_supply_v > 0 and num_cand_i > 0:
        matched_pairs = []
        unmatched_probes = []
        matched_v_stems = set()
        ambiguous = False

        for c_key, c_stem, c_arr in candidate_probes:
            v_cands = supply_voltage_nodes.get(c_stem) or voltage_nodes.get(c_stem)
            if v_cands and len(v_cands) == 1 and c_stem not in matched_v_stems:
                matched_v_stems.add(c_stem)
                matched_pairs.append((c_stem, v_cands[0][0], v_cands[0][1], c_key, c_arr))
            elif v_cands and (len(v_cands) > 1 or c_stem in matched_v_stems):
                ambiguous = True
                unmatched_probes.append(c_key)
            else:
                unmatched_probes.append(c_key)

        unmatched_supply_v = [st for st in sorted(supply_voltage_nodes.keys()) if st not in matched_v_stems]

        if (not ambiguous) and matched_pairs and (not unmatched_probes) and (not unmatched_supply_v):
            total_p, total_i, best_idx, n_pts, matched_rails = _eval_worst_across_sweep(matched_pairs)
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
            if n_pts > 1:
                out["dc_sweep_points"] = n_pts
                out["dc_worst_sweep_index"] = best_idx
            return out

        # Single supply voltage node + single generic unnamed source probe (`vdd` + `V0:p`).
        # NEVER pair a distinct named supply rail probe (e.g. `VDD18:p`) with a different supply node (`VDD`)!
        if num_supply_v == 1 and num_cand_i == 1:
            only_v_stem = list(supply_voltage_nodes.keys())[0]
            v_list = supply_voltage_nodes[only_v_stem]
            c_key, c_stem, c_arr = candidate_probes[0]
            if len(v_list) == 1 and (c_stem == only_v_stem or (not _is_supply_rail_stem(c_stem))):
                v_key, v_arr = v_list[0]
                total_p, total_i, best_idx, n_pts, matched_rails = _eval_worst_across_sweep(
                    [(only_v_stem, v_key, v_arr, c_key, c_arr)]
                )
                out.update({
                    "vdd_v": matched_rails[0]["vdd_v"],
                    "idd_a": _round_clean(total_i),
                    "dc_power_w": _round_clean(total_p),
                    "power_method": "supply_terminal",
                    "supply_node": v_key,
                    "current_probe": c_key,
                })
                if n_pts > 1:
                    out["dc_sweep_points"] = n_pts
                    out["dc_worst_sweep_index"] = best_idx
                return out

        # Multiple rails / probes or cross-rail mismatch -> fail closed!
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


def _extract_dc_power(parsed_list):
    """Compute worst-case static DC power across ALL DC files and ALL sweep points.

    - Sums `|V_k * I_k|` across all matched supply rails (`VDD:p` * `VDD` + `VDD18:p` * `VDD18`, etc.).
    - Evaluates EVERY sweep point in EVERY DC file and reports worst-case (`max`) power.
    - If ANY DC file has ambiguous / cross-rail supply matching, fails closed (`dc_power_w = None`).
    - MOS `sum(|Vds * Ids|)` fallback is stored ONLY in `mos_power_estimate_w`, NEVER in `dc_power_w`.
    """
    valid_results = []
    ambiguous_res = None
    mos_est_max = None

    for parsed in parsed_list:
        res = _extract_dc_power_single(parsed)
        if not res:
            continue
        if res.get("mos_power_estimate_w") is not None:
            if mos_est_max is None or res["mos_power_estimate_w"] > mos_est_max:
                mos_est_max = res["mos_power_estimate_w"]
        if res.get("power_method") == "ambiguous_multi_rail":
            ambiguous_res = res
        elif isinstance(res.get("dc_power_w"), (int, float)):
            valid_results.append(res)

    if ambiguous_res is not None:
        if mos_est_max is not None and "mos_power_estimate_w" not in ambiguous_res:
            ambiguous_res["mos_power_estimate_w"] = mos_est_max
        return ambiguous_res

    if valid_results:
        best = valid_results[0]
        for cand in valid_results[1:]:
            if cand["dc_power_w"] > best["dc_power_w"]:
                best = cand
        out = dict(best)
        idd_vals = [r["idd_a"] for r in valid_results if isinstance(r.get("idd_a"), (int, float))]
        if idd_vals:
            out["idd_a"] = _round_clean(max(idd_vals))
        if mos_est_max is not None:
            out["mos_power_estimate_w"] = mos_est_max
        return out

    if mos_est_max is not None:
        return {
            "mos_power_estimate_w": mos_est_max,
            "dc_power_w": None,
            "power_method": "mos_vds_ids_sum_estimate_only",
        }

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

    if vout_hint and (vout_hint in rejected_bf or vout_hint not in vals or len(vals[vout_hint]) != len(freqs)):
        res_mv = {
            "ac_output": vout_hint,
            "dc_gain_db": None,
            "bw_3db_hz": None,
            "ugf_hz": None,
            "pm_ac_deg": None,
        }
        if vout_hint in rejected_bf:
            res_mv["rejected_backfilled_signals"] = rejected_bf
        else:
            res_mv["missing_vout"] = vout_hint
        return res_mv

    h_vec = None
    out_label = None
    out_used_keys = []
    if vout_hint and vout_hint in vals:
        h_vec = [complex(v) for v in vals[vout_hint]]
        out_label = vout_hint
        out_used_keys = [vout_hint]
    elif not vout_hint:
        vp = _pick_signal_key(vals, ("voutp", "vout_p", "outp", "out_p", "vop"), exclude=(freq_key,))
        vn = _pick_signal_key(vals, ("voutn", "vout_n", "outn", "out_n", "von"), exclude=(freq_key,))
        if vp and vn and len(vals[vp]) == len(freqs) and len(vals[vn]) == len(freqs):
            h_vec = [complex(vals[vp][i]) - complex(vals[vn][i]) for i in range(len(freqs))]
            out_label = "%s-%s" % (vp, vn)
            out_used_keys = [vp, vn]
        else:
            vo = _pick_signal_key(
                vals,
                ("vout", "out", "vo", "v_out", "vf", "y"),
                exclude=(freq_key, "vin", "in", "inp", "inn", "vinp", "vinn", "vdd", "vss"),
            )
            if vo is None:
                for k in sorted(vals.keys()):
                    if k != freq_key and vals[k] and isinstance(vals[k][0], complex):
                        vo = k
                        break
            if vo and len(vals[vo]) == len(freqs):
                h_vec = [complex(v) for v in vals[vo]]
                out_label = vo
                out_used_keys = [vo]

    if not h_vec:
        return {"rejected_backfilled_signals": rejected_bf} if rejected_bf else {}

    # Strict `--vin` handling + automatic differential input (`inp-inn`, `vinp-vinn`, etc.) normalization
    vin_arr = None
    in_label = None
    if vin_hint:
        if vin_hint in rejected_bf or vin_hint not in vals or len(vals[vin_hint]) != len(freqs):
            res_mi = {
                "ac_output": out_label,
                "ac_input": vin_hint,
                "dc_gain_db": None,
                "bw_3db_hz": None,
                "ugf_hz": None,
                "pm_ac_deg": None,
            }
            if vin_hint in rejected_bf:
                res_mi["rejected_backfilled_signals"] = rejected_bf
            else:
                res_mi["missing_vin"] = vin_hint
            return res_mi
        vin_arr = [complex(v) for v in vals[vin_hint]]
        in_label = vin_hint
    else:
        excl_in = tuple([freq_key] + out_used_keys)
        diff_in_pairs = (
            ("vinp", "vinn"),
            ("vin_p", "vin_n"),
            ("inp", "inn"),
            ("in_p", "in_n"),
            ("vip", "vin"),
            ("v_inp", "v_inn"),
            ("in_pos", "in_neg"),
        )
        for p_cand, n_cand in diff_in_pairs:
            kp = _pick_signal_key(vals, (p_cand,), exclude=excl_in)
            kn = _pick_signal_key(vals, (n_cand,), exclude=excl_in)
            if kp and kn and kp != kn and len(vals[kp]) == len(freqs) and len(vals[kn]) == len(freqs):
                vin_arr = [complex(vals[kp][i]) - complex(vals[kn][i]) for i in range(len(freqs))]
                in_label = "%s-%s" % (kp, kn)
                break
        if vin_arr is None:
            vin_key = _pick_signal_key(vals, ("vin", "vin_ac", "in", "v_in"), exclude=excl_in)
            if vin_key and len(vals[vin_key]) == len(freqs):
                vin_arr = [complex(v) for v in vals[vin_key]]
                in_label = vin_key

    if vin_arr is not None:
        if abs(vin_arr[0]) > 1e-15:
            h_vec = [
                (h_vec[i] / vin_arr[i]) if abs(vin_arr[i]) > 1e-30 else h_vec[i]
                for i in range(len(freqs))
            ]
        elif vin_hint:
            return {
                "ac_output": out_label,
                "ac_input": in_label,
                "dc_gain_db": None,
                "bw_3db_hz": None,
                "ugf_hz": None,
                "pm_ac_deg": None,
            }

    # Ensure ascending frequency order for DC gain, 3 dB BW, and UGF extraction
    if any([freqs[i] > freqs[i + 1] for i in range(len(freqs) - 1)]):
        order = sorted(range(len(freqs)), key=lambda idx: freqs[idx])
        freqs = [freqs[idx] for idx in order]
        h_vec = [h_vec[idx] for idx in order]

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
    if in_label:
        res["ac_input"] = in_label
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

    rhp_pole_suspected = False
    dc_pos_fb = False

    if freq_key and lg_key and len(vals[freq_key]) >= 2 and len(vals[lg_key]) == len(vals[freq_key]):
        freqs = [float(x.real) if isinstance(x, complex) else float(x) for x in vals[freq_key]]
        lg = [complex(v) for v in vals[lg_key]]
        if any([freqs[i] > freqs[i + 1] for i in range(len(freqs) - 1)]):
            order = sorted(range(len(freqs)), key=lambda idx: freqs[idx])
            freqs = [freqs[idx] for idx in order]
            lg = [lg[idx] for idx in order]

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
                direction = "falling" if mag_db[i] >= mag_db[i + 1] else "rising"
                # Bode gain-phase RHP open-loop pole check:
                # For open-loop stable (P=0) causal L(s) rolling off from |L(0)| > 1 through 0 dB,
                # phase cannot lead past +45 deg or rise monotonically into positive phase while gain falls.
                if (not dc_pos_fb) and mag_db[0] > 0.0 and direction == "falling":
                    dphi_c = unwrapped[i + 1] - unwrapped[i]
                    if phi_c > 45.0 or (phi_c > 10.0 and dphi_c > 0.0):
                        rhp_pole_suspected = True
                ugf_crossings.append({
                    "freq_hz": _round_clean(f_c),
                    "phase_deg": _round_clean(phi_c),
                    "phase_margin_deg": _round_clean(pm_c),
                    "direction": direction,
                })

        # Secondary high-frequency roll-off RHP-pole check (e.g. L(s)=K/(s-p)^n where phase rises > +90 deg as |L|->0)
        if (
            (not dc_pos_fb)
            and mag_db[0] > 0.0
            and mag_db[-1] < mag_db[0] - 6.0
            and max(unwrapped) > unwrapped[0] + 90.0
            and unwrapped[-1] > unwrapped[0] + 60.0
        ):
            rhp_pole_suspected = True

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

        if rhp_pole_suspected:
            # Bode phase/gain margin is INVALID when open-loop RHP poles are present (Nyquist P != 0).
            # Fail closed so closed-loop instability (e.g. L(s)=3/(s-1)^2) can NEVER pass as stable!
            out.update({
                "stb_probe_signal": lg_key,
                "loop_dc_gain_db": _round_clean(loop_dc_gain_db),
                "stb_ugf_hz": _round_clean(primary_ugf),
                "phase_margin_deg": None,
                "gain_margin_db": None,
                "gm_freq_hz": None,
                "dc_positive_feedback": dc_pos_fb,
                "rhp_open_loop_pole_suspected": True,
                "stb_bode_valid": False,
                "raw_bode_phase_margin_deg": _round_clean(worst_pm),
                "ugf_crossing_count": len(ugf_crossings),
            })
        else:
            out.update({
                "stb_probe_signal": lg_key,
                "loop_dc_gain_db": _round_clean(loop_dc_gain_db),
                "stb_ugf_hz": _round_clean(primary_ugf),
                "phase_margin_deg": _round_clean(worst_pm),
                "gain_margin_db": _round_clean(gm_db),
                "gm_freq_hz": _round_clean(gm_freq_hz),
                "dc_positive_feedback": dc_pos_fb,
                "rhp_open_loop_pole_suspected": False,
                "stb_bode_valid": True,
                "ugf_crossing_count": len(ugf_crossings),
            })
        if len(ugf_crossings) > 1:
            out["all_ugf_crossings"] = ugf_crossings
        if len(gm_crossings) > 1:
            out["all_gm_crossings"] = gm_crossings

    if margin_parsed and (not rhp_pole_suspected) and (not dc_pos_fb):
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


def _interp_level_crossing_with_idx(times, vals, start_idx, end_idx, target, rising=True):
    for i in range(start_idx, min(end_idx, len(vals) - 1)):
        v0, v1 = vals[i], vals[i + 1]
        cond = (v0 <= target < v1 or (v0 < target <= v1)) if rising else (v0 >= target > v1 or (v0 > target >= v1))
        if cond:
            if abs(v1 - v0) < 1e-30:
                return times[i], i
            frac = (target - v0) / (v1 - v0)
            return (times[i] + frac * (times[i + 1] - times[i])), i
    return None, None


def _analyze_step_segment(times, vals, seg_start, seg_end, settling_tol_ratio=0.01, t_trig=None, target_v=None):
    """Extract slew rate (10%-90%), overshoot %, and settled plateau settling time on a step window.

    - When `target_v` is provided, settling is verified strictly against `target_v` (catching static error).
    - Rejects unsettled ramps (both uniform and non-uniform timesteps) via time-span & plateau-slope guards.
    """
    if seg_end - seg_start < 3:
        return {}
    t_win = times[seg_start:seg_end + 1]
    v_win = vals[seg_start:seg_end + 1]
    v_init = v_win[0]
    win_dur = t_win[-1] - t_win[0]
    if win_dur <= 1e-18:
        return {}

    # Build tail plateau window covering BOTH >= 15% of post-onset duration AND >= max(3, N//10) samples
    t_base = t_trig if (t_trig is not None and t_win[0] <= t_trig < t_win[-1]) else t_win[0]
    post_dur = t_win[-1] - t_base
    t_tail_cut = t_base + 0.85 * post_dur
    time_tail_indices = [idx for idx in range(len(t_win)) if t_win[idx] >= t_tail_cut]
    min_tail_n = max(3, len(v_win) // 10) if len(v_win) >= 3 else len(v_win)
    tail_n = max(min_tail_n, len(time_tail_indices))
    if len(v_win) >= 6:
        tail_n = min(tail_n, max(3, len(v_win) // 2))
    else:
        tail_n = min(tail_n, len(v_win))

    t_tail = t_win[-tail_n:]
    v_tail = v_win[-tail_n:]
    v_final = sum(v_tail) / float(len(v_tail))

    v_ref = float(target_v) if target_v is not None else v_final
    step_amp = v_final - v_init
    abs_step = abs(step_amp)
    ref_step = v_ref - v_init
    abs_ref_step = abs(ref_step)
    eff_step = ref_step if (target_v is not None and abs_ref_step >= 1e-9) else step_amp
    abs_eff_step = abs(eff_step)
    if max(abs_step, abs_ref_step) < 1e-9:
        return {}

    rising = (eff_step > 0.0)
    lvl_01 = v_init + 0.01 * eff_step
    lvl_10 = v_init + 0.10 * eff_step
    lvl_90 = v_init + 0.90 * eff_step

    t_onset = t_trig if t_trig is not None else _interp_level_crossing(t_win, v_win, 0, len(v_win) - 1, lvl_01, rising=rising)
    if t_onset is None:
        t_onset = t_win[0]

    t_10 = _interp_level_crossing(t_win, v_win, 0, len(v_win) - 1, lvl_10, rising=rising)
    t_90 = _interp_level_crossing(t_win, v_win, 0, len(v_win) - 1, lvl_90, rising=rising)
    sr_10_90 = None
    if t_10 is not None and t_90 is not None and (t_90 - t_10) > 1e-18:
        sr_10_90 = (0.80 * abs_eff_step) / (t_90 - t_10)

    if rising:
        v_ext = max(v_win)
        overshoot_pct = max(0.0, (v_ext - v_ref) / abs_eff_step * 100.0)
    else:
        v_ext = min(v_win)
        overshoot_pct = max(0.0, (v_ref - v_ext) / abs_eff_step * 100.0)

    tol = settling_tol_ratio * abs_eff_step
    tail_span = max(v_tail) - min(v_tail)
    tail_dt = t_tail[-1] - t_tail[0]
    avg_win_slope = abs_step / max(1e-18, win_dur)
    tail_slope = (abs(v_tail[-1] - v_tail[0]) / tail_dt) if tail_dt > 1e-18 else float("inf")

    # Anti-ramp plateau guard: tail must span >= 5% of window duration AND be much flatter than the transition ramp
    tail_has_plateau = (
        len(v_win) >= 6
        and tail_dt >= 0.05 * win_dur
        and (avg_win_slope <= 1e-18 or tail_slope <= 0.25 * avg_win_slope)
    )
    tail_settled = (
        tail_has_plateau
        and tail_span <= tol
        and abs(v_final - v_ref) <= tol
        and all([abs(x - v_ref) <= tol for x in v_tail])
    )
    if not tail_settled:
        settling_time_s = None
    else:
        last_out = -1
        for k in range(len(v_win)):
            if abs(v_win[k] - v_ref) > tol:
                last_out = k
        if last_out < 0:
            settling_time_s = 0.0
        elif last_out >= len(v_win) - 1:
            settling_time_s = None
        else:
            v_a = v_win[last_out]
            v_b = v_win[last_out + 1]
            bound = (v_ref + tol) if v_a > v_ref else (v_ref - tol)
            if abs(v_b - v_a) > 1e-30:
                frac = (bound - v_a) / (v_b - v_a)
                frac = max(0.0, min(1.0, frac))
                t_enter = t_win[last_out] + frac * (t_win[last_out + 1] - t_win[last_out])
            else:
                t_enter = t_win[last_out + 1]
            settling_time_s = max(0.0, t_enter - t_onset)

    out_seg = {
        "rising": rising,
        "slew_rate": sr_10_90,
        "overshoot_pct": overshoot_pct,
        "settling_time_s": settling_time_s,
        "step_amplitude_v": abs_eff_step,
        "v_init": v_init,
        "v_final": v_final,
    }
    if target_v is not None:
        out_seg["target_v"] = v_ref
        out_seg["static_error_v"] = v_final - v_ref
    return out_seg


def _extract_tran_metrics(parsed, vout_hint=None, settling_tol_ratio=0.01, target_v=None):
    vals, rejected_bf = _usable_waveform_values(parsed)
    t_key = parsed.get("sweep_name") or _pick_signal_key(vals, ("time", "t"))
    if not t_key or t_key not in vals:
        return {"rejected_backfilled_signals": rejected_bf} if rejected_bf else {}
    times = [float(x.real) if isinstance(x, complex) else float(x) for x in vals[t_key]]
    if len(times) < 4:
        return {}

    if vout_hint and (vout_hint in rejected_bf or vout_hint not in vals or len(vals[vout_hint]) != len(times)):
        res_mv = {
            "tran_output": vout_hint,
            "slew_rate_pos": None,
            "slew_rate_neg": None,
            "overshoot_pct": None,
            "settling_time_s": None,
            "ripple_pp": None,
            "step_detected": True,
        }
        if vout_hint in rejected_bf:
            res_mv["rejected_backfilled_signals"] = rejected_bf
        else:
            res_mv["missing_vout"] = vout_hint
        return res_mv

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
    tran_final_v = None
    static_error_v = None
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

            # Preserve input stimulus edge timestamps (`t_trig1`, `t_trig2`) so propagation delay is NEVER lost!
            t_trig1 = None
            t_trig2 = None
            if trig_vals is not None:
                tr_min = min(trig_vals)
                tr_max = max(trig_vals)
                tr_swing = tr_max - tr_min
                if tr_swing > 1e-9:
                    tr_goes_up = (abs(tr_max - trig_vals[0]) >= abs(trig_vals[0] - tr_min))
                    tr_mid = trig_vals[0] + 0.5 * ((tr_max - trig_vals[0]) if tr_goes_up else (tr_min - trig_vals[0]))
                    t_trig1, idx_tr1 = _interp_level_crossing_with_idx(
                        times, trig_vals, 0, len(times) - 1, tr_mid, rising=tr_goes_up
                    )
                    if idx_tr1 is not None:
                        t_trig2, _ = _interp_level_crossing_with_idx(
                            times, trig_vals, idx_tr1 + 1, len(times) - 1, tr_mid, rising=(not tr_goes_up)
                        )

            seg1 = _analyze_step_segment(
                times, vout, 0, split_idx,
                settling_tol_ratio=settling_tol_ratio,
                t_trig=t_trig1,
                target_v=target_v,
            )
            seg2 = _analyze_step_segment(
                times, vout, split_idx, len(vout) - 1,
                settling_tol_ratio=settling_tol_ratio,
                t_trig=t_trig2,
                target_v=(vout[0] if target_v is not None else None),
            )
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
            if seg1 and seg1.get("v_final") is not None:
                tran_final_v = seg1["v_final"]
            if seg1 and seg1.get("static_error_v") is not None:
                static_error_v = seg1["static_error_v"]

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
                times, vout, 0, len(vout) - 1,
                settling_tol_ratio=settling_tol_ratio,
                t_trig=t_trig,
                target_v=target_v,
            )
            if seg:
                if seg.get("rising"):
                    sr_pos = seg.get("slew_rate")
                else:
                    sr_neg = seg.get("slew_rate")
                overshoot_pct = seg.get("overshoot_pct")
                settling_time_s = seg.get("settling_time_s")
                tran_final_v = seg.get("v_final")
                static_error_v = seg.get("static_error_v")

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
        "tran_init_v": _round_clean(vout[0]),
        "tran_final_v": _round_clean(tran_final_v),
    }
    if target_v is not None:
        res["settling_target_v"] = _round_clean(float(target_v))
        res["static_error_v"] = _round_clean(static_error_v)
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


def _integrate_psd_band(freqs, psd, f_min=None, f_max=None):
    """Trapezoidally integrate sorted `(freqs, psd)` strictly over `[f_min, f_max]`.

    Returns `(rms_float, None)` on success, or `(None, 'noise_band_not_covered')` if the
    frequency sweep does not span the requested band.
    """
    if len(freqs) < 2 or len(psd) != len(freqs):
        return None, "noise_band_unverified"
    f_lo = freqs[0]
    f_hi = freqs[-1]
    lo = f_lo if f_min is None else float(f_min)
    hi = f_hi if f_max is None else float(f_max)
    if lo > hi:
        return None, "invalid_noise_band"
    tol_lo = max(1e-12, 1e-6 * abs(lo))
    tol_hi = max(1e-12, 1e-6 * abs(hi))
    if lo < f_lo - tol_lo or hi > f_hi + tol_hi:
        return None, "noise_band_not_covered"

    lo_clamped = max(f_lo, lo)
    hi_clamped = min(f_hi, hi)
    if hi_clamped <= lo_clamped:
        return 0.0, None

    def _interp_psd(f_target):
        if f_target <= freqs[0]:
            return psd[0]
        if f_target >= freqs[-1]:
            return psd[-1]
        for idx in range(len(freqs) - 1):
            if freqs[idx] <= f_target <= freqs[idx + 1]:
                df = freqs[idx + 1] - freqs[idx]
                if df <= 1e-30:
                    return psd[idx]
                frac = (f_target - freqs[idx]) / df
                return psd[idx] + frac * (psd[idx + 1] - psd[idx])
        return psd[-1]

    pts_f = [lo_clamped]
    pts_p = [_interp_psd(lo_clamped)]
    for idx in range(len(freqs)):
        if lo_clamped < freqs[idx] < hi_clamped:
            pts_f.append(freqs[idx])
            pts_p.append(psd[idx])
    pts_f.append(hi_clamped)
    pts_p.append(_interp_psd(hi_clamped))

    integ = 0.0
    for idx in range(len(pts_f) - 1):
        df = pts_f[idx + 1] - pts_f[idx]
        if df > 0.0:
            integ += 0.5 * (pts_p[idx] + pts_p[idx + 1]) * df
    return math.sqrt(max(0.0, integ)), None


def _extract_noise_metrics(parsed, return_curve=False):
    vals, rejected_bf = _usable_waveform_values(parsed)
    f_key = parsed.get("sweep_name") or _pick_signal_key(vals, ("freq", "frequency", "f"))
    if not f_key or f_key not in vals:
        out_e = {"rejected_backfilled_signals": rejected_bf} if rejected_bf else {}
        return (out_e, None) if return_curve else out_e
    freqs = [float(x.real) if isinstance(x, complex) else float(x) for x in vals[f_key]]
    if len(freqs) < 2:
        return ({}, None) if return_curve else {}
    n_key = _pick_signal_key(vals, ("out", "onoise", "inoise", "vout_noise", "iout_noise"), exclude=(f_key,))
    if not n_key or len(vals[n_key]) != len(freqs):
        out_e = {"rejected_backfilled_signals": rejected_bf} if rejected_bf else {}
        return (out_e, None) if return_curve else out_e

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
        return (res, None) if return_curve else res

    # Always sort ascending by frequency so descending sweeps (e.g. 100 Hz -> 10 Hz) integrate accurately!
    pairs = sorted(zip(freqs, raw), key=lambda pr: pr[0])
    f_sorted = [pr[0] for pr in pairs]
    psd = [pr[1] if is_psd else (pr[1] * pr[1]) for pr in pairs]

    rms_raw, _ = _integrate_psd_band(f_sorted, psd)
    rms_val = _round_clean(rms_raw)
    res = {
        "noise_signal": n_key,
        "noise_unit": unit,
        "noise_domain": domain,
        "noise_freq_min_hz": _round_clean(f_sorted[0]),
        "noise_freq_max_hz": _round_clean(f_sorted[-1]),
        "integrated_rms_noise_v": rms_val if domain == "voltage" else None,
        "integrated_rms_noise_a": rms_val if domain == "current" else None,
    }
    if rejected_bf:
        res["rejected_backfilled_signals"] = rejected_bf
    curve_info = {"domain": domain, "freqs": f_sorted, "psd": psd}
    return (res, curve_info) if return_curve else res


def _stb_loop_stem(filepath):
    bn = os.path.basename(filepath)
    low = bn.lower()
    for suf in (".margin.pstb", ".margin.stb", ".pstb", ".stb"):
        if low.endswith(suf):
            return bn[:len(bn) - len(suf)] or "stb"
    return bn


def _build_unique_file_keys(filepaths, base_dir=None):
    """Map each filepath to a collision-free key (basename if unique, else relative path)."""
    counts = {}
    for fp in filepaths:
        bn = os.path.basename(fp)
        counts[bn] = counts.get(bn, 0) + 1
    out = {}
    used = set()
    for fp in filepaths:
        bn = os.path.basename(fp)
        if counts.get(bn, 0) == 1:
            key = bn
        else:
            if base_dir and os.path.isdir(base_dir):
                key = os.path.relpath(fp, base_dir).replace(os.sep, "/")
            else:
                parent = os.path.basename(os.path.dirname(fp))
                key = "%s/%s" % (parent, bn) if parent else fp
        orig_key = key
        idx = 2
        while key in used:
            key = "%s#%d" % (orig_key, idx)
            idx += 1
        used.add(key)
        out[fp] = key
    return out


def _extract_point_metrics(
    psf_files_by_kind,
    vout_hint=None,
    vin_hint=None,
    settling_tol_ratio=0.01,
    target_v=None,
    base_dir=None,
    aux_out=None,
):
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

    def _add_analysis(tag):
        if tag not in analyses_present:
            analyses_present.append(tag)

    parsed_dc = []
    for p in psf_files_by_kind.get("dc", []):
        parsed_dc.append(parse_psf_file(p, reject_nonfinite=True, reject_truncated=True, fill_leading_missing=True))
    if parsed_dc:
        _add_analysis("dc")
        metrics.update(_extract_dc_power(parsed_dc))

    # Process ALL `.ac` / `.pac` files in this point with collision-free keys and aggregate worst-case
    ac_files = psf_files_by_kind.get("ac", [])
    ac_keys = _build_unique_file_keys(ac_files, base_dir=base_dir)
    ac_runs = {}
    has_pac = False
    for p in ac_files:
        if os.path.basename(p).lower().endswith(".pac"):
            has_pac = True
        ac_res = _extract_ac_metrics(
            parse_psf_file(p, reject_nonfinite=True, reject_truncated=True, fill_leading_missing=True),
            vout_hint=vout_hint,
            vin_hint=vin_hint,
        )
        if ac_res:
            ac_runs[ac_keys[p]] = ac_res
    if ac_runs:
        _add_analysis("ac")
        if has_pac:
            _add_analysis("pac")
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
        if first_ac.get("ac_input"):
            metrics["ac_input"] = first_ac["ac_input"]
        if len(ac_runs) > 1:
            metrics["ac_runs"] = ac_runs

    # Process ALL `.stb` / `.pstb` + `.margin.stb` loops with collision-free keys & strict stem matching
    stb_files = psf_files_by_kind.get("stb", [])
    margin_files = psf_files_by_kind.get("stb_margin", [])
    all_stb_keys = _build_unique_file_keys(stb_files + margin_files, base_dir=base_dir)

    margin_entries = []  # list of (mp, dir_real, stem, parsed)
    margin_by_dir_stem = {}
    margin_by_stem_list = {}
    has_pstb = False
    for mp in margin_files:
        if os.path.basename(mp).lower().endswith(".pstb"):
            has_pstb = True
        m_stem = _stb_loop_stem(mp)
        m_dir = os.path.realpath(os.path.dirname(mp))
        m_parsed = parse_psf_file(mp, reject_nonfinite=True, reject_truncated=True, fill_leading_missing=True)
        entry = (mp, m_dir, m_stem, m_parsed)
        margin_entries.append(entry)
        margin_by_dir_stem[(m_dir, m_stem)] = entry
        margin_by_stem_list.setdefault(m_stem, []).append(entry)

    generic_margin_stems = set(["stb", "pstb", "margin", "loop"])
    stb_loops = {}
    used_margin_paths = set()
    for sp in stb_files:
        if os.path.basename(sp).lower().endswith(".pstb"):
            has_pstb = True
        stem = _stb_loop_stem(sp)
        s_dir = os.path.realpath(os.path.dirname(sp))
        m_entry = margin_by_dir_stem.get((s_dir, stem))
        if m_entry is None:
            same_stem = [e for e in margin_by_stem_list.get(stem, []) if e[0] not in used_margin_paths]
            if len(same_stem) == 1:
                m_entry = same_stem[0]
        if m_entry is None and len(stb_files) == 1 and len(margin_entries) == 1:
            # Allow generic unnamed margin file (`stb.margin.stb`, `margin.stb`) ONLY — never cross-pair named loops!
            only_m = margin_entries[0]
            if only_m[2].lower() in generic_margin_stems and only_m[0] not in used_margin_paths:
                m_entry = only_m
        m_parsed = None
        if m_entry is not None:
            used_margin_paths.add(m_entry[0])
            m_parsed = m_entry[3]
        s_parsed = parse_psf_file(sp, reject_nonfinite=True, reject_truncated=True, fill_leading_missing=True)
        s_res = _extract_stb_metrics(s_parsed, margin_parsed=m_parsed)
        if s_res:
            stb_loops[all_stb_keys[sp]] = s_res

    for mp, _, _, m_parsed in margin_entries:
        if mp not in used_margin_paths:
            s_res = _extract_stb_metrics(None, margin_parsed=m_parsed)
            if s_res:
                stb_loops[all_stb_keys[mp]] = s_res

    if stb_loops:
        _add_analysis("stb")
        if has_pstb:
            _add_analysis("pstb")
        any_rhp_pole = any([bool(r.get("rhp_open_loop_pole_suspected")) for r in stb_loops.values()])
        for m_k in ("loop_dc_gain_db", "stb_ugf_hz", "phase_margin_deg", "gain_margin_db"):
            vals_k = [r[m_k] for r in stb_loops.values() if isinstance(r.get(m_k), (int, float))]
            # Fail closed if ANY loop has RHP-pole suspicion or failed to yield PM/UGF with positive DC gain
            tainted = False
            if any_rhp_pole and m_k in ("phase_margin_deg", "gain_margin_db"):
                tainted = True
            if (not tainted) and m_k in ("phase_margin_deg", "stb_ugf_hz") and len(stb_loops) > 1:
                for r in stb_loops.values():
                    if r.get(m_k) is None and (r.get("loop_dc_gain_db") is None or r.get("loop_dc_gain_db", -1.0) >= 0.0):
                        tainted = True
                        break
            if vals_k and not tainted:
                metrics[m_k] = _round_clean(min(vals_k))
            else:
                metrics[m_k] = None
        metrics["dc_positive_feedback"] = any([bool(r.get("dc_positive_feedback")) for r in stb_loops.values()])
        if any_rhp_pole:
            metrics["rhp_open_loop_pole_suspected"] = True
        if len(stb_loops) == 1:
            only_stb = stb_loops[list(stb_loops.keys())[0]]
            for extra_k in ("stb_probe_signal", "gm_freq_hz", "ugf_crossing_count", "all_ugf_crossings", "all_gm_crossings"):
                if extra_k in only_stb:
                    metrics[extra_k] = only_stb[extra_k]
        else:
            metrics["stb_loops"] = stb_loops

    # Process `.pss` files if present so `pss` analysis coverage can be verified distinctly
    for pss_p in psf_files_by_kind.get("pss", []):
        parse_psf_file(pss_p, reject_nonfinite=True, reject_truncated=True, fill_leading_missing=True)
        _add_analysis("pss")

    # Process ALL `.tran` files with collision-free keys and aggregate worst-case; fail-closed on unsettled step
    tran_files = psf_files_by_kind.get("tran", [])
    tran_keys = _build_unique_file_keys(tran_files, base_dir=base_dir)
    tran_runs = {}
    for tp in tran_files:
        tr_res = _extract_tran_metrics(
            parse_psf_file(tp, reject_nonfinite=True, reject_truncated=True, fill_leading_missing=True),
            vout_hint=vout_hint,
            settling_tol_ratio=settling_tol_ratio,
            target_v=target_v,
        )
        if tr_res:
            tran_runs[tran_keys[tp]] = tr_res
    if tran_runs:
        _add_analysis("tran")
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
        for tr_extra in ("tran_output", "tran_init_v", "tran_final_v", "settling_target_v", "static_error_v"):
            if first_tr.get(tr_extra) is not None:
                metrics[tr_extra] = first_tr[tr_extra]
        if len(tran_runs) > 1:
            metrics["tran_runs"] = tran_runs

    # Process ALL `.noise` / `.pnoise` files with collision-free keys and preserve spectral curves for band checks
    noise_files = psf_files_by_kind.get("noise", [])
    noise_keys = _build_unique_file_keys(noise_files, base_dir=base_dir)
    noise_runs = {}
    noise_curves = []
    has_pnoise = False
    for np_file in noise_files:
        if os.path.basename(np_file).lower().endswith(".pnoise"):
            has_pnoise = True
        ns_res, curve_info = _extract_noise_metrics(
            parse_psf_file(np_file, reject_nonfinite=True, reject_truncated=True, fill_leading_missing=True),
            return_curve=True,
        )
        if ns_res:
            noise_runs[noise_keys[np_file]] = ns_res
        if curve_info is not None:
            noise_curves.append(curve_info)
    if noise_runs:
        _add_analysis("noise")
        if has_pnoise:
            _add_analysis("pnoise")
        for nk in ("integrated_rms_noise_v", "integrated_rms_noise_a"):
            vals_k = [r[nk] for r in noise_runs.values() if isinstance(r.get(nk), (int, float))]
            metrics[nk] = _round_clean(max(vals_k)) if vals_k else None
        fmins = [r["noise_freq_min_hz"] for r in noise_runs.values() if isinstance(r.get("noise_freq_min_hz"), (int, float))]
        fmaxs = [r["noise_freq_max_hz"] for r in noise_runs.values() if isinstance(r.get("noise_freq_max_hz"), (int, float))]
        if fmins:
            metrics["noise_freq_min_hz"] = _round_clean(min(fmins))
        if fmaxs:
            metrics["noise_freq_max_hz"] = _round_clean(max(fmaxs))
        if len(noise_runs) == 1:
            only_ns = noise_runs[list(noise_runs.keys())[0]]
            for extra_k in ("noise_signal", "noise_unit", "noise_domain"):
                if extra_k in only_ns:
                    metrics[extra_k] = only_ns[extra_k]
        else:
            metrics["noise_runs"] = noise_runs
        if aux_out is not None and noise_curves:
            aux_out["noise_curves"] = noise_curves

    metrics["analyses_present"] = analyses_present
    return metrics


def _classify_psf_filename(filename):
    low = filename.lower()
    if low.endswith(".cdslck") or low.endswith(".log") or low.endswith(".json") or low.endswith(".scs"):
        return None
    if "margin" in low and (low.endswith(".stb") or low.endswith(".pstb")):
        return "stb_margin"
    if low.endswith(".stb") or low.endswith(".pstb"):
        return "stb"
    if low.endswith(".ac") or low.endswith(".pac"):
        return "ac"
    if low.endswith(".tran"):
        return "tran"
    if low.endswith(".noise") or low.endswith(".pnoise"):
        return "noise"
    if low.endswith(".pss"):
        return "pss"
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


def _scale_target_to_si(target_val, unit_str, metric_key=None):
    """Return `(scaled_float, error_reason_or_None)`.

    - Unknown units fail closed (`None, 'unknown_unit'`).
    - Incompatible unit/metric dimensions (e.g. `mV` on `dc_gain_db`) fail closed (`None, 'unit_dimension_mismatch'`).
    """
    if target_val is None:
        return None, None
    raw_u = str(unit_str or "").strip().replace(" ", "")
    if raw_u in UNIT_SCALE_CASE_SENSITIVE:
        scale = UNIT_SCALE_CASE_SENSITIVE[raw_u]
        u_dim = UNIT_DIM_CASE_SENSITIVE.get(raw_u)
    else:
        u_key = raw_u.lower()
        if u_key not in UNIT_SCALE_TO_SI:
            return None, "unknown_unit"
        scale = UNIT_SCALE_TO_SI[u_key]
        u_dim = UNIT_DIM_LOWER.get(u_key)
    if metric_key and u_dim is not None:
        expected_dim = METRIC_DIMENSIONS.get(metric_key)
        if expected_dim is not None and u_dim != expected_dim:
            return None, "unit_dimension_mismatch"
    return float(target_val) * scale, None


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
    seen = set()
    dedup = []
    for x in raw:
        xl = x.lower()
        if xl and xl not in seen:
            seen.add(xl)
            dedup.append(xl)
    return dedup


def _parse_numeric_list(val):
    if val is None:
        return []
    items = val if isinstance(val, (list, tuple)) else [val]
    out = []
    for elem in items:
        if isinstance(elem, bool):
            continue
        if isinstance(elem, (int, float)):
            out.append(float(elem))
        elif isinstance(elem, TEXT_TYPES):
            m = re.search(r'([+-]?\d+(?:\.\d+)?)', str(elem).strip())
            if m:
                out.append(float(m.group(1)))
    return out


def _extract_global_supplies(spec_obj):
    if not isinstance(spec_obj, dict):
        return []
    out = []
    cov = spec_obj.get("coverage")
    for src in (cov if isinstance(cov, dict) else {}, spec_obj):
        for k in ("supplies_V", "supplies_v", "voltages", "voltages_V", "supplies", "vdd_V"):
            if k in src and src[k] is not None:
                out.extend(_parse_numeric_list(src[k]))
    dedup = []
    for v in out:
        if not any([abs(v - x) < 1e-6 for x in dedup]):
            dedup.append(v)
    return dedup


def _extract_global_temperatures(spec_obj):
    if not isinstance(spec_obj, dict):
        return []
    out = []
    cov = spec_obj.get("coverage")
    for src in (cov if isinstance(cov, dict) else {}, spec_obj):
        for k in ("temperatures_C", "temperatures_c", "temperatures", "temps_C", "temps"):
            if k in src and src[k] is not None:
                out.extend(_parse_numeric_list(src[k]))
    dedup = []
    for t in out:
        if not any([abs(t - x) < 1e-6 for x in dedup]):
            dedup.append(t)
    return dedup


def _extract_mc_requirement(spec_obj):
    """Return minimum required Monte Carlo point count (`0` if MC is not requested)."""
    if not isinstance(spec_obj, dict):
        return 0
    cov = spec_obj.get("coverage")
    mc = None
    if isinstance(cov, dict) and "monte_carlo" in cov:
        mc = cov.get("monte_carlo")
    elif "monte_carlo" in spec_obj:
        mc = spec_obj.get("monte_carlo")
    if mc is None or mc is False:
        return 0
    if mc is True:
        return 1
    if isinstance(mc, (int, float)):
        return int(mc) if mc > 0 else 0
    if isinstance(mc, TEXT_TYPES):
        s = str(mc).strip().lower()
        if s in ("", "none", "null", "false", "no", "0", "disabled", "off"):
            return 0
        m = re.search(r'(\d+)', s)
        return max(1, int(m.group(1))) if m else 1
    if isinstance(mc, dict):
        if mc.get("enabled") is False or mc.get("required") is False:
            return 0
        for rk in ("runs", "samples", "n", "count", "iterations"):
            if isinstance(mc.get(rk), (int, float)) and mc[rk] > 0:
                return int(mc[rk])
        if mc.get("enabled") or mc.get("required"):
            return 1
    return 0


def _extract_pex_requirement(spec_obj):
    if not isinstance(spec_obj, dict):
        return False
    cov = spec_obj.get("coverage")
    for src in (cov if isinstance(cov, dict) else {}, spec_obj):
        for k in ("post_layout", "pex"):
            if k in src and src[k] is not None:
                val = src[k]
                if isinstance(val, bool):
                    if val:
                        return True
                elif isinstance(val, TEXT_TYPES):
                    if str(val).strip().lower() not in ("", "none", "null", "false", "no", "0", "disabled", "off"):
                        return True
                elif isinstance(val, dict):
                    if val.get("required") or val.get("enabled"):
                        return True
                elif isinstance(val, (int, float)) and val > 0:
                    return True
    return False


def _match_supply_covered(v_req, points_metrics):
    tol_v = max(0.01, 0.02 * abs(v_req))
    for pt_label, pm in points_metrics.items():
        vdd = pm.get("vdd_v")
        if isinstance(vdd, (int, float)) and abs(float(vdd) - v_req) <= tol_v:
            return True
        for r in pm.get("supply_rails", []):
            rv = r.get("vdd_v")
            if isinstance(rv, (int, float)) and abs(float(rv) - v_req) <= tol_v:
                return True
        # Match label encodings like `1.62V`, `1p62V`, `VDD1p62`, `1620mV`
        lbl = str(pt_label).lower()
        for m in re.finditer(r'(?:^|[^a-z0-9])(?:vdd|vsup|v)?(\d+)[p.](\d+)(?:v)?(?:$|[^a-z0-9])', lbl):
            cand = float("%s.%s" % (m.group(1), m.group(2)))
            if abs(cand - v_req) <= tol_v:
                return True
        for m in re.finditer(r'(?:^|[^a-z0-9])(\d+(?:\.\d+)?)v(?:$|[^a-z0-9])', lbl):
            if abs(float(m.group(1)) - v_req) <= tol_v:
                return True
        for m in re.finditer(r'(?:^|[^a-z0-9])(\d+(?:\.\d+)?)mv(?:$|[^a-z0-9])', lbl):
            if abs(float(m.group(1)) * 1e-3 - v_req) <= tol_v:
                return True
    return False


def _match_temp_covered(t_req, points_metrics):
    t_int = int(round(t_req))
    abs_i = abs(t_int)
    for pt_label in points_metrics.keys():
        lbl = str(pt_label).lower()
        tokens = [t for t in re.split(r'[/_\s]+', lbl) if t]
        for tok in tokens:
            if t_int < 0:
                if re.match(r'^(?:-|m|n|neg|t-|tm|tn)%d(?:c|degc)?$' % abs_i, tok):
                    return True
            else:
                if re.match(r'^(?:t|temp)?%d(?:c|degc)?$' % abs_i, tok):
                    return True
        # Also handle hyphen-separated labels like `TT-125C` or `SS--40C`
        if t_int < 0:
            if re.search(r'(?:^|[^0-9])(?:-|m|n|neg)%dc(?:$|[^a-z0-9])' % abs_i, lbl):
                return True
        else:
            if re.search(r'(?:^|[^0-9\-])%dc(?:$|[^a-z0-9])' % abs_i, lbl):
                return True
    return False


def _count_mc_points(points_metrics):
    cnt = 0
    for pt_label, pm in points_metrics.items():
        if "mc" in pm.get("analyses_present", []):
            cnt += 1
            continue
        lbl = str(pt_label).lower()
        if re.search(r'(?:^|[/_\-\s])(?:mc\d*|montecarlo|monte_carlo|iter\d+)(?:$|[/_\-\s])', lbl):
            cnt += 1
    return cnt


def _has_pex_point(points_metrics):
    for pt_label in points_metrics.keys():
        lbl = str(pt_label).lower()
        if re.search(r'(?:^|[/_\-\s])(?:pex|postlayout|post_layout|extracted|av_extracted|rcx|quantus|calibre)(?:$|[/_\-\s])', lbl):
            return True
    return False


def _is_spec_approval_pending(spec_obj):
    """Fail-closed approval check using an explicit allowlist of approved states."""
    if not isinstance(spec_obj, dict):
        return False
    if "approval" not in spec_obj:
        # Schema v1 specs must explicitly provide an approved `approval` record
        schema_val = str(spec_obj.get("schema", "")).strip().lower()
        return schema_val.startswith("skill-analog.spec")
    app = spec_obj.get("approval")
    if app is None:
        return True
    approved_tokens = set(["approved", "signed_off", "signoff", "accepted", "confirmed", "yes", "true", "1"])
    if isinstance(app, bool):
        return not app
    if isinstance(app, TEXT_TYPES):
        return str(app).strip().lower() not in approved_tokens
    if isinstance(app, dict):
        has_approved = ("approved" in app)
        has_status = ("status" in app)
        if not has_approved and not has_status:
            return True
        if has_approved:
            if not isinstance(app["approved"], bool) or (not app["approved"]):
                return True
        if has_status:
            st = app.get("status")
            if st is None:
                return True
            if isinstance(st, bool):
                if not st:
                    return True
            elif isinstance(st, TEXT_TYPES):
                if str(st).strip().lower() not in approved_tokens:
                    return True
            else:
                return True
        return False
    return True


def _parse_freq_value(val, default_unit="hz"):
    if val is None or isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        scale = UNIT_SCALE_TO_SI.get(str(default_unit or "hz").lower(), 1.0)
        return float(val) * scale
    if isinstance(val, TEXT_TYPES):
        s = str(val).strip()
        m = re.match(r'^([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*([a-zA-Z]*)$', s)
        if m:
            num = float(m.group(1))
            u = m.group(2) or default_unit or "hz"
            if u in UNIT_SCALE_CASE_SENSITIVE:
                return num * UNIT_SCALE_CASE_SENSITIVE[u]
            ul = u.lower()
            if ul in UNIT_SCALE_TO_SI and UNIT_DIM_LOWER.get(ul) == "freq":
                return num * UNIT_SCALE_TO_SI[ul]
    return None


def _extract_req_freq_band(item, quantity_str=""):
    """Extract `(f_min_hz, f_max_hz)` from explicit band fields or noise requirement description."""
    fmin = None
    fmax = None
    for bkey in ("band_hz", "freq_band_hz", "freq_band", "band"):
        bval = item.get(bkey)
        if isinstance(bval, (list, tuple)) and len(bval) == 2:
            fmin = _parse_freq_value(bval[0], "hz")
            fmax = _parse_freq_value(bval[1], "hz")
        elif isinstance(bval, dict):
            fmin = _parse_freq_value(bval.get("min", bval.get("f_min", bval.get("low"))), "hz")
            fmax = _parse_freq_value(bval.get("max", bval.get("f_max", bval.get("high"))), "hz")
        elif isinstance(bval, TEXT_TYPES):
            m = re.search(
                r'(\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*(hz|khz|mhz|ghz)?\s*(?:-|to|\.\.)\s*(\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*(hz|khz|mhz|ghz)',
                str(bval),
                re.IGNORECASE,
            )
            if m:
                u2 = m.group(4)
                u1 = m.group(2) or u2
                fmin = _parse_freq_value(m.group(1) + u1, "hz")
                fmax = _parse_freq_value(m.group(3) + u2, "hz")
        if fmin is not None or fmax is not None:
            return fmin, fmax

    for lo_k in ("f_min_hz", "freq_min_hz", "fmin_hz", "f_min", "fmin"):
        if item.get(lo_k) is not None:
            fmin = _parse_freq_value(item.get(lo_k), "hz")
            break
    for hi_k in ("f_max_hz", "freq_max_hz", "fmax_hz", "f_max", "fmax"):
        if item.get(hi_k) is not None:
            fmax = _parse_freq_value(item.get(hi_k), "hz")
            break
    if fmin is not None or fmax is not None:
        return fmin, fmax

    # Fallback: scan text metadata (`measurement`, `notes`, `description`) for noise requirements
    q_low = str(quantity_str or "").lower()
    if "noise" in q_low:
        for tkey in ("measurement", "notes", "description", "label"):
            tval = item.get(tkey)
            if isinstance(tval, TEXT_TYPES):
                m = re.search(
                    r'(\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*(hz|khz|mhz|ghz)?\s*(?:-|to|\.\.)\s*(\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*(hz|khz|mhz|ghz)',
                    str(tval),
                    re.IGNORECASE,
                )
                if m:
                    u2 = m.group(4)
                    u1 = m.group(2) or u2
                    fmin = _parse_freq_value(m.group(1) + u1, "hz")
                    fmax = _parse_freq_value(m.group(3) + u2, "hz")
                    return fmin, fmax
    return None, None


def _extract_req_settling_meta(item):
    """Extract optional `(target_v, settling_tol_ratio)` from requirement item."""
    tv = None
    for k in ("target_v", "expected_final_v", "settle_target_v", "final_v"):
        if isinstance(item.get(k), (int, float)) and not isinstance(item.get(k), bool):
            tv = float(item[k])
            break
    tol_r = None
    for k in ("settling_tol_ratio", "settling_tol"):
        v = item.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0:
            tol_r = float(v)
            break
        elif isinstance(v, TEXT_TYPES):
            s = str(v).strip()
            if s.endswith("%"):
                try:
                    tol_r = float(s[:-1].strip()) / 100.0
                    break
                except ValueError:
                    pass
    if tol_r is None:
        for k in ("tol_pct", "tolerance_pct", "settling_tol_pct"):
            v = item.get(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0:
                tol_r = float(v) / 100.0
                break
    return tv, tol_r


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
            qty = item.get("quantity") or item.get("metric") or item.get("name") or ""
            f_lo, f_hi = _extract_req_freq_band(item, quantity_str=qty)
            tv, tol_r = _extract_req_settling_meta(item)
            reqs.append({
                "id": item.get("id", "REQ-%02d" % (idx + 1)),
                "quantity": qty,
                "operator": op,
                "target": tgt,
                "target_max": tgt_max,
                "unit": item.get("unit", ""),
                "conditions": _extract_req_conditions(item),
                "analysis": str(item["analysis"]).strip().lower() if item.get("analysis") else None,
                "freq_min_hz": f_lo,
                "freq_max_hz": f_hi,
                "target_v": tv,
                "settling_tol_ratio": tol_r,
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
                qty = item.get("quantity", item.get("metric", item.get("name", "")))
                f_lo, f_hi = _extract_req_freq_band(item, quantity_str=qty)
                tv, tol_r = _extract_req_settling_meta(item)
                reqs.append({
                    "id": item.get("id", "REQ-%02d" % (idx + 1)),
                    "quantity": qty,
                    "operator": op,
                    "target": tgt,
                    "target_max": tgt_max,
                    "unit": item.get("unit", ""),
                    "conditions": _extract_req_conditions(item),
                    "analysis": str(item["analysis"]).strip().lower() if item.get("analysis") else None,
                    "freq_min_hz": f_lo,
                    "freq_max_hz": f_hi,
                    "target_v": tv,
                    "settling_tol_ratio": tol_r,
                })
            return reqs

    src = spec_obj.get("targets") if (isinstance(spec_obj, dict) and isinstance(spec_obj.get("targets"), dict)) else spec_obj
    if isinstance(src, dict):
        skip_meta = set([
            "schema", "schema_revision", "project_name", "revision", "approval",
            "user_theory_constraints", "design_constraints", "subblock_budgets",
            "requirements", "coverage", "measurement_contract", "notes", "optimization",
            "corners", "conditions", "analyses", "supplies_V", "temperatures_C",
            "monte_carlo", "post_layout", "pex", "settling_target_v", "expected_final_v",
            "target_v", "settling_tol", "settling_tol_ratio",
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
                    "freq_min_hz": None,
                    "freq_max_hz": None,
                    "target_v": None,
                    "settling_tol_ratio": None,
                })
            elif isinstance(val, dict):
                unit = val.get("unit", "")
                req_conds = _extract_req_conditions(val)
                req_an = str(val["analysis"]).strip().lower() if val.get("analysis") else None
                f_lo, f_hi = _extract_req_freq_band(val, quantity_str=key)
                tv, tol_r = _extract_req_settling_meta(val)
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
                        "freq_min_hz": f_lo,
                        "freq_max_hz": f_hi,
                        "target_v": tv,
                        "settling_tol_ratio": tol_r,
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
                        "freq_min_hz": f_lo,
                        "freq_max_hz": f_hi,
                        "target_v": tv,
                        "settling_tol_ratio": tol_r,
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
                            "freq_min_hz": f_lo,
                            "freq_max_hz": f_hi,
                            "target_v": tv,
                            "settling_tol_ratio": tol_r,
                        })
    return reqs


def evaluate_spec(points_metrics, spec_obj, aux_data=None):
    approval_pending = _is_spec_approval_pending(spec_obj)
    global_conds = _extract_global_conditions(spec_obj)
    global_analyses = _extract_global_analyses(spec_obj)
    global_supplies = _extract_global_supplies(spec_obj)
    global_temps = _extract_global_temperatures(spec_obj)
    mc_req_runs = _extract_mc_requirement(spec_obj)
    pex_req = _extract_pex_requirement(spec_obj)
    reqs = _normalize_spec_requirements(spec_obj)

    if not reqs:
        out = {
            "verdict": "NOT_VERIFIED",
            "approval_pending": approval_pending,
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

    # Global coverage checks (enforced at spec level regardless of per-requirement condition scoping!)
    missing_global_corners = []
    for gc in global_conds:
        if not _match_condition_keys(gc, available_keys):
            missing_global_corners.append(gc)

    missing_global_analyses = []
    for req_an in global_analyses:
        for pk in available_keys:
            present = points_metrics[pk].get("analyses_present", [])
            if req_an not in present and req_an not in missing_global_analyses:
                missing_global_analyses.append(req_an)

    missing_global_supplies = [v for v in global_supplies if not _match_supply_covered(v, points_metrics)]
    missing_global_temps = [t for t in global_temps if not _match_temp_covered(t, points_metrics)]
    missing_coverage_flags = []
    if mc_req_runs > 0 and _count_mc_points(points_metrics) < mc_req_runs:
        missing_coverage_flags.append("monte_carlo")
    if pex_req and (not _has_pex_point(points_metrics)):
        missing_coverage_flags.append("post_layout")

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

        canon_metric_key = _resolve_metric_key(req["quantity"], {})
        target_si, unit_err = _scale_target_to_si(req["target"], req.get("unit", ""), metric_key=canon_metric_key)
        target_max_si, unit_max_err = _scale_target_to_si(
            req.get("target_max"), req.get("unit", ""), metric_key=canon_metric_key
        )
        if unit_err or unit_max_err:
            nv_n += 1
            results.append({
                "id": req["id"],
                "quantity": req["quantity"],
                "operator": req["operator"],
                "target": req["target"],
                "unit": req.get("unit", ""),
                "status": "NOT_VERIFIED",
                "reason": unit_err or unit_max_err,
            })
            continue

        op = req["operator"]
        req_conds = req.get("conditions") or []
        req_an = req.get("analysis")
        req_fmin = req.get("freq_min_hz")
        req_fmax = req.get("freq_max_hz")
        req_tv = req.get("target_v")
        req_tol_r = req.get("settling_tol_ratio")

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
                # Exact analysis match: `.pstb` populates BOTH `stb` and `pstb`, `.stb` populates ONLY `stb`!
                if req_an not in m_dict.get("analyses_present", []):
                    any_missing = True
                    req_reason = req_reason or "missing_analysis"
                    per_cond[cond_name] = {"measured_si": None, "status": "NOT_VERIFIED", "reason": "missing_analysis"}
                    continue

            m_key = _resolve_metric_key(req["quantity"], m_dict)
            m_val = m_dict.get(m_key)

            # Frequency-band strict verification & integration for integrated RMS noise requirements
            if m_key in ("integrated_rms_noise_v", "integrated_rms_noise_a") and (req_fmin is not None or req_fmax is not None):
                req_domain = "voltage" if m_key == "integrated_rms_noise_v" else "current"
                pt_aux = (aux_data or {}).get(cond_name, {}) if isinstance(aux_data, dict) else {}
                curves = [c for c in pt_aux.get("noise_curves", []) if c.get("domain") == req_domain]
                if curves:
                    band_rms_vals = []
                    band_err = None
                    for c_info in curves:
                        b_rms, b_err = _integrate_psd_band(c_info["freqs"], c_info["psd"], f_min=req_fmin, f_max=req_fmax)
                        if b_err:
                            band_err = b_err
                            break
                        band_rms_vals.append(b_rms)
                    if band_err or not band_rms_vals:
                        any_missing = True
                        req_reason = req_reason or (band_err or "noise_band_unverified")
                        per_cond[cond_name] = {
                            "measured_si": None,
                            "status": "NOT_VERIFIED",
                            "reason": band_err or "noise_band_unverified",
                        }
                        continue
                    m_val = max(band_rms_vals)
                else:
                    f_lo = m_dict.get("noise_freq_min_hz")
                    f_hi = m_dict.get("noise_freq_max_hz")
                    if f_lo is None or f_hi is None:
                        any_missing = True
                        req_reason = req_reason or "noise_band_unverified"
                        per_cond[cond_name] = {
                            "measured_si": None,
                            "status": "NOT_VERIFIED",
                            "reason": "noise_band_unverified",
                        }
                        continue
                    lo_ok = (req_fmin is None) or (float(f_lo) <= float(req_fmin) * (1.0 + 1e-6) + 1e-12)
                    hi_ok = (req_fmax is None) or (float(f_hi) >= float(req_fmax) * (1.0 - 1e-6) - 1e-12)
                    if not (lo_ok and hi_ok):
                        any_missing = True
                        req_reason = req_reason or "noise_band_not_covered"
                        per_cond[cond_name] = {
                            "measured_si": None,
                            "status": "NOT_VERIFIED",
                            "reason": "noise_band_not_covered",
                        }
                        continue

            # Static target voltage verification for settling_time_s requirements
            if m_key == "settling_time_s":
                if req_tv is not None and isinstance(m_dict.get("tran_final_v"), (int, float)):
                    v_init_m = m_dict.get("tran_init_v")
                    v_init_f = float(v_init_m) if isinstance(v_init_m, (int, float)) else 0.0
                    tol_ratio_eff = req_tol_r if req_tol_r is not None else 0.01
                    tol_v = tol_ratio_eff * max(abs(float(req_tv) - v_init_f), 1e-9)
                    if abs(float(m_dict["tran_final_v"]) - float(req_tv)) > tol_v:
                        any_failed = True
                        per_cond[cond_name] = {
                            "measured_si": None,
                            "status": "FAIL",
                            "reason": "static_target_voltage_error",
                            "static_error_v": _round_clean(float(m_dict["tran_final_v"]) - float(req_tv)),
                        }
                        continue
                if m_val is None and isinstance(m_dict.get("static_error_v"), (int, float)) and abs(float(m_dict["static_error_v"])) > 0.0:
                    any_failed = True
                    per_cond[cond_name] = {
                        "measured_si": None,
                        "status": "FAIL",
                        "reason": "static_target_voltage_error",
                        "static_error_v": _round_clean(m_dict["static_error_v"]),
                    }
                    continue

            if m_val is None:
                any_missing = True
                miss_r = "rhp_open_loop_pole_suspected" if (
                    m_key in ("phase_margin_deg", "gain_margin_db") and m_dict.get("rhp_open_loop_pole_suspected")
                ) else "missing_metric"
                req_reason = req_reason or miss_r
                per_cond[cond_name] = {"measured_si": None, "status": "NOT_VERIFIED", "reason": miss_r}
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
    has_missing_cov = bool(
        missing_global_corners
        or missing_global_analyses
        or missing_global_supplies
        or missing_global_temps
        or missing_coverage_flags
    )
    if fail_n > 0:
        verdict = "FAIL"
    elif approval_pending:
        verdict = "NOT_VERIFIED"
        overall_reason = "spec_approval_pending"
    elif missing_global_corners:
        verdict = "NOT_VERIFIED"
        overall_reason = "missing_required_corners"
    elif missing_global_analyses:
        verdict = "NOT_VERIFIED"
        overall_reason = "missing_required_analyses"
    elif has_missing_cov:
        verdict = "NOT_VERIFIED"
        overall_reason = "missing_required_coverage"
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
    if missing_global_corners:
        summary_out["missing_corners"] = missing_global_corners
    if missing_global_analyses:
        summary_out["missing_analyses"] = missing_global_analyses
    if missing_global_supplies:
        summary_out["missing_supplies_V"] = missing_global_supplies
    if missing_global_temps:
        summary_out["missing_temperatures_C"] = missing_global_temps
    if missing_coverage_flags:
        summary_out["missing_coverage"] = missing_coverage_flags
    return summary_out


def _extract_spec_settling_defaults(spec_obj):
    if not isinstance(spec_obj, dict):
        return None, None
    tv, tol_r = _extract_req_settling_meta(spec_obj)
    if tv is None or tol_r is None:
        for req in _normalize_spec_requirements(spec_obj):
            if _resolve_metric_key(req["quantity"], {}) == "settling_time_s":
                if tv is None and req.get("target_v") is not None:
                    tv = req["target_v"]
                if tol_r is None and req.get("settling_tol_ratio") is not None:
                    tol_r = req["settling_tol_ratio"]
    return tv, tol_r


def run_metrics(run_dir, spec_path=None, vout_hint=None, vin_hint=None, settling_tol_ratio=0.01, target_v=None):
    point_files = _discover_run_points(run_dir)
    if not point_files:
        raise ValueError("No PSF ASCII simulation files found under: " + str(run_dir))

    spec_obj = None
    eff_target_v = target_v
    eff_settling_tol = settling_tol_ratio
    if spec_path is not None:
        if not os.path.isfile(spec_path):
            raise ValueError("Spec file not found: " + str(spec_path))
        s_handle = open(spec_path, "rb")
        try:
            spec_obj = json.loads(s_handle.read().decode("utf-8-sig"))
        finally:
            s_handle.close()
        spec_tv, spec_tol = _extract_spec_settling_defaults(spec_obj)
        if eff_target_v is None and spec_tv is not None:
            eff_target_v = spec_tv
        if spec_tol is not None and settling_tol_ratio == 0.01:
            eff_settling_tol = spec_tol

    points_metrics = {}
    aux_data = {}
    base_dir = run_dir if os.path.isdir(run_dir) else os.path.dirname(run_dir)
    for pt_label in sorted(point_files.keys()):
        pt_aux = {}
        points_metrics[pt_label] = _extract_point_metrics(
            point_files[pt_label],
            vout_hint=vout_hint,
            vin_hint=vin_hint,
            settling_tol_ratio=eff_settling_tol,
            target_v=eff_target_v,
            base_dir=base_dir,
            aux_out=pt_aux,
        )
        if pt_aux:
            aux_data[pt_label] = pt_aux

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

    if spec_obj is not None:
        spec_eval = evaluate_spec(points_metrics, spec_obj, aux_data=aux_data)
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

        # 6. Static Target Voltage Error (0.980 V vs 1.000 V target, 0.02% tol, 10 ns limit -> MUST FAIL!)
        st_dir = os.path.join(tmp_root, "static_err_tran")
        st_lines = ['HEADER\n"PSFversion" "1.00"\nTYPE\n"r_t" FLOAT DOUBLE\nSWEEP\n"time" "r_t"\nTRACE\n"Vin" "r_t"\n"Vout" "r_t"\nVALUE\n']
        for k in range(51):
            t_k = k * 0.2e-9  # 0 .. 10 ns
            vin_k = 0.0 if k == 0 else 1.0
            vout_k = 0.980 * (1.0 - math.exp(-t_k / 0.3e-9))
            st_lines.append('"time" %.6e\n"Vin" %.6e\n"Vout" %.6e\n' % (t_k, vin_k, vout_k))
        st_lines.append("END\n")
        _write_utf8(os.path.join(st_dir, "tran.tran"), "".join(st_lines))
        spec_st = {
            "requirements": [{
                "id": "TS_STATIC",
                "quantity": "settling_time_s",
                "operator": "<=",
                "target": 10.0,
                "unit": "ns",
                "target_v": 1.0,
                "settling_tol": 0.0002,
            }]
        }
        spec_st_path = os.path.join(tmp_root, "spec_st.json")
        _write_utf8(spec_st_path, json.dumps(spec_st))
        res_st = run_metrics(st_dir, spec_path=spec_st_path, settling_tol_ratio=0.0002, target_v=1.0)
        assert res_st["metrics"]["settling_time_s"] is None, res_st["metrics"]
        assert abs(res_st["metrics"]["static_error_v"] + 0.020) < 1e-4, res_st["metrics"]
        assert res_st["verdict"] == "FAIL", res_st

        # 7. Dual-Edge Pulse with 20 ns Propagation Delay MUST preserve delay (>= 20 ns, FAILS <= 10 ns spec)
        dp_dir = os.path.join(tmp_root, "dual_pulse_delay")
        dp_lines = ['HEADER\n"PSFversion" "1.00"\nTYPE\n"r_t" FLOAT DOUBLE\nSWEEP\n"time" "r_t"\nTRACE\n"Vin" "r_t"\n"Vout" "r_t"\nVALUE\n']
        for k in range(121):
            t_k = k * 1.0e-9  # 0 .. 120 ns
            vin_k = 1.0 if (10.0e-9 <= t_k < 60.0e-9) else 0.0
            if t_k < 30.0e-9:
                vout_k = 0.0
            elif t_k < 80.0e-9:
                vout_k = 1.0 - math.exp(-(t_k - 30.0e-9) / 0.2e-9)
            else:
                vout_k = math.exp(-(t_k - 80.0e-9) / 0.2e-9)
            dp_lines.append('"time" %.6e\n"Vin" %.6e\n"Vout" %.6e\n' % (t_k, vin_k, vout_k))
        dp_lines.append("END\n")
        _write_utf8(os.path.join(dp_dir, "tran.tran"), "".join(dp_lines))
        res_dp = run_metrics(dp_dir, settling_tol_ratio=0.01)
        assert res_dp["metrics"]["settling_time_s"] is not None, res_dp["metrics"]
        assert res_dp["metrics"]["settling_time_s"] >= 20.0e-9, res_dp["metrics"]

        # 8. Non-Uniform Dense-Tail Linear Ramp (without plateau) MUST still return settling_time_s = None
        nr_psf = os.path.join(tmp_root, "nonuniform_ramp.tran")
        nr_times = [k * 0.5e-9 for k in range(20)] + [9.95e-9 + j * 0.005e-9 for j in range(11)]
        nr_lines = ['HEADER\n"PSFversion" "1.00"\nTYPE\n"r_t" FLOAT DOUBLE\nSWEEP\n"time" "r_t"\nTRACE\n"Vout" "r_t"\nVALUE\n']
        for t_k in nr_times:
            nr_lines.append('"time" %.6e\n"Vout" %.6e\n' % (t_k, 1.0 * (t_k / 10.0e-9)))
        nr_lines.append("END\n")
        _write_utf8(nr_psf, "".join(nr_lines))
        res_nr = run_metrics(nr_psf, settling_tol_ratio=0.01)
        assert res_nr["metrics"]["settling_time_s"] is None, res_nr["metrics"]

        # 9. Swept DC Power & Multi-DC Files (20 uW at idx 0, 2 mW at idx 1 -> worst-case 2 mW) + Cross-Rail Fail-Closed
        dcs_dir = os.path.join(tmp_root, "dc_sweep")
        _write_utf8(os.path.join(dcs_dir, "dcOp.dc"), (
            'HEADER\n"PSFversion" "1.00"\n'
            'TYPE\n"v_t" FLOAT DOUBLE PROP( "units" "V" )\n"i_t" FLOAT DOUBLE PROP( "units" "A" )\n'
            'VALUE\n"VDD" "v_t" 1.0\n"VDD:p" "i_t" -2.0e-5\nEND\n'
        ))
        _write_utf8(os.path.join(dcs_dir, "dcSweep.dc"), (
            'HEADER\n"PSFversion" "1.00"\n'
            'TYPE\n"s_t" FLOAT DOUBLE\n"v_t" FLOAT DOUBLE PROP( "units" "V" )\n"i_t" FLOAT DOUBLE PROP( "units" "A" )\n'
            'SWEEP\n"vin" "s_t"\nTRACE\n"VDD" "v_t"\n"VDD:p" "i_t"\nVALUE\n'
            '"vin" 0.0\n"VDD" 1.0\n"VDD:p" -2.0e-5\n'
            '"vin" 1.0\n"VDD" 1.0\n"VDD:p" -2.0e-3\n'
            'END\n'
        ))
        res_dcs = run_metrics(dcs_dir)
        assert abs(res_dcs["metrics"]["dc_power_w"] - 0.002) < 1e-9, res_dcs["metrics"]

        # Cross-rail mismatch (`VDD` + `VDD18:p`) MUST fail closed (`dc_power_w is None`, `ambiguous_multi_rail`)
        xrail_dir = os.path.join(tmp_root, "xrail")
        _write_utf8(os.path.join(xrail_dir, "dcOp.dc"), (
            'HEADER\n"PSFversion" "1.00"\n'
            'TYPE\n"v_t" FLOAT DOUBLE PROP( "units" "V" )\n"i_t" FLOAT DOUBLE PROP( "units" "A" )\n'
            'VALUE\n"VDD" "v_t" 1.0\n"VDD18:p" "i_t" -2.0e-3\nEND\n'
        ))
        res_xrail = run_metrics(xrail_dir)
        assert res_xrail["metrics"]["dc_power_w"] is None, res_xrail["metrics"]
        assert res_xrail["metrics"]["power_method"] == "ambiguous_multi_rail", res_xrail["metrics"]

        # 10. Duplicate Basename STB Collision (`raw/dm.stb` 20 deg + `psf/dm.stb` 70 deg -> MUST keep 20 deg!)
        dup_stb_dir = os.path.join(tmp_root, "dup_stb")
        _write_utf8(os.path.join(dup_stb_dir, "raw", "dm.stb"), (
            'HEADER\n"PSFversion" "1.00"\nTYPE\n"f_t" FLOAT DOUBLE\n"c_t" COMPLEX DOUBLE\n'
            'SWEEP\n"freq" "f_t"\nTRACE\n"loopGain" "c_t"\nVALUE\n'
            '"freq" 1.0\n"loopGain" (1000.0 0.0)\n'
            '"freq" 1.0e6\n"loopGain" (-0.93969 -0.34202)\n'
            '"freq" 1.0e7\n"loopGain" (-0.1 0.0)\nEND\n'
        ))
        _write_utf8(os.path.join(dup_stb_dir, "psf", "dm.stb"), (
            'HEADER\n"PSFversion" "1.00"\nTYPE\n"f_t" FLOAT DOUBLE\n"c_t" COMPLEX DOUBLE\n'
            'SWEEP\n"freq" "f_t"\nTRACE\n"loopGain" "c_t"\nVALUE\n'
            '"freq" 1.0\n"loopGain" (1000.0 0.0)\n'
            '"freq" 1.0e6\n"loopGain" (0.34202 -0.93969)\n'
            '"freq" 1.0e7\n"loopGain" (-0.1 0.0)\nEND\n'
        ))
        res_dup_stb = run_metrics(dup_stb_dir)
        assert res_dup_stb["metrics"]["phase_margin_deg"] < 25.0, res_dup_stb["metrics"]
        assert len(res_dup_stb["metrics"]["stb_loops"]) == 2, res_dup_stb["metrics"]

        # 11. Mismatched STB Margin Pairing (`cmfb.stb` missing PM + `dm.margin.stb` 70 deg -> MUST NOT borrow 70 deg!)
        mis_stb_dir = os.path.join(tmp_root, "mis_stb")
        _write_utf8(os.path.join(mis_stb_dir, "cmfb.stb"), (
            'HEADER\n"PSFversion" "1.00"\nTYPE\n"f_t" FLOAT DOUBLE\n"c_t" COMPLEX DOUBLE\n'
            'SWEEP\n"freq" "f_t"\nTRACE\n"loopGain" "c_t"\nVALUE\n'
            '"freq" 1.0\n"loopGain" (100.0 0.0)\n"freq" 1.0e3\n"loopGain" (50.0 -10.0)\nEND\n'
        ))
        _write_utf8(os.path.join(mis_stb_dir, "dm.margin.stb"), (
            'HEADER\n"PSFversion" "1.00"\nTYPE\n"r_t" FLOAT DOUBLE\nVALUE\n'
            '"phaseMargin" "r_t" 70.0\n"phaseMarginFreq" "r_t" 1.0e6\nEND\n'
        ))
        res_mis_stb = run_metrics(mis_stb_dir)
        assert res_mis_stb["metrics"]["phase_margin_deg"] is None, res_mis_stb["metrics"]

        # 12. RHP Open-Loop Pole (`L(s)=3/(s-1)^2`, nominal Bode PM=70.53 deg but UNSTABLE -> fail closed!)
        rhp_dir = os.path.join(tmp_root, "rhp_stb")
        rhp_lines = ['HEADER\n"PSFversion" "1.00"\nTYPE\n"f_t" FLOAT DOUBLE\n"c_t" COMPLEX DOUBLE\nSWEEP\n"freq" "f_t"\nTRACE\n"loopGain" "c_t"\nVALUE\n']
        for w in (0.01, 0.1, 0.5, 1.0, 1.41421356, 2.0, 5.0, 20.0):
            s_c = complex(0.0, w)
            l_val = 3.0 / ((s_c - 1.0) * (s_c - 1.0))
            rhp_lines.append('"freq" %.6e\n"loopGain" (%.8e %.8e)\n' % (w / (2.0 * math.pi), l_val.real, l_val.imag))
        rhp_lines.append("END\n")
        _write_utf8(os.path.join(rhp_dir, "stb.stb"), "".join(rhp_lines))
        res_rhp = run_metrics(rhp_dir)
        assert res_rhp["metrics"]["phase_margin_deg"] is None, res_rhp["metrics"]
        assert res_rhp["metrics"].get("rhp_open_loop_pole_suspected") is True, res_rhp["metrics"]

        # 13. PSTB vs STB Distinction (spec asks for `pstb`, only `stb.stb` present -> NOT_VERIFIED)
        eval_pstb = evaluate_spec(
            {"TT": {"phase_margin_deg": 65.0, "analyses_present": ["stb"]}},
            {"requirements": [{"id": "P1", "quantity": "pm", "operator": ">=", "target": 60.0, "unit": "deg", "analysis": "pstb"}]},
        )
        assert eval_pstb["verdict"] == "NOT_VERIFIED", eval_pstb
        assert eval_pstb["results"][0]["reason"] == "missing_analysis", eval_pstb

        # 14. Noise Descending Freq (`100 -> 10 Hz` -> 9.49 uVrms, NOT 0) & Band Coverage (`0.5-300 Hz` vs `1 MHz` -> NOT_VERIFIED)
        ns_desc_dir = os.path.join(tmp_root, "noise_desc")
        _write_utf8(os.path.join(ns_desc_dir, "noise.noise"), (
            'HEADER\n"PSFversion" "1.00"\n'
            'TYPE\n"f_t" FLOAT DOUBLE PROP( "units" "Hz" )\n"vn_t" FLOAT DOUBLE PROP( "units" "V/sqrt(Hz)" )\n'
            'SWEEP\n"freq" "f_t"\nTRACE\n"out" "vn_t"\nVALUE\n'
            '"freq" 100.0\n"out" 1.0e-6\n'
            '"freq" 10.0\n"out" 1.0e-6\nEND\n'
        ))
        res_ns_desc = run_metrics(ns_desc_dir)
        assert abs(res_ns_desc["metrics"]["integrated_rms_noise_v"] - math.sqrt(90.0) * 1.0e-6) < 1e-10, res_ns_desc["metrics"]

        ns_hi_dir = os.path.join(tmp_root, "noise_hi")
        _write_utf8(os.path.join(ns_hi_dir, "noise.noise"), (
            'HEADER\n"PSFversion" "1.00"\n'
            'TYPE\n"f_t" FLOAT DOUBLE PROP( "units" "Hz" )\n"vn_t" FLOAT DOUBLE PROP( "units" "V/sqrt(Hz)" )\n'
            'SWEEP\n"freq" "f_t"\nTRACE\n"out" "vn_t"\nVALUE\n'
            '"freq" 1.0e6\n"out" 1.0e-9\n'
            '"freq" 1.0e7\n"out" 1.0e-9\nEND\n'
        ))
        spec_ns_band = {
            "requirements": [{
                "id": "N1",
                "quantity": "integrated_rms_noise_v",
                "operator": "<=",
                "target": 10.0,
                "unit": "uVrms",
                "band_hz": [0.5, 300.0],
            }]
        }
        spec_ns_path = os.path.join(tmp_root, "spec_ns.json")
        _write_utf8(spec_ns_path, json.dumps(spec_ns_band))
        res_ns_band = run_metrics(ns_hi_dir, spec_path=spec_ns_path)
        assert res_ns_band["verdict"] == "NOT_VERIFIED", res_ns_band
        assert res_ns_band["spec_evaluation"]["results"][0]["reason"] == "noise_band_not_covered", res_ns_band

        # 15. AC Differential Input (`inp-inn` = 0.1 V, `outp-outn` = 0.5 V -> +13.98 dB) + Strict Missing `--vin`/`--vout`
        ac_diff_dir = os.path.join(tmp_root, "ac_diff")
        _write_utf8(os.path.join(ac_diff_dir, "ac.ac"), (
            'HEADER\n"PSFversion" "1.00"\nTYPE\n"f_t" FLOAT DOUBLE\n"c_t" COMPLEX DOUBLE\n'
            'SWEEP\n"freq" "f_t"\nTRACE\n"inp" "c_t"\n"inn" "c_t"\n"outp" "c_t"\n"outn" "c_t"\nVALUE\n'
            '"freq" 1.0\n"inp" (0.05 0.0)\n"inn" (-0.05 0.0)\n"outp" (0.25 0.0)\n"outn" (-0.25 0.0)\n'
            '"freq" 1.0e6\n"inp" (0.05 0.0)\n"inn" (-0.05 0.0)\n"outp" (0.02 -0.02)\n"outn" (-0.02 0.02)\nEND\n'
        ))
        res_ac_diff = run_metrics(ac_diff_dir)
        assert abs(res_ac_diff["metrics"]["dc_gain_db"] - (20.0 * math.log10(5.0))) < 1e-4, res_ac_diff["metrics"]
        res_ac_bad_vin = run_metrics(ac_diff_dir, vin_hint="nonexistent_vin")
        assert res_ac_bad_vin["metrics"]["dc_gain_db"] is None, res_ac_bad_vin["metrics"]
        res_tr_bad_vout = run_metrics(dp_dir, vout_hint="nonexistent_vout")
        assert res_tr_bad_vout["metrics"]["settling_time_s"] is None, res_tr_bad_vout["metrics"]

        # 16. Unit Dimension Mismatch (`mV` on `dc_gain_db`), Strict Approval Allowlist, & Global PVT/Coverage Checks
        eval_dim = evaluate_spec(
            {"TT": {"dc_gain_db": 60.0, "analyses_present": ["ac"]}},
            {"requirements": [{"id": "D1", "quantity": "dc_gain_db", "operator": ">=", "target": 50.0, "unit": "mV"}]},
        )
        assert eval_dim["verdict"] == "NOT_VERIFIED", eval_dim
        assert eval_dim["results"][0]["reason"] == "unit_dimension_mismatch", eval_dim

        for bad_app in (None, "awaiting_review", {"status": "awaiting_review"}, {}):
            eval_app = evaluate_spec(
                {"TT": {"dc_gain_db": 60.0, "analyses_present": ["ac"]}},
                {"approval": bad_app, "requirements": [{"id": "A1", "quantity": "dc_gain_db", "operator": ">=", "target": 50.0, "unit": "dB"}]},
            )
            assert eval_app["verdict"] == "NOT_VERIFIED", (bad_app, eval_app)
            assert eval_app["reason"] == "spec_approval_pending", (bad_app, eval_app)

        eval_gcov = evaluate_spec(
            {"TT": {"dc_gain_db": 60.0, "vdd_v": 1.8, "analyses_present": ["ac"]}},
            {
                "coverage": {
                    "corners": ["TT", "SS"],
                    "supplies_V": [1.62, 1.8],
                    "temperatures_C": [-40, 125],
                    "monte_carlo": 100,
                    "post_layout": True,
                },
                "requirements": [{"id": "G1", "quantity": "dc_gain_db", "operator": ">=", "target": 50.0, "unit": "dB", "conditions": ["TT"]}],
            },
        )
        assert eval_gcov["verdict"] == "NOT_VERIFIED", eval_gcov
        assert "SS" in eval_gcov.get("missing_corners", []), eval_gcov
        assert 1.62 in eval_gcov.get("missing_supplies_V", []), eval_gcov
        assert -40.0 in eval_gcov.get("missing_temperatures_C", []), eval_gcov
        assert "monte_carlo" in eval_gcov.get("missing_coverage", []), eval_gcov
        assert "post_layout" in eval_gcov.get("missing_coverage", []), eval_gcov

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
                "static_target_voltage_error_fails_settling",
                "dual_edge_pulse_preserves_input_propagation_delay",
                "nonuniform_dense_tail_ramp_rejected",
                "dc_sweep_max_power_and_cross_rail_fail_closed",
                "duplicate_basename_stb_collision_preserved",
                "mismatched_stb_margin_not_cross_paired",
                "rhp_open_loop_pole_bode_violation_fail_closed",
                "pstb_distinct_from_stb",
                "noise_descending_sort_and_band_coverage_check",
                "ac_differential_input_and_strict_vin_vout",
                "unit_dimension_mismatch_approval_allowlist_and_global_pvt_coverage",
            ],
        }
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


HELP_TEXT = """Usage:
  python tools/psf_audit.py op-audit  <run_or_psf_path> [--vds-margin 0.05] [--expect-triode M_R1,M_SW] [--fail-on-violation]
  python tools/psf_audit.py metrics   <run_dir> [--spec spec.json] [--vout Vout] [--vin Vin] [--settling-tol 0.01] [--target-v 1.0] [--fail-on-spec]
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
        parser.add_option("--target-v", type="float", dest="target_v", default=None)
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
                target_v=opts.target_v,
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
