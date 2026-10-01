"""Vídeo institucional: intenção da IA, isolamento e falhas do canal."""

import json
import httpx

from config import settings
from models import ConfiguracaoNegocio, Conversa, Mensagem, Paciente
from services import presentation
from services.ai.agent import generate_reply
from services.ai.tools import ToolContext, execute_tool, tool_definitions
from services.whatsapp import WhatsAppService


class FakeWhatsApp:
    sent = []
    video_success = True

    def enviar_mensagem(self, instance, phone, text):
        self.sent.append(("text", instance, phone, text))
        return {"success": True}

    def enviar_video(self, instance, phone, url, caption):
        self.sent.append(("video", instance, phone, url, caption))
        return {"success": self.video_success, "status": 502 if not self.video_success else 201}


class FakeProvider:
    def __init__(self, tool=True, last_text="Se quiser, posso explicar os planos ou ajudar no cadastro."):
        self.tool = tool
        self.last_text = last_text
        self.calls = 0

    def chat_with_tools(self, messages, tools, *, tenant_id=None):
        self.calls += 1
        if self.tool and self.calls == 1:
            assert "sendRecepiaPresentation" in {t["function"]["name"] for t in tools}
            return {
                "role": "assistant", "content": None,
                "tool_calls": [{"id": "video-call", "type": "function",
                                "function": {"name": "sendRecepiaPresentation", "arguments": "{}"}}],
            }
        return {"role": "assistant", "content": self.last_text}


def setup_conversation(db_session, clinica_fake, text):
    tenant = clinica_fake["clinica"]
    tenant.tipo_negocio = "RECEPIA"
    customer = Paciente(clinica_id=tenant.id, nome="Cliente", telefone="5511999998888")
    db_session.add(customer)
    db_session.flush()
    conversation = Conversa(clinica_id=tenant.id, paciente_id=customer.id)
    db_session.add(conversation)
    db_session.flush()
    db_session.add(Mensagem(
        clinica_id=tenant.id, conversa_id=conversation.id,
        direcao="IN", conteudo=text,
    ))
    db_session.commit()
    return tenant, customer, conversation


def enable_video(monkeypatch, tmp_path):
    media = tmp_path / "recepia-apresentacao.mp4"
    media.write_bytes(b"real video fixture" * 100)
    monkeypatch.setattr(presentation, "VIDEO_PATH", media)
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "https://recepia.example")
    FakeWhatsApp.sent = []
    FakeWhatsApp.video_success = True
    monkeypatch.setattr(presentation, "WhatsAppService", FakeWhatsApp)


def test_como_funciona_envia_video_e_continua_atendimento(db_session, clinica_fake, monkeypatch, tmp_path):
    enable_video(monkeypatch, tmp_path)
    tenant, customer, conversation = setup_conversation(db_session, clinica_fake, "Como funciona o Recepia?")
    reply = generate_reply(db_session, tenant, customer, conversation, provider=FakeProvider())
    assert "planos" in reply
    assert [item[0] for item in FakeWhatsApp.sent] == ["text", "video"]
    assert FakeWhatsApp.sent[1][3] == "https://recepia.example/media/recepia-apresentacao.mp4"
    assert db_session.query(Mensagem).filter(
        Mensagem.clinica_id == tenant.id, Mensagem.conversa_id == conversation.id,
        Mensagem.tipo == "VIDEO",
    ).count() == 1


def test_pedido_de_video_envia_uma_vez_por_janela(db_session, clinica_fake, monkeypatch, tmp_path):
    enable_video(monkeypatch, tmp_path)
    tenant, customer, conversation = setup_conversation(db_session, clinica_fake, "Tem vídeo de apresentação?")
    ctx = ToolContext(db=db_session, clinica=tenant, paciente=customer, conversa=conversation)
    assert execute_tool("sendRecepiaPresentation", "{}", ctx)["success"] is True
    db_session.add(Mensagem(clinica_id=tenant.id, conversa_id=conversation.id,
                            direcao="IN", conteudo="Me explica o Recepia"))
    db_session.commit()
    second = execute_tool("sendRecepiaPresentation", "{}", ToolContext(
        db=db_session, clinica=tenant, paciente=customer, conversa=conversation,
    ))
    assert second["reason"] == "recent"
    assert [item[0] for item in FakeWhatsApp.sent].count("video") == 1


def test_pergunta_de_preco_nao_envia_video(db_session, clinica_fake, monkeypatch, tmp_path):
    enable_video(monkeypatch, tmp_path)
    tenant, customer, conversation = setup_conversation(db_session, clinica_fake, "Qual o valor?")
    reply = generate_reply(db_session, tenant, customer, conversation,
                           provider=FakeProvider(tool=False, last_text="O plano Essencial custa R$ 97/mês."))
    assert "R$ 97" in reply
    assert FakeWhatsApp.sent == []


