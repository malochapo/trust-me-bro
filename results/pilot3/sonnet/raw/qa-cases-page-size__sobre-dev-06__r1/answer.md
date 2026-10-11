The Cases table shows 40 rows per page when a user first opens it. `src/dispatch/static/dispatch/src/case/Table.vue` sets that with `const itemsPerPage = ref(40)` at line 185 and passes it to the data table as `:items-per-page="itemsPerPage"` at line 61. Its page-size options are `[10, 20, 40, 80]`.

The Vuex store module for cases, `src/dispatch/static/dispatch/src/case/store.js`, declares `table.options.itemsPerPage: 25` at line 141. That value isn't what the user sees first. The component's local 40 is what the table is given, and `loadItems` then writes the table's chosen size back into the store.

DEFAULT: 40
FILE: src/dispatch/static/dispatch/src/case/Table.vue
STORE_DEFAULT: 25