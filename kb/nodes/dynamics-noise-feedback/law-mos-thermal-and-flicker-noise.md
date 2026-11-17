---
{
  "id": "law-mos-thermal-and-flicker-noise",
  "kind": "law",
  "domain": "dynamics-noise-feedback",
  "title_vi": "Định luật Nhiễu Nhiệt và Nhiễu Nhấp nháy 1/f trong Linh kiện Điện trở & MOSFET (Thermal & 1/f Flicker Noise Laws)",
  "title_en": "Statistical Noise Fundamentals, Resistor 4kTR, and MOSFET Thermal & 1/f Flicker Noise Laws",
  "summary": "Nền tảng vật lý và thống kê của nhiễu điện tử nội tại: mật độ phổ công suất một phía (PSD, V^2/Hz vs V/sqrt(Hz)), nguyên lý cộng công suất nguồn không tương quan, nhiễu nhiệt điện trở 4kTR & bất biến kT/C, nhiễu nhiệt kênh dẫn 4kT*gamma*gm, nhiễu cổng và nhiễu nhấp nháy 1/f K/(Cox*W*L*f).",
  "diagram": "../../diagrams/mos-noise-input-referred.svg",
  "razavi_refs": [
    {
      "chapter": 7,
      "section": "7.1-7.2",
      "pages": "219-236",
      "equations": ["7.3", "7.4", "7.6", "7.11", "7.16", "7.23", "7.28", "7.30", "7.33", "7.34", "7.38", "7.42"]
    }
  ],
  "glossary_codes": ["T392", "T527", "T687", "T1009", "T1029", "T1063", "T1064", "T1080", "T1084", "T1089", "T1127", "T1177"],
  "process_agnostic": true,
  "roles": {
    "resistor_thermal_source": "Chuyển động nhiệt ngẫu nhiên của hạt tải trong điện trở R tạo nguồn áp nhiễu trắng nối tiếp 4kTR hoặc nguồn dòng song song 4kT/R",
    "mos_channel_thermal_source": "Dao động vận tốc hạt tải dọc kênh nghịch đảo của MOSFET tạo nguồn dòng nhiễu trắng nối giữa máng và nguồn 4kT*gamma*gm",
    "mos_gate_resistance_source": "Điện trở vật lý của dải cực cổng đa tinh thể/kim loại RG sinh nhiễu nhiệt 4kT*RG/3 (khi nối tiếp một đầu) phải được khống chế bằng chia ngón",
    "oxide_interface_traps_1f": "Các bẫy trạng thái lơ lửng tại biên phân cách Si-SiO2 bắt giữ và nhả hạt tải chậm tạo nguồn áp nhiễu nhấp nháy 1/f nối tiếp cực cổng K/(Cox*W*L*f)"
  },
  "symptoms_addressed": [
    "low-snr-floor-in-analog-front-end",
    "excess-low-frequency-1f-wander-in-dc-precision-circuits",
    "high-gate-resistance-noise-in-wide-rf-mosfets",
    "unit-confusion-between-psd-and-asd"
  ],
  "limitations": [
    "short-channel-hot-carriers-elevate-gamma-above-two-thirds",
    "1f-noise-diverges-logarithmically-if-integrated-to-zero-hz",
    "subthreshold-and-triode-regions-require-gds0-or-shot-like-formulations"
  ],
  "checklists": ["common-mos", "layout-and-matching"]
}
---

## 1. Bản chất Nguyên lý, Sơ đồ Mạch & Vai trò Từng Nhánh Cấu trúc

