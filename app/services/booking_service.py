import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.booking import Booking, BookingStatus
from app.schemas.booking import (
    AvailableSlot,
    AvailabilityResponse,
    BookingCreate,
    BookingUpdate,
)

logger = logging.getLogger(__name__)

# Operating hours: 07:00 – 22:00 in 1-hour slots
# Operating hours: 07:00 – 22:00 in 1-hour slots.
# The list runs up to and including "22:00" so that the last bookable slot
# (21:00 → 22:00) has a proper end-time boundary.
OPERATING_HOURS = [f"{h:02d}:00" for h in range(7, 23)]
COURT_COUNT = 4


def get_booking(db: Session, booking_id: int) -> Optional[Booking]:
    return db.query(Booking).filter(Booking.id == booking_id).first()


def get_bookings_by_date(db: Session, booking_date: str) -> List[Booking]:
    return (
        db.query(Booking)
        .filter(
            Booking.booking_date == booking_date,
            Booking.status != BookingStatus.CANCELLED,
        )
        .all()
    )


def get_bookings_by_phone(db: Session, caller_phone: str) -> List[Booking]:
    return (
        db.query(Booking)
        .filter(Booking.caller_phone == caller_phone)
        .order_by(Booking.created_at.desc())
        .all()
    )


def create_booking(db: Session, booking_data: BookingCreate) -> Booking:
    booking = Booking(**booking_data.dict())
    db.add(booking)
    db.commit()
    db.refresh(booking)
    logger.info(
        "Created booking id=%s for %s on %s %s-%s",
        booking.id,
        booking.caller_phone,
        booking.booking_date,
        booking.start_time,
        booking.end_time,
    )
    return booking


def update_booking(
    db: Session, booking_id: int, update_data: BookingUpdate
) -> Optional[Booking]:
    booking = get_booking(db, booking_id)
    if not booking:
        return None
    for field, value in update_data.dict(exclude_unset=True).items():
        setattr(booking, field, value)
    db.commit()
    db.refresh(booking)
    return booking


def cancel_booking(db: Session, booking_id: int) -> Optional[Booking]:
    booking = get_booking(db, booking_id)
    if not booking:
        return None
    booking.status = BookingStatus.CANCELLED
    db.commit()
    db.refresh(booking)
    logger.info("Cancelled booking id=%s", booking_id)
    return booking


def check_availability(
    db: Session,
    booking_date: str,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
) -> AvailabilityResponse:
    existing = get_bookings_by_date(db, booking_date)

    booked_slots: set = set()
    for b in existing:
        booked_slots.add((b.start_time, b.court_number))

    slots: List[AvailableSlot] = []
    for i, hour in enumerate(OPERATING_HOURS[:-1]):
        slot_start = hour
        slot_end = OPERATING_HOURS[i + 1]

        if start_time and slot_start < start_time:
            continue
        if end_time and slot_end > end_time:
            continue

        for court in range(1, COURT_COUNT + 1):
            available = (slot_start, court) not in booked_slots
            slots.append(
                AvailableSlot(
                    start_time=slot_start,
                    end_time=slot_end,
                    court_number=court,
                    available=available,
                )
            )

    return AvailabilityResponse(booking_date=booking_date, slots=slots)


def find_available_slot(
    db: Session, booking_date: str, preferred_time: Optional[str] = None
) -> Optional[AvailableSlot]:
    availability = check_availability(db, booking_date)
    available_slots = [s for s in availability.slots if s.available]

    if not available_slots:
        return None

    if preferred_time:
        preferred = [s for s in available_slots if s.start_time == preferred_time]
        if preferred:
            return preferred[0]
        # Preferred time is fully booked – let the caller decide what to offer next
        return None

    return available_slots[0]
