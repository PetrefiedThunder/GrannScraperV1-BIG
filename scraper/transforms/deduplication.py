"""
Data deduplication utilities.
"""

import hashlib
import json
from typing import Any, Optional


class Deduplicator:
    """
    Remove duplicate items from scraped data.

    Supports various deduplication strategies.
    """

    @staticmethod
    def deduplicate_by_key(
        items: list[dict[str, Any]], key: str
    ) -> list[dict[str, Any]]:
        """
        Deduplicate by specific key field.

        Args:
            items: List of items
            key: Field name to use for deduplication

        Returns:
            Deduplicated list
        """
        seen = set()
        result = []

        for item in items:
            key_value = item.get(key)
            if key_value is not None and key_value not in seen:
                seen.add(key_value)
                result.append(item)

        return result

    @staticmethod
    def deduplicate_by_keys(
        items: list[dict[str, Any]], keys: list[str]
    ) -> list[dict[str, Any]]:
        """
        Deduplicate by combination of keys.

        Args:
            items: List of items
            keys: List of field names to combine

        Returns:
            Deduplicated list
        """
        seen = set()
        result = []

        for item in items:
            # Create tuple of key values
            key_tuple = tuple(item.get(k) for k in keys)

            if key_tuple not in seen:
                seen.add(key_tuple)
                result.append(item)

        return result

    @staticmethod
    def deduplicate_exact(
        items: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Deduplicate by exact match (all fields).

        Args:
            items: List of items

        Returns:
            Deduplicated list
        """
        seen = set()
        result = []

        for item in items:
            # Create hash of entire item
            item_hash = Deduplicator._hash_dict(item)

            if item_hash not in seen:
                seen.add(item_hash)
                result.append(item)

        return result

    @staticmethod
    def deduplicate_fuzzy(
        items: list[dict[str, Any]], key: str, threshold: float = 0.9
    ) -> list[dict[str, Any]]:
        """
        Deduplicate using fuzzy matching on a key.

        Args:
            items: List of items
            key: Field to use for fuzzy matching
            threshold: Similarity threshold (0.0-1.0)

        Returns:
            Deduplicated list
        """
        try:
            from difflib import SequenceMatcher
        except ImportError:
            # Fall back to exact matching
            return Deduplicator.deduplicate_by_key(items, key)

        result = []

        for item in items:
            value = item.get(key)
            if value is None:
                result.append(item)
                continue

            # Check similarity with existing items
            is_duplicate = False
            for existing in result:
                existing_value = existing.get(key)
                if existing_value is None:
                    continue

                similarity = SequenceMatcher(
                    None, str(value), str(existing_value)
                ).ratio()

                if similarity >= threshold:
                    is_duplicate = True
                    break

            if not is_duplicate:
                result.append(item)

        return result

    @staticmethod
    def _hash_dict(d: dict[str, Any]) -> str:
        """
        Create hash of dict for comparison.

        Args:
            d: Dict to hash

        Returns:
            Hash string
        """
        # Convert dict to sorted JSON string for consistent hashing
        json_str = json.dumps(d, sort_keys=True, default=str)
        return hashlib.md5(json_str.encode()).hexdigest()

    @staticmethod
    def find_duplicates(
        items: list[dict[str, Any]], key: str
    ) -> dict[Any, list[dict[str, Any]]]:
        """
        Find and group duplicates by key.

        Args:
            items: List of items
            key: Field to check for duplicates

        Returns:
            Dict mapping duplicate values to list of items
        """
        duplicates = {}

        for item in items:
            value = item.get(key)
            if value is not None:
                if value not in duplicates:
                    duplicates[value] = []
                duplicates[value].append(item)

        # Filter to only actual duplicates (more than one item)
        return {k: v for k, v in duplicates.items() if len(v) > 1}
