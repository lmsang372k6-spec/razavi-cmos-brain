# Razavi CMOS Knowledge Brain & SKILL-ANALOG Runtime (`2026.11.18.6` · v4.0 Unified SSOT + 60s-TTL OTA)

- **Kho lưu trữ GitHub SSOT chính thức:** https://github.com/lmsang372k6-spec/razavi-cmos-brain
- **Bản đồ Tọa độ Tri thức Tương tác & Static API (GitHub Pages):** https://lmsang372k6-spec.github.io/razavi-cmos-brain/
- **Endpoint Raw tức thì cho Codex / Antigravity / RHEL 6.5 OTA:** https://raw.githubusercontent.com/lmsang372k6-spec/razavi-cmos-brain/main

**Nguồn Chân lý Duy nhất (Unified Single-Source-of-Truth v4.0)** hợp nhất trọn vẹn **Bộ não Tri thức Toàn Chip CMOS, PMIC & AMS** (`162` thẻ chuyên sâu 6 khối xuyên suốt **10 tầng kiến trúc**: `112` thẻ lý thuyết & cấu trúc mạch bao phủ trọn vẹn **19 chương** *Design of Analog CMOS Integrated Circuits, 2nd Ed.* của Behzad Razavi + `12` thẻ Quản lý Nguồn **PMIC** + `12` thẻ Bộ lọc Liên tục / Chuyển đổi Dữ liệu / Kiến trúc Hệ thống **AMS** + `26` Playbook thực chiến **Cadence Virtuoso IC617 / Spectre 15.1 / Tối ưu Pareto**), **72 sơ đồ nguyên lý vector SVG offline**, **482 cạnh đồ thị có hướng**, **21 bảng kiểm bất biến đa tiến trình**, **chỉ mục tọa độ sách đầy đủ (`293` mục, `1.475` phương trình Razavi, `423` mục `20_Index`)**, **52 kho GitHub đã kiểm định**, **2.280 thuật ngữ chuẩn CLB (`T001–T2280`)**, cùng **trọn bộ Runtime Engine `SKILL-ANALOG` (`runtime/`)** tương thích kép Python 2.6.6 (RHEL 6.5) & Python 3.x!

Kiến trúc đa tác tử đồng bộ tức thì không cần remount `.iso`:
- **Windows (`Codex Desktop` + `Antigravity Desktop`):** Kết nối trực tiếp `0 ms` qua NTFS Directory Junctions (`setup_windows_agents.py --install`), tra cứu NVMe `< 20 ms`, biên soạn & xuất bản 1 lệnh (`manage_kb.py publish`).
- **Linux RHEL 6.5 VM (`Codex Linux` + `Cadence IC617` + `Spectre 15.1`):** Tự động đồng bộ nền **60s TTL** qua GitHub Commit SHA (`ota_sync.py`, hoán đổi thư mục nguyên tử kiểm định SHA-256, bảo toàn `sources/`), tự khóa mạng tuyệt đối khi đặt `--offline` hoặc `SKILL_ANALOG_OFFLINE=1`, và khởi tạo/nâng cấp toàn bộ máy ảo + biên dịch lại bảng tra `GPDK090`/`GPDK045` chỉ bằng 1 dòng lệnh `curl | python -B -` (`runtime/bootstrap_rhel6_ota.py`).

---

## 1. Kiến trúc 10 Tầng Tri thức, PMIC, AMS & Chu trình Tối ưu Khép kín EDA

