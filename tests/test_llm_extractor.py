"""Tests for LLM-backed extraction providers."""

import re
from types import SimpleNamespace
from typing import Any

import pytest
from bs4 import BeautifulSoup

from scraper.config.models import FieldConfig, FieldType
from scraper.extractors import llm_extractor as llm_extractor_module
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

    def __init__(
        self,
        response: FakeResponse | Exception | list[FakeResponse | Exception],
    ) -> None:
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
        response = self.responses[response_index]
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture(autouse=True)
def clear_typesafe_confidence_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep confidence behavior independent of the developer's shell."""
    monkeypatch.delenv("TYPESAFE_MIN_CONFIDENCE", raising=False)


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
    option_count = len(response_options)
    top_probability = confidence * (1.0 - (1.0 / option_count)) + (1.0 / option_count)
    remainder = (1.0 - top_probability) / len(other_options)
    probabilities = {
        option: top_probability if option == choice else remainder for option in response_options
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
async def test_typesafe_unmatched_selector_returns_default() -> None:
    """A configured selector cannot silently widen TypeSafe's data scope."""
    client = RecordingHttpClient(FakeResponse(typesafe_choice("$19.99", 0.99)))
    extractor = LLMExtractor(
        typesafe_api_key="test-key",
        provider="typesafe",
        http_client=client,
    )
    field = currency_field(-1.0).model_copy(update={"selector": ".invoice-total"})
    soup = BeautifulSoup(
        '<div class="private-profile">SSN context and balance: $19.99</div>',
        "lxml",
    )

    result = await extractor.extract(soup, "total", field)

    assert result == -1.0
    assert client.calls == []


@pytest.mark.asyncio
async def test_typesafe_keeps_valid_amounts_near_numbers_and_operators() -> None:
    """Nearby dates, percentages, labels, and ranges do not erase candidates."""
    options = ["$50", "$100", "$20", "$80", "$75", "50 USD", "__none__"]
    client = RecordingHttpClient(FakeResponse(typesafe_choice("$80", 0.99, options=options)))
    extractor = LLMExtractor(
        typesafe_api_key="test-key",
        provider="typesafe",
        http_client=client,
    )
    soup = BeautifulSoup(
        "<p>Price $50 2026 edition; $50 20% off.</p>"
        "<p>Subtotal: $100 - Discount: $20; Total $80.</p>"
        "<p>Range: $50 - $75. Invoice 123 50 USD.</p>",
        "lxml",
    )

    result = await extractor.extract(soup, "total", currency_field(-1.0))

    assert result == 80.0
    assert list(client.calls[0]["json"]["questions"]["currency_value"]["criteria"]) == options


@pytest.mark.asyncio
async def test_typesafe_preserves_element_boundaries_near_three_digit_cells() -> None:
    """Adjacent table cells cannot be mistaken for grouped currency digits."""
    options = ["$50.00", "234.56 USD", "__none__"]
    client = RecordingHttpClient(FakeResponse(typesafe_choice("$50.00", 0.99, options=options)))
    extractor = LLMExtractor(
        typesafe_api_key="test-key",
        provider="typesafe",
        http_client=client,
    )
    soup = BeautifulSoup(
        "<table><tr><td>$50.00</td><td>123</td><td>1</td><td>234.56 USD</td></tr></table>",
        "lxml",
    )

    result = await extractor.extract(soup, "total", currency_field(-1.0))

    assert result == 50.0
    assert list(client.calls[0]["json"]["questions"]["currency_value"]["criteria"]) == options


@pytest.mark.asyncio
async def test_typesafe_fails_closed_for_signs_split_across_inline_elements() -> None:
    """Ambiguous signed and range values split across inline markup are skipped."""
    client = RecordingHttpClient(
        FakeResponse(
            typesafe_choice(
                "$75.00",
                0.99,
                options=["$50.00", "$75.00", "__none__"],
            )
        )
    )
    extractor = LLMExtractor(
        typesafe_api_key="test-key",
        provider="typesafe",
        http_client=client,
    )
    soup = BeautifulSoup(
        "<p><span>-</span><span>$20.00</span></p>"
        "<p><span>(</span><span>$30.00</span><span>)</span></p>"
        "<p><span>$50.00</span><span>-</span><span>$75.00</span></p>",
        "lxml",
    )

    result = await extractor.extract(soup, "range_end", currency_field(-1.0))

    assert result == -1.0
    assert client.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("html", "fabricated_candidate"),
    [
        (
            "<p>Total: <span>$1</span><span>234</span><span>.56</span></p>",
            "$1234.56",
        ),
        ("<p>Total: <span>$ </span><span>19.99</span></p>", "$ 19.99"),
        ("<p>Total: <span>19.99 </span><span>USD</span></p>", "19.99 USD"),
    ],
)
async def test_typesafe_fails_closed_for_currency_split_across_inline_elements(
    html: str,
    fabricated_candidate: str,
) -> None:
    """Inline fragments cannot be joined into a fabricated shorter amount."""
    client = RecordingHttpClient(FakeResponse(typesafe_choice(fabricated_candidate, 0.99)))
    extractor = LLMExtractor(
        typesafe_api_key="test-key",
        provider="typesafe",
        http_client=client,
    )
    soup = BeautifulSoup(html, "lxml")

    result = await extractor.extract(soup, "total", currency_field(-1.0))

    assert result == -1.0
    assert client.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "html",
    ["<p>Total: $19\n.99</p>", "<p>Total: $1\n234.56</p>"],
)
async def test_typesafe_fails_closed_for_currency_split_by_source_newline(
    html: str,
) -> None:
    """Literal source newlines cannot truncate or regroup a currency value."""
    client = RecordingHttpClient(FakeResponse(typesafe_choice("$19", 0.99)))
    extractor = LLMExtractor(
        typesafe_api_key="test-key",
        provider="typesafe",
        http_client=client,
    )

    result = await extractor.extract(
        BeautifulSoup(html, "lxml"),
        "total",
        currency_field(-1.0),
    )

    assert result == -1.0
    assert client.calls == []


