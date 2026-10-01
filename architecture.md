# Fact Knowledge Layer — Architecture

## 1. System Overview

The Fact Knowledge Layer converts heterogeneous PDF documents into structured, evidence-grounded facts and identifies relationships between facts across documents.

The system is designed to:

- Extract meaningful numerical and semantic facts from any PDF domain.
- Ground every persisted fact to its source document, page, chunk, and exact quote.
- Resolve entity mentions across documents to a shared canonical entity.
- Compare related facts across documents to find corroboration, contradiction, and reconciliation.
- Process PDFs asynchronously so uploads return immediately.
- Allow new documents to be added incrementally without rebuilding the knowledge layer.
- Support selective comparison between chosen documents.
- Provide a full human-review workflow for uncertain facts.
- Expose analytics, entity exploration, and export capabilities.

---

## 2. High-Level Architecture

```text
                    ┌─────────────────────────────────────────┐
                    │           React / Vite UI               │
                    │                                         │
                    │  Upload          Status Dashboard       │
                    │  Analytics       Fact Explorer          │
                    │  Entity Explorer Review Queue           │
                    │  Document View   Relationship Explorer  │
                    │  Compare                                │
                    └──────────────────┬──────────────────────┘
                                       │ HTTP / REST
                                       ▼
                    ┌─────────────────────────────────────────┐
                    │           FastAPI Backend               │
                    │                                         │
                    │  /documents   /facts      /entities     │
                    │  /relationships           /compare      │
                    │  /analytics   /schema     /jobs         │
                    └──────────────────┬──────────────────────┘
                                       │ Background job
                                       ▼
                    ┌─────────────────────────────────────────┐
                    │          Redis + Celery Workers         │
                    └────────────┬──────────────┬────────────┘
                                 │              │
                   ┌─────────────▼──┐    ┌──────▼──────────────┐
                   │  tasks_ingest  │    │  tasks_extraction    │
                   │  tasks_compare │    │  (batch + fallback)  │
                   └─────────────┬──┘    └──────┬───────────────┘
                                 │              │
                    ┌────────────▼──────────────▼────────────┐
                    │        PostgreSQL + pgvector            │
                    │                                         │
                    │  documents  chunks    entities          │
                    │  facts      fact_types relationships    │
                    └─────────────────────────────────────────┘
```

---

## 3. End-to-End Processing Pipeline

```text
PDF Upload
    ↓
SHA-256 duplicate check → skip if already processed
    ↓
Document record created
    ↓
Background job (Celery)
    ↓
PDF parsing (PyMuPDF)
    ↓
Page-aware chunking
    ↓
Chunk candidate filtering (skip boilerplate)
    ↓
Financial table detection → deterministic extraction (no LLM)
    OR
LLM batch extraction (Gemini / Ollama / OpenAI)
    ↓
Evidence validation (page + quote + offset)
    ↓
Entity resolution (exact → alias → normalised → new)
    ↓
Fact type registration (get_or_create)
    ↓
Fact persistence
    ↓
Compare tasks dispatched per (entity_id, attribute) pair
    ↓
Exact duplicate check → CORROBORATES (no LLM)
    OR
LLM semantic comparison → CORROBORATES / CONTRADICTS / RECONCILES / UNRELATED
    ↓
Relationship persistence
    ↓
React UI
```

---

## 4. Document Ingestion

The FastAPI `POST /documents/upload` endpoint:

1. Validates file extension and PDF magic bytes (`%PDF`).
2. Checks file size against `MAX_UPLOAD_SIZE_MB`.
3. Writes a temporary file to the upload directory.
4. Dispatches `ingest_document_task` via Celery and returns immediately.

The Celery ingestion task:

- Computes SHA-256 of the file content.
- Looks up existing documents by hash — returns the existing document ID if found (deduplication).
- On retry: checks if the document was already committed to avoid re-ingestion.
- On success: deletes the temporary file.
- Dispatches `extract_facts_task` after commit.

---

## 5. PDF Parsing and Chunking

`PDFParser` uses PyMuPDF to extract:

- Page-level plain text (`get_text("text")`)
- Block-level coordinates (`get_text("blocks")`) for evidence highlighting

`PDFChunker` splits pages into manageable overlapping chunks, preserving:

- Document ID
- Page number (1-based)
- Character start/end offsets
- Chunk index

**Known limitation:** Complex PDF tables can lose row/column relationships. Column values may not map reliably to their row headers during plain-text extraction.

