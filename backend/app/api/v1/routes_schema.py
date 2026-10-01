from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.deps import get_database, require_api_key
from app.infra.db.repositories.fact_type_repo import FactTypeRepository


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


# H-2: Routes now delegate directly to FactTypeRepository (backed by
# PostgreSQL) instead of the in-memory SchemaRegistryService singleton.
# This means fact types survive process restarts and are visible to workers.


@router.post(
    "/fact-types",
    response_model=FactTypeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_fact_type(
    request: FactTypeCreateRequest,
    db: Session = Depends(get_database),
) -> FactTypeResponse:
    """
    Create a fact type or return the existing type with the same name.
    """

    repo = FactTypeRepository(db)
    fact_type = repo.get_or_create(
        name=request.name,
        description=request.description,
        value_schema=request.value_schema,
    )
    db.commit()

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
def list_fact_types(
    db: Session = Depends(get_database),
) -> list[FactTypeResponse]:
    """
    List all active fact types.
    """

    from sqlalchemy import select
    from app.infra.db.models_orm import FactTypeORM

    orm_types = (
        db.execute(
            select(FactTypeORM)
            .where(FactTypeORM.is_active.is_(True))
            .order_by(FactTypeORM.created_at)
        )
        .scalars()
        .all()
    )

    return [
        FactTypeResponse(
            id=ft.id,
            name=ft.name,
            description=ft.description,
            value_schema=ft.value_schema,
            version=ft.version,
            is_active=ft.is_active,
        )
        for ft in orm_types
    ]


@router.get(
    "/fact-types/{fact_type_id}",
    response_model=FactTypeResponse,
)
def get_fact_type(
    fact_type_id: str,
    db: Session = Depends(get_database),
) -> FactTypeResponse:
    """
    Retrieve a fact type by ID.
    """

    from app.infra.db.models_orm import FactTypeORM

    orm_ft = db.get(FactTypeORM, fact_type_id)

    if orm_ft is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fact type not found: {fact_type_id}",
        )

    return FactTypeResponse(
        id=orm_ft.id,
        name=orm_ft.name,
        description=orm_ft.description,
        value_schema=orm_ft.value_schema,
        version=orm_ft.version,
        is_active=orm_ft.is_active,
    )
