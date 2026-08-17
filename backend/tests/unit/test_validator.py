import pytest
from fastapi import UploadFile, HTTPException
import io
from app.services.validator import FileValidator

class MockUploadFile(UploadFile):
    def __init__(self, filename: str, content: bytes):
        super().__init__(file=io.BytesIO(content), filename=filename)
        self._content = content
        
    async def read(self, *args, **kwargs):
        return self._content

@pytest.fixture
def validator():
    return FileValidator()

def test_validator_supported_extensions(validator):
    assert validator.validate_extension("test.pdf") == "pdf"
    assert validator.validate_extension("test.DOCX") == "docx"
    assert validator.validate_extension("TEST.CSV") == "csv"

def test_validator_unsupported_extensions(validator):
    with pytest.raises(HTTPException) as exc:
        validator.validate_extension("test.exe")
    assert exc.value.status_code == 400
    assert "Unsupported file extension" in str(exc.value.detail)

def test_validator_safe_filename(validator):
    assert validator.validate_filename_safety("valid_name.pdf") == "valid_name.pdf"
    
    with pytest.raises(HTTPException) as exc:
        validator.validate_filename_safety("../../etc/passwd.txt")
    assert exc.value.status_code == 400
    
    with pytest.raises(HTTPException) as exc:
        validator.validate_filename_safety("C:/etc/passwd.txt")
    assert exc.value.status_code == 400

def test_validator_file_size(validator):
    # 51MB
    large_content = b"0" * (51 * 1024 * 1024)
    with pytest.raises(HTTPException) as exc:
        validator.validate_content(large_content, "txt")
    assert exc.value.status_code == 400
    assert "exceeds maximum size" in str(exc.value.detail)
    
    # Empty
    with pytest.raises(HTTPException) as exc:
        validator.validate_content(b"", "txt")
    assert exc.value.status_code == 400
    
    # 1MB (valid)
    valid_content = b"0" * (1 * 1024 * 1024)
    validator.validate_content(valid_content, "txt") # Should not raise

def test_validator_pdf_signature(validator):
    valid_pdf = b"%PDF-1.4\n..."
    validator.validate_content(valid_pdf, "pdf")
    
    invalid_pdf = b"This is not a pdf"
    with pytest.raises(HTTPException) as exc:
        validator.validate_content(invalid_pdf, "pdf")
    assert exc.value.status_code == 400
    assert "Invalid PDF" in str(exc.value.detail)

def test_validator_docx_signature(validator):
    valid_docx = b"PK\x03\x04..."
    validator.validate_content(valid_docx, "docx")
    
    invalid_docx = b"This is not a docx"
    with pytest.raises(HTTPException) as exc:
        validator.validate_content(invalid_docx, "docx")
    assert exc.value.status_code == 400
    assert "Invalid DOCX" in str(exc.value.detail)
