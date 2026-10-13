# Fixture

`build.py` produces `build/fixture.git`: Netflix Dispatch at `dd2837e8`, with its last 150 commits replayed. Eight planted commits sit among them, each right after the upstream commit named in `plants.json`. Replayed commits keep their authors, committers and dates, so the build is deterministic. The build fails if the final tree differs from upstream with every plant applied.

| Plant | What it does | Used by |
| --- | --- | --- |
| `t0-test-teardown` | Releases pooled connections before the test database is dropped. Without it, PostgreSQL refuses the drop and every pytest run ends in an error. | all test-graded tasks |
| `p0-log-filter-outcome` | Logs the outcome of each processed signal instance | `log-dedup-regression` |
| `p1-default-dedup-window` | Makes the default deduplication window configurable (45 minutes) and leaves a stale "1-hour" docstring | `qa-default-dedup-window`, `qa-history-dedup-config` |
| `p2-redact-raw` | Masks sensitive raw fields before entity extraction | `qa-signal-pipeline` |
| `p3-cases-page-size` | Pages the cases table by 40, while the store still says 25 | `qa-cases-page-size` |
| `p6-entity-stats-window` | Makes the UI ask for entity signal stats over the last 30 days | `qa-ui-entity-stats` |
| `p5-snooze-refactor` | A refactor that turns `continue` into `break` on expired snooze filters (bug) | `fix-snooze-expired-filter` |
| `p4-dedup-window-seconds` | Reads per-filter deduplication windows as seconds instead of minutes (bug) | `log-dedup-regression` |

`author_plants.py` regenerates the patches from edits made on upstream. Maintainers run it; the benchmark does not. `gen_logs.py` writes the signal worker's log for `log-dedup-regression`, seeded, from the built fixture. `requirements.lock` pins Dispatch's Python dependencies.

## The pilot 2 fixture

From pilot 2 on, the tasks run on `build/pilot2/` (`python3 -I fixture/build.py --spec fixture/plants-pilot2.json --out build/pilot2`). `plants-pilot2.json` keeps the eight plants above and adds five, each a bug:

| Plant | What it does | Used by |
| --- | --- | --- |
| `q1-restricted-case-filter` | A refactor that lets members see restricted cases they do not take part in | `ci-red-regressions`, `mt-security-review`, `long-security-then-redaction` |
| `q2-case-cost-cutoff` | Stops a case's classic cost at the latest of its status timestamps | `ci-red-regressions`, `mt-logs-case-cost` |
| `q3-entity-first-match` | Keeps only the first JSONPath match in entity extraction | `ci-red-regressions`, `mt-redaction-entities`, `long-security-then-redaction` |
| `q4-reminder-day` | A refactor with a weekday off-by-one: the weekly Monday reminders stop | `log-reminders-stopped`, `mt-reminders-incident`, `long-incident-then-dedup`, `xs-reminders-*` |
| `q5-unprotected-event-delete` | Drops the permission check of an incident's custom event delete route | `mt-security-review`, `long-security-then-redaction` |

`gen_logs_pilot2.py build/pilot2` writes the scheduler and API logs of `log-reminders-stopped`, which the reminder conversations reuse; `gen_logs_pilot4.py build/pilot2` writes the three logs of `mt-logs-case-cost`. Both are seeded.

## Tests

The tests need PostgreSQL on localhost (user `postgres`, password `dispatch`). `tests/conftest.py` hard-codes the database name, so test runs must not overlap.
