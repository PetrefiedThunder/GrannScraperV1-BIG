"""
Advanced ML & AI data intelligence layer.

Goes beyond extraction to provide insights, quality scoring,
anomaly detection, and intelligent data processing.
"""

import logging
import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class DataQualityAnalyzer:
    """
    Analyze and score data quality automatically.

    Detects issues like:
    - Missing values
    - Outliers
    - Inconsistent formatting
    - Duplicate entries
    - Data drift over time
    """

    def __init__(self):
        self.baseline: Optional[Dict] = None

    def analyze_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Comprehensive data quality analysis.

        Returns quality score and detailed metrics.
        """
        if not items:
            return {'quality_score': 0, 'issues': ['No data']}

        metrics = {
            'total_items': len(items),
            'completeness': self._calculate_completeness(items),
            'consistency': self._calculate_consistency(items),
            'validity': self._calculate_validity(items),
            'uniqueness': self._calculate_uniqueness(items),
            'timeliness': self._calculate_timeliness(items),
        }

        # Overall quality score (0-100)
        weights = {
            'completeness': 0.25,
            'consistency': 0.20,
            'validity': 0.25,
            'uniqueness': 0.20,
            'timeliness': 0.10,
        }

        quality_score = sum(
            metrics[key] * weights[key]
            for key in weights.keys()
        )

        # Identify issues
        issues = self._identify_issues(metrics, items)

        return {
            'quality_score': round(quality_score, 2),
            'metrics': metrics,
            'issues': issues,
            'recommendations': self._generate_recommendations(metrics, issues),
        }

    def _calculate_completeness(self, items: List[Dict]) -> float:
        """Calculate data completeness (0-100)."""
        if not items:
            return 0

        # Count non-null values
        total_cells = 0
        filled_cells = 0

        for item in items:
            for value in item.values():
                total_cells += 1
                if value is not None and value != '' and value != []:
                    filled_cells += 1

        return (filled_cells / total_cells * 100) if total_cells > 0 else 0

    def _calculate_consistency(self, items: List[Dict]) -> float:
        """Calculate format consistency (0-100)."""
        if len(items) < 2:
            return 100

        consistency_scores = []

        # Check each field
        all_keys = set()
        for item in items:
            all_keys.update(item.keys())

        for key in all_keys:
            values = [item.get(key) for item in items if item.get(key) is not None]
            if not values:
                continue

            # Check type consistency
            types = [type(v).__name__ for v in values]
            type_consistency = Counter(types).most_common(1)[0][1] / len(types)

            # Check format consistency for strings
            if isinstance(values[0], str):
                format_patterns = self._detect_format_patterns(values)
                format_consistency = max(
                    count / len(values)
                    for count in format_patterns.values()
                ) if format_patterns else 1.0
            else:
                format_consistency = 1.0

            consistency_scores.append((type_consistency + format_consistency) / 2)

        return (sum(consistency_scores) / len(consistency_scores) * 100) if consistency_scores else 100

    def _detect_format_patterns(self, values: List[str]) -> Counter:
        """Detect common format patterns in strings."""
        patterns = []

        for value in values:
            # Detect pattern (digits, letters, special chars)
            pattern = re.sub(r'\d+', 'N', value)  # Numbers -> N
            pattern = re.sub(r'[a-zA-Z]+', 'A', pattern)  # Letters -> A
            patterns.append(pattern)

        return Counter(patterns)

    def _calculate_validity(self, items: List[Dict]) -> float:
        """Calculate data validity (0-100)."""
        validity_scores = []

        for item in items:
            item_score = 0
            checks = 0

            for key, value in item.items():
                if value is None or value == '':
                    continue

                checks += 1

                # Check based on field name/type
                if 'email' in key.lower():
                    if self._is_valid_email(str(value)):
                        item_score += 1
                elif 'url' in key.lower() or 'link' in key.lower():
                    if self._is_valid_url(str(value)):
                        item_score += 1
                elif 'phone' in key.lower():
                    if self._is_valid_phone(str(value)):
                        item_score += 1
                elif 'price' in key.lower() or 'cost' in key.lower():
                    if self._is_valid_price(value):
                        item_score += 1
                else:
                    # Generic validation - not empty, reasonable length
                    if len(str(value).strip()) > 0 and len(str(value)) < 10000:
                        item_score += 1

            validity_scores.append((item_score / checks * 100) if checks > 0 else 100)

        return sum(validity_scores) / len(validity_scores) if validity_scores else 100

    def _calculate_uniqueness(self, items: List[Dict]) -> float:
        """Calculate data uniqueness (0-100)."""
        if len(items) < 2:
            return 100

        # Create hash of each item
        hashes = []
        for item in items:
            # Sort keys for consistent hashing
            item_str = str(sorted(item.items()))
            hashes.append(hash(item_str))

        unique_count = len(set(hashes))
        return (unique_count / len(items) * 100)

    def _calculate_timeliness(self, items: List[Dict]) -> float:
        """Calculate data timeliness (0-100)."""
        # Look for date fields
        date_fields = []

        for item in items:
            for key, value in item.items():
                if any(word in key.lower() for word in ['date', 'time', 'created', 'updated', 'published']):
                    try:
                        if isinstance(value, str):
                            from dateutil import parser
                            parsed = parser.parse(value)
                            date_fields.append(parsed)
                    except:
                        pass

        if not date_fields:
            return 100  # No date fields to check

        # Calculate how recent the data is
        now = datetime.utcnow()
        avg_age_days = sum(
            (now - date).days for date in date_fields
        ) / len(date_fields)

        # Score based on age (fresher = better)
        if avg_age_days < 1:
            return 100
        elif avg_age_days < 7:
            return 90
        elif avg_age_days < 30:
            return 75
        elif avg_age_days < 90:
            return 60
        elif avg_age_days < 365:
            return 40
        else:
            return 20

    def _identify_issues(self, metrics: Dict, items: List[Dict]) -> List[str]:
        """Identify specific data quality issues."""
        issues = []

        if metrics['completeness'] < 80:
            issues.append(f"Low completeness ({metrics['completeness']:.1f}%) - many missing values")

        if metrics['consistency'] < 70:
            issues.append(f"Poor consistency ({metrics['consistency']:.1f}%) - mixed formats detected")

        if metrics['validity'] < 80:
            issues.append(f"Validity concerns ({metrics['validity']:.1f}%) - invalid data detected")

        if metrics['uniqueness'] < 90:
            duplicate_pct = 100 - metrics['uniqueness']
            issues.append(f"Duplicates detected ({duplicate_pct:.1f}% of data)")

        # Check for outliers in numeric fields
        outlier_fields = self._detect_outliers(items)
        if outlier_fields:
            issues.append(f"Outliers detected in fields: {', '.join(outlier_fields)}")

        return issues

    def _detect_outliers(self, items: List[Dict]) -> List[str]:
        """Detect outliers in numeric fields using IQR method."""
        outlier_fields = []

        # Get all numeric fields
        numeric_fields = defaultdict(list)

        for item in items:
            for key, value in item.items():
                if isinstance(value, (int, float)):
                    numeric_fields[key].append(value)

        # Check each numeric field for outliers
        for field, values in numeric_fields.items():
            if len(values) < 4:
                continue

            values_array = np.array(values)
            q1 = np.percentile(values_array, 25)
            q3 = np.percentile(values_array, 75)
            iqr = q3 - q1

            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr

            outliers = [v for v in values if v < lower_bound or v > upper_bound]

            if len(outliers) / len(values) > 0.05:  # More than 5% outliers
                outlier_fields.append(field)

        return outlier_fields

    def _generate_recommendations(self, metrics: Dict, issues: List[str]) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []

        if metrics['completeness'] < 80:
            recommendations.append(
                "Improve completeness:\n"
                "  • Check if selectors are correct\n"
                "  • Verify data is present on source pages\n"
                "  • Consider using default values for optional fields"
            )

        if metrics['consistency'] < 70:
            recommendations.append(
                "Improve consistency:\n"
                "  • Add data cleaning transformations\n"
                "  • Standardize date/number formats\n"
                "  • Use type conversion in field configs"
            )

        if metrics['validity'] < 80:
            recommendations.append(
                "Improve validity:\n"
                "  • Add validation rules to field configs\n"
                "  • Use regex patterns to extract clean data\n"
                "  • Filter out invalid entries"
            )

        if metrics['uniqueness'] < 90:
            recommendations.append(
                "Remove duplicates:\n"
                "  • Use deduplication by key fields\n"
                "  • Check if pagination is working correctly\n"
                "  • Verify URL generation isn't repeating"
            )

        return recommendations

    def _is_valid_email(self, value: str) -> bool:
        """Check if string is valid email."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, value))

    def _is_valid_url(self, value: str) -> bool:
        """Check if string is valid URL."""
        return value.startswith(('http://', 'https://'))

    def _is_valid_phone(self, value: str) -> bool:
        """Check if string is valid phone number."""
        digits = re.sub(r'\D', '', value)
        return 10 <= len(digits) <= 15

    def _is_valid_price(self, value: Any) -> bool:
        """Check if value is valid price."""
        if isinstance(value, (int, float)):
            return value >= 0
        if isinstance(value, str):
            # Extract numeric part
            numeric = re.sub(r'[^\d.]', '', value)
            try:
                price = float(numeric)
                return price >= 0
            except:
                return False
        return False


