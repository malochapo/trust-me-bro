The Cases table shows **40** rows per page on first open. The value comes from `const itemsPerPage = ref(40)` in `src/dispatch/static/dispatch/src/case/Table.vue:185`, which is bound to the table's `:items-per-page` prop at line 61. The Vuex store's `case_management` table options declare `itemsPerPage: 25` (`src/dispatch/static/dispatch/src/case/store.js:141`), so the store default is 25, not the 40 the user sees. The table's `loadItems` handler copies the table's page size into the store, so the store's 25 is overwritten on first load.

DEFAULT: 40
FILE: src/dispatch/static/dispatch/src/case/Table.vue
STORE_DEFAULT: 25