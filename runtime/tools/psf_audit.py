#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Spectre 15.1 Strict Fail-Closed Operating-Point Auditor & Spec Metrics Sign-Off Engine.

100% Python 2.6.6+ and Python 3 standard-library compatible (`optparse` CLI, zero external deps).

Subcommands:
  op-audit  <run_or_psf_path> [--vds-margin 0.05] [--expect-triode M_R1,M_SW] [--fail-on-violation]
  metrics   <run_dir> [--spec spec.json] [--fail-on-spec]
  self-test (or --self-test)
"""
from __future__ import division, print_function

import hashlib
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

try:
    _INT_TYPES = (int, long)  # noqa: F821
except NameError:
    _INT_TYPES = (int,)
_NUM_TYPES = _INT_TYPES + (float,)

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
    "mS": 1e-3,
    "S": 1.0,
    "mSiemens": 1e-3,
    "mF": 1e-3,
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
    "mS": "conductance",
    "S": "conductance",
    "mSiemens": "conductance",
    "mF": "capacitance",
}

UNIT_SCALE_TO_SI = {
    "": 1.0,
    # Frequency
    "hz": 1.0, "khz": 1e3, "mhz": 1e6, "ghz": 1e9, "thz": 1e12,
    # Time
    "s": 1.0, "sec": 1.0, "secs": 1.0, "second": 1.0, "seconds": 1.0,
    "ms": 1e-3, "msec": 1e-3, "msecs": 1e-3, "millisecond": 1e-3, "milliseconds": 1e-3,
    "us": 1e-6, "usec": 1e-6, "usecs": 1e-6, "microsecond": 1e-6, "microseconds": 1e-6,
    "ns": 1e-9, "nsec": 1e-9, "nsecs": 1e-9, "nanosecond": 1e-9, "nanoseconds": 1e-9,
    "ps": 1e-12, "psec": 1e-12, "psecs": 1e-12, "picosecond": 1e-12, "picoseconds": 1e-12,
    "fs": 1e-15, "fsec": 1e-15, "fsecs": 1e-15, "femtosecond": 1e-15, "femtoseconds": 1e-15,
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
    "siemens": 1.0, "ksiemens": 1e3, "msiemens": 1e-3, "usiemens": 1e-6, "nsiemens": 1e-9, "psiemens": 1e-12,
    "mho": 1.0, "mmho": 1e-3, "umho": 1e-6, "nmho": 1e-9,
    "a/v": 1.0, "ma/v": 1e-3, "ua/v": 1e-6, "na/v": 1e-9, "pa/v": 1e-12,
    # Capacitance & Inductance & Charge
    "f": 1.0, "mf": 1e-3, "uf": 1e-6, "nf": 1e-9, "pf": 1e-12, "ff": 1e-15, "af": 1e-18,
    "h": 1.0, "mh": 1e-3, "uh": 1e-6, "nh": 1e-9, "ph": 1e-12,
    "c": 1.0, "mc": 1e-3, "uc": 1e-6, "nc": 1e-9, "pc": 1e-12, "fc": 1e-15,
    # Slew rate
    "v/s": 1.0, "mv/s": 1e-3, "uv/s": 1e-6,
    "v/ms": 1e3, "v/us": 1e6, "v/ns": 1e9, "v/ps": 1e12,
    "mv/ms": 1.0, "mv/us": 1e3, "mv/ns": 1e6, "mv/ps": 1e9, "kv/us": 1e9,
    "uv/us": 1.0, "uv/ns": 1e3,
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
    "rad": 180.0 / math.pi, "rads": 180.0 / math.pi, "radian": 180.0 / math.pi, "radians": 180.0 / math.pi,
    "%": 1.0, "pct": 1.0, "percent": 1.0,
    "v/v": 1.0, "a/a": 1.0, "s/a": 1.0, "1/v": 1.0, "v^-1": 1.0,
}

UNIT_DIM_LOWER = {
    "": None,
    "hz": "freq", "khz": "freq", "mhz": "freq", "ghz": "freq", "thz": "freq",
    "s": "time", "sec": "time", "secs": "time", "second": "time", "seconds": "time",
    "ms": "time", "msec": "time", "msecs": "time", "millisecond": "time", "milliseconds": "time",
    "us": "time", "usec": "time", "usecs": "time", "microsecond": "time", "microseconds": "time",
    "ns": "time", "nsec": "time", "nsecs": "time", "nanosecond": "time", "nanoseconds": "time",
    "ps": "time", "psec": "time", "psecs": "time", "picosecond": "time", "picoseconds": "time",
    "fs": "time", "fsec": "time", "fsecs": "time", "femtosecond": "time", "femtoseconds": "time",
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
    "siemens": "conductance", "ksiemens": "conductance", "msiemens": "conductance", "usiemens": "conductance", "nsiemens": "conductance", "psiemens": "conductance",
    "mho": "conductance", "mmho": "conductance", "umho": "conductance", "nmho": "conductance",
    "a/v": "conductance", "ma/v": "conductance", "ua/v": "conductance", "na/v": "conductance", "pa/v": "conductance",
    "f": "capacitance", "mf": "capacitance", "uf": "capacitance", "nf": "capacitance", "pf": "capacitance", "ff": "capacitance", "af": "capacitance",
    "h": "inductance", "mh": "inductance", "uh": "inductance", "nh": "inductance", "ph": "inductance",
    "c": "charge", "mc": "charge", "uc": "charge", "nc": "charge", "pc": "charge", "fc": "charge",
    "v/s": "slew_rate", "mv/s": "slew_rate", "uv/s": "slew_rate",
    "v/ms": "slew_rate", "v/us": "slew_rate", "v/ns": "slew_rate", "v/ps": "slew_rate",
    "mv/ms": "slew_rate", "mv/us": "slew_rate", "mv/ns": "slew_rate", "mv/ps": "slew_rate", "kv/us": "slew_rate",
    "uv/us": "slew_rate", "uv/ns": "slew_rate",
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
    "rad": "angle", "rads": "angle", "radian": "angle", "radians": "angle",
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

NEG_SUPPLY_RAIL_PREFIXES = (
    "vss", "avss", "dvss", "vee", "avee", "dvee", "vneg",
)

NON_SUPPLY_STIM_STEMS = (
    "vin", "vip", "vinp", "vinn", "vin_ac", "vin_p", "vin_n", "in", "inp", "inn",
    "vout", "vop", "von", "out", "outp", "outn",
    "vcm", "vocm", "vicm", "vbias", "vref", "vstep", "vpulse",
    "vclk", "clk", "ven", "en", "vctrl", "ctrl", "vfb", "fb", "vtest", "vprobe", "iprobe",
    "gnd", "agnd", "dgnd", "0",
)


_TRACE_UNIT_ALIASES_LOWER = {
    "amp": "a", "amps": "a", "ampere": "a", "amperes": "a",
    "kamp": "ka", "kamps": "ka",
    "mamp": "ma", "mamps": "ma", "milliamp": "ma", "milliamps": "ma",
    "uamp": "ua", "uamps": "ua", "microamp": "ua", "microamps": "ua",
    "namp": "na", "namps": "na", "nanoamp": "na", "nanoamps": "na",
    "pamp": "pa", "pamps": "pa", "picoamp": "pa", "picoamps": "pa",
    "famp": "fa", "famps": "fa", "femtoamp": "fa", "femtoamps": "fa",
    "volt": "v", "volts": "v",
    "kvolt": "kv", "kvolts": "kv",
    "mvolt": "mv", "mvolts": "mv", "millivolt": "mv", "millivolts": "mv",
    "uvolt": "uv", "uvolts": "uv", "microvolt": "uv", "microvolts": "uv",
    "nvolt": "nv", "nvolts": "nv", "nanovolt": "nv", "nanovolts": "nv",
    "pvolt": "pv", "pvolts": "pv",
    "hertz": "hz", "khertz": "khz", "mhertz": "mhz", "ghertz": "ghz", "thertz": "thz",
    "watt": "w", "watts": "w", "mwatt": "mw", "mwatts": "mw", "uwatt": "uw", "uwatts": "uw",
    "nwatt": "nw", "nwatts": "nw", "pwatt": "pw", "pwatts": "pw",
    "farad": "f", "farads": "f", "pfarad": "pf", "ffarad": "ff", "nfarad": "nf", "ufarad": "uf",
    "dbv": "dbv", "db": "db", "degc": "temp_c", "c_deg": "temp_c", "kelvin": "temp_k",
}


def _resolve_trace_unit_scale(unit_str, expected_dim=None):
    """Resolve a PSF TRACE/TYPE unit property into `(si_scale, error_reason_or_None)`.

    Fail-closed on unknown unit strings or unit dimension mismatches so non-SI
    PSF traces (`mA`, `mV`, `MHz`, `ns`, ...) are always scaled cleanly to SI or rejected.
    """
    raw_u = str(unit_str or "").strip().replace(" ", "")
    if not raw_u:
        return 1.0, None
    if raw_u in UNIT_SCALE_CASE_SENSITIVE:
        u_scale = UNIT_SCALE_CASE_SENSITIVE[raw_u]
        u_dim = UNIT_DIM_CASE_SENSITIVE.get(raw_u)
        # Allow time unit `"s"`/`"sec"` vs `"S"` ONLY strictly by case (`S`=Siemens, `s`=seconds)
    else:
        u_key = raw_u.lower()
        u_key = _TRACE_UNIT_ALIASES_LOWER.get(u_key, u_key)
        if u_key not in UNIT_SCALE_TO_SI:
            return None, "unknown_trace_unit:%s" % raw_u
        u_scale = UNIT_SCALE_TO_SI[u_key]
        u_dim = UNIT_DIM_LOWER.get(u_key)
    if expected_dim is not None:
        if expected_dim == "voltage_or_ratio":
            if u_dim not in ("voltage", "ratio"):
                return None, "trace_unit_dimension_mismatch:%s" % raw_u
        elif u_dim != expected_dim:
            return None, "trace_unit_dimension_mismatch:%s" % raw_u
    return float(u_scale), None


def _get_parsed_signal_unit(parsed, sig_name):
    """Extract declared PSF `units` property for a trace, sweep axis, or type."""
    if not isinstance(parsed, dict) or not sig_name:
        return ""
    f_units = parsed.get("field_units") or {}
    if sig_name in f_units and f_units[sig_name]:
        return str(f_units[sig_name])
    types = parsed.get("types") or {}
    for tr in parsed.get("traces") or []:
        if tr.get("name") == sig_name:
            u = (tr.get("props") or {}).get("units")
            if u:
                return str(u)
            t_meta = types.get(tr.get("type"), {})
            u2 = (t_meta.get("props") or {}).get("units")
            if u2:
                return str(u2)
            break
    for sw in parsed.get("sweeps") or []:
        if sw.get("name") == sig_name:
            u = (sw.get("props") or {}).get("units")
            if u:
                return str(u)
            t_meta = types.get(sw.get("type"), {})
            u2 = (t_meta.get("props") or {}).get("units")
            if u2:
                return str(u2)
            break
    tr_types = parsed.get("trace_types") or {}
    if sig_name in tr_types:
        t_meta = types.get(tr_types[sig_name], {})
        u3 = (t_meta.get("props") or {}).get("units")
        if u3:
            return str(u3)
    return ""


def _scale_numeric_sequence(seq, scale, as_complex=False):
    if abs(scale - 1.0) <= 1e-15:
        if as_complex:
            return [complex(v) for v in seq]
        return [float(x.real) if isinstance(x, complex) else float(x) for x in seq]
    if as_complex:
        return [complex(v) * scale for v in seq]
    return [(float(x.real) if isinstance(x, complex) else float(x)) * scale for x in seq]


class _SilentOptionParser(OptionParser):
    def error(self, msg):
        raise ValueError(msg)


def _round_clean(val, digits=9):
    if val is None or isinstance(val, bool) or isinstance(val, _INT_TYPES):
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
            if isinstance(val, _NUM_TYPES) and not isinstance(val, bool):
                return val
    if canonical == "gds" and "rout" in fields_lc:
        rv = fields_lc["rout"]
        if isinstance(rv, _NUM_TYPES) and not isinstance(rv, bool) and abs(rv) > 1e-18:
            return 1.0 / float(rv)
    return None


def _is_pmos_device(inst_name, type_name, fields_lc, vgs, vth, vds=None, ids=None):
    joined = "%s %s %s" % (
        inst_name.lower(),
        (type_name or "").lower(),
        str(fields_lc.get("model", "")).lower(),
    )
    if any([tok in joined for tok in ("pmos", "pch", "pfet", "g45p")]):
        return True
    if vth is not None and float(vth) < -1e-4:
        return True
    if vds is not None and float(vds) < -1e-4:
        return True
    if ids is not None and float(ids) < -1e-18:
        return True
    return False


def _extract_mos_devices_from_parsed(parsed):
    """Extract raw MOSFET field dicts + unit maps from either STRUCT instances or flat M1:param values."""
    mos_map = {}

    for inst_name, meta in parsed.get("instances", {}).items():
        fields = meta.get("fields", {})
        if _is_mos_struct(meta.get("type", ""), fields):
            u_map = {}
            inst_fu = meta.get("field_units") or {}
            prefix = inst_name + ":"
            for fk in fields.keys():
                u_val = inst_fu.get(prefix + fk) or _get_parsed_signal_unit(parsed, prefix + fk)
                if u_val:
                    u_map[fk.lower()] = u_val
            mos_map[inst_name] = {
                "type": meta.get("type", "mos"),
                "fields_lc": dict([(k.lower(), v) for k, v in fields.items()]),
                "units_lc": u_map,
            }

    grouped_flat = {}
    grouped_units = {}
    for sig_name, arr in parsed.get("values", {}).items():
        if not arr or isinstance(arr[0], complex):
            continue
        sep = ":" if ":" in sig_name else ("." if "." in sig_name else None)
        if not sep:
            continue
        inst, param = sig_name.rsplit(sep, 1)
        if not inst or not param:
            continue
        p_low = param.lower()
        grouped_flat.setdefault(inst, {})[p_low] = arr[0]
        u_val = _get_parsed_signal_unit(parsed, sig_name)
        if u_val:
            grouped_units.setdefault(inst, {})[p_low] = u_val

    for inst_name, flc in grouped_flat.items():
        if inst_name in mos_map:
            continue
        if _is_mos_struct("mos", flc):
            mos_map[inst_name] = {
                "type": "mos_flat",
                "fields_lc": flc,
                "units_lc": grouped_units.get(inst_name, {}),
            }

    return mos_map


def _pick_scaled_mos_field(flc, units_lc, canonical, expected_dim, inst_name, unit_errs):
    cands = MOS_FIELD_ALIASES.get(canonical, (canonical,))
    for cand in cands:
        if cand in flc:
            val = flc[cand]
            if isinstance(val, _NUM_TYPES) and not isinstance(val, bool):
                u_str = (units_lc or {}).get(cand, "")
                scale, err = _resolve_trace_unit_scale(u_str, expected_dim=expected_dim)
                if err:
                    unit_errs.append("%s.%s: %s" % (inst_name, cand, err))
                    return None
                return float(val) * scale
    if canonical == "gds" and "rout" in flc:
        rv = flc["rout"]
        if isinstance(rv, _NUM_TYPES) and not isinstance(rv, bool) and abs(rv) > 1e-18:
            u_str = (units_lc or {}).get("rout", "")
            scale, err = _resolve_trace_unit_scale(u_str, expected_dim="resistance")
            if err:
                unit_errs.append("%s.rout: %s" % (inst_name, err))
                return None
            r_si = float(rv) * scale
            if abs(r_si) > 1e-18:
                return 1.0 / r_si
    return None


def audit_mos_op_parsed(parsed, vds_margin=0.05, expect_triode=None):
    """Strict fail-closed MOS operating-point auditor."""
    expect_set = set(expect_triode or [])
    expect_lc = set([x.lower() for x in expect_set])
    mos_raw = _extract_mos_devices_from_parsed(parsed)

    devices = {}
    flags = []
    unit_errors = []
    buckets = {
        "saturation": [],
        "cutoff": [],
        "unintended_triode": [],
        "expected_triode": [],
        "subthreshold": [],
        "breakdown": [],
        "unknown_region": [],
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
        ulc = entry.get("units_lc") or {}
        dev_type = entry["type"]
        dev_unit_errs = []

        ids = _pick_scaled_mos_field(flc, ulc, "ids", "current", inst_name, dev_unit_errs)
        vgs = _pick_scaled_mos_field(flc, ulc, "vgs", "voltage", inst_name, dev_unit_errs)
        vds = _pick_scaled_mos_field(flc, ulc, "vds", "voltage", inst_name, dev_unit_errs)
        vth = _pick_scaled_mos_field(flc, ulc, "vth", "voltage", inst_name, dev_unit_errs)
        vdsat = _pick_scaled_mos_field(flc, ulc, "vdsat", "voltage", inst_name, dev_unit_errs)
        gm = _pick_scaled_mos_field(flc, ulc, "gm", "conductance", inst_name, dev_unit_errs)
        gds = _pick_scaled_mos_field(flc, ulc, "gds", "conductance", inst_name, dev_unit_errs)
        gmb = _pick_scaled_mos_field(flc, ulc, "gmb", "conductance", inst_name, dev_unit_errs)
        cgg = _pick_scaled_mos_field(flc, ulc, "cgg", "capacitance", inst_name, dev_unit_errs)
        cgd = _pick_scaled_mos_field(flc, ulc, "cgd", "capacitance", inst_name, dev_unit_errs)
        cgs = _pick_scaled_mos_field(flc, ulc, "cgs", "capacitance", inst_name, dev_unit_errs)
        if dev_unit_errs:
            unit_errors.extend(dev_unit_errs)
            any_missing_op = True
        reg_raw = _pick_field(flc, "region")
        if reg_raw is not None:
            reg_rounded = int(round(float(reg_raw)))
            region = reg_rounded if abs(float(reg_raw) - float(reg_rounded)) <= 1e-6 else float(reg_raw)
        else:
            region = None

        gm_id = (abs(gm) / abs(ids)) if (gm is not None and ids is not None and abs(ids) > 1e-18) else None
        gm_gds = (abs(gm) / abs(gds)) if (gm is not None and gds is not None and abs(gds) > 1e-18) else None

        vov = None
        if vgs is not None and vth is not None:
            if _is_pmos_device(inst_name, dev_type, flc, vgs, vth, vds=vds, ids=ids):
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
        elif effective_region is not None:
            buckets["unknown_region"].append(inst_name)
            dev_flags.append("UNKNOWN_REGION")
            status = "FAIL"
            any_hard_fail = True
            flags.append({
                "device": inst_name,
                "code": "UNKNOWN_REGION",
                "severity": "error",
                "region": effective_region,
                "sat_margin": _round_clean(sat_margin),
                "message": "%s reported unknown/invalid Spectre region code=%s (valid: 0..4)" % (
                    inst_name, repr(effective_region)
                ),
            })

        needs_op_fields = bool(missing_fields) and (effective_region != 0) and not (
            is_expected_triode and region == 1
        )
        if needs_op_fields:
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

        if dev_unit_errs:
            dev_flags.append("UNIT_ERROR")
            any_missing_op = True
            if status != "FAIL":
                status = "NOT_VERIFIED"
            flags.append({
                "device": inst_name,
                "code": "UNIT_ERROR",
                "severity": "error",
                "message": "%s has invalid/mismatched PSF OP trace units: %s" % (
                    inst_name, "; ".join(dev_unit_errs)
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

    summary_out = {
        "saturation": buckets["saturation"],
        "cutoff": buckets["cutoff"],
        "unintended_triode": buckets["unintended_triode"],
        "expected_triode": buckets["expected_triode"],
        "subthreshold": buckets["subthreshold"],
        "breakdown": buckets["breakdown"],
        "unknown_region": buckets["unknown_region"],
        "tight_headroom": buckets["tight_headroom"],
        "missing_op_fields": buckets["missing_op_fields"],
        "min_sat_margin_v": _round_clean(min_sat_margin),
        "worst_headroom_device": worst_headroom_dev,
    }
    if unit_errors:
        summary_out["unit_errors"] = unit_errors

    return {
        "audit_pass": audit_pass,
        "status": overall,
        "device_count": len(devices),
        "devices": devices,
        "flags": flags,
        "summary": summary_out,
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


def _is_neg_supply_rail_stem(stem):
    if not stem or stem in NON_SUPPLY_STIM_STEMS:
        return False
    for pref in NEG_SUPPLY_RAIL_PREFIXES:
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
    unit_errors = []

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
        raw_unit = _get_parsed_signal_unit(parsed, k)
        is_curr_term = (
            kl.endswith(":p") or kl.endswith(".p") or kl.endswith(":i") or kl.endswith(".i")
        )
        if is_curr_term:
            leaf0 = re.split(r'[/:.]', kl)[0]
            c_scale, c_err = _resolve_trace_unit_scale(raw_unit, expected_dim="current")
            if c_err is None:
                is_curr_unit = bool(raw_unit.strip())
                if leaf0.startswith("v") or is_curr_unit:
                    stem = _normalize_rail_stem(k)
                    current_probes.append((k, stem, _scale_numeric_sequence(f_arr, c_scale)))
            else:
                stem = _normalize_rail_stem(k)
                if leaf0.startswith("v") or _is_supply_rail_stem(stem) or _is_neg_supply_rail_stem(stem):
                    unit_errors.append("%s: %s" % (k, c_err))
            continue

        # Skip flat device OP fields like `M1:vds` or `R1.i`
        if ":" in k:
            continue
        stem = _normalize_rail_stem(k)
        v_scale, v_err = _resolve_trace_unit_scale(raw_unit, expected_dim="voltage")
        if v_err is not None:
            if _is_supply_rail_stem(stem) or _is_neg_supply_rail_stem(stem):
                unit_errors.append("%s: %s" % (k, v_err))
            continue
        f_arr = _scale_numeric_sequence(f_arr, v_scale)
        if stem in ("0", "gnd", "agnd", "dgnd"):
            continue
        if _is_neg_supply_rail_stem(stem):
            if max([abs(x) for x in f_arr]) <= 1e-3:
                continue
            voltage_nodes.setdefault(stem, []).append((k, f_arr))
            supply_voltage_nodes.setdefault(stem, []).append((k, f_arr))
            continue
        voltage_nodes.setdefault(stem, []).append((k, f_arr))
        if _is_supply_rail_stem(stem):
            supply_voltage_nodes.setdefault(stem, []).append((k, f_arr))

    # Filter current probes: exclude explicit non-supply stimuli (`VIN:p`, `VBIAS:p`)
    # Include negative supply rail probes (e.g. `VSS:p`, `VEE:p`) when their rail voltage is non-zero (|V| > 1e-3).
    supply_named_probes = [
        cp for cp in current_probes
        if _is_supply_rail_stem(cp[1])
        or (_is_neg_supply_rail_stem(cp[1]) and cp[1] in supply_voltage_nodes)
    ]
    generic_src_probes = [
        cp for cp in current_probes
        if (cp[1] not in NON_SUPPLY_STIM_STEMS)
        and (not _is_supply_rail_stem(cp[1]))
        and (not _is_neg_supply_rail_stem(cp[1]))
    ]

    out = {}

    # Estimate MOS power separately (diagnostic only, never `dc_power_w`)
    mos_map = _extract_mos_devices_from_parsed(parsed)
    if mos_map:
        p_mos = 0.0
        mos_ok = False
        mos_u_errs = []
        for m_name, m_entry in mos_map.items():
            flc = m_entry["fields_lc"]
            ulc = m_entry.get("units_lc") or {}
            ids = _pick_scaled_mos_field(flc, ulc, "ids", "current", m_name, mos_u_errs)
            vds = _pick_scaled_mos_field(flc, ulc, "vds", "voltage", m_name, mos_u_errs)
            if ids is not None and vds is not None:
                p_mos += abs(float(ids) * float(vds))
                mos_ok = True
        if mos_ok and not mos_u_errs:
            out["mos_power_estimate_w"] = _round_clean(p_mos)

    if unit_errors:
        out.update({
            "dc_power_w": None,
            "idd_a": None,
            "vdd_v": None,
            "power_method": "trace_unit_error",
            "dc_unit_errors": unit_errors,
        })
        return out

    # When named supply probes are present, do NOT merge generic 0V ammeters (`V_TAIL:p`, `V_MEAS:p`)!
    if supply_named_probes:
        candidate_probes = supply_named_probes
    else:
        candidate_probes = generic_src_probes

    num_supply_v = len(supply_voltage_nodes)
    num_cand_i = len(candidate_probes)

    def _eval_worst_across_sweep(rail_pairs):
        # rail_pairs: list of (rail_stem, v_key, v_arr, c_key, c_arr)
        # Signed power delivered by each voltage source under Spectre passive sign convention: P = -V * I
        # Track max total power AND max total supply current independently across sweep points.
        n_pts = 1
        for _, _, v_arr, _, c_arr in rail_pairs:
            if len(v_arr) > n_pts:
                n_pts = len(v_arr)
            if len(c_arr) > n_pts:
                n_pts = len(c_arr)
        best_p = None
        best_p_idx = 0
        best_i = None
        best_i_idx = 0
        best_rails = None
        for idx in range(n_pts):
            tot_p = 0.0
            tot_i = 0.0
            rails_i = []
            for r_stem, v_key, v_arr, c_key, c_arr in rail_pairs:
                v_signed = v_arr[idx] if idx < len(v_arr) else v_arr[0]
                i_signed = c_arr[idx] if idx < len(c_arr) else c_arr[0]
                pp = -(v_signed * i_signed)
                cc = abs(i_signed)
                tot_p += pp
                tot_i += cc
                rails_i.append({
                    "rail": r_stem,
                    "voltage_node": v_key,
                    "current_probe": c_key,
                    "vdd_v": _round_clean(v_signed),
                    "idd_a": _round_clean(cc),
                    "power_w": _round_clean(pp),
                })
            if best_p is None or tot_p > best_p:
                best_p = tot_p
                best_p_idx = idx
                best_rails = rails_i
            if best_i is None or tot_i > best_i:
                best_i = tot_i
                best_i_idx = idx
        return best_p, best_i, best_p_idx, best_i_idx, n_pts, best_rails

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
            total_p, total_i, max_power_idx, max_idd_idx, n_pts, matched_rails = _eval_worst_across_sweep(matched_pairs)
            rail_volts = dict([(r["rail"], r["vdd_v"]) for r in matched_rails])
            prim_rail = "vdd" if "vdd" in rail_volts else (matched_rails[0]["rail"] if len(matched_rails) == 1 else None)
            out.update({
                "vdd_v": matched_rails[0]["vdd_v"] if len(matched_rails) == 1 else None,
                "idd_a": _round_clean(total_i),
                "dc_power_w": _round_clean(total_p),
                "power_method": "supply_terminal" if len(matched_rails) == 1 else "multi_rail_supply_terminal",
                "supply_rails": matched_rails,
                "rail_voltages": rail_volts,
                "primary_supply_rail": prim_rail,
            })
            if len(matched_rails) == 1:
                out["supply_node"] = matched_rails[0]["voltage_node"]
                out["current_probe"] = matched_rails[0]["current_probe"]
            if n_pts > 1:
                out["dc_sweep_points"] = n_pts
                out["dc_worst_sweep_index"] = max_power_idx
                out["max_power_idx"] = max_power_idx
                out["max_idd_idx"] = max_idd_idx
            return out

        # Single supply voltage node + single generic unnamed source probe (`vdd` + `V0:p`).
        # NEVER pair a distinct named supply rail probe (e.g. `VDD18:p`) with a different supply node (`VDD`)!
        if num_supply_v == 1 and num_cand_i == 1:
            only_v_stem = list(supply_voltage_nodes.keys())[0]
            v_list = supply_voltage_nodes[only_v_stem]
            c_key, c_stem, c_arr = candidate_probes[0]
            if len(v_list) == 1 and (c_stem == only_v_stem or (not _is_supply_rail_stem(c_stem))):
                v_key, v_arr = v_list[0]
                total_p, total_i, max_power_idx, max_idd_idx, n_pts, matched_rails = _eval_worst_across_sweep(
                    [(only_v_stem, v_key, v_arr, c_key, c_arr)]
                )
                out.update({
                    "vdd_v": matched_rails[0]["vdd_v"],
                    "idd_a": _round_clean(total_i),
                    "dc_power_w": _round_clean(total_p),
                    "power_method": "supply_terminal",
                    "supply_node": v_key,
                    "current_probe": c_key,
                    "supply_rails": matched_rails,
                    "rail_voltages": {only_v_stem: matched_rails[0]["vdd_v"]},
                    "primary_supply_rail": only_v_stem,
                })
                if n_pts > 1:
                    out["dc_sweep_points"] = n_pts
                    out["dc_worst_sweep_index"] = max_power_idx
                    out["max_power_idx"] = max_power_idx
                    out["max_idd_idx"] = max_idd_idx
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
    """Compute worst-case static DC power and supply current across ALL DC files and ALL sweep points.

    - Sums `|V_k * I_k|` across all matched supply rails (`VDD:p` * `VDD` + `VDD18:p` * `VDD18`, etc.).
    - Evaluates EVERY sweep point in EVERY DC file and reports worst-case (`max`) power and `max` supply current independently.
    - If ANY DC file has ambiguous / cross-rail supply matching or trace unit errors, fails closed (`dc_power_w = None`, `idd_a = None`).
    - MOS `sum(|Vds * Ids|)` fallback is stored ONLY in `mos_power_estimate_w`, NEVER in `dc_power_w`.
    """
    valid_results = []
    ambiguous_res = None
    unit_err_res = None
    mos_est_max = None

    for parsed in parsed_list:
        res = _extract_dc_power_single(parsed)
        if not res:
            continue
        if res.get("mos_power_estimate_w") is not None:
            if mos_est_max is None or res["mos_power_estimate_w"] > mos_est_max:
                mos_est_max = res["mos_power_estimate_w"]
        if res.get("power_method") == "trace_unit_error":
            unit_err_res = res
        elif res.get("power_method") == "ambiguous_multi_rail":
            ambiguous_res = res
        elif isinstance(res.get("dc_power_w"), _NUM_TYPES) and not isinstance(res.get("dc_power_w"), bool):
            valid_results.append(res)

    if unit_err_res is not None:
        if mos_est_max is not None and "mos_power_estimate_w" not in unit_err_res:
            unit_err_res["mos_power_estimate_w"] = mos_est_max
        return unit_err_res

    if ambiguous_res is not None:
        if mos_est_max is not None and "mos_power_estimate_w" not in ambiguous_res:
            ambiguous_res["mos_power_estimate_w"] = mos_est_max
        return ambiguous_res

    if valid_results:
        best_p_res = valid_results[0]
        for cand in valid_results[1:]:
            if cand["dc_power_w"] > best_p_res["dc_power_w"]:
                best_p_res = cand
        out = dict(best_p_res)
        power_vals = [
            r["dc_power_w"] for r in valid_results
            if isinstance(r.get("dc_power_w"), _NUM_TYPES) and not isinstance(r.get("dc_power_w"), bool)
        ]
        if power_vals:
            out["dc_power_w"] = _round_clean(max(power_vals))
        best_i_res = None
        for cand in valid_results:
            ci = cand.get("idd_a")
            if isinstance(ci, _NUM_TYPES) and not isinstance(ci, bool):
                if best_i_res is None or ci > best_i_res["idd_a"]:
                    best_i_res = cand
        if best_i_res is not None:
            out["idd_a"] = _round_clean(best_i_res["idd_a"])
            if "max_idd_idx" in best_i_res:
                out["max_idd_idx"] = best_i_res["max_idd_idx"]
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
    ac_u_errs = []
    f_u = _get_parsed_signal_unit(parsed, freq_key)
    f_scale, f_err = _resolve_trace_unit_scale(f_u, expected_dim="freq")
    if f_err:
        return {
            "dc_gain_db": None, "bw_3db_hz": None, "ugf_hz": None, "pm_ac_deg": None,
            "ac_unit_errors": ["%s: %s" % (freq_key, f_err)],
        }
    freqs = _scale_numeric_sequence(vals[freq_key], f_scale, as_complex=False)
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
        v_s, v_err = _resolve_trace_unit_scale(_get_parsed_signal_unit(parsed, vout_hint), expected_dim="voltage_or_ratio")
        if v_err:
            ac_u_errs.append("%s: %s" % (vout_hint, v_err))
        else:
            h_vec = _scale_numeric_sequence(vals[vout_hint], v_s, as_complex=True)
        out_label = vout_hint
        out_used_keys = [vout_hint]
    elif not vout_hint:
        vp = _pick_signal_key(vals, ("voutp", "vout_p", "outp", "out_p", "vop"), exclude=(freq_key,))
        vn = _pick_signal_key(vals, ("voutn", "vout_n", "outn", "out_n", "von"), exclude=(freq_key,))
        if vp and vn and len(vals[vp]) == len(freqs) and len(vals[vn]) == len(freqs):
            sp, ep = _resolve_trace_unit_scale(_get_parsed_signal_unit(parsed, vp), expected_dim="voltage_or_ratio")
            sn, en = _resolve_trace_unit_scale(_get_parsed_signal_unit(parsed, vn), expected_dim="voltage_or_ratio")
            if ep:
                ac_u_errs.append("%s: %s" % (vp, ep))
            if en:
                ac_u_errs.append("%s: %s" % (vn, en))
            if (not ep) and (not en):
                vp_sc = _scale_numeric_sequence(vals[vp], sp, as_complex=True)
                vn_sc = _scale_numeric_sequence(vals[vn], sn, as_complex=True)
                h_vec = [vp_sc[i] - vn_sc[i] for i in range(len(freqs))]
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
                sv, ev = _resolve_trace_unit_scale(_get_parsed_signal_unit(parsed, vo), expected_dim="voltage_or_ratio")
                if ev:
                    ac_u_errs.append("%s: %s" % (vo, ev))
                else:
                    h_vec = _scale_numeric_sequence(vals[vo], sv, as_complex=True)
                out_label = vo
                out_used_keys = [vo]

    if ac_u_errs:
        return {
            "ac_output": out_label,
            "dc_gain_db": None, "bw_3db_hz": None, "ugf_hz": None, "pm_ac_deg": None,
            "ac_unit_errors": ac_u_errs,
        }

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
        si, ei = _resolve_trace_unit_scale(_get_parsed_signal_unit(parsed, vin_hint), expected_dim="voltage_or_ratio")
        if ei:
            return {
                "ac_output": out_label, "ac_input": vin_hint,
                "dc_gain_db": None, "bw_3db_hz": None, "ugf_hz": None, "pm_ac_deg": None,
                "ac_unit_errors": ["%s: %s" % (vin_hint, ei)],
            }
        vin_arr = _scale_numeric_sequence(vals[vin_hint], si, as_complex=True)
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
                sp, ep = _resolve_trace_unit_scale(_get_parsed_signal_unit(parsed, kp), expected_dim="voltage_or_ratio")
                sn, en = _resolve_trace_unit_scale(_get_parsed_signal_unit(parsed, kn), expected_dim="voltage_or_ratio")
                if ep or en:
                    return {
                        "ac_output": out_label, "ac_input": "%s-%s" % (kp, kn),
                        "dc_gain_db": None, "bw_3db_hz": None, "ugf_hz": None, "pm_ac_deg": None,
                        "ac_unit_errors": [x for x in (ep and "%s: %s" % (kp, ep), en and "%s: %s" % (kn, en)) if x],
                    }
                vp_sc = _scale_numeric_sequence(vals[kp], sp, as_complex=True)
                vn_sc = _scale_numeric_sequence(vals[kn], sn, as_complex=True)
                vin_arr = [vp_sc[i] - vn_sc[i] for i in range(len(freqs))]
                in_label = "%s-%s" % (kp, kn)
                break
        if vin_arr is None:
            vin_key = _pick_signal_key(vals, ("vin", "vin_ac", "in", "v_in"), exclude=excl_in)
            if vin_key and len(vals[vin_key]) == len(freqs):
                si, ei = _resolve_trace_unit_scale(_get_parsed_signal_unit(parsed, vin_key), expected_dim="voltage_or_ratio")
                if ei:
                    return {
                        "ac_output": out_label, "ac_input": vin_key,
                        "dc_gain_db": None, "bw_3db_hz": None, "ugf_hz": None, "pm_ac_deg": None,
                        "ac_unit_errors": ["%s: %s" % (vin_key, ei)],
                    }
                vin_arr = _scale_numeric_sequence(vals[vin_key], si, as_complex=True)
                in_label = vin_key

    # Ensure ascending frequency order for (freqs, h_vec, vin_arr) BEFORE inspecting vin_arr
    if any([freqs[i] > freqs[i + 1] for i in range(len(freqs) - 1)]):
        order = sorted(range(len(freqs)), key=lambda idx: freqs[idx])
        freqs = [freqs[idx] for idx in order]
        h_vec = [h_vec[idx] for idx in order]
        if vin_arr is not None:
            vin_arr = [vin_arr[idx] for idx in order]

    if vin_arr is not None:
        zero_vin_indices = [i for i in range(len(freqs)) if abs(vin_arr[i]) <= 1e-30]
        if zero_vin_indices or abs(vin_arr[0]) <= 1e-15:
            res_zv = {
                "ac_output": out_label,
                "ac_input": in_label,
                "dc_gain_db": None,
                "bw_3db_hz": None,
                "ugf_hz": None,
                "pm_ac_deg": None,
                "ac_error": "zero_ac_input_stimulus",
            }
            if rejected_bf:
                res_zv["rejected_backfilled_signals"] = rejected_bf
            return res_zv
        h_vec = [h_vec[i] / vin_arr[i] for i in range(len(freqs))]

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


def _compute_nyquist_encirclements(freqs, lg):
    """Compute clockwise encirclements N of (-1+0j) on mirrored closed Nyquist contour L(jw).

    Returns `(nyquist_cw_encirclements, nyquist_contour_closed)`.
    """
    n_pts = len(freqs)
    if n_pts < 2 or len(lg) != n_pts:
        return None, False

    z = [complex(c.real + 1.0, c.imag) for c in lg]
    for zk in z:
        if abs(zk) <= 1e-9:
            return None, False

    span_ok = (n_pts >= 5) and (
        freqs[0] == 0.0 or (freqs[0] > 0.0 and (freqs[-1] / freqs[0]) >= 100.0)
    )

    abs_dc = abs(lg[0])
    dc_near_real = abs(lg[0].imag) <= 0.35 * max(1.0, abs_dc)
    dc_rhp_indented = (
        (lg[0].real > -0.5)
        and (abs_dc > 2.0)
        and (freqs[0] == 0.0 or (freqs[-1] / max(freqs[0], 1e-12)) >= 1000.0)
    )
    dc_bad_left = (lg[0].real <= -0.8) and (abs(lg[0].imag) > 0.25 * abs_dc)
    dc_ok = (dc_near_real or dc_rhp_indented) and (not dc_bad_left) and (abs(z[0]) > 1e-6)

    abs_hf = abs(lg[-1])
    hf_ok = (abs_hf < 0.5) or (
        abs(lg[-1].imag) <= 0.25 * max(1.0, abs_hf) and abs(z[-1]) > 0.5
    )

    sum_pos = 0.0
    coarse_jump = False
    max_step_rad = 2.0 * math.pi / 3.0
    for k in range(n_pts - 1):
        z0 = z[k]
        z1 = z[k + 1]
        cross = z0.real * z1.imag - z0.imag * z1.real
        dot = z0.real * z1.real + z0.imag * z1.imag
        dtheta = math.atan2(cross, dot)
        sum_pos += dtheta
        if (abs(z0) < 0.5 or abs(z1) < 0.5) and abs(dtheta) > max_step_rad:
            coarse_jump = True

    z_last = z[-1]
    z_last_c = complex(z_last.real, -z_last.imag)
    dtheta_hf = math.atan2(
        z_last.real * z_last_c.imag - z_last.imag * z_last_c.real,
        z_last.real * z_last_c.real + z_last.imag * z_last_c.imag,
    )

    z_first = z[0]
    z_first_c = complex(z_first.real, -z_first.imag)
    dtheta_dc = math.atan2(
        z_first_c.real * z_first.imag - z_first_c.imag * z_first.real,
        z_first_c.real * z_first.real + z_first_c.imag * z_first.imag,
    )

    n_float = -(2.0 * sum_pos + dtheta_hf + dtheta_dc) / (2.0 * math.pi)
    n_int = int(round(n_float))
    winding_valid = abs(n_float - n_int) < 1e-4
    contour_closed = bool(span_ok and dc_ok and hf_ok and (not coarse_jump) and winding_valid)
    return (n_int if winding_valid else None), contour_closed


_PZ_OPEN_LOOP_RE = re.compile(r'open[\s_-]?loop', re.IGNORECASE)
_PZ_CLOSED_LOOP_RE = re.compile(r'closed[\s_-]?loop', re.IGNORECASE)
_PZ_ZERO_RE = re.compile(r'(?:^|[./:_])(?:zeros?_?\d*|z_?\d+)(?:$|[./:_])', re.IGNORECASE)
_PZ_POLE_RE = re.compile(r'(?:^|[./:_])(?:poles?_?\d*|p_?\d+|(?:complex|real)_poles?_?\d*)(?:$|[./:_])', re.IGNORECASE)
_PZ_METADATA_KEYS = set([
    "numpoles", "numzeros", "num_poles", "num_zeros",
    "dcgain", "dc_gain", "gain", "freq", "frequency", "q", "qf", "zeta",
])


def _is_finite_num(val):
    if isinstance(val, bool) or not isinstance(val, _NUM_TYPES):
        return False
    f = float(val)
    return not (math.isnan(f) or math.isinf(f))


def _extract_provenance_tags(parsed):
    """Extract normalized provenance tags (circuit/design/netlist/subckt/loop/testbench) from PSF HEADER."""
    tags = {}
    header = parsed.get("header") if isinstance(parsed, dict) else None
    if not isinstance(header, dict):
        return tags
    key_map = {
        "circuit": "circuit", "design": "circuit", "cell": "circuit", "subckt": "circuit",
        "testbench": "testbench", "tb": "testbench",
        "loop": "loop", "loop_name": "loop", "stb_loop": "loop",
        "netlist": "netlist",
    }
    for hk_raw, hv_raw in header.items():
        hk = str(hk_raw).strip().lower()
        cat = key_map.get(hk)
        if not cat:
            continue
        hv = str(hv_raw).strip().strip('"').strip("'").lower()
        if not hv:
            continue
        if cat == "netlist":
            hv = os.path.basename(hv.replace("\\", "/"))
        tags[cat] = hv
    return tags


def _pz_loop_stem(path):
    if not path:
        return ""
    bn = os.path.basename(path).lower()
    st = re.sub(r'(?:\.pz\.psf|\.pz|\.psf|\.info)$', '', bn)
    st = re.sub(r'(?:^|[_.-])(?:open[\s_-]?loop|closed[\s_-]?loop|openloop|closedloop)(?:$|[_.-])', '_', st)
    st = st.strip('_.- ')
    return st


def _extract_pz_metrics(parsed, path=""):
    """Extract open-loop or closed-loop pole-zero metrics from a parsed `.pz` PSF ASCII file.

    Fail-closed invariants (Finding #03):
    - Never defaults untyped `.pz` files to `closed_loop` (`pz_mode = 'unknown'`).
    - Strictly enforces open LHP asymptotic stability (`Re(p) < -eps`), flagging origin (`0+0j`) and jw-axis poles.
    """
    if not isinstance(parsed, dict):
        return {
            "pz_mode": "unknown", "pz_parsed_ok": False,
            "poles_count": 0, "zeros_count": 0, "rhp_poles": 0,
            "jw_axis_poles": 0, "non_lhp_poles": 0,
        }

    pz_mode = None
    header = parsed.get("header") or {}
    if isinstance(header, dict):
        for hk in ("pz_mode", "pz_type", "loop", "loop_mode", "mode", "analysis", "analysis type", "analysis_type", "title", "description"):
            for orig_k, hv in header.items():
                if str(orig_k).strip().lower() == hk:
                    s_hv = str(hv)
                    if _PZ_OPEN_LOOP_RE.search(s_hv):
                        pz_mode = "open_loop"
                        break
                    if _PZ_CLOSED_LOOP_RE.search(s_hv):
                        pz_mode = "closed_loop"
                        break
            if pz_mode is not None:
                break
    if pz_mode is None and path:
        bn_low = os.path.basename(path).lower()
        if _PZ_OPEN_LOOP_RE.search(bn_low):
            pz_mode = "open_loop"
        elif _PZ_CLOSED_LOOP_RE.search(bn_low):
            pz_mode = "closed_loop"
    if pz_mode is None:
        pz_mode = "unknown"

    prov_tags = _extract_provenance_tags(parsed)
    pz_stem = _pz_loop_stem(path)

    poles = []
    zeros_count = 0
    handled_insts = set()

    instances = parsed.get("instances") or {}
    if isinstance(instances, dict):
        for inst_name in sorted(instances.keys()):
            inst_obj = instances[inst_name]
            if not isinstance(inst_obj, dict):
                continue
            inst_low = str(inst_name).lower()
            fields = inst_obj.get("fields") or {}
            flc = dict([(str(fk).strip().lower(), fv) for fk, fv in fields.items()])
            if _PZ_ZERO_RE.search(inst_low):
                zeros_count += 1
                handled_insts.add(inst_name)
                continue
            itype_low = str(inst_obj.get("type", "")).lower()
            if _PZ_POLE_RE.search(inst_low) or ("pole" in itype_low):
                re_v = None
                im_v = None
                for rk in ("real", "re", "sigma", "real_part", "r", "field_0"):
                    if rk in flc and _is_finite_num(flc[rk]):
                        re_v = float(flc[rk])
                        break
                for ik in ("imag", "im", "omega", "imag_part", "i", "field_1"):
                    if ik in flc and _is_finite_num(flc[ik]):
                        im_v = float(flc[ik])
                        break
                if re_v is not None:
                    poles.append(complex(re_v, im_v if im_v is not None else 0.0))
                handled_insts.add(inst_name)

    values = parsed.get("values") or {}
    sweep_name = parsed.get("sweep_name")
    flat_pairs = {}
    handled_flat_keys = set()
    if isinstance(values, dict):
        for k in sorted(values.keys()):
            if sweep_name and k == sweep_name:
                continue
            if any([k.startswith(ih + ":") for ih in handled_insts]):
                continue
            if ":" in k:
                inst_p, fld_p = k.rsplit(":", 1)
                fl = fld_p.strip().lower()
                if fl in ("real", "re", "sigma", "real_part", "r"):
                    flat_pairs.setdefault(inst_p, {})["re"] = (k, values[k])
                elif fl in ("imag", "im", "omega", "imag_part", "i"):
                    flat_pairs.setdefault(inst_p, {})["im"] = (k, values[k])

        for inst_p, pair in sorted(flat_pairs.items()):
            if "re" not in pair:
                continue
            k_re, arr_re = pair["re"]
            arr_im = pair["im"][1] if "im" in pair else None
            inst_low = inst_p.lower()
            if _PZ_ZERO_RE.search(inst_low):
                zeros_count += len(arr_re)
                handled_flat_keys.add(k_re)
                if "im" in pair:
                    handled_flat_keys.add(pair["im"][0])
                continue
            if _PZ_POLE_RE.search(inst_low):
                for idx_p, rv in enumerate(arr_re):
                    if _is_finite_num(rv):
                        iv = 0.0
                        if arr_im is not None and idx_p < len(arr_im) and _is_finite_num(arr_im[idx_p]):
                            iv = float(arr_im[idx_p])
                        poles.append(complex(float(rv), iv))
                handled_flat_keys.add(k_re)
                if "im" in pair:
                    handled_flat_keys.add(pair["im"][0])

        for k in sorted(values.keys()):
            if sweep_name and k == sweep_name:
                continue
            if k in handled_flat_keys or any([k.startswith(ih + ":") for ih in handled_insts]):
                continue
            kl = k.lower()
            if kl in _PZ_METADATA_KEYS:
                continue
            arr = values[k]
            if _PZ_ZERO_RE.search(kl):
                for elem in arr:
                    if isinstance(elem, complex):
                        if not (math.isnan(elem.real) or math.isinf(elem.real) or math.isnan(elem.imag) or math.isinf(elem.imag)):
                            zeros_count += 1
                    elif _is_finite_num(elem):
                        zeros_count += 1
                continue
            if _PZ_POLE_RE.search(kl):
                for elem in arr:
                    if isinstance(elem, complex):
                        if not (math.isnan(elem.real) or math.isinf(elem.real) or math.isnan(elem.imag) or math.isinf(elem.imag)):
                            poles.append(elem)
                    elif _is_finite_num(elem):
                        poles.append(complex(float(elem), 0.0))

    rhp_poles = 0
    jw_axis_poles = 0
    for p in poles:
        eps_p = 1e-12 * max(1.0, abs(p.real), abs(p.imag))
        if p.real > eps_p:
            rhp_poles += 1
        elif abs(p.real) <= eps_p:
            jw_axis_poles += 1
    non_lhp_poles = rhp_poles + jw_axis_poles
    pz_ok = (len(poles) >= 1)
    out_pz = {
        "pz_mode": pz_mode,
        "pz_parsed_ok": pz_ok,
        "poles_count": len(poles),
        "zeros_count": zeros_count,
        "rhp_poles": rhp_poles,
        "jw_axis_poles": jw_axis_poles,
        "non_lhp_poles": non_lhp_poles,
        "provenance_tags": prov_tags,
        "pz_stem": pz_stem,
    }
    if poles:
        out_pz["max_pole_real"] = _round_clean(max([p.real for p in poles]))
    if pz_mode == "closed_loop":
        out_pz["closed_loop_poles"] = len(poles)
        out_pz["closed_loop_rhp_poles"] = rhp_poles
        out_pz["closed_loop_jw_axis_poles"] = jw_axis_poles
        out_pz["closed_loop_non_lhp_poles"] = non_lhp_poles
    elif pz_mode == "open_loop":
        out_pz["open_loop_poles"] = len(poles)
        out_pz["open_loop_rhp_poles"] = rhp_poles
        out_pz["open_loop_jw_axis_poles"] = jw_axis_poles
        out_pz["open_loop_non_lhp_poles"] = non_lhp_poles
    return out_pz


def _extract_stb_metrics(stb_parsed, margin_parsed=None):
    vals, rejected_bf = _usable_waveform_values(stb_parsed) if stb_parsed else ({}, [])
    freq_key = (stb_parsed.get("sweep_name") if stb_parsed else None) or _pick_signal_key(
        vals, ("freq", "frequency", "f")
    )
    lg_key = _pick_signal_key(vals, ("loopGain", "loopgain", "T", "returnRatio"), exclude=(freq_key or "",))

    out = {}
    if rejected_bf:
        out["rejected_backfilled_signals"] = rejected_bf
    if stb_parsed:
        out["provenance_tags"] = _extract_provenance_tags(stb_parsed)
    elif margin_parsed:
        out["provenance_tags"] = _extract_provenance_tags(margin_parsed)

    rhp_pole_suspected = False
    dc_pos_fb = False
    stb_u_errs = []

    if freq_key and lg_key and len(vals[freq_key]) >= 2 and len(vals[lg_key]) == len(vals[freq_key]):
        f_scale, f_err = _resolve_trace_unit_scale(_get_parsed_signal_unit(stb_parsed, freq_key), expected_dim="freq")
        if f_err:
            stb_u_errs.append("%s: %s" % (freq_key, f_err))
        else:
            freqs = _scale_numeric_sequence(vals[freq_key], f_scale, as_complex=False)
            lg = [complex(v) for v in vals[lg_key]]
            if any([freqs[i] > freqs[i + 1] for i in range(len(freqs) - 1)]):
                order = sorted(range(len(freqs)), key=lambda idx: freqs[idx])
                freqs = [freqs[idx] for idx in order]
                lg = [lg[idx] for idx in order]

            mags = [abs(c) for c in lg]
            mag_db = [20.0 * math.log10(m) if m > 1e-300 else -600.0 for m in mags]
            raw_phase = [math.degrees(math.atan2(c.imag, c.real)) for c in lg]
            unwrapped = _unwrap_phase_deg(raw_phase)
            nyq_n, nyq_closed = _compute_nyquist_encirclements(freqs, lg)

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

            # Bode gain-phase slope consistency check across active frequency range:
            # An RHP open-loop pole adds -20 dB/dec magnitude rolloff with +90 deg phase lead (+180 deg anomaly
            # relative to minimum-phase Bode relation phi ~ 4.5 deg * slope_dB_per_dec). Over any sustained
            # monotonic rolloff window (>= 0.45 dec) with steep slope (<= -32 dB/dec) not on a decelerating
            # resonant skirt, excess phase lead >= +100 deg signals P > 0 RHP open-loop pole(s).
            if (not rhp_pole_suspected) and (not dc_pos_fb) and mag_db[0] > 0.0 and len(freqs) >= 3:
                n_f = len(freqs)
                for wi in range(n_f - 1):
                    if freqs[wi] <= 0.0:
                        continue
                    for wj in range(wi + 1, n_f):
                        if freqs[wj] <= freqs[wi]:
                            continue
                        dec_w = math.log10(freqs[wj] / freqs[wi])
                        if dec_w < 0.45:
                            continue
                        if dec_w > 1.5 and wj > wi + 1:
                            break
                        mono_down = True
                        for wk in range(wi, wj):
                            if mag_db[wk + 1] > mag_db[wk] + 0.5:
                                mono_down = False
                                break
                        if not mono_down:
                            continue
                        s_win = (mag_db[wj] - mag_db[wi]) / dec_w
                        if s_win > -32.0:
                            continue
                        dec_loc = math.log10(freqs[wj] / freqs[wj - 1]) if freqs[wj - 1] > 0.0 else 0.0
                        s_loc = ((mag_db[wj] - mag_db[wj - 1]) / dec_loc) if dec_loc > 1e-9 else s_win
                        s_cons = max(s_win, s_loc)
                        if s_cons > -32.0 or s_loc > s_win + 20.0:
                            continue
                        phi_rel_j = unwrapped[wj] - unwrapped[0]
                        exp_min_phase = 4.5 * s_cons
                        if (phi_rel_j - exp_min_phase) >= 100.0:
                            rhp_pole_suspected = True
                            break
                    if rhp_pole_suspected:
                        break

            falling_crossings = [c for c in ugf_crossings if c["direction"] == "falling"]
            primary_ugf = None
            worst_pm = None
            if falling_crossings:
                primary_ugf = falling_crossings[0]["freq_hz"]
            elif ugf_crossings:
                primary_ugf = ugf_crossings[0]["freq_hz"]
            if ugf_crossings:
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
                # Fail closed so closed-loop instability (e.g. L(s)=3/(s-1)^2 or 10/[(1-s/20)(1+s/10)^2]) can NEVER pass!
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
                    "nyquist_cw_encirclements": nyq_n,
                    "nyquist_contour_closed": nyq_closed,
                    "stb_notes": (
                        "Bode gain-phase anomaly indicates suspected RHP open-loop pole(s) (P > 0); "
                        "Bode-only phase/gain margins cannot certify closed-loop stability when P > 0 "
                        "and full Nyquist encirclement analysis (N = Z - P) is required."
                    ),
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
                    "nyquist_cw_encirclements": nyq_n,
                    "nyquist_contour_closed": nyq_closed,
                })
            if len(ugf_crossings) > 1:
                out["all_ugf_crossings"] = ugf_crossings
            if len(gm_crossings) > 1:
                out["all_gm_crossings"] = gm_crossings

    if margin_parsed and (not rhp_pole_suspected) and (not dc_pos_fb):
        mvals, _ = _usable_waveform_values(margin_parsed)
        if out.get("phase_margin_deg") is None and "phaseMargin" in mvals and mvals["phaseMargin"]:
            s_pm, e_pm = _resolve_trace_unit_scale(_get_parsed_signal_unit(margin_parsed, "phaseMargin"), expected_dim="angle")
            if e_pm:
                stb_u_errs.append("phaseMargin: %s" % e_pm)
            else:
                out["phase_margin_deg"] = _round_clean(float(mvals["phaseMargin"][0].real) * s_pm)
        if out.get("stb_ugf_hz") is None and "phaseMarginFreq" in mvals and mvals["phaseMarginFreq"]:
            s_pf, e_pf = _resolve_trace_unit_scale(_get_parsed_signal_unit(margin_parsed, "phaseMarginFreq"), expected_dim="freq")
            if e_pf:
                stb_u_errs.append("phaseMarginFreq: %s" % e_pf)
            else:
                out["stb_ugf_hz"] = _round_clean(float(mvals["phaseMarginFreq"][0].real) * s_pf)
        if out.get("gain_margin_db") is None and "gainMargin" in mvals and mvals["gainMargin"]:
            s_gm, e_gm = _resolve_trace_unit_scale(_get_parsed_signal_unit(margin_parsed, "gainMargin"), expected_dim="db")
            if e_gm:
                stb_u_errs.append("gainMargin: %s" % e_gm)
            else:
                out["gain_margin_db"] = _round_clean(float(mvals["gainMargin"][0].real) * s_gm)
        if out.get("gm_freq_hz") is None and "gainMarginFreq" in mvals and mvals["gainMarginFreq"]:
            s_gf, e_gf = _resolve_trace_unit_scale(_get_parsed_signal_unit(margin_parsed, "gainMarginFreq"), expected_dim="freq")
            if e_gf:
                stb_u_errs.append("gainMarginFreq: %s" % e_gf)
            else:
                out["gm_freq_hz"] = _round_clean(float(mvals["gainMarginFreq"][0].real) * s_gf)

    if stb_u_errs:
        out["stb_unit_errors"] = stb_u_errs
        out["phase_margin_deg"] = None
        out["gain_margin_db"] = None
        out["stb_ugf_hz"] = None

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

    # Build steady-state tail plateau window strictly by time span (last 15% of post-trigger duration,
    # requiring >= 2 samples, with no sample-count cap that breaks on adaptive Spectre timesteps).
    t_base = t_trig if (t_trig is not None and t_win[0] <= t_trig < t_win[-1]) else t_win[0]
    post_dur = t_win[-1] - t_base
    t_tail_cut = t_base + 0.85 * post_dur
    time_tail_indices = [idx for idx in range(len(t_win)) if t_win[idx] >= t_tail_cut]
    if len(time_tail_indices) >= 2:
        t_tail = [t_win[idx] for idx in time_tail_indices]
        v_tail = [v_win[idx] for idx in time_tail_indices]
    else:
        t_tail = t_win[-2:]
        v_tail = v_win[-2:]

    tail_dt = t_tail[-1] - t_tail[0]
    if tail_dt > 1e-18 and len(t_tail) >= 2:
        area_v = 0.0
        for tk in range(len(t_tail) - 1):
            dt_k = t_tail[tk + 1] - t_tail[tk]
            if dt_k > 0.0:
                area_v += 0.5 * (v_tail[tk] + v_tail[tk + 1]) * dt_k
        v_final = area_v / tail_dt
    else:
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
        reached_90 = (v_ext >= lvl_90 - 1e-12 * max(1.0, abs_eff_step))
    else:
        v_ext = min(v_win)
        overshoot_pct = max(0.0, (v_ref - v_ext) / abs_eff_step * 100.0)
        reached_90 = (v_ext <= lvl_90 + 1e-12 * max(1.0, abs_eff_step))

    tol = settling_tol_ratio * abs_eff_step
    tail_span = max(v_tail) - min(v_tail)
    avg_win_slope = abs_step / max(1e-18, post_dur if post_dur > 1e-18 else win_dur)
    tail_slope = (abs(v_tail[-1] - v_tail[0]) / tail_dt) if tail_dt > 1e-18 else float("inf")

    # Anti-ramp plateau guard: tail must span >= 5% of post-trigger duration AND be much flatter than the transition ramp
    ref_dur = post_dur if post_dur > 1e-18 else win_dur
    tail_has_plateau = (
        len(v_win) >= 4
        and len(v_tail) >= 2
        and tail_dt >= 0.05 * ref_dur
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
        "reached_90": reached_90,
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


def _detect_trigger_edges(times, trig_vals):
    """Detect all hysteresis-filtered input trigger edges `(t_cross, idx_cross, is_rising)`."""
    if not trig_vals or len(trig_vals) < 3:
        return []
    tr_min = min(trig_vals)
    tr_max = max(trig_vals)
    tr_swing = tr_max - tr_min
    if tr_swing <= 1e-9:
        return []
    tr_mid = 0.5 * (tr_min + tr_max)
    tr_lo = tr_min + 0.25 * tr_swing
    tr_hi = tr_min + 0.75 * tr_swing
    edges = []
    armed = 1 if trig_vals[0] >= tr_mid else -1
    pending = None
    last_i = len(trig_vals) - 2
    for i in range(len(trig_vals) - 1):
        v0, v1 = trig_vals[i], trig_vals[i + 1]
        if armed == -1:
            if (v0 <= tr_mid < v1) or (v0 < tr_mid <= v1):
                frac = (tr_mid - v0) / (v1 - v0) if abs(v1 - v0) > 1e-30 else 0.0
                pending = (times[i] + frac * (times[i + 1] - times[i]), i, True)
            if pending is not None and (v1 >= tr_hi or i == last_i):
                edges.append(pending)
                pending = None
                armed = 1
        else:
            if (v0 >= tr_mid > v1) or (v0 > tr_mid >= v1):
                frac = (tr_mid - v0) / (v1 - v0) if abs(v1 - v0) > 1e-30 else 0.0
                pending = (times[i] + frac * (times[i + 1] - times[i]), i, False)
            if pending is not None and (v1 <= tr_lo or i == last_i):
                edges.append(pending)
                pending = None
                armed = -1
    return edges


def _extract_tran_metrics(parsed, vout_hint=None, settling_tol_ratio=0.01, target_v=None):
    vals, rejected_bf = _usable_waveform_values(parsed)
    t_key = parsed.get("sweep_name") or _pick_signal_key(vals, ("time", "t"))
    if not t_key or t_key not in vals:
        return {"rejected_backfilled_signals": rejected_bf} if rejected_bf else {}
    t_scale, t_err = _resolve_trace_unit_scale(_get_parsed_signal_unit(parsed, t_key), expected_dim="time")
    if t_err:
        return {
            "slew_rate_pos": None, "slew_rate_neg": None,
            "overshoot_pct": None, "settling_time_s": None, "ripple_pp": None,
            "tran_unit_errors": ["%s: %s" % (t_key, t_err)],
        }
    times = _scale_numeric_sequence(vals[t_key], t_scale, as_complex=False)
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

    v_scale, v_err = _resolve_trace_unit_scale(_get_parsed_signal_unit(parsed, vo_key), expected_dim="voltage")
    if v_err:
        return {
            "tran_output": vo_key,
            "slew_rate_pos": None, "slew_rate_neg": None,
            "overshoot_pct": None, "settling_time_s": None, "ripple_pp": None,
            "tran_unit_errors": ["%s: %s" % (vo_key, v_err)],
        }
    vout = _scale_numeric_sequence(vals[vo_key], v_scale, as_complex=False)

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
        trig_dim = "current" if trig_key.lower() in ("iload", "i_load") else "voltage"
        tr_scale, tr_err = _resolve_trace_unit_scale(_get_parsed_signal_unit(parsed, trig_key), expected_dim=trig_dim)
        if tr_err is None:
            trig_vals = _scale_numeric_sequence(vals[trig_key], tr_scale, as_complex=False)

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
    clipped_pos = False
    clipped_neg = False

    if step_detected:
        trig_edges = _detect_trigger_edges(times, trig_vals) if trig_vals is not None else []
        returns_near_init = (abs(vout[-1] - vout[0]) < 0.35 * swing)
        if len(trig_edges) >= 2:
            # Multi-pulse / multi-edge train: segment strictly by detected input trigger edges
            # so each pulse window is evaluated independently without cross-cycle contamination.
            segs = []
            for e_i, (t_e, idx_e, _) in enumerate(trig_edges):
                w_start = 0 if e_i == 0 else idx_e
                w_end = trig_edges[e_i + 1][1] if (e_i + 1 < len(trig_edges)) else (len(vout) - 1)
                if w_end - w_start < 3:
                    continue
                seg_tv = None
                if target_v is not None:
                    seg_tv = target_v if (e_i % 2 == 0) else vout[0]
                seg = _analyze_step_segment(
                    times, vout, w_start, w_end,
                    settling_tol_ratio=settling_tol_ratio,
                    t_trig=t_e,
                    target_v=seg_tv,
                )
                if seg:
                    segs.append(seg)
            sr_pos_vals = []
            sr_neg_vals = []
            for seg in segs:
                if seg.get("rising"):
                    if seg.get("slew_rate") is not None:
                        sr_pos_vals.append(seg["slew_rate"])
                    elif target_v is not None and (not seg.get("reached_90", True)):
                        clipped_pos = True
                else:
                    if seg.get("slew_rate") is not None:
                        sr_neg_vals.append(seg["slew_rate"])
                    elif target_v is not None and (not seg.get("reached_90", True)):
                        clipped_neg = True
            if sr_pos_vals and (not clipped_pos):
                sr_pos = min(sr_pos_vals)
            if sr_neg_vals and (not clipped_neg):
                sr_neg = min(sr_neg_vals)
            overshoot_candidates = [s["overshoot_pct"] for s in segs if s.get("overshoot_pct") is not None]
            if overshoot_candidates:
                overshoot_pct = max(overshoot_candidates)
            if segs and segs[0].get("v_final") is not None:
                tran_final_v = segs[0]["v_final"]
            if segs and segs[0].get("static_error_v") is not None:
                static_error_v = segs[0]["static_error_v"]
            if segs and all([s.get("settling_time_s") is not None for s in segs]):
                settling_time_s = max([s["settling_time_s"] for s in segs])
            else:
                settling_time_s = None
        elif returns_near_init:
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

            t_trig1 = trig_edges[0][0] if len(trig_edges) >= 1 else None
            t_trig2 = None
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
                if seg.get("rising"):
                    if seg.get("slew_rate") is not None:
                        sr_pos = seg["slew_rate"]
                    elif target_v is not None and (not seg.get("reached_90", True)):
                        clipped_pos = True
                else:
                    if seg.get("slew_rate") is not None:
                        sr_neg = seg["slew_rate"]
                    elif target_v is not None and (not seg.get("reached_90", True)):
                        clipped_neg = True
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
            t_trig = trig_edges[0][0] if trig_edges else None
            seg = _analyze_step_segment(
                times, vout, 0, len(vout) - 1,
                settling_tol_ratio=settling_tol_ratio,
                t_trig=t_trig,
                target_v=target_v,
            )
            if seg:
                if seg.get("rising"):
                    sr_pos = seg.get("slew_rate")
                    if sr_pos is None and target_v is not None and (not seg.get("reached_90", True)):
                        clipped_pos = True
                else:
                    sr_neg = seg.get("slew_rate")
                    if sr_neg is None and target_v is not None and (not seg.get("reached_90", True)):
                        clipped_neg = True
                overshoot_pct = seg.get("overshoot_pct")
                settling_time_s = seg.get("settling_time_s")
                tran_final_v = seg.get("v_final")
                static_error_v = seg.get("static_error_v")

    # Disable max_dvdt fallback when waveform never reaches 90% of target_v (clipped step)
    if target_v is not None:
        tgt_delta = float(target_v) - vout[0]
        if tgt_delta > 1e-9 and v_max < vout[0] + 0.90 * tgt_delta - 1e-12 * max(1.0, abs(tgt_delta)):
            clipped_pos = True
        elif tgt_delta < -1e-9 and v_min > vout[0] + 0.90 * tgt_delta + 1e-12 * max(1.0, abs(tgt_delta)):
            clipped_neg = True

    if sr_pos is None and (not clipped_pos) and max_dvdt_pos is not None and step_detected and vout[-1] >= vout[0]:
        sr_pos = max_dvdt_pos
    if sr_neg is None and (not clipped_neg) and max_dvdt_neg is not None and step_detected and vout[-1] <= vout[0]:
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


_NOISE_SI_PREFIX = {
    "": 1.0,
    "f": 1e-15,
    "p": 1e-12,
    "n": 1e-9,
    "u": 1e-6,
    "m": 1e-3,
    "k": 1e3,
    "K": 1e3,
    "M": 1e6,
    "G": 1e9,
}


def _classify_noise_unit(unit_raw, sig_name):
    """Return `(domain, is_psd, si_scale)` where domain in `('voltage', 'current', 'unknown')`.

    Parses case-sensitive SI prefixes (`f`, `p`, `n`, `u`, `m`, `k`, `M`, `G`) for both ASD
    (`V/sqrt(Hz)`, `nV/sqrt(Hz)`, `uV/rtHz`, `pA/sqrt(Hz)`, ...) and PSD (`V^2/Hz`, `nV^2/Hz`,
    `pA^2/Hz`, ...). Caller scales ASD by `si_scale` and PSD by `si_scale**2`.
    """
    u_raw = str(unit_raw or "").strip().replace(" ", "")
    if not u_raw:
        sl = str(sig_name or "").strip().lower()
        if sl in ("vout_noise", "vnoise") or sl.startswith("v"):
            return "voltage", False, 1.0
        if sl in ("inoise_a", "iout_noise") or sl.startswith("i_"):
            return "current", False, 1.0
        if sl in ("onoise", "inoise", "out"):
            return "voltage", False, 1.0
        return "unknown", False, 1.0

    # Explicit PSD with optional SI prefix: e.g. `V^2/Hz`, `nV^2/Hz`, `(uV)^2/Hz`, `pA**2/Hz`, `V2/Hz`, `V*V/Hz`
    m_psd = re.match(
        r'^\(?([fpnumkKMG]?)([VvAa])\)?(?:\^2|\*\*2|2|\*(?:[fpnumkKMG]?[VvAa]))(?:/(?:[Hh][Zz])?)?$',
        u_raw,
    )
    if m_psd:
        pref = m_psd.group(1)
        base = m_psd.group(2).lower()
        dom = "voltage" if base == "v" else "current"
        return dom, True, _NOISE_SI_PREFIX.get(pref, 1.0)

    # Explicit ASD with optional SI prefix: e.g. `V/sqrt(Hz)`, `nV/sqrt(Hz)`, `uV/rtHz`, `pA/Hz^0.5`
    m_asd = re.match(
        r'^([fpnumkKMG]?)([VvAa])/(?:sqrt\([Hh][Zz]\)|rt[Hh][Zz]|[Hh][Zz]\^0\.5|[Hh][Zz]\*\*0\.5)$',
        u_raw,
    )
    if m_asd:
        pref = m_asd.group(1)
        base = m_asd.group(2).lower()
        dom = "voltage" if base == "v" else "current"
        return dom, False, _NOISE_SI_PREFIX.get(pref, 1.0)

    # Bare voltage/current unit with optional SI prefix (e.g. `nV`, `uV`, `V`, `pA`, `A`)
    m_bare = re.match(r'^([fpnumkKMG]?)([VvAa])$', u_raw)
    if m_bare:
        pref = m_bare.group(1)
        base = m_bare.group(2).lower()
        dom = "voltage" if base == "v" else "current"
        return dom, False, _NOISE_SI_PREFIX.get(pref, 1.0)

    # Fallback textual forms like `volt^2/Hz`, `amp/sqrt(Hz)`, `i^2/Hz`
    u_low = u_raw.lower()
    is_psd = ("^2" in u_low or "**2" in u_low or "v2/" in u_low or "a2/" in u_low or "i2/" in u_low or u_low.endswith("v2") or u_low.endswith("a2"))
    if "amp" in u_low or u_low.startswith("i^") or u_low.startswith("i*") or u_low.startswith("i2"):
        return "current", is_psd, 1.0
    if "volt" in u_low:
        return "voltage", is_psd, 1.0
    return "unknown", is_psd, 1.0


def _integrate_psd_band(freqs, psd, f_min=None, f_max=None):
    """Trapezoidally integrate sorted `(freqs, psd)` strictly over `[f_min, f_max]`.

    Returns `(rms_float, None)` on success, or `(None, reason)` if the band is invalid
    (`lo >= hi`, non-finite) or not covered by the frequency sweep.
    """
    if len(freqs) < 2 or len(psd) != len(freqs):
        return None, "noise_band_unverified"
    f_lo = freqs[0]
    f_hi = freqs[-1]
    lo = f_lo if f_min is None else float(f_min)
    hi = f_hi if f_max is None else float(f_max)
    if math.isnan(lo) or math.isinf(lo) or math.isnan(hi) or math.isinf(hi) or lo >= hi:
        return None, "invalid_noise_band"
    tol_lo = max(1e-12, 1e-6 * abs(lo))
    tol_hi = max(1e-12, 1e-6 * abs(hi))
    if lo < f_lo - tol_lo or hi > f_hi + tol_hi:
        return None, "noise_band_not_covered"

    lo_clamped = max(f_lo, lo)
    hi_clamped = min(f_hi, hi)
    if hi_clamped <= lo_clamped:
        return None, "invalid_noise_band"

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
    f_scale, f_err = _resolve_trace_unit_scale(_get_parsed_signal_unit(parsed, f_key), expected_dim="freq")
    if f_err:
        out_u = {
            "integrated_rms_noise_v": None,
            "integrated_rms_noise_a": None,
            "noise_unit_errors": ["%s: %s" % (f_key, f_err)],
        }
        return (out_u, None) if return_curve else out_u
    freqs = _scale_numeric_sequence(vals[f_key], f_scale, as_complex=False)
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

    domain, is_psd, si_scale = _classify_noise_unit(unit, n_key)
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
    scale2 = si_scale * si_scale
    psd = [(pr[1] * scale2) if is_psd else ((pr[1] * si_scale) * (pr[1] * si_scale)) for pr in pairs]

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


_MC_HEADER_KEYS = set([
    "analysis type", "analysis", "analysis_type", "title", "psfversion",
    "simulator", "run_mode", "mode", "sweep_type",
])
_MC_HEADER_VAL_RE = re.compile(
    r'(?:^|[^a-z0-9])(?:montecarlo|monte[\s_-]?carlo|mc)(?:$|[^a-z0-9])',
    re.IGNORECASE,
)
_MC_SWEEP_NAMES = set([
    "iteration", "mc_iteration", "montecarlo", "monte_carlo",
    "mc_iter", "mc_run", "mc_sample",
])

_PEX_HEADER_KEYS = set([
    "netlist", "design", "circuit", "cellview", "title", "subckt",
    "view", "viewname", "schematic", "extraction", "pex",
])
_PEX_HEADER_VAL_RE = re.compile(
    r'(?:^|[^a-z0-9])(?:av_extracted|calibre|quantus|rcx|pex|post_?layout|postlayout)(?:$|[^a-z0-9])',
    re.IGNORECASE,
)
_PARASITIC_RC_NAME_RE = re.compile(
    r'(?:^|[\s./:])(?:'
    r'(?:cpar|rpar|c_par|r_par|c_pex|r_pex|cpex|rpex|c_qrc|r_qrc|cqrc|rqrc|c_rcx|r_rcx|crcx|rrcx|c_ext|r_ext|avc|avr|parasitic_[rc])\w*'
    r'|[rc]_(?:net|n)\d+\w*'
    r'|[rc]_\d+_\d+'
    r'|[rc]\d+[#$]\d+\w*'
    r')(?:$|[\s./:(])',
    re.IGNORECASE,
)
_PARASITIC_RC_TYPE_RE = re.compile(
    r'(?:^|[^a-z0-9])(?:cparasitic|rparasitic|parasitic_cap|parasitic_res|pex_[rc]|rcx_[rc]|qrc_[rc])(?:$|[^a-z0-9])',
    re.IGNORECASE,
)


def _count_unique_mc_iterations(sw_vals):
    """Count unique finite/non-empty Monte Carlo iteration identifiers."""
    uniq = set()
    for v in (sw_vals or []):
        if isinstance(v, (bool, complex)) or v is None:
            continue
        if isinstance(v, _NUM_TYPES):
            fv = float(v)
            if _is_finite_num(fv):
                uniq.add(("n", round(fv, 12)))
        else:
            sv = str(v).strip()
            if not sv:
                continue
            try:
                fv = float(sv)
                if _is_finite_num(fv):
                    uniq.add(("n", round(fv, 12)))
                    continue
            except Exception:
                pass
            uniq.add(("s", sv.lower()))
    return len(uniq)


def _detect_mc_from_parsed(parsed):
    """Detect genuine Monte Carlo evidence from parsed PSF SWEEP iteration data (never scalar mc_runs)."""
    is_mc = False
    mc_runs = 0
    sw_primary = str(parsed.get("sweep_name") or "").strip().lower()
    if sw_primary in _MC_SWEEP_NAMES:
        sw_vals = parsed.get("sweep_values") or []
        uniq_n = _count_unique_mc_iterations(sw_vals)
        if uniq_n >= 1:
            is_mc = True
            mc_runs = uniq_n
    else:
        for sw in parsed.get("sweeps") or []:
            if isinstance(sw, dict):
                sn = str(sw.get("name") or "").strip().lower()
                if sn in _MC_SWEEP_NAMES:
                    sv = sw.get("values")
                    if sv is None and (not sw_primary):
                        sv = parsed.get("sweep_values")
                    uniq_n = _count_unique_mc_iterations(sv or [])
                    if uniq_n >= 1:
                        is_mc = True
                        if uniq_n > mc_runs:
                            mc_runs = uniq_n
                        break
    return is_mc, mc_runs


def _detect_pex_from_parsed(parsed):
    """Detect genuine post-layout/PEX evidence requiring BOTH extraction provenance header AND parasitic RC elements."""
    has_pex_header = False
    header = parsed.get("header") or {}
    if isinstance(header, dict):
        for hk_raw, hv_raw in header.items():
            hk = str(hk_raw).strip().lower()
            hv = str(hv_raw).strip().lower()
            if hk in _PEX_HEADER_KEYS and _PEX_HEADER_VAL_RE.search(hv):
                has_pex_header = True
                break

    rc_elems = set()
    instances = parsed.get("instances") or {}
    if isinstance(instances, dict):
        for inst_name, inst_obj in instances.items():
            sname = str(inst_name)
            stype = str(inst_obj.get("type", "")) if isinstance(inst_obj, dict) else ""
            if _PARASITIC_RC_NAME_RE.search(sname) or _PARASITIC_RC_TYPE_RE.search(stype):
                rc_elems.add(sname.lower())

    values = parsed.get("values") or {}
    if isinstance(values, dict):
        for sig_name in values.keys():
            sname = str(sig_name)
            if _PARASITIC_RC_NAME_RE.search(sname):
                rc_elems.add(sname.split(":", 1)[0].lower())

    trace_types = parsed.get("trace_types") or {}
    if isinstance(trace_types, dict):
        for tname, ttype in trace_types.items():
            if _PARASITIC_RC_TYPE_RE.search(str(ttype)):
                rc_elems.add(str(tname).split(":", 1)[0].lower())

    rc_cnt = len(rc_elems)
    is_pex = bool(has_pex_header and rc_cnt > 0)
    return is_pex, rc_cnt


_SHA256_HEX_RE = re.compile(r'^[0-9a-fA-F]{64}$')
_BLOCK_COMMENT_RE = re.compile(r'/\*.*?\*/', re.DOTALL)
_LINE_CONT_RE = re.compile(r'\\\r?\n')
_MC_STMT_RE = re.compile(r'(?<![A-Za-z0-9_])montecarlo(?![A-Za-z0-9_])', re.IGNORECASE)
_PEX_VIEW_MARKER_RE = re.compile(
    r'(?:view(?:\s*name)?|cellview|extracted|extractor|simulator|tool|program|netlist|subckt|include|library)\b[^;\r\n]*\b(?:av_extracted|calibre|quantus|qrc|rcx|pex)\b',
    re.IGNORECASE,
)
_PEX_TOKEN_RE = re.compile(r'(?:^|[^a-z0-9_])(?:av_extracted|calibre|quantus|qrc|rcx|pex)(?:$|[^a-z0-9_])', re.IGNORECASE)
_NETLIST_SECTION_RE = re.compile(r'(?<![A-Za-z0-9_])section\s*=\s*["\']?([A-Za-z0-9_.-]+)["\']?', re.IGNORECASE)
_NETLIST_TEMP_RE = re.compile(r'(?<![A-Za-z0-9_])temp\s*=\s*([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)', re.IGNORECASE)
_CORNER_PREFIX_RE = re.compile(r'^(tt|nn|ss|ff|fs|sf)(?:$|[_.\s-])', re.IGNORECASE)
_LABEL_CORNER_RE = re.compile(r'(?:^|[^a-z0-9])(tt|nn|ss|ff|fs|sf)(?:$|[^a-z0-9])', re.IGNORECASE)
_PSF_CORNER_HDR_KEYS = set([
    "corner", "process", "process_corner", "section",
    "model_section", "model section", "pvt_corner", "mos_corner",
])
_PSF_TEMP_HDR_KEYS = set([
    "temperature", "temp", "temp_c", "sim_temp", "analysis_temp",
])
_TEMP_VAL_RE = re.compile(r'^\s*([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*(deg\s*c|degc|c|k)?\s*$', re.IGNORECASE)
_STABILITY_METRICS = set(["phase_margin_deg", "gain_margin_db", "pm_ac_deg"])

_LBL_V_DEC_RE = re.compile(r'(?:^|[^a-z0-9])(?:vdd|vsup|v)?(\d+)[p.](\d+)v(?:$|[^a-z0-9])')
_LBL_V_INT_RE = re.compile(r'(?:^|[^a-z0-9])(?:vdd|vsup|v)?(\d+(?:\.\d+)?)v(?:$|[^a-z0-9])')
_LBL_MV_DEC_RE = re.compile(r'(?:^|[^a-z0-9])(?:vdd|vsup|v)?(\d+)[p.](\d+)mv(?:$|[^a-z0-9])')
_LBL_MV_INT_RE = re.compile(r'(?:^|[^a-z0-9])(?:vdd|vsup|v)?(\d+(?:\.\d+)?)mv(?:$|[^a-z0-9])')
_LBL_TEMP_NEG_RE = re.compile(r'(?<![a-z0-9-])(?:t-|tm|tn|neg|m|n|-)(\d+(?:\.\d+)?)(?:degc|c)(?=$|[^a-z0-9])')
_LBL_TEMP_POS_RE = re.compile(r'(?:^|[/_\s+]|(?<=[a-z])-)(?:t|temp)?(\d+(?:\.\d+)?)(?:degc|c)(?=$|[^a-z0-9])')
_LBL_TEMP_TOK_NEG_RE = re.compile(r'^(?:t-|tm|tn|neg|m|n|-)(\d+(?:\.\d+)?)(?:degc|c)$')
_LBL_TEMP_TOK_POS_RE = re.compile(r'^(?:t|temp|\+)?(\d+(?:\.\d+)?)(?:degc|c)$')


def _sha256_file(path):
    digest = hashlib.sha256()
    fh = open(path, "rb")
    try:
        while True:
            chunk = fh.read(65536)
            if not chunk:
                break
            digest.update(chunk)
    finally:
        fh.close()
    return digest.hexdigest().lower()


def _inside_dir(path, base_dir):
    rp = os.path.normcase(os.path.realpath(path))
    rb = os.path.normcase(os.path.realpath(base_dir))
    return rp == rb or rp.startswith(rb.rstrip(os.sep) + os.sep)


def _strip_spectre_inline_comment(line):
    in_dq = False
    in_sq = False
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if ch == '"' and not in_sq:
            in_dq = not in_dq
        elif ch == "'" and not in_dq:
            in_sq = not in_sq
        elif not in_dq and not in_sq and ch == "/" and i + 1 < n and line[i + 1] == "/":
            return line[:i]
        i += 1
    return line


def _strip_spectre_comments(text):
    no_block = _BLOCK_COMMENT_RE.sub(" ", text)
    joined = _LINE_CONT_RE.sub(" ", no_block)
    raw_lines = joined.splitlines()
    clean_lines = []
    for raw_ln in raw_lines:
        if raw_ln.lstrip().startswith("*"):
            continue
        cleaned = _strip_spectre_inline_comment(raw_ln).strip()
        if cleaned:
            clean_lines.append(cleaned)
    return raw_lines, "\n".join(clean_lines)


def _netlist_has_pex_markers(raw_lines, net_body):
    has_rc = bool(_PARASITIC_RC_NAME_RE.search(net_body) or _PARASITIC_RC_TYPE_RE.search(net_body))
    if not has_rc:
        return False
    if _PEX_TOKEN_RE.search(net_body):
        return True
    for raw_ln in raw_lines:
        if _PEX_VIEW_MARKER_RE.search(raw_ln):
            return True
    return False


def _normalize_corner_token(raw_val):
    if raw_val is None or isinstance(raw_val, bool):
        return None
    s = str(raw_val).strip().strip('"').strip("'")
    if not s:
        return None
    s_low = s.lower()
    if s_low in ("tt", "nn", "ss", "ff", "fs", "sf"):
        return s_low.upper()
    m = _CORNER_PREFIX_RE.match(s_low)
    if m:
        return m.group(1).upper()
    return s.upper()


def _corners_match(c1, c2):
    n1 = _normalize_corner_token(c1)
    n2 = _normalize_corner_token(c2)
    if n1 is None or n2 is None:
        return False
    if n1 == n2:
        return True
    if set([n1, n2]) == set(["TT", "NN"]):
        return True
    return False


def _parse_temp_c(raw_val):
    if raw_val is None or isinstance(raw_val, bool):
        return None
    if isinstance(raw_val, _NUM_TYPES):
        f = float(raw_val)
        return None if (math.isnan(f) or math.isinf(f)) else f
    if isinstance(raw_val, TEXT_TYPES):
        m = _TEMP_VAL_RE.match(str(raw_val))
        if not m:
            return None
        try:
            val = float(m.group(1))
        except (TypeError, ValueError):
            return None
        if math.isnan(val) or math.isinf(val):
            return None
        unit = (m.group(2) or "").strip().lower()
        if unit == "k":
            return val - 273.15
        return val
    return None


def _extract_psf_pvt_header(parsed):
    """Extract `(corner, temp_c, corner_conflict, temp_conflict)` from a parsed PSF HEADER."""
    header = parsed.get("header") if isinstance(parsed, dict) else None
    if not isinstance(header, dict):
        return None, None, False, False
    corners = []
    temps = []
    for hk_raw, hv_raw in header.items():
        hk = str(hk_raw).strip().lower()
        if hk in _PSF_CORNER_HDR_KEYS:
            c_norm = _normalize_corner_token(hv_raw)
            if c_norm:
                corners.append(c_norm)
        elif hk in _PSF_TEMP_HDR_KEYS:
            t_val = _parse_temp_c(hv_raw)
            if t_val is not None:
                temps.append(t_val)

    corner_conflict = False
    corner_out = corners[0] if corners else None
    if len(corners) > 1:
        for ck in corners[1:]:
            if not _corners_match(ck, corner_out):
                corner_conflict = True
                break

    temp_conflict = False
    temp_out = temps[0] if temps else None
    if len(temps) > 1:
        if (max(temps) - min(temps)) > 0.5:
            temp_conflict = True

    return corner_out, temp_out, corner_conflict, temp_conflict


def _extract_label_corners(label):
    out = []
    lbl = str(label or "").lower()
    for m in _LABEL_CORNER_RE.finditer(lbl):
        c_norm = _normalize_corner_token(m.group(1))
        if c_norm and not any([_corners_match(c_norm, existing) for existing in out]):
            out.append(c_norm)
    return out


def _extract_label_temps(label):
    out = []
    lbl = str(label or "").lower()
    tokens = [t for t in re.split(r'[/_\s]+', lbl) if t]
    for tok in tokens:
        m_n = _LBL_TEMP_TOK_NEG_RE.match(tok)
        if m_n:
            tv = -float(m_n.group(1))
            if not any([abs(tv - ex) <= 1e-6 for ex in out]):
                out.append(tv)
            continue
        m_p = _LBL_TEMP_TOK_POS_RE.match(tok)
        if m_p:
            tv = float(m_p.group(1))
            if not any([abs(tv - ex) <= 1e-6 for ex in out]):
                out.append(tv)
            continue
    for m in _LBL_TEMP_NEG_RE.finditer(lbl):
        tv = -float(m.group(1))
        if not any([abs(tv - ex) <= 1e-6 for ex in out]):
            out.append(tv)
    for m in _LBL_TEMP_POS_RE.finditer(lbl):
        tv = float(m.group(1))
        if not any([abs(tv - ex) <= 1e-6 for ex in out]):
            out.append(tv)
    return out


def _extract_label_voltages(label):
    out = []
    lbl = str(label or "").lower()
    for m in _LBL_V_DEC_RE.finditer(lbl):
        v = float("%s.%s" % (m.group(1), m.group(2)))
        if not any([abs(v - ex) <= 1e-6 for ex in out]):
            out.append(v)
    for m in _LBL_V_INT_RE.finditer(lbl):
        v = float(m.group(1))
        if not any([abs(v - ex) <= 1e-6 for ex in out]):
            out.append(v)
    for m in _LBL_MV_DEC_RE.finditer(lbl):
        v = float("%s.%s" % (m.group(1), m.group(2))) * 1e-3
        if not any([abs(v - ex) <= 1e-6 for ex in out]):
            out.append(v)
    for m in _LBL_MV_INT_RE.finditer(lbl):
        v = float(m.group(1)) * 1e-3
        if not any([abs(v - ex) <= 1e-6 for ex in out]):
            out.append(v)
    return out


def _resolve_manifest_psf_path(mf_dir, rel_k):
    if not isinstance(rel_k, TEXT_TYPES):
        return None
    s_k = str(rel_k).strip()
    if not s_k:
        return None
    cand = os.path.realpath(os.path.join(mf_dir, s_k))
    if os.path.isfile(cand) and _inside_dir(cand, mf_dir):
        return cand
    if "/" not in s_k.replace("\\", "/"):
        hits = []
        for sub in ("psf", "raw"):
            cand_sub = os.path.realpath(os.path.join(mf_dir, sub, s_k))
            if os.path.isfile(cand_sub) and _inside_dir(cand_sub, mf_dir):
                hits.append(cand_sub)
        if len(hits) == 1:
            return hits[0]
    return None


def _verify_bound_manifest(mf_path, audited_psf_files):
    """Cryptographically verify `run_manifest.json` / `cadence_run.json` against netlist & PSF SHA-256s."""
    mf_dir = os.path.realpath(os.path.dirname(mf_path))
    try:
        fh = open(mf_path, "rb")
        try:
            meta = json.loads(fh.read().decode("utf-8-sig"))
        finally:
            fh.close()
    except Exception:
        return None, "invalid_manifest_json"

    if not isinstance(meta, dict):
        return None, "invalid_manifest_object"

    run_id = meta.get("run_id")
    if not isinstance(run_id, TEXT_TYPES) or not str(run_id).strip():
        return None, "missing_or_invalid_run_id"

    exit_code = meta.get("exit_code")
    if isinstance(exit_code, bool) or not isinstance(exit_code, _INT_TYPES) or exit_code != 0:
        return None, "missing_or_nonzero_exit_code"

    np_raw = meta.get("netlist_path")
    nsha_raw = meta.get("netlist_sha256")
    if (
        not isinstance(np_raw, TEXT_TYPES) or not str(np_raw).strip()
        or not isinstance(nsha_raw, TEXT_TYPES) or not _SHA256_HEX_RE.match(str(nsha_raw).strip())
    ):
        return None, "missing_netlist_binding"
    np_str = str(np_raw).strip()
    np_abs = os.path.realpath(np_str if os.path.isabs(np_str) else os.path.join(mf_dir, np_str))
    if not os.path.isfile(np_abs):
        return None, "netlist_path_missing_on_disk"
    if _sha256_file(np_abs) != str(nsha_raw).strip().lower():
        return None, "netlist_sha256_mismatch"

    psf_map = meta.get("psf_files")
    if not isinstance(psf_map, dict) or not psf_map:
        return None, "missing_psf_files_binding"

    verified_psf = {}
    for rel_k, exp_sha in psf_map.items():
        if not isinstance(exp_sha, TEXT_TYPES) or not _SHA256_HEX_RE.match(str(exp_sha).strip()):
            return None, "invalid_psf_sha256_entry"
        resolved_p = _resolve_manifest_psf_path(mf_dir, rel_k)
        if not resolved_p:
            return None, "manifest_psf_missing_on_disk"
        actual_sha = _sha256_file(resolved_p)
        exp_l = str(exp_sha).strip().lower()
        if actual_sha != exp_l:
            return None, "psf_sha256_mismatch"
        verified_psf[os.path.normcase(resolved_p)] = (resolved_p, exp_l)

    if not audited_psf_files:
        return None, "no_audited_psf_files"
    for fp in audited_psf_files:
        if not fp or not os.path.isfile(fp):
            return None, "audited_psf_missing"
        real_fp = os.path.realpath(fp)
        norm_fp = os.path.normcase(real_fp)
        if norm_fp not in verified_psf:
            return None, "unaudited_psf_not_bound_in_manifest"
        if _sha256_file(real_fp) != verified_psf[norm_fp][1]:
            return None, "audited_psf_sha256_mismatch"

    pex_net_abs = None
    if "pex_netlist_path" in meta and meta.get("pex_netlist_path") is not None:
        pn_raw = meta.get("pex_netlist_path")
        psha_raw = meta.get("pex_netlist_sha256")
        if (
            not isinstance(pn_raw, TEXT_TYPES) or not str(pn_raw).strip()
            or not isinstance(psha_raw, TEXT_TYPES) or not _SHA256_HEX_RE.match(str(psha_raw).strip())
        ):
            return None, "invalid_pex_netlist_binding"
        pn_str = str(pn_raw).strip()
        pex_net_abs = os.path.realpath(pn_str if os.path.isabs(pn_str) else os.path.join(mf_dir, pn_str))
        if not os.path.isfile(pex_net_abs) or _sha256_file(pex_net_abs) != str(psha_raw).strip().lower():
            return None, "pex_netlist_sha256_mismatch"

    return {
        "manifest_dir": mf_dir,
        "meta": meta,
        "netlist_path": np_abs,
        "pex_netlist_path": pex_net_abs,
        "verified_psf": verified_psf,
    }, None


def _detect_evidence_from_run_metadata(psf_files, return_details=False):
    """Read cryptographically bound run metadata JSON (`run_manifest.json` / `cadence_run.json`) adjacent to point PSF files."""
    mc_ev = False
    mc_runs = 0
    pex_ev = False
    manifest_bound = False
    rejected_reason = None
    manifest_corner = None
    manifest_temp_c = None
    open_loop_rhp_poles = None
    verified_mc_files_map = {}  # normcase_real_path -> count

    cand_dirs = []
    seen_dirs = set()
    for fp in psf_files:
        if not fp:
            continue
        d = os.path.realpath(os.path.dirname(fp))
        if d not in seen_dirs:
            seen_dirs.add(d)
            cand_dirs.append(d)
        if os.path.basename(d).lower() in ("psf", "raw"):
            parent_d = os.path.realpath(os.path.dirname(d))
            if parent_d not in seen_dirs:
                seen_dirs.add(parent_d)
                cand_dirs.append(parent_d)

    for d in cand_dirs:
        for mf_name in ("run_manifest.json", "cadence_run.json"):
            mf_path = os.path.join(d, mf_name)
            if not os.path.isfile(mf_path):
                continue
            bound, rej = _verify_bound_manifest(mf_path, psf_files)
            if bound is None:
                if rejected_reason is None:
                    rejected_reason = rej
                continue

            manifest_bound = True
            meta = bound["meta"]
            mf_dir = bound["manifest_dir"]
            verified_psf = bound["verified_psf"]

            # Read bound netlist
            fh = open(bound["netlist_path"], "rb")
            try:
                net_txt = fh.read().decode("utf-8", "replace")
            finally:
                fh.close()
            raw_lines, net_body = _strip_spectre_comments(net_txt)

            # Bound MC evidence: netlist must contain `montecarlo` outside comments AND counts come ONLY from verified disk PSF artifacts
            if _MC_STMT_RE.search(net_body):
                cand_mc_entries = []
                if isinstance(meta.get("mc_psf_files"), list):
                    cand_mc_entries.extend(meta["mc_psf_files"])
                mc_obj = meta.get("monte_carlo")
                if isinstance(mc_obj, dict):
                    if isinstance(mc_obj.get("mc_psf_files"), list):
                        cand_mc_entries.extend(mc_obj["mc_psf_files"])
                    if isinstance(mc_obj.get("iterations"), list):
                        cand_mc_entries.extend(mc_obj["iterations"])

                resolved_mc_targets = []
                for item in cand_mc_entries:
                    item_path = None
                    item_sha = None
                    if isinstance(item, TEXT_TYPES):
                        item_path = _resolve_manifest_psf_path(mf_dir, item)
                    elif isinstance(item, dict):
                        p_str = item.get("path") or item.get("file") or item.get("psf")
                        item_path = _resolve_manifest_psf_path(mf_dir, p_str)
                        s_raw = item.get("sha256")
                        if s_raw is not None:
                            if not isinstance(s_raw, TEXT_TYPES) or not _SHA256_HEX_RE.match(str(s_raw).strip()):
                                continue
                            item_sha = str(s_raw).strip().lower()
                    if not item_path:
                        continue
                    norm_mc = os.path.normcase(item_path)
                    if norm_mc not in verified_psf:
                        continue
                    if item_sha is not None and verified_psf[norm_mc][1] != item_sha:
                        continue
                    if norm_mc not in [x[0] for x in resolved_mc_targets]:
                        resolved_mc_targets.append((norm_mc, item_path))

                # Also inspect audited PSF files themselves for iteration sweeps or MC artifacts
                for fp in psf_files:
                    real_fp = os.path.realpath(fp)
                    norm_fp = os.path.normcase(real_fp)
                    if norm_fp not in [x[0] for x in resolved_mc_targets]:
                        resolved_mc_targets.append((norm_fp, real_fp))

                distinct_single_mc = 0
                sweep_mc_total = 0
                seen_single_shas = set()
                seen_header_iters = set()
                has_explicit_mc_list = len(cand_mc_entries) > 0
                for norm_mc, mc_path in resolved_mc_targets:
                    try:
                        mc_parsed = parse_psf_file(
                            mc_path,
                            reject_nonfinite=True,
                            reject_truncated=True,
                            fill_leading_missing=True,
                        )
                    except Exception:
                        continue
                    is_p_mc, p_mc_runs = _detect_mc_from_parsed(mc_parsed)
                    sw_vals = mc_parsed.get("sweep_values") or []
                    sw_name = str(mc_parsed.get("sweep_name") or "").strip().lower()
                    if sw_name in _MC_SWEEP_NAMES and len(sw_vals) > 0:
                        uniq_sw = _count_unique_mc_iterations(sw_vals)
                        if uniq_sw > 0:
                            sweep_mc_total += uniq_sw
                            verified_mc_files_map[norm_mc] = uniq_sw
                    elif is_p_mc and p_mc_runs > 0:
                        sweep_mc_total += p_mc_runs
                        verified_mc_files_map[norm_mc] = p_mc_runs
                    else:
                        bn_l = os.path.basename(mc_path).lower()
                        is_mc_fn = (_classify_psf_filename(bn_l) == "mc") or ("mc" in bn_l) or ("iter" in bn_l)
                        if is_p_mc or is_mc_fn or (has_explicit_mc_list and len(resolved_mc_targets) >= 2):
                            file_sha = verified_psf.get(norm_mc, (None, None))[1]
                            if not file_sha:
                                file_sha = _sha256_file(mc_path)
                            if file_sha in seen_single_shas:
                                continue
                            hdr_iter_tok = None
                            hdr_obj = mc_parsed.get("header") or {}
                            if isinstance(hdr_obj, dict):
                                for h_k, h_v in hdr_obj.items():
                                    hk_l = str(h_k).strip().lower()
                                    if hk_l in ("mc_iteration", "mc_iter", "iteration", "mc_run"):
                                        hv_l = str(h_v).strip().lower()
                                        if hv_l not in ("", "0", "false", "no", "off", "none"):
                                            hdr_iter_tok = hv_l
                                            break
                            if hdr_iter_tok is not None:
                                if hdr_iter_tok in seen_header_iters:
                                    continue
                                seen_header_iters.add(hdr_iter_tok)
                            seen_single_shas.add(file_sha)
                            distinct_single_mc += 1
                            verified_mc_files_map[norm_mc] = 1

                tot_verified_mc = sweep_mc_total + distinct_single_mc
                if tot_verified_mc > 0:
                    mc_ev = True
                    if tot_verified_mc > mc_runs:
                        mc_runs = tot_verified_mc

            # Bound PEX evidence: requires genuine extracted markers in bound netlist or verified pex_netlist_path
            pex_disabled = (meta.get("post_layout") is False or meta.get("pex") is False or meta.get("pex_verified") is False)
            if not pex_disabled:
                if _netlist_has_pex_markers(raw_lines, net_body):
                    pex_ev = True
                elif bound["pex_netlist_path"] is not None:
                    pfh = open(bound["pex_netlist_path"], "rb")
                    try:
                        p_txt = pfh.read().decode("utf-8", "replace")
                    finally:
                        pfh.close()
                    p_raw, p_body = _strip_spectre_comments(p_txt)
                    if _netlist_has_pex_markers(p_raw, p_body):
                        pex_ev = True

            # Open-loop RHP pole count from bound manifest
            ol_p = meta.get("open_loop_rhp_poles")
            if isinstance(ol_p, _INT_TYPES) and not isinstance(ol_p, bool) and ol_p >= 0:
                open_loop_rhp_poles = int(ol_p)

            # Bound corner / temperature fallback
            if meta.get("corner") is not None:
                manifest_corner = _normalize_corner_token(meta.get("corner"))
            if manifest_corner is None:
                sec_corners = []
                for m_s in _NETLIST_SECTION_RE.finditer(net_body):
                    cn = _normalize_corner_token(m_s.group(1))
                    if cn in ("TT", "NN", "SS", "FF", "FS", "SF"):
                        if not any([_corners_match(cn, x) for x in sec_corners]):
                            sec_corners.append(cn)
                if len(sec_corners) == 1:
                    manifest_corner = sec_corners[0]

            if meta.get("temperature_c") is not None:
                manifest_temp_c = _parse_temp_c(meta.get("temperature_c"))
            if manifest_temp_c is None:
                net_temps = []
                for m_t in _NETLIST_TEMP_RE.finditer(net_body):
                    try:
                        tv = float(m_t.group(1))
                    except (TypeError, ValueError):
                        continue
                    if not any([abs(tv - x) <= 0.01 for x in net_temps]):
                        net_temps.append(tv)
                if len(net_temps) == 1:
                    manifest_temp_c = net_temps[0]

    if return_details:
        return mc_ev, mc_runs, pex_ev, {
            "manifest_bound": manifest_bound,
            "manifest_rejected_reason": rejected_reason if not manifest_bound else None,
            "corner": manifest_corner,
            "temperature_c": manifest_temp_c,
            "open_loop_rhp_poles": open_loop_rhp_poles,
        }
    return mc_ev, mc_runs, pex_ev


def _check_point_label_vs_metadata(point_label, pm):
    """Detect conflicts between directory/point label claims and simulator PVT metadata."""
    conflicts = []
    if not point_label or not isinstance(pm, dict):
        return conflicts

    lbl_corners = _extract_label_corners(point_label)
    if len(lbl_corners) > 1:
        conflicts.append("ambiguous_label_corners: %s" % ",".join(lbl_corners))
    psf_corner = _normalize_corner_token(pm.get("psf_corner"))
    if psf_corner is not None and lbl_corners:
        for lc in lbl_corners:
            if not _corners_match(lc, psf_corner):
                conflicts.append("label corner %s != psf_corner %s" % (lc, psf_corner))

    lbl_temps = _extract_label_temps(point_label)
    if len(lbl_temps) > 1:
        if (max(lbl_temps) - min(lbl_temps)) > 0.5:
            conflicts.append("ambiguous_label_temps: %s" % ",".join([str(t) for t in lbl_temps]))
    psf_temp = _parse_temp_c(pm.get("psf_temperature_c"))
    if psf_temp is not None and lbl_temps:
        for lt in lbl_temps:
            if abs(lt - psf_temp) > 0.5:
                conflicts.append("label temperature %gC != psf_temperature_c %gC" % (lt, psf_temp))

    lbl_volts = _extract_label_voltages(point_label)
    rail_volts = {}
    rv_raw = pm.get("rail_voltages")
    if isinstance(rv_raw, dict):
        for rk, rval in rv_raw.items():
            if _is_finite_num(rval):
                rail_volts[str(rk).strip().lower()] = float(rval)
    for r in pm.get("supply_rails") or []:
        if isinstance(r, dict) and _is_finite_num(r.get("vdd_v")):
            rk = str(r.get("rail") or "vdd").strip().lower()
            rail_volts.setdefault(rk, float(r["vdd_v"]))

    supply_vs = []
    vdd = pm.get("vdd_v")
    if _is_finite_num(vdd):
        supply_vs.append(float(vdd))
    elif "vdd" in rail_volts:
        supply_vs.append(float(rail_volts["vdd"]))
    elif pm.get("primary_supply_rail") and str(pm["primary_supply_rail"]).strip().lower() in rail_volts:
        supply_vs.append(float(rail_volts[str(pm["primary_supply_rail"]).strip().lower()]))
    elif len(rail_volts) == 1:
        supply_vs.append(float(list(rail_volts.values())[0]))
    elif len(rail_volts) > 1 and lbl_volts:
        conflicts.append(
            "ambiguous bare label voltage %s across multi-rail %s" % (
                ",".join(["%gV" % v for v in lbl_volts]),
                repr(sorted(rail_volts.keys())),
            )
        )

    if supply_vs and lbl_volts:
        for lv in lbl_volts:
            tol_v = max(0.01, 0.02 * abs(lv))
            if not any([abs(sv - lv) <= tol_v for sv in supply_vs]):
                conflicts.append("label voltage %gV != measured supply_v %s" % (lv, repr(supply_vs)))

    return conflicts


def _aggregate_ac_group(runs_map):
    """Aggregate one or more AC/PAC runs worst-case; fail closed on unit errors."""
    out = {}
    u_errs = []
    for k in sorted(runs_map.keys()):
        for err in runs_map[k].get("ac_unit_errors") or []:
            u_errs.append("%s: %s" % (k, err))
    for m_k in ("dc_gain_db", "bw_3db_hz", "ugf_hz", "pm_ac_deg"):
        if u_errs:
            out[m_k] = None
            continue
        vals_k = [
            r[m_k] for r in runs_map.values()
            if isinstance(r.get(m_k), _NUM_TYPES) and not isinstance(r.get(m_k), bool)
        ]
        any_none = any([r.get(m_k) is None for r in runs_map.values()])
        if vals_k and not any_none:
            out[m_k] = _round_clean(min(vals_k))
        elif len(runs_map) == 1 and vals_k:
            out[m_k] = _round_clean(vals_k[0])
        else:
            out[m_k] = None
    first_ac = runs_map[sorted(runs_map.keys())[0]]
    if first_ac.get("ac_output"):
        out["ac_output"] = first_ac["ac_output"]
    if first_ac.get("ac_input"):
        out["ac_input"] = first_ac["ac_input"]
    if len(runs_map) > 1:
        out["ac_runs"] = runs_map
    if u_errs:
        out["ac_unit_errors"] = u_errs
    return out


def _aggregate_stb_group(group_loops):
    """Aggregate STB or PSTB loops worst-case; fail closed on RHP anomaly or unit errors."""
    out = {}
    u_errs = []
    for k in sorted(group_loops.keys()):
        for err in group_loops[k].get("stb_unit_errors") or []:
            u_errs.append("%s: %s" % (k, err))
    any_rhp_pole = any([bool(r.get("rhp_open_loop_pole_suspected")) for r in group_loops.values()])
    for m_k in ("loop_dc_gain_db", "stb_ugf_hz", "phase_margin_deg", "gain_margin_db"):
        vals_k = [
            r[m_k] for r in group_loops.values()
            if isinstance(r.get(m_k), _NUM_TYPES) and not isinstance(r.get(m_k), bool)
        ]
        tainted = bool(u_errs)
        if (not tainted) and any_rhp_pole and m_k in ("phase_margin_deg", "gain_margin_db"):
            tainted = True
        if (not tainted) and m_k in ("phase_margin_deg", "stb_ugf_hz") and len(group_loops) > 1:
            for r in group_loops.values():
                if r.get(m_k) is None and (r.get("loop_dc_gain_db") is None or r.get("loop_dc_gain_db", -1.0) >= 0.0):
                    tainted = True
                    break
        if vals_k and not tainted:
            out[m_k] = _round_clean(min(vals_k))
        else:
            out[m_k] = None
    out["dc_positive_feedback"] = any([bool(r.get("dc_positive_feedback")) for r in group_loops.values()])
    if any_rhp_pole:
        out["rhp_open_loop_pole_suspected"] = True
        for r_s in group_loops.values():
            if r_s.get("stb_notes"):
                out["stb_notes"] = r_s["stb_notes"]
                break
    if u_errs:
        out["stb_unit_errors"] = u_errs
    if len(group_loops) == 1:
        only_stb = group_loops[list(group_loops.keys())[0]]
        for extra_k in (
            "stb_probe_signal", "gm_freq_hz", "ugf_crossing_count",
            "all_ugf_crossings", "all_gm_crossings", "stb_notes",
            "nyquist_cw_encirclements", "nyquist_contour_closed",
        ):
            if extra_k in only_stb:
                out[extra_k] = only_stb[extra_k]
    else:
        out["stb_loops"] = group_loops
        out["nyquist_contour_closed"] = all([bool(r.get("nyquist_contour_closed")) for r in group_loops.values()])
        nyq_vals = [
            r["nyquist_cw_encirclements"] for r in group_loops.values()
            if r.get("nyquist_cw_encirclements") is not None
        ]
        if nyq_vals and len(nyq_vals) == len(group_loops):
            out["nyquist_cw_encirclements"] = max(nyq_vals) if any([v > 0 for v in nyq_vals]) else min(nyq_vals)
    return out


def _aggregate_noise_group(runs_map):
    """Aggregate Noise or PNoise runs worst-case (`max`); fail closed on unit errors."""
    out = {}
    u_errs = []
    for k in sorted(runs_map.keys()):
        for err in runs_map[k].get("noise_unit_errors") or []:
            u_errs.append("%s: %s" % (k, err))
    for nk in ("integrated_rms_noise_v", "integrated_rms_noise_a"):
        if u_errs:
            out[nk] = None
            continue
        vals_k = [
            r[nk] for r in runs_map.values()
            if isinstance(r.get(nk), _NUM_TYPES) and not isinstance(r.get(nk), bool)
        ]
        out[nk] = _round_clean(max(vals_k)) if vals_k else None
    fmins = [
        r["noise_freq_min_hz"] for r in runs_map.values()
        if isinstance(r.get("noise_freq_min_hz"), _NUM_TYPES) and not isinstance(r.get("noise_freq_min_hz"), bool)
    ]
    fmaxs = [
        r["noise_freq_max_hz"] for r in runs_map.values()
        if isinstance(r.get("noise_freq_max_hz"), _NUM_TYPES) and not isinstance(r.get("noise_freq_max_hz"), bool)
    ]
    if fmins:
        out["noise_freq_min_hz"] = _round_clean(min(fmins))
    if fmaxs:
        out["noise_freq_max_hz"] = _round_clean(max(fmaxs))
    if len(runs_map) == 1:
        only_ns = runs_map[list(runs_map.keys())[0]]
        for extra_k in ("noise_signal", "noise_unit", "noise_domain"):
            if extra_k in only_ns:
                out[extra_k] = only_ns[extra_k]
    else:
        out["noise_runs"] = runs_map
    if u_errs:
        out["noise_unit_errors"] = u_errs
    return out


_GENERIC_PZ_STEMS = set(["", "pz", "closed_loop", "open_loop", "closedloop", "openloop", "cl", "ol", "pz_cl", "pz_ol"])
_GENERIC_STB_STEMS = set(["", "stb", "pstb", "margin", "loop"])


def _check_pz_stb_provenance(pz_runs, stb_loops, stb_loop_stems, cl_valid):
    """Validate circuit/testbench/loop/stem consistency across `.pz` and `.stb` runs."""
    conflicts = []
    # Cross-`.pz` global header agreement (circuit, testbench, netlist)
    pz_global_tags = {}
    for pr in pz_runs:
        ptags = pr.get("provenance_tags") or {}
        for cat in ("circuit", "testbench", "netlist"):
            val = ptags.get(cat)
            if not val:
                continue
            if cat in pz_global_tags and pz_global_tags[cat] != val:
                conflicts.append("pz_%s_conflict:%s!=%s" % (cat, pz_global_tags[cat], val))
            else:
                pz_global_tags[cat] = val

    # Match each `.pz` file against `.stb`/`.pstb` loops by stem & provenance tags
    all_stb_stems = set([st for st in stb_loop_stems.values() if st])
    named_stb_stems = set([st for st in all_stb_stems if st not in _GENERIC_STB_STEMS])
    stb_tags_list = [(skey, stb_loop_stems.get(skey, ""), (lr.get("provenance_tags") or {})) for skey, lr in stb_loops.items()]

    for pr in pz_runs:
        raw_stem = str(pr.get("pz_stem") or "").lower()
        norm_stem = re.sub(r'(?:^|[_.-])pz(?:$|[_.-])', '_', raw_stem).strip('_.- ')
        ptags = pr.get("provenance_tags") or {}
        is_generic = (raw_stem in _GENERIC_PZ_STEMS) or (norm_stem in _GENERIC_PZ_STEMS)

        if stb_loops and (not is_generic):
            stem_ok = (norm_stem in all_stb_stems) or (raw_stem in all_stb_stems)
            if (not stem_ok) and named_stb_stems:
                stem_ok = any([(norm_stem == st or raw_stem == st) for st in named_stb_stems])
            if not stem_ok:
                conflicts.append("pz_stb_stem_mismatch:%s" % raw_stem)

        if len(stb_tags_list) == 1:
            stags = stb_tags_list[0][2]
            for cat in ("circuit", "testbench", "loop", "netlist"):
                if ptags.get(cat) and stags.get(cat) and ptags[cat] != stags[cat]:
                    conflicts.append("pz_stb_%s_mismatch:%s!=%s" % (cat, ptags[cat], stags[cat]))
        elif len(stb_tags_list) > 1:
            matched_targets = []
            for skey, s_stem, stags in stb_tags_list:
                if (not is_generic) and (norm_stem == s_stem or raw_stem == s_stem):
                    matched_targets.append((skey, stags))
                elif ptags.get("loop") and stags.get("loop") and ptags["loop"] == stags["loop"]:
                    matched_targets.append((skey, stags))
            if not matched_targets:
                matched_targets = [(skey, stags) for skey, _, stags in stb_tags_list]
            for _, stags in matched_targets:
                for cat in ("circuit", "testbench", "netlist"):
                    if ptags.get(cat) and stags.get(cat) and ptags[cat] != stags[cat]:
                        conflicts.append("pz_stb_%s_mismatch:%s!=%s" % (cat, ptags[cat], stags[cat]))
                if (len(matched_targets) == 1) and ptags.get("loop") and stags.get("loop") and ptags["loop"] != stags["loop"]:
                    conflicts.append("pz_stb_loop_mismatch:%s!=%s" % (ptags["loop"], stags["loop"]))

    # Multi-loop closed-loop `.pz` coverage requirement
    cl_all_loops_covered = True
    if len(stb_loops) > 1 and cl_valid:
        for skey, s_stem in stb_loop_stems.items():
            stags = (stb_loops[skey].get("provenance_tags") or {})
            loop_tag = stags.get("loop")
            found = False
            for cr in cl_valid:
                c_raw = str(cr.get("pz_stem") or "").lower()
                c_norm = re.sub(r'(?:^|[_.-])pz(?:$|[_.-])', '_', c_raw).strip('_.- ')
                ctags = cr.get("provenance_tags") or {}
                if loop_tag and ctags.get("loop") and loop_tag == ctags["loop"]:
                    found = True
                    break
                if s_stem and s_stem not in _GENERIC_STB_STEMS and (c_norm == s_stem or c_raw == s_stem):
                    found = True
                    break
            if not found:
                cl_all_loops_covered = False
        if not cl_all_loops_covered:
            conflicts.append("multi_loop_missing_matching_closed_loop_pz")

    dedup_conf = []
    for c in conflicts:
        if c not in dedup_conf:
            dedup_conf.append(c)
    return dedup_conf, cl_all_loops_covered


def _extract_point_metrics(
    psf_files_by_kind,
    vout_hint=None,
    vin_hint=None,
    settling_tol_ratio=0.01,
    target_v=None,
    base_dir=None,
    aux_out=None,
    point_label=None,
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
    mc_flag = [False]
    mc_runs_box = [0]
    pex_flag = [False]
    rc_count_box = [0]
    hdr_corners = []
    hdr_temps = []
    hdr_conflicts = []

    def _add_analysis(tag):
        if tag not in analyses_present:
            analyses_present.append(tag)

    def _inspect_parsed_evidence(parsed_obj, fpath=""):
        if not isinstance(parsed_obj, dict):
            return
        is_mc, mc_n = _detect_mc_from_parsed(parsed_obj)
        if is_mc:
            mc_flag[0] = True
            if mc_n > mc_runs_box[0]:
                mc_runs_box[0] = mc_n
        is_pex, rc_cnt = _detect_pex_from_parsed(parsed_obj)
        if is_pex:
            pex_flag[0] = True
        if rc_cnt > 0:
            rc_count_box[0] += rc_cnt
        hc, ht, hc_conf, ht_conf = _extract_psf_pvt_header(parsed_obj)
        src_bn = os.path.basename(fpath) if fpath else "psf"
        if hc_conf:
            hdr_conflicts.append("conflicting corner headers inside %s" % src_bn)
        if ht_conf:
            hdr_conflicts.append("conflicting temperature headers inside %s" % src_bn)
        if hc is not None:
            hdr_corners.append((src_bn, hc))
        if ht is not None:
            hdr_temps.append((src_bn, ht))

    metrics_by_analysis = {}
    all_trace_u_errs = []

    parsed_dc = []
    for p in psf_files_by_kind.get("dc", []):
        dc_parsed = parse_psf_file(p, reject_nonfinite=True, reject_truncated=True, fill_leading_missing=True)
        _inspect_parsed_evidence(dc_parsed, p)
        parsed_dc.append(dc_parsed)
    if parsed_dc:
        _add_analysis("dc")
        dc_res = _extract_dc_power(parsed_dc)
        metrics.update(dc_res)
        metrics_by_analysis["dc"] = dict(dc_res)
        for uerr in dc_res.get("dc_unit_errors") or []:
            all_trace_u_errs.append("dc: %s" % uerr)

    # Process ALL `.ac` / `.pac` files in this point with strict per-analysis partitioning
    ac_files = psf_files_by_kind.get("ac", [])
    ac_keys = _build_unique_file_keys(ac_files, base_dir=base_dir)
    ac_runs = {}
    pure_ac_runs = {}
    pac_runs = {}
    has_pac = False
    for p in ac_files:
        is_pac_file = os.path.basename(p).lower().endswith(".pac")
        if is_pac_file:
            has_pac = True
        ac_parsed = parse_psf_file(p, reject_nonfinite=True, reject_truncated=True, fill_leading_missing=True)
        _inspect_parsed_evidence(ac_parsed, p)
        ac_res = _extract_ac_metrics(
            ac_parsed,
            vout_hint=vout_hint,
            vin_hint=vin_hint,
        )
        if ac_res:
            akey = ac_keys[p]
            ac_runs[akey] = ac_res
            if is_pac_file:
                pac_runs[akey] = ac_res
            else:
                pure_ac_runs[akey] = ac_res
    if ac_runs:
        _add_analysis("ac")
        if has_pac:
            _add_analysis("pac")
        ac_agg = _aggregate_ac_group(ac_runs)
        metrics.update(ac_agg)
        for uerr in ac_agg.get("ac_unit_errors") or []:
            all_trace_u_errs.append("ac: %s" % uerr)
        if pure_ac_runs:
            metrics_by_analysis["ac"] = _aggregate_ac_group(pure_ac_runs)
        elif pac_runs:
            metrics_by_analysis["ac"] = _aggregate_ac_group(pac_runs)
        if pac_runs:
            metrics_by_analysis["pac"] = _aggregate_ac_group(pac_runs)

    # Process ALL `.stb` / `.pstb` + `.margin.*` loops cleanly (NEVER cross-pair `.stb` with `.pstb`)
    stb_files = psf_files_by_kind.get("stb", [])
    margin_files = psf_files_by_kind.get("stb_margin", [])
    all_stb_keys = _build_unique_file_keys(stb_files + margin_files, base_dir=base_dir)

    margin_entries = []  # list of (mp, is_pstb, dir_real, stem, parsed)
    margin_by_kind_dir_stem = {}
    margin_by_kind_stem_list = {}
    has_pstb = False
    stb_file_counts = {False: 0, True: 0}
    margin_file_counts = {False: 0, True: 0}
    for sp in stb_files:
        is_p = os.path.basename(sp).lower().endswith(".pstb")
        stb_file_counts[is_p] = stb_file_counts.get(is_p, 0) + 1
    for mp in margin_files:
        is_p = os.path.basename(mp).lower().endswith(".pstb")
        if is_p:
            has_pstb = True
        margin_file_counts[is_p] = margin_file_counts.get(is_p, 0) + 1
        m_stem = _stb_loop_stem(mp)
        m_dir = os.path.realpath(os.path.dirname(mp))
        m_parsed = parse_psf_file(mp, reject_nonfinite=True, reject_truncated=True, fill_leading_missing=True)
        _inspect_parsed_evidence(m_parsed, mp)
        entry = (mp, is_p, m_dir, m_stem, m_parsed)
        margin_entries.append(entry)
        margin_by_kind_dir_stem[(is_p, m_dir, m_stem)] = entry
        margin_by_kind_stem_list.setdefault((is_p, m_stem), []).append(entry)

    generic_margin_stems = set(["stb", "pstb", "margin", "loop"])
    stb_loops = {}
    stb_loops_pure = {}
    pstb_loops = {}
    stb_loop_stems = {}
    used_margin_paths = set()
    for sp in stb_files:
        is_p = os.path.basename(sp).lower().endswith(".pstb")
        if is_p:
            has_pstb = True
        stem = _stb_loop_stem(sp)
        s_dir = os.path.realpath(os.path.dirname(sp))
        m_entry = margin_by_kind_dir_stem.get((is_p, s_dir, stem))
        if m_entry is None:
            same_stem = [e for e in margin_by_kind_stem_list.get((is_p, stem), []) if e[0] not in used_margin_paths]
            if len(same_stem) == 1:
                m_entry = same_stem[0]
        if m_entry is None and stb_file_counts.get(is_p, 0) == 1 and margin_file_counts.get(is_p, 0) == 1:
            # Allow generic unnamed margin file within the SAME analysis kind (`.stb` vs `.pstb`) ONLY
            same_kind_cands = [e for e in margin_entries if e[1] == is_p and e[0] not in used_margin_paths]
            if len(same_kind_cands) == 1 and same_kind_cands[0][3].lower() in generic_margin_stems:
                m_entry = same_kind_cands[0]
        m_parsed = None
        if m_entry is not None:
            used_margin_paths.add(m_entry[0])
            m_parsed = m_entry[4]
        s_parsed = parse_psf_file(sp, reject_nonfinite=True, reject_truncated=True, fill_leading_missing=True)
        _inspect_parsed_evidence(s_parsed, sp)
        s_res = _extract_stb_metrics(s_parsed, margin_parsed=m_parsed)
        if s_res:
            skey = all_stb_keys[sp]
            stb_loops[skey] = s_res
            stb_loop_stems[skey] = stem.lower()
            if is_p:
                pstb_loops[skey] = s_res
            else:
                stb_loops_pure[skey] = s_res

    for mp, is_p, _, m_stem, m_parsed in margin_entries:
        if mp not in used_margin_paths:
            s_res = _extract_stb_metrics(None, margin_parsed=m_parsed)
            if s_res:
                skey = all_stb_keys[mp]
                stb_loops[skey] = s_res
                stb_loop_stems[skey] = m_stem.lower()
                if is_p:
                    pstb_loops[skey] = s_res
                else:
                    stb_loops_pure[skey] = s_res

    if stb_loops:
        _add_analysis("stb")
        if has_pstb:
            _add_analysis("pstb")
        stb_agg = _aggregate_stb_group(stb_loops)
        metrics.update(stb_agg)
        for uerr in stb_agg.get("stb_unit_errors") or []:
            all_trace_u_errs.append("stb: %s" % uerr)
        if stb_loops_pure:
            metrics_by_analysis["stb"] = _aggregate_stb_group(stb_loops_pure)
        elif pstb_loops:
            metrics_by_analysis["stb"] = _aggregate_stb_group(pstb_loops)
        if pstb_loops:
            metrics_by_analysis["pstb"] = _aggregate_stb_group(pstb_loops)

    # Process `.pz` / `.pz.psf` / `pz.info` files (closed-loop, open-loop, and unknown/untyped)
    pz_files = psf_files_by_kind.get("pz", [])
    pz_keys = _build_unique_file_keys(pz_files, base_dir=base_dir)
    cl_pz_runs = []
    ol_pz_runs = []
    unknown_pz_runs = []
    any_pz_parsed_ok = False
    for pz_p in pz_files:
        pz_parsed = parse_psf_file(pz_p, reject_nonfinite=True, reject_truncated=True, fill_leading_missing=True)
        _inspect_parsed_evidence(pz_parsed, pz_p)
        pz_res = _extract_pz_metrics(pz_parsed, path=pz_p)
        _add_analysis("pz")
        if pz_res.get("pz_parsed_ok"):
            any_pz_parsed_ok = True
        pz_res["file_key"] = pz_keys[pz_p]
        pz_res["stem"] = pz_res.get("pz_stem") or _pz_loop_stem(pz_p)
        mode_pz = pz_res.get("pz_mode")
        if mode_pz == "open_loop":
            ol_pz_runs.append(pz_res)
        elif mode_pz == "closed_loop":
            cl_pz_runs.append(pz_res)
        else:
            unknown_pz_runs.append(pz_res)
    if pz_files:
        metrics["pz_parsed_ok"] = any_pz_parsed_ok
        metrics["pz_modes_present"] = sorted(list(set([r.get("pz_mode", "unknown") for r in (cl_pz_runs + ol_pz_runs + unknown_pz_runs)])))
        if unknown_pz_runs:
            metrics["pz_unknown_mode_count"] = len(unknown_pz_runs)

    # Process `.pss` files if present so `pss` analysis coverage can be verified distinctly
    for pss_p in psf_files_by_kind.get("pss", []):
        pss_parsed = parse_psf_file(pss_p, reject_nonfinite=True, reject_truncated=True, fill_leading_missing=True)
        _inspect_parsed_evidence(pss_parsed, pss_p)
        _add_analysis("pss")

    # Process ALL `.tran` files with collision-free keys and aggregate worst-case; fail-closed on unsettled step or unit errors
    tran_files = psf_files_by_kind.get("tran", [])
    tran_keys = _build_unique_file_keys(tran_files, base_dir=base_dir)
    tran_runs = {}
    for tp in tran_files:
        tp_parsed = parse_psf_file(tp, reject_nonfinite=True, reject_truncated=True, fill_leading_missing=True)
        _inspect_parsed_evidence(tp_parsed, tp)
        tr_res = _extract_tran_metrics(
            tp_parsed,
            vout_hint=vout_hint,
            settling_tol_ratio=settling_tol_ratio,
            target_v=target_v,
        )
        if tr_res:
            tran_runs[tran_keys[tp]] = tr_res
    if tran_runs:
        _add_analysis("tran")
        tran_agg = {}
        tran_u_errs = []
        for tk in sorted(tran_runs.keys()):
            for uerr in tran_runs[tk].get("tran_unit_errors") or []:
                tran_u_errs.append("%s: %s" % (tk, uerr))
        if tran_u_errs:
            all_trace_u_errs.extend(["tran: %s" % e for e in tran_u_errs])
            tran_agg["tran_unit_errors"] = tran_u_errs
            for m_k in ("slew_rate_pos", "slew_rate_neg", "overshoot_pct", "ripple_pp", "settling_time_s"):
                metrics[m_k] = None
                tran_agg[m_k] = None
        else:
            for min_k in ("slew_rate_pos", "slew_rate_neg"):
                vals_k = [r[min_k] for r in tran_runs.values() if isinstance(r.get(min_k), _NUM_TYPES) and not isinstance(r.get(min_k), bool)]
                val_m = _round_clean(min(vals_k)) if vals_k else None
                metrics[min_k] = val_m
                tran_agg[min_k] = val_m
            for max_k in ("overshoot_pct", "ripple_pp"):
                vals_k = [r[max_k] for r in tran_runs.values() if isinstance(r.get(max_k), _NUM_TYPES) and not isinstance(r.get(max_k), bool)]
                val_m = _round_clean(max(vals_k)) if vals_k else None
                metrics[max_k] = val_m
                tran_agg[max_k] = val_m

            step_runs = [r for r in tran_runs.values() if r.get("step_detected")]
            if step_runs:
                if any([r.get("settling_time_s") is None for r in step_runs]):
                    metrics["settling_time_s"] = None
                    tran_agg["settling_time_s"] = None
                else:
                    val_st = _round_clean(max([r["settling_time_s"] for r in step_runs]))
                    metrics["settling_time_s"] = val_st
                    tran_agg["settling_time_s"] = val_st
            else:
                metrics["settling_time_s"] = None
                tran_agg["settling_time_s"] = None

        first_tr = tran_runs[sorted(tran_runs.keys())[0]]
        for tr_extra in ("tran_output", "tran_init_v", "tran_final_v", "settling_target_v", "static_error_v"):
            if first_tr.get(tr_extra) is not None:
                metrics[tr_extra] = first_tr[tr_extra]
                tran_agg[tr_extra] = first_tr[tr_extra]
        if len(tran_runs) > 1:
            metrics["tran_runs"] = tran_runs
            tran_agg["tran_runs"] = tran_runs
        metrics_by_analysis["tran"] = tran_agg

    # Process ALL `.noise` / `.pnoise` files with strict per-analysis partitioning & curve separation
    noise_files = psf_files_by_kind.get("noise", [])
    noise_keys = _build_unique_file_keys(noise_files, base_dir=base_dir)
    noise_runs = {}
    pure_noise_runs = {}
    pnoise_runs = {}
    pure_noise_curves = []
    pnoise_curves = []
    has_pnoise = False
    for np_file in noise_files:
        is_pn_file = os.path.basename(np_file).lower().endswith(".pnoise")
        if is_pn_file:
            has_pnoise = True
        np_parsed = parse_psf_file(np_file, reject_nonfinite=True, reject_truncated=True, fill_leading_missing=True)
        _inspect_parsed_evidence(np_parsed, np_file)
        ns_res, curve_info = _extract_noise_metrics(
            np_parsed,
            return_curve=True,
        )
        if ns_res:
            nkey = noise_keys[np_file]
            noise_runs[nkey] = ns_res
            if is_pn_file:
                pnoise_runs[nkey] = ns_res
            else:
                pure_noise_runs[nkey] = ns_res
        if curve_info is not None:
            if is_pn_file:
                pnoise_curves.append(curve_info)
            else:
                pure_noise_curves.append(curve_info)
    if noise_runs:
        _add_analysis("noise")
        if has_pnoise:
            _add_analysis("pnoise")
        ns_agg = _aggregate_noise_group(noise_runs)
        metrics.update(ns_agg)
        for uerr in ns_agg.get("noise_unit_errors") or []:
            all_trace_u_errs.append("noise: %s" % uerr)
        if pure_noise_runs:
            metrics_by_analysis["noise"] = _aggregate_noise_group(pure_noise_runs)
        elif pnoise_runs:
            metrics_by_analysis["noise"] = _aggregate_noise_group(pnoise_runs)
        if pnoise_runs:
            metrics_by_analysis["pnoise"] = _aggregate_noise_group(pnoise_runs)
        if aux_out is not None and (pure_noise_curves or pnoise_curves):
            aux_out["noise_curves"] = pure_noise_curves + pnoise_curves
            nc_by_an = {}
            if pure_noise_curves:
                nc_by_an["noise"] = pure_noise_curves
            elif pnoise_curves:
                nc_by_an["noise"] = pnoise_curves
            if pnoise_curves:
                nc_by_an["pnoise"] = pnoise_curves
            aux_out["noise_curves_by_analysis"] = nc_by_an

    # Process dedicated Monte Carlo PSF analysis files (`mc*.psf`, `mcdata*`, `montecarlo*`)
    # Strict anti-spoofing (Finding #01): never trust filename alone without genuine iteration sweep evidence
    for mc_p in psf_files_by_kind.get("mc", []):
        mc_parsed = parse_psf_file(mc_p, reject_nonfinite=True, reject_truncated=True, fill_leading_missing=True)
        _inspect_parsed_evidence(mc_parsed, mc_p)

    # Check cryptographically bound run metadata JSON (`run_manifest.json` / `cadence_run.json`)
    all_psf_files = []
    for kind_files in psf_files_by_kind.values():
        all_psf_files.extend(kind_files)
    meta_mc, meta_mc_runs, meta_pex, meta_details = _detect_evidence_from_run_metadata(
        all_psf_files, return_details=True
    )
    if meta_mc:
        mc_flag[0] = True
        if meta_mc_runs > mc_runs_box[0]:
            mc_runs_box[0] = meta_mc_runs
    if meta_pex:
        pex_flag[0] = True
    if meta_details.get("manifest_rejected_reason"):
        metrics["manifest_rejected_reason"] = meta_details["manifest_rejected_reason"]

    # Stability proof verification (Finding #01 & Finding #03):
    # Requires typed closed-loop .pz (non-LHP=0) OR (typed open-loop .pz / bound manifest P + closed Nyquist Z=N+P==0)
    cl_valid = [r for r in cl_pz_runs if r.get("pz_parsed_ok")]
    ol_valid = [r for r in ol_pz_runs if r.get("pz_parsed_ok")]
    all_pz_parsed = cl_valid + ol_valid + [r for r in unknown_pz_runs if r.get("pz_parsed_ok")]
    stability_proof_conflicts, cl_all_loops_covered = _check_pz_stb_provenance(
        all_pz_parsed, stb_loops, stb_loop_stems, cl_valid
    )

    closed_loop_unstable = False
    nyquist_unstable = False
    nyquist_proved = False

    if cl_valid:
        tot_cl_poles = sum([r["closed_loop_poles"] for r in cl_valid])
        tot_cl_rhp = sum([r["closed_loop_rhp_poles"] for r in cl_valid])
        tot_cl_jw = sum([r.get("closed_loop_jw_axis_poles", 0) for r in cl_valid])
        tot_cl_non_lhp = tot_cl_rhp + tot_cl_jw
        metrics["closed_loop_poles"] = tot_cl_poles
        metrics["closed_loop_rhp_poles"] = tot_cl_rhp
        metrics["closed_loop_jw_axis_poles"] = tot_cl_jw
        metrics["closed_loop_non_lhp_poles"] = tot_cl_non_lhp
        if tot_cl_non_lhp > 0:
            closed_loop_unstable = True

    bound_ol_rhp = meta_details.get("open_loop_rhp_poles")
    open_loop_p = None
    open_loop_p_conflict = False
    if ol_valid:
        tot_ol_rhp = sum([r["open_loop_rhp_poles"] for r in ol_valid])
        tot_ol_jw = sum([r.get("open_loop_jw_axis_poles", 0) for r in ol_valid])
        open_loop_p = tot_ol_rhp
        metrics["open_loop_rhp_poles"] = open_loop_p
        if tot_ol_jw > 0:
            metrics["open_loop_jw_axis_poles"] = tot_ol_jw
            stability_proof_conflicts.append("open_loop_jw_axis_pole_on_nyquist_contour")
            open_loop_p_conflict = True
        if bound_ol_rhp is not None and bound_ol_rhp != tot_ol_rhp:
            open_loop_p_conflict = True
            stability_proof_conflicts.append("open_loop_p_manifest_mismatch")
    elif bound_ol_rhp is not None:
        open_loop_p = bound_ol_rhp
        metrics["open_loop_rhp_poles"] = open_loop_p

    # Physical law contradiction check: Z = N + P >= N for any closed Nyquist contour.
    if stb_loops and cl_valid and (not closed_loop_unstable):
        for lr in stb_loops.values():
            if lr.get("nyquist_contour_closed") is True and lr.get("nyquist_cw_encirclements") is not None:
                if int(lr["nyquist_cw_encirclements"]) > 0:
                    stability_proof_conflicts.append("nyquist_positive_encirclements_contradicts_lhp_closed_loop_pz")
                    break

    if stb_loops and open_loop_p is not None and (not open_loop_p_conflict):
        if len(stb_loops) == 1:
            lr = stb_loops[list(stb_loops.keys())[0]]
            if lr.get("nyquist_contour_closed") is True and lr.get("nyquist_cw_encirclements") is not None:
                z_val = int(lr["nyquist_cw_encirclements"]) + int(open_loop_p)
                metrics["nyquist_closed_loop_rhp_poles"] = z_val
                if z_val > 0:
                    nyquist_unstable = True
                elif z_val == 0:
                    nyquist_proved = True
        else:
            # Multi-loop: verify each loop individually
            all_loops_proved = True
            ol_by_stem = dict([(r["stem"], r) for r in ol_valid if r.get("stem")])
            max_z = 0
            any_z_checked = False
            for skey, lr in stb_loops.items():
                if lr.get("nyquist_contour_closed") is not True or lr.get("nyquist_cw_encirclements") is None:
                    all_loops_proved = False
                    continue
                loop_p = None
                lstem = stb_loop_stems.get(skey, "")
                if lstem in ol_by_stem:
                    loop_p = ol_by_stem[lstem]["open_loop_rhp_poles"]
                elif bound_ol_rhp is not None:
                    loop_p = bound_ol_rhp
                if loop_p is None:
                    all_loops_proved = False
                    continue
                z_l = int(lr["nyquist_cw_encirclements"]) + int(loop_p)
                any_z_checked = True
                if z_l > max_z:
                    max_z = z_l
                if z_l > 0:
                    nyquist_unstable = True
                    all_loops_proved = False
                elif z_l < 0:
                    all_loops_proved = False
            if any_z_checked:
                metrics["nyquist_closed_loop_rhp_poles"] = max_z
            if all_loops_proved and any_z_checked:
                nyquist_proved = True

    if closed_loop_unstable:
        metrics["closed_loop_unstable"] = True
    if nyquist_unstable:
        metrics["nyquist_unstable"] = True
    if stability_proof_conflicts:
        metrics["stability_proof_conflicts"] = stability_proof_conflicts

    if closed_loop_unstable or nyquist_unstable:
        metrics["stability_proof_verified"] = False
        metrics["stability_proof_method"] = "closed_loop_pz" if closed_loop_unstable else "open_loop_pz_plus_nyquist"
        metrics["bode_measurement_only"] = False
    elif stability_proof_conflicts:
        metrics["stability_proof_verified"] = False
        metrics["stability_proof_method"] = "stability_proof_conflict"
        metrics["bode_measurement_only"] = False
    elif cl_valid and metrics.get("closed_loop_non_lhp_poles") == 0 and cl_all_loops_covered:
        metrics["stability_proof_verified"] = True
        metrics["stability_proof_method"] = "closed_loop_pz"
        metrics["bode_measurement_only"] = False
    elif nyquist_proved:
        metrics["stability_proof_verified"] = True
        metrics["stability_proof_method"] = "open_loop_pz_plus_nyquist"
        metrics["bode_measurement_only"] = False
    elif unknown_pz_runs:
        metrics["stability_proof_verified"] = False
        metrics["stability_proof_method"] = "unknown_pz_mode"
        metrics["bode_measurement_only"] = True
    elif stb_loops or ac_runs or pz_files:
        metrics["stability_proof_verified"] = False
        metrics["stability_proof_method"] = "none_bode_only"
        metrics["bode_measurement_only"] = True

    # PVT metadata resolution & conflict detection (Finding #3)
    resolved_corner = None
    if hdr_corners:
        resolved_corner = hdr_corners[0][1]
        for bn, hc in hdr_corners[1:]:
            if not _corners_match(hc, resolved_corner):
                hdr_conflicts.append(
                    "PSF corner mismatch across files: %s=%s vs %s=%s" % (hdr_corners[0][0], resolved_corner, bn, hc)
                )
    if resolved_corner is None and meta_details.get("manifest_bound"):
        resolved_corner = meta_details.get("corner")
    elif resolved_corner is not None and meta_details.get("manifest_bound") and meta_details.get("corner"):
        if not _corners_match(resolved_corner, meta_details["corner"]):
            hdr_conflicts.append(
                "PSF corner %s disagrees with bound manifest corner %s" % (resolved_corner, meta_details["corner"])
            )

    resolved_temp = None
    if hdr_temps:
        resolved_temp = hdr_temps[0][1]
        for bn, ht in hdr_temps[1:]:
            if abs(ht - resolved_temp) > 0.5:
                hdr_conflicts.append(
                    "PSF temperature mismatch across files: %s=%gC vs %s=%gC" % (hdr_temps[0][0], resolved_temp, bn, ht)
                )
    if resolved_temp is None and meta_details.get("manifest_bound"):
        resolved_temp = meta_details.get("temperature_c")
    elif resolved_temp is not None and meta_details.get("manifest_bound") and meta_details.get("temperature_c") is not None:
        if abs(resolved_temp - meta_details["temperature_c"]) > 0.5:
            hdr_conflicts.append(
                "PSF temperature %gC disagrees with bound manifest temperature %gC" % (resolved_temp, meta_details["temperature_c"])
            )

    metrics["psf_corner"] = resolved_corner
    metrics["psf_temperature_c"] = _round_clean(resolved_temp)
    label_conflicts = _check_point_label_vs_metadata(point_label, metrics)
    all_pvt_conflicts = hdr_conflicts + label_conflicts
    metrics["pvt_metadata_conflict"] = bool(all_pvt_conflicts)
    metrics["pvt_metadata_verified"] = bool(
        (not all_pvt_conflicts) and (resolved_corner is not None) and (resolved_temp is not None)
    )
    if all_pvt_conflicts:
        metrics["pvt_conflict_details"] = all_pvt_conflicts

    if mc_flag[0]:
        _add_analysis("mc")
        metrics["mc_evidence"] = True
        if mc_runs_box[0] > 0:
            metrics["mc_runs_verified"] = mc_runs_box[0]
    else:
        metrics["mc_evidence"] = False

    if pex_flag[0]:
        _add_analysis("pex")
        metrics["pex_evidence"] = True
        if rc_count_box[0] > 0:
            metrics["parasitic_rc_count"] = rc_count_box[0]
    else:
        metrics["pex_evidence"] = False
        if rc_count_box[0] > 0:
            metrics["rc_hint_count"] = rc_count_box[0]

    if metrics_by_analysis:
        metrics["metrics_by_analysis"] = metrics_by_analysis
    if all_trace_u_errs:
        metrics["trace_unit_errors"] = all_trace_u_errs

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
    if (
        low.endswith(".pz")
        or low.endswith(".pz.psf")
        or low == "pz.info"
        or ("pz" in low and (low.endswith(".psf") or (low.endswith(".info") and "op" not in low and "dcop" not in low)))
    ):
        return "pz"
    if low.endswith(".dc") or (low.endswith(".info") and ("op" in low or "dcop" in low)):
        return "dc"
    if (
        re.match(r'^mc[^/]*\.psf$', low)
        or low.startswith("mcdata")
        or low.endswith(".mcdata")
        or low.startswith("montecarlo")
        or low.endswith(".mc")
    ):
        return "mc"
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

    - Non-finite (`NaN`/`Inf`/`-Inf`), `bool`, or non-numeric targets fail closed (`None, 'invalid_target'`).
    - Unknown units fail closed (`None, 'unknown_unit'`).
    - Incompatible unit/metric dimensions (e.g. `mV` on `dc_gain_db`) fail closed (`None, 'unit_dimension_mismatch'`).
    """
    if target_val is None:
        return None, None
    if isinstance(target_val, bool):
        return None, "invalid_target"
    try:
        t_num = float(target_val)
    except (TypeError, ValueError):
        return None, "invalid_target"
    if math.isnan(t_num) or math.isinf(t_num):
        return None, "invalid_target"
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
    scaled = t_num * scale
    if math.isnan(scaled) or math.isinf(scaled):
        return None, "invalid_target"
    return scaled, None


def _compare_op(measured, operator, target_si, target_max_si=None):
    if (
        math.isnan(measured) or math.isinf(measured)
        or math.isnan(target_si) or math.isinf(target_si)
        or (target_max_si is not None and (math.isnan(target_max_si) or math.isinf(target_max_si)))
    ):
        return None
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
        if isinstance(elem, _NUM_TYPES):
            f = float(elem)
            if not (math.isnan(f) or math.isinf(f)):
                out.append(f)
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


def _extract_global_supplies_by_rail(spec_obj):
    """Extract optional per-rail supply sweep expectations `{rail_stem: [v1, ...]}`."""
    if not isinstance(spec_obj, dict):
        return {}
    out = {}
    cov = spec_obj.get("coverage")
    for src in (cov if isinstance(cov, dict) else {}, spec_obj):
        sbr = src.get("supplies_by_rail")
        if isinstance(sbr, dict):
            for rk, rvals in sbr.items():
                rn = _normalize_rail_stem(str(rk))
                if not rn:
                    continue
                vals = _parse_numeric_list(rvals)
                if vals:
                    bucket = out.setdefault(rn, [])
                    for v in vals:
                        if not any([abs(v - x) < 1e-6 for x in bucket]):
                            bucket.append(v)
    return out


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
    if isinstance(mc, _NUM_TYPES) and not isinstance(mc, bool):
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
            if isinstance(mc.get(rk), _NUM_TYPES) and not isinstance(mc.get(rk), bool) and mc[rk] > 0:
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
                elif isinstance(val, _NUM_TYPES) and val > 0:
                    return True
    return False


def _point_rail_voltages(pm):
    rv_map = {}
    rv_raw = pm.get("rail_voltages")
    if isinstance(rv_raw, dict):
        for rk, rval in rv_raw.items():
            if _is_finite_num(rval):
                rn = _normalize_rail_stem(str(rk))
                if rn:
                    rv_map[rn] = float(rval)
    for r in pm.get("supply_rails") or []:
        if isinstance(r, dict) and _is_finite_num(r.get("vdd_v")):
            rn = _normalize_rail_stem(str(r.get("rail") or "vdd"))
            if rn:
                rv_map.setdefault(rn, float(r["vdd_v"]))
    return rv_map


def _match_supply_covered(v_req, points_metrics, rail_name=None):
    """Require real numeric `vdd_v` / primary or named rail metadata (never cross-match secondary rails to flat `supplies_V`)."""
    tol_v = max(0.01, 0.02 * abs(v_req))
    req_rn = _normalize_rail_stem(str(rail_name)) if rail_name is not None else None
    for pt_label, pm in points_metrics.items():
        if not isinstance(pm, dict):
            continue
        rv_map = _point_rail_voltages(pm)
        if req_rn is not None:
            if req_rn in rv_map:
                if abs(rv_map[req_rn] - v_req) <= tol_v:
                    return True
            elif req_rn == "vdd":
                vdd = pm.get("vdd_v")
                if _is_finite_num(vdd) and abs(float(vdd) - v_req) <= tol_v:
                    return True
            continue

        # Flat `supplies_V` check: match explicit primary `vdd` or sole single rail ONLY
        vdd = pm.get("vdd_v")
        if _is_finite_num(vdd):
            if abs(float(vdd) - v_req) <= tol_v:
                return True
            continue
        if "vdd" in rv_map:
            if abs(rv_map["vdd"] - v_req) <= tol_v:
                return True
            continue
        prim = pm.get("primary_supply_rail")
        if prim:
            prim_rn = _normalize_rail_stem(str(prim))
            if prim_rn in rv_map:
                if abs(rv_map[prim_rn] - v_req) <= tol_v:
                    return True
                continue
        if len(rv_map) == 1:
            sole_v = list(rv_map.values())[0]
            if abs(sole_v - v_req) <= tol_v:
                return True
    return False


def _match_temp_covered(t_req, points_metrics):
    """Require real numeric `psf_temperature_c` simulator metadata within 0.5 C (never bare folder labels)."""
    for pt_label, pm in points_metrics.items():
        if not isinstance(pm, dict):
            continue
        t_val = _parse_temp_c(pm.get("psf_temperature_c"))
        if t_val is not None and abs(t_val - float(t_req)) <= 0.5:
            return True
    return False


def _count_mc_points(points_metrics):
    """Count verified Monte Carlo runs/points from genuine MC artifact evidence only (never bare filenames)."""
    cnt = 0
    for pt_label, pm in points_metrics.items():
        if not isinstance(pm, dict):
            continue
        mc_runs = pm.get("mc_runs_verified", 0)
        if isinstance(mc_runs, _INT_TYPES) and not isinstance(mc_runs, bool) and mc_runs > 0:
            cnt += int(mc_runs)
            continue
        if pm.get("mc_evidence") is True or "mc" in pm.get("analyses_present", []):
            cnt += 1
    return cnt


def _has_pex_point(points_metrics):
    """Return True only when at least one point carries genuine post-layout/PEX artifact evidence."""
    for pt_label, pm in points_metrics.items():
        if not isinstance(pm, dict):
            continue
        if pm.get("pex_evidence") is True or "pex" in pm.get("analyses_present", []):
            return True
    return False


def _format_pvt_combo(corner, supply_v, temp_c):
    parts = []
    if corner is not None:
        parts.append(str(corner))
    if supply_v is not None:
        parts.append("%gV" % float(supply_v))
    if temp_c is not None:
        parts.append("%gC" % float(temp_c))
    return " @ ".join(parts)


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
    if isinstance(val, _NUM_TYPES):
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        scale = UNIT_SCALE_TO_SI.get(str(default_unit or "hz").lower(), 1.0)
        return f * scale
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
        if isinstance(item.get(k), _NUM_TYPES) and not isinstance(item.get(k), bool):
            tv = float(item[k])
            break
    tol_r = None
    for k in ("settling_tol_ratio", "settling_tol"):
        v = item.get(k)
        if isinstance(v, _NUM_TYPES) and not isinstance(v, bool) and v > 0:
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
            if isinstance(v, _NUM_TYPES) and not isinstance(v, bool) and v > 0:
                tol_r = float(v) / 100.0
                break
    return tv, tol_r


def _tokenize_condition_label(label):
    """Split condition label on `/`, `_`, whitespace, and non-negative hyphens, preserving `-` attached to digits."""
    return [t for t in re.split(r'[/_\s]+|-(?!\d)', str(label).strip().lower()) if t]


def _match_condition_keys(req_cond, available_keys):
    """Match a required corner/condition label (e.g. `SS`, `TT_27C`, `SS_-40C`) against discovered point keys."""
    rc = str(req_cond).strip()
    rc_low = rc.lower()
    exact = [k for k in available_keys if k == rc or k.lower() == rc_low]
    if exact:
        return sorted(exact)
    rc_tokens = _tokenize_condition_label(rc_low)
    if not rc_tokens:
        return []
    matched = []
    for k in sorted(available_keys):
        k_tokens = set(_tokenize_condition_label(k))
        if all([rt in k_tokens for rt in rc_tokens]):
            matched.append(k)
    return matched


def _point_matches_condition(req_cond, pt_label, pm, conflict_points=None):
    """Match a required corner/condition against simulator PVT metadata (never bare folder labels for PVT)."""
    if not isinstance(pm, dict):
        return False
    if conflict_points and pt_label in conflict_points:
        return False
    if pm.get("pvt_metadata_conflict"):
        return False

    req_corners = _extract_label_corners(req_cond)
    req_temps = _extract_label_temps(req_cond)
    req_volts = _extract_label_voltages(req_cond)

    if req_corners or req_temps or req_volts:
        if req_corners:
            psf_c = pm.get("psf_corner")
            if not psf_c or not all([_corners_match(rc, psf_c) for rc in req_corners]):
                return False
        if req_temps:
            psf_t = _parse_temp_c(pm.get("psf_temperature_c"))
            if psf_t is None or not all([abs(lt - psf_t) <= 0.5 for lt in req_temps]):
                return False
        if req_volts:
            if not all([_match_supply_covered(lv, {pt_label: pm}) for lv in req_volts]):
                return False

        # Verify any additional non-PVT descriptor tokens if present
        non_pvt_tokens = []
        for tok in _tokenize_condition_label(req_cond):
            if _extract_label_corners(tok) or _extract_label_temps(tok) or _extract_label_voltages(tok):
                continue
            non_pvt_tokens.append(tok)
        if non_pvt_tokens:
            pt_tokens = set(_tokenize_condition_label(pt_label))
            if not all([t in pt_tokens for t in non_pvt_tokens]):
                return False
        return True

    return bool(_match_condition_keys(req_cond, [pt_label]))


def _match_condition_points(req_cond, available_keys, points_metrics, conflict_points=None):
    return [
        k for k in available_keys
        if _point_matches_condition(req_cond, k, points_metrics.get(k), conflict_points=conflict_points)
    ]


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
            if isinstance(val, _NUM_TYPES) or isinstance(val, bool):
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
            elif isinstance(val, (list, tuple)) and len(val) == 2:
                reqs.append({
                    "id": "REQ-%02d" % idx,
                    "quantity": key,
                    "operator": "range",
                    "target": val[0],
                    "target_max": val[1],
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


def _has_relevant_unit_error(src_dict, m_dict):
    for key in ("dc_unit_errors", "ac_unit_errors", "stb_unit_errors", "tran_unit_errors", "noise_unit_errors", "trace_unit_errors"):
        if src_dict.get(key):
            return True
    if src_dict is not m_dict and m_dict.get("trace_unit_errors"):
        return True
    return False


def evaluate_spec(points_metrics, spec_obj, aux_data=None):
    approval_pending = _is_spec_approval_pending(spec_obj)
    global_conds = _extract_global_conditions(spec_obj)
    global_analyses = _extract_global_analyses(spec_obj)
    global_supplies = _extract_global_supplies(spec_obj)
    global_supplies_by_rail = _extract_global_supplies_by_rail(spec_obj)
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

    pvt_metadata_conflicts = []
    conflict_points = set()
    for pt_label in available_keys:
        pm = points_metrics.get(pt_label)
        if not isinstance(pm, dict):
            continue
        pt_confs = list(pm.get("pvt_conflict_details") or [])
        for lc in _check_point_label_vs_metadata(pt_label, pm):
            if lc not in pt_confs:
                pt_confs.append(lc)
        if pm.get("pvt_metadata_conflict") or pt_confs:
            conflict_points.add(pt_label)
            pvt_metadata_conflicts.append({
                "point": pt_label,
                "psf_corner": pm.get("psf_corner"),
                "psf_temperature_c": pm.get("psf_temperature_c"),
                "details": pt_confs if pt_confs else ["pvt_metadata_conflict"],
            })

    # Global coverage checks (enforced against simulator metadata, never bare folder names)
    missing_global_corners = []
    for gc in global_conds:
        if not _match_condition_points(gc, available_keys, points_metrics, conflict_points=conflict_points):
            missing_global_corners.append(gc)

    missing_global_analyses = []
    for req_an in global_analyses:
        for pk in available_keys:
            present = points_metrics[pk].get("analyses_present", [])
            if req_an not in present and req_an not in missing_global_analyses:
                missing_global_analyses.append(req_an)

    clean_points_metrics = dict([
        (k, points_metrics[k]) for k in available_keys if k not in conflict_points
    ])
    missing_global_supplies = [v for v in global_supplies if not _match_supply_covered(v, clean_points_metrics)]
    missing_global_supplies_by_rail = {}
    for r_name in sorted(global_supplies_by_rail.keys()):
        miss_rv = [v for v in global_supplies_by_rail[r_name] if not _match_supply_covered(v, clean_points_metrics, rail_name=r_name)]
        if miss_rv:
            missing_global_supplies_by_rail[r_name] = miss_rv
    missing_global_temps = [t for t in global_temps if not _match_temp_covered(t, clean_points_metrics)]

    # Full Cartesian PVT product coverage whenever >= 2 of (corners, supplies, temps) are specified
    missing_pvt_combinations = []
    has_rail_grid = bool(global_supplies_by_rail)
    active_pvt_axes = (1 if global_conds else 0) + (1 if (global_supplies or has_rail_grid) else 0) + (1 if global_temps else 0)
    if active_pvt_axes >= 2:
        c_list = global_conds if global_conds else [None]
        v_list = global_supplies if global_supplies else [None]
        t_list = global_temps if global_temps else [None]
        rail_axes = [(rn, global_supplies_by_rail[rn]) for rn in sorted(global_supplies_by_rail.keys())]
        # Expand flat supply axis AND each rail supply axis against (corner x temp)
        for c_req in c_list:
            for v_req in v_list:
                for t_req in t_list:
                    combo_covered = False
                    for pt_label in available_keys:
                        if pt_label in conflict_points:
                            continue
                        pm = points_metrics[pt_label]
                        if c_req is not None and not _point_matches_condition(c_req, pt_label, pm, conflict_points=conflict_points):
                            continue
                        if v_req is not None and not _match_supply_covered(v_req, {pt_label: pm}):
                            continue
                        if t_req is not None and not _match_temp_covered(t_req, {pt_label: pm}):
                            continue
                        combo_covered = True
                        break
                    if not combo_covered:
                        missing_pvt_combinations.append(_format_pvt_combo(c_req, v_req, t_req))
        for r_name, r_vals in rail_axes:
            for rv in r_vals:
                for c_req in c_list:
                    for t_req in t_list:
                        rc_ok = False
                        for pt_label in available_keys:
                            if pt_label in conflict_points:
                                continue
                            pm = points_metrics[pt_label]
                            if c_req is not None and not _point_matches_condition(c_req, pt_label, pm, conflict_points=conflict_points):
                                continue
                            if not _match_supply_covered(rv, {pt_label: pm}, rail_name=r_name):
                                continue
                            if t_req is not None and not _match_temp_covered(t_req, {pt_label: pm}):
                                continue
                            rc_ok = True
                            break
                        if not rc_ok:
                            lbl_c = _format_pvt_combo(c_req, rv, t_req) + (" [%s]" % r_name.upper())
                            if lbl_c not in missing_pvt_combinations:
                                missing_pvt_combinations.append(lbl_c)

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
                matched_ks = _match_condition_points(rc, available_keys, points_metrics, conflict_points=conflict_points)
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
                matched_ks = _match_condition_points(gc, available_keys, points_metrics, conflict_points=conflict_points)
                if not matched_ks:
                    missing_conds.append(gc)
                    per_cond[gc] = {"measured_si": None, "status": "NOT_VERIFIED", "reason": "missing_condition"}

        worst_cond = None
        worst_val = None
        any_missing = len(missing_conds) > 0
        any_failed = False
        req_reason = "missing_condition" if missing_conds else None
        fail_reason = None

        for cond_name in eval_keys:
            m_dict = points_metrics[cond_name]
            src_dict = m_dict
            if req_an:
                # Strict per-analysis routing: enforce BOTH presence and non-cross-contaminated metrics
                if req_an not in m_dict.get("analyses_present", []):
                    any_missing = True
                    req_reason = req_reason or "missing_analysis"
                    per_cond[cond_name] = {"measured_si": None, "status": "NOT_VERIFIED", "reason": "missing_analysis"}
                    continue
                mba = m_dict.get("metrics_by_analysis")
                if isinstance(mba, dict) and mba:
                    if req_an not in mba:
                        any_missing = True
                        req_reason = req_reason or "missing_analysis"
                        per_cond[cond_name] = {"measured_si": None, "status": "NOT_VERIFIED", "reason": "missing_analysis"}
                        continue
                    src_dict = mba[req_an]

            m_key = _resolve_metric_key(req["quantity"], src_dict)
            m_val = src_dict.get(m_key)

            # Frequency-band strict verification & integration for integrated RMS noise requirements
            if m_key in ("integrated_rms_noise_v", "integrated_rms_noise_a") and (req_fmin is not None or req_fmax is not None):
                req_domain = "voltage" if m_key == "integrated_rms_noise_v" else "current"
                pt_aux = (aux_data or {}).get(cond_name, {}) if isinstance(aux_data, dict) else {}
                nc_by_an = pt_aux.get("noise_curves_by_analysis")
                if req_an and isinstance(nc_by_an, dict) and nc_by_an:
                    cand_curves = nc_by_an.get(req_an, [])
                else:
                    cand_curves = pt_aux.get("noise_curves", [])
                curves = [c for c in cand_curves if c.get("domain") == req_domain]
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
                    f_lo = src_dict.get("noise_freq_min_hz")
                    f_hi = src_dict.get("noise_freq_max_hz")
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
                if req_tv is not None and isinstance(src_dict.get("tran_final_v"), _NUM_TYPES) and not isinstance(src_dict.get("tran_final_v"), bool):
                    v_init_m = src_dict.get("tran_init_v")
                    v_init_f = float(v_init_m) if (isinstance(v_init_m, _NUM_TYPES) and not isinstance(v_init_m, bool)) else 0.0
                    tol_ratio_eff = req_tol_r if req_tol_r is not None else 0.01
                    tol_v = tol_ratio_eff * max(abs(float(req_tv) - v_init_f), 1e-9)
                    if abs(float(src_dict["tran_final_v"]) - float(req_tv)) > tol_v:
                        any_failed = True
                        per_cond[cond_name] = {
                            "measured_si": None,
                            "status": "FAIL",
                            "reason": "static_target_voltage_error",
                            "static_error_v": _round_clean(float(src_dict["tran_final_v"]) - float(req_tv)),
                        }
                        continue
                if m_val is None and isinstance(src_dict.get("static_error_v"), _NUM_TYPES) and not isinstance(src_dict.get("static_error_v"), bool) and abs(float(src_dict["static_error_v"])) > 0.0:
                    any_failed = True
                    per_cond[cond_name] = {
                        "measured_si": None,
                        "status": "FAIL",
                        "reason": "static_target_voltage_error",
                        "static_error_v": _round_clean(src_dict["static_error_v"]),
                    }
                    continue

            if m_key in _STABILITY_METRICS:
                if m_dict.get("closed_loop_unstable"):
                    any_failed = True
                    cl_r = "closed_loop_rhp_pole" if m_dict.get("closed_loop_rhp_poles", 0) > 0 else "closed_loop_jw_axis_pole"
                    fail_reason = fail_reason or cl_r
                    per_cond[cond_name] = {
                        "measured_si": _round_clean(m_val) if m_val is not None else None,
                        "status": "FAIL",
                        "reason": cl_r,
                    }
                    continue
                if m_dict.get("nyquist_unstable"):
                    any_failed = True
                    fail_reason = fail_reason or "nyquist_unstable_encirclements"
                    per_cond[cond_name] = {
                        "measured_si": _round_clean(m_val) if m_val is not None else None,
                        "status": "FAIL",
                        "reason": "nyquist_unstable_encirclements",
                    }
                    continue

            if m_val is None:
                any_missing = True
                if m_key in ("phase_margin_deg", "gain_margin_db") and src_dict.get("rhp_open_loop_pole_suspected"):
                    miss_r = "rhp_open_loop_pole_suspected"
                elif _has_relevant_unit_error(src_dict, m_dict):
                    miss_r = "trace_unit_error"
                else:
                    miss_r = "missing_metric"
                req_reason = req_reason or miss_r
                per_cond[cond_name] = {"measured_si": None, "status": "NOT_VERIFIED", "reason": miss_r}
                continue

            ok_cmp = _compare_op(float(m_val), op, target_si, target_max_si=target_max_si)
            if ok_cmp is None:
                any_missing = True
                req_reason = req_reason or "invalid_operator_or_range"
                per_cond[cond_name] = {"measured_si": _round_clean(m_val), "status": "NOT_VERIFIED", "reason": "invalid_operator_or_range"}
                continue

            if m_key in _STABILITY_METRICS and ok_cmp and (not m_dict.get("stability_proof_verified")):
                any_missing = True
                if m_dict.get("stability_proof_conflicts"):
                    nv_r = "stability_proof_conflict"
                elif m_dict.get("stability_proof_method") == "unknown_pz_mode":
                    nv_r = "unknown_pz_mode"
                else:
                    nv_r = "bode_only_open_loop_rhp_unproven"
                req_reason = req_reason or nv_r
                per_cond[cond_name] = {
                    "measured_si": _round_clean(m_val),
                    "status": "NOT_VERIFIED",
                    "reason": nv_r,
                }
            else:
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
        elif req_status == "FAIL" and fail_reason:
            entry["reason"] = fail_reason
        results.append(entry)

    overall_reason = None
    has_missing_cov = bool(
        missing_global_corners
        or missing_global_analyses
        or missing_global_supplies
        or missing_global_supplies_by_rail
        or missing_global_temps
        or missing_pvt_combinations
        or missing_coverage_flags
    )
    if fail_n > 0:
        verdict = "FAIL"
    elif pvt_metadata_conflicts:
        verdict = "NOT_VERIFIED"
        overall_reason = "pvt_metadata_conflict"
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
    if pvt_metadata_conflicts:
        summary_out["pvt_metadata_conflicts"] = pvt_metadata_conflicts
    if missing_global_corners:
        summary_out["missing_corners"] = missing_global_corners
    if missing_global_analyses:
        summary_out["missing_analyses"] = missing_global_analyses
    if missing_global_supplies:
        summary_out["missing_supplies_V"] = missing_global_supplies
    if missing_global_supplies_by_rail:
        summary_out["missing_supplies_by_rail"] = missing_global_supplies_by_rail
    if missing_global_temps:
        summary_out["missing_temperatures_C"] = missing_global_temps
    if missing_pvt_combinations:
        summary_out["missing_pvt_combinations"] = missing_pvt_combinations
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
            point_label=pt_label,
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
        vals = [pm.get(m_key) for pm in points_metrics.values() if isinstance(pm.get(m_key), _NUM_TYPES) and not isinstance(pm.get(m_key), bool)]
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

        # 17. #3 STB RHP Open-Loop Pole Bode Gain-Phase Slope Guard (L(s)=10/[(1-s/20)(1+s/10)^2] vs valid Buck loop)
        rhp3_dir = os.path.join(tmp_root, "rhp3_stb")
        rhp3_lines = ['HEADER\n"PSFversion" "1.00"\nTYPE\n"f_t" FLOAT DOUBLE\n"c_t" COMPLEX DOUBLE\nSWEEP\n"freq" "f_t"\nTRACE\n"loopGain" "c_t"\nVALUE\n']
        for k_w in range(-6, 19):
            w_val = 10.0 ** (k_w / 6.0)
            s_c = complex(0.0, w_val)
            l_val = 10.0 / ((1.0 - s_c / 20.0) * (1.0 + s_c / 10.0) * (1.0 + s_c / 10.0))
            rhp3_lines.append('"freq" %.6e\n"loopGain" (%.8e %.8e)\n' % (w_val / (2.0 * math.pi), l_val.real, l_val.imag))
        rhp3_lines.append("END\n")
        _write_utf8(os.path.join(rhp3_dir, "stb.stb"), "".join(rhp3_lines))
        res_rhp3 = run_metrics(rhp3_dir)
        assert res_rhp3["metrics"].get("rhp_open_loop_pole_suspected") is True, res_rhp3["metrics"]
        assert res_rhp3["metrics"]["phase_margin_deg"] is None, res_rhp3["metrics"]
        assert "Nyquist" in str(res_rhp3["metrics"].get("stb_notes", "")), res_rhp3["metrics"]

        buck_dir = os.path.join(tmp_root, "buck_stb")
        buck_lines = ['HEADER\n"PSFversion" "1.00"\nTYPE\n"f_t" FLOAT DOUBLE\n"c_t" COMPLEX DOUBLE\nSWEEP\n"freq" "f_t"\nTRACE\n"loopGain" "c_t"\nVALUE\n']
        for k_w in range(-6, 25):
            w_val = 10.0 ** (k_w / 6.0)
            s_c = complex(0.0, w_val)
            l_val = 100.0 * ((1.0 + s_c / 5.0) ** 2) / ((1.0 + s_c / 0.5) * (1.0 + s_c / 100.0 + (s_c / 10.0) ** 2) * (1.0 + s_c / 500.0))
            buck_lines.append('"freq" %.6e\n"loopGain" (%.8e %.8e)\n' % (w_val / (2.0 * math.pi), l_val.real, l_val.imag))
        buck_lines.append("END\n")
        _write_utf8(os.path.join(buck_dir, "stb.stb"), "".join(buck_lines))
        res_buck = run_metrics(buck_dir)
        assert res_buck["metrics"].get("rhp_open_loop_pole_suspected") is not True, res_buck["metrics"]
        assert res_buck["metrics"]["phase_margin_deg"] is not None and res_buck["metrics"]["phase_margin_deg"] > 45.0, res_buck["metrics"]

        # 18. #4 STB Rising 0 dB Crossing Worst Phase Margin (falling PM=65 deg, rising PM=8 deg -> worst <= 10 deg!)
        rise_stb_dir = os.path.join(tmp_root, "rise_stb")
        _write_utf8(os.path.join(rise_stb_dir, "stb.stb"), (
            'HEADER\n"PSFversion" "1.00"\nTYPE\n"f_t" FLOAT DOUBLE\n"c_t" COMPLEX DOUBLE\n'
            'SWEEP\n"freq" "f_t"\nTRACE\n"loopGain" "c_t"\nVALUE\n'
            '"freq" 1.0\n"loopGain" (100.0 0.0)\n'
            '"freq" 1.0e5\n"loopGain" (-0.8452 -1.8126)\n'
            '"freq" 2.0e5\n"loopGain" (-0.2113 -0.4532)\n'
            '"freq" 4.0e5\n"loopGain" (-0.4951 -0.0696)\n'
            '"freq" 6.0e5\n"loopGain" (-1.9805 -0.2783)\n'
            '"freq" 1.0e6\n"loopGain" (-0.3214 -0.3830)\n'
            'END\n'
        ))
        res_rise_stb = run_metrics(rise_stb_dir)
        assert res_rise_stb["metrics"]["phase_margin_deg"] is not None, res_rise_stb["metrics"]
        assert res_rise_stb["metrics"]["phase_margin_deg"] < 12.0, res_rise_stb["metrics"]

        # 19. #5 Split-Supply DC Power (VDD=+1.8V -1mA + VSS=-1.8V +1mA = 3.6mW) + 0V Ammeters Ignored
        split_dir = os.path.join(tmp_root, "split_supply")
        _write_utf8(os.path.join(split_dir, "dcOp.dc"), (
            'HEADER\n"PSFversion" "1.00"\n'
            'TYPE\n"v_t" FLOAT DOUBLE PROP( "units" "V" )\n"i_t" FLOAT DOUBLE PROP( "units" "A" )\n'
            'VALUE\n'
            '"VDD" "v_t" 1.8\n"VDD:p" "i_t" -1.0e-3\n'
            '"VSS" "v_t" -1.8\n"VSS:p" "i_t" 1.0e-3\n'
            '"V_TAIL:p" "i_t" 5.0e-4\n"V_MEAS:p" "i_t" 2.0e-4\nEND\n'
        ))
        res_split = run_metrics(split_dir)
        assert abs(res_split["metrics"]["dc_power_w"] - 0.0036) < 1e-9, res_split["metrics"]
        assert res_split["metrics"]["power_method"] == "multi_rail_supply_terminal", res_split["metrics"]

        gnd_vss_dir = os.path.join(tmp_root, "gnd_vss")
        _write_utf8(os.path.join(gnd_vss_dir, "dcOp.dc"), (
            'HEADER\n"PSFversion" "1.00"\n'
            'TYPE\n"v_t" FLOAT DOUBLE PROP( "units" "V" )\n"i_t" FLOAT DOUBLE PROP( "units" "A" )\n'
            'VALUE\n'
            '"VDD" "v_t" 1.8\n"VDD:p" "i_t" -1.0e-3\n'
            '"VSS" "v_t" 0.0\n"VSS:p" "i_t" 1.0e-3\n'
            '"V_TAIL:p" "i_t" 5.0e-4\nEND\n'
        ))
        res_gvss = run_metrics(gnd_vss_dir)
        assert abs(res_gvss["metrics"]["dc_power_w"] - 0.0018) < 1e-9, res_gvss["metrics"]
        assert res_gvss["metrics"]["power_method"] == "supply_terminal", res_gvss["metrics"]

        # 20. #6 Spec PVT/MC Coverage & Fail-Closed Simulator Metadata Guards
        assert not _match_supply_covered(1.8, {"TT_1p8": {"analyses_present": ["ac"]}}), "Bare 1p8 without unit must not match!"
        assert not _match_supply_covered(1.8, {"TT_1p8V": {"analyses_present": ["ac"]}}), "Bare 1p8V folder label without numeric vdd_v must not match!"
        assert not _match_supply_covered(1.8, {"TT_1p8V": {"vdd_v": 1.0, "analyses_present": ["dc"]}}), "Numeric vdd_v=1.0 must reject 1.8V!"
        assert _match_supply_covered(1.8, {"TT_1p8V": {"vdd_v": 1.8, "analyses_present": ["dc"]}}), "Numeric vdd_v=1.8 should match 1.8V!"
        assert not _match_temp_covered(-40.0, {"SS_-40C": {}}), "Bare SS_-40C label without psf_temperature_c must not match!"
        assert _match_temp_covered(-40.0, {"SS_-40C": {"psf_temperature_c": -40.0}}), "Simulator psf_temperature_c=-40 must match -40C"
        assert not _match_temp_covered(40.0, {"SS_-40C": {"psf_temperature_c": -40.0}}), "SS_-40C must NEVER match +40C!"
        assert not _match_temp_covered(40.0, {"SS_40": {}}), "SS_40 without psf_temperature_c must not match 40C!"
        assert _match_condition_keys("SS_-40C", ["SS_40C"]) == [], "SS_-40C condition must NEVER match SS_40C!"
        assert _match_condition_keys("SS_-40C", ["SS_-40C_1p62V"]) == ["SS_-40C_1p62V"]
        assert _count_mc_points({"iter1": {}, "iter2": {}}) == 0, "Generic iterN must NOT count as Monte Carlo!"
        assert _count_mc_points({"mc1": {}, "monte_carlo_2": {}}) == 0, "Bare filename labels must NOT count as Monte Carlo!"
        assert _count_mc_points({"pt1": {"mc_evidence": True}, "pt2": {"analyses_present": ["mc"]}}) == 2
        assert _count_mc_points({"pt1": {"mc_evidence": True, "mc_runs_verified": 25}}) == 25
        assert not _has_pex_point({"tt_mc1_pex": {}, "av_extracted": {}}), "Bare filename labels must NOT count as PEX!"
        assert _has_pex_point({"pt1": {"pex_evidence": True}})
        assert _has_pex_point({"pt1": {"analyses_present": ["pex"]}})

        # 21. #7 MOS op-audit: Cutoff PMOS with vgs > 0, Unknown Region Code, --expect-triode Missing OP Fields
        pmos_cut_psf = os.path.join(tmp_root, "pmos_cutoff.info")
        _write_utf8(pmos_cut_psf, (
            'HEADER\n"PSFversion" "1.00"\n'
            'TYPE\n"bsim4" STRUCT( "gm" FLOAT DOUBLE "vgs" FLOAT DOUBLE "vth" FLOAT DOUBLE "vds" FLOAT DOUBLE "vdsat" FLOAT DOUBLE "ids" FLOAT DOUBLE )\n'
            'VALUE\n"M3" "bsim4" ( 0.0 0.2 -0.4 -0.5 -0.1 0.0 )\nEND\n'
        ))
        rep_pcut = run_op_audit(pmos_cut_psf)
        assert rep_pcut["status"] == "FAIL" and rep_pcut["audit_pass"] is False, rep_pcut
        assert rep_pcut["devices"]["M3"]["region"] == 0 and rep_pcut["devices"]["M3"]["vov"] < 0.0, rep_pcut

        unk_reg_psf = os.path.join(tmp_root, "unk_reg.info")
        _write_utf8(unk_reg_psf, (
            'HEADER\n"PSFversion" "1.00"\n'
            'TYPE\n"bsim4" STRUCT( "gm" FLOAT DOUBLE "vds" FLOAT DOUBLE "vdsat" FLOAT DOUBLE "ids" FLOAT DOUBLE "region" INT LONG )\n'
            'VALUE\n"M1" "bsim4" ( 1.0e-3 0.5 0.1 1.0e-4 9 )\nEND\n'
        ))
        rep_unkr = run_op_audit(unk_reg_psf)
        assert rep_unkr["status"] == "FAIL" and rep_unkr["audit_pass"] is False, rep_unkr
        assert "M1" in rep_unkr["summary"]["unknown_region"], rep_unkr

        tri_miss_psf = os.path.join(tmp_root, "triode_missing.info")
        _write_utf8(tri_miss_psf, (
            'HEADER\n"PSFversion" "1.00"\n'
            'TYPE\n"bsim4" STRUCT( "gm" FLOAT DOUBLE "vds" FLOAT DOUBLE "ids" FLOAT DOUBLE )\n'
            'VALUE\n"M_SW" "bsim4" ( 1.0e-3 0.05 1.0e-4 )\nEND\n'
        ))
        rep_tmiss = run_op_audit(tri_miss_psf, expect_triode=["M_SW"])
        assert rep_tmiss["status"] == "NOT_VERIFIED" and rep_tmiss["audit_pass"] is False, rep_tmiss
        assert "M_SW" in rep_tmiss["summary"]["missing_op_fields"], rep_tmiss

        # 22. #13 Transient: Adaptive Dense-Tail Settled Step, 3-Pulse Train, and Clipped Step No max_dvdt Fallback
        ad_psf = os.path.join(tmp_root, "adaptive_settled.tran")
        ad_times = [0.0, 0.5e-9, 1.0e-9, 2.0e-9, 5.0e-9] + [8.5e-9 + j * 0.0375e-9 for j in range(41)]
        ad_lines = ['HEADER\n"PSFversion" "1.00"\nTYPE\n"r_t" FLOAT DOUBLE\nSWEEP\n"time" "r_t"\nTRACE\n"Vout" "r_t"\nVALUE\n']
        for t_k in ad_times:
            v_k = 1.0 - math.exp(-t_k / 0.5e-9)
            ad_lines.append('"time" %.6e\n"Vout" %.6e\n' % (t_k, v_k))
        ad_lines.append("END\n")
        _write_utf8(ad_psf, "".join(ad_lines))
        res_ad = run_metrics(ad_psf, settling_tol_ratio=0.01)
        assert res_ad["metrics"]["settling_time_s"] is not None and res_ad["metrics"]["settling_time_s"] < 4.0e-9, res_ad["metrics"]

        mp_tran_psf = os.path.join(tmp_root, "multi_pulse.tran")
        mp_lines = ['HEADER\n"PSFversion" "1.00"\nTYPE\n"r_t" FLOAT DOUBLE\nSWEEP\n"time" "r_t"\nTRACE\n"Vin" "r_t"\n"Vout" "r_t"\nVALUE\n']
        for k in range(311):
            t_k = k * 1.0e-9
            cyc = k % 100
            vin_k = 1.0 if (10 <= cyc < 60) else 0.0
            if k < 10:
                vout_k = 0.0
            elif 10 <= cyc < 60:
                vout_k = 1.0 - math.exp(-((cyc - 10) * 1.0e-9) / 0.4e-9)
            else:
                dt_f = (cyc - 60) * 1.0e-9 if cyc >= 60 else (cyc + 40) * 1.0e-9
                vout_k = math.exp(-dt_f / 0.4e-9)
            mp_lines.append('"time" %.6e\n"Vin" %.6e\n"Vout" %.6e\n' % (t_k, vin_k, vout_k))
        mp_lines.append("END\n")
        _write_utf8(mp_tran_psf, "".join(mp_lines))
        res_mp_tr = run_metrics(mp_tran_psf, settling_tol_ratio=0.01)
        assert res_mp_tr["metrics"]["settling_time_s"] is not None and res_mp_tr["metrics"]["settling_time_s"] < 5.0e-9, res_mp_tr["metrics"]

        clip_psf = os.path.join(tmp_root, "clipped_step.tran")
        clip_lines = ['HEADER\n"PSFversion" "1.00"\nTYPE\n"r_t" FLOAT DOUBLE\nSWEEP\n"time" "r_t"\nTRACE\n"Vout" "r_t"\nVALUE\n']
        for k in range(21):
            t_k = k * 1.0e-9
            v_k = min(0.5, 0.5 * (1.0 - math.exp(-t_k / 1.0e-9)))
            clip_lines.append('"time" %.6e\n"Vout" %.6e\n' % (t_k, v_k))
        clip_lines.append("END\n")
        _write_utf8(clip_psf, "".join(clip_lines))
        res_clip = run_metrics(clip_psf, target_v=1.0)
        assert res_clip["metrics"]["slew_rate_pos"] is None, res_clip["metrics"]

        # 23. #14 AC Descending Sweep & Zero Vin Fail-Closed
        ac_desc_dir = os.path.join(tmp_root, "ac_desc")
        _write_utf8(os.path.join(ac_desc_dir, "ac.ac"), (
            'HEADER\n"PSFversion" "1.00"\nTYPE\n"f_t" FLOAT DOUBLE\n"c_t" COMPLEX DOUBLE\n'
            'SWEEP\n"freq" "f_t"\nTRACE\n"vin" "c_t"\n"vout" "c_t"\nVALUE\n'
            '"freq" 1.0e7\n"vin" (0.1 0.0)\n"vout" (-0.005 -0.005)\n'
            '"freq" 1.0e6\n"vin" (0.1 0.0)\n"vout" (0.0 -0.1)\n'
            '"freq" 1.0\n"vin" (0.1 0.0)\n"vout" (100.0 0.0)\nEND\n'
        ))
        res_ac_desc = run_metrics(ac_desc_dir)
        assert abs(res_ac_desc["metrics"]["dc_gain_db"] - 60.0) < 1e-3, res_ac_desc["metrics"]

        ac_zvin_dir = os.path.join(tmp_root, "ac_zvin")
        _write_utf8(os.path.join(ac_zvin_dir, "ac.ac"), (
            'HEADER\n"PSFversion" "1.00"\nTYPE\n"f_t" FLOAT DOUBLE\n"c_t" COMPLEX DOUBLE\n'
            'SWEEP\n"freq" "f_t"\nTRACE\n"vin" "c_t"\n"vout" "c_t"\nVALUE\n'
            '"freq" 1.0\n"vin" (0.1 0.0)\n"vout" (100.0 0.0)\n'
            '"freq" 1.0e6\n"vin" (0.0 0.0)\n"vout" (0.0 -0.1)\nEND\n'
        ))
        res_ac_zvin = run_metrics(ac_zvin_dir)
        assert res_ac_zvin["metrics"]["dc_gain_db"] is None, res_ac_zvin["metrics"]

        # 24. #15 Noise ASD/PSD SI Prefix Scaling & Zero-Width Band Rejection
        ns_nv_dir = os.path.join(tmp_root, "noise_nv")
        _write_utf8(os.path.join(ns_nv_dir, "noise.noise"), (
            'HEADER\n"PSFversion" "1.00"\n'
            'TYPE\n"f_t" FLOAT DOUBLE PROP( "units" "Hz" )\n"vn_t" FLOAT DOUBLE PROP( "units" "nV/sqrt(Hz)" )\n'
            'SWEEP\n"freq" "f_t"\nTRACE\n"out" "vn_t"\nVALUE\n'
            '"freq" 0.0\n"out" 10.0\n"freq" 100.0\n"out" 10.0\nEND\n'
        ))
        res_ns_nv = run_metrics(ns_nv_dir)
        assert abs(res_ns_nv["metrics"]["integrated_rms_noise_v"] - 1.0e-7) < 1e-12, res_ns_nv["metrics"]

        ns_psd_dir = os.path.join(tmp_root, "noise_nv2")
        _write_utf8(os.path.join(ns_psd_dir, "noise.noise"), (
            'HEADER\n"PSFversion" "1.00"\n'
            'TYPE\n"f_t" FLOAT DOUBLE PROP( "units" "Hz" )\n"vn_t" FLOAT DOUBLE PROP( "units" "nV^2/Hz" )\n'
            'SWEEP\n"freq" "f_t"\nTRACE\n"out" "vn_t"\nVALUE\n'
            '"freq" 0.0\n"out" 100.0\n"freq" 100.0\n"out" 100.0\nEND\n'
        ))
        res_ns_psd = run_metrics(ns_psd_dir)
        assert abs(res_ns_psd["metrics"]["integrated_rms_noise_v"] - 1.0e-7) < 1e-12, res_ns_psd["metrics"]

        spec_zw_path = os.path.join(tmp_root, "spec_zw.json")
        _write_utf8(spec_zw_path, json.dumps({
            "requirements": [{
                "id": "N_ZW", "quantity": "integrated_rms_noise_v", "operator": "<=",
                "target": 10.0, "unit": "uVrms", "band_hz": [50.0, 50.0],
            }]
        }))
        res_zw = run_metrics(ns_nv_dir, spec_path=spec_zw_path)
        assert res_zw["verdict"] == "NOT_VERIFIED", res_zw
        assert res_zw["spec_evaluation"]["results"][0]["reason"] == "invalid_noise_band", res_zw

        # 25. #16 Non-Finite / Bool / Non-Numeric Spec Targets & [min, max] Range in constraints
        for bad_tgt in (float("nan"), float("inf"), float("-inf"), True, False, "not_a_number"):
            ev_bt = evaluate_spec(
                {"TT": {"dc_gain_db": 60.0, "analyses_present": ["ac"]}},
                {"requirements": [{"id": "BT", "quantity": "dc_gain_db", "operator": "<=", "target": bad_tgt, "unit": "dB"}]},
            )
            assert ev_bt["verdict"] == "NOT_VERIFIED", (bad_tgt, ev_bt)
            assert ev_bt["results"][0]["reason"] == "invalid_target", (bad_tgt, ev_bt)

        ev_c_rng_pass = evaluate_spec(
            {"TT": {"dc_gain_db": 60.0, "analyses_present": ["ac"]}},
            {"constraints": [{"id": "CR1", "quantity": "dc_gain_db", "target": [50.0, 70.0], "unit": "dB"}]},
        )
        assert ev_c_rng_pass["verdict"] == "PASS", ev_c_rng_pass
        ev_c_rng_fail = evaluate_spec(
            {"TT": {"dc_gain_db": 75.0, "analyses_present": ["ac"]}},
            {"constraints": [{"id": "CR2", "quantity": "dc_gain_db", "target": [50.0, 70.0], "unit": "dB"}]},
        )
        assert ev_c_rng_fail["verdict"] == "FAIL", ev_c_rng_fail

        # 26. Independent Max Power & Max Supply Current (Sweep + Multi-DC File)
        indep_dir = os.path.join(tmp_root, "dc_indep_sweep")
        _write_utf8(os.path.join(indep_dir, "dcSweep.dc"), (
            'HEADER\n"PSFversion" "1.00"\n'
            'TYPE\n"s_t" FLOAT DOUBLE\n"v_t" FLOAT DOUBLE PROP( "units" "V" )\n"i_t" FLOAT DOUBLE PROP( "units" "A" )\n'
            'SWEEP\n"vdd_sw" "s_t"\nTRACE\n"VDD" "v_t"\n"VDD:p" "i_t"\nVALUE\n'
            '"vdd_sw" 0.0\n"VDD" 1.1\n"VDD:p" -1.0e-3\n'
            '"vdd_sw" 1.0\n"VDD" 0.9\n"VDD:p" -1.2e-3\n'
            'END\n'
        ))
        spec_idd_path = os.path.join(tmp_root, "spec_idd.json")
        _write_utf8(spec_idd_path, json.dumps({
            "requirements": [
                {"id": "P1", "quantity": "dc_power_w", "operator": "<=", "target": 1.2, "unit": "mW"},
                {"id": "I1", "quantity": "idd_a", "operator": "<=", "target": 1.1, "unit": "mA"},
            ]
        }))
        res_indep = run_metrics(indep_dir, spec_path=spec_idd_path)
        assert abs(res_indep["metrics"]["dc_power_w"] - 0.0011) < 1e-9, res_indep["metrics"]
        assert abs(res_indep["metrics"]["idd_a"] - 0.0012) < 1e-9, res_indep["metrics"]
        assert res_indep["metrics"]["max_power_idx"] == 0, res_indep["metrics"]
        assert res_indep["metrics"]["max_idd_idx"] == 1, res_indep["metrics"]
        assert res_indep["verdict"] == "FAIL", res_indep

        indep_mf_dir = os.path.join(tmp_root, "dc_indep_multifile")
        _write_utf8(os.path.join(indep_mf_dir, "dc1.dc"), (
            'HEADER\n"PSFversion" "1.00"\n'
            'TYPE\n"v_t" FLOAT DOUBLE PROP( "units" "V" )\n"i_t" FLOAT DOUBLE PROP( "units" "A" )\n'
            'VALUE\n"VDD" "v_t" 1.1\n"VDD:p" "i_t" -1.0e-3\nEND\n'
        ))
        _write_utf8(os.path.join(indep_mf_dir, "dc2.dc"), (
            'HEADER\n"PSFversion" "1.00"\n'
            'TYPE\n"v_t" FLOAT DOUBLE PROP( "units" "V" )\n"i_t" FLOAT DOUBLE PROP( "units" "A" )\n'
            'VALUE\n"VDD" "v_t" 0.9\n"VDD:p" "i_t" -1.2e-3\nEND\n'
        ))
        res_indep_mf = run_metrics(indep_mf_dir, spec_path=spec_idd_path)
        assert abs(res_indep_mf["metrics"]["dc_power_w"] - 0.0011) < 1e-9, res_indep_mf["metrics"]
        assert abs(res_indep_mf["metrics"]["idd_a"] - 0.0012) < 1e-9, res_indep_mf["metrics"]
        assert res_indep_mf["verdict"] == "FAIL", res_indep_mf

        # 27. Full Cartesian PVT Product Coverage (2x2x2 with only diagonal 2 points -> 6 missing combos -> NOT_VERIFIED)
        pvt_spec = {
            "coverage": {
                "corners": ["TT", "SS"],
                "supplies_V": [0.90, 1.10],
                "temperatures_C": [-40, 125],
            },
            "requirements": [{"id": "G1", "quantity": "dc_gain_db", "operator": ">=", "target": 50.0, "unit": "dB"}],
        }
        ev_pvt_sparse = evaluate_spec(
            {
                "TT_0p90V_-40C": {"dc_gain_db": 60.0, "vdd_v": 0.90, "psf_corner": "TT", "psf_temperature_c": -40.0, "analyses_present": ["ac"]},
                "SS_1p10V_125C": {"dc_gain_db": 58.0, "vdd_v": 1.10, "psf_corner": "SS", "psf_temperature_c": 125.0, "analyses_present": ["ac"]},
            },
            pvt_spec,
        )
        assert ev_pvt_sparse["verdict"] == "NOT_VERIFIED", ev_pvt_sparse
        assert not ev_pvt_sparse.get("missing_corners"), ev_pvt_sparse
        assert not ev_pvt_sparse.get("missing_supplies_V"), ev_pvt_sparse
        assert not ev_pvt_sparse.get("missing_temperatures_C"), ev_pvt_sparse
        assert len(ev_pvt_sparse.get("missing_pvt_combinations", [])) == 6, ev_pvt_sparse
        assert "TT @ 1.1V @ 125C" in ev_pvt_sparse["missing_pvt_combinations"], ev_pvt_sparse

        full_pvt_no_hdr = {}
        full_pvt_pts = {}
        for c_k in ("TT", "SS"):
            for v_k, v_lbl in ((0.90, "0p90V"), (1.10, "1p10V")):
                for t_k, t_lbl in ((-40, "-40C"), (125, "125C")):
                    lbl_k = "%s_%s_%s" % (c_k, v_lbl, t_lbl)
                    full_pvt_no_hdr[lbl_k] = {
                        "dc_gain_db": 60.0,
                        "vdd_v": v_k,
                        "analyses_present": ["ac"],
                    }
                    full_pvt_pts[lbl_k] = {
                        "dc_gain_db": 60.0,
                        "vdd_v": v_k,
                        "psf_corner": c_k,
                        "psf_temperature_c": float(t_k),
                        "analyses_present": ["ac"],
                    }
        ev_pvt_no_hdr = evaluate_spec(full_pvt_no_hdr, pvt_spec)
        assert ev_pvt_no_hdr["verdict"] == "NOT_VERIFIED", ev_pvt_no_hdr
        assert ev_pvt_no_hdr.get("missing_corners") == ["TT", "SS"], ev_pvt_no_hdr
        ev_pvt_full = evaluate_spec(full_pvt_pts, pvt_spec)
        assert ev_pvt_full["verdict"] == "PASS", ev_pvt_full
        assert "missing_pvt_combinations" not in ev_pvt_full, ev_pvt_full

        # 28. Genuine MC & PEX Evidence + Cryptographically Bound Manifest Anti-Spoofing (Finding #2)
        spoof_dir = os.path.join(tmp_root, "spoof_mc_pex")
        for s_name in ("tt_mc1_pex", "tt_mc2_pex"):
            _write_utf8(os.path.join(spoof_dir, s_name, "dcOp.dc"), (
                'HEADER\n"PSFversion" "1.00"\n'
                'TYPE\n"v_t" FLOAT DOUBLE PROP( "units" "V" )\n"i_t" FLOAT DOUBLE PROP( "units" "A" )\n'
                'VALUE\n"VDD" "v_t" 1.0\n"VDD:p" "i_t" -1.0e-4\nEND\n'
            ))
        spec_mc_pex_path = os.path.join(tmp_root, "spec_mc_pex.json")
        _write_utf8(spec_mc_pex_path, json.dumps({
            "coverage": {"monte_carlo": 2, "post_layout": True},
            "requirements": [{"id": "P_MC", "quantity": "dc_power_w", "operator": "<=", "target": 1.0, "unit": "mW"}],
        }))
        res_spoof = run_metrics(spoof_dir, spec_path=spec_mc_pex_path)
        assert res_spoof["verdict"] == "NOT_VERIFIED", res_spoof
        assert _count_mc_points(res_spoof["points"]) == 0, res_spoof["points"]
        assert res_spoof["points"]["tt_mc1_pex"]["pex_evidence"] is False, res_spoof["points"]
        assert res_spoof["points"]["tt_mc2_pex"]["pex_evidence"] is False, res_spoof["points"]
        assert "monte_carlo" in res_spoof["spec_evaluation"].get("missing_coverage", []), res_spoof
        assert "post_layout" in res_spoof["spec_evaluation"].get("missing_coverage", []), res_spoof

        # Genuine MC (iteration sweep + header) & Genuine PEX (av_extracted header + parasitic RC)
        real_mc_pex_dir = os.path.join(tmp_root, "real_mc_pex")
        _write_utf8(os.path.join(real_mc_pex_dir, "dcOp.dc"), (
            'HEADER\n"PSFversion" "1.00"\n"analysis type" "montecarlo"\n"cellview" "av_extracted"\n'
            'TYPE\n"i_sw" INT LONG\n"v_t" FLOAT DOUBLE PROP( "units" "V" )\n"i_t" FLOAT DOUBLE PROP( "units" "A" )\n'
            'SWEEP\n"iteration" "i_sw"\nTRACE\n"VDD" "v_t"\n"VDD:p" "i_t"\n"cpar_out:i" "i_t"\nVALUE\n'
            '"iteration" 1\n"VDD" 1.0\n"VDD:p" -1.0e-4\n"cpar_out:i" 1.0e-9\n'
            '"iteration" 2\n"VDD" 1.0\n"VDD:p" -1.1e-4\n"cpar_out:i" 1.1e-9\n'
            '"iteration" 3\n"VDD" 1.0\n"VDD:p" -1.2e-4\n"cpar_out:i" 1.2e-9\n'
            'END\n'
        ))
        res_real_mp = run_metrics(real_mc_pex_dir, spec_path=spec_mc_pex_path)
        assert res_real_mp["verdict"] == "PASS", res_real_mp
        assert res_real_mp["metrics"]["mc_evidence"] is True, res_real_mp["metrics"]
        assert res_real_mp["metrics"]["mc_runs_verified"] == 3, res_real_mp["metrics"]
        assert res_real_mp["metrics"]["pex_evidence"] is True, res_real_mp["metrics"]
        assert res_real_mp["metrics"]["parasitic_rc_count"] >= 1, res_real_mp["metrics"]

        # Loose unbacked run_manifest.json MUST fail closed (Finding #2 Codex repro)
        meta_mc_pex_dir = os.path.join(tmp_root, "meta_mc_pex")
        _write_utf8(os.path.join(meta_mc_pex_dir, "psf", "dcOp.dc"), (
            'HEADER\n"PSFversion" "1.00"\n'
            'TYPE\n"v_t" FLOAT DOUBLE PROP( "units" "V" )\n"i_t" FLOAT DOUBLE PROP( "units" "A" )\n'
            'VALUE\n"VDD" "v_t" 1.0\n"VDD:p" "i_t" -1.0e-4\nEND\n'
        ))
        _write_utf8(os.path.join(meta_mc_pex_dir, "run_manifest.json"), json.dumps({
            "monte_carlo": True,
            "mc_runs": 50,
            "pex_verified": True,
        }))
        res_meta_mp = run_metrics(meta_mc_pex_dir, spec_path=spec_mc_pex_path)
        assert res_meta_mp["verdict"] == "NOT_VERIFIED", res_meta_mp
        assert res_meta_mp["metrics"]["mc_evidence"] is False, res_meta_mp["metrics"]
        assert res_meta_mp["metrics"]["pex_evidence"] is False, res_meta_mp["metrics"]
        assert res_meta_mp["metrics"].get("manifest_rejected_reason"), res_meta_mp["metrics"]
        assert main(["metrics", meta_mc_pex_dir, "--spec", spec_mc_pex_path, "--fail-on-spec"], quiet=True) == 1

        # Bound manifest claiming mc_runs=50 next to single non-MC dcOp.dc MUST STILL ignore mc_runs=50!
        bound_unbacked_dir = os.path.join(tmp_root, "bound_unbacked_mc")
        bu_net = os.path.join(bound_unbacked_dir, "tb.scs")
        bu_dc = os.path.join(bound_unbacked_dir, "psf", "dcOp.dc")
        _write_utf8(bu_net, "simulator lang=spectre\nmc1 montecarlo numruns=50 {\n dcOp dc\n}\n")
        _write_utf8(bu_dc, (
            'HEADER\n"PSFversion" "1.00"\n'
            'TYPE\n"v_t" FLOAT DOUBLE PROP( "units" "V" )\n"i_t" FLOAT DOUBLE PROP( "units" "A" )\n'
            'VALUE\n"VDD" "v_t" 1.0\n"VDD:p" "i_t" -1.0e-4\nEND\n'
        ))
        _write_utf8(os.path.join(bound_unbacked_dir, "run_manifest.json"), json.dumps({
            "schema": "skill-analog.run-manifest.v1",
            "run_id": "run_unbacked_50",
            "exit_code": 0,
            "netlist_path": "tb.scs",
            "netlist_sha256": _sha256_file(bu_net),
            "psf_files": {"psf/dcOp.dc": _sha256_file(bu_dc)},
            "monte_carlo": True,
            "mc_runs": 50,
            "pex_verified": True,
        }))
        res_bu = run_metrics(bound_unbacked_dir, spec_path=spec_mc_pex_path)
        assert res_bu["verdict"] == "NOT_VERIFIED", res_bu
        assert res_bu["metrics"]["mc_evidence"] is False, res_bu["metrics"]
        assert res_bu["metrics"]["pex_evidence"] is False, res_bu["metrics"]

        # Positive bound manifest with real netlist (montecarlo + av_extracted/cpar_out) & verified MC PSF files PASSES
        bound_ok_dir = os.path.join(tmp_root, "bound_ok_mc_pex")
        bok_net = os.path.join(bound_ok_dir, "tb.scs")
        bok_mc1 = os.path.join(bound_ok_dir, "psf", "mc1_001.dc")
        bok_mc2 = os.path.join(bound_ok_dir, "psf", "mc1_002.dc")
        _write_utf8(bok_net, (
            "// View name: av_extracted\n"
            "simulator lang=spectre\n"
            "cpar_out (vout 0) capacitor c=5f\n"
            "mc1 montecarlo numruns=2 {\n dcOp dc\n}\n"
        ))
        for mc_idx, mc_fp in enumerate((bok_mc1, bok_mc2), 1):
            _write_utf8(mc_fp, (
                'HEADER\n"PSFversion" "1.00"\n'
                'TYPE\n"v_t" FLOAT DOUBLE PROP( "units" "V" )\n"i_t" FLOAT DOUBLE PROP( "units" "A" )\n'
                'VALUE\n"VDD" "v_t" 1.0\n"VDD:p" "i_t" %.6e\nEND\n' % (-1.0e-4 * mc_idx)
            ))
        _write_utf8(os.path.join(bound_ok_dir, "run_manifest.json"), json.dumps({
            "schema": "skill-analog.run-manifest.v1",
            "run_id": "run_bound_ok_1",
            "exit_code": 0,
            "netlist_path": "tb.scs",
            "netlist_sha256": _sha256_file(bok_net),
            "psf_files": {
                "psf/mc1_001.dc": _sha256_file(bok_mc1),
                "psf/mc1_002.dc": _sha256_file(bok_mc2),
            },
            "monte_carlo": {"enabled": True, "mc_psf_files": ["psf/mc1_001.dc", "psf/mc1_002.dc"]},
            "post_layout": {"enabled": True},
        }))
        res_bok = run_metrics(bound_ok_dir, spec_path=spec_mc_pex_path)
        assert res_bok["verdict"] == "PASS", res_bok
        assert res_bok["metrics"]["mc_evidence"] is True, res_bok["metrics"]
        assert res_bok["metrics"]["mc_runs_verified"] == 2, res_bok["metrics"]
        assert res_bok["metrics"]["pex_evidence"] is True, res_bok["metrics"]
        assert main(["metrics", bound_ok_dir, "--spec", spec_mc_pex_path, "--fail-on-spec"], quiet=True) == 0

        # 29. Codex STB RHP Pole-Zero Pair Repro + .pz / Nyquist Fail-Closed Proof (Finding #1)
        # L(s) = 10(s - 1010) / [(s + 1)(s - 1000)] over w = 10^-3 .. 10^5 rad/s (321 pts)
        codex_stb_lines = ['HEADER\n"PSFversion" "1.00"\nTYPE\n"f_t" FLOAT DOUBLE\n"c_t" COMPLEX DOUBLE\nSWEEP\n"freq" "f_t"\nTRACE\n"loopGain" "c_t"\nVALUE\n']
        for k_i in range(321):
            w_val = 10.0 ** (-3.0 + 8.0 * float(k_i) / 320.0)
            s_c = complex(0.0, w_val)
            l_val = 10.0 * (s_c - 1010.0) / ((s_c + 1.0) * (s_c - 1000.0))
            codex_stb_lines.append('"freq" %.8e\n"loopGain" (%.10e %.10e)\n' % (w_val / (2.0 * math.pi), l_val.real, l_val.imag))
        codex_stb_lines.append("END\n")
        codex_stb_txt = "".join(codex_stb_lines)

        spec_stb_pm_path = os.path.join(tmp_root, "spec_stb_pm.json")
        _write_utf8(spec_stb_pm_path, json.dumps({
            "requirements": [{"id": "PM_STB", "quantity": "phase_margin_deg", "operator": ">=", "target": 45.0, "unit": "deg"}]
        }))

        # 29a. Bode-only Codex repro (no .pz): preserves PM ~95.69 as measurement, verdict=NOT_VERIFIED, rc=1
        codex_bode_dir = os.path.join(tmp_root, "codex_stb_bode_only")
        _write_utf8(os.path.join(codex_bode_dir, "stb.stb"), codex_stb_txt)
        res_cbode = run_metrics(codex_bode_dir, spec_path=spec_stb_pm_path)
        assert abs(res_cbode["metrics"]["phase_margin_deg"] - 95.6886) < 0.05, res_cbode["metrics"]
        assert res_cbode["metrics"]["stability_proof_verified"] is False, res_cbode["metrics"]
        assert res_cbode["metrics"]["stability_proof_method"] == "none_bode_only", res_cbode["metrics"]
        assert res_cbode["metrics"]["bode_measurement_only"] is True, res_cbode["metrics"]
        assert res_cbode["metrics"]["nyquist_contour_closed"] is True, res_cbode["metrics"]
        assert res_cbode["metrics"]["nyquist_cw_encirclements"] == 0, res_cbode["metrics"]
        assert res_cbode["verdict"] == "NOT_VERIFIED", res_cbode
        cb_cond = res_cbode["spec_evaluation"]["results"][0]["conditions"]["nominal"]
        assert cb_cond["status"] == "NOT_VERIFIED", cb_cond
        assert cb_cond["reason"] == "bode_only_open_loop_rhp_unproven", cb_cond
        assert abs(cb_cond["measured_si"] - 95.6886) < 0.05, cb_cond
        assert main(["metrics", codex_bode_dir, "--spec", spec_stb_pm_path, "--fail-on-spec"], quiet=True) == 1

        # 29b. Closed-loop .pz with RHP pole (+1000.0989 s^-1) -> FAIL (closed_loop_rhp_pole)
        codex_clpz_dir = os.path.join(tmp_root, "codex_cl_pz_fail")
        _write_utf8(os.path.join(codex_clpz_dir, "stb.stb"), codex_stb_txt)
        _write_utf8(os.path.join(codex_clpz_dir, "pz.pz"), (
            'HEADER\n"PSFversion" "1.00"\n"analysis type" "pz"\n"pz_mode" "closed_loop"\nTYPE\n"c_t" COMPLEX DOUBLE\nVALUE\n'
            '"pole1" "c_t" (-11.0989 0.0)\n'
            '"pole2" "c_t" (1000.0989 0.0)\n'
            '"zero1" "c_t" (1010.0 0.0)\nEND\n'
        ))
        res_clpz = run_metrics(codex_clpz_dir, spec_path=spec_stb_pm_path)
        assert res_clpz["metrics"]["closed_loop_rhp_poles"] == 1, res_clpz["metrics"]
        assert res_clpz["metrics"]["closed_loop_unstable"] is True, res_clpz["metrics"]
        assert res_clpz["verdict"] == "FAIL", res_clpz
        assert res_clpz["spec_evaluation"]["results"][0]["conditions"]["nominal"]["reason"] == "closed_loop_rhp_pole", res_clpz
        assert main(["metrics", codex_clpz_dir, "--spec", spec_stb_pm_path, "--fail-on-spec"], quiet=True) == 1

        # 29c. Open-loop .pz (P=1) + Nyquist (N=0) -> Z = N + P = 1 > 0 -> FAIL (nyquist_unstable_encirclements)
        codex_olpz_dir = os.path.join(tmp_root, "codex_ol_pz_fail")
        _write_utf8(os.path.join(codex_olpz_dir, "stb.stb"), codex_stb_txt)
        _write_utf8(os.path.join(codex_olpz_dir, "open_loop.pz.psf"), (
            'HEADER\n"PSFversion" "1.00"\nTYPE\n"c_t" COMPLEX DOUBLE\nVALUE\n'
            '"pole1" "c_t" (-1.0 0.0)\n'
            '"pole2" "c_t" (1000.0 0.0)\n'
            '"zero1" "c_t" (1010.0 0.0)\nEND\n'
        ))
        res_olpz = run_metrics(codex_olpz_dir, spec_path=spec_stb_pm_path)
        assert res_olpz["metrics"]["open_loop_rhp_poles"] == 1, res_olpz["metrics"]
        assert res_olpz["metrics"]["nyquist_closed_loop_rhp_poles"] == 1, res_olpz["metrics"]
        assert res_olpz["metrics"]["nyquist_unstable"] is True, res_olpz["metrics"]
        assert res_olpz["verdict"] == "FAIL", res_olpz
        assert res_olpz["spec_evaluation"]["results"][0]["conditions"]["nominal"]["reason"] == "nyquist_unstable_encirclements", res_olpz
        assert main(["metrics", codex_olpz_dir, "--spec", spec_stb_pm_path, "--fail-on-spec"], quiet=True) == 1

        # 29d. Valid stable loop + closed-loop .pz (LHP poles only, plus RHP zero ignored) -> PASS
        good_stb_lines = ['HEADER\n"PSFversion" "1.00"\nTYPE\n"f_t" FLOAT DOUBLE\n"c_t" COMPLEX DOUBLE\nSWEEP\n"freq" "f_t"\nTRACE\n"loopGain" "c_t"\nVALUE\n']
        for k_i in range(101):
            w_val = 10.0 ** (-1.0 + 6.0 * float(k_i) / 100.0)
            s_c = complex(0.0, w_val)
            l_val = 100.0 / ((1.0 + s_c / 10.0) * (1.0 + s_c / 1000.0))
            good_stb_lines.append('"freq" %.8e\n"loopGain" (%.10e %.10e)\n' % (w_val / (2.0 * math.pi), l_val.real, l_val.imag))
        good_stb_lines.append("END\n")
        good_stb_txt = "".join(good_stb_lines)

        valid_cl_dir = os.path.join(tmp_root, "valid_cl_pz")
        _write_utf8(os.path.join(valid_cl_dir, "stb.stb"), good_stb_txt)
        _write_utf8(os.path.join(valid_cl_dir, "pz.info"), (
            'HEADER\n"PSFversion" "1.00"\n"pz_mode" "closed_loop"\nTYPE\n"pz_t" STRUCT( "real" FLOAT DOUBLE "imag" FLOAT DOUBLE )\nVALUE\n'
            '"pole1" "pz_t" ( -505.0 870.0 )\n'
            '"pole2" "pz_t" ( -505.0 -870.0 )\n'
            '"zero1" "pz_t" ( 5000.0 0.0 )\nEND\n'
        ))
        res_vcl = run_metrics(valid_cl_dir, spec_path=spec_stb_pm_path)
        assert res_vcl["metrics"]["closed_loop_rhp_poles"] == 0, res_vcl["metrics"]
        assert res_vcl["metrics"]["stability_proof_verified"] is True, res_vcl["metrics"]
        assert res_vcl["metrics"]["stability_proof_method"] == "closed_loop_pz", res_vcl["metrics"]
        assert res_vcl["verdict"] == "PASS", res_vcl
        assert main(["metrics", valid_cl_dir, "--spec", spec_stb_pm_path, "--fail-on-spec"], quiet=True) == 0

        # 29e. Valid stable loop + open-loop .pz (P=0) + closed Nyquist (N=0) -> PASS
        valid_ol_dir = os.path.join(tmp_root, "valid_ol_pz")
        _write_utf8(os.path.join(valid_ol_dir, "stb.stb"), good_stb_txt)
        _write_utf8(os.path.join(valid_ol_dir, "openloop.pz"), (
            'HEADER\n"PSFversion" "1.00"\nTYPE\n"c_t" COMPLEX DOUBLE\nVALUE\n'
            '"pole1" "c_t" (-10.0 0.0)\n'
            '"pole2" "c_t" (-1000.0 0.0)\nEND\n'
        ))
        res_vol = run_metrics(valid_ol_dir, spec_path=spec_stb_pm_path)
        assert res_vol["metrics"]["open_loop_rhp_poles"] == 0, res_vol["metrics"]
        assert res_vol["metrics"]["nyquist_closed_loop_rhp_poles"] == 0, res_vol["metrics"]
        assert res_vol["metrics"]["stability_proof_verified"] is True, res_vol["metrics"]
        assert res_vol["metrics"]["stability_proof_method"] == "open_loop_pz_plus_nyquist", res_vol["metrics"]
        assert res_vol["verdict"] == "PASS", res_vol

        # 29f. Bound manifest open_loop_rhp_poles=0 + closed Nyquist -> PASS; unclosed Nyquist -> NOT_VERIFIED
        bound_nyq_dir = os.path.join(tmp_root, "bound_nyq_pass")
        bnyq_net = os.path.join(bound_nyq_dir, "tb.scs")
        bnyq_stb = os.path.join(bound_nyq_dir, "psf", "stb.stb")
        _write_utf8(bnyq_net, "simulator lang=spectre\nstb1 stb\n")
        _write_utf8(bnyq_stb, good_stb_txt)
        _write_utf8(os.path.join(bound_nyq_dir, "run_manifest.json"), json.dumps({
            "schema": "skill-analog.run-manifest.v1",
            "run_id": "nyq_bound_1",
            "exit_code": 0,
            "netlist_path": "tb.scs",
            "netlist_sha256": _sha256_file(bnyq_net),
            "psf_files": {"psf/stb.stb": _sha256_file(bnyq_stb)},
            "open_loop_rhp_poles": 0,
        }))
        res_bnyq = run_metrics(bound_nyq_dir, spec_path=spec_stb_pm_path)
        assert res_bnyq["metrics"]["stability_proof_verified"] is True, res_bnyq["metrics"]
        assert res_bnyq["verdict"] == "PASS", res_bnyq

        unclosed_nyq_dir = os.path.join(tmp_root, "unclosed_nyq")
        _write_utf8(os.path.join(unclosed_nyq_dir, "stb.stb"), (
            'HEADER\n"PSFversion" "1.00"\nTYPE\n"f_t" FLOAT DOUBLE\n"c_t" COMPLEX DOUBLE\n'
            'SWEEP\n"freq" "f_t"\nTRACE\n"loopGain" "c_t"\nVALUE\n'
            '"freq" 1.0e5\n"loopGain" (1.5 -1.5)\n'
            '"freq" 2.0e5\n"loopGain" (0.5 -1.0)\n'
            '"freq" 3.0e5\n"loopGain" (0.2 -0.8)\nEND\n'
        ))
        _write_utf8(os.path.join(unclosed_nyq_dir, "open_loop.pz"), (
            'HEADER\n"PSFversion" "1.00"\nTYPE\n"c_t" COMPLEX DOUBLE\nVALUE\n"pole1" "c_t" (-10.0 0.0)\nEND\n'
        ))
        res_unc = run_metrics(unclosed_nyq_dir, spec_path=spec_stb_pm_path)
        assert res_unc["metrics"]["nyquist_contour_closed"] is False, res_unc["metrics"]
        assert res_unc["metrics"]["stability_proof_verified"] is False, res_unc["metrics"]
        assert res_unc["verdict"] == "NOT_VERIFIED", res_unc

        # 30. Codex 8-Folder PVT Spoofing Repro + Missing Header + Internal Conflict + Genuine Matching Headers (Finding #3)
        pvt_spec_path = os.path.join(tmp_root, "spec_pvt_8.json")
        _write_utf8(pvt_spec_path, json.dumps(pvt_spec))

        def _write_pvt_point(pt_dir, vdd_val, hdr_corner=None, hdr_temp=None, extra_hdr=""):
            hdr_lines = ['HEADER\n"PSFversion" "1.00"\n']
            if hdr_corner is not None:
                hdr_lines.append('"corner" "%s"\n' % hdr_corner)
            if hdr_temp is not None:
                hdr_lines.append('"temperature" %s\n' % repr(hdr_temp))
            if extra_hdr:
                hdr_lines.append(extra_hdr)
            hdr_str = "".join(hdr_lines)
            _write_utf8(os.path.join(pt_dir, "dcOp.dc"), (
                hdr_str +
                'TYPE\n"v_t" FLOAT DOUBLE PROP( "units" "V" )\n"i_t" FLOAT DOUBLE PROP( "units" "A" )\n'
                'VALUE\n"VDD" "v_t" %.4f\n"VDD:p" "i_t" -1.0e-4\nEND\n' % vdd_val
            ))
            _write_utf8(os.path.join(pt_dir, "ac.ac"), (
                hdr_str +
                'TYPE\n"f_t" FLOAT DOUBLE\n"c_t" COMPLEX DOUBLE\nSWEEP\n"freq" "f_t"\nTRACE\n"Vout" "c_t"\nVALUE\n'
                '"freq" 1.0\n"Vout" (1000.0 0.0)\n"freq" 1.0e6\n"Vout" (0.0 -1.0)\nEND\n'
            ))

        # 30a. Codex 8-folder spoofing repro: all 8 folders claim TT/SS x 0.9/1.1V x -40/125C, but HEADER says TT, 27
        spoof_8_dir = os.path.join(tmp_root, "pvt_spoof_8")
        for c_k in ("TT", "SS"):
            for v_k, v_lbl in ((0.90, "0p90V"), (1.10, "1p10V")):
                for t_k, t_lbl in ((-40, "-40C"), (125, "125C")):
                    _write_pvt_point(os.path.join(spoof_8_dir, "%s_%s_%s" % (c_k, v_lbl, t_lbl)), v_k, "TT", 27)
        res_sp8 = run_metrics(spoof_8_dir, spec_path=pvt_spec_path)
        assert res_sp8["verdict"] == "NOT_VERIFIED", res_sp8
        assert res_sp8["spec_evaluation"].get("reason") == "pvt_metadata_conflict", res_sp8["spec_evaluation"]
        assert len(res_sp8["spec_evaluation"].get("pvt_metadata_conflicts", [])) == 8, res_sp8["spec_evaluation"]
        assert main(["metrics", spoof_8_dir, "--spec", pvt_spec_path, "--fail-on-spec"], quiet=True) == 1

        # 30b. Missing-header 8-folder repro (no corner/temperature in HEADER) -> NOT_VERIFIED
        nohdr_8_dir = os.path.join(tmp_root, "pvt_nohdr_8")
        for c_k in ("TT", "SS"):
            for v_k, v_lbl in ((0.90, "0p90V"), (1.10, "1p10V")):
                for t_k, t_lbl in ((-40, "-40C"), (125, "125C")):
                    _write_pvt_point(os.path.join(nohdr_8_dir, "%s_%s_%s" % (c_k, v_lbl, t_lbl)), v_k, None, None)
        res_nh8 = run_metrics(nohdr_8_dir, spec_path=pvt_spec_path)
        assert res_nh8["verdict"] == "NOT_VERIFIED", res_nh8
        assert res_nh8["spec_evaluation"].get("missing_corners") == ["TT", "SS"], res_nh8["spec_evaluation"]
        assert res_nh8["spec_evaluation"].get("missing_temperatures_C") == [-40.0, 125.0], res_nh8["spec_evaluation"]
        assert len(res_nh8["spec_evaluation"].get("missing_pvt_combinations", [])) == 8, res_nh8["spec_evaluation"]
        assert main(["metrics", nohdr_8_dir, "--spec", pvt_spec_path, "--fail-on-spec"], quiet=True) == 1

        # 30c. Internal multi-PSF header conflict inside single point (dcOp=TT/27C vs ac=SS/125C)
        int_conf_dir = os.path.join(tmp_root, "pvt_internal_conflict")
        _write_utf8(os.path.join(int_conf_dir, "dcOp.dc"), (
            'HEADER\n"PSFversion" "1.00"\n"corner" "TT"\n"temperature" 27\n'
            'TYPE\n"v_t" FLOAT DOUBLE PROP( "units" "V" )\n"i_t" FLOAT DOUBLE PROP( "units" "A" )\n'
            'VALUE\n"VDD" "v_t" 1.0\n"VDD:p" "i_t" -1.0e-4\nEND\n'
        ))
        _write_utf8(os.path.join(int_conf_dir, "ac.ac"), (
            'HEADER\n"PSFversion" "1.00"\n"corner" "SS"\n"temperature" 125\n'
            'TYPE\n"f_t" FLOAT DOUBLE\n"c_t" COMPLEX DOUBLE\nSWEEP\n"freq" "f_t"\nTRACE\n"Vout" "c_t"\nVALUE\n'
            '"freq" 1.0\n"Vout" (1000.0 0.0)\n"freq" 1.0e6\n"Vout" (0.0 -1.0)\nEND\n'
        ))
        spec_gain_path = os.path.join(tmp_root, "spec_gain_simple.json")
        _write_utf8(spec_gain_path, json.dumps({
            "requirements": [{"id": "G1", "quantity": "dc_gain_db", "operator": ">=", "target": 50.0, "unit": "dB"}]
        }))
        res_ic = run_metrics(int_conf_dir, spec_path=spec_gain_path)
        assert res_ic["metrics"]["pvt_metadata_conflict"] is True, res_ic["metrics"]
        assert res_ic["verdict"] == "NOT_VERIFIED", res_ic
        assert res_ic["spec_evaluation"].get("reason") == "pvt_metadata_conflict", res_ic["spec_evaluation"]

        # 30d. Genuine matching-header 8-folder repro (including `"tnom" 27` ignored) -> PASS, rc == 0
        good_8_dir = os.path.join(tmp_root, "pvt_good_8")
        for c_k in ("TT", "SS"):
            for v_k, v_lbl in ((0.90, "0p90V"), (1.10, "1p10V")):
                for t_k, t_lbl in ((-40, "-40C"), (125, "125C")):
                    _write_pvt_point(
                        os.path.join(good_8_dir, "%s_%s_%s" % (c_k, v_lbl, t_lbl)),
                        v_k, c_k, t_k, extra_hdr='"tnom" 27\n',
                    )
        res_g8 = run_metrics(good_8_dir, spec_path=pvt_spec_path)
        assert res_g8["verdict"] == "PASS", res_g8
        for pt_k, pt_m in res_g8["points"].items():
            assert pt_m["pvt_metadata_verified"] is True, (pt_k, pt_m)
            assert pt_m["pvt_metadata_conflict"] is False, (pt_k, pt_m)
        assert main(["metrics", good_8_dir, "--spec", pvt_spec_path, "--fail-on-spec"], quiet=True) == 0

        # 31. Codex Findings #01..#05 Adversarial Regression Suite
        # 31a (Finding #01): scalar mc_runs=50, duplicate iteration=7, headerless cpar_out:i MUST NOT pass MC/PEX
        spoof_hdr_mc_pex = os.path.join(tmp_root, "f01_scalar_mc_headerless_pex")
        _write_utf8(os.path.join(spoof_hdr_mc_pex, "dcOp.dc"), (
            'HEADER\n"PSFversion" "1.00"\n"mc_runs" 50\n'
            'TYPE\n"v_t" FLOAT DOUBLE PROP( "units" "V" )\n"i_t" FLOAT DOUBLE PROP( "units" "A" )\n'
            'VALUE\n"VDD" "v_t" 1.0\n"VDD:p" "i_t" -1.0e-4\n"cpar_out:i" "i_t" 1.0e-9\nEND\n'
        ))
        res_f01a = run_metrics(spoof_hdr_mc_pex, spec_path=spec_mc_pex_path)
        assert res_f01a["verdict"] == "NOT_VERIFIED", res_f01a
        assert res_f01a["metrics"]["mc_evidence"] is False, res_f01a["metrics"]
        assert res_f01a["metrics"].get("mc_runs_verified", 0) == 0, res_f01a["metrics"]
        assert res_f01a["metrics"]["pex_evidence"] is False, res_f01a["metrics"]
        assert res_f01a["metrics"].get("rc_hint_count", 0) >= 1, res_f01a["metrics"]
        assert main(["metrics", spoof_hdr_mc_pex, "--spec", spec_mc_pex_path, "--fail-on-spec"], quiet=True) == 1

        dup_mc_dir = os.path.join(tmp_root, "f01_dup_mc_iter")
        _write_utf8(os.path.join(dup_mc_dir, "dcOp.dc"), (
            'HEADER\n"PSFversion" "1.00"\n"analysis type" "montecarlo"\n'
            'TYPE\n"i_sw" INT LONG\n"v_t" FLOAT DOUBLE PROP( "units" "V" )\n"i_t" FLOAT DOUBLE PROP( "units" "A" )\n'
            'SWEEP\n"iteration" "i_sw"\nTRACE\n"VDD" "v_t"\n"VDD:p" "i_t"\nVALUE\n'
            '"iteration" 7\n"VDD" 1.0\n"VDD:p" -1.0e-4\n'
            '"iteration" 7\n"VDD" 1.0\n"VDD:p" -1.1e-4\n'
            '"iteration" 7\n"VDD" 1.0\n"VDD:p" -1.2e-4\nEND\n'
        ))
        spec_mc3_path = os.path.join(tmp_root, "spec_mc3.json")
        _write_utf8(spec_mc3_path, json.dumps({
            "coverage": {"monte_carlo": 3},
            "requirements": [{"id": "I1", "quantity": "idd_a", "operator": "<=", "target": 1.0, "unit": "mA"}],
        }))
        res_f01b = run_metrics(dup_mc_dir, spec_path=spec_mc3_path)
        assert res_f01b["verdict"] == "NOT_VERIFIED", res_f01b
        assert res_f01b["metrics"]["mc_runs_verified"] == 1, res_f01b["metrics"]
        assert "monte_carlo" in res_f01b["spec_evaluation"].get("missing_coverage", []), res_f01b["spec_evaluation"]

        # 31b (Finding #02): Multi-rail VDD=0.9V + VDDA=1.1V MUST NOT satisfy flat supplies_V=[0.9, 1.1]
        multi_rail_dir = os.path.join(tmp_root, "f02_multirail_pvt", "TT_0p9V_27C")
        _write_utf8(os.path.join(multi_rail_dir, "dcOp.dc"), (
            'HEADER\n"PSFversion" "1.00"\n"corner" "TT"\n"temperature" 27\n'
            'TYPE\n"v_t" FLOAT DOUBLE PROP( "units" "V" )\n"i_t" FLOAT DOUBLE PROP( "units" "A" )\nVALUE\n'
            '"VDD" "v_t" 0.9\n"VDD:p" "i_t" -1.0e-4\n'
            '"VDDA" "v_t" 1.1\n"VDDA:p" "i_t" -1.0e-4\nEND\n'
        ))
        spec_flat_v_path = os.path.join(tmp_root, "spec_f02_flat.json")
        _write_utf8(spec_flat_v_path, json.dumps({
            "coverage": {"corners": ["TT"], "supplies_V": [0.9, 1.1], "temperatures_C": [27]},
            "requirements": [{"id": "P1", "quantity": "dc_power_w", "operator": "<=", "target": 1.0, "unit": "mW"}],
        }))
        res_f02 = run_metrics(os.path.dirname(multi_rail_dir), spec_path=spec_flat_v_path)
        assert res_f02["verdict"] == "NOT_VERIFIED", res_f02
        assert res_f02["spec_evaluation"].get("missing_supplies_V") == [1.1], res_f02["spec_evaluation"]

        spec_rail_v_path = os.path.join(tmp_root, "spec_f02_rail.json")
        _write_utf8(spec_rail_v_path, json.dumps({
            "coverage": {"corners": ["TT"], "supplies_by_rail": {"VDD": [0.9], "VDDA": [1.1]}, "temperatures_C": [27]},
            "requirements": [{"id": "P1", "quantity": "dc_power_w", "operator": "<=", "target": 1.0, "unit": "mW"}],
        }))
        res_f02_ok = run_metrics(os.path.dirname(multi_rail_dir), spec_path=spec_rail_v_path)
        assert res_f02_ok["verdict"] == "PASS", res_f02_ok

        # 31c (Finding #03): Untyped .pz, pole1=0 jw-axis pole, stem mismatch, and circuit header mismatch
        untyped_pz_dir = os.path.join(tmp_root, "f03_untyped_pz")
        _write_utf8(os.path.join(untyped_pz_dir, "stb.stb"), codex_stb_txt)
        _write_utf8(os.path.join(untyped_pz_dir, "pz.pz"), (
            'HEADER\n"PSFversion" "1.00"\nTYPE\n"c_t" COMPLEX DOUBLE\nVALUE\n'
            '"pole1" "c_t" (-10.0 0.0)\n"pole2" "c_t" (-1000.0 0.0)\nEND\n'
        ))
        res_f03a = run_metrics(untyped_pz_dir, spec_path=spec_stb_pm_path)
        assert res_f03a["metrics"]["stability_proof_verified"] is False, res_f03a["metrics"]
        assert res_f03a["metrics"]["stability_proof_method"] == "unknown_pz_mode", res_f03a["metrics"]
        assert res_f03a["verdict"] == "NOT_VERIFIED", res_f03a

        stem_mismatch_dir = os.path.join(tmp_root, "f03_stem_mismatch_pz")
        _write_utf8(os.path.join(stem_mismatch_dir, "main_loop.stb"), good_stb_txt)
        _write_utf8(os.path.join(stem_mismatch_dir, "other_loop_closed_loop.pz"), (
            'HEADER\n"PSFversion" "1.00"\n"pz_mode" "closed_loop"\nTYPE\n"c_t" COMPLEX DOUBLE\nVALUE\n'
            '"pole1" "c_t" (-100.0 0.0)\nEND\n'
        ))
        res_f03s = run_metrics(stem_mismatch_dir, spec_path=spec_stb_pm_path)
        assert res_f03s["metrics"]["stability_proof_verified"] is False, res_f03s["metrics"]
        assert res_f03s["metrics"]["stability_proof_method"] == "stability_proof_conflict", res_f03s["metrics"]
        assert res_f03s["verdict"] == "NOT_VERIFIED", res_f03s

        jw_pz_dir = os.path.join(tmp_root, "f03_jw_origin_pz")
        _write_utf8(os.path.join(jw_pz_dir, "stb.stb"), good_stb_txt)
        _write_utf8(os.path.join(jw_pz_dir, "closed_loop.pz"), (
            'HEADER\n"PSFversion" "1.00"\n"pz_mode" "closed_loop"\nTYPE\n"c_t" COMPLEX DOUBLE\nVALUE\n'
            '"pole1" "c_t" (0.0 0.0)\nEND\n'
        ))
        res_f03b = run_metrics(jw_pz_dir, spec_path=spec_stb_pm_path)
        assert res_f03b["metrics"]["stability_proof_verified"] is False, res_f03b["metrics"]
        assert res_f03b["metrics"]["closed_loop_jw_axis_poles"] == 1, res_f03b["metrics"]
        assert res_f03b["metrics"]["closed_loop_non_lhp_poles"] == 1, res_f03b["metrics"]
        assert res_f03b["verdict"] == "FAIL", res_f03b
        assert res_f03b["spec_evaluation"]["results"][0]["conditions"]["nominal"]["reason"] == "closed_loop_jw_axis_pole", res_f03b

        hdr_mismatch_pz_dir = os.path.join(tmp_root, "f03_hdr_mismatch_pz")
        _write_utf8(os.path.join(hdr_mismatch_pz_dir, "main.stb"), good_stb_txt.replace('"PSFversion" "1.00"', '"PSFversion" "1.00"\n"circuit" "dut_ldo"'))
        _write_utf8(os.path.join(hdr_mismatch_pz_dir, "closed_loop.pz"), (
            'HEADER\n"PSFversion" "1.00"\n"circuit" "dummy_rc"\n"pz_mode" "closed_loop"\nTYPE\n"c_t" COMPLEX DOUBLE\nVALUE\n'
            '"pole1" "c_t" (-100.0 0.0)\nEND\n'
        ))
        res_f03c = run_metrics(hdr_mismatch_pz_dir, spec_path=spec_stb_pm_path)
        assert res_f03c["metrics"]["stability_proof_verified"] is False, res_f03c["metrics"]
        assert res_f03c["metrics"]["stability_proof_method"] == "stability_proof_conflict", res_f03c["metrics"]
        assert res_f03c["verdict"] == "NOT_VERIFIED", res_f03c

        # 31d (Finding #04): core.stb GM MUST NOT satisfy analysis="pstb" when periodic.margin.pstb lacks GM
        pstb_mix_dir = os.path.join(tmp_root, "f04_stb_pstb_mix")
        core_stb_lines = ['HEADER\n"PSFversion" "1.00"\nTYPE\n"f_t" FLOAT DOUBLE\n"c_t" COMPLEX DOUBLE\nSWEEP\n"freq" "f_t"\nTRACE\n"loopGain" "c_t"\nVALUE\n']
        for k_i in range(61):
            w_val = 10.0 ** (float(k_i) * 5.0 / 60.0)
            s_c = complex(0.0, w_val)
            l_val = 10.0 / ((1.0 + s_c / 100.0) ** 3)
            core_stb_lines.append('"freq" %.8e\n"loopGain" (%.10e %.10e)\n' % (w_val / (2.0 * math.pi), l_val.real, l_val.imag))
        core_stb_lines.append("END\n")
        _write_utf8(os.path.join(pstb_mix_dir, "core.stb"), "".join(core_stb_lines))
        _write_utf8(os.path.join(pstb_mix_dir, "periodic.margin.pstb"), (
            'HEADER\n"PSFversion" "1.00"\nTYPE\n"deg_t" FLOAT DOUBLE PROP( "units" "deg" )\nVALUE\n'
            '"phaseMargin" "deg_t" 68.0\nEND\n'
        ))
        spec_pstb_gm_path = os.path.join(tmp_root, "spec_f04_pstb_gm.json")
        _write_utf8(spec_pstb_gm_path, json.dumps({
            "requirements": [{"id": "GM_P", "quantity": "gain_margin_db", "operator": ">=", "target": 10.0, "unit": "dB", "analysis": "pstb"}]
        }))
        res_f04 = run_metrics(pstb_mix_dir, spec_path=spec_pstb_gm_path)
        assert res_f04["verdict"] == "NOT_VERIFIED", res_f04
        assert abs(res_f04["metrics"]["metrics_by_analysis"]["pstb"]["phase_margin_deg"] - 68.0) < 0.01, res_f04["metrics"]
        assert res_f04["metrics"]["metrics_by_analysis"]["pstb"]["gain_margin_db"] is None, res_f04["metrics"]
        assert main(["metrics", pstb_mix_dir, "--spec", spec_pstb_gm_path, "--fail-on-spec"], quiet=True) == 1

        # 31e (Finding #05): DC trace units ("mA", both TYPE PROP & VALUE PROP), unknown trace unit, and --no-relax-units
        dc_ma_dir = os.path.join(tmp_root, "f05_dc_ma")
        _write_utf8(os.path.join(dc_ma_dir, "dcOp.dc"), (
            'HEADER\n"PSFversion" "1.00"\nTYPE\n"v_t" FLOAT DOUBLE PROP( "units" "V" )\n"i_t" FLOAT DOUBLE\n'
            'VALUE\n"VDD" "v_t" 1.0\n"VDD:p" "i_t" -0.1 PROP( "units" "mA" )\nEND\n'
        ))
        spec_idd_min_path = os.path.join(tmp_root, "spec_f05_idd_min.json")
        _write_utf8(spec_idd_min_path, json.dumps({
            "requirements": [{"id": "IDD_MIN", "quantity": "idd_a", "operator": ">=", "target": 1.0, "unit": "mA"}]
        }))
        res_f05a = run_metrics(dc_ma_dir, spec_path=spec_idd_min_path)
        assert abs(res_f05a["metrics"]["idd_a"] - 1e-4) < 1e-9, res_f05a["metrics"]
        assert abs(res_f05a["metrics"]["dc_power_w"] - 1e-4) < 1e-9, res_f05a["metrics"]
        assert res_f05a["verdict"] == "FAIL", res_f05a
        assert main(["metrics", dc_ma_dir, "--spec", spec_idd_min_path, "--no-relax-units", "--fail-on-spec"], quiet=True) == 1

        dc_unk_u_dir = os.path.join(tmp_root, "f05_unknown_unit")
        _write_utf8(os.path.join(dc_unk_u_dir, "dcOp.dc"), (
            'HEADER\n"PSFversion" "1.00"\nTYPE\n"v_t" FLOAT DOUBLE PROP( "units" "V" )\n"i_t" FLOAT DOUBLE PROP( "units" "furlong" )\n'
            'VALUE\n"VDD" "v_t" 1.0\n"VDD:p" "i_t" -0.1\nEND\n'
        ))
        res_f05b = run_metrics(dc_unk_u_dir, spec_path=spec_idd_min_path)
        assert res_f05b["verdict"] == "NOT_VERIFIED", res_f05b
        assert res_f05b["metrics"]["idd_a"] is None, res_f05b["metrics"]
        assert res_f05b["spec_evaluation"]["results"][0]["reason"] == "trace_unit_error", res_f05b["spec_evaluation"]

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
                "stb_bode_slope_rhp_pole_and_nyquist_note",
                "stb_rising_0db_crossing_worst_pm",
                "dc_split_supply_vss_and_0v_ammeter_isolation",
                "spec_pvt_supply_temp_ss_neg40c_and_mc_regex",
                "mos_cutoff_pmos_unknown_region_and_expect_triode_missing_op",
                "tran_adaptive_tail_multipulse_and_clipped_step_slew",
                "ac_descending_sweep_and_zero_vin_fail_closed",
                "noise_si_prefix_asd_psd_and_zero_width_band_rejected",
                "nonfinite_spec_targets_and_constraints_range_list",
                "independent_dc_max_power_and_max_idd_sweep_and_multifile",
                "cartesian_pvt_product_coverage_enforcement",
                "genuine_mc_and_pex_evidence_anti_spoofing",
                "cryptographically_bound_manifest_mc_and_pex",
                "stb_bode_only_rhp_pole_zero_and_pz_nyquist_proof",
                "pvt_header_metadata_enforcement_and_conflict_detection",
                "codex_f01_to_f05_invariants_mc_multirail_pz_pstb_units",
            ],
        }
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


HELP_TEXT = """Usage:
  python tools/psf_audit.py op-audit  <run_or_psf_path> [--vds-margin 0.05] [--expect-triode M_R1,M_SW] [--no-relax-units] [--fail-on-violation]
  python tools/psf_audit.py metrics   <run_dir> [--spec spec.json] [--vout Vout] [--vin Vin] [--settling-tol 0.01] [--target-v 1.0] [--no-relax-units] [--fail-on-spec]
  python tools/psf_audit.py self-test (or --self-test)

Notes:
  Strict trace and spec unit enforcement is enabled by default; `--no-relax-units` explicitly asserts strict unit scaling.
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
        parser.add_option("--no-relax-units", action="store_true", dest="strict_units", default=True)
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
        parser.add_option("--no-relax-units", action="store_true", dest="strict_units", default=True)
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
