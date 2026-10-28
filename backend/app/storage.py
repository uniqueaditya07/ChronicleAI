import os
import uuid
import hashlib
from pathlib import Path
from typing import Tuple, List

# Default storage directory: backend/storage/evidence
DEFAULT_STORAGE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "storage", "evidence"
)

def get_storage_root() -> str:
    storage_path = os.getenv("CHRONICLE_STORAGE_DIR", DEFAULT_STORAGE_DIR)
    os.makedirs(storage_path, exist_ok=True)
    return storage_path

def get_case_storage_dir(case_id: int) -> str:
    root = get_storage_root()
    case_dir = os.path.join(root, f"case_{case_id}")
    os.makedirs(case_dir, exist_ok=True)
    return case_dir

def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def validate_and_decode_txt(data: bytes) -> Tuple[str, str, List[str]]:
    """
    Validates that bytes represent valid text.
    Rejects binary/null-byte files.
    Decodes using UTF-8 (or UTF-8-sig if BOM is present).
    Returns (encoding, decoded_text, list_of_lines).
    """
    # Reject binary files containing null bytes
    if b"\x00" in data:
        raise ValueError("Binary content detected: file contains null bytes and is not valid plain text.")

    # Detect UTF-8 with BOM or standard UTF-8
    encoding = "utf-8"
    if data.startswith(b"\xef\xbb\xbf"):
        encoding = "utf-8-sig"

    try:
        decoded_text = data.decode(encoding)
    except UnicodeDecodeError as e:
        raise ValueError(f"Encoding error: file is not valid {encoding} text ({str(e)}).")

    # Split lines preserving original lines and line endings
    # Python splitlines() preserves blank lines.
    # Note: splitlines() handles \r\n, \n, and \r.
    raw_lines = decoded_text.splitlines()

    return encoding, decoded_text, raw_lines

def save_original_file(case_id: int, original_filename: str, data: bytes) -> Tuple[str, str]:
    """
    Saves original bytes under the case-specific storage directory using a safe UUID.
    Returns (stored_filename, full_file_path).
    Prevents path traversal and never uses user-supplied filenames on disk.
    """
    case_dir = get_case_storage_dir(case_id)
    # Generate random unique filename with .bin/.txt suffix
    safe_uuid = uuid.uuid4().hex
    stored_filename = f"{safe_uuid}.txt"
    full_path = os.path.join(case_dir, stored_filename)

    # Ensure path doesn't escape case_dir
    resolved_path = Path(full_path).resolve()
    resolved_case_dir = Path(case_dir).resolve()
    if not str(resolved_path).startswith(str(resolved_case_dir)):
        raise ValueError("Illegal path traversal detected.")

    with open(full_path, "wb") as f:
        f.write(data)

    return stored_filename, full_path

def remove_stored_file(case_id: int, stored_filename: str) -> None:
    """Safely removes a stored file during rollback/cleanup."""
    case_dir = get_case_storage_dir(case_id)
    full_path = os.path.join(case_dir, stored_filename)
    if os.path.exists(full_path):
        try:
            os.remove(full_path)
        except OSError:
            pass
