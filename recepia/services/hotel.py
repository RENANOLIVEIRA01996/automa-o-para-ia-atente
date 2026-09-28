"""Shared hotel availability rules for the API and WhatsApp agent."""

from datetime import date

from sqlalchemy.orm import Session

from models import ReservaHotel


def reservation_conflict(
    db: Session,
    clinica_id: str,
    room_id: str,
    check_in: date,
    check_out: date,
    exclude_id: str | None = None,
) -> bool:
    query = db.query(ReservaHotel.id).filter(
        ReservaHotel.clinica_id == clinica_id,
        ReservaHotel.quarto_id == room_id,
        ReservaHotel.status.in_(("RESERVADA", "CHECK_IN")),
        ReservaHotel.check_in < check_out,
        ReservaHotel.check_out > check_in,
    )
    if exclude_id:
        query = query.filter(ReservaHotel.id != exclude_id)
    return query.first() is not None
