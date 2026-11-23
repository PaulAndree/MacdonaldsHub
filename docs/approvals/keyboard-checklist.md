# Keyboard checklist (RNF-08)

Manual check that the import review flow can be completed with the keyboard only. Automated checks (`src/frontend/src/app/Accessibility.test.tsx`, `npm run check:contrast`) do not replace it: they cannot see focus order or whether focus is visible.

**How to run it:** `cd src/frontend && npm run dev:example`, open the address shown, and put the mouse aside. Use only `Tab`, `Shift+Tab`, `Enter`, `Space`, arrow keys and `Esc`. In the footer scenario panel, keep the role as administrator and the latency low.

- **Tester:** franchise administrator role (project owner)
- **Date:** 2026-11-23
- **Browser and version:** not recorded
- **Build / commit:** example build served by `npm run dev:example`

Mark each row `[x]` when it holds, or write the problem under "Findings".

## Import review flow

- [x] 1. The first `Tab` on any screen reaches "Saltar al contenido", it is visible when focused, and `Enter` moves focus to the main content.
- [x] 2. The main navigation links are reached in a logical order (Importar, Incidencias, Alta manual, Panel, Correo) and the current area is announced or marked.
- [x] 3. In Importar, the file field is reachable and a file can be chosen without the mouse.
- [x] 4. Upload progress and processing are announced or visible without moving focus away unexpectedly.
- [x] 5. In the review, the class filters, the table and the pager are reachable, in reading order, with no focus trap.
- [x] 6. A row with a reason or a compared version can be expanded and collapsed with `Enter` or `Space`.
- [x] 7. The excluded-rows report can be downloaded from the keyboard.
- [x] 8. The confirmation summary is reachable and "Confirmar" is operated with `Enter` or `Space`; a second press while it works does nothing.
- [x] 9. "Cancelar lote" asks for confirmation, `Esc` or the cancel option closes it, and focus returns to the control that opened it.
- [x] 10. After confirming or cancelling, focus lands somewhere meaningful (the result or the heading), not on the page start.
- [x] 11. Every focused element shows a visible focus indicator with enough contrast against its background.
- [x] 12. No element needs the mouse (hover-only information, drag, or click-only controls).

## Other areas (smoke check)

- [x] 13. Incidencias: filters, date fields (`dd/mm/aaaa`), table and detail link work by keyboard.
- [x] 14. Alta manual: the form can be completed, errors are reachable and the review step precedes saving.
- [x] 15. Panel: filters work and every figure is readable in order.
- [x] 16. Correo: pause and resume work by keyboard and the paused state is announced.

## Findings

None. The tester reported every row as passing ("todo OK").
