---
{
  "id": "law-noise-bandwidth-and-snr-power-scaling",
  "kind": "law",
  "domain": "dynamics-noise-feedback",
  "title_vi": "Định luật Băng thông Nhiễu Tương đương, Bất biến kT/C & Quy luật Nhân Tỉ lệ SNR – Công suất (Noise Bandwidth & SNR-Power Scaling Laws)",
  "title_en": "Equivalent Brickwall Noise Bandwidth, Output-First Noise Integration, Noise Correlation Shortcut, and Fundamental Analog SNR-Power Scaling",
  "summary": "Đúc kết 4 quy luật hệ thống tối hậu khép lại lý thuyết nhiễu tương tự: băng thông nhiễu gạch đứng Bn = (pi/2)*f_-3dB cho hệ 1 cực và sự hội tụ về 1.0*f_-3dB ở bậc cao, cái bẫy tích phân phân kỳ nếu lấy tích phân trực tiếp phổ nhiễu quy về ngõ vào thay vì tích phân ở ngõ ra rồi mới chia độ lợi, bổ đề khử tương quan Vn,in - In,in khi ghép tầng, cùng rào cản nhiệt động lực học 4x công suất cho mỗi +6 dB SNR (+1 bit ENOB).",
  "diagram": "../../diagrams/mos-noise-input-referred.svg",
  "razavi_refs": [
    {
      "chapter": 7,
      "section": "7.7-7.10",
      "pages": "263-267",
      "equations": ["7.143", "7.144", "7.145", "7.146", "7.147", "7.148", "7.149", "7.151", "7.153"]
    }
  ],
  "glossary_codes": ["T050", "T687", "T1139", "T1166", "T1169", "T1455"],
  "process_agnostic": true,
  "roles": {
    "brickwall_noise_bandwidth_bn": "Độ rộng dải tần hình chữ nhật tương đương Bn sao cho V0^2 * Bn bằng đúng tích phân toàn phần phổ nhiễu ngõ ra từ 0 đến vô cực, cho phép quy đổi nhanh mật độ phổ sang điện áp nhiễu hiệu dụng RMS",
    "load_integrating_capacitor_cl": "Tụ điện tích phân tải CL đóng vai trò bộ nhớ năng lượng nhiệt động lực học neo chặt phương sai tổng nhiễu nhiệt đầu ra quanh hằng số bất biến alpha * kT / CL bất kể gm hay R lớn hay nhỏ",
    "linear_impedance_scaler_m": "Hệ số nhân tỉ lệ tuyến tính M ghép song song M bản sao mạch (nhân W, ID, C lên M lần và chia R đi M lần) để hạ phương sai nhiễu đi M lần với cái giá nhân công suất và diện tích lên M lần",
    "interstage_loading_termination": "Trở kháng vào Zin2 của tầng sau khi được gắn làm tải cho tầng trước giúp tự động triệt tiêu vai trò của nguồn dòng nhiễu tương quan In,in2 theo Phụ lục A Chương 7"
  },
  "symptoms_addressed": [
    "underestimating-rms-noise-by-37-percent-when-using-f3db-instead-of-pi-over-2-f3db",
    "divergent-or-inflated-total-noise-from-integrating-input-referred-noise-spectrum-directly",
    "unrealistic-specs-demanding-plus-12db-snr-without-16x-power-budget-or-topology-change",
    "double-counting-or-mishandling-100-percent-correlated-vn-in-and-in-in-in-cascaded-stages"
  ],
  "limitations": [
    "linear-m-fold-scaling-multiplies-input-capacitance-cin-and-input-noise-current-in-in-by-m-overloading-preceding-stage",
    "shrinking-supply-voltage-vdd-in-nanometer-cmos-forces-quadratic-capacitor-and-power-explosion-to-preserve-snr",
    "appendix-a-in-in-elimination-shortcut-fails-when-stage-output-noise-depends-strongly-on-source-termination-zs"
  ],
  "checklists": ["common-mos", "single-stage"]
}
---

## 1. Bản chất Nguyên lý, Sơ đồ Mạch & Vai trò Từng Nhánh Cấu trúc

Trong giai đoạn đầu phân tích mạch, ta thường làm việc với mật độ phổ công suất tại một tần số đơn lẻ (spot noise, đơn vị $\text{V}^2/\text{Hz}$ hoặc $\text{nV}/\sqrt{\text{Hz}}$). Thế nhưng một bộ chuyển đổi ADC, một bộ giải điều chế hay tai người ở ngõ ra không bao giờ "nghe" một tần số đơn lẻ — chúng hứng chịu **tổng năng lượng nhiễu hiệu dụng (total integrated RMS noise, $\mu\text{V}_{\text{rms}}$)** tích lũy trên toàn bộ dải tần $[0, \infty)$ và so sánh nó với biên độ tín hiệu cực đại thông qua **tỷ số tín hiệu trên nhiễu (`T687`, signal-to-noise ratio — SNR)**! Bốn mục cuối cùng của Chương 7 trong sách Razavi (§7.7–§7.10, tr. 263–267) hợp nhất phép phân tích nhiễu transistor thành **4 định luật kiến trúc cấp hệ thống** mà mọi kỹ sư thiết kế chip tương tự phải thuộc nằm lòng trước khi nhận bất kỳ bảng chỉ tiêu kỹ thuật (spec sheet) nào:

![Tổng hợp phép quy đổi nhiễu về cửa vào, tích phân phổ nhiễu qua hàm truyền và nhân tỉ lệ tuyến tính M bản sao giảm nhiễu](../../diagrams/mos-noise-input-referred.svg)

