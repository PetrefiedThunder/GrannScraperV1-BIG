#!/usr/bin/env python3
"""
Example 5: Data Quality Monitoring - Monitor and ensure data quality

This example shows how to use the ML-powered data quality features.
"""

from scraper.sdk import GrandmaScrapeClient


def check_quality_thresholds(quality_report):
    """Check if data meets quality thresholds."""
    score = quality_report['quality_score']
    metrics = quality_report['metrics']

    # Define thresholds
    thresholds = {
        'overall': 0.8,      # 80% overall quality
        'completeness': 0.9,  # 90% completeness
        'validity': 0.95,     # 95% validity
        'uniqueness': 0.85,   # 85% uniqueness
    }

    issues = []

    if score < thresholds['overall']:
        issues.append(f"Overall quality ({score:.1%}) below threshold ({thresholds['overall']:.1%})")

    if metrics['completeness'] < thresholds['completeness']:
        issues.append(f"Completeness ({metrics['completeness']:.1%}) below threshold")

    if metrics['validity'] < thresholds['validity']:
        issues.append(f"Validity ({metrics['validity']:.1%}) below threshold")

    if metrics['uniqueness'] < thresholds['uniqueness']:
        issues.append(f"Uniqueness ({metrics['uniqueness']:.1%}) below threshold")

    return issues


def check_anomalies(anomaly_report):
    """Check for critical anomalies."""
    severity = anomaly_report['severity']
    anomaly_score = anomaly_report['anomaly_score']

    critical_issues = []

    if severity in ['high', 'critical']:
        critical_issues.append(
            f"{severity.upper()} severity anomalies detected (score: {anomaly_score:.1%})"
        )

    if anomaly_score > 0.5:
        critical_issues.append(f"High anomaly score: {anomaly_score:.1%}")

    return critical_issues


def main():
    print("🔍 Data Quality Monitoring Example\n")

    with GrandmaScrapeClient() as client:
        # Scrape data
        print("Scraping data...")
        job_id = client.auto_scrape(
            url="https://books.toscrape.com",
            max_pages=5,
            concurrent=True,
            wait=True
        )

        results = client.get_all_results(job_id)
        print(f"✅ Scraped {len(results)} items\n")

        # ====================================================================
        # DATA QUALITY ANALYSIS
        # ====================================================================
        print("=" * 60)
        print("DATA QUALITY ANALYSIS")
        print("=" * 60)

        quality = client.check_data_quality(job_id)
        report = quality['quality_report']

        print(f"\n📊 Overall Quality Score: {report['quality_score']:.1%}")

        print("\nDetailed Metrics:")
        for metric, value in report['metrics'].items():
            emoji = "✅" if value > 0.8 else "⚠️" if value > 0.6 else "❌"
            print(f"  {emoji} {metric.capitalize()}: {value:.1%}")

        if report.get('issues'):
            print("\n⚠️  Issues Found:")
            for issue in report['issues']:
                print(f"  - {issue}")
        else:
            print("\n✅ No quality issues detected")

        # Check thresholds
        quality_issues = check_quality_thresholds(report)
        if quality_issues:
            print("\n❌ QUALITY THRESHOLD VIOLATIONS:")
            for issue in quality_issues:
                print(f"  - {issue}")
        else:
            print("\n✅ All quality thresholds met")

        # ====================================================================
        # ANOMALY DETECTION
        # ====================================================================
        print("\n" + "=" * 60)
        print("ANOMALY DETECTION")
        print("=" * 60)

        anomalies = client.detect_anomalies(job_id)

        print(f"\n📊 Anomaly Score: {anomalies['anomaly_score']:.1%}")
        print(f"   Severity: {anomalies['severity'].upper()}")

        if anomalies.get('anomalies'):
            print(f"\n⚠️  {len(anomalies['anomalies'])} Anomalies Detected:")
            for anomaly in anomalies['anomalies'][:5]:  # Show first 5
                print(f"  - {anomaly}")

            if len(anomalies['anomalies']) > 5:
                print(f"  ... and {len(anomalies['anomalies']) - 5} more")
        else:
            print("\n✅ No anomalies detected")

        # Check for critical anomalies
        critical_anomalies = check_anomalies(anomalies)
        if critical_anomalies:
            print("\n❌ CRITICAL ANOMALIES:")
            for issue in critical_anomalies:
                print(f"  - {issue}")
        else:
            print("\n✅ No critical anomalies")

        # ====================================================================
        # RECOMMENDATIONS
        # ====================================================================
        print("\n" + "=" * 60)
        print("RECOMMENDATIONS")
        print("=" * 60)

        recommendations = []

        # Based on quality score
        if report['quality_score'] < 0.7:
            recommendations.append("🔄 Re-scrape with different selectors")
            recommendations.append("🔍 Review extraction configuration")

        # Based on completeness
        if report['metrics']['completeness'] < 0.9:
            recommendations.append("📝 Check for missing required fields")
            recommendations.append("🎯 Improve field selectors")

        # Based on validity
        if report['metrics']['validity'] < 0.9:
            recommendations.append("🔧 Add data validation rules")
            recommendations.append("🧹 Implement data cleaning")

        # Based on anomalies
        if anomalies['severity'] in ['high', 'critical']:
            recommendations.append("⚠️  Investigate anomalies immediately")
            recommendations.append("📊 Compare with baseline data")

        if recommendations:
            print("\n💡 Suggested Actions:")
            for rec in recommendations:
                print(f"  {rec}")
        else:
            print("\n✅ Data quality is excellent - no actions needed!")

        # ====================================================================
        # SUMMARY
        # ====================================================================
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)

        overall_status = "🟢 PASS"
        if quality_issues or critical_anomalies:
            overall_status = "🔴 FAIL"
        elif report['quality_score'] < 0.9 or anomalies['severity'] in ['medium', 'high']:
            overall_status = "🟡 WARNING"

        print(f"\nOverall Status: {overall_status}")
        print(f"Items Scraped: {len(results)}")
        print(f"Quality Score: {report['quality_score']:.1%}")
        print(f"Anomaly Score: {anomalies['anomaly_score']:.1%}")
        print(f"Issues Found: {len(quality_issues) + len(critical_anomalies)}")


if __name__ == "__main__":
    main()
