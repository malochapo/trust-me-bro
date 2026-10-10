# Fixture

`build.py` produces `build/fixture.git`: Netflix Dispatch at `dd2837e8`, with its last 150 commits replayed. Seven planted commits sit among them, each right after the upstream commit named in `plants.json`. Replayed commits keep their authors, committers and dates, so the build is deterministic. The build fails if the final tree differs from upstream with every plant applied.

| Plant | What it does | Used by |
| --- | --- | --- |
| `t0-test-teardown` | Releases pooled connections before the test database is dropped. Without it, PostgreSQL refuses the drop and every pytest run ends in an error. | all test-graded tasks |
| `p0-log-filter-outcome` | Logs the outcome of each processed signal instance | `log-dedup-regression` |
| `p1-default-dedup-window` | Makes the default deduplication window configurable (45 minutes) and leaves a stale "1-hour" docstring | `qa-default-dedup-window`, `qa-history-dedup-config` |
| `p2-redact-raw` | Masks sensitive raw fields before entity extraction | `qa-signal-pipeline` |
| `p3-cases-page-size` | Pages the cases table by 40, while the store still says 25 | `qa-cases-page-size` |
| `p5-snooze-refactor` | A refactor that turns `continue` into `break` on expired snooze filters (bug) | `fix-snooze-expired-filter` |
| `p4-dedup-window-seconds` | Reads per-filter deduplication windows as seconds instead of minutes (bug) | `log-dedup-regression` |

`author_plants.py` regenerates the patches from edits made on upstream. Maintainers run it; the benchmark does not. `gen_logs.py` writes the signal worker's log for `log-dedup-regression`, seeded, from the built fixture. `requirements.lock` pins Dispatch's Python dependencies.

The tests need PostgreSQL on localhost (user `postgres`, password `dispatch`). `tests/conftest.py` hard-codes the database name, so test runs must not overlap.
