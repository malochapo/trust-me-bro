The Cases table shows 40 cases per page when it first opens.

- **Initial value:** `Table.vue` declares `const itemsPerPage = ref(40)` and binds it to the table with `:items-per-page="itemsPerPage"`. The page-size options offered are 10, 20, 40 and 80.
- **Store default:** the Vuex cases module declares `itemsPerPage: 25` in its `table.options` (`case/store.js`, line 141). It doesn't set what the user sees on first open, because the component's 40 is what the table is given.

All paths below are under `src/dispatch/static/dispatch/src/`.

DEFAULT: 40
FILE: src/dispatch/static/dispatch/src/case/Table.vue
STORE_DEFAULT: 25