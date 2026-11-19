---
{
  "id": "concept-bsim4-and-finfet-nanometer-models",
  "kind": "concept",
  "domain": "nonideal-and-physical",
  "title_vi": "Mô hình Linh kiện SPICE Nanomet BSIM3/BSIM4, Bảo toàn Điện tích Ward–Dutton, Điểm ZTC và Vật lý FinFET Ba Chiều (BSIM4 & FinFET Models)",
  "title_en": "Nanometer SPICE Device Models (Level 1–3 to BSIM4 & EKV), Charge Conservation, ZTC Point, and 3D FinFET Physics",
  "summary": "Hệ thống hóa sự tiến hóa từ mô hình vật lý SPICE Level 1–3 sang họ mô hình công nghiệp BSIM3v3/BSIM4 và EKV: nội suy hình học theo chiều dài/rộng hiệu dụng, hàm trơn liên tục đạo hàm qua vùng dưới ngưỡng–bão hòa, sai số mất điện tích của mô hình tụ Meyer so với ma trận điện dung bảo toàn điện tích Ward–Dutton, dòng rò xuyên hầm cực cổng IG, GIDL, suy giảm ro do cấy halo/pocket, điểm hệ số nhiệt bằng không ZTC (đảo chiều nhiệt độ ở VOV thấp) và vật lý transistor vây ba chiều FinFET với bề rộng lượng tử hóa.",
  "diagram": "../../diagrams/short-channel-iv-gmid.svg",
  "razavi_refs": [
    {
      "chapter": 17,
      "section": "17.3.1-17.4, 17.Problems",
      "pages": "702-710",
      "equations": ["17.32", "17.36", "17.41", "17.48", "17.49", "17.50", "17.51", "17.52", "17.53"]
    },
    {
      "chapter": 2,
      "section": "2.5",
      "pages": "36-37",
      "equations": []
    }
  ],
  "glossary_codes": [
    "T031",
    "T043",
    "T054",
    "T069",
    "T737",
    "T808",
    "T809",
    "T810",
    "T1831",
    "T1835",
    "T1944",
    "T1961",
    "T1963",
    "T2180",
    "T2181",
    "T2182",
    "T2183",
    "T2185",
    "T2186",
    "T2187"
  ],
  "process_agnostic": true,
  "roles": {
    "spice_compact_model_engine": "Tập phương trình giải tích và tham số thực nghiệm (hàng trăm tham số trong BSIM4) nối kết vật lý bán dẫn của nhà máy đúc silicon với trình mô phỏng mạch Cadence Spectre.",
    "binning_and_smoothing_functions": "Công thức phụ thuộc kích thước hình học theo 1/Leff, 1/Weff và các hàm trơn toán học đảm bảo dòng ID, hỗ dẫn gm, gds và đạo hàm bậc cao liên tục tuyệt đối qua mọi vùng làm việc.",
    "ward_dutton_charge_model": "Mô hình tính toán điện tích tại bốn cực (QG, QD, QS, QB) làm biến trạng thái cơ sở để bảo toàn điện tích tuyệt đối trong mô phỏng quá độ mạch tụ chuyển mạch (SC) và dao động.",
    "nanometer_leakage_and_halo_terms": "Các thành phần vật lý dưới 90nm gồm dòng rò xuyên hầm oxit cổng IG, dòng rò cực máng cảm ứng bởi cổng GIDL và hiệu ứng cấy túi halo làm tăng gm nhưng làm sụp đổ điện trở ra ro.",
    "finfet_3d_trigate_channel": "Cấu trúc kênh dẫn dạng vây thẳng đứng được cổng kim loại điện môi k-cao bao bọc ba mặt giúp khôi phục kiểm soát tĩnh điện, triệt DIBL và lượng tử hóa bề rộng theo số vây nguyên Nfin."
  },
  "symptoms_addressed": [
    "square-law-hand-calculation-mismatch-against-spectre-bsim4",
    "artificial-voltage-droop-charge-loss-in-meyer-capacitance-spice-sim",
    "discontinuous-gm-or-ro-kinks-across-mos-inversion-regions-and-bin-boundaries",
    "unexpected-positive-temperature-coefficient-of-drain-current-at-low-vov",
    "gate-leakage-corrupting-ultra-low-frequency-integrators-and-pll-loop-filters"
  ],
  "limitations": [
    "bsim4-hundreds-of-empirical-parameters-obscure-direct-hand-design-intuition",
    "bin-boundary-discontinuities-if-w-or-l-sweeps-across-poorly-stitched-pdk-model-bins",
    "finfet-width-quantization-forbids-arbitrary-continuous-w-sizing-and-increases-fringing-cgd"
  ],
  "checklists": [
    "common-mos",
    "layout-and-matching"
  ]
}
---

