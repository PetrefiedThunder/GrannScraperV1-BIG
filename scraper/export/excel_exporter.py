"""
Excel export functionality.
"""

import logging
from pathlib import Path
from typing import Any

from scraper.export.base_exporter import BaseExporter

logger = logging.getLogger(__name__)


class ExcelExporter(BaseExporter):
    """Export data to Excel (.xlsx) format."""

    async def export(self, data: list[dict[str, Any]], metadata: dict[str, Any]) -> Path:
        """
        Export to Excel.

        Args:
            data: List of dicts to export
            metadata: Metadata

        Returns:
            Path to Excel file
        """
        if not data:
            logger.warning("No data to export")
            return self.output_path

        self._ensure_directory()

        try:
            import pandas as pd

            # Convert to DataFrame
            df = pd.DataFrame(data)

            # Write to Excel with metadata sheet
            with pd.ExcelWriter(self.output_path, engine="openpyxl") as writer:
                # Write data
                df.to_excel(writer, sheet_name="Data", index=False)

                # Write metadata
                metadata_df = pd.DataFrame(
                    [{"key": k, "value": str(v)} for k, v in metadata.items()]
                )
                metadata_df.to_excel(writer, sheet_name="Metadata", index=False)

            logger.info(f"Exported {len(data)} items to {self.output_path}")
            return self.output_path

        except ImportError:
            logger.error(
                "pandas not installed. Install with: pip install pandas openpyxl"
            )
            raise
