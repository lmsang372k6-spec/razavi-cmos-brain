---
{
  "id": "topo-frequency-synthesizer-integer-fractional-n",
  "kind": "topology",
  "domain": "sampled-and-clocked",
  "title_vi": "Bộ Tổng hợp Tần số Nguyên (Integer-N Pulse-Swallow) và Phân số Delta-Sigma (Fractional-N Frequency Synthesizers)",
  "title_en": "Integer-N Pulse-Swallow and Delta-Sigma Fractional-N Frequency Synthesizers",
  "summary": "Kiến trúc tổng hợp sóng mang đa kênh độ chính xác tinh thể thạch anh từ Razavi §16.5.1-16.5.3 đến thực tế RF hiện đại: phép nhân tần số f_out = N*f_REF, nguyên lý bộ chia nuốt xung (Pulse-Swallow Divider N = M*P + S dùng bộ chia tiền định hai mô-đun P/(P+1) tốc độ GHz), thảm họa nhân công suất nhiễu nội dải lên 20*log10(N) dB giam hãm băng thông của Integer-N, và bước nhảy vọt sang bộ tổng hợp Phân số Delta-Sigma (Fractional-N) định dạng nhiễu lượng tử hóa thông cao (1 - z^-1)^L.",
  "diagram": "../../diagrams/charge-pump-type2-pll.svg",
  "razavi_refs": [
    {
      "chapter": 16,
      "section": "16.5.1-16.5.3",
      "pages": "685-690",
      "equations": ["16.49", "16.50", "16.51", "16.52", "16.53", "16.54", "16.55", "16.56"]
    }
  ],
  "glossary_codes": [
    "T016",
    "T020",
    "T032",
    "T033",
    "T047",
    "T058",
    "T064",
    "T070",
    "T072",
    "T090",
    "T1025",
    "T1169",
    "T2079",
    "T2166",
    "T2169",
    "T2171",
    "T2174",
    "T2175",
    "T2177",
    "T2178",
    "T2179"
  ],
  "process_agnostic": true,
  "roles": {
    "dual_modulus_prescaler": "Khối chia tần số tốc độ siêu cao (CML / TSPC) đặt ngay sau VCO, chỉ cần chuyển đổi giữa hai tỉ số kế tiếp chia P hoặc chia (P + 1) theo bit điều khiển Modulus Control.",
    "program_and_swallow_counters": "Cặp bộ đếm số CMOS tốc độ thấp chạy ở f_VCO / P: bộ đếm nuốt S quyết định số lần chia (P+1), bộ đếm chương trình M quyết định tổng số chu kỳ để lập trình hệ số nguyên liên tục N = M*P + S.",
    "delta_sigma_modulus_modulator": "Bộ điều chế số tích lũy tràn đa tầng (MASH 1-1-1) đảo động hệ số chia tức thời N[k] mỗi chu kỳ f_REF sao cho trung bình bằng N + alpha, đồng thời đẩy năng lượng nhiễu lượng tử hóa dốc lên vùng tần số cao.",
    "divider_retimer_flipflop": "Một D-flip-flop tốc độ cao đặt cuối chuỗi chia được chốt trực tiếp bằng cạnh xung sạch từ chính VCO để xóa sạch toàn bộ jitter tích lũy của các cổng logic trong bộ đếm số!"
  },
  "symptoms_addressed": [
    "need-programmable-rf-channel-grid-from-single-fixed-crystal-oscillator",
    "cmos-programmable-counter-unable-to-operate-directly-at-multi-ghz-vco-frequency",
    "integer-n-narrow-channel-spacing-forcing-huge-n-high-inband-noise-and-slow-channel-hop",
    "periodic-fractional-spurs-from-simple-first-order-accumulator-fractional-division"
  ],
  "limitations": [
    "pulse-swallow-minimum-contiguous-divide-ratio-bounded-by-n-min-equals-p-times-p-minus-1",
    "inband-reference-and-charge-pump-phase-noise-always-amplified-by-20-log10-n",
    "fractional-n-quantization-noise-folds-into-baseband-if-charge-pump-is-nonlinear",
    "integer-boundary-spurs-ibs-emerge-when-vco-harmonic-lands-near-multiple-of-fref"
  ],
  "checklists": [
    "common-mos",
    "oscillator-and-pll",
    "spectre-pss-pnoise"
  ]
}
---

## 1. Bản chất Nguyên lý, Sơ đồ Mạch & Vai trò Từng Nhánh Cấu trúc

