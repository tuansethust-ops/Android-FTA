# Task Checklist: Top External Critical Path Blockers

## 1. Nâng cấp Knowledge Base
- `[x]` Thêm query `top_external_blockers` vào `knowledge/skills/startup_analysis.json`.

## 2. Nâng cấp Core Engine
- `[x]` Sửa `core/skill_engine.py` để chạy query CP và gắn vào biến trả về.
- `[x]` Sửa `main.py` bổ sung mục "3. Top 3 External Critical Path Blockers" vào Markdown.

## 3. Kiểm thử & Debugging
- `[x]` Chạy lệnh phân tích với `lacunh_heavy.pftrace` để kiểm tra lỗi cú pháp và output của Critical Path.
- `[x]` Cập nhật `walkthrough.md`.
