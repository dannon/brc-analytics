"""
ENA/SRA Search Service using pydantic-ai with tools for iterative exploration.

This implements an agent-based search over ENA/SRA sequencing data that can
interpret natural language queries, search by taxonomy or keywords, and apply
post-query filters.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from pydantic_ai import Agent, RunContext
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.openai import OpenAIProvider

from app.core.config import get_settings
from app.models.ena_search import ENAFilter, ENASearch, ENASearchResult
from app.services.ena_service import ENAService

logger = logging.getLogger(__name__)


# ============================================================
# ENA Schema Definition
# ============================================================

ENA_SCHEMA: dict[str, dict[str, Any]] = {
    "library_layout": {
        "type": "enum",
        "description": "Sequencing library layout",
        "values": ["PAIRED", "SINGLE"],
        "filterable": True,
        "operators": ["eq"],
    },
    "library_strategy": {
        "type": "enum",
        "description": "Sequencing strategy/assay type",
        "values": [
            "WGS",
            "WXS",
            "RNA-Seq",
            "ChIP-Seq",
            "ATAC-seq",
            "Bisulfite-Seq",
            "AMPLICON",
            "Hi-C",
            "RAD-Seq",
            "Targeted-Capture",
            "OTHER",
        ],
        "filterable": True,
        "operators": ["eq", "in"],
    },
    "library_source": {
        "type": "enum",
        "description": "Source material",
        "values": [
            "GENOMIC",
            "TRANSCRIPTOMIC",
            "METAGENOMIC",
            "METATRANSCRIPTOMIC",
            "SYNTHETIC",
            "VIRAL RNA",
            "OTHER",
        ],
        "filterable": True,
        "operators": ["eq", "in"],
    },
    "instrument_platform": {
        "type": "enum",
        "description": "Sequencing platform",
        "values": [
            "ILLUMINA",
            "PACBIO_SMRT",
            "OXFORD_NANOPORE",
            "ION_TORRENT",
            "BGISEQ",
            "DNBSEQ",
            "COMPLETE_GENOMICS",
            "LS454",
        ],
        "filterable": True,
        "operators": ["eq", "in"],
    },
    "instrument_model": {
        "type": "string",
        "description": "Specific sequencing instrument model",
        "examples": [
            "Illumina MiSeq",
            "Illumina NovaSeq 6000",
            "MinION",
            "PromethION",
        ],
        "filterable": True,
        "operators": ["eq", "contains"],
    },
    "scientific_name": {
        "type": "string",
        "description": "Scientific name of the organism",
        "filterable": True,
        "operators": ["eq", "contains"],
    },
    "tax_id": {
        "type": "string",
        "description": "NCBI Taxonomy ID",
        "filterable": True,
        "operators": ["eq"],
    },
    "read_count": {
        "type": "integer",
        "description": "Number of reads",
        "filterable": True,
        "operators": ["gt", "gte", "lt", "lte"],
    },
    "base_count": {
        "type": "integer",
        "description": "Total base pairs",
        "filterable": True,
        "operators": ["gt", "gte", "lt", "lte"],
    },
    "study_title": {
        "type": "string",
        "description": "Title of the study",
        "filterable": True,
        "operators": ["contains"],
    },
    "first_public": {
        "type": "date",
        "description": "Date when data was first made public",
        "filterable": True,
        "operators": ["gt", "gte", "lt", "lte"],
    },
}

# Common organism vocabulary mappings (name -> taxonomy ID)
ORGANISM_VOCABULARY: dict[str, str] = {
    "malaria": "5833",  # Plasmodium (genus)
    "plasmodium": "5833",
    "plasmodium falciparum": "36329",
    "p. falciparum": "36329",
    "plasmodium vivax": "5855",
    "p. vivax": "5855",
    "tuberculosis": "1773",
    "tb": "1773",
    "mycobacterium tuberculosis": "1773",
    "m. tuberculosis": "1773",
    "yeast": "4932",  # Saccharomyces cerevisiae
    "saccharomyces": "4930",  # Saccharomyces genus
    "saccharomyces cerevisiae": "4932",
    "candida": "5475",  # Candida genus
    "candida albicans": "5476",
    "candida auris": "498019",
    "c. auris": "498019",
    "aspergillus": "5052",  # Aspergillus genus
    "aspergillus fumigatus": "746128",
    "cryptococcus": "5206",  # Cryptococcus genus
    "cryptococcus neoformans": "5207",
    "e. coli": "562",
    "escherichia coli": "562",
    "staph": "1279",  # Staphylococcus genus
    "staphylococcus aureus": "1280",
    "mrsa": "1280",
    "toxoplasma": "5810",  # Toxoplasma genus
    "toxoplasma gondii": "5811",
    "leishmania": "5658",  # Leishmania genus
    "trypanosoma": "5690",  # Trypanosoma genus
    "giardia": "5740",  # Giardia genus
    "cryptosporidium": "5806",  # Cryptosporidium genus
}


# ============================================================
# Dependencies
# ============================================================


@dataclass
class ENADeps:
    """Dependencies injected into the ENA search agent."""

    ena_service: ENAService
    schema_info: dict = field(default_factory=lambda: ENA_SCHEMA)
    organism_vocab: dict = field(default_factory=lambda: ORGANISM_VOCABULARY)

    def _matches_filter(self, item: dict, f: ENAFilter) -> bool:
        """Check if an item matches a single filter condition."""
        value = item.get(f.field)

        if value is None:
            return f.operator == "eq" and f.value is None

        # Handle list values
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
            # Case-insensitive for strings
            if isinstance(value, str) and isinstance(f.value, str):
                return value.lower() == f.value.lower()
            return value == f.value
        elif f.operator == "ne":
            return value != f.value
        elif f.operator == "contains":
            return str(f.value).lower() in str(value).lower()
        elif f.operator == "in":
            if isinstance(f.value, list):
                if isinstance(value, str):
                    return value.upper() in [v.upper() for v in f.value]
                return value in f.value
            return False
        elif f.operator == "gt":
            return value > f.value
        elif f.operator == "gte":
            return value >= f.value
        elif f.operator == "lt":
            return value < f.value
        elif f.operator == "lte":
            return value <= f.value

        return False

    def apply_filters(
        self, results: list[dict], filters: list[ENAFilter]
    ) -> list[dict]:
        """Apply post-query filters to results."""
        if not filters:
            return results

        filtered = results
        for f in filters:
            filtered = [r for r in filtered if self._matches_filter(r, f)]

        return filtered


# ============================================================
# System Prompt
# ============================================================

ENA_SEARCH_PROMPT = """You help users find sequencing data in the ENA/SRA database.

