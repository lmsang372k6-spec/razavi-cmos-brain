---
{
  "id": "concept-pll-nonidealities-spurs-jitter",
  "kind": "concept",
  "domain": "sampled-and-clocked",
  "title_vi": "Bất lý tưởng PFD/CP, Vạch phổ Tham chiếu (Spurs), Đối ngẫu Jitter/Tạp âm Pha, Vòng khóa trễ (DLL) & Tổng hợp Tần số",
  "title_en": "PLL Nonidealities, Reference Spurs, Jitter/Phase-Noise Duality, DLLs & Frequency Synthesis",
  "summary": "Hệ quy luật thực chiến quyết định chất lượng phổ và jitter của hệ thống khóa pha: cơ chế vùng chết PFD (dead zone) và cách sửa bằng xung xóa Trst, bốn nguồn sinh gợn sóng Vcont tạo vạch phổ ký sinh tại w_out +- w_REF, quy luật đối ngẫu lọc thông thấp H(s) cho nhiễu tham chiếu/CP/bộ chia và lọc thông cao 1 - H(s) cho nhiễu VCO, đối chiếu vòng khóa trễ (DLL) không có cực 1/s và phép nhân tần số qua bộ chia hồi tiếp /M.",
  "diagram": "../../diagrams/charge-pump-type2-pll.svg",
  "razavi_refs": [
    {
      "chapter": 16,
      "section": "16.3.1",
      "pages": "677-681",
      "equations": []
    },
    {
      "chapter": 16,
      "section": "16.3.2",
      "pages": "681-683",
      "equations": ["16.48"]
    },
    {
      "chapter": 16,
      "section": "16.4",
      "pages": "683-685",
      "equations": []
    },
    {
      "chapter": 16,
      "section": "16.5",
      "pages": "685-689",
      "equations": ["16.49", "16.50", "16.51", "16.52", "16.53", "16.54", "16.56"]
    }
  ],
  "glossary_codes": [
    "T014",
    "T016",
    "T020",
    "T029",
    "T047",
    "T052",
    "T063",
    "T064",
    "T070",
    "T088",
    "T090",
    "T392",
    "T1009",
    "T1025",
    "T1169",
    "T1389",
    "T2015",
    "T2079",
    "T2087"
  ],
  "process_agnostic": true,
  "roles": {
    "pfd_reset_delay_anti_deadzone": "Độ trễ đường xóa cố ý Trst (TP) bật đồng thời cả hai công tắc UP/DN quanh Delta_phi = 0 để xóa sổ vùng chết độ lợi bằng không.",
    "charge_sharing_bootstrap_buffer": "Bộ đệm độ lợi đơn vị ghim điện thế các nút trong của bơm điện tích bằng Vcont khi ngắt khóa, triệt tiêu hiện tượng chia sẻ điện tích với tụ lọc vòng.",
    "noise_transfer_duality_filter": "Cơ chế phân chia băng thông vòng w_loop: lọc thông thấp H(s) cho nhiễu ngõ vào/PFD/CP/Divider và lọc thông cao 1 - H(s) cho nhiễu VCO.",
    "feedback_divider_and_vcdl": "Bộ đếm chia /M trong PLL thực hiện nhân tần số chính xác f_out = M*f_REF (làm giảm KVCO hiệu dụng đi M lần), đối lập với đường trễ VCDL bậc không trong vòng khóa trễ (DLL)."
  },
  "symptoms_addressed": [
    "random-wander-jitter-explosion-from-pfd-dead-zone",
    "reference-spurs-sidebands-at-f-out-plus-minus-f-ref",
    "suboptimal-pll-loop-bandwidth-causing-excessive-integrated-rms-jitter",
    "clock-distribution-skew-and-multiphase-jitter-accumulation"
  ],
  "limitations": [
    "anti-deadzone-reset-pulse-amplifies-up-down-mismatch-reference-spurs",
    "frequency-divider-m-multiplies-in-band-reference-and-cp-phase-noise-by-m-squared",
    "dll-cannot-multiply-or-synthesize-variable-frequencies",
    "dll-harmonic-false-locking-to-multiple-clock-periods-k-times-tin"
  ],
  "checklists": [
    "common-mos",
    "oscillator-and-pll",
    "feedback-and-stb",
    "current-mirror",
    "layout-and-matching"
  ]
}
---

## 1. Bản chất Nguyên lý, Sơ đồ Mạch & Vai trò Từng Nhánh Cấu trúc

