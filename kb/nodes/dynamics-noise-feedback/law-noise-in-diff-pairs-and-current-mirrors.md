---
{
  "id": "law-noise-in-diff-pairs-and-current-mirrors",
  "kind": "law",
  "domain": "dynamics-noise-feedback",
  "title_vi": "Định luật Nhiễu trong Gương Dòng Phân cực & Cặp Vi sai / 5T-OTA (Current-Mirror & Differential-Pair Noise Laws)",
  "title_en": "Noise Multiplication in Current Mirrors, Differential-Pair 2x Noise Law, and Tail-Current Symmetry-Breaking Mechanisms",
  "summary": "Giải phẫu định lượng cơ chế nhân công suất nhiễu theo K^2 và cộng nhiễu 4kT*gamma*gm_out*(1+K) trong mạng phân phối gương dòng (kèm mạch lọc RB-CB và bẫy dòng rò cổng nanomet), phép suy diễn chính xác vì sao cặp vi sai tải thụ động lẫn tải chủ động gương dòng 5T-OTA đều có công suất nhiễu gấp đôi tầng CS đơn (8kT*gamma), và 3 cơ chế vật lý phá vỡ tính đối xứng làm nhiễu nguồn dòng đuôi ISS tràn thẳng ra ngõ ra.",
  "diagram": "../../diagrams/mos-noise-input-referred.svg",
  "razavi_refs": [
    {
      "chapter": 7,
      "section": "7.5-7.6",
      "pages": "254-263",
      "equations": ["7.114", "7.116", "7.118", "7.121", "7.125", "7.126", "7.133", "7.140", "7.142"]
    }
  ],
  "glossary_codes": ["T012", "T026", "T233", "T392", "T512", "T586", "T1139", "T1147", "T1178"],
  "process_agnostic": true,
  "roles": {
    "reference_diode_branch": "Transistor mắc diode M_REF ở nhánh tham chiếu chuyển đổi cả dòng nhiễu nguồn chuẩn I_REF lẫn nhiễu tự sinh của chính nó thành điện áp nhiễu trên đường bus cổng phân cực Vb, bị khuếch đại công suất lên K^2 lần khi nhân dòng 1:K",
    "rb_cb_bias_lowpass_filter": "Mắt lọc thông thấp RB-CB chèn giữa cổng M_REF và cổng transistor nguồn dòng ngõ ra giúp hạ sâu tần số cắt nhiễu xuống dưới dải tín hiệu mà không tốn tụ bypass hàng chục nF, miễn là kiểm soát được dòng rò cổng qua RB",
    "differential_input_transconductors": "Cặp vi sai M1-M2 có hai cực cổng mắc nối tiếp đối với tín hiệu vi sai và nút nguồn chung P không phải đất ảo đối với nhiễu không tương quan, làm công suất nhiễu quy về ngõ vào tăng gấp đôi (8kT*gamma/gm) so với tầng CS đơn",
    "active_current_mirror_load": "Tải chủ động gương dòng M3-M4 trong 5T-OTA vừa phản chiếu nhiễu nửa trái qua diode M3 vừa cộng nhiễu trực tiếp từ M4 ở nửa phải, cho tổng nhiễu quy về ngõ vào giống hệt cặp vi sai đối xứng tải nguồn dòng",
    "tail_bias_current_source": "Nguồn dòng đuôi M_SS triệt tiêu ở ngõ ra vi sai hoàn toàn khi cân bằng tĩnh (Delta Vin = 0), nhưng rò nhiễu qua chuyển đổi đơn đầu hữu hạn của 5T-OTA, qua trễ pha cực gương omega_m ở tần số cao, và qua điều chế gm khi có tín hiệu lớn"
  },
  "symptoms_addressed": [
    "reference-current-mirror-magnifying-bandgap-and-1f-noise-by-k-squared",
    "unrealistic-nanofarad-bypass-capacitor-on-diode-connected-mirror-node",
    "applying-virtual-ground-half-circuit-blindly-to-uncorrelated-diff-pair-noise",
    "tail-current-source-flicker-and-thermal-noise-corrupting-vco-mixer-or-ota-output",
    "gate-leakage-voltage-drop-across-large-mos-bias-filter-resistor-rb"
  ],
  "limitations": [
    "rb-cb-gate-filter-slows-down-power-up-settling-time-and-injects-supply-transient-via-parasitic-cap-if-referenced-to-wrong-rail",
    "diff-pair-consumes-4x-power-compared-to-single-ended-cs-for-identical-input-referred-noise-voltage-at-fixed-overdrive",
    "small-signal-ac-noise-simulation-at-zero-differential-input-completely-misses-large-signal-tail-noise-modulation"
  ],
  "checklists": ["common-mos", "current-mirror", "differential-pair"]
}
---

## 1. Bản chất Nguyên lý, Sơ đồ Mạch & Vai trò Từng Nhánh Cấu trúc

Khi bước từ một tầng khuếch đại cô lập sang một vi mạch tương tự thực thụ, hai khối xây dựng nền tảng xuất hiện khắp mọi nơi là mạng **phân cực (`T012`, biasing)** dùng **gương dòng (`T026`, current mirror)** để phân phối **dòng điện phân cực (`T233`, bias current)** trên toàn chip, và **cặp vi sai (`T586`, differential pair)** kết hợp **tải chủ động (`T512`, active load)** để kháng nhiễu nguồn và chế độ chung (Razavi Chương 7, §7.5–§7.6, tr. 254–263). Tuy nhiên, chính hai khối tưởng chừng "quen thuộc đến mức vô hại" này lại ẩn chứa ba cạm bẫy nhiễu tinh vi nhất của thiết kế vi mạch CMOS:

![Mô hình hóa nhiễu quy về cực cổng, cơ chế nhân nhiễu K^2 trong gương dòng và phân tích nhiễu không tương quan trong cặp vi sai](../../diagrams/mos-noise-input-referred.svg)

