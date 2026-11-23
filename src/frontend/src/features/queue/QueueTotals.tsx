import { es } from "../../i18n/es";
import Kpi from "../../ui/Kpi";
import type { EmailTotals } from "./queries";

const t = es.queue;
const ORDER = ["pending", "sending", "sent", "error"] as const;

/** The four states and their counts. Zero is a real count here, so it is shown as 0. */
export default function QueueTotals({ totals }: { totals: EmailTotals }) {
  return (
    <section aria-label={t.totalsLabel} className="kpis">
      {ORDER.map((state) => (
        <Kpi key={state} label={t.states[state]} value={totals[state]} accent={state === "error" && totals.error > 0} />
      ))}
    </section>
  );
}
