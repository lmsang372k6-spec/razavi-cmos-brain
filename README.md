# Razavi CMOS Knowledge Brain (`2026.11.18.1`)

- **Kho lưu trữ GitHub chính thức:** https://github.com/lmsang372k6-spec/razavi-cmos-brain
- **Bản đồ Tri thức Tương tác & Static API (GitHub Pages):** https://lmsang372k6-spec.github.io/razavi-cmos-brain/
- **Endpoint Raw tức thì cho Codex / CLI:** https://raw.githubusercontent.com/lmsang372k6-spec/razavi-cmos-brain/main

**Bộ não Bản đồ Tri thức Thiết kế Vi mạch Tương tự CMOS** (Structured Knowledge Graph, Process-Agnostic Structural Checklists & Interactive Engineering Reference) được chưng cất có hệ thống từ toàn bộ **19 chương** của giáo trình kinh điển *Design of Analog CMOS Integrated Circuits (2nd Edition)* — Behzad Razavi, kết hợp kho **2.200 thuật ngữ song ngữ Anh–Việt chuẩn CLB Vi Mạch (`T001–T2200`)**.

Kho tri thức này được thiết kế kép cho cả **kỹ sư / người học thiết kế vi mạch** (qua ứng dụng Web Bản đồ Tri thức tương tác trên GitHub Pages) lẫn **tác tử AI thiết kế mạch Codex trên Cadence Virtuoso IC617 / Spectre 15.1** (qua các endpoint JSON/Markdown tĩnh tất định và bộ định tuyến cục bộ `< 10 ms` tương thích Python 2.6.6 trên RHEL 6.5).

---

## 1. Kiến trúc 7 Tầng Tri thức (Toàn bộ 19 Chương Razavi 2nd Ed.)

| Tầng | Miền tri thức (`kb/nodes/<domain>/`) | Chương Razavi | Trọng tâm kỹ thuật & Bất biến thiết kế |
|---|---|---|---|
| **1** | `foundations` | Ch.01, 02, 11, 17 | Bát giác Thiết kế Tương tự (8 trục đánh đổi), vật lý MOSFET, mô hình tín hiệu nhỏ & tụ ký sinh, hiệu ứng kênh ngắn (bão hòa vận tốc, DIBL, suy giảm $r_o$), định cỡ nanomet theo $V_{DS,\min}$ & $g_m/I_D$, 5 góc PVT (`TT/NN, FF, SS, FS, SF`). |
| **2** | `stages-and-mirrors` | Ch.03, 04, 05 | Tầng CS (tải R, diode, nguồn dòng, suy biến nguồn), Source Follower, Common-Gate, Cascode & Folded-Cascode đơn tầng, cặp vi sai & CMRR, Gilbert cell, chuỗi tiến hóa Gương dòng cơ bản $\to$ Cascode $\to$ **LVCCML dải rộng ($2V_{DS,\min}$)**, 5T-OTA. |
| **3** | `dynamics-noise-feedback` | Ch.06, 07, 08 | Định lý Miller & RHP zero truyền thẳng $+g_m/C_{GD}$, ZVTC & EET, $Z_{out}$ cảm kháng của SF, doublet gương dòng, nhiễu nhiệt $4kT\gamma g_m$ & $1/f$, quy đổi nhiễu ngõ vào, 4 cấu trúc hồi tiếp Sense–Return, tải hai cửa, định lý Bode/Blackman/Middlebrook & Spectre `stb` (`iprobe`/`diffstbprobe`). |
| **4** | `opamps-and-compensation` | Ch.09, 10 | Đối chiếu Telescopic, Folded-Cascode ($I_{\text{fold}} > I_{\text{tail}}/2$), Two-Stage Miller ($V_{GS6}=V_{DS4}$) và Gain-Boosted Cascode; mạch CMFB; Slew Rate & Class-AB; PSRR; dự trữ pha đa cực, tách cực Miller (Pole Splitting), điện trở triệt RHP zero $R_z$, bù Ahuja qua cascode & tiêu chuẩn ổn định Nyquist. |
| **5** | `references-and-biasing` | Ch.12 (+ Ch.08/10) | Phân cực độc lập nguồn cấp & mạch khởi động (Startup thoát $I=0$), triệt tiêu nhiệt CTAT + PTAT, lõi Bandgap $1{,}25\text{ V}$ & bẫy khuếch đại lệch không $(1+R_2/R_3)V_{OS}$, dòng PTAT / Constant-$G_m$, Bandgap hạ áp dưới $1\text{ V}$ (Banba) & tổng hợp bộ ổn áp tuyến tính **CMOS LDO**. |
| **6** | `sampled-and-clocked` | Ch.13, 15, 16 | Công tắc MOS/CMOS TG, phun điện tích kênh dẫn & xuyên nhiễu xung nhịp, quy tắc vàng **lấy mẫu tấm đáy (Bottom-Plate Sampling)**, công tắc Bootstrap, khuếch đại/tích phân SC & SC-CMFB, dao động vòng & LC ghép chéo/Colpitts, VCO & nhiễu pha, PLL loại I & **Charge-Pump PLL loại II**. |
| **7** | `nonideal-and-physical` | Ch.14, 18, 19 | Méo hài & khử hài chẵn vi sai, **định luật Pelgrom & đối ngẫu định cỡ cặp vi sai – gương dòng**, khử lệch không động Auto-Zeroing / CDS, cấu trúc giếng CMOS, chốt ký sinh SCR **Latch-up & Guard Ring**, chia ngón Multi-finger, **Common-Centroid ABBA**, Dummy / STI (LOD) / WPE & đóng gói dây hàn $L\,di/dt$. |

