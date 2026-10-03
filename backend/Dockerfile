FROM python:3.11-slim

# Install system dependencies needed by PyMuPDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmupdf-dev \
    libfreetype6-dev \
    libharfbuzz-dev \
    libjpeg-dev \
    libopenjp2-7-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency definition first so Docker caches the install layer
COPY pyproject.toml ./

# Install the project and all dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e "."

# Copy the rest of the application
COPY . .

# Create storage directory
RUN mkdir -p ./storage/uploads

# Expose FastAPI port
EXPOSE 8000

# Run database migrations then start the API server
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
