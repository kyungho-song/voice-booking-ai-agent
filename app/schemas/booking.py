from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from app.models.booking import BookingStatus


class BookingCreate(BaseModel):
    caller_phone: str
    customer_name: Optional[str] = None
    facility_name: str
    court_number: Optional[int] = None
    booking_date: str
    start_time: str
    end_time: str
    notes: Optional[str] = None
    call_id: Optional[str] = None


class BookingUpdate(BaseModel):
    customer_name: Optional[str] = None
    court_number: Optional[int] = None
    booking_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    status: Optional[BookingStatus] = None
    notes: Optional[str] = None
    google_calendar_event_id: Optional[str] = None
    sms_sent: Optional[int] = None


class BookingResponse(BaseModel):
    id: int
    caller_phone: str
    customer_name: Optional[str]
    facility_name: str
    court_number: Optional[int]
    booking_date: str
    start_time: str
    end_time: str
    status: BookingStatus
    notes: Optional[str]
    google_calendar_event_id: Optional[str]
    sms_sent: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    call_id: Optional[str]

    class Config:
        orm_mode = True


class AvailabilityRequest(BaseModel):
    booking_date: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None


class AvailableSlot(BaseModel):
    start_time: str
    end_time: str
    court_number: int
    available: bool


class AvailabilityResponse(BaseModel):
    booking_date: str
    slots: List[AvailableSlot]
