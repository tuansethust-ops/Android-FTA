# Android-FTA: Android App Launch Delay Analyzer (v4)

**AI-powered Android app startup performance analysis using Fault Tree Analysis (FTA) and Perfetto.**

---

## Tong quan

`Android-FTA` la cong cu phan tich hieu nang khoi chay ung dung Android, ket hop:

- **Perfetto Trace Processor** — xu ly trace goc tu thiet bi thuc
- **Skill-based Analysis** — trich xuat metrics theo tung kich ban (skill)
- **Fault Tree Analysis (FTA)** — chan doan nguyen nhan goc re (root cause) bang MCS
- **JSON-driven Knowledge Base** — de mo rong, khong can sua code

---

## Kien truc he thong

```
analyzer/
├── main.py                    # CLI entrypoint
├── core/
│   ├── fta_engine.py          # Fault Tree Analysis Engine
│   └── skill_engine.py        # Skill orchestrator (SQL runner)
├── providers/
│   └── perfetto_provider.py   # Adapter: Python -> trace_processor binary
├── knowledge/
│   ├── skills/
│   │   └── startup_analysis.json  # SQL queries + thresholds
│   └── strategies/
│       └── root_causes.json       # Knowledge base: root causes + recommendations
└── README.md                       # This file

trace_processor                  # Perfetto v56.1 auto-generated wrapper
```

### Luong du lieu


---

## Luồng dữ liệu

```
[Perfetto Trace File]
         │
         ▼
PerfettoProvider.query(sql)
   └→ Ghi SQL → temp .sql
   └→ Chạy: trace_processor -q <temp.sql> <trace>
   └→ Nhận CSV stdout
   └→ Parse → list[dict]
         │
         ▼
SkillEngine.run_startup_analysis()
   ├→ Query bindApplication, thread_states, cpu_freq...
   └→ metrics: {bind_application_ms, thread_runnable_ms, ...}
         │
         ▼
FTAEngine.evaluate("startup_analysis", metrics, thresholds)
   ├→ Load root_causes.json
   ├→ So sánh metrics vs thresholds
   ├→ Phân loại: HIGH / MEDIUM / NONE
   └→ Sắp xếp → list[issues] (MCS)
         │
         ▼
main.py → format_report() → Markdown → startup_analysis_report.md
```
---

## Cài đặt & Chạy

### Yêu cầu

- Python 3.x
- Perfetto trace file (`.pftrace`, `.perfetto`, `.trace`)
- `trace_processor` binary (đi kèm repo, auto-download nếu thiếu)

### Chạy phân tích

```bash
# Phân tích startup
python -m analyzer.main run startup_analysis --trace <path_to_trace.pftrace>

# Ví dụ:
python -m analyzer.main run startup_analysis --trace SmartPerfetto/test-traces/lacunh_heavy.pftrace
```

### Đầu ra

- File báo cáo Markdown: `startup_analysis_report.md`
- Bao gồm:
  - Tổng thời gian khởi chạy (dur/TTID/TTFD)
  - Metrics hệ thống cấp thấp
  - Minimal Cut Sets (MCS) được sắp xếp theo mức độ nghiêm trọng
  - Đề xuất khắc phục cụ thể
 
---

## License

This project is licensed under the terms of the LICENSE file in the repository root.

---

## Contributing

1. Fork repo
2. Tạo feature branch: `git checkout -b feature/new-skill`
3. Commit: `git commit -m "Add new skill"`
4. Push: `git push origin feature/new-skill`
5. Tạo Pull Request

---

## Links

- **Repo**: https://github.com/tuansethust-ops/Android-FTA
- **Perfetto Docs**: https://perfetto.dev/docs/

---

## Credits

Phát triển bởi Android Performance Team. Powered by Perfetto.