Nếu tính phi tuyến giới hạn biên độ cực đại của tín hiệu thì **nhiễu điện tử nội tại của linh kiện (device electronic noise, `T1077`)** đặt ra bức tường vật lý tối hậu cho biên độ tín hiệu nhỏ nhất mà mạch tương tự có thể xử lý được với tỷ số tín hiệu trên nhiễu (signal-to-noise ratio, SNR) chấp nhận được. Khác với nhiễu môi trường bên ngoài (như xuyên nhiễu nguồn cấp hay ghép đế có tính tất định theo xung nhịp), nhiễu nội tại sinh ra từ bản chất lượng tử–nhiệt ngẫu nhiên của hạt tải ngay bên trong điện trở và MOSFET (Razavi Chương 7, §7.1–§7.2).

![Mô hình nguồn nhiễu nhiệt kênh dẫn, nhiễu nhấp nháy 1/f và quy đổi nhiễu hai cửa của MOSFET](../../diagrams/mos-noise-input-referred.svg)

Mỗi linh kiện trên schematic ẩn chứa các cơ chế phát sinh nhiễu độc lập sau:
1. **Điện trở thực ($R$):** Được tách thành một **điện trở không sinh nhiễu (noiseless resistor, `T1085`)** mắc nối tiếp với nguồn áp nhiễu trắng $\overline{V_n^2} = 4kTR$ (Thevenin) hoặc mắc song song với nguồn dòng nhiễu trắng $\overline{I_n^2} = \frac{4kT}{R}$ (Norton).
2. **Kênh dẫn MOSFET ($\overline{I_{n,d}^2}$):** Ở vùng bão hòa, kênh nghịch đảo hoạt động như một phần tử dẫn điện không đồng nhất bị điều biến, được mô hình hóa bằng nguồn dòng nhiễu nhiệt nối trực tiếp giữa cực máng và cực nguồn $\overline{I_{n,d}^2} = 4kT\gamma g_m$ (và ở vùng triode sâu $V_{DS} \approx 0$, thay $g_m$ bằng độ dẫn máng–nguồn $g_{ds0} = R_{on}^{-1}$!).
3. **Cực cổng MOSFET ($R_G$ và Nhiễu cảm ứng cực cổng):** Dải cực cổng dài có điện trở phân bố $R_G$ tạo ra điện trở nhiễu hiệu dụng $R_G/3$ (khi cấp tín hiệu một đầu ngón) hoặc $R_G/12$ (khi cấp tín hiệu hai đầu ngón). Ngoài ra ở tần số rất cao gần $f_T$, dao động thế dọc kênh ghép điện dung qua $C_{ox}$ lên cực cổng sinh thêm dòng nhiễu cảm ứng cực cổng (induced gate noise, tỉ lệ với $\omega^2 C_{GS}^2 / g_m$).
4. **Mặt phân cách Oxit Cổng $\text{Si–SiO}_2$ ($\overline{V_{n,1/f}^2}$):** Các liên kết đứt gãy (dangling bonds) tại mặt tiếp giáp tinh thể silic và lớp điện môi cổng ngẫu nhiên bắt giữ rồi giải phóng hạt tải với hằng số thời gian trải rộng nhiều thập kỷ, tạo nên nguồn áp **nhiễu nhấp nháy $1/f$ (flicker noise, `T392`)** đặt nối tiếp tại cực cổng.

---

## 2. Hệ Phương trình Cốt lõi & Tư duy "Nhìn Mạch Đọc Nhanh" (Analysis by Inspection)

