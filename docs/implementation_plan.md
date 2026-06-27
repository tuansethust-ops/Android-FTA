# Batch Differential Analysis (So sánh thư mục DUT và REF) - Đã cập nhật

Mục tiêu: Mở rộng khả năng của hệ thống để phân tích và so sánh hàng loạt file trace giữa hai thiết bị/phiên bản phần mềm (DUT và REF). Khắc phục sự sai lệch giữa ý định của kịch bản test (First Entry / Re-entry) và trạng thái thực tế của hệ điều hành (COLD / WARM).

## User Review Required

> [!IMPORTANT]
> Cảm ơn bạn đã chỉ ra một "điểm mù" cực kỳ quan trọng trong thực tế test tự động (Automated Testing): Trạng thái của hệ thống sau khi Reboot 5 phút có thể làm hỏng ý định của tester (muốn test COLD nhưng hệ thống lại vô tình start app ngầm thành WARM).
> 
> **Kế hoạch gom nhóm (Grouping Logic) mới:**
> - Chúng ta sẽ **không** dùng `startup_type` của Perfetto để gom nhóm nữa.
> - Thay vào đó, hệ thống sẽ Parse **Tên File Log**.
> - **Cách phân biệt First-entry vs Re-entry:** Với mỗi App trong một Cycle, trace có thời gian (timestamp trong tên file) sớm hơn sẽ được coi là **First Entry**, trace muộn hơn (gần ngay sau đó) sẽ được coi là **Re-entry**.
> - **Validation Gate:** Hệ thống sẽ so sánh (DUT First-entry vs REF First-entry) và (DUT Re-entry vs REF Re-entry).
> 
> **Trạng thái hiện tại:** ⏸️ **TẠM DỪNG (PAUSED)**
> Tính năng này đang được đánh dấu (bookmark) lại để chờ bạn cung cấp định dạng tên file thực tế từ máy tính test. Khi bạn quay lại với một Agent khác (như Cline), chỉ cần cung cấp định dạng file, Agent sẽ tiếp tục ngay từ bước này.

### 1. `core/batch_engine.py` [NEW]
- Hàm `parse_filename(filepath)`: Sử dụng Regex để tách Tên App và Thời gian (Timestamp) từ tên file.
- Hàm `group_traces_by_cycle()`: Gom các file của cùng 1 App thành các cặp (Pair) dựa trên khoảng cách thời gian. File tạo ra trước là First-entry, tạo ra sau là Re-entry.
- Khởi tạo `SkillEngine` để phân tích từng file và thu thập `metrics` cho First-entry và Re-entry.
- Hàm `calculate_median()` để tính trung vị cho 3 cycles.
- Hàm `compare_and_evaluate()` tính toán Delta (DUT_Median - REF_Median) và đẩy qua `FTAEngine`.

### 2. Sửa `core/fta_engine.py` [MODIFY]
- Thay đổi logic kiểm tra ngưỡng (Threshold) thành chế độ tính Delta (So sánh chênh lệch giữa DUT và REF).

### 3. Sửa `main.py` [MODIFY]
- Thêm lệnh `compare --dut <dir> --ref <dir>`.
- Hiển thị báo cáo so sánh cho từng App, chia làm 2 mục: **First-entry Comparison** và **Re-entry Comparison**.

## Verification Plan
1. Tạo một thư mục giả lập với các tên file như `camera_20260627_100000.pftrace` (First) và `camera_20260627_100030.pftrace` (Re-entry).
2. Chạy lệnh `compare` và đảm bảo hệ thống gom đúng cặp First-entry/Re-entry dựa trên thời gian, bất chấp việc bên trong Perfetto báo cáo nó là COLD hay WARM.
