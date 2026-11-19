---
{
  "id": "law-stage-and-mirror-noise-rules",
  "kind": "law",
  "domain": "dynamics-noise-feedback",
  "title_vi": "Quy luật Nhiễu của Các Tầng Khuếch đại Đơn, Gương Dòng & Cặp Vi sai (Stage, Cascode, Mirror & Diff-Pair Noise Rules)",
  "title_en": "Input-Referred Noise Rules of CS, CG, SF, Cascode, Current Mirrors, and Differential Pairs",
  "summary": "Tổng hợp các định luật bất biến về đóng góp nhiễu theo vai trò cấu trúc: vì sao transistor cascode và nguồn dòng đuôi hầu như vô hình với nhiễu tần số thấp, trong khi tải nguồn dòng và gương dòng bơm thẳng nhiễu vào đường tín hiệu trừ khi thiết kế gm_load << gm_in (Vov lớn, L dài), cùng định luật đánh đổi nhiễu–công suất.",
  "diagram": "../../diagrams/mos-noise-input-referred.svg",
  "razavi_refs": [
    {
      "chapter": 7,
      "section": "7.4-7.7",
      "pages": "243-264",
      "equations": ["7.75", "7.78", "7.81", "7.85", "7.98", "7.103", "7.111", "7.113", "7.114", "7.125", "7.126", "7.140", "7.142"]
    }
  ],
  "glossary_codes": ["T021", "T023", "T026", "T050", "T082", "T499", "T586", "T1139", "T1147", "T1166", "T1178", "T1179"],
  "process_agnostic": true,
  "roles": {
    "primary_input_transconductor": "Transistor đầu vào (M1 trong CS / cặp M1-M2 trong vi sai) phải tối đa hóa gm1 (Vov nhỏ, gm/ID cao) để đè nhiễu mọi phần tử đứng sau",
    "parallel_active_load_or_mirror": "Nguồn dòng tải và gương dòng bơm dòng nhiễu trực tiếp vào nút tín hiệu, bắt buộc tối thiểu hóa gm_load (Vov lớn, L dài, gm/ID thấp)",
    "cascode_shield_device": "Transistor cascode M2 bị suy biến bởi trở kháng cực lớn rO1 ở cực nguồn nên tự nuốt dòng nhiễu của chính nó ở tần số thấp, chỉ lộ nhiễu khi CX ngắn mạch ở tần số cao",
    "tail_bias_current_source": "Nguồn dòng đuôi của cặp vi sai cân xứng chỉ bơm nhiễu chế độ chung chia đều hai nhánh nên triệt tiêu ở ngõ ra vi sai tần số thấp"
  },
  "symptoms_addressed": [
    "active-load-dominating-amplifier-noise",
    "current-mirror-bias-line-injecting-noise",
    "degenerated-cs-unexpected-noise-increase",
    "confusion-over-cascode-and-tail-source-noise"
  ],
  "limitations": [
    "cascode-noise-rises-at-high-frequencies-due-to-internal-node-capacitance-cx",
    "tail-current-noise-mixes-to-differential-output-under-large-signal-switching-or-ac-asymmetry",
    "lowering-gm-load-requires-larger-vds-min-eating-into-output-voltage-swing"
  ],
  "checklists": ["common-mos", "single-stage", "current-mirror", "differential-pair"]
}
---

## 1. Bản chất Nguyên lý, Sơ đồ Mạch & Vai trò Từng Nhánh Cấu trúc

Trong một sơ đồ mạch khuếch đại hay Op-Amp có hàng chục MOSFET, không cần giải lại KCL cho từng transistor nếu ta nắm vững **Quy tắc Kiểm tra Nhanh của Razavi (Inspection Rule, §7.4–§7.6 & §9.12)**: *Hãy tưởng tượng nhích nhẹ điện áp cực cổng của transistor thứ $k$ đi một lượng nhỏ $\Delta V_{G,k}$ (tương ứng nguồn nhiễu quy về cổng $V_{n,k}$) và xem dòng ngắn mạch ngõ ra thay đổi bao nhiêu.* Nếu $\Delta V_{G,k}$ tạo ra dòng ngõ ra lớn $g_{m,k} \Delta V_{G,k}$, transistor đó là **thủ phạm nhiễu hạng nặng**; nếu dòng của nó bị chặn bởi một nguồn dòng hở mạch ở cực nguồn, transistor đó **gần như câm nhiễu ở tần số thấp**!

