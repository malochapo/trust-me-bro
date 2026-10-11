When a user first opens the Cases table, it shows **40** rows per page. The initial value comes from `itemsPerPage = ref(40)` in `src/dispatch/static/dispatch/src/case/Table.vue:185`, and that ref is bound to the table's `:items-per-page` prop (line 61).

The Vuex store module for cases (`src/dispatch/static/dispatch/src/case/store.js:141`) declares `itemsPerPage: 25` in its `table.options` defaults. The table does not seem to read that value on first render. The store's 25 is therefore not what the user sees initially. I did not run the app to confirm which value the table ends up displaying, so the 40 is based on reading the code.

DEFAULT: 40
FILE: src/dispatch/static/dispatch/src/case/Table.vue
STORE_DEFAULT: 25