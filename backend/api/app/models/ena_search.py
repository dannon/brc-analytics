"""
Pydantic models for ENA/SRA LLM-powered search.

Defines structured output models for the pydantic-ai agent and
request/response models for the API endpoints.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

# ============================================================
# Agent Output Models
# ============================================================


class ENAFilter(BaseModel):
    """A filter condition for ENA search results."""

    field: str = Field(..., description="ENA field to filter on")
    operator: Literal["eq", "ne", "contains", "in", "gt", "gte", "lt", "lte"] = Field(
        ..., description="Comparison operator"
    )
    value: Any = Field(..., description="Value to compare against")


class ENASearch(BaseModel):
    """
    Structured search parameters for ENA/SRA.

    The agent produces this as output after interpreting the user's query.
    """

    search_method: Literal["taxonomy", "accession", "keywords"] = Field(
        ..., description="Primary search method to use"
    )
    taxonomy_id: str | None = Field(
        None, description="NCBI Taxonomy ID for organism-based search"
    )
    accession: str | None = Field(
        None, description="Specific accession number to look up"
    )
    keywords: list[str] = Field(
        default_factory=list, description="Keywords for text-based search"
    )
    filters: list[ENAFilter] = Field(
        default_factory=list, description="Post-query filters to apply"
    )
    limit: int = Field(default=100, le=500, description="Maximum results to return")


class ENASearchResult(BaseModel):
    """Result of an ENA search."""

    success: bool
    total_count: int
    results: list[dict[str, Any]]
    filters_applied: list[ENAFilter]
    search_params: ENASearch | None = None
    message: str | None = None
    cached: bool = False


# ============================================================
# API Request/Response Models
# ============================================================


class ENASearchRequest(BaseModel):
    """Request for natural language ENA search."""

    query: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Natural language search query",
        examples=[
            "Plasmodium falciparum RNA-seq paired-end data",
            "Candida auris whole genome sequencing from Illumina",
        ],
    )


class ENAConversationalSearchRequest(BaseModel):
    """Request for conversational (multi-turn) ENA search."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Natural language search query or refinement",
        examples=[
            "Candida auris whole genome sequencing",
            "only Illumina paired-end",
            "show me just the recent ones",
        ],
    )
    session_id: str | None = Field(
        None,
        description="Session ID for continuing a conversation. "
        "Omit to start new session.",
    )


class ENAConversationalSearchResponse(BaseModel):
    """Response from conversational ENA search."""

    session_id: str = Field(
        ..., description="Session ID for continuing this conversation"
    )
    success: bool
    total_count: int
    results: list[dict[str, Any]]
    filters_applied: list[dict[str, Any]]
    message: str
    turn_count: int = Field(..., description="Number of exchanges in this conversation")
    cached: bool = False


class ENADirectSearchRequest(BaseModel):
    """Request for direct (non-LLM) ENA search."""

    search_method: Literal["taxonomy", "accession", "keywords"] = Field(
        ..., description="Search method"
    )
    taxonomy_id: str | None = Field(None, description="Taxonomy ID for tax search")
    accession: str | None = Field(None, description="Accession for direct lookup")
    keywords: list[str] = Field(default_factory=list, description="Keywords for search")
    filters: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Post-query filters with field, operator, value",
    )
    limit: int = Field(100, ge=1, le=500, description="Maximum results")


class ENAHealthResponse(BaseModel):
    """Health check response for ENA search service."""

    status: str
    ena_service_available: bool
    agent_available: bool


class ENASchemaResponse(BaseModel):
    """Schema information for ENA fields."""

    fields: dict[str, dict[str, Any]]
    total_fields: int


class ENAFieldValuesResponse(BaseModel):
    """Valid values for an ENA field."""

    field: str
    values: list[str]
    description: str | None = None
