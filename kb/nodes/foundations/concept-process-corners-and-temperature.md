---
{
  "id": "concept-process-corners-and-temperature",
  "kind": "concept",
  "domain": "foundations",
  "title_vi": "Sự phụ thuộc nhiệt độ, điểm bù nhiệt ZTC và các góc công nghệ chế tạo PVT (Temperature Dependence & Process Corners)",
  "title_en": "MOS Temperature Dependence, Zero-TC Point, and PVT Process Corners",
  "summary": "Cơ chế vật lý đối kháng giữa suy giảm độ linh động mu(T) và giảm điện áp ngưỡng VTH(T) khi tăng nhiệt độ (tạo điểm ZTC và hiện tượng đảo chiều hệ số nhiệt ở áp thấp), cùng bản chất 5 góc công nghệ số (TT, FF, SS, FS, SF) và lý do mạch tương tự đạt chuẩn ở góc TT vẫn có thể thất bại thảm khốc trên silicon.",
  "diagram": "../../diagrams/short-channel-iv-gmid.svg",
  "razavi_refs": [
    {
      "chapter": 17,
      "section": "17.2.1, 17.3.7-17.4",
      "pages": "695-696, 708-710",
      "equations": ["17.18", "17.51", "17.52"]
    },
    {
      "chapter": 11,
      "section": "11.5.2",
      "pages": "493",
      "equations": []
    }
  ],
  "glossary_codes": ["T069", "T073", "T703", "T710", "T1082", "T1207", "T1211", "T1713", "T1867", "T1944", "T1946", "T2029", "T2068", "T2072"],
  "process_agnostic": true,
  "roles": {
    "thermal_mobility_vs_vth_competition": "Hai xu hướng nhiệt đối dấu (mu giảm theo T^-1.5 đối lập VTH giảm ~1-2 mV/K) quyết định chiều trôi của ID, gm và VDS,sat",
    "five_digital_speed_corners": "Bao hình chữ nhật tốc độ NMOS x PMOS (TT, FF, SS, FS, SF) sàng lọc phiến wafer đạt năng suất chế tạo",
    "pvt_signoff_envelope": "Ma trận tổ hợp Góc quy trình x Nguồn cấp x Nhiệt độ cộng biến thiên điện trở/tụ thụ động để bảo đảm mạch sống trên mọi lô chip"
  },
  "symptoms_addressed": [
    "circuit-passes-tt-27c-but-fails-ss-high-temp-or-sf-fs",
    "headroom-crush-at-ss-cold-or-hot-extremes",
    "phase-margin-collapse-at-ff-low-temp",
    "fixed-vgs-bias-runaway-across-corners-and-temperature"
  ],
  "limitations": [
    "digital-speed-corners-do-not-capture-local-random-mismatch-or-passive-rc-corners-automatically",
    "montecarlo-statistical-models-required-for-offset-and-mirror-yield"
  ],
  "checklists": ["common-mos", "current-mirror"]
}
---

## 1. Bản chất Nguyên lý, Sơ đồ Mạch & Vai trò Từng Nhánh Cấu trúc

Một thiết kế tương tự chạy hoàn hảo tại điểm danh định (`TT`, $V_{DD,\text{nom}}$, $T = 27^\circ\text{C} = 300\,\text{K}$) chỉ mới hoàn thành chưa tới $30\%$ chặng đường ra chip thực tế (Razavi Chương 11 §11.5.2 tr. 493 & Chương 17 §17.3.7–17.4 tr. 708–710). Khác với transistor lưỡng cực vốn có quan hệ hàm mũ $I_C\text{–}V_{BE}$ gắn chặt với các hằng số vật lý cơ bản ít đổi từ lô wafer này sang lô wafer khác, MOSFET chịu sự biến thiên tham số rất lớn theo **quy trình chế tạo (Process — $P$: $t_{ox}, V_{TH0}, L_D, W_{\text{eff}}, R_{\square}, C_{\text{unit}}$)**, **điện áp nguồn cấp (Voltage — $V$: thường $\pm 5\%$ đến $\pm 10\%$)** và **nhiệt độ tuyệt đối (Temperature — $T$: ví dụ $0^\circ\text{C}\dots 85^\circ\text{C}$ thương mại hoặc $-40^\circ\text{C}\dots 125^\circ\text{C}$ công nghiệp/ô tô)**.

