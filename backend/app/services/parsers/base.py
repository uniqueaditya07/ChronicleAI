from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, List
from app.schemas.source import ParsedDocument, ParsedChunk

class BaseParser(ABC):
    @abstractmethod
    def can_handle(self, file_type: str, extension: str) -> bool:
        """Determines if the parser can handle the given file type or extension."""
        pass

    @abstractmethod
    def parse(self, file_path: Path, metadata: Dict[str, Any] = None) -> ParsedDocument:
        """
        Parses the file into a deterministic ParsedDocument.
        Must preserve structural boundaries, positional metadata, and avoid semantic inference.
        """
        pass
