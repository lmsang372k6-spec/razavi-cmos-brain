# Phương pháp định cỡ gm/ID, bảng tra PDK & tối ưu hóa trên RHEL 6.5

Nguồn phương pháp luận nền tảng: Boris Murmann (`bmurmann/Book-on-gm-ID-design` trong lockfile). Do guest RHEL 6.5 chỉ có `/usr/bin/python` `2.6.6` (không có `numpy`/`scipy`/`h5py` nên không chạy trực tiếp được `dreoilin/pygmid`), `SKILL-ANALOG` cung cấp chuỗi công cụ chuẩn thư viện chuẩn Python 2.6.6+ gồm [gpdk_techsweep.py](../tools/gpdk_techsweep.py), [gmid_lut.py](../tools/gmid_lut.py) và [sizing_opt.py](../tools/sizing_opt.py).

## 1. Tạo bảng tra `.lut.json.gz` an toàn bằng `gpdk_techsweep.py`

Trước khi dùng bất kỳ LUT nào, bắt buộc kiểm tra `provenance`: tên/phiên bản PDK, đường dẫn và SHA-256 của tệp model Spectre, `section` góc công nghệ đúng chữ hoa/thường (`GPDK090`: `NN, SS, FF, FS, SF`; `GPDK045`: `tt, ss, ff, fs, sf`), loại linh kiện, nhiệt độ Celsius, kích thước tham chiếu `W_ref`/`nf` và quy ước dấu. Xem chi tiết hợp đồng dữ liệu tại [gpdk-characterization.md](gpdk-characterization.md).

Công cụ [gpdk_techsweep.py](../tools/gpdk_techsweep.py) đã khắc phục triệt để cả **4 lỗi nghiêm trọng của upstream `pygmid`**:
1. Chuẩn hóa tên tín hiệu PSF ASCII giữa dấu hai chấm và dấu chấm (`mn:ids` $\leftrightarrow$ `mn.ids`) kèm hỗ trợ `TRACE GROUP` và quy ước độ lớn/cực tính PMOS nhất quán.
2. Áp trần điện áp an toàn SOA cứng theo từng dòng linh kiện (`1.2V` cho `gpdk090_nmos1v`/`pmos1v`, `2.5V` cho IO `2v`; `1.0V` cho `g45n1svt`/`g45p1svt`, `1.8V` cho IO `g45*2*` — chặn lỗi quét `1.8V` làm thủng model 1V) và ghi trực tiếp độ C `temp=27.0` thay vì `300 - 273.15 = 26.85C`.
3. Kiểm tra chặt mã thoát Spectre (`returncode == 0`), lỗi `FATAL`/`ERROR` trong `spectre.out`, đủ số tệp lưới `(L, VSB, VDS)` và tính hữu hạn (`not NaN/Inf`) trước khi đóng gói — tuyệt đối không nuốt lỗi trả mảng `0.0`.
4. Tách riêng mật độ phổ nhiễu nhiệt kênh dẫn (`STH`: `mn:id`) và nhiễu nhấp nháy $1/f$ (`SFL`: `mn:fn`) trên hai nhánh đo độc lập `vnoi_n` / `vnoi_p`.

Các lệnh chuẩn (mọi tệp `.lut.json.gz` mặc định lưu tại `~/.cache/skill-analog/gmid-luts/`, không bao giờ chạm thư mục thư viện):
- Sinh bộ netlist quét để kiểm tra trước:
  `python -B tools/gpdk_techsweep.py --generate-deck --pdk gpdk090 --flavor core --corner NN --work-dir /tmp/sweep_gpdk090_nn`
- Chạy Spectre 15.1 (`-format psfascii`) và biên dịch LUT thực tế:
  `python -B tools/gpdk_techsweep.py --run --pdk gpdk090 --flavor core --corner NN`
- Sinh LUT giải tích EKV/BSIM4 đa chiều `L` để tự kiểm thử ngoại tuyến (offline demo/CI, không dùng thay signoff silicon):
  `python -B tools/gpdk_techsweep.py --generate-demo-lut /tmp/demo_gpdk090.lut.json.gz --pdk gpdk090 --corner NN`

## 2. Nội suy PCHIP `< 5 ms` và định cỡ linh kiện bằng `gmid_lut.py`

Công cụ [gmid_lut.py](../tools/gmid_lut.py) thực hiện nội suy đa tuyến tính 3 chiều `(L, VDS, VSB)` kết hợp spline bậc ba đơn điệu bảo toàn hình dạng Fritsch–Carlson (`PCHIP`) trên nhánh hoạt động của `gm/ID` (và nội suy trên $\ln J_D$ để giữ độ chính xác $< 0{,}1\%$ suốt từ vùng đảo yếu tới đảo mạnh) trong `< 1 ms`:

