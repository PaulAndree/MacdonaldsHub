import { es } from "../../i18n/es";
import { AmountText, BranchText, IncidentDateText, OptionalText, providerName } from "../../ui/values";
import type { Row } from "./types";

type Comparison = NonNullable<Row["comparison"]>;
type Fields = Row["fields"];

const t = es.review.compare;

type Line = { key: keyof typeof t.fields; file: React.ReactNode; existing: React.ReactNode; differs: boolean };

/** The file version of a conflicting row next to the incident that already exists, with what differs marked. */
export default function ComparisonTable({ fields, comparison }: { fields: Fields; comparison: Comparison }) {
  const existing = comparison.existing;
  const differs = (name: string) => comparison.differingFields.includes(name);
  const lines: Line[] = [
    { key: "provider", file: providerName(fields.provider), existing: providerName(existing.provider), differs: differs("provider") },
    { key: "orderId", file: fields.orderId, existing: existing.orderId, differs: differs("orderId") },
    {
      key: "incidentDate",
      file: <IncidentDateText date={fields.incidentDate} time={fields.incidentTime} />,
      existing: <IncidentDateText date={existing.incidentDate} time={existing.incidentTime} />,
      differs: differs("incidentDate") || differs("incidentTime"),
    },
    { key: "branch", file: <BranchText branch={fields.branch} />, existing: <BranchText branch={existing.branch} />, differs: differs("branch") },
    { key: "claimAmount", file: <AmountText value={fields.claimAmount} />, existing: <AmountText value={existing.claimAmount} />, differs: differs("claimAmount") },
    { key: "providerCosts", file: <AmountText value={fields.providerCosts} />, existing: <AmountText value={existing.providerCosts} />, differs: differs("providerCosts") },
    { key: "total", file: <AmountText value={fields.total} />, existing: <AmountText value={existing.total} />, differs: differs("total") },
    { key: "description", file: <OptionalText value={fields.description} empty={es.values.noDescription} />, existing: <OptionalText value={existing.description} empty={es.values.noDescription} />, differs: differs("description") },
  ];
  return (
    <>
      <h3>{t.title}</h3>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">{t.field}</th>
              <th scope="col">{t.file}</th>
              <th scope="col">{t.existing}</th>
            </tr>
          </thead>
          <tbody>
            {lines.map((line) => (
              <tr key={line.key} className={line.differs ? "diff" : undefined}>
                <th scope="row">{t.fields[line.key]}</th>
                <td>{line.file}</td>
                <td>
                  {line.existing}
                  {line.differs && <span className="diff-flag"> · {t.differs}</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
