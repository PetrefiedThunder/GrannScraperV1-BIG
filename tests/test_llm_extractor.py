"""Tests for LLM-backed extraction providers."""

from types import SimpleNamespace
from typing import Any

import pytest
from bs4 import BeautifulSoup

from scraper.config.models import FieldConfig, FieldType
from scraper.extractors.llm_extractor import LLMExtractor


class FakeResponse:
    """Minimal HTTP response fake for TypeSafe tests."""

    def __init__(
        self,
        payload: dict[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.payload = payload or {}
        self.error = error

    def raise_for_status(self) -> None:
        if self.error:
            raise self.error

    def json(self) -> dict[str, Any]:
        return self.payload


class RecordingHttpClient:
    """Record requests and return a configured response."""

    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    async def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
    ) -> FakeResponse:
        self.calls.append({"url": url, "headers": headers, "json": json})
        return self.response


def typesafe_choice(
    choice: str,
    confidence: float,
    *,
    model: str = "jev-1.13.0",
) -> dict[str, Any]:
    """Build a representative TypeSafe Choice response."""
    return {
        "model": model,
        "answers": {
            "currency_value": {
                "type": "choice",
                "choice": choice,
                "probabilities": {choice: confidence},
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


@pytest.mark.asyncio
async def test_typesafe_selects_high_confidence_currency_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A confident Choice answer returns the selected candidate as a float."""
    monkeypatch.setenv("SCRAPER_LLM_PROVIDER", "typesafe")
    monkeypatch.delenv("TYPESAFE_BASE_URL", raising=False)
    monkeypatch.delenv("TYPESAFE_DEFAULT_MODEL", raising=False)
    client = RecordingHttpClient(FakeResponse(typesafe_choice("$1,315.50", 0.93)))
    extractor = LLMExtractor(
        api_key="test-key",
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
          <p>Available credit: $50.00</p>
        </main>
        """,
        "lxml",
    )

    result = await extractor.extract(soup, "total", currency_field())

    assert result == 1315.50
    assert len(client.calls) == 1
    request = client.calls[0]
    assert request["url"] == "https://api.typesafe.ai/v1/systemone"
    assert request["headers"]["Authorization"] == "Bearer test-key"
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
        api_key="test-key",
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
        api_key="test-key",
        provider="typesafe",
        http_client=client,
    )
    soup = BeautifulSoup("<p>Contact us for pricing.</p>", "lxml")

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
async def test_typesafe_skips_unsupported_field_type() -> None:
    """The first pilot is limited to single-value currency fields."""
    client = RecordingHttpClient(FakeResponse(typesafe_choice("$19.99", 0.99)))
    extractor = LLMExtractor(
        api_key="test-key",
        provider="typesafe",
        http_client=client,
    )
    soup = BeautifulSoup("<p>Price: $19.99</p>", "lxml")
    field = FieldConfig(type=FieldType.STRING, use_llm=True, default="missing")

    result = await extractor.extract(soup, "title", field)

    assert result == "missing"
    assert client.calls == []


@pytest.mark.asyncio
async def test_typesafe_service_error_returns_default(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Provider failures do not fail the scrape."""
    client = RecordingHttpClient(FakeResponse(error=RuntimeError("private-page-marker")))
    extractor = LLMExtractor(
        api_key="sensitive-test-key",
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
async def test_typesafe_malformed_response_returns_default() -> None:
    """Incomplete response JSON is treated as a provider failure."""
    client = RecordingHttpClient(FakeResponse({"answers": {}}))
    extractor = LLMExtractor(
        api_key="test-key",
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