| Tầng | Miền tri thức (`kb/nodes/<domain>/`) | Chương / Phạm vi | Trọng tâm kỹ thuật & Bất biến thiết kế |
|---|---|---|---|
| **1** | `foundations` | Ch.01, 02, 11, 17 | Bát giác Thiết kế Tương tự (8 trục đánh đổi), dẫn yếu dưới ngưỡng (Subthreshold), vật lý MOSFET & tụ ký sinh theo vùng hoạt động, hiệu ứng kênh ngắn, định cỡ nanomet theo $V_{DS,\min}$ & $g_m/I_D$, 5 góc PVT. |
| **2** | `stages-and-mirrors` | Ch.03, 04, 05 | Tầng CS (tải R, diode, triode, nguồn dòng, suy biến nguồn), Source Follower & Super Source Follower, Common-Gate, Cascode & Regulated Cascode, lựa chọn cấu hình transistor (§3.5–3.7), cặp vi sai tải gương dòng chủ động (5T-OTA), Gilbert cell, Wilson & **LVCCML dải rộng ($2V_{DS,\min}$)**. |
| **3** | `dynamics-noise-feedback` | Ch.06, 07, 08 | Định lý Miller & RHP zero, ZVTC & EET, cực tần số cao Cascode/CG & suy giảm CMRR cặp vi sai, đối chiếu nhiễu đơn tầng / cặp vi sai / bẫy nhân nhiễu gương dòng & định luật công suất–SNR, 4 cấu trúc hồi tiếp hai cửa, khuếch đại điện trở chuyển tiếp **TIA**, định lý Bode/Blackman/Middlebrook. |
| **4** | `opamps-and-compensation` | Ch.09, 10 | Đối chiếu Telescopic, Folded-Cascode ($I_{\text{fold}} > I_{\text{tail}}/2$), Two-Stage Miller, Gain-Boosted Cascode & đầu vào **Rail-to-Rail Constant-$G_m$**; quy trình định cỡ từng bước, 4 họ CMFB, phân tích $PSRR^+/PSRR^-$, ngân sách Slewing + Linear Settling, ánh xạ dự trữ pha $PM \leftrightarrow$ vọt lố, tách cực Miller + $R_z$, bù Ahuja, **Nested Miller 3 tầng** & Nyquist. |
| **5** | `references-and-biasing` | Ch.12 (+ Ch.08/10) | Tự phân cực **Constant-$G_m$** & mạch khởi động thoát điểm chết $I=0$, lõi Bandgap $1{,}25\text{ V}$, bù cong bậc cao $T\ln T$ & lọc nhiễu Bandgap, Bandgap hạ áp dưới $1\text{ V}$ (Banba) & tổng hợp bộ ổn áp **CMOS LDO**. |
| **6** | `sampled-and-clocked` | Ch.13, 15, 16 | Công tắc MOS & Bootstrap, **lấy mẫu tấm đáy ($\phi_{1e}$)**, khuếch đại nhân áp SC & bộ tích phân SC miễn nhiễm ký sinh, so sánh chốt động **StrongARM / Miyahara**, kiến trúc **SAR ADC C-DAC**, dao động vòng / LC ghép chéo / **Colpitts / Quadrature VCO**, nhiễu pha Leeson & ISF, PFD chống vùng chết / tạp phổ Charge Pump, tổng hợp bộ lọc vòng bậc 3 **CP-PLL**, bộ tổng hợp tần số Integer/Fractional-$N$ & DLL. |
| **7** | `nonideal-and-physical` | Ch.11, 14, 17, 18, 19 | Nghiên cứu thiết kế Op-Amp nanomet, méo hài chẵn HD2 do mất cân xứng, **định luật Pelgrom**, khử lệch không động Auto-Zeroing / CDS đối chiếu **Chopper Stabilization**, mô hình BSIM4 & FinFET, quy trình chế tạo CMOS & điện trở/tụ tích hợp, Latch-up & Guard Ring, dây dẫn RC / Electromigration / IR Drop, nhiễu đế bán dẫn, **bảo vệ ESD Padring & ký sinh dây hàn $L\,di/dt$**. |
| **8** | `power-management-ic` | PMIC Công nghiệp (`12` thẻ) | Cân bằng Volt–Giây CCM/DCM & không gian trạng thái trung bình, giới hạn băng thông **RHP Zero** của Boost/Buck-Boost, **Synchronous Buck**, **4-Switch Non-Inverting Buck-Boost**, bơm điện tích công suất **SC Charge-Pump ($R_{SSL}/R_{FSL}$)**, tầng lái **High-Side Bootstrap + Adaptive Dead-Time**, tổng hợp bộ bù **VMC Type-III (K-factor)**, **Peak CMC + Bù dốc $m_a \ge 0{,}5 m_2$ & COT**, cảm biến dòng **SenseFET / $L/\text{DCR}$ / ZCD**, **Capless LDO (FVF + Ahuja + DFC + Dynamic SRE)**, chuỗi bảo vệ **POR / UVLO / Soft-Start / Foldback OCP / TSD**, và kiểm chứng Spectre `pss`+`pstb` kèm mô hình `pwm_switch_avg_ccm_dcm.va`. |
| **9** | `ams-filters-and-system` | Bộ lọc, DAC/ADC, AFE & Chip (`12` thẻ) | **Schmitt Trigger 6T** & so sánh trễ hồi tiếp dòng, dao động tích thoát **RC Sawtooth (`I_ZTC` khử trễ $t_d$)** & tinh thể Pierce, **3-Op-Amp INA** đối chiếu **Chopper CFIA (DC Servo $\pm 300\text{ mV}$ + RRL)**, bộ lọc liên tục **Active-RC Sallen-Key / Tow-Thomas Biquad**, **$G_m\text{-}C$ Biquad kèm vòng tự chỉnh tần số Master–Slave PVT**, T-Switch Mux & đệm lái **Track-and-Hold ADC**, **Kelvin / R-2R / Segmented Current-Steering DAC**, bộ điều chế **$\Delta\Sigma$ SC/CT (CIFF/CIFB, ELD, DWA)**, **Flash & Pipelined 1.5-bit/stage MDAC (RSD)**, giao tiếp tốc độ cao **LVDS/CML/CTLE/CDR**, phân bổ ngân sách **RSS cấp Chip** & trạm phân phối dòng trung tâm **`I_PTAT`/`I_ZTC` LVCCML**. |
| **10** | `eda-and-github-skills` | Chu trình Khép kín Cadence–Codex (`26` thẻ) | **26 Playbook thực chiến** chưng cất từ **52 kho mã nguồn mở đã kiểm định**: cầu nối IPC sống **`ic617_live_bridge.il` + `ic617_client.py`** (không tranh chấp khóa `.cdslck`, xuất/vẽ JSON schematic), bộ đọc/kiểm toán **`psf_ascii_reader.py` + `psf_audit.py`** (BSIM4 `STRUCT` OP, `TRACE GROUP` waveform & đánh giá `spec.json`), quét công nghệ **`gpdk_techsweep.py` + `gmid_lut.py`** (`< 5 ms`), bộ tối ưu **`sizing_opt.py`** (Sensitivity Jacobian + Log Trust-Region Pareto), cùng toàn bộ testbench Spectre `stb`/`diffstbprobe`/`pss`/`pac`/`pnoise`/`pstb`, Monte Carlo, Common-Centroid Layout, PEX & `CACE`. |

