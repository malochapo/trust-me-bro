The Cases table shows 40 cases per page when first opened.

The table component sets that value with `const itemsPerPage = ref(40)` at line 185 of `Table.vue`. It binds the value to the table with `:items-per-page="itemsPerPage"` (line 61). The page-size choices it offers are 10, 20, 40 and 80.

The Vuex `case_management` store declares `itemsPerPage: 25` in `table.options` (line 141 of `case/store.js`). The Table component's 40 overrides that for the first render. The store's 25 is only used when the options are sent to the API: `getAll` is dispatched with `table.options` (line 207), and `loadItems` copies the grid's page size back into the store.

I read the code only and didn't run the UI to confirm.

DEFAULT: 40
FILE: src/dispatch/static/dispatch/src/case/Table.vue
STORE_DEFAULT: 25