![Sự dịch chuyển đặc tuyến I–V và gm/ID dưới tác động vật lý kênh ngắn và môi trường](../../diagrams/short-channel-iv-gmid.svg)

Để không thiết kế mù trong sương mù, kỹ sư phải nắm vững **hai cơ chế vật lý nền tảng**:
1. **Cuộc giằng co Nhiệt độ bên trong MOSFET (§17.2.1 & §17.3.7):** Khi nhiệt độ tuyệt đối $T$ tăng lên, năng lượng vùng cấm silic $E_g(T)$ thu hẹp làm nồng độ hạt tải nội tại $n_i(T)$ tăng mạnh, kéo **điện áp ngưỡng $|V_{TH}(T)|$ giảm xuống** (muốn làm **tăng** dòng $I_D$). Đồng thời, dao động mạng tinh thể (phonon scattering) mạnh hơn làm **độ linh động hạt tải $\mu(T)$ giảm xuống** (muốn làm **giảm** dòng $I_D$)! Hai cơ chế ngược chiều này cắt nhau tại một điểm cân bằng gọi là **điểm hệ số nhiệt bằng không (Zero-Temperature-Coefficient, ZTC point)**.
2. **Bao hình Góc Công nghệ Chế tạo (Process Corners — Hình 17.17–17.18, §17.4):** Để cân bằng giữa yêu cầu phương sai hẹp của kỹ sư thiết kế và năng suất thu hồi wafer (yield) của nhà máy Fab, kỹ sư công nghệ đóng khung tốc độ trễ cổng của NMOS và PMOS vào một hình chữ nhật trên mặt phẳng $(\text{NFET speed}, \text{PFET speed})$ gồm tâm danh định **TT** (*Typical–Typical*) và **4 góc cực trị**: **FF** (*Fast–Fast*), **SS** (*Slow–Slow*), **FS** (*Fast NMOS – Slow PMOS*), và **SF** (*Slow NMOS – Fast PMOS*).

---

## 2. Hệ Phương trình Cốt lõi & Tư duy "Nhìn Mạch Đọc Nhanh" (Analysis by Inspection)

### 2.1. Hệ Phương trình Phụ thuộc Nhiệt độ và Điểm ZTC
Trong các mô hình SPICE/BSIM (§17.3.7, Phương trình 17.51–17.52, tr. 708 & §17.2.1 tr. 695–696):
1. **Năng lượng vùng cấm của Silic giảm khi tăng $T$:**
   $$E_g(T) = 1.16 - \frac{7.02 \times 10^{-4}\,T^2}{T + 1108}\;(\text{eV})$$
   *(Tại $T = 300\,\text{K}$, $E_g \approx 1.115\,\text{eV}$ và $\partial E_g / \partial T \approx -0.267\,\text{meV/K} \approx -0.27\,\text{meV/K}$ — thông số gốc quyết định độ cong bậc hai của mạch tham chiếu vùng cấm Bandgap ở Chương 12, xem Bài tập 17.14!).*
2. **Độ linh động hạt tải giảm theo lũy thừa âm của nhiệt độ:**
   $$\mu(T) = \mu(T_0)\left(\frac{T_0}{T}\right)^{k_\mu}, \qquad T_0 = 300\,\text{K}, \quad k_\mu \approx 1.5\;(\text{thực tế } 1.2\text{–}2.0)$$
3. **Điện áp ngưỡng giảm gần tuyến tính theo nhiệt độ:**
   $$V_{TH}(T) \approx V_{TH}(T_0) + \alpha_{VTH}(T - T_0), \qquad \alpha_{VTH} = \frac{\partial V_{TH}}{\partial T} \approx -1.0 \text{ đến } -2.0\,\text{mV/K}$$
