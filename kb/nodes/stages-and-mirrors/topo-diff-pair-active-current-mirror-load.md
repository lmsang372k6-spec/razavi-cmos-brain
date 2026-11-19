---
{
  "id": "topo-diff-pair-active-current-mirror-load",
  "kind": "topology",
  "domain": "stages-and-mirrors",
  "title_vi": "Cặp vi sai dùng tải gương dòng tích cực — Chuyển đổi Vi sai sang Đơn đầu (Differential Pair with Active Current-Mirror Load)",
  "title_en": "Differential Pair with Active Current-Mirror Load: Exact D2SE Superposition, CMRR & Mirror Doublet",
  "summary": "Giải mã cơ chế chuyển đổi vi sai sang đơn đầu bằng tải gương dòng tích cực (5T-OTA): chứng minh vì sao đọc đơn đầu thụ động đánh mất một nửa Gm, cách gương dòng PMOS khôi phục trọn vẹn Gm = gm1,2 và nén cầu 2rO1,2 thành rO2||rO4 (đối chiếu nghiệm chính xác PT 5.38), giới hạn CMRR hữu hạn ngay cả khi đối xứng hoàn hảo (PT 5.41-5.57), bất đối xứng kẹp biên lớn và cặp cực-zero gương dòng (wm, 2*wm).",
  "diagram": "../../diagrams/diff-pair-active-mirror.svg",
  "razavi_refs": [
    {
      "chapter": 4,
      "section": "4.3-4.4",
      "pages": "118-126",
      "equations": ["4.58", "4.60"]
    },
    {
      "chapter": 5,
      "section": "5.3, 5.3.1-5.3.4",
      "pages": "146-160",
      "equations": ["5.22", "5.26", "5.28", "5.33", "5.35", "5.38", "5.41", "5.47", "5.55", "5.57"]
    },
    {
      "chapter": 6,
      "section": "6.6.2",
      "pages": "201-203",
      "equations": ["6.91", "6.94", "6.95", "6.96"]
    }
  ],
  "glossary_codes": ["T612", "T624", "T699", "T755", "T764", "T967", "T973", "T1164", "T1587"],
  "process_agnostic": true,
  "roles": {
    "non_inverting_input_M1": "Transistor đầu vào không đảo (+) nối cực máng lên nhánh diode M3 (nút E/F), bơm dòng tín hiệu vào đường truyền chậm qua gương dòng.",
    "inverting_input_M2": "Transistor đầu vào đảo (-) nối cực máng trực tiếp vào nút ngõ ra đơn đầu Vout, tạo đường truyền nhanh rút dòng tín hiệu trực tiếp tại tải.",
    "diode_sense_transistor_M3": "Transistor PMOS mắc diode cảm nhận dòng nhánh M1 với trở kháng thấp rd = (1/gm3)||rO3 và xác lập điện áp phân cực cổng gương.",
    "mirror_push_transistor_M4": "Transistor PMOS đầu ra của gương dòng tích cực sao chép biến thiên dòng M1 đẩy vào nút Vout đồng pha với dòng rút của M2.",
    "tail_current_source_M5": "Nguồn dòng đuôi ISS có trở kháng tín hiệu nhỏ RSS quyết định độ nén chế độ chung sang đơn đầu ACM và giới hạn dưới của ICMR."
  },
  "symptoms_addressed": [
    "6db-gm-and-gain-loss-in-naive-single-ended-differential-readout",
    "floating-dc-output-voltage-without-common-mode-feedback",
    "need-for-compact-differential-to-single-ended-stage-in-two-stage-opamp"
  ],
  "limitations": [
    "loss-of-strict-ac-virtual-ground-at-tail-node-due-to-drain-load-asymmetry",
    "asymmetric-large-signal-clipping-and-systematic-offset-when-vout-differs-from-vf",
    "finite-cmrr-even-under-zero-mismatch-due-to-diode-ro3-shunting",
    "mirror-node-capacitance-introduces-octave-pole-zero-doublet-wm-and-2wm"
  ],
  "checklists": ["common-mos", "differential-pair", "current-mirror"]
}
---

## 1. Bản chất Nguyên lý, Sơ đồ Mạch & Vai trò Từng Nhánh Cấu trúc

Trong chuỗi xử lý tín hiệu hỗn hợp, rất nhiều khối chức năng đòi hỏi phải chuyển đổi tín hiệu vi sai sạch nhiễu thành tín hiệu đơn đầu quy chiếu xuống đất (ví dụ tầng đầu của Op-Amp hai tầng lái tầng CS thứ hai, bộ đệm đầu ra, hoặc bộ chuyển đổi mức cho cổng logic). Nếu chỉ lấy ngõ ra đơn đầu tại một cực máng của cặp vi sai tải nguồn dòng thụ động (Hình 5.23a, trang 147) và bỏ không cực máng bên kia, mạch lập tức chịu ba tổn thất nặng nề: **(1)** lãng phí hoàn toàn một nửa dòng tín hiệu xoay chiều (mất $6\text{ dB}$ hỗ dẫn truyền dẫn $G_m$), **(2)** thế một chiều tại cực máng đầu ra trôi tự do vì hai nguồn dòng bão hòa đấu đầu nhau không có CMFB, và **(3)** cực máng bên bỏ trống không có tải đối xứng làm lệch thế nút đuôi.

Giải pháp kinh điển của Razavi (Chương 5, §5.3, trang 146–160) là thay cặp nguồn dòng tĩnh bằng một **tải gương dòng tích cực (`T1587`, *active current mirror load*; `T699`, *active current mirrors*)**, tạo nên **cặp vi sai dùng gương dòng tích cực (`T764`, *differential pair with active current mirror*)** — hạt nhân cấu thành **OTA năm transistor (`T755` / `T1164`, *five-transistor OTA*)**.

![Cơ chế chồng chập dòng đẩy-kéo, phản xạ trở kháng cầu 2rO1,2 và hai đường nhanh-chậm trong cặp vi sai tải gương dòng tích cực](../../diagrams/diff-pair-active-mirror.svg)

