"""The shared segment catalog drives tenant navigation and terminology."""

from core.segments import SEGMENT_PRESETS, get_segment_config


def test_all_presets_have_resolved_navigation_and_no_shared_mutation():
    assert len(SEGMENT_PRESETS) == 10
    for code in SEGMENT_PRESETS:
        config = get_segment_config(code)
        assert config["business_type"] == code
        assert config["dashboard"]["cards"]
        assert config["navigation"][0]["id"] == "overview"
        assert all(item["label"] and item["icon"] for item in config["navigation"])
    car_wash = get_segment_config("CAR_WASH")
    clinic = get_segment_config("CLINIC")
    barber = get_segment_config("BARBERSHOP")
    assert "vehicles" in {item["id"] for item in car_wash["navigation"]}
    assert "history" not in {item["id"] for item in car_wash["navigation"]}
    assert clinic["labels"]["customers"] == "Pacientes"
    assert barber["labels"]["professionals"] == "Barbeiros"
    car_wash["labels"]["customers"] = "Alterado"
    assert get_segment_config("CAR_WASH")["labels"]["customers"] == "Clientes"


def test_segment_endpoint_changes_with_authenticated_tenant(
    client, auth_headers_a, auth_headers_b
):
    for code, expected in (
        ("CAR_WASH", "Veículos"),
        ("CLINIC", "Histórico clínico"),
        ("BARBERSHOP", "Barbeiros"),
    ):
        updated = client.patch(
            "/api/negocio", headers=auth_headers_a, json={"tipo_negocio": code}
        )
        assert updated.status_code == 200, updated.text
        config = client.get("/api/negocio/segmento", headers=auth_headers_a)
        assert config.status_code == 200, config.text
        assert expected in {item["label"] for item in config.json()["navigation"]}
        assert config.json()["business_type"] == code
    other = client.get("/api/negocio/segmento", headers=auth_headers_b)
    assert other.status_code == 200
    assert other.json()["business_type"] != "BARBERSHOP"


def test_car_wash_vehicle_scoped_and_linked_to_appointment(
    client, auth_headers_a, auth_headers_b
):
    client.patch(
        "/api/negocio", headers=auth_headers_a, json={"tipo_negocio": "CAR_WASH"}
    )
    customer = client.post(
        "/api/pacientes",
        headers=auth_headers_a,
        json={"nome": "João Cliente", "telefone": "11988887777"},
    )
    assert customer.status_code == 201, customer.text
    customer_id = customer.json()["id"]
    vehicle = client.post(
        "/api/veiculos",
        headers=auth_headers_a,
        json={
            "paciente_id": customer_id,
            "placa": "ABC-1D23",
            "marca": "Fiat",
            "modelo": "Argo",
            "ano": 2020,
            "cor": "Branco",
        },
    )
    assert vehicle.status_code == 201, vehicle.text
    assert vehicle.json()["placa"] == "ABC1D23"
    vehicle_id = vehicle.json()["id"]
    assert client.get("/api/veiculos", headers=auth_headers_b).status_code == 404
    service = client.post(
        "/api/procedimentos",
        headers=auth_headers_a,
        json={"nome": "Lavagem completa", "duracao_minutos": 90},
    )
    assert service.status_code == 201, service.text
    booked = client.post(
        "/api/agendamentos",
        headers=auth_headers_a,
        json={
            "paciente_id": customer_id,
            "veiculo_id": vehicle_id,
            "procedimento_id": service.json()["id"],
            "data_hora": "2030-10-15T14:00:00Z",
        },
    )
    assert booked.status_code == 201, booked.text
    assert booked.json()["veiculo_id"] == vehicle_id
    assert (
        client.delete(f"/api/veiculos/{vehicle_id}", headers=auth_headers_a).status_code
        == 204
    )
    historical = client.get(
        f"/api/agendamentos/{booked.json()['id']}", headers=auth_headers_a
    )
    assert historical.json()["veiculo_id"] == vehicle_id
    assert client.get("/api/veiculos", headers=auth_headers_a).json() == []


def test_service_delete_keeps_booking_history(client, auth_headers_a):
    customer = client.post(
        "/api/pacientes",
        headers=auth_headers_a,
        json={"nome": "Ana Cliente", "telefone": "11977776666"},
    )
    service = client.post(
        "/api/procedimentos",
        headers=auth_headers_a,
        json={"nome": "Lavagem premium", "duracao_minutos": 90, "preco": "75.00"},
    )
    assert customer.status_code == service.status_code == 201
    service_id = service.json()["id"]
    booked = client.post(
        "/api/agendamentos",
        headers=auth_headers_a,
        json={
            "paciente_id": customer.json()["id"],
            "procedimento_id": service_id,
            "data_hora": "2030-10-15T14:00:00Z",
        },
    )
    assert booked.status_code == 201, booked.text
    assert (
        client.delete(
            f"/api/procedimentos/{service_id}", headers=auth_headers_a
        ).status_code
        == 204
    )
    active = client.get("/api/procedimentos", headers=auth_headers_a).json()
    all_services = client.get(
        "/api/procedimentos?apenas_ativos=false", headers=auth_headers_a
    ).json()
    assert service_id not in {item["id"] for item in active}
    assert any(item["id"] == service_id and not item["ativo"] for item in all_services)
    historical = client.get(
        f"/api/agendamentos/{booked.json()['id']}", headers=auth_headers_a
    )
    assert historical.json()["procedimento_id"] == service_id


