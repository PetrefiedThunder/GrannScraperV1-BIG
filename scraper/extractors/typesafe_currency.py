"""Bounded TypeSafe candidate selection for currency fields."""

import asyncio
import logging
import math
import os
import re
import unicodedata
from typing import Any, Protocol

import httpx

from scraper.config.models import FieldConfig, FieldType

logger = logging.getLogger(__name__)

_CURRENCY_PATTERN = re.compile(
    r"(?<![\w.,$€£¥])(?:"
    r"[$€£¥][ \t\u00a0\u202f]*\d+(?:,\d{3})*(?:\.\d{1,2})?"
    r"|\d+(?:,\d{3})*(?:\.\d{1,2})?[ \t\u00a0\u202f]*(?:USD|EUR|GBP|JPY)"
    r")(?!\w|[.,]\d)",
    re.IGNORECASE,
)
_LEFT_CURRENCY_OPERAND_PATTERN = re.compile(
    r"(?<![\w.,$€£¥])(?:"
    r"[$€£¥][ \t\u00a0\u202f]*\d+(?:,\d{3})*(?:\.\d{1,2})?"
    r"(?:[ \t\u00a0\u202f]*(?:USD|EUR|GBP|JPY))?"
    r"|\d+(?:,\d{3})*(?:\.\d{1,2})?[ \t\u00a0\u202f]*(?:USD|EUR|GBP|JPY))"
    r"[ \t\u00a0\u202f]*\Z",
    re.IGNORECASE,
)
_DEFAULT_BASE_URL = "https://api.typesafe.ai"
_DEFAULT_MODEL = "jev-latest"
_DEFAULT_MIN_CONFIDENCE = 0.8
_MAX_CHOICES = 255
_MAX_CURRENCY_DIGITS = 308
_MAX_LEFT_OPERAND_CHARS = (_MAX_CURRENCY_DIGITS * 2) + 32
_NO_MATCH = "__none__"
_CONTEXT_RADIUS = 48
_MAX_STATE_CHARS = 24_000
_RETRYABLE_STATUS_CODES = {408, 429}
_MAX_ATTEMPTS = 3
_RETRY_BASE_DELAY_SECONDS = 0.25
_SIGN_CHARACTERS = {"-", "+", "−", "﹣", "－", "＋"}
_NUMBER_GROUP_SEPARATORS = {".", ",", "'", "’"}


def _is_currency_gap(character: str) -> bool:
    """Treat Unicode whitespace and invisible format controls as boundaries."""
    return character.isspace() or unicodedata.category(character) == "Cf"


def _is_inline_currency_gap(character: str) -> bool:
    """Return whether a boundary can occur inside one rendered text line."""
    return character != "\n" and _is_currency_gap(character)


def _is_sign_character(character: str) -> bool:
    """Recognize explicit signs and every Unicode dash-punctuation character."""
    return character in _SIGN_CHARACTERS or unicodedata.category(character) == "Pd"


def _consume_inline_gap_forward(
    document: str,
    start: int,
) -> tuple[int, bool, bool] | None:
    """Consume inline gaps, allowing one inline-boundary newline but not a block."""
    cursor = start
    saw_gap = False
    saw_format_control = False
    saw_newline = False
    while cursor < len(document):
        character = document[cursor]
        if character == "\n":
            if saw_newline:
                return None
            saw_newline = True
        elif _is_inline_currency_gap(character):
            saw_format_control |= unicodedata.category(character) == "Cf"
        else:
            break
        saw_gap = True
        cursor += 1
    if not saw_gap:
        return None
    return cursor, saw_format_control, saw_newline


def _has_spaced_group_prefix(document: str, start: int) -> bool:
    """Check only the adjacent inline-spaced token for 1-3 leading digits."""
    cursor = start - 1
    if cursor < 0 or not _is_inline_currency_gap(document[cursor]):
        return False
    while cursor >= 0 and _is_inline_currency_gap(document[cursor]):
        cursor -= 1

    digit_count = 0
    while cursor >= 0 and document[cursor].isdigit():
        digit_count += 1
        if digit_count > 3:
            return False
        cursor -= 1
    return digit_count > 0


def _has_separated_numeric_prefix(document: str, start: int) -> bool:
    """Detect a short numeric fragment before spaced grouping punctuation."""
    cursor = start - 1
    if cursor < 0 or not _is_inline_currency_gap(document[cursor]):
        return False
    while cursor >= 0 and _is_inline_currency_gap(document[cursor]):
        cursor -= 1
    if cursor < 0 or document[cursor] not in _NUMBER_GROUP_SEPARATORS:
        return False
    cursor -= 1
    while cursor >= 0 and _is_inline_currency_gap(document[cursor]):
        cursor -= 1
    return cursor >= 0 and document[cursor].isdigit()


