The Cases table shows **40** rows per page when a user first opens it. The value comes from `const itemsPerPage = ref(40)` in `src/dispatch/static/dispatch/src/case/Table.vue:185`, which is bound to the table's `:items-per-page` prop.

The Vuex store module for cases (`src/dispatch/static/dispatch/src/case/store.js:141`) declares `itemsPerPage: 25` in its `case_management.table.options` state. That value doesn't set the table's first render, because the table's local ref (40) wins, and `loadItems` then writes the table's current page size back into the store. A second `itemsPerPage: 50` at `store.js:534` belongs to a separate API request, not the table's default.

So the two values disagree: 40 in the component, 25 in the store.

DEFAULT: 40
FILE: src/dispatch/static/dispatch/src/case/Table.vue
STORE_DEFAULT: 25