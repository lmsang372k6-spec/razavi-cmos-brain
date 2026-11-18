# Sampling và comparator

Nguồn chính: `Arcadia-1/sar-adc-skills`, chỉ reference của sampler/switch/comparator cần dùng. Trước thiết kế chốt signal range/common mode, source impedance, sampling frequency/phase, acquisition time, load/CDAC, allowed error và supply.

Sampler: kiểm tra acquisition/settling theo source và switch resistance thực; kickback, charge injection/feedthrough, leakage/hold droop và clock overlap ở các điều kiện spec yêu cầu. Bootstrap cần kiểm tra điện áp các terminal và giới hạn model/PDK trong mọi phase, startup và input excursion. Không coi mạch chạy transient là đã chứng minh reliability.

Comparator: phân biệt static/dynamic, reset/evaluate phase, output load và detection threshold. Đo delay từ sự kiện clock/input đã định nghĩa tới quyết định hợp lệ; cho biết input overdrive/common mode và metastability criterion. Zero differential input không phải điểm delay điển hình. Kiểm tra kickback tới source/CDAC, reset completeness và khả năng quyết định ở thời gian cho phép.

Offset/mismatch cần quy trình Monte Carlo hoặc sweep xác định và model hỗ trợ; noise/jitter cần phép đo được simulator hỗ trợ, đủ samples và điều kiện thống kê. Chưa chạy thì `NOT VERIFIED`. Không suy offset/noise thống kê từ một transient deterministic hoặc một lần đổi seed.
