---
{
  "id": "skill-pll-cp-loop-filter-lock-jitter-tb",
  "kind": "skill",
  "domain": "eda-and-github-skills",
  "title_vi": "Testbench Vòng Khóa Pha Bơm Điện tích (Type-II CP-PLL): Tổng hợp Bộ Lọc Vòng, Vùng Chết PFD, Spur & Ngân sách Jitter",
  "title_en": "Type-II Charge-Pump PLL Testbench Playbook: 3rd-Order Loop Filter Synthesis, PFD Dead-Zone, Reference Spurs & Jitter Budget",
  "summary": "Quy trình thực chiến tổng hợp tham số và kiểm chứng toàn diện Vòng Khóa Pha Bơm Điện tích Loại II bậc 3 (Type-II 3rd-Order CP-PLL) trên Cadence IC617 + Spectre 15.1: thuật toán đóng thiết kế {Ip, R1, C1, C2} đặt dự trữ pha tối ưu quanh điểm cắt ωc <= ωref/10, quét kiểm định xung chống vùng chết PFD, đo bất cân xứng dòng UP/DN gây vạch giả tham chiếu ±fref, tăng tốc mô phỏng khóa pha quá độ bằng mô hình lai Verilog-A + Transistor, và tích phân tổng nhiễu pha / RMS Jitter đa nguồn.",
  "diagram": "../../diagrams/charge-pump-type2-pll.svg",
  "razavi_refs": [
    {
      "chapter": 16,
      "section": "16.1-16.3, 16.5",
      "pages": "655-683, 685-690",
      "equations": ["16.37", "16.38", "16.40", "16.42", "16.44", "16.45", "16.46", "16.47", "16.51", "16.55"]
    }
  ],
  "github_refs": [
    {
      "repo": "iic-jku/radio-frequency-integrated-circuits",
      "url": "https://github.com/iic-jku/radio-frequency-integrated-circuits",
      "use": "Phương pháp tổng hợp hàm truyền vòng khóa pha, phân bổ ngân sách nhiễu pha trong dải / ngoài dải và phân tích bộ tổng hợp tần số"
    },
    {
      "repo": "Arcadia-1/veriloga-skills",
      "url": "https://github.com/Arcadia-1/veriloga-skills",
      "use": "Xây dựng các khối hành vi PFD, bộ chia tần ÷N và VCO sạch trạng thái ẩn để mô phỏng tăng tốc quá trình bắt khóa PLL"
    },
    {
      "repo": "Arcadia-1/circuits-and-systems-classroom",
      "url": "https://github.com/Arcadia-1/circuits-and-systems-classroom",
      "use": "Mô hình hóa miền pha liên tục s-domain và hiệu ứng rời rạc lấy mẫu xung nhịp PFD trong hệ thống khóa pha"
    }
  ],
  "glossary_codes": [
    "T016",
    "T047",
    "T051",
    "T063",
    "T2166",
    "T2167",
    "T2169",
    "T2170",
    "T2171",
    "T2172",
    "T2173",
    "T2174",
    "T2175",
    "T2176",
    "T2177",
    "T2178",
    "T2179"
  ],
  "process_agnostic": true,
  "roles": {
    "tristate_pfd": "Bộ tách pha–tần số ba trạng thái (Tristate PFD) so sánh sườn lên fref và fdiv để phát xung UP/DN có độ rộng tỉ lệ tuyến tính với sai lệch pha kèm xung đặt lại tối thiểu t_rst chống vùng chết",
    "charge_pump": "Mạch bơm điện tích (Charge Pump) biến đổi hiệu độ rộng xung (UP - DN) thành gói điện tích bơm/rút vào bộ lọc vòng với yêu cầu khớp chặt I_UP = I_DN trên toàn dải áp điều khiển",
    "third_order_loop_filter": "Mạng lọc thụ động bậc hai về trở kháng Z_LF(s) gồm R1 nối tiếp C1 (tạo zero ổn định ωz cho hệ hai cực gốc tọa độ!) mắc song song tụ dập gợn C2 (tạo cực phụ thứ ba ωp3)",
    "vco_and_divider": "VCO tích phân pha với hàm truyền 2*pi*KVCO/s kết hợp bộ chia tần hồi tiếp ÷N nhân tần số ra lên fout = N * fref"
  },
  "symptoms_addressed": [
    "full-transistor-pll-transient-lock-simulation-takes-days-due-to-1000x-ratio-between-fvco-and-loop-bandwidth",
    "type-ii-pll-oscillates-in-phase-because-stabilizing-resistor-r1-was-omitted-or-c2-is-comparable-to-c1",
    "huge-random-jitter-wandering-around-lock-caused-by-pfd-cp-dead-zone-near-zero-phase-error",
    "strong-reference-spurs-at-f0-plus-minus-fref-due-to-up-dn-current-mismatch-and-switch-charge-injection",
    "excess-integrated-rms-jitter-from-suboptimal-loop-bandwidth-relative-to-inband-and-vco-noise-crossover"
  ],
  "limitations": [
    "continuous-time-linear-phase-model-breaks-down-when-loop-crossover-exceeds-roughly-one-tenth-of-fref",
    "single-pss-cannot-directly-solve-integer-n-pll-with-large-division-ratio-n-without-behavioral-divider-or-subblock-decomposition",
    "integer-n-architecture-suffers-20log10-n-inband-noise-amplification-unless-upgraded-to-fractional-n-with-higher-fref"
  ],
  "checklists": [
    "common-mos",
    "oscillator-and-pll",
    "current-mirror",
    "feedback-and-stb"
  ]
}
---

