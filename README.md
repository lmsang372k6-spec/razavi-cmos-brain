# Razavi CMOS Knowledge Brain (`2026.11.18.3`)

- **Kho lưu trữ GitHub chính thức:** https://github.com/lmsang372k6-spec/razavi-cmos-brain
- **Bản đồ Tọa độ Tri thức Tương tác & Static API (GitHub Pages):** https://lmsang372k6-spec.github.io/razavi-cmos-brain/
- **Endpoint Raw tức thì cho Codex / CLI:** https://raw.githubusercontent.com/lmsang372k6-spec/razavi-cmos-brain/main

**Bộ não Bản đồ Tọa độ Tri thức Thiết kế Vi mạch Tương tự CMOS & Thực chiến EDA** (`134` thẻ 6 khối = `112` thẻ lý thuyết & cấu trúc mạch chi tiết xuyên suốt **19 chương** *Design of Analog CMOS Integrated Circuits, 2nd Ed.* của Behzad Razavi + `22` thẻ thực chiến GitHub Analog/Cadence Virtuoso IC617/Spectre 15.1 Skills), tích hợp **56 sơ đồ nguyên lý vector SVG**, **319 cạnh đồ thị tiến hóa có hướng**, **16 bảng kiểm bất biến đa tiến trình**, **chỉ mục tọa độ sách chính xác (`293` mục, `230` phương trình cột mốc, `423` mục `20_Index`)**, **31 kho GitHub Analog/EDA đã kiểm định**, và **2.200 thuật ngữ song ngữ Anh–Việt chuẩn CLB Vi Mạch (`T001–T2200`)**.

Kho tri thức được thiết kế kép cho cả **kỹ sư / người học thiết kế vi mạch** (qua ứng dụng Web Bản đồ Tọa độ 2D đa khung nhìn trên GitHub Pages) lẫn **tác tử AI thiết kế mạch Codex trên Cadence Virtuoso IC617 / Spectre 15.1** (qua các endpoint JSON/Markdown tĩnh tất định và bộ định tuyến cục bộ `< 10 ms` tương thích Python 2.6.6 trên RHEL 6.5).

---

## 1. Kiến trúc 8 Tầng Tri thức & Thực chiến EDA

| Tầng | Miền tri thức (`kb/nodes/<domain>/`) | Chương / Phạm vi | Trọng tâm kỹ thuật & Bất biến thiết kế |
|---|---|---|---|
| **1** | `foundations` | Ch.01, 02, 11, 17 | Bát giác Thiết kế Tương tự (8 trục đánh đổi), dẫn yếu dưới ngưỡng (Subthreshold), vật lý MOSFET & tụ ký sinh theo vùng hoạt động, hiệu ứng kênh ngắn, định cỡ nanomet theo $V_{DS,\min}$ & $g_m/I_D$, 5 góc PVT. |
| **2** | `stages-and-mirrors` | Ch.03, 04, 05 | Tầng CS (tải R, diode, triode, nguồn dòng, suy biến nguồn), Source Follower & Super Source Follower, Common-Gate, Cascode & Regulated Cascode, lựa chọn cấu hình transistor (§3.5–3.7), cặp vi sai tải gương dòng chủ động (5T-OTA), Gilbert cell, Wilson & **LVCCML dải rộng ($2V_{DS,\min}$)**. |
| **3** | `dynamics-noise-feedback` | Ch.06, 07, 08 | Định lý Miller & RHP zero, ZVTC & EET, cực tần số cao Cascode/CG & suy giảm CMRR cặp vi sai, đối chiếu nhiễu đơn tầng / cặp vi sai / bẫy nhân nhiễu gương dòng & định luật công suất–SNR, 4 cấu trúc hồi tiếp hai cửa, khuếch đại điện trở chuyển tiếp **TIA**, định lý Bode/Blackman/Middlebrook. |
| **4** | `opamps-and-compensation` | Ch.09, 10 | Đối chiếu Telescopic, Folded-Cascode ($I_{\text{fold}} > I_{\text{tail}}/2$), Two-Stage Miller, Gain-Boosted Cascode & đầu vào **Rail-to-Rail Constant-$G_m$**; quy trình định cỡ từng bước, 4 họ CMFB, phân tích $PSRR^+/PSRR^-$, ngân sách Slewing + Linear Settling, ánh xạ dự trữ pha $PM \leftrightarrow$ vọt lố, tách cực Miller + $R_z$, bù Ahuja, **Nested Miller 3 tầng** & Nyquist. |
| **5** | `references-and-biasing` | Ch.12 (+ Ch.08/10) | Tự phân cực **Constant-$G_m$** & mạch khởi động thoát điểm chết $I=0$, lõi Bandgap $1{,}25\text{ V}$, bù cong bậc cao $T\ln T$ & lọc nhiễu Bandgap, Bandgap hạ áp dưới $1\text{ V}$ (Banba) & tổng hợp bộ ổn áp **CMOS LDO**. |
| **6** | `sampled-and-clocked` | Ch.13, 15, 16 | Công tắc MOS & Bootstrap, **lấy mẫu tấm đáy ($\phi_{1e}$)**, khuếch đại nhân áp SC & bộ tích phân SC miễn nhiễm ký sinh, so sánh chốt động **StrongARM / Miyahara**, kiến trúc **SAR ADC C-DAC**, dao động vòng / LC ghép chéo / **Colpitts / Quadrature VCO**, nhiễu pha Leeson & ISF, PFD chống vùng chết / tạp phổ Charge Pump, tổng hợp bộ lọc vòng bậc 3 **CP-PLL**, bộ tổng hợp tần số Integer/Fractional-$N$ & DLL. |
| **7** | `nonideal-and-physical` | Ch.11, 14, 17, 18, 19 | Nghiên cứu thiết kế Op-Amp nanomet, méo hài chẵn HD2 do mất cân xứng, **định luật Pelgrom**, khử lệch không động Auto-Zeroing / CDS đối chiếu **Chopper Stabilization**, mô hình BSIM4 & FinFET, quy trình chế tạo CMOS & điện trở/tụ tích hợp, Latch-up & Guard Ring, dây dẫn RC / Electromigration / IR Drop, nhiễu đế bán dẫn, **bảo vệ ESD Padring & ký sinh dây hàn $L\,di/dt$**. |
| **8** | `eda-and-github-skills` | Thực chiến GitHub / IC617 / Spectre | **22 Playbook thực chiến** chưng cất từ **31 kho mã nguồn mở đã kiểm định**: định cỡ bảng tra `gm/ID` (`bmurmann` / `pygmid`), Spectre `stb`/`diffstbprobe`, SpectreRF `pss`/`pac`/`pnoise`/`pstb`, góc PVT & Monte Carlo, tự động hóa Virtuoso IC617 SKILL/CDF & OCEAN/PSF, cây chẩn đoán lỗi 5T-OTA / Miller / Folded-Cascode / CMFB / Bandgap / LDO / Comparator / SAR ADC / SC / VCO / PLL, Verilog-A, Common-Centroid Layout, gỡ lỗi DRC/LVS/PEX và đặc tính hóa theo hợp đồng `CACE`. |

