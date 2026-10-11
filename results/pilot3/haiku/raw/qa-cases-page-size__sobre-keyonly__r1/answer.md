When a user first opens the Cases table, it shows **40 rows per page**. The Vuex store's `case_management` module declares **25**.

The 40 comes from a local ref in `src/dispatch/static/dispatch/src/case/Table.vue:185` (`const itemsPerPage = ref(40)`), which is bound to the table's `:items-per-page` prop at line 61. The store's default is `itemsPerPage: 25` in `src/dispatch/static/dispatch/src/case/store.js:141`, inside `case_management.table.options`. A second `itemsPerPage: 50` at `store.js:534` belongs to a different request, the plugin-type lookup, not the Cases table.

I did not run the app, so I haven't confirmed the 40-row display in a browser. The 25 in the store is only the initial options state; `Table.vue`'s `loadItems` overwrites it with whatever the table reports.

DEFAULT: 40
FILE: src/dispatch/static/dispatch/src/case/Table.vue
STORE_DEFAULT: 25