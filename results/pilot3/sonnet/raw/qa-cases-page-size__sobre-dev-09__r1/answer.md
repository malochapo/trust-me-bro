The Cases table shows 40 cases per page when a user first opens it. `itemsPerPage` is set with `const itemsPerPage = ref(40)` at line 185 of `case/Table.vue`, and the table binds it with `:items-per-page="itemsPerPage"` at line 61. The page-size choices offered are 10, 20, 40 and 80.

The Vuex store module for cases declares a different default. In `case/store.js`, `table.options.itemsPerPage` is 25 (line 141). The 40 in `Table.vue` is what the user sees first. I didn't trace whether the 25 is ever applied to the table at load time. `loadItems` overwrites it with the table's own `itemsPerPage` value.

All paths are under `src/dispatch/static/dispatch/src/`.

DEFAULT: 40
FILE: src/dispatch/static/dispatch/src/case/Table.vue
STORE_DEFAULT: 25