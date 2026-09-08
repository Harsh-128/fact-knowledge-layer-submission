# Fact Knowledge Layer — Architecture

## 1. System Overview

The Fact Knowledge Layer converts heterogeneous PDF documents into structured, evidence-grounded facts and identifies relationships between facts across documents.

The system is designed to:

- Extract meaningful numerical and semantic facts.
- Ground every persisted fact to its source document evidence.
- Resolve entities across documents.
- Compare related facts across documents.
- Identify corroboration, contradiction, and reconciliation through context.
- Process PDFs asynchronously.
- Allow new documents to be added without rebuilding the existing knowledge layer.

---

## 2. High-Level Architecture

```text
                         ┌─────────────────────────────┐
                         │       React / Vite UI       │
                         │                             │
                         │  Upload                     │
                         │  Fact Explorer              │
                         │  Document View              │
                         │  Relationship Explorer     │
                         └──────────────┬──────────────┘
                                        │
                                        │ HTTP / REST
                                        ▼
                         ┌─────────────────────────────┐
                         │      FastAPI Backend        │
                         │                             │
                         │  Document APIs              │
                         │  Fact APIs                  │
                         │  Relationship APIs          │
                         │  Job Status APIs            │
                         └──────────────┬──────────────┘
                                        │
                                        │ Background Job
                                        ▼
                         ┌─────────────────────────────┐
                         │       Redis + Celery        │
                         │      Worker Processing      │
                         └──────────────┬──────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    │                   │                   │
                    ▼                   ▼                   ▼
             PDF Ingestion       Fact Extraction       Comparison
                    │                   │                   │
                    ▼                   ▼                   ▼
             PDF Parsing          Ollama / LLM        Fact Comparison
                    │                   │                   │
                    ▼                   ▼                   │
              Chunking          Structured Facts          │
                    │                   │                   │
                    │                   ▼                   │
                    │          Evidence Validation         │
                    │                   │                   │
                    │                   ▼                   │
                    │          Entity Resolution            │
                    │                   │                   │
                    │                   ▼                   │
                    │           Fact Clustering              │
                    │                   │                   │
                    └───────────────────┴───────────────────┘
                                        │
                                        ▼
                         ┌─────────────────────────────┐
                         │    PostgreSQL + pgvector    │
                         │                             │
                         │ Documents                   │
                         │ Chunks                      │
                         │ Entities                    │
                         │ Facts                       │
                         │ Embeddings                  │
                         │ Relationships               │
                         └─────────────────────────────┘
```

---

## 3. End-to-End Processing Pipeline

A PDF moves through the following stages:

```text
PDF Upload
    ↓
Document Creation
    ↓
Background Job
    ↓
PDF Parsing
    ↓
Page-aware Chunking
    ↓
LLM Fact Extraction
    ↓
Evidence Validation
    ↓
Entity Resolution
    ↓
Fact Clustering
    ↓
Cross-document Comparison
    ↓
Relationship Creation
    ↓
PostgreSQL Persistence
    ↓
React UI
```

Each stage has a specific responsibility and can be tested or improved independently.

---

## 4. Document Ingestion

The FastAPI application accepts PDF uploads through the document API.

The ingestion process creates a document record and starts asynchronous processing using Celery and Redis.

The document stores information such as:

```text
Document ID
Filename
SHA-256 hash
Upload time
Status
Page count
```

Content hashing is also used to identify duplicate documents and avoid unnecessary re-processing.

---

## 5. PDF Parsing and Chunking

The PDF is parsed into page-aware text.

The parser retains source information so that extracted facts can later be traced back to the original document.

The parsed content is divided into manageable chunks before being sent to the LLM.

Conceptually:

```text
PDF
 │
 ├── Page 1
 │     ├── Chunk 1
 │     └── Chunk 2
 │
 ├── Page 2
 │     ├── Chunk 3
 │     └── Chunk 4
 │
 └── Page N
       └── Chunk N
```

Each chunk retains:

```text
Document ID
Page Number
Character Start
Character End
Chunk Text
Embedding
```

This page and character information is important for evidence grounding.

### Known limitation

Complex PDF tables can lose their original row/column relationships during text extraction. This was discovered during testing with an additional unseen stock-report PDF.

