---
name: razavi-cmos-brain
description: Process-agnostic Full-Chip Analog CMOS, PMIC, Mixed-Signal AMS & Closed-Loop Cadence/Spectre EDA Knowledge Brain (release 2026.11.18.6 · v4.0 SSOT + OTA): 162 6-block engineering cards across 10 domains (112 Razavi Ch.01-19 cards + 12 PMIC Buck/Boost/Buck-Boost/Capless-LDO/Protection cards + 12 AMS Filter/INA-CFIA/DAC/Delta-Sigma/Pipeline-ADC/System cards + 26 Closed-Loop Virtuoso IC617/SpectreRF/gm-ID/Pareto-Optimization skill cards), 72 vector SVG schematics, 482 directed upgrade/verification edges, 21 structural checklists, exact book coordinates (293 sections, 1,475 equations, 423 index terms), 52 vetted GitHub repositories, and 2,280 standardized Vietnamese-English terms (T001-T2280). Use when authoring/updating the KB (`manage_kb.py`) or looking up CMOS analog, PMIC, and mixed-signal IC theory, equations, topologies, and verification checklists.
---

# Razavi CMOS Knowledge Brain (`2026.11.18.6` · v4.0 Unified SSOT & 60s-TTL OTA Edition)

Canonical GitHub SSOT: `https://github.com/lmsang372k6-spec/razavi-cmos-brain`  
Unified Operational Skill (KB + `gm/ID` LUT + Fail-Closed PSF/Cadence Engine): [`skills/analog-design/SKILL.md`](../analog-design/SKILL.md)

## Progressive Lookup & Instant OTA Publishing Protocol

1. **Fast Local Lookup (`< 20 ms`, Zero Full-Corpus Dump):**
   - Use `python -B runtime/tools/kb_lookup.py <recipe|coord|search|domain|skills|diagnose|upgrades|checklist|stage|term> "<query>"` (`--offline` locks out all network calls).
   - Fetch only the **1–3 relevant 6-block cards** via `python -B runtime/tools/kb_fetch.py <node_id>` or read `kb/nodes/<domain>/<id>.md` directly alongside `kb/coordinates/book-coordinates.json` (`1,475` Razavi equations across `293` sections) and `kb/checklists/*.json` (`21` checklists).
2. **Instant Authoring & 1-Command Multi-Agent OTA Publish:**
   - Add or edit cards in `kb/nodes/<domain>/<id>.md`, checklists in `kb/checklists/`, or diagrams in `kb/diagrams/`.
   - Validate and rebuild all manifests & offline bundles atomically (`.build.lock` protected):
     `python -B tools/manage_kb.py rebuild`
   - Publish to GitHub `main` so Windows agents (`0 ms` via NTFS Junctions) and RHEL 6.5 Cadence VM (`60s` TTL atomic OTA sync) receive the verified release automatically:
     `python -B tools/manage_kb.py publish -m "<commit message>"`
