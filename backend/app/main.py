import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlmodel import Session

from .api import router
from .config import get_settings
from .db import engine, init_db
from .errors import DomainError
from .ui_api import router as ui_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    if get_settings().auto_create_tables:
        init_db()
    if os.getenv("SEED_ON_STARTUP", "1").lower() in ("1", "true", "yes"):
        from .demo_seed import seed_demo
        from .seed_data import seed

        with Session(engine) as s:
            seed(s)
            seed_demo(s)
    yield


app = FastAPI(title="WordAudit API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins.split(","), allow_methods=["*"],
                   allow_headers=["*"])


@app.exception_handler(DomainError)
async def domain_error_handler(_: Request, exc: DomainError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


app.include_router(router)
app.include_router(ui_router)
