import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.schemas.booking import (
    AvailabilityRequest,
    AvailabilityResponse,
    BookingCreate,
    BookingResponse,
    BookingUpdate,
)
from app.services import booking_service, calendar_service, sms_service
from app.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


@router.post("/", response_model=BookingResponse, status_code=201)
def create_booking(
    booking_data: BookingCreate,
    db: Session = Depends(get_db),
) -> BookingResponse:
    booking = booking_service.create_booking(db, booking_data)

    if settings.google_calendar_id and settings.google_calendar_secret:
        event_id = calendar_service.create_calendar_event(
            booking_date=booking.booking_date,
            start_time=booking.start_time,
            end_time=booking.end_time,
            customer_name=booking.customer_name or "",
            caller_phone=booking.caller_phone,
            facility_name=booking.facility_name,
            court_number=booking.court_number,
        )
        if event_id:
            booking_service.update_booking(
                db,
                booking.id,
                BookingUpdate(google_calendar_event_id=event_id),
            )
            booking.google_calendar_event_id = event_id

    if booking.caller_phone and settings.twilio_account_sid:
        sent = sms_service.send_booking_confirmation(
            to_phone=booking.caller_phone,
            customer_name=booking.customer_name or "",
            facility_name=booking.facility_name,
            booking_date=booking.booking_date,
            start_time=booking.start_time,
            end_time=booking.end_time,
            court_number=booking.court_number,
        )
        if sent:
            booking_service.update_booking(
                db, booking.id, BookingUpdate(sms_sent=1)
            )
            booking.sms_sent = 1

    return booking


@router.get("/{booking_id}", response_model=BookingResponse)
def get_booking(
    booking_id: int,
    db: Session = Depends(get_db),
) -> BookingResponse:
    booking = booking_service.get_booking(db, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


@router.patch("/{booking_id}", response_model=BookingResponse)
def update_booking(
    booking_id: int,
    update_data: BookingUpdate,
    db: Session = Depends(get_db),
) -> BookingResponse:
    booking = booking_service.update_booking(db, booking_id, update_data)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


@router.delete("/{booking_id}", response_model=BookingResponse)
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
) -> BookingResponse:
    booking = booking_service.cancel_booking(db, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.google_calendar_event_id and settings.google_calendar_secret:
        calendar_service.delete_calendar_event(booking.google_calendar_event_id)

    return booking


@router.get("/", response_model=List[BookingResponse])
def list_bookings_by_phone(
    phone: str,
    db: Session = Depends(get_db),
) -> List[BookingResponse]:
    return booking_service.get_bookings_by_phone(db, phone)


@router.post("/availability", response_model=AvailabilityResponse)
def check_availability(
    request: AvailabilityRequest,
    db: Session = Depends(get_db),
) -> AvailabilityResponse:
    return booking_service.check_availability(
        db,
        request.booking_date,
        request.start_time,
        request.end_time,
    )