---

## 6. LLM Fact Extraction

Each chunk passes through a two-stage filter before reaching the LLM:

### Stage 1 — Candidate filter (deterministic)

Chunks are skipped when they contain no numerics, dates, units, factual verbs, or relational language. This avoids sending boilerplate (table of contents, headers) to the LLM.

### Stage 2 — Financial table detection (deterministic)

Chunks containing multiple quarter labels (`Q1 FY24`, `Q2 FY24`, …) are handled by a deterministic table parser that extracts values per row and period. No LLM call is made for these chunks.

### Stage 3 — LLM batch extraction

Remaining chunks are sent to the LLM in batches of 4. The prompt requires the model to return:

```json
{
  "entity": "Company Name",
  "attribute": "revenue",
  "value": 1860,
  "unit": "INR crore",
  "temporal_scope": { "period_label": "Q1 FY24", "granularity": "quarter" },
  "confidence": 0.92,
  "evidence": {
    "page": 14,
    "chunk_id": "chunk:abc123",
    "quoted_text": "Revenue for Q1 FY24 was INR 1,860 crore."
  }
}
```

If a batch fails (malformed LLM output, 429 rate limit, 503 overload), each chunk is retried individually as a fallback.

---

## 7. Evidence Grounding

Every extracted fact must pass evidence validation before persistence:

```text
LLM returns evidence
    ↓
Page number matches source chunk page?
    ↓
quoted_text is non-empty?
    ↓
quoted_text found in source chunk text?
    ↓
Character offsets calculated
    ↓
Fact persisted
```

Facts that fail any step are silently dropped with a warning log. This prevents hallucinated facts from entering the knowledge layer.

---

## 8. Entity Resolution

The `EntityResolutionService` resolves an entity mention in four stages:

1. **Exact canonical name match** — in-memory cache first, then direct DB lookup via `get_by_canonical_name()` (indexed query, not a table scan).
2. **Alias match** — JSONB containment lookup in PostgreSQL.
3. **Normalised match** — strips legal suffixes (`Ltd`, `Limited`, `Corp`) and compares lowercased cores.
4. **New entity** — when no match is found, a new canonical entity is created and persisted.

---

## 9. Fact Clustering and Comparison

Facts are grouped by `(entity_id, attribute)`. Only groups with facts from at least two different documents enter comparison.

### Exact duplicate fast path

When two facts have identical entity, attribute, fact_type, value, unit, and temporal_scope, they are classified as `CORROBORATES` without any LLM call.

### LLM semantic comparison

For non-identical pairs, the comparison prompt includes both facts' full context (value, unit, temporal scope, evidence) and asks the LLM to classify the relationship as one of:

| Type | Meaning |
|---|---|
| `CORROBORATES` | Facts represent the same underlying information |
| `CONTRADICTS` | Facts describe the same context but conflict |
| `RECONCILES` | Values appear different but context explains the difference |
| `UNRELATED` | Facts are not comparable (blocked before LLM call) |

Relationships include a human-readable `explanation` generated by the LLM.

### Re-run comparisons

Any processed document can have its comparison tasks re-dispatched via `POST /documents/{id}/rerun-comparisons`. This is useful when Gemini 503 errors caused comparison tasks to fail silently.

### Selective comparison

The `POST /compare` endpoint accepts a list of document IDs and runs comparison only between facts from those documents. Pre-existing relationships between the selected documents are also included in the response.

---

## 10. Data Storage

PostgreSQL with pgvector stores six main tables:

### documents

```
id, filename, content_type, file_size_bytes, sha256,
page_count, status, error_message, created_at, processed_at
```

The `sha256` column has a unique constraint for deduplication.

### chunks

```
id, document_id (FK→documents), page_number, chunk_index,
text, char_start, char_end, token_count
```

### entities

```
id, canonical_name, entity_type, aliases (JSONB),
description, confidence, embedding (VECTOR(1536)),
created_at, updated_at
```

### fact_types

```
id, name, description, value_schema (JSONB),
version, is_active, created_at, updated_at
```

Fact types are data-driven and created on first use. No schema migration needed when new fact types appear.

### facts

```
id, document_id (FK), chunk_id (FK), entity_id (FK), fact_type_id (FK),
attribute, value (JSONB), unit, temporal_scope (JSONB),
evidence (JSONB), confidence, needs_review, extraction_method,
raw_extraction (JSONB), created_at
```

