The commit that broke it is `917a0b7b` ("share the lookback window computation"). My earlier summary was wrong about it: I'd described it as a fix. It changed the per-filter lookback from `timedelta(minutes=f.window)` to seconds. The UI ("Window (minutes)", options 5–30) and the existing stored values are minutes. A window of 30 therefore became 30 seconds, so two instances ten minutes apart no longer deduplicated.

**Fix**
- `src/dispatch/signal/service.py`: the lookback is now `_window_start(f.window * 60)`, so existing filters work again without being edited.
- `src/dispatch/signal/models.py`: the column default is now 60 and the pydantic default 10, both in minutes. Before, they were 3600 and 600, which only made sense as seconds. This only affects newly created filters.
- Regression test: `test_filter_dedup_window_is_in_minutes` in `tests/signal/test_signal_service.py`. A 30-minute filter deduplicates an instance created 10 minutes earlier and ignores one created 90 minutes earlier.
- Test results: the test fails without the fix and passes with it, and `tests/signal` passes (33 passed, 1 skipped).
- I also corrected my saved notes on this history.

The canary commit is `a348bbd2`, which skips deduplication for canary signals and excludes canary instances from dedup queries. The default window for signals without filters is 45 minutes (set by `7a9fe810`).

DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES

Note that `a348bbd2` and `7a9fe810` come from my saved notes, so I haven't re-checked them against the git history.