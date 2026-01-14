"""
Catalog Search Service using pydantic-ai with tools for iterative exploration.

This implements an agent-based search over the BRC Analytics catalog (assemblies,
organisms) that can explore the schema, preview results, and refine filters
iteratively until finding a good result set.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.openai import OpenAIProvider

from app.core.config import get_settings

logger = logging.getLogger(__name__)


# ============================================================
# Pydantic models for structured output
# ============================================================


class CatalogFilter(BaseModel):
    """A single filter condition for catalog search."""

    column: str = Field(..., description="Column to filter on")
    operator: Literal["eq", "ne", "contains", "in", "gt", "gte", "lt", "lte"] = Field(
        ..., description="Comparison operator"
    )
    value: Any = Field(..., description="Value to compare against")


class CatalogSearch(BaseModel):
    """Structured search parameters for the catalog."""

    filters: list[CatalogFilter] = Field(
        default_factory=list, description="Filter conditions to apply"
    )
    sort_by: str | None = Field(None, description="Column to sort by")
    sort_order: Literal["asc", "desc"] = Field("asc", description="Sort direction")
    limit: int = Field(default=50, le=500, description="Maximum results to return")


class CatalogSearchResult(BaseModel):
    """Result of a catalog search."""

    success: bool
    total_count: int
    results: list[dict]
    filters_applied: list[CatalogFilter]
    message: str | None = None


# ============================================================
# Schema definitions for the catalog
# ============================================================

ASSEMBLY_SCHEMA = {
    "accession": {
        "type": "string",
        "description": "GenBank/RefSeq accession (e.g., GCA_000002545.2)",
        "filterable": True,
        "operators": ["eq", "contains"],
    },
    "level": {
        "type": "enum",
        "description": "Assembly level - indicates completeness",
        "values": ["Complete Genome", "Chromosome", "Scaffold", "Contig"],
        "filterable": True,
        "operators": ["eq", "in"],
    },
    "ploidy": {
        "type": "enum_list",
        "description": "Ploidy level of the organism",
        "values": ["HAPLOID", "DIPLOID", "POLYPLOID"],
        "filterable": True,
        "operators": ["eq", "in", "contains"],
    },
    "taxonomicLevelDomain": {
        "type": "enum",
        "description": "Domain (Eukaryota, Bacteria, Archaea)",
        "values": ["Eukaryota", "Bacteria", "Archaea"],
        "filterable": True,
        "operators": ["eq", "in"],
    },
    "taxonomicLevelKingdom": {
        "type": "string",
        "description": "Taxonomic kingdom",
        "filterable": True,
        "operators": ["eq", "contains"],
    },
    "taxonomicLevelPhylum": {
        "type": "string",
        "description": "Taxonomic phylum",
        "filterable": True,
        "operators": ["eq", "contains"],
    },
    "taxonomicLevelClass": {
        "type": "string",
        "description": "Taxonomic class",
        "filterable": True,
        "operators": ["eq", "contains"],
    },
    "taxonomicLevelOrder": {
        "type": "string",
        "description": "Taxonomic order",
        "filterable": True,
        "operators": ["eq", "contains"],
    },
    "taxonomicLevelFamily": {
        "type": "string",
        "description": "Taxonomic family",
        "filterable": True,
        "operators": ["eq", "contains"],
    },
    "taxonomicLevelGenus": {
        "type": "string",
        "description": "Taxonomic genus",
        "filterable": True,
        "operators": ["eq", "contains"],
    },
    "taxonomicLevelSpecies": {
        "type": "string",
        "description": "Full species name (e.g., 'Plasmodium falciparum')",
        "filterable": True,
        "operators": ["eq", "contains"],
    },
    "taxonomicGroup": {
        "type": "enum_list",
        "description": "Broad taxonomic grouping",
        "values": [
            "Ascomycota",
            "Basidiomycota",
            "Viruses",
            "Bacteria",
            "Apicomplexa",
            "Nematoda",
            "Microsporidia",
            "Arthropoda",
            "Kinetoplastea",
            "Platyhelminthes",
            "Amoebozoa",
        ],
        "filterable": True,
        "operators": ["eq", "in", "contains"],
    },
    "ncbiTaxonomyId": {
        "type": "string",
        "description": "NCBI Taxonomy ID",
        "filterable": True,
        "operators": ["eq", "in"],
    },
    "speciesTaxonomyId": {
        "type": "string",
        "description": "Species-level NCBI Taxonomy ID",
        "filterable": True,
        "operators": ["eq", "in"],
    },
    "isRef": {
        "type": "enum",
        "description": "Is this a reference genome?",
        "values": ["Yes", "No"],
        "filterable": True,
        "operators": ["eq"],
    },
    "scaffoldCount": {
        "type": "integer",
        "description": "Number of scaffolds (fewer = more complete)",
        "range": {"min": 1, "max": 369492},
        "filterable": True,
        "operators": ["eq", "lt", "lte", "gt", "gte"],
    },
    "scaffoldN50": {
        "type": "integer",
        "description": "N50 scaffold length (higher = better assembly)",
        "range": {"min": 689, "max": 409777670},
        "filterable": True,
        "operators": ["eq", "lt", "lte", "gt", "gte"],
    },
    "length": {
        "type": "integer",
        "description": "Total genome length in base pairs",
        "range": {"min": 1673, "max": 2971314966},
        "filterable": True,
        "operators": ["eq", "lt", "lte", "gt", "gte"],
    },
    "gcPercent": {
        "type": "float",
        "description": "GC content percentage",
        "range": {"min": 17.5, "max": 75.5},
        "filterable": True,
        "operators": ["eq", "lt", "lte", "gt", "gte"],
    },
    "strainName": {
        "type": "string",
        "description": "Strain name if applicable",
        "filterable": True,
        "operators": ["eq", "contains"],
    },
    "commonName": {
        "type": "string",
        "description": "Common name of the organism",
        "filterable": True,
        "operators": ["eq", "contains"],
    },
}


# ============================================================
# Dependencies - catalog data and search execution
# ============================================================


@dataclass
class CatalogDeps:
    """Dependencies injected into the catalog search agent."""

    assemblies: list[dict] = field(default_factory=list)
    organisms: list[dict] = field(default_factory=list)
    schema_info: dict = field(default_factory=lambda: ASSEMBLY_SCHEMA)

    @classmethod
    def load(cls, catalog_path: str) -> "CatalogDeps":
        """Load catalog data from JSON files."""
        path = Path(catalog_path)

        assemblies = []
        organisms = []

        assemblies_file = path / "assemblies.json"
        if assemblies_file.exists():
            with open(assemblies_file) as f:
                assemblies = json.load(f)
            logger.info(f"Loaded {len(assemblies)} assemblies from catalog")

        organisms_file = path / "organisms.json"
        if organisms_file.exists():
            with open(organisms_file) as f:
                organisms = json.load(f)
            logger.info(f"Loaded {len(organisms)} organisms from catalog")

        return cls(assemblies=assemblies, organisms=organisms)

    def _matches_filter(self, item: dict, f: CatalogFilter) -> bool:
        """Check if an item matches a single filter condition."""
        value = item.get(f.column)

        # Handle None values
        if value is None:
            return f.operator == "eq" and f.value is None

        # Handle list values (like ploidy, taxonomicGroup)
        if isinstance(value, list):
            if f.operator == "eq":
                return f.value in value
            elif f.operator == "in":
                return any(v in f.value for v in value)
            elif f.operator == "contains":
                return any(str(f.value).lower() in str(v).lower() for v in value)
            return False

        # Standard operators
        if f.operator == "eq":
            return value == f.value
        elif f.operator == "ne":
            return value != f.value
        elif f.operator == "contains":
            return str(f.value).lower() in str(value).lower()
        elif f.operator == "in":
            return value in f.value
        elif f.operator == "gt":
            return value > f.value
        elif f.operator == "gte":
            return value >= f.value
        elif f.operator == "lt":
            return value < f.value
        elif f.operator == "lte":
            return value <= f.value

        return False

    def execute_search(self, search: CatalogSearch) -> dict:
        """Execute a search against the assemblies catalog."""
        results = self.assemblies

        # Apply filters
        for f in search.filters:
            results = [r for r in results if self._matches_filter(r, f)]

        total = len(results)

        # Sort if specified
        if search.sort_by and results:
            reverse = search.sort_order == "desc"
            results.sort(
                key=lambda x: (x.get(search.sort_by) is None, x.get(search.sort_by)),
                reverse=reverse,
            )

        # Apply limit
        results = results[: search.limit]

        # Determine assessment
        if total == 0:
            assessment = "no_results"
        elif total > 500:
            assessment = "too_broad"
        elif total > 100:
            assessment = "broad"
        elif total < 5:
            assessment = "narrow"
        else:
            assessment = "good"

        return {
            "total_count": total,
            "returned_count": len(results),
            "results": results,
            "assessment": assessment,
        }

    def search_organisms(self, search_term: str, limit: int = 20) -> list[dict]:
        """Search organisms by name, returning taxonomy IDs."""
        term = search_term.lower()
        matches = []

        for org in self.organisms:
            species = org.get("taxonomicLevelSpecies", "") or ""
            genus = org.get("taxonomicLevelGenus", "") or ""
            common = org.get("commonName", "") or ""

            if (
                term in species.lower()
                or term in genus.lower()
                or (common and term in common.lower())
            ):
                matches.append(
                    {
                        "species": species,
                        "genus": genus,
                        "common_name": common,
                        "taxonomy_id": org.get("ncbiTaxonomyId"),
                        "assembly_count": org.get("assemblyCount", 0),
                    }
                )

        # Sort by assembly count descending
        matches.sort(key=lambda x: x.get("assembly_count", 0), reverse=True)
        return matches[:limit]

    def get_distinct_values(self, column: str, limit: int = 50) -> list[str]:
        """Get distinct values for a column."""
        values = set()
        for a in self.assemblies:
            v = a.get(column)
            if v is not None:
                if isinstance(v, list):
                    values.update(v)
                else:
                    values.add(v)

        # Convert to sorted list, handling mixed types
        result = sorted([str(v) for v in values if v])
        return result[:limit]


# ============================================================
# System prompt for the catalog search agent
# ============================================================

CATALOG_SEARCH_PROMPT = """You help users find genome assemblies in the BRC Analytics catalog.

