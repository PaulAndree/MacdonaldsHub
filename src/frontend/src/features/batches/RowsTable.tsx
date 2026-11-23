import { Fragment, useState } from "react";
import { es } from "../../i18n/es";
import { AmountText, BranchText, IncidentDateText, Unknown, providerName } from "../../ui/values";
import ClassPill from "./ClassPill";
import RowDetail, { hasDetail } from "./RowDetail";
import type { Row } from "./types";

const c = es.review.columns;

function dateOf(row: Row) {
  return <IncidentDateText date={row.fields.incidentDate} time={row.fields.incidentTime} />;
}

/** Rows as read from the file, each with the class and reason the backend assigned. */
export default function RowsTable({ rows }: { rows: Row[] }) {
  const [open, setOpen] = useState<number | null>(null);
  return (
    <div className="table-scroll">
      <table>
        <caption className="visually-hidden">{es.review.tableCaption}</caption>
        <thead>
          <tr>
            <th scope="col">{c.row}</th>
            <th scope="col">{c.class}</th>
            <th scope="col">{c.provider}</th>
            <th scope="col">{c.orderId}</th>
            <th scope="col">{c.date}</th>
            <th scope="col">{c.branch}</th>
            <th scope="col">{c.claim}</th>
            <th scope="col">{c.reason}</th>
            <th scope="col">{es.review.detailColumn}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const expanded = open === row.rowNumber;
            return (
              <Fragment key={row.rowNumber}>
                <tr>
                  <td>{row.rowNumber}</td>
                  <td>
                    <ClassPill rowClass={row.class} />
                  </td>
                  <td>{providerName(row.fields.provider)}</td>
                  <td className="nowrap">{row.fields.orderId ?? <Unknown>{es.review.missingOrderId}</Unknown>}</td>
                  <td>{dateOf(row)}</td>
                  <td>
                    <BranchText branch={row.fields.branch} />
                  </td>
                  <td>
                    <AmountText value={row.fields.claimAmount} />
                  </td>
                  <td>{row.reason ?? ""}</td>
                  <td>
                    {hasDetail(row) && (
                      <button
                        type="button"
                        className="secondary"
                        aria-expanded={expanded}
                        aria-controls={`row-detail-${row.rowNumber}`}
                        onClick={() => setOpen(expanded ? null : row.rowNumber)}
                      >
                        {expanded ? es.review.hideDetail : es.review.detail}
                        <span className="visually-hidden"> fila {row.rowNumber}</span>
                      </button>
                    )}
                  </td>
                </tr>
                {expanded && (
                  <tr id={`row-detail-${row.rowNumber}`} className="row-detail">
                    <td colSpan={9}>
                      <RowDetail row={row} />
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
