from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401 — registra as entidades em Base.metadata
from app.api.errors import registrar_handlers
from app.api.middleware import HardeningMiddleware
from app.api.routers import aprovacoes, auth, colaboradores, movimentacoes, referencias, validacao
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

app.add_middleware(HardeningMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

registrar_handlers(app)

app.include_router(auth.router)
app.include_router(movimentacoes.router)
app.include_router(aprovacoes.router)
app.include_router(colaboradores.router)
app.include_router(referencias.router)
app.include_router(validacao.router)
