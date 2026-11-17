---
{
  "id": "topo-type1-simple-pll",
  "kind": "topology",
  "domain": "sampled-and-clocked",
  "title_vi": "Vòng khóa pha Loại I cơ bản dùng Bộ tách pha XOR / Nhân tương tự (Simple Type-I PLL)",
  "title_en": "Simple Type-I Phase-Locked Loop (XOR / Multiplier PD + RC LPF + VCO)",
  "summary": "Kiến trúc vòng khóa pha Loại I bậc hai gồm bộ tách pha XOR/nhân tương tự KD, bộ lọc thông thấp RC một cực và VCO tích phân pha KVCO/s: chứng minh điều kiện khóa đồng bộ tần số tuyệt đối w_out = w_in, sai số pha tĩnh Delta_phi = (w_in - w0)/(KD*KVCO), hàm truyền bậc hai (wn, zeta) và thế tiến thoái lưỡng nan khiến Type-I bế tắc giữa nén gợn sóng 2*w_in, độ ổn định và dải bắt khóa.",
  "diagram": "../../diagrams/charge-pump-type2-pll.svg",
  "razavi_refs": [
    {
      "chapter": 16,
      "section": "16.1.1",
      "pages": "651-653",
      "equations": []
    },
    {
      "chapter": 16,
      "section": "16.1.2",
      "pages": "653-660",
      "equations": ["16.1", "16.2", "16.3", "16.4", "16.5", "16.8", "16.9", "16.10"]
    },
    {
      "chapter": 16,
      "section": "16.1.3",
      "pages": "660-665",
      "equations": ["16.11", "16.12", "16.13", "16.14", "16.15", "16.16", "16.17", "16.18", "16.20", "16.22", "16.23", "16.30", "16.31", "16.36"]
    },
    {
      "chapter": 16,
      "section": "16.2.1",
      "pages": "666",
      "equations": []
    }
  ],
  "glossary_codes": [
    "T019",
    "T033",
    "T042",
    "T051",
    "T063",
    "T064",
    "T069",
    "T090",
    "T535",
    "T818",
    "T838",
    "T854",
    "T1389",
    "T1635",
    "T1650",
    "T1653",
    "T1801",
    "T1802",
    "T2028",
    "T2079"
  ],
  "process_agnostic": true,
  "roles": {
    "phase_detector_pd": "Cổng XOR hoặc bộ nhân tương tự Gilbert chuyển đổi độ lệch pha đầu vào - đầu ra thành điện áp trung bình tỉ lệ KPD*Delta_phi kèm hài bậc hai 2*w_in.",
    "first_order_rc_lpf": "Bộ lọc thông thấp RC hàm truyền 1/(1 + s/w_LPF) triệt gợn sóng tần số cao từ PD để giữ yên điện áp điều khiển Vcont ở xác lập.",
    "vco_phase_integrator": "Bộ tạo dao động điều khiển áp chuyển hóa Vcont thành pha dư qua cực tích phân lý tưởng tại gốc tọa độ KVCO/s.",
    "phase_feedback_path": "Đường hồi tiếp pha trực tiếp (hoặc qua bộ chia) ép đạo hàm sai số pha bằng không ở trạng thái khóa, bảo đảm w_out = w_in tuyệt đối."
  },
  "symptoms_addressed": [
    "clock-data-phase-drift-under-open-loop-or-pure-frequency-lock",
    "clock-skew-alignment-via-temporary-vco-frequency-excursion",
    "high-frequency-input-jitter-filtering-via-second-order-phase-loop"
  ],
  "limitations": [
    "nonzero-frequency-dependent-static-phase-error",
    "severe-tradeoff-between-2f-ripple-suppression-and-damping-factor-zeta",
    "tiny-frequency-capture-and-acquisition-range-on-order-of-w-lpf",
    "periodic-xor-pd-characteristic-losing-gain-beyond-pi-over-two"
  ],
  "checklists": [
    "common-mos",
    "oscillator-and-pll",
    "feedback-and-stb"
  ]
}
---

## 1. Bản chất Nguyên lý, Sơ đồ Mạch & Vai trò Từng Nhánh Cấu trúc

