# Changelog

All notable changes to the **ChronicleAI** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased] - 2026-08-17

### Added
- **Project Foundation (Phase 0)**:
  - Initialized Git repository and root `.gitignore`, `.env.example`.
  - Established Master Specification (`docs/MASTER_SPECIFICATION.md`) with 47 architectural and domain sections.
  - Backend project scaffold with FastAPI, Pydantic v2, and SQLAlchemy 2.0.
  - SQLite database integration configured with foreign keys and WAL mode.
  - Alembic database migration pipeline with initial `cases` table schema.
  - Structured logging and unified JSON error handling middleware.
  - Core Case CRUD REST API (`/api/v1/cases`) and system health endpoint (`/api/v1/health`).
  - Automated pytest test suite covering unit configuration, database session, and integration endpoints.
  - Frontend project scaffold with React 19, TypeScript, Vite, Tailwind CSS v4, and Lucide icons.
  - Application shell with live backend health telemetry and interactive database persistence testing widget.
  - Architectural Decision Records: `ADR-001` (Modular Monolith), `ADR-002` (SQLite Database), and `ADR-003` (Tailwind CSS v4 & Custom Timeline).
