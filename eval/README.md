# Evaluation (Person C)
Put consented clips (10-15 s each) in:
- `samples/real/`        genuine voices
- `samples/fake/`        AI-cloned voices (owner's permission)
- `samples/phone_noisy/` phone-recorded or noisy versions; name files `real_*.wav` or `fake_*.wav`

Run: `python eval/batch_eval.py`  (about 2 credits per second of audio, so 25 clips of 12 s is about 600 credits).
Output: `eval/results.csv` and an accuracy summary to paste into the README.