1. **Định luật Đánh đổi Nhiễu – Công suất bằng Co giãn Tỷ lệ Tuyến tính (`T1166`, `T050`, `T1455`, §7.7):** Ghép song song $M$ bản sao giống hệt của bất kỳ bộ khuếch đại nào làm điện áp nhiễu hiệu dụng giảm theo $\frac{1}{\sqrt{M}}$, khóa chặt định luật khắc nghiệt nhất của thế giới tương tự: **muốn tăng thêm $+6\text{ dB}$ SNR (tương đương $+1\text{ bit}$ độ phân giải hiệu dụng ENOB) bằng phép nhân tỉ lệ mạch, bắt buộc phải chi gấp $4\times$ công suất tiêu thụ và gấp $4\times$ diện tích silicon**!
2. **Khái niệm Băng thông Nhiễu Tương đương (`T1169`, Noise Bandwidth $B_n$, §7.8):** Một bộ khuếch đại một cực có độ lợi giảm dần $-20\text{ dB/dec}$ sau tần số cắt $f_{-3\text{dB}}$ không hề cắt đứt nhiễu tại $f_{-3\text{dB}}$ — phần "đuôi phổ" kéo dài từ $f_{-3\text{dB}}$ tới $\infty$ đóng góp thêm tới **$57{,}1\%$ công suất nhiễu** ($B_n = \frac{\pi}{2} f_{-3\text{dB}}$)!
3. **Cấm kỵ Tích phân Trực tiếp Nhiễu Quy về Ngõ vào (§7.9):** Vì $\overline{V_{n,in}^2}(f)$ là đại lượng toán học giả định thu được bằng cách chia phổ nhiễu ngõ ra cho $|H(jf)|^2$, khi $f \to \infty$ làm $|H(jf)| \to 0$, $\overline{V_{n,in}^2}(f)$ giữ phẳng hoặc vọt lên vô cùng khiến tích phân ở ngõ vào phân kỳ! **Mọi phép tích phân nhiễu bắt buộc phải thực hiện tại ngõ ra vật lý trước, rồi mới chia cho độ lợi giữa dải!**
4. **Quy tắc Khử Tương quan $V_{n,in}\text{–}I_{n,in}$ Khi Ghép Nối tầng (§7.10, Phụ lục A):** Trong đa số các tầng MOS mà nhiễu ngõ ra hầu như không phụ thuộc trở kháng nguồn $Z_S$, hai nguồn $V_{n,in}$ và $I_{n,in}$ tương quan $100\%$ theo hệ thức tất định $I_{n,in} = V_{n,in} / Z_{in}(s)$ — cho phép bỏ hẳn nguồn dòng $I_{n,in}$ chỉ bằng cách gắn $Z_{in}(s)$ làm tải cho tầng đứng trước!

---

## 2. Hệ Phương trình Cốt lõi & Tư duy "Nhìn Mạch Đọc Nhanh" (Analysis by Inspection)

### 2.1. Phép Nhân Tỉ Lệ Tuyến Tính $M$ Lần & Rào Cản Nhiệt Động Lực Học $P_{\text{diss}}\text{–SNR–BW}$ (§7.7, Phương trình 7.143–7.144)
Giả sử ta đã tối ưu xong một bộ khuếch đại chuẩn (mọi điện áp phân cực $V_{GS}, V_{DS}$, độ lợi áp $A_v$, biên độ dao động ngõ ra $V_{\text{swing}}$ và băng thông $-3\text{ dB}$ đều đạt chuẩn), nhưng **nhiễu nhiệt quy về ngõ vào (`T1139`)** vẫn cao hơn chỉ tiêu $\sqrt{M}$ lần. Áp dụng **phép nhân tỉ lệ tuyến tính bằng cách điều chỉnh chiều rộng transistor (`T1455`, `T050`, Hình 7.63–7.64; đối chiếu §9.2.3)**: đặt $M$ bản sao giống hệt nhau mắc song song toàn bộ các nút tương ứng — tương đương biến đổi mọi chiều rộng transistor $W_k \to M \cdot W_k$ (giữ nguyên $L_k$), mọi dòng phân cực $I_{D,k} \to M \cdot I_{D,k}$, mọi điện trở $R_k \to R_k / M$, và mọi tụ điện $C_k \to M \cdot C_k$!
- **Chứng minh cho $M = 2$ bản sao song song (Hình 7.64b, Phương trình 7.143–7.144):** Đặt tín hiệu vào bằng $0$, mỗi bản sao có mạch tương đương Thévenin ngõ ra gồm nguồn nhiễu $V_{n1,\text{out}}$ (hoặc $V_{n2,\text{out}}$) mắc nối tiếp trở kháng ra $R_{\text{out}}$. Khi nối song song hai ngõ ra, theo nguyên lý chồng chập tuyến tính (Phương trình 7.143):

$$
V_{n,\text{out}} = \frac{1}{2} \left( V_{n1,\text{out}} + V_{n2,\text{out}} \right)
$$

  Vì nhiễu nhiệt và nhiễu $1/f$ của hai bản sao vật lý tách biệt là **hoàn toàn không tương quan** ($\overline{V_{n1,\text{out}} V_{n2,\text{out}}} = 0$), bình phương trung bình của tổng bằng tổng các bình phương trung bình (Phương trình 7.144):

$$
\overline{V_{n,\text{out}}^2} = \frac{1}{4} \left( \overline{V_{n1,\text{out}}^2} + \overline{V_{n2,\text{out}}^2} \right) = \frac{1}{2} \overline{V_{n1,\text{out}}^2}
$$

- **Tổng quát hóa cho hệ số nhân bất kỳ $M > 0$:** Độ lợi điện áp $A_v$ không đổi, băng thông $f_{-3\text{dB}} = \frac{1}{2\pi (R/M)(M C)} = \frac{1}{2\pi R C}$ không đổi, biên độ dao động cực đại $V_{\text{swing}}$ không đổi, trong khi:

$$
\overline{V_{n,in}^2}(M) = \frac{\overline{V_{n,in}^2}(1)}{M}, \qquad V_{n,in,\text{rms}}(M) = \frac{V_{n,in,\text{rms}}(1)}{\sqrt{M}}, \qquad P_{\text{diss}}(M) = M \cdot P_{\text{diss}}(1), \qquad C_{in}(M) = M \cdot C_{in}(1)
$$

  *(Chú ý mặt trái cực kỳ quan trọng ở dòng cuối §7.7 tr. 263: khi để hở ngõ vào, $M$ bản sao song song bơm tổng dòng nhiễu song song làm **dòng nhiễu quy về ngõ vào tăng lên $M$ lần**: $\overline{I_{n,in}^2}(M) = M \cdot \overline{I_{n,in}^2}(1)$, đồng thời điện dung ngõ vào $C_{in}$ tăng gấp $M$ lần đè nặng lên tầng đứng trước!)*