## 1. Bản chất Nguyên lý, Sơ đồ Mạch & Vai trò Từng Nhánh Cấu trúc

Trong suốt các chương đầu tiên của sách Razavi, công thức luật bình phương kênh dài (`long-channel square-law model` — `T809`) đóng vai trò chiếc la bàn trực giác giúp kỹ sư nhận diện chiều hướng đánh đổi của mạch. Thế nhưng, ngay khi bước xuống các nút công nghệ dưới micromet sâu và nanomet (`180nm` $\to$ `90nm` $\to$ `65nm` $\to$ `45nm` $\to$ `FinFET`), không một phương trình sơ cấp 5 tham số nào còn đủ sức dự báo chính xác đồng thời dòng cực máng $I_D$, hỗ dẫn $g_m$, điện trở ra $r_O$ và năm thành phần điện dung phi tuyến (Razavi Chương 17 §17.3, tr. 701–708). Cầu nối duy nhất giữa phiến silicon thực tế của nhà máy đúc (`foundry`) với trình mô phỏng Cadence Spectre chính là **mô hình linh kiện thu gọn (`compact device model`)** — đỉnh cao là họ **mô hình BSIM4 (`T1831`)** cho MOSFET phẳng nanomet và **BSIM-CMG** cho **transistor hiệu ứng trường dạng vây (`FinFET` — `T043`)**.

![Đặc tuyến I-V kênh ngắn, hiệu suất hỗ dẫn gm/ID qua các vùng nghịch đảo và đối chiếu mô hình nanomet](../../diagrams/short-channel-iv-gmid.svg)

Để đọc hiểu tập tin mô hình PDK (`.scs` / `.lib`) như một kỹ sư thiết kế thực thụ thay vì coi SPICE là "hộp đen", cần nắm vững 5 trụ cột cấu trúc của thế hệ mô hình hiện đại:
1. **Sự tiến hóa từ Mô hình Vật lý Ngây thơ (`Level 1, 2, 3`) sang Mô hình Bán thực nghiệm Công nghiệp (`BSIM3v3 / BSIM4` & `EKV` — §17.3.1–17.3.5):**
   - *Level 1 (Shichman–Hodges, §17.3.1):* Chính là công thức luật bình phương sách giáo khoa với $\lambda$ hằng định, hoàn toàn mù trước hiệu ứng kênh ngắn, dẫn điện dưới ngưỡng và sự biến thiên $r_O(V_{DS})$.
   - *Level 2 & Level 3 (§17.3.2–17.3.3):* Level 2 tích phân điện tích vùng nghèo dọc kênh tạo hàm lũy thừa $3/2$ cồng kềnh nhưng đạo hàm $g_{ds} = \partial I_D / \partial V_{DS}$ lại **bị gãy khúc gián đoạn** tại điểm kẹp kênh $V_{DS,\text{sat}}$, khiến bộ giải Newton–Raphson của SPICE liên tục báo lỗi không hội tụ! Level 3 bán thực nghiệm hóa các biểu thức kênh ngắn/kênh hẹp nhưng bắt đầu sai lệch nặng khi $L < 0.8\,\mu\text{m}$.
   - *BSIM Series (`BSIM3v3` & `BSIM4`, §17.3.4):* Chuyển sang triết lý lấy **tính trơn toán học ($C^\infty$-continuity)** và **khả năng khớp số liệu đo đạc đa chiều (`geometry binning`)** làm trung tâm: ghép trơn vùng nghịch đảo yếu–trung bình–mạnh bằng một phương trình thống nhất theo điện áp vượt ngưỡng hiệu dụng $V_{gsteff}$, mô hình hóa đầy đủ 3 vùng của $r_O(V_{DS})$ (triode $\to$ bão hòa CLM $\to$ DIBL/va chạm ion hóa), bổ sung mạng điện trở cổng/nguồn/máng/đế tần số cao cùng các dòng rò lượng tử nanomet.
   - *Mô hình EKV (`Enz–Krummenacher–Vittoz`, §17.3.5):* Lấy **cực thân (`bulk`)** thay vì cực nguồn làm mốc tham chiếu điện thế đối xứng cho cả nguồn lẫn máng, cung cấp phương trình giải tích gọn đẹp dựa trên hệ số nghịch đảo (`inversion coefficient IC`) rất gần gũi với phương pháp định cỡ $g_m/I_D$ (`T2187`).
