# Thao tác Cadence theo dự án

Kiểm tra `project.json`, `cds.lib`, library/cell/view, PDK attachment và thư mục hiện hành trước thao tác. Mở folder hay Virtuoso không tự xác nhận DUT đang active; cần đọc session/cellView bằng giao diện đã được kiểm tra hoặc hỏi chọn DUT nếu còn mơ hồ.

Trước khi chỉnh kích thước linh kiện, thêm nhánh phân cực hay đổi cấu trúc mạch trên bất kỳ tiến trình nào (`180nm`, `90nm`, `65nm`, `45nm`), chạy [kb_lookup.py](../tools/kb_lookup.py) và [kb_fetch.py](../tools/kb_fetch.py) (xem [../kb/README.md](../kb/README.md)) để đối chiếu **bất biến cấu trúc độc lập tiến trình** (`checklists`) và lộ trình nâng cấp theo sách Razavi.

Với IC617, ưu tiên flow SKILL/OCEAN native đã kiểm chứng trong [ic617_oa_cdf.il](../tools/ic617_oa_cdf.il); khi cần bridge Python, đánh giá `unihd-cag/skillbridge` trước. Đọc [ic617-adapters.md](ic617-adapters.md). `Arcadia-1/virtuoso-bridge-lite` là reference API tùy chọn (chỉ cài làm tài liệu tham khảo, không đồng nghĩa daemon đã hoạt động; xem [compatibility.md](../environment/rhel6-ic617/compatibility.md)). Với IC617/Spectre15.1, thử truy vấn chỉ đọc trước, rồi thao tác trên cell nháp/bản sao đã backup khi thực sự cần. Không thay `.cdsinit`, kích hoạt listen port, mở firewall hoặc nâng Python hệ thống như bước ngầm.

Đối chiếu SKILL API với manual cài máy; CDF và model thật quyết định pin order, parameter name và netlisting:
- Khi đổi `l`, `w`, `fw`, `fingers`, `m` (MOSFET) hoặc `segW`, `segL` (điện trở phân đoạn) qua SKILL, bắt buộc khởi tạo `PasCdfFormInit(cdf)` với `cdfgData`/`cdfgForm` và thực thi `param~>callback` để cập nhật `simM`, `simW`, `ad`, `as`, `pd`, `ps` / `r`, `effW`, `effL` (xem mẫu chuẩn trong [ic617_oa_cdf.il](../tools/ic617_oa_cdf.il)). Chỉ gọi `dbReplaceProp` đơn thuần sẽ làm lệch thông số netlist Spectre so với ADE!
- Sau mọi thao tác schematic, chạy `schCheck(cv)`, kiểm tra số nhãn dây (`wire` label) và xuất netlist qua OCEAN `createNetlist(?recreateAll t ?display nil)` để xác nhận kết nối từng chân `instTerms`.
- Khi đo độ ổn định vòng hồi tiếp (Op-Amp, CMFB, LDO, Bandgap), ưu tiên phân tích `stb` của Spectre với `iprobe` / `diffstbprobe` giữ nguyên điểm làm việc DC và tải hai chiều (theo thẻ `tech-bode-blackman-middlebrook-stb`), trích `phaseMargin` / `gainMargin` qua OCEAN (`selectResult("stb1-margin.stb")`) hoặc đọc trực tiếp file PSF ASCII bằng [psf_ascii_reader.py](../tools/psf_ascii_reader.py) tương thích Python 2.6.6.

Runner phải dùng cwd dự án, netlist/model path xác định, run ID và log riêng. Kiểm tra exit status, fatal/error, convergence và analysis/data tồn tại; “process completed” chưa chứng minh dữ liệu đủ để chấm spec. Các đường `.../apps/cadence/data/sessions/virtuoso-*` của launcher Desktop là session tạm, không phải vị trí dự án mặc định. Library thiết kế cần nằm trong `design/` thuộc dự án và `cds.lib` trỏ đúng.

## Kỷ luật Dung lượng PSF ASCII, Quy chuẩn Schematic IC617 & Linh kiện Thực tế

### 1. Tiết kiệm dung lượng đĩa (`psfascii`)
- Mọi netlist có `tran`/`ac`/`stb`/`pstb`/`noise`/`pnoise`/`pss`/`pac` bắt buộc đặt `saveOptions options save=selected` kèm lệnh `save` tường minh các nút/dòng cần đo (`dcOpInfo` vẫn lưu tự động cho `op-audit`), nhờ đó kích thước mỗi góc giảm từ `~85 MB` xuống `~0,5–3 MB`.
- Trong giai đoạn tối ưu nháp chỉ quét 4–6 góc biên xấu nhất và tái sử dụng một thư mục bằng `--overwrite-run`; chỉ chạy đủ lưới PVT một lần trên bản chốt và dọn các `psf/` cũ bằng `python -B .../cadence_exec.py prune-runs --project . --keep 2` (`cadence_exec.py` tự chặn khi đĩa trống `< 512 MB`).

