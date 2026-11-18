---
{
  "id": "tech-cp-pll-third-order-loop-filter-synthesis",
  "kind": "technique",
  "domain": "sampled-and-clocked",
  "title_vi": "Quy trình Tổng hợp Chính xác Bộ lọc Vòng Bậc Ba cho PLL Bơm Điện tích Loại II (3rd-Order Type-II CP-PLL Loop Filter Synthesis)",
  "title_en": "Exact Closed-Form Synthesis of Third-Order Type-II Charge-Pump PLL Loop Filters",
  "summary": "Thuật toán tổng hợp giải tích chính xác các thông số linh kiện thụ động {IP, RP, C1, C2} từ tập chỉ tiêu đầu vào {f_REF, N, K_VCO, f_c, PM}: dẫn xuất hàm truyền vòng hở bậc ba L(s), điều kiện tối đa hóa dự trữ pha tại trung bình nhân hình học wc = sqrt(wz*wp3), hệ thức đóng b = C1/C2 = 2*tan^2(PM) + 2*tan(PM)*sec(PM), trần ổn định rời rạc Gardner wc <= w_REF/10, sự đánh đổi giữa độ nhô đỉnh Jitter Peaking và tốc độ khóa quá độ, cùng kỹ thuật tự bù biến thiên PVT của tích số IP*K_VCO.",
  "diagram": "../../diagrams/charge-pump-type2-pll.svg",
  "razavi_refs": [
    {
      "chapter": 16,
      "section": "16.2.4, 16.5.1",
      "pages": "671-677, 685-687",
      "equations": ["16.37", "16.39", "16.41", "16.44", "16.45", "16.46", "16.47", "16.49", "16.50", "16.53", "16.54"]
    }
  ],
  "glossary_codes": [
    "T016",
    "T042",
    "T051",
    "T063",
    "T064",
    "T069",
    "T854",
    "T865",
    "T1575",
    "T1614",
    "T1642",
    "T1678",
    "T1684",
    "T1804",
    "T1805",
    "T2166",
    "T2167",
    "T2174",
    "T2175",
    "T2176",
    "T2177",
    "T2179"
  ],
  "process_agnostic": true,
  "roles": {
    "zero_forming_branch_rp_c1": "Nhánh nối tiếp điện trở RP và tụ tích phân chính C1 (ký hiệu CP trong Razavi) tạo zero nửa mặt phẳng trái wz = 1/(RP*C1) để kéo pha vòng hở rời khỏi mốc mất ổn định -180 độ.",
    "ripple_suppression_cap_c2": "Tụ nhỏ C2 mắc song song toàn nhánh (RP + C1) hấp thụ xung dòng chữ nhật +-IP mỗi nhịp so pha, triệt bước nhảy áp tức thời IP*RP và sinh cực bậc ba wp3 = (C1+C2)/(RP*C1*C2).",
    "phase_margin_peak_placement": "Quy luật đặt tần số cắt độ lợi đơn vị wc đúng tại trung bình nhân hình học sqrt(wz*wp3) để đạt dự trữ pha cực đại với tỷ số diện tích tụ C1/C2 nhỏ nhất.",
    "programmable_ip_gain_tracking": "Cơ chế lập trình số dòng bơm điện tích IP tỷ lệ thuận với hệ số chia N và nghịch đảo với K_VCO để ghim cố định băng thông wc và dự trữ pha PM qua mọi kênh và góc PVT."
  },
  "symptoms_addressed": [
    "trial-and-error-pll-loop-filter-sizing-causing-ringing-or-instability",
    "phase-margin-collapse-when-ripple-capacitor-c2-is-added-naively",
    "excessive-jitter-peaking-in-cascaded-clock-recovery-pll-chains",
    "loop-bandwidth-and-damping-drift-across-channel-divide-ratio-n-and-pvt"
  ],
  "limitations": [
    "continuous-time-s-domain-model-breaks-down-above-gardner-limit-fref-over-10",
    "large-on-chip-integrating-capacitor-c1-occupies-significant-die-area-for-narrow-bandwidths",
    "thermal-noise-of-loop-filter-resistor-rp-adds-phase-noise-near-crossover-wc"
  ],
  "checklists": [
    "common-mos",
    "oscillator-and-pll",
    "feedback-and-stb",
    "spectre-pss-pnoise"
  ]
}
---

## 1. Bản chất Nguyên lý, Sơ đồ Mạch & Vai trò Từng Nhánh Cấu trúc

Trong thẻ cấu trúc cơ sở `topo-charge-pump-type2-pll`, chúng ta đã hiểu vì sao **vòng khóa pha bơm điện tích loại II** (`type-II charge-pump PLL` — `T2174`) chứa **hai bộ tích phân lý tưởng** (`two ideal integrators` — `T1804`) tạo nên **hai cực tại gốc tọa độ** (`Two Poles at Origin` — `T1805`, dịch pha nền $-180^\circ$), đòi hỏi bắt buộc phải có điện trở $R_P$ nối tiếp tụ tích phân $C_1$ để mở ra **zero ở nửa mặt phẳng trái** (`left-half-plane zero` — `T1678`) cứu ổn định, đồng thời phải mắc song song thêm tụ lọc gợn $C_2$ để chặn bước nhảy điện áp $\Delta V_{cont} = I_P R_P$ (Razavi §16.2.4, Hình 16.35 & 16.38).

