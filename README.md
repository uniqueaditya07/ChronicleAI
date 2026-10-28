# ChronicleAI

**AI-assisted search and analysis of text-based digital evidence.**

ChronicleAI is a college project for organizing case records, finding information across text files, and checking AI-assisted findings against their original sources. Its central principle is **evidence is not inference**: source text, documented observations, possible interpretations, and unanswered questions remain distinct.

The local evidence tools work without an API key. Optional Gemini analysis and case chat add cited explanations while retaining case ownership and line-level reference checks.

## Features

- **Cases:** create, inspect, search, edit, track status, and view statistics.
- **TXT evidence:** preserve original bytes, record SHA-256 hashes, reject duplicates within a case, and index 1-based lines. Supports UTF-8/UTF-8 BOM with a 5 MB limit per file.
- **Integrity checks:** compare stored bytes with recorded hashes without changing originals.
- **Search and inspection:** case-scoped literal substring search, highlighted matches, and a paginated Evidence Inspector. Citations load their target page, including lines beyond 2,000.
- **Entities:** local spaCy named entity extraction with source-line provenance.
- **AI analysis:** summary, documented observations, possible interpretations, and unresolved questions. Strict JSON/type/Unicode validation and reference quarantine protect the response boundary.
- **Case chat:** evidence-grounded questions/follow-ups, clickable citations, unsupported-answer notices, and scoped temporary conversation state.
- **Timeline:** chronological explicit dated statements, source citations, and separate ambiguous/incomplete/invalid dates without invented ordering.
- **Reports:** downloadable HTML with case details, inventory, recorded/computed hashes, analysis, timeline, questions, and linked excerpts. Open in a normal browser to print or save as PDF.

## Architecture and stack

```text
React / Vite browser UI
        | same-origin /api proxy during development
FastAPI application
        |-- SQLite / SQLAlchemy: cases, evidence metadata, indexed lines
        |-- Disk vault: original TXT bytes
        |-- spaCy: local English named entity extraction
        `-- Google Gemini: optional analysis and case chat
```

The backend owns case scoping, indexing, integrity, and citation validation. Frontend request identity and cancellation guards prevent stale case, file, and page responses from updating a newer view.

**Stack:** Python 3.12, FastAPI, SQLAlchemy, SQLite, spaCy, Google GenAI SDK, React 19, Vite 8, pytest, and Node's built-in test runner. Backend versions are pinned in `backend/requirements.txt`; frontend resolution is recorded in `frontend/package-lock.json`.

## Prerequisites

- Python **3.12**, Git, and Node.js **22.12+**. Node 24 was verified; Vite also supports Node 20.19+ in the 20.x line.
- Internet for initial dependency/model downloads. Gemini additionally requires an API key, available model access, and quota.
- These commands use Windows PowerShell. Windows was verified; other operating systems have not been manually verified.

## Installation and startup

Clone the repository and enter its root. No database or original investigation records are supplied. Backend startup creates an empty database automatically.

### Backend

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m spacy download en_core_web_sm
```

The spaCy model is a separate download, not an entry in `requirements.txt`. Verification used `en_core_web_sm` 3.8.0. If it is missing, entity extraction reports a controlled error; search and source inspection remain usable.

For optional AI features, set the key in this backend terminal. Replace the placeholder locally; never commit a real key or put it in a frontend `VITE_*` variable.

```powershell
$env:GEMINI_API_KEY = "<YOUR_GEMINI_API_KEY>"
# Optional: omit this variable to use the application's default.
$env:GEMINI_MODEL = "gemini-3.5-flash-lite"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

For local-only tools, omit the two environment commands and run the same server command. Health: `http://127.0.0.1:8000/api/health`. Interactive API documentation: `http://127.0.0.1:8000/docs`.

### Frontend

In a second terminal, from the repository root:

```powershell
cd frontend
npm ci
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Open `http://127.0.0.1:5173`. Vite proxies `/api` to port 8000. Both processes must run. Keep them on loopback: the application does not provide authentication.

## Environment configuration

`.env.example` documents variable names but is **not loaded automatically**. Set variables in the backend process environment and restart it after changes.

| Variable | Default / purpose |
|---|---|
| `GEMINI_API_KEY` | Optional key for analysis/chat; `GOOGLE_API_KEY` is an alternative. |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite`; an explicit environment value takes precedence. |
| `GEMINI_MAX_CONTEXT_CHARS` | `100000` indexed evidence characters; over-budget cases fail safely instead of truncating. |
| `DATABASE_URL` | SQLite file at `backend/chronicle.db`. Use an absolute `sqlite:///...` URL for disposable runs. |
| `CHRONICLE_STORAGE_DIR` | `backend/storage/evidence`; override with an absolute path for disposable runs. |

Gemini uses the Developer API `v1beta`, JSON output at temperature 0.2, a 60-second SDK/server timeout, and a 75-second browser abort. Errors are sanitized. Metadata listing does not guarantee generation access or quota.

