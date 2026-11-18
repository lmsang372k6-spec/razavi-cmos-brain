---
{
  "id": "skill-gpdk-techsweep-and-gmid-lut-interpolator",
  "kind": "skill",
  "domain": "eda-and-github-skills",
  "title_vi": "Quét Đặc tính PDK An toàn trên RHEL 6.5 & Giải Ngược Nội suy Đa tuyến tính gm/ID Dưới 5 ms (gpdk_techsweep & gmid_lut)",
  "title_en": "RHEL 6.5 Safe GPDK090/GPDK045 Techsweep Generator & Sub-5ms Pure-Python Multilinear gm/ID Inverse Sizing Engine",
  "summary": "Playbook vận hành cặp công cụ chuẩn Python 2.6.6+ tools/gpdk_techsweep.py và tools/gmid_lut.py (0 phụ thuộc NumPy/SciPy): khắc phục triệt để 4 lỗi nghiêm trọng của bộ quét pygmid upstream trên GPDK090/GPDK045 + Spectre 15.1, biên dịch bảng tra nén .lut.json.gz tại ~/.cache/skill-analog/gmid-luts/ và thực hiện giải ngược nội suy đa tuyến tính có cắt đuôi GIDL dưới 5 ms từ (gm, gm/ID, L, VDS) ra chính xác (W, nf chẵn, W_finger, ro, gm*ro, fT, Vdsat).",
  "diagram": "../../diagrams/gmid-sizing-methodology.svg",
  "razavi_refs": [
    {
      "chapter": 2,
      "section": "2.3-2.4.2",
      "pages": "24-31",
      "equations": [
        "2.32",
        "2.36",
        "2.42"
      ]
    },
    {
      "chapter": 11,
      "section": "11.2-11.6",
      "pages": "460-507",
      "equations": [
        "11.1",
        "11.4",
        "11.6",
        "11.10"
      ]
    },
    {
      "chapter": 14,
      "section": "14.2.1",
      "pages": "597-605",
      "equations": [
        "14.78",
        "14.82"
      ]
    },
    {
      "chapter": 17,
      "section": "17.1-17.4",
      "pages": "691-711",
      "equations": [
        "17.12",
        "17.32",
        "17.51"
      ]
    }
  ],
  "github_refs": [
    {
      "repo": "bmurmann/Book-on-gm-ID-design",
      "url": "https://github.com/bmurmann/Book-on-gm-ID-design",
      "use": "Ma trận quét đặc tính 4 chiều (L, VGS, VDS, VSB) và phương pháp thiết kế theo tỷ số chuẩn hóa của Boris Murmann"
    },
    {
      "repo": "bmurmann/Book-on-MOS-stages",
      "url": "https://github.com/bmurmann/Book-on-MOS-stages",
      "use": "Phân tích đánh đổi gm/ID, gm/gds, fT và tự tải Cdd/Cgg cho các tầng khuếch đại MOS kênh ngắn"
    },
    {
      "repo": "dreoilin/pygmid",
      "url": "https://github.com/dreoilin/pygmid",
      "use": "Đối chiếu giao diện tra cứu tỷ số và nhận diện 4 lỗi adapter quét Spectre cần khắc phục trên GPDK"
    },
    {
      "repo": "IHP-GmbH/IHP-AnalogAcademy",
      "url": "https://github.com/IHP-GmbH/IHP-AnalogAcademy",
      "use": "Quy trình chuẩn kết hợp khảo sát đường cong gm/ID với phân chia ngón đồng nhất và kiểm chứng góc quy trình"
    }
  ],
  "glossary_codes": [
    "T276",
    "T326",
    "T355",
    "T394",
    "T1851",
    "T2153",
    "T2154",
    "T2186",
    "T2278"
  ],
  "process_agnostic": true,
  "roles": {
    "safe_techsweep_compiler": "Công cụ tools/gpdk_techsweep.py sinh netlist Spectre 15.1 đúng trần điện áp SOA và đúng tên góc của GPDK090/GPDK045, nén kết quả thành tệp .lut.json.gz gọn nhẹ ngoài thư viện gốc",
    "monotone_inverse_solver": "Bộ giải ngược trong tools/gmid_lut.py tự động cắt nhánh rò GIDL bên trái đỉnh (gm/ID)_max và tìm nghiệm VGS chính xác bằng chia đôi kết hợp nội suy logarit mật độ dòng",
    "geometry_and_finger_snapper": "Lệnh con gmid_lut.py size chuyển đổi (gm, gm/ID, L, VDS) thành tổng bề rộng W, làm tròn số ngón chẵn nf >= 2 trên lưới chế tạo 5 nm và dự báo ngay ro, Cgg, fT",
    "pareto_tradeoff_explorer": "Lệnh con gmid_lut.py tradeoff xuất bảng đánh đổi đa chiều (gm/ID x L) -> (gm*ro, fT, JD, Vdsat) dẫn hướng chọn vùng nghịch đảo tối ưu cho từng vai trò transistor"
  },
  "symptoms_addressed": [
    "pygmid-requires-python3-numpy-scipy-unavailable-on-rhel6-guest",
    "upstream-sweep-runs-at-minus-246-celsius-due-to-kelvin-subtraction-bug",
    "gpdk090-1v-core-mosfet-overstressed-to-1-8v-during-lut-characterization",
    "inverse-gm-id-lookup-returns-bogus-zero-current-root-in-deep-gidl-cutoff-tail",
    "manual-w-l-guessing-takes-dozens-of-spectre-iterations-to-hit-gbw-and-gain"
  ],
  "limitations": [
    "narrow-width-and-sti-stress-create-minor-2-to-5-pct-shift-when-wf-differs-from-reference-finger",
    "extreme-high-frequency-rf-above-ft-over-5-requires-non-quasi-static-gate-resistance-modeling",
    "separate-lut-files-must-be-queried-when-evaluating-ff-or-ss-corners-directly"
  ],
  "checklists": [
    "closed-loop-sizing-and-signoff",
    "common-mos",
    "differential-pair",
    "current-mirror"
  ]
}
---

