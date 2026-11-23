# Sample XLSX files

Test files for the import flow. They follow the input contract of `docs/change_02_backend.md` (section 3): one sheet, eight recognized headers, Order ID as text, amounts as numeric cells, incident date as text `YYYY-MM-DD` or `YYYY-MM-DD HH:MM`. They contain no real data.

**Example mode (change 1):** the example build does **not** read the file. It picks the scenario from the **file name**, so keep the names. The contents matter for the real parser (change 2).

| File | What it is | Example-mode result | Expected with the real parser |
|---|---|---|---|
| `incidencias.xlsx` | Mixed: 8 valid rows, 6 rows with a row error, 2 repeated keys in the file | Large preview with the four classes | Rows 1-8 new (UE-100002 has no time; JE-55002 has no branch or amount; negative and zero amounts kept; `1A2b-3C` alphanumeric ID); 6 errors (unknown provider, numeric Order ID, bad date, text amount, unknown branch, missing Order ID); the two `UE-100010` rows are identical and the two `JE-55010` rows differ, so all four are excluded as repeated |
| `incidencias-sucursales-reales.xlsx` | The same mixed file as `incidencias.xlsx`, with the real branches (Palacio de hielo, Hortaleza, Plenilunio) | Large preview | Same classes as `incidencias.xlsx` when the catalog is the real one (`BRANCH_CATALOG` of the administrator); with the sample catalog its branches are unknown and every row is an error |
| `incidencias-validas.xlsx` | Only the 8 valid rows | Large preview | 8 new |
| `solo-obligatorios.xlsx` | Only Proveedor, Order ID and Fecha y hora | Required-only preview | 8 new, optional values absent (not zero) |
| `identica.xlsx` | Same content as `incidencias-validas.xlsx` | "Identical file" notice (upload it after confirming the other) | Same fingerprint: notice, then all duplicates |
| `sin-order-id.xlsx` | Missing the mandatory Order ID header | Whole file rejected | Whole file rejected |
| `dos-hojas.xlsx` | Two worksheets | Whole file rejected | Whole file rejected |
| `danado.xlsx` | Not a valid XLSX (corrupt) | Unreadable-file rejection (name contains `danado`) | Whole file rejected as unreadable |

Branch names in the other files use the sample catalog (`centro`, `norte`, `sur`), which is what a clean local stack and the tests load. With the real catalog loaded, use `incidencias-sucursales-reales.xlsx`. Providers: `uber eats`, `just eat`, `glovo`. Provider and branch are lowercased on read, so `Uber Eats` and `Norte` are valid.