---

## 2. Cấu trúc Kho Lưu trữ & Endpoint Tĩnh trên GitHub Pages

Khi xuất bản qua `.github/workflows/deploy.yml`, thư mục `_site/` phục vụ đồng thời giao diện Web tương tác tại `/` và hệ thống API tệp tĩnh tất định tại `/kb/*` (không cần máy chủ backend, không phụ thuộc `node_modules`):

```text
razavi-cmos-brain/
├── kb/
│   ├── manifest.json                 # Phiên bản phát hành, thống kê & SHA-256 mọi tệp trong kb/
│   ├── router-index.json             # Chỉ mục tra cứu tức thì (Nodes, Checklists, Symptoms, ASCII tokens)
│   ├── graph/
│   │   └── edges.jsonl               # Đồ thị có hướng: upgrades_to | fixes | compensated_by | trades_off_with ...
│   ├── nodes/<domain>/<id>.md        # 68 Thẻ Tri thức chuyên sâu 6 khối (JSON frontmatter + Markdown/LaTeX)
│   ├── diagrams/*.svg                # 38 Sơ đồ nguyên lý mạch vector SVG sắc nét + diagrams-manifest.json
│   ├── checklists/*.json             # 13 Bảng kiểm bất biến cấu trúc độc lập tiến trình (90nm / 65nm / 45nm)
│   └── glossary/
│       └── terms-vi-en.json          # 2.200 thuật ngữ song ngữ Anh–Việt chuẩn CLB (T001–T2200)
├── site/
│   ├── index.html                    # Ứng dụng Web Bản đồ Tri thức & Đồ thị Nâng cấp Tương tác
│   ├── styles.css                    # Giao diện học thuật độ tương phản cao (Light / Dark)
│   └── app.js                        # Tìm kiếm không dấu tiếng Việt + Anh, đồ thị SVG pan/zoom, KaTeX
├── skills/
│   └── razavi-cmos-brain/            # Skill chuẩn cho Codex / AI Agent (SKILL.md + agents/openai.yaml)
├── tools/
│   ├── generate_diagrams.py          # Trình sinh 38 sơ đồ mạch vector SVG thuần Python 3 stdlib
│   ├── build_index.py                # Trình biên dịch router-index.json & manifest.json
│   └── manage_kb.py                  # CLI 1 lệnh: thêm thẻ mới, nối cạnh nâng cấp, rebuild & kiểm định
├── validators/
│   └── validate_brain.py             # Kiểm định 100% schema 6 khối, LaTeX, SVG, Checklist & Đồ thị cạnh
├── HUONG-DAN-CAP-NHAT.md             # Quy trình 3 bước thêm thẻ mới & đồng bộ tức thì sang ổ F:
└── .github/workflows/deploy.yml      # Kiểm định tự động & triển khai GitHub Pages
```

