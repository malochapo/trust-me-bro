The window bug was introduced by `917a0b7b` ("refactor(signal): share the lookback window computation"). It changed the deduplication lookback from `timedelta(minutes=f.window)` to treating `f.window` as seconds. A 30-minute filter therefore looked back only 30 seconds, so two instances ten minutes apart opened two cases.

I don't have the earlier list from yesterday, so I rebuilt it from `git log --since=2025-05-22` and the code.

**Fix**
- `src/dispatch/signal/service.py`: `_window_start` takes minutes again. The filter window and the default window both go through it. Existing filter values are unchanged, so no filter needs editing. The stale comments that said "seconds" and "1-hour" now match the code.
- `src/dispatch/signal/models.py`: the column comment now says minutes, as the UI does.
- `tests/signal/test_signal_service.py`: added `test_filter_actions_deduplicate_window_is_in_minutes`. It creates an instance ten minutes old, then a new one under a 30-minute deduplicate filter, and expects deduplication. It fails when the seconds bug is reintroduced and passes with the fix.

`python -m pytest tests/signal` gives 33 passed, 1 skipped. I did not commit.

**Other findings, not changed**
- `086dc910` ("simplify snooze filter checks") changed `continue` to `break` for an expired snooze filter. Once one snooze filter has expired, the remaining snooze filters are skipped. This is a snooze bug, not a window bug, so I left it alone.
- The defaults are inconsistent with minutes. The schema default is `window: int = 600` (10 hours) and the column default is `60 * 60` (60 hours). I left them because changing them alters behaviour for filters created without a window.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES