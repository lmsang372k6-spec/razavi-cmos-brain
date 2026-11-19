# Hướng Dẫn Biên Soạn Siêu Tốc & Đồng Bộ Đa Tác Tử OTA (`2026.11.19.1` · v4.0 SSOT)

Kho `razavi-cmos-brain` (v4.0) là **Nguồn Chân lý Duy nhất (Single-Source-of-Truth — SSOT)** cho cả tri thức (`kb/`) lẫn bộ công cụ thực thi (`runtime/`) trên cả 3 môi trường mà **không bao giờ cần đóng gói lại hay remount đĩa `.iso` thủ công**:
1. **Windows — `Codex Desktop` & `Antigravity Desktop`:** Đọc/ghi trực tiếp `0 ms` qua NTFS Directory Junctions (`C:\Users\Admin\.codex\skills\analog-design` và `C:\Users\Admin\.gemini\config\skills\analog-design` $\to$ `skills\analog-design`).
2. **Linux RHEL 6.5 VM — `Codex Linux` + `Cadence IC617` + `Spectre 15.1`:** Tự động kiểm tra `HEAD` commit SHA từ GitHub nền mỗi **`60 giây` (`TTL = 60s`)**, xác thực `SHA-256` từng tệp và hoán đổi nguyên tử thư mục mà vẫn bảo toàn `sources/` (hoặc khóa mạng tuyệt đối `100%` khi bật `--offline` / `SKILL_ANALOG_OFFLINE=1`).

---

## 1. Bộ CLI Quản Trị & Xuất Bản 1 Lệnh `tools/manage_kb.py`

| Lệnh quản trị | Chức năng tự động hóa |
|---|---|
| `python -B tools/manage_kb.py status` | Thống kê toàn bộ 10 miền, 162+ thẻ, 311 mục, 1.504+ phương trình, 1.163+ hình, 72+ SVG, 21+ checklists, 482+ cạnh & 52+ repo GitHub. |
| `python -B tools/manage_kb.py new-card <domain> <id> "<vi>" "<en>" --chapter <N>` | Sinh khung thẻ chuẩn 6 khối đúng JSON frontmatter trên bất kỳ miền nào trong 10 miền. |
| `python -B tools/manage_kb.py new-checklist <id> "<vi>" "<en>"` | Tạo khung bảng kiểm bất biến đa tiến trình mới trong `kb/checklists/`. |
| `python -B tools/manage_kb.py add-edge <from> <to> <rel> "<when>" "<cost>" "<ref>"` | Nối cạnh có hướng vào `kb/graph/edges.jsonl` (chống trùng lặp tự động). |
| `python -B tools/manage_kb.py add-term "<en>" "<vi>" --chapter <N>` | Cấp mã `Txxxx` kế tiếp và thêm thuật ngữ song ngữ chuẩn CLB vào `terms-vi-en.json`. |
| `python -B tools/manage_kb.py rebuild` | Khóa `.build.lock`, biên dịch `router-index.json` + `nodes-bundle.json.gz` + `kb/manifest.json` + `runtime/manifest.json`, chạy `validate_brain.py` và `analogctl.py verify`. |
| `python -B tools/manage_kb.py publish -m "<thông điệp>"` | Chạy trọn gói `rebuild` + kiểm định liên kết + `git commit` + `git push origin main` để phát hành OTA tức thì! |

---

## 2. Quy Trình Sửa Chữa / Thêm Kiến Thức Siêu Tốc Trên Windows Hoặc Trực Tiếp Trên GitHub

### Cách A — Sửa hoặc thêm thẻ từ Windows (`Codex Desktop` / `Antigravity Desktop`)
1. Sửa trực tiếp bất kỳ tệp thẻ `.md` nào trong `kb/nodes/<domain>/`, công cụ trong `runtime/tools/`, hoặc tạo thẻ mới bằng `manage_kb.py new-card ...`.
2. Xuất bản chỉ bằng **1 lệnh duy nhất**:
   ```bash
   python -B tools/manage_kb.py publish -m "fix(kb): cap nhat phuong trinh va checklist"
   ```
   - Trên Windows: cả `Codex Desktop` và `Antigravity Desktop` thấy bản mới trong **`0 ms`**.
   - Trên máy ảo RHEL 6.5: trong vòng **`60 giây`**, lần gọi `kb_lookup.py` / `kb_fetch.py` tiếp theo tự kéo commit SHA mới về qua staging nguyên tử!

### Cách B — Sửa nóng trực tiếp trên giao diện Web GitHub
- Nếu sửa nội dung thẻ `.md` trực tiếp trên GitHub, chạy `python -B /home/disk/eda/references/SKILL-ANALOG/tools/kb_fetch.py <node-id> --refresh` trên RHEL 6.5 (hoặc `git pull` + `python -B tools/manage_kb.py publish` trên Windows để đồng bộ lại băm `manifest.json` và gói `nodes-bundle.json.gz`).

---

## 3. Khởi Tạo / Nâng Cấp 1 Dòng Lệnh Duy Nhất Trên Máy Ảo RHEL 6.5 (Không Đụng Tới `.iso`)

Chạy đúng **1 dòng lệnh** dưới đây bên trong terminal máy ảo RHEL 6.5 để nâng cấp toàn bộ `/home/disk/eda/references/SKILL-ANALOG` lên bản `v4.0` (`2026.11.19.1`), tải đủ `72` sơ đồ SVG offline + `162` thẻ nén, đồng thời **tự động biên dịch lại cả hai bảng tra `GPDK090` và `GPDK045`** từ dữ liệu quét Spectre sẵn có:

```bash
curl -fsSL --cacert /home/disk/eda/apps/codex/support/mozilla-cacert.pem https://raw.githubusercontent.com/lmsang372k6-spec/razavi-cmos-brain/main/runtime/bootstrap_rhel6_ota.py | python -B -
```

- Kiểm tra trạng thái OTA cục bộ (`0` gọi mạng):
  ```bash
  python -B /home/disk/eda/references/SKILL-ANALOG/tools/analogctl.py ota-status
  ```
- Chế độ thi / kiểm toán cô lập hoàn toàn không mạng (`Strict Offline Lock`):
  ```bash
  SKILL_ANALOG_OFFLINE=1 python -B /home/disk/eda/references/SKILL-ANALOG/tools/kb_lookup.py search "gain boosted cascode" --offline
  ```
