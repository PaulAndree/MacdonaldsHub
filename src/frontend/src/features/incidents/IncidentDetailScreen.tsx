import { Link, useParams } from "react-router-dom";
import { es } from "../../i18n/es";
import PageHeader from "../../ui/PageHeader";
import QueryView from "../../ui/QueryView";
import { AmountText, BranchText, IncidentDateText, OptionalText, Unknown, providerName } from "../../ui/values";
import EmailStateNotice from "./EmailStateNotice";
import HistoryTable from "./HistoryTable";
import IncidentActions from "./IncidentActions";
import { useIncident } from "./queries";
import StatusPill from "./StatusPill";
import type { Incident } from "./types";

const t = es.incidents;

function Facts({ incident }: { incident: Incident }) {
  return (
    <dl className="facts">
      <dt>{t.fields.provider}</dt>
      <dd>{providerName(incident.provider)}</dd>
      <dt>{t.fields.orderId}</dt>
      <dd>{incident.orderId}</dd>
      <dt>{t.fields.branch}</dt>
      <dd>
        <BranchText branch={incident.branch} />
      </dd>
      <dt>{t.fields.claimAmount}</dt>
      <dd>
        <AmountText value={incident.claimAmount} />
      </dd>
      <dt>{t.fields.providerCosts}</dt>
      <dd>
        <AmountText value={incident.providerCosts} />
      </dd>
      <dt>{t.fields.total}</dt>
      <dd>
        <AmountText value={incident.total} />
      </dd>
      <dt>{t.fields.description}</dt>
      <dd>
        <OptionalText value={incident.description} empty={es.values.noDescription} />
      </dd>
      <dt>{t.fields.channel}</dt>
      <dd>{t.channel[incident.channel]}</dd>
      <dt>{t.fields.batch}</dt>
      <dd>{incident.batchId ? <Link to={`/lotes/${incident.batchId}`}>{incident.batchId}</Link> : t.fields.manualEntry}</dd>
    </dl>
  );
}

/** The three dates are different things and are never merged: the incident, its claim and its recovery. */
function Dates({ incident }: { incident: Incident }) {
  return (
    <dl className="facts">
      <dt>{t.dates.incident}</dt>
      <dd>
        <IncidentDateText date={incident.incidentDate} time={incident.incidentTime} />
      </dd>
      <dt>{t.dates.claim}</dt>
      <dd>{incident.claimDate ?? <Unknown>{t.noClaim}</Unknown>}</dd>
      <dt>{t.dates.recovery}</dt>
      <dd>{incident.recoveryDate ?? <Unknown>{t.noRecovery}</Unknown>}</dd>
    </dl>
  );
}

function Outcome({ incident }: { incident: Incident }) {
  return (
    <>
      <dl className="facts">
        <dt>{t.result.status}</dt>
        <dd>
          <StatusPill status={incident.status} />
        </dd>
        <dt>{t.result.kind}</dt>
        <dd>{incident.result ? t.result.kinds[incident.result] : <Unknown>{t.result.none}</Unknown>}</dd>
        <dt>{t.result.claimed}</dt>
        <dd>
          <AmountText value={incident.claimAmount} />
        </dd>
        <dt>{t.result.recovered}</dt>
        <dd>
          <AmountText value={incident.recoveredAmount} unknown={t.noRecovery} />
        </dd>
      </dl>
      {incident.result && <p className="muted">{t.result.notePartial}</p>}
    </>
  );
}

export default function IncidentDetailScreen() {
  const { incidentId = "" } = useParams();
  const detail = useIncident(incidentId);
  return (
    <>
      <PageHeader
        title={detail.data ? t.detailTitle(detail.data.incident.orderId) : es.titles.incident}
        subtitle={detail.data ? `${providerName(detail.data.incident.provider)} · ${detail.data.incident.id}` : undefined}
        actions={
          <Link className="button-link secondary" to="/incidencias">
            {t.back}
          </Link>
        }
      />
      <QueryView query={detail}>
        {({ incident, history }) => (
          <>
            <section className="card" aria-labelledby="sec-data">
              <h2 id="sec-data">{t.sections.data}</h2>
              <Facts incident={incident} />
            </section>
            <section className="card" aria-labelledby="sec-dates">
              <h2 id="sec-dates">{t.sections.dates}</h2>
              <Dates incident={incident} />
            </section>
            <section className="card" aria-labelledby="sec-result">
              <h2 id="sec-result">{t.sections.result}</h2>
              <Outcome incident={incident} />
              <EmailStateNotice incident={incident} history={history} />
            </section>
            <IncidentActions incident={incident} />
            <section className="card" aria-labelledby="sec-history">
              <h2 id="sec-history">{t.sections.history}</h2>
              <HistoryTable history={history} />
            </section>
          </>
        )}
      </QueryView>
    </>
  );
}
