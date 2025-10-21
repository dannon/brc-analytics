from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import cache, ena, galaxy, health, llm, ncbi_links, version
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="BRC Analytics API",
    version=settings.APP_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(cache.router, prefix="/api/v1/cache", tags=["cache"])
app.include_router(version.router, prefix="/api/v1/version", tags=["version"])
app.include_router(ncbi_links.router, prefix="/api/v1/links", tags=["ncbi-links"])
app.include_router(galaxy.router, prefix="/api/v1/galaxy", tags=["galaxy"])
app.include_router(llm.router, prefix="/api/v1/llm", tags=["llm"])
app.include_router(ena.router, prefix="/api/v1/ena", tags=["ena"])


@app.get("/")
async def root():
    return {"message": "BRC Analytics API", "version": settings.APP_VERSION}
