# SMD Appeals Document Collector

This package is the current project baseline.

## Current behavior

- Keeps the customized two-card PyQt5 GUI layout.
- The user-facing status area now shows short process messages only.
- Full technical logs are saved to the run output folder.
- Each run creates a timestamped output folder beside the selected workbook:

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

## Troubleshooting

Use the status label for quick progress while the app runs. For detailed debugging, open the timestamped output folder and review the `appeals-collection-*.log` file.
