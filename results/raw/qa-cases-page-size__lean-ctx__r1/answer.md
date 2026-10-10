The Cases table shows 40 rows per page when first opened.

`Table.vue` declares `const itemsPerPage = ref(40)` at line 185 and binds it to the table with `:items-per-page="itemsPerPage"` at line 61. When the table loads, `loadItems` copies that value into the store's `table.options.itemsPerPage` and fetches the cases.

The Vuex store module for cases declares a different default. `src/case/store.js:141` has `itemsPerPage: 25`. The 40 in `Table.vue` is what the user sees first, and the store's 25 is overwritten as soon as the table loads.

DEFAULT: 40
FILE: src/dispatch/static/dispatch/src/case/Table.vue
STORE_DEFAULT: 25