<overview>
ENA (European Nucleotide Archive) contains sequencing read data from experiments worldwide.
You can search by organism (taxonomy ID), accession numbers, or keywords.
</overview>

<vocabulary>
Users may use informal terms. Map them appropriately:

Organisms (map to taxonomy ID search):
- "malaria" → tax_id 5833 (Plasmodium genus)
- "P. falciparum" or "Plasmodium falciparum" → tax_id 36329
- "TB" or "tuberculosis" → tax_id 1773 (Mycobacterium tuberculosis)
- "yeast" → tax_id 4932 (Saccharomyces cerevisiae)
- "Candida auris" or "C. auris" → tax_id 498019
- Use search_organism() to find taxonomy IDs for other organisms

Sequencing strategies:
- "whole genome sequencing", "WGS" → library_strategy = "WGS"
- "RNA-seq", "transcriptome" → library_strategy = "RNA-Seq"
- "exome", "WXS", "whole exome" → library_strategy = "WXS"
- "ChIP-seq", "chromatin" → library_strategy = "ChIP-Seq"
- "ATAC-seq", "chromatin accessibility" → library_strategy = "ATAC-seq"

Library layout:
- "paired-end", "paired end", "PE" → library_layout = "PAIRED"
- "single-end", "single end", "SE" → library_layout = "SINGLE"

