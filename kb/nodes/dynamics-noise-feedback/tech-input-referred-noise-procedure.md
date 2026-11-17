---
{
  "id": "tech-input-referred-noise-procedure",
  "kind": "technique",
  "domain": "dynamics-noise-feedback",
  "title_vi": "Quy trình Quy đổi Nhiễu về Ngõ vào (Vn,in & In,in), Băng thông Nhiễu và Bẫy Tích phân Nhiễu (Input-Referred Noise & Noise Bandwidth)",
  "title_en": "Input-Referred Noise Representation (Vn,in & In,in), Noise Correlation, Noise Bandwidth, and Integration Traps",
  "summary": "Quy trình hai bước chặt chẽ biểu diễn mọi mạng hai cửa tuyến tính có nhiễu bằng một mạng không nhiễu kèm cặp nguồn tương đương (Vn,in nối tiếp, In,in song song), công thức băng thông nhiễu hiệu dụng Bn = (pi/2)*f3dB, và cảnh báo sai lầm chí mạng khi tích phân phổ nhiễu quy về ngõ vào.",
  "diagram": "../../diagrams/mos-noise-input-referred.svg",
  "razavi_refs": [
    {
      "chapter": 7,
      "section": "7.3, 7.8-7.10",
      "pages": "236-243, 264-267",
      "equations": ["7.50", "7.53", "7.55", "7.56", "7.57", "7.60", "7.145", "7.146", "7.148", "7.152"]
    }
  ],
  "glossary_codes": ["T789", "T1063", "T1067", "T1133", "T1135", "T1137", "T1142", "T1146", "T1169", "T1171", "T1172", "T1173"],
  "process_agnostic": true,
  "roles": {
    "series_noise_voltage_vn": "Nguồn điện áp nhiễu tương đương Vn,in đặt nối tiếp ngõ vào, tìm được bằng phép ngắn mạch xoay chiều cửa vào (ZS = 0)",
    "shunt_noise_current_in": "Nguồn dòng nhiễu tương đương In,in đặt song song ngõ vào, tìm được bằng phép hở mạch xoay chiều cửa vào (ZS -> inf)",
    "noiseless_twoport_block": "Khối mạch hai cửa tuyến tính đã được tắt mọi nguồn nhiễu nội tại nhưng giữ nguyên toàn bộ trở kháng vào/ra và độ lợi A(s)",
    "noise_bandwidth_brickwall": "Bộ lọc chữ nhật tương đương có cùng độ cao đỉnh H0 và cùng tổng diện tích công suất nhiễu tích phân Bn = (pi/2)*f_p"
  },
  "symptoms_addressed": [
    "wrong-snr-prediction-with-high-impedance-sensor",
    "divergent-integral-when-integrating-input-referred-noise",
    "missing-correlation-term-between-vn-and-in",
    "gain-dependent-output-noise-comparison-bias"
  ],
  "limitations": [
    "vn-and-in-are-generally-correlated-from-shared-internal-sources",
    "input-referred-noise-spectrum-rises-at-high-frequencies-beyond-circuit-poles",
    "cannot-compare-total-integrated-input-noise-without-specifying-system-bandwidth"
  ],
  "checklists": ["common-mos", "single-stage", "feedback-and-stb"]
}
---

## 1. Bản chất Nguyên lý, Sơ đồ Mạch & Vai trò Từng Nhánh Cấu trúc

Tại sao trong thiết kế mạch tương tự, ta không dùng thẳng **nhiễu ngõ ra (`T1067`, output noise)** làm thước đo phẩm chất mà phải quy đổi về **nhiễu quy về ngõ vào (`T1133`, input-referred noise)**? Razavi chỉ rõ ngay ở §7.3 (tr. 236–237): nhiễu ngõ ra phụ thuộc trực tiếp vào độ lợi của tầng! Một bộ khuếch đại hỏng có độ lợi gần bằng $0$ sẽ cho nhiễu ngõ ra cực thấp nhưng hoàn toàn vô dụng vì tín hiệu cũng biến mất. Quy đổi nhiễu về ngõ vào cho phép **so sánh trực diện mức nhiễu nội tại của mạch với biên độ nguồn tín hiệu đầu vào $V_{\text{sig}}$** mà không phụ thuộc việc có gắn thêm tầng khuếch đại lý tưởng phía sau hay không.

