import os
import shutil
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import Case, EvidenceFile, EvidenceLine
from app.storage import get_case_storage_dir

TEST_DB_FILE = "test_phase2.db"
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_FILE}"
TEST_STORAGE_DIR = os.path.join(os.path.dirname(__file__), "test_storage")

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(autouse=True)
def setup_and_teardown_env(monkeypatch):
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

def create_sample_case(case_number="CASE-P2-001", title="Phase 2 Ingestion Case"):
    res = client.post("/api/cases", json={"case_number": case_number, "title": title})
    assert res.status_code == 201
    return res.json()["id"]

# 1. Valid TXT upload, SHA-256 calculation, file size, line counts, numbering
def test_valid_txt_upload():
    case_id = create_sample_case()
    file_content = b"Line 1: Subject identified.\nLine 2: Account transferred $50,000.\nLine 3: Transaction closed."

    files = {"file": ("bank_statement.txt", file_content, "text/plain")}
    response = client.post(f"/api/cases/{case_id}/evidence", files=files)
    assert response.status_code == 201
    data = response.json()
    assert data["case_id"] == case_id
    assert data["original_filename"] == "bank_statement.txt"
    assert data["file_size"] == len(file_content)
    assert data["line_count"] == 3
    assert len(data["sha256_hash"]) == 64

    # Check lines endpoint
    lines_res = client.get(f"/api/cases/{case_id}/evidence/{data['id']}/lines")
    assert lines_res.status_code == 200
    lines_data = lines_res.json()
    assert lines_data["total_lines"] == 3
    assert len(lines_data["lines"]) == 3
    assert lines_data["lines"][0]["line_number"] == 1
    assert lines_data["lines"][0]["content"] == "Line 1: Subject identified."
    assert lines_data["lines"][1]["line_number"] == 2
    assert lines_data["lines"][2]["line_number"] == 3

# 2. Blank line preservation & whitespace preservation
def test_blank_and_whitespace_preservation():
    case_id = create_sample_case()
    file_content = b"  Leading space\n\n\tTab indent\n   "
    files = {"file": ("whitespace.txt", file_content, "text/plain")}
    res = client.post(f"/api/cases/{case_id}/evidence", files=files)
    assert res.status_code == 201
    evidence_id = res.json()["id"]

    lines_res = client.get(f"/api/cases/{case_id}/evidence/{evidence_id}/lines")
    lines = lines_res.json()["lines"]
    assert len(lines) == 4
    assert lines[0]["content"] == "  Leading space"
    assert lines[1]["content"] == ""
    assert lines[2]["content"] == "\tTab indent"
    assert lines[3]["content"] == "   "

# 3. CRLF and LF handling
def test_crlf_and_lf_handling():
    case_id = create_sample_case()
    # Windows CRLF
    content_crlf = b"Row 1\r\nRow 2\r\nRow 3"
    files = {"file": ("crlf.txt", content_crlf, "text/plain")}
    res1 = client.post(f"/api/cases/{case_id}/evidence", files=files)
    assert res1.status_code == 201
    assert res1.json()["line_count"] == 3

    # Unix LF
    content_lf = b"Unix 1\nUnix 2"
    files2 = {"file": ("lf.txt", content_lf, "text/plain")}
    res2 = client.post(f"/api/cases/{case_id}/evidence", files=files2)
    assert res2.status_code == 201
    assert res2.json()["line_count"] == 2

# 4. Duplicate content rejection within same case
def test_duplicate_content_rejection_within_case():
    case_id = create_sample_case()
    content = b"Classified memo text verbatim."

    # Upload 1
    files1 = {"file": ("memo1.txt", content, "text/plain")}
    res1 = client.post(f"/api/cases/{case_id}/evidence", files=files1)
    assert res1.status_code == 201

    # Upload 2 with different filename but identical content
    files2 = {"file": ("memo_renamed.txt", content, "text/plain")}
    res2 = client.post(f"/api/cases/{case_id}/evidence", files=files2)
    assert res2.status_code == 409
    assert "Duplicate evidence detected" in res2.json()["detail"]

# 5. Same content accepted in different cases
def test_same_content_accepted_in_different_cases():
    case1 = create_sample_case("CASE-DIFF-1", "Case 1")
    case2 = create_sample_case("CASE-DIFF-2", "Case 2")
    content = b"Shared forensic evidence file."

    res1 = client.post(f"/api/cases/{case1}/evidence", files={"file": ("shared.txt", content, "text/plain")})
    assert res1.status_code == 201

    res2 = client.post(f"/api/cases/{case2}/evidence", files={"file": ("shared.txt", content, "text/plain")})
    assert res2.status_code == 201

