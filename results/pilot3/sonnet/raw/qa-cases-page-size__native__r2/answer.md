The Cases table shows 40 cases per page when a user first opens it.

The component sets that value with `const itemsPerPage = ref(40)` at line 185 of `src/dispatch/static/dispatch/src/case/Table.vue`. The same file binds it to the table with `:items-per-page="itemsPerPage"`, and the page-size options it offers are 10, 20, 40 and 80.

The Vuex store module for cases (`case/store.js`) declares `itemsPerPage: 25` in `table.options` (line 141). The component's value of 40 is what a user sees on first open. I didn't trace whether anything syncs the store's value into the component. The component writes the chosen page size back into the store inside `loadItems` (line 243).

DEFAULT: 40
FILE: src/dispatch/static/dispatch/src/case/Table.vue
STORE_DEFAULT: 25