Tuy nhiên, trong thực hành thiết kế công nghiệp, người kỹ sư không bao giờ được phép "chọn đại $C_2 = C_1/10$ rồi dùng công thức xấp xỉ bậc hai $\zeta, \omega_n$ để mò mẫm"! Khi thêm tụ $C_2$, hệ thống biến thành một **hệ thống ba cực** (`three-pole system` — `T1642`) thực thụ mà công thức bậc hai đánh giá sai lệch tới $12^\circ \sim 18^\circ$ dự trữ pha và làm lệch tần số cắt độ lợi đơn vị (`gain crossover frequency` — `T1614`, ký hiệu $\omega_c$). Thẻ kỹ thuật này cung cấp **quy trình tổng hợp đóng chính xác tuyệt đối (Exact Closed-Form 3rd-Order Loop Filter Synthesis)** — đi thẳng từ bộ chỉ tiêu hệ thống $\{f_{\text{REF}}, N, K_{VCO}, f_c, \text{PM}\}$ ra giá trị chính xác đến từng phần trăm của $\{I_P, R_P, C_1, C_2\}$, kiểm soát đồng thời **độ nhô đỉnh đóng vòng (Jitter Peaking)**, **suy hao vạch phổ tham chiếu**, **nhiễu nhiệt của chính điện trở $R_P$**, và **độ bền vững qua mọi góc PVT**!

![Sơ đồ vòng khóa pha bơm điện tích Loại II Bậc ba với mạng lọc vòng thụ động RP - C1 - C2 và bộ chia hồi tiếp /N](../../diagrams/charge-pump-type2-pll.svg)

Vai trò định lượng của từng phần tử trong **bộ lọc vòng** (`loop filter` — `T2175`) bậc hai thụ động (tạo vòng PLL bậc ba) được phân định rõ trên đồ thị Bode vòng hở $L(j\omega)$:
1. **Miền tần số rất thấp ($\omega \ll \omega_z$)**: Cả $C_1$ và $C_2$ nối song song đón dòng tích phân từ bơm điện tích với tổng điện dung tĩnh $C_{\text{tot}} = C_1 + C_2$. Biên độ vòng hở rơi dốc đứng **$-40\text{ dB/dec}$** ($1/\omega^2$) và pha nằm sát **$-180^\circ$**, cung cấp độ lợi vòng DC bằng vô cùng để khóa cứng sai số pha tĩnh bằng không.
2. **Miền cửa sổ ổn định giữa Zero và Cực bậc ba ($\omega_z < \omega < \omega_{p3}$)**: Zero $\omega_z = \frac{1}{R_P C_1}$ bẻ gãy độ dốc biên độ từ $-40\text{ dB/dec}$ sang **$-20\text{ dB/dec}$** (tại đó nhánh $R_P$ chiếm ưu thế tạo trở kháng phẳng $|Z_{\text{LF}}| \approx R_P \frac{C_1}{C_1 + C_2}$) và nâng đường cong pha nhô lên tạo thành một "ngọn đồi dự trữ pha dương" đạt đỉnh cực đại đúng tại trung bình nhân $\omega_m = \sqrt{\omega_z \omega_{p3}}$!
3. **Miền lọc gợn tần số cao ($\omega > \omega_{p3}$)**: Cực bậc ba $\omega_{p3} = \frac{C_1 + C_2}{R_P C_1 C_2}$ nối tắt điện trở $R_P$ qua dung kháng thấp của $C_2$, bẻ dốc biên độ vòng hở quay trở lại **$-40\text{ dB/dec}$** để dập tắt mạnh các hài xung nhịp $k \omega_{\text{REF}}$ và nhiễu lượng tử hóa $\Delta\Sigma$ tần số cao (nhưng đồng thời kéo pha tụt ngược về $-180^\circ$!).
4. **Mắt lọc RC thụ động bậc bốn tùy chọn ($R_3, C_3$ — 4th-Order Loop Filter)**: Khi cần ép vạch phổ giả tham chiếu (`reference spur` — `T2177`) xuống thêm $15 \sim 25\text{ dB}$ hoặc lọc nhiễu bộ điều chế $\Delta\Sigma$ bậc ba mà không phải thu hẹp băng thông vòng $\omega_c$, một mắt lọc phụ $R_3 - C_3$ có cực $\omega_{p4} = \frac{1}{R_3 C_3} \ge (5 \sim 8)\,\omega_c$ được chèn thêm trước chân $V_{cont}$ của VCO.

---

## 2. Hệ Phương trình Cốt lõi & Tư duy "Nhìn Mạch Đọc Nhanh" (Analysis by Inspection)

