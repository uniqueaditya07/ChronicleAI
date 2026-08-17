# ADR 001: Modular Monolith Architecture

## Status
Accepted

## Context
ChronicleAI requires rapid development over a 1-week timeframe while maintaining clean domain boundaries between ingestion, extraction, timeline reconstruction, provenance tracking, and investigation reasoning. Introducing microservices or distributed infrastructure (such as message queues, RPC services, or distributed caches) would introduce significant deployment overhead, debugging friction, and unnecessary operational complexity.

## Decision
We adopt a **Modular Monolith** architecture:
- A single FastAPI backend application organized into strictly separated domain modules (`services/ingestion`, `services/extraction`, `services/timeline`, `services/contradiction`, `services/investigation`).
- Python `ABC` / `Protocol` interfaces between service boundaries.
- A single unified relational database and API layer.
- An independent React + Vite + TypeScript frontend communicating via standard REST APIs.

## Consequences
### Positive
- Zero infrastructure deployment friction (runs locally out-of-the-box).
- Simple end-to-end testing and single-process debugging.
- Clean interfaces ensure any individual subsystem can be factored out into independent workers or microservices in the future if scale warrants.

### Negative
- Shared memory/process space requires discipline to prevent tight cross-module coupling. Enforced by code review and explicit interfaces.
