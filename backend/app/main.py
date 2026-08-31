from app.api.routes import auth, vehicles, requests, shifts, contractors, rbac, me, categories
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes import auth, vehicles, requests, shifts


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"🚀 {settings.app_name} v{settings.app_version} starting...")
    yield
    print("👋 Shutting down...")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

allowed_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(vehicles.router, prefix="/api/v1/vehicles", tags=["vehicles"])
app.include_router(requests.router, prefix="/api/v1/requests", tags=["requests"])
app.include_router(shifts.router, prefix="/api/v1/shifts", tags=["shifts"])
app.include_router(contractors.router, prefix="/api/v1/contractors", tags=["contractors"])
app.include_router(rbac.router, prefix="/api/v1/rbac", tags=["rbac"])
app.include_router(me.router, prefix="/api/v1", tags=["me"])
app.include_router(categories.router, prefix="/api/v1/categories", tags=["categories"])


@app.get("/health")
def health_check():
    return {"status": "healthy", "version": settings.app_version}


@app.get("/ready")
def readiness_check():
    from app.core.db import SessionLocal
    from sqlalchemy import text

    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_ok = True
    except Exception:
        db_ok = False

    return {"status": "ready" if db_ok else "not_ready", "checks": {"database": db_ok}}