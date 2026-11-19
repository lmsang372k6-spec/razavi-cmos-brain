---
{
  "id": "concept-mos-operating-regions",
  "kind": "concept",
  "domain": "foundations",
  "title_vi": "Các vùng hoạt động của MOSFET, điện áp ngưỡng và đặc tuyến I–V (MOS Operating Regions & I-V Derivation)",
  "title_en": "MOSFET Operating Regions, Threshold Voltage, and I-V Characteristics",
  "summary": "Giải phẫu vật lý hình thành kênh nghịch đảo, điện áp ngưỡng VTH, điện áp vượt ngưỡng Vov và thiết lập phương trình dòng–áp chính xác qua ba vùng Ngắt (Cutoff), Triode / Triode sâu (làm công tắc & điện trở điều khiển bằng áp) và Bão hòa (làm nguồn dòng điều khiển bằng áp).",
  "diagram": "../../diagrams/short-channel-iv-gmid.svg",
  "razavi_refs": [
    {
      "chapter": 2,
      "section": "2.1-2.2.2",
      "pages": "7-19",
      "equations": ["2.1", "2.2", "2.3", "2.4", "2.5", "2.6", "2.7", "2.8", "2.9", "2.10", "2.11", "2.12", "2.13", "2.14", "2.15", "2.16"]
    }
  ],
  "glossary_codes": ["T024", "T054", "T056", "T061", "T080", "T083", "T084", "T106", "T111", "T154", "T167", "T175", "T183", "T185", "T188", "T198", "T207", "T208", "T214", "T221", "T552"],
  "process_agnostic": true,
  "roles": {
    "gate_oxide_capacitor": "Tụ oxit cổng Cox biến điện áp điều khiển VGS thành mật độ điện tích linh động Qd(x) trong kênh dẫn",
    "deep_triode_resistor_switch": "Đường dẫn nguồn–máng tuyến tính Ron khi VDS << 2*Vov phục vụ chuyển mạch lấy mẫu và điện trở điều chỉnh bằng áp",
    "saturated_transconductor_current_source": "Cấu hình thắt kênh (pinch-off) khi VDS >= Vov tách dòng ID khỏi VDS để làm nguồn dòng và phần tử khuếch đại"
  },
  "symptoms_addressed": [
    "confusion-between-mos-and-bjt-saturation",
    "source-drain-role-reversal-misidentification",
    "triode-entry-gain-collapse",
    "pmos-sign-and-inequality-errors"
  ],
  "limitations": [
    "square-law-overestimates-current-in-sub-100nm-channels",
    "abrupt-vth-turn-on-ignores-subthreshold-tail",
    "neglects-channel-length-modulation-and-body-effect-in-first-order-form"
  ],
  "checklists": ["common-mos"]
}
---

## 1. Bản chất Nguyên lý, Sơ đồ Mạch & Vai trò Từng Nhánh Cấu trúc

Một **transistor hiệu ứng trường MOS (MOSFET)** là linh kiện bốn cực hoàn toàn đối xứng về mặt hình học giữa hai vùng pha tạp nặng cùng loại: **cực cổng (gate — G)** cách điện qua lớp oxit mỏng $t_{ox}$, hai vùng tiếp giáp làm **cực nguồn (source — S)** và **cực máng (drain — D)**, cùng **đế bán dẫn / cực thân (substrate / bulk — B)** (Razavi Chương 2, §2.1, Hình 2.2–2.4). Khác với cấu trúc rời rạc, trên một phiến CMOS tiêu chuẩn nền đế loại $p$ ($p$-substrate):
- Mọi **transistor loại $n$ (NMOS / NFET)** thường dùng chung đế $p$-substrate nối về điện thế âm nhất hệ thống ($V_{SS}$ hoặc $\text{GND}$) để giữ các diode tiếp giáp $n^+/p$ luôn phân cực ngược; trừ khi công nghệ cung cấp **giếng $n$ sâu (deep $n$-well — Ghi chú thiết kế nanomet tr. 9)** bao bọc một $p$-well cục bộ riêng (tốn thêm diện tích cách ly lớn).
- Mỗi **transistor loại $p$ (PMOS / PFET)** nằm trong một **giếng $n$ ($n$-well)** độc lập, mặc định nối lên điện thế dương nhất ($V_{DD}$), nhưng có thể tách riêng nối thân–nguồn ($B\text{–}S$) để triệt hiệu ứng thân khi cần.

