"""Email service using Resend API."""

import logging

import resend

from ..config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending transactional emails via Resend."""

    def __init__(self):
        resend.api_key = settings.RESEND_API_KEY
        self.from_email = "TradeStream <noreply@tradestream.io>"

    async def send_verification_email(self, to_email: str, token: str) -> bool:
        """Send email verification link."""
        verify_url = f"{settings.FRONTEND_URL}/auth/verify-email?token={token}"

        try:
            resend.Emails.send(
                {
                    "from": self.from_email,
                    "to": [to_email],
                    "subject": "Verify your TradeStream account",
                    "html": f"""
                <h1>Welcome to TradeStream!</h1>
                <p>Click the button below to verify your email address:</p>
                <p>
                    <a href="{verify_url}"
                       style="display:inline-block;padding:12px 24px;
                              background:#0ea5e9;color:white;text-decoration:none;
                              border-radius:6px;font-weight:600;">
                        Verify Email
                    </a>
                </p>
                <p>Or copy this link: {verify_url}</p>
                <p>This link expires in 24 hours.</p>
                <p style="color:#666;font-size:12px;">
                    If you didn't create an account, you can ignore this email.
                </p>
                """,
                }
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send verification email: {e}")
            return False

    async def send_password_reset_email(self, to_email: str, token: str) -> bool:
        """Send password reset link."""
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"

        try:
            resend.Emails.send(
                {
                    "from": self.from_email,
                    "to": [to_email],
                    "subject": "Reset your TradeStream password",
                    "html": f"""
                <h1>Password Reset Request</h1>
                <p>Click the button below to reset your password:</p>
                <p>
                    <a href="{reset_url}"
                       style="display:inline-block;padding:12px 24px;
                              background:#0ea5e9;color:white;text-decoration:none;
                              border-radius:6px;font-weight:600;">
                        Reset Password
                    </a>
                </p>
                <p>Or copy this link: {reset_url}</p>
                <p>This link expires in 1 hour.</p>
                <p style="color:#666;font-size:12px;">
                    If you didn't request this, you can ignore this email.
                </p>
                """,
                }
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send password reset email: {e}")
            return False

    async def send_welcome_email(self, to_email: str, display_name: str) -> bool:
        """Send welcome email after verification."""
        try:
            resend.Emails.send(
                {
                    "from": self.from_email,
                    "to": [to_email],
                    "subject": "Welcome to TradeStream!",
                    "html": f"""
                <h1>Welcome, {display_name}!</h1>
                <p>Your TradeStream account is ready to go.</p>
                <h2>Get Started:</h2>
                <ul>
                    <li>View real-time trading signals</li>
                    <li>Follow top signal providers</li>
                    <li>Build your watchlist</li>
                    <li>Earn achievements and climb the leaderboard</li>
                </ul>
                <p>
                    <a href="{settings.FRONTEND_URL}/dashboard"
                       style="display:inline-block;padding:12px 24px;
                              background:#0ea5e9;color:white;text-decoration:none;
                              border-radius:6px;font-weight:600;">
                        Go to Dashboard
                    </a>
                </p>
                """,
                }
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send welcome email: {e}")
            return False


# Singleton instance
email_service = EmailService()
