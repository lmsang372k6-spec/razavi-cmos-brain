---
name: razavi-cmos-brain
description: Process-agnostic Analog CMOS IC Design & Practical Cadence/Spectre EDA Knowledge Graph (release 2026.11.18.3): 134 6-block engineering cards (112 Razavi cards across all 19 chapters + 22 vetted GitHub/IC617/Spectre practical skill cards), 56 vector SVG schematics & testbench diagrams, 319 directed upgrade/verification edges, 16 structural checklists, exact section/page/equation/index book coordinates (293 sections, 230 equations, 423 index terms), 31 vetted open-source Analog/EDA repositories, and 2,200 standardized Vietnamese-English terms. Use when designing, sizing (gm/ID), simulating (Spectre dc/ac/stb/pss/pac/pnoise/pstb, SKILL, OCEAN), debugging, layout-checking, or explaining CMOS analog & mixed-signal circuits across 180nm, 90nm, 65nm, 45nm, or FinFET nodes.
---

# Razavi CMOS Knowledge Brain (`2026.11.18.3`)

Canonical GitHub Repository: `https://github.com/lmsang372k6-spec/razavi-cmos-brain`  
Interactive 2D Coordinate Web Map & Static API: `https://lmsang372k6-spec.github.io/razavi-cmos-brain`

## Progressive Lookup Protocol (Never Load All 134 Cards at Once)

1. **Locate exact theory nodes, book coordinates, or practical EDA playbooks first:**
   - **Router & 2D Graph (`kb/router-index.json` + `kb/graph/edges.jsonl`):** Match by topology/concept/technique/skill ID (`topo-folded-cascode-ota`, `topo-regulated-cascode-super-source-follower`, `topo-sar-adc-charge-redistribution-architecture`, `skill-gm-id-lookup-table-sizing`, `skill-spectre-stb-diffstb-middlebrook`, `skill-spectre-pss-pac-pnoise-pstb`, ...) or by failing symptom in `symptom_map`.
   - **Exact Book Coordinate Index (`kb/coordinates/book-coordinates.json`):** Jump directly from any Razavi 2nd Ed. Section (`§1.1`..`§19.4`), Equation (`Eq. 2.10`, `Eq. 10.25`), Book/PDF Page (`1..773`), or `20_Index` subject term to the canonical card IDs.
   - **Vetted GitHub EDA Catalog (`kb/github-skills/catalog.json`):** Look up 31 audited open-source Analog/EDA repositories (`bmurmann/Book-on-gm-ID-design`, `dreoilin/pygmid`, `Arcadia-1/*`, `KenKundert/*`, `efabless/cace`, ...) with pinned commit SHAs, licenses, and Cadence IC617 + Spectre 15.1 compatibility notes.
2. **Open only the 1–3 relevant 6-block cards** under `kb/nodes/<domain>/<id>.md` ( pairing a Razavi theory card with its Layer-8 `skill-*` Spectre/SKILL testbench card) and their structural checklists under `kb/checklists/<checklist_id>.json`.
3. **Enforce Process-Agnostic Structural Invariants before PDK tuning:**
   - Verify KCL branch invariants ($I_{\text{fold}} > 0.5 I_{\text{tail}}$), degenerate $I=0$ startup escape, Middlebrook/Spectre `stb` (`iprobe` / `diffstbprobe`) DM & CMFB loop stability without breaking DC bias, periodic `pss`/`pac`/`pnoise`/`pstb` setup for clocked/autonomous circuits, $V_{DS,\min}$ & $g_m/I_D$ LUT sizing laws, Pelgrom mismatch sizing duality, bottom-plate $\phi_{1e}$ sampling, and ESD/Guard-Ring/Common-Centroid rules across `{TT, FF, SS, FS, SF}` PVT corners.
4. **Pedagogical & Engineering Explanations:**
   - Cite exact Razavi 2nd Ed. Chapter, Section, Book Page, and Equation coordinates, use standardized CLB bilingual Vietnamese–English terms (`kb/glossary/terms-vi-en.json`, `T001–T2200`), and reference the vector schematic in `kb/diagrams/<file>.svg`.
