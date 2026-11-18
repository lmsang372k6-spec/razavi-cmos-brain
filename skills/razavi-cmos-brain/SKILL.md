---
name: razavi-cmos-brain
description: Process-agnostic Analog CMOS IC Design Knowledge Graph, 68 6-block engineering cards, 38 vector SVG circuit schematics, 112 topology-upgrade edges, 13 structural checklists, and 2,200 bilingual Vietnamese-English terms distilled from all 19 chapters of Behzad Razavi's Design of Analog CMOS Integrated Circuits (2nd Ed.). Use when designing, sizing, debugging, auditing, upgrading, or explaining CMOS analog circuits (CS/SF/CG/Cascode, Current Mirrors, Diff-Pairs, OTAs/Op-Amps, CMFB, Miller Compensation, Bandgap, LDO, Switched-Capacitor, VCO/PLL, Mismatch, Layout) across 180nm, 90nm, 65nm, 45nm, or FinFET nodes.
---

# Razavi CMOS Knowledge Brain

Canonical GitHub Repository: `https://github.com/lmsang372k6-spec/razavi-cmos-brain`  
Interactive Web Map & Static API: `https://lmsang372k6-spec.github.io/razavi-cmos-brain`

## Progressive Lookup Protocol (Never Load All 68 Cards at Once)

1. **Locate the right circuit node, symptom fix, or upgrade path first** by reading `kb/router-index.json` (and `kb/graph/edges.jsonl` for directed evolution edges):
   - Match by topology/concept ID (`topo-folded-cascode-ota`, `topo-lvccml-wide-swing-mirror`, `tech-miller-rhp-zero-nulling-and-cascode-comp`, `topo-bandgap-reference-core`, `topo-cmos-ldo-regulator`, `topo-charge-pump-type2-pll`, ...).
   - Match by failing symptom in `symptom_map` (`rhp-feedforward-zero`, `cascode-mirror-wasted-vth-headroom`, `narrow-icmr`, `offset`, `startup`, `charge-injection`, ...).
   - Match by Razavi 2nd Ed. chapter (`1..19`) or standardized CLB bilingual term (`kb/glossary/terms-vi-en.json`, `T001–T2200`).
2. **Open only the 1–3 relevant 6-block cards** under `kb/nodes/<domain>/<id>.md` and their paired structural checklists under `kb/checklists/<checklist_id>.json`.
3. **Enforce Process-Agnostic Structural Invariants before PDK tuning:**
   - Verify KCL branch invariants (e.g. $I_{\text{fold}} > 0.5 I_{\text{tail}}$), degenerate $I=0$ startup escape, Middlebrook/Spectre `stb` loop-probe setup without breaking DC bias, $V_{DS,\min}$ & $g_m/I_D$ sizing laws, and Pelgrom mismatch sizing duality (high $g_m/I_D$ for diff-pair input vs low $g_m/I_D$ for current-mirror loads) before running simulator sweeps on the target PDK (`180nm`, `90nm`, `65nm`, `45nm`).
4. **Pedagogical & Engineering Explanations:**
   - Cite exact Razavi 2nd Ed. Chapter, Section, and Equation references from Block 6 of the card, use standardized Vietnamese–English terms from `kb/glossary/terms-vi-en.json`, and reference the clean vector schematic in `kb/diagrams/<file>.svg`.