def test_car_wash_dashboard_counts_real_statuses(client, auth_headers_a):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    client.patch(
        "/api/negocio", headers=auth_headers_a, json={"tipo_negocio": "CAR_WASH"}
    )
    customer = client.post(
        "/api/pacientes",
        headers=auth_headers_a,
        json={"nome": "Carlos Lima", "telefone": "11966665555"},
    )
    service = client.post(
        "/api/procedimentos",
        headers=auth_headers_a,
        json={"nome": "Lavagem simples", "duracao_minutos": 90, "preco": "50.00"},
    )
    assert customer.status_code == service.status_code == 201
    vehicle = client.post(
        "/api/veiculos",
        headers=auth_headers_a,
        json={"paciente_id": customer.json()["id"], "placa": "XYZ2A34"},
    )
    assert vehicle.status_code == 201, vehicle.text
    local_today = datetime.now(ZoneInfo("America/Sao_Paulo")).replace(
        hour=14, minute=0, second=0, microsecond=0
    )
    booking = client.post(
        "/api/agendamentos",
        headers=auth_headers_a,
        json={
            "paciente_id": customer.json()["id"],
            "veiculo_id": vehicle.json()["id"],
            "procedimento_id": service.json()["id"],
            "data_hora": local_today.isoformat(),
        },
    )
    assert booking.status_code == 201, booking.text
    booking_id = booking.json()["id"]
    started = client.put(
        f"/api/agendamentos/{booking_id}",
        headers=auth_headers_a,
        json={"status": "em_andamento"},
    )
    assert started.status_code == 200, started.text
    metrics = client.get("/api/negocio/indicadores", headers=auth_headers_a)
    assert metrics.status_code == 200, metrics.text
    assert metrics.json()["em_andamento_hoje"] == 1
    finished = client.put(
        f"/api/agendamentos/{booking_id}",
        headers=auth_headers_a,
        json={"status": "realizado"},
    )
    assert finished.status_code == 200, finished.text
    metrics = client.get("/api/negocio/indicadores", headers=auth_headers_a).json()
    assert metrics["concluidos_hoje"] == 1
    assert metrics["receita_hoje"] == 50.0
    changed_price = client.put(
        f"/api/procedimentos/{service.json()['id']}",
        headers=auth_headers_a,
        json={"preco": "80.00"},
    )
    assert changed_price.status_code == 200
    stable = client.get("/api/negocio/indicadores", headers=auth_headers_a).json()
    assert stable["receita_hoje"] == 50.0


def test_car_wash_agent_requires_own_vehicle(db_session, clinica_fake):
    import json
    from datetime import date, datetime, timedelta, timezone
    from zoneinfo import ZoneInfo

    from models import Conversa, HorarioFuncionamento, Paciente, Procedimento
    from services.ai.tools import ToolContext, execute_tool, tool_definitions

    tenant = clinica_fake["clinica"]
    tenant.tipo_negocio = "CAR_WASH"
    customer = Paciente(clinica_id=tenant.id, nome="Cliente", telefone="5511999990000")
    other = Paciente(clinica_id=tenant.id, nome="Outro", telefone="5511999990001")
    db_session.add_all([customer, other])
    db_session.flush()
    conversation = Conversa(clinica_id=tenant.id, paciente_id=customer.id)
    service = Procedimento(clinica_id=tenant.id, nome="Lavagem", duracao_minutos=30)
    day = date.today() + timedelta(days=30)
    hours = HorarioFuncionamento(
        clinica_id=tenant.id,
        dia_semana=day.weekday(),
        hora_inicio="09:00",
        hora_fim="18:00",
        intervalo_slot_min=30,
    )
    db_session.add_all([conversation, service, hours])
    db_session.commit()
    names = {item["function"]["name"] for item in tool_definitions("CAR_WASH")}
    assert "registerVehicle" in names
    assert "registerVehicle" not in {
        item["function"]["name"] for item in tool_definitions("CLINIC")
    }
    ctx = ToolContext(db_session, tenant, customer, conversation)
    registered = execute_tool("registerVehicle", json.dumps({"plate": "ABC-1D23"}), ctx)
    assert registered["success"] is True
    vehicle_id = registered["vehicle_id"]
    assert (
        execute_tool("listCustomerVehicles", "{}", ctx)["vehicles"][0]["id"]
        == vehicle_id
    )
    local = datetime.combine(day, datetime.min.time()).replace(
        hour=10, tzinfo=ZoneInfo(tenant.timezone)
    )
    start = local.astimezone(timezone.utc).isoformat()
    args = {"service_id": service.id, "starts_at": start}
    assert "error" in execute_tool("createAppointment", json.dumps(args), ctx)
    args["vehicle_id"] = vehicle_id
    other_ctx = ToolContext(db_session, tenant, other, conversation)
    assert "error" in execute_tool("createAppointment", json.dumps(args), other_ctx)
    booked = execute_tool("createAppointment", json.dumps(args), ctx)
    assert booked["success"] is True
