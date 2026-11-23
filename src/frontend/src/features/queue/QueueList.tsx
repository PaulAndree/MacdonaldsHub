import { Link } from "react-router-dom";
import { es } from "../../i18n/es";
import { formatTimestamp } from "../../ui/format";
import { providerName } from "../../ui/values";
import type { QueueEntry } from "./queries";

const t = es.queue;
const STYLE = { pending: "pill--wait", sending: "pill--review", sent: "pill--ok", error: "pill--new" } as const;

/** Why an email is in error, in words, and never an action: there is no retry, resend or cancel. */
function ErrorReason({ entry }: { entry: QueueEntry }) {
  if (entry.state !== "error") return <span aria-hidden="true">—</span>;
  return (
    <>
      {entry.reason && <div>{entry.reason}</div>}
      {entry.errorKind && <div className="muted">{t.errorKinds[entry.errorKind]}</div>}
    </>
  );
}

export default function QueueList({ items }: { items: QueueEntry[] }) {
  return (
    <div className="table-scroll">
      <table aria-label={t.list.label}>
        <thead>
          <tr>
            <th scope="col">{t.list.orderId}</th>
            <th scope="col">{t.list.provider}</th>
            <th scope="col">{t.list.state}</th>
            <th scope="col">{t.list.reason}</th>
            <th scope="col">{t.list.recipient}</th>
            <th scope="col">{t.list.started}</th>
            <th scope="col">{t.list.finished}</th>
          </tr>
        </thead>
        <tbody>
          {items.map((entry) => (
            <tr key={entry.id}>
              <th scope="row">
                <Link to={`/incidencias/${entry.incidentId}`}>{entry.orderId}</Link>
              </th>
              <td>{providerName(entry.provider)}</td>
              <td>
                <span className={`pill ${STYLE[entry.state]}`}>{t.states[entry.state]}</span>
              </td>
              <td>
                <ErrorReason entry={entry} />
              </td>
              <td>{entry.recipient.label}</td>
              <td>{entry.startedAt ? formatTimestamp(entry.startedAt) : <span className="unknown">{t.list.notStarted}</span>}</td>
              <td>{entry.finishedAt ? formatTimestamp(entry.finishedAt) : <span className="unknown">{t.list.notFinished}</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
