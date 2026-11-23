import { es } from "../../i18n/es";
import ComparisonTable from "./ComparisonTable";
import type { Row } from "./types";

/** Whether a row has something more to explain: another version, or other occurrences of its key. */
export const hasDetail = (row: Row) => row.comparison !== null || row.repeatedInFile.length > 0;

export default function RowDetail({ row }: { row: Row }) {
  return (
    <div>
      {row.comparison && <ComparisonTable fields={row.fields} comparison={row.comparison} />}
      {row.repeatedInFile.length > 0 && (
        <>
          <h3>{es.review.repeated.title}</h3>
          <p>{es.review.repeated.text(row.repeatedInFile)}</p>
        </>
      )}
    </div>
  );
}
