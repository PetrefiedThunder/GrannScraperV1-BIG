"""Tests for LLM-backed extraction providers."""

from types import SimpleNamespace
from typing import Any

import pytest
from bs4 import BeautifulSoup

from scraper.config.models import FieldConfig, FieldType
from scraper.extractors import typesafe_currency
from scraper.extractors.llm_extractor import LLMExtractor


class FakeResponse:
    """Minimal HTTP response fake for TypeSafe tests."""

    def __init__(
        self,
        payload: dict[str, Any] | None = None,
        error: Exception | None = None,
        status_code: int = 200,
    ) -> None:
        self.payload = payload or {}
        self.error = error
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.error:
            raise self.error
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict[str, Any]:
        return self.payload


class RecordingHttpClient:
    """Record requests and return a configured response."""

    def __init__(self, response: FakeResponse | list[FakeResponse]) -> None:
        self.responses = response if isinstance(response, list) else [response]
        self.calls: list[dict[str, Any]] = []

    async def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
    ) -> FakeResponse:
        self.calls.append({"url": url, "headers": headers, "json": json})
        response_index = min(len(self.calls) - 1, len(self.responses) - 1)
        return self.responses[response_index]


def typesafe_choice(
    choice: str,
    confidence: float,
    *,
    model: str = "jev-1.13.0",
    options: list[str] | None = None,
) -> dict[str, Any]:
    """Build a complete TypeSafe Choice response for the supplied options."""
    default_options = ["$19.99", "__none__"] if choice == "__none__" else [choice, "__none__"]
    response_options = list(options or default_options)
    if choice not in response_options:
        response_options.insert(0, choice)
    if "__none__" not in response_options:
        response_options.append("__none__")
    other_options = [option for option in response_options if option != choice]
    remainder = (1.0 - confidence) / len(other_options)
    probabilities = {
        option: confidence if option == choice else remainder for option in response_options
    }
    return {
        "model": model,
        "answers": {
            "currency_value": {
                "type": "choice",
                "choice": choice,
                "probabilities": probabilities,
                "confidence": confidence,
            }
        },
    }


def currency_field(default: float = 0.0) -> FieldConfig:
    """Build the bounded field configuration used by the pilot."""
    return FieldConfig(
        type=FieldType.CURRENCY,
        use_llm=True,
        llm_description="Which amount is the total due?",
        default=default,
    )


def test_unknown_llm_provider_is_rejected() -> None:
    """A provider typo cannot route content or credentials elsewhere."""
    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        LLMExtractor(api_key="test-key", provider="typesaef")


