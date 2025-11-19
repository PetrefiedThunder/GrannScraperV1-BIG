"""
GrandmaScrape Monitoring & Alerting System.

Enterprise-grade monitoring with multi-channel alerting.

Features:
- Multi-channel notifications (Slack, Discord, Email, SMS, PagerDuty, Webhooks)
- Alert levels (info, warning, error, critical)
- Job failure/success alerts
- Data quality threshold alerts
- Anomaly detection alerts
- Alert history tracking

Usage:
    from scraper.monitoring import AlertManager, Alert, AlertLevel

    # Initialize alert manager
    manager = AlertManager()

    # Send alert
    alert = Alert(
        level=AlertLevel.ERROR,
        title="Scraping Failed",
        message="Job XYZ failed after 3 retries"
    )
    await manager.send_alert(alert, channels=["slack", "email"])
"""

from scraper.monitoring.alerts import (
    Alert,
    AlertLevel,
    AlertChannel,
    AlertManager,
    AlertConfig
)

__all__ = [
    'Alert',
    'AlertLevel',
    'AlertChannel',
    'AlertManager',
    'AlertConfig'
]