Trong mọi hệ thống thông tin vô tuyến (GSM, LTE, 5G, Wi-Fi, Bluetooth) và hệ thống phân phối xung nhịp đa miền trên SoC, một tinh thể thạch anh áp điện (`crystal reference`, điển hình $f_{\text{REF}} = 10 \sim 52\text{ MHz}$) có độ ổn định tần số tuyệt hảo cỡ vài phần triệu ($\pm 1 \sim 10\text{ ppm}$) nhưng lại cố định không thể quét kênh và không thể dao động ở tần số hàng GHz. Như Razavi trình bày tại §16.5.1 (trang 685–687, Hình 16.55–16.56), bằng cách chèn một bộ chia tần số khả trình vào đường hồi tiếp của PLL để tạo thành **bộ tổng hợp tần số** (`frequency synthesizer` — `T2178`), trạng thái khóa pha cưỡng bức $f_{\text{out}} / N = f_{\text{REF}} \implies f_{\text{out}} = N \cdot f_{\text{REF}}$, thừa hưởng độ chính xác $\text{ppm}$ tuyệt đối của thạch anh lên sóng mang nhiều GHz đồng thời cho phép nhảy kênh linh hoạt chỉ bằng cách thay đổi mã số $N$!

![Sơ đồ bộ tổng hợp tần số PLL bơm điện tích với bộ chia hồi tiếp khả trình làm nền tảng cho kiến trúc Integer-N và Fractional-N](../../diagrams/charge-pump-type2-pll.svg)

Tuy nhiên, việc hiện thực hóa phép chia tần số khả trình ở nhiều GHz và tối ưu độ sạch phổ đặt ra ba bài toán kiến trúc kinh điển dẫn dắt sự tiến hóa từ **Integer-$N$** sang **$\Delta\Sigma$ Fractional-$N$**:

1. **Bài toán Tốc độ Bộ Chia GHz & Kiến trúc Bộ Chia Nuốt Xung (`Pulse-Swallow Divider`, $N = M P + S$)**:
   - Một bộ đếm nhị phân nạp lại khả trình tổng quát (`programmable presettable CMOS counter`) có đường hồi tiếp kiểm tra chạm đích đi qua nhiều tầng cổng logic nên không thể chạy trực tiếp ở tần số VCO $5 \sim 20\text{ GHz}$ mà không tiêu thụ công suất khổng lồ! Nếu đặt trước nó một bộ chia cố định $\div P$ (ví dụ $\div 16$), tốc độ hạ xuống $16$ lần nhưng bước nhảy kênh tối thiểu lại vọt lên thành $\Delta f_{\text{ch}} = P \cdot f_{\text{REF}}$, mất khả năng chọn từng kênh hẹp!
   - **Giải pháp Bộ chia Nuốt Xung (`Pulse-Swallow Architecture`)**: Chỉ duy nhất khối đầu tiên tiếp xúc trực tiếp với VCO là **Bộ chia tiền định hai mô-đun (`Dual-Modulus Prescaler — DMP`, $\div P / (P+1)$**, ví dụ $\div 15/16$ hoặc $\div 32/33$ dùng chốt CML hoặc TSPC siêu nhanh). Ngõ ra của DMP (đã chậm đi $P$ lần!) nuôi đồng thời hai bộ đếm CMOS công suất thấp: **Bộ đếm Chương trình (`Program Counter` $M$)** và **Bộ đếm Nuốt (`Swallow Counter` $S$, với $S < M$)**.
   - *Chu trình vận hành trong 1 chu kỳ ngõ ra*: Khởi đầu chu kỳ, bit điều khiển mô-đun `MC = 1` ép DMP chia cho **$(P + 1)$** (mỗi nhịp đếm "nuốt" thêm đúng 1 xung VCO!). Sau khi đếm đủ **$S$ nhịp**, bộ đếm nuốt $S$ tràn và hạ `MC = 0`, chuyển DMP về chế độ chia **$P$** trong suốt **$(M - S)$ nhịp còn lại** cho tới khi bộ đếm chương trình $M$ chạm đích và đặt lại toàn bộ hai bộ đếm! Tổng số xung VCO đã tiêu thụ để xuất ra 1 xung hồi tiếp về PFD chính xác là:
     $$N = S \cdot (P + 1) + (M - S) \cdot P = M \cdot P + S$$
     Khi cố định $M$ và tăng $S$ từng đơn vị $0, 1, 2, \dots, P-1$, hệ số chia tổng $N$ tăng liên tục từng bước **$\Delta N = 1$** mà chỉ có một mạch nhỏ 4–5 flip-flop DMP phải chạy ở tốc độ sóng mang GHz!
