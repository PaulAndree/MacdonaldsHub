import { useSearchParams } from "react-router-dom";
import { Link } from "react-router-dom";
import { downloadFile } from "../../api/download";
import { es } from "../../i18n/es";
import { DateInput } from "../../ui/DateInput";
import { ErrorState } from "../../ui/StateViews";
import { useDateFilter } from "../../ui/useDateFilter";
import { useAction } from "../../ui/useAction";
import PageHeader from "../../ui/PageHeader";
import Pager from "../../ui/Pager";
import QueryView from "../../ui/QueryView";
import { AmountText, BranchText, IncidentDateText, providerName } from "../../ui/values";
import { usePermission } from "../session/usePermission";
import { exportPath, useBranchOptions, useIncidents } from "./queries";
import StatusPill from "./StatusPill";
import { EMPTY_FILTERS, type IncidentFilters } from "./types";
import { Unknown } from "../../ui/values";

const t = es.incidents;
const f = t.filters;
const PROVIDERS = ["uber eats", "just eat", "glovo"];
const STATUSES = Object.keys(t.status);

/** The confirmed incidents, with the filters kept in the address so a view can be shared and reopened. */
export default function IncidentsScreen() {
  const [params, setParams] = useSearchParams();
  const filters: IncidentFilters = {
    provider: params.get("provider") ?? EMPTY_FILTERS.provider,
    branch: params.get("branch") ?? EMPTY_FILTERS.branch,
    status: params.get("status") ?? EMPTY_FILTERS.status,
    dateKind: params.get("dateKind") ?? EMPTY_FILTERS.dateKind,
    from: params.get("from") ?? EMPTY_FILTERS.from,
    to: params.get("to") ?? EMPTY_FILTERS.to,
  };
  const page = Math.max(1, Number(params.get("page") ?? 1));
  const canWrite = usePermission("incidents_write");
  const list = useIncidents(filters, page);
  const branches = useBranchOptions();
  const exportFile = useAction(() => downloadFile(exportPath(filters), "incidencias.xlsx"));

  function change(patch: Partial<IncidentFilters>) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(patch)) {
      if (value && !(key === "dateKind" && value === "incident")) next.set(key, value);
      else next.delete(key);
    }
    next.delete("page");
    setParams(next);
  }

  const fromField = useDateFilter(filters.from, (iso) => change({ from: iso }));
  const toField = useDateFilter(filters.to, (iso) => change({ to: iso }));

  const filtered = Object.entries(filters).some(([key, value]) => value !== EMPTY_FILTERS[key as keyof IncidentFilters]);

  return (
    <>
      <PageHeader
        title={es.titles.incidents}
        subtitle={t.subtitle}
        actions={
          <>
            <button type="button" className="secondary" disabled={exportFile.pending} onClick={() => exportFile.run(undefined)}>
              {exportFile.pending ? t.exporting : t.export}
            </button>
            {canWrite && (
              <Link className="button-link" to="/incidencias/nueva">
                {t.newEntry}
              </Link>
            )}
          </>
        }
      />
      {exportFile.error != null && <ErrorState mutation error={exportFile.error} />}

      <form className="card filters" role="search" aria-label={f.label} onSubmit={(event) => event.preventDefault()}>
        <label>
          {f.provider}
          <select value={filters.provider} onChange={(e) => change({ provider: e.target.value })}>
            <option value="">{f.all}</option>
            {PROVIDERS.map((p) => (
              <option key={p} value={p}>
                {providerName(p)}
              </option>
            ))}
          </select>
        </label>
        <label>
          {f.branch}
          <select value={filters.branch} onChange={(e) => change({ branch: e.target.value })}>
            <option value="">{f.allBranches}</option>
            <option value="none">{f.noBranch}</option>
            {branches.data?.items.map((b) => (
              <option key={b.id} value={b.name}>
                {b.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          {f.status}
          <select value={filters.status} onChange={(e) => change({ status: e.target.value })}>
            <option value="">{f.all}</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {t.status[s as keyof typeof t.status]}
              </option>
            ))}
          </select>
        </label>
        <label>
          {f.dateKind}
          <select value={filters.dateKind} onChange={(e) => change({ dateKind: e.target.value })}>
            {Object.entries(f.dateKinds).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          {f.from}
          <DateInput value={fromField.text} aria-invalid={fromField.invalid} onChange={(e) => fromField.change(e.target.value)} />
        </label>
        <label>
          {f.to}
          <DateInput value={toField.text} aria-invalid={toField.invalid} onChange={(e) => toField.change(e.target.value)} />
        </label>
        {(fromField.invalid || toField.invalid) && (
          <p role="alert" className="field-error filters__error">
            {es.dates.invalid}
          </p>
        )}
        {filtered && (
          <div className="filters__clear">
            <button type="button" className="secondary" onClick={() => setParams(new URLSearchParams())}>
              {f.clear}
            </button>
          </div>
        )}
      </form>

      <QueryView query={list} isEmpty={(data) => data.total === 0} emptyTitle={t.empty}>
        {(data) => (
          <div className="card">
            <p role="status" className="muted">
              {t.count(data.total)}
            </p>
            <div className="table-scroll">
              <table>
                <caption className="visually-hidden">{t.tableCaption}</caption>
                <thead>
                  <tr>
                    <th scope="col">{t.columns.id}</th>
                    <th scope="col">{t.columns.provider}</th>
                    <th scope="col">{t.columns.orderId}</th>
                    <th scope="col">{t.columns.incidentDate}</th>
                    <th scope="col">{t.columns.branch}</th>
                    <th scope="col">{t.columns.claim}</th>
                    <th scope="col">{t.columns.status}</th>
                    <th scope="col">{t.columns.claimDate}</th>
                    <th scope="col">{t.columns.recovered}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((incident) => (
                    <tr key={incident.id}>
                      <td className="nowrap">
                        <Link to={`/incidencias/${incident.id}`}>{incident.id}</Link>
                      </td>
                      <td>{providerName(incident.provider)}</td>
                      <td className="nowrap">{incident.orderId}</td>
                      <td>
                        <IncidentDateText date={incident.incidentDate} time={incident.incidentTime} />
                      </td>
                      <td>
                        <BranchText branch={incident.branch} />
                      </td>
                      <td>
                        <AmountText value={incident.claimAmount} />
                      </td>
                      <td>
                        <StatusPill status={incident.status} />
                      </td>
                      <td>{incident.claimDate ?? <Unknown>{t.noClaim}</Unknown>}</td>
                      <td>
                        <AmountText value={incident.recoveredAmount} unknown={t.noRecovery} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager
              page={page}
              total={data.total}
              pageSize={data.pageSize}
              label={t.tableCaption}
              onPage={(next) => {
                const nextParams = new URLSearchParams(params);
                if (next > 1) nextParams.set("page", String(next));
                else nextParams.delete("page");
                setParams(nextParams);
              }}
            />
          </div>
        )}
      </QueryView>
    </>
  );
}
