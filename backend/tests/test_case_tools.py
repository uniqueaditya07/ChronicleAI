import hashlib
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db
from app.analysis_service import set_gemini_client, reset_gemini_client


@pytest.fixture
def case_client(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'tools.db'}", connect_args={"check_same_thread": False})
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
    monkeypatch.setenv("CHRONICLE_STORAGE_DIR", str(tmp_path / "vault"))
    def override():
        with sessions() as session:
            yield session
    app.dependency_overrides[get_db] = override
    reset_gemini_client()
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    client.close()
    reset_gemini_client()
    app.dependency_overrides.pop(get_db, None)
    engine.dispose()


def seed(client, number="TOOLS-A", content=b"Transfer recorded on 12 October 2026.\nInvoice missing on 2026-10-14."):
    case = client.post("/api/cases", json={"case_number": number, "title": number}).json()
    response = client.post(f'/api/cases/{case["id"]}/evidence', files={"file": (number + ".txt", content, "text/plain")})
    assert response.status_code == 201
    return case["id"], response.json()


def reply(file_id, **overrides):
    payload = {"summary": [{"statement": "A transfer is documented.", "classification": "documented_observation",
        "citations": [{"evidence_file_id": file_id, "start_line": 1, "end_line": 1}]}],
        "documented_observations": [], "possible_interpretations": [], "unresolved_questions": []}
    payload.update(overrides)
    return payload


def mock_response(payload):
    client = MagicMock()
    client.models.generate_content.return_value = SimpleNamespace(text=json.dumps(payload))
    set_gemini_client(client)
    return client


def test_chat_answers_followups_with_case_scoped_evidence(case_client):
    case_id, file = seed(case_client, content=b"ONLY_CASE_A: Transfer recorded on 12 October 2026.")
    seed(case_client, "TOOLS-B", b"ONLY_CASE_B_PRIVATE: Different evidence.")
    mock = mock_response(reply(file["id"]))
    response = case_client.post(f"/api/cases/{case_id}/chat", json={"question": "What happened next?",
        "history": [{"case_id": case_id, "question": "Was a transfer recorded?"}]})
    assert response.status_code == 200
    data = response.json()
    assert data["answer_status"] == "grounded"
    assert data["summary"][0]["citations"][0]["original_filename"] == file["original_filename"]
    prompt = mock.models.generate_content.call_args.kwargs["contents"]
    assert "ONLY_CASE_A" in prompt and "ONLY_CASE_B_PRIVATE" not in prompt
    assert "What happened next?" in prompt and "Was a transfer recorded?" in prompt


def test_chat_rejects_history_from_another_case(case_client):
    case_id, file = seed(case_client)
    mock = mock_response(reply(file["id"]))
    response = case_client.post(f"/api/cases/{case_id}/chat", json={"question": "Question?",
        "history": [{"case_id": case_id + 1, "question": "Foreign history"}]})
    assert response.status_code == 422
    mock.models.generate_content.assert_not_called()


@pytest.mark.parametrize("coordinate", [999, True, 1.5, "1"])
def test_chat_never_accepts_fabricated_or_coerced_line_references(case_client, coordinate):
    case_id, file = seed(case_client)
    payload = reply(file["id"])
    payload["summary"][0]["citations"][0].update(start_line=coordinate, end_line=coordinate)
    mock_response(payload)
    response = case_client.post(f"/api/cases/{case_id}/chat", json={"question": "Question?"})
    if type(coordinate) is int:
        assert response.status_code == 200
        assert response.json()["answer_status"] == "insufficient_evidence"
        assert response.json()["summary"] == []
    else:
        assert response.status_code == 502


def test_chat_foreign_case_citation_is_quarantined(case_client):
    case_id, _ = seed(case_client)
    _, foreign = seed(case_client, "FOREIGN", b"Foreign facts.")
    mock_response(reply(foreign["id"]))
    response = case_client.post(f"/api/cases/{case_id}/chat", json={"question": "Question?"})
    assert response.status_code == 200
    assert response.json()["summary"] == []
    assert response.json()["answer_status"] == "insufficient_evidence"


def test_chat_acknowledges_unsupported_questions(case_client):
    case_id, _ = seed(case_client)
    mock_response({"summary": [], "documented_observations": [], "possible_interpretations": [],
        "unresolved_questions": ["No evidence establishes who approved it."]})
    response = case_client.post(f"/api/cases/{case_id}/chat", json={"question": "Who approved it?"})
    assert response.status_code == 200
    assert response.json()["answer_status"] == "insufficient_evidence"
    assert "does not support" in response.json()["message"]


