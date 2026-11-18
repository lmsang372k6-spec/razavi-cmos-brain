# Quy trình thiết kế khép kín 7 bước theo chứng cứ & tối ưu Pareto

Mọi dự án trên RHEL 6.5 (`Python 2.6.6`, Virtuoso IC617, Spectre 15.1) đi theo **Chu trình Thiết kế Tối ưu Khép kín 7 Bước** (`design_cycle_stage` trong `project.json`), kết hợp bất biến cấu trúc lý thuyết với định cỡ `gm/ID` chính xác và tối ưu hóa độ nhạy có ràng buộc.

## Chu trình 7 bước bắt buộc (`1_spec_and_kb` → `7_pvt_mc_pex_signoff`)

1. **`1_spec_and_kb` — Định vị dự án, đọc đặc tả & tra cứu tri thức bất biến (`KB Lookup & Checklist`):**
   - Xác định dự án bằng `python -B tools/analogctl.py locate` (`project.json` hoặc `cds.lib`), phân giải symlink và dừng suy đoán nếu có nhiều `library/cell/view` hợp lệ.
   - Đọc `spec.json`: phân biệt rõ mục tiêu đã được người dùng phê duyệt (`approved`) với đề xuất nháp (`draft`). Không tự ý nới lỏng spec hoặc chấm `PASS` cho mục tiêu tự đặt.
   - Tra cứu `python -B tools/kb_lookup.py` (`search`, `coord`, `checklist`, `diagnose`, `upgrades`, `skills`) và `tools/kb_fetch.py <node_id>` để lấy phương trình thiết kế và bảng kiểm bất biến cấu trúc (`CHK-*`) theo [INDEX.md](INDEX.md) trước khi chọn kích thước transistor.

2. **`2_hierarchical_budget` — Phân rã kiến trúc đa khối, ngân sách đặc tả & hợp đồng giao tiếp (`Hierarchical Spec Budget`):**
   - Với IC đa khối (ví dụ PMIC Buck/Boost/Buck-Boost, Capless LDO kèm POR/UVLO/OCP/Soft-Start, PLL, SAR/$\Delta\Sigma$/Pipeline ADC, chuỗi lọc Active-RC/$G_m$-C + INA/CFIA), khai báo đồ thị khối `architecture.blocks[]` trong `project.json` (`cell`, `role`, `depends_on`, `active_view`: `"veriloga"` hoặc `"schematic"`, `signoff_status`) và phân bổ `subblock_budgets[]` (RSS nhiễu nhiệt $v_{n,\text{tot}}^2$, lệch áp Pelgrom $V_{OS}$, băng thông/dự trữ pha, dòng tĩnh $I_Q$) trong `spec.json`.
   - Khóa cứng hợp đồng giao tiếp liên khối `architecture.interfaces[]`: chiều chân (`pin_direction`), cửa sổ common-mode $V_{CM}$ và biên độ dao động, cực tính dòng phân cực ($I_{\text{sink}}$ / $I_{\text{source}}$ — cấm nối nhầm ngõ ra áp $V_{\text{bias}}$ vào ngõ nhận dòng $I_{\text{bias}}$), tách biệt trở kháng Middlebrook $|Z_{\text{out},k}| \le 0{,}1\,|Z_{\text{in},k+1}|$ trong băng thông làm việc, và dấu cực tính vòng hồi tiếp âm.