- **Khảo sát mặt biên đánh đổi Pareto `(gm/ID, L) -> (gm*ro, fT, JD, Vdsat)`:**
  `python -B tools/gmid_lut.py tradeoff --lut <path> --dev nmos --l-list 90e-9,180e-9,360e-9 --gm-id-range 8,22 --vds 0.6`
  *Nguyên tắc chọn vùng làm việc theo vai trò vật lý:*
  - **Cặp vi sai đầu vào (OTA / Comparator / LDO EA / INA):** Chọn vùng đảo trung bình–yếu (`gm/ID = 16..20 V^-1`) để cực đại hóa $g_m$ trên mỗi microamp dòng tĩnh, giảm nhiễu nhiệt đầu vào $v_n^2 \propto 1/g_m$ và giảm lệch áp $V_{OS} = \Delta V_{TH} + \frac{I_D}{g_m}\frac{\Delta\beta}{\beta}$.
  - **Tầng đệm cao tần, Cascode hoặc Driver:** Chọn vùng đỉnh tích `gm/ID * fT` (`gm/ID = 11..15 V^-1`, `L` ngắn vừa đủ đạt $g_m r_o$).
  - **Gương dòng & Nguồn dòng tải chủ động:** Chọn vùng đảo mạnh (`gm/ID = 7..10 V^-1`) kết hợp `L` dài (`2..5x L_min`) để tăng trở kháng ra $r_o$ và giảm sai lệch dòng $\frac{\sigma(I_D)}{I_D} \propto \frac{g_m}{I_D}\sigma(V_{TH})$.

- **Tra cứu điểm làm việc đơn lẻ (`query`):**
  `python -B tools/gmid_lut.py query --lut <path> --dev nmos --l 180e-9 --gm-id 15 --vds 0.6 --vsb 0.0`
  Trả về `jd_a_per_m`, `gm_gds`, `intrinsic_gain_db`, `ft_hz`, `vgs`, `signed_vgs`, `vdsat`, `vth`, `cgg_f_per_m`, `cgd_cgg`, `cdd_cgg`, `gamma_thermal`, `fco_flicker_hz`.

- **Định cỡ hình học hoàn chỉnh cho layout đối xứng (`size`):**
  `python -B tools/gmid_lut.py size --lut <path> --dev nmos --gm 1e-3 --gm-id 15 --l 180e-9 --vds 0.6 --w-finger-max 5e-6`
  Tự động tính `id_a = gm / (gm/ID)`, tổng bề rộng lý tưởng `W = ID / JD`, ép số ngón **`nf` chẵn `>= 2`** (phục vụ ghép đan xen / common-centroid), làm tròn `w_finger_m` và `l_m` theo lưới chế tạo `5nm`, và dự báo `ro_ohm`, `intrinsic_gain_db`, `cgg_f`, `cdd_f` cùng ngưỡng `vds_min = vdsat + 50mV`.

## 3. Kiểm chứng CDF/OP thực tế & khép vòng tối ưu bằng `sizing_opt.py`

1. Kiểm tra cách CDF của PDK diễn giải `w` (bề rộng mỗi finger hay tổng `w_total`) trong netlist Spectre xuất ra trước khi nạp tham số; giữ đầy đủ `ad/as/pd/ps` và hiệu ứng lân cận thông qua callback CDF chuẩn của IC617 (`tools/ic617_oa_cdf.il`).
2. Sau bước định cỡ `gmid_lut.py`, luôn chạy OP trên mạch thực (`tools/psf_audit.py op-audit`) vì $V_{DS}$, $V_{SB}$ thực tế và hiệu ứng tải chéo sẽ dịch nhẹ điểm làm việc so với bảng tra đơn linh kiện.
3. Dùng [sizing_opt.py](../tools/sizing_opt.py) để tính **Jacobian độ nhạy cục bộ** ($\partial \text{Metric}_i / \partial \ln x_j$) và tinh chỉnh đồng thời `(W, L, I_bias, C_c, R_z)` bằng thuật toán Trust-Region + Nelder-Mead có ràng buộc biên bão hòa $|V_{DS}| - |V_{DS,\text{sat}}| \ge 50\text{ mV}$ trên đa góc PVT (`TT`, `SS`, `FF`), không bao giờ sửa ngược LUT hay hạ chuẩn `spec.json` để ép báo `PASS`.
