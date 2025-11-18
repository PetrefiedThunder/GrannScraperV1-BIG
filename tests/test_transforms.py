"""
Tests for data transforms.
"""

from scraper.transforms.cleaning import DataCleaner
from scraper.transforms.type_inference import TypeInferrer
from scraper.transforms.deduplication import Deduplicator


def test_clean_text():
    """Test text cleaning."""
    text = "  Hello   World  \n\n"
    cleaned = DataCleaner.clean_text(text)
    assert cleaned == "Hello World"


def test_clean_text_none():
    """Test cleaning None value."""
    assert DataCleaner.clean_text(None) is None


def test_extract_currency():
    """Test currency extraction."""
    assert DataCleaner.extract_currency("$99.99") == 99.99
    assert DataCleaner.extract_currency("€1,234.56") == 1234.56
    assert DataCleaner.extract_currency("Price: $50") == 50.0


def test_clean_url():
    """Test URL cleaning."""
    url = "https://example.com/page?utm_source=test&foo=bar"
    cleaned = DataCleaner.clean_url(url)
    assert "utm_source" not in cleaned
    assert "foo=bar" in cleaned


def test_standardize_phone():
    """Test phone number standardization."""
    assert DataCleaner.standardize_phone("1234567890") == "(123) 456-7890"
    assert DataCleaner.standardize_phone("(123) 456-7890") == "(123) 456-7890"


def test_clean_email():
    """Test email cleaning."""
    assert DataCleaner.clean_email("Test@Example.COM") == "test@example.com"
    assert DataCleaner.clean_email("invalid") is None


def test_remove_duplicates():
    """Test duplicate removal."""
    items = [1, 2, 3, 2, 4, 1, 5]
    result = DataCleaner.remove_duplicates(items)
    assert result == [1, 2, 3, 4, 5]


def test_infer_type_string():
    """Test type inference for strings."""
    assert TypeInferrer.infer_type("hello") == "string"


def test_infer_type_int():
    """Test type inference for integers."""
    assert TypeInferrer.infer_type("123") == "int"
    assert TypeInferrer.infer_type("1,234") == "int"


def test_infer_type_float():
    """Test type inference for floats."""
    assert TypeInferrer.infer_type("123.45") == "float"


def test_infer_type_bool():
    """Test type inference for booleans."""
    assert TypeInferrer.infer_type("true") == "bool"
    assert TypeInferrer.infer_type("yes") == "bool"
    assert TypeInferrer.infer_type("false") == "bool"


def test_infer_type_url():
    """Test type inference for URLs."""
    assert TypeInferrer.infer_type("https://example.com") == "url"
    assert TypeInferrer.infer_type("http://test.org") == "url"


def test_infer_type_email():
    """Test type inference for emails."""
    assert TypeInferrer.infer_type("user@example.com") == "email"


def test_infer_type_currency():
    """Test type inference for currency."""
    assert TypeInferrer.infer_type("$99.99") == "currency"
    assert TypeInferrer.infer_type("€50") == "currency"


def test_convert_type_int():
    """Test type conversion to int."""
    assert TypeInferrer.convert_type("123", "int") == 123
    assert TypeInferrer.convert_type("1,234", "int") == 1234


def test_convert_type_float():
    """Test type conversion to float."""
    assert TypeInferrer.convert_type("123.45", "float") == 123.45


def test_convert_type_bool():
    """Test type conversion to bool."""
    assert TypeInferrer.convert_type("true", "bool") is True
    assert TypeInferrer.convert_type("false", "bool") is False


def test_infer_schema():
    """Test schema inference from items."""
    items = [
        {"name": "Alice", "age": "30", "email": "alice@example.com"},
        {"name": "Bob", "age": "25", "email": "bob@example.com"},
    ]

    schema = TypeInferrer.infer_schema(items)

    assert schema["name"] == "string"
    assert schema["age"] == "int"
    assert schema["email"] == "email"


def test_deduplicate_by_key():
    """Test deduplication by key."""
    items = [
        {"id": 1, "name": "Alice"},
        {"id": 2, "name": "Bob"},
        {"id": 1, "name": "Alice Duplicate"},
    ]

    result = Deduplicator.deduplicate_by_key(items, "id")

    assert len(result) == 2
    assert result[0]["id"] == 1
    assert result[1]["id"] == 2


def test_deduplicate_exact():
    """Test exact deduplication."""
    items = [
        {"name": "Alice", "age": 30},
        {"name": "Bob", "age": 25},
        {"name": "Alice", "age": 30},  # Exact duplicate
    ]

    result = Deduplicator.deduplicate_exact(items)

    assert len(result) == 2


def test_find_duplicates():
    """Test finding duplicates."""
    items = [
        {"id": 1, "name": "Alice"},
        {"id": 2, "name": "Bob"},
        {"id": 1, "name": "Alice2"},
        {"id": 1, "name": "Alice3"},
    ]

    duplicates = Deduplicator.find_duplicates(items, "id")

    assert 1 in duplicates
    assert len(duplicates[1]) == 3
    assert 2 not in duplicates