1. **Hiệu ứng Khuếch đại Nhiễu Theo Bình phương Tỉ số Nhân Gương ($K^2$ Noise Magnification trong §7.5):** Để tiết kiệm dòng tĩnh ở nhánh chuẩn, người thiết kế rất hay lấy một dòng tham chiếu nhỏ $I_{\text{REF}}$ (từ mạch Bandgap hoặc PTAT) chảy qua transistor mắc diode $M_{\text{REF}}$ nhỏ, rồi nhân gương tỉ lệ $1 : K$ ($K = 5 \dots 20$) sang transistor tải/phân cực lớn $M_1$ mang dòng $I_{D1} = K I_{\text{REF}}$. Về mặt tín hiệu nhỏ, $M_{\text{REF}}$ có diện tích kênh nhỏ gấp $K$ lần $M_1$ (nên công suất nhiễu $1/f$ quy về cổng lớn gấp $K$ lần!) đồng thời đóng vai trò bộ biến đổi dòng–áp nhân dòng nhiễu của chính nguồn $I_{\text{REF}}$ lên $K$ lần biên độ — tức **$K^2$ lần công suất nhiễu** ở ngõ ra!
2. **Sự Sụp đổ của Khái niệm "Đất Ảo Nửa Mạch" Đối với Nhiễu Ngẫu nhiên Không Tương quan (§7.6, Hình 7.56):** Với tín hiệu vi sai tiền định $+V_{in}/2$ và $-V_{in}/2$, nút nguồn chung $P$ của cặp vi sai đứng yên làm đất ảo. Nhưng hai nguồn nhiễu nội tại $I_{n1}$ (của $M_1$) và $I_{n2}$ (của $M_2$) **hoàn toàn không tương quan thống kê**! Tại một thời điểm bất kỳ, $I_{n1}$ nhấp nhô độc lập với $I_{n2}$, kéo nút nguồn chung $P$ dao động theo và chia đúng một nửa dòng $I_{n1}/2$ sang nhánh $M_2$ theo chiều ngược lại! Chỉ khi xét riêng từng nguồn một (hoặc dùng bổ đề điện áp nhiễu nối tiếp tại hai cực cổng Hình 7.57), ta mới chứng minh chặt chẽ được định luật bất biến $8kT\gamma$ của cặp vi sai.
3. **Ba Cửa Ngõ Phá Vỡ Tính "Tàng hình" Của Nguồn Dòng Đuôi $I_{SS}$ (§7.6, Hình 7.55, 7.62):** Dù ở điểm cân bằng lý tưởng ($\Delta V_{in} = 0$) của cặp vi sai hoàn toàn đối xứng, dòng nhiễu đuôi $I_{n,SS}$ chia đôi cân bằng và triệt tiêu trong điện áp vi sai $V_{X} - V_{Y}$, sự triệt tiêu đó lập tức tan vỡ khi: *(a)* mạch xuất ngõ ra đơn đầu qua gương dòng 5T-OTA (cả ở tần số thấp theo $\Delta V_{\text{out}} = -\frac{I_{n,SS}}{2 g_{m3}}$ lẫn vọt mạnh ở tần số cao quanh cực gương $\omega_m$!), *(b)* cặp vi sai lệch khỏi điểm cân bằng bởi tín hiệu vào lớn $\Delta V_{in} \neq 0$, hoặc *(c)* hai nhánh mất đối xứng trở kháng/điện dung.

---

## 2. Hệ Phương trình Cốt lõi & Tư duy "Nhìn Mạch Đọc Nhanh" (Analysis by Inspection)

### 2.1. Định luật Nhân Nhiễu Gương Dòng $1 : K$ & Mạch Lọc Thông Thấp $R_B C_B$ (§7.5, Phương trình 7.114–7.118)
Xét gương dòng sao chép tỉ lệ $(W/L)_1 = K (W/L)_{\text{REF}}$ (ký hiệu $N$ trong Hình 7.53a của sách Razavi, với cùng chiều dài kênh $L_1 = L_{\text{REF}}$ sao cho $I_{D1} = K I_{\text{REF}}$ và $g_{m1} = K g_{m,\text{REF}}$). Gọi $\overline{I_{n,\text{REF,in}}^2}$ là mật độ phổ dòng nhiễu sẵn có trên nguồn dòng tham chiếu đầu vào $I_{\text{REF}}$, còn $V_{n,\text{REF}}$ và $V_{n1}$ là **điện áp nhiễu quy về cực cổng (`T1147`)** của riêng $M_{\text{REF}}$ và $M_1$:
- **Khi chưa có tụ lọc tại nút cổng chung $X$:** Mạch tương đương Thévenin nhìn vào nhánh diode $M_{\text{REF}}$ có trở kháng ra $R_{\text{Thev}} = \frac{1}{g_{m,\text{REF}}}$ và điện áp nhiễu hở mạch $\overline{V_{n,X}^2} = \frac{\overline{I_{n,\text{REF,in}}^2}}{g_{m,\text{REF}}^2} + \overline{V_{n,\text{REF}}^2}$. Điện áp này cộng không tương quan với $\overline{V_{n1}^2}$ rồi nhân với $g_{m1}^2 = K^2 g_{m,\text{REF}}^2$:

$$
\overline{I_{n,D1}^2} = K^2 \overline{I_{n,\text{REF,in}}^2} + g_{m1}^2 \left( \overline{V_{n,\text{REF}}^2} + \overline{V_{n1}^2} \right)
$$

  - *Với thành phần nhiễu nhiệt:* Thay $\overline{V_{n,\text{REF,th}}^2} = \frac{4kT\gamma}{g_{m,\text{REF}}} = \frac{4kT\gamma K}{g_{m1}}$ và $\overline{V_{n1,\text{th}}^2} = \frac{4kT\gamma}{g_{m1}}$, ta thu được biểu thức tổng quát:

