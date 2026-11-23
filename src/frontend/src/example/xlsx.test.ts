import { describe, expect, it } from "vitest";
import { buildXlsx } from "./xlsx";
import { crc32, readStoredZip, zipStored } from "./zip";

describe("example XLSX writer", () => {
  it("computes the standard CRC-32", () => {
    expect(crc32(new TextEncoder().encode("123456789"))).toBe(0xcbf43926);
  });

  it("writes a ZIP that reads back with the same files", () => {
    const bytes = zipStored([
      { name: "a.txt", data: new TextEncoder().encode("hola") },
      { name: "dir/b.txt", data: new TextEncoder().encode("adiós") },
    ]);
    expect(readStoredZip(bytes)).toEqual({ "a.txt": "hola", "dir/b.txt": "adiós" });
  });

  it("writes the parts of a spreadsheet and keeps every value as text, exactly", () => {
    const files = readStoredZip(buildXlsx("Incidencias", [["Importe", "Nota"], ["0.1234", null], ["-3.00", "a & <b>"]]));
    expect(Object.keys(files)).toEqual([
      "[Content_Types].xml",
      "_rels/.rels",
      "xl/workbook.xml",
      "xl/_rels/workbook.xml.rels",
      "xl/worksheets/sheet1.xml",
    ]);
    const sheet = files["xl/worksheets/sheet1.xml"]!;
    expect(sheet).toContain(">0.1234<");
    expect(sheet).toContain(">-3.00<");
    expect(sheet).toContain("a &amp; &lt;b&gt;");
    // An empty cell is not written at all: it is not turned into a zero.
    expect(sheet).not.toContain('r="B2"');
    expect(files["xl/workbook.xml"]).toContain('name="Incidencias"');
  });
});
