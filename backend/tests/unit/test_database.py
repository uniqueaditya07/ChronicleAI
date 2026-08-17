from sqlalchemy import text
from sqlalchemy.orm import Session
from app.models.case import Case


def test_database_session_and_case_model(db_session: Session):
    # Test basic query execution
    result = db_session.execute(text("SELECT 1")).scalar()
    assert result == 1

    # Test Case model instantiation and persistence
    test_case = Case(
        name="Financial Ledger Investigation",
        description="Forensic investigation into wire transfers",
        status="active",
    )
    db_session.add(test_case)
    db_session.commit()
    db_session.refresh(test_case)

    assert test_case.id is not None
    assert len(test_case.id) == 36  # UUID v4 string length
    assert test_case.created_at is not None
    assert test_case.updated_at is not None
    assert test_case.name == "Financial Ledger Investigation"
    assert test_case.status == "active"