## 1. Thách thức Đa Thang Thời gian Của PLL & Kiến trúc Testbench Phân rã 4 Cấp

Kiểm chứng một **vòng khóa pha bơm điện tích loại II (`T2174`, Type-II Charge-Pump PLL)** kèm **bộ chia tần hồi tiếp (`T2178`)** là một trong những bài toán mô phỏng khó nhất của thiết kế vi mạch hỗn hợp tương tự–số vì **tỉ số đa thang thời gian (multi-timescale stiffness)** cực lớn: giả sử sóng mang VCO chạy ở $f_0 = 2{,}4\text{ GHz}$ ($T_0 = 416\text{ ps}$, đòi hỏi bước giải `maxstep <= 5..10 ps`), xung tham chiếu $f_{\text{ref}} = 20\text{ MHz}$ ($N = 120$), và băng thông vòng $f_c = 1\text{ MHz}$ với thời gian bắt khóa $T_{\text{lock}} \approx 15\text{ }\mu\text{s}$ — một lần chạy `tran` mức transistor toàn phần duy nhất phải tính toán qua **$36.000$ chu kỳ RF** (hàng triệu bước thời gian Newton-Raphson)! Nghiêm trọng hơn, nếu thả toàn khối chưa kiểm định vào chạy `tran` mù quáng, chỉ một lỗi nhỏ như đảo cực tính `UP/DN`, thiếu điện trở bù pha $R_1$ trong **bộ lọc vòng (`T2175`)**, hoặc **vùng chết (`T2172`, dead zone)** của PFD cũng khiến bạn mất hàng giờ chờ đợi chỉ để nhận về một đường $V_{\text{ctrl}}(t)$ đập vào biên nguồn!

![Cấu trúc Vòng Khóa Pha Bơm Điện tích Loại II: PFD + CP + Bộ lọc Rp/C1/C2 + VCO + Bộ chia N](../../diagrams/charge-pump-type2-pll.svg)

Để đạt tốc độ thiết kế nhanh gấp $50\times$ và độ tin cậy sign-off tuyệt đối theo Razavi Chương 16 (§16.2–§16.5, tr. 666–690), quy trình kiểm chứng công nghiệp bắt buộc chia tách thành **4 testbench chuyên biệt từ khối con lên toàn hệ thống**:
1. **Testbench Khối PFD + Charge Pump Mở Vòng (`Open-Loop PFD + CP Sweep`):** Quét sai lệch thời gian đầu vào $\Delta t \in [-500\text{ ps}, +500\text{ ps}]$ với bước mịn $2\text{ ps}$ quanh $\Delta t = 0$ để vẽ đường truyền điện tích trung bình $\overline{I_{\text{CP}}}(\Delta\phi)$ kiểm tra triệt để vùng chết, và quét DC điện áp nút lọc $V_{\text{ctrl}} \in [0{,}15\,V_{DD}, 0{,}85\,V_{DD}]$ đo độ lệch tĩnh $|I_{UP}(V_{\text{ctrl}}) - I_{DN}(V_{\text{ctrl}})|$ dự báo trực tiếp **vạch nhiễu giả tham chiếu (`T2177`, reference spur)**.
2. **Mô hình Miền Pha Tuyến tính AC (`s-Domain Phase-Domain Loop-Gain Check`):** Kiểm tra tức thì trong $0{,}1\text{ giây}$ hàm truyền vòng hở $L(s)$, tần số cắt $\omega_c$, **dự trữ pha (`T063`)** và hai hàm truyền nhiễu thông thấp $H_{\text{in}}(s)$ / thông cao $H_{\text{VCO}}(s)$ trên toàn dải biến thiên $K_{VCO,\min}..K_{VCO,\max}$ và hệ số chia $N_{\min}..N_{\max}$.
3. **Testbench Khóa Pha Quá độ Tăng tốc Lai (`Hybrid Behavioral-VCO/Divider + Transistor-PFD/CP/LF Lock Transient`):** Thay VCO tần số GHz bằng mô hình Verilog-A điều biến tần số sạch (hoặc giữ VCO transistor nhưng bước đầu chạy tỷ số chia rút gọn) để kiểm chứng quá trình kéo tần số (frequency acquisition), vọt lố bắt pha, dải áp ổn định $V_{\text{ctrl}}$ và biên độ gợn chu kỳ $\Delta V_{\text{ctrl,pp}}$ tại trạng thái khóa.
4. **Tổng hợp Ngân sách Nhiễu Pha & Jitter Tích phân Toàn Vòng (`Composite Phase-Noise & RMS Jitter Integration`):** Ghép kết quả `pss` + `pnoise` thực tế của từng khối con (VCO tự do, PFD+CP bị kích thích ở $f_{\text{ref}}$, bộ chia tần, và nhiễu nhiệt $4kT R_1$) qua đúng hàm truyền đóng vòng để tìm băng thông cắt tối ưu hóa tổng **jitter (`T047`)** RMS!

