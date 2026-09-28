"""O agente não confirma reservas sem uma escrita bem-sucedida."""

from models import Conversa, Paciente
from services.ai import agent


class FakeProvider:
    def __init__(self, answers):
        self.answers = iter(answers)

    def chat_with_tools(self, messages, tools, tenant_id):
        return next(self.answers)


def _context(db_session, clinica_fake):
    tenant = clinica_fake["clinica"]
    customer = Paciente(clinica_id=tenant.id, nome="Cliente", telefone="5511999988777")
    db_session.add(customer)
    db_session.flush()
    conversation = Conversa(clinica_id=tenant.id, paciente_id=customer.id)
    db_session.add(conversation)
    db_session.commit()
    return tenant, customer, conversation


def test_modelo_nao_confirma_sem_tool(db_session, clinica_fake):
    tenant, customer, conversation = _context(db_session, clinica_fake)
    provider = FakeProvider(
        [{"content": "Seu agendamento está confirmado para amanhã."}]
    )
    reply = agent.generate_reply(db_session, tenant, customer, conversation, provider)
    assert "Ainda não confirmei" in reply


def test_modelo_confirma_apos_escrita_bem_sucedida(
    db_session, clinica_fake, monkeypatch
):
    tenant, customer, conversation = _context(db_session, clinica_fake)
    monkeypatch.setattr(agent, "execute_tool", lambda *_: {"success": True})
    provider = FakeProvider(
        [
            {"tool_calls": [{"id": "call-1", "function": {
                "name": "createAppointment", "arguments": "{}"}}]},
            {"content": "Seu agendamento está confirmado para amanhã."},
        ]
    )
    reply = agent.generate_reply(db_session, tenant, customer, conversation, provider)
    assert reply == "Seu agendamento está confirmado para amanhã."


def test_modelo_nao_confirma_quando_escrita_falha(
    db_session, clinica_fake, monkeypatch
):
    tenant, customer, conversation = _context(db_session, clinica_fake)
    monkeypatch.setattr(
        agent, "execute_tool", lambda *_: {"error": "Horário indisponível"}
    )
    provider = FakeProvider(
        [
            {"tool_calls": [{"id": "call-1", "function": {
                "name": "createAppointment", "arguments": "{}"}}]},
            {"content": "Seu agendamento está confirmado para amanhã."},
        ]
    )
    reply = agent.generate_reply(db_session, tenant, customer, conversation, provider)
    assert "Ainda não confirmei" in reply
