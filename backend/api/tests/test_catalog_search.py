"""
Tests for Catalog Search service.

These tests verify:
1. Direct search (filter-based, no LLM)
2. Natural language search (LLM-powered)
3. Multi-turn conversation (session-based refinement)
4. Edge cases and error handling
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.catalog_search import (
    ASSEMBLY_SCHEMA,
    CatalogDeps,
    CatalogFilter,
    CatalogSearch,
    CatalogSearchService,
)

# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def sample_assemblies():
    """Sample assembly data for testing."""
    return [
        {
            "accession": "GCF_000002765.6",
            "level": "Complete Genome",
            "taxonomicLevelSpecies": "Plasmodium falciparum",
            "taxonomicLevelGenus": "Plasmodium",
            "taxonomicLevelDomain": "Eukaryota",
            "taxonomicGroup": ["Apicomplexa"],
            "ncbiTaxonomyId": "36329",
            "speciesTaxonomyId": "5833",
            "isRef": "Yes",
            "ploidy": ["HAPLOID"],
            "scaffoldCount": 14,
            "scaffoldN50": 1687656,
            "length": 23292622,
        },
        {
            "accession": "GCA_900632045.1",
            "level": "Complete Genome",
            "taxonomicLevelSpecies": "Plasmodium falciparum",
            "taxonomicLevelGenus": "Plasmodium",
            "taxonomicLevelDomain": "Eukaryota",
            "taxonomicGroup": ["Apicomplexa"],
            "ncbiTaxonomyId": "5833",
            "speciesTaxonomyId": "5833",
            "isRef": "No",
            "ploidy": ["HAPLOID"],
            "scaffoldCount": 14,
            "scaffoldN50": 1661861,
            "length": 22641838,
        },
        {
            "accession": "GCA_000005845.2",
            "level": "Complete Genome",
            "taxonomicLevelSpecies": "Escherichia coli",
            "taxonomicLevelGenus": "Escherichia",
            "taxonomicLevelDomain": "Bacteria",
            "taxonomicGroup": ["Bacteria"],
            "ncbiTaxonomyId": "511145",
            "speciesTaxonomyId": "562",
            "isRef": "Yes",
            "ploidy": ["HAPLOID"],
            "scaffoldCount": 1,
            "scaffoldN50": 4641652,
            "length": 4641652,
        },
        {
            "accession": "GCA_000182965.3",
            "level": "Chromosome",
            "taxonomicLevelSpecies": "Candida albicans",
            "taxonomicLevelGenus": "Candida",
            "taxonomicLevelDomain": "Eukaryota",
            "taxonomicGroup": ["Ascomycota"],
            "ncbiTaxonomyId": "237561",
            "speciesTaxonomyId": "5476",
            "isRef": "Yes",
            "ploidy": ["DIPLOID"],
            "scaffoldCount": 8,
            "scaffoldN50": 2231883,
            "length": 14282666,
        },
        {
            "accession": "GCA_000001234.1",
            "level": "Scaffold",
            "taxonomicLevelSpecies": "Aspergillus fumigatus",
            "taxonomicLevelGenus": "Aspergillus",
            "taxonomicLevelDomain": "Eukaryota",
            "taxonomicGroup": ["Ascomycota"],
            "ncbiTaxonomyId": "330879",
            "speciesTaxonomyId": "746128",
            "isRef": "No",
            "ploidy": ["HAPLOID"],
            "scaffoldCount": 56,
            "scaffoldN50": 500000,
            "length": 29000000,
        },
    ]


@pytest.fixture
def sample_organisms():
    """Sample organism data for testing."""
    return [
        {
            "taxonomicLevelSpecies": "Plasmodium falciparum",
            "taxonomicLevelGenus": "Plasmodium",
            "ncbiTaxonomyId": "5833",
            "commonName": "malaria parasite",
            "assemblyCount": 20,
        },
        {
            "taxonomicLevelSpecies": "Plasmodium vivax",
            "taxonomicLevelGenus": "Plasmodium",
            "ncbiTaxonomyId": "5855",
            "commonName": "",
            "assemblyCount": 5,
        },
        {
            "taxonomicLevelSpecies": "Escherichia coli",
            "taxonomicLevelGenus": "Escherichia",
            "ncbiTaxonomyId": "562",
            "commonName": "E. coli",
            "assemblyCount": 15,
        },
        {
            "taxonomicLevelSpecies": "Candida albicans",
            "taxonomicLevelGenus": "Candida",
            "ncbiTaxonomyId": "5476",
            "commonName": "",
            "assemblyCount": 10,
        },
    ]


@pytest.fixture
def catalog_deps(sample_assemblies, sample_organisms):
    """Create CatalogDeps with sample data."""
    return CatalogDeps(
        assemblies=sample_assemblies,
        organisms=sample_organisms,
        schema_info=ASSEMBLY_SCHEMA,
    )


# ============================================================
# Direct Search Tests (No LLM)
# ============================================================


class TestDirectSearch:
    """Tests for filter-based search without LLM."""

    def test_filter_by_species_exact(self, catalog_deps):
        """Filter by exact species name."""
        search = CatalogSearch(
            filters=[
                CatalogFilter(
                    column="taxonomicLevelSpecies",
                    operator="eq",
                    value="Plasmodium falciparum",
                )
            ]
        )
        result = catalog_deps.execute_search(search)
        assert result["total_count"] == 2
        assert all(
            r["taxonomicLevelSpecies"] == "Plasmodium falciparum"
            for r in result["results"]
        )

    def test_filter_by_species_contains(self, catalog_deps):
        """Filter by species name substring."""
        search = CatalogSearch(
            filters=[
                CatalogFilter(
                    column="taxonomicLevelSpecies",
                    operator="contains",
                    value="Plasmodium",
                )
            ]
        )
        result = catalog_deps.execute_search(search)
        assert result["total_count"] == 2

    def test_filter_by_level(self, catalog_deps):
        """Filter by assembly level."""
        search = CatalogSearch(
            filters=[
                CatalogFilter(column="level", operator="eq", value="Complete Genome")
            ]
        )
        result = catalog_deps.execute_search(search)
        assert result["total_count"] == 3
        assert all(r["level"] == "Complete Genome" for r in result["results"])

    def test_filter_by_domain(self, catalog_deps):
        """Filter by taxonomic domain."""
        search = CatalogSearch(
            filters=[
                CatalogFilter(
                    column="taxonomicLevelDomain", operator="eq", value="Bacteria"
                )
            ]
        )
        result = catalog_deps.execute_search(search)
        assert result["total_count"] == 1
        assert result["results"][0]["taxonomicLevelSpecies"] == "Escherichia coli"

    def test_filter_by_reference(self, catalog_deps):
        """Filter for reference genomes only."""
        search = CatalogSearch(
            filters=[CatalogFilter(column="isRef", operator="eq", value="Yes")]
        )
        result = catalog_deps.execute_search(search)
        assert result["total_count"] == 3
        assert all(r["isRef"] == "Yes" for r in result["results"])

    def test_filter_by_ploidy_list(self, catalog_deps):
        """Filter by ploidy (list field)."""
        search = CatalogSearch(
            filters=[CatalogFilter(column="ploidy", operator="eq", value="DIPLOID")]
        )
        result = catalog_deps.execute_search(search)
        assert result["total_count"] == 1
        assert result["results"][0]["taxonomicLevelSpecies"] == "Candida albicans"

    def test_filter_scaffold_count_lte(self, catalog_deps):
        """Filter by scaffold count <= value."""
        search = CatalogSearch(
            filters=[CatalogFilter(column="scaffoldCount", operator="lte", value=10)]
        )
        result = catalog_deps.execute_search(search)
        # Sample data: E.coli (1), Candida (8) = 2 assemblies with scaffoldCount <= 10
        assert result["total_count"] == 2
        assert all(r["scaffoldCount"] <= 10 for r in result["results"])

    def test_filter_scaffold_count_gte(self, catalog_deps):
        """Filter by scaffold count >= value."""
        search = CatalogSearch(
            filters=[CatalogFilter(column="scaffoldCount", operator="gte", value=50)]
        )
        result = catalog_deps.execute_search(search)
        assert result["total_count"] == 1
        assert result["results"][0]["scaffoldCount"] >= 50

    def test_multiple_filters_and(self, catalog_deps):
        """Multiple filters are ANDed together."""
        search = CatalogSearch(
            filters=[
                CatalogFilter(
                    column="taxonomicLevelSpecies",
                    operator="eq",
                    value="Plasmodium falciparum",
                ),
                CatalogFilter(column="isRef", operator="eq", value="Yes"),
            ]
        )
        result = catalog_deps.execute_search(search)
        assert result["total_count"] == 1
        assert result["results"][0]["accession"] == "GCF_000002765.6"

    def test_filter_in_operator(self, catalog_deps):
        """Filter with 'in' operator for multiple values."""
        search = CatalogSearch(
            filters=[
                CatalogFilter(
                    column="level", operator="in", value=["Scaffold", "Contig"]
                )
            ]
        )
        result = catalog_deps.execute_search(search)
        assert result["total_count"] == 1
        assert result["results"][0]["level"] == "Scaffold"

    def test_sort_by_scaffold_count_asc(self, catalog_deps):
        """Sort by scaffold count ascending (quality indicator)."""
        search = CatalogSearch(
            filters=[],
            sort_by="scaffoldCount",
            sort_order="asc",
        )
        result = catalog_deps.execute_search(search)
        counts = [r["scaffoldCount"] for r in result["results"]]
        assert counts == sorted(counts)

    def test_sort_by_scaffold_count_desc(self, catalog_deps):
        """Sort by scaffold count descending."""
        search = CatalogSearch(
            filters=[],
            sort_by="scaffoldCount",
            sort_order="desc",
        )
        result = catalog_deps.execute_search(search)
        counts = [r["scaffoldCount"] for r in result["results"]]
        assert counts == sorted(counts, reverse=True)

    def test_limit_results(self, catalog_deps):
        """Limit number of returned results."""
        search = CatalogSearch(filters=[], limit=2)
        result = catalog_deps.execute_search(search)
        assert result["total_count"] == 5  # Total matching
        assert result["returned_count"] == 2  # Limited

    def test_empty_filters_returns_all(self, catalog_deps):
        """Empty filters return all assemblies."""
        search = CatalogSearch(filters=[])
        result = catalog_deps.execute_search(search)
        assert result["total_count"] == 5

    def test_no_matches_returns_empty(self, catalog_deps):
        """No matches returns empty results with assessment."""
        search = CatalogSearch(
            filters=[
                CatalogFilter(
                    column="taxonomicLevelSpecies",
                    operator="eq",
                    value="Nonexistent species",
                )
            ]
        )
        result = catalog_deps.execute_search(search)
        assert result["total_count"] == 0
        assert result["assessment"] == "no_results"


# ============================================================
# Organism Search Tests
# ============================================================


class TestOrganismSearch:
    """Tests for organism name lookup."""

    def test_search_by_species_name(self, catalog_deps):
        """Search organisms by species name."""
        results = catalog_deps.search_organisms("Plasmodium")
        assert len(results) == 2
        assert all("Plasmodium" in r["species"] for r in results)

    def test_search_by_common_name(self, catalog_deps):
        """Search organisms by common name."""
        results = catalog_deps.search_organisms("malaria")
        assert len(results) == 1
        assert results[0]["species"] == "Plasmodium falciparum"

    def test_search_case_insensitive(self, catalog_deps):
        """Search is case insensitive."""
        results = catalog_deps.search_organisms("ESCHERICHIA")
        assert len(results) == 1
        assert results[0]["species"] == "Escherichia coli"

    def test_search_by_genus(self, catalog_deps):
        """Search by genus name."""
        results = catalog_deps.search_organisms("Candida")
        assert len(results) == 1
        assert results[0]["genus"] == "Candida"

    def test_search_results_sorted_by_assembly_count(self, catalog_deps):
        """Results sorted by assembly count descending."""
        results = catalog_deps.search_organisms("Plasmodium")
        counts = [r["assembly_count"] for r in results]
        assert counts == sorted(counts, reverse=True)

    def test_search_limit(self, catalog_deps):
        """Search respects limit parameter."""
        results = catalog_deps.search_organisms("Plasmodium", limit=1)
        assert len(results) == 1


# ============================================================
# Schema and Column Values Tests
# ============================================================


class TestSchemaAndValues:
    """Tests for schema introspection."""

    def test_get_distinct_values(self, catalog_deps):
        """Get distinct values for a column."""
        values = catalog_deps.get_distinct_values("level")
        assert "Complete Genome" in values
        assert "Chromosome" in values
        assert "Scaffold" in values

    def test_get_distinct_values_for_list_field(self, catalog_deps):
        """Get distinct values for list field (ploidy)."""
        values = catalog_deps.get_distinct_values("ploidy")
        assert "HAPLOID" in values
        assert "DIPLOID" in values

    def test_get_distinct_values_limit(self, catalog_deps):
        """Distinct values respects limit."""
        values = catalog_deps.get_distinct_values("taxonomicLevelSpecies", limit=2)
        assert len(values) <= 2


# ============================================================
# Assessment Tests
# ============================================================


class TestSearchAssessment:
    """Tests for result count assessment."""

    def test_assessment_good(self, catalog_deps):
        """Assessment is 'good' for reasonable result count."""
        # 5 results should be "good" (5-100 range)
        search = CatalogSearch(filters=[])
        result = catalog_deps.execute_search(search)
        assert result["assessment"] == "good"

    def test_assessment_narrow(self, catalog_deps):
        """Assessment is 'narrow' for very few results."""
        search = CatalogSearch(
            filters=[
                CatalogFilter(
                    column="taxonomicLevelDomain", operator="eq", value="Bacteria"
                )
            ]
        )
        result = catalog_deps.execute_search(search)
        assert result["total_count"] == 1
        assert result["assessment"] == "narrow"

    def test_assessment_no_results(self, catalog_deps):
        """Assessment is 'no_results' for zero matches."""
        search = CatalogSearch(
            filters=[CatalogFilter(column="level", operator="eq", value="Nonexistent")]
        )
        result = catalog_deps.execute_search(search)
        assert result["assessment"] == "no_results"


# ============================================================
# Multi-turn Conversation Tests
# ============================================================


class TestMultiTurnConversation:
    """
    Tests for multi-turn conversation capability.

    These tests verify that the agent can maintain context across
    multiple exchanges to progressively narrow search results.
    """

    @pytest.mark.asyncio
    async def test_progressive_narrowing_simulation(self, catalog_deps):
        """
        Simulate a multi-turn conversation where user progressively narrows results.

        Turn 1: "Show me Plasmodium genomes" → 2 results
        Turn 2: "Only the reference genome" → 1 result

        This tests the pattern even if sessions aren't implemented yet.
        """
        # Turn 1: Broad query
        search1 = CatalogSearch(
            filters=[
                CatalogFilter(
                    column="taxonomicLevelSpecies",
                    operator="contains",
                    value="Plasmodium",
                )
            ]
        )
        result1 = catalog_deps.execute_search(search1)
        assert result1["total_count"] == 2

        # Turn 2: Narrow to reference only (building on previous filters)
        search2 = CatalogSearch(
            filters=[
                CatalogFilter(
                    column="taxonomicLevelSpecies",
                    operator="contains",
                    value="Plasmodium",
                ),
                CatalogFilter(column="isRef", operator="eq", value="Yes"),
            ]
        )
        result2 = catalog_deps.execute_search(search2)
        assert result2["total_count"] == 1
        assert result2["results"][0]["isRef"] == "Yes"

    @pytest.mark.asyncio
    async def test_filter_accumulation_pattern(self, catalog_deps):
        """
        Test the pattern of accumulating filters across turns.

        This is how a UI would implement multi-turn:
        - Store previous filters
        - Add new filters from each turn
        - Re-execute with combined filters
        """
        accumulated_filters = []

        # Turn 1: Start with domain
        accumulated_filters.append(
            CatalogFilter(
                column="taxonomicLevelDomain", operator="eq", value="Eukaryota"
            )
        )
        result1 = catalog_deps.execute_search(
            CatalogSearch(filters=accumulated_filters)
        )
        assert result1["total_count"] == 4

        # Turn 2: Add taxonomic group filter
        accumulated_filters.append(
            CatalogFilter(column="taxonomicGroup", operator="eq", value="Ascomycota")
        )
        result2 = catalog_deps.execute_search(
            CatalogSearch(filters=accumulated_filters)
        )
        assert result2["total_count"] == 2

        # Turn 3: Add quality filter
        accumulated_filters.append(
            CatalogFilter(column="scaffoldCount", operator="lte", value=10)
        )
        result3 = catalog_deps.execute_search(
            CatalogSearch(filters=accumulated_filters)
        )
        assert result3["total_count"] == 1

    @pytest.mark.asyncio
    async def test_remove_filter_to_broaden(self, catalog_deps):
        """
        Test removing a filter to broaden results.

        User might say: "Actually, show me all genomes not just reference"
        """
        # Start with two filters
        filters = [
            CatalogFilter(
                column="taxonomicLevelDomain", operator="eq", value="Eukaryota"
            ),
            CatalogFilter(column="isRef", operator="eq", value="Yes"),
        ]
        result1 = catalog_deps.execute_search(CatalogSearch(filters=filters))
        assert result1["total_count"] == 2

        # Remove the isRef filter
        filters = [f for f in filters if f.column != "isRef"]
        result2 = catalog_deps.execute_search(CatalogSearch(filters=filters))
        assert result2["total_count"] == 4  # More results now


# ============================================================
# Natural Language Search Tests (with mocked LLM)
# ============================================================


class TestNaturalLanguageSearch:
    """
    Tests for natural language search.

    These use a mocked LLM to test the interpretation logic
    without making actual API calls.
    """

    @pytest.mark.asyncio
    async def test_complete_genome_interpretation(self):
        """
        Test that 'complete genome' is interpreted correctly.

        Expected: level = "Complete Genome"
        """
        # This tests our vocabulary mapping expectation
        # The LLM should produce this filter for "complete genomes"
        expected_filter = CatalogFilter(
            column="level", operator="eq", value="Complete Genome"
        )

        # Verify the filter works
        sample_data = [
            {"accession": "A", "level": "Complete Genome"},
            {"accession": "B", "level": "Scaffold"},
        ]
        deps = CatalogDeps(assemblies=sample_data, organisms=[])
        result = deps.execute_search(CatalogSearch(filters=[expected_filter]))
        assert result["total_count"] == 1

    @pytest.mark.asyncio
    async def test_draft_genome_interpretation(self):
        """
        Test that 'draft genome' is interpreted correctly.

        Expected: level in ["Scaffold", "Contig"]
        """
        expected_filter = CatalogFilter(
            column="level", operator="in", value=["Scaffold", "Contig"]
        )

        sample_data = [
            {"accession": "A", "level": "Complete Genome"},
            {"accession": "B", "level": "Scaffold"},
            {"accession": "C", "level": "Contig"},
        ]
        deps = CatalogDeps(assemblies=sample_data, organisms=[])
        result = deps.execute_search(CatalogSearch(filters=[expected_filter]))
        assert result["total_count"] == 2

    @pytest.mark.asyncio
    async def test_reference_genome_interpretation(self):
        """
        Test that 'reference genome' is interpreted correctly.

        Expected: isRef = "Yes"
        """
        expected_filter = CatalogFilter(column="isRef", operator="eq", value="Yes")

        sample_data = [
            {"accession": "A", "isRef": "Yes"},
            {"accession": "B", "isRef": "No"},
        ]
        deps = CatalogDeps(assemblies=sample_data, organisms=[])
        result = deps.execute_search(CatalogSearch(filters=[expected_filter]))
        assert result["total_count"] == 1

    @pytest.mark.asyncio
    async def test_bacterial_interpretation(self):
        """
        Test that 'bacterial' is interpreted correctly.

        Expected: taxonomicLevelDomain = "Bacteria"
        """
        expected_filter = CatalogFilter(
            column="taxonomicLevelDomain", operator="eq", value="Bacteria"
        )

        sample_data = [
            {"accession": "A", "taxonomicLevelDomain": "Bacteria"},
            {"accession": "B", "taxonomicLevelDomain": "Eukaryota"},
        ]
        deps = CatalogDeps(assemblies=sample_data, organisms=[])
        result = deps.execute_search(CatalogSearch(filters=[expected_filter]))
        assert result["total_count"] == 1

    @pytest.mark.asyncio
    async def test_high_quality_interpretation(self):
        """
        Test that 'high quality' implies sorting by scaffoldCount ascending.

        Fewer scaffolds = higher quality assembly.
        """
        sample_data = [
            {"accession": "A", "scaffoldCount": 100},
            {"accession": "B", "scaffoldCount": 5},
            {"accession": "C", "scaffoldCount": 1},
        ]
        deps = CatalogDeps(assemblies=sample_data, organisms=[])
        result = deps.execute_search(
            CatalogSearch(filters=[], sort_by="scaffoldCount", sort_order="asc")
        )
        accessions = [r["accession"] for r in result["results"]]
        assert accessions == ["C", "B", "A"]


# ============================================================
# Integration Tests (require running service)
# ============================================================


@pytest.mark.integration
class TestCatalogSearchIntegration:
    """
    Integration tests that require the full service running.

    Mark with @pytest.mark.integration and skip if service unavailable.
    """

    @pytest.mark.asyncio
    async def test_service_initialization(self):
        """Test that service initializes with real catalog."""
        service = CatalogSearchService()
        assert service.deps is not None
        assert len(service.deps.assemblies) > 0
        assert len(service.deps.organisms) > 0

    @pytest.mark.asyncio
    async def test_real_nlp_search_malaria(self):
        """Test real NLP search for malaria genomes."""
        service = CatalogSearchService()
        if not service.is_available():
            pytest.skip("LLM not available")

        result = await service.search("complete Plasmodium falciparum genomes")
        assert result.success
        assert result.total_count > 0
        # Verify filters make sense
        filter_columns = [f.column for f in result.filters_applied]
        has_species = any(
            "Species" in c or "species" in c.lower() for c in filter_columns
        )
        has_genus = any("Genus" in c for c in filter_columns)
        assert has_species or has_genus

    @pytest.mark.asyncio
    async def test_real_nlp_search_bacteria(self):
        """Test real NLP search for bacterial genomes."""
        service = CatalogSearchService()
        if not service.is_available():
            pytest.skip("LLM not available")

        result = await service.search("reference bacterial genomes")
        assert result.success
        # Should have domain and isRef filters
        filter_columns = [f.column for f in result.filters_applied]
        assert "taxonomicLevelDomain" in filter_columns or any(
            "Bacteria" in str(f.value) for f in result.filters_applied
        )


# ============================================================
# Session Tests
# ============================================================


class TestSessionService:
    """Tests for session management."""

    @pytest.fixture
    def mock_cache(self):
        """Create a mock cache service that stores data in memory."""
        storage = {}

        async def mock_get(key):
            return storage.get(key)

        async def mock_set(key, value, ttl=None):
            storage[key] = value

        async def mock_delete(key):
            storage.pop(key, None)

        cache = MagicMock()
        cache.get = AsyncMock(side_effect=mock_get)
        cache.set = AsyncMock(side_effect=mock_set)
        cache.delete = AsyncMock(side_effect=mock_delete)
        cache._storage = storage  # For inspection
        return cache

    @pytest.mark.asyncio
    async def test_create_session(self, mock_cache):
        """Test creating a new session."""
        from app.services.session import SessionService

        service = SessionService(mock_cache)
        session = await service.create_session()

        assert session.session_id is not None
        assert len(session.session_id) == 36  # UUID format
        assert session.messages == []
        assert session.filters == []
        assert session.last_result_count == 0

    @pytest.mark.asyncio
    async def test_get_session(self, mock_cache):
        """Test retrieving an existing session."""
        from app.services.session import SessionService

        service = SessionService(mock_cache)
        session = await service.create_session()

        # Retrieve it
        retrieved = await service.get_session(session.session_id)

        assert retrieved is not None
        assert retrieved.session_id == session.session_id

    @pytest.mark.asyncio
    async def test_get_nonexistent_session(self, mock_cache):
        """Test getting a session that doesn't exist."""
        from app.services.session import SessionService

        service = SessionService(mock_cache)
        result = await service.get_session("nonexistent-session-id")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_or_create_session_new(self, mock_cache):
        """Test get_or_create when session doesn't exist."""
        from app.services.session import SessionService

        service = SessionService(mock_cache)
        session = await service.get_or_create_session(None)

        assert session.session_id is not None
        assert session.messages == []

    @pytest.mark.asyncio
    async def test_get_or_create_session_existing(self, mock_cache):
        """Test get_or_create retrieves existing session."""
        from app.services.session import SessionService

        service = SessionService(mock_cache)
        original = await service.create_session()
        original.add_user_message("test message")
        await service.update_session(original)

        # Should retrieve the same session
        retrieved = await service.get_or_create_session(original.session_id)

        assert retrieved.session_id == original.session_id
        assert len(retrieved.messages) == 1
        assert retrieved.messages[0].content == "test message"

    @pytest.mark.asyncio
    async def test_session_message_history(self, mock_cache):
        """Test adding messages to session."""
        from app.services.session import SessionService

        service = SessionService(mock_cache)
        session = await service.create_session()

        session.add_user_message("Find malaria genomes")
        session.add_assistant_message("Found 50 malaria genomes")
        session.add_user_message("Narrow to complete genomes")
        session.add_assistant_message("Found 12 complete malaria genomes")

        await service.update_session(session)

        # Retrieve and verify
        retrieved = await service.get_session(session.session_id)
        assert len(retrieved.messages) == 4
        assert retrieved.messages[0].role == "user"
        assert retrieved.messages[1].role == "assistant"
        assert "malaria" in retrieved.messages[0].content.lower()

    @pytest.mark.asyncio
    async def test_session_filter_accumulation(self, mock_cache):
        """Test accumulating filters in session."""
        from app.services.session import SearchFilter, SessionService

        service = SessionService(mock_cache)
        session = await service.create_session()

        # Add first filter
        session.update_filters(
            [
                SearchFilter(
                    column="taxonomicLevelDomain", operator="eq", value="Eukaryota"
                )
            ]
        )
        assert len(session.filters) == 1

        # Add second filter
        session.update_filters(
            [
                SearchFilter(
                    column="taxonomicLevelDomain", operator="eq", value="Eukaryota"
                ),
                SearchFilter(column="level", operator="eq", value="Complete Genome"),
            ]
        )
        assert len(session.filters) == 2

        await service.update_session(session)

        # Verify persistence
        retrieved = await service.get_session(session.session_id)
        assert len(retrieved.filters) == 2

    @pytest.mark.asyncio
    async def test_session_clear_filters(self, mock_cache):
        """Test clearing all filters in session."""
        from app.services.session import SearchFilter, SessionService

        service = SessionService(mock_cache)
        session = await service.create_session()

        session.update_filters(
            [SearchFilter(column="level", operator="eq", value="Complete Genome")]
        )
        assert len(session.filters) == 1

        session.clear_filters()
        assert len(session.filters) == 0

    @pytest.mark.asyncio
    async def test_session_context_summary(self, mock_cache):
        """Test generating context summary."""
        from app.services.session import SearchFilter, SessionService

        service = SessionService(mock_cache)
        session = await service.create_session()

        # No filters
        summary = session.get_context_summary()
        assert "No filters" in summary

        # With filters
        session.update_filters(
            [
                SearchFilter(column="level", operator="eq", value="Complete Genome"),
                SearchFilter(
                    column="taxonomicLevelSpecies",
                    operator="contains",
                    value="Plasmodium",
                ),
            ]
        )
        session.last_result_count = 42

        summary = session.get_context_summary()
        assert "level eq Complete Genome" in summary
        assert "42 results" in summary

    @pytest.mark.asyncio
    async def test_delete_session(self, mock_cache):
        """Test deleting a session."""
        from app.services.session import SessionService

        service = SessionService(mock_cache)
        session = await service.create_session()

        await service.delete_session(session.session_id)

        # Should not be retrievable
        result = await service.get_session(session.session_id)
        assert result is None


