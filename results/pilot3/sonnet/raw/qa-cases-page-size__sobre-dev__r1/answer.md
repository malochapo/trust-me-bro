When a user first opens the Cases table, it shows **40 cases per page**. `Table.vue` sets this with `const itemsPerPage = ref(40)` at line 185, and binds it to the table through `:items-per-page="itemsPerPage"`. The page-size choices offered are 10, 20, 40 and 80.

The Vuex store module for cases declares a different default for the same table. In `case/store.js` the table options set `itemsPerPage: 25` (line 141). The component's 40 is what the user sees on first load.

I didn't run the UI. This comes from reading the two files. I didn't trace whether the store's 25 is applied before the component renders.

The other `itemsPerPage: 50` in `store.js`, near line 534, is a separate plugin-lookup request, not the table.

DEFAULT: 40
FILE: src/dispatch/static/dispatch/src/case/Table.vue
STORE_DEFAULT: 25