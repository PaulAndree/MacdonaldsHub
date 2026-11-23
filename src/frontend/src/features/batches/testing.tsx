import { QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { createQueryClient } from "../../api/queryClient";
import BatchScreen from "./BatchScreen";
import ImportScreen from "./ImportScreen";

export const XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
export const xlsx = (name = "incidencias.xlsx") => new File(["x"], name, { type: XLSX });

function Where() {
  return <p data-testid="where">{useLocation().pathname}</p>;
}

/** The import and batch screens as the router mounts them, with the current address visible. */
export function renderBatches(path = "/importar", extra?: ReactElement) {
  const client = createQueryClient({ retryDelay: 0 });
  const view = render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/importar" element={<ImportScreen />} />
          <Route path="/lotes/:batchId" element={<BatchScreen />} />
          <Route path="*" element={<p>otra pantalla</p>} />
        </Routes>
        {extra}
        <Where />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { client, ...view };
}
