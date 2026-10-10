The Cases table shows 40 cases per page when a user first opens it.

The initial value is set in `Table.vue`, which declares `const itemsPerPage = ref(40)` and binds it to the table's `:items-per-page`. Its page-size options are `[10, 20, 40, 80]`, so 40 is one of the choices.

The Vuex store module for cases, `store.js` in the same directory, declares `itemsPerPage: 25` in `table.options`. The component's 40 overrides that value for the initial display. Once the table fires `update:options`, `loadItems` writes the table's `itemsPerPage` back into the store.

DEFAULT: 40
FILE: src/dispatch/static/dispatch/src/case/Table.vue
STORE_DEFAULT: 25