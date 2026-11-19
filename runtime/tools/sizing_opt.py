#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Physics-Pruned Sensitivity & Constrained Trust-Region / Nelder-Mead Sizing Optimizer.

100% compatible with RHEL 6.5 Python 2.6.6 and Python 3.x using pure standard library
(optparse CLI, zero numpy/scipy, zero f-strings, zero dict/set comprehensions).

Inspired by LEDRO (physics-pruned subspace & sensitivity guidance) and AnalogCoderPro:
  - Stage 1: Evaluates initial gm/ID design point and computes exact finite-difference
    Sensitivity Jacobian (dMetric_i / d ln x_j), ranking which transistor W, L, I_bias,
    or Cc/Rz controls each failing specification, and pruning insensitive variables.
  - Stage 2: Runs Penalty-Barrier Constrained Trust-Region (with Broyden rank-1 Jacobian
    updates) + Physics-Pruned Subspace Nelder-Mead Simplex in normalized log/lin space,
    snaps final geometry to PDK manufacturing grid (5nm), and verifies Worst-Case PVT
    Corners (TT, SS, FF, FS, SF) under a strict hard evaluation budget ceiling.

Release: 2026.11.19.1
"""
from __future__ import division, print_function

import copy
import json
import math
import optparse
import os
import shutil
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True

RELEASE = "2026.11.19.1"
LIBRARY_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
TIMER = getattr(time, "perf_counter", time.time)


class SizingOptError(Exception):
    pass


class _BudgetExhausted(Exception):
    """Internal sentinel raised when eval_cached reaches hard max_evaluations ceiling."""
    pass


def _is_inside(path, base):
    p_norm = os.path.normcase(os.path.realpath(path))
    b_norm = os.path.normcase(os.path.realpath(base))
    return p_norm == b_norm or p_norm.startswith(b_norm.rstrip(os.sep) + os.sep)


def _safe_finite_float(val):
    if val is None or isinstance(val, bool):
        return None
    try:
        f = float(val)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def _clamp(val, lo, hi):
    if val < lo:
        return lo
    if val > hi:
        return hi
    return val


def _validate_step_grid(step_grid, vmin, vmax, label="variable"):
    if step_grid is None:
        return
    if step_grid <= 0.0:
        raise SizingOptError("Invalid non-positive step_grid=%g for %s" % (step_grid, label))
    eps_lo = max(1e-15, 1e-12 * max(abs(vmin), abs(step_grid)))
    eps_hi = max(1e-15, 1e-12 * max(abs(vmax), abs(step_grid)))
    first_grid = math.ceil((vmin - eps_lo) / step_grid) * step_grid
    if first_grid > vmax + eps_hi:
        raise SizingOptError(
            "No valid step_grid=%g multiple inside bounds [%g, %g] for %s"
            % (step_grid, vmin, vmax, label)
        )


def _snap_val(val, step_grid, lo, hi):
    if hi < lo:
        raise SizingOptError("Invalid bounds [%g, %g]: max < min" % (lo, hi))
    v = _clamp(val, lo, hi)
    if step_grid is not None:
        _validate_step_grid(step_grid, lo, hi)
        eps_lo = max(1e-15, 1e-12 * max(abs(lo), abs(step_grid)))
        eps_hi = max(1e-15, 1e-12 * max(abs(hi), abs(step_grid)))
        v = round(v / step_grid) * step_grid
        if v < lo - eps_lo:
            v = math.ceil((lo - eps_lo) / step_grid) * step_grid
        if v > hi + eps_hi:
            v = math.floor((hi + eps_hi) / step_grid) * step_grid
    return _clamp(v, lo, hi)


class DesignSpace(object):
    """Normalized [0, 1]^d log/linear parameter transform + PDK grid snapper."""

    def __init__(self, variables, default_step_grid=None):
        if not isinstance(variables, list) or not variables:
            raise SizingOptError("Problem 'variables' must be a non-empty list.")
        self.vars = []
        for entry in variables:
            name = entry["name"]
            vmin = float(entry["min"])
            vmax = float(entry["max"])
            vinit = float(entry.get("init", math.sqrt(vmin * vmax) if vmin > 0 else 0.5 * (vmin + vmax)))
            scale = str(entry.get("scale", "log")).lower()
            if scale not in ("log", "lin", "linear"):
                raise SizingOptError("Unsupported scale '%s' for variable %s" % (scale, name))
            if scale == "linear":
                scale = "lin"
            if scale == "log" and vmin <= 0.0:
                raise SizingOptError("Log-scaled variable '%s' requires min > 0." % name)
            if vmax <= vmin:
                raise SizingOptError("Variable '%s' requires max > min." % name)
            if "step_grid" in entry:
                step = entry.get("step_grid")
            elif "step_grid_m" in entry:
                step = entry.get("step_grid_m")
            else:
                step = default_step_grid
            if step is None or float(step) == 0.0:
                step_f = None
            else:
                step_f = float(step)
                _validate_step_grid(step_f, vmin, vmax, name)
            self.vars.append({
                "name": name,
                "min": vmin,
                "max": vmax,
                "init": _clamp(vinit, vmin, vmax),
                "scale": scale,
                "step_grid": step_f,
                "span_ln": math.log(vmax / vmin) if scale == "log" else (vmax - vmin),
                "role": entry.get("role", ""),
            })
        self.dim = len(self.vars)

    def x_to_u(self, x_dict):
        u = []
        for spec in self.vars:
            xv = _clamp(float(x_dict[spec["name"]]), spec["min"], spec["max"])
            if spec["scale"] == "log":
                uv = math.log(xv / spec["min"]) / spec["span_ln"]
            else:
                uv = (xv - spec["min"]) / spec["span_ln"]
            u.append(_clamp(uv, 0.0, 1.0))
        return u

    def u_to_x(self, u_vec, snap=False):
        x_out = {}
        for idx, spec in enumerate(self.vars):
            uv = _clamp(float(u_vec[idx]), 0.0, 1.0)
            if spec["scale"] == "log":
                xv = spec["min"] * math.exp(uv * spec["span_ln"])
            else:
                xv = spec["min"] + uv * spec["span_ln"]
            if snap:
                xv = _snap_val(xv, spec["step_grid"], spec["min"], spec["max"])
            x_out[spec["name"]] = xv
        return x_out

    def init_x(self):
        out = {}
        for spec in self.vars:
            out[spec["name"]] = spec["init"]
        return out


# ---------------------------------------------------------------------------
# Built-in Authentic 2-Stage Miller CMOS OTA Analytical Benchmark (GPDK090-like)
# ---------------------------------------------------------------------------

def evaluate_miller_ota_2stage(params, corner="TT"):
    """Evaluate 2-stage NMOS-input / PMOS-CS Miller + Rz OTA across TT/SS/FF/FS/SF.

    Architecture: NMOS input diff-pair (M1/M2, width W_in, length L_ch) with PMOS active
    mirror (M3/M4), NMOS tail source (M5, current I_tail), PMOS common-source 2nd stage
    (M6, width W_cs, length L_ch) biased by NMOS sink (M7, current I_stage2), driving
    C_L = 5 pF with Miller capacitor C_c and series nulling resistor R_z on VDD = 1.2 V.
    """
    c_up = str(corner).strip().upper()
    if c_up in ("TT", "NN"):
        vdd = 1.20
        temp_c = 27.0
        mu_n_fac = 1.00
        vth_n_shift = 0.0
        mu_p_fac = 1.00
        vth_p_shift = 0.0
        r_fac = 1.00
        c_fac = 1.00
    elif c_up == "SS":
        vdd = 1.14
        temp_c = 110.0
        mu_n_fac = 0.77
        vth_n_shift = 0.042
        mu_p_fac = 0.77
        vth_p_shift = 0.042
        r_fac = 1.14
        c_fac = 1.07
    elif c_up == "FF":
        vdd = 1.26
        temp_c = -25.0
        mu_n_fac = 1.24
        vth_n_shift = -0.042
        mu_p_fac = 1.24
        vth_p_shift = -0.042
        r_fac = 0.86
        c_fac = 0.93
    elif c_up == "FS":
        # Fast NMOS / Slow PMOS skewed corner
        vdd = 1.20
        temp_c = 27.0
        mu_n_fac = 1.22
        vth_n_shift = -0.038
        mu_p_fac = 0.79
        vth_p_shift = 0.038
        r_fac = 1.00
        c_fac = 1.00
    elif c_up == "SF":
        # Slow NMOS / Fast PMOS skewed corner
        vdd = 1.20
        temp_c = 27.0
        mu_n_fac = 0.79
        vth_n_shift = 0.038
        mu_p_fac = 1.22
        vth_p_shift = -0.038
        r_fac = 1.00
        c_fac = 1.00
    else:
        raise SizingOptError(
            "Unrecognized corner '%s' in evaluate_miller_ota_2stage (allowed: TT, NN, SS, FF, FS, SF)."
            % str(corner)
        )

    k_b = 1.3806488e-23
    q_e = 1.60217657e-19
    t_k = 273.15 + temp_c
    vt = k_b * t_k / q_e

    w_in = float(params["W_in"])
    l_ch = float(params["L_ch"])
    w_cs = float(params["W_cs"])
    i_tail = float(params["I_tail"])
    i_st2 = float(params["I_stage2"])
    c_c = float(params["C_c"]) * c_fac
    r_z = float(params["R_z"]) * r_fac
    c_load = 5.0e-12

    cox = 0.0168 * c_fac
    n_n = 1.30
    n_p = 1.33
    mu_n = 0.033 * mu_n_fac
    mu_p = 0.0125 * mu_p_fac

    # Stage 1: M1/M2 NMOS diff-pair (ID1 = I_tail / 2)
    id1 = 0.5 * i_tail
    ispec1 = 2.0 * n_n * mu_n * cox * vt * vt * (w_in / l_ch)
    ic1 = id1 / max(ispec1, 1e-18)
    # Continuous EKV moderate-to-strong inversion + velocity saturation
    gms_id1 = 1.0 / (n_n * vt * math.sqrt(0.25 + ic1) + 0.045 * (90e-9 / l_ch) * ic1 * vt)
    gm1 = id1 * gms_id1
    vov1 = 2.0 * n_n * vt * math.log(1.0 + math.sqrt(ic1))
    vdsat1 = max(2.2 * vt, vov1 / math.sqrt(1.0 + 0.35 * vov1))

    # Stage 1 active mirror M3/M4 (scaled proportional to I_tail for matched Vsg6)
    w_m3 = max(4.0e-6, 0.55 * w_cs * (id1 / max(i_st2, 1e-9)))
    ispec3 = 2.0 * n_p * mu_p * cox * vt * vt * (w_m3 / l_ch)
    ic3 = id1 / max(ispec3, 1e-18)
    gm3 = id1 / (n_p * vt * math.sqrt(0.25 + ic3))
    vov3 = 2.0 * n_p * vt * math.log(1.0 + math.sqrt(ic3))
    vdsat3 = max(2.2 * vt, vov3 / math.sqrt(1.0 + 0.30 * vov3))
    vsg3 = (0.36 + vth_p_shift) + vov3

    # Stage 2: M6 PMOS common-source driver (ID6 = I_stage2)
    ispec6 = 2.0 * n_p * mu_p * cox * vt * vt * (w_cs / l_ch)
    ic6 = i_st2 / max(ispec6, 1e-18)
    gms_id6 = 1.0 / (n_p * vt * math.sqrt(0.25 + ic6) + 0.040 * (90e-9 / l_ch) * ic6 * vt)
    gm6 = i_st2 * gms_id6
    vov6 = 2.0 * n_p * vt * math.log(1.0 + math.sqrt(ic6))
    vdsat6 = max(2.2 * vt, vov6 / math.sqrt(1.0 + 0.30 * vov6))
    vsg6 = (0.36 + vth_p_shift) + vov6

    # Tail M5 & Stage-2 sink M7 biased in moderate inversion (Vdsat ~ 0.10V..0.15V)
    vdsat5 = 0.105 + 0.025 * math.sqrt(i_tail / 50e-6)
    vdsat7 = 0.115 + 0.030 * math.sqrt(i_st2 / 150e-6)

    # Headroom / saturation margins at standard NMOS-input VCM = 0.56 * VDD, Vout_DC = 0.5 * VDD
    vcm = 0.56 * vdd
    vgs1 = (0.34 + vth_n_shift) + vov1
    v_tail = vcm - vgs1
    sat_m5 = v_tail - vdsat5
    v_node1 = vdd - vsg6
    sat_m1 = (v_node1 - v_tail) - vdsat1
    sat_m3 = vsg6 - vdsat3
    sat_m6 = (0.5 * vdd) - vdsat6
    sat_m7 = (0.5 * vdd) - vdsat7
    min_sat_margin = min([sat_m1, sat_m3, sat_m5, sat_m6, sat_m7])

    # Output conductances (channel-length modulation scaling with L_ch)
    l_scale = math.pow(l_ch / 90e-9, 0.88)
    va1 = 2.15 * l_scale * (0.5 + 0.5 * math.tanh(max(sat_m1, -0.1) / 0.08 + 0.8))
    va3 = 1.95 * l_scale * (0.5 + 0.5 * math.tanh(max(sat_m3, -0.1) / 0.08 + 0.8))
    va6 = 2.05 * l_scale * (0.5 + 0.5 * math.tanh(max(sat_m6, -0.1) / 0.08 + 0.8))
    va7 = 2.25 * l_scale

    gds1 = id1 / max(va1, 0.25)
    gds3 = id1 / max(va3, 0.25)
    gds6 = i_st2 / max(va6, 0.25)
    gds7 = i_st2 / max(va7, 0.25)

    r1 = 1.0 / (gds1 + gds3)
    r2 = 1.0 / (gds6 + gds7)
    a1 = gm1 * r1
    a2 = gm6 * r2
    a0 = max(a1 * a2, 1e-6)
    dc_gain_db = 20.0 * math.log10(a0)

    # Node parasitic capacitances
    c1 = (0.67 * cox * w_cs * l_ch) + (9.0e-10 * (w_in + w_m3 + w_cs))
    c2 = c_load + (9.5e-10 * w_cs) + 15e-15

    # Exact 3-pole, 1-zero Miller + Nulling-Resistor transfer function H(jw)
    # Numerator: a0 * (1 + s * C_c * (R_z - 1/gm6))
    # Denominator: 1 + b1*s + b2*s^2 + b3*s^3
    z_tau = c_c * (r_z - (1.0 / gm6))
    b1 = r1 * (c1 + c_c * (1.0 + gm6 * r2)) + r2 * (c2 + c_c) + r_z * c_c
    b2 = (
        r1 * r2 * (c1 * c2 + c1 * c_c + c2 * c_c)
        + c_c * r_z * (r1 * c1 + r2 * c2 + gm6 * r1 * r2 * (c1 + c2) * 0.04)
    )
    b3 = r1 * r2 * r_z * c1 * c2 * c_c

    # Sweep log-spaced frequencies to extract exact UGF, Phase Margin, and Gain Margin
    n_pts = 180
    f_lo = 1.0e3
    f_hi = 2.0e10
    step_dec = math.log10(f_hi / f_lo) / float(n_pts - 1)

    prev_mag = a0
    prev_f = f_lo
    prev_ph = 0.0
    ugf_hz = f_lo
    pm_deg = 180.0
    gm_db = 45.0
    found_ugf = False
    found_180 = False

    for k in range(n_pts):
        freq = math.pow(10.0, math.log10(f_lo) + k * step_dec)
        w = 2.0 * math.pi * freq
        num_re = a0
        num_im = a0 * w * z_tau
        w2 = w * w
        den_re = 1.0 - b2 * w2
        den_im = w * (b1 - b3 * w2)

        num_mag = math.sqrt(num_re * num_re + num_im * num_im)
        den_mag = max(math.sqrt(den_re * den_re + den_im * den_im), 1e-30)
        mag = num_mag / den_mag

        ph_num = math.degrees(math.atan2(num_im, num_re))
        ph_den = math.degrees(math.atan2(den_im, den_re))
        if den_re < 0.0 and ph_den < 0.0:
            ph_den += 360.0
        phase = ph_num - ph_den

        if (not found_ugf) and prev_mag >= 1.0 and mag < 1.0:
            frac = math.log(prev_mag) / max(math.log(prev_mag / max(mag, 1e-20)), 1e-12)
            ugf_hz = prev_f * math.pow(freq / prev_f, frac)
            ph_cross = prev_ph + frac * (phase - prev_ph)
            pm_deg = 180.0 + ph_cross
            found_ugf = True

        if (not found_180) and prev_ph > -180.0 and phase <= -180.0:
            frac_p = (-180.0 - prev_ph) / min(phase - prev_ph, -1e-9)
            mag_180 = prev_mag * math.pow(max(mag, 1e-20) / max(prev_mag, 1e-20), frac_p)
            gm_db = -20.0 * math.log10(max(mag_180, 1e-12))
            found_180 = True

        prev_mag = mag
        prev_f = freq
        prev_ph = phase

    # Slew rate (symmetric bottleneck between Stage 1 charging Cc and Stage 2 driving CL + Cc)
    sr1 = i_tail / max(c_c, 1e-18)
    sr2 = max(i_st2 - i_tail, 1e-9) / (c_load + c_c)
    slew_v_us = min(sr1, sr2) * 1e-6

    # Input-referred thermal noise density (nV / sqrt(Hz))
    gamma_th = 0.95
    vn2 = (8.0 * k_b * t_k * gamma_th / max(gm1, 1e-12)) * (1.0 + gm3 / max(gm1, 1e-12))
    vn_nv_rthz = math.sqrt(vn2) * 1e9

    i_ref_bias = 8.0e-6
    power_w = vdd * (i_tail + i_st2 + i_ref_bias)
    area_um2 = ((2.0 * w_in + 2.0 * w_m3 + w_cs) * l_ch * 1e12) + (c_c * 1e12 * 420.0) + (r_z * 0.04)
    fom_mhz_pf_mw = (ugf_hz * 1e-6) * (c_load * 1e12) / max(power_w * 1e3, 1e-9)

    return {
        "dc_gain_db": dc_gain_db,
        "ugf_hz": ugf_hz,
        "phase_margin_deg": pm_deg,
        "gain_margin_db": gm_db,
        "slew_rate_v_us": slew_v_us,
        "vn_in_nv_rt_hz": vn_nv_rthz,
        "min_sat_margin_v": min_sat_margin,
        "triode_or_cutoff_count": 0 if min_sat_margin >= 0.0 else 1,
        "power_w": power_w,
        "area_um2": area_um2,
        "fom_small_signal": fom_mhz_pf_mw,
    }


def build_evaluator(problem):
    ev_spec = problem.get("evaluator", {"type": "builtin_miller_ota_2stage"})
    ev_type = ev_spec.get("type", "builtin_miller_ota_2stage")

    if ev_type == "builtin_miller_ota_2stage":
        return evaluate_miller_ota_2stage, "builtin_analytical_demo"

    if ev_type == "callable":
        fn = ev_spec.get("fn")
        if not callable(fn):
            raise SizingOptError("Callable evaluator requires callable 'fn' in problem['evaluator'].")
        return fn, "python_callable"

    if ev_type == "command":
        cmd_template = ev_spec.get("cmd")
        if not cmd_template or not isinstance(cmd_template, list):
            raise SizingOptError("Command evaluator requires 'cmd' list in problem['evaluator'].")

        def _run_cmd(params, corner="TT"):
            tmp_d = tempfile.mkdtemp(prefix="skill_analog_eval_")
            try:
                in_path = os.path.join(tmp_d, "params.json")
                out_path = os.path.join(tmp_d, "metrics.json")
                payload = {"params": params, "corner": corner}
                f = open(in_path, "wb")
                try:
                    f.write(json.dumps(payload, sort_keys=True).encode("utf-8"))
                finally:
                    f.close()

                cmd = []
                for tok in cmd_template:
                    cmd.append(
                        str(tok)
                        .replace("{params_json}", in_path)
                        .replace("{out_json}", out_path)
                        .replace("{corner}", str(corner))
                    )
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                out_b, err_b = proc.communicate()
                if proc.returncode != 0:
                    raise SizingOptError(
                        "Evaluator command failed (exit %d): %s"
                        % (proc.returncode, err_b.decode("latin1")[:400])
                    )
                if os.path.isfile(out_path):
                    rf = open(out_path, "rb")
                    try:
                        return json.loads(rf.read().decode("utf-8"))
                    finally:
                        rf.close()
                return json.loads(out_b.decode("utf-8"))
            finally:
                shutil.rmtree(tmp_d, ignore_errors=True)

        return _run_cmd, "external_command"

    raise SizingOptError("Unsupported evaluator type: %s" % ev_type)


# ---------------------------------------------------------------------------
# Constraint & Merit Function Evaluation (with Strict Unit & Dimension Checks)
# ---------------------------------------------------------------------------

# (si_scale, dimension_family)
_UNIT_INFO_CASE_SENSITIVE = {
    "MHz": (1.0e6, "freq"),
    "mHz": (1.0e-3, "freq"),
    "mW": (1.0e-3, "power"),
    "MW": (1.0e6, "power"),
    "mV": (1.0e-3, "voltage"),
    "MV": (1.0e6, "voltage"),
    "mA": (1.0e-3, "current"),
    "MA": (1.0e6, "current"),
    "ms": (1.0e-3, "time"),
    "mS": (1.0e-3, "conductance"),
    "S": (1.0, "conductance"),
    "mOhm": (1.0e-3, "resistance"),
    "MOhm": (1.0e6, "resistance"),
    "Mohm": (1.0e6, "resistance"),
    "Mohms": (1.0e6, "resistance"),
    "MOhms": (1.0e6, "resistance"),
    "mV/rtHz": (1.0e-3, "noise_density"),
    "MV/s": (1.0e6, "slew_rate"),
    "mV/s": (1.0e-3, "slew_rate"),
}

_UNIT_INFO_LOWER = {
    "": (1.0, None),
    "db": (1.0, "db"),
    "dbc": (1.0, "db"),
    "dbc/hz": (1.0, "phase_noise"),
    "deg": (1.0, "angle"),
    "rad": (180.0 / math.pi, "angle"),
    "hz": (1.0, "freq"),
    "khz": (1.0e3, "freq"),
    "mhz": (1.0e6, "freq"),
    "ghz": (1.0e9, "freq"),
    "v": (1.0, "voltage"),
    "vrms": (1.0, "voltage"),
    "vpp": (1.0, "voltage"),
    "mv": (1.0e-3, "voltage"),
    "mvrms": (1.0e-3, "voltage"),
    "uv": (1.0e-6, "voltage"),
    "uvrms": (1.0e-6, "voltage"),
    "nv": (1.0e-9, "voltage"),
    "a": (1.0, "current"),
    "ma": (1.0e-3, "current"),
    "ua": (1.0e-6, "current"),
    "na": (1.0e-9, "current"),
    "pa": (1.0e-12, "current"),
    "w": (1.0, "power"),
    "mw": (1.0e-3, "power"),
    "uw": (1.0e-6, "power"),
    "nw": (1.0e-9, "power"),
    "pw": (1.0e-12, "power"),
    "s": (1.0, "time"),
    "sec": (1.0, "time"),
    "ms": (1.0e-3, "time"),
    "us": (1.0e-6, "time"),
    "ns": (1.0e-9, "time"),
    "ps": (1.0e-12, "time"),
    "fs": (1.0e-15, "time"),
    "v/s": (1.0, "slew_rate"),
    "v/ms": (1.0e3, "slew_rate"),
    "v/us": (1.0e6, "slew_rate"),
    "v/ns": (1.0e9, "slew_rate"),
    "v/rthz": (1.0, "noise_density"),
    "v/sqrt(hz)": (1.0, "noise_density"),
    "uv/rthz": (1.0e-6, "noise_density"),
    "uv/sqrt(hz)": (1.0e-6, "noise_density"),
    "nv/rthz": (1.0e-9, "noise_density"),
    "nv/sqrt(hz)": (1.0e-9, "noise_density"),
    "ohm": (1.0, "resistance"),
    "ohms": (1.0, "resistance"),
    "kohm": (1.0e3, "resistance"),
    "kohms": (1.0e3, "resistance"),
    "megohm": (1.0e6, "resistance"),
    "megohms": (1.0e6, "resistance"),
    "mohm": (1.0e-3, "resistance"),
    "mohms": (1.0e-3, "resistance"),
    "f": (1.0, "capacitance"),
    "pf": (1.0e-12, "capacitance"),
    "ff": (1.0e-15, "capacitance"),
    "nf": (1.0e-9, "capacitance"),
    "uf": (1.0e-6, "capacitance"),
    "us/v": (1.0e-6, "conductance"),
    "1/v": (1.0, "gm_id"),
    "v^-1": (1.0, "gm_id"),
    "%": (1.0, "percent"),
    "pct": (1.0, "percent"),
}


def _infer_metric_native_unit(metric_name):
    """Return `(native_si_scale, dimension_family)` inferred from canonical metric suffix."""
    m = str(metric_name or "").strip().lower()
    if m.endswith("_nv_rt_hz") or m.endswith("_nv_rthz"):
        return 1.0e-9, "noise_density"
    if m.endswith("_uv_rt_hz") or m.endswith("_uv_rthz"):
        return 1.0e-6, "noise_density"
    if m.endswith("_v_rt_hz") or m.endswith("_v_rthz"):
        return 1.0, "noise_density"
    if m.endswith("_v_us") or m.endswith("_v_per_us"):
        return 1.0e6, "slew_rate"
    if m.endswith("_v_ns") or m.endswith("_v_per_ns"):
        return 1.0e9, "slew_rate"
    if m.endswith("_v_per_s") or m.endswith("_v_s"):
        return 1.0, "slew_rate"
    if m.endswith("_dbc_hz") or m.endswith("_dbc_per_hz"):
        return 1.0, "phase_noise"
    if m.endswith("_db") or m.endswith("_dbc") or m in ("dc_gain", "psrr", "cmrr", "gain_margin", "snr", "sndr", "sfdr"):
        return 1.0, "db"
    if m.endswith("_deg") or m in ("phase_margin",):
        return 1.0, "angle"
    if m.endswith("_ghz"):
        return 1.0e9, "freq"
    if m.endswith("_mhz"):
        return 1.0e6, "freq"
    if m.endswith("_khz"):
        return 1.0e3, "freq"
    if m.endswith("_hz") or m in ("ugf", "gbw", "bw_3db"):
        return 1.0, "freq"
    if m.endswith("_mw"):
        return 1.0e-3, "power"
    if m.endswith("_uw"):
        return 1.0e-6, "power"
    if m.endswith("_nw"):
        return 1.0e-9, "power"
    if m.endswith("_w") or m in ("power", "dc_power", "p_dc", "pdc"):
        return 1.0, "power"
    if m.endswith("_ps"):
        return 1.0e-12, "time"
    if m.endswith("_ns"):
        return 1.0e-9, "time"
    if m.endswith("_us"):
        return 1.0e-6, "time"
    if m.endswith("_ms"):
        return 1.0e-3, "time"
    if m.endswith("_s") or m in ("settling_time", "t_settle", "rise_time", "fall_time"):
        return 1.0, "time"
    if m.endswith("_uv") or m.endswith("_uvrms"):
        return 1.0e-6, "voltage"
    if m.endswith("_mv") or m.endswith("_mvrms"):
        return 1.0e-3, "voltage"
    if m.endswith("_v") or m.endswith("_vrms") or m.endswith("_vpp") or m in ("v_os", "offset", "min_sat_margin"):
        return 1.0, "voltage"
    if m.endswith("_ua"):
        return 1.0e-6, "current"
    if m.endswith("_ma"):
        return 1.0e-3, "current"
    if m.endswith("_a") or m in ("i_dd", "i_bias", "i_q"):
        return 1.0, "current"
    if m.endswith("_ohm"):
        return 1.0, "resistance"
    if m.endswith("_pf"):
        return 1.0e-12, "capacitance"
    if m.endswith("_ff"):
        return 1.0e-15, "capacitance"
    if m.endswith("_f"):
        return 1.0, "capacitance"
    if m.endswith("_pct") or m.endswith("_percent"):
        return 1.0, "percent"
    return 1.0, None


def _convert_constraint_value(raw_val, unit_str, metric_name, cid):
    raw_u = str(unit_str or "").strip().replace(" ", "")
    if not raw_u:
        return float(raw_val), 1.0
    if raw_u in _UNIT_INFO_CASE_SENSITIVE:
        u_scale, u_fam = _UNIT_INFO_CASE_SENSITIVE[raw_u]
    else:
        u_low = raw_u.lower()
        if u_low not in _UNIT_INFO_LOWER:
            raise SizingOptError("Unknown constraint unit '%s' on %s (metric=%s)" % (raw_u, cid, metric_name))
        u_scale, u_fam = _UNIT_INFO_LOWER[u_low]
    m_scale, m_fam = _infer_metric_native_unit(metric_name)
    if u_fam is not None and m_fam is not None and u_fam != m_fam:
        raise SizingOptError(
            "Incompatible unit '%s' (%s) for metric '%s' (%s) on constraint %s"
            % (raw_u, u_fam, metric_name, m_fam, cid)
        )
    factor = u_scale / m_scale
    return float(raw_val) * factor, factor


def normalize_constraints(problem):
    raw_list = list(problem.get("hard_constraints", []))
    if "mos_sat_margin_min" in problem:
        raw_sat = problem["mos_sat_margin_min"]
    elif "mos_sat_margin_min_v" in problem:
        raw_sat = problem["mos_sat_margin_min_v"]
    else:
        raw_sat = 0.05
    sat_min = _safe_finite_float(raw_sat)
    if sat_min is None:
        raise SizingOptError("Invalid or non-finite mos_sat_margin_min: %r" % (raw_sat,))
    has_sat = False
    constraints = []
    for idx, item in enumerate(raw_list):
        metric = item.get("metric", item.get("quantity", item.get("id")))
        cid = item.get("id", metric or ("c_%d" % idx))
        op = str(item.get("op", item.get("operator", ">="))).strip()
        unit_str = str(item.get("unit", "") or "").strip()
        raw_tgt = item.get("target")
        target_raw = _safe_finite_float(raw_tgt)
        if target_raw is None:
            raise SizingOptError("Invalid or non-finite constraint target %r on %s" % (raw_tgt, cid))
        target, unit_factor = _convert_constraint_value(target_raw, unit_str, metric, cid)
        default_scale = max(abs(target) * 0.15, 1e-30) if target != 0.0 else 1e-9
        if "scale" in item and item["scale"] is not None:
            raw_sc = _safe_finite_float(item["scale"])
            if raw_sc is None or raw_sc <= 0.0:
                raise SizingOptError("Invalid or non-positive constraint scale %r on %s" % (item["scale"], cid))
            scale = raw_sc * unit_factor
        else:
            scale = default_scale
        if metric == "min_sat_margin_v":
            has_sat = True
        constraints.append({
            "id": cid,
            "metric": metric,
            "op": op,
            "target": target,
            "target_raw": target_raw,
            "scale": max(scale, 1e-30),
            "unit": unit_str,
        })

    if problem.get("enforce_mos_sat_margin", True) and not has_sat:
        constraints.append({
            "id": "mos_sat_margin",
            "metric": "min_sat_margin_v",
            "op": ">=",
            "target": sat_min,
            "target_raw": sat_min,
            "scale": max(sat_min, 0.02),
            "unit": "V",
        })
    return constraints


def check_constraints(metrics, constraints, target_shifts=None):
    """Evaluate margins and violations against constraints (+ optional PVT guard shifts)."""
    shifts = target_shifts or {}
    details = []
    total_viol = 0.0
    all_pass = True
    all_guarded_pass = True

    for c in constraints:
        mname = c["metric"]
        op = c["op"]
        tgt = _safe_finite_float(c.get("target"))
        if tgt is None:
            raise SizingOptError("Invalid or non-finite constraint target %r on %s" % (c.get("target"), c.get("id")))
        raw_scale = c.get("scale", max(abs(tgt) * 0.15, 1e-30))
        scale_val = _safe_finite_float(raw_scale)
        if scale_val is None or scale_val <= 0.0:
            raise SizingOptError("Invalid or non-finite constraint scale %r on %s" % (raw_scale, c.get("id")))
        scale_pos = max(scale_val, 1e-30)
        shift_raw = shifts.get(c["id"], 0.0)
        shift = _safe_finite_float(shift_raw)
        if shift is None:
            raise SizingOptError("Invalid or non-finite target shift %r on %s" % (shift_raw, c.get("id")))

        if op not in (">=", ">", "<=", "<"):
            raise SizingOptError("Unsupported constraint operator '%s' on %s" % (op, c["id"]))

        if mname not in metrics or metrics[mname] is None:
            all_pass = False
            all_guarded_pass = False
            total_viol += 2.0
            details.append({
                "id": c["id"],
                "metric": mname,
                "op": op,
                "status": "NOT_VERIFIED",
                "value": None,
                "target": tgt,
                "effective_target": (tgt + shift) if op in (">=", ">") else (tgt - shift),
                "unit": c.get("unit", ""),
                "margin": None,
                "guarded_margin_norm": None,
                "violation_norm": 2.0,
            })
            continue

        raw_mval = metrics[mname]
        val = _safe_finite_float(raw_mval)
        if val is None:
            passed = False
            all_pass = False
            all_guarded_pass = False
            viol = 10.0
            total_viol += 10.0
            details.append({
                "id": c["id"],
                "metric": mname,
                "op": op,
                "value": raw_mval,
                "target": tgt,
                "effective_target": (tgt + shift) if op in (">=", ">") else (tgt - shift),
                "unit": c.get("unit", ""),
                "margin": None,
                "guarded_margin_norm": None,
                "violation_norm": viol,
                "status": "FAIL",
            })
            continue

        if op in (">=", ">"):
            eff_tgt = tgt + shift
            margin = val - eff_tgt
            raw_margin = val - tgt
        else:
            eff_tgt = tgt - shift
            margin = eff_tgt - val
            raw_margin = tgt - val

        if op in (">", "<"):
            passed = (raw_margin > 0.0)
            guarded_passed = passed and (margin > 0.0)
        else:
            passed = (raw_margin >= -1e-12 * max(abs(tgt), 1e-30))
            guarded_passed = passed and (margin >= -1e-12 * max(abs(eff_tgt), abs(tgt), 1e-30))

        if not passed:
            all_pass = False
        if not guarded_passed:
            all_guarded_pass = False

        viol = max(0.0, -margin / scale_pos)
        if (not guarded_passed) and viol <= 0.0:
            viol = 1e-9
        total_viol += viol

        details.append({
            "id": c["id"],
            "metric": mname,
            "op": op,
            "value": val,
            "target": tgt,
            "effective_target": eff_tgt,
            "unit": c.get("unit", ""),
            "margin": raw_margin,
            "guarded_margin_norm": margin / scale_pos,
            "violation_norm": viol,
            "status": "PASS" if passed else "FAIL",
        })

    toc_cnt = _safe_finite_float(metrics.get("triode_or_cutoff_count", 0))
    if toc_cnt is not None and toc_cnt > 0:
        all_pass = False
        all_guarded_pass = False
        total_viol += 0.5 * toc_cnt

    return {
        "all_pass": all_pass,
        "all_guarded_pass": all_guarded_pass,
        "total_violation": total_viol,
        "details": details,
    }


def compute_objective_norm(metrics, obj_spec, ref_val):
    metric_name = obj_spec.get("metric", "power_w")
    goal = str(obj_spec.get("goal", obj_spec.get("sense", "minimize"))).lower()
    val = _safe_finite_float(metrics.get(metric_name)) if isinstance(metrics, dict) else None
    if val is None:
        return 1.0e6
    ref_f = _safe_finite_float(ref_val)
    denom = max(abs(ref_f) if ref_f is not None else 1.0, 1e-18)
    if goal.startswith("max"):
        return -val / denom
    return val / denom


def penalty_barrier_merit(metrics, constraints, obj_spec, obj_ref, target_shifts=None, rho=35.0, mu_barrier=0.012):
    chk = check_constraints(metrics, constraints, target_shifts=target_shifts)
    f_norm = compute_objective_norm(metrics, obj_spec, obj_ref)
    pen = 0.0
    bar = 0.0
    for d in chk["details"]:
        v = d["violation_norm"]
        gm = d.get("guarded_margin_norm")
        if v > 0.0:
            pen += v + 4.0 * v * v
            bar -= math.log(1e-4)
        elif gm is not None:
            bar -= math.log(min(max(gm + 1e-4, 1e-4), 2.5))
    return f_norm + rho * pen + mu_barrier * bar, chk


# ---------------------------------------------------------------------------
# Stage 1: Sensitivity Jacobian & Physics-Guided Subspace Pruning
# ---------------------------------------------------------------------------

def compute_sensitivity_stage1(
    space, eval_cached, u0, constraints, obj_spec, nom_corner="TT", step_u=0.045
):
    """Evaluate initial point + finite-difference Sensitivity Jacobian dMetric / d(ln x)."""
    m0 = eval_cached(u0, nom_corner)
    x0_dict = space.u_to_x(u0, snap=False)
    obj_metric = obj_spec.get("metric", "power_w")
    tracked_metrics = [obj_metric]
    for c in constraints:
        if c["metric"] not in tracked_metrics and c["metric"] in m0:
            tracked_metrics.append(c["metric"])

    jac_u = {}
    d_lnx = {}
    for mname in tracked_metrics:
        jac_u[mname] = [0.0] * space.dim
        d_lnx[mname] = {}
        for vspec in space.vars:
            d_lnx[mname][vspec["name"]] = 0.0

    neighbor_samples = []
    budget_cut_short = False
    for j in range(space.dim):
        vspec = space.vars[j]
        du = step_u if (u0[j] + step_u <= 1.0) else -step_u
        u_pert = list(u0)
        u_pert[j] = _clamp(u0[j] + du, 0.0, 1.0)
        actual_du = u_pert[j] - u0[j]
        try:
            m_pert = eval_cached(u_pert, nom_corner)
        except _BudgetExhausted:
            budget_cut_short = True
            break
        neighbor_samples.append((u_pert, m_pert))

        d_phys = actual_du * vspec["span_ln"]
        x_base = x0_dict[vspec["name"]]
        for mname in tracked_metrics:
            v_pert = _safe_finite_float(m_pert.get(mname))
            v_base = _safe_finite_float(m0.get(mname))
            if v_pert is None or v_base is None or abs(actual_du) < 1e-18 or abs(d_phys) < 1e-30:
                continue
            dm = v_pert - v_base
            jac_u[mname][j] = dm / actual_du
            if vspec["scale"] == "lin":
                d_lnx[mname][vspec["name"]] = x_base * (dm / d_phys)
            else:
                d_lnx[mname][vspec["name"]] = dm / d_phys

    # Rank dominant knobs per constraint (especially failing ones!) and compute variable importance
    chk0 = check_constraints(m0, constraints)
    knob_rankings = {}
    var_importance = [0.0] * space.dim

    for idx_c, c in enumerate(constraints):
        mname = c["metric"]
        if mname not in jac_u:
            continue
        is_failing = (chk0["details"][idx_c]["status"] != "PASS")
        weight_c = 3.0 if is_failing else 1.0
        ranked = []
        for j, vspec in enumerate(space.vars):
            norm_sens = jac_u[mname][j] / max(c["scale"], 1e-12)
            dir_sign = 1.0 if c["op"] in (">=", ">") else -1.0
            helpful_grad = dir_sign * norm_sens
            var_importance[j] = max(var_importance[j], weight_c * abs(norm_sens))
            ranked.append({
                "variable": vspec["name"],
                "d_metric_d_lnx": round(d_lnx[mname][vspec["name"]], 5),
                "margin_gain_per_10pct_increase": round(
                    dir_sign * d_lnx[mname][vspec["name"]] * math.log(1.10), 5
                ),
                "recommended_direction": "increase" if helpful_grad > 0 else "decrease",
                "abs_norm_sensitivity": abs(norm_sens),
            })
        ranked.sort(key=lambda item: item["abs_norm_sensitivity"], reverse=True)
        for r in ranked:
            del r["abs_norm_sensitivity"]
        knob_rankings[c["id"]] = {
            "metric": mname,
            "initial_status": chk0["details"][idx_c]["status"],
            "initial_value": chk0["details"][idx_c]["value"],
            "target": c["target"],
            "dominant_knobs": ranked[:4],
        }

    # Include objective sensitivity in variable importance
    obj_base = _safe_finite_float(m0.get(obj_metric))
    obj_scale = max(abs(obj_base), 1e-15) if obj_base is not None else 1.0
    for j in range(space.dim):
        var_importance[j] = max(var_importance[j], abs(jac_u[obj_metric][j]) / obj_scale)

    max_imp = max(var_importance) if var_importance else 1.0
    prune_cutoff = 0.015 * max_imp
    active_indices = []
    pruned_names = []
    if max_imp <= 0.0 or budget_cut_short:
        active_indices = list(range(space.dim))
    else:
        for j, vspec in enumerate(space.vars):
            if var_importance[j] >= prune_cutoff:
                active_indices.append(j)
            else:
                pruned_names.append(vspec["name"])
        if not active_indices:
            active_indices = list(range(space.dim))
            pruned_names = []

    return {
        "m0": m0,
        "initial_check": chk0,
        "jac_u": jac_u,
        "d_metric_d_lnx": d_lnx,
        "constraint_knob_rankings": knob_rankings,
        "active_indices": active_indices,
        "pruned_variables": pruned_names,
        "var_importance": var_importance,
        "neighbor_samples": neighbor_samples,
        "partial_sensitivity": budget_cut_short,
    }


def _solve_linearized_tr_step(
    u_cur, m_cur, jac_u, active_indices, constraints, obj_spec, obj_ref, target_shifts, radius
):
    """Solve linearized Penalty-Barrier subproblem inside ||du||_inf <= radius (0 simulator evals!)."""
    dim = len(u_cur)
    du = [0.0] * dim
    obj_m = obj_spec.get("metric", "power_w")
    goal_max = str(obj_spec.get("goal", obj_spec.get("sense", "minimize"))).lower().startswith("max")
    obj_sign = -1.0 if goal_max else 1.0

    def lin_metrics(delta_u):
        pred = dict(m_cur)
        for mname, grad in jac_u.items():
            base_v = _safe_finite_float(m_cur.get(mname))
            if base_v is None:
                pred[mname] = None
                continue
            acc = base_v
            for j in active_indices:
                acc += grad[j] * delta_u[j]
            pred[mname] = acc
        return pred

    best_du = list(du)
    best_merit, _ = penalty_barrier_merit(
        m_cur, constraints, obj_spec, obj_ref, target_shifts=target_shifts, rho=45.0, mu_barrier=0.010
    )

    for it in range(90):
        pred_m = lin_metrics(du)
        chk = check_constraints(pred_m, constraints, target_shifts=target_shifts)
        grad_u = [0.0] * dim

        for j in active_indices:
            grad_u[j] += obj_sign * jac_u[obj_m][j] / max(abs(obj_ref), 1e-18)

        for idx_c, c in enumerate(constraints):
            mname = c["metric"]
            if mname not in jac_u:
                continue
            det = chk["details"][idx_c]
            v = det["violation_norm"]
            gm = det["guarded_margin_norm"]
            dir_s = 1.0 if c["op"] in (">=", ">") else -1.0
            if v > 0.0 or gm is None:
                dphi_dgm = -45.0 * (1.0 + 8.0 * v)
            else:
                denom_b = min(max(gm + 1e-4, 1e-4), 2.5)
                dphi_dgm = (-0.010 / denom_b) if gm < 2.5 else 0.0
            factor = dphi_dgm * dir_s / c["scale"]
            for j in active_indices:
                grad_u[j] += factor * jac_u[mname][j]

        gnorm = math.sqrt(sum([grad_u[j] * grad_u[j] for j in active_indices]))
        if gnorm < 1e-12:
            break
        step_len = radius * 0.32 * math.pow(0.965, it)
        cand_du = list(du)
        for j in active_indices:
            lo_d = max(-radius, -u_cur[j])
            hi_d = min(radius, 1.0 - u_cur[j])
            cand_du[j] = _clamp(du[j] - step_len * (grad_u[j] / gnorm), lo_d, hi_d)

        cand_pred = lin_metrics(cand_du)
        cand_merit, _ = penalty_barrier_merit(
            cand_pred, constraints, obj_spec, obj_ref, target_shifts=target_shifts, rho=45.0, mu_barrier=0.010
        )
        du = cand_du
        if cand_merit < best_merit:
            best_merit = cand_merit
            best_du = list(cand_du)

    return best_du, best_merit


def _broyden_update(jac_u, du, m_old, m_new):
    norm2 = sum([d * d for d in du])
    if norm2 < 1e-10:
        return
    for mname, grad in jac_u.items():
        if mname not in m_new or mname not in m_old:
            continue
        v_new = _safe_finite_float(m_new.get(mname))
        v_old = _safe_finite_float(m_old.get(mname))
        if v_new is None or v_old is None:
            continue
        dm_actual = v_new - v_old
        dm_pred = sum([grad[j] * du[j] for j in range(len(du))])
        resid = dm_actual - dm_pred
        for j in range(len(du)):
            grad[j] += 0.75 * resid * du[j] / norm2


# ---------------------------------------------------------------------------
# Full Two-Stage Closed-Loop Optimizer
# ---------------------------------------------------------------------------

def optimize_problem(problem, sensitivity_only=False):
    t_start = TIMER()
    if not isinstance(problem, dict):
        raise SizingOptError("Problem specification must be a JSON object / dict.")

    if "corners" in problem:
        corners = problem["corners"]
    elif "pvt_corners" in problem:
        corners = problem["pvt_corners"]
    else:
        corners = ["TT", "SS", "FF"]
    if not isinstance(corners, list) or len(corners) == 0:
        raise SizingOptError("Problem 'corners' must be a non-empty list of PVT corner names.")
    for c_item in corners:
        if c_item is None or not str(c_item).strip():
            raise SizingOptError("Problem 'corners' entries must be non-empty corner names.")

    raw_max_evals = problem.get("max_evaluations", 34)
    if raw_max_evals is None or isinstance(raw_max_evals, bool):
        raise SizingOptError("Problem 'max_evaluations' must be an integer >= 1.")
    max_evals = int(raw_max_evals)
    if max_evals < 1:
        raise SizingOptError("Problem 'max_evaluations' must be >= 1, got %d." % max_evals)

    default_step_grid = problem.get("step_grid", problem.get("step_grid_m"))
    space = DesignSpace(problem["variables"], default_step_grid=default_step_grid)
    evaluator, evaluator_source = build_evaluator(problem)
    constraints = normalize_constraints(problem)
    obj_spec = problem.get("objective", {"metric": "power_w", "goal": "minimize"})
    nom_corner = "TT" if "TT" in corners else corners[0]

    eval_cache = {}
    eval_counter = [0]
    history = []

    def eval_cached(u_vec, corner="TT", snap=False):
        x_dict = space.u_to_x(u_vec, snap=snap)
        key_items = [str(corner)]
        for vspec in space.vars:
            key_items.append("%.10g" % x_dict[vspec["name"]])
        ckey = "|".join(key_items)
        if ckey in eval_cache:
            return eval_cache[ckey]
        if eval_counter[0] >= max_evals:
            raise _BudgetExhausted()
        eval_counter[0] += 1
        metrics = evaluator(x_dict, corner=corner)
        eval_cache[ckey] = metrics
        history.append({
            "eval_index": eval_counter[0],
            "corner": corner,
            "snapped": bool(snap),
            "objective": metrics.get(obj_spec.get("metric", "power_w")),
        })
        return metrics

    u0 = space.x_to_u(space.init_x())
    s1 = compute_sensitivity_stage1(
        space, eval_cached, u0, constraints, obj_spec, nom_corner=nom_corner
    )
    m0 = s1["m0"]
    obj_metric = obj_spec.get("metric", "power_w")
    obj_ref_raw = _safe_finite_float(m0.get(obj_metric))
    obj_ref = obj_ref_raw if (obj_ref_raw is not None and obj_ref_raw != 0.0) else 1.0

    if sensitivity_only:
        return {
            "ok": True,
            "release": RELEASE,
            "mode": "sensitivity_only",
            "evaluator_source": evaluator_source,
            "evaluations": eval_counter[0],
            "max_evaluations": max_evals,
            "partial_sensitivity": s1["partial_sensitivity"],
            "initial_variables": space.u_to_x(u0, snap=False),
            "initial_metrics_tt": m0,
            "initial_constraints": s1["initial_check"],
            "sensitivity_d_metric_d_lnx": s1["d_metric_d_lnx"],
            "constraint_knob_rankings": s1["constraint_knob_rankings"],
            "pruned_variables": s1["pruned_variables"],
            "elapsed_ms": round((TIMER() - t_start) * 1000.0, 3),
        }

    # Initial conservative PVT guardband on nominal corner
    target_shifts = {}
    for c in constraints:
        if len(corners) > 1:
            if c["metric"] == "min_sat_margin_v":
                target_shifts[c["id"]] = 0.048
            elif c["metric"] == "dc_gain_db":
                target_shifts[c["id"]] = 2.8
            elif c["metric"] == "phase_margin_deg":
                target_shifts[c["id"]] = 4.5
            elif c["metric"] == "ugf_hz":
                target_shifts[c["id"]] = 0.22 * abs(c["target"])
            else:
                target_shifts[c["id"]] = 0.08 * c["scale"]
        else:
            target_shifts[c["id"]] = 0.0

    # Pick best point seen across Stage 1 (u0 + finite-difference neighbors)
    u_best = list(u0)
    m_best = m0
    merit_best, _ = penalty_barrier_merit(m_best, constraints, obj_spec, obj_ref, target_shifts=target_shifts)
    jac_u = copy.deepcopy(s1["jac_u"])
    active_idx = list(s1["active_indices"])

    for u_nb, m_nb in s1["neighbor_samples"]:
        mer_nb, _ = penalty_barrier_merit(m_nb, constraints, obj_spec, obj_ref, target_shifts=target_shifts)
        if mer_nb < merit_best:
            merit_best = mer_nb
            u_best = list(u_nb)
            m_best = m_nb

    # Stage 2A: Constrained Trust-Region with Broyden Rank-1 Jacobian Updates
    tr_radius = 0.34
    reserve_for_pvt_and_simplex = min(14, max(8, len(corners) * 2 + 6))
    tr_budget = min(max_evals - len(corners), max(eval_counter[0] + 4, max_evals - reserve_for_pvt_and_simplex))

    try:
        while eval_counter[0] < tr_budget and tr_radius >= 0.015:
            du_step, pred_merit = _solve_linearized_tr_step(
                u_best, m_best, jac_u, active_idx, constraints, obj_spec, obj_ref, target_shifts, tr_radius
            )
            max_du = max([abs(v) for v in du_step])
            if max_du < 1e-4:
                break

            u_cand = [_clamp(u_best[j] + du_step[j], 0.0, 1.0) for j in range(space.dim)]
            actual_du = [u_cand[j] - u_best[j] for j in range(space.dim)]
            m_cand = eval_cached(u_cand, nom_corner, snap=False)
            _broyden_update(jac_u, actual_du, m_best, m_cand)

            merit_cand, _ = penalty_barrier_merit(m_cand, constraints, obj_spec, obj_ref, target_shifts=target_shifts)
            pred_drop = max(merit_best - pred_merit, 1e-9)
            actual_drop = merit_best - merit_cand
            rho_ratio = actual_drop / pred_drop

            if actual_drop > 0.0:
                u_best = u_cand
                m_best = m_cand
                merit_best = merit_cand
                if rho_ratio > 0.70 and max_du > 0.8 * tr_radius:
                    tr_radius = min(0.45, tr_radius * 1.25)
            else:
                tr_radius *= 0.48
    except _BudgetExhausted:
        pass

    # Stage 2B: Physics-Pruned Subspace Nelder-Mead Simplex Polish (top-k active variables)
    ranked_active = sorted(active_idx, key=lambda j: s1["var_importance"][j], reverse=True)
    sub_idx = ranked_active[: min(3, len(ranked_active))]
    nm_budget = max(0, max_evals - (len(corners) * 2 + 2) - eval_counter[0])

    if sub_idx and nm_budget >= len(sub_idx) + 1:
        simplex = [(list(u_best), merit_best, m_best)]
        delta_nm = 0.038
        try:
            for j in sub_idx:
                if eval_counter[0] >= max_evals - (len(corners) * 2 + 1):
                    break
                u_v = list(u_best)
                step_s = -delta_nm if u_best[j] > 0.2 else delta_nm
                u_v[j] = _clamp(u_best[j] + step_s, 0.0, 1.0)
                m_v = eval_cached(u_v, nom_corner, snap=False)
                _broyden_update(jac_u, [u_v[k] - u_best[k] for k in range(space.dim)], m_best, m_v)
                mer_v, _ = penalty_barrier_merit(m_v, constraints, obj_spec, obj_ref, target_shifts=target_shifts)
                simplex.append((u_v, mer_v, m_v))

            while len(simplex) == len(sub_idx) + 1 and eval_counter[0] < max_evals - (len(corners) * 2 + 1):
                simplex.sort(key=lambda item: item[1])
                if simplex[0][1] < merit_best:
                    u_best, merit_best, m_best = list(simplex[0][0]), simplex[0][1], simplex[0][2]

                n_sub = len(sub_idx)
                u_cent = list(simplex[0][0])
                for j in sub_idx:
                    u_cent[j] = sum([simplex[k][0][j] for k in range(n_sub)]) / float(n_sub)

                u_worst, mer_worst, _ = simplex[-1]
                u_refl = list(u_cent)
                for j in sub_idx:
                    u_refl[j] = _clamp(u_cent[j] + 1.0 * (u_cent[j] - u_worst[j]), 0.0, 1.0)
                m_refl = eval_cached(u_refl, nom_corner, snap=False)
                mer_refl, _ = penalty_barrier_merit(m_refl, constraints, obj_spec, obj_ref, target_shifts=target_shifts)

                if mer_refl < simplex[0][1] and eval_counter[0] < max_evals - (len(corners) * 2 + 1):
                    u_exp = list(u_cent)
                    for j in sub_idx:
                        u_exp[j] = _clamp(u_cent[j] + 1.75 * (u_refl[j] - u_cent[j]), 0.0, 1.0)
                    m_exp = eval_cached(u_exp, nom_corner, snap=False)
                    mer_exp, _ = penalty_barrier_merit(m_exp, constraints, obj_spec, obj_ref, target_shifts=target_shifts)
                    if mer_exp < mer_refl:
                        simplex[-1] = (u_exp, mer_exp, m_exp)
                    else:
                        simplex[-1] = (u_refl, mer_refl, m_refl)
                elif mer_refl < simplex[-2][1]:
                    simplex[-1] = (u_refl, mer_refl, m_refl)
                else:
                    if eval_counter[0] >= max_evals - (len(corners) * 2 + 1):
                        break
                    u_cont = list(u_cent)
                    base_u = u_refl if mer_refl < mer_worst else u_worst
                    for j in sub_idx:
                        u_cont[j] = _clamp(u_cent[j] + 0.5 * (base_u[j] - u_cent[j]), 0.0, 1.0)
                    m_cont = eval_cached(u_cont, nom_corner, snap=False)
                    mer_cont, _ = penalty_barrier_merit(m_cont, constraints, obj_spec, obj_ref, target_shifts=target_shifts)
                    if mer_cont < min(mer_refl, mer_worst):
                        simplex[-1] = (u_cont, mer_cont, m_cont)
                    else:
                        break
        except _BudgetExhausted:
            pass

        simplex.sort(key=lambda item: item[1])
        if simplex[0][1] < merit_best:
            u_best, merit_best, m_best = list(simplex[0][0]), simplex[0][1], simplex[0][2]

    # Stage 2C: PDK Manufacturing Grid Snap + Worst-Case PVT Corner Verification & Polish
    def _unverified_corner_check():
        unv_details = []
        for c in constraints:
            unv_details.append({
                "id": c["id"],
                "metric": c["metric"],
                "op": c["op"],
                "value": None,
                "target": c["target"],
                "effective_target": c["target"],
                "unit": c["unit"],
                "margin": None,
                "guarded_margin_norm": None,
                "violation_norm": 2.0,
                "status": "NOT_VERIFIED",
            })
        return {
            "all_pass": False,
            "all_guarded_pass": False,
            "total_violation": None,
            "status": "NOT_VERIFIED",
            "details": unv_details,
        }

    def evaluate_all_corners_snapped(u_vec):
        corner_metrics = {}
        corner_checks = {}
        corner_status = {}
        verified_list = []
        unverified_list = []
        all_ok = True
        for c_name in corners:
            try:
                mc = eval_cached(u_vec, corner=c_name, snap=True)
            except _BudgetExhausted:
                all_ok = False
                unverified_list.append(c_name)
                corner_metrics[c_name] = {"status": "NOT_VERIFIED"}
                corner_checks[c_name] = _unverified_corner_check()
                corner_status[c_name] = "NOT_VERIFIED"
                continue
            cc = check_constraints(mc, constraints)
            c_stat = "PASS" if cc["all_pass"] else "FAIL"
            cc["status"] = c_stat
            corner_metrics[c_name] = mc
            corner_checks[c_name] = cc
            corner_status[c_name] = c_stat
            verified_list.append(c_name)
            if not cc["all_pass"]:
                all_ok = False
        if unverified_list or len(verified_list) < len(corners):
            all_ok = False
        return all_ok, corner_metrics, corner_checks, corner_status, verified_list, unverified_list

    pvt_ok, pvt_metrics, pvt_checks, pvt_status, verified_corners, unverified_corners = (
        evaluate_all_corners_snapped(u_best)
    )

    # If any PVT corner failed after grid snapping and budget remains for polish + re-verification:
    if (not pvt_ok) and (not unverified_corners) and (eval_counter[0] + len(corners) + 1 <= max_evals):
        tt_snapped = pvt_metrics.get(nom_corner, m_best)
        tt_chk = check_constraints(tt_snapped, constraints)
        for idx_c, c in enumerate(constraints):
            tt_m = tt_chk["details"][idx_c]["margin"]
            worst_m = tt_m
            for c_name in corners:
                cm = pvt_checks[c_name]["details"][idx_c]["margin"]
                if cm is not None and (worst_m is None or cm < worst_m):
                    worst_m = cm
            if tt_m is not None and worst_m is not None:
                target_shifts[c["id"]] = max(
                    target_shifts.get(c["id"], 0.0), (tt_m - worst_m) + 0.04 * c["scale"]
                )

        merit_best, _ = penalty_barrier_merit(m_best, constraints, obj_spec, obj_ref, target_shifts=target_shifts)
        polish_steps = max(1, min(3, max_evals - len(corners) - eval_counter[0]))
        polished = False
        try:
            for _ in range(polish_steps):
                du_p, _ = _solve_linearized_tr_step(
                    u_best, m_best, jac_u, active_idx, constraints, obj_spec, obj_ref, target_shifts, 0.22
                )
                u_p = [_clamp(u_best[j] + du_p[j], 0.0, 1.0) for j in range(space.dim)]
                m_p = eval_cached(u_p, nom_corner, snap=False)
                _broyden_update(jac_u, [u_p[j] - u_best[j] for j in range(space.dim)], m_best, m_p)
                mer_p, _ = penalty_barrier_merit(m_p, constraints, obj_spec, obj_ref, target_shifts=target_shifts)
                if mer_p < merit_best:
                    u_best, merit_best, m_best = u_p, mer_p, m_p
                    polished = True
        except _BudgetExhausted:
            pass

        if polished:
            cand_ok, cand_metrics, cand_checks, cand_status, cand_ver, cand_unver = (
                evaluate_all_corners_snapped(u_best)
            )
            if not cand_unver:
                pvt_ok = cand_ok
                pvt_metrics = cand_metrics
                pvt_checks = cand_checks
                pvt_status = cand_status
                verified_corners = cand_ver
                unverified_corners = cand_unver

    final_x = space.u_to_x(u_best, snap=True)
    if nom_corner in verified_corners:
        final_tt = pvt_metrics[nom_corner]
    else:
        try:
            final_tt = eval_cached(u_best, nom_corner, snap=True)
        except _BudgetExhausted:
            final_tt = m_best

    init_obj = _safe_finite_float(m0.get(obj_metric))
    final_obj = _safe_finite_float(final_tt.get(obj_metric)) if isinstance(final_tt, dict) else None
    goal_max = str(obj_spec.get("goal", obj_spec.get("sense", "minimize"))).lower().startswith("max")
    if init_obj is None or final_obj is None:
        improvement_pct = 0.0
    elif goal_max:
        improvement_pct = 100.0 * (final_obj - init_obj) / max(abs(init_obj), 1e-18)
    else:
        improvement_pct = 100.0 * (init_obj - final_obj) / max(abs(init_obj), 1e-18)

    # Compute worst-case margin across all PVT corners for every spec
    worst_case_summary = []
    for idx_c, c in enumerate(constraints):
        worst_corner = None
        worst_margin = None
        worst_val = None
        has_fail = False
        has_unverified = False
        for c_name in corners:
            det = pvt_checks[c_name]["details"][idx_c]
            if det["status"] == "NOT_VERIFIED":
                has_unverified = True
                continue
            if det["status"] != "PASS":
                has_fail = True
            if det["margin"] is not None and (worst_margin is None or det["margin"] < worst_margin):
                worst_margin = det["margin"]
                worst_corner = c_name
                worst_val = det["value"]

        if has_fail:
            spec_status = "FAIL"
        elif has_unverified:
            spec_status = "NOT_VERIFIED"
        else:
            spec_status = "PASS"

        worst_case_summary.append({
            "id": c["id"],
            "metric": c["metric"],
            "op": c["op"],
            "target": c["target"],
            "unit": c["unit"],
            "worst_corner": worst_corner,
            "worst_value": worst_val,
            "worst_margin": worst_margin,
            "status": spec_status,
        })

    return {
        "ok": True,
        "release": RELEASE,
        "evaluator_source": evaluator_source,
        "all_specs_pass_pvt": pvt_ok,
        "evaluations": eval_counter[0],
        "max_evaluations": max_evals,
        "corners_requested": list(corners),
        "corners_verified": verified_corners,
        "unverified_corners": unverified_corners,
        "pvt_corner_status": pvt_status,
        "objective": {
            "metric": obj_metric,
            "goal": obj_spec.get("goal", "minimize"),
            "initial_tt": init_obj,
            "final_tt": final_obj,
            "improvement_pct": round(improvement_pct, 2),
        },
        "initial_variables": space.u_to_x(u0, snap=False),
        "optimized_variables_grid_snapped": final_x,
        "stage1_sensitivity": {
            "d_metric_d_lnx": s1["d_metric_d_lnx"],
            "constraint_knob_rankings": s1["constraint_knob_rankings"],
            "pruned_variables": s1["pruned_variables"],
            "partial_sensitivity": s1["partial_sensitivity"],
        },
        "initial_constraints_tt": s1["initial_check"],
        "worst_case_pvt_summary": worst_case_summary,
        "pvt_corner_metrics": pvt_metrics,
        "elapsed_ms": round((TIMER() - t_start) * 1000.0, 3),
    }


def build_demo_miller_ota_problem():
    """Failing over-powered initial 2-stage Miller OTA problem for --self-test & demo."""
    return {
        "schema": "skill-analog.sizing-problem.v1",
        "name": "miller_ota_2stage_gpdk090_1v2",
        "mos_sat_margin_min": 0.05,
        "max_evaluations": 34,
        "corners": ["TT", "SS", "FF"],
        "evaluator": {"type": "builtin_miller_ota_2stage"},
        "objective": {"metric": "power_w", "goal": "minimize"},
        "variables": [
            {"name": "W_in", "init": 10.0e-6, "min": 3.0e-6, "max": 80.0e-6, "scale": "log", "step_grid": 5.0e-9, "role": "input_diff_pair"},
            {"name": "L_ch", "init": 120.0e-9, "min": 120.0e-9, "max": 700.0e-9, "scale": "log", "step_grid": 5.0e-9, "role": "channel_length"},
            {"name": "W_cs", "init": 14.0e-6, "min": 6.0e-6, "max": 160.0e-6, "scale": "log", "step_grid": 5.0e-9, "role": "stage2_driver"},
            {"name": "I_tail", "init": 110.0e-6, "min": 12.0e-6, "max": 180.0e-6, "scale": "log", "step_grid": 1.0e-7, "role": "stage1_bias"},
            {"name": "I_stage2", "init": 280.0e-6, "min": 35.0e-6, "max": 350.0e-6, "scale": "log", "step_grid": 1.0e-7, "role": "stage2_bias"},
            {"name": "C_c", "init": 0.55e-12, "min": 0.40e-12, "max": 4.5e-12, "scale": "log", "step_grid": 1.0e-15, "role": "miller_cap"},
            {"name": "R_z", "init": 120.0, "min": 100.0, "max": 12000.0, "scale": "log", "step_grid": 10.0, "role": "nulling_resistor"},
        ],
        "hard_constraints": [
            {"id": "dc_gain", "metric": "dc_gain_db", "op": ">=", "target": 65.0, "unit": "dB", "scale": 8.0},
            {"id": "ugf", "metric": "ugf_hz", "op": ">=", "target": 25.0e6, "unit": "Hz", "scale": 5.0e6},
            {"id": "phase_margin", "metric": "phase_margin_deg", "op": ">=", "target": 60.0, "unit": "deg", "scale": 8.0},
            {"id": "gain_margin", "metric": "gain_margin_db", "op": ">=", "target": 10.0, "unit": "dB", "scale": 4.0},
            {"id": "slew_rate", "metric": "slew_rate_v_us", "op": ">=", "target": 18.0, "unit": "V/us", "scale": 4.0},
            {"id": "input_noise", "metric": "vn_in_nv_rt_hz", "op": "<=", "target": 18.0, "unit": "nV/rtHz", "scale": 3.0},
            {"id": "mos_sat_margin", "metric": "min_sat_margin_v", "op": ">=", "target": 0.05, "unit": "V", "scale": 0.04},
        ],
    }


def run_self_test():
    tmp_dir = tempfile.mkdtemp(prefix="skill_analog_sizing_opt_")
    try:
        # 1. Core 2-stage Miller OTA closed-loop optimization across TT, SS, FF
        prob = build_demo_miller_ota_problem()
        res = optimize_problem(prob)

        if res.get("evaluator_source") != "builtin_analytical_demo":
            raise AssertionError("Expected evaluator_source='builtin_analytical_demo'")
        if res["initial_constraints_tt"]["all_pass"]:
            raise AssertionError("Self-test initial guess must start from a failing state!")
        if not res["all_specs_pass_pvt"]:
            raise AssertionError(
                "Optimizer failed to satisfy all PVT specs: %s"
                % json.dumps(res["worst_case_pvt_summary"])
            )
        if res["evaluations"] > res["max_evaluations"] or res["evaluations"] >= 35:
            raise AssertionError("Evaluations %d >= 35 limit!" % res["evaluations"])
        if res["objective"]["improvement_pct"] < 38.0:
            raise AssertionError(
                "Power reduction %.2f%% < 38%% target!" % res["objective"]["improvement_pct"]
            )
        opt_x = res["optimized_variables_grid_snapped"]
        for mvar in ("W_in", "L_ch", "W_cs"):
            rem = abs((opt_x[mvar] / 5.0e-9) - round(opt_x[mvar] / 5.0e-9))
            if rem > 1e-6:
                raise AssertionError("Variable %s=%.12g not snapped to 5nm grid!" % (mvar, opt_x[mvar]))

        # 2. Reject empty corners and max_evaluations < 1
        for bad_patch in (
            {"corners": []},
            {"corners": None},
            {"max_evaluations": 0},
            {"max_evaluations": -4},
        ):
            bad_p = build_demo_miller_ota_problem()
            bad_p.update(bad_patch)
            rejected = False
            try:
                optimize_problem(bad_p)
            except SizingOptError:
                rejected = True
            if not rejected:
                raise AssertionError("Failed to reject invalid problem patch: %s" % repr(bad_patch))

        # 3. Hard max_evaluations ceiling (even max_evaluations=1, on-grid & off-grid!)
        for max_b in (1, 2, 5):
            p_b = build_demo_miller_ota_problem()
            p_b["max_evaluations"] = max_b
            p_b["variables"][0]["init"] = 10.0023e-6  # off-grid so snap=True differs from snap=False
            r_b = optimize_problem(p_b)
            if r_b["evaluations"] > max_b:
                raise AssertionError("Exceeded max_evaluations=%d (got %d)!" % (max_b, r_b["evaluations"]))
            if max_b == 1:
                if r_b["evaluations"] != 1:
                    raise AssertionError("Expected exact 1 evaluation for max_evaluations=1")
                if r_b["all_specs_pass_pvt"]:
                    raise AssertionError("all_specs_pass_pvt MUST be False when corners are NOT_VERIFIED!")
                if "SS" not in r_b["unverified_corners"] or r_b["pvt_corner_status"]["SS"] != "NOT_VERIFIED":
                    raise AssertionError("Unverified corner SS must be marked NOT_VERIFIED!")

        # 4. Infeasible step_grid interval [46, 49] with step_grid=5 rejected
        caught_grid_ds = False
        try:
            DesignSpace([{"name": "x_bad", "min": 46.0, "max": 49.0, "init": 47.0, "scale": "lin", "step_grid": 5.0}])
        except SizingOptError:
            caught_grid_ds = True
        caught_grid_snap = False
        try:
            _snap_val(47.0, 5.0, 46.0, 49.0)
        except SizingOptError:
            caught_grid_snap = True
        if not (caught_grid_ds and caught_grid_snap):
            raise AssertionError("Failed to reject [46, 49] with step_grid=5!")

        # 5. check_constraints: strict < and >, picosecond tolerance, NaN and Inf
        for c_desc, m_test, c_test in (
            ("strict_lt_equal", {"m": 1.0}, [{"id": "c1", "metric": "m", "op": "<", "target": 1.0, "scale": 1.0}]),
            ("strict_gt_equal", {"m": 1.0}, [{"id": "c1", "metric": "m", "op": ">", "target": 1.0, "scale": 1.0}]),
            ("ps_strict_lt", {"m": 2.0e-12}, [{"id": "c1", "metric": "m", "op": "<", "target": 1.0e-12, "scale": 1.0}]),
            ("ps_le", {"m": 2.0e-12}, [{"id": "c1", "metric": "m", "op": "<=", "target": 1.0e-12, "scale": 1.0}]),
            ("nan_metric", {"m": float("nan")}, [{"id": "c1", "metric": "m", "op": ">=", "target": 1.0, "scale": 1.0}]),
            ("inf_metric", {"m": float("inf")}, [{"id": "c1", "metric": "m", "op": "<=", "target": 10.0, "scale": 1.0}]),
        ):
            chk_t = check_constraints(m_test, c_test)
            if chk_t["all_pass"] or chk_t["all_guarded_pass"] or chk_t["details"][0]["status"] != "FAIL":
                raise AssertionError(
                    "check_constraints failed adversarial case %s: %s" % (c_desc, repr(chk_t))
                )
        chk_nan = check_constraints(
            {"m": float("nan")}, [{"id": "c1", "metric": "m", "op": ">=", "target": 1.0, "scale": 1.0}]
        )
        if chk_nan["total_violation"] < 10.0:
            raise AssertionError("Expected total_violation >= 10.0 for NaN metric!")

        # 6. Linear-scale variable dM / d(ln x) = x * dM/dx (M = x at x = 2 -> 2.0)
        lin_prob = {
            "enforce_mos_sat_margin": False,
            "corners": ["TT"],
            "max_evaluations": 10,
            "evaluator": {
                "type": "callable",
                "fn": lambda params, corner="TT": {"M": float(params["x"])},
            },
            "objective": {"metric": "M", "goal": "minimize"},
            "variables": [
                {"name": "x", "init": 2.0, "min": 0.5, "max": 4.5, "scale": "lin"},
            ],
            "hard_constraints": [
                {"id": "m_min", "metric": "M", "op": ">=", "target": 1.0, "scale": 1.0},
            ],
        }
        s1_lin = optimize_problem(lin_prob, sensitivity_only=True)
        dlnx_val = s1_lin["sensitivity_d_metric_d_lnx"]["M"]["x"]
        if abs(dlnx_val - 2.0) > 1e-9:
            raise AssertionError("Expected dM/d(ln x) = 2.0 for M=x at x=2, got %.9f" % dlnx_val)

        # 7. Explicit FS / SF corners distinct from TT & invalid corner rejection
        init_vars = DesignSpace(prob["variables"]).init_x()
        m_tt = evaluate_miller_ota_2stage(init_vars, "TT")
        m_fs = evaluate_miller_ota_2stage(init_vars, "FS")
        m_sf = evaluate_miller_ota_2stage(init_vars, "SF")
        if not (m_fs["vn_in_nv_rt_hz"] < m_tt["vn_in_nv_rt_hz"] < m_sf["vn_in_nv_rt_hz"]):
            raise AssertionError("FS / TT / SF NMOS thermal noise ordering invalid!")
        if abs(m_fs["phase_margin_deg"] - m_sf["phase_margin_deg"]) < 0.5:
            raise AssertionError("FS and SF PMOS 2nd-stage phase margins should differ significantly!")
        caught_bad_corner = False
        try:
            evaluate_miller_ota_2stage(init_vars, "UNKNOWN_CORNER")
        except SizingOptError:
            caught_bad_corner = True
        if not caught_bad_corner:
            raise AssertionError("Failed to reject unrecognized corner in evaluate_miller_ota_2stage!")

        # 8. Command-based external evaluator + CLI exit code 1 on infeasible spec & 0 on sensitivity-only
        eval_script = os.path.join(tmp_dir, "ext_eval.py")
        ext_code = (
            "from __future__ import division, print_function\n"
            "import json, sys\n"
            "sys.path.insert(0, %r)\n"
            "import sizing_opt\n"
            "f = open(sys.argv[1], 'rb')\n"
            "d = json.loads(f.read().decode('utf-8'))\n"
            "f.close()\n"
            "m = sizing_opt.evaluate_miller_ota_2stage(d['params'], d['corner'])\n"
            "o = open(sys.argv[2], 'wb')\n"
            "o.write(json.dumps(m).encode('utf-8'))\n"
            "o.close()\n"
        ) % os.path.dirname(os.path.realpath(__file__))
        ef = open(eval_script, "wb")
        try:
            ef.write(ext_code.encode("utf-8"))
        finally:
            ef.close()

        ext_prob = build_demo_miller_ota_problem()
        ext_prob["evaluator"] = {
            "type": "command",
            "cmd": [sys.executable, "-B", eval_script, "{params_json}", "{out_json}"],
        }
        s1_ext = optimize_problem(ext_prob, sensitivity_only=True)
        if not s1_ext["ok"] or s1_ext["evaluations"] != 8 or s1_ext["evaluator_source"] != "external_command":
            raise AssertionError("Command evaluator sensitivity-only check failed!")

        infeas_prob = build_demo_miller_ota_problem()
        infeas_prob["max_evaluations"] = 10
        infeas_prob["hard_constraints"][0]["target"] = 240.0  # impossible 240 dB DC gain in 2-stage
        infeas_path = os.path.join(tmp_dir, "infeasible_prob.json")
        pf = open(infeas_path, "wb")
        try:
            pf.write(json.dumps(infeas_prob).encode("utf-8"))
        finally:
            pf.close()

        self_script = os.path.realpath(__file__)
        proc_fail = subprocess.Popen(
            [sys.executable, "-B", self_script, "--problem", infeas_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out_fail, _ = proc_fail.communicate()
        if proc_fail.returncode != 1:
            raise AssertionError("CLI must return exit code 1 on infeasible spec, got %d" % proc_fail.returncode)
        parsed_fail = json.loads(out_fail.decode("utf-8"))
        if parsed_fail.get("all_specs_pass_pvt") is not False:
            raise AssertionError("Infeasible problem must report all_specs_pass_pvt=False")

        proc_s1 = subprocess.Popen(
            [sys.executable, "-B", self_script, "--sensitivity-only", "--problem", infeas_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        proc_s1.communicate()
        if proc_s1.returncode != 0:
            raise AssertionError("CLI --sensitivity-only must return exit code 0 when ok=True")

        # 9. Unit scaling & dimension mismatch regression (0.002 W vs 0.4 mW MUST FAIL!)
        unit_prob = {
            "enforce_mos_sat_margin": False,
            "hard_constraints": [
                {"id": "p_max", "metric": "power_w", "op": "<=", "target": 0.4, "unit": "mW"},
            ],
        }
        unit_cons = normalize_constraints(unit_prob)
        if abs(unit_cons[0]["target"] - 0.0004) > 1e-12:
            raise AssertionError("Expected 0.4 mW -> 0.0004 W, got %r" % unit_cons[0]["target"])
        chk_p_over = check_constraints({"power_w": 0.002}, unit_cons)
        if chk_p_over["all_pass"] or chk_p_over["details"][0]["status"] != "FAIL":
            raise AssertionError("0.002 W MUST FAIL against 0.4 mW constraint!")
        caught_bad_dim = False
        try:
            normalize_constraints({
                "enforce_mos_sat_margin": False,
                "hard_constraints": [
                    {"id": "bad_u", "metric": "dc_gain_db", "op": ">=", "target": 60.0, "unit": "mV"},
                ],
            })
        except SizingOptError:
            caught_bad_dim = True
        if not caught_bad_dim:
            raise AssertionError("Failed to reject dimensionally incompatible unit mV on dc_gain_db!")

        # 10. Unit 'mohm' (1e-3 Ohm) vs 'Mohm' (1e6 Ohm) (#8)
        res_u_cons = normalize_constraints({
            "enforce_mos_sat_margin": False,
            "hard_constraints": [
                {"id": "r_lo", "metric": "ron_ohm", "op": "<=", "target": 50.0, "unit": "mohm"},
                {"id": "r_hi", "metric": "rout_ohm", "op": ">=", "target": 2.0, "unit": "Mohm"},
            ],
        })
        if abs(res_u_cons[0]["target"] - 0.05) > 1e-12:
            raise AssertionError("Expected 50 mohm -> 0.05 ohm, got %r" % res_u_cons[0]["target"])
        if abs(res_u_cons[1]["target"] - 2.0e6) > 1e-6:
            raise AssertionError("Expected 2 Mohm -> 2e6 ohm, got %r" % res_u_cons[1]["target"])

        # 11. Stage-1 & TR/Broyden None/non-finite metric crash guard (#9)
        none_eval_calls = [0]

        def _none_metric_eval(params, corner="TT"):
            none_eval_calls[0] += 1
            x = float(params["x"])
            if none_eval_calls[0] == 2:
                return {"power_w": None, "gain_db": None}
            return {"power_w": x * 1e-3, "gain_db": 40.0 + 10.0 * x}

        none_prob = {
            "enforce_mos_sat_margin": False,
            "corners": ["TT"],
            "max_evaluations": 12,
            "evaluator": {"type": "callable", "fn": _none_metric_eval},
            "objective": {"metric": "power_w", "goal": "minimize"},
            "variables": [{"name": "x", "init": 1.0, "min": 0.5, "max": 3.0, "scale": "lin"}],
            "hard_constraints": [{"id": "g1", "metric": "gain_db", "op": ">=", "target": 55.0, "unit": "dB"}],
        }
        none_res = optimize_problem(none_prob)
        if not none_res["ok"]:
            raise AssertionError("Optimizer crashed or failed on intermittent None metrics!")
        if compute_objective_norm({"power_w": None}, {"metric": "power_w", "goal": "minimize"}, 1.0) < 1e5:
            raise AssertionError("compute_objective_norm must penalize None metric with large finite value!")

        # 12. Reject NaN/Inf/bool constraint targets in normalize_constraints & check_constraints (#16)
        for bad_t in (float("nan"), float("inf"), float("-inf"), True, False):
            caught_n = False
            try:
                normalize_constraints({
                    "enforce_mos_sat_margin": False,
                    "hard_constraints": [{"id": "bt", "metric": "dc_gain_db", "op": ">=", "target": bad_t}],
                })
            except SizingOptError:
                caught_n = True
            if not caught_n:
                raise AssertionError("normalize_constraints failed to reject target=%r!" % (bad_t,))
            caught_c = False
            try:
                check_constraints(
                    {"dc_gain_db": 60.0},
                    [{"id": "bt", "metric": "dc_gain_db", "op": ">=", "target": bad_t, "scale": 1.0}],
                )
            except SizingOptError:
                caught_c = True
            if not caught_c:
                raise AssertionError("check_constraints failed to reject target=%r!" % (bad_t,))

        # 13. Template canonical & legacy aliases (mos_sat_margin_min_v, pvt_corners, step_grid_m) (#21)
        alias_prob = {
            "mos_sat_margin_min_v": 0.08,
            "pvt_corners": ["TT", "SS"],
            "step_grid_m": 0.1,
            "max_evaluations": 10,
            "evaluator": {
                "type": "callable",
                "fn": lambda params, corner="TT": {
                    "power_w": float(params["w"]) * 1e-3,
                    "min_sat_margin_v": 0.12 if corner == "TT" else 0.09,
                },
            },
            "objective": {"metric": "power_w", "goal": "minimize"},
            "variables": [{"name": "w", "init": 1.05, "min": 0.5, "max": 2.0, "scale": "lin"}],
            "hard_constraints": [],
        }
        alias_cons = normalize_constraints(alias_prob)
        if abs(alias_cons[0]["target"] - 0.08) > 1e-12:
            raise AssertionError("Legacy alias mos_sat_margin_min_v not honored: %r" % alias_cons)
        alias_res = optimize_problem(alias_prob)
        if alias_res["corners_requested"] != ["TT", "SS"] or not alias_res["all_specs_pass_pvt"]:
            raise AssertionError("Legacy aliases pvt_corners/step_grid_m failed: %r" % alias_res)
        w_snap = alias_res["optimized_variables_grid_snapped"]["w"]
        if abs((w_snap / 0.1) - round(w_snap / 0.1)) > 1e-6:
            raise AssertionError("Legacy step_grid_m=0.1 was not snapped: w=%r" % w_snap)

        return {
            "ok": True,
            "release": RELEASE,
            "self_test": "PASS",
            "evaluations": res["evaluations"],
            "all_specs_pass_pvt": res["all_specs_pass_pvt"],
            "corners_verified": res["corners_verified"],
            "initial_power_uw": round(res["objective"]["initial_tt"] * 1e6, 2),
            "optimized_power_uw": round(res["objective"]["final_tt"] * 1e6, 2),
            "power_reduction_pct": res["objective"]["improvement_pct"],
            "optimized_variables": opt_x,
            "worst_case_pvt_summary": res["worst_case_pvt_summary"],
            "phase_margin_dominant_knobs": res["stage1_sensitivity"]["constraint_knob_rankings"]["phase_margin"]["dominant_knobs"][:3],
            "dc_gain_dominant_knobs": res["stage1_sensitivity"]["constraint_knob_rankings"]["dc_gain"]["dominant_knobs"][:3],
            "redteam_guards_verified": [
                "empty_corners_and_nonpositive_budget_rejected",
                "hard_max_evaluations_ceiling_with_not_verified_corners",
                "infeasible_step_grid_bounds_rejected",
                "strict_inequality_picosecond_and_nan_constraints_fail",
                "linear_variable_d_metric_d_lnx_exact",
                "fs_sf_skewed_corners_and_invalid_corner_rejected",
                "infeasible_cli_returns_exit_1",
                "mohm_vs_Mohm_unit_scaling_verified",
                "none_metric_stage1_tr_broyden_guarded",
                "nonfinite_and_bool_targets_rejected",
                "template_canonical_and_legacy_aliases_verified",
            ],
            "elapsed_ms": res["elapsed_ms"],
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def build_parser():
    usage = (
        "Usage:\n"
        "  python tools/sizing_opt.py --problem PROBLEM.json [--out RESULT.json]\n"
        "  python tools/sizing_opt.py --sensitivity-only --problem PROBLEM.json\n"
        "  python tools/sizing_opt.py --write-demo-problem PATH\n"
        "  python tools/sizing_opt.py --self-test"
    )
    p = optparse.OptionParser(usage=usage)
    p.add_option("--problem", dest="problem_path", default=None, help="Input optimization problem JSON file")
    p.add_option("--out", dest="out_path", default=None, help="Optional output JSON file (outside SKILL-ANALOG/library)")
    p.add_option("--sensitivity-only", dest="sensitivity_only", action="store_true", default=False,
                 help="Run Stage 1 finite-difference Sensitivity Jacobian only")
    p.add_option("--write-demo-problem", dest="demo_prob_path", default=None, metavar="PATH",
                 help="Write sample 2-stage Miller OTA optimization problem JSON to PATH")
    p.add_option("--self-test", dest="self_test", action="store_true", default=False,
                 help="Run 2-stage Miller OTA self-test (<35 evals, 100% PVT pass, >=38% power cut)")
    return p


def main(argv=None):
    parser = build_parser()
    opts, extra = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if extra:
        print(json.dumps({"ok": False, "error": "Unexpected arguments: " + " ".join(extra)}, indent=2, sort_keys=True))
        return 2

    try:
        if opts.self_test:
            res = run_self_test()
            print(json.dumps(res, indent=2, sort_keys=True))
            return 0 if res.get("ok") else 1

        if opts.demo_prob_path:
            if _is_inside(opts.demo_prob_path, LIBRARY_ROOT):
                raise SizingOptError("Demo problem output must not reside inside SKILL-ANALOG/library.")
            parent = os.path.dirname(os.path.abspath(opts.demo_prob_path))
            if parent and not os.path.isdir(parent):
                os.makedirs(parent)
            prob = build_demo_miller_ota_problem()
            f = open(opts.demo_prob_path, "wb")
            try:
                f.write((json.dumps(prob, indent=2, sort_keys=True) + "\n").encode("utf-8"))
            finally:
                f.close()
            print(json.dumps({"ok": True, "problem_path": os.path.realpath(opts.demo_prob_path)}, indent=2, sort_keys=True))
            return 0

        if not opts.problem_path:
            parser.print_help()
            return 0

        if not os.path.isfile(opts.problem_path):
            raise SizingOptError("Problem file not found: %s" % opts.problem_path)
        pf = open(opts.problem_path, "rb")
        try:
            prob = json.loads(pf.read().decode("utf-8"))
        finally:
            pf.close()

        res = optimize_problem(prob, sensitivity_only=opts.sensitivity_only)
        if opts.out_path:
            if _is_inside(opts.out_path, LIBRARY_ROOT):
                raise SizingOptError("Result output must not reside inside SKILL-ANALOG/library.")
            parent = os.path.dirname(os.path.abspath(opts.out_path))
            if parent and not os.path.isdir(parent):
                os.makedirs(parent)
            of = open(opts.out_path, "wb")
            try:
                of.write((json.dumps(res, indent=2, sort_keys=True) + "\n").encode("utf-8"))
            finally:
                of.close()

        print(json.dumps(res, indent=2, sort_keys=True))
        if res.get("ok") and (opts.sensitivity_only or res.get("all_specs_pass_pvt")):
            return 0
        return 1
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2, sort_keys=True))
        return 1


if __name__ == "__main__":
    sys.exit(main())
