"""Retirement notification and report distribution for the Janitor Agent.

Notifies dependent systems of retirement events via Pub/Sub and distributes
daily reports to Slack, email, and GCS storage.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from absl import logging


@dataclass
class ReportDistributionConfig:
    """Configuration for report distribution channels."""

    storage_bucket: str = "gs://tradestream-reports/janitor/"
    slack_channel: str = "#strategy-ops"
    slack_webhook_url: str = ""
    email_recipients: list[str] = field(
        default_factory=lambda: ["strategy-ops@tradestream.io"]
    )
    report_retention_days: int = 90
    email_on_threshold: int = 10


@dataclass
class NotificationConfig:
    """Configuration for dependent system notifications."""

    pubsub_project: str = "tradestream"
    dependent_systems: list[str] = field(
        default_factory=lambda: [
            "signal-router",
            "portfolio-manager",
            "alert-system",
            "dashboard",
        ]
    )


class RetirementNotifier:
    """Notify dependent systems of retirement events."""

    def __init__(self, config: NotificationConfig):
        self._config = config

    def notify_retirement(
        self,
        impl_id: str,
        spec_id: str,
        symbol: str,
        reason: str,
        metadata: Optional[dict] = None,
    ) -> dict:
        """Notify all dependent systems of a retirement event."""
        notification = {
            "event": "strategy_retired",
            "impl_id": impl_id,
            "spec_id": spec_id,
            "symbol": symbol,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }

        results = {}
        for system in self._config.dependent_systems:
            try:
                self._publish_event(system, notification)
                results[system] = "notified"
            except Exception as e:
                results[system] = f"failed: {str(e)}"
                logging.error("Failed to notify %s: %s", system, e)

        return results

    def _publish_event(self, system: str, notification: dict):
        """Publish to Pub/Sub topic for the system."""
        try:
            from google.cloud import pubsub_v1

            publisher = pubsub_v1.PublisherClient()
            topic = f"projects/{self._config.pubsub_project}/topics/{system}-events"
            data = json.dumps(notification).encode("utf-8")
            future = publisher.publish(topic, data)
            future.result(timeout=10)
            logging.info("Published retirement event to %s", topic)
        except ImportError:
            logging.warning(
                "google-cloud-pubsub not available, skipping notification to %s",
                system,
            )
        except Exception as e:
            logging.error("Failed to publish to %s: %s", system, e)
            raise


class ReportDistributor:
    """Distribute janitor reports to configured channels."""

    def __init__(self, config: ReportDistributionConfig):
        self._config = config

    def distribute(self, report) -> dict:
        """Distribute a janitor report to all configured channels."""
        results = {}
        report_markdown = report.to_markdown()
        report_date = str(report.report_date)

        # 1. Store to GCS
        gcs_result = self._upload_to_gcs(report_markdown, report_date)
        if gcs_result:
            results["storage"] = gcs_result

        # 2. Send Slack notification
        slack_result = self._send_slack(report, report_date)
        if slack_result:
            results["slack"] = self._config.slack_channel

        # 3. Send email for significant events
        if (
            report.retired_count > self._config.email_on_threshold
            or report.has_warnings
        ):
            email_result = self._send_email(report, report_date)
            if email_result:
                results["email"] = self._config.email_recipients

        return results

    def _upload_to_gcs(self, markdown: str, report_date: str) -> Optional[str]:
        """Upload report to Google Cloud Storage."""
        try:
            from google.cloud import storage

            client = storage.Client()
            bucket_name = self._config.storage_bucket.replace("gs://", "").split("/")[0]
            prefix = "/".join(
                self._config.storage_bucket.replace("gs://", "").split("/")[1:]
            )
            blob_path = f"{prefix}{report_date}/report.md"

            bucket = client.bucket(bucket_name)
            blob = bucket.blob(blob_path)
            blob.upload_from_string(markdown, content_type="text/markdown")

            path = f"gs://{bucket_name}/{blob_path}"
            logging.info("Report uploaded to %s", path)
            return path
        except ImportError:
            logging.warning("google-cloud-storage not available, skipping GCS upload")
            return None
        except Exception as e:
            logging.error("Failed to upload report to GCS: %s", e)
            return None

    def _send_slack(self, report, report_date: str) -> bool:
        """Send Slack notification with report summary."""
        if not self._config.slack_webhook_url:
            logging.info("No Slack webhook configured, skipping notification")
            return False

        try:
            import requests

            message = {
                "channel": self._config.slack_channel,
                "text": f"*Janitor Report - {report_date}*",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                f"*Janitor Agent Report — {report_date}*\n"
                                f"- Evaluated: {report.evaluated_count}\n"
                                f"- Retired: {report.retired_count}\n"
                                f"- Protected: {report.protected_count}\n"
                                f"- Duration: {report.duration_seconds:.1f}s"
                            ),
                        },
                    }
                ],
            }

            resp = requests.post(
                self._config.slack_webhook_url,
                json=message,
                timeout=10,
            )
            resp.raise_for_status()
            logging.info("Slack notification sent to %s", self._config.slack_channel)
            return True
        except ImportError:
            logging.warning("requests not available, skipping Slack notification")
            return False
        except Exception as e:
            logging.error("Failed to send Slack notification: %s", e)
            return False

    def _send_email(self, report, report_date: str) -> bool:
        """Send email notification for significant events."""
        try:
            import smtplib
            from email.mime.text import MIMEText

            smtp_host = os.environ.get("SMTP_HOST", "")
            smtp_port = int(os.environ.get("SMTP_PORT", "587"))
            smtp_user = os.environ.get("SMTP_USER", "")
            smtp_pass = os.environ.get("SMTP_PASS", "")
            from_addr = os.environ.get("JANITOR_EMAIL_FROM", "janitor@tradestream.io")

            if not smtp_host:
                logging.info("No SMTP host configured, skipping email")
                return False

            subject = f"[Action Required] Janitor Report - {report_date}"
            body = report.to_markdown()

            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = from_addr
            msg["To"] = ", ".join(self._config.email_recipients)

            with smtplib.SMTP(smtp_host, smtp_port) as server:
                if smtp_user:
                    server.starttls()
                    server.login(smtp_user, smtp_pass)
                server.sendmail(
                    from_addr, self._config.email_recipients, msg.as_string()
                )

            logging.info("Email sent to %s", self._config.email_recipients)
            return True
        except Exception as e:
            logging.error("Failed to send email: %s", e)
            return False
