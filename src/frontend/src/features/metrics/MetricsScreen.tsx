import { useSearchParams } from "react-router-dom";
import { es } from "../../i18n/es";
import { DateInput } from "../../ui/DateInput";
import PageHeader from "../../ui/PageHeader";
import QueryView from "../../ui/QueryView";
import { EmptyState, PendingMarker } from "../../ui/StateViews";
import { useDateFilter } from "../../ui/useDateFilter";
import { providerName } from "../../ui/values";
import { useBranchOptions } from "../incidents/queries";
import BreakdownTable from "./BreakdownTable";
import ChannelPanel from "./ChannelPanel";
import PendingClaims from "./PendingClaims";
import { DEFAULT_METRICS_FILTERS, type MetricsFilters, useMetrics } from "./queries";

const t = es.metrics;
const f = t.filters;
const PROVIDERS = ["uber eats", "just eat", "glovo"];

/** Follow-up of claims. The date criterion is always stated, and criteria not yet decided are marked as examples. */
export default function MetricsScreen() {
  const [params, setParams] = useSearchParams();
  const filters: MetricsFilters = {
    dateKind: params.get("dateKind") ?? DEFAULT_METRICS_FILTERS.dateKind,
    from: params.get("from") ?? "",
    to: params.get("to") ?? "",
    provider: params.get("provider") ?? "",
    branch: params.get("branch") ?? "",
  };
  const metrics = useMetrics(filters);
  const branches = useBranchOptions();

  function change(patch: Partial<MetricsFilters>) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(patch)) {
      if (value && !(key === "dateKind" && value === DEFAULT_METRICS_FILTERS.dateKind)) next.set(key, value);
      else next.delete(key);
    }
    setParams(next);
  }
  const fromField = useDateFilter(filters.from, (iso) => change({ from: iso }));
  const toField = useDateFilter(filters.to, (iso) => change({ to: iso }));
  const filtered = Object.entries(filters).some(([key, value]) => value !== DEFAULT_METRICS_FILTERS[key as keyof MetricsFilters]);

  return (
    <>
      <PageHeader
        title={es.titles.dashboard}
        subtitle={metrics.data ? t.subtitle(es.environments[metrics.data.environment]) : undefined}
      />

      <form className="card filters" role="search" aria-label={f.label} onSubmit={(event) => event.preventDefault()}>
        <label>
          {f.dateKind}
          <select value={filters.dateKind} onChange={(e) => change({ dateKind: e.target.value })}>
            {Object.entries(t.dateKinds).map(([value, label]) => (
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

      <QueryView query={metrics}>
        {(data) => {
          const noData = data.warnings.some((w) => w.code === "no_data");
          return (
            <>
              {data.environment !== "test" && (
                <p className="muted" role="note">
                  {t.envProduction}
                </p>
              )}
              {data.criteria.status === "example" && (
                <p className="muted">
                  {t.examples} {data.criteria.pendingDecision && <PendingMarker id={data.criteria.pendingDecision} />}
                </p>
              )}
              {data.warnings
                .filter((w) => w.code === "incomplete_amounts")
                .map((w) => (
                  <p key={w.code} className="notice notice--warning" role="note">
                    {w.message}
                  </p>
                ))}
              {noData ? <EmptyState title={t.noPeriod} /> : null}
              {data.channels.map((channel) => (
                <ChannelPanel key={channel.channel} channel={channel} criteria={data.criteria} />
              ))}
              <BreakdownTable rows={data.breakdown} />
              <PendingClaims claims={data.pendingClaims} criteria={data.criteria} />
            </>
          );
        }}
      </QueryView>
    </>
  );
}
