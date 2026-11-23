import { useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useId, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, api } from "../../api/client";
import { es } from "../../i18n/es";
import { parseAmountInput } from "../../ui/amount";
import { parseDateField, parseTimeField } from "../../ui/dates";
import { DateInput, TimeInput } from "../../ui/DateInput";
import PageHeader from "../../ui/PageHeader";
import { ErrorState } from "../../ui/StateViews";
import { useAction } from "../../ui/useAction";
import { AmountText, BranchText, IncidentDateText, OptionalText, providerName } from "../../ui/values";
import ComparisonTable from "../batches/ComparisonTable";
import { incidentKeys, useBranchOptions } from "./queries";
import type { Incident, IncidentCore } from "./types";

const t = es.manual;
const PROVIDERS = ["uber eats", "just eat", "glovo"];

interface Form {
  provider: string;
  orderId: string;
  date: string;
  time: string;
  branch: string;
  claimAmount: string;
  providerCosts: string;
  total: string;
  description: string;
}
const EMPTY: Form = { provider: "", orderId: "", date: "", time: "", branch: "", claimAmount: "", providerCosts: "", total: "", description: "" };

type ManualCheck = { outcome: "new" | "duplicate" | "conflict"; existing: IncidentCore | null; differingFields: string[] };
type Step = { name: "edit" } | { name: "review"; core: IncidentCore } | { name: "blocked"; check: ManualCheck; core: IncidentCore } | { name: "saved"; incident: Incident };

/** The form's text as the data the API takes. Nothing is trimmed or repaired; empty optional boxes are absent. */
function toCore(form: Form): { core: IncidentCore } | { errors: Partial<Record<keyof Form, string>> } {
  const errors: Partial<Record<keyof Form, string>> = {};
  if (!form.provider) errors.provider = t.errors.provider;
  if (form.orderId.trim() === "") errors.orderId = t.errors.orderId;
  const date = parseDateField(form.date);
  if (!date.ok) errors.date = es.dates.invalid;
  else if (date.value === null) errors.date = t.errors.date;
  const time = parseTimeField(form.time);
  if (!time.ok) errors.time = es.dates.invalidTime;
  const amounts = { claimAmount: parseAmountInput(form.claimAmount), providerCosts: parseAmountInput(form.providerCosts), total: parseAmountInput(form.total) };
  for (const [key, parsed] of Object.entries(amounts)) if (!parsed.ok) errors[key as keyof Form] = t.errors.amount;
  if (Object.keys(errors).length > 0) return { errors };
  const value = (parsed: ReturnType<typeof parseAmountInput>) => (parsed.ok ? parsed.value : null);
  return {
    core: {
      provider: form.provider as IncidentCore["provider"],
      orderId: form.orderId,
      incidentDate: date.ok && date.value ? date.value : "",
      incidentTime: time.ok ? time.value : null,
      branch: form.branch || null,
      claimAmount: value(amounts.claimAmount),
      providerCosts: value(amounts.providerCosts),
      total: value(amounts.total),
      description: form.description === "" ? null : form.description,
    },
  };
}

const asFields = (core: IncidentCore) => ({ ...core });

function Field({ id, label, error, help, children }: { id: string; label: string; error?: string; help?: string; children: React.ReactNode }) {
  return (
    <>
      <label htmlFor={id}>
        {label}
        {children}
      </label>
      {error ? (
        <p id={`${id}-error`} role="alert" className="field-error">
          {error}
        </p>
      ) : (
        help && <p className="muted">{help}</p>
      )}
    </>
  );
}

