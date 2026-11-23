import { useState } from "react";
import { downloadFile } from "../../api/download";
import { es } from "../../i18n/es";
import { ErrorState, LoadingState } from "../../ui/StateViews";
import { useAction } from "../../ui/useAction";
import { useBatchRows } from "./queries";
import ConfirmationPanel from "./ConfirmationPanel";
import RowsTable from "./RowsTable";
import type { Batch, RowClass } from "./types";

type Filter = RowClass | "all";
const FILTERS: Filter[] = ["all", "new", "duplicate", "conflict", "error"];
const PAGE_SIZE = 50;

/**
 * Review of a prepared batch: the counts per class, and every row with its class and reason.
 * Totals are always visible and nothing is truncated: the rows are paged and the page says how many
 * there are. The classification is the backend's; nothing here recomputes it.
 */
export default function ReviewPanel({ batch }: { batch: Batch }) {
  const [filter, setFilter] = useState<Filter>("all");
  const [page, setPage] = useState(1);
  const rows = useBatchRows(batch.id, filter, page, true);
  const report = useAction(() => downloadFile(`/api/batches/${batch.id}/excluded-report`, "informe-filas-excluidas.xlsx"));
  const totals = batch.summary?.totals;
  if (!totals || !batch.summary) return null;

  const total = totals.new + totals.duplicate + totals.conflict + totals.error;
  const excluded = totals.duplicate + totals.conflict + totals.error;
  const counts: Record<Filter, number> = { all: total, ...totals };
  const matching = rows.data?.total ?? counts[filter];
  const pages = Math.max(1, Math.ceil(matching / PAGE_SIZE));
  const from = matching === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const to = Math.min(page * PAGE_SIZE, matching);

  function choose(next: Filter) {
    setFilter(next);
    setPage(1);
  }

  return (
    <>
      <div className="card">
        <h2>{es.review.temporaryTitle}</h2>
        <p>{es.review.temporaryText}</p>
        <p>
          <strong>{es.review.willImport(batch.summary.incidentsToCreate)}</strong> {es.review.willExclude(excluded)}
        </p>
        {excluded > 0 && (
          <p>
            <button type="button" className="secondary" disabled={report.pending} onClick={() => report.run(undefined)}>
              {report.pending ? es.review.report.downloading : es.review.report.button}
            </button>{" "}
            <span className="muted">{es.review.report.help}</span>
          </p>
        )}
        {report.error != null && <ErrorState mutation error={report.error} />}
        <p>
          <a href="#confirmacion">{es.confirm.anchor}</a>
        </p>
        <div role="group" aria-label={es.review.filterLabel} className="class-filter">
          {FILTERS.map((item) => (
            <button
              key={item}
              type="button"
              className={item === filter ? undefined : "secondary"}
              aria-pressed={item === filter}
              onClick={() => choose(item)}
            >
              {es.review.classes[item]} <span className="class-filter__count">{counts[item]}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="card">
        {rows.isPending && <LoadingState />}
        {rows.isError && <ErrorState error={rows.error} onRetry={() => void rows.refetch()} />}
        {rows.data && (
          <>
            {rows.data.items.length === 0 ? <p>{es.review.noRows}</p> : <RowsTable rows={rows.data.items} />}
            <nav aria-label={es.review.tableCaption} className="pager">
              <p role="status">
                {es.review.showing(from, to, matching)} · {es.review.pageOf(page, pages)}
              </p>
              <button type="button" className="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                {es.review.previous}
              </button>{" "}
              <button type="button" className="secondary" disabled={page >= pages} onClick={() => setPage(page + 1)}>
                {es.review.next}
              </button>
            </nav>
          </>
        )}
      </div>

      <ConfirmationPanel batch={batch} />
    </>
  );
}
