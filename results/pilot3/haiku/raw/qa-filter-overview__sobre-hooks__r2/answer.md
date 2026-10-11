## How a new signal instance is classified

The entry point is `process_signal_batch` (`src/dispatch/signal/flows.py:~391`), which calls `signal_instance_create_flow` (`flows.py:46`) for each unprocessed instance. Unprocessed means `filter_action IS NULL` and `case_id IS NULL` (`get_unprocessed_signal_instance_ids`, `signal/service.py:900`, limit 500, oldest first). Entities are extracted before filtering, so filters can match on them. The classification then runs in `filter_signal` (`signal/service.py:866`):

1. **Snooze check**: `filter_snooze` (`service.py:743`)
2. **Dedup check, only if not snoozed**: `filter_dedup` (`service.py:789`)
3. **Outcome**: if neither set `filter_action`, it is set to `none` and the instance is not filtered. Otherwise `filtered = True`. The session is committed and the result returned.

Back in `signal_instance_create_flow`, a filtered instance returns early. It only refreshes the Slack signal message if it has a case and a conversation. An unfiltered canary returns with no case. An unfiltered non-canary with `create_case` set goes on to `case_service.create`.

### 1. Snooze (`filter_snooze`)

- Only filters with `mode == active` and `action == snooze` are considered.
- A snooze filter with no `expiration` logs a warning and is skipped.
- If `expiration <= now` (UTC; the code assumes the stored naive datetime is UTC), the loop does `break`, not `continue`. Any later filters in the list are then never checked for this instance.
- No `expression`: every instance of the signal is snoozed.
- With an `expression`: the instance is snoozed only if it matches the expression. Matching uses `apply_filter_specific_joins` and `apply_filters`, restricted to this instance's id. No time window applies.
- A match sets `filter_action = snooze` and stops the loop.
- Snooze does not exclude canary instances.

### 2. Deduplication (`filter_dedup`)

- **Canary**: returns immediately. Canary instances are never deduplicated.
- **Default path**: taken only when the signal has no filters at all, in any mode or action.
  - Lookback: `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds (`config.py:95`, env var, **minutes**, default **45**).
  - Candidates: same `signal_id`, `created_at` within the window, `id` different, `case_id IS NOT NULL`, not canary.
  - Entities are not compared. The most recent candidate's `case_id` is used.
- **Filter path**: taken when the signal has at least one filter. Each `mode == active` and `action == deduplicate` filter is tried in list order; the first match wins.
  - Candidates: same signal, not canary, inner-joined to `entities` and `entity_type`, matching `f.expression` via `apply_filters`.
  - Lookback: `f.window` **seconds**, from `_window_start`.
  - The candidate must share at least one entity id with the new instance. An instance with no entities never matches.
  - Candidates are ordered by `created_at` ascending and the first one's `case_id` is used. No `case_id IS NOT NULL` check is applied here, so the match can yield `case_id = None`.
- A signal with only snooze filters has no deduplicate filters, so it gets no dedup at all, not even the default one.

### Time windows as the code applies them

| Setting | Unit | Default | Where it is used |
|---|---|---|---|
| `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` | minutes (×60 → seconds) | 45 | Default dedup path only |
| `SignalFilter.window` (DB column) | seconds | 3600 (`signal/models.py:206`) | Filter-path dedup |
| `SignalFilterBase.window` (Pydantic) | seconds | 600 (`signal/models.py:282`) | Default for filters created via API or Slack |
| Snooze `expiration` | absolute datetime | none (no expiry, so the filter is skipped) | `filter_snooze` |

- Snooze filters have no window. The Slack snooze modal (`dispatch_slack/case/interactive.py` ~1016–1038) computes `expiration = now + delta` from the relative date picker. It does not set `window`.
- The Vue dialog `SignalFilterCreateDialog.vue` labels the dedup window "Window (minutes)" with options 5, 10, 15, 20, 30. It posts the selected number unchanged, and the store's `save` does not convert it. The backend then treats that number as seconds, so a "10 minute" window becomes 10 seconds.
- The `filter_signal` docstring says the default is a "1-hour window". The code default is 45 minutes.

### Canary signals

- **Snooze**: applied as for any signal. A canary can be snoozed, which sets `filter_action = snooze` and counts as filtered.
- **Dedup**: skipped entirely for canary instances.
- **As dedup targets**: canary instances are excluded from both dedup queries (`~SignalInstance.canary`), so they never join an existing case.
- **If not filtered**: `signal_instance_create_flow` returns before case creation. The instance is saved with `filter_action = none` and no case.

### Things worth knowing

- The `break` on an expired snooze filter skips the remaining filters for that instance.
- Filter-path dedup can match a prior instance with no case. The instance is then marked `deduplicate` with `case_id = None` and no case is created.
- The window unit mismatch above means the UI and the backend disagree about dedup window units.

I read the code only and did not run the tests or exercise these paths.