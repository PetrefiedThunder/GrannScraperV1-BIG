"""
Base extractor interface.

All extractors inherit from this.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional

from bs4 import BeautifulSoup

from scraper.config.models import FieldConfig


class BaseExtractor(ABC):
    """Abstract base class for all extractors."""

    @abstractmethod
    async def extract(
        self,
        soup: BeautifulSoup,
        field_name: str,
        field_config: FieldConfig,
        context: Optional[dict[str, Any]] = None,
    ) -> Any:
        """
        Extract field value from parsed HTML.

        Args:
            soup: Parsed HTML (BeautifulSoup)
            field_name: Name of field being extracted
            field_config: Configuration for this field
            context: Optional context (URL, metadata, etc.)

        Returns:
            Extracted value (can be single value or list)
        """
        pass

    def _apply_regex(self, value: str, pattern: str) -> Optional[str]:
        """
        Apply regex pattern to extracted value.

        Args:
            value: Value to process
            pattern: Regex pattern

        Returns:
            Matched value or None
        """
        import re
        match = re.search(pattern, value)
        if match:
            return match.group(1) if match.groups() else match.group(0)
        return None
