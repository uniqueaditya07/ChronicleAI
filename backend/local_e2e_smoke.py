"""Disposable local API smoke workflow with mocked Gemini; never uses cloud services."""

import hashlib
import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock


def main():
    with tempfile.TemporaryDirectory(prefix="chronicleai-e2e-") as temp_dir:
        root = Path(temp_dir).resolve()
        os.environ["DATABASE_URL"] = "sqlite:///" + (root / "smoke.sqlite").as_posix()
        os.environ["CHRONICLE_STORAGE_BACKEND"] = "local"
        os.environ["CHRONICLE_STORAGE_DIR"] = str(root / "evidence")
        os.environ["GEMINI_API_KEY"] = "smoke-test-placeholder"
        os.environ.pop("GOOGLE_API_KEY", None)
        os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"

        from fastapi.testclient import TestClient
        from sqlalchemy.orm import sessionmaker
        from app.analysis_service import reset_gemini_client, set_gemini_client
        from app.database import Base, engine, get_db
        from app.main import app
        from app.models import EvidenceFile

        # Reuse the app's configured engine: lifespan.init_db() uses this engine.
        # A second engine pointed at the same SQLite file would leave the app's
        # pool alive after the test engine was disposed, locking the temp DB.
        sessions = sessionmaker(bind=engine)

        def override_db():
            with sessions() as session:
                yield session

        app.dependency_overrides[get_db] = override_db
        content = b"Synthetic transfer was recorded on 12 October 2026.\nWitness met Director Brooks in Pune.\n"

        def mock_gemini(case_id, evidence_id):
            citation = {"evidence_file_id": evidence_id, "start_line": 1, "end_line": 1,
                        "snippet": "Synthetic transfer was recorded"}
            answer_payload = {
                "answer_status": "grounded",
                "answer": {"text": "The synthetic transfer was recorded.", "citations": [citation]},
                "summary": [{"statement": "The synthetic transfer was recorded.",
                    "classification": "documented_observation", "citations": [citation]}],
                "documented_observations": [], "possible_interpretations": [],
                "unresolved_questions": [],
            }
            analysis_payload = {
                "summary": answer_payload["summary"],
                "documented_observations": [], "possible_interpretations": [],
                "unresolved_questions": [],
            }
            fake = MagicMock()
            fake.models.generate_content.side_effect = [
                SimpleNamespace(text=json.dumps(analysis_payload)),
                SimpleNamespace(text=json.dumps(answer_payload)),
            ]
            set_gemini_client(fake)

        def run_workflow(client, case_id=None):
            health = client.get("/api/health")
            assert health.status_code == 200, health.text
            if case_id is None:
                created = client.post("/api/cases", json={
                    "case_number": "E2E-SYNTHETIC-001", "title": "Disposable E2E smoke case"
                })
                assert created.status_code == 201, created.text
                case_id = created.json()["id"]
            case_response = client.get(f"/api/cases/{case_id}")
            assert case_response.status_code == 200, case_response.text
            assert any(item["id"] == case_id for item in client.get("/api/cases").json())

            inventory = client.get(f"/api/cases/{case_id}/evidence")
            if not inventory.json():
                upload = client.post(f"/api/cases/{case_id}/evidence",
                    files={"file": ("synthetic.txt", content, "text/plain")})
                assert upload.status_code == 201, upload.text
                evidence = upload.json()
            else:
                evidence = inventory.json()[0]
            assert evidence["sha256_hash"] == hashlib.sha256(content).hexdigest()
            lines = client.get(f"/api/cases/{case_id}/evidence/{evidence['id']}/lines")
            assert lines.status_code == 200 and lines.json()["total_lines"] == 2
            found = client.get(f"/api/cases/{case_id}/search", params={"q": "Synthetic transfer"})
            assert found.status_code == 200 and found.json()["total_matches"] == 1
            entities = client.get(f"/api/cases/{case_id}/entities")
            assert entities.status_code == 200, entities.text
            verify = client.get(f"/api/cases/{case_id}/evidence/{evidence['id']}/verify")
            assert verify.status_code == 200 and verify.json()["verification_status"] == "verified"
            assert client.get(f"/api/cases/{case_id}/timeline").status_code == 200

            mock_gemini(case_id, evidence["id"])
            response = client.post(f"/api/cases/{case_id}/analysis")
            assert response.status_code == 200, response.text
            analysis = response.json()
            assert analysis["summary"] and analysis["summary"][0]["citations"]
            chat = client.post(f"/api/cases/{case_id}/chat", json={"question": "What was recorded?"})
            assert chat.status_code == 200 and chat.json()["answer"]["citations"]
            report = client.post(f"/api/cases/{case_id}/report", json={"analysis": analysis})
            assert report.status_code == 200 and "Synthetic transfer" in report.text
            return case_id, evidence["id"]

        try:
            Base.metadata.create_all(engine)
            with TestClient(app) as client:
                cid, eid = run_workflow(client)
                foreign = client.post("/api/cases", json={
                    "case_number": "E2E-SYNTHETIC-002", "title": "Isolation check"
                }).json()
                assert client.get(f"/api/cases/{foreign['id']}/evidence/{eid}").status_code == 404
                missing = client.get(f"/api/cases/{cid}/evidence/999999/verify")
                assert missing.status_code == 404
                invalid = client.post(f"/api/cases/{cid}/evidence",
                    files={"file": ("invalid.pdf", b"synthetic", "application/pdf")})
                assert invalid.status_code == 415

            reset_gemini_client()
            with TestClient(app) as restarted_client:
                assert restarted_client.get(f"/api/cases/{cid}").status_code == 200
                assert restarted_client.get(f"/api/cases/{cid}/evidence/{eid}/verify").json()["verification_status"] == "verified"
                assert restarted_client.post(f"/api/cases/{cid}/report", json={}).status_code == 200
                evidence = restarted_client.get(f"/api/cases/{cid}/evidence/{eid}").json()
                original_path = root / "evidence" / f"case_{cid}" / evidence["stored_filename"]
                assert original_path.read_bytes() == content
                original_path.unlink()
                missing = restarted_client.get(f"/api/cases/{cid}/evidence/{eid}/verify")
                assert missing.status_code == 200 and missing.json()["verification_status"] == "missing_file"
                missing_report = restarted_client.post(f"/api/cases/{cid}/report", json={})
                assert missing_report.status_code == 200 and "missing" in missing_report.text.lower()
            print("PASS: disposable API workflow, mocked analysis/chat, report, isolation, and restart persistence")
            print("NOT TESTED: browser UI, Vite proxy, real Uvicorn process, live Gemini, and Supabase")
        finally:
            reset_gemini_client()
            app.dependency_overrides.pop(get_db, None)
            # Both TestClient contexts have exited above; close every pooled
            # SQLite connection before TemporaryDirectory removes the database.
            engine.dispose()


if __name__ == "__main__":
    main()