$$
\overline{I_{n,D1,\text{th}}^2} = K^2 \overline{I_{n,\text{REF,in}}^2} + 4 k T \gamma g_{m1} (1 + K)
$$

  - *Với thành phần **nhiễu nhấp nháy (`T392`)** $1/f$:* Vì $L_1 = L_{\text{REF}}$ và $W_1 = K W_{\text{REF}}$, diện tích cổng của $M_{\text{REF}}$ nhỏ hơn $M_1$ đúng $K$ lần nên $\overline{V_{n,\text{REF},1/f}^2} = K \overline{V_{n1,1/f}^2}$! Do đó nhánh chuẩn nhỏ bé $M_{\text{REF}}$ đóng góp nhiễu $1/f$ ở ngõ ra **gấp $K$ lần chính transistor nguồn dòng chính $M_1$** ($\overline{I_{n,D1,1/f}^2} = g_{m1}^2 \overline{V_{n1,1/f}^2}(1 + K)$)!
- **Khi gắn tụ nối tắt đơn độc $C_B$ tại nút diode $X$ xuống đất (Hình 7.53, Phương trình 7.114–7.117):** Hằng số thời gian tại nút $X$ bị trở kháng thấp $\frac{1}{g_{m,\text{REF}}}$ khống chế (Phương trình 7.114–7.115, với $N \equiv K$):

$$
\overline{I_{n,D1}^2}(\omega) = g_{m1}^2 \left[ \frac{\overline{V_{n,\text{REF}}^2}}{1 + \left(\dfrac{C_B \omega}{g_{m,\text{REF}}}\right)^2} + \overline{V_{n1}^2} \right] = g_{m1}^2 \overline{V_{n1,1/f}^2} \left[ \frac{K}{1 + \left(\dfrac{C_B \omega}{g_{m,\text{REF}}}\right)^2} + 1 \right]
$$

  Để nén đóng góp nhiễu của $M_{\text{REF}}$ xuống không đáng kể từ tần số góc $\omega$ trở lên, điều kiện (7.116)–(7.117) bắt buộc:

$$
\frac{K}{\left(C_B \omega / g_{m,\text{REF}}\right)^2} \ll 1 \iff C_B^2 \gg \frac{K g_{m,\text{REF}}^2}{\omega^2}
$$

  *Con số cảnh tỉnh từ Ví dụ số §7.5 (tr. 255, `NG07-07`):* Ngay cả ở tần số cao tới $f = 1\text{ MHz}$ với $K = 5$ và $\frac{1}{g_{m,\text{REF}}} = 200\,\Omega$, ta đã cần $C_B^2 \gg 2{,}533 \times 10^{-18}\text{ F}^2$; muốn nén nhiễu công suất của $M_{\text{REF}}$ đi $10$ lần phải dùng tụ **$C_B = \sqrt{10 \times 2{,}533 \times 10^{-18}} = 5{,}03\text{ nF}$** — lớn không tưởng đối với tích hợp trên chip (chiếm hàng $\text{mm}^2$ diện tích oxit)!
- **Giải pháp Chèn Điện trở Cô lập $R_B$ Giữa Cổng $M_{\text{REF}}$ và Cổng $M_1 + C_B$ (Hình 7.54, Phương trình 7.118):** Vì cổng $M_1$ không tiêu thụ dòng DC (ở tiến trình oxit dày), chèn $R_B \gg \frac{1}{g_{m,\text{REF}}}$ tách nút tụ $C_B$ khỏi trở kháng thấp của diode $M_{\text{REF}}$, biến đổi (7.114) thành Phương trình (7.118):

$$
\overline{I_{n,D1}^2}(\omega) = g_{m1}^2 \left[ \frac{\overline{V_{n,\text{REF}}^2} + 4 k T R_B}{1 + \left( \dfrac{1}{g_{m,\text{REF}}} + R_B \right)^2 C_B^2 \omega^2} + \overline{V_{n1}^2} \right]
$$

  Tần số cắt thông thấp hạ sâu xuống $f_c = \dfrac{1}{2\pi \left( g_{m,\text{REF}}^{-1} + R_B \right) C_B}$ (`NG07-08`), và tuyệt đẹp là chính mắt lọc $R_B C_B$ cũng tự lọc luôn cả nhiễu nhiệt $4kT R_B$ của chính $R_B$ trên dải tần $f \gg f_c$! Với $R_B = 500\text{ k}\Omega$ (hiện thực gọn nhẹ bằng MOSFET kênh hẹp dài hoạt động vùng triode như Hình 7.54b) và $C_B = 2\text{ pF}$, ta đạt ngay $f_c \approx 159\text{ kHz}$ chỉ với diện tích bằng $1/2500$ so với tụ $5\text{ nF}$!

