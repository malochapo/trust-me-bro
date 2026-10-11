On a first visit, the Cases table shows **40** rows per page. The Vuex store module for cases declares **25** for the same table.

- **Initial value:** `src/dispatch/static/dispatch/src/case/Table.vue` line 185 has `const itemsPerPage = ref(40)`. That ref is bound to the table's `items-per-page` prop (line 61), and `loadItems` writes it into `caseManagement.table.options.itemsPerPage` (line 243).
- **Store default:** `src/dispatch/static/dispatch/src/case/store.js` line 141 sets `itemsPerPage: 25` in the module's `state.table.options`. The other `itemsPerPage: 50` at line 534 is in a different action (it fetches plugin types), so it doesn't apply to the table.

The component's 40 overrides the store's 25 when the table mounts, so the 25 is only seen before the component sets its own value.

DEFAULT: 40
FILE: src/dispatch/static/dispatch/src/case/Table.vue
STORE_DEFAULT: 25