Sự phối hợp vật lý giữa 5 transistor giải quyết đồng thời cả bài toán xoay chiều lẫn một chiều:
1. **Khôi phục $100\%$ hỗ dẫn bằng cộng dòng đẩy–kéo (*Push-Pull Current Summation*):** Khi đặt kích thích vi sai nhỏ $V_{in1} = +\Delta V_{in}/2$ và $V_{in2} = -\Delta V_{in}/2$, nhánh trái $M_1$ tăng dòng máng thêm $+\frac{1}{2}g_{m1}\Delta V_{in}$ rút khỏi transistor PMOS mắc diode $M_3$ (nút gương $F$, hoặc $E$ ở Chương 6). Gương dòng $M_3\text{–}M_4$ lập tức phản chiếu biến thiên này thành dòng **đẩy ra** $+\frac{1}{2}g_{m1}\Delta V_{in}$ từ máng $M_4$ đổ vào nút ngõ ra $X$ ($V_{out}$). Cùng khoảnh khắc đó, nhánh phải $M_2$ giảm dòng máng $-\frac{1}{2}g_{m2}\Delta V_{in}$, tức **hút bớt dòng** khỏi nút $X$. Theo định luật Kirchhoff dòng điện, tổng dòng ngắn mạch đổ vào tải là $I_{out,\text{sc}} = +\frac{1}{2}g_{m1}\Delta V_{in} - (-\frac{1}{2}g_{m2}\Delta V_{in}) = g_{m1,2}\Delta V_{in}$! Nhờ sự đảo dấu qua gương dòng, **cổng $M_1$ (nằm dưới nhánh diode $M_3$) trở thành ngõ vào không đảo ($+$)**, còn **cổng $M_2$ (nằm dưới nút ngõ ra $V_{out}$) trở thành ngõ vào đảo ($-$)**.
2. **Tự khóa điểm phân cực DC ngõ ra mà không cần mạch CMFB:** Ở trạng thái cân bằng tĩnh $V_{in1} = V_{in2}$ với các cặp transistor đối xứng, dòng $I_{D1} = I_{D2} = I_{SS}/2$ buộc $|I_{D3}| = |I_{D4}|$; ngay cả khi xét điều biến chiều dài kênh $\lambda \neq 0$, phép chứng minh phản chứng (trang 150) khẳng định nghiệm duy nhất là $V_{out,\text{DC}} = V_F = V_{DD} - |V_{GS3}|$.
3. **Cái giá của sự bất đối xứng cấu trúc:** Khác với cặp vi sai đối xứng hoàn toàn có thể cắt đôi bằng **mạch nửa (`T624`, *half circuit*)** hay **nửa mạch vi sai (`T967`, *differential half circuit*)** như ở Mục 4.4 (Phương trình 4.60), tải tại máng $M_1$ là diode trở kháng thấp $\approx 1/g_{m3}$ trong khi tải tại máng $M_2$ là nút trở kháng rất cao $r_{O2} \parallel r_{O4}$. Sự phá vỡ đối xứng tải này hủy bỏ đất ảo chặt chẽ tại nút đuôi $P$, giới hạn CMRR hữu hạn ngay cả khi linh kiện khớp tuyệt đối, và sinh ra **cực gương (`T973`, *mirror pole*)** tại nút diode!

---

## 2. Hệ Phương trình Cốt lõi & Tư duy "Nhìn Mạch Đọc Nhanh" (Analysis by Inspection)

### 2.1. Tại sao Đọc Đơn đầu Thụ động Mất Độ lợi? (Phương trình 5.22 & 5.26)
Trước khi giải mạch gương dòng tích cực, Razavi (§5.3, Hình 5.23–5.25, trang 147–148) mổ xẻ chính xác cặp vi sai dùng tải nguồn dòng thụ động lấy ngõ ra đơn đầu (cực máng $M_1$ nối thẳng lên $V_{DD}$, cực máng $M_2$ nối tải nguồn dòng tĩnh $M_4$ có trở kháng $r_{O4}$, xem ghi chú biên tập `NG05-02`). Vì cực máng $M_2$ mang điện trở lớn $r_{O4}$, không được phép xấp xỉ điện trở nhìn vào cực nguồn $M_2$ là $1/g_{m2}$! Áp dụng công thức biến đổi trở kháng tầng cổng chung từ Chương 3, điện trở tương đương nhìn lên cực nguồn $M_2$ từ nút đuôi $P$ tuân theo Phương trình (5.22):

$$
R_{eq} = \frac{r_{O2} + r_{O4}}{1 + g_{m2} r_{O2}}
$$

Hiệu ứng phân áp từ cổng $M_1$ (mạch bám nguồn tải $R_{eq} \parallel r_{O1}$) xuống nút $P$ rồi khuếch đại cổng chung qua $M_2$ lên tải $r_{O4}$ (với $V_{in2} = 0$, đặt $V_{in1} = V_{in}$, giả thiết $g_{m1} r_{O1} = g_{m2} r_{O2} \gg 1$) rút gọn về Phương trình (5.25)–(5.26):

$$
\frac{V_{out}}{V_{in}}\bigg|_{\text{passive-SE}} = \frac{g_{m2} r_{O2} r_{O4}}{2 r_{O2} + r_{O4}} = \frac{g_{m2}}{2}\left[(2 r_{O2}) \parallel r_{O4}\right]
$$

Nhìn vào biểu thức (5.26): hỗ dẫn hiệu dụng chỉ đạt **$G_m = g_{m2}/2$** (mất một nửa dòng tín hiệu!). Nếu mạch phải lái tải điện trở hoặc tải $r_{O4} \ll 2 r_{O2}$, độ lợi chỉ bằng $\frac{1}{2} g_{m2} r_{O4}$; ngay cả khi $r_{O2} = r_{O4} = r_O$, độ lợi thụ động chỉ đạt $\frac{1}{3} g_m r_O$, thấp hơn đáng kể mức $\frac{1}{2} g_m r_O$ của tải gương dòng tích cực!

