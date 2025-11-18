"""
LLM-powered extraction using Claude API.

Enables semantic understanding and intelligent field extraction.
"""

import json
import logging
import os
from typing import Any, Optional

from bs4 import BeautifulSoup

from scraper.config.models import FieldConfig
from scraper.extractors.base_extractor import BaseExtractor

logger = logging.getLogger(__name__)


class LLMExtractor(BaseExtractor):
    """
    Claude-powered intelligent extraction.

    Uses Claude API for:
    - Semantic field detection
    - Natural language queries
    - Schema inference
    - Complex pattern recognition
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize LLM extractor.

        Args:
            api_key: Claude API key (defaults to ANTHROPIC_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self._client = None

    def _get_client(self):
        """Lazy load Anthropic client."""
        if not self._client and self.api_key:
            try:
                from anthropic import AsyncAnthropic
                self._client = AsyncAnthropic(api_key=self.api_key)
            except ImportError:
                logger.warning(
                    "anthropic package not installed. "
                    "Install with: pip install anthropic"
                )
        return self._client

    async def extract(
        self,
        soup: BeautifulSoup,
        field_name: str,
        field_config: FieldConfig,
        context: Optional[dict[str, Any]] = None,
    ) -> Any:
        """
        Extract field using Claude AI.

        Args:
            soup: Parsed HTML
            field_name: Field name
            field_config: Field configuration
            context: Optional context

        Returns:
            Extracted value with confidence
        """
        client = self._get_client()
        if not client:
            logger.warning("LLM extraction not available (no API key)")
            return field_config.default

        try:
            # Get relevant HTML snippet
            html_snippet = self._get_relevant_html(soup, field_config)

            # Build prompt
            prompt = self._build_extraction_prompt(
                html_snippet, field_name, field_config
            )

            # Call Claude API
            response = await client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )

            # Parse response
            result = self._parse_llm_response(
                response.content[0].text, field_config
            )

            logger.debug(f"LLM extracted {field_name}: {result}")
            return result

        except Exception as e:
            logger.error(f"LLM extraction error for {field_name}: {e}")
            return field_config.default

    def _get_relevant_html(
        self, soup: BeautifulSoup, field_config: FieldConfig
    ) -> str:
        """
        Get relevant HTML snippet for LLM processing.

        Args:
            soup: Full page soup
            field_config: Field config

        Returns:
            HTML snippet (simplified)
        """
        # If selector provided, use that section
        if field_config.selector:
            element = soup.select_one(field_config.selector)
            if element:
                html = str(element)
            else:
                html = str(soup)
        else:
            html = str(soup)

        # Simplify HTML - remove scripts, styles, etc.
        from bs4 import BeautifulSoup as BS
        snippet_soup = BS(html, "lxml")

        # Remove noise
        for tag in snippet_soup(["script", "style", "noscript", "svg"]):
            tag.decompose()

        # Get text with some structure
        simplified = snippet_soup.get_text(separator=" ", strip=True)

        # Truncate if too long (keep token count reasonable)
        max_chars = 4000
        if len(simplified) > max_chars:
            simplified = simplified[:max_chars] + "..."

        return simplified

    def _build_extraction_prompt(
        self, html: str, field_name: str, field_config: FieldConfig
    ) -> str:
        """
        Build extraction prompt for Claude.

        Args:
            html: HTML snippet
            field_name: Field name
            field_config: Field configuration

        Returns:
            Prompt string
        """
        description = (
            field_config.llm_description
            or f"Extract {field_name} from the content"
        )

        prompt = f"""You are extracting structured data from HTML content.

Field to extract: {field_name}
Description: {description}
Expected type: {field_config.type.value}

Content:
{html}

Extract the requested field value. Return ONLY the extracted value, nothing else.
If the field cannot be found, return "null".

Extracted value:"""

        return prompt

    def _parse_llm_response(
        self, response_text: str, field_config: FieldConfig
    ) -> Any:
        """
        Parse LLM response to typed value.

        Args:
            response_text: Raw LLM response
            field_config: Field configuration

        Returns:
            Typed value
        """
        text = response_text.strip()

        if text.lower() in ("null", "none", "n/a", "not found"):
            return field_config.default

        # Try to parse based on field type
        from scraper.config.models import FieldType

        field_type = field_config.type

        try:
            if field_type == FieldType.INT:
                # Extract first number
                import re
                match = re.search(r"-?\d+", text.replace(",", ""))
                return int(match.group()) if match else field_config.default

            elif field_type == FieldType.FLOAT:
                import re
                match = re.search(r"-?\d+\.?\d*", text.replace(",", ""))
                return float(match.group()) if match else field_config.default

            elif field_type == FieldType.BOOL:
                return text.lower() in ("true", "yes", "1", "on")

            elif field_type == FieldType.CURRENCY:
                # Extract currency value
                import re
                match = re.search(r"[\d,]+\.?\d*", text)
                if match:
                    return float(match.group().replace(",", ""))
                return field_config.default

            else:  # STRING or others
                return text

        except Exception as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            return text


class LLMSchemaInferrer:
    """
    Infer data schema from example pages using Claude.

    Automatically detects fields, types, and selectors.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize schema inferrer.

        Args:
            api_key: Claude API key
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self._client = None

    def _get_client(self):
        """Lazy load client."""
        if not self._client and self.api_key:
            try:
                from anthropic import AsyncAnthropic
                self._client = AsyncAnthropic(api_key=self.api_key)
            except ImportError:
                logger.warning("anthropic package not installed")
        return self._client

    async def infer_schema(
        self, html: str, description: Optional[str] = None
    ) -> dict[str, dict]:
        """
        Infer schema from HTML.

        Args:
            html: HTML content
            description: Optional description of what to extract

        Returns:
            Dict of field configs
        """
        client = self._get_client()
        if not client:
            return {}

        try:
            prompt = self._build_schema_prompt(html, description)

            response = await client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )

            schema = self._parse_schema_response(response.content[0].text)
            return schema

        except Exception as e:
            logger.error(f"Schema inference error: {e}")
            return {}

    def _build_schema_prompt(
        self, html: str, description: Optional[str]
    ) -> str:
        """Build schema inference prompt."""
        desc_part = (
            f"\nWhat to extract: {description}\n" if description else ""
        )

        prompt = f"""Analyze this HTML and infer a data extraction schema.
{desc_part}
Return a JSON object where each key is a field name and each value has:
- selector: CSS selector for the field
- type: data type (string/int/float/bool/date/currency/url/email)
- description: what this field represents

HTML:
{html[:3000]}

Return ONLY valid JSON, no other text:"""

        return prompt

    def _parse_schema_response(self, response_text: str) -> dict[str, dict]:
        """Parse schema JSON from LLM."""
        try:
            # Extract JSON from response
            import re
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                schema = json.loads(json_match.group())
                return schema
            return {}
        except Exception as e:
            logger.error(f"Failed to parse schema: {e}")
            return {}
