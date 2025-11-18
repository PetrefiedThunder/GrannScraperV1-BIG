"""
JSON export functionality.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from scraper.export.base_exporter import BaseExporter

logger = logging.getLogger(__name__)


class JSONExporter(BaseExporter):
    """Export data to JSON format."""

    async def export(self, data: list[dict[str, Any]], metadata: dict[str, Any]) -> Path:
        """
        Export to JSON.

        Args:
            data: List of dicts to export
            metadata: Metadata

        Returns:
            Path to JSON file
        """
        self._ensure_directory()

        export_data = {
            "metadata": metadata,
            "items": data,
            "count": len(data),
            "exported_at": datetime.utcnow().isoformat(),
        }

        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(
                export_data,
                f,
                indent=2,
                ensure_ascii=False,
                default=str,  # Handle datetime, etc.
            )

        logger.info(f"Exported {len(data)} items to {self.output_path}")
        return self.output_path


class NDJSONExporter(BaseExporter):
    """Export data to NDJSON (newline-delimited JSON) format."""

    async def export(self, data: list[dict[str, Any]], metadata: dict[str, Any]) -> Path:
        """Export to NDJSON."""
        self._ensure_directory()

        with open(self.output_path, "w", encoding="utf-8") as f:
            for item in data:
                f.write(json.dumps(item, ensure_ascii=False, default=str))
                f.write("\n")

        logger.info(f"Exported {len(data)} items to {self.output_path}")
        return self.output_path
