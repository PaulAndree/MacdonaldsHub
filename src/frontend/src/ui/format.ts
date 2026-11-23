const madrid = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Europe/Madrid",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

/**
 * Presents a UTC instant in Europe/Madrid time as `YYYY-MM-DD HH:MM` (RNF-13). Instants are stored
 * and sent in UTC; only the presentation is local.
 */
export function formatTimestamp(iso: string): string {
  const parts = Object.fromEntries(madrid.formatToParts(new Date(iso)).map((p) => [p.type, p.value]));
  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}`;
}