## 1. Vì sao Cần Bộ Công cụ `gpdk_techsweep.py` & `gmid_lut.py` Thuần Thư viện Chuẩn Trên RHEL 6.5?

Phương pháp định cỡ hệ thống theo tỷ số hỗ dẫn trên dòng máng $g_m/I_D$ (`T1851`, `skill-gm-id-lookup-table-sizing`) là chiếc cầu nối vật lý duy nhất biến các chỉ tiêu mạch cấp cao ($\text{GBW}, A_0, \overline{v_n^2}, \sigma(V_{OS}), V_{DS,\min}$) thành kích thước transistor $(W, L, N_f)$ chính xác ngay từ lần chạy đầu tiên ở các công nghệ $180\text{ nm}$, $90\text{ nm}$ và $45\text{ nm}$. Tuy nhiên, khi triển khai tự động hóa trực tiếp bên trong máy ảo Linux RHEL 6.5 đi kèm Cadence IC617 + Spectre 15.1, các công cụ mã nguồn mở sẵn có đều vấp phải hai rào cản chí mạng:
1. **Phụ thuộc Nặng vào Ngăn xếp Khoa học Python 3:** Thư viện `dreoilin/pygmid` đòi hỏi Python $\ge 3{,}8$ cùng `numpy` và `scipy.interpolate.interpn`, còn kho gốc `bmurmann/Book-on-gm-ID-design` viết cho MATLAB thương mại — cả hai đều **không tồn tại** trên môi trường `/usr/bin/python` (`2.6.6`) chuẩn của RHEL 6.5.
2. **Bốn Lỗi Adapter Quét Nghiêm trọng Trên GPDK090 / GPDK045 (`CHK-OPT-04`):**
   - *Lỗi 1 (Độ K so với Độ C):* Trình sinh netlist upstream lấy `TEMP - 273.15`; truyền `27` khiến Spectre chạy ở **$-246{,}15\,^\circ\text{C}$** (đóng băng hạt dẫn làm $V_{TH}$ và $g_m/I_D$ sai lệch hoàn toàn!).
   - *Lỗi 2 (Lệch dấu phân tách PSF):* Lưu tên khóa `mn:ids` nhưng trình đọc đổi sang dấu chấm `mn.ids` trả về toàn số `0.0`.
   - *Lỗi 3 (Nuốt mã thoát lỗi):* Bắt ngoại lệ `CalledProcessError` rồi vẫn xuất tệp bảng tra chứa toàn giá trị không mà không cảnh báo.
   - *Lỗi 4 (Quá áp đánh thủng mô hình Core):* Quét tới $1{,}8\text{ V}$ trên linh kiện oxit mỏng `gpdk090_nmos1v` ($V_{\text{DD,nom}} = 1{,}0\text{–}1{,}2\text{ V}$) và nhầm tên section góc quy trình (`GPDK090` dùng chữ hoa `NN, SS, FF, FS, SF` trong khi `GPDK045` dùng chữ thường `tt, ss, ff, fs, sf`).

