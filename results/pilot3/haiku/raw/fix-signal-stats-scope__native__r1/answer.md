Fixed: with a `signal_id`, `GET /api/v1/{organization}/signals/{signal_id}/stats` now counts only snooze filters attached to that signal. Without a signal, it still counts across all signals. The new test passes, and the 33-test signal suite passes (1 skipped).

**Root cause:** in `get_signal_stats` (`src/dispatch/signal/service.py`), the snooze-filter aggregate matched filters on the entity expression alone and never looked at `signal_id`. The instance count right below it already restricted by signal, so only the filter counts were wrong.

**Fix:** when `signal_id` is set, the filter query now also requires the filter to be linked to that signal through the `assoc_signal_filters` table. I used the same `if signal_id` truthiness check the instance query already uses. The no-signal path is unchanged.

**Test:** `test_get_signal_stats_snooze_counts_scoped_to_signal_id` in `tests/signal/test_signal_stats_service.py`. It sets up two signals that share one entity. Signal 1 has one active snooze filter, and signal 2 has one active and one expired. It checks the per-signal counts and the unscoped totals. Against the original code it fails with `assert 2 == 1`, so it catches the bug.

**Test environment:** `python -m pytest` as-is fails during database setup. The server's `template1` is SQL_ASCII, so `CREATE DATABASE ... ENCODING 'utf8'` is rejected. To run the tests I used a small shim outside the repo, at `/tmp/sobre-bench-work/pgshim/pg_template0_shim.py`, which makes the test DB come from `template0`. Run it with `PYTHONPATH=/tmp/sobre-bench-work/pgshim python -m pytest -p pg_template0_shim ...`. I did not change the repo's test setup or the database server. You may want to fix `template1` on the server or change the test setup so plain `python -m pytest` works.

No formatter is installed here, so I didn't run ruff or black. I checked the added lines by hand against the 100-character limit. I did not commit anything.