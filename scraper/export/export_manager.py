"""
Export manager - coordinates multiple export formats.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from scraper.config.models import ExportConfig, ScrapeResult
from scraper.export.csv_exporter import CSVExporter
from scraper.export.excel_exporter import ExcelExporter
from scraper.export.json_exporter import JSONExporter, NDJSONExporter
from scraper.export.sqlite_exporter import SQLiteExporter

logger = logging.getLogger(__name__)


class ExportManager:
    """
    Manages exporting data to multiple formats.

    Coordinates various exporters and handles file naming.
    """

    def __init__(self, config: ExportConfig):
        """
        Initialize export manager.

        Args:
            config: Export configuration
        """
        self.config = config

    async def export_result(self, result: ScrapeResult) -> dict[str, Path]:
        """
        Export scrape result to configured formats.

        Args:
            result: ScrapeResult to export

        Returns:
            Dict mapping format name to exported file path
        """
        exported_files = {}

        if not result.data:
            logger.warning("No data to export")
            return exported_files

        # Generate base filename
        timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
        filename_vars = {
            "job_name": result.metadata.get("job_name", "scrape"),
            "timestamp": timestamp,
            "job_id": result.job_id,
        }
        base_filename = self.config.filename_template.format(**filename_vars)

        # Ensure base directory exists
        self.config.base_path.mkdir(parents=True, exist_ok=True)

        # Export to each format
        for export_format in self.config.formats:
            try:
                file_path = await self._export_format(
                    export_format,
                    base_filename,
                    result.data,
                    result.metadata,
                )
                if file_path:
                    exported_files[export_format] = file_path
            except Exception as e:
                logger.error(f"Failed to export to {export_format}: {e}")

        return exported_files

    async def _export_format(
        self,
        export_format: str,
        base_filename: str,
        data: list[dict[str, Any]],
        metadata: dict[str, Any],
    ) -> Path:
        """
        Export to specific format.

        Args:
            export_format: Format name (csv, json, excel, etc.)
            base_filename: Base filename (without extension)
            data: Data to export
            metadata: Metadata

        Returns:
            Path to exported file
        """
        format_lower = export_format.lower()

        if format_lower == "csv":
            output_path = self.config.base_path / f"{base_filename}.csv"
            exporter = CSVExporter(output_path)
            return await exporter.export(data, metadata)

        elif format_lower == "json":
            output_path = self.config.base_path / f"{base_filename}.json"
            exporter = JSONExporter(output_path)
            return await exporter.export(data, metadata)

        elif format_lower == "ndjson":
            output_path = self.config.base_path / f"{base_filename}.ndjson"
            exporter = NDJSONExporter(output_path)
            return await exporter.export(data, metadata)

        elif format_lower in ("excel", "xlsx"):
            output_path = self.config.base_path / f"{base_filename}.xlsx"
            exporter = ExcelExporter(output_path)
            return await exporter.export(data, metadata)

        elif format_lower in ("sqlite", "db"):
            output_path = self.config.base_path / f"{base_filename}.db"
            exporter = SQLiteExporter(output_path)
            return await exporter.export(data, metadata)

        else:
            logger.warning(f"Unknown export format: {export_format}")
            return None