2. **Nút thắt Cổ chai Cốt tử của Bộ Tổng hợp Nguyên (`Integer-N Bottleneck`)**:
   - Trong `Integer-N`, bước cách kênh vô tuyến bắt buộc bằng đúng tần số so pha tại PFD: $\Delta f_{\text{ch}} = f_{\text{REF}}$. Nếu chuẩn vô tuyến đòi hỏi bước kênh hẹp $\Delta f_{\text{ch}} = 200\text{ kHz}$ ở sóng mang $f_{\text{out}} = 2.4\text{ GHz}$:
     - Hệ số chia vọt lên khổng lồ: $N = \frac{2.4\text{ GHz}}{200\text{ kHz}} = \mathbf{12{,}000}$!
     - Theo phương trình đóng vòng (16.50), toàn bộ nhiễu pha nội dải của thạch anh, PFD và bơm điện tích bị nhân biên độ lên $N$ lần, tức công suất nhiễu pha nội dải tăng vọt thêm **$20\log_{10}(12{,}000) = +81.6\text{ dB}$**!
     - Đồng thời do giới hạn ổn định rời rạc Gardner ($f_c \le f_{\text{REF}}/10 = 20\text{ kHz}$!), băng thông vòng bị trói chặt ở dưới $20\text{ kHz}$: vừa **không thể nén nổi nhiễu pha VCO** trong dải $20\text{ kHz} \dots 1\text{ MHz}$, vừa làm **thời gian chuyển kênh kéo dài hàng trăm microgiây**!
3. **Cuộc Cách mạng Bộ Tổng hợp Phân số Điều chế $\Delta\Sigma$ (`Delta-Sigma Fractional-N Synthesizer`)**:
   - Phá tan xiềng xích $f_{\text{REF}} = \Delta f_{\text{ch}}$! Dùng thẳng thạch anh tần số cao sạch $f_{\text{REF}} = 40 \sim 80\text{ MHz}$ (giảm ngay hệ số chia ở $2.4\text{ GHz}$ xuống còn $N \approx 30 \sim 60$, cắt bỏ **$> 45\text{ dB}$** hệ số nhân nhiễu nội dải và cho phép mở rộng băng thông vòng lên $f_c = 500\text{ kHz} \sim 2\text{ MHz}$ khóa kênh trong vài microgiây!), trong khi một **bộ điều chế số $\Delta\Sigma$ đa tầng (`MASH 1-1-1`)** thay đổi động hệ số chia nguyên tức thời $N[k] \in \{N_0 - 3, \dots, N_0 + 4\}$ ở mỗi nhịp $T_{\text{REF}}$ sao cho giá trị trung bình thời gian bằng $N_{\text{avg}} = N_0 + \frac{K_{\text{frac}}}{2^B}$ (đạt độ phân giải bước kênh nhỏ hơn $1\text{ Hz}$!).

---

## 2. Hệ Phương trình Cốt lõi & Tư duy "Nhìn Mạch Đọc Nhanh" (Analysis by Inspection)

### 2.1. Điều kiện Liên tục Không Khuyết Mã của Bộ chia Nuốt Xung ($N_{\min} = P(P - 1)$)
Trong công thức $N = M P + S$: để bộ đếm nuốt $S$ kịp hoàn thành việc nuốt $S$ xung trước khi bộ đếm chương trình $M$ kết thúc chu kỳ, điều kiện phần cứng bắt buộc là **$M \ge S$** (hoặc $M > S$ tùy thiết kế logic nạp lại). Để quét liên tục mọi số nguyên không bị hở lỗ giữa lúc $S$ quay vòng từ $P - 1$ về $0$ và $M$ tăng thêm $1$, chỉ số $S$ phải được phép chạy hết tập dư $\{0, 1, \dots, P - 1\}$. Do đó giá trị nhỏ nhất của $M$ là $M_{\min} = P - 1$ (hoặc $P$), ấn định **ngưỡng chia liên tục tối thiểu**:

$$N_{\min,\text{contiguous}} = P(P - 1) \qquad \left(\text{ví dụ DMP } \div 16/17 \implies P = 16 \implies N_{\min} = 16 \times 15 = 240\right)$$

*Phản xạ thiết kế*: Nếu bạn cần tổng hợp dải tần bắt đầu từ $N = 60$ đến $N = 120$, **tuyệt đối không được chọn DMP $\div 16/17$** (vì dưới $240$ sẽ bị rỗng mã không chia được nhiều kênh!), mà phải chọn DMP $\div 8/9$ ($N_{\min} = 8 \times 7 = 56 \le 60$) hoặc dùng chuỗi chia mô-đun đa tầng nối tiếp (`Modular / Vaucher 2/3 Divider Chain`, cho phép chia liên tục mọi số nguyên từ $2^K$ đến $2^{K+1}-1$ với kiến trúc lặp cực gọn!).

