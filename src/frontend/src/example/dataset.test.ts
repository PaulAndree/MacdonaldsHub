import { describe, expect, it } from "vitest";
import { datasetOf, excludedOf, firstEmailRow, summaryOf } from "./dataset";

describe("example dataset", () => {
  const large = datasetOf("large");

  it("holds about 500 rows of the four classes (RNF-01)", () => {
    expect(large.rows).toHaveLength(500);
    expect(large.totals).toEqual({ new: 410, duplicate: 60, conflict: 18, error: 12 });
  });

  it("is the same on every load", () => {
    expect(datasetOf("large")).toBe(large);
  });

  it("numbers the rows from 2, after the header, without gaps", () => {
    expect(large.rows.map((r) => r.rowNumber)).toEqual(Array.from({ length: 500 }, (_, i) => i + 2));
  });

  it("gives every excluded row a reason and no new row one", () => {
    for (const row of large.rows) {
      if (row.class === "new") expect(row.reason).toBeNull();
      else expect(row.reason).toBeTruthy();
    }
  });

  it("repeats keys inside the file: all occurrences are excluded and point to each other", () => {
    const repeated = large.rows.filter((r) => r.repeatedInFile.length > 0);
    expect(repeated.length).toBeGreaterThanOrEqual(8);
    for (const row of repeated) {
      expect(["duplicate", "conflict"]).toContain(row.class);
      for (const other of row.repeatedInFile) {
        const twin = large.rows.find((r) => r.rowNumber === other);
        expect(twin?.fields.provider).toBe(row.fields.provider);
        expect(twin?.fields.orderId).toBe(row.fields.orderId);
        expect(twin?.repeatedInFile).toContain(row.rowNumber);
      }
    }
  });

  it("a conflict with an existing incident carries both versions and what differs", () => {
    const conflicts = large.rows.filter((r) => r.class === "conflict" && r.comparison);
    expect(conflicts.length).toBe(12);
    for (const row of conflicts) {
      const comparison = row.comparison!;
      expect(comparison.differingFields.length).toBeGreaterThan(0);
      const field = comparison.differingFields[0] as keyof typeof row.fields & keyof typeof comparison.existing;
      expect(comparison.existing[field]).not.toBe(row.fields[field]);
    }
  });

  it("error rows keep the raw value that failed, so the reason can be understood", () => {
    const errors = large.rows.filter((r) => r.class === "error");
    expect(errors.some((r) => r.fields.incidentDate === "12/11/2026")).toBe(true);
    expect(errors.some((r) => r.fields.claimAmount === "12,50 €")).toBe(true);
    expect(errors.some((r) => r.fields.orderId === null)).toBe(true);
  });

  it("includes absent optional values and amounts with more than two decimals", () => {
    const news = large.rows.filter((r) => r.class === "new");
    expect(news.some((r) => r.fields.branch === null)).toBe(true);
    expect(news.some((r) => r.fields.claimAmount === null)).toBe(true);
    expect(news.some((r) => r.fields.claimAmount === "0.1234")).toBe(true);
    expect(news.some((r) => r.fields.incidentTime === null)).toBe(true);
    expect(news.some((r) => r.fields.incidentTime !== null)).toBe(true);
  });

  it("derives the summary from the rows: emails only for Uber Eats and Just Eat", () => {
    const summary = summaryOf("large");
    const news = large.rows.filter((r) => r.class === "new");
    expect(summary.incidentsToCreate).toBe(410);
    expect(summary.emailsToGenerate).toBe(news.filter((r) => r.fields.provider !== "glovo").length);
    expect(summary.withoutEmail).toBe(news.filter((r) => r.fields.provider === "glovo").length);
    expect(summary.emailsToGenerate + summary.withoutEmail).toBe(summary.incidentsToCreate);
  });

  it("lists exactly the rows that are not new as excluded", () => {
    expect(excludedOf("large")).toHaveLength(90);
    expect(firstEmailRow("large")?.class).toBe("new");
  });

  it("a file with only the required columns has every optional value absent (UI-01)", () => {
    const { rows, totals } = datasetOf("required-only");
    expect(totals.new).toBe(rows.length);
    for (const row of rows) {
      expect(row.fields.branch).toBeNull();
      expect(row.fields.claimAmount).toBeNull();
      expect(row.fields.providerCosts).toBeNull();
      expect(row.fields.total).toBeNull();
      expect(row.fields.description).toBeNull();
    }
  });

  it("an identical file is all existing duplicates", () => {
    expect(datasetOf("identical").totals).toEqual({ new: 0, duplicate: 7, conflict: 0, error: 0 });
  });

  it("a rejected file holds no rows", () => {
    expect(datasetOf("none").rows).toEqual([]);
  });
});
