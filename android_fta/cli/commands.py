"""CLI command implementations."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from android_fta.core.batch_engine import BatchEngine, FilenameParser
from android_fta.core.fta_engine import FTAEngine
from android_fta.core.models import StartupResult
from android_fta.core.skill_engine import SkillEngine
from android_fta.providers.perfetto import PerfettoError, PerfettoProvider
from android_fta.reports.base import ReportFormatter
from android_fta.reports.csv import CsvReportFormatter
from android_fta.reports.json import JsonReportFormatter
from android_fta.reports.markdown import MarkdownReportFormatter

logger = logging.getLogger(__name__)

# Project root: android_fta/cli/commands.py → ../../
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _resolve_tp_bin() -> str:
    """Find the trace_processor binary in common locations."""
    candidates = [
        _PROJECT_ROOT / "trace_processor.exe",  # Windows
        _PROJECT_ROOT / "trace_processor",  # Unix
        Path("trace_processor.exe"),
        Path("trace_processor"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate.resolve())
    return ""


def setup_logging(verbose: bool = False, quiet: bool = False) -> None:
    """Configure the logging system."""
    if quiet:
        level = logging.WARNING
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


_FORMATTERS: dict[str, type[ReportFormatter]] = {
    "csv": CsvReportFormatter,
    "json": JsonReportFormatter,
    "markdown": MarkdownReportFormatter,
}

_EXTENSIONS: dict[str, str] = {
    "csv": ".csv",
    "json": ".json",
    "markdown": ".md",
}


def _get_formatter(fmt: str) -> ReportFormatter:
    """Return the appropriate report formatter."""
    cls = _FORMATTERS.get(fmt, MarkdownReportFormatter)
    return cls()


def _get_extension(fmt: str) -> str:
    """Return the default file extension for a report format."""
    return _EXTENSIONS.get(fmt, ".md")


# ---------------------------------------------------------------------------
# run command
# ---------------------------------------------------------------------------


def cmd_run(  # noqa: PLR0913
    skill: str,
    trace: str,
    output: str | None,
    format: str,  # noqa: A002
    max_workers: int = 1,
) -> int:
    """Execute the 'run' command: analyze a single trace.

    Args:
        skill: Name of the skill to execute.
        trace: Path to the .pftrace file.
        output: Output file path (or None for default).
        format: Report format (markdown, csv, json).
        max_workers: Reserved for future parallel startup analysis.
    """
    _ = max_workers  # Reserved for Phase 4 parallel startup analysis

    tp_bin = _resolve_tp_bin()
    if not tp_bin:
        logger.error(
            "trace_processor binary not found. Download from "
            "https://perfetto.dev/docs/contributing/build-instructions"
        )
        return 1

    if not os.path.exists(trace):
        logger.error("Trace file not found: %s", trace)
        return 1

    try:
        provider = PerfettoProvider(tp_bin, trace)
    except PerfettoError as exc:
        logger.error("Failed to initialize PerfettoProvider: %s", exc)
        return 1

    skills_dir = _PROJECT_ROOT / "knowledge" / "skills"
    strategies_dir = _PROJECT_ROOT / "knowledge" / "strategies"

    if not skills_dir.exists():
        logger.error("Skills directory not found: %s", skills_dir)
        return 1

    engine = SkillEngine(provider, str(skills_dir))

    try:
        metrics = engine.execute(skill)
    except FileNotFoundError as exc:
        logger.error("Skill file not found: %s", exc)
        return 1

    # Load thresholds and evaluate
    skill_def = engine.load_skill(skill)
    thresholds = skill_def.get("thresholds", {})

    fta = FTAEngine(str(strategies_dir))
    for warning in fta.validate_thresholds(skill, thresholds):
        logger.warning("Threshold validation: %s", warning)

    results: list[StartupResult] = []
    for m in metrics:
        issues = fta.evaluate(skill, m, thresholds)
        results.append(StartupResult(metrics=m, issues=issues))

    # Format report
    formatter = _get_formatter(format)
    report = formatter.format_single(results, skill)

    # Save
    ext = _get_extension(format)
    report_path = output or f"{skill}_report{ext}"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    logger.info("Analysis complete! Report saved to %s", report_path)
    return 0


# ---------------------------------------------------------------------------
# compare command
# ---------------------------------------------------------------------------


def cmd_compare(  # noqa: PLR0913
    dut: str,
    ref: str,
    skill: str,
    output: str | None,
    parser_regex: str | None,
    format: str,  # noqa: A002
    max_workers: int = 4,
) -> int:
    """Execute the 'compare' command: differential analysis."""
    tp_bin = _resolve_tp_bin()
    if not tp_bin:
        logger.error("trace_processor binary not found.")
        return 1

    if not os.path.isdir(dut):
        logger.error("DUT directory not found: %s", dut)
        return 1
    if not os.path.isdir(ref):
        logger.error("REF directory not found: %s", ref)
        return 1

    skills_dir = str(_PROJECT_ROOT / "knowledge" / "skills")
    strategies_dir = str(_PROJECT_ROOT / "knowledge" / "strategies")

    parser = FilenameParser(pattern=parser_regex)
    batch = BatchEngine(
        tp_bin_path=tp_bin,
        skills_dir=skills_dir,
        strategies_dir=strategies_dir,
        parser=parser,
        max_workers=max_workers,
    )

    try:
        report = batch.compare(dut, ref, skill_name=skill)
    except Exception:
        logger.exception("Comparison failed")
        return 1

    formatter = _get_formatter(format)
    report_str = formatter.format_differential(report)

    ext = _get_extension(format)
    report_path = output or f"differential_report{ext}"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_str)

    logger.info("Comparison complete! Report saved to %s", report_path)
    return 0
