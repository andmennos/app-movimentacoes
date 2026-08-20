"""Catálogos de referência — spec.md §15 (`GET /referencias/*`). Somente
leitura de listas pequenas e estáveis; candidatas ao cache local de T-68."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Cargo, CentroCusto, Departamento, EstruturaOrganizacional


def listar_cargos(session: Session) -> list[Cargo]:
    return list(session.scalars(select(Cargo).order_by(Cargo.nome)))


def listar_departamentos(session: Session) -> list[Departamento]:
    return list(session.scalars(select(Departamento).order_by(Departamento.nome)))


def listar_centros_custo(session: Session) -> list[CentroCusto]:
    return list(session.scalars(select(CentroCusto).order_by(CentroCusto.nome)))


def listar_estruturas(session: Session) -> list[EstruturaOrganizacional]:
    return list(session.scalars(select(EstruturaOrganizacional).order_by(EstruturaOrganizacional.nome)))
