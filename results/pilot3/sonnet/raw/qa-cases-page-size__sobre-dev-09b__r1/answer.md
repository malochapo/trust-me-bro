The Cases table shows 40 cases per page when it first opens. `src/dispatch/static/dispatch/src/case/Table.vue:185` sets this with `const itemsPerPage = ref(40)`, and line 61 binds it to the table's `:items-per-page`. The page-size options on that table are 10, 20, 40 and 80.

The Vuex store module at `case/store.js:141` declares `itemsPerPage: 25` in the cases table options. The component's 40 is what the user sees at first. When the table loads items, `loadItems` (line 243) writes the table's page size back into that store option, replacing the 25.

DEFAULT: 40
FILE: src/dispatch/static/dispatch/src/case/Table.vue
STORE_DEFAULT: 25