def test_pedido_explicito_permite_reenvio(db_session, clinica_fake, monkeypatch, tmp_path):
    enable_video(monkeypatch, tmp_path)
    tenant, customer, conversation = setup_conversation(db_session, clinica_fake, "Tem vídeo de apresentação?")
    def context():
        return ToolContext(db=db_session, clinica=tenant, paciente=customer, conversa=conversation)
    assert execute_tool("sendRecepiaPresentation", "{}", context())["success"] is True
    db_session.add(Mensagem(clinica_id=tenant.id, conversa_id=conversation.id,
                            direcao="IN", conteudo="Me manda o vídeo de novo"))
    db_session.commit()
    assert execute_tool("sendRecepiaPresentation", "{}", context())["success"] is True
    assert [item[0] for item in FakeWhatsApp.sent].count("video") == 2


def test_falha_de_arquivo_ou_envio_continua_por_texto(db_session, clinica_fake, monkeypatch, tmp_path):
    enable_video(monkeypatch, tmp_path)
    tenant, customer, conversation = setup_conversation(db_session, clinica_fake, "Tem vídeo?")
    monkeypatch.setattr(presentation, "VIDEO_PATH", tmp_path / "missing.mp4")
    reply = generate_reply(db_session, tenant, customer, conversation,
                           provider=FakeProvider(last_text="Enviei o vídeo!"))
    assert "Posso te explicar por aqui" in reply
    assert FakeWhatsApp.sent == []
    enable_video(monkeypatch, tmp_path)
    FakeWhatsApp.video_success = False
    reply = generate_reply(db_session, tenant, customer, conversation,
                           provider=FakeProvider(last_text="Enviei o vídeo!"))
    assert "Posso te explicar por aqui" in reply
    assert [item[0] for item in FakeWhatsApp.sent] == ["text", "video"]


def test_tenant_comum_nao_tem_tool_nem_altera_configuracao(client, db_session, clinica_fake, auth_headers_a):
    tenant = clinica_fake["clinica"]
    assert "sendRecepiaPresentation" not in {t["function"]["name"] for t in tool_definitions(tenant.tipo_negocio)}
    result = client.patch("/api/negocio/configuracao", headers=auth_headers_a,
                          json={"video_apresentacao_ativo": False})
    assert result.status_code == 403
    assert db_session.query(ConfiguracaoNegocio).filter(
        ConfiguracaoNegocio.clinica_id == tenant.id
    ).count() == 0


def test_tool_somente_tenant_recepia(db_session, clinica_fake):
    tenant = clinica_fake["clinica"]
    tenant.tipo_negocio = "RECEPIA"
    assert "sendRecepiaPresentation" in {t["function"]["name"] for t in tool_definitions("RECEPIA")}
    tenant.tipo_negocio = "OTHER"
    customer = Paciente(clinica_id=tenant.id, nome="Cliente", telefone="5511999998888")
    db_session.add(customer)
    db_session.flush()
    conversation = Conversa(clinica_id=tenant.id, paciente_id=customer.id)
    db_session.add(conversation)
    db_session.commit()
    result = execute_tool("sendRecepiaPresentation", json.dumps({}), ToolContext(
        db=db_session, clinica=tenant, paciente=customer, conversa=conversation,
    ))
    assert result["error"] == "Ferramenta não permitida"


def test_rota_publica_serve_apenas_o_mp4(client, monkeypatch, tmp_path):
    media = tmp_path / "recepia-apresentacao.mp4"
    media.write_bytes(b"mp4 demonstration" * 100)
    monkeypatch.setattr(presentation, "VIDEO_PATH", media)
    response = client.get("/media/recepia-apresentacao.mp4")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("video/mp4")
    assert response.content == media.read_bytes()
    assert client.head("/media/recepia-apresentacao.mp4").status_code == 200
    assert client.get("/media/../.env").status_code == 404


def test_evolution_recebe_payload_de_video_por_url(monkeypatch):
    captured = {}

    def fake_post(_self, url, *, json, headers):
        captured.update({"url": url, "body": json, "headers": headers})
        return httpx.Response(201, json={"key": {"id": "media-test"}},
                              request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    result = WhatsAppService().enviar_video(
        "instancia-demo", "+55 (11) 99999-8888",
        "https://recepia.example/media/recepia-apresentacao.mp4", "Legenda",
    )
    assert result["success"] is True
    assert captured["url"].endswith("/message/sendMedia/instancia-demo")
    assert captured["body"] == {
        "number": "5511999998888", "mediatype": "video", "mimetype": "video/mp4",
        "media": "https://recepia.example/media/recepia-apresentacao.mp4",
        "fileName": "recepia-apresentacao.mp4", "caption": "Legenda",
    }


def test_configuracao_pode_desabilitar_video(db_session, clinica_fake, monkeypatch, tmp_path):
    enable_video(monkeypatch, tmp_path)
    tenant, customer, conversation = setup_conversation(db_session, clinica_fake, "Me mostra o sistema")
    db_session.add(ConfiguracaoNegocio(
        clinica_id=tenant.id, video_apresentacao_ativo=False,
    ))
    db_session.commit()
    result = execute_tool("sendRecepiaPresentation", "{}", ToolContext(
        db=db_session, clinica=tenant, paciente=customer, conversa=conversation,
    ))
    assert result["reason"] == "disabled"
    assert FakeWhatsApp.sent == []