def _has_invisible_numeric_prefix(document: str, start: int) -> bool:
    """Detect a numeric or currency prefix hidden by Unicode format controls."""
    cursor = start - 1
    saw_format_control = False
    while cursor >= 0 and _is_inline_currency_gap(document[cursor]):
        saw_format_control |= unicodedata.category(document[cursor]) == "Cf"
        cursor -= 1
    return bool(
        saw_format_control
        and cursor >= 0
        and (
            document[cursor].isdigit()
            or document[cursor] in _NUMBER_GROUP_SEPARATORS
            or document[cursor] in "$€£¥"
        )
    )


def _has_partial_numeric_prefix(document: str, start: int, candidate: str) -> bool:
    """Reject a code-suffixed tail split from a preceding numeric fragment."""
    if not candidate or not candidate[0].isdigit():
        return False
    if _has_inline_numeric_prefix(document, start):
        return True
    if _has_invisible_numeric_prefix(document, start):
        return True

    leading_digits = re.match(r"\d+", candidate)
    if leading_digits is None or len(leading_digits.group()) > 3:
        return False
    if len(leading_digits.group()) == 3 and _has_spaced_group_prefix(document, start):
        return True
    return _has_separated_numeric_prefix(document, start)


def _has_left_operand(document: str, sign_index: int) -> bool:
    """Return whether a sign follows a complete supported currency operand."""
    operand_end = sign_index
    while operand_end > 0 and _is_inline_currency_gap(document[operand_end - 1]):
        operand_end -= 1
    window_start = max(0, operand_end - _MAX_LEFT_OPERAND_CHARS)
    prefix = document[window_start:operand_end]
    match = _LEFT_CURRENCY_OPERAND_PATTERN.search(prefix)
    if match is None:
        return False
    if sum(character.isdigit() for character in match.group()) > _MAX_CURRENCY_DIGITS:
        return False
    if _has_partial_numeric_prefix(prefix, match.start(), match.group()):
        return False

    cursor = match.start() - 1
    newline_count = 0
    while cursor >= 0 and _is_currency_gap(prefix[cursor]):
        if prefix[cursor] == "\n":
            newline_count += 1
            if newline_count == 2:
                return True
        cursor -= 1
    return cursor < 0 or (not _is_sign_character(prefix[cursor]) and prefix[cursor] != "(")


def _has_right_context(document: str, sign_index: int) -> bool:
    """Return whether a sign is followed by another value or separator label."""
    cursor = sign_index + 1
    while cursor < len(document) and _is_inline_currency_gap(document[cursor]):
        cursor += 1
    return cursor < len(document) and (document[cursor].isalnum() or document[cursor] in "$€£¥(")


def _has_inline_numeric_prefix(document: str, start: int) -> bool:
    """Detect a numeric fragment immediately before one inline boundary."""
    cursor = start - 1
    saw_newline = False
    while cursor >= 0:
        character = document[cursor]
        if character == "\n":
            if saw_newline:
                return False
            saw_newline = True
        elif not _is_inline_currency_gap(character):
            break
        cursor -= 1
    if not saw_newline or cursor < 0:
        return False
    previous = document[cursor]
    return previous.isdigit() or previous in _NUMBER_GROUP_SEPARATORS | {"$", "€", "£", "¥"}


def _has_spaced_numeric_suffix(document: str, end: int) -> bool:
    """Detect a numeric continuation separated by inline Unicode boundaries."""
    cursor = end
    separator_before_gap = False
    if cursor < len(document) and document[cursor] in _NUMBER_GROUP_SEPARATORS:
        separator_before_gap = True
        cursor += 1
    consumed_gap = _consume_inline_gap_forward(document, cursor)
    if consumed_gap is None:
        return False
    cursor, saw_format_control, saw_newline = consumed_gap
    if cursor >= len(document):
        return False

    if document[cursor].isdigit():
        digit_start = cursor
        while cursor < len(document) and document[cursor].isdigit():
            cursor += 1
        digit_count = cursor - digit_start
        if saw_format_control or saw_newline:
            return True
        if separator_before_gap:
            return digit_count <= 3
        return digit_count == 3

    if document[cursor] not in _NUMBER_GROUP_SEPARATORS:
        return False
    cursor += 1
    while cursor < len(document) and _is_inline_currency_gap(document[cursor]):
        saw_format_control |= unicodedata.category(document[cursor]) == "Cf"
        cursor += 1
    digit_start = cursor
    while cursor < len(document) and document[cursor].isdigit():
        cursor += 1
    digit_count = cursor - digit_start
    return digit_count > 0 if saw_format_control or saw_newline else 1 <= digit_count <= 3


