The Cases table shows 40 cases per page when a user first opens it.

`ref(40)` in `src/dispatch/static/dispatch/src/case/Table.vue:185` sets that initial value. It feeds the table's `:items-per-page` binding on line 61, and the page-size options offered are 10, 20, 40 and 80.

The Vuex module for cases, `case/store.js`, declares `itemsPerPage: 25` in its table options (line 141). That default is not what the user sees first. `loadItems` in `Table.vue` (line 243) overwrites the store value with whatever page size the table component reports.

The `itemsPerPage: 50` at line 534 of `store.js` is unrelated. It is a plugin-lookup query limit, not a table setting.

DEFAULT: 40
FILE: src/dispatch/static/dispatch/src/case/Table.vue
STORE_DEFAULT: 25