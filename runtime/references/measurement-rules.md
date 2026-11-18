# Hợp đồng phép đo và kết luận

Mỗi requirement cần có ID ổn định. Trước khi đánh giá, xác định đại lượng, operator, target/unit, nguồn target được người dùng chấp thuận và các điều kiện đo. Nếu spec chỉ có tên chung như “bandwidth” hoặc “noise”, làm rõ định nghĩa trước khi chấm.

## Bản ghi tối thiểu cho mỗi kết quả

Lưu requirement ID; giá trị và đơn vị; trạng thái; analysis/TB/DUT; node/polarity; stimulus, supply, bias/common mode, load; PDK/model section/corner/temperature; thời gian hoặc dải tần đo; phiên bản netlist và script extractor; đường dẫn raw/log; run ID. Lưu thêm seed/sample count nếu có ngẫu nhiên. Các path dùng trong evidence phải chỉ tới artifact của chính run đó.

Status: `PASS` hoặc `FAIL` chỉ khi phép đo hợp lệ và có target đã chấp thuận (`approval` không ở trạng thái `pending` / `draft` / `unapproved`); `NOT_VERIFIED` khi thiếu dữ liệu/target/góc PVT bắt buộc (`missing_condition`), thiếu trường điểm làm việc MOSFET (`MISSING_OP_FIELDS`), tệp PSF bị cắt cụt thiếu `END`, hoặc đơn vị không hợp lệ (`INVALID_UNIT`); `INVALID` khi run/phép đo vi phạm điều kiện valid. Với `--fail-on-spec`, mọi kết luận khác `PASS` (kể cả `FAIL` và `NOT_VERIFIED`) đều phải trả mã thoát `1`.

Chuẩn hóa đơn vị một lần ở biên extractor (`UNIT_SCALE_TO_SI` kiểm tra nghiêm ngặt, từ chối mọi đơn vị viết sai chính tả thay vì ngầm nhân `1.0`), giữ cả giá trị gốc/unit gốc và dùng dung sai tương đối `1e-12 * max(|target_si|, 1e-30)` (để các đại lượng pico-giây/femto-farad như `1.1 ps <= 1 ps` không bao giờ lọt qua). Báo điều kiện worst case và kết quả từng góc PVT (`TT`, `SS`, `FF`, `FS`, `SF`); không lấy kết quả một góc `TT` để kết luận `PASS` khi spec yêu cầu nhiều góc.

## Theo loại phép đo

- **Điểm làm việc MOSFET (`op-audit`) & SOA theo họ mô hình (`BSIM3v3` vs `BSIM4`):** mỗi MOSFET phải có đủ `vdsat` và `region` (hoặc `vgs, vth`); thiếu dữ liệu buộc chấm `NOT_VERIFIED` (`audit_pass: false`). Thiết bị khuếch đại/nguồn dòng có `0 <= |VDS| - |Vdsat| < vds_margin` không được chấm `audit_pass: true`. Kiểm tra giới hạn SOA đa cực theo đúng PDK: **`GPDK090` dùng BSIM3v3** (`1.2 V` core: `|VGB|, |VDB| <= 1.32 V`; `2.5 V` IO: `<= 2.75 V`; không phát `nf` trực tiếp cho Spectre primitive) còn **`GPDK045` dùng BSIM4** (`1.0 V` core: `|VGB|, |VDB| <= 1.1 V`; `1.8 V` IO: `<= 1.98 V`; hỗ trợ `nf` trực tiếp).
- **DC/gain/swing/ICMR:** nêu điểm bias, phương pháp sweep và điều kiện tuyến tính hợp lệ. Phân biệt small-signal gain với large-signal transfer; khi ràng buộc có cả `min` và `max`, kiểm tra bao hàm cả hai biên (`op = "range"`).
- **AC/bandwidth:** nêu transfer và chuẩn hóa (single ended/differential, input/output). Xác định bandwidth so với mức nào, tìm crossing đúng nhánh và báo nhiều crossing nếu có. Không dùng tần số cuối sweep khi chưa tìm thấy crossing.
- **Loop stability (`.stb` / `.pstb`):** xác định loop, điểm probe, polarity và return-ratio convention; giữ bias và loading khi mở loop. Chỉ tiêu `pm` / `phase_margin` / `phase_margin_deg` **bắt buộc** lấy từ phân tích `.stb` hoặc `.pstb` (tuyệt đối không lấy pha `.ac` hở mạch `pm_ac_deg` thay thế!). Quét **mọi** vòng lặp trong thư mục chạy (ví dụ cả `dm.stb` lẫn `cmfb.stb`, lấy worst-case) và kiểm tra **mọi** điểm cắt pha đã trải (`unwrapped`) tại `-(180° + 360°k)` để phát hiện biên độ vượt `0 dB` ở `-540°`.
- **Transient/settling/slew:** nêu step amplitude, rise/fall, initial conditions, clock và load. Settling đòi hỏi một vùng bình nguyên xác lập thực sự ở cuối cửa sổ (`max - min <= tol` và độ dốc đuôi nhỏ hơn hẳn độ dốc bước — một sườn dốc tuyến tính chưa chạm đích phải trả `settling_time_s = null`). Với xung hai sườn (lên và xuống), nếu bất kỳ sườn nào chưa xác lập thì `settling_time_s` tổng thể phải là `null`.
- **Noise:** ghi input/output referred, PSD (`V^2/Hz`, `A^2/Hz`) hay ASD (`V/sqrt(Hz)`, `A/sqrt(Hz)`), single/double sided và băng tần tích phân. Tách bạch tuyệt đối nhiễu điện áp đầu ra/quy đổi đầu vào (`integrated_rms_noise_v`) với nhiễu dòng điện (`integrated_rms_noise_a`); không bao giờ gán phổ dòng `A/sqrt(Hz)` vào trường điện áp `integrated_rms_noise_v`.
- **Power:** ghép từng nguồn áp DC (`VDD`, `AVDD`, `VDD18`...) với đúng nhánh dòng nguồn tương ứng để cộng `sum(|V_k * I_k|)` thành `dc_power_w` (nếu còn nhánh dòng nguồn không khớp được điện áp thì để `dc_power_w = null`, tuyệt đối không nhân chéo nhầm nguồn; tổng ước lượng trên các MOSFET lưu riêng ở `mos_power_estimate_w`). Công suất tĩnh DC không thay thế công suất chuyển mạch trung bình chu kỳ.
- **CMRR/PSRR:** nêu perturbation nguồn nào, normalized transfer, common/differential output, tần số/băng và magnitude convention. Chưa định nghĩa transfer thì chưa so con số dB.
- **Monte Carlo/yield:** ghi loại biến thiên model được hỗ trợ, seed, số mẫu, tiêu chí pass, failures và cách xử lý run invalid. Sample yield cần nêu sample count/uncertainty; zero failure không chứng minh yield tuyệt đối.
- **ADC:** theo [models-and-adc.md](models-and-adc.md); không bỏ missing codes/overflow hoặc thay raw bằng calibrated để chấm raw spec.

Một báo cáo nghiệm thu phải nói rõ schematic/nominal/PVT/mismatch/extracted/hardware. DRC/LVS hoặc mô phỏng một testbench không chứng minh mọi yêu cầu analog đã đạt.
