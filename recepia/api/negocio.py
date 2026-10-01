"""Identidade e regras genéricas da empresa autenticada."""

from datetime import date
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from sqlalchemy.orm import Session

from core import audit
from core.business_types import PUBLIC_BUSINESS_TYPES, INTERNAL_BUSINESS_TYPES, normalize_business_type
from core.segments import get_segment_config
from core.extra_fields import merge_extra_fields
from core.deps import audit_context, clinica_atual, requer_clinica_ativa
from database import get_db_dependency
from models import (
    AIUsage,
    AcaoAudit,
    Agendamento,
    Clinica,
    ConfiguracaoNegocio,
    Conversa,
    Mensagem,
    Paciente,
    OrdemServico,
    Procedimento,
    Profissional,
    Quarto,
    ReservaHotel,
    Status,
)

router = APIRouter(prefix="/api/negocio", tags=["negocio"])


class EmpresaIn(BaseModel):
    nome: str | None = Field(None, min_length=2, max_length=120)
    slug: str | None = Field(
        None, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=100
    )
    tipo_negocio: str | None = None
    telefone: str | None = Field(None, max_length=30)
    email: str | None = Field(None, max_length=255)
    timezone: str | None = Field(None, max_length=64)
    endereco_rua: str | None = Field(None, max_length=120)
    endereco_numero: str | None = Field(None, max_length=20)
    endereco_cidade: str | None = Field(None, max_length=80)
    endereco_uf: str | None = Field(None, min_length=2, max_length=2)
    endereco_cep: str | None = Field(None, max_length=8)
    campos_extras: dict[str, object] | None = None

    @field_validator("tipo_negocio")
    @classmethod
    def validar_tipo(cls, value):
        return normalize_business_type(value) if value is not None else None

    @field_validator("timezone")
    @classmethod
    def validar_timezone(cls, value):
        if value is not None:
            try:
                ZoneInfo(value)
            except ZoneInfoNotFoundError as exc:
                raise ValueError("Timezone inválido") from exc
        return value


class EmpresaOut(BaseModel):
    id: str
    nome: str
    slug: str | None
    tipo_negocio: str
    telefone: str | None
    email: str | None
    timezone: str
    endereco_rua: str | None = None
    endereco_numero: str | None = None
    endereco_cidade: str | None = None
    endereco_uf: str | None = None
    endereco_cep: str | None = None
    campos_extras: dict = Field(default_factory=dict)
    plano: str
    trial_expira_em: date | None = None
    ativo: bool

    class Config:
        from_attributes = True


class ConfiguracaoIn(BaseModel):
    descricao: str | None = Field(None, max_length=5000)
    instrucoes_ia: str | None = Field(None, max_length=10000)
    video_apresentacao_ativo: bool | None = None
    video_apresentacao_texto: str | None = Field(None, max_length=600)
    politica_cancelamento: str | None = Field(None, max_length=5000)
    regras_agendamento: str | None = Field(None, max_length=5000)
    mensagem_boas_vindas: str | None = Field(None, max_length=2000)
    telefone_suporte_humano: str | None = Field(None, max_length=30)
    retorno_ia_apos_minutos: int | None = Field(None, ge=1, le=1440)


class ConfiguracaoOut(ConfiguracaoIn):
    id: str
    clinica_id: str

    class Config:
        from_attributes = True


@router.get("/tipos")
def tipos_negocio():
    return sorted(PUBLIC_BUSINESS_TYPES)


@router.get("/segmentos")
def catalogo_segmentos():
    """Business labels from the same catalog used by the panel and AI."""
    return [
        {"code": code, "name": get_segment_config(code)["name"]}
        for code in sorted(PUBLIC_BUSINESS_TYPES)
    ]


@router.get("/segmento")
def segmento_atual(clinica: Clinica = Depends(clinica_atual)):
    """Resolved UI and AI preset for the authenticated tenant."""
    return get_segment_config(clinica.tipo_negocio)


@router.get("", response_model=EmpresaOut)
def obter_empresa(clinica: Clinica = Depends(clinica_atual)):
    return clinica