`value` and `evidence` are JSONB so facts of any shape fit without schema changes.

### relationships

```
id, source_fact_id (FK→facts), target_fact_id (FK→facts),
relationship_type, confidence, explanation, evidence (JSONB),
needs_review, created_at
```

---

## 11. API Surface

All routes are registered under `/api/v1/`.

| Router | Prefix | Key endpoints |
|---|---|---|
| documents | `/documents` | list, upload, delete, status, rerun-comparisons |
| facts | `/facts` | list (with needs_review filter), get, PATCH review |
| relationships | `/relationships` | list (with doc + type filter), get |
| entities | `/entities` | list (search + type filter), get (facts grouped by attribute) |
| compare | `/compare` | POST with document_ids list |
| analytics | `/analytics` | GET /summary — all stats in one call |
| schema | `/schema` | fact-type CRUD, DB-backed |
| jobs | `/jobs` | Celery AsyncResult status |

---

## 12. Frontend Architecture

Nine pages built with React 19 + TypeScript + Vite:

| Page | Purpose |
|---|---|
| `UploadPage` | Upload PDF, show filename in success message, poll job status |
| `StatusDashboard` | Live-polling cards with chunk/fact/review counts per document; re-run button |
| `AnalyticsPage` | System-wide charts: facts per doc, relationship types, confidence distribution, entity types, top attributes, top entities (pure CSS/SVG) |
| `FactExplorer` | Search/filter/sort facts; min-confidence slider; pagination (50/page); CSV export |
| `EntityExplorer` | Browse canonical entities; click to see all facts grouped by attribute |
| `ReviewQueue` | Accept / reject / undo flagged facts with evidence shown |
| `DocumentView` | Per-document fact list with evidence highlighting; delete button |
| `RelationshipGraph` | All relationships with explanations; filter by document and type |
| `ComparePage` | Checkbox-select documents; run selective comparison; see results immediately |

---

## 13. LLM Integration

The `LLMClient` abstraction supports three providers via a single `generate_structured()` interface:

| Provider | Config key | Notes |
|---|---|---|
| Gemini | `LLM_PROVIDER=gemini` | Free tier (no credit card); 15 RPM; recommended |
| Ollama | `LLM_PROVIDER=ollama` | Fully local; no API costs; slower on CPU |
| OpenAI-compatible | `LLM_PROVIDER=openai` | Works with OpenAI, OpenRouter, and compatible providers |

Retry logic is built into each provider client (4 attempts with exponential backoff). Malformed JSON is repaired with `json-repair` before Pydantic validation. Individual fact items that fail validation are skipped rather than failing the whole batch.

---

## 14. Hybrid Reasoning

The system avoids unnecessary LLM calls by separating deterministic and semantic work:

```
Fact pair
    │
    ├─ Different entity or attribute → UNRELATED (no LLM)
    │
    ├─ Identical value/unit/scope → CORROBORATES (no LLM)
    │
    └─ Needs semantic reasoning → LLM comparison
```

Deterministic responsibilities:
- Evidence validation
- Exact duplicate detection
- Financial table extraction
- Chunk candidate filtering
- Structural output validation
- Persistence and deduplication

LLM responsibilities:
- Fact extraction from arbitrary text
- Semantic interpretation of values
- Context-aware comparison
- Contradiction and reconciliation reasoning
- Relationship explanation generation

---

## 15. Asynchronous Processing

```text
FastAPI (sync response: document_id + task_id)
    ↓
Redis broker
    ↓
Celery worker
    ↓
ingest_document_task
    ↓
extract_facts_task (dispatched after commit)
    ↓
compare_facts_task × N (one per entity+attribute pair, dispatched after extraction)
```

The frontend polls `GET /jobs/{task_id}` every 2 seconds to track ingestion.  
The Status Dashboard polls `GET /documents/{id}/status` every 3 seconds during active processing.

---

## 16. Error Handling and Reliability

| Failure type | Handling |
|---|---|
| Invalid PDF magic bytes | Rejected at upload with 415 |
| Duplicate PDF (same SHA-256) | Returns existing document ID immediately |
| Empty / boilerplate chunk | Skipped before LLM call |
| Malformed LLM JSON | `json-repair` → Pydantic validation → item-level skip |
| LLM 429 / 503 | Retry with backoff (up to 4 attempts) |
| Evidence not found in chunk | Fact dropped, warning logged |
| Comparison failure | Logged and skipped; re-dispatchable via re-run endpoint |
| Celery retry on non-transient error | Narrowed `autoretry_for` to `(ConnectionError, TimeoutError, OSError)` |
| Malformed JSONB evidence in DB | Wrapped in try/except; bad items skipped, rest of fact loaded |
| Null temporal_scope in DB | Correctly returns `None` instead of empty TemporalScope |

