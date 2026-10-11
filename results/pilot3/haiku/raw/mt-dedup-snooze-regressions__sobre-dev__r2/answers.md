I found four commits since 2025-05-22 that change snooze or deduplication decisions or their windows. I changed no code.

Current windows, as the code applies them:

- **Default dedup window** (signals with no filters at all): `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, default **45 minutes** (2,700 s), overridable by env var. Defined at `src/dispatch/config.py:95`, applied at `src/dispatch/signal/service.py:805`.
- **Expression dedup filter window** (`SignalFilter.window`): stored and read as **seconds** (`service.py:845-846`). The DB column defaults to **3600 s** (`models.py:206-208`). The pydantic schema default is **600 s** (`models.py:282`), used when a request omits the field. The UI dialog offers 5, 10, 15, 20, 30 under a label that says "Window (minutes)" (`SignalFilterCreateDialog.vue:56,196`).
- **Snooze**: no window. It depends only on the filter's `expiration` timestamp.

Commits, oldest first:

1. **`a348bbd2`**, 2025-05-29, Will Sheldon, *fix(signal): don't dedup on canary signals (#6026)*. Canary instances are skipped by dedup, both as the incoming instance and as candidates to match against. Snooze is unaffected.

2. **`7a9fe810`**, 2025-06-19, Jordan Lee, *feat(signal): make the default deduplication window configurable*. The default-window lookback was hard-coded at 1 hour. It now reads `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45 minutes. This is a 15-minute reduction from the old 1-hour behavior for the default case.

3. **`086dc910`**, 2025-08-07, Sam Ortega, *refactor(signal): simplify snooze filter checks*. This was meant as a refactor, but it changed behavior in two ways:
   - An **expired** snooze filter used to `continue`, so later snooze filters were still checked. It now `break`s out of the loop, so no later snooze filter on that signal is evaluated (`service.py:762`).
   - It also dropped the warnings logged for snooze filters with no mode or no action. The filtering outcome for those cases is unchanged.

4. **`917a0b7b`**, 2025-08-14, Jordan Lee, *refactor(signal): share the lookback window computation*. This added `_window_start(seconds)` and routed both windows through it. It also changed the unit for expression dedup filters. Before, the window was `timedelta(minutes=f.window)`. Now it is `_window_start(f.window)`, which treats `f.window` as seconds. Existing filters therefore look back 60 times less far than before (a stored 10 now means 10 seconds, not 10 minutes). The commit message calls this a refactor and does not mention the change. I did not check whether a data migration rescaled existing rows.

Known inconsistencies in the current code:
- The `filter_signal` docstring (`service.py:~870`) still says the default window is 1 hour. The code uses 45 minutes.
- The UI label says minutes, but the backend reads seconds, so the 5–30 options produce 5–30 second windows.

Excluded from the list: `4474af25` (logging only), `d2675cf4` (redacts raw fields before entity extraction, which can indirectly affect what dedup matches on, but it does not change the snooze or dedup logic itself), and `5e136d7b` (UI and model import changes).

I searched commit messages and content for the relevant terms, and I also listed every commit since 2025-05-22 that touched `src/dispatch/signal/`, `src/dispatch/config.py`, or `models.py`. I did not check the frontend history beyond the dialog's current values.

----- next turn -----

The cause is commit `917a0b7b`. It changed the expression-filter window from minutes to seconds, so a filter set to 30 looked back 30 seconds. Your two instances, ten minutes apart, fell outside that and opened two cases. The other commits don't affect windows.

**Fix**
- `src/dispatch/signal/service.py` (`filter_dedup`): the window is now `_window_start(f.window * 60)`, so the stored value is read as minutes, as the UI shows it. Existing filters keep their stored values and need no edits. This assumes stored values were written in minutes by the UI, which matches the code before `917a0b7b`. I did not check whether a migration rescaled rows during that window.
- `src/dispatch/signal/models.py`: corrected the comment on `window` to say minutes.

**Regression test**
- `tests/signal/test_signal_service.py`: `test_filter_actions_deduplicate_window_is_minutes`, parametrized over two cases. A 30-minute window dedupes an instance from 10 minutes earlier, and a 5-minute window does not. I confirmed the 30-minute case fails with the old seconds line and passes with the fix.

**Test results**
- Signal service tests: 16 passed, 1 skipped.
- Full suite: 361 passed, 4 skipped, 8 failed. The same 8 fail on a clean tree (`tests/ai/test_ai_service.py`, `tests/database/test_service.py`, `tests/entity/test_entity_service.py`), so they predate my change.

**Left unchanged, for you to decide**
- The column default is `60 * 60`, which is now 60 hours rather than the 1 hour its old comment described. The API schema default is 600, which is 10 hours. Both predate `917a0b7b`, and changing them alters behavior for new filters created without a window, so I did not touch them.
- The `filter_signal` docstring still says the default window is 1 hour. The code uses 45 minutes.
- `086dc910` made an expired snooze stop the loop instead of skipping to the next filter. It is unrelated to this bug and I left it alone.

----- next turn -----

The cause is commit `086dc910` (Sam Ortega, 2025-08-07). It changed the expired-snooze branch in `filter_snooze` from `continue` to `break`. The "Okta: Impossible travel" filters are ordered with the expired one first, so the loop hit it and stopped before reaching the valid one. New instances for that user were therefore never snoozed.

**Fix**
- `src/dispatch/signal/service.py` (`filter_snooze`): the expired-filter branch uses `continue` again, so later snooze filters are still checked.

**Regression test**
- `tests/signal/test_signal_service.py`: `test_filter_actions_snooze_after_expired_snooze`. It creates an expired snooze filter followed by an active one for the same entity, then asserts the instance is snoozed. It fails with `break` and passes with `continue`.

**Results**
- Signal service tests: 17 passed, 1 skipped.
- Full suite: 362 passed, 4 skipped, 8 failed. The 8 failures are the same ones that fail on a clean tree, in `tests/ai`, `tests/database`, and `tests/entity`.

**Current state of the working tree**
This session's changes are uncommitted. They are the window-unit fix from the last report and this snooze fix. Both are in `service.py`, plus the matching tests and the `models.py` comment.

----- next turn -----

Recap of this session's work on the Dispatch signal filters:

- **Dedup window units (fixed, uncommitted):** Commit `917a0b7b` changed expression-filter dedup windows from minutes to seconds, so a 30-minute window looked back 30 seconds. The fix in `src/dispatch/signal/service.py` reads the stored value as minutes again, so existing filters work unchanged. A regression test covers it.
- **Snooze after an expired filter (fixed, uncommitted):** Commit `086dc910` changed an expired snooze filter from `continue` to `break`, which stopped the loop before later valid filters were checked. The fix restores `continue`. A regression test covers it.
- **Canary signals:** Commit `a348bbd2` made dedup skip canary signals, both as the incoming instance and as match candidates.
- **Default grouping:** Signals with no filters are grouped by a 45-minute default window, set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`.

Open items, not changed: the column default for `SignalFilter.window` is 60 hours, and the API schema default is 10 hours. The `filter_signal` docstring still says 1 hour.

DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES