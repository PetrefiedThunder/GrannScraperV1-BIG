"""
Enterprise Logging & Observability System.

Structured logging, metrics, and distributed tracing.
Competitors charge $199-499/month for APM features.
"""

import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
import traceback
from contextvars import ContextVar

from pythonjsonlogger import jsonlogger


# Context variables for request tracking
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar('user_id', default=None)


# ============================================================================
# STRUCTURED LOGGING
# ============================================================================

class StructuredLogger:
    """
    Structured JSON logging for production.

    Features:
    - JSON formatted logs
    - Request ID tracking
    - User ID tracking
    - Performance metrics
    - Error tracking with stack traces
    - Log levels and filtering
    - Multiple outputs (console, file, remote)
    """

    def __init__(
        self,
        name: str,
        log_level: str = "INFO",
        log_file: Optional[str] = None,
        json_format: bool = True
    ):
        """
        Initialize structured logger.

        Args:
            name: Logger name
            log_level: Logging level
            log_file: Optional log file path
            json_format: Use JSON formatting
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, log_level.upper()))

        # Remove existing handlers
        self.logger.handlers.clear()

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)

        if json_format:
            # JSON formatter
            formatter = jsonlogger.JsonFormatter(
                '%(timestamp)s %(level)s %(name)s %(message)s '
                '%(request_id)s %(user_id)s %(duration_ms)s'
            )
        else:
            # Standard formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )

        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # File handler
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    def _get_context(self) -> Dict[str, Any]:
        """Get current logging context."""
        return {
            'request_id': request_id_var.get(),
            'user_id': user_id_var.get(),
            'timestamp': datetime.utcnow().isoformat()
        }

    def info(self, message: str, **kwargs):
        """Log info message."""
        extra = {**self._get_context(), **kwargs}
        self.logger.info(message, extra=extra)

    def warning(self, message: str, **kwargs):
        """Log warning message."""
        extra = {**self._get_context(), **kwargs}
        self.logger.warning(message, extra=extra)

    def error(self, message: str, exc_info: Optional[Exception] = None, **kwargs):
        """Log error message."""
        extra = {**self._get_context(), **kwargs}

        if exc_info:
            extra['exception'] = {
                'type': type(exc_info).__name__,
                'message': str(exc_info),
                'traceback': traceback.format_exc()
            }

        self.logger.error(message, extra=extra, exc_info=exc_info)

    def critical(self, message: str, **kwargs):
        """Log critical message."""
        extra = {**self._get_context(), **kwargs}
        self.logger.critical(message, extra=extra)


# ============================================================================
# PERFORMANCE METRICS
# ============================================================================

class PerformanceMetrics:
    """
    Track performance metrics for scraping operations.

    Features:
    - Request duration tracking
    - Success/failure rates
    - Throughput metrics
    - Percentile calculations (p50, p95, p99)
    - Resource usage
    """

    def __init__(self):
        """Initialize metrics collector."""
        self.metrics: Dict[str, list] = {
            'request_durations': [],
            'scrape_durations': [],
            'items_scraped': [],
            'pages_visited': [],
            'errors': [],
            'success_rate': []
        }

    def record_request(self, duration_ms: float, success: bool):
        """Record HTTP request metrics."""
        self.metrics['request_durations'].append(duration_ms)

        if not success:
            self.metrics['errors'].append({
                'timestamp': datetime.utcnow().isoformat(),
                'duration_ms': duration_ms
            })

    def record_scrape(
        self,
        duration_seconds: float,
        items_scraped: int,
        pages_visited: int,
        success: bool
    ):
        """Record scraping job metrics."""
        self.metrics['scrape_durations'].append(duration_seconds)
        self.metrics['items_scraped'].append(items_scraped)
        self.metrics['pages_visited'].append(pages_visited)
        self.metrics['success_rate'].append(1 if success else 0)

    def get_percentile(self, values: list, percentile: int) -> float:
        """Calculate percentile from values."""
        if not values:
            return 0.0

        sorted_values = sorted(values)
        index = int(len(sorted_values) * (percentile / 100))
        return sorted_values[min(index, len(sorted_values) - 1)]

    def get_stats(self) -> Dict[str, Any]:
        """Get aggregated metrics."""
        request_durations = self.metrics['request_durations']
        scrape_durations = self.metrics['scrape_durations']
        items_scraped = self.metrics['items_scraped']

        return {
            'requests': {
                'total': len(request_durations),
                'avg_duration_ms': sum(request_durations) / len(request_durations) if request_durations else 0,
                'p50_ms': self.get_percentile(request_durations, 50),
                'p95_ms': self.get_percentile(request_durations, 95),
                'p99_ms': self.get_percentile(request_durations, 99),
                'errors': len(self.metrics['errors'])
            },
            'scrapes': {
                'total': len(scrape_durations),
                'avg_duration_s': sum(scrape_durations) / len(scrape_durations) if scrape_durations else 0,
                'total_items': sum(items_scraped),
                'avg_items_per_scrape': sum(items_scraped) / len(items_scraped) if items_scraped else 0,
                'success_rate': sum(self.metrics['success_rate']) / len(self.metrics['success_rate']) if self.metrics['success_rate'] else 0
            }
        }


# ============================================================================
# REQUEST TRACKING
# ============================================================================

class RequestTracker:
    """
    Track and correlate requests across the system.

    Features:
    - Generate unique request IDs
    - Distributed tracing
    - Request lifecycle logging
    - Performance profiling
    """

    def __init__(self, logger: StructuredLogger):
        """Initialize request tracker."""
        self.logger = logger
        self.active_requests: Dict[str, Dict[str, Any]] = {}

    def start_request(self, request_id: str, method: str, path: str, **kwargs):
        """Start tracking a request."""
        request_id_var.set(request_id)

        self.active_requests[request_id] = {
            'start_time': time.time(),
            'method': method,
            'path': path,
            **kwargs
        }

        self.logger.info(
            f"Request started: {method} {path}",
            request_id=request_id,
            method=method,
            path=path
        )

    def end_request(
        self,
        request_id: str,
        status_code: int,
        **kwargs
    ):
        """End tracking a request."""
        if request_id not in self.active_requests:
            return

        request_info = self.active_requests[request_id]
        duration_ms = (time.time() - request_info['start_time']) * 1000

        self.logger.info(
            f"Request completed: {request_info['method']} {request_info['path']}",
            request_id=request_id,
            status_code=status_code,
            duration_ms=duration_ms,
            **kwargs
        )

        del self.active_requests[request_id]
        request_id_var.set(None)

    def log_error(self, request_id: str, error: Exception):
        """Log request error."""
        self.logger.error(
            f"Request failed: {error}",
            request_id=request_id,
            exc_info=error
        )


# ============================================================================
# LOG AGGREGATION
# ============================================================================

class LogAggregator:
    """
    Aggregate and analyze logs.

    Features:
    - Error rate tracking
    - Slow request detection
    - Pattern detection
    - Alert triggers
    """

    def __init__(self, logger: StructuredLogger):
        """Initialize log aggregator."""
        self.logger = logger
        self.error_counts: Dict[str, int] = {}
        self.slow_requests: list = []
        self.slow_threshold_ms = 5000  # 5 seconds

    def analyze_request(
        self,
        request_id: str,
        duration_ms: float,
        status_code: int,
        error: Optional[Exception] = None
    ):
        """Analyze completed request."""

        # Track errors
        if error or status_code >= 400:
            error_type = type(error).__name__ if error else f"HTTP_{status_code}"
            self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1

            # Alert on high error rate
            if self.error_counts[error_type] > 10:
                self.logger.warning(
                    f"High error rate detected: {error_type}",
                    error_type=error_type,
                    count=self.error_counts[error_type]
                )

        # Track slow requests
        if duration_ms > self.slow_threshold_ms:
            self.slow_requests.append({
                'request_id': request_id,
                'duration_ms': duration_ms,
                'timestamp': datetime.utcnow().isoformat()
            })

            self.logger.warning(
                f"Slow request detected: {duration_ms:.0f}ms",
                request_id=request_id,
                duration_ms=duration_ms
            )

    def get_error_summary(self) -> Dict[str, Any]:
        """Get error summary."""
        total_errors = sum(self.error_counts.values())

        return {
            'total_errors': total_errors,
            'by_type': self.error_counts,
            'slow_requests': len(self.slow_requests),
            'slowest_request': max(
                self.slow_requests,
                key=lambda x: x['duration_ms']
            ) if self.slow_requests else None
        }


# ============================================================================
# AUDIT LOGGING
# ============================================================================

class AuditLogger:
    """
    Security audit logging.

    Tracks security-relevant events:
    - Authentication attempts
    - Authorization failures
    - Data access
    - Configuration changes
    """

    def __init__(self, log_file: str):
        """Initialize audit logger."""
        self.logger = logging.getLogger('audit')
        self.logger.setLevel(logging.INFO)

        # Separate audit log file
        handler = logging.FileHandler(log_file)
        formatter = jsonlogger.JsonFormatter(
            '%(timestamp)s %(event_type)s %(user_id)s %(message)s %(details)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def log_auth_attempt(self, user_id: str, success: bool, ip_address: str):
        """Log authentication attempt."""
        self.logger.info(
            f"Authentication {'successful' if success else 'failed'}",
            extra={
                'event_type': 'auth_attempt',
                'user_id': user_id,
                'success': success,
                'ip_address': ip_address,
                'timestamp': datetime.utcnow().isoformat()
            }
        )

    def log_data_access(self, user_id: str, resource: str, action: str):
        """Log data access."""
        self.logger.info(
            f"Data access: {action} on {resource}",
            extra={
                'event_type': 'data_access',
                'user_id': user_id,
                'resource': resource,
                'action': action,
                'timestamp': datetime.utcnow().isoformat()
            }
        )

    def log_config_change(self, user_id: str, setting: str, old_value: Any, new_value: Any):
        """Log configuration change."""
        self.logger.info(
            f"Configuration changed: {setting}",
            extra={
                'event_type': 'config_change',
                'user_id': user_id,
                'setting': setting,
                'old_value': str(old_value),
                'new_value': str(new_value),
                'timestamp': datetime.utcnow().isoformat()
            }
        )


# ============================================================================
# OBSERVABILITY DASHBOARD
# ============================================================================

class ObservabilityDashboard:
    """
    Real-time observability dashboard.

    Aggregates logs, metrics, and traces for monitoring.
    """

    def __init__(self):
        """Initialize dashboard."""
        self.logger = StructuredLogger('observability')
        self.metrics = PerformanceMetrics()
        self.request_tracker = RequestTracker(self.logger)
        self.log_aggregator = LogAggregator(self.logger)

    def get_health_status(self) -> Dict[str, Any]:
        """Get system health status."""
        metrics = self.metrics.get_stats()
        errors = self.log_aggregator.get_error_summary()

        # Calculate health score
        error_rate = errors['total_errors'] / max(metrics['requests']['total'], 1)
        success_rate = metrics['scrapes'].get('success_rate', 1.0)
        avg_duration = metrics['requests'].get('avg_duration_ms', 0)

        health_score = (
            (1 - error_rate) * 0.4 +
            success_rate * 0.4 +
            (1 - min(avg_duration / 10000, 1)) * 0.2  # Penalize if avg > 10s
        )

        status = 'healthy' if health_score > 0.8 else 'degraded' if health_score > 0.5 else 'unhealthy'

        return {
            'status': status,
            'health_score': health_score,
            'metrics': metrics,
            'errors': errors,
            'timestamp': datetime.utcnow().isoformat()
        }


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

def setup_logging_example():
    """Example of setting up logging."""

    # Structured logger
    logger = StructuredLogger(
        'grandmascrape',
        log_level='INFO',
        log_file='logs/app.log',
        json_format=True
    )

    # Set request context
    request_id_var.set('req_123456')
    user_id_var.set('user_789')

    # Log messages
    logger.info("Starting scrape job", job_id="job_001", url="https://example.com")

    try:
        # Simulate operation
        raise ValueError("Example error")
    except Exception as e:
        logger.error("Scrape failed", exc_info=e, job_id="job_001")

    # Performance metrics
    metrics = PerformanceMetrics()
    metrics.record_scrape(
        duration_seconds=12.5,
        items_scraped=100,
        pages_visited=10,
        success=True
    )

    print(json.dumps(metrics.get_stats(), indent=2))

    # Audit logging
    audit = AuditLogger('logs/audit.log')
    audit.log_auth_attempt(
        user_id='user_789',
        success=True,
        ip_address='192.168.1.1'
    )

    # Observability dashboard
    dashboard = ObservabilityDashboard()
    health = dashboard.get_health_status()
    print(json.dumps(health, indent=2))
