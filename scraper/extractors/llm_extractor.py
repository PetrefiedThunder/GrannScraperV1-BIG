"""LLM extraction using Anthropic or bounded TypeSafe selection."""

import json
import logging
import math
import os
import re
from typing import Any, Optional

from bs4 import BeautifulSoup
from bs4.element import CData, NavigableString, PageElement, Tag

from scraper.config.models import FieldConfig, FieldType
from scraper.extractors.base_extractor import BaseExtractor
from scraper.extractors.typesafe_currency import (
    TypeSafeCurrencySelector,
    TypeSafeHttpClient,
)

logger = logging.getLogger(__name__)

_BLOCK_TEXT_TAG_PATTERN = re.compile(
    r"^(?:address|article|aside|blockquote|body|br|button|dd|div|dl|dt|fieldset|"
    r"figcaption|figure|footer|form|h[1-6]|header|hr|html|li|main|nav|ol|p|pre|"
    r"section|table|tbody|td|tfoot|th|thead|tr|ul)$"
)
_STRUCTURAL_TEXT_ROLES = {
    "cell",
    "columnheader",
    "gridcell",
    "row",
    "rowheader",
}
_BLOCK_DISPLAY_PATTERN = re.compile(
    r"(?:^|;)\s*display\s*:\s*(?:block|inline-block|grid|inline-grid|flex|inline-flex|table(?:-[\w-]+)?)\b",
    re.IGNORECASE,
)
_CONTAINER_DISPLAY_PATTERN = re.compile(
    r"(?:^|;)\s*display\s*:\s*(?:grid|inline-grid|flex|inline-flex|table(?:-[\w-]+)?)\b",
    re.IGNORECASE,
)
_BLOCK_BOUNDARY_MARKER = "\ue000"
_INLINE_BOUNDARY_MARKER = "\ue001"


def _is_structural_text_boundary(tag: Tag) -> bool:
    """Identify markup that renders child text as separate visual items."""
    role = str(tag.get("role", "")).lower()
    style = str(tag.get("style", ""))
    parent = tag.parent if isinstance(tag.parent, Tag) else None
    parent_role = str(parent.get("role", "")).lower() if parent else ""
    parent_style = str(parent.get("style", "")) if parent else ""
    return bool(
        _BLOCK_TEXT_TAG_PATTERN.fullmatch(tag.name or "")
        or role in _STRUCTURAL_TEXT_ROLES
        or _BLOCK_DISPLAY_PATTERN.search(style)
        or parent_role == "row"
        or _CONTAINER_DISPLAY_PATTERN.search(parent_style)
    )


def _typesafe_text_with_boundaries(snippet_soup: BeautifulSoup) -> str:
    """Flatten text without synthesizing tokens across rendered boundaries."""
    raw_parts: list[str] = []
    stack: list[tuple[PageElement, bool]] = [(snippet_soup, False)]
    seen_raw_node = False

    def append_raw_node(value: str) -> None:
        nonlocal seen_raw_node
        if seen_raw_node:
            raw_parts.append(_INLINE_BOUNDARY_MARKER)
        raw_parts.append(value)
        seen_raw_node = True

    while stack:
        node, closing_boundary = stack.pop()
        if closing_boundary:
            append_raw_node(_BLOCK_BOUNDARY_MARKER)
            continue
        if isinstance(node, Tag):
            structural_boundary = _is_structural_text_boundary(node)
            if structural_boundary:
                append_raw_node(_BLOCK_BOUNDARY_MARKER)
                stack.append((node, True))
            for child in reversed(list(node.children)):
                stack.append((child, False))
            continue
        if type(node) not in {NavigableString, CData}:
            continue

        text = str(node)
        text = text.replace(_BLOCK_BOUNDARY_MARKER, " ").replace(_INLINE_BOUNDARY_MARKER, " ")
        append_raw_node(re.sub(r"\r\n?|\n", _INLINE_BOUNDARY_MARKER, text))

    raw_text = "".join(raw_parts)
    tokens = re.split(
        f"([{_BLOCK_BOUNDARY_MARKER}{_INLINE_BOUNDARY_MARKER}])",
        raw_text,
    )
    parts: list[str] = []
    pending_boundary = 0
    previous_had_trailing_space = False
    for token in tokens:
        if token == _BLOCK_BOUNDARY_MARKER:
            pending_boundary = 2
            continue
        if token == _INLINE_BOUNDARY_MARKER:
            pending_boundary = max(pending_boundary, 1)
            continue

        has_leading_space = bool(token) and token[0].isspace()
        has_trailing_space = bool(token) and token[-1].isspace()
        normalized = " ".join(token.split())
        if not normalized:
            continue
        if parts:
            if pending_boundary == 2:
                parts.append("\n\n")
            elif pending_boundary == 1 and not (
                previous_had_trailing_space or has_leading_space
            ):
                parts.append("\n")
            else:
                parts.append(" ")
        parts.append(normalized)
        pending_boundary = 0
        previous_had_trailing_space = has_trailing_space
    return "".join(parts)


