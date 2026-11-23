"""Reads the single worksheet of an .xlsx file straight from its package (RF-02, RNF-13).

A spreadsheet library would hand numbers over as floats and lose the digits of the file. Here each
numeric cell keeps the raw text stored in the file, so `12.345` stays `12.345`. The reader never
evaluates a formula and never opens a macro; it reports a formula cell as such.

Whole-file rejections (corrupt, protected, several worksheets, a mandatory header missing, too
large, unsafe) raise `XlsxRejected` with one of the reasons of the approved contract.
"""

import io
import re
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal
from xml.etree import ElementTree as ET

from app.domain.rows import EMPTY, HEADERS, MANDATORY_HEADERS, Cell

# Maximum size of an uploaded file (P-06). There is no separate row limit.
MAX_FILE_BYTES = 10 * 1024 * 1024
# Guards against archives that expand far beyond their size (not a business limit).
MAX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
MAX_PARTS = 2000
MAX_RATIO = 1000

Reason = Literal["missing_required_header", "multiple_worksheets", "corrupt_or_protected_file"]

_OLE2 = bytes.fromhex("D0CF11E0A1B11AE1")  # an encrypted .xlsx is an OLE2 container, not a ZIP
_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_PKG_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
_REF = re.compile(r"^([A-Z]+)(\d+)$")

# Built-in number formats that show a date or a time.
_BUILTIN_DATE_FORMATS = frozenset(
    {14, 15, 16, 17, 18, 19, 20, 21, 22, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36}
    | {45, 46, 47, 50, 51, 52, 53, 54, 55, 56, 57, 58}
)


class XlsxRejected(Exception):
    """The whole file is rejected; `reason` is a value of the contract's rejection enum."""

    def __init__(self, reason: Reason, detail: str | None = None) -> None:
        super().__init__(detail or reason)
        self.reason: Reason = reason
        self.detail = detail


@dataclass(frozen=True)
class SourceRowCells:
    row_number: int  # as numbered in the spreadsheet
    cells: dict[str, Cell]  # field name -> cell, only recognized columns


@dataclass(frozen=True)
class Sheet:
    rows: list[SourceRowCells]


def read_xlsx(data: bytes) -> Sheet:
    """Parse the file. Only recognized columns are kept; blank rows are skipped."""
    if len(data) > MAX_FILE_BYTES:
        raise XlsxRejected("corrupt_or_protected_file", "El archivo supera el límite de 10 MB.")
    if data[:8] == _OLE2:
        raise XlsxRejected(
            "corrupt_or_protected_file",
            "El archivo está protegido con contraseña o no es un XLSX válido.",
        )
    try:
        package = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise XlsxRejected(
            "corrupt_or_protected_file", "El archivo no es un XLSX válido o está dañado."
        ) from None
    with package:
        _check_package_is_safe(package)
        try:
            return _read(package)
        except (ET.ParseError, KeyError, zipfile.BadZipFile, ValueError):
            raise XlsxRejected(
                "corrupt_or_protected_file", "El archivo está dañado y no se puede leer."
            ) from None


def _check_package_is_safe(package: zipfile.ZipFile) -> None:
    infos = package.infolist()
    unsafe = len(infos) > MAX_PARTS or sum(i.file_size for i in infos) > MAX_UNCOMPRESSED_BYTES
    unsafe = unsafe or any(
        i.file_size > 1024 * 1024 and i.file_size / max(i.compress_size, 1) > MAX_RATIO
        for i in infos
    )
    if unsafe:
        raise XlsxRejected("corrupt_or_protected_file", "El archivo no es seguro de procesar.")


def _xml(package: zipfile.ZipFile, name: str) -> bytes:
    raw = package.read(name)
    # OOXML parts never need a DTD; refusing it closes entity-expansion attacks.
    if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
        raise XlsxRejected("corrupt_or_protected_file", "El archivo no es seguro de procesar.")
    return raw


