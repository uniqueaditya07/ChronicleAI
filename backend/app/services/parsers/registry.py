from typing import Optional
from app.services.parsers.base import BaseParser
from app.services.parsers.pdf_parser import PDFParser
from app.services.parsers.docx_parser import DOCXParser
from app.services.parsers.txt_parser import TXTParser
from app.services.parsers.csv_parser import CSVParser
from app.services.parsers.json_parser import JSONParser
from app.services.parsers.log_parser import LOGParser

class ParserRegistry:
    def __init__(self):
        self.parsers = [
            PDFParser(),
            DOCXParser(),
            TXTParser(),
            CSVParser(),
            JSONParser(),
            LOGParser()
        ]

    def get_parser(self, file_type: str, extension: str) -> Optional[BaseParser]:
        """Resolves the appropriate parser for the file extension."""
        ext_clean = extension.lower().lstrip(".")
        for parser in self.parsers:
            if parser.can_handle(file_type, ext_clean):
                return parser
        return None
