# Instructions for implementing agents

1. Read `openspec/config.yaml`, then the docs/ source of the active change before writing anything.
2. Empty files and `.gitkeep` placeholders are NOT implemented functionality.
3. Backend layering: `domain/` pure business rules (no I/O, TDD) -> `services/` use cases -> `adapters/` storage, identity, mail, db; `api/` and `worker/` are entrypoints sharing that code.
4. Configuration selects adapters, never business rules.
5. Never commit or print secrets; `.env` is local only. Use `.env.example` for variable names.
6. Pending decisions P-01..P-12 stay explicit; do not invent defaults.
