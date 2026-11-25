"""Append user-confirmed alerts to local JSON and optionally send Telegram messages."""
import json
from datetime import datetime, timezone

import requests

from . import config


def _alerts_path():
    return config.DATA_DIR / "alerts.json"


def _read_alerts() -> list[dict]:
    path = _alerts_path()
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def send_telegram(contact: dict, text: str) -> bool | None:
    """Send only when both the optional bot token and contact chat ID are configured."""
    token = config.TELEGRAM_BOT_TOKEN
    chat_id = contact.get("telegram_chat_id")
    if not token or not chat_id:
        return None
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )
        return response.ok
    except requests.RequestException:
        return False


def log_alert(
    contact_id: str,
    operation_id: str,
    risk: str,
    message: str,
    contact: dict | None = None,
) -> dict:
    """Persist a confirmed alert; optional Telegram failures are recorded without raising."""
    path = _alerts_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    alerts = _read_alerts()
    alert = {
        "contact_id": contact_id,
        "operation_id": operation_id,
        "risk": risk,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "logged",
    }
    if contact is not None and config.TELEGRAM_BOT_TOKEN and contact.get("telegram_chat_id"):
        if send_telegram(contact, message) is False:
            alert["status"] = "failed"
    alerts.append(alert)
    path.write_text(json.dumps(alerts, indent=2), encoding="utf-8")
    return alert


def list_alerts() -> list[dict]:
    return _read_alerts()
