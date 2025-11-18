"""
Data cleaning and normalization utilities.
"""

import re
from typing import Any, Optional


class DataCleaner:
    """
    Clean and normalize scraped data.

    Provides common cleaning operations.
    """

    @staticmethod
    def clean_text(text: Optional[str]) -> Optional[str]:
        """
        Clean text value.

        Args:
            text: Text to clean

        Returns:
            Cleaned text
        """
        if not text or not isinstance(text, str):
            return text

        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text)

        # Strip leading/trailing whitespace
        text = text.strip()

        # Remove zero-width characters
        text = text.replace("\u200b", "")  # Zero-width space
        text = text.replace("\ufeff", "")  # Zero-width no-break space

        return text if text else None

    @staticmethod
    def normalize_whitespace(text: Optional[str]) -> Optional[str]:
        """Normalize all whitespace to single spaces."""
        if not text:
            return text

        return " ".join(text.split())

    @staticmethod
    def remove_html_tags(text: Optional[str]) -> Optional[str]:
        """Remove HTML tags from text."""
        if not text:
            return text

        clean = re.compile("<.*?>")
        return re.sub(clean, "", text)

    @staticmethod
    def extract_numbers(text: Optional[str]) -> Optional[str]:
        """Extract only numbers from text."""
        if not text:
            return text

        numbers = re.findall(r"\d+", str(text))
        return "".join(numbers) if numbers else None

    @staticmethod
    def extract_currency(text: Optional[str]) -> Optional[float]:
        """
        Extract currency value from text.

        Args:
            text: Text containing currency

        Returns:
            Float value or None
        """
        if not text:
            return None

        # Remove currency symbols and commas
        cleaned = re.sub(r"[$€£¥,]", "", str(text))

        # Extract number
        match = re.search(r"\d+\.?\d*", cleaned)
        if match:
            try:
                return float(match.group())
            except ValueError:
                return None

        return None

    @staticmethod
    def clean_url(url: Optional[str]) -> Optional[str]:
        """
        Clean and normalize URL.

        Args:
            url: URL to clean

        Returns:
            Cleaned URL
        """
        if not url:
            return url

        url = url.strip()

        # Remove tracking parameters (common ones)
        url = re.sub(r"[?&](utm_|fbclid=|gclid=)[^&]*", "", url)

        # Clean up multiple ? or &
        url = re.sub(r"\?&", "?", url)
        url = re.sub(r"&+", "&", url)

        # Remove trailing ? or &
        url = url.rstrip("?&")

        return url

    @staticmethod
    def standardize_phone(phone: Optional[str]) -> Optional[str]:
        """
        Standardize phone number format.

        Args:
            phone: Phone number string

        Returns:
            Standardized phone number
        """
        if not phone:
            return phone

        # Extract digits only
        digits = re.sub(r"\D", "", str(phone))

        # Format based on length (US format)
        if len(digits) == 10:
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        elif len(digits) == 11 and digits[0] == "1":
            return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
        else:
            return digits

    @staticmethod
    def clean_email(email: Optional[str]) -> Optional[str]:
        """
        Clean and validate email.

        Args:
            email: Email address

        Returns:
            Cleaned email or None if invalid
        """
        if not email:
            return email

        email = email.strip().lower()

        # Basic email validation
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if re.match(email_pattern, email):
            return email

        return None

    @staticmethod
    def normalize_case(text: Optional[str], case: str = "lower") -> Optional[str]:
        """
        Normalize text case.

        Args:
            text: Text to normalize
            case: Target case (lower, upper, title, sentence)

        Returns:
            Normalized text
        """
        if not text:
            return text

        if case == "lower":
            return text.lower()
        elif case == "upper":
            return text.upper()
        elif case == "title":
            return text.title()
        elif case == "sentence":
            return text.capitalize()
        else:
            return text

    @staticmethod
    def remove_duplicates(items: list[Any]) -> list[Any]:
        """
        Remove duplicate items while preserving order.

        Args:
            items: List with potential duplicates

        Returns:
            List with duplicates removed
        """
        seen = set()
        result = []

        for item in items:
            # Handle unhashable types
            try:
                if item not in seen:
                    seen.add(item)
                    result.append(item)
            except TypeError:
                # For unhashable types (dicts, lists), always include
                result.append(item)

        return result

    @staticmethod
    def clean_item(item: dict[str, Any]) -> dict[str, Any]:
        """
        Clean all text fields in an item.

        Args:
            item: Item dict

        Returns:
            Cleaned item dict
        """
        cleaned = {}

        for key, value in item.items():
            if isinstance(value, str):
                cleaned[key] = DataCleaner.clean_text(value)
            elif isinstance(value, list):
                cleaned[key] = [
                    DataCleaner.clean_text(v) if isinstance(v, str) else v
                    for v in value
                ]
            else:
                cleaned[key] = value

        return cleaned