Vì sao các hệ thống đồng bộ không chỉ khóa tần số bằng một bộ dò tần số (Frequency Detector — FD) mà bắt buộc phải dùng **vòng khóa pha** (Phase-Locked Loop — PLL, Chương 16)? Razavi chỉ rõ bản chất vật lý trong §16.1.2 (Hình 16.9–16.10): nếu một vòng hồi tiếp chỉ so sánh tần số $\omega_{in}$ và $\omega_{out}$, mọi sai lệch linh kiện hoặc điện áp lệch (offset) không tránh khỏi trong bộ dò tần số sẽ để lại một sai số tần số tĩnh nhỏ $\Delta\omega = \omega_{out} - \omega_{in} \neq 0$. Khi tích phân theo thời gian, sai số tần số nhỏ này tích lũy thành độ trôi pha tăng tuyến tính vô hạn $\Delta\phi(t) = \Delta\omega \cdot t \to \infty$, làm xung nhịp lấy mẫu trượt qua ranh giới bit dữ liệu và gây lỗi bit tuần hoàn! Ngược lại, khi vòng hồi tiếp trực tiếp khóa độ lệch pha ở một hằng số hữu hạn không đổi theo thời gian ($\phi_{out}(t) - \phi_{in}(t) = \phi_0 = \text{hằng số}$), phép lấy đạo hàm hai vế lập tức khóa chặt sự bằng nhau **tuyệt đối** về tần số (PT 16.1–16.2):

$$\frac{d\phi_{out}}{dt} - \frac{d\phi_{in}}{dt} = 0 \implies \omega_{out} = \omega_{in} \quad (\text{chính xác tuyệt đối đến } 0\text{ ppm sai số tĩnh!})$$

Hơn nữa, để dịch pha ngõ ra VCO khớp lại với xung nhịp chuẩn đang bị lệch thời gian $\Delta t$ (Hình 16.4), hệ thống bắt buộc phải thay đổi tạm thời **tần số** VCO trong khoảng $[t_1, t_2]$ để tích lũy diện tích pha bù $\Delta\phi = \int_{t_1}^{t_2} \Delta\omega_{out}\,dt$, rồi trả tần số VCO về đúng $\omega_{in}$ khi pha đã gióng hàng.

![Sơ đồ kiến trúc vòng khóa pha đối chiếu từ cấu trúc cơ bản sang bơm điện tích Loại II](../../diagrams/charge-pump-type2-pll.svg)

Kiến trúc **PLL Loại I cơ bản (Simple Type-I PLL, Hình 16.5b–16.6)** ghép nối tiếp ba khối chức năng trong miền pha:
1. **Bộ tách pha (Phase Detector — PD, §16.1.1)**: Điển hình là cổng logic **XOR** (cho tín hiệu vuông, Hình 16.2–16.3) hoặc **bộ nhân tương tự tế bào Gilbert** (cho tín hiệu sin nhỏ, Bài tập 16.1). Khi hai xung vuông cùng tần số lệch pha $\Delta\phi$, cổng XOR xuất ra **hai xung lỗi trong mỗi chu kỳ** (tại cả sườn lên lẫn sườn xuống), tức thành phần gợn sóng xoay chiều có tần số cơ bản gấp đôi tần số ngõ vào ($2\omega_{in}$)! Giá trị trung bình một chiều của ngõ ra XOR biến thiên tuần hoàn dạng sóng tam giác theo $\Delta\phi$: với biên độ logic từ $0$ đến $V_0$, mức trung bình tăng tuyến tính từ $0$ (tại $\Delta\phi = 0$) qua điểm giữa danh định $V_0/2$ (tại khóa vuông góc $\Delta\phi = \pi/2$) lên $V_0$ (tại $\Delta\phi = \pi$) với độ lợi tách pha $K_{PD} = V_0 / \pi$ ($\text{V/rad}$), rồi đổi sang sườn âm trên $[\pi, 2\pi]$.
2. **Bộ lọc thông thấp bậc một (Low-Pass Filter — LPF)**: Một mắt lọc $R_{LPF} C_{LPF}$ thụ động có hàm truyền $G_{LPF}(s) = \frac{1}{1 + s/\omega_{LPF}}$ với $\omega_{LPF} = \frac{1}{R_{LPF} C_{LPF}}$. Nếu nối thẳng PD vào VCO mà bỏ LPF (Hình 16.5a), chuỗi xung $2\omega_{in}$ từ PD sẽ điều chế mạnh đường $V_{cont}$, phá nát tính tuần hoàn của VCO bằng các vạch phổ biên khổng lồ tại $\omega_{in} \pm 2\omega_{in}$!
3. **Mạch dao động điều khiển áp (VCO)**: Đóng vai trò bộ tích phân từ điện áp điều khiển sang pha dư với hàm truyền $\frac{\Phi_{out}(s)}{V_{cont}(s)} = \frac{K_{VCO}}{s}$. Vì toàn bộ hàm truyền vòng hở chỉ chứa **đúng một cực tại gốc tọa độ $s = 0$** (do riêng VCO đóng góp, còn PD + LPF có độ lợi DC hữu hạn), hệ thống này được định danh chính tắc là **PLL Loại I (Type-I PLL)** có bậc động học vòng kín bằng **bậc 2 (second-order)**.

