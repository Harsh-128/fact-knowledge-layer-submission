from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.routes_documents import router as documents_router
from app.api.v1.routes_facts import router as facts_router
from app.api.v1.routes_jobs import router as jobs_router
from app.api.v1.routes_relationships import router as relationships_router
from app.config import settings
from app.core.logging import setup_logging


setup_logging()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "A grounded fact knowledge layer for extracting, linking, "
        "and comparing facts across documents."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "https://fact-knowledge-layer-frontend.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
def health_check() -> dict:
    """
    Basic API health endpoint.
    """
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
    }


app.include_router(
    documents_router,
    prefix=settings.api_v1_prefix,
)

app.include_router(
    facts_router,
    prefix=settings.api_v1_prefix,
)

app.include_router(
    jobs_router,
    prefix=settings.api_v1_prefix,
)

app.include_router(
    relationships_router,
    prefix=settings.api_v1_prefix,
)
