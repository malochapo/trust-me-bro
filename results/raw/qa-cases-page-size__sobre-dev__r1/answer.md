The Cases table shows 40 cases per page when it first opens.

`Table.vue` sets that value with `const itemsPerPage = ref(40)` (line 185) and binds it to the table through `:items-per-page="itemsPerPage"` (line 61). Once the table loads, `loadItems` writes the table's actual page size back into the store (line 243).

The Vuex cases module, `case/store.js`, declares `itemsPerPage: 25` under `table.options` (line 141). That 25 doesn't control the first render, because the component's 40 is what the table uses.

I read the code but didn't run the app.

DEFAULT: 40
FILE: src/dispatch/static/dispatch/src/case/Table.vue
STORE_DEFAULT: 25