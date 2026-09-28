"""Agenda transacional compartilhada pelo painel e pelo atendimento automático."""

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.orm import Session

from models import (
    Agendamento,
    BloqueioAgenda,
    Clinica,
    HorarioFuncionamento,
    HorarioProfissional,
    Procedimento,
    Profissional,
    ProfissionalProcedimento,
    Status,
)


def bloquear_agenda_tenant(db: Session, clinica_id: str) -> None:
    """Serializa escritas de agenda por tenant na transação PostgreSQL atual."""
    if db.get_bind().dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:tenant))"),
            {"tenant": clinica_id},
        )


def ha_conflito(
    db: Session,
    clinica_id: str,
    inicio: datetime,
    duracao_minutos: int,
    profissional_id: str | None = None,
    excluir_id: str | None = None,
) -> bool:
    """Detecta sobreposição; vaga sem profissional reserva a empresa inteira."""
    if duracao_minutos < 1 or duracao_minutos > 1440:
        raise ValueError("Duração inválida")
    fim = inicio + timedelta(minutes=duracao_minutos)
    consulta = db.query(Agendamento).filter(
        Agendamento.clinica_id == clinica_id,
        Agendamento.status.in_((Status.PENDENTE, Status.CONFIRMADO, Status.EM_ANDAMENTO)),
        Agendamento.data_hora < fim,
        Agendamento.data_hora >= inicio - timedelta(days=1),
    )
    if excluir_id:
        consulta = consulta.filter(Agendamento.id != excluir_id)
    for existente in consulta.all():
        if (
            profissional_id is None
            or existente.profissional_id is None
            or existente.profissional_id == profissional_id
        ):
            fim_existente = existente.data_hora + timedelta(
                minutes=existente.duracao_minutos
            )
            if inicio < fim_existente:
                return True

    bloqueios = (
        db.query(BloqueioAgenda)
        .filter(
            BloqueioAgenda.clinica_id == clinica_id,
            BloqueioAgenda.inicio < fim,
            BloqueioAgenda.fim > inicio,
        )
        .all()
    )
    return any(
        b.profissional_id is None
        or profissional_id is None
        or b.profissional_id == profissional_id
        for b in bloqueios
    )


def _periodo_dia(
    db: Session, clinica_id: str, dia_semana: int, profissional_id: str | None
):
    horario = (
        db.query(HorarioFuncionamento)
        .filter(
            HorarioFuncionamento.clinica_id == clinica_id,
            HorarioFuncionamento.dia_semana == dia_semana,
            HorarioFuncionamento.ativo.is_(True),
        )
        .first()
    )
    if horario is None:
        return None
    inicio, fim = horario.hora_inicio, horario.hora_fim
    passo = horario.intervalo_slot_min
    if profissional_id:
        proprio = (
            db.query(HorarioProfissional)
            .filter(
                HorarioProfissional.clinica_id == clinica_id,
                HorarioProfissional.profissional_id == profissional_id,
                HorarioProfissional.dia_semana == dia_semana,
            )
            .first()
        )
        if proprio:
            if not proprio.ativo:
                return None
            inicio = max(inicio, proprio.hora_inicio)
            fim = min(fim, proprio.hora_fim)
    return (inicio, fim, passo) if inicio < fim else None


def slots_disponiveis(
    db: Session,
    clinica: Clinica,
    procedimento: Procedimento,
    dia: date,
    profissional_id: str | None = None,
) -> list[datetime]:
    """Retorna inícios UTC disponíveis para um serviço em um dia local do tenant."""
    if procedimento.clinica_id != clinica.id or not procedimento.ativo:
        raise ValueError("Serviço não pertence à empresa")
    if profissional_id:
        profissional = (
            db.query(Profissional)
            .filter(
                Profissional.id == profissional_id,
                Profissional.clinica_id == clinica.id,
                Profissional.ativo.is_(True),
            )
            .first()
        )
        if profissional is None:
            raise ValueError("Profissional não pertence à empresa")
        vinculos = (
            db.query(ProfissionalProcedimento)
            .filter(
                ProfissionalProcedimento.clinica_id == clinica.id,
                ProfissionalProcedimento.profissional_id == profissional_id,
            )
            .all()
        )
        if vinculos and procedimento.id not in {v.procedimento_id for v in vinculos}:
            return []
    periodo = _periodo_dia(db, clinica.id, dia.weekday(), profissional_id)
    if periodo is None:
        return []
    inicio_h, fim_h, passo = periodo
    tz = ZoneInfo(clinica.timezone or "America/Sao_Paulo")
    cursor = datetime.combine(dia, time.fromisoformat(inicio_h), tzinfo=tz)
    limite = datetime.combine(dia, time.fromisoformat(fim_h), tzinfo=tz)
    duracao = timedelta(minutes=procedimento.duracao_minutos)
    agora = datetime.now(timezone.utc).replace(tzinfo=None)
    slots = []
    while cursor + duracao <= limite:
        utc = cursor.astimezone(timezone.utc).replace(tzinfo=None)
        if utc > agora and not ha_conflito(
            db, clinica.id, utc, procedimento.duracao_minutos, profissional_id
        ):
            slots.append(utc)
        cursor += timedelta(minutes=passo)
    return slots
