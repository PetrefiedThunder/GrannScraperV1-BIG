"""
Advanced Monitoring and Alerting System.

Multi-channel notifications for job events, failures, and data quality issues.
Premium feature - competitors charge $99-299/month for this.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
import httpx

from scraper.config.models import ScrapeResult

logger = logging.getLogger(__name__)


class AlertLevel(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertChannel(str, Enum):
    """Supported alert channels."""
    EMAIL = "email"
    SLACK = "slack"
    DISCORD = "discord"
    WEBHOOK = "webhook"
    SMS = "sms"
    PAGERDUTY = "pagerduty"


@dataclass
class Alert:
    """Alert message."""
    level: AlertLevel
    title: str
    message: str
    job_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class AlertManager:
    """
    Multi-channel alerting system.

    Supports:
    - Slack notifications
    - Discord webhooks
    - Email alerts
    - SMS (Twilio)
    - PagerDuty incidents
    - Custom webhooks
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize alert manager.

        Args:
            config: Alert configuration with channel settings
        """
        self.config = config or {}
        self.client = httpx.AsyncClient()
        self.alert_history: List[Alert] = []

    async def send_alert(self, alert: Alert, channels: Optional[List[AlertChannel]] = None):
        """
        Send alert to configured channels.

        Args:
            alert: Alert to send
            channels: List of channels to send to (or use config default)
        """
        if channels is None:
            channels = self.config.get('default_channels', [AlertChannel.WEBHOOK])

        logger.info(f"Sending {alert.level} alert: {alert.title}")

        # Store in history
        self.alert_history.append(alert)

        # Send to each channel
        tasks = []
        for channel in channels:
            if channel == AlertChannel.SLACK:
                tasks.append(self._send_slack(alert))
            elif channel == AlertChannel.DISCORD:
                tasks.append(self._send_discord(alert))
            elif channel == AlertChannel.EMAIL:
                tasks.append(self._send_email(alert))
            elif channel == AlertChannel.WEBHOOK:
                tasks.append(self._send_webhook(alert))
            elif channel == AlertChannel.SMS:
                tasks.append(self._send_sms(alert))
            elif channel == AlertChannel.PAGERDUTY:
                tasks.append(self._send_pagerduty(alert))

        # Send all concurrently
        await asyncio.gather(*tasks, return_exceptions=True)

    # ========================================================================
    # SLACK INTEGRATION
    # ========================================================================

    async def _send_slack(self, alert: Alert):
        """Send alert to Slack via webhook."""
        webhook_url = self.config.get('slack', {}).get('webhook_url')
        if not webhook_url:
            logger.warning("Slack webhook URL not configured")
            return

        # Color based on level
        color_map = {
            AlertLevel.INFO: "#36a64f",
            AlertLevel.WARNING: "#ff9900",
            AlertLevel.ERROR: "#ff0000",
            AlertLevel.CRITICAL: "#8b0000",
        }

        payload = {
            "attachments": [{
                "color": color_map.get(alert.level, "#808080"),
                "title": f"🧓 GrandmaScrape Alert: {alert.title}",
                "text": alert.message,
                "fields": [
                    {
                        "title": "Level",
                        "value": alert.level.upper(),
                        "short": True
                    },
                    {
                        "title": "Job ID",
                        "value": alert.job_id or "N/A",
                        "short": True
                    },
                    {
                        "title": "Timestamp",
                        "value": alert.timestamp.isoformat(),
                        "short": False
                    }
                ],
                "footer": "GrandmaScrape Monitoring",
                "ts": int(alert.timestamp.timestamp())
            }]
        }

        # Add metadata fields
        if alert.metadata:
            for key, value in alert.metadata.items():
                payload["attachments"][0]["fields"].append({
                    "title": key.replace("_", " ").title(),
                    "value": str(value),
                    "short": True
                })

        try:
            response = await self.client.post(webhook_url, json=payload)
            response.raise_for_status()
            logger.info("Slack alert sent successfully")
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")

    # ========================================================================
    # DISCORD INTEGRATION
    # ========================================================================

    async def _send_discord(self, alert: Alert):
        """Send alert to Discord via webhook."""
        webhook_url = self.config.get('discord', {}).get('webhook_url')
        if not webhook_url:
            logger.warning("Discord webhook URL not configured")
            return

        # Emoji and color based on level
        emoji_map = {
            AlertLevel.INFO: "ℹ️",
            AlertLevel.WARNING: "⚠️",
            AlertLevel.ERROR: "❌",
            AlertLevel.CRITICAL: "🚨",
        }

        color_map = {
            AlertLevel.INFO: 3447003,    # Blue
            AlertLevel.WARNING: 16776960,  # Yellow
            AlertLevel.ERROR: 15158332,   # Red
            AlertLevel.CRITICAL: 9109504,  # Dark red
        }

        embed = {
            "title": f"{emoji_map.get(alert.level, '📢')} {alert.title}",
            "description": alert.message,
            "color": color_map.get(alert.level, 8421504),
            "fields": [
                {
                    "name": "Level",
                    "value": alert.level.upper(),
                    "inline": True
                },
                {
                    "name": "Job ID",
                    "value": alert.job_id or "N/A",
                    "inline": True
                }
            ],
            "footer": {
                "text": "GrandmaScrape Monitoring"
            },
            "timestamp": alert.timestamp.isoformat()
        }

        # Add metadata
        if alert.metadata:
            for key, value in alert.metadata.items():
                embed["fields"].append({
                    "name": key.replace("_", " ").title(),
                    "value": str(value),
                    "inline": True
                })

        payload = {
            "username": "GrandmaScrape",
            "embeds": [embed]
        }

        try:
            response = await self.client.post(webhook_url, json=payload)
            response.raise_for_status()
            logger.info("Discord alert sent successfully")
        except Exception as e:
            logger.error(f"Failed to send Discord alert: {e}")

    # ========================================================================
    # EMAIL INTEGRATION
    # ========================================================================

    async def _send_email(self, alert: Alert):
        """Send alert via email (SMTP)."""
        email_config = self.config.get('email', {})
        if not email_config.get('enabled'):
            logger.warning("Email alerts not configured")
            return

        # Would use aiosmtplib or similar
        # Example implementation:
        import aiosmtplib
        from email.message import EmailMessage

        msg = EmailMessage()
        msg['Subject'] = f"[{alert.level.upper()}] GrandmaScrape: {alert.title}"
        msg['From'] = email_config.get('from_address')
        msg['To'] = ', '.join(email_config.get('to_addresses', []))

        # HTML email body
        html_body = f"""
        <html>
          <body style="font-family: Arial, sans-serif;">
            <h2 style="color: {'#ff0000' if alert.level in [AlertLevel.ERROR, AlertLevel.CRITICAL] else '#ff9900' if alert.level == AlertLevel.WARNING else '#36a64f'};">
              GrandmaScrape Alert: {alert.title}
            </h2>
            <p><strong>Level:</strong> {alert.level.upper()}</p>
            <p><strong>Job ID:</strong> {alert.job_id or 'N/A'}</p>
            <p><strong>Timestamp:</strong> {alert.timestamp.isoformat()}</p>
            <hr>
            <p>{alert.message}</p>
            {'<hr>' if alert.metadata else ''}
            {'<h3>Details:</h3>' if alert.metadata else ''}
            {'<ul>' + ''.join([f'<li><strong>{k}:</strong> {v}</li>' for k, v in (alert.metadata or {}).items()]) + '</ul>' if alert.metadata else ''}
          </body>
        </html>
        """

        msg.set_content(alert.message)
        msg.add_alternative(html_body, subtype='html')

        try:
            await aiosmtplib.send(
                msg,
                hostname=email_config.get('smtp_host', 'localhost'),
                port=email_config.get('smtp_port', 587),
                username=email_config.get('smtp_user'),
                password=email_config.get('smtp_password'),
                use_tls=email_config.get('use_tls', True)
            )
            logger.info("Email alert sent successfully")
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")

    # ========================================================================
    # WEBHOOK INTEGRATION
    # ========================================================================

    async def _send_webhook(self, alert: Alert):
        """Send alert to custom webhook."""
        webhook_url = self.config.get('webhook', {}).get('url')
        if not webhook_url:
            logger.warning("Webhook URL not configured")
            return

        payload = {
            "level": alert.level,
            "title": alert.title,
            "message": alert.message,
            "job_id": alert.job_id,
            "metadata": alert.metadata,
            "timestamp": alert.timestamp.isoformat()
        }

        try:
            response = await self.client.post(webhook_url, json=payload)
            response.raise_for_status()
            logger.info("Webhook alert sent successfully")
        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")

    # ========================================================================
    # SMS INTEGRATION (Twilio)
    # ========================================================================

    async def _send_sms(self, alert: Alert):
        """Send alert via SMS using Twilio."""
        sms_config = self.config.get('sms', {})
        if not sms_config.get('enabled'):
            logger.warning("SMS alerts not configured")
            return

        # Only send SMS for ERROR and CRITICAL
        if alert.level not in [AlertLevel.ERROR, AlertLevel.CRITICAL]:
            return

        from twilio.rest import Client

        account_sid = sms_config.get('twilio_account_sid')
        auth_token = sms_config.get('twilio_auth_token')
        from_number = sms_config.get('from_number')
        to_numbers = sms_config.get('to_numbers', [])

        if not all([account_sid, auth_token, from_number, to_numbers]):
            logger.warning("SMS configuration incomplete")
            return

        client = Client(account_sid, auth_token)

        message_body = f"[{alert.level.upper()}] GrandmaScrape: {alert.title}\n\n{alert.message[:100]}"

        try:
            for to_number in to_numbers:
                client.messages.create(
                    body=message_body,
                    from_=from_number,
                    to=to_number
                )
            logger.info("SMS alert sent successfully")
        except Exception as e:
            logger.error(f"Failed to send SMS alert: {e}")

    # ========================================================================
    # PAGERDUTY INTEGRATION
    # ========================================================================

    async def _send_pagerduty(self, alert: Alert):
        """Send alert to PagerDuty."""
        pd_config = self.config.get('pagerduty', {})
        if not pd_config.get('enabled'):
            logger.warning("PagerDuty not configured")
            return

        # Only trigger PagerDuty for CRITICAL alerts
        if alert.level != AlertLevel.CRITICAL:
            return

        routing_key = pd_config.get('routing_key')
        if not routing_key:
            logger.warning("PagerDuty routing key not configured")
            return

        payload = {
            "routing_key": routing_key,
            "event_action": "trigger",
            "payload": {
                "summary": f"GrandmaScrape: {alert.title}",
                "severity": "critical",
                "source": "grandmascrape",
                "custom_details": {
                    "message": alert.message,
                    "job_id": alert.job_id,
                    **(alert.metadata or {})
                }
            }
        }

        try:
            response = await self.client.post(
                "https://events.pagerduty.com/v2/enqueue",
                json=payload
            )
            response.raise_for_status()
            logger.info("PagerDuty incident created successfully")
        except Exception as e:
            logger.error(f"Failed to create PagerDuty incident: {e}")

    # ========================================================================
    # MONITORING HELPERS
    # ========================================================================

    async def alert_job_failed(self, job_id: str, error: str):
        """Alert when a job fails."""
        await self.send_alert(Alert(
            level=AlertLevel.ERROR,
            title="Scraping Job Failed",
            message=f"Job {job_id} failed with error: {error}",
            job_id=job_id,
            metadata={"error": error}
        ))

    async def alert_low_quality(self, job_id: str, quality_score: float, threshold: float):
        """Alert when data quality is low."""
        await self.send_alert(Alert(
            level=AlertLevel.WARNING,
            title="Low Data Quality Detected",
            message=f"Job {job_id} produced data with quality score {quality_score:.1%}, below threshold {threshold:.1%}",
            job_id=job_id,
            metadata={
                "quality_score": f"{quality_score:.1%}",
                "threshold": f"{threshold:.1%}"
            }
        ))

    async def alert_anomalies(self, job_id: str, severity: str, anomaly_count: int):
        """Alert when anomalies are detected."""
        level = AlertLevel.CRITICAL if severity == "critical" else AlertLevel.WARNING

        await self.send_alert(Alert(
            level=level,
            title=f"{severity.upper()} Anomalies Detected",
            message=f"Job {job_id} detected {anomaly_count} anomalies with {severity} severity",
            job_id=job_id,
            metadata={
                "severity": severity,
                "anomaly_count": anomaly_count
            }
        ))

    async def alert_job_success(self, job_id: str, result: ScrapeResult):
        """Alert when a job completes successfully."""
        await self.send_alert(Alert(
            level=AlertLevel.INFO,
            title="Scraping Job Completed",
            message=f"Job {job_id} completed successfully",
            job_id=job_id,
            metadata={
                "items_scraped": result.items_scraped,
                "pages_visited": result.pages_visited,
                "duration": f"{result.duration:.2f}s",
                "success_rate": f"{result.success_rate:.1%}"
            }
        ))

    def get_alert_history(self, limit: int = 100) -> List[Alert]:
        """Get recent alert history."""
        return self.alert_history[-limit:]

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