![Lưu đồ trích xuất bảng tra gm/ID đa tiến trình và giải ngược nội suy đa tuyến tính tốc độ mili-giây](../../diagrams/gmid-sizing-methodology.svg)

Cặp công cụ **`tools/gpdk_techsweep.py`** và **`tools/gmid_lut.py`** giải quyết dứt điểm toàn bộ các rào cản trên bằng 100% thư viện chuẩn Python (`optparse`, `gzip`, `json`, `math`, `bisect`), chạy dưới **$5\text{ ms}$ mỗi truy vấn** ngay trên Python 2.6.6 lẫn Python 3, đồng thời lưu trữ bảng tra nén `.lut.json.gz` sạch sẽ tại `~/.cache/skill-analog/gmid-luts/` (giữ cây thư viện `SKILL-ANALOG` bất biến tuyệt đối!).

---

## 2. Toán học Nội suy Đa Tuyến tính Trên Không gian Logarit & Giải Ngược Cắt Đuôi GIDL

### 2.1. Cấu trúc Ten-xơ Chuẩn hóa Bất biến Bề rộng Trong `.lut.json.gz`
Trên lưới quét 4 chiều rời rạc theo đúng thứ tự vòng lặp lồng nhau `[L, VDS, VSB, VGS]` ($\mathcal{G} = \mathbf{L} \times \mathbf{V}_{DS} \times \mathbf{V}_{SB} \times \mathbf{V}_{GS}$) với ngón đơn vị chuẩn $W_{\text{ref}} = N_{f,\text{ref}} \cdot W_{f,\text{ref}}$ (ví dụ $W_{f,\text{ref}} = 2\text{ }\mu\text{m}, N_{f,\text{ref}} = 2 \Rightarrow W_{\text{ref}} = 4\text{ }\mu\text{m}$), `gpdk_techsweep.py` thu thập và chuẩn hóa mọi đại lượng mở rộng về mật độ trên một mét bề rộng kênh (`T2278`):

$$
J_D = \frac{|I_D|}{W_{\text{ref}}}, \quad \frac{g_m}{I_D} = \frac{g_m}{|I_D|}, \quad \frac{g_m}{g_{ds}}, \quad f_T = \frac{g_m}{2\pi |C_{gg}|}, \quad c_{gg} = \frac{|C_{gg}|}{W_{\text{ref}}}, \quad c_{gd} = \frac{|C_{gd}|}{W_{\text{ref}}}, \quad c_{dd} = \frac{|C_{dd}|}{W_{\text{ref}}}, \quad V_{DS,\text{sat}}, \quad V_{TH}
$$

