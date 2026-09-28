"""The extra segment modules keep tenant ownership and operational state."""

import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from models import Conversa, Paciente, Quarto
from services.ai.tools import ToolContext, execute_tool, tool_definitions


def _segment(client, headers, code):
    response = client.patch(
        "/api/negocio", headers=headers, json={"tipo_negocio": code}
    )
    assert response.status_code == 200, response.text


def _customer(client, headers):
    response = client.post(
        "/api/pacientes", headers=headers,
        json={"nome": "Cliente de teste", "telefone": "11988887777"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_pet_appointment_requires_pet_of_same_tutor(client, auth_headers_a, auth_headers_b):
    _segment(client, auth_headers_a, "PET")
    tutor = _customer(client, auth_headers_a)
    other_tutor = _customer(client, auth_headers_a)
    pet = client.post(
        "/api/pets", headers=auth_headers_a,
        json={"paciente_id": tutor, "nome": "Bidu", "especie": "Cão"},
    )
    assert pet.status_code == 201, pet.text
    pet_id = pet.json()["id"]
    assert client.get("/api/pets", headers=auth_headers_b).status_code == 404
    service = client.post(
        "/api/procedimentos", headers=auth_headers_a,
        json={"nome": "Banho", "duracao_minutos": 45},
    )
    payload = {
        "paciente_id": other_tutor,
        "pet_id": pet_id,
        "procedimento_id": service.json()["id"],
        "data_hora": "2030-10-15T14:00:00Z",
    }
    assert client.post(
        "/api/agendamentos", headers=auth_headers_a, json=payload
    ).status_code == 404
    payload["paciente_id"] = tutor
    payload.pop("pet_id")
    assert client.post(
        "/api/agendamentos", headers=auth_headers_a, json=payload
    ).status_code == 422
    payload["pet_id"] = pet_id
    booked = client.post(
        "/api/agendamentos", headers=auth_headers_a, json=payload
    )
    assert booked.status_code == 201, booked.text
    assert booked.json()["pet_id"] == pet_id
    assert client.delete(f"/api/pets/{pet_id}", headers=auth_headers_a).status_code == 204
    assert client.get(
        f"/api/agendamentos/{booked.json()['id']}", headers=auth_headers_a
    ).json()["pet_id"] == pet_id
    names = {tool["function"]["name"] for tool in tool_definitions("PET")}
    assert {"listCustomerPets", "registerPet", "createAppointment"} <= names
    assert "createHotelReservation" not in names


def test_auto_repair_order_and_indicators(client, auth_headers_a, auth_headers_b):
    _segment(client, auth_headers_a, "AUTO_REPAIR")
    customer = _customer(client, auth_headers_a)
    vehicle = client.post(
        "/api/veiculos", headers=auth_headers_a,
        json={"paciente_id": customer, "placa": "ABC1D23"},
    )
    assert vehicle.status_code == 201, vehicle.text
    order = client.post(
        "/api/ordens-servico", headers=auth_headers_a,
        json={"paciente_id": customer, "veiculo_id": vehicle.json()["id"],
              "descricao": "Trocar óleo", "valor": "150.00"},
    )
    assert order.status_code == 201, order.text
    metrics = client.get("/api/negocio/indicadores", headers=auth_headers_a).json()
    assert metrics["ordens_abertas"] == 1
    assert metrics["receita_estimada"] == 150
    updated = client.patch(
        f"/api/ordens-servico/{order.json()['id']}", headers=auth_headers_a,
        json={"status": "EM_ANDAMENTO"},
    )
    assert updated.status_code == 200, updated.text
    assert client.get("/api/negocio/indicadores", headers=auth_headers_a).json()[
        "veiculos_em_servico"
    ] == 1
    _segment(client, auth_headers_b, "AUTO_REPAIR")
    assert client.get("/api/ordens-servico", headers=auth_headers_b).json() == []
    assert client.patch(
        f"/api/ordens-servico/{order.json()['id']}", headers=auth_headers_b,
        json={"status": "CONCLUIDA"},
    ).status_code == 404


def test_hotel_reservation_conflict_transitions_and_tenant_scope(
    client, auth_headers_a, auth_headers_b
):
    _segment(client, auth_headers_a, "HOTEL")
    _segment(client, auth_headers_b, "HOTEL")
    guest = _customer(client, auth_headers_a)
    room = client.post(
        "/api/quartos", headers=auth_headers_a,
        json={"numero": "101", "categoria": "Standard", "capacidade": 2,
              "valor_diaria": "200.00"},
    )
    assert room.status_code == 201, room.text
    assert client.get("/api/quartos", headers=auth_headers_b).json() == []
    start = date.today() + timedelta(days=30)
    payload = {"paciente_id": guest, "quarto_id": room.json()["id"],
               "check_in": start.isoformat(),
               "check_out": (start + timedelta(days=2)).isoformat()}
    booked = client.post("/api/reservas-hotel", headers=auth_headers_a, json=payload)
    assert booked.status_code == 201, booked.text
    assert float(booked.json()["valor_previsto"]) == 400
    assert client.post(
        "/api/reservas-hotel", headers=auth_headers_a, json=payload
    ).status_code == 409
    assert client.get("/api/reservas-hotel", headers=auth_headers_b).json() == []
    assert client.delete(
        f"/api/quartos/{room.json()['id']}", headers=auth_headers_a
    ).status_code == 409
    reservation_id = booked.json()["id"]
    assert client.patch(
        f"/api/reservas-hotel/{reservation_id}", headers=auth_headers_b,
        json={"status": "CANCELADA"},
    ).status_code == 404
    cancelled = client.patch(
        f"/api/reservas-hotel/{reservation_id}", headers=auth_headers_a,
        json={"status": "CANCELADA"},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert client.post(
        "/api/reservas-hotel", headers=auth_headers_a, json=payload
    ).status_code == 201
    today = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    today_booking = client.post(
        "/api/reservas-hotel", headers=auth_headers_a,
        json={**payload, "check_in": today.isoformat(),
              "check_out": (today + timedelta(days=1)).isoformat()},
    )
    assert today_booking.status_code == 201, today_booking.text
    metrics = client.get("/api/negocio/indicadores", headers=auth_headers_a).json()
    assert metrics["reservas_ativas"] == 2
    assert metrics["checkins_hoje"] == 1
    assert metrics["quartos_ocupados"] == 0
    assert metrics["quartos_disponiveis"] == 0
    checked_in = client.patch(
        f"/api/reservas-hotel/{today_booking.json()['id']}",
        headers=auth_headers_a, json={"status": "CHECK_IN"},
    )
    assert checked_in.status_code == 200, checked_in.text
    assert client.get("/api/negocio/indicadores", headers=auth_headers_a).json()[
        "quartos_ocupados"
    ] == 1
    names = {tool["function"]["name"] for tool in tool_definitions("HOTEL")}
    assert {"checkRoomAvailability", "createHotelReservation"} <= names
    assert "createAppointment" not in names


def test_hotel_ai_checks_availability_and_writes_only_own_booking(
    db_session, clinica_fake, clinica_fake_b
):
    tenant = clinica_fake["clinica"]
    tenant.tipo_negocio = "HOTEL"
    customer = Paciente(
        clinica_id=tenant.id, nome="Hóspede", telefone="11999998888"
    )
    db_session.add(customer)
    db_session.flush()
    conversation = Conversa(clinica_id=tenant.id, paciente_id=customer.id)
    room = Quarto(
        clinica_id=tenant.id, numero="201", capacidade=2, valor_diaria=120
    )
    foreign = Quarto(
        clinica_id=clinica_fake_b["clinica"].id, numero="301", capacidade=2
    )
    db_session.add_all([conversation, room, foreign])
    db_session.commit()
    ctx = ToolContext(db_session, tenant, customer, conversation)
    start = date.today() + timedelta(days=45)
    dates = {"check_in": start.isoformat(),
             "check_out": (start + timedelta(days=3)).isoformat()}
    assert execute_tool(
        "checkRoomAvailability", json.dumps({**dates, "room_id": foreign.id}), ctx
    ) == {"rooms": []}
    available = execute_tool(
        "checkRoomAvailability", json.dumps({**dates, "room_id": room.id}), ctx
    )
    assert available["rooms"][0]["total_estimate"] == "360.00"
    booked = execute_tool(
        "createHotelReservation", json.dumps({**dates, "room_id": room.id}), ctx
    )
    assert booked["success"] is True
    assert "error" in execute_tool(
        "createHotelReservation", json.dumps({**dates, "room_id": room.id}), ctx
    )
    reservations = execute_tool("findCustomerReservations", "{}", ctx)
    assert reservations["reservations"][0]["id"] == booked["reservation_id"]


def test_consulting_extra_fields_round_trip_and_segment_switch(
    client, auth_headers_a
):
    _segment(client, auth_headers_a, "CONSULTING")
    business = client.patch(
        "/api/negocio", headers=auth_headers_a,
        json={"campos_extras": {"area_atuacao": "Tecnologia"}},
    )
    assert business.status_code == 200, business.text
    assert business.json()["campos_extras"]["area_atuacao"] == "Tecnologia"
    customer = client.post(
        "/api/pacientes", headers=auth_headers_a,
        json={"nome": "Cliente Consultoria", "telefone": "11988887777",
              "campos_extras": {"empresa": "Acme"}},
    )
    assert customer.status_code == 201, customer.text
    assert customer.json()["campos_extras"]["empresa"] == "Acme"
    assert client.post(
        "/api/pacientes", headers=auth_headers_a,
        json={"nome": "Outro Cliente", "telefone": "11988887776",
              "campos_extras": {"campo_desconhecido": "x"}},
    ).status_code == 422
    service = client.post(
        "/api/procedimentos", headers=auth_headers_a,
        json={"nome": "Reunião inicial", "duracao_minutos": 60},
    )
    booked = client.post(
        "/api/agendamentos", headers=auth_headers_a,
        json={"paciente_id": customer.json()["id"],
              "procedimento_id": service.json()["id"],
              "data_hora": "2030-10-16T14:00:00Z",
              "campos_extras": {"assunto": "Planejamento"}},
    )
    assert booked.status_code == 201, booked.text
    assert booked.json()["campos_extras"]["assunto"] == "Planejamento"
    _segment(client, auth_headers_a, "BARBERSHOP")
    historical = client.get(
        f"/api/agendamentos/{booked.json()['id']}", headers=auth_headers_a
    )
    assert historical.json()["campos_extras"]["assunto"] == "Planejamento"
    assert client.get(
        f"/api/pacientes/{customer.json()['id']}", headers=auth_headers_a
    ).json()["campos_extras"]["empresa"] == "Acme"
