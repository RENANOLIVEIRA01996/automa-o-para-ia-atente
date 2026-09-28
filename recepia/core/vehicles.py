"""Vehicle identifiers shared by the dashboard API and the WhatsApp agent."""

import re


def normalize_plate(value: str) -> str:
    plate = value.strip().upper().replace("-", "").replace(" ", "")
    if not re.fullmatch(r"[A-Z]{3}[0-9][A-Z0-9][0-9]{2}", plate):
        raise ValueError("Placa inválida")
    return plate