### 2.1. Thống kê Nhiễu: PSD Một Phía, Định hình Phổ và Tương quan (§7.1)
- **Công suất trung bình chuẩn hóa và Giá trị hiệu dụng (RMS, Phương trình 7.3):** Với quá trình ngẫu nhiên dừng $x(t)$ có trung bình bằng không ($\overline{x(t)} = 0$), công suất trung bình chuẩn hóa trên tải $1\,\Omega$ là $P_{av} = \lim_{T\to\infty} \frac{1}{T}\int_{-T/2}^{+T/2} x^2(t)\,dt = V_{\text{rms}}^2$ (lưu ý `NG07-01`: chỉ khi trung bình $m = 0$ thì độ lệch chuẩn $\sigma$ của phân bố Gauss mới bằng chính xác $V_{\text{rms}}$; nếu $m \neq 0$ thì $V_{\text{rms}} = \sqrt{\sigma^2 + m^2}$!).
- **Mật độ phổ công suất một phía (One-Sided PSD, `T1084`) so với Mật độ phổ biên độ (ASD):** Trong kỹ thuật mạch thực hành (và trong Cadence Spectre!), ta gấp nửa trục tần số âm sang trục dương $f \ge 0$ để dùng **PSD một phía** $S_v(f)$ ký hiệu ngắn gọn là $\overline{V_n^2}$ có đơn vị **$\text{V}^2/\text{Hz}$** (hoặc $\text{A}^2/\text{Hz}$ cho dòng), còn căn bậc hai $\sqrt{\overline{V_n^2}}$ là ASD có đơn vị **$\text{V}/\sqrt{\text{Hz}}$** (ví dụ $4\text{ nV}/\sqrt{\text{Hz}} \iff 1{,}6\times 10^{-17}\text{ V}^2/\text{Hz}$).
- **Định lý Truyền Nhiễu Tuyến tính (Phương trình 7.4):** Khi nguồn nhiễu $S_x(f)$ đi qua mạng tuyến tính bất biến thời gian $H(s)$, PSD ngõ ra được nhân với **bình phương biên độ** hàm truyền:

$$
S_y(f) = S_x(f) \cdot \left|H(j 2\pi f)\right|^2, \qquad V_{n,\text{out,rms}} = \sqrt{\int_{f_1}^{f_2} S_y(f)\,df}
$$

- **Tổng các Nguồn Nhiễu Không Tương quan vs. Có Tương quan (Phương trình 7.9–7.11):**

$$
\overline{\big[x_1(t) + x_2(t)\big]^2} = \overline{x_1^2(t)} + \overline{x_2^2(t)} + 2\,\overline{x_1(t) x_2(t)}
$$

Hai linh kiện vật lý độc lập (ví dụ $M_1$ và $R_D$) luôn **không tương quan (`T1064`, uncorrelated)** nên số hạng tích chéo bằng 0: **luôn cộng các bình phương $\overline{V_{n1}^2} + \overline{V_{n2}^2}$, tuyệt đối không bao giờ cộng trực tiếp biên độ căn bậc hai**, và **không bao giờ quan tâm dấu âm/dương của $H(s)$ khi các nguồn độc lập nhau**! Ngược lại, nếu cùng một nguồn nhiễu vật lý đi tới ngõ ra theo **hai đường truyền khác nhau** (ví dụ qua hai nhánh mạch cầu hoặc qua $V_{n,in}$ và $I_{n,in}$ của cùng một linh kiện), chúng **có tương quan hoàn toàn (`T1063`, correlated)** — bắt buộc phải cộng đại số biên độ phức theo KCL/KVL hoàn chỉnh rồi mới bình phương!

### 2.2. Nhiễu Nhiệt Điện trở và Bất biến $kT/C$ (§7.2.1, Phương trình 7.16–7.23)
Mật độ phổ một phía của điện trở $R$ ở nhiệt độ tuyệt đối $T$ (với hằng số Boltzmann $k = 1{,}38 \times 10^{-23}\text{ J/K}$, tại $T = 300\text{ K}$ có $4kT \approx 1{,}656 \times 10^{-20}\text{ J}$):

$$
\overline{V_{n,R}^2} = 4 k T R \quad [\text{V}^2/\text{Hz}], \qquad \overline{I_{n,R}^2} = \frac{4 k T}{R} \quad [\text{A}^2/\text{Hz}]
$$

