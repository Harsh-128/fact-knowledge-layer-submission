from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.v1.deps import require_api_key
from app.domain.services.schema_registry_service import (
    SchemaRegistryService,
)


router = APIRouter(
    prefix="/schema",
    tags=["schema"],
    dependencies=[Depends(require_api_key)],
)


class FactTypeCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: str | None = None
    value_schema: dict = Field(default_factory=dict)


class FactTypeResponse(BaseModel):
    id: str
    name: str
    description: str | None
    value_schema: dict
    version: int
    is_active: bool


# One registry instance is shared by this API process.
registry = SchemaRegistryService()


@router.post(
    "/fact-types",
    response_model=FactTypeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_fact_type(
    request: FactTypeCreateRequest,
) -> FactTypeResponse:
    """
    Create a fact type or return the existing type with the same name.
    """

    fact_type = registry.get_or_create(
        name=request.name,
        description=request.description,
        value_schema=request.value_schema,
    )

    return FactTypeResponse(
        id=fact_type.id,
        name=fact_type.name,
        description=fact_type.description,
        value_schema=fact_type.value_schema,
        version=fact_type.version,
        is_active=fact_type.is_active,
    )


@router.get(
    "/fact-types",
    response_model=list[FactTypeResponse],
)
def list_fact_types() -> list[FactTypeResponse]:
    """
    List all active fact types.
    """

    return [
        FactTypeResponse(
            id=fact_type.id,
            name=fact_type.name,
            description=fact_type.description,
            value_schema=fact_type.value_schema,
            version=fact_type.version,
            is_active=fact_type.is_active,
        )
        for fact_type in registry.list_active()
    ]


@router.get(
    "/fact-types/{fact_type_id}",
    response_model=FactTypeResponse,
)
def get_fact_type(
    fact_type_id: str,
) -> FactTypeResponse:
    """
    Retrieve a fact type by ID.
    """

    fact_type = registry.get_by_id(fact_type_id)

    if fact_type is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fact type not found: {fact_type_id}",
        )

    return FactTypeResponse(
        id=fact_type.id,
        name=fact_type.name,
        description=fact_type.description,
        value_schema=fact_type.value_schema,
        version=fact_type.version,
        is_active=fact_type.is_active,
    )
