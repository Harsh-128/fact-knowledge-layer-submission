from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.models.chunk import Chunk
from app.domain.models.document import Document
from app.infra.pdf.parser import ParsedDocument


@dataclass(slots=True)
class ChunkingConfig:
    """
    Configuration for semantic text chunking.

    Token counts are approximated using 4 characters per token.
    This keeps the chunker independent of any specific LLM tokenizer.
    """

    target_tokens: int = 500
    overlap_tokens: int = 50
    min_chunk_tokens: int = 50

    @property
    def target_characters(self) -> int:
        return self.target_tokens * 4

    @property
    def overlap_characters(self) -> int:
        return self.overlap_tokens * 4

    @property
    def min_chunk_characters(self) -> int:
        return self.min_chunk_tokens * 4


class PDFChunker:
    """
    Convert parsed PDF pages into manageable text chunks.

    Design goals:
    - preserve page boundaries where possible
    - avoid splitting sentences unnecessarily
    - maintain character offsets
    - provide controlled overlap
    - remain independent of LLMs and fact schemas
    """

    # Sentence boundary pattern.
    SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+")

    # Collapse repeated whitespace efficiently.
    WHITESPACE_PATTERN = re.compile(r"[ \t]+")

    def __init__(self, config: ChunkingConfig | None = None) -> None:
        self.config = config or ChunkingConfig()

        if self.config.target_tokens <= 0:
            raise ValueError("target_tokens must be greater than zero")

        if self.config.overlap_tokens < 0:
            raise ValueError("overlap_tokens cannot be negative")

        if self.config.overlap_tokens >= self.config.target_tokens:
            raise ValueError(
                "overlap_tokens must be smaller than target_tokens"
            )

        if self.config.min_chunk_tokens <= 0:
            raise ValueError("min_chunk_tokens must be greater than zero")

    def chunk_document(
        self,
        parsed_document: ParsedDocument,
        document: Document,
    ) -> list[Chunk]:
        """
        Chunk a parsed document into domain Chunk objects.
        """

        chunks: list[Chunk] = []
        chunk_index = 0

        for page in parsed_document.pages:
            if page.is_empty:
                continue

            page_chunks = self._chunk_page(
                page_number=page.page_number,
                text=page.text,
            )

            for text, char_start, char_end in page_chunks:
                chunks.append(
                    Chunk(
                        id=f"{document.id}:chunk:{chunk_index}",
                        document_id=document.id,
                        page_number=page.page_number,
                        chunk_index=chunk_index,
                        text=text,
                        char_start=char_start,
                        char_end=char_end,
                        token_count=self._estimate_tokens(text),
                    )
                )

                chunk_index += 1

        return chunks

    def _chunk_page(
        self,
        page_number: int,
        text: str,
    ) -> list[tuple[str, int, int]]:
        """
        Split one page into sentence-aware chunks.

        Returns:
            (chunk_text, character_start, character_end)
        """

        normalized_text = self._normalize_text(text)

        if not normalized_text:
            return []

        # Fast path:
        # Most short PDF pages can be returned directly without
        # sentence processing.
        if len(normalized_text) <= self.config.target_characters:
            return [
                (
                    normalized_text,
                    0,
                    len(normalized_text),
                )
            ]

        sentences = self._split_into_sentences(normalized_text)

        if not sentences:
            return self._chunk_by_characters(normalized_text)

        chunks: list[tuple[str, int, int]] = []

        current_sentences: list[tuple[str, int, int]] = []
        current_start = 0
        current_end = 0

        for sentence, sentence_start, sentence_end in sentences:

            if not current_sentences:
                current_start = sentence_start

            proposed_end = sentence_end
            proposed_length = proposed_end - current_start

            # Current chunk is full.
            if (
                current_sentences
                and proposed_length > self.config.target_characters
            ):
                chunk_text = normalized_text[
                    current_start:current_end
                ].strip()

                if chunk_text:
                    chunks.append(
                        (
                            chunk_text,
                            current_start,
                            current_end,
                        )
                    )

                # Keep approximately 50 tokens of overlap.
                overlap_start = self._calculate_overlap_start(
                    sentences=current_sentences,
                )

                current_sentences = [
                    item
                    for item in current_sentences
                    if item[2] > overlap_start
                ]

                current_start = overlap_start

            current_sentences.append(
                (
                    sentence,
                    sentence_start,
                    sentence_end,
                )
            )

            current_end = sentence_end

        # Add final chunk.
        if current_end > current_start:
            final_text = normalized_text[
                current_start:current_end
            ].strip()

            if final_text:
                chunks.append(
                    (
                        final_text,
                        current_start,
                        current_end,
                    )
                )

        return self._merge_tiny_chunks(chunks)

    def _split_into_sentences(
        self,
        text: str,
    ) -> list[tuple[str, int, int]]:
        """
        Split text into sentences while preserving offsets.

        This implementation avoids repeated text.find() calls.
        Regex match positions are used directly.
        """

        sentences: list[tuple[str, int, int]] = []

        start = 0

        for match in self.SENTENCE_PATTERN.finditer(text):
            end = match.start()

            sentence = text[start:end].strip()

            if sentence:
                # Calculate whitespace removed by strip().
                leading_whitespace = len(text[start:end]) - len(
                    text[start:end].lstrip()
                )

                actual_start = start + leading_whitespace
                actual_end = actual_start + len(sentence)

                sentences.append(
                    (
                        sentence,
                        actual_start,
                        actual_end,
                    )
                )

            start = match.end()

        # Final sentence.
        final_sentence = text[start:].strip()

        if final_sentence:
            leading_whitespace = len(text[start:]) - len(
                text[start:].lstrip()
            )

            actual_start = start + leading_whitespace
            actual_end = actual_start + len(final_sentence)

            sentences.append(
                (
                    final_sentence,
                    actual_start,
                    actual_end,
                )
            )

        return sentences

    def _calculate_overlap_start(
        self,
        sentences: list[tuple[str, int, int]],
    ) -> int:
        """
        Calculate the starting offset for overlapping content.

        Prefer a sentence boundary while keeping approximately
        overlap_characters from the previous chunk.
        """

        if not sentences:
            return 0

        target_start = max(
            0,
            sentences[-1][2] - self.config.overlap_characters,
        )

        for _, sentence_start, _ in sentences:
            if sentence_start >= target_start:
                return sentence_start

        return target_start

    def _chunk_by_characters(
        self,
        text: str,
    ) -> list[tuple[str, int, int]]:
        """
        Fallback chunking for text where sentence boundaries
        cannot be detected.
        """

        chunks: list[tuple[str, int, int]] = []

        start = 0
        text_length = len(text)

        target_size = self.config.target_characters
        overlap_size = self.config.overlap_characters

        while start < text_length:
            end = min(
                start + target_size,
                text_length,
            )

            chunk_text = text[start:end].strip()

            if chunk_text:
                # Avoid text.find(); calculate the trimmed offsets directly.
                leading_whitespace = len(text[start:end]) - len(
                    text[start:end].lstrip()
                )

                actual_start = start + leading_whitespace
                actual_end = actual_start + len(chunk_text)

                chunks.append(
                    (
                        chunk_text,
                        actual_start,
                        actual_end,
                    )
                )

            if end >= text_length:
                break

            # Move forward while preserving overlap.
            start = max(
                start + 1,
                end - overlap_size,
            )

        return chunks

    def _merge_tiny_chunks(
        self,
        chunks: list[tuple[str, int, int]],
    ) -> list[tuple[str, int, int]]:
        """
        Merge very small trailing chunks into the previous chunk.
        """

        if len(chunks) <= 1:
            return chunks

        merged: list[tuple[str, int, int]] = []

        min_size = self.config.min_chunk_characters

        for text, start, end in chunks:

            if (
                merged
                and len(text) < min_size
            ):
                previous_text, previous_start, _ = merged[-1]

                combined_text = (
                    previous_text.rstrip()
                    + "\n"
                    + text.lstrip()
                )

                merged[-1] = (
                    combined_text,
                    previous_start,
                    end,
                )

            else:
                merged.append(
                    (
                        text,
                        start,
                        end,
                    )
                )

        return merged

    @staticmethod
    def _normalize_text(text: str) -> str:
        """
        Normalize whitespace without destroying meaningful content.
        """

        text = text.replace("\r\n", "\n")
        text = text.replace("\r", "\n")

        lines: list[str] = []

        for line in text.split("\n"):
            line = PDFChunker.WHITESPACE_PATTERN.sub(
                " ",
                line,
            ).strip()

            if line:
                lines.append(line)

        return "\n".join(lines).strip()

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """
        Estimate token count using approximately 4 characters/token.
        """

        if not text.strip():
            return 0

        return max(
            1,
            round(len(text) / 4),
        )


def chunk_pdf(
    parsed_document: ParsedDocument,
    document: Document,
    config: ChunkingConfig | None = None,
) -> list[Chunk]:
    """
    Convenience function for chunking a parsed PDF.
    """

    return PDFChunker(config).chunk_document(
        parsed_document=parsed_document,
        document=document,
    )