*Điểm nhớ nhanh vàng:* Một điện trở **$R = 1\text{ k}\Omega$** ở phòng thí nghiệm ($300\text{ K}$) luôn sinh chính xác **$\sqrt{4kTR} \approx 4{,}07\text{ nV}/\sqrt{\text{Hz}}$** (nên $50\,\Omega \to 0{,}91\text{ nV}/\sqrt{\text{Hz}}$, $10\text{ k}\Omega \to 12{,}9\text{ nV}/\sqrt{\text{Hz}}$!).

Khi đặt một tụ điện $C$ lọc thông thấp sau điện trở $R$ (Ví dụ 7.5, Phương trình 7.17–7.23), tổng bình phương điện áp nhiễu tích phân từ $0$ đến $\infty$ là:

$$
\overline{V_{n,\text{out,tot}}^2} = \int_{0}^{\infty} \frac{4 k T R}{1 + (2\pi R C f)^2}\,df = \frac{k T}{C}
$$

**Bất biến Vật lý $kT/C$:** Điện trở $R$ triệt tiêu hoàn toàn! Tăng $R$ làm tăng PSD nhiễu nền $4kTR$ bao nhiêu lần thì lại thu hẹp băng thông lọc $\frac{1}{2\pi R C}$ đi đúng bấy nhiêu lần (diện tích dưới đường cong giữ nguyên không đổi bằng $\frac{kT}{C}$; ví dụ $C = 1\text{ pF}$ tại $300\text{ K}$ luôn có $V_{n,\text{rms}} \approx 64\,\mu\text{V}_{\text{rms}}$!).

### 2.3. Nhiễu Nhiệt Kênh Dẫn & Nhiễu Cực Cổng của MOSFET (§7.2.1, Phương trình 7.28–7.33)
- **Trong vùng bão hòa:** Nguồn dòng nhiễu máng–nguồn và điện áp quy về cực cổng tương ứng là:

$$
\overline{I_{n,\text{th}}^2} = 4 k T \gamma g_m \quad [\text{A}^2/\text{Hz}] \quad \Longleftrightarrow \quad \overline{V_{n,\text{th,gate}}^2} = \frac{\overline{I_{n,\text{th}}^2}}{g_m^2} = \frac{4 k T \gamma}{g_m} \quad [\text{V}^2/\text{Hz}]
$$

Với linh kiện kênh dài lý tưởng, hệ số nhiễu dư $\gamma = \frac{2}{3}$; với các tiến trình dưới micromet sâu (90nm / 65nm / 45nm), hạt tải nóng và hiệu ứng kênh ngắn đẩy $\gamma$ lên khoảng **$1{,}0 \text{–} 2{,}0$** tùy $V_{DS}$ và $L$.
- **Trong vùng triode (ví dụ công tắc MOS hay điện trở điều khiển bằng cổng):** Hỗ dẫn $g_m$ có thể bằng 0 khi $V_{DS} = 0$, nhưng điện trở kênh $R_{on}$ vẫn chịu dao động nhiệt chuẩn Nyquist:

$$
\overline{I_{n,\text{triode}}^2} = \frac{4 k T}{R_{on}} = 4 k T g_{ds0}
$$

- **Điều kiện bỏ qua nhiễu điện trở cổng phân bố $R_G$ (Phương trình 7.31–7.33):** Điện trở cổng phân bố đóng góp $\overline{V_{n,RG}^2} = 4 k T \frac{R_G}{3}$ (nối 1 đầu) hoặc $4 k T \frac{R_G}{12}$ (nối 2 đầu). Để nhiễu cổng nhỏ không đáng kể so với nhiễu kênh dẫn, bắt buộc chia ngón nhiều nhánh song song sao cho $\frac{R_G}{3} \ll \frac{\gamma}{g_m}$.

### 2.4. Nhiễu Nhấp nháy $1/f$ và Tần số Giao nhau $f_C$ (§7.2.2, Phương trình 7.34–7.42)
Nguồn điện áp nhiễu nhấp nháy đặt nối tiếp cực cổng tỉ lệ nghịch với tích diện tích cổng $W \cdot L$ và mật độ điện dung oxit $C_{ox}$:

