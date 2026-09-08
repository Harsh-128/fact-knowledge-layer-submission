from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""


class DocumentORM(Base):
    """Database representation of an uploaded PDF."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="application/pdf",
    )
    file_size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    sha256: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        unique=True,
    )
    page_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="uploaded",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class ChunkORM(Base):
    """Database representation of a semantic document chunk."""

    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)

    document_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    page_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    char_start: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    char_end: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    token_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_chunks_document_index",
        ),
    )


class EntityORM(Base):
    """Database representation of a canonical entity."""

    __tablename__ = "entities"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)

    canonical_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
    )

    entity_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="unknown",
    )

    aliases: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
    )

    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1536),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class FactTypeORM(Base):
    """Database representation of an evolving fact schema."""

    __tablename__ = "fact_types"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        unique=True,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    value_schema: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class FactORM(Base):
    """Database representation of a source-grounded fact."""

    __tablename__ = "facts"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)

    document_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    chunk_id: Mapped[str | None] = mapped_column(
        String(100),
        ForeignKey("chunks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    entity_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("entities.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    fact_type_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("fact_types.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    attribute: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
        index=True,
    )

    value: Mapped[Any] = mapped_column(
        JSONB,
        nullable=False,
    )

    unit: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    temporal_scope: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    evidence: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    needs_review: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    extraction_method: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="llm",
    )

    raw_extraction: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class RelationshipORM(Base):
    """Database representation of a relationship between two facts."""

    __tablename__ = "relationships"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)

    source_fact_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("facts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    target_fact_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("facts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    relationship_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    explanation: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    evidence: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    needs_review: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
