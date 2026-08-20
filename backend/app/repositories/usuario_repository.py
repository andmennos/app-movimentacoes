from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Usuario


def buscar_por_username(session: Session, username: str) -> Usuario | None:
    consulta = select(Usuario).where(Usuario.username == username)
    return session.scalars(consulta).one_or_none()


def buscar_por_id(session: Session, usuario_id: int) -> Usuario | None:
    return session.get(Usuario, usuario_id)