![Biểu diễn mạng hai cửa tuyến tính có nhiễu bằng mạch không nhiễu kèm cặp nguồn Vn,in và In,in](../../diagrams/mos-noise-input-referred.svg)

Tuy nhiên, một mô hình chỉ có duy nhất một nguồn áp $\overline{V_{n,in}^2}$ là **không đầy đủ về mặt vật lý** khi mạch có trở kháng vào hữu hạn $Z_{in}(s)$ (do điện trở hồi tiếp hoặc tụ cổng $C_{GS} + C_{GD,\text{Miller}}$ ở tần số cao) và được lái bởi nguồn tín hiệu có trở kháng trong $Z_S \neq 0$ (như photodiode, cảm biến áp điện, hay ăng-ten $50\,\Omega$):
1. **Nguồn áp nhiễu nối tiếp $V_{n,in}$:** Đại diện cho toàn bộ nhiễu nội tại xuất hiện ở ngõ ra khi cửa vào bị khóa cứng bởi một nguồn áp lý tưởng có $Z_S = 0$ (ngắn mạch cửa vào). Nếu nguồn thực tế hở mạch ($Z_S \to \infty$) và mạch có $Z_{in}$ hữu hạn, nguồn $V_{n,in}$ bị treo hở một đầu nên không thể bơm bất kỳ dòng nào vào mạch — dự đoán sai rằng nhiễu ngõ ra bằng 0!
2. **Nguồn dòng nhiễu song song $I_{n,in}$:** Đại diện cho toàn bộ nhiễu nội tại xuất hiện ở ngõ ra khi cửa vào bị kích bởi một nguồn dòng lý tưởng có $Z_S \to \infty$ (hở mạch cửa vào). Khi $Z_S = 0$, toàn bộ $I_{n,in}$ bị hút xuống đất qua nhánh ngắn mạch mà không đi vào mạch, nên hai nguồn **không bao giờ tính trùng (double count)** nhiễu ở hai giới hạn cực đoan!
3. **Mạch hai cửa không nhiễu (`T1135`, Noiseless Two-Port):** Giữ nguyên toàn bộ cấu trúc, trở kháng vào $Z_{in}(s)$, trở kháng ra $Z_{out}(s)$ và hàm truyền đạt của mạch thật, chỉ triệt các nguồn nhiễu nội tại về 0.

---

## 2. Hệ Phương trình Cốt lõi & Tư duy "Nhìn Mạch Đọc Nhanh" (Analysis by Inspection)

### 2.1. Quy trình Hai Bước Xác định Cặp $(V_{n,in}, I_{n,in})$ Độc lập Nguồn Kích (§7.3)
Để cặp $(V_{n,in}, I_{n,in})$ là thuộc tính nội tại chỉ phụ thuộc bản thân bộ khuếch đại (độc lập với $Z_S$ bên ngoài):
- **Bước 1 — Tìm $V_{n,in}$ (Ngắn mạch ngõ vào, $Z_S = 0$):** Nối tắt hai cực ngõ vào, tính điện áp nhiễu ngõ ra $\left.V_{n,\text{out}}\right|_{Z_S=0}$ (hoặc dòng ngắn mạch ngõ ra), rồi chia cho độ lợi điện áp $A_v(s) = \left.\dfrac{V_{\text{out}}}{V_{\text{in}}}\right|_{Z_S=0}$ của mạch không nhiễu (Phương trình 7.50, 7.56):