4. **Độ dốc dưới ngưỡng suy thoái tuyến tính theo $T$ (Chú thích 2, tr. 696):**
   $$S(T) = 2.3\,\frac{kT}{q}\left(1 + \frac{C_d}{C_{ox}}\right) \propto T$$
   Khi lên $125^\circ\text{C}$ ($398\,\text{K}$), vừa $V_{TH}$ giảm đi $\sim 100\text{–}180\,\text{mV}$, vừa $S(T)$ tăng thêm $33\%$ ($398/300$), khiến **dòng rò tắt dưới ngưỡng $I_{\text{off}}$ tăng vọt hàng chục đến hàng trăm lần** so với ở $27^\circ\text{C}$!

**Giải tích Điểm Hệ số Nhiệt Bằng Không (ZTC Point) khi giữ $V_{GS}$ cố định:**
Xét phương trình luật bình phương $I_D(T) = \frac{1}{2}\mu(T) C_{ox}\frac{W}{L}[V_{GS} - V_{TH}(T)]^2$ với $\mu(T) \propto T^{-3/2}$. Lấy đạo hàm logarit $\frac{1}{I_D}\frac{\partial I_D}{\partial T} = 0$:

$$-\frac{3}{2 T} + \frac{2\,(-\alpha_{VTH})}{V_{GS} - V_{TH}(T)} = 0 \quad \Longrightarrow \quad V_{OV,\text{ZTC}} = V_{GS,\text{ZTC}} - V_{TH}(T_0) = \frac{4}{3}|\alpha_{VTH}| T_0$$

Thay $|\alpha_{VTH}| \approx 1.5\,\text{mV/K}$ và $T_0 = 300\,\text{K}$, ta thu được mốc trực giác cực kỳ sắc bén:
$$V_{OV,\text{ZTC}} \approx 0.6\,\text{V} \quad (\text{thực tế trên BSIM4 khoảng } 0.45\text{–}0.7\,\text{V})$$
- **Hệ quả Đảo chiều Hệ số Nhiệt ở Thiết kế Điện áp Thấp Hiện đại:**
  - Nếu phân cực ở **$V_{OV}$ lớn** ($> V_{OV,\text{ZTC}}$, thường gặp ở mạch cao áp cũ): sự suy giảm $\mu(T)$ thắng thế $\Rightarrow$ khi nóng lên, $I_D$ **giảm** (tự ổn định nhiệt).
  - Trong **hầu hết mạch tương tự nanomet nguồn $\le 1.2\,\text{V}$**, ta luôn phân cực ở **$V_{OV} \approx 80\text{–}250\,\text{mV} < V_{OV,\text{ZTC}}$**! Ở vùng này:
    - Nếu giữ **$V_{GS}$ cố định**: sự sụt giảm $V_{TH}(T)$ thắng thế tuyệt đối $\Rightarrow$ khi nóng lên, $I_D$ **tăng vọt**!
    - Nếu giữ **dòng phân cực $I_D$ cố định** (nhờ gương dòng từ nguồn dòng hằng định): vì $\mu(T)$ giảm mạnh ở nhiệt độ cao ($125^\circ\text{C}$), để duy trì cùng dòng $I_D$, điện áp vượt ngưỡng $V_{OV}(T) = \sqrt{\frac{2 I_D}{\mu(T) C_{ox} W/L}} \propto T^{+3/4}$ **tăng lên** (ăn mất nhiều khoảng dự trữ $V_{DS,\min}$ hơn ở nhiệt độ cao!), đồng thời **độ hỗ dẫn $g_m = \sqrt{2\mu(T)C_{ox}(W/L)I_D} \propto T^{-3/4}$ giảm xuống** khoảng $15\%\text{–}20\%$ tại $125^\circ\text{C}$! *(Vì lẽ đó, ở Chương 12 Razavi giới thiệu phân cực dòng **PTAT** $I_D \propto T$ để bù lại sự sụt giảm của $\mu(T)$ và giữ $g_m$ ổn định hơn theo nhiệt độ!).*

### 2.2. Tư duy "Nhìn Mạch Đọc Nhanh" Tác động của 5 Góc Công nghệ (Bài tập 17.15–17.16, tr. 710)
Ở góc **Fast (F)**, lớp oxit mỏng hơn ($C_{ox}$ lớn hơn, $\mu C_{ox}$ lớn hơn), $L_{\text{eff}}$ ngắn hơn nhẹ và $|V_{TH}|$ thấp hơn; ở góc **Slow (S)**, $t_{ox}$ dày hơn ($\mu C_{ox}$ nhỏ hơn), $L_{\text{eff}}$ dài hơn và $|V_{TH}|$ cao hơn:

