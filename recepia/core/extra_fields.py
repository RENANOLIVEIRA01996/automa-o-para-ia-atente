"""Validate optional JSON fields against the tenant's segment preset."""

from math import isfinite

from core.segments import get_segment_config


def merge_extra_fields(
    current: dict | None,
    incoming: dict,
    business_type: str,
    entity: str,
) -> dict:
    definitions = {
        item["key"]: item
        for item in get_segment_config(business_type)["extra_fields"][entity]
        if item["type"] != "entity"
    }
    if len(incoming) > 20:
        raise ValueError("Campos adicionais excedem o limite")
    result = dict(current or {})
    for key, value in incoming.items():
        if key not in definitions:
            raise ValueError(f"Campo adicional desconhecido: {key}")
        kind = definitions[key]["type"]
        if value is not None and value != "":
            if kind == "number":
                if (isinstance(value, bool) or not isinstance(value, (int, float))
                        or not isfinite(value)):
                    raise ValueError(f"Campo numérico inválido: {key}")
            elif not isinstance(value, str):
                raise ValueError(f"Campo de texto inválido: {key}")
            if len(str(value)) > 500:
                raise ValueError(f"Campo adicional muito longo: {key}")
            result[key] = value
        else:
            result.pop(key, None)
    return result
