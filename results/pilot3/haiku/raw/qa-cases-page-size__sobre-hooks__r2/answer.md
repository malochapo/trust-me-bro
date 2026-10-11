The Cases table opens with **40** rows per page. The table's own `itemsPerPage` ref in `Table.vue` sets this, and the table only shows the value from the store once the user changes it.

The store's `case_management` module declares a default of **25** for the same table (`table.options.itemsPerPage`). That 25 doesn't reach the first render, because `Table.vue` passes its own ref (40) to the table and `loadItems` writes the store value only after the table emits `update:options`. The store's 25 would take effect only if that update reports a different value, which I did not trace further.

The other `itemsPerPage: 50` in `store.js` (line 534) belongs to a different request, a plugin-type lookup, and is unrelated to the Cases table.

- Initial value: `src/dispatch/static/dispatch/src/case/Table.vue:185` (`const itemsPerPage = ref(40)`)
- Store default: `src/dispatch/static/dispatch/src/case/store.js:141` (`itemsPerPage: 25`)

DEFAULT: 40
FILE: src/dispatch/static/dispatch/src/case/Table.vue
STORE_DEFAULT: 25