$$
V_{n,in}(s) = \frac{\left.V_{n,\text{out}}\right|_{Z_S=0}}{A_v(s)} \implies \overline{V_{n,in}^2} = \frac{\left.\overline{V_{n,\text{out}}^2}\right|_{Z_S=0}}{\left|A_v(j\omega)\right|^2}
$$

- **Bước 2 — Tìm $I_{n,in}$ (Hở mạch ngõ vào, $Z_S \to \infty$):** Để hở hai cực ngõ vào, tính điện áp nhiễu ngõ ra $\left.V_{n,\text{out}}\right|_{Z_S=\infty}$, rồi chia cho độ lợi hỗ trở (transimpedance gain) $R_T(s) = \left.\dfrac{V_{\text{out}}}{I_{\text{in}}}\right|_{Z_S=\infty} = Z_{in}(s) A_v(s)$ (Phương trình 7.53, 7.57):

$$
I_{n,in}(s) = \frac{\left.V_{n,\text{out}}\right|_{Z_S=\infty}}{Z_{in}(s) A_v(s)} \implies \overline{I_{n,in}^2} = \frac{\left.\overline{V_{n,\text{out}}^2}\right|_{Z_S=\infty}}{\left|Z_{in}(j\omega)\right|^2 \left|A_v(j\omega)\right|^2}
$$

**Trường hợp đặc biệt cực kỳ tiện lợi của MOSFET tần số thấp–trung bình:** Khi cửa vào nhìn thẳng vào cực cổng cách điện của MOSFET có $Z_{in}(s) = \frac{1}{s C_{in}}$ rất lớn sao cho $\left|Z_S(j\omega) \cdot \omega C_{in}\right| \ll 1$ trên toàn bộ dải tần quan tâm, đóng góp của $I_{n,in}$ qua $Z_S$ nhỏ không đáng kể và ta **chỉ cần tính duy nhất $\overline{V_{n,in}^2}$**! Ngược lại, với mạch hồi tiếp song song ở ngõ vào (như TIA dùng $R_F$ ở Ví dụ 7.11, Phương trình 7.63–7.72) hoặc tầng cổng chung CG / LNA RF ở tần số GHz, **bắt buộc phải tính đủ cả $V_{n,in}$ và $I_{n,in}$**!

### 2.2. Bài toán Tương quan giữa $V_{n,in}$ và $I_{n,in}$ (§7.3 & §7.10, Phương trình 7.55, 7.152)
Khi gắn nguồn tín hiệu thực tế có trở kháng $Z_S$ (tự thân $Z_S$ có nhiễu $\overline{V_{n,ZS}^2} = 4 k T \,\text{Re}\{Z_S\}$), tổng điện áp nhiễu hiệu dụng quy về nối tiếp với nguồn tín hiệu là (Phương trình 7.55, 7.152):

$$
\overline{V_{n,\text{tot,src}}^2} = \overline{V_{n,ZS}^2} + \overline{V_{n,in + I_n Z_S}^2} = 4 k T\,\text{Re}\{Z_S\} + \overline{\left| V_{n,in} + Z_S I_{n,in} \right|^2}
$$

Lưu ý tối quan trọng của Razavi (§7.10, Phụ lục A): vì cả $V_{n,in}$ và $I_{n,in}$ thường được sinh ra từ **cùng các nguồn nhiễu vật lý bên trong mạch** (ví dụ cùng dòng nhiễu kênh $\overline{I_{n,d}^2}$ và nhiễu tải $R_D$ trong tầng CS có tụ vào $C_{in}$: $I_{n,in} = s C_{in} V_{n,in}$ ở Phương trình 7.56–7.59!), chúng **có tương quan chặt chẽ với nhau**:

$$
\overline{\left| V_{n,in} + Z_S I_{n,in} \right|^2} = \overline{V_{n,in}^2} + \left|Z_S\right|^2 \overline{I_{n,in}^2} + 2\,\text{Re}\left\{ Z_S \, \overline{V_{n,in}^* I_{n,in}} \right\}
$$

