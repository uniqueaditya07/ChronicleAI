import os
import uuid
import hashlib
import logging
import re
from pathlib import Path
from typing import Tuple, List, Protocol
from urllib.parse import quote, urlsplit

import httpx

# Default storage directory: backend/storage/evidence
DEFAULT_STORAGE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "storage", "evidence"
)

SUPABASE_STORAGE_TIMEOUT_SECONDS = 30.0
logger = logging.getLogger(__name__)


def _log_failure(operation: str, category: str, upstream_status=None) -> None:
    # Only internal labels and the numeric HTTP status: never URLs, keys, paths,
    # request/response bodies, filenames, or exception text/tracebacks.
    logger.warning(
        "Evidence storage failure backend=supabase operation=%s category=%s upstream_status=%s",
        operation, category, upstream_status if upstream_status is not None else "none",
    )


class StorageError(Exception):
    """Base error for configured evidence storage failures."""


class StorageConfigurationError(StorageError):
    """Storage backend configuration is missing or invalid."""


class StorageNotFoundError(StorageError):
    """A stored evidence object does not exist."""


def _configuration_error(category: str, message: str) -> StorageConfigurationError:
    _log_failure("configure", category)
    return StorageConfigurationError(message)


class EvidenceStorage(Protocol):
    def save(self, case_id: int, data: bytes) -> Tuple[str, str]: ...
    def read(self, case_id: int, stored_filename: str) -> bytes: ...
    def remove(self, case_id: int, stored_filename: str) -> None: ...


class LocalEvidenceStorage:
    """Existing case-scoped filesystem vault."""

    def save(self, case_id: int, data: bytes) -> Tuple[str, str]:
        case_dir = get_case_storage_dir(case_id)
        stored_filename = f"{uuid.uuid4().hex}.txt"
        full_path = os.path.join(case_dir, stored_filename)

        resolved_path = Path(full_path).resolve()
        resolved_case_dir = Path(case_dir).resolve()
        if not resolved_path.is_relative_to(resolved_case_dir):
            raise ValueError("Illegal path traversal detected.")

        with open(full_path, "wb") as evidence_file:
            evidence_file.write(data)
        return stored_filename, full_path

    def read(self, case_id: int, stored_filename: str) -> bytes:
        storage_root = Path(os.getenv("CHRONICLE_STORAGE_DIR", DEFAULT_STORAGE_DIR)).resolve()
        case_dir = (storage_root / f"case_{case_id}").resolve()
        file_path = (case_dir / stored_filename).resolve()
        if not file_path.is_relative_to(case_dir):
            raise ValueError("Illegal path traversal detected.")
        try:
            return file_path.read_bytes()
        except FileNotFoundError as exc:
            raise StorageNotFoundError("Evidence object was not found.") from exc

    def remove(self, case_id: int, stored_filename: str) -> None:
        storage_root = Path(os.getenv("CHRONICLE_STORAGE_DIR", DEFAULT_STORAGE_DIR)).resolve()
        case_dir = (storage_root / f"case_{case_id}").resolve()
        file_path = (case_dir / stored_filename).resolve()
        if not file_path.is_relative_to(case_dir):
            raise ValueError("Illegal path traversal detected.")
        try:
            file_path.unlink(missing_ok=True)
        except OSError:
            # Preserve the existing best-effort local rollback behavior.
            pass


