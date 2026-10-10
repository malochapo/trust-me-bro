The Cases table shows 40 cases per page when it first opens.

`src/dispatch/static/dispatch/src/case/Table.vue` sets this with `const itemsPerPage = ref(40)` at line 185. The table binds to it with `:items-per-page="itemsPerPage"` at line 61.

The Vuex store module `src/dispatch/static/dispatch/src/case/store.js` declares `itemsPerPage: 25` at line 141, in the table options. The component's 40 overrides that for the initial page size. I didn't read the store's surrounding lines, so I'm assuming line 141 is that table-options default.

DEFAULT: 40
FILE: src/dispatch/static/dispatch/src/case/Table.vue
STORE_DEFAULT: 25