Nếu bỏ qua số hạng tương quan chéo thứ ba (như ở Phương trình 7.59–7.62), ta sẽ tính thiếu hoặc tính sai hoàn toàn hệ số $(1 + s Z_S C_{in})$ tại ngõ vào!

### 2.3. Băng thông Nhiễu Hiệu dụng ($B_n$ — Noise Bandwidth, §7.8, Phương trình 7.145–7.146)
Với phổ nhiễu ngõ ra $S_{v,\text{out}}(f) = V_0^2 \cdot \left|\frac{H(j2\pi f)}{H_0}\right|^2$ có giá trị nền phẳng $V_0^2$ ở tần số thấp, **băng thông nhiễu (`T1169`)** $B_n$ được định nghĩa sao cho tổng phương sai nhiễu ngõ ra bằng tích đơn giản $V_0^2 \cdot B_n$:

$$
\int_{0}^{\infty} V_{n,\text{out}}^2(f)\,df = V_0^2 \cdot B_n \implies B_n = \frac{1}{V_0^2} \int_{0}^{\infty} V_{n,\text{out}}^2(f)\,df \quad [\text{Hz}]
$$

- **Đối với hệ một cực bậc nhất** $H(s) = \dfrac{H_0}{1 + s/\omega_p}$ (với $f_p = \dfrac{\omega_p}{2\pi}$ là băng thông $-3\text{ dB}$ tính bằng Hz):

$$
B_n = \int_{0}^{\infty} \frac{df}{1 + (f / f_p)^2} = \frac{\pi}{2} f_p \approx 1{,}571\, f_p = \frac{\omega_p}{4} \quad [\text{Hz}]
$$

- **Đối với hệ bậc hai trùng cực hoặc Butterworth bậc cao:** Đuôi bộ lọc cắt dốc hơn nên tỉ số $B_n / f_{-3\text{dB}}$ tiến dần về $1{,}0$ (bậc 2 Butterworth có $B_n \approx 1{,}11\,f_{-3\text{dB}}$; bậc 3 có $B_n \approx 1{,}05\,f_{-3\text{dB}}$).

### 2.4. Ví dụ Định lượng Đầy Đủ Cả $V_{n,in}$ và $I_{n,in}$: Bộ Khuếch đại Hỗ trở TIA Có Điện trở Hồi tiếp $R_F$ (Ví dụ 7.11, tr. 242–243)
Xét tầng nguồn chung ($g_m$, bỏ qua $r_O$ để minh họa gọn như Hình 7.38) có điện trở hồi tiếp $R_F$ nối từ máng về cổng:
1. **Tìm $\overline{V_{n,in}^2}$ (Ngắn mạch cửa vào xuống đất):** Khi cổng nối đất AC, nguồn nhiễu của $R_F$ ($\overline{I_{n,RF}^2} = \frac{4kT}{R_F}$) và dòng nhiễu kênh MOSFET ($\overline{I_{n,M1}^2} = 4kT\gamma g_m$) cùng đổ vào nút máng tạo áp nhiễu ngõ ra $\overline{V_{n,\text{out}}^2}\big|_{Z_S=0} = \left(\frac{4kT}{R_F} + 4kT\gamma g_m\right) R_F^2$. Chia cho bình phương độ lợi áp của mạch không nhiễu $A_v = (1 - g_m R_F)$ (Phương trình 7.66–7.67):

$$
\overline{V_{n,in}^2} = \frac{4 k T R_F + 4 k T \gamma g_m R_F^2}{(g_m R_F - 1)^2} \;\xrightarrow{g_m R_F \gg 1}\; \frac{4 k T \gamma}{g_m} + \frac{4 k T}{g_m^2 R_F}
$$