Vì mật độ dòng $J_D(V_{GS})$ biến thiên xuyên qua **6–8 bậc độ lớn** từ vùng dưới ngưỡng ($10^{-3}\text{ A/m}$) lên vùng nghịch đảo mạnh ($10^{+2}\text{ A/m}$), phép nội suy tuyến tính trực tiếp trên $J_D$ sẽ gây sai số vọt lố tới $25\text{–}40\%$ ở vùng nghịch đảo yếu (Razavi Chương 2 Phương trình 2.32: $I_D \propto \exp(V_{GS}/(\zeta V_T))$)! Do đó, `gmid_lut.py` thực hiện **nội suy tuyến tính trên $\ln(J_D)$**:

$$
\ln J_D(V_{GS}) \approx (1 - \alpha)\,\ln J_D[k] + \alpha\,\ln J_D[k+1] \;\;\Longrightarrow\;\; J_D(V_{GS}) = J_D[k]^{1-\alpha} \cdot J_D[k+1]^{\alpha}, \qquad \alpha = \frac{V_{GS} - V_{GS}[k]}{V_{GS}[k+1] - V_{GS}[k]}
$$

Phép trung bình nhân có trọng số này tái tạo **chính xác tuyệt đối ($0\%$ sai số phương pháp)** luật hàm mũ dưới ngưỡng và chuyển tiếp êm sang vùng bão hòa vận tốc!

### 2.2. Cắt Bỏ Nhánh Phi Đơn điệu GIDL & Giải Ngược Đa Tuyến tính 3 Bước (`< 5 ms`)
Khi cho trước mục tiêu thiết kế $\left(g_{m,\text{req}},\; \eta_{\text{target}} = (g_m/I_D)_{\text{req}},\; L,\; V_{DS},\; V_{SB}\right)$:
1. **Bước 1 — Chiếu đa tuyến tính theo $(L, V_{DS}, V_{SB})$:** Với mỗi điểm lưới $V_{GS}[m]$, nội suy tam tuyến tính theo $(\ln L, V_{DS}, V_{SB})$ để dựng đường cong 1 chiều địa phương $\eta(V_{GS})$ và $\ln J_D(V_{GS})$ tại đúng điều kiện phân cực cực máng–thân thực tế của nhánh mạch.
2. **Bước 2 — Lọc cửa sổ đơn điệu vật lý (Chống bẫy GIDL):** Ở $V_{GS}$ quá thấp ($< 0{,}15\text{ V}$), dòng rò cảm ứng cổng tại cực máng (GIDL) và rò tiếp giáp làm $|I_D|$ ngừng giảm khiến $\eta(V_{GS}) = g_m/|I_D|$ gãy gập đi xuống về $0$. Bộ giải tự động tìm chỉ số đỉnh cực đại $m_{\text{peak}} = \arg\max_m \eta[m]$ và **chỉ tìm nghiệm trên miền đơn điệu giảm nghiêm ngặt $m \in [m_{\text{peak}}, M-1]$**! Nếu $\eta_{\text{target}} > \eta[m_{\text{peak}}]$, công cụ báo lỗi vượt trần nhiệt động lực học dưới ngưỡng $\frac{1}{\zeta V_T}$ (`CHK-MOS-04`) thay vì trả nghiệm rác!
3. **Bước 3 — Giải ngược $V_{GS}^*$ và Làm tròn Hình học Chia Ngón Chẵn (`size`):** Tìm đoạn bao $\eta[m+1] \le \eta_{\text{target}} \le \eta[m]$ bằng tìm kiếm nhị phân $O(\log M)$, suy ra $V_{GS}^*$, $J_D^* = \exp(\ln J_D(V_{GS}^*))$ và tính toàn bộ thông số hình học sẵn sàng đưa thẳng vào `ic617_client.py set-param`:

$$
I_D = \frac{g_{m,\text{req}}}{\eta_{\text{target}}}, \qquad W_{\text{raw}} = \frac{I_D}{J_D^*}, \qquad N_f = \max\!\left(2,\; 2\left\lceil \frac{W_{\text{raw}}}{2\,W_{f,\max}} \right\rceil\right), \qquad W_f = \Delta_{\text{mfg}} \cdot \operatorname{round}\!\left(\frac{W_{\text{raw}} / N_f}{\Delta_{\text{mfg}}}\right)
$$