### 2.1. Dẫn xuất Chính xác Hàm truyền Vòng hở Bậc ba $L(s)$ và Điều kiện Cực đại Dự trữ Pha
Xét CP-PLL có dòng bơm $I_P$ $[\text{A}]$, độ nhạy VCO $K_{VCO} = 2\pi K_{VCO,\text{Hz}}$ $[\text{rad/(s}\cdot\text{V)}]$ và bộ chia hồi tiếp nguyên hoặc phân số trung bình $N$ ($f_{\text{out}} = N f_{\text{REF}}$, Razavi §16.5.1 PT 16.49–16.54, trong sách ký hiệu $M$). Trở kháng truyền đạt của mạng lọc vòng gồm nhánh nối tiếp $(R_P + \frac{1}{s C_1})$ mắc song song tụ $C_2$ là:

$$Z_{\text{LF}}(s) = \frac{V_{cont}(s)}{I_{\text{CP}}(s)} = \left(R_P + \frac{1}{s C_1}\right) \parallel \frac{1}{s C_2} = \frac{1 + s R_P C_1}{s (C_1 + C_2)\left(1 + s R_P \dfrac{C_1 C_2}{C_1 + C_2}\right)}$$

Đặt tỉ số điện dung không thứ nguyên **$b \equiv \frac{C_1}{C_2}$**, tần số góc zero **$\omega_z \equiv \frac{1}{R_P C_1}$**, và tần số góc cực bậc ba **$\omega_{p3} \equiv \frac{C_1 + C_2}{R_P C_1 C_2} = (b + 1)\omega_z$**. Hàm truyền vòng hở pha $L(s)$ viết gọn tuyệt đẹp là:

$$L(s) = \frac{I_P}{2\pi} \cdot Z_{\text{LF}}(s) \cdot \frac{K_{VCO}}{N s} = \frac{I_P K_{VCO}}{2\pi N (C_1 + C_2)} \cdot \frac{1 + s/\omega_z}{s^2 \left(1 + s/\omega_{p3}\right)}$$

Tại mọi tần số góc $\omega > 0$, góc pha của $L(j\omega)$ là $\angle L(j\omega) = -180^\circ + \arctan\left(\frac{\omega}{\omega_z}\right) - \arctan\left(\frac{\omega}{\omega_{p3}}\right)$, suy ra hàm **dự trữ pha** (`phase margin` — `T063`) phụ thuộc tần số cắt $\omega$:

$$\text{PM}(\omega) = 180^\circ + \angle L(j\omega) = \arctan\left(\frac{\omega}{\omega_z}\right) - \arctan\left(\frac{\omega}{\omega_{p3}}\right)$$

Để đạt độ bền vững tối đa trước biến thiên PVT của $I_P$ và $K_{VCO}$ (khiến tần số cắt $\omega_c$ trượt sang trái hoặc phải), ta **bắt buộc đặt tần số cắt độ lợi đơn vị $\omega_c$ (nơi $|L(j\omega_c)| = 1$) trùng khít với đỉnh cực đại của đường cong pha**! Lấy đạo hàm $\frac{d\,\text{PM}(\omega)}{d\omega} = \frac{1/\omega_z}{1 + (\omega/\omega_z)^2} - \frac{1/\omega_{p3}}{1 + (\omega/\omega_{p3})^2} = 0$, ta thu được hệ thức trung bình nhân hình học kinh điển:

$$\omega_c = \sqrt{\omega_z \cdot \omega_{p3}} \implies \frac{\omega_c}{\omega_z} = \frac{\omega_{p3}}{\omega_c} = \sqrt{\frac{\omega_{p3}}{\omega_z}} = \sqrt{b + 1} \equiv \gamma_c$$

Thế $\omega_c / \omega_z = \gamma_c$ và $\omega_c / \omega_{p3} = 1/\gamma_c$ vào biểu thức dự trữ pha và dùng công thức lượng giác $\tan(\alpha - \beta) = \frac{\tan\alpha - \tan\beta}{1 + \tan\alpha\tan\beta}$:

$$\tan(\text{PM}_{\max}) = \frac{\gamma_c - \dfrac{1}{\gamma_c}}{1 + \gamma_c \cdot \dfrac{1}{\gamma_c}} = \frac{\gamma_c^2 - 1}{2\gamma_c} = \frac{b}{2\sqrt{b + 1}}$$

Giải phương trình bậc hai $\gamma_c^2 - 2\tan(\text{PM})\,\gamma_c - 1 = 0$ (chọn nghiệm dương $\gamma_c > 1$), ta có **công thức giải tích đóng chính xác 100% không cần xấp xỉ** tính tỉ số tụ $b = C_1/C_2$ từ chỉ tiêu dự trữ pha $\text{PM}$ mong muốn:

$$\gamma_c = \sqrt{b + 1} = \tan(\text{PM}) + \sec(\text{PM}) = \frac{1 + \sin(\text{PM})}{\cos(\text{PM})}, \qquad b = \frac{C_1}{C_2} = 2\tan^2(\text{PM}) + 2\tan(\text{PM})\sec(\text{PM})$$

