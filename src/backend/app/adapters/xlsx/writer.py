"""Writes the excluded-rows report as an .xlsx the user can correct and upload again (RF-20).

The columns of the file come first with the same headers the import reads, then three extra
columns (row of the original, class and reason) that the import ignores. Amounts are written as
numeric cells when they are numbers, so the digits survive a round trip; everything else is text.
"""

import io
import re
import zipfile
from collections.abc import Sequence
from xml.sax.saxutils import escape

from app.services.preview import PreviewRow

_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_AMOUNT = re.compile(r"^-?\d+(\.\d+)?$")

COLUMNS: tuple[tuple[str, str, bool], ...] = (
    ("Proveedor", "provider", False),
    ("Order ID", "orderId", False),
    ("Fecha y hora", "when", False),
    ("Sucursal", "branch", False),
    ("Importe a reclamar", "claimAmount", True),
    ("Costos de proveedor", "providerCosts", True),
    ("Total", "total", True),
    ("Descripción", "description", False),
)
EXTRA = ("Fila original", "Clase", "Motivo")
CLASS_LABELS = {"duplicate": "Duplicada", "conflict": "En conflicto", "error": "Con error"}


def _letter(index: int) -> str:
    name = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        name = chr(65 + rest) + name
    return name


def _text(ref: str, value: str) -> str:
    return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escape(value)}</t></is></c>'


def _when(fields: dict[str, str | None]) -> str | None:
    day, clock = fields.get("incidentDate"), fields.get("incidentTime")
    if day and clock:
        return f"{day} {clock}"
    return day


def build_excluded_report(rows: Sequence[PreviewRow]) -> bytes:
    lines: list[list[tuple[str, bool]]] = [
        [(h, False) for h, _, _ in COLUMNS] + [(h, False) for h in EXTRA]
    ]
    for row in rows:
        values = {**row.fields, "when": _when(row.fields)}
        cells = [(values.get(key) or "", numeric) for _, key, numeric in COLUMNS]
        cells += [
            (str(row.row_number), False),
            (CLASS_LABELS.get(row.row_class, row.row_class), False),
            (row.reason or "", False),
        ]
        lines.append(cells)

    body: list[str] = []
    for r, cells in enumerate(lines, start=1):
        out = []
        for c, (value, numeric) in enumerate(cells):
            ref = f"{_letter(c)}{r}"
            if value == "":
                continue
            if r > 1 and numeric and _AMOUNT.match(value):
                out.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                out.append(_text(ref, value))
        body.append(f'<row r="{r}">{"".join(out)}</row>')

    sheet = (
        f'<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="{_NS}">'
        f"<sheetData>{''.join(body)}</sheetData></worksheet>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            "</Types>",
        )
        z.writestr(
            "_rels/.rels",
            '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Id="rId1" Type="{_REL}/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        )
        z.writestr(
            "xl/workbook.xml",
            f'<?xml version="1.0"?><workbook xmlns="{_NS}" xmlns:r="{_REL}"><sheets>'
            '<sheet name="Filas excluidas" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Id="rId1" Type="{_REL}/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        )
        z.writestr("xl/worksheets/sheet1.xml", sheet)
    return buffer.getvalue()