AI requests send the selected case's indexed evidence to Google. Use only evidence you are authorized to send. This release's demo/test fixtures are fictional; original investigation records and historical case reports are excluded.

## Testing

### Backend: use a disposable copy

Tests create databases/storage, and some fixtures clean their own test paths. Do not run them against an investigation workspace. After installing dependencies, run this from the repository root. It copies application/test code, clears inherited API credentials, and uses the existing virtual environment. The disposable directory is removed after the subprocess exits.

```powershell
$python = (Resolve-Path backend/.venv/Scripts/python.exe).Path
@"
import os, pathlib, shutil, subprocess, sys, tempfile
repo = pathlib.Path.cwd()
with tempfile.TemporaryDirectory(prefix="ChronicleAI-tests-") as directory:
    root = pathlib.Path(directory)
    for name in ("app", "tests"):
        shutil.copytree(repo / "backend" / name, root / name,
                        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "test_storage*", "test_*storage*"))
    temporary = root / "tmp"
    temporary.mkdir()
    env = os.environ.copy()
    for key in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "PYTHONPATH", "PYTEST_ADDOPTS", "PYTEST_PLUGINS"):
        env.pop(key, None)
    env.update(DATABASE_URL="sqlite:///" + (root / "application.db").as_posix(),
               CHRONICLE_STORAGE_DIR=str(root / "evidence"),
               TEMP=str(temporary), TMP=str(temporary), TMPDIR=str(temporary),
               PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", GEMINI_MODEL="gemini-3.5-flash-lite",
               GEMINI_MAX_CONTEXT_CHARS="100000")
    subprocess.run([sys.executable, "-B", "-m", "pytest", "tests", "-v",
                    "--basetemp", str(root / "pytest-temp"),
                    "-o", "cache_dir=" + str(root / "pytest-cache")],
                   cwd=root, env=env, check=True)
"@ | & $python -B -
```

Existing Gemini regression tests use mocks and need no live key. The release was verified with **270 backend tests**, covering case isolation, ingestion, search, entities, strict analysis/Unicode validation, chat, timeline uncertainty, reports, and model overrides.

### Frontend

```powershell
cd frontend
npm test
npm run lint
npm run build
```

Verification passed **128 frontend tests**, lint, and the production build. One existing React hook warning remains. The dependency-free harness executes production handlers with simulated hooks and controlled request ordering; it is not a rendered-browser test. Ignored `frontend/dist` contains generated static files, not a standalone API deployment.

## Presentation walkthrough

1. Create a case and upload `demo/presentation-evidence.txt`. Its first line explicitly identifies every person, organization, and event as fictional.
2. Show the inventory/hash, open the Inspector, and verify cryptographic integrity.
3. Search for `receipt`, inspect highlighted source lines, and explore entity citations.
4. Open the timeline: explicit dates are ordered; `03/04/2026` has ambiguous day/month order, and `October 2026` has no invented day.
5. With Gemini configured, generate analysis and inspect observations, interpretations, questions, and citations. Ask chat what the evidence establishes about the receipt and who approved the transfer.
6. Download the report after analysis, open its HTML file, follow excerpt links, and choose **Print / Save as PDF**. Without analysis, AI sections are explicitly unavailable; inventory/timeline export still works.
7. Switch cases to demonstrate isolation. Chat clears when leaving the case; only the last six completed user questions provide follow-up context, never evidence.

The default model passed two controlled live synthetic checks: minimal text in 2.293 seconds and case analysis in 3.878 seconds upstream, with all 16 analysis citations valid and snippets matching. Live chat was not called in that two-request budget; shared analysis/chat model behavior is mock-tested.

Earlier browser verification used synthetic data and mocked Gemini for case creation/editing, upload, integrity, search, entities, chat isolation, timeline citations, Inspector navigation beyond line 2,000, and report download. Browser restrictions prevented visual print-preview verification; rehearse printing in your normal browser.

## Limitations

- Local, single-user college project: no authentication, access roles, public hosting setup, or forensic custody certification.
- TXT only: no PDF, DOCX, CSV, OCR, image, audio, or video ingestion.
- SHA-256 detects changed bytes; it does not provide operating-system write protection or certify evidence origin.
- Citation validation checks ownership and indexed coordinates, not semantic truth. Review every AI claim against its sources.
- English NER/date patterns can miss entities/date mentions. Timeline entries are dated source statements, not independently verified occurrences or inferred relationships.
- Chat and analysis are temporary UI state, not persisted records. New evidence invalidates old UI answers; generate the analysis you want before exporting.
- Large-case latency, provider access, quota, and capacity vary. Evidence exceeding the context budget is rejected without truncation.

## Release contents and license

The release includes source, tests, configuration examples, documentation, static assets, and a fictional demo. Keep databases, vault files, credentials, exports, logs, and historical investigation reports out of Git.

A project license has not yet been selected; no license file is included. Third-party dependencies retain their own licenses.
