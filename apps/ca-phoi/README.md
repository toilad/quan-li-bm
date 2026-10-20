# Tải phôi California

A separate desktop app (shortcut "Tải phôi California" on the Desktop). It shares nothing with "Đọc phôi", Postgres, OCR or the Google Sheet.

The daily flow:
1. Pick up to 5 keywords with **Random 5** or by ticking them.
2. **Start Search** runs the keywords one at a time. It stops once 60 targets are found.
3. **Download 50** downloads one PDF at a time. It stops at 50 successful PDFs.

## Target filter
- LLC only (CA and Out of State).
- Active Only, on by default.
- Initial Filing Date in 2007–2013: the forms the PDF reader handles. 2014–2016 filings (REV 01/2014 and later) all ended up in review.
- Name of at most 30 characters (adjustable).
- Name ends in `LLC` or `, LLC`.
- Deduplicated by Entity Number.
- Converted entities are dropped. Their number year differs from the filing year, or their history holds a Conversion; their initial filing is an LLC-1A, not an original LLC-1.

## Download rule
`RECORD_NUM` → `/api/History/business/{RECORD_NUM}` → the single "Initial Filing" item whose number equals the Entity Number → `DOWNLOAD_LINK`.
- A domestic LLC gives LLC-1; a foreign LLC gives LLC-5.
- The app never substitutes a Statement of Information.
- It never overwrites a file. A different company with the same name is saved as `<Name> - <EntityNo>.pdf`.

## Browser
The app uses the installed Edge with its own profile, `%LOCALAPPDATA%\CaPhoi\edge-profile`, controlled through Playwright over CDP on port 9333. No Chromium is downloaded.

When Bizfile asks for a CAPTCHA, the app pauses and shows **CẦN XÁC MINH**. The owner ticks the check in Edge, and the app resumes at the same step.

## Data
History lives in `%LOCALAPPDATA%\CaPhoi\ca_phoi.db` (SQLite): keywords, targets and downloads. PDFs are only stored in the folder you choose.

## Development
```
.venv\Scripts\python.exe -m unittest discover -s tests -t .
.venv\Scripts\python.exe -m tests.regression_live "<out folder>" "<test db>"   # live, needs a verified Edge
```