@pytest.mark.asyncio
async def test_typesafe_separates_buttons_and_semantic_grid_cells() -> None:
    """Rendered item boundaries prevent adjacent digits from being fabricated."""
    options = ["$10", "20 USD", "234 USD", "__none__"]
    client = RecordingHttpClient(FakeResponse(typesafe_choice("234 USD", 0.99, options=options)))
    extractor = LLMExtractor(
        typesafe_api_key="test-key",
        provider="typesafe",
        http_client=client,
    )
    soup = BeautifulSoup(
        "<button>$10</button><button>20 USD</button>"
        '<div role="row" style="display:grid;gap:1rem">'
        '<span role="cell">Items: 1</span><span role="cell">234 USD</span>'
        "</div>",
        "lxml",
    )

    result = await extractor.extract(soup, "total", currency_field(-1.0))

    assert result == 234.0
    criteria = client.calls[0]["json"]["questions"]["currency_value"]["criteria"]
    assert list(criteria) == options


@pytest.mark.asyncio
async def test_typesafe_does_not_promote_html_comments_to_page_text() -> None:
    """Boundary normalization cannot expose comment-only candidates."""
    client = RecordingHttpClient(FakeResponse(typesafe_choice("$19.99", 0.99)))
    extractor = LLMExtractor(
        typesafe_api_key="test-key",
        provider="typesafe",
        http_client=client,
    )
    soup = BeautifulSoup(
        "<!-- internal adjustment: $999.99 --><p>Total: $19.99</p>",
        "lxml",
    )

    result = await extractor.extract(soup, "total", currency_field(-1.0))

    assert result == 19.99
    criteria = client.calls[0]["json"]["questions"]["currency_value"]["criteria"]
    assert list(criteria) == ["$19.99", "__none__"]


