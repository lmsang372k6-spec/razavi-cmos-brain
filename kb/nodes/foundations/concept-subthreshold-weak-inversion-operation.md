---
{
  "id": "concept-subthreshold-weak-inversion-operation",
  "kind": "concept",
  "domain": "foundations",
  "title_vi": "Dẫn Dưới ngưỡng & Vùng Nghịch đảo Yếu của MOSFET: Đặc tuyến Hàm mũ, Cực đại Hiệu suất gm/ID và Cái giá Tốc độ fT (Subthreshold & Weak-Inversion Operation)",
  "title_en": "MOSFET Subthreshold Conduction, Weak-Inversion Exponential Characteristics, and gm/ID vs. fT Trade-Off",
  "summary": "Giải phẫu vật lý dòng khuếch tán dưới ngưỡng ID = I0*exp(VGS / (zeta*VT)), hệ số không lý tưởng bộ chia áp tụ cổng–nghèo zeta = 1 + Cdep/Cox, độ dốc dưới ngưỡng S ~ 80-100 mV/dec, trần hiệu suất hỗ dẫn cực đại gm/ID = 1/(zeta*VT) ~ 25-32 V^-1 so với BJT, quy tắc giao cắt nghịch đảo mạnh–yếu và cái giá sụp đổ tần số chuyển tiếp fT trong vi mạch công suất siêu thấp.",
  "diagram": "../../diagrams/short-channel-iv-gmid.svg",
  "razavi_refs": [
    {
      "chapter": 2,
      "section": "2.3",
      "pages": "24-26",
      "equations": ["2.32", "2.33", "2.34", "2.35", "2.36", "2.37", "2.38", "2.39"]
    },
    {
      "chapter": 2,
      "section": "2.5",
      "pages": "36-37",
      "equations": []
    },
    {
      "chapter": 11,
      "section": "11.2-11.3, 11.6.5",
      "pages": "460-467, 505-507",
      "equations": ["11.5", "11.6"]
    }
  ],
  "glossary_codes": ["T091", "T183", "T270", "T271", "T273", "T276", "T278", "T283", "T434"],
  "process_agnostic": true,
  "roles": {
    "capacitive_gate_divider_zeta": "Bộ chia điện áp tụ nối tiếp Cox và Cdep làm thế bề mặt phi_s chỉ nhận được phân số 1/zeta của biến thiên điện áp cổng VGS, sinh ra hệ số không lý tưởng zeta > 1",
    "diffusion_dominated_channel": "Khi VGS < VTH, điện trường dọc kênh yếu và dòng máng chuyển sang cơ chế khuếch tán hạt tải vượt rào thế nguồn–kênh tương tự cực phát–cực nền của BJT",
    "max_gm_over_id_transconductor": "Chế độ phân cực tối ưu hóa hỗ dẫn gm trên mỗi micro-ampe dòng tiêu thụ cho cặp vi sai đầu vào băng thông vừa/thấp và mạch y sinh năng lượng cực nhỏ"
  },
  "symptoms_addressed": [
    "square-law-predicting-infinite-gm-as-width-grows",
    "unexpected-milliamps-off-state-leakage-in-large-arrays",
    "subthreshold-pair-missing-unity-gain-bandwidth-target",
    "exponential-threshold-mismatch-sensitivity-in-weak-inversion-mirrors"
  ],
  "limitations": [
    "transit-frequency-ft-collapses-by-one-to-two-orders-of-magnitude",
    "gm-over-id-saturates-below-bjt-limit-due-to-zeta-greater-than-one",
    "drain-current-becomes-exponentially-sensitive-to-vth-pelgrom-mismatch",
    "high-temperature-degrades-subthreshold-slope-and-explodes-off-leakage"
  ],
  "checklists": ["common-mos"]
}
---

## 1. Bản chất Nguyên lý, Sơ đồ Mạch & Vai trò Từng Nhánh Cấu trúc

Trong mô hình bậc nhất quy luật bình phương của `concept-mos-operating-regions`, ta từng giả thiết một ranh giới bật–tắt đột ngột: khi $V_{GS} < V_{TH}$, mật độ điện tích nghịch đảo bằng không tuyệt đối và transistor tắt hoàn toàn ($I_D = 0$). Trên thực tế vật lý bán dẫn (Razavi Chương 2, §2.3 *Subthreshold Conduction*, tr. 24–26, Hình 2.28), ngay cả khi $V_{GS}$ nằm thấp hơn $V_{TH}$ vài trăm milivôn, bề mặt silic dưới lớp oxit cổng đã ở trạng thái **nghịch đảo yếu (`T271`, weak inversion)**: nồng độ electron tự do tại mặt phân cách tuy nhỏ hơn nồng độ tạp chất nền $N_{\text{sub}}$ nhưng khác không và tuân theo phân bố thống kê Boltzmann theo thế bề mặt $\psi_s$. Hiện tượng tồn tại **dòng điện dưới ngưỡng (`T273`, subthreshold current)** hữu hạn này được gọi là **sự dẫn dưới ngưỡng (`T270`, subthreshold conduction)**.

![Đặc tuyến chuyển tiếp từ vùng nghịch đảo yếu hàm mũ sang vùng nghịch đảo mạnh và đường cong hiệu suất gm/ID](../../diagrams/short-channel-iv-gmid.svg)