# 6. Invalid file extension rejection
def test_invalid_extension_rejected():
    case_id = create_sample_case()
    files = {"file": ("evidence.pdf", b"%PDF-1.4 Fake PDF", "application/pdf")}
    res = client.post(f"/api/cases/{case_id}/evidence", files=files)
    assert res.status_code == 415
    assert "Unsupported file type" in res.json()["detail"]

# 7. Binary content rejection (null bytes)
def test_binary_content_rejected():
    case_id = create_sample_case()
    binary_data = b"Plain text header\x00\x01\x02binary payload"
    files = {"file": ("fake_text.txt", binary_data, "text/plain")}
    res = client.post(f"/api/cases/{case_id}/evidence", files=files)
    assert res.status_code == 415
    assert "Binary content detected" in res.json()["detail"]

# 8. Empty file rejection
def test_empty_file_rejected():
    case_id = create_sample_case()
    files = {"file": ("empty.txt", b"", "text/plain")}
    res = client.post(f"/api/cases/{case_id}/evidence", files=files)
    assert res.status_code == 422
    assert "empty" in res.json()["detail"].lower()

# 9. Oversized file rejection (> 5MB)
def test_oversized_file_rejected():
    case_id = create_sample_case()
    big_content = b"A" * (5 * 1024 * 1024 + 1024)
    files = {"file": ("big.txt", big_content, "text/plain")}
    res = client.post(f"/api/cases/{case_id}/evidence", files=files)
    assert res.status_code == 413
    assert "exceeds maximum allowed size" in res.json()["detail"].lower()

# 10. Nonexistent case rejection
def test_upload_nonexistent_case():
    files = {"file": ("valid.txt", b"Hello", "text/plain")}
    res = client.post("/api/cases/999999/evidence", files=files)
    assert res.status_code == 404

# 11. Case isolation (Case A evidence cannot be accessed via Case B URL)
def test_case_isolation():
    case1 = create_sample_case("CASE-ISO-1", "Case 1")
    case2 = create_sample_case("CASE-ISO-2", "Case 2")

    res = client.post(f"/api/cases/{case1}/evidence", files={"file": ("c1_file.txt", b"Secret data", "text/plain")})
    assert res.status_code == 201
    ev_id = res.json()["id"]

    # Attempt to access via case2
    res_iso = client.get(f"/api/cases/{case2}/evidence/{ev_id}")
    assert res_iso.status_code == 404

    res_iso_lines = client.get(f"/api/cases/{case2}/evidence/{ev_id}/lines")
    assert res_iso_lines.status_code == 404

    res_iso_verify = client.get(f"/api/cases/{case2}/evidence/{ev_id}/verify")
    assert res_iso_verify.status_code == 404

# 12. Integrity verification success & failure upon tampering
def test_integrity_verification_and_tampering():
    case_id = create_sample_case()
    original_data = b"Critical financial record line 1\nCritical financial record line 2"
    res = client.post(f"/api/cases/{case_id}/evidence", files={"file": ("record.txt", original_data, "text/plain")})
    assert res.status_code == 201
    ev_data = res.json()
    ev_id = ev_data["id"]
    stored_name = ev_data["stored_filename"]

    # 1. Verify unmodified
    v_res = client.get(f"/api/cases/{case_id}/evidence/{ev_id}/verify")
    assert v_res.status_code == 200
    v_data = v_res.json()
    assert v_data["file_exists"] is True
    assert v_data["hash_matched"] is True
    assert v_data["verification_status"] == "verified"
    assert v_data["stored_hash"] == v_data["computed_hash"]

    # 2. Tamper with file on disk
    case_dir = get_case_storage_dir(case_id)
    stored_file_path = os.path.join(case_dir, stored_name)
    with open(stored_file_path, "wb") as f:
        f.write(b"Tampered unauthorized content!")

    # Verify after tampering
    v_tamper_res = client.get(f"/api/cases/{case_id}/evidence/{ev_id}/verify")
    assert v_tamper_res.status_code == 200
    vt_data = v_tamper_res.json()
    assert vt_data["file_exists"] is True
    assert vt_data["hash_matched"] is False
    assert vt_data["verification_status"] == "corrupted"
    assert "mismatch" in vt_data["message"].lower()

    # 3. Missing file
    os.remove(stored_file_path)
    v_missing_res = client.get(f"/api/cases/{case_id}/evidence/{ev_id}/verify")
    assert v_missing_res.status_code == 200
    vm_data = v_missing_res.json()
    assert vm_data["file_exists"] is False
    assert vm_data["verification_status"] == "missing_file"
