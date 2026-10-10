The Cases table shows 40 rows per page when it first opens. `Table.vue` sets that value with `const itemsPerPage = ref(40)`, and it is bound to the table through `:items-per-page="itemsPerPage"` at line 61.

The Vuex store module for cases declares a different default, 25, in `case_management.table.options.itemsPerPage` at line 141 of `src/dispatch/static/dispatch/src/case/store.js`. That value only seeds the store. The table's `loadItems` handler overwrites it with whatever the component passes, which starts at 40.

I read the code but did not run the UI to confirm the 40 on screen.

DEFAULT: 40
FILE: src/dispatch/static/dispatch/src/case/Table.vue
STORE_DEFAULT: 25