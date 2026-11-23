import { QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import { createQueryClient } from "../api/queryClient";

export const sessionOf = (environment: "test" | "production", role: "administrator" | "global_manager" = "administrator") => ({
  identifier: "user-1",
  email: "usuario@example.test",
  role,
  environment,
  permissions:
    role === "administrator"
      ? ["import", "confirm", "incidents_read", "incidents_write", "metrics_read", "queue_control"]
      : ["incidents_read", "metrics_read"],
});

/** Answers GET /api/session with the given body (or status) and everything else with 404. */
export function stubSession(session: unknown, status = 200) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) =>
      String(input).endsWith("/api/session")
        ? new Response(JSON.stringify(session), { status, headers: { "content-type": "application/json" } })
        : new Response(JSON.stringify({ code: "not_found", message: "x" }), { status: 404 }),
    ),
  );
}

/** Renders an element inside a router at `path` with a fresh query client. */
export function renderAt(path: string, ui: ReactElement) {
  return render(
    <QueryClientProvider client={createQueryClient({ retryDelay: 0 })}>
      <MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}
