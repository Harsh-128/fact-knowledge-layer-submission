# Fact Knowledge Layer

## Setup and Run Instructions

### Prerequisites

Make sure the following are installed:

- Python 3.11+
- Node.js 18+
- Docker and Docker Compose
- Ollama

The project uses FastAPI, PostgreSQL with pgvector, Redis, Celery, React/Vite, and Ollama.

### 1. Clone the repository

```bash
git clone https://github.com/Harsh-128/fact-knowledge-layer-submission.git
cd fact-knowledge-layer-submission
```

### 2. Start PostgreSQL and Redis

From the project root:

```bash
docker compose up -d
```

Check the services:

```bash
docker compose ps
```

Make sure PostgreSQL and Redis are running before continuing.

### 3. Configure the backend

```bash
cd backend
cp .env.example .env
```

Update `.env` with your local configuration if required.
Do not commit `.env` or any credentials to the repository.

### 4. Create the Python environment

From the `backend` directory:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install the backend dependencies:

```bash
pip install -r requirements.txt
```

### 5. Start Ollama

The project uses Ollama for local LLM inference.
Make sure Ollama is installed and pull the required model:

```bash
ollama pull qwen3:8b
```

Make sure Ollama is running before processing PDFs.

### 6. Start the FastAPI backend

From the `backend` directory:

```bash
uvicorn app.main:app --reload
```

The API will normally be available at:

```
http://localhost:8000
```

### 7. Start the Celery worker

Open another terminal:

```bash
cd ~/Projects/fact-knowledge-layer/backend
source .venv/bin/activate
```

Start the Celery worker:

```bash
celery -A app.workers.celery_app:celery_app worker --loglevel=info
```

The worker processes document ingestion, fact extraction, and fact comparison asynchronously.

### 8. Start the frontend

Open another terminal:

```bash
cd ~/Projects/fact-knowledge-layer/frontend
npm install
npm run dev
```

Open the URL shown by Vite, normally:

```
http://localhost:5173
```

---

## Video Demo

**Demo video:** https://youtu.be/CNV7ICs5Wns

The demo is under 3 minutes and shows the application processing a PDF through the UI.
### Demo Preview

![Fact Knowledge Layer Demo](docs/demo.gif)

The demonstration covers:

1. Uploading a PDF.
2. Background processing.
3. Extracted facts.
4. Source evidence and page references.
5. Fact exploration.
6. Cross-document relationship analysis.
7. Corroboration.
8. Contradiction.
9. Reconciliation by context.
10. An extraction limitation discovered during testing.

---

## Required Demo Cases

The system was evaluated against the four required reasoning and extraction cases.

### Case 1 — Corroborated Fact

**Scenario:**  
The same underlying fact appears across multiple documents, potentially using different wording, units, or presentation formats.

**Example:**  
The system identifies matching facts referring to the same entity and attribute across documents and creates a `CORROBORATES` relationship.

**System reasoning:**
- Resolve the extracted facts to the same entity.
- Compare the attribute and value.
- Consider units and temporal/contextual scope.
- If the values represent the same underlying fact, classify the relationship as `CORROBORATES`.

**Evidence shown:**  
Each fact retains its source document, page, chunk, and exact supporting text.

---

### Case 2 — Genuine Contradiction

**Scenario:**  
Two documents report different values for the same entity and attribute under the same relevant context.

**Example:**  
One source reports revenue as **INR 100 crore**, while another reports **INR 200 crore** for the same scope.

**System reasoning:**  
After entity and attribute matching, the comparison layer determines that the values cannot represent the same numerical fact and creates a `CONTRADICTS` relationship.

**Evidence shown:**  
Both conflicting facts retain their independent source evidence and page references.

---

### Case 3 — Apparent Contradiction Explained by Context

**Scenario:**  
Two values initially appear contradictory but become consistent after considering units, time period, or scope.

**Example:**  
A value of **INR 100 crore** and **INR 1000 million** represent the same amount after unit normalization.

**System reasoning:**
- Match the facts to the same entity and attribute.
- Compare numerical values after considering their units.
- Examine temporal and contextual scope.
- Determine that the apparent difference is explainable rather than a genuine contradiction.

The system therefore creates a `RECONCILES` relationship instead of marking the facts as contradictory.

**Evidence shown:**  
The relationship retains links to both source facts and their supporting evidence.

---

### Case 4 — Extraction / Reasoning Failure

**Scenario:**  
During testing with a previously unseen PDF, the extraction pipeline encountered a table whose numerical columns were not reliably associated with the corresponding rows.

**Observed issue:**  
The system was able to extract meaningful text values from the table, but the table structure was not sufficiently preserved to guarantee that each numerical value was mapped to the correct row/column.

**How it was handled:**  
The pipeline validates extracted evidence against the original chunk text and retains confidence and review metadata. However, this particular example was not automatically flagged for review, demonstrating a limitation in the current extraction approach.

**Planned improvement:**
- Add table-aware PDF parsing.
- Preserve row/column relationships explicitly.
- Validate numerical values against table headers.
- Add stronger confidence checks for ambiguous table extraction.
- Route uncertain table facts to `needs_review`.