2. **Mô hình Điện tích Bảo toàn Ward–Dutton so với Bẫy Mất Điện tích của Mô hình Meyer (§17.3.6, Hình 17.16):** Trong mạch tụ chuyển mạch (SC), bộ so sánh và VCO, biến trạng thái phải là **điện tích cực nút $Q_G, Q_D, Q_S, Q_B$** thay vì các tụ vi phân rời rạc $C_{GS}(V), C_{GD}(V)$.
3. **Các Hiện tượng Ký sinh Lượng tử & Pha tạp Túi ở Công nghệ Nanomet (`BSIM4` — `90nm/65nm/45nm`):** Dòng rò xuyên hầm trực tiếp qua oxit cổng siêu mỏng (`gate leakage` — `T808`, `T1963`), dòng rò cực máng cảm ứng bởi cực cổng (`GIDL`), và cấy ion túi nghiêng (`Halo / Pocket implant`) làm đảo ngược quy luật $V_{TH}(L)$ và bóp nghẹt độ lợi nội tại $g_m r_O$.
4. **Hành vi Phụ thuộc Nhiệt độ và Điểm Đảo chiều Hệ số Nhiệt (`ZTC Point` — `T2185`, §17.3.7):** Sự cạnh tranh đối kháng giữa giảm điện áp ngưỡng $|V_{TH}(T)|$ và giảm độ linh động $\mu(T)$ khi tăng nhiệt độ tạo ra điểm giao cắt bất biến theo nhiệt độ.
5. **Bước Nhảy Vọt Kiến trúc sang `3D Tri-Gate FinFET` (Chương 2 §2.5, Hình 2.42–2.44):** Khi $L < 22\text{ nm}$, kênh phẳng mất khả năng kìm hãm điện trường cực máng; cấu trúc vây dựng đứng ba mặt cổng khôi phục đặc tuyến gần lý tưởng nhưng áp đặt luật **lượng tử hóa bề rộng rời rạc** theo số nguyên vây $N_{\text{fin}}$.

---

## 2. Hệ Phương trình Cốt lõi & Tư duy "Nhìn Mạch Đọc Nhanh" (Analysis by Inspection)

### 2.1. Quy luật Phân ô Hình học (`Geometry Binning`) trong BSIM & Level 28 (§17.3.4–17.3.5, Eq. 17.48–17.50)
Để một bộ phương trình khớp chính xác từ transistor cực ngắn/hẹp của logic số đến transistor dài/rộng hàng chục micromet của mạch tương tự, BSIM biểu diễn từng tham số vật lý hiệu dụng $P$ (như $V_{TH0}, \mu_0, \text{eta0}\dots$) quanh giá trị tiệm cận kênh rộng–dài $P_0$ theo chiều dài và chiều rộng hiệu dụng ($L_{\text{eff}} = L_{\text{drawn}} - 2 L_{\text{int}}$, $W_{\text{eff}} = W_{\text{drawn}} - 2 W_{\text{int}}$):

$$P(L_{\text{eff}}, W_{\text{eff}}) = P_0 + \frac{P_L}{L_{\text{eff}}} + \frac{P_W}{W_{\text{eff}}} + \frac{P_{WL}}{L_{\text{eff}} W_{\text{eff}}}$$

*(Trong sách Razavi §17.3.4 Eq. 17.48–17.49 viết dạng bậc nhất $P = P_0 + \frac{\alpha_P}{L_{\text{eff}}} + \frac{\beta_P}{W_{\text{eff}}}$; còn mô hình mở rộng Eq. 17.50 tính gia số quanh linh kiện tham chiếu đã đo đạc $(L_{\text{ref}}, W_{\text{ref}})$ kèm số hạng tích chéo $\gamma\!\left(\frac{1}{L} - \frac{1}{L_{\text{ref}}}\right)\!\left(\frac{1}{W} - \frac{1}{W_{\text{ref}}}\right)$).* Trong các bộ PDK công nghiệp (`TSMC/GF/UMC 90nm/65nm/45nm`), không gian $(W, L)$ được chia thành ma trận từ $9$ đến $25$ ô kích thước (`model bins`, ví dụ ranh giới tại $L = 0.12\,\mu\text{m}, 0.5\,\mu\text{m}, 2.0\,\mu\text{m}$).

### 2.2. Tại sao Mô hình Tụ Meyer Không Bảo toàn Điện tích? (§17.3.6, Hình 17.16)
Trong mô hình Meyer cổ điển, dòng điện dung cổng được tính từ tích phân $i_G = C_{GS}(V_{GS})\frac{dV_{GS}}{dt} + C_{GD}(V_{GD})\frac{dV_{GD}}{dt}$ với giả thiết ngầm rằng điện dung là hàm một biến độc lập và đối xứng ($C_{GD} = C_{DG}$). Trên thực tế ở MOSFET vùng bão hòa, điện áp cực máng thay đổi gần như không làm đổi điện tích cổng ($\frac{\partial Q_G}{\partial V_D} \approx 0$), trong khi điện áp cực cổng thay đổi lại điều khiển mạnh điện tích phía máng ($\frac{\partial Q_D}{\partial V_G} \neq 0$) — nghĩa là **tụ tương hỗ không đối xứng ($C_{GD} \neq C_{DG}$)**!
- Hệ quả kinh điển trên Hình 17.16: Đặt sóng vuông tuần hoàn qua tụ lý tưởng nối vào cực cổng MOSFET thả nổi DC (bộ chia áp điện dung). Với mô hình Meyer, sau mỗi chu kỳ nạp–xả điện áp, tích phân khép kín $\oint C(V)\,dV \neq 0$ làm "bốc hơi" một lượng điện tích ảo tại nút nổi $X$, gây ra hiện tượng **sụt áp trôi dần (`artificial voltage droop`)** hoàn toàn phi vật lý!
- **Giải pháp Ward–Dutton trong BSIM3/BSIM4:** Trình mô phỏng tính trực tiếp 4 hàm điện tích trạng thái $Q_G, Q_B, Q_S, Q_D$ thỏa mãn định luật bảo toàn tổng $Q_G + Q_B + Q_S + Q_D \equiv 0$, rồi lấy đạo hàm theo thời gian $i_k = \frac{dQ_k}{dt}$ và phân bổ điện tích kênh $Q_{\text{inv}} = Q_S + Q_D$ theo kịch bản chia phần trăm (`xpart`: `40%/60%` chuẩn bão hòa kênh dài, `50%/50%` đối xứng triode, hoặc `0%/100%`), đảm bảo mạch tụ chuyển mạch SC và bơm điện tích PLL bảo toàn điện tích đến từng atto-coulomb!

### 2.3. Dòng Rò Cực Cổng $I_G$, Dòng Rò `GIDL` và Sụp Đổ $r_O$ do Cấy Halo trong BSIM4
Khi chiều dày oxit cổng vật lý $t_{ox}$ co xuống dưới $20\,\text{\AA}$ ($2.0\text{ nm}$ ở `90nm/65nm` trước khi chuyển sang điện môi `High-k HfO2` ở `45nm/28nm`), xác suất xuyên hầm lượng tử cơ học trực tiếp của điện tử qua rào thế $\text{SiO}_2$ tăng theo hàm mũ của điện trường $E_{ox} = V_{GS}/t_{ox}$:

$$J_G = A_{\text{tun}} E_{ox}^2 \exp\!\left(-\frac{B_{\text{tun}}}{E_{ox}}\right) \implies I_G = W \cdot L \cdot J_G$$

- Cùng lúc đó, khi cực cổng kéo về mức thấp hoặc âm ($V_{GD} < 0$) trong khi cực máng ở mức cao $V_{DD}$, điện trường ngang–dọc cực mạnh tại vùng chồng lấp cổng–máng làm uốn cong dải năng lượng gây xuyên hầm từ dải hóa trị lên dải dẫn, sinh ra **dòng rò cực máng cảm ứng bởi cực cổng (`GIDL — Gate-Induced Drain Leakage`)** làm tăng dòng rò tắt của công tắc lấy mẫu!
- **Nghịch lý Cấy Túi `Halo / Pocket Implant` lên $g_m r_O$:** Để chống sụt áp ngưỡng `VTH roll-off` (`T2182`) và `DIBL` (`T2181`), nhà máy cấy hai "túi" pha tạp nồng độ cao sát sườn nguồn và máng. Khi $L$ ngắn lại, hai túi này chập vào nhau làm $V_{TH}$ **tăng lên** ở gần $L_{\min}$ (**hiệu ứng kênh ngắn đảo ngược — `Reverse Short-Channel Effect, RSCE`**), nhưng độ dốc pha tạp dốc đứng tại biên máng lại làm gia tăng mạnh hiệu ứng điều biến vùng nghèo theo $V_{DS}$, kéo điện trở ra $r_O$ của transistor core sụt thê thảm (khiến $g_m r_O$ chỉ còn $5\text{–}10$ ở `65nm/45nm`!). Các transistor tương tự chuyên dụng (`analog native / no-halo` hoặc I/O dày oxit) bỏ bước cấy halo này nên đạt $g_m r_O$ cao gấp $2\text{–}3$ lần ở cùng chiều dài kênh!

### 2.4. Phương trình Phụ thuộc Nhiệt độ và Điểm Hệ số Nhiệt Bằng Không (`ZTC Point` — §17.3.7, Eq. 17.51–17.52)
Trong BSIM, năng lượng vùng cấm của silic và độ linh động hạt tải giảm khi nhiệt độ tuyệt đối $T$ tăng (PT 17.51–17.52):

$$E_g(T) = 1.16 - \frac{7.02 \times 10^{-4}\,T^2}{T + 1108}\;\;[\text{eV}], \qquad \mu(T) = \mu_0 \left(\frac{300\text{ K}}{T}\right)^{\!k_\mu} \quad (k_\mu \approx 1.5\text{–}2.0), \qquad V_{TH}(T) = V_{TH}(T_0) - \kappa_{VT}(T - T_0)$$

