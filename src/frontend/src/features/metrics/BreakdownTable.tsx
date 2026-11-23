import { es } from "../../i18n/es";
import { AmountText, BranchText, providerName } from "../../ui/values";
import type { Metrics } from "./queries";

const t = es.metrics.breakdown;

export default function BreakdownTable({ rows }: { rows: Metrics["breakdown"] }) {
  if (rows.length === 0) return null;
  return (
    <section className="card" aria-labelledby="breakdown-title">
      <h2 id="breakdown-title">{t.title}</h2>
      <div className="table-scroll">
        <table>
          <caption className="visually-hidden">{t.title}</caption>
          <thead>
            <tr>
              <th scope="col">{t.columns.provider}</th>
              <th scope="col">{t.columns.branch}</th>
              <th scope="col">{t.columns.claimed}</th>
              <th scope="col">{t.columns.claimedAmount}</th>
              <th scope="col">{t.columns.recovered}</th>
              <th scope="col">{t.columns.recoveredAmount}</th>
              <th scope="col">{t.columns.incomplete}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={`${row.provider}|${row.branch}`}>
                <td>{providerName(row.provider)}</td>
                <td>
                  <BranchText branch={row.branch} />
                </td>
                <td>{row.claimedCount}</td>
                <td>
                  <AmountText value={row.claimedAmount} unknown={es.metrics.noData} />
                </td>
                <td>{row.recoveredCount}</td>
                <td>
                  <AmountText value={row.recoveredAmount} unknown={es.metrics.noRecovery} />
                </td>
                <td>{row.incompleteCount > 0 ? <span className="pill pill--review">{row.incompleteCount}</span> : 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
