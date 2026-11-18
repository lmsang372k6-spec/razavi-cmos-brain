# Characterization GPDK045 / GPDK090

Dùng khi cần tạo hoặc kiểm tra LUT gm/ID. Đây là quy trình cần thích nghi với model/CDF đang cài; chưa phải bộ sweep đã chạy thành công trên RHEL6.

## Chọn nguồn và phạm vi

- Phương pháp: Murmann. Lookup và cấu trúc sweep: `dreoilin--pygmid`; đọc riêng `src/pygmid/sweep/config.py`, `sweep.py` và cấu hình GPDK090 mẫu khi cần.
- Không chạy upstream ngay trong thư mục thiết kế hoặc thư viện chung. `pygmid` tạo tên cố định `pysweep.scs`, `params.scs`, thư mục `sweep/` và có cleanup. Dùng thư mục chạy mới dưới `PROJECT/sim/runs/char-RUN_ID/`; giữ log/raw trước cleanup hoặc dùng runner đã sửa và kiểm thử.
- `ashwith/pyMOSChar` không được chọn làm runner: README chỉ hỗ trợ Python 2.7, khác Python 2.6.6 từng ghi nhận trên máy này. `charMOS.py` có cleanup bằng `os.system('rm -fr ...')`, runner không kiểm tra exit status rõ ràng, Spectre netlist cố định `temp=27` dù metadata có `temp`. Chỉ tham khảo ý tưởng sweep, không dùng metadata đó để chứng nhận nhiệt độ thực.

## Hợp đồng dữ liệu trước khi sweep

Lưu cấu hình và chứng cứ trong dự án: model path/hash/version, section đúng chữ hoa/thường, loại NMOS/PMOS và voltage flavor, simulator/version, nhiệt độ C, tnom C, W/L theo mét, ý nghĩa W mỗi finger/tổng, nf/m/simM, VGS/VDS/VSB và quy ước dấu. Ghi grid và đơn vị riêng cho từng trục, model/terminal pin order, tham số hình học và nguồn CDF/netlist.

Probe chỉ đọc ngày 06/11/2026 trên guest đã xác minh section top-level: GPDK045 `tt/ff/ss/fs/sf/mc`; GPDK090 `NN/SS/SF/FS/FF` cùng các biến thể `_highPerf`. Đây là bằng chứng filesystem, chưa phải kết quả mô phỏng; include hierarchy, CDF và model validity vẫn cần kiểm tra. Không dùng cùng một bảng corner chung. `mc` nếu tồn tại cũng chưa chứng minh mismatch đã bật: cần model statistics, variation mode, seed và netlist Monte Carlo đúng bản.

`python tools/probe_gpdk.py` chỉ đọc inventory giới hạn, hash model top-level, section header và tìm executable trong PATH; không khởi chạy simulator hay đọc toàn model ra màn hình. Lưu JSON bên ngoài thư viện, ví dụ `PROJECT/docs/gpdk-probe.json`. Nếu file không ở vị trí dự kiến, xác định đường thật từ setup PDK; không coi file không tìm thấy là không có PDK. Include hierarchy, CDF, giới hạn điện áp và license cần kiểm tra tiếp.

## Các điểm sửa bắt buộc trong adapter pygmid

Ở commit đã khóa, `config.py` đổi `TEMP - 273.15` khi sinh Spectre. Vì vậy cấu hình `temp=300` là 300 K, tương ứng 26,85°C; muốn đúng 27°C đặt 300,15 K. Đọc netlist sinh ra để kiểm tra lại, không suy đơn vị từ tên biến.

Cấu hình mẫu GPDK090 dùng `gpdk090_nmos1v` / `gpdk090_pmos1v` nhưng sweep VGS/VDS tới 1,8 V. Không kế thừa mức này trước khi xác minh voltage rating và model validity của đúng device. Không dùng giới hạn từ tên thư viện 90 nm hay từ mạch mẫu 1,2 V. Xác định cả VGB/VGD/VDB, body diode và miền reverse bias khi sweep VSB.

