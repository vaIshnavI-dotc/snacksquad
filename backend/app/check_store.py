"""Persist check results by operation ID so follow-up actions never re-run detection."""
import json

from . import config


def _checks_path():
    return config.DATA_DIR / "checks.json"


def save_check(operation_id: str, result: dict) -> None:
    path = _checks_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    checks = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    checks[operation_id] = result
    path.write_text(json.dumps(checks, indent=2), encoding="utf-8")


def get_check(operation_id: str) -> dict | None:
    path = _checks_path()
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8")).get(operation_id)
