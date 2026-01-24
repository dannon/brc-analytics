"""
ENA/SRA Search API endpoints.

Provides natural language search over ENA/SRA sequencing data using an AI agent.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import get_ena_search_service
from app.models.ena_search import (
    ENAConversationalSearchRequest,
    ENAConversationalSearchResponse,
    ENADirectSearchRequest,
    ENAFieldValuesResponse,
    ENAFilter,
    ENAHealthResponse,
    ENASchemaResponse,
    ENASearch,
    ENASearchRequest,
    ENASearchResult,
)
from app.services.ena_search import ENA_SCHEMA, ENASearchService
from app.services.session import SearchFilter, get_session_service

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================
# Endpoints
# ============================================================


@router.get("/health", response_model=ENAHealthResponse)
async def ena_search_health(
    service: ENASearchService = Depends(get_ena_search_service),
) -> ENAHealthResponse:
    """Check health of the ENA search service."""
    return ENAHealthResponse(
        status="healthy" if service.is_available() else "degraded",
        ena_service_available=service.ena_service is not None,
        agent_available=service.agent is not None,
    )


@router.post("/search", response_model=ENASearchResult)
async def natural_language_search(
    request: ENASearchRequest,
    service: ENASearchService = Depends(get_ena_search_service),
) -> ENASearchResult:
    """Search ENA/SRA using natural language.

    The AI agent will:
    1. Interpret your query (organism, sequencing type, platform, etc.)
    2. Determine the best search strategy
    3. Build appropriate filters
    4. Return matching sequencing runs

    Examples:
    - "Plasmodium falciparum RNA-seq paired-end data"
    - "Candida auris whole genome sequencing from Illumina"
    - "tuberculosis samples with high read counts"
    - "ATAC-seq data from Nanopore"
    """
    if not service.is_available():
        raise HTTPException(status_code=503, detail="ENA search service not available")

    result = await service.search(request.query)

    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)

    return result


@router.post("/search/conversation", response_model=ENAConversationalSearchResponse)
async def conversational_search(
    request: ENAConversationalSearchRequest,
    service: ENASearchService = Depends(get_ena_search_service),
) -> ENAConversationalSearchResponse:
    """Search ENA/SRA with multi-turn conversation support.

    This endpoint maintains conversation state across multiple requests,
    allowing you to progressively refine your search.

    Workflow:
    1. First request: Send a query without session_id to start a new conversation
    2. Response: Receive results and a session_id
    3. Subsequent requests: Include the session_id to refine the search
    4. The AI remembers context and can handle refinements

    Examples:
    - Turn 1: "Candida auris whole genome sequencing" -> Returns 50 results
    - Turn 2: "only Illumina paired-end" -> Returns 20 results
    - Turn 3: "with more than 1 million reads" -> Returns 8 results

    Sessions expire after 1 hour of inactivity.
    """
    if not service.is_available():
        raise HTTPException(status_code=503, detail="ENA search service not available")

    # Get or create session
    session_service = await get_session_service()
    session = await session_service.get_or_create_session(request.session_id)

    # Convert session filters to dict format for the agent
    current_filters = [
        {"field": f.column, "operator": f.operator, "value": f.value}
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
    session.add_assistant_message(result.message or "Search completed")
    session.agent_messages = new_messages
    session.last_result_count = result.total_count
    session.last_query = request.query

    # Update filters from result (using 'field' key for ENAFilter)
    if result.filters_applied:
        session.filters = [
            SearchFilter(
                column=f.field if hasattr(f, "field") else f.get("field", ""),
                operator=f.operator
                if hasattr(f, "operator")
                else f.get("operator", "eq"),
                value=f.value if hasattr(f, "value") else f.get("value"),
            )
            for f in result.filters_applied
        ]

    await session_service.update_session(session)

    # Convert filters to dict for response
    filters_dict = [
        {"field": f.field, "operator": f.operator, "value": f.value}
        for f in (result.filters_applied or [])
    ]

    return ENAConversationalSearchResponse(
        session_id=session.session_id,
        success=result.success,
        total_count=result.total_count,
        results=result.results,
        filters_applied=filters_dict,
        message=result.message or "Search completed",
        turn_count=len([m for m in session.messages if m.role == "user"]),
        cached=result.cached,
    )


@router.post("/search/direct", response_model=ENASearchResult)
async def direct_search(
    request: ENADirectSearchRequest,
    service: ENASearchService = Depends(get_ena_search_service),
) -> ENASearchResult:
    """Search ENA directly with explicit parameters (no LLM).

    Useful for programmatic access when you know exactly what to search for.

    Search methods:
    - "taxonomy": Search by taxonomy ID (requires taxonomy_id parameter)
    - "accession": Look up specific accession (requires accession parameter)
    - "keywords": Search by keywords (requires keywords parameter)

    Filter operators:
    - eq: equals
    - ne: not equals
    - contains: substring match
    - in: value in list
    - gt, gte, lt, lte: numeric comparisons

    Example request:
    ```json
    {
        "search_method": "taxonomy",
        "taxonomy_id": "36329",
        "filters": [
            {"field": "library_layout", "operator": "eq", "value": "PAIRED"},
            {"field": "library_strategy", "operator": "eq", "value": "RNA-Seq"}
        ],
        "limit": 50
    }
    ```
    """
    if not service.deps:
        raise HTTPException(status_code=503, detail="ENA service not available")

    try:
        filters = [ENAFilter(**f) for f in request.filters]
        search_params = ENASearch(
            search_method=request.search_method,
            taxonomy_id=request.taxonomy_id,
            accession=request.accession,
            keywords=request.keywords,
            filters=filters,
            limit=request.limit,
        )
        return await service.direct_search_async(search_params)
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid search parameters: {e}"
        ) from e


@router.get("/schema", response_model=ENASchemaResponse)
async def get_schema(
    service: ENASearchService = Depends(get_ena_search_service),
) -> ENASchemaResponse:
    """Get the ENA schema with filterable fields and their valid values."""
    return ENASchemaResponse(
        fields=ENA_SCHEMA,
        total_fields=len(ENA_SCHEMA),
    )


@router.get("/values/{field}", response_model=ENAFieldValuesResponse)
async def get_field_values(
    field: str,
    service: ENASearchService = Depends(get_ena_search_service),
) -> ENAFieldValuesResponse:
    """Get valid values for a specific ENA field.

    Useful for understanding what values are available for filtering.
    Only enum-type fields have predefined values.
    """
    if field not in ENA_SCHEMA:
        valid_fields = list(ENA_SCHEMA.keys())
        raise HTTPException(
            status_code=400,
            detail=f"Unknown field: {field}. Valid fields: {valid_fields}",
        )

    field_info = ENA_SCHEMA[field]
    values = field_info.get("values", [])

    if not values:
        raise HTTPException(
            status_code=400,
            detail=f"Field '{field}' does not have predefined values (type: {field_info.get('type')})",
        )

    return ENAFieldValuesResponse(
        field=field,
        values=values,
        description=field_info.get("description"),
    )
