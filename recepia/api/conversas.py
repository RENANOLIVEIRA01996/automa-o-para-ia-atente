"""Caixa de entrada da empresa e controle de atendimento humano."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.deps import clinica_atual, requer_clinica_ativa
from database import get_db_dependency
from models import Clinica, Conversa, Mensagem, Paciente
from services.whatsapp import WhatsAppService

router = APIRouter(prefix="/api/conversas", tags=["conversas"])


def _conversa(db: Session, clinica_id: str, conversa_id: str) -> Conversa:
    item = (
        db.query(Conversa)
        .filter(
            Conversa.id == conversa_id,
            Conversa.clinica_id == clinica_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(404, "Conversa não encontrada")
    return item


@router.get("")
def listar(
    clinica: Clinica = Depends(clinica_atual),
    db: Session = Depends(get_db_dependency),
):
    items = (
        db.query(Conversa, Paciente)
        .join(
            Paciente,
            Paciente.id == Conversa.paciente_id,
        )
        .filter(Conversa.clinica_id == clinica.id, Paciente.clinica_id == clinica.id)
        .order_by(Conversa.ultima_mensagem_em.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "id": c.id,
            "cliente_id": p.id,
            "cliente": p.nome,
            "telefone": p.telefone,
            "atendimento_humano": c.atendimento_humano,
            "ultima_mensagem_em": c.ultima_mensagem_em,
        }
        for c, p in items
    ]


@router.get("/{conversa_id}")
def obter(
    conversa_id: str,
    clinica: Clinica = Depends(clinica_atual),
    db: Session = Depends(get_db_dependency),
):
    item = _conversa(db, clinica.id, conversa_id)
    mensagens = (
        db.query(Mensagem)
        .filter(
            Mensagem.clinica_id == clinica.id,
            Mensagem.conversa_id == item.id,
        )
        .order_by(Mensagem.criado_em.asc())
        .limit(200)
        .all()
    )
    return {
        "id": item.id,
        "atendimento_humano": item.atendimento_humano,
        "mensagens": [
            {
                "id": m.id,
                "direcao": m.direcao,
                "conteudo": m.conteudo,
                "criado_em": m.criado_em,
            }
            for m in mensagens
        ],
    }


@router.post("/{conversa_id}/assumir")
def assumir(
    conversa_id: str,
    clinica: Clinica = Depends(requer_clinica_ativa),
    db: Session = Depends(get_db_dependency),
):
    item = _conversa(db, clinica.id, conversa_id)
    item.atendimento_humano = True
    item.atendimento_humano_atividade_em = datetime.utcnow()
    db.commit()
    return {"atendimento_humano": True}


@router.post("/{conversa_id}/devolver")
def devolver(
    conversa_id: str,
    clinica: Clinica = Depends(requer_clinica_ativa),
    db: Session = Depends(get_db_dependency),
):
    item = _conversa(db, clinica.id, conversa_id)
    item.atendimento_humano = False
    item.atendimento_humano_atividade_em = None
    db.commit()
    return {"atendimento_humano": False}


class RespostaIn(BaseModel):
    texto: str = Field(..., min_length=1, max_length=4000)


@router.post("/{conversa_id}/responder")
def responder(
    conversa_id: str,
    payload: RespostaIn,
    clinica: Clinica = Depends(requer_clinica_ativa),
    db: Session = Depends(get_db_dependency),
):
    item = _conversa(db, clinica.id, conversa_id)
    cliente = (
        db.query(Paciente)
        .filter(
            Paciente.id == item.paciente_id,
            Paciente.clinica_id == clinica.id,
        )
        .first()
    )
    if not cliente or not clinica.evolution_instance_name:
        raise HTTPException(409, "WhatsApp indisponível")
    envio = WhatsAppService().enviar_mensagem(
        clinica.evolution_instance_name,
        cliente.telefone,
        payload.texto,
    )
    if not envio.get("success"):
        raise HTTPException(502, "Falha ao enviar mensagem")
    item.atendimento_humano = True
    item.atendimento_humano_atividade_em = datetime.utcnow()
    item.ultima_mensagem_em = datetime.utcnow()
    db.add(
        Mensagem(
            clinica_id=clinica.id,
            conversa_id=item.id,
            direcao="OUT",
            conteudo=payload.texto,
            instance_name=clinica.evolution_instance_name,
        )
    )
    db.commit()
    return {"status": "enviada", "atendimento_humano": True}