### 2.2. Phép Chồng chập Tín hiệu Nhỏ (`T612`) cho $G_m, R_{out}$ & Nghiệm Đóng Chính xác (Phương trình 5.28, 5.33, 5.35, 5.38)
Vì nút đuôi $P$ không phải đất ảo xoay chiều khi nút ra $X$ dao động lớn, ta áp dụng bổ đề tuyến tính hai bước $A_v = G_m R_{out}$ kết hợp **nguyên lý chồng chập (`T612`, *superposition*)** (§5.3.2, Hình 5.32–5.34):

1. **Bước 1 — Hỗ dẫn ngắn mạch $G_m$:** Khi nối tắt xoay chiều ngõ ra $X$ xuống đất ($V_{out} = 0$), bất đối xứng điện áp cực máng biến mất gần như hoàn toàn (vì nút $F$ cũng chỉ dao động cỡ $1/g_{m3}$ rất nhỏ). Nhìn nhanh cho ngay $G_m \approx g_{m1,2}$. Nếu giải nút $P$ chính xác với trở kháng diode $r_d = \frac{1}{g_{m3}} \parallel r_{O3} = \frac{r_{O3}}{1 + g_{m3} r_{O3}}$ (hở mạch nguồn dòng đuôi lý tưởng $I_{SS}$), ta được $G_{m,\text{exact}} = g_{m1} r_{O1} \frac{g_{m4} r_d + 1}{2 r_{O1} + r_d}$.
2. **Bước 2 — Phép màu "Gấp Đôi Dẫn Nạp Cầu $2r_{O1,2}$" trong $R_{out}$ (Phương trình 5.28 & 5.33):** Nối đất các cổng $V_{in1} = V_{in2} = 0$ và đặt áp thử $V_X$ vào nút ngõ ra $X$ (Hình 5.33). Với nguồn dòng đuôi $I_{SS}$ hở mạch xoay chiều, cực nguồn của $M_1$ và $M_2$ nối tiếp lơ lửng nhau: bất kỳ dòng nhỏ $i_1$ nào chảy từ $X$ xuống qua $M_2$ đều bắt buộc phải chảy ngược lên qua $M_1$ vào nút diode $F$ ($V_{gs1} + V_{gs2} = 0$ với $I_{D1,\text{ac}} = -I_{D2,\text{ac}} \implies$ tổng trở cầu nối từ $X$ sang $F$ bằng đúng $r_{O1} + r_{O2} = 2 r_{O1}$!). Do đó dòng đi vào nhánh cầu là $i_1 = \frac{V_X}{2 r_{O1} + r_d}$. Nhưng dòng $i_1$ này khi đổ vào $M_3$ lại làm giảm điện thế nút $F$ một lượng $i_1 r_d$, điều khiển cổng $M_4$ rút thêm một dòng phản chiếu $g_{m4} r_d i_1$ ngay tại nút $X$! Tổng dẫn nạp đầu ra chính xác theo Phương trình (5.33) là:

$$
\frac{I_X}{V_X} = \frac{1 + g_{m4} r_d}{2 r_{O1} + r_d} + \frac{1}{r_{O4}} = \frac{(1 + g_{m4} r_d) r_{O4} + 2 r_{O1} + r_d}{(2 r_{O1} + r_d) r_{O4}}
$$

Khi $2 r_{O1} \gg r_d$ và $g_{m3} = g_{m4}$ sao cho $g_{m4} r_d \approx 1$, phân số thứ nhất rút gọn ngoạn mục thành $\frac{1 + 1}{2 r_{O1}} = \frac{1}{r_{O1}} = \frac{1}{r_{O2}}$, cho công thức nhìn mạch chuẩn mực (Phương trình 5.28):

$$
R_{out} \approx r_{O2} \parallel r_{O4} \implies \left|A_{v,\text{approx}}\right| = g_{m1,2}\left(r_{O2} \parallel r_{O4}\right)
$$

3. **Bước 3 — Phương trình Độ lợi Chính xác Tuyệt đối ở Mọi Giá trị $g_m r_O$ (Phương trình 5.35 & 5.38):** Nhân trực tiếp $G_{m,\text{exact}}$ với $R_{out,\text{exact}} = (I_X / V_X)^{-1}$, đại lượng $(2 r_{O1} + r_d)$ triệt tiêu sạch giữa tử số và mẫu số (Phương trình 5.35), và khi thay $r_d = \frac{r_{O3}}{1 + g_{m3} r_{O3}}$ với $r_{O3} = r_{O4}, g_{m3} = g_{m4}$, Razavi thu được công thức đóng siêu gọn (Phương trình 5.38):

$$
G_m R_{out} = -g_{m1} r_{O1} \frac{(g_{m4} r_d + 1) r_{O4}}{(g_{m4} r_d + 1) r_{O4} + 2 r_{O1} + r_d} \implies \left|A_{v,\text{exact}}\right| = g_{m1}\left(r_{O1} \parallel r_{O4}\right)\frac{2 g_{m4} r_{O4} + 1}{2\left(g_{m4} r_{O4} + 1\right)}
$$

Ngay cả trong tiến trình cực ngắn nơi độ lợi nội tại $g_{m4} r_{O4}$ tụt xuống chỉ còn $4$, thừa số hiệu chỉnh $\frac{2(4)+1}{2(4+1)} = \frac{9}{10} = 0{,}90$ xác nhận công thức nhìn nhanh $g_{m1}(r_{O1} \parallel r_{O4})$ chỉ sai lệch chưa tới $0{,}9\text{ dB}$!

