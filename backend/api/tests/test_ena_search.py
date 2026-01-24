"""
Tests for ENA Search service.

These tests verify:
1. Direct search (filter-based, no LLM)
2. Natural language search (LLM-powered)
3. Multi-turn conversation (session-based refinement)
4. Schema and field value access
5. Edge cases and error handling
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.ena_search import ENAFilter, ENASearch
from app.services.ena_search import ENA_SCHEMA, ORGANISM_VOCABULARY, ENADeps

# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def sample_ena_results():
    """Sample ENA read run data for testing."""
    return [
        {
            "run_accession": "SRR1234567",
            "scientific_name": "Plasmodium falciparum",
            "tax_id": "36329",
            "library_strategy": "RNA-Seq",
            "library_layout": "PAIRED",
            "library_source": "TRANSCRIPTOMIC",
            "instrument_platform": "ILLUMINA",
            "instrument_model": "Illumina NovaSeq 6000",
            "read_count": 50000000,
            "base_count": 7500000000,
            "study_title": "P. falciparum transcriptome study",
        },
        {
            "run_accession": "SRR2345678",
            "scientific_name": "Plasmodium falciparum",
            "tax_id": "36329",
            "library_strategy": "WGS",
            "library_layout": "PAIRED",
            "library_source": "GENOMIC",
            "instrument_platform": "ILLUMINA",
            "instrument_model": "Illumina MiSeq",
            "read_count": 20000000,
            "base_count": 3000000000,
            "study_title": "P. falciparum WGS study",
        },
        {
            "run_accession": "SRR3456789",
            "scientific_name": "Candida auris",
            "tax_id": "498019",
            "library_strategy": "WGS",
            "library_layout": "SINGLE",
            "library_source": "GENOMIC",
            "instrument_platform": "OXFORD_NANOPORE",
            "instrument_model": "MinION",
            "read_count": 1000000,
            "base_count": 5000000000,
            "study_title": "C. auris nanopore sequencing",
        },
        {
            "run_accession": "SRR4567890",
            "scientific_name": "Candida auris",
            "tax_id": "498019",
            "library_strategy": "RNA-Seq",
            "library_layout": "PAIRED",
            "library_source": "TRANSCRIPTOMIC",
            "instrument_platform": "ILLUMINA",
            "instrument_model": "Illumina HiSeq 2500",
            "read_count": 30000000,
            "base_count": 4500000000,
            "study_title": "C. auris transcriptome",
        },
        {
            "run_accession": "SRR5678901",
            "scientific_name": "Mycobacterium tuberculosis",
            "tax_id": "1773",
            "library_strategy": "WGS",
            "library_layout": "PAIRED",
            "library_source": "GENOMIC",
            "instrument_platform": "ILLUMINA",
            "instrument_model": "Illumina NovaSeq 6000",
            "read_count": 100000000,
            "base_count": 15000000000,
            "study_title": "M. tuberculosis genome survey",
        },
    ]


@pytest.fixture
def mock_ena_service(sample_ena_results):
    """Create a mock ENA service."""
    service = MagicMock()
    service.search_by_taxonomy = AsyncMock(
        return_value={"data": sample_ena_results, "cached": False}
    )
    service.search_by_keywords = AsyncMock(
        return_value={"data": sample_ena_results, "cached": False}
    )
    service.get_by_accession = AsyncMock(
        return_value={"data": [sample_ena_results[0]], "cached": False}
    )
    return service


@pytest.fixture
def ena_deps(mock_ena_service):
    """Create ENADeps with mock ENA service."""
    return ENADeps(
        ena_service=mock_ena_service,
        schema_info=ENA_SCHEMA,
        organism_vocab=ORGANISM_VOCABULARY,
    )


# ============================================================
# Filter Tests
# ============================================================


class TestFilterApplication:
    """Tests for post-query filter application."""

    def test_filter_by_layout_paired(self, ena_deps, sample_ena_results):
        """Filter by library layout PAIRED."""
        filter_ = ENAFilter(field="library_layout", operator="eq", value="PAIRED")
        results = ena_deps.apply_filters(sample_ena_results, [filter_])
        assert len(results) == 4
        assert all(r["library_layout"] == "PAIRED" for r in results)

    def test_filter_by_layout_single(self, ena_deps, sample_ena_results):
        """Filter by library layout SINGLE."""
        filter_ = ENAFilter(field="library_layout", operator="eq", value="SINGLE")
        results = ena_deps.apply_filters(sample_ena_results, [filter_])
        assert len(results) == 1
        assert results[0]["run_accession"] == "SRR3456789"

    def test_filter_by_strategy(self, ena_deps, sample_ena_results):
        """Filter by library strategy."""
        filter_ = ENAFilter(field="library_strategy", operator="eq", value="RNA-Seq")
        results = ena_deps.apply_filters(sample_ena_results, [filter_])
        assert len(results) == 2
        assert all(r["library_strategy"] == "RNA-Seq" for r in results)

    def test_filter_by_platform(self, ena_deps, sample_ena_results):
        """Filter by instrument platform."""
        filter_ = ENAFilter(
            field="instrument_platform", operator="eq", value="ILLUMINA"
        )
        results = ena_deps.apply_filters(sample_ena_results, [filter_])
        assert len(results) == 4
        assert all(r["instrument_platform"] == "ILLUMINA" for r in results)

    def test_filter_by_platform_nanopore(self, ena_deps, sample_ena_results):
        """Filter by Nanopore platform."""
        filter_ = ENAFilter(
            field="instrument_platform", operator="eq", value="OXFORD_NANOPORE"
        )
        results = ena_deps.apply_filters(sample_ena_results, [filter_])
        assert len(results) == 1
        assert results[0]["instrument_platform"] == "OXFORD_NANOPORE"

    def test_filter_by_organism_contains(self, ena_deps, sample_ena_results):
        """Filter by organism name (contains)."""
        filter_ = ENAFilter(
            field="scientific_name", operator="contains", value="Candida"
        )
        results = ena_deps.apply_filters(sample_ena_results, [filter_])
        assert len(results) == 2
        assert all("Candida" in r["scientific_name"] for r in results)

    def test_filter_by_read_count_gt(self, ena_deps, sample_ena_results):
        """Filter by read count greater than."""
        filter_ = ENAFilter(field="read_count", operator="gt", value=25000000)
        results = ena_deps.apply_filters(sample_ena_results, [filter_])
        assert len(results) == 3
        assert all(r["read_count"] > 25000000 for r in results)

    def test_filter_by_read_count_gte(self, ena_deps, sample_ena_results):
        """Filter by read count greater than or equal."""
        filter_ = ENAFilter(field="read_count", operator="gte", value=30000000)
        results = ena_deps.apply_filters(sample_ena_results, [filter_])
        assert len(results) == 3
        assert all(r["read_count"] >= 30000000 for r in results)

    def test_filter_multiple_conditions(self, ena_deps, sample_ena_results):
        """Multiple filters are ANDed together."""
        filters = [
            ENAFilter(field="library_layout", operator="eq", value="PAIRED"),
            ENAFilter(field="library_strategy", operator="eq", value="WGS"),
            ENAFilter(field="instrument_platform", operator="eq", value="ILLUMINA"),
        ]
        results = ena_deps.apply_filters(sample_ena_results, filters)
        assert len(results) == 2
        assert all(r["library_layout"] == "PAIRED" for r in results)
        assert all(r["library_strategy"] == "WGS" for r in results)
        assert all(r["instrument_platform"] == "ILLUMINA" for r in results)

    def test_filter_no_matches(self, ena_deps, sample_ena_results):
        """No matches returns empty list."""
        filter_ = ENAFilter(
            field="instrument_platform", operator="eq", value="PACBIO_SMRT"
        )
        results = ena_deps.apply_filters(sample_ena_results, [filter_])
        assert len(results) == 0

    def test_filter_case_insensitive_string(self, ena_deps, sample_ena_results):
        """String comparison should be case insensitive."""
        filter_ = ENAFilter(field="library_layout", operator="eq", value="paired")
        results = ena_deps.apply_filters(sample_ena_results, [filter_])
        assert len(results) == 4

    def test_filter_contains_case_insensitive(self, ena_deps, sample_ena_results):
        """Contains operator should be case insensitive."""
        filter_ = ENAFilter(
            field="scientific_name", operator="contains", value="PLASMODIUM"
        )
        results = ena_deps.apply_filters(sample_ena_results, [filter_])
        assert len(results) == 2


# ============================================================
# Organism Vocabulary Tests
# ============================================================


class TestOrganismVocabulary:
    """Tests for organism name to taxonomy ID mapping."""

    def test_common_organisms_in_vocabulary(self):
        """Verify common organisms are in vocabulary."""
        assert "malaria" in ORGANISM_VOCABULARY
        assert "tb" in ORGANISM_VOCABULARY
        assert "yeast" in ORGANISM_VOCABULARY
        assert "candida auris" in ORGANISM_VOCABULARY

    def test_plasmodium_mappings(self):
        """Verify Plasmodium taxonomy ID mappings."""
        assert ORGANISM_VOCABULARY["malaria"] == "5833"
        assert ORGANISM_VOCABULARY["plasmodium falciparum"] == "36329"
        assert ORGANISM_VOCABULARY["p. falciparum"] == "36329"

    def test_tuberculosis_mappings(self):
        """Verify TB taxonomy ID mappings."""
        assert ORGANISM_VOCABULARY["tuberculosis"] == "1773"
        assert ORGANISM_VOCABULARY["tb"] == "1773"
        assert ORGANISM_VOCABULARY["mycobacterium tuberculosis"] == "1773"

    def test_candida_mappings(self):
        """Verify Candida taxonomy ID mappings."""
        assert ORGANISM_VOCABULARY["candida"] == "5475"
        assert ORGANISM_VOCABULARY["candida auris"] == "498019"
        assert ORGANISM_VOCABULARY["c. auris"] == "498019"


# ============================================================
# Schema Tests
# ============================================================


class TestENASchema:
    """Tests for ENA schema definition."""

    def test_required_fields_present(self):
        """Verify all required fields are in schema."""
        required = [
            "library_layout",
            "library_strategy",
            "library_source",
            "instrument_platform",
            "scientific_name",
            "tax_id",
            "read_count",
        ]
        for field in required:
            assert field in ENA_SCHEMA

    def test_enum_fields_have_values(self):
        """Enum fields should have predefined values."""
        assert "values" in ENA_SCHEMA["library_layout"]
        assert "PAIRED" in ENA_SCHEMA["library_layout"]["values"]
        assert "SINGLE" in ENA_SCHEMA["library_layout"]["values"]

        assert "values" in ENA_SCHEMA["library_strategy"]
        assert "WGS" in ENA_SCHEMA["library_strategy"]["values"]
        assert "RNA-Seq" in ENA_SCHEMA["library_strategy"]["values"]

        assert "values" in ENA_SCHEMA["instrument_platform"]
        assert "ILLUMINA" in ENA_SCHEMA["instrument_platform"]["values"]
        assert "OXFORD_NANOPORE" in ENA_SCHEMA["instrument_platform"]["values"]

    def test_fields_have_descriptions(self):
        """All fields should have descriptions."""
        for field, info in ENA_SCHEMA.items():
            assert "description" in info, f"Field {field} missing description"
            assert len(info["description"]) > 0


# ============================================================
# ENASearch Model Tests
# ============================================================


class TestENASearchModel:
    """Tests for ENASearch model validation."""

    def test_valid_taxonomy_search(self):
        """Valid taxonomy search params."""
        search = ENASearch(
            search_method="taxonomy",
            taxonomy_id="36329",
            filters=[],
            limit=100,
        )
        assert search.search_method == "taxonomy"
        assert search.taxonomy_id == "36329"

    def test_valid_keywords_search(self):
        """Valid keywords search params."""
        search = ENASearch(
            search_method="keywords",
            keywords=["Plasmodium", "RNA-Seq"],
            filters=[],
            limit=100,
        )
        assert search.search_method == "keywords"
        assert len(search.keywords) == 2

    def test_valid_accession_search(self):
        """Valid accession lookup params."""
        search = ENASearch(
            search_method="accession",
            accession="SRR1234567",
            filters=[],
            limit=100,
        )
        assert search.search_method == "accession"
        assert search.accession == "SRR1234567"

    def test_search_with_filters(self):
        """Search with post-query filters."""
        search = ENASearch(
            search_method="taxonomy",
            taxonomy_id="36329",
            filters=[
                ENAFilter(field="library_layout", operator="eq", value="PAIRED"),
                ENAFilter(field="library_strategy", operator="eq", value="RNA-Seq"),
            ],
            limit=50,
        )
        assert len(search.filters) == 2

    def test_default_limit(self):
        """Default limit should be 100."""
        search = ENASearch(search_method="keywords", keywords=["test"])
        assert search.limit == 100

    def test_max_limit_enforced(self):
        """Limit should not exceed 500."""
        with pytest.raises(ValueError):
            ENASearch(search_method="keywords", keywords=["test"], limit=1000)


# ============================================================
# Natural Language Interpretation Tests
# ============================================================


class TestNaturalLanguageInterpretation:
    """Tests for expected NLP interpretations without calling LLM."""

    def test_paired_end_filter(self, ena_deps, sample_ena_results):
        """'paired-end' should map to library_layout = PAIRED."""
        expected_filter = ENAFilter(
            field="library_layout", operator="eq", value="PAIRED"
        )
        results = ena_deps.apply_filters(sample_ena_results, [expected_filter])
        assert len(results) == 4

    def test_wgs_filter(self, ena_deps, sample_ena_results):
        """'WGS' or 'whole genome' should map to library_strategy = WGS."""
        expected_filter = ENAFilter(
            field="library_strategy", operator="eq", value="WGS"
        )
        results = ena_deps.apply_filters(sample_ena_results, [expected_filter])
        assert len(results) == 3
        assert all(r["library_strategy"] == "WGS" for r in results)

    def test_rna_seq_filter(self, ena_deps, sample_ena_results):
        """'RNA-seq' or 'transcriptome' should map to library_strategy = RNA-Seq."""
        expected_filter = ENAFilter(
            field="library_strategy", operator="eq", value="RNA-Seq"
        )
        results = ena_deps.apply_filters(sample_ena_results, [expected_filter])
        assert len(results) == 2

    def test_illumina_filter(self, ena_deps, sample_ena_results):
        """'Illumina' should map to instrument_platform = ILLUMINA."""
        expected_filter = ENAFilter(
            field="instrument_platform", operator="eq", value="ILLUMINA"
        )
        results = ena_deps.apply_filters(sample_ena_results, [expected_filter])
        assert len(results) == 4

    def test_nanopore_filter(self, ena_deps, sample_ena_results):
        """'Nanopore' should map to instrument_platform = OXFORD_NANOPORE."""
        expected_filter = ENAFilter(
            field="instrument_platform", operator="eq", value="OXFORD_NANOPORE"
        )
        results = ena_deps.apply_filters(sample_ena_results, [expected_filter])
        assert len(results) == 1

    def test_combined_filters_plasmodium_rnaseq_paired(
        self, ena_deps, sample_ena_results
    ):
        """'Plasmodium RNA-seq paired-end' should combine multiple filters."""
        filters = [
            ENAFilter(field="scientific_name", operator="contains", value="Plasmodium"),
            ENAFilter(field="library_strategy", operator="eq", value="RNA-Seq"),
            ENAFilter(field="library_layout", operator="eq", value="PAIRED"),
        ]
        results = ena_deps.apply_filters(sample_ena_results, filters)
        assert len(results) == 1
        assert results[0]["run_accession"] == "SRR1234567"


# ============================================================
# Multi-turn Conversation Tests
# ============================================================


class TestMultiTurnConversation:
    """Tests for multi-turn conversation patterns."""

    def test_progressive_narrowing(self, ena_deps, sample_ena_results):
        """Test progressive narrowing of results."""
        # Turn 1: All Illumina data
        filters1 = [
            ENAFilter(field="instrument_platform", operator="eq", value="ILLUMINA")
        ]
        results1 = ena_deps.apply_filters(sample_ena_results, filters1)
        assert len(results1) == 4

        # Turn 2: Narrow to paired-end only
        filters2 = filters1 + [
            ENAFilter(field="library_layout", operator="eq", value="PAIRED")
        ]
        results2 = ena_deps.apply_filters(sample_ena_results, filters2)
        assert len(results2) == 4  # All Illumina are paired in sample data

        # Turn 3: Narrow to RNA-Seq
        filters3 = filters2 + [
            ENAFilter(field="library_strategy", operator="eq", value="RNA-Seq")
        ]
        results3 = ena_deps.apply_filters(sample_ena_results, filters3)
        assert len(results3) == 2

    def test_filter_replacement(self, ena_deps, sample_ena_results):
        """Test replacing a filter instead of adding."""
        # Start with WGS
        filters1 = [ENAFilter(field="library_strategy", operator="eq", value="WGS")]
        results1 = ena_deps.apply_filters(sample_ena_results, filters1)
        assert len(results1) == 3

        # Replace with RNA-Seq (user says "actually, RNA-seq")
        filters2 = [ENAFilter(field="library_strategy", operator="eq", value="RNA-Seq")]
        results2 = ena_deps.apply_filters(sample_ena_results, filters2)
        assert len(results2) == 2

    def test_filter_removal_to_broaden(self, ena_deps, sample_ena_results):
        """Test removing filter to get more results."""
        # Start with narrow filters
        filters1 = [
            ENAFilter(field="instrument_platform", operator="eq", value="ILLUMINA"),
            ENAFilter(field="library_strategy", operator="eq", value="RNA-Seq"),
        ]
        results1 = ena_deps.apply_filters(sample_ena_results, filters1)
        assert len(results1) == 2

        # Remove strategy filter (user says "show all library types")
        filters2 = [
            ENAFilter(field="instrument_platform", operator="eq", value="ILLUMINA")
        ]
        results2 = ena_deps.apply_filters(sample_ena_results, filters2)
        assert len(results2) == 4


# ============================================================
# Session Tests (reusing catalog pattern)
# ============================================================


class TestSessionWithENAFilters:
    """Tests for session management with ENA-specific filters."""

    @pytest.fixture
    def mock_cache(self):
        """Create a mock cache service."""
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
        return cache

    @pytest.mark.asyncio
    async def test_session_with_ena_style_filters(self, mock_cache):
        """Test session stores ENA-style filters."""
        from app.services.session import SearchFilter, SessionService

        service = SessionService(mock_cache)
        session = await service.create_session()

        # Add ENA-style filters (using 'column' internally as session does)
        session.update_filters(
            [
                SearchFilter(column="library_layout", operator="eq", value="PAIRED"),
                SearchFilter(column="library_strategy", operator="eq", value="RNA-Seq"),
            ]
        )

        await service.update_session(session)

        retrieved = await service.get_session(session.session_id)
        assert len(retrieved.filters) == 2
        assert retrieved.filters[0].column == "library_layout"
        assert retrieved.filters[1].column == "library_strategy"


# ============================================================
# Integration Tests (require running service)
# ============================================================


@pytest.mark.integration
class TestENASearchIntegration:
    """Integration tests that require full service running."""

    @pytest.mark.asyncio
    async def test_service_initialization(self):
        """Test that service initializes properly."""
        from app.services.ena_search import ENASearchService
        from app.services.ena_service import ENAService

        # Create minimal services for testing
        cache = MagicMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()

        ena_service = ENAService(cache)
        search_service = ENASearchService(ena_service)

        # Without API key, agent should not be available
        # But deps should be initialized
        assert search_service.deps is not None
        assert search_service.ena_service is not None

    @pytest.mark.asyncio
    async def test_real_search_plasmodium(self):
        """Test real search for Plasmodium data."""
        from app.core.dependencies import get_ena_search_service

        service = await get_ena_search_service()
        if not service.is_available():
            pytest.skip("LLM not available")

        result = await service.search("Plasmodium falciparum RNA-seq paired-end data")
        assert result.success
        # Should have filters for species, strategy, layout
        assert len(result.filters_applied) > 0