3. **`3_gmid_lut_sizing` — Định cỡ vật lý bằng bảng tra `gm/ID` của PDK (`gmid_lut.py Sizing`):**
   - Sử dụng [gpdk_techsweep.py](../tools/gpdk_techsweep.py) để sinh/biên dịch bảng `.lut.json.gz` chuẩn SOA (`1.2V`/`2.5V` cho GPDK090 `NN/SS/FF/FS/SF`; `1.0V`/`1.8V` cho GPDK045 `tt/ss/ff/fs/sf`) lưu tại `~/.cache/skill-analog/gmid-luts/` (tuyệt đối không ghi vào `SKILL-ANALOG`).
   - Chạy [gmid_lut.py](../tools/gmid_lut.py) (`tradeoff`, `query`, `size`) theo [gm-id.md](gm-id.md) để chọn điểm tối ưu `(gm/ID, L)` cho từng vai trò transistor (`gm/ID = 16..20 V^-1` cho cặp vi sai đầu vào nhiễu/offset thấp; `11..15 V^-1` cho tầng đệm/cascode cao tần; `7..10 V^-1` + `L` dài cho gương dòng $r_o$ lớn và khớp Pelgrom tốt), suy ra `id_a`, số ngón chẵn `nf >= 2`, `w_finger_m` làm tròn lưới `5nm`, `ro_ohm`, `cgg_f` và `vds_min`. Giữ nhãn `estimated` cho tới khi có kết quả mô phỏng Spectre.

4. **`4_schematic_and_veriloga` — Dựng Schematic/Symbol OA & Mô hình Hành vi Hỗn hợp (`Schematic / Verilog-A Build`):**
   - Kiểm tra/dựng schematic và symbol trên Virtuoso IC617 qua cầu nối phiên mở trực tiếp `tools/ic617_client.py` (tránh xung đột khóa `.cdslck` và không tốn thêm license) hoặc chạy batch an toàn qua `tools/cadence_exec.py` + `tools/ic617_oa_cdf.il` theo [ic617-adapters.md](ic617-adapters.md).
   - Với hệ thống đa khối, kiểm chứng khung hệ thống từ trên xuống bằng `active_view = "veriloga"` rồi thay thế từng khối từ dưới lên bằng `"schematic"`.
   - Đặc biệt với nguồn chuyển mạch DC-DC (Buck, Boost, Inverting Buck-Boost), dùng mô hình công tắc trung bình 3 cực không trạng thái ẩn [pwm_switch_avg_ccm_dcm.va](../models/veriloga/pwm_switch_avg_ccm_dcm.va) để chạy `.dc`, `.ac`, `.stb` hội tụ trong `< 0.3s` (tự động tái hiện tỷ số truyền CCM/DCM, cực kép $LC$ và RHP zero phụ thuộc tải) nhằm tổng hợp mạng bù Type-II / Type-III / Slope-Comp trước khi đóng vòng MOSFET chuyển mạch.

5. **`5_op_and_stb_audit` — Mô phỏng Spectre Baseline, Kiểm toán Điểm làm việc OP & Độ ổn định (`cadence_exec + psf_audit`):**
   - Định nghĩa testbench và hợp đồng phép đo theo [measurement-rules.md](measurement-rules.md) trước khi tối ưu.
   - Chạy Spectre 15.1 (`-format psfascii`) lưu riêng vào `sim/runs/<run-id>/` qua `tools/cadence_exec.py`.
   - Chạy `tools/psf_audit.py op-audit` để kiểm tra vùng hoạt động của toàn bộ MOSFET (`region == 2` bão hòa trừ các transistor chủ đích làm công tắc/điện trở triode) cùng dự trữ thế bão hòa $|V_{DS}| - |V_{DS,\text{sat}}| \ge 50\text{ mV}$, và chạy `tools/psf_audit.py metrics --spec spec.json` để trích xuất DC/AC/STB/Tran/Noise. Tách biệt lỗi hội tụ/netlist với lỗi chưa đạt chỉ tiêu thiết kế.