---

## 6. LLM Fact Extraction

Each chunk is processed by the LLM using a structured extraction prompt.

The model is instructed to identify meaningful facts rather than generate a general document summary.

A fact can contain:

```text
Entity
Attribute / Fact Type
Value
Unit
Temporal Scope
Confidence
Evidence
Review Status
```

Example conceptual output:

```json
{
  "entity": "Example Company",
  "attribute": "revenue",
  "value": 1860,
  "unit": "INR crore",
  "temporal_scope": {
    "period": "Q1 FY24"
  },
  "confidence": 0.90,
  "evidence": {
    "page": 14,
    "quote": "Revenue for Q1 FY24 was INR 1,860 crore."
  }
}
```

The actual fact representation remains flexible because different PDFs can contain different types of information.

---

## 7. Evidence Grounding

Evidence grounding is a core reliability mechanism.

The LLM must provide supporting evidence for an extracted fact.

The backend validates the returned evidence against the original chunk:

```text
LLM Fact
    ↓
Page Validation
    ↓
Chunk Validation
    ↓
Exact Quote Validation
    ↓
Character Offset Calculation
    ↓
Persist Fact
```

A fact is not silently accepted just because the LLM produced it.

The evidence validation checks that:

1. The referenced page matches the source chunk.
2. The evidence quote is not empty.
3. The quote exists in the original chunk text.
4. Character offsets can be calculated.

If valid evidence cannot be established, the extraction pipeline does not persist the unsupported fact.

This makes the knowledge layer auditable and reduces unsupported LLM-generated information.

---

## 8. Entity Resolution

The same entity can appear differently across documents.

For example:

```text
Document A:
"Example Company"

Document B:
"Example Company Ltd."

Document C:
"Example Company Limited"
```

The entity resolution layer attempts to associate these mentions with the same canonical entity.

The conceptual flow is:

```text
Extracted Entity Mention
          ↓
Entity Matching
          ↓
Existing Canonical Entity
          ↓
Fact Associated With Entity
```

This is important because cross-document comparison should happen between facts about the same entity rather than simply comparing similar text.

---

## 9. Fact Clustering

After entity resolution, facts are grouped using their canonical entity and attribute.

Conceptually:

```text
Entity: Example Company
│
├── Revenue
│    ├── Fact A — Document 1
│    ├── Fact B — Document 2
│    └── Fact C — Document 3
│
├── Employees
│    ├── Fact D — Document 1
│    └── Fact E — Document 3
│
└── Location
     └── Fact F — Document 2
```

Only relevant facts should be compared with each other.

This prevents unrelated facts from being incorrectly classified as contradictions.

---

## 10. Cross-Document Comparison

Facts belonging to the same comparison group are passed to the comparison layer.

The system identifies:

```text
CORROBORATES
CONTRADICTS
RECONCILES
```

### Corroboration

Two facts represent the same underlying information.

```text
Fact A ─────────────┐
                    ├── CORROBORATES
Fact B ─────────────┘
```

### Contradiction

Two facts describe the same relevant entity, attribute, and context but contain conflicting values.

```text
Fact A: Revenue = 100 INR crore
Fact B: Revenue = 200 INR crore

              ↓

          CONTRADICTS
```

### Reconciliation

Two facts appear different but can be explained by context.

For example:

```text
100 INR crore
      =
1000 INR million

              ↓

          RECONCILES
```

The comparison layer also considers temporal scope and other available context before deciding that two facts genuinely contradict each other.

---

## 11. Hybrid Reasoning

The system does not rely entirely on the LLM.

It uses deterministic logic where the answer is unambiguous and LLM reasoning where semantic interpretation is required.

```text
                    Fact Pair
                       │
              ┌────────┴────────┐
              │                 │
              ▼                 ▼
       Deterministic         LLM Reasoning
          Checks                  │
              │                   │
       Exact matches       Context analysis
       Evidence checks     Semantic comparison
       Validation          Explanation
              │                   │
              └────────┬──────────┘
                       ▼
                 Relationship
```

### Deterministic responsibilities

- Evidence validation.
- Exact duplicate handling.
- Structured output validation.
- Persistence.
- Basic data validation.