$$
\overline{V_{n,1/f}^2} = \frac{K}{C_{ox} W L} \cdot \frac{1}{f} \quad [\text{V}^2/\text{Hz}], \qquad \overline{I_{n,1/f}^2} = g_m^2 \overline{V_{n,1/f}^2} = \frac{K g_m^2}{C_{ox} W L f} \quad [\text{A}^2/\text{Hz}]
$$

trong đó hằng số phụ thuộc công nghệ $K$ cỡ $10^{-25}\text{–}10^{-24}\text{ V}^2\cdot\text{F}$ (PMOS thường có $K_P$ nhỏ hơn $K_N$ của NMOS đáng kể nhờ kênh dẫn bẫy ít hạt tải bề mặt hơn — tuy phụ thuộc kỹ thuật xử lý nitơ hóa oxit cổng ở công nghệ nanomet).
- **Tích phân nhiễu $1/f$ trên băng tần $[f_L, f_H]$ (Phương trình 7.38–7.39):**

$$
P_{1/f}(f_L, f_H) = \int_{f_L}^{f_H} \frac{K}{C_{ox} W L f}\,df = \frac{K}{C_{ox} W L} \ln\left(\frac{f_H}{f_L}\right)
$$

Mỗi thập kỷ tần số (ví dụ $0{,}1\text{ Hz}\to 1\text{ Hz}$ so với $1\text{ MHz}\to 10\text{ MHz}$) chứa **cùng một năng lượng nhiễu $1/f$ bằng nhau** ($\ln 10 \approx 2{,}303$)!
- **Tần số góc nhiễu nhấp nháy $f_C$ ($1/f$ Corner Frequency, Phương trình 7.41–7.42):** Là tần số (tính bằng **Hz**, xem `NG07-02`!) tại đó PSD nhiễu $1/f$ bằng PSD nhiễu nhiệt của chính linh kiện (hoặc của toàn bộ bộ khuếch đại):

$$
\frac{K}{C_{ox} W L f_C} = \frac{4 k T \gamma}{g_m} \implies f_C = \frac{K}{4 k T \gamma C_{ox}} \cdot \frac{g_m}{W L}
$$

---

## 3. Bất biến Cấu trúc & Các Bẫy Lỗi Kinh điển (Structural Invariants & Traps)

