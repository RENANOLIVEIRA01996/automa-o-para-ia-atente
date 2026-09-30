"""Ferramentas do agente com tenant e cliente vindos do webhook."""

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.vehicles import normalize_plate
from core.phones import tenta_normalizar
from models import (
    Agendamento,
    Clinica,
    ConfiguracaoNegocio,
    Conversa,
    HorarioFuncionamento,
    Paciente,
    Pet,
    Procedimento,
    Profissional,
    Quarto,
    ReservaHotel,
    Status,
    Veiculo,
)
from services.availability import bloquear_agenda_tenant, ha_conflito, slots_disponiveis
from services.hotel import reservation_conflict

log = logging.getLogger("recepia.ai.tools")


@dataclass
class ToolContext:
    db: Session
    clinica: Clinica
    paciente: Paciente
    conversa: Conversa


class Empty(BaseModel):
    pass


class HumanSupportIn(BaseModel):
    resumo: str | None = Field(None, max_length=300)


class ServiceId(BaseModel):
    service_id: str = Field(min_length=1, max_length=100)


class SlotsIn(ServiceId):
    date: date
    professional_id: str | None = None


class CreateIn(ServiceId):
    starts_at: datetime
    professional_id: str | None = None
    vehicle_id: str | None = None
    pet_id: str | None = None


class RegisterPetIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    species: str = Field(min_length=1, max_length=80)
    breed: str | None = Field(None, max_length=80)
    size: str | None = Field(None, max_length=30)


class HotelStayIn(BaseModel):
    check_in: date
    check_out: date

    @model_validator(mode="after")
    def validate_dates(self):
        if self.check_out <= self.check_in:
            raise ValueError("Check-out deve ser após check-in")
        return self


class HotelAvailabilityIn(HotelStayIn):
    room_id: str | None = None


class HotelBookingIn(HotelStayIn):
    room_id: str


class HotelReservationId(BaseModel):
    reservation_id: str


class RegisterVehicleIn(BaseModel):
    plate: str = Field(min_length=7, max_length=10)
    brand: str | None = Field(None, max_length=80)
    model: str | None = Field(None, max_length=80)
    year: int | None = Field(None, ge=1900, le=2100)
    color: str | None = Field(None, max_length=40)


class AppointmentId(BaseModel):
    appointment_id: str = Field(min_length=1, max_length=100)


class RescheduleIn(AppointmentId):
    starts_at: datetime


SCHEMAS: dict[str, tuple[type[BaseModel], str]] = {
    "getBusinessInfo": (Empty, "Consulta dados e regras da empresa"),
    "listServices": (Empty, "Lista serviços ativos com preços e duração"),
    "getServiceDetails": (ServiceId, "Detalhes de um serviço cadastrado"),
    "getAvailableSlots": (
        SlotsIn,
        "Consulta horários reais para um serviço e uma data local",
    ),
    "findCustomerAppointments": (Empty, "Lista agendamentos deste cliente"),
    "createAppointment": (CreateIn, "Reserva um horário real para este cliente"),
    "rescheduleAppointment": (RescheduleIn, "Remarca um agendamento deste cliente"),
    "cancelAppointment": (AppointmentId, "Cancela um agendamento deste cliente"),
    "requestHumanSupport": (HumanSupportIn, "Transfere a conversa para atendimento humano. Para vendas, informe um resumo breve do interesse."),
    "listCustomerVehicles": (Empty, "Lista os veículos cadastrados deste cliente"),
    "registerVehicle": (RegisterVehicleIn, "Cadastra o veículo deste cliente pela placa"),
    "listCustomerPets": (Empty, "Lista pets deste tutor"),
    "registerPet": (RegisterPetIn, "Cadastra um pet deste tutor"),
    "listRooms": (Empty, "Lista quartos ativos, categorias, capacidade e diárias"),
    "checkRoomAvailability": (HotelAvailabilityIn, "Consulta quartos livres entre check-in e check-out"),
    "createHotelReservation": (HotelBookingIn, "Reserva um quarto livre para este hóspede"),
    "findCustomerReservations": (Empty, "Lista reservas deste hóspede"),
    "cancelHotelReservation": (HotelReservationId, "Cancela uma reserva futura deste hóspede"),
}


def tool_definitions(business_type: str | None = None) -> list[dict]:
    vehicle_tools = {"listCustomerVehicles", "registerVehicle"}
    pet_tools = {"listCustomerPets", "registerPet"}
    hotel_tools = {"listRooms", "checkRoomAvailability", "createHotelReservation", "findCustomerReservations", "cancelHotelReservation"}
    appointment_tools = {"getAvailableSlots", "findCustomerAppointments", "createAppointment", "rescheduleAppointment", "cancelAppointment", "listServices", "getServiceDetails"}
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": schema.model_json_schema(),
            },
        }
        for name, (schema, description) in SCHEMAS.items()
        if (name not in vehicle_tools or business_type in {"CAR_WASH", "AUTO_REPAIR"})
        and (name not in pet_tools or business_type == "PET")
        and (name not in hotel_tools or business_type == "HOTEL")
        and (name not in appointment_tools or business_type != "HOTEL")
        and (business_type != "RECEPIA" or name in {"getBusinessInfo", "requestHumanSupport"})
    ]


def _service(ctx: ToolContext, service_id: str) -> Procedimento | None:
    return (
        ctx.db.query(Procedimento)
        .filter(
            Procedimento.clinica_id == ctx.clinica.id,
            Procedimento.id == service_id,
            Procedimento.ativo.is_(True),
        )
        .first()
    )


def _appointment(ctx: ToolContext, appointment_id: str) -> Agendamento | None:
    return (
        ctx.db.query(Agendamento)
        .filter(
            Agendamento.id == appointment_id,
            Agendamento.clinica_id == ctx.clinica.id,
            Agendamento.paciente_id == ctx.paciente.id,
        )
        .first()
    )


def _utc_naive(value: datetime, clinica: Clinica) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo(clinica.timezone))
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _appointment_data(item: Agendamento) -> dict:
    return {
        "id": item.id,
        "service": item.servico,
        "starts_at_utc": item.data_hora.isoformat() + "Z",
        "status": item.status,
    }


