# 🚀 Android App Launch Delay Analyzer - Project Handover

**To: Next Coding Agent (Cline / AI Assistant)**
**From: Google Antigravity (Initial Architect)**

This document serves as a comprehensive Knowledge Transfer (KT) to help you seamlessly take over this project. Please read this entirely before making any code changes.

---

## 1. Project Vision & Architecture
This project is an **Enterprise-grade Android Performance Analyzer**, heavily inspired by Google's internal **SmartPerfetto** architecture. 

It aims to automatically analyze `.pftrace` files to find the root causes of App Launch delays without requiring manual UI inspection.

### Architecture: "Skill-based Engine"
We explicitly DO NOT hardcode analysis logic (like `if package == "camera"`) inside Python. The system is decoupled:
- **Core Engine (Python):** Executes queries, orchestrates data, and formats Markdown reports.
- **Trace Processor (Binary):** A standalone Google binary used to run SQL against `.pftrace` files.
- **Knowledge Base (JSON):** Contains `skills` (SQL queries + thresholds) and `strategies` (Root cause mappings).

### The Taxonomy: P1-P8 Convergence Model
We strictly follow the **App Entry FTA - Leaf Convergence Model (v6.5)**. All root causes are mapped to 8 phases:
- `P1-P2`: Input & Framework Orchestration.
- `P3`: Process Bring-up (`dlopen`, `bindApplication`).
- `P4`: App Init & Lifecycle (`activityStart`, JIT, Lock Contention).
- `P5`: Resource / Data (`inflate`, Asset loading).
- `P6`: Frame Production (`Choreographer`).
- `P8`: System-wide Interference (CPU Starvation, GC, I/O Blocks).

---

## 2. Current State (What has been implemented)

The project currently operates in **Single-Trace Mode** (`python3 analyzer/main.py run startup_analysis --trace <file>`).

### Key Modules Built:
1. `analyzer/providers/perfetto_provider.py`: Wraps the `trace_processor` subprocess.
2. `analyzer/core/skill_engine.py`: Loads `startup_analysis.json`, iterates over all startup events, and executes SQL.
3. `analyzer/core/fta_engine.py`: Evaluates metrics against thresholds and maps them to P-taxonomy rules in `root_causes.json`.
4. `analyzer/main.py`: The CLI entry point that outputs a beautifully formatted Markdown report (`startup_analysis_report.md`).

### Deep Capabilities (Already working!):
- Uses Perfetto Stdlib: `android.startup.startups` (for TTID/TTFD) and `android.startup.startup_breakdowns` (for `bind_application`, `activity_start`, `inflate` timings).
- **Raw Critical Path Analysis:** We wrote a custom SQL query using `sched.thread_executing_span` to extract the **Top 3 External Blockers** (e.g., `system_server`, `kworker`) that blocked the Main Thread during startup, explicitly excluding the app's own internal threads.

---

## 3. Your Mission (Next Steps)

The user requires a **Batch Differential Analysis (DUT vs REF)** feature.
Currently, the user has test folders containing traces from 3 cycles. Each cycle has 2 traces per app: a **First Entry** and a **Re-entry**.

### The Problem with Default Perfetto Grouping
Perfetto's native `startup_type` (COLD/WARM/HOT) is unreliable here. Because the test script waits 5 minutes after a reboot, OS background tasks might inadvertently start the app, turning an intended COLD start (First Entry) into a WARM start. If we group by Perfetto's output, we break the test cycles.

### The Required Implementation:
You must implement a new command: `python3 analyzer/main.py compare --dut <DUT_DIR> --ref <REF_DIR>`

**Execution Flow for `compare` mode:**
1. **File Parsing (PENDING USER INPUT):** Scan both directories for `.pftrace` files. Parse the **filenames** to extract the App Name and Timestamp. **IMPORTANT:** The exact filename format is currently unknown (the user will provide this from another computer). **DO NOT** hardcode the Regex until the user provides the format.
2. **Grouping:** For each App in a Cycle, order the traces by timestamp. The earlier one is **First-entry**, the later one is **Re-entry**.
3. **Execution:** Run the existing `SkillEngine` on every trace to extract metrics (TTID, binder wait, inflate, etc.).
4. **Aggregation:** Calculate the **Median** for each metric across the 3 cycles to eliminate outliers.
5. **Delta Calculation:** Calculate `Delta = DUT_Median - REF_Median` for First-entry and Re-entry separately.
6. **FTA Evaluation:** Pass the `Delta` values into `FTAEngine`. The thresholds in `startup_analysis.json` should now act as Delta Thresholds (e.g., if DUT is 40ms slower than REF in `inflate`, trigger P5.6).
7. **Reporting:** Generate a comparative Markdown report.

---

## 4. Quick Start for the Next Agent
1. Look at `analyzer/knowledge/skills/startup_analysis.json` to understand the SQL queries.
2. Look at `analyzer/knowledge/strategies/root_causes.json` to understand the P1-P8 taxonomy.
3. Look at `analyzer/main.py` to see how the single-trace `run` command is implemented.
4. Begin implementing `core/batch_engine.py` and the `compare` command in `main.py` according to the mission above!

**Good luck, Agent! Continue the legacy.** 🚀