Vì cấu trúc vật lý đối xứng giữa S và D, việc gọi cực nào là **cực nguồn** và cực nào là **cực máng** chỉ xác định được sau khi biết thế điện áp tại hai đầu kênh (§2.1.2, tr. 9 & §2.2.2, tr. 18):
- Với **NMOS** (hạt tải là electron âm): cực có điện thế **thấp hơn** cung cấp electron nên là **Source**, cực có điện thế **cao hơn** thu electron nên là **Drain** ($V_D \ge V_S$).
- Với **PMOS** (hạt tải là lỗ trống dương): cực có điện thế **cao hơn** cung cấp lỗ trống nên là **Source**, cực có điện thế **thấp hơn** là **Drain** ($V_S \ge V_D$). Khi điện thế nút đảo chiều trong mạch chuyển mạch (như công tắc lấy mẫu Chương 13), vai trò S và D tự động hoán đổi cho nhau!

![Đặc tuyến dòng–áp I–V từ quy luật bình phương đến kênh ngắn](../../diagrams/short-channel-iv-gmid.svg)

Quá trình hình thành kênh dẫn dọc bề mặt phân cách oxit–silic của NMOS khi tăng $V_{GS}$ từ $0$ diễn ra qua ba giai đoạn vật lý liên tiếp (Hình 2.6, §2.2.1):
1. **Vùng nghèo (Depletion):** Khi $V_{GS}$ mới dương nhẹ, điện trường xuyên qua $C_{ox}$ đẩy lỗ trống rời khỏi bề mặt đế $p$, để lại các ion nhận bất động tích điện âm ($Q_{\text{dep}}$) tạo thành bộ chia áp tụ nối tiếp $C_{ox}$ và $C_{\text{dep}}$; chưa có hạt tải tự do nên $I_D = 0$.
2. **Khởi phát nghịch đảo mạnh & Điện áp ngưỡng ($V_{TH}$):** Khi thế bề mặt đủ dương để nồng độ electron tại mặt phân cách bằng đúng nồng độ lỗ trống của đế nền, các electron từ cực nguồn tràn vào tạo thành **lớp nghịch đảo (inversion layer)** nối thông S–D tại **điện áp ngưỡng (threshold voltage — $V_{TH}$)**.
3. **Điều biến kênh theo $V_{DS}$ — từ Triode đến Thắt kênh (Pinch-off):** Khi $V_{GS} > V_{TH}$, hiệu áp vượt quá ngưỡng được gọi là **điện áp vượt ngưỡng (overdrive voltage)**:
   $$V_{OV} \triangleq V_{GS} - V_{TH}$$
   Nếu $V_{DS}$ rất nhỏ, lớp nghịch đảo trải đều từ S tới D như một thanh điện trở điều khiển bằng $V_{OV}$ (**vùng triode sâu — deep triode**). Khi $V_{DS}$ tăng dần, thế kênh cục bộ $V(x)$ tăng từ $0$ (tại S) lên $V_{DS}$ (tại D), làm hiệu thế cổng–kênh tại đầu máng sụt còn $V_{GD} = V_{GS} - V_{DS}$. Ngay khi $V_{DS}$ chạm $V_{GS} - V_{TH}$ (tức $V_{GD} = V_{TH}$), mật độ điện tích linh động tại sát đầu máng giảm về không — kênh dẫn bị **thắt kênh (pinched off)** tại $x = L' \le L$, mở ra **vùng bão hòa (saturation region)** nơi các electron lao vọt qua vùng nghèo cực máng với vận tốc cao và dòng $I_D$ trở nên hầu như độc lập với $V_{DS}$.

---

## 2. Hệ Phương trình Cốt lõi & Tư duy "Nhìn Mạch Đọc Nhanh" (Analysis by Inspection)

