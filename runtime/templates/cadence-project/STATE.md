# Project state: {{PROJECT_NAME}}

- Project root: `{{PROJECT_ROOT}}`
- Design-cycle stage: `1_spec_and_kb` (`1_spec_and_kb` -> `2_hierarchical_budget` -> `3_gmid_lut_sizing` -> `4_schematic_and_veriloga` -> `5_op_and_stb_audit` -> `6_sensitivity_pareto_opt` -> `7_pvt_mc_pex_signoff`).
- DUT/testbench: not selected; inspect `project.json` and `cds.lib`.
- Architecture & block DAG: `architecture.blocks[]` and `architecture.interfaces[]` empty (`active_view` swaps `veriloga` -> `schematic` bottom-up).
- Approved spec: none recorded in this template (`spec.json` status is `draft`).
- gm/ID LUT provenance: not selected (store compiled `.lut.json.gz` under `~/.cache/skill-analog/gmid-luts/`, never inside `SKILL-ANALOG`).
- OP / STB & optimization evidence: none; run `psf_audit.py` and `sizing_opt.py` against `sim/runs/<run-id>/` when ready.
- Best verified result: none; cite run ID, corner coverage, and raw PSF artifacts when available.
- Open issue: fill project metadata, select topology/checklists, and confirm requirements with the user.
- Next step: inspect actual PDK/library/cell/view and consult `kb_lookup.py` before creating or modifying a design.

Keep this file concise. Distinguish `estimated` (`gm/ID` LUT / hand math) from `simulated` (`Spectre` PSF evidence across nominal/PVT/MC/PEX) and update only meaningful changes; never store secrets or raw chat.
