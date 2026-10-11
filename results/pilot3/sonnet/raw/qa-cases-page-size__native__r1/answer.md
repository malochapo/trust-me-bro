The Cases table shows 40 cases per page when it first opens.

- **Where it's set:** `src/dispatch/static/dispatch/src/case/Table.vue:185` declares `const itemsPerPage = ref(40)`. The table binds this to `:items-per-page`, and the page-size menu offers 10, 20, 40 and 80.
- **Store default:** the `case_management` Vuex module in `src/dispatch/static/dispatch/src/case/store.js:141` declares `itemsPerPage: 25` in `table.options`. The component's 40 overrides this on first load. Once the table's options-update handler (`loadItems`) fires, it writes the table's current page size back into the store.

DEFAULT: 40
FILE: src/dispatch/static/dispatch/src/case/Table.vue
STORE_DEFAULT: 25