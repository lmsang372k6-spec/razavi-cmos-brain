---
{
  "id": "law-short-channel-effects",
  "kind": "law",
  "domain": "foundations",
  "title_vi": "Lý thuyết thu nhỏ linh kiện, hiệu ứng kênh ngắn và hệ phân cấp mô hình BSIM (Scaling Theory, Short-Channel Effects & BSIM Models)",
  "title_en": "MOS Scaling Theory, Short-Channel Effects, and SPICE/BSIM Device Models",
  "summary": "Hệ quy luật vật lý chi phối MOSFET khi co nhỏ kích thước xuống miền dưới micron và nanomet: thu nhỏ trường không đổi so với áp không đổi, sụt/tăng ngưỡng VTH (chia sẻ điện tích, cấy halo, DIBL), suy giảm độ linh động trường dọc, bão hòa vận tốc hạt tải, biến thiên phi tuyến ro(VDS), hạt tải nóng và tiến hóa mô hình Level 1–3 đến BSIM4.",
  "diagram": "../../diagrams/short-channel-iv-gmid.svg",
  "razavi_refs": [
    {
      "chapter": 17,
      "section": "17.1-17.3.6",
      "pages": "691-708, 710",
      "equations": ["17.1", "17.2", "17.4", "17.9", "17.11", "17.13", "17.15", "17.16", "17.18", "17.19", "17.20", "17.21", "17.23", "17.25", "17.26", "17.27", "17.30", "17.31", "17.48", "17.53"]
    },
    {
      "chapter": 11,
      "section": "11.1-11.2",
      "pages": "459-463",
      "equations": ["11.1", "11.3", "11.4", "11.5", "11.6"]
    }
  ],
  "glossary_codes": ["T031", "T075", "T106", "T167", "T394", "T1829", "T1831", "T1838", "T1841", "T1844", "T1845", "T1988"],
  "process_agnostic": true,
  "roles": {
    "scaling_laws": "So sánh hệ quả thu nhỏ trường không đổi (Dennard) với thu nhỏ áp không đổi lên công suất số và dải động tương tự",
    "high_field_transport": "Mô hình hóa sự suy giảm độ linh động theo trường dọc theta và bão hòa vận tốc theo trường ngang vsat làm phẳng gm",
    "2d_electrostatics_and_dibl": "Giải thích biến thiên VTH theo L (charge sharing vs halo RSCE) và đường cong yên ngựa ro(VDS) do CLM + DIBL + ion hóa va chạm",
    "compact_spice_models": "Định vị giới hạn hội tụ, đạo hàm và bảo toàn điện tích từ Shichman-Hodges Level 1 tới BSIM3v3/BSIM4 và EKV"
  },
  "symptoms_addressed": [
    "severe-discrepancy-between-hand-square-law-and-bsim4",
    "intrinsic-gain-gmro-collapse-in-nanometer-nodes",
    "odd-harmonic-distortion-in-single-device-v-to-i",
    "cascode-gain-ceiling-from-substrate-impact-ionization",
    "charge-droop-in-meyer-cap-transient-simulations"
  ],
  "limitations": [
    "empirical-bsim-hundreds-of-parameters-obscure-hand-algebra",
    "vth-cannot-scale-below-300mv-due-to-nonscalable-subthreshold-slope"
  ],
  "checklists": ["common-mos"]
}
---

## 1. Bản chất Nguyên lý, Sơ đồ Mạch & Vai trò Từng Nhánh Cấu trúc

Tại sao công thức luật bình phương $I_D = \frac{1}{2}\mu_n C_{ox}\frac{W}{L}(V_{GS} - V_{TH})^2$ hoạt động tốt ở kênh dài vài $\mu\text{m}$ thập niên 1980 nhưng lại sai lệch một trời một vực khi $L$ co xuống $180\,\text{nm} \rightarrow 90\,\text{nm} \rightarrow 65\,\text{nm} \rightarrow 40\,\text{nm}$ (Hình 11.1 & Chương 17)? Câu trả lời nằm ở sự phá vỡ **lý thuyết thu nhỏ kích thước linh kiện lý tưởng (ideal constant-field scaling theory)** của Dennard (§17.1, tr. 691–695).

