const PLAIN = /^(-?)(\d+)(?:\.(\d+))?$/;

interface Scaled {
  value: bigint;
  scale: number;
}

function scaled(text: string): Scaled {
  const match = PLAIN.exec(text);
  if (!match) throw new Error(`Not a decimal: ${text}`);
  const [, sign, integer, fraction = ""] = match;
  const value = BigInt(`${integer}${fraction}`);
  return { value: sign === "-" ? -value : value, scale: fraction.length };
}

function rescale(item: Scaled, scale: number): bigint {
  return item.value * 10n ** BigInt(scale - item.scale);
}

function format(value: bigint, scale: number): string {
  const negative = value < 0n;
  const digits = (negative ? -value : value).toString().padStart(scale + 1, "0");
  const integer = digits.slice(0, digits.length - scale);
  const fraction = digits.slice(digits.length - scale);
  return `${negative ? "-" : ""}${integer}${scale > 0 ? `.${fraction}` : ""}`;
}

/** The exact sum of decimal strings, with as many decimals as the most precise of them. No floating point. */
export function sumDecimals(values: string[]): string | null {
  if (values.length === 0) return null;
  const parsed = values.map(scaled);
  const scale = Math.max(...parsed.map((p) => p.scale));
  return format(parsed.reduce((total, p) => total + rescale(p, scale), 0n), scale);
}

/** `numerator / denominator` with a fixed number of decimals, rounded half up. `null` when the denominator is zero. */
export function ratio(numerator: string, denominator: string, digits = 4): string | null {
  const n = scaled(numerator);
  const d = scaled(denominator);
  const scale = Math.max(n.scale, d.scale);
  const top = rescale(n, scale);
  const bottom = rescale(d, scale);
  if (bottom === 0n) return null;
  const factor = 10n ** BigInt(digits);
  const negative = (top < 0n) !== (bottom < 0n);
  const absTop = top < 0n ? -top : top;
  const absBottom = bottom < 0n ? -bottom : bottom;
  const quotient = (absTop * factor * 2n + absBottom) / (absBottom * 2n);
  return format(negative ? -quotient : quotient, digits);
}

/** Whole days from one ISO date to another (the second minus the first). */
export function daysBetween(fromIso: string, toIso: string): number {
  return Math.round((Date.parse(`${toIso}T00:00:00Z`) - Date.parse(`${fromIso}T00:00:00Z`)) / 86_400_000);
}