Để hiểu thấu đáo vì sao MOSFET dưới ngưỡng mang dáng dấp hàm mũ giống transistor lưỡng cực BJT nhưng luôn "kém sắc" hơn BJT một hệ số $\zeta > 1$ (trong bản in sách gốc Razavi 2nd Ed. ký hiệu là $\xi$, còn nhiều tài liệu CMOS gọi là $n$ hoặc $\zeta$), cần bóc tách hai cơ chế vật lý nối tiếp nhau từ cực cổng xuống kênh dẫn:
1. **Cơ chế vận chuyển bằng khuếch tán vượt rào thế (Diffusion over Source–Channel Barrier):** Khi $V_{GS} < V_{TH}$, mật độ hạt tải dọc kênh quá thưa để tạo ra độ sụt thế trôi (drift) đáng kể; thế bề mặt $\psi_s$ gần như phẳng dọc chiều dài kênh. Cực nguồn $n^+$, vùng kênh nghèo $p$ dưới cổng và cực máng $n^+$ lập thành một cấu trúc $n^+\text{–}p\text{–}n^+$ tương tự BJT vùng tích cực! Khi tăng thế bề mặt $\Delta\psi_s$, chiều cao rào thế tiếp giáp nguồn–kênh hạ xuống đúng $\Delta\psi_s$, khiến nồng độ electron tiêm từ nguồn vào đầu kênh tăng vọt theo hàm mũ Boltzmann $\propto \exp\left(\frac{\Delta\psi_s}{V_T}\right)$, với **điện áp nhiệt (`T276`, thermal voltage)** $V_T = \frac{kT}{q} \approx 25{,}85\,\text{mV}$ tại $T = 300\,\text{K}$. Hạt tải sau đó khuếch tán theo gradien nồng độ từ cực nguồn sang cực máng.
2. **Bộ chia áp điện dung Cổng – Vùng nghèo ($\zeta > 1$):** Khác với BJT nơi tín hiệu $V_{BE}$ đặt trực tiếp lên tiếp giáp phát–nền, ở MOSFET cực cổng bị cách ly bởi lớp oxit cổng $C_{ox}$ mắc nối tiếp với điện dung vùng nghèo đế bán dẫn $C_{\text{dep}} = \sqrt{\frac{q \epsilon_{\text{si}} N_{\text{sub}}}{4\Phi_F}}$ nằm bên dưới mặt phân cách oxit–silic! Do đó, khi tăng điện áp cổng thêm $\Delta V_{GS}$, thế bề mặt kênh chỉ nhận được phần chia áp điện dung:
   $$\Delta\psi_s = \Delta V_{GS} \cdot \frac{C_{ox}}{C_{ox} + C_{\text{dep}}} = \frac{\Delta V_{GS}}{\zeta}, \qquad \zeta \triangleq 1 + \frac{C_{\text{dep}}}{C_{ox}} > 1$$
   Trên công nghệ CMOS phẳng điển hình, tỉ số $C_{\text{dep}}/C_{ox} \approx 0{,}25\text{–}0{,}6$, kéo hệ số không lý tưởng $\zeta \approx 1{,}25\text{–}1{,}6$ (Razavi thường lấy giá trị tiêu biểu $\zeta \approx 1{,}3\text{–}1{,}5$). Chỉ khi chuyển sang cấu trúc **FinFET** bao bọc cổng ba mặt trên vây silic cực mỏng (§2.5 *Appendix A: FinFETs*, tr. 36–37), cực cổng mới kiểm soát tĩnh điện hoàn toàn kênh dẫn ($C_{\text{dep}} \ll C_{ox}$), đưa $\zeta \to 1{,}05\text{–}1{,}15$ tiến sát giới hạn nhiệt động lực học lý tưởng!

---

## 2. Hệ Phương trình Cốt lõi & Tư duy "Nhìn Mạch Đọc Nhanh" (Analysis by Inspection)

### 2.1. Phương trình Dòng Dưới ngưỡng Đầy đủ & Điều kiện Bão hòa Chỉ Cần $3\,V_T$!
Gộp cả sự phụ thuộc tỉ lệ hình học $W/L$ và hiệu thế máng–nguồn $V_{DS}$ trong cơ chế khuếch tán hạt tải, dòng cực máng dưới ngưỡng (khi $V_{GS} < V_{TH}$) tuân theo phương trình chuẩn (tổng quát từ Phương trình 2.33, tr. 24–26):

$$I_D = I_0 \exp\!\left(\frac{V_{GS}}{\zeta V_T}\right)\left[1 - \exp\!\left(-\frac{V_{DS}}{V_T}\right)\right] = I_{D0} \frac{W}{L} \exp\!\left(\frac{V_{GS} - V_{TH}}{\zeta V_T}\right)\left[1 - \exp\!\left(-\frac{V_{DS}}{V_T}\right)\right]$$

