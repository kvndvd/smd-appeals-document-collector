from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple, Union
import re
import zipfile
import xml.etree.ElementTree as ET

ALLOWED_COURT_CODES = {"CA4", "CA5", "CA6", "CA7", "CA8", "CA9", "CA11"}
REQUIRED_FIELDS = ("CaseNumber", "LocationID", "addDocURL")


class WorkbookReadError(ValueError):
    """Raised when the selected Excel workbook cannot be used by the app."""


@dataclass(frozen=True)
class CourtUrlRow:
    row_number: int
    case_number: str
    court_code: str
    add_doc_url: str


def _clean(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_header(value) -> str:
    """Normalize headers so CaseNumber, Case Number, case_number all match."""
    text = _clean(value).lower()
    return "".join(ch for ch in text if ch.isalnum())


def _column_letter(index: int) -> str:
    """Convert a zero-based column index to an Excel column letter."""
    index += 1
    letters = ""
    while index:
        index, rem = divmod(index - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def _column_index_from_cell_ref(cell_ref: str) -> int:
    """Return zero-based column index from an Excel cell reference, e.g. C12 -> 2."""
    letters = re.sub(r"[^A-Za-z]", "", cell_ref or "")
    if not letters:
        return 0
    value = 0
    for char in letters.upper():
        value = value * 26 + (ord(char) - ord("A") + 1)
    return value - 1


def _xml_text(element: Optional[ET.Element]) -> str:
    if element is None:
        return ""
    return "".join(element.itertext())


def _load_shared_strings(zf: zipfile.ZipFile) -> List[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    try:
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    except Exception:
        return []
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    values: List[str] = []
    for si in root.findall("m:si", ns):
        values.append(_xml_text(si))
    return values


def _first_sheet_path(zf: zipfile.ZipFile) -> str:
    """Find the workbook's first sheet XML path without loading openpyxl."""
    names = set(zf.namelist())
    if "xl/workbook.xml" not in names:
        raise WorkbookReadError("This Excel file is missing xl/workbook.xml and cannot be read.")
    if "xl/_rels/workbook.xml.rels" not in names:
        # Most simple files use sheet1.xml. Fall back only if rels is missing.
        if "xl/worksheets/sheet1.xml" in names:
            return "xl/worksheets/sheet1.xml"
        raise WorkbookReadError("This Excel file is missing workbook relationships and cannot be read.")

    ns = {
        "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
        "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    }
    workbook_root = ET.fromstring(zf.read("xl/workbook.xml"))
    first_sheet = workbook_root.find("m:sheets/m:sheet", ns)
    if first_sheet is None:
        raise WorkbookReadError("This workbook does not contain any visible worksheet.")
    rel_id = first_sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
    if not rel_id:
        raise WorkbookReadError("The first worksheet relationship could not be identified.")

    rels_root = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    target = None
    for rel in rels_root.findall("rel:Relationship", ns):
        if rel.attrib.get("Id") == rel_id:
            target = rel.attrib.get("Target")
            break
    if not target:
        raise WorkbookReadError("The first worksheet target could not be identified.")

    if target.startswith("/"):
        path = target.lstrip("/")
    elif target.startswith("xl/"):
        path = target
    else:
        path = "xl/" + target
    path = path.replace("//", "/")
    if path not in names:
        raise WorkbookReadError(f"The first worksheet XML file was not found inside the workbook: {path}")
    return path


def _cell_value(cell: ET.Element, shared_strings: List[str], ns: Dict[str, str]) -> str:
    cell_type = cell.attrib.get("t", "")

    if cell_type == "inlineStr":
        inline = cell.find("m:is", ns)
        return _clean(_xml_text(inline))

    value_element = cell.find("m:v", ns)
    value = _clean(value_element.text if value_element is not None else "")

    if cell_type == "s":
        try:
            return _clean(shared_strings[int(value)])
        except Exception:
            return ""
    if cell_type == "str":
        return value
    if cell_type == "b":
        return "TRUE" if value == "1" else "FALSE" if value == "0" else value
    return value


def _read_rows_from_xlsm_zip(path: Path) -> List[List[str]]:
    """
    Read worksheet values directly from the .xlsm zip/XML package.

    This intentionally avoids openpyxl's workbook feature parsing. Some SMD
    templates contain Excel filter metadata that can make openpyxl raise:
    'Value must be either numerical or a string containing a wildcard'.
    The bot only needs cell values, so XML reading is safer for this workflow.
    """
    try:
        with zipfile.ZipFile(path) as zf:
            shared_strings = _load_shared_strings(zf)
            sheet_path = _first_sheet_path(zf)
            root = ET.fromstring(zf.read(sheet_path))
    except zipfile.BadZipFile as exc:
        raise WorkbookReadError("This file is not a valid Excel .xlsm/.xlsx package. It may be corrupted or password-protected.") from exc
    except WorkbookReadError:
        raise
    except Exception as exc:
        raise WorkbookReadError(f"Could not read workbook XML. Details: {exc}") from exc

    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rows: List[List[str]] = []
    for row_element in root.findall(".//m:sheetData/m:row", ns):
        row_number_text = row_element.attrib.get("r")
        try:
            excel_row_number = int(row_number_text) if row_number_text else len(rows) + 1
        except ValueError:
            excel_row_number = len(rows) + 1
        while len(rows) < excel_row_number:
            rows.append([])
        row_values = rows[excel_row_number - 1]
        for cell in row_element.findall("m:c", ns):
            cell_ref = cell.attrib.get("r", "")
            col_index = _column_index_from_cell_ref(cell_ref)
            while len(row_values) <= col_index:
                row_values.append("")
            row_values[col_index] = _cell_value(cell, shared_strings, ns)
    return rows


def _header_map_from_values(first_row: List[str]) -> Tuple[Dict[str, int], List[str]]:
    mapping: Dict[str, int] = {}
    visible_headers: List[str] = []
    for index, cell_value in enumerate(first_row):
        header = _clean(cell_value)
        visible_headers.append(header)
        normalized = _normalize_header(header)
        if normalized:
            mapping[normalized] = index
    return mapping, visible_headers


def _find_column(headers: Dict[str, int], names: Iterable[str], fallback_index: Optional[int]) -> Optional[int]:
    for name in names:
        key = _normalize_header(name)
        if key in headers:
            return headers[key]
    return fallback_index


def workbook_diagnostics(xlsm_path: Union[str, Path]) -> str:
    """Return a short diagnostic summary for troubleshooting workbook load issues."""
    grouped = read_court_urls(xlsm_path)
    total = sum(len(rows) for rows in grouped.values())
    counts = ", ".join(f"{court}: {len(rows)}" for court, rows in grouped.items()) or "none"
    return f"Workbook OK. Usable rows: {total}. Court counts: {counts}."


def read_court_urls(xlsm_path: Union[str, Path]) -> Dict[str, List[CourtUrlRow]]:
    """
    Read an .xlsm workbook and group rows by available court code.

    Required data:
      - CaseNumber: case/docket number to log and use in the PDF filename.
      - LocationID: court code such as CA4, CA5, CA6. Usually column C.
      - addDocURL: PACER URL to open. Usually column K.

    The reader checks header names first and falls back to the known SMD Appeals
    template positions: CaseNumber=B, LocationID=C, addDocURL=K. It reads the
    workbook XML directly so Excel filter metadata cannot trigger openpyxl
    wildcard errors.
    """
    path = Path(xlsm_path).expanduser().resolve()
    if not path.exists():
        raise WorkbookReadError(f"Workbook not found: {path}")
    if path.suffix.lower() not in {".xlsm", ".xlsx"}:
        raise WorkbookReadError(f"Expected an .xlsm file, got: {path.name}")

    rows = _read_rows_from_xlsm_zip(path)
    if not rows:
        raise WorkbookReadError("The workbook sheet is empty. Row 1 must contain CaseNumber, LocationID, and addDocURL.")

    headers, visible_headers = _header_map_from_values(rows[0])

    # Header names are preferred; fallback indexes support the current SMD Appeals template.
    case_index = _find_column(headers, ["CaseNumber", "Case Number", "DocketNumber", "Docket Number"], 1)
    location_index = _find_column(headers, ["LocationID", "Location ID", "Court", "CourtCode", "Court Code"], 2)
    url_index = _find_column(headers, ["addDocURL", "Add Doc URL", "Document URL", "DocURL", "URL"], 10)

    missing = []
    if case_index is None:
        missing.append("CaseNumber")
    if location_index is None:
        missing.append("LocationID")
    if url_index is None:
        missing.append("addDocURL")
    if missing:
        shown_headers = ", ".join(h for h in visible_headers if h) or "(no headers found)"
        raise WorkbookReadError(
            "Missing required workbook column(s): "
            + ", ".join(missing)
            + ". Row 1 headers found: "
            + shown_headers
        )

    found: Dict[str, List[CourtUrlRow]] = {code: [] for code in sorted(ALLOWED_COURT_CODES)}
    unsupported_examples: List[str] = []
    blank_url_count = 0
    blank_case_count = 0
    scanned_rows = 0

    for row_number, row in enumerate(rows[1:], start=2):
        scanned_rows += 1
        case_number = _clean(row[case_index] if len(row) > case_index else "")
        location_id = _clean(row[location_index] if len(row) > location_index else "").upper().replace(" ", "")
        add_doc_url = _clean(row[url_index] if len(row) > url_index else "")

        if not any(_clean(value) for value in row):
            continue
        if not case_number:
            blank_case_count += 1
        if not add_doc_url:
            blank_url_count += 1
            continue
        if location_id not in ALLOWED_COURT_CODES:
            if location_id and len(unsupported_examples) < 8:
                unsupported_examples.append(location_id)
            continue

        found[location_id].append(
            CourtUrlRow(
                row_number=row_number,
                case_number=case_number,
                court_code=location_id,
                add_doc_url=add_doc_url,
            )
        )

    filtered = {court_code: rows for court_code, rows in found.items() if rows}
    if not filtered:
        details = [
            f"Scanned {scanned_rows} row(s).",
            f"Using columns: CaseNumber={_column_letter(case_index)}, LocationID={_column_letter(location_index)}, addDocURL={_column_letter(url_index)}.",
            f"Supported LocationID values are: {', '.join(sorted(ALLOWED_COURT_CODES))}.",
        ]
        if blank_url_count:
            details.append(f"Rows skipped because addDocURL was blank: {blank_url_count}.")
        if unsupported_examples:
            details.append(f"Unsupported LocationID example(s): {', '.join(sorted(set(unsupported_examples)))}.")
        if blank_case_count:
            details.append(f"Rows with blank CaseNumber: {blank_case_count}.")
        raise WorkbookReadError("No usable PACER rows were found. " + " ".join(details))

    return filtered


def select_courts_interactively(available: Dict[str, List[CourtUrlRow]]) -> List[str]:
    """Prompt the user to select court codes from the available workbook values."""
    if not available:
        return []

    print("\nAvailable court codes found in workbook:")
    for index, court_code in enumerate(available.keys(), start=1):
        print(f"  {index}. {court_code} ({len(available[court_code])} URL(s))")

    print("\nType court codes separated by commas, numbers separated by commas, or ALL.")
    print("Example: CA4,CA9 or 1,3")

    code_by_index = {str(index): code for index, code in enumerate(available.keys(), start=1)}

    while True:
        raw_selection = input("Select courts to open: ").strip()
        if not raw_selection:
            print("Please select at least one court code.")
            continue

        if raw_selection.upper() == "ALL":
            return list(available.keys())

        selected: List[str] = []
        invalid: List[str] = []
        for part in raw_selection.split(","):
            token = part.strip().upper()
            if not token:
                continue
            if token in code_by_index:
                selected.append(code_by_index[token])
            elif token in available:
                selected.append(token)
            else:
                invalid.append(token)

        if invalid:
            print(f"Invalid selection(s): {', '.join(invalid)}")
            continue

        if selected:
            # preserve order and remove duplicates
            return list(dict.fromkeys(selected))

        print("Please select at least one court code.")


def iter_selected_rows(
    grouped_rows: Dict[str, List[CourtUrlRow]],
    selected_courts: Iterable[str],
) -> Iterable[CourtUrlRow]:
    for court_code in selected_courts:
        yield from grouped_rows.get(court_code, [])
