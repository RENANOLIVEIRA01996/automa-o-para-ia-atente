"""Idempotência de mensagens e suspensão da IA durante atendimento humano."""

from models import Conversa, Mensagem, Paciente
from config import settings
from services.ai import inbound


def test_inbound_duplicado_e_human_takeover(
    client, db_session, clinica_fake, auth_headers_a, monkeypatch
):
    sent = []

    class FakeWhatsApp:
        def enviar_mensagem(self, instance_name, phone, message):
            sent.append((instance_name, phone, message))
            return {"success": True}

    monkeypatch.setattr(inbound, "WhatsAppService", FakeWhatsApp)
    monkeypatch.setattr(
        inbound, "generate_reply", lambda *_args: "Resposta real mockada"
    )
    tenant = clinica_fake["clinica"]
    first = inbound.process_inbound(
        db_session,
        tenant,
        tenant.evolution_instance_name,
        "5511999998888",
        "Oi",
        "message-1",
        "Cliente",
    )
    assert first["status"] == "respondida"
    assert (
        inbound.process_inbound(
            db_session,
            tenant,
            tenant.evolution_instance_name,
            "5511999998888",
            "Oi",
            "message-1",
        )["status"]
        == "duplicada"
    )
    assert len(sent) == 1
    assert (
        db_session.query(Mensagem).filter(Mensagem.clinica_id == tenant.id).count() == 2
    )

    conversation = (
        db_session.query(Conversa).filter(Conversa.clinica_id == tenant.id).one()
    )
    assert (
        client.post(
            f"/api/conversas/{conversation.id}/assumir", headers=auth_headers_a
        ).json()["atendimento_humano"]
        is True
    )
    result = inbound.process_inbound(
        db_session,
        tenant,
        tenant.evolution_instance_name,
        "5511999998888",
        "Preciso de ajuda",
        "message-2",
    )
    assert result["status"] == "humano"
    assert len(sent) == 1
    assert (
        db_session.query(Mensagem).filter(Mensagem.clinica_id == tenant.id).count() == 3
    )
    assert (
        client.post(
            f"/api/conversas/{conversation.id}/devolver", headers=auth_headers_a
        ).json()["atendimento_humano"]
        is False
    )


def test_conversas_nao_vazam_para_outro_tenant(
    client, db_session, clinica_fake, auth_headers_a, auth_headers_b
):
    tenant = clinica_fake["clinica"]
    customer = Paciente(clinica_id=tenant.id, nome="Cliente", telefone="5511998888777")
    db_session.add(customer)
    db_session.flush()
    conversation = Conversa(clinica_id=tenant.id, paciente_id=customer.id)
    db_session.add(conversation)
    db_session.commit()
    assert (
        client.get("/api/conversas", headers=auth_headers_a).json()[0]["id"]
        == conversation.id
    )
    assert client.get("/api/conversas", headers=auth_headers_b).json() == []
    assert (
        client.get(
            f"/api/conversas/{conversation.id}", headers=auth_headers_b
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/conversas/{conversation.id}/assumir", headers=auth_headers_b
        ).status_code
        == 404
    )


def test_webhook_openrouter_encaminha_ao_agente_sem_duplicar(
    client, db_session, clinica_fake, monkeypatch
):
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(settings, "OPENROUTER_MODEL", "test-model")
    monkeypatch.setattr(inbound, "generate_reply", lambda *_args: "Resposta")
    sent = []

    class FakeWhatsApp:
        def enviar_mensagem(self, instance, phone, message):
            sent.append((instance, phone, message))
            return {"success": True}

    monkeypatch.setattr(inbound, "WhatsAppService", FakeWhatsApp)
    tenant = clinica_fake["clinica"]
    payload = {
        "event": "messages.upsert",
        "instance": tenant.evolution_instance_name,
        "data": {
            "key": {"remoteJid": "5511999998888@s.whatsapp.net",
                    "fromMe": False, "id": "webhook-id-1"},
            "message": {"conversation": "Oi"},
            "pushName": "Cliente",
        },
    }
    headers = {"X-Webhook-Token": settings.EVOLUTION_WEBHOOK_SECRET}
    assert client.post("/api/webhook/evolution", json=payload, headers=headers).status_code == 200
    assert client.post("/api/webhook/evolution", json=payload, headers=headers).status_code == 200
    assert len(sent) == 1
    assert db_session.query(Mensagem).filter(Mensagem.clinica_id == tenant.id).count() == 2