trong đó $I_0 = \alpha \frac{W}{L}$ với hằng số dòng $\alpha = I_{D0}\exp\!\left(-\frac{V_{TH}}{\zeta V_T}\right)$ (đơn vị $\text{A}$, khớp nguyên văn Phương trình 2.37: $I_D = \alpha \frac{W}{L}\exp\!\left(\frac{V_{GS}}{\zeta V_T}\right)$ khi $V_{DS} \gtrsim 4 V_T$), còn $I_{D0} = \mu C_{ox}(\zeta - 1)V_T^2$ là dòng đặc trưng quy chiếu tại $V_{GS} = V_{TH}$. Hai hệ quả cực kỳ quan trọng nhảy ra ngay khi nhìn bằng mắt (inspection):
1. **Điện áp bão hòa tối thiểu $V_{DS,\min}$ không phụ thuộc $W/L$ và nhỏ kỷ lục ($\sim 3\text{–}4\,V_T$):**
   Trong vùng nghịch đảo mạnh, $V_{DS,\text{sat}} = V_{GS} - V_{TH}$ có thể chiếm $150\text{–}300\,\text{mV}$. Ngược lại, trong vùng dưới ngưỡng, thừa số $\left[1 - \exp(-V_{DS}/V_T)\right]$ tiến tới $0{,}95$ ngay khi $V_{DS} = 3 V_T \approx 78\,\text{mV}$ và đạt $0{,}982$ tại $V_{DS} = 4 V_T \approx 104\,\text{mV}$! Một khi $V_{DS} \gtrsim 4 V_T \approx 100\,\text{mV}$, nồng độ hạt tải tại đầu máng đã tụt về gần không nên gradien khuếch tán đạt cực đại và phương trình rút gọn đúng thành Phương trình (2.33) của Razavi:
   $$I_D \approx I_0 \exp\!\left(\frac{V_{GS}}{\zeta V_T}\right) \quad (\text{khi } V_{DS} \gtrsim 4 V_T \approx 100\,\text{mV}, \text{ bỏ qua điều biến kênh})$$
2. **Độ dốc dưới ngưỡng (`T278`, subthreshold slope — $S$):**
   Lấy logarit thập phân hai vế của (2.33) để tìm lượng điện áp $V_{GS}$ cần giảm nhằm cắt dòng rò đi đúng $10$ lần ($1\text{ decade}$, §2.3, Hình 2.28, tr. 24–25):
   $$\frac{I_{D1}}{I_{D2}} = 10 \quad \Longleftrightarrow \quad S \triangleq \left(\frac{\partial \log_{10} I_D}{\partial V_{GS}}\right)^{-1} = \zeta V_T \ln 10 \approx 2{,}3026\,\zeta V_T$$
   - Ở giới hạn lý tưởng tuyệt đối $\zeta = 1$ tại $T = 300\,\text{K}$: $S_{\min} = (25{,}85\,\text{mV})\times \ln 10 \approx 59{,}5\,\text{mV/decade}$ (mốc kinh điển $60\,\text{mV/dec}$).
   - Với CMOS phẳng thực tế $\zeta \approx 1{,}35\text{–}1{,}55$: $S \approx 80\text{–}95\,\text{mV/decade}$ ở nhiệt độ phòng, và **tồi đi tuyến tính theo nhiệt độ tuyệt đối $T$** (lên tới $105\text{–}125\,\text{mV/dec}$ tại $125\,^\circ\text{C}$!).

### 2.2. Bài toán Minh họa Kinh điển của Razavi (§2.3, Hình 2.28, tr. 24–25 — Thảm họa Dòng Rò Tĩnh $18\,\text{mA}$)
Xét một vi mạch cỡ lớn chứa $N = 100\times 10^6$ transistor có điện áp ngưỡng thấp $V_{TH} = 0{,}3\,\text{V}$ và độ dốc dưới ngưỡng $S = 80\,\text{mV/dec}$ (ứng với $\zeta \approx 1{,}34$). Giả sử tại ranh giới $V_{GS} = V_{TH} = 0{,}3\,\text{V}$, mỗi transistor mang dòng $I_D(V_{TH}) = 1\,\mu\text{A}$. Khi tắt hoàn toàn cổng xuống $V_{GS} = 0\,\text{V}$, hiệu áp lùi dưới ngưỡng chỉ được $\Delta V_{GS} = 300\,\text{mV} = 3{,}75 \times (80\,\text{mV/dec})$, tức dòng rò mỗi transistor chỉ giảm được $10^{3{,}75} \approx 5{,}62 \times 10^3$ lần:
$$I_{\text{off,1-FET}} = 1\,\mu\text{A} \times 10^{-0{,}30 / 0{,}08} = 1\,\mu\text{A} \times 10^{-3{,}75} \approx 178\,\text{pA}$$
Con số $178\,\text{pA}$ nghe có vẻ vô hại trên một linh kiện đơn lẻ, nhưng nhân trên $100$ triệu transistor đang ở trạng thái tắt ($V_{GS} = 0$):
$$I_{\text{leak,total}} = 100 \times 10^6 \times 178\,\text{pA} \approx 17{,}8\,\text{mA} \approx 18\,\text{mA}$$
(đúng con số **$18\,\text{mA}$ dòng rò tĩnh rút cạn pin** được Razavi cảnh báo ở tr. 25 dù toàn chip đang ở trạng thái chờ!). Đó là lý do các tiến trình $90\text{nm}/65\text{nm}/45\text{nm}$ không thể hạ $V_{TH}$ tùy ý xuống $0{,}15\,\text{V}$ khi hạ $V_{DD}$, mà buộc phải cung cấp họ linh kiện ngưỡng cao `HVT` cho các khối nhạy rò!

