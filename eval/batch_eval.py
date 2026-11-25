"""Run all sample clips through Aletheia and report accuracy. Owner: Person C. Costs credits!"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app import detectif_client as dc  # noqa: E402

EXTS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm"}
rows = []
for folder in ("real", "fake", "phone_noisy"):
    for p in sorted((ROOT / "eval" / "samples" / folder).glob("*")):
        if p.suffix.lower() not in EXTS:
            continue
        truth = "fake" if (folder == "fake" or p.name.startswith("fake_")) else "real"
        try:
            out = dc.detect(p.name, p.read_bytes())
            pred, score = out["result"]["verdict"], out["result"]["score"]
        except dc.DetectifError as e:
            pred, score = f"error:{e.code}", ""
        rows.append({"file": f"{folder}/{p.name}", "truth": truth, "pred": pred, "score": score})
        print(rows[-1])

with open(ROOT / "eval" / "results.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["file", "truth", "pred", "score"])
    w.writeheader()
    w.writerows(rows)

ok = [r for r in rows if not str(r["pred"]).startswith("error")]
if ok:
    acc = sum(r["truth"] == r["pred"] for r in ok) / len(ok)
    print(f"\nAccuracy: {acc:.0%} on {len(ok)} clips ({len(rows) - len(ok)} errors)")