Một vòng khóa pha bơm điện tích Loại II lý tưởng hứa hẹn sai số pha tĩnh bằng không, đường điều khiển $V_{cont}$ phẳng tuyệt đối ở trạng thái khóa và phổ sóng mang thuần khiết. Tuy nhiên, khi hiện thực hóa ở mức transistor CMOS (§16.3–16.5), bốn nhóm hiện tượng vật lý quyết định sự sống còn của toàn bộ hệ thống định thời và tổng hợp tần số: **(1) Vùng chết PFD và bốn cơ chế sinh vạch phổ ký sinh tham chiếu (reference spurs)**, **(2) Tính đối ngẫu lọc tần số đối với jitter / tạp âm pha**, **(3) Sự ra đời của vòng khóa trễ (Delay-Locked Loop — DLL, `T029`)**, và **(4) Quy luật co giãn động học khi chèn bộ chia tần số $\div M$**.

![Sơ đồ kiến trúc tổng hợp tần số PLL bơm điện tích có bộ chia /M để phân tích nhiễu, spur và đối chiếu DLL](../../diagrams/charge-pump-type2-pll.svg)

### 1.1. Vùng chết (Dead Zone) của PFD & Bốn Nguồn gốc Sinh Vạch phổ Tham chiếu (§16.3.1)
- **Vùng chết $\pm\phi_0$ và Giải pháp Xung xóa Đồng thời $T_P$ (Hình 16.39–16.43)**: Nếu khi $|\Delta\phi| < \phi_0$ rất nhỏ, xung lỗi từ PFD quá hẹp không kịp nạp điện dung cổng để vượt ngưỡng mở công tắc trong **bơm điện tích** (`charge pump` `T016`), dòng bơm bằng $0$ làm độ lợi vòng sụp về $0$! Bên trong khoảng $[-\phi_0, +\phi_0]$, VCO trôi tự do không có hồi tiếp sửa sai, gây bùng nổ **jitter** (`T047` — biến thiên ngẫu nhiên thời điểm cắt không). Cách khắc phục chuẩn là thiết kế đường `Reset` của PFD có độ trễ xác định $T_P \approx 5 T_D$ (thường $150 \sim 400\text{ ps}$) sao cho ngay tại $\Delta\phi = 0$, cả hai xung $Q_A$ và $Q_B$ đều bật đủ cao để mở hoàn toàn cả hai công tắc UP/DN cùng lúc, bảo toàn đạo hàm dòng tịnh $dI_{\text{net}}/d\Delta\phi \neq 0$ mượt qua gốc tọa độ.
- **Mặt trái của xung đồng thời $T_P$ — Bốn cơ chế bơm gợn sóng tuần hoàn $f_{REF}$ lên $V_{cont}$**: Vì mỗi chu kỳ tham chiếu $T_{REF}$, cả hai công tắc UP (PMOS $M_4$) và DN (NMOS $M_3$) đều đóng mở trong khoảng $T_P$, bất kỳ sự mất cân đối nhỏ nào cũng tạo nhiễu nhấp nhô tuần hoàn trên $V_{cont}$ và điều tần VCO đẻ ra **vạch phổ tham chiếu (reference spurs)** tại $\omega_{out} \pm k\omega_{REF}$:
  1. *Lệch trễ điều khiển công tắc ($\overline{Q_A}$ qua cổng đảo so với $Q_B$ đi thẳng, Hình 16.44)*: Bơm cặp xung dòng lưỡng cực $+I_P$ rồi $-I_P$ lệch giờ nhau; phải cân bằng trễ bằng cách chèn một cổng truyền dẫn CMOS luôn dẫn trên nhánh $Q_B$ (Hình 16.44c).
  2. *Sai lệch linh kiện (`mismatch` `T052`) giữa dòng $I_{UP}$ và $I_{DN}$ & Điều chế chiều dài kênh theo $V_{cont}$ (Hình 16.45)*: Khi $I_{UP} \neq I_{DN}$ trong khoảng $T_P$, vòng khóa pha buộc phải tự dịch sang một **độ lệch pha tĩnh bù $\Delta\phi_{\text{off}}$** sao cho tổng điện tích tịnh trong cả chu kỳ bằng $0$, nhưng trong suốt khoảng $T_P$ dòng lệch vẫn nạp rồi xả làm $V_{cont}$ nhảy bậc tuần hoàn! Tệ hơn, ở MOSFET kênh ngắn có $r_o$ thấp, khi $V_{cont}$ đổi mức để quét tần số VCO thì $I_{UP}(V_{cont})$ và $I_{DN}(V_{cont})$ tách xa nhau ra.
  3. *Bất đối xứng **phun điện tích** (`charge injection` `T014` — tuyệt đối không dịch nhầm thành bơm điện tích!) và xuyên thông xung nhịp (clock feedthrough)* giữa công tắc PMOS $M_4$ và NMOS $M_3$ khi ngắt.
  4. *Chia sẻ điện tích (Charge Sharing) tại nút trong của nguồn dòng (Hình 16.46–16.47)*: Khi hai công tắc $S_1, S_2$ ngắt, hai nguồn dòng $M_1, M_2$ kéo tuột nút ký sinh $X$ xuống $0\text{ V}$ và đẩy nút $Y$ lên $V_{DD}$. Ở nhịp so pha kế tiếp khi $S_1, S_2$ đóng lại, tụ lọc $C_1/C_2$ phải bơm điện tích nạp/xả $C_X, C_Y$ về mức $V_{cont}$, gây sụt/vọt áp trên $V_{cont}$ (trừ khi $V_{cont}$ tình cờ nằm đúng giữa!). Giải pháp kinh điển là dùng bộ đệm độ lợi đơn vị (unity-gain buffer) nối qua cặp công tắc phụ đảo pha $S_3, S_4$ để **tự thiết lập / ghim thế (bootstrapping `T2015`)** $V_X = V_Y = V_{cont}$ trong suốt thời gian chờ!

