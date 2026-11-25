import io
import json
import wave

import pytest
import requests
from fastapi.testclient import TestClient

from backend.app import alerts, config
from backend.app.contacts import list_contacts, save_contacts
from backend.app import detectif_client as dc
from backend.app.detectif_client import DetectifError, _raise
from backend.app.evidence import build_evidence_packet, render_html
from backend.app.main import app
from backend.app.risk import build_response, risk_level


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    def fail_request(*_args, **_kwargs):
        raise AssertionError("Tests must not make network requests.")

    monkeypatch.setattr("requests.post", fail_request)
    monkeypatch.setattr("requests.get", fail_request)


def test_risk_uses_verdict_and_score():
    assert risk_level("fake", 0.1) == "medium"
    assert risk_level("real", 0.95) == "medium"


def test_evidence_html_contains_disclaimer_and_1930():
    packet = build_evidence_packet(
        {
            "verdict": "fake",
            "score": 0.91,
            "risk": "high",
            "duration_seconds": 12,
            "segments": [{"start": 0, "end": 4, "score": 0.9, "verdict": "fake"}],
        },
        "Asha",
        None,
        "en",
    )
    html = render_html(packet)
    assert "evidence, not proof" in html
    assert "1930" in html
    assert "<table>" in html


def test_contacts_load_from_json(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    contacts = list_contacts()
    assert len(contacts) == 2
    assert (tmp_path / "contacts.json").exists()
    assert json.loads((tmp_path / "contacts.json").read_text(encoding="utf-8")) == contacts
    save_contacts([contacts[0]])
    assert len(list_contacts()) == 1


def _wav_clip(seconds):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b"\0\0" * 8000 * seconds)
    return buffer.getvalue()


def test_short_wav_is_rejected_without_api_call():
    with pytest.raises(DetectifError) as raised:
        dc.detect("short.wav", _wav_clip(3))
    assert raised.value.code == "audio_too_short"


def test_long_wav_is_rejected_without_api_call(monkeypatch):
    monkeypatch.setattr(config, "MAX_CLIP_SECONDS", 5)
    with pytest.raises(DetectifError) as raised:
        dc.detect("long.wav", _wav_clip(6))
    assert raised.value.code == "audio_too_long"


def test_alert_requires_confirm_true():
    response = TestClient(app).post(
        "/api/alert",
        json={"operation_id": "missing", "contact_id": "sample-mom", "confirm": False},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "confirmation_required"


def test_check_alert_and_evidence_reuse_saved_result(monkeypatch, tmp_path):
    from backend.app import main

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        main.dc,
        "detect",
        lambda _filename, _data: {
            "operation_id": "op-check",
            "result": {
                "verdict": "fake",
                "score": 0.93,
                "duration_seconds": 14,
                "segments": [{"start": 0, "end": 5, "score": 0.93, "verdict": "fake"}],
            },
            "credits": {"balance": 20},
        },
    )
    client = TestClient(app)
    checked = client.post(
        "/api/check",
        data={"lang": "en", "claimed_contact_id": "sample-mom"},
        files={"file": ("voice.mp3", b"sample audio", "audio/mpeg")},
    )
    assert checked.status_code == 200
    result = checked.json()
    assert result["action"]["type"] == "block_and_callback"
    assert "simulated" in result["action"]["note"]

    alerted = client.post(
        "/api/alert",
        json={"operation_id": "op-check", "contact_id": "sample-mom", "confirm": True},
    )
    assert alerted.status_code == 200
    assert alerted.json()["status"] == "logged"
    packet = client.get("/api/evidence/op-check?format=json&caller=Asha&lang=hi")
    assert packet.status_code == 200
    assert packet.json()["verdict"] == "fake"


@pytest.mark.parametrize(
    ("code", "status", "retryable"),
    [
        ("insufficient_speech", 422, False),
        ("audio_too_short", 422, False),
        ("audio_too_long", 422, False),
        ("silent_audio", 422, False),
        ("corrupt_audio", 422, False),
        ("unsupported_format", 415, False),
        ("insufficient_credits", 402, False),
        ("rate_limited", 429, True),
        ("concurrency_limited", 429, True),
        ("server_busy", 503, True),
        ("inference_overloaded", 503, True),
        ("inference_failed", 502, True),
        ("inference_timeout", 504, True),
        ("invalid_api_key", 401, False),
        ("missing_file", 400, False),
    ],
)
def test_error_code_mapping(code, status, retryable):
    class Response:
        status_code = status

        @staticmethod
        def json():
            return {"error": {"code": code, "message": "provider message"}}

    with pytest.raises(DetectifError) as raised:
        _raise(Response())
    assert raised.value.code == code
    assert raised.value.status == status
    assert raised.value.retryable is retryable
    assert raised.value.message != "provider message"


def test_alert_is_logged_without_telegram(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "")
    alert = alerts.log_alert("sample-mom", "op-1", "high", "Please verify")
    assert alert["status"] == "logged"
    assert len(alerts.list_alerts()) == 1


def test_telegram_failure_marks_alert_failed(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "test-token")

    def fail_telegram(*_args, **_kwargs):
        raise requests.RequestException("offline")

    monkeypatch.setattr("backend.app.alerts.requests.post", fail_telegram)
    alert = alerts.log_alert(
        "sample-mom",
        "op-fail",
        "high",
        "Please verify",
        {"telegram_chat_id": "test-chat"},
    )
    assert alert["status"] == "failed"


def test_build_response_includes_limitations():
    response = build_response(
        {
            "operation_id": "op-2",
            "result": {"verdict": "real", "score": 0.1},
            "credits": {"balance": 10},
        },
        "hi",
    )
    assert response["limitations"]
    assert "स्कोर" not in response["disclaimer"]