| Đại lượng nút quanh vòng | Trạng thái sau Bước nhảy Pha đầu vào $\phi_1 u(t)$ | Trạng thái sau Bước nhảy Tần số đầu vào $\Delta\omega\,u(t)$ |
| :--- | :--- | :--- |
| **Tần số ngõ ra $\omega_{out}(\infty)$** | Quay về đúng giá trị cũ $\omega_1$ | Dịch chuyển vĩnh viễn lên giá trị mới $\omega_1 + \Delta\omega$ |
| **Điện áp điều khiển $V_{cont}(\infty)$** | Quay về đúng mức DC cũ $(\omega_1 - \omega_0)/K_{VCO}$ | Tăng vĩnh viễn thêm một lượng $\Delta\omega / K_{VCO}$ |
| **Sai số pha tĩnh $\Delta\phi(\infty)$** | Quay về đúng sai số cũ $\phi_0$ (nhờ cực $1/s$ của VCO!) | Tăng vĩnh viễn thêm một lượng $\Delta\omega / (K_{PD} K_{VCO})$ |

## 2. Hệ Phương trình Cốt lõi & Tư duy "Nhìn Mạch Đọc Nhanh" (Analysis by Inspection)

### 2.1. Trạng thái Khóa Tĩnh & Sai số Pha Tĩnh (Static Phase Error)
Quy chiếu quanh điểm làm việc trung tâm $\omega_0$ của VCO (ví dụ đặt $\omega_0$ là tần số VCO tại mức trung bình danh định $V_0 / 2$ ứng với độ lệch pha vuông góc $\pi/2$ của cổng XOR, hoặc điểm cắt $0\text{ V}$ của PD đối xứng lưỡng cực $\pm V_0/2$), để VCO chạy ở tần số khóa $\omega_{out} = \omega_{in} = \omega_1$, đường điều khiển bắt buộc phải nhận điện áp một chiều duy nhất $V_1$ từ bộ tách pha (PT 16.3–16.5):

$$V_{cont,\text{DC}} = \frac{\omega_1 - \omega_0}{K_{VCO}}, \qquad \phi_0 = \frac{V_{cont,\text{DC}}}{K_{PD}} = \frac{\omega_1 - \omega_0}{K_{PD} K_{VCO}}$$

(Với cổng XOR đơn cực $[0, V_0]$ có $\omega_{out} = \omega_{0,\text{free}} + K_{VCO} V_{cont}$, độ lệch pha tuyệt đối giữa hai ngõ vào là $\Delta\phi_{\text{XOR}} = \frac{\omega_1 - \omega_{0,\text{free}}}{K_{PD} K_{VCO}}$, luôn co về gần $90^\circ$ tức $\pi/2$ khi tích $K_{PD} K_{VCO}$ lớn và tâm dải VCO đặt tại $V_0 / 2$ — Bài tập 16.4!). Phương trình này phơi bày nhược điểm tĩnh đầu tiên của Type-I: **sai số pha tĩnh khác không và thay đổi trực tiếp theo tần số làm việc $\omega_1$ cũng như trôi $\omega_0$ theo nhiệt độ**! Nếu $|\omega_1 - \omega_0|$ lớn tới mức đẩy $\Delta\phi$ chạm đỉnh đặc tuyến PD (nơi độ dốc $K_{PD} \to 0$, Ví dụ 16.3), vòng hồi tiếp đứt gãy và tuột khóa hoàn toàn (giới hạn dải giữ khóa tĩnh $\Delta\omega_{\text{lock}} \le V_{PD,\max} K_{VCO}$).

### 2.2. Hàm truyền Tuyến tính Miền Pha Dư, Tần số Tự nhiên $\omega_n$ & Hệ số Tắt dần $\zeta$
Trong miền pha dư quanh trạng thái khóa (Hình 16.16), hàm truyền vòng hở (loop gain $L(s)$ với hệ số hồi tiếp bằng $1$) và hàm truyền vòng kín $H(s)$ có dạng chuẩn bậc hai (PT 16.12–16.18):

$$H_{\text{open}}(s) = K_{PD} \cdot \frac{1}{1 + \dfrac{s}{\omega_{LPF}}} \cdot \frac{K_{VCO}}{s}, \qquad H(s) = \frac{\Phi_{out}(s)}{\Phi_{in}(s)} = \frac{\omega_{out}(s)}{\omega_{in}(s)} = \frac{K_{PD} K_{VCO}}{\dfrac{s^2}{\omega_{LPF}} + s + K_{PD} K_{VCO}} = \frac{\omega_n^2}{s^2 + 2\zeta\omega_n s + \omega_n^2}$$