### 2.2. Định luật Nhân Nhiễu $20\log_{10} N$ & Rút gọn Jitter của PLL (§16.5.1–16.5.3, PT 16.49–16.56)
Từ Phương trình (16.49)–(16.50) của Razavi, hàm truyền pha đóng vòng từ đầu vào $\Phi_{\text{in}}(s)$ tới đầu ra $\Phi_{\text{out}}(s)$ và hàm truyền nhiễu từ VCO $\Phi_{\text{VCO}}(s)$ tới đầu ra là:

$$\frac{\Phi_{\text{out}}(s)}{\Phi_{\text{in}}(s)} = N \cdot H_{\text{u}}(s), \qquad \frac{\Phi_{\text{out}}(s)}{\Phi_{\text{VCO}}(s)} = 1 - H_{\text{u}}(s)$$

trong đó $H_{\text{u}}(s)$ có độ lợi một chiều bằng $1$ ($H_{\text{u}}(0) = 1$). Đối với mọi nguồn nhiễu quy đổi về đầu vào bộ tách pha — bao gồm nhiễu pha của thạch anh $S_{\phi,\text{XTAL}}(f)$, nhiễu thời gian của PFD, nhiễu dòng của bơm điện tích $\left(\frac{2\pi}{I_P}\right)^2 S_{i,\text{CP}}(f)$ và nhiễu thời gian của cạnh ra bộ chia tần số $S_{\phi,\text{DIV}}(f)$ — mật độ phổ công suất nhiễu pha trong dải thông ($f \ll f_c$) bị nhân lên **$N^2$ lần**:

$$\mathcal{L}_{\text{in-band,tot}}(f) = \mathcal{L}_{\text{in,eq}}(f) + 20\log_{10}(N) \;\; [\text{dBc/Hz}]$$

Đồng thời trong **Mục 16.5.3 (Ví dụ 16.13, PT 16.55–16.56)** về khử jitter: nếu một tín hiệu đồng hồ đầu vào mang điều chế pha nhiễu tần số $\omega_m \gg \omega_n$ (nằm ngoài băng thông vòng của một PLL băng hẹp có $N = 1$), biên độ jitter truyền ra ngõ ra bị nén đi theo tỉ số xấp xỉ $\left|\frac{\Phi_{\text{out}}}{\Phi_{\text{in}}}(j\omega_m)\right| \approx \frac{2\zeta\omega_n}{\omega_m}$ (dốc $-20\text{ dB/dec}$ do zero trong tử số $H(s)$, hoặc $-40\text{ dB/dec}$ sau cực $\omega_{p3}$!).

### 2.3. Phổ Nhiễu Lượng tử hóa Pha của Bộ Điều chế $\Delta\Sigma$ Bậc $L$ (`MASH-L Phase Noise Shaping`)
Tại sao trong Fractional-$N$ không dùng một bộ tích lũy bậc 1 đơn giản (cứ $Q$ chu kỳ lại chia $N+1$ một lần để đạt $N + 1/Q$)? Bởi vì chuỗi tràn của bộ tích lũy bậc 1 tuần hoàn cứng theo chu kỳ $Q \cdot T_{\text{REF}}$, tạo ra sóng răng cưa lỗi pha lớn trên $V_{cont}$ và đẻ ra **vạch phổ giả phân số khổng lồ (`Fractional Spurs`)** ngay tại độ lệch $\frac{f_{\text{REF}}}{Q}$ nằm lọt thỏm bên trong băng thông vòng!

Khi thay bằng bộ điều chế $\Delta\Sigma$ bậc $L$ (điển hình **MASH 1-1-1 bậc $L = 3$**) có nhiễu lượng tử hóa tần số chuẩn hóa trải đều trắng trên $[-f_{\text{REF}}/2, +f_{\text{REF}}/2]$ với phương sai bước chia $\frac{1}{12}$ và hàm định dạng nhiễu tần số $(1 - z^{-1})^L$:
- Vì pha là **tích phân rời rạc** của tần số chia (nhân thêm thừa số $\frac{1}{1 - z^{-1}}$ làm giảm 1 bậc đạo hàm!), mật độ phổ nhiễu pha lượng tử hóa một phía quy về ngõ vào PFD (đã tính đến tích phân tần số sang pha và nhân $N$ ra ngõ ra VCO, rút gọn $N$ nên **hoàn toàn độc lập với $N$!**) tuân theo công thức kinh điển của Miller & Perrott:

$$\mathcal{L}_{\Delta\Sigma,\text{open}}(f) = 10\log_{10}\left\{ \frac{(2\pi)^2}{12 \, f_{\text{REF}}} \cdot \left[ 2 \sin\left(\frac{\pi f}{f_{\text{REF}}}\right) \right]^{2(L - 1)} \right\} \;\; [\text{dBc/Hz}]$$

Sau khi đi qua hàm truyền đóng vòng thông thấp bậc $K_{\text{PLL}}$ của PLL (với bộ lọc vòng bậc ba + 1 mắt RC phụ cho $K_{\text{PLL}}$ dốc $-60\text{ dB/dec}$ ở $f > f_{p3}, f_{p4}$), phổ nhiễu $\Delta\Sigma$ tại ngõ ra VCO là $\mathcal{L}_{\Delta\Sigma,\text{out}}(f) = \mathcal{L}_{\Delta\Sigma,\text{open}}(f) + 20\log_{10}\left|\frac{H_{\text{cl}}(jf)}{N}\right|$:
- Với $L = 3$ (MASH 1-1-1): ở tần số thấp $f \ll f_{\text{REF}}$, $\mathcal{L}_{\Delta\Sigma,\text{open}}(f)$ tăng theo độ dốc **$20(L - 1) = +40\text{ dB/dec}$** ($f^4$ công suất!), nên ở nội dải ($f < 100\text{ kHz}$) nhiễu lượng tử hóa thấp dưới **$-140\text{ dBc/Hz}$**!
- Để dập tắt cái dốc $+40\text{ dB/dec}$ này ở ngoài băng thông vòng ($f_c < f < f_{\text{REF}}/2$), hàm truyền đóng vòng $\left|H_{\text{cl}}(jf)/N\right|$ bắt buộc phải lăn dốc ít nhất **$-60\text{ dB/dec}$** (net roll-off $-20\text{ dB/dec}$), tức **MASH bậc $L$ đòi hỏi bậc lọc vòng PLL tối thiểu là $(L + 1)$** (MASH 1-1-1 bậc $3 \implies$ bắt buộc dùng PLL bậc $4$ có cả $C_2$ và mắt lọc $R_3 C_3$!).

### 2.4. Ví dụ Định lượng Đối chiếu Trực diện Integer-$N$ vs MASH 1-1-1 Fractional-$N$ cho GSM/BLE ($2.4\text{ GHz}$)
Yêu cầu tổng hợp sóng mang quanh $f_{\text{out}} = 2.4\text{ GHz}$ với độ phân giải kênh $\Delta f_{\text{ch}} \le 250\text{ kHz}$, giả sử bộ PFD+CP chuẩn hóa có sàn nhiễu quy đổi về $1\text{ Hz}$ là $\text{PN}_{\text{norm}} = -222\text{ dBc/Hz}$ (tức $\mathcal{L}_{\text{in-band}} = -222 + 10\log_{10}(f_{\text{REF}}) + 20\log_{10}(N)$):
1. **Thiết kế Integer-$N$ ($f_{\text{REF}} = 250\text{ kHz}$, $N = 9600$)**:
   - Sàn nhiễu nội dải: $-222 + 10\log_{10}(2.5\times 10^5) + 20\log_{10}(9600) = -222 + 54.0 + 79.6 = \mathbf{-88.4\text{ dBc/Hz}}$ (quá ồn!).
   - Băng thông vòng tối đa: $f_c \le 25\text{ kHz} \implies$ thời gian khóa kênh $> 150\,\mu\text{s}$; không nén được nhiễu VCO ở $100\text{ kHz}$.
2. **Thiết kế MASH 1-1-1 Fractional-$N$ ($f_{\text{REF}} = 50\text{ MHz}$ kèm bộ tích lũy 20-bit cho bước kênh $47.7\text{ Hz}$, $N = 48$)**:
   - Sàn nhiễu nội dải: $-222 + 10\log_{10}(5\times 10^7) + 20\log_{10}(48) = -222 + 77.0 + 33.6 = \mathbf{-111.4\text{ dBc/Hz}}$ (**sạch hơn $23.0\text{ dB}$**!).
   - Chọn băng thông vòng $f_c = 800\text{ kHz}$ ($\ll 50\text{ MHz} / 10$, khóa kênh siêu tốc trong $< 5\,\mu\text{s}$!): tại $f = 800\text{ kHz}$, nhiễu lượng tử mở của MASH 1-1-1 là $10\log_{10}\left[\frac{4\pi^2}{12 \times 50\times 10^6} \left(2\sin\frac{0.8\pi}{50}\right)^4\right] \approx -101.8\text{ dBc/Hz}$, sau khi trừ $3\text{ dB}$ cắt vòng và lọc bậc 4 ($f_{p3} = 2.8\text{ MHz}, f_{p4} = 4.5\text{ MHz}$) nằm hoàn toàn dưới mặt nạ phổ của VCO!

---

## 3. Bất biến Cấu trúc & Các Bẫy Lỗi Kinh điển (Structural Invariants & Traps)

- **[INV-SYN-01] Bất biến Chốt Tái Định Thời Ở Đích Cuối Bộ Chia (`Output Edge Retiming D-FF`)**: Khi tín hiệu đi nối tiếp qua DMP $\div P/(P+1)$ và chuỗi $8 \sim 12$ tầng flip-flop bất đồng bộ (ripple counter) của bộ đếm $M$, nhiễu nhiệt và nhiễu nguồn cấp của **tất cả các cổng logic dọc đường cộng dồn phương sai jitter** lên cạnh ra đưa về PFD (và bị PLL nhân tiếp với $N^2$!). **Quy tắc sắt đá**: Không bao giờ nối thẳng ngõ ra bộ đếm ripple vào PFD! Phải đặt **một D-Flip-Flop tốc độ cao cuối cùng (`Retimer FF`)** nhận tín hiệu ra của bộ đếm làm dữ liệu `D` và dùng **chính xung nhịp gốc cực sạch của VCO** làm xung `CLK` chốt lại! Phép tái định thời này quét sạch $100\%$ jitter của toàn bộ chuỗi đếm số phía trước, chỉ để lại duy nhất nhiễu của 1 con Retimer FF (lưu ý thiết kế biên thời gian thiết lập/giữ `setup/hold margin` cho đường dữ liệu vào Retimer qua mọi góc PVT!).
- **[INV-SYN-02] Bất biến Thêm Nhiễu Giả Ngẫu nhiên LSB (`LSB Dithering`) Chống Chu kỳ Giới hạn trong MASH**: Nếu đầu vào phân số $K_{\text{frac}}$ của bộ điều chế MASH 1-1-1 là hằng số có nhiều bit $0$ tận cùng (ví dụ $K_{\text{frac}} / 2^B = 1/2$ hay $1/4$), quỹ đạo trạng thái số bị ngắn lại gây xuất hiện các vạch spur rời rạc thay vì phổ trắng! Luôn cố định bit thấp nhất `LSB = 1` (tạo lệch tần số tĩnh vô hại $< 1\text{ Hz}$) hoặc cộng chuỗi LFSR dither 1-bit để đảm bảo chu kỳ tuần hoàn của bộ điều chế dài tối đa và phổ lượng tử trơn mịn tuyệt đối.
- **[TRAP-SYN-01] Bẫy Phi tuyến PFD/CP Gập Nhiễu Lượng tử $\Delta\Sigma$ Xuống Nội Dải (`Noise Folding`)**: Đây là nguyên nhân số 1 khiến chip Fractional-$N$ đo thực tế có sàn nhiễu nội dải cao hơn mô phỏng tuyến tính tới $15 \sim 25\text{ dB}$! MASH 1-1-1 quét hệ số chia từ $N-3$ đến $N+4$, nên sai số pha tức thời tại PFD nhảy lắc lư cỡ $\pm 4\pi \frac{1}{N}$ rad quanh điểm cân bằng. Nếu đường truyền PFD+CP bị gãy khúc tại $\Delta\phi = 0$ do $I_{UP} \neq I_{DN}$ (`topo-pfd-deadzone-and-charge-pump-nonidealities`), thành phần bậc hai $\alpha_2 (\Delta\phi)^2$ sẽ tự nhân tích chập phổ nhiễu lượng tử cao tần ở $10 \sim 25\text{ MHz}$ để trộn gập thẳng thành sàn nhiễu trắng phẳng lì ở $10\text{ kHz}$! Khắc phục chuẩn: bơm một dòng rỉ một chiều nhỏ cố định (`DC bleed current` $I_{\text{bleed}} \approx 2\% \sim 5\%\,I_P$) tại ngõ ra CP để dịch điểm khóa tĩnh sang $\Delta\phi_{\text{dc}} > |\Delta\phi_{\Delta\Sigma,\text{peak}}|$, ép toàn bộ quỹ đạo động của $\Delta\Sigma$ chỉ nằm trọn trên **một nhánh đơn cực duy nhất (chỉ nhánh UP)** không bao giờ cắt qua điểm gãy $0$!
- **[TRAP-SYN-02] Bẫy Vạch Phổ Biên Nguyên (`Integer-Boundary Spurs — IBS`)**: Khi tổng hợp kênh phân số cực sát một bội số nguyên của thạch anh, ví dụ $f_{\text{out}} = (48 + 0.002) \times 50\text{ MHz} = 2400.1\text{ MHz}$, hài của VCO hoặc dòng chuyển mạch bộ chia giao thoa qua đế bán dẫn / nguồn cấp với hài thứ $48$ của thạch anh tạo vạch nhịp hiệu tần tại đúng $\Delta f = 0.002 \times 50\text{ MHz} = \mathbf{100\text{ kHz}}$ nằm gọn trong băng thông vòng PLL nên không bị lọc! Để diệt IBS, phải bọc cách ly hoàn toàn khối đệm thạch anh khỏi VCO (`tech-substrate-noise-coupling-and-shielding`) và hỗ trợ chọn đổi hai tần số chia tham chiếu nếu kênh rơi sát biên nguyên.