![Quy đổi nhiễu về cực cổng và tổng hợp các thành phần nhiễu trong tầng khuếch đại MOS](../../diagrams/mos-noise-input-referred.svg)

Từ nguyên lý đó, mọi transistor trong mạch tương tự phân hóa thành 4 nhóm hành vi nhiễu hoàn toàn đối lập:
1. **Transistor Hỗ dẫn Đầu vào ($M_1$ ở CS, $M_1\text{–}M_2$ ở Cặp Vi sai):** Tín hiệu cần khuếch đại cũng đi qua chính $g_{m1}$, nên khi quy nhiễu về ngõ vào, nhiễu của chính nó tỉ lệ với $\frac{1}{g_{m1}}$, đồng thời $g_{m1}^2$ đứng ở mẫu số làm "lá chắn" chia nhỏ nhiễu của tất cả tải và tầng sau!
2. **Nguồn Dòng Tải & Nhánh Gương Dòng Song song ($M_{\text{load}}$, $M_{\text{mirror}}$):** Không mang tín hiệu đầu vào ở cực cổng (hoặc chỉ dùng làm tải dòng), nhưng cực máng nối thẳng vào đường dòng tín hiệu! Dòng nhiễu $4kT\gamma g_{m,\text{load}}$ đổ 100% vào đường tín hiệu, rồi khi quy về ngõ vào bị nhân với tỉ số $\frac{g_{m,\text{load}}}{g_{m1}^2}$ (cho nhiễu nhiệt) và $\left(\frac{g_{m,\text{load}}}{g_{m1}}\right)^2$ (cho nhiễu $1/f$)!
3. **Transistor Cascode ($M_2$ chồng trên $M_1$):** Cực nguồn của $M_2$ nhìn xuống thấy trở kháng cực cao $r_{O1}$ của $M_1$. Theo KCL một nhánh nối tiếp không phân nhánh ở tần số thấp, dòng cực máng của $M_1$ bị khóa cứng, nên nguồn dòng nhiễu nội tại $I_{n2}$ nối giữa máng và nguồn của $M_2$ chỉ chạy vòng tròn bên trong chính $M_2$ (làm nhấp nhô nhẹ điện thế nút nội $X$) chứ **không thể thoát ra tải**!
4. **Nguồn Dòng Đuôi Cặp Vi sai ($M_{\text{tail}}$):** Tại điểm cân bằng tĩnh đối xứng ($\Delta V_{in} = 0$), dòng nhiễu $I_{n,\text{tail}}$ chia đôi hoàn toàn bằng nhau ($\frac{1}{2} I_{n,\text{tail}}$) lên cả hai nhánh trái–phải, trở thành nhiễu chế độ chung thuần túy và tự triệt tiêu trong ngõ ra vi sai (cũng như tự triệt tiêu qua gương dòng $1:1$ ở tần số thấp!).

---

## 2. Hệ Phương trình Cốt lõi & Tư duy "Nhìn Mạch Đọc Nhanh" (Analysis by Inspection)

### 2.1. Tầng Nguồn Chung (CS) & CS Suy biến Cực nguồn (§7.4.1, Phương trình 7.75–7.85 & Bài tập 7.13, 7.18)
- **CS tải nguồn dòng PMOS $M_2$ (Hình 7.42):** Tổng dòng nhiễu ngắn mạch ngõ ra là $\overline{I_{n,\text{out}}^2} = \overline{I_{n1}^2} + \overline{I_{n2}^2}$. Chia cho $g_{m1}^2$, điện áp nhiễu tổng quy về cổng $M_1$ (gồm cả nhiễu nhiệt và $1/f$) là (Phương trình 7.75 cho tải $R_D$, Phương trình 7.78 cho tải nguồn dòng $M_2$, và Phương trình 7.85 cho tải $M_2 \parallel R_D$):