def execute_tool(name: str, raw_arguments: str, ctx: ToolContext) -> dict:
    if name not in {tool["function"]["name"] for tool in tool_definitions(ctx.clinica.tipo_negocio)}:
        return {"error": "Ferramenta não permitida"}
    schema = SCHEMAS[name][0]
    try:
        args = schema.model_validate(json.loads(raw_arguments or "{}"))
    except (ValueError, TypeError, ValidationError):
        return {"error": "Argumentos inválidos"}

    db = ctx.db
    tenant = ctx.clinica
    if name == "getBusinessInfo":
        config = (
            db.query(ConfiguracaoNegocio)
            .filter(ConfiguracaoNegocio.clinica_id == tenant.id)
            .first()
        )
        hours = (
            db.query(HorarioFuncionamento)
            .filter(
                HorarioFuncionamento.clinica_id == tenant.id,
                HorarioFuncionamento.ativo.is_(True),
            )
            .all()
        )
        return {
            "name": tenant.nome,
            "business_type": tenant.tipo_negocio,
            "phone": tenant.telefone,
            "timezone": tenant.timezone,
            "description": config.descricao if config else None,
            "cancellation_policy": config.politica_cancelamento if config else None,
            "booking_rules": config.regras_agendamento if config else None,
            "business_extras": tenant.campos_extras or {},
            "hours": [
                {"weekday": h.dia_semana, "start": h.hora_inicio, "end": h.hora_fim}
                for h in hours
            ],
        }
    if name == "listServices":
        services = (
            db.query(Procedimento)
            .filter(
                Procedimento.clinica_id == tenant.id,
                Procedimento.ativo.is_(True),
            )
            .order_by(Procedimento.nome)
            .limit(100)
            .all()
        )
        return {
            "services": [
                {
                    "id": s.id,
                    "name": s.nome,
                    "duration_minutes": s.duracao_minutos,
                    "price": str(s.preco) if s.preco is not None else None,
                }
                for s in services
            ]
        }
    if name == "getServiceDetails":
        service = _service(ctx, args.service_id)
        if not service:
            return {"error": "Serviço não encontrado"}
        return {
            "id": service.id,
            "name": service.nome,
            "description": service.descricao,
            "duration_minutes": service.duracao_minutos,
            "price": str(service.preco) if service.preco is not None else None,
        }
    if name == "getAvailableSlots":
        service = _service(ctx, args.service_id)
        if not service:
            return {"error": "Serviço não encontrado"}
        try:
            slots = slots_disponiveis(
                db, tenant, service, args.date, args.professional_id
            )
        except ValueError as exc:
            return {"error": str(exc)}
        return {
            "timezone": tenant.timezone,
            "slots_utc": [s.isoformat() + "Z" for s in slots[:20]],
        }
    if name == "findCustomerAppointments":
        items = (
            db.query(Agendamento)
            .filter(
                Agendamento.clinica_id == tenant.id,
                Agendamento.paciente_id == ctx.paciente.id,
            )
            .order_by(Agendamento.data_hora.desc())
            .limit(20)
            .all()
        )
        return {"appointments": [_appointment_data(item) for item in items]}
    if name == "listCustomerVehicles":
        if tenant.tipo_negocio not in {"CAR_WASH", "AUTO_REPAIR"}:
            return {"error": "Ferramenta indisponível neste segmento"}
        vehicles = (
            db.query(Veiculo)
            .filter(
                Veiculo.clinica_id == tenant.id,
                Veiculo.paciente_id == ctx.paciente.id,
                Veiculo.ativo.is_(True),
            )
            .order_by(Veiculo.placa)
            .all()
        )
        return {
            "vehicles": [
                {"id": v.id, "plate": v.placa, "brand": v.marca, "model": v.modelo,
                 "year": v.ano, "color": v.cor}
                for v in vehicles
            ]
        }
    if name == "registerVehicle":
        if tenant.tipo_negocio not in {"CAR_WASH", "AUTO_REPAIR"}:
            return {"error": "Ferramenta indisponível neste segmento"}
        try:
            plate = normalize_plate(args.plate)
        except ValueError:
            return {"error": "Placa inválida"}
        existing = db.query(Veiculo).filter(
            Veiculo.clinica_id == tenant.id, Veiculo.placa == plate,
        ).first()
        if existing:
            if existing.paciente_id != ctx.paciente.id:
                return {"error": "Veículo cadastrado para outro cliente; peça suporte humano"}
            if not existing.ativo:
                existing.ativo = True
                db.commit()
            return {"success": True, "vehicle_id": existing.id, "plate": plate}
        vehicle = Veiculo(
            clinica_id=tenant.id, paciente_id=ctx.paciente.id, placa=plate,
            marca=args.brand, modelo=args.model, ano=args.year, cor=args.color,
        )
        db.add(vehicle)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return {"error": "Placa já cadastrada; peça suporte humano"}
        db.refresh(vehicle)
        return {"success": True, "vehicle_id": vehicle.id, "plate": vehicle.placa}
    if name == "listCustomerPets":
        pets = db.query(Pet).filter(
            Pet.clinica_id == tenant.id,
            Pet.paciente_id == ctx.paciente.id,
            Pet.ativo.is_(True),
        ).order_by(Pet.nome).all()
        return {"pets": [
            {"id": p.id, "name": p.nome, "species": p.especie,
             "breed": p.raca, "size": p.porte}
            for p in pets
        ]}
    if name == "registerPet":
        pet = Pet(
            clinica_id=tenant.id, paciente_id=ctx.paciente.id,
            nome=args.name.strip(), especie=args.species.strip(),
            raca=args.breed, porte=args.size,
        )
        if not pet.nome or not pet.especie:
            return {"error": "Nome e espécie do pet são obrigatórios"}
        db.add(pet)
        db.commit()
        db.refresh(pet)
        return {"success": True, "pet_id": pet.id, "name": pet.nome}
    if name == "listRooms":
        rooms = db.query(Quarto).filter(
            Quarto.clinica_id == tenant.id,
            Quarto.ativo.is_(True),
            Quarto.status == "DISPONIVEL",
        ).order_by(Quarto.numero).all()
        return {"rooms": [
            {"id": r.id, "number": r.numero, "category": r.categoria,
             "capacity": r.capacidade,
             "nightly_rate": str(r.valor_diaria) if r.valor_diaria is not None else None}
            for r in rooms
        ]}
    if name == "checkRoomAvailability":
        if args.check_in < datetime.now(ZoneInfo(tenant.timezone)).date():
            return {"error": "Check-in não pode ser no passado"}
        rooms = db.query(Quarto).filter(
            Quarto.clinica_id == tenant.id,
            Quarto.ativo.is_(True),
            Quarto.status == "DISPONIVEL",
        )
        if args.room_id:
            rooms = rooms.filter(Quarto.id == args.room_id)
        available = [r for r in rooms.all() if not reservation_conflict(
            db, tenant.id, r.id, args.check_in, args.check_out
        )]
        return {"rooms": [
            {"id": r.id, "number": r.numero, "category": r.categoria,
             "capacity": r.capacidade,
             "total_estimate": str(r.valor_diaria * (args.check_out - args.check_in).days)
             if r.valor_diaria is not None else None}
            for r in available
        ]}
    if name == "createHotelReservation":
        if args.check_in < datetime.now(ZoneInfo(tenant.timezone)).date():
            return {"error": "Check-in não pode ser no passado"}
        bloquear_agenda_tenant(db, tenant.id)
        room = db.query(Quarto).filter(
            Quarto.clinica_id == tenant.id,
            Quarto.id == args.room_id,
            Quarto.ativo.is_(True),
            Quarto.status == "DISPONIVEL",
        ).first()
        if room is None:
            return {"error": "Quarto indisponível"}
        if reservation_conflict(db, tenant.id, room.id, args.check_in, args.check_out):
            return {"error": "Quarto ocupado neste período"}
        item = ReservaHotel(
            clinica_id=tenant.id, paciente_id=ctx.paciente.id,
            quarto_id=room.id, check_in=args.check_in, check_out=args.check_out,
            valor_previsto=room.valor_diaria * (args.check_out - args.check_in).days
            if room.valor_diaria is not None else None,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return {"success": True, "reservation_id": item.id,
                "room_number": room.numero,
                "check_in": item.check_in.isoformat(),
                "check_out": item.check_out.isoformat()}
    if name == "findCustomerReservations":
        items = db.query(ReservaHotel).filter(
            ReservaHotel.clinica_id == tenant.id,
            ReservaHotel.paciente_id == ctx.paciente.id,
        ).order_by(ReservaHotel.check_in.desc()).limit(20).all()
        return {"reservations": [
            {"id": r.id, "room_id": r.quarto_id,
             "check_in": r.check_in.isoformat(), "check_out": r.check_out.isoformat(),
             "status": r.status} for r in items
        ]}
    if name == "cancelHotelReservation":
        item = db.query(ReservaHotel).filter(
            ReservaHotel.clinica_id == tenant.id,
            ReservaHotel.paciente_id == ctx.paciente.id,
            ReservaHotel.id == args.reservation_id,
        ).first()
        if (item is None or item.status != "RESERVADA"
                or item.check_in < datetime.now(ZoneInfo(tenant.timezone)).date()):
            return {"error": "Reserva ativa não encontrada"}
        item.status = "CANCELADA"
        db.commit()
        return {"success": True, "reservation_id": item.id}
    if name == "createAppointment":
        service = _service(ctx, args.service_id)
        if not service:
            return {"error": "Serviço não encontrado"}
        vehicle = None
        if tenant.tipo_negocio in {"CAR_WASH", "AUTO_REPAIR"}:
            if not args.vehicle_id:
                return {"error": "Selecione ou cadastre o veículo antes de agendar"}
            vehicle = db.query(Veiculo).filter(
                Veiculo.id == args.vehicle_id,
                Veiculo.clinica_id == tenant.id,
                Veiculo.paciente_id == ctx.paciente.id,
                Veiculo.ativo.is_(True),
            ).first()
            if vehicle is None:
                return {"error": "Veículo não encontrado para este cliente"}
        pet = None
        if tenant.tipo_negocio == "PET":
            if not args.pet_id:
                return {"error": "Selecione ou cadastre o pet antes de agendar"}
            pet = db.query(Pet).filter(
                Pet.id == args.pet_id,
                Pet.clinica_id == tenant.id,
                Pet.paciente_id == ctx.paciente.id,
                Pet.ativo.is_(True),
            ).first()
            if pet is None:
                return {"error": "Pet não encontrado para este tutor"}
        inicio = _utc_naive(args.starts_at, tenant)
        local_date = (
            inicio.replace(tzinfo=timezone.utc)
            .astimezone(ZoneInfo(tenant.timezone))
            .date()
        )
        bloquear_agenda_tenant(db, tenant.id)
        try:
            available = slots_disponiveis(
                db, tenant, service, local_date, args.professional_id
            )
        except ValueError as exc:
            return {"error": str(exc)}
        if inicio not in available or ha_conflito(
            db, tenant.id, inicio, service.duracao_minutos, args.professional_id
        ):
            return {"error": "Horário indisponível"}
        prof = None
        if args.professional_id:
            prof = (
                db.query(Profissional)
                .filter(
                    Profissional.id == args.professional_id,
                    Profissional.clinica_id == tenant.id,
                    Profissional.ativo.is_(True),
                )
                .first()
            )
        item = Agendamento(
            clinica_id=tenant.id,
            paciente_id=ctx.paciente.id,
            veiculo_id=vehicle.id if vehicle else None,
            pet_id=pet.id if pet else None,
            procedimento_id=service.id,
            valor_previsto=service.preco,
            servico=service.nome,
            data_hora=inicio,
            duracao_minutos=service.duracao_minutos,
            profissional_id=prof.id if prof else None,
            profissional=prof.nome if prof else None,
            origem="WHATSAPP",
            status=Status.PENDENTE,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return {"success": True, "appointment": _appointment_data(item)}
    if name == "rescheduleAppointment":
        item = _appointment(ctx, args.appointment_id)
        if not item or item.status not in (Status.PENDENTE, Status.CONFIRMADO):
            return {"error": "Agendamento ativo não encontrado"}
        service = _service(ctx, item.procedimento_id) if item.procedimento_id else None
        if not service:
            return {"error": "Agendamento sem serviço cadastrado; peça suporte humano"}
        inicio = _utc_naive(args.starts_at, tenant)
        local_date = (
            inicio.replace(tzinfo=timezone.utc)
            .astimezone(ZoneInfo(tenant.timezone))
            .date()
        )
        bloquear_agenda_tenant(db, tenant.id)
        slots = slots_disponiveis(db, tenant, service, local_date, item.profissional_id)
        if inicio not in slots and inicio != item.data_hora:
            return {"error": "Horário indisponível"}
        if ha_conflito(
            db,
            tenant.id,
            inicio,
            item.duracao_minutos,
            item.profissional_id,
            excluir_id=item.id,
        ):
            return {"error": "Horário indisponível"}
        item.data_hora = inicio
        item.status = Status.PENDENTE
        item.confirmacao_enviada = False
        item.segunda_confirmacao = False
        db.commit()
        return {"success": True, "appointment": _appointment_data(item)}
    if name == "cancelAppointment":
        item = _appointment(ctx, args.appointment_id)
        if not item or item.status not in (Status.PENDENTE, Status.CONFIRMADO):
            return {"error": "Agendamento ativo não encontrado"}
        item.status = Status.CANCELADO
        db.commit()
        return {"success": True, "appointment": _appointment_data(item)}
    if ctx.conversa.atendimento_humano:
        return {"success": True, "human_takeover": True, "already_human": True}
    ctx.conversa.atendimento_humano = True
    db.commit()
    if tenant.tipo_negocio != "RECEPIA":
        return {"success": True, "human_takeover": True}

    config = db.query(ConfiguracaoNegocio).filter(ConfiguracaoNegocio.clinica_id == tenant.id).first()
    destino = tenta_normalizar(config.telefone_suporte_humano) if config and config.telefone_suporte_humano else None
    origem = tenta_normalizar(ctx.paciente.telefone)
    if not destino or destino == origem or not tenant.evolution_instance_name:
        return {"success": True, "human_takeover": True, "owner_notified": False}

    from services.whatsapp import WhatsAppService
    resumo = (args.resumo or "Interessado pediu atendimento humano.").strip().replace("\n", " ")[:300]
    aviso = (
        "Novo interessado em contratar o Recepia.\n"
        f"Nome: {ctx.paciente.nome[:120]}\n"
        f"WhatsApp: +{origem or ctx.paciente.telefone}\n"
        f"Resumo: {resumo}\n"
        "A conversa está no painel em Conversas, marcada para atendimento humano."
    )
    try:
        enviado = WhatsAppService().enviar_mensagem(tenant.evolution_instance_name, destino, aviso)
        notified = bool(enviado.get("success"))
    except Exception:
        log.exception("Aviso comercial falhou: tenant=%s", tenant.id)
        notified = False
    if not notified:
        log.error("Aviso comercial não confirmado: tenant=%s", tenant.id)
    return {"success": True, "human_takeover": True, "owner_notified": notified}
