"""
SQLite export functionality.
"""

import logging
import sqlite3
from pathlib import Path
from typing import Any

from scraper.export.base_exporter import BaseExporter

logger = logging.getLogger(__name__)


class SQLiteExporter(BaseExporter):
    """Export data to SQLite database."""

    def __init__(self, output_path: Path, table_name: str = "scraped_data"):
        """
        Initialize SQLite exporter.

        Args:
            output_path: Path to SQLite database file
            table_name: Name of table to create/insert into
        """
        super().__init__(output_path)
        self.table_name = table_name

    async def export(self, data: list[dict[str, Any]], metadata: dict[str, Any]) -> Path:
        """
        Export to SQLite.

        Args:
            data: List of dicts to export
            metadata: Metadata

        Returns:
            Path to SQLite database
        """
        if not data:
            logger.warning("No data to export")
            return self.output_path

        self._ensure_directory()

        conn = sqlite3.connect(str(self.output_path))
        cursor = conn.cursor()

        try:
            # Get all unique columns
            all_columns = set()
            for item in data:
                all_columns.update(item.keys())

            columns = sorted(all_columns)

            # Create table
            column_defs = ", ".join([f'"{col}" TEXT' for col in columns])
            create_sql = f'CREATE TABLE IF NOT EXISTS "{self.table_name}" ({column_defs})'
            cursor.execute(create_sql)

            # Insert data
            placeholders = ", ".join(["?" for _ in columns])
            column_names = ", ".join([f'"{col}"' for col in columns])
            insert_sql = f'INSERT INTO "{self.table_name}" ({column_names}) VALUES ({placeholders})'

            for item in data:
                values = []
                for col in columns:
                    value = item.get(col)
                    if isinstance(value, (list, dict)):
                        import json
                        value = json.dumps(value)
                    elif value is None:
                        value = None
                    else:
                        value = str(value)
                    values.append(value)

                cursor.execute(insert_sql, values)

            # Create metadata table
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS metadata (key TEXT, value TEXT)"
            )
            for key, value in metadata.items():
                cursor.execute(
                    "INSERT INTO metadata (key, value) VALUES (?, ?)",
                    (key, str(value))
                )

            conn.commit()
            logger.info(f"Exported {len(data)} items to {self.output_path}")

        finally:
            conn.close()

        return self.output_path
