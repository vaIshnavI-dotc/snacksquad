"""Map Aletheia output to a risk level and advice. Owner: Person A.
Thresholds are placeholders: tune them with eval/batch_eval.py results.
Decide primarily with `verdict`; the docs say not to rely on the score alone."""
from . import config

DISCLAIMER = {
    "en": "The result is evidence, not proof. Confirm through another channel.",
    "hi": "यह परिणाम साक्ष्य है, प्रमाण नहीं। किसी अन्य तरीके से पुष्टि करें।",
}

LIMITATIONS = {
    "en": [
        "Results are evidence, not proof.",
        "Short clips (under 10 seconds) and phone-quality audio are less reliable.",
        "The service works best with English and Hindi audio.",
    ],
    "hi": [
        "परिणाम साक्ष्य हैं, प्रमाण नहीं।",
        "छोटी क्लिप (10 सेकंड से कम) और फोन-क्वालिटी ऑडियो के परिणाम कम विश्वसनीय हो सकते हैं।",
        "यह सेवा अंग्रेज़ी और हिंदी ऑडियो पर सबसे अच्छा काम करती है।",
    ],
}

ADVICE = {
    "high": {
        "en": [
            "Do not send money or share OTPs, PINs or passwords.",
            "Hang up and call the person back on a number you already have saved.",
            "Ask a question only the real person could answer.",
            "Report scam calls at cybercrime.gov.in or call 1930 (India).",
        ],
        "hi": [
            "पैसे, OTP, PIN या पासवर्ड न भेजें।",
            "कॉल काट दें और उस व्यक्ति के सेव किए हुए नंबर पर वापस कॉल करें।",
            "ऐसा सवाल पूछें जिसका जवाब सिर्फ असली व्यक्ति दे सके।",
            "ठगी की शिकायत cybercrime.gov.in पर या 1930 पर करें।",
        ],
    },
    "medium": {
        "en": [
            "This voice may be AI-generated. Do not act on urgent requests yet.",
            "Verify by calling back on a saved number or asking a personal question.",
        ],
        "hi": [
            "यह आवाज़ AI से बनी हो सकती है। जल्दबाज़ी वाली माँग पर अभी कार्रवाई न करें।",
            "सेव किए हुए नंबर पर कॉल करके या निजी सवाल पूछकर पुष्टि करें।",
        ],
    },
    "low": {
        "en": [
            "No strong signs of AI generation found.",
            "Still be careful with any request for money or codes.",
        ],
        "hi": [
            "AI से बनी आवाज़ के मज़बूत संकेत नहीं मिले।",
            "फिर भी पैसे या कोड माँगने वाले अनुरोधों में सावधानी रखें।",
        ],
    },
}


def risk_level(verdict: str, score: float) -> str:
    if verdict == "fake":
        return "high" if score >= config.HIGH_RISK_SCORE else "medium"
    return "low" if score < config.LOW_RISK_SCORE else "medium"


def build_response(api_json: dict, lang: str = "en") -> dict:
    lang = lang if lang in ("en", "hi") else "en"
    res = api_json["result"]
    level = risk_level(res["verdict"], res["score"])
    return {
        "operation_id": api_json["operation_id"],
        "verdict": res["verdict"],
        "score": res["score"],
        "risk": level,
        "duration_seconds": res.get("duration_seconds"),
        "segments": res.get("segments", []),
        "advice": ADVICE[level][lang],
        "disclaimer": DISCLAIMER[lang],
        "limitations": LIMITATIONS[lang],
        "credits_left": api_json.get("credits", {}).get("balance"),
    }
