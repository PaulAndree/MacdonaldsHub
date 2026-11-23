import { es } from "../../i18n/es";
import { formatTimestamp } from "../../ui/format";
import { Unknown, formatAmount } from "../../ui/values";
import type { HistoryEntry } from "./types";

const h = es.incidents.history;

function shown(entry: HistoryEntry, value: string | null) {
  if (value === null) return <Unknown>{h.nothing}</Unknown>;
  switch (entry.field) {
    case "status":
      return es.incidents.status[value as keyof typeof es.incidents.status] ?? value;
    case "result":
      return es.incidents.result.kinds[value as keyof typeof es.incidents.result.kinds] ?? value;
    case "recoveredAmount":
      return formatAmount(value);
    default:
      return value;
  }
}

/** Append-only record of what changed, who changed it, when (Madrid time) and why. */
export default function HistoryTable({ history }: { history: HistoryEntry[] }) {
  if (history.length === 0) return <p>{h.empty}</p>;
  return (
    <div className="table-scroll">
      <table>
        <caption className="visually-hidden">{es.incidents.sections.history}</caption>
        <thead>
          <tr>
            <th scope="col">{h.date}</th>
            <th scope="col">{h.actor}</th>
            <th scope="col">{h.what}</th>
            <th scope="col">{h.change}</th>
            <th scope="col">{h.reason}</th>
          </tr>
        </thead>
        <tbody>
          {history.map((entry, index) => (
            <tr key={index} className={entry.kind === "correction" ? "correction" : undefined}>
              <td className="nowrap">{formatTimestamp(entry.at)}</td>
              <td>{entry.actor === "system" ? h.system : entry.actor}</td>
              <td>
                {h.kinds[entry.kind]}: {h.fields[entry.field]}
              </td>
              <td>
                {shown(entry, entry.previousValue)} → {shown(entry, entry.newValue)}
              </td>
              <td>{entry.reason ?? ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