với lưới chế tạo $\Delta_{\text{mfg}} = 5\text{ nm}$ và số ngón $N_f$ luôn là **số nguyên chẵn $\ge 2$** phục vụ ghép cài răng lược / đồng tâm chung ABBA (`T2194`, Razavi Chương 19 §19.2.2)!

---

## 3. Bất biến Vật lý & Các Bẫy Lỗi Khi Quét và Tra Cứu PDK (Invariants & Traps)

- **[INV-LUT-01] Khóa Cứng Trần Điện áp Quét Theo Đúng Phân hạng Oxit Cổng PDK (`SOA Cap`):**
  - Với **`GPDK090`**: linh kiện core `gpdk090_nmos1v` / `gpdk090_pmos1v` quét $V_{GS}, V_{DS} \in [0,\; 1{,}20\text{ V}]$ trên các góc `NN, SS, FF, FS, SF`; linh kiện IO dày `gpdk090_nmos2v` / `pmos2v` quét tối đa $2{,}50\text{ V}$.
  - Với **`GPDK045`**: linh kiện core `g45n1svt` / `g45p1svt` (và `lvt`/`hvt`) quét $V_{GS}, V_{DS} \in [0,\; 1{,}00\text{ V}]$ (tối đa $1{,}10\text{ V}$) trên các góc chữ thường `tt, ss, ff, fs, sf`; linh kiện IO `g45n2svt` quét tối đa $1{,}80\text{ V}$.
- **[INV-LUT-02] Đối Ngẫu Pelgrom Khi Chọn $g_m/I_D$ Trên Bảng `tradeoff` (`T2153`, `T2154`):** Theo định luật Pelgrom (Razavi Chương 14 §14.2.1), phương sai lệch áp đầu vào cặp vi sai và phương sai lệch dòng tương đối của gương dòng biến thiên **ngược chiều nhau** theo $g_m/I_D$:
  $$\sigma^2(V_{OS,\text{in}}) = \sigma^2(\Delta V_{TH}) + \frac{1}{(g_m/I_D)^2}\,\sigma^2\!\left(\frac{\Delta\beta}{\beta}\right), \qquad \sigma^2\!\left(\frac{\Delta I_D}{I_D}\right) = \left(\frac{g_m}{I_D}\right)^2 \sigma^2(\Delta V_{TH}) + \sigma^2\!\left(\frac{\Delta\beta}{\beta}\right)$$
  Do đó không bao giờ dùng chung một giá trị $g_m/I_D$ cho toàn mạch: chọn $g_m/I_D \in [15, 21]\text{ V}^{-1}$ cho cặp vi sai đầu vào, nhưng ép $g_m/I_D \in [6, 9]\text{ V}^{-1}$ kèm $L$ dài cho gương dòng và nguồn dòng đuôi!
- **[TRAP-LUT-01] Bẫy Quên Điện áp Thực tế $V_{DS}$ Khi Tra Độ lợi Nội tại $g_m/g_{ds}$ Ở 45nm/90nm:** Hiệu ứng DIBL và điều biến chiều dài kênh phụ thuộc rất mạnh vào $V_{DS}$: cùng một transistor `g45n1svt` tại $L = 90\text{ nm}, g_m/I_D = 15\text{ V}^{-1}$ có thể đạt $g_m/g_{ds} = 24$ ở $V_{DS} = 0{,}55\text{ V}$, nhưng tụt xuống chỉ còn $g_m/g_{ds} = 11$ khi $V_{DS}$ bị ép thấp còn $0{,}16\text{ V}$ dưới đáy chuỗi cascode! Luôn truyền đúng `--vds` dự kiến của nhánh đó trên sơ đồ phân bổ áp dọc khi gọi `gmid_lut.py`!
- **[TRAP-LUT-02] Bẫy Hiệu ứng Thân $V_{SB} > 0$ Trên Cặp Vi sai NMOS Nối Chung Giếng Đế p-sub:** Trong tiến trình giếng đơn tiêu chuẩn (không dùng Triple-Well), cặp vi sai đầu vào NMOS hoặc transistor cascode tầng trên chịu $V_{SB} \approx 0{,}25\text{–}0{,}60\text{ V}$, làm tăng $V_{TH}$ thêm $80\text{–}180\text{ mV}$ và thay đổi tỷ số $g_{mb}/g_m = \eta$. Phải truyền `--vsb` khác không khi định cỡ các linh kiện không nối cực nguồn với cực thân!

