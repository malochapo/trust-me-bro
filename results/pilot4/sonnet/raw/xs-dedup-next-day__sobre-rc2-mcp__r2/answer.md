The bug came from commit 917a0b7b ("refactor(signal): share the lookback window computation", 2025-08-14). The new test fails without the fix and passes with it, and `python -m pytest tests/signal` passes (33 passed, 1 skipped). I didn't run the full test suite.

**Cause.** Before that commit, the filter lookback was `timedelta(minutes=f.window)`. The commit added a `_window_start(seconds)` helper and passed `f.window` through it as seconds, with a comment saying the window is stored in seconds. But the UI labels the field "Window (minutes)" and offers 5/10/15/20/30. Existing rows therefore hold minutes. A window of 30 became 30 seconds, so two instances ten minutes apart no longer grouped into one case.

**Fix.**
- `src/dispatch/signal/service.py`: `_window_start` now takes minutes. The filter path passes `f.window` as minutes, and the default path passes `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` without the `* 60`. Existing filters work without being edited.
- `src/dispatch/signal/models.py`: I corrected the column comment, which wrongly said seconds.
- Regression test: `test_filter_actions_deduplicate_window_is_in_minutes` in `tests/signal/test_signal_service.py`. It uses a window of 30 and two instances ten minutes apart, and checks that they deduplicate into the same case.

I left the column default (`60 * 60`) and the schema default (`600`) alone. Read as minutes, both are odd values, but the UI always sets a window, so I didn't change them.

The canary commit is a348bbd2 (2025-05-29, "don't dedup on canary signals"). The default-window setting was introduced in 7a9fe810. The default window is 45 minutes unless the setting is overridden; the code default is 45, although the `filter_signal` docstring still says 1 hour.

DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES