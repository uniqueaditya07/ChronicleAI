# ChronicleAI

> **Evidence-Centric AI Timeline Reconstruction & Investigation System**

[![Status: In Development](https://img.shields.io/badge/status-active%20development-blue.svg)](#)
[![Phase: Phase 0 Foundation](https://img.shields.io/badge/phase-0%20foundation-emerald.svg)](#)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](#)

---

## 1. Project Overview

**ChronicleAI** is an evidence-centric AI system designed to reconstruct chronological event timelines from heterogeneous, incomplete, and potentially conflicting information sources.

The system is built on a central invariant:

$$\textbf{EVIDENCE} \neq \textbf{INFERENCE}$$

The system never silently converts an uncertain AI inference into an established fact. Every extracted entity, event, claim, and conclusion maintains bidirectional provenance tracing back to its raw source evidence.

---

## 2. Core Architecture

The system is architected as a **Modular Monolith**:

- **Backend**: Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.0 (ORM), Alembic migrations, SQLite database.
- **Frontend**: React 19, TypeScript, Vite, Tailwind CSS v4, Lucide icons.
- **AI Engine (Planned Phase 2+)**: Gemini structured JSON extraction & schema validation.

```
┌────────────────────────────────────────────────────────┐
│               Frontend (React / Vite / TS)             │
│   Tailwind CSS v4 • Lucide • Dynamic Application Shell │
└───────────────────────────┬────────────────────────────┘
                            │ REST / JSON (/api/v1)
┌───────────────────────────▼────────────────────────────┐
│               Backend (FastAPI / Python)               │
│   Lifespan • CORS • Structured Logging • Pydantic v2   │
│   SQLAlchemy 2.0 ORM • SQLite (WAL mode & FK active)   │
└───────────────────────────┬────────────────────────────┘
                            │
               ┌────────────▼────────────┐
               │    SQLite (Local DB)    │
               │   data/chronicle.db     │
               └─────────────────────────┘
```

---

## 3. Current Project State (Phase 0 Foundation)

- **Backend Foundation**: Runnable FastAPI application with modular settings, structured logging, CORS middleware, global error envelope, and database connection lifecycle.
- **Database & Migrations**: SQLAlchemy 2.0 declarative models with Alembic migrations (`cases` table initialized).
- **Frontend Foundation**: Vite + React 19 + TypeScript + Tailwind CSS v4 shell with live backend health telemetry and interactive case persistence testing widget.
- **Test Suite**: Automated pytest suite for configuration, database session, health check, and CRUD endpoints.

---

## 4. Getting Started

### Prerequisites

- **Python 3.11+**
- **Node.js v18+** & **npm**

### Backend Setup

1. Open a terminal in the project root:
   ```bash
   cd backend
   ```

2. Create and activate a virtual environment:
   ```bash
   # Windows (PowerShell)
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1

   # Linux/macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run database migrations:
   ```bash
   alembic upgrade head
   ```

5. Start the backend development server:
   ```bash
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

   - API Documentation: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
   - Health Endpoint: [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health)

### Frontend Setup

1. In a separate terminal, navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the Vite development server:
   ```bash
   npm run dev
   ```

4. Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## 5. Running Tests

### Backend Test Suite

From the `backend/` directory:
```bash
pytest -v
```

### Frontend Build & Type Check

From the `frontend/` directory:
```bash
npm run build
```

---

## 6. Phased Development Roadmap

- [x] **Phase 0 — Project Foundation** *(Complete)*
- [ ] **Phase 1 — Evidence Ingestion** *(Next)*
- [ ] **Phase 2 — Entity & Event Extraction**
- [ ] **Phase 3 — Timeline Engine**
- [ ] **Phase 4 — Evidence Graph & Provenance**
- [ ] **Phase 5 — Contradiction & Uncertainty Engine**
- [ ] **Phase 6 — Investigation / Reasoning Agent**
- [ ] **Phase 7 — Report Generation**
- [ ] **Phase 8 — Evaluation & Research**
- [ ] **Phase 9 — Final Polish & Release**

---

## 7. License

MIT License. See [LICENSE](LICENSE) for details.
