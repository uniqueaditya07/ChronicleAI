import pytest
import hashlib
from pathlib import Path
from app.services.storage import StorageService
from app.config import get_settings

@pytest.fixture
def storage_service(tmp_path, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path / "data" / "files")
    return StorageService()

def test_storage_save_file(storage_service, tmp_path):
    case_id = "test-case-123"
    content = b"test content"
    original_filename = "test.txt"
    
    stored_filename, relative_path, size, file_hash = storage_service.save_file(case_id, original_filename, content)
    
    # Path should exist
    abs_path = storage_service.upload_dir / relative_path
    assert abs_path.exists()
    assert abs_path.read_bytes() == content
    
    expected_hash = hashlib.sha256(content).hexdigest()
    assert file_hash == expected_hash
    assert size == len(content)

def test_storage_delete_file(storage_service):
    case_id = "test-case-del"
    stored_name, _, _, _ = storage_service.save_file(case_id, "test.txt", b"1")
    
    assert storage_service.get_file_path(case_id, stored_name).exists()
    
    deleted = storage_service.delete_file(case_id, stored_name)
    assert deleted is True
    assert not storage_service.get_file_path(case_id, stored_name).exists()
    
    # Deleting non-existent
    assert storage_service.delete_file(case_id, "fake.txt") is False

def test_storage_path_traversal_protection(storage_service):
    with pytest.raises(ValueError, match="path traversal"):
        storage_service.save_file("../evil-case", "test.txt", b"bad")
        
    with pytest.raises(ValueError, match="path traversal"):
        storage_service.get_file_path("valid-case", "../evil-file.txt")