---

## 2. Cấu trúc Kho Lưu trữ & Endpoint Tĩnh trên GitHub Pages

Khi xuất bản qua `.github/workflows/deploy.yml`, thư mục `_site/` phục vụ đồng thời giao diện Web tương tác v2 tại `/` và hệ thống API tệp tĩnh tất định tại `/kb/*` (không cần máy chủ backend, không phụ thuộc `node_modules`):

```text
razavi-cmos-brain/
├── kb/
│   ├── manifest.json                     # Phiên bản 2026.11.18.3, thống kê & SHA-256 toàn bộ 212 tệp trong kb/
│   ├── router-index.json                 # Chỉ mục định tuyến tức thì (134 Nodes + coord_2d + section_coords + Symptoms)
│   ├── coordinates/
│   │   └── book-coordinates.json         # Tọa độ chính xác 19 chương, 293 mục, 230 phương trình & 423 mục 20_Index
│   ├── github-skills/
│   │   └── catalog.json                  # Danh mục 31 kho GitHub Analog/EDA đã kiểm định giấy phép & độ tương thích IC617
│   ├── graph/
│   │   └── edges.jsonl                   # 319 cạnh có hướng: upgrades_to | fixes | compensated_by | requires | governed_by ...
│   ├── nodes/<domain>/<id>.md            # 134 Thẻ Tri thức & Playbook 6 khối (JSON frontmatter + Markdown/LaTeX)
│   ├── diagrams/*.svg                    # 56 Sơ đồ nguyên lý & lưu đồ kiểm chứng vector SVG + diagrams-manifest.json
│   ├── checklists/*.json                 # 16 Bảng kiểm bất biến cấu trúc độc lập tiến trình (180nm / 90nm / 65nm / 45nm)
│   └── glossary/
│       └── terms-vi-en.json              # 2.200 thuật ngữ song ngữ Anh–Việt chuẩn CLB (T001–T2200)
├── site/
│   ├── index.html                        # Ứng dụng Web v2: Thanh nhảy tọa độ, Đồ thị 2D, Cây 19 Chương & Kho GitHub Skills
│   ├── styles.css                        # Giao diện học thuật tối giản ấm độ tương phản cao (Light / Dark)
│   └── app.js                            # Tra cứu §Mục / Eq. / Trang / 20_Index / Tiếng Việt không dấu, Đồ thị 2D, KaTeX
├── skills/
│   └── razavi-cmos-brain/                # Skill chuẩn cho Codex / AI Agent (SKILL.md + agents/openai.yaml)
├── tools/
│   ├── generate_diagrams.py              # Trình sinh & kiểm định va chạm nhãn cho 56 sơ đồ vector SVG thuần Python 3 stdlib
│   ├── build_index.py                    # Trình biên dịch router-index.json (kèm tọa độ 2D) & manifest.json
│   └── manage_kb.py                      # CLI 1 lệnh: thêm thẻ mới, nối cạnh nâng cấp, rebuild & xuất gói nén offline
├── validators/
│   └── validate_brain.py                 # Kiểm định 100% 8 miền, tọa độ sách, GitHub catalog, LaTeX, SVG, Checklist & Đồ thị
├── HUONG-DAN-CAP-NHAT.md                 # Quy trình 3 bước mở rộng thẻ/kỹ năng mới & đồng bộ tức thì sang ổ F:
└── .github/workflows/deploy.yml          # Kiểm định tự động & triển khai GitHub Pages
```