@pytest.mark.asyncio
async def test_typesafe_selects_high_confidence_currency_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A confident Choice answer returns the selected candidate as a float."""
    monkeypatch.setenv("SCRAPER_LLM_PROVIDER", "typesafe")
    monkeypatch.delenv("TYPESAFE_BASE_URL", raising=False)
    monkeypatch.delenv("TYPESAFE_DEFAULT_MODEL", raising=False)
    client = RecordingHttpClient(
        FakeResponse(
            typesafe_choice(
                "$1,315.50",
                0.93,
                options=[
                    "$1,200.00",
                    "$115.50",
                    "$1,315.50",
                    "$50.00",
                    "__none__",
                ],
            )
        )
    )
    extractor = LLMExtractor(
        api_key="anthropic-test-key",
        typesafe_api_key="typesafe-test-key",
        http_client=client,
        min_confidence=0.8,
    )
    soup = BeautifulSoup(
        """
        <main>
          <p>Subtotal: $1,200.00</p>
          <p>Tax: $115.50</p>
          <p>Total due: $1,315.50</p>
          <p>Payment summary: $1,315.50</p>
          <p>Available credit: $50.00, subject to approval</p>
        </main>
        """,
        "lxml",
    )

    result = await extractor.extract(soup, "total", currency_field())

    assert result == 1315.50
    assert len(client.calls) == 1
    request = client.calls[0]
    assert request["url"] == "https://api.typesafe.ai/v1/systemone"
    assert request["headers"]["Authorization"] == "Bearer typesafe-test-key"
    assert request["headers"]["Content-Type"] == "application/json"
    payload = request["json"]
    assert payload["model"] == "jev-latest"
    assert "Total due: $1,315.50" in payload["state"]["document"]
    question = payload["questions"]["currency_value"]
    assert question["type"] == "choice"
    assert question["instructions"] == "Which amount is the total due?"
    assert list(question["criteria"]) == [
        "$1,200.00",
        "$115.50",
        "$1,315.50",
        "$50.00",
        "__none__",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("choice", "confidence"),
    [
        ("__none__", 0.99),
        ("$19.99", 0.79),
        ("$999.99", 0.99),
        ("$19.99", 1.01),
    ],
)
async def test_typesafe_returns_default_for_no_match_or_low_confidence(
    choice: str,
    confidence: float,
) -> None:
    """No-match and answers below the configured threshold fail closed."""
    client = RecordingHttpClient(FakeResponse(typesafe_choice(choice, confidence)))
    extractor = LLMExtractor(
        typesafe_api_key="test-key",
        provider="typesafe",
        http_client=client,
        min_confidence=0.8,
    )
    soup = BeautifulSoup("<p>Total: $19.99</p>", "lxml")

    result = await extractor.extract(soup, "total", currency_field(-1.0))

    assert result == -1.0
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_typesafe_skips_request_without_currency_candidates() -> None:
    """Candidate-free content does not spend an API request."""
    client = RecordingHttpClient(FakeResponse(typesafe_choice("__none__", 0.99)))
    extractor = LLMExtractor(
        typesafe_api_key="test-key",
        provider="typesafe",
        http_client=client,
    )
    soup = BeautifulSoup(
        "<p>Unsupported: €1.234,56 and $1,23.</p>"
        "<p>Grouped: €1 234,56, $1\u00a0234.56, 1\u202f234.56 USD, "
        "€1'234.56, and 1’234.56 EUR.</p>"
        "<p>Signed values: $-50.00, -50.00 USD, - $60.00, "
        "+ $70.00, ($80.00), − $90.00, $100.00-, and $110.00+</p>",
        "lxml",
    )

    result = await extractor.extract(soup, "total", currency_field(-1.0))

    assert result == -1.0
    assert client.calls == []


@pytest.mark.asyncio
async def test_typesafe_invalid_selector_returns_default() -> None:
    """Malformed selector configuration does not escape the extractor boundary."""
    client = RecordingHttpClient(FakeResponse(typesafe_choice("$19.99", 0.99)))
    extractor = LLMExtractor(
        typesafe_api_key="test-key",
        provider="typesafe",
        http_client=client,
    )
    field = currency_field(-1.0).model_copy(update={"selector": "["})
    soup = BeautifulSoup("<p>Total: $19.99</p>", "lxml")

    result = await extractor.extract(soup, "total", field)

    assert result == -1.0
    assert client.calls == []


@pytest.mark.asyncio
async def test_typesafe_finds_candidate_after_claude_text_limit() -> None:
    """Candidate discovery is not limited by Claude's 4,000-character prompt cap."""
    client = RecordingHttpClient(FakeResponse(typesafe_choice("$19.99", 0.99)))
    extractor = LLMExtractor(
        typesafe_api_key="test-key",
        provider="typesafe",
        http_client=client,
    )
    soup = BeautifulSoup(
        f"<p>{'x' * 4100} Total due: $19.99</p>",
        "lxml",
    )

    result = await extractor.extract(soup, "total", currency_field(-1.0))

    assert result == 19.99
    state = client.calls[0]["json"]["state"]["document"]
    assert "Total due: $19.99" in state
    assert len(state) < 500


