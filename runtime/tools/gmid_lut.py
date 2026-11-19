#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Sub-5ms Pure-Stdlib gm/ID Lookup Table Interpolator & Transistor Sizer.

100% compatible with RHEL 6.5 Python 2.6.6 and Python 3.x (zero external dependencies:
no numpy, no scipy, no argparse, no f-strings, no dict/set comprehensions).

Implements 3D Trilinear (L, VDS, VSB) + Fritsch-Carlson Monotone Piecewise Cubic Hermite
Spline (PCHIP) inverse ratio solver for Murmann gm/ID methodology:
  - query:    (dev, L, gm/ID, VDS, VSB) -> true realized gm/ID (+ interp error), JD, gm/gds, fT,
              VGS, Vdsat, Vth, Cgg/W, Cgd/Cgg, Cdd/Cgg, multi-terminal SOA check (VGB, VDB)
  - size:     (dev, gm or ID, gm/ID, L, VDS, VSB) -> ID, W_total, even nf>=2, W_finger (5nm grid),
              full realized operating point re-queried at JD_realized = ID / W_total
  - tradeoff: Pareto table across (gm/ID, L) -> (gm*ro, fT, JD, Vdsat) + role recommendations

Release: 2026.11.19.1
"""
from __future__ import division, print_function

import bisect
import gzip
import json
import math
import optparse
import os
import shutil
import sys
import tempfile
import time

sys.dont_write_bytecode = True

TOOLS_DIR = os.path.dirname(os.path.realpath(__file__))
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

import gpdk_techsweep  # noqa: E402

RELEASE = "2026.11.19.1"
TIMER = getattr(time, "perf_counter", time.time)

DEV_ALIASES = {
    "n": "nmos",
    "nmos": "nmos",
    "nch": "nmos",
    "nfet": "nmos",
    "mn": "nmos",
    "p": "pmos",
    "pmos": "pmos",
    "pch": "pmos",
    "pfet": "pmos",
    "mp": "pmos",
}


class LutError(Exception):
    pass


class LutBoundsError(LutError):
    pass


def _require_finite(val, name):
    if isinstance(val, bool):
        raise LutError("%s must be a finite number (got bool)" % name)
    try:
        f = float(val)
    except (TypeError, ValueError):
        raise LutError("%s must be a finite number (got %r)" % (name, val))
    if math.isnan(f) or math.isinf(f):
        raise LutError("%s must be finite (got %r)" % (name, val))
    return f


def _format_spectre_dim(val_m):
    """Format meter dimension as valid Spectre engineering string (no scientific notation + suffix, 5nm precision)."""
    val = _require_finite(val_m, "dimension")
    av = abs(val)
    if av == 0.0:
        return "0"
    if av >= 1.0:
        scaled, suf, ndec = val, "", 9
    elif av >= 1.0e-3:
        scaled, suf, ndec = val * 1.0e3, "m", 6
    elif av >= 1.0e-6:
        scaled, suf, ndec = val * 1.0e6, "u", 6
    elif av >= 1.0e-9:
        scaled, suf, ndec = val * 1.0e9, "n", 3
    else:
        scaled, suf, ndec = val * 1.0e12, "p", 3
    fmt = ("%%.%df" % ndec) % scaled
    if "." in fmt:
        fmt = fmt.rstrip("0").rstrip(".")
    if fmt == "-0":
        fmt = "0"
    return fmt + suf


def _snap_grid(val, grid):
    if grid is None or grid <= 0.0:
        return val
    return round(val / grid) * grid


def _is_within_axis(axis, x_val):
    if not axis:
        return False
    if isinstance(x_val, bool) or math.isnan(x_val) or math.isinf(x_val):
        return False
    if len(axis) == 1:
        return abs(x_val - axis[0]) <= max(1e-12, 1e-4 * abs(axis[0]))
    lo = axis[0]
    hi = axis[-1]
    tol = 1e-9 * max(1.0, abs(hi - lo))
    return (lo - tol) <= x_val <= (hi + tol)


def _bracket_1d(axis, x_val, axis_name, allow_extrapolate=False):
    x_val = _require_finite(x_val, axis_name)
    n = len(axis)
    if n == 0:
        raise LutError("Empty LUT axis: %s" % axis_name)
    if n == 1:
        if not allow_extrapolate and abs(x_val - axis[0]) > max(1e-12, 1e-4 * abs(axis[0])):
            raise LutBoundsError(
                "%s=%.4g out of single-point LUT domain [%.4g]" % (axis_name, x_val, axis[0])
            )
        return 0, 0, 0.0

    lo = axis[0]
    hi = axis[-1]
    tol = 1e-9 * max(1.0, abs(hi - lo))
    if x_val < lo - tol or x_val > hi + tol:
        if not allow_extrapolate:
            raise LutBoundsError(
                "%s=%.6g out of LUT bounds [%.6g, %.6g]" % (axis_name, x_val, lo, hi)
            )
        if x_val <= lo:
            return 0, 1, 0.0
        return n - 2, n - 1, 1.0

    if x_val <= lo + tol:
        return 0, 0, 0.0
    if x_val >= hi - tol:
        return n - 1, n - 1, 0.0

    idx = bisect.bisect_right(axis, x_val) - 1
    if idx < 0:
        idx = 0
    elif idx >= n - 1:
        idx = n - 2
    denom = axis[idx + 1] - axis[idx]
    w = (x_val - axis[idx]) / denom if denom > 0.0 else 0.0
    if abs(w) < 1e-12:
        return idx, idx, 0.0
    if abs(w - 1.0) < 1e-12:
        return idx + 1, idx + 1, 0.0
    return idx, idx + 1, w


def pchip_slopes(x, y):
    """Fritsch-Carlson (1980) / Brodlie shape-preserving monotone cubic Hermite slopes."""
    n = len(x)
    if n < 2:
        return [0.0] * n
    h = []
    delta = []
    for k in range(n - 1):
        hk = x[k + 1] - x[k]
        if hk <= 0.0:
            raise LutError("PCHIP requires strictly increasing x knots.")
        h.append(hk)
        delta.append((y[k + 1] - y[k]) / hk)

    if n == 2:
        return [delta[0], delta[0]]

    m = [0.0] * n
    for k in range(1, n - 1):
        d0 = delta[k - 1]
        d1 = delta[k]
        if d0 * d1 <= 0.0:
            m[k] = 0.0
        else:
            w1 = 2.0 * h[k] + h[k - 1]
            w2 = h[k] + 2.0 * h[k - 1]
            m[k] = (w1 + w2) / (w1 / d0 + w2 / d1)

    # Non-centered shape-preserving endpoint derivatives
    m0 = ((2.0 * h[0] + h[1]) * delta[0] - h[0] * delta[1]) / (h[0] + h[1])
    if m0 * delta[0] <= 0.0:
        m0 = 0.0
    elif (delta[0] * delta[1] < 0.0) and (abs(m0) > 3.0 * abs(delta[0])):
        m0 = 3.0 * delta[0]
    m[0] = m0

    mn = ((2.0 * h[n - 2] + h[n - 3]) * delta[n - 2] - h[n - 2] * delta[n - 3]) / (h[n - 2] + h[n - 3])
    if mn * delta[n - 2] <= 0.0:
        mn = 0.0
    elif (delta[n - 2] * delta[n - 3] < 0.0) and (abs(mn) > 3.0 * abs(delta[n - 2])):
        mn = 3.0 * delta[n - 2]
    m[n - 1] = mn
    return m


def interp1d_eval(x, y, x_q, method="pchip", precomputed_slopes=None):
    """Evaluate 1D PCHIP or linear interpolant at x_q on strictly ascending x."""
    n = len(x)
    if n == 1:
        return y[0]
    if x_q <= x[0]:
        return y[0]
    if x_q >= x[-1]:
        return y[-1]

    k = bisect.bisect_right(x, x_q) - 1
    if k < 0:
        k = 0
    elif k >= n - 1:
        k = n - 2
    hk = x[k + 1] - x[k]
    t = (x_q - x[k]) / hk
    if method == "linear" or n == 2:
        return y[k] + t * (y[k + 1] - y[k])

    m = precomputed_slopes if precomputed_slopes is not None else pchip_slopes(x, y)
    omt = 1.0 - t
    h00 = (1.0 + 2.0 * t) * omt * omt
    h10 = t * omt * omt
    h01 = t * t * (3.0 - 2.0 * t)
    h11 = t * t * (t - 1.0)
    return h00 * y[k] + h10 * hk * m[k] + h01 * y[k + 1] + h11 * hk * m[k + 1]


def _prepare_monotone_increasing(x_raw, y_raw):
    """Deduplicate/enforce strict increase in x_raw for inverse ratio lookup."""
    pairs = sorted(zip(x_raw, y_raw), key=lambda item: item[0])
    x_clean = []
    y_clean = []
    for xv, yv in pairs:
        if not x_clean:
            x_clean.append(xv)
            y_clean.append(yv)
        elif xv > x_clean[-1] + 1e-9:
            x_clean.append(xv)
            y_clean.append(yv)
    return x_clean, y_clean


class GmidLut(object):
    """Fast pure-stdlib 4D gm/ID Lookup Table loaded from .lut.json.gz."""

    def __init__(self, data, source_path=None):
        if not isinstance(data, dict) or data.get("schema") != "skill-analog.gmid-lut.v1":
            raise LutError("Unsupported LUT schema (expected 'skill-analog.gmid-lut.v1').")
        self.data = data
        self.source_path = source_path
        self.provenance = data.get("provenance", {})
        self.devices = data.get("devices", {})
        self._slice_cache = {}

    def resolve_device(self, dev):
        key = DEV_ALIASES.get(str(dev).strip().lower())
        if not key or key not in self.devices:
            raise LutError(
                "Unknown device '%s'. Available in LUT: %s"
                % (dev, ", ".join(sorted(self.devices.keys())))
            )
        return key, self.devices[key]

    def _check_soa(self, dev_key, vgs_mag, vds_mag, vsb_mag, allow_soa_violation=True):
        """Evaluate single- and multi-terminal SOA bounds (VDD/VGS/VDS, VSB, |VGB|, |VDB|)."""
        vgs_mag = _require_finite(vgs_mag, "vgs")
        vds_mag = _require_finite(vds_mag, "vds")
        vsb_mag = _require_finite(vsb_mag, "vsb")
        vgb_mag = vgs_mag + vsb_mag
        vdb_mag = vds_mag + vsb_mag
        violations = []
        soa_limits = self.provenance.get("soa_limits")
        if isinstance(soa_limits, dict) and soa_limits:
            vdd_lim = soa_limits.get("vdd_max")
            vgs_lim = soa_limits.get("vgs_max", vdd_lim)
            vds_lim = soa_limits.get("vds_max", vdd_lim)
            vsb_lim = soa_limits.get("vsb_max")
            vgb_lim = soa_limits.get("vgb_max")
            vdb_lim = soa_limits.get("vdb_max")
            if vgs_lim is not None and vgs_mag > float(vgs_lim) + 1e-9:
                violations.append("|VGS|=%.4gV > vgs_max=%.4gV" % (vgs_mag, float(vgs_lim)))
            if vds_lim is not None and vds_mag > float(vds_lim) + 1e-9:
                violations.append("|VDS|=%.4gV > vds_max=%.4gV" % (vds_mag, float(vds_lim)))
            if vsb_lim is not None and vsb_mag > float(vsb_lim) + 1e-9:
                violations.append("|VSB|=%.4gV > vsb_max=%.4gV" % (vsb_mag, float(vsb_lim)))
            if vgb_lim is not None and vgb_mag > float(vgb_lim) + 1e-9:
                violations.append(
                    "|VGB|=|VGS|+|VSB|=%.4gV > vgb_max=%.4gV" % (vgb_mag, float(vgb_lim))
                )
            if vdb_lim is not None and vdb_mag > float(vdb_lim) + 1e-9:
                violations.append(
                    "|VDB|=|VDS|+|VSB|=%.4gV > vdb_max=%.4gV" % (vdb_mag, float(vdb_lim))
                )
        elif self.provenance.get("vdd_max_v") is not None:
            vdd_lim = float(self.provenance["vdd_max_v"])
            if vgs_mag > vdd_lim + 1e-9:
                violations.append("|VGS|=%.4gV > vdd_max=%.4gV" % (vgs_mag, vdd_lim))
            if vds_mag > vdd_lim + 1e-9:
                violations.append("|VDS|=%.4gV > vdd_max=%.4gV" % (vds_mag, vdd_lim))
        else:
            violations.append("Missing SOA metadata (soa_limits / vdd_max_v) in LUT provenance")

        soa_ok = (len(violations) == 0)
        if (not soa_ok) and (not allow_soa_violation):
            raise LutBoundsError("SOA violation for %s: %s" % (dev_key, "; ".join(violations)))
        return soa_ok, violations, vgb_mag, vdb_mag

    def _slice_vgs_curves(self, dev_entry, l_m, vds, vsb, allow_extrapolate=False):
        """Trilinearly interpolate all VGS-curves at (l_m, vds, vsb) in < 0.1 ms."""
        l_ax = dev_entry["L"]
        d_ax = dev_entry["VDS"]
        b_ax = dev_entry["VSB"]
        g_ax = dev_entry["VGS"]
        n_l, n_d, n_b, n_g = dev_entry["shape"]

        il0, il1, wl = _bracket_1d(l_ax, l_m, "L", allow_extrapolate)
        id0, id1, wd = _bracket_1d(d_ax, abs(vds), "VDS", allow_extrapolate)
        ib0, ib1, wb = _bracket_1d(b_ax, abs(vsb), "VSB", allow_extrapolate)

        l_terms = ((il0, 1.0 - wl),) if il0 == il1 else ((il0, 1.0 - wl), (il1, wl))
        d_terms = ((id0, 1.0 - wd),) if id0 == id1 else ((id0, 1.0 - wd), (id1, wd))
        b_terms = ((ib0, 1.0 - wb),) if ib0 == ib1 else ((ib0, 1.0 - wb), (ib1, wb))

        corners = []
        for il, w_l in l_terms:
            for id_i, w_d in d_terms:
                for ib, w_b in b_terms:
                    w_tot = w_l * w_d * w_b
                    if w_tot > 0.0:
                        base = ((il * n_d + id_i) * n_b + ib) * n_g
                        corners.append((base, w_tot))

        fields = dev_entry["fields"]
        wanted_fields = (
            "id_w", "gm_w", "gds_w", "gmb_w", "vth", "vdsat",
            "cgg_w", "cgs_w", "cgd_w", "cdd_w", "sth_w", "sfl_w",
        )
        curves = {}
        for fname in wanted_fields:
            arr = fields.get(fname)
            if not arr:
                curves[fname] = [0.0] * n_g
                continue
            if len(corners) == 1:
                base0, _ = corners[0]
                curves[fname] = arr[base0: base0 + n_g]
            else:
                out_vec = [0.0] * n_g
                for base, weight in corners:
                    seg = arr[base: base + n_g]
                    for k in range(n_g):
                        out_vec[k] += weight * seg[k]
                curves[fname] = out_vec
        return g_ax, curves

    def _get_prepared_slice(self, dev_key, dev_entry, l_val, vds_mag, vsb_mag, allow_extrapolate):
        in_domain = (
            _is_within_axis(dev_entry["L"], l_val)
            and _is_within_axis(dev_entry["VDS"], vds_mag)
            and _is_within_axis(dev_entry["VSB"], vsb_mag)
        )
        if not in_domain and not allow_extrapolate:
            # Trigger exact LutBoundsError message via _bracket_1d
            self._slice_vgs_curves(dev_entry, l_val, vds_mag, vsb_mag, False)

        ckey = (
            dev_key,
            round(l_val, 12),
            round(vds_mag, 9),
            round(vsb_mag, 9),
            False if in_domain else True,
        )
        cached = self._slice_cache.get(ckey)
        if cached is not None:
            return cached

        g_ax, curves = self._slice_vgs_curves(dev_entry, l_val, vds_mag, vsb_mag, allow_extrapolate)
        n_g = len(g_ax)
        id_w_vec = [max(v, 1e-18) for v in curves["id_w"]]
        gm_w_vec = [max(v, 1e-18) for v in curves["gm_w"]]
        gm_id_vec = [gm_w_vec[k] / id_w_vec[k] for k in range(n_g)]

        idx_peak = 0
        peak_val = gm_id_vec[0]
        for k in range(1, n_g):
            if gm_id_vec[k] > peak_val:
                peak_val = gm_id_vec[k]
                idx_peak = k

        gmid_branch = gm_id_vec[idx_peak:]
        vgs_branch = g_ax[idx_peak:]
        x_gmid_inc, y_gmid_vgs = _prepare_monotone_increasing(gmid_branch, vgs_branch)
        m_gmid_vgs = pchip_slopes(x_gmid_inc, y_gmid_vgs)

        log_id_vec = [math.log(v) for v in id_w_vec]
        log_gm_vec = [math.log(v) for v in gm_w_vec]
        log_gds_vec = [math.log(max(v, 1e-19)) for v in curves["gds_w"]]

        idx_min_id = 0
        min_id_v = id_w_vec[0]
        for k in range(1, n_g):
            if id_w_vec[k] <= min_id_v:
                min_id_v = id_w_vec[k]
                idx_min_id = k
        x_logid_inc, y_logid_vgs = _prepare_monotone_increasing(
            log_id_vec[idx_min_id:], g_ax[idx_min_id:]
        )

        slopes = {
            "log_id": pchip_slopes(g_ax, log_id_vec),
            "log_gm": pchip_slopes(g_ax, log_gm_vec),
            "log_gds": pchip_slopes(g_ax, log_gds_vec),
            "gmb_w": pchip_slopes(g_ax, curves["gmb_w"]),
            "vth": pchip_slopes(g_ax, curves["vth"]),
            "vdsat": pchip_slopes(g_ax, curves["vdsat"]),
            "cgg_w": pchip_slopes(g_ax, curves["cgg_w"]),
            "cgs_w": pchip_slopes(g_ax, curves["cgs_w"]),
            "cgd_w": pchip_slopes(g_ax, curves["cgd_w"]),
            "cdd_w": pchip_slopes(g_ax, curves["cdd_w"]),
            "sth_w": pchip_slopes(g_ax, curves["sth_w"]),
            "sfl_w": pchip_slopes(g_ax, curves["sfl_w"]),
        }
        prepared = {
            "g_ax": g_ax,
            "curves": curves,
            "id_w_vec": id_w_vec,
            "log_id_vec": log_id_vec,
            "log_gm_vec": log_gm_vec,
            "log_gds_vec": log_gds_vec,
            "gmid_min": min(gmid_branch),
            "gmid_max": max(gmid_branch),
            "x_gmid_inc": x_gmid_inc,
            "y_gmid_vgs": y_gmid_vgs,
            "m_gmid_vgs": m_gmid_vgs,
            "x_logid_inc": x_logid_inc,
            "y_logid_vgs": y_logid_vgs,
            "slopes": slopes,
        }
        if len(self._slice_cache) > 128:
            self._slice_cache.clear()
        self._slice_cache[ckey] = prepared
        return prepared

    def query(
        self,
        dev="nmos",
        l_m=180e-9,
        gm_id=None,
        jd=None,
        vgs=None,
        vds=0.6,
        vsb=0.0,
        method="pchip",
        allow_extrapolate=False,
        allow_soa_violation=True,
    ):
        t0 = TIMER()
        if method not in ("pchip", "linear"):
            raise LutError("Unsupported interpolation method '%s' (choose 'pchip' or 'linear')" % method)

        dev_key, dev_entry = self.resolve_device(dev)
        vds_mag = abs(_require_finite(vds, "vds"))
        vsb_mag = abs(_require_finite(vsb, "vsb"))
        l_val = _require_finite(l_m, "l_m")

        prep = self._get_prepared_slice(dev_key, dev_entry, l_val, vds_mag, vsb_mag, allow_extrapolate)
        g_ax = prep["g_ax"]
        curves = prep["curves"]
        id_w_vec = prep["id_w_vec"]
        gmid_min = prep["gmid_min"]
        gmid_max = prep["gmid_max"]
        slopes = prep["slopes"]

        requested_gmid = None
        if gm_id is not None:
            requested_gmid = _require_finite(gm_id, "gm_id")
            target_gmid = requested_gmid
            if target_gmid < gmid_min - 1e-6 or target_gmid > gmid_max + 1e-6:
                if not allow_extrapolate:
                    raise LutBoundsError(
                        "Requested gm/ID=%.3f V^-1 outside achievable range [%.2f, %.2f] V^-1 "
                        "for %s at L=%.3gnm, |VDS|=%.3fV, |VSB|=%.3fV."
                        % (target_gmid, gmid_min, gmid_max, dev_key, l_val * 1e9, vds_mag, vsb_mag)
                    )
                target_gmid = min(max(target_gmid, gmid_min), gmid_max)
            vgs_q = interp1d_eval(
                prep["x_gmid_inc"], prep["y_gmid_vgs"], target_gmid,
                method=method, precomputed_slopes=prep["m_gmid_vgs"]
            )
        elif jd is not None:
            target_jd = _require_finite(jd, "jd")
            if target_jd <= 0.0:
                raise LutError("Current density JD must be positive (A/m).")
            jd_min = min(id_w_vec)
            jd_max = max(id_w_vec)
            if (target_jd < jd_min or target_jd > jd_max) and not allow_extrapolate:
                raise LutBoundsError(
                    "Requested JD=%.3e A/m outside range [%.3e, %.3e] A/m."
                    % (target_jd, jd_min, jd_max)
                )
            x_inc = prep["x_logid_inc"]
            y_vgs = prep["y_logid_vgs"]
            target_log_jd = math.log(min(max(target_jd, jd_min), jd_max))
            vgs_q = interp1d_eval(x_inc, y_vgs, target_log_jd, method=method)
            if method == "pchip" and len(x_inc) >= 2 and x_inc[0] < target_log_jd < x_inc[-1]:
                k_b = bisect.bisect_right(x_inc, target_log_jd) - 1
                if k_b < 0:
                    k_b = 0
                elif k_b >= len(x_inc) - 1:
                    k_b = len(x_inc) - 2
                v_lo = y_vgs[k_b]
                v_hi = y_vgs[k_b + 1]
                f_lo = (
                    interp1d_eval(g_ax, prep["log_id_vec"], v_lo, method=method, precomputed_slopes=slopes["log_id"])
                    - target_log_jd
                )
                f_hi = (
                    interp1d_eval(g_ax, prep["log_id_vec"], v_hi, method=method, precomputed_slopes=slopes["log_id"])
                    - target_log_jd
                )
                if f_lo <= 0.0 <= f_hi and v_hi > v_lo:
                    v_cur = min(max(vgs_q, v_lo), v_hi)
                    last_side = 0
                    for _ in range(24):
                        f_cur = (
                            interp1d_eval(
                                g_ax, prep["log_id_vec"], v_cur,
                                method=method, precomputed_slopes=slopes["log_id"]
                            )
                            - target_log_jd
                        )
                        if abs(f_cur) < 1e-14 or (v_hi - v_lo) < 1e-15:
                            break
                        if f_cur < 0.0:
                            v_lo = v_cur
                            f_lo = f_cur
                            if last_side == -1:
                                f_hi *= 0.5
                            last_side = -1
                        else:
                            v_hi = v_cur
                            f_hi = f_cur
                            if last_side == 1:
                                f_lo *= 0.5
                            last_side = 1
                        denom_f = f_hi - f_lo
                        span_v = v_hi - v_lo
                        if abs(denom_f) > 1e-18:
                            v_sec = v_lo - f_lo * span_v / denom_f
                            if v_lo + 1e-6 * span_v < v_sec < v_hi - 1e-6 * span_v:
                                v_cur = v_sec
                            else:
                                v_cur = 0.5 * (v_lo + v_hi)
                        else:
                            v_cur = 0.5 * (v_lo + v_hi)
                    vgs_q = v_cur
        elif vgs is not None:
            vgs_q = abs(_require_finite(vgs, "vgs"))
            if (vgs_q < g_ax[0] - 1e-9 or vgs_q > g_ax[-1] + 1e-9) and not allow_extrapolate:
                raise LutBoundsError(
                    "Requested |VGS|=%.3fV outside LUT range [%.3f, %.3f]V."
                    % (vgs_q, g_ax[0], g_ax[-1])
                )
        else:
            raise LutError("Specify one of --gm-id, --jd, or --vgs for query.")

        soa_ok, soa_violations, vgb_mag, vdb_mag = self._check_soa(
            dev_key, vgs_q, vds_mag, vsb_mag, allow_soa_violation=allow_soa_violation
        )

        jd_q = math.exp(interp1d_eval(g_ax, prep["log_id_vec"], vgs_q, method=method, precomputed_slopes=slopes["log_id"]))
        gm_w_q = math.exp(interp1d_eval(g_ax, prep["log_gm_vec"], vgs_q, method=method, precomputed_slopes=slopes["log_gm"]))
        gds_w_q = math.exp(interp1d_eval(g_ax, prep["log_gds_vec"], vgs_q, method=method, precomputed_slopes=slopes["log_gds"]))
        gmb_w_q = max(0.0, interp1d_eval(g_ax, curves["gmb_w"], vgs_q, method=method, precomputed_slopes=slopes["gmb_w"]))
        vth_q = interp1d_eval(g_ax, curves["vth"], vgs_q, method=method, precomputed_slopes=slopes["vth"])
        vdsat_q = max(0.02, interp1d_eval(g_ax, curves["vdsat"], vgs_q, method=method, precomputed_slopes=slopes["vdsat"]))
        cgg_w_q = max(1e-18, interp1d_eval(g_ax, curves["cgg_w"], vgs_q, method=method, precomputed_slopes=slopes["cgg_w"]))
        cgs_w_q = max(0.0, interp1d_eval(g_ax, curves["cgs_w"], vgs_q, method=method, precomputed_slopes=slopes["cgs_w"]))
        cgd_w_q = max(0.0, interp1d_eval(g_ax, curves["cgd_w"], vgs_q, method=method, precomputed_slopes=slopes["cgd_w"]))
        cdd_w_q = max(0.0, interp1d_eval(g_ax, curves["cdd_w"], vgs_q, method=method, precomputed_slopes=slopes["cdd_w"]))
        sth_w_q = max(0.0, interp1d_eval(g_ax, curves["sth_w"], vgs_q, method=method, precomputed_slopes=slopes["sth_w"]))
        sfl_w_q = max(0.0, interp1d_eval(g_ax, curves["sfl_w"], vgs_q, method=method, precomputed_slopes=slopes["sfl_w"]))

        gmid_realized = gm_w_q / jd_q
        gm_gds_q = gm_w_q / gds_w_q
        av0_db = 20.0 * math.log10(max(gm_gds_q, 1e-12))
        ft_hz = gm_w_q / (2.0 * math.pi * cgg_w_q)
        k_boltz = 1.3806488e-23
        t_kelvin = 273.15 + float(self.provenance.get("temp_c", 27.0))
        gamma_th = sth_w_q / (4.0 * k_boltz * t_kelvin * gm_w_q) if sth_w_q > 0.0 else None
        fco_hz = (sfl_w_q / sth_w_q) if (sth_w_q > 0.0 and sfl_w_q > 0.0) else None
        sat_margin = vds_mag - vdsat_q
        pol = int(dev_entry.get("polarity", 1))
        elapsed_ms = (TIMER() - t0) * 1000.0

        out = {
            "ok": True,
            "command": "query",
            "device": dev_key,
            "model_name": dev_entry.get("model_name"),
            "polarity": pol,
            "pdk": self.provenance.get("pdk"),
            "corner": self.provenance.get("corner"),
            "source_mode": self.provenance.get("source_mode"),
            "inputs": {
                "l_m": l_val,
                "gm_id_v_inv": requested_gmid if requested_gmid is not None else gmid_realized,
                "vds_v": vds_mag,
                "vsb_v": vsb_mag,
                "method": method,
            },
            "gm_id": round(gmid_realized, 6),
            "jd_a_per_m": jd_q,
            "jd_ua_per_um": jd_q,
            "gm_s_per_m": gm_w_q,
            "gds_s_per_m": gds_w_q,
            "gm_gds": gm_gds_q,
            "intrinsic_gain_db": av0_db,
            "ft_hz": ft_hz,
            "ft_ghz": ft_hz * 1e-9,
            "vgs": vgs_q,
            "signed_vgs": pol * vgs_q,
            "vgb": vgb_mag,
            "vdb": vdb_mag,
            "vdsat": vdsat_q,
            "vth": vth_q,
            "vov": vgs_q - vth_q,
            "sat_margin_v": sat_margin,
            "in_saturation": bool(sat_margin >= 0.0),
            "soa_ok": bool(soa_ok),
            "soa_violations": soa_violations,
            "cgg_f_per_m": cgg_w_q,
            "cgs_f_per_m": cgs_w_q,
            "cgd_f_per_m": cgd_w_q,
            "cdd_f_per_m": cdd_w_q,
            "cgs_cgg": cgs_w_q / cgg_w_q,
            "cgd_cgg": cgd_w_q / cgg_w_q,
            "cdd_cgg": cdd_w_q / cgg_w_q,
            "gmb_gm": gmb_w_q / gm_w_q,
            "sth_a2_per_hz_m": sth_w_q,
            "sfl_a2_per_hz_m": sfl_w_q,
            "gamma_thermal": gamma_th,
            "fco_flicker_hz": fco_hz,
            "achievable_gm_id_range": [round(gmid_min, 3), round(gmid_max, 3)],
            "elapsed_ms": round(elapsed_ms, 4),
        }
        if requested_gmid is not None:
            out["gm_id_target"] = round(requested_gmid, 6)
            out["gm_id_interp_error"] = round(gmid_realized - requested_gmid, 6)
        return out

    def size(
        self,
        dev="nmos",
        gm=None,
        id_a=None,
        gm_id=15.0,
        l_m=180e-9,
        vds=0.6,
        vsb=0.0,
        w_finger_max=5.0e-6,
        w_finger_min=240e-9,
        grid=5.0e-9,
        even_nf=True,
        vds_margin=0.05,
        method="pchip",
        allow_soa_violation=True,
    ):
        t0 = TIMER()
        if (gm is None and id_a is None) or (gm is not None and id_a is not None):
            raise LutError("Provide exactly one of --gm (Siemens) or --id (Amps) for sizing.")

        l_in = _require_finite(l_m, "l_m")
        grid_f = _require_finite(grid, "grid")
        if grid_f <= 0.0:
            raise LutError("Manufacturing grid must be strictly positive (got %r)." % (grid,))
        vds_in = _require_finite(vds, "vds")
        vsb_in = _require_finite(vsb, "vsb")
        vds_margin_f = _require_finite(vds_margin, "vds_margin")
        wf_min_f = _require_finite(w_finger_min, "w_finger_min")
        wf_max_f = _require_finite(w_finger_max, "w_finger_max")
        l_snapped = _snap_grid(l_in, grid_f)
        gmid_val = _require_finite(gm_id, "gm_id")
        q = self.query(
            dev=dev,
            l_m=l_snapped,
            gm_id=gmid_val,
            vds=vds_in,
            vsb=vsb_in,
            method=method,
            allow_soa_violation=True,
        )

        if gm is not None:
            gm_target = _require_finite(gm, "gm")
            if gm_target <= 0.0:
                raise LutError("Target gm must be strictly positive (Siemens).")
            id_req = gm_target / gmid_val
        else:
            id_req = _require_finite(id_a, "id_a")
            if id_req <= 0.0:
                raise LutError("Target drain current ID must be strictly positive (Amps).")
            gm_target = id_req * gmid_val

        jd_val = q["jd_a_per_m"]
        w_ideal = id_req / jd_val

        g = max(grid_f, 1e-12)
        wf_min_grid = math.ceil((wf_min_f - 1e-15) / g) * g
        wf_max_grid = math.floor((wf_max_f + 1e-15) / g) * g
        if wf_max_grid < wf_min_grid - 1e-15:
            raise LutError(
                "No manufacturing grid (%.3gnm) point exists inside [w_finger_min=%.3gnm, w_finger_max=%.3gnm]."
                % (g * 1e9, wf_min_f * 1e9, wf_max_f * 1e9)
            )

        nf_raw = int(math.ceil(w_ideal / max(wf_max_grid, 1e-12)))
        if even_nf:
            nf = max(2, nf_raw)
            if nf % 2 != 0:
                nf += 1
        else:
            nf = max(1, nf_raw)

        warnings = []
        wf_raw = w_ideal / float(nf)
        wf_snapped = _snap_grid(wf_raw, g)
        if wf_snapped > wf_max_grid + 1e-15:
            nf += 2 if even_nf else 1
            wf_raw = w_ideal / float(nf)
            wf_snapped = _snap_grid(wf_raw, g)
            if wf_snapped > wf_max_grid + 1e-15:
                wf_snapped = wf_max_grid
                warnings.append(
                    "Finger width %.3gnm exceeded grid-aligned w_finger_max %.3gnm (nf=%d); clamped to %.3gnm."
                    % (wf_raw * 1e9, wf_max_grid * 1e9, nf, wf_snapped * 1e9)
                )
        if wf_snapped < wf_min_grid - 1e-15:
            wf_snapped = wf_min_grid
            warnings.append(
                "Ideal finger width %.3gnm < w_finger_min %.3gnm (nf=%d); clamped on grid to %.3gnm."
                % (wf_raw * 1e9, wf_min_f * 1e9, nf, wf_snapped * 1e9)
            )

        w_total = nf * wf_snapped
        lut_clamped = False
        if abs(w_total - w_ideal) > 1e-18:
            jd_requested = id_req / max(w_total, 1e-18)
            q_real = self.query(
                dev=dev,
                l_m=l_snapped,
                jd=jd_requested,
                vds=vds,
                vsb=vsb,
                method=method,
                allow_extrapolate=True,
                allow_soa_violation=allow_soa_violation,
            )
            if abs(q_real["jd_a_per_m"] - jd_requested) / max(jd_requested, 1e-30) > 1e-2:
                lut_clamped = True
                warnings.append(
                    "Requested JD=%.3e A/m exceeds LUT JD domain; operating point clamped at LUT boundary (JD_lut=%.3e A/m)."
                    % (jd_requested, q_real["jd_a_per_m"])
                )
        else:
            jd_requested = jd_val
            q_real = q
            if (not q_real["soa_ok"]) and (not allow_soa_violation):
                raise LutBoundsError(
                    "SOA violation for %s: %s" % (q_real["device"], "; ".join(q_real["soa_violations"]))
                )

        # Compute ALL realized small-signal & bias quantities from the SINGLE actual LUT operating point (vgs, w_total)
        jd_actual = q_real["jd_a_per_m"]
        id_realized = w_total * jd_actual
        gm_realized = w_total * q_real["gm_s_per_m"]
        gds_s = gm_realized / max(q_real["gm_gds"], 1e-18)
        ro_ohm = 1.0 / max(gds_s, 1e-18)

        cgg_f = w_total * q_real["cgg_f_per_m"]
        cgs_f = w_total * q_real["cgs_f_per_m"]
        cgd_f = w_total * q_real["cgd_f_per_m"]
        cdd_f = w_total * q_real["cdd_f_per_m"]
        vds_min = q_real["vdsat"] + vds_margin_f
        if abs(vds_in) < vds_min:
            warnings.append(
                "Applied |VDS|=%.3fV is below vds_min=%.3fV (vdsat=%.3fV + margin=%.3fV)!"
                % (abs(vds_in), vds_min, q_real["vdsat"], vds_margin_f)
            )
        for sv in q_real["soa_violations"]:
            warnings.append("SOA violation: %s" % sv)

        is_gpdk090 = str(q_real.get("model_name", "")).startswith("gpdk090_")
        w_total_str = _format_spectre_dim(w_total)
        w_finger_str = _format_spectre_dim(wf_snapped)
        l_str = _format_spectre_dim(l_snapped)
        elapsed_ms = (TIMER() - t0) * 1000.0
        return {
            "ok": (not lut_clamped),
            "lut_clamped": lut_clamped,
            "command": "size",
            "device": q_real["device"],
            "model_name": q_real["model_name"],
            "pdk": q_real["pdk"],
            "corner": q_real["corner"],
            "gm_target_s": gm_target,
            "gm_realized_s": gm_realized,
            "gm_id": q_real["gm_id"],
            "gm_id_target": round(gmid_val, 6),
            "id_requested_a": id_req,
            "id_realized_a": id_realized,
            "id_a": id_realized,
            "l_m": l_snapped,
            "w_ideal_m": w_ideal,
            "nf": nf,
            "w_finger_m": wf_snapped,
            "w_total_m": w_total,
            "jd_a_per_m": jd_actual,
            "jd_requested_a_per_m": jd_requested,
            "jd_ideal_a_per_m": jd_val,
            "vgs": q_real["vgs"],
            "signed_vgs": q_real["signed_vgs"],
            "vgb": q_real["vgb"],
            "vdb": q_real["vdb"],
            "vth": q_real["vth"],
            "vdsat": q_real["vdsat"],
            "vds_min": vds_min,
            "soa_ok": q_real["soa_ok"],
            "soa_violations": list(q_real["soa_violations"]),
            "ro_ohm": ro_ohm,
            "gds_s": gds_s,
            "gm_gds": q_real["gm_gds"],
            "intrinsic_gain_db": q_real["intrinsic_gain_db"],
            "ft_hz": q_real["ft_hz"],
            "cgg_f": cgg_f,
            "cgs_f": cgs_f,
            "cgd_f": cgd_f,
            "cdd_f": cdd_f,
            "spectre_params": {
                "model": q_real["model_name"],
                "w_total": w_total_str,
                "w_finger": w_finger_str,
                "l": l_str,
                "nf": nf,
                "m": nf if is_gpdk090 else 1,
                "simM": nf if is_gpdk090 else 1,
                "netlist_hint": (
                    "w=%s l=%s m=%d simM=%d" % (w_finger_str, l_str, nf, nf)
                    if is_gpdk090
                    else "w=%s l=%s nf=%d m=1" % (w_total_str, l_str, nf)
                ),
            },
            "warnings": warnings,
            "elapsed_ms": round(elapsed_ms, 4),
        }

    def tradeoff(
        self,
        dev="nmos",
        l_list=None,
        gm_id_min=8.0,
        gm_id_max=22.0,
        gm_id_step=2.0,
        vds=0.6,
        vsb=0.0,
        method="pchip",
        allow_soa_violation=True,
    ):
        t0 = TIMER()
        dev_key, dev_entry = self.resolve_device(dev)
        vds_f = _require_finite(vds, "vds")
        vsb_f = _require_finite(vsb, "vsb")
        gmin_f = _require_finite(gm_id_min, "gm_id_min")
        gmax_f = _require_finite(gm_id_max, "gm_id_max")
        step_val = _require_finite(gm_id_step, "gm_id_step")
        if l_list is not None:
            lengths = sorted([_require_finite(lv, "l_list") for lv in l_list])
        else:
            lengths = list(dev_entry["L"][:4])

        if step_val <= 0.0:
            raise LutError("gm_id_step must be strictly positive (got %s)." % str(gm_id_step))
        if gmax_f < gmin_f:
            raise LutError("gm_id_max (%.4g) must be >= gm_id_min (%.4g)." % (gmax_f, gmin_f))

        gmid_points = []
        cur = gmin_f
        while cur <= gmax_f + 1e-9:
            gmid_points.append(round(cur, 4))
            cur += step_val

        rows = []
        for l_m in lengths:
            for gmid_val in gmid_points:
                try:
                    q = self.query(
                        dev=dev_key, l_m=l_m, gm_id=gmid_val,
                        vds=vds_f, vsb=vsb_f, method=method, allow_extrapolate=False,
                        allow_soa_violation=True,
                    )
                except LutBoundsError:
                    continue
                fom_rf = q["gm_id"] * q["ft_ghz"]
                rows.append({
                    "l_m": l_m,
                    "l_nm": round(l_m * 1e9, 2),
                    "gm_id_target": gmid_val,
                    "gm_id": q["gm_id"],
                    "gm_gds": round(q["gm_gds"], 3),
                    "intrinsic_gain_db": round(q["intrinsic_gain_db"], 2),
                    "ft_hz": q["ft_hz"],
                    "ft_ghz": round(q["ft_ghz"], 3),
                    "jd_a_per_m": q["jd_a_per_m"],
                    "jd_ua_per_um": round(q["jd_ua_per_um"], 4),
                    "vdsat": round(q["vdsat"], 4),
                    "vgs": round(q["vgs"], 4),
                    "soa_ok": q["soa_ok"],
                    "fom_gm_id_ft_ghz": round(fom_rf, 2),
                })

        if not rows:
            raise LutError("No valid (gm/ID, L) points inside LUT domain for tradeoff table.")

        # Mark 2D Pareto frontier for maximizing (gm_gds, ft_hz) strictly over SOA-safe rows only
        safe_rows = [r for r in rows if r["soa_ok"]]
        for r in rows:
            if not r["soa_ok"]:
                r["pareto_gain_speed"] = False
                continue
            dominated = False
            for other in safe_rows:
                if (
                    other["gm_gds"] >= r["gm_gds"]
                    and other["ft_hz"] >= r["ft_hz"]
                    and (other["gm_gds"] > r["gm_gds"] or other["ft_hz"] > r["ft_hz"])
                ):
                    dominated = True
                    break
            r["pareto_gain_speed"] = not dominated

        all_soa_failed = (len(safe_rows) == 0)
        soa_violation_count = len(rows) - len(safe_rows)
        pareto_safe_count = sum([1 for r in safe_rows if r.get("pareto_gain_speed")])
        strict_soa_failed = (not allow_soa_violation) and (soa_violation_count > 0 or pareto_safe_count == 0)

        if all_soa_failed:
            role_recs = {
                "input_diff_pair_low_noise_offset": {
                    "target_regime": "moderate-to-weak inversion (gm/ID 16..20 V^-1)",
                    "recommended_point": None,
                    "reason": "all_points_violate_soa",
                },
                "current_mirror_high_rout_matching": {
                    "target_regime": "strong inversion + longer L (gm/ID 7..10 V^-1)",
                    "recommended_point": None,
                    "reason": "all_points_violate_soa",
                },
                "high_speed_gain_or_cascode": {
                    "target_regime": "peak gm/ID * fT product (gm/ID 11..15 V^-1)",
                    "recommended_point": None,
                    "reason": "all_points_violate_soa",
                },
            }
        else:
            diff_cands = [r for r in safe_rows if 15.0 <= r["gm_id"] <= 20.5] or safe_rows
            best_diff = max(diff_cands, key=lambda r: r["gm_id"] * math.log(max(r["gm_gds"], 2.0)) * math.sqrt(r["ft_ghz"]))

            mirror_cands = [r for r in safe_rows if r["gm_id"] <= 11.0] or safe_rows
            best_mirror = max(mirror_cands, key=lambda r: r["gm_gds"] / max(r["gm_id"], 1.0))

            speed_cands = [r for r in safe_rows if 10.0 <= r["gm_id"] <= 16.0] or safe_rows
            best_speed = max(speed_cands, key=lambda r: r["fom_gm_id_ft_ghz"])
            role_recs = {
                "input_diff_pair_low_noise_offset": {
                    "target_regime": "moderate-to-weak inversion (gm/ID 16..20 V^-1)",
                    "recommended_point": best_diff,
                },
                "current_mirror_high_rout_matching": {
                    "target_regime": "strong inversion + longer L (gm/ID 7..10 V^-1)",
                    "recommended_point": best_mirror,
                },
                "high_speed_gain_or_cascode": {
                    "target_regime": "peak gm/ID * fT product (gm/ID 11..15 V^-1)",
                    "recommended_point": best_speed,
                },
            }

        elapsed_ms = (TIMER() - t0) * 1000.0
        ok_flag = (not all_soa_failed) and (pareto_safe_count > 0) and (not strict_soa_failed)
        soa_ok_flag = (not all_soa_failed) and (not strict_soa_failed)
        return {
            "ok": ok_flag,
            "soa_ok": soa_ok_flag,
            "command": "tradeoff",
            "device": dev_key,
            "model_name": dev_entry.get("model_name"),
            "pdk": self.provenance.get("pdk"),
            "corner": self.provenance.get("corner"),
            "vds_v": abs(vds_f),
            "vsb_v": abs(vsb_f),
            "count": len(rows),
            "soa_safe_count": len(safe_rows),
            "soa_violation_count": soa_violation_count,
            "pareto_safe_count": pareto_safe_count,
            "rows": rows,
            "role_recommendations": role_recs,
            "elapsed_ms": round(elapsed_ms, 4),
        }

    def info(self):
        devs = {}
        for k, d in self.devices.items():
            devs[k] = {
                "model_name": d.get("model_name"),
                "polarity": d.get("polarity"),
                "shape": d.get("shape"),
                "L_range_m": [min(d["L"]), max(d["L"])],
                "VGS_range_v": [min(d["VGS"]), max(d["VGS"])],
                "VDS_range_v": [min(d["VDS"]), max(d["VDS"])],
                "VSB_range_v": [min(d["VSB"]), max(d["VSB"])],
            }
        return {
            "ok": True,
            "command": "info",
            "release": RELEASE,
            "lut_path": self.source_path,
            "provenance": self.provenance,
            "devices": devs,
        }


def load_lut(path):
    if not path or not os.path.isfile(path):
        raise LutError("gm/ID LUT file not found: %s" % str(path))
    if path.endswith(".gz"):
        gz = gzip.open(path, "rb")
        try:
            raw = gz.read()
        finally:
            gz.close()
    else:
        f = open(path, "rb")
        try:
            raw = f.read()
        finally:
            f.close()
    data = json.loads(raw.decode("utf-8"))
    return GmidLut(data, source_path=os.path.realpath(path))


def _parse_csv_floats(text):
    vals = []
    for tok in text.split(","):
        tok = tok.strip()
        if tok:
            vals.append(_require_finite(tok, "csv_float"))
    if not vals:
        raise LutError("Expected comma-separated numbers, got: %s" % text)
    return vals


def run_self_test():
    tmp_dir = tempfile.mkdtemp(prefix="skill_analog_gmid_lut_")
    try:
        lut_path = os.path.join(tmp_dir, "demo_gpdk090.lut.json.gz")
        gpdk_techsweep.generate_demo_lut(lut_path, pdk="gpdk090", corner="NN")
        lut = load_lut(lut_path)

        # 1. Warm + timed query benchmark (< 5 ms requirement!)
        lut.query(dev="nmos", l_m=180e-9, gm_id=15.0, vds=0.6, vsb=0.0)
        q_n = lut.query(dev="nmos", l_m=180e-9, gm_id=15.0, vds=0.6, vsb=0.0)
        q_p = lut.query(dev="pmos", l_m=240e-9, gm_id=12.0, vds=0.6, vsb=0.1)
        s_n = lut.size(dev="nmos", gm=1.0e-3, gm_id=15.0, l_m=180e-9, vds=0.6, w_finger_max=5.0e-6)
        tr = lut.tradeoff(dev="nmos", l_list=[90e-9, 180e-9, 360e-9], gm_id_min=8.0, gm_id_max=22.0, gm_id_step=2.0)

        if s_n["nf"] < 2 or (s_n["nf"] % 2) != 0:
            raise AssertionError("Expected even nf >= 2 for matched layout, got %d" % s_n["nf"])
        if abs(s_n["id_a"] - (1.0e-3 / 15.0)) > 1e-10:
            raise AssertionError("Inaccurate ID = gm / (gm/ID)")

        # 2. Verify true realized gm_w/jd reporting & gm_id_interp_error in query(--gm-id)
        q_rt = lut.query(dev="nmos", l_m=180e-9, vgs=q_n["vgs"], vds=0.6, vsb=0.0)
        if q_n["gm_id"] != q_rt["gm_id"]:
            raise AssertionError(
                "query(gm_id) must report exact realized gm_w/jd at vgs_q (%s vs %s)"
                % (q_n["gm_id"], q_rt["gm_id"])
            )
        if q_n.get("gm_id_target") != 15.0 or "gm_id_interp_error" not in q_n:
            raise AssertionError("Missing gm_id_target or gm_id_interp_error in query(gm_id) output")
        if abs((q_n["gm_id_target"] + q_n["gm_id_interp_error"]) - q_n["gm_id"]) > 2e-6:
            raise AssertionError("gm_id_interp_error inconsistent with gm_id - gm_id_target")
        if abs(q_rt["gm_id"] - 15.0) > 0.05:
            raise AssertionError("PCHIP inverse VGS round-trip error too large: %.4f vs 15.0" % q_rt["gm_id"])

        # Also check linear method where inverse error is visibly non-zero
        q_lin = lut.query(dev="nmos", l_m=180e-9, gm_id=14.37, vds=0.6, vsb=0.0, method="linear")
        true_ratio = round(q_lin["gm_s_per_m"] / q_lin["jd_a_per_m"], 6)
        if q_lin["gm_id"] != true_ratio:
            raise AssertionError("Linear query gm_id=%s != round(gm_w/jd)=%s" % (q_lin["gm_id"], true_ratio))

        # 3. Verify clamped width (w_total != w_ideal) full OP consistency in size()!
        s_clamp = lut.size(
            dev="nmos",
            id_a=0.5e-6,
            gm_id=11.0,
            l_m=180e-9,
            vds=0.6,
            vsb=0.0,
            w_finger_min=500e-9,
        )
        if not (s_clamp["w_total_m"] > s_clamp["w_ideal_m"] * 3.0):
            raise AssertionError("Expected strong minimum-width clamping in s_clamp test")
        exp_jd_real = 0.5e-6 / s_clamp["w_total_m"]
        q_exp_real = lut.query(
            dev="nmos", l_m=180e-9, jd=exp_jd_real, vds=0.6, vsb=0.0, allow_extrapolate=True
        )
        if abs(s_clamp["jd_requested_a_per_m"] - exp_jd_real) > 1e-12:
            raise AssertionError("s_clamp jd_requested_a_per_m != id_req / w_total")
        if abs(s_clamp["jd_a_per_m"] - q_exp_real["jd_a_per_m"]) > 1e-12:
            raise AssertionError("s_clamp jd_a_per_m != q_real['jd_a_per_m']")
        if abs(s_clamp["jd_ideal_a_per_m"] - (0.5e-6 / s_clamp["w_ideal_m"])) > 1e-9:
            raise AssertionError("s_clamp jd_ideal_a_per_m mismatch")
        if s_clamp["gm_id_target"] != 11.0 or s_clamp["gm_id"] != q_exp_real["gm_id"]:
            raise AssertionError("s_clamp gm_id must equal realized q_real['gm_id']")
        for op_key in ("vgs", "signed_vgs", "vth", "vdsat", "gm_gds", "intrinsic_gain_db", "ft_hz"):
            if abs(s_clamp[op_key] - q_exp_real[op_key]) > 1e-12:
                raise AssertionError("s_clamp[%s] inconsistent with q_real[%s]" % (op_key, op_key))
        for cap_k, per_m_k in (
            ("cgg_f", "cgg_f_per_m"),
            ("cgs_f", "cgs_f_per_m"),
            ("cgd_f", "cgd_f_per_m"),
            ("cdd_f", "cdd_f_per_m"),
        ):
            if abs(s_clamp[cap_k] - s_clamp["w_total_m"] * q_exp_real[per_m_k]) > 1e-22:
                raise AssertionError("s_clamp[%s] inconsistent with w_total * q_real[%s]" % (cap_k, per_m_k))
        ft_from_caps = s_clamp["gm_realized_s"] / (2.0 * math.pi * s_clamp["cgg_f"])
        if abs(ft_from_caps - s_clamp["ft_hz"]) / s_clamp["ft_hz"] > 1e-8:
            raise AssertionError("s_clamp gm_realized / (2*pi*cgg_f) != ft_hz!")

        # 4. Verify multi-terminal SOA checks on GPDK045 (|VGB|=1.5V > 1.1V and |VDB|=1.5V > 1.1V)
        lut45_path = os.path.join(tmp_dir, "demo_gpdk045.lut.json.gz")
        gpdk_techsweep.generate_demo_lut(lut45_path, pdk="gpdk045", corner="tt")
        lut45 = load_lut(lut45_path)
        q45_ok = lut45.query(dev="nmos", l_m=90e-9, vgs=0.6, vds=0.5, vsb=0.25)
        if not q45_ok["soa_ok"] or q45_ok["soa_violations"]:
            raise AssertionError("Expected safe GPDK045 point to have soa_ok=True")
        q45_bad = lut45.query(dev="nmos", l_m=90e-9, vgs=1.0, vds=0.5, vsb=0.5)
        if q45_bad["soa_ok"] or not any("VGB" in msg for msg in q45_bad["soa_violations"]):
            raise AssertionError("Expected |VGB|=1.5V > 1.1V SOA violation on GPDK045!")
        s45_bad = lut45.size(dev="nmos", gm=0.5e-3, gm_id=10.0, l_m=90e-9, vds=1.0, vsb=0.5)
        if s45_bad["soa_ok"] or not any("SOA violation" in w for w in s45_bad["warnings"]):
            raise AssertionError("Expected size() to flag |VDB|=1.5V > 1.1V SOA violation in warnings!")
        blocked_soa = False
        try:
            lut45.query(dev="nmos", l_m=90e-9, vgs=1.0, vds=0.5, vsb=0.5, allow_soa_violation=False)
        except LutBoundsError:
            blocked_soa = True
        if not blocked_soa:
            raise AssertionError("Expected allow_soa_violation=False to raise LutBoundsError!")

        # 5. Physics monotonicity & speed checks
        q_short = lut.query(dev="nmos", l_m=90e-9, gm_id=14.0, vds=0.6)
        q_long = lut.query(dev="nmos", l_m=500e-9, gm_id=14.0, vds=0.6)
        if not (q_long["gm_gds"] > q_short["gm_gds"] and q_short["ft_hz"] > q_long["ft_hz"]):
            raise AssertionError("Physics trend check failed on gm/gds vs fT across L!")
        if q_n["elapsed_ms"] >= 5.0 or s_n["elapsed_ms"] >= 5.0 or tr["elapsed_ms"] >= 5.0:
            raise AssertionError(
                "Interpolation exceeded 5ms target: query=%.3fms size=%.3fms tradeoff=%.3fms"
                % (q_n["elapsed_ms"], s_n["elapsed_ms"], tr["elapsed_ms"])
            )

        # 7. Verify GPDK090 netlist hint includes m=nf, grid bounds [242nm, 803nm] never violated,
        #    LUT boundary clamp returns ok=False & consistent realized ID/gm, gm_id_step<=0 rejected,
        #    missing SOA metadata fails closed, and all-SOA-fail tradeoff recommends None!
        if s_n["spectre_params"]["m"] != s_n["nf"] or ("m=%d" % s_n["nf"]) not in s_n["spectre_params"]["netlist_hint"]:
            raise AssertionError("GPDK090 spectre_params must set m=nf and include m=<nf> in netlist_hint!")
        s_gmin = lut.size(dev="nmos", id_a=0.1e-6, gm_id=12.0, l_m=180e-9, vds=0.6, w_finger_min=242e-9, w_finger_max=803e-9, grid=5e-9)
        if s_gmin["w_finger_m"] < 242e-9 - 1e-15 or s_gmin["w_finger_m"] > 803e-9 + 1e-15:
            raise AssertionError("Grid-snapped w_finger violated [242nm, 803nm]: %.4gnm" % (s_gmin["w_finger_m"] * 1e9))
        s_gmax = lut.size(dev="nmos", id_a=150e-6, gm_id=15.0, l_m=180e-9, vds=0.6, w_finger_min=242e-9, w_finger_max=803e-9, grid=5e-9)
        if s_gmax["w_finger_m"] < 242e-9 - 1e-15 or s_gmax["w_finger_m"] > 803e-9 + 1e-15:
            raise AssertionError("Grid-snapped w_finger violated [242nm, 803nm]: %.4gnm" % (s_gmax["w_finger_m"] * 1e9))
        s_tiny = lut.size(dev="nmos", id_a=1e-12, gm_id=15.0, l_m=180e-9, vds=0.6)
        if s_tiny["ok"] is not False or not s_tiny["lut_clamped"]:
            raise AssertionError("Clamped 1pA size() must return ok=False and lut_clamped=True!")
        q_chk_tiny = lut.query(dev="nmos", l_m=180e-9, vgs=s_tiny["vgs"], vds=0.6)
        if abs(s_tiny["id_realized_a"] - s_tiny["w_total_m"] * q_chk_tiny["jd_a_per_m"]) / max(s_tiny["id_realized_a"], 1e-30) > 1e-3:
            raise AssertionError("Realized ID in clamped size() inconsistent with returned (vgs, w_total)!")
        bad_step = False
        try:
            lut.tradeoff(dev="nmos", gm_id_min=8.0, gm_id_max=16.0, gm_id_step=0.0, vds=0.6)
        except LutError:
            bad_step = True
        if not bad_step:
            raise AssertionError("tradeoff() must reject gm_id_step <= 0!")
        tr_soa_fail = lut.tradeoff(dev="nmos", gm_id_min=10.0, gm_id_max=18.0, gm_id_step=4.0, vds=1.0, vsb=0.5)
        if tr_soa_fail["ok"] or tr_soa_fail["soa_ok"] or tr_soa_fail["role_recommendations"]["high_speed_gain_or_cascode"]["recommended_point"] is not None:
            raise AssertionError("tradeoff() must not recommend any point when all points violate SOA!")
        no_soa_data = json.loads(json.dumps(lut.data))
        no_soa_data["provenance"].pop("soa_limits", None)
        no_soa_data["provenance"].pop("vdd_max_v", None)
        lut_no_soa = type(lut)(no_soa_data)
        q_no_soa = lut_no_soa.query(dev="nmos", l_m=180e-9, gm_id=15.0, vds=0.6, allow_soa_violation=True)
        if q_no_soa["soa_ok"]:
            raise AssertionError("Missing SOA metadata must not report soa_ok=True!")
        caught_missing_soa = False
        try:
            lut_no_soa.query(dev="nmos", l_m=180e-9, gm_id=15.0, vds=0.6, allow_soa_violation=False)
        except LutBoundsError:
            caught_missing_soa = True
        if not caught_missing_soa:
            raise AssertionError("Strict SOA mode must raise LutBoundsError when SOA metadata is missing!")

        # 8. Verify NaN/Inf rejection in query, size, and tradeoff (#17)
        for bad_val in (float("nan"), float("inf"), float("-inf")):
            for fn_desc, fn_call in (
                ("query_gmid", lambda bv=bad_val: lut.query(dev="nmos", l_m=180e-9, gm_id=bv, vds=0.6)),
                ("query_vds", lambda bv=bad_val: lut.query(dev="nmos", l_m=180e-9, gm_id=15.0, vds=bv)),
                ("size_gm", lambda bv=bad_val: lut.size(dev="nmos", gm=bv, gm_id=15.0, l_m=180e-9, vds=0.6)),
                ("size_gmid", lambda bv=bad_val: lut.size(dev="nmos", gm=1e-3, gm_id=bv, l_m=180e-9, vds=0.6)),
                ("tradeoff_vds", lambda bv=bad_val: lut.tradeoff(dev="nmos", vds=bv)),
            ):
                caught_nf = False
                try:
                    fn_call()
                except LutError:
                    caught_nf = True
                if not caught_nf:
                    raise AssertionError("Failed to reject non-finite %r in %s!" % (bad_val, fn_desc))

        # 9. Verify !soa_ok rows excluded from pareto_gain_speed & tradeoff --strict-soa CLI exit 1 (#17)
        # On GPDK045 (vgb_max=1.1V), vsb=0.50V causes high-VGS (low gm/ID) rows to violate VGB>1.1V while high gm/ID rows pass
        tr45_mix = lut45.tradeoff(
            dev="nmos", l_list=[45e-9, 180e-9], gm_id_min=4.0, gm_id_max=22.0, gm_id_step=2.0,
            vds=0.5, vsb=0.50, allow_soa_violation=True
        )
        unsafe_rows = [r for r in tr45_mix["rows"] if not r["soa_ok"]]
        if not unsafe_rows or tr45_mix["soa_safe_count"] == 0:
            raise AssertionError("Expected mixed SOA-safe and SOA-violating rows in GPDK045 tradeoff test!")
        if any([r.get("pareto_gain_speed") for r in unsafe_rows]):
            raise AssertionError("SOA-violating rows MUST be excluded from pareto_gain_speed!")
        tr45_strict = lut45.tradeoff(
            dev="nmos", l_list=[45e-9, 180e-9], gm_id_min=4.0, gm_id_max=22.0, gm_id_step=2.0,
            vds=0.5, vsb=0.50, allow_soa_violation=False
        )
        if tr45_strict["ok"] is not False or tr45_strict["soa_ok"] is not False:
            raise AssertionError("Strict SOA tradeoff with violating rows must return ok=False and soa_ok=False!")
        import subprocess
        proc_tr = subprocess.Popen(
            [
                sys.executable, "-B", os.path.realpath(__file__), "tradeoff",
                "--lut", lut45_path, "--dev", "nmos", "--l-list", "45e-9,180e-9",
                "--gm-id-range", "4,22", "--gm-id-step", "2", "--vds", "0.5", "--vsb", "0.50", "--strict-soa",
            ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        out_tr, _ = proc_tr.communicate()
        if proc_tr.returncode != 1:
            raise AssertionError("CLI tradeoff --strict-soa must exit 1 on SOA violation, got %d" % proc_tr.returncode)
        proc_nan = subprocess.Popen(
            [
                sys.executable, "-B", os.path.realpath(__file__), "query",
                "--lut", lut_path, "--dev", "nmos", "--l", "180e-9", "--gm-id", "nan", "--vds", "0.6",
            ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        out_nan, _ = proc_nan.communicate()
        if proc_nan.returncode != 1 or json.loads(out_nan.decode("utf-8")).get("ok") is not False:
            raise AssertionError("CLI query --gm-id nan must exit 1 with ok=False!")

        # 10. Verify large-W Spectre formatter (no scientific notation + suffix) & 5nm grid precision (#17)
        if _format_spectre_dim(12.555e-6) != "12.555u":
            raise AssertionError("5nm grid precision lost: got %r" % _format_spectre_dim(12.555e-6))
        if _format_spectre_dim(12.56e-3) != "12.56m":
            raise AssertionError("Large-W formatter failed: got %r" % _format_spectre_dim(12.56e-3))
        s_huge = lut45.size(dev="nmos", id_a=0.5, gm_id=14.0, l_m=90e-9, vds=0.5, w_finger_max=5.0e-6)
        w_tot_s = s_huge["spectre_params"]["w_total"]
        if "e+" in w_tot_s.lower() or "e-" in w_tot_s.lower():
            raise AssertionError("Invalid Spectre scientific+suffix width emitted: %r" % w_tot_s)

        return {
            "ok": True,
            "release": RELEASE,
            "self_test": "PASS",
            "query_elapsed_ms": q_n["elapsed_ms"],
            "size_elapsed_ms": s_n["elapsed_ms"],
            "tradeoff_elapsed_ms": tr["elapsed_ms"],
            "roundtrip_gm_id": q_rt["gm_id"],
            "gm_id_interp_error": q_n["gm_id_interp_error"],
            "clamped_width_consistency_verified": True,
            "multi_terminal_soa_verified": True,
            "nan_inf_rejection_verified": True,
            "soa_pareto_and_strict_cli_verified": True,
            "spectre_dim_formatter_verified": True,
            "sample_nmos_size": {
                "id_ua": round(s_n["id_a"] * 1e6, 3),
                "w_total_um": round(s_n["w_total_m"] * 1e6, 3),
                "nf": s_n["nf"],
                "w_finger_um": round(s_n["w_finger_m"] * 1e6, 3),
                "intrinsic_gain_db": round(s_n["intrinsic_gain_db"], 2),
                "vds_min_v": round(s_n["vds_min"], 4),
            },
            "sample_pmos_vgs": round(q_p["signed_vgs"], 4),
            "tradeoff_points": tr["count"],
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def build_parser():
    usage = (
        "Usage:\n"
        "  python tools/gmid_lut.py query    --lut PATH --dev nmos --l 180e-9 --gm-id 15 --vds 0.6\n"
        "  python tools/gmid_lut.py size     --lut PATH --dev nmos --gm 1e-3 --gm-id 15 --l 180e-9 --vds 0.6\n"
        "  python tools/gmid_lut.py tradeoff --lut PATH --dev nmos --l-list 90e-9,180e-9,360e-9 --gm-id-range 8,22\n"
        "  python tools/gmid_lut.py info     --lut PATH\n"
        "  python tools/gmid_lut.py --generate-demo-lut PATH [--pdk gpdk090|gpdk045] [--corner NN]\n"
        "  python tools/gmid_lut.py --self-test"
    )
    p = optparse.OptionParser(usage=usage)
    p.add_option("--lut", dest="lut_path", default=None, help="Path to .lut.json.gz file")
    p.add_option("--dev", dest="dev", default="nmos", help="Device type: nmos or pmos [default: %default]")
    p.add_option("--l", dest="l_m", type="float", default=180e-9, help="Channel length L in meters [default: %default]")
    p.add_option("--gm-id", dest="gm_id", type="float", default=None, help="Target gm/ID in V^-1")
    p.add_option("--jd", dest="jd", type="float", default=None, help="Target current density ID/W in A/m")
    p.add_option("--vgs", dest="vgs", type="float", default=None, help="Gate-source voltage |VGS| in V")
    p.add_option("--gm", dest="gm", type="float", default=None, help="Target transconductance gm in Siemens (for size)")
    p.add_option("--id", dest="id_a", type="float", default=None, help="Target drain current ID in Amps (for size)")
    p.add_option("--vds", dest="vds", type="float", default=0.6, help="Drain-source voltage |VDS| in V [default: %default]")
    p.add_option("--vsb", dest="vsb", type="float", default=0.0, help="Source-bulk voltage |VSB| in V [default: %default]")
    p.add_option("--w-finger-max", dest="w_finger_max", type="float", default=5.0e-6,
                 help="Maximum finger width in meters [default: %default]")
    p.add_option("--w-finger-min", dest="w_finger_min", type="float", default=240e-9,
                 help="Minimum finger width in meters [default: %default]")
    p.add_option("--grid", dest="grid", type="float", default=5.0e-9,
                 help="PDK manufacturing grid in meters [default: %default]")
    p.add_option("--allow-odd-nf", dest="allow_odd_nf", action="store_true", default=False,
                 help="Allow odd finger count nf (default enforces even nf>=2 for layout matching)")
    p.add_option("--vds-margin", dest="vds_margin", type="float", default=0.05,
                 help="Saturation headroom margin added to Vdsat for vds_min [default: %default]")
    p.add_option("--l-list", dest="l_list", default=None, help="Comma-separated L list in meters (for tradeoff)")
    p.add_option("--gm-id-range", dest="gm_id_range", default="8,22",
                 help="Min,max gm/ID range in V^-1 (for tradeoff) [default: %default]")
    p.add_option("--gm-id-step", dest="gm_id_step", type="float", default=2.0,
                 help="Step size for gm/ID tradeoff table [default: %default]")
    p.add_option("--method", dest="method", default="pchip", help="Interpolation: pchip or linear [default: %default]")
    p.add_option("--allow-extrapolate", dest="allow_extrapolate", action="store_true", default=False,
                 help="Clamp out-of-bounds queries instead of raising LutBoundsError")
    p.add_option("--allow-soa-violation", dest="allow_soa_violation", action="store_true", default=False,
                 help="Allow multi-terminal SOA violations to return with soa_ok=false instead of raising")
    p.add_option("--strict-soa", dest="strict_soa", action="store_true", default=False,
                 help="Raise LutBoundsError when multi-terminal SOA limits (VGB/VDB/VDD) are exceeded")
    p.add_option("--generate-demo-lut", dest="demo_lut_path", default=None, metavar="PATH",
                 help="Generate analytical EKV/BSIM4 demo .lut.json.gz at PATH")
    p.add_option("--pdk", dest="pdk", default="gpdk090", help="PDK for --generate-demo-lut [default: %default]")
    p.add_option("--corner", dest="corner", default=None, help="Corner for --generate-demo-lut")
    p.add_option("--self-test", dest="self_test", action="store_true", default=False,
                 help="Run unit & sub-5ms speed self-test in tempfile.mkdtemp()")
    return p


def main(argv=None):
    parser = build_parser()
    opts, pos = parser.parse_args(sys.argv[1:] if argv is None else argv)

    try:
        if opts.self_test or (pos and pos[0] == "self-test"):
            res = run_self_test()
            print(json.dumps(res, indent=2, sort_keys=True))
            return 0

        if opts.demo_lut_path or (pos and pos[0] == "generate-demo-lut"):
            target = opts.demo_lut_path or opts.lut_path
            if not target and len(pos) >= 2:
                target = pos[1]
            if not target:
                raise LutError("Provide output path via --generate-demo-lut PATH")
            res = gpdk_techsweep.generate_demo_lut(target, pdk=opts.pdk, corner=opts.corner)
            print(json.dumps(res, indent=2, sort_keys=True))
            return 0

        if not pos:
            parser.print_help()
            return 0

        cmd = pos[0].strip().lower()
        if len(pos) > 1:
            raise LutError("Unexpected extra arguments: " + " ".join(pos[1:]))
        if not opts.lut_path:
            raise LutError("Missing required --lut <path.lut.json.gz>")

        eff_allow_soa = False if opts.strict_soa else True
        if opts.allow_soa_violation:
            eff_allow_soa = True

        lut = load_lut(opts.lut_path)
        if cmd == "info":
            res = lut.info()
        elif cmd == "query":
            res = lut.query(
                dev=opts.dev,
                l_m=opts.l_m,
                gm_id=opts.gm_id,
                jd=opts.jd,
                vgs=opts.vgs,
                vds=opts.vds,
                vsb=opts.vsb,
                method=opts.method,
                allow_extrapolate=opts.allow_extrapolate,
                allow_soa_violation=eff_allow_soa,
            )
        elif cmd == "size":
            gm_id_val = opts.gm_id if opts.gm_id is not None else 15.0
            res = lut.size(
                dev=opts.dev,
                gm=opts.gm,
                id_a=opts.id_a,
                gm_id=gm_id_val,
                l_m=opts.l_m,
                vds=opts.vds,
                vsb=opts.vsb,
                w_finger_max=opts.w_finger_max,
                w_finger_min=opts.w_finger_min,
                grid=opts.grid,
                even_nf=(not opts.allow_odd_nf),
                vds_margin=opts.vds_margin,
                method=opts.method,
                allow_soa_violation=eff_allow_soa,
            )
        elif cmd == "tradeoff":
            rng = _parse_csv_floats(opts.gm_id_range)
            if len(rng) != 2:
                raise LutError("--gm-id-range must have exactly 2 numbers: min,max")
            l_vals = _parse_csv_floats(opts.l_list) if opts.l_list else None
            res = lut.tradeoff(
                dev=opts.dev,
                l_list=l_vals,
                gm_id_min=rng[0],
                gm_id_max=rng[1],
                gm_id_step=opts.gm_id_step,
                vds=opts.vds,
                vsb=opts.vsb,
                method=opts.method,
                allow_soa_violation=eff_allow_soa,
            )
        else:
            raise LutError("Unknown command '%s'. Choose from: query, size, tradeoff, info" % cmd)

        print(json.dumps(res, indent=2, sort_keys=True))
        if not res.get("ok", True):
            return 1
        if (cmd in ("query", "size", "tradeoff")) and (res.get("soa_ok") is False) and (not opts.allow_soa_violation):
            return 1
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2, sort_keys=True))
        return 1


if __name__ == "__main__":
    sys.exit(main())