### 2.2. Cặp Vi sai Tải Thụ động $R_D$ vs. Tải Chủ động 5T-OTA: Định luật $8kT\gamma$ (§7.6, Phương trình 7.119–7.142)
1. **Cặp vi sai tải điện trở đối xứng $R_{D1} = R_{D2} = R_D$ (Hình 7.56–7.57, Phương trình 7.119–7.126):**
   - *Phân tích dòng vật lý giải thích vì sao không có đất ảo (Hình 7.56b–d):* Xét riêng nguồn dòng nhiễu $I_{n1}$ nối giữa máng và nguồn của $M_1$ khi hai cổng nối tắt đất và đuôi $I_{SS}$ hở mạch xoay chiều ($\lambda = 0$). Nhìn từ cực nguồn $M_1$ sang cực nguồn $M_2$ thấy trở kháng $1/g_{m2} = 1/g_{m1}$, nên dòng chạy vòng qua $M_1\text{–}M_2$ đúng bằng $\frac{1}{2} I_{n1}$! Hệ quả: dòng đi xuống từ $R_{D1}$ là $+\frac{1}{2} I_{n1}$ và dòng đi xuống từ $R_{D2}$ là $-\frac{1}{2} I_{n1}$. Vì hai nhánh áp này sinh ra từ **cùng một nguồn $I_{n1}$ nên tương quan $100\%$**, điện áp vi sai ngõ ra cộng biên độ trực tiếp: $V_{n,\text{out}}\big|_{M1} = \frac{I_{n1}}{2} R_{D1} - \left(-\frac{I_{n1}}{2} R_{D2}\right) = I_{n1} R_D \implies \overline{V_{n,\text{out}}^2}\big|_{M1} = \overline{I_{n1}^2} R_D^2 = 4kT\gamma g_m R_D^2$ (Phương trình 7.119–7.120), và tương tự cho $M_2$ là $\overline{V_{n,\text{out}}^2}\big|_{M2} = 4kT\gamma g_m R_D^2$ (Phương trình 7.121–7.122)! Cộng công suất không tương quan của $M_1, M_2, R_{D1}, R_{D2}$ rồi chia cho bình phương độ lợi vi sai $(g_m R_D)^2$ (hoặc đặt ngay hai nguồn áp nhiễu nối tiếp tại hai cổng như Hình 7.57!), ta thu được **nhiễu nhiệt quy về ngõ vào (`T1139`)** và **nhiễu nhấp nháy quy về ngõ vào (`T1178`)** (Phương trình 7.125–7.126):

$$
\overline{V_{n,in,\text{diff-R}}^2} = 8 k T \left( \frac{\gamma}{g_m} + \frac{1}{g_m^2 R_D} \right) + \frac{2 K_N}{C_{ox} W L f}
$$

2. **Cặp vi sai tải nguồn dòng đối xứng vs. Tải chủ động gương dòng 5T-OTA (Ví dụ 7.22, Hình 7.59–7.61, Phương trình 7.133–7.142):**
   - *Với cặp vi sai vi sai hoàn toàn tải hai nguồn dòng PMOS $M_3\text{–}M_4$ (Ví dụ 7.22, Hình 7.59):* Dù tính chi tiết sự chia dòng của $M_3$ giữa $r_{O3}$ và trở kháng nhìn vào cực máng $M_1$ là $R_X = r_{O4} + 2 r_{O1}$ (Phương trình 7.133–7.136: $I_{nA} = I_{n3} \frac{r_{O4}+2r_{O1}}{2(r_{O3}+r_{O1})}$, $I_{nB} = I_{n3} \frac{r_{O3}}{2(r_{O3}+r_{O1})}$, hiệu $V_{nX} - V_{nY}$ khử sạch mẫu số trả lại đúng $I_{n3}(r_{O1} \parallel r_{O3})$!), hay phân tích đối xứng nửa mạch cho nguồn đơn $V_{n3}$ (Hình 7.60), kết quả nhiễu quy về ngõ vào là Phương trình (7.140).
   - *Với bộ khuếch đại 5T-OTA tải gương dòng bất đối xứng $M_3\text{–}M_4$ (Hình 7.61, Phương trình 7.141–7.142):* Nối tắt ngõ ra tìm dòng nhiễu ngắn mạch Norton $\overline{I_{n,\text{out,sc}}^2}$: dòng nhiễu của $M_3$ ($4kT\gamma g_{m3}$) chảy trọn qua trở kháng diode $1/g_{m3}$ tạo áp cổng $\frac{4kT\gamma}{g_{m3}}$ rồi được $M_4$ nhân lại với $g_{m4}^2 = g_{m3}^2$, trả lại đúng $4kT\gamma g_{m3}$ tại ngõ ra — cộng không tương quan với $4kT\gamma g_{m4}$ của chính $M_4$ thành $\overline{I_{n,\text{out,sc}}^2} = 4kT\gamma(g_{m1} + g_{m2} + g_{m3} + g_{m4}) = 8kT\gamma(g_{m1,2} + g_{m3,4})$ (Phương trình 7.141). Chia cho hỗ dẫn toàn mạch $G_m^2 = g_{m1,2}^2$, ta nhận được **cùng một công thức bất biến (Phương trình 7.140 & 7.142)** cho cả hai cấu trúc:

$$
\overline{V_{n,in,\text{diff/5T}}^2} = 8 k T \gamma \left( \frac{1}{g_{m1,2}} + \frac{g_{m3,4}}{g_{m1,2}^2} \right) + \frac{2 K_N}{C_{ox} (WL)_{1,2} f} + \frac{2 K_P}{C_{ox} (WL)_{3,4} f} \left( \frac{g_{m3,4}}{g_{m1,2}} \right)^2
$$

   - *Bảng So Sánh Công Bằng Giữa Cặp Vi Sai và Tầng CS Đơn:*
     * Nếu giữ **cùng kích thước và dòng mỗi nhánh** như CS đơn ($g_{m1,2} = g_{m,\text{CS}}$, tổng dòng đuôi $I_{SS} = 2 I_{D,\text{CS}}$): cặp vi sai tiêu thụ **gấp $2\times$ công suất** VÀ có công suất nhiễu quy về ngõ vào **lớn gấp $2\times$** ($\sqrt{2}\times$ điện áp hiệu dụng), đổi lại biên độ dao động ngõ ra vi sai cực đại tăng gấp $2\times$ ($4\times$ công suất tín hiệu đỉnh $\implies$ dải động cực đại DR tăng $+3\text{ dB}$!).
     * Nếu ràng buộc **cùng tổng ngân sách công suất $I_{\text{tot}}$** và cùng $V_{OV}$ ($I_{D1,2} = \frac{1}{2} I_{D,\text{CS}} \implies g_{m1,2} = \frac{1}{2} g_{m,\text{CS}}$): cặp vi sai có công suất nhiễu nhiệt quy về ngõ vào **lớn gấp $4\times$ ($+6\text{ dB}$, tức gấp $2\times$ điện áp nhiễu RMS)** so với tầng CS đơn!

