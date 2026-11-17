---
{
  "id": "topo-charge-pump-type2-pll",
  "kind": "topology",
  "domain": "sampled-and-clocked",
  "title_vi": "Vòng khóa pha Bơm điện tích Loại II và Mạng Bù Tần số Rp-C1-C2 (Charge-Pump Type-II PLL)",
  "title_en": "Charge-Pump Type-II Phase-Locked Loop (Tri-State PFD + CP + Rp/C1/C2 Loop Filter)",
  "summary": "Kiến trúc vòng khóa pha chuẩn công nghiệp giải quyết triệt để bài toán bắt tần số và sai số pha tĩnh: bộ tách pha/tần số ba trạng thái (PFD) tầm tuyến tính +-2*pi kết hợp bơm điện tích Ip nạp tụ C1 tạo hai cực tại gốc tọa độ s=0 (vòng Loại II không ổn định nếu thiếu bù), cơ chế chèn điện trở nối tiếp Rp tạo zero nửa mặt phẳng trái wz = 1/(Rp*C1) cứu dự trữ pha và tụ lọc gợn song song C2 ~ C1/10..C1/5 hoàn thiện vòng bậc ba.",
  "diagram": "../../diagrams/charge-pump-type2-pll.svg",
  "razavi_refs": [
    {
      "chapter": 16,
      "section": "16.2.1",
      "pages": "666",
      "equations": []
    },
    {
      "chapter": 16,
      "section": "16.2.2",
      "pages": "667-670",
      "equations": []
    },
    {
      "chapter": 16,
      "section": "16.2.3",
      "pages": "670-671",
      "equations": []
    },
    {
      "chapter": 16,
      "section": "16.2.4",
      "pages": "671-677",
      "equations": ["16.37", "16.38", "16.39", "16.40", "16.41", "16.42", "16.43", "16.44", "16.45", "16.46", "16.47"]
    }
  ],
  "glossary_codes": [
    "T016",
    "T019",
    "T033",
    "T042",
    "T051",
    "T058",
    "T063",
    "T064",
    "T069",
    "T088",
    "T854",
    "T865",
    "T1575",
    "T1592",
    "T1614",
    "T1642",
    "T1678",
    "T1802",
    "T1804",
    "T1805"
  ],
  "process_agnostic": true,
  "roles": {
    "tri_state_pfd": "Hai D-flip-flop kích cạnh có chân xóa chung (AND gate) xuất xung UP (QA) và DOWN (QB) phân biệt đơn điệu cả sai số tần số lẫn sai số pha trên [-2*pi, +2*pi].",
    "charge_pump_ip": "Hai nguồn dòng chuyển mạch +Ip và -Ip biến đổi độ rộng xung chênh lệch từ PFD thành gói điện tích bơm vào hoặc rút ra khỏi bộ lọc vòng.",
    "integrating_cap_c1_and_zero_resistor_rp": "Tụ tích phân chính C1 (ký hiệu CP trong Razavi) tạo cực thứ hai tại gốc tọa độ để triệt tiêu sai số pha tĩnh, nối tiếp điện trở Rp sinh LHP zero wz = 1/(Rp*C1) bù pha ổn định vòng.",
    "ripple_bypass_capacitor_c2": "Tụ nhỏ C2 (~ C1/10 đến C1/5) mắc song song nhánh Rp-C1 dập tắt bước nhảy điện áp tức thời Ip*Rp trên đường Vcont mỗi nhịp so pha."
  },
  "symptoms_addressed": [
    "type1-pll-lock-acquisition-failure-under-wide-pvt-vco-spread",
    "nonzero-static-phase-error-in-type1-pll",
    "oscillation-instability-of-two-origin-poles-without-compensating-zero",
    "instantaneous-vcont-voltage-jump-ip-times-rp-on-charge-pump-pulses"
  ],
  "limitations": [
    "closed-loop-peaking-around-natural-frequency-due-to-lhp-zero-in-numerator",
    "stability-degradation-when-ip-times-kvco-decreases-or-divide-ratio-increases",
    "discrete-time-sampling-instability-if-loop-bandwidth-exceeds-one-tenth-fref",
    "third-order-pole-from-c2-eroding-phase-margin-if-c2-sized-too-large"
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

Để thoát khỏi hai căn bệnh nan y của PLL Loại I (dải bắt khóa hẹp cỡ $\omega_{LPF}$ không đủ bù trôi PVT của VCO và sai số pha tĩnh $\phi_0 \neq 0$ phụ thuộc tần số), nền công nghiệp vi mạch tích hợp hội tụ về kiến trúc **vòng khóa pha bơm điện tích Loại II** (Charge-Pump Type-II PLL — CPPLL, §16.2). Quá trình kiến tạo cấu trúc này dựa trên sự kết hợp tinh tế của bốn ý tưởng cốt lõi:

![Sơ đồ vòng khóa pha bơm điện tích Loại II với PFD ba trạng thái, bơm điện tích Ip và bộ lọc vòng Rp-C1-C2](../../diagrams/charge-pump-type2-pll.svg)

1. **Bộ tách pha/tần số ba trạng thái (Tri-State Phase/Frequency Detector — PFD, §16.2.2, Hình 16.22–16.26)**:
   Khác với D-flip-flop đơn thuần (kiểu bang-bang trong Ví dụ 16.7 cho giá trị trung bình bằng $0$ khi $\omega_A \neq \omega_B$!), mạch PFD dùng **hai D-flip-flop kích cạnh lên có chân dữ liệu nối cứng lên mức cao (bit 1 / $V_{DD}$)**, nhận hai tín hiệu $A$ ($\text{REF}$) và $B$ ($\text{VCO/DIV}$) làm xung nhịp, kèm một cổng **AND** nối từ hai ngõ ra $Q_A, Q_B$ quay về chân `Reset` đồng thời cả hai flip-flop:
   - Mạch có **3 trạng thái logic hữu dụng**: $(Q_A = 0, Q_B = 0)$, $(Q_A = 1, Q_B = 0 \text{ — xung UP})$, và $(Q_A = 0, Q_B = 1 \text{ — xung DOWN})$ (trạng thái $Q_A = Q_B = 1$ chỉ tồn tại thoáng qua trong độ rộng xung xóa $T_P \approx 5 T_D$ trễ cổng logic, Ví dụ 16.8).
   - *Khi khác tần số ($\omega_A > \omega_B$)*: Cạnh lên của $A$ tới dồn dập hơn $B$ nên chỉ có $Q_A$ liên tục phát xung dương kéo VCO tăng tốc, còn $Q_B$ chỉ nháy xung hẹp lúc xóa — tạo ra tín hiệu phân biệt tần số **đơn điệu một chiều**, mở rộng **dải tự bắt khóa (acquisition/pull-in range) bằng toàn bộ dải điều chỉnh của VCO**!
   - *Khi cùng tần số ($\omega_A = \omega_B$)*: Hiệu giá trị trung bình giữa $Q_A$ và $Q_B$ biến thiên **tuyến tính và đối xứng trên toàn dải rộng gấp đôi cổng XOR là $-2\pi < \Delta\phi < +2\pi$** ($\pm 360^\circ$, Hình 16.26).
2. **Bơm điện tích (Charge Pump — CP, `T016`, §16.2.3, Hình 16.28)**:
   Nếu chỉ lọc RC hai ngõ ra của PFD (Hình 16.27), độ lợi một chiều vẫn hữu hạn nên sai số pha tĩnh vẫn khác $0$. Bằng cách đặt **bơm điện tích** gồm nguồn dòng nạp $I_1 = +I_P$ (đóng mở bởi $S_1$ theo $Q_A$) và nguồn dòng xả $I_2 = -I_P$ (đóng mở bởi $S_2$ theo $Q_B$) bơm trực tiếp vào một tụ tích phân $C_1$ (Razavi ký hiệu là $C_P$): chừng nào còn tồn tại sai số pha tĩnh $\Delta\phi \neq 0$, mỗi chu kỳ bơm điện tích lại nhồi thêm điện tích vào $C_1$ đẩy $V_{cont} \to \pm\infty$ (độ lợi DC bằng vô cùng!). Do ở trạng thái khóa thực tế $V_{cont}$ hữu hạn, **sai số pha tĩnh lý tưởng bắt buộc phải bằng $0$ tuyệt đối ($\Delta\phi_{\text{ss}} = 0$)** tại mọi tần số làm việc!
3. **Bản chất mất ổn định của Hai bộ tích phân lý tưởng & Điện trở bù $R_P$ (§16.2.4, Hình 16.33–16.35)**:
   Sự kết hợp giữa khối PFD + CP + $C_1$ (một bộ tích phân $1/s$) và VCO (bộ tích phân thứ hai $K_{VCO}/s$) sinh ra **hai cực tại gốc tọa độ $s = 0$** (**PLL Loại II — Type-II PLL**). Hai bộ tích phân nối tiếp đóng góp dịch pha không đổi $-90^\circ - 90^\circ = -180^\circ$ ở mọi tần số (dự trữ pha $0^\circ$), đặt cặp cực vòng kín nằm ngay trên trục ảo $j\omega$ làm vòng **chắc chắn tự dao động**! Để cứu vãn ổn định mà không đánh mất độ lợi vô cùng ở DC, bắt buộc mắc nối tiếp điện trở $R_P$ với tụ $C_1$ để sinh ra một **zero ở nửa mặt phẳng trái (LHP zero)** tại $\omega_z = \frac{1}{R_P C_1}$, kéo pha vòng hở vọt từ $-180^\circ$ hướng về $-90^\circ$.
4. **Tụ lọc gợn song song $C_2$ hoàn thiện Bộ lọc Vòng Bậc hai (Hình 16.38)**:
   Vì dòng xung chữ nhật $\pm I_P$ chảy thẳng qua điện trở $R_P$ gây bước nhảy điện áp tức thời $\Delta V_{cont} = I_P R_P$ mỗi lần chuyển mạch, một tụ phụ nhỏ $C_2 \approx \left(\frac{1}{10} \sim \frac{1}{5}\right) C_1$ luôn được mắc song song với nhánh $(R_P + C_1)$ để san phẳng xung dòng, biến toàn hệ thành **PLL Loại II Bậc ba (3rd-order Type-II PLL)**.

## 2. Hệ Phương trình Cốt lõi & Tư duy "Nhìn Mạch Đọc Nhanh" (Analysis by Inspection)

### 2.1. Xấp xỉ Thời gian Liên tục cho PFD + Bơm điện tích & Thảm họa Chưa Bù ($R_P = 0$)
Khi ngõ vào có bước nhảy lệch pha $\Delta\phi = \phi_0 u(t)$ với chu kỳ tham chiếu $T_{in}$, mỗi chu kỳ xung UP (hoặc DOWN) mở rộng $\frac{|\phi_0|}{2\pi} T_{in}$ giây, bơm lượng điện tích $\Delta Q = I_P \frac{\phi_0}{2\pi} T_{in}$, tương đương dòng điện trung bình trong một chu kỳ (Ví dụ 16.10, PT 16.37–16.40):

$$\frac{I_{out}(s)}{\Delta\Phi(s)} = \frac{I_P}{2\pi} \quad (\text{A/rad}) \implies \left.\frac{V_{cont}(s)}{\Delta\Phi(s)}\right|_{R_P=0} = \frac{I_P}{2\pi C_1 s}$$

Ghép với VCO có $\frac{\Phi_{out}(s)}{V_{cont}(s)} = \frac{K_{VCO}}{s}$, hàm truyền vòng hở và vòng kín khi chưa có $R_P$ (PT 16.41–16.42) là:

$$H_{\text{open}}(s) = \frac{I_P K_{VCO}}{2\pi C_1 s^2}, \qquad H(s) = \frac{\dfrac{I_P K_{VCO}}{2\pi C_1}}{s^2 + \dfrac{I_P K_{VCO}}{2\pi C_1}} \implies s_{1,2} = \pm j\sqrt{\frac{I_P K_{VCO}}{2\pi C_1}}$$

Hai cực nằm chết cứng trên trục ảo: mọi nhiễu nhỏ sẽ khiến pha và tần số VCO lắc lư hình sin không bao giờ tắt!

### 2.2. Bù Tần số bằng Điện trở Nối tiếp $R_P$ (2nd-Order Type-II Approximation)
Khi chèn $R_P$ nối tiếp với $C_1$, trở kháng bộ lọc vòng là $Z_{LF}(s) = R_P + \frac{1}{C_1 s} = \frac{1 + s R_P C_1}{C_1 s}$. Hàm truyền vòng hở $L(s)$ và hàm truyền vòng kín $H(s)$ trở thành (PT 16.44–16.47):

$$H_{\text{open}}(s) = \frac{I_P}{2\pi}\left(R_P + \frac{1}{C_1 s}\right)\frac{K_{VCO}}{s} = \frac{I_P K_{VCO}}{2\pi C_1} \cdot \frac{1 + s/\omega_z}{s^2}, \qquad \omega_z = \frac{1}{R_P C_1}$$

$$H(s) = \frac{\Phi_{out}(s)}{\Phi_{in}(s)} = \frac{\dfrac{I_P K_{VCO}}{2\pi C_1}(R_P C_1 s + 1)}{s^2 + \dfrac{I_P}{2\pi} K_{VCO} R_P s + \dfrac{I_P K_{VCO}}{2\pi C_1}} = \frac{2\zeta\omega_n s + \omega_n^2}{s^2 + 2\zeta\omega_n s + \omega_n^2}$$

Trong đó tần số tự nhiên $\omega_n$, hệ số tắt dần $\zeta$ và hằng số thời gian tắt dần bao hình $\tau_{\text{decay}} = (\zeta\omega_n)^{-1}$ là:

$$\omega_n = \sqrt{\frac{I_P K_{VCO}}{2\pi C_1}}, \qquad \zeta = \frac{R_P}{2}\sqrt{\frac{I_P C_1 K_{VCO}}{2\pi}} = \frac{\omega_n}{2\omega_z}, \qquad \frac{1}{\zeta\omega_n} = \frac{4\pi}{R_P I_P K_{VCO}}$$

Ở vùng tần số vượt lên trên zero ($\omega \gg \omega_z$), nhánh điện trở $R_P$ chiếm ưu thế so với dung kháng $1/(\omega C_1)$, làm độ dốc biên độ vòng hở thoai thoải từ $-40\text{ dB/dec}$ về $-20\text{ dB/dec}$ và ghim tần số cắt độ lợi vòng (xấp xỉ băng thông vòng $\omega_{\text{loop}} \approx \omega_u$) cực kỳ gọn cho tính nhẩm thiết kế:

$$\omega_{\text{loop}} \approx 2\zeta\omega_n = \frac{I_P}{2\pi} R_P K_{VCO} \quad \text{(khi } \zeta \ge 0.7\text{, và nếu có bộ chia } \div M \text{ thì chia thêm cho } M\text{!)}$$

### 2.3. Ảnh hưởng của Tụ Lọc Gợn $C_2$ trong Vòng Bậc ba Thực tế (3rd-Order Type-II Loop)
Khi mắc $C_2$ song song với $(R_P + C_1)$, trở kháng bộ lọc vòng có dạng chuẩn hai cực – một zero:

$$Z_{LF}(s) = \left(R_P + \frac{1}{C_1 s}\right) \parallel \frac{1}{C_2 s} = \frac{1 + s R_P C_1}{s(C_1 + C_2)\left(1 + s R_P \dfrac{C_1 C_2}{C_1 + C_2}\right)}$$

Hàm truyền vòng hở $L(s) = \frac{I_P K_{VCO}}{2\pi} \frac{Z_{LF}(s)}{s}$ nay sở hữu:
- Hai cực tại gốc tọa độ $s = 0$, một zero ổn định tại $\omega_z = \frac{1}{R_P C_1}$, và **một cực bậc ba tần số cao tại $\omega_{p3} = \frac{C_1 + C_2}{R_P C_1 C_2} \approx \frac{1}{R_P C_2}$**.
- Dự trữ pha vòng hở là $\text{PM}(\omega) = \tan^{-1}(\omega / \omega_z) - \tan^{-1}(\omega / \omega_{p3})$, đạt **đỉnh cực đại duy nhất** tại trung bình nhân hình học $\omega_u = \sqrt{\omega_z \omega_{p3}}$! Đặt tỉ số tụ $b = C_1 / C_2 \approx \omega_{p3}/\omega_z - 1$: với $C_1 / C_2 = 8 \sim 12$, đỉnh dự trữ pha đạt $\text{PM}_{\max} \approx 53^\circ \sim 60^\circ$ cực kỳ vững chãi!

### 2.4. Ví dụ Định lượng Thiết kế Bộ lọc Vòng Bậc ba Chuẩn Công nghiệp
Thiết kế bộ tổng hợp tần số CP-PLL Loại II tạo $f_{out} = 2.4\text{ GHz}$ từ thạch anh $f_{REF} = 20\text{ MHz}$ (hệ số chia $M = 120$), dùng LC-VCO có $K_{VCO,\text{Hz}} = 80\text{ MHz/V}$ ($K_{VCO} = 2\pi \times 80\text{ MHz/V}$) và dòng bơm điện tích $I_P = 200\,\mu\text{A}$:
1. **Chọn băng thông vòng cắt độ lợi $\omega_u$ tuân thủ giới hạn rời rạc Gardner**:
   - Đặt $f_u = f_{REF} / 20 = 1\text{ MHz}$ ($\omega_u = 2\pi \times 10^6\text{ rad/s} \ll \omega_{REF}/10$).
2. **Chọn tỉ số tụ $b = C_1 / C_2 = 10$ để đạt đỉnh dự trữ pha tại đúng $\omega_u$**:
   - $\text{PM}_{\max} = \tan^{-1}\sqrt{b + 1} - \tan^{-1}\frac{1}{\sqrt{b + 1}} = \tan^{-1}(3.317) - \tan^{-1}(0.3015) \approx 73.2^\circ - 16.8^\circ = 56.4^\circ$.
   - Tần số zero và cực bậc ba: $f_z = \frac{f_u}{\sqrt{11}} \approx 301.5\text{ kHz}$ và $f_{p3} = f_u\sqrt{11} \approx 3.317\text{ MHz}$.
3. **Tính giá trị linh kiện thụ động $R_P, C_1, C_2$ trên chip**:
   - Tại $\omega_u$, $|L(j\omega_u)| = 1 \implies R_P = \frac{2\pi M f_u}{I_P K_{VCO,\text{Hz}}} \cdot \frac{b + 1}{b\sqrt{1 + 1/(b+1)}} \approx \frac{120 \times 1\text{ MHz}}{200\,\mu\text{A} \times 80\text{ MHz/V}} \times 1.05 \approx 7.88\text{ k}\Omega$.
   - $C_1 = \frac{1}{2\pi f_z R_P} = \frac{1}{2\pi \times 301.5\text{ kHz} \times 7.88\text{ k}\Omega} \approx 67.0\text{ pF}$ (tích hợp gọn trên chip bằng tụ MIM/MOM $\sim 180\,\mu\text{m} \times 180\,\mu\text{m}$!).
   - $C_2 = \frac{C_1}{10} \approx 6.7\text{ pF}$; hệ số tắt dần tương đương $\zeta \approx \frac{1}{2}\sqrt{\frac{\omega_u}{\omega_z}} \approx 0.91$, hằng số thời gian hội tụ khóa tinh $\tau_{\text{decay}} \approx 0.35\,\mu\text{s}$.

## 3. Bất biến Cấu trúc & Các Bẫy Lỗi Kinh điển (Structural Invariants & Traps)

- **[INV-CPPLL-01] Bất biến ngược chiều ổn định giữa Type-II và Type-I (Hình 16.36–16.37)**: Trong Type-I, giảm $K_{PD} K_{VCO}$ làm vòng *ổn định hơn*; ngược lại hoàn toàn trong Type-II, **giảm $I_P K_{VCO}$ (hoặc tăng hệ số chia tần $M$) kéo tần số cắt độ lợi $\omega_u$ tụt về phía gốc tọa độ tiến gần vùng $-180^\circ$ dưới $\omega_z$, làm SỤT dự trữ pha và SỤT $\zeta \propto \sqrt{I_P K_{VCO}}$**! Trên mặt phẳng phức (Hình 16.37), hai cực xuất phát từ gốc tọa độ chạy trên đường tròn tâm $-\omega_z$ bán kính $\omega_z$ khi tăng $I_P K_{VCO}$.
- **[INV-CPPLL-02] Giới hạn rời rạc Gardner ($\omega_{\text{loop}} \le \omega_{REF} / 10$)**: Mô hình $s$-domain ở trên là phép xấp xỉ liên tục hóa một hệ lấy mẫu theo cạnh xung nhịp mỗi chu kỳ $T_{REF}$. Nếu tăng $R_P$ hoặc $I_P$ quá lớn đẩy băng thông vòng $\omega_{\text{loop}}$ vượt quá $\sim \frac{1}{10}\,\omega_{REF}$, trễ lấy mẫu rời rạc của PFD làm sụp đổ dự trữ pha và gây dao động tự kích chu kỳ rời rạc (trái ngược dự đoán ngây thơ $\zeta \to \infty$ khi $R_P \to \infty$!).
- **[INV-CPPLL-03] Không bao giờ nối cổng VCO vào tấm giữa của $R_P$ và $C_1$ (Bài tập 16.10)**: Điện áp điều khiển $V_{cont}$ bắt buộc phải lấy trên toàn bộ chuỗi $(R_P + C_1)$; nếu lấy nhầm tại nút giữa chỉ trên tụ $C_1$, dòng qua $C_1$ vẫn là dòng bơm điện tích khiến zero $\omega_z = 1/(R_P C_1)$ biến mất hoàn toàn khỏi hàm truyền và PLL quay lại dao động bất ổn định!
- **[TRAP-CPPLL-01] Bẫy ngộ nhận đồ thị Bode ở $\omega \to 0$ vi phạm tiêu chuẩn Nyquist (Ví dụ 16.11)**: Nhìn đồ thị Bode vòng hở có $|H_{\text{open}}| > 1$ và pha tiến sát $-180^\circ$ ở tần số rất thấp dễ tưởng nhầm mạch dao động, nhưng nhờ zero ở nửa mặt phẳng trái, pha luôn lớn hơn nghiêm ngặt $-180^\circ$ với mọi $\omega > 0$ (ví dụ $-179^\circ, -135^\circ\dots$); đồ thị phân cực Nyquist không bao giờ bao quanh điểm $(-1, j0)$ nên mạch hoàn toàn ổn định!
- **[TRAP-CPPLL-02] Bẫy độ nhô đỉnh hàm truyền đóng vòng (Jitter Peaking) do zero nằm trên tử số $H(s)$**: Nhìn PT (16.45), tử số của $H(s) = \frac{2\zeta\omega_n s + \omega_n^2}{s^2 + 2\zeta\omega_n s + \omega_n^2}$ chứa trực tiếp zero tại $-\omega_z = -\omega_n/(2\zeta)$! Do đó $|H(j\omega)|$ luôn vọt lên lớn hơn $1$ ($> 0\text{ dB}$, gọi là *jitter peaking*) trước khi dốc xuống, làm khuếch đại nhiễu đầu vào nếu $\zeta$ nhỏ (ứng dụng truyền dẫn quang SONET/PCIe thường bắt buộc $\zeta \ge 1 \sim 3$ để ghìm peaking $< 0.1\text{ dB}$!).
- **[TRAP-CPPLL-03] Bẫy dòng rò cực cổng varactor / tụ lọc làm trôi $V_{cont}$**: Nếu dùng tụ MOS cổng oxit siêu mỏng làm tụ lớn $C_1$ ở tiến trình `65nm`/`45nm`, dòng rò xuyên hầm cực cổng $I_{\text{leak}}$ rút điện tích liên tục khỏi $C_1$, buộc PFD phải tạo độ lệch pha tĩnh để bơm bù mỗi chu kỳ và sinh ra spur tham chiếu cực lớn!

## 4. Lộ trình Nâng cấp Cấu trúc & Bát giác Đánh đổi (Upgrade Paths & Design Octagon)

Trong `concept-analog-design-octagon`, `topo-charge-pump-type2-pll` là bước nâng cấp trực tiếp thay thế `topo-type1-simple-pll`, giải quyết dứt điểm bài toán bắt khóa tần số rộng và sai số pha tĩnh bằng không, đổi lại phải quản trị cẩn trọng bài toán ổn định hai cực gốc tọa độ (`law-multipole-phase-margin`), độ nhô đỉnh đáp ứng (jitter peaking) và các bất lý tưởng chuyển mạch của bơm điện tích:

- **Ghép nối với lõi VCO**: Điều khiển trực tiếp `topo-vco-tuning-and-phase-noise` (xây dựng trên `topo-ring-oscillator` cho bộ tạo xung nhịp đa pha diện tích nhỏ hoặc `topo-lc-cross-coupled-and-colpitts` cho bộ tổng hợp tần số RF tạp âm pha thấp).
- **Xử lý bất lý tưởng thực thi, triệt vạch phổ ký sinh (Reference Spurs), tối ưu nhiễu pha & tổng hợp tần số $/M$**: Chuyển tiếp trực tiếp sang nút chuyên sâu `concept-pll-nonidealities-spurs-jitter` để giải quyết vùng chết PFD, sai lệch dòng UP/DN, chia sẻ điện tích, đối ngẫu hàm truyền nhiễu và vòng khóa trễ DLL.
- **Thiết kế mạch nguồn & gương dòng cho bơm điện tích chính xác**: Dùng gương dòng cascode điện áp thấp `topo-lvccml-wide-swing-mirror` có trở kháng ra cao để cân bằng dòng $I_{UP} = I_{DN}$ trên dải rộng $V_{cont}$, giảm nhiễu linh kiện theo `law-mos-thermal-and-flicker-noise`, và cấp nguồn riêng qua `topo-cmos-ldo-regulator`.

| Hạng mục Đối chiếu | PLL Loại I (PD + RC LPF) | PLL Loại II Chưa Bù ($C_1$ thuần) | PLL Loại II Chuẩn ($R_P + C_1 \parallel C_2$) |
| :--- | :--- | :--- | :--- |
| **Cực tại gốc tọa độ** | $1$ cực ($-90^\circ$ ở DC) | $2$ cực ($-180^\circ$ ở mọi $\omega$) | $2$ cực gốc + $1$ LHP zero $\omega_z$ + $1$ cực $\omega_{p3}$ |
| **Sai số pha tĩnh $\Delta\phi_{\text{ss}}$** | Khác $0$: $\Delta\omega / (K_{PD} K_{VCO})$ | Bằng $0$ (nhưng tự dao động!) | **Bằng $0$ lý tưởng** (chỉ còn lệch nhỏ do $\Delta I_{CP}$) |
| **Dải tự bắt khóa tần số** | Hẹp ($\sim \omega_{LPF}$) | Không ổn định | **Toàn dải điều chỉnh VCO** (nhờ PFD 3 trạng thái) |
| **Xu hướng khi giảm $K_{VCO}$** | Hệ số tắt dần $\zeta$ **tăng** | Luôn mất ổn định ($\zeta = 0$) | Hệ số tắt dần $\zeta$ **giảm** (cần canh góc `SS`/dải biên!) |

## 5. Thích ứng Đa Tiến trình (90nm / 65nm / 45nm) & Cách Kiểm chứng trong Cadence / Spectre

Khi thiết kế CPPLL trên `90nm`, `65nm`, `45nm` ($V_{DD} = 1.2\text{ V} \to 0.9\text{ V}$):
- **Bài toán thu hẹp dải tuân thủ (Compliance Range) của Bơm điện tích**: Ở $V_{DD} = 1.0\text{ V}$, cả nguồn dòng PMOS phía trên ($I_{UP}$) lẫn nguồn dòng NMOS phía dưới ($I_{DN}$) cần tối thiểu $V_{DS,\min} \approx 120 \sim 150\text{ mV}$ (hoặc $\sim 200 \sim 250\text{ mV}$ nếu dùng cascode), ép cửa sổ tuyến tính của $V_{cont}$ xuống còn $[0.25\text{ V}, 0.75\text{ V}]$. Ngoài cửa sổ này, một trong hai nguồn dòng rơi vào vùng triode làm lệch nặng $I_{UP} \neq I_{DN}$ và giảm $I_P$ gây mất dự trữ pha! Khắc phục bằng cách dùng cấu trúc cascode dải rộng chiều dài kênh lớn ($L \ge 3 \sim 5\,L_{\min}$) cho nguồn dòng CP kết hợp dàn tụ chuyển mạch trên VCO để khóa $V_{cont}$ luôn nằm gọn quanh $V_{DD}/2$!
- **Chọn loại tụ cho $C_1, C_2$ & Layout**: Bắt buộc dùng **tụ kim loại MIM / MOM** (hoặc tụ MOS oxit dày I/O $2.5\text{ V}/1.8\text{ V}$ dòng rò gần bằng $0$) cho $C_1$ (thường vài chục đến vài trăm $\text{pF}$) và $C_2$, tuyệt đối không dùng tụ cổng core oxit mỏng rò điện! Bố cục hai nhánh UP/DN và flip-flop PFD đối xứng tuyệt đối theo `tech-common-centroid-sti-wpe-layout`, cách ly khối số PFD/Divider khỏi khối tương tự CP/LPF/VCO bằng hào bảo vệ kép theo `law-cmos-wells-and-latchup-guard-rings`.

**Quy trình thiết kế theo thuật toán 4 bước & Kiểm chứng Cadence / Spectre**:
1. **Thuật toán tính nhanh thông số vòng chuẩn 60 độ PM**: Chọn băng thông vòng $\omega_u \le \omega_{REF}/10$; chọn tỉ số $b = C_1/C_2 = 10$ (cho $\text{PM}_{\max} \approx 55^\circ$); đặt $\omega_z = \omega_u / \sqrt{b + 1} \approx \omega_u / 3.3$ và $\omega_{p3} \approx 3.3\,\omega_u$; từ $I_P$ và $K_{VCO}/M$ suy ra $R_P \approx \frac{2\pi M \omega_u}{I_P K_{VCO}} \sqrt{\frac{b+1}{b}}$, rồi tính $C_1 = \frac{1}{\omega_z R_P}$ và $C_2 = \frac{C_1}{b}$.
2. **Kiểm tra đặc tuyến PFD + CP quét pha & điện áp (`tran` sweep)**: Cấp xung $A, B$ quét $\Delta\phi \in [-2\pi, +2\pi]$ với nguồn áp DC giữ nút ra tại $V_{cont} = 0.25, 0.5, 0.75\text{ V}$; tích phân dòng trung bình $I_{\text{avg}}(\Delta\phi)$ để kiểm tra độ dốc $I_P / (2\pi)$, không có vùng chết quanh $\Delta\phi = 0$, và độ lệch $|I_{UP} - I_{DN}| / I_P < 1\% \sim 2\%$ qua các góc PVT.
3. **Đồng mô phỏng hỗn hợp (Behavioral-to-Transistor Lock Verification)**: Dùng mô hình miền pha MATLAB/Python hoặc mạch tương đương AC tuyến tính kiểm tra Bode vòng hở ($\text{PM} \ge 50^\circ$ trên mọi góc `SS/FF` khi $I_P, R_P, K_{VCO}$ biến thiên!), sau đó thay VCO bằng mô hình Verilog-A thực tế (có nạp bảng $K_{VCO}(V_{cont})$ từ `pss`) chạy khóa quá độ toàn vòng PFD+CP+LPF+Divider mức transistor trong vài trăm chu kỳ $T_{REF}$, và cuối cùng gắn VCO mức transistor khởi tạo $V_{cont}$ gần điểm khóa để kiểm chứng xác lập cuối cùng với `errpreset=conservative`.

## 6. Mốc Đối chiếu Sách Razavi & Thuật ngữ Chuẩn CLB

- **Mốc sách Razavi (2nd Ed.)**: Chương 16 — `§16.2.1` (*Problem of Lock Acquisition*, tr. 666, Hình 16.21); `§16.2.2` (*Phase/Frequency Detector*, tr. 667–670, Hình 16.22–16.27, Ví dụ 16.7–16.8); `§16.2.3` (*Charge Pump*, tr. 670–671, Hình 16.28–16.29, Ví dụ 16.9); `§16.2.4` (*Basic Charge-Pump PLL*, tr. 671–677, Hình 16.30–16.38, Ví dụ 16.10–16.11, PT 16.37–16.47, Bài tập 16.10–16.11, 16.14).
- **Đối chiếu Thuật ngữ Chuẩn CLB Vi Mạch**:
  - `charge pump` (`T016`): **bơm điện tích** *(lưu ý phân biệt rạch ròi với `charge injection` `T014` là phun điện tích!)*.
  - `phase-locked loop, PLL` (`T064`): vòng khóa pha; `ONE / ZERO (bit)` (`T058`): bit 1 / bit 0.
  - `Two Poles at Origin` (`T1805`): hai cực tại gốc tọa độ; `two ideal integrators` (`T1804`): hai bộ tích phân lý tưởng.
  - `left-half-plane zero` (`T1678`): zero ở nửa mặt phẳng trái; `frequency compensation` (`T1575`): bù tần số.
  - `phase margin` (`T063`): dự trữ pha; `gain crossover frequency` (`T1614`): tần số cắt độ lợi; `three-pole system` (`T1642`): hệ thống ba cực.
