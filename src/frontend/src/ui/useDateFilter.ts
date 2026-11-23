import { useEffect, useState } from "react";
import { isoToDisplay, parseDateField } from "./dates";

/**
 * A date box tied to a value that lives elsewhere (for example the address). The text is shown as
 * dd/mm/aaaa. The value changes only when the text is a real date or is empty; while the text is not
 * valid the value stays as it was and `invalid` says so, so a half-typed date never changes the result.
 */
export function useDateFilter(iso: string, onIso: (iso: string) => void) {
  const [text, setText] = useState(isoToDisplay(iso));
  const [invalid, setInvalid] = useState(false);

  // The value changed from outside (for example the filters were cleared): show it.
  useEffect(() => {
    const parsed = parseDateField(text);
    if (!parsed.ok || (parsed.value ?? "") !== iso) {
      setText(isoToDisplay(iso));
      setInvalid(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reacts to the value only, not to every keystroke
  }, [iso]);

  function change(next: string) {
    setText(next);
    const parsed = parseDateField(next);
    setInvalid(!parsed.ok);
    if (parsed.ok) onIso(parsed.value ?? "");
  }

  return { text, invalid, change };
}
