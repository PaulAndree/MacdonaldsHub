import type { ReactNode } from "react";
import { es } from "../i18n/es";
import { describeError } from "./describeError";

export function LoadingState({ label = es.common.loading }: { label?: string }) {
  return (
    <p role="status" aria-live="polite">
      {label}
    </p>
  );
}

export function EmptyState({ title = es.states.empty, hint }: { title?: string; hint?: ReactNode }) {
  return (
    <div className="card" role="note">
      <p>
        <strong>{title}</strong>
      </p>
      {hint && <p>{hint}</p>}
    </div>
  );
}

export function ErrorState({
  error,
  onRetry,
  mutation = false,
}: {
  error: unknown;
  onRetry?: () => void;
  mutation?: boolean;
}) {
  return (
    <div className="notice notice--danger" role="alert">
      <p>{describeError(error, { mutation })}</p>
      {onRetry && !mutation && (
        <button type="button" className="secondary" onClick={onRetry}>
          {es.common.retry}
        </button>
      )}
    </div>
  );
}

export function IncompleteDataNotice({ count }: { count: number }) {
  if (count <= 0) return null;
  return (
    <p className="notice notice--warning" role="note">
      {es.states.incomplete(count)}
    </p>
  );
}

export function DeniedState({ detail }: { detail?: string }) {
  return (
    <div className="notice notice--danger" role="alert">
      <p>
        <strong>{es.states.deniedTitle}</strong>
      </p>
      <p>{detail ?? es.states.denied}</p>
    </div>
  );
}

export function DiscardedState() {
  return (
    <div className="notice notice--warning" role="status">
      <p>
        <strong>{es.states.discardedTitle}</strong>
      </p>
      <p>{es.states.discarded}</p>
    </div>
  );
}

export function PausedState() {
  return (
    <div className="notice notice--warning" role="status">
      <p>
        <strong>{es.states.pausedTitle}</strong>
      </p>
      <p>{es.states.paused}</p>
    </div>
  );
}

/** Marks an example of a decision that is still open. Never presented as approved. */
export function PendingMarker({ id, children }: { id: string; children?: ReactNode }) {
  return (
    <span className="pending-marker">
      {es.common.pendingDecision} ({id})
      {children && <span className="visually-hidden"> {children}</span>}
    </span>
  );
}
