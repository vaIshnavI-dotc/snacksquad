import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("DETECTIF_API_KEY", "")
BASE_URL = os.getenv("DETECTIF_BASE_URL", "https://platform.detectif.ai")
HIGH_RISK_SCORE = float(os.getenv("HIGH_RISK_SCORE", "0.80"))
LOW_RISK_SCORE = float(os.getenv("LOW_RISK_SCORE", "0.30"))
