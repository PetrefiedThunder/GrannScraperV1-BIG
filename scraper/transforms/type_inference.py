"""
Type inference for scraped data.
"""

import re
from datetime import datetime
from typing import Any, Optional


class TypeInferrer:
    """
    Infer and convert data types automatically.

    Analyzes data patterns to guess types.
    """

    @staticmethod
    def infer_type(value: Any) -> str:
        """
        Infer the type of a value.

        Args:
            value: Value to analyze

        Returns:
            Type name (string, int, float, bool, date, url, email, phone)
        """
        if value is None or value == "":
            return "null"

        if not isinstance(value, str):
            if isinstance(value, bool):
                return "bool"
            elif isinstance(value, int):
                return "int"
            elif isinstance(value, float):
                return "float"
            elif isinstance(value, datetime):
                return "datetime"
            else:
                return "unknown"

        # String type inference
        value_clean = value.strip()

        # Boolean
        if value_clean.lower() in ("true", "false", "yes", "no"):
            return "bool"

        # URL
        if re.match(r"https?://", value_clean):
            return "url"

        # Email
        if re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", value_clean):
            return "email"

        # Phone (simplified)
        if re.match(r"^[\d\s\-\(\)\+]{10,}$", value_clean):
            return "phone"

        # Currency
        if re.match(r"^[$€£¥]\s*[\d,]+\.?\d*$", value_clean):
            return "currency"

        # Integer
        if re.match(r"^-?\d+$", value_clean.replace(",", "")):
            return "int"

        # Float
        if re.match(r"^-?\d+\.\d+$", value_clean.replace(",", "")):
            return "float"

        # Date/DateTime (simplified)
        if re.match(r"\d{4}-\d{2}-\d{2}", value_clean):
            return "date"

        # Default
        return "string"

    @staticmethod
    def convert_type(value: Any, target_type: str) -> Any:
        """
        Convert value to target type.

        Args:
            value: Value to convert
            target_type: Target type name

        Returns:
            Converted value or original if conversion fails
        """
        if value is None or value == "":
            return None

        try:
            if target_type == "int":
                if isinstance(value, str):
                    value = value.replace(",", "")
                return int(float(value))

            elif target_type == "float":
                if isinstance(value, str):
                    value = value.replace(",", "")
                return float(value)

            elif target_type == "bool":
                if isinstance(value, str):
                    return value.lower() in ("true", "yes", "1", "on")
                return bool(value)

            elif target_type == "currency":
                if isinstance(value, str):
                    # Extract number from currency string
                    match = re.search(r"[\d,]+\.?\d*", value)
                    if match:
                        return float(match.group().replace(",", ""))
                return float(value)

            elif target_type in ("date", "datetime"):
                from dateutil import parser
                return parser.parse(str(value))

            else:
                return str(value)

        except Exception:
            return value

    @staticmethod
    def infer_schema(items: list[dict[str, Any]]) -> dict[str, str]:
        """
        Infer schema from a list of items.

        Args:
            items: List of item dicts

        Returns:
            Dict mapping field names to inferred types
        """
        if not items:
            return {}

        schema = {}

        # Get all fields
        all_fields = set()
        for item in items:
            all_fields.update(item.keys())

        # Infer type for each field
        for field in all_fields:
            type_counts = {}

            for item in items:
                value = item.get(field)
                if value is not None and value != "":
                    inferred_type = TypeInferrer.infer_type(value)
                    type_counts[inferred_type] = type_counts.get(inferred_type, 0) + 1

            # Most common type wins
            if type_counts:
                schema[field] = max(type_counts, key=type_counts.get)
            else:
                schema[field] = "string"

        return schema
