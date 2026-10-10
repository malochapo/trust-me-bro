The Cases table shows 40 rows per page when it first opens.

- **Initial value:** `Table.vue` sets it with `const itemsPerPage = ref(40)` (line 185). That value is bound to the table with `:items-per-page="itemsPerPage"` (line 61). The page-size menu offers 10, 20, 40 and 80.
- **Store default:** The Vuex module for cases declares `itemsPerPage: 25` in `table.options`, in `store.js` at line 141.
- **Why the two differ:** The store's 25 is not what the user first sees. Once the table loads, its `loadItems` handler (line 241 of `Table.vue`) writes the table's current page size back into the store (line 243).

DEFAULT: 40
FILE: src/dispatch/static/dispatch/src/case/Table.vue
STORE_DEFAULT: 25