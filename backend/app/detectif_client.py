"""Thin wrapper around the DetectifAI REST API. Owner: Person A."""
import time
import uuid
import requests

from . import config


class DetectifError(Exception):
    def __init__(self, status, code, message, retryable=False):
        super().__init__(message)
        self.status, self.code, self.message, self.retryable = status, code, message, retryable


def _headers(extra=None):
    if not config.API_KEY:
        raise DetectifError(500, "missing_api_key", "Server has no API key configured.")
    h = {"Authorization": f"Bearer {config.API_KEY}"}
    h.update(extra or {})
    return h


def _raise(resp):
    try:
        err = resp.json().get("error", {})
    except Exception:
        err = {}
    retryable = resp.status_code in (429, 500, 502, 503, 504)
    raise DetectifError(resp.status_code, err.get("code", "unknown_error"),
                        err.get("message", "Request failed."), retryable)


def detect(filename: str, data: bytes, retries: int = 2) -> dict:
    """POST /v1/deepfake/detect. Same Idempotency-Key is reused on retries (retries are free)."""
    key = str(uuid.uuid4())
    for attempt in range(retries + 1):
        resp = requests.post(
            f"{config.BASE_URL}/v1/deepfake/detect",
            headers=_headers({"Idempotency-Key": key}),
            files={"file": (filename, data)},
            timeout=130,
        )
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code in (429, 503) and attempt < retries:
            time.sleep(int(resp.headers.get("Retry-After", "2")))
            continue
        if resp.status_code in (500, 502, 504) and attempt < retries:
            time.sleep(2 * (attempt + 1))
            continue
        _raise(resp)


def send_feedback(operation_id: str, correct: bool, label=None, note=None) -> dict:
    body = {"correct": correct, "label": label, "note": note}
    resp = requests.post(f"{config.BASE_URL}/v1/operations/{operation_id}/feedback",
                         headers=_headers(), json=body, timeout=30)
    if resp.status_code != 200:
        _raise(resp)
    return resp.json()


def credits() -> dict:
    resp = requests.get(f"{config.BASE_URL}/v1/credits", headers=_headers(), timeout=30)
    if resp.status_code != 200:
        _raise(resp)
    return resp.json()
