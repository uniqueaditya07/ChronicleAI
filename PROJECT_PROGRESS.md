# ChronicleAI — Release Status

This document describes the current college presentation release. Historical investigation reports, original databases, vault files, and evidence-derived case details are excluded.

## Implemented scope

| Area | Current behavior |
|---|---|
| Cases | Create, list, search, inspect, edit, status tracking and statistics. |
| Evidence | UTF-8 TXT ingestion, original-byte storage, SHA-256, per-case duplicate rejection and indexed lines. |
| Retrieval | Case-scoped literal search and Inspector pages of 2,000 lines with target-aware citation navigation. |
| Entities | Local English spaCy NER with case-scoped line provenance. |
| Analysis | Four sections, strict provider JSON/type/Unicode validation, case citation allowlisting and claim quarantine. |
| Chat | Evidence-grounded questions/follow-ups, unsupported-answer notices, validated citations and scoped temporary history. |
| Timeline | Chronological explicit dates, source lines and separate ambiguous/incomplete/invalid dates. |
| Reports | HTML download with inventory, integrity, analysis, timeline, questions, linked excerpts and print control. |
| Reliability | Request identity/cancellation guards for case, file, page, analysis, chat, timeline and report operations. |

## Verification

- **Backend:** 270 tests passed in isolation; regression Gemini clients mocked.
- **Frontend:** 128 production-handler tests passed; lint and production build passed.
- **Known warnings:** one existing React hook warning and a Starlette/AnyIO test-client deprecation warning.
- **Live Gemini:** two controlled synthetic checks with `gemini-3.5-flash-lite` succeeded: 2.293 seconds for minimal text and 3.878 seconds upstream for small case analysis. All 16 citations referenced correct files/lines and had matching snippets, with no quarantine warnings.
- **Chat:** shared model/default override and validation paths are mock-tested. No additional live chat request was made in the two-request budget.
- **Browser:** synthetic/mocked verification covered case creation/editing, upload, integrity, search, entities, analysis, chat isolation, timeline citations, Inspector line 2,501, and report download. Visual print-preview needs a normal-browser rehearsal.

## Configuration

The default is `gemini-3.5-flash-lite`; `GEMINI_MODEL` remains an override. Credentials belong in the backend environment; `.env` files are not loaded automatically. Generation access can differ from metadata listings.

The SDK uses Gemini Developer API `v1beta`, JSON at temperature 0.2 and a 60-second SDK/server timeout. The frontend aborts analysis/chat after 75 seconds. No explicit output-token/thinking limit is set. Indexed evidence has a configurable 100,000-character budget and is never silently truncated.

## API surface

- `GET /api/health`
- `POST /api/cases`, `GET /api/cases`, `GET /api/cases/stats`
- `GET /api/cases/{case_id}`, `PATCH /api/cases/{case_id}`
- `POST /api/cases/{case_id}/evidence`, `GET /api/cases/{case_id}/evidence`
- `GET /api/cases/{case_id}/evidence/{evidence_id}`
- `GET /api/cases/{case_id}/evidence/{evidence_id}/lines`
- `GET /api/cases/{case_id}/evidence/{evidence_id}/verify`
- `GET /api/cases/{case_id}/search`
- `GET /api/cases/{case_id}/entities`, `GET /api/cases/{case_id}/entities/summary`
- `POST /api/cases/{case_id}/analysis`, `POST /api/cases/{case_id}/chat`
- `GET /api/cases/{case_id}/timeline`, `POST /api/cases/{case_id}/report`

## Boundaries and presentation readiness

The local evidence tools work without Gemini. This college project has no authentication, user roles, cloud deployment, OCR, non-TXT ingestion, vector database, inferred relationship graph, or forensic certification.

Reference validation does not establish semantic truth. Timeline dates are source mentions, not independently verified events. Preserve evidence/inference separation throughout the demonstration.

Use `demo/presentation-evidence.txt` or other explicitly fictional fixtures. Release test narratives are constructed fictional data. Rehearse the documented workflow and check provider quota; large-case latency and capacity remain variable.

## Publication boundary

This release uses an independent `presentation-ready` history. It does not inherit internal investigation reports or original development commits. The existing public `main` history remains separate and must not be merged or force-pushed over by release preparation.
