# ChronicleAI — Current Project State

> This document maintains the live state of the project for engineers and AI coding sessions.

---

## 1. Executive Summary

- **Current Phase**: Phase 1 — Evidence Ingestion
- **Current Milestone**: Milestone 1.1 — Deterministic Extraction Engine Complete
- **Overall Status**: Phase 1 objectives completed; ready for Phase 2 authorization.
- **Last Updated**: 2026-08-18T01:05:00+05:30

---

## 2. Work Completed

### Phase 0 Foundation
- [x] Initialized Git repository and environment configuration templates (`.gitignore`, `.env.example`).
- [x] Produced complete 47-section Master Specification (`docs/MASTER_SPECIFICATION.md`).
- [x] Established FastAPI backend structure with modular configuration (`app/config.py`), structured logging (`app/logging_config.py`), database engine (`app/database.py`), and unified error handling (`app/main.py`).
- [x] Configured SQLite database with WAL journal mode and foreign key enforcement.
- [x] Initialized Alembic database migration pipeline with baseline `cases` table.
- [x] Implemented `/api/v1/health` and `/api/v1/cases` endpoints.
- [x] Created automated test suite with in-memory SQLite fixture and 8 passing unit/integration tests.
- [x] Initialized React 19 + TypeScript + Vite + Tailwind CSS v4 frontend.
- [x] Implemented frontend application shell with live backend health telemetry and interactive Case creation widget.
- [x] Documented Architecture Decision Records (`ADR-001`, `ADR-002`, `ADR-003`).

### Phase 1 Evidence Ingestion
- [x] Created `Source` and `SourceChunk` models with robust Alembic migrations safely stamping Phase 0.
- [x] Built `StorageService` and `FileValidator` for secure, deterministic file persistence and hashing.
- [x] Developed `BaseParser` interface and `ParserRegistry`.
- [x] Implemented concrete parsers for PDF (PyMuPDF), DOCX (python-docx), CSV (pandas), JSON, TXT, and LOG.
- [x] Integrated `IngestionService` coordinating upload validation, persistence, parsing, and DB chunk storage.
- [x] Built FastAPI `POST /sources` and `GET /sources/{id}/chunks` endpoints and integration tests.
- [x] Created React `EvidenceManager`, `SourceUploadModal`, `SourceList`, and `ChunkViewerModal` integrated into App shell.

---

## 3. Current Work

- Verifying Phase 1 complete functionality.
- Staging and committing Phase 1 codebase.
- Awaiting authorization to begin Phase 2 (Extraction Engine).

---

## 4. Next Task

- **Phase 2: Extraction Engine**
  - Integrate Google GenAI SDK (Gemini).
  - Implement Pydantic schema validation boundary for AI outputs.
  - Construct prompt templates for Entities, Events, and Claims extraction.
  - Implement chunk-by-chunk deduction orchestrator.
  - Develop `ExtractionViewer` UI for reviewing pending deductions.

---

## 5. Architectural Constraints & Invariants

1. **EVIDENCE ≠ INFERENCE**: The system must never present an AI deduction as an uncorroborated fact.
2. **Provenance Preservation**: All entities, events, claims, and timeline items must link back to source chunks.
3. **Structured AI Outputs**: All LLM calls must use Pydantic schemas; raw AI output must be validated prior to database persistence.
4. **No Direct DB Access by LLM**: The AI layer receives text and produces structured JSON; services validate and persist.
5. **Deterministic Parsers**: Document parsing into chunks is 100% deterministic and runs without calling the LLM.

---

## 6. Important Decisions Record

- **ADR-001**: Adopt Modular Monolith architecture pattern.
- **ADR-002**: Use SQLite as initial database with SQLAlchemy 2.0 and Alembic.
- **ADR-003**: Use Tailwind CSS v4 and construct a custom React timeline component.

---

## 7. Things That Must Not Be Broken

- FastAPI health check endpoint contract (`/api/v1/health`).
- SQLAlchemy Base model timestamp mixin (`id` UUID + UTC `created_at` / `updated_at`).
- Alembic offline & online migration compatibility (`render_as_batch=True`).
- Tailwind CSS v4 build setup in Vite (`@tailwindcss/vite`).
- Backend unit & integration test suite (`pytest`).

---

## 8. Known Issues / Technical Debt

- *None in Phase 0.* All backend tests and frontend builds pass cleanly.
