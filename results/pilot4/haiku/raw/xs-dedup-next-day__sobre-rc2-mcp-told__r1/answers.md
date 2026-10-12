Three commits since 2025-05-22 changed how snooze or dedup decisions are made, or the windows they use. I didn't change any code.

**Commits**

1. **`a348bbd2`** (2025-05-29), `fix(signal): don't dedup on canary signals (#6026)`
   - Canary signal instances are skipped by dedup. In `filter_dedup` (`src/dispatch/signal/service.py`), the function returns early when `signal_instance.canary` is set. Canary instances are also excluded from the candidate queries, both the default path and the custom-filter path.
   - No window is involved.

2. **`7a9fe810`** (2025-06-19), `feat(signal): make the default deduplication window configurable`
   - Replaced a hard-coded one-hour default window with `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, read from `src/dispatch/config.py:95`.
   - Default is **45 minutes**, read from the environment as an integer. The code multiplies it by 60 to get seconds before use (`service.py`, `default_dedup_window = _window_start(SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60)`).
   - This applies when a signal has no dedup filters.

3. **`917a0b7b`** (2025-08-14), `refactor(signal): share the lookback window computation`
   - Introduced `_window_start(seconds)` and routed both lookbacks through it. It is described as a refactor, but it changed units for custom filters.
   - Before: `timedelta(minutes=f.window)`. After: `_window_start(f.window)`, which treats `f.window` as **seconds**. The comment added reads "SignalFilter.window is stored in seconds".
   - The model agrees with seconds: `SignalFilter.window` in `src/dispatch/signal/models.py:206-208` is an Integer with default `60 * 60` (3600 s). The pydantic schema at `models.py:282` defaults to `600`.

**Commits I checked that do not change snooze/dedup windows**
- `086dc910` (2025-08-07) changed the snooze filter check to skip filters whose mode is not active. It does not change any window.
- `4474af25` only logs the outcome of each processed instance.
- `d2675cf4` masks raw fields before processing.
- `dee1699d` concerns case-type suggestion.

**Current values as the code applies them**
- Custom dedup filters: `f.window` in **seconds**. The model default is 3600 s; the UI offers values 5, 10, 15, 20, 30.
- Default dedup (no filters): **45 minutes**, i.e. 2700 s.
- Snooze: no time window. A snooze filter applies until its `expiration` datetime, and a filter without an expiration is skipped with a warning.
- `flows.py:373` has a hard-coded `timedelta(seconds=5)` in the path that decides whether to post an update for a deduplicated signal. It is a notification gate, not a dedup window, and it has not changed since 2025-05-22.

**Problems to know about**
- **Unit mismatch.** `SignalFilterCreateDialog.vue:56` is labelled "Window (minutes)" and offers 5–30 (`:196`). The value is sent as-is, and `917a0b7b` now reads it as seconds. A filter created with "30" therefore dedups over 30 seconds, not 30 minutes. I did not verify the save payload end to end, so this rests on the label, the item list, and the backend change.
- **Stale docs and comments.** `docs/docs/administration/settings/signal/filter.mdx:35` says the default is a one-hour window, and the docstring at `service.py` around line 873 also says one hour. The code default is 45 minutes. The comment at `models.py:208` says one hour, which matches the model default of 3600 s.

I also recorded the window history as a finding in sobre.

----- next turn -----

The window bug came from 917a0b7b (`refactor(signal): share the lookback window computation`). It fixed the UI-reported behaviour, but only for filters created after it. Filters you already had are stored in minutes, and the commit started reading them as seconds. So a window of 30 became 30 seconds, and two instances ten minutes apart didn't group.

**Fix**
- `src/dispatch/signal/service.py`: `filter_dedup` now reads `f.window` as minutes again (`_window_start(f.window * 60)`), so existing filters work without edits. The default-window path already multiplied `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` by 60 and was correct.
- `src/dispatch/signal/models.py`: the `window` column comment said seconds and its default was `60 * 60`. It now says minutes with default `60`, which keeps the one-hour default. This is a Python-side default, so no migration is needed. Existing rows are untouched.
- `filter_signal`'s docstring now names the setting instead of "1-hour".
- `tests/signal/test_signal_service.py`: added `test_filter_actions_deduplicate_window_in_minutes`. It creates an instance 10 minutes old and a new one, under a window-30 filter, and expects deduplication. I confirmed it fails with the seconds line restored and passes with the fix.

**Test results**
- `python -m pytest tests/signal`: 33 passed, 1 skipped.
- I did not run the full suite.

**Other findings**
- 086dc910 (`simplify snooze filter checks`) changed `continue` to `break` in the expired-snooze branch of `filter_snooze`. One expired snooze filter now stops evaluation of the remaining snooze filters for that signal. This is a separate bug in snoozing, which I did not fix.
- The API schema default in `SignalFilterBase` is `window: int | None = 600`. Under the minutes meaning that is 10 hours, not the 1 hour the column default implies. I left it alone because changing it affects API clients.

The commit list I used is from `git log --since=2025-05-22` filtered to signal, dedup and snooze files. I could not see yesterday's list in this conversation.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES