On first open, the Cases table shows 40 rows per page. The local `itemsPerPage` ref in `Table.vue` sets this, and it is bound to the table's `:items-per-page` prop.

The Vuex store module for cases (`case_management`, in `store.js`) declares `itemsPerPage: 25` in its `table.options` state. The `itemsPerPage: 50` at line 534 belongs to a different request (plugin instances), not the table.

The store default is overwritten by `loadItems` when the table emits its options, so the displayed value is 40 on first open.

DEFAULT: 40
FILE: src/dispatch/static/dispatch/src/case/Table.vue
STORE_DEFAULT: 25