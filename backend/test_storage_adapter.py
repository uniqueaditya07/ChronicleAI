"""Isolated adapter tests; Supabase requests are always mocked."""

import hashlib
from types import SimpleNamespace

import pytest

from app import storage
from app.storage import (
    StorageConfigurationError,
    StorageError,
    StorageNotFoundError,
    SupabaseEvidenceStorage,
    get_storage_backend,
    read_stored_file,
    remove_stored_file,
    save_original_file,
)


class FakeResponse:
    def __init__(self, status_code=200, content=b"", payload=None):
        self.status_code = status_code
        self.content = content
        self.payload = payload or {}

    def json(self):
        return self.payload


@pytest.fixture
def supabase_env(monkeypatch):
    monkeypatch.setenv("CHRONICLE_STORAGE_BACKEND", "supabase")
    monkeypatch.setenv("SUPABASE_URL", "https://demo-project.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-secret")
    monkeypatch.setenv("SUPABASE_STORAGE_BUCKET", "private-evidence")


def test_supabase_upload_uses_private_case_scoped_key_and_no_upsert(monkeypatch, supabase_env):
    requests = []

    def fake_request(method, url, **kwargs):
        requests.append((method, url, kwargs))
        return FakeResponse(status_code=200)

    monkeypatch.setattr(storage.httpx, "request", fake_request)
    key, opaque_reference = save_original_file(41, "private note.txt", b"original bytes")

    assert key.startswith("case_41/")
    assert opaque_reference == key
    assert requests[0][0] == "POST"
    assert requests[0][1] == f"https://demo-project.supabase.co/storage/v1/object/private-evidence/{key}"
    assert requests[0][2]["headers"]["x-upsert"] == "false"
    assert requests[0][2]["headers"]["Content-Type"] == "text/plain"
    assert requests[0][2]["headers"]["Authorization"] == "Bearer test-service-role-secret"
    assert requests[0][2]["content"] == b"original bytes"
    assert "private note.txt" not in key
    assert "test-service-role-secret" not in key


def test_supabase_read_returns_object_bytes_and_checks_case_scope(monkeypatch, supabase_env):
    calls = []
    key = "case_41/" + "a" * 32 + ".txt"

    def fake_request(method, url, **kwargs):
        calls.append((method, url))
        return FakeResponse(content=b"retrieved evidence")

    monkeypatch.setattr(storage.httpx, "request", fake_request)
    assert read_stored_file(41, key) == b"retrieved evidence"
    assert calls[0][0] == "GET"
    assert f"/storage/v1/object/authenticated/private-evidence/{key}" in calls[0][1]

    with pytest.raises(ValueError, match="does not belong"):
        read_stored_file(42, key)
    assert len(calls) == 1


@pytest.mark.parametrize("response", [
    FakeResponse(status_code=404),
    FakeResponse(status_code=400, payload={"statusCode": "404", "error": "not_found"}),
])
def test_supabase_missing_object_is_reported_as_missing(monkeypatch, supabase_env, response):
    monkeypatch.setattr(storage.httpx, "request", lambda *args, **kwargs: response)
    key = "case_41/" + "b" * 32 + ".txt"

    with pytest.raises(StorageNotFoundError):
        read_stored_file(41, key)


def test_supabase_upload_error_does_not_expose_response_body(monkeypatch, supabase_env):
    response = FakeResponse(status_code=503, payload={"message": "test-service-role-secret private bytes"})
    monkeypatch.setattr(storage.httpx, "request", lambda *args, **kwargs: response)

    with pytest.raises(StorageError) as error:
        save_original_file(41, "note.txt", b"private bytes")
    assert "test-service-role-secret" not in str(error.value)
    assert "private bytes" not in str(error.value)


def test_supabase_configuration_requires_https_and_all_environment_values(monkeypatch):
    with pytest.raises(StorageConfigurationError):
        SupabaseEvidenceStorage("http://demo-project.supabase.co", "key", "bucket")

    for name in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_STORAGE_BUCKET"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("CHRONICLE_STORAGE_BACKEND", "supabase")
    with pytest.raises(StorageConfigurationError):
        get_storage_backend()


def test_supabase_cleanup_targets_only_the_scoped_key(monkeypatch, supabase_env):
    calls = []
    key = "case_41/" + "c" * 32 + ".txt"

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return FakeResponse()

    monkeypatch.setattr(storage.httpx, "request", fake_request)
    remove_stored_file(41, key)

    assert calls[0][0] == "DELETE"
    assert calls[0][2]["json"] == {"prefixes": [key]}


