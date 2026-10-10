The Cases table shows 40 cases per page when it first opens.

- **Where it's set:** `Table.vue` declares `const itemsPerPage = ref(40)` and binds it with `:items-per-page="itemsPerPage"`. The page-size dropdown offers 10, 20, 40 and 80.
- **Store default:** the Vuex cases module declares `table.options.itemsPerPage: 25` in `case/store.js`. The table doesn't use that value for its initial page size, because the component's local 40 is what gets bound.

Paths are relative to `src/dispatch/static/dispatch/`.

DEFAULT: 40
FILE: src/case/Table.vue
STORE_DEFAULT: 25