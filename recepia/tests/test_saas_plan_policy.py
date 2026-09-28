"""Planos e trial permanecem informativos enquanto a cobrança está desligada."""

from datetime import date, timedelta

from config import settings
from models import Plano


def test_plano_e_trial_nao_bloqueiam_operacao_por_padrao(
    client, db_session, clinica_fake, auth_headers_a, monkeypatch
):
    monkeypatch.setattr(settings, "SAAS_LIMITS_ENABLED", False)
    tenant = clinica_fake["clinica"]
    tenant.plano = Plano.ESSENCIAL
    tenant.trial_expira_em = date.today() - timedelta(days=1)
    db_session.commit()
    for number in range(3):
        response = client.post(
            "/api/profissionais",
            headers=auth_headers_a,
            json={"nome": f"Profissional {number}"},
        )
        assert response.status_code == 201
