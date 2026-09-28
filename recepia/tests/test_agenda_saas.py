"""Regressões da agenda genérica: isolamento, duração e concorrência lógica."""

from datetime import date, datetime, timedelta, timezone

from models import BloqueioAgenda, HorarioFuncionamento, Procedimento


def test_impede_sobreposicao_e_libera_apos_cancelar(client, auth_headers_a):
    p = client.post(
        "/api/pacientes",
        headers=auth_headers_a,
        json={"nome": "Cliente A", "telefone": "11999998888"},
    ).json()
    proc = client.post(
        "/api/procedimentos",
        headers=auth_headers_a,
        json={"nome": "Corte longo", "duracao_minutos": 60},
    ).json()
    inicio = "2030-10-15T14:00:00Z"
    primeiro = client.post(
        "/api/agendamentos",
        headers=auth_headers_a,
        json={
            "paciente_id": p["id"],
            "data_hora": inicio,
            "procedimento_id": proc["id"],
            "duracao_minutos": 5,
        },
    )
    assert primeiro.status_code == 201, primeiro.text
    assert primeiro.json()["duracao_minutos"] == 60

    segundo = client.post(
        "/api/agendamentos",
        headers=auth_headers_a,
        json={
            "paciente_id": p["id"],
            "data_hora": "2030-10-15T14:30:00Z",
            "procedimento_id": proc["id"],
        },
    )
    assert segundo.status_code == 409
    assert (
        client.delete(
            f"/api/agendamentos/{primeiro.json()['id']}", headers=auth_headers_a
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/agendamentos",
            headers=auth_headers_a,
            json={
                "paciente_id": p["id"],
                "data_hora": "2030-10-15T14:30:00Z",
                "procedimento_id": proc["id"],
            },
        ).status_code
        == 201
    )


def test_slots_respeitam_duracao_bloqueio_e_timezone(
    client, db_session, clinica_fake, auth_headers_a
):
    clinica = clinica_fake["clinica"]
    clinica.timezone = "America/Sao_Paulo"
    dia = date.today() + timedelta(days=30)
    db_session.add(
        HorarioFuncionamento(
            clinica_id=clinica.id,
            dia_semana=dia.weekday(),
            hora_inicio="09:00",
            hora_fim="11:00",
            intervalo_slot_min=30,
            ativo=True,
        )
    )
    proc = Procedimento(clinica_id=clinica.id, nome="Atendimento", duracao_minutos=60)
    db_session.add(proc)
    db_session.flush()
    from zoneinfo import ZoneInfo

    local = datetime.combine(dia, datetime.min.time()).replace(
        hour=9, tzinfo=ZoneInfo(clinica.timezone)
    )
    inicio_utc = local.astimezone(timezone.utc).replace(tzinfo=None)
    db_session.add(
        BloqueioAgenda(
            clinica_id=clinica.id,
            inicio=inicio_utc,
            fim=inicio_utc + timedelta(minutes=30),
        )
    )
    db_session.commit()

    resp = client.get(
        "/api/agenda/slots",
        headers=auth_headers_a,
        params={"procedimento_id": proc.id, "data": dia.isoformat()},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["timezone"] == clinica.timezone
    assert resp.json()["slots_utc"] == [
        (inicio_utc + timedelta(minutes=30)).isoformat() + "Z",
        (inicio_utc + timedelta(minutes=60)).isoformat() + "Z",
    ]


def test_jornada_e_servicos_do_profissional_sao_isolados_por_empresa(
    client, auth_headers_a, auth_headers_b
):
    profissional = client.post(
        "/api/profissionais", headers=auth_headers_a, json={"nome": "Especialista"}
    ).json()
    servico = client.post(
        "/api/procedimentos", headers=auth_headers_a,
        json={"nome": "Corte", "duracao_minutos": 30},
    ).json()
    base = f"/api/agenda/profissionais/{profissional['id']}"
    assert client.put(
        f"{base}/horarios/0", headers=auth_headers_a,
        json={"hora_inicio": "09:00", "hora_fim": "18:00"},
    ).status_code == 200
    assert client.put(
        f"{base}/servicos", headers=auth_headers_a,
        json={"procedimento_ids": [servico["id"]]},
    ).status_code == 200
    jornadas = client.get(f"{base}/horarios", headers=auth_headers_a)
    vinculos = client.get(f"{base}/servicos", headers=auth_headers_a)
    assert jornadas.json()[0]["dia_semana"] == 0
    assert vinculos.json()["procedimento_ids"] == [servico["id"]]
    assert client.get(f"{base}/horarios", headers=auth_headers_b).status_code == 404
    assert client.get(f"{base}/servicos", headers=auth_headers_b).status_code == 404
