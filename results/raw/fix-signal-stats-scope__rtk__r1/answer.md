I fixed the bug. `GET /{signal_id}/stats` now counts only snooze filters attached to that signal.

In `get_signal_stats` (`src/dispatch/signal/service.py`), when a `signal_id` is given, the snooze query is now limited to filters linked to that signal through `assoc_signal_filters`. Without a `signal_id`, it still counts the filters of every signal. The instance counts are unchanged.

I added `test_get_signal_stats_snoozes_scoped_to_signal` to `tests/signal/test_signal_stats_service.py`. It creates one active and one expired filter on the target signal, plus an active filter on another signal. All three match the same entity.
- **With a signal id:** it expects 1 active and 1 expired.
- **Without one:** it expects 2 active and 1 expired.

The test fails without the fix, and all 7 tests in that file pass with it.

One thing about running tests: plain `python -m pytest` failed with a missing `easydict` module partway through my session. I didn't find the cause. Running the venv's interpreter directly, `/tmp/sobre-bench-work/run-02288317c3d5/venv/bin/python -m pytest`, worked.