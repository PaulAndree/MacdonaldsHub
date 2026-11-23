import { Link } from "react-router-dom";
import { es } from "../../i18n/es";
import ClassPill from "./ClassPill";
import type { ConfirmationResult } from "./types";

const t = es.confirm;

/** What a confirmation actually did. It can differ from the preview: rows may have matched meanwhile. */
export default function ConfirmationResultView({ result }: { result: ConfirmationResult }) {
  return (
    <>
      <div className="notice notice--success" role="status">
        <h2 style={{ marginTop: 0 }}>{t.doneTitle}</h2>
        <p>{t.doneText}</p>
        {result.alreadyConfirmed && <p>{t.repeated}</p>}
      </div>

      <div className="card">
        <dl className="facts">
          <dt>{t.created}</dt>
          <dd>{result.createdIncidents}</dd>
          <dt>{t.pendingEmails}</dt>
          <dd>{result.pendingEmails}</dd>
          <dt>{t.withoutEmail}</dt>
          <dd>{result.withoutEmail}</dd>
          <dt>{t.excluded}</dt>
          <dd>{result.excluded.length + result.excludedAtConfirmation.length}</dd>
        </dl>
        <p className="muted">{t.emailsHelp}</p>

        {result.excludedAtConfirmation.length > 0 && (
          <div className="notice notice--warning" role="note">
            <h3 style={{ marginTop: 0 }}>{t.overtakenTitle}</h3>
            <p>{t.overtakenText}</p>
            <ul>
              {result.excludedAtConfirmation.map((row) => (
                <li key={row.rowNumber}>
                  {es.review.columns.row} {row.rowNumber}: {row.reason}
                </li>
              ))}
            </ul>
          </div>
        )}

        {result.excluded.length > 0 && (
          <details>
            <summary>{t.excludedList(result.excluded.length)}</summary>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th scope="col">{t.columns.row}</th>
                    <th scope="col">{t.columns.class}</th>
                    <th scope="col">{t.columns.reason}</th>
                  </tr>
                </thead>
                <tbody>
                  {result.excluded.map((row) => (
                    <tr key={row.rowNumber}>
                      <td>{row.rowNumber}</td>
                      <td>
                        <ClassPill rowClass={row.class} />
                      </td>
                      <td>{row.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        )}
        <p>
          <Link to="/incidencias">{t.viewIncidents}</Link> · <Link to="/importar">{es.import.chooseAnother}</Link>
        </p>
      </div>
    </>
  );
}