### 2.3. Giải Phẫu 3 Cơ Chế Khiến Nhiễu Nguồn Dòng Đuôi $I_{n,SS}$ Phá Vỡ Đối Xứng (§7.6, Phương trình 7.129–7.132 & Hình 7.62)
1. **Cơ chế 1 — Điều chế Hỗ dẫn Khi Tín hiệu Vi sai Lớn $\Delta V_{in} \neq 0$ (Phương trình 7.129–7.132, tr. 259–260):** Khi có tín hiệu vi sai $\Delta V_{in}$ làm hai nhánh lệch khỏi cân bằng, tổng dòng đuôi tức thời là $I_{SS} + I_n$ (với $I_n \ll I_{SS}$). Trong vùng luật bình phương, hỗ dẫn tức thời bị dòng nhiễu đuôi điều chế biên độ:

$$
I_{D1} - I_{D2} = \frac{1}{2} \mu_n C_{ox} \frac{W}{L} \Delta V_{in} \sqrt{\frac{4(I_{SS} + I_n)}{\mu_n C_{ox}(W/L)} - \Delta V_{in}^2} \approx g_{m0} \left( 1 + \frac{I_n}{2 I_{SS}} \right) \Delta V_{in}
$$

   Số hạng tích chập phi tuyến $\Delta I_{\text{out,noise}} = g_{m0} \Delta V_{in} \frac{I_n}{2 I_{SS}}$ cho thấy: ngay khi cặp vi sai chuyển mạch (trong bộ trộn tần Gilbert mixer, bộ dao động VCO, hoặc Op-Amp đang slewing), **nhiễu nhấp nháy $1/f$ và nhiễu nhiệt của nguồn dòng đuôi $M_{SS}$ bị trộn tần trực tiếp lên tín hiệu vi sai**, biến thành nhiễu pha cận sóng mang ($1/f^3$ phase noise) hoặc nâng nền nhiễu trộn!
2. **Cơ chế 2 — Rò Nhiễu Đuôi Qua Biến Đổi Vi Sai sang Đơn Đầu của 5T-OTA ở Tần Số Thấp (Hình 7.62, tr. 262):** Trong 5T-OTA ngõ ra đơn đầu khi $V_{in1} = V_{in2}$, dòng nhiễu đuôi $I_n$ vẫn chia đều $\frac{1}{2} I_n$ vào $M_1$ và $M_2$. Nửa dòng $\frac{1}{2} I_n$ qua $M_1$ làm nút diode $X$ (cực cổng chung của gương $M_3\text{–}M_4$) dao động một lượng $\Delta V_X = -\frac{I_n}{2 g_{m3}}$. Để $M_4$ sao chép chính xác dòng của $M_3$ ($I_{D4} = I_{D2} = I_{D1} = I_{D3}$) khi cả hai có cùng $V_{SG3,4}$ và cùng $r_{O3,4}$, điều kiện đối xứng DC/tần số thấp buộc điện áp máng của $M_4$ phải bám theo điện áp máng $X$ của $M_3$: $\Delta V_{\text{out}} = \Delta V_X = -\frac{I_n}{2 g_{m3}} \implies \overline{V_{n,\text{out}}^2}\big|_{\text{tail,DC}} = \frac{\overline{I_{n,SS}^2}}{4 g_{m3}^2}$! (Quy về ngõ vào chia cho $A_v^2 = g_{m1}^2 (r_{O2} \parallel r_{O4})^2$ thì nhỏ nhờ $\text{CMRR}$ cao ở DC, nhưng khác $0$!).
3. **Cơ chế 3 — Lệch Pha Qua Cực Gương $\omega_m$ Ở Tần Số Cao Trong 5T-OTA:** Nửa dòng nhiễu đuôi $\frac{1}{2} I_{n,SS}$ đi qua nhánh phải $M_2$ tới ngõ ra tức thời, trong khi nửa dòng $\frac{1}{2} I_{n,SS}$ đi qua nhánh trái $M_1$ phải vòng qua gương dòng $M_3\text{–}M_4$ chịu trễ pha của cực gương $\omega_m \approx \frac{g_{m3}}{C_X}$ ($C_X \approx 2 C_{GS3,4} + C_{DB1} + C_{DB3}$)! Hiệu dòng nhiễu thoát ra ngõ ra đơn đầu là:

$$
I_{n,\text{out,tail}}(s) = \frac{I_{n,SS}}{2} \left( 1 - \frac{1}{1 + s / \omega_m} \right) = \frac{I_{n,SS}}{2} \cdot \frac{s / \omega_m}{1 + s / \omega_m} \implies \overline{I_{n,\text{out,tail}}^2}(\omega) = \frac{\overline{I_{n,SS}^2}}{4} \cdot \frac{(\omega / \omega_m)^2}{1 + (\omega / \omega_m)^2}
$$

   Khi $\omega \gtrsim \omega_m$, gương dòng $M_3\text{–}M_4$ không kịp phản chiếu nửa dòng bên trái để khử nửa dòng bên phải nữa, khiến **$\frac{1}{4}$ công suất dòng nhiễu của nguồn đuôi $M_{SS}$ đổ thẳng ra ngõ ra**!

---

## 3. Bất biến Cấu trúc & Các Bẫy Lỗi Kinh điển (Structural Invariants & Traps)