Đồng nhất mẫu số với đa thức đặc trưng bậc hai chuẩn thu được bộ ba phương trình vàng của PLL Loại I:

$$\omega_n = \sqrt{\omega_{LPF} K_{PD} K_{VCO}}, \qquad \zeta = \frac{1}{2}\sqrt{\frac{\omega_{LPF}}{K_{PD} K_{VCO}}}, \qquad \zeta\omega_n = \frac{1}{2}\omega_{LPF}$$

Hàm truyền sai số pha $H_e(s) = \frac{\Phi_e(s)}{\Phi_{in}(s)} = 1 - H(s) = \frac{s^2 + 2\zeta\omega_n s}{s^2 + 2\zeta\omega_n s + \omega_n^2}$ (PT 16.31) kiểm chứng tức thì qua định lý giá trị cuối: với bước nhảy tần số $\Phi_{in}(s) = \Delta\omega / s^2$, sai số pha xác lập là $\lim_{s\to 0} s H_e(s)\frac{\Delta\omega}{s^2} = \frac{2\zeta}{\omega_n}\Delta\omega = \frac{\Delta\omega}{K_{PD} K_{VCO}}$!

*Phản xạ nhìn mạch đọc nhanh trên mặt phẳng phức & nút đo thực nghiệm*:
- **Quỹ đạo nghiệm số (Root Locus, Hình 16.20)**: Khi tăng $K_{PD} K_{VCO}$ từ $0$ lên, hai cực vòng kín bắt đầu tại $0$ và $-\omega_{LPF}$ chạy chụm vào nhau tại $-\omega_{LPF}/2$ (khi $K_{PD} K_{VCO} = \omega_{LPF}/4 \implies \zeta = 1$), sau đó tách thành hai nhánh phức đi thẳng đứng song song trục ảo $j\omega$ với phần thực cố định $\sigma = -\zeta\omega_n = -\omega_{LPF}/2$!
- **Điểm đo vàng $V_{cont}(t)$ (PT 16.15)**: Vì khó đo trực tiếp pha tức thời trên dao động ký, phương trình $V_{cont}(s)/\omega_{in}(s) = H(s)/K_{VCO}$ cho phép quan sát trực tiếp hệ số tắt dần $\zeta$, dao động rung (ringing) và thời gian xác lập $t_s \propto 1/(\zeta\omega_n) = 2/\omega_{LPF}$ ngay trên dạng sóng điện áp $V_{cont}(t)$!

### 2.3. Ví dụ Định lượng Thực chiến (Theo Ví dụ Razavi 16.5 & Bài tập 16.9)
Xét một PLL Loại I dùng bộ tách pha XOR có $K_{PD} = 1\text{ V/rad}$, VCO có $K_{VCO} = 2\pi \times (100\text{ MHz/V})$ và bộ lọc RC thông thấp có tần số góc cắt $\omega_{LPF} = 2\pi \times (1\text{ MHz})$:
1. **Tính tần số tự nhiên $\omega_n$ và hệ số tắt dần $\zeta$**:
   - $\omega_n = \sqrt{\omega_{LPF} K_{PD} K_{VCO}} = 2\pi\sqrt{1\text{ MHz} \times 100\text{ MHz}} = 2\pi \times 10\text{ MHz}$.
   - $\zeta = \frac{1}{2}\sqrt{\frac{\omega_{LPF}}{K_{PD} K_{VCO}}} = \frac{1}{2}\sqrt{\frac{1\text{ MHz}}{100\text{ MHz}}} = 0.05 \ll \frac{\sqrt{2}}{2}$!
   - *Chẩn đoán tức thì*: Hệ thống rơi vào vùng **thiếu tắt dần trầm trọng** ($\zeta = 0.05$), đáp ứng bậc thang tần số lắc lư dữ dội ở tần số rung $\omega_n\sqrt{1 - \zeta^2} \approx 2\pi \times 9.99\text{ MHz}$ với bao hình tắt chậm theo $\tau = (\zeta\omega_n)^{-1} = \frac{2}{\omega_{LPF}} \approx 0.318\,\mu\text{s}$!