---

## 4. Ma trận Ba Lệnh Vận hành Của `gpdk_techsweep.py` & `gmid_lut.py`

| Công cụ & Lệnh Con | Tham số Đầu vào Chính | Đầu ra JSON Chuẩn | Thời gian Chạy & Ngữ cảnh Sử dụng |
|---|---|---|---|
| `gpdk_techsweep.py --pdk gpdk090 --corners NN,SS,FF` | Đường dẫn model PDK, danh sách góc, bước lưới `L/VDS/VSB/VGS` | Tệp `~/.cache/skill-analog/gmid-luts/gpdk090_core_1v_<corner>_27C.lut.json.gz` | Chạy **1 lần duy nhất** mỗi PDK (`2–6 phút`), tái sử dụng vĩnh viễn cho mọi dự án |
| `gpdk_techsweep.py --generate-demo-lut <path>` | Đường dẫn xuất tệp LUT mẫu | Bảng tra vật lý chuẩn EKV/BSIM đa chiều dài kênh cho NMOS & PMOS | `< 0.5 s` — phục vụ tự kiểm thử ngoại tuyến (`--self-test`) khi chưa bật Spectre |
| `gmid_lut.py query` | `--lut`, `--dev nmos\|pmos`, `--l`, `--gm-id`, `--vds`, `[--vsb]` | `{jd_a_per_m, gm_gds, ft_hz, vgs, vdsat, vth, cgg_f_per_m, cgd_cgg, cdd_cgg}` | **`< 5 ms`** — khảo sát điểm phân cực và lấy hệ số tự tải ký sinh |
| `gmid_lut.py size` | `--lut`, `--dev`, `--gm`, `--gm-id`, `--l`, `--vds`, `[--w-finger-max]` | `{id_a, w_total_m, nf, w_finger_m, ro_ohm, intrinsic_gain_db, cgg_f, vds_min}` | **`< 5 ms`** — Giai đoạn 3 định cỡ trực tiếp từng nhánh transistor |
| `gmid_lut.py tradeoff` | `--lut`, `--dev`, `--l-list`, `--gm-id-range`, `--vds` | Bảng ma trận Pareto `(gm/ID, L) -> (gm*ro, fT, JD, Vdsat)` | **`< 8 ms`** — chọn cặp $(g_m/I_D, L)$ tối ưu trước khi chốt kiến trúc tầng |

---

## 5. Quy trình Thực chiến Từ Quét Bảng Tra GPDK Đến Định cỡ Cặp Vi sai & Gương Dòng

### 5.1. Khởi tạo Bảng Tra GPDK090/GPDK045 Hoặc Bảng Mẫu Tự Kiểm thử
Trên máy RHEL 6.5 (hoặc máy phát triển bất kỳ), luôn truyền `PYTHONDONTWRITEBYTECODE=1 python -B`:

```bash
# A. Khi chạy trên máy chủ Cadence có sẵn GPDK090 + Spectre 15.1 (lưu vào ~/.cache/skill-analog/gmid-luts/)
PYTHONDONTWRITEBYTECODE=1 python -B /home/disk/eda/references/SKILL-ANALOG/tools/gpdk_techsweep.py \
  --pdk gpdk090 \
  --model-file /home/disk/eda/pdks/gpdk090_v4.6/models/spectre/gpdk090.scs \
  --corners NN,SS,FF \
  --out-dir ~/.cache/skill-analog/gmid-luts

# B. Kiểm tra nhanh độ chính xác nội bộ (< 0.5s, dùng thư mục tạm tự dọn sạch hoặc đường dẫn cache)
PYTHONDONTWRITEBYTECODE=1 python -B /home/disk/eda/references/SKILL-ANALOG/tools/gpdk_techsweep.py \
  --generate-demo-lut ~/.cache/skill-analog/gmid-luts/demo_90nm_tt.lut.json.gz
```