---

## 2. Thuật toán Tổng hợp Chính xác Bộ Lọc Vòng Bậc 3 & Phương trình Spur / Jitter

### 2.1. Công thức Đóng Thiết kế Bộ Lọc Vòng Bậc Ba Từ Đặc tả $\{f_{\text{ref}}, N, K_{VCO}, f_c, \text{PM}\}$
Tại sao PLL Loại II không bao giờ ổn định nếu bộ lọc vòng chỉ có một tụ điện $C_1$ nối đất? Vì bản thân VCO đã là một khâu tích phân pha lý tưởng $\frac{2\pi K_{VCO}}{s}$ (cực thứ nhất tại $s = 0$), còn tổ hợp PFD + CP bơm dòng vào tụ $C_1$ lại tạo thêm cực thứ hai ngay tại gốc tọa độ $\frac{I_P}{2\pi} \cdot \frac{1}{s C_1}$! Hai cực tại $s = 0$ làm góc pha vòng hở bắt đầu ngay từ **$-180^\circ$** ($\text{PM} = 0^\circ$ — dao động tự kích!). Để cứu hệ thống (Razavi §16.2.1–§16.2.4, Phương trình 16.37–16.46):
- Mắc nối tiếp điện trở $R_1$ với tụ $C_1$ để tạo **zero ổn định nửa mặt phẳng trái** $\omega_z = \frac{1}{R_1 C_1}$ kéo pha vọt lên dương;
- Mắc song song thêm tụ nhỏ $C_2 \approx \left(\frac{1}{8}\text{ đến }\frac{1}{15}\right) C_1$ trực tiếp từ $V_{\text{ctrl}}$ xuống đất để lọc xung điện áp bậc thang $I_P R_1$ mỗi nhịp $f_{\text{ref}}$, sinh ra **cực thứ ba** $\omega_{p3} = \frac{C_1 + C_2}{R_1 C_1 C_2}$.

Trở kháng bộ lọc $Z_{\text{LF}}(s)$ và hàm truyền vòng hở $L(s)$ (với $K_{VCO}$ tính bằng $\text{Hz/V}$, nên độ nhạy góc là $2\pi K_{VCO}\text{ rad/(s}\cdot\text{V)}$) là:

$$
Z_{\text{LF}}(s) = \frac{1 + s R_1 C_1}{s (C_1 + C_2) \left(1 + s R_1 \dfrac{C_1 C_2}{C_1 + C_2}\right)}, \qquad L(s) = \frac{I_P}{2\pi} \cdot Z_{\text{LF}}(s) \cdot \frac{2\pi K_{VCO}}{N s} = \frac{I_P K_{VCO}}{N} \cdot \frac{1 + s/\omega_z}{s^2 (C_1 + C_2) (1 + s/\omega_{p3})}
$$

Góc dự trữ pha $\text{PM}(\omega)$ đạt **cực đại tuyệt đối** đúng tại tần số trung bình nhân hình học $\omega_c = \sqrt{\omega_z \omega_{p3}}$! Đặt tỉ số phân tách cực–zero là $\gamma = \frac{\omega_{p3}}{\omega_z} = 1 + \frac{C_1}{C_2}$, thuật toán tổng hợp 4 bước không cần mò mẫm là:
1. **Chọn băng thông cắt vòng $\omega_c = 2\pi f_c$ tuân thủ giới hạn Gardner:** $f_c \le \frac{f_{\text{ref}}}{10}$ (thường chọn $f_c \in [\frac{f_{\text{ref}}}{20}, \frac{f_{\text{ref}}}{12}]$ để xấp xỉ liên tục đúng hoàn toàn và nén mạnh spur tham chiếu).
2. **Từ chỉ tiêu dự trữ pha mục tiêu $\text{PM}_{\max}$ (ví dụ $55^\circ\text{–}62^\circ$), tính hệ số tách $\gamma$:**

$$
\text{PM}_{\max} = \arctan\!\left(\sqrt{\gamma}\right) - \arctan\!\left(\frac{1}{\sqrt{\gamma}}\right) \implies \sqrt{\gamma} = \tan\text{PM}_{\max} + \sec\text{PM}_{\max} = \frac{1 + \sin\text{PM}_{\max}}{\cos\text{PM}_{\max}}
$$

*(Ví dụ vàng: muốn $\text{PM}_{\max} = 56{,}4^\circ \implies \sqrt{\gamma} = 3{,}0 \implies \gamma = 9 \implies C_1 = 8\,C_2$, đặt $\omega_z = \omega_c / 3$ và $\omega_{p3} = 3\,\omega_c$; muốn $\text{PM}_{\max} = 61{,}9^\circ \implies \sqrt{\gamma} = 3{,}75 \implies \gamma \approx 14 \implies C_1 = 13\,C_2$!)*
3. **Chốt dòng bơm $I_P$ (thường $50\text{ }\mu\text{A}\text{–}500\text{ }\mu\text{A}$) và giải chính xác $C_2, C_1, R_1$ để $|L(j\omega_c)| = 1$:**