`config.py` lưu grid theo các tuple, nhưng phần sinh DC VGS/VDS dùng `start=0`, max và bước giữa hai điểm đầu. Grid bắt đầu khác 0, nhiều đoạn, không đều hoặc chỉ một điểm cần adapter riêng; đừng coi metadata grid là bằng chứng simulator chạy đúng grid. WIDTH/NFING bị ép int ở parser; Wtot tính theo micromet và supplement mẫu có biểu thức hình học với một finger. Không thay nf tùy ý rồi coi kích thước tương đương. Metadata `corner=NOM` khác include `section=NN`; ghi section thực vào provenance.

Sweep/lookup thuộc Python 3, không chạy bằng Python 2.6.6. `setup.cfg` ghi >=3.4 nhưng code hiện có dataclasses, f-string và annotation mới hơn; minimum trong metadata không phải kết quả thử runtime. Chọn interpreter/venv riêng đã kiểm tra cả dependencies; không thay Python hệ thống RHEL6.

## Lỗi upstream phải xử lý trước khi dùng runner

Ở commit pygmid đã khóa, [config.py](../sources/dreoilin--pygmid/src/pygmid/sweep/config.py), [sweep.py](../sources/dreoilin--pygmid/src/pygmid/sweep/sweep.py) và [simulator.py](../sources/dreoilin--pygmid/src/pygmid/sweep/simulator.py) chưa tạo thành adapter đã kiểm thử:

- Config dùng khóa `mn:ids`/`mn:gm`, reader tách theo dấu chấm và tạo khóa `mn.`; nơi nhận kết quả lại truy cập khóa gốc dấu hai chấm. Thống nhất mapping tên tín hiệu với PSF thực, kiểm tra cả NMOS/PMOS và noise.
- Simulator bắt `CalledProcessError` rồi trả `None`; sweep vẫn chuyển sang reader. Reader khởi tạo zero và không kiểm tra đủ file VDS. Dừng run khi simulator lỗi; kiểm tra log, analysis, đủ grid và finite values trước khi lưu LUT. Không dùng zero để biểu diễn dữ liệu thiếu.
- Vòng cộng noise hiện thêm từng tín hiệu vào cả `STH` và `SFL`; cần mapping riêng, unit/định nghĩa rõ và đối chiếu Spectre.

Các lỗi trên được rà bằng đọc code và kiểm tra biểu thức chuỗi, chưa phải kết quả chạy adapter. Không sửa nguồn đã khóa để che provenance; nếu cần triển khai adapter, đặt bản sửa trong dự án, ghi commit nền và patch, rồi kiểm thử trước khi tạo dữ liệu thiết kế.

## Xác minh theo mức độ

1. Xuất netlist NMOS và PMOS từ schematic thử đúng CDF/PDK để biết pin order, geometry, W/nf/m và tên OP thực. Không sửa model gốc.
2. Chạy vài điểm DC nhỏ trong miền hợp lệ trước. Xác minh chiều dòng PMOS, gm/gds/caps, nhiệt độ, section và convergence qua log/netlist/raw. Không lấy trị tuyệt đối mọi đại lượng rồi che lỗi dấu.
3. Chạy pilot grid nhỏ, kiểm tra số chiều/số điểm, NaN/Inf, đơn vị và nội suy. Đối chiếu một số điểm trực tiếp và điểm giữa grid với Spectre theo tolerance đã định nghĩa trong dự án. Không đặt tolerance ngầm để chấm pass.
4. Chỉ mở rộng sweep sau pilot đạt. Tách dữ liệu theo PDK/device/flavor/corner/temp/geometry; không gộp các LUT rồi để lookup chọn nhầm.
5. Trong mạch thật, kiểm tra lại OP và bias; LUT không thay thế AC/transient/noise/PVT. Khi chưa có log/raw và phép đối chiếu, trạng thái `NOT VERIFIED`.

Dữ liệu LUT của người dùng nằm dưới dự án hoặc kho dữ liệu được chọn rõ ràng; `SKILL-ANALOG` chỉ giữ hướng dẫn và nguồn tham khảo. Không đưa model PDK, dữ liệu mạch riêng hoặc file pickle không rõ nguồn vào bộ source chung.
