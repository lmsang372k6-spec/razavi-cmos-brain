# Layout và kiểm chứng vật lý

Nguồn quyết định: rule decks, device/PCell definitions, extraction models và manual của PDK/tool thực. Tài liệu bridge chỉ hỗ trợ thao tác; không tự cung cấp signoff rules. GPDK là môi trường thiết kế tham khảo, không được gọi là foundry tapeout signoff khi chưa có bộ rule/model/flow được foundry chấp nhận.

Trước layout xác định hierarchy, matching/symmetry constraints, orientation/well/body contacts, guard rings, routing sensitivity, density và các giới hạn device phù hợp PDK. Xác minh PCell parameters, net names và units qua dữ liệu thật. Không thay toàn bộ quy tắc bằng pattern common-centroid được sao từ một topology khác.

DRC: lưu tool/deck/version, run configuration, violations và waivers được phê duyệt. LVS: chỉ rõ schematic/source và extracted layout, hierarchy/blackboxes, device recognition, globals và parameter tolerances. Điều tra mismatches; không sửa source CDL để ép LVS thành CORRECT hoặc bỏ thiết bị để che sai khác. Một báo cáo sạch với exclusions/blackboxes phải nêu coverage đó.

PEX: ghi deck/options/corner, extracted view/netlist và mapping pins/parasitics. Giữ parasitics và thiết bị mà flow cần; so baseline schematic với extracted bằng cùng TB/spec và ngẫu nhiên/corner thích hợp. DRC/LVS sạch không chứng minh performance post-layout. PVT/mismatch/PEX chưa chạy là `NOT VERIFIED`, kể cả nominal schematic đã pass.
