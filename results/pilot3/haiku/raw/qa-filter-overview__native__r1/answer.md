## Short answer

For each new `SignalInstance`, `filter_signal` checks snooze first, then deduplication, and only if neither applies does the instance continue toward case creation. Canaries skip deduplication and never get a case. The default dedup window is 45 minutes in code, although the docstring and docs say one hour.

## Entry point and order

`signal_instance_create_flow` (`src/dispatch/signal/flows.py:46`) redacts the raw payload, extracts entities, then calls `signal_service.filter_signal` (`flows.py:78`). The order is:

1. **`filter_snooze`** (`src/dispatch/signal/service.py:743`) runs first.
2. **`filter_dedup`** (`service.py:789`) runs only if `filter_action` is still unset.
3. If neither set `filter_action`, it is set to `none` and the instance is not filtered (`service.py:866-899`, `filter_signal`).

Back in the flow, a filtered instance returns early (`flows.py:78-101`). If a case and conversation already exist and the action was deduplicate, the Slack signal message may be updated. Otherwise the code continues:

- `flows.py:103`: if `canary`, return without creating a case.
- If `signal.create_case` is false, return.
- Otherwise resolve case type, priority, oncall service and conversation target, then create the case.

## Snooze (`filter_snooze`)

- Iterates `signal.filters` in order. Only filters with `mode == active` and `action == snooze` are considered; other modes are ignored.
- A snooze filter with no `expiration` is skipped with a warning.
- If `expiration` is in the past, the loop `break`s. Later snooze filters are not evaluated, even if they would match.
- **No expression:** every instance of that signal is snoozed until expiry.
- **With expression:** the expression is applied to the signal's instances (`apply_filter_specific_joins`, `apply_filters`), and the filter matches only if the current instance's id is in the result. The first match sets `filter_action = snooze` and stops.
- There is no time window for snooze. It matches on the expression and the expiration.

## Deduplication (`filter_dedup`)

- **Canary:** returns immediately, so canaries are never deduplicated.
- **Default path**, used only when the signal has no filters at all (`service.py:800-824`):
  - Lookback window is `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds (`config.py:95-96`, default **45 minutes**, so 2700 seconds). `_window_start` (`service.py:784`) computes the cutoff from `now`.
  - Candidates must be the same signal, created within the window, not the current instance, with a non-null `case_id`, and not canary.
  - Entities are not compared. The most recent candidate (`order_by desc(created_at)`) supplies the case. Every instance of the signal in the window groups together.
- **Filter path**, used when the signal has at least one filter (`service.py:826-863`):
  - Only `mode == active` filters with `action == deduplicate` are considered. If the signal has other filters but no active dedup filter, no dedup happens and the default path is not used.
  - `SignalFilter.window` is in seconds, and the cutoff is `now - window`.
  - Candidates must be the same signal, in the window, not canary, not the current instance, and share at least one entity with the current instance, with `apply_filters(query, f.expression)` applied to the candidates' entities and entity types.
  - The earliest matching candidate (`order_by asc(created_at)`) supplies `case_id`. Unlike the default path, this query does not require `case_id` to be non-null, so it can set `deduplicate` with `case_id = None`.

## Time windows and defaults

| Item | Unit | Value in code |
|---|---|---|
| `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` | minutes (converted to seconds) | 45 (`config.py:95-96`) |
| `SignalFilter.window` column | seconds | DB default 3600 (`models.py:206-208`) |
| `SignalFilterBase.window` (API schema) | seconds | 600 (`models.py:282`) |
| Snooze | none | expiration timestamp only |

The API-schema default of 600 seconds is what gets stored when a client omits `window`. The DB column default of 3600 applies only to rows inserted without the field. The `filter_signal` docstring and `docs/docs/administration/settings/signal/filter.mdx:35` both say one hour, which does not match the 45-minute code default.

## Canary signals

- **Snooze:** `filter_snooze` has no canary check, so a canary can be snoozed like any other instance.
- **Deduplication:** a canary is never deduplicated (`service.py:801`), and canaries are excluded from both the default and filter dedup candidate queries (`service.py:813`, `:834`).
- **Case creation:** a non-snoozed canary is stored with `filter_action = none` and returns at `flows.py:103` without creating a case.

## Other things I noticed

- `filter_snooze` `break`s on an expired filter, so later snooze filters are not checked.
- A signal with any filter set (even only snooze or monitor filters) never uses the 45-minute default dedup.
- The default and filter dedup paths choose different candidates: most recent versus earliest.

I read the code and did not run anything or test these paths.