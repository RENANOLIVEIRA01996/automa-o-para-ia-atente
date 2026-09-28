"""Aplica o esquema aditivo existente somente com --apply explícito.

Executar após backup/ensaio em uma branch Neon. Não faz deploy.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    parser = argparse.ArgumentParser(description="Preparar banco da Recepia após backup")
    parser.add_argument("--apply", action="store_true", help="executar create_all e migrações aditivas")
    args = parser.parse_args()
    if not args.apply:
        parser.error("nenhuma alteração feita; use --apply após backup e ensaio")

    from database import init_db

    init_db()
    print("Esquema Recepia preparado.")


if __name__ == "__main__":
    main()
