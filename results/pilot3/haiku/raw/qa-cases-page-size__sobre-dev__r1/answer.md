On first open, the Cases table shows **40** rows per page. The value comes from `ref(40)` in the table component, and that is what the `v-data-table-server` binding uses as its `items-per-page` value.

The Vuex store module for cases (`case_management`, in `case/store.js`) declares a default of **25** in `table.options.itemsPerPage` (line 141). The table component's `loadItems` handler overwrites that store value with whatever the table reports, so the 40 shown on first render is the one that takes effect.

DEFAULT: 40
FILE: src/dispatch/static/dispatch/src/case/Table.vue
STORE_DEFAULT: 25