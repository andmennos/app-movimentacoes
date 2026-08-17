from pathlib import Path

from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    database_path: Path = BASE_DIR / "portal_mobilidade.db"
    pagina_tamanho_default: int = 20
    pagina_tamanho_maximo: int = 100
    ciclo_limite_profundidade: int = 100
    versao_motor: str = "1.0.0"

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.database_path}"


settings = Settings()
