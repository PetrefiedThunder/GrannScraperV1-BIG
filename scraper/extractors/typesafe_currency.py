"""Bounded TypeSafe candidate selection for currency fields."""

import asyncio
import logging
import math
import os
import re
from typing import Any, Protocol

import httpx

from scraper.config.models import FieldConfig, FieldType

logger = logging.getLogger(__name__)

_CURRENCY_PATTERN = re.compile(
    r"(?<![\w.,+-])(?:"
    r"[$€£¥]\s*\d+(?:,\d{3})*(?:\.\d{1,2})?"
    r"|\d+(?:,\d{3})*(?:\.\d{1,2})?\s*(?:USD|EUR|GBP|JPY)"
    r")(?!\w|[.,]\d)",
    re.IGNORECASE,
)
_DEFAULT_BASE_URL = "https://api.typesafe.ai"
_DEFAULT_MODEL = "jev-latest"
_DEFAULT_MIN_CONFIDENCE = 0.8
_MAX_CHOICES = 255
_NO_MATCH = "__none__"
_CONTEXT_RADIUS = 48
_MAX_STATE_CHARS = 24_000
_RETRYABLE_STATUS_CODES = {429, 529}
_MAX_ATTEMPTS = 3
_RETRY_BASE_DELAY_SECONDS = 0.25
_SIGN_CHARACTERS = {"-", "+", "−", "﹣", "－", "＋"}
_UNSUPPORTED_PREFIX_CHARACTERS = _SIGN_CHARACTERS | {"("}
_NUMBER_GROUP_SEPARATORS = {".", ",", "'", "’"}


def _is_unsigned_currency_match(document: str, match: re.Match[str]) -> bool:
    """Reject signed or partially matched formatted numbers."""
    prefix_index = match.start() - 1
    while prefix_index >= 0 and document[prefix_index].isspace():
        prefix_index -= 1
    if prefix_index >= 0:
        prefix_character = document[prefix_index]
        if prefix_character in _UNSUPPORTED_PREFIX_CHARACTERS:
            return False
        if match.group()[0].isdigit() and (
            prefix_character.isdigit() or prefix_character in _NUMBER_GROUP_SEPARATORS
        ):
            return False

    suffix_index = match.end()
    while suffix_index < len(document) and document[suffix_index].isspace():
        suffix_index += 1
    if suffix_index >= len(document):
        return True

    suffix_character = document[suffix_index]
    if suffix_character in _SIGN_CHARACTERS or suffix_character.isdigit():
        return False
    return not (
        suffix_character in _NUMBER_GROUP_SEPARATORS
        and suffix_index + 1 < len(document)
        and document[suffix_index + 1].isdigit()
    )


class TypeSafeHttpResponse(Protocol):
    """Response operations used by the TypeSafe HTTP adapter."""

    status_code: int

    def raise_for_status(self) -> object: ...

    def json(self) -> dict[str, Any]: ...


class TypeSafeHttpClient(Protocol):
    """Async client operations used by the TypeSafe HTTP adapter."""

    async def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
    ) -> TypeSafeHttpResponse: ...


