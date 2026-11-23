import type { InputHTMLAttributes } from "react";
import { es } from "../i18n/es";

/**
 * A date box that reads and shows `dd/mm/aaaa` whatever the language of the browser. The native date
 * control follows the browser's locale and cannot be forced, so this is a text box; the form turns
 * its text into the ISO date with `parseDateField`.
 */
export function DateInput(props: Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "inputMode" | "placeholder">) {
  return <input {...props} type="text" inputMode="numeric" autoComplete="off" placeholder={es.dates.placeholder} maxLength={10} />;
}

/** A time box in `hh:mm`, 24 hours, so it never shows AM or PM. */
export function TimeInput(props: Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "inputMode" | "placeholder">) {
  return <input {...props} type="text" inputMode="numeric" autoComplete="off" placeholder={es.dates.timePlaceholder} maxLength={5} />;
}
