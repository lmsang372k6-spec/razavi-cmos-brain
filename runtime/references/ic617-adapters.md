# Adapter IC617, Live CIW Bridge, CDF và dữ liệu mô phỏng PSF

Đọc khi cần tương tác Cadence Virtuoso IC617, thực thi Spectre 15.1 hoặc trích xuất số đo trên RHEL 6.5 (`Python 2.6.6`). Mặc định người dùng tự thiết kế và học; Codex giải thích, rà thiếu sót theo [Bộ não Tri thức Razavi](../kb/README.md) và sửa phần được yêu cầu. Không tự chuyển topology, ghi đè xóa cell của người dùng hay chạy chiến dịch tối ưu khi chưa được duyệt.

## Thứ tự lựa chọn công cụ nội bộ (`100% Python 2.6.6 + Pure IC617 SKILL`)

1. **Điều khiển phiên Virtuoso GUI đang mở (ưu tiên số 1 khi người dùng đang mở schematic):**
   - [tools/ic617_live_bridge.il](../tools/ic617_live_bridge.il) + [tools/ic617_client.py](../tools/ic617_client.py): cầu nối trực tiếp CIW qua Unix domain socket `~/.cache/skill-analog/ic617-<user>.sock` (`0700` thư mục, `0600` session token ngẫu nhiên, **0% phụ thuộc Python 3**, không chiếm thêm license Virtuoso, không đụng khóa `.cdslck`).
   - Nạp một lần trong Virtuoso CIW khi cần dùng:
     ```lisp
     (load "/home/disk/eda/references/SKILL-ANALOG/tools/ic617_live_bridge.il")
     ```
   - Các lệnh có sẵn trong `python -B tools/ic617_client.py`:
     - `ping`: kiểm tra kết nối sống, PID Virtuoso, thư mục làm việc và phiên bản IC617.
     - `active-cv`: đọc cellView đang mở trên cửa sổ đồ họa (`geGetEditCellView()`).
     - `dump-json [--lib L --cell C --view V] [--out FILE]`: xuất JSON toàn bộ cấu trúc schematic (`instances`, `stored_props`, `effective_cdf`, `pin_centers`, `nets`, `pins`, `diagnostics`, `child_cells`).
     - `set-param --inst M1 --param w=12u [--param fingers=4] [--order l,fingers,w,m]`: cập nhật thông số linh kiện và kích hoạt đầy đủ callback CDF ngay trên phiên mở.
     - `check-save [--lib L --cell C --view V]`: chạy `schCheck` + `dbSave` và báo số lỗi/cảnh báo.
     - `export-png --out FILE [--lib L --cell C --view V] [--width 2600 --height 1700]`: xuất ảnh PNG toàn mạch trực tiếp từ phiên GUI.
     - `eval "<skill_expr>"`: thực thi biểu thức SKILL an toàn qua `errset(evalstring(...))` kèm thu luồng `woport` (`stdout`).

2. **Trình bọc thực thi an toàn cho dòng lệnh (`spectre`, `ocean`, `virtuoso-batch`, `si`):**
   - [tools/cadence_exec.py](../tools/cadence_exec.py): tự động nạp `$HOME/cadence/env.sh`, đặt `CDS_Netlisting_Mode=Analog` và `CDS_UseNextLicense=never`, cưỡng bức thư mục kết quả nằm gọn trong `<project>/sim/runs/<run-id>/` (cấm ghi vào thư viện `SKILL-ANALOG`), mặc định truyền `-format psfascii` cho `spectre`, và tự quét khóa `.cdslck` trước mọi tác vụ ghi OA hàng loạt (tự chuyển hướng sang `ic617_client.py` nếu cầu nối CIW đang mở, hoặc báo rõ `user`/`host`/`pid` giữ khóa thay vì treo tiến trình).

