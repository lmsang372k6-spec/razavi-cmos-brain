# Verilog-A và đo ADC

## Verilog-A

Nguồn ngôn ngữ: `Arcadia-1/veriloga-skills`, chỉ phần authoring/module/contributions/events/operators cần dùng. Compile bằng Spectre thật trước khi coi là tương thích; không thay solver bằng EVAS/OpenVAF trong dự án này.

Model cần ghi pin discipline/direction, units, parameters/ranges, supply/common-mode behavior, reset/startup, latency, clock edge và valid output. Dùng analog operators/events đúng ngữ cảnh và tính liên tục phù hợp; tránh discontinuities hay thời điểm sampling phụ thuộc timestep ngoài ý muốn. Test DC/edge cases/transient và convergence trước kết nối full system. Model lý tưởng phải được gắn nhãn các nonidealities chưa có; behavioral pass không chứng minh transistor pass.

## ADC

Nguồn phân tích: `Arcadia-1/ADCToolbox`, user guide/API đúng bản. Python package yêu cầu runtime hiện đại; không cài chồng vào system Python RHEL6. Có thể xử lý dữ liệu đã xuất trên host khi toolchain đó được xác nhận.

Ghi raw sample artifact, code encoding/polarity, EOC/sample selection, Fs, Fin, số mẫu, transient bị loại, full-scale convention, window/coherence, FFT normalization, signal/noise/distortion bin masks và aliases. Không dùng window mặc định mà không ghi và không coi bin leak thành noise vật lý. Báo SNDR/SNR/SFDR/THD theo convention rõ; ENOB cần ghi công thức và điều kiện amplitude/full scale.

INL/DNL cần nêu endpoint/best-fit hoặc method khác, input ramp/histogram stimulus và code range. Kiểm tra missing codes, saturation và sample coverage. Một FFT tốt không chứng minh static linearity; một ramp không chứng minh dynamic SNDR.

Giữ raw và calibrated results riêng, ghi calibration training/evaluation split và corrections. Không dùng dữ liệu đáp án benchmark làm design reference trong một bài đánh giá AI. Nếu thiếu Fs/Fin/code ordering/sample timing hoặc raw artifact, báo `NOT VERIFIED` cho metric bị ảnh hưởng thay vì đưa một con số có vẻ hợp lý.
