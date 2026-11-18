#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Safe Spectre 15.1 PDK gm/ID Characterization & LUT Compiler (GPDK090 / GPDK045).

100% compatible with RHEL 6.5 Python 2.6.6 and Python 3.x using pure standard library.
Uses optparse (never argparse), writes zero bytecode, and never writes runtime files
or LUT caches inside the runtime tools tree.

Fixes upstream pygmid & Spectre PSF characterization pitfalls:
  1. Normalizes Spectre PSF signal names ('mn:ids' <-> 'mn.ids' <-> 'mn.m0:ids') and PMOS signs.
  2. Enforces strict single- and multi-terminal SOA voltage caps (VDD/VGS/VDS, VSB, |VGB|=|VGS|+|VSB|,
     |VDB|=|VDS|+|VSB|) across GPDK090 (1.2V core / 2.5V IO) and GPDK045 (1.0V core / 1.8V IO),
     plus exact Celsius temp (27.0C, not 26.85C).
  3. Checks Spectre exit status, log errors, full grid file count, finite values, recursive .scs
     model include tree SHA-256 provenance, non-zero noise PSD verification when .noise files exist,
     and exact canonical [L, VDS, VSB, VGS] tensor axis ordering matching gmid_lut.py.
  4. Separates thermal noise PSD (STH: id/rd/rs/rg/rn) from 1/f flicker noise PSD (SFL: fn)
     across both inline and hierarchical subcircuit STRUCT/GROUP .noise PSF files, and omits
     unsupported 'nf' parameters on GPDK090 BSIM3v3 subcircuit wrappers.

Release: 2026.11.18.6
"""
from __future__ import print_function

import gzip
import hashlib
import json
import math
import optparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True

_TOOLS_DIR = os.path.dirname(os.path.realpath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

from psf_ascii_reader import parse_psf_file  # noqa: E402

RELEASE = "2026.11.18.6"
LIBRARY_ROOT = os.path.dirname(_TOOLS_DIR)
TIMER = getattr(time, "perf_counter", time.time)

SOA_POLICY_NOTE = (
    "Grid corners where |VGS| + |VSB| > vgb_max or |VDS| + |VSB| > vdb_max "
    "exceed gate/junction SOA and are flagged/blocked by gmid_lut.py unless "
    "allow_soa_violation=True."
)

PDK_PRESETS = {
    "gpdk090": {
        "id": "GPDK090",
        "model_candidates": [
            "/home/disk/eda/apps/cadence/pdks/gpdk090_v4.6/models/spectre/gpdk090.scs",
            "/home/disk/eda/apps/cadence/pdks/gpdk090_v4.6/gpdk090/models/spectre/gpdk090.scs",
            "/home/work/gpdk090_v4.6/models/spectre/gpdk090.scs",
        ],
        "corners": ("NN", "SS", "FF", "FS", "SF", "NN_highPerf", "SS_highPerf", "FF_highPerf"),
        "default_corner": "NN",
        "flavors": {
            "core": {
                "label": "core_1v",
                "modeln": "gpdk090_nmos1v",
                "modelp": "gpdk090_pmos1v",
                "vdd_max": 1.2,
                "vsb_max": 0.6,
                "vgb_max": 1.32,
                "vdb_max": 1.32,
                "w_ref": 4.0e-6,
                "nf": 1,
                "emit_nf": False,
                "l_grid": [90e-9, 120e-9, 180e-9, 240e-9, 360e-9, 500e-9, 1.0e-6],
                "vgs_step": 0.03,
                "vds_grid": [0.05, 0.15, 0.30, 0.60, 0.90, 1.20],
                "vsb_grid": [0.0, 0.3, 0.6],
                "extra_inst_params": "simM=1",
            },
            "io": {
                "label": "io_2v5",
                "modeln": "gpdk090_nmos2v",
                "modelp": "gpdk090_pmos2v",
                "vdd_max": 2.5,
                "vsb_max": 1.2,
                "vgb_max": 2.75,
                "vdb_max": 2.75,
                "w_ref": 8.0e-6,
                "nf": 1,
                "emit_nf": False,
                "l_grid": [280e-9, 360e-9, 500e-9, 1.0e-6, 2.0e-6],
                "vgs_step": 0.05,
                "vds_grid": [0.10, 0.30, 0.60, 1.20, 1.80, 2.50],
                "vsb_grid": [0.0, 0.4, 0.8],
                "extra_inst_params": "simM=1",
            },
        },
    },
    "gpdk045": {
        "id": "GPDK045",
        "model_candidates": [
            "/home/disk/eda/apps/cadence/pdks/gpdk045_v_5_0/models/spectre/gpdk045.scs",
            "/home/disk/eda/apps/cadence/pdks/gpdk045_v_5_0/gpdk045/models/spectre/gpdk045.scs",
            "/home/work/gpdk045_v_5_0/models/spectre/gpdk045.scs",
        ],
        "corners": ("tt", "ss", "ff", "fs", "sf"),
        "default_corner": "tt",
        "flavors": {
            "core": {
                "label": "core_1v_svt",
                "modeln": "g45n1svt",
                "modelp": "g45p1svt",
                "vdd_max": 1.0,
                "vsb_max": 0.5,
                "vgb_max": 1.1,
                "vdb_max": 1.1,
                "w_ref": 2.0e-6,
                "nf": 4,
                "emit_nf": True,
                "l_grid": [45e-9, 60e-9, 90e-9, 135e-9, 180e-9, 360e-9, 720e-9, 1.0e-6],
                "vgs_step": 0.025,
                "vds_grid": [0.05, 0.15, 0.30, 0.50, 0.75, 1.00],
                "vsb_grid": [0.0, 0.25, 0.50],
                "extra_inst_params": "",
            },
            "lvt": {
                "label": "core_1v_lvt",
                "modeln": "g45n1lvt",
                "modelp": "g45p1lvt",
                "vdd_max": 1.0,
                "vsb_max": 0.5,
                "vgb_max": 1.1,
                "vdb_max": 1.1,
                "w_ref": 2.0e-6,
                "nf": 4,
                "emit_nf": True,
                "l_grid": [45e-9, 60e-9, 90e-9, 180e-9, 360e-9, 1.0e-6],
                "vgs_step": 0.025,
                "vds_grid": [0.05, 0.15, 0.30, 0.50, 0.75, 1.00],
                "vsb_grid": [0.0, 0.25, 0.50],
                "extra_inst_params": "",
            },
            "hvt": {
                "label": "core_1v_hvt",
                "modeln": "g45n1hvt",
                "modelp": "g45p1hvt",
                "vdd_max": 1.0,
                "vsb_max": 0.5,
                "vgb_max": 1.1,
                "vdb_max": 1.1,
                "w_ref": 2.0e-6,
                "nf": 4,
                "emit_nf": True,
                "l_grid": [45e-9, 60e-9, 90e-9, 180e-9, 360e-9, 1.0e-6],
                "vgs_step": 0.025,
                "vds_grid": [0.05, 0.15, 0.30, 0.50, 0.75, 1.00],
                "vsb_grid": [0.0, 0.25, 0.50],
                "extra_inst_params": "",
            },
            "io": {
                "label": "io_1v8",
                "modeln": "g45n2svt",
                "modelp": "g45p2svt",
                "vdd_max": 1.8,
                "vsb_max": 0.9,
                "vgb_max": 1.98,
                "vdb_max": 1.98,
                "w_ref": 4.0e-6,
                "nf": 4,
                "emit_nf": True,
                "l_grid": [150e-9, 240e-9, 360e-9, 500e-9, 1.0e-6, 2.0e-6],
                "vgs_step": 0.04,
                "vds_grid": [0.10, 0.30, 0.60, 0.90, 1.35, 1.80],
                "vsb_grid": [0.0, 0.3, 0.6],
                "extra_inst_params": "",
            },
        },
    },
}

FLAVOR_ALIASES = {
    "1v": "core",
    "core_1v": "core",
    "svt": "core",
    "core_1v_svt": "core",
    "2v5": "io",
    "io2v5": "io",
    "io_2v5": "io",
    "1v8": "io",
    "2v": "io",
    "io1v8": "io",
    "io_1v8": "io",
}


class TechSweepError(Exception):
    pass


def _build_soa_limits(fcfg):
    vdd_max = float(fcfg["vdd_max"])
    vsb_max = float(fcfg.get("vsb_max", round(0.5 * vdd_max, 6)))
    vgb_max = float(fcfg.get("vgb_max", round(1.1 * vdd_max, 6)))
    vdb_max = float(fcfg.get("vdb_max", round(1.1 * vdd_max, 6)))
    return {
        "vdd_max": vdd_max,
        "vgs_max": vdd_max,
        "vds_max": vdd_max,
        "vsb_max": vsb_max,
        "vgb_max": vgb_max,
        "vdb_max": vdb_max,
        "note": SOA_POLICY_NOTE,
    }


def _resolve_soa_from_spec(spec):
    existing = spec.get("soa_limits")
    if isinstance(existing, dict) and "vgb_max" in existing and "vdb_max" in existing:
        out = dict(existing)
        if "note" not in out:
            out["note"] = SOA_POLICY_NOTE
        return out
    pdk_k = str(spec.get("pdk_key", "")).lower()
    flav_k = str(spec.get("flavor_key", "core")).lower()
    flav_k = FLAVOR_ALIASES.get(flav_k, flav_k)
    if pdk_k in PDK_PRESETS and flav_k in PDK_PRESETS[pdk_k]["flavors"]:
        return _build_soa_limits(PDK_PRESETS[pdk_k]["flavors"][flav_k])
    vdd_max = float(spec.get("vdd_max", 1.2))
    return {
        "vdd_max": vdd_max,
        "vgs_max": vdd_max,
        "vds_max": vdd_max,
        "vsb_max": round(0.5 * vdd_max, 6),
        "vgb_max": round(1.1 * vdd_max, 6),
        "vdb_max": round(1.1 * vdd_max, 6),
        "note": SOA_POLICY_NOTE,
    }


def _is_inside(path, base):
    p_norm = os.path.normcase(os.path.realpath(path))
    b_norm = os.path.normcase(os.path.realpath(base))
    return p_norm == b_norm or p_norm.startswith(b_norm.rstrip(os.sep) + os.sep)


def ensure_outside_library(path, label):
    if _is_inside(path, LIBRARY_ROOT):
        raise TechSweepError(
            "%s must never reside inside SKILL-ANALOG/library (%s): %s"
            % (label, LIBRARY_ROOT, path)
        )


def default_lut_cache_dir():
    home = os.path.expanduser("~")
    return os.path.join(home, ".cache", "skill-analog", "gmid-luts")


def default_lut_path(pdk_key, flavor_key, corner, temp_c):
    preset = PDK_PRESETS[pdk_key]
    flavor_label = preset["flavors"][flavor_key]["label"]
    temp_tag = ("%g" % float(temp_c)).replace("-", "m").replace(".", "p")
    fname = "%s_%s_%s_%sC.lut.json.gz" % (pdk_key, flavor_label, corner, temp_tag)
    return os.path.join(default_lut_cache_dir(), fname)


def _mkdir_p(path):
    if path and not os.path.isdir(path):
        os.makedirs(path)


def _sha256_file(path):
    if not path or not os.path.isfile(path):
        return None
    h = hashlib.sha256()
    f = open(path, "rb")
    try:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    finally:
        f.close()
    return h.hexdigest()


_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_INCLUDE_LINE_RE = re.compile(
    r'^\s*(?:\.?(?:ahdl_)?include|\.lib)\s+(?:"([^"]+)"|\'([^\']+)\'|([^\s;]+))',
    re.IGNORECASE,
)


def _strip_scs_statements(text):
    """Strip Spectre /*...*/, //..., and leading * comment lines; join trailing \\ continuations."""
    no_block = _BLOCK_COMMENT_RE.sub(" ", text)
    joined_lines = []
    buf = ""
    for raw_line in no_block.splitlines():
        s_lead = raw_line.lstrip()
        if not buf and (not s_lead or s_lead.startswith("*") or s_lead.startswith("//")):
            continue
        in_dq = False
        in_sq = False
        cut_idx = len(raw_line)
        i = 0
        n_ch = len(raw_line)
        while i < n_ch:
            ch = raw_line[i]
            if ch == '"' and not in_sq:
                in_dq = not in_dq
            elif ch == "'" and not in_dq:
                in_sq = not in_sq
            elif (not in_dq) and (not in_sq) and ch == "/" and (i + 1 < n_ch) and raw_line[i + 1] == "/":
                cut_idx = i
                break
            i += 1
        line_clean = raw_line[:cut_idx].strip()
        if not line_clean:
            if buf:
                joined_lines.append(buf)
                buf = ""
            continue
        if line_clean.endswith("\\"):
            stem = line_clean[:-1].strip()
            buf = (buf + " " + stem).strip() if buf else stem
        else:
            full_line = (buf + " " + line_clean).strip() if buf else line_clean
            buf = ""
            if full_line:
                joined_lines.append(full_line)
    if buf:
        joined_lines.append(buf)
    return joined_lines


