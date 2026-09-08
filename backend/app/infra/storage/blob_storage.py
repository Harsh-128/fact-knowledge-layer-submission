from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

from app.config import settings
from app.core.exceptions import DocumentProcessingError


class BlobStorage:
    """
    Local filesystem implementation of document/blob storage.

    The rest of the application interacts with this class instead of
    directly manipulating files. This makes the storage implementation
    replaceable later with S3, GCS, Azure Blob Storage, etc.
    """

    def __init__(self, base_dir: str | Path | None = None) -> None:
        self.base_dir = Path(
            base_dir or settings.upload_dir
        ).expanduser()

        self.base_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    def save(
        self,
        content: bytes,
        filename: str,
        *,
        object_id: str | None = None,
    ) -> str:
        """
        Save file content and return its storage path.

        The original filename is retained only as a sanitized suffix.
        The generated object ID prevents filename collisions.
        """

        if not content:
            raise DocumentProcessingError(
                "Cannot store an empty file."
            )

        safe_filename = self._sanitize_filename(filename)

        if not safe_filename:
            raise DocumentProcessingError(
                "A valid filename is required."
            )

        object_id = object_id or uuid4().hex

        storage_filename = f"{object_id}_{safe_filename}"
        destination = self.base_dir / storage_filename

        try:
            destination.write_bytes(content)
        except OSError as exc:
            raise DocumentProcessingError(
                f"Unable to store file: {exc}"
            ) from exc

        return str(destination)

    def read(
        self,
        storage_path: str | Path,
    ) -> bytes:
        """Read a stored file."""

        path = Path(storage_path)

        if not path.exists():
            raise DocumentProcessingError(
                f"Stored file does not exist: {path}"
            )

        if not path.is_file():
            raise DocumentProcessingError(
                f"Stored path is not a file: {path}"
            )

        try:
            return path.read_bytes()
        except OSError as exc:
            raise DocumentProcessingError(
                f"Unable to read stored file: {exc}"
            ) from exc

    def delete(
        self,
        storage_path: str | Path,
    ) -> None:
        """Delete a stored file."""

        path = Path(storage_path)

        if not path.exists():
            return

        if not path.is_file():
            raise DocumentProcessingError(
                f"Stored path is not a file: {path}"
            )

        try:
            path.unlink()
        except OSError as exc:
            raise DocumentProcessingError(
                f"Unable to delete stored file: {exc}"
            ) from exc

    def exists(
        self,
        storage_path: str | Path,
    ) -> bool:
        """Return whether a stored file exists."""

        path = Path(storage_path)

        return path.exists() and path.is_file()

    def sha256(
        self,
        content: bytes,
    ) -> str:
        """Calculate the SHA-256 checksum of file content."""

        return hashlib.sha256(content).hexdigest()

    def get_size(
        self,
        storage_path: str | Path,
    ) -> int:
        """Return the size of a stored file in bytes."""

        path = Path(storage_path)

        if not path.exists():
            raise DocumentProcessingError(
                f"Stored file does not exist: {path}"
            )

        try:
            return path.stat().st_size
        except OSError as exc:
            raise DocumentProcessingError(
                f"Unable to determine file size: {exc}"
            ) from exc

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """
        Keep only the filename component and remove unsafe path characters.

        This prevents an uploaded filename such as ../../secret.txt from
        escaping the configured storage directory.
        """

        name = Path(filename).name.strip()

        if not name:
            return ""

        safe_characters = (
            character
            for character in name
            if character.isalnum()
            or character in {
                ".",
                "_",
                "-",
                " ",
            }
        )

        sanitized = "".join(safe_characters)

        return sanitized.strip()


def get_blob_storage() -> BlobStorage:
    """Create the configured blob storage implementation."""

    return BlobStorage()
