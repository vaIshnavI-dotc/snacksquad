"""FastAPI app. Owner: Person A. Run: uvicorn backend.app.main:app --reload"""
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import alerts, check_store, contacts, evidence
from . import detectif_client as dc
from .risk import build_response

app = FastAPI(title="Scam Shield")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _error(code: str, message: str, retryable: bool, status: int) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "retryable": retryable}},
    )


def _err(e: dc.DetectifError) -> JSONResponse:
    return _error(e.code, e.message, e.retryable, e.status)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request, exc: RequestValidationError):
    return _error("invalid_request", "The request is missing or has invalid fields.", False, 422)


@app.exception_handler(HTTPException)
async def http_error_handler(_request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {}
    return _error(
        detail.get("code", "not_found" if exc.status_code == 404 else "http_error"),
        detail.get("message", str(exc.detail) if isinstance(exc.detail, str) else "Request failed."),
        detail.get("retryable", False),
        exc.status_code,
    )


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/credits")
def get_credits():
    try:
        return {"available": dc.credits().get("available")}
    except dc.DetectifError as e:
        return _err(e)


@app.get("/api/contacts")
def get_contacts():
    return contacts.list_contacts()


@app.post("/api/check")
def check(
    file: UploadFile = File(...),
    lang: str = Form("en"),
    claimed_contact_id: str | None = Form(None),
):
    claimed_contact = None
    if claimed_contact_id:
        claimed_contact = contacts.get_contact(claimed_contact_id)
        if claimed_contact is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "contact_not_found", "message": "Trusted contact was not found."},
            )
    try:
        data = file.file.read()
        api_json = dc.detect(file.filename or "audio.wav", data)
        result = build_response(api_json, lang)
        result["claimed_contact"] = claimed_contact
        if result["risk"] == "high":
            # Call blocking is simulated in the demo UI; this endpoint never blocks a phone call.
            result["action"] = {
                "type": "block_and_callback",
                "callback_number_masked": (
                    claimed_contact.get("callback_number_masked") if claimed_contact else None
                ),
                "safe_word_hint": claimed_contact.get("safe_word_hint") if claimed_contact else None,
                "note": "Call blocking is simulated for this demo; hang up and call back using a trusted number.",
            }
        elif result["risk"] == "medium":
            result["action"] = {"type": "verify_first"}
        else:
            result["action"] = {"type": "proceed_with_caution"}
        check_store.save_check(result["operation_id"], result)
        return result
    except dc.DetectifError as e:
        return _err(e)


class AlertRequest(BaseModel):
    operation_id: str
    contact_id: str
    confirm: bool


@app.post("/api/alert")
def create_alert(body: AlertRequest):
    if body.confirm is not True:
        return _error(
            "confirmation_required",
            "Confirm before sending an impersonation alert.",
            False,
            400,
        )
    check_result = check_store.get_check(body.operation_id)
    if check_result is None:
        raise HTTPException(status_code=404, detail="Check result was not found.")
    contact = contacts.get_contact(body.contact_id)
    if contact is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "contact_not_found", "message": "Trusted contact was not found."},
        )
    caller = contact["name"]
    message = (
        f"Scam Shield alert: a suspicious call claiming to be {caller} "
        f"was assessed as {check_result['risk']} risk. Verify through a trusted channel."
    )
    alert = alerts.log_alert(
        body.contact_id,
        body.operation_id,
        check_result["risk"],
        message,
        contact,
    )
    return alert


@app.get("/api/alerts")
def get_alerts():
    return alerts.list_alerts()


@app.get("/api/evidence/{operation_id}")
def get_evidence(
    operation_id: str,
    format: str = "json",
    caller: str = "",
    lang: str = "en",
):
    if format not in ("json", "html"):
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_format", "message": "Format must be json or html."},
        )
    check_result = check_store.get_check(operation_id)
    if check_result is None:
        raise HTTPException(status_code=404, detail="Check result was not found.")
    packet = evidence.build_evidence_packet(check_result, caller, None, lang)
    if format == "html":
        return HTMLResponse(evidence.render_html(packet))
    return packet


class Feedback(BaseModel):
    correct: bool
    label: str | None = None
    note: str | None = None


@app.post("/api/feedback/{operation_id}")
def feedback(operation_id: str, body: Feedback):
    try:
        dc.send_feedback(operation_id, body.correct, body.label, body.note)
        return {"ok": True}
    except dc.DetectifError as e:
        return _err(e)


# Serve the frontend (must be last)
FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
