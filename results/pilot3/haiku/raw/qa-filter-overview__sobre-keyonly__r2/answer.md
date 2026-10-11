## Decision order for a new signal instance

Processing starts in `signal_instance_create_flow` (`src/dispatch/signal/flows.py`). It redacts the raw payload, extracts entities, and then calls `signal_service.filter_signal` (`src/dispatch/signal/service.py:866`). The order is:

1. **`filter_snooze`** (`service.py:743`) runs first.
2. **`filter_dedup`** (`service.py:789`) runs only if snooze did not set a `filter_action`.
3. If neither set a `filter_action`, it is set to `none` and `filter_signal` returns `False`. Otherwise it returns `True`.

Back in the flow:

- If filtered (snoozed or deduplicated), the flow updates the existing case's signal message when the instance has a case and a conversation, then returns. No new case is created.
- If not filtered and `canary` is set, the instance is stored and the flow returns (`flows.py:102-104`).
- If not filtered and `signal.create_case` is false, the flow returns.
- Otherwise `case_service.create` opens a new case, with case type, priority, severity, and oncall assignee resolved from the instance, then the signal, then the case type.

## Snooze (`filter_snooze`)

- Only filters with `mode == active` and `action == snooze` are considered.
- A snooze filter with no `expiration` is skipped with a warning.
- If `expiration` is at or before now, the loop does `break`. This ends the whole loop, so any later snooze filters are also skipped, not just the expired one.
- Matching: a query over instances of the same signal, with `apply_filter_specific_joins` and `apply_filters(query, f.expression)`. The instance is snoozed if it appears in the results. An empty expression snoozes every instance of that signal until expiration.
- The only time bound is the absolute `expiration` datetime. Naive values are treated as UTC. There is no window.
- Canary instances are not excluded from snooze.

## Deduplication (`filter_dedup`)

Canary instances return immediately, so they are never deduplicated.

**Branch A: the signal has no filters at all.** This is the default rule.
- Lookback is `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (`config.py:95`, env-configurable, default **45 minutes**), converted to seconds and applied to `created_at`.
- It matches any other instance of the same signal with a non-null `case_id` and `canary` false, regardless of entities.
- The most recent match's `case_id` is used.
- The docstring of `filter_signal` says "1-hour window". The code uses 45 minutes.

**Branch B: the signal has filters.** Only filters with `mode == active` and `action == deduplicate` are used. Other filters are ignored. If no such filter exists, no deduplication happens. A signal with only snooze filters therefore gets no default dedup.
- For each dedup filter, the candidates are instances of the same signal with `canary` false, joined to their entities and entity types, matching `apply_filters(query, f.expression)`.
- `created_at` must be within `f.window` seconds of now. `SignalFilter.window` is an integer number of seconds. The model default is 3600 (1 hour). The API schema default in `SignalFilterBase` is 600 (10 minutes).
- The candidate must share at least one entity with the new instance. An instance with no entities matches nothing.
- The earliest candidate's `case_id` is used. The first dedup filter that matches wins.

## Canary signals

- `filter_dedup` skips canary instances, and canary instances are excluded from the candidate pool in both branches.
- `filter_snooze` does not skip canaries, so a canary can still be snoozed.
- A canary that is not snoozed is stored with entities and never gets a case, because the flow returns at `flows.py:102-104`.

## Gaps I noticed while reading

- `_window_start` in Branch B does not guard against `f.window` being `None`. The schema allows `int | None`, so a `None` window would likely raise a `TypeError`.
- Branch B does not filter candidates to `case_id IS NOT NULL`, unlike Branch A. If the earliest matching instance has no case, the new instance is marked `deduplicate` with `case_id` set to `None`.

I read these functions directly and did not run the code or its tests.