The Cases table shows 40 cases per page when it first opens.

The initial value comes from `const itemsPerPage = ref(40)` in `src/dispatch/static/dispatch/src/case/Table.vue` (line 185). That value is passed to the table as `:items-per-page="itemsPerPage"`. The page-size choices offered are 10, 20, 40 and 80.

The Vuex store module for cases, `src/dispatch/static/dispatch/src/case/store.js`, declares `table.options.itemsPerPage: 25` (line 141). The component's 40 is what the user sees, because the table is bound to the component's local value rather than the store's.

The `itemsPerPage: 50` at line 534 of `store.js` is a separate request parameter and is not part of the table options.

DEFAULT: 40
FILE: src/dispatch/static/dispatch/src/case/Table.vue
STORE_DEFAULT: 25