### 2.3. Nghịch lý Mở Rộng $W \to \infty$, Trần Hiệu suất $(g_m / I_D)_{\max}$ & Tần số $f_T$
Một câu hỏi nền tảng mà Razavi đặt ra ở cuối §2.3 (tr. 25–26): *Theo công thức quy luật bình phương $g_m = \sqrt{2\mu_n C_{ox}\frac{W}{L} I_D}$ (Phương trình 2.19), nếu ta giữ dòng phân cực $I_D$ không đổi và tăng chiều rộng $W$ lên lớn tùy ý, liệu $g_m$ có tăng lên vô hạn và vượt qua cả BJT ($g_{m,\text{BJT}} = I_C / V_T$) hay không?*
- **Câu trả lời vật lý dứt khoát là KHÔNG!** Khi $I_D$ giữ cố định mà tăng $W$ mãi, mật độ dòng $I_D / (W/L)$ sụt giảm làm $V_{GS}$ lùi về sát rồi tụt xuống dưới $V_{TH}$, đẩy transistor rời khỏi vùng nghịch đảo mạnh để rơi vào vùng nghịch đảo yếu!
- Lấy đạo hàm Phương trình (2.33) theo $V_{GS}$, **độ hỗ dẫn trong vùng dưới ngưỡng (`T283`, subthreshold transconductance)** bằng:
  $$g_{m,\text{sub}} = \frac{\partial I_D}{\partial V_{GS}} = \frac{I_D}{\zeta V_T} \quad \Longrightarrow \quad \left(\frac{g_m}{I_D}\right)_{\max} = \frac{1}{\zeta V_T} < \frac{1}{V_T} = \left(\frac{g_m}{I_C}\right)_{\text{BJT}}$$
  Tại $T = 300\,\text{K}$ với $\zeta \approx 1{,}3\text{–}1{,}5$, trần hiệu suất hỗ dẫn cực đại của MOSFET bão hòa ở mức **$(g_m/I_D)_{\max} \approx 25\text{–}30\,\text{V}^{-1}$** (thấp hơn mức $38{,}7\,\text{V}^{-1}$ của BJT), và hoàn toàn **không còn phụ thuộc vào $W/L$ hay $\mu_n C_{ox}$ nữa**! Một khi đã lọt sâu vào vùng dưới ngưỡng, tăng gấp đôi $W$ ở cùng dòng $I_D$ **không tăng thêm một phần trăm $g_m$ nào**, mà chỉ làm giảm $V_{GS}$ đi $\zeta V_T \ln 2 \approx 24\,\text{mV}$ và nhân đôi toàn bộ tụ ký sinh cổng!

### 2.4. Quy tắc Chuyển giao Nghịch đảo Mạnh – Yếu (Phương trình 2.38–2.39) & Cái giá Tốc độ $f_T$
Khi giải bài toán tìm $V_{GS}$ tại dòng $I_D$ và tỉ số $W/L$ cho trước, Razavi nêu quy tắc thực hành sắc bén (Phương trình 2.38–2.39, tr. 26): tính $V_{GS}$ theo cả hai công thức — nghịch đảo mạnh (2.38) và nghịch đảo yếu (2.39) — rồi **chọn giá trị nhỏ hơn** (vì ở mật độ dòng thấp, cơ chế dưới ngưỡng đã cung cấp đủ dòng $I_D$ trước khi $V_{GS}$ kịp vươn tới giá trị đòi hỏi bởi luật bình phương):

$$V_{GS,\text{SI}} = V_{TH} + \sqrt{\frac{2 I_D}{\mu_n C_{ox}(W/L)}} \quad (2.38), \qquad V_{GS,\text{WI}} = \zeta V_T \ln\!\left(\frac{I_D}{\alpha (W/L)}\right) = V_{TH} + \zeta V_T \ln\!\left(\frac{I_D}{I_{D0}(W/L)}\right) \quad (2.39)$$

Điểm giao thoa chuyển tiếp (vùng **nghịch đảo vừa — moderate inversion**) xảy ra quanh điện áp vượt ngưỡng biểu kiến $V_{OV,\text{trans}} = 2\zeta V_T \approx 70\text{–}80\,\text{mV}$ (ứng với $g_m/I_D \approx 15\text{–}20\,\text{V}^{-1}$), nơi cả đạo hàm $I_D$ lẫn $g_m/I_D$ nối trơn liên tục giữa hai tiệm cận:
$$\frac{g_m}{I_D} \approx \frac{2}{V_{OV}} \quad (\text{Strong Inversion, } V_{OV} \gg 2\zeta V_T) \qquad \longleftrightarrow \qquad \frac{g_m}{I_D} = \frac{1}{\zeta V_T} \quad (\text{Weak Inversion})$$