với $\kappa_{VT} \approx 0.8\text{–}2.0\text{ mV/K}$. Lấy đạo hàm dòng bão hòa kênh dài $I_D(T) \approx \frac{1}{2}\mu(T) C_{ox}\frac{W}{L}\big[V_{GS} - V_{TH}(T)\big]^2$ theo $T$ với $V_{GS}$ cố định và cho $\frac{\partial I_D}{\partial T} = 0$:

$$\frac{1}{I_D}\frac{\partial I_D}{\partial T} = -\frac{k_\mu}{T} + \frac{2\kappa_{VT}}{V_{GS} - V_{TH}(T)} = 0 \implies V_{OV,\text{ZTC}} = V_{GS,\text{ZTC}} - V_{TH}(T_0) \approx \frac{2 \kappa_{VT} T_0}{k_\mu}$$

Ở $T_0 = 300\text{ K}$, thế trực tiếp dải $\kappa_{VT} \in [0.8,\,2.0]\text{ mV/K}$ và $k_\mu \in [1.5,\,2.0]$ vào công thức luật bình phương trên cho dải biên $V_{OV,\text{ZTC}} \approx 240\text{–}800\text{ mV}$; trong công nghệ nanomet bão hòa vận tốc ($I_D \propto V_{OV}^\alpha$ với $\alpha \approx 1.2\text{–}1.5$) và $\kappa_{VT}$ điển hình $\approx 0.6\text{–}1.2\text{ mV/K}$, biểu thức tổng quát $V_{OV,\text{ZTC}} \approx \frac{\alpha\,\kappa_{VT}\,T_0}{k_\mu}$ hạ điểm ZTC đo thực tế về quanh $\approx 180\text{–}350\text{ mV}$.

- **Hệ quả thiết kế cực kỳ quan trọng (`Temperature Inversion` ở nguồn thấp):**
  - Ở vùng vượt ngưỡng lớn ($V_{OV} > V_{OV,\text{ZTC}}$, thường gặp ở công nghệ cũ $3.3\text{ V}/5\text{ V}$): sự suy giảm độ linh động $\mu(T)$ thắng thế $\implies$ nhiệt độ tăng làm dòng $I_D$ **giảm** ($\partial I_D/\partial T < 0$).
  - Ở vùng vượt ngưỡng nhỏ và dưới ngưỡng ($V_{OV} < V_{OV,\text{ZTC}}$, điển hình ở công nghệ nanomet $V_{DD} \le 1.0\text{ V}$ khi $V_{OV} \approx 50\text{–}120\text{ mV}$!): sự sụt giảm ngưỡng $V_{TH}(T)$ thắng thế tuyệt đối $\implies$ **nhiệt độ tăng làm dòng $I_D$ TĂNG VỌT ($\partial I_D/\partial T > 0$, đảo chiều hệ số nhiệt!)**, khiến góc chậm nhất về tốc độ đôi khi chuyển từ `(SS, +125 °C)` sang **`(SS, -40 °C)`**!

### 2.5. Lượng tử hóa Bề rộng và Điện tích Kênh trong `3D FinFET` (Chương 2 §2.5, tr. 36–37)
Trên một vây silicon thẳng đứng có bề dày đỉnh $W_F$ (hay $T_{\text{fin}} \approx 5\text{–}8\text{ nm}$) và chiều cao vây $H_F$ ($H_{\text{fin}} \approx 35\text{–}55\text{ nm}$) do nhà máy cố định cứng bằng công nghệ khắc vách ngăn tự căn chỉnh, dòng điện chảy trên **ba mặt của vây** (hai vách bên + đỉnh vây). Khi ghép song song $N_{\text{fin}}$ vây nguyên trên một transistor (Hình 2.43), bề rộng kênh dẫn hiệu dụng bị **lượng tử hóa rời rạc**:

$$W_{\text{eff}} = N_{\text{fin}} \cdot \left(2 H_{\text{fin}} + T_{\text{fin}}\right), \qquad N_{\text{fin}} \in \{1, 2, 3, \dots\}$$

*Ví dụ định lượng (Razavi §2.5):* Với $T_{\text{fin}} = 6\text{ nm}$ và $H_{\text{fin}} = 50\text{ nm}$, mỗi vây đơn vị mang bề rộng hiệu dụng cố định $W_{1\text{fin}} = 2(50) + 6 = 106\text{ nm}$. Kỹ sư **không thể** chọn $W = 150\text{ nm}$; chỉ có thể chọn $N_{\text{fin}} = 1$ ($106\text{ nm}$) hoặc $N_{\text{fin}} = 2$ ($212\text{ nm}$)! Đổi lại, cổng bao ba mặt ép hệ số sườn dưới ngưỡng $\zeta \to 1.05$ ($S \approx 63\text{–}68\text{ mV/dec}$), dập tắt DIBL và nâng độ lợi nội tại $g_m r_O$ từ $\sim 7$ (ở `28nm` phẳng) vọt trở lại $15\text{–}30$!

