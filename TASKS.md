# ChronicleAI — Task Checklist & Phase Tracker

---

## Phase 0: Project Foundation
- [x] **0.1** Initialize Git repository and root `.gitignore`, `.env.example`
- [x] **0.2** Create Master Specification (`docs/MASTER_SPECIFICATION.md`)
- [x] **0.3** Set up backend project (FastAPI, SQLAlchemy 2.0, Pydantic v2, Alembic, SQLite)
- [x] **0.4** Set up frontend project (React 19, Vite, TypeScript, Tailwind CSS v4, Lucide)
- [x] **0.5** Implement database connection with SQLite WAL mode and foreign key constraints
- [x] **0.6** Implement Alembic migrations setup and baseline `cases` table
- [x] **0.7** Implement Case CRUD endpoints and health check endpoint
- [x] **0.8** Implement structured logging and unified error handlers
- [x] **0.9** Implement frontend application shell with live backend health telemetry
- [x] **0.10** Implement backend unit & integration tests (`pytest`)
- [x] **0.11** Create required documentation (`README.md`, `CHANGELOG.md`, `DEVELOPMENT_LOG.md`, `PROJECT_STATE.md`, `TASKS.md`, ADRs)
- [x] **0.12** Perform end-to-end build and test verification
- [x] **0.13** Initial Phase 0 Git commit

---

## Phase 1: Evidence Ingestion
- [ ] **1.1** Implement file upload API endpoint (`POST /api/v1/cases/{case_id}/sources/upload`)
- [ ] **1.2** Implement file deduplication using SHA-256 content hashes
- [ ] **1.3** Implement `BaseParser` interface and `ParserRegistry`
- [ ] **1.4** Implement PDF parser (PyMuPDF / `fitz`)
- [ ] **1.5** Implement DOCX parser (`python-docx`)
- [ ] **1.6** Implement TXT parser
- [ ] **1.7** Implement CSV parser (`pandas`)
- [ ] **1.8** Implement JSON parser
- [ ] **1.9** Implement LOG file parser
- [ ] **1.10** Implement Source Chunk persistence in SQLite
- [ ] **1.11** Build Source upload & file management UI in frontend
- [ ] **1.12** Build Source preview & Chunk inspector UI
- [ ] **1.13** Write parser unit tests and ingestion integration tests

---

## Phase 2: Entity & Event Extraction
- [ ] **2.1** Implement `LLMProvider` interface and Gemini client integration
- [ ] **2.2** Define few-shot structured extraction prompts and schemas
- [ ] **2.3** Implement Entity extraction service with type taxonomy
- [ ] **2.4** Implement Event extraction service with ISO 8601 timestamp normalization
- [ ] **2.5** Implement Claim extraction service with claimant & subject identification
- [ ] **2.6** Implement extraction validation & confidence bounds clamping
- [ ] **2.7** Implement AI extraction run audit logging (`ai_extraction_runs`)
- [ ] **2.8** Build Entity, Event, and Claim explorer views in frontend
- [ ] **2.9** Write extraction pipeline tests with mock LLM fixtures

---

## Phase 3: Timeline Engine
- [ ] **3.1** Implement Timeline construction algorithm with precision partitioning
- [ ] **3.2** Implement support for exact, day-level, approximate, and relative timestamps
- [ ] **3.3** Build custom interactive React Timeline component
- [ ] **3.4** Implement timeline filtering (by entity, source, type, confidence threshold)
- [ ] **3.5** Implement event detail expansion and provenance drill-down
- [ ] **3.6** Write timeline ordering and precision test suite

---

## Phase 4: Evidence Graph & Provenance
- [ ] **4.1** Implement Relationship extraction service
- [ ] **4.2** Build Provenance Chain component (Conclusion → Evidence → Chunk → Source)
- [ ] **4.3** Build interactive React Flow evidence & entity relationship graph
- [ ] **4.4** Implement Entity resolution detection and merge workflow UI
- [ ] **4.5** Write relationship and graph integration tests

---

## Phase 5: Contradiction & Uncertainty Engine
- [ ] **5.1** Implement deterministic temporal and factual contradiction detection
- [ ] **5.2** Implement AI-assisted contradiction detection
- [ ] **5.3** Build Contradiction comparison and resolution UI
- [ ] **5.4** Implement global uncertainty visualization across all views
- [ ] **5.5** Write contradiction detection tests

---

## Phase 6: Investigation / Reasoning Agent (Advanced)
- [ ] **6.1** Implement SQLite FTS5 full-text search indexing
- [ ] **6.2** Implement evidence retrieval pipeline
- [ ] **6.3** Implement investigation Q&A agent with mandatory citation validation
- [ ] **6.4** Build chat-based investigation interface with clickable citations
- [ ] **6.5** Write investigation accuracy tests

---

## Phase 7: Report Generation
- [ ] **7.1** Implement structured report generation engine
- [ ] **7.2** Create report templates separating established facts from inferences
- [ ] **7.3** Build report viewer and Markdown/PDF export UI
- [ ] **7.4** Write report generator unit tests

---

## Phase 8: Evaluation & Research
- [ ] **8.1** Construct synthetic benchmark scenarios (financial fraud, security incident)
- [ ] **8.2** Implement automated evaluation metrics (Precision, Recall, F1, Citation Accuracy)
- [ ] **8.3** Execute benchmark evaluations and document findings
- [ ] **8.4** Frame answers to core research questions (RQ1–RQ5)

---

## Phase 9: Final Polish & Release
- [ ] **9.1** End-to-end validation across full multi-source workflows
- [ ] **9.2** UI/UX polish and responsive layout hardening
- [ ] **9.3** Documentation finalization
- [ ] **9.4** Release v0.1.0 tag