class LLMExtractor(BaseExtractor):
    """
    Provider-backed intelligent extraction.

    Uses Anthropic by default for:
    - Semantic field detection
    - Natural language queries
    - Schema inference
    - Complex pattern recognition

    An explicit TypeSafe pilot supports bounded single-value currency selection.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        typesafe_api_key: str | None = None,
        provider: str | None = None,
        http_client: TypeSafeHttpClient | None = None,
        min_confidence: float | None = None,
    ) -> None:
        """
        Initialize LLM extractor.

        Args:
            api_key: Anthropic API key (defaults to ``ANTHROPIC_API_KEY``)
            typesafe_api_key: TypeSafe API key (defaults to ``TYPESAFE_API_KEY``)
            provider: ``anthropic`` (default) or the currency-only ``typesafe`` pilot
            http_client: Optional injected HTTP client for TypeSafe
            min_confidence: Minimum TypeSafe confidence accepted by the pilot
        """
        configured_provider = (
            provider or os.getenv("SCRAPER_LLM_PROVIDER") or "anthropic"
        )
        self.provider = configured_provider.strip().lower()
        if self.provider not in {"anthropic", "typesafe"}:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self._typesafe_selector: TypeSafeCurrencySelector | None
        if self.provider == "typesafe":
            self._typesafe_selector = TypeSafeCurrencySelector(
                api_key=typesafe_api_key,
                http_client=http_client,
                min_confidence=min_confidence,
            )
        else:
            self._typesafe_selector = None
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
        Extract a field using the configured provider.

        Args:
            soup: Parsed HTML
            field_name: Field name
            field_config: Field configuration
            context: Optional context

        Returns:
            Extracted value with confidence
        """
        if (
            self.provider == "typesafe"
            and field_config.type == FieldType.CURRENCY
            and not field_config.multiple
        ):
            if self._typesafe_selector is None:
                return field_config.default
            try:
                html_snippet = self._get_relevant_html(
                    soup,
                    field_config,
                    max_chars=None,
                    require_selector_match=True,
                )
                selected = await self._typesafe_selector.select(
                    html_snippet,
                    field_name,
                    field_config,
                )
                if selected is None:
                    return field_config.default
                return self._parse_llm_response(selected, field_config)
            except Exception as error:
                logger.warning(
                    "TypeSafe extraction preparation failed (%s)",
                    type(error).__name__,
                )
                return field_config.default

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
        self,
        soup: BeautifulSoup,
        field_config: FieldConfig,
        max_chars: int | None = 4000,
        require_selector_match: bool = False,
    ) -> str:
        """
        Get relevant HTML snippet for LLM processing.

        Args:
            soup: Full page soup
            field_config: Field config
            max_chars: Optional text limit; ``None`` preserves all cleaned text
            require_selector_match: Fail if a configured selector matches nothing

        Returns:
            HTML snippet (simplified)
        """
        # If selector provided, use that section
        if field_config.selector:
            element = soup.select_one(field_config.selector)
            if element:
                html = str(element)
            elif require_selector_match:
                raise ValueError("Configured selector matched no elements")
            else:
                html = str(soup)
        else:
            html = str(soup)

        # Simplify HTML - remove scripts, styles, etc.
        snippet_soup = BeautifulSoup(html, "lxml")

        # Remove noise
        for tag in snippet_soup(["script", "style", "noscript", "svg"]):
            tag.decompose()

        # TypeSafe distinguishes rendered blocks from ambiguous inline boundaries.
        if require_selector_match:
            simplified = _typesafe_text_with_boundaries(snippet_soup)
        else:
            simplified = snippet_soup.get_text(separator=" ", strip=True)

        # Truncate if too long (keep token count reasonable)
        if max_chars is not None and len(simplified) > max_chars:
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
                    value = float(match.group().replace(",", ""))
                    return value if math.isfinite(value) else field_config.default
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