<catalog_overview>
The catalog contains {assembly_count} genome assemblies from {organism_count} organisms.
Main groups: fungi, bacteria, viruses, parasites (Apicomplexa, Kinetoplastea), and other pathogens.
</catalog_overview>

<vocabulary>
Users may use informal terms. Map them to catalog values:
- "complete genome" or "finished" → level = "Complete Genome"
- "draft genome" → level in ["Scaffold", "Contig"]
- "chromosome level" → level = "Chromosome"
- "high quality" → sort by scaffoldCount ascending (fewer scaffolds = better)
- "reference genome" → isRef = "Yes"
- "malaria" → search for "Plasmodium" in organisms
- "TB" or "tuberculosis" → search for "Mycobacterium tuberculosis"
- "yeast" → search for "Saccharomyces" or taxonomicGroup contains "Ascomycota"
- "fungus/fungi" → taxonomicGroup contains relevant fungal groups
- "bacteria/bacterial" → taxonomicLevelDomain = "Bacteria"
- "parasite" → taxonomicGroup in ["Apicomplexa", "Kinetoplastea", "Platyhelminthes", "Nematoda"]
</vocabulary>

<process>
1. First, use get_schema() to understand available columns and their values
2. If the user mentions an organism name, use search_organisms() to find the correct taxonomy ID
3. Use preview_search() to test your filters and see result counts
4. If results are too broad (>500), add more specific filters
5. If results are too narrow (0), relax constraints or try alternative filters
6. Iterate until you have a reasonable result set (5-100 is ideal)
7. Return the final CatalogSearch with your refined filters
</process>