---

## 3. Chạy Kiểm định & Xem Giao diện Web Tọa độ 2D Cục bộ

Yêu cầu duy nhất: **Python 3.8+** (100% thư viện chuẩn `stdlib`, **không** cần cài đặt gói `pip` hay `npm` ngoài; luôn chạy với `-B` hoặc `PYTHONDONTWRITEBYTECODE=1`).

```bash
# 1. Biên dịch lại chỉ mục định tuyến 2D và bảng kê SHA-256 + chạy kiểm định toàn vẹn
python -B tools/manage_kb.py rebuild

# 2. Chạy riêng bộ kiểm định 134 thẻ, 56 SVG, 16 checklist, tọa độ sách, catalog GitHub & đồ thị cạnh
python -B validators/validate_brain.py

# 3. Mở giao diện Web tương tác ngay trên máy cục bộ
python -B -m http.server 8080
# Mở trình duyệt tại: http://localhost:8080/site/
```

---

## 4. Định tuyến Tọa độ & GitHub Skills trên Máy ảo Cadence RHEL 6.5 (`Python 2.6.6`)

- **Quản trị kho tri thức 1 lệnh ([HUONG-DAN-CAP-NHAT.md](HUONG-DAN-CAP-NHAT.md)):**
  - `python -B tools/manage_kb.py status` — thống kê chi tiết 134 thẻ, tọa độ sách, kho GitHub, cạnh đồ thị, checklist, SVG và thuật ngữ.
  - `python -B tools/manage_kb.py new-card <domain> <id> "<title_vi>" "<title_en>" --chapter <N>` — tạo khung thẻ chuẩn 6 khối (hỗ trợ cả 7 tầng Razavi và tầng 8 `eda-and-github-skills`).
  - `python -B tools/manage_kb.py add-edge <from> <to> <rel> "<when>" "<cost>" "<ref>"` — thêm cạnh đồ thị có hướng.
  - `python -B tools/manage_kb.py rebuild` — biên dịch lại chỉ mục 2D + kiểm định toàn vẹn `ok: true`.
- **Định tuyến trực tiếp cho Codex trên ổ `F:` (`F:\SKILL-ANALOG` / RHEL 6.5):**
  - Bộ công cụ `library/tools/kb_lookup.py` và `library/tools/kb_fetch.py` tương thích 100% **Python 2.6.6** và **Python 3**:
    * `kb_lookup.py coord "9.2"` / `kb_lookup.py coord "Eq. 2.10"` / `kb_lookup.py coord "page 342"` — nhảy thẳng tới đúng trang sách, phương trình, mục sách Razavi và thẻ tri thức tương ứng.
    * `kb_lookup.py skills "pss pnoise"` — tra cứu nhanh 22 playbook thực chiến `skill-*` và 31 kho GitHub đã kiểm định tương thích IC617.
    * `kb_fetch.py --sync` — đồng bộ trực tiếp `router-index.json`, `edges.jsonl`, `book-coordinates.json`, `catalog.json` và các thẻ mới nhất từ GitHub kèm dự phòng offline `nodes-bundle.json.gz`.

---

## 5. Bản quyền & Minh bạch Nguồn Học thuật / Mã nguồn Mở

- Mã nguồn công cụ, bộ kiểm định, 56 sơ đồ vector tự dựng, 16 bảng kiểm cấu trúc và giao diện Web trong kho này được phát hành theo giấy phép **MIT License** ([LICENSE](LICENSE)).
- Toàn bộ 112 thẻ Razavi và 22 thẻ kỹ năng thực chiến EDA được biên soạn bằng văn phong kỹ thuật độc lập (phương trình giải tích, bất biến cấu trúc, cây chẩn đoán lỗi và hợp đồng kiểm chứng Spectre/SKILL); **tuyệt đối không sao chép nguyên văn đoạn văn bản dài từ sách in hay chép nguyên khối mã nguồn chưa cấp phép**, đồng thời ghi nhận minh bạch giấy phép SPDX và commit khóa cứng của từng kho GitHub trong `kb/github-skills/catalog.json`.
