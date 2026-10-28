# Fictional test fixtures only; no original case evidence is included.
import os
import shutil
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

TEST_DB_FILE = "test_phase3_search.db"
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_FILE}"
TEST_STORAGE_DIR = os.path.join(os.path.dirname(__file__), "test_storage_search")

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(autouse=True)
def setup_and_teardown_search_env(monkeypatch):
    monkeypatch.setenv("CHRONICLE_STORAGE_DIR", TEST_STORAGE_DIR)
    app.dependency_overrides[get_db] = override_get_db
    os.makedirs(TEST_STORAGE_DIR, exist_ok=True)
    Base.metadata.create_all(bind=engine)

    yield

    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.pop(get_db, None)
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except OSError:
            pass
    if os.path.exists(TEST_STORAGE_DIR):
        try:
            shutil.rmtree(TEST_STORAGE_DIR)
        except OSError:
            pass

client = TestClient(app)

def create_case_with_evidence():
    # Create Case 1
    c1 = client.post("/api/cases", json={"case_number": "SEARCH-CASE-1", "title": "Fraud Probe"}).json()
    case1_id = c1["id"]

    # Evidence A in Case 1
    ev_a_content = (
        "Meeting with David Mason on 12 October 2026.\n"
        "Discussed invoice SYN-2026-0001 for $125000 paid to Acme Consulting.\n"
        "Special bonus: 100% approved by finance.\n"
        "User account_id_99 flagged for audit."
    ).encode("utf-8")
    client.post(
        f"/api/cases/{case1_id}/evidence",
        files={"file": ("memo_october.txt", ev_a_content, "text/plain")}
    )

    # Evidence B in Case 1
    ev_b_content = (
        "Follow-up interview regarding Acme Consulting.\n"
        "Payment reference SYN-2026-0001 was processed via wire transfer.\n"
        "Discount rate was 25%_standard."
    ).encode("utf-8")
    client.post(
        f"/api/cases/{case1_id}/evidence",
        files={"file": ("audit_interview.txt", ev_b_content, "text/plain")}
    )

    # Create Case 2 (Isolation Test Case)
    c2 = client.post("/api/cases", json={"case_number": "SEARCH-CASE-2", "title": "Isolated Case"}).json()
    case2_id = c2["id"]

    ev_c_content = (
        "David Mason appears in Case 2 confidential records.\n"
        "SYN-2026-0001 isolated record."
    ).encode("utf-8")
    client.post(
        f"/api/cases/{case2_id}/evidence",
        files={"file": ("classified_case2.txt", ev_c_content, "text/plain")}
    )

    return case1_id, case2_id

# 1. Single-word search
def test_single_word_search():
    case1_id, _ = create_case_with_evidence()
    res = client.get(f"/api/cases/{case1_id}/search?q=David")
    assert res.status_code == 200
    data = res.json()
    assert data["total_matches"] == 1
    assert data["query"] == "David"
    match = data["results"][0]
    assert match["original_filename"] == "memo_october.txt"
    assert match["line_number"] == 1
    assert "David Mason" in match["line_content"]
    assert len(match["sha256_hash"]) == 64

# 2. Multi-word phrase search
def test_multi_word_phrase_search():
    case1_id, _ = create_case_with_evidence()
    res = client.get(f"/api/cases/{case1_id}/search?q=Acme Consulting")
    assert res.status_code == 200
    data = res.json()
    # Appears in memo_october.txt (line 2) and audit_interview.txt (line 1)
    assert data["total_matches"] == 2
    filenames = [r["original_filename"] for r in data["results"]]
    assert "memo_october.txt" in filenames
    assert "audit_interview.txt" in filenames

# 3. Case-insensitive search
def test_case_insensitive_search():
    case1_id, _ = create_case_with_evidence()
    res_lower = client.get(f"/api/cases/{case1_id}/search?q=david mason")
    res_upper = client.get(f"/api/cases/{case1_id}/search?q=DAVID MASON")
    assert res_lower.status_code == 200
    assert res_upper.status_code == 200
    assert res_lower.json()["total_matches"] == 1
    assert res_upper.json()["total_matches"] == 1
    assert res_lower.json()["results"][0]["line_number"] == 1

# 4. Numerical search
def test_numerical_search():
    case1_id, _ = create_case_with_evidence()
    res = client.get(f"/api/cases/{case1_id}/search?q=125000")
    assert res.status_code == 200
    data = res.json()
    assert data["total_matches"] == 1
    assert "$125,000" in data["results"][0]["line_content"] or "125000" in data["results"][0]["line_content"]