3. **Thư viện thủ tục SKILL OA / CDF / Schematic / OCEAN chuẩn hóa:**
   - [tools/ic617_oa_cdf.il](../tools/ic617_oa_cdf.il) (nạp an toàn, không tự sửa cell hay `.cdsinit`; xem CDF cơ sở chỉ đọc bằng [tools/cdf-readonly.il](../tools/cdf-readonly.il)):
     - `saApplyInstCdfCallbacks(inst propPairs [callbackOrder] [derivedProps])` *(bí danh tương thích ngược: `saTriggerInstanceCdfCallbacks`)* và `saSyncInstStringCdf(inst propPairs [callbackOrder] [derivedProps])`: kiểm tra tên tham số đối chiếu `cdfData~>parameters`, ghi chuỗi trực tiếp (`if(stringp(val) val sprintf(nil "%L" val))` — khắc phục triệt để lỗi nhân đôi dấu nháy kép `%L`), khởi tạo `PasCdfFormInit(cdfData)`, thực thi chuỗi callback và gọi `cdfUpdateInstParam(inst)`.
     - `saDumpSchematicJson(cv outJsonPath)` *(kèm `saSerializeSchematicJson(cv)`)*: bộ tuần tự hóa JSON thuần SKILL xuất `lib`, `cell`, `view`, `instances` (tâm chân toàn cục `pin_centers`, `stored_props`, `effective_cdf`), `nets` (`isGlobal`, `connections`), `pins`, `diagnostics` (`floating_nets`, `single_term_nets`, `check_errors`, `check_warnings`) và `child_cells`.
     - `saPlaceAndWireFromPlan(planPath outJsonPath)`: đọc bản kế hoạch dòng lệnh (`LIB`, `CELL`, `GRID`, `SYMBOL`, `INST`, `PARAM`, `PIN`, `STUB`, `NET`, `WIRE`), tự sao lưu view cũ sang `<cell>_bak_<ts>` (tuyệt đối không dùng `ddDeleteObj` xóa hủy diệt), bắt lưới `0.0625`, tính tâm chân chính xác bằng `dbTransformPoint(centerBBox(fig~>bBox) inst~>transform)`, đi dây vuông góc `schCreateWire` + `schCreateWireLabel` + `schCreatePin`, tùy chọn sinh `symbol` (`schSchemToPinList` + `schPinListToSymbolGen`), và đóng gói `schCheck` + `dbSave` trong `unwindProtect`.
     - `saCheckAndSave(cv [outJsonPath])` *(bí danh: `saCheckAndSaveJson`)* và `saCheckAndReportSchematic(cv reportPath)`.
     - `saExportSpectreNetlist(libName cellName viewName runDir modelScs sectionName outPathTxt [probeLib probeCell])`.
     - `saExportStbMargins(psfDir stbResultName outPathTxt)` *(bí danh trả về danh sách kết hợp: `saMeasureStbMargin`)*.
     - `saExportSchematicPng(libName cellName viewName pngPath [width] [height])`.

4. **Bộ đọc trạng thái PSF ASCII & Kiểm toán Điểm làm việc / Chỉ tiêu Spec (Fail-Closed Sign-off `2026.11.18.7`):**
   - [tools/psf_ascii_reader.py](../tools/psf_ascii_reader.py): máy trạng thái đọc đầy đủ Spectre 15.1 PSF ASCII (`HEADER`, `TYPE` gồm cả `STRUCT(...)` nhiều trường lồng nhau, `SWEEP`, `TRACE` gồm ánh xạ `" 401" GROUP N`, và `VALUE` gồm số thực/phức `(re im)`, bản ghi linh kiện `STRUCT` nhiều dòng cho cả **BSIM3v3 (`"bsim3v3"` trên `GPDK090`)** lẫn **BSIM4 (`"bsim4"` trên `GPDK045`)**, cùng giải nén delta-compression và kiểm tra bắt buộc từ khóa kết thúc `END` để chặn file PSF bị cắt cụt). Từ chối chặt `NaN`/`Inf` và ghi nhận rõ mẫu thiếu đầu dải quét (`backfilled_leading_signals`).
   - [tools/psf_audit.py](../tools/psf_audit.py):
     - `op-audit <run_or_psf_path> [--vds-margin 0.05] [--expect-triode M_R1,M_SW]`: trích xuất `ids, vgs, vds, vth, vdsat, gm, gds, gmb, cgg, cgd, cgs, region` của mọi MOSFET (tương thích cả **BSIM3v3 `GPDK090`** và **BSIM4 `GPDK045`**), tính `gm_id`, `gm_gds`, `vov`, `sat_margin = abs(vds) - abs(vdsat)`. Chế độ **Fail-Closed**: thiếu `vdsat` hoặc thiếu `region`/`(vgs, vth)` trả về `MISSING_OP_FIELDS` (`status="NOT_VERIFIED"`, `audit_pass=False`); thiết bị có `0 <= sat_margin < vds_margin` đặt `audit_pass=False`.
     - `metrics <run_dir> [--spec spec.json] [--fail-on-spec]`: quét toàn bộ các tệp `.stb` (`dm.stb`, `cmfb.stb`), `.ac`, `.tran`, `.noise` ở mọi góc PVT yêu cầu; tính công suất DC đa nguồn (`dc_power_w` ghép đúng từng cặp áp–dòng nguồn, tách biệt khỏi `mos_power_estimate_w`), tách rõ nhiễu áp `integrated_rms_noise_v` và nhiễu dòng `integrated_rms_noise_a`, kiểm tra mọi điểm cắt pha `-(180° + 360°k)` cho dự trữ biên `gain_margin_db`, tuyệt đối không lấy pha `.ac` (`pm_ac_deg`) thay cho dự trữ pha vòng kín `.stb`/`.pstb` (`phase_margin_deg`), và chấm `PASS` / `FAIL` / `NOT_VERIFIED` theo [measurement-rules.md](measurement-rules.md).