---

## 17. Incremental Knowledge Building

New PDFs can be added at any time:

```text
Existing knowledge layer
    ↓
New PDF uploaded
    ↓
Extract new facts
    ↓
Resolve against existing entities
    ↓
Compare new facts against ALL existing facts with same entity + attribute
    ↓
Add new relationships
```

Existing facts are not re-extracted. Existing relationships are not affected unless the new document introduces a new entity or attribute match.

---

## 18. Engineering Trade-offs

### PostgreSQL + pgvector over a dedicated vector database

**Benefit:** fewer infrastructure components; relational data and vector operations stay together.  
**Trade-off:** a dedicated vector DB may be more suitable at very large scale.

### Celery + Redis over synchronous processing

**Benefit:** LLM and PDF processing do not block API requests; suitable for large documents.  
**Trade-off:** adds infrastructure and operational complexity.

### Evidence-first extraction

**Benefit:** every persisted fact is auditable and traceable to a source quote.  
**Trade-off:** some valid facts may be rejected when the LLM cannot provide a verifiable quote.

### Hybrid LLM + deterministic reasoning

**Benefit:** LLM used only where semantic reasoning is needed; deterministic paths are fast, cheap, and predictable.  
**Trade-off:** more complex than an LLM-only prototype.

### Gemini free tier as default LLM

**Benefit:** no cost, no credit card, ~15 RPM is sufficient for typical use.  
**Trade-off:** rate limit causes automatic retries on large documents; local Ollama avoids this at the cost of speed.

---

## 19. Known Limitations

1. Complex PDF tables can lose row/column relationships during text extraction.
2. Scanned PDFs (image-based) produce no text — OCR support is not yet implemented.
3. Gemini free tier hits 429 rate limits on large document batches; retry logic handles this automatically.
4. Local Ollama inference is slow on CPU (~40 seconds per batch).
5. Temporal reasoning across different quarters or periods requires deeper context.
6. Entity resolution can be ambiguous for highly similar entity names.

---

## 20. Future Improvements

```text
Table-aware PDF parsing (preserve row/column structure)
    ↓
OCR support for scanned PDFs (Tesseract)
    ↓
RAG / natural language Q&A over extracted facts
    ↓
Parallel Celery workers for faster large-document processing
    ↓
Formal evaluation dataset for extraction accuracy
    ↓
Bulk PDF upload
    ↓
Email / webhook notification on processing completion
```

---

## 21. End-to-End Summary

```text
                    ┌───────────────┐
                    │   PDF Upload  │
                    └───────┬───────┘
                            ↓ SHA-256 dedup check
                    ┌───────────────┐
                    │  FastAPI API  │
                    └───────┬───────┘
                            ↓ async dispatch
                    ┌───────────────┐
                    │ Celery + Redis│
                    └───────┬───────┘
                            ↓
                    ┌───────────────┐
                    │  PDF Parse    │
                    │  + Chunking   │
                    └───────┬───────┘
                            ↓ candidate filter
                    ┌───────────────────────────┐
                    │  Deterministic table path │
                    │  OR LLM batch extraction  │
                    └───────────┬───────────────┘
                                ↓
                    ┌───────────────┐
                    │   Evidence    │
                    │  Validation   │
                    └───────┬───────┘
                            ↓
                    ┌───────────────┐
                    │    Entity     │
                    │  Resolution   │
                    └───────┬───────┘
                            ↓
                    ┌───────────────┐
                    │ Fact Clusters │
                    │ (entity+attr) │
                    └───────┬───────┘
                            ↓ exact dupe → no LLM
                    ┌───────────────┐
                    │  LLM Compare  │
                    │  + Explain    │
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
                    ┌───────────────────────────────────┐
                    │           React UI                │
                    │  Status · Analytics · Facts       │
                    │  Entities · Review · Relationships│
                    │  Compare · Document View          │
                    └───────────────────────────────────┘
```

The key design principle is **evidence-grounded knowledge**: every fact traces back to its source, every relationship has an explanation, and no fact enters the system without a verifiable quote from the original document.