Theo kịch bản **thu nhỏ trường không đổi (constant-field scaling)** với hệ số thu nhỏ $\alpha > 1$: mọi kích thước hình học $(W, L, t_{ox}, x_j)$ giảm $\alpha$ lần, điện áp $(V_{DD}, V_{TH})$ giảm $\alpha$ lần, và nồng độ pha tạp đế $N_{\text{sub}}$ tăng $\alpha$ lần để giữ nguyên cường độ điện trường $E = V/d$ khắp linh kiện. Khi đó với mạch số, điện dung giảm $\alpha$, dòng giảm $\alpha$, trễ cổng $T_d = C V_{DD}/I$ giảm $\alpha$, và công suất động $f C V_{DD}^2$ giảm tới $\alpha^3$ lần! Thế nhưng với **mạch tương tự bị giới hạn bởi nhiễu nhiệt** (§17.1, tr. 694), bức tranh hoàn toàn đảo ngược:
- Khi $V_{DD}$ giảm $\alpha$ lần, biên độ tín hiệu cực đại giảm $\alpha$ lần $\Rightarrow$ công suất tín hiệu giảm $\alpha^2$ lần.
- Để giữ nguyên **dải động (dynamic range, DR)**, mật độ phổ nhiễu nhiệt $\overline{V_n^2} = 4kT\gamma / g_m$ cũng phải giảm $\alpha^2$ lần $\Rightarrow$ **$g_m$ phải tăng lên $\alpha^2$ lần**! Vì $V_{OV}$ đã giảm $\alpha$ lần, từ $g_m = 2I_D / V_{OV}$ suy ra dòng phân cực $I_D$ phải **tăng $\alpha$ lần**, khiến công suất tĩnh $P = (V_{DD}/\alpha)(\alpha I_D) = V_{DD} I_D$ **không hề giảm** (thậm chí tăng $\alpha$ lần trong mạch chuyển mạch tụ giới hạn bởi nhiễu $kT/C$ nếu giữ nguyên tốc độ biến thiên slew rate!).

![So sánh đặc tuyến I–V luật bình phương với bão hòa vận tốc và đường cong gm/ID](../../diagrams/short-channel-iv-gmid.svg)

Nghiêm trọng hơn, trong thực tế lịch sử bán dẫn, $V_{DD}$ và $V_{TH}$ **không thể co nhỏ nhanh bằng kích thước $L$** vì 5 rào cản vật lý bất khả kháng (§17.2, tr. 695): (1) điện trường tăng vọt theo xu hướng pha trộn *thu nhỏ áp không đổi (constant-voltage scaling)*; (2) thế tiếp xúc nội tại $\Phi_B$ không co nhỏ được; (3) độ sâu tiếp giáp S/D khó ép mỏng tương ứng; (4) độ linh động giảm khi tăng pha tạp đế; và đặc biệt (5) **độ dốc dưới ngưỡng $S = 2.3 V_T(1 + C_d/C_{ox}) \approx 80\text{–}100\,\text{mV/dec}$ phụ thuộc vào hằng số nhiệt $kT/q$ nên hoàn toàn không co nhỏ được**! Muốn dòng rò tắt $I_{\text{off}}$ nhỏ hơn dòng dẫn $5$ bậc độ lớn đồng thời chịu được $\sim 100\,\text{mV}$ trôi do nhiệt độ và quy trình, $V_{TH}$ bị khóa sàn quanh $0.25\text{–}0.4\,\text{V}$. Điện trường dọc và ngang tăng cao trong kênh ngắn đã kích hoạt hàng loạt **hiệu ứng kênh ngắn (short-channel effects, SCE)** làm biến dạng tận gốc cả $V_{TH}$, $g_m$, lẫn $r_o$.

---

## 2. Hệ Phương trình Cốt lõi & Tư duy "Nhìn Mạch Đọc Nhanh" (Analysis by Inspection)

