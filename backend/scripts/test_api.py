"""Sanity check: python backend/scripts/test_api.py clip.wav  (costs about 2 credits per second)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.app import detectif_client as dc  # noqa: E402

path = Path(sys.argv[1])
out = dc.detect(path.name, path.read_bytes())
print(json.dumps(out, indent=2))