| Góc tổ hợp nguy hiểm | Chuyện gì xảy ra bên trong mạch tương tự? | Chỉ tiêu nào dễ gãy nhất? |
|---|---|---|
| **`SS` + $V_{DD,\min}$ + $T_{\min}$ (`-40°C`)** | $|V_{TH}|$ đạt cực đại tuyệt đối (vừa góc Slow vừa trời lạnh tăng $|V_{TH}|$ thêm $\sim 100\,\text{mV}$!) trong khi $V_{DD}$ sụt thấp nhất | **Sập tổng điện áp chuỗi cổng–nguồn** ($V_{GS,1} + V_{GS,2} + V_{DS,\text{tail}} > V_{DD}$), khóa cứng ICMR, mạch khởi động (startup) không bật nổi! |
| **`SS` + $V_{DD,\min}$ + $T_{\max}$ (`125°C`)** | Độ linh động $\mu$ rơi xuống đáy tuyệt đối $\Rightarrow$ với dòng $I_D$ cố định, $V_{DS,\text{sat}}$ phình to cực đại còn $g_m$ tụt thấp nhất | **Mất bão hòa (rơi vào Triode)** ở ngăn xếp cascode/đầu ra, **sụt GBW / tốc độ xác lập $t_s$**, tăng nhiễu nhiệt $4kT\gamma/g_m$! |
| **`FF` + $V_{DD,\max}$ + $T_{\min}$ (`-40°C`)** | $\mu C_{ox}$ cực đại, $L_{\text{eff}}$ ngắn nhất $\Rightarrow g_m$ tăng vọt kéo $\text{GBW}$ vọt cao, trong khi $r_o$ giảm do kênh ngắn hơn & DIBL mạnh | **Mất dự trữ pha (Phase Margin sập $\rightarrow$ tự kích dao động!)**, sụt độ lợi vòng hở DC $A_0$, vọt dòng công suất tĩnh! |
| **`FF` + $V_{DD,\max}$ + $T_{\max}$ (`125°C`)** | $|V_{TH}|$ chạm đáy tuyệt đối + $S(T)$ phình to + nguồn $V_{DD}$ cao nhất | **Dòng rò tắt $I_{\text{off}}$ bùng nổ**, công tắc lấy mẫu rò làm trôi áp trên tụ giữ mẫu, nguy cơ quá nhiệt hoặc latch-up! |
| **Góc lệch chéo `FS` và `SF`** | NMOS mạnh – PMOS yếu (hoặc ngược lại) làm lệch hẳn $|V_{GS,P}|$ so với $V_{GS,N}$ | **Trôi mức DC tầng đẩy–kéo CMOS**, lệch dòng nạp/xả Charge Pump PLL, lệch điểm chuyển mạch cảm biến CMFB nguồn–bám (Hình 11.27)! |

### 2.3. Giải tích So sánh 2 Phương thức Phân cực Qua 4 Góc Công nghệ (Bài tập 17.15 & 17.16 Razavi, Hình 17.20, tr. 710)
Xét hai tầng khuếch đại nguồn chung: Hình 17.20(a) tải nguồn dòng PMOS $M_2$, và Hình 17.20(b) tải nối diode PMOS $M_2$. Giả sử góc Fast (`F`) có $\mu C_{ox}$ lớn hơn và góc Slow (`S`) có $\mu C_{ox}$ nhỏ hơn:

