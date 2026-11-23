import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../api/client";
import { es } from "../../i18n/es";
import { ErrorState } from "../../ui/StateViews";
import { useAction } from "../../ui/useAction";
import { batchKeys, usePendingBatch } from "./queries";
import type { DiscardResult } from "./types";

const t = es.logout;

/**
 * Cerrar sesión discards the user's unconfirmed batches and nothing else: it does not end the Google
 * session. With a batch under review it asks first and says what will be discarded.
 */
export default function LogoutButton({ canImport }: { canImport: boolean }) {
  const queryClient = useQueryClient();
  const pending = usePendingBatch(canImport);
  const [asking, setAsking] = useState(false);
  const [outcome, setOutcome] = useState<number | null>(null);

  const discard = useAction(async () => {
    const result = await api.post<DiscardResult>("/api/batches/discard-unconfirmed");
    await queryClient.invalidateQueries({ queryKey: batchKeys.pending });
    await queryClient.invalidateQueries({ queryKey: ["batches"] });
    return result;
  });

  function start() {
    setOutcome(null);
    if (pending.data) setAsking(true);
    else discard.run(undefined, { onSuccess: (result) => setOutcome(result.discarded) });
  }

  return (
    <div className="logout">
      <button type="button" className="on-brand" onClick={start} disabled={discard.pending}>
        {t.button}
      </button>
      {asking && pending.data && (
        <div role="alertdialog" aria-labelledby="logout-title" aria-describedby="logout-text" className="logout__panel">
          <p id="logout-title">
            <strong>{t.title}</strong>
          </p>
          <p id="logout-text">{t.withBatch(pending.data.fileName)}</p>
          <p>{t.only}</p>
          <p>
            <button
              type="button"
              className="danger"
              disabled={discard.pending}
              onClick={() =>
                discard.run(undefined, {
                  onSuccess: (result) => {
                    setOutcome(result.discarded);
                    setAsking(false);
                  },
                })
              }
              autoFocus
            >
              {discard.pending ? t.working : t.confirm}
            </button>{" "}
            <button type="button" className="secondary" disabled={discard.pending} onClick={() => setAsking(false)}>
              {t.keep}
            </button>
          </p>
          {discard.error != null && (
            <div role="alert">
              <p>{t.failed}</p>
              <ErrorState mutation error={discard.error} />
            </div>
          )}
        </div>
      )}
      {!asking && discard.error != null && (
        <div className="logout__panel" role="alert">
          <p>{t.failed}</p>
          <ErrorState mutation error={discard.error} />
        </div>
      )}
      {outcome !== null && (
        <p role="status" className="logout__status">
          {t.done(outcome)} {t.googleOpen}
        </p>
      )}
    </div>
  );
}
