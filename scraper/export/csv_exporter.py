"""
CSV export functionality.
"""

import csv
import logging
from pathlib import Path
from typing import Any

from scraper.export.base_exporter import BaseExporter

logger = logging.getLogger(__name__)


class CSVExporter(BaseExporter):
    """Export data to CSV format."""

    async def export(self, data: list[dict[str, Any]], metadata: dict[str, Any]) -> Path:
        """
        Export to CSV.

        Args:
            data: List of dicts to export
            metadata: Metadata

        Returns:
            Path to CSV file
        """
        if not data:
            logger.warning("No data to export")
            return self.output_path

        self._ensure_directory()

        # Get all unique keys across all items
        all_keys = set()
        for item in data:
            all_keys.update(item.keys())

        fieldnames = sorted(all_keys)

        # Write CSV
        with open(self.output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for item in data:
                # Convert lists/dicts to strings
                row = {}
                for key in fieldnames:
                    value = item.get(key)
                    if isinstance(value, (list, dict)):
                        row[key] = str(value)
                    elif value is None:
                        row[key] = ""
                    else:
                        row[key] = value
                writer.writerow(row)

        logger.info(f"Exported {len(data)} items to {self.output_path}")
        return self.output_path
