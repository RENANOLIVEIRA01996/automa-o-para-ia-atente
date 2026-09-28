"""Persistência de conversa e resposta do agente a eventos Evolution."""

import logging
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import Clinica, Conversa, Mensagem, Paciente, WhatsAppInstance
from services.ai.agent import generate_reply
from services.whatsapp import WhatsAppService

log = logging.getLogger("recepia.inbound")


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
