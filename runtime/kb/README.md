# Bộ Định tuyến Tri thức CMOS Razavi, PMIC, AMS & Chu trình Tối ưu Cadence/GitHub (`library/kb/`)

Thư mục này kết nối trực tiếp Codex trên máy ảo RHEL 6.5 với **Bộ não Tri thức CMOS Razavi + PMIC + AMS + Kỹ năng Khép kín Cadence/GitHub (`2026.11.19.1`)** trên GitHub, đồng thời tích hợp sẵn bộ chỉ mục tọa độ sách chính xác, danh mục 52 kho kỹ năng EDA đã kiểm định và gói dự phòng ngoại tuyến 100%:

- **Kho GitHub chính thức:** https://github.com/lmsang372k6-spec/razavi-cmos-brain
- **Bản đồ Tri thức Tọa độ 2D (22 cột, 10 tầng) & Static API:** https://lmsang372k6-spec.github.io/razavi-cmos-brain
- **Endpoint Raw tức thì:** https://raw.githubusercontent.com/lmsang372k6-spec/razavi-cmos-brain/main

## Thành phần cục bộ trong `library/kb/` (`100` tệp KB đồng bộ + `config.json` & `README.md`)

- `config.json`: cấu hình sẵn `base_url` (GitHub Pages), `raw_base_url` (Raw GitHub), danh sách gói chứng chỉ CA mới trên RHEL 6.5 (`mozilla-cacert.pem`) và cơ chế lưu đệm bên ngoài thư viện (`~/.cache/razavi-cmos-brain` hoặc `/tmp/razavi-brain-cache-*`) để `analogctl.py verify` luôn sạch tuyệt đối.
- `router-index.json`: chỉ mục **162 thẻ 6 khối** xuyên suốt **10 tầng tri thức** (**112 thẻ nguyên lý Razavi** Ch.01–Ch.19 + **12 thẻ Quản lý Nguồn PMIC** Buck/Boost/4-Switch Buck-Boost/SC Charge-Pump/Capless LDO/POR-UVLO-OCP-TSD + **12 thẻ Hệ thống Tín hiệu Hỗn hợp AMS** Schmitt/RC-Pierce Osc/INA-Chopper CFIA/Active-RC Tow-Thomas/$G_m$-C/DAC/$\Delta\Sigma$/Pipeline MDAC/LVDS-CTLE-CDR/Central `I_PTAT`-`I_ZTC` Bias Hub + **26 thẻ tầng EDA**; tổng cộng **27 thẻ kỹ năng thực chiến `skill-*`**), tọa độ 2D không chồng lấn trên 22 cột (`coord_2d`), ánh xạ **Chu trình Thiết kế 7 Bước (`design_stages`)**, **72 sơ đồ vector SVG** và ánh xạ triệu chứng $\to$ cấu trúc mạch.
- `coordinates/book-coordinates.json`: chỉ mục tọa độ chính xác từ 20 tệp PDF sách gốc Razavi 2nd Ed. gồm **19 chương**, **311 mục (`§1.1`..`§19.4`)**, **1.504 phương trình (`Eq. 2.1`..`Eq. 19.27`)**, **1.163 hình vẽ (`Fig. 1.1`..`Fig. 19.75`)** và **423 mục từ tra cứu `20_Index`** kèm số trang sách, số trang PDF và ánh xạ thẳng sang `node_id`.
- `github-skills/catalog.json`: danh mục **52 kho mã nguồn mở Analog IC / PMIC / AMS / Cadence / Spectre / EDA** trên GitHub đã kiểm định commit khóa cứng 40 ký tự, giấy phép SPDX và hướng dẫn tương thích thực tế với Cadence IC617 + Spectre 15.1 trên RHEL 6.5 (`Python 2.6.6`).
- `edges.jsonl`: đồ thị có hướng **482 cạnh** mô tả chuỗi nâng cấp mạch (`upgrades_to`), sửa lỗi (`fixes`), bù tần số (`compensated_by`), đánh đổi (`trades_off_with`), điều kiện bắt buộc (`requires`), quy luật chi phối (`governed_by`) và ràng buộc vật lý (`layout_constrained_by`).
- `checklists/`: **21 bảng kiểm cấu trúc bất biến** áp dụng cho mọi tiến trình (`180nm`, `90nm`, `65nm`, `45nm`), bao gồm mới `dcdc-switching-converter` (`CHK-DCDC-01..10`), `ldo-regulator` mở rộng (`CHK-LDO-01..10`), `continuous-time-filters` (`CHK-CTF-01..09`), `dac-and-deltasigma-adc` (`CHK-CNV-01..09`), `system-integration-por-and-bias-bus` (`CHK-SYS-01..10`) và `closed-loop-sizing-and-signoff` (`CHK-OPT-01..08`).
- `terms-vi-en.json`: **2.280 thuật ngữ song ngữ Anh–Việt chuẩn CLB** (`T001–T2280`, bổ sung 80 thuật ngữ chuyên sâu PMIC, AMS và Tối ưu hóa Khép kín Cadence).
- `nodes-bundle.json.gz`: gói snapshot nén toàn bộ **162 thẻ 6 khối** giúp [kb_fetch.py](../tools/kb_fetch.py) trích xuất trọn vẹn ngay cả khi máy ảo RHEL 6.5 ngoại tuyến (`< 15 ms` khi đọc trực tiếp SSOT / trong tiến trình ấm; `~150–220 ms` cho mỗi lần gọi CLI lạnh qua tiến trình con trên RHEL 6.5 Python 2.6.6 do khởi động trình thông dịch và giải nén gói gzip).

