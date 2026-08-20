"""Contrato de erro único (spec.md §8.4) e handlers de exceção do FastAPI."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.repositories.exceptions import OrdenacaoInvalida
from app.services.exceptions import (
    AcessoNegado,
    ApprovadorHierarquicoNaoResolvido,
    AprovacaoForaDeOrdem,
    AprovacaoJaDecidida,
    AprovacaoNaoEncontrada,
    ColaboradorNaoEncontrado,
    CredenciaisInvalidas,
    FalhaTecnicaValidacao,
    LoginBloqueado,
    MovimentacaoNaoAguardandoAprovacao,
    MovimentacaoNaoEncontrada,
    ReferenciaNaoEncontrada,
    TokenInvalidoOuExpirado,
    ValidacaoEmAndamento,
    ValidacaoManualNaoPermitida,
)


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


async def _handler_validacao_manual_nao_permitida(
    request: Request, exc: ValidacaoManualNaoPermitida
) -> JSONResponse:
    corpo = _erro("VALIDACAO_MANUAL_NAO_PERMITIDA", str(exc))
    corpo["impedimentos"] = [
        {"origem": i.origem, "codigo": i.codigo, "mensagem": i.mensagem} for i in exc.impedimentos
    ]
    return JSONResponse(status_code=409, content=corpo)


async def _handler_validacao_em_andamento(request: Request, exc: ValidacaoEmAndamento) -> JSONResponse:
    return JSONResponse(status_code=409, content=_erro("VALIDACAO_EM_ANDAMENTO", str(exc)))


async def _handler_erro_interno(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content=_erro("ERRO_INTERNO", "Erro interno do servidor"))


async def _handler_credenciais_invalidas(request: Request, exc: CredenciaisInvalidas) -> JSONResponse:
    resposta = JSONResponse(status_code=401, content=_erro("CREDENCIAIS_INVALIDAS", str(exc)))
    resposta.headers["Cache-Control"] = "no-store"
    return resposta


async def _handler_login_bloqueado(request: Request, exc: LoginBloqueado) -> JSONResponse:
    resposta = JSONResponse(status_code=429, content=_erro("LOGIN_BLOQUEADO", str(exc)))
    resposta.headers["Retry-After"] = str(exc.retry_after_seconds)
    resposta.headers["Cache-Control"] = "no-store"
    return resposta


async def _handler_token_invalido(request: Request, exc: TokenInvalidoOuExpirado) -> JSONResponse:
    resposta = JSONResponse(status_code=401, content=_erro("TOKEN_INVALIDO", str(exc)))
    resposta.headers["Cache-Control"] = "no-store"
    return resposta


async def _handler_acesso_negado(request: Request, exc: AcessoNegado) -> JSONResponse:
    return JSONResponse(status_code=403, content=_erro("ACESSO_NEGADO", str(exc)))


async def _handler_colaborador_nao_encontrado(request: Request, exc: ColaboradorNaoEncontrado) -> JSONResponse:
    return JSONResponse(status_code=404, content=_erro("COLABORADOR_NAO_ENCONTRADO", str(exc)))


async def _handler_referencia_nao_encontrada(request: Request, exc: ReferenciaNaoEncontrada) -> JSONResponse:
    return JSONResponse(status_code=404, content=_erro("REFERENCIA_NAO_ENCONTRADA", str(exc)))


async def _handler_aprovacao_nao_encontrada(request: Request, exc: AprovacaoNaoEncontrada) -> JSONResponse:
    return JSONResponse(status_code=404, content=_erro("APROVACAO_NAO_ENCONTRADA", str(exc)))


async def _handler_aprovacao_ja_decidida(request: Request, exc: AprovacaoJaDecidida) -> JSONResponse:
    return JSONResponse(status_code=409, content=_erro("APROVACAO_JA_DECIDIDA", str(exc)))


async def _handler_aprovacao_fora_de_ordem(request: Request, exc: AprovacaoForaDeOrdem) -> JSONResponse:
    return JSONResponse(status_code=409, content=_erro("APROVACAO_FORA_DE_ORDEM", str(exc)))


async def _handler_movimentacao_nao_aguardando_aprovacao(
    request: Request, exc: MovimentacaoNaoAguardandoAprovacao
) -> JSONResponse:
    return JSONResponse(status_code=409, content=_erro("MOVIMENTACAO_NAO_AGUARDANDO_APROVACAO", str(exc)))


async def _handler_aprovador_hierarquico_nao_resolvido(
    request: Request, exc: ApprovadorHierarquicoNaoResolvido
) -> JSONResponse:
    return JSONResponse(status_code=409, content=_erro("APROVADOR_HIERARQUICO_NAO_RESOLVIDO", str(exc)))


def registrar_handlers(app: FastAPI) -> None:
    app.add_exception_handler(MovimentacaoNaoEncontrada, _handler_nao_encontrada)
    app.add_exception_handler(OrdenacaoInvalida, _handler_parametro_invalido)
    app.add_exception_handler(RequestValidationError, _handler_payload_invalido)
    app.add_exception_handler(ValidacaoManualNaoPermitida, _handler_validacao_manual_nao_permitida)
    app.add_exception_handler(ValidacaoEmAndamento, _handler_validacao_em_andamento)
    app.add_exception_handler(FalhaTecnicaValidacao, _handler_erro_interno)
    app.add_exception_handler(CredenciaisInvalidas, _handler_credenciais_invalidas)
    app.add_exception_handler(LoginBloqueado, _handler_login_bloqueado)
    app.add_exception_handler(TokenInvalidoOuExpirado, _handler_token_invalido)
    app.add_exception_handler(AcessoNegado, _handler_acesso_negado)
    app.add_exception_handler(ColaboradorNaoEncontrado, _handler_colaborador_nao_encontrado)
    app.add_exception_handler(ReferenciaNaoEncontrada, _handler_referencia_nao_encontrada)
    app.add_exception_handler(AprovacaoNaoEncontrada, _handler_aprovacao_nao_encontrada)
    app.add_exception_handler(AprovacaoJaDecidida, _handler_aprovacao_ja_decidida)
    app.add_exception_handler(AprovacaoForaDeOrdem, _handler_aprovacao_fora_de_ordem)
    app.add_exception_handler(MovimentacaoNaoAguardandoAprovacao, _handler_movimentacao_nao_aguardando_aprovacao)
    app.add_exception_handler(ApprovadorHierarquicoNaoResolvido, _handler_aprovador_hierarquico_nao_resolvido)
    app.add_exception_handler(Exception, _handler_erro_interno)