@pytest.mark.asyncio
@pytest.mark.parametrize("document", ["$50.00 -", "$50.00\t+"])
async def test_typesafe_rejects_whitespace_separated_trailing_sign(
    document: str,
) -> None:
    """A separated postfix sign cannot turn a signed amount positive."""
    client = RecordingHttpClient(FakeResponse(typesafe_choice("$50.00", 0.99)))
    extractor = LLMExtractor(
        typesafe_api_key="test-key",
        provider="typesafe",
        http_client=client,
    )
    soup = BeautifulSoup(f"<p>{document}</p>", "lxml")

    result = await extractor.extract(soup, "total", currency_field(-1.0))

    assert result == -1.0
    assert client.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "html",
    [
        "<p>Balance $50.00 -</p><p>Status closed</p>",
        "<p>Balance 50.00 USD +</p><p>Status closed</p>",
    ],
)
async def test_typesafe_rejects_trailing_sign_at_block_boundary(html: str) -> None:
    """Later page blocks cannot make a postfix sign look binary."""
    client = RecordingHttpClient(FakeResponse(typesafe_choice("$50.00", 0.99)))
    extractor = LLMExtractor(
        typesafe_api_key="test-key",
        provider="typesafe",
        http_client=client,
    )

    result = await extractor.extract(
        BeautifulSoup(html, "lxml"),
        "total",
        currency_field(-1.0),
    )

    assert result == -1.0
    assert client.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("prefix", ["Invoice 1", "Paid in USD"])
async def test_typesafe_block_boundary_terminates_left_operand(prefix: str) -> None:
    """A prior block cannot convert the next block's unary minus to binary."""
    client = RecordingHttpClient(FakeResponse(typesafe_choice("$50.00", 0.99)))
    extractor = LLMExtractor(
        typesafe_api_key="test-key",
        provider="typesafe",
        http_client=client,
    )
    soup = BeautifulSoup(f"<p>{prefix}</p><p>- $50.00</p>", "lxml")

    result = await extractor.extract(soup, "total", currency_field(-1.0))

    assert result == -1.0
    assert client.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "document",
    ["Invoice 123 -$50.00", "Order 2026 + $75.00"],
)
async def test_typesafe_unrelated_number_is_not_a_binary_left_operand(
    document: str,
) -> None:
    """Identifiers and dates cannot turn a unary sign into subtraction."""
    client = RecordingHttpClient(FakeResponse(typesafe_choice("$50.00", 0.99)))
    extractor = LLMExtractor(
        typesafe_api_key="test-key",
        provider="typesafe",
        http_client=client,
    )

    result = await extractor.extract(
        BeautifulSoup(f"<p>{document}</p>", "lxml"),
        "total",
        currency_field(-1.0),
    )

    assert result == -1.0
    assert client.calls == []