$$
\omega_z = \frac{\omega_c}{\sqrt{\gamma}}, \qquad \omega_{p3} = \omega_c \sqrt{\gamma}, \qquad C_1 + C_2 = \frac{I_P K_{VCO}}{N \omega_c^2} \sqrt{\gamma} \cdot \frac{\sqrt{1 + \gamma}}{\gamma} = \frac{I_P K_{VCO}}{N \omega_c^2} \quad \text{(xấp xỉ cực gọn!)}
$$

Kiểm tra đại số tuyệt đẹp: tại $\omega_c = \sqrt{\omega_z \omega_{p3}}$, tỉ số biên độ $\frac{\sqrt{1 + (\omega_c/\omega_z)^2}}{\sqrt{1 + (\omega_c/\omega_{p3})^2}} = \frac{\sqrt{1 + \gamma}}{\sqrt{1 + 1/\gamma}} = \sqrt{\gamma}$! Thay vào $|L(j\omega_c)| = 1$ cho kết quả **chính xác tuyệt đối không xấp xỉ**:

$$
C_2 = \frac{I_P K_{VCO}}{N \omega_c^2 \sqrt{\gamma}}, \qquad C_1 = (\gamma - 1)\,C_2, \qquad R_1 = \frac{1}{\omega_z C_1} = \frac{\sqrt{\gamma}}{\omega_c C_1}
$$

### 2.2. Định lượng Biên tần Giả Tham chiếu (`Reference Spur`) & Ngân sách Jitter Đa Nguồn
Ở trạng thái khóa xác lập của vòng Loại II, điện áp trung bình trên tụ tích phân $C_1$ không đổi qua mỗi chu kỳ $T_{\text{ref}} = 1/f_{\text{ref}}$, nên **tổng điện tích một chiều ròng đi vào bộ lọc vòng trong trọn một chu kỳ bằng 0 tuyệt đối** ($\oint_0^{T_{\text{ref}}} i_{\text{CP}}(t)\,dt = 0$). Tuy nhiên, khi tồn tại lệch dòng tĩnh $\Delta I_{\text{CP}} = I_{UP} - I_{DN}$ trên khoảng xung đặt lại tối thiểu $t_{\text{rst}}$, lệch trễ đóng cắt, điện tích phun/chia sẻ công tắc $\Delta Q_{\text{sw}}$ hoặc dòng rò $I_{\text{leak}}$ trên nút $V_{\text{ctrl}}$, vòng hồi tiếp buộc phải dịch pha tĩnh để bơm xung bù ngược dấu, tạo ra dạng sóng dòng tuần hoàn trung bình không nhưng có **biên độ hài bậc một Fourier khác không** $I_{1,\text{pk}} = \frac{2}{T_{\text{ref}}}\left|\int_0^{T_{\text{ref}}} i_{\text{CP}}(t)e^{-j2\pi f_{\text{ref}} t}\,dt\right|$. Đặt gói điện tích hài bậc một tương đương $Q_{1,\text{eq}} \triangleq \frac{T_{\text{ref}}}{2} I_{1,\text{pk}} = \left|\int_0^{T_{\text{ref}}} i_{\text{CP}}(t)e^{-j2\pi f_{\text{ref}} t}\,dt\right|$, biên độ gợn áp hài bậc một $V_{\text{ctrl},1,\text{pk}} = I_{1,\text{pk}} \left|Z_{\text{LF}}(j 2\pi f_{\text{ref}})\right|$ điều tần biên hẹp VCO ($K_{VCO}$ tính bằng $\text{Hz/V}$) sinh ra cặp vạch phổ giả tại $f_0 \pm f_{\text{ref}}$ (Razavi §16.3.1–§16.3.2):

$$
P_{\text{spur}}(\pm f_{\text{ref}}) \approx 20\log_{10}\!\left( \frac{\Delta\phi_{\text{pk}}}{2} \right) = 20\log_{10}\!\left( \frac{K_{VCO} \cdot V_{\text{ctrl},1,\text{pk}}}{2 f_{\text{ref}}} \right) = 20\log_{10}\!\left( Q_{1,\text{eq}} \cdot \left|Z_{\text{LF}}(j 2\pi f_{\text{ref}})\right| \cdot K_{VCO} \right) \quad [\text{dBc}]
$$

