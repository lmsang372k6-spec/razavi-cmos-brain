# SAR ADC

Nguồn chính: `Arcadia-1/sar-adc-skills`. Chọn architecture/switching scheme theo spec trước sizing CDAC/comparator. Chốt resolution, range/common mode, Fs, input bandwidth, ENOB/SNDR, static linearity, power, reference/source drive và operating conditions.

Lập timing diagram: sample, hold, từng bit trial, comparator evaluate/reset, DAC/reference settling, EOC và output valid. Định nghĩa code encoding, bit significance, polarity và differential/full-scale convention. Kiểm tra endpoint/near-midscale, monotonic inputs, comparator decision polarity và bit sequencing trước FFT dài.

CDAC: ghi topology/switching, capacitance unit, parasitic assumptions, mismatch model và reference network. Phân biệt thermal noise, mismatch, settling và kickback; không dùng một con số C từ ví dụ khác PDK như sizing đã kiểm chứng. Reference và source impedance cần được mô hình hóa ở mức spec yêu cầu.

Đầu tiên kiểm tra behavioral blocks, rồi transistor block interfaces, cuối cùng full chain và PVT/mismatch/PEX theo phạm vi yêu cầu. Giữ reference behavioral results tách kết quả transistor. Thu samples đúng output-valid/EOC; phép đo động/tĩnh theo [models-and-adc.md](../models-and-adc.md).
