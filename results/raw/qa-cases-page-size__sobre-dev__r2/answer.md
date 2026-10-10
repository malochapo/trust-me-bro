The Cases table shows 40 cases per page when a user first opens it. `Table.vue` sets that value with `const itemsPerPage = ref(40)` (line 185) and passes it to the table through `:items-per-page="itemsPerPage"` (line 61). The page-size options are 10, 20, 40 and 80.

The Vuex store module for cases declares a different default. In `case/store.js`, `table.options.itemsPerPage` is 25 (line 141). The table doesn't use this value for its initial page size, because `Table.vue` has its own local value of 40.

I didn't run the app to confirm the 40 in the browser. I read it from the source.

DEFAULT: 40
FILE: src/dispatch/static/dispatch/src/case/Table.vue
STORE_DEFAULT: 25