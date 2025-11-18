"""
Tests for ML data intelligence features.
"""

import pytest
from datetime import datetime

from scraper.ml.data_intelligence import (
    DataQualityAnalyzer,
    AnomalyDetector,
    SmartCategorizer
)


@pytest.fixture
def sample_data():
    """Sample dataset for testing."""
    return [
        {
            "title": "Product 1",
            "price": 19.99,
            "description": "Great product with many features",
            "category": "Electronics",
            "stock": 100,
            "created_at": "2024-01-01T00:00:00"
        },
        {
            "title": "Product 2",
            "price": 29.99,
            "description": "Another amazing product",
            "category": "Electronics",
            "stock": 50,
            "created_at": "2024-01-02T00:00:00"
        },
        {
            "title": "Product 3",
            "price": 39.99,
            "description": "Best seller in its category",
            "category": "Home",
            "stock": 75,
            "created_at": "2024-01-03T00:00:00"
        },
    ]


@pytest.fixture
def incomplete_data():
    """Dataset with quality issues."""
    return [
        {
            "title": "Product 1",
            "price": 19.99,
            "description": "Test",
        },
        {
            "title": "",  # Empty
            "price": None,  # Missing
            "description": "Test product",
        },
        {
            "title": "Product 3",
            "price": -10.0,  # Invalid
            "description": "Test",
        },
    ]


class TestDataQualityAnalyzer:
    """Test data quality analyzer."""

    def test_analyze_complete_dataset(self, sample_data):
        """Test analysis of complete dataset."""
        analyzer = DataQualityAnalyzer()
        report = analyzer.analyze_dataset(sample_data)

        assert "quality_score" in report
        assert "metrics" in report
        assert report["quality_score"] > 0.8  # High quality data

        metrics = report["metrics"]
        assert "completeness" in metrics
        assert "consistency" in metrics
        assert "validity" in metrics
        assert "uniqueness" in metrics

    def test_analyze_incomplete_dataset(self, incomplete_data):
        """Test analysis of incomplete dataset."""
        analyzer = DataQualityAnalyzer()
        report = analyzer.analyze_dataset(incomplete_data)

        assert report["quality_score"] < 0.7  # Low quality data
        assert len(report["issues"]) > 0

        # Should detect missing values
        issues_text = str(report["issues"])
        assert any("missing" in str(issue).lower() for issue in report["issues"])

    def test_completeness_calculation(self, sample_data):
        """Test completeness metric."""
        analyzer = DataQualityAnalyzer()
        completeness = analyzer._calculate_completeness(sample_data)

        assert completeness == 1.0  # All fields present

    def test_completeness_with_missing(self, incomplete_data):
        """Test completeness with missing values."""
        analyzer = DataQualityAnalyzer()
        completeness = analyzer._calculate_completeness(incomplete_data)

        assert completeness < 1.0  # Some fields missing

    def test_uniqueness_calculation(self, sample_data):
        """Test uniqueness metric."""
        analyzer = DataQualityAnalyzer()
        uniqueness = analyzer._calculate_uniqueness(sample_data)

        assert uniqueness > 0.8  # High uniqueness

    def test_validity_calculation(self, incomplete_data):
        """Test validity metric."""
        analyzer = DataQualityAnalyzer()
        validity = analyzer._calculate_validity(incomplete_data)

        assert validity < 1.0  # Invalid price (-10.0)


class TestAnomalyDetector:
    """Test anomaly detector."""

    def test_detect_no_anomalies(self, sample_data):
        """Test detection with normal data."""
        detector = AnomalyDetector()
        report = detector.detect_anomalies(sample_data)

        assert "anomaly_score" in report
        assert "severity" in report
        assert report["severity"] in ["low", "medium", "high", "critical"]

        # Normal data should have low anomaly score
        assert report["anomaly_score"] < 0.5

    def test_detect_outliers(self):
        """Test outlier detection."""
        data = [
            {"price": 10.0, "stock": 100},
            {"price": 12.0, "stock": 120},
            {"price": 11.0, "stock": 110},
            {"price": 1000.0, "stock": 1},  # Outlier
        ]

        detector = AnomalyDetector()
        report = detector.detect_anomalies(data)

        # Should detect the outlier
        assert len(report["anomalies"]) > 0

    def test_detect_missing_fields(self):
        """Test detection of missing fields."""
        baseline_data = [
            {"title": "A", "price": 10, "stock": 100},
            {"title": "B", "price": 20, "stock": 200},
        ]

        new_data = [
            {"title": "C", "price": 30},  # Missing 'stock'
        ]

        detector = AnomalyDetector()
        detector.set_baseline(baseline_data)
        report = detector.detect_anomalies(new_data)

        # Should detect missing field
        assert any("missing" in str(a).lower() for a in report.get("anomalies", []))


class TestSmartCategorizer:
    """Test smart categorization."""

    def test_categorize_products(self):
        """Test product categorization."""
        data = [
            {"description": "Laptop computer with great specs"},
            {"description": "Desktop computer for gaming"},
            {"description": "Wireless mouse and keyboard"},
            {"description": "Office chair with lumbar support"},
            {"description": "Standing desk for home office"},
            {"description": "Monitor with 4K resolution"},
        ]

        categorizer = SmartCategorizer()
        categories = categorizer.categorize(data, n_categories=2, text_field="description")

        assert "categories" in categories
        assert len(categories["categories"]) == len(data)

        # Each item should have a category
        for cat in categories["categories"]:
            assert cat in [0, 1]  # 2 categories

    def test_suggest_category_names(self):
        """Test category name suggestion."""
        data = [
            {"description": "laptop computer notebook"},
            {"description": "desktop computer tower"},
            {"description": "chair desk furniture"},
        ]

        categorizer = SmartCategorizer()
        result = categorizer.categorize(data, n_categories=2, text_field="description")

        assert "category_names" in result
        assert len(result["category_names"]) == 2

        # Names should be meaningful
        for name in result["category_names"]:
            assert len(name) > 0

    def test_empty_dataset(self):
        """Test with empty dataset."""
        categorizer = SmartCategorizer()
        result = categorizer.categorize([], n_categories=2, text_field="description")

        assert "categories" in result
        assert len(result["categories"]) == 0


class TestIntegration:
    """Integration tests for data intelligence."""

    def test_full_quality_pipeline(self, sample_data):
        """Test complete quality analysis pipeline."""
        analyzer = DataQualityAnalyzer()
        detector = AnomalyDetector()

        # Analyze quality
        quality_report = analyzer.analyze_dataset(sample_data)
        assert quality_report["quality_score"] > 0.0

        # Detect anomalies
        anomaly_report = detector.detect_anomalies(sample_data)
        assert "anomaly_score" in anomaly_report

        # High quality data should have low anomalies
        if quality_report["quality_score"] > 0.9:
            assert anomaly_report["severity"] in ["low", "medium"]

    def test_categorization_after_quality_check(self, sample_data):
        """Test categorization after quality filtering."""
        analyzer = DataQualityAnalyzer()
        categorizer = SmartCategorizer()

        # Check quality
        quality_report = analyzer.analyze_dataset(sample_data)

        # Only categorize if quality is good
        if quality_report["quality_score"] > 0.7:
            result = categorizer.categorize(
                sample_data,
                n_categories=2,
                text_field="description"
            )

            assert len(result["categories"]) == len(sample_data)