class TypeSafeCurrencySelector:
    """Select one verbatim currency candidate with a TypeSafe Choice question."""

    def __init__(
        self,
        api_key: str | None = None,
        http_client: TypeSafeHttpClient | None = None,
        min_confidence: float | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("TYPESAFE_API_KEY")
        self.http_client = http_client
        self.base_url = os.getenv("TYPESAFE_BASE_URL", _DEFAULT_BASE_URL).rstrip("/")
        self.model = os.getenv("TYPESAFE_DEFAULT_MODEL", _DEFAULT_MODEL)
        self.min_confidence = self._resolve_min_confidence(min_confidence)

    async def select(
        self,
        document: str,
        field_name: str,
        field_config: FieldConfig,
    ) -> str | None:
        """Return an accepted candidate, or ``None`` when selection is unsafe."""
        if field_config.type != FieldType.CURRENCY or field_config.multiple:
            return None
        if not self.api_key:
            logger.warning("TypeSafe extraction not available (no API key)")
            return None

        candidates = self._find_candidates(document)
        if not candidates:
            return None
        state_document = self._build_candidate_context(document, candidates)
        if state_document is None:
            return None

        criteria = dict.fromkeys(candidates)
        criteria[_NO_MATCH] = "None of these candidates is the requested amount."
        payload = {
            "state": {"document": state_document},
            "model": self.model,
            "questions": {
                "currency_value": {
                    "type": "choice",
                    "instructions": field_config.llm_description
                    or f"Which amount is the {field_name}?",
                    "criteria": criteria,
                }
            },
        }

        try:
            response = await self._post_with_retries(payload)
            response.raise_for_status()
            body = response.json()
            answer = body["answers"]["currency_value"]
            choice = answer["choice"]
            probabilities = answer["probabilities"]
            confidence = answer["confidence"]

            if answer.get("type") != "choice":
                return None
            if not isinstance(choice, str):
                return None
            if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
                return None
            if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
                return None
            if not isinstance(probabilities, dict):
                return None
            if set(probabilities) != set(criteria):
                return None
            probability_values: list[float] = []
            for probability in probabilities.values():
                if isinstance(probability, bool) or not isinstance(probability, (int, float)):
                    return None
                if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
                    return None
                probability_values.append(float(probability))
            if not math.isclose(
                sum(probability_values),
                1.0,
                rel_tol=0.0,
                abs_tol=1e-6,
            ):
                return None
            if probabilities[choice] < max(probability_values):
                return None
            if confidence < self.min_confidence:
                return None
            if choice == _NO_MATCH or choice not in candidates:
                return None

            model = str(body.get("model", "unknown"))[:80]
            logger.debug(
                "TypeSafe currency selection accepted: model=%s confidence=%.3f candidate_count=%d",
                model,
                confidence,
                len(candidates),
            )
            return choice
        except Exception as error:
            logger.warning(
                "TypeSafe currency selection failed (%s)",
                type(error).__name__,
            )
            return None

    async def _post_with_retries(
        self,
        payload: dict[str, Any],
    ) -> TypeSafeHttpResponse:
        """Retry TypeSafe's documented transient status codes with backoff."""
        if self.http_client is not None:
            return await self._post_with_client(self.http_client, payload)

        async with httpx.AsyncClient(timeout=10.0) as client:
            return await self._post_with_client(client, payload)

    async def _post_with_client(
        self,
        client: TypeSafeHttpClient,
        payload: dict[str, Any],
    ) -> TypeSafeHttpResponse:
        for attempt in range(_MAX_ATTEMPTS):
            response = await client.post(
                f"{self.base_url}/v1/systemone",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            if response.status_code not in _RETRYABLE_STATUS_CODES or attempt == _MAX_ATTEMPTS - 1:
                return response
            await asyncio.sleep(_RETRY_BASE_DELAY_SECONDS * (2**attempt))
        raise RuntimeError("unreachable TypeSafe retry state")

    @staticmethod
    def _find_candidates(document: str) -> list[str]:
        """Find unique currency strings in source order, reserving no-match."""
        candidates: list[str] = []
        seen: set[str] = set()
        for match in _CURRENCY_PATTERN.finditer(document):
            if not _is_unsigned_currency_match(document, match):
                continue
            candidate = match.group().strip()
            if candidate not in seen:
                if len(candidates) == _MAX_CHOICES - 1:
                    return []
                candidates.append(candidate)
                seen.add(candidate)
        return candidates

    @staticmethod
    def _build_candidate_context(
        document: str,
        candidates: list[str],
    ) -> str | None:
        """Keep bounded source context around each candidate, including page tails."""
        snippets: list[str] = []
        candidate_set = set(candidates)
        seen_snippets: set[str] = set()
        state_length = 0
        for match in _CURRENCY_PATTERN.finditer(document):
            if not _is_unsigned_currency_match(document, match):
                continue
            candidate = match.group().strip()
            if candidate not in candidate_set:
                continue
            start = max(0, match.start() - _CONTEXT_RADIUS)
            end = min(len(document), match.end() + _CONTEXT_RADIUS)
            snippet = document[start:end].strip()
            if snippet in seen_snippets:
                continue
            separator_length = len("\n...\n") if snippets else 0
            if state_length + separator_length + len(snippet) > _MAX_STATE_CHARS:
                return None
            snippets.append(snippet)
            seen_snippets.add(snippet)
            state_length += separator_length + len(snippet)
        return "\n...\n".join(snippets) if snippets else None

    @staticmethod
    def _resolve_min_confidence(value: float | None) -> float:
        raw_value: float | str = (
            value
            if value is not None
            else os.getenv(
                "TYPESAFE_MIN_CONFIDENCE",
                str(_DEFAULT_MIN_CONFIDENCE),
            )
        )
        try:
            confidence = float(raw_value)
        except (TypeError, ValueError):
            logger.warning(
                "Invalid TYPESAFE_MIN_CONFIDENCE; using %.1f",
                _DEFAULT_MIN_CONFIDENCE,
            )
            return _DEFAULT_MIN_CONFIDENCE

        if 0.0 <= confidence <= 1.0:
            return confidence

        logger.warning(
            "TYPESAFE_MIN_CONFIDENCE must be between 0 and 1; using %.1f",
            _DEFAULT_MIN_CONFIDENCE,
        )
        return _DEFAULT_MIN_CONFIDENCE
