from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import engine
from .models import Base
from .routers import admin, candidate

app = FastAPI(title="questionme", docs_url=None, redoc_url=None, openapi_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.public_base_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(candidate.router)
app.include_router(admin.router)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(engine)


@app.get("/healthz")
def healthz() -> dict:
    """Liveness only. See /readyz for the one that touches the database."""
    return {"ok": True, "environment": settings.environment}


@app.get("/readyz")
def readyz() -> dict:
    """Readiness: a real round-trip through the app's own pool, so this fails
    when the application cannot reach MariaDB - which is the failure a plain
    liveness check hides."""
    from sqlalchemy import text

    from .db import SessionLocal
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"ok": True, "db": "up"}
    finally:
        db.close()
