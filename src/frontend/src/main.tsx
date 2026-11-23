import { QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { createQueryClient } from "./api/queryClient";
import type { ExampleUi } from "./example/ui";
import AppRoutes from "./app/AppRoutes";
import { areas } from "./app/areas";
import "@fontsource/barlow/latin-400.css";
import "@fontsource/barlow/latin-500.css";
import "@fontsource/barlow/latin-600.css";
import "@fontsource/barlow-condensed/latin-500.css";
import "@fontsource/barlow-condensed/latin-600.css";
import "@fontsource/barlow-condensed/latin-700.css";
import "./ui/tokens.css";
import "./ui/base.css";

const queryClient = createQueryClient();

function render(exampleUi?: ExampleUi) {
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AppRoutes areas={areas} exampleUi={exampleUi} />
        </BrowserRouter>
      </QueryClientProvider>
    </StrictMode>,
  );
}

/**
 * In the example build the request layer starts before the first render. The condition compares a
 * build-time constant, so the standard build drops this import and everything behind it.
 */
async function start() {
  if (import.meta.env.VITE_EXAMPLE_MODE === "true") {
    const { startExampleMode } = await import("./example/start");
    render(await startExampleMode());
    return;
  }
  render();
}

void start();
