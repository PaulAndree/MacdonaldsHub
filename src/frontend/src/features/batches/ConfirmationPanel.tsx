import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../api/client";
import { es } from "../../i18n/es";
import { ErrorState, LoadingState, PendingMarker } from "../../ui/StateViews";
import { useAction } from "../../ui/useAction";
import { batchKeys, useConfirmationSummary } from "./queries";
import type { Batch, ConfirmationResult } from "./types";

const t = es.confirm;

/**
 * The single confirm action. It states what will happen, that there is no undo, and keeps the control
 * from being used twice. After a failure with no answer it never claims to know whether the
 * confirmation happened: it offers to check the batch.
 */
export default function ConfirmationPanel({ batch }: { batch: Batch }) {
  const queryClient = useQueryClient();
  const summary = useConfirmationSummary(batch.id, true);
  const [stillInReview, setStillInReview] = useState(false);
  const [checking, setChecking] = useState(false);

  const confirm = useAction(async () => {
    const reviewedVersion = summary.data?.reviewedVersion ?? batch.reviewedVersion;
    const result = await api.post<ConfirmationResult>(`/api/batches/${batch.id}/confirm`, { reviewedVersion });
    queryClient.setQueryData(batchKeys.result(batch.id), result);
    await queryClient.invalidateQueries({ queryKey: batchKeys.batch(batch.id) });
    await queryClient.invalidateQueries({ queryKey: batchKeys.pending });
    return result;
  });

  /** Asks the server for the batch. Confirmation is idempotent, so a confirmed batch yields its stored result. */
  async function checkStatus() {
    setChecking(true);
    setStillInReview(false);
    try {
      const current = await queryClient.fetchQuery({
        queryKey: batchKeys.batch(batch.id),
        queryFn: () => api.get<Batch>(`/api/batches/${batch.id}`),
        staleTime: 0,
      });
      if (current.state === "confirmed" || current.state === "completed") confirm.run(undefined);
      else if (current.state === "in_review") setStillInReview(true);
      else await queryClient.invalidateQueries({ queryKey: batchKeys.batch(batch.id) });
    } finally {
      setChecking(false);
    }
  }

  if (summary.isPending) return <LoadingState />;
  if (summary.isError) return <ErrorState error={summary.error} onRetry={() => void summary.refetch()} />;
  const data = summary.data;
  const nothing = data.incidentsToCreate === 0;

  return (
    <section id="confirmacion" className="card" aria-labelledby="confirm-title">
      <h2 id="confirm-title">{t.title}</h2>
      <dl className="facts">
        <dt>{t.incidents}</dt>
        <dd>{data.incidentsToCreate}</dd>
        <dt>{t.emails}</dt>
        <dd>{data.emailsToGenerate}</dd>
        <dt>{t.withoutEmail}</dt>
        <dd>{data.withoutEmail}</dd>
        <dt>{t.excluded}</dt>
        <dd>{data.excluded}</dd>
        <dt>{t.recipient}</dt>
        <dd>{data.recipient.label}</dd>
      </dl>

      <h3>{t.template}</h3>
      <blockquote className="template">
        <p>
          <strong>{data.template.subject}</strong>
        </p>
        <p>{data.template.body}</p>
      </blockquote>
      {!data.template.isFinal && (
        <p>
          {t.templateExample} {data.template.pendingDecision && <PendingMarker id={data.template.pendingDecision} />}
        </p>
      )}
      <p className="muted">{t.onlyVariable}</p>

      <p className="notice notice--warning" role="note">
        {t.noUndo}
      </p>

      {nothing && <p className="notice" role="note">{t.nothingToImport}</p>}
      <p>
        <button type="button" disabled={confirm.pending || checking || nothing} onClick={() => confirm.run(undefined)}>
          {confirm.pending ? t.confirming : t.button(data.incidentsToCreate)}
        </button>
      </p>

      {confirm.error != null && (
        <>
          <ErrorState mutation error={confirm.error} />
          <p>
            <button type="button" className="secondary" disabled={checking || confirm.pending} onClick={() => void checkStatus()}>
              {checking ? t.checking : t.checkStatus}
            </button>
          </p>
        </>
      )}
      {stillInReview && (
        <p className="notice notice--warning" role="status">
          {t.stillInReview}
        </p>
      )}
    </section>
  );
}
