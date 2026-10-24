from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import router
from .config import get_settings
from .db import init_db
from .errors import DomainError


@asynccontextmanager
async def lifespan(app: FastAPI):
    if get_settings().auto_create_tables:
        init_db()
    yield


app = FastAPI(title="BrandTrust API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins.split(","), allow_methods=["*"],
                   allow_headers=["*"])


@app.exception_handler(DomainError)
async def domain_error_handler(_: Request, exc: DomainError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


app.include_router(router)
