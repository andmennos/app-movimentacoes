from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"), env_file_encoding="utf-8", extra="ignore"
    )
    """`env_file` resolvido a partir de `BASE_DIR` (não do diretório de
    trabalho do processo) — funciona igual rodando `uvicorn` da raiz do
    repo, de `backend/`, ou via `pytest` (T-77/RC-39). `backend/.env` nunca
    é commitado (`.gitignore`); `backend/.env.example` documenta as
    variáveis sem conter segredo funcional."""

    database_path: Path = BASE_DIR / "portal_mobilidade.db"
    pagina_tamanho_default: int = 20
    pagina_tamanho_maximo: int = 100
    ciclo_limite_profundidade: int = 100
    versao_motor: str = "1.0.0"
    job_stale_after_seconds: int = 300
    """spec.md §7.4 — um job `PROCESSANDO` cujo `iniciado_em` ultrapassa este
    limite é considerado travado (processo que o adquiriu provavelmente
    morreu) e pode ser recuperado (T-52)."""

    jwt_secret: str
    """spec.md §2.2/§12.2/RC-39 — obrigatório via ambiente/`.env`, sem
    fallback funcional hardcoded no repositório (T-77). Sem essa variável, a
    própria construção de `Settings()` falha (`pydantic.ValidationError`) no
    import de `app.config` — o processo (uvicorn ou script) não sobe, em vez
    de subir silenciosamente com um segredo previsível."""
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30

    login_failure_window_seconds: int = 300
    login_max_failures: int = 3
    login_block_seconds: int = 1800

    rate_limit_read_per_minute: int = 100
    rate_limit_write_per_minute: int = 30

    reference_cache_ttl_seconds: float = 60.0
    """spec.md §13/RC-29 — TTL do cache local de cargos/departamentos/
    centros de custo. Nunca usado para senha/JWT/aprovação/BOLA."""

    max_body_bytes: int = 100_000
    """spec.md §12.5/plan.md §15 — limite de tamanho para payloads de
    escrita (100 KB é folgado para os payloads do MVP; existe para barrar
    corpos anormalmente grandes, não para acomodar uploads)."""

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.database_path}"


settings = Settings()