- **Phương trình Định luật Cơ bản Liên kết Công suất – Dải động (DR/SNR) – Băng thông – Điện áp nguồn $V_{DD}$:**
  Xét một tầng OTA/khuếch đại một cực lái tụ tải $C_L$ với băng thông $f_{-3\text{dB}} = \frac{G_m}{2\pi C_L}$ (suy ra $G_m = 2\pi f_{-3\text{dB}} C_L$), biên độ dao động đỉnh–đỉnh hữu ích chiếm tỉ phần $\eta_{\text{sw}} V_{DD}$ (công suất tín hiệu hình sin cực đại $P_{\text{sig,max}} = \frac{1}{8} \eta_{\text{sw}}^2 V_{DD}^2$), và tổng nhiễu tích phân đầu ra $\overline{V_{n,\text{tot}}^2} = \alpha \frac{k T}{C_L}$ (với $\alpha = \gamma \cdot \text{NF}_{\text{excess}} \sim 1\text{–}4$). Để đạt dải động (hoặc $\text{SNR}_{\max}$ tuyến tính, không tính theo dB) bằng $\text{DR} = \frac{P_{\text{sig,max}}}{\overline{V_{n,\text{tot}}^2}}$:

$$
\text{DR} = \frac{\eta_{\text{sw}}^2 V_{DD}^2}{8 \alpha k T / C_L} \implies C_{L,\min} = \frac{8 \alpha \, k T \, \text{DR}}{\eta_{\text{sw}}^2 V_{DD}^2}
$$

  Với hiệu suất hỗ dẫn tổng thể $\left(\frac{G_m}{I_{\text{tot}}}\right)$, dòng nguồn tối thiểu là $I_{\text{tot}} = \frac{2\pi f_{-3\text{dB}} C_{L,\min}}{(G_m / I_{\text{tot}})}$, cho ra **Định luật Công suất Tối thiểu Tuyệt đối của Mạch Tương tự Tuyến tính**:

$$
P_{\text{diss,\min}} = V_{DD} I_{\text{tot}} = \frac{16 \pi \alpha}{\eta_{\text{sw}}^2 (G_m / I_{\text{tot}})} \cdot \frac{k T \cdot f_{-3\text{dB}} \cdot \text{DR}}{V_{DD}}
$$

  Ba chân lý thiết kế rút ra ngay lập tức từ phương trình bất biến này:
  1. **Quy tắc $4\times$ Công suất cho mỗi $+6\text{ dB}$ SNR ($+1\text{ bit}$ ENOB):** Tăng $+6{,}02\text{ dB}$ SNR đồng nghĩa nhân $\text{DR}$ tuyến tính lên $4\times$ $\implies$ bắt buộc tăng $C_L$ gấp $4\times$, tăng $G_m$ gấp $4\times$, và **tăng công suất tiêu thụ $P_{\text{diss}}$ gấp $4\times$**! (Tăng từ $10\text{ bit}$ lên $16\text{ bit}$ ở cùng băng thông tốn gấp $4^6 = 4096\times$ công suất nếu chỉ nhân tỉ lệ tương tự thuần túy!).
  2. **Hình phạt Đau đớn Khi Hạ Điện áp Nguồn $V_{DD}$ Ở Công nghệ Nanomet:** Ở cùng hiệu suất $G_m / I_{\text{tot}}$ (bị trần vật lý nhiệt động $\frac{q}{n k T} \approx 28\text{ V}^{-1}$ khóa cứng!), khi hạ nguồn từ $V_{DD} = 1{,}8\text{ V}$ xuống $0{,}9\text{ V}$ làm biên độ tín hiệu tối đa sụt $2\times$ ($P_{\text{sig,max}}$ sụt $4\times$), bạn phải nhân tụ $C_L$ lên $4\times$ để nén nhiễu $kT/C_L$ đi $4\times$, dẫn đến $I_{\text{tot}}$ tăng $4\times$ và **công suất $P_{\text{diss}} = V_{DD} I_{\text{tot}}$ TĂNG GẤP $2\times$ khi giảm một nửa $V_{DD}$**! (Ngược hẳn với mạch logic số CMOS nơi $P_{\text{digital}} = C V_{DD}^2 f$ giảm $4\times$!).

### 2.2. Băng thông Nhiễu Tương đương $B_n$ & Bất biến $kT/C$ (§7.8, Phương trình 7.145–7.146)
Với một mạch tuyến tính có phổ công suất nhiễu ngõ ra $S_{v,\text{out}}(f) = \overline{V_{n,\text{out}}^2}(f)$ đạt giá trị phẳng $\overline{V_0^2}$ ở tần số thấp, tổng phương sai nhiễu ngõ ra được định nghĩa qua **băng thông nhiễu (`T1169`, noise bandwidth)** $B_n$ — chiều rộng của một bộ lọc thông thấp "bức tường gạch" (brickwall filter) lý tưởng có cùng độ cao nền $\overline{V_0^2}$ và bao phủ đúng diện tích tích phân dưới đường cong thực tế (Hình 7.65, Phương trình 7.145–7.146):

$$
\overline{V_{n,\text{out,tot}}^2} = \int_{0}^{\infty} \overline{V_{n,\text{out}}^2}(f)\,df \equiv \overline{V_0^2} \cdot B_n \implies B_n = \frac{1}{\overline{V_0^2}} \int_{0}^{\infty} \overline{V_{n,\text{out}}^2}(f)\,df \quad \text{[Hz]}
$$

- **Hệ bậc một (1st-order single-pole system) $H(jf) = \dfrac{H_0}{1 + j (f / f_{-3\text{dB}})}$:** Với nhiễu trắng đi qua hệ một cực:

