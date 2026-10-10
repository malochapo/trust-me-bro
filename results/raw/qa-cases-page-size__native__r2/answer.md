The Cases table shows 40 cases per page when it first opens.

`src/dispatch/static/dispatch/src/case/Table.vue:185` sets the initial value with `const itemsPerPage = ref(40)`. The table binds it through `:items-per-page="itemsPerPage"` at line 61. After that, `loadItems` (line 241) writes whatever page size the table reports back into the store.

The Vuex module for cases, `src/dispatch/static/dispatch/src/case/store.js:141`, declares `itemsPerPage: 25` in `table.options`. The component's 40 is what the user sees at first. The store's 25 is only the declared default.

DEFAULT: 40
FILE: src/dispatch/static/dispatch/src/case/Table.vue
STORE_DEFAULT: 25