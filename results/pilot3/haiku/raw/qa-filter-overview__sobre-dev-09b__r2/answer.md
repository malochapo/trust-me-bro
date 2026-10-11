## How a new signal instance is classified

Processing runs through `signal_instance_create_flow` in `src/dispatch/signal/flows.py:46`, which calls `signal_service.filter_signal` (`src/dispatch/signal/service.py:866`). `filter_signal` runs the checks in this order:

1. **`filter_snooze`** (`service.py:743`)
2. **`filter_dedup`** (`service.py:789`), only if no snooze matched
3. If neither set a `filter_action`, it is set to `none` and the instance is not filtered. Otherwise `filter_signal` returns `True` and the instance is filtered. It commits in either case.

Back in `signal_instance_create_flow`, a filtered instance returns early. The one side effect is that if it was deduplicated into a case that has a conversation, the case's signal message is updated via `update_signal_message`. An unfiltered instance goes on to canary handling and then case creation.

### Snooze (`filter_snooze`)

- Iterates `signal_instance.signal.filters`. Only filters with `mode == active` and `action == snooze` are considered.
- A snooze filter with no `expiration` is logged as a warning and skipped.
- If the filter's expiration is at or before now (UTC), the loop hits `break`. That ends the whole loop, so any snooze filters after it are not evaluated. The expiration is stored as a naive datetime and treated as UTC.
- If the filter has an expression, it is applied with `apply_filter_specific_joins` and `apply_filters` to the instances of the same `signal_id`. The instance is snoozed only if it appears in that result. If the expression is empty, every instance of the signal is snoozed.
- A match sets `filter_action = snooze` and stops the loop.
- Snooze never checks `canary`, so canary instances can be snoozed.

### Deduplication (`filter_dedup`)

Canary is checked first: a canary instance returns immediately with no dedup.

**Case 1: the signal has no filters at all.** The default rule applies.
- The lookback is `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds, from `_window_start`. The setting is in minutes, read from config, and defaults to **45**.
- It looks for another instance of the same signal, with a non-null `case_id`, not canary, and a different id, created within the window. It takes the most recent one by `created_at`.
- It matches on the signal only. Entities are not considered.
- On a match it sets `case_id` to that case and `filter_action = deduplicate`.

**Case 2: the signal has filters.** The default is not used. Only filters with `mode == active` and `action == deduplicate` are considered, in order, and the first match wins.
- The window is `f.window` in **seconds**, looked back from now with `_window_start`.
- Candidates are instances of the same signal that are not canary, were created inside the window, are not this instance, and match `f.expression` through `apply_filters`.
- They must share at least one entity with the current instance (`Entity.id` in the instance's entity ids).
- The earliest match by `created_at` is used. Its `case_id` is copied onto the instance and `filter_action = deduplicate` is set.
- The earliest match's `case_id` is not checked for null. If it is null, the instance is still marked deduplicated with no case.
- If the signal has filters but none are active deduplicate filters, nothing is deduplicated. The default rule does not apply.

### Window defaults and units

- `SignalFilter.window` column (`src/dispatch/signal/models.py:206`): integer seconds, default `3600` (1 hour). The comment says so too.
- `SignalFilterBase.window` (`models.py:282`): Pydantic default `600` seconds (10 minutes). I did not check which create schema the Slack snooze path or the API uses, so I can't say which of the two defaults a newly created filter gets.
- `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (`src/dispatch/config.py:95`): minutes, default `45`, converted to seconds in `filter_dedup`.
- Snooze duration: the Slack modal parses a duration string into a `timedelta` and sets `expiration = now + delta` (`src/dispatch/plugins/dispatch_slack/case/interactive.py:~990–1038`). The stored value is an absolute time, not a duration.

### Canary signals

- Snooze applies to canary instances.
- Dedup skips canary instances, both as the instance being classified and as candidates in both dedup branches (`~SignalInstance.canary` in the queries).
- A canary instance that is not snoozed is not filtered. `signal_instance_create_flow` then returns it at the canary check (`flows.py:102`), so it is stored with no case and no workflows run.

I did not read the rest of `signal_instance_create_flow` (case creation, workflows) past the canary check.