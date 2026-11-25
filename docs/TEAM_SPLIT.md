# Team split (3 people, 6 hours)

Rule: everyone works only in their own folders, commits small and often, pulls before pushing.
The contract between backend and frontend is `docs/API_CONTRACT.md`. Do not change it without telling the others.

## Person A: Backend and API  (owns `backend/`, `.env.example`, `requirements.txt`)
| Time | Task |
|---|---|
| 0:00-0:45 | Create GitHub repo, add teammates, get API key, run `backend/scripts/test_api.py` on one real and one fake clip |
| 0:45-2:15 | Finish `detectif_client.py` (errors, retries, Idempotency-Key), `/api/check`, `/api/credits`, `/api/feedback` |
| 2:15-3:00 | Tune `risk.py` thresholds with Person C's results, add tests in `backend/tests/` |
| 3:00-4:30 | Help the others: bot, deployment, bug fixes |
| 4:30-6:00 | Final testing, README setup section, push repo |

## Person B: Frontend and UX  (owns `frontend/`)
| Time | Task |
|---|---|
| 0:00-0:45 | Open `frontend/mock/sample_response.json`, build the page against the mock so you are not blocked |
| 0:45-2:30 | Upload box (drag and drop plus record), loading state, risk card |
| 2:30-4:00 | Segment timeline chart, "what to do next" panel, "Was this right?" buttons, English/Hindi toggle |
| 4:00-4:45 | Error states (too short, too little speech, no credits, busy), credits footer |
| 4:45-6:00 | Polish for the demo, take screenshots, help record the demo video |

## Person C: Data, evaluation and content  (owns `eval/`, `bot/`, `docs/` except this file)
| Time | Task |
|---|---|
| 0:00-1:00 | Record clips WITH PERMISSION: genuine voices (10-15 s), cloned voices of consenting teammates, phone-recorded and noisy versions. Put them in `eval/samples/` |
| 1:00-2:30 | Write `docs/demo_script.md`; start the optional Telegram bot (`bot/`) |
| 2:30-4:00 | Run `eval/batch_eval.py` (about 20-25 clips, watch credits) and share results with Person A |
| 4:00-5:00 | Write the Reddit post (`docs/reddit_post_draft.md`), post it, copy the link |
| 5:00-6:00 | Record the 2-minute demo video, fill "Honest results" in README, go through `docs/SUBMISSION_CHECKLIST.md` |

## Shared
- Credits: 5,000 total, Aletheia costs 2 per second. Budget: about 1,500 dev, 1,000 eval, 1,000 demo, 1,500 reserve.
- Do not call the API in loops while debugging. Use `Idempotency-Key` and cache results.
- Only one person runs `batch_eval.py` (Person C), to avoid burning credits twice.
