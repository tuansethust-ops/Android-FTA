# Android-FTA Architecture Guide

Welcome, future AI Agent / Developer! This document explains the codebase design, data flows, core components, and extensibility patterns of the `Android-FTA` system. 

---

## 1. System Vision & Overview

`Android-FTA` is an automated, SQL-driven performance analyzer for Android applications. It runs queries on `.pftrace` (Perfetto) files using Google's standalone `trace_processor` binary and applies **Fault Tree Analysis (FTA)** logic to flag root causes of app launch delays.

Unlike naive hardcoded script tools, the performance analysis rules are **completely decoupled** from Python code:
* **The Engines (Python)** coordinate file processing, SQL execution, delta evaluation, and report generation.
* **The Knowledge Base (JSON)** contains SQL query definitions, thresholds, and strategic root cause recommendations mapping to the **AOSP P1-P8 Performance Taxonomy**.

---

## 2. Directory Structure

```
Android-FTA/
├── main.py                     # CLI Entry Point
├── pyproject.toml              # Build & dependency settings (Ruff, Mypy, Pytest)
├── trace_processor.exe         # Standalone Google trace_processor binary (Windows)
├── .github/workflows/ci.yml    # CI/CD test and lint checks
├── android_fta/                # Main Application Package
│   ├── __init__.py
│   ├── __main__.py             # Entry point for python -m android_fta
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── commands.py         # Subcommand runners (run, compare)
│   │   └── parser.py           # CLI Argument specifications
│   ├── core/
│   │   ├── __init__.py
│   │   ├── models.py           # Strictly-typed Dataclasses
│   │   ├── skill_engine.py     # SQL Orchestrator & Safe Float converter
│   │   ├── fta_engine.py       # Fault Tree Evaluator & Threshold Validator
│   │   └── batch_engine.py     # Folder-scanning and Grouping compares
│   ├── providers/
│   │   ├── __init__.py
│   │   └── perfetto.py         # Subprocess Trace Processor adapter
│   └── reports/
│       ├── __init__.py
│       ├── base.py             # Abstract report formatter interface
│       ├── markdown.py         # Formats outputs as Markdown
│       ├── csv.py              # Formats outputs as CSV
│       └── json.py             # Formats outputs as JSON
├── knowledge/                  # Performance Rules Base
│   ├── skills/
│   │   └── startup_analysis.json  # SQL query maps + thresholds
│   └── strategies/
│       └── root_causes.json       # FTA rules + recommendations
├── docs/
│   ├── ARCHITECTURE.md         # This document
│   └── research_deep_dive.md   # Domain-specific AOSP startup deep dive
└── tests/                      # Unit test suites (78 passing)
    ├── conftest.py
    ├── test_cli.py
    ├── test_perfetto_provider.py
    ├── test_skill_engine.py
    ├── test_fta_engine.py
    ├── test_batch_engine.py
    └── test_reports.py
```

---

## 3. Core Components & Logic

### 3.1 Data Models (`core/models.py`)
All internal metrics, issues, and comparison results are backed by strongly-typed Python `dataclasses`:
* `StartupMetrics`: Stores launch durations (`dur_ms`, `ttid_ms`, `ttfd_ms`), low-level breakdowns, CPU scheduler states, and blocker threads.
* `Issue`: Represents a single flagged performance anomaly (`code` like `P3.7`, `severity` like `HIGH/MEDIUM`, `value`, and `recommendation`).
* `DifferentialMetric` / `AppComparison`: Structures compared DUT vs REF metrics (medians, delta, delta%).

### 3.2 Trace Processor Provider (`providers/perfetto.py`)
The `PerfettoProvider` manages execution of SQL against a trace:
* It generates a temporary `.sql` file containing the query.
* Spawns `trace_processor` using `subprocess.run()`.
* Automatically cleans up temporary files (even on execution failures).
* Enforces a configurable timeout (default `300s`) to prevent hanging.
* Parses stdout CSV using Python's `csv.DictReader` into a list of row dicts.

### 3.3 Skill Engine (`core/skill_engine.py`)
Loads a skill definition JSON and drives metrics collection:
1. Queries the trace for startup events.
2. For each startup event, runs supplementary queries (Breakdown timings, Thread scheduler states, Avg CPU frequency, Top external critical path blockers).
3. Evaluates and converts row outputs to float values via `_safe_float()`, safely handling missing keys, empty strings, and `[NULL]` placeholders.