- **[INV-MIRR-DIFF-01] Định lý Điện trở Gia tăng Chủ động Luôn Ồn Hơn Điện trở Thụ động Cùng Giá trị (Ví dụ 7.21, Hình 7.58, Phương trình 7.127–7.128):**
  Khi dùng một cặp vi sai phân cực dòng siêu nhỏ làm "điện trở thả nổi" $R_{AB} = \frac{1}{g_{m1}} + \frac{1}{g_{m2}} = \frac{2}{g_{m1}}$ trên chip (Hình 7.58a, đi kèm các nguồn dòng phân cực trên/dưới có hỗ dẫn $g_{m,\text{bias}}$), điện áp nhiễu nhiệt giữa hai đầu $A, B$ là $\overline{V_{n,AB}^2} = 8 k T \gamma \left( \frac{1}{g_{m1}} + \frac{g_{m,\text{bias}}}{g_{m1}^2} \right) = 4 k T R_{AB} \cdot \gamma \left( 1 + \frac{g_{m,\text{bias}}}{g_{m1}} \right)$! So với điện trở поли/màng mỏng thụ động có nhiễu chuẩn Nyquist $4kT R_{AB}$, điện trở chủ động MOS luôn ồn hơn ít nhất thừa số $\gamma \left(1 + \frac{g_{m,\text{bias}}}{g_{m1}}\right) > 1$ (thường gấp $2\text{–}4$ lần công suất nhiễu!) đồng thời dải tuyến tính bị bó hẹp trong cỡ $\pm V_{OV1}$.
- **[TRAP-MIRR-DIFF-01] Bẫy Dòng Rò Xuyên Oxit Cổng Làm Lệch Phân Cực Khi Dùng $R_B$ Quá Lớn Ở 65nm / 45nm (Chú thích chân trang 12, tr. 256):**
  Trong công nghệ kênh dài ($0{,}5\,\mu\text{m}$ hay $180\text{ nm}$), oxit cổng dày $> 4\text{ nm}$ nên dòng rò cổng bằng $0$, cho phép dùng giả điện trở $R_B \sim 10\text{ M}\Omega\text{–}1\text{ G}\Omega$ trên đường phân cực gương dòng. Nhưng sang tiến trình **65nm / 45nm** dùng transistor chuẩn mỏng oxit (`thin-oxide core FET`, $t_{ox} \approx 1{,}2\text{–}1{,}8\text{ nm}$), mật độ dòng rò xuyên hầm trực tiếp qua oxit cổng $J_G$ lên tới hàng $\text{nA}/\mu\text{m}^2$! Nếu nhánh gương nuôi mảng lớn có tổng dòng rò cổng $I_{G,\text{leak}} = 20\text{ nA}$ chảy qua $R_B = 2\text{ M}\Omega$, sụt áp DC $I_{G,\text{leak}} R_B = 40\text{ mV}$ trên cực cổng có $g_m/I_D = 15\text{ V}^{-1}$ sẽ làm **sai lệch dòng phân cực tới $45\%\text{–}60\%$**! Ở $\le 65\text{ nm}$, bắt buộc giới hạn $R_B$ sao cho $I_{G,\text{leak,max}} R_B < 1\text{ mV}$, và dùng **tụ MIM / MOM kim loại** (tuyệt đối không dùng tụ MOS thin-oxide làm $C_B$ sau $R_B$ lớn!).
- **[TRAP-MIRR-DIFF-02] Nối Tụ Lọc Gương Dòng $C_B$ Sai Đường Nguồn Tham Chiếu Làm Sập PSRR:**
  Với gương dòng **PMOS** có cực nguồn nối lên $V_{DD}$, tụ lọc cổng $C_B$ **BẮT BUỘC phải nối giữa cực cổng $V_{bP}$ và $V_{DD}$** (KHÔNG ĐƯỢC nối xuống GND)! Nếu bạn nối $C_B$ từ cổng PMOS xuống GND, ở tần số cao $C_B$ ghim cứng $V_G = 0\text{ V}$ xoay chiều trong khi cực nguồn nhảy theo nhiễu nguồn $\Delta V_{DD}$, biến toàn bộ nhiễu nguồn $\Delta V_{DD}$ thành $\Delta V_{SG} = \Delta V_{DD}$ và bơm thẳng dòng nhiễu nguồn $g_{mP} \Delta V_{DD}$ vào mạch! Quy tắc bất di bất dịch: **gương NMOS nối $C_B$ xuống $V_{SS}$/GND; gương PMOS nối $C_B$ lên $V_{DD}$**!
- **[TRAP-MIRR-DIFF-03] Thiếu Thừa Số $1/f$ Trong Lời Văn Dẫn Tới Phương Trình (7.126) (`NG07-09`, tr. 258):**
  Câu văn ngay trước Phương trình (7.126) trong sách gốc in thiếu biến tần số $f$ khi viết giá trị nguồn áp cổng là $K/(C_{ox} W L)$; luôn nhớ đó là mật độ phổ công suất trên mỗi $\text{Hz}$ nên bắt buộc phải có mẫu số $f$, tức $\frac{K}{C_{ox} W L f}$ như trong chính Phương trình (7.126).

---

## 4. Lộ trình Nâng cấp Cấu trúc & Bát giác Đánh đổi (Upgrade Paths & Design Octagon)

