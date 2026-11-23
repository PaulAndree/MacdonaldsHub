import { es } from "../../i18n/es";
import { formatTimestamp } from "../../ui/format";
import type { Batch } from "./types";

type Notice = NonNullable<Batch["identicalFile"]>;

/**
 * The file matches one already confirmed. It is a warning only: it does not replace the row-level
 * deduplication, so the administrator may continue or cancel.
 */
export default function IdenticalFileNotice({
  notice,
  onContinue,
  onCancel,
  cancelling = false,
}: {
  notice: Notice;
  onContinue: () => void;
  onCancel: () => void;
  cancelling?: boolean;
}) {
  return (
    <div className="notice notice--warning" role="alert">
      <h2 style={{ marginTop: 0 }}>{es.identical.title}</h2>
      <p>{es.identical.text(formatTimestamp(notice.confirmedAt))}</p>
      <p>
        <button type="button" onClick={onContinue}>
          {es.identical.continue}
        </button>{" "}
        <button type="button" className="secondary" disabled={cancelling} onClick={onCancel}>
          {es.identical.cancel}
        </button>
      </p>
    </div>
  );
}