---

## 4. Lộ trình Nâng cấp Cấu trúc & Bát giác Đánh đổi (Upgrade Paths & Design Octagon)

Trong `concept-analog-design-octagon`, lựa chọn kiến trúc tổng hợp tần số quyết định cấu trúc toàn bộ máy thu phát:

- **Nền tảng kết nối từ**: Ghép nối trực tiếp bộ lọc vòng bậc ba/bậc bốn từ `tech-cp-pll-third-order-loop-filter-synthesis`, mạch PFD/CP tuyến tính cao từ `topo-pfd-deadzone-and-charge-pump-nonidealities`, và lõi VCO tạp âm thấp từ `topo-quadrature-vco-and-varactor-tuning` & `law-oscillator-phase-noise-leeson-and-isf`.
- **Đối chiếu Toàn diện các Họ Kiến trúc Tổng hợp Tần số**:

| Đặc trưng Kiến trúc | Integer-$N$ (Pulse-Swallow) | $\Delta\Sigma$ Fractional-$N$ (MASH 1-1-1) | Fractional-$N$ + Phase-Interpolator / DTC | Sub-Sampling / All-Digital PLL (SS-PLL / ADPLL) |
| :--- | :--- | :--- | :--- | :--- |
| **Bước nhảy kênh $\Delta f_{\text{ch}}$** | Cứng bằng $f_{\text{REF}}$ | Nhỏ tùy ý ($< 1\text{ Hz}$ với 24-bit) | Nhỏ tùy ý ($< 1\text{ Hz}$) | Nhỏ tùy ý + hiệu chỉnh số hoàn toàn |
| **Hệ số nhân nhiễu $20\log_{10} N$** | Rất lớn khi $\Delta f_{\text{ch}}$ hẹp | Nhỏ nhờ dùng thẳng $f_{\text{REF}}$ cao | Nhỏ | SS-PLL **không bị nhân $N^2$** nhiễu PD/CP! |
| **Băng thông vòng & Tốc độ khóa** | Hẹp ($\le \Delta f_{\text{ch}}/10$), khóa chậm | Rộng ($0.2 \sim 2\text{ MHz}$), khóa vài $\mu\text{s}$ | Rất rộng (tới $5\text{ MHz}$) | Rộng + hỗ trợ chuyển chế độ Gear-Shifting |
| **Độ phức tạp & Cạm bẫy chính** | Đơn giản, không có fractional spur | Nhiễu gập CP phi tuyến & IBS | Triệt lỗi lượng tử ngay trước PFD bằng DTC | Đòi hỏi TDC độ phân giải vài ps hoặc khóa FLL phụ |

---

## 5. Thích ứng Đa Tiến trình (90nm / 65nm / 45nm) & Cách Kiểm chứng trong Cadence / Spectre