### 1.2. Vòng khóa trễ (Delay-Locked Loop — DLL, §16.4) so với PLL
Khi ứng dụng chỉ cần tạo nhiều pha xung nhịp cách đều cực chuẩn (ví dụ 4 pha cách nhau đúng $T_{in}/4$) hoặc khử trễ đệm xung nhịp (skew reduction) mà **không cần thay đổi tần số**, việc dùng VCO trong PLL gây hai bất lợi: nhiễu cạnh xung bị lưu chuyển tích lũy vòng quanh VCO qua nhiều chu kỳ, và cực $1/s$ của VCO gây nguy cơ mất ổn định bậc cao. **Vòng khóa trễ (DLL, Hình 16.53–16.54)** thay VCO bằng **đường trễ điều khiển bằng điện áp (Voltage-Controlled Delay Line — VCDL)** nhận thẳng $CK_{in}$ ở đầu vào: mỗi cạnh xung nhiễu đi hết VCDL là thoát ra ngoài biến mất vĩnh viễn (**không tích lũy jitter qua nhiều chu kỳ**!), và hàm truyền từ $V_{cont}$ sang pha ra chỉ là hằng số khuếch đại $\Phi_{out}(s)/V_{cont}(s) = K_{VCDL}$ (**không có cực $1/s$**!).

| Tiêu chí Kiến trúc | Vòng khóa pha Loại II (CP-PLL + Bộ chia $/M$) | Vòng khóa trễ Bơm điện tích (CP-DLL) |
| :--- | :--- | :--- |
| **Phần tử tạo pha** | VCO tự dao động: $\Phi_{out}(s)/V_{cont}(s) = K_{VCO}/s$ | Đường trễ VCDL truyền thẳng: $\Phi_{out}(s)/V_{cont}(s) = K_{VCDL}$ |
| **Bậc hệ thống & Ổn định** | Hai cực gốc tọa độ $1/s^2 \implies$ bắt buộc bù zero $R_P C_1$. | Chỉ 1 cực gốc tọa độ $1/s$ (từ CP+$C_1$) $\implies$ **ổn định vô điều kiện bậc 1**! |
| **Tích lũy Jitter nội tại** | Cạnh lỗi quay vòng trong VCO tích lũy nhiễu qua nhiều chu kỳ. | Không tái tuần hoàn; cạnh lỗi đi hết dây trễ 1 chu kỳ là bị xóa sạch. |
| **Tổng hợp tần số / Điểm yếu** | Nhân tần số linh hoạt $f_{out} = M f_{REF}$. | **Không thể nhân tần số** ($f_{out} = f_{in}$); dễ bị khóa nhầm bội chu kỳ $k T_{in}$! |

## 2. Hệ Phương trình Cốt lõi & Tư duy "Nhìn Mạch Đọc Nhanh" (Analysis by Inspection)

### 2.1. Sai lệch Pha Tĩnh & Biên độ Vạch phổ Tham chiếu do Sai lệch Dòng UP/DN
Khi tồn tại độ lệch dòng $\Delta I = I_{UP} - I_{DN}$ trong suốt độ rộng xung xóa đồng thời $T_P$ (Bài tập 16.12, Hình 16.45b), để điện tích trung bình mỗi chu kỳ $T_{REF}$ bằng $0$, vòng khóa pha tự xác lập độ lệch pha tĩnh $\Delta\phi_{\text{off}}$:

$$\Delta I \cdot T_P = I_P \cdot \frac{|\Delta\phi_{\text{off}}|}{2\pi} T_{REF} \implies |\Delta\phi_{\text{off}}| = 2\pi \left(\frac{\Delta I}{I_P}\right)\left(\frac{T_P}{T_{REF}}\right)$$

