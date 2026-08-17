# ADR 002: SQLite as Initial Database Engine

## Status
Accepted

## Context
ChronicleAI needs a zero-configuration, embedded relational database for local investigations, supporting rapid schema evolution and deterministic test fixtures without requiring external database servers (like PostgreSQL or MySQL).

## Decision
We select **SQLite** with SQLAlchemy 2.0 ORM and Alembic migrations as the primary database for the current phase:
- Enforce foreign keys on connection (`PRAGMA foreign_keys = ON`).
- Enable Write-Ahead Logging (`PRAGMA journal_mode = WAL`) for concurrent reads.
- Use UUIDv4 string primary keys across all tables to ensure seamless migration to PostgreSQL or distributed databases in future iterations.
- Enable `render_as_batch=True` in Alembic to handle SQLite table migrations cleanly.

## Consequences
### Positive
- Zero external database installation or configuration required.
- Extremely fast in-memory database testing (`sqlite:///:memory:`).
- Self-contained file-based storage allows easy case export and backup.

### Negative
- Concurrent writes are serialized. This is acceptable for single-user investigation workflows.
