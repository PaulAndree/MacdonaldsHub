import { setupWorker } from "msw/browser";
import { handlers } from "./handlers";
import { type ExampleUi, exampleUi } from "./ui";

/** Starts the in-browser mock layer. Only the example build ever loads this module. */
export async function startExampleMode(): Promise<ExampleUi> {
  const worker = setupWorker(...handlers);
  await worker.start({
    onUnhandledRequest: "bypass",
    quiet: true,
    serviceWorker: { url: "/mockServiceWorker.js" },
  });
  return exampleUi;
}