- **[INV-NOISE-01] Bất biến Diện tích Chống Nhiễu $1/f$:** Ở một tỉ số định cỡ $W/L$ và dòng phân cực $I_D$ giữ cố định ($g_m$ không đổi), nếu tăng đồng thời cả $W$ và $L$ lên $\alpha$ lần ($W \to \alpha W, L \to \alpha L$), diện tích cổng tăng $\alpha^2$ lần làm **công suất nhiễu $1/f$ giảm $\alpha^2$ lần** (điện áp nhiễu RMS giảm $\alpha$ lần) và tần số giao nhau $f_C$ hạ thấp đi $\alpha^2$ lần mà không tốn thêm bất kỳ micro-ampe dòng nguồn nào!
- **[TRAP-NOISE-01] Bẫy Đồng Nhất Hai Ký hiệu $\gamma$ Trong Sách Razavi (`NG07-11`):** Razavi dùng cùng chữ cái Hy Lạp $\gamma$ cho cả **hệ số hiệu ứng thân** ($\text{V}^{1/2}$, Chương 2) lẫn **hệ số nhiễu nhiệt kênh dẫn** (không thứ nguyên $\approx 2/3\text{–}1{,}5$, Chương 7)! Trong các bài tập ghi "$\lambda = \gamma = 0$" để bỏ qua hiệu ứng thân, tuyệt đối không bao giờ cho $\gamma_{\text{noise}} = 0$ trong công thức $4kT\gamma g_m$ (nếu không MOSFET biến thành linh kiện siêu dẫn không nhiễu nhiệt!).
- **[TRAP-NOISE-02] Tích Phân Nhiễu $1/f$ Từ $f_L = 0\text{ Hz}$:** Vì $\ln(f_H / 0) = \infty$, tuyệt đối không bao giờ đặt tần số bắt đầu quét tích phân nhiễu $1/f$ tại $0\text{ Hz}$. Giới hạn dưới vật lý được xác định bởi **nghịch đảo thời gian quan sát hệ thống** $f_L \approx \frac{1}{T_{\text{obs}}}$ (ví dụ mạch chạy liên tục 1 giờ có $T_{\text{obs}} = 3600\text{ s} \implies f_L \approx 0{,}28\text{ mHz}$; kể cả kéo dài sang 1 năm thì $\ln(f_H/f_L)$ cũng chỉ tăng rất chậm theo hàm logarit!).
- **[TRAP-NOISE-03] Quên Nhiễu $4kT/R_{on}$ Khi $I_D = 0$ ở Công tắc Lấy mẫu (Passive MOS Switch):** Trong mạch lấy mẫu giữ (track-and-hold) hoặc bộ trộn thụ động (passive mixer), dòng DC qua MOSFET bằng $0\text{ A}$ nên $g_m = \frac{\partial I_D}{\partial V_{GS}}\big|_{V_{DS}=0} = 0$! Nếu người thiết kế hiểu lầm công thức $4kT\gamma g_m$ áp dụng cho mọi vùng, họ sẽ kết luận sai rằng công tắc không có nhiễu nhiệt! Thực tế BSIM4 dùng mô hình thống nhất dựa trên điện tích kênh dẫn / $g_{ds0}$ trả về đúng $\overline{I_n^2} = 4kT g_{ds0} = \frac{4kT}{R_{on}}$ và sinh ra đúng nhiễu lấy mẫu $\frac{kT}{C_H}$ (`topo-mos-and-cmos-sampling-switches`).

---

## 4. Lộ trình Nâng cấp Cấu trúc & Bát giác Đánh đổi (Upgrade Paths & Design Octagon)

| Loại nhiễu thống trị cần xử lý | Kỹ thuật / Cấu trúc đích (Canonical Node) | Nguyên lý triệt nhiễu | Đánh đổi trên Bát giác Thiết kế |
|---|---|---|---|
| Nhiễu nhiệt $\frac{4kT\gamma}{g_m}$ của cặp đầu vào quá lớn | Tăng $g_m$ bằng cách tăng $I_D$ và $W/L$ hoặc đẩy vào vùng nghịch đảo vừa/yếu (`tech-nanometer-vdsmin-gmid-sizing`, `law-stage-and-mirror-noise-rules`) | Đẩy hiệu suất $g_m/I_D$ lên sát cực đại vật lý $\frac{1}{\zeta V_T} \approx 25\text{–}28\text{ V}^{-1}$ hoặc dùng phép nhân tỉ lệ tuyến tính (nhân đôi dòng & $W$ giảm $3\text{ dB}$ nhiễu) | Tăng công suất tiêu thụ hoặc tăng mạnh diện tích $W \Rightarrow$ tăng điện dung ngõ vào $C_{in}$ làm giảm tốc độ |
| Nhiễu nhấp nháy $1/f$ lấn át ở dải tần âm thanh / cảm biến / tham chiếu DC | Tăng diện tích $W \cdot L$ hoặc dùng khử lệch động Auto-Zeroing / CDS / Chopper (`tech-dynamic-offset-cancellation-az-cds`) | Lọc thông cao nhiễu tần số thấp $1/f$ hoặc dời phổ tín hiệu lên trên $f_C$ | Mạch chuyển mạch phức tạp hơn, chịu nhiễu gấp phổ (noise folding) của nhiễu nhiệt băng rộng |
| Cần đánh giá nhiễu tổng thể khi nguồn tín hiệu có trở kháng hữu hạn $Z_S$ | `tech-input-referred-noise-procedure` | Biểu diễn bằng cặp nguồn tương đương $(V_{n,in}, I_{n,in})$ và tích phân trên băng thông nhiễu hiệu dụng $B_n$ | Yêu cầu xét tương quan giữa $V_{n,in}$ và $I_{n,in}$ khi $Z_S$ ngang tầm $Z_{in}$ |

