import type { components } from "../api/schema";
import { es } from "../i18n/es";
import { type DatasetKind, datasetOf } from "./dataset";
import type { Cell } from "./xlsx";

type Incident = components["schemas"]["Incident"];

const UNKNOWN_AMOUNT = es.values.unknownAmount;

/**
 * Incidents as a sheet. Absent values are written out ("Sin sucursal", "Importe desconocido"), never
 * left as a zero, and amounts keep their source text.
 */
export function incidentsSheet(incidents: Incident[]): Cell[][] {
  const header = [
    "ID", "Proveedor", "Order ID", "Fecha de la incidencia", "Hora (Madrid)", "Sucursal", "Importe a reclamar",
    "Costos de proveedor", "Total", "Descripción", "Estado", "Canal", "Fecha de reclamación", "Fecha de recuperación", "Importe recuperado",
  ];
  const amount = (value: string | null) => value ?? UNKNOWN_AMOUNT;
  return [
    header,
    ...incidents.map((i) => [
      i.id,
      es.providers[i.provider] ?? i.provider,
      i.orderId,
      i.incidentDate,
      i.incidentTime ?? es.incidents.noTime,
      i.branch ?? es.values.noBranch,
      amount(i.claimAmount),
      amount(i.providerCosts),
      amount(i.total),
      i.description ?? es.values.noDescription,
      es.incidents.status[i.status],
      es.incidents.channel[i.channel],
      i.claimDate ?? es.incidents.noClaim,
      i.recoveryDate ?? es.incidents.noRecovery,
      amount(i.recoveredAmount),
    ]),
  ];
}

/** The excluded rows of a batch with their reasons, to correct the file and upload it again (RF-20). */
export function excludedSheet(kind: DatasetKind): Cell[][] {
  const excluded = datasetOf(kind).rows.filter((row) => row.class !== "new");
  return [
    ["Fila", "Clase", "Motivo", "Proveedor", "Order ID", "Fecha y hora", "Sucursal", "Importe a reclamar"],
    ...excluded.map((row) => [
      String(row.rowNumber),
      es.review.classSingular[row.class],
      row.reason ?? "",
      row.fields.provider ?? "",
      row.fields.orderId ?? "",
      [row.fields.incidentDate, row.fields.incidentTime].filter(Boolean).join(" "),
      row.fields.branch ?? es.values.noBranch,
      row.fields.claimAmount ?? UNKNOWN_AMOUNT,
    ]),
  ];
}