# 5. Punctuation and reference-code search
def test_punctuation_and_reference_code():
    case1_id, _ = create_case_with_evidence()
    res = client.get(f"/api/cases/{case1_id}/search?q=SYN-2026-0001")
    assert res.status_code == 200
    data = res.json()
    assert data["total_matches"] == 2
    for r in data["results"]:
        assert "SYN-2026-0001" in r["line_content"]

# 6. Literal % and _ handling (no wildcard expansion)
def test_literal_sql_wildcard_handling():
    case1_id, _ = create_case_with_evidence()
    # Searching for literal "% approved"
    res_pct = client.get(f"/api/cases/{case1_id}/search?q=% approved")
    assert res_pct.status_code == 200
    assert res_pct.json()["total_matches"] == 1
    assert res_pct.json()["results"][0]["line_content"] == "Special bonus: 100% approved by finance."

    # Searching for literal "%_" should match "25%_standard"
    res_combo = client.get(f"/api/cases/{case1_id}/search?q=%_")
    assert res_combo.status_code == 200
    assert res_combo.json()["total_matches"] == 1
    assert "25%_standard" in res_combo.json()["results"][0]["line_content"]

    # Searching for "_" should NOT act as single character wildcard matching every non-empty line
    res_underscore = client.get(f"/api/cases/{case1_id}/search?q=account_id_99")
    assert res_underscore.status_code == 200
    assert res_underscore.json()["total_matches"] == 1

# 7. No matching results
def test_no_matching_results():
    case1_id, _ = create_case_with_evidence()
    res = client.get(f"/api/cases/{case1_id}/search?q=NonExistentTermXYZ")
    assert res.status_code == 200
    data = res.json()
    assert data["total_matches"] == 0
    assert data["results"] == []

# 8. Empty or whitespace query validation
def test_empty_query_validation():
    case1_id, _ = create_case_with_evidence()
    res_blank = client.get(f"/api/cases/{case1_id}/search?q=   ")
    assert res_blank.status_code == 422
    assert "empty or contain only whitespace" in res_blank.json()["detail"]

# 9. Nonexistent case rejection
def test_search_nonexistent_case():
    res = client.get("/api/cases/999999/search?q=test")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()

# 10. Case isolation
def test_search_case_isolation():
    case1_id, case2_id = create_case_with_evidence()
    # David Mason appears in both cases, but query in Case 1 must return ONLY Case 1 matches
    res1 = client.get(f"/api/cases/{case1_id}/search?q=David Mason")
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["total_matches"] == 1
    assert data1["results"][0]["case_id"] == case1_id
    assert data1["results"][0]["original_filename"] == "memo_october.txt"

    # Query in Case 2 returns ONLY Case 2 match
    res2 = client.get(f"/api/cases/{case2_id}/search?q=David Mason")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["total_matches"] == 1
    assert data2["results"][0]["case_id"] == case2_id
    assert data2["results"][0]["original_filename"] == "classified_case2.txt"

# 11. Deterministic ordering: original_filename ASC, evidence_file_id ASC, line_number ASC
def test_deterministic_ordering():
    case1_id, _ = create_case_with_evidence()
    res = client.get(f"/api/cases/{case1_id}/search?q=SYN-2026-0001")
    assert res.status_code == 200
    results = res.json()["results"]
    assert len(results) == 2
    # audit_interview.txt comes before memo_october.txt alphabetically
    assert results[0]["original_filename"] == "audit_interview.txt"
    assert results[1]["original_filename"] == "memo_october.txt"

# 12. Pagination and total counts
def test_pagination_and_total_counts():
    case1_id, _ = create_case_with_evidence()
    # Both files contain "SYN-2026-0001", page_size=1 should return 1 item with total_matches=2
    res_p1 = client.get(f"/api/cases/{case1_id}/search?q=SYN-2026-0001&page=1&page_size=1")
    assert res_p1.status_code == 200
    d1 = res_p1.json()
    assert d1["total_matches"] == 2
    assert d1["page"] == 1
    assert len(d1["results"]) == 1
    assert d1["results"][0]["original_filename"] == "audit_interview.txt"

    # Page 2
    res_p2 = client.get(f"/api/cases/{case1_id}/search?q=SYN-2026-0001&page=2&page_size=1")
    assert res_p2.status_code == 200
    d2 = res_p2.json()
    assert d2["total_matches"] == 2
    assert d2["page"] == 2
    assert len(d2["results"]) == 1
    assert d2["results"][0]["original_filename"] == "memo_october.txt"