$$
B_{n,1} = \int_{0}^{\infty} \frac{df}{1 + (f / f_{-3\text{dB}})^2} = f_{-3\text{dB}} \Big[ \arctan(u) \Big]_{0}^{\infty} = \frac{\pi}{2} f_{-3\text{dB}} \approx 1{,}571 \, f_{-3\text{dB}} = \frac{\omega_{-3\text{dB}}}{4} \quad \text{[Hz]}
$$

  *(Nếu lấy nhầm $f_{-3\text{dB}}$ thay cho $B_n$, bạn đánh giá thấp công suất nhiễu đi $1{,}571$ lần — tức tính thiếu $20\%$ điện áp nhiễu RMS hay ảo tưởng dư gần $2\text{ dB}$ SNR!)*
- **Bảng Tra Hệ số Băng thông Nhiễu $B_n / f_{-3\text{dB}}$ Cho Các Bộ Lọc Thông Thấp Bậc Cao (Butterworth & Bậc 2 Tổng quát):**
  Với bộ lọc Butterworth tối đa phẳng bậc $N$ có $|H(jf)/H_0|^2 = \dfrac{1}{1 + (f/f_{-3\text{dB}})^{2N}}$, tích phân Euler chính xác cho $\dfrac{B_{n,N}}{f_{-3\text{dB}}} = \dfrac{\pi / (2N)}{\sin\!\left(\frac{\pi}{2N}\right)}$:

| Bậc Bộ Lọc / Hệ Thống | Hàm Truyền Chuẩn Hóa $|H(jf)/H_0|^2$ | Tỉ số $B_n / f_{-3\text{dB}}$ Chính Xác | Giá trị Số & Hệ Quả Thiết Kế Thực Tế |
|---|---|---|---|
| **Bậc $N = 1$** (Mạng $RC$ đơn, OTA 1 tầng) | $\dfrac{1}{1 + (f/f_{-3\text{dB}})^2}$ | $\dfrac{\pi}{2}$ | **$1{,}571 \, f_{-3\text{dB}}$** (hoặc $\dfrac{1}{4 R C}$ Hz — khử sạch $R$ trong $4kTR \cdot \frac{1}{4RC} = \frac{kT}{C}$!) |
| **Bậc $N = 2$ Butterworth** ($\zeta = \frac{1}{\sqrt{2}}, \text{PM} = 65{,}5^\circ$) | $\dfrac{1}{1 + (f/f_{-3\text{dB}})^4}$ | $\dfrac{\pi}{2\sqrt{2}}$ | **$1{,}111 \, f_{-3\text{dB}}$** (Cắt giảm được $29\%$ công suất nhiễu ngoài dải so với bậc 1!) |
| **Bậc $N = 2$ Toàn cực bất kỳ** ($\omega_n, \zeta$) | $\dfrac{\omega_n^4}{(\omega_n^2 - \omega^2)^2 + 4\zeta^2 \omega_n^2 \omega^2}$ | $B_n = \dfrac{\omega_n}{8 \zeta} = \dfrac{f_n}{4 \zeta}$ [Hz] | **Cảnh báo vọt lố:** Nếu thiếu bù pha làm $\zeta = 0{,}25$ ($\text{PM} \approx 28^\circ$), đỉnh nhọn cộng hưởng thổi $B_n = f_n$ tăng gấp đôi! |
| **Bậc $N = 3$ Butterworth** | $\dfrac{1}{1 + (f/f_{-3\text{dB}})^6}$ | $\dfrac{\pi}{3}$ | **$1{,}047 \, f_{-3\text{dB}}$** |
| **Bậc $N = 4$ Butterworth** | $\dfrac{1}{1 + (f/f_{-3\text{dB}})^8}$ | $\dfrac{\pi / 8}{\sin(\pi/8)}$ | **$1{,}026 \, f_{-3\text{dB}}$** (Thực tế đã hội tụ sát bộ lọc gạch đứng lý tưởng $1{,}000 \, f_{-3\text{dB}}$!) |

### 2.3. Cái Bẫy Phân Kỳ Khi Tích Phân Nhiễu Quy Về Ngõ Vào & Bổ Đề Tương Quan Ghép Tầng (§7.9–§7.10, Phương trình 7.147–7.153)
1. **Tại sao CẤM tích phân trực tiếp $\overline{V_{n,in}^2}(f)$ theo tần số (§7.9, Hình 7.66, Phương trình 7.147–7.148):**
   Xét tầng CS đơn (Hình 7.66: hỗ dẫn $g_m$, tải $R_D \parallel C_L$, bỏ qua nhiễu $R_D$ và $\lambda$). Tại ngõ ra vật lý, dòng nhiễu trắng $4kT\gamma g_m$ bị lọc thông thấp bởi tổng trở tải tạo ra phổ khả tích $\overline{V_{n,\text{out}}^2}(f) = \frac{4kT\gamma g_m R_D^2}{1 + (2\pi f R_D C_L)^2}$, tích phân trên $[0, \infty)$ cho kết quả hữu hạn $\overline{V_{n,\text{out,tot}}^2} = \frac{\gamma g_m R_D k T}{C_L}$. Thế nhưng nếu chia $\overline{V_{n,\text{out}}^2}(f)$ cho bình phương độ lớn hàm truyền $\left|A_v(jf)\right|^2 = \frac{g_m^2 R_D^2}{1 + (2\pi f R_D C_L)^2}$ tại từng tần số, mẫu số $(1 + \omega^2 R_D^2 C_L^2)$ bị giản ước mất, trả lại $\overline{V_{n,in}^2}(f) = \frac{4kT\gamma}{g_m} = \text{hằng số}$ từ $f = 0$ tới $f = \infty$ — tích phân bằng **VÔ CÙNG ($\infty$)**! (Thậm chí nếu có nhiễu từ tầng sau đứng sau cực lọc, $\overline{V_{n,in}^2}(f)$ còn tăng theo $f^2, f^4$ ở tần số cao!).
   **Quy trình chuẩn duy nhất của Razavi (Phương trình 7.147–7.148):** Luôn tích phân phổ nhiễu **tại ngõ ra trước**, sau đó chia căn bậc hai (hoặc phương sai) cho **độ lợi tần số thấp / giữa dải $|A_{v0}| = g_m R_D$**:

$$
V_{n,in,\text{tot,rms}} \triangleq \frac{\sqrt{\int_{f_1}^{f_2} \overline{V_{n,\text{out}}^2}(f)\,df}}{\left|A_{v0}\right|} \xrightarrow{[0, \infty)} \frac{\sqrt{\gamma g_m R_D \dfrac{k T}{C_L}}}{g_m R_D} = \sqrt{\frac{\gamma k T}{g_m R_D C_L}} \qquad \text{(Phương trình 7.147–7.148)}
$$

   *(Lưu ý xác minh thứ nguyên trong Phương trình 7.147–7.148 của sách gốc: vì $\overline{V_{n,\text{out,tot}}^2} = \gamma g_m R_D \frac{kT}{C_L}$, chia phương sai cho $(g_m R_D)^2$ cho $\overline{V_{n,in,\text{tot}}^2} = \frac{\gamma k T}{g_m R_D C_L}$, nên giá trị hiệu dụng RMS là $V_{n,in,\text{tot,rms}} = \sqrt{\frac{\gamma k T}{g_m R_D C_L}}$!)*
2. **Bổ đề Khử Nguồn Dòng Nhiễu Tương Quan $I_{n,in}$ Khi Ghép Tầng (§7.10, Phụ lục A, Hình 7.67–7.69, Phương trình 7.149–7.153):**
   Xét một tầng khuếch đại (chẳng hạn tầng CS có tụ vào $C_{in}$, bỏ qua $C_{GD}$) mà điện áp nhiễu ngõ ra hầu như không đổi dù cửa vào bị ngắn mạch ($Z_S = 0$) hay để hở ($Z_S = \infty$): $\left.V_{n,\text{out}}\right|_{Z_S = 0} \approx \left.V_{n,\text{out}}\right|_{Z_S = \infty}$ (Phương trình 7.149). Khi đó, gọi $H(s) = V_{\text{out}}/V_{in}$ và $Z_{in}(s)$ là trở kháng vào của tầng đó, phép đo ngắn mạch và hở mạch cửa vào cho (Phương trình 7.150–7.151):

$$
V_{n,in}(s) = \frac{V_{n,\text{out}}}{H(s)}, \qquad I_{n,in}(s) = \frac{V_{n,\text{out}}}{Z_{in}(s) H(s)} = \frac{V_{n,in}(s)}{Z_{in}(s)}
$$

   Vì $Z_{in}(s)$ là hàm tất định, $I_{n,in}$ và $V_{n,in}$ **tương quan $100\%$**! Khi ghép tầng này đứng sau một tầng trước có trở kháng ra $Z_S(s)$ (Hình 7.68a), cộng đại số có dấu hai nguồn tương quan tại nút giao tiếp $X$ cho kết quả kỳ diệu (Phương trình 7.152–7.153):

$$
V_{n,X}(s) = V_{n,in}(s) \frac{Z_{in}(s)}{Z_{in}(s) + Z_S(s)} + I_{n,in}(s) \big(Z_{in}(s) \parallel Z_S(s)\big) = V_{n,in}(s) \left[ \frac{Z_{in}}{Z_{in} + Z_S} + \frac{1}{Z_{in}} \frac{Z_{in} Z_S}{Z_{in} + Z_S} \right] \equiv V_{n,in}(s)
$$

   **Định lý Rút Gọn Ghép Tầng Của Razavi (Hình 7.68b):** Với mọi tầng có $V_{n,\text{out}}$ ít nhạy với $Z_S$, bạn **được phép vứt bỏ hoàn toàn nguồn dòng nhiễu $I_{n,in}$ của tầng 2** khỏi phép tính mà không hề sai số ở mọi tần số, miễn là nhớ gắn trở kháng vào $Z_{in2}(s)$ của tầng 2 làm tải cho ngõ ra tầng 1 khi tính hàm truyền của tầng 1! (Còn nếu $V_{n,\text{out}}$ nhạy mạnh với $Z_S$ do hồi tiếp qua $R_F$ hoặc $C_{GD}$ lớn, hãy gộp luôn hai tầng thành một khối duy nhất như Hình 7.69!).

---

## 3. Bất biến Cấu trúc & Các Bẫy Lỗi Kinh điển (Structural Invariants & Traps)

- **[INV-BW-SCALE-01] Bất biến Nhiệt Động Lực Học $kT/C$ — Tại Sao Tăng $g_m$ Của OTA 1 Tầng KHÔNG Giảm Được Tổng Nhiễu RMS Tích Phân!**
  Xét một 5T-OTA hoặc Telescopic OTA 1 tầng đóng vòng làm bộ đệm độ lợi đơn vị lái tụ tải $C_L$: mật độ phổ nhiễu nhiệt quy về cổng giảm tỉ lệ nghịch với $g_{m1}$ ($\overline{V_{n,in}^2}(f) = \frac{8kT\gamma}{g_{m1}}(1 + \eta)$), NHƯNG băng thông vòng kín lại mở rộng tỉ lệ thuận với $g_{m1}$ ($f_{-3\text{dB}} = \frac{g_{m1}}{2\pi C_L} \implies B_n = \frac{\pi}{2} \frac{g_{m1}}{2\pi C_L} = \frac{g_{m1}}{4 C_L}$)! Khi nhân mật độ phổ với $B_n$, **$g_{m1}$ triệt tiêu sạch sành sanh**:

$$
\overline{V_{n,\text{tot}}^2} = \left[ \frac{8 k T \gamma}{g_{m1}} (1 + \eta) \right] \cdot \left( \frac{g_{m1}}{4 C_L} \right) = \frac{2 \gamma (1 + \eta) k T}{C_L}
$$

  Bài học xương máu: nếu mạch không có bộ lọc băng hẹp riêng đứng sau cắt băng thông, tăng dòng phân cực để tăng $g_{m1}$ trên cùng một tụ tải $C_L$ chỉ làm mạch nhanh hơn chứ **tổng điện áp nhiễu hiệu dụng RMS giữ nguyên không đổi đến từng microvolt**! Muốn hạ tổng nhiễu RMS tích phân, con đường duy nhất là **tăng điện dung $C_L$** (hoặc đặt bộ lọc chống chồng phổ cắt hẹp băng thông sau mạch)!
