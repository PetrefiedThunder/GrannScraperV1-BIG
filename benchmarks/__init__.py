"""
GrandmaScrape Performance Benchmarks.

Real-world benchmarks and commercial competitor comparisons.

Features:
- Performance benchmarks (sequential, concurrent, quality analysis)
- Commercial competitor comparisons (Apify, ScraperAPI, Bright Data, etc.)
- Feature-by-feature analysis
- ROI calculations
- Markdown report generation

Usage:
    from benchmarks import PerformanceBenchmark, CommercialComparison

    # Run performance benchmarks
    benchmark = PerformanceBenchmark()
    results = await benchmark.run_all_benchmarks()

    # Generate comparison report
    comparison = CommercialComparison()
    report = comparison.generate_comparison_report(results)
    print(report)
"""

from benchmarks.performance_benchmarks import (
    PerformanceBenchmark,
    CommercialComparison,
    BenchmarkResults
)

__all__ = [
    'PerformanceBenchmark',
    'CommercialComparison',
    'BenchmarkResults'
]
