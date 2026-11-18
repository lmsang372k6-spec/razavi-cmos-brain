# Hướng Dẫn Mở Rộng & Cập Nhật Bộ Não Tri Thức (`razavi-cmos-brain`)

Kho tri thức được thiết kế để bạn hoặc AI có thể **thêm thẻ mạch mới, thêm cạnh nâng cấp, thêm luật kiểm tra hoặc sửa phương trình chỉ bằng 1–2 lệnh**, tự động kiểm tra lỗi 100% và đồng bộ ngay tới **Codex trên ổ `F:`** qua GitHub!

---

## 1. Quy trình 3 bước thêm một Thẻ Tri thức mới

### Bước 1: Tạo khung thẻ chuẩn 6 khối tự động
```bash
python tools/manage_kb.py new-card opamps-and-compensation topo-recycling-folded-cascode \
  "Bộ khuếch đại cascode gập tái chế dòng (Recycling Folded-Cascode)" \
  "Recycling Folded-Cascode OTA" \
  --chapter 9 --section "9.2.4" --diagram folded-cascode-ota.svg
```
Lệnh này tạo sẵn file `kb/nodes/opamps-and-compensation/topo-recycling-folded-cascode.md` với đúng JSON frontmatter và đủ 6 mục tiêu chuẩn.

### Bước 2: Nối cạnh nâng cấp vào Đồ thị (`edges.jsonl`)
```bash
python tools/manage_kb.py add-edge topo-folded-cascode-ota topo-recycling-folded-cascode upgrades_to \
  "Cần nhân đôi hỗ dẫn hiệu dụng Gm và GBW trên cùng ngân sách dòng tĩnh" \
  "Thêm gương dòng tách nhánh tại nút gập, cần ghép đối xứng tỉ số K" \
  "Ch.9 §9.2.4 + Mở rộng cấu trúc"
```

### Bước 3: Biên dịch lại chỉ mục + Kiểm định tự động + Đẩy lên GitHub
```bash
python tools/manage_kb.py rebuild
git add -A
git commit -m "feat(kb): add recycling folded-cascode topology card"
git push
```
Ngay khi `git push`, GitHub Actions (`.github/workflows/deploy.yml`) tự động chạy lại `validate_brain.py` và xuất bản lên **GitHub Pages** (`https://lmsang372k6-spec.github.io/razavi-cmos-brain/`).

---

## 2. Cách Codex ở Ổ `F:` Tự Động Nhận Bản Cập Nhật Mới Từ GitHub

Trong máy ảo Cadence RHEL 6.5 (hoặc trên Windows), không cần cài lại `SKILL-ANALOG`. Chỉ cần chạy:
```bash
python /home/disk/eda/references/SKILL-ANALOG/tools/kb_fetch.py --sync
```
Lệnh `--sync` tải trực tiếp `router-index.json`, `edges.jsonl`, `manifest.json` và `terms-vi-en.json` mới nhất từ GitHub vào bộ nhớ đệm người dùng (`~/.cache/razavi-cmos-brain/`), giúp `kb_lookup.py` và `kb_fetch.py` lập tức nhìn thấy mọi thẻ mới bạn vừa đẩy lên GitHub mà vẫn giữ nguyên tính toàn vẹn `analogctl.py verify` của thư mục gốc!
