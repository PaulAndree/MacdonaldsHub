import { useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useId, useState } from "react";
import { api } from "../../api/client";
import { es } from "../../i18n/es";
import { amountToInput, parseAmountInput } from "../../ui/amount";
import { isoToDisplay, parseDateField } from "../../ui/dates";
import { DateInput } from "../../ui/DateInput";
import { ErrorState, PendingMarker } from "../../ui/StateViews";
import { useAction } from "../../ui/useAction";
import { usePermission } from "../session/usePermission";
import { incidentKeys } from "./queries";
import type { Incident } from "./types";

const claimText = es.incidents.actions.claim;
const resultText = es.incidents.actions.result;
const correctText = es.incidents.actions.correct;

type Refresh = (message: string) => void;

/** Claim an incident that has no email, outside the application, and record when. */
function ClaimForm({ incident, onDone }: { incident: Incident; onDone: Refresh }) {
  const queryClient = useQueryClient();
  const [date, setDate] = useState("");
  const [problem, setProblem] = useState<"missing" | "invalid" | null>(null);
  const claim = useAction((claimDate: string) => api.post(`/api/incidents/${incident.id}/claim`, { claimDate }));
  const dateId = useId();

  function submit(event: FormEvent) {
    event.preventDefault();
    const parsed = parseDateField(date);
    if (!parsed.ok) return setProblem("invalid");
    if (parsed.value === null) return setProblem("missing");
    setProblem(null);
    claim.run(parsed.value, {
      onSuccess: () => {
        void queryClient.invalidateQueries({ queryKey: incidentKeys.all });
        onDone(claimText.done);
      },
    });
  }

  return (
    <section className="card" aria-labelledby="claim-title">
      <h2 id="claim-title">{claimText.title}</h2>
      <p>{claimText.help}</p>
      <p>
        {claimText.channel}: <PendingMarker id="P-11" /> <span className="muted">{claimText.channelNote}</span>
      </p>
      <form onSubmit={submit} noValidate className="form-grid">
        <label htmlFor={dateId}>
          {claimText.date}
          <DateInput id={dateId} value={date} aria-invalid={problem !== null} aria-describedby={problem ? `${dateId}-error` : undefined} onChange={(e) => setDate(e.target.value)} />
        </label>
        {problem && (
          <p id={`${dateId}-error`} role="alert" className="field-error">
            {problem === "missing" ? claimText.dateRequired : es.dates.invalid}
          </p>
        )}
        <p>
          <button type="submit" disabled={claim.pending}>
            {claim.pending ? claimText.sending : claimText.submit}
          </button>
        </p>
      </form>
      {claim.error != null && <ErrorState mutation error={claim.error} />}
    </section>
  );
}

interface ResultBody {
  result: "resolved" | "rejected";
  recoveredAmount: string | null;
  recoveryDate: string | null;
  reason?: string;
}

