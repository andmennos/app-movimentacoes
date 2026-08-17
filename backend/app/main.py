from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401 — registra as entidades em Base.metadata
from app.api.errors import registrar_handlers
from app.api.routers import movimentacoes, validacao
from app.database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(
    title="Portal de Mobilidade Organizacional",
    description="Motor de validação determinístico de movimentações organizacionais.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

registrar_handlers(app)

app.include_router(movimentacoes.router)
app.include_router(validacao.router)
