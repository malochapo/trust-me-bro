The Cases table shows 40 rows per page when it first opens.

`Table.vue` sets that with `const itemsPerPage = ref(40)` at line 185. It passes the value to the data table through `:items-per-page="itemsPerPage"`, and the page-size options are `[10, 20, 40, 80]`.

The Vuex store module for cases (`store.js`, in the `case_management` table options at line 141) declares `itemsPerPage: 25`. That value doesn't control the first render. The component's local 40 wins, and the store value is only overwritten later by `loadItems`.

All paths are under `src/dispatch/static/dispatch/src/case/`.

DEFAULT: 40
FILE: src/dispatch/static/dispatch/src/case/Table.vue
STORE_DEFAULT: 25