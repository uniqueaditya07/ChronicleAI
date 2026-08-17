import mimetypes
from typing import Tuple
from pathlib import Path
from fastapi import UploadFile, HTTPException, status
from app.config import get_settings

settings = get_settings()

class FileValidator:
    def __init__(self):
        self.allowed_extensions = [ext.lower() for ext in settings.ALLOWED_EXTENSIONS]
        self.max_size_bytes = settings.MAX_UPLOAD_SIZE_BYTES

    def validate_filename_safety(self, filename: str) -> str:
        """Ensures filename has no path traversal components."""
        if not filename:
            raise HTTPException(status_code=400, detail="Filename is empty")
        
        path = Path(filename)
        # Check if absolute
        if path.is_absolute():
            raise HTTPException(status_code=400, detail="Filename must be relative")
        # Check for traversal
        if ".." in path.parts:
            raise HTTPException(status_code=400, detail="Filename contains path traversal")
        # Null bytes
        if "\0" in filename:
            raise HTTPException(status_code=400, detail="Filename contains null byte")
            
        return path.name

    def validate_extension(self, filename: str) -> str:
        """Validates file extension against allowlist."""
        ext = Path(filename).suffix.lower()
        if not ext or ext.startswith('.'):
            ext = ext[1:] # remove dot
            
        if ext not in self.allowed_extensions:
            raise HTTPException(status_code=400, detail=f"Unsupported file extension: {ext}. Allowed: {', '.join(self.allowed_extensions)}")
        return ext

    def validate_content(self, content: bytes, ext: str) -> None:
        """Validates magic bytes / signatures based on extension."""
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="File is empty")
            
        if len(content) > self.max_size_bytes:
            raise HTTPException(status_code=400, detail=f"File exceeds maximum size of {self.max_size_bytes} bytes")

        # Magic bytes checks
        if ext == "pdf":
            if not content.startswith(b"%PDF-"):
                raise HTTPException(status_code=400, detail="Invalid PDF file signature")
        elif ext == "docx":
            if not content.startswith(b"PK"):
                raise HTTPException(status_code=400, detail="Invalid DOCX file signature (missing PK header)")
        # txt, csv, json, log don't have universally strict magic bytes, parser will handle malformed cases

    async def validate_upload(self, file: UploadFile) -> Tuple[str, str, bytes]:
        """
        Validates uploaded file stream.
        Returns: (safe_filename, validated_extension, file_content_bytes)
        """
        filename = file.filename or ""
        safe_filename = self.validate_filename_safety(filename)
        ext = self.validate_extension(safe_filename)
        
        content = await file.read()
        self.validate_content(content, ext)
        
        return safe_filename, ext, content