### 5.2. Khảo sát Bảng Đánh đổi Pareto (`tradeoff`) & Giải Ngược Kích thước (`size`) Cho OTA
Giả sử ta cần thiết kế tầng đầu OTA đạt $\text{GBW} = 100\text{ MHz}$ trên tải hiệu dụng $C_{L,\text{eff}} = 1{,}5\text{ pF} \Rightarrow g_{m1} = 2\pi (10^8)(1{,}5\times 10^{-12}) \approx 0{,}942\text{ mS}$, độ lợi tầng $\ge 34\text{ dB}$ ($50\text{ V/V} \Rightarrow$ cần $g_m/g_{ds} \ge 100$ nếu tải đối xứng, hoặc cascode):

```bash
# 1. Xem ma trận đánh đổi giữa các chiều dài kênh L = 100n, 180n, 360n, 540n và gm/ID từ 8 đến 20 V^-1
PYTHONDONTWRITEBYTECODE=1 python -B /home/disk/eda/references/SKILL-ANALOG/tools/gmid_lut.py tradeoff \
  --lut ~/.cache/skill-analog/gmid-luts/gpdk090_core_1v_NN_27C.lut.json.gz \
  --dev nmos --l-list 100e-9,180e-9,360e-9,540e-9 --gm-id-range 8,20 --vds 0.45

# 2. Định cỡ cặp vi sai đầu vào M1/M2 ở vùng nghịch đảo vừa-yếu (gm/ID = 16 V^-1, L = 250n, VDS = 0.35V, VSB = 0.25V)
PYTHONDONTWRITEBYTECODE=1 python -B /home/disk/eda/references/SKILL-ANALOG/tools/gmid_lut.py size \
  --lut ~/.cache/skill-analog/gmid-luts/gpdk090_core_1v_NN_27C.lut.json.gz \
  --dev nmos --gm 0.95e-3 --gm-id 16.0 --l 250e-9 --vds 0.35 --vsb 0.25 --w-finger-max 4e-6

# 3. Định cỡ gương dòng tải PMOS M3/M4 ở vùng nghịch đảo mạnh (gm/ID = 7.5 V^-1, L = 500n) để nén nhiễu & mismatch
PYTHONDONTWRITEBYTECODE=1 python -B /home/disk/eda/references/SKILL-ANALOG/tools/gmid_lut.py size \
  --lut ~/.cache/skill-analog/gmid-luts/gpdk090_core_1v_NN_27C.lut.json.gz \
  --dev pmos --gm 0.445e-3 --gm-id 7.5 --l 500e-9 --vds 0.40 --vsb 0.0 --w-finger-max 4e-6
```

Đầu ra JSON của lệnh `size` cung cấp trọn bộ thông số vật lý chỉ trong $2\text{ ms}$:

```json
{
  "ok": true,
  "dev": "nmos",
  "inputs": {"gm_s": 0.00095, "gm_id": 16.0, "l_m": 2.5e-07, "vds_v": 0.35, "vsb_v": 0.25},
  "sized": {
    "id_a": 5.9375e-05,
    "w_total_m": 1.44e-05,
    "nf": 4,
    "w_finger_m": 3.6e-06,
    "vgs_v": 0.512,
    "vds_min_v": 0.128,
    "ro_ohm": 41250.0,
    "intrinsic_gain_vv": 39.19,
    "intrinsic_gain_db": 31.86,
    "ft_hz": 18400000000.0,
    "cgg_f": 8.22e-15,
    "cdd_f": 4.95e-15
  }
}
```

