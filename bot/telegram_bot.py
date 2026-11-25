"""Run from the project root: TELEGRAM_BOT_TOKEN=... python bot/telegram_bot.py"""

import asyncio
import json
import logging
import mimetypes
import os
import sys
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

try:
    from telegram import Update
    from telegram.ext import (
        Application,
        CommandHandler,
        ContextTypes,
        MessageHandler,
        filters,
    )
except ImportError as exc:
    raise SystemExit(
        "Telegram bot dependency is missing. Install it with "
        "`pip install python-telegram-bot`."
    ) from exc


load_dotenv(Path(__file__).resolve().parents[1] / ".env")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
BACKEND_URL = os.getenv(
    "BACKEND_URL", "http://localhost:8000/api/check"
).strip()
MIN_DURATION_SECONDS = 4
MAX_DURATION_SECONDS = 120
MAX_FILE_BYTES = 20 * 1024 * 1024
REQUEST_TIMEOUT_SECONDS = 60

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("scam_shield.telegram_bot")

START_HELP = (
    "Send a 4–120 second voice note or audio clip and I’ll check it with Scam "
    "Shield. Only test voices you have consent to use."
)
TEXT_PROMPT = (
    "Please send a 4–120 second voice note or audio file to check it. "
    "Only test voices you have consent to use."
)
NEXT_STEPS = (
    "\n\nSafe next steps:\n"
    "• Don’t send money or share codes based on an urgent request.\n"
    "• Hang up and call back using a known, verified number; use a family "
    "safe word if available.\n"
    "• If impersonation is suspected, alert the person or a trusted contact.\n"
    "• Review and verify the details carefully before reporting at "
    "cybercrime.gov.in or calling 1930."
)