### 3.4 FTA Engine (`core/fta_engine.py`)
The decision-making component of the tool:
* **Caching**: On initialization, it reads and caches `root_causes.json` to prevent repeating disk reads.
* **Evaluation**: Matches extracted metrics against warning/alert thresholds. It supports both `absolute_gt` (greater than) and `absolute_lt` (less than, e.g., CPU frequency) comparisons.
* **Delta Mode**: When analyzing batch comparisons, it switches to evaluating medians against `delta_high` and `delta_medium` limits.
* **Validation Gate**: Includes `validate_thresholds()`, which cross-references skill thresholds against root cause strategies, warning if rules refer to missing thresholds or vice-versa.

### 3.5 Batch Engine (`core/batch_engine.py`)
Facilitates bulk comparison between directories:
1. **Trace Collection**: Scans a directory for `.pftrace`, `.perfetto-trace`, or `.trace` files.
2. **Filename Parsing**: Extracts App Name, Timestamp, Cycle ID, and Entry Type (First-entry vs Re-entry) using `FilenameParser`.
   * **Smart Auto-detector**: Extracts cycle indicators (`CycleX`, `cycle_X`), timestamps (`YYYYMMDD_HHMMSS`), and entry keywords (`_first_`, `_entry1_`, `_re_`, `_reentry_`).
   * **Regex Parser**: Configured via a CLI regex pattern containing named match groups.
3. **Parallel Processing**: Uses a `ThreadPoolExecutor` to analyze trace files concurrently, bounded by `--max-workers`.
4. **Differential Aggregation**:
   * Groups trace results by `(app_name, entry_type)`.
   * Computes the **Median** value across cycles for each metric (eliminating boot-up and OS background scheduling outliers).
   * Calculates `Delta = DUT_Median - REF_Median` and evaluates the difference in the `FTAEngine`.

---

## 4. Single-Trace vs. Batch Comparison Flows

### 4.1 Single Trace Mode (`run`)
```
[Trace File] ──> PerfettoProvider ──> [SQL Queries] ──> SkillEngine ──> [StartupMetrics] ──> FTAEngine ──> [Markdown/JSON/CSV]
```

### 4.2 Batch Differential Mode (`compare`)
```
[DUT & REF Folder] ──> Scan & Parse ──> ThreadPoolExecutor ──> Median across Cycles ──> Delta (DUT - REF) ──> FTA delta_mode ──> [ReportFormatter]
```

---

## 5. How to Extend the System

Adding new performance analysis scenarios is easy and requires no changes to the Python source code.

### Step 1: Create a Skill file
Add a new JSON file under `knowledge/skills/<skill_name>.json`. Define:
* `queries`: SQL templates, where `{startup_id}` acts as a placeholder.
* `thresholds`: Key-value pairs defining `high`, `medium`, `delta_high`, `delta_medium`, and `compare_mode` (`absolute_gt` or `absolute_lt`).

```json
{
  "name": "my_custom_scenario",
  "queries": {
    "startups": "SELECT ...",
    "breakdown": "SELECT reason, dur as total_dur_ms FROM ... WHERE startup_id = {startup_id}"
  },
  "thresholds": {
    "my_metric": {
      "high": 100.0,
      "medium": 50.0,
      "delta_high": 30.0,
      "delta_medium": 15.0
    }
  }
}
```

### Step 2: Add Root Causes
Register the taxonomy mapping in `knowledge/strategies/root_causes.json` under your scenario key:
```json
{
  "my_custom_scenario": [
    {
      "code": "P9.9",
      "name": "Custom Performance Anomaly",
      "metric": "my_metric",
      "recommendation": "Perform optimization X and audit configuration Y."
    }
  ]
}
```

---

## 6. How to Run & Verify

### Command Line Interface
```bash
# Analyze a single trace
python main.py run startup_analysis --trace /path/to/trace.pftrace --format markdown

# Compare DUT and REF directories in parallel
python main.py compare --dut /path/to/dut/ --ref /path/to/ref/ --max-workers 8

# Output formats: markdown (default), json, or csv
python main.py run startup_analysis --trace /path/to/trace.pftrace --format json
```

### Running Tests & Coverage
```bash
# Install editable development dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v --tb=short

# Run test coverage
pytest tests/ --cov=android_fta --cov-report=term-missing
```

### Code Style & Linting
```bash
# Lint checks
ruff check android_fta/ tests/

# Auto-format code
ruff format android_fta/ tests/
```