$$
\overline{V_{n,in}^2} = 4 k T \gamma \left( \frac{1}{g_{m1}} + \frac{g_{m2}}{g_{m1}^2} \right) + \frac{K_N}{C_{ox} W_1 L_1 f} + \frac{K_P}{C_{ox} W_2 L_2 f} \cdot \left(\frac{g_{m2}}{g_{m1}}\right)^2
$$

Nếu tích phân tổng nhiễu nhiệt trên tụ tải ngõ ra $C_L$ của tầng một cực này (Phương trình 7.81):

$$
\overline{V_{n,\text{out,tot}}^2} = \gamma (g_{m1} + g_{m2})(r_{O1} \parallel r_{O2}) \frac{k T}{C_L}
$$

- **CS suy biến bằng điện trở cực nguồn $R_S$ tải $R_D$ (Bài tập 7.13 & 7.18, Hình 7.76 & 7.78):** Suy biến nguồn cải thiện độ tuyến tính nhưng **luôn làm xấu đi nhiễu quy về ngõ vào** vì cộng thẳng nhiễu nhiệt $4kT R_S$ và làm giảm hỗ dẫn hiệu dụng khiến nhiễu của tải $R_D$ bị đẩy tăng lên $(1 + g_{m1} R_S)^2$ lần:

$$
\overline{V_{n,in,\text{deg}}^2} = \frac{4 k T \gamma}{g_{m1}} + 4 k T R_S + \frac{4 k T}{R_D} \left( \frac{1}{g_{m1}} + R_S \right)^2
$$

### 2.2. Tầng Cổng Chung (CG) & Tầng Theo Nguồn (SF) (§7.4.2–7.4.3, Phương trình 7.98–7.111)
- **Tầng CG phân cực bằng nguồn dòng dưới nguồn $M_2$ và tải nguồn dòng trên máng $M_3$ (Ví dụ 7.20, Hình 7.49):** Cực kỳ bất lợi về nhiễu dòng vì cả hai nguồn dòng phân cực $M_2$ (dưới cực nguồn) và $M_3$ (trên cực máng) đều bơm thẳng nhiễu vào mạch (Phương trình 7.98, 7.103):

$$
\overline{V_{n,in,\text{CG}}^2} = \frac{4 k T \gamma (g_{m1} + g_{m3})}{(g_{m1} + g_{mb1})^2}, \qquad \overline{I_{n,in,\text{CG}}^2} = 4 k T \gamma (g_{m2} + g_{m3})
$$

- **Tầng Theo Nguồn (Source Follower $M_1$ phân cực bởi nguồn dòng $M_2$, Hình 7.51):** Tuy độ lợi điện áp nhỏ hơn 1 ($A_v = \frac{g_{m1}}{g_{m1} + g_{mb1}}$), các hệ số $g_{mb1}$ rút gọn sạch sẽ để cho điện áp nhiễu nhiệt quy về ngõ vào **giống hệt tầng CS** (Phương trình 7.111):

$$
\overline{V_{n,in,\text{SF}}^2} = 4 k T \gamma \left( \frac{1}{g_{m1}} + \frac{g_{m2}}{g_{m1}^2} \right)
$$

### 2.3. Tầng Cascode: Vô Hình Ở Tần Số Thấp, Lộ Nhiễu Ở Tần Số Cao (§7.4.4, Phương trình 7.112–7.113)
Xét transistor cascode $M_2$ chồng trên $M_1$, gọi tổng điện dung ký sinh tại nút nội $X$ là $C_X$ và điện trở ra của $M_1$ là $r_{O1}$. Dòng nhiễu $I_{n2}$ của $M_2$ nhìn xuống nút $X$ thấy tổng trở $Z_X(s) = r_{O1} \parallel \frac{1}{s C_X}$. Tỉ phần dòng nhiễu của $M_2$ thoát ra ngõ ra là:

