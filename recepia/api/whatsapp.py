"""Endpoints pra clínica conectar/desconectar/checar WhatsApp.

Autenticado via JWT da clínica. Dashboard mostra QR Code pra dona escanear.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from config import settings
from database import get_db_dependency
from models import AcaoAudit, Clinica
from core.deps import audit_context, clinica_atual, requer_clinica_ativa
from core import audit
from services.whatsapp import WhatsAppService
from services.ai.inbound import sync_instance

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])


@router.post("/conectar")
def conectar(
    clinica: Clinica = Depends(requer_clinica_ativa),
    ctx: dict = Depends(audit_context),
    db: Session = Depends(get_db_dependency),
):
    """Cria instância no Evolution, configura webhook automático (G5), retorna QR Code."""
    if not settings.DEBUG and not settings.PUBLIC_WEBHOOK_URL:
        raise HTTPException(503, "PUBLIC_WEBHOOK_URL não configurada")
    if not settings.DEBUG and settings.AI_PROVIDER == "openrouter" and not settings.openrouter_enabled:
        raise HTTPException(503, "Configure OPENROUTER_API_KEY e OPENROUTER_MODEL antes de conectar o WhatsApp")
    if not settings.DEBUG and not settings.EVOLUTION_API_KEY:
        raise HTTPException(503, "EVOLUTION_API_KEY não configurada")
    ws = WhatsAppService()
    if not ws.criar_instancia(clinica.evolution_instance_name).get("success"):
        raise HTTPException(502, "Falha ao criar instancia WhatsApp")

    # G5: aponta o webhook do Evolution pra Recepia ANTES da clínica conectar.
    # Sem isso, mensagens recebidas nunca chegam no servidor.
    if settings.PUBLIC_WEBHOOK_URL:
        webhook_url = settings.PUBLIC_WEBHOOK_URL.rstrip("/") + "/api/webhook/evolution"
        if not ws.configurar_webhook(clinica.evolution_instance_name, webhook_url).get("success"):
            raise HTTPException(502, "Falha ao configurar webhook")

    qr = ws.obter_qrcode(clinica.evolution_instance_name)
    if not qr.get("success"):
        raise HTTPException(502, "QR Code indisponivel")

    audit.log(db, **ctx, acao=AcaoAudit.SETUP, recurso="whatsapp",
              recurso_id=clinica.evolution_instance_name,
              detalhes={"acao": "conectar", "webhook_configurado": bool(settings.PUBLIC_WEBHOOK_URL)})
    db.commit()
    sync_instance(db, clinica, "AGUARDANDO_QR")

    return {
        "instance_name": clinica.evolution_instance_name,
        "qrcode_base64": qr.get("base64"),
        "pairing_code": qr.get("pairing_code"),
    }


@router.get("/status")
def status(
    clinica: Clinica = Depends(clinica_atual),
    ctx: dict = Depends(audit_context),
    db: Session = Depends(get_db_dependency),
):
    ws = WhatsAppService()
    resultado = ws.status_instancia(clinica.evolution_instance_name)
    # Atualiza flag no banco se mudou.
    # Race condition: /status concorrente com /desconectar ou com webhook do Evolution
    # podia gerar last-write-wins inconsistente. SELECT ... FOR UPDATE serializa as escritas.
    conectado = resultado.get("conectado", False)
    if clinica.evolution_conectado != conectado:
        clinica_lock = db.query(Clinica).filter(Clinica.id == clinica.id).with_for_update().first()
        if clinica_lock and clinica_lock.evolution_conectado != conectado:
            clinica_lock.evolution_conectado = conectado
            db.commit()
    if resultado.get("success"):
        sync_instance(db, clinica, "CONECTADO" if conectado else "DESCONECTADO")
    return {
        "conectado": conectado,
        "estado": resultado.get("estado"),
    }


@router.post("/desconectar")
def desconectar(
    clinica: Clinica = Depends(requer_clinica_ativa),
    ctx: dict = Depends(audit_context),
    db: Session = Depends(get_db_dependency),
):
    ws = WhatsAppService()
    resultado = ws.desconectar(clinica.evolution_instance_name)
    if not resultado.get("success"):
        raise HTTPException(502, "Falha ao desconectar WhatsApp")
    # Lock pra evitar race com /status concorrente sobrescrevendo evolution_conectado.
    clinica_lock = db.query(Clinica).filter(Clinica.id == clinica.id).with_for_update().first()
    if clinica_lock:
        clinica_lock.evolution_conectado = False
    audit.log(db, **ctx, acao=AcaoAudit.SETUP, recurso="whatsapp",
              recurso_id=clinica.evolution_instance_name,
              detalhes={"acao": "desconectar"})
    db.commit()
    sync_instance(db, clinica, "DESCONECTADO")
    return {"status": "DESCONECTADO"}


@router.post("/reconectar")
def reconectar(
    clinica: Clinica = Depends(requer_clinica_ativa),
    db: Session = Depends(get_db_dependency),
):
    if not WhatsAppService().reiniciar(clinica.evolution_instance_name).get("success"):
        raise HTTPException(502, "Falha ao reiniciar WhatsApp")
    sync_instance(db, clinica, "CONECTANDO")
    return {"status": "CONECTANDO"}
