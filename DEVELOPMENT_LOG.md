# Development Log

This document records the chronological engineering diary and technical decision history of ChronicleAI.

---

## 2026-08-18 — Phase 1: Evidence Ingestion

### Objectives
- Implement deterministic ingestion pipelines for multiple evidence formats (PDF, DOCX, TXT, CSV, JSON, LOG).
- Establish the `Source` and `SourceChunk` models and ensure robust file persistence.
- Develop the Ingestion Orchestrator to route files through validators, storage, and parsers.
- Build the React Evidence Management UI to support uploads and chunk inspection.
- Strictly adhere to the invariant: "EVIDENCE ≠ INFERENCE".

### Key Decisions Made
1. **Parser Registry**: Implemented a dynamic `ParserRegistry` allowing modular parser extension for various file types.
2. **Deterministic Chunking**: Replaced complex chunking with strict, rule-based extraction tailored to each format (e.g. paragraph-level for TXT/DOCX, row-level for CSV/JSON).
3. **Reconciliation vs Recreation**: Handled a database mismatch securely by explicitly stamping Alembic state rather than destroying previous DB contents, ensuring persistence of Phase 0 state.
4. **React Component State**: Chose to keep `EvidenceManager` within the core `App.tsx` shell using conditional rendering, prioritizing velocity and layout consistency for Phase 1.

### Outcomes
- Evidence Ingestion APIs (`POST /cases/{id}/sources`) and DB migrations correctly built and tested.
- Frontend successfully integrated with Source list rendering, Upload modals, and an evidence chunk inspector.
- All integration tests passing.

---

## 2026-08-17 — Phase 0: Project Foundation Initialization

### Objectives
- Establish the technical, architectural, and documentation foundation for ChronicleAI according to the Master Specification.
- Ensure full-stack connectivity between FastAPI backend and React + TypeScript + Tailwind CSS v4 frontend.
- Establish database persistence with SQLite, SQLAlchemy 2.0 ORM, and Alembic migrations.
- Implement automated testing and documentation frameworks before proceeding to feature phases.

### Key Decisions Made
1. **Modular Monolith**: Adopted modular backend architecture using FastAPI and service-layer abstraction rather than distributed microservices to maintain zero operational friction while preserving clean boundaries.
2. **Tailwind CSS v4 Integration**: Configured `@tailwindcss/vite` plugin with `@import "tailwindcss"` in `index.css`, avoiding legacy config bloat while retaining high performance.
3. **Custom Timeline Strategy**: Confirmed that a custom React timeline component will be built in Phase 3 rather than introducing rigid third-party timeline libraries.
4. **SQLite WAL Mode & Foreign Keys**: Enforced SQLite PRAGMA configuration (`PRAGMA foreign_keys=ON`, `PRAGMA journal_mode=WAL`) upon connection to guarantee transactional integrity and concurrent read support.

### Implementation Details
- **Backend**:
  - `backend/app/config.py`: Pydantic `BaseSettings` for environment variables, paths, and CORS.
  - `backend/app/logging_config.py`: Application-wide structured logging.
  - `backend/app/database.py`: Engine, `SessionLocal`, `Base` declarative model, `TimestampMixin` with UUID generator.
  - `backend/app/models/case.py`: Case ORM entity representing investigation containers.
  - `backend/app/schemas/`: Pydantic request/response validation for health and case entities.
  - `backend/app/api/`: REST endpoints `/api/v1/health` and `/api/v1/cases`.
  - `backend/app/main.py`: FastAPI app instance with lifespan manager, CORS middleware, and unified error handling.
  - `backend/alembic/`: Alembic configuration and initial migration `60b414519da9_create_cases_table.py`.
- **Frontend**:
  - `frontend/src/api/client.ts`: Typed API client for `/api/v1/health` and `/api/v1/cases`.
  - `frontend/src/components/layout/`: AppLayout, TopBar (showing live backend health & DB status), Sidebar (phased navigation).
  - `frontend/src/App.tsx`: Interactive shell with system telemetry and live Case persistence test widget.
  - `frontend/vite.config.ts`: Tailwind v4 plugin, path aliases, API proxy.

### Tests Executed
- **Backend Tests (`pytest -v`)**:
  - `tests/unit/test_config.py`: Verifies default configuration values and directory creation.
  - `tests/unit/test_database.py`: Verifies SQLite in-memory session, table creation, and Case persistence.
  - `tests/integration/test_health.py`: Verifies `/` and `/api/v1/health` responses and database connectivity flag.
  - `tests/integration/test_cases.py`: Full CRUD test coverage for Case creation, listing, updating, and deletion.
  - *Result*: 8 passed in 0.21s.
- **Frontend Build (`npm run build`)**:
  - TypeScript type check (`tsc -b`) and Vite production bundle.
  - *Result*: Clean build with 0 errors.

### Issues Encountered & Resolved
1. **Alembic script path resolution**: When executed from root vs backend folder, Alembic requires `%(here)s/alembic` in `alembic.ini`. Configured `%(here)s` for robust cross-directory execution.
2. **TypeScript 6 baseUrl deprecation**: Replaced deprecated `"baseUrl": "."` with direct `"paths": { "@/*": ["./src/*"] }` in `tsconfig.app.json`.
3. **OxLint / TSC unused imports**: Cleaned unused imports in React layout components to satisfy strict compiler flags.

### Next Steps
- Await approval for Phase 0 completion.
- Begin **Phase 1: Evidence Ingestion** (multi-format parsers for PDF, DOCX, TXT, CSV, JSON, LOG; chunking pipeline; source storage).
