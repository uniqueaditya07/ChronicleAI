# ChronicleAI REST API Specification

Base URL: `/api/v1`

---

## 1. System Endpoints

### `GET /api/v1/health`
Checks backend application health and database connection.

**Response (200 OK)**:
```json
{
  "status": "healthy",
  "app_name": "ChronicleAI API",
  "version": "0.1.0",
  "environment": "development",
  "database_connected": true,
  "timestamp": "2026-08-17T18:15:00.000000Z"
}
```

---

## 2. Case Management Endpoints

### `POST /api/v1/cases`
Creates a new investigation case container.

**Request Body**:
```json
{
  "name": "Operation Bluebird Investigation",
  "description": "Cross-document timeline reconstruction"
}
```

**Response (201 Created)**:
```json
{
  "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "name": "Operation Bluebird Investigation",
  "description": "Cross-document timeline reconstruction",
  "status": "active",
  "created_at": "2026-08-17T18:15:00.000000Z",
  "updated_at": "2026-08-17T18:15:00.000000Z"
}
```

### `GET /api/v1/cases`
Lists investigation cases with pagination and status filtering.

**Query Parameters**:
- `skip`: Integer (default 0)
- `limit`: Integer (default 50)
- `status_filter`: String (optional: `active`, `archived`, `deleted`)

**Response (200 OK)**:
```json
{
  "items": [
    {
      "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
      "name": "Operation Bluebird Investigation",
      "description": "Cross-document timeline reconstruction",
      "status": "active",
      "created_at": "2026-08-17T18:15:00.000000Z",
      "updated_at": "2026-08-17T18:15:00.000000Z"
    }
  ],
  "total": 1
}
```

### `GET /api/v1/cases/{case_id}`
Retrieves details for a specific case.

### `PATCH /api/v1/cases/{case_id}`
Updates case name, description, or status.

### `DELETE /api/v1/cases/{case_id}`
Deletes a case and all associated records.