@pytest.mark.asyncio
async def test_typesafe_context_uses_exact_candidate_match() -> None:
    """A shorter candidate gets its own context, not a longer value's prefix."""
    client = RecordingHttpClient(
        FakeResponse(
            typesafe_choice(
                "$19",
                0.99,
                options=["$19.99", "$19", "__none__"],
            )
        )
    )
    extractor = LLMExtractor(
        typesafe_api_key="test-key",
        provider="typesafe",
        http_client=client,
    )
    soup = BeautifulSoup(
        f"<p>Subtotal: $19.99</p><p>{'x' * 200} Service fee: $19</p>",
        "lxml",
    )

    result = await extractor.extract(soup, "fee", currency_field(-1.0))

    assert result == 19.0
    state = client.calls[0]["json"]["state"]["document"]
    assert "Service fee: $19" in state


@pytest.mark.asyncio
async def test_typesafe_context_keeps_duplicate_value_occurrences() -> None:
    """Repeated values keep distinct labels needed for semantic selection."""
    client = RecordingHttpClient(
        FakeResponse(
            typesafe_choice(
                "$50",
                0.99,
                options=["$50", "$40", "__none__"],
            )
        )
    )
    extractor = LLMExtractor(
        typesafe_api_key="test-key",
        provider="typesafe",
        http_client=client,
    )
    soup = BeautifulSoup(
        f"<p>Refund issued: $50</p><p>{'x' * 200} Total due: $50</p>"
        f"<p>{'x' * 200} Subtotal: $40</p>",
        "lxml",
    )

    result = await extractor.extract(soup, "total", currency_field(-1.0))

    assert result == 50.0
    state = client.calls[0]["json"]["state"]["document"]
    assert "Refund issued: $50" in state
    assert "Total due: $50" in state
    assert "Subtotal: $40" in state


@pytest.mark.asyncio
async def test_typesafe_skips_request_when_choice_limit_would_overflow() -> None:
    """An incomplete candidate set is never sent for semantic selection."""
    client = RecordingHttpClient(FakeResponse(typesafe_choice("__none__", 0.99)))
    extractor = LLMExtractor(
        typesafe_api_key="test-key",
        provider="typesafe",
        http_client=client,
    )
    amounts = " ".join(f"${value}.00" for value in range(255))
    soup = BeautifulSoup(f"<p>{amounts}</p>", "lxml")

    result = await extractor.extract(soup, "total", currency_field(-1.0))

    assert result == -1.0
    assert client.calls == []


@pytest.mark.asyncio
async def test_typesafe_skips_request_without_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit opt-in still fails closed when its credential is absent."""
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    client = RecordingHttpClient(FakeResponse(typesafe_choice("$19.99", 0.99)))
    extractor = LLMExtractor(provider="typesafe", http_client=client)
    soup = BeautifulSoup("<p>Total: $19.99</p>", "lxml")

    result = await extractor.extract(soup, "total", currency_field(-1.0))

    assert result == -1.0
    assert client.calls == []


@pytest.mark.asyncio
async def test_typesafe_skips_unsupported_field_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The first pilot is limited to single-value currency fields."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    client = RecordingHttpClient(FakeResponse(typesafe_choice("$19.99", 0.99)))
    extractor = LLMExtractor(
        typesafe_api_key="test-key",
        provider="typesafe",
        http_client=client,
    )
    soup = BeautifulSoup("<p>Price: $19.99</p>", "lxml")
    field = FieldConfig(type=FieldType.STRING, use_llm=True, default="missing")

    result = await extractor.extract(soup, "title", field)

    assert result == "missing"
    assert client.calls == []


@pytest.mark.asyncio
async def test_typesafe_provider_preserves_anthropic_for_other_fields() -> None:
    """Opting into the currency pilot does not disable other LLM fields."""

    class FakeMessages:
        async def create(
            self,
            *,
            model: str,
            max_tokens: int,
            messages: list[dict[str, str]],
        ) -> SimpleNamespace:
            assert model == "claude-3-5-sonnet-20241022"
            assert max_tokens == 1024
            assert messages[0]["role"] == "user"
            return SimpleNamespace(content=[SimpleNamespace(text="Invoice title")])

    client = RecordingHttpClient(FakeResponse(typesafe_choice("$19.99", 0.99)))
    extractor = LLMExtractor(
        api_key="anthropic-test-key",
        typesafe_api_key="typesafe-test-key",
        provider="typesafe",
        http_client=client,
    )
    extractor._client = SimpleNamespace(messages=FakeMessages())
    soup = BeautifulSoup("<h1>Invoice title</h1>", "lxml")
    field = FieldConfig(type=FieldType.STRING, use_llm=True)

    result = await extractor.extract(soup, "title", field)

    assert result == "Invoice title"
    assert client.calls == []


@pytest.mark.asyncio
async def test_typesafe_service_error_returns_default(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Provider failures do not fail the scrape."""
    client = RecordingHttpClient(FakeResponse(error=RuntimeError("private-page-marker")))
    extractor = LLMExtractor(
        typesafe_api_key="sensitive-test-key",
        provider="typesafe",
        http_client=client,
    )
    soup = BeautifulSoup(
        "<p>private-page-marker Total: $19.99</p>",
        "lxml",
    )

    result = await extractor.extract(soup, "total", currency_field(-1.0))

    assert result == -1.0
    assert len(client.calls) == 1
    assert "private-page-marker" not in caplog.text
    assert "sensitive-test-key" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [429, 529])
