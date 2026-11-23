import { useQueryClient } from "@tanstack/react-query";
import { es } from "../../i18n/es";
import { formatTimestamp } from "../../ui/format";
import { ErrorState, PausedState } from "../../ui/StateViews";
import { useAction } from "../../ui/useAction";
import { usePermission } from "../session/usePermission";
import { changeQueue, queueKey, type QueueStatus } from "./queries";

const t = es.queue;

/**
 * Global pause and resume. Pausing only stops new attempts: one that already started may finish, and the
 * screen says so. Without the permission the buttons are not offered, but the API decides (UI-10).
 */
export default function QueueControl({ status }: { status: QueueStatus }) {
  const allowed = usePermission("queue_control");
  const queryClient = useQueryClient();
  const action = useAction((kind: "pause" | "resume") => changeQueue(kind));
  const refresh = () => void queryClient.invalidateQueries({ queryKey: queueKey });
  const kind = status.paused ? "resume" : "pause";
  const busy = action.pending;
  const label = status.paused ? (busy ? t.resuming : t.resume) : busy ? t.pausing : t.pause;

  return (
    <section className="card" aria-labelledby="queue-control">
      <h2 id="queue-control">{status.paused ? t.paused : t.running}</h2>
      {!status.sendingAvailable && (
        <div className="notice notice--warning" role="status">
          <p>
            <strong>{t.unavailableTitle}</strong>
          </p>
          {status.unavailableReason && <p>{status.unavailableReason}</p>}
          <p>{t.unavailableNote}</p>
        </div>
      )}
      {status.paused && <PausedState />}
      {status.paused && status.pausedAt && <p>{t.pausedSince(formatTimestamp(status.pausedAt))}</p>}
      {status.inFlight > 0 && (
        <p role="status">{status.paused ? t.inFlightWhilePaused(status.inFlight) : t.inFlight(status.inFlight)}</p>
      )}
      {!status.paused && <p>{t.pauseHelp}</p>}
      {allowed && (
        <button type="button" disabled={busy} aria-busy={busy} onClick={() => action.run(kind, { onSuccess: refresh })}>
          {label}
        </button>
      )}
      {action.error != null && <ErrorState error={action.error} mutation />}
    </section>
  );
}
