"""`python -m app.security.reset_lockouts` — spec.md §12.3/plan.md §6.6.

Remove somente os bloqueios de força bruta (`SecurityLockout`). Não altera
usuários, movimentações, aprovações nem qualquer outra tabela.
"""

from __future__ import annotations

from app.database import SessionLocal
from app.repositories import security_lockout_repository as lockout_repo


def main() -> None:
    session = SessionLocal()
    try:
        total = lockout_repo.resetar_todos(session)
        print(f"Lockouts removidos: {total}.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