1. **Trường hợp 1 — Phân cực chuẩn tại Dòng tĩnh $I_D$ không đổi (Bài tập 17.15, nhờ gương dòng):**
   - Trong Hình 17.20(a) (tải nguồn dòng, $|A_v| = g_{m1}(r_{o1}\parallel r_{o2})$): với $I_D$ hằng định, $r_{o1}\parallel r_{o2} \approx \frac{1}{(\lambda_n + \lambda_p)I_D}$ ít đổi bậc một, còn $g_{m1} = \sqrt{2(\mu_n C_{ox})(W/L)_1 I_D}$ tăng ở góc `FN` (`FF`, `FS`) và giảm ở góc `SN` (`SS`, `SF`). Do đó ở góc `SS`, độ lợi giảm nhẹ theo $\sqrt{\mu_n C_{ox}}$ và công suất nhiễu nhiệt ngõ vào $\overline{V_{n,\text{in}}^2} = 4kT\gamma\left(\frac{1}{g_{m1}} + \frac{g_{m2}}{g_{m1}^2}\right)$ tăng vừa phải (đặc biệt ở góc `SF` khi NMOS chậm $g_{m1}\downarrow$ mà PMOS nhanh $g_{m2}\uparrow$!).
   - Trong Hình 17.20(b) (tải nối diode PMOS, $|A_v| = g_{m1}/g_{m2} = \sqrt{\frac{\mu_n C_{ox}(W/L)_1}{\mu_p C_{ox}(W/L)_2}}$): ở các góc đồng hướng `FF` và `SS`, cả $\mu_n C_{ox}$ lẫn $\mu_p C_{ox}$ cùng tăng hoặc cùng giảm nên **tỉ số độ lợi gần như tự bù hoàn hảo**! Thế nhưng ngay tại hai góc chéo **`FS` và `SF`**, tử số và mẫu số biến thiên **ngược chiều nhau** làm độ lợi biến động cực đại!
2. **Trường hợp 2 — Phân cực sai lầm bằng $V_{GS}$ cố định (Bài tập 17.16):**
   - Khi cố định $V_{GS1}$ và $V_{SG2}$, dòng tĩnh $I_D = \frac{1}{2}\mu C_{ox}\frac{W}{L}(V_{GS} - V_{TH})^2$ biến động dữ dội theo cả $\mu C_{ox}$ lẫn bình phương độ trôi $V_{TH}$!
   - Nghiêm trọng nhất là ở Hình 17.20(a) tại góc chéo **`FS`** (NMOS nhanh muốn hút dòng $I_{D1}$ cực lớn, trong khi PMOS chậm chỉ cấp được dòng $|I_{D2}|$ nhỏ): không có cơ chế tự cân bằng dòng, cực máng ngõ ra lập tức bị kéo sập sát $0\,\text{V}$, ép $M_1$ chìm sâu vào vùng triode và **phá hủy hoàn toàn chức năng khuếch đại**!
   - Phép đối chiếu hai bài tập cuối Chương 17 này chứng minh bằng toán học vì sao mọi tầng khuếch đại IC bắt buộc phải neo theo dòng tĩnh (current-mode biasing) kết hợp CMFB hoặc hồi tiếp DC!

---

## 3. Bất biến Cấu trúc & Các Bẫy Lỗi Kinh điển (Structural Invariants & Traps)

