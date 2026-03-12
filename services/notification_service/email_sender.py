"""Email sender for trading signals using SMTP."""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from absl import logging


class EmailSender:
    """Sends trading signals via email using an SMTP server."""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        from_addr: str,
        to_addrs: list[str],
        use_tls: bool = True,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_addr = from_addr
        self.to_addrs = to_addrs
        self.use_tls = use_tls

    def send_signal(self, signal: dict) -> bool:
        """Format and send a trading signal via email.

        Returns:
            True if the email was sent successfully.
        """
        action = signal.get("action", "UNKNOWN")
        symbol = signal.get("symbol", "N/A")
        subject = f"TradeStream Signal: {action} {symbol}"

        html_body = self._render_html(signal)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.from_addr
        msg["To"] = ", ".join(self.to_addrs)

        plain = self._render_plain(signal)
        msg.attach(MIMEText(plain, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                if self.username:
                    server.login(self.username, self.password)
                server.sendmail(self.from_addr, self.to_addrs, msg.as_string())
            logging.info("Email sent for %s to %s", symbol, self.to_addrs)
            return True
        except Exception as e:
            logging.error("Failed to send email: %s", e)
            return False

    def _render_plain(self, signal: dict) -> str:
        action = signal.get("action", "UNKNOWN")
        symbol = signal.get("symbol", "N/A")
        confidence = signal.get("confidence", 0)
        score = signal.get("opportunity_score", 0)
        summary = signal.get("summary", "")

        lines = [
            f"TradeStream Signal: {action} {symbol}",
            f"Confidence: {confidence:.0%}",
        ]
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

        color = {"BUY": "#00CC00", "SELL": "#CC0000", "HOLD": "#FFAA00"}.get(
            action, "#808080"
        )

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
      <tr>
        <td style="padding:4px 8px;font-weight:bold;">Action</td>
        <td style="padding:4px 8px;">{action}</td>
      </tr>
      <tr>
        <td style="padding:4px 8px;font-weight:bold;">Confidence</td>
        <td style="padding:4px 8px;">{confidence:.0%}</td>
      </tr>
      {score_row}
    </table>
    {summary_block}
    <p style="margin-top:16px;font-size:11px;color:#999;">Sent by TradeStream Signal Service</p>
  </div>
</div>"""