---

## 5. Thích ứng Đa Tiến trình (90nm / 65nm / 45nm) & Cách Kiểm chứng trong Cadence / Spectre

### 5.1. Thích ứng Công nghệ Nanomet (90nm $\to$ 65nm $\to$ 45nm)
- **$f_C$ vọt lên hàng chục MHz ở chiều dài tối thiểu $L_{\min}$:** Như Razavi minh họa ngay tại Chú giải lề tr. 232 (cho linh kiện $W/L = 5\,\mu\text{m}/40\text{ nm}$ tại $I_D = 250\,\mu\text{A}$), diện tích cổng siêu nhỏ $W L = 0{,}2\,\mu\text{m}^2$ đẩy tần số góc $1/f$ ($f_C$) vọt lên tới **vài MHz đến hàng chục MHz**! Do đó trong 90nm/65nm/45nm, ngay cả các bộ khuếch đại băng gốc thông tin vô tuyến vài MHz hay VCO (`topo-vco-tuning-and-phase-noise`) cũng chịu sự chi phối nặng nề của nhiễu $1/f$ nếu vô tình dùng $L = L_{\min}$!
- **Mô hình Nhiễu BSIM4 (`tnoimod` & `fnoimod`) và Chia Ngón Cổng (`nf`):** Trong các PDK thương mại 90nm/65nm/45nm, mô hình nhiễu nhiệt toàn cục `tnoimod=1` (holistic thermal noise) tính thêm cả nhiễu cảm ứng cổng có tương quan, và `fnoimod=1` tính đầy đủ biến thiên mật độ hạt tải cùng biến thiên độ linh động (thay vì $K$ hằng số độc lập phân cực). Đồng thời trên schematic Cadence, bật mô hình điện trở cổng (`rgatemod=1` hoặc khối RF subcircuit) và chia ngón chẵn `nf` sao cho chiều rộng mỗi ngón $W_f = W/nf \le 2\text{–}5\,\mu\text{m}$ để đè nhiễu $R_G$ xuống dưới $5\%$ nhiễu kênh dẫn.

### 5.2. Quy trình Kiểm chứng trong Cadence Virtuoso / Spectre
1. **Chạy Phân tích `noise` Chuẩn xác:**
   - Trong ADE / netlist Spectre: khai báo phân tích `noise ( Vout+ Vout- ) Vsrc dec 50 1 10G` (luôn chỉ định đúng nguồn tín hiệu vào `iprobe`/`Vsrc` để Spectre tính chính xác hàm truyền tới ngõ ra và trả về cả `out` lẫn `in`).
   - Đọc đơn vị cẩn thận trong ViVA Calculator: chọn **`V^2/Hz`** khi muốn cộng/so sánh đóng góp công suất phần trăm, hoặc chọn **`V/sqrt(Hz)`** khi đọc mật độ biên độ chuẩn datasheet.
2. **Bảng Kiểm toán Đóng góp Nhiễu (`Noise Summary`):**
   - Trong ADE chọn *Results $\to$ Print $\to$ Noise Summary*: xuất cả hai bảng **Spot Noise** (tại tần số thấp như `100 Hz` để bắt thủ phạm nhiễu `fn` / $1/f$, và tại tần số giữa dải như `10 MHz` để bắt thủ phạm nhiễu nhiệt `id` / `rn`) lẫn **Integrated Noise** trên băng thông yêu cầu $[f_1, f_2]$! Linh kiện đầu bảng `Noise Summary` chiếm $>50\%$ tổng bình phương chính là mục tiêu duy nhất đáng tối ưu trước tiên.

