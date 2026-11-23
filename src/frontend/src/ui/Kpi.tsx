import type { ReactNode } from "react";

/** One figure: a label, its value and, when needed, a note under it. */
export default function Kpi({ label, value, note, accent = false }: { label: string; value: ReactNode; note?: ReactNode; accent?: boolean }) {
  return (
    <div className={accent ? "kpi kpi--primary" : "kpi"}>
      <span className="kpi__label">{label}</span>
      <strong className="kpi__value">{value}</strong>
      {note && <span className="kpi__note">{note}</span>}
    </div>
  );
}
