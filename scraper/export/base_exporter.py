"""
Base exporter interface.

All exporters inherit from this.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class BaseExporter(ABC):
    """Abstract base class for all exporters."""

    def __init__(self, output_path: Path):
        """
        Initialize exporter.

        Args:
            output_path: Path to export file
        """
        self.output_path = output_path

    @abstractmethod
    async def export(self, data: list[dict[str, Any]], metadata: dict[str, Any]) -> Path:
        """
        Export data to file.

        Args:
            data: List of items to export
            metadata: Metadata about the scrape

        Returns:
            Path to exported file
        """
        pass

    def _ensure_directory(self) -> None:
        """Ensure output directory exists."""
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
