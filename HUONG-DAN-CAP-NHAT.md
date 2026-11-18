# Hướng Dẫn Mở Rộng & Cập Nhật Bộ Não Tri Thức (`razavi-cmos-brain` · `2026.11.18.3`)

Kho tri thức được thiết kế để bạn hoặc AI có thể **thêm thẻ lý thuyết Razavi mới, thêm Playbook thực chiến GitHub/EDA (`skill-*`), thêm cạnh nâng cấp, cập nhật tọa độ sách hoặc thêm luật kiểm tra chỉ bằng 1–2 lệnh**, kiểm định tự động 100% và đồng bộ ngay tới **Codex trên ổ `F:`** qua GitHub!

---

## 1. Quy trình 3 bước thêm Thẻ Tri thức hoặc Playbook Thực chiến mới

### Bước 1: Tạo khung thẻ chuẩn 6 khối tự động
- **Thêm thẻ cấu trúc / lý thuyết Razavi (Tầng 1–7):**
```bash
python -B tools/manage_kb.py new-card opamps-and-compensation topo-recycling-folded-cascode \
  "Bộ khuếch đại cascode gập tái chế dòng (Recycling Folded-Cascode)" \
  "Recycling Folded-Cascode OTA" \
  --chapter 9 --section "9.2.4" --diagram folded-cascode-ota.svg
```
- **Thêm thẻ Playbook thực chiến GitHub / Cadence EDA (Tầng 8 `eda-and-github-skills`):**
```bash
python -B tools/manage_kb.py new-card eda-and-github-skills skill-spectre-hb-mixer-iip3-tb \
  "Mô phỏng Độ tuyến tính IIP3 & Hệ số Nhiễu bằng Harmonic Balance trong SpectreRF" \
  "SpectreRF Harmonic Balance IIP3 & NF Testbench Workflow" \
  --chapter 14 --section "14.1" --diagram spectre-pss-pnoise-flow.svg
```
*(Lưu ý: Với thẻ `skill-*`, khai báo `github_refs` trong JSON frontmatter trỏ tới kho mã nguồn đã kiểm định trong `kb/github-skills/catalog.json`.)*

### Bước 2: Nối cạnh nâng cấp / kiểm chứng vào Đồ thị (`edges.jsonl`)
```bash
python -B tools/manage_kb.py add-edge topo-folded-cascode-ota topo-recycling-folded-cascode upgrades_to \
  "Cần nhân đôi hỗ dẫn hiệu dụng Gm và GBW trên cùng ngân sách dòng tĩnh" \
  "Thêm gương dòng tách nhánh tại nút gập, cần ghép đối xứng tỉ số K" \
  "Ch.9 §9.2.4 + Mở rộng cấu trúc"
```

### Bước 3: Biên dịch lại chỉ mục tọa độ 2D + Kiểm định toàn vẹn + Đẩy lên GitHub
```bash
python -B tools/manage_kb.py rebuild
node --check site/app.js
git add -A
git commit -m "feat(kb): add recycling folded-cascode topology card"
git push
```
Ngay khi `git push`, GitHub Actions (`.github/workflows/deploy.yml`) tự động chạy `validate_brain.py` + `node --check site/app.js` và xuất bản lên **GitHub Pages** (`https://lmsang372k6-spec.github.io/razavi-cmos-brain/`).

---

## 2. Cách Codex ở Ổ `F:` Tự Động Đồng Bộ Tọa Độ & GitHub Skills Mới

Trong máy ảo Cadence RHEL 6.5 (hoặc trên Windows), không cần cài lại `SKILL-ANALOG`. Chỉ cần chạy:
```bash
python /home/disk/eda/references/SKILL-ANALOG/tools/kb_fetch.py --sync
```
Lệnh `--sync` tải trực tiếp `router-index.json`, `edges.jsonl`, `manifest.json`, `terms-vi-en.json`, `coordinates/book-coordinates.json` và `github-skills/catalog.json` mới nhất từ GitHub vào bộ nhớ đệm người dùng (`~/.cache/razavi-cmos-brain/`), giúp các lệnh `kb_lookup.py coord`, `kb_lookup.py skills` và `kb_fetch.py` lập tức nhìn thấy mọi bản cập nhật mà vẫn giữ nguyên tính toàn vẹn `analogctl.py verify` của thư mục gốc!
