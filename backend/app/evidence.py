"""Build a user-reviewable complaint summary from an existing detection result."""
from datetime import datetime, timezone
from html import escape

from .risk import LIMITATIONS

TITLE = "Complaint-ready summary (user must review and verify before filing)"

NEXT_STEPS = {
    "en": [
        "Call 1930 for help reporting cyber financial fraud.",
        "File a complaint at https://cybercrime.gov.in.",
        "Keep the original audio file unchanged.",
    ],
    "hi": [
        "साइबर वित्तीय धोखाधड़ी की रिपोर्ट करने के लिए 1930 पर कॉल करें।",
        "https://cybercrime.gov.in पर शिकायत दर्ज करें।",
        "मूल ऑडियो फ़ाइल को बिना बदले सुरक्षित रखें।",
    ],
}

DISCLAIMER = {
    "en": "This detection result is evidence, not proof. Review and verify all details before filing.",
    "hi": "यह पहचान परिणाम साक्ष्य है, प्रमाण नहीं। शिकायत दर्ज करने से पहले सभी विवरण जाँचें और सत्यापित करें।",
}


def build_evidence_packet(
    check_result: dict,
    caller_claimed_name: str | None,
    context_note: str | None,
    lang: str,
) -> dict:
    """Create a printable packet without making another detection API request."""
    language = lang if lang in ("en", "hi") else "en"
    return {
        "title": TITLE,
        "incident_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "clip_duration_seconds": check_result.get("duration_seconds"),
        "claimed_caller_identity": caller_claimed_name or "Not provided",
        "context_note": context_note or "",
        "verdict": check_result["verdict"],
        "score": check_result["score"],
        "risk_level": check_result["risk"],
        "segments": check_result.get("segments", []),
        "limitations": LIMITATIONS[language],
        "disclaimer": DISCLAIMER[language],
        "next_steps": NEXT_STEPS[language],
        "language": language,
    }


def render_html(packet: dict) -> str:
    """Render a self-contained printable HTML summary with escaped user/API text."""
    segments = "".join(
        "<tr>"
        f"<td>{escape(str(segment.get('start', '')))}</td>"
        f"<td>{escape(str(segment.get('end', '')))}</td>"
        f"<td>{escape(str(segment.get('score', '')))}</td>"
        f"<td>{escape(str(segment.get('verdict', '')))}</td>"
        "</tr>"
        for segment in packet.get("segments", [])
    )
    limitations = "".join(f"<li>{escape(item)}</li>" for item in packet["limitations"])
    next_steps = "".join(f"<li>{escape(item)}</li>" for item in packet["next_steps"])
    fields = (
        ("Incident timestamp (UTC)", packet["incident_timestamp_utc"]),
        ("Clip duration (seconds)", packet["clip_duration_seconds"]),
        ("Claimed caller identity", packet["claimed_caller_identity"]),
        ("Verdict", packet["verdict"]),
        ("Score", packet["score"]),
        ("Risk level", packet["risk_level"]),
    )
    details = "".join(
        f"<p><strong>{escape(label)}:</strong> {escape(str(value if value is not None else 'Not available'))}</p>"
        for label, value in fields
    )
    context = (
        f"<p><strong>Context note:</strong> {escape(packet['context_note'])}</p>"
        if packet.get("context_note") else ""
    )
    return (
        "<!doctype html><html lang=\""
        + escape(packet["language"])
        + "\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" "
        "content=\"width=device-width, initial-scale=1\"><title>"
        + escape(packet["title"])
        + "</title><style>body{font:16px/1.5 Arial,sans-serif;max-width:900px;"
        "margin:2rem auto;padding:0 1rem;color:#222}h1{font-size:1.5rem}"
        "table{border-collapse:collapse;width:100%}th,td{border:1px solid #bbb;"
        "padding:.5rem;text-align:left}th{background:#eee}.notice{border-left:4px "
        "solid #a33;padding:.75rem;background:#fff5f5}@media print{body{margin:0}}</style>"
        "</head><body><h1>"
        + escape(packet["title"])
        + "</h1>"
        + details
        + context
        + "<h2>Segments</h2><table><thead><tr><th>Start</th><th>End</th>"
        "<th>Score</th><th>Verdict</th></tr></thead><tbody>"
        + segments
        + "</tbody></table><h2>Limitations</h2><ul>"
        + limitations
        + "</ul><p class=\"notice\"><strong>"
        + escape(packet["disclaimer"])
        + "</strong></p><h2>Next steps</h2><ul>"
        + next_steps
        + "</ul></body></html>"
    )
