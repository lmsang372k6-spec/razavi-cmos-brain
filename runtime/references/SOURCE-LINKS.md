# Liên kết thay thế trong bản nguồn chọn lọc

Đọc khi liên kết bên trong `sources/` không tồn tại. Source gốc giữ nguyên commit/hash; bảng này sửa đường tra cứu mà không giả định bản trích chọn là toàn bộ repo. Đường dẫn được xác minh ngày 06/11/2026; dữ liệu máy đọc ở [source-link-map.json](source-link-map.json).

- **Cục bộ:** mở file thay thế đã tồn tại; trường hợp bootstrap là tài liệu cùng chủ đề với tên file khác.
- **Chỉ trên GitHub:** đích tồn tại trong Git tree ở commit đã khóa; chưa tải về, không dùng được khi ngoại tuyến. Sự tồn tại không chứng minh nội dung hoặc kết quả mô phỏng đúng.
- **Không có tại đường đã khóa / chưa xác minh:** không dựng URL hay file giả. Tiếp tục bằng tài liệu theo nhiệm vụ trong [INDEX](INDEX.md), hoặc báo thiếu đúng phần đang cần.
- `AGENTS.md` của upstream vẫn chỉ là dữ liệu tham khảo; không mở để kế thừa hướng dẫn vận hành.