5. **Phân biệt Vật lý & Cú pháp Mô hình `GPDK090` (BSIM3v3) và `GPDK045` (BSIM4):**
   - **`GPDK090` (`gpdk090_v4.6`) — BSIM3v3 (`bsim3v3`):** lõi `1.2 V` (`gpdk090_nmos1v` / `gpdk090_pmos1v`, SOA đa cực `|VGB| <= 1.32 V`, `|VDB| <= 1.32 V`) và IO `2.5 V` (`|VGB|, |VDB| <= 2.75 V`). Bản thân primitive Spectre BSIM3v3 trong `gpdk090` **không nhận tham số `nf` trực tiếp trên dòng netlist** (`emit_nf: False` trong [tools/gpdk_techsweep.py](../tools/gpdk_techsweep.py); chia ngón thực hiện qua hệ số song song `m` hoặc callback CDF `fingers` trên schematic OA). Nhiễu nhiệt và `1/f` (`sth_w`, `sfl_w`) xuất trong cấu trúc `STRUCT`/`GROUP` của PSF `.noise`.
   - **`GPDK045` (`gpdk045_v_5_0`) — BSIM4 (`bsim4`):** lõi `1.0 V` (`g45n1svt` / `g45p1svt`, SOA đa cực `|VGB| <= 1.1 V`, `|VDB| <= 1.1 V`) và IO `1.8 V` (`|VGB|, |VDB| <= 1.98 V`). Hỗ trợ trực tiếp `nf` (`emit_nf: True`), hiệu ứng ứng suất STI (`sa`, `sb`), WPE và dòng rò xuyên hầm cổng `igidl`/`igs`/`igd`.

6. **Đồng bộ OTA Nguyên tử (`ota_sync.py` & `analogctl.py sync`):**
   - [tools/ota_sync.py](../tools/ota_sync.py) và [tools/analogctl.py](../tools/analogctl.py) (`sync`, `ota-status`): tự động kiểm tra mã băm commit 40 ký tự mới nhất từ GitHub (`TTL = 60s`), tải chênh lệch theo SHA-256 vào thư mục tạm `.staging-*`, kiểm tra cú pháp JSON + `compile()` Python 2.6 rồi tráo nguyên tử. Đặt `SKILL_ANALOG_OFFLINE=1` hoặc `--offline` để khóa cứng 100% truy cập mạng (`--sync --offline` trả mã thoát `2`).

## Giới hạn của các gói Upstream trong `sources/`

Các thư mục trong `sources/` chỉ là bản chụp tham khảo tĩnh; không gọi như thư viện Python đã cài trên RHEL 6.5 (`Python 2.6.6`):
- `unihd-cag/skillbridge` và `Arcadia-1/virtuoso-bridge-lite`: mã nguồn phía client đòi hỏi Python >= 3.8 / 3.10 và thiếu tệp phụ trợ máy chủ; trên RHEL 6.5 luôn dùng [tools/ic617_live_bridge.il](../tools/ic617_live_bridge.il) + [tools/ic617_client.py](../tools/ic617_client.py).
- `KwantaeKim/cdl_gen`: đòi hỏi Python >= 3.9 và thủ tục `cdlgenPlaceSch`/`cdlgenDrawSym` gọi `(ddDeleteObj old)` xóa thẳng cell hiện hữu; luôn dùng `saPlaceAndWireFromPlan` có sao lưu `<cell>_bak_<ts>`.
- `KenKundert/psf_utils`: đòi hỏi Python >= 3.6, `ply`, `inform`, `numpy`; trên RHEL 6.5 luôn dùng [tools/psf_ascii_reader.py](../tools/psf_ascii_reader.py) và [tools/psf_audit.py](../tools/psf_audit.py). Với dữ liệu nhị phân PSF/PSFXL/SST, chạy Spectre kèm `-format psfascii` qua [tools/cadence_exec.py](../tools/cadence_exec.py) hoặc chuyển đổi bằng tiện ích `psf` của MMSIM.
- Xem thêm bản đồ liên kết thay thế tại [SOURCE-LINKS](SOURCE-LINKS.md).

## Ví dụ GPDK090 hai tầng

Nguồn `SrinivasNv0031/two-stage-cmos-opamp-gpdk090` chỉ là case study tùy chọn khi học op-amp hai tầng (kết hợp đọc thẻ `topo-two-stage-opamp`, `tech-miller-pole-splitting`, `tech-miller-rhp-zero-nulling-and-cascode-comp`), không thay OTA một tầng đã chọn. Không kế thừa các con số trong README upstream làm kết quả dự án hiện tại.