2. **Thử hạ $\omega_{LPF}$ xuống $2\pi \times 20\text{ kHz}$ để lọc sạch gợn sóng (như Ví dụ 16.5 cho bước nhảy kênh $200\text{ kHz}$ cần hội tụ trong sai số $100\text{ Hz}$)**:
   - Thời gian xác lập kéo dài tới $t_s = \frac{\ln(200\text{ kHz}/100\text{ Hz})}{\zeta\omega_n} = \frac{7.6}{\omega_{LPF}/2} = \frac{15.2}{2\pi \times 20\text{ kHz}} \approx 0.12\text{ ms}$.
   - Đồng thời, nếu vẫn giữ $K_{PD} K_{VCO} = 2\pi \times 100\text{ MHz/rad}$, hệ số tắt dần sụp xuống mức thảm họa $\zeta = \frac{1}{2}\sqrt{\frac{20\text{ kHz}}{100\text{ MHz}}} \approx 0.007$! Muốn kéo $\zeta$ lên mức ổn định $\zeta = 1$, bắt buộc phải cắt giảm $K_{PD} K_{VCO}$ xuống chỉ còn $\frac{\omega_{LPF}}{4} = 2\pi \times 5\text{ kHz/rad}$ — khiến dải giữ khóa tĩnh co rúm xuống vỏn vẹn vài kHz! Con số này chứng minh trực quan sự bế tắc không lối thoát của kiến trúc Loại I.

## 3. Bất biến Cấu trúc & Các Bẫy Lỗi Kinh điển (Structural Invariants & Traps)

- **[INV-PLL1-01] Thế tiến thoái lưỡng nan Bốn chiều của PLL Loại I (The Four-Way Type-I Dilemma)**: Nhìn vào ba biểu thức $\phi_0 = \frac{\Delta\omega}{K_{PD} K_{VCO}}$, $\zeta = \frac{1}{2}\sqrt{\frac{\omega_{LPF}}{K_{PD} K_{VCO}}}$ và $\tau_{\text{settle}} = \frac{2}{\omega_{LPF}}$, mọi nỗ lực cải thiện một chỉ tiêu đều phá hủy các chỉ tiêu còn lại:
  1. Muốn **nén mạnh gợn sóng $2\omega_{in}$** trên $V_{cont}$ (giảm vạch phổ biên ở ngõ ra VCO) $\implies$ phải ép **$\omega_{LPF}$ thật nhỏ** $\implies$ làm **$\zeta$ sụt thảm hại** (dao động rung dữ dội, mất dự trữ pha), **kéo dài thời gian xác lập** $2/\omega_{LPF}$, và **bóp nghẹt dải bắt khóa**!
  2. Muốn **giảm sai số pha tĩnh $\phi_0$** $\implies$ phải tăng **$K_{PD} K_{VCO}$ thật lớn** $\implies$ đẩy tần số cắt độ lợi vượt xa $\omega_{LPF}$ trên đồ thị Bode (Hình 16.19) và một lần nữa **đánh sập hệ số tắt dần $\zeta \propto 1/\sqrt{K_{PD} K_{VCO}}$**!
- **[INV-PLL1-02] Bất biến dải bắt khóa hẹp ($\Delta\omega_{\text{acq}} \sim \omega_{LPF}$, §16.2.1)**: Khi mới bật nguồn mà $|\omega_{in} - \omega_{out}| \gg \omega_{LPF}$, ngõ ra bộ nhân/XOR tạo tần số phách $\omega_{\text{beat}} = |\omega_{in} - \omega_{out}|$ bị chính bộ lọc thông thấp $\omega_{LPF}$ chặn mất trước khi kịp kéo VCO lại gần — nên dải tự bắt khóa (acquisition / capture range) của Type-I chỉ xấp xỉ cỡ $\omega_{LPF}$, quá nhỏ so với độ trôi PVT của VCO tích hợp!
- **[TRAP-PLL1-01] Bẫy nhầm cực tính vòng ở XOR PD là "bắt buộc một chiều" vs bão hòa biên (Bài tập 16.5)**: Do đặc tuyến trung bình của cổng XOR có dạng tam giác đối xứng gồm cả sườn dương trên $(0, \pi)$ lẫn sườn âm trên $(\pi, 2\pi)$, nếu đảo cực tính vòng, PLL dùng XOR không bị đẩy văng ra vô cực mà tự động trượt sang khóa ổn định ở sườn bên kia (lệch pha $180^\circ$ so với điểm khóa cũ), miễn là tần số nằm trong dải giữ!
- **[TRAP-PLL1-02] Bẫy chu kỳ nhiệm vụ khác $50\%$ (Duty-Cycle Asymmetry) trên cổng XOR**: Đặc tuyến tam giác đạt đỉnh trọn vẹn tại $\Delta\phi = \pi$ của cổng XOR chỉ đúng khi cả xung đầu vào lẫn xung VCO đều có chu kỳ nhiệm vụ đúng $50\%$; nếu xung bị lệch duty cycle, đỉnh đặc tuyến bị cắt cụt phẳng đầu (flat-top clipping), thu hẹp vùng tuyến tính và làm giảm dải khóa thực tế.
- **[TRAP-PLL1-03] Bẫy nhầm "tần số đã bằng nhau nghĩa là vòng đã xác lập" (Hình 16.13)**: Trong quá trình quá độ thiếu tắt dần ($\zeta < 1$), tại các thời điểm $V_{cont}(t)$ cắt ngang giá trị xác lập cuối cùng, tần số $\omega_{out}(t)$ tức thời đúng bằng $\omega_{in}$, nhưng sai số pha $\Delta\phi(t)$ lúc đó vẫn đang lệch nên vòng chưa thể dừng lại mà tiếp tục vọt lố! Phải hội tụ đồng thời cả tần số lẫn pha thì quá độ mới chấm dứt.

