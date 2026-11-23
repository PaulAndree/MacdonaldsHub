import type { ReactNode } from "react";
import { es } from "../i18n/es";
import { formatTimestamp } from "./format";

const DECIMAL = /^(-?)(\d+)(?:\.(\d+))?$/;

/**
 * An amount in euros exactly as it came: every decimal is kept (never rounded to two) and the sign is
 * kept. Only the presentation changes: decimal comma, thousands dots and the euro sign. It works on
 * the text, never on a floating-point number, so no value can be altered (RNF-13).
 * Text that is not a plain decimal is returned unchanged; the backend explains why it is invalid.
 */
export function formatAmount(value: string): string {
  const match = DECIMAL.exec(value);
  if (!match) return value;
  const [, sign, integer, fraction] = match;
  const grouped = integer!.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return `${sign}${grouped}${fraction === undefined ? "" : `,${fraction}`} €`;
}

/**
 * A rate such as 0.3692 as a percentage, 36,92 %, by moving the decimal point in the text. No number
 * is calculated, so no digit changes.
 */
export function formatRate(rate: string): string {
  const match = /^(\d+)(?:\.(\d+))?$/.exec(rate);
  if (!match) return rate;
  const fraction = (match[2] ?? "").padEnd(2, "0");
  const whole = `${match[1]}${fraction.slice(0, 2)}`.replace(/^0+(?=\d)/, "");
  const rest = fraction.slice(2);
  return `${whole}${rest ? `,${rest}` : ""} %`;
}

export function Unknown({ children }: { children: ReactNode }) {
  return <span className="unknown">{children}</span>;
}

/** An optional amount. An absent value is "unknown", never zero. */
export function AmountText({ value, unknown = es.values.unknownAmount }: { value: string | null; unknown?: string }) {
  if (value === null) return <Unknown>{unknown}</Unknown>;
  return <span className="amount">{formatAmount(value)}</span>;
}

/**
 * The incident date as `YYYY-MM-DD`, and the time as `HH:MM` only when the source had one. A date with
 * no time is never shown as 00:00. The time is Europe/Madrid local time, as the contract defines.
 */
export function IncidentDateText({ date, time }: { date: string | null; time: string | null }) {
  if (date === null) return <Unknown>{es.values.unknown}</Unknown>;
  if (time === null) return <span>{date}</span>;
  return (
    <span title={es.values.madridTime}>
      {date} {time}
    </span>
  );
}

/** A missing branch reads "Sin sucursal". */
export function BranchText({ branch }: { branch: string | null }) {
  return branch === null ? <Unknown>{es.values.noBranch}</Unknown> : <span>{branch}</span>;
}

export function OptionalText({ value, empty = es.values.unknown }: { value: string | null; empty?: string }) {
  return value === null ? <Unknown>{empty}</Unknown> : <span>{value}</span>;
}

/** A system timestamp (UTC) in Madrid time. */
export function Timestamp({ value }: { value: string }) {
  return (
    <time dateTime={value} title={es.values.madridTime}>
      {formatTimestamp(value)}
    </time>
  );
}

/** Provider name for display. The value itself stays lowercase everywhere else. */
export function providerName(provider: string | null): string {
  return provider === null ? es.values.unknown : (es.providers[provider] ?? provider);
}
