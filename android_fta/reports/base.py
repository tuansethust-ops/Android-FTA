"""Base report formatter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from android_fta.core.models import (
        DifferentialReport,
        StartupResult,
    )


class ReportFormatter(ABC):
    """Abstract base class for report formatters."""

    @abstractmethod
    def format_single(self, results: list[StartupResult], skill_name: str) -> str:
        """Format a single-trace analysis report."""
        ...

    @abstractmethod
    def format_differential(self, report: DifferentialReport) -> str:
        """Format a differential (DUT vs REF) analysis report."""
        ...
