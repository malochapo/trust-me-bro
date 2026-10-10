The Cases table shows 40 cases per page when a user first opens it. `Table.vue` sets that value with `const itemsPerPage = ref(40)` and passes it to the table as `:items-per-page`. The page-size options in the same file are 10, 20, 40 and 80.

The Vuex store module for cases declares a different default. In `table.options` it has `itemsPerPage: 25`. The initial 40 overrides that, because the component's own value is what the table uses.

DEFAULT: 40
FILE: src/dispatch/static/dispatch/src/case/Table.vue
STORE_DEFAULT: 25