<tips>
- Start broad with organism/domain, then narrow down
- taxonomicLevelSpecies for exact species, taxonomicLevelGenus for genus-level
- Use "contains" operator for partial name matches
- scaffoldCount is a good quality indicator - lower is better
- Always preview before finalizing to verify result counts
</tips>
"""


# ============================================================
# Catalog Search Service
# ============================================================


class CatalogSearchService:
    """Service for searching the BRC catalog using an AI agent with tools."""

    def __init__(self, catalog_path: str | None = None):
        self.settings = get_settings()
        self.catalog_path = catalog_path or self.settings.CATALOG_PATH
        self.deps: CatalogDeps | None = None
        self.agent: Agent | None = None

        self._initialize()

    def _initialize(self):
        """Initialize the catalog data and agent."""
        if not self.settings.AI_API_KEY:
            logger.warning(
                "AI API key not configured - catalog search will be disabled"
            )
            return

        # Load catalog data
        try:
            self.deps = CatalogDeps.load(self.catalog_path)
        except Exception as e:
            logger.error(f"Failed to load catalog: {e}")
            return

        # Create the model
        try:
            is_anthropic = (
                self.settings.AI_API_BASE_URL
                and "anthropic.com" in self.settings.AI_API_BASE_URL
            )

            if is_anthropic:
                provider = AnthropicProvider(api_key=self.settings.AI_API_KEY)
                model = AnthropicModel(
                    self.settings.AI_PRIMARY_MODEL, provider=provider
                )
            else:
                provider = OpenAIProvider(
                    api_key=self.settings.AI_API_KEY,
                    base_url=self.settings.AI_API_BASE_URL or None,
                )
                model = OpenAIChatModel(
                    self.settings.AI_PRIMARY_MODEL, provider=provider
                )

            # Format the system prompt with catalog stats
            system_prompt = CATALOG_SEARCH_PROMPT.format(
                assembly_count=len(self.deps.assemblies),
                organism_count=len(self.deps.organisms),
            )

            # Create the agent with structured output
            self.agent = Agent(
                model,
                deps_type=CatalogDeps,
                output_type=CatalogSearch,
                instructions=system_prompt,
            )

            # Register tools
            self._register_tools()

            logger.info("Catalog search service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize catalog search agent: {e}")
            self.agent = None

    def _register_tools(self):
        """Register tools on the agent."""
        if not self.agent:
            return

        @self.agent.tool
        async def get_schema(
            ctx: RunContext[CatalogDeps], columns: list[str] | None = None
        ) -> dict:
            """Get schema information for catalog columns.

            Args:
                columns: Specific columns to get info for, or None for overview.

            Returns:
                Schema details including types, valid values, and operators.
            """
            schema = ctx.deps.schema_info
            if columns:
                return {k: v for k, v in schema.items() if k in columns}
            # Return overview with just column names and descriptions
            return {
                "columns": {k: v.get("description", "") for k, v in schema.items()},
                "total_columns": len(schema),
                "hint": "Call with specific column names for detailed info including valid values",
            }

        @self.agent.tool
        async def search_organisms(
            ctx: RunContext[CatalogDeps], search_term: str
        ) -> list[dict]:
            """Search for organisms by name to find their taxonomy IDs.

            Args:
                search_term: Organism name to search for (partial matches work).

            Returns:
                List of matching organisms with taxonomy IDs and assembly counts.
            """
            return ctx.deps.search_organisms(search_term)

        @self.agent.tool
        async def get_column_values(
            ctx: RunContext[CatalogDeps], column: str
        ) -> list[str]:
            """Get distinct values for a column (useful for enum/categorical columns).

            Args:
                column: The column name to get values for.

            Returns:
                List of distinct values found in that column.
            """
            return ctx.deps.get_distinct_values(column)

        @self.agent.tool
        async def preview_search(
            ctx: RunContext[CatalogDeps], filters: list[dict]
        ) -> dict:
            """Preview search results with given filters before finalizing.

            Args:
                filters: List of filter dicts with 'column', 'operator', 'value' keys.

            Returns:
                Result count, assessment (too_broad/good/narrow/no_results), and sample results.
            """
            try:
                parsed_filters = [CatalogFilter(**f) for f in filters]
                search = CatalogSearch(filters=parsed_filters, limit=5)
                result = ctx.deps.execute_search(search)
                return {
                    "total_count": result["total_count"],
                    "assessment": result["assessment"],
                    "sample_results": [
                        {
                            "accession": r.get("accession"),
                            "species": r.get("taxonomicLevelSpecies"),
                            "level": r.get("level"),
                            "scaffoldCount": r.get("scaffoldCount"),
                        }
                        for r in result["results"][:3]
                    ],
                }
            except Exception as e:
                return {"error": str(e)}

    def is_available(self) -> bool:
        """Check if the service is available."""
        return self.agent is not None and self.deps is not None

    async def search(self, query: str) -> CatalogSearchResult:
        """Search the catalog using natural language.

        Args:
            query: Natural language search query.

        Returns:
            CatalogSearchResult with matching assemblies.
        """
        if not self.is_available():
            return CatalogSearchResult(
                success=False,
                total_count=0,
                results=[],
                filters_applied=[],
                message="Catalog search service not available",
            )

        try:
            logger.info(f"Catalog search query: {query}")

            # Run the agent to get filters
            result = await self.agent.run(query, deps=self.deps)
            search_params = result.output

            logger.info(f"Agent returned filters: {search_params.filters}")

            # Execute the final search
            search_result = self.deps.execute_search(search_params)

            return CatalogSearchResult(
                success=True,
                total_count=search_result["total_count"],
                results=search_result["results"],
                filters_applied=search_params.filters,
                message=f"Found {search_result['total_count']} assemblies",
            )

        except Exception as e:
            logger.error(f"Catalog search failed: {e}")
            return CatalogSearchResult(
                success=False,
                total_count=0,
                results=[],
                filters_applied=[],
                message=f"Search failed: {str(e)}",
            )

    def direct_search(self, search: CatalogSearch) -> CatalogSearchResult:
        """Execute a search directly without using the agent.

        Useful for programmatic access or when filters are already known.
        """
        if not self.deps:
            return CatalogSearchResult(
                success=False,
                total_count=0,
                results=[],
                filters_applied=[],
                message="Catalog not loaded",
            )

        result = self.deps.execute_search(search)
        return CatalogSearchResult(
            success=True,
            total_count=result["total_count"],
            results=result["results"],
            filters_applied=search.filters,
        )

    async def conversational_search(
        self,
        query: str,
        message_history: list | None = None,
        current_filters: list | None = None,
    ) -> tuple[CatalogSearchResult, list]:
        """
        Search with conversation context for multi-turn refinement.

        Args:
            query: The user's query for this turn.
            message_history: Previous messages from pydantic-ai (for context).
            current_filters: Currently applied filters from previous turns.

        Returns:
            Tuple of (search result, updated message history).
        """
        if not self.is_available():
            return (
                CatalogSearchResult(
                    success=False,
                    total_count=0,
                    results=[],
                    filters_applied=[],
                    message="Catalog search service not available",
                ),
                [],
            )

        try:
            # Build context prompt with current state
            context_parts = []

            if current_filters:
                filter_desc = ", ".join(
                    f"{f['column']} {f['operator']} {f['value']}"
                    for f in current_filters
                )
                context_parts.append(f"Current filters: {filter_desc}")

            if context_parts:
                context = "\n".join(context_parts)
                augmented_query = f"{context}\n\nUser request: {query}"
            else:
                augmented_query = query

            logger.info(f"Conversational search: {query}")
            logger.info(
                f"Message history length: {len(message_history) if message_history else 0}"
            )

            # Run the agent with message history for context
            result = await self.agent.run(
                augmented_query,
                deps=self.deps,
                message_history=message_history,
            )
            search_params = result.output

            logger.info(f"Agent returned filters: {search_params.filters}")

            # Execute the search
            search_result = self.deps.execute_search(search_params)

            # Get updated message history for next turn
            new_history = result.all_messages()

            return (
                CatalogSearchResult(
                    success=True,
                    total_count=search_result["total_count"],
                    results=search_result["results"],
                    filters_applied=search_params.filters,
                    message=f"Found {search_result['total_count']} assemblies",
                ),
                new_history,
            )

        except Exception as e:
            logger.error(f"Conversational search failed: {e}")
            return (
                CatalogSearchResult(
                    success=False,
                    total_count=0,
                    results=[],
                    filters_applied=[],
                    message=f"Search failed: {str(e)}",
                ),
                message_history or [],
            )
