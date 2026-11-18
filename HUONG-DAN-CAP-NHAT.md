# Hướng Dẫn Mở Rộng & Cập Nhật Bộ Não Tri Thức (`razavi-cmos-brain` · `2026.11.18.4`)

Kho tri thức v3 được thiết kế để bạn hoặc AI có thể **thêm thẻ lý thuyết Razavi (Tầng 1–7), thẻ Quản lý Nguồn PMIC (Tầng 8), thẻ Vi mạch Hỗn hợp AMS & Kiến trúc Hệ thống (Tầng 9), hoặc Playbook Chu trình Khép kín Cadence–Codex (Tầng 10)** chỉ bằng 1–2 lệnh, kiểm định tự động 100% và đồng bộ ngay tới **Codex trên ổ `F:` (`F:\SKILL-ANALOG` / RHEL 6.5 Python 2.6.6)**!

---

## 1. Bộ CLI Quản Trị Toàn Diện `tools/manage_kb.py` (Mọi Tầng Đều Nâng Cấp Bằng 1 Lệnh)

| Lệnh quản trị | Chức năng tự động hóa |
|---|---|
| `python -B tools/manage_kb.py status` | Thống kê tức thì toàn bộ 10 miền, 162+ thẻ, 72+ SVG, 21+ checklists, 482+ cạnh, 2.280+ thuật ngữ & 52+ repo GitHub. |
| `python -B tools/manage_kb.py new-card <domain> <id> "<vi>" "<en>" --chapter <N>` | Sinh khung thẻ chuẩn 6 khối đúng JSON frontmatter trên bất kỳ miền nào trong 10 miền. |
| `python -B tools/manage_kb.py new-checklist <id> "<vi>" "<en>"` | Tạo khung bảng kiểm bất biến đa tiến trình mới trong `kb/checklists/`. |
| `python -B tools/manage_kb.py add-edge <from> <to> <rel> "<when>" "<cost>" "<ref>"` | Nối cạnh có hướng vào `kb/graph/edges.jsonl` (chống trùng lặp tự động). |
| `python -B tools/manage_kb.py add-term "<en>" "<vi>" --chapter <N>` | Cấp mã `Txxxx` kế tiếp và thêm thuật ngữ song ngữ chuẩn CLB vào `terms-vi-en.json`. |
| `python -B tools/manage_kb.py add-repo <owner/repo> --commit <40hex> ...` | Đăng ký kho GitHub đã khóa commit SHA 40 ký tự vào `kb/github-skills/catalog.json`. |
| `python -B tools/manage_kb.py rebuild [--export-bundle PATH]` | Biên dịch lại `router-index.json` + `manifest.json`, chạy `validate_brain.py` (`0` lỗi) và xuất gói nén offline. |

---

## 2. Quy trình 3 bước thêm Thẻ Tri thức hoặc Playbook Thực chiến mới

### Bước 1: Tạo khung thẻ chuẩn 6 khối tự động trên 1 trong 10 miền
- **Thêm thẻ PMIC (Tầng 8 `power-management-ic`) hoặc AMS (Tầng 9 `ams-filters-and-system`):**
```bash
python -B tools/manage_kb.py new-card power-management-ic topo-multiphase-interleaved-buck \
  "Bộ biến đổi hạ áp đa pha đan xen tự cân bằng dòng (Multiphase Interleaved Buck)" \
  "Multiphase Interleaved Synchronous Buck Converter" \
  --chapter 12 --section "12.6" --diagram synchronous-buck-converter.svg
```
- **Thêm thẻ Playbook Tối ưu Khép kín Cadence / GitHub EDA (Tầng 10 `eda-and-github-skills`):**
```bash
python -B tools/manage_kb.py new-card eda-and-github-skills skill-spectre-hb-mixer-iip3-tb \
  "Mô phỏng Độ tuyến tính IIP3 & Hệ số Nhiễu bằng Harmonic Balance trong SpectreRF" \
  "SpectreRF Harmonic Balance IIP3 & NF Testbench Workflow" \
  --chapter 14 --section "14.1" --diagram spectre-pss-pnoise-flow.svg
```
*(Lưu ý: Với thẻ `skill-*`, khai báo `github_refs` trong JSON frontmatter trỏ tới kho mã nguồn đã kiểm định trong danh mục 52 repo `kb/github-skills/catalog.json`.)*

### Bước 2: Nối cạnh nâng cấp / kiểm chứng vào Đồ thị (`edges.jsonl`)
```bash
python -B tools/manage_kb.py add-edge topo-synchronous-buck-converter-architecture topo-multiphase-interleaved-buck upgrades_to \
  "Dòng tải SoC > 5–20 A cần triệt tiêu gợn dòng tụ vào/ra theo hệ số N pha và giảm nhiệt cục bộ" \
  "Cần vòng cân bằng dòng giữa các pha (Per-Phase Current Sharing) và bộ tạo xung lệch pha 360°/N" \
  "Erickson Ch.8 + westonb/open-pmic"
```

### Bước 3: Biên dịch lại chỉ mục 10 miền (22 cột 2D) + Kiểm định toàn vẹn + Đẩy lên GitHub
```bash
python -B tools/manage_kb.py rebuild
node --check site/app.js
# Sau khi rà soát báo cáo kiểm định ok: true:
git add -A
git commit -m "feat(kb): add multiphase interleaved buck topology card"
git push
```
Lệnh `manage_kb.py rebuild` tự động gộp mọi mảnh cạnh tạm `kb/graph/edges-*.jsonl` (nếu có) vào `kb/graph/edges.jsonl`, cập nhật `kb/router-index.json` + `kb/manifest.json` và chạy `validators/validate_brain.py` kiểm định đủ **10 miền, 72 SVG, 21 bảng kiểm, 2.280 thuật ngữ, 52 kho GitHub và cân bằng toán học LaTeX**.

---

## 2. Xuất gói Nén Tất định & Đồng bộ sang Ổ `F:` (`SKILL-ANALOG`)

- **Đóng gói trực tiếp trên máy chủ Windows sang `F:\SKILL-ANALOG`:**
```bash
python -B tools/manage_kb.py rebuild --export-bundle "F:\SKILL-ANALOG\library\kb\nodes-bundle.json.gz"
```
- **Đồng bộ trực tuyến từ trong máy ảo Cadence RHEL 6.5 (`Python 2.6.6`):**
```bash
python /home/disk/eda/references/SKILL-ANALOG/tools/kb_fetch.py --sync
```
Lệnh `--sync` tải trực tiếp `router-index.json`, `edges.jsonl`, `manifest.json`, `terms-vi-en.json`, `coordinates/book-coordinates.json`, `github-skills/catalog.json` và toàn bộ **21 tệp `checklists/*.json`** mới nhất vào bộ nhớ đệm người dùng (`~/.cache/razavi-cmos-brain/`), giúp `kb_lookup.py` và Chu trình Tối ưu Khép kín 7 Bước của Codex lập tức cập nhật mà vẫn giữ nguyên vẹn chữ ký `analogctl.py verify` của thư mục gốc!
