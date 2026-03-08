"""
Notification and alerting system for monitoring scraper operations
Supports webhooks (Slack, Discord, generic), email, and metrics tracking
"""
import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path
from dataclasses import dataclass, asdict
import logging

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class ScraperMetrics:
    """Metrics for a single scraper run"""
    start_time: datetime
    end_time: datetime
    success: bool
    data_type: str  # "daily" or "yearly"
    date_or_year: str  # "2026-03-07" or "2024"
    mortgages_count: int = 0
    mortgages_over_1m: int = 0
    total_volume: float = 0.0
    files_downloaded: int = 0
    s3_uploaded: bool = False
    error_message: Optional[str] = None

    @property
    def duration_seconds(self) -> float:
        """Calculate duration in seconds"""
        return (self.end_time - self.start_time).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['start_time'] = self.start_time.isoformat()
        data['end_time'] = self.end_time.isoformat()
        data['duration_seconds'] = self.duration_seconds
        return data


class NotificationManager:
    """Manages notifications via multiple channels"""

    def __init__(self):
        # Webhook URLs from environment
        self.slack_webhook = os.getenv("SLACK_WEBHOOK_URL")
        self.discord_webhook = os.getenv("DISCORD_WEBHOOK_URL")
        self.generic_webhook = os.getenv("WEBHOOK_URL")

        # Email configuration from environment
        self.email_enabled = os.getenv("EMAIL_NOTIFICATIONS", "false").lower() == "true"
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.email_from = os.getenv("EMAIL_FROM")
        self.email_to = os.getenv("EMAIL_TO", "").split(",")

    def send_success_notification(self, metrics: ScraperMetrics) -> None:
        """
        Send success notification via all configured channels

        Args:
            metrics: Scraper run metrics
        """
        title = f"✅ Scraper Success: {metrics.data_type.title()} {metrics.date_or_year}"

        message = self._format_success_message(metrics)

        self._send_to_all_channels(title, message, "success", metrics)

    def send_failure_notification(self, metrics: ScraperMetrics) -> None:
        """
        Send failure notification via all configured channels

        Args:
            metrics: Scraper run metrics (with error info)
        """
        title = f"❌ Scraper Failed: {metrics.data_type.title()} {metrics.date_or_year}"

        message = self._format_failure_message(metrics)

        self._send_to_all_channels(title, message, "failure", metrics)

    def _format_success_message(self, metrics: ScraperMetrics) -> str:
        """Format success message"""
        lines = [
            f"**Status:** Success ✅",
            f"**Type:** {metrics.data_type.title()}",
            f"**Date/Year:** {metrics.date_or_year}",
            f"**Duration:** {metrics.duration_seconds:.1f}s",
            f"**Mortgages:** {metrics.mortgages_count:,}",
            f"**≥$1M Mortgages:** {metrics.mortgages_over_1m:,}",
            f"**Total Volume:** ${metrics.total_volume:,.2f}",
            f"**S3 Upload:** {'Yes ✓' if metrics.s3_uploaded else 'No'}",
        ]
        return "\n".join(lines)

    def _format_failure_message(self, metrics: ScraperMetrics) -> str:
        """Format failure message"""
        lines = [
            f"**Status:** Failed ❌",
            f"**Type:** {metrics.data_type.title()}",
            f"**Date/Year:** {metrics.date_or_year}",
            f"**Duration:** {metrics.duration_seconds:.1f}s",
            f"**Error:** {metrics.error_message or 'Unknown error'}",
        ]
        return "\n".join(lines)

    def _send_to_all_channels(
        self,
        title: str,
        message: str,
        status: str,
        metrics: ScraperMetrics
    ) -> None:
        """Send notification to all configured channels"""
        # Slack
        if self.slack_webhook:
            self._send_slack(title, message, status)

        # Discord
        if self.discord_webhook:
            self._send_discord(title, message, status)

        # Generic webhook
        if self.generic_webhook:
            self._send_webhook(title, message, metrics)

        # Email
        if self.email_enabled and self.email_to:
            self._send_email(title, message, status)

    def _send_slack(self, title: str, message: str, status: str) -> None:
        """Send notification to Slack"""
        if not REQUESTS_AVAILABLE:
            logger.warning("requests library not available, skipping Slack notification")
            return

        try:
            color = "#36a64f" if status == "success" else "#ff0000"

            payload = {
                "attachments": [
                    {
                        "fallback": title,
                        "color": color,
                        "title": title,
                        "text": message,
                        "footer": "Broward Mortgage Scraper",
                        "ts": int(datetime.now().timestamp())
                    }
                ]
            }

            response = requests.post(
                self.slack_webhook,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            logger.info("✓ Slack notification sent")

        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")

    def _send_discord(self, title: str, message: str, status: str) -> None:
        """Send notification to Discord"""
        if not REQUESTS_AVAILABLE:
            logger.warning("requests library not available, skipping Discord notification")
            return

        try:
            color = 3066993 if status == "success" else 15158332  # Green or Red

            payload = {
                "embeds": [
                    {
                        "title": title,
                        "description": message,
                        "color": color,
                        "footer": {
                            "text": "Broward Mortgage Scraper"
                        },
                        "timestamp": datetime.now().isoformat()
                    }
                ]
            }

            response = requests.post(
                self.discord_webhook,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            logger.info("✓ Discord notification sent")

        except Exception as e:
            logger.error(f"Failed to send Discord notification: {e}")

    def _send_webhook(self, title: str, message: str, metrics: ScraperMetrics) -> None:
        """Send notification to generic webhook"""
        if not REQUESTS_AVAILABLE:
            logger.warning("requests library not available, skipping webhook notification")
            return

        try:
            payload = {
                "title": title,
                "message": message,
                "metrics": metrics.to_dict(),
                "timestamp": datetime.now().isoformat()
            }

            response = requests.post(
                self.generic_webhook,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            logger.info("✓ Webhook notification sent")

        except Exception as e:
            logger.error(f"Failed to send webhook notification: {e}")

    def _send_email(self, title: str, message: str, status: str) -> None:
        """Send email notification"""
        try:
            if not all([self.smtp_username, self.smtp_password, self.email_from]):
                logger.warning("Email not configured, skipping email notification")
                return

            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = title
            msg["From"] = self.email_from
            msg["To"] = ", ".join(self.email_to)

            # Plain text version
            text_body = message.replace("**", "").replace("✅", "[SUCCESS]").replace("❌", "[FAILED]")

            # HTML version
            html_body = f"""
            <html>
              <body>
                <h2>{title}</h2>
                <pre style="font-family: monospace; background: #f5f5f5; padding: 10px;">
{message}
                </pre>
                <p style="color: #666; font-size: 12px;">
                  Sent by Broward Mortgage Scraper
                </p>
              </body>
            </html>
            """

            msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            # Send via SMTP
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)

            logger.info(f"✓ Email notification sent to {len(self.email_to)} recipients")

        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")


class MetricsTracker:
    """Track and persist scraper metrics"""

    def __init__(self, metrics_dir: Path = Path("data/metrics")):
        self.metrics_dir = metrics_dir
        self.metrics_dir.mkdir(parents=True, exist_ok=True)

    def save_metrics(self, metrics: ScraperMetrics) -> Path:
        """
        Save metrics to JSON file

        Args:
            metrics: Scraper run metrics

        Returns:
            Path to saved metrics file
        """
        timestamp = metrics.start_time.strftime("%Y%m%d_%H%M%S")
        filename = f"metrics_{metrics.data_type}_{metrics.date_or_year}_{timestamp}.json"
        filepath = self.metrics_dir / filename

        with open(filepath, 'w') as f:
            json.dump(metrics.to_dict(), f, indent=2)

        logger.info(f"Metrics saved to {filepath}")
        return filepath

    def get_recent_metrics(self, limit: int = 10) -> List[ScraperMetrics]:
        """
        Get recent metrics

        Args:
            limit: Maximum number of metrics to return

        Returns:
            List of recent metrics
        """
        metric_files = sorted(
            self.metrics_dir.glob("metrics_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )[:limit]

        metrics = []
        for filepath in metric_files:
            try:
                with open(filepath) as f:
                    data = json.load(f)
                    # Reconstruct ScraperMetrics (simplified, doesn't restore datetime objects)
                    metrics.append(data)
            except Exception as e:
                logger.warning(f"Failed to load metrics from {filepath}: {e}")

        return metrics

    def get_summary_stats(self, days: int = 30) -> Dict[str, Any]:
        """
        Get summary statistics for recent runs

        Args:
            days: Number of days to include in summary

        Returns:
            Dictionary with summary statistics
        """
        cutoff = datetime.now().timestamp() - (days * 86400)

        metric_files = [
            f for f in self.metrics_dir.glob("metrics_*.json")
            if f.stat().st_mtime > cutoff
        ]

        total_runs = len(metric_files)
        successful_runs = 0
        failed_runs = 0
        total_mortgages = 0

        for filepath in metric_files:
            try:
                with open(filepath) as f:
                    data = json.load(f)
                    if data.get('success'):
                        successful_runs += 1
                        total_mortgages += data.get('mortgages_count', 0)
                    else:
                        failed_runs += 1
            except Exception as e:
                logger.warning(f"Failed to process {filepath}: {e}")

        return {
            "period_days": days,
            "total_runs": total_runs,
            "successful_runs": successful_runs,
            "failed_runs": failed_runs,
            "success_rate": (successful_runs / total_runs * 100) if total_runs > 0 else 0,
            "total_mortgages_processed": total_mortgages
        }