---

## 2. Chu trình Thiết kế & Tối ưu Khép kín 7 Bước (`7-Stage Optimal Design Cycle`)

1. **Bước 1 — Tra cứu KB & Bảng kiểm Bất biến (`kb_lookup.py` + `21` Checklists):** Chọn cấu trúc tối ưu theo chỉ tiêu và nạp danh sách bất biến KCL / vùng hoạt động / cực tính hồi tiếp trước khi vẽ mạch.
2. **Bước 2 — Phân bổ Ngân sách Cấp Chip & Hợp đồng Giao tiếp (`spec.json` + `project.json`):** Phân bổ nhiễu RSS, độ lệch Pelgrom, $V_{CM}$, cực tính dòng phân cực và điều kiện tách trở kháng $|Z_{\text{out},k}| \ll |Z_{\text{in},k+1}|$.
3. **Bước 3 — Định cỡ Vật lý Bảng tra `gm/ID` (`gpdk_techsweep.py` + `gmid_lut.py`):** Nội suy đa chiều `< 5 ms` từ `(gm, gm/ID, L, VDS)` sang `ID, W, nf (chẵn), gm*ro, fT, Vdsat` chuẩn xác cho GPDK090 / GPDK045.
4. **Bước 4 — Dựng Schematic OA & Khung Hỗn hợp Verilog-A (`ic617_live_bridge.il` + `ic617_client.py`):** Đặt linh kiện theo lưới `0.0625`, gọi đủ callback CDF (không lỗi nháy kép `%L`), kiểm chứng nhanh vòng kín `< 0.3 s` với `pwm_switch_avg_ccm_dcm.va` và `saCheckAndSaveJson`.
5. **Bước 5 — Mô phỏng Spectre & Kiểm toán Tự động PSF (`cadence_exec.py` + `psf_audit.py`):** Quét toàn bộ MOSFET (`region == 2`, $|V_{DS}| - |V_{DS,\text{sat}}| \ge 50\text{ mV}$) và đo tự động DC/AC/STB/PSS-PSTB/Tran đối chiếu `spec.json`.
6. **Bước 6 — Ma trận Độ nhạy Jacobian & Tối ưu Vùng Tin cậy Pareto (`sizing_opt.py`):** Tính đạo hàm độ nhạy cục bộ $\partial \text{Metric}_i / \partial \ln x_j$ và hội tụ cực tiểu công suất/diện tích trong không gian logarit có ràng buộc biên an toàn.
7. **Bước 7 — Nghiệm thu Đa góc PVT, Monte Carlo & Hậu Layout PEX (`CACE` Signoff):** Kiểm chứng góc xấu nhất `{TT, SS, FF, FS, SF} × {VDD_min, VDD_max} × {-40°C..125°C}`, thống kê $\pm 3\sigma$ Pelgrom và ký sinh sau trích xuất RC.

