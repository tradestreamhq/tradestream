"""Action dispatchers for alert rules.

Each dispatcher sends an alert notification through a specific channel.
"""

import json
import time

import requests

from services.shared.structured_logger import StructuredLogger

_log = StructuredLogger(service_name="alert_rules_engine")


def dispatch_action(action_type: str, action_params: dict, alert_message: str, context: dict) -> bool:
    """Dispatch an alert through the specified action channel.

    Returns True if the action was delivered successfully.
    """
    dispatcher = _DISPATCHERS.get(action_type)
    if dispatcher is None:
        _log.warning("Unknown action type", action_type=action_type)
        return False
    try:
        return dispatcher(action_params, alert_message, context)
    except Exception as e:
        _log.error("Action dispatch failed", action_type=action_type, error=str(e))
        return False


def _dispatch_webhook(params: dict, message: str, context: dict) -> bool:
    url = params.get("url", "")
    if not url:
        _log.warning("Webhook action missing URL")
        return False

    payload = {
        "alert_message": message,
        "context": context,
        "timestamp": time.time(),
    }
    headers = {"Content-Type": "application/json"}

    resp = requests.post(url, json=payload, headers=headers, timeout=10)
    if 200 <= resp.status_code < 300:
        return True
    _log.warning("Webhook returned non-2xx", status=resp.status_code, url=url)
    return False


def _dispatch_in_app(params: dict, message: str, context: dict) -> bool:
    """In-app notification via Redis pub/sub."""
    # In-app notifications are recorded as events by the engine.
    # This dispatcher is a no-op that always succeeds since the event
    # is already stored in the rule store's event list.
    _log.info("In-app alert", message=message)
    return True


def _dispatch_email(params: dict, message: str, context: dict) -> bool:
    """Email dispatch stub — delegates to the notification service's email sender in production."""
    to = params.get("to", "")
    if not to:
        _log.warning("Email action missing 'to' address")
        return False
    _log.info("Email alert dispatched", to=to, message=message)
    return True


def _dispatch_sms(params: dict, message: str, context: dict) -> bool:
    """SMS dispatch stub — would integrate with Twilio or similar in production."""
    phone = params.get("phone", "")
    if not phone:
        _log.warning("SMS action missing 'phone' number")
        return False
    _log.info("SMS alert dispatched", phone=phone, message=message)
    return True


_DISPATCHERS = {
    "webhook": _dispatch_webhook,
    "in_app": _dispatch_in_app,
    "email": _dispatch_email,
    "sms": _dispatch_sms,
}
