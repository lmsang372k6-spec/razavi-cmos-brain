# SKILL-ANALOG (`2026.11.19.1`)

Thư viện tra cứu, **Bộ não Tri thức 162 Thẻ (CMOS Razavi Ch.01–Ch.19 + Quản lý Nguồn PMIC + Tín hiệu Hỗn hợp AMS + Kỹ năng Thực chiến GitHub)** định tuyến tọa độ trực tiếp lên GitHub (https://github.com/lmsang372k6-spec/razavi-cmos-brain | https://lmsang372k6-spec.github.io/razavi-cmos-brain) và **Chu trình Thiết kế Tối ưu Khép kín 7 Bước** cho Codex CLI trên Cadence Virtuoso IC617 / Spectre 15.1. Bản đang dùng trong RHEL đặt tại `/home/disk/eda/references/SKILL-ANALOG`; dữ liệu dự án đặt riêng tại `/home/disk/eda/projects/cadence/<tên>/`.

## Dùng hằng ngày

Mở thư mục dự án → **Open in Terminal** → `codex`. Với dự án mới: `eda new TEN`, rồi `eda ai TEN`. Bạn có thể yêu cầu bằng tiếng Việt hoặc tiếng Anh cho cả mạch cơ sở Razavi, nguồn xung PMIC (`Buck`, `Boost`, `4-Switch Buck-Boost`, `Capless LDO`, `POR/UVLO/OCP`) lẫn hệ thống AMS (`INA/Chopper CFIA`, `Active-RC Tow-Thomas`, `Gm-C`, `Segmented DAC`, `Delta-Sigma / Pipelined ADC`), hoặc yêu cầu chạy chu trình tối ưu kích thước theo `spec.json`.

Mở Virtuoso: `eda open TEN` hoặc `cadence TEN`. Khi đang mở cửa sổ Virtuoso GUI và muốn Codex đọc/cập nhật trực tiếp không đụng khóa `.cdslck`, nạp 1 dòng trong CIW: `(load "/home/disk/eda/references/SKILL-ANALOG/tools/ic617_live_bridge.il")`.

## Cấu trúc và trách nhiệm

| Nơi | Nội dung |
|---|---|
| `skills/analog-design/` | Skill gốc duy nhất tích hợp **Chu trình Thiết kế Tối ưu Khép kín 7 Bước** ([SKILL.md](skills/analog-design/SKILL.md)) |
| `kb/` | Cấu hình định tuyến GitHub (`config.json`), chỉ mục **162 thẻ / 10 tầng** (`router-index.json`), tọa độ sách (`coordinates/book-coordinates.json`), **52 kho GitHub** (`github-skills/catalog.json`), **482 cạnh** (`edges.jsonl`), **21 `checklists/`**, **2.280 thuật ngữ CLB** (`terms-vi-en.json`) & gói dự phòng ngoại tuyến `nodes-bundle.json.gz` (xem [kb/README.md](kb/README.md)) |
| `tools/kb_lookup.py`, `tools/kb_fetch.py` | Bộ định tuyến `< 15 ms` (`status`, `coord`, `skills`, `stage`, `search`, `diagnose`, `upgrades`, `chapter`, `checklist`, `term`), đồng bộ 26 tệp từ GitHub (`--sync`) & đầu kéo thẻ 6 khối lai Online/Offline |
| `tools/gpdk_techsweep.py`, `tools/gmid_lut.py`, `tools/sizing_opt.py` | Bộ quét đặc tuyến GPDK090/045 chuẩn SOA, nội suy `gm/ID` PCHIP `< 5 ms` (`query`, `size`, `tradeoff`) và bộ tối ưu **Sensitivity Jacobian + Log Trust-Region / Nelder-Mead** (`Python 2.6.6` stdlib) |
| `tools/ic617_live_bridge.il`, `tools/ic617_client.py`, `tools/cadence_exec.py`, `tools/ic617_oa_cdf.il` | Cầu nối socket phiên Virtuoso GUI sống, trình chạy an toàn `spectre`/`ocean`/`virtuoso-batch`/`si` có kiểm khóa `.cdslck`, và thư viện SKILL OA/CDF/JSON/Plan không xóa hủy diệt |
| `tools/psf_ascii_reader.py`, `tools/psf_audit.py` | Máy trạng thái đọc Spectre 15.1 PSF ASCII (`STRUCT` BSIM4, `TRACE GROUP`, delta-compression, phức `stb`) & kiểm toán tự động `op-audit` + `metrics --spec` |
| `models/veriloga/pwm_switch_avg_ccm_dcm.va` | Mô hình Verilog-A công tắc trung bình 3 cực CCM/DCM trơn $C^\infty$, 0 trạng thái ẩn cho Buck/Boost/Buck-Boost |
| `templates/cadence-project/` | Mẫu dự án đa khối (`architecture.blocks[]`, `interfaces[]`, `design_cycle_stage`, `subblock_budgets[]`, `optimization`) |
| `references/`, `environment/rhel6-ic617/`, `sources/` | Hướng dẫn theo tác vụ ([references/INDEX.md](references/INDEX.md)), tương thích máy chủ và 261 tệp nguồn tham khảo khóa cứng trong `sources.lock.json` |
| `tools/analogctl.py`, `tools/check_references.py` | Xác minh SHA-256 toàn kho (`verify`), kiểm tra liên kết tài liệu, chẩn đoán môi trường (`doctor`) và khởi tạo metadata dự án (`init`/`locate`) |

Liên kết thiếu trong source trích chọn được tra qua [SOURCE-LINKS](references/SOURCE-LINKS.md). Liên kết discovery của Codex:

```text
/home/work/.agents/skills/analog-design
  -> /home/disk/eda/references/SKILL-ANALOG/skills/analog-design
$CODEX_HOME/AGENTS.md
  -> /home/disk/eda/references/SKILL-ANALOG/integration/codex-user-AGENTS.md
```

## Quản lý chặt chẽ

- Spec mới để trạng thái `draft`; chỉ chỉ tiêu bạn phê duyệt mới dùng để kết luận `PASS` / `FAIL`, thiếu dữ liệu là `NOT VERIFIED`.
- Thư viện `/home/disk/eda/references/SKILL-ANALOG` giữ bất biến tuyệt đối khi chạy: mọi socket IPC, bảng `.lut.json.gz`, cache đồng bộ GitHub và kết quả mô phỏng đều đặt ở thư mục dự án, `~/.cache/` hoặc `/tmp/`.

Kiểm tra integrity: `python -B /home/disk/eda/references/SKILL-ANALOG/tools/analogctl.py verify`. Kiểm tra liên kết tài liệu: `python -B /home/disk/eda/references/SKILL-ANALOG/tools/check_references.py`. Xem chi tiết phát hành tại [INSTALLATION.md](INSTALLATION.md).
