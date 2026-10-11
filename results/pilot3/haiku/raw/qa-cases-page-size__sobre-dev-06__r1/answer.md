When a user first opens the Cases table, it shows **40** rows per page. The initial value comes from `const itemsPerPage = ref(40)` in `src/dispatch/static/dispatch/src/case/Table.vue:185`. The Vuex case module (`src/dispatch/static/dispatch/src/case/store.js:141`) declares `itemsPerPage: 25` for the same table's options, so the two defaults disagree. I did not check whether the store value ever overrides the component's 40 at load time. The `loadItems` handler at `Table.vue:241-243` writes the component's value into the store, which suggests the component value wins.

DEFAULT: 40
FILE: src/dispatch/static/dispatch/src/case/Table.vue
STORE_DEFAULT: 25