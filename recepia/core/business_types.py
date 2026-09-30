"""Business type validation backed by the shared segment catalog."""

from core.segments import SEGMENT_PRESETS

BUSINESS_TYPES = frozenset(SEGMENT_PRESETS)
INTERNAL_BUSINESS_TYPES = frozenset({"RECEPIA"})
PUBLIC_BUSINESS_TYPES = BUSINESS_TYPES - INTERNAL_BUSINESS_TYPES


def normalize_business_type(value: str) -> str:
    value = value.strip().upper()
    if value not in BUSINESS_TYPES:
        raise ValueError("Tipo de negócio inválido")
    return value
