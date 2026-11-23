# API contract

`openapi.yaml` is the versioned contract between the frontend and the backend (ADR-16). Change 1
(`frontend`) uses it with example data. Change 2 (`backend`) implements it. The administrator's
approval names the exact contract version.

## Rules every operation follows

- **Amounts** are decimal strings (`"0.1234"`), never JSON numbers. An absent amount is `null`, never `"0"`.
- **Incident date** is `YYYY-MM-DD` with an optional `HH:MM` time in Europe/Madrid. No time means `null`;
  `00:00` is never invented.
- **System timestamps** are UTC instants.
- **Providers and branches** are lowercase.
- **Errors** use the `Error` schema. 401 is no valid session, 403 is authenticated but not authorized.
- Pending decisions (P-01, P-03, P-04, P-07, P-11, P-12) appear as explicit fields such as
  `pendingDecision`, never as invented values.

## Changing the contract

Run these from `src/frontend`:

```bash
npm run contract:lint       # structure and style of openapi.yaml
npm test                    # every named example is validated against its schema, strictly
npm run contract:generate   # rewrites src/api/schema.d.ts and src/example/contract.json
npm run contract:check      # fails if those generated files are out of date
npm run approval:check      # fails if the contract differs from the approved one
```

1. Edit `openapi.yaml`. Give every response a named example for each state it can show (success,
   empty, error, denied).
2. Bump `info.version` (below).
3. Run the commands above, then commit the contract and the two generated files together.

The two generated files are committed on purpose. The frontend image is built from `src/frontend`
and cannot see `docs/`, and the example mode reads the JSON copy.

## Versions

`info.version` follows semantic versioning:

| Change | Bump |
|---|---|
| Wording, examples or descriptions only | patch |
| A new operation or an optional field | minor |
| A removed or renamed operation or field, or a stricter type | major |

## When a new approval is needed

The administrator approves a design version together with a contract version. The approval record,
`docs/approvals/change_01_frontend.md`, holds a line such as:

```
<!-- approval: contractVersion=0.1.0 contractSha256=<64 hex characters> -->
```

`npm run approval:hash` prints the values for the current contract. Once that line exists, CI runs
`npm run approval:check` and **fails on any difference**, including a wording-only change. It then
asks for a new administrator approval: review the change, record the new values in the same file and
note who approved and when. Before any approval is recorded, the check passes with a notice.