def _short_value(value: Any, limit: int = 500) -> str:
    """Render API-provided values without trusting their type or length."""
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    else:
        text = str(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _format_result(result: dict[str, Any]) -> str:
    lines = ["Scam Shield result — evidence, not proof."]
    for label, keys in (
        ("Verdict", ("verdict",)),
        ("Score", ("score",)),
        ("Risk", ("risk_level", "risk")),
        ("Alert", ("alert_status", "alert")),
        ("Evidence packet", ("evidence_packet", "packet")),
    ):
        for key in keys:
            if result.get(key) is not None:
                lines.append(f"{label}: {_short_value(result[key])}")
                break

    segments = result.get("segments")
    if isinstance(segments, list) and segments:
        rendered = []
        for segment in segments[:5]:
            if isinstance(segment, dict):
                start = segment.get("start")
                end = segment.get("end")
                verdict = segment.get("verdict")
                score = segment.get("score")
                details = []
                if start is not None and end is not None:
                    details.append(f"{_short_value(start, 30)}–{_short_value(end, 30)}s")
                if verdict is not None:
                    details.append(_short_value(verdict, 60))
                if score is not None:
                    details.append(f"score {_short_value(score, 30)}")
                if details:
                    rendered.append(", ".join(details))
        if rendered:
            lines.append("Segments: " + "; ".join(rendered))
        if len(segments) > 5:
            lines.append(f"Showing 5 of {len(segments)} segments.")

    packet_url = result.get("evidence_packet_url") or result.get("packet_url")
    if packet_url:
        lines.append(f"Cybercell Evidence Packet: {_short_value(packet_url, 500)}")
    elif not result.get("evidence_packet") and not result.get("packet"):
        lines.append("Cybercell Evidence Packet: no packet details or link were returned.")
    lines.append(NEXT_STEPS)
    return "\n".join(lines)


def _api_error_message(response: requests.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        body = {}
    error = body.get("error", {}) if isinstance(body, dict) else {}
    code = error.get("code") if isinstance(error, dict) else None
    message = error.get("message") if isinstance(error, dict) else None
    code_messages = {
        "audio_too_long": "That audio is longer than the backend allows. Please send a clip of 4–120 seconds.",
        "insufficient_speech": "There wasn’t enough usable speech to check. Please try a clear 4–120 second clip.",
        "unsupported_format": "The backend can’t read this audio format. Please send a common audio file or Telegram voice note.",
        "missing_file": "The backend did not receive the audio. Please try sending it again.",
    }
    if code in code_messages:
        return code_messages[code]
    if message:
        return f"The backend could not check this audio (HTTP {response.status_code}): {_short_value(message, 300)}"
    return f"The backend could not check this audio (HTTP {response.status_code}). Please try again."


def _check_with_backend(
    audio: bytes, filename: str, content_type: str
) -> tuple[int, dict[str, Any] | None, str | None]:
    try:
        response = requests.post(
            BACKEND_URL,
            files={"file": (filename, audio, content_type)},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        logger.warning("Backend request failed: %s", exc)
        return 0, None, (
            "I couldn’t reach the Scam Shield backend. Make sure it is running "
            "at the configured BACKEND_URL and try again."
        )

    if not response.ok:
        return response.status_code, None, _api_error_message(response)
    try:
        data = response.json()
    except ValueError:
        return response.status_code, None, (
            "The backend returned an unreadable response. Please try again."
        )
    if not isinstance(data, dict):
        return response.status_code, None, (
            "The backend returned an unexpected response. Please try again."
        )
    if "verdict" not in data or "score" not in data:
        return response.status_code, None, (
            "The backend response did not include a verdict and score, so no "
            "result can be shown. Please try again."
        )
    return response.status_code, data, None


async def _reply(update: Update, text: str) -> None:
    if update.effective_message:
        await update.effective_message.reply_text(text)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply(update, f"Welcome to Scam Shield.\n\n{START_HELP}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply(update, START_HELP)


async def text_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply(update, TEXT_PROMPT)


async def process_audio(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    telegram_file: Any,
    filename: str,
    content_type: str,
    duration: int | None,
    file_size: int | None,
) -> None:
    if duration is not None and not MIN_DURATION_SECONDS <= duration <= MAX_DURATION_SECONDS:
        await _reply(
            update,
            "Audio must be 4–120 seconds long. Please send a clip within that range.",
        )
        return
    if file_size is not None and file_size > MAX_FILE_BYTES:
        await _reply(
            update,
            "That file is over Telegram’s 20 MB download limit for this bot. "
            "Please send a smaller audio clip.",
        )
        return

    try:
        audio = bytes(await telegram_file.download_as_bytearray())
    except Exception:
        logger.exception("Could not download Telegram audio")
        await _reply(update, "I couldn’t download that audio. Please send it again.")
        return

    if not audio:
        await _reply(update, "The audio file was empty. Please try sending it again.")
        return
    if len(audio) > MAX_FILE_BYTES:
        await _reply(update, "That file is too large to process. Please send a smaller clip.")
        return

    await _reply(update, "Checking the audio…")
    _, result, error = await asyncio.to_thread(
        _check_with_backend, audio, filename, content_type
    )
    if error:
        await _reply(update, error)
        return

    if result is None:
        await _reply(update, "The backend did not return a result. Please try again.")
        return
    checked_duration = result.get("duration_seconds")
    if isinstance(checked_duration, (int, float)) and not (
        MIN_DURATION_SECONDS <= checked_duration <= MAX_DURATION_SECONDS
    ):
        await _reply(
            update,
            "The backend reports this clip is outside the 4–120 second range, "
            "so I can’t provide a result. Please send a clip within that range.",
        )
        return
    await _reply(update, _format_result(result))


async def voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message or not message.voice:
        return
    voice = message.voice
    try:
        telegram_file = await context.bot.get_file(voice.file_id)
    except Exception:
        logger.exception("Could not retrieve Telegram voice file")
        await _reply(update, "I couldn’t retrieve that voice note. Please send it again.")
        return
    await process_audio(
        update,
        context,
        telegram_file,
        "voice.ogg",
        "audio/ogg",
        voice.duration,
        voice.file_size,
    )


async def audio_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message or not message.audio:
        return
    audio = message.audio
    filename = os.path.basename(audio.file_name or "audio")
    guessed_type = mimetypes.guess_type(filename)[0]
    content_type = (
        audio.mime_type
        if audio.mime_type and audio.mime_type.startswith("audio/")
        else guessed_type or audio.mime_type or "application/octet-stream"
    )
    try:
        telegram_file = await context.bot.get_file(audio.file_id)
    except Exception:
        logger.exception("Could not retrieve Telegram audio file")
        await _reply(update, "I couldn’t retrieve that audio file. Please send it again.")
        return
    await process_audio(
        update,
        context,
        telegram_file,
        filename,
        content_type,
        audio.duration,
        audio.file_size,
    )


async def document_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    document = message.document if message else None
    if not document:
        return
    filename = os.path.basename(document.file_name or "audio")
    guessed_type = mimetypes.guess_type(filename)[0]
    content_type = document.mime_type or guessed_type
    audio_extensions = {
        ".aac", ".flac", ".m4a", ".mp3", ".oga", ".ogg", ".opus", ".wav", ".webm"
    }
    if not (
        (content_type and content_type.startswith("audio/"))
        or Path(filename).suffix.lower() in audio_extensions
    ):
        await _reply(update, TEXT_PROMPT)
        return
    if not (content_type and content_type.startswith("audio/")):
        content_type = guessed_type or "application/octet-stream"
    try:
        telegram_file = await context.bot.get_file(document.file_id)
    except Exception:
        logger.exception("Could not retrieve Telegram audio document")
        await _reply(update, "I couldn’t retrieve that audio file. Please send it again.")
        return
    await process_audio(
        update,
        context,
        telegram_file,
        filename,
        content_type,
        None,
        document.file_size,
    )


def main() -> None:
    if not TOKEN:
        print(
            "Error: TELEGRAM_BOT_TOKEN is missing. Set it in .env or the environment.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    if not BACKEND_URL:
        print("Error: BACKEND_URL must not be empty.", file=sys.stderr)
        raise SystemExit(1)

    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.VOICE, voice_message))
    application.add_handler(MessageHandler(filters.AUDIO, audio_message))
    application.add_handler(MessageHandler(filters.Document.ALL, document_message))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, text_prompt)
    )
    logger.info("Starting Scam Shield Telegram bot; backend: %s", BACKEND_URL)
    application.run_polling()


if __name__ == "__main__":
    main()