- **[TRAP-BW-SCALE-01] Lẫn Lộn Giữa Trục Tần Số Góc $\omega$ ($\text{rad/s}$) và Tần Số $f$ ($\text{Hz}$) Khi Tính $B_n$ (`NG07-10`, tr. 264):**
  Trong sách Razavi, Phương trình (7.145)–(7.146) tích phân theo $df$ (nên $B_n$ có đơn vị $\text{Hz}$ để nhân với mật độ phổ tính trên $\text{Hz}$), trong khi Hình 7.65 lại vẽ trục hoành theo $\omega_{p1}$! Nhiều kỹ sư viết nhầm $B_n = \frac{\pi}{2} \omega_p$ rồi đem nhân với mật độ phổ $\text{V}^2/\text{Hz}$, gây **sai số thổi phồng công suất nhiễu lên $2\pi \approx 6{,}28$ lần ($+8\text{ dB}$)**! Luôn ghi nhớ kèm đơn vị:

$$
B_n = \frac{\pi}{2} f_p = \frac{\omega_p}{4} \quad [\text{Hz}]
$$

- **[TRAP-BW-SCALE-02] Bấm Nút `Integrated Input Noise` Trong Simulator Từ $1\text{ Hz}$ Đến $100\text{ GHz}$ Ra Hàng Chục Volt Nhiễu Ảo!**
  Trong Cadence ADE / ViVA Calculator, hàm `integ(onoise^2, f1, f2)` cho ra phương sai nhiễu thực tại ngõ ra (luôn hội tụ khi $f_2 \gg f_{-3\text{dB}}$), còn hàm `integ(inoise^2, f1, f2)` lại tích phân thẳng đường cong $\overline{V_{n,in}^2}(f) = \overline{V_{n,\text{out}}^2}(f) / |A_v(jf)|^2$! Nếu đặt giới hạn trên `f2 = 100 GHz` vượt xa băng thông mạch $10\text{ MHz}$, simulator thực hiện đúng phép tích phân vô nghĩa của §7.9 và báo tổng nhiễu quy về ngõ vào hàng $\text{V}_{\text{rms}}$! Luôn tích phân `onoise` trên toàn dải (hoặc qua bộ lọc thu thực tế) rồi chia cho `mag(value(VF("/vout")/VF("/vin"), f_midband))`!
- **[TRAP-BW-SCALE-03] Quên Tích Phân Nhiễu Nhấp Nháy $1/f$ Theo Thang Lôgarit $\ln(f_H / f_L)$:**
  Khác với nhiễu nhiệt tích phân theo $B_n$, tích phân mật độ phổ $S_{1/f}(f) = \frac{K_{\text{eff}}}{f}$ trên dải $[f_L, f_H]$ cho $K_{\text{eff}} \ln\!\left(\frac{f_H}{f_L}\right)$: mỗi thập kỷ tần số ($0{,}1\text{ Hz}\text{–}1\text{ Hz}$ hay $1\text{ MHz}\text{–}10\text{ MHz}$) chứa **cùng một lượng năng lượng nhiễu nhấp nháy bằng nhau** ($\ln 10 \approx 2{,}303\,K_{\text{eff}}$)! Với mạch đo DC mở cửa quan sát trong thời gian $T_{\text{obs}}$ (chẳng hạn $T_{\text{obs}} = 10\text{ s}$), cận dưới hiệu dụng là $f_L \approx \frac{1}{2 T_{\text{obs}}} = 0{,}05\text{ Hz}$ chứ không được đặt $f_L = 0$!

---

## 4. Lộ trình Nâng cấp Cấu trúc & Bát giác Đánh đổi (Upgrade Paths & Design Octagon)

| Rào cản Hệ thống về Băng thông Nhiễu & Công suất | Giải pháp Kiến trúc Đột phá (Canonical Node) | Cách Phá vỡ Giới hạn Tuyến tính | Đánh đổi trên Bát giác Thiết kế |
|---|---|---|---|
| Đuôi nhiễu rộng $1{,}571\,f_{-3\text{dB}}$ của tầng bậc 1 làm tràn nhiễu chồng phổ (aliasing) trước khâu lấy mẫu ADC (`topo-mos-and-cmos-sampling-switches`) | Đặt bộ lọc chống chồng phổ bậc 2–4 Butterworth trước công tắc lấy mẫu | Ép hệ số $B_n / f_{-3\text{dB}}$ từ $1{,}571$ xuống $1{,}03\text{–}1{,}11$, ngăn phổ nhiễu nhiệt tần số cao gấp nếp (fold back) vào băng Nyquist $[0, f_s/2]$! | Thêm công suất/diện tích của mắt lọc tích cực hoặc suy hao trên điện trở thụ động |
| Nhân tỉ lệ tuyến tính $M$ lần tốn $4\times$ công suất cho mỗi $+1\text{ bit}$ ENOB ở dải động cao ($16\text{–}20\text{ bit}$) | Lấy mẫu quá mức kết hợp Định hình Nhiễu $\Delta\Sigma$ (Oversampling + Noise Shaping) hoặc Khuếch đại Đẩy–Kéo / Tái sử dụng dòng (Current Reuse) | Tái sử dụng cùng một dòng $I_D$ nuôi nhiều cặp hỗ dẫn xếp chồng (tăng $G_m / I_{\text{tot}}$ gấp $2\text{–}3\times$), hoặc thu hẹp băng tần tín hiệu so với tần số lấy mẫu $f_s$ | Tăng độ phức tạp xử lý số hậu kỳ (decimation filter) hoặc đòi hỏi thêm khoảng dự trữ điện áp chồng tầng |
| Hạ nguồn cấp xuống $V_{DD} = 0{,}8\text{–}1{,}0\text{ V}$ ở 45nm làm sụt biên độ tín hiệu $V_{\text{swing}}$, ép tăng tụ $C_L$ và công suất gấp đôi | Dùng cấu trúc vi sai hoàn toàn kết hợp tầng ra Rail-to-Rail Class-AB (`topo-two-stage-opamp` + `tech-slew-rate-and-class-ab-opamps`) | Tăng hệ số sử dụng nguồn $\eta_{\text{sw}} = V_{\text{diff,pp}} / V_{DD}$ từ $\sim 0{,}5$ (cascode 1 tầng) lên $\sim 1{,}6\text{–}1{,}8$, giúp giảm $C_{L,\min} \propto 1/\eta_{\text{sw}}^2$ đi **$10\times$** ở cùng SNR! | Phải bù tần số Miller hai tầng và kiểm soát dòng tĩnh lớp AB |