class AnomalyDetector:
    """
    Detect anomalies in scraped data.

    Useful for:
    - Detecting when sites change structure
    - Finding data quality issues
    - Monitoring for unexpected patterns
    """

    def __init__(self):
        self.baseline_stats: Optional[Dict] = None

    def set_baseline(self, items: List[Dict[str, Any]]):
        """Set baseline statistics from known good data."""
        self.baseline_stats = self._calculate_stats(items)

    def detect_anomalies(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Detect anomalies compared to baseline.

        Returns anomaly score and details.
        """
        if not self.baseline_stats:
            # First run - set baseline
            self.set_baseline(items)
            return {'anomaly_score': 0, 'anomalies': [], 'is_normal': True}

        current_stats = self._calculate_stats(items)

        anomalies = []
        anomaly_score = 0

        # Compare field counts
        baseline_fields = set(self.baseline_stats['field_counts'].keys())
        current_fields = set(current_stats['field_counts'].keys())

        missing_fields = baseline_fields - current_fields
        new_fields = current_fields - baseline_fields

        if missing_fields:
            anomalies.append({
                'type': 'missing_fields',
                'severity': 'high',
                'fields': list(missing_fields),
                'message': f'Expected fields are missing: {missing_fields}'
            })
            anomaly_score += 30

        if new_fields:
            anomalies.append({
                'type': 'new_fields',
                'severity': 'medium',
                'fields': list(new_fields),
                'message': f'Unexpected new fields detected: {new_fields}'
            })
            anomaly_score += 10

        # Compare value distributions
        for field in baseline_fields & current_fields:
            baseline_dist = self.baseline_stats['value_distributions'].get(field, {})
            current_dist = current_stats['value_distributions'].get(field, {})

            # KL divergence or simple difference
            distribution_diff = self._compare_distributions(baseline_dist, current_dist)

            if distribution_diff > 0.5:  # Significant change
                anomalies.append({
                    'type': 'distribution_change',
                    'severity': 'medium',
                    'field': field,
                    'difference': distribution_diff,
                    'message': f'Unusual value distribution in field: {field}'
                })
                anomaly_score += 15

        # Compare item counts
        baseline_count = self.baseline_stats['item_count']
        current_count = current_stats['item_count']

        count_ratio = current_count / baseline_count if baseline_count > 0 else 0

        if count_ratio < 0.5:  # Less than 50% of expected
            anomalies.append({
                'type': 'low_item_count',
                'severity': 'high',
                'expected': baseline_count,
                'actual': current_count,
                'message': f'Item count much lower than expected ({current_count} vs {baseline_count})'
            })
            anomaly_score += 40

        elif count_ratio > 2.0:  # More than 200% of expected
            anomalies.append({
                'type': 'high_item_count',
                'severity': 'medium',
                'expected': baseline_count,
                'actual': current_count,
                'message': f'Item count much higher than expected ({current_count} vs {baseline_count})'
            })
            anomaly_score += 20

        return {
            'anomaly_score': min(anomaly_score, 100),
            'anomalies': anomalies,
            'is_normal': anomaly_score < 30,
            'severity': self._get_severity_level(anomaly_score),
        }

    def _calculate_stats(self, items: List[Dict]) -> Dict:
        """Calculate statistics for a dataset."""
        stats = {
            'item_count': len(items),
            'field_counts': Counter(),
            'value_distributions': defaultdict(Counter),
            'type_distributions': defaultdict(Counter),
        }

        for item in items:
            for key, value in item.items():
                stats['field_counts'][key] += 1
                stats['type_distributions'][key][type(value).__name__] += 1

                # Sample values for distribution
                if isinstance(value, (str, int, float)):
                    value_key = str(value)[:50]  # Truncate long strings
                    stats['value_distributions'][key][value_key] += 1

        return stats

    def _compare_distributions(self, dist1: Counter, dist2: Counter) -> float:
        """Compare two distributions (simplified KL divergence)."""
        if not dist1 or not dist2:
            return 1.0 if dist1 != dist2 else 0.0

        all_keys = set(dist1.keys()) | set(dist2.keys())

        total1 = sum(dist1.values())
        total2 = sum(dist2.values())

        difference = 0
        for key in all_keys:
            p1 = dist1.get(key, 0) / total1
            p2 = dist2.get(key, 0) / total2
            difference += abs(p1 - p2)

        return difference / len(all_keys)

    def _get_severity_level(self, score: float) -> str:
        """Get severity level from anomaly score."""
        if score < 20:
            return 'low'
        elif score < 50:
            return 'medium'
        elif score < 80:
            return 'high'
        else:
            return 'critical'


class SmartCategorizer:
    """
    Automatically categorize scraped items using ML techniques.

    Uses TF-IDF and clustering to group similar items.
    """

    def __init__(self):
        self.categories: Optional[Dict] = None

    def auto_categorize(
        self,
        items: List[Dict[str, Any]],
        text_field: str = 'title',
        num_categories: int = 5
    ) -> List[Tuple[Dict, str, float]]:
        """
        Automatically categorize items into groups.

        Returns list of (item, category, confidence) tuples.
        """
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.cluster import KMeans
        except ImportError:
            logger.warning("scikit-learn not installed. Install with: pip install scikit-learn")
            return [(item, 'uncategorized', 0.0) for item in items]

        # Extract text
        texts = [item.get(text_field, '') for item in items]
        texts = [str(text) for text in texts if text]

        if len(texts) < num_categories:
            return [(item, f'category_0', 1.0) for item in items]

        # TF-IDF vectorization
        vectorizer = TfidfVectorizer(max_features=100, stop_words='english')
        X = vectorizer.fit_transform(texts)

        # K-means clustering
        kmeans = KMeans(n_clusters=num_categories, random_state=42)
        clusters = kmeans.fit_predict(X)

        # Calculate confidence (distance to centroid)
        distances = kmeans.transform(X)
        confidences = 1 / (1 + distances.min(axis=1))

        # Assign categories
        results = []
        for item, cluster, confidence in zip(items, clusters, confidences):
            category = f'category_{cluster}'
            results.append((item, category, float(confidence)))

        return results

    def suggest_category_names(
        self,
        categorized_items: List[Tuple[Dict, str, float]],
        text_field: str = 'title'
    ) -> Dict[str, str]:
        """
        Suggest human-readable category names based on common terms.

        Returns mapping of category_id -> suggested_name.
        """
        try:
            from sklearn.feature_extraction.text import CountVectorizer
        except ImportError:
            return {}

        # Group by category
        categories = defaultdict(list)
        for item, category, _ in categorized_items:
            text = item.get(text_field, '')
            if text:
                categories[category].append(str(text))

        # Find top terms for each category
        suggestions = {}

        for category, texts in categories.items():
            if len(texts) < 2:
                suggestions[category] = category
                continue

            # Get most common words
            vectorizer = CountVectorizer(max_features=5, stop_words='english')
            try:
                X = vectorizer.fit_transform(texts)
                top_words = vectorizer.get_feature_names_out()
                suggestions[category] = '_'.join(top_words[:2])
            except:
                suggestions[category] = category

        return suggestions
