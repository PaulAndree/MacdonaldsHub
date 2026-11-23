import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import AppRoutes from "../../app/AppRoutes";
import { areas } from "../../app/areas";
import { renderAt } from "../../app/testing";
import { handlers } from "../../example/handlers";
import { resetScenario, setScenario } from "../../example/scenario";
import { resetStore } from "../../example/state";
import { readStoredZip } from "../../example/zip";
import { es } from "../../i18n/es";

const server = setupServer(...handlers);
const t = es.incidents;
const requests: string[] = [];

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
  server.events.on("request:start", ({ request }) => {
    if (request.url.includes("/api/incidents/export")) requests.push(new URL(request.url).search);
  });
});
beforeEach(() => {
  requests.length = 0;
  resetScenario();
  setScenario({ latencyMs: 0 });
  resetStore();
});
afterEach(() => {
  server.resetHandlers();
  vi.restoreAllMocks();
});
afterAll(() => server.close());

const show = (path = "/incidencias") => renderAt(path, <AppRoutes areas={areas} />);

/** Captures what the page downloads: the file name and the sheet inside it. */
function captureDownload() {
  const saved: { name: string; blob: Blob }[] = [];
  let blob: Blob | null = null;
  URL.createObjectURL = vi.fn((value: Blob | MediaSource) => {
    blob = value as Blob;
    return "blob:export";
  });
  URL.revokeObjectURL = vi.fn();
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
    saved.push({ name: this.download, blob: blob! });
  });
  return {
    saved,
    async sheet() {
      await waitFor(() => expect(saved).toHaveLength(1));
      const bytes = await new Promise<Uint8Array>((resolve) => {
        const reader = new FileReader();
        reader.onload = () => resolve(new Uint8Array(reader.result as ArrayBuffer));
        reader.readAsArrayBuffer(saved[0]!.blob);
      });
      const files = readStoredZip(bytes);
      return files["xl/worksheets/sheet1.xml"]!;
    },
  };
}

describe("export of incidents (RF-16)", () => {
  it("downloads a spreadsheet with every incident when there is no filter", async () => {
    const download = captureDownload();
    show();
    await userEvent.click(await screen.findByRole("button", { name: t.export }));
    const sheet = await download.sheet();
    expect(download.saved[0]!.name).toBe("incidencias.xlsx");
    for (const id of ["inc-001", "inc-002", "inc-003", "inc-004", "inc-005"]) expect(sheet).toContain(`>${id}<`);
    expect(requests).toEqual([""]);
  });

  it("exports only what the active filters show, with the same filters in the request", async () => {
    const download = captureDownload();
    show("/incidencias?provider=glovo&dateKind=recovery&from=2026-11-01");
    await userEvent.click(await screen.findByRole("button", { name: t.export }));
    const sheet = await download.sheet();
    expect(requests[0]).toContain("provider=glovo");
    expect(requests[0]).toContain("dateKind=recovery");
    expect(requests[0]).toContain("from=2026-11-01");
    expect(sheet).toContain(">inc-005<");
    expect(sheet).not.toContain(">inc-001<");
    expect(sheet).not.toContain(">inc-003<");
  });

  it("keeps an absent branch, amount, description and time explicit, never as zero", async () => {
    const download = captureDownload();
    show("/incidencias?branch=none");
    await userEvent.click(await screen.findByRole("button", { name: t.export }));
    const sheet = await download.sheet();
    expect(sheet).toContain(">inc-002<");
    expect(sheet).toContain(`>${es.values.noBranch}<`);
    expect(sheet).toContain(`>${es.values.unknownAmount}<`);
    expect(sheet).toContain(`>${es.values.noDescription}<`);
    expect(sheet).toContain(`>${t.noTime}<`);
    expect(sheet).toContain(`>${t.noClaim}<`);
    expect(sheet).toContain(`>${t.noRecovery}<`);
    expect(sheet).not.toMatch(/>0(\.0+)?</);
  });

  it("keeps amounts exactly as they are in the source, with the decimal point", async () => {
    const download = captureDownload();
    show();
    await userEvent.click(await screen.findByRole("button", { name: t.export }));
    const sheet = await download.sheet();
    expect(sheet).toContain(">12.50<");
    expect(sheet).toContain(">32.00<");
    expect(sheet).not.toContain("12,50");
  });

  it("says what the export contains and that absent values are never zero", async () => {
    show();
    expect(await screen.findByText(t.exportHelp)).toBeInTheDocument();
  });

  it("reports a failed export instead of failing silently", async () => {
    captureDownload();
    show();
    const button = await screen.findByRole("button", { name: t.export });
    setScenario({ failure: "server" });
    await userEvent.click(button);
    expect(await screen.findByRole("alert")).toHaveTextContent(es.errors.generic);
  });
});
