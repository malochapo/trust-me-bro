The Cases table shows **40** rows per page on first open. The initial value is set in `Table.vue`, which declares `const itemsPerPage = ref(40)` and binds it to `v-data-table-server` via `:items-per-page`. The table's footer offers 10, 20, 40, and 80, so 40 is a valid option.

The case Vuex store module declares `itemsPerPage: 25` in its `table.options` (`src/dispatch/static/dispatch/src/case/store.js:141`). That store value doesn't set the first-open view, because the table's `loadItems` handler writes the table's own `itemsPerPage` (40) back into the store when the table's options update. I didn't run the app to confirm this at runtime; the answer comes from reading the code.

DEFAULT: 40
FILE: src/dispatch/static/dispatch/src/case/Table.vue
STORE_DEFAULT: 25