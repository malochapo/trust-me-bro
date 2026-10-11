Filters now carry an optional `reason`, from the database through the API to the Snoozes table and the create dialog. The signal test files pass (`tests/signal/test_signal_filter_service.py`: 6 passed, including two new tests for `reason` on create and update).

**What changed**
- **Model** (`src/dispatch/signal/models.py`): `SignalFilter.reason` is a nullable `String`. It's added to `SignalFilterBase`, so create, update, and read all accept and return it.
- **Migration** (`src/dispatch/database/revisions/tenant/versions/2026-10-10_3c9a1f7e2b58.py`): adds the `reason` column to `signal_filter`, revising `ff08d822ef2c`, which is the current head.
- **Snoozes table** (`TableInstanceSnoozes.vue`): new sortable "Reason" column after Description.
- **Create dialog** (`SignalFilterCreateDialog.vue`, `filter/store.js`): optional "Reason" textarea on the final Save step, after Description. It's mapped to `selected.reason` and defaults to null.

**Choices I made**
- The reason field is optional and sits on the Save step beside Description. It has no required rule.
- The column is `String` with no length limit, matching `description`.

**Verification gaps**
- **Test DB workaround:** the test database couldn't be created as-is. The local cluster's `template1` is `SQL_ASCII`, which breaks creating a UTF8 database, so every test errored at setup. I didn't change the repo. I ran the tests with a plugin in `/tmp/sobre-bench-work/pgfix/` that creates the test DB from `template0`. The fixture needs that plugin, so run with `PYTHONPATH=/tmp/sobre-bench-work/pgfix python -m pytest -p pgtemplate0 …`. You may want to fix the cluster or the fixture so plain `python -m pytest` works.
- **Migration not run:** I didn't run `alembic upgrade` against a database. I checked the file by reading it against existing migrations.
- **Frontend not built or linted:** prettier isn't installed locally, so the Vue changes haven't been compiled or formatted-checked. I also didn't render the UI.
- **Lint:** `ruff check` passes on the changed Python. `ruff format` flags one pre-existing blank-line issue in `models.py`, outside my change.

Nothing is committed. The changes are in the working tree, along with the new migration file.