Toàn bộ cặp số `l=250n`, `fingers=4`, `w=14.4u` (với `w_finger=3.6u` làm tròn chẵn lưới `5nm`) sẵn sàng nạp trực tiếp sang Giai đoạn 4 (`ic617_client.py set-param`) và Giai đoạn 6 (`sizing_opt.py`) với sai số điểm tĩnh dưới $3\%$ ngay từ lần mô phỏng Spectre đầu tiên!

---

## 6. Đối chiếu Sách Razavi, Nguồn GitHub Đã Kiểm định & Thuật ngữ Chuẩn CLB

### 6.1. Đối chiếu Sách Gốc Razavi (2nd Edition) & Nguồn Mở GitHub
- **Razavi Chương 11 (§11.2–11.6, tr. 460–507) & Chương 17 (§17.1–17.4, tr. 693–711):** Nền tảng trích xuất đặc tính transistor nanomet theo $V_{DS,\min}$ và mật độ dòng chuẩn hóa khi luật bình phương mất hiệu lực do bão hòa vận tốc và DIBL.
- **Razavi Chương 14 (§14.2.1, tr. 597–605, Phương trình 14.78–14.82):** Định luật Pelgrom và nguyên lý đối ngẫu định cỡ giữa cặp khuếch đại vi sai đầu vào với gương dòng phân cực.
- **Nguồn GitHub Đã Kiểm định:**
  - [`bmurmann/Book-on-gm-ID-design`](https://github.com/bmurmann/Book-on-gm-ID-design) (commit `9bc96fbcfc0d`, AGPL-3.0) & [`bmurmann/Book-on-MOS-stages`](https://github.com/bmurmann/Book-on-MOS-stages) (commit `de27e862689b`, CC-BY-4.0): Phương pháp luận thiết kế theo bảng tra đa chiều và phương trình tầng khuếch đại kênh ngắn.
  - [`dreoilin/pygmid`](https://github.com/dreoilin/pygmid) (commit `a9563980b30b`, Apache-2.0) & [`IHP-GmbH/IHP-AnalogAcademy`](https://github.com/IHP-GmbH/IHP-AnalogAcademy) (commit `d1c892d66bd6`, Apache-2.0): Cơ sở đối chiếu giao diện tra cứu và quy tắc sửa 4 lỗi quét đặc tính PDK thực tế.

### 6.2. Bảng Thuật ngữ Chuẩn CLB Vi Mạch Sử dụng trong Thẻ
| Mã CLB | Thuật ngữ Tiếng Anh | Thuật ngữ Tiếng Việt Chuẩn | Vai trò Trong `gpdk_techsweep.py` & `gmid_lut.py` |
|---|---|---|---|
| `T2278` | multilinear gm/ID lookup-table inverse sizing | định cỡ giải ngược nội suy đa tuyến tính trên bảng tra gm/ID | Thuật toán hạt nhân giải ngược $(g_m, g_m/I_D, L, V_{DS}) \mapsto (W, N_f)$ dưới $5\text{ ms}$ |
| `T1851` | gm/ID ratio | tỉ số gm/ID | Biến đầu vào độc lập chọn vùng nghịch đảo tối ưu cho từng nhánh |
| `T2153` / `T2154` | Pelgrom's law / sizing duality | định luật Pelgrom / đối ngẫu định cỡ cặp vi sai và gương dòng | Quyết định $g_m/I_D$ cao cho cặp vào và $g_m/I_D$ thấp cho gương dòng |
| `T394` | Intrinsic gain (gm rO) | Độ lợi nội tại | Trả về tại đúng $V_{DS}$ thực tế trong bảng `tradeoff` và `size` |
| `T355` | Body transconductance (gmb) | Độ hỗ dẫn thân gmb | Xét đầy đủ qua trục quét thứ tư `--vsb` trên transistor không nối chung nguồn–thân |
| `T326` | Folded transistor | Transistor bố trí gấp | Tự động tách chiều rộng tổng thành số ngón chẵn `nf >= 2` trên lưới `5 nm` |
