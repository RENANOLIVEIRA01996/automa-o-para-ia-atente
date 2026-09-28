"""Tenant-scoped vehicles for car wash and auto repair."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core import audit
from core.deps import audit_context, clinica_atual, requer_clinica_ativa
from core.vehicles import normalize_plate
from database import get_db_dependency
from models import AcaoAudit, Clinica, Paciente, Veiculo

router = APIRouter(prefix="/api/veiculos", tags=["veiculos"])


class VeiculoIn(BaseModel):
    paciente_id: str
    placa: str = Field(..., min_length=7, max_length=8)
    marca: str | None = Field(None, max_length=80)
    modelo: str | None = Field(None, max_length=80)
    ano: int | None = Field(None, ge=1900, le=2100)
    cor: str | None = Field(None, max_length=40)
    km: int | None = Field(None, ge=0)
    observacoes: str | None = Field(None, max_length=5000)

    @field_validator("placa")
    @classmethod
    def normalizar_placa(cls, value: str) -> str:
        return normalize_plate(value)


class VeiculoUpdate(BaseModel):
    paciente_id: str | None = None
    placa: str | None = Field(None, min_length=7, max_length=8)
    marca: str | None = Field(None, max_length=80)
    modelo: str | None = Field(None, max_length=80)
    ano: int | None = Field(None, ge=1900, le=2100)
    cor: str | None = Field(None, max_length=40)
    km: int | None = Field(None, ge=0)
    observacoes: str | None = Field(None, max_length=5000)
    ativo: bool | None = None

    @field_validator("placa")
    @classmethod
    def normalizar_placa(cls, value: str | None) -> str | None:
        return normalize_plate(value) if value is not None else None


class VeiculoOut(BaseModel):
    id: str
    paciente_id: str
    placa: str
    marca: str | None
    modelo: str | None
    ano: int | None
    cor: str | None
    km: int | None
    observacoes: str | None
    ativo: bool
    criado_em: datetime

    class Config:
        from_attributes = True


def _segmento_permitido(clinica: Clinica) -> None:
    if clinica.tipo_negocio not in {"CAR_WASH", "AUTO_REPAIR"}:
        raise HTTPException(404, "Módulo de veículos indisponível")


def _cliente(db: Session, clinica: Clinica, paciente_id: str) -> Paciente:
    cliente = (
        db.query(Paciente)
        .filter(
            Paciente.id == paciente_id,
            Paciente.clinica_id == clinica.id,
            Paciente.deletado_em.is_(None),
        )
        .first()
    )
    if cliente is None:
        raise HTTPException(404, "Cliente não encontrado nesta empresa")
    return cliente


def _veiculo(db: Session, clinica: Clinica, veiculo_id: str) -> Veiculo:
    veiculo = (
        db.query(Veiculo)
        .filter(
            Veiculo.id == veiculo_id,
            Veiculo.clinica_id == clinica.id,
        )
        .first()
    )
    if veiculo is None:
        raise HTTPException(404, "Veículo não encontrado")
    return veiculo


@router.get("", response_model=list[VeiculoOut])
def listar(
    paciente_id: str | None = None,
    apenas_ativos: bool = True,
    clinica: Clinica = Depends(clinica_atual),
    db: Session = Depends(get_db_dependency),
):
    _segmento_permitido(clinica)
    query = db.query(Veiculo).filter(Veiculo.clinica_id == clinica.id)
    if paciente_id:
        query = query.filter(Veiculo.paciente_id == paciente_id)
    if apenas_ativos:
        query = query.filter(Veiculo.ativo.is_(True))
    return query.order_by(Veiculo.placa).all()


@router.post("", response_model=VeiculoOut, status_code=status.HTTP_201_CREATED)
def criar(
    payload: VeiculoIn,
    clinica: Clinica = Depends(requer_clinica_ativa),
    ctx: dict = Depends(audit_context),
    db: Session = Depends(get_db_dependency),
):
    _segmento_permitido(clinica)
    _cliente(db, clinica, payload.paciente_id)
    item = Veiculo(clinica_id=clinica.id, **payload.model_dump())
    db.add(item)
    try:
        db.flush()
        audit.log(
            db,
            **ctx,
            acao=AcaoAudit.CREATE,
            recurso="veiculo",
            recurso_id=item.id,
            detalhes={"placa": item.placa},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Placa já cadastrada nesta empresa") from exc
    db.refresh(item)
    return item


@router.put("/{veiculo_id}", response_model=VeiculoOut)
def atualizar(
    veiculo_id: str,
    payload: VeiculoUpdate,
    clinica: Clinica = Depends(requer_clinica_ativa),
    ctx: dict = Depends(audit_context),
    db: Session = Depends(get_db_dependency),
):
    _segmento_permitido(clinica)
    item = _veiculo(db, clinica, veiculo_id)
    if payload.paciente_id is not None:
        _cliente(db, clinica, payload.paciente_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        if key in {"paciente_id", "placa"} and value is None:
            raise HTTPException(422, f"{key} não pode ser nulo")
        setattr(item, key, value)
    audit.log(
        db,
        **ctx,
        acao=AcaoAudit.UPDATE,
        recurso="veiculo",
        recurso_id=item.id,
        detalhes={"campos": sorted(payload.model_fields_set)},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Placa já cadastrada nesta empresa") from exc
    db.refresh(item)
    return item


@router.delete("/{veiculo_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(
    veiculo_id: str,
    clinica: Clinica = Depends(requer_clinica_ativa),
    ctx: dict = Depends(audit_context),
    db: Session = Depends(get_db_dependency),
):
    _segmento_permitido(clinica)
    item = _veiculo(db, clinica, veiculo_id)
    item.ativo = False
    audit.log(
        db,
        **ctx,
        acao=AcaoAudit.DELETE,
        recurso="veiculo",
        recurso_id=item.id,
        detalhes={"placa": item.placa, "soft_delete": True},
    )
    db.commit()