2. **Tìm $\overline{I_{n,in}^2}$ (Hở mạch cửa vào — kích bằng nguồn dòng $I_{in}$, xem `NG07-03` Hình 7.38e):** Khi cửa vào hở mạch, độ lợi dòng ngắn mạch ngõ ra là $\frac{I_{\text{out}}}{I_{\text{in}}} = g_m R_F - 1$ (Phương trình 7.70), còn dòng nhiễu ngắn mạch ngõ ra là $\overline{I_{n,\text{out}}^2}\big|_{Z_S=\infty} = g_m^2 (4 k T R_F) + 4 k T \gamma g_m$ (vì cửa vào hở nên toàn bộ áp nhiễu $4kT R_F$ đặt thẳng lên cực cổng $M_1$!). Chia cho $(g_m R_F - 1)^2$ (Phương trình 7.71–7.72):

$$
\overline{I_{n,in}^2} = \frac{4 k T R_F g_m^2 + 4 k T \gamma g_m}{(g_m R_F - 1)^2} \;\xrightarrow{g_m R_F \gg 1}\; \frac{4 k T}{R_F} + \frac{4 k T \gamma}{g_m R_F^2}
$$

**Bài học thiết kế trực quan:** Khi cảm biến là photodiode có trở kháng cực cao ($Z_S \to \infty$), đại lượng quyết định hoàn toàn độ nhạy thu quang là $\overline{I_{n,in}^2} \approx \dfrac{4 k T}{R_F}$: muốn giảm nhiễu dòng ngõ vào **phải tăng $R_F$ lớn nhất có thể** (chứ không phải giảm $R_F$!), rồi dùng độ lợi vòng của TIA để khôi phục lại băng thông!

---

## 3. Bất biến Cấu trúc & Các Bẫy Lỗi Kinh điển (Structural Invariants & Traps)

- **[INV-IRN-01] Bất biến Bảo toàn Tỷ số Tín hiệu trên Nhiễu trong Băng hẹp $\Delta f$:** Tại bất kỳ tần số đơn lẻ $f$ nào, tỉ số giữa công suất tín hiệu và mật độ phổ nhiễu đo tại ngõ vào **bằng chính xác** tỉ số đo tại ngõ ra vì cả hai cùng nhân với $\left|H(j2\pi f)\right|^2$:

$$
\text{SNR}(f) = \frac{S_{\text{sig,out}}(f)}{S_{n,\text{out}}(f)} = \frac{S_{\text{sig,in}}(f) \left|H(f)\right|^2}{S_{n,in}(f) \left|H(f)\right|^2} = \frac{S_{\text{sig,in}}(f)}{S_{n,in}(f)}
$$

- **[TRAP-IRN-01] Bẫy Tích Phân Nhiễu Quy Về Ngõ Vào từ $0$ đến $\infty$ (§7.9, Phương trình 7.147–7.148):** Đây là lỗi kinh điển nhất khi mới dùng Cadence Spectre! Giả sử tầng khuếch đại có nhiễu ngõ ra hữu hạn lọc qua một cực $\overline{V_{n,\text{out}}^2}(f) = \frac{V_{n0}^2}{1 + (f/f_p)^2}$ và hàm truyền $A_v(f) = \frac{A_0}{1 + j f/f_p}$, hoặc có tải nhiễu ở tầng sau trong khi tầng đầu đã suy giảm độ lợi. Khi chia $\overline{V_{n,\text{out}}^2}(f)$ cho $\left|A_v(f)\right|^2$, mẫu số $\frac{1}{1 + (f/f_p)^2}$ bị khử mất (thậm chí phổ $\overline{V_{n,in}^2}(f)$ **tăng vọt theo $f^2$ ở tần số cao** do nhiễu các tầng sau chia cho độ lợi đang rơi $-20\text{ dB/dec}$!). Do đó:

$$
\int_{0}^{\infty} \overline{V_{n,in}^2}(f)\,df = \infty \quad (\text{VÔ NGHĨA VẬT LÝ!})
$$

