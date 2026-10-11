The Cases table shows **40** rows per page on first open. The component sets `const itemsPerPage = ref(40)` in `Table.vue`, and that local value drives the table's `items-per-page` binding. The Vuex store module for cases declares `itemsPerPage: 25` in its `table.options` state, so the store default differs from the initial UI value.

- `src/dispatch/static/dispatch/src/case/Table.vue:185` sets the initial value to 40.
- `src/dispatch/static/dispatch/src/case/store.js:141` declares 25 in the case management table options.

I didn't run the app, so the 40 comes from reading the code rather than observing the page.

DEFAULT: 40
FILE: src/dispatch/static/dispatch/src/case/Table.vue
STORE_DEFAULT: 25