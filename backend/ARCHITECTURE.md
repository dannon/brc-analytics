# BRC Analytics Backend Architecture

## Overview

This document explains the architectural decisions behind adding a FastAPI backend to BRC Analytics, a Next.js-based static genomics data portal. The backend enables three key capabilities that static generation cannot provide:

1. **AI-Powered Question Answering** - LLMs help users find data, suggest workflows, and answer genomics analysis questions
2. **Galaxy Integration** - Computational workflow execution via BioBlend
3. **Real-time Data** - External API integration (ENA sequencing data)

**Scale:** 85 files, 12,554 lines, 70 e2e tests, 3 major services (FastAPI, Redis, nginx)

---

## Why Add a Backend?

### Original Architecture Limitations

BRC Analytics was built as a purely static Next.js site for CDN deployment. This provided excellent performance but fundamental limitations:

- **Static search only** - All queries pre-indexed at build time, no dynamic filtering
- **No computation** - Users can browse workflows but not execute them
- **No live data** - Cannot fetch fresh sequencing runs from ENA/NCBI
- **No personalization** - Every user sees identical content

### User Requirements

Three critical needs emerged from user feedback:

**1. AI-Powered Assistance**

Researchers need help navigating the complexity of genomics data and workflows:

- **Data discovery**: _"Find Plasmodium falciparum drug resistance WGS from 2024"_ → structured search parameters
- **Workflow guidance**: _"I have RNA-seq data from a non-model organism, what workflow should I use?"_ → workflow recommendations
- **Analysis planning**: _"How do I analyze outbreak surveillance data?"_ → step-by-step guidance
- Not: Manual taxonomy lookups, workflow browsing, reading documentation
- Solution requires: LLM to understand user intent across multiple domains (data, workflows, analysis methods)

**2. Galaxy Workflow Execution**

- Researchers want: Click "Run Analysis" → configure parameters → monitor job
- Not: Download data → install tools → run manually
- Solution requires: Galaxy API integration, file upload, job monitoring

**3. Live ENA Data**

- Researchers want: Fetch latest sequencing runs by accession number
- Not: Wait for next static site rebuild
- Solution requires: Real-time API calls, caching, data transformation

### Why a Dedicated Backend?

**Key Requirements:**

1. **Galaxy Integration** - BioBlend (official Python library) provides convenient Galaxy API integration
2. **Database Analytics** - DuckDB + Python data ecosystem (pandas, polars, arrow) for genomics metadata analytics
3. **Long-running workflows** - Galaxy jobs run for minutes to hours, need stateful job tracking
4. **Colocation** - TACC hosts Galaxy + databases + compute infrastructure

**Why FastAPI + Python:**

**Ecosystem alignment:**

- **DuckDB integration** - First-class Python bindings, natural fit with pandas/polars for data transformation
- **BioBlend** - Official Galaxy library maintained by Galaxy core team
- **Pydantic AI** - Provider-agnostic LLM framework with excellent structured output support

**Technical benefits:**

- **Async-native** - Handles concurrent LLM calls, Galaxy API requests, and database queries efficiently
- **Type safety** - Pydantic models + auto-generated OpenAPI → TypeScript types for frontend
- **Auto documentation** - Interactive API docs at `/api/docs` without manual work

**Deployment architecture:**

```
TACC Infrastructure:
├── PostgreSQL (metadata)
├── DuckDB (analytics)
├── Galaxy instances (workflows)
└── FastAPI backend ──→ All colocated, low-latency access
         ↓
    Next.js frontend (CDN or TACC nginx)
```

This architecture creates clear separation:

- **Frontend** (Next.js/TypeScript): User interaction, visualization
- **Backend** (FastAPI/Python): Database analytics, Galaxy integration, LLM orchestration
- **Data layer**: All Python-native tools colocated at TACC

---

## Technology Choices

### FastAPI (Web Framework)

**Why FastAPI?**

- **Galaxy integration** - BioBlend (official Galaxy Python client maintained by Galaxy core team) provides mature, well-tested Galaxy API integration
- **Type safety** - Pydantic models with automatic validation catch errors at development time
- **Async-native** - First-class async/await support for concurrent LLM calls, Galaxy API requests, and database queries
- **Auto-documentation** - OpenAPI/Swagger docs generated automatically from type annotations
- **Production-ready** - Battle-tested at scale with excellent performance characteristics

### Pydantic AI (LLM Framework)

**Why Pydantic AI?**