---

## 3. Bất biến Cấu trúc & Các Bẫy Lỗi Kinh điển (Structural Invariants & Traps)

- **`[INV-MOD-01]` Bất biến Khớp Cặp Bằng Cùng Một Ô Phân loại Mô hình (`Same Model-Bin Matching`):**
  Hai transistor lập tỉ số trong gương dòng hoặc cặp vi sai bắt buộc phải nằm trong **cùng một ô `model bin`** (tốt nhất có cùng chiều dài $L$ và cùng chiều rộng ngón đơn vị $W_{\text{finger}}$, chỉ nhân bội số `m` hoặc `nf`), tuyệt đối không để một linh kiện nằm sát dưới ranh giới bin ($L = 0.49\,\mu\text{m}$) còn linh kiện kia nhảy sang bin kế tiếp ($L = 0.51\,\mu\text{m}$) gây bước nhảy giả tạo trên $V_{TH}$ và $g_{ds}$!
- **`[INV-MOD-02]` Bất biến Bật Tham số Phụ thuộc Bố cục (`LOD / WPE`) Ngay Từ Schematic:**
  Trong mô hình BSIM4 từ `90nm` trở xuống, kết quả mô phỏng schematic chỉ khớp với sau layout (`PEX`) nếu các tham số khoảng cách mép khuếch tán `sa, sb` (`STI stress / LOD`) và khoảng cách mép giếng `sca, scb, scc` (`WPE` — `T2196`) trên Pcell được ước lượng sát với bố cục có gắn ngón giả (`dummy fingers`) thực tế.
- **`[TRAP-MOD-01]` Bẫy Quên Dòng Rò Cổng $I_G$ của Transistor Lõi Oxit Mỏng (`65nm/45nm`) trên Nút Giữ Tụ:**
  Dùng MOSFET `core 1.0V` diện tích lớn ($W \times L = 200\,\mu\text{m} \times 2\,\mu\text{m}$) làm tụ lọc vòng PLL `topo-charge-pump-type2-pll` hoặc làm cặp đầu vào bộ tích phân hằng số thời gian giây: ở `65nm` oxit $\text{SiON}$ dày $1.4\text{ nm}$, mật độ dòng rò cổng có thể lên tới vài chục $\text{nA}/\mu\text{m}^2$ ở $125\,^\circ\text{C}$, rút cạn điện tích tụ lọc vòng sinh vạch phổ giả tham chiếu khổng lồ! *Cách chữa:* Luôn dùng tụ `MOM`/`MIM` hoặc MOSFET `I/O thick-oxide` ($1.8\text{ V}/2.5\text{ V}$ có $t_{ox} > 4\text{ nm} \implies I_G \approx 0$) cho các nút tích phân tĩnh!
- **`[TRAP-MOD-02]` Bẫy Sai Khác Góc Tốc độ Chậm Nhất do Đảo Chiều Nhiệt độ (`Temperature Inversion`):**
  Thói quen từ công nghệ $0.35\,\mu\text{m}$ khiến nhiều kỹ sư chỉ kiểm tra tốc độ chậm nhất ở `(SS, VDD_min, +125 °C)`. Ở mạch điện áp thấp $0.9\text{ V}$ phân cực dưới điểm `ZTC` ($V_{OV} < 150\text{ mV}$), tại `-40 °C` ngưỡng $V_{TH}$ tăng thêm $\sim 100\text{ mV}$ bóp nghẹt dòng phân cực và hỗ dẫn khiến **`(SS, VDD_min, -40 °C)` mới là góc chậm nhất và dễ sập khoảng dự trữ bão hòa nhất**!
- **`[TRAP-MOD-03]` Bẫy Tụ Rìa Cực Lớn (`3D Fringing Capacitance`) trong FinFET:**
  Mặc dù FinFET có $g_m r_O$ tuyệt vời ở tần số thấp, cấu trúc cổng kim loại cao dựng đứng đối diện trực tiếp với cột tiếp xúc nguồn/máng (`raised S/D epi + local interconnect`) làm điện dung rìa $C_{GD,\text{fringe}}$ và điện trở nối tiếp nguồn/máng $R_{SD}$ lớn hơn hẳn MOSFET phẳng, làm giảm $f_T / f_{\max}$ sau khi trích xuất ký sinh `PEX` tới $25\%\text{–}40\%$!

---