Điện tích lệch $\Delta Q \approx \Delta I \cdot T_P$ đập vào tụ lọc gợn $C_2$ ở tần số $\omega_{REF} = 2\pi / T_{REF}$ tạo thành phần cơ bản trên $V_{cont}$ cỡ $V_m \approx \frac{\Delta Q}{C_2}$ (hoặc lọc thêm qua cực $\omega_{p3}$), qua VCO sinh ra cặp **vạch phổ ký sinh tham chiếu (reference spurs)** tại $\omega_{out} \pm \omega_{REF}$ có mức tỉ đối xấp xỉ $\frac{A_{\text{spur}}}{A_{\text{carrier}}} = \frac{K_{VCO} V_m}{2\omega_{REF}}$. *Nhìn mạch đọc nhanh*: muốn giảm spur $20\text{ dB}$, hoặc giảm $K_{VCO}$, hoặc giảm $T_P$ vừa đủ thoát vùng chết, hoặc ghép thêm mắt lọc RC thụ động sau $C_2$, hoặc dùng cascode + bootstrap cân bằng $I_{UP} = I_{DN}$!

### 2.2. Định luật Đối ngẫu Hàm truyền Jitter & Tạp âm Pha trong PLL (§16.3.2)
Biểu diễn tín hiệu gần tuần hoàn dưới dạng $x(t) = A\cos[\omega_0 t + \phi_n(t)]$, trong đó phổ của pha dư ngẫu nhiên $S_{\phi}(f)$ là tạp âm pha còn độ lệch chuẩn thời điểm cắt không là jitter. Xét đồng thời hai nguồn nhiễu chính (Hình 16.50–16.51, PT 16.48):
1. **Nhiễu từ ngõ vào tham chiếu $\Phi_{in}(s)$ (và nhiễu nội dải của PFD, bơm điện tích, bộ chia quy về ngõ vào)**: Đi qua **hàm truyền thông thấp (Low-Pass Transfer Function)** $H(s)$:

$$\frac{\Phi_{out}(s)}{\Phi_{in}(s)} = H(s) = \frac{2\zeta\omega_n s + \omega_n^2}{s^2 + 2\zeta\omega_n s + \omega_n^2} \quad \left(\text{hoặc nhân } M \text{ khi có bộ chia } \div M\right)$$

Jitter biến thiên chậm ($\omega \ll \omega_{\text{loop}}$) trên xung tham chiếu đi thẳng ra ngõ ra (bị nhân biên độ pha lên $M$ lần, tức công suất tạp âm pha tăng $+20\log_{10} M\text{ dB}$!); jitter biến thiên nhanh ($\omega \gg \omega_{\text{loop}}$) bị vòng lọc chặn lại.
2. **Nhiễu pha tự sinh của VCO $\Phi_{VCO}(s)$**: Đi qua **hàm truyền sai số thông cao (High-Pass Transfer Function)** $1 - H(s)$ (PT 16.48):

$$\frac{\Phi_{out}(s)}{\Phi_{VCO}(s)} = 1 - H(s) = \frac{s^2}{s^2 + 2\zeta\omega_n s + \omega_n^2}$$

Trôi pha chậm và nhiễu $1/f^3, 1/f^2$ tần số thấp của VCO ($\omega \ll \omega_{\text{loop}}$) bị vòng khóa pha phát hiện và nén mạnh theo độ dốc $+40\text{ dB/dec}$ khi $\omega \to 0$; ngược lại, nhiễu pha tần số cao của VCO ($\omega \gg \omega_{\text{loop}}$) vượt quá tốc độ phản ứng của bộ lọc vòng nên lọt thẳng ra ngõ ra với độ lợi bằng $1$!

**Nguyên lý chọn Băng thông Vòng Tối ưu ($\omega_{\text{loop,opt}}$)**: Tổng phổ tạp âm pha ngõ ra là $S_{\phi,\text{out}}(f) = |H_{\text{in}}(jf)|^2 S_{\phi,\text{in,eq}}(f) + |1 - H(jf)|^2 S_{\phi,\text{VCO}}(f)$. Băng thông vòng tối ưu làm cực tiểu jitter RMS tích phân toàn dải chính là **tần số giao cắt nơi sàn nhiễu quy đổi của nhánh Tham chiếu/PFD/CP (đã nhân $M^2$) cắt ngang đường cong tạp âm pha tự do của VCO**!

### 2.3. Phép Nhân Tần số & Co giãn Thông số Động học qua Bộ chia $\div M$ (§16.5.1)
Khi chèn bộ đếm chia tần $\div M$ vào nhánh hồi tiếp từ ngõ ra VCO về PFD (Hình 16.55b–16.57), điều kiện khóa pha ép $f_D = f_{out}/M = f_{REF} \implies f_{out} = M f_{REF}$ (tổng hợp tần số bước kênh $f_{REF}$ với độ chính xác ppm kế thừa nguyên vẹn từ thạch anh $f_{REF}$!). Về mặt động học vòng kín, tổ hợp $(\text{VCO} + \div M)$ tương đương hệt một VCO có độ lợi giảm đi $M$ lần là $K_{VCO}/M$ (PT 16.49–16.54):