### 2.1. Ba Cơ chế Biến thiên Điện áp Ngưỡng $V_{TH}$ theo $L$ và $V_{DS}$ (§17.2.1, tr. 695–697)
1. **Sụt áp ngưỡng khi giảm $L$ (经典 $V_{TH}$ Roll-off do Chia sẻ Điện tích — Hình 17.5–17.6):** Khi $L$ ngắn, hai vùng nghèo của tiếp giáp nguồn và máng lấn sâu vào gầm kênh dẫn, gánh đỡ (image) một phần lớn điện tích ion bất động trong đế thay cho cực cổng. Cực cổng cần ít điện tích hơn để mở kênh $\Rightarrow V_{TH}$ **giảm khi $L$ giảm**.
2. **Hiệu ứng Kênh ngắn Đảo ngược (Reverse Short-Channel Effect, RSCE — Hình 17.8):** Để chống xuyên thủng ở công nghệ nanomet, nhà máy cấy thêm hai túi pha tạp nặng loại $p^+$ (**halo / pocket implants**) bao quanh mép S và D. Khi $L$ rất ngắn ($L = L_{\min}$), hai vùng halo $p^+$ chồng lấn làm nồng độ pha tạp trung bình dọc kênh $N_{\text{sub,avg}}$ cao vọt $\Rightarrow V_{TH}$ cao; khi tăng $L$ dài ra khỏi $L_{\min}$, tỷ trọng vùng halo giảm làm $N_{\text{sub,avg}}$ giảm $\Rightarrow$ **$V_{TH}$ lại giảm khi tăng $L$ từ $L_{\min}$**! *(Chính hiệu ứng RSCE này giải thích hiện tượng thực tế ở Chương 11 Chú thích 6 tr. 474: tăng gấp đôi $L$ của PMOS từ $40\,\text{nm}$ lên $80\,\text{nm}$ mà không tăng $W$, dòng $I_D$ hầu như không giảm một nửa như lý thuyết cũ vì $|V_{THP}|$ đã giảm xuống!).*
3. **Hạ thấp rào thế do điện áp cực máng (Drain-Induced Barrier Lowering, DIBL — Hình 17.7):** Điện trường hai chiều từ cực máng xuyên qua vùng nghèo nâng thế bề mặt kênh (tương đương một tụ ghép máng–kênh $C'_d$), hạ thấp rào thế nguồn–kênh và làm **$V_{TH}$ giảm tuyến tính khi tăng $V_{DS}$**:
   $$\Delta V_{TH,\text{DIBL}} = -\eta_{\text{DIBL}} V_{DS}$$
   Làm tăng dòng máng theo $V_{DS}$ ngay cả sau khi thắt kênh — thủ phạm số một đánh sập trở kháng ra $r_o$ ở 90nm/65nm/45nm!

### 2.2. Suy giảm Độ linh động Trường dọc ($\theta$) & Bão hòa Vận tốc Trường ngang ($v_{\text{sat}}$)
- **Trường dọc từ $V_{GS}$ (§17.2.2, Phương trình 17.20–17.23 & Ví dụ 11.1 Phương trình 11.4–11.6):** Điện trường thẳng đứng ép hạt tải sát mặt nhám oxit–silic gây tán xạ bề mặt:
  $$\mu_{\text{eff}} = \frac{\mu_0}{1 + \theta(V_{GS} - V_{TH})}, \qquad \theta \approx \frac{10^{-7}}{t_{ox}}\;(\text{V}^{-1})$$
  Khai triển chuỗi $I_D \approx \frac{1}{2}\mu_0 C_{ox}\frac{W}{L}\left[(V_{GS}-V_{TH})^2 - \theta(V_{GS}-V_{TH})^3\right]$ phơi bày hệ quả quan trọng: khác với luật bình phương thuần túy vốn chỉ sinh hài bậc hai, suy giảm độ linh động sinh ra **méo hài bậc lẻ ($HD_3$)** ngay trong một transistor đơn và không thể triệt tiêu hoàn toàn chỉ bằng đối xứng vi sai!
- **Trường ngang dọc kênh và Bão hòa vận tốc (§17.2.3, Phương trình 17.24–17.30 & Bài tập 17.10 Phương trình 17.53):** Khi điện trường dọc kênh vượt $E_{\text{crit}} \approx 1\,\text{V}/\mu\text{m}$ (tức chỉ cần $V_{DS} > 40\,\text{mV}$ trên kênh $40\,\text{nm}$!), vận tốc electron chạm trần **vận tốc bão hòa $v_{\text{sat}} \approx 10^7\,\text{cm/s}$**.
  - *Giới hạn bão hòa vận tốc hoàn toàn (Phương trình 11.1–11.3 & 17.25):*
    $$I_{D,\text{vsat}} = W C_{ox}(V_{GS} - V_{TH}) v_{\text{sat}}, \qquad g_{m,\text{vsat}} = W C_{ox} v_{\text{sat}}$$
    Ba đảo lộn chấn động so với kênh dài: (1) $I_D$ tăng **tuyến tính** (cách đều nhau khi quét đều $V_{GS}$!) chứ không bình phương; (2) $I_D$ và $g_m$ **độc lập với chiều dài kênh $L$** và dòng $I_D$ — hỗ dẫn bị khóa trần chỉ còn phụ thuộc bề rộng $W$; (3) xảy ra **bão hòa sớm (premature saturation)** tại $V_{DS,\text{sat}} < V_{GS} - V_{TH}$!
  - *Phương trình hợp nhất cả hai trường (Phương trình 17.26–17.30 & 17.53):*
    $$I_D = \frac{1}{2}\mu_0 C_{ox}\frac{W}{L}\frac{(V_{GS} - V_{TH})^2}{1 + \left(\dfrac{\mu_0}{2 v_{\text{sat}} L} + \theta\right)(V_{GS} - V_{TH})}, \qquad V_{DS,\text{sat}} = \frac{2\frac{v_{\text{sat}}L}{\mu_{\text{eff}}}(V_{GS}-V_{TH})}{2\frac{v_{\text{sat}}L}{\mu_{\text{eff}}} + (V_{GS}-V_{TH})}$$
    *(Ghi chú hiệu đính quan trọng: Phương trình 17.27 trong bản in gốc viết $2\mu_{\text{eff}}L$ do lỗi in thứ nguyên; đại lượng điện áp đặc trưng chuẩn khớp với Phương trình 17.26 chính là $2 v_{\text{sat}} L / \mu_{\text{eff}}$! Khi $V_{OV} \ll 2 v_{\text{sat}} L / \mu_0$, mẫu số tiến về $1$ và linh kiện quay lại tiệm cận luật bình phương!)*
    Đạo hàm Phương trình 17.30 cho công thức hỗ dẫn tổng quát trên mọi vùng nghịch đảo mạnh (Phương trình 17.53, tr. 710):
    $$g_m = \frac{I_D}{V_{GS} - V_{TH}}\left[1 + \frac{1}{1 + \left(\dfrac{\mu_0}{2 v_{\text{sat}} L} + \theta\right)(V_{GS} - V_{TH})}\right]$$
    Nhìn nhanh cực đẹp: khi $V_{OV}$ nhỏ, ngoặc vuông bằng $2 \Rightarrow g_m = \frac{2I_D}{V_{OV}}$ (luật bình phương); khi $V_{OV}$ lớn (kênh cực ngắn), ngoặc vuông giảm về $1 \Rightarrow g_m = \frac{I_D}{V_{OV}}$ (hiệu suất hỗ dẫn mất đứt một nửa!).

### 2.3. Đường cong Hình Chuông của $r_o(V_{DS})$ và Hiệu ứng Hạt tải Nóng (§17.2.4–17.2.5, Hình 17.12)
Trong một MOSFET kênh ngắn thực tế, điện trở ra $r_o(V_{DS})$ không bao giờ là hằng số $1/(\lambda I_D)$ mà trải qua **3 miền vật lý nối tiếp** khi tăng $V_{DS}$ từ biên triode lên $V_{DD}$ (Hình 17.12, tr. 701):
1. **Miền sát biên bão hòa ($V_{DS}$ vừa vượt $V_{DS,\text{sat}}$):** Điều biến chiều dài kênh thuần túy (CLM) thống trị; độ mở rộng vùng nghèo giảm dần theo $\sqrt{V_{DS} - V_{DS,\text{sat}}}$ nên $r_o$ **tăng dần** từ giá trị rất thấp ở vùng gối (Phương trình 17.31).
2. **Miền giữa dải điện áp:** Hiệu ứng **DIBL** bắt đầu kéo giảm $V_{TH}$ khi tăng $V_{DS}$, cân bằng với sự giảm tốc CLM tạo ra một vùng đỉnh phẳng tương đối của $r_o$ (hoặc ở PMOS 40nm Hình 11.20b, DIBL mạnh đến mức làm $r_o$ giảm dần ngay từ sớm!).
3. **Miền $V_{DS}$ cao — Ion hóa do va chạm & Hạt tải nóng (Hot-Carrier Impact Ionization):** Hạt tải tăng tốc cực mạnh gần cực máng va đập vào mạng tinh thể sinh cặp electron–lỗ trống: electron chui vào cực máng còn lỗ trống đổ thẳng xuống **đế bán dẫn ($I_{\text{sub}}$)**, kéo sập $r_o$ ở $V_{DS}$ lớn! *(Ở công nghệ $\le 45\,\text{nm}$ chạy nguồn $V_{DD} \le 1.0\,\text{V}$ nhỏ hơn năng lượng vùng cấm silic $E_g \approx 1.12\,\text{eV}$, hiệu ứng hạt tải nóng giảm mạnh như Razavi chỉ rõ ở tr. 700, nhưng vẫn rất nguy hiểm ở linh kiện I/O $1.8\,\text{V}/2.5\,\text{V}$!).*

### 2.4. Bảng Tiến hóa Các Thế hệ Mô hình SPICE Compact (§17.3.1–17.3.6, tr. 701–708)
Hiểu rõ giả thiết ngầm của từng thế hệ mô hình giúp kỹ sư không bị đánh lừa bởi lỗi hội tụ hoặc đạo hàm giả tạo trong mô phỏng:

| Thế hệ mô hình | Phạm vi chiều dài $L$ hợp lệ | Đặc điểm vật lý & Toán học cốt lõi | Khiếm khuyết chí mạng trong thiết kế tương tự |
|---|---|---|---|
| **Level 1** *(Shichman–Hodges)* | $L \gtrsim 4\,\mu\text{m}$ | Phương trình luật bình phương + $(1+\lambda V_{DS})$, tụ Meyer làm trơn (Phương trình 17.32–17.36) | Không có dẫn dưới ngưỡng, không có hiệu ứng kênh ngắn, sai số $r_o$ rất lớn, tụ không bảo toàn điện tích |
| **Level 2** | $L \gtrsim 0.7\text{–}1\,\mu\text{m}$ *(kênh rộng)* | Tích phân điện tích nghèo biến thiên dọc kênh tạo lũy thừa $3/2$ (Phương trình 17.37–17.43) | Gãy khúc đạo hàm (kink) tại biên dưới ngưỡng – nghịch đảo mạnh (Hình 17.14) và biên triode – bão hòa |
| **Level 3** | $L \gtrsim 1\,\mu\text{m}$ | Bán thực nghiệm cho $\mu_{\text{eff}}$, $v_{\max}$ và DIBL theo $1/L_{\text{eff}}^3$ (Phương trình 17.44–17.47) | Đứt gãy nghiêm trọng đạo hàm $\partial I_D/\partial V_{DS}$ gây bước nhảy giả trên $r_o(V_{DS})$ (Hình 17.15) |
| **BSIM1 / BSIM2** | $L \gtrsim 0.5\text{–}0.8\,\mu\text{m}$ | Tham số hóa hình học $P = P_0 + \alpha_P/L_{\text{eff}} + \beta_P/W_{\text{eff}}$ (~50–70 tham số, Phương trình 17.48) | Quá thiên về đa thức khớp đường cong thực nghiệm; BSIM1 có thể cho $r_o < 0$ ở $V_{DS}$ cao! |
| **BSIM3v3 / BSIM4** | $0.25\,\mu\text{m}$ xuống $28\,\text{nm}$ | Quay lại nền tảng vật lý, một phương trình thống nhất liên tục mọi đạo hàm $I_D, g_m, g_{ds}$ từ dưới ngưỡng tới bão hòa + bảo toàn điện tích + DIBL/RSCE/STI/WPE | Hàng trăm tham số phức tạp không thể giải ngược bằng tay $\rightarrow$ bắt buộc đi kèm phương pháp $g_m/I_D$ Chương 11! |
| **EKV** *(Enz–Krummenacher–Vittoz)* | Mọi vùng nghịch đảo | Lấy **cực thân (Bulk)** làm gốc điện thế thay vì cực nguồn, đối xứng hoàn toàn S–D | Rất gọn cho giải tích công suất siêu thấp / dưới ngưỡng, ít phổ biến hơn BSIM4 trong PDK thương mại chuẩn |

### 2.5. Bài toán Kiểm chứng Độ lợi Khi Bão hòa Vận tốc Hoàn toàn (Bài tập 17.12, Hình 17.19, tr. 710)
Giả sử các transistor trong tầng nguồn chung tải điện trở $R_D$ (Hình 17.19a) và cặp vi sai tải nối diode PMOS $M_{3,4}$ (Hình 17.19b) đều chịu bão hòa vận tốc hoàn toàn ($g_m = W C_{ox} v_{\text{sat}}$, bỏ qua $\lambda, \gamma$):
- Với tầng CS tải điện trở:
  $$|A_v| = g_{m1} R_D = W_1 C_{ox} v_{\text{sat}} R_D$$
  (độc lập hoàn toàn với $L_1$ và dòng phân cực $I_D$!).
- Với cặp vi sai NMOS $M_{1,2}$ tải nối diode PMOS $M_{3,4}$:
  $$|A_v| = \frac{g_{m1}}{g_{m3}} = \frac{W_1 C_{ox} v_{\text{sat},n}}{W_3 C_{ox} v_{\text{sat},p}} = \frac{W_1 v_{\text{sat},n}}{W_3 v_{\text{sat},p}}$$
  Khác hẳn kênh dài nơi $|A_v| = \sqrt{\frac{\mu_n(W/L)_1}{\mu_p(W/L)_3}}$ tăng theo căn bậc hai của tỉ số, ở giới hạn bão hòa vận tốc độ lợi tỷ lệ **bậc nhất** với $W_1 / W_3$ và tỷ số $v_{\text{sat},n}/v_{\text{sat},p}$ gần $1$ hơn nhiều so với $\mu_n / \mu_p$!

---

## 3. Bất biến Cấu trúc & Các Bẫy Lỗi Kinh điển (Structural Invariants & Traps)

- **[INV-SCE-01] Sơ đồ Tương đương Tín hiệu Nhỏ Chương 2 Vẫn Đúng Cấu trúc ở Kênh Ngắn (Chương 11 §11.1, tr. 459):** Mạch tương đương gồm $g_m v_{gs}$, $g_{mb} v_{bs}$, $r_o$ và 5 tụ cực vẫn giữ nguyên 100% giá trị cho phân tích mạch ở 90nm/65nm/45nm/28nm; thứ duy nhất phải thay đổi là **không dùng công thức luật bình phương để tính $g_m, r_o, V_{OV}$ từ $W/L, I_D$**, mà phải tra từ đặc tuyến mô hình thực!
- **[INV-SCE-02] Trần Độ lợi Cascode do Dòng Ion hóa Đổ Về Đế (Hình 17.12, tr. 701):** Khi xảy ra ion hóa va chạm ở $V_{DS}$ lớn, dòng phát sinh chảy trực tiếp từ **Drain xuống Substrate (GND)** chứ không chảy về Source! Vì điện trở rò $r_{\text{impact}}$ này bắc cầu từ ngõ ra thẳng xuống đất (vượt qua mặt đầu cực nguồn của transistor cascode), không một cấu trúc xếp chồng cascode hay gain-boosting nào có thể nhân $r_{\text{impact}}$ lên bằng $g_m r_o$ được nữa!

- **[TRAP-SCE-01] Bẫy Đỉnh Lồi Hẫng / Gián đoạn Đạo hàm trong Mô hình Cũ (Level 1–3, BSIM1–2 — §17.3.1–17.3.4):** Mô hình Level 1–3 có sự đứt gãy đạo hàm $\partial I_D/\partial V_{DS}$ tại ranh giới triode–bão hòa (Hình 17.15) và điểm gãy khúc (kink) giữa dưới ngưỡng và nghịch đảo mạnh (Hình 17.14), thậm chí BSIM1 từng dự đoán $r_o < 0$ phi vật lý ở $V_{DS}$ lớn! Thiết kế mạch tương tự hiện đại bắt buộc dùng mô hình liên tục đạo hàm bậc cao và bảo toàn điện tích (BSIM3v3.3, BSIM4, PSP hoặc EKV).
- **[TRAP-SCE-02] Bẫy Mất Độ lợi tại Đỉnh Dải Dao động do Sụt $r_o(V_{DS})$:** Chỉ kiểm tra độ lợi AC tại $V_{\text{out}} = V_{DD}/2$ (nơi $r_o$ đạt đỉnh hình chuông) sẽ bỏ lọt hiện tượng khi ngõ ra tiến gần $V_{DD} - V_{DS,\min}$ hoặc $V_{DS,\min}$, một nhánh đi vào vùng sườn trái CLM còn nhánh đối diện chịu DIBL mạnh ở $V_{DS}$ lớn, làm độ lợi vi sai sụt mất $3\text{–}5$ lần (y hệt Hình 11.22 & 11.40c của Razavi!).
- **[TRAP-SCE-03] Bẫy Giảm $g_m$ Khi Quét Quá Cao $V_{GS}$ (Bài tập 11.2, Hình 11.6, tr. 462):** Ở linh kiện nanomet, khi $V_{GS} - V_{TH}$ vượt quá $\sim 0.45\text{–}0.5\,\text{V}$, tán xạ trường dọc mạnh đến mức đường cong $g_m(V_{GS})$ không những không tăng mà còn **quay đầu giảm xuống**!

---

## 4. Lộ trình Nâng cấp Cấu trúc & Bát giác Đánh đổi (Upgrade Paths & Design Octagon)

Sự suy thoái của $g_m r_o$ và phi tuyến kênh ngắn định hình lại toàn bộ chiến lược chọn cấu trúc mạch:
- **Thay đổi phương pháp định cỡ linh kiện:** Từ luật bình phương `concept-mos-operating-regions` bắt buộc chuyển sang quy trình thiết kế theo linh kiện tham chiếu và mật độ dòng `tech-nanometer-vdsmin-gmid-sizing` kết hợp chọn $L > L_{\min}$ có chọn lọc tại `tech-channel-length-and-opamp-scaling`.
- **Khắc phục sụt giảm $g_m r_o$ trên Bát giác `concept-analog-design-octagon`:** Khi một tầng đơn chỉ đạt $g_m r_o \approx 8\text{–}12$, muốn đạt độ lợi $A_0 \ge 500\text{–}1000$ dưới nguồn $1.0\,\text{V}$ không thể dùng mãi `topo-telescopic-cascode-opamp` (thiếu swing), mà phải nâng cấp lên `topo-two-stage-opamp` (tầng 1 cascode + tầng 2 CS dài kênh) hoặc `topo-gain-boosted-cascode`.
- **Khắc phục sai lệch biến thiên góc công nghệ và nhiệt độ đi kèm kênh ngắn:** Chuyển tiếp trực tiếp sang quy tắc kiểm chứng 5 góc tiến trình và điểm bù nhiệt ZTC tại `concept-process-corners-and-temperature`.

---

## 5. Thích ứng Đa Tiến trình (90nm / 65nm / 45nm) & Cách Kiểm chứng trong Cadence / Spectre

Bảng định hướng hành vi kênh ngắn điển hình khi chuyển dịch giữa ba nút công nghệ mục tiêu:

| Đặc tính vật lý (tại $L = L_{\min}$) | CMOS 90nm ($V_{DD} = 1.2\,\text{V}$) | CMOS 65nm ($V_{DD} = 1.0\text{–}1.2\,\text{V}$) | CMOS 45nm / 40nm ($V_{DD} = 0.9\text{–}1.0\,\text{V}$) |
|---|---|---|---|
| Độ lợi nội tại $g_m r_o$ ở $L_{\min}$ | $\sim 12\text{–}18$ | $\sim 9\text{–}14$ | $\sim 6\text{–}10$ (PMOS có thể chỉ $\sim 5\text{–}7$) |
| Chiều dài kênh khuyến nghị cho nguồn dòng / cascode | $180\text{–}360\,\text{nm}$ ($2\text{–}4\,L_{\min}$) | $130\text{–}260\,\text{nm}$ ($2\text{–}4\,L_{\min}$) | $80\text{–}180\,\text{nm}$ ($2\text{–}4\,L_{\min}$) |
| Hiện tượng RSCE (Halo implant) | Rõ rệt | Rất mạnh | Cực mạnh ($|V_{TH}|$ giảm $30\text{–}80\,\text{mV}$ khi tăng $L$) |

**Cách trích xuất đường cong đặc trưng BSIM4 trong Cadence Virtuoso / Spectre (một lần cho mỗi tiến trình):**
1. Dựng testbench 1 transistor tham chiếu $W_{\text{REF}} = 5\,\mu\text{m}$ (ví dụ chia $nf = 5$ ngón $1\,\mu\text{m}$ để khớp hiệu ứng chiều rộng hẹp STI/WPE thực tế!), quét tham số `L` qua `{Lmin, 2*Lmin, 4*Lmin, 8*Lmin}`.
2. Chạy quét `dc` lồng nhau (`VGS` từ $0$ đến $V_{DD}$, `VDS` tại $\{0.15\,\text{V}, V_{DD}/2\}$) và lưu trọn bộ vector BSIM4: `id`, `gm`, `gds`, `gmbs`, `vth`, `vdsat`, `cgg`, `cdd`.
3. Vẽ 4 đồ thị cốt lõi trong ViVA: (a) `gm/id` theo `id/W`; (b) `gm/gds` ($g_m r_o$) theo `vds` để thấy rõ hình chuông CLM–DIBL; (c) `vth` theo `L` để nhận diện đỉnh RSCE halo; và (d) `gm/(2*pi*abs(cgg))` ($f_T$) theo `gm/id`.

**Mẫu Netlist Spectre Độc lập (`char_sce.scs`) Đo Trực tiếp DIBL, Hình Chuông $r_o(V_{DS})$ và RSCE Trên Mọi PDK:**
```spice
simulator lang=spectre
parameters L_val=60n W_f=1u nf_val=5 VGS_val=0.45 VDS_val=0.5

include "toplevel_models.scs" section=tt

Vgs (g 0) vsource dc=VGS_val
Vds (d 0) vsource dc=VDS_val
Mref (d g 0 0) nch w=W_f*nf_val l=L_val nf=nf_val m=1

save Mref:id Mref:gm Mref:gds Mref:vth Mref:vdsat Mref:cgg

// 1. Quét VDS để vẽ đường cong hình chuông ro(VDS) = 1 / gds và hệ số DIBL = -d(vth)/d(VDS)
swp_vds dc param=VDS_val start=0.02 stop=1.0 step=0.01

// 2. Quét chiều dài kênh L để quan sát VTH roll-off và Reverse Short-Channel Effect (RSCE halo)
swp_len dc param=L_val values=[45n 60n 90n 130n 180n 360n 720n]
```

*Cách đọc nhanh trên đồ thị xuất ra:* Nếu tại $V_{DS} = 0.5\,\text{V}$ độ dốc $-\partial V_{TH}/\partial V_{DS}$ vượt quá $80\text{–}100\,\text{mV/V}$, linh kiện ở chiều dài $L$ đó đang chịu DIBL rất nặng — tuyệt đối không dùng $L$ này cho gương dòng chính xác hoặc tải nguồn dòng đơn không bọc cascode!

---

## 6. Mốc Đối chiếu Sách Razavi & Thuật ngữ Chuẩn CLB

- **Sách gốc Razavi (2nd Ed.):**
  - Chương 17: §17.1 *Scaling Theory* (tr. 691–695, Phương trình 17.1–17.15, Hình 17.1–17.4), §17.2 *Short-Channel Effects* (tr. 695–701: §17.2.1 *Threshold Voltage Variation*, DIBL & RSCE halo Phương trình 17.16–17.19; §17.2.2 *Mobility Degradation* Phương trình 17.20–17.23; §17.2.3 *Velocity Saturation* Phương trình 17.24–17.30; §17.2.4 *Hot Carrier Effects*; §17.2.5 *Output Impedance Variation with $V_{DS}$* Phương trình 17.31 & Hình 17.12), §17.3.1–17.3.6 *MOS Device Models: Level 1–3, BSIM1–4, HSPICE Level 28, EKV & Charge Conservation* (tr. 701–708, Phương trình 17.32–17.50, Hình 17.14–17.16), Bài tập 17.10 (tr. 710, Phương trình 17.53).
  - Chương 11: §11.1–11.2 (tr. 459–463, Phương trình 11.1–11.6, Hình 11.1–11.6).
- **Thuật ngữ chuẩn CLB Vi Mạch (`THUẬT NGỮ CHUẨN.md`):**
  - `T075` / `T1829`: *scaling theory / technology scaling* $\rightarrow$ **Lý thuyết thu nhỏ kích thước linh kiện / Thu nhỏ kích thước công nghệ**.
  - `T1838` / `T1841` / `T1844`: *velocity saturation / saturated velocity / premature saturation* $\rightarrow$ **Bão hòa vận tốc hạt tải**, **Vận tốc bão hòa**, **Bão hòa sớm**.
  - `T1845`: *mobility degradation with vertical field* $\rightarrow$ **Suy giảm độ linh động do điện trường thẳng đứng**; `T1831`: **Mô hình BSIM4**.
  - Chú thích Chương 11 (`C11-0171`): *drain-induced barrier lowering (DIBL)* $\rightarrow$ **Hiệu ứng hạ thấp rào thế do điện áp cực máng**.