### 2.1. Điện áp ngưỡng vật lý và Chiều dài kênh hiệu dụng
Do sự khuếch tán ngang $L_D$ của hai vùng pha tạp $n^+$ dưới cổng trong quá trình ủ nhiệt, khoảng cách thực tế giữa S và D là **chiều dài hiệu dụng (effective length)**:

$$L_{\text{eff}} = L_{\text{drawn}} - 2 L_D$$

(Trong toàn bộ sách Razavi, ký hiệu $L$ trong công thức điện học luôn hiểu là $L_{\text{eff}}$ trừ khi ghi rõ $L_{\text{drawn}}$). Phương trình vật lý của điện áp ngưỡng tại phân cực thân–nguồn bằng không (Phương trình 2.1, tr. 11) là:

$$V_{TH0} = \Phi_{MS} + 2\Phi_F + \frac{Q_{\text{dep}}}{C_{ox}}, \qquad \Phi_F = \frac{kT}{q}\ln\!\left(\frac{N_{\text{sub}}}{n_i}\right), \qquad Q_{\text{dep}} = \sqrt{4 q \epsilon_{\text{si}} |\Phi_F| N_{\text{sub}}}$$

với $C_{ox} = \epsilon_{ox}/t_{ox}$ là điện dung oxit cổng trên một đơn vị diện tích (mốc nhớ nhanh của Razavi tr. 11: tại $t_{ox} = 20\,\text{\AA} = 2\,\text{nm}$, $C_{ox} \approx 17.25\,\text{fF}/\mu\text{m}^2$, suy ra tỷ lệ nghịch tức thì cho mọi $t_{ox}$ khác!).

### 2.2. Thiết lập chặt chẽ đặc tuyến $I_D\text{–}V_{DS}$ từ Bổ đề Dòng hạt tải
Bổ đề cơ bản của thanh bán dẫn mang mật độ điện tích linh động trên đơn vị chiều dài $Q_d(x)$ ($\text{C/m}$) chuyển động với vận tốc $v(x)$ (Phương trình 2.2–2.6, tr. 12–14):

$$I = Q_d(x)\cdot v(x)$$

Tại tọa độ $x$ dọc kênh NMOS (với $V_S = 0$, thế kênh $V(0)=0$ và $V(L)=V_{DS}$), mật độ điện tích cảm ứng trong lớp nghịch đảo là $Q_d(x) = -W C_{ox}\,[V_{GS} - V(x) - V_{TH}]$. Với giả thiết kênh dài $v(x) = -\mu_n E(x) = \mu_n \frac{dV(x)}{dx}$, dòng cực máng hằng định dọc kênh thỏa mãn:

$$I_D = W C_{ox}\,[V_{GS} - V(x) - V_{TH}]\,\mu_n \frac{dV(x)}{dx} \quad \Longrightarrow \quad \int_0^L I_D\,dx = \int_0^{V_{DS}} W C_{ox}\mu_n\,[V_{GS} - V - V_{TH}]\,dV$$

Tích phân vế phải cho ta trọn vẹn hệ phương trình 3 vùng hoạt động của **NMOS** ($V_{TH} > 0$) và đối ngẫu **PMOS** ($V_{THP} < 0$, $V_{GS} < 0$, $V_{DS} \le 0$):

1. **Vùng Ngắt (Cutoff Region — $V_{GS} < V_{TH}$ với NMOS, hoặc $V_{SG} < |V_{THP}|$ với PMOS):**
   $$I_D \approx 0 \quad \text{(bỏ qua dòng rò dưới ngưỡng bậc hai)}$$

