"""JSON-backed trusted contacts. Store only data teammates have consented to share."""
import json

from . import config

SAMPLE_CONTACTS = [
    {
        "id": "sample-mom",
        "name": "Asha Sharma",
        "relationship": "Mother",
        "phone_masked": "+91 ••••• 12345",
        "telegram_chat_id": None,
        "safe_word_hint": "Ask about the blue umbrella",
        "callback_number_masked": "+91 ••••• 12345",
    },
    {
        "id": "sample-friend",
        "name": "Ravi Mehta",
        "relationship": "Friend",
        "phone_masked": "+91 ••••• 67890",
        "telegram_chat_id": None,
        "safe_word_hint": "Ask about the old college nickname",
        "callback_number_masked": "+91 ••••• 67890",
    },
]


def _contacts_path():
    return config.DATA_DIR / "contacts.json"


def save_contacts(contact_list: list[dict]) -> None:
    """Persist the trusted contacts supplied by consenting teammates."""
    path = _contacts_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(contact_list, indent=2), encoding="utf-8")


def list_contacts() -> list[dict]:
    path = _contacts_path()
    if not path.exists():
        save_contacts(SAMPLE_CONTACTS)
    return json.loads(path.read_text(encoding="utf-8"))


def get_contact(contact_id: str) -> dict | None:
    return next((contact for contact in list_contacts() if contact["id"] == contact_id), None)