---

## 6. Mốc Đối chiếu Sách Razavi & Thuật ngữ Chuẩn CLB

### 6.1. Đối chiếu Sách Gốc Razavi (2nd Edition)
- **Chương 7:** *Noise* — §7.1 *Statistical Characteristics of Noise* (tr. 219–227, Phương trình 7.1–7.15), §7.2.1 *Thermal Noise* (tr. 228–233, Phương trình 7.16–7.33), §7.2.2 *Flicker Noise* (tr. 234–236, Phương trình 7.34–7.43).
- **Chú giải Hiệu đính Học thuật CLB (`NG07`):**
  - **`NG07-01` (tr. 225):** Giá trị hiệu dụng $V_{\text{rms}}$ chỉ bằng độ lệch chuẩn $\sigma$ khi quá trình ngẫu nhiên có giá trị trung bình bằng không ($m = 0$).
  - **`NG07-02` (tr. 235):** Thuật ngữ *"1/f Corner"* được CLB dịch là **"tần số góc $1/f$" (`T1127`)** (theo nghĩa "corner" = góc gãy của đường tiệm cận phổ). Cần đặc biệt lưu ý: $f_C$ ở đây **đo bằng Hz**, là tần số giao nhau giữa phổ $1/f$ và phổ nhiễu nhiệt, **không phải** tần số góc $\omega = 2\pi f$ (rad/s) và cũng không phải tần số cắt lọc $-3\text{ dB}$!
  - **`NG07-09` (tr. 258):** Trong lời văn ngay trước Phương trình (7.126), sách in tắt $K/(C_{ox} W L)$ thiếu thừa số $1/f$; công thức mật độ phổ đúng luôn là $K/(C_{ox} W L f)$ như ở (7.34) và (7.126).
  - **`NG07-11` (tr. 268):** Phân biệt rõ hai ý nghĩa của ký hiệu $\gamma$ (hệ số hiệu ứng thân so với hệ số nhiễu nhiệt kênh dẫn).

### 6.2. Bảng Thuật ngữ Chuẩn CLB Vi Mạch Sử dụng trong Thẻ
| Mã CLB | Thuật ngữ Tiếng Anh | Thuật ngữ Tiếng Việt Chuẩn | Ghi chú Ngữ cảnh |
|---|---|---|---|
| `T527` | noise | nhiễu | Phân biệt nhiễu điện tử nội tại (`T1077`) và nhiễu môi trường (`T1079`) |
| `T1029` | power spectral density (PSD) | mật độ phổ công suất | Biểu diễn một phía ($f \ge 0$), đơn vị $\text{V}^2/\text{Hz}$ hoặc $\text{A}^2/\text{Hz}$ |
| `T1063` | correlated | có tương quan | Phải cộng đại số biên độ phức trước khi bình phương |
| `T1064` | uncorrelated | không tương quan | Cộng trực tiếp bình phương mật độ phổ công suất |
| `T1009` | thermal noise | nhiễu nhiệt | Phổ phẳng (nhiễu trắng `T1041`) tỉ lệ với nhiệt độ tuyệt đối $T$ |
| `T1089` | kT/C noise | nhiễu $kT/C$ | Tổng phương sai nhiễu nhiệt trên tụ $C$, độc lập với $R$ |
| `T1177` | channel thermal noise | nhiễu nhiệt kênh dẫn | $\overline{I_n^2} = 4kT\gamma g_m$ đối với MOSFET bão hòa |
| `T392` | flicker noise | nhiễu nhấp nháy | Nhiễu $1/f$ do bẫy giao diện oxit cổng $\text{Si–SiO}_2$ |
| `T1127` | 1/f Corner | tần số góc 1/f | Giao điểm phổ $1/f$ và nhiễu nhiệt, tính bằng Hz (`NG07-02`) |