$$
\left|\frac{I_{out,n2}}{I_{n2}}\right| \approx \left| \frac{1}{1 + (g_{m2} + g_{mb2}) \left( r_{O1} \parallel \dfrac{1}{s C_X} \right)} \right|
$$

- Ở **tần số thấp** ($\omega \ll \frac{1}{r_{O1} C_X}$): mẫu số xấp xỉ $g_{m2} r_{O1} \gg 1$, nên công suất nhiễu của $M_2$ bị nén đi **$(g_{m2} r_{O1})^2$ lần** ($\sim 20\text{–}40\text{ dB}$) — hoàn toàn bỏ qua được!
- Ở **tần số cao** (như trong LNA RF khi $\frac{1}{\omega C_X} \sim \frac{1}{g_{m2}}$): tụ $C_X$ tạo điểm tựa đất xoay chiều cho cực nguồn $M_2$ (Phương trình 7.113), khiến $M_2$ bơm dòng nhiễu đáng kể ra ngõ ra!

### 2.4. Gương Dòng, Cặp Vi sai & Định luật Đánh đổi Nhiễu–Công suất (§7.5–§7.7)
- **Gương dòng sao chép tỉ lệ $1 : K$ ($I_{out} = K I_{\text{REF}}$, Hình 7.53–7.54):** Nếu nhánh chuẩn $M_{\text{REF}}$ bản thân đã mang dòng nhiễu $\overline{I_{n,\text{REF}}^2}$ từ mạch tạo tham chiếu, bộ gương không chỉ nhân nhiễu đó lên $K^2$ lần mà còn cộng thêm nhiễu tự sinh của cặp transistor gương:

$$
\overline{I_{n,\text{out,mirr}}^2} = K^2 \overline{I_{n,\text{REF}}^2} + 4 k T \gamma g_{m,\text{out}} \left( 1 + K \right) \quad (\text{khi } g_{m,\text{out}} = K g_{m,\text{REF}})
$$

Để chặn nhiễu tần số cao từ nhánh tham chiếu $M_{\text{REF}}$ truyền sang hàng loạt nhánh khuếch đại trên chip, gắn lọc thông thấp $R_B C_B$ trên đường áp cổng phân cực $V_b$ (Phương trình 7.118, chú ý không để dòng rò cổng tạo sụt áp DC qua $R_B$!).
- **Cặp vi sai tải thụ động $R_D$ so với tải chủ động 5T-OTA (Phương trình 7.125, 7.126, 7.140, 7.142):**
  Với cặp vi sai $M_1\text{–}M_2$ (mỗi transistor có hỗ dẫn $g_{m1,2}$) và tải chủ động $M_3\text{–}M_4$ (mỗi transistor có hỗ dẫn $g_{m3,4}$):

$$
\overline{V_{n,in,\text{diff}}^2} = 8 k T \gamma \left( \frac{1}{g_{m1,2}} + \frac{g_{m3,4}}{g_{m1,2}^2} \right) + \frac{2 K_N}{C_{ox} (WL)_{1,2} f} + \frac{2 K_P}{C_{ox} (WL)_{3,4} f} \left(\frac{g_{m3,4}}{g_{m1,2}}\right)^2
$$

Chú ý hệ số **$8 k T \gamma$** (= $2 \times 4 k T \gamma$): với cùng $g_m$ mỗi nhánh như một tầng CS đơn, cặp vi sai có công suất nhiễu gấp đôi tầng CS đơn (vì hai transistor mắc nối tiếp đối với điện áp vi sai!), đổi lại biên độ tín hiệu vi sai cũng tăng gấp đôi.
- **Định luật Nhân Tỉ lệ Tuyến tính Nhiễu–Công suất (Noise-Power Trade-off, §7.7, Phương trình 7.143–7.144):** Nếu ta ghép song song $M$ bản sao giống hệt của toàn bộ bộ khuếch đại (tức nhân toàn bộ chiều rộng transistor $W \to M \cdot W$, nhân dòng tiêu thụ $I_{\text{supply}} \to M \cdot I_{\text{supply}}$, giảm điện trở $R \to R/M$, nhân tụ $C \to M \cdot C$, giữ nguyên mọi điện áp phân cực, độ lợi và băng thông!):