### LLM responsibilities

- Fact extraction.
- Semantic interpretation.
- Context-aware comparison.
- Contradiction reasoning.
- Reconciliation reasoning.
- Relationship explanations.

This provides a balance between predictability and flexibility.

---

## 12. Data Storage

The system uses PostgreSQL with pgvector.

The main logical entities are:

```text
Document
   │
   ├── Chunk
   │
   └── Fact
         │
         ├── Entity
         ├── Fact Type
         ├── Evidence
         └── Relationship
```

### Document

Stores uploaded document metadata and processing status.

### Chunk

Stores page-aware source text and its position within the document.

### Entity

Stores canonical entities used to connect facts across documents.

### Fact

Stores:

```text
Document
Chunk
Entity
Attribute
Value
Unit
Temporal Scope
Confidence
Raw Extraction
Embedding
Review Status
```

Flexible JSON/JSONB values are used because facts can have different shapes.

For example:

```text
Revenue → numerical value + unit + period

Director → person + role + tenure

Address → structured or textual location
```

A rigid schema would make every new fact type require database changes.

### Relationship

Stores:

```text
Fact A
Fact B
Relationship Type
Explanation
Confidence
Creation Time
```

---

## 13. Asynchronous Processing

LLM inference can take significant time, particularly for large PDFs.

The system therefore uses Celery and Redis:

```text
FastAPI
   ↓
Redis
   ↓
Celery Worker
   ↓
Ingestion
   ↓
Extraction
   ↓
Comparison
```

The API does not need to remain blocked while the complete pipeline executes.

The frontend can monitor job status and display processing progress and resulting counts.

This architecture also makes it possible to extend processing to larger documents and multiple PDFs.

---

## 14. Backend Architecture

The backend separates API logic, domain logic, infrastructure, and background workers.

```text
backend/
└── app/
    │
    ├── api/
    │   └── v1/
    │       ├── documents
    │       ├── facts
    │       ├── relationships
    │       └── jobs
    │
    ├── domain/
    │   ├── models/
    │   │   ├── document
    │   │   ├── chunk
    │   │   ├── entity
    │   │   ├── fact
    │   │   └── relationship
    │   │
    │   └── services/
    │       ├── ingestion
    │       ├── extraction
    │       ├── entity resolution
    │       └── comparison
    │
    ├── infra/
    │   ├── database
    │   ├── vector operations
    │   ├── LLM integration
    │   └── PDF processing
    │
    └── workers/
        ├── Celery application
        ├── ingestion tasks
        ├── extraction tasks
        └── comparison tasks
```

This separation keeps the core knowledge-layer logic independent from infrastructure-specific implementations.

---

## 15. Frontend Architecture

The frontend is built using React/Vite.

```text
frontend/
└── src/
    ├── pages/
    │   ├── UploadPage
    │   ├── DocumentView
    │   ├── FactExplorer
    │   └── RelationshipGraph
    │
    └── components/
        ├── EvidenceHighlighter
        ├── FactCard
        └── RelationshipBadge
```

### Main UI capabilities

```text
Upload PDF
    ↓
Track Processing
    ↓
View Facts
    ↓
Filter Facts
    ↓
Inspect Evidence
    ↓
Explore Relationships
```

The Document View provides source evidence inspection, while Fact Explorer allows facts to be filtered by document, entity, and attribute.

---

## 16. LLM Layer

The LLM integration is isolated from the core business logic.

The final working development setup uses:

```text
Ollama
   ↓
qwen3:8b
```

The LLM is used for:

- Structured fact extraction.
- Semantic interpretation.
- Fact comparison.
- Contradiction reasoning.
- Reconciliation reasoning.
- Relationship explanations.

During development, external API usage was also considered, but Gemini API quota limitations led to using local Ollama for the final working implementation.

Keeping the LLM integration isolated makes it possible to change the inference provider without redesigning the complete knowledge pipeline.

---

## 17. Error Handling and Reliability

Several reliability mechanisms are implemented.

### Malformed LLM output

If structured batch output cannot be parsed reliably, the extraction pipeline has a fallback path that can process chunks individually.

### Invalid evidence

Evidence is checked against the original source text before the fact is persisted.

