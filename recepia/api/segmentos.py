"""Recurring entities required by pet care, auto repair and hotels."""

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core import audit
from core.deps import audit_context, clinica_atual, requer_clinica_ativa
from database import get_db_dependency
from models import (
    AcaoAudit,
    Clinica,
    OrdemServico,
    Paciente,
    Pet,
    Procedimento,
    Quarto,
    ReservaHotel,
    Veiculo,
)
from services.availability import bloquear_agenda_tenant
from services.hotel import reservation_conflict

router = APIRouter(prefix="/api", tags=["segmentos"])


def _only(clinica: Clinica, *types: str) -> None:
    if clinica.tipo_negocio not in types:
        raise HTTPException(404, "Módulo indisponível neste segmento")


def _customer(db: Session, clinica: Clinica, customer_id: str) -> Paciente:
    customer = db.query(Paciente).filter(
        Paciente.id == customer_id,
        Paciente.clinica_id == clinica.id,
        Paciente.deletado_em.is_(None),
    ).first()
    if customer is None:
        raise HTTPException(404, "Cliente não encontrado nesta empresa")
    return customer


def _item(db: Session, model, clinica: Clinica, item_id: str):
    item = db.query(model).filter(model.id == item_id, model.clinica_id == clinica.id).first()
    if item is None:
        raise HTTPException(404, "Registro não encontrado")
    return item


def _today(clinica: Clinica) -> date:
    return datetime.now(ZoneInfo(clinica.timezone)).date()


class PetIn(BaseModel):
    paciente_id: str
    nome: str = Field(min_length=1, max_length=120)
    especie: str = Field(min_length=1, max_length=80)
    raca: str | None = Field(None, max_length=80)
    porte: str | None = Field(None, max_length=30)
    idade_anos: int | None = Field(None, ge=0, le=100)
    observacoes: str | None = Field(None, max_length=5000)


class PetUpdate(BaseModel):
    nome: str | None = Field(None, min_length=1, max_length=120)
    especie: str | None = Field(None, min_length=1, max_length=80)
    raca: str | None = Field(None, max_length=80)
    porte: str | None = Field(None, max_length=30)
    idade_anos: int | None = Field(None, ge=0, le=100)
    observacoes: str | None = Field(None, max_length=5000)
    ativo: bool | None = None


class PetOut(PetIn):
    model_config = ConfigDict(from_attributes=True)

    id: str
    ativo: bool
    criado_em: datetime


@router.get("/pets", response_model=list[PetOut])
def listar_pets(
    paciente_id: str | None = None,
    apenas_ativos: bool = True,
    clinica: Clinica = Depends(clinica_atual),
    db: Session = Depends(get_db_dependency),
):
    _only(clinica, "PET")
    query = db.query(Pet).filter(Pet.clinica_id == clinica.id)
    if paciente_id:
        query = query.filter(Pet.paciente_id == paciente_id)
    if apenas_ativos:
        query = query.filter(Pet.ativo.is_(True))
    return query.order_by(Pet.nome).all()


@router.post("/pets", response_model=PetOut, status_code=status.HTTP_201_CREATED)
def criar_pet(
    payload: PetIn,
    clinica: Clinica = Depends(requer_clinica_ativa),
    ctx: dict = Depends(audit_context),
    db: Session = Depends(get_db_dependency),
):
    _only(clinica, "PET")
    _customer(db, clinica, payload.paciente_id)
    pet = Pet(clinica_id=clinica.id, **payload.model_dump())
    db.add(pet)
    db.flush()
    audit.log(db, **ctx, acao=AcaoAudit.CREATE, recurso="pet", recurso_id=pet.id,
              detalhes={"nome": pet.nome})
    db.commit()
    db.refresh(pet)
    return pet