### 2.3. Độ lợi Chế độ Chung $A_{\text{CM}}$ & CMRR Hữu hạn Khi Đối xứng và Lệch Nhánh (Phương trình 4.58, 5.41, 5.47, 5.55, 5.57)
Khác với ngõ ra vi sai đối xứng nơi $A_{\text{CM-DM}} = 0$ nếu linh kiện khớp hoàn hảo (Phương trình 4.58 cho $\text{CMRR} \to \infty$ khi $\Delta g_m \to 0$), cấu trúc gương dòng tích cực lấy ngõ ra đơn đầu chịu hai tầng suy giảm CMRR (§5.3.3–5.3.4, trang 156–160):
- **Khi toàn bộ cặp transistor khớp hoàn hảo ($g_{m1}=g_{m2}, g_{m3}=g_{m4}$, Phương trình 5.41 & 5.47):** Dưới biến thiên đồng pha $\Delta V_{in,\text{CM}}$, tính đối xứng giữ $V_{out} = V_F$ nên cho phép nối tắt $F$ với $X$, gộp $M_1 \parallel M_2$ (hỗ dẫn $2g_{m1,2}$ suy biến bởi $R_{SS}$) lái tải diode gộp $M_3 \parallel M_4$ (trở kháng $\approx \frac{1}{2g_{m3,4}}$):

$$
A_{\text{CM,sym}} = -\frac{1}{1 + 2 g_{m1,2} R_{SS}} \cdot \frac{g_{m1,2}}{g_{m3,4}}, \qquad \text{CMRR}_{\text{sym}} = \left|\frac{A_{\text{DM}}}{A_{\text{CM,sym}}}\right| \approx \left(1 + 2 g_{m1,2} R_{SS}\right) g_{m3,4}\left(r_{O1,2} \parallel r_{O3,4}\right)
$$

*Tại sao dòng phản chiếu từ $M_3$ sang $M_4$ không khử sạch dòng chế độ chung của $M_2$?* Phương trình (5.47) vạch rõ thủ phạm là **$r_{O3}$ hữu hạn**: khi $M_1$ tăng dòng $\Delta I_1$, một phần dòng rẽ qua $r_{O3}$ thay vì qua $1/g_{m3}$, làm dòng phản chiếu $|\Delta I_{D4}| = g_{m4} \Delta I_1 \frac{r_{O3}}{1 + g_{m3} r_{O3}}$ luôn hụt hơn $\Delta I_2 = \Delta I_1$ một lượng $\frac{\Delta I_1}{1 + g_{m3} r_{O3}}$, đẩy áp tại nút $X$ sụt bằng đúng $\Delta V_F$!
- **Khi xuất hiện thêm bất đối xứng hỗ dẫn $g_{m1} \neq g_{m2}$ (Phương trình 5.55 & 5.57):** Cộng dòng không cân bằng tại nút $X$ (với $r_{O3} = r_{O4} \gg 1/g_{m3}$) cho Phương trình (5.55) và rút gọn về Phương trình (5.57):

$$
\Delta V_{out} = \left[\frac{g_{m1}\Delta V_{in,\text{CM}}}{1 + (g_{m1}+g_{m2})R_{SS}}\frac{r_{O3}}{r_{O3} + g_{m3}^{-1}} - \frac{g_{m2}\Delta V_{in,\text{CM}}}{1 + (g_{m1}+g_{m2})R_{SS}}\right] r_{O4} \implies \frac{\Delta V_{out}}{\Delta V_{in,\text{CM}}} \approx \frac{(g_{m1} - g_{m2})r_{O3} - \dfrac{g_{m2}}{g_{m3}}}{1 + (g_{m1} + g_{m2})R_{SS}}
$$

So sánh hai số hạng trên tử số của (5.57) mang lại trực giác thiết kế sắc bén: ngay cả khi lệch $(g_{m1} - g_{m2})/g_m$ chỉ cỡ $1\text{–}2\%$, nếu $g_m r_O \approx 30$ thì số hạng bất đối xứng $(g_{m1} - g_{m2})r_{O3} \approx 0{,}3\text{–}0{,}6$ vẫn có cùng bậc độ lớn với số hạng cấu trúc $-g_{m2}/g_{m3} \approx -1$!

### 2.4. Cực Gương $\omega_m$ & Cặp Cực–Zero Gần Trùng (Octave Doublet — Mục 6.6.2, Phương trình 6.91, 6.94–6.96)
Ở tần số cao (§6.6.2, Hình 6.40–6.41, trang 201–203), tổng điện dung ký sinh tại nút cổng gương $E$ là $C_E = C_{GS3} + C_{GS4} + C_{DB1} + C_{DB3} + C_{GD1,\text{M}} + C_{GD4,\text{M}}$. Giải mạch tương đương Thévenin giữa hai cực máng cặp NMOS ($R_X = 2 r_{ON}$) nối vào gương PMOS cho hàm truyền bậc hai đầy đủ (Phương trình 6.91):

$$
\frac{V_{out}}{V_{in}}(s) = \frac{g_{mN} r_{ON} r_{OP}\left(2 g_{mP} + C_E s\right)}{2 r_{OP} r_{ON} C_E C_L s^2 + \left[\left(2 r_{ON} + r_{OP}\right)C_E + r_{OP}\left(1 + 2 g_{mP} r_{ON}\right)C_L\right]s + 2 g_{mP}\left(r_{ON} + r_{OP}\right)}
$$

Với $\omega_{p2} \gg \omega_{p1}$ và $2 g_{mP} r_{ON} \gg 1$, mạch phân tách thành cực trội ngõ ra $\omega_{p1} \approx \frac{1}{(r_{ON}\parallel r_{OP})C_L}$, **cực gương (`T973`)** $\omega_{p2} = \omega_m \approx \frac{g_{mP}}{C_E}$ (Phương trình 6.94), và một **điểm không nửa mặt phẳng trái (LHP zero) tại đúng $\omega_z = 2\omega_{p2} = \frac{2 g_{mP}}{C_E}$**! Cộng trực tiếp hai đường truyền song song — đường chậm qua gương $\frac{A_0/2}{(1 + s/\omega_{p1})(1 + s/\omega_{p2})}$ và đường nhanh trực tiếp qua $M_2$ $\frac{A_0/2}{1 + s/\omega_{p1}}$ (lưu ý trong Phương trình 6.95–6.96 sách Razavi ký hiệu $A_0$ cho nửa độ lợi mỗi nhánh nên độ lợi DC tổng bằng $2A_0$) — giải thích trọn vẹn bản chất vật lý:

$$
\frac{V_{out}}{V_{in}}(s) = \frac{A_{\text{DC}}/2}{1 + s/\omega_{p1}}\left(\frac{1}{1 + s/\omega_{p2}} + 1\right) = \frac{A_{\text{DC}}\left(1 + \dfrac{s}{2\omega_{p2}}\right)}{\left(1 + \dfrac{s}{\omega_{p1}}\right)\left(1 + \dfrac{s}{\omega_{p2}}\right)}
$$

**Ví dụ số tổng hợp (chuẩn Ví dụ 5.8–5.10 & §6.6.2):** Xét mạch 5T-OTA có $I_{SS} = 200\,\mu\text{A}$ ($I_{D1..4} = 100\,\mu\text{A}$), $g_{m1,2} = 1{,}6\text{ mS}$, $g_{m3,4} = 0{,}8\text{ mS}$, $r_{O1,2} = r_{O3,4} = 50\text{ k}\Omega$, $R_{SS} = 40\text{ k}\Omega$, $C_L = 1\text{ pF}$, $C_E = 80\text{ fF}$.
- Độ lợi vi sai nhìn nhanh $|A_{v,\text{approx}}| = 1{,}6\text{ mS} \times (50 \parallel 50)\text{ k}\Omega = 40\text{ V/V}$ ($32{,}04\text{ dB}$); nghiệm chính xác (5.38) với $g_{m4} r_{O4} = 40$ cho $40 \times \frac{81}{82} = 39{,}51\text{ V/V}$ ($31{,}93\text{ dB}$). Nếu đọc đơn đầu thụ động (5.26), độ lợi tụt xuống chỉ còn $\frac{0{,}8\text{ mS}}{1} \times (100 \parallel 50)\text{ k}\Omega = 26{,}7\text{ V/V}$ ($28{,}5\text{ dB}$), và nếu lái tải ngoài $R_L = 10\text{ k}\Omega$ thì tụt gần một nửa ($0{,}8\text{ mS}\times (100\parallel 50\parallel 10)\text{ k}\Omega = 6{,}15\text{ V/V}$ so với $1{,}6\text{ mS}\times (25\parallel 10)\text{ k}\Omega = 11{,}4\text{ V/V}$)!
- $\text{CMRR}_{\text{sym}}$ khi khớp hoàn hảo: $|A_{\text{CM,sym}}| = \frac{1}{1 + 2(1{,}6\text{ mS})(40\text{ k}\Omega)} \cdot \frac{1{,}6}{0{,}8} = \frac{2}{129} = 0{,}0155 \implies \text{CMRR}_{\text{sym}} = \frac{39{,}51}{0{,}0155} \approx 2\,549$ ($68{,}1\text{ dB}$). Nếu có lệch $g_{m1} - g_{m2} = 2\%\,g_{m1} = 32\,\mu\text{S}$, tử số (5.57) trở thành $(0{,}032\text{ mS}\times 50\text{ k}\Omega) - 2 = 1{,}6 - 2{,}0 = -0{,}4$ (tình cờ ngược dấu bớt một phần, hoặc nếu lệch ngược dấu $-2\%$ thì cộng dồn thành $-3{,}6$ làm $\text{CMRR}$ sụt thêm $5{,}1\text{ dB}$ xuống $63{,}0\text{ dB}$!).
- Cực trội $\omega_{p1}/(2\pi) = \frac{1}{2\pi \times 25\text{ k}\Omega \times 1\text{ pF}} = 6{,}37\text{ MHz}$ ($\text{GBW} \approx 254\text{ MHz}$), cực gương $\omega_m/(2\pi) = \frac{0{,}8\text{ mS}}{2\pi \times 80\text{ fF}} = 1{,}59\text{ GHz}$ và LHP zero tại $3{,}18\text{ GHz}$.

---

## 3. Bất biến Cấu trúc & Các Bẫy Lỗi Kinh điển (Structural Invariants & Traps)

- **`[INV-ACTMIR-01]` Bất biến Khóa Điện áp Đối xứng & Điện áp Lệch Hệ thống ($V_{OS,\text{sys}}$):** Mạch 5T-OTA chỉ triệt tiêu hoàn toàn sai số điều biến chiều dài kênh khi và chỉ khi **điện áp tĩnh ngõ ra đúng bằng điện áp nút diode gương dòng**: $V_{out,\text{DC}} = V_F = V_{DD} - |V_{GS3}|$. Khi đặt 5T-OTA làm tầng đầu của Op-Amp hai tầng (`topo-two-stage-opamp`), cổng transistor tầng hai ép $V_{out,\text{DC}} = V_{GS,\text{stage2}}$ (hoặc $V_{DD} - |V_{GS6}|$): nếu không định cỡ tỉ lệ mật độ dòng để khóa $V_{DD} - |V_{GS3,4}| = V_{out,\text{DC}}$, sự chênh áp $|V_{DS4}| - |V_{DS3}|$ sinh ngay dòng lệch $\Delta I = \lambda_P \frac{I_{SS}}{2}(|V_{DS4}| - |V_{GS3}|)$ và tạo điện áp lệch hệ thống quy về ngõ vào $V_{OS,\text{sys}} = \frac{\Delta V_{out,\text{DC}}}{A_{v1}}$!
- **`[INV-ACTMIR-02]` Bất đối xứng Kẹp Biên Lớn & Ngưỡng Đáy Phụ thuộc $V_{in,\text{CM}}$ (Mục 5.3.1, Ví dụ 5.8 & Bài tập 5.21):**
  - Khi $V_{in1} \gg V_{in2}$: $M_2$ ngắt hẳn, $M_4$ đi vào vùng triode sâu với dòng bằng $0$ và kéo $V_{out,\max} = V_{DD}$ (chạm sát nguồn dương!).
  - Ngược lại khi $V_{in1} \ll V_{in2}$: nếu biên độ vi sai cực lớn làm $M_1$ tắt hẳn thì $M_3, M_4$ tắt và $M_2, M_5$ kéo $V_{out} \to 0\text{ V}$; **tuy nhiên** trong các bộ chuyển đổi vi sai sang đơn đầu có biên độ vào vừa phải quanh $V_{in,\text{CM}}$ (Bài tập 5.21, Hình 5.64, trang 170–171), ngay khi $V_{out}$ tụt xuống dưới $V_{in2} - V_{TH2} \approx V_{in,\text{CM}} + \frac{\Delta V}{2} - V_{TH2}$, transistor $M_2$ rơi sâu vào vùng triode và bị kẹp đáy $V_{\min}$ phụ thuộc trực tiếp vào $V_{in,\text{CM}}$ nếu $M_1$ chưa ngắt hết dòng qua gương $M_3\text{–}M_4$!