## 4. Lộ trình Nâng cấp Cấu trúc & Bát giác Đánh đổi (Upgrade Paths & Design Octagon)

Trong **Bát giác Thiết kế (`concept-analog-design-octagon`)**, việc thấu hiểu vật lý mô hình linh kiện giúp kỹ sư chọn đúng **Chủng loại Linh kiện (`Device Flavor`: Core RVT/LVT/HVT vs Analog Native vs Thick-Oxide I/O)** trước khi chọn cấu trúc mạch:
- **Từ Công thức Tay Kênh dài sang Định cỡ Tra bảng Chuẩn hóa:** Liên kết trực tiếp với `law-short-channel-effects` và nâng cấp phương pháp tính toán lên `tech-nanometer-vdsmin-gmid-sizing` cùng nghiên cứu thực nghiệm `tech-nanometer-opamp-design-case-studies`.
- **Quản trị Biến thiên Góc Công nghệ & Nhiệt độ:** Phối hợp chặt chẽ với `concept-process-corners-and-temperature` để quét bao phủ cả 5 góc `{TT, FF, SS, FS, SF}` ở cả `-40 °C` lẫn `+125 °C`.

| Đặc trưng Mô hình & Vật lý | SPICE Level 1–3 Cổ điển | BSIM4 Phẳng Nanomet (`90nm–28nm`) | BSIM-CMG `3D FinFET` (`16nm–3nm`) |
| :--- | :--- | :--- | :--- |
| **Tính liên tục giải tích ($I_D, g_m, g_{ds}$)** | Gãy khúc tại $V_{TH}$ và $V_{DS,\text{sat}}$ | **Liên tục trơn $C^\infty$** toàn miền qua hàm $V_{gsteff}$ | **Liên tục trơn $C^\infty$** dựa trên thế bề mặt vật lý |
| **Bảo toàn điện tích quá độ** | Không (mô hình Meyer gây sụt áp giả) | **Có** (ma trận điện tích 4 cực Ward–Dutton) | **Có** (điện tích 3D bao gồm tụ rìa vách vây) |
| **Độ lợi nội tại $g_m r_O$ (tại $2\,L_{\min}$)** | Dự báo sai (quá cao $\sim 50\text{–}100$) | Thấp ($6\text{–}12$) do DIBL & cấy túi Halo | **Khôi phục mạnh ($15\text{–}30$)** nhờ cổng 3 mặt |
| **Tự do chọn kích thước hình học** | $W, L$ liên tục tùy ý | $W, L$ liên tục (chú ý ranh giới bin & STI/WPE) | **$W$ lượng tử hóa theo $N_{\text{fin}}$**, $L$ chỉ có vài giá trị rời rạc! |
| **Dòng rò cổng $I_G$ & `ZTC`** | Không mô hình hóa ($I_G = 0$) | $I_G$ đáng kể ở `SiON` `65nm`; `ZTC` tại $V_{OV} \approx 0.2\text{ V}$ | Điện môi `High-k Metal Gate` nén $I_G$; tự nung nóng (`self-heating`) cao |

---

## 5. Thích ứng Đa Tiến trình (90nm / 65nm / 45nm) & Cách Kiểm chứng trong Cadence / Spectre

### 5.1. Chiến lược Chọn Chủng loại MOSFET Đa Tiến trình (`Device Flavor Selection`)
1. **Ở `90nm` / `65nm` (Oxit cổng $\text{SiON}$, $V_{DD,\text{core}} = 1.0\text{–}1.2\text{ V}$, $V_{DD,\text{IO}} = 2.5\text{ V}/1.8\text{ V}$):**
   - Khối tham chiếu `Bandgap`, `LDO` đầu vào nguồn cao và công tắc giữ điện tích thời gian dài: ưu tiên dùng transistor `I/O 1.8V/2.5V` để có $I_G \approx 0$ và khoảng dự trữ rộng.
   - Khối `OTA`, `SAR ADC`, `PLL` tốc độ cao dùng nguồn $1.0\text{ V}$: dùng transistor `RVT` (hoặc `LVT` thận trọng cho công tắc/cặp đầu vào ở nguồn $0.9\text{ V}$, nhưng kiểm tra kỹ dòng rò dưới ngưỡng ở `FF, 125 °C`!).
2. **Ở `45nm` / `28nm` (`High-k Metal Gate`, $V_{DD} = 0.9\text{–}1.0\text{ V}$) và `FinFET`:**
   - Công nghệ `HKMG` giảm dòng rò cổng đi hàng trăm lần so với `65nm` oxit thường, nhưng làm tăng hiệu ứng bẫy điện tích gây nhiễu $1/f$ ở kênh nhỏ; trong `FinFET`, thay vì thay đổi $W$ liên tục, mọi tỉ số gương dòng và cặp vi sai phải thiết kế bằng **tỉ số nguyên của số vây mỗi ngón ($N_{\text{fin}}$) nhân với số ngón (`nf`) và hệ số nhân (`m`)**!

