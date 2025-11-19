"""
GrandmaScrape Observability & Logging System.

Full-stack observability for production monitoring.

Features:
- Structured JSON Logging (request ID, user ID, contextual metadata)
- Performance Metrics (p50, p95, p99 percentiles)
- Request Tracking (distributed tracing support)
- Log Aggregation
- Audit Logging (security events, compliance)
- Observability Dashboard (real-time health status)

Usage:
    from scraper.observability import StructuredLogger, PerformanceMetrics

    # Structured logging
    logger = StructuredLogger("my_module")
    logger.info("Scraping started", url=url, job_id=job_id)
    logger.error("Scraping failed", exc_info=exception)

    # Performance metrics
    metrics = PerformanceMetrics()
    await metrics.record_request_duration(duration_ms)
    stats = metrics.get_percentiles()  # Returns p50, p95, p99
"""

from scraper.observability.logging_system import (
    StructuredLogger,
    PerformanceMetrics,
    RequestTracker,
    LogAggregator,
    AuditLogger,
    ObservabilityDashboard
)

__all__ = [
    'StructuredLogger',
    'PerformanceMetrics',
    'RequestTracker',
    'LogAggregator',
    'AuditLogger',
    'ObservabilityDashboard'
]