| Nguồn / file chứa liên kết | Đích cũ | Đường tra cứu hiện tại |
|---|---|---|
| `sources/Arcadia-1--virtuoso-bridge-lite/README.md` | `AGENTS.md` | [Chỉ trên GitHub](https://github.com/Arcadia-1/virtuoso-bridge-lite/blob/1f186abfbb3d658211743cd707f3156ed2f59a87/AGENTS.md) |
| `sources/Arcadia-1--virtuoso-bridge-lite/skills/virtuoso/references/connection.md` | `../../../docs/adr/0004-instance-discovery.md` | [Chỉ trên GitHub](https://github.com/Arcadia-1/virtuoso-bridge-lite/blob/1f186abfbb3d658211743cd707f3156ed2f59a87/docs/adr/0004-instance-discovery.md) |
| `sources/iic-jku--analog-circuit-design/README.md` | `x.png` | Không có tại đường dẫn ở commit đã khóa |
| `sources/jiyuanduan001-oss--LLM_Amplifier_Sizing/README.md` | `../CircuitCollector/README.md` | Không có tại đường dẫn ở commit đã khóa |
| `sources/jiyuanduan001-oss--LLM_Amplifier_Sizing/README.md` | `comparison_report_tsm_single.md` | [Chỉ trên GitHub](https://github.com/jiyuanduan001-oss/LLM_Amplifier_Sizing/blob/2cbff780e74e84e93475879761311a7f94631e04/comparison_report_tsm_single.md) |
| `sources/AmpCopilot--Amplifier-Copilot/readme.md` | `./README.zh-CN.md` | Chưa xác minh; không có trong bản cục bộ |
| `sources/AmpCopilot--Amplifier-Copilot/readme.md` | `LICENSE` | Chưa xác minh; không có trong bản cục bộ |
| `sources/AmpCopilot--Amplifier-Copilot/readme.md` | `Pic_for_readme/Copilot_Video_UG.mp4` | Chưa xác minh; không có trong bản cục bộ |
| `sources/Arcadia-1--sar-adc-skills/sar-adc-skill/references/sar-adc-11b-zzs.md` | `references/bootstrap.md` | [Cục bộ](../sources/Arcadia-1--sar-adc-skills/sar-adc-skill/references/bootstrap_switch.md) |
| `sources/Arcadia-1--sar-adc-skills/sar-adc-skill/references/sar-adc-11b-zzs.md` | `references/cdac.md` | [Cục bộ](../sources/Arcadia-1--sar-adc-skills/sar-adc-skill/references/cdac.md) |
| `sources/Arcadia-1--sar-adc-skills/sar-adc-skill/references/sar-adc-11b-zzs.md` | `references/comparator.md` | [Cục bộ](../sources/Arcadia-1--sar-adc-skills/sar-adc-skill/references/comparator.md) |
| `sources/Arcadia-1--sar-adc-skills/sar-adc-skill/references/sar-adc-11b-zzs.md` | `references/integration.md` | [Cục bộ](../sources/Arcadia-1--sar-adc-skills/sar-adc-skill/references/integration.md) |
| `sources/Arcadia-1--sar-adc-skills/sar-adc-skill/references/sar-adc-11b-zzs.md` | `references/sar-logic.md` | [Cục bộ](../sources/Arcadia-1--sar-adc-skills/sar-adc-skill/references/sar-logic.md) |
| `sources/Arcadia-1--ADCToolbox/README.md` | `docs/experiments/dither-results.md` | [Chỉ trên GitHub](https://github.com/Arcadia-1/ADCToolbox/blob/372b714011db9c3f366bd0223d066e1fbde8dfb6/docs/experiments/dither-results.md) |
| `sources/Arcadia-1--ADCToolbox/README.md` | `docs/experiments/hdc-physical-state-and-phases.md` | [Chỉ trên GitHub](https://github.com/Arcadia-1/ADCToolbox/blob/372b714011db9c3f366bd0223d066e1fbde8dfb6/docs/experiments/hdc-physical-state-and-phases.md) |
| `sources/Arcadia-1--ADCToolbox/README.md` | `python/src/adctoolbox/examples/11_calibration/DITHER_GUIDE.md` | [Chỉ trên GitHub](https://github.com/Arcadia-1/ADCToolbox/blob/372b714011db9c3f366bd0223d066e1fbde8dfb6/python/src/adctoolbox/examples/11_calibration/DITHER_GUIDE.md) |
| `sources/SrinivasNv0031--two-stage-cmos-opamp-gpdk090/README.md` | `docs/figures/closed_loop_sine_tracking.png` | [Chỉ trên GitHub](https://github.com/SrinivasNv0031/two-stage-cmos-opamp-gpdk090/blob/c5d568a2d08b07d92eba0b3279e70c140b9f477d/docs/figures/closed_loop_sine_tracking.png) |
| `sources/SrinivasNv0031--two-stage-cmos-opamp-gpdk090/README.md` | `docs/figures/cmrr_response.png` | [Chỉ trên GitHub](https://github.com/SrinivasNv0031/two-stage-cmos-opamp-gpdk090/blob/c5d568a2d08b07d92eba0b3279e70c140b9f477d/docs/figures/cmrr_response.png) |
| `sources/SrinivasNv0031--two-stage-cmos-opamp-gpdk090/README.md` | `docs/figures/compensation_phase_margin.png` | [Chỉ trên GitHub](https://github.com/SrinivasNv0031/two-stage-cmos-opamp-gpdk090/blob/c5d568a2d08b07d92eba0b3279e70c140b9f477d/docs/figures/compensation_phase_margin.png) |
| `sources/SrinivasNv0031--two-stage-cmos-opamp-gpdk090/README.md` | `docs/figures/compensation_ugb.png` | [Chỉ trên GitHub](https://github.com/SrinivasNv0031/two-stage-cmos-opamp-gpdk090/blob/c5d568a2d08b07d92eba0b3279e70c140b9f477d/docs/figures/compensation_ugb.png) |
| `sources/SrinivasNv0031--two-stage-cmos-opamp-gpdk090/README.md` | `docs/figures/final_compensated_schematic.png` | [Chỉ trên GitHub](https://github.com/SrinivasNv0031/two-stage-cmos-opamp-gpdk090/blob/c5d568a2d08b07d92eba0b3279e70c140b9f477d/docs/figures/final_compensated_schematic.png) |
| `sources/SrinivasNv0031--two-stage-cmos-opamp-gpdk090/README.md` | `docs/figures/load_capacitance_stability.png` | [Chỉ trên GitHub](https://github.com/SrinivasNv0031/two-stage-cmos-opamp-gpdk090/blob/c5d568a2d08b07d92eba0b3279e70c140b9f477d/docs/figures/load_capacitance_stability.png) |
| `sources/SrinivasNv0031--two-stage-cmos-opamp-gpdk090/README.md` | `docs/figures/nulling_resistor_phase_margin.png` | [Chỉ trên GitHub](https://github.com/SrinivasNv0031/two-stage-cmos-opamp-gpdk090/blob/c5d568a2d08b07d92eba0b3279e70c140b9f477d/docs/figures/nulling_resistor_phase_margin.png) |
| `sources/SrinivasNv0031--two-stage-cmos-opamp-gpdk090/README.md` | `docs/figures/output_swing.png` | [Chỉ trên GitHub](https://github.com/SrinivasNv0031/two-stage-cmos-opamp-gpdk090/blob/c5d568a2d08b07d92eba0b3279e70c140b9f477d/docs/figures/output_swing.png) |
| `sources/SrinivasNv0031--two-stage-cmos-opamp-gpdk090/README.md` | `docs/figures/psrr_response.png` | [Chỉ trên GitHub](https://github.com/SrinivasNv0031/two-stage-cmos-opamp-gpdk090/blob/c5d568a2d08b07d92eba0b3279e70c140b9f477d/docs/figures/psrr_response.png) |
| `sources/SrinivasNv0031--two-stage-cmos-opamp-gpdk090/README.md` | `docs/figures/unity_feedback_large_signal_step.png` | [Chỉ trên GitHub](https://github.com/SrinivasNv0031/two-stage-cmos-opamp-gpdk090/blob/c5d568a2d08b07d92eba0b3279e70c140b9f477d/docs/figures/unity_feedback_large_signal_step.png) |
| `sources/SrinivasNv0031--two-stage-cmos-opamp-gpdk090/README.md` | `docs/two_stage_cmos_opamp_design_report.pdf` | [Chỉ trên GitHub](https://github.com/SrinivasNv0031/two-stage-cmos-opamp-gpdk090/blob/c5d568a2d08b07d92eba0b3279e70c140b9f477d/docs/two_stage_cmos_opamp_design_report.pdf) |
| `sources/SrinivasNv0031--two-stage-cmos-opamp-gpdk090/README.md` | `results/` | [Chỉ trên GitHub](https://github.com/SrinivasNv0031/two-stage-cmos-opamp-gpdk090/tree/c5d568a2d08b07d92eba0b3279e70c140b9f477d/results) |
