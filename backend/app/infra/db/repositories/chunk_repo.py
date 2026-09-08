from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.domain.models.chunk import Chunk
from app.infra.db.models_orm import ChunkORM


class ChunkRepository:
    """Persistence operations for document chunks."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, chunk: Chunk) -> Chunk:
        """Persist a single chunk."""

        existing = self.get_by_id(chunk.id)

        if existing is not None:
            return existing

        orm_chunk = ChunkORM(
            id=chunk.id,
            document_id=chunk.document_id,
            page_number=chunk.page_number,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            char_start=chunk.char_start,
            char_end=chunk.char_end,
            token_count=chunk.token_count,
        )

        self.db.add(orm_chunk)
        self.db.flush()

        return self._to_domain(orm_chunk)

    def create_many(self, chunks: list[Chunk]) -> list[Chunk]:
        """Persist multiple chunks in one transaction."""

        if not chunks:
            return []

        created: list[Chunk] = []

        for chunk in chunks:
            created.append(self.create(chunk))

        self.db.flush()

        return created

    def get_by_id(
        self,
        chunk_id: str,
    ) -> Chunk | None:
        """Find a chunk by ID."""

        orm_chunk = self.db.get(
            ChunkORM,
            chunk_id,
        )

        if orm_chunk is None:
            return None

        return self._to_domain(orm_chunk)

    def get_by_document(
        self,
        document_id: str,
    ) -> list[Chunk]:
        """Return all chunks belonging to a document."""

        statement = (
            select(ChunkORM)
            .where(ChunkORM.document_id == document_id)
            .order_by(
                ChunkORM.page_number,
                ChunkORM.chunk_index,
            )
        )

        chunks = self.db.execute(
            statement
        ).scalars().all()

        return [
            self._to_domain(chunk)
            for chunk in chunks
        ]

    def get_by_page(
        self,
        document_id: str,
        page_number: int,
    ) -> list[Chunk]:
        """Return chunks belonging to one PDF page."""

        if page_number < 1:
            raise ValueError("page_number must be at least 1.")

        statement = (
            select(ChunkORM)
            .where(
                ChunkORM.document_id == document_id,
                ChunkORM.page_number == page_number,
            )
            .order_by(ChunkORM.chunk_index)
        )

        chunks = self.db.execute(
            statement
        ).scalars().all()

        return [
            self._to_domain(chunk)
            for chunk in chunks
        ]

    def count_by_document(
        self,
        document_id: str,
    ) -> int:
        """Return the number of chunks for a document."""

        statement = select(ChunkORM.id).where(
            ChunkORM.document_id == document_id
        )

        return len(
            self.db.execute(statement).scalars().all()
        )

    def delete_by_document(
        self,
        document_id: str,
    ) -> int:
        """Delete all chunks belonging to a document."""

        statement = delete(ChunkORM).where(
            ChunkORM.document_id == document_id
        )

        result = self.db.execute(statement)

        self.db.flush()

        return result.rowcount

    @staticmethod
    def _to_domain(
        orm_chunk: ChunkORM,
    ) -> Chunk:
        """Convert a database chunk into the domain model."""

        return Chunk(
            id=orm_chunk.id,
            document_id=orm_chunk.document_id,
            page_number=orm_chunk.page_number,
            chunk_index=orm_chunk.chunk_index,
            text=orm_chunk.text,
            char_start=orm_chunk.char_start,
            char_end=orm_chunk.char_end,
            token_count=orm_chunk.token_count,
        )