2. **Vùng Triode / Tuyến tính (Triode Region — $V_{GS} > V_{TH}$ và $0 \le V_{DS} < V_{GS} - V_{TH}$, Phương trình 2.8 & 2.15):**
   $$I_{D,n} = \mu_n C_{ox}\frac{W}{L}\left[(V_{GS} - V_{TH})V_{DS} - \frac{1}{2}V_{DS}^2\right], \qquad I_{D,p} = -\mu_p C_{ox}\frac{W}{L}\left[(V_{GS} - V_{THP})V_{DS} - \frac{1}{2}V_{DS}^2\right]$$
   - **Hệ quả Triode sâu (Deep Triode — $V_{DS} \ll 2(V_{GS} - V_{TH})$, Phương trình 2.10–2.11):** Bỏ qua số hạng bậc hai $\frac{1}{2}V_{DS}^2$, MOSFET trở thành điện trở tuyến tính điều khiển bằng cổng:
     $$R_{on} = \frac{1}{\mu_n C_{ox}\dfrac{W}{L}(V_{GS} - V_{TH})}$$
     Lưu ý sắc sảo của Razavi (tr. 15): khác hẳn BJT, MOSFET **vẫn có thể đang bật dẫn mạnh ($R_{on}$ hữu hạn nhỏ) ngay cả khi dòng tĩnh $I_D = 0$** (khi $V_{DS} = 0$, ví dụ công tắc lấy mẫu ở cuối quá trình nạp tụ!).