**Quy tắc Bắt buộc (§7.9):** Luôn luôn **tích phân phổ nhiễu tại NGÕ RA** $\overline{V_{n,\text{out,tot}}^2} = \int_0^\infty \overline{V_{n,\text{out}}^2}(f)\,df$ (hoặc tích phân trên đúng băng thông tín hiệu hữu ích $[f_1, f_2]$ của hệ thống), sau đó mới chia tổng bình phương nhiễu ngõ ra đó cho bình phương độ lợi băng thông giữa $A_0^2$ để thu được điện áp nhiễu hiệu dụng tương đương ngõ vào $V_{n,\text{in,rms}} = \dfrac{V_{n,\text{out,rms}}}{|A_0|}$!
- **[TRAP-IRN-02] Nhầm lẫn $2\pi$ khi Đổi Trục $\omega$ sang $f$ trong Băng thông Nhiễu (`NG07-10`):** Công thức $B_n = \frac{\pi}{2} f_p$ tính bằng **Hz**! Nếu bạn đã có cực tính bằng rad/s ($\omega_p = \frac{1}{RC}$), thì $B_n = \frac{\pi}{2} \cdot \frac{\omega_p}{2\pi} = \frac{\omega_p}{4} = \frac{1}{4RC}\text{ [Hz]}$ (kiểm chứng ngay: $4kTR \times \frac{1}{4RC} = \frac{kT}{C}$, khớp tuyệt đối!). Viết nhầm $B_n = \frac{\pi}{2}\omega_p$ sẽ làm vọt nhiễu tính tay lên gấp $2\pi \approx 6{,}28$ lần công suất!
- **[TRAP-IRN-03] Chia Sai Độ lợi khi Mạch được Lái bằng Nguồn Dòng (Ví dụ 7.11 & `NG07-03`):** Khi nguồn tín hiệu là nguồn dòng $I_{in}$ (như TIA thu quang có trở kháng hồi tiếp $R_F$), để tìm $\overline{I_{n,in}^2}$ phải chia dòng nhiễu ngắn mạch ngõ ra cho bình phương độ lợi dòng ngắn mạch $(g_m R_F - 1)^2$ (hoặc chia áp nhiễu ngõ ra cho bình phương hỗ trở $R_T^2$), tuyệt đối không chia cho độ lợi áp!

---

## 4. Lộ trình Nâng cấp Cấu trúc & Bát giác Đánh đổi (Upgrade Paths & Design Octagon)

| Bối cảnh thiết kế giao diện đầu vào | Lựa chọn cấu trúc tối ưu (Canonical Node) | Lý do khớp trở kháng nguồn–nhiễu | Đánh đổi trên Bát giác Thiết kế |
|---|---|---|---|
| Nguồn tín hiệu trở kháng thấp–vừa ($Z_S$ nhỏ) cần $V_{n,in}$ cực thấp | Tầng CS hoặc Cặp vi sai MOSFET $g_m$ lớn (`law-stage-and-mirror-noise-rules`, `topo-telescopic-cascode-opamp`) | Cổng MOSFET có $I_{n,in} \approx 0$ ở tần số thấp và $\overline{V_{n,in}^2} \propto 1/g_m$ | Dòng tiêu thụ lớn hoặc diện tích $W$ lớn tăng $C_{in}$ |
| Nguồn tín hiệu là cảm biến dòng trở kháng rất lớn + tụ ký sinh lớn (Photodiode) | Bộ khuếch đại hỗ trở hồi tiếp điện áp–dòng điện (`concept-feedback-four-topologies` — VC / Shunt-Shunt TIA) | Hạ trở kháng vào xuống $R_{in,\text{closed}} = \frac{R_F}{1 + A_0}$ mở rộng băng thông mà chỉ cộng nhiễu dòng $\frac{4kT}{R_F}$ (cho phép chọn $R_F$ lớn!) | Thành phần $\overline{V_{n,in}^2} \cdot (\omega C_{PD})^2$ tăng ở tần số cao gây cực nhiễu và đòi hỏi ổn định vòng TIA |
| Phối hợp trở kháng $50\,\Omega$ dải rộng không dùng điện trở kết cuối sinh nhiễu $4kTR$ | Tầng cổng chung $1/g_m = 50\,\Omega$ hoặc CS suy biến cuộn cảm / hồi tiếp song song–nối tiếp | Cung cấp $R_{in} = 50\,\Omega$ mà tránh đặt điện trở vật lý $50\,\Omega$ song song làm nhân đôi hệ số nhiễu (Noise Figure $\ge 3\text{ dB}$) | Tầng CG đơn giản vẫn bị giới hạn $\gamma$ tại điều kiện phối hợp $g_m R_S = 1$ (`law-stage-and-mirror-noise-rules`) |