@router.patch("", response_model=EmpresaOut)
def atualizar_empresa(
    payload: EmpresaIn,
    clinica: Clinica = Depends(requer_clinica_ativa),
    ctx: dict = Depends(audit_context),
    db: Session = Depends(get_db_dependency),
):
    updates = payload.model_dump(exclude_unset=True)
    if updates.get("tipo_negocio") in INTERNAL_BUSINESS_TYPES and clinica.tipo_negocio not in INTERNAL_BUSINESS_TYPES:
        raise HTTPException(403, "Segmento interno indisponível para esta empresa")
    if any(
        key in updates and updates[key] is None
        for key in ("nome", "tipo_negocio", "timezone")
    ):
        raise HTTPException(422, "Nome, tipo de negócio e timezone não podem ser nulos")
    if updates.get("slug"):
        existente = (
            db.query(Clinica)
            .filter(Clinica.slug == updates["slug"], Clinica.id != clinica.id)
            .first()
        )
        if existente:
            raise HTTPException(409, "Slug já utilizado")
    for key, value in updates.items():
        if key == "campos_extras":
            if value is not None:
                try:
                    clinica.campos_extras = merge_extra_fields(
                        clinica.campos_extras, value,
                        updates.get("tipo_negocio") or clinica.tipo_negocio,
                        "business",
                    )
                except ValueError as exc:
                    raise HTTPException(422, str(exc)) from exc
            continue
        setattr(clinica, key, value)
    audit.log(
        db,
        **ctx,
        acao=AcaoAudit.UPDATE,
        recurso="negocio",
        recurso_id=clinica.id,
        detalhes={"campos": sorted(updates)},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Slug já utilizado") from exc
    db.refresh(clinica)
    return clinica


@router.get("/configuracao", response_model=ConfiguracaoOut | None)
def obter_configuracao(
    clinica: Clinica = Depends(clinica_atual),
    db: Session = Depends(get_db_dependency),
):
    return (
        db.query(ConfiguracaoNegocio)
        .filter(ConfiguracaoNegocio.clinica_id == clinica.id)
        .first()
    )


@router.patch("/configuracao", response_model=ConfiguracaoOut)
def atualizar_configuracao(
    payload: ConfiguracaoIn,
    clinica: Clinica = Depends(requer_clinica_ativa),
    ctx: dict = Depends(audit_context),
    db: Session = Depends(get_db_dependency),
):
    config = (
        db.query(ConfiguracaoNegocio)
        .filter(ConfiguracaoNegocio.clinica_id == clinica.id)
        .first()
    )
    if config is None:
        config = ConfiguracaoNegocio(clinica_id=clinica.id)
        db.add(config)
    updates = payload.model_dump(exclude_unset=True)
    if "video_apresentacao_ativo" in updates and updates["video_apresentacao_ativo"] is None:
        raise HTTPException(422, "Envio do vídeo deve estar habilitado ou desabilitado")
    if any(key.startswith("video_apresentacao_") for key in updates) and clinica.tipo_negocio != "RECEPIA":
        raise HTTPException(403, "Vídeo institucional disponível apenas para o Recepia")
    for key, value in updates.items():
        setattr(config, key, value)
    db.flush()
    audit.log(
        db,
        **ctx,
        acao=AcaoAudit.UPDATE,
        recurso="configuracao_negocio",
        recurso_id=config.id,
        detalhes={"campos": sorted(updates)},
    )
    db.commit()
    db.refresh(config)
    return config


@router.get("/indicadores")
def indicadores(
    clinica: Clinica = Depends(clinica_atual),
    db: Session = Depends(get_db_dependency),
):
    hoje = datetime.now(ZoneInfo(clinica.timezone)).date()
    inicio = datetime.combine(hoje, time.min, tzinfo=ZoneInfo(clinica.timezone))
    fim = inicio + timedelta(days=1)
    inicio_utc = inicio.astimezone(timezone.utc).replace(tzinfo=None)
    fim_utc = fim.astimezone(timezone.utc).replace(tzinfo=None)
    base = db.query(Agendamento).filter(Agendamento.clinica_id == clinica.id)
    hoje_query = base.filter(
        Agendamento.data_hora >= inicio_utc, Agendamento.data_hora < fim_utc
    )
    por_status = dict(
        db.query(Agendamento.status, func.count(Agendamento.id))
        .filter(
            Agendamento.clinica_id == clinica.id,
            Agendamento.data_hora >= inicio_utc,
            Agendamento.data_hora < fim_utc,
        )
        .group_by(Agendamento.status)
        .all()
    )
    valor_concluido = (
        db.query(func.coalesce(func.sum(func.coalesce(Agendamento.valor_previsto, Procedimento.preco, 0)), 0))
        .select_from(Agendamento)
        .outerjoin(
            Procedimento,
            (Agendamento.procedimento_id == Procedimento.id)
            & (Procedimento.clinica_id == clinica.id),
        )
        .filter(
            Agendamento.clinica_id == clinica.id,
            Agendamento.data_hora >= inicio_utc,
            Agendamento.data_hora < fim_utc,
            Agendamento.status == Status.REALIZADO,
        )
        .scalar()
    )
    extras = {}
    if clinica.tipo_negocio == "AUTO_REPAIR":
        ordens = db.query(OrdemServico).filter(
            OrdemServico.clinica_id == clinica.id,
            OrdemServico.status.in_(("ABERTA", "EM_ANDAMENTO")),
        )
        extras = {
            "ordens_abertas": ordens.count(),
            "receita_estimada": float(ordens.with_entities(
                func.coalesce(func.sum(OrdemServico.valor), 0)
            ).scalar() or 0),
            "veiculos_em_servico": db.query(func.count(func.distinct(OrdemServico.veiculo_id))).filter(
                OrdemServico.clinica_id == clinica.id,
                OrdemServico.status == "EM_ANDAMENTO",
            ).scalar(),
        }
    elif clinica.tipo_negocio == "PET":
        extras = {
            "pets_agendados_hoje": hoje_query.filter(
                Agendamento.status != Status.CANCELADO,
                Agendamento.pet_id.is_not(None),
            ).with_entities(func.count(func.distinct(Agendamento.pet_id))).scalar(),
        }
    elif clinica.tipo_negocio == "HOTEL":
        active = db.query(ReservaHotel).filter(
            ReservaHotel.clinica_id == clinica.id,
            ReservaHotel.status.in_(("RESERVADA", "CHECK_IN")),
            ReservaHotel.check_out > hoje,
        )
        occupied = active.filter(
            ReservaHotel.status == "CHECK_IN",
            ReservaHotel.check_in <= hoje,
        ).with_entities(func.count(func.distinct(ReservaHotel.quarto_id))).scalar() or 0
        unavailable = active.filter(
            ReservaHotel.check_in <= hoje,
        ).with_entities(func.count(func.distinct(ReservaHotel.quarto_id))).scalar() or 0
        usable = db.query(Quarto).filter(
            Quarto.clinica_id == clinica.id,
            Quarto.ativo.is_(True),
            Quarto.status == "DISPONIVEL",
        ).count()
        extras = {
            "reservas_ativas": active.count(),
            "checkins_hoje": db.query(ReservaHotel).filter(
                ReservaHotel.clinica_id == clinica.id,
                ReservaHotel.check_in == hoje,
                ReservaHotel.status.in_(("RESERVADA", "CHECK_IN")),
            ).count(),
            "checkouts_hoje": db.query(ReservaHotel).filter(
                ReservaHotel.clinica_id == clinica.id,
                ReservaHotel.check_out == hoje,
                ReservaHotel.status.in_(("CHECK_IN", "CHECK_OUT")),
            ).count(),
            "quartos_ocupados": occupied,
            "quartos_disponiveis": max(0, usable - unavailable),
        }
    return {
        **extras,
        "agendamentos_hoje": hoje_query.filter(
            Agendamento.status != Status.CANCELADO
        ).count(),
        "em_andamento_hoje": por_status.get(Status.EM_ANDAMENTO, 0),
        "concluidos_hoje": por_status.get(Status.REALIZADO, 0),
        "confirmados_hoje": por_status.get(Status.CONFIRMADO, 0),
        "pendentes_hoje": por_status.get(Status.PENDENTE, 0),
        "faltas_hoje": por_status.get(Status.NO_SHOW, 0),
        "receita_hoje": float(valor_concluido or 0),
        "profissionais_ativos": db.query(Profissional).filter(
            Profissional.clinica_id == clinica.id,
            Profissional.ativo.is_(True),
        ).count(),
        "veiculos_em_servico": extras.get("veiculos_em_servico") if clinica.tipo_negocio == "AUTO_REPAIR" else hoje_query.filter(
            Agendamento.status == Status.EM_ANDAMENTO,
            Agendamento.veiculo_id.is_not(None),
        ).with_entities(func.count(func.distinct(Agendamento.veiculo_id))).scalar(),
        "proximos_agendamentos": base.filter(
            Agendamento.data_hora >= datetime.now(timezone.utc).replace(tzinfo=None),
            Agendamento.status.in_((Status.PENDENTE, Status.CONFIRMADO, Status.EM_ANDAMENTO)),
        ).count(),
        "cancelamentos_hoje": base.filter(
            Agendamento.data_hora >= inicio_utc,
            Agendamento.data_hora < fim_utc,
            Agendamento.status == Status.CANCELADO,
        ).count(),
        "novos_clientes_hoje": db.query(Paciente)
        .filter(
            Paciente.clinica_id == clinica.id,
            Paciente.criado_em >= inicio_utc,
            Paciente.criado_em < fim_utc,
        )
        .count(),
        "conversas": db.query(Conversa)
        .filter(Conversa.clinica_id == clinica.id)
        .count(),
        "conversas_humanas": db.query(Conversa)
        .filter(Conversa.clinica_id == clinica.id, Conversa.atendimento_humano.is_(True))
        .count(),
        "mensagens_hoje": db.query(Mensagem)
        .filter(
            Mensagem.clinica_id == clinica.id,
            Mensagem.criado_em >= inicio_utc,
            Mensagem.criado_em < fim_utc,
        )
        .count(),
        "chamadas_ia_hoje": db.query(AIUsage)
        .filter(
            AIUsage.clinica_id == clinica.id,
            AIUsage.criado_em >= inicio_utc,
            AIUsage.criado_em < fim_utc,
        )
        .count(),
        "tokens_ia_total": db.query(
            func.coalesce(func.sum(AIUsage.input_tokens + AIUsage.output_tokens), 0)
        )
        .filter(AIUsage.clinica_id == clinica.id)
        .scalar(),
    }