Platforms:
- "Illumina", "HiSeq", "MiSeq", "NovaSeq", "NextSeq" → instrument_platform = "ILLUMINA"
- "PacBio", "SMRT" → instrument_platform = "PACBIO_SMRT"
- "Nanopore", "ONT", "Oxford Nanopore", "MinION", "PromethION" → instrument_platform = "OXFORD_NANOPORE"
- "Ion Torrent" → instrument_platform = "ION_TORRENT"
</vocabulary>

<process>
1. Identify the search strategy:
   - If organism mentioned: use taxonomy search (search_method="taxonomy")
   - If specific accession given: use accession lookup (search_method="accession")
   - Otherwise: use keyword search (search_method="keywords")

2. For organism searches:
   - Check vocabulary first for common organisms
   - Use search_organism() tool if not in vocabulary
   - Use the taxonomy ID for the search

3. Build filters for additional criteria:
   - library_layout for paired/single-end
   - library_strategy for WGS/RNA-Seq/etc.
   - instrument_platform for sequencing technology

4. Use preview_search() to test and see result counts

5. Return ENASearch with appropriate parameters
</process>

<tips>
- Taxonomy search is most reliable for organism queries
- Post-query filters narrow results after ENA returns data
- PAIRED/SINGLE are exact values for library_layout
- Library strategy values are case-sensitive (e.g., "RNA-Seq" not "rna-seq")
- Use preview_search to verify result counts before finalizing
</tips>
"""


# ============================================================
# ENA Search Service
# ============================================================


class ENASearchService:
    """Service for searching ENA using an AI agent with tools."""

    def __init__(self, ena_service: ENAService):
        self.settings = get_settings()
        self.ena_service = ena_service
        self.deps: ENADeps | None = None
        self.agent: Agent | None = None

        self._initialize()

    def _initialize(self):
        """Initialize the agent and dependencies."""
        if not self.settings.AI_API_KEY:
            logger.warning("AI API key not configured - ENA search will be disabled")
            return

        self.deps = ENADeps(ena_service=self.ena_service)

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

            self.agent = Agent(
                model,
                deps_type=ENADeps,
                output_type=ENASearch,
                instructions=ENA_SEARCH_PROMPT,
            )

            self._register_tools()

            logger.info("ENA search service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize ENA search agent: {e}")
            self.agent = None

    def _register_tools(self):
        """Register tools on the agent."""
        if not self.agent:
            return

        @self.agent.tool
        async def get_schema(
            ctx: RunContext[ENADeps], fields: list[str] | None = None
        ) -> dict:
            """Get schema information for ENA fields.

            Args:
                fields: Specific fields to get info for, or None for overview.

            Returns:
                Schema details including types, valid values, and operators.
            """
            schema = ctx.deps.schema_info
            if fields:
                return {k: v for k, v in schema.items() if k in fields}
            return {
                "fields": {k: v.get("description", "") for k, v in schema.items()},
                "total_fields": len(schema),
                "hint": "Call with specific field names for valid values",
            }

        @self.agent.tool
        async def search_organism(ctx: RunContext[ENADeps], name: str) -> dict:
            """Search for an organism's taxonomy ID.

            Args:
                name: Organism name to search for (common name or scientific name).

            Returns:
                Taxonomy ID if found, or suggestions.
            """
            name_lower = name.lower().strip()

            # Check vocabulary first
            if name_lower in ctx.deps.organism_vocab:
                tax_id = ctx.deps.organism_vocab[name_lower]
                return {
                    "found": True,
                    "name": name,
                    "taxonomy_id": tax_id,
                    "source": "vocabulary",
                }

            # Check partial matches
            for key, tax_id in ctx.deps.organism_vocab.items():
                if name_lower in key or key in name_lower:
                    return {
                        "found": True,
                        "name": key,
                        "taxonomy_id": tax_id,
                        "source": "partial_match",
                    }

            return {
                "found": False,
                "message": f"Organism '{name}' not found in vocabulary. "
                "Try using the scientific name or check spelling.",
                "suggestions": [k for k in ctx.deps.organism_vocab.keys()][:10],
            }

        @self.agent.tool
        async def get_field_values(ctx: RunContext[ENADeps], field: str) -> dict:
            """Get valid values for an enum field.

            Args:
                field: The field name to get values for.

            Returns:
                List of valid values for the field.
            """
            schema = ctx.deps.schema_info
            if field not in schema:
                return {
                    "error": f"Unknown field: {field}",
                    "valid_fields": list(schema.keys()),
                }

            field_info = schema[field]
            if "values" in field_info:
                return {
                    "field": field,
                    "type": field_info.get("type"),
                    "values": field_info["values"],
                    "description": field_info.get("description"),
                }
            else:
                return {
                    "field": field,
                    "type": field_info.get("type"),
                    "description": field_info.get("description"),
                    "note": "This field does not have predefined values",
                }

        @self.agent.tool
        async def preview_search(
            ctx: RunContext[ENADeps],
            search_method: str,
            taxonomy_id: str | None = None,
            keywords: list[str] | None = None,
            filters: list[dict] | None = None,
        ) -> dict:
            """Preview search results before finalizing.

            Args:
                search_method: "taxonomy", "accession", or "keywords"
                taxonomy_id: Taxonomy ID for organism search
                keywords: Keywords for text search
                filters: Post-query filters to apply

            Returns:
                Result count, assessment, and sample results.
            """
            try:
                # Execute the ENA search
                if search_method == "taxonomy" and taxonomy_id:
                    result = await ctx.deps.ena_service.search_by_taxonomy(
                        taxonomy_id, limit=100
                    )
                elif search_method == "keywords" and keywords:
                    result = await ctx.deps.ena_service.search_by_keywords(
                        keywords, limit=100
                    )
                else:
                    return {"error": "Invalid search parameters"}

                data = result.get("data", [])
                total_before_filter = len(data)

                # Apply post-query filters
                if filters:
                    parsed_filters = [ENAFilter(**f) for f in filters]
                    data = ctx.deps.apply_filters(data, parsed_filters)

                total = len(data)

                # Assess the results
                if total == 0:
                    assessment = "no_results"
                elif total > 200:
                    assessment = "many_results"
                elif total > 50:
                    assessment = "good"
                elif total < 5:
                    assessment = "few_results"
                else:
                    assessment = "good"

                # Return sample
                sample = []
                for r in data[:3]:
                    sample.append(
                        {
                            "run_accession": r.get("run_accession"),
                            "scientific_name": r.get("scientific_name"),
                            "library_strategy": r.get("library_strategy"),
                            "library_layout": r.get("library_layout"),
                            "instrument_platform": r.get("instrument_platform"),
                        }
                    )

                return {
                    "total_before_filter": total_before_filter,
                    "total_after_filter": total,
                    "assessment": assessment,
                    "sample_results": sample,
                    "cached": result.get("cached", False),
                }

            except Exception as e:
                return {"error": str(e)}

    def is_available(self) -> bool:
        """Check if the service is available."""
        return self.agent is not None and self.deps is not None

    async def search(self, query: str) -> ENASearchResult:
        """Search ENA using natural language.

        Args:
            query: Natural language search query.

        Returns:
            ENASearchResult with matching runs.
        """
        if not self.is_available():
            return ENASearchResult(
                success=False,
                total_count=0,
                results=[],
                filters_applied=[],
                message="ENA search service not available",
            )

        try:
            logger.info(f"ENA search query: {query}")

            # Run the agent to get search parameters
            result = await self.agent.run(query, deps=self.deps)
            search_params = result.output

            logger.info(
                f"Agent returned: method={search_params.search_method}, "
                f"tax_id={search_params.taxonomy_id}, "
                f"keywords={search_params.keywords}, "
                f"filters={len(search_params.filters)}"
            )

            # Execute the search
            return await self._execute_search(search_params)

        except Exception as e:
            logger.error(f"ENA search failed: {e}")
            return ENASearchResult(
                success=False,
                total_count=0,
                results=[],
                filters_applied=[],
                message=f"Search failed: {str(e)}",
            )

    async def _execute_search(self, search_params: ENASearch) -> ENASearchResult:
        """Execute the actual ENA search based on parameters."""
        try:
            # Execute the appropriate search
            if search_params.search_method == "taxonomy" and search_params.taxonomy_id:
                result = await self.ena_service.search_by_taxonomy(
                    search_params.taxonomy_id, limit=search_params.limit
                )
            elif search_params.search_method == "accession" and search_params.accession:
                result = await self.ena_service.get_by_accession(
                    search_params.accession
                )
            elif search_params.search_method == "keywords" and search_params.keywords:
                result = await self.ena_service.search_by_keywords(
                    search_params.keywords, limit=search_params.limit
                )
            else:
                return ENASearchResult(
                    success=False,
                    total_count=0,
                    results=[],
                    filters_applied=[],
                    message="Invalid search parameters",
                )

            data = result.get("data", [])
            cached = result.get("cached", False)

            # Apply post-query filters
            if search_params.filters:
                data = self.deps.apply_filters(data, search_params.filters)

            # Apply limit
            data = data[: search_params.limit]

            return ENASearchResult(
                success=True,
                total_count=len(data),
                results=data,
                filters_applied=search_params.filters,
                search_params=search_params,
                message=f"Found {len(data)} sequencing runs",
                cached=cached,
            )

        except Exception as e:
            logger.error(f"ENA search execution failed: {e}")
            return ENASearchResult(
                success=False,
                total_count=0,
                results=[],
                filters_applied=[],
                message=f"Search execution failed: {str(e)}",
            )

    async def conversational_search(
        self,
        query: str,
        message_history: list | None = None,
        current_filters: list | None = None,
    ) -> tuple[ENASearchResult, list]:
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
                ENASearchResult(
                    success=False,
                    total_count=0,
                    results=[],
                    filters_applied=[],
                    message="ENA search service not available",
                ),
                [],
            )

        try:
            # Build context prompt with current state
            context_parts = []

            if current_filters:
                filter_desc = ", ".join(
                    f"{f['field']} {f['operator']} {f['value']}"
                    for f in current_filters
                )
                context_parts.append(f"Current filters: {filter_desc}")

            if context_parts:
                context = "\n".join(context_parts)
                augmented_query = f"{context}\n\nUser request: {query}"
            else:
                augmented_query = query

            logger.info(f"Conversational ENA search: {query}")
            logger.info(
                f"Message history length: {len(message_history) if message_history else 0}"
            )

            # Run the agent with message history
            result = await self.agent.run(
                augmented_query,
                deps=self.deps,
                message_history=message_history,
            )
            search_params = result.output

            logger.info(f"Agent returned: method={search_params.search_method}")

            # Execute the search
            search_result = await self._execute_search(search_params)

            # Get updated message history
            new_history = result.all_messages()

            return (search_result, new_history)

        except Exception as e:
            logger.error(f"Conversational ENA search failed: {e}")
            return (
                ENASearchResult(
                    success=False,
                    total_count=0,
                    results=[],
                    filters_applied=[],
                    message=f"Search failed: {str(e)}",
                ),
                message_history or [],
            )

    def direct_search(self, search_params: ENASearch) -> ENASearchResult:
        """
        Execute a search directly without using the agent.

        This is a synchronous wrapper - callers should use async version.
        """
        import asyncio

        return asyncio.get_event_loop().run_until_complete(
            self._execute_search(search_params)
        )

    async def direct_search_async(self, search_params: ENASearch) -> ENASearchResult:
        """Execute a search directly without using the agent."""
        return await self._execute_search(search_params)

    def get_schema(self) -> dict:
        """Get the ENA schema."""
        return ENA_SCHEMA

    def get_field_values(self, field: str) -> list[str] | None:
        """Get valid values for an enum field."""
        field_info = ENA_SCHEMA.get(field)
        if field_info and "values" in field_info:
            return field_info["values"]
        return None