def _read(package: zipfile.ZipFile) -> Sheet:
    names = set(package.namelist())
    if "xl/workbook.xml" not in names:
        raise XlsxRejected("corrupt_or_protected_file", "El archivo no es un XLSX válido.")
    workbook = ET.fromstring(_xml(package, "xl/workbook.xml"))
    sheets = workbook.findall(f"{_MAIN}sheets/{_MAIN}sheet")
    if len(sheets) > 1:
        raise XlsxRejected("multiple_worksheets", f"El archivo tiene {len(sheets)} hojas.")
    if not sheets:
        raise XlsxRejected("corrupt_or_protected_file", "El archivo no tiene ninguna hoja.")
    properties = workbook.find(f"{_MAIN}workbookPr")
    date1904 = properties is not None and properties.get("date1904") in ("1", "true")
    part = _sheet_part(package, sheets[0].get(f"{_REL}id"), names)
    strings = _shared_strings(package, names)
    date_styles = _date_styles(package, names)

    header_columns: dict[int, str] = {}
    rows: list[SourceRowCells] = []
    for number, cells in _iter_rows(package, part):
        resolved = {
            column: _cell(raw, strings, date_styles, date1904) for column, raw in cells.items()
        }
        if not header_columns:
            if all(c.kind == "empty" for c in resolved.values()):
                continue  # empty rows before the header
            header_columns = _headers(resolved)
            continue
        by_field = {
            HEADERS[header_columns[col]]: cell
            for col, cell in resolved.items()
            if col in header_columns and cell.kind != "empty"
        }
        if by_field:  # a completely empty row is skipped
            rows.append(SourceRowCells(number, by_field))
    if not header_columns:
        raise XlsxRejected("missing_required_header", MANDATORY_HEADERS[0])
    return Sheet(rows)


def _headers(row: dict[int, Cell]) -> dict[int, str]:
    found: dict[int, str] = {}
    seen: set[str] = set()
    for column, cell in sorted(row.items()):
        if cell.kind == "text" and cell.text in HEADERS:  # exact match, extra headers ignored
            if cell.text in seen:
                raise XlsxRejected("missing_required_header", f"Encabezado repetido: {cell.text}")
            seen.add(cell.text)
            found[column] = cell.text
    for name in MANDATORY_HEADERS:
        if name not in seen:
            raise XlsxRejected("missing_required_header", name)
    return found


def _sheet_part(package: zipfile.ZipFile, rel_id: str | None, names: set[str]) -> str:
    if "xl/_rels/workbook.xml.rels" in names and rel_id:
        rels = ET.fromstring(_xml(package, "xl/_rels/workbook.xml.rels"))
        for rel in rels.findall(f"{_PKG_REL}Relationship"):
            if rel.get("Id") == rel_id:
                target = rel.get("Target") or ""
                path = target.lstrip("/") if target.startswith("/") else f"xl/{target}"
                if path in names:
                    return path
    raise XlsxRejected("corrupt_or_protected_file", "No se encuentra la hoja del archivo.")


def _text_of(element: ET.Element) -> str:
    """Text of a shared or inline string: every `t` except phonetic hints."""
    parts: list[str] = []
    for child in element:
        tag = child.tag.removeprefix(_MAIN)
        if tag == "t":
            parts.append(child.text or "")
        elif tag == "r":
            parts.extend(t.text or "" for t in child.findall(f"{_MAIN}t"))
    return "".join(parts)


def _shared_strings(package: zipfile.ZipFile, names: set[str]) -> list[str]:
    if "xl/sharedStrings.xml" not in names:
        return []
    root = ET.fromstring(_xml(package, "xl/sharedStrings.xml"))
    return [_text_of(si) for si in root.findall(f"{_MAIN}si")]


def _is_date_format(code: str) -> bool:
    cleaned = re.sub(r'"[^"]*"|\\.|\[[^\]]*\]|_.|\*.', "", code)
    return bool(re.search(r"[ymdhs]", cleaned, re.IGNORECASE)) and cleaned.lower() != "general"


