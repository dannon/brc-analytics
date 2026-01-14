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
from app.services.session import SearchFilter, get_session_service

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


class ConversationalSearchRequest(BaseModel):
    """Request for conversational (multi-turn) catalog search."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Natural language search query or refinement",
        examples=[
            "complete malaria genomes",
            "narrow that to just Plasmodium falciparum",
            "only the reference genomes",
        ],
    )
    session_id: str | None = Field(
        None,
        description="Session ID for continuing a conversation. "
        "Omit to start new session.",
    )


class ConversationalSearchResponse(BaseModel):
    """Response from conversational catalog search."""

    session_id: str = Field(
        ..., description="Session ID for continuing this conversation"
    )
    success: bool
    total_count: int
    results: list[dict[str, Any]]
    filters_applied: list[dict[str, Any]]
    message: str
    turn_count: int = Field(..., description="Number of exchanges in this conversation")


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


@router.post("/search/conversation", response_model=ConversationalSearchResponse)
async def conversational_search(
    request: ConversationalSearchRequest,
    service: CatalogSearchService = Depends(get_catalog_search_service),
) -> ConversationalSearchResponse:
    """Search the catalog using natural language with multi-turn conversation support.

    This endpoint maintains conversation state across multiple requests, allowing you to
    progressively refine your search. Each exchange builds on previous context.

    Workflow:
    1. First request: Send a query without session_id to start a new conversation
    2. Response: Receive results and a session_id
    3. Subsequent requests: Include the session_id to refine/narrow the search
    4. The AI remembers context and can handle refinements like "narrow that to..."

    Examples:
    - Turn 1: "complete malaria genomes" → Returns 50 results
    - Turn 2: "narrow to Plasmodium falciparum" → Returns 12 results
    - Turn 3: "only reference genomes" → Returns 2 results

    Sessions expire after 1 hour of inactivity.
    """
    if not service.is_available():
        raise HTTPException(
            status_code=503, detail="Catalog search service not available"
        )

    # Get or create session
    session_service = await get_session_service()
    session = await session_service.get_or_create_session(request.session_id)

    # Convert session filters to dict format for the agent
    current_filters = [
        {"column": f.column, "operator": f.operator, "value": f.value}
        for f in session.filters
    ]

    # Run conversational search with session context
    result, new_messages = await service.conversational_search(
        query=request.query,
        message_history=session.agent_messages if session.agent_messages else None,
        current_filters=current_filters if current_filters else None,
    )

    # Update session with new state
    session.add_user_message(request.query)
    session.add_assistant_message(result.message)
    session.agent_messages = new_messages
    session.last_result_count = result.total_count
    session.last_query = request.query

    # Update filters from result
    if result.filters_applied:
        session.filters = [
            SearchFilter(
                column=f.column if hasattr(f, "column") else f["column"],
                operator=f.operator if hasattr(f, "operator") else f["operator"],
                value=f.value if hasattr(f, "value") else f["value"],
            )
            for f in result.filters_applied
        ]

    await session_service.update_session(session)

    # Convert filters to dict for response
    filters_dict = [
        {"column": f.column, "operator": f.operator, "value": f.value}
        for f in (result.filters_applied or [])
    ]

    return ConversationalSearchResponse(
        session_id=session.session_id,
        success=result.success,
        total_count=result.total_count,
        results=result.results,
        filters_applied=filters_dict,
        message=result.message,
        turn_count=len([m for m in session.messages if m.role == "user"]),
    )


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
            {"column": "taxonomicLevelSpecies", "operator": "contains",
             "value": "Plasmodium"},
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
        raise HTTPException(
            status_code=400, detail=f"Invalid search parameters: {e}"
        ) from e


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
        valid_cols = list(service.deps.schema_info.keys())
        raise HTTPException(
            status_code=400,
            detail=f"Unknown column: {column}. Valid columns: {valid_cols}",
        )

    values = service.deps.get_distinct_values(column, limit=min(limit, 200))
    return {
        "column": column,
        "values": values,
        "count": len(values),
    }
