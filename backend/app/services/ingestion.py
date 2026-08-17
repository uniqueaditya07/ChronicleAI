import logging
from typing import Optional
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.case import Case
from app.models.source import Source, ProcessingStatus
from app.services.storage import StorageService
from app.services.validator import FileValidator
from app.services.parsers.registry import ParserRegistry
from app.services.parsers.chunker import DocumentChunker

logger = logging.getLogger(__name__)

class IngestionService:
    def __init__(self, db: Session):
        self.db = db
        self.storage = StorageService()
        self.validator = FileValidator()
        self.registry = ParserRegistry()
        self.chunker = DocumentChunker()

    async def ingest_file(self, case_id: str, file: UploadFile) -> Source:
        # 1. Validate Case
        case = self.db.query(Case).filter(Case.id == case_id).first()
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        # 2. Validate file
        safe_filename, ext, content = await self.validator.validate_upload(file)

        # 3-5. Storage and Hash (StorageService computes SHA-256 inside)
        stored_filename, rel_path, file_size, file_hash = self.storage.save_file(case_id, safe_filename, content)
        
        try:
            # 6. Create Source in 'processing' status
            source = Source(
                case_id=case_id,
                original_filename=safe_filename,
                stored_filename=stored_filename,
                file_type=ext,
                file_size=file_size,
                content_hash=file_hash,
                processing_status=ProcessingStatus.processing.value
            )
            self.db.add(source)
            self.db.commit()
            self.db.refresh(source)
        except IntegrityError:
            self.db.rollback()
            # Cleanup storage since DB insert failed
            self.storage.delete_file(case_id, stored_filename)
            raise HTTPException(status_code=409, detail="A source with identical content already exists in this case")
        except Exception as e:
            self.db.rollback()
            self.storage.delete_file(case_id, stored_filename)
            raise HTTPException(status_code=500, detail=f"Database error during ingestion: {str(e)}")

        # 7-13. Parse and Chunk
        try:
            parser = self.registry.get_parser(ext, ext)
            if not parser:
                raise ValueError(f"No parser available for {ext}")

            file_path = self.storage.get_file_path(case_id, stored_filename)
            
            # Parse deterministically
            parsed_doc = parser.parse(file_path, {"original_filename": safe_filename})
            
            # Convert to ORM chunks
            source_chunks = self.chunker.chunk_document(source.id, parsed_doc)
            
            # Persist chunks
            if source_chunks:
                self.db.bulk_save_objects(source_chunks)
                
            source.processing_status = ProcessingStatus.completed.value
            if parsed_doc.metadata:
                import json
                source.metadata_json = json.dumps(parsed_doc.metadata)
                
            self.db.commit()
            self.db.refresh(source)
            
        except Exception as e:
            logger.error(f"Ingestion failed for source {source.id}: {str(e)}", exc_info=True)
            self.db.rollback()
            
            # Mark source as failed
            try:
                # We need a fresh transaction to update the source status
                failed_source = self.db.query(Source).filter(Source.id == source.id).first()
                if failed_source:
                    failed_source.processing_status = ProcessingStatus.failed.value
                    failed_source.processing_error = str(e)
                    self.db.commit()
                    self.db.refresh(source)
            except Exception as inner_e:
                logger.error(f"Failed to mark source as failed: {str(inner_e)}")
                self.db.rollback()

        return source
