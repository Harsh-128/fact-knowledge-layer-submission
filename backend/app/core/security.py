from fastapi import Header, HTTPException, status

from app.config import settings


async def verify_api_key(
    x_api_key: str | None = Header(default=None),
) -> None:
    """
    Validate the optional application API key.

    Authentication is disabled when OPENAI_API_KEY is not relevant here
    and no application API key has been configured.
    """
    configured_api_key = getattr(settings, "api_key", "")

    # Authentication is optional for local development.
    if not configured_api_key:
        return

    if x_api_key != configured_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )