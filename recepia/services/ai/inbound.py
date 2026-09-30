"""Persistência de conversa e resposta do agente a eventos Evolution."""

import logging
import json
import re
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import Clinica, Conversa, Mensagem, Paciente, WhatsAppInstance
from services.ai.agent import generate_reply
from services.ai.tools import ToolContext, execute_tool
from services.whatsapp import WhatsAppService

log = logging.getLogger("recepia.inbound")

_SALES_INTENT = re.compile(
    r"\b(?:quero|gostaria de|vou|preciso)\s+(?:contratar|assinar|comprar|fechar)\b"
    r"|\b(?:como|onde)\s+(?:contrato|assino|compro)\b"
    r"|\b(?:me passe|manda|envia)\s+(?:o\s+)?(?:link de pagamento|checkout)\b",
    re.IGNORECASE,
)


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
    if conversa.atendimento_humano:
        return {"status": "humano"}

    if clinica.tipo_negocio == "RECEPIA" and _SALES_INTENT.search(texto) and not re.search(
        r"\b(?:não|nao|nunca)\s+(?:quero|vou|preciso|gostaria de)\s+\w*\s*(?:contratar|assinar|comprar|fechar)\b",
        texto, re.IGNORECASE,
    ):
        resultado = execute_tool(
            "requestHumanSupport",
            json.dumps({"resumo": f"Interesse explícito em contratação: {texto[:180]}"}, ensure_ascii=False),
            ToolContext(db=db, clinica=clinica, paciente=paciente, conversa=conversa),
        )
        log.info("Interesse comercial encaminhado: tenant=%s aviso=%s", clinica.id, resultado.get("owner_notified"))
        resposta = "Que bom! Vou encaminhar seu interesse ao responsável pelo Recepia para continuar por aqui. Você também pode iniciar o teste grátis de 7 dias, sem cartão: https://recepia.132-226-243-173.sslip.io/cadastro"
    else:
        resposta = generate_reply(db, clinica, paciente, conversa)
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
