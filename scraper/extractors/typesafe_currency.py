"""Bounded TypeSafe candidate selection for currency fields."""

import logging
import os
import re
from typing import Any, Protocol

import httpx

from scraper.config.models import FieldConfig, FieldType

logger = logging.getLogger(__name__)

_CURRENCY_PATTERN = re.compile(
    r"(?<![\w.])(?:"
    r"[$€£¥]\s*-?\d+(?:,\d{3})*(?:\.\d{1,2})?"
    r"|-?\d+(?:,\d{3})*(?:\.\d{1,2})?\s*(?:USD|EUR|GBP|JPY)"
    r")(?!\w)",
    re.IGNORECASE,
)
_DEFAULT_BASE_URL = "https://api.typesafe.ai"
_DEFAULT_MODEL = "jev-latest"
_DEFAULT_MIN_CONFIDENCE = 0.8
_MAX_CHOICES = 255
_NO_MATCH = "__none__"


class TypeSafeHttpResponse(Protocol):
    """Response operations used by the TypeSafe HTTP adapter."""

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

        criteria = dict.fromkeys(candidates)
        criteria[_NO_MATCH] = "None of these candidates is the requested amount."
        payload = {
            "state": {"document": document},
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
            response = await self._post(payload)
            response.raise_for_status()
            body = response.json()
            answer = body["answers"]["currency_value"]
            choice = answer["choice"]
            confidence = answer["confidence"]

            if answer.get("type") != "choice":
                return None
            if not isinstance(choice, str):
                return None
            if isinstance(confidence, bool) or not isinstance(
                confidence, (int, float)
            ):
                return None
            if confidence < self.min_confidence:
                return None
            if choice == _NO_MATCH or choice not in candidates:
                return None

            model = str(body.get("model", "unknown"))[:80]
            logger.debug(
                "TypeSafe currency selection accepted: model=%s confidence=%.3f "
                "candidate_count=%d",
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

    async def _post(
        self,
        payload: dict[str, Any],
    ) -> TypeSafeHttpResponse:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/v1/systemone"
        if self.http_client is not None:
            return await self.http_client.post(url, headers=headers, json=payload)

        async with httpx.AsyncClient(timeout=10.0) as client:
            return await client.post(url, headers=headers, json=payload)

    @staticmethod
    def _find_candidates(document: str) -> list[str]:
        """Find unique currency strings in source order, reserving no-match."""
        candidates: list[str] = []
        seen: set[str] = set()
        for match in _CURRENCY_PATTERN.finditer(document):
            candidate = match.group().strip()
            if candidate not in seen:
                candidates.append(candidate)
                seen.add(candidate)
            if len(candidates) == _MAX_CHOICES - 1:
                break
        return candidates

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
