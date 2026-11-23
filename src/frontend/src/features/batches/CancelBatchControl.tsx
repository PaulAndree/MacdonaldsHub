import { useId, useState } from "react";
import { es } from "../../i18n/es";
import { ErrorState } from "../../ui/StateViews";
import { useDiscardBatch } from "./actions";

const t = es.pending;

/**
 * Cancels an unconfirmed batch, after asking. Cancelling deletes the file and the prepared rows and
 * the batch can no longer be confirmed. It is never offered for a confirmed batch.
 */
export default function CancelBatchControl({ batchId, label = t.cancel }: { batchId: string; label?: string }) {
  const [asking, setAsking] = useState(false);
  const titleId = useId();
  const discard = useDiscardBatch(batchId);

  if (!asking) {
    return (
      <button type="button" className="secondary" onClick={() => setAsking(true)}>
        {label}
      </button>
    );
  }
  return (
    <div role="group" aria-labelledby={titleId} className="inline-confirm">
      <p id={titleId}>
        <strong>{t.askTitle}</strong>
      </p>
      <p>{t.askText}</p>
      <p>
        <button type="button" className="danger" disabled={discard.pending} onClick={() => discard.run(undefined, { onSuccess: () => setAsking(false) })} autoFocus>
          {discard.pending ? t.cancelling : t.askYes}
        </button>{" "}
        <button type="button" className="secondary" disabled={discard.pending} onClick={() => setAsking(false)}>
          {t.askNo}
        </button>
      </p>
      {discard.error != null && <ErrorState mutation error={discard.error} />}
    </div>
  );
}