### 2. Chiều xoay Transistor chuẩn SGK Razavi & Phân khối Schematic (kiểm tra tự động bằng `design-audit`)
- **Chiều xoay bắt buộc (kênh thẳng đứng `R0` / `MY`, cấm xoay ngang `R90`/`R270` hoặc lộn ngược `MX`/`R180` trừ công tắc truyền dòng được khai báo `--expect-sideways`):**
  - **PMOS (tải gương, cascode trên, diff-pair PMOS, pass PMOS):** Cực **Source (`S`) hướng LÊN trên** về phía thanh `VDD`/`VIN`, cực **Drain (`D`) hướng XUỐNG dưới** (`y(S) > y(D)`).
  - **NMOS (cặp vi sai, gương dòng dưới, cascode dưới, nguồn đuôi, xả/kẹp xuống GND):** Cực **Source (`S`) hướng XUỐNG dưới** về phía thanh `VSS`/`GND`, cực **Drain (`D`) hướng LÊN trên** (`y(D) > y(S)`).
  - **Đối xứng cặp khớp nhau (`R0` ↔ `MY`):** Hai transistor của cặp vi sai, gương dòng, cascode phải đặt ngang hàng nhau (`y` bằng nhau) với hai cực Gate đối mặt nhau (`trái = R0`, `phải = MY`) nối thẳng ngang thật ngắn.
- **Bố cục theo luồng tín hiệu & Khoảng cách gọn (`bbox <= 24 x 14`, `crossovers <= 15`):**
  - Đặt ray nguồn `VDD`/`VIN` liên tục phía trên cùng, ray `VSS`/`GND` liên tục phía dưới cùng.
  - Sắp xếp các khối chức năng từ **trái sang phải** theo thứ tự dòng tín hiệu (ví dụ với LDO: `BIAS & STARTUP` → `ERROR AMP` → `COMPENSATION / DRIVER` → `PASS PMOS & FB DIVIDER`, cụm phụ `SRE / CLAMP` tách gọn bên dưới kèm nhãn chú thích khối `note label`), thu gọn khoảng cách trong khối đủ thoáng không đè chữ, không trải rộng lan man.
  - Nối dây vuông góc thật bên trong từng khối; chỉ dùng `wire label` ngắn, sạch cho bus phản hồi hoặc phân phối bias dài vượt qua $\ge 2$ khối để giữ `crossovers <= 15` (cấm tuyệt đối kiểu cột `STUB` đứt đoạn).
  - **Quy tắc phân cấp bắt buộc:** Khi mạch vượt quá **`35` linh kiện**, **bắt buộc tách thành các subcell có symbol riêng** (`bias_startup`, `error_amp`, `driver_comp`, `protection`, `top`) thay vì nhồi phẳng toàn bộ vào 1 trang duy nhất.

### 3. Giới hạn Linh kiện Thụ động Thực tế trên Silicon (Chống "nhồi R/C lý tưởng")
- **Cấm dùng R/C lý tưởng khổng lồ** để ép đạt thông số mô phỏng pre-layout:
  - **Tụ điện on-chip (Capless LDO / Op-Amp):** Tổng tụ nội bộ $\sum C_{\text{on-chip}} \le 20\text{ pF}$ (khuyến nghị $\le 15\text{ pF}$), mỗi tụ đơn lẻ $\le 10\text{ pF}$, luôn nhỏ hơn nhiều so với tải `CL`, và diện tích tụ ước tính ($\approx 2\text{ fF}/\mu\text{m}^2$) không phình gấp $> 50\times$ tổng diện tích MOS. Với mạch bù Capless LDO 45 nm/90 nm, ưu tiên **Miller / Ahuja cascode / FVF / DFC** giúp $C_c \approx 2\text{–}8\text{ pF}$ thay vì đặt tụ `30–130 pF`.
  - **Điện trở on-chip:** Tổng điện trở danh định $\sum R \le 1\text{ M}\Omega$ (khuyến nghị $\le 500\text{ k}\Omega$), mỗi điện trở đơn lẻ $\le 200\text{–}300\text{ k}\Omega$. Tuyệt đối không đặt điện trở lý tưởng hàng $\text{M}\Omega$ (`2–25 MOhm`); khi cần trở lớn tạo hằng số thời gian RC hoặc khởi động dòng thấp, phải thay bằng **MOS hoạt động vùng triode/dưới ngưỡng hoặc pseudoresistor MOS thật** để phản ánh đúng ký sinh và sai lệch theo góc PVT.
  - **Kiểm định tự động bắt buộc:** Chạy đồng thời:
    `python -B .../psf_audit.py design-audit <dut.scs> --schematic <dump.json> --forbid-ideal-passives --fail-on-violation` (dùng `--forbid-ideal-passives` ở bước chốt PDK, bỏ cờ này khi còn ở bước thử nhanh pre-PDK nhưng vẫn giữ trần R/C thực tế).
