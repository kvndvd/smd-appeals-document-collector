# SMD Appeals Document Collector

This package is the current project baseline.

## Current behavior

- Keeps the customized two-card PyQt5 GUI layout.
- Supports the original Excel template (`.xlsm` / `.xlsx`) with:
  - `CaseNumber`
  - `LocationID`
  - `addDocURL`
- Supports the CT request CSV template (`.csv`) with:
  - `CaseKey`
  - `DocURL`
- For CSV files, `CaseKey` is split into `CaseNumber` and `LocationID` using the final underscore:

```text
25-60278_CA5 -> CaseNumber: 25-60278, LocationID: CA5
```

- The user-facing status area shows short process messages only.
- Full technical logs are saved to the run output folder.
- Each run creates a timestamped output folder beside the selected template:

```text
Bot_Appeals_Collection_<YYYY-MM-DD>-<HHMMSSAM/PM>
```

Example:

```text
Bot_Appeals_Collection_2026-06-23-041522PM
```

- The full log file is saved inside that output folder:

```text
appeals-collection-<YYYY-MM-DD>-<HHMMSSAM/PM>.log
```

Example:

```text
appeals-collection-2026-06-23-041522PM.log
```

- Downloaded PDFs still follow the existing court/case naming convention inside the output folder.

## Running

```bash
pip install -r requirements.txt
python main.py
```

## Troubleshooting template reading

For Excel templates, verify row 1 contains `CaseNumber`, `LocationID`, and `addDocURL`.

For CSV templates, verify row 1 contains `CaseKey` and `DocURL`, and each `CaseKey` uses this format:

```text
<CaseNumber>_<LocationID>
```

Supported `LocationID` values are:

```text
CA4, CA5, CA6, CA7, CA8, CA9, CA11
```

Use the status label for quick progress while the app runs. For detailed debugging, open the timestamped output folder and review the `appeals-collection-*.log` file.