class SupabaseEvidenceStorage:
    """Private Supabase Storage access using backend-only credentials."""

    def __init__(self, project_url: str, service_role_key: str, bucket: str):
        try:
            parsed_url = urlsplit(project_url.strip().rstrip("/"))
        except ValueError:
            raise _configuration_error(
                "invalid_project_url", "Supabase Storage requires a valid HTTPS project URL."
            ) from None
        if (
            parsed_url.scheme != "https"
            or not parsed_url.hostname
            or parsed_url.username
            or parsed_url.password
            or parsed_url.path
            or parsed_url.query
            or parsed_url.fragment
        ):
            raise _configuration_error(
                "invalid_project_url", "Supabase Storage requires a valid HTTPS project URL."
            )
        if not service_role_key.strip() or not bucket.strip():
            raise _configuration_error(
                "missing_credentials_or_bucket", "Supabase Storage credentials and bucket are required."
            )

        key = service_role_key.strip()
        if not key.isascii() or any(
            character.isspace() or ord(character) < 32 or ord(character) == 127
            for character in key
        ):
            raise _configuration_error(
                "invalid_credential_format", "Supabase Storage credential format is invalid."
            )

        self.base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        self.bucket = bucket.strip()
        self.headers = {"apikey": key}
        # Legacy service_role keys are JWTs. New secret keys are opaque API
        # keys; the Supabase gateway authenticates those via apikey alone.
        if not key.startswith("sb_secret_"):
            self.headers["Authorization"] = f"Bearer {key}"

    @classmethod
    def from_environment(cls):
        project_url = os.getenv("SUPABASE_URL", "")
        service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        bucket = os.getenv("SUPABASE_STORAGE_BUCKET", "")
        for value, category in (
            (project_url, "missing_supabase_url"),
            (service_role_key, "missing_service_role_key"),
            (bucket, "missing_storage_bucket"),
        ):
            if not value.strip():
                raise _configuration_error(
                    category,
                    "Supabase Storage requires SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, and SUPABASE_STORAGE_BUCKET.",
                )
        return cls(project_url, service_role_key, bucket)

    def _object_key(self, case_id: int, stored_filename: str = "") -> str:
        if stored_filename:
            expected_prefix = f"case_{case_id}/"
            if not stored_filename.startswith(expected_prefix):
                raise ValueError("Evidence object does not belong to the requested case.")
            name = stored_filename[len(expected_prefix):]
            if not re.fullmatch(r"[0-9a-f]{32}\.txt", name):
                raise ValueError("Invalid evidence object key.")
            return stored_filename
        return f"case_{case_id}/{uuid.uuid4().hex}.txt"

    def _object_url(self, key: str, *, authenticated_download: bool = False) -> str:
        access_path = "authenticated/" if authenticated_download else ""
        return (
            f"{self.base_url}/storage/v1/object/"
            f"{access_path}{quote(self.bucket, safe='')}/{quote(key, safe='/')}"
        )

    @staticmethod
    def _failure_category(response) -> str:
        # Both modern codes and legacy error shapes occur in Storage. Map to
        # fixed labels instead of logging upstream text, which can echo secrets.
        try:
            payload = response.json()
        except (ValueError, AttributeError):
            payload = {}
        if isinstance(payload, dict):
            categories = {
                "NoSuchBucket": "bucket_not_found",
                "NoSuchKey": "object_not_found",
                "InvalidJWT": "authentication",
                "AccessDenied": "authorization",
                "InvalidMimeType": "mime_type_rejected",
                "invalid_mime_type": "mime_type_rejected",
                "EntityTooLarge": "file_size_limit",
                "InvalidBucketName": "invalid_bucket",
                "InvalidKey": "invalid_object_key",
                "ResourceAlreadyExists": "object_conflict",
                "KeyAlreadyExists": "object_conflict",
                "DatabaseTimeout": "upstream_timeout",
                "TenantNotFound": "storage_not_provisioned",
            }
            for field in ("code", "error"):
                code = payload.get(field)
                if isinstance(code, str) and code in categories:
                    return categories[code]
            # Legacy missing-bucket responses often use HTTP 400/not_found.
            if payload.get("message") == "Bucket not found":
                return "bucket_not_found"
            if payload.get("message") == "new row violates row-level security policy":
                return "authorization"
        status_categories = {
            400: "bad_request", 401: "authentication", 403: "authorization",
            404: "not_found", 409: "object_conflict", 413: "file_size_limit",
            415: "mime_type_rejected", 429: "rate_limited",
        }
        default = "upstream_unavailable" if response.status_code >= 500 else "unexpected_response"
        return status_categories.get(response.status_code, default)

    @classmethod
    def _log_response_failure(cls, operation: str, response) -> None:
        _log_failure(operation, cls._failure_category(response), response.status_code)

    @staticmethod
    def _is_missing_response(response) -> bool:
        if response.status_code == 404:
            return True
        try:
            payload = response.json()
        except (ValueError, AttributeError):
            return False
        return (
            isinstance(payload, dict)
            and str(payload.get("statusCode", "")) == "404"
            and payload.get("error") == "not_found"
        )

    def _request(self, method: str, key: str, *, content=None, json_body=None):
        headers = dict(self.headers)
        if content is not None:
            headers["Content-Type"] = "text/plain"
            headers["x-upsert"] = "false"
        try:
            response = httpx.request(
                method,
                self._object_url(key, authenticated_download=(method == "GET")),
                headers=headers,
                content=content,
                json=json_body,
                timeout=SUPABASE_STORAGE_TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as exc:
            operation = "read" if method == "GET" else "upload"
            category = "timeout" if isinstance(exc, httpx.TimeoutException) else "transport_error"
            _log_failure(operation, category)
            raise StorageError("Supabase Storage request failed.") from exc
        return response

    def save(self, case_id: int, data: bytes) -> Tuple[str, str]:
        key = self._object_key(case_id)
        response = self._request("POST", key, content=data)
        if not 200 <= response.status_code < 300:
            self._log_response_failure("upload", response)
            raise StorageError(f"Supabase Storage upload failed (HTTP {response.status_code}).")
        # The key is opaque metadata; no public or signed object URL is returned.
        return key, key

    def read(self, case_id: int, stored_filename: str) -> bytes:
        key = self._object_key(case_id, stored_filename)
        response = self._request("GET", key)
        if not 200 <= response.status_code < 300:
            self._log_response_failure("read", response)
        if self._is_missing_response(response):
            raise StorageNotFoundError("Evidence object was not found.")
        if not 200 <= response.status_code < 300:
            raise StorageError(f"Supabase Storage read failed (HTTP {response.status_code}).")
        return response.content

    def remove(self, case_id: int, stored_filename: str) -> None:
        key = self._object_key(case_id, stored_filename)
        bucket_url = f"{self.base_url}/storage/v1/object/{quote(self.bucket, safe='')}"
        try:
            response = httpx.request(
                "DELETE",
                bucket_url,
                headers={**self.headers, "Content-Type": "application/json"},
                json={"prefixes": [key]},
                timeout=SUPABASE_STORAGE_TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as exc:
            category = "timeout" if isinstance(exc, httpx.TimeoutException) else "transport_error"
            _log_failure("cleanup", category)
            raise StorageError("Supabase Storage cleanup failed.") from exc
        if not 200 <= response.status_code < 300:
            self._log_response_failure("cleanup", response)
        if not 200 <= response.status_code < 300 and not self._is_missing_response(response):
            raise StorageError(f"Supabase Storage cleanup failed (HTTP {response.status_code}).")


def get_storage_backend() -> EvidenceStorage:
    backend_name = os.getenv("CHRONICLE_STORAGE_BACKEND", "local").strip().lower()
    if backend_name == "local":
        return LocalEvidenceStorage()
    if backend_name == "supabase":
        return SupabaseEvidenceStorage.from_environment()
    logger.warning("Evidence storage failure operation=configure category=invalid_backend upstream_status=none")
    raise StorageConfigurationError("CHRONICLE_STORAGE_BACKEND must be 'local' or 'supabase'.")

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


def read_stored_file(case_id: int, stored_filename: str) -> bytes:
    return get_storage_backend().read(case_id, stored_filename)

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
    Saves original bytes in the configured backend using a generated opaque key.
    Returns (stored_filename, local_path_or_key); user filenames never form object keys.
    """
    return get_storage_backend().save(case_id, data)

def remove_stored_file(case_id: int, stored_filename: str) -> None:
    """Safely removes a stored file during rollback/cleanup."""
    try:
        get_storage_backend().remove(case_id, stored_filename)
    except StorageError:
        # Preserve the existing best-effort cleanup semantics.
        pass