*(Kiểm tra thứ nguyên: $[\text{C}]\cdot[\Omega]\cdot[\text{Hz/V}] = 1$; cụ thể $Q_{1,\text{eq}} \approx |I_{\text{leak}}| T_{\text{ref}}$ với dòng rò tĩnh bù bởi xung hẹp, $Q_{1,\text{eq}} \approx \pi f_{\text{ref}}(t_{\text{rst}} + \Delta t_{\text{skew}})\,|\Delta I_{\text{CP}}|\,t_{\text{rst}}$ khi xét khử lưỡng cực liền kề của lệch dòng trong $t_{\text{rst}}$, và cận trên $Q_{1,\text{eq}} \le |\Delta Q_{\text{sw}}|$ với gói lỗi phun/chia sẻ điện tích bất đối xứng.)* Nhờ có tụ $C_2$, ở tần số cao $f_{\text{ref}} \gg f_{p3}$, $|Z_{\text{LF}}(j 2\pi f_{\text{ref}})| \approx \frac{1}{2\pi f_{\text{ref}} C_2}$ giúp nén mạnh vạch spur!

Đối với tổng **nhiễu pha đóng vòng** $S_{\phi,\text{out}}(f)$ và **RMS Jitter tuyệt đối** $\sigma_{t,\text{rms}}$ tích phân từ $f_{\min}$ tới $f_{\max}$ (Razavi §16.3.2 & §16.5, `T2179`):

$$
S_{\phi,\text{out}}(f) = \left|N \cdot \frac{L(j2\pi f)}{1 + L(j2\pi f)}\right|^2 \!\left( S_{\phi,\text{ref}}(f) + \frac{4\pi^2 S_{i,\text{CP}}(f)}{I_P^2} \right) + \left|\frac{2\pi K_{VCO}}{j2\pi f \big(1 + L(j2\pi f)\big)}\right|^2 \!4 k T R_1 + \left|\frac{1}{1 + L(j2\pi f)}\right|^2 \!S_{\phi,\text{VCO}}(f)
$$

$$
\sigma_{t,\text{rms}} = \frac{1}{2\pi f_0} \sqrt{ \int_{f_{\min}}^{f_{\max}} 2 \cdot 10^{\mathcal{L}_{\text{PLL}}(f)/10}\,df }
$$

Băng thông cắt $f_c$ **tối ưu hóa jitter** chính là giao điểm mà mật độ nhiễu pha trong dải (từ Tham chiếu + PFD + CP nhân lên $N^2$, tức cộng $+20\log_{10}N\text{ dB}$!) cắt đúng đường nhiễu pha tự do ngoài dải của VCO!

---

## 3. Bất biến Kỹ thuật & Các Bẫy Lỗi Thực chiến (Invariants & Traps)

- **[INV-PLL-01] Bất biến Xung Chống Vùng Chết PFD (`Anti-Dead-Zone Reset Pulse` $t_{\text{rst}}$ Tối ưu):** Nếu đường đặt lại cổng NAND trong PFD quá nhanh khiến xung đồng thời `UP = DN = 1` chưa kịp vượt trọn ngưỡng mở công tắc dòng Charge Pump tại góc chậm `SS`, hệ số khuếch đại tách pha $K_{\text{PD}}$ rơi về $0$ quanh $\Delta\phi = 0$ — VCO trôi tự do không có lực kéo hồi tiếp cho tới khi vấp rìa vùng chết! Ngược lại, nếu chèn trễ đặt lại $t_{\text{rst}}$ quá rộng (ví dụ $> 500\text{ ps}$), cả hai nguồn dòng `I_UP` và `I_DN` cùng mở lâu mỗi chu kỳ $T_{\text{ref}}$ vừa bơm thẳng nhiễu nhiệt/flicker vào $V_{\text{ctrl}}$, vừa nhân lớn vạch giả tham chiếu $\propto |\Delta I_{\text{CP}}| t_{\text{rst}}$! Quy tắc vàng: thiết kế $t_{\text{rst}} \approx 150\text{–}300\text{ ps}$ (đủ để hai xung dòng chồng nhau đạt $\ge 80\%$ biên độ đỉnh tại góc `SS`, không lớn hơn!).
- **[INV-PLL-02] Bất biến Bám Tỉ lệ $\omega_c \propto \sqrt{I_P K_{VCO} / N}$ Khi Quét Băng Rộng:** Trong bộ tổng hợp tần số đa kênh có $N$ thay đổi từ $N_{\min}$ đến $N_{\max}$ và $K_{VCO}$ biến thiên qua các ngân hàng tụ, tích $(K_{VCO}/N)$ có thể trôi gấp $2\text{–}4\times$, đẩy điểm cắt $\omega_c$ trượt khỏi đỉnh hình chuông của $\text{PM}(\omega)$! Giải pháp chuẩn công nghiệp: lập trình ngân hàng dòng bơm số $I_P \propto \frac{N}{K_{VCO}}$ để giữ nguyên $\omega_c$ và dự trữ pha bất biến trên mọi kênh tần số!
- **[TRAP-PLL-01] Bẫy Đấu Nhầm Cực tính Dấu Giữa $K_{VCO}$ Âm Và `UP/DN` Gây Chốt Cứng Vào Biên Nguồn:** Một LC-VCO dùng varactor PMOS hoặc NMOS đảo đầu thường có độ dốc **âm** ($K_{VCO} < 0$: tăng $V_{\text{ctrl}}$ làm giảm tần số $f_0$!). Nếu bạn giữ nguyên đấu nối Charge Pump thông thường (`UP` bơm dòng nâng $V_{\text{ctrl}}$, `DN` rút dòng hạ $V_{\text{ctrl}}$), vòng hồi tiếp âm biến thành **hồi tiếp dương $100\%$**, đóng sập $V_{\text{ctrl}}$ dính chặt vào $V_{DD}$ hoặc $0\text{ V}$ ngay lập tức! Bắt buộc kiểm tra dấu $\partial f_0 / \partial V_{\text{ctrl}}$ trước và hoán vị hai đầu vào `REF`/`FB` của PFD (hoặc hoán vị `UP`/`DN`) khi $K_{VCO} < 0$.
- **[TRAP-PLL-02] Bẫy Chia Sẻ Điện tích (`Charge Sharing`) Khi Ngắt Công tắc Charge Pump:** Khi `UP` và `DN` tắt, điện thế tại nút cực máng nguồn dòng `I_UP` bị kéo lên sát $V_{DD}$ còn nút nguồn dòng `I_DN` sụt sát $0\text{ V}$; ở chu kỳ kế tiếp khi hai công tắc bật trong thời gian $t_{\text{rst}}$, tụ ký sinh của hai nút này xả/nạp thẳng vào $V_{\text{ctrl}}$ gây bước nhảy điện tích lệch dữ dội mỗi khi $V_{\text{ctrl}} \neq V_{DD}/2$! Khắc phục bằng nhánh công tắc phụ nối sang bộ đệm khuếch đại thuật toán độ lợi đơn vị (`Unity-Gain Replica Buffer`) giữ áp hai nút chờ luôn bằng đúng $V_{\text{ctrl}}$ (Razavi §16.3.1, Hình 16.47, tr. 680)!

