On first open, the Cases table shows **40** rows per page. The initial value is set in `Table.vue` (`const itemsPerPage = ref(40)`), which is bound to the table's `:items-per-page` prop. The case store module declares **25** for `table.options.itemsPerPage` (`store.js:141`), so the store default differs from what the table shows.

I haven't run the app, so the 40 comes from reading the code. The table's `update:options` handler writes its own `itemsPerPage` back into the store, which is why the page size ends up as 40 even though the store starts at 25. One detail I didn't confirm: the mount-time `getAll` call (`Table.vue:207`) reads the store options, so it may briefly request 25 before the table's emitted options replace that value.

The `store.js:534` value of 50 belongs to a different action (a plugin-type lookup), not the cases table, so I ignored it.

Paths are relative to the repo root.

DEFAULT: 40
FILE: src/dispatch/static/dispatch/src/case/Table.vue
STORE_DEFAULT: 25