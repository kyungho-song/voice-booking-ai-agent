import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.database import Base
from app.models.booking import BookingStatus
from app.schemas.booking import BookingCreate, BookingUpdate
from app.services.booking_service import (
    COURT_COUNT,
    OPERATING_HOURS,
    cancel_booking,
    check_availability,
    create_booking,
    find_available_slot,
    get_booking,
    get_bookings_by_date,
    get_bookings_by_phone,
    update_booking,
)

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture()
def db():
    engine = create_engine(
        TEST_DATABASE_URL, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def _booking_create(**kwargs) -> BookingCreate:
    defaults = {
        "caller_phone": "+821012345678",
        "customer_name": "홍길동",
        "facility_name": "테스트 테니스장",
        "court_number": 1,
        "booking_date": "2024-06-15",
        "start_time": "19:00",
        "end_time": "20:00",
    }
    defaults.update(kwargs)
    return BookingCreate(**defaults)


class TestCreateBooking:
    def test_creates_booking_successfully(self, db):
        booking = create_booking(db, _booking_create())
        assert booking.id is not None
        assert booking.caller_phone == "+821012345678"
        assert booking.customer_name == "홍길동"
        assert booking.booking_date == "2024-06-15"
        assert booking.start_time == "19:00"
        assert booking.status == BookingStatus.CONFIRMED

    def test_creates_booking_without_customer_name(self, db):
        booking = create_booking(db, _booking_create(customer_name=None))
        assert booking.customer_name is None
        assert booking.caller_phone == "+821012345678"


class TestGetBooking:
    def test_get_existing_booking(self, db):
        created = create_booking(db, _booking_create())
        fetched = get_booking(db, created.id)
        assert fetched is not None
        assert fetched.id == created.id

    def test_get_nonexistent_booking_returns_none(self, db):
        result = get_booking(db, 99999)
        assert result is None

    def test_get_bookings_by_date(self, db):
        create_booking(db, _booking_create(booking_date="2024-06-15"))
        create_booking(db, _booking_create(booking_date="2024-06-15", start_time="20:00", end_time="21:00"))
        create_booking(db, _booking_create(booking_date="2024-06-16"))

        results = get_bookings_by_date(db, "2024-06-15")
        assert len(results) == 2

    def test_get_bookings_by_phone(self, db):
        create_booking(db, _booking_create(caller_phone="+821011111111"))
        create_booking(db, _booking_create(caller_phone="+821011111111", start_time="20:00", end_time="21:00"))
        create_booking(db, _booking_create(caller_phone="+821099999999"))

        results = get_bookings_by_phone(db, "+821011111111")
        assert len(results) == 2
        for b in results:
            assert b.caller_phone == "+821011111111"


class TestUpdateBooking:
    def test_update_customer_name(self, db):
        booking = create_booking(db, _booking_create(customer_name="홍길동"))
        updated = update_booking(db, booking.id, BookingUpdate(customer_name="김철수"))
        assert updated.customer_name == "김철수"

    def test_update_nonexistent_booking_returns_none(self, db):
        result = update_booking(db, 99999, BookingUpdate(customer_name="test"))
        assert result is None

    def test_update_google_calendar_event_id(self, db):
        booking = create_booking(db, _booking_create())
        updated = update_booking(
            db, booking.id, BookingUpdate(google_calendar_event_id="evt_abc123")
        )
        assert updated.google_calendar_event_id == "evt_abc123"


class TestCancelBooking:
    def test_cancel_booking(self, db):
        booking = create_booking(db, _booking_create())
        assert booking.status == BookingStatus.CONFIRMED

        cancelled = cancel_booking(db, booking.id)
        assert cancelled.status == BookingStatus.CANCELLED

    def test_cancel_nonexistent_booking_returns_none(self, db):
        result = cancel_booking(db, 99999)
        assert result is None

    def test_cancelled_booking_excluded_from_date_query(self, db):
        booking = create_booking(db, _booking_create())
        cancel_booking(db, booking.id)

        results = get_bookings_by_date(db, "2024-06-15")
        assert len(results) == 0


class TestCheckAvailability:
    def test_all_slots_available_on_empty_day(self, db):
        availability = check_availability(db, "2024-06-15")
        available_slots = [s for s in availability.slots if s.available]
        total_slots = (len(OPERATING_HOURS) - 1) * COURT_COUNT
        assert len(available_slots) == total_slots

    def test_booked_slot_shows_unavailable(self, db):
        create_booking(
            db,
            _booking_create(
                booking_date="2024-06-15",
                start_time="19:00",
                end_time="20:00",
                court_number=1,
            ),
        )
        availability = check_availability(db, "2024-06-15")
        court1_1900 = [
            s
            for s in availability.slots
            if s.start_time == "19:00" and s.court_number == 1
        ]
        assert len(court1_1900) == 1
        assert court1_1900[0].available is False

    def test_other_courts_still_available_when_one_booked(self, db):
        create_booking(
            db,
            _booking_create(
                booking_date="2024-06-15",
                start_time="19:00",
                end_time="20:00",
                court_number=1,
            ),
        )
        availability = check_availability(db, "2024-06-15")
        other_1900 = [
            s
            for s in availability.slots
            if s.start_time == "19:00" and s.court_number != 1
        ]
        assert all(s.available for s in other_1900)

    def test_cancelled_booking_frees_slot(self, db):
        booking = create_booking(
            db,
            _booking_create(
                booking_date="2024-06-15",
                start_time="19:00",
                end_time="20:00",
                court_number=1,
            ),
        )
        cancel_booking(db, booking.id)

        availability = check_availability(db, "2024-06-15")
        court1_1900 = [
            s
            for s in availability.slots
            if s.start_time == "19:00" and s.court_number == 1
        ]
        assert court1_1900[0].available is True


class TestFindAvailableSlot:
    def test_finds_slot_on_empty_day(self, db):
        slot = find_available_slot(db, "2024-06-15")
        assert slot is not None
        assert slot.available is True

    def test_finds_preferred_time_slot(self, db):
        slot = find_available_slot(db, "2024-06-15", preferred_time="20:00")
        assert slot is not None
        assert slot.start_time == "20:00"

    def test_returns_none_when_fully_booked(self, db):
        for hour_idx in range(len(OPERATING_HOURS) - 1):
            start = OPERATING_HOURS[hour_idx]
            end = OPERATING_HOURS[hour_idx + 1]
            for court in range(1, COURT_COUNT + 1):
                create_booking(
                    db,
                    _booking_create(
                        booking_date="2024-06-15",
                        start_time=start,
                        end_time=end,
                        court_number=court,
                    ),
                )

        slot = find_available_slot(db, "2024-06-15")
        assert slot is None

    def test_returns_none_when_preferred_time_fully_booked(self, db):
        for court in range(1, COURT_COUNT + 1):
            create_booking(
                db,
                _booking_create(
                    booking_date="2024-06-15",
                    start_time="19:00",
                    end_time="20:00",
                    court_number=court,
                ),
            )

        slot = find_available_slot(db, "2024-06-15", preferred_time="19:00")
        assert slot is None
