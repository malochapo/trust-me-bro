The Cases table shows 40 cases per page when it first opens. `Table.vue` sets that with `const itemsPerPage = ref(40)` and binds it to the table's `:items-per-page`. The page-size options offered are 10, 20, 40 and 80.

The Vuex store module for cases declares a different default for the same table. In `store.js`, `table.options.itemsPerPage` is 25. The component's 40 is what the user sees at first. The store's 25 only matters if something reads it before the table has loaded.

The file is `src/dispatch/static/dispatch/src/case/Table.vue`, and the store module is `src/dispatch/static/dispatch/src/case/store.js`.

DEFAULT: 40
FILE: src/dispatch/static/dispatch/src/case/Table.vue
STORE_DEFAULT: 25