### 2.2. Bộ Ba Phương trình Đóng Tính Ra Ngay $C_2, C_1, R_P$ từ $|L(j\omega_c)| = 1$
Thay $\omega_z = \frac{\omega_c}{\gamma_c}$, $\omega_{p3} = \gamma_c \omega_c$ và $C_1 = b C_2 = (\gamma_c^2 - 1) C_2$ vào điều kiện biên độ cắt đơn vị $|L(j\omega_c)| = 1$:

$$\left|L(j\omega_c)\right| = \frac{I_P K_{VCO}}{2\pi N \gamma_c^2 C_2 \omega_c^2} \cdot \frac{\sqrt{1 + \gamma_c^2}}{\sqrt{1 + 1/\gamma_c^2}} = \frac{I_P K_{VCO}}{2\pi N \omega_c^2 (\gamma_c C_2)} = 1$$

Nhân tử căn thức rút gọn kỳ diệu thành đúng $\gamma_c$! Nhờ đó ta thu được **Thuật toán 4 Bước Vàng Tổng hợp Bộ lọc Vòng CP-PLL**:
1. **Bước 1 — Từ $\text{PM}$ tính hệ số tách cực $\gamma_c$ và tỉ số tụ $b$**:
   $$\gamma_c = \tan(\text{PM}) + \sec(\text{PM}), \qquad b = \gamma_c^2 - 1$$
2. **Bước 2 — Tính chính xác tụ lọc gợn $C_2$ và tụ tích phân chính $C_1$**:
   $$C_2 = \frac{I_P K_{VCO}}{2\pi N \omega_c^2 \gamma_c}, \qquad C_1 = b \cdot C_2$$
3. **Bước 3 — Tính chính xác điện trở bù zero $R_P$**:
   $$R_P = \frac{\gamma_c}{\omega_c C_1} = \frac{2\pi N \omega_c}{I_P K_{VCO}} \cdot \frac{\gamma_c^2}{\gamma_c^2 - 1} = \frac{2\pi N \omega_c}{I_P K_{VCO}} \cdot \left(\frac{b + 1}{b}\right)$$
4. **Bước 4 — Kiểm tra Nhiễu nhiệt của Điện trở $R_P$ lên Phổ Nhiễu Pha tại $\omega_c$**:
   Điện trở $R_P$ sinh nhiễu nhiệt trắng một phía $S_{v,RP} = 4 k T R_P$, đi qua bộ chia mạng lọc vòng $\frac{1/(s C_2)}{R_P + 1/(s C_1) + 1/(s C_2)} = \frac{b}{b+1}\frac{1}{1 + s/\omega_{p3}}$ ra $V_{cont}$ (tại $\omega_c = \omega_{p3}/\gamma_c$, bình phương biên độ truyền đạt là $\frac{b^2}{(b+1)(b+2)}$) và bị hàm truyền vòng đóng nén bởi $\frac{1}{|1 + L(j\omega)|^2}$ (bằng đúng $1$ tại $\omega_c$ khi $\text{PM} = 60^\circ$!). Mật độ phổ nhiễu pha đơn biên tại $\omega_c$ do riêng $R_P$ gây ra là:
   $$\mathcal{L}_{RP}(\omega_c) = 10\log_{10}\!\left[ \frac{1}{2} \cdot 4 k T R_P \cdot \frac{b^2}{(b+1)(b+2)} \left(\frac{K_{VCO}}{\omega_c}\right)^2 \cdot \frac{1}{|1 + L(j\omega_c)|^2} \right]$$
   Nếu $\mathcal{L}_{RP}(\omega_c)$ quá cao, chỉ cần **nhân đôi dòng bơm $I_P$** $\implies$ $R_P$ tự động giảm một nửa còn $C_1, C_2$ tăng gấp đôi, hạ nhiễu nhiệt của $R_P$ đi $3\text{ dB}$ mà giữ nguyên bất biến $\omega_c$ và $\text{PM}$!

**Bảng Tra Cứu Nhanh Chuẩn Thiết kế Bậc Ba ($\omega_c = \sqrt{\omega_z \omega_{p3}}$)**:

| Dự trữ pha mục tiêu ($\text{PM}$) | Hệ số tách cực $\gamma_c = \omega_c / \omega_z$ | Tỉ số tụ chính xác $b = C_1 / C_2$ | Hệ số sửa $R_P$: $(b+1)/b$ | Độ nhô đỉnh đóng vòng (Jitter Peaking) | Ứng dụng Khuyến nghị |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **$45^\circ$** | $2.414$ | $4.83$ ($\approx 5$) | $1.207$ | $3.20\text{ dB}$ (rung nhẹ) | Chỉ dùng khi cực kỳ thiếu diện tích tụ $C_1$. |
| **$55^\circ$** | $3.172$ | $9.06$ ($\approx 9$) | $1.110$ | $2.10\text{ dB}$ | Cân bằng gọn diện tích cho Clocking / IoT. |
| **$60^\circ$ (`T1684`)** | $3.732$ | **$12.93$ ($\approx 13$)** | $1.077$ | $1.70\text{ dB}$ | **Chuẩn vàng RF Synthesizer** (Wi-Fi / 5G / BLE). |
| **$65^\circ$** | $4.511$ | $19.35$ ($\approx 20$) | $1.052$ | $1.37\text{ dB}$ | Hệ thống có $K_{VCO}$ trôi rộng cần đỉnh pha phẳng. |
| **$70^\circ$** | $5.671$ | $31.16$ ($\approx 31$) | $1.032$ | $1.08\text{ dB}$ | Truyền dẫn nối tiếp nối tầng hạn chế Jitter Peaking. |

