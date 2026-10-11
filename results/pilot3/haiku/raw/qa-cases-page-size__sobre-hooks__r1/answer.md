The Cases table shows **40** rows per page when a user first opens it. That value comes from `const itemsPerPage = ref(40)` in the Cases table component.

The Vuex store module for cases (`case_management`) declares a default of **25** in `case/store.js` (`itemsPerPage: 25`, around line 141). That is the store's own initial `table.options`. The table component doesn't use it on first render: it binds its local `itemsPerPage` ref (40) to the data table, and the first `update:options` event sends that value back into the store.

The store also has `itemsPerPage: 50` at line 534, but that is in an unrelated request for plugin types, not the cases table.

I read these from the code only; I did not run the app to confirm the rendered row count.

DEFAULT: 40
FILE: src/dispatch/static/dispatch/src/case/Table.vue
STORE_DEFAULT: 25