/** Record a result, or correct one that was already recorded (with its reason). */
function ResultForm({ incident, mode, onDone }: { incident: Incident; mode: "record" | "correct"; onDone: Refresh }) {
  const queryClient = useQueryClient();
  const correcting = mode === "correct";
  const text = correcting ? correctText : resultText;
  const [result, setResult] = useState<"resolved" | "rejected">(incident.result ?? "resolved");
  const [amount, setAmount] = useState(correcting ? amountToInput(incident.recoveredAmount) : "");
  const [date, setDate] = useState(correcting ? isoToDisplay(incident.recoveryDate) : "");
  const [reason, setReason] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const id = useId();

  const parsed = parseAmountInput(amount);
  const parsedDate = parseDateField(date);
  const unchanged =
    correcting && result === incident.result && parsed.ok && parsed.value === incident.recoveredAmount && parsedDate.ok && parsedDate.value === incident.recoveryDate;
  const amountInvalid = submitted && !parsed.ok;
  const dateInvalid = submitted && !parsedDate.ok;
  const reasonMissing = submitted && correcting && reason.trim() === "";

  const action = useAction((body: ResultBody) =>
    api.post(correcting ? `/api/incidents/${incident.id}/corrections` : `/api/incidents/${incident.id}/result`, body),
  );

  function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitted(true);
    if (!parsed.ok || !parsedDate.ok || (correcting && (reason.trim() === "" || unchanged))) return;
    const body: ResultBody = { result, recoveredAmount: parsed.value, recoveryDate: parsedDate.value };
    if (correcting) body.reason = reason.trim();
    action.run(body, {
      onSuccess: () => {
        void queryClient.invalidateQueries({ queryKey: incidentKeys.all });
        onDone(correcting ? correctText.done : resultText.done);
      },
    });
  }

  return (
    <section className="card" aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`}>{text.title}</h2>
      <p>{correcting ? correctText.help : resultText.help}</p>
      <form onSubmit={submit} noValidate className="form-grid">
        <label htmlFor={`${id}-kind`}>
          {resultText.kind}
          <select id={`${id}-kind`} value={result} onChange={(e) => setResult(e.target.value as "resolved" | "rejected")}>
            <option value="resolved">{es.incidents.result.kinds.resolved}</option>
            <option value="rejected">{es.incidents.result.kinds.rejected}</option>
          </select>
        </label>
        <label htmlFor={`${id}-amount`}>
          {resultText.amount}
          <input id={`${id}-amount`} type="text" inputMode="decimal" value={amount} aria-invalid={amountInvalid} aria-describedby={`${id}-amount-help`} onChange={(e) => setAmount(e.target.value)} />
        </label>
        <p id={`${id}-amount-help`} className={amountInvalid ? "field-error" : "muted"} role={amountInvalid ? "alert" : undefined}>
          {amountInvalid ? resultText.invalidAmount : resultText.amountHelp}
        </p>
        <label htmlFor={`${id}-date`}>
          {resultText.date}
          <DateInput id={`${id}-date`} value={date} aria-invalid={dateInvalid} onChange={(e) => setDate(e.target.value)} />
        </label>
        {dateInvalid && (
          <p role="alert" className="field-error">
            {es.dates.invalid}
          </p>
        )}
        {correcting && (
          <>
            <label htmlFor={`${id}-reason`}>
              {correctText.reason}
              <textarea id={`${id}-reason`} rows={2} value={reason} aria-invalid={reasonMissing} onChange={(e) => setReason(e.target.value)} />
            </label>
            {reasonMissing && (
              <p role="alert" className="field-error">
                {correctText.reasonRequired}
              </p>
            )}
            {unchanged && <p className="muted">{correctText.unchanged}</p>}
          </>
        )}
        <p>
          <button type="submit" disabled={action.pending || Boolean(unchanged)}>
            {action.pending ? text.sending : text.submit}
          </button>
        </p>
      </form>
      {action.error != null && <ErrorState mutation error={action.error} />}
    </section>
  );
}

/**
 * What an administrator can do with an incident, by its state. A global manager only consults, and a
 * claimed-by-email incident has nothing to do by hand. Hiding these is a convenience: the API decides.
 */
export default function IncidentActions({ incident }: { incident: Incident }) {
  const canWrite = usePermission("incidents_write");
  const [message, setMessage] = useState<string | null>(null);
  if (!canWrite) return null;

  return (
    <>
      {message && (
        <p role="status" className="notice notice--success">
          {message}
        </p>
      )}
      {incident.status === "imported_no_email" && <ClaimForm key={incident.status} incident={incident} onDone={setMessage} />}
      {incident.status === "claimed" && <ResultForm key={incident.status} incident={incident} mode="record" onDone={setMessage} />}
      {(incident.status === "resolved" || incident.status === "rejected") && (
        <ResultForm key={`${incident.status}-${incident.recoveredAmount}-${incident.recoveryDate}`} incident={incident} mode="correct" onDone={setMessage} />
      )}
    </>
  );
}