### 2.3. Trần Ổn định Rời rạc Gardner & Ví dụ Số Hoàn chỉnh ($4.8\text{ GHz}$ Synthesizer)
Mô hình Laplace ở trên giả thiết bơm điện tích bơm dòng liên tục, nhưng thực tế PFD chỉ cập nhật mẫu một lần mỗi chu kỳ $T_{\text{REF}} = 2\pi / \omega_{\text{REF}}$, tạo ra trễ lấy mẫu giữ mẫu hiệu dụng $\Delta\phi_{\text{discrete}}(\omega) \approx -\frac{\omega T_{\text{REF}}}{2}$ (hoặc phân tích chính xác trong miền $z$ của Floyd M. Gardner 1980). Tại $\omega_c = \frac{\omega_{\text{REF}}}{10}$, riêng trễ rời rạc đã ăn mòn mất $\frac{0.1 \times 360^\circ}{2} \approx 18^\circ$ (hoặc $\sim 6^\circ \sim 12^\circ$ tùy độ rộng xung)! Do đó quy tắc bất di bất dịch là **chọn $f_c \le \frac{f_{\text{REF}}}{15} \sim \frac{f_{\text{REF}}}{10}$**.

**Ví dụ Thiết kế Hoàn chỉnh từ Đầu tới Cuối**:
Tổng hợp bộ lọc vòng trên chip cho PLL tạo $f_{\text{out}} = 4.8\text{ GHz}$ từ thạch anh $f_{\text{REF}} = 40\text{ MHz}$ ($N = 120$), VCO có $K_{VCO,\text{Hz}} = 60\text{ MHz/V}$ ($K_{VCO} = 2\pi \times 60 \times 10^6 = 3.770 \times 10^8\,\text{rad/(s}\cdot\text{V)}$). Yêu cầu băng thông cắt $f_c = 500\text{ kHz}$ ($= f_{\text{REF}}/80$, $\omega_c = 3.1416 \times 10^6\text{ rad/s}$), dự trữ pha $\text{PM} = 60^\circ$, và chọn dòng bơm $I_P = 500\,\mu\text{A}$:
1. Với $\text{PM} = 60^\circ$: $\gamma_c = \tan 60^\circ + \sec 60^\circ = \sqrt{3} + 2 = \mathbf{3.732}$, tỉ số tụ $b = 3.732^2 - 1 = \mathbf{12.928}$.
2. Tụ lọc gợn $C_2$:
   $$C_2 = \frac{500 \times 10^{-6} \times 3.770 \times 10^8}{2\pi \times 120 \times (3.1416 \times 10^6)^2 \times 3.732} = \frac{1.885 \times 10^5}{2.777 \times 10^{16}} = \mathbf{6.79\text{ pF}}$$
3. Tụ tích phân chính $C_1$:
   $$C_1 = 12.928 \times 6.787\text{ pF} = \mathbf{87.8\text{ pF}}$$
4. Điện trở bù zero $R_P$:
   $$R_P = \frac{3.732}{3.1416 \times 10^6 \times 87.75 \times 10^{-12}} = \mathbf{13.54\text{ k}\Omega}$$
5. Kiểm tra vị trí các tần số gãy và thời gian khóa tinh:
   - $f_z = \frac{f_c}{3.732} = \mathbf{134.0\text{ kHz}}$; $f_{p3} = 3.732 \, f_c = \mathbf{1.866\text{ MHz}}$ (cách xa $f_{\text{REF}} = 40\text{ MHz}$ hơn $21\times$, nén mạnh hài $40\text{ MHz}$ thêm $26.6\text{ dB}$!).
   - Thời gian xác lập bám tần số tới sai số $10^{-6}$ ($\sim 14$ hằng số thời gian $\tau \approx \frac{2}{\omega_c}$): $t_{\text{settle}} \approx 14 \times \frac{2}{3.1416 \times 10^6} \approx \mathbf{8.9\,\mu\text{s}}$!
   - Nhiễu nhiệt riêng của $R_P = 13.54\text{ k}\Omega$ tại $f_c = 500\text{ kHz}$: $\sqrt{4 k T R_P} = 15.0\text{ nV}/\sqrt{\text{Hz}} \implies \mathcal{L}_{RP}(500\text{ kHz}) \approx \mathbf{-118.9\text{ dBc/Hz}}$ (nếu muốn hạ thêm $6\text{ dB}$ xuống $-124.9\text{ dBc/Hz}$, chỉ cần tăng $I_P = 2.0\text{ mA}$ để giảm $R_P = 3.38\text{ k}\Omega$!).

