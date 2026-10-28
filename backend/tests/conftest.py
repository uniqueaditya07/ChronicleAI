import pytest
from app.database import Base
from app.models import Case, EvidenceFile, EvidenceLine

@pytest.fixture(autouse=True)
def reset_dependency_overrides():
    from app.main import app
    yield
    app.dependency_overrides.clear()
