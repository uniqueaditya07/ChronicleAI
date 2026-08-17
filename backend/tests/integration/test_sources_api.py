import pytest
from fastapi.testclient import TestClient

def create_case(client):
    resp = client.post("/api/v1/cases/", json={"name": "Test Case"})
    return resp.json()["id"]

def test_sources_api_upload_and_list(client: TestClient, db_session):
    case_id = create_case(client)
    file_content = b"Paragraph 1.\n\nParagraph 2."
    files = {"file": ("test.txt", file_content, "text/plain")}
    upload_resp = client.post(f"/api/v1/cases/{case_id}/sources/", files=files)
    
    assert upload_resp.status_code == 201
    source_data = upload_resp.json()
    assert source_data["original_filename"] == "test.txt"
    assert source_data["processing_status"] == "completed"
    assert source_data["chunk_count"] == 2
    source_id = source_data["id"]

    # List sources
    list_resp = client.get(f"/api/v1/cases/{case_id}/sources/")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["total"] == 1

    # Get source detail
    detail_resp = client.get(f"/api/v1/cases/{case_id}/sources/{source_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["id"] == source_id

    # List chunks
    chunks_resp = client.get(f"/api/v1/cases/{case_id}/sources/{source_id}/chunks")
    assert chunks_resp.status_code == 200
    chunks_data = chunks_resp.json()
    assert chunks_data["total"] == 2

    # Pagination for chunks
    page_resp = client.get(f"/api/v1/cases/{case_id}/sources/{source_id}/chunks?skip=1&limit=1")
    assert page_resp.status_code == 200
    assert page_resp.json()["total"] == 2
    assert len(page_resp.json()["items"]) == 1

def test_sources_api_duplicate_upload(client: TestClient, db_session):
    case_id = create_case(client)
    file_content = b"Paragraph 1.\n\nParagraph 2."
    files = {"file": ("test.txt", file_content, "text/plain")}
    client.post(f"/api/v1/cases/{case_id}/sources/", files=files)
    
    # Duplicate upload returns 409
    files_dup = {"file": ("test_copy.txt", file_content, "text/plain")}
    dup_resp = client.post(f"/api/v1/cases/{case_id}/sources/", files=files_dup)
    assert dup_resp.status_code == 409

def test_sources_api_invalid_upload(client: TestClient, db_session):
    case_id = create_case(client)
    # Upload invalid file (unsupported extension)
    files_bad = {"file": ("test.exe", b"bad", "application/x-msdownload")}
    bad_resp = client.post(f"/api/v1/cases/{case_id}/sources/", files=files_bad)
    assert bad_resp.status_code == 400

def test_sources_api_not_found(client: TestClient, db_session):
    case_id = create_case(client)
    assert client.get(f"/api/v1/cases/fake-case/sources/").status_code == 404
    assert client.get(f"/api/v1/cases/{case_id}/sources/fake-source").status_code == 404
    assert client.get(f"/api/v1/cases/{case_id}/sources/fake-source/chunks").status_code == 404
