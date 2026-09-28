"""Valida a camada comercial sobre o schema legado sem acesso entre tenants."""


def test_empresa_e_configuracao_isoladas(client, auth_headers_a, auth_headers_b):
    resp = client.patch(
        "/api/negocio",
        headers=auth_headers_a,
        json={
            "nome": "Barbearia A",
            "slug": "barbearia-a",
            "tipo_negocio": "barbershop",
            "timezone": "America/Sao_Paulo",
            "endereco_rua": "Rua das Flores",
            "endereco_numero": "10",
            "endereco_cidade": "São Paulo",
            "endereco_uf": "SP",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["tipo_negocio"] == "BARBERSHOP"
    assert resp.json()["endereco_rua"] == "Rua das Flores"
    assert (
        client.get("/api/negocio", headers=auth_headers_b).json()["nome"]
        != "Barbearia A"
    )

    resp = client.patch(
        "/api/negocio/configuracao",
        headers=auth_headers_a,
        json={"descricao": "Cortes e barba", "politica_cancelamento": "Avisar com 24h"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["descricao"] == "Cortes e barba"
    assert (
        client.get("/api/negocio/configuracao", headers=auth_headers_b).json() is None
    )


def test_servico_com_preco_e_referencia_tenant(client, auth_headers_a, auth_headers_b):
    resp = client.post(
        "/api/procedimentos",
        headers=auth_headers_a,
        json={
            "nome": "Corte",
            "duracao_minutos": 45,
            "descricao": "Corte masculino",
            "preco": "55.90",
        },
    )
    assert resp.status_code == 201, resp.text
    servico = resp.json()
    assert servico["preco"] == "55.90"
    assert servico["descricao"] == "Corte masculino"

    cliente_b = client.post(
        "/api/pacientes",
        headers=auth_headers_b,
        json={"nome": "Cliente B", "telefone": "11988887777"},
    )
    assert cliente_b.status_code == 201, cliente_b.text
    resp = client.post(
        "/api/agendamentos",
        headers=auth_headers_b,
        json={
            "paciente_id": cliente_b.json()["id"],
            "data_hora": "2030-10-15T14:00:00Z",
            "procedimento_id": servico["id"],
        },
    )
    assert resp.status_code == 404


def test_signup_generico_sem_dados_clinicos(client):
    from core.limiter import limiter

    anterior = limiter.enabled
    limiter.enabled = False
    try:
        resp = client.post(
            "/api/signup",
            json={
                "nome_clinica": "Oficina Exemplo",
                "tipo_negocio": "AUTO_REPAIR",
                "nome_responsavel": "Responsável",
                "email": "dono@oficina.example",
                "telefone": "11988889999",
                "senha": "senha-segura-123",
                "aceito_termos": True,
            },
        )
    finally:
        limiter.enabled = anterior
    assert resp.status_code == 201, resp.text
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    empresa = client.get("/api/negocio", headers=headers)
    assert empresa.json()["tipo_negocio"] == "AUTO_REPAIR"
    assert (
        client.post(
            "/api/pacientes",
            headers=headers,
            json={"nome": "Cliente da oficina", "telefone": "11977776666"},
        ).status_code
        == 201
    )
