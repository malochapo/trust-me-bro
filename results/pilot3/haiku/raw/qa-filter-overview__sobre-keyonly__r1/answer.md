## How a new signal instance is routed

Routing happens in `signal_instance_create_flow` (`src/dispatch/signal/flows.py:46`), which calls `signal_service.filter_signal` (`src/dispatch/signal/service.py:866`). Nothing here was executed. This is from reading the code.

**Order of checks:**

1. **Entities are extracted first.** `entity_service.find_entities` runs on the signal's entity types plus the `all`-scope entity types, and the result is saved to `signal_instance.entities`. Dedup and snooze expressions can match on these.
2. **`filter_signal`** runs `filter_snooze`, then `filter_dedup` only if `filter_action` is still unset. If neither sets it, `filter_action` becomes `none`. The result is committed, and `filtered` is true only when an action was set.
3. **If filtered:** the instance returns early. If it has a `case_id` and the case has a conversation, `update_signal_message` runs when `_should_update_signal_message` allows it. That check requires a deduplicate action and at least 5 seconds since the last update.
4. **Canary check:** if `signal_instance.canary` is set, the instance is stored and returned with no case.
5. **Case creation:** if `signal.create_case` is false, it returns. Otherwise a case is created, `case_new_create_flow` runs, engagements run, and workflows run.

Snooze and dedup are mutually exclusive, because dedup only runs when `filter_action` is still empty.

## Snooze (`filter_snooze`, service.py:743)

- Walks `signal.filters` in order. Only filters with `mode == active` and `action == snooze` are considered.
- A snooze filter with no `expiration` logs a warning and is skipped.
- An expired filter hits `break`, which ends the whole snooze loop, so later snooze filters are not checked.
- With no `expression`, the instance is snoozed unconditionally until expiration.
- With an `expression`, the code queries `SignalInstance` rows for the same `signal_id`, applies `apply_filter_specific_joins` and `apply_filters` for that expression, and restricts the result to this instance's `id`. A match sets `filter_action = snooze`.
- Snooze has no time window. Only `expiration` limits it. The expiration is compared as UTC after `tzinfo` is attached.

## Deduplication (`filter_dedup`, service.py:789)

Dedup first returns immediately for canary instances.

**Path A: the signal has no filters at all (`signal.filters` is empty).** This is the default rule.
- Candidates: same `signal_id`, `created_at` within `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds, not this instance, `case_id` not null, not canary.
- Entities are not compared. The most recent candidate's `case_id` is used.
- `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (config.py:95) defaults to **45 minutes (2700 s)**.

**Path B: the signal has any filter, of any kind.** The default rule is skipped entirely, even if the filters are only snooze filters. Each filter is checked in order:
- Only `mode == active` and `action == deduplicate` are considered. Dedup filters have no `expiration` check.
- Candidates: same `signal_id`, not canary, not this instance, joined to entities and entity types, matching `f.expression` through `apply_filters`, `created_at` within `f.window` seconds, and sharing at least one entity with this instance. An instance with no entities cannot match.
- Results are ordered by `created_at` ascending and the first candidate's `case_id` is used. The first matching filter wins.
- Unlike Path A, this path does not require `case_id` to be non-null. If the earliest match has no case, the instance is marked `deduplicate` with `case_id` set to `None`.

**Window defaults (in seconds):**

| Where | Value |
|---|---|
| Default rule (no filters) | 45 min = 2700 s, from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` |
| `SignalFilterBase.window` (API schema, models.py:282) | 600 s = 10 min |
| `SignalFilter.window` column default (models.py:206) | 3600 s = 1 h |

The schema default is what new filters created through the Pydantic model receive. I did not trace whether an explicit `None` can reach the column.

Two details could go wrong. The `filter_signal` docstring and the column comment both say 1 hour, which does not match the 45-minute code default. Also, a `None` window would make `_window_start(f.window)` fail.

## Canary signals

- **Dedup:** canary instances are never deduplicated (`filter_dedup` returns early). Canary instances are also excluded as dedup candidates in both paths.
- **Snooze:** `filter_snooze` does not check `canary`, so a canary instance can be snoozed. It then gets `filter_action = snooze`, counts as filtered, and the flow returns at step 3.
- **Not snoozed:** the instance gets `filter_action = none` and reaches the canary check in the flow (flows.py:103). It is stored with entities and no case. No case is created, and no engagements or workflows run.