| Điểm yếu nhiễu của Gương Dòng / Cặp Vi Sai | Nâng cấp sang cấu trúc đích (Canonical Node) | Hiệu quả cải thiện định lượng | Đánh đổi trên Bát giác Thiết kế |
|---|---|---|---|
| Nhánh chuẩn gương dòng nhân nhiễu theo $K^2$ khi dùng tỉ số nhân lớn $K = 10\text{–}20$ | Hạ tỉ số gương xuống $K \le 2\text{–}4$ kết hợp mắt lọc cổng $R_B C_B$ (Hình 7.54) và định cỡ $V_{OV,\text{mirr}}$ cao (`topo-lvccml-wide-swing-mirror`) | Cắt đứt nhiễu từ mạch Bandgap/`I_REF` và nhánh diode $M_{\text{REF}}$ trên toàn dải tần tín hiệu $f > f_c$ | Tốn thêm chút dòng tĩnh cho nhánh chuẩn và thời gian khởi động nạp tụ $R_B C_B$ lâu hơn ($\sim 5 R_B C_B$) |
| Nhiễu nguồn dòng đuôi $M_{SS}$ lọt ra ngõ ra đơn đầu 5T-OTA ở tần số cao do trễ pha cực gương $\omega_m$ | Chuyển sang cấu trúc vi sai hoàn toàn (`topo-telescopic-cascode-opamp`, `topo-folded-cascode-ota` kèm `tech-common-mode-feedback-cmfb`) | Hai nhánh trái–phải hoàn toàn đối xứng hình học ở mọi tần số, loại bỏ hoàn toàn cực gương $\omega_m$ và triệt sạch nhiễu đuôi chế độ chung | Phải thiết kế thêm mạch hồi tiếp chế độ chung (CMFB) và xử lý tín hiệu hai dây vi sai |
| Nhiễu $1/f$ của nguồn dòng đuôi $M_{SS}$ trộn tần thành nhiễu pha $1/f^3$ trong VCO LC chuyển mạch (`topo-lc-cross-coupled-and-colpitts`) | Mạch lọc nhiễu đuôi cộng hưởng ở $2\omega_0$ (Hegazi Tail-Noise LC Filter: tụ nối tắt lớn song song cuộn cảm cộng hưởng tại $2 f_0$) | Ngắn mạch nhiễu tần số thấp và tạo trở kháng cao tại hài bậc hai $2 f_0$ để giữ đối xứng chuyển mạch | Tăng diện tích silicon do thêm cuộn cảm lọc đuôi trên chip |
| Nhiễu nhấp nháy $1/f$ của cặp đầu vào $M_1\text{–}M_2$ và tải $M_3\text{–}M_4$ thống trị ở dải tần DC – kHz (cảm biến sinh học, đo lường) | Đổi sang cặp đầu vào PMOS (`topo-folded-cascode-ota`) kết hợp kỹ thuật tự triệt lệch / điều chế băm Chopper (`tech-dynamic-offset-cancellation-az-cds`) | Dời toàn bộ phổ nhiễu $1/f$ và điện áp lệch DC lên tần số băm $f_{\text{chop}}$ rồi lọc bỏ, chỉ còn lại nền nhiễu nhiệt trắng $8kT\gamma/g_{m1}$! | Xuất hiện gợn sóng tại tần số băm (chopper ripple) và cần xung nhịp điều khiển |

---

## 5. Thích ứng Đa Tiến trình (90nm / 65nm / 45nm) & Cách Kiểm chứng trong Cadence / Spectre

### 5.1. Bảng Định Cỡ Bất Đối Xứng Đầu Vào vs. Gương Tải & Lọc Phân Cực Ở 90nm / 65nm / 45nm
Trong 5T-OTA hay tầng đầu Op-Amp trên tiến trình nanomet, vì cặp đầu vào $M_{1,2}$ và cặp tải gương dòng $M_{3,4}$ mang **cùng dòng tĩnh mỗi nhánh $I_D = I_{SS}/2$**, tỉ số nhiễu nhiệt của tải so với cặp đầu vào bằng đúng tỉ số hiệu suất hỗ dẫn $\frac{(g_m/I_D)_{3,4}}{(g_m/I_D)_{1,2}}$:

| Khối Phần Tử trong Cặp Vi Sai & Mạng Phân Cực | Vùng Hoạt Động & $g_m/I_D$ ($\text{V}^{-1}$) | $V_{DS,\min}$ ($\text{mV}$) | Quy tắc Chọn $L$ & Tụ Lọc (90nm / 65nm / 45nm) | Mục Tiêu Ngân Sách Nhiễu Đạt Được |
|---|---|---|---|---|
| **Cặp vi sai đầu vào $M_1\text{–}M_2$** | Nghịch đảo yếu / vừa: $18 \text{ – } 24$ | $80 \text{ – } 110$ | $L_{1,2} = 2\text{–}4\,L_{\min}$, ưu tiên PMOS nếu băng tần $< 1\text{ MHz}$ | Chiếm $> 75\%$ ngân sách nhiễu nhiệt hữu ích, cực tiểu hóa $\frac{8kT\gamma}{g_{m1,2}}$ |
| **Tải chủ động gương dòng $M_3\text{–}M_4$** | Nghịch đảo mạnh: $5 \text{ – } 7$ | $220 \text{ – } 300$ | $L_{3,4} = 4\text{–}10\,L_{\min}$ (dài gấp $2\text{–}4\times L_{1,2}$!) | Ép $\frac{g_{m3,4}}{g_{m1,2}} \le 0{,}30$ (nhiễu nhiệt tải $< 30\%$) và $\left(\frac{g_{m3,4}}{g_{m1,2}}\right)^2 \le 0{,}09$ triệt sạch nhiễu $1/f$ tải! |
| **Nguồn dòng đuôi $M_{SS}$ & Nhánh chuẩn $M_{\text{REF}}$** | Nghịch đảo mạnh/vừa: $7 \text{ – } 11$ | $150 \text{ – } 220$ | $K \le 4$; lọc cổng $R_B \le 200\text{ k}\Omega$ (kiểm tra $I_{G,\text{leak}} R_B < 0{,}5\text{ mV}$) + tụ MOM $C_B \ge 2\text{ pF}$ về đúng rail nguồn! | Đẩy tần số cắt lọc nhiễu nhánh chuẩn $f_c < 400\text{ kHz}$ và giảm nhiễu đuôi trộn tần |

### 5.2. Quy trình Kiểm chứng trong Cadence Virtuoso / Spectre
Để bóc tách chính xác cả 3 hiện tượng (nhân nhiễu gương $K^2$, rò nhiễu đuôi qua cực gương $\omega_m$ trong 5T-OTA, và trộn nhiễu đuôi khi có $\Delta V_{in} \neq 0$), sử dụng kịch bản mô phỏng Spectre dưới đây:

