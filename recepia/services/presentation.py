"""Vídeo institucional público do Recepia, enviado pela instância Evolution do tenant."""

import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from config import settings
from models import Clinica, ConfiguracaoNegocio, Conversa, Mensagem, Paciente
from services.whatsapp import WhatsAppService

log = logging.getLogger("recepia.presentation")

VIDEO_FILENAME = "recepia-apresentacao.mp4"
VIDEO_PATH = Path(__file__).resolve().parents[1] / "public" / "media" / VIDEO_FILENAME
VIDEO_PATH_URL = f"/media/{VIDEO_FILENAME}"
INTRO_TEXT = "Claro! 😊 Vou te mostrar rapidamente como o Recepia funciona."
DEFAULT_CAPTION = (
    "Recepia 🤖\nEnquanto você trabalha, nossa IA ajuda a atender seus clientes, "
    "organizar informações e realizar agendamentos pelo WhatsApp."
)
FOLLOWUP_TEXT = "Se quiser, posso também te explicar os planos ou te ajudar a criar sua conta."
UNAVAILABLE_TEXT = (
    "Posso te explicar por aqui: o Recepia atende clientes pelo WhatsApp com IA "
    "e ajuda a organizar serviços, horários e agendamentos. "
    "Se quiser, posso detalhar os planos ou orientar seu cadastro."
)
RECENT_TEXT = (
    "Já enviei o vídeo nesta conversa há pouco. Posso explicar algum ponto; "
    "se quiser receber o vídeo de novo, é só pedir."
)
COOLDOWN = timedelta(hours=12)
_EXPLICIT_RESEND = re.compile(
    r"(?:v[ií]deo|apresenta[cç][aã]o|demonstra[cç][aã]o).{0,40}"
    r"(?:de novo|novamente|outra vez|reenvi[ae]|repete)"
    r"|(?:reenvi[ae]|manda|envia).{0,25}(?:de novo|novamente|outra vez).{0,25}"
    r"(?:v[ií]deo|apresenta[cç][aã]o|demonstra[cç][aã]o)",
    re.IGNORECASE,
)


def public_video_url() -> str | None:
    """Usa somente uma base HTTPS pública; o webhook interno nunca é usado."""
    candidates = [settings.PUBLIC_BASE_URL, settings.APP_URL]
    if settings.DOMAIN:
        candidates.append("https://" + settings.DOMAIN)
    for candidate in candidates:
        try:
            parsed = urlsplit((candidate or "").strip())
        except ValueError:
            continue
        if (
            parsed.scheme == "https"
            and parsed.hostname
            and not parsed.username
            and not parsed.password
            and not parsed.query
            and not parsed.fragment
        ):
            return f"{parsed.scheme}://{parsed.netloc}{VIDEO_PATH_URL}"
    return None


def video_available() -> bool:
    try:
        return VIDEO_PATH.is_file() and VIDEO_PATH.stat().st_size > 1024
    except OSError:
        return False


def explicit_resend_requested(db: Session, clinica_id: str, conversa_id: str) -> bool:
    inbound = (
        db.query(Mensagem)
        .filter(
            Mensagem.clinica_id == clinica_id,
            Mensagem.conversa_id == conversa_id,
            Mensagem.direcao == "IN",
        )
        .order_by(Mensagem.criado_em.desc(), Mensagem.id.desc())
        .first()
    )
    return bool(inbound and _EXPLICIT_RESEND.search(inbound.conteudo))


def send_presentation_video(
    db: Session, clinica: Clinica, paciente: Paciente, conversa: Conversa
) -> dict:
    """Envia aviso e vídeo pela mesma instância do tenant; registra sucesso no histórico."""
    if clinica.tipo_negocio != "RECEPIA" or conversa.clinica_id != clinica.id or paciente.clinica_id != clinica.id:
        return {"success": False, "reason": "not_allowed", "fallback_text": UNAVAILABLE_TEXT}
    config = db.query(ConfiguracaoNegocio).filter(
        ConfiguracaoNegocio.clinica_id == clinica.id
    ).first()
    if config and not config.video_apresentacao_ativo:
        return {"success": False, "reason": "disabled", "fallback_text": UNAVAILABLE_TEXT}
    url = public_video_url()
    if not url or not video_available() or not clinica.evolution_instance_name:
        log.warning("Vídeo de apresentação indisponível: tenant=%s", clinica.id)
        return {"success": False, "reason": "unavailable", "fallback_text": UNAVAILABLE_TEXT}

    # A linha da conversa serializa envios simultâneos ao mesmo contato no Postgres.
    db.query(Conversa).filter(
        Conversa.id == conversa.id, Conversa.clinica_id == clinica.id
    ).with_for_update().one()
    last_video = (
        db.query(Mensagem)
        .filter(
            Mensagem.clinica_id == clinica.id,
            Mensagem.conversa_id == conversa.id,
            Mensagem.direcao == "OUT",
            Mensagem.tipo == "VIDEO",
            Mensagem.criado_em >= datetime.utcnow() - COOLDOWN,
        )
        .first()
    )
    if last_video and not explicit_resend_requested(db, clinica.id, conversa.id):
        db.commit()
        return {"success": False, "reason": "recent", "fallback_text": RECENT_TEXT}

    whatsapp = WhatsAppService()
    try:
        intro = whatsapp.enviar_mensagem(clinica.evolution_instance_name, paciente.telefone, INTRO_TEXT)
    except Exception:
        db.commit()
        log.exception("Aviso do vídeo falhou: tenant=%s", clinica.id)
        return {"success": False, "reason": "send_failed", "fallback_text": UNAVAILABLE_TEXT}
    if not intro.get("success"):
        db.commit()
        log.error("Aviso do vídeo falhou: tenant=%s status=%s", clinica.id, intro.get("status"))
        return {"success": False, "reason": "send_failed", "fallback_text": UNAVAILABLE_TEXT}
    db.add(Mensagem(
        clinica_id=clinica.id, conversa_id=conversa.id, direcao="OUT",
        conteudo=INTRO_TEXT, instance_name=clinica.evolution_instance_name,
    ))
    caption = (config.video_apresentacao_texto if config and config.video_apresentacao_texto else DEFAULT_CAPTION)
    try:
        video = whatsapp.enviar_video(
            clinica.evolution_instance_name, paciente.telefone, url, caption
        )
    except Exception:
        db.commit()
        log.exception("Envio do vídeo falhou: tenant=%s", clinica.id)
        return {"success": False, "reason": "send_failed", "fallback_text": UNAVAILABLE_TEXT}
    if not video.get("success"):
        db.commit()
        log.error("Envio do vídeo falhou: tenant=%s status=%s", clinica.id, video.get("status"))
        return {"success": False, "reason": "send_failed", "fallback_text": UNAVAILABLE_TEXT}
    db.add(Mensagem(
        clinica_id=clinica.id, conversa_id=conversa.id, direcao="OUT", tipo="VIDEO",
        conteudo=caption, instance_name=clinica.evolution_instance_name,
    ))
    conversa.ultima_mensagem_em = datetime.utcnow()
    db.commit()
    log.info("Vídeo de apresentação enviado: tenant=%s conversa=%s", clinica.id, conversa.id)
    return {"success": True, "video_sent": True, "followup": FOLLOWUP_TEXT}