## 4. Lộ trình Nâng cấp Cấu trúc & Bát giác Đánh đổi (Upgrade Paths & Design Octagon)

Trong bức tranh tổng thể `concept-analog-design-octagon`, `topo-type1-simple-pll` có cấu trúc mạch cực kỳ đơn giản, không có cực gốc tọa độ thứ hai nên **không bao giờ tự dao động mất ổn định tuyệt đối ở bậc hai lý tưởng** ($\zeta > 0$ với mọi thông số hữu hạn; không bị nhô đỉnh hàm truyền đóng vòng như Type-II vì tử số $H(s)$ không chứa zero!), rất hữu ích ở tần số siêu cao sóng milimet (nơi bộ tách pha tuần tự PFD không kịp lật trạng thái) hoặc khôi phục xung nhịp đơn giản. Tuy nhiên, đối với tổng hợp tần số và tạo xung nhịp vi mạch VLSI đa dụng, sự trói buộc cứng nhắc giữa $\omega_{LPF}$, $\zeta$, $\phi_0$ và dải bắt khóa khiến nó thất thế hoàn toàn:

- **Nâng cấp đột phá giải phóng cả dải bắt khóa lẫn sai số pha tĩnh**: Thay thế bộ tách pha XOR + lọc RC bằng bộ tách pha/tần số ba trạng thái (PFD) kết hợp bơm điện tích (Charge Pump) và mắt lọc $R_P - C_1 - C_2$ tại `topo-charge-pump-type2-pll` — mở rộng dải bắt khóa phủ trọn dải điều chỉnh VCO và ép sai số pha tĩnh về $0$ tuyệt đối!
- **Lựa chọn lõi VCO phù hợp bên trong vòng**: Kết nối với VCO vòng hoặc LC-VCO đã tối ưu $K_{VCO}$ tại `topo-vco-tuning-and-phase-noise` (dựa trên nền tảng `topo-ring-oscillator` hoặc `topo-lc-cross-coupled-and-colpitts`).
- **Kiểm soát nhiễu pha, vạch phổ biên và lựa chọn kiến trúc vòng khóa trễ (DLL)**: Áp dụng quy luật lọc thông thấp nhiễu đầu vào $H(s)$ đối ngẫu với lọc thông cao nhiễu VCO $1 - H(s)$ (hoặc chuyển sang vòng khóa trễ DLL bậc một khi không cần nhân tần số) tại `concept-pll-nonidealities-spurs-jitter`, kết hợp ổn định pha đa cực từ `law-multipole-phase-margin` và nguồn sạch `topo-cmos-ldo-regulator`.

| Thông số Đánh giá | PLL Loại I (XOR / Multiplier + RC LPF) | Ý nghĩa Thiết kế & Hạn chế Vật lý |
| :--- | :--- | :--- |
| **Số cực gốc tọa độ ($s = 0$)** | $1$ cực duy nhất (từ bản thân VCO $K_{VCO}/s$) | Độ lợi vòng tiến tới $\infty$ cho bước nhảy pha, nhưng chỉ hữu hạn cho bước nhảy tần số! |
| **Sai số pha tĩnh $\phi_0$** | $\Delta\omega / (K_{PD} K_{VCO}) \neq 0$ (quanh điểm cân bằng $\pi/2$) | Trôi theo tần số kênh và trôi theo nhiệt độ/góc công nghệ của $\omega_0$. |
| **Tần số gợn sóng chủ đạo** | $2\omega_{in}$ (cổng XOR lật cả hai sườn xung) | Dễ lọc hơn $1\omega_{in}$ đôi chút nhưng biên độ xung luôn đập tối đa $0 \leftrightarrow V_{DD}$ suốt chu kỳ! |
| **Độ nhô đỉnh hàm truyền (Peaking)** | Không có zero trên tử số $H(s)$ ($\lvert H(j\omega) \rvert \le 1$ khi $\zeta \ge \frac{\sqrt{2}}{2}$) | Ưu điểm hiếm hoi: không gây jitter peaking khi chọn $\zeta \ge 0.707$. |
| **Dải bắt khóa (Capture Range)** | Rất hẹp, chỉ cỡ $\sim \omega_{LPF}$ | Không tự kéo khóa được nếu tần số tự do VCO lệch xa tần số chuẩn lúc mới cấp nguồn. |