---

## 3. Bất biến Cấu trúc & Các Bẫy Lỗi Kinh điển (Structural Invariants & Traps)

- **[INV-LF-01] Bất biến Độ Nhạy Dự trữ Pha đối với Sự Trượt của Tích số $\eta = \frac{I_P K_{VCO}}{N R_P^{-1}}$ qua PVT**: Nhờ đặt $\omega_c$ đúng tại đỉnh cực đại $\sqrt{\omega_z \omega_{p3}}$, đạo hàm bậc nhất $\left.\frac{\partial\,\text{PM}}{\partial\omega_c}\right|_{\text{nom}} = 0$! Ngay cả khi tích $I_P K_{VCO} R_P$ trôi lệch $\pm 40\%$ qua các góc công nghệ `SS/FF` (làm $\omega_c$ dịch đi $\pm 40\%$), dự trữ pha của thiết kế $\text{PM}_{\text{nom}} = 60^\circ$ chỉ giảm nhẹ chưa tới **$2.5^\circ$** (vẫn đạt $> 57.5^\circ$)! Ngược lại, nếu thiết kế cẩu thả đặt $\omega_c$ nằm trên sườn dốc sát $\omega_z$ hoặc sát $\omega_{p3}$, biến thiên $40\%$ sẽ đánh tụt $\text{PM}$ xuống $< 35^\circ$ gây rung lắc dữ dội!
- **[INV-LF-02] Bất biến Cấm Phá Hủy Zero do Gắn Nhầm Bản Đáy Ký sinh hoặc Nút Trích Áp (Razavi Bài tập 16.10)**: Trên sơ đồ và trên layout của nhánh nối tiếp $R_P - C_1$:
  1. Dây điều khiển $V_{cont}$ đi vào VCO **bắt buộc trích từ đầu trên của tổ hợp $(R_P + C_1)$** (nơi đấu chung với bơm điện tích và $C_2$).
  2. Về mặt vật lý mặt cắt (`concept-integrated-resistors-and-capacitors-cmos`), tụ $C_1$ có diện tích cực lớn ($\sim 100\text{ pF}$) nên mang điện dung ký sinh bản đáy xuống đất rất lớn ($C_{p,\text{bot}} \approx 5\% \sim 15\%\,C_1 = 5 \sim 15\text{ pF}$, lớn hơn cả $C_2$!). **BẮT BUỘC đặt $C_1$ ở dưới nối đất (bản đáy nối GND, bản đỉnh nối vào $R_P$) và đặt $R_P$ ở phía trên nối vào $V_{cont}$**! Nếu đặt ngược $C_1$ ở trên còn $R_P$ ở dưới nối đất, tụ ký sinh bản đáy $C_{p,\text{bot}} = 10\text{ pF}$ sẽ cộng thẳng vào $C_2 = 7.5\text{ pF}$, nhân đôi $C_2$ ngoài ý muốn và ăn cụt $15^\circ$ dự trữ pha!
- **[TRAP-LF-01] Bẫy Chồng Chấp Jitter Peaking trong Hệ thống Nối tầng Nhiều PLL (`Jitter Peaking Accumulation`)**: Trong bất kỳ CP-PLL Loại II nào, vì zero $\omega_z$ nằm trực tiếp trên tử số của hàm truyền đóng vòng $H(s) = N \frac{1 + s/\omega_z}{1 + s/\omega_z + \dots}$, biên độ $|H(j\omega)| / N$ luôn nhô cao hơn $0\text{ dB}$ trước khi lăn xuống ($\sim 1.70\text{ dB}$ ở $\text{PM} = 60^\circ$). Trong mạng viễn thông quang (SONET / OTN) hoặc cây xung nhịp PCIe nơi $10 \sim 20$ bộ khôi phục xung nhịp nối đuôi nhau, độ nhô $1.7\text{ dB}$ mỗi chặng sẽ nhân lên thành **+$34\text{ dB}$ khuếch đại nhiễu** làm sập mắt tín hiệu! Giải pháp cho ứng dụng nối tầng: phải đẩy tỉ số $b = C_1 / C_2 \ge 50 \sim 100$ ($\text{PM} > 78^\circ$, quá tắt dần $\zeta > 2$) hoặc tách đường điều khiển VCO làm hai cổng (Proportional-Integral Split-Path PLL để chuyển zero ra khỏi tử số của $H(s)$!).
- **[TRAP-LF-02] Bẫy Quên Cộng Điện dung Ngõ vào của VCO và Bộ Đệm Vào $C_2$**: Khi $C_2$ thiết kế nhỏ (ví dụ $2 \sim 5\text{ pF}$), điện dung bản thân của varactor VCO + dây dẫn che chắn + cổng Op-Amp bootstrap của bơm điện tích (thường $0.8 \sim 2.0\text{ pF}$) mắc song song trực tiếp với $C_2$! Phải trừ toàn bộ lượng điện dung ký sinh trên nút $V_{cont}$ ra khỏi giá trị $C_{2,\text{drawn}}$ vẽ trên layout: $C_{2,\text{drawn}} = C_{2,\text{target}} - C_{\text{par,Vcont}}$.

