import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

TEST_DB_FILE = "test_chronicle.db"
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_FILE}"

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(autouse=True)
def setup_and_teardown_db():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.pop(get_db, None)
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except OSError:
            pass

client = TestClient(app)

def test_create_case_success():
    payload = {
        "case_number": "CASE-2026-001",
        "title": "Corporate Leak Investigation",
        "description": "Analysis of leaked internal memos.",
        "status": "Open"
    }
    response = client.post("/api/cases", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["case_number"] == "CASE-2026-001"
    assert data["title"] == "Corporate Leak Investigation"
    assert data["description"] == "Analysis of leaked internal memos."
    assert data["status"] == "Open"
    assert "created_at" in data
    assert "updated_at" in data

def test_create_case_duplicate_number():
    payload = {
        "case_number": "CASE-DUP-01",
        "title": "Initial Case",
        "status": "Open"
    }
    res1 = client.post("/api/cases", json=payload)
    assert res1.status_code == 201

    res2 = client.post("/api/cases", json=payload)
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"]

def test_create_case_invalid_payload():
    # Missing required title
    payload = {
        "case_number": "CASE-INVALID-01"
    }
    response = client.post("/api/cases", json=payload)
    assert response.status_code == 422

    # Empty case_number
    response2 = client.post("/api/cases", json={"case_number": "", "title": "Empty Num"})
    assert response2.status_code == 422

def test_get_case_by_id():
    payload = {
        "case_number": "CASE-GET-01",
        "title": "Target Retrieval",
        "description": "Details here"
    }
    created = client.post("/api/cases", json=payload).json()
    case_id = created["id"]

    response = client.get(f"/api/cases/{case_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == case_id
    assert data["case_number"] == "CASE-GET-01"

def test_get_case_not_found():
    response = client.get("/api/cases/999999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

def test_list_cases_and_search():
    client.post("/api/cases", json={"case_number": "ALPHA-01", "title": "Fraud in Operations", "status": "Open"})
    client.post("/api/cases", json={"case_number": "BETA-02", "title": "Insider Trading Review", "status": "In Progress"})
    client.post("/api/cases", json={"case_number": "GAMMA-03", "title": "Old Archive", "status": "Closed"})

    # List all
    res_all = client.get("/api/cases")
    assert res_all.status_code == 200
    assert len(res_all.json()) == 3

    # Filter by status
    res_status = client.get("/api/cases?status=Open")
    assert res_status.status_code == 200
    assert len(res_status.json()) == 1
    assert res_status.json()[0]["case_number"] == "ALPHA-01"

    # Search by title
    res_search = client.get("/api/cases?search=Trading")
    assert res_search.status_code == 200
    assert len(res_search.json()) == 1
    assert res_search.json()[0]["case_number"] == "BETA-02"

    # Search by case_number
    res_search_num = client.get("/api/cases?search=GAMMA")
    assert res_search_num.status_code == 200
    assert len(res_search_num.json()) == 1
    assert res_search_num.json()[0]["title"] == "Old Archive"

def test_update_case():
    created = client.post("/api/cases", json={"case_number": "CASE-UPD-01", "title": "Original Title"}).json()
    case_id = created["id"]

    patch_payload = {
        "title": "Updated Title",
        "status": "Closed",
        "description": "Case concluded successfully."
    }
    response = client.patch(f"/api/cases/{case_id}", json=patch_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["status"] == "Closed"
    assert data["description"] == "Case concluded successfully."

def test_update_case_not_found():
    response = client.patch("/api/cases/999999", json={"title": "Doesn't exist"})
    assert response.status_code == 404

def test_case_stats():
    client.post("/api/cases", json={"case_number": "S-1", "title": "One", "status": "Open"})
    client.post("/api/cases", json={"case_number": "S-2", "title": "Two", "status": "In Progress"})
    client.post("/api/cases", json={"case_number": "S-3", "title": "Three", "status": "Closed"})
    client.post("/api/cases", json={"case_number": "S-4", "title": "Four", "status": "Open"})

    response = client.get("/api/cases/stats")
    assert response.status_code == 200
    stats = response.json()
    assert stats["total_cases"] == 4
    assert stats["open_cases"] == 2
    assert stats["in_progress_cases"] == 1
    assert stats["closed_cases"] == 1