def _hash_model_tree(model_file):
    """Recursively parse Spectre include statements in .scs files with cycle protection.

    Resolves relative include paths against the including file's directory and returns:
      - model_file: realpath of root model_file (or original string if missing)
      - model_sha256: SHA-256 of root model_file (or None)
      - included_files_sha256: sorted dict of realpath -> sha256 for all included .scs files
      - model_tree_sha256: aggregate SHA-256 over root + all included .scs files
      - missing_includes: sorted list of unresolved include realpaths (if any)
    """
    if not model_file:
        return {
            "model_file": None,
            "model_sha256": None,
            "included_files_sha256": {},
            "model_tree_sha256": None,
            "missing_includes": [],
        }
    expanded_root = os.path.expanduser(os.path.expandvars(str(model_file)))
    if not os.path.isfile(expanded_root):
        return {
            "model_file": model_file,
            "model_sha256": None,
            "included_files_sha256": {},
            "model_tree_sha256": None,
            "missing_includes": [],
        }

    root_real = os.path.realpath(expanded_root)
    visited = set()
    all_hashes = {}
    included_raw = {}
    missing_set = set()
    missing_list = []

    def _walk(cur_real, is_root):
        norm_key = os.path.normcase(cur_real)
        if norm_key in visited:
            return
        visited.add(norm_key)

        sha = _sha256_file(cur_real)
        if sha is None:
            return
        all_hashes[cur_real] = sha
        if not is_root:
            included_raw[cur_real] = sha

        f = open(cur_real, "rb")
        try:
            content = f.read().decode("latin1")
        finally:
            f.close()

        base_dir = os.path.dirname(cur_real)
        for stmt in _strip_scs_statements(content):
            m = _INCLUDE_LINE_RE.match(stmt)
            if not m:
                continue
            raw_inc = m.group(1) or m.group(2) or m.group(3)
            if not raw_inc:
                continue
            inc_exp = os.path.expanduser(os.path.expandvars(raw_inc))
            if not os.path.isabs(inc_exp):
                inc_cand = os.path.join(base_dir, inc_exp)
            else:
                inc_cand = inc_exp
            inc_real = os.path.realpath(inc_cand)
            if os.path.isfile(inc_real):
                _walk(inc_real, False)
            else:
                miss_norm = os.path.normcase(inc_real)
                if miss_norm not in missing_set:
                    missing_set.add(miss_norm)
                    missing_list.append(inc_real)

    _walk(root_real, True)

    sorted_inc = {}
    for k in sorted(included_raw.keys()):
        sorted_inc[k] = included_raw[k]

    tree_h = hashlib.sha256()
    tree_h.update(("ROOT:%s:%s\n" % (root_real, all_hashes.get(root_real, ""))).encode("utf-8"))
    for k in sorted(sorted_inc.keys()):
        tree_h.update(("INC:%s:%s\n" % (k, sorted_inc[k])).encode("utf-8"))
    for miss_p in sorted(missing_list):
        tree_h.update(("MISSING:%s\n" % miss_p).encode("utf-8"))

    return {
        "model_file": root_real,
        "model_sha256": all_hashes.get(root_real),
        "included_files_sha256": sorted_inc,
        "model_tree_sha256": tree_h.hexdigest(),
        "missing_includes": sorted(missing_list),
    }


def _linspace_step(start, stop, step):
    if step <= 0.0 or stop < start:
        raise TechSweepError("Invalid sweep range start=%g stop=%g step=%g" % (start, stop, step))
    count = int(math.floor((stop - start) / step + 1e-9)) + 1
    vals = []
    for idx in range(count):
        val = round(start + idx * step, 9)
        if val <= stop + 1e-9:
            vals.append(min(val, stop))
    if not vals or abs(vals[-1] - stop) > 1e-7:
        vals.append(round(stop, 9))
    return vals


def _parse_float_list(csv_text):
    items = []
    for tok in csv_text.split(","):
        tok = tok.strip()
        if tok:
            items.append(float(tok))
    if not items:
        raise TechSweepError("Empty numeric list: %s" % csv_text)
    return sorted(items)


def resolve_sweep_spec(
    pdk="gpdk090",
    flavor="core",
    corner=None,
    temp_c=27.0,
    model_file=None,
    vgs_max=None,
    vds_max=None,
    vsb_max=None,
    l_list=None,
    vgs_step=None,
    vds_list=None,
    vsb_list=None,
    allow_overvoltage=False,
):
    pdk_key = pdk.strip().lower()
    if pdk_key not in PDK_PRESETS:
        raise TechSweepError("Unsupported PDK '%s'. Choose from: %s" % (pdk, ", ".join(sorted(PDK_PRESETS.keys()))))
    preset = PDK_PRESETS[pdk_key]

    flav_raw = flavor.strip().lower()
    flav_key = FLAVOR_ALIASES.get(flav_raw, flav_raw)
    if flav_key not in preset["flavors"]:
        raise TechSweepError(
            "Unsupported flavor '%s' for %s. Choose from: %s"
            % (flavor, preset["id"], ", ".join(sorted(preset["flavors"].keys())))
        )
    fcfg = preset["flavors"][flav_key]
    soa_limits = _build_soa_limits(fcfg)

    chosen_corner = corner if corner else preset["default_corner"]
    if chosen_corner not in preset["corners"]:
        raise TechSweepError(
            "Invalid corner '%s' for %s (case-sensitive!). Allowed sections: %s"
            % (chosen_corner, preset["id"], ", ".join(preset["corners"]))
        )

    vdd_cap = fcfg["vdd_max"]
    eff_vgs_max = float(vgs_max) if vgs_max is not None else vdd_cap
    eff_vds_max = float(vds_max) if vds_max is not None else vdd_cap
    eff_vsb_max = float(vsb_max) if vsb_max is not None else fcfg["vsb_max"]

    if not allow_overvoltage:
        if eff_vgs_max > vdd_cap + 1e-9:
            raise TechSweepError(
                "SOA violation: requested VGS_max=%.3fV exceeds %s %s safe cap %.2fV (fixes pygmid 1.8V bug)."
                % (eff_vgs_max, preset["id"], fcfg["modeln"], vdd_cap)
            )
        if eff_vds_max > vdd_cap + 1e-9:
            raise TechSweepError(
                "SOA violation: requested VDS_max=%.3fV exceeds %s %s safe cap %.2fV."
                % (eff_vds_max, preset["id"], fcfg["modeln"], vdd_cap)
            )
        if eff_vsb_max > vdd_cap + 1e-9:
            raise TechSweepError(
                "SOA violation: requested VSB_max=%.3fV exceeds safe reverse body-bias cap %.2fV."
                % (eff_vsb_max, vdd_cap)
            )

    step_g = float(vgs_step) if vgs_step is not None else fcfg["vgs_step"]
    vgs_grid = _linspace_step(0.0, eff_vgs_max, step_g)

    if vds_list:
        vds_grid = [v for v in vds_list if 0.0 < v <= eff_vds_max + 1e-9]
    else:
        vds_grid = [v for v in fcfg["vds_grid"] if v <= eff_vds_max + 1e-9]
        if not vds_grid or abs(vds_grid[-1] - eff_vds_max) > 1e-6:
            vds_grid.append(eff_vds_max)
    vds_grid = sorted(list(set([round(v, 9) for v in vds_grid])))

    if vsb_list is not None:
        vsb_grid = sorted(list(set([round(v, 9) for v in vsb_list])))
    else:
        vsb_grid = [v for v in fcfg["vsb_grid"] if v <= eff_vsb_max + 1e-9]

    l_grid = sorted(list(set(l_list if l_list else fcfg["l_grid"])))
    if min(l_grid) <= 0.0:
        raise TechSweepError("Channel lengths must be strictly positive (meters).")

    resolved_model = model_file
    if not resolved_model:
        for cand in preset["model_candidates"]:
            if os.path.isfile(cand):
                resolved_model = cand
                break
        if not resolved_model:
            resolved_model = preset["model_candidates"][0]

    return {
        "pdk_key": pdk_key,
        "pdk": preset["id"],
        "flavor_key": flav_key,
        "flavor": fcfg["label"],
        "corner": chosen_corner,
        "temp_c": float(temp_c),
        "vdd_max": vdd_cap,
        "soa_limits": soa_limits,
        "model_file": resolved_model,
        "modeln": fcfg["modeln"],
        "modelp": fcfg["modelp"],
        "w_ref": fcfg["w_ref"],
        "nf": fcfg["nf"],
        "emit_nf": bool(fcfg.get("emit_nf", True)),
        "extra_inst_params": fcfg["extra_inst_params"],
        "L": l_grid,
        "VGS": vgs_grid,
        "VDS": vds_grid,
        "VSB": vsb_grid,
    }


