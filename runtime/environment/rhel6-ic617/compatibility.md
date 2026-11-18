# Môi trường và mức tương thích

`tools.json`/`pdk.json` ghi kết quả đọc filesystem khi VM tắt, không chứng nhận chạy được công cụ, license hay bridge. Chỉ cập nhật `runtime_verified` sau kiểm tra thật có phiên bản, thời gian và bằng chứng. Không suy gói đang cài từ README upstream.

- IC617 và MMSIM151/Spectre15.1 là mục tiêu hiện tại; examples bridge-lite dùng công cụ mới hơn. Bridge-lite cần Python >=3.9; ADCToolbox cần Python >=3.10. Chưa xác nhận các runtime này trong RHEL6. Không nâng Python hệ thống, glibc hoặc OS để làm một tài liệu tham khảo chạy được.
- Thư viện tài liệu/skill hoạt động bằng file; không cần bridge hay daemon để Codex tra cứu. Bridge chỉ được kích hoạt sau kiểm tra transport/API và thao tác đọc nhỏ trên phiên Cadence. Python hiện đại có thể chạy trên host khi quy trình truyền file/điều khiển được xác minh.
- Nếu bridge-lite không phù hợp IC617, đánh giá một adapter tương thích cho cùng vai trò. `skillbridge` nay là ứng viên transport được ưu tiên đánh giá cho IC617 theo tuyên bố upstream; chưa cài/chạy và không được bật song song mặc định. Native SKILL/OCEAN/script runner đúng bản cũng là phương án khi có đủ tài liệu và test.
- Không dùng `aps`, `++aps`, solver flags, PSF reader hay STB APIs chỉ vì source mới có ví dụ; kiểm tra `-help`/manual đúng bản và thử nhỏ trước.
- PDK045/090 ở đường dẫn thực trong `pdk.json`; model names, legal ranges, fingers/multiplicity, CDF callback và corner sections phải lấy từ bản cài. Không chọn PDK mặc định khi chưa xác định DUT.
- `/home/disk/eda` nằm trong VMDK trên F của Windows. Shared folders đang tắt ở lần kiểm kê; `F:\SKILL-ANALOG` không tự trở thành đường dẫn Linux. Dữ liệu dự án tiếp tục nằm ngoài thư viện, trong project root thực đã phân giải.
- Lần kiểm kê thấy `/home/disk` ext2 có cờ lỗi `s_state=2`, F còn khoảng 21.81 GiB; đây là dữ liệu thời điểm kiểm kê, cần kiểm tra lại. Không tự sửa filesystem, compact VMDK hay di chuyển dự án như tác dụng phụ của thiết kế analog.

Khi một bước thiếu tool/license/API/model, báo chính xác phần bị chặn và tiếp tục việc độc lập như tính tay, xem topology hoặc định nghĩa TB. Kết quả chưa chạy được vẫn `NOT VERIFIED`.

## Nguồn kiểm tra thêm 06/11/2026

Python 2.6.6 là lần ghi nhận guest trước đây, không phải Python 2.7. skillbridge khai >=3.8; cdl_gen >=3.9; psf_utils >=3.6 (dependencies cần kiểm tra riêng). pygmid có code mới hơn minimum metadata >=3.4. Không nguồn nào đã qua thử runtime trong guest ở lần cập nhật này. Xem `references/ic617-adapters.md` và `references/gpdk-characterization.md`; probe chỉ đọc metadata, không chứng nhận license hay simulation. Các corner trong báo cáo CLI của người dùng chưa được nhập vào `pdk.json` như sự thật đã xác minh.