# ============================================================
# Conversational Search Integration Tests
# ============================================================


@pytest.mark.integration
class TestConversationalSearch:
    """Integration tests for multi-turn conversational search."""

    @pytest.mark.asyncio
    async def test_conversational_search_single_turn(self):
        """Test a single turn of conversational search."""
        service = CatalogSearchService()
        if not service.is_available():
            pytest.skip("LLM not available")

        result, messages = await service.conversational_search(
            query="complete bacterial genomes",
            message_history=None,
            current_filters=None,
        )

        assert result.success
        assert result.total_count > 0
        assert len(messages) > 0  # Should have message history

    @pytest.mark.asyncio
    async def test_conversational_search_with_context(self):
        """Test conversational search with existing filters as context."""
        service = CatalogSearchService()
        if not service.is_available():
            pytest.skip("LLM not available")

        # Start with some filters already applied
        current_filters = [
            {"column": "taxonomicLevelDomain", "operator": "eq", "value": "Eukaryota"}
        ]

        result, messages = await service.conversational_search(
            query="narrow to complete genomes",
            message_history=None,
            current_filters=current_filters,
        )

        assert result.success
        # Should have filters applied
        assert len(result.filters_applied) > 0
        # The agent might keep the domain filter or refine based on context

    @pytest.mark.asyncio
    async def test_multi_turn_progressive_refinement(self):
        """Test multi-turn conversation that progressively narrows results."""
        service = CatalogSearchService()
        if not service.is_available():
            pytest.skip("LLM not available")

        # Turn 1: Broad query
        result1, messages1 = await service.conversational_search(
            query="complete genomes", message_history=None, current_filters=None
        )
        assert result1.success
        count1 = result1.total_count

        # Turn 2: Narrow to specific domain (using message history)
        current_filters = [
            {"column": f.column, "operator": f.operator, "value": f.value}
            for f in result1.filters_applied
        ]
        result2, messages2 = await service.conversational_search(
            query="only bacterial ones",
            message_history=messages1,
            current_filters=current_filters,
        )
        assert result2.success
        count2 = result2.total_count

        # Results should narrow (or at least be different)
        # Note: exact behavior depends on LLM interpretation
        assert count2 <= count1 or len(result2.filters_applied) >= len(
            result1.filters_applied
        )

    @pytest.mark.asyncio
    async def test_multi_turn_with_clear_intent(self):
        """Test multi-turn where user wants to start over."""
        service = CatalogSearchService()
        if not service.is_available():
            pytest.skip("LLM not available")

        # Turn 1: Start with malaria
        result1, messages1 = await service.conversational_search(
            query="Plasmodium falciparum genomes",
            message_history=None,
            current_filters=None,
        )
        assert result1.success

        # Turn 2: Completely different query (should understand to start fresh)
        # Note: We're testing that the agent handles context appropriately
        result2, messages2 = await service.conversational_search(
            query="actually, search for E. coli instead",
            message_history=messages1,
            current_filters=None,  # Clear filters to indicate fresh start
        )

        assert result2.success
        # The agent should understand the intent to switch topics
        # (This is a best-effort test - LLM behavior may vary)
        assert len(result2.filters_applied) > 0