## Lệnh tra cứu tọa độ, PMIC/AMS, kỹ năng Cadence & đồng bộ OTA từ GitHub (Python 2.6.6 & Python 3)

```bash
# 0. Kiểm tra trạng thái kết nối GitHub & đồng bộ 100 tệp KB vào ~/.cache/razavi-cmos-brain (+ cập nhật nguyên tử 150 tệp SSOT trong library/ khi có quyền ghi; thêm --no-library-update nếu chỉ ghi cache)
python -B /home/disk/eda/references/SKILL-ANALOG/tools/kb_lookup.py status
python -B /home/disk/eda/references/SKILL-ANALOG/tools/kb_fetch.py --sync
python -B /home/disk/eda/references/SKILL-ANALOG/tools/kb_fetch.py --sync --no-library-update

# 1. Tra cứu TỌA ĐỘ SÁCH CHÍNH XÁC theo Mục (§), Phương trình (Eq.), Số trang hoặc 20_Index
python -B /home/disk/eda/references/SKILL-ANALOG/tools/kb_lookup.py coord "9.2"
python -B /home/disk/eda/references/SKILL-ANALOG/tools/kb_lookup.py coord "§12.3"
python -B /home/disk/eda/references/SKILL-ANALOG/tools/kb_lookup.py coord "Eq. 10.25"
python -B /home/disk/eda/references/SKILL-ANALOG/tools/kb_lookup.py coord "page 356"

# 2. Tìm kiếm nhanh PMIC, AMS & Công cụ Chu trình Khép kín Cadence IC617
python -B /home/disk/eda/references/SKILL-ANALOG/tools/kb_lookup.py search "4-switch buck-boost"
python -B /home/disk/eda/references/SKILL-ANALOG/tools/kb_lookup.py search "capless ldo"
python -B /home/disk/eda/references/SKILL-ANALOG/tools/kb_lookup.py search "current steering dac"
python -B /home/disk/eda/references/SKILL-ANALOG/tools/kb_lookup.py skills "sizing_opt"
python -B /home/disk/eda/references/SKILL-ANALOG/tools/kb_lookup.py stage list

# 3. Xem 21 bảng kiểm bất biến, chẩn đoán triệu chứng lỗi, lộ trình nâng cấp & 2.280 thuật ngữ CLB
python -B /home/disk/eda/references/SKILL-ANALOG/tools/kb_lookup.py checklist dcdc-switching-converter
python -B /home/disk/eda/references/SKILL-ANALOG/tools/kb_lookup.py diagnose "rhp zero"
python -B /home/disk/eda/references/SKILL-ANALOG/tools/kb_lookup.py upgrades topo-cascode-current-mirror
python -B /home/disk/eda/references/SKILL-ANALOG/tools/kb_lookup.py term "slope compensation"

# 4. Đọc toàn bộ thẻ 6 khối trực tiếp từ GitHub + dự phòng offline (< 15 ms trong tiến trình ấm / đọc trực tiếp SSOT; ~150–220 ms CLI lạnh trên RHEL 6.5 Python 2.6.6)
python -B /home/disk/eda/references/SKILL-ANALOG/tools/kb_fetch.py topo-boost-inverting-and-4switch-buckboost
python -B /home/disk/eda/references/SKILL-ANALOG/tools/kb_fetch.py skill-closed-loop-sizing-and-pareto-optimization --offline
```

Xem quy trình Chu trình Thiết kế Tối ưu Khép kín 7 Bước tại [SKILL.md](../skills/analog-design/SKILL.md), [design-flow.md](../references/design-flow.md) và [INDEX.md](../references/INDEX.md).