@pytest.mark.asyncio
async def test_typesafe_inline_whitespace_cannot_expose_partial_decimal() -> None:
    """Whitespace around an inline boundary cannot truncate a price."""
    client = RecordingHttpClient(FakeResponse(typesafe_choice("$19", 0.99)))
    extractor = LLMExtractor(
        typesafe_api_key="test-key",
        provider="typesafe",
        http_client=client,
    )
    soup = BeautifulSoup(
        "<p><span>$19 </span><span>.99</span></p>",
        "lxml",
    )

    result = await extractor.extract(soup, "total", currency_field(-1.0))

    assert result == -1.0
    assert client.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("html", "truncated_candidate"),
    [
        ("<p><span>$1,</span><span>234.56</span></p>", "$1"),
        ("<p><span>$19.</span><span>99</span></p>", "$19"),
        ("<p><span>$1, </span><span>234.56</span></p>", "$1"),
        ("<p><span>$19. </span><span>99</span></p>", "$19"),
    ],
)
async def test_typesafe_inline_punctuation_cannot_expose_partial_amount(
    html: str,
    truncated_candidate: str,
) -> None:
    """Punctuation before an inline boundary cannot truncate an amount."""
    client = RecordingHttpClient(FakeResponse(typesafe_choice(truncated_candidate, 0.99)))
    extractor = LLMExtractor(
        typesafe_api_key="test-key",
        provider="typesafe",
        http_client=client,
    )

    result = await extractor.extract(
        BeautifulSoup(html, "lxml"),
        "total",
        currency_field(-1.0),
    )

    assert result == -1.0
    assert client.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("html", "truncated_candidate"),
    [
        (
            '<p><span style="display:inline-block">$19</span>'
            '<span style="display:inline-block">.99</span></p>',
            "$19",
        ),
        (
            '<p><span style="display:inline-flex">$1,</span>'
            '<span style="display:inline-grid">234.56</span></p>',
            "$1",
        ),
    ],
)
async def test_typesafe_inline_box_cannot_expose_partial_amount(
    html: str,
    truncated_candidate: str,
) -> None:
    """Inline CSS boxes cannot expose a prefix of one split amount."""
    client = RecordingHttpClient(FakeResponse(typesafe_choice(truncated_candidate, 0.99)))
    extractor = LLMExtractor(
        typesafe_api_key="test-key",
        provider="typesafe",
        http_client=client,
    )

    result = await extractor.extract(
        BeautifulSoup(html, "lxml"),
        "total",
        currency_field(-1.0),
    )

    assert result == -1.0
    assert client.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "document",
    [
        "-$50.00 -$75.00",
        "+$50.00 -$75.00",
        "SKU123$50.00 -$75.00",
        "-$50 USD -$75.00",
        "+$50 USD -$75.00",
        "$1\n234 USD-$75.00",
    ],
)
async def test_typesafe_invalid_left_token_cannot_authorize_signed_amount(
    document: str,
) -> None:
    """Only a valid unsigned currency operand can make a later sign binary."""
    client = RecordingHttpClient(FakeResponse(typesafe_choice("$75.00", 0.99)))
    extractor = LLMExtractor(
        typesafe_api_key="test-key",
        provider="typesafe",
        http_client=client,
    )

    result = await extractor.extract(
        BeautifulSoup(f"<p>{document}</p>", "lxml"),
        "total",
        currency_field(-1.0),
    )

    assert result == -1.0
    assert client.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("document", "overlapping_candidate"),
    [
        ("-$50USD", "50USD"),
        ("-€50EUR", "50EUR"),
        ("($50USD)", "50USD"),
    ],
)
async def test_typesafe_currency_code_cannot_overlap_signed_symbol_amount(
    document: str,
    overlapping_candidate: str,
) -> None:
    """A code-suffixed match cannot start inside a signed symbol amount."""
    client = RecordingHttpClient(FakeResponse(typesafe_choice(overlapping_candidate, 0.99)))
    extractor = LLMExtractor(
        typesafe_api_key="test-key",
        provider="typesafe",
        http_client=client,
    )

    result = await extractor.extract(
        BeautifulSoup(f"<p>{document}</p>", "lxml"),
        "total",
        currency_field(-1.0),
    )

    assert result == -1.0
    assert client.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("document", "truncated_candidate"),
    [("$19. 99 USD", "99 USD"), ("1, 234.56 USD", "234.56 USD")],
)
async def test_typesafe_currency_code_cannot_start_in_partial_amount(
    document: str,
    truncated_candidate: str,
) -> None:
    """A code-suffixed tail cannot survive rejection of its numeric prefix."""
    client = RecordingHttpClient(FakeResponse(typesafe_choice(truncated_candidate, 0.99)))
    extractor = LLMExtractor(
        typesafe_api_key="test-key",
        provider="typesafe",
        http_client=client,
    )

    result = await extractor.extract(
        BeautifulSoup(f"<p>{document}</p>", "lxml"),
        "total",
        currency_field(-1.0),
    )

    assert result == -1.0
    assert client.calls == []


