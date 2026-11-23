// Checks that every text/background and UI-component color pair in tokens.css meets WCAG 2.1 AA:
// 4.5:1 for text and 3:1 for borders and focus indicators. Usage: node scripts/contrast.mjs
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const tokensPath = process.env.TOKENS_FILE ?? resolve(root, "src/ui/tokens.css");

/** [foreground, background, minimum ratio, what it is] */
const pairs = [
  ["text", "bg", 4.5, "body text"],
  ["text", "surface", 4.5, "text on cards and tables"],
  ["text", "surface-muted", 4.5, "table headers"],
  ["text", "accent", 4.5, "text on the yellow accent"],
  ["text", "warning-bg", 4.5, "highlighted differences in a comparison"],
  ["text-muted", "bg", 4.5, "secondary text"],
  ["text-muted", "surface", 4.5, "secondary text on cards"],
  ["text-muted", "surface-muted", 4.5, "disabled buttons"],
  ["primary", "surface", 4.5, "links and secondary buttons"],
  ["primary", "bg", 4.5, "links on the page"],
  ["primary", "hover-bg", 4.5, "secondary button hover"],
  ["text", "hover-bg", 4.5, "hovered navigation"],
  ["on-primary", "primary", 4.5, "header and primary button"],
  ["on-primary", "primary-hover", 4.5, "primary button hover"],
  ["on-primary", "danger", 4.5, "danger button"],
  ["danger", "danger-bg", 4.5, "error notice and new-state pill"],
  ["danger", "surface", 4.5, "overdue and error text"],
  ["warning-text", "warning-bg", 4.5, "warning notice and in-review pill"],
  ["success", "success-bg", 4.5, "success notice and done pill"],
  ["success", "surface", 4.5, "positive text"],
  ["info-text", "info-bg", 4.5, "information notice and waiting pill"],
  ["on-example", "example-bg", 4.5, "example-data banner"],
  ["on-test", "test-bg", 4.5, "test-environment banner"],
  ["border", "surface", 3, "input borders"],
  ["border", "bg", 3, "borders on the page"],
  ["focus", "bg", 3, "focus ring on the page"],
  ["focus", "surface", 3, "focus ring on cards"],
  ["focus", "surface-muted", 3, "focus ring on muted areas"],
  ["on-primary", "primary", 3, "white focus ring inside the red header"],
];

function readTokens(css) {
  const tokens = new Map();
  for (const match of css.matchAll(/--color-([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})\s*;/g)) {
    tokens.set(match[1], match[2]);
  }
  return tokens;
}

function luminance(hex) {
  const channels = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const [r, g, b] = channels.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function ratio(a, b) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

const tokens = readTokens(readFileSync(tokensPath, "utf-8"));
const failures = [];
for (const [fg, bg, min, what] of pairs) {
  const a = tokens.get(fg);
  const b = tokens.get(bg);
  if (!a || !b) {
    failures.push(`missing token for ${fg} on ${bg}`);
    continue;
  }
  const value = ratio(a, b);
  const ok = value >= min;
  console.log(`${ok ? "ok  " : "FAIL"} ${value.toFixed(2).padStart(5)}:1 (min ${min})  ${fg} on ${bg}  ${what}`);
  if (!ok) failures.push(`${fg} on ${bg} is ${value.toFixed(2)}:1, needs ${min}:1 (${what})`);
}

if (failures.length > 0) {
  console.error(`\n${failures.length} pair(s) below WCAG AA:\n- ${failures.join("\n- ")}`);
  process.exit(1);
}
console.log(`\nAll ${pairs.length} pairs meet WCAG AA.`);
