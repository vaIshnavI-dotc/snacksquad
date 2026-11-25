"""Thin wrapper around the DetectifAI REST API. Owner: Person A."""
import io
import time
import uuid
import wave

import requests

from . import config


ERROR_MESSAGES = {
    "insufficient_speech": (422, "There is not enough speech in this clip to analyze.", False),
    "audio_too_short": (422, "The audio clip is too short to analyze.", False),
    "audio_too_long": (422, "The audio clip is too long to analyze.", False),
    "silent_audio": (422, "No speech was detected in this audio clip.", False),
    "corrupt_audio": (422, "The audio file could not be read. Try another copy.", False),
    "unsupported_format": (415, "This audio format is not supported.", False),
    "insufficient_credits": (402, "The detection service has insufficient credits.", False),
    "rate_limited": (429, "The detection service is busy. Please try again shortly.", True),
    "concurrency_limited": (429, "Too many detections are running. Please try again shortly.", True),
    "server_busy": (503, "The detection service is temporarily busy.", True),
    "inference_overloaded": (503, "The detection service is temporarily overloaded.", True),
    "inference_failed": (502, "The detection service could not analyze this clip.", True),
    "inference_timeout": (504, "The detection service took too long to respond.", True),
    "invalid_api_key": (401, "The detection service is not configured correctly.", False),
    "missing_file": (400, "Please upload an audio file.", False),
}


class DetectifError(Exception):
    def __init__(self, status: int, code: str, message: str, retryable: bool = False):
        super().__init__(message)
        self.status, self.code, self.message, self.retryable = status, code, message, retryable


def _headers(extra: dict | None = None) -> dict:
    if not config.API_KEY:
        raise DetectifError(500, "missing_api_key", "Server has no API key configured.")
    h = {"Authorization": f"Bearer {config.API_KEY}"}
    h.update(extra or {})
    return h


def _raise(resp: requests.Response) -> None:
    try:
        err = resp.json().get("error", {})
    except (ValueError, AttributeError):
        err = {}
    code = err.get("code", "unknown_error")
    status, message, retryable = ERROR_MESSAGES.get(
        code,
        (
            resp.status_code,
            "The detection service returned an unexpected error.",
            resp.status_code in (429, 500, 502, 503, 504),
        ),
    )
    raise DetectifError(status, code, message, retryable)


def _check_wav_duration(filename: str, data: bytes) -> None:
    """Reject clearly out-of-range WAV clips without making an API request."""
    if not filename.lower().endswith(".wav"):
        return
    try:
        with wave.open(io.BytesIO(data), "rb") as audio:
            duration = audio.getnframes() / audio.getframerate()
    except (wave.Error, EOFError, OSError, ZeroDivisionError):
        return
    if duration < config.MIN_CLIP_SECONDS:
        raise DetectifError(
            422, "audio_too_short",
            f"Audio must be at least {config.MIN_CLIP_SECONDS} seconds long.",
        )
    if duration > config.MAX_CLIP_SECONDS:
        raise DetectifError(
            422, "audio_too_long",
            f"Audio must be no longer than {config.MAX_CLIP_SECONDS} seconds.",
        )


def _retry_after(resp: requests.Response) -> float:
    try:
        return max(0.0, float(resp.headers.get("Retry-After", "2")))
    except (TypeError, ValueError):
        return 2.0


def detect(filename: str, data: bytes, retries: int = 2) -> dict:
    """POST /v1/deepfake/detect. Same Idempotency-Key is reused on retries (retries are free)."""
    _check_wav_duration(filename, data)
    key = str(uuid.uuid4())
    for attempt in range(retries + 1):
        try:
            resp = requests.post(
                f"{config.BASE_URL}/v1/deepfake/detect",
                headers=_headers({"Idempotency-Key": key}),
                files={"file": (filename, data)},
                timeout=130,
            )
        except requests.RequestException as exc:
            raise DetectifError(503, "service_unavailable",
                                "The detection service could not be reached.", True) from exc
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code in (429, 503) and attempt < retries:
            time.sleep(_retry_after(resp))
            continue
        if resp.status_code in (500, 502, 504) and attempt < retries:
            time.sleep(2 * (attempt + 1))
            continue
        _raise(resp)


def send_feedback(operation_id: str, correct: bool, label=None, note=None) -> dict:
    body = {"correct": correct, "label": label, "note": note}
    try:
        resp = requests.post(f"{config.BASE_URL}/v1/operations/{operation_id}/feedback",
                             headers=_headers(), json=body, timeout=30)
    except requests.RequestException as exc:
        raise DetectifError(503, "service_unavailable",
                            "The detection service could not be reached.", True) from exc
    if resp.status_code != 200:
        _raise(resp)
    return resp.json()


def credits() -> dict:
    try:
        resp = requests.get(f"{config.BASE_URL}/v1/credits", headers=_headers(), timeout=30)
    except requests.RequestException as exc:
        raise DetectifError(503, "service_unavailable",
                            "The detection service could not be reached.", True) from exc
    if resp.status_code != 200:
        _raise(resp)
    return resp.json()
