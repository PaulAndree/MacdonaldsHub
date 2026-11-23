export type AmountInput = { ok: true; value: string | null } | { ok: false };

const PLAIN = /^-?\d+(?:[.,]\d+)?$/;

/**
 * An amount typed by a person. A decimal comma is accepted and sent with a point; nothing else about
 * the digits changes, and no number is ever computed. An empty box is "absent" (`null`), which is not
 * the same as an explicit zero. Anything that is not a plain number is rejected.
 */
export function parseAmountInput(text: string): AmountInput {
  const trimmed = text.trim();
  if (trimmed === "") return { ok: true, value: null };
  if (!PLAIN.test(trimmed)) return { ok: false };
  return { ok: true, value: trimmed.replace(",", ".") };
}

/** How an amount from the API is put back in a box to edit it: same digits, decimal comma. */
export function amountToInput(value: string | null): string {
  return value === null ? "" : value.replace(".", ",");
}
