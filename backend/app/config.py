import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("DETECTIF_API_KEY", "")
BASE_URL = os.getenv("DETECTIF_BASE_URL", "https://platform.detectif.ai")
HIGH_RISK_SCORE = float(os.getenv("HIGH_RISK_SCORE", "0.80"))
LOW_RISK_SCORE = float(os.getenv("LOW_RISK_SCORE", "0.30"))
MAX_CLIP_SECONDS = int(os.getenv("MAX_CLIP_SECONDS", "120"))
MIN_CLIP_SECONDS = int(os.getenv("MIN_CLIP_SECONDS", "4"))
DATA_DIR = Path(os.getenv("DATA_DIR", Path(__file__).resolve().parents[1] / "data"))
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