def _date_styles(package: zipfile.ZipFile, names: set[str]) -> set[int]:
    """Indexes of the cell styles whose number format shows a date or time."""
    if "xl/styles.xml" not in names:
        return set()
    root = ET.fromstring(_xml(package, "xl/styles.xml"))
    custom = {
        int(f.get("numFmtId", "-1")): f.get("formatCode", "")
        for f in root.findall(f"{_MAIN}numFmts/{_MAIN}numFmt")
    }
    styles: set[int] = set()
    for index, xf in enumerate(root.findall(f"{_MAIN}cellXfs/{_MAIN}xf")):
        fmt = int(xf.get("numFmtId", "0"))
        if fmt in _BUILTIN_DATE_FORMATS or (fmt in custom and _is_date_format(custom[fmt])):
            styles.add(index)
    return styles


def _column_index(letters: str) -> int:
    value = 0
    for char in letters:
        value = value * 26 + (ord(char) - 64)
    return value - 1


@dataclass
class _Raw:
    kind: str | None
    style: int
    value: str | None
    inline: str | None
    formula: bool


def _iter_rows(package: zipfile.ZipFile, part: str) -> Iterator[tuple[int, dict[int, _Raw]]]:
    raw = _xml(package, part)
    counter = 0
    for _event, row in ET.iterparse(io.BytesIO(raw), events=("end",)):
        if row.tag != f"{_MAIN}row":
            continue
        counter = int(row.get("r") or counter + 1)
        cells: dict[int, _Raw] = {}
        position = 0
        for c in row.findall(f"{_MAIN}c"):
            ref = _REF.match(c.get("r") or "")
            position = _column_index(ref.group(1)) if ref else position
            v = c.find(f"{_MAIN}v")
            inline = c.find(f"{_MAIN}is")
            cells[position] = _Raw(
                kind=c.get("t"),
                style=int(c.get("s") or 0),
                value=None if v is None else (v.text or ""),
                inline=None if inline is None else _text_of(inline),
                formula=c.find(f"{_MAIN}f") is not None,
            )
            position += 1
        yield counter, cells
        row.clear()


def _cell(raw: _Raw, strings: list[str], date_styles: set[int], date1904: bool) -> Cell:
    if raw.formula:
        return Cell("formula")  # never evaluated, and its cached value is not trusted
    kind = raw.kind
    if kind == "inlineStr":
        return Cell("text", raw.inline) if raw.inline else EMPTY
    if raw.value is None or raw.value == "":
        return EMPTY
    if kind == "s":
        text = strings[int(raw.value)]
        return Cell("text", text) if text != "" else EMPTY
    if kind == "str":
        return Cell("text", raw.value)
    if kind == "b":
        return Cell("text", "TRUE" if raw.value == "1" else "FALSE")
    if kind == "e":
        return Cell("text", raw.value)
    if kind == "d":
        return Cell("datetime", when=datetime.fromisoformat(raw.value))
    # A number. A date format makes it a date or date-time; otherwise it keeps its raw digits.
    if raw.style in date_styles:
        moment = _from_serial(raw.value, date1904)
        if moment is not None:
            return Cell("datetime", when=moment)
    return Cell("number", raw.value)


def _from_serial(serial: str, date1904: bool) -> datetime | None:
    try:
        number = Decimal(serial)
    except ArithmeticError:
        return None
    days = int(number)
    seconds = round((number - days) * 86400)
    if date1904:
        base = datetime(1904, 1, 1)
    elif days >= 61:
        base = datetime(
            1899, 12, 30
        )  # Excel's 1900 system counts a 29 February 1900 that never was
    else:
        return None  # dates before March 1900 are not supported
    try:
        return base + timedelta(days=days, seconds=seconds)
    except OverflowError:
        return None
