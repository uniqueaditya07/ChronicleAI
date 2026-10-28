def test_case_persistence_across_sessions():
    import os
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from fastapi.testclient import TestClient
    from app.main import app
    from app.database import Base, get_db

    pers_db_file = "test_persistence.db"
    pers_db_url = f"sqlite:///{pers_db_file}"
    if os.path.exists(pers_db_file):
        os.remove(pers_db_file)

    engine = create_engine(pers_db_url, connect_args={"check_same_thread": False})
    SessionMaker = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override():
        db = SessionMaker()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    client = TestClient(app)

    # Session 1: Create case
    res1 = client.post("/api/cases", json={
        "case_number": "PERSIST-01",
        "title": "Persistent Crime Unit",
        "status": "In Progress"
    })
    assert res1.status_code == 201
    case_id = res1.json()["id"]

    # "Restart": Reconnect to same database engine/file
    engine.dispose()
    new_engine = create_engine(pers_db_url, connect_args={"check_same_thread": False})
    NewSessionMaker = sessionmaker(autocommit=False, autoflush=False, bind=new_engine)

    def new_override():
        db = NewSessionMaker()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = new_override
    new_client = TestClient(app)

    # Session 2: Read case
    res2 = new_client.get(f"/api/cases/{case_id}")
    assert res2.status_code == 200
    assert res2.json()["case_number"] == "PERSIST-01"
    assert res2.json()["title"] == "Persistent Crime Unit"

    # Clean up
    new_engine.dispose()
    if os.path.exists(pers_db_file):
        try:
            os.remove(pers_db_file)
        except OSError:
            pass
