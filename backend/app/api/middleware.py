"""Middlewares de hardening — spec.md §12.4/§12.5 (T-67).

Um único `BaseHTTPMiddleware` cobre, nesta ordem: limite de tamanho do
corpo em escritas, rate limiting geral (leitura/escrita, por IP+identidade),
e headers de segurança na resposta. `/auth/login` fica fora do rate limiter
geral — já tem proteção mais específica (lockout persistido, spec §12.3).
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import settings
from app.security import rate_limit
from app.security.jwt import TokenInvalido, decode_and_validate_token

_METODOS_ESCRITA = {"POST", "PUT", "PATCH", "DELETE"}
_ROTAS_SEM_RATE_LIMIT_GERAL = {"/auth/login"}

_HEADERS_SEGURANCA = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cache-Control": "no-store",
}


def _ip_cliente(request: Request) -> str:
    return request.client.host if request.client else "desconhecido"


def _identidade(request: Request) -> str:
    """Melhor esforço, sem tocar o banco (spec §14.2 — chave é IP+user_id
    quando autenticado, IP quando anônimo). Um token inválido/expirado
    apenas cai para "anônimo" aqui; a rota decide o 401 normalmente."""
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return "anon"
    token = auth[7:].strip()
    try:
        claims = decode_and_validate_token(token)
    except TokenInvalido:
        return "anon"
    return str(claims.get("sub", "anon"))


_ERRO_PAYLOAD_MUITO_GRANDE = {
    "erro": {"codigo": "PAYLOAD_MUITO_GRANDE", "mensagem": "Corpo da requisição excede o limite permitido."}
}


class HardeningMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in _METODOS_ESCRITA:
            # spec.md RC-40/SEC-03 (T-78) — Content-Length pode existir só
            # como fast-fail (barato, evita ler o corpo quando o cliente já
            # anuncia um tamanho grande demais), mas nunca pode ser a única
            # defesa: um cliente pode omiti-lo (chunked transfer-encoding)
            # ou mentir um valor menor que o corpo real. Por isso o limite é
            # sempre reconferido sobre os bytes efetivamente recebidos.
            content_length = request.headers.get("content-length")
            if content_length is not None:
                try:
                    tamanho_anunciado = int(content_length)
                except ValueError:
                    tamanho_anunciado = None
                if tamanho_anunciado is not None and tamanho_anunciado > settings.max_body_bytes:
                    return JSONResponse(status_code=413, content=_ERRO_PAYLOAD_MUITO_GRANDE)

            corpo = await request.body()  # Starlette cacheia — a rota ainda lê o mesmo corpo depois
            if len(corpo) > settings.max_body_bytes:
                return JSONResponse(status_code=413, content=_ERRO_PAYLOAD_MUITO_GRANDE)

        if request.url.path not in _ROTAS_SEM_RATE_LIMIT_GERAL:
            escrita = request.method in _METODOS_ESCRITA
            limite = settings.rate_limit_write_per_minute if escrita else settings.rate_limit_read_per_minute
            chave = f"{_ip_cliente(request)}:{_identidade(request)}:{'w' if escrita else 'r'}"
            permitido, retry_after = rate_limit.verificar_e_registrar(chave, limite)
            if not permitido:
                resposta = JSONResponse(
                    status_code=429,
                    content={"erro": {"codigo": "RATE_LIMIT_EXCEDIDO", "mensagem": "Muitas requisições — tente novamente mais tarde."}},
                )
                resposta.headers["Retry-After"] = str(retry_after)
                return resposta

        resposta = await call_next(request)
        for nome, valor in _HEADERS_SEGURANCA.items():
            resposta.headers[nome] = valor
        return resposta
