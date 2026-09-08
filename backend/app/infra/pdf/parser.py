from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pymupdf

from app.core.exceptions import PDFParsingError, UnsupportedDocumentError


@dataclass(slots=True)
class ParsedPage:
    """
    Parsed representation of a single PDF page.

    The page keeps both plain text and layout blocks so that later
    stages can preserve useful evidence and page-level context.
    """

    page_number: int
    text: str
    blocks: list[dict[str, Any]] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        """Return True when the page contains no meaningful text."""
        return not self.text.strip()

    @property
    def character_count(self) -> int:
        """Return the number of characters extracted from the page."""
        return len(self.text)


@dataclass(slots=True)
class ParsedDocument:
    """
    Parsed representation of an entire PDF document.
    """

    filename: str
    page_count: int
    metadata: dict[str, Any]
    pages: list[ParsedPage]

    @property
    def full_text(self) -> str:
        """Return all page text joined in document order."""
        return "\n".join(page.text for page in self.pages)

    @property
    def non_empty_pages(self) -> list[ParsedPage]:
        """Return only pages containing extracted text."""
        return [page for page in self.pages if not page.is_empty]


class PDFParser:
    """
    PDF parser backed by PyMuPDF.

    The parser is intentionally independent of:
    - specific document names,
    - fact types,
    - LLM providers,
    - database models,
    - business-specific schemas.
    """

    SUPPORTED_CONTENT_TYPE = "application/pdf"

    def parse(self, file_path: str | Path) -> ParsedDocument:
        """
        Parse a PDF from disk.

        Args:
            file_path: Path to the PDF file.

        Returns:
            ParsedDocument containing metadata and page-level text.

        Raises:
            UnsupportedDocumentError: If the file is not a PDF.
            PDFParsingError: If the PDF cannot be opened or parsed.
        """
        path = Path(file_path)

        if not path.exists():
            raise PDFParsingError(f"PDF file does not exist: {path}")

        if not path.is_file():
            raise PDFParsingError(f"PDF path is not a file: {path}")

        if path.suffix.lower() != ".pdf":
            raise UnsupportedDocumentError(
                f"Unsupported document type: {path.suffix or 'unknown'}"
            )

        try:
            document = pymupdf.open(path)
        except Exception as exc:
            raise PDFParsingError(
                f"Unable to open PDF '{path.name}': {exc}"
            ) from exc

        try:
            return self._parse_document(document, path.name)
        except PDFParsingError:
            raise
        except Exception as exc:
            raise PDFParsingError(
                f"Unable to parse PDF '{path.name}': {exc}"
            ) from exc
        finally:
            document.close()

    def _parse_document(
        self,
        document: pymupdf.Document,
        filename: str,
    ) -> ParsedDocument:
        """Convert an open PyMuPDF document into our parsed representation."""

        page_count = len(document)

        if page_count == 0:
            raise PDFParsingError(
                f"PDF '{filename}' does not contain any pages."
            )

        metadata = self._extract_metadata(document)

        pages: list[ParsedPage] = []

        for page_index in range(page_count):
            page = document.load_page(page_index)

            text = page.get_text("text").strip()

            blocks = self._extract_blocks(page)

            pages.append(
                ParsedPage(
                    page_number=page_index + 1,
                    text=text,
                    blocks=blocks,
                )
            )

        return ParsedDocument(
            filename=filename,
            page_count=page_count,
            metadata=metadata,
            pages=pages,
        )

    @staticmethod
    def _extract_metadata(document: pymupdf.Document) -> dict[str, Any]:
        """
        Extract standard PDF metadata.

        PyMuPDF returns fields such as:
        title, author, subject, keywords, creator, producer,
        creationDate, and modDate.
        """
        metadata = document.metadata or {}

        return {
            key: value
            for key, value in metadata.items()
            if value not in (None, "")
        }

    @staticmethod
    def _extract_blocks(page: pymupdf.Page) -> list[dict[str, Any]]:
        """
        Extract text blocks while retaining their page coordinates.

        Coordinates are useful later for UI evidence highlighting and
        document-layout-aware processing.
        """

        raw_blocks = page.get_text("blocks")

        blocks: list[dict[str, Any]] = []

        for block_index, block in enumerate(raw_blocks):
            if len(block) < 5:
                continue

            x0, y0, x1, y1, text = block[:5]

            cleaned_text = str(text).strip()

            if not cleaned_text:
                continue

            blocks.append(
                {
                    "block_index": block_index,
                    "bbox": {
                        "x0": float(x0),
                        "y0": float(y0),
                        "x1": float(x1),
                        "y1": float(y1),
                    },
                    "text": cleaned_text,
                }
            )

        return blocks


def parse_pdf(file_path: str | Path) -> ParsedDocument:
    """
    Convenience function for parsing a PDF without manually
    constructing a PDFParser instance.
    """
    return PDFParser().parse(file_path)