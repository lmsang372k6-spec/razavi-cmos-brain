# OTA và amplifier

Nguồn sizing: Murmann; lý thuyết: JKU; fault tree theo OTA5/Miller: LLM_Amplifier_Sizing; topology/TB tham khảo: Amplifier-Copilot. Chọn một topology cụ thể, không nạp cả database. Công nghệ của ví dụ không cung cấp W/L/bias hợp lệ cho GPDK.

Trước sizing nêu input/output common mode, supply, load, feedback factor, gain/bandwidth, settling/slew/noise và power. Tách differential path và common-mode control nếu fully differential. Kiểm tra headroom trên toàn input/output range và chức năng khởi động/bias, không chỉ một OP nominal.

Với OTA5, xác định các nút điện trở cao, current path, input-pair loading và giới hạn swing. Với Miller hai tầng, xác định compensation path, pole/zero và load trước đề xuất đổi Cc, nulling resistor hoặc dòng; không áp một hướng chỉnh cho mọi bias/topology. Chẩn đoán theo cơ chế: OP sai → gain/headroom → các pole/zero/loop → large signal → noise/power; dùng data để chọn bước tiếp theo.

Phân biệt open-loop AC, closed-loop frequency response và loop stability. Một gain-bandwidth estimate từ gm/C không thay kết quả đo loop. Kiểm tra closed-loop transient bên cạnh STB theo [measurement-rules.md](../measurement-rules.md). Nguồn fault-tree chỉ tạo giả thuyết; mọi sửa phải được kiểm tra bằng netlist/model thực và cùng điều kiện baseline.