**Cái giá khốc liệt về tần số chuyển tiếp (`T434`, transit frequency — $f_T$):** Trong vùng dưới ngưỡng, điện dung cổng tổng cộng nhìn từ cực cổng là $C_{gg,\text{WI}} \approx W L (C_{ox} \parallel C_{\text{dep}}) + 2 W C_{ov}$. Vì dòng $I_D \propto \frac{W}{L}\mu_n C_{ox} V_T^2 \exp\!\left(\frac{V_{GS}-V_{TH}}{\zeta V_T}\right)$, tần số chuyển tiếp nội tại $f_T = \frac{g_m}{2\pi C_{gg}}$ sụt giảm theo hàm mũ khi đi sâu xuống dưới ngưỡng:
$$f_{T,\text{WI}} \approx \frac{I_D / (\zeta V_T)}{2\pi W L C_{gg}'} \propto \frac{\mu_n V_T}{2\pi L^2} \exp\!\left(\frac{V_{GS} - V_{TH}}{\zeta V_T}\right)$$
Nếu ở nghịch đảo mạnh trên tiến trình $65\,\text{nm}$ transistor đạt $f_T \approx 80\text{–}150\,\text{GHz}$, thì khi dìm xuống vùng nghịch đảo yếu sâu ($g_m/I_D \approx 26\,\text{V}^{-1}$), $f_T$ lao dốc xuống chỉ còn **$0{,}3\text{–}3\,\text{GHz}$** (tụt $30\text{–}100$ lần)!

---

## 3. Bất biến Cấu trúc & Các Bẫy Lỗi Kinh điển (Structural Invariants & Traps)

- **[INV-SUB-01] Bất biến Trần Hiệu suất Hỗ dẫn và Tính Bất biến Độ lợi Nội tại:** Trong vùng nghịch đảo yếu với $V_{DS} \ge 4 V_T$, tỉ số $g_m / I_D = \frac{1}{\zeta V_T}$ là hằng số vật lý chỉ phụ thuộc nhiệt độ và tỷ số tụ $C_{\text{dep}}/C_{ox}$. Nhờ $r_O = \frac{1}{\lambda I_D}$ cũng tỉ lệ nghịch với $I_D$, **độ lợi nội tại $g_m r_O = \frac{1}{\zeta \lambda V_T}$ đạt giá trị cực đại trên toàn dải hoạt động của MOSFET** và hầu như giữ phẳng ngay cả khi hạ dòng xuống hàng nano-ampe!
- **[INV-SUB-02] Bất biến Độ rộng Tuyến tính Vi sai Cố định $\sim 2\zeta V_T$:** Một cặp vi sai phân cực trong vùng dưới ngưỡng có đặc tuyến chuyển mạch dòng dạng hàm $\tanh\!\left(\frac{\Delta V_{in}}{2\zeta V_T}\right)$ y hệt cặp vi sai BJT, nên dải tuyến tính đầu vào khóa cứng ở mức $\pm 2\zeta V_T \approx \pm 70\,\text{mV}$ độc lập với dòng đuôi $I_{SS}$ và $W/L$!

- **[TRAP-SUB-01] Bẫy Nổ Sai lệch Dòng (Current Mismatch Explosion) Khi Đặt Gương Dòng Vào Vùng Dưới Ngưỡng:**
  Đây là lỗi chí tử phổ biến nhất khi thiết kế mạch công suất thấp! Xét hai transistor gương dòng có độ lệch điện áp ngưỡng Pelgrom $\Delta V_{TH}$ (`law-pelgrom-mismatch-and-sizing-duality`). Sai số dòng tương đối là $\frac{\Delta I_D}{I_D} = \frac{g_m}{I_D} \Delta V_{TH}$. Trong vùng dưới ngưỡng, $g_m / I_D = \frac{1}{\zeta V_T} \approx 28\,\text{V}^{-1}$ đạt cực đại! Chỉ một sai lệch nhỏ $\Delta V_{TH} = 5\,\text{mV}$ đã gây sai số dòng $\frac{\Delta I_D}{I_D} \approx 28 \times 0{,}005 = 14\%$ (và với $\Delta V_{TH} = 15\,\text{mV}$, dòng lệch theo hàm mũ $\exp(15/35) - 1 = +53\%$!). **Quy tắc sắt đá:** Cặp vi sai đầu vào *được phép và rất nên* đặt ở nghịch đảo vừa/yếu (vì offset áp đầu vào $\sigma(V_{OS}) \approx \sigma(\Delta V_{TH})$ nhỏ nhất!), nhưng **gương dòng và nguồn dòng phân cực tuyệt đối KHÔNG đặt ở vùng dưới ngưỡng** (trừ khi có điện trở suy biến nguồn $I_D R_S \gg \zeta V_T$)!
- **[TRAP-SUB-02] Bẫy "Béo Phì Điện dung" Vô Ích Khi Tăng $W$ Quá Đà:** Khi đã chạm bình nguyên $g_m/I_D \approx 26\text{–}28\,\text{V}^{-1}$, tiếp tục mở rộng $W$ để mong tăng $\text{GBW} = \frac{g_{m1}}{2\pi C_L}$ là hoàn toàn vô tác dụng (vì $g_{m1}$ đã bão hòa theo $I_D$), ngược lại còn bơm thêm hàng trăm femto-farad $C_{GS}, C_{DB}$ làm sập cực không trội và giết chết dự trữ pha PM!
- **[TRAP-SUB-03] Bẫy Đảo Dấu Hệ số Nhiệt độ & Rò Nóng $125\,^\circ\text{C}$:** Ở nghịch đảo mạnh (mật độ dòng lớn), $I_D$ giảm khi nhiệt độ tăng (do $\mu(T) \propto T^{-1{,}5}$ thắng sự giảm $V_{TH}(T)$). Nhưng ở vùng dưới ngưỡng, sự sụt giảm $|V_{TH}(T)|$ ($\sim -1\text{ đến }-1{,}8\,\text{mV/K}$) cộng hưởng với đuôi mũ Boltzmann khiến $I_D$ tại $V_{GS}$ cố định **tăng vọt gấp $10\text{–}30$ lần** từ $-40\,^\circ\text{C}$ lên $+125\,^\circ\text{C}$ (`concept-process-corners-and-temperature`)! Nếu phân cực bằng áp cố định thay vì gương dòng PTAT/Constant-$g_m$, mạch sẽ cháy ngân sách công suất ở góc `FF, 125°C`.

---

## 4. Lộ trình Nâng cấp Cấu trúc & Bát giác Đánh đổi (Upgrade Paths & Design Octagon)

Trên **Bát giác Thiết kế Mạch Tương tự** (`concept-analog-design-octagon`), việc dịch chuyển điểm làm việc từ Nghịch đảo mạnh ($g_m/I_D \approx 6\text{–}10\,\text{V}^{-1}$) sang Nghịch đảo vừa ($14\text{–}18\,\text{V}^{-1}$) và Nghịch đảo yếu ($22\text{–}28\,\text{V}^{-1}$) thực hiện một cuộc hoán đổi đa trục rõ rệt:
- **Trục thắng lớn (Power, Noise, Gain, Voltage Swing):**
  - Tại cùng chỉ tiêu nhiễu nhiệt $\overline{V_{n,in}^2} = \frac{4kT\gamma}{g_m}$ (`law-mos-thermal-and-flicker-noise`) hoặc cùng $\text{GBW} = \frac{g_{m1}}{2\pi C_L}$, đẩy cặp vi sai đầu vào lên vùng nghịch đảo yếu giúp **cắt giảm dòng tiêu thụ $I_D$ đi $2{,}5\text{–}4$ lần**!
  - Khoảng dự trữ bão hòa sụt xuống $V_{DS,\min} \approx 4 V_T \approx 100\,\text{mV}$, mở toang dải dao động điện áp dưới nguồn $0{,}8\text{–}1{,}0\,\text{V}$ (xem thiết kế Op-Amp công suất thấp Ví dụ 11.16 của Razavi dùng cascode vùng dưới ngưỡng, Chương 11 tr. 505–507, `tech-channel-length-and-opamp-scaling`).
- **Trục trả giá & Lộ trình nâng cấp:**
  - **Sập tốc độ $f_T$ & Slew Rate $\text{SR} = I_{SS}/C_L$:** Vì $I_{SS} = \frac{g_{m1}}{(g_m/I_D)_1}$ trở nên rất nhỏ khi $g_m/I_D$ cao, tốc độ biến thiên biên độ lớn $\text{SR}$ bị thắt cổ chai (`law-slewing-vs-linear-settling-time-budget`) $\rightarrow$ nâng cấp sang cặp đầu vào **Class-AB** (`tech-slew-rate-and-class-ab-opamps`) để tách dòng slewing động khỏi dòng tĩnh nhỏ!
  - **Hẹp dải tuyến tính $\pm 2\zeta V_T$:** Khi cần xử lý tín hiệu vi sai hàng trăm mV mà vẫn tiết kiệm dòng $\rightarrow$ dùng suy biến nguồn `topo-diff-pair-with-degeneration-and-triode-loads`.
  - **Quy trình định cỡ liền mạch qua cả 3 vùng:** Bỏ hẳn công thức rời rạc từng mảnh để dùng đường cong chuẩn hóa $g_m/I_D$ kết hợp mật độ dòng $I_D/(W/L)$ tại `tech-nanometer-vdsmin-gmid-sizing`.

---

## 5. Thích ứng Đa Tiến trình (90nm / 65nm / 45nm) & Cách Kiểm chứng trong Cadence / Spectre

### 5.1. Điểm Ngọt "Nghịch đảo Vừa" (Moderate Inversion Sweet Spot) Trên 90nm / 65nm / 45nm
Ở các tiến trình công nghiệp **90nm, 65nm và 45nm**, hiệu ứng DIBL (làm hạ rào thế kênh khi tăng $V_{DS}$, xem `law-short-channel-effects`) làm xấu thêm độ dốc dưới ngưỡng $S$ ở kênh ngắn $L_{\min}$ (có thể vọt lên $100\text{–}115\,\text{mV/dec}$). Do đó:
1. **Không bao giờ dùng $L = L_{\min}$ cho transistor analog chạy dưới ngưỡng:** Chọn $L \ge (2\text{–}4)L_{\min}$ (ví dụ $L = 150\text{–}250\,\text{nm}$ ở công nghệ 65nm) để khôi phục kiểm soát tĩnh điện cổng, giữ $\zeta \approx 1{,}35$ và nâng $g_m r_O$ lên $> 25$.
2. **Chiến lược phân bổ vùng nghịch đảo tối ưu toàn cục trên một Op-Amp nanomet:**

| Vai trò linh kiện trong mạch | Vùng vận hành tối ưu | Mục tiêu $g_m/I_D$ ($\text{V}^{-1}$) | Mật độ dòng $I_D/W$ điển hình (65nm) | Lý do vật lý quyết định |
|---|---|---|---|---|
| **Cặp vi sai đầu vào băng thông cực thấp / y sinh / Bandgap OTA** | Nghịch đảo yếu (Weak Inversion, `region = 3`) | $22 \text{–} 27\,\text{V}^{-1}$ | $0{,}05 \text{–} 0{,}3\,\mu\text{A}/\mu\text{m}$ | Tối đa hóa $g_m$ trên mỗi nA/$\mu$A, giảm cực đại $\sigma(V_{OS})$ và $V_{DS,\min} \approx 100\,\text{mV}$. |
| **Cặp vi sai đầu vào tốc độ vừa–cao ($10\text{–}200\,\text{MHz}$)** | **Nghịch đảo vừa (Moderate Inversion — Điểm ngọt vàng!)** | $14 \text{–} 19\,\text{V}^{-1}$ | $0{,}8 \text{–} 3{,}0\,\mu\text{A}/\mu\text{m}$ | Đạt $\sim 65\%$ trần $g_m/I_D$ nhưng giữ được $f_T \approx 8\text{–}25\,\text{GHz}$ cao gấp $10\times$ vùng dưới ngưỡng sâu! |
| **Transistor chắn Cascode ($M_{\text{cas}}$)** | Nghịch đảo vừa–yếu | $15 \text{–} 20\,\text{V}^{-1}$ | $0{,}6 \text{–} 2{,}5\,\mu\text{A}/\mu\text{m}$ | Giữ $V_{DS,\min}$ nhỏ cho dải dao động ngõ ra và tăng độ lợi che chắn $g_m r_O$, chú ý cực phụ $\omega_{p,X} = g_{m,\text{cas}}/C_X$. |
| **Gương dòng, Nguồn dòng đuôi & Tải chủ động** | **Nghịch đảo mạnh (Strong Inversion, `region = 2`)** | $5 \text{–} 9\,\text{V}^{-1}$ | $8 \text{–} 25\,\mu\text{A}/\mu\text{m}$ | Nén nhiễu nhiệt tải $(g_{m,\text{load}}/g_{m,\text{in}})$ và chặn đứng bùng nổ sai lệch dòng gương Pelgrom! |

3. **Phân cực giữ $g_m$ không đổi theo nhiệt độ cho cặp đầu vào dưới ngưỡng:** Vì $g_{m,\text{sub}} = \frac{I_D}{\zeta V_T} = \frac{q I_D}{\zeta k T}$ tỉ lệ nghịch với nhiệt độ tuyệt đối $T$ nếu giữ $I_D$ hằng định, muốn $\text{GBW} = \frac{g_{m1}}{2\pi C_L}$ bất biến từ $-40\,^\circ\text{C}$ tới $125\,^\circ\text{C}$, phải nuôi cặp đầu vào dưới ngưỡng bằng **nguồn dòng PTAT ($I_D \propto V_T \propto T$)** từ khối tham chiếu Bandgap (`tech-ptat-current-and-constant-gm`) — khi đó $T$ ở tử và mẫu triệt tiêu nhau hoàn hảo!

### 5.2. Cách Trích xuất $S$, $\zeta$, $g_m/I_D$ và Kiểm chứng trên Cadence Virtuoso / Spectre
Trong mô hình BSIM4 của Spectre, khi transistor đi vào vùng dưới ngưỡng, tham số `region` trong `dcOpInfo` chuyển sang **`region = 3`** (Subthreshold), và tham số `vdsat` tự động được BSIM4 kẹp về sàn nhiệt $\sim 2\text{–}4\,V_T$ ($\sim 60\text{–}100\,\text{mV}$) thay vì âm vô nghĩa như hiệu `vgs - vth`!

```ocean
; Script OCEAN trích xuất Độ dốc dưới ngưỡng S (mV/dec), hệ số zeta, gm/ID và fT thực tế:
analysis('dc ?dev "/VGS_SRC" ?param "dc" ?start 0.0 ?stop 1.0 ?step 0.005)
run()
id_wf   = IS("/M1/D")
gm_wf   = getData("M1:gm" ?result "dc")
cgg_wf  = abs(getData("M1:cgg" ?result "dc"))

; 1. Hiệu suất hỗ dẫn gm/ID (V^-1) và Tần số chuyển tiếp fT (Hz):
gmid_wf = gm_wf / id_wf
ft_wf   = gm_wf / (2 * 3.14159265 * cgg_wf)

; 2. Độ dốc dưới ngưỡng S (mV/decade) và hệ số không lý tưởng zeta tại VGS = 0.15V:
slope_S_mV_dec = value(1e3 / deriv(log10(id_wf)) 0.15)
zeta_extracted = slope_S_mV_dec / (25.85 * 2.302585)
printf("Subthreshold Slope S = %.1f mV/dec | zeta = %.2f | Max gm/ID = %.1f V^-1\n"
       slope_S_mV_dec zeta_extracted ymax(gmid_wf))
```

- **Danh mục kiểm tra bắt buộc khi nghiệm thu mạch có transistor `region = 3`:**
  1. Kiểm tra `abs(vds) >= 0.12` ($> 4 V_T$ ở cả $125\,^\circ\text{C}$ nơi $4 V_T \approx 137\,\text{mV}$!) tại góc xấu nhất `SS, 125°C` và `FF, 125°C`.
  2. Tuyệt đối xác nhận **không có gương dòng chính xác nào** vô tình bị rơi vào `region = 3` bằng chạy `montecarlo` (mismatch + process) kiểm tra $\sigma(I_{\text{branch}})$.
  3. Kiểm tra tích hiệu suất–băng thông nội tại $(g_m/I_D)\cdot f_T$ trên đường cong quét để không đặt $W$ vượt quá điểm gãy của cực không trội.

---

## 6. Mốc Đối chiếu Sách Razavi & Thuật ngữ Chuẩn CLB

### 6.1. Đối chiếu Sách Gốc Razavi (2nd Edition)
- **Chương 2:** §2.3 *Second-Order Effects — Subthreshold Conduction* (tr. 24–26, PDF tr. 18–20): Phương trình (2.32) (nhắc lại điều biến kênh ở Ví dụ 2.7), Phương trình (2.33) đặc tuyến hàm mũ dưới ngưỡng, Hình 2.28 đường cong $\log I_D$ theo $V_{GS}$ kèm phép ước lượng độ dốc $80\,\text{mV/dec}$ và dòng rò tĩnh $18\,\text{mA}$ trên $100$ triệu transistor, chứng minh $g_m = I_D / (\xi V_T)$ cùng điểm giao $(V_{GS}-V_{TH})_1 = 2\xi V_T$ ở Phương trình (2.34)–(2.35), và Ví dụ 2.8 Phương trình (2.36)–(2.39) khảo sát mật độ dòng $I_D/W$ cùng quy tắc chọn giá trị $V_{GS}$ nhỏ hơn giữa luật bình phương và hàm mũ; §2.5 *Appendix A: FinFETs* (tr. 36–37, cải thiện kiểm soát tĩnh điện cổng giảm dòng rò dưới ngưỡng); Bài tập 2.14 & 2.27 (tr. 42–43).
- **Chương 11:** §11.2–§11.3 (tr. 460–467, đường cong thực nghiệm $g_m/I_D$ trơn từ vùng dưới ngưỡng sang nghịch đảo mạnh, Phương trình 11.5–11.6) và §11.6.5 *Large-Signal Behavior* (Ví dụ 11.16, tr. 505–507, tận dụng vùng dưới ngưỡng cho transistor cascode để tiết kiệm dự trữ điện áp và tăng $g_m$).
- **Ghi chú Ký hiệu Bản gốc & Bản dịch CLB:** Trong ấn bản 2 tiếng Anh của Razavi, hệ số không lý tưởng dưới ngưỡng được in bằng chữ Hy Lạp $\xi$ (*xi*, Phương trình 2.33 & 2.39), trong khi ấn bản 1 và nhiều tài liệu vi mạch dùng $\zeta$ (*zeta*) hoặc $n$; cả hai đều biểu diễn cùng một đại lượng vật lý $1 + C_{\text{dep}}/C_{ox} > 1$.

### 6.2. Bảng Thuật ngữ Chuẩn CLB Vi Mạch Sử dụng trong Thẻ
| Mã CLB | Thuật ngữ Tiếng Anh | Thuật ngữ Tiếng Việt Chuẩn | Ghi chú Ngữ cảnh |
|---|---|---|---|
| `T270` | Subthreshold Conduction | Sự dẫn dưới ngưỡng | Cơ chế dẫn dòng khuếch tán hữu hạn khi $V_{GS} < V_{TH}$ |
| `T271` | Weak inversion | Nghịch đảo yếu | Trạng thái bề mặt kênh có hạt tải tự do thưa, $I_D$ tăng hàm mũ |
| `T273` | Subthreshold current | Dòng điện dưới ngưỡng | $I_D = I_0 \exp[V_{GS}/(\zeta V_T)]$ khi $V_{DS} \gtrsim 4 V_T$ |
| `T276` | Thermal voltage ($V_T = kT/q$) | Điện áp nhiệt $V_T$ | $\approx 25{,}85\,\text{mV}$ ở $300\,\text{K}$; tăng tuyến tính theo nhiệt độ tuyệt đối $T$ |
| `T278` | Subthreshold slope | Độ dốc dưới ngưỡng | Số $\text{mV}$ cần thay đổi trên $V_{GS}$ để đổi $10\times$ dòng $I_D$ ($\zeta V_T \ln 10$) |
| `T283` | Subthreshold transconductance | Độ hỗ dẫn trong vùng dưới ngưỡng | $g_m = I_D / (\zeta V_T)$, giới hạn trần của hiệu suất $g_m/I_D$ |
| `T434` | Transit frequency ($f_T$) | Tần số chuyển tiếp $f_T$ | Tần số độ lợi dòng ngắn mạch bằng 1: $f_T = g_m / (2\pi C_{gg})$ |
| `T183` | Overdrive voltage ($V_{GS} - V_{TH}$) | Điện áp vượt ngưỡng | Mất ý nghĩa hình học khi âm trong vùng dưới ngưỡng; thay bằng $g_m/I_D$ |