$$
P_{\text{diss}} \propto M \quad \Longleftrightarrow \quad \overline{V_{n,in}^2} \propto \frac{1}{M} \quad \Longleftrightarrow \quad V_{n,in,\text{rms}} \propto \frac{1}{\sqrt{M}}
$$

**Hệ quả khắc nghiệt:** Muốn giảm một nửa điện áp nhiễu RMS ($-6\text{ dB}$ nhiễu, tăng $+6\text{ dB}$ dải động DR), bạn bắt buộc phải trả giá bằng **gấp $4\times$ công suất tiêu thụ và gấp $4\times$ diện tích silicon**!

---

## 3. Bất biến Cấu trúc & Các Bẫy Lỗi Kinh điển (Structural Invariants & Traps)

- **[INV-STAGE-NOISE-01] Định lý Bất đối xứng Định cỡ Đầu vào vs. Tải Chủ động (The Golden Sizing Duality for Noise):**
  Nhìn vào thừa số $\left(1 + \dfrac{g_{m,\text{load}}}{g_{m,\text{in}}}\right)$ trong nhiễu nhiệt và $\left(\dfrac{g_{m,\text{load}}}{g_{m,\text{in}}}\right)^2$ trong nhiễu $1/f$:
  - **Cặp đầu vào ($M_{1,2}$):** Phải cực đại hóa $g_{m,\text{in}}$ trên dòng cho trước $\implies$ định cỡ ở vùng **nghịch đảo vừa/yếu ($V_{OV}$ nhỏ, $g_m/I_D$ cao $\sim 18\text{–}25\text{ V}^{-1}$)**, $W$ rộng.
  - **Nguồn dòng tải / Gương dòng / Nguồn dòng gập ($M_{\text{load}}$):** Phải cực tiểu hóa $g_{m,\text{load}}$ trên cùng dòng $I_D$ $\implies$ định cỡ ở vùng **nghịch đảo mạnh ($V_{OV}$ lớn, $g_m/I_D$ thấp $\sim 5\text{–}8\text{ V}^{-1}$)** và **chiều dài kênh $L_{\text{load}}$ dài** ($2\text{–}6\,L_{\min}$) để đồng thời nén mạnh nhiễu $1/f$ nhờ $(WL)_{\text{load}}$ lớn lẫn $\left(g_{m,\text{load}}/g_{m,\text{in}}\right)^2 \ll 1$!
  *(Tuyệt vời thay, quy tắc này trùng khớp 100% cùng chiều với Định luật Pelgrom để giảm điện áp lệch offset ở `law-pelgrom-mismatch-and-sizing-duality`!)*
- **[TRAP-STAGE-NOISE-01] Khi Nguồn Dòng Đuôi KHÔNG CÒN Vô Hình Với Nhiễu (§7.6, Phương trình 7.129–7.134):** Đừng tưởng nguồn dòng đuôi $M_{SS}$ luôn vô hại trong mọi trường hợp! Có **3 kịch bản thực tế** khiến nhiễu của $M_{SS}$ lọt thẳng ra ngõ ra vi sai:
  1. **Khi có tín hiệu vi sai lớn ở ngõ vào ($\Delta V_{in} \neq 0$) hoặc trong bộ trộn / VCO chuyển mạch:** Hai nhánh dẫn dòng lệch nhau ($I_{D1} \neq I_{D2}$, $g_{m1} \neq g_{m2}$), nên biến thiên dòng đuôi $\Delta I_{SS}$ điều chế biên độ tín hiệu và biến đổi tần số (up/down-conversion) thẳng thành nhiễu vi sai / nhiễu pha!
  2. **Ở tần số cao trong 5T-OTA đơn đầu:** Đường gương dòng $M_3\text{–}M_4$ bị trễ pha qua cực gương $\omega_m$, trong khi nhánh phải $M_2$ truyền tức thì, nên hai nửa dòng nhiễu đuôi không còn triệt tiêu nhau ở tần số gần $\omega_m$!
  3. **Khi tải hai bên bất đối xứng (mất cân bằng $\Delta R_D$ hoặc $\Delta C_L$).**
