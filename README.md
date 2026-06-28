# Android-FTA: Android App Launch Delay Analyzer

**AI-powered Android app startup performance analysis using Fault Tree Analysis (FTA) and Perfetto.**

This project uses Google's standalone `trace_processor` binary to execute SQL queries on Perfetto trace files, matching results against threshold values to diagnose performance issues according to the AOSP P1-P8 taxonomy.

---

## Features

- **Decoupled Architecture**: SQL queries, performance thresholds, and root-cause strategies are configured as JSON files. No Python edits are needed to support new scenarios.
- **Single-Trace Analysis (`run`)**: Extracts launch timing breakdowns (Zygote, bindApplication, inflate, etc.), thread scheduling states, average CPU frequencies, and the top 3 external critical path blockers.
- **Batch Differential Comparison (`compare`)**: Group trace files from DUT and REF directories across cycles, compute medians to filter outliers, calculate deltas, and evaluate using delta-thresholds.
- **Multi-Format Output**: Reports can be formatted and saved as **Markdown**, **JSON**, or **CSV**.
- **Parallel Trace Analysis**: Leverage python concurrent threads via `--max-workers` to parse multiple traces concurrently.
- **Comprehensive Tests**: 78 unit and integration tests passing, ensuring robustness of data models, providers, and parsing.

---

## Project Structure

```
Android-FTA/
├── main.py                     # CLI Entry Point
├── pyproject.toml              # Project dependencies and tool configurations
├── trace_processor.exe         # Perfetto trace processor binary (Windows)
├── android_fta/                # Main package
│   ├── __main__.py             # Submodule entry point (python -m android_fta)
│   ├── cli/                    # CLI parsing and command routing
│   ├── core/                   # SkillEngine, FTAEngine, BatchEngine, and Models
│   ├── providers/              # Perfetto Trace Processor subprocess adapter
│   └── reports/                # Markdown, CSV, and JSON formatters
├── knowledge/                  # Performance Knowledge base (SQL queries, rules)
│   ├── skills/                 # Skill definitions (timings and thresholds)
│   └── strategies/             # Strategies (root-cause mappings)
├── docs/                       # Documentation (Architecture, Deep dive)
└── tests/                      # Unit test suite
```

For a detailed walkthrough of code modules and extensibility patterns, please refer to the [Architecture Guide](docs/ARCHITECTURE.md).

---

## Installation & Running

### Requirements

- Python 3.10+
- Perfetto trace processor binary (the package defaults to `./trace_processor.exe` on Windows or `./trace_processor` on Unix. Make sure the binary exists in the project root or is available in your PATH).

### Installation

Install the package in editable mode along with development dependencies:

```bash
pip install -e ".[dev]"
```

### CLI Command Options

#### 1. Single Trace Analysis (`run`)
Runs performance rules (skills) on a single trace and outputs a report.

```bash
python main.py run startup_analysis --trace /path/to/trace.pftrace --format markdown --output report.md
```

Options:
* `skill` (positional): Name of the skill to execute (e.g., `startup_analysis`).
* `--trace` (required): Path to the Perfetto trace file.
* `--output`, `-o`: File path to save the report (defaults to `<skill>_report.<format>`).
* `--format`: Output format, choose from `markdown`, `json`, `csv` (defaults to `markdown`).
* `--max-workers`: Max worker threads (reserved for future parallel startup event parsing).

#### 2. Batch Differential Comparison (`compare`)
Compares trace files in a DUT directory against a REF directory.

```bash
python main.py compare --dut ./traces/dut/ --ref ./traces/ref/ --skill startup_analysis --format markdown
```

Options:
* `--dut` (required): Directory containing DUT trace files.
* `--ref` (required): Directory containing REF trace files.
* `--skill`: Performance skill name (defaults to `startup_analysis`).
* `--output`, `-o`: Output report path.
* `--parser-regex`: Custom regex pattern to extract `app`, `timestamp`, `cycle`, and `entry_type` from filenames. If omitted, the Smart Auto-detector is used.
* `--format`: Output format, choose from `markdown`, `json`, `csv` (defaults to `markdown`).
* `--max-workers`: Max concurrent threads to analyze traces (defaults to `4`).

---

## Development & Validation

### Running the Test Suite

Run all tests via `pytest`:

```bash
pytest tests/ -v --tb=short
```

Run test coverage analysis:

```bash
pytest tests/ --cov=android_fta --cov-report=term-missing
```

### Code Formatting & Quality

Code style is enforced via `ruff`. Ensure checks pass before committing:

```bash
# Lint checks
ruff check android_fta/ tests/

# Format code
ruff format android_fta/ tests/
```

---

## License

This project is licensed under the terms of the LICENSE file in the repository root.