- **`[TRAP-ACTMIR-01]` Bẫy Đấu Nhầm Cực tính Cổng Đảo / Không Đảo Khi Đóng Hồi tiếp Âm:** Rất nhiều lỗi tự kích khóa cứng (*latch-up* lên $V_{DD}$ hoặc $0\text{ V}$) trong thiết kế Op-Amp đến từ việc nhìn lầm ngõ ra nằm trên nhánh phải $M_2$ rồi tưởng cổng $M_2$ là cực dương! Hãy khắc cốt ghi tâm: đi từ cổng $M_2$ tới $V_{out}$ là một tầng CS đảo pha ($-$), còn đi từ cổng $M_1$ qua $M_3 \to M_4$ tới $V_{out}$ qua hai lần đảo dấu nên đồng pha ($+$). Cổng nhận hồi tiếp âm bắt buộc phải là **cổng $M_2$** (trừ khi phía sau còn nối thêm một tầng CS đảo pha thứ hai như trong Miller Op-Amp, khi đó cực tính tổng đảo ngược lại!).
- **`[TRAP-ACTMIR-02]` Bẫy Phá Vỡ PSRR+ Nghiêm Trọng ($A_{VDD} \approx 1\text{ V/V}$, $\text{PSRR}^+ \text{ cao tần sụp về } 0\text{ dB}$):** Đối với nhiễu trên đường nguồn $V_{DD}$, nút diode $F$ bám sát $V_{DD}$ qua trở kháng thấp $1/g_{m3}$ nên $V_F$ nhấp nhô gần như $100\%$ cùng biên độ với $\Delta V_{DD}$; còn ở tần số cao, tụ ký sinh $C_{GS3} + C_{GS4}$ nối tắt cổng gương vào $V_{DD}$ giữ $v_{sg4} \approx 0$ khiến toàn bộ nhiễu $\Delta V_{DD}$ truyền qua $r_{O4}$ hoặc tụ ký sinh xuống $V_{out}$ tùy theo cực tính tầng sau (`tech-opamp-psrr-plus-and-minus-analysis`)!
- **`[TRAP-ACTMIR-03]` Bẫy Đuôi Xác lập Chậm (Slow-Settling Tail) do Doublet $(\omega_m, 2\omega_m)$:** Nếu chọn chiều dài kênh gương PMOS $L_{3,4}$ quá lớn ($> 1\,\mu\text{m}$) để giảm nhiễu $1/f$ và nâng $r_{O4}$, diện tích cổng $W_3 L_3 + W_4 L_4$ phình to kéo cực gương $\omega_m = g_{mP}/C_E$ lọt xuống gần băng thông vòng kín $\omega_{GBW}$. Dù dự trữ pha nhìn trên Bode chỉ sụt nhẹ ($\le 19{,}5^\circ$), cặp cực–zero cách nhau 1 octave sinh ra thành phần hàm mũ tắt dần chậm làm mạch tụ chuyển mạch (SC) không thể đạt độ chính xác xác lập $12\text{–}14\text{ bit}$ trong chu kỳ xung nhịp!

---

## 4. Lộ trình Nâng cấp Cấu trúc & Bát giác Đánh đổi (Upgrade Paths & Design Octagon)

| Giới hạn của Cặp vi sai Tải Gương Dòng Tích cực | Cấu trúc Nâng cấp Chính tắc (Canonical Node) | Cơ chế Đột phá Cấu trúc | Đánh đổi trên Bát giác Thiết kế |
| :--- | :--- | :--- | :--- |
| Độ lợi một tầng $g_{m1}(r_{O2} \parallel r_{O4}) \approx 25\text{–}35\text{ dB}$ không đủ cho Op-Amp chính xác ở 65nm/45nm, biên độ ra bị kẹp bởi $V_{in,\text{CM}} - V_{TH2}$ | `topo-two-stage-opamp` (Dùng 5T-OTA làm Tầng 1 + Tầng 2 CS tải nguồn dòng bù Miller) | Tầng 2 nhân thêm độ lợi $-g_{m6}(r_{O6}\parallel r_{O7})$ lên $60\text{–}75\text{ dB}$ và giải phóng biên độ ra đạt $V_{DD} - 2V_{DS,\min}$ độc lập với ICMR! | Xuất hiện hệ hai cực trội, cần tụ bù $C_C$ và triệt RHP zero (`tech-miller-rhp-zero-nulling-and-cascode-comp`) |
| Cần độ lợi cao $>55\text{ dB}$ ngay trong **một tầng**, triệt tiêu hiệu ứng Miller ở $M_{1,2}$ và đẩy cực phụ lên cao hơn cực gương PMOS | `topo-telescopic-cascode-opamp` hoặc `topo-folded-cascode-ota` (dùng gương dòng cascode điện áp thấp `topo-lvccml-wide-swing-mirror`) | Che chắn cực máng bằng tầng CG nâng $R_{out} \sim g_m r_O^2$; bản Folded-Cascode PMOS-in chuyển đường gập sang NMOS tốc độ cao! | Thu hẹp dải dao động ngõ ra ($V_{DD} - 4V_{DS,\min}$ hoặc $5V_{DS,\min}$) và tăng công suất tĩnh (với Folded-Cascode) |
| Cực gương $\omega_m$ + doublet $(\omega_m, 2\omega_m)$ và CMRR hữu hạn của chuyển đổi đơn đầu không chấp nhận được ở ADC tốc độ cao | Ngõ ra **Vi sai Hoàn toàn** (`topo-folded-cascode-ota` + `tech-common-mode-feedback-cmfb`) | Bỏ gương dòng chuyển đổi đơn đầu, giữ đối xứng tuyệt đối hai đường tín hiệu (xóa sổ hoàn toàn doublet gương và khử nhiễu nguồn/đế!) | Bắt buộc thiết kế thêm mạch CMFB thời gian liên tục hoặc tụ chuyển mạch (`tech-switched-capacitor-cmfb`) |

