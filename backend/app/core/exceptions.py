class FactKnowledgeLayerError(Exception):
    """Base exception for the Fact Knowledge Layer application."""


class DocumentProcessingError(FactKnowledgeLayerError):
    """Raised when a document cannot be processed successfully."""


class PDFParsingError(DocumentProcessingError):
    """Raised when PDF text or metadata cannot be extracted."""


class FactExtractionError(DocumentProcessingError):
    """Raised when facts cannot be extracted from document content."""


class EntityResolutionError(FactKnowledgeLayerError):
    """Raised when an entity cannot be resolved or canonicalized."""


class FactComparisonError(FactKnowledgeLayerError):
    """Raised when facts cannot be compared reliably."""


class UnsupportedDocumentError(DocumentProcessingError):
    """Raised when an uploaded document type is not supported."""


class DocumentNotFoundError(FactKnowledgeLayerError):
    """Raised when a requested document does not exist."""


class FactNotFoundError(FactKnowledgeLayerError):
    """Raised when a requested fact does not exist."""


class RelationshipNotFoundError(FactKnowledgeLayerError):
    """Raised when a requested fact relationship does not exist."""