def test_chat_labels_interpretation_only_answer(case_client):
    case_id, file = seed(case_client)
    payload = reply(file["id"])
    interpretation = payload["summary"].pop()
    interpretation["classification"] = "possible_interpretation"
    payload["possible_interpretations"] = [interpretation]
    mock_response(payload)
    response = case_client.post(f"/api/cases/{case_id}/chat", json={"question": "What could this mean?"})
    assert response.status_code == 200
    assert response.json()["answer_status"] == "interpretation_only"


@pytest.mark.parametrize("error,status", [("503 UNAVAILABLE private-token", 503), ("timeout private-token", 503), ("401 API_KEY_INVALID private-token", 502)])
def test_chat_preserves_sanitized_gemini_failures(case_client, error, status):
    case_id, file = seed(case_client)
    mock = mock_response(reply(file["id"]))
    mock.models.generate_content.side_effect = Exception(error)
    response = case_client.post(f"/api/cases/{case_id}/chat", json={"question": "Question?"})
    assert response.status_code == status
    assert "private-token" not in response.text


@pytest.mark.parametrize("question", ["", "  ", "\ud800", "x" * 2001])
def test_chat_invalid_questions_return_safe_422(case_client, question):
    case_id, _ = seed(case_client)
    response = case_client.post(f"/api/cases/{case_id}/chat", content=json.dumps({"question": question}), headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert "input" not in response.json().get("detail", {})


def test_chat_empty_case_requires_no_gemini_call(case_client):
    case = case_client.post("/api/cases", json={"case_number": "EMPTY", "title": "Empty"}).json()
    mock = mock_response({})
    response = case_client.post(f'/api/cases/{case["id"]}/chat', json={"question": "What is known?"})
    assert response.status_code == 200
    assert response.json()["answer_status"] == "insufficient_evidence"
    mock.models.generate_content.assert_not_called()


@pytest.mark.parametrize("payload", [{}, [], {"summary": 7}, reply(1, unresolved_questions=["\udfff"])])
def test_chat_reuses_structure_and_unicode_validation(case_client, payload):
    case_id, _ = seed(case_client)
    mock_response(payload)
    response = case_client.post(f"/api/cases/{case_id}/chat", json={"question": "Question?"})
    assert response.status_code == 502
    assert response.json()["detail"] == "Failed to parse structured JSON response from Gemini model."


def test_timeline_orders_explicit_dates_and_preserves_sources(case_client):
    original = b"Late event on 2026-10-15.\nEarly event on 12 October 2026.\nMiddle event on October 14, 2026."
    case_id, file = seed(case_client, content=original)
    seed(case_client, "OTHER", b"OTHER_CASE event on 2026-01-01.")
    response = case_client.get(f"/api/cases/{case_id}/timeline")
    assert response.status_code == 200
    data = response.json()
    assert [event["normalized_date"] for event in data["events"]] == ["2026-10-12", "2026-10-14", "2026-10-15"]
    for event in data["events"]:
        citation = event["citations"][0]
        assert citation["evidence_file_id"] == file["id"]
        assert event["description"] == original.decode().splitlines()[citation["start_line"] - 1]
    assert data["undated"] == []
    assert "OTHER_CASE" not in response.text


@pytest.mark.parametrize("text,status,normalized", [
    ("03/04/2026", "ambiguous", None), ("31/02/2026", "invalid", None),
    ("October 2026", "incomplete", None), ("yesterday", "incomplete", None),
    ("15/10/2026", "explicit", "2026-10-15"), ("10/15/2026", "explicit", "2026-10-15"),
    ("03/03/2026", "explicit", "2026-03-03"), ("2026-02-29", "invalid", None),
])
def test_timeline_never_guesses_ambiguous_or_invalid_dates(case_client, text, status, normalized):
    case_id, _ = seed(case_client, content=("Event dated " + text).encode())
    response = case_client.get(f"/api/cases/{case_id}/timeline")
    assert response.status_code == 200
    events = response.json()["events"] + response.json()["undated"]
    assert len(events) == 1
    assert events[0]["date_status"] == status
    assert events[0]["normalized_date"] == normalized


def test_timeline_multiple_dates_do_not_invent_event_associations(case_client):
    case_id, _ = seed(case_client, content=b"A payment on 12 October 2026 was discussed on 15 October 2026.")
    data = case_client.get(f"/api/cases/{case_id}/timeline").json()
    assert len(data["events"]) == 2
    assert all("multiple dates" in event["note"] for event in data["events"])
    assert data["events"][0]["description"] == data["events"][1]["description"]


def test_timeline_empty_and_unknown_cases(case_client):
    case = case_client.post("/api/cases", json={"case_number": "EMPTY", "title": "Empty"}).json()
    data = case_client.get(f'/api/cases/{case["id"]}/timeline').json()
    assert data["events"] == data["undated"] == []
    assert case_client.get("/api/cases/99999/timeline").status_code == 404


def test_report_contains_integrity_timeline_findings_and_local_citations(case_client):
    case_id, file = seed(case_client)
    payload = reply(file["id"], case_id=case_id, unresolved_questions=["Where is the invoice?"])
    mock = mock_response({})
    response = case_client.post(f"/api/cases/{case_id}/report", json={"analysis": payload})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert f'ChronicleAI-case-{case_id}.html' in response.headers["content-disposition"]
    for expected in ("TOOLS-A", file["sha256_hash"], "verified", "Documented observations", "Possible interpretations", "Evidence-linked timeline", "Where is the invoice?", "2026-10-12", "Print / Save as PDF"):
        assert expected in response.text
    assert f'href="#evidence-{file["id"]}-L1"' in response.text
    assert f'id="evidence-{file["id"]}-L1"' in response.text
    assert f"Case ID: {case_id}" in response.text
    assert "Created (UTC)" in response.text and "Updated (UTC)" in response.text
    mock.models.generate_content.assert_not_called()


def test_report_escapes_case_evidence_and_ai_html(case_client):
    case_id, file = seed(case_client, content=b'<script>alert("EVIDENCE")</script> on 2026-10-12.')
    case_client.patch(f"/api/cases/{case_id}", json={"title": "<img src=x onerror=alert(1)>"})
    payload = reply(file["id"], case_id=case_id)
    payload["summary"][0]["statement"] = "<script>alert('MODEL')</script>"
    response = case_client.post(f"/api/cases/{case_id}/report", json={"analysis": payload})
    assert response.status_code == 200
    assert "<script>" not in response.text and "<img" not in response.text
    assert "&lt;script&gt;" in response.text and "&lt;img" in response.text


def test_report_revalidates_and_quarantines_foreign_citations(case_client):
    case_id, file = seed(case_client)
    _, foreign = seed(case_client, "OTHER", b"SECRET_FOREIGN_TEXT")
    payload = reply(foreign["id"], case_id=case_id)
    response = case_client.post(f"/api/cases/{case_id}/report", json={"analysis": payload})
    assert response.status_code == 200
    assert "SECRET_FOREIGN_TEXT" not in response.text
    assert "Quarantined" in response.text
    payload["case_id"] = case_id + 1
    assert case_client.post(f"/api/cases/{case_id}/report", json={"analysis": payload}).status_code == 422


@pytest.mark.parametrize("mutation", ["missing", "float", "surrogate"])
def test_report_rejects_malformed_analysis_snapshots(case_client, mutation):
    case_id, file = seed(case_client)
    payload = reply(file["id"], case_id=case_id)
    if mutation == "missing": del payload["summary"]
    elif mutation == "float": payload["summary"][0]["citations"][0]["start_line"] = 1.5
    else: payload["summary"][0]["statement"] = "\ud800"
    response = case_client.post(f"/api/cases/{case_id}/report", content=json.dumps({"analysis": payload}), headers={"Content-Type": "application/json"})
    assert response.status_code == 422


def test_report_without_analysis_is_explicit_and_handles_missing_file(case_client, tmp_path):
    case_id, file = seed(case_client)
    path = tmp_path / "vault" / f"case_{case_id}" / file["stored_filename"]
    path.unlink()
    response = case_client.post(f"/api/cases/{case_id}/report", json={})
    assert response.status_code == 200
    assert "No AI analysis snapshot supplied" in response.text
    assert "missing" in response.text


def test_tools_do_not_modify_evidence_or_database_records(case_client, tmp_path):
    case_id, file = seed(case_client)
    path = tmp_path / "vault" / f"case_{case_id}" / file["stored_filename"]
    before = path.read_bytes()
    mock_response(reply(file["id"]))
    assert case_client.post(f"/api/cases/{case_id}/chat", json={"question": "What happened?"}).status_code == 200
    assert case_client.get(f"/api/cases/{case_id}/timeline").status_code == 200
    assert case_client.post(f"/api/cases/{case_id}/report", json={}).status_code == 200
    assert path.read_bytes() == before
    assert hashlib.sha256(before).hexdigest() == file["sha256_hash"]
    assert case_client.get(f"/api/cases/{case_id}/evidence/{file['id']}").json() == file


@pytest.mark.parametrize("configured", [False, True])
def test_chat_configuration_failures_do_not_expose_keys(case_client, monkeypatch, configured):
    from google import genai
    case_id, _ = seed(case_client)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    constructor = MagicMock(side_effect=ValueError("private-api-key initialization error"))
    monkeypatch.setattr(genai, "Client", constructor)
    if configured:
        monkeypatch.setenv("GEMINI_API_KEY", "private-api-key")
    response = case_client.post(f"/api/cases/{case_id}/chat", json={"question": "What happened?"})
    assert response.status_code == 503
    assert "private-api-key" not in response.text
    assert constructor.call_count == int(configured)


def test_report_detects_integrity_mismatch_without_rewriting_evidence(case_client, tmp_path):
    case_id, file = seed(case_client)
    path = tmp_path / "vault" / f"case_{case_id}" / file["stored_filename"]
    path.write_bytes(b"Simulated external damage in disposable test vault only.")
    before = path.read_bytes()
    response = case_client.post(f"/api/cases/{case_id}/report", json={})
    assert response.status_code == 200
    assert "mismatch" in response.text and file["sha256_hash"] in response.text
    assert hashlib.sha256(before).hexdigest() in response.text
    assert path.read_bytes() == before


def test_chat_rejects_excessive_history_without_calling_gemini(case_client):
    case_id, _ = seed(case_client)
    mock = mock_response({})
    response = case_client.post(f"/api/cases/{case_id}/chat", json={"question": "Follow-up?",
        "history": [{"case_id": case_id, "question": "Previous?"}] * 7})
    assert response.status_code == 422
    mock.models.generate_content.assert_not_called()


@pytest.mark.parametrize("endpoint", ["analysis", "chat"])
@pytest.mark.parametrize("override,expected", [
    (None, "gemini-3.5-flash-lite"),
    ("gemini-3.8-flash", "gemini-3.8-flash"),
])
def test_presentation_model_and_environment_override_are_shared_by_analysis_and_chat(
    case_client, monkeypatch, endpoint, override, expected,
):
    if override is None:
        monkeypatch.delenv("GEMINI_MODEL", raising=False)
    else:
        monkeypatch.setenv("GEMINI_MODEL", override)
    case_id, file = seed(case_client)
    mock = mock_response(reply(file["id"]))
    request = {"json": {"question": "What is documented?"}} if endpoint == "chat" else {}
    response = case_client.post(f"/api/cases/{case_id}/{endpoint}", **request)
    assert response.status_code == 200
    assert response.json()["model_used"] == expected
    call = mock.models.generate_content.call_args.kwargs
    assert call["model"] == expected
    assert call["config"].response_mime_type == "application/json"
    assert call["config"].temperature == 0.2
    assert response.json()["summary"][0]["citations"][0]["evidence_file_id"] == file["id"]


@pytest.mark.parametrize("endpoint", ["analysis", "chat"])
@pytest.mark.parametrize("snippet,expected", [
    ("12 October 2026", "12 October 2026"),
    ("A transfer was recorded", "Transfer recorded on 12 October 2026."),
    ("Transfer recorded...October 2026", "Transfer recorded on 12 October 2026."),
])
def test_quote_snippets_are_verbatim_source_or_rebuilt(case_client, endpoint, snippet, expected):
    case_id, file = seed(case_client)
    payload = reply(file["id"])
    payload["summary"][0]["citations"][0]["snippet"] = snippet
    mock_response(payload)
    request = {"json": {"question": "What was recorded?"}} if endpoint == "chat" else {}
    response = case_client.post(f"/api/cases/{case_id}/{endpoint}", **request)
    assert response.status_code == 200
    citation = response.json()["summary"][0]["citations"][0]
    assert citation["snippet"] == expected
    assert citation["evidence_file_id"] == file["id"]
    assert response.json()["warnings"] == []
