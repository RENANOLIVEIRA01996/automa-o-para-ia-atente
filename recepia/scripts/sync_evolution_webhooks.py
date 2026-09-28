"""Reaponta webhooks de instâncias já presentes na Evolution.

Uso manual após trocar PUBLIC_WEBHOOK_URL. Não cria nem remove instâncias.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    parser = argparse.ArgumentParser(description="Sincronizar webhooks Evolution")
    parser.add_argument("--apply", action="store_true", help="alterar webhooks de instâncias existentes")
    args = parser.parse_args()

    from config import settings
    from database import get_db
    from models import Clinica
    from services.whatsapp import WhatsAppService

    if not settings.PUBLIC_WEBHOOK_URL:
        parser.error("PUBLIC_WEBHOOK_URL não configurada")
    url = settings.PUBLIC_WEBHOOK_URL.rstrip("/") + "/api/webhook/evolution"
    with get_db() as db:
        names = [name for (name,) in db.query(Clinica.evolution_instance_name).filter(
            Clinica.evolution_instance_name.isnot(None),
        ).all() if name]

    if not args.apply:
        print(f"Encontradas {len(names)} empresas com instância. Nenhuma alteração feita; use --apply.")
        return

    ws = WhatsAppService()
    ok = 0
    failed = 0
    for name in names:
        if ws.configurar_webhook(name, url).get("success"):
            ok += 1
        else:
            failed += 1
    print(f"Webhooks atualizados: {ok}; falhas: {failed}.")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
