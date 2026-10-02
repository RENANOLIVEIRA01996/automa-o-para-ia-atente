"""Persistência de conversa e resposta do agente a eventos Evolution."""

import logging
import json
import re
import unicodedata
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import Clinica, ConfiguracaoNegocio, Conversa, Mensagem, Paciente, WhatsAppInstance
from services.ai.agent import generate_reply
from services.ai.public_links import recepia_signup_url, recepia_site_url
from services.ai.tools import ToolContext, execute_tool
from services.whatsapp import WhatsAppService

log = logging.getLogger("recepia.inbound")

_SALES_INTENT = re.compile(
    r"\b(?:quero|gostaria de|vou|preciso)\s+(?:contratar|assinar|comprar|fechar)\b"
    r"|\b(?:como|onde)\s+(?:contrato|assino|compro)\b"
    r"|\b(?:me passe|manda|envia)\s+(?:o\s+)?(?:link de pagamento|checkout)\b",
    re.IGNORECASE,
)

_AI_RETURN = re.compile(
    r"\b(?:voltar|volte|retomar|retome|reativar|reative)\b.{0,60}"
    r"(?:\bia\b|inteligencia artificial|assistente|atendente virtual|atendimento automatico|robo|bot)\b"
    r"|\b(?:quero|gostaria de|prefiro|pode)\b.{0,25}\b(?:falar|conversar)\b.{0,30}"
    r"(?:\bia\b|assistente|atendente virtual|robo|bot)\b"
)
_HUMAN_REQUEST = re.compile(
    r"\b(?:quero|preciso|gostaria de|pode)\b.{0,35}\b(?:falar|conversar)\b.{0,30}"
    r"(?:atendente|pessoa|humano|alguem|representante)\b"
)


def _normalize_intent(texto: str) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFKD", texto.casefold())
        if not unicodedata.combining(char)
    )


def explicit_ai_return(texto: str) -> bool:
    normalized = _normalize_intent(texto)
    match = _AI_RETURN.search(normalized)
    if not match:
        return False
    return not re.search(r"\b(?:nao|nunca)\b.{0,30}$", normalized[:match.start()])


def requested_recepia_link(texto: str) -> str | None:
    """Resolve pedidos explícitos de link sem depender da resposta do modelo."""
    normalized = _normalize_intent(texto)
    if re.search(r"\bnao\s+(?:me\s+)?(?:manda|envia|passe|passa|quero)\b", normalized):
        return None
    if re.search(r"\b(?:video|demonstracao|apresentacao|pagamento|checkout)\b", normalized):
        return None
    has_link = bool(re.search(r"\b(?:link|url|endereco)\b", normalized))
    has_site = bool(re.search(r"\b(?:site|pagina|landing)\b", normalized))
    if not has_link and not has_site:
        return None
    if re.search(r"\b(?:cadastro|cadastrar|conta|teste|comecar|iniciar|experimentar|assinar|contratar|comprar)\b", normalized):
        return "signup"
    if has_link or (has_site and re.search(
        r"\b(?:qual|manda|envia|passe|passa|quero|gostaria|ver|acessar|visitar|conhecer)\b",
        normalized,
    )):
        return "site"
    return None


