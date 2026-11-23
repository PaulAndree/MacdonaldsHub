import { es } from "../../i18n/es";
import PageHeader from "../../ui/PageHeader";
import PendingBatchNotice from "./PendingBatchNotice";
import { usePendingBatch } from "./queries";
import UploadPanel from "./UploadPanel";

export default function ImportScreen() {
  const pending = usePendingBatch();
  return (
    <>
      <PageHeader title={es.titles.import} subtitle={es.import.subtitle} />
      {pending.data && <PendingBatchNotice batch={pending.data} blocked />}
      <UploadPanel disabled={Boolean(pending.data)} />
      <div className="card">
        <p>{es.import.requiredHeaders}</p>
        <p>{es.import.optionalHeaders}</p>
      </div>
    </>
  );
}
