# Scam Shield: "Check Before You Forward"

CMRIT x DetectifAI Hackathon, Track 01 (Scam Shield), built on **Aletheia** deepfake detection.

Upload or forward a voice note. We check it with Aletheia and show a Low / Medium / High
risk card, a timeline of which parts sound AI-generated, and a clear next step.
A score is evidence, not proof, and the app says so.

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # then paste your DETECTIF_API_KEY
python backend/scripts/test_api.py path/to/clip.wav   # sanity check the API first
uvicorn backend.app.main:app --reload                 # open http://127.0.0.1:8000
```

## Structure
See `docs/TEAM_SPLIT.md` for who owns what, and `docs/API_CONTRACT.md` for the
JSON the backend returns to the frontend.

## How it works
1. Frontend sends audio to `POST /api/check`.
2. Backend forwards it to `POST https://platform.detectif.ai/v1/deepfake/detect`.
3. Backend maps `verdict` + `score` to a risk level and adds advice (English / Hindi).
4. Frontend shows the risk card, segment timeline and a "Was this right?" button
   (calls `POST /v1/operations/{id}/feedback`).

## Honest results
TODO (Person C): paste accuracy table and failure cases from `eval/results.csv`.

## Limitations
- Works best on English and Hindi; other languages may be less reliable.
- Phone-quality audio is less reliable than clean recordings.
- Under 10 seconds of speech gives more false alarms.
- A score is a signal, not proof. Always verify through another channel.

## Consent
Only voices of team members who gave permission were recorded or cloned.
