from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Agricultural decision-support API using satellite and soil data.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/", tags=["Root"])
def root():
    return {"application": settings.app_name, "status": "running"}


@app.get("/health", tags=["Health"])
def health():
    # This endpoint checks the API process only; it does not query MySQL.
    return {"status": "healthy"}