## 5. Thích ứng Đa Tiến trình (90nm / 65nm / 45nm) & Cách Kiểm chứng trong Cadence / Spectre

Khi triển khai PLL Loại I trên các tiến trình `90nm`, `65nm`, `45nm` (ví dụ PLL sóng mang tần số cao dùng bộ trộn Gilbert/CML XOR làm PD):
- **Áp lực tăng $K_{VCO}$ ở $V_{DD}$ thấp làm suy sụp $\zeta$**: Ở `65nm`/`45nm` ($V_{DD} \le 1.0\text{ V}$), biên độ ngõ ra của cổng XOR/nhân CML bị bóp nhỏ làm giảm $K_{PD}$, nhưng nếu thiết kế VCO không có dàn tụ chuyển mạch khiến $K_{VCO}$ quá lớn thì tích $K_{PD} K_{VCO}$ biến thiên dữ dội theo góc PVT, đẩy $\zeta = \frac{1}{2}\sqrt{\omega_{LPF}/(K_{PD} K_{VCO})}$ tụt xuống dưới $0.3$ gây dao động rung kéo dài. Do đó, bắt buộc dùng dàn tụ thô ghim nhỏ $K_{VCO}$, chọn $\zeta_{\text{nom}} \ge 0.8 \sim 1.0$, và nếu dùng bộ nhân vi sai CML phải phân cực qua gương dòng `topo-lvccml-wide-swing-mirror`, giảm nhiễu linh kiện theo `law-mos-thermal-and-flicker-noise`, bố cục cổng XOR cân bằng hoàn toàn hai đường vào $A \to Y$ và $B \to Y$ (dùng cổng XOR truyền dẫn đối xứng hoặc CML đối xứng theo `tech-common-centroid-sti-wpe-layout` và cách ly nền số theo `law-cmos-wells-and-latchup-guard-rings`).

**Quy trình kiểm chứng chuẩn trong Cadence Virtuoso / Spectre**:
1. **Đo đặc tuyến tĩnh bộ tách pha $V_{PD,\text{avg}}(\Delta\phi)$**: Cấp hai nguồn xung cùng tần số có độ lệch pha quét tham số từ $-2\pi$ đến $+2\pi$, lấy trung bình `average(VT("/vpd"))` trong một chu kỳ để đọc chính xác độ dốc $K_{PD}$ ($\text{V/rad}$) và vùng tuyến tính qua các góc PVT.
2. **Kiểm chứng mô hình pha tuyến tính & Đồng mô phỏng Verilog-A / Transistor**: Trước khi chạy toàn mạch transistor tốn hàng giờ, dựng mô hình Verilog-A cho VCO ($\omega_0, K_{VCO}$ trích xuất từ `pss`) kết hợp cổng XOR và lọc $R_{LPF} C_{LPF}$ mức transistor để kiểm tra đáp ứng quá độ $V_{cont}(t)$ trước một bước nhảy tần số nhỏ $\Delta f_{in}$: đo độ vọt lố (overshoot), chu kỳ rung $\omega_n\sqrt{1 - \zeta^2}$ và hằng số thời gian tắt dần $2/\omega_{LPF}$ đối chiếu trực tiếp với PT (16.22)–(16.23).
3. **Kiểm tra khả năng tự bắt khóa (Pull-in / Acquisition Test) & Mức Spur $2 f_{in}$ toàn mạch transistor**: Khởi tạo $V_{cont}(0)$ ở biên xa nhất để giả lập sai lệch tần số ban đầu $\Delta f_{\text{init}}$ ở góc `SS` và `FF` nhằm xác minh vòng thực sự bắt được khóa mà không trượt chu kỳ vô tận; khi đã khóa xác lập, đo độ nhấp nhô đỉnh–đỉnh $\Delta V_{cont,\text{pp}}$ ở tần số $2 f_{in}$ và chạy DFT / `pss` trên ngõ ra VCO để xác nhận vạch phổ biên tại $f_0 \pm 2 f_{in}$ thấp hơn ngưỡng đặc tả (thường $<-45\text{ dBc}$).

