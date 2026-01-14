"""
Catalog Search API endpoints.

Provides natural language search over the BRC Analytics catalog (assemblies, organisms).
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.dependencies import get_catalog_search_service
from app.services.catalog_search import (
    CatalogFilter,
    CatalogSearch,
    CatalogSearchResult,
    CatalogSearchService,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================
# Request/Response Models
# ============================================================


class NaturalLanguageSearchRequest(BaseModel):
    """Request for natural language catalog search."""

    query: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Natural language search query",
        examples=["complete malaria genomes", "draft bacterial assemblies"],
    )


class DirectSearchRequest(BaseModel):
    """Request for direct (non-LLM) catalog search."""

    filters: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Filter conditions with column, operator, value",
    )
    sort_by: str | None = Field(None, description="Column to sort by")
    sort_order: str = Field("asc", description="Sort order (asc/desc)")
    limit: int = Field(50, ge=1, le=500, description="Maximum results")


class CatalogHealthResponse(BaseModel):
    """Health check response for catalog service."""

    status: str
    catalog_loaded: bool
    assembly_count: int
    organism_count: int
    agent_available: bool


# ============================================================
# Endpoints
# ============================================================


@router.get("/health", response_model=CatalogHealthResponse)
async def catalog_health(
    service: CatalogSearchService = Depends(get_catalog_search_service),
) -> CatalogHealthResponse:
    """Check health of the catalog search service."""
    if service.deps:
        return CatalogHealthResponse(
            status="healthy" if service.is_available() else "degraded",
            catalog_loaded=True,
            assembly_count=len(service.deps.assemblies),
            organism_count=len(service.deps.organisms),
            agent_available=service.agent is not None,
        )
    return CatalogHealthResponse(
        status="unhealthy",
        catalog_loaded=False,
        assembly_count=0,
        organism_count=0,
        agent_available=False,
    )


@router.post("/search", response_model=CatalogSearchResult)
async def natural_language_search(
    request: NaturalLanguageSearchRequest,
    service: CatalogSearchService = Depends(get_catalog_search_service),
) -> CatalogSearchResult:
    """Search the catalog using natural language.

    The AI agent will:
    1. Interpret your query
    2. Explore the catalog schema
    3. Build and refine filters iteratively
    4. Return matching assemblies

    Examples:
    - "complete Plasmodium falciparum genomes"
    - "high quality fungal assemblies"
    - "draft bacterial genomes from the Enterobacteriaceae family"
    - "reference genomes for parasites"
    """
    if not service.is_available():
        raise HTTPException(
            status_code=503, detail="Catalog search service not available"
        )

    result = await service.search(request.query)

    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)

    return result


@router.post("/search/direct", response_model=CatalogSearchResult)
async def direct_search(
    request: DirectSearchRequest,
    service: CatalogSearchService = Depends(get_catalog_search_service),
) -> CatalogSearchResult:
    """Search the catalog directly with explicit filters (no LLM).

    Useful for programmatic access when you know exactly what filters to apply.

    Filter operators:
    - eq: equals
    - ne: not equals
    - contains: substring match (case-insensitive)
    - in: value in list
    - gt, gte, lt, lte: numeric comparisons

    Example request:
    ```json
    {
        "filters": [
            {"column": "taxonomicLevelSpecies", "operator": "contains", "value": "Plasmodium"},
            {"column": "level", "operator": "eq", "value": "Complete Genome"}
        ],
        "sort_by": "scaffoldCount",
        "sort_order": "asc",
        "limit": 20
    }
    ```
    """
    if not service.deps:
        raise HTTPException(status_code=503, detail="Catalog not loaded")

    try:
        filters = [CatalogFilter(**f) for f in request.filters]
        search = CatalogSearch(
            filters=filters,
            sort_by=request.sort_by,
            sort_order=request.sort_order,  # type: ignore
            limit=request.limit,
        )
        return service.direct_search(search)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid search parameters: {e}")


@router.get("/schema")
async def get_schema(
    service: CatalogSearchService = Depends(get_catalog_search_service),
) -> dict:
    """Get the catalog schema with filterable columns and their valid values."""
    if not service.deps:
        raise HTTPException(status_code=503, detail="Catalog not loaded")

    return {
        "columns": service.deps.schema_info,
        "assembly_count": len(service.deps.assemblies),
        "organism_count": len(service.deps.organisms),
    }


@router.get("/organisms")
async def search_organisms(
    q: str = "",
    limit: int = 20,
    service: CatalogSearchService = Depends(get_catalog_search_service),
) -> list[dict]:
    """Search organisms by name.

    Returns matching organisms with their taxonomy IDs and assembly counts.
    Useful for finding the correct taxonomy ID to use in filters.
    """
    if not service.deps:
        raise HTTPException(status_code=503, detail="Catalog not loaded")

    if not q or len(q) < 2:
        raise HTTPException(
            status_code=400, detail="Search term must be at least 2 characters"
        )

    return service.deps.search_organisms(q, limit=min(limit, 100))


@router.get("/values/{column}")
async def get_column_values(
    column: str,
    limit: int = 50,
    service: CatalogSearchService = Depends(get_catalog_search_service),
) -> dict:
    """Get distinct values for a specific column.

    Useful for understanding what values are available for filtering.
    """
    if not service.deps:
        raise HTTPException(status_code=503, detail="Catalog not loaded")

    if column not in service.deps.schema_info:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown column: {column}. Valid columns: {list(service.deps.schema_info.keys())}",
        )

    values = service.deps.get_distinct_values(column, limit=min(limit, 200))
    return {
        "column": column,
        "values": values,
        "count": len(values),
    }
