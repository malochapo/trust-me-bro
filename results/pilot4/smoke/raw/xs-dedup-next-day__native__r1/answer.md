The commit that broke deduplication windows is `917a0b7b` ("refactor(signal): share the lookback window computation", Aug 14 2025). It is fixed, with a regression test.

I don't have yesterday's list in this conversation, so I rebuilt it from `git log` since 2025-05-22, filtered to the commits that touch snooze and dedup code.

**Cause:** `SignalFilter.window` is stored as minutes. The UI offers 5–30 under "Window (minutes)", and the pre-`917a0b7b` code used `timedelta(minutes=f.window)`. `917a0b7b` treated the value as seconds, so a 30-minute filter became a 30-second lookback. Two instances ten minutes apart fall outside that window and open separate cases.

**Fix:**
- `src/dispatch/signal/service.py`: the dedup lookback is now `_window_start(f.window * 60)`, with the comment corrected to say minutes. Existing filters keep their stored values and work without edits.
- `src/dispatch/signal/models.py`: the column comment and default now say minutes. The default changed from `60 * 60` to `60`, which is one hour in minutes.

**Tests:** `tests/signal/test_signal_service.py` adds two tests. One checks that a 30-minute window groups instances ten minutes apart. The other checks that it doesn't group instances forty minutes apart. The first fails without the fix and passes with it. `python -m pytest tests/signal` gives 34 passed, 1 skipped. I didn't run the full suite. `ruff` isn't installed here, so I didn't lint.

**Left alone:**
- The Pydantic schema default `window: int | None = 600` in `models.py` is unchanged, and so is the matching `default: 600` in `docs/scripts/openapi.yaml`. Read as minutes, that's 10 hours, not 10 minutes. Changing it alters what API clients get when they omit `window`, so I left that decision to you.
- `086dc910` changed `continue` to `break` for expired snooze filters in `filter_snooze`. That stops the loop at the first expired snooze, so later active snooze filters are skipped. It's a separate bug from the window issue, so I didn't change it.
- `docs/docs/administration/settings/signal/filter.mdx` still says the default is one hour, which is correct for the default of 45 minutes only if the setting is unchanged; it's worth updating.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES