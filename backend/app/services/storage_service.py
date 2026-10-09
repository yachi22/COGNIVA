import os
import uuid
import re
from pathlib import Path
from typing import Tuple, Dict, Any, Optional
from fastapi import UploadFile, HTTPException, status
from app.core.config import settings

# Recognized magic byte signatures for supported enterprise file formats
MAGIC_SIGNATURES = {
    "pdf": [b"%PDF"],
    "docx": [b"PK\x03\x04"],  # Standard ZIP / OpenXML archive header
}


class StorageService:
    """
    Modular file storage service for Cogniva.
    Handles secure disk persistence, file validation, magic byte checking,
    path traversal prevention, and lifecycle cleanup.
    Abstracted to allow seamless migration to S3/Blob storage in future phases.
    """

    def __init__(self, base_dir: Optional[str] = None):
        if base_dir:
            self.base_dir = Path(base_dir).resolve()
        else:
            # Anchor relative to backend root or current working directory
            self.base_dir = Path(settings.STORAGE_DIR).resolve()
        
        self.documents_dir = self.base_dir / "documents"
        self.documents_dir.mkdir(parents=True, exist_ok=True)

    def get_user_storage_dir(self, user_id: uuid.UUID) -> Path:
        """
        Returns and guarantees existence of user-isolated storage directory.
        storage/documents/<user-id>/
        """
        user_dir = (self.documents_dir / str(user_id)).resolve()
        # Prevent any path traversal escaping documents_dir
        if not str(user_dir).startswith(str(self.documents_dir)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid storage path specification."
            )
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitize original filename to strip directory traversal sequences
        and unwanted control characters.
        """
        # Strip directory path separators
        clean_name = os.path.basename(filename)
        # Keep only alphanumeric, hyphens, underscores, dots, and spaces
        clean_name = re.sub(r'[^a-zA-Z0-9._\-\s]', '_', clean_name).strip()
        if not clean_name:
            clean_name = f"document_{uuid.uuid4().hex[:8]}"
        return clean_name

    def validate_file_metadata(self, filename: str) -> str:
        """
        Validates file extension against allowed extensions.
        Returns normalized lowercase extension (e.g. 'pdf' or 'docx').
        """
        if not filename or "." not in filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file format. Uploaded file must have an extension (.pdf or .docx)."
            )

        ext = filename.rsplit(".", 1)[1].lower()
        if ext not in settings.ALLOWED_EXTENSIONS:
            allowed = ", ".join(f".{e}" for e in settings.ALLOWED_EXTENSIONS)
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported file type '{ext}'. Supported formats: {allowed}"
            )
        return ext

    def validate_magic_bytes(self, header: bytes, file_type: str) -> None:
        """
        Validates file signature magic bytes to prevent renamed malicious files.
        """
        if not header:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty file uploaded. Please upload a valid document."
            )

        signatures = MAGIC_SIGNATURES.get(file_type, [])
        is_valid = any(header.startswith(sig) for sig in signatures)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file content for .{file_type} format. The file header does not match expected format specifications."
            )

    async def save_uploaded_file(
        self,
        file: UploadFile,
        user_id: uuid.UUID
    ) -> Tuple[str, str, str, int, str, Dict[str, Any]]:
        """
        Validates and securely saves an uploaded file for an authenticated user.
        
        Returns:
            Tuple of:
            - safe_stored_filename: generated UUID-based filename on disk
            - sanitized_original_filename: safe original filename
            - file_type: 'pdf' or 'docx'
            - total_bytes: size in bytes
            - relative_storage_path: user-relative safe storage path string
        """
        original_name = self.sanitize_filename(file.filename or "uploaded_file")
        file_type = self.validate_file_metadata(original_name)

        user_dir = self.get_user_storage_dir(user_id)
        
        # Read initial chunk to inspect magic bytes and ensure non-empty
        initial_chunk = await file.read(1024)
        if not initial_chunk or len(initial_chunk) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty (0 bytes)."
            )

        self.validate_magic_bytes(initial_chunk, file_type)

        # Generate a collision-free, safe stored filename
        storage_id = uuid.uuid4().hex
        stored_filename = f"{storage_id}.{file_type}"
        target_path = user_dir / stored_filename

        max_size = settings.max_upload_size_bytes
        total_bytes = len(initial_chunk)

        try:
            with open(target_path, "wb") as destination:
                destination.write(initial_chunk)
                
                # Stream the remainder in 64KB chunks to protect server RAM
                chunk_size = 64 * 1024
                while True:
                    chunk = await file.read(chunk_size)
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    if total_bytes > max_size:
                        destination.close()
                        if target_path.exists():
                            target_path.unlink()
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB."
                        )
                    destination.write(chunk)
        except Exception:
            # Clean up partial file on any exception
            if target_path.exists():
                try:
                    target_path.unlink()
                except OSError:
                    pass
            raise

        # User-isolated relative path stored in database (e.g. documents/<user_id>/<stored_name>)
        relative_path = f"documents/{user_id}/{stored_filename}"

        metadata = {
            "size_bytes": total_bytes,
            "content_type": file.content_type or f"application/{file_type}",
            "original_filename": original_name,
            "stored_filename": stored_filename,
        }

        return stored_filename, original_name, file_type, total_bytes, relative_path, metadata

    def get_full_path(self, relative_path: str) -> Path:
        """
        Resolves absolute path for a relative storage path.
        """
        return (self.base_dir / relative_path).resolve()

    def save_extracted_json(
        self,
        user_id: uuid.UUID,
        relative_storage_path: str,
        data: Dict[str, Any]
    ) -> str:
        """
        Saves extracted JSON artifact safely in the user's storage directory.
        """
        full_path = self.get_full_path(relative_storage_path)
        user_dir = self.get_user_storage_dir(user_id)
        if not str(full_path).startswith(str(user_dir)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid storage path."
            )

        json_path = full_path.with_name(f"{full_path.stem}_extracted.json")
        import json
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return f"documents/{user_id}/{json_path.name}"

    def load_extracted_json(
        self,
        user_id: uuid.UUID,
        relative_json_path: str
    ) -> Optional[Dict[str, Any]]:
        """
        Loads extracted JSON artifact with tenant containment verification.
        """
        full_path = self.get_full_path(relative_json_path)
        user_dir = self.get_user_storage_dir(user_id)
        if not str(full_path).startswith(str(user_dir)):
            return None

        if not full_path.exists() or not full_path.is_file():
            return None

        import json
        with open(full_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def delete_stored_file(self, user_id: uuid.UUID, relative_storage_path: str) -> bool:
        """
        Deletes the file and its extracted JSON artifact from disk if they exist,
        enforcing user directory containment.
        """
        # Ensure path stays within user storage directory
        full_path = self.get_full_path(relative_storage_path)
        user_dir = self.get_user_storage_dir(user_id)
        
        # Verify the target file is strictly inside this user's directory
        if not str(full_path).startswith(str(user_dir)):
            return False

        deleted = False
        if full_path.exists() and full_path.is_file():
            try:
                full_path.unlink()
                deleted = True
            except OSError:
                pass

        # Also remove extracted JSON if present
        json_path = full_path.with_name(f"{full_path.stem}_extracted.json")
        if json_path.exists() and json_path.is_file():
            try:
                json_path.unlink()
            except OSError:
                pass

        return deleted


# Singleton instance
storage_service = StorageService()
