"""Consulta de disponibilidade real e jornada por profissional."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from core.deps import clinica_atual, requer_clinica_ativa
from database import get_db_dependency
from models import (
    Clinica,
    HorarioProfissional,
    Procedimento,
    Profissional,
    ProfissionalProcedimento,
)
from services.availability import slots_disponiveis

router = APIRouter(prefix="/api/agenda", tags=["agenda"])


@router.get("/slots")
def consultar_slots(
    procedimento_id: str,
    data: date,
    profissional_id: str | None = None,
    clinica: Clinica = Depends(clinica_atual),
    db: Session = Depends(get_db_dependency),
):
    procedimento = (
        db.query(Procedimento)
        .filter(
            Procedimento.id == procedimento_id,
            Procedimento.clinica_id == clinica.id,
        )
        .first()
    )
    if procedimento is None:
        raise HTTPException(404, "Serviço não encontrado")
    try:
        slots = slots_disponiveis(db, clinica, procedimento, data, profissional_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {
        "data": data.isoformat(),
        "timezone": clinica.timezone,
        "slots_utc": [item.isoformat() + "Z" for item in slots],
    }


class JornadaIn(BaseModel):
    hora_inicio: str = Field(..., pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    hora_fim: str = Field(..., pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    ativo: bool = True

    @model_validator(mode="after")
    def ordem(self):
        if self.hora_inicio >= self.hora_fim:
            raise ValueError("hora_inicio deve ser antes de hora_fim")
        return self


@router.get("/profissionais/{profissional_id}/horarios")
def listar_jornadas(
    profissional_id: str,
    clinica: Clinica = Depends(clinica_atual),
    db: Session = Depends(get_db_dependency),
):
    profissional = db.query(Profissional).filter(
        Profissional.id == profissional_id,
        Profissional.clinica_id == clinica.id,
    ).first()
    if profissional is None:
        raise HTTPException(404, "Profissional não encontrado")
    rows = db.query(HorarioProfissional).filter(
        HorarioProfissional.clinica_id == clinica.id,
        HorarioProfissional.profissional_id == profissional_id,
    ).order_by(HorarioProfissional.dia_semana).all()
    return [
        {
            "dia_semana": row.dia_semana,
            "hora_inicio": row.hora_inicio,
            "hora_fim": row.hora_fim,
            "ativo": row.ativo,
        }
        for row in rows
    ]


@router.put("/profissionais/{profissional_id}/horarios/{dia_semana}")
def definir_jornada(
    profissional_id: str,
    dia_semana: int,
    payload: JornadaIn,
    clinica: Clinica = Depends(requer_clinica_ativa),
    db: Session = Depends(get_db_dependency),
):
    if dia_semana not in range(7):
        raise HTTPException(422, "Dia da semana inválido")
    profissional = (
        db.query(Profissional)
        .filter(
            Profissional.id == profissional_id,
            Profissional.clinica_id == clinica.id,
        )
        .first()
    )
    if profissional is None:
        raise HTTPException(404, "Profissional não encontrado")
    jornada = (
        db.query(HorarioProfissional)
        .filter(
            HorarioProfissional.clinica_id == clinica.id,
            HorarioProfissional.profissional_id == profissional_id,
            HorarioProfissional.dia_semana == dia_semana,
        )
        .first()
    )
    if jornada is None:
        jornada = HorarioProfissional(
            clinica_id=clinica.id,
            profissional_id=profissional_id,
            dia_semana=dia_semana,
        )
        db.add(jornada)
    jornada.hora_inicio = payload.hora_inicio
    jornada.hora_fim = payload.hora_fim
    jornada.ativo = payload.ativo
    db.commit()
    return {
        "profissional_id": profissional_id,
        "dia_semana": dia_semana,
        **payload.model_dump(),
    }


class ServicosProfissionalIn(BaseModel):
    procedimento_ids: list[str] = Field(default_factory=list, max_length=100)


@router.get("/profissionais/{profissional_id}/servicos")
def listar_servicos_profissional(
    profissional_id: str,
    clinica: Clinica = Depends(clinica_atual),
    db: Session = Depends(get_db_dependency),
):
    profissional = db.query(Profissional).filter(
        Profissional.id == profissional_id,
        Profissional.clinica_id == clinica.id,
    ).first()
    if profissional is None:
        raise HTTPException(404, "Profissional não encontrado")
    rows = db.query(ProfissionalProcedimento).filter(
        ProfissionalProcedimento.clinica_id == clinica.id,
        ProfissionalProcedimento.profissional_id == profissional_id,
    ).all()
    return {"profissional_id": profissional_id,
            "procedimento_ids": sorted(row.procedimento_id for row in rows)}


@router.put("/profissionais/{profissional_id}/servicos")
def definir_servicos_profissional(
    profissional_id: str,
    payload: ServicosProfissionalIn,
    clinica: Clinica = Depends(requer_clinica_ativa),
    db: Session = Depends(get_db_dependency),
):
    profissional = (
        db.query(Profissional)
        .filter(
            Profissional.id == profissional_id,
            Profissional.clinica_id == clinica.id,
        )
        .first()
    )
    if profissional is None:
        raise HTTPException(404, "Profissional não encontrado")
    ids = set(payload.procedimento_ids)
    servicos = (
        db.query(Procedimento)
        .filter(
            Procedimento.clinica_id == clinica.id,
            Procedimento.id.in_(ids),
        )
        .all()
        if ids
        else []
    )
    if {s.id for s in servicos} != ids:
        raise HTTPException(404, "Serviço não encontrado nesta empresa")
    db.query(ProfissionalProcedimento).filter(
        ProfissionalProcedimento.clinica_id == clinica.id,
        ProfissionalProcedimento.profissional_id == profissional_id,
    ).delete(synchronize_session=False)
    for servico_id in ids:
        db.add(
            ProfissionalProcedimento(
                clinica_id=clinica.id,
                profissional_id=profissional_id,
                procedimento_id=servico_id,
            )
        )
    db.commit()
    return {"profissional_id": profissional_id, "procedimento_ids": sorted(ids)}
