# ChronicleAI Domain & Data Model

## 1. Domain Entities Overview

```
Case (Container)
  └── Source (Document / Artifact)
       └── SourceChunk (Atomic extractable text segment)
            └── Evidence (Normalized excerpt with provenance)
                 ├── EntityMention ──> Entity
                 ├── Event ──> TimelineEntry
                 ├── Claim ──> Claimant / Subject
                 └── Relationship ──> Entity ↔ Entity
```

---

## 2. Table Schemas (Current & Phased Roadmap)

### Active in Phase 0: `cases`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | String(36) | Primary Key (UUIDv4) | Unique case identifier |
| `name` | String(255) | NOT NULL | Case title |
| `description` | Text | Nullable | Detailed case summary |
| `status` | String(50) | NOT NULL, Default 'active' | active, archived, deleted |
| `created_at` | DateTime(UTC) | NOT NULL | Creation timestamp |
| `updated_at` | DateTime(UTC) | NOT NULL | Last update timestamp |

---

## 3. Timestamp Invariant Strategy

ChronicleAI supports heterogeneous temporal precisions:
- `exact`: Second/minute-level timestamp (e.g. `2024-03-15T14:30:00Z`).
- `day`: Date only (`2024-03-15`).
- `month`: Month-level (`2024-03`).
- `year`: Year-level (`2024`).
- `approximate`: Midpoint approximation with confidence penalty.
- `relative`: Anchor event reference (e.g. "two days after meeting").
- `unknown`: Explicitly marked as undated without guessing.
