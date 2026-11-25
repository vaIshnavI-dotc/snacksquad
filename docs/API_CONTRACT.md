# API contract (backend <-> frontend)

Base: same origin. All responses JSON. Errors never leak the API key.

## POST /api/check
multipart/form-data: `file` (audio), optional `lang` = `en` | `hi` (default `en`)

200:
```json
{
  "operation_id": "op_...",
  "verdict": "fake",
  "score": 0.91,
  "risk": "high",
  "duration_seconds": 12.4,
  "segments": [{"start": 0, "end": 4, "score": 0.88, "verdict": "fake"}],
  "advice": ["..."],
  "disclaimer": "A score is evidence, not proof.",
  "credits_left": 4980
}
```
`risk` is one of `low`, `medium`, `high`.

Error (any non-200):
```json
{"error": {"code": "insufficient_speech", "message": "...", "retryable": false}}
```
Common codes: `insufficient_speech`, `audio_too_long`, `unsupported_format`,
`insufficient_credits`, `rate_limited`, `server_busy`, `missing_file`.

## POST /api/feedback/{operation_id}
JSON: `{"correct": true, "label": "real" | "fake" | null, "note": "optional"}`
200: `{"ok": true}`

## GET /api/credits
200: `{"available": 4980}`

## GET /api/health
200: `{"status": "ok"}`