- **Provider-agnostic** - Supports OpenAI, Anthropic, SambaNova without code changes
- **Type safety** - Structured outputs using Pydantic models we already use in FastAPI
- **Async-native** - First-class async/await support
- **Flexibility** - Can switch models (GPT-4o, Claude, open-source) via configuration
- **Simplicity** - Lightweight, focused on structured outputs without unnecessary abstractions

**Key pattern - Dual model optimization:**

```python
# Powerful model for complex reasoning
reasoning_model = "claude-3-5-sonnet-20241022"

# Fast model for simple formatting
formatting_model = "claude-haiku-4-5-20251001"

# Optimization: Use expensive model only where needed, fast model for formatting
```

### Redis (Caching)

**Why Redis?**

Performance-critical operations need fast caching:

- **Database queries** - DuckDB analytics queries (primary use case)
- **LLM responses** - 3-8 second calls reduced to ~50ms
- **External APIs** - ENA data fetches, NCBI lookups
- **Deterministic operations** - Same input → same output (within TTL)

Redis provides:

- **Dramatic latency reduction** - Multi-second operations → milliseconds
- **High throughput** - Handle concurrent requests efficiently
- **Flexible TTL** - Different expiration times per use case (1 hour for LLM, 1 day for workflows, custom for DB queries)
- **LRU eviction** - Automatic memory management
- **Simple deployment** - Single-instance sufficient, scales to cluster when needed
- **Production-ready** - Battle-tested, reliable, well-understood operational characteristics

### Docker Compose (Deployment)

**Why Docker Compose?**

- **Multi-service** - Orchestrates nginx + FastAPI + Redis with service discovery
- **Reproducible** - Same environment in dev/staging/production
- **Simple** - No Kubernetes complexity for 3-service architecture
- **Scalable enough** - Handles 10-100 concurrent users (current requirement)

Future scaling path: Load balancer → multiple backend instances → Redis cluster → Kubernetes (if traffic exceeds 100 RPS)

---

## Implementation Highlights

### 1. AI-Powered Question Answering

The LLM system handles two primary use cases:

**A. Dataset Search** - Natural language to structured queries

```
User query: "Plasmodium falciparum RNA-seq from 2024"
    ↓
Check Redis cache (key = SHA256(query))
    ↓ (cache miss)
Phase 1: LLM reasoning (Claude Sonnet)
    → Extract: organism, taxonomy ID, experiment type, date range
    ↓
Phase 2: LLM formatting (Claude Haiku)
    → Convert to JSON matching DatasetQuery schema
    ↓
Pydantic validation → structured data
    ↓
Cache result (TTL = 1 hour)
    ↓
Return to frontend
```

**B. Workflow Suggestions** - Data/goals to workflow recommendations

```
User input: "I have paired-end RNA-seq from a non-model organism"
    ↓
Check Redis cache
    ↓ (cache miss)
LLM reasoning (Claude Sonnet)
    → Understand: data type, organism type, analysis goals
    → Match: compatible workflows from catalog
    → Recommend: ranked workflow suggestions with explanations
    ↓
Format as WorkflowSuggestion schema
    ↓
Cache result (TTL = 1 day)
    ↓
Return to frontend
```

**Performance:**

- Dataset search (cold): 3-8 seconds
- Workflow suggestions (cold): 4-10 seconds
- Cached responses: ~50-60ms
- Cache hit rate: ~20-30% in production (estimated)

### 2. Invalid Query Detection

LLMs hallucinate plausible results for gibberish ("asdf123" → "Organism: Arabidopsis" ❌).

**Multi-layer validation:**

1. **Prompt engineering** - Instruct model to detect invalid queries
2. **Confidence scoring** - Compute 0-1 score based on reasoning quality
3. **Post-processing** - Reject queries below 0.5 confidence threshold

**Test results:**

- Valid biology queries: >90% confidence
- Random gibberish: <30% confidence
- Ambiguous queries: 40-70% confidence (appropriate uncertainty)

### 3. Galaxy Workflow Integration

**Full Workflow Implementation:**

