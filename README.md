# SMD Appeals Document Collector - PACER Order PDF Collection

This PyQt5 app reads the SMD Appeals `.xlsm` workbook, opens the selected PACER `addDocURL` rows, and downloads PDF documents where the document table description contains `Order` or `Orders`.

## Workbook wildcard error fix

This version fixes the workbook error:

```text
Value must be either numerical or a string containing a wildcard
```

That error is caused by Excel filter metadata in the workbook. Some versions of `openpyxl` try to parse those saved filters and fail before the app can read the rows. The bot does not need Excel filters; it only needs cell values. This version reads the `.xlsm` XML directly, bypassing that filter metadata.

## Workbook requirements

The workbook should have row 1 headers for these fields:

- `CaseNumber`
- `LocationID`
- `addDocURL`

The reader also supports common header spacing variants and falls back to the SMD Appeals template layout:

- Column B: `CaseNumber`
- Column C: `LocationID`
- Column K: `addDocURL`

Supported `LocationID` values are: `CA4`, `CA5`, `CA6`, `CA7`, `CA8`, `CA9`, `CA11`.

## Output format

PDFs are saved under:

```text
Bot_Appeals_Collection_<YYYY-MM-DD>/<LocationID>/LDC_SMD_<CaseNumber>_PCQ.pdf
```

Example:

```text
Bot_Appeals_Collection_2026-06-21/CA7/LDC_SMD_25-2099_PCQ.pdf
```

## Troubleshooting Workbook Error

If the GUI shows `Workbook Error`, check these first:

1. Make sure the file is a real `.xlsm` workbook.
2. Make sure the workbook is not password-protected or corrupted.
3. Make sure row 1 has `CaseNumber`, `LocationID`, and `addDocURL`, or keep the standard template layout B/C/K.
4. Make sure `LocationID` contains supported values such as `CA5` or `CA7`, not `C5`, `C7`, or `CA 7`.
5. Make sure `addDocURL` is not blank.

You can test the workbook from Command Prompt in the app folder:

```bat
python -c "from courtWorkbook import workbook_diagnostics; print(workbook_diagnostics(r'C:\path\to\SMD Appeals Template.xlsm'))"
```

For the workbook you uploaded, the expected result is:

```text
Workbook OK. Usable rows: 18. Court counts: CA5: 4, CA7: 14.
```
