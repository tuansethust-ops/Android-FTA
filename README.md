# Android-FTA: Android App Launch Delay Analyzer (v4)

**AI-powered Android app startup performance analysis using Fault Tree Analysis (FTA) and Perfetto.**

---

## Overview

`Android-FTA` is a tool for analyzing Android app startup performance, combining:

- **Perfetto Trace Processor** — processing raw traces from real devices
- **Skill-based Analysis** — extracting metrics per scenario (skill)
- **Fault Tree Analysis (FTA)** — diagnosing root causes using MCS (Minimal Cut Sets)
- **JSON-driven Knowledge Base** — to extend without modifying code

---

## System Architecture

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

### Data Flow

```
[Perfetto Trace File]
         │
         ▼
PerfettoProvider.query(sql)
   └→ Write SQL → temp .sql
   └→ Run: trace_processor -q <temp.sql> <trace>
   └→ Receive CSV stdout
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
   ├→ Compare metrics vs thresholds
   ├→ Classify: HIGH / MEDIUM / NONE
   └→ Sort → list[issues] (MCS)
         │
         ▼
main.py → format_report() → Markdown → startup_analysis_report.md
```
---

## Installation & Running

### Requirements

- Python 3.x
- Perfetto trace file (`.pftrace`, `.perfetto`, `.trace`)
- `trace_processor` binary (included in repo, auto-download if missing)

### Run Analysis

```bash
# Startup analysis
python -m analyzer.main run startup_analysis --trace <path_to_trace.pftrace>

# Example:
python -m analyzer.main run startup_analysis --trace SmartPerfetto/test-traces/lacunh_heavy.pftrace
```

### Output

- Markdown report file: `startup_analysis_report.md`
- Includes:
  - Total startup time (dur/TTID/TTFD)
  - Low-level system metrics
  - Minimal Cut Sets (MCS) sorted by severity level
  - Specific remediation suggestions
 
---

## License

This project is licensed under the terms of the LICENSE file in the repository root.

---

## Contributing

1. Fork repo
2. Create feature branch: `git checkout -b feature/new-skill`
3. Commit: `git commit -m "Add new skill"`
4. Push: `git push origin feature/new-skill`
5. Create Pull Request

---

## Links

- **Repo**: https://github.com/tuansethust-ops/Android-FTA
- **Perfetto Docs**: https://perfetto.dev/docs/

---

## Credits

Developed by Android Performance Team. Powered by Perfetto.
