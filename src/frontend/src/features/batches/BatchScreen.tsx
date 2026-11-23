import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { es } from "../../i18n/es";
import PageHeader from "../../ui/PageHeader";
import QueryView from "../../ui/QueryView";
import { DiscardedState, ErrorState } from "../../ui/StateViews";
import { useDiscardBatch } from "./actions";
import CancelBatchControl from "./CancelBatchControl";
import ConfirmationResultView from "./ConfirmationResultView";
import IdenticalFileNotice from "./IdenticalFileNotice";
import ProcessingState from "./ProcessingState";
import { useBatch, useConfirmationResult } from "./queries";
import RejectionNotice from "./RejectionNotice";
import ReviewPanel from "./ReviewPanel";
import { type Batch, isUnconfirmed } from "./types";

function BatchView({ batch }: { batch: Batch }) {
  const [acknowledged, setAcknowledged] = useState(false);
  const result = useConfirmationResult(batch.id);
  const discard = useDiscardBatch(batch.id);
  // Cancelling is offered while the batch is unconfirmed, never after confirming.
  const cancel = isUnconfirmed(batch) ? (
    <p>
      <CancelBatchControl batchId={batch.id} />
    </p>
  ) : null;

  switch (batch.state) {
    case "uploaded":
    case "processing":
      return (
        <>
          {cancel}
          <ProcessingState />
        </>
      );
    case "rejected":
      return batch.rejection ? <RejectionNotice rejection={batch.rejection} /> : null;
    case "discarded":
      return (
        <>
          <DiscardedState />
          <p>
            <Link to="/importar">{es.import.chooseAnother}</Link>
          </p>
        </>
      );
    case "in_review":
      if (batch.identicalFile && !acknowledged) {
        return (
          <>
            <IdenticalFileNotice
              notice={batch.identicalFile}
              cancelling={discard.pending}
              onContinue={() => setAcknowledged(true)}
              onCancel={() => discard.run(undefined)}
            />
            {discard.error != null && <ErrorState mutation error={discard.error} />}
          </>
        );
      }
      return (
        <>
          {cancel}
          <ReviewPanel batch={batch} />
        </>
      );
    case "confirmed":
    case "completed":
      return result.data ? (
        <ConfirmationResultView result={result.data} />
      ) : (
        <div className="notice notice--success" role="status">
          <p>{es.confirm.confirmedOn}</p>
          <p>
            <Link to="/incidencias">{es.confirm.viewIncidents}</Link>
          </p>
        </div>
      );
    default:
      return null;
  }
}

/** One batch: processing, review, confirmation or its final state. */
export default function BatchScreen() {
  const { batchId = "" } = useParams();
  const batch = useBatch(batchId);
  return (
    <>
      <PageHeader title={es.titles.batch} subtitle={batch.data?.fileName} />
      <QueryView query={batch}>{(data) => <BatchView batch={data} />}</QueryView>
    </>
  );
}
