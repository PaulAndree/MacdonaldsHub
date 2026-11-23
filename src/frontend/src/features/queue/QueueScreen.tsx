import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { es } from "../../i18n/es";
import PageHeader from "../../ui/PageHeader";
import Pager from "../../ui/Pager";
import QueryView from "../../ui/QueryView";
import { EmptyState } from "../../ui/StateViews";
import { formatTimestamp } from "../../ui/format";
import BatchProgress from "./BatchProgress";
import QueueControl from "./QueueControl";
import QueueList from "./QueueList";
import QueueTotals from "./QueueTotals";
import { useQueue } from "./queries";

const t = es.queue;
const STATES = ["pending", "sending", "sent", "error"] as const;

/**
 * The email queue: states and totals, progress per batch, and the global pause. It offers no retry,
 * resend or cancel (UI-07): a failed email is explained, never offered again.
 */
export default function QueueScreen() {
  const [params, setParams] = useSearchParams();
  const [page, setPage] = useState(1);
  const filters = { state: params.get("state") ?? "", batchId: params.get("batchId") ?? "" };
  const queue = useQueue(filters, page);

  function change(key: "state" | "batchId", value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next);
    setPage(1);
  }

  return (
    <>
      <PageHeader title={es.titles.queue} />
      <QueryView query={queue}>
        {(view) => {
          const empty = view.batches.length === 0 && view.status.inFlight === 0 && Object.values(view.totals).every((n) => n === 0);
          return (
            <>
              <QueueControl status={view.status} />
              {view.nextEligibleAt && !view.status.paused && <p className="muted">{t.nextEligible(formatTimestamp(view.nextEligibleAt))}</p>}
              {empty ? (
                <EmptyState title={t.emptyQueue.title} hint={t.emptyQueue.text} />
              ) : (
                <>
                  <QueueTotals totals={view.totals} />
                  <BatchProgress batches={view.batches} />
                  <section className="card" aria-labelledby="queue-items">
                    <h2 id="queue-items">{t.list.title}</h2>
                    <form className="filters" role="search" aria-label={t.list.label} onSubmit={(e) => e.preventDefault()}>
                      <label>
                        {t.list.filterState}
                        <select value={filters.state} onChange={(e) => change("state", e.target.value)}>
                          <option value="">{t.list.all}</option>
                          {STATES.map((s) => (
                            <option key={s} value={s}>
                              {t.states[s]}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        {t.list.filterBatch}
                        <select value={filters.batchId} onChange={(e) => change("batchId", e.target.value)}>
                          <option value="">{t.list.all}</option>
                          {view.batches.map((b) => (
                            <option key={b.batchId} value={b.batchId}>
                              {b.batchId}
                            </option>
                          ))}
                        </select>
                      </label>
                    </form>
                    {view.items.length === 0 ? (
                      <EmptyState title={t.list.empty} />
                    ) : (
                      <>
                        <QueueList items={view.items} />
                        <p className="muted">{t.noActions}</p>
                        <Pager page={view.page} total={view.total} pageSize={view.pageSize} onPage={setPage} label={t.list.pager} />
                      </>
                    )}
                  </section>
                </>
              )}
            </>
          );
        }}
      </QueryView>
    </>
  );
}