$$H(s) = \frac{\dfrac{I_P K_{VCO}}{2\pi C_1}(R_P C_1 s + 1)}{s^2 + \dfrac{I_P}{2\pi}\dfrac{K_{VCO}}{M} R_P s + \dfrac{I_P}{2\pi C_1}\dfrac{K_{VCO}}{M}}, \qquad \omega_n = \sqrt{\frac{I_P}{2\pi C_1}\frac{K_{VCO}}{M}}, \qquad \zeta = \frac{R_P}{2}\sqrt{\frac{I_P C_1}{2\pi}\frac{K_{VCO}}{M}}$$

*Hệ quả sống còn*: Khi $H(s) \to M$ ở $s \to 0$, việc tăng hệ số chia $M$ làm giảm cả $\omega_n \propto 1/\sqrt{M}$, giảm cả $\zeta \propto 1/\sqrt{M}$ và kéo dài thời gian xác lập $(\zeta\omega_n)^{-1} = \frac{4\pi M}{R_P I_P K_{VCO}}$ gấp $M$ lần! Do đó, trong bộ tổng hợp tần số đa kênh có $M$ thay đổi rộng, **bơm điện tích luôn được thiết kế khả trình $I_P \propto M$** để giữ thương số $I_P / M = \text{hằng số}$, cố định $\omega_n$, $\zeta$ và dự trữ pha không đổi trên mọi kênh tần số!

### 2.4. Ví dụ Định lượng Thực chiến: Ước tính Sai lệch Pha Tĩnh & Reference Spur từ Sai lệch Bơm điện tích
Xét bộ tổng hợp tần số $f_{out} = 2.4\text{ GHz}$, $f_{REF} = 20\text{ MHz}$ ($T_{REF} = 50\text{ ns}$), $K_{VCO,\text{Hz}} = 80\text{ MHz/V}$, tụ lọc gợn $C_2 = 6.7\text{ pF}$, xung xóa chống vùng chết $T_P = 250\text{ ps}$, dòng bơm danh định $I_P = 200\,\mu\text{A}$ nhưng chịu sai lệch dòng tĩnh giữa PMOS và NMOS là $\Delta I = I_{UP} - I_{DN} = 4\,\mu\text{A}$ ($2\%$):
1. **Độ lệch pha tĩnh tự xác lập ở ngõ vào PFD**:
   - $|\Delta\phi_{\text{off}}| = 2\pi \left(\frac{4\,\mu\text{A}}{200\,\mu\text{A}}\right)\left(\frac{0.25\text{ ns}}{50\text{ ns}}\right) = 2\pi \times 0.02 \times 0.005 = 6.28 \times 10^{-4}\text{ rad} \approx 0.036^\circ$ (tương đương độ lệch cạnh xung tĩnh $\Delta t_{\text{skew}} = \frac{\Delta I}{I_P} T_P = 0.02 \times 250\text{ ps} = 5\text{ ps}$!).
2. **Biên độ gợn sóng trên $V_{cont}$ và mức Reference Spur tại $2.4\text{ GHz} \pm 20\text{ MHz}$**:
   - Lượng điện tích lệch bơm rồi rút mỗi chu kỳ $\Delta Q = \Delta I \cdot T_P = 4\,\mu\text{A} \times 250\text{ ps} = 1\text{ fC}$.
   - Biên độ hài cơ bản tần số $f_{REF}$ trên tụ $C_2$ (xấp xỉ xung hẹp Fourier $V_{m,1} \approx \frac{2\,\Delta Q}{C_2}$ trước khi qua thêm suy hao mắt lọc phụ): $V_{m,1} \approx \frac{2 \times 1\text{ fC}}{6.7\text{ pF}} \approx 0.30\text{ mV}$.
   - Mức vạch phổ ký sinh theo PT (15.83): $\text{Spur} \approx 20\log_{10}\left(\frac{K_{VCO,\text{Hz}}\,V_{m,1}}{2 f_{REF}}\right) = 20\log_{10}\left(\frac{80\text{ MHz/V} \times 0.30\text{ mV}}{2 \times 20\text{ MHz}}\right) = 20\log_{10}(6 \times 10^{-4}) \approx -64.4\text{ dBc}$. Nếu rút $T_P$ xuống $150\text{ ps}$ và dùng op-amp khớp dòng giảm $\Delta I / I_P$ xuống $0.3\%$, spur hạ sâu xuống dưới **$-85\text{ dBc}$**!

## 3. Bất biến Cấu trúc & Các Bẫy Lỗi Kinh điển (Structural Invariants & Traps)