@router.put("/pets/{item_id}", response_model=PetOut)
def atualizar_pet(
    item_id: str,
    payload: PetUpdate,
    clinica: Clinica = Depends(requer_clinica_ativa),
    ctx: dict = Depends(audit_context),
    db: Session = Depends(get_db_dependency),
):
    _only(clinica, "PET")
    pet = _item(db, Pet, clinica, item_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        if key in {"nome", "especie"} and value is None:
            raise HTTPException(422, f"{key} não pode ser nulo")
        setattr(pet, key, value)
    audit.log(db, **ctx, acao=AcaoAudit.UPDATE, recurso="pet", recurso_id=pet.id,
              detalhes={"campos": sorted(payload.model_fields_set)})
    db.commit()
    db.refresh(pet)
    return pet


@router.delete("/pets/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_pet(
    item_id: str,
    clinica: Clinica = Depends(requer_clinica_ativa),
    ctx: dict = Depends(audit_context),
    db: Session = Depends(get_db_dependency),
):
    _only(clinica, "PET")
    pet = _item(db, Pet, clinica, item_id)
    pet.ativo = False
    audit.log(db, **ctx, acao=AcaoAudit.DELETE, recurso="pet", recurso_id=pet.id,
              detalhes={"soft_delete": True})
    db.commit()


_ORDER_TRANSITIONS = {
    "ABERTA": {"EM_ANDAMENTO", "CONCLUIDA", "CANCELADA"},
    "EM_ANDAMENTO": {"CONCLUIDA", "CANCELADA"},
    "CONCLUIDA": set(),
    "CANCELADA": set(),
}


class OrdemIn(BaseModel):
    paciente_id: str
    veiculo_id: str
    procedimento_id: str | None = None
    descricao: str = Field(min_length=2, max_length=5000)
    valor: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    observacoes: str | None = Field(None, max_length=5000)


class OrdemUpdate(BaseModel):
    procedimento_id: str | None = None
    descricao: str | None = Field(None, min_length=2, max_length=5000)
    status: str | None = None
    valor: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    observacoes: str | None = Field(None, max_length=5000)


class OrdemOut(OrdemIn):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    criado_em: datetime
    atualizado_em: datetime


def _order_refs(db: Session, clinica: Clinica, cliente_id: str,
                veiculo_id: str, servico_id: str | None) -> None:
    _customer(db, clinica, cliente_id)
    vehicle = db.query(Veiculo).filter(
        Veiculo.id == veiculo_id, Veiculo.clinica_id == clinica.id,
        Veiculo.paciente_id == cliente_id, Veiculo.ativo.is_(True),
    ).first()
    if vehicle is None:
        raise HTTPException(404, "Veículo não encontrado para este cliente")
    if servico_id:
        service = db.query(Procedimento).filter(
            Procedimento.id == servico_id,
            Procedimento.clinica_id == clinica.id,
            Procedimento.ativo.is_(True),
        ).first()
        if service is None:
            raise HTTPException(404, "Serviço não encontrado nesta empresa")


@router.get("/ordens-servico", response_model=list[OrdemOut])
def listar_ordens(
    clinica: Clinica = Depends(clinica_atual),
    db: Session = Depends(get_db_dependency),
):
    _only(clinica, "AUTO_REPAIR")
    return db.query(OrdemServico).filter(OrdemServico.clinica_id == clinica.id).order_by(
        OrdemServico.criado_em.desc()
    ).all()


@router.post("/ordens-servico", response_model=OrdemOut, status_code=status.HTTP_201_CREATED)
def criar_ordem(
    payload: OrdemIn,
    clinica: Clinica = Depends(requer_clinica_ativa),
    ctx: dict = Depends(audit_context),
    db: Session = Depends(get_db_dependency),
):
    _only(clinica, "AUTO_REPAIR")
    _order_refs(db, clinica, payload.paciente_id, payload.veiculo_id, payload.procedimento_id)
    order = OrdemServico(clinica_id=clinica.id, **payload.model_dump())
    db.add(order)
    db.flush()
    audit.log(db, **ctx, acao=AcaoAudit.CREATE, recurso="ordem_servico", recurso_id=order.id,
              detalhes={"veiculo_id": order.veiculo_id})
    db.commit()
    db.refresh(order)
    return order


@router.patch("/ordens-servico/{item_id}", response_model=OrdemOut)
def atualizar_ordem(
    item_id: str,
    payload: OrdemUpdate,
    clinica: Clinica = Depends(requer_clinica_ativa),
    ctx: dict = Depends(audit_context),
    db: Session = Depends(get_db_dependency),
):
    _only(clinica, "AUTO_REPAIR")
    order = _item(db, OrdemServico, clinica, item_id)
    if payload.status and payload.status != order.status:
        if payload.status not in _ORDER_TRANSITIONS.get(order.status, set()):
            raise HTTPException(400, "Transição de ordem inválida")
    if payload.procedimento_id:
        _order_refs(db, clinica, order.paciente_id, order.veiculo_id, payload.procedimento_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        if key in {"descricao", "status"} and value is None:
            raise HTTPException(422, f"{key} não pode ser nulo")
        setattr(order, key, value)
    audit.log(db, **ctx, acao=AcaoAudit.UPDATE, recurso="ordem_servico", recurso_id=order.id,
              detalhes=payload.model_dump(exclude_unset=True, mode="json"))
    db.commit()
    db.refresh(order)
    return order


_ROOM_STATUSES = {"DISPONIVEL", "MANUTENCAO"}
_RESERVATION_TRANSITIONS = {
    "RESERVADA": {"CHECK_IN", "CANCELADA"},
    "CHECK_IN": {"CHECK_OUT"},
    "CHECK_OUT": set(),
    "CANCELADA": set(),
}


class QuartoIn(BaseModel):
    numero: str = Field(min_length=1, max_length=50)
    categoria: str | None = Field(None, max_length=80)
    capacidade: int = Field(1, ge=1, le=30)
    status: str = "DISPONIVEL"
    valor_diaria: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)

    @model_validator(mode="after")
    def validar_status(self):
        if self.status not in _ROOM_STATUSES:
            raise ValueError("Status do quarto inválido")
        self.numero = self.numero.strip()
        if not self.numero:
            raise ValueError("Número do quarto obrigatório")
        return self


class QuartoUpdate(BaseModel):
    numero: str | None = Field(None, min_length=1, max_length=50)
    categoria: str | None = Field(None, max_length=80)
    capacidade: int | None = Field(None, ge=1, le=30)
    status: str | None = None
    valor_diaria: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    ativo: bool | None = None

    @model_validator(mode="after")
    def validar_status(self):
        if self.status is not None and self.status not in _ROOM_STATUSES:
            raise ValueError("Status do quarto inválido")
        if self.numero is not None:
            self.numero = self.numero.strip()
            if not self.numero:
                raise ValueError("Número do quarto obrigatório")
        return self


class QuartoOut(QuartoIn):
    model_config = ConfigDict(from_attributes=True)

    id: str
    ativo: bool
    criado_em: datetime


def _room(db: Session, clinica: Clinica, room_id: str, *, available: bool = False) -> Quarto:
    room = _item(db, Quarto, clinica, room_id)
    if available and (not room.ativo or room.status == "MANUTENCAO"):
        raise HTTPException(409, "Quarto indisponível")
    return room


@router.get("/quartos", response_model=list[QuartoOut])
def listar_quartos(
    apenas_ativos: bool = True,
    clinica: Clinica = Depends(clinica_atual),
    db: Session = Depends(get_db_dependency),
):
    _only(clinica, "HOTEL")
    query = db.query(Quarto).filter(Quarto.clinica_id == clinica.id)
    if apenas_ativos:
        query = query.filter(Quarto.ativo.is_(True))
    return query.order_by(Quarto.numero).all()


@router.post("/quartos", response_model=QuartoOut, status_code=status.HTTP_201_CREATED)
def criar_quarto(
    payload: QuartoIn,
    clinica: Clinica = Depends(requer_clinica_ativa),
    ctx: dict = Depends(audit_context),
    db: Session = Depends(get_db_dependency),
):
    _only(clinica, "HOTEL")
    room = Quarto(clinica_id=clinica.id, **payload.model_dump())
    db.add(room)
    try:
        db.flush()
        audit.log(db, **ctx, acao=AcaoAudit.CREATE, recurso="quarto", recurso_id=room.id,
                  detalhes={"numero": room.numero})
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Quarto já cadastrado") from exc
    db.refresh(room)
    return room


@router.put("/quartos/{item_id}", response_model=QuartoOut)
def atualizar_quarto(
    item_id: str,
    payload: QuartoUpdate,
    clinica: Clinica = Depends(requer_clinica_ativa),
    ctx: dict = Depends(audit_context),
    db: Session = Depends(get_db_dependency),
):
    _only(clinica, "HOTEL")
    room = _room(db, clinica, item_id)
    if payload.status == "MANUTENCAO" or payload.ativo is False:
        active = db.query(ReservaHotel).filter(
            ReservaHotel.clinica_id == clinica.id,
            ReservaHotel.quarto_id == item_id,
            ReservaHotel.status.in_(("RESERVADA", "CHECK_IN")),
            ReservaHotel.check_out > _today(clinica),
        ).first()
        if active:
            raise HTTPException(409, "Quarto possui reserva ativa")
    for key, value in payload.model_dump(exclude_unset=True).items():
        if key in {"numero", "capacidade", "status", "ativo"} and value is None:
            raise HTTPException(422, f"{key} não pode ser nulo")
        setattr(room, key, value)
    audit.log(db, **ctx, acao=AcaoAudit.UPDATE, recurso="quarto", recurso_id=room.id,
              detalhes=payload.model_dump(exclude_unset=True, mode="json"))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Quarto já cadastrado") from exc
    db.refresh(room)
    return room


@router.delete("/quartos/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_quarto(
    item_id: str,
    clinica: Clinica = Depends(requer_clinica_ativa),
    ctx: dict = Depends(audit_context),
    db: Session = Depends(get_db_dependency),
):
    _only(clinica, "HOTEL")
    room = _room(db, clinica, item_id)
    active = db.query(ReservaHotel).filter(
        ReservaHotel.clinica_id == clinica.id,
        ReservaHotel.quarto_id == item_id,
        ReservaHotel.status.in_(("RESERVADA", "CHECK_IN")),
        ReservaHotel.check_out > _today(clinica),
    ).first()
    if active:
        raise HTTPException(409, "Quarto possui reserva ativa")
    room.ativo = False
    audit.log(db, **ctx, acao=AcaoAudit.DELETE, recurso="quarto", recurso_id=room.id,
              detalhes={"soft_delete": True})
    db.commit()


class ReservaIn(BaseModel):
    paciente_id: str
    quarto_id: str
    check_in: date
    check_out: date
    observacoes: str | None = Field(None, max_length=5000)

    @model_validator(mode="after")
    def validar_datas(self):
        if self.check_out <= self.check_in:
            raise ValueError("Check-out deve ser após o check-in")
        return self


class ReservaUpdate(BaseModel):
    quarto_id: str | None = None
    check_in: date | None = None
    check_out: date | None = None
    status: str | None = None
    observacoes: str | None = Field(None, max_length=5000)


class ReservaOut(ReservaIn):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    valor_previsto: Decimal | None
    criado_em: datetime


@router.get("/reservas-hotel", response_model=list[ReservaOut])
def listar_reservas(
    clinica: Clinica = Depends(clinica_atual),
    db: Session = Depends(get_db_dependency),
):
    _only(clinica, "HOTEL")
    return db.query(ReservaHotel).filter(ReservaHotel.clinica_id == clinica.id).order_by(
        ReservaHotel.check_in.desc()
    ).all()


@router.post("/reservas-hotel", response_model=ReservaOut, status_code=status.HTTP_201_CREATED)
def criar_reserva(
    payload: ReservaIn,
    clinica: Clinica = Depends(requer_clinica_ativa),
    ctx: dict = Depends(audit_context),
    db: Session = Depends(get_db_dependency),
):
    _only(clinica, "HOTEL")
    _customer(db, clinica, payload.paciente_id)
    if payload.check_in < _today(clinica):
        raise HTTPException(422, "Check-in não pode ser no passado")
    bloquear_agenda_tenant(db, clinica.id)
    room = _room(db, clinica, payload.quarto_id, available=True)
    if reservation_conflict(db, clinica.id, room.id, payload.check_in, payload.check_out):
        raise HTTPException(409, "Quarto ocupado neste período")
    nights = (payload.check_out - payload.check_in).days
    reservation = ReservaHotel(
        clinica_id=clinica.id, **payload.model_dump(),
        valor_previsto=room.valor_diaria * nights if room.valor_diaria is not None else None,
    )
    db.add(reservation)
    db.flush()
    audit.log(db, **ctx, acao=AcaoAudit.CREATE, recurso="reserva_hotel",
              recurso_id=reservation.id, detalhes={"quarto_id": room.id})
    db.commit()
    db.refresh(reservation)
    return reservation


@router.patch("/reservas-hotel/{item_id}", response_model=ReservaOut)
def atualizar_reserva(
    item_id: str,
    payload: ReservaUpdate,
    clinica: Clinica = Depends(requer_clinica_ativa),
    ctx: dict = Depends(audit_context),
    db: Session = Depends(get_db_dependency),
):
    _only(clinica, "HOTEL")
    bloquear_agenda_tenant(db, clinica.id)
    reservation = _item(db, ReservaHotel, clinica, item_id)
    if payload.status is not None:
        if payload.status not in _RESERVATION_TRANSITIONS.get(reservation.status, set()):
            raise HTTPException(400, "Transição de reserva inválida")
    changed_dates = any(key in payload.model_fields_set for key in ("quarto_id", "check_in", "check_out"))
    if changed_dates and reservation.status != "RESERVADA":
        raise HTTPException(409, "Datas só podem ser alteradas antes do check-in")
    room_id = payload.quarto_id or reservation.quarto_id
    check_in = payload.check_in or reservation.check_in
    check_out = payload.check_out or reservation.check_out
    if check_out <= check_in:
        raise HTTPException(422, "Check-out deve ser após o check-in")
    if changed_dates and check_in < _today(clinica):
        raise HTTPException(422, "Check-in não pode ser no passado")
    room = _room(db, clinica, room_id, available=changed_dates)
    if changed_dates and reservation_conflict(db, clinica.id, room_id, check_in, check_out, item_id):
        raise HTTPException(409, "Quarto ocupado neste período")
    for key, value in payload.model_dump(exclude_unset=True).items():
        if key in {"quarto_id", "check_in", "check_out", "status"} and value is None:
            raise HTTPException(422, f"{key} não pode ser nulo")
        setattr(reservation, key, value)
    if changed_dates:
        nights = (check_out - check_in).days
        reservation.valor_previsto = (
            room.valor_diaria * nights if room.valor_diaria is not None else None
        )
    audit.log(db, **ctx, acao=AcaoAudit.UPDATE, recurso="reserva_hotel",
              recurso_id=reservation.id,
              detalhes=payload.model_dump(exclude_unset=True, mode="json"))
    db.commit()
    db.refresh(reservation)
    return reservation