---

## 5. Thích ứng Đa Tiến trình (90nm / 65nm / 45nm) & Cách Kiểm chứng trong Cadence / Spectre

### 5.1. Chiến lược Định cỡ Bất đối xứng Cặp Đầu vào – Gương Dòng Tải (90nm / 65nm / 45nm)
Trong tiến trình nanomet ($V_{DD} = 1{,}0\text{–}1{,}2\text{ V}$), cặp đầu vào $M_{1,2}$ và gương dòng tải $M_{3,4}$ tuân theo **luật đối ngẫu định cỡ ngược chiều** (`law-pelgrom-mismatch-and-sizing-duality` & `law-stage-and-mirror-noise-rules`):
- Nhiễu nhiệt quy về cổng và điện áp lệch ngẫu nhiên $\sigma(V_{OS})$ của 5T-OTA được cho bởi:

$$
\overline{V_{n,\text{in}}^2} = 8kT\gamma\left(\frac{1}{g_{m1,2}} + \frac{g_{m3,4}}{g_{m1,2}^2}\right), \qquad \sigma^2(V_{OS}) = \sigma^2(\Delta V_{TH1,2}) + \left(\frac{g_{m3,4}}{g_{m1,2}}\right)^2 \sigma^2(\Delta V_{TH3,4})
$$

- Cả hai phương trình đều yêu cầu **$g_{m3,4} \ll g_{m1,2}$** (lý tưởng $g_{m3,4} / g_{m1,2} \le 0{,}3\text{–}0{,}5$), nhưng đồng thời cực gương $\omega_m \approx \frac{g_{m3,4}}{2 C_{GS3,4}} \propto \frac{\mu_p |V_{OV3,4}|}{L_{3,4}^2}$ lại đòi hỏi **không được chọn $L_{3,4}$ quá dài** đến mức $\omega_m < 3\,\omega_{GBW}$! Do đó điểm cân bằng tối ưu trên 90nm/65nm/45nm được xác lập theo bảng sau:

| Nhánh linh kiện | Vùng $g_m/I_D$ mục tiêu | Dự trữ $V_{DS,\min}$ | Chiều dài kênh $L$ | Mục tiêu Tối ưu Đa Chỉ tiêu |
| :--- | :--- | :--- | :--- | :--- |
| **Cặp đầu vào $M_1, M_2$** | $16\text{–}22\text{ V}^{-1}$ (nghịch đảo vừa–yếu) | $80\text{–}110\text{ mV}$ | $(2\text{–}4)L_{\min}$ | Cực đại hóa $g_{m1,2}$ trên mỗi $\mu\text{A}$, nén nhiễu và offset từ gương tải, mở rộng ICMR. |
| **Gương tải tích cực $M_3, M_4$** | $7\text{–}10\text{ V}^{-1}$ (nghịch đảo mạnh–vừa) | $180\text{–}230\text{ mV}$ | $(3\text{–}6)L_{\min}$ | Giữ $g_{m3,4} \le 0{,}45\,g_{m1,2}$ giảm nhiễu/offset, nhưng kiểm soát $L_{3,4}$ để $\omega_m \ge 3\,\text{GBW}$! |
| **Nguồn dòng đuôi $M_5$** | $8\text{–}12\text{ V}^{-1}$ | $150\text{–}200\text{ mV}$ | $(5\text{–}10)L_{\min}$ | Tăng $R_{SS} = r_{O5}$ để nâng $\text{CMRR}_{\text{sym}}$ theo PT (5.41) mà vẫn giữ đáy ICMR thấp. |

*(Mẹo điện áp thấp $V_{DD} = 0{,}9\text{–}1{,}0\text{ V}$:* Nếu trần ICMR $V_{DD} - |V_{GS3}| + V_{TH1}$ quá chật do $|V_{GS3}|$ lớn, ưu tiên chuyển sang bản đối ngẫu **đầu vào PMOS + gương dòng tích cực NMOS** để ICMR vươn xuống tận $0\text{ V}$ và cực gương NMOS nhanh gấp $2{,}5\times$ cực gương PMOS!).

### 5.2. Quy trình Kiểm chứng Chuẩn trong Cadence Virtuoso / Spectre
1. **Kiểm chứng điểm cân bằng đối xứng không gây tự trôi:** Đặt mạch trong cấu hình hồi tiếp đơn vị DC (hoặc dùng balun lý tưởng giữ $V_{in1,\text{DC}} = V_{in2,\text{DC}} = V_{in,\text{CM}}$ và kiểm tra `V(vout) - V(net_F)`): tại góc danh định đối xứng, $|V_{out,\text{DC}} - V_F|$ phải bằng $0$ tới mức microvôn, xác nhận không bị lệch CLM.
2. **Đối chiếu trực tiếp công thức chính xác (5.38) và CMRR (5.41):** Trích xuất `gm`, `gds` từ `dcOpInfo` và so sánh với độ lợi `ac` tần số thấp của kích thích vi sai (`vdm = 1`) và chế độ chung (`vcm = 1`).
3. **Phát hiện Cực Gương & Doublet bằng Đồ thị Pha & Đáp ứng Xung Bước Nhảy (`ac`, `pz`, `tran`):** Chạy `pz` đọc cặp cực–zero quanh $\omega_m$ và $2\omega_m$; đóng vòng bộ đệm độ lợi đơn vị (`vout` nối `vin_minus`), cấp xung bước nhảy nhỏ $10\text{ mV}$ trong `tran` và vẽ sai số logarit `log10(abs(VT("/vout") - V_final) / 0.01)` để kiểm tra xem có xuất hiện độ gãy khúc thành hai độ dốc (chữ ký đặc trưng của *doublet slow-settling tail*) hay không!

```text
; Mẫu biểu thức ADE / Spectre kiểm chứng Cặp Vi sai Tải Gương Dòng Tích cực:
V_Mirror_Diff_mV = 1e3 * abs(v("/vout" ?result "dcOp") - v("/vf" ?result "dcOp")) ; ~ 0 mV tai can bang
gm1_val          = pv("M1" "gm")
ro1_val          = 1.0 / pv("M1" "gds")
gm4_val          = pv("M4" "gm")
ro4_val          = 1.0 / pv("M4" "gds")
Av_Exact_538     = gm1_val * (ro1_val*ro4_val/(ro1_val+ro4_val)) * (2*gm4_val*ro4_val + 1) / (2*(gm4_val*ro4_val + 1))
CMRR_Sym_dB      = dB20(mag(VF("/vout")) / mag(XF("/vcm_src")))                   ; Doi chieu PT (5.41)
f_Mirror_Est_Hz  = pv("M3" "gm") / (2*3.14159 * (abs(pv("M3" "cgg")) + abs(pv("M4" "cgg")) + abs(pv("M1" "cdd"))))
```

---

## 6. Mốc Đối chiếu Sách Razavi & Thuật ngữ Chuẩn CLB

### 6.1. Đối chiếu Sách Gốc Razavi (2nd Edition) & Chú giải Học thuật CLB
| Mục / Trang (Razavi 2nd Ed.) | Phương trình & Hình đối chiếu | Nội dung cốt lõi & Ghi chú Hiệu đính CLB (`NG`) |
| :--- | :--- | :--- |
| **§4.3–4.4**, tr. 118–126 (PDF 19–27) | PT (4.58), (4.60); Hình 4.37(a) | Cơ sở CMRR cặp vi sai đối xứng dưới lệch $\Delta g_m$ (PT 4.58) và tải PMOS mắc diode dùng khái niệm mạch nửa $A_v \approx -g_{mN}/g_{mP}$ (PT 4.60). |
| **§5.3 & §5.3.1**, tr. 146–152 (PDF 13–19) | PT (5.22), (5.26); Hình 5.22–5.30; Ví dụ 5.8–5.10 | Chứng minh đọc đơn đầu trên tải nguồn dòng thụ động mất một nửa hỗ dẫn (PT 5.22, 5.26) và phân tích tín hiệu lớn 5T-OTA. **Lưu ý `NG05-02` (tr. 147):** ngay trước PT (5.20), bản in gốc xuất hiện ký tự in nghiêng $a$ không định nghĩa trong cụm "$r_{O2}\,a$". **Lưu ý `NG05-01` (tr. 150, Ví dụ 5.8):** bản in gốc liệt kê "$M_1, M_2$, and $M_4$ turn off" rồi ngay sau đó viết "$M_2$ and $M_5$ remain on"; đối chiếu mạch cho thấy transistor ngắt cùng $M_1, M_4$ ở danh sách đầu chính là $M_3$! |
| **§5.3.2**, tr. 152–156 (PDF 19–23) | PT (5.28), (5.33), (5.35), (5.38); Hình 5.31–5.36; Ví dụ 5.11–5.12 | Tại sao nút đuôi $P$ mất đất ảo chặt chẽ; phép chồng chập hai bước cho $R_{out} \approx r_{O2}\parallel r_{O4}$ (PT 5.28) và dẫn xuất nghiệm đóng chính xác tuyệt đối (PT 5.33, 5.35, 5.38). |
| **§5.3.3–5.3.4**, tr. 156–160 (PDF 23–27) | PT (5.41), (5.47), (5.55), (5.57); Hình 5.37–5.42; Ví dụ 5.13 | Độ lợi chế độ chung khi đối xứng hoàn hảo (PT 5.41), bóc tách lỗi ngụy biện "$A_{\text{CM}}=0$" qua dòng hụt của $r_{O3}$ (PT 5.47), và $A_{\text{CM}}$ tổng hợp dưới lệch $g_{m1} \neq g_{m2}$ (PT 5.55, 5.57). |
| **§6.6.2**, tr. 201–203 (PDF 29–31) | PT (6.91), (6.94), (6.95), (6.96); Hình 6.40–6.41 | Hàm truyền bậc hai của cặp vi sai tải gương dòng tích cực (PT 6.91), cực gương $\omega_{p2} \approx g_{mP}/C_E$ (PT 6.94) và mô hình cộng hai đường nhanh–chậm sinh LHP zero $2\omega_{p2}$ (PT 6.95–6.96). |

### 6.2. Bảng Thuật ngữ Chuẩn CLB Vi Mạch Sử dụng trong Thẻ
| Mã CLB | Thuật ngữ Tiếng Anh | Thuật ngữ Tiếng Việt Chuẩn | Ghi chú Ngữ cảnh |
| :--- | :--- | :--- | :--- |
| `T764` | differential pair with active current mirror | cặp vi sai dùng gương dòng tích cực | Tên cấu trúc đầy đủ của mạch chuyển đổi vi sai sang đơn đầu ở §5.3 |
| `T755` / `T1164` | five-transistor OTA | OTA năm transistor | Tên gọi công nghiệp tương đương của cấu trúc Hình 5.27 |
| `T699` / `T1587` | active current mirrors / active current mirror load | gương dòng tích cực / tải gương dòng tích cực | Gương dòng đóng vai trò xử lý và cộng dòng tín hiệu xoay chiều (khác gương phân cực tĩnh) |
| `T612` | superposition | nguyên lý chồng chập | Công cụ tuyến tính cốt lõi để tách tính toán $G_m, R_{out}$ và cộng hai đường nhanh–chậm |
| `T624` / `T967` | half circuit / differential half circuit | mạch nửa / nửa mạch vi sai | Chỉ đúng chặt chẽ khi hai nhánh đối xứng hoàn toàn; bị vi phạm một phần tại nút $P$ của 5T-OTA |
| `T973` | mirror pole | cực gương | Cực không trội $\omega_m \approx g_{mP}/C_E$ hình thành tại nút cổng nối diode của gương dòng |
