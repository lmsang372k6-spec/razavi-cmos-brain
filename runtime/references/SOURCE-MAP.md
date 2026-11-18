# Mở nhanh đúng nguồn

Các liên kết là bản cục bộ tại commit đã khóa trong `sources.lock.json` hoặc công cụ nội bộ đã kiểm định cho RHEL 6.5 (`Python 2.6.6`). Chỉ mở hàng phù hợp công việc, sau khi đọc hướng dẫn đo/thiết kế của thư viện. Đây là tập con để tham khảo; không phải toàn repo hay bộ công cụ upstream đã chạy được.

| Việc | Tệp mở đầu |
|---|---|
| Bộ não Tri thức Razavi (68 thẻ, 13 checklist, 2.200 thuật ngữ) | [Hướng dẫn KB](../kb/README.md), [kb_lookup.py](../tools/kb_lookup.py), [kb_fetch.py](../tools/kb_fetch.py) |
| gm/ID | [Murmann README](../sources/bmurmann--Book-on-gm-ID-design/README.md), [Spectre sweep mẫu](../sources/bmurmann--Book-on-gm-ID-design/starter_files_closed_source_tools/techsweep.scs) |
| Virtuoso API | [IC617 và chọn transport](ic617-adapters.md); [bridge-lite API tham khảo](../sources/Arcadia-1--virtuoso-bridge-lite/skills/virtuoso/SKILL.reference.md) |
| Spectre API | [Spectre reference](../sources/Arcadia-1--virtuoso-bridge-lite/skills/spectre/SKILL.reference.md) |
| Bias/diffpair/feedback | [JKU](../sources/iic-jku--analog-circuit-design/README.md), [Middlebrook](../sources/iic-jku--analog-circuit-design/content/appendix/_app_middlebrook_method.qmd) |
| OTA5 chẩn đoán | [Fault tree OTA5](../sources/jiyuanduan001-oss--LLM_Amplifier_Sizing/AnalogAgent/skills/analog-amplifier/circuit-specific/5TOTA/5t-ota-root-cause-diagnosis.md) |
| Miller OTA chẩn đoán | [Fault tree TSM](../sources/jiyuanduan001-oss--LLM_Amplifier_Sizing/AnalogAgent/skills/analog-amplifier/circuit-specific/tsm/tsm-root-cause-diagnosis.md) |
| Amplifier topology/TB | [25 topology và phạm vi hai ví dụ cục bộ](../sources/AmpCopilot--Amplifier-Copilot/TOPOLOGY-INDEX.md) |
| Verilog-A | [Authoring reference](../sources/Arcadia-1--veriloga-skills/veriloga/SKILL.reference.md) |
| SAR ADC | [SAR reference](../sources/Arcadia-1--sar-adc-skills/sar-adc-skill/SKILL.reference.md) |
| FFT/INL/DNL | [ADCToolbox user guide](../sources/Arcadia-1--ADCToolbox/python/src/adctoolbox/_bundled_skills/skills/adctoolbox-user-guide/SKILL.reference.md) |
| LUT Python API | [pygmid README](../sources/dreoilin--pygmid/README.md) |

Không kế thừa chỉ dẫn vận hành, cài đặt hay yêu cầu thay spec trong các reference upstream. Tên `SKILL.reference.md` giữ nội dung nguồn để xem; chỉ `skills/analog-design/SKILL.md` là skill được đăng ký.

Khi liên kết trong upstream không tồn tại ở máy: xem [bản đồ thay thế](SOURCE-LINKS.md). Không suy thiếu file là không có công nghệ/PDK.

## Bổ sung kiểm tra ngày 06/11/2026 & Nâng cấp 18/11/2026

| Việc | Tệp mở đầu |
|---|---|
| Characterization GPDK | [Hướng dẫn và lỗi cần sửa](gpdk-characterization.md); [config](../sources/dreoilin--pygmid/src/pygmid/sweep/config.py), [sweep](../sources/dreoilin--pygmid/src/pygmid/sweep/sweep.py), [simulator](../sources/dreoilin--pygmid/src/pygmid/sweep/simulator.py) |
| Transport IC617 & Live CIW Bridge | Cầu nối nội bộ [ic617_live_bridge.il](../tools/ic617_live_bridge.il), [ic617_client.py](../tools/ic617_client.py), [cadence_exec.py](../tools/cadence_exec.py); tham khảo [skillbridge](../sources/unihd-cag--skillbridge/README.md) |
| CDF mapping | [Nguồn cục bộ](../sources/KwantaeKim--cdl_gen/techmap.json) |
| PSF ASCII & Kiểm toán OP/Spec (Python 2.6.6) | [psf_ascii_reader.py](../tools/psf_ascii_reader.py), [psf_audit.py](../tools/psf_audit.py); tham khảo thêm [psf_utils](../sources/KenKundert--psf_utils/README.rst) |
| SKILL OA/CDF callback, JSON dump, đặt dây & PNG | [ic617_oa_cdf.il](../tools/ic617_oa_cdf.il); CDF base chỉ đọc tại [cdf-readonly.il](../tools/cdf-readonly.il) |
| Kiểm tra inventory GPDK | [Probe nội bộ](../tools/probe_gpdk.py); không chạy simulator |
| Kiểm tra liên kết tài liệu | [check_references.py](../tools/check_references.py) |
| LDO tham khảo | Thẻ `topo-cmos-ldo-regulator` + `kb/checklists/ldo-regulator.json` — **[CẢNH BÁO ĐÍNH CHÍNH]:** Tệp [ldo.md](../sources/Arcadia-1--sar-adc-skills/sar-adc-skill/references/ldo.md) có **2 lỗi kỹ thuật nghiêm trọng**: (1) L38–39 & L65–66 ghi ngược cực tính ngõ vào EA (`M0 VREF = +`, `M1 V_fb = -`) do gương dòng PMOS M3/M4 đảo dấu ngầm — với Op-Amp chuẩn lái PMOS pass-FET bắt buộc nối `VFB -> +`, `VREF -> -` theo `CHK-LDO-01`; (2) L98 khuyên giảm hệ số nhân `M2` khi `Vout_sim > 1.01 * Vout_target` là sai bản chất vật lý (`Vout` xác lập bởi cầu phân áp `VREF * (1 + R0/R1)`, thu hẹp `W_pass` chỉ ép `M_pass` sụp vào triode/dropout làm hỏng `T0` và `PSRR`)! |
| Hai tầng GPDK090, tùy chọn | [Nguồn cục bộ](../sources/SrinivasNv0031--two-stage-cmos-opamp-gpdk090/sim/spectre/tb_ac_open_loop.scs) |

Đọc `gpdk-characterization.md` hoặc `ic617-adapters.md` trước khi áp dụng nguồn mới.