---

## 5. Thích ứng Đa Tiến trình (90nm / 65nm / 45nm) & Cách Kiểm chứng trong Cadence / Spectre

### 5.1. Thích ứng Công nghệ Nanomet (90nm $\to$ 65nm $\to$ 45nm)
- **Dòng Rò Cực Cổng (Gate Tunneling Leakage $I_G$) tạo Nhiễu Bắn (Shot Noise) vào $I_{n,in}$:** Ở tiến trình $\ge 180\text{ nm}$ ($t_{ox} > 4\text{ nm}$), ở tần số thấp $I_{n,in} \approx 0$. Nhưng khi xuống **65nm và đặc biệt 45nm** với lớp oxit mỏng $\sim 1{,}2\text{–}1{,}8\text{ nm}$ (trước High-k hoặc ở transistor core mỏng), dòng xuyên hầm cực cổng $I_G$ xuất hiện rõ rệt (như Razavi lưu ý tại Chú thích chân trang 12, tr. 256) và sinh ra **nhiễu bắn (shot noise) $\overline{I_{n,G}^2} = 2 q I_G$** cộng trực tiếp vào $\overline{I_{n,in}^2}$ ở tần số thấp! Với các mạch giao tiếp cảm biến trở kháng hàng chục $\text{M}\Omega$ trên chip 65nm/45nm, bắt buộc dùng **transistor I/O oxit dày (thick-oxide $1{,}8\text{ V}/2{,}5\text{ V}$)** ở ngay cặp đầu vào để triệt dòng rò cổng $I_G$!

### 5.2. Quy trình Kiểm chứng trong Cadence Virtuoso / Spectre
1. **Cách tránh bẫy tích phân `in` trong Spectre `noise`:**
   - Khi chạy `noise ( Vout+ Vout- ) Vsrc dec 50 1 100G`, Spectre xuất hai hàm: `getData("out" ?result "noise")` (phổ nhiễu ngõ ra) và `getData("in" ?result "noise")` (phổ nhiễu quy về nguồn `Vsrc`).
   - **ĐÚNG:** Để tính tổng nhiễu RMS toàn dải của bộ khuếch đại tự giới hạn băng thông, dùng hàm Calculator `integ(getData("out" ?result "noise")^2, 1, 100G)` lấy căn bậc hai ra $V_{n,\text{out,rms}}$, rồi chia cho độ lợi DC `value(mag(getData("/Voutdiff" ?result "ac")), 1k)`!
   - **SAI:** Tuyệt đối không chạy `integ(getData("in" ?result "noise")^2, 1, 100G)` lên tới `100 GHz` (vượt xa băng thông mạch) vì đường `in` vọt lên vô cực theo tần số làm kết quả tích phân bùng nổ vô nghĩa! Đường `in` chỉ được tích phân khi đằng sau hệ thống có bộ lọc chống chồng phổ (anti-aliasing filter) sắc nét khóa cứng băng tần $[f_1, f_2]$ nằm trọn bên trong băng thông phẳng của mạch!