def process_inbound(
    db: Session,
    clinica: Clinica,
    instance_name: str,
    telefone: str,
    texto: str,
    message_id: str,
    push_name: str | None = None,
) -> dict:
    """Registra a mensagem antes de chamar IA; unique impede resposta duplicada."""
    existente = (
        db.query(Mensagem)
        .filter(
            Mensagem.instance_name == instance_name,
            Mensagem.external_message_id == message_id,
        )
        .first()
    )
    if existente:
        return {"status": "duplicada"}
    paciente = (
        db.query(Paciente)
        .filter(
            Paciente.clinica_id == clinica.id,
            Paciente.telefone == telefone,
            Paciente.deletado_em.is_(None),
        )
        .first()
    )
    if paciente is None:
        paciente = Paciente(
            clinica_id=clinica.id,
            nome=(push_name or "Cliente")[:120],
            telefone=telefone,
        )
        db.add(paciente)
        db.flush()
    conversa = (
        db.query(Conversa)
        .filter(
            Conversa.clinica_id == clinica.id,
            Conversa.paciente_id == paciente.id,
            Conversa.canal == "WHATSAPP",
        )
        .first()
    )
    if conversa is None:
        conversa = Conversa(clinica_id=clinica.id, paciente_id=paciente.id)
        db.add(conversa)
        db.flush()
    conversa.ultima_mensagem_em = datetime.utcnow()
    db.add(
        Mensagem(
            clinica_id=clinica.id,
            conversa_id=conversa.id,
            direcao="IN",
            conteudo=texto,
            instance_name=instance_name,
            external_message_id=message_id,
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"status": "duplicada"}
    returning_from_human = False
    if conversa.atendimento_humano:
        returning_from_human = explicit_ai_return(texto)
        if not returning_from_human and not _HUMAN_REQUEST.search(_normalize_intent(texto)):
            config = db.query(ConfiguracaoNegocio).filter(
                ConfiguracaoNegocio.clinica_id == clinica.id
            ).first()
            minutes = config.retorno_ia_apos_minutos if config else None
            last_human = conversa.atendimento_humano_atividade_em
            returning_from_human = bool(
                minutes and last_human
                and datetime.utcnow() - last_human >= timedelta(minutes=minutes)
            )
        if not returning_from_human:
            return {"status": "humano"}
        conversa.atendimento_humano = False
        conversa.atendimento_humano_atividade_em = None
        db.commit()
        log.info("Atendimento por IA reativado: tenant=%s conversa=%s", clinica.id, conversa.id)

    if not returning_from_human and clinica.tipo_negocio == "RECEPIA" and _SALES_INTENT.search(texto) and not re.search(
        r"\b(?:não|nao|nunca)\s+(?:quero|vou|preciso|gostaria de)\s+\w*\s*(?:contratar|assinar|comprar|fechar)\b",
        texto, re.IGNORECASE,
    ):
        resultado = execute_tool(
            "requestHumanSupport",
            json.dumps({"resumo": f"Interesse explícito em contratação: {texto[:180]}"}, ensure_ascii=False),
            ToolContext(db=db, clinica=clinica, paciente=paciente, conversa=conversa),
        )
        log.info("Interesse comercial encaminhado: tenant=%s aviso=%s", clinica.id, resultado.get("owner_notified"))
        resposta = ("Que bom! Vou encaminhar seu interesse ao responsável pelo Recepia para "
                    "continuar por aqui. Você também pode iniciar o teste grátis de 7 dias, "
                    f"sem cartão: {recepia_signup_url()}")
    elif clinica.tipo_negocio == "RECEPIA" and (link_kind := requested_recepia_link(texto)):
        resposta = (
            f"Aqui está o site do Recepia: {recepia_site_url()} Nele você pode conhecer "
            "o sistema e acessar a demonstração."
            if link_kind == "site" else
            f"Para começar seu teste grátis de 7 dias, sem cartão, acesse: {recepia_signup_url()}"
        )
    else:
        resposta = generate_reply(
            db, clinica, paciente, conversa,
            **({"returning_from_human": True} if returning_from_human else {}),
        )
    envio = WhatsAppService().enviar_mensagem(instance_name, telefone, resposta)
    if not envio.get("success"):
        db.commit()  # registra AIUsage mesmo com falha do canal
        log.error(
            "Envio WhatsApp falhou: tenant=%s instance=%s", clinica.id, instance_name
        )
        return {"status": "erro_envio"}
    db.add(
        Mensagem(
            clinica_id=clinica.id,
            conversa_id=conversa.id,
            direcao="OUT",
            conteudo=resposta,
            instance_name=instance_name,
        )
    )
    conversa.ultima_mensagem_em = datetime.utcnow()
    db.commit()
    return {"status": "respondida"}


def sync_instance(
    db: Session, clinica: Clinica, status: str, phone: str | None = None
) -> None:
    if not clinica.evolution_instance_name:
        return
    item = (
        db.query(WhatsAppInstance)
        .filter(WhatsAppInstance.clinica_id == clinica.id)
        .first()
    )
    if item is None:
        item = WhatsAppInstance(
            clinica_id=clinica.id, instance_name=clinica.evolution_instance_name
        )
        db.add(item)
    item.status = status
    if phone:
        item.phone_number = phone
    db.commit()