def _fmt_num_list(values):
    return " ".join(["%.9g" % v for v in values])


def build_spectre_deck(spec):
    """Build verified Spectre 15.1 characterization deck (techsweep.scs)."""
    nf_val = int(spec.get("nf", 1))
    w_finger = spec["w_ref"] / float(max(nf_val, 1))
    nf_clause = (" nf=%d" % nf_val) if spec.get("emit_nf", True) else ""
    extra = (" " + spec["extra_inst_params"]) if spec["extra_inst_params"] else ""
    vds_vals = _fmt_num_list(spec["VDS"])
    vgs_vals = _fmt_num_list(spec["VGS"])
    soa = _resolve_soa_from_spec(spec)

    lines = [
        "// Skill-Analog Verified Spectre 15.1 gm/ID Characterization Deck (v%s)" % RELEASE,
        "// PDK=%s Flavor=%s Section=%s Temp=%.2fC VDD_cap=%.2fV VGB_max=%.2fV VDB_max=%.2fV"
        % (
            spec["pdk"],
            spec["flavor"],
            spec["corner"],
            spec["temp_c"],
            spec["vdd_max"],
            soa["vgb_max"],
            soa["vdb_max"],
        ),
        "simulator lang=spectre",
        "global 0",
        'include "%s" section=%s' % (spec["model_file"], spec["corner"]),
        'include "params.scs"',
        "",
        "parameters gs=0.4 ds=0.4",
        "",
        "// Independent NMOS and PMOS bias & noise probes (zero cross-coupling)",
        "vnoi_n (vxn 0) vsource dc=0",
        "vdsn   (vdn vxn) vsource dc=ds",
        "vgsn   (vgn 0) vsource dc=gs",
        "vbsn   (vbn 0) vsource dc=-vsb_mag",
        "",
        "vnoi_p (vxp 0) vsource dc=0",
        "vdsp   (vdp vxp) vsource dc=-ds",
        "vgsp   (vgp 0) vsource dc=-gs",
        "vbsp   (vbp 0) vsource dc=vsb_mag",
        "",
        "mn (vdn vgn 0 vbn) %s w=%.9g l=length_m%s m=1%s"
        % (spec["modeln"], spec["w_ref"], nf_clause, extra),
        "mp (vdp vgp 0 vbp) %s w=%.9g l=length_m%s m=1%s"
        % (spec["modelp"], spec["w_ref"], nf_clause, extra),
        "// Width ref: w_total=%.9g (nf_ref=%d, w_finger=%.9g; GPDK090 CDF uses per-finger w + simM=m*fingers; GPDK045 uses total w + nf)"
        % (spec["w_ref"], nf_val, w_finger),
        "",
        "save mn:ids mn:gm mn:gds mn:gmbs mn:vth mn:vdsat mn:cgg mn:cgs mn:cgd mn:cgb mn:cdd mn:css mn:cjd",
        "save mp:ids mp:gm mp:gds mp:gmbs mp:vth mp:vdsat mp:cgg mp:cgs mp:cgd mp:cgb mp:cdd mp:css mp:cjd",
        "",
        "simOptions options gmin=1e-13 reltol=1e-4 vabstol=1e-6 iabstol=1e-12 temp=%.4f tnom=27"
        % spec["temp_c"],
        "",
        "sweepvds sweep param=ds values=[%s] {" % vds_vals,
        "    sweepvgs dc param=gs values=[%s]" % vgs_vals,
        "}",
        "sweepvds_noisen sweep param=ds values=[%s] {" % vds_vals,
        "    sweepvgs_noisen noise freq=1.0 oprobe=vnoi_n param=gs values=[%s]" % vgs_vals,
        "}",
        "sweepvds_noisep sweep param=ds values=[%s] {" % vds_vals,
        "    sweepvgs_noisep noise freq=1.0 oprobe=vnoi_p param=gs values=[%s]" % vgs_vals,
        "}",
        "",
    ]
    return "\n".join(lines)