3. **Vùng Bão hòa — Quy luật Bình phương (Saturation Region — $V_{GS} > V_{TH}$ và $V_{DS} \ge V_{DS,\text{sat}} = V_{GS} - V_{TH}$, Phương trình 2.9, 2.13–2.14, 2.16):**
   Tích phân dừng tại điểm thắt kênh $x = L' \approx L$ ứng với $V(L') = V_{GS} - V_{TH}$ (đúng bằng đỉnh parabol của Phương trình 2.8!):
   $$I_{D,n} = \frac{1}{2}\mu_n C_{ox}\frac{W}{L'}(V_{GS} - V_{TH})^2, \qquad V_{GS} = V_{TH} + \sqrt{\frac{2 I_D}{\mu_n C_{ox}(W/L')}}$$
   $$|I_{D,p}| = \frac{1}{2}\mu_p C_{ox}\frac{W}{L'}(V_{SG} - |V_{THP}|)^2$$

### 2.3. Mẹo "Nhìn Mạch Đọc Nhanh" Ranh giới Bão hòa Không Cần Biết Điện thế Cực Nguồn!
Trong các mạch chồng tầng phức tạp (cascode, gương dòng, cặp vi sai tải tích cực), việc trừ nhẩm $V_{GS} - V_{TH}$ rồi so với $V_{DS}$ rất dễ nhầm dấu (đặc biệt với PMOS!). Razavi chỉ ra quy tắc bất biến cực nhanh dựa trực tiếp trên hiệu áp **Cổng–Máng** (Hình 2.19, tr. 18–19):
- **Với NMOS đang dẫn ($V_{GS} > V_{THN}$):** Điều kiện $V_{DS} \ge V_{GS} - V_{THN}$ tương đương đại số tuyệt đối với:
  $$V_G - V_D \le V_{THN} \quad \Longleftrightarrow \quad V_D \ge V_G - V_{THN}$$
  *Đọc nhanh:* Điện thế cực máng NMOS được phép **tụt xuống thấp hơn cả cực cổng một khoảng tối đa bằng $V_{THN}$** trước khi rơi vào vùng triode! (Hệ quả tức thì: một NMOS **nối diode** có $V_D = V_G$, nên $V_G - V_D = 0 < V_{THN} \Rightarrow$ **luôn luôn nằm chắc chắn trong vùng bão hòa** miễn là $V_{THN} > 0$!).
- **Với PMOS đang dẫn ($V_{SG} > |V_{THP}|$):** Điều kiện $V_{SD} \ge V_{SG} - |V_{THP}|$ tương đương tuyệt đối với:
  $$V_D - V_G \le |V_{THP}| \quad \Longleftrightarrow \quad V_D \le V_G + |V_{THP}|$$
  *Đọc nhanh:* Điện thế cực máng PMOS được phép **nhô cao hơn cực cổng một khoảng tối đa bằng $|V_{THP}|$** trước khi rơi vào vùng triode!

### 2.4. Hai Ví dụ Kinh điển Từ Sách Razavi (Ví dụ 2.1 & Bài tập 2.16 — Ghép Nối tiếp Kênh)
1. **Công tắc / Điện trở Triode sâu có Cực Máng Hở Mạch (Ví dụ 2.1, Hình 2.14, Phương trình 2.12, tr. 15–16):**
   Cho NMOS $M_1$ có $\mu_n C_{ox} = 50\,\mu\text{A/V}^2$, $W/L = 10$, $V_{TH} = 0.3\,\text{V}$, cực nguồn nối nguồn cố định $V_S = 1.0\,\text{V}$, cực máng để hở ($I_D = 0$). Khi quét $V_G$ từ $0$ lên $3\,\text{V}$:
   - Với $V_G < V_S + V_{TH} = 1.3\,\text{V}$: transistor ngắt hoàn toàn, $R_{on} = \infty$.
   - Với $V_G > 1.3\,\text{V}$: vì cực máng để hở nên $I_D = 0 \Rightarrow V_{DS} = 0 \ll 2(V_{GS} - V_{TH})$, linh kiện nằm **chính xác trong vùng triode sâu** với điện trở dẫn giảm theo đường hyperbol:
     $$R_{on}(V_G) = \frac{1}{(50\,\mu\text{A/V}^2)\times 10 \times (V_G - 1.3\,\text{V})} = \frac{2\,\text{k}\Omega\cdot\text{V}}{V_G - 1.3\,\text{V}}$$
     Ví dụ này phá tan ngộ nhận phổ biến rằng "$I_D = 0$ nghĩa là MOSFET tắt"!
2. **Ghép nối tiếp hai MOSFET cùng cổng tạo kênh dài gấp đôi (Bài tập 2.16, Hình 2.55, tr. 42):**
   Khi hai NMOS giống hệt nhau kích thước $W/L$ nối chung cực cổng $V_G$ và mắc nối tiếp kênh (cực máng con dưới $M_1$ nối vào cực nguồn con trên $M_2$, bỏ qua $\gamma, \lambda$):
   - Con dưới $M_1$ luôn có $V_{D1} = V_{S2} < V_G - V_{TH}$ (để con trên $M_2$ còn dẫn được!), nên **$M_1$ bắt buộc làm việc trong vùng Triode**, còn $M_2$ ở vùng Bão hòa nếu $V_{DS,\text{tot}} \ge V_G - V_{TH}$.
   - Cộng phương trình dòng $I_{D1,\text{tri}} = I_{D2,\text{sat}}$ khử hoàn toàn nút giữa $V_X = V_{D1}$, thu được $I_D = \frac{1}{2}\mu_n C_{ox}\frac{W}{2L}(V_{GS} - V_{TH})^2$ — tương đương chính xác một MOSFET đơn có tỉ số hình học **$W/(2L)$**! Kỹ thuật ghép nối tiếp kênh (*series stacking*) này cực kỳ hữu ích khi cần tạo $L_{\text{eff}}$ lớn cho gương dòng công suất siêu nhỏ hoặc chia áp chống đánh thủng SOA!

---

## 3. Bất biến Cấu trúc & Các Bẫy Lỗi Kinh điển (Structural Invariants & Traps)

- **[INV-REG-01] Bất biến Phân vai Vai trò Vùng hoạt động trong Mạch Tương tự:**
  - Cần **nguồn dòng tĩnh** hoặc **bộ chuyển đổi áp–dòng khuếch đại ($g_m$ cao, $r_o$ cao)** $\rightarrow$ bắt buộc phân cực trong **Vùng Bão hòa (Saturation)**.
  - Cần **công tắc truyền tín hiệu** hoặc **điện trở biến thiên theo điện áp** (ví dụ $R_z$ bù Miller bám theo $1/g_{m2}$, hoặc cảm biến CMFB vùng triode) $\rightarrow$ bắt buộc vận hành trong **Vùng Triode / Triode sâu**.
- **[INV-REG-02] Bất biến Nguồn dòng Một đầu Nổi (Single-Floating-Terminal Current Source — Hình 2.17, tr. 18):** Để $V_{GS}$ được cố định độc lập với tín hiệu, cực nguồn của nguồn dòng NMOS phải neo vào đất (hút dòng về GND — *current sink*) và cực nguồn của nguồn dòng PMOS phải neo vào $V_{DD}$ (bơm dòng từ nguồn dương — *current source*). Rất khó tạo nguồn dòng MOSFET hai đầu cùng nổi tùy ý mà không có mạch dịch mức bám theo.
- **[INV-REG-03] Bất biến Transistor Nối Diode Chế độ Tăng cường:** Mọi MOSFET chế độ tăng cường ($V_{THN} > 0$ hoặc $V_{THP} < 0$) có cực cổng nối trực tiếp cực máng ($V_{GD} = 0$) và có dòng chạy qua đều tự động ở **vùng bão hòa** (trừ linh kiện *native / zero-$V_{TH}$* hoặc *depletion-mode* có $V_{THN} \le 0$!).

- **[TRAP-REG-01] Bẫy Đánh đồng "Bão hòa" của MOSFET với "Bão hòa" của BJT (Chú thích 6, tr. 16):** Ngược nhau hoàn toàn! Ở BJT, *forward-active* là vùng khuếch đại nguồn dòng còn *saturation* là vùng tiếp giáp B–C phân cực thuận làm sập điện trở ra. Ở MOSFET, **Saturation** mới là vùng nguồn dòng/khuếch đại tốt, còn **Triode** mới là vùng sập điện trở ra và mất độ lợi!
- **[TRAP-REG-02] Bẫy Lẫn lộn Dấu PMOS khi Viết Bất đẳng thức:** Viết $V_{DS} \ge V_{GS} - V_{TH}$ với các số âm của PMOS trong đầu cực kỳ dễ đảo chiều dấu bất đẳng thức! Luôn viết công thức PMOS theo **độ lớn dương** $V_{SG} = V_S - V_G > |V_{THP}|$, $V_{SD} = V_S - V_D \ge V_{OV,P} = V_{SG} - |V_{THP}|$, hoặc dùng quy tắc $V_D \le V_G + |V_{THP}|$.
- **[TRAP-REG-03] Bẫy Hoán đổi Cực Nguồn – Cực Máng Ngầm trong Mô phỏng Quá độ:** Trong công tắc truyền dẫn hoặc tải kéo–đẩy khi điện áp nút ngõ ra vọt qua điện thế đầu kia của kênh, cực từng được gọi là "Source" trên ký hiệu schematic nay có thế cao hơn (với NMOS) và biến thành **Drain thực sự**, làm thay đổi hoàn toàn $V_{GS}$ hiệu dụng và $V_{SB}$!

---

## 4. Lộ trình Nâng cấp Cấu trúc & Bát giác Đánh đổi (Upgrade Paths & Design Octagon)

Từ các phương trình vùng hoạt động cơ sở này, toàn bộ cây kiến thức phân nhánh theo hai hướng:
1. **Bổ sung hiệu ứng vật lý bậc hai và mô hình tần số cao:**
   - Từ đạo hàm đặc tuyến bão hòa đi tới 3 công thức hỗ dẫn, hiệu ứng thân, điều biến chiều dài kênh và dẫn dưới ngưỡng tại `concept-mos-transconductance-and-body-effect`.
   - Từ cấu trúc hình học lớp oxit và tiếp giáp $n^+/p$ đi tới sơ đồ tương đương tín hiệu nhỏ kèm tụ ký sinh tại `concept-mos-capacitances-small-signal`.
   - Khi chiều dài kênh co xuống dưới micron / nanomet khiến giả thiết $v = \mu E$ đổ vỡ, nâng cấp mô hình vật lý sang `law-short-channel-effects` và phương pháp định cỡ thực chiến dựa trên $V_{DS,\min}$ tại `tech-nanometer-vdsmin-gmid-sizing`.
2. **Đánh đổi trực tiếp trên Bát giác Thiết kế (`concept-analog-design-octagon`) thông qua chọn $V_{OV}$:**
   - Chọn **$V_{OV}$ nhỏ** ($60\text{–}120\,\text{mV}$): tối đa hóa **Voltage Swing** (do $V_{DS,\text{sat}}$ thấp) và hiệu suất hỗ dẫn $g_m/I_D$ (tốt cho cặp vi sai đầu vào `topo-basic-differential-pair`), nhưng đòi hỏi $W/L$ lớn làm giảm **Speed**, thu hẹp dải tuyến tính đầu vào $\sqrt{2}V_{OV}$, và làm tăng sai lệch dòng ở gương dòng `topo-basic-current-mirror` (theo định luật đối ngẫu Pelgrom `law-pelgrom-mismatch-and-sizing-duality`).
   - Chọn **$V_{OV}$ lớn** ($200\text{–}350\,\text{mV}$): tăng **Linearity** và cải thiện độ khớp dòng gương dòng, nhưng ăn lẹm trực tiếp vào khoảng dự trữ điện áp dưới nguồn cấp thấp.

---

## 5. Thích ứng Đa Tiến trình (90nm / 65nm / 45nm) & Cách Kiểm chứng trong Cadence / Spectre

Ở các tiến trình **90nm, 65nm và 45nm**, hai thay đổi cốt tử xảy ra so với lý thuyết kênh dài Chương 2:
1. **Bão hòa sớm do bão hòa vận tốc (Premature Saturation):** Dòng cực máng bắt đầu đi ngang (vào vùng bão hòa) ở điện áp gối $V_{DS,\min}$ **nhỏ hơn** $V_{GS} - V_{TH}$ tính theo luật bình phương (xem Hình 11.2 & 11.4, Chương 11). Ngoài ra, biên chuyển tiếp từ triode sang bão hòa trở nên trơn dần (không gãy khúc rõ rệt), đặc biệt ở PMOS kênh ngắn $40\text{–}65\,\text{nm}$.
2. **Đa chủng loại ngưỡng $V_{TH}$ trong cùng một PDK:** Các bộ PDK công nghiệp 90nm/65nm/45nm cung cấp nhiều họ linh kiện (`SVT/RVT`, `LVT`, `HVT`, `Native/Zero-VT` và `Thick-Oxide I/O 1.8V/2.5V`). Quy tắc cấu trúc $V_D \ge V_G - V_{THN}$ vẫn đúng về mặt định tính, nhưng tuyệt đối không dùng công thức tay $V_{OV} = \sqrt{2I_D/(\mu C_{ox} W/L)}$ để chốt kích thước cuối cùng!

**Cách kiểm chứng chính xác vùng hoạt động trong Cadence Virtuoso IC617 / Spectre:**
- **Đọc mã `region` chuẩn của mô hình BSIM3v3 / BSIM4 trong `dcOpInfo`:**
  - `region = 0`: Ngắt (Cutoff)
  - `region = 1`: Vùng Triode / Tuyến tính (Linear / Triode) — **BÁO ĐỘNG ĐỎ** nếu đó là transistor khuếch đại hoặc nguồn dòng/gương dòng!
  - `region = 2`: Vùng Bão hòa (Saturation) — trạng thái chuẩn cho khuếch đại & gương dòng.
  - `region = 3`: Vùng Dưới ngưỡng (Subthreshold / Weak inversion) — chấp nhận được cho cặp đầu vào công suất siêu thấp hoặc cascode mật độ dòng nhỏ (như Ví dụ 11.16 của Razavi), nhưng cần kiểm tra băng thông $f_T$.
  - `region = 4`: Đánh thủng (Breakdown) — vi phạm giới hạn an toàn điện áp cực (SOA)!
- **Kiểm tra định lượng biên bão hòa thực tế trên Spectre:** Không lấy `vgs - vth` trừ tay, mà đọc trực tiếp tham số nội tại `vdsat` do BSIM4 tính toán và kiểm chứng bất đẳng thức:
  $$|V_{DS}| - |V_{\text{dsat}}| \ge 50\text{–}100\,\text{mV} \quad \text{và đồng thời kiểm tra } g_m r_o = \frac{\texttt{gm}}{\texttt{gds}} \text{ đạt kỳ vọng}$$
  bởi ở 45nm/65nm, đôi khi Spectre báo `region = 2` vừa chớm qua ranh giới nhưng `gds` vẫn còn rất lớn (knee region), làm độ lợi thực tế tụt một nửa nếu không chừa biên dự phòng trên $V_{\text{dsat}}$!

**Mẫu Script Chẩn đoán Vùng Hoạt động Tự động Trong OCEAN / PSF Reader:**
```ocean
; Kiểm tra nhanh vùng làm việc & khoảng dự trữ bão hòa cho danh sách MOSFET chính
foreach(instName list("/M1" "/M2" "/M3" "/M4" "/Mtail")
  reg   = pv(instName "region" ?result "dcOpInfo")
  vds   = abs(pv(instName "vds"    ?result "dcOpInfo"))
  vdsat = abs(pv(instName "vdsat"  ?result "dcOpInfo"))
  gm_ro = pv(instName "gm" ?result "dcOpInfo") / pv(instName "gds" ?result "dcOpInfo")
  printf("Inst %s : region=%d | |VDS|-|Vdsat|=%.1f mV | gm*ro=%.1f\n"
         instName int(reg) (vds - vdsat)*1e3 gm_ro)
)
```

| Tổ hợp kết quả `dcOpInfo` đọc được | Chẩn đoán vật lý chính xác | Hành động sửa mạch chuẩn Razavi |
|---|---|---|
| `region = 1`, `|VDS| < |Vdsat|` trên nguồn dòng/khuếch đại | Transistor sập vào vùng Triode do thiếu khoảng dự trữ hoặc lệch phân cực cổng | Giảm $V_{DS,\text{sat}}$ bằng tăng $W$ (giữ $I_D$), dịch lại áp phân cực $V_b$ (LVCCML), hoặc bớt tầng xếp chồng |
| `region = 2`, nhưng `|VDS| - |Vdsat| < 30 mV` và `gm*ro < 6` | Nằm sát điểm uốn gối (knee region), chỉ cần tín hiệu nhỏ hoặc sang góc `SS, 125°C` là rơi vào Triode | Nới thêm $\ge 50\,\text{mV}$ cho $|V_{DS}|$ hoặc tăng nhẹ $W$ để hạ thấp $|V_{\text{dsat}}|$ |
| `region = 0` trên một nhánh mạch | Mạch tự phân cực rơi vào nghiệm suy biến $I = 0$ hoặc $V_{CM}$ đầu vào vi phạm sàn ICMR | Bổ sung mạch khởi động (startup) hoặc dịch mức chế độ chung đầu vào $V_{CM}$ |

---

## 6. Mốc Đối chiếu Sách Razavi & Thuật ngữ Chuẩn CLB

- **Sách gốc Razavi (2nd Ed.):**
  - Chương 2: §2.1.1 *MOSFET as a Switch* (tr. 7–8), §2.1.2 *MOSFET Structure* (tr. 8–9, Ghi chú *Deep n-well* tr. 9), §2.1.3 *MOS Symbols* (tr. 9–10, Hình 2.5), §2.2.1 *Threshold Voltage* (tr. 10–12, Phương trình 2.1), §2.2.2 *Derivation of I/V Characteristics* (tr. 12–19, Phương trình 2.2–2.16, Ví dụ 2.1–2.2, Hình 2.18–2.19).
- **Chú giải & Bản dịch chuẩn CLB (`Nội bộ/Chương 02/Nguồn dựng/content.json` & `THUẬT NGỮ CHUẨN.md`):**
  - `FN2`: Chỉ số *drawn* là kích thước vẽ trên bố trí hình học (layout), phân biệt với chiều dài hiệu dụng $L_{\text{eff}} = L_{\text{drawn}} - 2L_D$.
  - `FN4`: Phân biệt linh kiện *chế độ tăng cường* (enhancement-mode, $V_{THN} > 0$) với *chế độ nghèo* (depletion-mode).
  - `FN6`: Cảnh báo không nhầm thuật ngữ *bão hòa (saturation)* giữa MOSFET và BJT.
  - Mã thuật ngữ: `T111` (**Điện áp ngưỡng**, $V_{TH}$), `T183` / `T905` (**Điện áp vượt ngưỡng**, $V_{GS} - V_{TH}$), `T185` (**Vùng triode**, còn gọi là vùng tuyến tính), `T188` (**Vùng triode sâu**), `T198` (**Vùng bão hòa**), `T207` (**Điện áp máng–nguồn tối thiểu để duy trì bão hòa**), `T208` (**Khoảng dự trữ điện áp**), `T083` (**Quy luật bình phương**).
