import { es } from "../../i18n/es";
import type { QueueView } from "./queries";

const t = es.queue.batches;

/**
 * Progress per batch. A completed batch can contain errors, so it always shows both its Sent and its Error
 * counts: completed never reads as "all sent".
 */
export default function BatchProgress({ batches }: { batches: QueueView["batches"] }) {
  if (batches.length === 0) return null;
  return (
    <section className="card" aria-labelledby="queue-batches">
      <h2 id="queue-batches">{t.title}</h2>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">{t.batch}</th>
              <th scope="col">{t.state}</th>
              {(["pending", "sending", "sent", "error"] as const).map((state) => (
                <th key={state} scope="col">
                  {es.queue.states[state]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {batches.map((batch) => (
              <tr key={batch.batchId}>
                <th scope="row">{batch.batchId}</th>
                <td>
                  <span className={batch.completed ? (batch.totals.error > 0 ? "pill pill--review" : "pill pill--ok") : "pill pill--wait"}>
                    {batch.completed ? t.completed : t.inProgress}
                  </span>
                  {batch.completed && batch.totals.error > 0 && <div>{t.withErrors(batch.totals.error)}</div>}
                </td>
                <td>{batch.totals.pending}</td>
                <td>{batch.totals.sending}</td>
                <td>{batch.totals.sent}</td>
                <td>{batch.totals.error}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted">{t.completedNote}</p>
    </section>
  );
}
