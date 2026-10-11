The Cases table shows **40 cases per page** when a user first opens it.

- **Where it's set:** `Table.vue` declares `const itemsPerPage = ref(40)` at line 185. It binds that value to the data table with `:items-per-page="itemsPerPage"` at line 61. The page-size options offered are 10, 20, 40 and 80.
- **Store default:** The cases Vuex module (`case/store.js`, line 141) declares `table.options.itemsPerPage: 25`. The table doesn't use this for its first render. Once the table loads, its `loadItems` handler overwrites the store value with whatever the table is using, so the store value becomes 40 as well.

There is also an `itemsPerPage: 50` at line 534 of `store.js`. It belongs to a plugin-type lookup request, not the table.

DEFAULT: 40
FILE: src/dispatch/static/dispatch/src/case/Table.vue
STORE_DEFAULT: 25