---

## 4. Ma trận Chẩn đoán Lỗi & Lộ trình Nâng cấp Kiến trúc PLL

| Triệu chứng thất bại trong Testbench PLL | Nguyên nhân vật lý / thiết kế gốc rễ | Phép đo xác nhận trong Spectre | Giải pháp khắc phục / Nâng cấp cấu trúc |
|---|---|---|---|
| $V_{\text{ctrl}}(t)$ dao động hình sin tần số $\sim f_c$ không bao giờ tắt dần | Quên điện trở $R_1$, tụ dập gợn $C_2$ chọn quá lớn ($C_2 > C_1/4$ làm sập $\text{PM} < 30^\circ$), hoặc $K_{VCO}$ thực tế lớn gấp $3\times$ ước tính | Chạy mô hình AC miền pha với $K_{VCO}$ trích từ `pss` thực của VCO | Tái tổng hợp $\{R_1, C_1, C_2\}$ với $\gamma = 9\text{–}14$ ($C_1 \ge 8\,C_2$) tại đúng $\max(K_{VCO})$ và $\min(N)$ |
| Tần số khóa đúng trung bình nhưng $V_{\text{ctrl}}$ trôi lững lờ qua lại vài mV và jitter đỉnh–đỉnh vọt cao | Vùng chết PFD+CP quanh $\Delta\phi = 0$ do trễ reset quá ngắn | Chạy quét $\Delta t \in [-200\text{ ps}, +200\text{ ps}]$ mở vòng: đường $\overline{I_{\text{CP}}}(\Delta t)$ nằm ngang bằng $0$ ở vùng tâm | Chèn chuỗi số chẵn cổng inverter kích thước chuẩn vào đường `RST` của PFD để tạo xung tối thiểu $t_{\text{rst}} \approx 200\text{ ps}$ |
| Phổ FFT sóng ra có hai vạch nhọn cao $> -45\text{ dBc}$ tại $f_0 \pm f_{\text{ref}}$ | Lệch dòng $I_{UP} \neq I_{DN}$ do $r_O$ hữu hạn của Charge Pump hoặc chia sẻ điện tích công tắc | Quét DC $V_{\text{ctrl}}$ đo $(I_{UP} - I_{DN})/I_P$; tắt dòng rò để tách phần phun điện tích | Nâng Charge Pump lên cascode rộng dải (`topo-lvccml-wide-swing-mirror`) kết hợp OTA phản hồi ghim dòng $I_{UP}=I_{DN}$ + đệm replica chống chia sẻ điện tích; thêm mắt lọc RC bậc 4 sau $C_2$ |
| Sàn nhiễu pha phẳng trong dải ($< f_c$) quá cao giới hạn RMS jitter tổng dù VCO rất sạch | Hệ số chia $N = f_0 / f_{\text{ref}}$ quá lớn làm nhân nhiễu PFD/CP lên $+20\log_{10}N\text{ dB}$, hoặc dòng $I_P$ quá nhỏ | Vẽ chồng các đường thành phần nhiễu quy về ngõ ra trên đồ thị log-log | Tăng dòng $I_P$ (giảm nhiễu nhiệt CP tỉ lệ $1/I_P$); nếu bước kênh hẹp ép $f_{\text{ref}}$ thấp trong Integer-N thì nâng cấp lên **Fractional-N $\Delta\Sigma$ PLL** để dùng $f_{\text{ref}}$ cao gấp $10\text{–}50\times$! |

---