@pytest.mark.asyncio
async def test_typesafe_valid_symbol_operand_can_precede_range_endpoint() -> None:
    """An unsigned symbol amount with a currency label remains a valid operand."""
    options = ["$50", "$75.00", "__none__"]
    client = RecordingHttpClient(FakeResponse(typesafe_choice("$75.00", 0.99, options=options)))
    extractor = LLMExtractor(
        typesafe_api_key="test-key",
        provider="typesafe",
        http_client=client,
    )

    result = await extractor.extract(
        BeautifulSoup("<p>$50 USD -$75.00</p>", "lxml"),
        "range_end",
        currency_field(-1.0),
    )

    assert result == 75.0
    criteria = client.calls[0]["json"]["questions"]["currency_value"]["criteria"]
    assert list(criteria) == options


def test_typesafe_signed_chain_validation_work_is_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repeated signed tokens cannot make candidate validation recurse quadratically."""
    original_has_left_operand = typesafe_currency._has_left_operand
    original_pattern = typesafe_currency._LEFT_CURRENCY_OPERAND_PATTERN
    call_count = 0
    searched_prefix_lengths: list[int] = []

    def counted(document: str, sign_index: int) -> bool:
        nonlocal call_count
        call_count += 1
        return original_has_left_operand(document, sign_index)

    class RecordingPattern:
        def search(self, prefix: str) -> re.Match[str] | None:
            searched_prefix_lengths.append(len(prefix))
            return original_pattern.search(prefix)

    monkeypatch.setattr(typesafe_currency, "_has_left_operand", counted)
    monkeypatch.setattr(
        typesafe_currency,
        "_LEFT_CURRENCY_OPERAND_PATTERN",
        RecordingPattern(),
    )
    token_count = 300
    document = " -".join("$1" for _ in range(token_count))

    candidates = typesafe_currency.TypeSafeCurrencySelector._find_candidates(document)

    assert candidates == ["$1"]
    assert call_count <= token_count * 2
    assert searched_prefix_lengths
    assert max(searched_prefix_lengths) <= typesafe_currency._MAX_LEFT_OPERAND_CHARS


@pytest.mark.parametrize(
    "document",
    [
        "$1\u2009234.56",
        "1\u2009234.56 USD",
        "$1\u2007234.56",
        "$1\u200a234.56",
        "$1\u2003234.56",
        "$1\u200b234.56",
        "1\u200b234.56 USD",
        "$1\u2060234.56",
        "$1\ufeff234.56",
        "$1\r234.56",
        "1\r234.56 USD",
        "$1,\r234.56",
        "$1\n\u200b234.56",
        "1\n\u200b234.56 USD",
    ],
)
def test_typesafe_unicode_separators_fail_closed(document: str) -> None:
    """Unicode spacing and format characters cannot expose partial amounts."""
    assert typesafe_currency.TypeSafeCurrencySelector._find_candidates(document) == []


@pytest.mark.parametrize(
    "document",
    [
        "-\u200b$50.00",
        "−\u200b$50.00",
        "‐$50.00",
        "‑$50.00",
        "‒$50.00",
        "–$50.00",
        "—$50.00",
    ],
)
def test_typesafe_unicode_signs_fail_closed(document: str) -> None:
    """Unicode dash signs and invisible sign separators remain signed."""
    assert typesafe_currency.TypeSafeCurrencySelector._find_candidates(document) == []


def test_typesafe_unicode_gaps_preserve_binary_range_dash() -> None:
    """Invisible inline gaps cannot turn a range dash into a unary sign."""
    document = "$50\u200b—\u2060$75"

    candidates = typesafe_currency.TypeSafeCurrencySelector._find_candidates(document)

    assert candidates == ["$50", "$75"]


def test_typesafe_boundary_flattening_is_non_mutating() -> None:
    """Boundary serialization cannot rewrite the caller's DOM."""
    soup = BeautifulSoup(
        "<div><p>Total: <span>$19.99</span></p>"
        "<p>Tax: <strong>$2.00</strong></p><!-- $999 --></div>",
        "lxml",
    )
    original_html = str(soup)

    flattened = llm_extractor_module._typesafe_text_with_boundaries(soup)

    assert flattened == "Total:\n$19.99\n\nTax:\n$2.00"
    assert str(soup) == original_html


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
async def test_typesafe_accepts_full_documented_choice_limit() -> None:
    """All 254 candidates plus no-match fit in one bounded Choice request."""
    candidates = [f"${value}.00" for value in range(254)]
    options = [*candidates, "__none__"]
    client = RecordingHttpClient(FakeResponse(typesafe_choice("$253.00", 0.99, options=options)))
    extractor = LLMExtractor(
        typesafe_api_key="test-key",
        provider="typesafe",
        http_client=client,
    )
    soup = BeautifulSoup(f"<p>{' '.join(candidates)}</p>", "lxml")

    result = await extractor.extract(soup, "total", currency_field(-1.0))

    assert result == 253.0
    request = client.calls[0]["json"]
    assert list(request["questions"]["currency_value"]["criteria"]) == options
    assert len(request["state"]["document"]) < 24_000


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
async def test_typesafe_explicit_empty_api_key_does_not_use_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicitly empty credential cannot fall back to an ambient key."""
    monkeypatch.setenv("TYPESAFE_API_KEY", "ambient-test-key")
    client = RecordingHttpClient(FakeResponse(typesafe_choice("$19.99", 0.99)))
    extractor = LLMExtractor(
        typesafe_api_key="",
        provider="typesafe",
        http_client=client,
    )
    soup = BeautifulSoup("<p>Total: $19.99</p>", "lxml")

    result = await extractor.extract(soup, "total", currency_field(-1.0))

    assert result == -1.0
    assert client.calls == []


@pytest.mark.asyncio
async def test_typesafe_rejects_currency_too_large_for_finite_float() -> None:
    """An oversized amount cannot become infinity downstream."""
    candidate = f"${'9' * 400}"
    client = RecordingHttpClient(FakeResponse(typesafe_choice(candidate, 0.99)))
    extractor = LLMExtractor(
        typesafe_api_key="test-key",
        provider="typesafe",
        http_client=client,
    )
    soup = BeautifulSoup(f"<p>Total: {candidate}</p>", "lxml")

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
@pytest.mark.parametrize(
    "failure",
    [FakeResponse(status_code=408), FakeResponse(status_code=503), TimeoutError()],
)
async def test_typesafe_retries_other_transient_failures(
    monkeypatch: pytest.MonkeyPatch,
    failure: FakeResponse | Exception,
) -> None:
    """Bounded retries cover transient HTTP and transport failures."""
    monkeypatch.setattr(typesafe_currency, "_RETRY_BASE_DELAY_SECONDS", 0.0)
    client = RecordingHttpClient([failure, FakeResponse(typesafe_choice("$19.99", 0.99))])
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
async def test_typesafe_boolean_confidence_threshold_fails_closed() -> None:
    """A bool cannot disable the configured uncertainty gate."""
    client = RecordingHttpClient(FakeResponse(typesafe_choice("$19.99", 0.5)))
    extractor = LLMExtractor(
        typesafe_api_key="test-key",
        provider="typesafe",
        http_client=client,
        min_confidence=False,
    )
    soup = BeautifulSoup("<p>Total: $19.99</p>", "lxml")

    result = await extractor.extract(soup, "total", currency_field(-1.0))

    assert result == -1.0


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
async def test_typesafe_rejects_confidence_inconsistent_with_probabilities() -> None:
    """A forged high confidence cannot override a nearly flat distribution."""
    client = RecordingHttpClient(
        FakeResponse(
            {
                "answers": {
                    "currency_value": {
                        "type": "choice",
                        "choice": "$19.99",
                        "confidence": 0.99,
                        "probabilities": {
                            "$19.99": 0.34,
                            "$20.00": 0.33,
                            "__none__": 0.33,
                        },
                    }
                }
            }
        )
    )
    extractor = LLMExtractor(
        typesafe_api_key="test-key",
        provider="typesafe",
        http_client=client,
        min_confidence=0.8,
    )
    soup = BeautifulSoup("<p>Total: $19.99 or $20.00</p>", "lxml")

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
