# ChronicleAI System Architecture

## 1. Architectural Philosophy

ChronicleAI is designed around a single immutable principle:

$$\textbf{EVIDENCE} \neq \textbf{INFERENCE}$$

1. **Evidence First**: All conclusions, timeline entries, entities, and relationships are grounded in raw source evidence.
2. **Provenance**: Complete bidirectional traceability exists from conclusion $\rightarrow$ extraction $\rightarrow$ chunk $\rightarrow$ source file.
3. **Explicit Uncertainty**: Confidence scores, temporal precision, and verification statuses are represented explicitly.
4. **Deterministic Ingestion**: Document parsing and chunking are deterministic and never involve LLM hallucinations.

---

## 2. Component Topology

```
┌────────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React 19 / TypeScript)                │
│   Vite • Tailwind CSS v4 • Lucide Icons • React Flow (Phase 4)         │
│   Components: AppLayout, TopBar, Sidebar, CaseManager, Telemetry       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP / JSON REST (/api/v1)
┌───────────────────────────────────▼────────────────────────────────────┐
│                        BACKEND (FastAPI / Python)                      │
│                                                                        │
│  ┌─── API Layer ──────────────────────────────────────────────────┐    │
│  │   /health   │   /cases   │   /sources (P1)   │   /timeline (P3)│    │
│  └────────────────────────────────┬───────────────────────────────┘    │
│                                   │                                    │
│  ┌─── Service Layer ──────────────▼───────────────────────────────┐    │
│  │   CaseService        │ IngestionService (P1)                   │    │
│  │   ExtractionService (P2) │ TimelineService (P3)                │    │
│  │   ContradictionService (P5) │ InvestigationService (P6)        │    │
│  └────────────────────────────────┬───────────────────────────────┘    │
│                                   │                                    │
│  ┌─── Data Access Layer ──────────▼───────────────────────────────┐    │
│  │   SQLAlchemy 2.0 ORM • Pydantic v2 Schemas • Alembic Migrations│    │
│  └────────────────────────────────┬───────────────────────────────┘    │
└───────────────────────────────────┼────────────────────────────────────┘
                                    │
                    ┌───────────────▼───────────────┐
                    │       SQLite Database         │
                    │   (WAL Mode, Foreign Keys)    │
                    └───────────────────────────────┘
```

---

## 3. Technology Stack Reference

| Subsystem | Technology | Justification |
|---|---|---|
| API Framework | FastAPI | High throughput, native async support, Pydantic validation, OpenAPI specs |
| ORM | SQLAlchemy 2.0 | Explicit typing, mapped_column syntax, multi-database portability |
| Database | SQLite 3 | Embedded, zero-configuration, robust WAL concurrency for single-user |
| Migrations | Alembic | Tracked, reversible schema changes with SQLite batch mode support |
| Frontend | React 19 + TypeScript + Vite | Type safety, lightning-fast HMR, mature ecosystem |
| Styling | Tailwind CSS v4 | CSS-first configuration, zero runtime overhead, modular utility classes |
| Validation | Pydantic v2 | High-performance C-based schema validation and type coercion |