- **[INV-SPUR-01] Bất biến đánh đổi giữa Chống Vùng Chết và Mức Spur Tham chiếu**: Kéo dài xung xóa $T_P$ quá rộng tuy đảm bảo $100\%$ không bao giờ rơi vào vùng chết, nhưng phương trình $|\Delta\phi_{\text{off}}| \propto \Delta I \cdot T_P$ chỉ rõ lượng điện tích nhiễu bơm vào bộ lọc vòng mỗi chu kỳ tăng tỉ lệ thuận với $T_P$, làm vạch phổ spur tại $\pm f_{REF}$ vọt cao! Chỉ thiết kế $T_P$ vừa đủ để xung UP/DN chạm trọn vẹn biên logic ở góc chậm nhất `SS 125C` (thường $150 \sim 300\text{ ps}$).
- **[INV-NOISE-02] Bất biến quyết định băng thông theo chất lượng VCO**: Nếu dùng VCO vòng nhiễu lớn (`topo-ring-oscillator`) khóa vào thạch anh sạch $\implies$ phải **mở rộng $\omega_{\text{loop}}$ tối đa có thể** ($\sim \omega_{REF}/15 \dots \omega_{REF}/10$) để hàm thông cao $1 - H(s)$ gọt sạch nhiễu VCO. Ngược lại, nếu dùng LC-VCO $Q$ cao cực sạch (`topo-lc-cross-coupled-and-colpitts`) để lọc sạch một luồng xung nhịp đầu vào đầy jitter (Jitter Attenuator / Clock Recovery §16.5.3) $\implies$ phải **thu hẹp $\omega_{\text{loop}}$ thật nhỏ** để hàm thông thấp $H(s)$ chặn nhiễu đầu vào!
- **[TRAP-DLL-01] Bẫy khóa giả bội chu kỳ (Harmonic / False Delay Lock Ambiguity) trong DLL (§16.4)**: Nếu tổng trễ VCDL của vòng khóa trễ có thể quét từ dưới $T_{in}$ vượt quá $2 T_{in}$, PFD chỉ nhìn cạnh lên nên không phân biệt được trễ $1\,T_{in}$ hay $2\,T_{in}$ (hoặc thậm chí kẹt ở giới hạn biên trễ cực tiểu/cực đại)! Nếu DLL khóa nhầm vào $2\,T_{in}$, khoảng cách 4 pha biến thành $T_{in}/2$ thay vì $T_{in}/4$, phá hỏng hoàn toàn định thời hệ thống. Bắt buộc giới hạn dải VCDL trong $(0.5\,T_{in}, 1.5\,T_{in})$ hoặc tích hợp mạch khởi tạo chống khóa nhầm (false-lock detector), đồng thời khớp hình học cực chặt các tầng VCDL vì sai lệch linh kiện giữa các tầng trễ không được vòng hồi tiếp sửa ở các nút lấy pha giữa!
- **[TRAP-NOISE-02] Bẫy dòng bơm $I_P$ quá nhỏ làm nhiễu nhiệt bơm điện tích áp đảo nội dải**: Mật độ phổ dòng nhiễu nhiệt của bơm điện tích tỉ lệ với $I_P$ ($S_{i,CP} \propto 4 k T \gamma g_m \cdot \frac{T_P}{T_{REF}}$), nhưng độ lợi tách pha tỉ lệ với $I_P^2$ trong bình phương hàm truyền — do đó tạp âm pha nội dải quy về ngõ ra do CP gây ra tỉ lệ nghịch với $I_P$! Chọn $I_P$ quá nhỏ để tiết kiệm diện tích tụ $C_1$ sẽ làm sàn nhiễu nội dải (nhân thêm $M^2$) dâng cao ngất ngưởng.

## 4. Lộ trình Nâng cấp Cấu trúc & Bát giác Đánh đổi (Upgrade Paths & Design Octagon)

Trong `concept-analog-design-octagon`, nút khái niệm này khép kín toàn bộ chu trình thiết kế cấp hệ thống của miền xung nhịp và tổng hợp tần số:

- **Từ nền tảng vòng khóa pha cơ bản đến hoàn chỉnh**: Nối tiếp trực tiếp sau `topo-type1-simple-pll` và `topo-charge-pump-type2-pll`, cung cấp tiêu chuẩn định lượng để phân bổ chỉ tiêu cho `topo-vco-tuning-and-phase-noise`, `topo-ring-oscillator` và `topo-lc-cross-coupled-and-colpitts`.
- **Nâng cấp mạch bơm điện tích triệt Spur**: Thay thế nguồn dòng đơn giản bằng cấu trúc gương dòng cascode dải rộng `topo-lvccml-wide-swing-mirror` kết hợp op-amp ghim thế bootstrap nút trong (Hình 16.47) hoặc bơm điện tích vi sai điều hướng dòng (current-steering CP), đồng thời kiểm soát dự trữ pha bậc ba/bậc bốn theo `law-multipole-phase-margin`.
- **Bảo vệ toàn vẹn tín hiệu và nguồn cấp mức vật lý**: Tối thiểu hóa nhiễu nhiệt & $1/f$ trong CP/VCO/Buffer theo `law-mos-thermal-and-flicker-noise`, tách biệt các miền nguồn tương tự (VCO, CP) và số (PFD, `/M` Divider) bằng các bộ ổn áp `topo-cmos-ldo-regulator` độc lập, thực thi bố cục trọng tâm chung cho các tầng VCDL/CP theo `tech-common-centroid-sti-wpe-layout` và rào chắn nhiễu đế xuyên âm (`crosstalk` `T2087`) theo `law-cmos-wells-and-latchup-guard-rings`.

| Nguồn Nhiễu / Bất lý tưởng | Hàm truyền tới Pha ngõ ra $\Phi_{out}(s)$ | Hệ quả Phổ / Thời gian | Đối sách Thiết kế Trọng tâm |
| :--- | :--- | :--- | :--- |
| **Nhiễu pha thạch anh tham chiếu $\Phi_{REF}$** | Thông thấp: $M \cdot H(s)$ | Tăng công suất nhiễu nội dải gấp $M^2$ ($+20\log_{10} M\text{ dB}$) | Dùng thạch anh $f_{REF}$ cao sạch (giảm $M$), thu hẹp $\omega_{\text{loop}}$ nếu đầu vào bẩn. |
| **Nhiễu dòng bơm điện tích $I_{n,CP}$** | Thông thấp: $\frac{2\pi M}{I_P} H(s)$ | Nâng sàn nhiễu phẳng (in-band plateau) quanh sóng mang | Tăng dòng bơm $I_P$, giảm chu kỳ bật $T_P / T_{REF}$, định cỡ $V_{OV}$ lớn cho nguồn dòng CP. |
| **Nhiễu nhiệt điện trở lọc $R_P$** | Thông dải: $V_{n,RP} \frac{K_{VCO}}{s}[1 - H(s)]$ | Đóng góp đỉnh nhiễu ngay vùng cắt băng thông $\omega_{\text{loop}}$ | Không chọn $C_1$ quá bé khiến $R_P$ phình quá lớn (giữ $R_P$ cỡ vài $\text{k}\Omega$). |
| **Tạp âm pha tự do của VCO $\Phi_{VCO}$** | Thông cao: $1 - H(s)$ | Quyết định sườn nhiễu ngoại dải ($\Delta f > f_{\text{loop}}$) | Tối đa hóa $Q$ khung LC hoặc mở rộng $\omega_{\text{loop}}$ để nén mạnh nhiễu Ring VCO. |
| **Gợn sóng chu kỳ $f_{REF}$ trên $V_{cont}$** | Điều tần hẹp: $\frac{K_{VCO} V_m}{2\omega_{REF}}$ | Cặp vạch phổ rời rạc (Spurs) tại $f_{out} \pm k f_{REF}$ | Khớp trễ cổng truyền dẫn, khớp $I_{UP}=I_{DN}$, ghim thế bootstrap nút trong & giảm $K_{VCO}$. |

## 5. Thích ứng Đa Tiến trình (90nm / 65nm / 45nm) & Cách Kiểm chứng trong Cadence / Spectre

Trên các tiến trình `90nm`, `65nm`, `45nm`, tốc độ cổng logic siêu nhanh ($T_D \approx 8 \sim 20\text{ ps}$) mang lại lợi thế lớn cho PFD và bộ chia tần số tốc độ GHz, nhưng suy giảm trở kháng ngõ ra $r_o$ làm trầm trọng bài toán sai lệch dòng bơm điện tích:
- **Thực thi PFD & CP thích ứng nanomet**: Với $T_D$ quá nhỏ ở `45nm`, $5 T_D$ chỉ khoảng $50\text{ ps}$ có thể chưa đủ mở hết công tắc CP lớn ở góc `SS`; cần chèn chuỗi chẵn cổng đảo có tải tụ xác định trên đường `Reset` để định chuẩn $T_P \approx 150 \sim 250\text{ ps}$. Đối với bơm điện tích ở $V_{DD} = 0.9 \sim 1.0\text{ V}$, dùng thêm một op-amp phản hồi phụ (replica feedback op-amp) điều chỉnh cổng PMOS sao cho $I_{UP}(V_{cont}) = I_{DN}(V_{cont})$ tự động khớp nhau trên toàn dải $V_{cont}$, ép sai lệch dòng tĩnh xuống dưới $0.5\%$ và đè mức reference spur xuống dưới $-65 \sim -75\text{ dBc}$!