- **[INV-PVT-01] Cấm Tuyệt đối Phân cực Cực Cổng bằng Nguồn Áp Cố định Độc lập Quy trình (Bài tập 17.15 vs 17.16):** Nếu đặt một điện áp $V_{GS}$ cố định (ví dụ chia áp bằng hai điện trở từ $V_{DD}$), khi quét từ `SS, -40°C` sang `FF, 125°C`, sự biến thiên đồng thời của $V_{TH}$, $\mu C_{ox}$ và $V_{DD}$ sẽ làm dòng tĩnh $I_D$ nhảy vọt **$300\%\text{–}1000\%$**! Ngược lại, khi phân cực bằng **gương dòng (`topo-basic-current-mirror`) lấy từ bộ tạo dòng tham chiếu (`tech-supply-independent-bias-and-startup`)**, điện áp $V_{GS}$ tự động điều chỉnh ngược chiều để bù lại hoàn toàn độ lệch $V_{TH}$ toàn cục!
- **[INV-PVT-02] Góc Toàn cục (Global Corners) KHÔNG Thay thế Được Biến thiên Ngẫu nhiên Cục bộ (Local Mismatch):** Cả 5 góc `TT, FF, SS, FS, SF` đều gán **cùng một bộ tham số** cho mọi transistor cùng loại trên mạch — nên một cặp vi sai đối xứng vẽ trên schematic sẽ luôn cho điện áp lệch không $V_{OS} = 0\,\text{V}$ và $\text{CMRR} = \infty$ ở cả 5 góc! Muốn kiểm tra offset, CMRR thực tế và độ khớp gương dòng, bắt buộc phải áp dụng định luật Pelgrom (`law-pelgrom-mismatch-and-sizing-duality`) và chạy mô phỏng thống kê **Monte Carlo (`mismatch` / `all`)**.
- **[INV-PVT-03] Biến thiên Độc lập của Điện trở & Tụ điện Thụ động (`RC Corners`):** Điện trở tấm polysilicon/khuếch tán biến thiên $\pm 20\%\text{–}30\%$ và tụ MIM/MOM biến thiên $\pm 10\%\text{–}15\%$ theo quy trình chế tạo **hoàn toàn độc lập** với góc `FF/SS` của MOSFET! Do đó, mọi hằng số thời gian hay điện trở khử zero $R_z$ nếu dùng điện trở thụ động cố định sẽ trượt khỏi $1/g_{m2}$ tới $\pm 40\%$ qua PVT (phải dùng MOSFET vùng triode bám theo $1/g_{m2}$ ở `tech-miller-rhp-zero-nulling-and-cascode-comp`!).

- **[TRAP-PVT-01] Bẫy Thiết kế "Vừa Khít Chỉ tiêu" tại Góc `TT, 27°C`:** Nếu tại `TT, 27°C` mạch vừa đủ $A_0 = 505$ (chỉ tiêu $\ge 500$), $\text{PM} = 60.5^\circ$ (chỉ tiêu $\ge 60^\circ$) và $t_s = 4.9\,\text{ns}$ (chỉ tiêu $\le 5\,\text{ns}$), thì chắc chắn 100% mạch sẽ rớt `A0` ở góc `FF`, rớt `ts` ở góc `SS, 125°C` và rớt `PM` ở `FF, -40°C`! Nguyên tắc thực chiến (Razavi tr. 493): tại `TT, 27°C` phải chừa biên dự phòng thiết kế (*overdesign margin*) tối thiểu $20\%\text{–}35\%$ cho Gain, Bandwidth và ít nhất $8^\circ\text{–}10^\circ$ cho Phase Margin.
- **[TRAP-PVT-02] Bẫy Bỏ qua Góc Chéo `FS` / `SF` trong Mạch Không Hồi tiếp DC:** Trong các mạch ghép tầng trực tiếp dùng tỷ lệ $V_{GS,N} / |V_{GS,P}|$ (như bộ cảm biến CMFB dùng hai cặp bám nguồn bổ sung ở Phương trình 11.13 tr. 480, hay tầng khuếch đại đảo đẩy–kéo CMOS `topo-cs-current-source-and-active-load`), góc `FS` và `SF` nguy hiểm gấp nhiều lần `FF` và `SS`!

---

## 4. Lộ trình Nâng cấp Cấu trúc & Bát giác Đánh đổi (Upgrade Paths & Design Octagon)

Để chế ngự sự trôi dạt PVT mà không phải tăng gấp ba công suất trên Bát giác `concept-analog-design-octagon`, kiến trúc mạch CMOS tiến hóa qua ba lớp phòng thủ:
1. **Phòng thủ ở Mức Phân cực & Tham chiếu:** Thay phân cực điện trở bằng gương dòng dải rộng `topo-lvccml-wide-swing-mirror`, tạo dòng tham chiếu độc lập nguồn cấp kèm mạch khởi động `tech-supply-independent-bias-and-startup`, tạo dòng phân cực bám hỗ dẫn `tech-ptat-current-and-constant-gm` (giữ $g_m \propto 1/R$ ít phụ thuộc $\mu C_{ox}$ và $T$!), và tạo điện áp chuẩn bù nhiệt bậc một CTAT + PTAT bằng `topo-bandgap-reference-core` hoặc `topo-low-voltage-sub1v-bandgap`.
2. **Phòng thủ ở Mức Tín hiệu & Hồi tiếp:** Đóng vòng hồi tiếp âm độ lợi lớn (`concept-feedback-four-topologies`) để khóa độ lợi vòng kín vào **tỷ số hai linh kiện thụ động cùng loại đặt cạnh nhau** ($R_2/R_1$ hoặc $C_1/C_2$ trong `topo-switched-capacitor-amplifiers-integrators` — biến thiên cùng chiều theo PVT nên tỷ số triệt tiêu đến $< 0.1\%$!).
3. **Phòng thủ ở Mức Bố trí Hình học (Layout):** Ghép cặp đối xứng trọng tâm chung (`tech-common-centroid-sti-wpe-layout`) để khử gradient nhiệt độ và độ dày oxit trên mặt đế.