---

## 5. Thích ứng Đa Tiến trình (90nm / 65nm / 45nm) & Cách Kiểm chứng trong Cadence / Spectre

### 5.1. Bảng Ngân Sách Tụ Tải $C_{L,\min}$ & Dòng Tĩnh Tối Thiểu Theo Chỉ Tiêu SNR / ENOB Ở $V_{DD} = 1{,}0\text{ V}$ (65nm / 45nm)
Giả sử thiết kế một bộ đệm/OTA vi sai hoàn toàn ở tiến trình **65nm / 45nm** ($V_{DD} = 1{,}0\text{ V}$, biên độ vi sai đỉnh–đỉnh $V_{\text{diff,pp}} = 1{,}2\text{ V}_{pp} \implies V_{\text{sig,rms}} = \frac{1{,}2}{2\sqrt{2}} = 0{,}424\text{ V}_{\text{rms}}$, hệ số nhiễu tổng hợp $\overline{V_{n,\text{tot}}^2} = \frac{3 k T}{C_L}$ với $kT = 4{,}14 \times 10^{-21}\text{ J}$ ở $300\text{ K}$, băng thông yêu cầu $f_{-3\text{dB}} = 50\text{ MHz}$, hiệu suất cặp đầu vào $g_{m1}/I_{D1} = 20\text{ V}^{-1}$ với $I_{\text{tot}} = 2 I_{D1}$):

| Chỉ tiêu Độ phân giải / SNR | Điện áp Nhiễu Tối đa $V_{n,\text{tot,rms}}$ | Tụ Tải Nhiệt Động Tối thiểu $C_{L,\min} = \frac{3kT}{V_{n,\text{rms}}^2}$ | Hỗ dẫn Yêu cầu $g_{m1} = 2\pi f_{-3\text{dB}} C_L$ | Dòng Tĩnh Lõi $I_{\text{tot}}$ & Công suất ở $1{,}0\text{ V}$ | Quy luật Chế ngự Thiết kế Thực Tế |
|---|---|---|---|---|---|
| **$8\text{ bit}$ ($\text{SNR} = 50\text{ dB}$)** | $1340\,\mu\text{V}_{\text{rms}}$ | $0{,}007\text{ pF}$ *(7 fF!)* | $2{,}2\,\mu\text{S}$ | *(Bị giới hạn bởi ký sinh & matching, chọn $C_L \ge 50\text{ fF}$, $I_{\text{tot}} \approx 20\,\mu\text{A}$)* | **Chế độ Ký sinh / Matching chi phối** (nhiễu nhiệt dư dả, không tốn điện vì $kT/C$) |
| **$10\text{ bit}$ ($\text{SNR} = 62\text{ dB}$)** | $336\,\mu\text{V}_{\text{rms}}$ | $0{,}11\text{ pF}$ | $34{,}6\,\mu\text{S}$ | $I_{\text{tot}} \approx 3{,}5\,\mu\text{A}$ *(thực tế $\sim 30\,\mu\text{A}$ do slew rate)* | Điểm chuyển giao giữa giới hạn Slew Rate/Ký sinh và giới hạn Nhiễu nhiệt |
| **$12\text{ bit}$ ($\text{SNR} = 74\text{ dB}$)** | $84{,}4\,\mu\text{V}_{\text{rms}}$ | **$1{,}74\text{ pF}$** | $0{,}55\text{ mS}$ | **$55\,\mu\text{A}$ ($55\,\mu\text{W}$)** | **Chế độ Nhiễu Nhiệt $kT/C$ bắt đầu thống trị hoàn toàn!** |
| **$14\text{ bit}$ ($\text{SNR} = 86\text{ dB}$)** | $21{,}1\,\mu\text{V}_{\text{rms}}$ | **$27{,}9\text{ pF}$** *($16\times$)* | $8{,}76\text{ mS}$ *($16\times$)* | **$0{,}88\text{ mA}$ ($0{,}88\text{ mW}$)** *($16\times$)* | Gấp đúng $4^2 = 16\times$ tụ và công suất so với $12\text{ bit}$! |
| **$16\text{ bit}$ ($\text{SNR} = 98\text{ dB}$)** | $5{,}30\,\mu\text{V}_{\text{rms}}$ | **$442\text{ pF}$** *($256\times$)* | $139\text{ mS}$ *($256\times$)* | **$13{,}9\text{ mA}$ ($13{,}9\text{ mW}$)** *($256\times$)* | Tụ $442\text{ pF}$ không thể đặt trên chip ở băng Nyquist $50\text{ MHz}$ $\implies$ bắt buộc kiến trúc Pipelined/Oversampling! |

### 5.2. Quy trình Kiểm chứng trong Cadence Virtuoso / Spectre (Đo Đúng $B_n$, RMS Noise & Kiểm Tra Nhân Tỉ Lệ `m`)
Trong Spectre, mọi MOSFET, điện trở và tụ điện đều hỗ trợ tham số nhân bản song song `m` (multiplicity factor) ngay trên schematic — đây chính là hiện thực phần cứng chính xác 100% của phép nhân tỉ lệ tuyến tính $M$ trong §7.7! Script OCEAN dưới đây thực hiện phép tích phân chuẩn xác tại ngõ ra (§7.9) và kiểm chứng đồng thời $B_n$ lẫn định luật $1/\sqrt{M}$:

```lisp
; === OCEAN Script: Tinh dung Total Integrated Input-Referred Noise (§7.9) & kiem chung Bn, M-scaling ===
simulator('spectre)
design("libName" "tb_ota_snr_scaling" "schematic")
resultsDir("./sim_noise_bw")

foreach(M_scale '(1 4)
    desVar("M_copy" M_scale) ; Nhan song song m=M_copy tren toan bo transistor/R/C
    analysis('ac ?start 1 ?stop 100G ?dec 50)
    analysis('noise ?start 1 ?stop 100G ?dec 50 ?onode "/vout_p" ?oprobe "" ?iprobe "/VSRC_IN")
    run()

    ; 1. Lay do loi giua dai Av0 va tan so cat -3dB
    selectResult('ac)
    tf_mag = mag(VF("/vout_p") - VF("/vout_n"))
    Av0    = value(tf_mag 1e3)
    f_3dB  = cross(tf_mag (Av0 / sqrt(2.0)) 1 "falling")

    ; 2. Tich phan PHUONG SAI NHIEU NGO RA tren toan pho [1 Hz, 100 GHz], SAU DO moi chia cho Av0!
    selectResult('noise)
    onoise_psd = getData("out" ?result "noise")^2
    V0_sq_out  = value(onoise_psd 1e4) ; Nen nhieu nhiet phang o 10 kHz (tren goc 1/f)
    Vno_tot_sq = integ(onoise_psd 1 1e11)
    Vni_rms_ok = sqrt(Vno_tot_sq) / Av0
    Bn_meas    = Vno_tot_sq / V0_sq_out

    printf("[M=%d] Av0=%.2f | f_3dB=%.2f MHz | Bn=%.2f MHz (Bn/f_3dB=%.3f) | Vn_in_rms=%.2f uVrms\n"
           M_scale Av0 (f_3dB/1e6) (Bn_meas/1e6) (Bn_meas/f_3dB) (Vni_rms_ok*1e6))
)
; Kiem chung ky vong: Bn/f_3dB ~ 1.571 (cho 1 cuc), va Vn_in_rms(M=4) = 0.50 * Vn_in_rms(M=1)!
```

---

## 6. Mốc Đối chiếu Sách Razavi & Thuật ngữ Chuẩn CLB

### 6.1. Đối chiếu Sách Gốc Razavi (2nd Edition) & Chú giải Học thuật CLB
- **Chương 7:** §7.7 *Noise-Power Trade-Off* (tr. 263–264: Hình 7.63–7.64, Phương trình 7.143–7.144; đối chiếu thêm Chương 9 §9.2.3 *Linear Scaling* tr. 354–355), §7.8 *Noise Bandwidth* (tr. 264: Hình 7.65, Phương trình 7.145–7.146), §7.9 *Problem of Input Noise Integration* (tr. 265: Hình 7.66, Phương trình 7.147–7.148), §7.10 *Appendix A: Problem of Noise Correlation* (tr. 265–267: Hình 7.67–7.69, Phương trình 7.149–7.153).
- **Chú giải Hiệu đính Học thuật CLB (`source_issues.json` — Chương 07):**
  - **`NG07-10` (tr. 264, Hình 7.65 & Phương trình 7.145–7.146):** Các tích phân định nghĩa $B_n$ ở (7.145)–(7.146) lấy vi phân theo $df$ (đơn vị $\text{Hz}$), trong khi Hình 7.65 vẽ phổ theo trục tần số góc $\omega$ ($\text{rad/s}$). Khi đổi biến $df = d\omega / (2\pi)$, phát biểu ở cuối §7.8 rằng băng thông nhiễu của hệ một cực bằng $\frac{\pi}{2}$ lần tần số cực phải hiểu chính xác là **$B_n = \frac{\pi}{2} f_p = \frac{\omega_p}{4}\text{ [Hz]}$** (tuyệt đối không phải $\frac{\pi}{2} \omega_p$ tính bằng $\text{Hz}$!).
  - **`NG07-01` & `NG07-02` (tr. 225 & tr. 235, đối chiếu nền tảng khi tính tổng nhiễu hiệu dụng):** Giá trị hiệu dụng RMS chỉ trùng với độ lệch chuẩn $\sigma$ khi quá trình nhiễu có trung bình bằng không ($m = 0$); và thuật ngữ *"1/f Corner"* ($f_C$, dịch chuẩn là *tần số góc 1/f*) là tần số giao nhau giữa mật độ phổ nhiễu $1/f$ và nhiễu nhiệt đo bằng **$\text{Hz}$**, không phải tần số góc $\omega = 2\pi f$ ($\text{rad/s}$) và cũng không phải tần số cắt $-3\text{ dB}$ của bộ lọc!

### 6.2. Bảng Thuật ngữ Chuẩn CLB Vi Mạch Sử dụng trong Thẻ
| Mã CLB | Thuật ngữ Tiếng Anh | Thuật ngữ Tiếng Việt Chuẩn | Ghi chú Ngữ cảnh |
|---|---|---|---|
| `T1169` | noise bandwidth | băng thông nhiễu | $B_n = \frac{\pi}{2} f_{-3\text{dB}} \approx 1{,}571\,f_{-3\text{dB}}$ cho hệ thông thấp bậc 1 |
| `T1166` | noise-power trade-off | đánh đổi giữa nhiễu và công suất | Giảm $2\times$ điện áp nhiễu RMS ($+6\text{ dB}$ SNR) đòi hỏi $4\times$ công suất |
| `T050` | linear scaling | co giãn tỷ lệ tuyến tính | Nhân đồng thời $W, I_D, C$ lên $M$ lần và chia $R$ đi $M$ lần |
| `T1455` | linear scaling by adjusting the transistor widths | phép nhân tỉ lệ tuyến tính bằng cách điều chỉnh chiều rộng transistor | Bảo toàn mọi điểm phân cực DC, độ lợi $A_v$, biên độ ra và băng thông |
| `T687` | signal-to-noise ratio | tỷ số tín hiệu trên nhiễu (SNR) | Gắn chặt với kích thước tụ tích phân tải tối thiểu $C_{L,\min} \propto \text{DR} \cdot kT / V_{DD}^2$ |
| `T1139` | input-referred thermal noise | nhiễu nhiệt quy về ngõ vào | Đại lượng giả định toán học: phải tích phân tại ngõ ra trước rồi mới chia $|A_{v0}|$ |
