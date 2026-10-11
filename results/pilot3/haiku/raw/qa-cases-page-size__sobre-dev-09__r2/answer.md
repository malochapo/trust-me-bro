The Cases table shows **40** rows per page on first open. The value comes from `ref(40)` in `src/dispatch/static/dispatch/src/case/Table.vue:185`, which is bound to the table's `:items-per-page` prop at line 61. The table's footer offers 10, 20, 40, and 80 per page.

The Vuex store module for cases (`src/dispatch/static/dispatch/src/case/store.js`, the `table.options` block around line 141) declares `itemsPerPage: 25`. So the store default and the table's initial value disagree. The table's initial 40 is what the user sees, because the component sets its own value rather than reading the store's 25. I did not run the app to confirm the rendered result.

DEFAULT: 40
FILE: src/dispatch/static/dispatch/src/case/Table.vue
STORE_DEFAULT: 25