---

## 5. Thích ứng Đa Tiến trình (90nm / 65nm / 45nm) & Cách Kiểm chứng trong Cadence / Spectre

Ở **90nm / 65nm / 45nm**, tỷ số $V_{TH} / V_{DD}$ tăng cao (ví dụ $V_{TH} \approx 0.35\,\text{V}$ trên nguồn $V_{DD} = 1.0\,\text{V}$ ở 45nm, so với $0.5\,\text{V} / 3.3\,\text{V}$ trước đây). Vì biên độ biến thiên tuyệt đối $\Delta V_{TH,\text{PVT}} \approx \pm 80\text{–}100\,\text{mV}$ hầu như không giảm khi thu nhỏ tiến trình, nó nuốt trọn một tỷ lệ phần trăm khổng lồ của $V_{DD} = 0.9\text{–}1.0\,\text{V}$!

**Ma trận Kiểm định PVT Sign-off Chuẩn trong Cadence ADE Explorer / Assembler (Spectre):**
1. **Khai báo Model Sections chuẩn của PDK:** Trong `Model Libraries`, trỏ tới tệp toplevel `.scs` và cấu hình biến góc cho cả 3 nhóm phần tử:
   - MOSFET (`tt`, `ff`, `ss`, `fnsp`/`fs`, `snfp`/`sf`)
   - Điện trở (`res_typ`, `res_min`/`fast`, `res_max`/`slow`)
   - Tụ điện MIM/MOM (`cap_typ`, `cap_min`, `cap_max`)
2. **Tổ hợp Ma trận Góc Tối thiểu (17–27 Corners trước khi chạy Monte Carlo):**
   - `Nominal`: `(tt, res_typ, cap_typ, VDD_nom, 27°C)`
   - `Extreme Corners`: `{ff, ss, fs, sf} × {VDD_nom * 0.9, VDD_nom * 1.1} × {-40°C, 125°C}` kèm tổ hợp hằng số thời gian cực đại `(ss, res_max, cap_max, VDD_min, 125°C)` (kiểm tra tốc độ xác lập chậm nhất) và cực tiểu `(ff, res_min, cap_min, VDD_max, -40°C)` (kiểm tra dự trữ pha `stb` thấp nhất!).
3. **Kiểm tra Tự động Bất biến Sống còn trên Toàn Ma trận:** Thiết lập biểu thức `Spec` trong ADE Assembler:
   - `min_sat_margin = min(abs(VDS_k) - abs(Vdsat_k)) > 40mV` trên toàn bộ mọi góc!
   - Kiểm tra khởi động nguồn `tran` với xung dốc `VDD` bật từ $0\,\text{V} \rightarrow V_{DD,\min}$ tại góc `ss, -40°C` để chắc chắn mạch không bị kẹt ở điểm chết dòng bằng không!