```spectre
// === Kich ban Spectre: Kiem chung loc nhieu guong RB-CB & ro nhieu duoi M_SS ===
parameters K_mirr=8 R_filt=150k C_filt=4p Vin_diff=0

// 1. Phan tich Noise tuyen tinh tai Vin_diff = 0 va Vin_diff = 50mV (lech can bang!)
dc_op dc param=Vin_diff values=[0 50m]
ac_noise noise (vout_p vout_n) vsrc_diff start=10 stop=10G dec=30

// 2. Neu la 5T-OTA don dau: do Noise Summary tai 1 kHz va tai f ~ fm = gm3/(2*pi*CX)
// Xac nhan:
//   - Tai 1 kHz (Vin_diff=0): M_SS dong gop ~ 0%, M_REF bi RB*CB cat sach (< 0.5%)
//   - Tai f ~ fm (don dau) hoac khi Vin_diff = 50mV: dong gop cua M_SS tang vot!
//   - Kiem tra DC OP: abs(V(gate_Mref) - V(gate_Mtail)) < 0.5mV (khong bi sut ap dong ro cong!)
```

---

## 6. Mốc Đối chiếu Sách Razavi & Thuật ngữ Chuẩn CLB

### 6.1. Đối chiếu Sách Gốc Razavi (2nd Edition) & Chú giải Học thuật CLB
- **Chương 7:** §7.5 *Noise in Current Mirrors* (tr. 254–256: Hình 7.53–7.54, Phương trình 7.114–7.118, Chú thích chân trang 12 về dòng rò cực cổng qua $R_B$), §7.6 *Noise in Differential Pairs* (tr. 256–263: Hình 7.55–7.62, Phương trình 7.119–7.142, Ví dụ 7.21 về điện trở thả nổi chủ động, Ví dụ 7.22 về cặp vi sai tải nguồn dòng, và phân tích 5T-OTA tải gương dòng Hình 7.61–7.62).
- **Chú giải Hiệu đính Học thuật CLB (`source_issues.json` — Chương 07):**
  - **`NG07-07` (tr. 255, §7.5):** Trong ví dụ số tính tụ lọc gương dòng từ Phương trình (7.117) với $N = 5$, $g_{m,\text{REF}} \approx 1/(200\,\Omega)$ và $f = 1\text{ MHz}$, bản in gốc viết $C_B^2 \gg 2{,}533 \times 10^{-18}\text{ F}$; vì vế trái là bình phương điện dung $C_B^2$ nên đơn vị đúng phải là **$\text{F}^2$**, và giá trị tụ $C_B = 5{,}03\text{ nF}$ nêu ngay sau đó chính là $\sqrt{10 \times 2{,}533 \times 10^{-18}}\text{ F}$.
  - **`NG07-08` (tr. 256, Hình 7.54 & Phương trình 7.118):** Đoạn lời văn ngay dưới Hình 7.54 in dư chỉ số `"1"` trong ký hiệu $g_{m1,\text{REF}}$ (ký hiệu chuẩn trên Hình 7.54 và Phương trình 7.118 là $M_{\text{REF}}$ với hỗ dẫn $g_{m,\text{REF}}$), đồng thời biểu thức nghịch đảo hằng số thời gian $\left[(1/g_{m,\text{REF}} + R_B) C_B\right]^{-1}$ cho **tần số góc cắt $\omega_c$ tính bằng $\text{rad/s}$**, còn tần số cắt tính bằng $\text{Hz}$ là $f_c = \omega_c / (2\pi)$.
  - **`NG07-09` (tr. 258, trước Phương trình 7.126):** Câu dẫn trước (7.126) in thiếu thừa số $1/f$ trong biểu thức $K/(C_{ox} W L)$; mật độ phổ điện áp nhiễu nhấp nháy quy về cổng đúng phải là $\frac{K}{C_{ox} W L f}$ như được in chính xác ngay trong Phương trình (7.126).

### 6.2. Bảng Thuật ngữ Chuẩn CLB Vi Mạch Sử dụng trong Thẻ
| Mã CLB | Thuật ngữ Tiếng Anh | Thuật ngữ Tiếng Việt Chuẩn | Ghi chú Ngữ cảnh |
|---|---|---|---|
| `T012` | biasing | phân cực | Thiết lập điểm làm việc tĩnh nhưng dễ vô tình mở đường bơm nhiễu vào mạch |
| `T026` | current mirror | gương dòng | Nhân công suất nhiễu nguồn chuẩn theo $K^2$ và cộng thêm $4kT\gamma g_{m,\text{out}}(1+K)$ |
| `T233` | Bias current | dòng điện phân cực | Dòng tĩnh $I_{\text{REF}}, I_{SS}$ cần được lọc sạch nhiễu tần số cao trước khi cấp vào lõi |
| `T586` | differential pair | cặp vi sai | Có phương sai nhiễu quy về ngõ vào gấp $2\times$ tầng CS đơn ở cùng $g_m$ mỗi nhánh |
| `T512` | active load | tải chủ động | Cặp gương dòng $M_3\text{–}M_4$ trong 5T-OTA phải ép $g_{m3,4} \ll g_{m1,2}$ để không làm nổ nhiễu |
| `T392` | Flicker noise | nhiễu nhấp nháy | Nhánh diode $M_{\text{REF}}$ diện tích nhỏ sinh nhiễu $1/f$ gấp $K$ lần nhánh gương ra $M_1$ |
| `T1147` | gate-referred noise voltage | điện áp nhiễu quy về cực cổng | Cho phép tính nhanh nhiễu cặp vi sai bằng 2 nguồn áp mắc nối tiếp ở 2 cực cổng |
| `T1139` | input-referred thermal noise | nhiễu nhiệt quy về ngõ vào | Đạt $8kT\gamma\left(\frac{1}{g_{m1,2}} + \frac{g_{m3,4}}{g_{m1,2}^2}\right)$ cho cả vi sai đối xứng lẫn 5T-OTA |
| `T1178` | input-referred flicker noise | nhiễu nhấp nháy quy về ngõ vào | Bị nén mạnh bởi tỉ số bình phương $\left(g_{m3,4}/g_{m1,2}\right)^2$ và chiều dài kênh $L_{3,4}$ lớn |
