import pytest
from app.services.ingestion import IngestionService
from app.models.case import Case
from app.models.source import Source, SourceChunk
from fastapi import UploadFile
import io

class AsyncMockUploadFile(UploadFile):
    def __init__(self, filename: str, content: bytes):
        super().__init__(file=io.BytesIO(content), filename=filename)
        self._content = content
        
    async def read(self, *args, **kwargs):
        return self._content

@pytest.fixture
def test_upload_dir(tmp_path, monkeypatch):
    from app.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path / "data" / "files")
    return tmp_path

@pytest.mark.asyncio
async def test_ingestion_service_success(db_session, test_upload_dir):
    # Setup test case
    case = Case(name="Test Case")
    db_session.add(case)
    db_session.commit()
    
    service = IngestionService(db=db_session)
    
    content = b"Line 1\n\nLine 2"
    file = AsyncMockUploadFile("test.txt", content)
    
    # Run ingestion
    source = await service.ingest_file(
        case_id=case.id,
        file=file
    )
    
    # Assertions
    assert source.id is not None
    assert source.original_filename == "test.txt"
    assert source.file_type == "txt"
    assert source.processing_status == "completed"
    
    # Verify chunks are in DB
    chunks = db_session.query(SourceChunk).filter(SourceChunk.source_id == source.id).all()
    assert len(chunks) == 2
    assert chunks[0].content_text == "Line 1"
    assert chunks[1].content_text == "Line 2"
    
    # Verify duplicate detection
    with pytest.raises(Exception) as exc:
        file2 = AsyncMockUploadFile("duplicate.txt", content)
        await service.ingest_file(case_id=case.id, file=file2)
    assert exc.value.status_code == 409
        
    # Identical content in DIFFERENT case is allowed
    case2 = Case(name="Test Case 2")
    db_session.add(case2)
    db_session.commit()
    
    file3 = AsyncMockUploadFile("test.txt", content)
    source2 = await service.ingest_file(
        case_id=case2.id,
        file=file3
    )
    assert source2.id is not None
