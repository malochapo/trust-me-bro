The Cases table shows 40 rows per page when it first opens.

- **Where the 40 comes from:** `Table.vue` declares `const itemsPerPage = ref(40)` (line 185) and binds it to the table with `:items-per-page="itemsPerPage"` (line 61). I didn't open the full `Table.vue` template, so I haven't checked whether anything overrides this binding on load.
- **Store default:** the `case` Vuex module's `table.options` in `case/store.js` declares `itemsPerPage: 25` (line 141). The Cases table doesn't use this on first open, because the component's 40 is what gets bound.
- **Possible mismatch:** `loadItems` in `Table.vue` writes the table's current `itemsPerPage` back into `caseManagement.value.table.options` (line 243). I didn't check whether that call fires on the first load or only after the user changes the page size.
- **Not the table default:** `store.js` also has an `itemsPerPage: 50` at line 534, but it's a request parameter for a plugin-instance lookup, not the table option.

DEFAULT: 40
FILE: src/dispatch/static/dispatch/src/case/Table.vue
STORE_DEFAULT: 25