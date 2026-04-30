from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.database import async_engine, Base
from app.api.documents import router as documents_router
from app.api.progress import router as progress_router
from app.config import get_settings
import os

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup — skip if DB not available
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        print(f"Warning: Could not create tables: {e}")
    yield
    await async_engine.dispose()


app = FastAPI(
    title="DocFlow API",
    description="Async Document Processing Workflow System",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production with actual frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents_router)
app.include_router(progress_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "DocFlow API"}


@app.get("/")
async def root():
    return {"status": "ok", "service": "DocFlow API"}
