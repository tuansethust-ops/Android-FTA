# Walkthrough: Raw Critical Path Analysis cho App Launch

Hệ thống vừa được trang bị thêm một khả năng cực kỳ chuyên sâu: **Trích xuất Raw Critical Path (Đường găng thô)** để tìm ra các "Thủ phạm bên ngoài" cản trở luồng chính của ứng dụng.

## 1. Vấn đề của Breakdown cũ
Mặc dù `opinionated_breakdown` cho chúng ta biết ứng dụng mất bao lâu ở các bước như `bindApplication` hay bị khóa bởi `binder`, nhưng nó không chỉ đích danh **Tiến trình nào** của hệ điều hành đang gây ra độ trễ đó.

## 2. Giải pháp: Raw Critical Path SQL
Chúng ta đã nhúng trực tiếp một câu lệnh SQL phức tạp gọi vào hàm `_thread_executing_span_critical_path` của Perfetto Stdlib. 
Câu lệnh này duyệt qua toàn bộ chuỗi đánh thức (waker chain) của Main Thread, loại trừ các luồng nội bộ của chính ứng dụng, và tính tổng thời gian mà các tiến trình bên ngoài làm nghẽn Main Thread.

## 3. Kết quả trên Trace thực tế
Khi phân tích file `lacunh_heavy.pftrace`, báo cáo sinh ra có thêm một mục cực kỳ giá trị:

```markdown
### 3. Top 3 External Critical Path Blockers
These are external system processes that blocked the Main Thread during startup:
- **system_server** (`binder:3826_17`): 3.5 ms
- **kworker/7:4** (`kworker/7:4`): 1.7 ms
- **system_server** (`binder:3826_16`): 1.1 ms
```

Đồng thời, nhờ tối ưu lại bộ đếm thời gian `thread_state`, hệ thống cũng đã phát hiện ra một sự cố nghiêm trọng khác:
```markdown
#### 🔴 HIGH MCS-4: [P8.1] CPU capacity and scheduler interference
> **Actual Value:** 848.0 ms (Warning Threshold: 20.0 ms)
**Recommendation:** Main Thread is runnable but preempted by OS. Check background process count or cpuset priority.
```
*(Main Thread đã sẵn sàng chạy nhưng bị hệ điều hành "giam" suốt 848ms, có thể do CPU quá tải hoặc phân bổ `cpuset` sai).*

Công cụ của chúng ta giờ đây thực sự là một vũ khí hạng nặng để "khám nghiệm tử thi" mọi sự cố hiệu năng trên Android!