### 5.1. Thiết kế Chuỗi Chia Tốc độ Cao ở `90nm` / `65nm` / `45nm`
- Ở `65nm` và `45nm`, cổng logic TSPC (`True Single-Phase Clock` dùng 9 transistor không tốn dòng tĩnh!) dễ dàng vận hành tin cậy tới $8 \sim 14\text{ GHz}$ qua mọi góc PVT, cho phép thay thế chốt vi sai CML ngốn hàng miliampe ở các tầng đầu của bộ chia $\div 2/3$ cho băng tần dưới $10\text{ GHz}$ (chỉ cần dùng CML ở tầng $\div 2$ đầu tiên khi $f_{\text{VCO}} > 15\text{ GHz}$).
- **Cách ly Xung Đá Ngược (`Kickback Isolation`) giữa Bộ Chia và Khung LC-VCO**: Cổng đầu vào của bộ chia bật tắt biên độ lớn tạo biến thiên điện dung $C_{\text{in}}(V)$ và đá nhiễu hài từ bộ đếm số ngược về khung cộng hưởng VCO (gây kéo tần số VCO — `load pulling` và IBS!). Luôn chèn một **tầng đệm cách ly nguồn chung / cascode nhỏ** giữa khung LC-VCO và ngõ vào bộ chia tiền định!

### 5.2. Phác đồ Kiểm chứng Chuỗi Chia và Đồng Mô phỏng Hỗn hợp Fractional-$N$ trong Spectre
1. **Kiểm tra Đường cong Nhạy Đầu vào của Bộ chia Tiền định (`Divider Sensitivity Curve` bằng `tran` / `pss`)**: Quét tần số từ $0.5 f_{\min}$ tới $1.3 f_{\max}$ và tìm biên độ sóng sin tối thiểu $V_{\text{in,min}}(f)$ mà bộ chia $\div P/(P+1)$ chia đúng ở cả hai chế độ `MC = 0` và `MC = 1` tại góc `SS 125°C` và `FF -40°C` (đảm bảo biên độ VCO thực tế cao hơn đường cong nhạy ít nhất $6\text{ dB}$!).
2. **Kiểm tra Biên Thời gian của Retimer FF & Logic Nuốt Xung**:
```spice
// Kiem tra chu trinh chia Pulse-Swallow N = M*P + S va do sạch jitter sau Retimer FF trong Spectre
simulator lang=spectre
parameters f_vco=4.8G

// Nguon song mang VCO kem nhieu hoac lech nhe de kiem tra setup/hold cua Retimer FF o goc SS 125C & FF -40C
Vvco_p (vco_p 0) vsource type=sine ampl=0.45 sinedc=0.6 freq=f_vco
Vvco_n (vco_n 0) vsource type=sine ampl=0.45 sinedc=0.6 freq=f_vco sinephase=180

// 1. Kiem chung ty so chia chinh xac tren 10 chu ky ngo ra f_div = f_vco / N:
tran_div tran stop=300n errpreset=conservative
// Xac nhan trong Calculator: freq(v("/div_retimed_out")) == f_vco / (M_val * P_val + S_val) chinh xac tuyet doi!

// 2. Do san nhieu pha cua bo chia da Retime bang PSS + PNoise (Driven mode voi fund = f_vco / N):
pss_div pss fund=(f_vco/120) harms=120 tstab=100n errpreset=conservative
pnoise_div (div_retimed_out 0) pnoise sweeptype=relative relharmnum=1 start=1k stop=10M \
    dec=5 maxsideband=60 noisetype=timedomain
// Nhieu pha cua Retimed Divider phai nam thap hon san PFD+CP it nhat 10 dB (thuong < -150 dBc/Hz tai 100 kHz)!
```

---

## 6. Mốc Đối chiếu Sách Razavi & Thuật ngữ Chuẩn CLB

- **Sách gốc Razavi (2nd Ed.)**: Chương 16, Mục `16.5.1` (*Frequency Multiplication and Synthesis*, trang 685–687, Hình `16.55`–`16.56`, Phương trình `16.49`–`16.54`), Mục `16.5.2` (*Skew Reduction*, trang 687–688, Hình `16.57`–`16.59`), và Mục `16.5.3` (*Jitter Reduction*, trang 688–690, Hình `16.60`–`16.61`, Ví dụ `16.13`, Phương trình `16.55`–`16.56`, Bài tập `16.15`–`16.16`).
- **Đối chiếu Thuật ngữ Chuẩn CLB Vi Mạch (`terms-vi-en.json`)**:
  - `T2178` (`frequency synthesizer / feedback divider`): **bộ tổng hợp tần số (kèm bộ chia tần hồi tiếp)**; `T2179` (`PLL noise transfer bandwidth trade-off`): **đối ngẫu băng thông truyền nhiễu trong PLL**.
  - `T072` (`RF transmitter`): **bộ phát RF**; `T2079` (`clock frequency`): **tần số xung nhịp**.
  - `T2177` (`reference spur`): **vạch nhiễu giả tần số tham chiếu**; `T1169` (`noise bandwidth`): **băng thông nhiễu**; `T020` (`clock recovery`): **khôi phục xung nhịp**.
