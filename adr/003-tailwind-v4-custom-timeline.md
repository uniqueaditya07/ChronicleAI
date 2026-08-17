# ADR 003: Tailwind CSS v4 & Custom React Timeline Component

## Status
Accepted

## Context
1. Modern styling: ChronicleAI requires a clean, robust, and performant design system. Tailwind CSS v4 provides a streamlined build pipeline with `@tailwindcss/vite`.
2. Timeline visualization: Existing generic timeline libraries (e.g. `vis-timeline`) lack native support for ChronicleAI's core domain requirements: imprecise timestamps (e.g. "early March", "Q2 2024"), uncertainty bands, confidence badges, conflicting events, and direct provenance drill-down.

## Decision
1. Use **Tailwind CSS v4** via the `@tailwindcss/vite` plugin and `@import "tailwindcss"` configuration.
2. Build a **custom React timeline component** in Phase 3 tailored specifically to our `Event` and `Uncertainty` domain models rather than wrapping generic third-party timeline libraries.

## Consequences
### Positive
- Direct alignment between the uncertainty data model and UI rendering.
- Complete control over event clustering, conflict indicators, and drill-down interactions.
- Minimal bundle overhead and clean styling integration with Tailwind v4.

### Negative
- Custom timeline interactions (zooming, temporal clustering) must be implemented deliberately; mitigated by progressive delivery from simple vertical timeline to interactive multi-scale timeline.