---

## 3. Cấu trúc Kho Lưu trữ & Endpoint Tĩnh trên GitHub Pages

Khi xuất bản qua `.github/workflows/deploy.yml`, thư mục `_site/` phục vụ đồng thời giao diện Web tương tác v3 tại `/` và hệ thống API tệp tĩnh tất định tại `/kb/*` (100% Python 3 stdlib, không phụ thuộc `node_modules`):

```text
razavi-cmos-brain/
├── kb/
│   ├── manifest.json                     # Phiên bản 2026.11.18.6, thống kê 10 miền & SHA-256 toàn bộ tệp trong kb/
│   ├── router-index.json                 # Chỉ mục định tuyến tức thì (162 Nodes + 22-col coord_2d + design_cycle + Symptoms)
│   ├── nodes-bundle.json.gz              # Gói nén tất định 162 thẻ phục vụ tra cứu offline < 15 ms
│   ├── coordinates/
│   │   └── book-coordinates.json         # Tọa độ chính xác 19 chương, 293 mục, 1.475 phương trình & 423 mục 20_Index
│   ├── github-skills/
│   │   └── catalog.json                  # Danh mục 52 kho GitHub Analog/PMIC/AMS/EDA đã kiểm định giấy phép & IC617
│   ├── graph/
│   │   └── edges.jsonl                   # 482 cạnh có hướng: upgrades_to | fixes | compensated_by | requires | governed_by ...
│   ├── nodes/<domain>/<id>.md            # 162 Thẻ Tri thức & Playbook 6 khối xuyên suốt 10 tầng kiến trúc
│   ├── diagrams/*.svg                    # 72 Sơ đồ nguyên lý & lưu đồ vector SVG + diagrams-manifest.json
│   ├── checklists/*.json                 # 21 Bảng kiểm bất biến cấu trúc độc lập tiến trình (180nm / 90nm / 65nm / 45nm)
│   └── glossary/
│       └── terms-vi-en.json              # 2.280 thuật ngữ song ngữ Anh–Việt chuẩn CLB & PMIC/AMS (T001–T2280)
├── runtime/                              # Trọn bộ Runtime Engine SKILL-ANALOG v4.0 (Python 2.6.6 + Python 3 stdlib)
│   ├── manifest.json                     # Danh mục SHA-256 toàn bộ công cụ runtime phục vụ đồng bộ nguyên tử OTA
│   ├── bootstrap_rhel6_ota.py            # Kịch bản 1 dòng nâng cấp máy ảo RHEL 6.5 & biên dịch lại LUT GPDK090/045
│   ├── tools/                            # analogctl, ota_sync, kb_lookup, kb_fetch, psf_audit, gmid_lut, sizing_opt, ic617_*
│   ├── models/veriloga/                  # pwm_switch_avg_ccm_dcm.va (Vorperian CCM/DCM trơn C^inf, đúng tổn hao RMS DCM)
│   ├── integration/                      # install.py (RHEL 6.5) & setup_windows_agents.py (Windows Junctions)
│   └── references/                       # Tài liệu vận hành Cadence IC617, Spectre 15.1, gm/ID & hợp đồng phép đo
├── site/
│   ├── index.html                        # Ứng dụng Web: 10 Tầng, Bộ lọc PMIC/AMS/Skills, Chu trình 7 Bước & Đồ thị 22 Cột
│   ├── styles.css                        # Giao diện học thuật tối giản ấm độ tương phản cao (Light / Dark)
│   └── app.js                            # Tra cứu tọa độ / PMIC / AMS / Tiếng Việt không dấu, Đồ thị 2D 22 cột, KaTeX
├── skills/
│   ├── analog-design/                    # Unified Skill cho Codex Desktop, Antigravity Desktop & RHEL 6.5 Codex
│   └── razavi-cmos-brain/                # Skill chuyên biệt tra cứu & quản trị kho tri thức
├── tools/
│   ├── generate_diagrams.py              # Trình sinh & kiểm định không va chạm nhãn cho 72 sơ đồ vector SVG
│   ├── build_index.py                    # Trình biên dịch 10 miền (.build.lock), nodes-bundle & kb/runtime manifests
│   └── manage_kb.py                      # CLI 1 lệnh: new-card, add-edge, rebuild & publish trực tiếp lên GitHub OTA
├── validators/
│   └── validate_brain.py                 # Kiểm định 100% 162 thẻ, 1.475 PT, 72 SVG, 21 checklist, Python 2.6 AST & SHA-256
├── HUONG-DAN-CAP-NHAT.md                 # Quy trình 3 bước mở rộng thẻ/kỹ năng mới & đồng bộ sang ổ F:
└── .github/workflows/deploy.yml          # Kiểm định tự động & triển khai GitHub Pages
```