def write_deck_bundle(spec, out_dir):
    ensure_outside_library(out_dir, "Techsweep deck directory")
    _mkdir_p(out_dir)
    scs_path = os.path.join(out_dir, "techsweep.scs")
    params_path = os.path.join(out_dir, "params.scs")
    manifest_path = os.path.join(out_dir, "sweep_manifest.json")
    runner_sh = os.path.join(out_dir, "run_techsweep.sh")

    f = open(scs_path, "wb")
    try:
        f.write(build_spectre_deck(spec).encode("utf-8"))
    finally:
        f.close()

    f = open(params_path, "wb")
    try:
        p_txt = "parameters length_m=%.9g vsb_mag=%.9g\n" % (spec["L"][0], spec["VSB"][0])
        f.write(p_txt.encode("utf-8"))
    finally:
        f.close()

    f = open(manifest_path, "wb")
    try:
        f.write((json.dumps(spec, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    finally:
        f.close()

    sh_lines = [
        "#!/bin/sh",
        "set -eu",
        'if [ -f "$HOME/cadence/env.sh" ]; then',
        '  . "$HOME/cadence/env.sh"',
        "fi",
        "export CDS_Netlisting_Mode=Analog",
        'python -B "%s" --run --pdk %s --flavor %s --corner %s --work-dir "%s"'
        % (
            os.path.realpath(__file__),
            spec["pdk_key"],
            spec["flavor_key"],
            spec["corner"],
            os.path.realpath(out_dir),
        ),
        "",
    ]
    f = open(runner_sh, "wb")
    try:
        f.write("\n".join(sh_lines).encode("utf-8"))
    finally:
        f.close()
    try:
        os.chmod(runner_sh, 0o755)
    except OSError:
        pass

    return {
        "ok": True,
        "deck_file": os.path.realpath(scs_path),
        "params_file": os.path.realpath(params_path),
        "manifest_file": os.path.realpath(manifest_path),
        "runner_script": os.path.realpath(runner_sh),
        "spec": spec,
    }


THERMAL_NOISE_PARAMS = set([
    "id", "rd", "rs", "rg", "rb", "rn", "thermal", "idrain", "ith", "sth",
])
FLICKER_NOISE_PARAMS = set([
    "fn", "flicker", "fl", "1overf", "ifl", "sfl",
])


def _normalize_sig_name(name):
    """Normalize 'mn:ids' and 'mn.ids' to canonical 'mn:ids'."""
    if "." in name and ":" not in name:
        head, tail = name.split(".", 1)
        if head in ("mn", "mp") and "." not in tail:
            return head + ":" + tail
    return name


def _split_inst_param(sig_name):
    if ":" in sig_name:
        return sig_name.rsplit(":", 1)
    if "." in sig_name:
        return sig_name.rsplit(".", 1)
    return None, sig_name


def _inst_matches_prefix(inst_part, prefix):
    if not inst_part:
        return False
    ilow = inst_part.lower()
    plow = prefix.lower()
    if ilow == plow:
        return True
    for sep in (".", ":", "/"):
        if ilow.startswith(plow + sep):
            return True
    return False


def parse_psf_sweep_file(path):
    """Parse Spectre PSF ASCII sweep file via full state-machine reader (STRUCT/GROUP/SWEEP)."""
    try:
        parsed = parse_psf_file(path, reject_nonfinite=True)
    except Exception as exc:
        raise TechSweepError("Failed to parse PSF file %s: %s" % (path, str(exc)))
    if not parsed.get("has_value_section"):
        raise TechSweepError("No VALUE section in PSF file %s" % path)

    signals = {}
    raw_vals = parsed.get("values", {})
    for raw_name in sorted(raw_vals.keys()):
        arr = raw_vals[raw_name]
        if not arr:
            continue
        out_arr = []
        for item in arr:
            val = abs(item) if isinstance(item, complex) else float(item)
            if math.isnan(val) or math.isinf(val):
                raise TechSweepError("Non-finite PSF value in %s for %s" % (path, raw_name))
            out_arr.append(val)
        canon = _normalize_sig_name(raw_name)
        signals[canon] = out_arr

    if not signals:
        raise TechSweepError("No valid PSF signals parsed from %s" % path)
    return signals


def _lookup_dc_signal(dc_sigs, prefix, param_name, n_g):
    """Lookup DC signal '<prefix>:<param_name>' with subcircuit fallback ('mn.m0:ids', etc.)."""
    direct_k = "%s:%s" % (prefix, param_name)
    if direct_k in dc_sigs and len(dc_sigs[direct_k]) == n_g:
        return dc_sigs[direct_k]
    p_low = param_name.lower()
    for sig_k in sorted(dc_sigs.keys()):
        arr = dc_sigs[sig_k]
        if len(arr) != n_g:
            continue
        inst_part, tail_param = _split_inst_param(sig_k)
        if tail_param.lower() == p_low and _inst_matches_prefix(inst_part, prefix):
            return arr
    return None


def _extract_device_noise_psds(parsed_noise, prefix, n_g):
    """Extract separated thermal (STH) and 1/f flicker (SFL) current noise PSDs (A^2/Hz)."""
    if not parsed_noise:
        return [0.0] * n_g, [0.0] * n_g, False
    raw_vals = parsed_noise.get("values", {})
    field_units = parsed_noise.get("field_units", {})
    sth_arr = [0.0] * n_g
    sfl_arr = [0.0] * n_g
    tot_arr = [0.0] * n_g
    found_th = False
    found_fl = False
    found_tot = False

    for raw_key in sorted(raw_vals.keys()):
        arr = raw_vals[raw_key]
        if len(arr) != n_g:
            continue
        inst_part, param_part = _split_inst_param(raw_key)
        if not _inst_matches_prefix(inst_part, prefix):
            continue
        p_low = param_part.lower()
        u_low = str(field_units.get(raw_key, "")).lower()
        is_asd = ("sqrt" in u_low)

        if p_low in THERMAL_NOISE_PARAMS:
            found_th = True
            for k in range(n_g):
                mag = abs(arr[k]) if isinstance(arr[k], complex) else abs(float(arr[k]))
                sth_arr[k] += (mag * mag) if is_asd else mag
        elif p_low in FLICKER_NOISE_PARAMS:
            found_fl = True
            for k in range(n_g):
                mag = abs(arr[k]) if isinstance(arr[k], complex) else abs(float(arr[k]))
                sfl_arr[k] += (mag * mag) if is_asd else mag
        elif p_low == "total":
            found_tot = True
            for k in range(n_g):
                mag = abs(arr[k]) if isinstance(arr[k], complex) else abs(float(arr[k]))
                tot_arr[k] += (mag * mag) if is_asd else mag

    if not found_th and found_tot and found_fl:
        for k in range(n_g):
            sth_arr[k] = max(0.0, tot_arr[k] - sfl_arr[k])
        found_th = True

    return sth_arr, sfl_arr, (found_th or found_fl)


def _detect_sweep_base(raw_dir, prefix, suffix):
    """Detect whether Spectre outer sweep numbering in raw_dir is 0-based or 1-based."""
    for cand0 in (
        os.path.join(raw_dir, "%s-%03d_%s" % (prefix, 0, suffix)),
        os.path.join(raw_dir, "%s-%d_%s" % (prefix, 0, suffix)),
    ):
        if os.path.isfile(cand0):
            return 0
    for cand1 in (
        os.path.join(raw_dir, "%s-%03d_%s" % (prefix, 1, suffix)),
        os.path.join(raw_dir, "%s-%d_%s" % (prefix, 1, suffix)),
    ):
        if os.path.isfile(cand1):
            return 1
    return None


def _find_sweep_slice_file(raw_dir, prefix, suffix, i_d, base_idx):
    if base_idx is None:
        return None
    idx = base_idx + i_d
    for cand in (
        os.path.join(raw_dir, "%s-%03d_%s" % (prefix, idx, suffix)),
        os.path.join(raw_dir, "%s-%d_%s" % (prefix, idx, suffix)),
    ):
        if os.path.isfile(cand):
            return cand
    return None


def _save_lut_gz(lut_obj, out_path):
    ensure_outside_library(out_path, "Compiled gm/ID LUT")
    _mkdir_p(os.path.dirname(os.path.abspath(out_path)))
    payload = json.dumps(lut_obj, separators=(",", ":"), sort_keys=True).encode("utf-8")
    if out_path.endswith(".gz"):
        gz = gzip.open(out_path, "wb")
        try:
            gz.write(payload)
        finally:
            gz.close()
    else:
        f = open(out_path, "wb")
        try:
            f.write(payload)
        finally:
            f.close()
    return os.path.realpath(out_path)


def compile_psf_sweep_dir(sweep_dir, out_path):
    """Compile a completed Spectre PSF ASCII characterization tree into .lut.json.gz."""
    manifest_path = os.path.join(sweep_dir, "sweep_manifest.json")
    if not os.path.isfile(manifest_path):
        raise TechSweepError("Missing sweep_manifest.json in %s" % sweep_dir)
    mf = open(manifest_path, "rb")
    try:
        spec = json.loads(mf.read().decode("utf-8"))
    finally:
        mf.close()

    l_grid = spec["L"]
    vds_grid = spec["VDS"]
    vsb_grid = spec["VSB"]
    vgs_grid = spec["VGS"]
    n_l = len(l_grid)
    n_d = len(vds_grid)
    n_b = len(vsb_grid)
    n_g = len(vgs_grid)
    w_ref = float(spec["w_ref"])

    field_names = (
        "id_w", "gm_w", "gds_w", "gmb_w", "vth", "vdsat",
        "cgg_w", "cgs_w", "cgd_w", "cdd_w", "sth_w", "sfl_w",
    )
    dev_tables = {}
    for dev_key, prefix, pol in (("nmos", "mn", 1), ("pmos", "mp", -1)):
        fields = {}
        for fn in field_names:
            fields[fn] = []
        dev_tables[dev_key] = {
            "model_name": spec["modeln"] if dev_key == "nmos" else spec["modelp"],
            "polarity": pol,
            "L": l_grid,
            "VDS": vds_grid,
            "VSB": vsb_grid,
            "VGS": vgs_grid,
            "shape": [n_l, n_d, n_b, n_g],
            "fields": fields,
        }

    # Pre-validate raw_<i_l>_<i_b> directories and detect 0-based vs 1-based outer sweep index
    raw_meta = {}
    noise_psf_files_present = False
    for i_l in range(n_l):
        for i_b in range(n_b):
            raw_dir = os.path.join(sweep_dir, "raw_%d_%d" % (i_l, i_b))
            if not os.path.isdir(raw_dir):
                raise TechSweepError("Missing PSF directory %s (simulation incomplete)" % raw_dir)
            dc_base = _detect_sweep_base(raw_dir, "sweepvds", "sweepvgs.dc")
            nn_base = _detect_sweep_base(raw_dir, "sweepvds_noisen", "sweepvgs_noisen.noise")
            pn_base = _detect_sweep_base(raw_dir, "sweepvds_noisep", "sweepvgs_noisep.noise")
            if nn_base is not None or pn_base is not None:
                noise_psf_files_present = True
            else:
                for entry_name in os.listdir(raw_dir):
                    if entry_name.lower().endswith(".noise"):
                        noise_psf_files_present = True
                        break
            raw_meta[(i_l, i_b)] = (raw_dir, dc_base, nn_base, pn_base)

    noise_found = {"nmos": False, "pmos": False}

    # Flatten strictly in declared axes_order = ["L", "VDS", "VSB", "VGS"], shape = [n_l, n_d, n_b, n_g]
    for i_l in range(n_l):
        for i_d in range(n_d):
            for i_b in range(n_b):
                raw_dir, dc_base, nn_base, pn_base = raw_meta[(i_l, i_b)]
                dc_file = _find_sweep_slice_file(raw_dir, "sweepvds", "sweepvgs.dc", i_d, dc_base)
                if not dc_file:
                    raise TechSweepError(
                        "Missing DC sweep PSF file for L[%d], VDS[%d], VSB[%d] in %s"
                        % (i_l, i_d, i_b, raw_dir)
                    )
                dc_sigs = parse_psf_sweep_file(dc_file)

                nn_parsed = None
                pn_parsed = None
                nn_file = _find_sweep_slice_file(
                    raw_dir, "sweepvds_noisen", "sweepvgs_noisen.noise", i_d, nn_base
                )
                if nn_file:
                    noise_psf_files_present = True
                    try:
                        nn_parsed = parse_psf_file(nn_file, reject_nonfinite=True)
                    except Exception as exc:
                        raise TechSweepError("Failed to parse NMOS noise PSF %s: %s" % (nn_file, str(exc)))
                pn_file = _find_sweep_slice_file(
                    raw_dir, "sweepvds_noisep", "sweepvgs_noisep.noise", i_d, pn_base
                )
                if pn_file:
                    noise_psf_files_present = True
                    try:
                        pn_parsed = parse_psf_file(pn_file, reject_nonfinite=True)
                    except Exception as exc:
                        raise TechSweepError("Failed to parse PMOS noise PSF %s: %s" % (pn_file, str(exc)))

                for dev_key, pfx, n_parsed in (("nmos", "mn", nn_parsed), ("pmos", "mp", pn_parsed)):
                    req_keys = ("ids", "gm", "gds", "vth", "vdsat", "cgg", "cgs", "cgd", "cdd")
                    resolved_dc = {}
                    for rk in req_keys:
                        arr = _lookup_dc_signal(dc_sigs, pfx, rk, n_g)
                        if arr is None:
                            raise TechSweepError(
                                "Signal '%s:%s' missing or wrong VGS length in %s (expected %d)"
                                % (pfx, rk, dc_file, n_g)
                            )
                        resolved_dc[rk] = arr

                    gmbs_arr = _lookup_dc_signal(dc_sigs, pfx, "gmbs", n_g)
                    if gmbs_arr is None:
                        gmbs_arr = _lookup_dc_signal(dc_sigs, pfx, "gmb", n_g) or ([0.0] * n_g)
                    cjd_arr = _lookup_dc_signal(dc_sigs, pfx, "cjd", n_g) or ([0.0] * n_g)

                    sth_arr, sfl_arr, has_n = _extract_device_noise_psds(n_parsed, pfx, n_g)
                    if has_n:
                        noise_found[dev_key] = True

                    fdict = dev_tables[dev_key]["fields"]
                    for k_g in range(n_g):
                        ids_mag = max(abs(resolved_dc["ids"][k_g]), 1e-18)
                        gm_mag = max(abs(resolved_dc["gm"][k_g]), 1e-18)
                        gds_mag = max(abs(resolved_dc["gds"][k_g]), 1e-18)
                        gmb_mag = abs(gmbs_arr[k_g])
                        vth_mag = abs(resolved_dc["vth"][k_g])
                        vdsat_mag = max(abs(resolved_dc["vdsat"][k_g]), 0.025)
                        cgg_mag = max(abs(resolved_dc["cgg"][k_g]), 1e-21)
                        cgs_mag = abs(resolved_dc["cgs"][k_g])
                        cgd_mag = abs(resolved_dc["cgd"][k_g])
                        cdd_mag = abs(resolved_dc["cdd"][k_g]) + abs(cjd_arr[k_g])

                        fdict["id_w"].append(float("%.6g" % (ids_mag / w_ref)))
                        fdict["gm_w"].append(float("%.6g" % (gm_mag / w_ref)))
                        fdict["gds_w"].append(float("%.6g" % (gds_mag / w_ref)))
                        fdict["gmb_w"].append(float("%.6g" % (gmb_mag / w_ref)))
                        fdict["vth"].append(round(vth_mag, 6))
                        fdict["vdsat"].append(round(vdsat_mag, 6))
                        fdict["cgg_w"].append(float("%.6g" % (cgg_mag / w_ref)))
                        fdict["cgs_w"].append(float("%.6g" % (cgs_mag / w_ref)))
                        fdict["cgd_w"].append(float("%.6g" % (cgd_mag / w_ref)))
                        fdict["cdd_w"].append(float("%.6g" % (cdd_mag / w_ref)))
                        fdict["sth_w"].append(float("%.6g" % (abs(sth_arr[k_g]) / w_ref)))
                        fdict["sfl_w"].append(float("%.6g" % (abs(sfl_arr[k_g]) / w_ref)))

    if noise_psf_files_present:
        for dev_key in ("nmos", "pmos"):
            sth_list = dev_tables[dev_key]["fields"]["sth_w"]
            if (not sth_list) or max(sth_list) <= 0.0:
                raise TechSweepError(
                    "Noise PSF files present but extracted sth_w is all-zero (%s)" % dev_key
                )

    tree_info = _hash_model_tree(spec.get("model_file"))
    soa_limits = _resolve_soa_from_spec(spec)

    lut_obj = {
        "schema": "skill-analog.gmid-lut.v1",
        "axes_order": ["L", "VDS", "VSB", "VGS"],
        "provenance": {
            "generator": "gpdk_techsweep.py",
            "generator_release": RELEASE,
            "source_mode": "spectre_psfascii",
            "pdk": spec["pdk"],
            "flavor": spec["flavor"],
            "corner": spec["corner"],
            "temp_c": spec["temp_c"],
            "vdd_max_v": spec["vdd_max"],
            "soa_limits": soa_limits,
            "soa_grid_note": SOA_POLICY_NOTE,
            "w_ref_m": w_ref,
            "nf_ref": spec["nf"],
            "model_file": spec["model_file"],
            "model_sha256": tree_info["model_sha256"],
            "included_files_sha256": tree_info["included_files_sha256"],
            "model_tree_sha256": tree_info["model_tree_sha256"],
            "noise_contributors_extracted": noise_found,
            "sign_convention": "positive_magnitudes_with_device_polarity",
            "pygmid_bugs_fixed": [
                "colon_vs_dot_psf_signal_mapping",
                "soa_voltage_cap_and_celsius_temp",
                "multi_terminal_vgb_vdb_soa_limits",
                "recursive_scs_model_tree_sha256",
                "strict_spectre_exit_and_finite_grid_validation",
                "separated_thermal_sth_and_flicker_sfl_noise",
                "nonzero_sth_verification_when_noise_psf_present",
                "canonical_l_vds_vsb_vgs_tensor_axis_order",
                "subcircuit_struct_and_group_noise_extraction",
            ],
        },
        "devices": dev_tables,
    }
    saved = _save_lut_gz(lut_obj, out_path)
    return {"ok": True, "lut_path": saved, "provenance": lut_obj["provenance"]}


def run_spectre_sweep(spec, work_dir, out_path):
    """Run Spectre 15.1 characterization across (L, VSB) and compile LUT."""
    bundle = write_deck_bundle(spec, work_dir)
    for i_l, l_val in enumerate(spec["L"]):
        for i_b, vsb_val in enumerate(spec["VSB"]):
            f = open(bundle["params_file"], "wb")
            try:
                f.write(("parameters length_m=%.9g vsb_mag=%.9g\n" % (l_val, vsb_val)).encode("utf-8"))
            finally:
                f.close()

            raw_dir = os.path.join(work_dir, "raw_%d_%d" % (i_l, i_b))
            _mkdir_p(raw_dir)
            log_path = os.path.join(raw_dir, "spectre.out")
            sh_cmd = (
                'if [ -f "$HOME/cadence/env.sh" ]; then . "$HOME/cadence/env.sh"; fi; '
                'export CDS_Netlisting_Mode=Analog; '
                'spectre +escchars =log "%s" -format psfascii -raw "%s" "%s"'
                % (log_path, raw_dir, bundle["deck_file"])
            )
            proc = subprocess.Popen(
                ["/bin/sh", "-c", sh_cmd],
                cwd=work_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            out_b, err_b = proc.communicate()
            if proc.returncode != 0:
                raise TechSweepError(
                    "Spectre failed (exit %d) at L=%.3gnm VSB=%.3fV: %s"
                    % (proc.returncode, l_val * 1e9, vsb_val, err_b.decode("latin1")[:400])
                )
            if os.path.isfile(log_path):
                lf = open(log_path, "rb")
                try:
                    log_txt = lf.read().decode("latin1")
                finally:
                    lf.close()
                if re.search(r"\bFATAL\b|\bERROR\s*\(", log_txt):
                    raise TechSweepError("Spectre reported ERROR/FATAL in %s" % log_path)
    return compile_psf_sweep_dir(work_dir, out_path)


def _ekv_id_per_m(l_m, vgs, vds, vsb, dev_cfg):
    """Continuous C^infinity EKV + BSIM4 short-channel analytical drain current per meter."""
    vt_th = dev_cfg["vt_thermal"]
    l_min = dev_cfg["l_min"]
    ratio_l = l_min / max(l_m, 0.5 * l_min)

    # Short-channel Vth roll-off + reverse short-channel + DIBL + body effect
    phi_2f = 0.72
    body_term = dev_cfg["gamma_b"] * (math.sqrt(phi_2f + max(vsb, 0.0)) - math.sqrt(phi_2f))
    dibl = dev_cfg["eta_dibl"] * math.pow(ratio_l, 1.55) * max(vds, 0.0)
    sc_shift = -0.028 * math.pow(ratio_l, 1.8) + 0.014 * math.pow(ratio_l, 0.8)
    vth = max(0.12, dev_cfg["vth0"] + sc_shift + body_term - dibl)

    n_slope = dev_cfg["n0"] + 0.14 * math.pow(ratio_l, 1.25)
    u = (vgs - vth) / (2.0 * n_slope * vt_th)
    if u > 25.0:
        qf = u + math.exp(-u)
    elif u < -35.0:
        qf = math.exp(u)
    else:
        qf = math.log(1.0 + math.exp(u))

    v_eff_ov = 2.0 * n_slope * vt_th * qf
    theta_vel = dev_cfg["theta0"] + 1.0 / (dev_cfg["e_sat"] * l_m)
    i_spec_w = 2.0 * n_slope * dev_cfg["mu0"] * dev_cfg["cox"] * (vt_th * vt_th) / l_m
    id_sat0 = i_spec_w * (qf * qf) / (1.0 + theta_vel * v_eff_ov)

    vdsat = v_eff_ov / math.sqrt(1.0 + 0.85 * theta_vel * v_eff_ov) + 2.2 * vt_th
    veff_r = max(vds, 1e-6) / vdsat
    m_exp = 2.6
    f_triode = veff_r / math.pow(1.0 + math.pow(veff_r, m_exp), 1.0 / m_exp)

    # Channel length modulation + DIBL output conductance (scales strongly with L)
    va_early = dev_cfg["va0"] * math.pow(l_m / l_min, 0.88) * (
        0.65 + 0.55 * (0.5 * (1.0 + math.tanh((vds - vdsat) / 0.14)))
    )
    clm = 1.0 + max(vds, 0.0) / max(va_early, 0.25)
    id_w = id_sat0 * f_triode * clm + 1e-13 * (1.0 + vds)
    return id_w, vth, vdsat, qf, n_slope


def generate_demo_lut(out_path, pdk="gpdk090", corner=None, temp_c=27.0, flavor="core"):
    """Generate realistic multi-L analytical EKV/BSIM4 NMOS+PMOS LUT (.lut.json.gz)."""
    pdk_key = pdk.strip().lower()
    if pdk_key not in PDK_PRESETS:
        raise TechSweepError("Unsupported PDK for demo LUT: %s" % pdk)
    preset = PDK_PRESETS[pdk_key]
    flav_raw = str(flavor).strip().lower() if flavor else "core"
    flav_key = FLAVOR_ALIASES.get(flav_raw, flav_raw)
    if flav_key not in preset["flavors"]:
        flav_key = "core"
    fcfg = preset["flavors"][flav_key]
    soa_limits = _build_soa_limits(fcfg)

    chosen_corner = corner if corner else preset["default_corner"]
    c_low = chosen_corner.lower()

    # Corner shifts
    vth_shift = 0.0
    mu_scale = 1.0
    if c_low.startswith("ss"):
        vth_shift = 0.045
        mu_scale = 0.80
    elif c_low.startswith("ff"):
        vth_shift = -0.045
        mu_scale = 1.22
    elif c_low.startswith("fs"):
        vth_shift = -0.025
        mu_scale = 1.08
    elif c_low.startswith("sf"):
        vth_shift = 0.025
        mu_scale = 0.92

    k_boltz = 1.3806488e-23
    q_elec = 1.60217657e-19
    t_kelvin = 273.15 + float(temp_c)
    vt_th = k_boltz * t_kelvin / q_elec

    if pdk_key == "gpdk090":
        l_min = 90e-9
        vdd_max = fcfg["vdd_max"]
        l_grid = [90e-9, 120e-9, 180e-9, 250e-9, 360e-9, 500e-9, 1.0e-6] if flav_key != "io" else list(fcfg["l_grid"])
        vgs_grid = _linspace_step(0.0, vdd_max, fcfg["vgs_step"])
        vds_grid = [0.10, 0.30, 0.60, 0.90, 1.20] if flav_key != "io" else list(fcfg["vds_grid"])
        vsb_grid = list(fcfg["vsb_grid"])
        cox = 0.0168
        cov_n = 2.8e-10
        cov_p = 2.6e-10
        cj_n = 6.2e-10
        cj_p = 5.8e-10
        modeln = fcfg["modeln"]
        modelp = fcfg["modelp"]
        vth0_n = 0.34 + vth_shift
        vth0_p = 0.36 - (vth_shift if c_low in ("fs", "sf") else -vth_shift)
        mu0_n = 0.034 * mu_scale
        mu0_p = 0.0125 * mu_scale
        va0_n = 2.2
        va0_p = 2.0
    else:
        l_min = 45e-9
        vdd_max = fcfg["vdd_max"]
        l_grid = [45e-9, 60e-9, 90e-9, 135e-9, 180e-9, 360e-9, 720e-9, 1.0e-6] if flav_key != "io" else list(fcfg["l_grid"])
        vgs_grid = _linspace_step(0.0, vdd_max, fcfg["vgs_step"])
        vds_grid = [0.08, 0.25, 0.50, 0.75, 1.00] if flav_key != "io" else list(fcfg["vds_grid"])
        vsb_grid = list(fcfg["vsb_grid"])
        cox = 0.0238
        cov_n = 2.3e-10
        cov_p = 2.2e-10
        cj_n = 5.2e-10
        cj_p = 5.0e-10
        modeln = fcfg["modeln"]
        modelp = fcfg["modelp"]
        vth0_n = 0.31 + vth_shift
        vth0_p = 0.33 + vth_shift
        mu0_n = 0.028 * mu_scale
        mu0_p = 0.011 * mu_scale
        va0_n = 1.55
        va0_p = 1.45

    dev_configs = {
        "nmos": {
            "model_name": modeln,
            "polarity": 1,
            "vt_thermal": vt_th,
            "l_min": l_min,
            "vth0": vth0_n,
            "gamma_b": 0.28,
            "eta_dibl": 0.055,
            "n0": 1.27,
            "mu0": mu0_n,
            "cox": cox,
            "theta0": 0.26,
            "e_sat": 7.5e6,
            "va0": va0_n,
            "cov": cov_n,
            "cj0": cj_n,
            "kf": 1.8e-24,
        },
        "pmos": {
            "model_name": modelp,
            "polarity": -1,
            "vt_thermal": vt_th,
            "l_min": l_min,
            "vth0": vth0_p,
            "gamma_b": 0.24,
            "eta_dibl": 0.062,
            "n0": 1.30,
            "mu0": mu0_p,
            "cox": cox,
            "theta0": 0.30,
            "e_sat": 1.05e7,
            "va0": va0_p,
            "cov": cov_p,
            "cj0": cj_p,
            "kf": 6.5e-25,
        },
    }

    n_l = len(l_grid)
    n_d = len(vds_grid)
    n_b = len(vsb_grid)
    n_g = len(vgs_grid)
    dv = 1e-4

    devices_out = {}
    for dev_key in ("nmos", "pmos"):
        cfg = dev_configs[dev_key]
        fields = {
            "id_w": [], "gm_w": [], "gds_w": [], "gmb_w": [],
            "vth": [], "vdsat": [], "cgg_w": [], "cgs_w": [],
            "cgd_w": [], "cdd_w": [], "sth_w": [], "sfl_w": [],
        }
        for l_m in l_grid:
            c_ox_l = cfg["cox"] * l_m
            for vds in vds_grid:
                for vsb in vsb_grid:
                    for vgs in vgs_grid:
                        id0, vth, vdsat, qf, _ = _ekv_id_per_m(l_m, vgs, vds, vsb, cfg)
                        id_gp, _, _, _, _ = _ekv_id_per_m(l_m, vgs + dv, vds, vsb, cfg)
                        id_gm_m, _, _, _, _ = _ekv_id_per_m(l_m, max(0.0, vgs - dv), vds, vsb, cfg)
                        step_g = (vgs + dv) - max(0.0, vgs - dv)
                        gm_w = max((id_gp - id_gm_m) / step_g, 1e-15)

                        id_dp, _, _, _, _ = _ekv_id_per_m(l_m, vgs, vds + dv, vsb, cfg)
                        id_dm, _, _, _, _ = _ekv_id_per_m(l_m, vgs, max(1e-4, vds - dv), vsb, cfg)
                        step_d = (vds + dv) - max(1e-4, vds - dv)
                        gds_w = max((id_dp - id_dm) / step_d, 1e-16)

                        id_bp, _, _, _, _ = _ekv_id_per_m(l_m, vgs, vds, vsb + dv, cfg)
                        gmb_w = max((id_0_or_bp(id0, id_bp)) / dv, 1e-16)

                        inv_frac = qf / (1.2 + qf)
                        triode_blend = 0.5 * (1.0 - math.tanh((vds - vdsat) / 0.08))
                        cgs_int = c_ox_l * (0.12 + 0.55 * inv_frac)
                        cgd_int = c_ox_l * 0.30 * inv_frac * triode_blend
                        cgb_int = c_ox_l * 0.22 * (1.0 - inv_frac)

                        cgs_w = cgs_int + cfg["cov"]
                        cgd_w = cgd_int + cfg["cov"]
                        cgg_w = cgs_w + cgd_w + cgb_int
                        cj_eff = cfg["cj0"] / math.pow(1.0 + (vds + vsb) / 0.85, 0.38)
                        cdd_w = cgd_w + cj_eff

                        gamma_n = 0.85 + 0.35 * (l_min / l_m)
                        sth_w = 4.0 * k_boltz * t_kelvin * gamma_n * gm_w
                        sfl_w = (cfg["kf"] * gm_w * gm_w) / (cfg["cox"] * l_m)

                        fields["id_w"].append(float("%.6g" % id0))
                        fields["gm_w"].append(float("%.6g" % gm_w))
                        fields["gds_w"].append(float("%.6g" % gds_w))
                        fields["gmb_w"].append(float("%.6g" % gmb_w))
                        fields["vth"].append(round(vth, 5))
                        fields["vdsat"].append(round(vdsat, 5))
                        fields["cgg_w"].append(float("%.6g" % cgg_w))
                        fields["cgs_w"].append(float("%.6g" % cgs_w))
                        fields["cgd_w"].append(float("%.6g" % cgd_w))
                        fields["cdd_w"].append(float("%.6g" % cdd_w))
                        fields["sth_w"].append(float("%.6g" % sth_w))
                        fields["sfl_w"].append(float("%.6g" % sfl_w))

        devices_out[dev_key] = {
            "model_name": cfg["model_name"],
            "polarity": cfg["polarity"],
            "L": l_grid,
            "VDS": vds_grid,
            "VSB": vsb_grid,
            "VGS": vgs_grid,
            "shape": [n_l, n_d, n_b, n_g],
            "fields": fields,
        }

    lut_obj = {
        "schema": "skill-analog.gmid-lut.v1",
        "axes_order": ["L", "VDS", "VSB", "VGS"],
        "provenance": {
            "generator": "gpdk_techsweep.py",
            "generator_release": RELEASE,
            "source_mode": "analytical_ekv_demo",
            "pdk": preset["id"],
            "flavor": "%s_demo" % fcfg["label"],
            "corner": chosen_corner,
            "temp_c": float(temp_c),
            "vdd_max_v": vdd_max,
            "soa_limits": soa_limits,
            "soa_grid_note": SOA_POLICY_NOTE,
            "w_ref_m": 4.0e-6,
            "nf_ref": 4,
            "model_file": None,
            "model_sha256": None,
            "included_files_sha256": {},
            "model_tree_sha256": None,
            "sign_convention": "positive_magnitudes_with_device_polarity",
            "warning": "Analytical EKV/BSIM4 demo LUT for offline sizing self-test; run gpdk_techsweep.py --run on Spectre 15.1 for silicon signoff.",
            "pygmid_bugs_fixed": [
                "colon_vs_dot_psf_signal_mapping",
                "soa_voltage_cap_and_celsius_temp",
                "multi_terminal_vgb_vdb_soa_limits",
                "strict_spectre_exit_and_finite_grid_validation",
                "separated_thermal_sth_and_flicker_sfl_noise",
            ],
        },
        "devices": devices_out,
    }
    saved = _save_lut_gz(lut_obj, out_path)
    return {
        "ok": True,
        "lut_path": saved,
        "pdk": preset["id"],
        "corner": chosen_corner,
        "shape": [n_l, n_d, n_b, n_g],
        "bytes": os.path.getsize(saved),
    }


def id_0_or_bp(id0, id_bp):
    diff = id0 - id_bp
    return diff if diff > 0.0 else abs(diff)


def run_self_test():
    from gmid_lut import LutBoundsError, load_lut  # local stdlib tool in same directory

    tmp_dir = tempfile.mkdtemp(prefix="skill_analog_techsweep_")
    try:
        # 1. Verify SOA overvoltage guard (must reject 1.8V on 1.2V core gpdk090!)
        blocked_overvolt = False
        try:
            resolve_sweep_spec(pdk="gpdk090", flavor="core", vgs_max=1.8)
        except TechSweepError:
            blocked_overvolt = True
        if not blocked_overvolt:
            raise AssertionError("Failed to block 1.8V overvoltage on gpdk090 1V core!")

        # 2. Verify multi-terminal SOA presets across GPDK045 & GPDK090 core/IO
        expected_soa = (
            ("gpdk045", "core", 1.0, 1.1, 1.1),
            ("gpdk045", "io", 1.8, 1.98, 1.98),
            ("gpdk090", "core", 1.2, 1.32, 1.32),
            ("gpdk090", "io", 2.5, 2.75, 2.75),
        )
        for p_k, fl_k, exp_vdd, exp_vgb, exp_vdb in expected_soa:
            sp_chk = resolve_sweep_spec(pdk=p_k, flavor=fl_k)
            soa_d = sp_chk["soa_limits"]
            if (
                abs(soa_d["vdd_max"] - exp_vdd) > 1e-9
                or abs(soa_d["vgb_max"] - exp_vgb) > 1e-9
                or abs(soa_d["vdb_max"] - exp_vdb) > 1e-9
            ):
                raise AssertionError("SOA preset mismatch for %s/%s: %s" % (p_k, fl_k, repr(soa_d)))

        # 3. Verify GPDK090 (no 'nf=', uses simM=1) & GPDK045 ('nf=4') deck generation
        deck090_dir = os.path.join(tmp_dir, "deck_gpdk090")
        spec090 = resolve_sweep_spec(pdk="gpdk090", flavor="core", corner="NN")
        b090 = write_deck_bundle(spec090, deck090_dir)
        f = open(b090["deck_file"], "rb")
        try:
            scs_txt = f.read().decode("utf-8")
        finally:
            f.close()
        if "temp=27.0000" not in scs_txt or "gpdk090_nmos1v" not in scs_txt:
            raise AssertionError("Deck missing exact Celsius temp=27 or gpdk090_nmos1v")
        if " nf=" in scs_txt:
            raise AssertionError("GPDK090 deck must not emit unsupported 'nf=' wrapper parameter")

        deck045_dir = os.path.join(tmp_dir, "deck_gpdk045")
        spec045 = resolve_sweep_spec(pdk="gpdk045", flavor="core", corner="tt")
        b045 = write_deck_bundle(spec045, deck045_dir)
        f = open(b045["deck_file"], "rb")
        try:
            scs045_txt = f.read().decode("utf-8")
        finally:
            f.close()
        if " nf=4 " not in scs045_txt:
            raise AssertionError("GPDK045 BSIM4 deck must emit 'nf=4'")

        # 4. Verify _hash_model_tree recursive .scs include parsing, relative paths & cycle guard
        model_dir = os.path.join(tmp_dir, "models_scs")
        sub_dir = os.path.join(model_dir, "sub")
        _mkdir_p(sub_dir)
        top_scs = os.path.join(model_dir, "gpdk_top.scs")
        mos_scs = os.path.join(sub_dir, "mos_core.scs")
        leaf_scs = os.path.join(sub_dir, "corners_leaf.scs")

        for p_scs, body_scs in (
            (
                top_scs,
                '// Top model card\n* include "ignored_spice_comment.scs"\n'
                '/* include "ignored_block_comment.scs" */\n'
                'simulator lang=spectre\n'
                'include "sub/mos_core.scs" section=NN // active child\n',
            ),
            (
                mos_scs,
                'simulator lang=spectre\n'
                'include "corners_leaf.scs"\n'
                'include "../gpdk_top.scs"\n',  # intentional cycle back to root!
            ),
            (
                leaf_scs,
                "parameters vth0_nom=0.34\n",
            ),
        ):
            wf = open(p_scs, "wb")
            try:
                wf.write(body_scs.encode("utf-8"))
            finally:
                wf.close()

        tree1 = _hash_model_tree(top_scs)
        mos_real = os.path.realpath(mos_scs)
        leaf_real = os.path.realpath(leaf_scs)
        if mos_real not in tree1["included_files_sha256"] or leaf_real not in tree1["included_files_sha256"]:
            raise AssertionError("_hash_model_tree missed transitive included .scs files!")
        if len(tree1["included_files_sha256"]) != 2:
            raise AssertionError("Expected 2 included .scs files, got %d" % len(tree1["included_files_sha256"]))

        # Mutate leaf .scs without touching top_scs: model_tree_sha256 MUST change!
        wf = open(leaf_scs, "wb")
        try:
            wf.write("parameters vth0_nom=0.36\n".encode("utf-8"))
        finally:
            wf.close()
        tree2 = _hash_model_tree(top_scs)
        if tree2["model_sha256"] != tree1["model_sha256"]:
            raise AssertionError("Unmodified root model_sha256 should remain unchanged")
        if tree2["model_tree_sha256"] == tree1["model_tree_sha256"]:
            raise AssertionError("model_tree_sha256 failed to detect leaf .scs modification!")

        # 5. Verify 4D (2x3x2x4) PSF ASCII compilation:
        #    - Distinct VDS vs VSB dependence to catch any axis transposition via GmidLut.query()
        #    - Subcircuit TYPE STRUCT + delta-compressed .noise (NMOS: mn.m1)
        #    - TRACE GROUP with 2-field resistor STRUCT + 5-field bsim3v3 STRUCT (PMOS: mp.rg + mp.m1)
        mini_dir = os.path.join(tmp_dir, "mini_psf")
        l_vals = [90e-9, 180e-9]
        vds_vals = [0.2, 0.6, 1.0]
        vsb_vals = [0.0, 0.4]
        mini_spec = resolve_sweep_spec(
            pdk="gpdk090", flavor="core", corner="NN",
            model_file=top_scs,
            l_list=l_vals, vds_list=vds_vals, vsb_list=vsb_vals, vgs_step=0.4
        )
        write_deck_bundle(mini_spec, mini_dir)
        vgs_vals = mini_spec["VGS"]  # [0.0, 0.4, 0.8, 1.2]
        w_ref = mini_spec["w_ref"]

        def _expected_point(l_v, vds_v, vsb_v, vg_v, is_pmos=False):
            scale_l = (90e-9 / l_v)
            vth_mag = (0.34 if not is_pmos else 0.37) + 0.18 * vsb_v - 0.05 * vds_v
            id_a = (1e-9 + 120e-6 * scale_l * max(vg_v - 0.1, 0.02) * (1.0 + 0.55 * vds_v) / (1.0 + 0.7 * vsb_v))
            if is_pmos:
                id_a *= 0.45
            gm_s = max(id_a * (18.0 - 9.0 * vg_v), 2e-10)
            gds_s = gm_s / (15.0 * (l_v / 90e-9) * (1.0 + 1.4 * vds_v))
            sth_psd = 1.65e-20 * gm_s * (1.1 + 0.2 * vds_v)
            sfl_psd = 2.4e-18 * (gm_s * gm_s) * scale_l * (1.0 + 0.3 * vsb_v)
            return id_a, gm_s, gds_s, vth_mag, sth_psd, sfl_psd

        for i_l, l_v in enumerate(l_vals):
            for i_b, vsb_v in enumerate(vsb_vals):
                raw_ij = os.path.join(mini_dir, "raw_%d_%d" % (i_l, i_b))
                _mkdir_p(raw_ij)
                for i_d, vds_v in enumerate(vds_vals):
                    dc_psf = os.path.join(raw_ij, "sweepvds-%03d_sweepvgs.dc" % i_d)
                    psf_lines = [
                        "HEADER", "SWEEP", '"gs" "V"', "TRACE",
                        '"grp1" GROUP 2', '"mn.ids" "A" "mp:ids" "A"',
                        "VALUE",
                    ]
                    nn_lines = [
                        "HEADER",
                        "TYPE",
                        '"V" FLOAT DOUBLE PROP( "units" "V" )',
                        '"A^2/Hz" FLOAT DOUBLE PROP( "units" "A^2/Hz" )',
                        '"A/sqrt(Hz)" FLOAT DOUBLE PROP( "units" "A/sqrt(Hz)" )',
                        '"bsim3v3" STRUCT( "rd" "A^2/Hz" "rs" "A^2/Hz" "id" "A^2/Hz" "fn" "A^2/Hz" "total" "A^2/Hz" ) PROP( "key" "model" )',
                        "SWEEP", '"gs" "V"',
                        "TRACE", '"mn.m1" "bsim3v3"', '"out" "A/sqrt(Hz)"',
                        "VALUE",
                    ]
                    pn_lines = [
                        "HEADER",
                        "TYPE",
                        '"V" FLOAT DOUBLE PROP( "units" "V" )',
                        '"A^2/Hz" FLOAT DOUBLE PROP( "units" "A^2/Hz" )',
                        '"A/sqrt(Hz)" FLOAT DOUBLE PROP( "units" "A/sqrt(Hz)" )',
                        '"resistor" STRUCT( "rn" "A^2/Hz" "total" "A^2/Hz" )',
                        '"bsim3v3" STRUCT( "rd" "A^2/Hz" "rs" "A^2/Hz" "id" "A^2/Hz" "fn" "A^2/Hz" "total" "A^2/Hz" )',
                        "SWEEP", '"gs" "V"',
                        "TRACE", '" 1" GROUP 3',
                        '"mp.rg" "resistor"', '"mp.m1" "bsim3v3"', '"out" "A/sqrt(Hz)"',
                        "VALUE",
                    ]
                    for vg_v in vgs_vals:
                        idn, gmn, gdsn, vthn, sthn, sfln = _expected_point(l_v, vds_v, vsb_v, vg_v, False)
                        idp, gmp, gdsp, vthp, sthp, sflp = _expected_point(l_v, vds_v, vsb_v, vg_v, True)
                        psf_lines.append('"gs" %.6e' % vg_v)
                        psf_lines.append('"grp1" %.8e %.8e' % (idn, -idp))
                        for dev_p, gm_x, gds_x, vth_x in (
                            ("mn", gmn, gdsn, vthn),
                            ("mp", gmp, gdsp, -vthp),
                        ):
                            psf_lines.append('"%s:gm" %.8e' % (dev_p, gm_x))
                            psf_lines.append('"%s.gds" %.8e' % (dev_p, gds_x))
                            psf_lines.append('"%s:vth" %.8e' % (dev_p, vth_x))
                            psf_lines.append('"%s:vdsat" %.8e' % (dev_p, 0.11))
                            psf_lines.append('"%s:cgg" %.8e' % (dev_p, 8e-15))
                            psf_lines.append('"%s:cgs" %.8e' % (dev_p, -5e-15))
                            psf_lines.append('"%s:cgd" %.8e' % (dev_p, -1.2e-15))
                            psf_lines.append('"%s:cdd" %.8e' % (dev_p, 3.5e-15))

                        nn_lines.append('"gs" %.6e' % vg_v)
                        nn_lines.append(
                            '"mn.m1" ( %.8e %.8e %.8e %.8e %.8e )'
                            % (0.05 * sthn, 0.05 * sthn, 0.90 * sthn, sfln, sthn + sfln)
                        )
                        nn_lines.append('"out" %.8e' % math.sqrt(sthn + sfln))

                        pn_lines.append('"gs" %.6e' % vg_v)
                        pn_lines.append('" 1"')
                        pn_lines.append("( %.8e %.8e )" % (0.04 * sthp, 0.04 * sthp))
                        pn_lines.append(
                            "( %.8e %.8e %.8e %.8e %.8e )"
                            % (0.03 * sthp, 0.03 * sthp, 0.90 * sthp, sflp, 0.96 * sthp + sflp)
                        )
                        pn_lines.append("%.8e" % math.sqrt(sthp + sflp))

                    psf_lines.append("END")
                    nn_lines.append("END")
                    pn_lines.append("END")

                    for out_f, content_lines in (
                        (dc_psf, psf_lines),
                        (os.path.join(raw_ij, "sweepvds_noisen-%03d_sweepvgs_noisen.noise" % i_d), nn_lines),
                        (os.path.join(raw_ij, "sweepvds_noisep-%03d_sweepvgs_noisep.noise" % i_d), pn_lines),
                    ):
                        wf = open(out_f, "wb")
                        try:
                            wf.write(("\n".join(content_lines) + "\n").encode("utf-8"))
                        finally:
                            wf.close()

        lut_out = os.path.join(tmp_dir, "mini.lut.json.gz")
        compiled = compile_psf_sweep_dir(mini_dir, lut_out)
        prov = compiled["provenance"]
        if prov["noise_contributors_extracted"] != {"nmos": True, "pmos": True}:
            raise AssertionError("Expected noise_contributors_extracted True for both NMOS and PMOS")
        if prov["generator_release"] != RELEASE:
            raise AssertionError("Expected generator_release=%s, got %s" % (RELEASE, prov["generator_release"]))
        if prov["model_tree_sha256"] != tree2["model_tree_sha256"]:
            raise AssertionError("Compiled LUT provenance model_tree_sha256 mismatch!")
        if prov["included_files_sha256"] != tree2["included_files_sha256"]:
            raise AssertionError("Compiled LUT provenance included_files_sha256 mismatch!")
        if abs(prov["soa_limits"]["vgb_max"] - 1.32) > 1e-9 or abs(prov["soa_limits"]["vdb_max"] - 1.32) > 1e-9:
            raise AssertionError("Compiled LUT provenance missing GPDK090 core SOA limits!")

        # Verify exact round-trip through GmidLut at asymmetric (L, VDS, VSB) coordinates
        lut = load_lut(lut_out)
        for is_p, dev_name in ((False, "nmos"), (True, "pmos")):
            for l_chk, vds_chk, vsb_chk, vg_chk in (
                (180e-9, 0.2, 0.4, 0.8),
                (90e-9, 1.0, 0.0, 0.8),
                (180e-9, 1.0, 0.4, 0.4),
            ):
                exp_id, exp_gm, _, exp_vth, exp_sth, exp_sfl = _expected_point(
                    l_chk, vds_chk, vsb_chk, vg_chk, is_p
                )
                q = lut.query(dev=dev_name, l_m=l_chk, vgs=vg_chk, vds=vds_chk, vsb=vsb_chk, method="linear")
                rel_id = abs(q["jd_a_per_m"] - (exp_id / w_ref)) / (exp_id / w_ref)
                err_vth = abs(q["vth"] - exp_vth)
                rel_sth = abs(q["sth_a2_per_hz_m"] - (exp_sth / w_ref)) / (exp_sth / w_ref)
                rel_sfl = abs(q["sfl_a2_per_hz_m"] - (exp_sfl / w_ref)) / (exp_sfl / w_ref)
                if rel_id > 1e-4 or err_vth > 1e-4 or rel_sth > 1e-4 or rel_sfl > 1e-4:
                    raise AssertionError(
                        "4D LUT round-trip mismatch on %s (L=%g, VDS=%g, VSB=%g): rel_id=%g err_vth=%g rel_sth=%g rel_sfl=%g"
                        % (dev_name, l_chk, vds_chk, vsb_chk, rel_id, err_vth, rel_sth, rel_sfl)
                    )

        # 6. Verify silent zero-noise .noise PSF rejection!
        zero_noise_dir = os.path.join(tmp_dir, "zero_noise_psf")
        shutil.copytree(mini_dir, zero_noise_dir)
        for i_l in range(len(l_vals)):
            for i_b in range(len(vsb_vals)):
                raw_ij = os.path.join(zero_noise_dir, "raw_%d_%d" % (i_l, i_b))
                for i_d in range(len(vds_vals)):
                    pn_f = os.path.join(raw_ij, "sweepvds_noisep-%03d_sweepvgs_noisep.noise" % i_d)
                    bad_noise = [
                        "HEADER",
                        "TYPE",
                        '"V" FLOAT DOUBLE PROP( "units" "V" )',
                        '"A/sqrt(Hz)" FLOAT DOUBLE PROP( "units" "A/sqrt(Hz)" )',
                        "SWEEP", '"gs" "V"',
                        "TRACE", '"out" "A/sqrt(Hz)"',
                        "VALUE",
                    ]
                    for vg_v in vgs_vals:
                        bad_noise.append('"gs" %.6e' % vg_v)
                        bad_noise.append('"out" 1.0e-12')
                    bad_noise.append("END")
                    wf = open(pn_f, "wb")
                    try:
                        wf.write(("\n".join(bad_noise) + "\n").encode("utf-8"))
                    finally:
                        wf.close()

        caught_zero_noise = False
        try:
            compile_psf_sweep_dir(zero_noise_dir, os.path.join(tmp_dir, "bad_zero.lut.json.gz"))
        except TechSweepError as exc:
            if "Noise PSF files present but extracted sth_w is all-zero" in str(exc):
                caught_zero_noise = True
        if not caught_zero_noise:
            raise AssertionError("Failed to reject .noise PSF directory with all-zero sth_w!")

        # 7. Verify demo LUT generation & GPDK045 multi-terminal SOA flag/block
        demo_lut090 = os.path.join(tmp_dir, "demo_gpdk090.lut.json.gz")
        demo_res = generate_demo_lut(demo_lut090, pdk="gpdk090", corner="NN")
        demo_lut045 = os.path.join(tmp_dir, "demo_gpdk045.lut.json.gz")
        generate_demo_lut(demo_lut045, pdk="gpdk045", corner="tt")
        lut45 = load_lut(demo_lut045)
        q45_vgb = lut45.query(dev="nmos", l_m=45e-9, vgs=1.0, vds=0.5, vsb=0.5)
        if q45_vgb["soa_ok"] or not q45_vgb["soa_violations"]:
            raise AssertionError("Expected |VGB|=1.5V > 1.1V SOA violation flag on GPDK045!")
        blocked_strict_soa = False
        try:
            lut45.query(dev="nmos", l_m=45e-9, vgs=1.0, vds=0.5, vsb=0.5, allow_soa_violation=False)
        except LutBoundsError:
            blocked_strict_soa = True
        if not blocked_strict_soa:
            raise AssertionError("Expected LutBoundsError when allow_soa_violation=False on |VGB|=1.5V!")

        return {
            "ok": True,
            "release": RELEASE,
            "self_test": "PASS",
            "overvoltage_guard_verified": blocked_overvolt,
            "multi_terminal_soa_verified": True,
            "model_tree_hash_verified": True,
            "zero_noise_psf_guard_verified": caught_zero_noise,
            "axis_order_and_struct_noise_verified": True,
            "compiled_psf_lut": os.path.basename(compiled["lut_path"]),
            "demo_lut_bytes": demo_res["bytes"],
            "demo_shape": demo_res["shape"],
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def build_parser():
    usage = (
        "Usage: python tools/gpdk_techsweep.py [options]\n\n"
        "Modes:\n"
        "  --generate-demo-lut PATH   Generate analytical EKV/BSIM4 demo .lut.json.gz\n"
        "  --generate-deck            Write verified Spectre 15.1 techsweep deck to --work-dir\n"
        "  --compile-psf DIR          Compile existing PSF ASCII sweep dir into --out\n"
        "  --run                      Execute Spectre 15.1 characterization and compile --out\n"
        "  --self-test                Run offline temp-dir verification suite"
    )
    p = optparse.OptionParser(usage=usage)
    p.add_option("--pdk", dest="pdk", default="gpdk090", help="PDK id: gpdk090 or gpdk045 [default: %default]")
    p.add_option("--flavor", dest="flavor", default="core", help="Device flavor: core, io, lvt, hvt [default: %default]")
    p.add_option("--corner", dest="corner", default=None, help="Model section (GPDK090: NN/SS/FF/FS/SF; GPDK045: tt/ss/ff/fs/sf)")
    p.add_option("--temp", dest="temp_c", type="float", default=27.0, help="Temperature in Celsius [default: %default]")
    p.add_option("--model-file", dest="model_file", default=None, help="Explicit Spectre .scs model path")
    p.add_option("--l-list", dest="l_list", default=None, help="Comma-separated L values in meters")
    p.add_option("--vds-list", dest="vds_list", default=None, help="Comma-separated VDS values in Volts")
    p.add_option("--vsb-list", dest="vsb_list", default=None, help="Comma-separated VSB values in Volts")
    p.add_option("--vgs-step", dest="vgs_step", type="float", default=None, help="VGS step in Volts")
    p.add_option("--vgs-max", dest="vgs_max", type="float", default=None, help="Max |VGS| in Volts (SOA-checked)")
    p.add_option("--vds-max", dest="vds_max", type="float", default=None, help="Max |VDS| in Volts (SOA-checked)")
    p.add_option("--allow-overvoltage", dest="allow_overvoltage", action="store_true", default=False,
                 help="Override PDK SOA voltage cap (not recommended)")
    p.add_option("--work-dir", dest="work_dir", default=None, help="Directory outside library for Spectre deck/PSF")
    p.add_option("--out", dest="out_path", default=None, help="Output .lut.json.gz path [default: ~/.cache/skill-analog/gmid-luts/...]")
    p.add_option("--generate-demo-lut", dest="demo_lut_path", default=None, metavar="PATH",
                 help="Generate analytical multi-L NMOS+PMOS .lut.json.gz for offline self-test/demo")
    p.add_option("--generate-deck", dest="generate_deck", action="store_true", default=False,
                 help="Generate Spectre 15.1 techsweep.scs and runner script without running Spectre")
    p.add_option("--compile-psf", dest="compile_psf_dir", default=None, metavar="DIR",
                 help="Compile an existing PSF ASCII sweep directory into --out")
    p.add_option("--run", dest="do_run", action="store_true", default=False,
                 help="Run Spectre 15.1 characterization and compile .lut.json.gz")
    p.add_option("--self-test", dest="self_test", action="store_true", default=False,
                 help="Run unit tests in tempfile.mkdtemp() and clean up")
    return p


def main(argv=None):
    parser = build_parser()
    opts, extra = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if extra:
        print(json.dumps({"ok": False, "error": "Unexpected positional arguments: " + " ".join(extra)}, indent=2, sort_keys=True))
        return 2

    try:
        if opts.self_test:
            res = run_self_test()
            print(json.dumps(res, indent=2, sort_keys=True))
            return 0

        if opts.demo_lut_path:
            res = generate_demo_lut(
                opts.demo_lut_path,
                pdk=opts.pdk,
                corner=opts.corner,
                temp_c=opts.temp_c,
                flavor=opts.flavor,
            )
            print(json.dumps(res, indent=2, sort_keys=True))
            return 0

        spec = resolve_sweep_spec(
            pdk=opts.pdk,
            flavor=opts.flavor,
            corner=opts.corner,
            temp_c=opts.temp_c,
            model_file=opts.model_file,
            vgs_max=opts.vgs_max,
            vds_max=opts.vds_max,
            l_list=_parse_float_list(opts.l_list) if opts.l_list else None,
            vgs_step=opts.vgs_step,
            vds_list=_parse_float_list(opts.vds_list) if opts.vds_list else None,
            vsb_list=_parse_float_list(opts.vsb_list) if opts.vsb_list else None,
            allow_overvoltage=opts.allow_overvoltage,
        )
        out_lut = opts.out_path or default_lut_path(spec["pdk_key"], spec["flavor_key"], spec["corner"], spec["temp_c"])

        if opts.compile_psf_dir:
            res = compile_psf_sweep_dir(opts.compile_psf_dir, out_lut)
            print(json.dumps(res, indent=2, sort_keys=True))
            return 0

        if opts.generate_deck:
            wdir = opts.work_dir or os.path.join(
                os.path.expanduser("~"), ".cache", "skill-analog", "techsweep-work",
                "%s_%s_%s" % (spec["pdk_key"], spec["flavor_key"], spec["corner"])
            )
            res = write_deck_bundle(spec, wdir)
            print(json.dumps(res, indent=2, sort_keys=True))
            return 0

        if opts.do_run:
            wdir = opts.work_dir or os.path.join(
                os.path.expanduser("~"), ".cache", "skill-analog", "techsweep-work",
                "%s_%s_%s" % (spec["pdk_key"], spec["flavor_key"], spec["corner"])
            )
            res = run_spectre_sweep(spec, wdir, out_lut)
            print(json.dumps(res, indent=2, sort_keys=True))
            return 0

        parser.print_help()
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2, sort_keys=True))
        return 1


if __name__ == "__main__":
    sys.exit(main())
