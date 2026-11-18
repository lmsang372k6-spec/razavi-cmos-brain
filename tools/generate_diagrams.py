#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deterministic, textbook-grade SVG circuit schematic & analytical diagram generator
for Razavi CMOS Knowledge Brain (Design of Analog CMOS Integrated Circuits, 2nd Ed.).

Pure Python 3 standard library only (zero external packages, zero temp files).
Generates all 56 vector SVG diagrams in `kb/diagrams/` + `kb/diagrams/diagrams-manifest.json`
and validates every SVG via xml.etree.ElementTree + strict viewBox & text-collision checks.
"""

import json
import math
import os
import sys
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

# Prevent .pyc generation if imported
sys.dont_write_bytecode = True

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT_DIR = os.path.join(ROOT_DIR, "kb", "diagrams")

# Semantic Academic Color Palette
COL_BG = "#ffffff"
COL_CARD_SUB = "#f8fafc"
COL_BORDER = "#e2e8f0"
COL_GRID = "#cbd5e1"
COL_DARK = "#0f172a"      # Primary schematic wires & devices
COL_SIG = "#2563eb"       # Signal path highlight
COL_BIAS = "#059669"      # Bias / current-mirror / guard path
COL_WARN = "#dc2626"      # Parasitic / RHP zero / trap / latch-up loop
COL_AMBER = "#d97706"     # Feedback / compensation / secondary highlight
COL_PURPLE = "#7c3aed"    # Auxiliary / clock phase highlight
COL_MUTED = "#475569"     # Annotations & equations
COL_SUBTLE = "#94a3b8"    # Guides & dashed boundaries

TONE_STYLES = {
    "neutral": ("#f8fafc", "#cbd5e1", "#0f172a"),
    "sig":     ("#eff6ff", "#93c5fd", "#1d4ed8"),
    "bias":    ("#ecfdf5", "#6ee7b7", "#047857"),
    "warn":    ("#fef2f2", "#fca5a5", "#b91c1c"),
    "amber":   ("#fffbeb", "#fcd34d", "#b45309"),
    "purple":  ("#f5f3ff", "#c4b5fd", "#6d28d9"),
}

FONT_SANS = "Inter, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"


def fmt(v):
    if isinstance(v, float):
        s = f"{v:.2f}".rstrip("0").rstrip(".")
        return "0" if s == "-0" else s
    return str(v)


class SVGDoc:
    """Clean, deterministic schematic & technical plot builder."""

    def __init__(self, filename, title_en, title_vi, chapter, chapters,
                 width=1020, height=580, legend=True):
        self.filename = filename
        self.title_en = title_en
        self.title_vi = title_vi
        self.chapter = chapter
        self.chapters = chapters
        self.width = width
        self.height = height
        self.elements = []
        self._init_chrome(legend=legend)

    def _init_chrome(self, legend=True):
        w, h = self.width, self.height
        # Outer card background
        self.elements.append(
            f'<rect x="2" y="2" width="{w - 4}" height="{h - 4}" rx="10" '
            f'fill="{COL_BG}" stroke="{COL_BORDER}" stroke-width="1.5"/>'
        )
        # Header background strip
        self.elements.append(
            f'<path d="M 12 2 L {w - 12} 2 Q {w - 2} 2 {w - 2} 12 L {w - 2} 58 '
            f'L 2 58 L 2 12 Q 2 2 12 2 Z" fill="{COL_CARD_SUB}"/>'
        )
        self.elements.append(
            f'<line x1="2" y1="58" x2="{w - 2}" y2="58" stroke="{COL_BORDER}" stroke-width="1.2"/>'
        )
        # Chapter badge pill
        badge_w = max(58, len(self.chapter) * 7 + 18)
        self.elements.append(
            f'<rect x="18" y="11" width="{badge_w}" height="22" rx="6" '
            f'fill="#eff6ff" stroke="#bfdbfe" stroke-width="1"/>'
        )
        self.text(18 + badge_w / 2, 26, self.chapter, size=11.5,
                  color="#1d4ed8", anchor="middle", weight="bold")
        # Title EN & Subtitle VI
        self.text(28 + badge_w, 26.5, self.title_en, size=15,
                  color=COL_DARK, anchor="start", weight="bold")
        self.text(20, 48, self.title_vi, size=11.5,
                  color=COL_MUTED, anchor="start")

        if legend:
            lx = w - 310
            # Legend dots + labels on top right (single row at y=25)
            items = [
                (lx, COL_SIG, "Signal"),
                (lx + 82, COL_BIAS, "Bias/Mirror"),
                (lx + 188, COL_WARN, "Parasitic/FB"),
            ]
            for ix, col, lbl in items:
                self.elements.append(
                    f'<line x1="{fmt(ix)}" y1="22" x2="{fmt(ix + 16)}" y2="22" '
                    f'stroke="{col}" stroke-width="2.6" stroke-linecap="round"/>'
                )
                self.text(ix + 21, 26, lbl, size=10.5, color=COL_MUTED, anchor="start")

    # ---------------- Basic Primitives ----------------
    def text(self, x, y, s, size=12, color=COL_DARK, anchor="start",
             weight="normal", italic=False):
        if not s:
            return
        style_parts = [
            f'font-family="{FONT_SANS}"',
            f'font-size="{fmt(size)}"',
            f'fill="{color}"',
            f'text-anchor="{anchor}"',
        ]
        if weight != "normal":
            style_parts.append(f'font-weight="{weight}"')
        if italic:
            style_parts.append('font-style="italic"')
        attrs = " ".join(style_parts)
        self.elements.append(
            f'<text x="{fmt(x)}" y="{fmt(y)}" {attrs}>{escape(str(s))}</text>'
        )

    def line(self, x1, y1, x2, y2, color=COL_DARK, sw=2.0, dash=None,
             marker_end=None, marker_start=None):
        extra = ""
        if dash:
            extra += f' stroke-dasharray="{dash}"'
        if marker_end:
            extra += f' marker-end="url(#{marker_end})"'
        if marker_start:
            extra += f' marker-start="url(#{marker_start})"'
        self.elements.append(
            f'<line x1="{fmt(x1)}" y1="{fmt(y1)}" x2="{fmt(x2)}" y2="{fmt(y2)}" '
            f'stroke="{color}" stroke-width="{fmt(sw)}" stroke-linecap="round"{extra}/>'
        )

    def wire(self, pts, color=COL_DARK, sw=2.0, dash=None, marker_end=None):
        pstr = " ".join(f"{fmt(x)},{fmt(y)}" for x, y in pts)
        extra = ""
        if dash:
            extra += f' stroke-dasharray="{dash}"'
        if marker_end:
            extra += f' marker-end="url(#{marker_end})"'
        self.elements.append(
            f'<polyline points="{pstr}" fill="none" stroke="{color}" '
            f'stroke-width="{fmt(sw)}" stroke-linecap="round" stroke-linejoin="round"{extra}/>'
        )

    def rect(self, x, y, w, h, fill=COL_BG, stroke=COL_BORDER, sw=1.4,
             rx=6, dash=None, opacity=None):
        extra = ""
        if dash:
            extra += f' stroke-dasharray="{dash}"'
        if opacity is not None:
            extra += f' fill-opacity="{fmt(opacity)}"'
        self.elements.append(
            f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}" '
            f'rx="{fmt(rx)}" fill="{fill}" stroke="{stroke}" stroke-width="{fmt(sw)}"{extra}/>'
        )

    def circle(self, cx, cy, r, fill=COL_BG, stroke=COL_DARK, sw=1.8, dash=None):
        extra = f' stroke-dasharray="{dash}"' if dash else ""
        self.elements.append(
            f'<circle cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(r)}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{fmt(sw)}"{extra}/>'
        )

    def poly(self, pts, fill="none", stroke=COL_DARK, sw=1.8, opacity=None):
        pstr = " ".join(f"{fmt(x)},{fmt(y)}" for x, y in pts)
        extra = f' fill-opacity="{fmt(opacity)}"' if opacity is not None else ""
        self.elements.append(
            f'<polygon points="{pstr}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{fmt(sw)}" stroke-linejoin="round"{extra}/>'
        )

    def path(self, d_str, fill="none", stroke=COL_DARK, sw=2.0,
             dash=None, marker_end=None):
        extra = ""
        if dash:
            extra += f' stroke-dasharray="{dash}"'
        if marker_end:
            extra += f' marker-end="url(#{marker_end})"'
        self.elements.append(
            f'<path d="{d_str}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{fmt(sw)}" stroke-linecap="round" stroke-linejoin="round"{extra}/>'
        )

    def dot(self, x, y, color=COL_DARK, r=3.5):
        self.elements.append(
            f'<circle cx="{fmt(x)}" cy="{fmt(y)}" r="{fmt(r)}" fill="{color}"/>'
        )

    def port(self, x, y, label="", side="left", color=COL_DARK, r=3.4, fs=12, bold=True):
        self.circle(x, y, r, fill=COL_BG, stroke=color, sw=1.9)
        if label:
            wt = "bold" if bold else "normal"
            if side == "left":
                self.text(x - 8, y + 4, label, size=fs, color=color, anchor="end", weight=wt)
            elif side == "right":
                self.text(x + 8, y + 4, label, size=fs, color=color, anchor="start", weight=wt)
            elif side == "top":
                self.text(x, y - 8, label, size=fs, color=color, anchor="middle", weight=wt)
            elif side == "bottom":
                self.text(x, y + 16, label, size=fs, color=color, anchor="middle", weight=wt)

    def arrow(self, x1, y1, x2, y2, color=COL_SIG, sw=1.8, dash=None):
        marker_map = {
            COL_DARK: "arr-dark",
            COL_SIG: "arr-sig",
            COL_BIAS: "arr-bias",
            COL_WARN: "arr-warn",
            COL_AMBER: "arr-amber",
            COL_PURPLE: "arr-purple",
            COL_MUTED: "arr-muted",
        }
        mk = marker_map.get(color, "arr-dark")
        self.line(x1, y1, x2, y2, color=color, sw=sw, dash=dash, marker_end=mk)

    # ---------------- Panels & Callouts ----------------
    def panel(self, x, y, w, h, heading="", sub="", stroke=COL_BORDER, fill="#fcfdff"):
        self.rect(x, y, w, h, fill=fill, stroke=stroke, sw=1.3, rx=8)
        if heading:
            self.rect(x, y, w, 28, fill="#f1f5f9", stroke=stroke, sw=1.0, rx=8)
            self.text(x + 12, y + 18.5, heading, size=12, color=COL_DARK, weight="bold")
            if sub:
                self.text(x + w - 12, y + 18.5, sub, size=11, color=COL_MUTED, anchor="end")

    def callout(self, x, y, w, h, title="", lines=(), tone="neutral", fs=11.2):
        bg, bd, hd = TONE_STYLES.get(tone, TONE_STYLES["neutral"])
        self.rect(x, y, w, h, fill=bg, stroke=bd, sw=1.3, rx=7)
        self.line(x + 3, y + 6, x + 3, y + h - 6, color=hd, sw=3.0)
        cy = y + 18
        if title:
            self.text(x + 12, cy, title, size=fs + 0.6, color=hd, weight="bold")
            cy += 17
        for ln in lines:
            self.text(x + 12, cy, ln, size=fs, color=COL_DARK)
            cy += 16

    # ---------------- Power & Ground ----------------
    def vdd(self, x, y, label="VDD", color=COL_DARK):
        """Draws VDD rail bar above (x, y) and connects stub to (x, y)."""
        self.line(x, y, x, y - 9, color=color, sw=2.0)
        self.line(x - 13, y - 9, x + 13, y - 9, color=color, sw=2.4)
        if label:
            self.text(x, y - 14, label, size=11.2, color=color, anchor="middle", weight="bold")

    def gnd(self, x, y, color=COL_DARK):
        """Draws 3-bar GND symbol below (x, y)."""
        self.line(x, y, x, y + 7, color=color, sw=2.0)
        self.line(x - 11, y + 7, x + 11, y + 7, color=color, sw=2.1)
        self.line(x - 7, y + 11.5, x + 7, y + 11.5, color=color, sw=1.9)
        self.line(x - 3, y + 16, x + 3, y + 16, color=color, sw=1.8)

    # ---------------- Analog Devices ----------------
    def _place_dev_labels(self, x, y, side, label, sub, color, dx=10):
        if not label and not sub:
            return
        anchor = "start" if side == "right" else "end"
        lx = x + dx if side == "right" else x - dx
        if label and sub:
            self.text(lx, y - 3, label, size=11.8, color=color, anchor=anchor, weight="bold")
            self.text(lx, y + 12, sub, size=10.5, color=COL_MUTED, anchor=anchor)
        elif label:
            self.text(lx, y + 4, label, size=11.8, color=color, anchor=anchor, weight="bold")
        else:
            self.text(lx, y + 4, sub, size=10.5, color=COL_MUTED, anchor=anchor)

    def nmos(self, x, y, facing="right", color=COL_DARK, label="", sub="",
             label_side=None, show_body=False):
        """
        Vertical NMOS with Drain at (x, y-24), Source at (x, y+24).
        facing='right': Gate on left at (x-30, y), channel on right toward x.
        facing='left':  Gate on right at (x+30, y), channel on left toward x.
        """
        s_dir = 1 if facing == "right" else -1
        ch_x = x - 12 * s_dir
        ox_x = x - 18 * s_dir
        g_x = x - 30 * s_dir

        # Drain lead (top)
        self.wire([(x, y - 24), (x, y - 12), (ch_x, y - 12)], color=color, sw=2.0)
        # Source lead (bottom) with outward NMOS arrow
        self.wire([(ch_x, y + 12), (x, y + 12), (x, y + 24)], color=color, sw=2.0)
        ax = x - 2 * s_dir
        self.poly([
            (ax, y + 12),
            (ax - 6.5 * s_dir, y + 8.5),
            (ax - 6.5 * s_dir, y + 15.5),
        ], fill=color, stroke=color, sw=1.0)
        # Channel & Gate plates
        self.line(ch_x, y - 15, ch_x, y + 15, color=color, sw=2.3)
        self.line(ox_x, y - 12, ox_x, y + 12, color=color, sw=2.0)
        self.line(g_x, y, ox_x, y, color=color, sw=2.0)

        b_pin = (x + 14 * s_dir, y)
        if show_body:
            self.line(ch_x, y, b_pin[0], y, color=COL_MUTED, sw=1.5)

        lside = label_side or ("right" if facing == "right" else "left")
        dx = 8 if lside == ("right" if facing == "right" else "left") else 34
        self._place_dev_labels(x, y, lside, label, sub, color, dx=dx)
        return {"d": (x, y - 24), "s": (x, y + 24), "g": (g_x, y), "b": b_pin}

    def pmos(self, x, y, facing="right", color=COL_DARK, label="", sub="",
             label_side=None, show_body=False):
        """
        Vertical PMOS with Source at (x, y-24), Drain at (x, y+24).
        Includes gate inversion bubble + inward source arrow at top.
        """
        s_dir = 1 if facing == "right" else -1
        ch_x = x - 12 * s_dir
        ox_x = x - 17 * s_dir
        bub_x = x - 20.5 * s_dir
        g_x = x - 30 * s_dir

        # Source lead (top) with inward arrow toward channel
        self.wire([(x, y - 24), (x, y - 12), (ch_x, y - 12)], color=color, sw=2.0)
        ax = ch_x + 2 * s_dir
        self.poly([
            (ax, y - 12),
            (ax + 6.5 * s_dir, y - 15.5),
            (ax + 6.5 * s_dir, y - 8.5),
        ], fill=color, stroke=color, sw=1.0)
        # Drain lead (bottom)
        self.wire([(ch_x, y + 12), (x, y + 12), (x, y + 24)], color=color, sw=2.0)
        # Channel, Gate plate, Bubble & Gate lead
        self.line(ch_x, y - 15, ch_x, y + 15, color=color, sw=2.3)
        self.line(ox_x, y - 12, ox_x, y + 12, color=color, sw=2.0)
        self.circle(bub_x, y, 3.0, fill=COL_BG, stroke=color, sw=1.7)
        self.line(g_x, y, bub_x - 3.0 * s_dir, y, color=color, sw=2.0)

        b_pin = (x + 14 * s_dir, y)
        if show_body:
            self.line(ch_x, y, b_pin[0], y, color=COL_MUTED, sw=1.5)

        lside = label_side or ("right" if facing == "right" else "left")
        dx = 8 if lside == ("right" if facing == "right" else "left") else 34
        self._place_dev_labels(x, y, lside, label, sub, color, dx=dx)
        return {"s": (x, y - 24), "d": (x, y + 24), "g": (g_x, y), "b": b_pin}

    def nmos_h(self, x, y, gate_pos="top", color=COL_DARK, label="", sub=""):
        """Horizontal pass NMOS: pins l=(x-24, y), r=(x+24, y), g=(x, y-+30)."""
        g_dir = -1 if gate_pos == "top" else 1
        ch_y = y + 12 * g_dir
        ox_y = y + 18 * g_dir
        g_y = y + 30 * g_dir
        self.wire([(x - 24, y), (x - 12, y), (x - 12, ch_y)], color=color, sw=2.0)
        self.wire([(x + 12, ch_y), (x + 12, y), (x + 24, y)], color=color, sw=2.0)
        self.line(x - 15, ch_y, x + 15, ch_y, color=color, sw=2.3)
        self.line(x - 12, ox_y, x + 12, ox_y, color=color, sw=2.0)
        self.line(x, g_y, x, ox_y, color=color, sw=2.0)
        # Arrow on right/source terminal pointing toward y
        ay = y + 2 * g_dir
        self.poly([
            (x + 12, ay),
            (x + 8.5, ay + 6 * g_dir),
            (x + 15.5, ay + 6 * g_dir),
        ], fill=color, stroke=color, sw=1.0)
        if label:
            ly = y - 10 if gate_pos == "bottom" else y + 18
            self.text(x, ly, label, size=11.5, color=color, anchor="middle", weight="bold")
        if sub:
            ly = y - 24 if gate_pos == "bottom" else y + 32
            self.text(x, ly, sub, size=10.5, color=COL_MUTED, anchor="middle")
        return {"l": (x - 24, y), "r": (x + 24, y), "g": (x, g_y)}

    def pmos_h(self, x, y, gate_pos="bottom", color=COL_DARK, label="", sub=""):
        """Horizontal pass PMOS with gate bubble: l=(x-24, y), r=(x+24, y), g=(x, y+-30)."""
        g_dir = -1 if gate_pos == "top" else 1
        ch_y = y + 12 * g_dir
        ox_y = y + 17 * g_dir
        bub_y = y + 20.5 * g_dir
        g_y = y + 30 * g_dir
        self.wire([(x - 24, y), (x - 12, y), (x - 12, ch_y)], color=color, sw=2.0)
        self.wire([(x + 12, ch_y), (x + 12, y), (x + 24, y)], color=color, sw=2.0)
        self.line(x - 15, ch_y, x + 15, ch_y, color=color, sw=2.3)
        self.line(x - 12, ox_y, x + 12, ox_y, color=color, sw=2.0)
        self.circle(x, bub_y, 3.0, fill=COL_BG, stroke=color, sw=1.7)
        self.line(x, g_y, x, bub_y + 3.0 * g_dir, color=color, sw=2.0)
        if label:
            ly = y - 10 if gate_pos == "bottom" else y + 18
            self.text(x, ly, label, size=11.5, color=color, anchor="middle", weight="bold")
        if sub:
            ly = y - 24 if gate_pos == "bottom" else y + 32
            self.text(x, ly, sub, size=10.5, color=COL_MUTED, anchor="middle")
        return {"l": (x - 24, y), "r": (x + 24, y), "g": (x, g_y)}

    def bjt_pnp(self, x, y, facing="right", color=COL_DARK, label="", sub="", label_side=None):
        """Substrate/vertical PNP: Emitter top (x, y-24), Collector bottom (x, y+24), Base (x-+28, y)."""
        s_dir = 1 if facing == "right" else -1
        bx = x - 13 * s_dir
        gx = x - 28 * s_dir
        self.line(gx, y, bx, y, color=color, sw=2.0)
        self.line(bx, y - 14, bx, y + 14, color=color, sw=2.5)
        # Emitter (top) angled to base with inward arrow
        self.wire([(x, y - 24), (x, y - 14), (bx, y - 5)], color=color, sw=2.0)
        mx, my = (x + bx) / 2, (y - 14 + y - 5) / 2
        self.poly([
            (bx + 2 * s_dir, y - 6),
            (mx + 1 * s_dir, my - 5),
            (mx + 5 * s_dir, my + 2),
        ], fill=color, stroke=color, sw=1.0)
        # Collector (bottom)
        self.wire([(bx, y + 5), (x, y + 14), (x, y + 24)], color=color, sw=2.0)
        lside = label_side or ("right" if facing == "right" else "left")
        self._place_dev_labels(x, y, lside, label, sub, color, dx=9)
        return {"e": (x, y - 24), "c": (x, y + 24), "b": (gx, y)}

    def bjt_npn(self, x, y, facing="right", color=COL_DARK, label="", sub="", label_side=None):
        """Vertical NPN: Collector top (x, y-24), Emitter bottom (x, y+24), Base (x-+28, y)."""
        s_dir = 1 if facing == "right" else -1
        bx = x - 13 * s_dir
        gx = x - 28 * s_dir
        self.line(gx, y, bx, y, color=color, sw=2.0)
        self.line(bx, y - 14, bx, y + 14, color=color, sw=2.5)
        self.wire([(x, y - 24), (x, y - 14), (bx, y - 5)], color=color, sw=2.0)
        self.wire([(bx, y + 5), (x, y + 14), (x, y + 24)], color=color, sw=2.0)
        mx, my = (x + bx) / 2, (y + 14 + y + 5) / 2
        self.poly([
            (x, y + 14),
            (mx - 1 * s_dir, my - 3),
            (mx - 4 * s_dir, my + 3),
        ], fill=color, stroke=color, sw=1.0)
        lside = label_side or ("right" if facing == "right" else "left")
        self._place_dev_labels(x, y, lside, label, sub, color, dx=9)
        return {"c": (x, y - 24), "e": (x, y + 24), "b": (gx, y)}

    # ---------------- Passive Components & Sources ----------------
    def res_v(self, x, y, color=COL_DARK, label="", sub="", label_side="right"):
        """Vertical resistor: t=(x, y-24), b=(x, y+24)."""
        pts = [
            (x, y - 24), (x, y - 16),
            (x + 6, y - 13), (x - 6, y - 8),
            (x + 6, y - 3), (x - 6, y + 3),
            (x + 6, y + 8), (x - 6, y + 13),
            (x, y + 16), (x, y + 24),
        ]
        self.wire(pts, color=color, sw=1.9)
        self._place_dev_labels(x, y, label_side, label, sub, color, dx=11)
        return {"t": (x, y - 24), "b": (x, y + 24)}

    def res_h(self, x, y, color=COL_DARK, label="", sub="", label_pos="top"):
        """Horizontal resistor: l=(x-24, y), r=(x+24, y)."""
        pts = [
            (x - 24, y), (x - 16, y),
            (x - 13, y - 6), (x - 8, y + 6),
            (x - 3, y - 6), (x + 3, y + 6),
            (x + 8, y - 6), (x + 13, y + 6),
            (x + 16, y), (x + 24, y),
        ]
        self.wire(pts, color=color, sw=1.9)
        if label:
            ly = y - 11 if label_pos == "top" else y + 19
            self.text(x, ly, label, size=11.5, color=color, anchor="middle", weight="bold")
        if sub:
            ly = y + 19 if label_pos == "top" else y - 11
            self.text(x, ly, sub, size=10.5, color=COL_MUTED, anchor="middle")
        return {"l": (x - 24, y), "r": (x + 24, y)}

    def cap_v(self, x, y, color=COL_DARK, label="", sub="", label_side="right"):
        """Vertical capacitor: t=(x, y-18), b=(x, y+18)."""
        self.line(x, y - 18, x, y - 4, color=color, sw=2.0)
        self.line(x - 11, y - 4, x + 11, y - 4, color=color, sw=2.3)
        self.line(x - 11, y + 4, x + 11, y + 4, color=color, sw=2.3)
        self.line(x, y + 4, x, y + 18, color=color, sw=2.0)
        self._place_dev_labels(x, y, label_side, label, sub, color, dx=15)
        return {"t": (x, y - 18), "b": (x, y + 18)}

    def cap_h(self, x, y, color=COL_DARK, label="", sub="", label_pos="top"):
        """Horizontal capacitor: l=(x-18, y), r=(x+18, y)."""
        self.line(x - 18, y, x - 4, y, color=color, sw=2.0)
        self.line(x - 4, y - 11, x - 4, y + 11, color=color, sw=2.3)
        self.line(x + 4, y - 11, x + 4, y + 11, color=color, sw=2.3)
        self.line(x + 4, y, x + 18, y, color=color, sw=2.0)
        if label:
            ly = y - 15 if label_pos == "top" else y + 23
            self.text(x, ly, label, size=11.5, color=color, anchor="middle", weight="bold")
        if sub:
            ly = y + 23 if label_pos == "top" else y - 15
            self.text(x, ly, sub, size=10.5, color=COL_MUTED, anchor="middle")
        return {"l": (x - 18, y), "r": (x + 18, y)}

    def ind_v(self, x, y, color=COL_DARK, label="", sub="", label_side="right"):
        """Vertical inductor: t=(x, y-24), b=(x, y+24)."""
        d = (
            f"M {fmt(x)} {fmt(y - 24)} L {fmt(x)} {fmt(y - 16)} "
            f"A 4 4 0 0 1 {fmt(x)} {fmt(y - 8)} "
            f"A 4 4 0 0 1 {fmt(x)} {fmt(y)} "
            f"A 4 4 0 0 1 {fmt(x)} {fmt(y + 8)} "
            f"A 4 4 0 0 1 {fmt(x)} {fmt(y + 16)} "
            f"L {fmt(x)} {fmt(y + 24)}"
        )
        self.path(d, stroke=color, sw=2.0)
        self._place_dev_labels(x, y, label_side, label, sub, color, dx=11)
        return {"t": (x, y - 24), "b": (x, y + 24)}

    def ind_h(self, x, y, color=COL_DARK, label="", label_pos="top"):
        """Horizontal inductor: l=(x-24, y), r=(x+24, y)."""
        d = (
            f"M {fmt(x - 24)} {fmt(y)} L {fmt(x - 16)} {fmt(y)} "
            f"A 4 4 0 0 1 {fmt(x - 8)} {fmt(y)} "
            f"A 4 4 0 0 1 {fmt(x)} {fmt(y)} "
            f"A 4 4 0 0 1 {fmt(x + 8)} {fmt(y)} "
            f"A 4 4 0 0 1 {fmt(x + 16)} {fmt(y)} "
            f"L {fmt(x + 24)} {fmt(y)}"
        )
        self.path(d, stroke=color, sw=2.0)
        if label:
            ly = y - 11 if label_pos == "top" else y + 19
            self.text(x, ly, label, size=11.5, color=color, anchor="middle", weight="bold")
        return {"l": (x - 24, y), "r": (x + 24, y)}

    def isrc_v(self, x, y, direction="down", color=COL_BIAS, label="", sub="", label_side="right"):
        """Independent current source: t=(x, y-24), b=(x, y+24)."""
        self.line(x, y - 24, x, y - 14, color=color, sw=2.0)
        self.line(x, y + 14, x, y + 24, color=color, sw=2.0)
        self.circle(x, y, 14, fill=COL_BG, stroke=color, sw=1.9)
        if direction == "down":
            self.arrow(x, y - 8, x, y + 7, color=color, sw=1.9)
        else:
            self.arrow(x, y + 8, x, y - 7, color=color, sw=1.9)
        self._place_dev_labels(x, y, label_side, label, sub, color, dx=18)
        return {"t": (x, y - 24), "b": (x, y + 24)}

    def dep_isrc_v(self, x, y, direction="down", color=COL_SIG, label="", sub="", label_side="right"):
        """Diamond controlled current source: t=(x, y-24), b=(x, y+24)."""
        self.line(x, y - 24, x, y - 16, color=color, sw=2.0)
        self.line(x, y + 16, x, y + 24, color=color, sw=2.0)
        self.poly([
            (x, y - 16), (x + 14, y), (x, y + 16), (x - 14, y)
        ], fill=COL_BG, stroke=color, sw=1.9)
        if direction == "down":
            self.arrow(x, y - 8, x, y + 7, color=color, sw=1.8)
        else:
            self.arrow(x, y + 8, x, y - 7, color=color, sw=1.8)
        self._place_dev_labels(x, y, label_side, label, sub, color, dx=18)
        return {"t": (x, y - 24), "b": (x, y + 24)}

    def vsrc_v(self, x, y, color=COL_DARK, label="", sub="", label_side="left", ac=False):
        """Independent voltage/noise source: t=(x, y-24), b=(x, y+24)."""
        self.line(x, y - 24, x, y - 14, color=color, sw=2.0)
        self.line(x, y + 14, x, y + 24, color=color, sw=2.0)
        self.circle(x, y, 14, fill=COL_BG, stroke=color, sw=1.9)
        if ac:
            self.path(
                f"M {fmt(x - 7)} {fmt(y)} Q {fmt(x - 3.5)} {fmt(y - 7)} {fmt(x)} {fmt(y)} "
                f"T {fmt(x + 7)} {fmt(y)}",
                stroke=color, sw=1.7
            )
        else:
            self.line(x - 3.5, y - 5.5, x + 3.5, y - 5.5, color=color, sw=1.6)
            self.line(x, y - 9, x, y - 2, color=color, sw=1.6)
            self.line(x - 3.5, y + 6, x + 3.5, y + 6, color=color, sw=1.6)
        self._place_dev_labels(x, y, label_side, label, sub, color, dx=18)
        return {"t": (x, y - 24), "b": (x, y + 24)}

    def vsrc_h(self, x, y, color=COL_WARN, label="", label_pos="top", plus_right=True):
        """Horizontal voltage/offset source: l=(x-22, y), r=(x+22, y)."""
        self.line(x - 22, y, x - 13, y, color=color, sw=2.0)
        self.line(x + 13, y, x + 22, y, color=color, sw=2.0)
        self.circle(x, y, 13, fill=COL_BG, stroke=color, sw=1.8)
        px = x + 5 if plus_right else x - 5
        mx = x - 5 if plus_right else x + 5
        self.line(px - 3, y, px + 3, y, color=color, sw=1.5)
        self.line(px, y - 3, px, y + 3, color=color, sw=1.5)
        self.line(mx - 3, y, mx + 3, y, color=color, sw=1.5)
        if label:
            ly = y - 16 if label_pos == "top" else y + 24
            self.text(x, ly, label, size=11, color=color, anchor="middle", weight="bold")
        return {"l": (x - 22, y), "r": (x + 22, y)}

    def sw_h(self, x, y, label="", color=COL_DARK, closed=False):
        """Horizontal sampling switch: l=(x-20, y), r=(x+20, y)."""
        self.line(x - 20, y, x - 10, y, color=color, sw=2.0)
        self.line(x + 10, y, x + 20, y, color=color, sw=2.0)
        self.circle(x - 8, y, 2.3, fill=COL_BG, stroke=color, sw=1.6)
        self.circle(x + 8, y, 2.3, fill=COL_BG, stroke=color, sw=1.6)
        if closed:
            self.line(x - 6, y - 1, x + 6, y - 1, color=color, sw=2.1)
        else:
            self.line(x - 6, y - 1, x + 7, y - 9, color=color, sw=2.1)
        if label:
            self.text(x, y - 13, label, size=11, color=COL_PURPLE, anchor="middle", weight="bold")
        return {"l": (x - 20, y), "r": (x + 20, y)}

    def opamp(self, x, y, w=58, h=52, facing="right", plus_top=False,
              diff_out=False, label="", color=COL_DARK, fill="#f8fafc"):
        """Op-amp / OTA triangle centered at (x, y)."""
        s_dir = 1 if facing == "right" else -1
        in_x = x - (w / 2) * s_dir
        out_x = x + (w / 2) * s_dir
        self.poly([
            (in_x, y - h / 2),
            (in_x, y + h / 2),
            (out_x, y),
        ], fill=fill, stroke=color, sw=2.0)

        sx = in_x + 9 * s_dir
        top_y, bot_y = y - 13, y + 13
        py, my = (top_y, bot_y) if plus_top else (bot_y, top_y)
        # + sign
        self.line(sx - 3.5, py, sx + 3.5, py, color=color, sw=1.6)
        self.line(sx, py - 3.5, sx, py + 3.5, color=color, sw=1.6)
        # - sign
        self.line(sx - 3.5, my, sx + 3.5, my, color=color, sw=1.6)

        if label:
            self.text(x - 4 * s_dir, y + 4, label, size=11.2,
                      color=color, anchor="middle", weight="bold")

        if diff_out:
            ox = x + (w * 0.22) * s_dir
            return {
                "in_top": (in_x, top_y),
                "in_bot": (in_x, bot_y),
                "out_p": (ox, y - 11),
                "out_n": (ox, y + 11),
            }
        return {"in_top": (in_x, top_y), "in_bot": (in_x, bot_y), "out": (out_x, y)}

    # ---------------- Plot Axes Helper ----------------
    def axes(self, x, y, w, h, xlabel="", ylabel="", title=""):
        """Draws clean scientific plot axes with origin at bottom-left (x, y+h)."""
        x0, y0 = x, y + h
        self.arrow(x0, y0, x + w + 8, y0, color=COL_DARK, sw=1.8)
        self.arrow(x0, y0, x0, y - 8, color=COL_DARK, sw=1.8)
        if xlabel:
            self.text(x + w, y0 + 18, xlabel, size=11.2, color=COL_DARK, anchor="end", weight="bold")
        if ylabel:
            self.text(x0 + 8, y + 4, ylabel, size=11.2, color=COL_DARK, anchor="start", weight="bold")
        if title:
            self.text(x + w / 2, y - 12, title, size=12, color=COL_DARK, anchor="middle", weight="bold")
        return (x0, y0)

    # ---------------- SVG Serialization ----------------
    def render(self):
        markers = []
        for name, col in [
            ("arr-dark", COL_DARK),
            ("arr-sig", COL_SIG),
            ("arr-bias", COL_BIAS),
            ("arr-warn", COL_WARN),
            ("arr-amber", COL_AMBER),
            ("arr-purple", COL_PURPLE),
            ("arr-muted", COL_MUTED),
        ]:
            markers.append(
                f'    <marker id="{name}" viewBox="0 0 10 10" refX="8.5" refY="5" '
                f'markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse">'
                f'<path d="M 0 1.2 L 9 5 L 0 8.8 z" fill="{col}"/></marker>'
            )
        defs = "  <defs>\n" + "\n".join(markers) + "\n  </defs>"
        body = "\n".join("  " + e for e in self.elements)
        return (
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{self.height}" '
            f'viewBox="0 0 {self.width} {self.height}">\n'
            f'{defs}\n'
            f'{body}\n'
            f'</svg>\n'
        )


def validate_svg_file(filepath):
    """
    Validates XML well-formedness, non-empty viewBox, non-trivial geometry,
    in-bounds text placement, and zero text-on-text collisions.
    """
    tree = ET.parse(filepath)
    root = tree.getroot()
    vb = root.attrib.get("viewBox", "")
    parts = [float(p) for p in vb.split()]
    if len(parts) != 4 or parts[2] <= 100 or parts[3] <= 100:
        raise ValueError(f"{filepath}: invalid viewBox '{vb}'")
    w, h = parts[2], parts[3]

    geom_tags = {"line", "polyline", "polygon", "path", "rect", "circle", "ellipse"}
    geom_count = 0
    texts = []
    for elem in root.iter():
        tag = elem.tag.split("}")[-1]
        if tag in geom_tags:
            geom_count += 1
        elif tag == "text":
            tx = float(elem.attrib.get("x", "0"))
            ty = float(elem.attrib.get("y", "0"))
            fs = float(elem.attrib.get("font-size", "12"))
            anchor = elem.attrib.get("text-anchor", "start")
            content = "".join(elem.itertext()).strip()
            if not content:
                continue
            # Conservative character-width estimate
            est_w = sum(0.68 * fs if ord(ch) > 127 or ch.isupper() else 0.54 * fs for ch in content)
            if anchor == "middle":
                x0, x1 = tx - est_w / 2, tx + est_w / 2
            elif anchor == "end":
                x0, x1 = tx - est_w, tx
            else:
                x0, x1 = tx, tx + est_w
            y0, y1 = ty - 0.80 * fs, ty + 0.20 * fs
            if x0 < 8 or x1 > w - 8 or y0 < 8 or y1 > h - 8:
                raise ValueError(
                    f"{os.path.basename(filepath)}: text out of bounds '{content}' "
                    f"box=({x0:.1f},{y0:.1f})-({x1:.1f},{y1:.1f}) in {w}x{h}"
                )
            texts.append((x0, y0, x1, y1, content))

    if geom_count < 15:
        raise ValueError(f"{filepath}: insufficient schematic geometry ({geom_count})")

    # Pairwise text bounding-box overlap check (strict zero-pixel tolerance)
    for i in range(len(texts)):
        ax0, ay0, ax1, ay1, sa = texts[i]
        for j in range(i + 1, len(texts)):
            bx0, by0, bx1, by1, sb = texts[j]
            if ax0 < bx1 and ax1 > bx0 and ay0 < by1 and ay1 > by0:
                raise ValueError(
                    f"{os.path.basename(filepath)}: overlapping labels '{sa}' and '{sb}'"
                )
    return geom_count, len(texts)


# ==============================================================================
# PART 2: DIAGRAMS 01 - 12 (Foundations, Single-Stage, Diff-Pair, Mirrors, Ch.6)
# ==============================================================================

def diag_01_analog_design_octagon():
    d = SVGDoc(
        "analog-design-octagon.svg",
        "Analog Design Octagon (8-Axis Coupled Trade-Off Web)",
        "Bát giác Thiết kế Mạch Tương tự — Mạng Đánh đổi Đa chiều (Razavi Ch.01 §1.4)",
        "Ch.01", [1], width=1040, height=590, legend=False
    )
    cx, cy, r = 320, 332, 168
    axes_info = [
        (-90,  "Noise",             "Nhiễu",                COL_WARN),
        (-45,  "Linearity",         "Độ tuyến tính",        COL_SIG),
        (0,    "Gain",              "Độ lợi (Av)",          COL_SIG),
        (45,   "Supply (VDD)",      "Điện áp nguồn cấp",    COL_BIAS),
        (90,   "Voltage Swing",     "Dải dao động áp",      COL_AMBER),
        (135,  "Speed / BW",        "Tốc độ / Băng thông",  COL_SIG),
        (180,  "In/Out Impedance",  "Trở kháng vào / ra",   COL_PURPLE),
        (-135, "Power Dissipation", "Công suất tiêu tán",   COL_WARN),
    ]
    pts = []
    for deg, _, _, _ in axes_info:
        rad = math.radians(deg)
        pts.append((cx + r * math.cos(rad), cy + r * math.sin(rad)))

    # Subtle background rings
    d.circle(cx, cy, r * 0.55, fill="none", stroke="#f1f5f9", sw=1.2, dash="4,4")
    d.circle(cx, cy, r * 0.80, fill="none", stroke="#f1f5f9", sw=1.2, dash="4,4")

    # All-to-all trade-off web chords
    for i in range(8):
        for j in range(i + 1, 8):
            is_adj = (j - i == 1) or (i == 0 and j == 7)
            if not is_adj:
                d.line(pts[i][0], pts[i][1], pts[j][0], pts[j][1],
                       color="#cbd5e1", sw=1.15)

    # Highlight primary Razavi trade-off diagonals
    highlight_pairs = [
        (0, 7, COL_WARN),   # Noise <-> Power
        (2, 5, COL_SIG),    # Gain <-> Speed
        (2, 4, COL_AMBER),  # Gain <-> Swing (cascode stack)
        (1, 4, COL_BIAS),   # Linearity <-> Swing
        (3, 4, COL_AMBER),  # VDD <-> Swing
    ]
    for i, j, col in highlight_pairs:
        d.line(pts[i][0], pts[i][1], pts[j][0], pts[j][1], color=col, sw=2.1, dash="6,3")

    # Outer Octagon Perimeter
    d.poly(pts, fill="none", stroke=COL_DARK, sw=2.6)

    # Center hub badge
    d.circle(cx, cy, 38, fill="#eff6ff", stroke="#3b82f6", sw=1.8)
    d.text(cx, cy - 4, "8-D", size=13, color="#1d4ed8", anchor="middle", weight="bold")
    d.text(cx, cy + 12, "Trade-Offs", size=10.5, color=COL_MUTED, anchor="middle")

    # Vertex nodes & non-overlapping pill labels
    label_offsets = [
        (0, -34, "middle"),     # Top: Noise
        (20, -18, "start"),     # Top-right: Linearity
        (22, -4, "start"),      # Right: Gain
        (20, 18, "start"),      # Bottom-right: Supply
        (0, 30, "middle"),      # Bottom: Swing
        (-20, 18, "end"),       # Bottom-left: Speed
        (-20, -4, "end"),       # Left: Z_in/out
        (-20, -18, "end"),      # Top-left: Power
    ]
    for idx, (deg, en, vi, col) in enumerate(axes_info):
        px, py = pts[idx]
        d.circle(px, py, 6.5, fill=col, stroke=COL_BG, sw=2.0)
        dx, dy, anc = label_offsets[idx]
        d.text(px + dx, py + dy, en, size=12.2, color=COL_DARK, anchor=anc, weight="bold")
        d.text(px + dx, py + dy + 15, vi, size=10.8, color=COL_MUTED, anchor=anc)

    # Right-side analytical cards
    d.callout(615, 84, 400, 226, "Canonical Octagon Couplings (Razavi §1.4)", [
        "1. Gain vs Speed: Higher Rout boosts Av = gm*Rout",
        "   but lowers output pole wp = 1/(Rout*CL).",
        "2. Gain vs Voltage Swing: Cascoding boosts Av ~ (gm*ro)^2",
        "   at the direct cost of VDS,min headroom per stacked device.",
        "3. Noise vs Power: Input thermal noise Vn^2 = 4kT*gamma/gm",
        "   halves only when ID and W scale up by 2x (Linear Scaling).",
        "4. Linearity vs Swing & VDD: Larger Vov widens linear",
        "   diff-pair range sqrt(2)*Vov but eats output headroom.",
    ], tone="sig", fs=11.0)

    d.callout(615, 328, 400, 234, "Abstraction Levels & Process-Agnostic Rule", [
        "• Physics Level: Carrier velocity sat vsat, DIBL, oxide tox",
        "• Device Level: gm/ID, VDS,min, intrinsic gain gm*ro, fT",
        "• Circuit Level: CS, Cascode, Diff-Pair, Mirrors, OTA",
        "• Architecture Level: Two-Stage, Folded, BGR, CP-PLL",
        "",
        "PDK-Agnostic Invariant (180nm -> 90nm -> 65nm -> 45nm):",
        "Topology trade-off laws remain invariant; express rules",
        "in VDS,min, gm/ID, gm*ro, and M:N finger ratios.",
    ], tone="bias", fs=11.0)
    return d


def diag_02_mos_small_signal_caps():
    d = SVGDoc(
        "mos-small-signal-caps.svg",
        "MOSFET Complete High-Frequency Small-Signal Model",
        "Mô hình Tín hiệu nhỏ Tần số cao Đầy đủ của MOSFET (gm·vgs, gmb·vbs, ro & 5 Tụ Ký sinh)",
        "Ch.02", [2], width=1060, height=580
    )
    # Nodes & Coordinates
    gx, gy = 100, 225
    s_bus_y = 375
    b_bus_y = 495
    d_y = 225

    # Gate input & top Cgd bridge
    d.port(gx, gy, "G (Gate)", side="top", color=COL_SIG)
    d.wire([(gx + 4, gy), (235, gy)], color=COL_SIG)
    d.dot(155, gy, COL_SIG)
    d.dot(235, gy, COL_SIG)

    # Cgd bridge along top (y=135)
    d.wire([(235, gy), (235, 135), (372, 135)], color=COL_WARN)
    cgd = d.cap_h(390, 135, color=COL_WARN, label="Cgd (Overlap / Miller)", label_pos="top")
    d.wire([cgd["r"], (560, 135), (560, d_y)], color=COL_WARN)

    # Cgb from Gate (x=155) down to Body bus (y=495)
    d.line(155, gy, 155, 332, color=COL_AMBER)
    cgb = d.cap_v(155, 350, color=COL_AMBER, label="Cgb", label_side="left")
    d.line(155, cgb["b"][1], 155, b_bus_y, color=COL_AMBER)
    d.dot(155, b_bus_y, COL_DARK)

    # Cgs from Gate (x=235) down to Source bus (y=375)
    d.line(235, gy, 235, 282, color=COL_WARN)
    cgs = d.cap_v(235, 300, color=COL_WARN, label="Cgs", sub="+ vgs −", label_side="left")
    d.line(235, cgs["b"][1], 235, s_bus_y, color=COL_WARN)
    d.dot(235, s_bus_y, COL_DARK)

    # Drain rail (y=225) from x=365 to Drain port (x=695)
    d.line(365, d_y, 691, d_y, color=COL_SIG)
    d.port(695, d_y, "D (Drain)", side="right", color=COL_SIG)
    d.dot(475, d_y, COL_SIG)
    d.dot(560, d_y, COL_SIG)
    d.dot(585, d_y, COL_SIG)
    d.dot(650, d_y, COL_SIG)

    # Controlled source gm*vgs (x=365)
    d.line(365, d_y, 365, 276, color=COL_SIG)
    gm_src = d.dep_isrc_v(365, 300, direction="down", color=COL_SIG,
                          label="gm·vgs", label_side="right")
    d.line(365, gm_src["b"][1], 365, s_bus_y, color=COL_SIG)
    d.dot(365, s_bus_y, COL_DARK)

    # Body-effect controlled source gmb*vbs (x=475)
    d.line(475, d_y, 475, 276, color=COL_BIAS)
    gmb_src = d.dep_isrc_v(475, 300, direction="down", color=COL_BIAS,
                           label="gmb·vbs", sub="η·gm·vbs", label_side="right")
    d.line(475, gmb_src["b"][1], 475, s_bus_y, color=COL_BIAS)
    d.dot(475, s_bus_y, COL_DARK)

    # Output resistance ro (x=585)
    d.line(585, d_y, 585, 276, color=COL_DARK)
    ro = d.res_v(585, 300, color=COL_DARK, label="ro", sub="1/(λ·ID)", label_side="right")
    d.line(585, ro["b"][1], 585, s_bus_y, color=COL_DARK)
    d.dot(585, s_bus_y, COL_DARK)

    # Source bus (y=375)
    d.line(235, s_bus_y, 691, s_bus_y, color=COL_DARK)
    d.port(695, s_bus_y, "S (Source)", side="right", color=COL_DARK)
    d.dot(310, s_bus_y, COL_DARK)

    # Csb between Source (y=375) and Body (y=495) at x=310
    d.line(310, s_bus_y, 310, 417, color=COL_AMBER)
    csb = d.cap_v(310, 435, color=COL_AMBER, label="Csb", sub="− vbs +", label_side="right")
    d.line(310, csb["b"][1], 310, b_bus_y, color=COL_AMBER)
    d.dot(310, b_bus_y, COL_DARK)

    # Cdb between Drain (y=225) and Body (y=495) at x=650
    d.line(650, d_y, 650, 417, color=COL_AMBER)
    cdb = d.cap_v(650, 435, color=COL_AMBER, label="Cdb", label_side="left")
    d.line(650, cdb["b"][1], 650, b_bus_y, color=COL_AMBER)
    d.dot(650, b_bus_y, COL_DARK)

    # Body bus (y=495)
    d.line(155, b_bus_y, 691, b_bus_y, color=COL_MUTED)
    d.port(695, b_bus_y, "B (Body)", side="right", color=COL_MUTED)

    # Right-side Capacitance & Parameter Summary
    d.callout(775, 88, 265, 224, "Saturation Region Caps (§2.5)", [
        "• Cgs ≈ (2/3)·W·L·Cox + W·Cov",
        "• Cgd ≈ W·Cov  (gate-drain ovlp)",
        "• Cgb ≈ 0  (shielded by channel)",
        "• Cdb = Cdb0 / (1 + VDB/φB)^mj",
        "• Csb = Csb0 / (1 + VSB/φB)^mj",
        "",
        "Triode: Cgs = Cgd ≈ (1/2)WLCox+WCov",
        "Cutoff: Cgb ≈ WLCox || Cdep",
    ], tone="warn", fs=10.8)

    d.callout(775, 330, 265, 212, "Key Small-Signal Relations", [
        "• gm = ∂ID/∂VGS = 2·ID / Vov",
        "     = √(2·μn·Cox·(W/L)·ID)",
        "• gmb = η·gm  (η ≈ 0.1 - 0.25)",
        "• Intrinsic Gain: Av0 = gm·ro",
        "• Transit Freq (Unity Current Gain):",
        "  fT ≈ gm / [2π·(Cgs + Cgd)]",
    ], tone="sig", fs=10.8)
    return d


def diag_03_short_channel_iv_gmid():
    d = SVGDoc(
        "short-channel-iv-gmid.svg",
        "Short-Channel I–V (Velocity Sat & DIBL) vs gm/ID Sizing Curve",
        "Đặc tuyến I–V Kênh ngắn (Bão hòa Vận tốc & DIBL) và Đường cong Định cỡ gm/ID (Ch.11 & Ch.17)",
        "Ch.11 & 17", [11, 17], width=1060, height=580, legend=False
    )
    # Left Panel: ID vs VDS
    d.panel(22, 74, 492, 484, "(a) Long-Channel Square-Law vs Nanometer Short-Channel I–V")
    x0, y0 = d.axes(68, 138, 405, 345, xlabel="VDS", ylabel="ID")

    # VDS,min dashed locus
    d.path(f"M {x0} {y0} Q {x0 + 62} {y0 - 150} {x0 + 135} {y0 - 320}",
           stroke=COL_BIAS, sw=1.8, dash="5,4")
    d.text(x0 + 142, y0 - 316, "VDS,min locus", size=10.8, color=COL_BIAS, weight="bold")

    # Square-law curves (quadratic spacing: h = 28, 95, 195, 315, flat sat)
    sq_heights = [28, 92, 188, 308]
    for idx, h in enumerate(sq_heights):
        vk = 38 + idx * 24
        d.path(
            f"M {x0} {y0} Q {x0 + vk * 0.55} {y0 - h} {x0 + vk} {y0 - h} "
            f"L {x0 + 380} {y0 - h}",
            stroke=COL_SIG, sw=1.7, dash="6,4"
        )

    # Velocity-saturated + DIBL curves (equal linear spacing + upward slope in sat)
    sc_heights = [46, 110, 174, 238]
    for idx, h in enumerate(sc_heights):
        vk = 34 + idx * 16
        end_h = h + 26 + idx * 5  # DIBL / CLM droop in ro
        d.path(
            f"M {x0} {y0} Q {x0 + vk * 0.55} {y0 - h} {x0 + vk} {y0 - h} "
            f"L {x0 + 380} {y0 - end_h}",
            stroke=COL_WARN, sw=2.3
        )
        d.text(x0 + 385, y0 - end_h + 4, f"VGS{idx + 1}", size=10.2, color=COL_WARN, weight="bold")

    # Legend inside left panel
    d.line(82, 514, 110, 514, color=COL_SIG, sw=1.9, dash="6,4")
    d.text(118, 518, "Square-Law: quadratic ΔID ∝ (VGS−VTH)^2", size=10.8, color=COL_SIG)
    d.line(82, 536, 110, 536, color=COL_WARN, sw=2.3)
    d.text(118, 540, "Short-Channel: linear ΔID (vsat) + DIBL finite ro slope", size=10.8, color=COL_WARN)

    # Right Panel: gm/ID & fT vs VGS - VTH / Inversion Level
    d.panel(536, 74, 502, 484, "(b) Transconductance Efficiency gm/ID & fT vs Inversion Region")
    rx0, ry0 = d.axes(585, 138, 395, 345, xlabel="Inversion Level: VGS − VTH  [or log ID/(W/L)]", ylabel="gm / ID  [V⁻¹]")
    # Secondary right vertical axis for fT
    d.arrow(rx0 + 395, ry0, rx0 + 395, 130, color=COL_AMBER, sw=1.7)
    d.text(rx0 + 388, 126, "fT (Speed)", size=11, color=COL_AMBER, anchor="end", weight="bold")

    # Sweet-spot Moderate Inversion shaded zone
    d.rect(rx0 + 125, 145, 115, 338, fill="#ecfdf5", stroke="#a7f3d0", sw=1.0, rx=4, opacity=0.65)
    d.text(rx0 + 182, 315, "Moderate Inv.", size=11, color=COL_BIAS, anchor="middle", weight="bold")
    d.text(rx0 + 182, 331, "Sweet Spot", size=10.5, color=COL_BIAS, anchor="middle")
    d.text(rx0 + 62, 315, "Weak Inv.", size=10.8, color=COL_MUTED, anchor="middle")
    d.text(rx0 + 332, 315, "Strong Inv.", size=10.8, color=COL_MUTED, anchor="middle")

    # gm/ID curve (high plateau ~26 V^-1 -> smooth roll-off)
    gmid_pts = []
    for i in range(41):
        u = i / 40.0
        px = rx0 + 10 + u * 375
        # Logistic transition from 1/(n*VT) down to 2/Vov
        val = 0.18 + 0.74 / (1.0 + math.exp((u - 0.42) * 7.5))
        py = ry0 - val * 320
        gmid_pts.append((px, py))
    d.wire(gmid_pts, color=COL_SIG, sw=2.6)
    d.text(rx0 + 18, ry0 - 308, "gm/ID ≈ 1/(ζ·VT) ≈ 26 V⁻¹", size=10.8, color=COL_SIG, weight="bold")

    # fT curve (rising and saturating at velocity saturation limit)
    ft_pts = []
    for i in range(41):
        u = i / 40.0
        px = rx0 + 10 + u * 375
        val = 0.86 * (u ** 1.55) / (0.35 + (u ** 1.55))
        py = ry0 - 12 - val * 300
        ft_pts.append((px, py))
    d.wire(ft_pts, color=COL_AMBER, sw=2.4, dash="7,3")
    d.text(rx0 + 275, ry0 - 268, "fT ≈ gm/(2π·Cgg)", size=10.8, color=COL_AMBER, weight="bold")

    # Bottom summary inside right panel
    d.text(558, 518, "• Input Diff-Pair: High gm/ID (14–22 V⁻¹) -> max Gm/Power & low VOS", size=10.6, color=COL_DARK)
    d.text(558, 538, "• Current Mirrors / Loads: Low gm/ID (5–9 V⁻¹) -> low noise & tight matching", size=10.6, color=COL_DARK)
    return d


def diag_04_cs_loads_comparison():
    d = SVGDoc(
        "cs-loads-comparison.svg",
        "Common-Source (CS) Stage: Load Topologies Comparison",
        "So sánh Tầng Nguồn chung (CS): Tải Điện trở, Tải Nối Diode và Tải Nguồn dòng (Ch.03 §3.3)",
        "Ch.03", [3], width=1060, height=580
    )
    panels = [
        (22,  "(a) Resistive Load (RD)"),
        (366, "(b) Diode-Connected Load (M2)"),
        (710, "(c) Current-Source Load (M2)"),
    ]
    for px, title in panels:
        d.panel(px, 74, 328, 484, title)

    # --- (a) Resistive Load ---
    cx1 = 186
    d.vdd(cx1, 136)
    rd = d.res_v(cx1, 185, color=COL_DARK, label="RD", label_side="right")
    d.line(cx1, 136, cx1, rd["t"][1])
    d.line(cx1, rd["b"][1], cx1, 296, color=COL_SIG)
    d.dot(cx1, 252, COL_SIG)
    d.line(cx1, 252, cx1 + 65, 252, color=COL_SIG)
    d.port(cx1 + 69, 252, "Vout", side="right", color=COL_SIG)
    m1a = d.nmos(cx1, 320, facing="right", color=COL_SIG, label="M1", sub="gm1, ro1")
    d.line(cx1 - 68, 320, m1a["g"][0], 320, color=COL_SIG)
    d.port(cx1 - 72, 320, "Vin", side="left", color=COL_SIG)
    d.line(cx1, m1a["s"][1], cx1, 382)
    d.gnd(cx1, 382)
    d.callout(38, 424, 296, 118, "Gain vs Headroom Trade-Off", [
        "Av = −gm1 · (RD || ro1)",
        "Rout = RD || ro1",
        "Bottleneck: Large Av needs large",
        "ID·RD drop -> crushes Vout swing!",
    ], tone="neutral", fs=10.6)

    # --- (b) Diode-Connected Load ---
    cx2 = 530
    d.vdd(cx2, 136)
    m2b = d.pmos(cx2, 190, facing="right", color=COL_BIAS, label="M2", sub="1/(gm2+gmb2)")
    d.line(cx2, 136, cx2, m2b["s"][1])
    # Gate-to-drain diode connection on left of M2
    d.wire([m2b["g"], (cx2 - 42, 190), (cx2 - 42, 232), (cx2, 232)], color=COL_BIAS)
    d.dot(cx2, 232, COL_BIAS)
    d.line(cx2, m2b["d"][1], cx2, 296, color=COL_SIG)
    d.dot(cx2, 256, COL_SIG)
    d.line(cx2, 256, cx2 + 65, 256, color=COL_SIG)
    d.port(cx2 + 69, 256, "Vout", side="right", color=COL_SIG)
    m1b = d.nmos(cx2, 320, facing="right", color=COL_SIG, label="M1", sub="gm1, ro1")
    d.line(cx2 - 68, 320, m1b["g"][0], 320, color=COL_SIG)
    d.port(cx2 - 72, 320, "Vin", side="left", color=COL_SIG)
    d.line(cx2, m1b["s"][1], cx2, 382)
    d.gnd(cx2, 382)
    d.callout(382, 424, 296, 118, "Linear Moderate Gain", [
        "Rout ≈ 1/gm2 || ro2 || ro1",
        "Av ≈ −gm1 / gm2  (if PMOS B=S)",
        "   = −√[μn(W/L)1 / μp(W/L)2]",
        "Good linearity, modest gain (2–8x).",
    ], tone="bias", fs=10.6)

    # --- (c) Current-Source Load ---
    cx3 = 874
    d.vdd(cx3, 136)
    m2c = d.pmos(cx3, 190, facing="right", color=COL_BIAS, label="M2", sub="ro2 (Active CS)")
    d.line(cx3, 136, cx3, m2c["s"][1])
    d.line(cx3 - 64, 190, m2c["g"][0], 190, color=COL_BIAS)
    d.port(cx3 - 68, 190, "Vb", side="left", color=COL_BIAS)
    d.line(cx3, m2c["d"][1], cx3, 296, color=COL_SIG)
    d.dot(cx3, 252, COL_SIG)
    d.line(cx3, 252, cx3 + 65, 252, color=COL_SIG)
    d.port(cx3 + 69, 252, "Vout", side="right", color=COL_SIG)
    m1c = d.nmos(cx3, 320, facing="right", color=COL_SIG, label="M1", sub="gm1, ro1")
    d.line(cx3 - 68, 320, m1c["g"][0], 320, color=COL_SIG)
    d.port(cx3 - 72, 320, "Vin", side="left", color=COL_SIG)
    d.line(cx3, m1c["s"][1], cx3, 382)
    d.gnd(cx3, 382)
    d.callout(726, 424, 296, 118, "High Intrinsic Gain Stage", [
        "Rout = ro1 || ro2",
        "Av = −gm1 · (ro1 || ro2)",
        "Vout,max = VDD − |VDS,min2|",
        "Foundation of CMOS OTA stages!",
    ], tone="sig", fs=10.6)
    return d


def diag_05_cs_source_degeneration():
    d = SVGDoc(
        "cs-source-degeneration.svg",
        "CS Stage with Source Degeneration: Linearization & Rout Boost",
        "Tầng CS Suy biến Cực nguồn: Tuyến tính hóa Gm và Khuếch đại Trở kháng ra Rout (Ch.03 §3.3.6)",
        "Ch.03", [3], width=1040, height=580
    )
    d.panel(22, 74, 486, 484, "(a) Degenerated CS Stage (Series Feedback)")
    d.panel(532, 74, 486, 484, "(b) Inspection Model for Boosted Rout")

    # --- Left: Degenerated CS ---
    cx1 = 245
    d.vdd(cx1, 134)
    rd = d.res_v(cx1, 178, color=COL_DARK, label="RD", label_side="right")
    d.line(cx1, 134, cx1, rd["t"][1])
    d.line(cx1, rd["b"][1], cx1, 256, color=COL_SIG)
    d.dot(cx1, 226, COL_SIG)
    d.line(cx1, 226, cx1 + 78, 226, color=COL_SIG)
    d.port(cx1 + 82, 226, "Vout", side="right", color=COL_SIG)

    m1 = d.nmos(cx1, 280, facing="right", color=COL_SIG, label="M1", sub="gm, gmb, ro")
    d.line(cx1 - 80, 280, m1["g"][0], 280, color=COL_SIG)
    d.port(cx1 - 84, 280, "Vin", side="left", color=COL_SIG)

    # Source node VS & degeneration resistor RS
    d.line(cx1, m1["s"][1], cx1, 344, color=COL_AMBER)
    d.dot(cx1, 326, COL_AMBER)
    d.text(cx1 - 12, 330, "VS = id·RS", size=11, color=COL_AMBER, anchor="end", weight="bold")
    rs = d.res_v(cx1, 368, color=COL_AMBER, label="RS", sub="Local −FB", label_side="right")
    d.line(cx1, rs["b"][1], cx1, 412)
    d.gnd(cx1, 412)

    d.callout(44, 442, 442, 102, "Effective Transconductance Gm", [
        "Gm = id / vin = gm / [1 + (gm + gmb)·RS]",
        "Av = −Gm · RD  ≈ −RD / RS   when gm·RS >> 1",
        "Trade-off: Smoother gm curvature (higher linearity), lower gain & headroom.",
    ], tone="sig", fs=10.6)

    # --- Right: Rout Test Circuit ---
    cx2 = 715
    # Test node at drain (y=156)
    d.line(cx2, 156, cx2 + 125, 156, color=COL_BIAS)
    d.dot(cx2, 156, COL_BIAS)
    d.dot(cx2 + 72, 156, COL_DARK)

    m1r = d.nmos(cx2, 232, facing="right", color=COL_BIAS, label="M1", sub="vgs = −vs")
    d.line(cx2, 156, cx2, m1r["d"][1], color=COL_BIAS)
    # Gate grounded
    d.wire([m1r["g"], (cx2 - 52, 232), (cx2 - 52, 268)], color=COL_DARK)
    d.gnd(cx2 - 52, 268)
    d.text(cx2 - 52, 222, "VG = 0", size=10.8, color=COL_MUTED, anchor="middle")

    # External ro drawn explicitly in parallel from Drain (156) to Source (305)
    ro_r = d.res_v(cx2 + 72, 232, color=COL_DARK, label="ro", label_side="right")
    d.line(cx2 + 72, 156, cx2 + 72, ro_r["t"][1])
    d.wire([ro_r["b"], (cx2 + 72, 305), (cx2, 305)], color=COL_DARK)
    d.dot(cx2, 305, COL_AMBER)

    d.line(cx2, m1r["s"][1], cx2, 336, color=COL_AMBER)
    rs2 = d.res_v(cx2, 360, color=COL_AMBER, label="RS", sub="vs = Ix·RS", label_side="left")
    d.line(cx2, rs2["b"][1], cx2, 408)
    d.gnd(cx2, 408)

    # Vx test source on far right (x=865)
    vx = d.vsrc_v(cx2 + 150, 275, color=COL_BIAS, label="Vx", sub="Test Ix", label_side="right", ac=True)
    d.wire([(cx2 + 125, 156), (cx2 + 150, 156), vx["t"]], color=COL_BIAS)
    d.line(cx2 + 150, vx["b"][1], cx2 + 150, 408, color=COL_BIAS)
    d.gnd(cx2 + 150, 408)
    d.arrow(cx2 + 138, 144, cx2 + 95, 144, color=COL_BIAS, sw=1.8)
    d.text(cx2 + 116, 136, "Ix", size=11.2, color=COL_BIAS, anchor="middle", weight="bold")

    d.callout(554, 442, 442, 102, "Output Impedance Multiplication Law (Razavi Eq. 3.68)", [
        "Rout = [1 + (gm + gmb)·ro]·RS + ro",
        "     ≈ (gm + gmb)·ro·RS + ro   (boosted by ~gm·ro!)",
        "Foundation of Cascode stages (replace RS with ro of bottom FET).",
    ], tone="bias", fs=10.6)
    return d


def diag_06_source_follower_and_cg():
    d = SVGDoc(
        "source-follower-and-cg.svg",
        "Source Follower (Common-Drain) vs Common-Gate (CG) Stage",
        "So sánh Mạch Bám nguồn (Source Follower) và Tầng Cổng chung (Common-Gate) (Ch.03 §3.4–3.5)",
        "Ch.03", [3], width=1040, height=580
    )
    d.panel(22, 74, 486, 484, "(a) Source Follower (Voltage Buffer / Level Shifter)")
    d.panel(532, 74, 486, 484, "(b) Common-Gate Stage (Current Buffer / High-Freq)")

    # --- (a) Source Follower ---
    cx1 = 245
    d.vdd(cx1, 140)
    m1 = d.nmos(cx1, 215, facing="right", color=COL_SIG, label="M1", sub="gm1, gmb1", show_body=True)
    d.line(cx1, 140, cx1, m1["d"][1])
    # Body grounded to show body effect gmb1 != 0 in N-well CMOS
    d.wire([m1["b"], (cx1 + 36, 215), (cx1 + 36, 236)], color=COL_MUTED)
    d.gnd(cx1 + 36, 236)
    d.line(cx1 - 80, 215, m1["g"][0], 215, color=COL_SIG)
    d.port(cx1 - 84, 215, "Vin", side="left", color=COL_SIG)

    # Source output node (y=280)
    d.line(cx1, m1["s"][1], cx1, 320, color=COL_SIG)
    d.dot(cx1, 280, COL_SIG)
    d.line(cx1, 280, cx1 + 88, 280, color=COL_SIG)
    d.port(cx1 + 92, 280, "Vout", side="right", color=COL_SIG)

    # Current source load M2
    m2 = d.nmos(cx1, 344, facing="right", color=COL_BIAS, label="M2 (ISS)", sub="ro2")
    d.line(cx1 - 68, 344, m2["g"][0], 344, color=COL_BIAS)
    d.port(cx1 - 72, 344, "Vb", side="left", color=COL_BIAS)
    d.line(cx1, m2["s"][1], cx1, 402)
    d.gnd(cx1, 402)

    d.callout(44, 430, 442, 114, "Source Follower Properties (§3.4)", [
        "• Av = gm1 / (gm1 + gmb1 + 1/(ro1 || ro2 || RL)) < 1",
        "• High Rin (∞ at DC), Low Rout ≈ 1/(gm1 + gmb1) || ro1 || ro2",
        "• Caveat: Body effect η = gmb1/gm1 attenuates gain & adds",
        "  nonlinearity; poor heavy resistive current driver.",
    ], tone="sig", fs=10.5)

    # --- (b) Common-Gate Stage ---
    cx2 = 775
    d.vdd(cx2, 134)
    rd = d.res_v(cx2, 178, color=COL_DARK, label="RD", label_side="right")
    d.line(cx2, 134, cx2, rd["t"][1])
    d.line(cx2, rd["b"][1], cx2, 250, color=COL_SIG)
    d.dot(cx2, 224, COL_SIG)
    d.line(cx2, 224, cx2 + 82, 224, color=COL_SIG)
    d.port(cx2 + 86, 224, "Vout", side="right", color=COL_SIG)

    mcg = d.nmos(cx2, 274, facing="right", color=COL_SIG, label="M1", sub="gm1, gmb1, ro1")
    d.line(cx2 - 70, 274, mcg["g"][0], 274, color=COL_BIAS)
    d.port(cx2 - 74, 274, "Vb (AC GND)", side="left", color=COL_BIAS)

    # Source driven by Vin + ISS bias to GND
    d.line(cx2, mcg["s"][1], cx2, 344, color=COL_SIG)
    d.dot(cx2, 322, COL_SIG)
    d.line(cx2 - 84, 322, cx2, 322, color=COL_SIG)
    d.port(cx2 - 88, 322, "Vin", side="left", color=COL_SIG)

    iss = d.isrc_v(cx2, 368, direction="down", color=COL_BIAS, label="ISS", label_side="right")
    d.line(cx2, iss["b"][1], cx2, 404)
    d.gnd(cx2, 404)

    d.callout(554, 430, 442, 114, "Common-Gate Properties (§3.5)", [
        "• Non-inverting Gain: Av ≈ +(gm1 + gmb1)·RD  (if ro1 -> ∞)",
        "• Exact Input Z: Rin = (RD + ro1) / [1 + (gm1 + gmb1)·ro1]",
        "  -> Low Rin ≈ 1/(gm1+gmb1) ONLY if RD << ro1! (High if I-load!)",
        "• Zero Miller Cgd multiplication (gate is AC grounded).",
    ], tone="bias", fs=10.5)
    return d


def diag_07_cascode_shielding():
    d = SVGDoc(
        "cascode-shielding.svg",
        "Telescopic Cascode Stage: Drain-Voltage Shielding & Rout ≈ gm·ro²",
        "Tầng Cascode Lồng (Telescopic): Cơ chế Che chắn Cực máng & Nâng Rout ≈ gm·ro² (Ch.03 §3.6)",
        "Ch.03", [3], width=1040, height=580
    )
    # Left schematic card
    d.panel(24, 74, 480, 484, "Cascode Amplifier & Shielded Internal Node X")
    cx = 235
    d.vdd(cx, 130)
    iload = d.isrc_v(cx, 174, direction="down", color=COL_BIAS, label="I0 (Active Load)", sub="Rout,p", label_side="right")
    d.line(cx, 130, cx, iload["t"][1])

    # Output node Vout (y=222)
    d.line(cx, iload["b"][1], cx, 248, color=COL_SIG)
    d.dot(cx, 222, COL_SIG)
    d.line(cx, 222, cx + 105, 222, color=COL_SIG)
    d.port(cx + 109, 222, "Vout (ΔVout)", side="right", color=COL_SIG)

    # Cascode device M2 (y=272)
    m2 = d.nmos(cx, 272, facing="right", color=COL_BIAS, label="M2 (Cascode)", sub="gm2, gmb2, ro2")
    d.line(cx - 72, 272, m2["g"][0], 272, color=COL_BIAS)
    d.port(cx - 76, 272, "Vb", side="left", color=COL_BIAS)

    # Shielded node X (y=328)
    d.line(cx, m2["s"][1], cx, 360, color=COL_SIG)
    d.dot(cx, 328, COL_AMBER)
    d.line(cx, 328, cx + 95, 328, color=COL_AMBER, dash="4,3")
    d.text(cx + 102, 332, "Node X (Shielded!)", size=11.2, color=COL_AMBER, weight="bold")
    d.text(cx + 102, 347, "ΔVX ≈ ΔVout / (gm2·ro2)", size=10.5, color=COL_MUTED)

    # Input device M1 (y=384)
    m1 = d.nmos(cx, 384, facing="right", color=COL_SIG, label="M1 (Input)", sub="gm1, ro1")
    d.line(cx - 72, 384, m1["g"][0], 384, color=COL_SIG)
    d.port(cx - 76, 384, "Vin", side="left", color=COL_SIG)
    d.line(cx, m1["s"][1], cx, 444)
    d.gnd(cx, 444)

    # Headroom bracket on left side (x=76)
    d.line(88, 222, 88, 444, color=COL_WARN, sw=1.8, dash="4,3")
    d.line(82, 222, 94, 222, color=COL_WARN, sw=1.8)
    d.line(82, 444, 94, 444, color=COL_WARN, sw=1.8)
    d.text(84, 475, "Headroom Cost: Vout,min ≥ VDS,min1 + VDS,min2 = 2·VDS,min",
           size=11, color=COL_WARN, anchor="start", weight="bold")
    d.text(84, 495, "Signal Path: id1 = gm1·Vin flows ~100% through M2 to Vout",
           size=10.8, color=COL_SIG, anchor="start")

    # Right side analytical cards
    d.callout(528, 76, 488, 162, "1. Physical Shielding Mechanism (Razavi §3.6)", [
        "• M2 acts as a Common-Gate current buffer stacked atop M1.",
        "• Looking up from Node X into Source of M2: Zin,s2 ≈ 1/(gm2 + gmb2)",
        "  (when load is resistive; or Rout,load/(gm2*ro2) for high-Z load).",
        "• Large output swing ΔVout is attenuated by ~(gm2 + gmb2)·ro2 at Node X,",
        "  clamping VDS1 constant and suppressing M1 channel-length modulation!",
    ], tone="amber", fs=10.8)

    d.callout(528, 254, 488, 152, "2. Exact & Approximate Output Impedance", [
        "• Treating M1's ro1 as degeneration resistor RS of M2:",
        "  Rout,dn = [1 + (gm2 + gmb2)·ro2]·ro1 + ro2",
        "          ≈ (gm2 + gmb2)·ro2·ro1   ~  gm·ro²",
        "• With cascode PMOS load (Rout,up ~ gm·ro²):",
        "  Intrinsic Voltage Gain: |Av| = Gm·Rout ≈ (1/2)·(gm·ro)²",
    ], tone="sig", fs=10.8)

    d.callout(528, 422, 488, 136, "3. High-Frequency & Noise Bonus (Ch.06 & Ch.07)", [
        "• Eliminates Miller Effect on M1: Av(G1 -> X) ≈ −gm1 / gm2 ≈ −1,",
        "  so Cgd1 is multiplied by only ~2x instead of (1 + gm1·Rout)!",
        "• Low-Freq Noise of M2 is negligible: M2's thermal noise circulates",
        "  locally because ro1 degenerates M2's source by gm2·ro1 >> 1.",
    ], tone="bias", fs=10.8)
    return d


def diag_08_diff_pair_half_circuit():
    d = SVGDoc(
        "diff-pair-half-circuit.svg",
        "Differential Pair, Virtual Ground & DM / CM Half-Circuit Decomposition",
        "Cặp Vi sai Cơ bản, Đất Ảo (Virtual Ground) và Phân rã Nửa mạch Vi sai / Đồng pha (Ch.04 §4.2–4.3)",
        "Ch.04", [4], width=1080, height=590
    )
    # Left Panel: Full Differential Pair
    d.panel(20, 74, 510, 492, "(a) Symmetric Differential Pair with Finite Tail Impedance RSS")
    xl, xr = 195, 355
    pcx = 275
    d.vdd(xl, 136)
    d.vdd(xr, 136)
    rd1 = d.res_v(xl, 180, color=COL_DARK, label="RD", label_side="left")
    rd2 = d.res_v(xr, 180, color=COL_DARK, label="RD", label_side="right")
    d.line(xl, 136, xl, rd1["t"][1])
    d.line(xr, 136, xr, rd2["t"][1])

    # Output nodes
    d.line(xl, rd1["b"][1], xl, 266, color=COL_SIG)
    d.line(xr, rd2["b"][1], xr, 266, color=COL_SIG)
    d.dot(xl, 232, COL_SIG)
    d.dot(xr, 232, COL_SIG)
    d.line(xl - 52, 232, xl, 232, color=COL_SIG)
    d.port(xl - 56, 232, "Vout−", side="left", color=COL_SIG)
    d.line(xr, 232, xr + 52, 232, color=COL_SIG)
    d.port(xr + 56, 232, "Vout+", side="right", color=COL_SIG)

    # M1 (facing right -> gate on left) & M2 (facing left -> gate on right)
    m1 = d.nmos(xl, 290, facing="right", color=COL_SIG, label="M1", label_side="right")
    m2 = d.nmos(xr, 290, facing="left", color=COL_SIG, label="M2", label_side="left")
    d.line(xl - 58, 290, m1["g"][0], 290, color=COL_SIG)
    d.port(xl - 62, 290, "Vin+", side="left", color=COL_SIG)
    d.line(m2["g"][0], 290, xr + 58, 290, color=COL_SIG)
    d.port(xr + 62, 290, "Vin−", side="right", color=COL_SIG)

    # Tail Node P (y=356)
    d.wire([m1["s"], (xl, 356), (xr, 356), m2["s"]], color=COL_DARK)
    d.dot(pcx, 356, COL_AMBER)
    d.text(pcx, 344, "Node P (ΔVP = 0 for DM!)", size=11, color=COL_AMBER, anchor="middle", weight="bold")

    # Parallel ISS & RSS in tail
    d.wire([(pcx, 356), (pcx - 42, 356), (pcx - 42, 386)], color=COL_BIAS)
    d.wire([(pcx, 356), (pcx + 42, 356), (pcx + 42, 386)], color=COL_WARN)
    iss = d.isrc_v(pcx - 42, 410, direction="down", color=COL_BIAS, label="ISS", label_side="left")
    rss = d.res_v(pcx + 42, 410, color=COL_WARN, label="RSS", label_side="right")
    d.wire([iss["b"], (pcx - 42, 456), (pcx + 42, 456), rss["b"]], color=COL_DARK)
    d.dot(pcx, 456, COL_DARK)
    d.gnd(pcx, 456)

    d.text(40, 514, "• Large-Signal Full Tilt: |ΔVin,max| = √2 · Vov = √(4·ISS / (μn·Cox·W/L))", size=10.6, color=COL_DARK)
    d.text(40, 536, "• ICMR:  VGS + VDS,tail  ≤  Vin,CM  ≤  VDD − (ISS/2)·RD + VTH", size=10.6, color=COL_MUTED)

    # Top-Right Panel: DM Half-Circuit
    d.panel(550, 74, 510, 236, "(b) Differential-Mode (DM) Half-Circuit")
    cxd = 675
    d.vdd(cxd, 128)
    rdd = d.res_v(cxd, 166, color=COL_DARK, label="RD", label_side="right")
    d.line(cxd, 128, cxd, rdd["t"][1])
    d.line(cxd, rdd["b"][1], cxd, 214, color=COL_SIG)
    d.dot(cxd, 200, COL_SIG)
    d.line(cxd, 200, cxd + 55, 200, color=COL_SIG)
    d.port(cxd + 59, 200, "−ΔVout/2", side="right", color=COL_SIG)
    md = d.nmos(cxd, 238, facing="right", color=COL_SIG, label="M1", label_side="right")
    d.line(cxd - 54, 238, md["g"][0], 238, color=COL_SIG)
    d.port(cxd - 58, 238, "+Vid/2", side="left", color=COL_SIG)
    d.line(cxd, md["s"][1], cxd, 276)
    d.gnd(cxd, 276)
    d.text(cxd + 16, 282, "AC Virtual GND", size=10.2, color=COL_AMBER, weight="bold")

    d.callout(805, 118, 240, 172, "DM Gain", [
        "Symmetry forces ΔVP = 0:",
        "• Tail RSS carries 0 AC current",
        "• Adm = Vout,dm / Vid",
        "      = −gm1 · (RD || ro1)",
        "• Independent of RSS!",
    ], tone="sig", fs=10.6)

    # Bottom-Right Panel: CM Half-Circuit
    d.panel(550, 326, 510, 240, "(c) Common-Mode (CM) Half-Circuit")
    cxc = 675
    d.vdd(cxc, 376)
    rdc = d.res_v(cxc, 412, color=COL_DARK, label="RD", label_side="right")
    d.line(cxc, 376, cxc, rdc["t"][1])
    d.line(cxc, rdc["b"][1], cxc, 444, color=COL_WARN)
    mc = d.nmos(cxc, 468, facing="right", color=COL_WARN, label="M1", label_side="right")
    d.line(cxc - 54, 468, mc["g"][0], 468, color=COL_WARN)
    d.port(cxc - 58, 468, "ΔVin,CM", side="left", color=COL_WARN)
    rs_cm = d.res_v(cxc, 520, color=COL_WARN, label="2·RSS", label_side="right")
    d.line(cxc, mc["s"][1], cxc, rs_cm["t"][1], color=COL_WARN)
    d.gnd(cxc, rs_cm["b"][1])

    d.callout(795, 366, 250, 184, "CM Gain & CMRR (§4.3)", [
        "RSS splits into two parallel 2·RSS:",
        "• Acm ≈ −RD / [1/gm1 + 2·RSS]",
        "• If ΔRD mismatch -> Acm-dm ≠ 0!",
        "• CMRR = |Adm / Acm-dm|",
        "  ≈ (gm1·RD / ΔRD)·(1 + 2·gm1·RSS)",
    ], tone="warn", fs=10.5)
    return d


def diag_09_gilbert_cell():
    d = SVGDoc(
        "gilbert-cell.svg",
        "Gilbert Variable-Gain Amplifier & Four-Quadrant Multiplier Cell",
        "Ô nhân Tương tự Bốn Góc phần tư / Khuếch đại Độ lợi Biến thiên Gilbert (Ch.04 §4.5)",
        "Ch.04", [4], width=1040, height=600
    )
    d.panel(22, 74, 610, 502, "CMOS Gilbert Cell Topology (Current-Steering Quad + Gm Pair)")

    # Coordinates for switching quad M3, M4 (left pair) & M5, M6 (right pair)
    x_m3, x_m4 = 200, 290
    x_m5, x_m6 = 380, 470
    x_l_load, x_r_load = 230, 440

    d.vdd(x_l_load, 132)
    d.vdd(x_r_load, 132)
    rd_l = d.res_v(x_l_load, 174, color=COL_DARK, label="RD", label_side="left")
    rd_r = d.res_v(x_r_load, 174, color=COL_DARK, label="RD", label_side="right")
    d.line(x_l_load, 132, x_l_load, rd_l["t"][1])
    d.line(x_r_load, 132, x_r_load, rd_r["t"][1])

    # Output cross-summing buses:
    # Left bus y=214 connects RD_left, M3_drain (200), and M5_drain (380) -> Vout-
    # Right bus y=230 connects RD_right, M4_drain (290), and M6_drain (470) -> Vout+
    y_bus_l, y_bus_r = 214, 230
    d.line(125, y_bus_l, x_m5, y_bus_l, color=COL_SIG)
    d.port(121, y_bus_l, "Vout−", side="left", color=COL_SIG)
    d.line(x_l_load, rd_l["b"][1], x_l_load, y_bus_l, color=COL_SIG)
    d.dot(x_l_load, y_bus_l, COL_SIG)
    d.dot(x_m3, y_bus_l, COL_SIG)

    d.line(x_m4, y_bus_r, 545, y_bus_r, color=COL_SIG)
    d.port(549, y_bus_r, "Vout+", side="right", color=COL_SIG)
    d.line(x_r_load, rd_r["b"][1], x_r_load, y_bus_r, color=COL_SIG)
    d.dot(x_r_load, y_bus_r, COL_SIG)
    d.dot(x_m6, y_bus_r, COL_SIG)

    # Switching Quad Transistors at y=288
    # M3 (facing right, gate at 170), M4 (facing left, gate at 320)
    # M5 (facing right, gate at 350), M6 (facing left, gate at 500)
    m3 = d.nmos(x_m3, 288, facing="right", color=COL_AMBER, label="M3", label_side="right")
    m4 = d.nmos(x_m4, 288, facing="left",  color=COL_AMBER, label="M4", label_side="left")
    m5 = d.nmos(x_m5, 288, facing="right", color=COL_AMBER, label="M5", label_side="right")
    m6 = d.nmos(x_m6, 288, facing="left",  color=COL_AMBER, label="M6", label_side="left")

    # Connect drains to output buses
    d.line(x_m3, y_bus_l, x_m3, m3["d"][1], color=COL_SIG)
    d.line(x_m5, y_bus_l, x_m5, m5["d"][1], color=COL_SIG)
    d.line(x_m4, y_bus_r, x_m4, m4["d"][1], color=COL_SIG)
    d.line(x_m6, y_bus_r, x_m6, m6["d"][1], color=COL_SIG)

    # Inner gates M4 (320) & M5 (350) tied together -> Vctrl- (V2-)
    d.line(m4["g"][0], 288, m5["g"][0], 288, color=COL_AMBER)
    d.dot(335, 288, COL_AMBER)
    d.wire([(335, 288), (335, 252)], color=COL_AMBER)
    d.port(335, 248, "V2−", side="top", color=COL_AMBER)

    # Outer gates M3 (170) & M6 (500) driven by V2+
    d.line(125, 288, m3["g"][0], 288, color=COL_AMBER)
    d.port(121, 288, "V2+", side="left", color=COL_AMBER)
    d.line(m6["g"][0], 288, 545, 288, color=COL_AMBER)
    d.port(549, 288, "V2+", side="right", color=COL_AMBER)

    # Source junctions of upper pairs -> drains of M1 (245) & M2 (425) at y=346
    d.wire([m3["s"], (x_m3, 346), (x_m4, 346), m4["s"]], color=COL_SIG)
    d.dot(245, 346, COL_SIG)
    d.wire([m5["s"], (x_m5, 346), (x_m6, 346), m6["s"]], color=COL_SIG)
    d.dot(425, 346, COL_SIG)

    # Bottom Gm Pair M1 (245, y=402) & M2 (425, y=402)
    m1 = d.nmos(245, 402, facing="right", color=COL_SIG, label="M1", sub="ID1", label_side="right")
    m2 = d.nmos(425, 402, facing="left",  color=COL_SIG, label="M2", sub="ID2", label_side="left")
    d.line(245, 346, 245, m1["d"][1], color=COL_SIG)
    d.line(425, 346, 425, m2["d"][1], color=COL_SIG)

    d.line(155, 402, m1["g"][0], 402, color=COL_SIG)
    d.port(151, 402, "V1+", side="left", color=COL_SIG)
    d.line(m2["g"][0], 402, 515, 402, color=COL_SIG)
    d.port(519, 402, "V1−", side="right", color=COL_SIG)

    # Tail current source ISS
    d.wire([m1["s"], (245, 458), (425, 458), m2["s"]], color=COL_DARK)
    d.dot(335, 458, COL_BIAS)
    iss = d.isrc_v(335, 498, direction="down", color=COL_BIAS, label="ISS", label_side="right")
    d.line(335, 458, 335, iss["t"][1], color=COL_BIAS)
    d.gnd(335, iss["b"][1] + 6)
    d.line(335, iss["b"][1], 335, iss["b"][1] + 6)

    # Right side operating principles
    d.callout(652, 84, 366, 226, "1. Variable-Gain & Polarity Reversal (§4.5)", [
        "• Bottom pair M1–M2 converts V1 = V1+ − V1−",
        "  into differential current: ΔI = ID1 − ID2 ≈ gm1·V1.",
        "• Upper quad M3–M6 steers ID1 & ID2 according",
        "  to control voltage V2 = V2+ − V2−:",
        "  - V2 >> +√2·Vov: M3, M6 ON -> Av > 0 (max +gain)",
        "  - V2 = 0: currents cancel equally -> Av = 0!",
        "  - V2 << −√2·Vov: M4, M5 ON -> Av < 0 (polarity flip!)",
    ], tone="amber", fs=10.7)

    d.callout(652, 330, 366, 240, "2. Small-Signal Multiplier Law & Headroom", [
        "• Small V1 & V2 four-quadrant product:",
        "  Vout = (Vout+ − Vout−) ≈ μn·Cox·(W/L)·RD · V1 · V2",
        "• Applications: VGA / AGC, RF Mixers, Phase",
        "  Detectors (Ch.16), Analog Multipliers.",
        "",
        "• Headroom Stack Penalty (3 stacked tiers):",
        "  VCM2 ≥ VCM1 + VGS,quad − VTH1",
        "  VDD ≥ RD·(ISS/2) + 2·VDS,min + VDS,tail",
    ], tone="sig", fs=10.7)
    return d


def diag_10_current_mirrors_evolution():
    d = SVGDoc(
        "current-mirrors-evolution.svg",
        "Current Mirror Evolution: Basic -> Cascode -> Low-Voltage Wide-Swing (LVCCML)",
        "Tiến hóa Gương dòng: Cơ bản -> Cascode -> Cascode Điện áp thấp Dải rộng LVCCML (Ch.05 §5.1–5.2)",
        "Ch.05", [5], width=1080, height=600
    )
    d.panel(18,  74, 310, 502, "(a) Basic Current Mirror")
    d.panel(344, 74, 336, 502, "(b) Standard Cascode Mirror")
    d.panel(696, 74, 366, 502, "(c) Low-Voltage Wide-Swing (LVCCML)")

    # --- (a) Basic Mirror ---
    x1a, x2a = 105, 235
    d.vdd(x1a, 136)
    iref1 = d.isrc_v(x1a, 184, direction="down", color=COL_BIAS, label="IREF", label_side="left")
    d.line(x1a, 136, x1a, iref1["t"][1], color=COL_BIAS)

    m1a = d.nmos(x1a, 350, facing="left", color=COL_BIAS, label="M1", label_side="left")
    m2a = d.nmos(x2a, 350, facing="right", color=COL_SIG, label="M2", sub="ro2", label_side="right")
    d.line(x1a, iref1["b"][1], x1a, m1a["d"][1], color=COL_BIAS)
    # Gate tie & diode connection
    d.line(m1a["g"][0], 350, m2a["g"][0], 350, color=COL_BIAS)
    d.wire([(x1a, 304), (x1a + 44, 304), (x1a + 44, 350)], color=COL_BIAS)
    d.dot(x1a, 304, COL_BIAS)
    d.dot(x1a + 44, 350, COL_BIAS)

    # Output port
    d.line(x2a, 240, x2a, m2a["d"][1], color=COL_SIG)
    d.port(x2a, 236, "Iout (Vout)", side="top", color=COL_SIG)
    d.gnd(x1a, m1a["s"][1] + 12)
    d.line(x1a, m1a["s"][1], x1a, m1a["s"][1] + 12)
    d.gnd(x2a, m2a["s"][1] + 12)
    d.line(x2a, m2a["s"][1], x2a, m2a["s"][1] + 12)

    d.callout(32, 434, 282, 126, "Headroom = 1·VDS,min", [
        "• Vout,min = VDS,min2  (Wide swing)",
        "• Rout = ro2  (Low!)",
        "• Fatal CLM Error when Vout ≠ VGS1:",
        "  ΔI/I ≈ λ · (Vout − VGS1)",
    ], tone="neutral", fs=10.4)

    # --- (b) Standard Cascode Mirror ---
    x1b, x2b = 438, 582
    d.vdd(x1b, 128)
    iref2 = d.isrc_v(x1b, 168, direction="down", color=COL_BIAS, label="IREF", label_side="left")
    d.line(x1b, 128, x1b, iref2["t"][1], color=COL_BIAS)

    m3b = d.nmos(x1b, 260, facing="left", color=COL_BIAS, label="M3", label_side="left")
    m4b = d.nmos(x2b, 260, facing="right", color=COL_SIG, label="M4", label_side="right")
    m1b = d.nmos(x1b, 358, facing="left", color=COL_BIAS, label="M1", label_side="left")
    m2b = d.nmos(x2b, 358, facing="right", color=COL_SIG, label="M2", label_side="right")

    d.line(x1b, iref2["b"][1], x1b, m3b["d"][1], color=COL_BIAS)
    d.line(x1b, m3b["s"][1], x1b, m1b["d"][1], color=COL_BIAS)
    d.line(x2b, m4b["s"][1], x2b, m2b["d"][1], color=COL_SIG)
    d.line(x2b, 208, x2b, m4b["d"][1], color=COL_SIG)
    d.port(x2b, 204, "Iout (Vout)", side="top", color=COL_SIG)

    # Diode stack connections (both M3 and M1 diode connected!)
    d.line(m3b["g"][0], 260, m4b["g"][0], 260, color=COL_BIAS)
    d.wire([(x1b, 218), (x1b + 44, 218), (x1b + 44, 260)], color=COL_BIAS)
    d.dot(x1b, 218, COL_BIAS)
    d.dot(x1b + 44, 260, COL_BIAS)

    d.line(m1b["g"][0], 358, m2b["g"][0], 358, color=COL_BIAS)
    d.wire([(x1b, 316), (x1b + 44, 316), (x1b + 44, 358)], color=COL_BIAS)
    d.dot(x1b, 316, COL_BIAS)
    d.dot(x1b + 44, 358, COL_BIAS)

    # Highlight wasted VTH at node Y
    d.dot(x2b, 316, COL_WARN)
    d.text(x2b + 8, 314, "VY = VTH+Vov!", size=10.2, color=COL_WARN, weight="bold")

    d.gnd(x1b, m1b["s"][1] + 10)
    d.line(x1b, m1b["s"][1], x1b, m1b["s"][1] + 10)
    d.gnd(x2b, m2b["s"][1] + 10)
    d.line(x2b, m2b["s"][1], x2b, m2b["s"][1] + 10)

    d.callout(358, 434, 308, 126, "TRAP: Wastes VTH Headroom!", [
        "• Rout ≈ gm4·ro4·ro2  (High!)",
        "• VN = VGS3 + VGS1 = 2VTH + 2Vov",
        "• Vout,min = VTH + 2·Vov  (Razavi §5.2)",
        "  Loses a full VTH (~0.4–0.6V) of swing!",
    ], tone="warn", fs=10.4)

    # --- (c) Low-Voltage Wide-Swing Cascode Mirror (LVCCML) ---
    xb_bias, x1c, x2c = 762, 875, 992
    d.vdd(xb_bias, 128)
    d.vdd(x1c, 128)
    ib = d.isrc_v(xb_bias, 168, direction="down", color=COL_AMBER, label="Ib", label_side="left")
    iref3 = d.isrc_v(x1c, 168, direction="down", color=COL_BIAS, label="IREF", label_side="left")
    d.line(xb_bias, 128, xb_bias, ib["t"][1], color=COL_AMBER)
    d.line(x1c, 128, x1c, iref3["t"][1], color=COL_BIAS)

    # Bias generator transistor Mb sized (1/4)(W/L) -> VGSb = VTH + 2*Vov = Vb!
    mb = d.nmos(xb_bias, 310, facing="left", color=COL_AMBER, label="Mb", sub="W/4L", label_side="left")
    d.line(xb_bias, ib["b"][1], xb_bias, mb["d"][1], color=COL_AMBER)
    d.wire([(xb_bias, 232), (xb_bias + 30, 232), (xb_bias + 30, 310)], color=COL_AMBER)
    d.dot(xb_bias, 232, COL_AMBER)
    d.dot(xb_bias + 30, 310, COL_AMBER)
    d.gnd(xb_bias, mb["s"][1] + 58)
    d.line(xb_bias, mb["s"][1], xb_bias, mb["s"][1] + 58)

    m3c = d.nmos(x1c, 260, facing="left", color=COL_BIAS, label="M3", label_side="left")
    m4c = d.nmos(x2c, 260, facing="right", color=COL_SIG, label="M4", label_side="right")
    m1c = d.nmos(x1c, 358, facing="left", color=COL_BIAS, label="M1", label_side="left")
    m2c = d.nmos(x2c, 358, facing="right", color=COL_SIG, label="M2", label_side="right")

    d.line(x1c, iref3["b"][1], x1c, m3c["d"][1], color=COL_BIAS)
    d.line(x1c, m3c["s"][1], x1c, m1c["d"][1], color=COL_BIAS)
    d.line(x2c, m4c["s"][1], x2c, m2c["d"][1], color=COL_SIG)
    d.line(x2c, 208, x2c, m4c["d"][1], color=COL_SIG)
    d.port(x2c, 204, "Iout", side="top", color=COL_SIG)

    # Vb = VGS + Vov feeds gates of M3 & M4!
    d.wire([(xb_bias + 30, 260), m3c["g"], m4c["g"]], color=COL_AMBER)
    d.dot(xb_bias + 30, 260, COL_AMBER)
    d.dot(m3c["g"][0], 260, COL_AMBER)
    d.text((m3c["g"][0] + m4c["g"][0]) / 2, 250, "Vb = VGS+Vov", size=10.2,
           color=COL_AMBER, anchor="middle", weight="bold")

    # Drain of M3 feeds gates of M1 & M2!
    d.wire([(x1c, 214), (x1c + 52, 214), (x1c + 52, 358)], color=COL_BIAS)
    d.line(m1c["g"][0], 358, m2c["g"][0], 358, color=COL_BIAS)
    d.dot(x1c, 214, COL_BIAS)
    d.dot(x1c + 52, 358, COL_BIAS)

    d.gnd(x1c, m1c["s"][1] + 10)
    d.line(x1c, m1c["s"][1], x1c, m1c["s"][1] + 10)
    d.gnd(x2c, m2c["s"][1] + 10)
    d.line(x2c, m2c["s"][1], x2c, m2c["s"][1] + 10)

    d.callout(710, 434, 338, 126, "OPTIMAL: Vout,min = 2·VDS,min!", [
        "• VDS1 = VDS2 = Vb − VGS3 = VDS,min",
        "• Recovers full VTH headroom: Vout,min = 2·Vov!",
        "• Keeps full Rout ≈ gm4·ro4·ro2 & tight VDS match",
        "• Workhorse mirror in 90nm / 65nm / 45nm IC!",
    ], tone="bias", fs=10.4)
    return d


def diag_11_five_transistor_ota():
    d = SVGDoc(
        "five-transistor-ota.svg",
        "Five-Transistor OTA (Diff-Pair with Active Current-Mirror Load)",
        "Mạch Khuếch đại Hỗ dẫn 5 Transistor (5T-OTA: Cặp Vi sai Tải Gương dòng Tích cực — Ch.04 & Ch.05 §5.3)",
        "Ch.04 & 05", [4, 5], width=1040, height=580
    )
    d.panel(22, 74, 545, 484, "5T-OTA Schematic & Small-Signal Current Recombination")

    xl, xr = 205, 375
    cx = 290
    d.vdd(xl, 134)
    d.vdd(xr, 134)

    # PMOS Active Mirror Load: M3 (diode-connected on left, facing left -> gate right)
    # M4 (mirror output on right, facing right -> gate left)
    m3 = d.pmos(xl, 196, facing="left", color=COL_BIAS, label="M3", sub="Diode Load", label_side="left")
    m4 = d.pmos(xr, 196, facing="right", color=COL_BIAS, label="M4", sub="ro4", label_side="right")
    d.line(xl, 134, xl, m3["s"][1])
    d.line(xr, 134, xr, m4["s"][1])
    d.line(m3["g"][0], 196, m4["g"][0], 196, color=COL_BIAS)
    # Diode tie on M3
    d.wire([(xl, 238), (xl + 42, 238), (xl + 42, 196)], color=COL_BIAS)
    d.dot(xl, 238, COL_BIAS)
    d.dot(xl + 42, 196, COL_BIAS)
    d.text(cx, 184, "Mirror Node X", size=10.6, color=COL_BIAS, anchor="middle", weight="bold")

    # Output node on right branch (y=264)
    d.line(xl, m3["d"][1], xl, 296, color=COL_BIAS)
    d.line(xr, m4["d"][1], xr, 296, color=COL_SIG)
    d.dot(xr, 264, COL_SIG)
    d.line(xr, 264, xr + 95, 264, color=COL_SIG)
    d.port(xr + 99, 264, "Vout", side="right", color=COL_SIG)

    # Small-signal current annotations on branches
    d.arrow(xl - 16, 250, xl - 16, 286, color=COL_BIAS, sw=1.7)
    d.text(xl - 22, 272, "+gm1·Vid/2", size=10.3, color=COL_BIAS, anchor="end", weight="bold")
    d.arrow(xr + 16, 224, xr + 16, 256, color=COL_BIAS, sw=1.7)
    d.text(xr + 22, 242, "+gm1·Vid/2", size=10.3, color=COL_BIAS, anchor="start", weight="bold")
    d.arrow(xr - 16, 294, xr - 16, 268, color=COL_SIG, sw=1.7)
    d.text(xr - 22, 286, "−gm2·Vid/2", size=10.3, color=COL_SIG, anchor="end", weight="bold")

    # NMOS Input Differential Pair M1 & M2 (y=320)
    m1 = d.nmos(xl, 320, facing="right", color=COL_SIG, label="M1", sub="gm1, ro1", label_side="right")
    m2 = d.nmos(xr, 320, facing="left",  color=COL_SIG, label="M2", sub="gm2, ro2", label_side="left")
    d.line(xl - 68, 320, m1["g"][0], 320, color=COL_SIG)
    d.port(xl - 72, 320, "Vin−", side="left", color=COL_SIG)
    d.line(m2["g"][0], 320, xr + 68, 320, color=COL_SIG)
    d.port(xr + 72, 320, "Vin+", side="right", color=COL_SIG)
    # Wait: let's double-check Vin+ and Vin- polarity!
    # When M1 gate rises (+Vid/2), ID1 increases -> M3 pulls more -> M4 pushes UP into Vout -> Vout RISES!
    # Wait: YES!! Look at that: if M1 gate rises, ID1 rises -> M3 drain current rises -> M4 pushes current INTO Vout!
    # Meanwhile M2 gate falls (-Vid/2) -> ID2 decreases -> Vout RISES by BOTH halves!
    # Therefore M1 (diode side) IS THE NON-INVERTING INPUT Vin+, and M2 (output side) IS THE INVERTING INPUT Vin-!!
    # Let's fix those two labels right here before even saving! What an awesome catch!
    d.elements = d.elements[:-4]
    d.line(xl - 68, 320, m1["g"][0], 320, color=COL_SIG)
    d.port(xl - 72, 320, "Vin+", side="left", color=COL_SIG)
    d.line(m2["g"][0], 320, xr + 68, 320, color=COL_SIG)
    d.port(xr + 72, 320, "Vin−", side="right", color=COL_SIG)

    # Tail Node P & Tail Transistor M5 (y=424)
    d.wire([m1["s"], (xl, 376), (xr, 376), m2["s"]], color=COL_DARK)
    d.dot(cx, 376, COL_DARK)
    m5 = d.nmos(cx, 424, facing="right", color=COL_BIAS, label="M5 (ISS)", sub="RSS = ro5", label_side="right")
    d.line(cx, 376, cx, m5["d"][1])
    d.line(cx - 72, 424, m5["g"][0], 424, color=COL_BIAS)
    d.port(cx - 76, 424, "Vb", side="left", color=COL_BIAS)
    d.line(cx, m5["s"][1], cx, 476)
    d.gnd(cx, 476)

    d.text(42, 524, "Polarity Rule: M1 (mirror-ref side) = Vin+ ; M2 (output side) = Vin−",
           size=11, color=COL_DARK, weight="bold")
    d.text(42, 544, "Total short-circuit Gm = gm1/2 (mirror) + gm2/2 (direct) = gm1 !",
           size=10.8, color=COL_SIG)

    # Right Analytical Callouts
    d.callout(586, 76, 432, 162, "1. Small-Signal Gain & Output Impedance (§5.3.2)", [
        "• By inspection (valid since RSS = ro5 >> 1/gm3):",
        "  Gm = gm1 ,   Rout ≈ ro2 || ro4",
        "  Adm = Vout / (Vin+ − Vin−) ≈ gm1 · (ro2 || ro4)",
        "• Achieves FULL gm1·(ro2||ro4) differential-to-single-ended",
        "  gain without wasting half the signal current!",
    ], tone="sig", fs=10.7)

    d.callout(586, 252, 432, 150, "2. ICMR, Output Swing & Asymmetric Clipping", [
        "• Output Swing: VCM_in − VTH1 ≤ Vout ≤ VDD − |VDS,min4|",
        "  (Limited by M2 entering triode if Vout drops too low!)",
        "• ICMR: VGS1 + VDS,min5 ≤ Vin,CM ≤ VDD − |VGS3| + VTH1",
        "• Asymmetry: Node X sits at VDD−|VGS3|; Vout can swing wider.",
    ], tone="amber", fs=10.7)

    d.callout(586, 416, 432, 142, "3. CMRR & Noise Design Rules (Ch.05 & Ch.07)", [
        "• Finite ro5 + mirror impedance asymmetry degrades CMRR:",
        "  CMRR ≈ 2 · gm1 · ro5 · (gm3 · (ro1 || ro3))",
        "• Noise: M3 & M4 inject thermal & 1/f noise directly:",
        "  Vn,in² = 8kTγ·(1/gm1 + gm3/gm1²) -> Make gm3 << gm1!",
    ], tone="warn", fs=10.7)
    return d


def diag_12_miller_effect_rhp_zero():
    d = SVGDoc(
        "miller-effect-rhp-zero.svg",
        "CS Stage with Floating Cgd: Miller Multiplication & RHP Zero",
        "Tầng CS có Tụ nối chéo Cgd: Hiệu ứng Nhân tụ Miller và Zero Nửa mặt phẳng Phải (Ch.06 §6.1–6.2)",
        "Ch.06", [6], width=1060, height=580
    )
    d.panel(20,  74, 505, 484, "(a) Physical CS Stage & Feedforward RHP Zero Path")
    d.panel(545, 74, 495, 484, "(b) Miller Input / Output Decoupled Approximation")

    # --- (a) Physical CS with Cgd ---
    cx1 = 315
    d.vdd(cx1, 134)
    rd = d.res_v(cx1, 178, color=COL_DARK, label="RD", label_side="right")
    d.line(cx1, 134, cx1, rd["t"][1])

    # Input Vin -> RS -> Node X (285)
    d.port(66, 295, "Vin", side="left", color=COL_SIG)
    rs = d.res_h(126, 295, color=COL_SIG, label="RS", label_pos="top")
    d.line(70, 295, rs["l"][0], 295, color=COL_SIG)
    d.line(rs["r"][0], 295, cx1 - 30, 295, color=COL_SIG)
    d.dot(186, 295, COL_SIG)
    d.dot(225, 295, COL_WARN)
    d.text(204, 313, "VX", size=10.8, color=COL_SIG, weight="bold")

    # Cgs at input (x=186)
    cgs = d.cap_v(186, 355, color=COL_DARK, label="Cgs", label_side="left")
    d.line(186, 295, 186, cgs["t"][1])
    d.gnd(186, cgs["b"][1] + 8)
    d.line(186, cgs["b"][1], 186, cgs["b"][1] + 8)

    # Floating Cgd bridge from X (225, 295) to Y (cx1, 232)
    d.wire([(225, 295), (225, 232), (242, 232)], color=COL_WARN, sw=2.2)
    cgd = d.cap_h(260, 232, color=COL_WARN, label="Cgd", label_pos="top")
    d.line(cgd["r"][0], 232, cx1, 232, color=COL_WARN, sw=2.2)
    d.dot(cx1, 232, COL_WARN)
    d.arrow(232, 212, 292, 212, color=COL_WARN, sw=1.8)
    d.text(262, 202, "ifwd = s·Cgd·VX", size=10.3, color=COL_WARN, anchor="middle", weight="bold")

    # M1 & Output Vout + CL
    m1 = d.nmos(cx1, 295, facing="right", color=COL_SIG, label="M1", sub="id = gm1·VX")
    d.line(cx1, rd["b"][1], cx1, m1["d"][1], color=COL_SIG)
    d.dot(cx1, 252, COL_SIG)
    d.line(cx1, 252, 438, 252, color=COL_SIG)
    d.port(442, 252, "Vout", side="right", color=COL_SIG)
    d.dot(405, 252, COL_DARK)
    cl = d.cap_v(405, 340, color=COL_DARK, label="CL + Cdb", label_side="right")
    d.line(405, 252, 405, cl["t"][1])
    d.gnd(405, cl["b"][1] + 10)
    d.line(405, cl["b"][1], 405, cl["b"][1] + 10)

    d.line(cx1, m1["s"][1], cx1, 376)
    d.gnd(cx1, 376)

    d.callout(38, 418, 468, 126, "Origin of Right-Half-Plane (RHP) Zero (Eq. 6.32)", [
        "• At s = ωz = +gm1 / Cgd, feedforward current s·Cgd·VX equals",
        "  drain current gm1·VX -> net current into RD||CL vanishes (Vout=0)!",
        "• Transfer Numerator:  1 − s · (Cgd / gm1)  ->  ωz = +gm1 / Cgd",
        "• RHP Zero boosts magnitude (+20 dB/dec) while LAGGING phase (−90°)!",
    ], tone="warn", fs=10.5)

    # --- (b) Miller Equivalent ---
    # Input port side
    d.port(585, 232, "Vin", side="left", color=COL_SIG)
    rs2 = d.res_h(642, 232, color=COL_SIG, label="RS", label_pos="top")
    d.line(589, 232, rs2["l"][0], 232, color=COL_SIG)
    d.line(rs2["r"][0], 232, 725, 232, color=COL_SIG)
    d.dot(705, 232, COL_AMBER)
    cin_m = d.cap_v(705, 296, color=COL_AMBER, label="Cin,eq",
                    sub="Cgs+(1+gm1·RD)Cgd", label_side="left")
    d.line(705, 232, 705, cin_m["t"][1], color=COL_AMBER)
    d.gnd(705, cin_m["b"][1] + 10)
    d.line(705, cin_m["b"][1], 705, cin_m["b"][1] + 10)

    # Output port side
    gm_eq = d.dep_isrc_v(855, 296, direction="down", color=COL_SIG, label="gm1·VX", label_side="left")
    rd_eq = d.res_v(920, 296, color=COL_DARK, label="RD", label_side="left")
    cout_m = d.cap_v(975, 296, color=COL_AMBER, label="Cout,eq", label_side="left")
    d.line(855, 232, 998, 232, color=COL_SIG)
    d.port(1002, 232, "Vout", side="right", color=COL_SIG)
    d.dot(920, 232, COL_DARK)
    d.dot(975, 232, COL_AMBER)
    d.line(855, 232, 855, gm_eq["t"][1], color=COL_SIG)
    d.line(920, 232, 920, rd_eq["t"][1])
    d.line(975, 232, 975, cout_m["t"][1], color=COL_AMBER)
    d.wire([gm_eq["b"], (855, 344), (975, 344), (975, cout_m["b"][1])], color=COL_DARK)
    d.line(920, rd_eq["b"][1], 920, 344)
    d.dot(920, 344, COL_DARK)
    d.gnd(920, 344)

    d.callout(562, 390, 462, 154, "Miller vs Exact Two-Pole Analysis (§6.2)", [
        "• Miller Input Pole: ωp,in ≈ 1 / [RS · (Cgs + (1 + gm1·RD)Cgd)]",
        "• Exact Dominant Pole (ZVTC / Denominator D(s)):",
        "  ωp1 ≈ 1 / [RS(Cgs + (1+gm1·RD)Cgd) + RD(Cgd + CL)]",
        "• Caveat: Miller misses RD·CL term when RS is small AND",
        "  completely hides the RHP zero +gm1/Cgd & pole-splitting!",
    ], tone="amber", fs=10.5)
    return d


# ==============================================================================
# PART 3: DIAGRAMS 13 - 25 (Mirror Doublet, Noise, Feedback, Op-Amps, Comp, Bias)
# ==============================================================================

def diag_13_diffpair_mirror_pole_doublet():
    d = SVGDoc(
        "diffpair-mirror-pole-doublet.svg",
        "Active-Load Diff-Pair: Mirror Pole ωm & Pole-Zero Doublet",
        "Cặp Vi sai Tải Tích cực: Cực Nút Gương ωm và Cặp Cực–Zero Sát nhau (Doublet — Ch.06 §6.6)",
        "Ch.06", [6], width=1060, height=580
    )
    d.panel(20,  74, 520, 484, "(a) Fast Direct Path vs Slow Mirror Path (CX)")
    d.panel(558, 74, 482, 484, "(b) Doublet (ωm, 2·ωm) & Slow Settling Tail")

    # --- (a) Schematic ---
    xl, xr = 195, 385
    cx = 290
    d.vdd(xl, 134)
    d.vdd(xr, 134)
    m3 = d.pmos(xl, 196, facing="left",  color=COL_AMBER, label="M3", sub="1/gm3", label_side="left")
    m4 = d.pmos(xr, 196, facing="right", color=COL_AMBER, label="M4", sub="gm4=gm3", label_side="right")
    d.line(xl, 134, xl, m3["s"][1])
    d.line(xr, 134, xr, m4["s"][1])
    d.line(m3["g"][0], 196, m4["g"][0], 196, color=COL_AMBER)
    d.wire([(xl, 238), (xl + 40, 238), (xl + 40, 196)], color=COL_AMBER)
    d.dot(xl, 238, COL_AMBER)
    d.dot(xl + 40, 196, COL_AMBER)
    d.dot(cx, 196, COL_WARN)

    # Mirror node capacitance CX to VDD/AC-GND
    cx_cap = d.cap_v(cx, 142, color=COL_WARN, label="CX ≈ 2·Cgs3", label_side="right")
    d.line(cx, 196, cx, cx_cap["b"][1], color=COL_WARN)
    d.vdd(cx, cx_cap["t"][1], label="AC GND", color=COL_WARN)

    # Output node & CL
    d.line(xl, m3["d"][1], xl, 304, color=COL_AMBER)
    d.line(xr, m4["d"][1], xr, 304, color=COL_SIG)
    d.dot(xr, 266, COL_SIG)
    d.line(xr, 266, 488, 266, color=COL_SIG)
    d.port(492, 266, "Vout", side="right", color=COL_SIG)
    d.dot(472, 266, COL_DARK)
    cl = d.cap_v(472, 392, color=COL_DARK, label="CL", label_side="right")
    d.line(472, 266, 472, cl["t"][1])
    d.gnd(472, cl["b"][1] + 8)
    d.line(472, cl["b"][1], 472, cl["b"][1] + 8)

    # Input pair M1 & M2
    m1 = d.nmos(xl, 328, facing="right", color=COL_AMBER, label="M1", sub="Slow Half", label_side="right")
    m2 = d.nmos(xr, 328, facing="left",  color=COL_SIG,   label="M2", sub="Fast Half", label_side="left")
    d.line(xl - 64, 328, m1["g"][0], 328, color=COL_AMBER)
    d.port(xl - 68, 328, "Vin+", side="left", color=COL_AMBER)
    d.line(m2["g"][0], 328, xr + 38, 328, color=COL_SIG)
    d.port(xr + 42, 328, "Vin−", side="right", color=COL_SIG)

    d.wire([m1["s"], (xl, 384), (xr, 384), m2["s"]], color=COL_DARK)
    d.dot(cx, 384, COL_BIAS)
    iss = d.isrc_v(cx, 422, direction="down", color=COL_BIAS, label="ISS", label_side="right")
    d.line(cx, 384, cx, iss["t"][1])
    d.gnd(cx, iss["b"][1] + 6)
    d.line(cx, iss["b"][1], cx, iss["b"][1] + 6)

    d.callout(38, 468, 484, 76, "Two Parallel Feedforward Paths", [
        "• Path 1 (Slow, Amber): M1 -> Node X (pole ωm = gm3/CX) -> M4 -> Vout",
        "• Path 2 (Fast, Blue):  M2 -> directly drives Vout (bypasses Node X!)",
    ], tone="amber", fs=10.5)

    # --- (b) Bode & Step Settling ---
    bx0, by0 = d.axes(598, 128, 392, 165, xlabel="log ω", ylabel="|H(jω)| [dB]")
    # Bode curve showing dominant pole wp1, mirror pole wm, and zero 2*wm
    d.wire([
        (bx0, 146), (bx0 + 95, 146),
        (bx0 + 215, 224),   # -20 dB/dec after wp1
        (bx0 + 265, 272),   # -40 dB/dec between wm and 2*wm
        (bx0 + 370, 340 - 65),  # returns to -20 dB/dec after wz = 2*wm
    ], color=COL_SIG, sw=2.4)
    d.dot(bx0 + 95, 146, COL_DARK)
    d.text(bx0 + 95, 136, "ωp1", size=10.5, color=COL_DARK, anchor="middle", weight="bold")
    d.dot(bx0 + 215, 224, COL_WARN)
    d.text(bx0 + 205, 214, "ωm", size=10.5, color=COL_WARN, anchor="end", weight="bold")
    d.dot(bx0 + 265, 272, COL_BIAS)
    d.text(bx0 + 275, 266, "ωz = 2·ωm", size=10.5, color=COL_BIAS, anchor="start", weight="bold")

    # Step settling plot below
    sx0, sy0 = d.axes(598, 340, 392, 95, xlabel="Time t", ylabel="Vout(t)")
    d.line(sx0, 355, sx0 + 385, 355, color=COL_SUBTLE, sw=1.2, dash="4,4")
    # Ideal single-pole fast step (dashed blue) vs doublet slow tail (solid red)
    d.path(f"M {sx0} {sy0} Q {sx0 + 48} 356 {sx0 + 130} 355 L {sx0 + 380} 355",
           stroke=COL_SIG, sw=1.8, dash="5,4")
    d.path(f"M {sx0} {sy0} Q {sx0 + 45} 372 {sx0 + 110} 370 Q {sx0 + 230} 358 {sx0 + 380} 356",
           stroke=COL_WARN, sw=2.3)
    d.text(sx0 + 195, 382, "Slow exp(−ωm·t) doublet tail!", size=10.5, color=COL_WARN, weight="bold")

    d.callout(576, 462, 446, 84, "Doublet Formula (Razavi Eq. 6.77)", [
        "Gm(s) = (gm1 / 2) · [1 + 1/(1 + s/ωm)] = gm1 · (1 + s/(2ωm)) / (1 + s/ωm)",
        "ωm ≈ gm3 / (2·Cgs3 + Cdb1 + Cdb3)  -> Keep ωm >> GBW for fast settling!",
    ], tone="warn", fs=10.3)
    return d


def diag_14_mos_noise_input_referred():
    d = SVGDoc(
        "mos-noise-input-referred.svg",
        "MOS Thermal & 1/f Noise Model and Input-Referred (Vn², In²) Two-Port",
        "Mô hình Nhiễu Nhiệt & Nhiễu 1/f của MOSFET và Quy đổi Mạng Hai cửa Nhiễu Ngõ vào (Ch.07 §7.2–7.3)",
        "Ch.07", [7], width=1060, height=580
    )
    d.panel(20,  74, 500, 484, "(a) Physical Noisy MOSFET & PSD Corner fc")
    d.panel(540, 74, 500, 484, "(b) Rigorous Input-Referred Noise Two-Port")

    # --- (a) Noisy MOSFET ---
    mx = 275
    d.line(mx, 128, mx, 188, color=COL_DARK)
    d.port(mx, 124, "Drain (D)", side="top", color=COL_DARK)
    d.dot(mx, 152, COL_AMBER)

    # Gate with series flicker noise Vn,1/f^2
    d.port(82, 212, "Gate (G)", side="left", color=COL_SIG)
    vnf = d.vsrc_h(162, 212, color=COL_WARN, label="Vn,1/f²", label_pos="top")
    d.line(86, 212, vnf["l"][0], 212, color=COL_SIG)
    d.line(vnf["r"][0], 212, mx - 30, 212, color=COL_WARN)

    m1 = d.nmos(mx, 212, facing="right", color=COL_DARK, label="M1", sub="Noiseless Core", label_side="left")
    # Drain-source thermal noise current source in parallel on right (x=375)
    d.wire([(mx, 152), (385, 152), (385, 188)], color=COL_AMBER)
    inth = d.isrc_v(385, 212, direction="down", color=COL_AMBER, label="In,th²", sub="4kTγ·gm", label_side="right")
    d.wire([inth["b"], (385, 272), (mx, 272)], color=COL_AMBER)
    d.line(mx, m1["s"][1], mx, 296, color=COL_DARK)
    d.dot(mx, 272, COL_AMBER)
    d.port(mx, 300, "Source (S)", side="bottom", color=COL_DARK)

    # Mini PSD log-log plot at bottom of left panel
    px0, py0 = d.axes(78, 360, 385, 140, xlabel="log f [Hz]", ylabel="Input PSD Sv(f) [V²/Hz]")
    # 1/f line + flat thermal floor + total curve
    d.line(px0 + 18, 372, px0 + 215, 486, color=COL_WARN, sw=1.6, dash="4,4")
    d.line(px0 + 18, 458, px0 + 365, 458, color=COL_AMBER, sw=1.6, dash="4,4")
    d.path(f"M {px0 + 18} 370 L {px0 + 135} 438 Q {px0 + 175} 458 {px0 + 230} 458 L {px0 + 365} 458",
           stroke=COL_SIG, sw=2.5)
    d.line(px0 + 166, 458, px0 + 166, py0, color=COL_MUTED, sw=1.2, dash="3,3")
    d.text(px0 + 166, py0 + 16, "fc (1/f corner)", size=10.3, color=COL_DARK, anchor="middle", weight="bold")
    d.text(px0 + 46, 386, "K / (Cox·W·L·f)", size=10.4, color=COL_WARN, weight="bold")
    d.text(px0 + 245, 448, "4kTγ / gm (Thermal)", size=10.4, color=COL_AMBER, weight="bold")

    # --- (b) Input-Referred Two-Port ---
    # Source branch: Vsig + ZS -> series Vn,in^2 -> shunt In,in^2 -> Noiseless Amplifier
    sx = 595
    vsig = d.vsrc_v(sx, 260, color=COL_SIG, label="Vsig", label_side="left", ac=True)
    zs = d.res_h(655, 186, color=COL_DARK, label="ZS (RS)", label_pos="top")
    d.wire([vsig["t"], (sx, 186), zs["l"]], color=COL_SIG)

    vn_in = d.vsrc_h(745, 186, color=COL_WARN, label="Vn,in²", label_pos="top")
    d.line(zs["r"][0], 186, vn_in["l"][0], 186, color=COL_SIG)
    d.line(vn_in["r"][0], 186, 855, 186, color=COL_WARN)
    d.dot(812, 186, COL_AMBER)

    in_in = d.isrc_v(812, 250, direction="down", color=COL_AMBER, label="In,in²", label_side="left")
    d.line(812, 186, 812, in_in["t"][1], color=COL_AMBER)

    # Noiseless Two-Port block
    d.rect(855, 162, 125, 146, fill="#eff6ff", stroke=COL_SIG, sw=1.8, rx=8)
    d.text(917.5, 224, "Noiseless", size=12, color=COL_SIG, anchor="middle", weight="bold")
    d.text(917.5, 242, "Two-Port", size=12, color=COL_SIG, anchor="middle", weight="bold")
    d.text(917.5, 260, "Gain Av(s)", size=11, color=COL_MUTED, anchor="middle")

    d.line(980, 220, 1010, 220, color=COL_SIG)
    d.port(1014, 220, "Vout", side="right", color=COL_SIG)

    # Return ground rail
    d.wire([vsig["b"], (sx, 314), (855, 314)], color=COL_DARK)
    d.line(812, in_in["b"][1], 812, 314, color=COL_AMBER)
    d.dot(812, 314, COL_DARK)
    d.gnd(700, 314)
    d.dot(700, 314, COL_DARK)

    d.callout(560, 356, 460, 186, "Two-Step Procedure & Why In,in² Matters (§7.3)", [
        "1. Short input (ZS = 0): Measure Vn,out² -> Vn,in² = Vn,out² / |Av0|²",
        "2. Open input  (ZS = ∞): Measure Vn,out² -> In,in² = Vn,out² / |Ztrans|²",
        "",
        "• For finite source impedance ZS (assuming low correlation):",
        "  Vn,tot,in² ≈ Vn,in² + |ZS|² · In,in² + 4kT·Re(ZS)",
        "• Low-f MOSFET gate: In,in² ≈ 0, UNLESS ω·Cgs·|ZS| is significant!",
        "• 1-Pole Noise Bandwidth:  BWn = (π / 2) · f-3dB ≈ 1.57 · f-3dB",
    ], tone="sig", fs=10.4)
    return d


def diag_15_feedback_four_topologies():
    d = SVGDoc(
        "feedback-four-topologies.svg",
        "Four Feedback Topologies (Razavi Sense–Return Naming Convention)",
        "Bốn Cấu trúc Hồi tiếp Chuẩn theo Quy ước Cảm nhận Ngõ ra – Hồi về Ngõ vào (Ch.08 §8.2)",
        "Ch.08", [8], width=1080, height=620
    )

    def draw_fb_cell(px, py, title, amp_lbl, sense_type, ret_type, rin_eq, rout_eq):
        d.panel(px, py, 512, 258, title)
        # Forward Amplifier box
        ax, ay, aw, ah = px + 185, py + 52, 130, 68
        d.rect(ax, ay, aw, ah, fill="#eff6ff", stroke=COL_SIG, sw=1.8, rx=7)
        d.text(ax + aw / 2, ay + 28, "Forward Amp", size=11.2, color=COL_SIG, anchor="middle", weight="bold")
        d.text(ax + aw / 2, ay + 46, amp_lbl, size=11, color=COL_DARK, anchor="middle")

        # Feedback Network box
        bx, by, bw, bh = px + 185, py + 150, 130, 56
        d.rect(bx, by, bw, bh, fill="#fffbeb", stroke=COL_AMBER, sw=1.8, rx=7)
        d.text(bx + bw / 2, by + 24, "Feedback β", size=11.2, color=COL_AMBER, anchor="middle", weight="bold")
        d.text(bx + bw / 2, by + 41, f"Sense: {sense_type} | Ret: {ret_type}",
               size=9.8, color=COL_MUTED, anchor="middle")

        # Input side wiring (Series = Voltage subtraction; Shunt = Current subtraction)
        if ret_type == "V (Series)":
            # Vin+ to top amp input, amp bottom input goes down to beta top-left, beta bot-left to GND
            d.port(px + 66, ay + 18, "Vin", side="left", color=COL_SIG)
            d.line(px + 70, ay + 18, ax, ay + 18, color=COL_SIG)
            d.wire([(ax, ay + 52), (px + 135, ay + 52), (px + 135, by + 16), (bx, by + 16)], color=COL_AMBER)
            d.text(px + 128, ay + 46, "VF", size=10.2, color=COL_AMBER, anchor="end", weight="bold")
            d.wire([(bx, by + 42), (px + 105, by + 42), (px + 105, by + 56)], color=COL_DARK)
            d.gnd(px + 105, by + 56)
        else:
            # Shunt current summing node at input!
            d.port(px + 66, ay + 24, "Iin", side="left", color=COL_SIG)
            d.line(px + 70, ay + 24, ax, ay + 24, color=COL_SIG)
            d.dot(px + 135, ay + 24, COL_AMBER)
            d.wire([(px + 135, ay + 24), (px + 135, by + 18), (bx, by + 18)], color=COL_AMBER)
            d.arrow(px + 135, ay + 45, px + 135, by + 12, color=COL_AMBER, sw=1.6)
            d.text(px + 126, ay + 62, "IF", size=10.2, color=COL_AMBER, anchor="end", weight="bold")
            d.wire([(ax, ay + 54), (px + 105, ay + 54), (px + 105, by + 42), (bx, by + 42)], color=COL_DARK)
            d.dot(px + 105, by + 42, COL_DARK)
            d.gnd(px + 105, by + 56)
            d.line(px + 105, by + 42, px + 105, by + 56)

        # Output side wiring (Shunt = Voltage sense; Series = Current sense)
        if sense_type == "V (Shunt)":
            d.line(ax + aw, ay + 22, px + 432, ay + 22, color=COL_SIG)
            d.port(px + 436, ay + 22, "Vout", side="right", color=COL_SIG)
            d.dot(px + 382, ay + 22, COL_AMBER)
            d.wire([(px + 382, ay + 22), (px + 382, by + 18), (bx + bw, by + 18)], color=COL_AMBER)
            d.wire([(ax + aw, ay + 54), (px + 408, ay + 54), (px + 408, by + 42), (bx + bw, by + 42)], color=COL_DARK)
            d.gnd(px + 408, by + 56)
            d.line(px + 408, by + 42, px + 408, by + 56)
        else:
            # Series current loop through RL and beta right port!
            d.wire([(ax + aw, ay + 20), (px + 428, ay + 20), (px + 428, ay + 55)], color=COL_SIG)
            rl = d.res_v(px + 428, ay + 79, color=COL_DARK, label="RL", label_side="right")
            d.text(px + 392, ay + 13, "Iout ->", size=10.4, color=COL_SIG, weight="bold")
            d.wire([rl["b"], (px + 428, by + 18), (bx + bw, by + 18)], color=COL_AMBER)
            d.wire([(bx + bw, by + 42), (px + 365, by + 42), (px + 365, ay + 54), (ax + aw, ay + 54)], color=COL_DARK)
            d.gnd(px + 365, by + 56)
            d.line(px + 365, by + 42, px + 365, by + 56)

        # Closed-loop Rin & Rout summary bar at bottom of cell
        d.rect(px + 14, py + 222, 484, 26, fill="#f8fafc", stroke=COL_BORDER, sw=1.0, rx=5)
        d.text(px + 24, py + 239, rin_eq, size=10.6, color=COL_BIAS, weight="bold")
        d.text(px + 488, py + 239, rout_eq, size=10.6, color=COL_SIG, anchor="end", weight="bold")

    draw_fb_cell(
        20, 74, "(a) Voltage–Voltage Feedback (§8.2.1)", "A0 [V/V]",
        "V (Shunt)", "V (Series)",
        "Rin,cl = Rin · (1 + β·A0)  [HIGH]",
        "Rout,cl = Rout / (1 + β·A0)  [LOW]"
    )
    draw_fb_cell(
        548, 74, "(b) Current–Voltage Feedback (§8.2.2)", "Gm [A/V]",
        "I (Series)", "V (Series)",
        "Rin,cl = Rin · (1 + β·Gm)  [HIGH]",
        "Rout,cl = Rout · (1 + β·Gm)  [HIGH]"
    )
    draw_fb_cell(
        20, 346, "(c) Voltage–Current Feedback (§8.2.3)", "R0 [V/A]",
        "V (Shunt)", "I (Shunt)",
        "Rin,cl = Rin / (1 + β·R0)  [LOW]",
        "Rout,cl = Rout / (1 + β·R0)  [LOW]"
    )
    draw_fb_cell(
        548, 346, "(d) Current–Current Feedback (§8.2.4)", "AI [A/A]",
        "I (Series)", "I (Shunt)",
        "Rin,cl = Rin / (1 + β·AI)  [LOW]",
        "Rout,cl = Rout · (1 + β·AI)  [HIGH]"
    )
    return d


def diag_16_middlebrook_stb_loop_probe():
    d = SVGDoc(
        "middlebrook-stb-loop-probe.svg",
        "Breaking the Feedback Loop: Loading, Middlebrook & Spectre STB Probe",
        "Mở vòng Hồi tiếp Chuẩn xác: Hiệu ứng Tải, Tiêm Kép Middlebrook & Đầu dò Spectre STB (Ch.08 §8.5–8.8)",
        "Ch.08", [8], width=1080, height=590
    )
    d.panel(18,  74, 326, 492, "(a) Naive Wire Cut / Big L–C Trap")
    d.panel(360, 74, 346, 492, "(b) Two-Port Loading & Middlebrook")
    d.panel(722, 74, 340, 492, "(c) Cadence Spectre stb (iprobe)")

    # --- (a) Naive Cut ---
    op1 = d.opamp(180, 175, w=58, h=50, facing="right", plus_top=False, label="A(s)")
    d.port(72, op1["in_bot"][1], "Vin=0", side="left", color=COL_MUTED)
    d.line(76, op1["in_bot"][1], op1["in_bot"][0], op1["in_bot"][1], color=COL_MUTED)
    d.wire([op1["out"], (275, 175), (275, 290), (225, 290)], color=COL_DARK)
    d.rect(145, 268, 80, 44, fill="#fef2f2", stroke=COL_WARN, sw=1.6, rx=6)
    d.text(185, 294, "β Net", size=11.5, color=COL_WARN, anchor="middle", weight="bold")
    # Cut with X mark!
    d.wire([(145, 290), (105, 290), (105, 224)], color=COL_WARN, dash="4,3")
    d.wire([(105, 194), (105, op1["in_top"][1]), op1["in_top"]], color=COL_WARN, dash="4,3")
    d.line(95, 200, 115, 218, color=COL_WARN, sw=2.6)
    d.line(95, 218, 115, 200, color=COL_WARN, sw=2.6)
    d.text(122, 214, "BROKEN!", size=11, color=COL_WARN, weight="bold")

    d.callout(32, 356, 298, 190, "Why Naive Cuts Fail!", [
        "1. Direct wire cut destroys DC bias ->",
        "   MOSFETs saturate to rails!",
        "2. Disconnects Zin,β / Zout,β loading",
        "   from the broken loop ends!",
        "3. Giant 1 GH / 1 GF L-C break fails",
        "   for bilateral Z, Miller caps, or",
        "   low-freq Bandgap / LDO poles!",
    ], tone="warn", fs=10.4)

    # --- (b) Middlebrook Dual V & I Injection ---
    op2 = d.opamp(535, 165, w=58, h=50, facing="right", plus_top=False, label="A(s)")
    d.gnd(452, op2["in_bot"][1] + 10)
    d.wire([(452, op2["in_bot"][1] + 10), (452, op2["in_bot"][1]), op2["in_bot"]])
    d.wire([op2["out"], (645, 165), (645, 286), (578, 286)], color=COL_SIG)
    d.rect(492, 264, 86, 44, fill="#fffbeb", stroke=COL_AMBER, sw=1.6, rx=6)
    d.text(535, 290, "Bilateral β", size=11.2, color=COL_AMBER, anchor="middle", weight="bold")

    # Series Vz + Shunt Iz injection on feedback wire
    vz = d.vsrc_v(422, 222, color=COL_SIG, label="Vz", label_side="left", ac=True)
    d.wire([(492, 286), (422, 286), vz["b"]], color=COL_AMBER)
    d.wire([vz["t"], (422, op2["in_top"][1]), op2["in_top"]], color=COL_SIG)
    d.dot(456, op2["in_top"][1], COL_BIAS)
    iz = d.isrc_v(456, 218, direction="up", color=COL_BIAS, label="Iz", label_side="right")
    d.line(456, op2["in_top"][1], 456, iz["t"][1], color=COL_BIAS)
    d.gnd(456, iz["b"][1] + 4)
    d.line(456, iz["b"][1], 456, iz["b"][1] + 4)

    d.callout(374, 356, 318, 190, "Middlebrook Exact Theorem (§8.7)", [
        "• Keeps closed-loop DC intact!",
        "• Step 1: Inject series Vz -> Tv = Vy/Vx",
        "• Step 2: Inject shunt  Iz -> Ti = Iy/Ix",
        "• Exact Bilateral Loop Gain T(s):",
        "  T = (Tv · Ti − 1) / (Tv + Ti + 2)",
        "• Blackman Impedance Formula (§8.8):",
        "  Zport = Z0 · (1 + T_sc) / (1 + T_oc)",
    ], tone="sig", fs=10.4)

    # --- (c) Spectre stb iprobe / diffstbprobe ---
    op3 = d.opamp(895, 165, w=58, h=50, facing="right", plus_top=False, label="OTA")
    d.gnd(808, op3["in_bot"][1] + 10)
    d.wire([(808, op3["in_bot"][1] + 10), (808, op3["in_bot"][1]), op3["in_bot"]])
    # iprobe badge inline at output/feedback loop
    d.line(op3["out"][0], 165, 950, 165, color=COL_SIG)
    d.rect(950, 148, 86, 34, fill="#ecfdf5", stroke=COL_BIAS, sw=2.0, rx=6)
    d.text(993, 169, "iprobe", size=11.8, color=COL_BIAS, anchor="middle", weight="bold")
    d.wire([(993, 182), (993, 286), (935, 286)], color=COL_BIAS)
    d.rect(850, 264, 85, 44, fill="#f8fafc", stroke=COL_DARK, sw=1.6, rx=6)
    d.text(892.5, 290, "β Network", size=11.2, color=COL_DARK, anchor="middle", weight="bold")
    d.wire([(850, 286), (780, 286), (780, op3["in_top"][1]), op3["in_top"]], color=COL_BIAS)

    d.callout(736, 356, 312, 190, "Cadence Spectre STB Standard", [
        "• Place analogLib/iprobe in series",
        "  inside the single feedback loop.",
        "• Zero DC drop (R=0) -> 100% exact OP!",
        "• Automatically performs bidirectional",
        "  voltage+current Middlebrook sweep!",
        "• Fully-Diff Op-Amp: use diffstbprobe",
        "  (mode=diff for DM, mode=comm for CMFB).",
    ], tone="bias", fs=10.4)
    return d


def diag_17_telescopic_cascode_opamp():
    d = SVGDoc(
        "telescopic-cascode-opamp.svg",
        "Fully-Differential Telescopic Cascode Operational Amplifier",
        "Bộ Khuếch đại Thuật toán Cascode Lồng Vi sai Toàn phần (Telescopic Op-Amp — Ch.09 §9.2)",
        "Ch.09", [9], width=1060, height=620
    )
    d.panel(22, 74, 548, 524, "5-Transistor Vertical Stack Topology (M1–M9)")

    xl, xr = 215, 385
    cx = 300
    d.vdd(xl, 118)
    d.vdd(xr, 118)

    # Top PMOS current sources M7, M8 (y=158)
    m7 = d.pmos(xl, 158, facing="right", color=COL_BIAS, label="M7", label_side="right")
    m8 = d.pmos(xr, 158, facing="left",  color=COL_BIAS, label="M8", label_side="left")
    d.line(xl, 118, xl, m7["s"][1])
    d.line(xr, 118, xr, m8["s"][1])
    d.line(125, 158, m7["g"][0], 158, color=COL_AMBER)
    d.port(121, 158, "VCMFB", side="left", color=COL_AMBER)
    d.line(m8["g"][0], 158, 475, 158, color=COL_AMBER)
    d.port(479, 158, "VCMFB", side="right", color=COL_AMBER)

    # PMOS cascode shields M5, M6 (y=232)
    m5 = d.pmos(xl, 232, facing="right", color=COL_BIAS, label="M5", label_side="right")
    m6 = d.pmos(xr, 232, facing="left",  color=COL_BIAS, label="M6", label_side="left")
    d.line(xl, m7["d"][1], xl, m5["s"][1], color=COL_BIAS)
    d.line(xr, m8["d"][1], xr, m6["s"][1], color=COL_BIAS)
    d.line(125, 232, m5["g"][0], 232, color=COL_BIAS)
    d.port(121, 232, "Vb2", side="left", color=COL_BIAS)
    d.line(m6["g"][0], 232, 475, 232, color=COL_BIAS)
    d.port(479, 232, "Vb2", side="right", color=COL_BIAS)

    # Differential Output Nodes at y=286
    d.line(xl, m5["d"][1], xl, 316, color=COL_SIG)
    d.line(xr, m6["d"][1], xr, 316, color=COL_SIG)
    d.dot(xl, 286, COL_SIG)
    d.dot(xr, 286, COL_SIG)
    d.line(125, 286, xl, 286, color=COL_SIG)
    d.port(121, 286, "Vout−", side="left", color=COL_SIG)
    d.line(xr, 286, 475, 286, color=COL_SIG)
    d.port(479, 286, "Vout+", side="right", color=COL_SIG)

    # NMOS cascode shields M3, M4 (y=340)
    m3 = d.nmos(xl, 340, facing="right", color=COL_BIAS, label="M3", label_side="right")
    m4 = d.nmos(xr, 340, facing="left",  color=COL_BIAS, label="M4", label_side="left")
    d.line(125, 340, m3["g"][0], 340, color=COL_BIAS)
    d.port(121, 340, "Vb1", side="left", color=COL_BIAS)
    d.line(m4["g"][0], 340, 475, 340, color=COL_BIAS)
    d.port(479, 340, "Vb1", side="right", color=COL_BIAS)

    # NMOS input pair M1, M2 (y=414)
    m1 = d.nmos(xl, 414, facing="right", color=COL_SIG, label="M1", sub="gm1", label_side="right")
    m2 = d.nmos(xr, 414, facing="left",  color=COL_SIG, label="M2", sub="gm2", label_side="left")
    d.line(xl, m3["s"][1], xl, m1["d"][1], color=COL_SIG)
    d.line(xr, m4["s"][1], xr, m2["d"][1], color=COL_SIG)
    d.line(125, 414, m1["g"][0], 414, color=COL_SIG)
    d.port(121, 414, "Vin+", side="left", color=COL_SIG)
    d.line(m2["g"][0], 414, 475, 414, color=COL_SIG)
    d.port(479, 414, "Vin−", side="right", color=COL_SIG)

    # Tail current source M9 (y=498)
    d.wire([m1["s"], (xl, 456), (xr, 456), m2["s"]], color=COL_DARK)
    d.dot(cx, 456, COL_BIAS)
    m9 = d.nmos(cx, 498, facing="right", color=COL_BIAS, label="M9 (ISS)", label_side="right")
    d.line(cx, 456, cx, m9["d"][1], color=COL_BIAS)
    d.line(215, 498, m9["g"][0], 498, color=COL_BIAS)
    d.port(211, 498, "Vb0", side="left", color=COL_BIAS)
    d.line(cx, m9["s"][1], cx, 542)
    d.gnd(cx, 542)

    d.text(300, 582, "5 Stacked Saturated MOSFETs -> Single Current Branch per Side!",
           size=11, color=COL_DARK, anchor="middle", weight="bold")

    # Right Analytical Callouts
    d.callout(590, 76, 448, 168, "1. Gain, Speed & Power Advantage (§9.2.1)", [
        "• Differential Voltage Gain:",
        "  |Adm| ≈ gm1 · [ (gm3·ro3·ro1) || (gm5·ro5·ro7) ]",
        "• Highest Speed & Lowest Power of Cascode Op-Amps:",
        "  - Only 2 current branches (ISS total) vs 4 in Folded",
        "  - Nondominant pole at NMOS M3 source (high gm3/Cx!)",
        "  - Lowest thermal noise: only M1,2 and M7,8 contribute!",
    ], tone="sig", fs=10.7)

    d.callout(590, 260, 448, 162, "2. Headroom Stack Penalty (5·VDS,min)", [
        "• Peak-to-Peak Single-Side Swing:",
        "  Vout,swing = VDD − (VDS,min1 + VDS,min3 + |VDS,min5|",
        "                      + |VDS,min7| + VDS,min9)",
        "             = VDD − 5 · VDS,min",
        "• Differential p-p swing = 2 · (VDD − 5·VDS,min).",
    ], tone="amber", fs=10.7)

    d.callout(590, 438, 448, 160, "3. TRAP: Cannot Short Input to Output! (Fig. 9.5)", [
        "• If Vout is shorted directly to Vin (unity-gain buffer):",
        "  - M1 stays in sat ONLY if Vout ≤ VDS1 + VTH1 -> narrow!",
        "  - M3 stays in sat ONLY if Vout ≥ Vb1 − VTH3",
        "• Result: Unity-gain DC feedback fails unless switched-cap",
        "  level shifting is used -> Upgrade to Folded-Cascode!",
    ], tone="warn", fs=10.7)
    return d


def diag_18_folded_cascode_ota():
    d = SVGDoc(
        "folded-cascode-ota.svg",
        "Folded-Cascode OTA: Fold-Node KCL (Ifold > Itail/2) & Cascode Shields",
        "Bộ Khuếch đại Hỗ dẫn Cascode Gập: Bất biến KCL Nút Gập (Ifold > Itail/2) & Che chắn (Ch.09 §9.2.4)",
        "Ch.09", [9], width=1080, height=620
    )
    d.panel(20, 74, 600, 524, "NMOS-Input Folded-Cascode OTA Schematic")

    x_out_l, x_in_l, x_mid, x_in_r, x_out_r = 140, 255, 315, 375, 490

    # Top VDD rails at x_out_l & x_out_r
    d.vdd(x_out_l, 120)
    d.vdd(x_out_r, 120)

    # Top PMOS Folding Current Sources M5, M6 (y=164)
    m5 = d.pmos(x_out_l, 164, facing="left",  color=COL_BIAS, label="M5", sub="Ifold", label_side="left")
    m6 = d.pmos(x_out_r, 164, facing="right", color=COL_BIAS, label="M6", sub="Ifold", label_side="right")
    d.line(x_out_l, 120, x_out_l, m5["s"][1])
    d.line(x_out_r, 120, x_out_r, m6["s"][1])
    d.line(m5["g"][0], 164, m6["g"][0], 164, color=COL_BIAS)
    d.dot(x_mid, 164, COL_BIAS)
    d.port(x_mid, 144, "Vb,fold", side="top", color=COL_BIAS)
    d.line(x_mid, 148, x_mid, 164, color=COL_BIAS)

    # FOLD NODES X (left) & Y (right) at y=214!
    y_fold = 214
    d.line(x_out_l, m5["d"][1], x_out_l, 252, color=COL_AMBER)
    d.line(x_out_r, m6["d"][1], x_out_r, 252, color=COL_AMBER)
    d.dot(x_out_l, y_fold, COL_WARN)
    d.dot(x_out_r, y_fold, COL_WARN)
    d.text(x_out_l - 10, y_fold - 4, "Fold X", size=11, color=COL_WARN, anchor="end", weight="bold")
    d.text(x_out_r + 10, y_fold - 4, "Fold Y", size=11, color=COL_WARN, anchor="start", weight="bold")

    # Connect NMOS Input Pair drains UP to Fold Nodes X & Y!
    m1 = d.nmos(x_in_l, 305, facing="right", color=COL_SIG, label="M1", sub="Itail/2", label_side="right")
    m2 = d.nmos(x_in_r, 305, facing="left",  color=COL_SIG, label="M2", sub="Itail/2", label_side="left")
    d.wire([m1["d"], (x_in_l, y_fold), (x_out_l, y_fold)], color=COL_SIG)
    d.wire([m2["d"], (x_in_r, y_fold), (x_out_r, y_fold)], color=COL_SIG)

    # Input Gates Vin+ & Vin-
    d.line(x_in_l - 52, 305, m1["g"][0], 305, color=COL_SIG)
    d.port(x_in_l - 56, 305, "Vin+", side="left", color=COL_SIG)
    d.line(m2["g"][0], 305, x_in_r + 52, 305, color=COL_SIG)
    d.port(x_in_r + 56, 305, "Vin−", side="right", color=COL_SIG)

    # Tail NMOS M11 (x_mid, y=420)
    d.wire([m1["s"], (x_in_l, 368), (x_in_r, 368), m2["s"]], color=COL_DARK)
    d.dot(x_mid, 368, COL_BIAS)
    m11 = d.nmos(x_mid, 420, facing="right", color=COL_BIAS, label="M11", sub="Itail", label_side="right")
    d.line(x_mid, 368, x_mid, m11["d"][1], color=COL_BIAS)
    d.line(x_mid - 50, 420, m11["g"][0], 420, color=COL_BIAS)
    d.port(x_mid - 54, 420, "Vb0", side="left", color=COL_BIAS)
    d.line(x_mid, m11["s"][1], x_mid, 480)
    d.gnd(x_mid, 480)

    # PMOS Cascode Shields M3 & M4 (y=276)
    m3 = d.pmos(x_out_l, 276, facing="right", color=COL_BIAS, label="M3", label_side="left")
    m4 = d.pmos(x_out_r, 276, facing="left",  color=COL_BIAS, label="M4", label_side="right")
    d.line(x_out_l - 52, 276, m3["g"][0], 276, color=COL_BIAS)
    d.port(x_out_l - 56, 276, "Vb,p", side="left", color=COL_BIAS)
    d.line(m4["g"][0], 276, x_out_r + 52, 276, color=COL_BIAS)
    d.port(x_out_r + 56, 276, "Vb,p", side="right", color=COL_BIAS)

    # Output Nodes Vout- & Vout+ at y=336
    d.line(x_out_l, m3["d"][1], x_out_l, 372, color=COL_SIG)
    d.line(x_out_r, m4["d"][1], x_out_r, 372, color=COL_SIG)
    d.dot(x_out_l, 336, COL_SIG)
    d.dot(x_out_r, 336, COL_SIG)
    d.line(74, 336, x_out_l, 336, color=COL_SIG)
    d.port(70, 336, "Vout−", side="left", color=COL_SIG)
    d.line(x_out_r, 336, 556, 336, color=COL_SIG)
    d.port(560, 336, "Vout+", side="right", color=COL_SIG)

    # Bottom NMOS Cascode Active Loads M7, M8 (y=396) & M9, M10 (y=486)
    m7 = d.nmos(x_out_l, 396, facing="right", color=COL_BIAS, label="M7", label_side="right")
    m8 = d.nmos(x_out_r, 396, facing="left",  color=COL_BIAS, label="M8", label_side="left")
    d.line(78, 396, m7["g"][0], 396, color=COL_BIAS)
    d.port(74, 396, "Vb,n", side="left", color=COL_BIAS)
    d.line(m8["g"][0], 396, 552, 396, color=COL_BIAS)
    d.port(556, 396, "Vb,n", side="right", color=COL_BIAS)

    m9  = d.nmos(x_out_l, 486, facing="right", color=COL_AMBER, label="M9", label_side="right")
    m10 = d.nmos(x_out_r, 486, facing="left",  color=COL_AMBER, label="M10", label_side="left")
    d.line(x_out_l, m7["s"][1], x_out_l, m9["d"][1], color=COL_BIAS)
    d.line(x_out_r, m8["s"][1], x_out_r, m10["d"][1], color=COL_BIAS)
    d.line(78, 486, m9["g"][0], 486, color=COL_AMBER)
    d.port(74, 486, "VCMFB", side="left", color=COL_AMBER)
    d.line(m10["g"][0], 486, 552, 486, color=COL_AMBER)
    d.port(556, 486, "VCMFB", side="right", color=COL_AMBER)

    d.line(x_out_l, m9["s"][1], x_out_l, 536)
    d.gnd(x_out_l, 536)
    d.line(x_out_r, m10["s"][1], x_out_r, 536)
    d.gnd(x_out_r, 536)

    d.text(315, 582, "KCL at Fold X/Y:  Icas(M3,4) = Ifold − Itail / 2  >  0 !",
           size=11.4, color=COL_WARN, anchor="middle", weight="bold")

    # Right Analytical Callouts
    d.callout(638, 76, 422, 168, "1. Structural KCL Invariant & Slewing (§9.2.4)", [
        "• Mandatory DC Equilibrium Invariant:",
        "  Ifold > (1/2) · Itail   (choose Ifold ≈ 0.75–1.0 · Itail)",
        "• If Ifold ≤ Itail/2, cascode shields M3–M4 pinch OFF!",
        "• Slewing Trap (§9.9): If Ifold < Itail, full input tilt",
        "  starves one cascode branch -> fold node collapses toward",
        "  GND, causing slow overdrive recovery!",
    ], tone="warn", fs=10.6)

    d.callout(638, 258, 422, 166, "2. Gain, Swing & Unity-Feedback Advantage", [
        "• Output Swing: VDD − 4·VDS,min  (saves 1·VDS,min vs Tel!)",
        "• Allows direct Vin = Vout unity-gain buffer connection &",
        "  wide ICMR reaching VDD (NMOS-in) or GND (PMOS-in)!",
        "• Gain: |Adm| = gm1 · [ (gm3·ro3·(ro1 || ro5)) || (gm7·ro7·ro9) ]",
        "  (~2–3x lower than Telescopic due to parallel ro1 || ro5).",
    ], tone="sig", fs=10.6)

    d.callout(638, 438, 422, 158, "3. Noise & Nondominant Fold Pole Trade-Off", [
        "• Power: Consumes 2·Ifold (~2x Telescopic current).",
        "• Extra Noise: Folding sources M5,6 inject 8kTγ·gm5 / gm1²",
        "  -> Size M5,6 with LOW gm/ID (large Vov, long L)!",
        "• Fold Pole: ωp,fold ≈ (gm3 + gmb3) / (Cdb1 + Cdb5 + Cgs3).",
    ], tone="bias", fs=10.6)
    return d


def diag_19_two_stage_miller_opamp():
    d = SVGDoc(
        "two-stage-miller-opamp.svg",
        "Two-Stage CMOS Op-Amp with Miller Compensation (Cc + Nulling Rz)",
        "Op-Amp CMOS Hai Tầng Bù Tần số Miller (Cc nối tiếp Điện trở Triệt Zero Rz — Ch.09 §9.3 & Ch.10 §10.5)",
        "Ch.09 & 10", [9, 10], width=1080, height=600
    )
    d.panel(20, 74, 620, 504, "Stage 1 (High-Gain Diff OTA) + Stage 2 (High-Swing CS) + Cc/Rz")

    x_m1, x_m2, x_st2 = 175, 325, 515
    cx1 = 250

    # Top VDD supplies
    d.vdd(cx1, 118)
    d.vdd(x_st2, 118)

    # Stage 1 Top PMOS Tail M5 (x=250, y=162) & Stage 2 PMOS Load M7 (x=515, y=180)
    m5 = d.pmos(cx1, 162, facing="right", color=COL_BIAS, label="M5 (ISS)", label_side="right")
    m7 = d.pmos(x_st2, 180, facing="left", color=COL_BIAS, label="M7 (I2)", sub="ro7", label_side="right")
    d.line(cx1, 118, cx1, m5["s"][1])
    d.line(x_st2, 118, x_st2, m7["s"][1])
    d.port(150, 162, "Vb", side="left", color=COL_BIAS)
    d.line(154, 162, m5["g"][0], 162, color=COL_BIAS)
    d.port(445, 180, "Vb", side="left", color=COL_BIAS)
    d.line(449, 180, m7["g"][0], 180, color=COL_BIAS)

    # PMOS Diff Input Pair M1 & M2 (y=252)
    d.wire([m5["d"], (cx1, 206), (x_m1, 206), (x_m1, 228)], color=COL_SIG)
    d.wire([(cx1, 206), (x_m2, 206), (x_m2, 228)], color=COL_SIG)
    d.dot(cx1, 206, COL_SIG)

    m1 = d.pmos(x_m1, 252, facing="right", color=COL_SIG, label="M1", sub="gm1", label_side="right")
    m2 = d.pmos(x_m2, 252, facing="left",  color=COL_SIG, label="M2", sub="gm2", label_side="left")
    # Polarity: M1 (mirror side) = Vin-, M2 (Node X side -> inverting M6) = Vin+!
    d.line(95, 252, m1["g"][0], 252, color=COL_SIG)
    d.port(91, 252, "Vin−", side="left", color=COL_SIG)
    d.line(m2["g"][0], 252, 412, 252, color=COL_SIG)
    d.port(416, 252, "Vin+", side="right", color=COL_SIG)

    # Bottom NMOS Mirror Load M3 (diode) & M4 (y=424)
    m3 = d.nmos(x_m1, 424, facing="left",  color=COL_BIAS, label="M3", label_side="left")
    m4 = d.nmos(x_m2, 424, facing="right", color=COL_BIAS, label="M4", label_side="left")
    d.line(x_m1, m1["d"][1], x_m1, m3["d"][1], color=COL_BIAS)
    d.line(x_m2, m2["d"][1], x_m2, m4["d"][1], color=COL_SIG)
    d.line(m3["g"][0], 424, m4["g"][0], 424, color=COL_BIAS)
    d.wire([(x_m1, 376), (x_m1 + 42, 376), (x_m1 + 42, 424)], color=COL_BIAS)
    d.dot(x_m1, 376, COL_BIAS)
    d.dot(x_m1 + 42, 424, COL_BIAS)

    # High-Z Stage-1 Output Node X (x=325, y=350) -> drives Stage 2 Gate M6 (y=424)
    d.dot(x_m2, 342, COL_WARN)
    d.dot(x_m2, 386, COL_SIG)
    d.text(x_m2 - 10, 340, "Node X (R1,C1)", size=10.6, color=COL_WARN, anchor="end", weight="bold")

    # Miller Compensation Branch (Node X -> Rz -> Cc -> Vout at y=342)
    rz = d.res_h(392, 342, color=COL_AMBER, label="Rz", label_pos="top")
    cc = d.cap_h(458, 342, color=COL_WARN, label="Cc", label_pos="top")
    d.line(x_m2, 342, rz["l"][0], 342, color=COL_WARN, sw=2.2)
    d.line(rz["r"][0], 342, cc["l"][0], 342, color=COL_WARN, sw=2.2)
    d.wire([cc["r"], (x_st2, 342)], color=COL_WARN, sw=2.2)
    d.dot(x_st2, 342, COL_WARN)

    # Stage 2 CS Amplifier M6 (x=515, y=424) + Vout + CL
    m6 = d.nmos(x_st2, 424, facing="right", color=COL_SIG, label="M6 (CS)", sub="gm6, ro6", label_side="right")
    d.wire([(x_m2, 386), (455, 386), (455, 424), m6["g"]], color=COL_SIG)
    d.line(x_st2, m7["d"][1], x_st2, m6["d"][1], color=COL_SIG)
    d.dot(x_st2, 286, COL_SIG)
    d.line(x_st2, 286, 602, 286, color=COL_SIG)
    d.port(606, 286, "Vout", side="right", color=COL_SIG)
    d.dot(580, 286, COL_DARK)
    cl = d.cap_v(580, 345, color=COL_DARK, label="CL", label_side="right")
    d.line(580, 286, 580, cl["t"][1])
    d.gnd(580, cl["b"][1] + 8)
    d.line(580, cl["b"][1], 580, cl["b"][1] + 8)

    # Bottom GND connections
    for gx in (x_m1, x_m2, x_st2):
        d.line(gx, 448, gx, 488)
        d.gnd(gx, 488)

    d.text(330, 542, "Decouples Gain & Swing: Stage 1 gives Av1 ~ gm1·R1 ; Stage 2 gives Swing = VDD − 2·VDS,min!",
           size=10.6, color=COL_DARK, anchor="middle", weight="bold")
    d.text(330, 562, "Zero Systematic Offset Rule:  (W/L)6 / (W/L)4 = 2 · (W/L)7 / (W/L)5   =>   VGS6 = VDS4 = VGS3",
           size=10.5, color=COL_BIAS, anchor="middle", weight="bold")

    # Right Callout Cards
    d.callout(656, 76, 404, 166, "1. Two-Stage Gain & Uncompensated Danger", [
        "• Overall DC Gain: Av0 = [gm1·(ro2||ro4)] · [gm6·(ro6||ro7)]",
        "• Uncompensated has TWO high-Z nodes (Node X & Vout):",
        "  ωp1,0 = 1/(R1·C1)  and  ωp2,0 = 1/(R2·CL) -> PM ≈ 10–20°!",
        "• Output Swing: VDS,min6 ≤ Vout ≤ VDD − |VDS,min7| (Rail-near!).",
    ], tone="sig", fs=10.5)

    d.callout(656, 256, 404, 160, "2. Miller Pole Splitting & GBW (§10.5)", [
        "• Dominant Pole:     ωp1 ≈ 1 / [R1 · (1 + gm6·R2) · Cc]",
        "• Nondominant Pole:  ωp2 ≈ gm6 · Cc / [C1·CL + Cc·(C1 + CL)]",
        "                         ≈ gm6 / CL   (when Cc >> C1)",
        "• Unity-Gain GBW:    ωu ≈ gm1 / Cc   (need ωp2 ≥ 2.2·ωu)",
    ], tone="bias", fs=10.5)

    d.callout(656, 430, 404, 148, "3. Nulling Resistor Rz & Slew Rate", [
        "• Zero Location: ωz = 1 / [Cc · (1/gm6 − Rz)]",
        "  - Rz = 0 -> RHP Zero +gm6/Cc (destroys Phase Margin!)",
        "  - Rz = 1/gm6 -> Zero pushed to ∞",
        "  - Rz = (CL + Cc)/(gm6·Cc) -> LHP Zero cancels ωp2!",
        "• Slew Rate: SR = min( ISS / Cc ,  I2 / (Cc + CL) )",
    ], tone="warn", fs=10.4)
    return d


def diag_20_gain_boosted_cascode():
    d = SVGDoc(
        "gain-boosted-cascode.svg",
        "Regulated / Gain-Boosted Cascode Stage (Auxiliary Feedback Loop)",
        "Tầng Cascode Khuếch đại Độ lợi (Regulated Cascode — Vòng Hồi tiếp Bộ Khuếch đại Phụ Ch.09 §9.4)",
        "Ch.09", [9], width=1040, height=580
    )
    d.panel(22, 74, 500, 484, "Gain-Boosted Cascode Topology (M1 + M2 + Aaux)")

    cx = 335
    d.vdd(cx, 126)
    iload = d.isrc_v(cx, 170, direction="down", color=COL_BIAS, label="I0 (Cascode Load)", label_side="right")
    d.line(cx, 126, cx, iload["t"][1])

    # Vout node (y=222)
    d.line(cx, iload["b"][1], cx, 256, color=COL_SIG)
    d.dot(cx, 222, COL_SIG)
    d.line(cx, 222, 442, 222, color=COL_SIG)
    d.port(446, 222, "Vout", side="right", color=COL_SIG)

    # Cascode M2 (y=280)
    m2 = d.nmos(cx, 280, facing="right", color=COL_BIAS, label="M2", sub="gm2, ro2", label_side="right")

    # Auxiliary Amplifier Aaux on left (centered at x=190, y=280, facing right)
    # Wait: let's verify Aaux input signs!
    # Node X (source of M2 = y=342) connects to '-' (bottom or top); Vb connects to '+'!
    # With plus_top=True: top input = '+', bottom input = '-'!
    a_aux = d.opamp(195, 280, w=68, h=58, facing="right", plus_top=True,
                    label="Aaux", color=COL_AMBER, fill="#fffbeb")
    # Output of Aaux drives Gate of M2!
    d.line(a_aux["out"][0], 280, m2["g"][0], 280, color=COL_AMBER, sw=2.2)
    # '+' top input driven by Vb
    d.port(102, a_aux["in_top"][1], "Vb", side="left", color=COL_BIAS)
    d.line(106, a_aux["in_top"][1], a_aux["in_top"][0], a_aux["in_top"][1], color=COL_BIAS)
    # '-' bottom input senses Node X (y=342)!
    d.wire([a_aux["in_bot"], (132, a_aux["in_bot"][1]), (132, 342), (cx, 342)], color=COL_AMBER, sw=2.1)
    d.dot(cx, 342, COL_AMBER)
    d.text(cx + 12, 346, "Node X (VX ≈ Vb)", size=11, color=COL_AMBER, weight="bold")

    # Main input transistor M1 (y=406)
    m1 = d.nmos(cx, 406, facing="right", color=COL_SIG, label="M1", sub="gm1, ro1", label_side="right")
    d.line(cx, m2["s"][1], cx, m1["d"][1], color=COL_SIG)
    d.port(235, 406, "Vin", side="left", color=COL_SIG)
    d.line(239, 406, m1["g"][0], 406, color=COL_SIG)
    d.line(cx, m1["s"][1], cx, 466)
    d.gnd(cx, 466)

    d.text(272, 514, "Negative Feedback Loop: ΔVX -> −Aaux·ΔVX at Gate(M2)",
           size=11, color=COL_AMBER, anchor="middle", weight="bold")
    d.text(272, 535, "Equivalent to multiplying gm2 by (1 + Aaux)!",
           size=10.8, color=COL_DARK, anchor="middle")

    # Right Analytical Callouts
    d.callout(544, 76, 474, 158, "1. Super-Cascode Output Impedance (§9.4.1)", [
        "• Local feedback holds VX tightly at Vb:",
        "  vgs2 = vg2 − vx = −Aaux·vx − vx = −(1 + Aaux)·vx",
        "• Boosted Output Impedance:",
        "  Rout ≈ [1 + (1 + Aaux)·gm2·ro2]·ro1 + ro2",
        "       ≈ (1 + Aaux) · gm2 · ro2 · ro1   ~  (gm·ro)³ !",
    ], tone="sig", fs=10.7)

    d.callout(544, 248, 474, 150, "2. Low-Voltage Input ICMR Constraint on Aaux", [
        "• To preserve output swing, VX = Vb is set near VDS,min1",
        "  (~100–180 mV above GND in 65nm/45nm)!",
        "• An NMOS-input diff-pair in Aaux CANNOT operate at VX ≈ VDS,min!",
        "• Solution: Use a PMOS-input Folded-Cascode or CS stage for Aaux.",
    ], tone="amber", fs=10.7)

    d.callout(544, 412, 474, 146, "3. Pole-Zero Doublet & Stability Window (§9.4.2)", [
        "• Auxiliary loop creates a closed-loop pole-zero doublet!",
        "• Safe Bandwidth Window (Bult & Geelen / Razavi):",
        "    β · ωu,main  <  ωu,aux  <  ωp2,main (fold/cascode pole)",
        "• Too slow ωu,aux -> slow settling doublet; too fast -> rings!",
    ], tone="warn", fs=10.6)
    return d


def diag_21_cmfb_sensing_networks():
    d = SVGDoc(
        "cmfb-sensing-networks.svg",
        "Common-Mode Feedback (CMFB): Resistive, Triode-MOS & Switched-Cap",
        "Mạng Cảm biến & Hồi tiếp Chế độ chung (CMFB): Điện trở, MOS Vùng Triode và Tụ Chuyển mạch (Ch.09 §9.7)",
        "Ch.09 & 13", [9, 13], width=1080, height=590
    )
    d.panel(18,  74, 338, 492, "(a) Resistive CM Detector (+ Ccm)")
    d.panel(371, 74, 338, 492, "(b) Deep-Triode MOS CMFB")
    d.panel(724, 74, 338, 492, "(c) Switched-Capacitor SC-CMFB")

    # --- (a) Resistive CMFB ---
    d.port(58, 142, "Vout+", side="left", color=COL_SIG)
    d.port(58, 222, "Vout−", side="left", color=COL_SIG)
    r1 = d.res_h(135, 142, color=COL_DARK, label="Rcm", label_pos="top")
    r2 = d.res_h(135, 222, color=COL_DARK, label="Rcm", label_pos="bottom")
    d.line(62, 142, r1["l"][0], 142, color=COL_SIG)
    d.line(62, 222, r2["l"][0], 222, color=COL_SIG)
    d.wire([r1["r"], (192, 142), (192, 222), r2["r"]], color=COL_AMBER)
    d.dot(192, 182, COL_AMBER)
    d.text(192, 126, "Vout,CM", size=10.5, color=COL_AMBER, anchor="middle", weight="bold")

    acm = d.opamp(262, 195, w=54, h=48, facing="right", plus_top=True, label="Acm", color=COL_AMBER)
    d.line(192, 182, acm["in_top"][0], acm["in_top"][1], color=COL_AMBER)
    d.port(214, acm["in_bot"][1] + 28, "VCM,ref", side="bottom", color=COL_BIAS)
    d.wire([(214, acm["in_bot"][1] + 24), (214, acm["in_bot"][1]), acm["in_bot"]], color=COL_BIAS)
    d.line(acm["out"][0], 195, 312, 195, color=COL_BIAS)
    d.port(316, 195, "Vctrl", side="right", color=COL_BIAS)

    d.callout(32, 336, 310, 212, "Resistive Sensing Trade-Offs", [
        "• Vout,CM = (Vout+ + Vout−) / 2",
        "  (Independent of large DM swing!)",
        "• SEVERE LOADING TRAP:",
        "  Rcm appears in parallel with Rout!",
        "  Must have Rcm >> gm·ro² (huge area",
        "  & parasitic cap -> add shunt Ccm",
        "  for high-freq CM phase lead).",
    ], tone="amber", fs=10.4)

    # --- (b) Triode-MOS CMFB ---
    xm1, xm2 = 490, 590
    cx_b = 540
    d.port(cx_b, 142, "To OTA Tail / Load", side="top", color=COL_BIAS)
    d.wire([(cx_b, 146), (cx_b, 178), (xm1, 178), (xm1, 206)], color=COL_BIAS)
    d.wire([(cx_b, 178), (xm2, 178), (xm2, 206)], color=COL_BIAS)
    d.dot(cx_b, 178, COL_BIAS)

    mt1 = d.nmos(xm1, 230, facing="right", color=COL_SIG, label="Mcm1", sub="Triode", label_side="right")
    mt2 = d.nmos(xm2, 230, facing="left",  color=COL_SIG, label="Mcm2", sub="Triode", label_side="left")
    d.port(428, 230, "Vout+", side="left", color=COL_SIG)
    d.line(432, 230, mt1["g"][0], 230, color=COL_SIG)
    d.port(652, 230, "Vout−", side="right", color=COL_SIG)
    d.line(mt2["g"][0], 230, 648, 230, color=COL_SIG)

    d.wire([mt1["s"], (xm1, 282), (xm2, 282), mt2["s"]], color=COL_DARK)
    d.dot(cx_b, 282, COL_DARK)
    d.gnd(cx_b, 282)

    d.callout(385, 336, 310, 212, "Triode-MOS Trade-Offs", [
        "• Zero resistive DC loading on Vout!",
        "• Gtot = μn·Cox·(W/L)·(Vout+ + Vout− − 2VTH)",
        "  depends only on Vout,CM while in",
        "  deep triode!",
        "• LIMITATION: Restricted output swing!",
        "  If Vout+ or Vout− drops below VTH,",
        "  Mcm cuts off -> CM level shifts!",
    ], tone="sig", fs=10.4)

    # --- (c) Switched-Capacitor CMFB (SC-CMFB) ---
    d.port(764, 140, "Vout+", side="left", color=COL_SIG)
    d.port(764, 212, "Vout−", side="left", color=COL_SIG)
    cc1 = d.cap_h(846, 140, color=COL_SIG, label="Cc", label_pos="top")
    cc2 = d.cap_h(846, 212, color=COL_SIG, label="Cc", label_pos="bottom")
    d.line(768, 140, cc1["l"][0], 140, color=COL_SIG)
    d.line(768, 212, cc2["l"][0], 212, color=COL_SIG)
    d.wire([cc1["r"], (912, 140), (912, 212), cc2["r"]], color=COL_BIAS)
    d.dot(912, 176, COL_BIAS)
    d.line(912, 176, 1002, 176, color=COL_BIAS)
    d.port(1006, 176, "VCMFB", side="right", color=COL_BIAS)

    # Refresh switched capacitor Cs below (y=276)
    cs_sc = d.cap_h(895, 276, color=COL_PURPLE, label="Cs (Refresh)", label_pos="bottom")
    # Switches phi2 (connecting Cs across Cc) & phi1 (charging Cs to VCM,ref - Vb0)
    d.wire([(805, 140), (805, 276), (835, 276)], color=COL_PURPLE, dash="4,3")
    d.dot(805, 140, COL_SIG)
    sw1 = d.sw_h(855, 276, label="φ2", color=COL_PURPLE)
    sw2 = d.sw_h(945, 276, label="φ2", color=COL_PURPLE)
    d.wire([sw2["r"], (975, 276), (975, 176)], color=COL_PURPLE, dash="4,3")
    d.dot(975, 176, COL_BIAS)
    d.text(895, 318, "φ1: Precharge Cs to (VCM,ref − Vbias)", size=10.0, color=COL_PURPLE, anchor="middle", weight="bold")

    d.callout(738, 336, 310, 212, "SC-CMFB Gold Standard (§13.5)", [
        "• Zero static DC power!",
        "• Zero resistive output loading ->",
        "  preserves full (gm·ro)² DC gain!",
        "• Full rail-to-rail linear output swing!",
        "• Standard choice in Switched-Cap",
        "  amplifiers, Pipelined & ΔΣ ADCs.",
    ], tone="bias", fs=10.4)
    return d


def diag_22_pole_splitting_locus():
    d = SVGDoc(
        "pole-splitting-locus.svg",
        "Miller Compensation: Bode Pole Splitting & s-Plane Rz Zero Locus",
        "Bù Miller: Tách Cực trên Giản đồ Bode & Quỹ đạo Cực–Zero theo Điện trở Rz (Ch.10 §10.5)",
        "Ch.10", [10], width=1080, height=590, legend=False
    )
    d.panel(18,  74, 515, 492, "(a) Bode Magnitude Response: Pole Splitting")
    d.panel(549, 74, 513, 492, "(b) Complex s-Plane Pole & Rz Zero Trajectories")

    # --- (a) Bode Magnitude ---
    bx0, by0 = d.axes(68, 134, 428, 250, xlabel="log ω  [rad/s]", ylabel="|A(jω)|  [dB]")
    # 0 dB line
    y_0db = 324
    d.line(bx0, y_0db, bx0 + 422, y_0db, color=COL_SUBTLE, sw=1.3, dash="5,4")
    d.text(bx0 - 8, y_0db + 4, "0 dB", size=10.5, color=COL_MUTED, anchor="end")

    # Uncompensated curve (dashed gray/red: wp1,0 and wp2,0 close -> crosses 0 dB at -40 dB/dec!)
    d.wire([
        (bx0, 168), (bx0 + 175, 168),
        (bx0 + 235, 206),
        (bx0 + 355, 366),
    ], color=COL_SUBTLE, sw=2.0, dash="6,4")
    d.text(bx0 + 182, 160, "ωp1,0", size=10.3, color=COL_MUTED)
    d.text(bx0 + 244, 202, "ωp2,0 (Uncomp)", size=10.3, color=COL_MUTED)

    # Miller compensated curve (solid blue: wp1' pushed far left, wp2' pushed right past GBW!)
    d.wire([
        (bx0, 168), (bx0 + 58, 168),
        (bx0 + 286, y_0db),   # crosses 0 dB at -20 dB/dec!
        (bx0 + 345, 366),
        (bx0 + 395, 422 - 42),
    ], color=COL_SIG, sw=2.6)
    # RHP Zero flattening tail if Rz=0 (dashed red)
    d.wire([(bx0 + 315, 344), (bx0 + 408, 344)], color=COL_WARN, sw=2.1, dash="4,3")
    d.text(bx0 + 360, 336, "Rz=0: RHP ωz!", size=10.2, color=COL_WARN, anchor="middle", weight="bold")

    # Pole-splitting horizontal arrows!
    d.arrow(bx0 + 168, 184, bx0 + 68, 184, color=COL_SIG, sw=1.9)
    d.text(bx0 + 118, 200, "Split Left", size=10.2, color=COL_SIG, anchor="middle", weight="bold")
    d.arrow(bx0 + 245, 226, bx0 + 340, 226, color=COL_BIAS, sw=1.9)
    d.text(bx0 + 292, 242, "Split Right", size=10.2, color=COL_BIAS, anchor="middle", weight="bold")

    d.dot(bx0 + 58, 168, COL_SIG)
    d.text(bx0 + 58, 157, "ωp1'", size=10.8, color=COL_SIG, anchor="middle", weight="bold")
    d.dot(bx0 + 286, y_0db, COL_SIG)
    d.text(bx0 + 276, y_0db - 10, "GBW = gm1/Cc", size=10.5, color=COL_SIG, anchor="end", weight="bold")
    d.dot(bx0 + 345, 366, COL_BIAS)
    d.text(bx0 + 354, 372, "ωp2' ≈ gm6/CL", size=10.5, color=COL_BIAS, anchor="start", weight="bold")

    d.callout(36, 422, 478, 128, "Why ωp2 Moves UP Physically (§10.5.2)", [
        "• At high ω, Miller Cc shorts Gate and Drain of M6!",
        "• M6 becomes DIODE-CONNECTED -> output impedance drops",
        "  from R2 = ro6||ro7 down to 1/gm6 -> ωp2' ≈ gm6 / CL!",
        "• Phase Margin ≥ 60° requires ωp2' ≥ √3·GBW (~2.2x with zeros).",
    ], tone="sig", fs=10.5)

    # --- (b) s-Plane Trajectory ---
    # Origin at (x=865, y=255)
    ox, oy = 865, 255
    d.arrow(585, oy, 1032, oy, color=COL_DARK, sw=1.8)   # Real sigma axis
    d.arrow(ox, 392, ox, 118, color=COL_DARK, sw=1.8)    # Imag jw axis
    d.text(1028, oy + 18, "σ (Re)", size=11, color=COL_DARK, anchor="end", weight="bold")
    d.text(ox + 8, 128, "jω (Im)", size=11, color=COL_DARK, weight="bold")
    d.text(720, 128, "LHP (Stable)", size=11, color=COL_BIAS, anchor="middle", weight="bold")
    d.text(955, 128, "RHP (Lag!)", size=11, color=COL_WARN, anchor="middle", weight="bold")

    # Pole X marks on negative real axis
    def draw_pole_x(px, py, col, lbl, dy=-12):
        d.line(px - 5, py - 5, px + 5, py + 5, color=col, sw=2.2)
        d.line(px - 5, py + 5, px + 5, py - 5, color=col, sw=2.2)
        if lbl:
            d.text(px, py + dy, lbl, size=10.4, color=col, anchor="middle", weight="bold")

    # Uncomp poles -> Split poles
    draw_pole_x(785, oy, COL_SUBTLE, "p1,0", dy=20)
    draw_pole_x(730, oy, COL_SUBTLE, "p2,0", dy=20)
    draw_pole_x(836, oy, COL_SIG, "p1'", dy=-12)
    draw_pole_x(635, oy, COL_SIG, "p2'", dy=-12)
    d.arrow(792, oy - 6, 828, oy - 6, color=COL_SIG, sw=1.7)
    d.arrow(720, oy - 6, 646, oy - 6, color=COL_SIG, sw=1.7)

    # Zero O marks: RHP at Rz=0 -> +inf at Rz=1/gm6 -> LHP canceling p2' at Rz=(CL+Cc)/(gm6*Cc)!
    d.circle(952, oy, 5.5, fill=COL_BG, stroke=COL_WARN, sw=2.2)
    d.text(952, oy - 13, "z0 (+gm6/Cc)", size=10.3, color=COL_WARN, anchor="middle", weight="bold")
    d.text(952, oy + 20, "Rz = 0", size=10.0, color=COL_WARN, anchor="middle")
    d.arrow(962, oy - 3, 1018, oy - 3, color=COL_AMBER, sw=1.8, dash="4,3")
    d.text(995, oy - 28, "Rz->1/gm6 (z->∞)", size=9.8, color=COL_AMBER, anchor="middle")

    # LHP Zero wrapping in from -inf onto p2'!
    d.arrow(588, oy + 28, 632, oy + 8, color=COL_BIAS, sw=1.9, dash="4,3")
    d.circle(635, oy, 8.5, fill="none", stroke=COL_BIAS, sw=2.1)
    d.text(650, oy + 38, "LHP z cancels p2'!", size=10.4, color=COL_BIAS, anchor="start", weight="bold")

    d.callout(568, 422, 476, 128, "Exact Nulling Resistor Tuning Law (Eq. 10.38–10.41)", [
        "• s_zero = +1 / [Cc · (1/gm6 − Rz)]",
        "• Rz = 1 / gm6              -> Moves RHP zero to ∞",
        "• Rz = (CL + Cc)/(gm6·Cc)   -> Places LHP zero right on ωp2'!",
        "• Implement Rz with triode MOSFET biased by replica diode M!",
    ], tone="bias", fs=10.5)
    return d


def diag_23_cascode_ahuja_compensation():
    d = SVGDoc(
        "cascode-ahuja-compensation.svg",
        "Cascode (Ahuja) Compensation: Blocking RHP Feedforward Zero",
        "Bù Tần số qua Nhánh Cascode (Ahuja): Chặn Đường Truyền thẳng RHP Zero & Đẩy Cao ωp2 (Ch.10 §10.7)",
        "Ch.10", [10], width=1060, height=580
    )
    d.panel(22, 74, 535, 484, "Returning Cc to Low-Z Cascode Source Node A (Razavi Fig. 10.41)")

    x_st1, x_st2 = 205, 435
    d.vdd(x_st1, 124)
    d.vdd(x_st2, 124)

    # Stage 1 Active Load R1/I1 at top (x=205)
    i1 = d.isrc_v(x_st1, 168, direction="down", color=COL_BIAS, label="I1 (R1)", label_side="left")
    d.line(x_st1, 124, x_st1, i1["t"][1])

    # High-Z Stage-1 Output Node X (y=222) -> Gate of Stage 2 CS M2!
    d.line(x_st1, i1["b"][1], x_st1, 256, color=COL_SIG)
    d.dot(x_st1, 222, COL_SIG)
    d.text(x_st1 - 12, 220, "Node X (High-Z)", size=10.8, color=COL_SIG, anchor="end", weight="bold")
    # C1 parasitic at Node X
    c1 = d.cap_v(122, 272, color=COL_MUTED, label="C1", label_side="left")
    d.wire([(x_st1, 222), (122, 222), c1["t"]], color=COL_MUTED, dash="4,3")
    d.gnd(122, c1["b"][1] + 6)
    d.line(122, c1["b"][1], 122, c1["b"][1] + 6)

    # Stage 1 Cascode Shield M3 (y=280)
    m3 = d.nmos(x_st1, 280, facing="right", color=COL_BIAS, label="M3 (CG)", sub="gm3", label_side="right")
    d.port(145, 280, "Vb", side="left", color=COL_BIAS)
    d.line(149, 280, m3["g"][0], 280, color=COL_BIAS)

    # Low-Z Cascode Source Node A (y=342) — Cc returns HERE!
    d.line(x_st1, m3["s"][1], x_st1, 396, color=COL_SIG)
    d.dot(x_st1, 342, COL_BIAS)
    d.text(x_st1 - 12, 346, "Node A (~1/gm3)", size=10.8, color=COL_BIAS, anchor="end", weight="bold")

    # Stage 1 Input M1 (y=420)
    m1 = d.nmos(x_st1, 420, facing="right", color=COL_SIG, label="M1", sub="gm1", label_side="right")
    d.port(115, 420, "Vin", side="left", color=COL_SIG)
    d.line(119, 420, m1["g"][0], 420, color=COL_SIG)
    d.line(x_st1, m1["s"][1], x_st1, 476)
    d.gnd(x_st1, 476)

    # Stage 2 Load I2 & CS M2 (x=435)
    i2 = d.isrc_v(x_st2, 168, direction="down", color=COL_BIAS, label="I2 (R2)", label_side="right")
    d.line(x_st2, 124, x_st2, i2["t"][1])
    m2 = d.nmos(x_st2, 280, facing="right", color=COL_SIG, label="M2 (Stg 2)", sub="gm2", label_side="right")
    d.wire([(x_st1, 222), (375, 222), (375, 280), m2["g"]], color=COL_SIG)
    d.line(x_st2, i2["b"][1], x_st2, m2["d"][1], color=COL_SIG)

    # Vout node (y=342 below M2? Wait: M2 is NMOS CS, so Drain is TOP of M2 at y=236! Source is GND!)
    # Let's place Vout at Drain of M2 (y=232) and route Cc from (x_st2, 232) down to Node A (y=342)!
    d.dot(x_st2, 232, COL_SIG)
    d.line(x_st2, 232, 506, 232, color=COL_SIG)
    d.port(510, 232, "Vout", side="right", color=COL_SIG)
    cl = d.cap_v(495, 342, color=COL_DARK, label="CL (Large!)", label_side="right")
    d.dot(495, 232, COL_DARK)
    d.line(495, 232, 495, cl["t"][1])
    d.gnd(495, cl["b"][1] + 10)
    d.line(495, cl["b"][1], 495, cl["b"][1] + 10)
    d.line(x_st2, m2["s"][1], x_st2, 476)
    d.gnd(x_st2, 476)

    # Unidirectional Cascode Miller Capacitor Cc from Vout (x_st2, 232) to Node A (x_st1, 342)!
    cc = d.cap_h(320, 342, color=COL_AMBER, label="Cc (Cascode Return)", label_pos="top")
    d.line(x_st1, 342, cc["l"][0], 342, color=COL_AMBER, sw=2.3)
    d.wire([cc["r"], (395, 342), (395, 232), (x_st2, 232)], color=COL_AMBER, sw=2.3)
    d.dot(x_st2, 232, COL_AMBER)
    d.arrow(378, 360, 255, 360, color=COL_BIAS, sw=1.8)
    d.text(318, 376, "ic = s·Cc·Vout -> up M3 to X!", size=10.3, color=COL_BIAS, anchor="middle", weight="bold")

    d.text(288, 520, "Unidirectional CG Buffer M3: Conducts ic from Vout -> X,",
           size=10.8, color=COL_DARK, anchor="middle", weight="bold")
    d.text(288, 540, "while BLOCKING feedforward from Node X -> Vout (No RHP Zero)!",
           size=10.6, color=COL_WARN, anchor="middle", weight="bold")

    # Right Analytical Callouts
    d.callout(576, 76, 462, 160, "1. Elimination of RHP Feedforward Zero (§10.7)", [
        "• Standard Miller connects Cc directly to high-Z Gate X,",
        "  leaking feedforward current to Vout (ωz = +gm2/Cc).",
        "• Cascode compensation connects Cc to M3's source (Node A):",
        "  Node X cannot drive Vout through M3's drain-to-source!",
        "• Only LHP zero at ωz = −gm3 / Cc (far at high frequency).",
    ], tone="bias", fs=10.6)

    d.callout(576, 250, 462, 160, "2. Higher Nondominant Pole for Heavy CL!", [
        "• Dominant Pole unchanged:  ωp1 ≈ 1 / (gm2 · R2 · R1 · Cc)",
        "• Output Pole BOOSTED by (Cc / C1):",
        "    ωp2 ≈ (Cc / C1) · (gm2 / CL)   >>   gm2 / CL !",
        "• Enables high GBW when driving huge capacitive loads CL",
        "  (e.g., LDO pass-gate or off-chip pads without huge I2)!",
    ], tone="sig", fs=10.6)

    d.callout(576, 424, 462, 134, "3. Complex-Pole Ringing Caveat", [
        "• Finite gm3 introduces a 3rd-order loop with Node A & C1;",
        "  if gm3 is too small, ωp2 & ωp3 form underdamped complex",
        "  conjugate poles (gain peaking near ωu -> check STB!).",
    ], tone="amber", fs=10.6)
    return d


def diag_24_nyquist_polar_stability():
    d = SVGDoc(
        "nyquist-polar-stability.svg",
        "Nyquist Polar Stability Plot: Stable, Unstable & Conditionally Stable Loops",
        "Biểu đồ Cực Nyquist: Hệ Ổn định, Mất ổn định & Ổn định Có điều kiện quanh (−1, j0) (Ch.10 §10.8)",
        "Ch.10", [10], width=1060, height=580, legend=False
    )
    d.panel(20, 74, 540, 484, "Polar Loop Transmission βH(jω) Plane (ω: 0 -> +∞)")

    # Polar origin at (355, 290)
    ox, oy = 355, 290
    d.circle(ox, oy, 155, fill="none", stroke="#e2e8f0", sw=1.4, dash="5,4")
    d.text(ox + 92, oy - 146, "|βH| = 1 (0 dB)", size=10.3, color=COL_MUTED, anchor="middle")

    d.arrow(65, oy, 535, oy, color=COL_DARK, sw=1.8)
    d.arrow(ox, 525, ox, 108, color=COL_DARK, sw=1.8)
    d.text(530, oy - 10, "Re{βH}", size=11, color=COL_DARK, anchor="end", weight="bold")
    d.text(ox + 10, 120, "Im{βH}", size=11, color=COL_DARK, weight="bold")

    # Critical Barkhausen Point (-1, j0) at ox - 155 = 200, oy = 290
    crit_x = ox - 155
    d.circle(crit_x, oy, 5.5, fill=COL_WARN, stroke=COL_BG, sw=1.8)
    d.text(crit_x - 10, oy - 12, "(−1, j0)", size=11.5, color=COL_WARN, anchor="end", weight="bold")

    # 1. Stable 2/3-pole system (Emerald: crosses negative real axis at -0.35 inside unit circle)
    d.path(
        f"M {ox + 150} {oy} C {ox + 150} {oy + 150}, {ox - 55} {oy + 115}, {ox - 55} {oy} "
        f"C {ox - 55} {oy - 28}, {ox - 12} {oy - 14}, {ox} {oy}",
        stroke=COL_BIAS, sw=2.4
    )
    d.text(ox + 58, oy + 118, "1. Unconditionally Stable", size=10.8, color=COL_BIAS, weight="bold")

    # 2. Unstable 3-pole system (Red dashed: crosses to LEFT of (-1, j0) at -1.45 -> encircles -1!)
    d.path(
        f"M {ox + 165} {oy} C {ox + 165} {oy + 215}, {ox - 225} {oy + 165}, {ox - 225} {oy} "
        f"C {ox - 225} {oy - 55}, {ox - 60} {oy - 35}, {ox} {oy}",
        stroke=COL_WARN, sw=2.2, dash="6,4"
    )
    d.text(ox - 210, oy + 145, "2. Unstable (Encircles −1)", size=10.8, color=COL_WARN, weight="bold")

    # 3. Conditionally Stable system (Blue: crosses < -1, loops above, crosses back > -1 before origin!)
    # Wait: let's draw a crystal-clear textbook conditionally stable contour where (-1, 0) sits in the safe pocket!
    d.path(
        f"M {ox + 160} {oy} "
        f"C {ox + 140} {oy + 195}, {ox - 255} {oy + 120}, {ox - 245} {oy} "
        f"C {ox - 238} {oy - 72}, {ox - 105} {oy - 68}, {ox - 115} {oy} "
        f"C {ox - 122} {oy + 36}, {ox - 45} {oy + 28}, {ox} {oy}",
        stroke=COL_SIG, sw=2.4
    )
    d.text(ox - 175, oy - 72, "3. Conditionally Stable Pocket", size=10.8, color=COL_SIG, weight="bold")

    # Right Callout Cards
    d.callout(580, 76, 460, 162, "1. Cauchy Principle & Nyquist Criterion (§10.8)", [
        "• Closed-Loop RHP Poles:   Z = N + P",
        "  - P = open-loop RHP poles of βH(s)  (usually P = 0)",
        "  - N = net clockwise encirclements of (−1, j0) as ω: −∞ -> +∞",
        "• Stability Requirement: Z = 0  (so N = 0 when P = 0!).",
        "• Mirror Im{βH(−jω)} = −Im{βH(+jω)} across the Real axis!",
    ], tone="sig", fs=10.6)

    d.callout(580, 252, 460, 156, "2. Why Bode Plots Fail on Multipole Loops!", [
        "• Curve 3 crosses ∠βH = −180° at |βH| > 1 (looks unstable",
        "  by naive Bode rule!), yet phase recovers > −180° before",
        "  |βH| drops through 0 dB -> N = 0 encirclements (STABLE)!",
        "• Danger: Dropping loop gain (slewing / startup saturation)",
        "  shrinks Curve 3 so (−1, j0) gets encircled -> OSCILLATES!",
    ], tone="warn", fs=10.6)

    d.callout(580, 422, 460, 136, "3. Handling Origin Poles (Type-II PLL / Integrators)", [
        "• Each pole at s = 0 adds a clockwise semicircle of ∞ radius",
        "  in the s-plane indent detour -> 90° phase shift at ω = 0+.",
        "• Always inspect Spectre STB Nyquist plot alongside Bode PM/GM!",
    ], tone="bias", fs=10.6)
    return d


def diag_25_supply_independent_bias_startup():
    d = SVGDoc(
        "supply-independent-bias-startup.svg",
        "Constant-Gm Supply-Independent Bias Loop WITH Startup Circuit",
        "Mạch Phân cực Độc lập Nguồn cấp (Constant-Gm) kèm Mạch Khởi động Thoát Điểm Chết I=0 (Ch.12 §12.1–12.2)",
        "Ch.12", [12], width=1080, height=600
    )
    d.panel(20,  74, 620, 504, "Startup Circuit (Red) + Constant-Gm Self-Biased Core (Green/Blue)")
    d.panel(658, 74, 402, 504, "Dual Equilibrium States & Constant-Gm Law")

    # Startup branch on left (x=115, x=235) + Core loop on right (x=370, x=510)
    x_su1, x_su2, x_l, x_r = 120, 240, 385, 525

    for vx in (x_su1, x_l, x_r):
        d.vdd(vx, 126)

    # Core PMOS 1:1 Mirror: M3 (left) & M4 (right, diode-connected -> loop gain < 1!)
    m3 = d.pmos(x_l, 188, facing="right", color=COL_BIAS, label="M3 (1x)", label_side="left")
    m4 = d.pmos(x_r, 188, facing="left",  color=COL_BIAS, label="M4 (1x)", sub="Diode", label_side="right")
    d.line(x_l, 126, x_l, m3["s"][1])
    d.line(x_r, 126, x_r, m4["s"][1])
    d.line(m3["g"][0], 188, m4["g"][0], 188, color=COL_BIAS)
    # M4 diode connection
    d.wire([(x_r, 232), (x_r - 42, 232), (x_r - 42, 188)], color=COL_BIAS)
    d.dot(x_r, 232, COL_BIAS)
    d.dot(x_r - 42, 188, COL_BIAS)
    d.text((x_l + x_r) / 2, 174, "VP (PMOS Bias)", size=10.6, color=COL_BIAS, anchor="middle", weight="bold")

    # Core NMOS 1:K Degenerated Mirror: M1 (left, 1x, diode-connected) & M2 (right, Kx + RS)
    m1 = d.nmos(x_l, 342, facing="left",  color=COL_SIG, label="M1 (1x)", sub="Diode", label_side="left")
    m2 = d.nmos(x_r, 342, facing="right", color=COL_SIG, label="M2 (K·x)", label_side="right")
    d.line(x_l, m3["d"][1], x_l, m1["d"][1], color=COL_BIAS)
    d.line(x_r, m4["d"][1], x_r, m2["d"][1], color=COL_BIAS)
    d.line(m1["g"][0], 342, m2["g"][0], 342, color=COL_SIG)
    d.wire([(x_l, 294), (x_l + 42, 294), (x_l + 42, 342)], color=COL_SIG)
    d.dot(x_l, 294, COL_SIG)
    d.dot(x_l + 42, 342, COL_SIG)
    d.text((x_l + x_r) / 2, 330, "VN (NMOS Bias)", size=10.6, color=COL_SIG, anchor="middle", weight="bold")

    # Source degeneration RS under M2!
    rs = d.res_v(x_r, 426, color=COL_AMBER, label="RS", sub="Sets gm1!", label_side="right")
    d.line(x_r, m2["s"][1], x_r, rs["t"][1], color=COL_SIG)
    d.line(x_r, rs["b"][1], x_r, 488)
    d.gnd(x_r, 488)
    d.line(x_l, m1["s"][1], x_l, 488)
    d.gnd(x_l, 488)

    # Startup Circuit (Left):
    # High-R pull-up PMOS Msu1 (gate GND) -> Node S -> Inverter/pull-down Msu2 (gate VN) -> Gate of Msu3!
    # Wait: even cleaner textbook CMOS startup:
    # Msu1 (weak PMOS pull-up, gate=GND) pulls Node S high when VN=0 (Msu2 NMOS OFF);
    # Node S drives Gate of Msu3 (NMOS pulling VP down to inject current into M3/M1!).
    # Once VN rises to VGS1, Msu2 turns ON strongly, pulling Node S to GND -> Msu3 turns OFF completely!
    msu1 = d.pmos(x_su1, 188, facing="right", color=COL_WARN, label="Msu1", sub="Long L", label_side="right")
    d.line(x_su1, 126, x_su1, msu1["s"][1], color=COL_WARN)
    d.wire([msu1["g"], (x_su1 - 42, 188), (x_su1 - 42, 224)], color=COL_DARK)
    d.gnd(x_su1 - 42, 224)

    msu2 = d.nmos(x_su1, 342, facing="left", color=COL_WARN, label="Msu2", sub="Sense VN", label_side="left")
    d.line(x_su1, msu1["d"][1], x_su1, msu2["d"][1], color=COL_WARN)
    d.dot(x_su1, 266, COL_WARN)
    d.text(x_su1 - 10, 264, "VS", size=10.5, color=COL_WARN, anchor="end", weight="bold")
    # Connect Msu2 gate to VN!
    d.wire([msu2["g"], (x_su1 + 52, 342), (x_su1 + 52, 466), (x_l + 42, 466), (x_l + 42, 342)],
           color=COL_SIG, dash="5,3")
    d.line(x_su1, msu2["s"][1], x_su1, 488)
    d.gnd(x_su1, 488)

    # Inject NMOS Msu3 at x_su2=240: Gate=VS (266), Drain pulls VP (188), Source=GND!
    msu3 = d.nmos(x_su2, 266, facing="right", color=COL_WARN, label="Msu3", sub="Injector", label_side="right")
    d.line(x_su1, 266, msu3["g"][0], 266, color=COL_WARN, sw=2.0)
    d.wire([msu3["d"], (x_su2, 188), m3["g"]], color=COL_WARN, sw=2.0, dash="5,3")
    d.dot(m3["g"][0], 188, COL_WARN)
    d.line(x_su2, msu3["s"][1], x_su2, 488)
    d.gnd(x_su2, 488)

    d.text(330, 535, "At I=0 (VN=0): Msu2 OFF -> VS=VDD -> Msu3 ON -> pulls VP down to start loop!",
           size=10.5, color=COL_WARN, anchor="middle", weight="bold")
    d.text(330, 555, "Normal OP (VN=VGS1): Msu2 ON (strong) -> VS≈0 -> Msu3 OFF (zero leakage into loop!)",
           size=10.5, color=COL_BIAS, anchor="middle", weight="bold")

    # --- Right Panel: I1 vs I2 Intersection Curve + Equations ---
    ix0, iy0 = d.axes(705, 134, 315, 195, xlabel="I_branch1", ylabel="I_branch2")
    # 1:1 mirror straight line I2 = I1
    d.line(ix0, iy0, ix0 + 285, iy0 - 178, color=COL_BIAS, sw=2.2)
    d.text(ix0 + 282, iy0 - 184, "PMOS: I2 = I1", size=10.4, color=COL_BIAS, anchor="end", weight="bold")
    # Degenerated NMOS curve (starts steep slope K > 1 at origin, bends flat due to RS!)
    d.path(f"M {ix0} {iy0} Q {ix0 + 55} {iy0 - 118} {ix0 + 290} {iy0 - 142}",
           stroke=COL_SIG, sw=2.4)
    d.text(ix0 + 292, iy0 - 122, "NMOS + RS", size=10.4, color=COL_SIG, anchor="end", weight="bold")

    # Highlight BOTH intersections: (0,0) Dead State and (Iout, Iout) Desired OP!
    d.circle(ix0, iy0, 5.5, fill=COL_WARN, stroke=COL_BG, sw=1.8)
    d.text(ix0 + 14, iy0 - 8, "Dead State I = 0!", size=10.5, color=COL_WARN, weight="bold")
    d.circle(ix0 + 206, iy0 - 129, 5.5, fill=COL_BIAS, stroke=COL_BG, sw=1.8)
    d.text(ix0 + 195, iy0 - 142, "Desired Stable OP", size=10.5, color=COL_BIAS, anchor="end", weight="bold")

    d.callout(674, 366, 370, 196, "Constant-Gm Equations (Razavi Eq. 12.6–12.8)", [
        "• Positive-FB Loop Gain < 1 requires RS on larger M2!",
        "• Reference Current:",
        "  Iout = [2 / (μn·Cox·(W/L)N·RS²)] · (1 − 1/√K)²",
        "• Transconductance Stabilized to RS:",
        "  gm1 = 2 · (1 − 1/√K) / RS   (if K=4 -> gm1 = 1/RS!)",
        "• Mandatory Verification: Transient VDD slow/fast PWL",
        "  ramp from 0 V across SS/FF corners!",
    ], tone="sig", fs=10.4)
    return d


# ==============================================================================
# PART 4: DIAGRAMS 26 - 38 (Bandgap, LDO, SC, PLL, Mismatch, Layout, Master Map)
# ==============================================================================

def diag_26_bandgap_reference_core():
    d = SVGDoc(
        "bandgap-reference-core.svg",
        "Classic CMOS Bandgap Reference: CTAT + PTAT & Op-Amp Offset Trap",
        "Mạch Tham chiếu Vùng cấm CMOS Kinh điển: Bù nhiệt CTAT + PTAT & Bẫy Khuếch đại Offset VOS (Ch.12 §12.3)",
        "Ch.12", [12], width=1080, height=600
    )
    d.panel(20,  74, 590, 504, "Op-Amp Clamped Bandgap Core (Razavi Fig. 12.11–12.12)")
    d.panel(628, 74, 432, 504, "Zero-TC Curvature & Fatal (1 + R2/R3)·VOS Error")

    # Left Schematic: Op-Amp A1 output = VREF driving top bus (y=138) of R1 (left, x=170) & R2 (right, x=305)
    xl, xr = 165, 305
    # Top VREF rail from Op-Amp output (x=515, y=225 -> up to y=132 -> left to xl)
    op = d.opamp(455, 225, w=64, h=56, facing="right", plus_top=True,
                 label="A1", color=COL_SIG, fill="#eff6ff")
    d.wire([op["out"], (530, 225), (530, 132), (xl, 132)], color=COL_SIG, sw=2.2)
    d.dot(530, 225, COL_SIG)
    d.line(530, 225, 552, 225, color=COL_SIG, sw=2.2)
    d.port(556, 225, "VREF", side="right", color=COL_SIG)
    d.dot(xr, 132, COL_SIG)

    # Top equal branch resistors R1 & R2 (y=176)
    r1 = d.res_v(xl, 176, color=COL_DARK, label="R1", label_side="left")
    r2 = d.res_v(xr, 176, color=COL_DARK, label="R2 (=R1)", label_side="right")
    d.line(xl, 132, xl, r1["t"][1], color=COL_SIG)
    d.line(xr, 132, xr, r2["t"][1], color=COL_SIG)

    # Nodes X (xl, 212) -> '+' input (with VOS in series!) and Y (xr, 238) -> '-' input!
    d.line(xl, r1["b"][1], xl, 366, color=COL_BIAS)
    d.dot(xl, 212, COL_BIAS)
    d.text(xl - 10, 216, "VX", size=11, color=COL_BIAS, anchor="end", weight="bold")
    vos = d.vsrc_h(366, 212, color=COL_WARN, label="VOS", label_pos="top")
    d.line(xl, 212, vos["l"][0], 212, color=COL_BIAS)
    d.line(vos["r"][0], 212, op["in_top"][0], 212, color=COL_WARN)

    d.line(xr, r2["b"][1], xr, 280, color=COL_AMBER)
    d.dot(xr, 238, COL_AMBER)
    d.text(xr - 10, 242, "VY", size=11, color=COL_AMBER, anchor="end", weight="bold")
    d.line(xr, 238, op["in_bot"][0], 238, color=COL_AMBER)

    # PTAT resistor R3 above Q2 on right branch (y=304)
    r3 = d.res_v(xr, 304, color=COL_AMBER, label="R3", sub="ΔVBE=VT·ln(n)", label_side="right")
    d.line(xr, r3["b"][1], xr, 366, color=COL_AMBER)

    # Substrate PNP Q1 (1xA) & Q2 (n*A) at y=390
    q1 = d.bjt_pnp(xl, 390, facing="right", color=COL_BIAS, label="Q1 (1·A)", sub="VBE1 (CTAT)", label_side="right")
    q2 = d.bjt_pnp(xr, 390, facing="right", color=COL_AMBER, label="Q2 (n·A)", sub="VBE2", label_side="right")
    # Bases & Collectors tied to P-substrate GND!
    d.wire([q1["b"], (xl - 36, 390), (xl - 36, 444), (xl, 444), q1["c"]], color=COL_DARK)
    d.dot(xl, 444, COL_DARK)
    d.gnd(xl, 444)

    d.wire([q2["b"], (xr - 36, 390), (xr - 36, 444), (xr, 444), q2["c"]], color=COL_DARK)
    d.dot(xr, 444, COL_DARK)
    d.gnd(xr, 444)

    d.text(315, 504, "Feedback Polarity: Node Y (R3 + Q2) MUST drive (−) input so β− > β+!",
           size=10.8, color=COL_DARK, anchor="middle", weight="bold")
    d.text(315, 526, "Zero-TC Condition:  (1 + R2/R3)·ln(n) ≈ 17.2   =>   VREF ≈ 1.25 V",
           size=11, color=COL_SIG, anchor="middle", weight="bold")
    d.text(315, 548, "(Needs Startup Circuit to escape VREF = 0 degenerate state)",
           size=10.4, color=COL_MUTED, anchor="middle")

    # Right Panel: Temperature Cancellation Plot + Offset Formula
    tx0, ty0 = d.axes(678, 134, 342, 196, xlabel="Temperature T [K]", ylabel="Voltage [V]")
    # CTAT VBE falling (-1.5 mV/K)
    d.line(tx0 + 18, 195, tx0 + 318, 286, color=COL_BIAS, sw=2.0, dash="5,4")
    d.text(tx0 + 318, 302, "VBE (CTAT: −1.5 mV/K)", size=10.3, color=COL_BIAS, anchor="end", weight="bold")
    # Scaled PTAT rising (+1.5 mV/K)
    d.line(tx0 + 18, 298, tx0 + 318, 207, color=COL_AMBER, sw=2.0, dash="5,4")
    d.text(tx0 + 318, 200, "α·VT·ln(n) (PTAT: +1.5 mV/K)", size=10.3, color=COL_AMBER, anchor="end", weight="bold")
    # Sum VREF ~ 1.25V bowed curve (2nd-order curvature)
    d.path(f"M {tx0 + 18} 184 Q {tx0 + 185} 158 {tx0 + 318} 184", stroke=COL_SIG, sw=2.6)
    d.dot(tx0 + 185, 171, COL_SIG)
    d.text(tx0 + 205, 160, "VREF(T0) ≈ 1.25 V (∂V/∂T = 0)", size=10.5, color=COL_SIG, anchor="middle", weight="bold")

    d.callout(646, 366, 396, 196, "Bandgap & Offset Equations (Eq. 12.23 & 12.33)", [
        "• Ideal Output:",
        "  VREF = VBE2 + (1 + R2/R3)·VT·ln(n) = VBE1 + (R2/R3)·VT·ln(n)",
        "• FATAL OP-AMP OFFSET TRAP:",
        "  VREF ≈ VBE1 + (R2/R3)·VT·ln(n) − (1 + R2/R3)·VOS !",
        "  - Non-PTAT VOS gets multiplied by ~8–12x, corrupting",
        "    BOTH absolute accuracy AND temperature coefficient!",
        "  - Mitigation: Large n (e.g., n=8 or 24), series 2-diode",
        "    stack, large input pair WL, or chopper/auto-zero A1.",
    ], tone="warn", fs=10.3)
    return d


def diag_27_low_voltage_sub1v_bandgap():
    d = SVGDoc(
        "low-voltage-sub1v-bandgap.svg",
        "Low-Voltage Sub-1V Current-Mode Bandgap Reference (Banba / Razavi §12.7)",
        "Mạch Tham chiếu Vùng cấm Phân số Dưới 1V theo Chế độ Dòng (Banba — Razavi Ch.12 §12.7 Fig. 12.33)",
        "Ch.12", [12], width=1080, height=600
    )
    d.panel(20, 74, 620, 504, "Current-Summing Fractional Bandgap Core (VDD ≤ 1.0 V)")

    x_x, x_y, x_out = 175, 345, 535
    for vx in (x_x, x_y, x_out):
        d.vdd(vx, 124)

    # PMOS Current Mirror M3 (left), M4 (middle), M5 (output right) at y=172
    m3 = d.pmos(x_x,   172, facing="left",  color=COL_BIAS, label="M3", label_side="left")
    m4 = d.pmos(x_y,   172, facing="left",  color=COL_BIAS, label="M4", label_side="left")
    m5 = d.pmos(x_out, 172, facing="right", color=COL_SIG,  label="M5", sub="Mirrors ICTAT+IPTAT", label_side="left")
    for vx, m in ((x_x, m3), (x_y, m4), (x_out, m5)):
        d.line(vx, 124, vx, m["s"][1])

    # Common gate line for M3, M4, M5 at y=172 driven by Op-Amp A1!
    op = d.opamp(262, 248, w=54, h=46, facing="left", plus_top=False,
                 label="A1", color=COL_AMBER, fill="#fffbeb")
    # Wait: let's place A1 cleanly at (x=445, y=248, facing="right") or wire gates cleanly without overlap!
    # Remove that opamp and place A1 at (445, 250) facing right -> output goes up to gate bus y=138!
    d.elements = d.elements[:-6]
    # Gate bus at y=140 connecting gates of M3 (205), M4 (375), M5 (505)
    d.wire([m3["g"], (m3["g"][0], 140), (m5["g"][0], 140), m5["g"]], color=COL_BIAS)
    d.wire([m4["g"], (m4["g"][0], 140)], color=COL_BIAS)
    d.dot(m4["g"][0], 140, COL_BIAS)

    op = d.opamp(445, 246, w=54, h=46, facing="right", plus_top=False,
                 label="A1", color=COL_AMBER, fill="#fffbeb")
    # A1 output -> up to gate bus (490, 140)
    d.wire([op["out"], (486, 246), (486, 140)], color=COL_AMBER, sw=2.0)
    d.dot(486, 140, COL_AMBER)

    # Node X (x=175, y=233) & Node Y (x=345, y=259)
    d.line(x_x, m3["d"][1], x_x, 366, color=COL_BIAS)
    d.line(x_y, m4["d"][1], x_y, 294, color=COL_AMBER)
    d.dot(x_x, 233, COL_BIAS)
    d.dot(x_y, 259, COL_AMBER)
    d.text(x_x - 10, 230, "VX", size=11, color=COL_BIAS, anchor="end", weight="bold")
    d.text(x_y - 10, 256, "VY", size=11, color=COL_AMBER, anchor="end", weight="bold")
    # Wire VX -> A1 in_top ('-'), VY -> A1 in_bot ('+')!
    # Wait: let's check feedback sign when A1 drives PMOS gates M3, M4!
    # PMOS M3, M4 add an EXTRA inversion (VG drops -> ID rises -> VX, VY rise)!
    # Since Y branch (R1 + Q2) is higher impedance than X branch (Q1), ΔVY > ΔVX when VG drops!
    # To make VG RISE when VY > VX (negative feedback!), Y MUST connect to '+' and X MUST connect to '−'!
    # With plus_top=False, in_top is '−' (connected to VX) and in_bot is '+' (connected to VY)! 100% exact!
    d.line(x_x, 233, op["in_top"][0], 233, color=COL_BIAS)
    d.line(x_y, 259, op["in_bot"][0], 259, color=COL_AMBER)

    # Shunt CTAT resistors R3 (at X, x=105) & R2 (at Y, x=275) to GND!
    r3 = d.res_v(105, 390, color=COL_BIAS, label="R3 (=R2)", sub="ICTAT", label_side="left")
    d.wire([(x_x, 280), (105, 280), r3["t"]], color=COL_BIAS)
    d.dot(x_x, 280, COL_BIAS)
    d.line(105, r3["b"][1], 105, 468)
    d.gnd(105, 468)

    r2 = d.res_v(275, 390, color=COL_BIAS, label="R2", sub="ICTAT", label_side="left")
    d.wire([(x_y, 280), (275, 280), r2["t"]], color=COL_BIAS)
    d.dot(x_y, 280, COL_AMBER)
    d.line(275, r2["b"][1], 275, 468)
    d.gnd(275, 468)

    # Series PTAT resistor R1 above Q2 on branch Y
    r1 = d.res_v(x_y, 318, color=COL_AMBER, label="R1", sub="IPTAT", label_side="right")
    d.line(x_y, r1["b"][1], x_y, 376, color=COL_AMBER)

    # Substrate PNPs Q1 (x_x) & Q2 (x_y) at y=400
    q1 = d.bjt_pnp(x_x, 400, facing="right", color=COL_DARK, label="Q1 (A)", label_side="right")
    q2 = d.bjt_pnp(x_y, 400, facing="right", color=COL_DARK, label="Q2 (nA)", label_side="right")
    for qx, q in ((x_x, q1), (x_y, q2)):
        d.wire([q["b"], (qx - 34, 400), (qx - 34, 468), (qx, 468), q["c"]], color=COL_DARK)
        d.dot(qx, 468, COL_DARK)
        d.gnd(qx, 468)

    # Output Branch M5 -> VBG node -> R4 to GND!
    d.line(x_out, m5["d"][1], x_out, 366, color=COL_SIG)
    d.dot(x_out, 305, COL_SIG)
    d.line(x_out, 305, 588, 305, color=COL_SIG)
    d.port(592, 305, "VBG", side="right", color=COL_SIG)
    r4 = d.res_v(x_out, 390, color=COL_SIG, label="R4", sub="Scales VBG!", label_side="right")
    d.line(x_out, r4["b"][1], x_out, 468)
    d.gnd(x_out, 468)

    d.text(330, 526, "IC,sum = |VBE1| / R2  (CTAT)  +  VT·ln(n) / R1  (PTAT)",
           size=11, color=COL_DARK, anchor="middle", weight="bold")
    d.text(330, 548, "Max Internal Node Voltage = |VBE1| + |VDS,min| ≈ 0.85 V  ->  Works at VDD = 0.9 V!",
           size=10.6, color=COL_BIAS, anchor="middle", weight="bold")

    # Right Analytical Callouts
    d.callout(656, 76, 404, 168, "1. Why Classic 1.25V BGR Fails in Nanometer CMOS", [
        "• Voltage-mode BGR stacks PTAT + CTAT to VREF ≈ 1.25 V,",
        "  demanding VDD ≥ 1.4 V — impossible in 65nm/45nm core",
        "  supplies (VDD = 0.9 V – 1.1 V)!",
        "• Solution (Banba 1999 / Razavi §12.7): Sum CTAT and PTAT",
        "  CURRENTS at low node voltage VX = VY = |VBE1| ≈ 0.7 V!",
    ], tone="sig", fs=10.5)

    d.callout(656, 260, 404, 160, "2. Fractional Bandgap Output Equation (Eq. 12.73)", [
        "• Mirrored output current into R4 gives ANY sub-1V target:",
        "  VBG = (R4 / R2) · [ |VBE1| + (R2 / R1)·VT·ln(n)",
        "                      − (1 + R2 / R1)·VOS ]",
        "• Resistor ratio R4/R2 cancels sheet-resistance TC,",
        "  yielding e.g. VBG = 0.60 V with ∂VBG/∂T = 0!",
    ], tone="bias", fs=10.5)

    d.callout(656, 436, 404, 142, "3. Low-VDD Design Checks in 65nm / 45nm", [
        "• Op-Amp A1 input CM sits at |VBE1| ≈ 0.7 V -> use PMOS",
        "  or low-VTH NMOS input pair depending on cold-corner VBE!",
        "• M3–M5 VDS mismatch corrupts current ratio unless L is long!",
    ], tone="amber", fs=10.5)
    return d


def diag_28_cmos_ldo_regulator():
    d = SVGDoc(
        "cmos-ldo-regulator.svg",
        "CMOS Low-Dropout (LDO) Regulator: Poles, ESR Zero & PSRR Path",
        "Bộ Ổn áp Sụt áp Thấp CMOS (LDO): Linh kiện Truyền PMOS, Cực Tải, Zero ESR & Đường PSRR (Ch.08/10/12)",
        "Ch.08/10/12", [8, 10, 12], width=1080, height=600
    )
    d.panel(20, 74, 625, 504, "PMOS-Pass LDO Topology (Voltage–Voltage Feedback)")

    # Unregulated VIN supply rail at top (y=126)
    x_mp = 385
    d.vdd(x_mp, 126, label="VIN (Unreg)", color=COL_WARN)
    # Error Amp on left (x=195, y=205) — '+' at bottom (VFB), '-' at top (VREF)!
    ea = d.opamp(195, 205, w=68, h=58, facing="right", plus_top=False,
                 label="EA", color=COL_SIG, fill="#eff6ff")
    d.port(96, ea["in_top"][1], "VREF (BGR)", side="left", color=COL_BIAS)
    d.line(100, ea["in_top"][1], ea["in_top"][0], ea["in_top"][1], color=COL_BIAS)

    # PMOS Pass Device MP (x=385, y=205)
    mp = d.pmos(x_mp, 205, facing="right", color=COL_SIG, label="MP (Pass)", sub="Large W/L!", label_side="right")
    d.line(x_mp, 126, x_mp, mp["s"][1], color=COL_WARN, sw=2.3)
    d.line(ea["out"][0], 205, mp["g"][0], 205, color=COL_SIG, sw=2.2)
    d.dot(295, 205, COL_AMBER)
    # Gate parasitic Cg at node VG (x=295)
    cg = d.cap_v(295, 148, color=COL_AMBER, label="Cg (Huge!)", label_side="left")
    d.line(295, 205, 295, cg["b"][1], color=COL_AMBER)
    d.vdd(295, cg["t"][1], label="VIN", color=COL_WARN)
    d.text(295, 224, "Node VG (ωp,g)", size=10.4, color=COL_AMBER, anchor="middle", weight="bold")

    # Regulated VOUT horizontal rail at y=275 (x=385 -> 585)
    d.line(x_mp, mp["d"][1], x_mp, 315, color=COL_SIG, sw=2.3)
    d.dot(x_mp, 275, COL_SIG)
    d.line(x_mp, 275, 588, 275, color=COL_SIG, sw=2.4)
    d.port(592, 275, "VOUT", side="right", color=COL_SIG)
    d.dot(475, 275, COL_SIG)
    d.dot(555, 275, COL_AMBER)

    # Resistive Feedback Divider Rf1 & Rf2 at x=385
    rf1 = d.res_v(x_mp, 339, color=COL_DARK, label="Rf1", label_side="right")
    d.line(x_mp, 363, x_mp, 412, color=COL_SIG)
    d.dot(x_mp, 386, COL_SIG)
    # Feedback wire from VFB (385, 386) left to EA '+' bottom input!
    d.wire([(x_mp, 386), (132, 386), (132, ea["in_bot"][1]), ea["in_bot"]], color=COL_SIG, sw=2.0)
    d.text(255, 378, "VFB -> (+) EA Input (MP inverts!)", size=10.5, color=COL_SIG, anchor="middle", weight="bold")
    rf2 = d.res_v(x_mp, 436, color=COL_DARK, label="Rf2", label_side="right")
    d.line(x_mp, rf2["b"][1], x_mp, 488)
    d.gnd(x_mp, 488)

    # Variable Load Current ILOAD at x=475
    iload = d.isrc_v(475, 390, direction="down", color=COL_DARK, label="ILOAD", sub="0 -> Imax", label_side="left")
    d.line(475, 275, 475, iload["t"][1])
    d.line(475, iload["b"][1], 475, 488)
    d.gnd(475, 488)

    # Off-chip / On-chip Output Capacitor Cout + RESR at x=555
    cout = d.cap_v(555, 345, color=COL_AMBER, label="Cout", label_side="right")
    resr = d.res_v(555, 428, color=COL_AMBER, label="RESR", sub="LHP ωz!", label_side="right")
    d.line(555, 275, 555, cout["t"][1], color=COL_AMBER)
    d.line(555, cout["b"][1], 555, resr["t"][1], color=COL_AMBER)
    d.line(555, resr["b"][1], 555, 488, color=COL_AMBER)
    d.gnd(555, 488)

    d.text(332, 536, "Regulated Output:  VOUT = VREF · (1 + Rf1 / Rf2)   |   Dropout:  VDO = VDS,min(MP)",
           size=10.8, color=COL_DARK, anchor="middle", weight="bold")
    d.text(332, 556, "PSRR Trap: ΔVIN couples via MP's ro,p AND Cgs,p unless VG tracks ΔVIN!",
           size=10.5, color=COL_WARN, anchor="middle")

    # Right Analytical Callouts
    d.callout(662, 76, 398, 168, "1. Polarity & Two-Pole Stability Hazard", [
        "• PMOS MP is a Common-Source stage (inverting from VG to VOUT),",
        "  so feedback VFB MUST enter EA's (+) non-inverting terminal!",
        "• Two Low-Frequency Poles fight for dominance:",
        "  - Output Pole: ωp,out = 1 / [(ro,p || RLOAD) · Cout]",
        "  - Gate Pole:   ωp,g   = 1 / [Rout,EA · (Cgs,p + (1+Av,p)Cgd,p)]",
    ], tone="sig", fs=10.4)

    d.callout(662, 258, 398, 160, "2. Load-Dependent Pole Shift & Compensation", [
        "• As ILOAD varies from 10 μA -> 100 mA, ro,p drops ~1000x ->",
        "  ωp,out shifts across 3–4 DECADES! Worst PM vary by LDO type:",
        "  - Off-chip μF Cout (ωp,out dominant): Stabilize via RESR",
        "    LHP zero ωz,ESR = 1 / (RESR · Cout) (watchlight-load!).",
        "  - Capless on-chip LDO: Use Ahuja/Miller + buffer on VG!",
    ], tone="amber", fs=10.4)

    d.callout(662, 432, 398, 146, "3. Transient Droop & PSRR Across Frequency", [
        "• Load-Step Undershoot:  ΔVdroop ≈ (ΔILOAD · tresp) / Cout",
        "  + ΔILOAD · RESR  (tresp ≈ 1 / BWloop + slew delay at Cg!).",
        "• High-freq PSRR degrades at ωu,loop where Cout impedance",
        "  takes over from active EA loop gain.",
    ], tone="warn", fs=10.4)
    return d


def diag_29_mos_switch_charge_injection():
    d = SVGDoc(
        "mos-switch-charge-injection.svg",
        "MOS Sampling Switch: Charge Injection, Clock Feedthrough & Dummy Fix",
        "Công tắc Lấy mẫu MOS: Phun Điện tích Kênh dẫn, Xuyên nhiễu Xung nhịp & Công tắc Giả (Ch.13 §13.2)",
        "Ch.13", [13], width=1080, height=590
    )
    d.panel(18,  74, 505, 492, "(a) NMOS Turn-Off Charge Injection & Feedthrough")
    d.panel(543, 74, 519, 492, "(b) CMOS Transmission Gate & Dummy Switch (0.5·W)")

    # --- (a) NMOS Switch Charge Injection ---
    sx = 265
    sy = 235
    d.port(82, sy, "Vin", side="left", color=COL_SIG)
    ms = d.nmos_h(sx, sy, gate_pos="top", color=COL_SIG, label="M1 (W / L)")
    d.line(86, sy, ms["l"][0], sy, color=COL_SIG, sw=2.1)
    d.line(ms["r"][0], sy, 442, sy, color=COL_SIG, sw=2.1)
    d.port(446, sy, "Vout", side="right", color=COL_SIG)
    d.dot(392, sy, COL_SIG)

    # Gate clock CK falling edge
    d.line(sx, 145, sx, ms["g"][1], color=COL_PURPLE, sw=2.0)
    d.port(sx, 141, "CK (VDD -> 0)", side="top", color=COL_PURPLE)

    # Overlap capacitance WCov from Gate to Drain/Output (Red dashed)
    wcov = d.cap_h(328, 175, color=COL_WARN, label="W·Cov", label_pos="top")
    d.wire([(sx, 175), wcov["l"]], color=COL_WARN, dash="4,3")
    d.dot(sx, 175, COL_PURPLE)
    d.wire([wcov["r"], (365, 175), (365, sy)], color=COL_WARN, dash="4,3")
    d.dot(365, sy, COL_WARN)

    # Channel charge packet arrows splitting left & right!
    d.arrow(sx + 10, sy + 28, sx + 78, sy + 28, color=COL_WARN, sw=2.0)
    d.arrow(sx - 10, sy + 28, sx - 78, sy + 28, color=COL_MUTED, sw=1.8)
    d.text(sx, sy + 48, "Qch = −W·L·Cox·(VDD − Vin − VTH)", size=10.8,
           color=COL_WARN, anchor="middle", weight="bold")

    # Hold capacitor CH
    ch = d.cap_v(392, 318, color=COL_DARK, label="CH", label_side="right")
    d.line(392, sy, 392, ch["t"][1])
    d.gnd(392, ch["b"][1] + 10)
    d.line(392, ch["b"][1], 392, ch["b"][1] + 10)

    d.callout(36, 386, 468, 162, "Two Turn-Off Error Mechanisms (§13.2.3)", [
        "1. Channel Charge Injection (Signal-Dependent!):",
        "   ΔVinj = −[W·L·Cox / (2·CH)] · (VDD − Vin − VTH(Vin))",
        "   -> Causes DC offset, gain error, AND VTH(Vin) nonlinearity!",
        "2. Clock Feedthrough (Overlap Capacitance):",
        "   ΔVft = −VDD · W·Cov / (W·Cov + CH)   (Signal-independent).",
    ], tone="warn", fs=10.4)

    # --- (b) Top: CMOS Transmission Gate; Bottom: Dummy Switch ---
    # CMOS TG centered at x=730, y=188
    tgx, tgy = 720, 185
    d.port(585, tgy, "Vin", side="left", color=COL_SIG)
    # Parallel NMOS (top branch y=162) & PMOS (bottom branch y=208)
    mn_tg = d.nmos_h(tgx, 162, gate_pos="top", color=COL_SIG)
    mp_tg = d.pmos_h(tgx, 208, gate_pos="bottom", color=COL_BIAS)
    d.wire([(589, tgy), (645, tgy), (645, 162), mn_tg["l"]], color=COL_SIG)
    d.wire([(645, tgy), (645, 208), mp_tg["l"]], color=COL_SIG)
    d.dot(645, tgy, COL_SIG)
    d.wire([mn_tg["r"], (795, 162), (795, tgy), (842, tgy)], color=COL_SIG)
    d.wire([mp_tg["r"], (795, 208), (795, tgy)], color=COL_SIG)
    d.dot(795, tgy, COL_SIG)
    d.port(846, tgy, "Vout", side="right", color=COL_SIG)
    d.text(tgx, 124, "CK", size=10.5, color=COL_PURPLE, anchor="middle", weight="bold")
    d.text(tgx, 254, "CK_bar", size=10.5, color=COL_PURPLE, anchor="middle", weight="bold")

    # Mini Ron vs Vin plot on top right (x=905..1040)
    rx0, ry0 = d.axes(905, 125, 125, 108, xlabel="Vin", ylabel="Ron")
    d.path(f"M {rx0 + 8} 212 Q {rx0 + 75} 206 {rx0 + 102} 134", stroke=COL_SIG, sw=1.5, dash="3,3")
    d.path(f"M {rx0 + 22} 134 Q {rx0 + 50} 206 {rx0 + 118} 212", stroke=COL_BIAS, sw=1.5, dash="3,3")
    d.line(rx0 + 8, 218, rx0 + 118, 218, color=COL_WARN, sw=2.3)
    d.text(rx0 + 64, 212, "Ron,TG = RN||RP", size=9.6, color=COL_WARN, anchor="middle", weight="bold")

    # Divider line inside right panel
    d.line(558, 276, 1046, 276, color=COL_BORDER, sw=1.2)
    d.text(566, 298, "Half-Size Dummy Switch Charge Cancellation (Fig. 13.21):",
           size=11.4, color=COL_DARK, weight="bold")

    # Main switch M1 (x=685, y=385) + Dummy switch M2 (x=835, y=385, shorted D-S!) + CH (x=955)
    d.port(585, 385, "Vin", side="left", color=COL_SIG)
    m_main = d.nmos_h(685, 385, gate_pos="top", color=COL_SIG, label="M1 (W / L)")
    m_dum  = d.nmos_h(835, 385, gate_pos="top", color=COL_BIAS, label="M2 (0.5·W / L)")
    d.line(589, 385, m_main["l"][0], 385, color=COL_SIG)
    d.line(m_main["r"][0], 385, m_dum["l"][0], 385, color=COL_SIG)
    d.line(m_dum["r"][0], 385, 995, 385, color=COL_SIG)
    d.port(999, 385, "Vout", side="right", color=COL_SIG)

    # Short M2 Source & Drain together underneath M2!
    d.wire([(802, 385), (802, 412), (868, 412), (868, 385)], color=COL_BIAS, sw=1.9)
    d.dot(802, 385, COL_BIAS)
    d.dot(868, 385, COL_BIAS)

    d.port(685, 336, "CK", side="top", color=COL_PURPLE)
    d.line(685, 340, 685, m_main["g"][1], color=COL_PURPLE)
    d.port(835, 336, "CK_bar", side="top", color=COL_BIAS)
    d.line(835, 340, 835, m_dum["g"][1], color=COL_BIAS)

    ch2 = d.cap_v(945, 450, color=COL_DARK, label="CH", label_side="right")
    d.dot(945, 385, COL_SIG)
    d.line(945, 385, 945, ch2["t"][1])
    d.gnd(945, ch2["b"][1] + 8)
    d.line(945, ch2["b"][1], 945, ch2["b"][1] + 8)

    d.text(566, 520, "• If M1's channel charge splits 50%/50%, M2 (W2 = 0.5·W1) turning ON", size=10.5, color=COL_DARK)
    d.text(566, 540, "  absorbs ΔQ1 and cancels W·Cov feedthrough! (Imperfect if fast/asym -> use Bottom-Plate!)", size=10.3, color=COL_MUTED)
    return d


def diag_30_bottom_plate_sampling_sc():
    d = SVGDoc(
        "bottom-plate-sampling-sc.svg",
        "Bottom-Plate Sampling (φ1e Early Clock) & Parasitic-Insensitive SC Amp",
        "Lấy mẫu Tấm Đáy (Xung sớm φ1e) & Bộ Khuếch đại Tụ Chuyển mạch Không nhạy Tụ Ký sinh (Ch.13 §13.2.4–13.3)",
        "Ch.13", [13], width=1080, height=600
    )
    d.panel(20, 74, 650, 504, "Parasitic-Insensitive Non-Inverting SC Amplifier / Integrator")
    d.panel(688, 74, 372, 504, "Two-Phase Non-Overlapping Timing")

    # Left SC Schematic:
    # Vin -> S1(phi1) -> Node A -> C1 -> Node X -> S4(phi2) -> Op-Amp (-)
    # Node A also has S2(phi2) to GND + Cp1 parasitic
    # Node X also has S3(phi1e EARLY!) to GND + Cp2 parasitic
    y_sig = 295
    d.port(66, y_sig, "Vin", side="left", color=COL_SIG)
    s1 = d.sw_h(128, y_sig, label="S1 (φ1)", color=COL_SIG)
    d.line(70, y_sig, s1["l"][0], y_sig, color=COL_SIG)

    # Node A (x=195)
    d.line(s1["r"][0], y_sig, 252, y_sig, color=COL_SIG)
    d.dot(186, y_sig, COL_SIG)
    d.dot(228, y_sig, COL_MUTED)
    # S2 (phi2) to GND at x=186
    d.wire([(186, y_sig), (186, 375)], color=COL_PURPLE)
    d.circle(186, 385, 2.5, fill=COL_BG, stroke=COL_PURPLE, sw=1.6)
    d.line(186, 387, 195, 404, color=COL_PURPLE, sw=2.1)
    d.circle(186, 408, 2.5, fill=COL_BG, stroke=COL_PURPLE, sw=1.6)
    d.text(172, 398, "S2 (φ2)", size=10.5, color=COL_PURPLE, anchor="end", weight="bold")
    d.gnd(186, 422)
    d.line(186, 411, 186, 422, color=COL_PURPLE)

    # Parasitic Cp1 at Node A (x=228)
    cp1 = d.cap_v(228, 368, color=COL_SUBTLE, label="Cp1", label_side="right")
    d.line(228, y_sig, 228, cp1["t"][1], color=COL_SUBTLE, dash="3,3")
    d.gnd(228, cp1["b"][1] + 6)
    d.line(228, cp1["b"][1], 228, cp1["b"][1] + 6, color=COL_SUBTLE)

    # Sampling Capacitor C1 (x=270, y=295)
    c1 = d.cap_h(270, y_sig, color=COL_SIG, label="C1", label_pos="top")

    # Top/Right Plate Node X (x=325..385) — CRITICAL BOTTOM-PLATE NODE!
    d.line(c1["r"][0], y_sig, 385, y_sig, color=COL_SIG)
    d.dot(322, y_sig, COL_SUBTLE)
    d.dot(362, y_sig, COL_WARN)
    d.text(350, y_sig - 24, "Node X (Float 1st!)", size=10.4, color=COL_WARN, anchor="middle", weight="bold")

    # Parasitic Cp2 at Node X (x=322)
    cp2 = d.cap_v(322, 368, color=COL_SUBTLE, label="Cp2", label_side="left")
    d.line(322, y_sig, 322, cp2["t"][1], color=COL_SUBTLE, dash="3,3")
    d.gnd(322, cp2["b"][1] + 6)
    d.line(322, cp2["b"][1], 322, cp2["b"][1] + 6, color=COL_SUBTLE)

    # S3 (phi1_e EARLY!) grounding Node X at x=362!
    d.line(362, y_sig, 362, 375, color=COL_WARN, sw=2.1)
    d.circle(362, 385, 2.5, fill=COL_BG, stroke=COL_WARN, sw=1.7)
    d.line(362, 387, 372, 404, color=COL_WARN, sw=2.2)
    d.circle(362, 408, 2.5, fill=COL_BG, stroke=COL_WARN, sw=1.7)
    d.text(376, 398, "S3 (φ1e!)", size=10.8, color=COL_WARN, anchor="start", weight="bold")
    d.gnd(362, 422)
    d.line(362, 411, 362, 422, color=COL_WARN)

    # S4 (phi2) connecting Node X to Op-Amp (-) virtual ground!
    s4 = d.sw_h(405, y_sig, label="S4 (φ2)", color=COL_PURPLE)
    op = d.opamp(518, 308, w=68, h=58, facing="right", plus_top=False,
                 label="OTA", color=COL_SIG, fill="#eff6ff")
    d.line(s4["r"][0], y_sig, op["in_top"][0], y_sig, color=COL_SIG)
    d.dot(452, y_sig, COL_SIG)
    # (+) input grounded
    d.wire([op["in_bot"], (465, op["in_bot"][1]), (465, 358)], color=COL_DARK)
    d.gnd(465, 358)

    # Feedback Capacitor C2 (+ optional reset switch S5(phi1) for amp vs integrator) across OTA!
    c2 = d.cap_h(518, 205, color=COL_BIAS, label="C2 (Feedback)", label_pos="top")
    d.wire([(452, y_sig), (452, 205), c2["l"]], color=COL_BIAS, sw=2.0)
    d.wire([c2["r"], (584, 205), (584, 308)], color=COL_BIAS, sw=2.0)
    d.dot(584, 308, COL_SIG)
    # Reset switch S5(phi1) above C2 (y=146)
    s5 = d.sw_h(518, 146, label="S5 (φ1 Reset)", color=COL_MUTED)
    d.wire([(452, 205), (452, 146), s5["l"]], color=COL_MUTED, dash="4,3")
    d.dot(452, 205, COL_BIAS)
    d.wire([s5["r"], (584, 146), (584, 205)], color=COL_MUTED, dash="4,3")
    d.dot(584, 205, COL_BIAS)

    d.line(op["out"][0], 308, 622, 308, color=COL_SIG, sw=2.2)
    d.port(626, 308, "Vout", side="right", color=COL_SIG)

    d.callout(38, 462, 612, 98, "Why Cp1 & Cp2 NEVER Corrupt Gain Vout = +(C1 / C2)·Vin!", [
        "• Cp1 is driven by low-Z Vin in φ1 and shorted to GND in φ2 -> transfers ZERO charge to C2!",
        "• Cp2 is shorted to GND in φ1 and clamped to 0V Virtual Ground in φ2 -> ΔVCp2 = 0!",
        "• Feedback factor during φ2 amplification:  β = C2 / (C1 + C2 + Cp2 + Cin,op).",
    ], tone="bias", fs=10.4)

    # --- Right Panel: Clock Timing Waveforms ---
    wx = 735
    # Row 1: phi1_e (turns OFF at x=855 — EARLIER!)
    d.text(725, 162, "φ1e", size=11.5, color=COL_WARN, anchor="end", weight="bold")
    d.wire([
        (wx, 170), (wx + 22, 170), (wx + 28, 134),
        (wx + 115, 134), (wx + 122, 170), (wx + 300, 170)
    ], color=COL_WARN, sw=2.3)

    # Row 2: phi1 (turns OFF at x=890 — Δt AFTER phi1_e!)
    d.text(725, 232, "φ1", size=11.5, color=COL_SIG, anchor="end", weight="bold")
    d.wire([
        (wx, 240), (wx + 22, 240), (wx + 28, 204),
        (wx + 150, 204), (wx + 157, 240), (wx + 300, 240)
    ], color=COL_SIG, sw=2.3)

    # Vertical dashed markers highlighting Δt_early!
    d.line(wx + 118, 128, wx + 118, 256, color=COL_WARN, sw=1.3, dash="4,3")
    d.line(wx + 153, 198, wx + 153, 256, color=COL_SIG, sw=1.3, dash="4,3")
    d.text(wx + 136, 270, "Δt_early", size=10.4, color=COL_WARN, anchor="middle", weight="bold")

    # Row 3: phi2 (non-overlapping high from x=920 to x=1015)
    d.text(725, 316, "φ2", size=11.5, color=COL_PURPLE, anchor="end", weight="bold")
    d.wire([
        (wx, 324), (wx + 182, 324), (wx + 189, 288),
        (wx + 278, 288), (wx + 285, 324), (wx + 300, 324)
    ], color=COL_PURPLE, sw=2.3)

    d.callout(704, 356, 340, 204, "Golden Rule of Bottom-Plate Sampling", [
        "1. S3 (φ1e) sits at fixed VGND = 0V, so its",
        "   VGS = VDD is INDEPENDENT of Vin!",
        "2. S3 opens FIRST -> injects only a constant",
        "   pedestal ΔQ0 (canceled differentially!).",
        "3. Node X is now OPEN-CIRCUITED (floating)!",
        "4. When S1 (φ1) opens Δt later, its signal-",
        "   dependent Qch(Vin) has NO return path",
        "   into C1 -> ZERO nonlinear distortion!",
    ], tone="warn", fs=10.3)
    return d


def diag_31_bootstrapped_switch():
    d = SVGDoc(
        "bootstrapped-switch.svg",
        "Constant-VGS Bootstrapped Sampling Switch Topology",
        "Công tắc Lấy mẫu Tự nâng Áp Cổng (Bootstrapped Switch: Giữ VGS = VDD Hằng số — Ch.13 §13.2)",
        "Ch.13", [13], width=1060, height=590
    )
    d.panel(20, 74, 585, 492, "Flying-Capacitor Gate Bootstrap Switch (Precharge φp vs Sample φs)")

    # Main sampling NMOS MS at (x=365, y=385, gate_pos="top" -> gate at y=355!)
    ms_x, ms_y = 365, 395
    d.port(124, ms_y, "Vin (0..VDD)", side="left", color=COL_SIG)
    ms = d.nmos_h(ms_x, ms_y, gate_pos="top", color=COL_SIG, label="MS (Main Switch)")
    d.line(128, ms_y, ms["l"][0], ms_y, color=COL_SIG, sw=2.4)
    d.line(ms["r"][0], ms_y, 522, ms_y, color=COL_SIG, sw=2.4)
    d.port(526, ms_y, "Vout", side="right", color=COL_SIG)
    d.dot(185, ms_y, COL_SIG)
    d.dot(480, ms_y, COL_SIG)

    ch = d.cap_v(480, 466, color=COL_DARK, label="CH", label_side="right")
    d.line(480, ms_y, 480, ch["t"][1])
    d.gnd(480, ch["b"][1] + 8)
    d.line(480, ch["b"][1], 480, ch["b"][1] + 8)

    # Flying Bootstrap Capacitor Cb centered vertically at (x=255, y=245)
    cb_x = 255
    cb = d.cap_v(cb_x, 245, color=COL_BIAS, label="Cb (Bootstrap)", sub="VCb = VDD", label_side="left")
    y_top, y_bot = 185, 305
    d.line(cb_x, y_top, cb_x, cb["t"][1], color=COL_BIAS, sw=2.1)
    d.line(cb_x, cb["b"][1], cb_x, y_bot, color=COL_BIAS, sw=2.1)
    d.dot(cb_x, y_top, COL_BIAS)
    d.dot(cb_x, y_bot, COL_BIAS)

    # Phase 1 (Precharge φp: CK=0):
    # Sp1 charges top plate (cb_x, 185) from VDD; Sp2 grounds bottom plate (cb_x, 305); Soff grounds Gate(MS)!
    d.vdd(145, 134)
    sp1 = d.sw_h(195, y_top, label="Sp1 (φp)", color=COL_AMBER)
    d.wire([(145, 134), (145, y_top), sp1["l"]], color=COL_AMBER, dash="5,3")
    d.line(sp1["r"][0], y_top, cb_x, y_top, color=COL_AMBER, dash="5,3")

    sp2 = d.sw_h(195, y_bot, label="Sp2 (φp)", color=COL_AMBER)
    d.line(sp2["r"][0], y_bot, cb_x, y_bot, color=COL_AMBER, dash="5,3")
    d.wire([sp2["l"], (145, y_bot), (145, 336)], color=COL_AMBER, dash="5,3")
    d.gnd(145, 336)

    # Phase 2 (Sample φs: CK=1):
    # Ss1 connects Vin (185, ms_y) -> bottom plate (cb_x, y_bot)!
    # Ss2 connects top plate (cb_x, y_top) -> Gate of MS (ms_x, 365)!
    ss1 = d.sw_h(312, y_bot, label="Ss1 (φs)", color=COL_SIG, closed=True)
    d.line(cb_x, y_bot, ss1["l"][0], y_bot, color=COL_SIG, sw=2.0)
    d.wire([(185, ms_y), (185, 355), (345, 355), (345, y_bot), ss1["r"]], color=COL_SIG, sw=2.0)

    ss2 = d.sw_h(312, y_top, label="Ss2 (φs)", color=COL_SIG, closed=True)
    d.line(cb_x, y_top, ss2["l"][0], y_top, color=COL_SIG, sw=2.0)
    d.wire([ss2["r"], (ms_x, y_top), ms["g"]], color=COL_SIG, sw=2.2)
    d.dot(ms_x, 265, COL_AMBER)

    # Gate pull-down switch Soff(φp) at x=455 turning MS OFF cleanly during precharge!
    soff = d.sw_h(425, 265, label="Soff (φp)", color=COL_AMBER)
    d.line(ms_x, 265, soff["l"][0], 265, color=COL_AMBER, dash="5,3")
    d.wire([soff["r"], (465, 265), (465, 305)], color=COL_AMBER, dash="5,3")
    d.gnd(465, 305)

    d.text(ms_x + 12, 232, "VG(φs) = Vin + VDD !", size=11.5, color=COL_SIG, weight="bold")
    d.text(302, 535, "During φs:  VGS(MS) = (Vin + VDD) − Vin = VDD = CONSTANT!",
           size=11.2, color=COL_BIAS, anchor="middle", weight="bold")

    # Right Analytical Callouts
    d.callout(624, 76, 416, 158, "1. Why CMOS TG Fails at Low VDD (90nm/65nm/45nm)", [
        "• When VDD drops near or below VTH,N + |VTH,P| (~0.9 V),",
        "  NEITHER NMOS nor PMOS conducts strongly near Vin ≈ VDD/2!",
        "• Ron(Vin) spikes into a huge nonlinear 'dead-zone' bell,",
        "  causing severe HD3 harmonic distortion in high-ENOB ADCs.",
    ], tone="warn", fs=10.5)

    d.callout(624, 248, 416, 158, "2. Constant Overdrive & High Linearity", [
        "• Flying cap Cb acts as a floating VDD battery tied to Vin:",
        "  Ron ≈ 1 / [μn·Cox·(W/L)·(VDD − VTH(Vin))]",
        "• Only tiny residual body-effect ΔVTH(VSB) remains (eliminated",
        "  completely if MS sits in an isolated Deep N-Well tied to Vin!).",
        "• Note: Parasitic Cp at top plate attenuates VG to Cb/(Cb+Cp)·VDD.",
    ], tone="sig", fs=10.5)

    d.callout(624, 420, 416, 146, "3. Oxide Reliability (SOA) Invariant!", [
        "• Even though absolute VG reaches 2·VDD when Vin = VDD,",
        "  EVERY terminal difference across MS stays ≤ VDD:",
        "  VGS = VDD ,   VGD ≈ VDD (since Vout ≈ Vin),   VGB ≤ 2·VDD",
        "  (Use Deep N-Well body tie + cascade shield on Soff NMOS!).",
    ], tone="bias", fs=10.5)
    return d


def diag_32_ring_and_lc_oscillators():
    d = SVGDoc(
        "ring-and-lc-oscillators.svg",
        "3-Stage CMOS Ring Oscillator vs Cross-Coupled LC-Tank VCO",
        "Bộ Dao động Vòng 3 Tầng (Ring Oscillator) và Bộ Dao động VCO Cộng hưởng LC Chéo (Ch.15 §15.2–15.4)",
        "Ch.15", [15], width=1080, height=590
    )
    d.panel(18,  74, 505, 492, "(a) 3-Stage CMOS Ring Oscillator")
    d.panel(543, 74, 519, 492, "(b) Cross-Coupled NMOS LC-Tank VCO")

    # --- (a) 3-Stage Ring Oscillator ---
    # Draw 3 inverter triangles + RC load poles at x=145, 275, 405 along y=225
    inv_xs = [140, 275, 410]
    y_ring = 225
    for idx, ix in enumerate(inv_xs):
        # Inverter triangle + output bubble
        d.poly([(ix - 22, y_ring - 22), (ix - 22, y_ring + 22), (ix + 18, y_ring)],
               fill="#eff6ff", stroke=COL_SIG, sw=2.0)
        d.circle(ix + 22, y_ring, 3.5, fill=COL_BG, stroke=COL_SIG, sw=1.8)
        d.text(ix - 7, y_ring + 4, f"A{idx + 1}", size=10.8, color=COL_SIG, anchor="middle", weight="bold")
        d.text(ix, y_ring - 30, "−60° lag", size=10.0, color=COL_AMBER, anchor="middle", weight="bold")

        # Interstage wire + parasitic C0 to GND
        nx = ix + 56
        d.line(ix + 26, y_ring, nx + 26 if idx < 2 else 472, y_ring, color=COL_SIG, sw=2.1)
        d.dot(nx, y_ring, COL_DARK)
        c0 = d.cap_v(nx, y_ring + 55, color=COL_MUTED, label="C0", label_side="right")
        d.line(nx, y_ring, nx, c0["t"][1], color=COL_MUTED)
        d.gnd(nx, c0["b"][1] + 6)
        d.line(nx, c0["b"][1], nx, c0["b"][1] + 6, color=COL_MUTED)

    # Feedback loop from stage 3 output (472, y_ring) up/around to stage 1 input (85, y_ring)!
    d.wire([(472, y_ring), (472, 142), (82, 142), (82, y_ring), (118, y_ring)], color=COL_WARN, sw=2.2)
    d.arrow(310, 142, 240, 142, color=COL_WARN, sw=2.0)
    d.text(275, 130, "Global Feedback Loop (DC Inversion + 3×60° = 360°!)",
           size=10.5, color=COL_WARN, anchor="middle", weight="bold")
    d.port(476, y_ring, "Vout", side="right", color=COL_SIG)

    d.callout(36, 358, 468, 190, "Ring Oscillator Laws (Razavi §15.2)", [
        "• Why 1-stage & 2-stage inverter rings FAIL to oscillate:",
        "  Max phase shift < 180° -> 2-stage simply LATCHES UP!",
        "• 3-Stage Small-Signal Barkhausen Startup [H(s) = −A0³/(1+s/ω0)³]:",
        "  ωosc = √3 · ω0   and   Per-Stage Gain  A0 ≥ 2 !",
        "• Large-Signal Rail-to-Rail Oscillation Frequency:",
        "  fosc = 1 / (2 · N · td)    (Tuned via current-starving ISS).",
        "• Compact area & wide tuning, but higher phase noise than LC!",
    ], tone="sig", fs=10.4)

    # --- (b) Cross-Coupled LC VCO ---
    xl, xr = 705, 895
    cx = 800
    d.vdd(xl, 122)
    d.vdd(xr, 122)

    # Spiral Inductors L1, L2 (y=166) + parallel tank loss Rp
    l1 = d.ind_v(xl, 166, color=COL_BIAS, label="L1", sub="Rp", label_side="left")
    l2 = d.ind_v(xr, 166, color=COL_BIAS, label="L2", sub="Rp", label_side="right")
    d.line(xl, 122, xl, l1["t"][1], color=COL_BIAS)
    d.line(xr, 122, xr, l2["t"][1], color=COL_BIAS)

    # Output Tank Nodes Vout- (xl, 224) & Vout+ (xr, 224) + MOS Varactors tuned by Vcont!
    y_tank = 224
    d.line(xl, l1["b"][1], xl, 326, color=COL_SIG)
    d.line(xr, l2["b"][1], xr, 326, color=COL_SIG)
    d.dot(xl, y_tank, COL_SIG)
    d.dot(xr, y_tank, COL_SIG)
    d.line(618, y_tank, xl, y_tank, color=COL_SIG)
    d.port(614, y_tank, "Vout−", side="left", color=COL_SIG)
    d.line(xr, y_tank, 982, y_tank, color=COL_SIG)
    d.port(986, y_tank, "Vout+", side="right", color=COL_SIG)

    # Varactor branch across tank at y=224 with center control port Vcont!
    cv1 = d.cap_h(758, y_tank, color=COL_AMBER, label="Cvar", label_pos="top")
    cv2 = d.cap_h(842, y_tank, color=COL_AMBER, label="Cvar", label_pos="top")
    d.line(xl, y_tank, cv1["l"][0], y_tank, color=COL_AMBER)
    d.line(cv1["r"][0], y_tank, cv2["l"][0], y_tank, color=COL_AMBER)
    d.line(cv2["r"][0], y_tank, xr, y_tank, color=COL_AMBER)
    d.dot(cx, y_tank, COL_AMBER)
    d.line(cx, 166, cx, y_tank, color=COL_AMBER)
    d.port(cx, 162, "Vcont", side="top", color=COL_AMBER)

    # Cross-Coupled NMOS Pair M1 (xl, facing left -> gate right!) & M2 (xr, facing right -> gate left!) at y=350
    m1 = d.nmos(xl, 350, facing="left",  color=COL_SIG, label="M1", sub="gm", label_side="left")
    m2 = d.nmos(xr, 350, facing="right", color=COL_SIG, label="M2", sub="gm", label_side="right")

    # Cross-coupled gate wires (clean non-ambiguous diagonal cross!)
    d.dot(xl, 286, COL_WARN)
    d.dot(xr, 286, COL_WARN)
    d.wire([(xl, 286), (758, 286), m2["g"]], color=COL_WARN, sw=2.0)
    d.wire([(xr, 286), (842, 286), m1["g"]], color=COL_WARN, sw=2.0)
    d.text(cx, 276, "Zin = −2 / gm", size=10.6, color=COL_WARN, anchor="middle", weight="bold")

    # Tail current source ISS at bottom
    d.wire([m1["s"], (xl, 396), (xr, 396), m2["s"]], color=COL_DARK)
    d.dot(cx, 396, COL_BIAS)
    iss = d.isrc_v(cx, 428, direction="down", color=COL_BIAS, label="ISS", label_side="right")
    d.line(cx, 396, cx, iss["t"][1], color=COL_BIAS)
    d.gnd(cx, iss["b"][1] + 4)
    d.line(cx, iss["b"][1], cx, iss["b"][1] + 4)

    d.callout(560, 466, 486, 86, "LC-Tank Startup & Resonance (§15.3–15.4)", [
        "• Resonance: ωosc = 1 / √[L · (Cvar(Vcont) + Cpar)]  |  Rp ≈ Q²·Rs",
        "• Negative resistance −2/gm cancels 2·Rp:  Startup  gm · Rp ≥ 1  (choose 2–3x)!",
        "• Superior spectral purity (high Q suppresses phase noise skirt).",
    ], tone="bias", fs=10.3)
    return d


def diag_33_charge_pump_type2_pll():
    d = SVGDoc(
        "charge-pump-type2-pll.svg",
        "Charge-Pump Type-II Phase-Locked Loop (PFD + CP + Rp/C1/C2 LPF + VCO + ÷N)",
        "Vòng Khóa Pha Bơm Điện tích Loại II: PFD + CP + Bộ lọc Rp/C1/C2 + VCO + Bộ chia N (Ch.16 §16.2)",
        "Ch.16", [16], width=1080, height=600
    )
    d.panel(20, 74, 1040, 336, "Complete Charge-Pump Type-II Frequency Synthesizer Loop")

    # Input fREF -> Tri-State PFD Box (x=115..255, y=135..245)
    d.port(66, 162, "fREF", side="left", color=COL_SIG)
    d.line(70, 162, 115, 162, color=COL_SIG, sw=2.2)

    d.rect(115, 135, 145, 110, fill="#eff6ff", stroke=COL_SIG, sw=1.9, rx=8)
    d.text(187.5, 164, "Tri-State PFD", size=12.2, color=COL_SIG, anchor="middle", weight="bold")
    d.text(187.5, 184, "DFF_A + DFF_B", size=10.6, color=COL_DARK, anchor="middle")
    d.text(187.5, 202, "+ Reset Delay td", size=10.4, color=COL_BIAS, anchor="middle", weight="bold")
    d.text(187.5, 220, "(Kills Dead Zone)", size=10.0, color=COL_MUTED, anchor="middle")

    # UP & DN control lines from PFD to Charge Pump (x=375)
    cp_x = 375
    d.vdd(cp_x, 128)
    i_up = d.isrc_v(cp_x, 156, direction="down", color=COL_BIAS, label="IUP (Ip)", label_side="right")
    d.line(cp_x, 128, cp_x, i_up["t"][1], color=COL_BIAS)

    # UP switch (y=188) & DN switch (y=242) meeting at Vctrl node (y=215)!
    d.line(cp_x, i_up["b"][1], cp_x, 180, color=COL_BIAS)
    d.line(cp_x, 180, cp_x + 9, 196, color=COL_PURPLE, sw=2.1)
    d.line(cp_x, 198, cp_x, 232, color=COL_SIG, sw=2.2)
    d.line(cp_x, 232, cp_x + 9, 248, color=COL_PURPLE, sw=2.1)
    d.line(cp_x, 250, cp_x, 258, color=COL_BIAS)
    i_dn = d.isrc_v(cp_x, 282, direction="down", color=COL_BIAS, label="IDN (Ip)", label_side="right")
    d.line(cp_x, 306, cp_x, 326, color=COL_BIAS)
    d.gnd(cp_x, 326)

    # UP & DN arrows from PFD
    d.arrow(260, 165, cp_x - 10, 185, color=COL_PURPLE, sw=1.8, dash="4,3")
    d.text(308, 162, "UP", size=10.8, color=COL_PURPLE, anchor="middle", weight="bold")
    d.arrow(260, 218, cp_x - 10, 238, color=COL_PURPLE, sw=1.8, dash="4,3")
    d.text(308, 242, "DN", size=10.8, color=COL_PURPLE, anchor="middle", weight="bold")

    # Vctrl Horizontal Wire (y=215) across Loop Filter (Rp+C1 at x=535, C2 at x=645) -> VCO (x=735)!
    y_vc = 215
    d.dot(cp_x, y_vc, COL_SIG)
    d.line(cp_x, y_vc, 735, y_vc, color=COL_SIG, sw=2.4)
    d.text(462, y_vc - 10, "Vctrl", size=11.5, color=COL_SIG, anchor="middle", weight="bold")
    d.dot(535, y_vc, COL_AMBER)
    d.dot(645, y_vc, COL_AMBER)

    # 2nd-Order Type-II Loop Filter: Branch 1 = Rp + C1 (x=535); Branch 2 = C2 (x=645)
    rp = d.res_v(535, 256, color=COL_AMBER, label="Rp", sub="Zero ωz!", label_side="left")
    c1 = d.cap_v(535, 318, color=COL_AMBER, label="C1 (Main)", label_side="left")
    d.line(535, y_vc, 535, rp["t"][1], color=COL_AMBER, sw=2.1)
    d.line(535, rp["b"][1], 535, c1["t"][1], color=COL_AMBER, sw=2.1)
    d.line(535, c1["b"][1], 535, 352, color=COL_AMBER)
    d.gnd(535, 352)

    c2 = d.cap_v(645, 286, color=COL_MUTED, label="C2 (Ripple)", sub="≈ C1/10", label_side="right")
    d.line(645, y_vc, 645, c2["t"][1], color=COL_MUTED, sw=1.9)
    d.line(645, c2["b"][1], 645, 352, color=COL_MUTED)
    d.gnd(645, 352)

    # VCO Block (x=735..875, y=170..260)
    d.rect(735, 170, 140, 90, fill="#ecfdf5", stroke=COL_BIAS, sw=2.0, rx=8)
    d.text(805, 204, "VCO", size=13, color=COL_BIAS, anchor="middle", weight="bold")
    d.text(805, 224, "Φout(s) = KVCO / s", size=10.8, color=COL_DARK, anchor="middle")
    d.text(805, 242, "(2nd Origin Pole!)", size=10.2, color=COL_WARN, anchor="middle", weight="bold")

    # Output fOUT = N * fREF & Feedback Divider ÷N back to PFD!
    d.line(875, y_vc, 944, y_vc, color=COL_SIG, sw=2.4)
    d.port(948, y_vc, "fOUT = N·fREF", side="right", color=COL_SIG, fs=11)
    d.dot(908, y_vc, COL_SIG)

    # Feedback path along y=382 with ÷N block at x=450..565
    d.wire([(908, y_vc), (908, 382), (570, 382)], color=COL_DARK, sw=2.0)
    d.rect(445, 360, 125, 44, fill="#f8fafc", stroke=COL_DARK, sw=1.8, rx=7)
    d.text(507.5, 386, "Divider  ÷ N", size=11.8, color=COL_DARK, anchor="middle", weight="bold")
    d.wire([(445, 382), (85, 382), (85, 218), (115, 218)], color=COL_DARK, sw=2.0)
    d.text(245, 372, "fFB = fOUT / N", size=10.8, color=COL_DARK, anchor="middle", weight="bold")

    # Bottom 3 Analytical Cards
    d.callout(20, 426, 336, 154, "1. Why Rp Zero is Mandatory!", [
        "• CP + C1 is an integrator (1/s) AND VCO phase",
        "  is a 2nd integrator (KVCO/s) -> H(s) ∝ 1/s²!",
        "• Two poles at s=0 start at −180° phase ->",
        "  OSCILLATES if Rp = 0!",
        "• Series Rp adds LHP zero:  ωz = 1 / (Rp·C1).",
    ], tone="warn", fs=10.3)

    d.callout(372, 426, 336, 154, "2. Loop Dynamics & Ripple Cap C2", [
        "• Natural Freq: ωn = √[ Ip·KVCO / (2π·N·C1) ]",
        "• Damping:      ζ  = (Rp / 2) · √[ Ip·C1·KVCO / (2π·N) ]",
        "• Shunt C2 suppresses ΔV = Ip·Rp step jumps on",
        "  Vctrl (choose C2 ≤ C1/10 so ωp3 >> ωu!).",
    ], tone="amber", fs=10.3)

    d.callout(724, 426, 336, 154, "3. Noise Transfer Duality (§16.4)", [
        "• Ref / PFD / Charge-Pump / Divider Noise:",
        "  LOW-PASS filtered (× N² inside loop BW)!",
        "• VCO Phase Noise:",
        "  HIGH-PASS filtered (suppressed inside BW)!",
        "• Trade-off sets optimal PLL loop bandwidth ωu.",
    ], tone="sig", fs=10.3)
    return d


def diag_34_pelgrom_mismatch_duality():
    d = SVGDoc(
        "pelgrom-mismatch-duality.svg",
        "Pelgrom Mismatch Law & The Fundamental CMOS Sizing Duality",
        "Định luật Bất đối xứng Pelgrom & Quy tắc Đối ngẫu Định cỡ: Cặp Vi sai vs Gương dòng (Ch.14 §14.2)",
        "Ch.14", [14], width=1080, height=590
    )
    d.panel(18,  74, 512, 492, "(a) Differential Pair: Minimize VOLTAGE Offset VOS")
    d.panel(550, 74, 512, 492, "(b) Current Mirror: Minimize CURRENT Error ΔID/ID")

    # --- (a) Diff-Pair Voltage Offset ---
    xl, xr = 185, 365
    cx = 275
    d.vdd(xl, 126)
    d.vdd(xr, 126)
    rd1 = d.res_v(xl, 168, color=COL_DARK, label="RD1", label_side="left")
    rd2 = d.res_v(xr, 168, color=COL_DARK, label="RD2+ΔRD", label_side="right")
    d.line(xl, 126, xl, rd1["t"][1])
    d.line(xr, 126, xr, rd2["t"][1])

    m1 = d.nmos(xl, 260, facing="right", color=COL_SIG, label="M1", sub="VTH1", label_side="right")
    m2 = d.nmos(xr, 260, facing="left",  color=COL_SIG, label="M2", sub="VTH1+ΔVTH", label_side="left")
    d.line(xl, rd1["b"][1], xl, m1["d"][1], color=COL_SIG)
    d.line(xr, rd2["b"][1], xr, m2["d"][1], color=COL_SIG)

    # Series input-referred offset VOS on Vin+
    vos = d.vsrc_h(112, 260, color=COL_WARN, label="VOS,in", label_pos="top")
    d.port(64, 260, "Vin+", side="left", color=COL_SIG)
    d.line(68, 260, vos["l"][0], 260, color=COL_SIG)
    d.line(vos["r"][0], 260, m1["g"][0], 260, color=COL_WARN)
    d.line(m2["g"][0], 260, 442, 260, color=COL_SIG)
    d.port(446, 260, "Vin−", side="right", color=COL_SIG)

    d.wire([m1["s"], (xl, 316), (xr, 316), m2["s"]], color=COL_DARK)
    d.dot(cx, 316, COL_BIAS)
    iss = d.isrc_v(cx, 352, direction="down", color=COL_BIAS, label="ISS", label_side="right")
    d.line(cx, 316, cx, iss["t"][1], color=COL_BIAS)
    d.gnd(cx, iss["b"][1] + 4)
    d.line(cx, iss["b"][1], cx, iss["b"][1] + 4)

    d.callout(34, 400, 480, 150, "DIFF-PAIR SIZING RULE: Small Vov / High gm/ID!", [
        "• Pelgrom Law:  σ(ΔVTH) = AVTH / √(W · L)",
        "• Input Offset: VOS = ΔVTH + (Vov / 2) · [Δ(W/L)/(W/L) + ΔRD/RD]",
        "• Active-Load Referred Offset: VOS,tot² = ΔVTH,in² + (gm,ld/gm,in)²·ΔVTH,ld²",
        "-> SIZING PRESCRIPTION: Large W·L, WIDE W, SMALL Vov (HIGH gm/ID)!",
    ], tone="sig", fs=10.3)

    # --- (b) Current Mirror Current Error ---
    xm1, xm2 = 715, 895
    d.vdd(xm1, 126)
    iref = d.isrc_v(xm1, 174, direction="down", color=COL_BIAS, label="IREF", label_side="left")
    d.line(xm1, 126, xm1, iref["t"][1], color=COL_BIAS)

    mm1 = d.nmos(xm1, 290, facing="left",  color=COL_BIAS, label="M1", sub="VTH1", label_side="left")
    mm2 = d.nmos(xm2, 290, facing="right", color=COL_AMBER, label="M2", sub="VTH1+ΔVTH", label_side="right")
    d.line(xm1, iref["b"][1], xm1, mm1["d"][1], color=COL_BIAS)
    d.line(mm1["g"][0], 290, mm2["g"][0], 290, color=COL_BIAS)
    d.wire([(xm1, 244), (xm1 + 44, 244), (xm1 + 44, 290)], color=COL_BIAS)
    d.dot(xm1, 244, COL_BIAS)
    d.dot(xm1 + 44, 290, COL_BIAS)

    d.line(xm2, 188, xm2, mm2["d"][1], color=COL_AMBER)
    d.port(xm2, 184, "Iout = IREF + ΔID!", side="top", color=COL_WARN)
    d.arrow(xm2 + 16, 206, xm2 + 16, 248, color=COL_WARN, sw=1.9)

    d.line(xm1, mm1["s"][1], xm1, 358)
    d.gnd(xm1, 358)
    d.line(xm2, mm2["s"][1], xm2, 358)
    d.gnd(xm2, 358)

    d.callout(566, 400, 480, 150, "CURRENT-MIRROR SIZING RULE: Large Vov / Low gm/ID!", [
        "• Relative Current Mismatch (Razavi Eq. 14.43):",
        "  ΔID / ID = Δ(W/L)/(W/L) − (2 / Vov)·ΔVTH = Δβ/β − (gm/ID)·ΔVTH",
        "• Small Vov (subthreshold) BLOWS UP ΔVTH error by ~25 V⁻¹!",
        "-> SIZING PRESCRIPTION: Large W·L, LONG L, LARGE Vov (LOW gm/ID)!",
    ], tone="amber", fs=10.3)
    return d


def diag_35_autozero_cds_offset():
    d = SVGDoc(
        "autozero-cds-offset.svg",
        "Auto-Zeroing & Correlated Double Sampling (CDS): Offset & 1/f Cancellation",
        "Tự Chỉnh Không (Auto-Zeroing) & Lấy mẫu Kép Tương quan (CDS): Khử Offset & Nhiễu 1/f (Ch.14 §14.2.2)",
        "Ch.14", [14], width=1080, height=580
    )
    d.panel(18,  74, 510, 484, "(a) Phase φ1 (Auto-Zero): Sample VOS + Vn,1/f(t1)")
    d.panel(552, 74, 510, 484, "(b) Phase φ2 (Amplify): Subtract Stored Offset & 1/f")

    # --- (a) Phase phi1: Auto-Zeroing ---
    # Input shorted to GND/VCM via S_az1 -> CAZ -> Node X -> Amplifier (-); unity feedback switch S_az2 closed!
    y1 = 235
    d.gnd(88, y1 + 36)
    d.wire([(88, y1 + 36), (88, y1), (115, y1)], color=COL_BIAS)
    s_az1 = d.sw_h(135, y1, label="S1 (φ1 ON)", color=COL_BIAS, closed=True)
    caz1 = d.cap_h(225, y1, color=COL_WARN, label="CAZ", sub="−  VCAZ ≈ VOS  +", label_pos="top")
    d.line(s_az1["r"][0], y1, caz1["l"][0], y1, color=COL_BIAS, sw=2.1)

    op1 = d.opamp(385, 248, w=68, h=58, facing="right", plus_top=False,
                  label="A0", color=COL_SIG, fill="#eff6ff")
    d.line(caz1["r"][0], y1, op1["in_top"][0], y1, color=COL_WARN, sw=2.1)
    d.dot(295, y1, COL_WARN)

    # VOS + Vn,1/f at (+) input of op1!
    vos1 = d.vsrc_v(322, 315, color=COL_WARN, label="VOS + Vn(t1)", label_side="left")
    d.wire([op1["in_bot"], (322, op1["in_bot"][1]), vos1["t"]], color=COL_WARN)
    d.gnd(322, vos1["b"][1] + 8)
    d.line(322, vos1["b"][1], 322, vos1["b"][1] + 8, color=COL_WARN)

    # Unity feedback switch S3(phi1 ON) across op1!
    s_fb1 = d.sw_h(385, 155, label="S3 (φ1 ON)", color=COL_BIAS, closed=True)
    d.wire([(295, y1), (295, 155), s_fb1["l"]], color=COL_BIAS, sw=2.0)
    d.wire([s_fb1["r"], (455, 155), (455, 248), op1["out"]], color=COL_BIAS, sw=2.0)
    d.dot(455, 248, COL_SIG)
    d.line(455, 248, 488, 248, color=COL_SIG)
    d.port(492, 248, "VAZ", side="right", color=COL_SIG)

    d.callout(36, 396, 474, 144, "Auto-Zero Phase φ1 Equilibrium (§14.2.2)", [
        "• Unity-gain loop clamps inverting input to:",
        "  VX(t1) = [A0 / (1 + A0)] · (VOS + Vn,1/f(t1)) ≈ VOS + Vn,1/f(t1)",
        "• Storage cap CAZ records exact snapshot VCAZ = VX(t1)!",
        "• Note: Open S3 slightly early (bottom-plate rule) to bound ΔQinj!",
    ], tone="bias", fs=10.4)

    # --- (b) Phase phi2: Offset-Canceled Amplification ---
    y2 = 235
    d.port(602, y2, "Vin", side="left", color=COL_SIG)
    s_in2 = d.sw_h(662, y2, label="S2 (φ2 ON)", color=COL_SIG, closed=True)
    d.line(606, y2, s_in2["l"][0], y2, color=COL_SIG, sw=2.2)

    caz2 = d.cap_h(755, y2, color=COL_BIAS, label="CAZ", sub="−  VOS+Vn(t1)  +", label_pos="top")
    d.line(s_in2["r"][0], y2, caz2["l"][0], y2, color=COL_SIG, sw=2.2)

    op2 = d.opamp(915, 248, w=68, h=58, facing="right", plus_top=False,
                  label="A0", color=COL_SIG, fill="#eff6ff")
    d.line(caz2["r"][0], y2, op2["in_top"][0], y2, color=COL_SIG, sw=2.2)
    d.dot(825, y2, COL_MUTED)

    # Open S3 shown cleanly at top (y=155)
    s_fb2 = d.sw_h(915, 155, label="S3 (φ2 OPEN)", color=COL_MUTED, closed=False)
    d.wire([(825, y2), (825, 155), s_fb2["l"]], color=COL_MUTED, dash="4,3")
    d.wire([s_fb2["r"], (985, 155), (985, 248)], color=COL_MUTED, dash="4,3")

    vos2 = d.vsrc_v(852, 315, color=COL_WARN, label="VOS + Vn(t2)", label_side="left")
    d.wire([op2["in_bot"], (852, op2["in_bot"][1]), vos2["t"]], color=COL_WARN)
    d.gnd(852, vos2["b"][1] + 8)
    d.line(852, vos2["b"][1], 852, vos2["b"][1] + 8, color=COL_WARN)

    d.line(op2["out"][0], 248, 1014, 248, color=COL_SIG, sw=2.3)
    d.port(1018, 248, "Vout", side="right", color=COL_SIG)

    d.callout(570, 396, 474, 144, "CDS Subtraction of DC Offset & 1/f Noise!", [
        "• Effective amplifier input error during φ2:",
        "  Verr = [VOS/(1 + A0)] + [Vn(t2) − Vn(t1)] !",
        "• DC Offset reduced by (1 + A0) (residual = switch Qinj / CAZ ->",
        "  suppress further via auxiliary low-gain nulling port Aaux!).",
        "• Slow 1/f flicker noise (f << fs) is correlated -> CANCELED!",
    ], tone="sig", fs=10.4)
    return d


def diag_36_latchup_and_guard_rings():
    d = SVGDoc(
        "latchup-and-guard-rings.svg",
        "CMOS Parasitic NPN–PNP Thyristor (SCR) Latch-Up & Guard Rings",
        "Mặt cắt Bán dẫn CMOS: Cơ chế Khóa cứng Ký sinh SCR (Latch-Up) & Vòng Bảo vệ Guard Ring (Ch.18 §18.8)",
        "Ch.18 & 19", [18, 19], width=1080, height=600
    )
    d.panel(20, 74, 645, 504, "N-Well / P-Substrate Cross-Section, SCR Loop & Guard Rings")

    # P-Substrate Silicon Body (x=45..640, y=220..515)
    y_surf = 230
    d.rect(45, y_surf, 595, 275, fill="#f8fafc", stroke=COL_DARK, sw=1.8, rx=4)
    d.text(540, 488, "P-Substrate (P−)", size=12, color=COL_MUTED, anchor="middle", weight="bold")

    # N-Well Tub on left (x=68..338, y=230..395)
    d.rect(68, y_surf, 270, 165, fill="#eff6ff", stroke=COL_SIG, sw=1.8, rx=6)
    d.text(203, 382, "N-Well", size=11.8, color=COL_SIG, anchor="middle", weight="bold")

    # Active Diffusion Wells along surface y=230 (height 34):
    # Inside N-well: [N+ tap (80)], [P+ src (145)], [P+ drn (215)], [N+ Guard Ring (282)]
    # Inside P-sub:  [P+ Guard Ring (356)], [N+ drn (425)], [N+ src (495)], [P+ sub tap (565)]
    diffs = [
        (80,  42, "#bfdbfe", COL_SIG,  "N+"),
        (142, 46, "#fecaca", COL_WARN, "P+"),
        (212, 46, "#fecaca", COL_WARN, "P+"),
        (278, 46, "#a7f3d0", COL_BIAS, "N+ GR"),
        (354, 46, "#a7f3d0", COL_BIAS, "P+ GR"),
        (422, 46, "#bfdbfe", COL_SIG,  "N+"),
        (492, 46, "#bfdbfe", COL_SIG,  "N+"),
        (560, 46, "#fecaca", COL_DARK, "P+"),
    ]
    for dx, dw, dfill, dcol, dlbl in diffs:
        d.rect(dx, y_surf, dw, 32, fill=dfill, stroke=dcol, sw=1.5, rx=3)
        d.text(dx + dw / 2, y_surf + 20, dlbl, size=9.8, color=COL_DARK, anchor="middle", weight="bold")

    # PMOS Polysilicon Gate (between P+ 142..188 and 212..258 -> x=186..214)
    d.rect(185, y_surf - 14, 30, 12, fill="#fde68a", stroke=COL_AMBER, sw=1.5, rx=2)
    d.text(200, y_surf - 20, "PMOS", size=10.8, color=COL_DARK, anchor="middle", weight="bold")

    # NMOS Polysilicon Gate (between N+ 422..468 and 492..538 -> x=466..494)
    d.rect(465, y_surf - 14, 30, 12, fill="#fde68a", stroke=COL_AMBER, sw=1.5, rx=2)
    d.text(480, y_surf - 20, "NMOS", size=10.8, color=COL_DARK, anchor="middle", weight="bold")

    # VDD connections to N+ well tap (101), PMOS P+ source (165), and N+ Guard Ring (301)
    y_vdd_bus = 138
    d.line(101, y_vdd_bus, 301, y_vdd_bus, color=COL_BIAS, sw=2.2)
    d.vdd(200, y_vdd_bus)
    d.dot(200, y_vdd_bus, COL_BIAS)
    for vx in (101, 165, 301):
        d.line(vx, y_vdd_bus, vx, y_surf, color=COL_BIAS, sw=1.9)
        if vx != 200:
            d.dot(vx, y_vdd_bus, COL_BIAS)

    # GND connections to P+ Guard Ring (377), NMOS N+ source (515), and P+ sub tap (583)
    y_gnd_bus = 166
    d.line(377, y_gnd_bus, 583, y_gnd_bus, color=COL_BIAS, sw=2.2)
    d.gnd(583, y_gnd_bus)
    for gx in (377, 515):
        d.line(gx, y_gnd_bus, gx, y_surf, color=COL_BIAS, sw=1.9)
        d.dot(gx, y_gnd_bus, COL_BIAS)
    d.line(583, y_gnd_bus, 583, y_surf, color=COL_BIAS, sw=1.9)

    # Parasitic SCR Schematic Overlay inside Silicon:
    # Rwell from N+ tap (101, 310) to PNP Q1 Base (175, 310); Q1 Emitter = P+ (165, 262);
    # Q1 Collector -> P-sub node (395, 435) = Base of NPN Q2!
    # Q2 Emitter = NMOS N+ (515, 262); Q2 Collector -> N-well node (175, 310); Rsub to P+ tap (583, 435)!
    d.wire([(101, 262), (101, 325), (122, 325)], color=COL_WARN, sw=1.8)
    rw = d.res_h(146, 325, color=COL_WARN, label="Rwell", label_pos="bottom")
    d.text(235, 322, "Q1 (PNP, β1)", size=10.8, color=COL_WARN, weight="bold")
    d.text(405, 355, "Q2 (NPN, β2)", size=10.8, color=COL_WARN, weight="bold")

    # Regenerative cross-coupled loop arrows (Red!)
    d.path("M 215 262 Q 255 435 425 435", stroke=COL_WARN, sw=2.2, dash="6,3", marker_end="arr-warn")
    d.path("M 495 262 Q 395 330 190 325", stroke=COL_WARN, sw=2.2, dash="6,3", marker_end="arr-warn")

    rs_sub = d.res_h(525, 435, color=COL_WARN, label="Rsub", label_pos="top")
    d.line(425, 435, rs_sub["l"][0], 435, color=COL_WARN, sw=1.8)
    d.wire([rs_sub["r"], (583, 435), (583, 262)], color=COL_WARN, sw=1.8)

    d.text(342, 535, "Positive-Feedback SCR Loop:  I_C1 feeds Base(Q2) via Rsub ; I_C2 feeds Base(Q1) via Rwell!",
           size=10.6, color=COL_WARN, anchor="middle", weight="bold")
    d.text(342, 555, "N+ / P+ Guard Rings (Green) intercept minority carriers & clamp Rwell, Rsub -> 0!",
           size=10.6, color=COL_BIAS, anchor="middle", weight="bold")

    # Right Analytical Callouts
    d.callout(682, 76, 378, 166, "1. Physical Latch-Up Mechanism (§18.8)", [
        "• Every bulk CMOS pair forms a 4-layer P+ / N-well /",
        "  P-sub / N+ Silicon-Controlled Rectifier (SCR)!",
        "• ESD/I/O overshoot or substrate bounce injects current",
        "  through Rsub or Rwell: once I·R ≥ 0.7 V turns ON Q1/Q2",
        "  with loop gain β1·β2 ≥ 1, VDD shorts to GND until",
        "  power is cycled (or metal melts)!",
    ], tone="warn", fs=10.4)

    d.callout(682, 256, 378, 162, "2. Mandatory Layout Prevention Rules", [
        "1. Place dense N+ well taps (to VDD) & P+ substrate",
        "   taps (to VSS) throughout all analog blocks -> Rwell, Rsub ↓.",
        "2. Surround noisy digital, I/O ESD, & large switches",
        "   with continuous double Guard Rings (P+ in P-sub,",
        "   N+ in N-well) to collect injected minority carriers!",
    ], tone="bias", fs=10.4)

    d.callout(682, 432, 378, 146, "3. Deep N-Well (Triple-Well) Isolation", [
        "• In 90nm/65nm/45nm RF & mixed-signal PDKs, placing",
        "  sensitive NMOS inside an isolated P-well within a",
        "  VDD-biased Deep N-Well shields substrate noise AND",
        "  eliminates body effect (tie local P-well to Source)!",
    ], tone="sig", fs=10.4)
    return d


def diag_37_common_centroid_multifinger():
    d = SVGDoc(
        "common-centroid-multifinger.svg",
        "Multi-Finger Folded Gate & 2D ABBA Common-Centroid Layout (+ Dummies)",
        "Layout Chia Ngón (Multi-Finger) & Đối xứng Trọng tâm Chung ABBA Kèm Dải Giả Dummy/STI/WPE (Ch.19 §19.2)",
        "Ch.19", [19], width=1080, height=600, legend=False
    )
    d.panel(18,  74, 495, 504, "(a) Multi-Finger Folded MOSFET (M = 4 Fingers)")
    d.panel(533, 74, 529, 504, "(b) 2D ABBA Common-Centroid + Dummy Strips + WPE/LOD")

    # --- (a) Multi-Finger Layout ---
    # Active/OD green rectangle: x=95..435, y=185..325
    ox_x, ox_y, ox_w, ox_h = 95, 190, 340, 130
    # Top & bottom Polysilicon Gate buses connecting all 4 gate fingers!
    d.rect(135, 148, 260, 18, fill="#fecaca", stroke=COL_WARN, sw=1.5, rx=3)
    d.rect(135, 344, 260, 18, fill="#fecaca", stroke=COL_WARN, sw=1.5, rx=3)
    d.text(265, 140, "Double-Contacted Gate Bus (RG ↓ by 12·M²!)", size=10.5,
           color=COL_WARN, anchor="middle", weight="bold")

    # Active diffusion (Emerald tint)
    d.rect(ox_x, ox_y, ox_w, ox_h, fill="#d1fae5", stroke=COL_BIAS, sw=2.0, rx=4)

    # 4 Vertical Poly Gate Fingers at x = 152, 222, 292, 362 (width 18)
    finger_xs = [152, 222, 292, 362]
    for fx in finger_xs:
        d.rect(fx, 166, 18, 178, fill="#fca5a5", stroke=COL_WARN, sw=1.5, rx=2)

    # Alternating Source (S) & Shared Drain (D) regions + Contacts!
    # Regions center x: S(122), D(196), S(266), D(336), S(404)
    sd_cols = [
        (122, "S", COL_SIG),
        (196, "D", COL_AMBER),
        (266, "S", COL_SIG),
        (336, "D", COL_AMBER),
        (404, "S", COL_SIG),
    ]
    for sx, role, col in sd_cols:
        d.text(sx, 182, role, size=11.5, color=col, anchor="middle", weight="bold")
        for cy_c in (218, 255, 292):
            d.rect(sx - 5, cy_c - 5, 10, 10, fill=COL_DARK, stroke=COL_BG, sw=1.0, rx=1)

    d.callout(36, 386, 458, 174, "Why Folding W into M Fingers is Mandatory (§19.2)", [
        "1. Gate Resistance RG Reduction (Thermal Noise!):",
        "   • Single-side gate contact:  RG = RG,1 / (3 · M²)",
        "   • Double-side gate contact:  RG = RG,1 / (12 · M²) !",
        "2. Drain Junction Capacitance CDB Halved:",
        "   • Even M shares internal drains between 2 gates,",
        "     cutting CDB area & sidewall perimeter by ~2x!",
    ], tone="sig", fs=10.4)

    # --- (b) 2D ABBA Common-Centroid + Dummies + WPE/STI ---
    # Outer Well / STI Boundary Box (dashed purple)
    d.rect(562, 126, 470, 242, fill="#f8fafc", stroke=COL_PURPLE, sw=1.8, rx=8, dash="6,4")
    d.text(797, 144, "N-Well / STI Edge Boundary (Keep WPE & LOD Margin ≥ d_min!)",
           size=10.3, color=COL_PURPLE, anchor="middle", weight="bold")

    # Left & Right Dummy Strips (Gray) + Central 2x2 [A1 B1 ; B2 A2] Cells!
    # Left Dummy: x=590..638, y=162..342
    d.rect(590, 164, 46, 180, fill="#e2e8f0", stroke=COL_MUTED, sw=1.6, rx=5)
    d.text(613, 250, "DUM", size=10.8, color=COL_MUTED, anchor="middle", weight="bold")
    d.text(613, 266, "(VSS)", size=9.8, color=COL_MUTED, anchor="middle")

    # Right Dummy: x=958..1004, y=164..344
    d.rect(958, 164, 46, 180, fill="#e2e8f0", stroke=COL_MUTED, sw=1.6, rx=5)
    d.text(981, 250, "DUM", size=10.8, color=COL_MUTED, anchor="middle", weight="bold")
    d.text(981, 266, "(VSS)", size=9.8, color=COL_MUTED, anchor="middle")

    # 2x2 Common-Centroid Matrix centered at (797, 254):
    # Top-Left A1 (662, 164), Top-Right B1 (808, 164)
    # Bot-Left B2 (662, 262), Bot-Right A2 (808, 262)  (each w=124, h=82)
    cells = [
        (662, 164, "M1a (A1)", "#dbeafe", COL_SIG),
        (808, 164, "M2a (B1)", "#d1fae5", COL_BIAS),
        (662, 262, "M2b (B2)", "#d1fae5", COL_BIAS),
        (808, 262, "M1b (A2)", "#dbeafe", COL_SIG),
    ]
    for cx_cell, cy_cell, clbl, cfill, ccol in cells:
        d.rect(cx_cell, cy_cell, 124, 82, fill=cfill, stroke=ccol, sw=2.0, rx=6)
        d.text(cx_cell + 62, cy_cell + 46, clbl, size=12.5, color=ccol, anchor="middle", weight="bold")

    # Diagonal Crosshairs meeting at Exact Shared Centroid (797, 254)!
    d.line(724, 205, 870, 303, color=COL_SIG, sw=1.6, dash="4,3")
    d.line(870, 205, 724, 303, color=COL_BIAS, sw=1.6, dash="4,3")
    d.circle(797, 254, 6.5, fill=COL_WARN, stroke=COL_BG, sw=2.0)

    # Process / Thermal Gradient Vector Arrow across wafer
    d.arrow(580, 358, 1012, 358, color=COL_WARN, sw=1.9)
    d.text(797, 353, "Linear Wafer / Thermal Gradient ∇P(x, y) -> Cancels at Shared Centroid!",
           size=10.0, color=COL_WARN, anchor="middle", weight="bold")

    d.callout(550, 386, 494, 174, "Nanometer Layout Matching Checklist (90nm / 65nm / 45nm)", [
        "• Same Orientation: Current MUST flow parallel (never rotate 90°!).",
        "• Common-Centroid [A B / B A] or 1D [A B B A]: Identical center",
        "  of gravity (Xc, Yc) cancels 1st-order tox, VTH & ΔT gradients!",
        "• Dummy Poly & Active Strips: Equalize poly etch micro-loading",
        "  AND equalize STI Mechanical Stress (LOD) across all fingers!",
        "• Well Proximity Effect (WPE): Keep matched pairs far & equidistant",
        "  from N-Well edges where scattered implant ions shift VTH!",
    ], tone="amber", fs=10.2)
    return d


def diag_38_upgrade_evolution_map():
    d = SVGDoc(
        "upgrade-evolution-map.svg",
        "Razavi CMOS Knowledge Brain: 19-Chapter Circuit Upgrade & Evolution Map",
        "Bản đồ Tổng thể Tiến hóa Cấu trúc Vi mạch Tương tự CMOS qua 19 Chương Sách Razavi",
        "Ch.01–19", list(range(1, 20)), width=1160, height=680, legend=False
    )

    lanes = [
        (72,  "1. Device & Single-Stage Core (Ch.1–3, 11, 17)", "#eff6ff", "#93c5fd", COL_SIG, [
            ("Square-Law MOS", "Ch.02 Vov"),
            ("Short-Ch gm/ID", "Ch.11/17 VDS,min"),
            ("CS Amplifiers", "Ch.03 RD/Diode/I"),
            ("Degenerated / CG", "Ch.03 Rout Boost"),
            ("Telescopic Casc", "Ch.03 gm·ro²"),
            ("Gain-Boost Casc", "Ch.09 (gm·ro)³"),
        ], ["vsat/DIBL", "Gain", "Linear/HF", "Rout↑", "+Aaux"]),

        (190, "2. Current Mirrors, Biasing, Bandgap & LDO (Ch.5, 12)", "#ecfdf5", "#6ee7b7", COL_BIAS, [
            ("Basic Mirror", "Ch.05 CLM err"),
            ("Cascode Mirror", "Ch.05 VTH+2Vov!"),
            ("LVCCML Mirror", "Ch.05 2·VDS,min!"),
            ("Const-Gm + Start", "Ch.12 gm=2../RS"),
            ("1.25V Bandgap", "Ch.12 CTAT+PTAT"),
            ("Sub-1V BGR & LDO", "Ch.12/08/10"),
        ], ["Rout↑", "Save VTH!", "Self-Bias", "Zero-TC", "VDD≤1V"]),

        (308, "3. Differential Pairs & Op-Amp Architectures (Ch.4, 9)", "#eff6ff", "#93c5fd", COL_SIG, [
            ("Basic Diff-Pair", "Ch.04 Virt GND"),
            ("Gilbert / Deg DP", "Ch.04 VGA/Mult"),
            ("5T Active OTA", "Ch.05 gm(ro2||4)"),
            ("Telescopic OTA", "Ch.09 Fast/5·Vov"),
            ("Folded-Cascode", "Ch.09 Ifold>It/2"),
            ("Two-Stage + CMFB", "Ch.09 Max Swing!"),
        ], ["Linear/VGA", "SE Gain", "Casc Av↑", "Wide ICMR", "Swing↑"]),

        (426, "4. Frequency, Noise, Feedback & Compensation (Ch.6–8, 10)", "#fffbeb", "#fcd34d", COL_AMBER, [
            ("Miller & Doublet", "Ch.06 +gm/Cgd"),
            ("Vn², In² Noise", "Ch.07 4kTγgm,1/f"),
            ("4-Topo Feedback", "Ch.08 Sense-Ret"),
            ("Middlebrook STB", "Ch.08 iprobe"),
            ("Pole Split + Rz", "Ch.10 LHP Zero!"),
            ("Ahuja & Nyquist", "Ch.10 Heavy CL"),
        ], ["SNR Budget", "Close Loop", "Exact T(s)", "Comp 2-Stg", "Kill RHP z"]),

        (544, "5. Sampled-Data, PLLs, Mismatch & Physical IC (Ch.13–16, 18–19)", "#fef2f2", "#fca5a5", COL_WARN, [
            ("Pelgrom Duality", "Ch.14 VOS vs ΔI"),
            ("ABBA + GuardRing", "Ch.18/19 Layout"),
            ("Bottom-Plate SC", "Ch.13 φ1e Rule"),
            ("Bootstrap + CDS", "Ch.13/14 VGS=VDD"),
            ("Ring & LC VCO", "Ch.15 gm·Rp≥1"),
            ("Type-II CP-PLL", "Ch.16 Rp·C1 Zero"),
        ], ["Physical", "Zero Qinj", "Low-VDD/1/f", "Generate f", "Lock Phase"]),
    ]

    for ly, ltitle, lbg, lbd, lcol, nodes, edges in lanes:
        d.rect(18, ly, 1124, 106, fill=lbg, stroke=lbd, sw=1.3, rx=8, opacity=0.45)
        d.text(30, ly + 19, ltitle, size=11.8, color=COL_DARK, weight="bold")

        for idx, (ntitle, nsub) in enumerate(nodes):
            nx = 30 + idx * 186
            ny = ly + 30
            nw, nh = 138, 62
            d.rect(nx, ny, nw, nh, fill=COL_BG, stroke=lcol, sw=1.8, rx=7)
            d.text(nx + nw / 2, ny + 26, ntitle, size=11.0, color=COL_DARK, anchor="middle", weight="bold")
            d.text(nx + nw / 2, ny + 45, nsub, size=9.8, color=COL_MUTED, anchor="middle")

            if idx < len(edges):
                ax1 = nx + nw + 3
                ax2 = nx + 186 - 5
                ay = ny + nh / 2
                d.arrow(ax1, ay, ax2, ay, color=lcol, sw=1.8)
                d.text((ax1 + ax2) / 2, ay - 7, edges[idx], size=9.2,
                       color=lcol, anchor="middle", weight="bold")

    return d


# ==============================================================================
# PART 6: DIAGRAMS 39 - 56 (Fine-Grained Razavi Sub-Topologies & EDA/GitHub Flows)
# ==============================================================================

def diag_39_regulated_cascode_ssf():
    d = SVGDoc(
        "regulated-cascode-ssf.svg",
        "Super Source Follower (SSF) & Regulated Cascode Local Feedback Loops",
        "Bộ Đệm Super Source Follower & Cascode Điều chỉnh Độ lợi — Vòng Hồi tiếp Cục bộ Nhân Trở kháng (Ch.03/09)",
        "Ch.03/09", [3, 5, 9], width=1080, height=600
    )
    d.panel(18,  74, 510, 504, "(a) Super Source Follower (Ultra-Low Rout Buffer)")
    d.panel(548, 74, 514, 504, "(b) Regulated (Gain-Boosted) Cascode Current Branch")

    # --- (a) Super Source Follower ---
    # PMOS M1 follower (x=210, y=245), top current source Ib1 from VDD (y=120..185)
    d.vdd(210, 122, "VDD")
    ib1 = d.isrc_v(210, 154, direction="down", color=COL_BIAS, label="Ib1", label_side="left")
    d.line(210, 122, 210, ib1["t"][1], color=COL_BIAS)
    m1 = d.pmos(210, 245, facing="right", color=COL_SIG, label="M1", sub="Follower")
    d.line(210, ib1["b"][1], 210, m1["s"][1], color=COL_SIG)
    d.port(150, 245, "Vin", side="left", color=COL_SIG)
    d.line(150, 245, m1["g"][0], 245, color=COL_SIG)

    # Bottom current source Ib2 from M1 drain to GND
    ib2 = d.isrc_v(210, 365, direction="down", color=COL_BIAS, label="Ib2", label_side="left")
    d.line(210, m1["d"][1], 210, ib2["t"][1], color=COL_DARK)
    d.gnd(210, ib2["b"][1])

    # Feedback NMOS M2 (x=335, y=245): Drain tied to Vout (source of M1!), Gate tied to Drain of M1 (node A), Source to GND
    m2 = d.nmos(335, 290, facing="right", color=COL_AMBER, label="M2", sub="FB Loop")
    # Connect M1 source (210, 205) to Vout rail & M2 drain
    d.dot(210, 205, COL_SIG)
    d.wire([(210, 205), (335, 205), m2["d"]], color=COL_SIG, sw=2.1)
    d.line(335, 205, 420, 205, color=COL_SIG, sw=2.1)
    d.port(420, 205, "Vout", side="right", color=COL_SIG)

    # Connect node A (210, 305) to M2 gate
    d.dot(210, 305, COL_AMBER)
    d.wire([(210, 305), (285, 305), (285, 290), m2["g"]], color=COL_AMBER, sw=2.0)
    d.text(246, 297, "Node A", size=10.5, color=COL_AMBER, anchor="middle", weight="bold")
    d.gnd(335, m2["s"][1])

    d.callout(36, 418, 474, 142, "SSF Local Shunt Feedback Inspection", [
        "• Standard SF output resistance:  Rout,SF ≈ 1 / gm1",
        "• Local loop M1-drain -> M2-gate boosts pull-down current by (gm1·ro1):",
        "  Rout,SSF ≈ 1 / (gm1 · gm2 · ro1)   (20x–80x lower Rout!)",
        "• Trade-off: Two-pole local loop requires CL stability check!",
    ], tone="sig", fs=10.5)

    # --- (b) Regulated Cascode ---
    d.port(815, 118, "Iout (Rout)", side="right", color=COL_SIG)
    d.arrow(815, 124, 815, 160, color=COL_SIG, sw=2.0)
    mc = d.nmos(815, 205, facing="right", color=COL_SIG, label="M2", sub="Cascode")
    d.line(815, 160, 815, mc["d"][1], color=COL_SIG)

    m_main = d.nmos(815, 335, facing="right", color=COL_DARK, label="M1", sub="Main CS/Isrc")
    d.line(815, mc["s"][1], 815, m_main["d"][1], color=COL_DARK)
    d.gnd(815, m_main["s"][1])
    d.port(750, 335, "Vin / Vb1", side="left", color=COL_DARK)
    d.line(750, 335, m_main["g"][0], 335, color=COL_DARK)

    # Auxiliary Amplifier facing left? No, facing right or left: sense VX at (815, 270), compare to Vref_x, drive M2 gate (785, 205)!
    d.dot(815, 270, COL_AMBER)
    d.text(826, 274, "VX ≈ Vref", size=10.8, color=COL_AMBER, weight="bold")
    amp = d.opamp(685, 218, w=58, h=50, facing="right", plus_top=True, label="Aaux", color=COL_AMBER, fill="#fffbeb")
    # + input = Vb_set, - input = VX
    d.port(605, 205, "VDS,set", side="left", color=COL_BIAS, fs=11)
    d.line(605, 205, amp["in_top"][0], amp["in_top"][1], color=COL_BIAS)
    d.wire([(815, 270), (636, 270), (636, amp["in_bot"][1]), amp["in_bot"]], color=COL_AMBER, sw=1.9)
    # Output of Aaux drives M2 gate at (785, 205)
    d.wire([amp["out"], (755, 218), (755, 205), mc["g"]], color=COL_AMBER, sw=2.0)

    d.callout(566, 418, 478, 142, "Regulated Cascode Impedance Multiplication", [
        "• Loop locks VX ≈ VDS,set (can sit right at VDS1,min + 50 mV!).",
        "• Effective cascode transconductance becomes (1 + Aaux)·gm2:",
        "  Rout,RGC ≈ (1 + Aaux) · gm2 · ro2 · ro1   ~ O((gm·ro)³) !",
        "• Stability Window:  ω_p,out < ω_u,aux < ω_p2 (avoid doublet!).",
    ], tone="amber", fs=10.5)
    return d


def diag_40_diff_pair_active_mirror():
    d = SVGDoc(
        "diff-pair-active-mirror.svg",
        "5T Differential Pair with Active Mirror Load: Full Gm Restoration & Doublet",
        "Cặp Vi sai Tải Gương dòng Tích cực (5T-OTA): Khôi phục Hỗ dẫn Gm Toàn phần & Cặp Cực–Zero (Ch.04/05)",
        "Ch.04/05", [4, 5, 6], width=1080, height=600
    )
    d.panel(18,  74, 530, 504, "(a) Differential-to-Single-Ended Signal Current Superposition")
    d.panel(566, 74, 496, 504, "(b) Asymmetric Mirror Pole-Zero Doublet & CMRR Limit")

    # VDD bar across x=145..415 at y=126
    d.line(145, 126, 415, 126, color=COL_DARK, sw=2.4)
    d.text(280, 114, "VDD", size=11.5, color=COL_DARK, anchor="middle", weight="bold")

    # M3 (diode PMOS, left x=195, facing="left" so gates face center!) and M4 (PMOS, right x=365, facing="right")
    m3 = d.pmos(195, 185, facing="left", color=COL_BIAS, label="M3", sub="Diode 1/gm3", label_side="left")
    m4 = d.pmos(365, 185, facing="right", color=COL_BIAS, label="M4", sub="Mirror Load", label_side="right")
    d.line(195, 126, 195, m3["s"][1], color=COL_DARK)
    d.line(365, 126, 365, m4["s"][1], color=COL_DARK)
    # Mirror gate bus at y=185 from m3["g"] (225, 185) to m4["g"] (335, 185)
    d.line(m3["g"][0], 185, m4["g"][0], 185, color=COL_BIAS, sw=2.0)
    # Diode connection from M3 drain (195, 222) up to gate bus (250, 185)
    d.dot(195, 222, COL_BIAS)
    d.dot(250, 185, COL_BIAS)
    d.wire([(195, 222), (250, 222), (250, 185)], color=COL_BIAS, sw=1.9)
    d.text(280, 175, "Node X (CX)", size=10.5, color=COL_BIAS, anchor="middle", weight="bold")

    # Input NMOS diff pair M1 (x=195), M2 (x=365) at y=315
    m1 = d.nmos(195, 315, facing="right", color=COL_SIG, label="M1", label_side="left")
    m2 = d.nmos(365, 315, facing="left", color=COL_SIG, label="M2", label_side="right")
    d.line(195, 209, 195, m1["d"][1], color=COL_DARK)
    d.line(365, 209, 365, m2["d"][1], color=COL_DARK)

    d.port(122, 315, "Vin+", side="left", color=COL_SIG)
    d.line(122, 315, m1["g"][0], 315, color=COL_SIG)
    d.port(438, 315, "Vin-", side="right", color=COL_SIG)
    d.line(m2["g"][0], 315, 438, 315, color=COL_SIG)

    # Single-ended output Vout at M4/M2 drain (365, 255)
    d.dot(365, 255, COL_SIG)
    d.line(365, 255, 452, 255, color=COL_SIG, sw=2.2)
    d.port(452, 255, "Vout", side="right", color=COL_SIG)

    # Tail node P & M5 current source
    d.wire([m1["s"], (195, 365), (365, 365), m2["s"]], color=COL_DARK, sw=2.0)
    d.dot(280, 365, COL_DARK)
    iss = d.isrc_v(280, 405, direction="down", color=COL_BIAS, label="ISS (ro5)", label_side="right")
    d.line(280, 365, 280, iss["t"][1], color=COL_BIAS)
    d.gnd(280, iss["b"][1])

    # Small-signal current annotations
    d.text(138, 258, "+gm1·vin/2", size=10.5, color=COL_SIG, anchor="middle", weight="bold")
    d.text(422, 226, "Mirrored", size=10.0, color=COL_BIAS, anchor="start")
    d.text(422, 240, "+gm1·vin/2", size=10.2, color=COL_BIAS, anchor="start", weight="bold")

    d.callout(36, 452, 494, 110, "Full Transconductance Restoration (§4.3 / §5.3)", [
        "• M1 pulls +gm1·vin/2 from M3 -> M4 mirrors +gm1·vin/2 into Vout;",
        "  simultaneously M2 pushes +gm1·vin/2 into Vout -> Iout = gm1·vin !",
        "• Voltage Gain:  Av = gm1 · (ro2 || ro4)   (2x single-side gain!).",
    ], tone="sig", fs=10.4)

    # --- (b) Two-Path Frequency Response & CMRR ---
    d.callout(586, 112, 456, 146, "1. Two Parallel Signal Paths -> Pole-Zero Doublet (§6.6)", [
        "• Path 1 (Direct via M2): Instantaneous current +gm1·vin/2 -> Vout.",
        "• Path 2 (Mirrored M1->M3->M4): Delayed by mirror pole",
        "  ω_p,m ≈ gm3 / CX   where CX = CGS3 + CGS4 + CDB1 + CDB3.",
        "• Summing both paths creates an LHP Zero at ω_z = 2 · ω_p,m !",
        "  Close pole-zero doublet causes slow exponential settling tail!",
    ], tone="amber", fs=10.4)

    d.callout(586, 274, 456, 136, "2. Common-Mode Rejection Ratio (CMRR) Miracle", [
        "• Even with finite tail impedance RSS = ro5, diode M3 senses",
        "  common-mode tail current ΔICM/(1+2gm1·RSS) and M4 cancels it!",
        "• Perfect symmetry gives Av,CM ≈ -1 / (2·gm3·RSS) << 1,",
        "  yielding  CMRR = |Av,DM / Av,CM| ≈ 2·gm1·RSS · gm3·(ro2||ro4) !",
    ], tone="bias", fs=10.4)

    d.callout(586, 426, 456, 134, "3. Systematic Offset Trap in 5T-OTA", [
        "• Node X sits at VX = VDD - |VGS3|, while Vout may sit elsewhere!",
        "• If Vout ≠ VX, channel-length modulation |VDS4| ≠ |VDS3| creates",
        "  systematic input offset VOS,sys = ΔVDS / [gm1·(ro2||ro4)] !",
    ], tone="warn", fs=10.4)
    return d


def diag_41_wilson_current_mirror():
    d = SVGDoc(
        "wilson-current-mirror.svg",
        "Modified Wilson Current Mirror vs Wide-Swing Cascode (LVCCML)",
        "Gương dòng Wilson Cải tiến (Hồi tiếp Âm Dòng–Áp) đối chiếu Gương dòng Áp thấp LVCCML (Ch.05)",
        "Ch.05", [5], width=1080, height=600
    )
    d.panel(18,  74, 520, 504, "(a) Modified 4-MOS Wilson Mirror (VDS1 = VDS2 Equalized)")
    d.panel(556, 74, 506, 504, "(b) Headroom & Accuracy Trade-Off Across 4 Mirror Families")

    # Reference current Iref at left column x=165, Output Iout at right column x=355
    d.vdd(165, 118, "VDD")
    iref = d.isrc_v(165, 150, direction="down", color=COL_BIAS, label="Iref", label_side="left")
    d.line(165, 118, 165, iref["t"][1], color=COL_BIAS)

    # M4 (diode-connected equalizer on left x=165, y=225) so VDS1 matches VDS2!
    m4 = d.nmos(165, 225, facing="left", color=COL_MUTED, label="M4", sub="VDS Equalizer", label_side="left")
    d.line(165, iref["b"][1], 165, m4["d"][1], color=COL_BIAS)
    d.dot(165, 192, COL_MUTED)
    d.wire([(165, 192), (212, 192), (212, 225), m4["g"]], color=COL_MUTED, sw=1.8)

    m3 = d.nmos(355, 225, facing="right", color=COL_SIG, label="M3", sub="FB Cascode", label_side="right")
    d.port(355, 136, "Iout (Rout)", side="right", color=COL_SIG)
    d.arrow(355, 144, 355, m3["d"][1], color=COL_SIG, sw=2.0)

    # Wire Iref node (165, 192) across to M3 gate (325, 225)!
    d.wire([(212, 192), (285, 192), (285, 225), m3["g"]], color=COL_AMBER, sw=2.0)
    d.dot(212, 192, COL_AMBER)

    # Bottom pair: M1 (left x=165, y=350, facing="left") and M2 (right x=355, y=350, facing="right", DIODE connected!)
    m1 = d.nmos(165, 350, facing="left", color=COL_BIAS, label="M1", sub="Sense", label_side="left")
    m2 = d.nmos(355, 350, facing="right", color=COL_BIAS, label="M2", sub="Diode Ref", label_side="right")
    d.line(165, m4["s"][1], 165, m1["d"][1], color=COL_DARK)
    d.line(355, m3["s"][1], 355, m2["d"][1], color=COL_DARK)

    # Gate bus M1-M2 at y=350 tied to M2 drain / M3 source node (355, 290)!
    d.line(m1["g"][0], 350, m2["g"][0], 350, color=COL_BIAS, sw=2.0)
    d.dot(355, 290, COL_BIAS)
    d.dot(295, 350, COL_BIAS)
    d.wire([(355, 290), (295, 290), (295, 350)], color=COL_BIAS, sw=1.9)

    d.gnd(165, m1["s"][1])
    d.gnd(355, m2["s"][1])

    d.text(118, 292, "VD1=VGS2", size=10.2, color=COL_BIAS, anchor="end", weight="bold")
    d.text(405, 292, "VD2=VGS2", size=10.2, color=COL_BIAS, anchor="start", weight="bold")

    d.callout(36, 424, 484, 136, "Negative-Feedback Loop Operation", [
        "• Any pull on Iout raises VD2 -> raises VG1 -> M1 pulls down VG3 ->",
        "  M3 opposes ΔIout!  Rout ≈ gm3 · ro3 · ro1 / 2.",
        "• Diode M4 equalizes VD1 = VD2 = VGS2 -> zero systematic CLM error!",
        "• Fatal Low-VDD Cost: Input branch demands 2·VGS = 2·VTH + 2·Vov,",
        "  and output branch still loses VGS2 + VDS3,min = VTH + 2·Vov !",
    ], tone="warn", fs=10.2)

    # --- (b) Comparison Table / Bars ---
    rows = [
        ("1. Basic 2-MOS Mirror", "Vout,min = Vov", "Rout = ro2", "High CLM error (~10%)", "neutral"),
        ("2. Standard Cascode", "Vout,min = VTH + 2·Vov", "Rout ≈ gm·ro²", "Wastes 1 VTH at output!", "warn"),
        ("3. Modified Wilson", "Vout,min = VTH + 2·Vov", "Rout ≈ gm·ro²/2", "Asymmetric noise/poles + 2VGS in!", "amber"),
        ("4. Wide-Swing LVCCML", "Vout,min = 2·VDS,min !", "Rout ≈ gm·ro²", "Best for ≤1.2V CMOS (Vb=VTH+2Vov)!", "bias"),
    ]
    ry = 118
    for rtitle, vmin_s, rout_s, note_s, rtone in rows:
        d.callout(576, ry, 466, 98, rtitle, [
            f"• Headroom:  {vmin_s}    |    Impedance:  {rout_s}",
            f"• Verdict:   {note_s}",
        ], tone=rtone, fs=10.4)
        ry += 110
    return d


def diag_42_noise_stages_comparison():
    d = SVGDoc(
        "noise-stages-comparison.svg",
        "Input-Referred Noise Laws Across CS, CG, SF & Cascode Topologies",
        "Quy luật Nhiễu Quy đổi Ngõ vào của 4 Tầng Khuếch đại Cơ bản: CS, CG, SF & Cascode (Razavi Ch.07 §7.4)",
        "Ch.07", [7], width=1080, height=600
    )
    cols = [
        (18,  "1. Common-Source (CS)", COL_SIG),
        (282, "2. Common-Gate (CG)", COL_AMBER),
        (546, "3. Source Follower (SF)", COL_WARN),
        (810, "4. Cascode Stage", COL_BIAS),
    ]
    for px, ptitle, _ in cols:
        d.panel(px, 74, 252, 322, ptitle)

    # 1. CS mini schematic (center x=144)
    d.vdd(144, 128, "VDD")
    rd = d.res_v(144, 162, color=COL_DARK, label="RD", label_side="right")
    d.line(144, 128, 144, rd["t"][1])
    m_cs = d.nmos(144, 248, facing="right", color=COL_SIG, label="M1", sub="gm1 (MAX!)")
    d.line(144, rd["b"][1], 144, m_cs["d"][1])
    d.dot(144, 204, COL_SIG)
    d.port(195, 204, "Vout", side="right", color=COL_SIG, fs=10.8)
    d.line(144, 204, 195, 204, color=COL_SIG)
    d.port(82, 248, "Vin", side="left", color=COL_SIG, fs=10.8)
    d.line(82, 248, m_cs["g"][0], 248, color=COL_SIG)
    d.gnd(144, m_cs["s"][1])
    d.text(144, 326, "Vn,in² = 4kT(γ/gm1 + 1/(gm1²RD))", size=9.8, color=COL_SIG, anchor="middle", weight="bold")
    d.text(144, 344, "+ K / (Cox·W1·L1·f)", size=9.8, color=COL_MUTED, anchor="middle")
    d.text(144, 372, "Best low-noise voltage front-end!", size=9.8, color=COL_BIAS, anchor="middle", weight="bold")

    # 2. CG mini schematic (center x=408)
    d.vdd(408, 128, "VDD")
    rd2 = d.res_v(408, 160, color=COL_DARK, label="RD", label_side="right")
    d.line(408, 128, 408, rd2["t"][1])
    m_cg = d.nmos(408, 228, facing="right", color=COL_AMBER, label="M1", sub="CG")
    d.line(408, rd2["b"][1], 408, m_cg["d"][1])
    d.port(346, 228, "Vb", side="left", color=COL_BIAS, fs=10.8)
    d.line(346, 228, m_cg["g"][0], 228, color=COL_BIAS)
    d.dot(408, 262, COL_SIG)
    d.port(344, 262, "Vin", side="left", color=COL_SIG, fs=10.8)
    d.line(344, 262, 408, 262, color=COL_SIG)
    ib_cg = d.isrc_v(408, 292, direction="down", color=COL_WARN, label="Ib!", label_side="right")
    d.line(408, 262, 408, ib_cg["t"][1], color=COL_WARN)
    d.gnd(408, ib_cg["b"][1])
    d.text(408, 346, "Bias Ib injects In² directly", size=9.8, color=COL_WARN, anchor="middle", weight="bold")
    d.text(408, 364, "into input source node!", size=9.8, color=COL_WARN, anchor="middle")
    d.text(408, 382, "In,in² = 4kTγ·gm,b + In,RD²", size=9.6, color=COL_DARK, anchor="middle")

    # 3. SF mini schematic (center x=672)
    d.vdd(672, 128, "VDD")
    m_sf = d.nmos(672, 188, facing="right", color=COL_SIG, label="M1", sub="Follower")
    d.line(672, 128, 672, m_sf["d"][1])
    d.port(610, 188, "Vin", side="left", color=COL_SIG, fs=10.8)
    d.line(610, 188, m_sf["g"][0], 188, color=COL_SIG)
    d.dot(672, 226, COL_SIG)
    d.port(725, 226, "Vout", side="right", color=COL_SIG, fs=10.8)
    d.line(672, 226, 725, 226, color=COL_SIG)
    m_b = d.nmos(672, 276, facing="right", color=COL_WARN, label="M2", sub="gm2 Noise!")
    d.line(672, 226, 672, m_b["d"][1])
    d.port(610, 276, "Vb", side="left", color=COL_BIAS, fs=10.8)
    d.line(610, 276, m_b["g"][0], 276, color=COL_BIAS)
    d.gnd(672, m_b["s"][1])
    d.text(672, 344, "Vn,in² = 4kTγ(1/gm1 + gm2/gm1²)", size=9.6, color=COL_WARN, anchor="middle", weight="bold")
    d.text(672, 363, "Gain ≤ 1 cannot suppress", size=9.8, color=COL_MUTED, anchor="middle")
    d.text(672, 380, "subsequent stages' noise!", size=9.8, color=COL_WARN, anchor="middle", weight="bold")

    # 4. Cascode mini schematic (center x=936)
    d.vdd(936, 124, "VDD")
    rd4 = d.res_v(936, 152, color=COL_DARK, label="RD", label_side="right")
    d.line(936, 124, 936, rd4["t"][1])
    mc2 = d.nmos(936, 212, facing="right", color=COL_BIAS, label="M2", sub="Cascode")
    d.line(936, rd4["b"][1], 936, mc2["d"][1])
    d.port(876, 212, "Vb", side="left", color=COL_BIAS, fs=10.5)
    d.line(876, 212, mc2["g"][0], 212, color=COL_BIAS)
    mc1 = d.nmos(936, 282, facing="right", color=COL_SIG, label="M1", sub="Main gm1")
    d.line(936, mc2["s"][1], 936, mc1["d"][1])
    d.port(876, 282, "Vin", side="left", color=COL_SIG, fs=10.5)
    d.line(876, 282, mc1["g"][0], 282, color=COL_SIG)
    d.gnd(936, mc1["s"][1])
    d.text(936, 344, "Low ω: M2 noise ≈ 0 (ro1 deg!)", size=9.8, color=COL_BIAS, anchor="middle", weight="bold")
    d.text(936, 363, "High ω: CX shunts ro1 -> M2", size=9.8, color=COL_WARN, anchor="middle", weight="bold")
    d.text(936, 380, "noise rises as (ω·CX/gm1)²!", size=9.8, color=COL_WARN, anchor="middle")

    # Bottom golden synthesis banner
    d.callout(18, 412, 1044, 166, "Razavi Ch.07 Golden Noise Design Rules (Friis Cascade + Mirror Amplification Trap)", [
        "1. Maximize gm1 of Input Device (high ID, high gm/ID) to crush both its own thermal noise 4kTγ/gm1 AND load noise ÷ gm1².",
        "2. Minimize gm_load of Active Current-Source Loads (size loads in strong inversion with SMALL gm/ID & long L): Vn,in² ∝ gm_load / gm1²!",
        "3. Current-Mirror Bias Noise Trap (§7.6): A reference diode Mref mirrored by ratio K multiplies reference noise power by K²! Bypass Vbias with C_b!",
        "4. Flicker (1/f) Noise Rule: Input-referred 1/f noise scales as 1/(W·L·Cox); use large gate area W·L (or PMOS / Chopper) for DC-precision stages.",
    ], tone="sig", fs=10.5)
    return d


def diag_43_tia_shunt_shunt_feedback():
    d = SVGDoc(
        "tia-shunt-shunt-feedback.svg",
        "Shunt-Shunt CMOS Transimpedance Amplifier (TIA): Gain, Stability & Noise",
        "Bộ Khuếch đại Điện trở Chuyển tiếp (TIA Hồi tiếp Song song – Song song): Băng thông, Ổn định CPD & Nhiễu (Ch.08)",
        "Ch.08", [7, 8, 10], width=1080, height=600
    )
    d.panel(18,  74, 545, 504, "(a) Optical / Current-Sense Shunt-Shunt Feedback TIA")
    d.panel(580, 74, 482, 504, "(b) Why Feedback RF Beats Open-Loop Rin by Orders of Magnitude")

    # Photodiode current source IPD + CPD in parallel at input node X (x=215, y=285)
    ipd = d.isrc_v(105, 345, direction="up", color=COL_SIG, label="Iin (IPD)", label_side="left")
    cpd = d.cap_v(185, 345, color=COL_WARN, label="CPD + Cin", sub="Parasitic!", label_side="right")
    d.gnd(105, ipd["b"][1])
    d.gnd(185, cpd["b"][1])

    # Input summing node at y=285
    d.wire([(105, ipd["t"][1]), (105, 285), (275, 285)], color=COL_SIG, sw=2.1)
    d.line(185, cpd["t"][1], 185, 285, color=COL_WARN, sw=1.9)
    d.dot(185, 285, COL_SIG)
    d.dot(235, 285, COL_AMBER)

    # Core Inverting Amplifier -A0 centered at (335, 285)
    d.poly([(275, 245), (275, 325), (385, 285)], fill="#eff6ff", stroke=COL_SIG, sw=2.1)
    d.text(318, 290, "-A0", size=13, color=COL_SIG, anchor="middle", weight="bold")

    # Output node at x=450, y=285 + Load Cap CL
    d.line(385, 285, 495, 285, color=COL_SIG, sw=2.1)
    d.port(495, 285, "Vout", side="right", color=COL_SIG)
    d.dot(435, 285, COL_AMBER)
    cl = d.cap_v(465, 345, color=COL_DARK, label="CL", label_side="right")
    d.dot(465, 285, COL_DARK)
    d.line(465, 285, 465, cl["t"][1])
    d.gnd(465, cl["b"][1])

    # Feedback network: RF at y=195 + Phase-lead CF at y=132 between x=235 and x=435
    d.wire([(235, 285), (235, 195), (311, 195)], color=COL_AMBER, sw=2.0)
    rf = d.res_h(335, 195, color=COL_AMBER, label="RF (Gain = -RF)", label_pos="bottom")
    d.wire([rf["r"], (435, 195), (435, 285)], color=COL_AMBER, sw=2.0)

    # Parallel CF across RF for phase-lead compensation
    d.dot(265, 195, COL_PURPLE)
    d.dot(405, 195, COL_PURPLE)
    d.wire([(265, 195), (265, 132), (317, 132)], color=COL_PURPLE, sw=1.8)
    cf = d.cap_h(335, 132, color=COL_PURPLE, label="CF (Phase-Lead Zero)", label_pos="top")
    d.wire([cf["r"], (405, 132), (405, 195)], color=COL_PURPLE, sw=1.8)

    d.callout(36, 422, 508, 138, "Closed-Loop Port Equations (Current-Voltage Feedback)", [
        "• Closed-Loop Transimpedance:   ZT = Vout / Iin ≈ -RF · [A0 / (1 + A0)]",
        "• Input Virtual-Ground Resistance:   Rin,closed = RF / (1 + A0)  (tiny!)",
        "• Input -3 dB Bandwidth:   ω_-3dB ≈ (1 + A0) / [RF · (CPD + Cin)]",
        "  -> Feedback compresses Rin by (1+A0), extending bandwidth (1+A0)x!",
    ], tone="sig", fs=10.4)

    # --- (b) Right panel explanations ---
    d.callout(600, 114, 442, 146, "1. The Gain-Noise Miracle of Shunt-Shunt TIA", [
        "• Open-loop resistor R_in requires SMALL R_in for wide bandwidth",
        "  1/(R_in·CPD), which destroys gain AND explodes thermal current",
        "  noise  In,R² = 4kT / R_in !",
        "• Feedback TIA uses LARGE RF (high gain + LOW thermal noise",
        "  4kT/RF!), while A0 divides input resistance down to RF/(1+A0)!",
    ], tone="bias", fs=10.4)

    d.callout(600, 276, 442, 138, "2. Two-Pole Peaking Trap from Large Photodiode CPD", [
        "• Loop gain T(s) has two poles: amplifier pole ω_p,amp and input",
        "  feedback pole ω_p,in = 1 / [RF · (CPD + Cin + CF)].",
        "• Large CPD pushes ω_p,in below unity-loop-gain -> severe ringing!",
        "• Fix: Add small CF across RF creating LHP zero ω_z = 1/(RF·CF)!",
    ], tone="warn", fs=10.4)

    d.callout(600, 430, 442, 130, "3. Core Amplifier Noise (C_tot · ω Rising Term)", [
        "• Total input-referred current noise PSD:",
        "  In,in²(ω) = 4kT/RF + Vn,amp² · [1/RF² + ω²·(CPD + Cin)²]",
        "• At high frequency, ω²·CPD²·Vn,amp² dominates (" + "f² noise)! Match Cin ≈ CPD!",
    ], tone="amber", fs=10.3)
    return d


def diag_44_rail_to_rail_input_stage():
    d = SVGDoc(
        "rail-to-rail-input-stage.svg",
        "Complementary NMOS+PMOS Rail-to-Rail Input Stage & Constant-Gm Control",
        "Tầng Đầu vào Bù Đường–Đường (NMOS + PMOS Song song) & Ổn định Hỗ dẫn Constant-Gm (Razavi Ch.09)",
        "Ch.09", [9], width=1080, height=600
    )
    d.panel(18,  74, 535, 504, "(a) Parallel PMOS + NMOS Differential Pairs (0 to VDD ICMR)")
    d.panel(570, 74, 492, 504, "(b) Gm(VCM) 2x Variation Trap & Constant-Gm Stabilization")

    # Left: PMOS pair (x=142, 222, y=260) fed from top IP_tail; NMOS pair (x=368, 448, y=260) fed from bottom IN_tail
    d.vdd(182, 126, "VDD")
    ipt = d.isrc_v(182, 156, direction="down", color=COL_BIAS, label="ISS,P", label_side="left")
    d.line(182, 126, 182, ipt["t"][1], color=COL_BIAS)
    d.wire([(182, ipt["b"][1]), (182, 198), (142, 198), (142, 236)], color=COL_BIAS)
    d.wire([(182, 198), (222, 198), (222, 236)], color=COL_BIAS)
    d.dot(182, 198, COL_BIAS)

    mp1 = d.pmos(142, 260, facing="right", color=COL_SIG, label="MP1", label_side="left")
    mp2 = d.pmos(222, 260, facing="left", color=COL_SIG, label="MP2", label_side="right")

    mn1 = d.nmos(368, 260, facing="right", color=COL_AMBER, label="MN1", label_side="left")
    mn2 = d.nmos(448, 260, facing="left", color=COL_AMBER, label="MN2", label_side="right")

    d.wire([mn1["s"], (368, 325), (448, 325), mn2["s"]], color=COL_BIAS)
    d.dot(408, 325, COL_BIAS)
    int_src = d.isrc_v(408, 366, direction="down", color=COL_BIAS, label="ISS,N", label_side="right")
    d.line(408, 325, 408, int_src["t"][1], color=COL_BIAS)
    d.gnd(408, int_src["b"][1])

    # Tie Vin+ to MP1 & MN1 gates via clean top/bottom buses; Vin- to MP2 & MN2 gates
    d.port(72, 212, "Vin+", side="left", color=COL_SIG)
    d.wire([(72, 212), (102, 212), (102, 260), mp1["g"]], color=COL_SIG, sw=1.9)
    d.dot(102, 212, COL_SIG)
    d.wire([(102, 212), (328, 212), (328, 260), mn1["g"]], color=COL_SIG, sw=1.9)

    d.port(512, 304, "Vin-", side="right", color=COL_SIG, fs=11)
    d.wire([(512, 304), (488, 304), (488, 260), mn2["g"]], color=COL_SIG, sw=1.9)
    d.dot(488, 304, COL_SIG)
    d.wire([(488, 304), (262, 304), (262, 260), mp2["g"]], color=COL_SIG, sw=1.9)

    # Outputs go to Folded-Cascode Summing Bus at bottom/top
    d.rect(115, 418, 360, 38, fill="#f1f5f9", stroke=COL_DARK, sw=1.6, rx=6)
    d.text(295, 441, "Folded-Cascode Current-Summing Load (Iout = (gmP + gmN)·Vin)", size=11,
           color=COL_DARK, anchor="middle", weight="bold")
    d.line(142, mp1["d"][1], 142, 418, color=COL_SIG, dash="4,3")
    d.line(222, mp2["d"][1], 222, 418, color=COL_SIG, dash="4,3")
    d.line(368, mn1["d"][1], 368, 175, color=COL_AMBER, dash="4,3")
    d.line(448, mn2["d"][1], 448, 175, color=COL_AMBER, dash="4,3")
    d.text(408, 165, "To PMOS Fold Nodes", size=10, color=COL_AMBER, anchor="middle", weight="bold")

    d.callout(36, 472, 498, 90, "ICMR Coverage Condition (VDD ≥ VTHN + |VTHP| + 2·VDS,min)", [
        "• Low VCM (0 V to VDD - |VGS,P| - VDS,sat): PMOS pair MP1–MP2 active.",
        "• High VCM (VGS,N + VDS,sat to VDD): NMOS pair MN1–MN2 active.",
        "• Mid-Rail Overlap: BOTH pairs conduct simultaneously!",
    ], tone="sig", fs=10.3)

    # --- (b) Plot of Gm vs VCM ---
    ox, oy = d.axes(620, 130, 390, 190, xlabel="VCM (0 -> VDD)", ylabel="Gm,tot")
    # PMOS curve (blue dashed): flat from x=625..820 at y=235, drops to y=320 at x=890
    d.path("M 625 235 L 805 235 Q 850 235 885 320", stroke=COL_SIG, sw=2.0, dash="5,3")
    d.text(680, 253, "gm,P (PMOS)", size=10.2, color=COL_SIG, weight="bold")

    # NMOS curve (amber dashed): rises from x=745 y=320 to flat y=235 at x=815..1005
    d.path("M 740 320 Q 775 235 820 235 L 1005 235", stroke=COL_AMBER, sw=2.0, dash="5,3")
    d.text(945, 253, "gm,N (NMOS)", size=10.2, color=COL_AMBER, anchor="middle", weight="bold")

    # Uncompensated sum (red solid hump jumping to 2x at mid-rail y=155!)
    d.path("M 625 230 L 740 230 Q 780 152 815 152 Q 855 152 885 230 L 1005 230",
           stroke=COL_WARN, sw=2.6)
    d.text(815, 142, "Uncompensated Gm = 2·gm0 (2x GBW Hump!)", size=10.5,
           color=COL_WARN, anchor="middle", weight="bold")

    # Stabilized Constant-Gm line (green flat at y=224!)
    d.line(625, 222, 1005, 222, color=COL_BIAS, sw=2.4, dash="7,3")
    d.text(915, 212, "Constant-Gm Stabilized", size=10.3, color=COL_BIAS, anchor="middle", weight="bold")

    d.callout(590, 358, 454, 202, "Why 2x Gm Variation Breaks Compensation & How to Fix It", [
        "• Unity-gain frequency ω_u = Gm,tot / Cc doubles at mid-rail,",
        "  eroding Phase Margin OR wasting 2x speed at the rails!",
        "• Fix 1 (Square-Law 4x Tail Boost): Current switch steals ISS when",
        "  one pair turns off and boosts active pair tail to 4·ISS -> gm = 2·gm0!",
        "• Fix 2 (Weak-Inversion 1:1 Current Steering): Since gm = ID/(ζVT),",
        "  keeping ISS,P + ISS,N = I_const automatically holds Gm,tot constant!",
        "• Note: Input offset VOS still transitions from VOS,P to VOS,N -> THD!",
    ], tone="amber", fs=10.2)
    return d


def diag_45_nested_miller_3stage():
    d = SVGDoc(
        "nested-miller-3stage.svg",
        "Three-Stage Low-Voltage Op-Amp with Nested Miller Compensation (NMC)",
        "Op-Amp 3 Tầng Áp thấp & Bù Miller Lồng nhau (Nested Miller / Multipath NMC — Ch.10)",
        "Ch.10", [9, 10, 11], width=1080, height=600
    )
    d.panel(18,  74, 610, 504, "(a) Nested Miller Topology (Outer Cm1 + Inner Cm2 + Feedforward gmf)")
    d.panel(644, 74, 418, 504, "(b) Pole-Splitting Hierarchy & Nanometer Gain Rescue")

    # Three stages at y=300: Stage 1 (+gm1, x=135), Stage 2 (-gm2, x=310), Stage 3 (+gm3, x=485)
    # Wait: for overall negative feedback from output to Stage 1/2, let's check exact NMC polarities!
    # Stage 1 (+gm1), Stage 2 (+gm2), Stage 3 (-gm3, CS output stage):
    # - Inner Miller cap Cm2 spans Stage 3 (-gm3, inverting! Node B -> Vout)!
    # - Outer Miller cap Cm1 spans Stage 2 + Stage 3 (+gm2 * -gm3 = inverting! Node A -> Vout)!
    # Let's double check that! Node A -> (+gm2) -> Node B -> (-gm3) -> Vout:
    # Total gain from Node A to Vout is NEGATIVE (-gm2*ro2*gm3*RL), AND gain from Node B to Vout is NEGATIVE (-gm3*RL)!
    # Both Cm1 and Cm2 have negative Miller feedback around Vout! 100% textbook exact!

    d.port(48, 300, "Vin", side="left", color=COL_SIG)
    # Stage 1 (+gm1)
    d.poly([(95, 268), (95, 332), (165, 300)], fill="#eff6ff", stroke=COL_SIG, sw=2.0)
    d.text(122, 304, "+gm1", size=11.5, color=COL_SIG, anchor="middle", weight="bold")
    d.line(48, 300, 95, 300, color=COL_SIG, sw=2.0)

    # Node A at x=210
    d.line(165, 300, 265, 300, color=COL_SIG, sw=2.0)
    d.dot(210, 300, COL_WARN)
    d.text(210, 322, "Node A", size=10.5, color=COL_DARK, anchor="middle", weight="bold")

    # Stage 2 (+gm2)
    d.poly([(265, 268), (265, 332), (335, 300)], fill="#eff6ff", stroke=COL_SIG, sw=2.0)
    d.text(292, 304, "+gm2", size=11.5, color=COL_SIG, anchor="middle", weight="bold")

    # Node B at x=380
    d.line(335, 300, 435, 300, color=COL_SIG, sw=2.0)
    d.dot(380, 300, COL_AMBER)
    d.text(380, 322, "Node B", size=10.5, color=COL_DARK, anchor="middle", weight="bold")

    # Stage 3 (-gm3, CS Rail-to-Rail Output Stage)
    d.poly([(435, 268), (435, 332), (505, 300)], fill="#ecfdf5", stroke=COL_BIAS, sw=2.0)
    d.text(462, 304, "-gm3", size=11.5, color=COL_BIAS, anchor="middle", weight="bold")

    # Output Vout + CL
    d.line(505, 300, 590, 300, color=COL_SIG, sw=2.2)
    d.port(590, 300, "Vout", side="right", color=COL_SIG)
    d.dot(535, 300, COL_AMBER)
    d.dot(555, 300, COL_WARN)
    cl = d.cap_v(572, 356, color=COL_DARK, label="CL", label_side="left")
    d.dot(572, 300, COL_DARK)
    d.line(572, 300, 572, cl["t"][1])
    d.gnd(572, cl["b"][1])

    # Inner Miller Cap Cm2 from Node B (380, 300) to Vout (535, 300) at y=215
    d.wire([(380, 300), (380, 215), (439, 215)], color=COL_AMBER, sw=2.0)
    cm2 = d.cap_h(457, 215, color=COL_AMBER, label="Cm2 (Inner Loop)", label_pos="top")
    d.wire([cm2["r"], (535, 215), (535, 300)], color=COL_AMBER, sw=2.0)

    # Outer Miller Cap Cm1 from Node A (210, 300) to Vout (555, 300) at y=145
    d.wire([(210, 300), (210, 145), (364, 145)], color=COL_WARN, sw=2.1)
    cm1 = d.cap_h(382, 145, color=COL_WARN, label="Cm1 (Outer Loop: ωu = gm1/Cm1)", label_pos="top")
    d.wire([cm1["r"], (555, 145), (555, 300)], color=COL_WARN, sw=2.1)

    # Multipath Feedforward gm_f from Vin/Node A directly to Vout (dashed purple below at y=385)
    d.wire([(210, 300), (210, 385), (335, 385)], color=COL_PURPLE, sw=1.8, dash="5,3")
    d.rect(335, 369, 76, 32, fill="#f5f3ff", stroke=COL_PURPLE, sw=1.6, rx=5)
    d.text(373, 389, "-gmf (MNMC)", size=10.2, color=COL_PURPLE, anchor="middle", weight="bold")
    d.wire([(411, 385), (535, 385), (535, 300)], color=COL_PURPLE, sw=1.8, dash="5,3", marker_end="arr-purple")

    d.callout(36, 434, 574, 126, "Why Nanometer Low-VDD Design Needs 3-Stage NMC", [
        "• At 65nm/45nm (VDD ≤ 1.0 V, gm·ro ≈ 8–12), cascode stacking crushes output swing,",
        "  while a 2-stage op-amp reaches only (gm·ro)² ≈ 38–42 dB DC gain!",
        "• Three cascaded low-headroom CS stages achieve Av0 = (gm·ro)³ ≈ 60–75 dB",
        "  with full rail-to-rail Vout swing (VDS,sat to VDD - VDS,sat)!",
    ], tone="sig", fs=10.4)

    # --- (b) Right panel Sizing Rules ---
    d.callout(662, 114, 382, 152, "1. Standard NMC Stability Dimensioning", [
        "• For 60° Phase Margin (Butterworth 3rd-order closed-loop):",
        "  1) Outer unity-gain BW:   ω_u = gm1 / Cm1",
        "  2) Inner loop pole:       ω_p2 = gm2 / Cm2 ≈ 2 · ω_u",
        "  3) Output stage pole:     ω_p3 = gm3 / CL  ≥ 4 · ω_u",
        "• Requires heavy gm3 (power hungry for large CL)!",
    ], tone="amber", fs=10.3)

    d.callout(662, 282, 382, 140, "2. RHP Zero Trap & Multipath Fix (MNMC / RNMC)", [
        "• Cm1 & Cm2 create feedforward RHP zeros that degrade PM!",
        "• Multipath gmf (or Reversed NMC taking Cm2 to cascode",
        "  node instead of gate) cancels RHP zero & relaxes gm3/gm1",
        "  by 2x–5x for high-capacitance load driving!",
    ], tone="purple", fs=10.3)

    d.callout(662, 438, 382, 122, "3. Spectre STB Verification Contract", [
        "• Break outer feedback loop with iprobe -> check PM ≥ 60°",
        "  AND Gain Margin GM ≥ 10 dB across CL_min .. CL_max!",
        "• Check step response for zero hidden sub-loop ringing!",
    ], tone="bias", fs=10.3)
    return d


def diag_46_constant_gm_self_bias():
    d = SVGDoc(
        "constant-gm-self-bias.svg",
        "Constant-Gm Self-Biased Reference: Startup Escape & equilibrium Law",
        "Mạch Tự Phân cực Hỗ dẫn Không đổi (Constant-Gm): Điểm Cân bằng, Mạch Khởi động & Kháng VDD (Ch.12 §12.1)",
        "Ch.12", [5, 12], width=1080, height=600
    )
    d.panel(18,  74, 545, 504, "(a) Constant-Gm Core (1:K Ratio + RS) + Startup Circuit")
    d.panel(580, 74, 482, 504, "(b) Dual-Equilibrium Intersection & gm = 2(1-1/√K)/RS")

    # VDD bus across x=95..480 at y=126
    d.line(95, 126, 480, 126, color=COL_DARK, sw=2.4)
    d.text(290, 114, "VDD", size=11.5, color=COL_DARK, anchor="middle", weight="bold")

    # Startup branch on far left (x=130): MS1 (PMOS small pull-up), MS2 (NMOS sense), MS3 (NMOS injector into PMOS gate bus!)
    # Core left branch x=280 (M3 PMOS + M1 NMOS), Core right branch x=430 (M4 diode PMOS + M2 K*W NMOS + RS!)
    m3 = d.pmos(280, 195, facing="left", color=COL_BIAS, label="M3 (1x)", label_side="left")
    m4 = d.pmos(430, 195, facing="right", color=COL_BIAS, label="M4 (1x)", sub="Diode", label_side="right")
    d.line(280, 126, 280, m3["s"][1])
    d.line(430, 126, 430, m4["s"][1])
    d.line(m3["g"][0], 195, m4["g"][0], 195, color=COL_BIAS, sw=2.0)
    # Diode tie on M4 (right branch) so M3 mirrors I2 -> I1, while M1 is diode on left!
    d.dot(430, 230, COL_BIAS)
    d.dot(378, 195, COL_BIAS)
    d.wire([(430, 230), (378, 230), (378, 195)], color=COL_BIAS, sw=1.9)

    # Bottom NMOS M1 (diode 1x at x=280, y=315) and M2 (Kx at x=430, y=315) + RS at (430, 395)
    m1 = d.nmos(280, 315, facing="left", color=COL_SIG, label="M1 (W/L)", sub="Diode", label_side="left")
    m2 = d.nmos(430, 315, facing="right", color=COL_SIG, label="M2 (K·W/L)", sub="K = 4", label_side="right")
    d.line(280, m3["d"][1], 280, m1["d"][1])
    d.line(430, m4["d"][1], 430, m2["d"][1])
    d.line(m1["g"][0], 315, m2["g"][0], 315, color=COL_SIG, sw=2.0)
    # M1 diode tie
    d.dot(280, 276, COL_SIG)
    d.dot(332, 315, COL_SIG)
    d.wire([(280, 276), (332, 276), (332, 315)], color=COL_SIG, sw=1.9)

    rs = d.res_v(430, 392, color=COL_AMBER, label="RS", sub="Sets gm1!", label_side="right")
    d.line(430, m2["s"][1], 430, rs["t"][1])
    d.gnd(280, m1["s"][1])
    d.gnd(430, rs["b"][1])

    # Startup circuit box & injector on left (x=95..205)
    d.rect(48, 168, 148, 210, fill="#fef2f2", stroke=COL_WARN, sw=1.5, rx=7, dash="5,3")
    d.text(122, 188, "Startup Escape", size=11, color=COL_WARN, anchor="middle", weight="bold")
    d.text(122, 212, "1. If I1 = I2 = 0:", size=10, color=COL_DARK, anchor="middle")
    d.text(122, 228, "   VG,N = 0 -> M_off", size=10, color=COL_DARK, anchor="middle")
    d.text(122, 248, "2. MS pulls VG,P", size=10, color=COL_WARN, anchor="middle", weight="bold")
    d.text(122, 264, "   down -> injects", size=10, color=COL_WARN, anchor="middle")
    d.text(122, 280, "   kickstart current!", size=10, color=COL_WARN, anchor="middle")
    d.text(122, 304, "3. Once locked:", size=10, color=COL_BIAS, anchor="middle", weight="bold")
    d.text(122, 320, "   MS turns 100% OFF", size=10, color=COL_BIAS, anchor="middle")
    d.text(122, 336, "   (I_leak = 0!)", size=10, color=COL_BIAS, anchor="middle")
    # Arrow from Startup to PMOS gate bus & sense from NMOS gate bus
    d.wire([(196, 230), (235, 230), (235, 195), m3["g"]], color=COL_WARN, sw=1.8, dash="4,3")
    d.wire([(280, 355), (122, 355), (122, 378)], color=COL_MUTED, sw=1.5, dash="3,3")

    d.callout(36, 444, 508, 118, "Closed-Form Constant-Gm Law (Square-Law & Cascode Fix)", [
        "• KVL on M1–M2–RS:  VGS1 = VGS2 + I2·RS  with I1 = I2 = Iref :",
        "  Iref = [2 / (μn·Cox·(W/L)1 · RS²)] · (1 - 1/√K)²",
        "  =>  gm1 = 2 · (1 - 1/√K) / RS    (for K=4:  gm1 = 1 / RS !)",
        "• Add Cascode shields on M1–M4 to prevent VDD drift via λ (CLM)!",
    ], tone="sig", fs=10.3)

    # --- (b) Dual-Equilibrium I1 vs I2 Curve ---
    ox, oy = d.axes(636, 134, 370, 210, xlabel="I1 (NMOS Branch)", ylabel="I2")
    # 1:1 PMOS mirror line I2 = I1 (straight green line from (636,344) to (970,154))
    d.line(636, 344, 966, 156, color=COL_BIAS, sw=2.2)
    d.text(925, 148, "PMOS Mirror: I2 = I1", size=10.5, color=COL_BIAS, anchor="middle", weight="bold")

    # NMOS + RS sublinear curve starting steep at origin, crossing I2=I1 at (848, 223)!
    d.path("M 636 344 Q 685 235 848 223 T 985 206", stroke=COL_SIG, sw=2.5)
    d.text(895, 242, "NMOS + RS Law", size=10.5, color=COL_SIG, anchor="start", weight="bold")

    # Degenerate Zero Point (636, 344) - RED!
    d.circle(636, 344, 6.5, fill=COL_WARN, stroke=COL_BG, sw=2.0)
    d.text(650, 334, "Degenerate Trap (0, 0)!", size=10.5, color=COL_WARN, weight="bold")

    # Desired Operating Point (848, 223) - BLUE/GREEN!
    d.circle(848, 223, 6.5, fill=COL_SIG, stroke=COL_BG, sw=2.0)
    d.text(840, 206, "Stable Lock: gm1 = 1/RS", size=10.5, color=COL_SIG, anchor="end", weight="bold")

    d.callout(600, 384, 442, 178, "Why Self-Biased Loops Fail Without Startup & DC Sweep Test", [
        "• Positive loop gain > 1 near origin pushes circuit away from",
        "  small perturbations ONLY once VGS > VTH; at VGS = 0, loop gain = 0",
        "  so (I1=0, I2=0) is a stable dead zone!",
        "• Mandatory Verification (Spectre):",
        "  1) Slow & fast VDD ramp tran (1 ns and 10 ms) at SS, -40°C!",
        "  2) Sweep starter node voltage to prove single intersection!",
    ], tone="warn", fs=10.3)
    return d


def diag_47_sc_parasitic_insensitive_integrator():
    d = SVGDoc(
        "sc-parasitic-insensitive-integrator.svg",
        "Parasitic-Insensitive Bottom-Plate Switched-Capacitor Integrator",
        "Bộ Tích phân Tụ Chuyển mạch Miễn nhiễm Ký sinh (Stray-Insensitive SC Integrator & Xung φ1e — Ch.13 §13.4)",
        "Ch.13", [13], width=1080, height=600
    )
    d.panel(18,  74, 635, 504, "(a) 4-Switch Stray-Insensitive SC Integrator (Cp1 & Cp2 Neutralized!)")
    d.panel(670, 74, 392, 504, "(b) Non-Overlapping Bottom-Plate Clock Timing")

    # Input port Vin at (65, 220) -> S1(φ1) -> Node A (185, 220) -> CS -> Node B (305, 220) -> S3(φ2) -> Virtual GND Node X (415, 220)
    d.port(62, 220, "Vin", side="left", color=COL_SIG)
    s1 = d.sw_h(122, 220, label="S1 (φ1)", color=COL_SIG)
    d.line(62, 220, s1["l"][0], 220, color=COL_SIG)

    # Node A (178, 220): S2(φ2) down to GND + Cp1 parasitic cap down to GND!
    d.line(s1["r"][0], 220, 226, 220, color=COL_SIG)
    d.dot(172, 220, COL_DARK)
    d.dot(204, 220, COL_WARN)
    # S2 vertical branch to GND at x=172
    d.wire([(172, 220), (172, 278)], color=COL_PURPLE, sw=1.9)
    d.circle(172, 282, 2.5, fill=COL_BG, stroke=COL_PURPLE, sw=1.6)
    d.line(172, 285, 180, 300, color=COL_PURPLE, sw=2.0)
    d.circle(172, 304, 2.5, fill=COL_BG, stroke=COL_PURPLE, sw=1.6)
    d.text(158, 296, "S2(φ2)", size=10.2, color=COL_PURPLE, anchor="end", weight="bold")
    d.line(172, 307, 172, 326, color=COL_PURPLE, sw=1.9)
    d.gnd(172, 326)

    # Parasitic Cp1 at x=208
    cp1 = d.cap_v(212, 296, color=COL_WARN, label="Cp1", label_side="right")
    d.wire([(204, 220), (212, 220), cp1["t"]], color=COL_WARN, sw=1.6, dash="4,3")
    d.gnd(212, cp1["b"][1], color=COL_WARN)

    # Sampling Capacitor CS centered at (262, 220) (bottom plate on left/right? Early φ1e is at virtual-ground side Node B!)
    cs = d.cap_h(262, 220, color=COL_SIG, label="CS (Bottom->B)", label_pos="top")
    d.line(226, 220, cs["l"][0], 220, color=COL_SIG)

    # Node B (318, 220): S3 (φ1e EARLY!) down to GND + Cp2 parasitic to GND + S4 (φ2) right to Op-Amp Virtual Ground!
    d.line(cs["r"][0], 220, 368, 220, color=COL_SIG)
    d.dot(310, 220, COL_WARN)
    d.dot(342, 220, COL_BIAS)

    cp2 = d.cap_v(304, 296, color=COL_WARN, label="Cp2", label_side="left")
    d.wire([(310, 220), (304, 220), cp2["t"]], color=COL_WARN, sw=1.6, dash="4,3")
    d.gnd(304, cp2["b"][1], color=COL_WARN)

    # Early switch S3 (φ1e) at x=342
    d.line(342, 220, 342, 278, color=COL_BIAS, sw=1.9)
    d.circle(342, 282, 2.5, fill=COL_BG, stroke=COL_BIAS, sw=1.6)
    d.line(342, 285, 350, 300, color=COL_BIAS, sw=2.0)
    d.circle(342, 304, 2.5, fill=COL_BG, stroke=COL_BIAS, sw=1.6)
    d.text(354, 296, "S3(φ1e!)", size=10.2, color=COL_BIAS, anchor="start", weight="bold")
    d.line(342, 307, 342, 326, color=COL_BIAS, sw=1.9)
    d.gnd(342, 326)

    # S4 (φ2) horizontal at (388, 220) -> Virtual GND node X (435, 220) -> Op-Amp '-' input!
    s4 = d.sw_h(388, 220, label="S4 (φ2)", color=COL_PURPLE)
    oa = d.opamp(505, 233, w=64, h=56, facing="right", plus_top=False, label="OTA", color=COL_DARK)
    d.line(s4["r"][0], 220, oa["in_top"][0], oa["in_top"][1], color=COL_SIG, sw=2.0)
    d.dot(442, 220, COL_AMBER)
    # '+' input to GND
    d.wire([oa["in_bot"], (452, oa["in_bot"][1]), (452, 292)], color=COL_DARK)
    d.gnd(452, 292)

    # Integrating Capacitor CI from (442, 220) to Vout (568, 233) at y=142
    d.wire([(442, 220), (442, 142), (487, 142)], color=COL_AMBER, sw=2.0)
    ci = d.cap_h(505, 142, color=COL_AMBER, label="CI (Integrate)", label_pos="top")
    d.wire([ci["r"], (568, 142), (568, 233)], color=COL_AMBER, sw=2.0)
    d.line(oa["out"][0], 233, 608, 233, color=COL_SIG, sw=2.1)
    d.dot(568, 233, COL_AMBER)
    d.port(608, 233, "Vout", side="right", color=COL_SIG)

    d.callout(36, 386, 598, 174, "Why BOTH Parasitics Cp1 & Cp2 Vanish from H(z) (§13.4)", [
        "• Cp1 (Left Plate): Charged to Vin during φ1, then discharged harmlessly to GND via S2",
        "  during φ2 (never flows through S4 into virtual ground!).",
        "• Cp2 (Right Plate): Grounded during φ1 (V=0), then connected to OTA Virtual Ground",
        "  (V≈0) during φ2 -> ΔV_Cp2 = 0 -> steals ZERO signal charge (provided A0 >> 1)!",
        "• Exact Delayed Non-Inverting Transfer Function:",
        "  H(z) = Vout(z) / Vin(z) = + (CS / CI) · [ z⁻¹ / (1 - z⁻¹) ] !",
    ], tone="sig", fs=10.3)

    # --- (b) Timing waveforms ---
    # φ1e (green): high x=710..815, falls EARLY at 815
    d.text(690, 138, "φ1e", size=11.5, color=COL_BIAS, weight="bold")
    d.wire([(728, 144), (736, 116), (812, 116), (820, 144), (1035, 144)], color=COL_BIAS, sw=2.2)

    # φ1 (blue): high x=728..842 (falls Δt AFTER φ1e!)
    d.text(690, 198, "φ1", size=11.5, color=COL_SIG, weight="bold")
    d.wire([(728, 204), (736, 176), (838, 176), (846, 204), (1035, 204)], color=COL_SIG, sw=2.2)
    d.line(816, 112, 816, 212, color=COL_BIAS, sw=1.3, dash="3,3")
    d.line(842, 172, 842, 268, color=COL_MUTED, sw=1.3, dash="3,3")
    d.text(852, 165, "φ1e opens Δt BEFORE φ1!", size=9.8, color=COL_BIAS, weight="bold")

    # φ2 (purple): non-overlapping, rises at x=872..1005!
    d.text(690, 258, "φ2", size=11.5, color=COL_PURPLE, weight="bold")
    d.wire([(728, 264), (870, 264), (878, 236), (1002, 236), (1010, 264), (1035, 264)], color=COL_PURPLE, sw=2.2)
    d.text(858, 282, "t_nov > 0 (Never overlap φ1 & φ2!)", size=9.8, color=COL_WARN, anchor="middle", weight="bold")

    d.callout(688, 314, 356, 246, "Clock & Settling Invariants", [
        "1. Non-Overlap Deadtime t_nov:",
        "   If φ1 & φ2 overlap even 20 ps, CI discharges",
        "   straight to Vin/GND -> catastrophic integrator leak!",
        "2. Early φ1e Rule (Bottom-Plate Sampling):",
        "   S3 opens at V=0 -> constant Vin-independent Qinj;",
        "   then Node B is floating so S1 opening injects ZERO Q!",
        "3. Settling Within T_φ2 = T_clk/2 - t_nov:",
        "   t_slew + N_τ · τ_closed < T_φ2  where",
        "   β = CI / (CI + CS + Cin)  and  τ = 1 / (β · ωu).",
    ], tone="amber", fs=10.1)
    return d


def diag_48_strongarm_dynamic_comparator():
    d = SVGDoc(
        "strongarm-dynamic-comparator.svg",
        "StrongARM Dynamic Regenerative Latched Comparator (Zero Static Power)",
        "Bộ So sánh Chốt Động Tái sinh StrongARM: 4 Pha Khuếch đại – Chốt Dương & Nhiễu Giật ngược (Ch.13/14)",
        "Ch.13/14", [13, 14], width=1080, height=600
    )
    d.panel(18,  74, 545, 504, "(a) StrongARM Transistor Topology (M1–M2 + Cross-Coupled Latch)")
    d.panel(580, 74, 482, 504, "(b) 4-Phase Transient Regeneration & Kickback / Offset")

    # VDD rail at y=124 across x=115..455
    d.line(115, 124, 455, 124, color=COL_DARK, sw=2.4)
    d.text(285, 112, "VDD", size=11.5, color=COL_DARK, anchor="middle", weight="bold")

    # Cross-coupled PMOS M5 (x=215, y=185, facing="right") and M6 (x=355, y=185, facing="left")
    m5 = d.pmos(215, 185, facing="right", color=COL_BIAS, label="M5", label_side="left")
    m6 = d.pmos(355, 185, facing="left", color=COL_BIAS, label="M6", label_side="right")
    d.line(215, 124, 215, m5["s"][1])
    d.line(355, 124, 355, m6["s"][1])

    # Cross-coupled NMOS M3 (x=215, y=282, facing="right") and M4 (x=355, y=282, facing="left")
    m3 = d.nmos(215, 282, facing="right", color=COL_AMBER, label="M3", label_side="left")
    m4 = d.nmos(355, 282, facing="left", color=COL_AMBER, label="M4", label_side="right")
    d.line(215, m5["d"][1], 215, m3["d"][1])
    d.line(355, m6["d"][1], 355, m4["d"][1])

    # Output nodes Vout- (left x=215, y=234) and Vout+ (right x=355, y=234)
    d.dot(215, 234, COL_SIG)
    d.dot(355, 234, COL_SIG)
    d.port(112, 234, "Vout-", side="left", color=COL_SIG)
    d.line(112, 234, 215, 234, color=COL_SIG, sw=2.0)
    d.port(458, 234, "Vout+", side="right", color=COL_SIG)
    d.line(355, 234, 458, 234, color=COL_SIG, sw=2.0)

    d.wire([m5["g"], (175, 185), (175, 282), m3["g"]], color=COL_AMBER, sw=1.8)
    d.dot(175, 218, COL_AMBER)
    d.wire([(175, 218), (355, 218)], color=COL_AMBER, sw=1.7)
    d.dot(355, 218, COL_SIG)

    d.wire([m6["g"], (395, 185), (395, 282), m4["g"]], color=COL_AMBER, sw=1.8)
    d.dot(395, 250, COL_AMBER)
    d.wire([(395, 250), (215, 250)], color=COL_AMBER, sw=1.7)
    d.dot(215, 250, COL_SIG)

    # Precharge PMOS switches S1, S4 to VDD when CLK=0 (annotated cleanly at top-left away from M5)
    d.text(36, 146, "S1–S4 Precharge", size=10.0, color=COL_PURPLE, weight="bold")
    d.text(36, 161, "P, Q, Out± -> VDD", size=9.8, color=COL_PURPLE)
    d.text(36, 176, "(when CLK = 0)", size=9.8, color=COL_MUTED)

    # Di-nodes P (215, 326) and Q (355, 326) feeding Input Diff-Pair M1 (215, 372) and M2 (355, 372)
    d.text(198, 328, "P", size=10.8, color=COL_DARK, anchor="end", weight="bold")
    d.text(372, 328, "Q", size=10.8, color=COL_DARK, anchor="start", weight="bold")
    m1 = d.nmos(215, 372, facing="right", color=COL_SIG, label="M1", label_side="left")
    m2 = d.nmos(355, 372, facing="left", color=COL_SIG, label="M2", label_side="right")
    d.line(215, m3["s"][1], 215, m1["d"][1])
    d.line(355, m4["s"][1], 355, m2["d"][1])
    d.port(125, 372, "Vin+", side="left", color=COL_SIG)
    d.line(125, 372, m1["g"][0], 372, color=COL_SIG)
    d.port(445, 372, "Vin-", side="right", color=COL_SIG)
    d.line(m2["g"][0], 372, 445, 372, color=COL_SIG)

    # Tail clocked NMOS M_clk at (285, 456)
    d.wire([m1["s"], (215, 418), (355, 418), m2["s"]], color=COL_DARK, sw=2.0)
    d.dot(285, 418, COL_DARK)
    mclk = d.nmos(285, 462, facing="right", color=COL_PURPLE, label="Mclk", sub="Dynamic Tail")
    d.line(285, 418, 285, mclk["d"][1])
    d.port(215, 462, "CLK", side="left", color=COL_PURPLE)
    d.line(215, 462, mclk["g"][0], 462, color=COL_PURPLE)
    d.gnd(285, mclk["s"][1])

    d.text(285, 558, "Zero Static DC Current (I_DC = 0)! Energy ~ C_tot · VDD² per decision!",
           size=10.6, color=COL_BIAS, anchor="middle", weight="bold")

    # --- (b) Right panel: Transient waveforms & Regeneration Eq ---
    ox, oy = d.axes(630, 128, 388, 195, xlabel="Time after CLK ↑", ylabel="Vout+, Vout-")
    # Precharge at VDD (y=145) until x=675, then both discharge linearly (Integration phase x=675..765),
    # then M5/M6 turn ON -> Positive feedback splits Vout+ back to VDD (y=145) and Vout- to 0V (y=323)!
    d.line(630, 145, 675, 145, color=COL_DARK, sw=2.2)
    # Vout+ (Blue: slight slow discharge then snaps UP to VDD!)
    d.path("M 675 145 L 765 215 Q 805 150 855 145 L 1005 145", stroke=COL_SIG, sw=2.5)
    d.text(925, 136, "Vout+ -> VDD ('1')", size=10.5, color=COL_SIG, anchor="middle", weight="bold")
    # Vout- (Red: slightly faster discharge then snaps DOWN to GND!)
    d.path("M 675 145 L 765 232 Q 805 318 855 321 L 1005 321", stroke=COL_WARN, sw=2.5)
    d.text(925, 311, "Vout- -> GND ('0')", size=10.5, color=COL_WARN, anchor="middle", weight="bold")

    d.line(765, 125, 765, 323, color=COL_AMBER, sw=1.4, dash="4,3")
    d.text(720, 268, "Integration", size=9.8, color=COL_MUTED, anchor="middle", weight="bold")
    d.text(832, 228, "Regeneration", size=9.8, color=COL_AMBER, anchor="middle", weight="bold")
    d.text(832, 243, "e^(+t / τ_reg)", size=9.8, color=COL_AMBER, anchor="middle")

    d.callout(600, 360, 444, 200, "Dynamic Gain, Metastability & Kickback Rules", [
        "• Pre-amp integration gain A_int ≈ gm1·VTHP / (I_tail/2 · CP/CL) ≈ 3–6",
        "  divides upper latch (M3–M6) offset & noise!",
        "• Regeneration Time Constant:   τ_reg = CL / (gm,N + gm,P)",
        "  Metastability BER = exp( - T_decision / τ_reg ) !",
        "• Kickback Noise Trap: Huge ΔVDS1,2 (~VDD) couples through CGD1,2",
        "  into Vin±! Mitigate with neutralization caps, pre-amp, or Miyahara!",
    ], tone="sig", fs=10.2)
    return d


def diag_49_chopper_stabilization_principle():
    d = SVGDoc(
        "chopper-stabilization-principle.svg",
        "Chopper Stabilization: Continuous-Time VOS & 1/f Up-Modulation (Zero Folding)",
        "Kỹ thuật Ổn định Băm xung (Chopper Stabilization): Biến điệu Lệch không VOS & Nhiễu 1/f Không Gập Nhiễu Trắng (Ch.14)",
        "Ch.14", [7, 14], width=1080, height=600, legend=False
    )
    d.panel(18,  74, 1044, 222, "(a) Chopper-Stabilized Instrumentation Amplifier Architecture")
    d.panel(18, 312, 1044, 266, "(b) Frequency-Domain Spectral Evolution (Signal vs VOS + 1/f Noise)")

    y_ch = 195
    d.port(104, y_ch, "Vin (DC)", side="left", color=COL_SIG)
    d.line(104, y_ch, 175, y_ch, color=COL_SIG, sw=2.2)
    d.text(140, y_ch - 10, "(1)", size=11, color=COL_SIG, anchor="middle", weight="bold")

    # Chopper Modulator 1 (Multiplier circle at x=205)
    d.circle(205, y_ch, 24, fill="#eff6ff", stroke=COL_PURPLE, sw=2.0)
    d.line(195, y_ch - 10, 215, y_ch + 10, color=COL_PURPLE, sw=2.0)
    d.line(195, y_ch + 10, 215, y_ch - 10, color=COL_PURPLE, sw=2.0)
    d.arrow(205, 256, 205, 221, color=COL_PURPLE, sw=1.8)
    d.text(205, 272, "m1(t) @ f_chop (±1)", size=10.5, color=COL_PURPLE, anchor="middle", weight="bold")

    # Node (2) + VOS & 1/f Noise summing junction at x=355
    d.line(229, y_ch, 337, y_ch, color=COL_SIG, sw=2.1)
    d.text(282, y_ch - 10, "(2) @ f_chop", size=10.8, color=COL_SIG, anchor="middle", weight="bold")
    d.circle(355, y_ch, 16, fill="#fef2f2", stroke=COL_WARN, sw=1.9)
    d.text(355, y_ch + 4, "+", size=14, color=COL_WARN, anchor="middle", weight="bold")
    d.arrow(355, 132, 355, 177, color=COL_WARN, sw=1.9)
    d.text(355, 124, "VOS + Vn,1/f (at DC!)", size=10.8, color=COL_WARN, anchor="middle", weight="bold")

    # Broadband Amplifier A0 (f_-3dB > 3·f_chop) at x=475
    d.line(371, y_ch, 425, y_ch, color=COL_DARK, sw=2.0)
    d.poly([(425, 155), (425, 235), (535, y_ch)], fill="#f8fafc", stroke=COL_DARK, sw=2.1)
    d.text(468, y_ch + 4, "A0", size=13.5, color=COL_DARK, anchor="middle", weight="bold")
    d.text(480, 255, "f_chop > f_corner,1/f", size=10.2, color=COL_MUTED, anchor="middle")

    # Output Demodulator Chopper 2 at x=645
    d.line(535, y_ch, 621, y_ch, color=COL_DARK, sw=2.0)
    d.circle(645, y_ch, 24, fill="#eff6ff", stroke=COL_PURPLE, sw=2.0)
    d.line(635, y_ch - 10, 655, y_ch + 10, color=COL_PURPLE, sw=2.0)
    d.line(635, y_ch + 10, 655, y_ch - 10, color=COL_PURPLE, sw=2.0)
    d.arrow(645, 256, 645, 221, color=COL_PURPLE, sw=1.8)
    d.text(645, 272, "m2(t) @ f_chop (±1)", size=10.5, color=COL_PURPLE, anchor="middle", weight="bold")

    # Node (3) -> Low-Pass / Ripple-Reduction Notch Filter at x=775..885 -> Vout
    d.line(669, y_ch, 765, y_ch, color=COL_SIG, sw=2.1)
    d.text(717, y_ch - 10, "(3)", size=11, color=COL_SIG, anchor="middle", weight="bold")
    d.rect(765, 165, 128, 60, fill="#ecfdf5", stroke=COL_BIAS, sw=1.9, rx=7)
    d.text(829, 191, "LPF / Ripple", size=11.2, color=COL_BIAS, anchor="middle", weight="bold")
    d.text(829, 209, "Notch (< f_chop)", size=10.2, color=COL_MUTED, anchor="middle")

    d.line(893, y_ch, 968, y_ch, color=COL_SIG, sw=2.2)
    d.port(968, y_ch, "Vout", side="right", color=COL_SIG)

    # --- (b) Three Spectral Plots ---
    # Plot 1: Before A0 (Node 2 + VOS/1/f)
    d.axes(55, 378, 255, 145, xlabel="f", ylabel="PSD", title="Inside Amp: Signal Transposed Above 1/f")
    # 1/f skirt + VOS spike at DC (Red)
    d.arrow(68, 523, 68, 404, color=COL_WARN, sw=2.4)
    d.path("M 72 415 Q 92 498 155 506 L 300 506", stroke=COL_WARN, sw=2.0)
    d.text(108, 405, "VOS + 1/f", size=10, color=COL_WARN, weight="bold")
    # Up-modulated signal at f_chop (x=205, Blue lobe)
    d.path("M 175 523 Q 205 415 235 523", fill="#dbeafe", stroke=COL_SIG, sw=2.1)
    d.text(205, 412, "Vin @ f_chop", size=10.2, color=COL_SIG, anchor="middle", weight="bold")

    # Plot 2: After Output Chopper m2(t) (Node 3)
    d.axes(395, 378, 265, 145, xlabel="f", ylabel="PSD", title="After m2(t): Signal @ DC, VOS @ f_chop!")
    # Signal restored to baseband DC (Blue lobe at x=395..445)
    d.path("M 396 418 Q 422 422 444 523", fill="#dbeafe", stroke=COL_SIG, sw=2.2)
    d.text(432, 410, "A0·Vin @ DC", size=10.2, color=COL_SIG, weight="bold")
    # White thermal floor ONLY (no aliasing!)
    d.line(396, 506, 650, 506, color=COL_BIAS, sw=1.8, dash="5,3")
    d.text(495, 498, "1x Thermal Floor!", size=9.8, color=COL_BIAS, anchor="middle", weight="bold")
    # VOS + 1/f up-converted to f_chop (x=555) & 3f_chop (x=632)
    d.arrow(555, 523, 555, 408, color=COL_WARN, sw=2.3)
    d.path("M 530 506 Q 555 430 580 506", stroke=COL_WARN, sw=1.9)
    d.text(555, 400, "VOS+1/f @ f_chop", size=9.8, color=COL_WARN, anchor="middle", weight="bold")

    # Right summary comparison vs Auto-Zeroing
    d.callout(696, 354, 348, 206, "Chopper vs Auto-Zeroing (CDS) Duality", [
        "• Auto-Zeroing (Sampled): Samples VOS, folding wideband",
        "  thermal noise into baseband (PSD rises ~ π·f_BW/f_s !).",
        "• Chopper (Continuous Modulation): Never samples signal ->",
        "  ZERO broadband thermal noise folding (achieves nV/√Hz)!",
        "• Residual Chopper Offset Trap: Clock charge-injection spikes",
        "  at m1(t) rectify at m2(t) -> VOS,res ∝ f_chop · ΔQ!",
        "  Fix: Dead-band guard switches, nested chopper, LPF notch.",
    ], tone="sig", fs=10.1)
    return d


def diag_50_colpitts_and_quadrature_vco():
    d = SVGDoc(
        "colpitts-and-quadrature-vco.svg",
        "CMOS Colpitts LC Oscillator (Cyclostationary ISF) & Quadrature VCO",
        "Bộ Dao động LC Colpitts (Tối ưu Hàm Nhạy Xung ISF) & VCO Cầu phương I/Q (Razavi Ch.15)",
        "Ch.15", [15], width=1080, height=600
    )
    d.panel(18,  74, 510, 504, "(a) CMOS Colpitts Oscillator (gm·Rp ≥ 4 Startup & Low Phase Noise)")
    d.panel(546, 74, 516, 504, "(b) Quadrature Coupled LC-VCO (QVCO) + Coarse/Fine Tuning")

    # --- (a) Colpitts LC Oscillator ---
    # VDD rail at y=126 across x=145..365
    d.line(145, 126, 375, 126, color=COL_DARK, sw=2.4)
    d.text(260, 114, "VDD", size=11.5, color=COL_DARK, anchor="middle", weight="bold")

    # Tank Inductor Lp (x=185, y=185) and Rp (x=115, y=185) in parallel between VDD and Vout (y=235)
    rp = d.res_v(125, 182, color=COL_WARN, label="Rp", label_side="left")
    lp = d.ind_v(205, 182, color=COL_SIG, label="Lp", label_side="right")
    d.wire([(145, 126), (125, 126), rp["t"]], color=COL_WARN)
    d.line(205, 126, 205, lp["t"][1], color=COL_SIG)
    d.wire([rp["b"], (125, 236), (345, 236)], color=COL_SIG, sw=2.1)
    d.line(205, lp["b"][1], 205, 236, color=COL_SIG)
    d.dot(205, 236, COL_SIG)
    d.dot(345, 236, COL_AMBER)
    d.port(415, 236, "Vout (Tank)", side="right", color=COL_SIG)
    d.line(345, 236, 415, 236, color=COL_SIG, sw=2.1)

    # CG Transistor M1 at x=255, y=296 (Drain at 236, Gate tied to Vb, Source tapped between C1 & C2!)
    m1 = d.nmos(255, 296, facing="right", color=COL_SIG, label="M1", sub="CG Core", label_side="left")
    d.dot(255, 236, COL_SIG)
    d.line(255, 236, 255, m1["d"][1], color=COL_SIG)
    d.port(168, 296, "Vb", side="left", color=COL_BIAS)
    d.line(168, 296, m1["g"][0], 296, color=COL_BIAS)

    # Capacitive Feedback Divider: C1 from Vout (345, 236) to Source Tap X (345, 340), C2 from X to GND!
    c1 = d.cap_v(345, 286, color=COL_AMBER, label="C1", label_side="right")
    d.line(345, 236, 345, c1["t"][1], color=COL_AMBER)
    d.wire([m1["s"], (255, 340), (345, 340), c1["b"]], color=COL_AMBER, sw=2.0)
    d.dot(255, 340, COL_AMBER)
    d.dot(345, 340, COL_AMBER)

    ib = d.isrc_v(255, 386, direction="down", color=COL_BIAS, label="Ib", label_side="left")
    c2 = d.cap_v(345, 386, color=COL_AMBER, label="C2", label_side="right")
    d.line(255, 340, 255, ib["t"][1], color=COL_BIAS)
    d.line(345, 340, 345, c2["t"][1], color=COL_AMBER)
    d.gnd(255, ib["b"][1])
    d.gnd(345, c2["b"][1])

    d.callout(36, 434, 474, 128, "Colpitts Startup & Cyclostationary Phase-Noise Physics", [
        "• Resonance:  ω0 = 1 / √[ Lp · C1·C2 / (C1 + C2) ]",
        "• Startup Condition:  gm · Rp ≥ (C1 + C2)² / (C1 · C2) ≥ 4  (at C1=C2)!",
        "  (Harder startup than cross-coupled LC gm·Rp ≥ 1!)",
        "• ISF Advantage: M1 conducts narrow Class-C current pulses right at",
        "  tank voltage extremum where Impulse Sensitivity Γ(φ) ≈ 0 -> low L(Δf)!",
    ], tone="sig", fs=10.2)

    # --- (b) Quadrature VCO + Coarse/Fine Cap Bank ---
    # Two VCO blocks coupled in a 90° loop: Core I (left x=600..750, y=145..235) & Core Q (right x=855..1005, y=145..235)
    d.rect(582, 142, 165, 92, fill="#eff6ff", stroke=COL_SIG, sw=2.0, rx=8)
    d.text(664, 178, "LC-VCO Core I", size=12, color=COL_SIG, anchor="middle", weight="bold")
    d.text(664, 198, "Outputs: I+, I- (0°/180°)", size=10.3, color=COL_DARK, anchor="middle")
    d.text(664, 218, "gm,core + Gm,couple", size=10.0, color=COL_MUTED, anchor="middle")

    d.rect(862, 142, 165, 92, fill="#ecfdf5", stroke=COL_BIAS, sw=2.0, rx=8)
    d.text(944, 178, "LC-VCO Core Q", size=12, color=COL_BIAS, anchor="middle", weight="bold")
    d.text(944, 198, "Outputs: Q+, Q- (90°/270°)", size=10.3, color=COL_DARK, anchor="middle")
    d.text(944, 218, "Exact 90° Phase Lock", size=10.0, color=COL_MUTED, anchor="middle")

    # Direct coupling (+Gm_c: I -> Q at y=166) and Inverting coupling (-Gm_c: Q -> I at y=210)!
    d.arrow(747, 166, 860, 166, color=COL_SIG, sw=2.1)
    d.text(804, 157, "+Gm,c (In-Phase)", size=10.2, color=COL_SIG, anchor="middle", weight="bold")

    d.arrow(862, 210, 749, 210, color=COL_WARN, sw=2.1)
    d.text(804, 228, "-Gm,c (Cross-Inverted!)", size=10.2, color=COL_WARN, anchor="middle", weight="bold")

    # Hybrid Tuning Box (Coarse Switched MIM Cap Bank + Fine MOS Varactor -> lowers KVCO!)
    d.rect(582, 266, 445, 118, fill="#fffbeb", stroke=COL_AMBER, sw=1.6, rx=8)
    d.text(804, 290, "Hybrid Nanometer Frequency Tuning (Lowers KVCO AM-PM Noise!)",
           size=11.4, color=COL_AMBER, anchor="middle", weight="bold")
    d.text(804, 314, "• Coarse Digital Band Select: Binary-weighted MIM/MOM Cap Bank + NMOS switches",
           size=10.4, color=COL_DARK, anchor="middle")
    d.text(804, 334, "  (Trade-off: Switch Ron lowers Q_cap = 1/(ω·C·Ron) vs Off-state Coff tuning range).",
           size=10.2, color=COL_MUTED, anchor="middle")
    d.text(804, 356, "• Fine Continuous Analog Lock: Accumulation-Mode MOS Varactor driven by Vctrl",
           size=10.4, color=COL_DARK, anchor="middle")
    d.text(804, 374, "  with small KVCO (MHz/V) so loop-filter thermal/ripple voltage causes minimal jitter!",
           size=10.2, color=COL_BIAS, anchor="middle", weight="bold")

    d.callout(566, 402, 476, 160, "Leeson / Hajimiri Phase-Noise Regimes (§15.7)", [
        "• 1/f³ Close-In Corner: Device 1/f flicker noise up-converted via",
        "  waveform asymmetry (DC component c0 of ISF) & AM-to-PM varactor!",
        "• 1/f² Thermal Skirt: Tank loss + active Gm thermal noise ÷ V_swing²·Q²!",
        "• Tail 2·ω0 Noise Trap: Tail current thermal noise around 2·f0 mixes",
        "  down into ±Δf phase noise! Fix: LC tail noise filter at 2·f0.",
    ], tone="purple", fs=10.2)
    return d


def diag_51_pfd_charge_pump_spur():
    d = SVGDoc(
        "pfd-charge-pump-spur.svg",
        "Tristate PFD Anti-Dead-Zone Reset, Charge-Pump Mismatch & Reference Spurs",
        "Bộ Dò Pha–Tần PFD Chống Vùng Chết, Sai lệch Bơm Điện tích (Charge Pump) & Tạp phổ Spur (Razavi Ch.16 §16.2)",
        "Ch.16", [16], width=1080, height=600
    )
    d.panel(18,  74, 560, 504, "(a) Tristate PFD (τ_rst Anti-Dead-Zone) + Charge Pump + 3rd-Order LF")
    d.panel(595, 74, 467, 504, "(b) Why I_UP ≠ I_DN Creates Reference Spurs at f0 ± f_ref")

    # Top DFF_A (y=155) for f_ref -> UP; Bottom DFF_B (y=285) for f_div -> DN; AND + Delay τ_rst in middle (y=220)!
    d.port(48, 162, "f_ref", side="left", color=COL_SIG, fs=10.8)
    d.rect(92, 132, 74, 52, fill="#eff6ff", stroke=COL_SIG, sw=1.8, rx=5)
    d.text(129, 154, "DFF_A", size=11, color=COL_SIG, anchor="middle", weight="bold")
    d.text(129, 172, "D = VDD", size=9.8, color=COL_MUTED, anchor="middle")
    d.line(48, 162, 92, 162, color=COL_SIG)

    d.port(48, 292, "f_div", side="left", color=COL_AMBER, fs=10.8)
    d.rect(92, 262, 74, 52, fill="#fffbeb", stroke=COL_AMBER, sw=1.8, rx=5)
    d.text(129, 284, "DFF_B", size=11, color=COL_AMBER, anchor="middle", weight="bold")
    d.text(129, 302, "D = VDD", size=9.8, color=COL_MUTED, anchor="middle")
    d.line(48, 292, 92, 292, color=COL_AMBER)

    # Reset AND + Delay τ_rst block in middle (x=196..292, y=208..244)
    d.rect(192, 208, 108, 36, fill="#fef2f2", stroke=COL_WARN, sw=1.7, rx=5)
    d.text(246, 230, "AND + τ_rst", size=10.5, color=COL_WARN, anchor="middle", weight="bold")
    # UP wire at y=158, DN wire at y=288
    d.line(166, 158, 345, 158, color=COL_SIG, sw=2.0)
    d.text(246, 150, "UP", size=11, color=COL_SIG, anchor="middle", weight="bold")
    d.line(166, 288, 345, 288, color=COL_AMBER, sw=2.0)
    d.text(246, 306, "DN", size=11, color=COL_AMBER, anchor="middle", weight="bold")
    # Tap UP & DN into AND, and RST back to DFF_A/B
    d.dot(215, 158, COL_SIG)
    d.line(215, 158, 215, 208, color=COL_SIG, sw=1.5)
    d.dot(275, 288, COL_AMBER)
    d.line(275, 288, 275, 244, color=COL_AMBER, sw=1.5)
    d.wire([(192, 226), (129, 226), (129, 184)], color=COL_WARN, sw=1.5, dash="3,3")
    d.line(129, 226, 129, 262, color=COL_WARN, sw=1.5, dash="3,3")

    # Charge Pump column at x=365: VDD -> I_UP -> S_UP -> Vctrl (y=232) -> S_DN -> I_DN -> GND
    d.vdd(365, 134, "VDD")
    iup = d.isrc_v(365, 162, direction="down", color=COL_BIAS, label="I_UP", label_side="right")
    d.line(365, 134, 365, iup["t"][1])
    # S_UP & S_DN switches meeting at Vctrl (365, 232)
    d.wire([iup["b"], (365, 206)], color=COL_SIG, sw=2.0)
    d.line(365, 206, 357, 220, color=COL_SIG, sw=2.1)
    d.wire([(365, 223), (365, 240)], color=COL_DARK, sw=2.1)
    d.line(365, 240, 357, 254, color=COL_AMBER, sw=2.1)
    idn = d.isrc_v(365, 302, direction="down", color=COL_WARN, label="I_DN", label_side="right")
    d.line(365, 257, 365, idn["t"][1], color=COL_AMBER)
    d.gnd(365, idn["b"][1])

    # Vctrl node at (365, 232) feeding 3rd-order passive Loop Filter: (RP + C1) || C2 -> VCO!
    d.dot(365, 232, COL_SIG)
    d.line(365, 232, 552, 232, color=COL_SIG, sw=2.2)
    d.port(552, 232, "Vctrl", side="top", color=COL_SIG)

    # Branch 1 (x=452): RP + C1 to GND
    d.dot(452, 232, COL_BIAS)
    rp_lf = d.res_v(452, 274, color=COL_BIAS, label="RP", label_side="left")
    d.line(452, 232, 452, rp_lf["t"][1])
    c1_lf = d.cap_v(452, 334, color=COL_BIAS, label="C1", label_side="left")
    d.line(452, rp_lf["b"][1], 452, c1_lf["t"][1])
    d.gnd(452, c1_lf["b"][1])

    # Branch 2 (x=518): Ripple cap C2 (~C1/10) to GND
    d.dot(518, 232, COL_PURPLE)
    c2_lf = d.cap_v(518, 302, color=COL_PURPLE, label="C2", sub="≈C1/10", label_side="right")
    d.line(518, 232, 518, c2_lf["t"][1])
    d.gnd(518, c2_lf["b"][1])

    d.callout(36, 386, 524, 174, "Dead-Zone Elimination vs 3rd-Order Loop Filter Synthesis", [
        "• Dead-Zone Fix: Without reset delay τ_rst (~150–300 ps), ultra-narrow",
        "  UP/DN pulses near Δφ = 0 fail to turn ON CP switches -> VCO wanders freely!",
        "• Stabilizing Zero & Ripple Pole:",
        "  ω_z = 1 / (RP · C1)   stabilizes Type-II double integrator (2 poles at s=0);",
        "  ω_p3 ≈ 1 / (RP · C2)  suppresses RP·I_CP voltage jumps (keep C2 ≤ C1/10)!",
    ], tone="sig", fs=10.2)

    # --- (b) Right panel: Locked Mismatch Ripple & Spurs ---
    # Vctrl ripple + RF spectrum with ±f_ref spurs!
    d.axes(645, 134, 375, 165, xlabel="Frequency f", ylabel="P(f) dBc", title="PLL Output Spectrum Under ΔI = I_UP - I_DN")
    # Carrier spike at f0 (x=832)
    d.arrow(832, 299, 832, 146, color=COL_SIG, sw=3.0)
    d.text(832, 138, "f0 = N · f_ref", size=10.8, color=COL_SIG, anchor="middle", weight="bold")
    # Phase noise skirt around f0
    d.path("M 665 288 Q 795 278 826 190 M 838 190 Q 869 278 1000 288", stroke=COL_MUTED, sw=1.7, dash="4,3")
    # Reference spurs at f0 - f_ref (x=725) and f0 + f_ref (x=940) in RED!
    d.arrow(725, 299, 725, 212, color=COL_WARN, sw=2.3)
    d.text(725, 203, "-f_ref Spur", size=10.2, color=COL_WARN, anchor="middle", weight="bold")
    d.arrow(940, 299, 940, 212, color=COL_WARN, sw=2.3)
    d.text(940, 203, "+f_ref Spur", size=10.2, color=COL_WARN, anchor="middle", weight="bold")

    # Brace showing dBc spur suppression
    d.line(844, 212, 932, 212, color=COL_AMBER, sw=1.4, dash="3,3")
    d.text(888, 226, "P_spur (dBc)", size=10, color=COL_AMBER, anchor="middle", weight="bold")

    d.callout(612, 344, 432, 216, "Quantitative Reference Spur Physics & Fixes (§16.2)", [
        "• In steady-state lock, if I_UP ≠ I_DN, PFD shifts static phase Δφ_ss",
        "  so net charge over T_ref is zero:  I_UP·t_UP = I_DN·t_DN.",
        "• During every reset pulse τ_rst, ΔI = I_UP - I_DN injects periodic",
        "  ripple ΔV_ctrl(f_ref) into KVCO, creating FM sidebands at f0 ± f_ref:",
        "  P_spur ≈ 20·log10[ (KVCO · ΔV_ripple) / (2 · ω_ref) ] !",
        "• Fixes: Replica unity-gain op-amp biasing V_ctrl = V_replica to match",
        "  I_UP = I_DN across V_ctrl range + dummy charge-cancellation switches!",
    ], tone="warn", fs=10.1)
    return d


def diag_52_sar_adc_cdac_architecture():
    d = SVGDoc(
        "sar-adc-cdac-architecture.svg",
        "Charge-Redistribution SAR ADC: Capacitive DAC, Binary Search & Noise Budget",
        "Kiến trúc SAR ADC Phân phối lại Điện tích: Mảng Tụ C-DAC, Thuật toán Nhị phân & Ngân sách Nhiễu (Ch.13/14)",
        "Ch.13/14", [13, 14], width=1080, height=600, legend=False
    )
    d.panel(18,  74, 585, 504, "(a) N-Bit Charge-Redistribution C-DAC + Dynamic Comparator + SAR")
    d.panel(620, 74, 442, 504, "(b) Binary Convergence & Monotonic / Vcm Energy Saving")

    # Top plate VX bus from x=85..435 at y=185 feeding Dynamic Comparator!
    d.line(85, 185, 435, 185, color=COL_SIG, sw=2.3)
    d.text(245, 173, "Top-Plate Summing Node VX (Bottom-Plate Sampled!)",
           size=10.6, color=COL_SIG, anchor="middle", weight="bold")

    # Top-plate reset / Vcm sampling switch (early φs,e!) at x=98
    d.dot(98, 185, COL_BIAS)
    d.line(98, 185, 98, 134, color=COL_BIAS, sw=1.9)
    d.port(98, 130, "Vcm (φs,e!)", side="top", color=COL_BIAS, fs=10.5)

    # 4 Binary-Weighted Capacitor Columns: 8C (MSB, x=158), 4C (x=232), 2C (x=306), 1C + 1C_term (x=380)
    cap_cols = [
        (162, "2^(N-1)C", "b_{N-1}"),
        (238, "2^(N-2)C", "b_{N-2}"),
        (314, "... 2C",   "b_1"),
        (388, "C + C",    "b_0 / Term"),
    ]
    for cx, clbl, blbl in cap_cols:
        d.dot(cx, 185, COL_SIG)
        cv = d.cap_v(cx, 232, color=COL_DARK, label="")
        d.line(cx, 185, cx, cv["t"][1], color=COL_SIG)
        d.text(cx, 236, clbl, size=9.6, color=COL_AMBER, anchor="middle", weight="bold")
        # 3-throw switch box below each capacitor (Vin / Vref+ / GND)
        d.rect(cx - 28, 272, 56, 42, fill="#f8fafc", stroke=COL_PURPLE, sw=1.5, rx=5)
        d.line(cx, cv["b"][1], cx, 272, color=COL_DARK)
        d.text(cx, 290, "Vin|Vref", size=9.2, color=COL_DARK, anchor="middle")
        d.text(cx, 306, blbl, size=9.4, color=COL_PURPLE, anchor="middle", weight="bold")
        # Control arrow up from SAR register
        d.arrow(cx, 358, cx, 316, color=COL_PURPLE, sw=1.6)

    # Dynamic Comparator at (478, 198)
    comp = d.opamp(478, 198, w=62, h=52, facing="right", plus_top=False, label="Comp", color=COL_SIG, fill="#eff6ff")
    d.line(435, 185, comp["in_top"][0], comp["in_top"][1], color=COL_SIG, sw=2.1)
    d.wire([comp["in_bot"], (432, comp["in_bot"][1]), (432, 238)], color=COL_BIAS)
    d.port(432, 242, "Vcm", side="bottom", color=COL_BIAS, fs=10.2)

    # SAR Digital Control Register Box at (130..545, y=358..416)
    d.rect(130, 358, 418, 56, fill="#ecfdf5", stroke=COL_BIAS, sw=1.9, rx=7)
    d.text(339, 382, "Successive Approximation Register (SAR Logic — N Cycles)",
           size=11.5, color=COL_BIAS, anchor="middle", weight="bold")
    d.text(339, 401, "Outputs Digital Word D_out[N-1:0]  &  Drives C-DAC Switches",
           size=10.2, color=COL_DARK, anchor="middle")
    # Connect Comparator output around right into SAR box!
    d.wire([comp["out"], (566, 198), (566, 386), (550, 386)], color=COL_SIG, sw=2.0, marker_end="arr-sig")

    d.callout(36, 434, 548, 126, "3-Source SAR ADC Precision & Noise Budget", [
        "1. Sampling kT/C + Comparator Thermal Noise:  Vn,tot² = kT/C_tot + Vn,comp² < Δ²/12",
        "   where LSB step Δ = V_FS / 2^N  (10-bit 1Vpp -> Δ ≈ 1 mV; 12-bit -> Δ ≈ 244 µV!).",
        "2. C-DAC Pelgrom Capacitor Mismatch (σ_ΔC/C = A_C / √(W·L)): Sets INL / DNL / SFDR!",
        "3. Reference Settling: Vref buffer must settle CDAC MSB current spike within T_bit!",
    ], tone="sig", fs=10.1)

    # --- (b) Right panel: Binary Search Convergence Plot + Switching Schemes ---
    ox, oy = d.axes(668, 132, 352, 184, xlabel="Bit Trial k (1 .. N)", ylabel="VX - Vcm", title="Successive Approximation Trajectory")
    # Dashed target zero line Vcm at y=224
    d.line(668, 224, 1020, 224, color=COL_BIAS, sw=1.8, dash="5,3")
    d.text(988, 216, "Target = 0", size=10, color=COL_BIAS, anchor="end", weight="bold")

    # Stepwise waveform converging to 0: starts at -Vin (y=292), jumps +Vref/2 (y=172), -Vref/4 (y=232), +Vref/8 (y=202), +Vref/16 (y=217), -Vref/32 (y=224)!
    pts = [
        (676, 292), (730, 292),
        (730, 172), (784, 172),
        (784, 240), (838, 240),
        (838, 206), (892, 206),
        (892, 228), (946, 228),
        (946, 221), (1002, 221),
    ]
    d.wire(pts, color=COL_SIG, sw=2.5)
    d.text(757, 162, "MSB (+Vref/2)", size=9.8, color=COL_SIG, anchor="middle", weight="bold")
    d.text(811, 256, "-Vref/4", size=9.8, color=COL_AMBER, anchor="middle", weight="bold")

    d.callout(638, 354, 406, 206, "Modern Low-Energy C-DAC Switching Schemes", [
        "• Conventional Trial-and-Error: Wastes huge energy discharging",
        "  MSB cap back down when trial bit = 0 (E_avg ≈ 1363·C·Vref² @ 10b).",
        "• Vcm-Based Merged Capacitor Switching (MCS): Resets bottom",
        "  plates to Vcm first -> cuts total C_tot by 2x & energy by ~87%!",
        "• Monotonic Set-and-Down (Liu): Samples directly on top plates",
        "  and only switches one side down -> 81% less energy + faster,",
        "  at the cost of Vcm shifting toward GND (watch comparator VOS!).",
    ], tone="amber", fs=10.1)
    return d


def diag_53_esd_padring_cross_section():
    d = SVGDoc(
        "esd-padring-cross-section.svg",
        "Analog I/O ESD Protection, Active Rail Clamp & Split-Ground Padring",
        "Mạch Bảo vệ Phóng tĩnh điện ESD, Kẹp Nguồn Chủ động & Tách Đất Analog/Digital + Cuộn cảm Dây hàn (Ch.19 §19.5)",
        "Ch.19", [18, 19], width=1080, height=600
    )
    d.panel(18,  74, 640, 504, "(a) Dual-Diode HBM/CDM ESD + RC Active Power Clamp + Bondwire L")
    d.panel(675, 74, 387, 504, "(b) Split Supply Star-Ground & Package L·di/dt Rules")

    # Top VDDA bus (x=195..620, y=132) and Bottom VSSA bus (x=195..500, y=425) + VSSD bus (x=555..635, y=425)
    d.line(195, 132, 620, 132, color=COL_BIAS, sw=2.6)
    d.text(405, 118, "VDDA (Clean Analog Supply Bus)", size=11.2, color=COL_BIAS, anchor="middle", weight="bold")

    d.line(195, 425, 495, 425, color=COL_DARK, sw=2.6)
    d.text(330, 444, "VSSA (Quiet Analog Ground)", size=11.0, color=COL_DARK, anchor="middle", weight="bold")

    # External Pin -> Bondwire L_bond (x=118, y=278) -> I/O Pad (175, 278)
    d.port(48, 278, "Pin", side="left", color=COL_SIG)
    lb = d.ind_h(102, 278, color=COL_WARN, label="L_bond (~2nH)", label_pos="top")
    d.line(48, 278, lb["l"][0], 278, color=COL_WARN, sw=2.0)

    # Bond Pad square at (154..186, 262..294)
    d.rect(154, 262, 32, 32, fill="#dbeafe", stroke=COL_SIG, sw=2.2, rx=4)
    d.line(lb["r"][0], 278, 154, 278, color=COL_SIG, sw=2.0)
    d.text(170, 253, "PAD", size=10.5, color=COL_SIG, anchor="middle", weight="bold")

    # Primary Dual ESD Diodes at x=235: DP pointing UP to VDDA (132), DN pointing UP from VSSA (425) to signal line (278)!
    d.line(186, 278, 316, 278, color=COL_SIG, sw=2.1)
    d.dot(235, 278, COL_WARN)

    # Helper inline upward diode symbol at (x=235, yc=205) and (x=235, yc=352)
    for yc_d, dlbl in [(205, "D_P (P+/N-well)"), (352, "D_N (N+/P-sub)")]:
        d.poly([(223, yc_d + 11), (247, yc_d + 11), (235, yc_d - 11)], fill="#fee2e2", stroke=COL_WARN, sw=1.9)
        d.line(222, yc_d - 11, 248, yc_d - 11, color=COL_WARN, sw=2.2)
        d.text(253, yc_d + 4, dlbl, size=10.2, color=COL_WARN, weight="bold")
    d.line(235, 278, 235, 216, color=COL_WARN, sw=2.0)
    d.line(235, 194, 235, 132, color=COL_WARN, sw=2.0)
    d.dot(235, 132, COL_BIAS)

    d.line(235, 425, 235, 363, color=COL_WARN, sw=2.0)
    d.line(235, 341, 235, 278, color=COL_WARN, sw=2.0)
    d.dot(235, 425, COL_DARK)

    # Secondary CDM Resistor R_sec (x=340, y=278) -> Core Thin-Oxide Gate M_in (x=435, y=278)!
    rsec = d.res_h(340, 278, color=COL_AMBER, label="R_sec (CDM)", sub="50–200 Ω", label_pos="top")
    m_core = d.nmos(445, 278, facing="right", color=COL_SIG, label="M_core", sub="Thin tox!")
    d.line(rsec["r"][0], 278, m_core["g"][0], 278, color=COL_SIG, sw=2.0)
    d.line(445, m_core["s"][1], 445, 425, color=COL_DARK)
    d.dot(445, 425, COL_DARK)
    d.text(445, 242, "Core Analog", size=10.2, color=COL_SIG, anchor="middle", weight="bold")

    # Active RC-Triggered BigFET Power-Rail Clamp between VDDA and VSSA at x=555!
    d.rect(505, 198, 118, 156, fill="#fffbeb", stroke=COL_AMBER, sw=1.8, rx=7)
    d.text(564, 224, "RC-Triggered", size=10.6, color=COL_AMBER, anchor="middle", weight="bold")
    d.text(564, 242, "BigFET Clamp", size=10.6, color=COL_AMBER, anchor="middle", weight="bold")
    d.text(564, 266, "τ_RC ~ 1 µs:", size=9.8, color=COL_DARK, anchor="middle")
    d.text(564, 282, "ON for ns ESD", size=9.8, color=COL_WARN, anchor="middle", weight="bold")
    d.text(564, 298, "OFF in DC op!", size=9.8, color=COL_BIAS, anchor="middle", weight="bold")
    d.line(564, 132, 564, 198, color=COL_WARN, sw=2.2)
    d.line(564, 354, 564, 425, color=COL_WARN, sw=2.0)
    d.wire([(495, 425), (564, 425)], color=COL_DARK, sw=2.4)
    d.dot(564, 132, COL_BIAS)
    d.dot(564, 425, COL_DARK)

    # Back-to-back Antiparallel ESD Diodes between VSSA (495, 425) and VSSD Digital Ground at bottom right!
    d.rect(470, 474, 168, 84, fill="#f5f3ff", stroke=COL_PURPLE, sw=1.5, rx=7)
    d.text(554, 496, "VSSA <-> VSSD Bridge", size=10.5, color=COL_PURPLE, anchor="middle", weight="bold")
    d.text(554, 515, "Back-to-Back ESD Diodes:", size=9.8, color=COL_DARK, anchor="middle")
    d.text(554, 532, "Blocks ±0.4V digital bounce,", size=9.6, color=COL_BIAS, anchor="middle")
    d.text(554, 548, "shunts 2 A ESD zap safely!", size=9.6, color=COL_WARN, anchor="middle", weight="bold")
    d.line(492, 425, 492, 474, color=COL_PURPLE, sw=1.8, dash="4,3")

    d.callout(36, 470, 418, 92, "HBM (+2 kV) Complete Current Return Loop", [
        "• Zap Pin (+) wrt VSSA (-): Current flows PAD -> D_P -> VDDA bus ->",
        "  Active BigFET Rail Clamp -> VSSA! (Never rely on D_P without",
        "  a low-impedance VDDA-to-VSSA Rail Clamp!)",
    ], tone="warn", fs=10.0)

    # --- (b) Right panel ---
    d.callout(693, 114, 352, 146, "1. Bondwire L·di/dt Ground Bounce (§19.5)", [
        "• Gold/Cu wirebond adds L_bond ≈ 1 nH/mm (2–5 nH/pin).",
        "• Digital I/O switching ΔI = 100 mA in Δt = 100 ps induces",
        "  ΔV_bounce = L · ΔI/Δt = 2 nH · 10⁹ A/s = 2.0 V !!",
        "• Never share analog ground wirebond with digital drivers!",
        "  Use multiple parallel ground pins (L_eff = L / N) + Kelvin sense.",
    ], tone="warn", fs=10.1)

    d.callout(693, 276, 352, 138, "2. Analog RF/High-Speed C_ESD Trade-Off", [
        "• Large ESD diodes add C_ESD ~ 0.3–1.5 pF + nonlinear C(V)",
        "  directly at the pin, degrading S11, TIA BW, and HD2/HD3!",
        "• Mitigation: T-coil inductive neutralization, smaller diodes",
        "  with faster rail clamp, & symmetric DP = DN C(V) cancellation.",
    ], tone="sig", fs=10.1)

    d.callout(693, 430, 352, 130, "3. Mandatory Double Guard-Ring Rule", [
        "• ESD diodes inject massive minority carriers into substrate",
        "  during stress -> prime Latch-Up trigger!",
        "• Surround every I/O ESD cell with dedicated P+ & N+ guard",
        "  rings spaced ≥ 15–20 µm from sensitive analog cores.",
    ], tone="bias", fs=10.1)
    return d


def diag_54_spectre_stb_probe_setup():
    d = SVGDoc(
        "spectre-stb-probe-setup.svg",
        "Cadence Spectre Loop Stability Verification: iprobe & diffstbprobe",
        "Thiết lập Đo Ổn định Vòng Hồi tiếp trong Spectre: iprobe Đơn cực & diffstbprobe Vi sai / CMFB (Layer 8 · Ch.08/10)",
        "EDA · Ch.08/10", [8, 9, 10], width=1080, height=600
    )
    d.panel(18,  74, 515, 504, "(a) Single-Ended Closed-Loop Testbench (analogLib/iprobe)")
    d.panel(550, 74, 512, 504, "(b) Fully-Differential OTA: DM vs CMFB Loop (diffstbprobe)")

    # --- (a) Single-Ended Op-Amp / LDO STB ---
    oa1 = d.opamp(275, 255, w=68, h=58, facing="right", plus_top=True, label="DUT", color=COL_SIG, fill="#eff6ff")
    # + input = VDC,CM bias
    d.port(115, oa1["in_top"][1], "VCM,DC", side="left", color=COL_BIAS)
    d.line(115, oa1["in_top"][1], oa1["in_top"][0], oa1["in_top"][1], color=COL_BIAS, sw=2.0)

    # Output + CL + RL
    d.line(oa1["out"][0], 255, 465, 255, color=COL_SIG, sw=2.2)
    d.port(465, 255, "Vout", side="right", color=COL_SIG)
    d.dot(405, 255, COL_AMBER)
    cl1 = d.cap_v(438, 315, color=COL_DARK, label="CL", label_side="right")
    d.dot(438, 255, COL_DARK)
    d.line(438, 255, 438, cl1["t"][1])
    d.gnd(438, cl1["b"][1])

    # Feedback network Z1 (to Vref) & Z2 (from Vout) -> iprobe right before '-' input!
    # Put feedback network β at y=162 from x=405 -> x=295 -> iprobe box (195..270, y=146..178) -> '-' input!
    rfb = d.res_h(352, 162, color=COL_AMBER, label="Z2 (RF / β)", label_pos="top")
    d.wire([(405, 255), (405, 162), rfb["r"]], color=COL_AMBER, sw=2.0)
    d.line(rfb["l"][0], 162, 278, 162, color=COL_AMBER, sw=2.0)

    # Spectre iprobe symbol box at (186..278, 144..180)
    d.rect(186, 144, 92, 36, fill="#fef2f2", stroke=COL_WARN, sw=2.1, rx=6)
    d.text(232, 166, "STB iprobe", size=11, color=COL_WARN, anchor="middle", weight="bold")
    d.arrow(268, 136, 198, 136, color=COL_WARN, sw=1.7)
    d.text(233, 128, "Into High-Z Gate", size=9.6, color=COL_WARN, anchor="middle", weight="bold")

    # Wire from iprobe left (186, 162) down to '-' input (241, 268) + Z1 to VCM
    d.wire([(186, 162), (156, 162), (156, oa1["in_bot"][1]), oa1["in_bot"]], color=COL_AMBER, sw=2.0)
    d.dot(156, oa1["in_bot"][1], COL_AMBER)
    rg1 = d.res_v(156, 326, color=COL_AMBER, label="Z1", label_side="left")
    d.line(156, oa1["in_bot"][1], 156, rg1["t"][1], color=COL_AMBER)
    d.gnd(156, rg1["b"][1])

    d.callout(36, 396, 478, 164, "Why Spectre `stb` Beats Classic Big-L / Big-C AC Breaks", [
        "• Never break DC bias with 1 GH / 1 GF ideal components (causes",
        "  floating DC convergence error or alters exact bidirectional Z loading!).",
        "• `stb` keeps loop 100% CLOSED during DC OpPoint, then evaluates exact",
        "  Middlebrook voltage+current return ratio T(jω) at `probe=IPRB0`!",
        "• Netlist:  `stb stb start=1 stop=100G dec=30 probe=IPRB0`",
        "  Check: Phase Margin PM ≥ 60° & Gain Margin GM ≥ 10 dB across PVT!",
    ], tone="sig", fs=10.1)

    # --- (b) Fully-Differential diffstbprobe ---
    # Fully-diff OTA block at (685, 240) + CMFB block at (835, 345) + diffstbprobe at (795, 152)!
    d.rect(628, 206, 108, 76, fill="#eff6ff", stroke=COL_SIG, sw=2.0, rx=7)
    d.text(682, 238, "Fully-Diff", size=11.5, color=COL_SIG, anchor="middle", weight="bold")
    d.text(682, 256, "OTA Core", size=11.0, color=COL_SIG, anchor="middle", weight="bold")

    # Out+ (y=224) and Out- (y=264) extending to x=985
    d.line(736, 224, 985, 224, color=COL_SIG, sw=2.1)
    d.line(736, 264, 985, 264, color=COL_SIG, sw=2.1)
    d.port(985, 224, "Out+", side="right", color=COL_SIG, fs=10.5)
    d.port(985, 264, "Out-", side="right", color=COL_SIG, fs=10.5)

    # Top: Differential Feedback via `diffstbprobe` box (742..874, 126..174)
    d.rect(738, 126, 140, 48, fill="#fef2f2", stroke=COL_WARN, sw=2.1, rx=6)
    d.text(808, 146, "diffstbprobe", size=11.2, color=COL_WARN, anchor="middle", weight="bold")
    d.text(808, 163, "mode = diff | comm", size=9.8, color=COL_DARK, anchor="middle", weight="bold")

    d.dot(928, 224, COL_AMBER)
    d.dot(948, 264, COL_AMBER)
    d.wire([(928, 224), (928, 138), (878, 138)], color=COL_AMBER, sw=1.8)
    d.wire([(948, 264), (948, 162), (878, 162)], color=COL_AMBER, sw=1.8)
    d.wire([(738, 138), (595, 138), (595, 224), (628, 224)], color=COL_AMBER, sw=1.8)
    d.wire([(738, 162), (578, 162), (578, 264), (628, 264)], color=COL_AMBER, sw=1.8)

    # Bottom: Dedicated CMFB Loop + CMFB iprobe at V_cmfb control wire!
    d.rect(778, 314, 124, 52, fill="#ecfdf5", stroke=COL_BIAS, sw=1.9, rx=6)
    d.text(840, 336, "CMFB Sense", size=11, color=COL_BIAS, anchor="middle", weight="bold")
    d.text(840, 353, "& Error Amp", size=10.2, color=COL_MUTED, anchor="middle")
    d.dot(885, 224, COL_BIAS)
    d.dot(865, 264, COL_BIAS)
    d.line(885, 224, 885, 314, color=COL_BIAS, sw=1.6)
    d.line(865, 264, 865, 314, color=COL_BIAS, sw=1.6)

    # CMFB return wire via IPRB_CMFB to OTA tail/load bias pin (682, 282)
    d.rect(654, 322, 92, 34, fill="#fffbeb", stroke=COL_AMBER, sw=1.9, rx=5)
    d.text(700, 343, "IPRB_CMFB", size=10.5, color=COL_AMBER, anchor="middle", weight="bold")
    d.line(778, 339, 746, 339, color=COL_BIAS, sw=1.9)
    d.wire([(654, 339), (636, 339), (636, 298), (682, 298), (682, 282)], color=COL_BIAS, sw=1.9, marker_end="arr-bias")

    d.callout(568, 396, 476, 164, "Dual-Loop Fully-Differential Stability Audit", [
        "1. Differential Mode (`diffstbprobe` with `mode=diff`):",
        "   Verifies main signal feedback loop T_DM(jω), GBW_DM, and PM_DM ≥ 60°.",
        "2. Common-Mode Feedback Loop (`IPRB_CMFB` or `mode=comm`):",
        "   CMFB shares OTA output pole CL AND adds CM detector pole!",
        "   A ringing or unstable CMFB rail clips Out± even if T_DM looks perfect!",
        "   Rule: Verify PM_CMFB ≥ 55° & GBW_CMFB ≈ (0.3 .. 1.0) · GBW_DM!",
    ], tone="amber", fs=10.1)
    return d


def diag_55_spectre_pss_pnoise_flow():
    d = SVGDoc(
        "spectre-pss-pnoise-flow.svg",
        "Spectre Periodic RF & Mixed-Signal Verification Flow (PSS -> PAC / PNoise / PSTB)",
        "Quy trình Mô phỏng Tuần hoàn Spectre RF / Mixed-Signal cho Mạch SC, Comparator, VCO & PLL (Layer 8)",
        "EDA · PSS/PNoise", [13, 15, 16], width=1080, height=600, legend=False
    )
    d.panel(18, 74, 1044, 232, "(a) Why Standard DC + AC/Noise Fails on Clocked / Autonomous Circuits & 4-Engine Flow")
    d.panel(18, 322, 1044, 256, "(b) Exact Use-Case Matrix: Switched-Capacitor vs Dynamic Comparator vs VCO / CP-PLL")

    # Stage 1 box: PSS (x=42..302, y=126..278)
    d.rect(42, 124, 256, 156, fill="#eff6ff", stroke=COL_SIG, sw=2.2, rx=8)
    d.text(170, 149, "1. Periodic Steady State (pss)", size=12, color=COL_SIG, anchor="middle", weight="bold")
    d.text(170, 171, "Computes exact time-varying", size=10.4, color=COL_DARK, anchor="middle")
    d.text(170, 188, "periodic trajectory x_0(t) = x_0(t+T0)!", size=10.4, color=COL_DARK, anchor="middle", weight="bold")
    d.text(170, 212, "• Shooting Engine: SC / Comp / Ring", size=10.0, color=COL_MUTED, anchor="middle")
    d.text(170, 229, "• Harmonic Balance: High-Q LC-VCO", size=10.0, color=COL_MUTED, anchor="middle")
    d.text(170, 248, "• Set `tstab` until steady limit cycle!", size=10.0, color=COL_WARN, anchor="middle", weight="bold")

    # Fan-out arrows from PSS right edge (298, 202) to 3 linearized periodic analyses!
    targets = [
        (365, 114, 326, 52, "#ecfdf5", COL_BIAS, "2A. PAC / PXF (Periodic AC / XF)",
         "Gain H(z), Aliasing Sidebands & Clocked PSRR"),
        (365, 178, 326, 52, "#fef2f2", COL_WARN, "2B. PNoise (Sampled & Phase Noise)",
         "SC kT/C Folding, Jitter & VCO 1/f³ + 1/f² L(Δf)"),
        (365, 242, 326, 52, "#fffbeb", COL_AMBER, "2C. PSTB (Periodic Loop Stability)",
         "Time-averaged loop gain T(jω) of SC-CMFB!"),
    ]
    for tx, ty, tw, th, tfill, tcol, thd, tsub in targets:
        d.wire([(298, 202), (332, 202), (332, ty + th / 2), (tx - 2, ty + th / 2)],
               color=tcol, sw=2.0, marker_end="arr-dark")
        d.rect(tx, ty, tw, th, fill=tfill, stroke=tcol, sw=1.9, rx=7)
        d.text(tx + 14, ty + 21, thd, size=11.2, color=tcol, weight="bold")
        d.text(tx + 14, ty + 40, tsub, size=10.0, color=COL_DARK)

    # Right verification box inside top panel (x=722..1040, y=118..286)
    d.callout(722, 116, 318, 174, "Critical Spectre Parameter Rules", [
        "• `beat` / `fund`: GCD of all autonomous",
        "  or driven clock frequencies!",
        "• `maxacfreq` / `maxsideband >= 15..40`:",
        "  Too few sidebands misses wideband thermal",
        "  noise folding across f_clk harmonics!",
        "• `errpreset=conservative` mandatory",
        "  for < -120 dBc/Hz VCO phase noise!",
    ], tone="purple", fs=10.0)

    # --- (b) 3-Column Practical Setup Matrix ---
    cards = [
        (38, "Switched-Capacitor (SC Integrator / Amp)", "sig", [
            "• Driven PSS: `fund = f_clk`, `harms = 0`",
            "  (Shooting engine handles sharp switches!).",
            "• PAC: Sweep 1 Hz .. f_clk/2, `maxsideband=20`",
            "  -> read sampled discrete-time gain |H(e^jω)|.",
            "• PNoise (`sampled` / `timedomain` at end of",
            "  φ2 hold window): Captures exact kT/C + OTA",
            "  folded white & 1/f noise!",
        ]),
        (380, "StrongARM Comparator Input Noise", "amber", [
            "• Driven PSS at `f_clk` with small DC overdrive",
            "  ΔVin near switching threshold (e.g. 0.5 mV).",
            "• PNoise (`sampled` jitter/voltage at regeneration",
            "  crossing) + PAC conversion gain A_conv:",
            "  σ_Vn,in = V_n,out(strobe) / A_conv !",
            "• Transient Noise (`trannoise`) cross-check",
            "  via CDF Gaussian fit P('1' | ΔVin)!",
        ]),
        (722, "Free-Running Ring / LC-VCO", "warn", [
            "• Autonomous PSS: Leave `fund` as initial",
            "  estimate, specify oscillator differential nodes,",
            "  `tstab` ≥ 20–100 cycles until amplitude settles!",
            "• PNoise (`noisetype=sources` or `pm`, sweep",
            "  `relharmnum=1`, Δf = 100 Hz .. 100 MHz):",
            "  Extracts L(Δf) [dBc/Hz], RMS jitter, AND",
            "  per-transistor flicker vs thermal contributors!",
        ]),
    ]
    for cx, ctitle, ctone, clines in cards:
        d.callout(cx, 358, 322, 202, ctitle, clines, tone=ctone, fs=9.9)
    return d


def diag_56_gmid_sizing_methodology():
    d = SVGDoc(
        "gmid-sizing-methodology.svg",
        "Universal gm/ID Lookup-Table Sizing Methodology (Murmann / pygmid Flow)",
        "Phương pháp Định cỡ Bảng tra Chuẩn hóa gm/ID Đa Tiến trình (180nm / 90nm / 65nm / 45nm — Layer 8 & Ch.11/17)",
        "EDA · gm/ID", [2, 11, 17], width=1080, height=600
    )
    d.panel(18,  74, 525, 504, "(a) PDK-Normalized Trade-Off Curves vs Inversion Efficiency gm/ID")
    d.panel(560, 74, 502, 504, "(b) 5-Step Equation-Free LUT Sizing Algorithm (Zero Trial-and-Error)")

    # Plot axes: X = gm/ID from 4 to 24 V^-1; Y = normalized fT (blue) & gm*ro (green)
    ox, oy = d.axes(72, 134, 420, 210, xlabel="", ylabel="fT , gm·ro")

    # Region vertical guide bands: Strong (x=85..185), Moderate Sweet-Spot (x=185..345, tinted!), Weak (x=345..485)
    d.rect(190, 134, 155, 210, fill="#ecfdf5", stroke="none", rx=0, opacity=0.6)
    d.line(190, 134, 190, 344, color=COL_SUBTLE, sw=1.2, dash="4,4")
    d.line(345, 134, 345, 344, color=COL_SUBTLE, sw=1.2, dash="4,4")
    d.text(132, 150, "Strong Inv", size=10.0, color=COL_AMBER, anchor="middle", weight="bold")
    d.text(268, 150, "Moderate Sweet Spot", size=10.2, color=COL_BIAS, anchor="middle", weight="bold")
    d.text(416, 150, "Weak Inv", size=10.0, color=COL_SIG, anchor="middle", weight="bold")

    # fT curve (Blue): High in strong inversion (y=168 at x=92), drops rapidly in weak inversion (y=324 at x=475)
    d.path("M 92 168 Q 225 186 335 250 T 475 326", stroke=COL_SIG, sw=2.7)
    d.text(142, 196, "Speed fT = gm/(2π·Cgg)", size=10.4, color=COL_SIG, weight="bold")

    # Intrinsic gain gm*ro curve for L = 4*Lmin (Green): Rises from y=284 at x=92 to plateau y=184 at x=375..475
    d.path("M 92 284 Q 215 210 355 188 L 475 184", stroke=COL_BIAS, sw=2.6)
    d.text(395, 176, "gm·ro (L = 4·Lmin)", size=10.4, color=COL_BIAS, anchor="middle", weight="bold")

    # Intrinsic gain gm*ro for L = Lmin (Red dashed — lower due to DIBL!)
    d.path("M 92 318 Q 225 274 365 258 L 475 256", stroke=COL_WARN, sw=2.0, dash="5,3")
    d.text(405, 274, "gm·ro (L = Lmin, DIBL!)", size=10.0, color=COL_WARN, anchor="middle", weight="bold")

    # X-axis tick labels + clean centered axis title below
    for xv, lbl in [(95, "5"), (190, "10"), (268, "14"), (345, "18"), (455, "24")]:
        d.line(xv, 341, xv, 347, color=COL_DARK, sw=1.5)
        d.text(xv, 361, lbl, size=10, color=COL_MUTED, anchor="middle")
    d.text(282, 381, "gm / ID  [V⁻¹]  (Strong 5  <-->  Weak 22)", size=10.8, color=COL_DARK, anchor="middle", weight="bold")

    d.callout(36, 396, 488, 164, "Role-Specific gm/ID Selection Law (Pelgrom + Headroom)", [
        "• Input Diff-Pair (M1–M2): Choose gm/ID = 14 .. 20 V⁻¹ (Moderate/Weak)",
        "  -> Maximizes gm per µA, crushes input thermal noise & VOS mismatch!",
        "• Current Mirrors & Active Loads: Choose gm/ID = 5 .. 8 V⁻¹ (Strong Inv)",
        "  + Long L -> Minimizes current mismatch σ(ΔI/I) & load noise gm_load!",
        "• RF / High-Speed Cascode Shields: Choose gm/ID = 8 .. 12 V⁻¹ -> High fT!",
    ], tone="sig", fs=10.1)

    # --- (b) 5-Step Flow ---
    steps = [
        ("Step 1 · Compute Required gm from Specs", "sig",
         "gm1 = 2π · GBW · CL,eff    (or from thermal noise target 4kTγ/gm1)"),
        ("Step 2 · Choose Inversion Operating Point (gm/ID)", "bias",
         "Pick gm/ID ∈ [5, 22] V⁻¹ -> sets VDS,min ≈ 2 / (gm/ID) automatically!"),
        ("Step 3 · Lock Exact Drain Bias Current ID", "amber",
         "ID = gm1 / (gm / ID)       (Check power budget & slew rate SR = ISS/CL)"),
        ("Step 4 · Select Channel Length L from gm·ro & fT LUT", "purple",
         "Query BSIM4 LUT(L, gm/ID, VDS) so gm·ro ≥ A_target & fT ≥ 10·GBW"),
        ("Step 5 · Compute Width W from Current Density JD = ID/W", "neutral",
         "W = ID / JD(L, gm/ID) -> Fold into even M fingers & run CDF callbacks!"),
    ]
    sy = 112
    for idx_s, (stitle, stone, sbody) in enumerate(steps):
        d.callout(580, sy, 462, 74, stitle, [sbody], tone=stone, fs=10.3)
        if idx_s < len(steps) - 1:
            d.arrow(811, sy + 75, 811, sy + 89, color=COL_DARK, sw=1.8)
        sy += 92
    return d


ALL_GENERATORS = [
    diag_01_analog_design_octagon,
    diag_02_mos_small_signal_caps,
    diag_03_short_channel_iv_gmid,
    diag_04_cs_loads_comparison,
    diag_05_cs_source_degeneration,
    diag_06_source_follower_and_cg,
    diag_07_cascode_shielding,
    diag_08_diff_pair_half_circuit,
    diag_09_gilbert_cell,
    diag_10_current_mirrors_evolution,
    diag_11_five_transistor_ota,
    diag_12_miller_effect_rhp_zero,
    diag_13_diffpair_mirror_pole_doublet,
    diag_14_mos_noise_input_referred,
    diag_15_feedback_four_topologies,
    diag_16_middlebrook_stb_loop_probe,
    diag_17_telescopic_cascode_opamp,
    diag_18_folded_cascode_ota,
    diag_19_two_stage_miller_opamp,
    diag_20_gain_boosted_cascode,
    diag_21_cmfb_sensing_networks,
    diag_22_pole_splitting_locus,
    diag_23_cascode_ahuja_compensation,
    diag_24_nyquist_polar_stability,
    diag_25_supply_independent_bias_startup,
    diag_26_bandgap_reference_core,
    diag_27_low_voltage_sub1v_bandgap,
    diag_28_cmos_ldo_regulator,
    diag_29_mos_switch_charge_injection,
    diag_30_bottom_plate_sampling_sc,
    diag_31_bootstrapped_switch,
    diag_32_ring_and_lc_oscillators,
    diag_33_charge_pump_type2_pll,
    diag_34_pelgrom_mismatch_duality,
    diag_35_autozero_cds_offset,
    diag_36_latchup_and_guard_rings,
    diag_37_common_centroid_multifinger,
    diag_38_upgrade_evolution_map,
    diag_39_regulated_cascode_ssf,
    diag_40_diff_pair_active_mirror,
    diag_41_wilson_current_mirror,
    diag_42_noise_stages_comparison,
    diag_43_tia_shunt_shunt_feedback,
    diag_44_rail_to_rail_input_stage,
    diag_45_nested_miller_3stage,
    diag_46_constant_gm_self_bias,
    diag_47_sc_parasitic_insensitive_integrator,
    diag_48_strongarm_dynamic_comparator,
    diag_49_chopper_stabilization_principle,
    diag_50_colpitts_and_quadrature_vco,
    diag_51_pfd_charge_pump_spur,
    diag_52_sar_adc_cdac_architecture,
    diag_53_esd_padring_cross_section,
    diag_54_spectre_stb_probe_setup,
    diag_55_spectre_pss_pnoise_flow,
    diag_56_gmid_sizing_methodology,
]


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    manifest_entries = []
    errors = []

    for idx, gen_fn in enumerate(ALL_GENERATORS, start=1):
        doc = gen_fn()
        svg_text = doc.render()
        out_path = os.path.join(OUT_DIR, doc.filename)
        with open(out_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(svg_text)

        try:
            geom_cnt, txt_cnt = validate_svg_file(out_path)
        except Exception as exc:
            errors.append(str(exc))
            geom_cnt, txt_cnt = 0, 0

        manifest_entries.append({
            "index": idx,
            "filename": doc.filename,
            "file": doc.filename,
            "path": f"kb/diagrams/{doc.filename}",
            "viewBox": f"0 0 {doc.width} {doc.height}",
            "title_vi": doc.title_vi,
            "title_en": doc.title_en,
            "chapter": doc.chapter,
            "chapters": doc.chapters,
            "width": doc.width,
            "height": doc.height,
            "geometry_elements": geom_cnt,
            "text_elements": txt_cnt,
        })

    manifest_obj = {
        "version": "2026.11.18.3",
        "generator": "tools/generate_diagrams.py",
        "total_diagrams": len(manifest_entries),
        "diagrams": manifest_entries,
    }
    manifest_path = os.path.join(OUT_DIR, "diagrams-manifest.json")
    with open(manifest_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest_obj, f, ensure_ascii=False, indent=2)
        f.write("\n")

    if errors:
        print(f"VALIDATION FAILED ({len(errors)} issues):", file=sys.stderr)
        for err in errors:
            print("  -", err, file=sys.stderr)
        sys.exit(1)

    print(f"OK: Generated and XML/bounds/collision-validated {len(manifest_entries)} SVGs + diagrams-manifest.json")


if __name__ == "__main__":
    main()