**Mẫu Kịch bản OCEAN Quét Tự động Ma trận Góc PVT & Tìm Điểm Bù Nhiệt ZTC:**
```ocean
; Quét tự động qua 5 góc công nghệ x 3 mức nhiệt độ và báo cáo biên dự trữ bão hòa nhỏ nhất
corners = list("tt" "ff" "ss" "fs" "sf")
temps   = list(-40 27 125)

foreach(cor corners
  modelFile(list("toplevel_models.scs" cor))
  foreach(tmp temps
    temp(tmp)
    desVar("VDD" if(cor == "ss" then 0.9*VDD_nom else if(cor == "ff" then 1.1*VDD_nom else VDD_nom)))
    analysis('dc ?saveOppoint t)
    analysis('stb ?start 1 ?stop 10G ?probe "/IPRB0")
    run()
    pm_val   = phaseMargin(getData("loopGain" ?result "stb"))
    vmargin1 = abs(pv("/M1" "vds" ?result "dcOpInfo")) - abs(pv("/M1" "vdsat" ?result "dcOpInfo"))
    printf("Corner=%s T=%4dC : PM=%.1f deg | M1_sat_margin=%.1f mV\n"
           cor tmp pm_val vmargin1*1e3)
  )
)
```

| Hiện tượng quan sát được khi chạy ma trận PVT | Nguyên nhân gốc rễ theo Chương 17 | Cách khắc phục triệt để về mặt cấu trúc |
|---|---|---|
| Dòng tổng `IDD` tăng vọt ở `125°C` trên mọi góc | Nhánh phân cực bị neo theo điện áp cố định tại $V_{OV} < V_{OV,\text{ZTC}}$ nên sụt giảm $V_{TH}(T)$ thắng thế | Thay bằng nguồn tham chiếu dòng độc lập nguồn / Bandgap + gương dòng |
| `PM` đạt $62^\circ$ ở `TT, 27°C` nhưng tụt còn $38^\circ$ ở `FF, -40°C` | $\mu(T)$ tăng mạnh ở $-40^\circ\text{C}$ làm $\text{GBW}$ vọt cao vượt gần cực phụ, hoặc $R_z$ thụ động không bám theo $1/g_{m2}$ | Dùng transistor MOSFET vùng triode làm $R_z$ phân cực từ nhánh gương đồng dạng để $R_z \propto 1/g_{m2}$ qua mọi góc PVT! |
| Góc `FS` và `SF` làm lệch mức ra tĩnh tầng đẩy–kéo quá $\pm 200\,\text{mV}$ | Tỷ số cường độ NMOS/PMOS đảo chiều không có vòng hồi tiếp DC khóa mức | Bổ sung vòng hồi tiếp DC / CMFB khóa cứng điểm làm việc tĩnh ngõ ra |

---

## 6. Mốc Đối chiếu Sách Razavi & Thuật ngữ Chuẩn CLB

- **Sách gốc Razavi (2nd Ed.):**
  - Chương 17: §17.2.1 (tr. 695–696: hệ số nhiệt của $V_{TH} \approx -1\,\text{mV/K}$ và độ dốc dưới ngưỡng $S(T)$), §17.3.7 *Temperature Dependence* (tr. 708, Phương trình 17.51–17.52), §17.4 *Process Corners* (tr. 708–709, Hình 17.17–17.18), Bài tập 17.14–17.16 (tr. 710: phân tích độ lợi và nhiễu nhiệt qua 4 góc công nghệ khi phân cực dòng hằng định so với giữ $V_{GS}$ cố định).
  - Chương 1: §1.1.4 *Analog Design Challenges* (mục *PVT Variations*, tr. 4); Chương 11: §11.5.2 (tr. 493: lưu ý bảo toàn biên thiết kế từ góc TT sang SS/FF, dải nhiệt và $\pm 5\%\,V_{DD}$).
- **Thuật ngữ chuẩn CLB Vi Mạch (`THUẬT NGỮ CHUẨN.md`):**
  - `T069` / `T073` / `T1211`: *PVT variations* $\rightarrow$ **Biến thiên PVT** (lưu ý `T069`: *process* trong PVT là **quy trình công nghệ chế tạo**, không phải nút công nghệ hay xử lý tín hiệu).
  - `T1944`: *corner of the process* $\rightarrow$ **Góc công nghệ chế tạo** (`TT`, `FF`, `SS`, `FS`, `SF`).
  - `T703`: *temperature dependence* $\rightarrow$ **Độ phụ thuộc nhiệt độ**; `T2029`: **Các hệ số nhiệt**; `T2068`: **Số mũ phụ thuộc nhiệt độ của độ linh động**; `T2072`: **Nhiệt độ tại đó hệ số nhiệt bằng không**.
