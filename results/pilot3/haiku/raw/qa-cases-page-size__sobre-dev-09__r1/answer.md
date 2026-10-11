When a user first opens the Cases table, it shows **40** rows per page. The Vue component sets that: `const itemsPerPage = ref(40)` in `case/Table.vue:185`, bound to the table's `:items-per-page` prop at line 61. The footer offers 10, 20, 40, and 80.

The Vuex store module for cases declares `itemsPerPage: 25` in the `table.options` block at `case/store.js:141`. The component's value of 40 wins on first render, and `loadItems` (`case/Table.vue:241`) then writes the page size into the store. The other `itemsPerPage: 50` at `case/store.js:534` is an unrelated plugin-type lookup, not the table default.

I did not run the app to confirm the rendered page size. The answer comes from reading the code.

DEFAULT: 40
FILE: src/dispatch/static/dispatch/src/case/Table.vue
STORE_DEFAULT: 25