**Quy trình kiểm chứng Spur & Jitter chuẩn trong Cadence Virtuoso / SpectreRF**:
1. **Kiểm tra Vùng chết & Sai lệch Điện tích Tịnh Từng Chu kỳ (`tran` fine-step)**: Quét bước nhảy pha cực mịn $\Delta t \in [-20\text{ ps}, +20\text{ ps}]$ với bước $0.5\text{ ps}$ ở đầu vào PFD+CP (`reltol=1e-5`, `maxstep=0.2ps`), vẽ đường cong điện tích tịnh mỗi chu kỳ $Q_{\text{net}}(\Delta t) = \int_0^{T_{REF}} i_{CP}(t)\,dt$: đường cong bắt buộc đi thẳng tắp không gãy khúc quanh $\Delta t = 0$, và độ lệch điểm cắt trục hoành cho biết trực tiếp sai số pha tĩnh $\Delta\phi_{\text{off}}$.
2. **Dự báo Tổng Jitter Tích phân bằng Ghép Phổ Khối (Block-Level `pss` + `pnoise` Budget)**:
   - Chạy `pss` + `pnoise` riêng trên khối (PFD + CP) bị kích bởi xung chuẩn $f_{REF}$ để lấy mật độ phổ dòng nhiễu ngõ ra $S_{i,\text{CP}}(f)$.
   - Chạy `pss` + `pnoise` riêng trên khối bộ chia `/M` và khối VCO tự do để lấy $S_{\phi,\text{DIV}}(f)$ và $S_{\phi,\text{VCO}}(f)$.
   - Đưa tất cả qua các hàm truyền đóng vòng giải tích $H(jf)$, $Z_{LF}(jf)$ và $1 - H(jf)$, tích phân diện tích tổng $S_{\phi,\text{tot}}(f)$ từ $1\text{ kHz}$ đến $f_0 / 2$ (ví dụ chuẩn tích phân $12\text{ kHz} \sim 20\text{ MHz}$) để tính RMS Jitter:

$$\sigma_{\Delta T,\text{rms}} = \frac{1}{2\pi f_{out}}\sqrt{2 \int_{f_1}^{f_2} 10^{\mathcal{L}_{\text{tot}}(f)/10}\,df}$$

3. **Đo trực tiếp Reference Spurs ở Trạng thái Khóa Xác lập**: Sau khi vòng khóa pha toàn mạch transistor đã ổn định hoàn toàn (đạo hàm chu kỳ trung bình của $V_{cont}$ bằng $0$), chạy tiếp $32 \sim 64$ chu kỳ $T_{REF}$ với `strobeperiod` chính xác không nhiễu nội suy, lấy FFT trên $V_{out}(t)$ (hoặc đọc gợn sóng $\Delta V_{cont}(f_{REF})$ nhân $K_{VCO}/(2\omega_{REF})$) để nghiệm thu biên độ vạch phổ tại $f_{out} \pm f_{REF}$ và $f_{out} \pm 2 f_{REF}$ sau trích xuất ký sinh Post-Layout PEX.

## 6. Mốc Đối chiếu Sách Razavi & Thuật ngữ Chuẩn CLB

- **Mốc sách Razavi (2nd Ed.)**: Chương 16 — `§16.3.1` (*PFD/CP Nonidealities*, tr. 677–681, Hình 16.39–16.47); `§16.3.2` (*Jitter in PLLs*, tr. 681–683, Hình 16.48–16.51, PT 16.48); `§16.4` (*Delay-Locked Loops*, tr. 683–685, Hình 16.52–16.54, Ví dụ 16.12); `§16.5` (*Applications: Frequency Multiplication and Synthesis, Skew Reduction, Jitter Reduction*, tr. 685–689, Hình 16.55–16.61, Ví dụ 16.13, PT 16.49–16.56, Bài tập 16.12–16.13, 16.15–16.16).
- **Đối chiếu Thuật ngữ Chuẩn CLB Vi Mạch**:
  - `charge pump` (`T016`): **bơm điện tích** vs `charge injection` (`T014`): **phun điện tích** *(hai hiện tượng hoàn toàn khác nhau, tuyệt đối không đánh đồng!)*.
  - `phase-locked loop, PLL` (`T064`): vòng khóa pha; `delay-locked loop, DLL` (`T029`): vòng khóa trễ.
  - `jitter` (`T047`): jitter *(giữ nguyên ngữ, giải thích là biến thiên/sai lệch thời điểm cạnh tín hiệu)*.
  - `mismatch` (`T052`): sai lệch linh kiện; `bootstrapped` (`T2015`): được tự thiết lập nhờ hồi tiếp.
  - `clock recovery` (`T020`): khôi phục xung nhịp; `noise bandwidth` (`T1169`): băng thông nhiễu; `crosstalk` (`T2087`): xuyên nhiễu.