async def test_typesafe_retries_transient_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
) -> None:
    """A transient TypeSafe rate limit is retried before failing closed."""
    monkeypatch.setattr(typesafe_currency, "_RETRY_BASE_DELAY_SECONDS", 0.0)
    client = RecordingHttpClient(
        [
            FakeResponse(status_code=status_code),
            FakeResponse(typesafe_choice("$19.99", 0.99)),
        ]
    )
    extractor = LLMExtractor(
        typesafe_api_key="test-key",
        provider="typesafe",
        http_client=client,
    )
    soup = BeautifulSoup("<p>Total: $19.99</p>", "lxml")

    result = await extractor.extract(soup, "total", currency_field(-1.0))

    assert result == 19.99
    assert len(client.calls) == 2


@pytest.mark.asyncio
async def test_typesafe_malformed_response_returns_default() -> None:
    """Incomplete response JSON is treated as a provider failure."""
    client = RecordingHttpClient(FakeResponse({"answers": {}}))
    extractor = LLMExtractor(
        typesafe_api_key="test-key",
        provider="typesafe",
        http_client=client,
    )
    soup = BeautifulSoup("<p>Total: $19.99</p>", "lxml")

    result = await extractor.extract(soup, "total", currency_field(-1.0))

    assert result == -1.0


@pytest.mark.asyncio
async def test_typesafe_missing_probabilities_returns_default() -> None:
    """A partial Choice answer does not satisfy the raw HTTP contract."""
    client = RecordingHttpClient(
        FakeResponse(
            {
                "answers": {
                    "currency_value": {
                        "type": "choice",
                        "choice": "$19.99",
                        "confidence": 0.99,
                    }
                }
            }
        )
    )
    extractor = LLMExtractor(
        typesafe_api_key="test-key",
        provider="typesafe",
        http_client=client,
    )
    soup = BeautifulSoup("<p>Total: $19.99</p>", "lxml")

    result = await extractor.extract(soup, "total", currency_field(-1.0))

    assert result == -1.0


@pytest.mark.asyncio
async def test_anthropic_remains_the_default_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The existing Claude behavior stays authoritative unless opted out."""
    monkeypatch.delenv("SCRAPER_LLM_PROVIDER", raising=False)

    class FakeMessages:
        async def create(
            self,
            *,
            model: str,
            max_tokens: int,
            messages: list[dict[str, str]],
        ) -> SimpleNamespace:
            assert model == "claude-3-5-sonnet-20241022"
            assert max_tokens == 1024
            assert messages[0]["role"] == "user"
            return SimpleNamespace(content=[SimpleNamespace(text="$19.99")])

    extractor = LLMExtractor(api_key="test-key")
    extractor._client = SimpleNamespace(messages=FakeMessages())
    soup = BeautifulSoup("<p>Total: $19.99</p>", "lxml")

    result = await extractor.extract(soup, "total", currency_field())

    assert result == 19.99
