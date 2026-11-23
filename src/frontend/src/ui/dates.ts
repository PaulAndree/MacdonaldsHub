export type DateField = { ok: true; value: string | null } | { ok: false };

const DISPLAY = /^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$/;
const ISO = /^(\d{4})-(\d{2})-(\d{2})$/;
const TIME = /^(\d{1,2})[:.](\d{2})$/;

const pad = (n: number | string, width = 2) => String(n).padStart(width, "0");
const daysIn = (year: number, month: number) => new Date(Date.UTC(year, month, 0)).getUTCDate();

/** `2026-11-21` is shown to a person as `21/11/2026`. Anything that is not an ISO date is returned as it is. */
export function isoToDisplay(iso: string | null | undefined): string {
  const match = iso ? ISO.exec(iso) : null;
  return match ? `${match[3]}/${match[2]}/${match[1]}` : (iso ?? "");
}

/**
 * A date typed as `dd/mm/aaaa` (a single digit for day or month, and `-` or `.` as separators, are
 * accepted). The result is the ISO date the API takes. An empty box is absent (`null`). A date that
 * does not exist, such as 31/02/2026, is rejected: it is never turned into "no date".
 */
export function parseDateField(text: string): DateField {
  const trimmed = text.trim();
  if (trimmed === "") return { ok: true, value: null };
  const match = DISPLAY.exec(trimmed);
  if (!match) return { ok: false };
  const day = Number(match[1]);
  const month = Number(match[2]);
  const year = Number(match[3]);
  if (year < 1900 || year > 2100 || month < 1 || month > 12 || day < 1 || day > daysIn(year, month)) return { ok: false };
  return { ok: true, value: `${pad(year, 4)}-${pad(month)}-${pad(day)}` };
}

/** A time typed as `hh:mm`, 24 hours. Empty is absent; no time is ever invented. */
export function parseTimeField(text: string): DateField {
  const trimmed = text.trim();
  if (trimmed === "") return { ok: true, value: null };
  const match = TIME.exec(trimmed);
  if (!match) return { ok: false };
  const hours = Number(match[1]);
  const minutes = Number(match[2]);
  if (hours > 23 || minutes > 59) return { ok: false };
  return { ok: true, value: `${pad(hours)}:${pad(minutes)}` };
}