## 5. Thích ứng Đa Tiến trình (180nm–45nm) & Bộ Testbench Spectre 15.1 + Tổng hợp Python

### 5.1. Lưu ý Thực tế Ở Công nghệ Nanomet Nguồn Thấp (90nm / 65nm / 45nm)
- **Thu hẹp cửa sổ tuân thủ $V_{\text{ctrl}}$:** Trên nguồn $1{,}0\text{ V}$, Charge Pump dùng gương cascode tiêu thụ ít nhất $2 V_{DS,\min} \approx 250\text{ mV}$ mỗi đầu trên và dưới, chỉ để lại cửa sổ tuyến tính $V_{\text{ctrl}} \in [0{,}25\text{ V}, 0{,}75\text{ V}]$ rộng đúng **$0{,}5\text{ V}$**! Bắt buộc giới hạn dải tinh của VCO nằm trọn trong $[0{,}25\text{ V}, 0{,}75\text{ V}]$ và giao phần bắt tần số thô cho bộ hiệu chuẩn mảng tụ chuyển mạch số (AFC) trước khi đóng vòng analog!
- **Dòng rò cổng oxit mỏng trên tụ lọc vòng $C_1$ lớn:** Ở 65nm/45nm, tuyệt đối **không dùng tụ cổng MOS oxit mỏng (core thin-oxide MOScap)** cho tụ tích phân $C_1$ hàng chục $\text{pF}$! Dòng rò xuyên hầm cực cổng $I_G$ hàng chục $\text{nA}$ ở $125\,^\circ\text{C}$ chảy liên tục khỏi nút $V_{\text{ctrl}}$ sẽ gây vạch giả tham chiếu khổng lồ! Bắt buộc dùng **tụ kim loại MOM/MIM** hoặc tụ MOS lớp dày I/O ($1{,}8\text{ V}/2{,}5\text{ V}$ thick-oxide) có dòng rò $< 1\text{ pA}$!

### 5.2. Kịch bản Python Chuẩn Xác Tổng hợp Bộ Lọc Vòng Bậc 3 & Kiểm Tra Dự Trữ Pha (`pll_lpf_synth.py`)
```python
#!/usr/bin/env python3
"""Exact 3rd-Order Type-II Charge-Pump PLL Loop Filter Synthesis & Phase Margin Audit."""
import math

def synthesize_type2_lpf(f_ref_hz, N_div, kvco_hz_per_v, ip_amp, fc_hz, pm_target_deg=58.0):
    assert fc_hz <= 0.1 * f_ref_hz, "Vi pham gioi han on dinh roi rac Gardner: fc phai <= f_ref / 10!"
    wc = 2.0 * math.pi * fc_hz
    pm_rad = math.radians(pm_target_deg)
    sqrt_gamma = (1.0 + math.sin(pm_rad)) / math.cos(pm_rad)
    gamma = sqrt_gamma ** 2

    c2 = (ip_amp * kvco_hz_per_v) / (N_div * (wc ** 2) * sqrt_gamma)
    c1 = (gamma - 1.0) * c2
    r1 = sqrt_gamma / (wc * c1)
    fz_hz = 1.0 / (2.0 * math.pi * r1 * c1)
    fp3_hz = (c1 + c2) / (2.0 * math.pi * r1 * c1 * c2)
    return {
        "gamma": round(gamma, 3),
        "R1_kOhm": round(r1 / 1e3, 3),
        "C1_pF": round(c1 * 1e12, 3),
        "C2_pF": round(c2 * 1e12, 3),
        "fz_kHz": round(fz_hz / 1e3, 2),
        "fc_kHz": round(fc_hz / 1e3, 2),
        "fp3_kHz": round(fp3_hz / 1e3, 2),
        "PM_deg": round(math.degrees(math.atan(wc / (2 * math.pi * fz_hz)) - math.atan(wc / (2 * math.pi * fp3_hz))), 2),
    }

if __name__ == "__main__":
    # Vi du: fref=25 MHz, fout=2.4 GHz (N=96), KVCO=60 MHz/V, Ip=150 uA, fc=1.2 MHz, PM=58 deg
    print(synthesize_type2_lpf(25e6, 96, 60e6, 150e-6, 1.2e6, pm_target_deg=58.0))
```