def _has_inline_numeric_suffix(document: str, end: int) -> bool:
    """Detect a numeric continuation immediately after one inline boundary."""
    if _has_spaced_numeric_suffix(document, end):
        return True
    boundary = end
    if boundary < len(document) and document[boundary] in _NUMBER_GROUP_SEPARATORS:
        boundary += 1
    if boundary >= len(document) or document[boundary] != "\n":
        return False
    continuation = boundary + 1
    if continuation >= len(document) or document[continuation] == "\n":
        return False
    if document[continuation].isdigit():
        return True
    return (
        document[continuation] in _NUMBER_GROUP_SEPARATORS
        and continuation + 1 < len(document)
        and document[continuation + 1].isdigit()
    )


def _is_unsigned_currency_match(document: str, match: re.Match[str]) -> bool:
    """Reject signed or partially matched formatted numbers."""
    candidate = match.group()
    if _has_partial_numeric_prefix(document, match.start(), candidate):
        return False
    prefix_index = match.start() - 1
    if prefix_index >= 0:
        prefix_character = document[prefix_index]
        if prefix_character == "(":
            return False
        if _is_sign_character(prefix_character) and not _has_left_operand(document, prefix_index):
            return False
        if candidate[0].isdigit() and (
            prefix_character.isdigit() or prefix_character in _NUMBER_GROUP_SEPARATORS
        ):
            return False

    if prefix_index >= 0 and _is_currency_gap(document[prefix_index]):
        previous_nonspace = prefix_index
        while previous_nonspace >= 0 and _is_currency_gap(document[previous_nonspace]):
            previous_nonspace -= 1
        if previous_nonspace >= 0:
            prefix_character = document[previous_nonspace]
            if prefix_character == "(":
                return False
            if _is_sign_character(prefix_character) and not _has_left_operand(
                document, previous_nonspace
            ):
                return False

    suffix_index = match.end()
    if suffix_index >= len(document):
        return True
    if candidate[0] in "$€£¥" and _has_inline_numeric_suffix(document, suffix_index):
        return False
    suffix_character = document[suffix_index]
    if suffix_character.isdigit():
        return False
    if _is_sign_character(suffix_character) and not _has_right_context(document, suffix_index):
        return False
    if _is_currency_gap(suffix_character):
        next_nonspace = suffix_index
        while next_nonspace < len(document) and _is_currency_gap(document[next_nonspace]):
            next_nonspace += 1
        if (
            next_nonspace < len(document)
            and _is_sign_character(document[next_nonspace])
            and not _has_right_context(document, next_nonspace)
        ):
            return False
    return not (
        suffix_character in _NUMBER_GROUP_SEPARATORS
        and suffix_index + 1 < len(document)
        and document[suffix_index + 1].isdigit()
    )


def _choice_confidence_floor(probabilities: list[float]) -> float:
    """Calculate a conservative normalized top-probability confidence floor."""
    option_count = len(probabilities)
    if option_count == 1:
        return 1.0
    uniform_probability = 1.0 / option_count
    return (max(probabilities) - uniform_probability) / (1.0 - uniform_probability)


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
        self.api_key = os.getenv("TYPESAFE_API_KEY") if api_key is None else api_key
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
            confidence_floor = _choice_confidence_floor(probability_values)
            if probabilities[choice] < max(probability_values):
                return None
            if confidence < self.min_confidence or confidence_floor < self.min_confidence:
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
            try:
                response = await client.post(
                    f"{self.base_url}/v1/systemone",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
            except (httpx.TransportError, TimeoutError):
                if attempt == _MAX_ATTEMPTS - 1:
                    raise
                await asyncio.sleep(_RETRY_BASE_DELAY_SECONDS * (2**attempt))
                continue
            retryable_status = (
                response.status_code in _RETRYABLE_STATUS_CODES
                or 500 <= response.status_code <= 599
            )
            if not retryable_status or attempt == _MAX_ATTEMPTS - 1:
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
            if sum(character.isdigit() for character in candidate) > _MAX_CURRENCY_DIGITS:
                continue
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
        ranges: list[tuple[int, int]] = []
        candidate_set = set(candidates)
        for match in _CURRENCY_PATTERN.finditer(document):
            if not _is_unsigned_currency_match(document, match):
                continue
            candidate = match.group().strip()
            if candidate not in candidate_set:
                continue
            start = max(0, match.start() - _CONTEXT_RADIUS)
            end = min(len(document), match.end() + _CONTEXT_RADIUS)
            if ranges and start <= ranges[-1][1]:
                previous_start, previous_end = ranges[-1]
                ranges[-1] = (previous_start, max(previous_end, end))
            else:
                ranges.append((start, end))

        snippets: list[str] = []
        seen_snippets: set[str] = set()
        state_length = 0
        for start, end in ranges:
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
        if isinstance(raw_value, bool):
            logger.warning(
                "Invalid TYPESAFE_MIN_CONFIDENCE; using %.1f",
                _DEFAULT_MIN_CONFIDENCE,
            )
            return _DEFAULT_MIN_CONFIDENCE
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