def test_local_filesystem_remains_default_and_round_trips_in_disposable_storage(tmp_path, monkeypatch):
    monkeypatch.delenv("CHRONICLE_STORAGE_BACKEND", raising=False)
    monkeypatch.setenv("CHRONICLE_STORAGE_DIR", str(tmp_path / "evidence"))
    key, path = save_original_file(7, "local.txt", b"local bytes")

    assert len(key) == 36 and key.endswith(".txt")
    assert read_stored_file(7, key) == b"local bytes"
    assert path.endswith(key)
    remove_stored_file(7, key)
    with pytest.raises(StorageNotFoundError):
        read_stored_file(7, key)


def test_report_integrity_uses_configured_storage_and_detects_mismatch(monkeypatch, supabase_env):
    from app.case_tools import evidence_integrity

    content = b"report verification"
    file_record = SimpleNamespace(
        case_id=41,
        stored_filename="case_41/" + "d" * 32 + ".txt",
        sha256_hash=hashlib.sha256(content).hexdigest(),
    )
    monkeypatch.setattr(storage.httpx, "request", lambda *args, **kwargs: FakeResponse(content=content))
    assert evidence_integrity(file_record) == ("verified", file_record.sha256_hash)

    file_record.sha256_hash = "0" * 64
    assert evidence_integrity(file_record) == ("mismatch", hashlib.sha256(content).hexdigest())


def test_evidence_api_upload_and_verification_use_private_storage_without_contract_changes(
    monkeypatch, supabase_env
):
    from urllib.parse import unquote, urlsplit

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import StaticPool

    from app.api.evidence import router as evidence_router
    from app.database import Base, get_db
    from app.models import Case, EvidenceFile

    objects = {}
    fail_storage = {"enabled": False}

    def fake_request(method, url, **kwargs):
        if fail_storage["enabled"]:
            return FakeResponse(
                status_code=503,
                payload={"message": "test-service-role-secret private evidence"},
            )
        object_path = urlsplit(url).path
        prefix = "/storage/v1/object/"
        if "/authenticated/" in object_path:
            object_path = object_path.replace("/authenticated/", "/", 1)
        object_key = unquote(object_path.split(prefix + "private-evidence/", 1)[-1])
        if method == "POST":
            objects[object_key] = kwargs["content"]
            return FakeResponse(status_code=200)
        if method == "GET":
            if object_key not in objects:
                return FakeResponse(status_code=404)
            return FakeResponse(content=objects[object_key])
        if method == "DELETE":
            for key in kwargs["json"]["prefixes"]:
                objects.pop(key, None)
            return FakeResponse(status_code=200)
        raise AssertionError("Unexpected storage HTTP method.")

    monkeypatch.setattr(storage.httpx, "request", fake_request)
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        case = Case(case_number="STORAGE-API-01", title="Storage adapter check")
        db.add(case)
        db.commit()
        case_id = case.id

    app = FastAPI()
    app.include_router(evidence_router)

    def override_get_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        uploaded = client.post(
            f"/api/cases/{case_id}/evidence",
            files={"file": ("review.txt", b"first line\nsecond line", "text/plain")},
        )
        assert uploaded.status_code == 201
        metadata = uploaded.json()
        assert set(metadata) == {
            "id", "case_id", "original_filename", "stored_filename", "file_size",
            "sha256_hash", "encoding", "line_count", "uploaded_at",
        }
        assert metadata["case_id"] == case_id
        assert metadata["stored_filename"].startswith(f"case_{case_id}/")
        assert metadata["sha256_hash"] == hashlib.sha256(b"first line\nsecond line").hexdigest()
        assert metadata["line_count"] == 2

        verify_url = f"/api/cases/{case_id}/evidence/{metadata['id']}/verify"
        verified = client.get(verify_url)
        assert verified.status_code == 200
        assert verified.json()["verification_status"] == "verified"
        assert verified.json()["computed_hash"] == metadata["sha256_hash"]

        objects[metadata["stored_filename"]] = b"tampered bytes"
        corrupted = client.get(verify_url)
        assert corrupted.status_code == 200
        assert corrupted.json()["verification_status"] == "corrupted"

        fail_storage["enabled"] = True
        failed_upload = client.post(
            f"/api/cases/{case_id}/evidence",
            files={"file": ("unavailable.txt", b"must not be indexed", "text/plain")},
        )
        assert failed_upload.status_code == 503
        assert "test-service-role-secret" not in failed_upload.text
        with Session(engine) as db:
            assert db.query(EvidenceFile).filter_by(original_filename="unavailable.txt").count() == 0
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_http_transport_error_is_sanitized(monkeypatch, supabase_env):
    import httpx

    def fail_request(*args, **kwargs):
        raise httpx.ConnectError("test-service-role-secret private evidence")

    monkeypatch.setattr(storage.httpx, "request", fail_request)
    with pytest.raises(StorageError) as error:
        save_original_file(41, "note.txt", b"private evidence")
    assert "test-service-role-secret" not in str(error.value)
    assert "private evidence" not in str(error.value)
