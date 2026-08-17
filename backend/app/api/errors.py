"""Contrato de erro único (spec.md §8.4) e handlers de exceção do FastAPI."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.repositories.exceptions import OrdenacaoInvalida
from app.services.exceptions import MovimentacaoNaoEncontrada


def _erro(codigo: str, mensagem: str) -> dict:
    return {"erro": {"codigo": codigo, "mensagem": mensagem}}


async def _handler_nao_encontrada(request: Request, exc: MovimentacaoNaoEncontrada) -> JSONResponse:
    return JSONResponse(status_code=404, content=_erro("MOVIMENTACAO_NAO_ENCONTRADA", str(exc)))


async def _handler_parametro_invalido(request: Request, exc: OrdenacaoInvalida) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content=_erro("PARAMETRO_INVALIDO", f"Campo de ordenação inválido: {exc.campo}"),
    )


async def _handler_payload_invalido(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content=_erro("PAYLOAD_INVALIDO", "Payload inválido"))


async def _handler_erro_interno(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content=_erro("ERRO_INTERNO", "Erro interno do servidor"))


def registrar_handlers(app: FastAPI) -> None:
    app.add_exception_handler(MovimentacaoNaoEncontrada, _handler_nao_encontrada)
    app.add_exception_handler(OrdenacaoInvalida, _handler_parametro_invalido)
    app.add_exception_handler(RequestValidationError, _handler_payload_invalido)
    app.add_exception_handler(Exception, _handler_erro_interno)