| Phép đo Kiểm chứng Spectre | Thiết lập Phân tích & Nút Quan sát | Tiêu chí Nghiệm thu (Sign-off) qua PVT |
| :--- | :--- | :--- |
| **Độ lợi tách pha $K_{PD}$** | `tran` quét lệch pha $\Delta\phi \in [0, 2\pi]$, lấy `average(VT("/vpd"))` | Đơn điệu trên $(0, \pi)$, độ dốc đạt $V_{DD}/\pi \pm 10\%$, duty cycle đầu vào $50\% \pm 2\%$. |
| **Động học bậc thang pha/tần số** | Bước nhảy $\Delta f_{in} = 0.1\,\omega_{LPF}/(2\pi)$, đo sóng $V_{cont}(t)$ | Vọt lố $< 20\%$ ($\zeta \ge 0.45 \sim 0.707$), bao hình hội tụ đúng hằng số thời gian $2/\omega_{LPF}$. |
| **Sai số pha tĩnh $\phi_0$** | Đo `delay()` giữa sườn lên `Vin` và `Vout` ở xác lập khóa | Bám sát $\pi/2 + (\omega_{in} - \omega_0)/(K_{PD} K_{VCO})$, không vượt biên $[0.2\pi, 0.8\pi]$. |
| **Gợn sóng $2 f_{in}$ & Reference Spur** | `dft` / `pss` trên $V_{cont}(t)$ và $V_{out}(t)$ sau khi khóa hoàn toàn | Biên độ hài $2 f_{in}$ khớp $V_{\text{pp}} \cdot \lvert G_{LPF}(j 2\omega_{in}) \rvert$, spur ngõ ra đạt ngưỡng thiết kế. |

## 6. Mốc Đối chiếu Sách Razavi & Thuật ngữ Chuẩn CLB

- **Mốc sách Razavi (2nd Ed.)**: Chương 16 — `§16.1.1` (*Phase Detector*, tr. 651–653, Hình 16.1–16.3, Ví dụ 16.1); `§16.1.2` (*Basic PLL Topology*, tr. 653–660, Hình 16.4–16.14, Ví dụ 16.2–16.4, PT 16.1–16.10); `§16.1.3` (*Dynamics of Simple PLL*, tr. 660–665, Hình 16.15–16.20, Ví dụ 16.5–16.6, PT 16.11–16.36); `§16.2.1` (*Problem of Lock Acquisition*, tr. 666, Hình 16.21, Bài tập 16.1–16.9).
- **Bảng Tra cứu Nhanh Phương trình Gốc Razavi Chương 16 (§16.1)**:
  - PT `(16.1)–(16.2)`: Định nghĩa khóa pha $\phi_{out} - \phi_{in} = \text{hằng số} \implies \omega_{out} = \omega_{in}$ tuyệt đối.
  - PT `(16.3)–(16.5)`: Mức điều khiển tĩnh $V_1 = (\omega_1 - \omega_0)/K_{VCO}$ và sai số pha tĩnh $\phi_0 = (\omega_1 - \omega_0)/(K_{PD} K_{VCO})$.
  - PT `(16.8)`: Tích phân bù bước nhảy pha $\int_{t_1}^{\infty} \Delta\omega_{out}\,dt = \phi_1$.
  - PT `(16.12)–(16.14)`: Hàm truyền vòng hở $H_{\text{open}}(s)$ và đóng vòng bậc hai $H(s)$ áp dụng cho cả pha dư lẫn tần số.
  - PT `(16.16)–(16.18)`: Dạng chuẩn $\omega_n = \sqrt{\omega_{LPF} K_{PD} K_{VCO}}$ và hệ số tắt dần $\zeta = \frac{1}{2}\sqrt{\omega_{LPF}/(K_{PD} K_{VCO})}$.
  - PT `(16.22)–(16.23)`: Đáp ứng bậc thang thiếu tắt dần và tốc độ tắt dần bao hình $\zeta\omega_n = \omega_{LPF}/2$.
  - PT `(16.30)–(16.36)`: Hàm truyền sai số pha $H_e(s) = 1 - H(s)$ và kiểm chứng định lý giá trị cuối cho bước nhảy tần số.
- **Đối chiếu Thuật ngữ Chuẩn CLB Vi Mạch**:
  - `phase-locked loop, PLL` (`T064`): vòng khóa pha; `negative-feedback loop` (`T535`): vòng hồi tiếp âm.
  - `digital gate` (`T033`): cổng logic số; `filtering` (`T1389`): lọc tín hiệu; `corner frequency` (`T818`): tần số cắt.
  - `Poles at Origin` (`T1801`): các cực tại gốc tọa độ; `two-pole system` (`T1635`): hệ thống hai cực.
  - `phase margin` (`T063`): dự trữ pha; `ringing` (`T1650`): dao động rung; `frequency peaking` (`T1653`): độ nhô đỉnh đáp ứng tần số.
