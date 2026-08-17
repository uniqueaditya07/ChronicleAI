import hashlib
import uuid
from pathlib import Path
from typing import Tuple
from app.config import get_settings

settings = get_settings()

class StorageService:
    def __init__(self):
        self.upload_dir = settings.UPLOAD_DIR

    def _get_case_dir(self, case_id: str) -> Path:
        case_dir = self.upload_dir / case_id
        # Prevent path traversal
        if not case_dir.resolve().is_relative_to(self.upload_dir.resolve()):
            raise ValueError("Invalid case ID resulting in path traversal")
        return case_dir

    def save_file(self, case_id: str, original_filename: str, content: bytes) -> Tuple[str, str, int, str]:
        """
        Saves a file deterministically.
        Returns: (stored_filename, relative_path, file_size, content_hash)
        """
        case_dir = self._get_case_dir(case_id)
        case_dir.mkdir(parents=True, exist_ok=True)
        
        # Calculate SHA-256
        file_hash = hashlib.sha256(content).hexdigest()
        file_size = len(content)
        
        # Determine extension from original filename safely
        ext = Path(original_filename).suffix.lower()
        if not ext:
            ext = ".bin" # Fallback if no extension
            
        stored_filename = f"{uuid.uuid4()}{ext}"
        file_path = case_dir / stored_filename
        
        # Write to disk
        file_path.write_bytes(content)
        
        return stored_filename, str(file_path.relative_to(self.upload_dir)), file_size, file_hash

    def get_file_path(self, case_id: str, stored_filename: str) -> Path:
        """Returns the absolute path to the stored file, safely."""
        case_dir = self._get_case_dir(case_id)
        file_path = case_dir / stored_filename
        
        # Prevent path traversal in stored_filename
        if not file_path.resolve().is_relative_to(case_dir.resolve()):
            raise ValueError("Invalid stored filename resulting in path traversal")
            
        return file_path

    def delete_file(self, case_id: str, stored_filename: str) -> bool:
        """Deletes a stored file if it exists. Returns True if deleted, False if not found."""
        try:
            file_path = self.get_file_path(case_id, stored_filename)
            if file_path.exists():
                file_path.unlink()
                return True
        except ValueError:
            pass
        return False
