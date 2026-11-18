"""Offline checks for PostgreSQL URL setup and generated schema/query SQL."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable

from app.database import normalize_database_url
from app.models import Base, Case, CaseStatus, EvidenceFile, EvidenceLine


def test_postgresql_url_uses_psycopg_and_requires_tls_by_default():
    url = normalize_database_url("postgresql://demo:secret@db.example.test:5432/chronicle")

    assert url.startswith("postgresql+psycopg://demo:secret@db.example.test:5432/chronicle?")
    assert "sslmode=require" in url
    assert "connect_timeout=10" in url


def test_supabase_postgres_alias_and_strong_tls_settings_are_preserved():
    url = normalize_database_url("postgres://demo:secret@db.example.test/chronicle?sslmode=verify-full")

    assert url.startswith("postgresql+psycopg://")
    assert "sslmode=verify-full" in url


@pytest.mark.parametrize("sslmode", ["disable", "allow", "prefer"])
def test_postgresql_url_rejects_tls_modes_that_can_downgrade(sslmode):
    with pytest.raises(ValueError, match="must use sslmode"):
        normalize_database_url(f"postgresql://demo@localhost/chronicle?sslmode={sslmode}")


def test_sqlite_url_is_kept_unchanged():
    url = "sqlite:///local.db"

    assert normalize_database_url(url) == url


def test_postgresql_url_rejects_uninstalled_driver():
    with pytest.raises(ValueError, match="installed psycopg driver"):
        normalize_database_url("postgresql+psycopg2://demo@localhost/chronicle")


def test_initial_schema_compiles_for_postgresql_with_constraints_and_enum():
    tables = {table.name: str(CreateTable(table).compile(dialect=postgresql.dialect()))
              for table in Base.metadata.sorted_tables}

    assert set(tables) == {"cases", "evidence_files", "evidence_lines"}
    assert "casestatus" in tables["cases"]
    assert "FOREIGN KEY(case_id) REFERENCES cases (id) ON DELETE CASCADE" in tables["evidence_files"]
    assert "FOREIGN KEY(evidence_file_id) REFERENCES evidence_files (id) ON DELETE CASCADE" in tables["evidence_lines"]
    assert Case.__table__.c.status.type.enums == ["OPEN", "IN_PROGRESS", "CLOSED"]
    assert CaseStatus.OPEN.value == "Open"
    assert any(constraint.name == "uq_case_sha256" for constraint in EvidenceFile.__table__.constraints)
    assert any(constraint.name == "uq_file_line_number" for constraint in EvidenceLine.__table__.constraints)


def test_case_insensitive_literal_search_compiles_to_postgresql_ilike():
    statement = (
        EvidenceLine.__table__.select()
        .where(EvidenceLine.content.ilike(r"%100\%\_approved%", escape="\\"))
    )

    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "ILIKE" in sql
    assert "ESCAPE" in sql


def test_sqlite_schema_and_relationship_round_trip_in_memory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        case = Case(case_number="SQLITE-ROUNDTRIP", title="Local compatibility")
        case.evidence_files.append(EvidenceFile(
            original_filename="sample.txt",
            stored_filename="opaque-key.txt",
            file_size=4,
            sha256_hash="a" * 64,
            encoding="utf-8",
            line_count=1,
        ))
        case.evidence_files[0].lines.append(EvidenceLine(line_number=1, content="demo"))
        session.add(case)
        session.commit()
        loaded = session.query(Case).filter_by(case_number="SQLITE-ROUNDTRIP").one()

        assert loaded.status == CaseStatus.OPEN
        assert loaded.evidence_files[0].lines[0].line_number == 1
        assert loaded.evidence_files[0].lines[0].content == "demo"

    engine.dispose()
