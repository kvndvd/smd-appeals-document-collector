# Counsel Collector - PACER Stage 1

This is the refined PyQt5 baseline.

## What this stage does

- Reads an `.xlsm` workbook.
- Reads `CaseNumber`, `LocationID`, and `addDocURL`.
- Detects supported courts: `CA4`, `CA5`, `CA6`, `CA7`, `CA8`, `CA9`, and `CA11`.
- Lets the user select which detected courts to test.
- Uses the PACER ID, password, and client code typed in the GUI.
- Saves PACER ID, password, and client code when **Save credentials** is checked.
- Opens each selected row URL one by one.
- Writes debug/status text after each URL opens successfully, then proceeds to the next row.
- Does not download, scrape, or collect documents yet.

## Run

```bash
pip install -r requirements.txt
python main.py
```

## Notes

The GUI path no longer uses a config file for PACER credentials.