```
User clicks "Run Workflow" on dataset page
    ↓
1. Create Galaxy History (container for job)
    POST /api/v1/galaxy/histories
    ↓
2. Upload Data Files
    - Option A: Upload from URL (ENA FASTQ files)
      POST /api/v1/galaxy/upload-from-url
    - Option B: Upload local file
      POST /api/v1/galaxy/upload-file (multipart/form-data)
    ↓
3. Configure Workflow Parameters
    Frontend: GalaxyJobForm component
    - Assembly reference genome URL
    - Gene model (GTF) URL
    - Sequencing read parameters
    - Tool-specific options
    ↓
4. Submit Workflow
    POST /api/v1/galaxy/workflows/{workflow_id}/run
    Backend creates workflow invocation via BioBlend
    Returns: job_id, history_id
    ↓
5. Monitor Status (Polling)
    GET /api/v1/galaxy/jobs/{job_id}/status (every 5s)
    Frontend: GalaxyJobStatus component shows progress
    States: new → queued → running → ok/error
    ↓
6. Retrieve Results
    GET /api/v1/galaxy/histories/{history_id}/datasets
    Frontend: GalaxyJobResults component shows output files
```

**Key Implementation Patterns:**

**Async wrapper for sync BioBlend:**

```python
class GalaxyService:
    def __init__(self, galaxy_instance: GalaxyInstance):
        self.gi = galaxy_instance

    async def create_history(self, name: str) -> str:
        """Wrap sync BioBlend call in thread pool"""
        loop = asyncio.get_event_loop()
        history = await loop.run_in_executor(
            None,
            lambda: self.gi.histories.create_history(name=name)
        )
        return history['id']

    async def upload_from_url(
        self,
        history_id: str,
        file_url: str,
        file_type: str = "auto"
    ) -> str:
        """Upload file from URL (e.g., ENA FASTQ)"""
        loop = asyncio.get_event_loop()
        dataset = await loop.run_in_executor(
            None,
            lambda: self.gi.tools.upload_file(
                file_url,
                history_id,
                file_type=file_type
            )
        )
        return dataset['outputs'][0]['id']

    async def invoke_workflow(
        self,
        workflow_id: str,
        history_id: str,
        inputs: Dict[str, Any],
        params: Dict[str, Any]
    ) -> str:
        """Submit workflow with parameters"""
        loop = asyncio.get_event_loop()
        invocation = await loop.run_in_executor(
            None,
            lambda: self.gi.workflows.invoke_workflow(
                workflow_id,
                inputs=inputs,
                params=params,
                history_id=history_id
            )
        )
        return invocation['id']
```

**Frontend state management:**

```typescript
// hooks/useGalaxyJob.ts
export function useGalaxyJob(jobId: string) {
  const [status, setStatus] = useState<JobStatus>("pending");
  const [results, setResults] = useState<Dataset[]>([]);

  useEffect(() => {
    // Poll every 5 seconds
    const interval = setInterval(async () => {
      const response = await fetch(`/api/v1/galaxy/jobs/${jobId}/status`);
      const data = await response.json();
      setStatus(data.state);

      if (data.state === "ok") {
        // Fetch results when complete
        const resultsResponse = await fetch(
          `/api/v1/galaxy/histories/${data.history_id}/datasets`
        );
        setResults(await resultsResponse.json());
        clearInterval(interval);
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [jobId]);

  return { status, results };
}
```

**Current Implementation:**

- BioBlend handles Galaxy auth complexity (API keys, session management)
- Automatic deserialization of Galaxy responses
- Battle-tested library maintained by Galaxy core team
- Thread pool wraps synchronous BioBlend calls for async compatibility

**Future Work:**

- WebSocket connection for real-time job updates (replacing polling)
- Server-sent events (SSE) for progress streaming
- Webhook callbacks when jobs complete (email notifications)

### 4. Error Handling & Resilience

**Retry logic** (using tenacity library):

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(httpx.HTTPError)
)
async def call_llm(...):
    # Automatic retry on transient network failures
    # Exponential backoff: 2s, 4s, 8s
```

**Validation** (Pydantic models):

```python
class DatasetSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    max_results: int = Field(default=10, ge=1, le=100)