### 5.3. Mẫu Netlist Spectre 15.1 Kiểm tra Vùng Chết Mở Vòng PFD + Charge Pump (`tb_pfd_cp_deadzone.scs`)
```spice
// tb_pfd_cp_deadzone.scs — Open-Loop PFD + Charge-Pump Transfer & Dead-Zone Audit
simulator lang=spectre
global 0

parameters vdd_val=1.2 vctrl_dc=0.6 fref=25M Tref=1/fref dt_skew=0p

VDD   (vdd   0) vsource dc=vdd_val type=dc
VCTRL (vctrl 0) vsource dc=vctrl_dc type=dc

// Xung tham chieu co dinh tai t = 5ns; xung hoi tiep dich som/muon theo dt_skew
VREF (clk_ref 0) vsource type=pulse val0=0 val1=vdd_val delay=5n \
     rise=30p fall=30p width=0.5*Tref period=Tref
VDIV (clk_div 0) vsource type=pulse val0=0 val1=vdd_val delay=(5n + dt_skew) \
     rise=30p fall=30p width=0.5*Tref period=Tref

// Khoi DUT: PFD + Charge Pump noi ra nguon ap VCTRL de do dong bom tinh I(VCTRL:p)
// X_PFD_CP (clk_ref clk_div up dn vctrl ibias vdd 0) pfd_cp_top

save clk_ref clk_div up dn VCTRL:p
saveOptions options save=selected

// Quet dt_skew tu -300ps den +300ps buoc 10ps quanh 0ps de phat hien vung phang Dead-Zone!
sw_skew sweep param=dt_skew start=-300p stop=300p step=10p {
    tran_dz tran stop=4*Tref maxstep=2p errpreset=conservative
}
// Tinh dien tich trung binh moi chu ky trong OCEAN: Q_avg = integ(-i("VCTRL:p") 2*Tref 3*Tref)
// Dieu kien DAT: dQ_avg / d(dt_skew) tai dt_skew=0 khop Ip +- 5% (KHONG lom ve 0!)
```

---

## 6. Đối chiếu Sách Razavi, Nguồn GitHub Đã Kiểm định & Bảng Thuật ngữ Chuẩn CLB

### 6.1. Mốc Tọa độ Chính xác Trong Sách Razavi (2nd Edition) & Kho GitHub
- **Razavi Chương 16 (*Phase-Locked Loops*):** §16.1 *Simple PLL* — bộ tách pha XOR, động học khóa và nhược điểm dải bắt hẹp của vòng loại I (tr. 655–666), §16.2 *Charge-Pump PLLs* — bài toán giới hạn bắt tần số, PFD ba trạng thái, mạch bơm điện tích, động học vòng khóa pha loại II và quy trình thiết kế bộ lọc vòng bậc ba (tr. 666–677, Phương trình 16.37–16.47, Ví dụ 16.7–16.11), §16.3 *Nonideal Effects in PLLs* — vùng chết PFD, bất cân xứng dòng UP/DN, chia sẻ điện tích và đối ngẫu băng thông truyền nhiễu của tham chiếu so với VCO (tr. 677–683), §16.5 *Applications: Frequency Multiplication and Synthesis* — bộ chia tần hồi tiếp, mạch đếm nuốt xung (pulse-swallow divider) và sự nhân nhiễu trong dải lên $M^2$ lần (tr. 685–690, Phương trình 16.51, 16.55).
- **Đối chiếu Nguồn Mở Đã Kiểm Định:**
  - `iic-jku/radio-frequency-integrated-circuits` (`0799d7eaf993`, Apache-2.0): Quy trình phân tích hàm truyền vòng PLL, tổng hợp bộ lọc thụ động và đánh giá tổng nhiễu pha tích phân.
  - `Arcadia-1/veriloga-skills` (`7c5d3f03a162`) & `Arcadia-1/circuits-and-systems-classroom` (`f377bd965e8a`, MIT): Xây dựng khối kiểm thử hành vi lai giúp rút ngắn thời gian mô phỏng bắt khóa từ hàng ngày xuống vài phút.

### 6.2. Bảng Thuật ngữ Chuẩn CLB Vi Mạch Sử dụng trong Thẻ
| Mã CLB | Thuật ngữ Tiếng Anh | Thuật ngữ Tiếng Việt Chuẩn | Ý nghĩa Kỹ thuật Cốt lõi |
|---|---|---|---|
| `T2171` | phase/frequency detector, PFD | bộ tách pha–tần số | Phát hiện đồng thời cả sai số tần số lẫn sai số pha trong dải $\pm 2\pi\text{ rad}$ giúp mở rộng không giới hạn dải bắt khóa |
| `T016` / `T2174` | charge pump / type-II charge-pump PLL | bơm điện tích / vòng khóa pha bơm điện tích loại II | Hệ chứa hai khâu tích phân lý tưởng tại $s = 0$ giúp triệt tiêu hoàn toàn sai số pha tĩnh cho cả bước nhảy pha lẫn bước nhảy tần số |
| `T2172` | dead zone | vùng chết (trong PFD/CP) | Khoảng sai lệch pha nhỏ quanh $0$ mà xung điều khiển quá hẹp không kịp bật dòng bơm, làm mất tác dụng khóa pha |
| `T2175` | loop filter | bộ lọc vòng | Mạng $R_1\text{–}C_1\text{–}C_2$ tạo zero ổn định vòng và cực dập gợn điện áp điều khiển |
| `T2177` | reference spur | vạch nhiễu giả tần số tham chiếu | Cặp biên tần điều chế ký sinh tại $f_0 \pm k f_{\text{ref}}$ sinh ra do gợn chu kỳ trên đường $V_{\text{ctrl}}$ |
| `T2179` | PLL noise transfer bandwidth trade-off | đối ngẫu băng thông truyền nhiễu trong PLL | Vòng PLL là bộ lọc thông thấp đối với nhiễu Ref/PFD/CP nhưng là bộ lọc thông cao đối với nhiễu pha VCO |