---

## 4. Lộ trình Nâng cấp Cấu trúc & Bát giác Đánh đổi (Upgrade Paths & Design Octagon)

Trong `concept-analog-design-octagon`, tổng hợp bộ lọc vòng điều phối trực tiếp sự đánh đổi giữa **Diện tích Tụ điện trên Chip ($C_1$)**, **Thời gian Khóa Kênh ($t_{\text{lock}} \propto 1/\omega_c$)**, **Tổng Jitter Tích phân**, và **Mức Lọc Spur Ngoại dải**:

- **Nền tảng kết nối từ**: Nhận thông số dòng bơm và nhiễu từ `topo-pfd-deadzone-and-charge-pump-nonidealities`, kiến trúc hạt nhân từ `topo-charge-pump-type2-pll`, tiêu chuẩn ổn định đa cực từ `law-multipole-phase-margin`, và độ nhạy $K_{VCO}$ từ `topo-quadrature-vco-and-varactor-tuning`.
- **Lộ trình nâng cấp khi chạm rào cản vật lý**:
  1. **Khi băng thông vòng yêu cầu quá hẹp ($f_c < 50\text{ kHz}$ để lọc sạch tham chiếu ồn) khiến $C_1$ phình lên hàng $\text{nF}$ không thể tích hợp lên chip**: Nâng cấp sang **Bộ lọc Vòng Nhân Điện dung Chủ động / Tích cực Hai Đường (`Dual-Path / Capacitance-Multiplier Loop Filter`)** — dùng dòng bơm phụ nhỏ bằng $I_P / K$ nạp vào tụ $C_1 / K$ kết hợp cộng áp trên nhánh tỷ lệ $I_P R_P$, thu nhỏ diện tích tụ $C_1$ đi $10 \sim 20$ lần mà không tăng nhiễu nhiệt của $R_P$!
  2. **Khi bộ điều chế $\Delta\Sigma$ bậc 3 trong `topo-frequency-synthesizer-integer-fractional-n` đẩy nhiễu lượng tử dốc $+40\text{ dB/dec}$ ở tần số cao mà vòng bậc ba chỉ dốc $-40\text{ dB/dec}$ (chỉ san phẳng chứ chưa dập tắt!)**: Nâng cấp lên **Bộ lọc Vòng Bậc Bốn (thêm mắt lọc $R_3 - C_3$ sau $C_2$)** để tổng hàm truyền vòng kín rơi dốc **$-60\text{ dB/dec}$** ở ngoại dải, đè bẹp hoàn toàn nhiễu lượng tử hóa $\Delta\Sigma$ (lưu ý tính bù hao hụt pha $\Delta\text{PM}_4 = \arctan(\omega_c / \omega_{p4}) \approx 7^\circ$ bằng cách khởi tạo phần bậc ba ở $\text{PM}_3 = 67^\circ$ để sau khi trừ $7^\circ$ vẫn còn trọn vẹn $\text{PM}_{\text{tot}} = 60^\circ$!).

---

## 5. Thích ứng Đa Tiến trình (90nm / 65nm / 45nm) & Cách Kiểm chứng trong Cadence / Spectre

### 5.1. Cơ chế Tự Bù Biến thiên PVT cho Băng thông Vòng (`Constant-Bandwidth Calibration`)
Ở các tiến trình `90nm`, `65nm`, `45nm`, điện trở poly không phủ silicide $R_P$ biến thiên $\pm 20\%$ theo góc quy trình, tụ MIM/MOM biến thiên $\pm 15\%$, và $K_{VCO}$ biến thiên tới $\pm 35\%$ theo mã dàn tụ (vì $K_{VCO} \propto f_0^3$!). Nhìn vào phương trình tần số cắt $\omega_c \approx \frac{I_P R_P K_{VCO}}{2\pi N} \frac{b}{b+1}$:
- Nếu tạo dòng tham chiếu cho bơm điện tích từ mạch **Constant-$G_m$ / Bandgap trên cùng loại điện trở đơn vị với $R_P$** (`topo-constant-gm-bias-and-supply-sensitivity`), dòng bơm sẽ tự nhiên thỏa mãn $I_P = \frac{V_{\text{BG}}}{R_{\text{ref}}} \implies$ tích số **$I_P \cdot R_P = V_{\text{BG}} \frac{R_P}{R_{\text{ref}}}$ trở thành hằng số hình học bất biến hoàn toàn trước sai số $\pm 20\%$ và hệ số nhiệt của điện trở tấm**!
- Tiếp đó, lập trình một DAC dòng điện 4–5 bit cho bơm điện tích theo công thức $I_P(\text{band}, N) \propto \frac{N}{\hat{K}_{VCO}(\text{band})}$ giúp khóa cứng cả $\omega_c$ lẫn $\text{PM}$ phẳng tuyệt đối từ kênh tần số thấp nhất đến kênh cao nhất!