### 5.2. Kịch bản Kiểm chứng Mô hình Linh kiện, Điểm ZTC và Dòng Rò trong Spectre
Trước khi bắt tay thiết kế bất kỳ mạch mới nào trên một PDK lạ, luôn chạy một testbench khảo sát đặc trưng một transistor đơn vị để kiểm tra tính liên tục đạo hàm qua các bin, tìm chính xác tọa độ `ZTC` và đo trần dòng rò cổng $I_G$:

```spice
// Spectre Characterization Testbench: Quet ZTC Point, gm*ro & Gate Leakage IG (BSIM4)
simulator lang=spectre
parameters vgs_val=0.5 vds_val=0.5 l_val=180n

Vgs (g 0) vsource dc=vgs_val
Vds (d 0) vsource dc=vds_val
Vbs (b 0) vsource dc=0

// Luon khai bao uoc luong sa/sb (STI) sat voi thuc te layout co 2 dummy fingers!
M_dut (d g 0 b) nch w=2u l=l_val nf=2 m=1 sa=0.35u sb=0.35u

// 1. Quet VGS qua 3 nhiet do (-40C, 27C, 125C) de dinh vi chinh xac giao diem ZTC!
swp_ztc sweep param=temp values=[-40 27 125] {
    dc_vgs dc param=vgs_val start=0 stop=1.1 step=5m
}

// 2. Kiem tra su lien tuc cua gm*ro va tran dong ro cuc cong IG tai 125 degC
save M_dut:id M_dut:gm M_dut:gds M_dut:ig M_dut:vth M_dut:vdsat
chk_ig assert dev=M_dut param=ig min=-1n max=1n level=warning \
    info="CANH BAO BSIM4: Dong ro cuc cong IG vuot 1 nA - khong dung lam nut giu dien tich tinh!"
```

---

## 6. Mốc Đối chiếu Sách Razavi & Thuật ngữ Chuẩn CLB

| Mục Sách Razavi (2nd Ed.) | Trang & Phương trình | Nội dung Đối chiếu Trọng tâm | Mã Thuật ngữ Chuẩn CLB |
| :--- | :--- | :--- | :--- |
| **§17.3.1–17.3.3 Level 1–3** | Tr. 701–706, Eq. `(17.32)–(17.47)`, Fig. `17.13–17.15` | Hạn chế của Level 1, điểm gãy khúc đạo hàm $g_{ds}$ ở $V_{DS,\text{sat}}$ của Level 2 và bán thực nghiệm Level 3 | `T809` (mô hình kênh dài), `T1835` (các hiệu ứng kênh ngắn), `T737` (chiều dài hiệu dụng) |
| **§17.3.4–17.3.5 BSIM & EKV** | Tr. 706–707, Eq. `(17.48)–(17.50)` | Công thức nội suy hình học theo $1/L_{\text{eff}}, 1/W_{\text{eff}}$, ghép nối trơn vùng nghịch đảo yếu–mạnh, mô hình BSIM4 và EKV | `T1831` (mô hình BSIM4), `T810` (vùng dưới ngưỡng), `T808` / `T1963` (dòng rò cực cổng), `T2187` (hiệu suất hỗ dẫn $g_m/I_D$) |
| **§17.3.6 Charge Modeling** | Tr. 707–708, Fig. `17.16` | Hiện tượng không bảo toàn điện tích gây sụt áp giả của mô hình Meyer và kịch bản chia điện tích kênh `40/60, 50/50, 0/100` | `T054` (MOSFET), `T1961` (các dòng rò), `T2180` (bão hòa vận tốc), `T2181` (DIBL) |
| **§17.3.7–17.4 Temp & Corners** | Tr. 708–710, Eq. `(17.51)–(17.53)`, Fig. `17.17–17.20` | Sự biến thiên $E_g(T)$, $\mu(T) \propto T^{-3/2}$, điểm giao cắt hệ số nhiệt bằng không `ZTC` và bao hình 5 góc quy trình | `T2185` (điểm phân cực ZTC), `T2186` (các góc quy trình TT/FF/SS/FS/SF), `T069` (biến thiên PVT) |
| **Ch.2 §2.5 Appendix A: FinFETs** | Tr. 36–37, Fig. `2.42–2.44` | Cấu trúc vây silicon 3 mặt cổng, khôi phục đặc tuyến gần luật bình phương và lượng tử hóa bề rộng $W = N_{\text{fin}}(2 H_F + W_F)$ | `T043` (transistor hiệu ứng trường dạng vây — FinFET), `T031` (thu nhỏ kích thước linh kiện) |