---

## 4. Chạy Kiểm định & Xem Giao diện Web v3 Cục bộ

Yêu cầu duy nhất: **Python 3.8+** (100% thư viện chuẩn `stdlib`, luôn chạy với `-B` hoặc `PYTHONDONTWRITEBYTECODE=1`).

```bash
# 1. Hợp nhất các mảnh cạnh (nếu có), biên dịch chỉ mục 10 miền và chạy kiểm định toàn vẹn
python -B tools/manage_kb.py rebuild

# 2. Chạy riêng bộ kiểm định 162 thẻ, 72 SVG, 21 checklist, 2.280 thuật ngữ, 52 repo GitHub & đồ thị cạnh
python -B validators/validate_brain.py

# 3. Kiểm tra cú pháp JavaScript giao diện Web v3 & chạy máy chủ tĩnh cục bộ
node --check site/app.js
python -B -m http.server 8080
# Mở trình duyệt tại: http://localhost:8080/site/
```

---

## 5. Bản quyền & Minh bạch Nguồn Học thuật / Mã nguồn Mở

- Mã nguồn công cụ, bộ kiểm định, 72 sơ đồ vector tự dựng, 21 bảng kiểm cấu trúc và giao diện Web v3 trong kho này được phát hành theo giấy phép **MIT License** ([LICENSE](LICENSE)).
- Toàn bộ 162 thẻ tri thức và Playbook thực chiến được biên soạn độc lập bằng văn phong kỹ thuật gốc (phương trình giải tích, bất biến cấu trúc, cây chẩn đoán lỗi và hợp đồng kiểm chứng Spectre/SKILL/Verilog-A); **không sao chép nguyên văn đoạn văn bản dài từ sách in hay chép nguyên khối mã nguồn chưa cấp phép**, đồng thời ghi nhận minh bạch giấy phép SPDX và mã băm commit khóa cứng của cả 52 kho GitHub trong `kb/github-skills/catalog.json`.
