---
name: razavi-cmos-brain
description: Process-agnostic Full-Chip Analog CMOS, PMIC, Mixed-Signal AMS & Closed-Loop Cadence/Spectre EDA Knowledge Brain (release 2026.11.18.4): 162 6-block engineering cards across 10 domains (112 Razavi Ch.01-19 cards + 12 PMIC Buck/Boost/Buck-Boost/Capless-LDO/Protection cards + 12 AMS Filter/INA-CFIA/DAC/Delta-Sigma/Pipeline-ADC/System cards + 26 Closed-Loop Virtuoso IC617/SpectreRF/gm-ID/Pareto-Optimization skill cards), 72 vector SVG schematics, 482 directed upgrade/verification edges, 21 structural checklists, exact book coordinates (293 sections, 230 equations, 423 index terms), 52 vetted GitHub repositories, and 2,280 standardized Vietnamese-English terms (T001-T2280). Use when designing, sizing (gm/ID LUT), simulating (Spectre dc/ac/stb/pss/pac/pnoise/pstb, SKILL IPC bridge, PSF audit, Verilog-A), optimizing (Sensitivity Jacobian & Pareto sizing), debugging, or explaining CMOS analog, power-management, and mixed-signal ICs across 180nm, 90nm, 65nm, 45nm, or FinFET nodes.
---

# Razavi CMOS Knowledge Brain (`2026.11.18.4` · v3 10-Domain Full-Chip Edition)

Canonical GitHub Repository: `https://github.com/lmsang372k6-spec/razavi-cmos-brain`  
Interactive 22-Column 2D Coordinate Web Map & Static API: `https://lmsang372k6-spec.github.io/razavi-cmos-brain`

## Mandatory 7-Stage Optimal Design Cycle & Progressive Lookup Protocol (Never Load All 162 Cards at Once)

1. **Stage 1 — Progressive Router, Coordinate & Checklist Lookup:**
   - Query `kb/router-index.json` + `kb/graph/edges.jsonl` across all **10 domains** (`foundations` .. `nonideal-and-physical`, `power-management-ic`, `ams-filters-and-system`, `eda-and-github-skills`) or match failing simulation behavior via `symptom_map`.
   - Use `kb/coordinates/book-coordinates.json` for exact Razavi 2nd Ed. Section (`§1.1`..`§19.4`), Equation (`Eq. 2.10`, `Eq. 10.25`), and Page (`1..773`) resolution, and `kb/github-skills/catalog.json` for 52 audited Analog/PMIC/AMS/EDA GitHub repositories.
   - Open only the **1–3 relevant 6-block cards** (`kb/nodes/<domain>/<id>.md`) plus their linked checklists (`kb/checklists/*.json`, 21 checklists total).
2. **Stage 2 — Top-Down Hierarchical Spec & Interface Budgeting:**
   - Enforce RSS noise/offset allocation, common-mode $V_{CM}$ compatibility, $|Z_{\text{out},k}| \ll |Z_{\text{in},k+1}|$ impedance separation, central `I_PTAT`/`I_ZTC` LVCCML current-star distribution (`C_byp` to local supply rail, never VSS on PMOS mirrors!), and deterministic `POR -> UVLO -> BGR -> Bias -> LDO -> Clock/PLL -> Data Path` sequencing.
3. **Stage 3 — Equation-Free PDK `gm/ID` LUT Sizing (`gpdk_techsweep.py` + `gmid_lut.py`):**
   - Size devices in `< 5 ms` by inversion role (`gm/ID = 15..20 V^-1` for low-noise/offset input pairs, `7..10 V^-1` + longer `L` for mirrors/loads, `W_opt` balancing $R_{\text{on}}$ vs $Q_g f_{sw}$ for PMIC power FETs), folding wide devices into even `nf >= 2` fingers.
4. **Stage 4 — Live Virtuoso OA Schematic & Mixed-Mode Behavioral Shell (`ic617_live_bridge.il` + `ic617_client.py`):**
   - Inspect/place/wire schematics via live CIW IPC without `.cdslck` lock contention or `%L` string double-quoting; verify switching DC-DC loops rapidly in `.dc/.ac/.stb` using hidden-state-free `pwm_switch_avg_ccm_dcm.va` before full transistor signoff.
5. **Stage 5 — Automated Spectre Execution & PSF OP/Loop Audit (`cadence_exec.py` + `psf_audit.py`):**
   - Audit BSIM4 `dcOpInfo.info` (`region == 2`, $|V_{DS}| - |V_{DS,\text{sat}}| \ge 50\text{ mV}$), continuous `stb`/`diffstbprobe` DM & CMFB margins, and periodic `pss` + `pstb`/`pac`/`pnoise` for switched-capacitor, VCO/PLL, and PWM Buck/Boost/Buck-Boost converters (respecting $f_c \le f_{z,\text{RHP},\min}/4$ and slope compensation $m_a \ge 0.5 m_2$).
6. **Stage 6 — Physics-Pruned Sensitivity Jacobian & Constrained Pareto Optimization (`sizing_opt.py`):**
   - Compute $\partial \text{Metric}_i / \partial \ln x_j$ to identify controlling devices (`W`, `L`, `I_bias`, `C_c`, `R_z`) and optimize power/area/FoM in log-transformed space while respecting hard saturation & phase-margin barriers.
7. **Stage 7 — Worst-Case PVT, Pelgrom Monte Carlo & Post-Layout PEX Signoff:**
   - Sign off across `{TT, FF, SS, FS, SF}` × `{VDD_min, VDD_max}` × `{T_min, T_max}`, $\pm 3\sigma$ mismatch yield (including segmented DAC INL & DWA), Thermal SOA foldback OCP, and post-layout RC extraction (`CACE` contract), citing standardized CLB terms (`T001–T2280`) and vector diagrams (`kb/diagrams/*.svg`, 72 diagrams).
