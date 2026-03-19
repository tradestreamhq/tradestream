"""Email delivery channel with immediate and digest support."""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from absl import logging

from services.delivery.channels.base import DeliveryChannel, DeliveryResult


class EmailDeliveryChannel(DeliveryChannel):
    """Delivers signals via email (SMTP).

    Supports immediate single-signal delivery. For digest mode,
    the delivery router accumulates signals and calls send_digest().
    """

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int = 587,
        username: str = "",
        password: str = "",
        from_addr: str = "alerts@tradestream.io",
        use_tls: bool = True,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_addr = from_addr
        self.use_tls = use_tls

    @property
    def name(self) -> str:
        return "email"

    def send(self, signal: dict, recipient: str) -> DeliveryResult:
        """Send a single signal email to recipient (email address)."""
        action = signal.get("action", "UNKNOWN")
        symbol = signal.get("symbol", "N/A")
        subject = f"TradeStream Signal: {action} {symbol}"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.from_addr
        msg["To"] = recipient

        msg.attach(MIMEText(self._render_plain(signal), "plain"))
        msg.attach(MIMEText(self._render_html(signal), "html"))

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                if self.username:
                    server.login(self.username, self.password)
                server.sendmail(self.from_addr, [recipient], msg.as_string())
            return DeliveryResult.ok(self.name)
        except smtplib.SMTPRecipientsRefused:
            return DeliveryResult.fail(self.name, "Recipient refused", retryable=False)
        except Exception as e:
            return DeliveryResult.fail(self.name, str(e), retryable=True)

    def send_digest(self, signals: list[dict], recipient: str) -> DeliveryResult:
        """Send a digest of multiple signals in one email."""
        if not signals:
            return DeliveryResult.ok(self.name)

        subject = f"TradeStream Digest: {len(signals)} signals"
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.from_addr
        msg["To"] = recipient

        plain_parts = [self._render_plain(s) for s in signals]
        msg.attach(MIMEText("\n---\n".join(plain_parts), "plain"))

        html_parts = [self._render_html(s) for s in signals]
        separator = '<hr style="margin:16px 0;border:none;border-top:1px solid #ddd;">'
        msg.attach(MIMEText(separator.join(html_parts), "html"))

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                if self.username:
                    server.login(self.username, self.password)
                server.sendmail(self.from_addr, [recipient], msg.as_string())
            return DeliveryResult.ok(self.name)
        except Exception as e:
            return DeliveryResult.fail(self.name, str(e), retryable=True)

    def _render_plain(self, signal: dict) -> str:
        action = signal.get("action", "UNKNOWN")
        symbol = signal.get("symbol", "N/A")
        confidence = signal.get("confidence", 0)
        score = signal.get("opportunity_score", 0)
        summary = signal.get("summary", "")

        lines = [f"TradeStream Signal: {action} {symbol}", f"Confidence: {confidence:.0%}"]
        if score:
            lines.append(f"Opportunity Score: {score}")
        if summary:
            lines.append(f"\n{summary}")
        return "\n".join(lines)

    def _render_html(self, signal: dict) -> str:
        action = signal.get("action", "UNKNOWN")
        symbol = signal.get("symbol", "N/A")
        confidence = signal.get("confidence", 0)
        score = signal.get("opportunity_score", 0)
        summary = signal.get("summary", "")

        color = {"BUY": "#00CC00", "SELL": "#CC0000", "HOLD": "#FFAA00"}.get(action, "#808080")

        score_row = ""
        if score:
            score_row = f'<tr><td style="padding:4px 8px;font-weight:bold;">Opportunity Score</td><td style="padding:4px 8px;">{score}</td></tr>'

        summary_block = ""
        if summary:
            summary_block = f'<p style="margin-top:12px;color:#333;">{summary}</p>'

        return f"""\
<div style="font-family:Arial,sans-serif;max-width:480px;">
  <div style="background:{color};color:#fff;padding:12px 16px;border-radius:6px 6px 0 0;">
    <h2 style="margin:0;">{action} {symbol}</h2>
  </div>
  <div style="border:1px solid #ddd;border-top:none;padding:12px 16px;border-radius:0 0 6px 6px;">
    <table style="width:100%;border-collapse:collapse;">
      <tr><td style="padding:4px 8px;font-weight:bold;">Action</td><td style="padding:4px 8px;">{action}</td></tr>
      <tr><td style="padding:4px 8px;font-weight:bold;">Confidence</td><td style="padding:4px 8px;">{confidence:.0%}</td></tr>
      {score_row}
    </table>
    {summary_block}
    <p style="margin-top:16px;font-size:11px;color:#999;">Sent by TradeStream Signal Service</p>
  </div>
</div>"""