### Duplicate documents

Document content hashing helps identify duplicate uploads.

### Low-confidence / uncertain results

Facts and relationships contain confidence and review metadata so uncertain results can be surfaced for future review workflows.

---

## 18. Incremental Knowledge Building

New PDFs can be added to the existing knowledge layer.

Conceptually:

```text
Existing Knowledge Layer
        │
        │
        ▼
New PDF
        │
        ▼
Extract New Facts
        │
        ▼
Resolve Against Existing Entities
        │
        ▼
Compare Relevant Facts
        │
        ▼
Add New Relationships
```

The existing facts do not need to be completely rebuilt whenever a new document is uploaded.

---

## 19. Engineering Trade-offs

### PostgreSQL + pgvector

Chosen instead of introducing a separate vector database.

**Benefit:**
- Fewer infrastructure components.
- Relational data and vector operations remain together.

**Trade-off:**
- A specialized vector database may be more appropriate at very large scale.

### Celery + Redis

Chosen instead of synchronous processing.

**Benefit:**
- Long-running PDF and LLM processing does not block API requests.
- Better foundation for multiple documents.

**Trade-off:**
- Adds infrastructure and operational complexity.

### Evidence-first extraction

The system prioritizes grounded facts rather than maximizing the number of extracted facts.

**Benefit:**
- Results are auditable.
- Reduces unsupported facts.

**Trade-off:**
- Some potentially useful facts may be rejected when reliable evidence cannot be established.

### Hybrid LLM + deterministic reasoning

**Benefit:**
- LLM provides semantic flexibility.
- Deterministic logic provides predictable validation.

**Trade-off:**
- The system is more complex than an LLM-only prototype.

---

## 20. Known Limitations

The current system has several known limitations:

1. Complex PDF tables can lose row/column relationships.
2. Local LLM inference can be slow for large documents.
3. LLM structured output can occasionally be malformed or incomplete.
4. Temporal reasoning becomes difficult when similar metrics refer to different periods.
5. Entity resolution can be ambiguous for similar entity names.
6. A complete human-in-the-loop review interface is not yet implemented.

---

## 21. Future Improvements

The next improvements would include:

```text
Table-aware PDF parsing
        ↓
Stronger numerical validation
        ↓
Improved temporal reasoning
        ↓
Better entity matching
        ↓
Human review workflow
        ↓
Parallel processing / better batching
        ↓
Formal evaluation dataset
```

These improvements would increase extraction accuracy and make the system more suitable for larger document collections.

---

## 22. End-to-End Summary

The complete knowledge flow is:

```text
                    ┌───────────────┐
                    │   PDF Upload  │
                    └───────┬───────┘
                            ↓
                    ┌───────────────┐
                    │    FastAPI    │
                    └───────┬───────┘
                            ↓
                    ┌───────────────┐
                    │ Celery + Redis│
                    └───────┬───────┘
                            ↓
                    ┌───────────────┐
                    │ PDF Parse     │
                    │ + Chunking    │
                    └───────┬───────┘
                            ↓
                    ┌───────────────┐
                    │ LLM Extraction│
                    └───────┬───────┘
                            ↓
                    ┌───────────────┐
                    │    Evidence   │
                    │   Validation  │
                    └───────┬───────┘
                            ↓
                    ┌───────────────┐
                    │    Entity     │
                    │   Resolution  │
                    └───────┬───────┘
                            ↓
                    ┌───────────────┐
                    │ Fact Clusters │
                    └───────┬───────┘
                            ↓
                    ┌───────────────┐
                    │    Compare    │
                    │ Facts + Context│
                    └───────┬───────┘
                            ↓
              ┌─────────────┼─────────────┐
              ↓             ↓             ↓
        CORROBORATES   CONTRADICTS   RECONCILES
              └─────────────┼─────────────┘
                            ↓
                    ┌───────────────┐
                    │  PostgreSQL   │
                    │  + pgvector   │
                    └───────┬───────┘
                            ↓
                    ┌───────────────┐
                    │   React UI    │
                    └───────────────┘
```

The key design principle is **evidence-grounded knowledge rather than simple document summarization**: every useful fact should remain connected to its source, and relationships between facts should be explainable.
