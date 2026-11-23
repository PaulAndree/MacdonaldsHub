import { Link } from "react-router-dom";
import { es } from "../../i18n/es";
import { PendingMarker } from "../../ui/StateViews";
import { providerName } from "../../ui/values";
import type { Metrics } from "./queries";

const t = es.metrics.pending;

/** Claims still waiting for a result, with how long they have waited. The age criterion is an example (P-04). */
export default function PendingClaims({ claims, criteria }: { claims: Metrics["pendingClaims"]; criteria: Metrics["criteria"] }) {
  return (
    <section className="card" aria-labelledby="pending-title">
      <h2 id="pending-title">{t.title}</h2>
      <p className="muted">
        {t.note} {criteria.pendingDecision && <PendingMarker id={criteria.pendingDecision} />}
      </p>
      {claims.length === 0 ? (
        <p>{t.empty}</p>
      ) : (
        <div className="table-scroll">
          <table>
            <caption className="visually-hidden">{t.title}</caption>
            <thead>
              <tr>
                <th scope="col">{t.columns.incident}</th>
                <th scope="col">{t.columns.provider}</th>
                <th scope="col">{t.columns.claimedOn}</th>
                <th scope="col">{t.columns.age}</th>
              </tr>
            </thead>
            <tbody>
              {claims.map((claim) => (
                <tr key={claim.incidentId}>
                  <td className="nowrap">
                    <Link to={`/incidencias/${claim.incidentId}`}>{claim.incidentId}</Link>
                  </td>
                  <td>{providerName(claim.provider)}</td>
                  <td>{claim.claimDate}</td>
                  <td>{t.age(claim.ageDays)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