- **[TRAP-STAGE-NOISE-02] Chia Sẻ Chung Một Nhánh Chuẩn Gương Dòng Cho Cả Khối Mạch Nhạy Nhiễu:** Nếu một nhánh diode $M_{\text{REF}}$ nhỏ ($I_{\text{REF}} = 10\,\mu\text{A}$) nhân gương $1:20$ nuôi tầng đầu vào $200\,\mu\text{A}$ mà không có tụ lọc cổng $C_B$, nhiễu của $M_{\text{REF}}$ bị nhân công suất lên $20^2 = 400$ lần và thổi bùng nền nhiễu toàn mạch (nhất là đối với nhánh nguồn dòng gập trong Folded-Cascode; trong cặp vi sai cân bằng thì nhiễu cổng chung của hai tải đối xứng là đồng pha đối với vi sai hoàn toàn, nhưng nếu bất đối xứng vẫn rò sang vi sai).

---

## 4. Lộ trình Nâng cấp Cấu trúc & Bát giác Đánh đổi (Upgrade Paths & Design Octagon)

| Điểm yếu nhiễu của cấu trúc đang xét | Nâng cấp / Chuyển đổi cấu trúc (Canonical Node) | Hiệu quả đạt được | Đánh đổi trên Bát giác Thiết kế |
|---|---|---|---|
| Op-Amp Cascode Gập (`topo-folded-cascode-ota`) bị nhiễu cao do có tới 2 cặp nguồn dòng tải song song ($M_{7,8}$ và $M_{9,10}$) | Quay về `topo-telescopic-cascode-opamp` nếu biên độ tín hiệu và ICMR cho phép, hoặc nâng tầng đầu thành CS/Telescopic trong `topo-two-stage-opamp` | Loại bỏ hoàn toàn một cặp nguồn dòng gập khỏi ngân sách nhiễu Phương trình (9.91) (`concept-opamp-psrr-and-noise`) | Hẹp dải dao động ngõ ra và không nối tắt vào–ra trực tiếp được (với Telescopic), hoặc phải bù Miller (với Two-Stage) |
| Muốn giảm $g_{m,\text{load}}$ bằng cách tăng $V_{OV,\text{load}}$ nhưng làm cạn kiệt khoảng dự trữ điện áp ở $V_{DD} = 1{,}0\text{ V}$ | Dùng gương dòng cascode điện áp thấp `topo-lvccml-wide-swing-mirror` hoặc chuyển sang Op-Amp hai tầng `topo-two-stage-opamp` | Ở Op-Amp 2 tầng, nút ra tầng 1 chỉ dao động vài chục mV nên dành trọn $300\text{–}400\text{ mV}$ overdrive cho tải tầng 1 để triệt nhiễu! | Phải chi thêm dòng phân cực cho tầng thứ hai và mạch bù tần số |
| Tầng CG bị giới hạn hệ số nhiễu do nguồn dòng phân cực dưới cực nguồn | Dùng cuộn cảm cộng hưởng ở cực nguồn (trong RF LNA) hoặc cấu trúc khử nhiễu (Noise-Canceling CG-CS) | Triệt dòng nhiễu kênh của transistor CG tại ngõ ra trong khi cộng đồng pha tín hiệu | Tăng diện tích cuộn cảm hoặc thêm nhánh CS phụ tiêu thụ dòng |