---

## 3. Chạy Kiểm định & Xem Giao diện Web Cục bộ

Yêu cầu duy nhất: **Python 3.8+** (100% thư viện chuẩn `stdlib`, **không** cần cài đặt gói `pip` hay `npm` ngoài).

```bash
# 1. Biên dịch lại chỉ mục định tuyến và bảng kê SHA-256
python tools/build_index.py

# 2. Chạy bộ kiểm định toàn vẹn 68 thẻ, 38 sơ đồ SVG, 13 checklist, 2.200 thuật ngữ và đồ thị cạnh
python validators/validate_brain.py

# 3. Mở giao diện Web tương tác ngay trên máy cục bộ
python -m http.server 8080
# Sau đó mở trình duyệt tại: http://localhost:8080/site/
```

---

## 4. Mở rộng Kho Tri thức & Tích hợp `SKILL-ANALOG` trên Máy ảo Cadence RHEL 6.5 (`Python 2.6.6`)

- **Cập nhật & mở rộng siêu nhanh ([HUONG-DAN-CAP-NHAT.md](HUONG-DAN-CAP-NHAT.md)):**
  - `python tools/manage_kb.py status` — thống kê toàn bộ thẻ, chương, cạnh đồ thị, checklist, sơ đồ SVG và thuật ngữ.
  - `python tools/manage_kb.py new-card <domain> <id> "<title_vi>" "<title_en>" --chapter <N>` — sinh khung thẻ chuẩn 6 khối.
  - `python tools/manage_kb.py add-edge <from> <to> <rel> "<when>" "<cost>" "<ref>"` — thêm cạnh nâng cấp vào `edges.jsonl`.
  - `python tools/manage_kb.py rebuild` — tự động biên dịch lại chỉ mục và chạy bộ kiểm định toàn vẹn `validate_brain.py`.
- **Định tuyến trực tiếp cho Codex trên ổ `F:` (`F:\SKILL-ANALOG` / RHEL 6.5):**
  - Phân hệ định tuyến mỏng (`library/tools/kb_lookup.py` và `library/tools/kb_fetch.py`) tương thích nghiêm ngặt với **Python 2.6.6** và **Python 3**.
  - **Định tuyến tức thì (`< 10 ms`):** Tìm thẻ mạch, chẩn đoán triệu chứng lỗi, tra đường nâng cấp cấu trúc (`upgrades_to`, `fixes`, `compensated_by`), lọc theo 19 chương sách Razavi, đọc 13 bảng kiểm bất biến (`checklists`) và tra cứu 2.200 thuật ngữ Anh–Việt không dấu.
  - **Đồng bộ trực tiếp từ GitHub (`kb_fetch.py --sync`) + Dự phòng Offline 100%:** Tự động tải chỉ mục và thẻ mới nhất qua HTTPS từ GitHub Pages / Raw GitHub (hỗ trợ gói chứng chỉ CA mới trên RHEL 6.5 kèm xác thực SHA-256 vào bộ đệm ngoài thư viện), và tự động chuyển mượt sang gói nén cục bộ `nodes-bundle.json.gz` khi ngoại tuyến.

---

## 5. Bản quyền & Minh bạch Nguồn Học thuật

- Mã nguồn công cụ, bộ kiểm định, sơ đồ vector tự dựng, bảng kiểm cấu trúc và giao diện Web trong kho này được phát hành theo giấy phép **MIT License** ([LICENSE](LICENSE)).
- Toàn bộ nội dung thẻ tri thức được biên soạn độc lập dưới dạng công thức giải tích, bất biến cấu trúc và quy tắc thiết kế tham số hóa; **tuyệt đối không sao chép nguyên văn đoạn văn bản dài hay cắt ảnh trang sách gốc** từ *Design of Analog CMOS Integrated Circuits (2nd Edition)* của Behzad Razavi (McGraw-Hill Education). Mọi mục chỉ dẫn Chương/Mục/Phương trình đều nhằm giúp người đọc đối chiếu trực tiếp với sách in chính thức.
