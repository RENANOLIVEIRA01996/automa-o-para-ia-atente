"""O modelo só consegue operar dados do cliente e tenant do contexto."""

import json
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from models import Conversa, HorarioFuncionamento, Paciente, Procedimento
from services.ai.tools import ToolContext, execute_tool


def test_tools_reservam_apenas_servico_do_tenant_e_evitam_conflito(
    db_session, clinica_fake, clinica_fake_b
):
    tenant = clinica_fake["clinica"]
    customer = Paciente(clinica_id=tenant.id, nome="Cliente", telefone="5511999990000")
    db_session.add(customer)
    db_session.flush()
    conversation = Conversa(clinica_id=tenant.id, paciente_id=customer.id)
    service = Procedimento(clinica_id=tenant.id, nome="Corte", duracao_minutos=30)
    foreign = Procedimento(
        clinica_id=clinica_fake_b["clinica"].id, nome="Serviço B", duracao_minutos=30
    )
    db_session.add_all([conversation, service, foreign])
    day = date.today() + timedelta(days=30)
    db_session.add(
        HorarioFuncionamento(
            clinica_id=tenant.id,
            dia_semana=day.weekday(),
            hora_inicio="09:00",
            hora_fim="18:00",
            intervalo_slot_min=30,
        )
    )
    db_session.commit()
    ctx = ToolContext(db_session, tenant, customer, conversation)
    assert "error" in execute_tool(
        "getServiceDetails", json.dumps({"service_id": foreign.id}), ctx
    )

    local = datetime.combine(day, datetime.min.time()).replace(
        hour=10, tzinfo=ZoneInfo(tenant.timezone)
    )
    start = local.astimezone(timezone.utc).isoformat()
    args = json.dumps(
        {"service_id": service.id, "starts_at": start, "tenant_id": foreign.clinica_id}
    )
    first = execute_tool("createAppointment", args, ctx)
    assert first["success"] is True
    assert "error" in execute_tool("createAppointment", args, ctx)
    assert "error" in execute_tool(
        "cancelAppointment", json.dumps({"appointment_id": "foreign"}), ctx
    )
    assert execute_tool(
        "cancelAppointment",
        json.dumps({"appointment_id": first["appointment"]["id"]}),
        ctx,
    )["success"]


def test_tool_human_support_impede_ia(db_session, clinica_fake):
    tenant = clinica_fake["clinica"]
    customer = Paciente(clinica_id=tenant.id, nome="Cliente", telefone="5511999990000")
    db_session.add(customer)
    db_session.flush()
    conversation = Conversa(clinica_id=tenant.id, paciente_id=customer.id)
    db_session.add(conversation)
    db_session.commit()
    result = execute_tool(
        "requestHumanSupport",
        "{}",
        ToolContext(db_session, tenant, customer, conversation),
    )
    assert result == {"success": True, "human_takeover": True}
    assert conversation.atendimento_humano is True