### 5.2. Script Python / Spectre Tự động Tổng hợp và Kiểm chứng Bậc 3 / Bậc 4 Chuẩn Xác
```python
# Script Python 3 chuan (khong phu thuoc thu vien ngoai, PYTHONDONTWRITEBYTECODE=1 python -B)
# Tinh chinh xac linh kien Bo loc Vong Bac 3 & Bac 4 (co bu pha R3-C3) va kiem nghiem Bode:
import math

def synthesize_cp_pll_loop_filter(f_ref, N, kvco_hz_per_v, ip_amp, fc_hz, pm_target_deg, p4_ratio=None):
    assert fc_hz <= f_ref / 10.0, "Vi pham gioi han on dinh roi rac Gardner: fc phai <= f_ref / 10!"
    wc = 2.0 * math.pi * fc_hz
    kvco_rad = 2.0 * math.pi * kvco_hz_per_v
    # Neu co mat loc bac 4 tai wp4 = p4_ratio * wc, cong bu truoc goc suy hao arctan(1/p4_ratio)
    extra_deg = math.degrees(math.atan(1.0 / p4_ratio)) if p4_ratio else 0.0
    pm3_rad = math.radians(pm_target_deg + extra_deg)
    gamma_c = math.tan(pm3_rad) + (1.0 / math.cos(pm3_rad))
    b = gamma_c * gamma_c - 1.0
    c2 = (ip_amp * kvco_rad) / (2.0 * math.pi * N * wc * wc * gamma_c)
    c1 = b * c2
    rp = gamma_c / (wc * c1)
    out = {"C1_pF": c1 * 1e12, "C2_pF": c2 * 1e12, "RP_kOhm": rp * 1e-3, "b_ratio": b,
           "fz_kHz": (fc_hz / gamma_c) * 1e-3, "fp3_MHz": (fc_hz * gamma_c) * 1e-6}
    if p4_ratio:
        c3 = c2 / 5.0
        r3 = 1.0 / (p4_ratio * wc * c3)
        out.update({"R3_kOhm": r3 * 1e-3, "C3_pF": c3 * 1e12, "fp4_MHz": p4_ratio * fc_hz * 1e-6})
    return out
```

Trong Cadence Virtuoso, trước khi chạy mô phỏng quá độ hàng chục microgiây tốn thời gian, hãy dựng một **mạch tương đương miền pha tuyến tính (`AC Phase-Domain Testbench`)** trong 30 giây: dùng nguồn dòng điều khiển bằng áp `vccs` ($G = \frac{I_P}{2\pi}$) lái mạng thực tế `RP, C1, C2, R3, C3` (dùng đúng model PDK có ký sinh bản đáy!), nối vào bộ tích phân lý tưởng `svcvs` ($\frac{K_{VCO}}{s}$) rồi chia $1/N$ qua `iprobe` chạy phân tích Spectre `stb` qua toàn bộ 5 góc quy trình + nhiệt độ để đóng dấu xác nhận `Phase Margin >= 55 deg`, `Gain Margin >= 12 dB`, và `Jitter Peaking <= Spec`!

---

## 6. Mốc Đối chiếu Sách Razavi & Thuật ngữ Chuẩn CLB

- **Sách gốc Razavi (2nd Ed.)**: Chương 16, Mục `16.2.4` (*Basic Charge-Pump PLL*, trang 671–677, Hình `16.30`–`16.38`, Ví dụ `16.10`–`16.11`, Phương trình `16.37`–`16.47`) và Mục `16.5.1` (*Frequency Multiplication and Synthesis*, trang 685–687, Hình `16.55`–`16.56`, Phương trình `16.49`–`16.54`, Bài tập `16.10`–`16.11`, `16.14`–`16.16`).
- **Đối chiếu Thuật ngữ Chuẩn CLB Vi Mạch (`terms-vi-en.json`)**:
  - `T2174` (`type-II charge-pump PLL`): **vòng khóa pha bơm điện tích loại II**; `T2175` (`loop filter`): **bộ lọc vòng**.
  - `T1805` (`Two Poles at Origin`): **hai cực tại gốc tọa độ**; `T1678` (`left-half-plane zero`): **zero ở nửa mặt phẳng trái**; `T1642` (`three-pole system`): **hệ thống ba cực**.
  - `T063` (`phase margin`): **dự trữ pha**; `T1684` (`phase margin of 60°`): **dự trữ pha $60^\circ$**; `T1614` (`gain crossover frequency`): **tần số cắt độ lợi**.
  - `T2176` (`damping factor, zeta`): **hệ số tắt dần**; `T1575` (`frequency compensation`): **bù tần số**.