6. **`6_sensitivity_pareto_opt` — Ma trận Độ nhạy Jacobian & Tối ưu Hóa Pareto Có Ràng buộc (`sizing_opt.py`):**
   - Khi thiết kế baseline lệch chỉ tiêu do hiệu ứng bậc hai (DIBL, điện dung ký sinh nút trong, tương tác cực–zero Miller/$R_z$) hoặc tiêu thụ thừa công suất, lập bài toán JSON cho [sizing_opt.py](../tools/sizing_opt.py).
   - **Giai đoạn 1 (Sensitivity Jacobian):** Tính đạo hàm logarit hữu hạn $\frac{\partial \text{Metric}_i}{\partial \ln x_j}$ để chỉ rõ chính xác biến `W`, `L`, `I_bias`, `C_c`, `R_z` nào chi phối từng thông số đang `FAIL` và cắt tỉa các biến vô cảm.
   - **Giai đoạn 2 (Constrained Trust-Region + Subspace Nelder-Mead):** Tối ưu hàm phạt–rào cản trong không gian chuẩn hóa logarit để đạt đồng thời 100% ràng buộc cứng + dự trữ bão hòa MOS $\ge 50\text{ mV}$ đồng thời cực tiểu hóa công suất/diện tích (hoặc cực đại hóa FoM), tự động làm tròn kích thước về lưới chế tạo PDK (`5nm`) và đối chiếu góc PVT (`TT`, `SS`, `FF`).

7. **`7_pvt_mc_pex_signoff` — Nghiệm thu Góc PVT, Nhiễu Mismatch Monte Carlo & Hậu Layout PEX (`PVT + MC + PEX Signoff`):**
   - Mở rộng kiểm chứng trên toàn bộ ma trận góc PVT (`SS`, `FF`, `FS`, `SF`, biên nguồn $V_{DD}\pm\Delta$, dải nhiệt độ $-40^\circ\text{C} \dots 125^\circ\text{C}$), thống kê Monte Carlo mismatch/process (ghi rõ số mẫu, seed và độ tin cậy yield), và mô phỏng extracted hậu layout (DRC/LVS/PEX).
   - Với mạch nguồn chuyển mạch PWM thực, bắt buộc khóa nghiệm thu vòng kín bằng SpectreRF `pss` + `pstb` (`stop = 0.49*f_sw`, đặt `iprobe` trên nhánh tương tự liên tục trước cầu hồi tiếp, **cấm đặt `iprobe` trên dây xung số PWM**) kèm quá độ nhảy tải `.tran` (`I_min <-> I_max`).
   - Mọi thông số chưa chạy đủ điều kiện hoặc thiếu artifact vẫn mang trạng thái `NOT VERIFIED`; tuyệt đối không lấy kết quả `TT` đại diện cho PVT hay lấy ước lượng thế chỗ cho đo đạc mô phỏng.

## Cấu trúc lưu trữ dự án & kỷ luật bất biến

- `design/`: thư viện OpenAccess / DUT (đối chiếu đường dẫn thực trong `cds.lib` và CDF).
- `netlists/`: netlist nguồn hoặc netlist xuất từ schematic được gắn nhãn rõ ràng.
- `scripts/`: kịch bản runner, bộ sinh bài toán `sizing_opt` và hàm trích xuất chỉ tiêu của dự án.
- `sim/runs/<run-id>/`: lưu trọn bộ snapshot tham số, mã băm `spec.json`, netlist, log Spectre và dữ liệu PSF ASCII. Không ghi đè run đã trích dẫn làm bằng chứng.
- `sim/logs/`, `docs/`, `exports/`: nhật ký điều phối, phân tích lý thuyết/bảng `tradeoff`, và báo cáo xuất bản.
- `STATE.md`: cập nhật ngắn gọn `design_cycle_stage`, tiến độ từng khối trong `architecture.blocks[]`, run tốt nhất và bước tiếp theo; không lưu thông tin mật hay hội thoại thô.
- Thư viện `/home/disk/eda/references/SKILL-ANALOG` là **chỉ đọc tuyệt đối** khi vận hành: mọi socket IPC, bảng `.lut.json.gz` và thư mục chạy tạm phải nằm trong dự án, `~/.cache/skill-analog/` hoặc `/tmp/`.
