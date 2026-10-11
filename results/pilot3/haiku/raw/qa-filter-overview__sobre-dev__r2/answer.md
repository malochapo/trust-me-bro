## How a new signal instance is classified

Entry point: `signal_instance_create_flow` in `src/dispatch/signal/flows.py:46`. It extracts entities (`flows.py:62-75`), then calls `signal_service.filter_signal` (`flows.py:78`). The checks run in this order:

1. **`filter_signal`** (`src/dispatch/signal/service.py:866`) calls **`filter_snooze`** first.
2. Only if nothing was set by snooze (`filter_action` is empty), it calls **`filter_dedup`** (`service.py:889`).
3. If still unset, `filter_action` becomes `none` and the result is "not filtered". Otherwise the instance is "filtered". `db_session.commit()` runs either way.
4. Back in the flow, a filtered instance returns early (`flows.py:81-100`). It only refreshes the Slack signal message when it has a case with a conversation. No case is created.
5. An unfiltered canary returns at `flows.py:103-104`, before any case creation.
6. If `signal.create_case` is false, it returns at `flows.py:106-107`.
7. Otherwise a case is created.

### Snooze: `filter_snooze` (`service.py:743`)

It iterates `signal_instance.signal.filters` and skips any filter that is not `mode == active` with `action == snooze`.

- No `expiration`: logs a warning and skips the filter.
- `expiration <= now` (UTC; the stored naive datetime is treated as UTC): executes `break`. This stops the loop, so later snooze filters are not evaluated, not just the expired one.
- Otherwise, it builds a query over all `SignalInstance` rows with the same `signal_id`, using `apply_filter_specific_joins` and `apply_filters` (`database/service.py:387`) with `f.expression`.
  - Empty expression: the instance is snoozed regardless of entities.
  - Non-empty expression: the instance is snoozed only if it appears in the filtered query.
- Snooze has no time window. It matches on the expression alone.
- Snooze does not check `canary`.

### Deduplication: `filter_dedup` (`service.py:789`)

- **Canary:** returns immediately, with no dedup.
- **Signal has no filter rows at all:** the default branch runs.
  - Window: `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds. The config default is 45 minutes (`src/dispatch/config.py:95-96`).
  - Matches any other instance of the same signal, not canary, with a non-null `case_id`, created within the window. It does not look at entities.
  - Picks the most recent match (`order_by created_at desc`) and copies its `case_id`. Sets `filter_action = deduplicate`.
- **Signal has filter rows:** the default branch is skipped entirely. Only active filters with `action == deduplicate` are considered, in list order. If none exist, nothing is deduplicated and the 45-minute default does not apply.
  - For each such filter, the candidates are other instances of the same signal that are not canary, joined to entities and entity types, with `f.expression` applied.
  - Candidate `created_at` must be at or after `now - f.window` seconds.
  - Candidates must share at least one entity with the new instance. An instance with no entities matches nothing.
  - Results are ordered by `created_at` ascending. The earliest instance's `case_id` is used, and `filter_action = deduplicate` is set. The first matching filter wins.

### Window units and defaults

| Setting | Unit | Where it applies |
|---|---|---|
| Default dedup window | minutes (config), converted to seconds | `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, default 45 |
| `SignalFilter.window` (DB column) | seconds | Column default 3600 (1 hour), `signal/models.py:206-208` |
| `SignalFilterBase.window` (API schema) | seconds | Pydantic default 600 (10 minutes), `signal/models.py:282`. This is what API-created filters get unless `window` is sent. |
| Snooze `expiration` | absolute datetime (UTC) | No window |

### Canary signals

- Snooze is not canary-aware. A canary instance can be snoozed and gets `filter_action = snooze`.
- Dedup is skipped for canary instances, and canary instances are excluded from the candidate pool in both dedup branches (`service.py:813`, `834`).
- A canary that is not filtered is stored with `filter_action = none`. Case creation is skipped (`flows.py:103-104`).

### Things I noticed in the code

- The `filter_signal` docstring (`service.py:872-874`) says the default dedup window is 1 hour. The code uses the 45-minute config default.
- In the filter-based dedup branch, `instances[0].case_id` is not checked for null. The default branch does filter on `case_id IS NOT NULL`, but this branch does not. If the earliest match has no case, `case_id` becomes null and `filter_action` is still set to `deduplicate`, so the instance counts as filtered and no case is created. I did not run this, so it's an inference from reading the query.
- `filter_snooze` `break`s on the first expired snooze filter, so an expired filter earlier in the list hides any active snooze filters after it.

I only read the code and did not run any tests.