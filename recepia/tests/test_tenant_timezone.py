"""Datas sem offset usam o timezone do tenant nas APIs de agenda."""

from datetime import datetime

from models import Agendamento, BloqueioAgenda


def test_agendamento_e_filtro_de_dia_usam_timezone_do_tenant(
    client, db_session, clinica_fake, auth_headers_a
):
    clinica = clinica_fake["clinica"]
    clinica.timezone = "UTC"
    db_session.commit()
    paciente = client.post(
        "/api/pacientes",
        headers=auth_headers_a,
        json={"nome": "Cliente UTC", "telefone": "5511999988888"},
    ).json()
    resposta = client.post(
        "/api/agendamentos",
        headers=auth_headers_a,
        json={
            "paciente_id": paciente["id"],
            "data_hora": "2026-10-01T00:30:00",
            "duracao_minutos": 30,
        },
    )
    assert resposta.status_code == 201
    salvo = db_session.get(Agendamento, resposta.json()["id"])
    assert salvo.data_hora == datetime(2026, 10, 1, 0, 30)
    agenda = client.get("/api/agendamentos?data=2026-10-01", headers=auth_headers_a)
    assert [item["id"] for item in agenda.json()] == [salvo.id]


def test_bloqueio_e_filtro_usam_timezone_do_tenant(
    client, db_session, clinica_fake, auth_headers_a
):
    clinica = clinica_fake["clinica"]
    clinica.timezone = "UTC"
    db_session.commit()
    resposta = client.post(
        "/api/bloqueios",
        headers=auth_headers_a,
        json={"inicio": "2026-10-01T00:15:00", "fim": "2026-10-01T00:45:00"},
    )
    assert resposta.status_code == 201
    salvo = db_session.get(BloqueioAgenda, resposta.json()["id"])
    assert salvo.inicio == datetime(2026, 10, 1, 0, 15)
    bloqueios = client.get(
        "/api/bloqueios?data_inicio=2026-10-01&data_fim=2026-10-01",
        headers=auth_headers_a,
    )
    assert [item["id"] for item in bloqueios.json()] == [salvo.id]