---

## 5. Thích ứng Đa Tiến trình (90nm / 65nm / 45nm) & Cách Kiểm chứng trong Cadence / Spectre

### 5.1. Thích ứng Công nghệ Nanomet (90nm $\to$ 65nm $\to$ 45nm)
- **Không dùng công thức $\sqrt{W/L}$ kênh dài để ước lượng tỉ số nhiễu:** Trong công nghệ 90nm/65nm/45nm, cặp đầu vào chạy ở nghịch đảo vừa/yếu ($g_m/I_D \approx 20\text{ V}^{-1}$) còn tải chạy ở nghịch đảo mạnh ($g_m/I_D \approx 6\text{ V}^{-1}$). Vì hai nhánh mang cùng dòng DC $I_D$, tỉ số đóng góp nhiễu nhiệt đọc thẳng ngay từ tỉ số hiệu suất hỗ dẫn mà **không phụ thuộc công nghệ**:

$$
\frac{\overline{V_{n,\text{th,load}}^2}}{\overline{V_{n,\text{th,in}}^2}} = \frac{\gamma_{\text{load}}}{\gamma_{\text{in}}} \cdot \frac{(g_m / I_D)_{\text{load}}}{(g_m / I_D)_{\text{in}}} \approx \frac{6}{20} = 0{,}30 \quad (\text{tải chỉ cộng thêm } 30\%\text{ công suất nhiễu!})
$$

Công thức bất biến theo $g_m/I_D$ này giải thích vì sao phương pháp định cỡ $g_m/I_D$ (`tech-nanometer-vdsmin-gmid-sizing`) kiểm soát nhiễu chính xác tuyệt đối xuyên suốt 180nm $\to$ 90nm $\to$ 65nm $\to$ 45nm!

### 5.2. Quy trình Kiểm chứng trong Cadence Virtuoso / Spectre
1. **Kiểm tra Xác nhận Transistor Cascode "Câm Nhiễu" ở Tần số Thấp vs. Tần số Cao:**
   - Mở bảng `Noise Summary` (Spot Noise) tại `10 kHz`: xác nhận phần trăm đóng góp của các transistor cascode ($M_3, M_4, M_5, M_6$) chỉ dưới `< 1%`, trong khi cặp đầu vào ($M_1, M_2$) chiếm `60%–75%` và cặp tải nguồn dòng chiếm `20%–35%`.
   - Sau đó in bảng `Noise Summary` tại tần số cao gần hoặc trên $\text{GBW}$ (ví dụ `500 MHz` hoặc `2 GHz`): bạn sẽ thấy đóng góp của transistor cascode nhô lên rõ rệt đúng như Phương trình (7.113) dự đoán do tụ nút nội $C_X$ dẫn dòng!
2. **Kiểm tra Nhiễu Điều chế Thời gian của Nguồn Dòng Đuôi (`pnoise` cho mạch tuần hoàn):** Nếu mạch làm việc với tín hiệu lớn tuần hoàn (như bộ khuếch đại chuyển mạch, SC, mixer, VCO), phân tích `noise` tuyến tính quanh điểm tĩnh cân bằng sẽ bỏ sót hoàn toàn nhiễu chuyển đổi từ nguồn dòng đuôi — lúc đó bắt buộc dùng `pss` + `pnoise` trong SpectreRF!

---

## 6. Mốc Đối chiếu Sách Razavi & Thuật ngữ Chuẩn CLB

