from collections.abc import Generator

from fastapi import Depends

from app.core.security import verify_api_key
from app.infra.db.session import get_db


def get_database() -> Generator:
    """
    Provide a database session to API routes.
    """
    yield from get_db()


def require_api_key(
    _: None = Depends(verify_api_key),
) -> None:
    """
    Apply API-key verification to protected routes.

    Authentication is disabled when no API key is configured,
    which keeps local development simple.
    """
    return None
