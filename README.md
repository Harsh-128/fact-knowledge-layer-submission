# Fact Knowledge Layer

A document-agnostic fact extraction and comparison system that processes PDFs, extracts meaningful facts with source evidence, and identifies relationships between facts across documents.

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