# FastAPI automatically validates, returns 422 for invalid requests
```

---

## Testing Strategy

### E2E Testing with Playwright (~70 tests, 8 test modules)

**Why E2E instead of pure API tests?**

- Tests **full stack** - Frontend React → FastAPI → LLM/Galaxy
- Catches CORS issues, serialization bugs, type mismatches
- Validates actual user workflows end-to-end
- Verifies Next.js SSG constraints work with dynamic backend

**Coverage:**

- Health checks & monitoring
- LLM query interpretation
- Cache behavior & TTL
- Invalid query detection
- Galaxy job submission
- API contract validation

**Trade-off:** Slower (~2-5s per test) but higher confidence than unit tests

---

## Performance

### Measured Latencies

| Operation           | Cold      | Cached | Notes                       |
| ------------------- | --------- | ------ | --------------------------- |
| Health check        | 20ms      | 10ms   | Redis ping                  |
| LLM search          | 3-8s      | 50ms   | Dual LLM calls vs. cache    |
| Workflow suggestion | 4-10s     | 60ms   | More complex reasoning      |
| ENA data fetch      | 200-500ms | 30ms   | External API + cache        |
| DB queries          | TBD       | TBD    | Planned: DuckDB with caching |

**Performance strategy:**

- **Caching first** - Redis dramatically reduces latency for all operations
- **Provider flexibility** - Can switch to faster/cheaper LLM providers as needed
- **Async architecture** - Handle multiple concurrent requests efficiently
- **Database optimization** - DuckDB analytics with Redis caching layer

---

## Production Readiness

### Current State: Demo/Pilot Ready ✅

- Core functionality works end-to-end
- 70 passing E2E tests
- Docker deployment tested
- API documentation auto-generated
- Error handling implemented

### Production Gaps

**Infrastructure:**

- [ ] Monitoring/alerting (Prometheus, Grafana)
- [ ] Rate limiting per user/IP
- [ ] Horizontal scaling (load balancer + multiple backends)
- [ ] Secret management (AWS Secrets Manager, Vault)

**Code Quality:**

- [ ] More comprehensive logging with request IDs
- [ ] Load testing (currently untested beyond ~10 concurrent requests)
- [ ] Disaster recovery plan

**Estimated effort to production:** 3-4 weeks

---

## Key Design Decisions

### What Went Well

✅ **Type safety** - Pydantic models caught numerous bugs during development
✅ **Docker Compose** - Rapid iteration on multi-service stack
✅ **E2E tests** - Caught integration issues unit tests would miss
✅ **Provider abstraction** - Easy to switch between Claude, GPT-4, SambaNova

### Current Implementation Notes

**LLM Strategy:**

- Dual-model approach (Sonnet for reasoning, Haiku for formatting) achieves 30% cost savings
- Alternative: Single model with Pydantic AI's `result_type` structured outputs may simplify while maintaining type safety

**Job Monitoring:**

- Polling-based status checks (5s interval) work well for demo/pilot scale
- Future: WebSocket or SSE for real-time updates on long-running workflows

**Deployment:**

- Single-instance deployment sufficient for current load
- Future: Load balancer + multiple instances + Redis cluster for production scale

### What We'd Do Differently

- Use Pydantic AI's structured output (`result_type`) from day one instead of manual JSON parsing
- Add request ID tracking and distributed tracing from the start
- Load test earlier to understand scaling limits
- Consider semantic caching (embedding-based similarity) for better cache hit rates

---

## Conclusion

This implementation establishes a **coherent architecture** for AI-powered genomics data analysis. The FastAPI + Python backend aligns naturally with the bioinformatics ecosystem and planned infrastructure:

**Architectural strengths:**

- **Python ecosystem alignment** - DuckDB, BioBlend, data analytics libraries (pandas/polars) all first-class
- **TACC colocation** - Backend colocated with databases, Galaxy instances, and compute infrastructure
- **Clear separation** - Static frontend (CDN) + dynamic Python backend (analytics/computation)
- **Type safety** - Pydantic models enforce contracts, auto-generate OpenAPI for frontend integration
- **Provider flexibility** - LLM abstraction allows switching between Claude, GPT-4, open-source models

**Current capabilities:**

- ✅ Natural language dataset search with invalid query detection
- ✅ Workflow recommendations based on data type and analysis goals
- ✅ Galaxy workflow submission and monitoring
- ✅ ENA data integration with caching
- ✅ 70 E2E tests validating full-stack integration

**Future expansion:**

With databases added to the stack, the Python backend becomes the **natural integration layer** for:

- DuckDB analytics queries across genomics metadata
- PostgreSQL transactional data management
- Pandas/Polars data transformations feeding LLM context
- Galaxy workflow orchestration with database-backed state tracking

**Additional use cases and testing:**

- Multi-organism comparative genomics queries across species
- Temporal analysis (outbreak tracking, evolutionary studies)
- Batch workflow submission for large-scale analyses
- Advanced LLM features (RAG over scientific literature, protocol suggestions)
- Expanded test coverage (load testing, security testing, integration testing with real Galaxy instances)
- User feedback integration for LLM query refinement

**Next steps:** Production hardening (monitoring, rate limiting, load testing), database integration, WebSocket-based job status updates, and expanding test coverage to validate emerging use cases.
