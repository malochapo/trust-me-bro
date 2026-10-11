The short answer: `signal_instance_create_flow` (`src/dispatch/signal/flows.py:46`) first resolves entities, then calls `signal_service.filter_signal` (`src/dispatch/signal/service.py:866`). That function runs snooze first, then dedup only if snooze did not match. If either matches, the instance is filtered and no case is created. Otherwise a new case is created, unless the signal has `create_case` off or the instance is a canary.

## Order of checks

1. **Entity extraction** (`flows.py:57-70`). Entities are found before filtering, because deduplication matches on them.
2. **`filter_snooze`** (`service.py:743`), then **`filter_dedup`** (`service.py:789`) only if `filter_action` is still unset.
3. If `filter_action` is set, `filter_signal` returns `True`. The flow logs it, updates the signal message if the case has a conversation, and returns without creating a case or running workflows (`flows.py:78-100`).
4. If it is not filtered and the instance is a canary, it is stored and returned (`flows.py:102-104`).
5. If `signal.create_case` is false, it is returned (`flows.py:106-107`).
6. Otherwise a case is created via `case_service.create`, then `case_flows.case_new_create_flow`, engagements, and workflows run (`flows.py:153-228`).

`filter_signal` sets `filter_action` to `none` when nothing matched, then commits.

## Snooze (`filter_snooze`)

- Only filters with `mode == active` and `action == snooze` are considered. Other modes and actions are skipped.
- A snooze filter with no `expiration` is skipped with a warning.
- If `expiration` is in the past, the loop **`break`s**, not `continue`s. Any later filters in the list are then never checked. The expiration is compared as a naive datetime with UTC applied, and it is an absolute timestamp, not a window.
- If the filter has no `expression`, every instance of that signal is snoozed.
- If it has an `expression`, the signal's instances are queried with `apply_filter_specific_joins` and `apply_filters`. The instance is snoozed only if its own id is in the result.
- There is no canary exclusion here, so a canary can be snoozed.

## Deduplication (`filter_dedup`)

- **Canary: returns immediately.** Canaries are never deduplicated. They are also excluded as dedup targets in both branches (`~SignalInstance.canary`).
- **No snooze/dedup filters on the signal** (the `if not signal_instance.signal.filters` branch): the lookback is `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds. The config default is **45 minutes** (`src/dispatch/config.py:95`). It matches the most recent earlier instance of the same signal with a non-null `case_id` and no canary flag, ignoring entities. On a match it copies that `case_id` and sets `deduplicate`.
- **Filters present**: for each filter with `mode == active` and `action == deduplicate` (in list order, first match wins):
  - Candidates are instances of the same signal that are not canaries, joined to their entities and entity types, matching `f.expression`.
  - `created_at` must be within `f.window` **seconds** before now.
  - The candidate must share at least one entity with this instance (`Entity.id.in_`). An instance with no entities cannot match.
  - The earliest matching candidate's `case_id` is used.
- **Window defaults, units in seconds:**
  - The DB model default is `3600` (1 hour), per the model comment and `Column(Integer, default=60*60)`.
  - The API schema `SignalFilterBase.window` defaults to `600` (10 minutes). Filters created through the API get 600 unless the caller sets it.

Quirk: the filter-path query does not require the candidate to have a `case_id`. If the earliest match has none, the instance is still marked `deduplicate` with `case_id = None`, so it counts as filtered and no case is created.

The `filter_signal` docstring says the default dedup window is 1 hour. The code uses 45 minutes.

## Canary summary

- Snooze can match canary instances.
- Dedup never applies to canary instances, and canary instances are never used as dedup targets.
- If a canary is not snoozed, it is saved with no case, no case creation, and no workflows.

I read the code but did not run tests or execute these paths against a database.