### 6.1. Đối chiếu Sách Gốc Razavi (2nd Edition)
- **Chương 7:** §7.4 *Noise in Single-Stage Amplifiers* — §7.4.1 *CS Stage* (tr. 244–249), §7.4.2 *CG Stage* (tr. 249–253), §7.4.3 *Source Followers* (tr. 253–254), §7.4.4 *Cascode Stage* (tr. 254); §7.5 *Noise in Current Mirrors* (tr. 254–256); §7.6 *Noise in Differential Pairs* (tr. 256–262); §7.7 *Noise-Power Trade-Off* (tr. 263–264).
- **Chú giải Hiệu đính Học thuật CLB (`NG07`):**
  - **`NG07-04` (tr. 247, Ví dụ 7.17, Hình 7.44b):** Trong sơ đồ tầng CS tải nguồn dòng song song điện trở $R_D$, nguồn dòng nhiễu của điện trở tải cực máng bị in nhầm nhãn là $\overline{I_{n,R1}^2}$; điện trở tải thực tế trên hình và trong Phương trình (7.85) là $R_D$.
  - **`NG07-05` (tr. 252, Phương trình 7.101–7.102):** Khi quy đổi nhiễu tải $M_3$ của tầng CG về ngõ vào, (7.101) viết theo biên độ $I_{n,in}\big|_{M3} \approx I_{n3}$ rồi sang (7.102) viết nối tiếp $\approx 4kT\gamma g_{m3}$ (vốn là bình phương trung bình $\overline{I_{n,in}^2}\big|_{M3}$, đơn vị $\text{A}^2/\text{Hz}$); hiểu bước (7.102) là mật độ phổ bình phương trung bình như viết tường minh ở (7.103).
  - **`NG07-06` (tr. 254, Hình 7.52c):** Khi giải thích trực quan vì sao transistor cascode ít nhiễu, câu cuối sách chỉ ghi gọn "$V_{out}/V_n$ vẫn lớn hơn rất nhiều" mà không ghi rõ vế so sánh là độ lợi từ nguồn nhiễu $V_{n2}$ tại cổng cascode tới $V_{out}$ (tức $|A_{v,\text{in}}| \gg |A_{v,\text{cas-gate}}|$ nhờ suy biến $r_{O1}$!).
  - **`NG07-07` & `NG07-08` (tr. 255–256, §7.5 & Hình 7.54):** Trong ví dụ số ở §7.5 (tr. 255) tính tụ lọc gương dòng $C_B^2 \gg 2{,}533 \times 10^{-18}$, đơn vị của $C_B^2$ phải là $\text{F}^2$ (sách in nhầm $\text{F}$); và ở tr. 256, ký hiệu $g_{m1,\text{REF}}$ chính là $g_{m,\text{REF}}$ của $M_{\text{REF}}$, còn nghịch đảo hằng số thời gian cho $\omega_c$ (rad/s) nên $f_c = \omega_c/(2\pi)$ (Hz).

### 6.2. Bảng Thuật ngữ Chuẩn CLB Vi Mạch Sử dụng trong Thẻ
| Mã CLB | Thuật ngữ Tiếng Anh | Thuật ngữ Tiếng Việt Chuẩn | Ghi chú Ngữ cảnh |
|---|---|---|---|
| `T1147` | gate-referred noise voltage | điện áp nhiễu quy về cực cổng | $\overline{V_{n,\text{gate}}^2} = \frac{4kT\gamma}{g_m} + \frac{K}{C_{ox}WLf}$ |
| `T1139` | input-referred thermal noise | nhiễu nhiệt quy về ngõ vào | Thành phần phẳng theo tần số quy về cửa vào |
| `T1178` | input-referred flicker noise | nhiễu nhấp nháy quy về ngõ vào | Thành phần tỉ lệ $1/f$ quy về cửa vào |
| `T1179` | degenerated common-source stage | tầng nguồn chung có suy biến cực nguồn | Tuyến tính hơn nhưng chịu thêm nhiễu nhiệt của $R_S$ |
| `T026` | current mirror | gương dòng | Bơm nhiễu mạnh nếu không lọc hoặc không hạ $g_m$ |
| `T1166` | noise-power trade-off | đánh đổi giữa nhiễu và công suất | Nhân $M$ lần công suất giảm $M$ lần phương sai nhiễu |
| `T050` | linear scaling | phép nhân tỉ lệ tuyến tính | Nhân đồng thời $W$ và $I_D$, giữ nguyên mật độ dòng và $L$ |
