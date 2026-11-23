import { Link } from "react-router-dom";
import { es } from "../../i18n/es";
import CancelBatchControl from "./CancelBatchControl";
import type { Batch } from "./types";

const t = es.pending;

/**
 * The user has a batch they have not confirmed. It does not expire, so whenever they return it is
 * offered back: resume, confirm or cancel. `blocked` explains why a new upload is not allowed.
 */
export default function PendingBatchNotice({ batch, blocked = false }: { batch: Batch; blocked?: boolean }) {
  const reviewing = batch.state === "in_review";
  return (
    <div className="notice notice--warning" role="region" aria-label={blocked ? t.blockedTitle : t.title}>
      <h2 style={{ marginTop: 0 }}>{blocked ? t.blockedTitle : t.title}</h2>
      <p>{blocked ? t.blockedText(batch.fileName) : reviewing ? t.inReview(batch.fileName) : t.processing(batch.fileName)}</p>
      <div className="actions-row">
        <Link className="button-link" to={`/lotes/${batch.id}`}>
          {t.resume}
        </Link>
        {reviewing && (
          <Link className="button-link secondary" to={`/lotes/${batch.id}#confirmacion`}>
            {t.confirmNow}
          </Link>
        )}
        <CancelBatchControl batchId={batch.id} />
      </div>
    </div>
  );
}