2. **Kiểm tra Tương quan Nguồn Thực tế $Z_S$:** Thay vì tự tính tay $V_{n,in}$ và $I_{n,in}$ rời nhau dễ quên hệ số tương quan phức, hãy đặt đúng mô hình trở kháng cảm biến $Z_S(s)$ nối tiếp nguồn `Vsrc` trong testbench Spectre (có thể bật `isnoisy=no` trên điện trở trong của $Z_S$ nếu chỉ muốn đo riêng nhiễu do bản thân IC cộng thêm!). Spectre tự động giải chính xác toàn bộ tương quan ma trận dẫn nạp phức!

---

## 6. Mốc Đối chiếu Sách Razavi & Thuật ngữ Chuẩn CLB

### 6.1. Đối chiếu Sách Gốc Razavi (2nd Edition)
- **Chương 7:** §7.3 *Representation of Noise in Circuits* (tr. 236–243, Phương trình 7.44–7.72, Hình 7.29–7.38), §7.8 *Noise Bandwidth* (tr. 264–265, Phương trình 7.145–7.146, Hình 7.65), §7.9 *Problem of Input Noise Integration* (tr. 265, Phương trình 7.147–7.148, Hình 7.66), §7.10 *Appendix A: Problem of Noise Correlation* (tr. 265–267, Phương trình 7.149–7.153, Hình 7.67–7.68).
- **Chú giải Hiệu đính Học thuật CLB (`NG07`):**
  - **`NG07-03` (tr. 243, Ví dụ 7.11):** Khi tính độ lợi dòng điện cho bộ khuếch đại có điện trở hồi tiếp $R_F$ ở Phương trình (7.69)–(7.71), lời văn nguồn dẫn nhầm sang Hình 7.38(c) (vốn dùng nguồn áp $V_{in}$); sơ đồ thực tế được kích bằng nguồn dòng $I_{in}$ tương ứng với phép tính phải là **Hình 7.38(e)**.
  - **`NG07-10` (tr. 264, Hình 7.65):** Các tích phân định nghĩa $B_n$ ở (7.145)–(7.146) lấy theo vi phân $df$ (Hz), trong khi trục hoành Hình 7.65 vẽ theo $\omega$ (rad/s). Luôn nhớ đổi $df = d\omega / (2\pi)$ để có $B_n = \frac{\pi}{2} f_p = \frac{\omega_p}{4}\text{ [Hz]}$.

### 6.2. Bảng Thuật ngữ Chuẩn CLB Vi Mạch Sử dụng trong Thẻ
| Mã CLB | Thuật ngữ Tiếng Anh | Thuật ngữ Tiếng Việt Chuẩn | Ghi chú Ngữ cảnh |
|---|---|---|---|
| `T1133` | input-referred noise | nhiễu quy về ngõ vào | Đại lượng chuẩn để so sánh trực tiếp với biên độ tín hiệu vào |
| `T1137` | input-referred noise voltage | điện áp nhiễu quy về ngõ vào | Đo bằng phép ngắn mạch cửa vào ($Z_S = 0$) |
| `T1146` | input-referred noise current | dòng điện nhiễu quy về ngõ vào | Đo bằng phép hở mạch cửa vào ($Z_S \to \infty$) |
| `T1135` | noiseless circuit | mạch không nhiễu | Khối hai cửa giữ nguyên hàm truyền sau khi rút nhiễu ra ngoài |
| `T1169` | noise bandwidth | băng thông nhiễu | $B_n = (\pi/2) f_{-3\text{dB}}$ đối với hệ một cực |
| `T1171` | noise correlation | tương quan nhiễu | Xảy ra khi $V_{n,in}$ và $I_{n,in}$ bắt nguồn từ cùng linh kiện |
| `T1172` | input noise integration | phép tích phân nhiễu quy về ngõ vào | Bẫy phân kỳ nếu tích phân vượt quá băng thông bộ khuếch đại |
| `T1173` | output noise integration | phép tích phân nhiễu ngõ ra | Luôn hội tụ hữu hạn nhờ các cực tự nhiên của mạch |
