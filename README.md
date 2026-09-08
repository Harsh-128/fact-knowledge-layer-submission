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

2. Start PostgreSQL and Redis

From the project root:

docker compose up -d

Check the services:

docker compose ps

Make sure PostgreSQL and Redis are running before continuing.

3. Configure the backend
cd backend
cp .env.example .env

Update .env with your local configuration if required.

Do not commit .env or any credentials to the repository.

4. Create the Python environment

From the backend directory:

python -m venv .venv
source .venv/bin/activate

Install the backend dependencies:

pip install -r requirements.txt
5. Start Ollama

The project uses Ollama for local LLM inference.

Make sure Ollama is installed and pull the required model:

ollama pull qwen3:8b

Make sure Ollama is running before processing PDFs.

6. Start the FastAPI backend

From the backend directory:

uvicorn app.main:app --reload

The API will normally be available at:

http://localhost:8000
7. Start the Celery worker

Open another terminal:

cd ~/Projects/fact-knowledge-layer/backend
source .venv/bin/activate

Start the Celery worker:

celery -A app.workers.celery_app:celery_app worker --loglevel=info

The worker processes document ingestion, fact extraction, and fact comparison asynchronously.

8. Start the frontend

Open another terminal:

cd ~/Projects/fact-knowledge-layer/frontend
npm install
npm run dev

Open the URL shown by Vite, normally:

http://localhost:5173
