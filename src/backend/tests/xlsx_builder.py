"""Builds small synthetic .xlsx files for tests, down to the raw text of each cell.

A cell is one of:
  None                    empty
  ("n", "12.345")         number, written exactly as given
  ("s", "text")           text through the shared strings table
  ("i", "text")           inline text
  ("dt", serial)          number with a date-time style (serial as written, e.g. "46022.5")
  ("d", serial)           number with a date style
  ("f", "A1+1", "3")      formula with a cached value
  ("b", "1")              boolean
  ("e", "#N/A")           error
"""

import io
import zipfile
from typing import Any
from xml.sax.saxutils import escape

Cell = tuple[str, ...] | None

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

STYLES = f"""<?xml version="1.0" encoding="UTF-8"?>
<styleSheet xmlns="{NS}">
  <numFmts count="1"><numFmt numFmtId="164" formatCode="yyyy\\-mm\\-dd\\ hh:mm"/></numFmts>
  <cellXfs count="4">
    <xf numFmtId="0"/>
    <xf numFmtId="14"/>
    <xf numFmtId="164"/>
    <xf numFmtId="49"/>
  </cellXfs>
</styleSheet>"""


def _col(index: int) -> str:
    name = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        name = chr(65 + rest) + name
    return name


def sheet_xml(rows: list[list[Cell]], shared: list[str]) -> str:
    body = []
    for r, row in enumerate(rows, start=1):
        cells = []
        for c, cell in enumerate(row):
            if cell is None:
                continue
            ref = f"{_col(c)}{r}"
            kind = cell[0]
            if kind == "n":
                cells.append(f'<c r="{ref}"><v>{cell[1]}</v></c>')
            elif kind == "s":
                if cell[1] not in shared:
                    shared.append(cell[1])
                cells.append(f'<c r="{ref}" t="s"><v>{shared.index(cell[1])}</v></c>')
            elif kind == "i":
                cells.append(
                    f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escape(cell[1])}</t></is></c>'
                )
            elif kind == "dt":
                cells.append(f'<c r="{ref}" s="2"><v>{cell[1]}</v></c>')
            elif kind == "d":
                cells.append(f'<c r="{ref}" s="1"><v>{cell[1]}</v></c>')
            elif kind == "f":
                cells.append(f'<c r="{ref}"><f>{escape(cell[1])}</f><v>{cell[2]}</v></c>')
            elif kind == "b":
                cells.append(f'<c r="{ref}" t="b"><v>{cell[1]}</v></c>')
            elif kind == "e":
                cells.append(f'<c r="{ref}" t="e"><v>{escape(cell[1])}</v></c>')
            else:  # pragma: no cover
                raise ValueError(kind)
        body.append(f'<row r="{r}">{"".join(cells)}</row>')
    return f'<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="{NS}"><sheetData>{"".join(body)}</sheetData></worksheet>'


def build(
    sheets: list[list[list[Cell]]],
    *,
    date1904: bool = False,
    extra_workbook: str = "",
    sheet_names: list[str] | None = None,
    sheet_prefix: str = "",
    doctype: str = "",
) -> bytes:
    shared: list[str] = []
    sheet_parts = [sheet_xml(rows, shared) for rows in sheets]
    names = sheet_names or [f"Hoja{i}" for i in range(1, len(sheets) + 1)]
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        )
        pr = '<workbookPr date1904="1"/>' if date1904 else "<workbookPr/>"
        z.writestr(
            "xl/workbook.xml",
            f'<?xml version="1.0"?>{doctype}<workbook xmlns="{NS}" xmlns:r="{REL}">{pr}<sheets>'
            + "".join(
                f'<sheet name="{n}" sheetId="{i}" r:id="rId{i}"/>' for i, n in enumerate(names, 1)
            )
            + f"</sheets>{extra_workbook}</workbook>",
        )
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(
                f'<Relationship Id="rId{i}" Type="{REL}/worksheet" Target="{sheet_prefix}worksheets/sheet{i}.xml"/>'
                for i in range(1, len(sheets) + 1)
            )
            + "</Relationships>",
        )
        z.writestr("xl/styles.xml", STYLES)
        z.writestr(
            "xl/sharedStrings.xml",
            f'<?xml version="1.0"?><sst xmlns="{NS}">'
            + "".join(f'<si><t xml:space="preserve">{escape(s)}</t></si>' for s in shared)
            + "</sst>",
        )
        for i, part in enumerate(sheet_parts, 1):
            z.writestr(f"xl/worksheets/sheet{i}.xml", part)
    return out.getvalue()


HEADERS: list[Cell] = [("s", h) for h in ("Proveedor", "Order ID", "Fecha y hora")]


def simple(rows: list[list[Cell]], headers: list[Cell] | None = None, **kw: Any) -> bytes:
    return build([[headers or HEADERS, *rows]], **kw)