export default function ManualEntryScreen() {
  const queryClient = useQueryClient();
  const branches = useBranchOptions();
  const [form, setForm] = useState<Form>(EMPTY);
  const [errors, setErrors] = useState<Partial<Record<keyof Form, string>>>({});
  const [step, setStep] = useState<Step>({ name: "edit" });
  const id = useId();
  const set = (key: keyof Form) => (event: { target: { value: string } }) => setForm((current) => ({ ...current, [key]: event.target.value }));

  const check = useAction((core: IncidentCore) => api.post<ManualCheck>("/api/incidents/manual/check", core));
  const save = useAction((core: IncidentCore) => api.post<Incident>("/api/incidents/manual", core));

  function submit(event: FormEvent) {
    event.preventDefault();
    const parsed = toCore(form);
    if ("errors" in parsed) return setErrors(parsed.errors);
    setErrors({});
    check.run(parsed.core, {
      onSuccess: (result) => setStep(result.outcome === "new" ? { name: "review", core: parsed.core } : { name: "blocked", check: result, core: parsed.core }),
    });
  }

  function confirm(core: IncidentCore) {
    save.run(core, {
      onSuccess: (incident) => {
        void queryClient.invalidateQueries({ queryKey: incidentKeys.all });
        setStep({ name: "saved", incident });
      },
    });
  }

  // Another window created the same key between the check and the confirmation.
  const conflictOnSave = save.error instanceof ApiError && save.error.code === "incident_exists";

  if (step.name === "saved") {
    return (
      <>
        <PageHeader title={es.titles.manualEntry} />
        <div className="notice notice--success" role="status">
          <h2 style={{ marginTop: 0 }}>{t.savedTitle}</h2>
          <p>{t.savedText}</p>
          <p>
            <Link to={`/incidencias/${step.incident.id}`}>{t.open}</Link> ·{" "}
            <button type="button" className="secondary" onClick={() => { setForm(EMPTY); setStep({ name: "edit" }); save.reset(); check.reset(); }}>
              {t.another}
            </button>
          </p>
        </div>
      </>
    );
  }

  if (step.name === "review") {
    const core = step.core;
    return (
      <>
        <PageHeader title={es.titles.manualEntry} />
        <section className="card" aria-labelledby={`${id}-review`}>
          <h2 id={`${id}-review`}>{t.reviewTitle}</h2>
          <p className="notice notice--warning" role="note">{t.notSaved}</p>
          <dl className="facts">
            <dt>{es.incidents.fields.provider}</dt>
            <dd>{providerName(core.provider)}</dd>
            <dt>{es.incidents.fields.orderId}</dt>
            <dd>{core.orderId}</dd>
            <dt>{es.incidents.dates.incident}</dt>
            <dd><IncidentDateText date={core.incidentDate} time={core.incidentTime} /></dd>
            <dt>{es.incidents.fields.branch}</dt>
            <dd><BranchText branch={core.branch} /></dd>
            <dt>{es.incidents.fields.claimAmount}</dt>
            <dd><AmountText value={core.claimAmount} /></dd>
            <dt>{es.incidents.fields.providerCosts}</dt>
            <dd><AmountText value={core.providerCosts} /></dd>
            <dt>{es.incidents.fields.total}</dt>
            <dd><AmountText value={core.total} /></dd>
            <dt>{es.incidents.fields.description}</dt>
            <dd><OptionalText value={core.description} empty={es.values.noDescription} /></dd>
          </dl>
          <p className="muted">{core.provider === "glovo" ? t.emailNone : t.emailWill}</p>
          {save.error != null && (conflictOnSave ? <p className="notice notice--danger" role="alert">{t.raced} {save.error instanceof ApiError ? save.error.message : ""}</p> : <ErrorState mutation error={save.error} />)}
          <p>
            <button type="button" disabled={save.pending} onClick={() => confirm(core)}>
              {save.pending ? t.saving : t.confirm}
            </button>{" "}
            <button type="button" className="secondary" disabled={save.pending} onClick={() => { save.reset(); setStep({ name: "edit" }); }}>
              {t.edit}
            </button>
          </p>
        </section>
      </>
    );
  }

  const blocked = step.name === "blocked" ? step : null;
  return (
    <>
      <PageHeader title={es.titles.manualEntry} />
      {blocked && (
        <div className="notice notice--danger" role="alert">
          <h2 style={{ marginTop: 0 }}>{blocked.check.outcome === "duplicate" ? t.duplicateTitle : t.conflictTitle}</h2>
          <p>{blocked.check.outcome === "duplicate" ? t.duplicateText : t.conflictText}</p>
          {blocked.check.outcome === "conflict" && blocked.check.existing && (
            <ComparisonTable fields={asFields(blocked.core)} comparison={{ existing: blocked.check.existing, differingFields: blocked.check.differingFields }} />
          )}
        </div>
      )}
      <form className="card form-grid" onSubmit={submit} noValidate aria-label={es.titles.manualEntry}>
        <Field id={`${id}-provider`} label={t.provider} error={errors.provider}>
          <select id={`${id}-provider`} value={form.provider} aria-invalid={Boolean(errors.provider)} onChange={set("provider")}>
            <option value="">{t.chooseProvider}</option>
            {PROVIDERS.map((p) => <option key={p} value={p}>{providerName(p)}</option>)}
          </select>
        </Field>
        <Field id={`${id}-order`} label={t.orderId} error={errors.orderId} help={t.orderIdHelp}>
          <input id={`${id}-order`} type="text" value={form.orderId} aria-invalid={Boolean(errors.orderId)} onChange={set("orderId")} />
        </Field>
        <Field id={`${id}-date`} label={t.date} error={errors.date}>
          <DateInput id={`${id}-date`} value={form.date} aria-invalid={Boolean(errors.date)} onChange={set("date")} />
        </Field>
        <Field id={`${id}-time`} label={t.time} error={errors.time} help={t.timeHelp}>
          <TimeInput id={`${id}-time`} value={form.time} aria-invalid={Boolean(errors.time)} onChange={set("time")} />
        </Field>
        <Field id={`${id}-branch`} label={t.branch}>
          <select id={`${id}-branch`} value={form.branch} onChange={set("branch")}>
            <option value="">{t.noBranch}</option>
            {branches.data?.items.map((b) => <option key={b.id} value={b.name}>{b.name}</option>)}
          </select>
        </Field>
        <Field id={`${id}-claim`} label={t.claimAmount} error={errors.claimAmount} help={t.amountHelp}>
          <input id={`${id}-claim`} type="text" inputMode="decimal" value={form.claimAmount} aria-invalid={Boolean(errors.claimAmount)} onChange={set("claimAmount")} />
        </Field>
        <Field id={`${id}-costs`} label={t.providerCosts} error={errors.providerCosts}>
          <input id={`${id}-costs`} type="text" inputMode="decimal" value={form.providerCosts} aria-invalid={Boolean(errors.providerCosts)} onChange={set("providerCosts")} />
        </Field>
        <Field id={`${id}-total`} label={t.total} error={errors.total}>
          <input id={`${id}-total`} type="text" inputMode="decimal" value={form.total} aria-invalid={Boolean(errors.total)} onChange={set("total")} />
        </Field>
        <Field id={`${id}-description`} label={t.description}>
          <textarea id={`${id}-description`} rows={3} value={form.description} onChange={set("description")} />
        </Field>
        <p className="muted">{form.provider === "glovo" ? t.emailNone : form.provider ? t.emailWill : t.emailGeneral}</p>
        {check.error != null && <ErrorState mutation error={check.error} />}
        <p>
          <button type="submit" disabled={check.pending}>
            {check.pending ? t.checking : t.check}
          </button>
        </p>
      </form>
    </>
  );
}
