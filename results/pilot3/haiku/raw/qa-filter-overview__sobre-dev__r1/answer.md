**Short answer:** for each new instance, `filter_signal` checks snooze first, then deduplication, then falls through to "no filter" and case creation. Canary instances can be snoozed, are never deduplicated, and never get a case. Everything below is from reading the code; I did not run it.

## Order of checks

`signal_instance_create_flow` (`src/dispatch/signal/flows.py:46`) does this in order:

1. Loads the instance and redacts `raw`.
2. Finds entities via `entity_service.find_entities` and saves them. This happens before any filter runs, so filters can match on entities.
3. Calls `signal_service.filter_signal` (`flows.py:78`, defined at `src/dispatch/signal/service.py:866`):
   - `filter_snooze` runs first.
   - `filter_dedup` runs only if no `filter_action` was set by the snooze step.
   - If neither matches, `filter_action` is set to `SignalFilterAction.none`. Otherwise the instance counts as filtered. The session is committed either way.
4. If filtered, the flow optionally refreshes the existing Slack signal message (`update_signal_message`, only for deduplicated instances) and returns. No case is created and no workflows run.
5. If `signal_instance.canary` is set, the flow returns (`flows.py:103`).
6. If `signal.create_case` is false, the flow returns.
7. Otherwise it creates a case via `case_service.create`, runs `case_flows.case_new_create_flow`, engages identities, and runs workflows.

Instances are picked up for processing only when `filter_action` is NULL (`signal/service.py:911`, `cli.py:992`), through `process_signal_batch` and `main_processing_loop`.

## Snooze: `filter_snooze` (`service.py:743`)

Iterates `signal.filters` and skips any filter that is not `mode == active` with `action == snooze`.

- **No expiration:** logs a warning and skips the filter.
- **Expired** (`expiration <= now`, UTC): executes `break`, which ends the loop. Any later snooze filters are not evaluated for this instance. This is a quirk, since an expired filter stops the scan rather than being skipped.
- **Has an expression:** builds a query over the signal's instances using `apply_filter_specific_joins` and `apply_filters` (`database/service.py:450` and `:387`), then checks whether this instance's own row matches. A match sets `filter_action = snooze` and breaks. A non-match moves on to the next filter.
- **No expression:** snoozes every instance of the signal until expiration.

There is no time window for snoozes. Only `expiration` matters. The only match criteria are the expression applied to the instance and its signal.

## Deduplication: `filter_dedup` (`service.py:789`)

- **Canary:** returns immediately (`service.py:801`).
- **No filters on the signal (default path, `service.py:800-826`):**
  - Window: `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60`, from `config.py:95`. The default is **45 minutes**, overridable by environment variable.
  - Candidates: other instances of the same signal, created inside the window, with `case_id` set, excluding canary instances and the instance itself.
  - Entities are **not** compared. Any matching instance counts.
  - Takes the most recent candidate (`order_by created_at desc`, `first()`) and copies its `case_id`.
- **Signal has filters (custom path, `service.py:828-863`):**
  - Only filters with `mode == active` and `action == deduplicate` are used. The default path does not run in this case, so a signal with filters that has no active dedup filter is never deduplicated.
  - For each such filter, in order, the candidates are the signal's non-canary instances that share at least one entity with this instance (`Entity.id IN` this instance's entities) and that match `f.expression` through `apply_filters`.
  - Window: `f.window` **seconds** (`service.py:846`). The `SignalFilter` model column defaults to 3600 (1 hour, `signal/models.py:206-208`). The API schema `SignalFilterBase.window` defaults to 600 (10 minutes, `models.py:282`), which is what API-created filters get unless set.
  - Takes the earliest candidate (`order_by created_at asc`) and copies its `case_id`. The first matching filter wins.

Note that `filter_signal`'s docstring says the default window is 1 hour, which is stale. The code uses 45 minutes.

## Canary signals

- **Snooze:** `filter_snooze` has no canary check, so a canary instance can be snoozed. It is then counted as filtered and returns before the canary branch.
- **Dedup:** `filter_dedup` returns early for canary instances, so they are never deduplicated.
- **Visibility to others:** canary instances are excluded from every dedup candidate query (`~SignalInstance.canary`, `service.py:813` and `:834`). A real instance never attaches to a canary's case.
- **Case creation:** an unfiltered canary is stored with `filter_action = none` and the flow returns at `flows.py:103`. It never creates a case or runs workflows.

## Summary of outcomes

| Result | Set by | `filter_action` | Case |
|---|---|---|---|
| Snoozed | `filter_snooze` | `snooze` | none created; instance keeps its existing `case_id` if any |
| Deduplicated | `filter_dedup` | `deduplicate` | copies `case_id` from matched instance |
| New case | neither matches | `none` | created, unless `create_case` is false or the instance is canary |