import { es } from "../../i18n/es";
import type { RowClass } from "./types";

const STYLE: Record<RowClass, string> = {
  new: "pill--ok",
  duplicate: "pill--wait",
  conflict: "pill--review",
  error: "pill--new",
};

/** The class the backend gave a row. The browser only displays it; it never works it out. */
export default function ClassPill({ rowClass }: { rowClass: RowClass }) {
  return <span className={`pill ${STYLE[rowClass]}`}>{es.review.classSingular[rowClass]}</span>;
}
