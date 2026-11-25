"""FastAPI app. Owner: Person A. Run: uvicorn backend.app.main:app --reload"""
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import detectif_client as dc
from .risk import build_response

app = FastAPI(title="Scam Shield")


def _err(e: dc.DetectifError):
    return JSONResponse(
        status_code=e.status,
        content={"error": {"code": e.code, "message": e.message, "retryable": e.retryable}},
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


@app.post("/api/check")
def check(file: UploadFile = File(...), lang: str = Form("en")):
    try:
        data = file.file.read()
        api_json = dc.detect(file.filename or "audio.wav", data)
        return build_response(api_json, lang)
    except dc.DetectifError as e:
        return _err(e)


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
