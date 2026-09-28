"""CRUD de procedimentos — catálogo de serviços da clínica (Sprint 9)."""
from datetime import datetime
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from database import get_db_dependency
from models import AcaoAudit, Clinica, Procedimento
from core.deps import audit_context, clinica_atual, requer_clinica_ativa
from core import audit

router = APIRouter(prefix="/api/procedimentos", tags=["procedimentos"])


class ProcedimentoIn(BaseModel):
    nome: str = Field(..., min_length=2, max_length=120)
    descricao: str | None = Field(None, max_length=5000)
    preco: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    duracao_minutos: int = Field(30, ge=5, le=480)
    cor: str = Field("#E8B4B8", pattern=r"^#[0-9A-Fa-f]{6}$")

    @field_validator("nome")
    @classmethod
    def nome_nao_vazio(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Nome do serviço não pode ser vazio")
        return value


class ProcedimentoUpdate(BaseModel):
    nome: str | None = Field(None, min_length=2, max_length=120)
    descricao: str | None = Field(None, max_length=5000)
    preco: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    duracao_minutos: int | None = Field(None, ge=5, le=480)
    cor: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    ativo: bool | None = None

    @field_validator("nome")
    @classmethod
    def nome_nao_vazio(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Nome do serviço não pode ser vazio")
        return value.strip() if value is not None else None


class ProcedimentoOut(BaseModel):
    id: str
    nome: str
    descricao: str | None = None
    preco: Decimal | None = None
    duracao_minutos: int
    cor: str
    ativo: bool
    criado_em: datetime

    class Config:
        from_attributes = True


@router.get("", response_model=list[ProcedimentoOut])
def listar(
    apenas_ativos: bool = True,
    clinica: Clinica = Depends(clinica_atual),
    db: Session = Depends(get_db_dependency),
):
    q = db.query(Procedimento).filter(Procedimento.clinica_id == clinica.id)
    if apenas_ativos:
        q = q.filter(Procedimento.ativo == True)
    return q.order_by(Procedimento.nome).all()


@router.post("", response_model=ProcedimentoOut, status_code=status.HTTP_201_CREATED)
def criar(
    payload: ProcedimentoIn,
    clinica: Clinica = Depends(requer_clinica_ativa),
    ctx: dict = Depends(audit_context),
    db: Session = Depends(get_db_dependency),
):
    existing = db.query(Procedimento).filter(
        Procedimento.clinica_id == clinica.id,
        Procedimento.nome.ilike(payload.nome.strip()),
    ).first()
    if existing:
        raise HTTPException(409, "Já existe um procedimento com esse nome")
    proc = Procedimento(
        clinica_id=clinica.id,
        nome=payload.nome.strip(),
        descricao=payload.descricao,
        preco=payload.preco,
        duracao_minutos=payload.duracao_minutos,
        cor=payload.cor,
    )
    db.add(proc)
    audit.log(db, **ctx, acao=AcaoAudit.CREATE, recurso="procedimento", recurso_id=proc.id,
              detalhes={"nome": proc.nome})
    db.commit()
    db.refresh(proc)
    return proc


@router.put("/{proc_id}", response_model=ProcedimentoOut)
def atualizar(
    proc_id: str,
    payload: ProcedimentoUpdate,
    clinica: Clinica = Depends(requer_clinica_ativa),
    ctx: dict = Depends(audit_context),
    db: Session = Depends(get_db_dependency),
):
    proc = db.query(Procedimento).filter(
        Procedimento.id == proc_id,
        Procedimento.clinica_id == clinica.id,
    ).first()
    if not proc:
        raise HTTPException(404, "Procedimento não encontrado")
    if payload.nome is not None:
        proc.nome = payload.nome.strip()
    if "descricao" in payload.model_fields_set:
        proc.descricao = payload.descricao
    if "preco" in payload.model_fields_set:
        proc.preco = payload.preco
    if payload.duracao_minutos is not None:
        proc.duracao_minutos = payload.duracao_minutos
    if payload.cor is not None:
        proc.cor = payload.cor
    if payload.ativo is not None:
        proc.ativo = payload.ativo
    audit.log(db, **ctx, acao=AcaoAudit.UPDATE, recurso="procedimento", recurso_id=proc.id,
              detalhes=payload.model_dump(exclude_none=True, mode="json"))
    db.commit()
    db.refresh(proc)
    return proc


@router.delete("/{proc_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(
    proc_id: str,
    clinica: Clinica = Depends(requer_clinica_ativa),
    ctx: dict = Depends(audit_context),
    db: Session = Depends(get_db_dependency),
):
    proc = db.query(Procedimento).filter(
        Procedimento.id == proc_id,
        Procedimento.clinica_id == clinica.id,
    ).first()
    if not proc:
        raise HTTPException(404, "Procedimento não encontrado")
    audit.log(db, **ctx, acao=AcaoAudit.DELETE, recurso="procedimento", recurso_id=proc.id,
              detalhes={"nome": proc.nome})
    # A service can be referenced by appointments, team assignments and old
    # conversations. Preserve the catalog row and all historical references.
    proc.ativo = False
    db.commit()
