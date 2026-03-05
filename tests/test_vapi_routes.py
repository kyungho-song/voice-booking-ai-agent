import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.database.database as db_module
from app.database.database import Base, get_db
from app.main import app
from app.schemas.booking import BookingCreate
from app.services.booking_service import COURT_COUNT, OPERATING_HOURS, create_booking

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture()
def test_engine():
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def test_session(test_engine):
    Session = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(test_engine, test_session):
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    # Patch the module-level engine and session factory so the startup event
    # uses the same engine as the test session
    original_engine = db_module._engine
    original_session = db_module._SessionLocal
    db_module._engine = test_engine
    db_module._SessionLocal = TestSession

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

    db_module._engine = original_engine
    db_module._SessionLocal = original_session


SAMPLE_CALL = {
    "id": "call_test_001",
    "status": "in-progress",
    "customer": {"number": "+821012345678"},
}


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


class TestVapiAssistantRequest:
    def test_assistant_request_returns_config(self, client):
        payload = {
            "message": {
                "type": "assistant-request",
                "call": SAMPLE_CALL,
            }
        }
        response = client.post("/vapi/webhook", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "firstMessage" in data
        assert "model" in data
        assert "voice" in data

    def test_assistant_request_first_message_is_korean(self, client):
        payload = {
            "message": {
                "type": "assistant-request",
                "call": SAMPLE_CALL,
            }
        }
        response = client.post("/vapi/webhook", json=payload)
        data = response.json()
        assert "안녕하세요" in data["firstMessage"]


class TestVapiStatusUpdate:
    def test_status_update_returns_ok(self, client):
        payload = {
            "message": {
                "type": "status-update",
                "call": SAMPLE_CALL,
                "status": "in-progress",
            }
        }
        response = client.post("/vapi/webhook", json=payload)
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestVapiFunctionCall_CheckAvailability:
    def test_check_availability_returns_summary(self, client):
        payload = {
            "message": {
                "type": "function-call",
                "call": SAMPLE_CALL,
                "functionCall": {
                    "name": "check_availability",
                    "parameters": {"booking_date": "2024-06-15"},
                },
            }
        }
        response = client.post("/vapi/webhook", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data


class TestVapiFunctionCall_CreateBooking:
    def test_create_booking_succeeds(self, client):
        with patch("app.api.routes.vapi.sms_service.send_booking_confirmation") as mock_sms, \
             patch("app.api.routes.vapi.calendar_service.create_calendar_event") as mock_cal:
            mock_sms.return_value = False
            mock_cal.return_value = None

            payload = {
                "message": {
                    "type": "function-call",
                    "call": SAMPLE_CALL,
                    "functionCall": {
                        "name": "create_booking",
                        "parameters": {
                            "booking_date": "2024-06-15",
                            "start_time": "19:00",
                            "end_time": "20:00",
                            "customer_name": "홍길동",
                            "court_number": 1,
                        },
                    },
                }
            }
            response = client.post("/vapi/webhook", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "예약이 완료되었습니다" in data["result"]

    def test_create_booking_when_fully_booked_returns_error_message(
        self, client
    ):
        # Fill all courts for 19:00 via REST so the same session pipeline is used
        for court in range(1, COURT_COUNT + 1):
            with patch("app.api.routes.booking.calendar_service.create_calendar_event") as mock_cal, \
                 patch("app.api.routes.booking.sms_service.send_booking_confirmation") as mock_sms:
                mock_cal.return_value = None
                mock_sms.return_value = False
                client.post("/bookings/", json={
                    "caller_phone": "+821099999999",
                    "facility_name": "테스트장",
                    "booking_date": "2024-06-20",
                    "start_time": "19:00",
                    "end_time": "20:00",
                    "court_number": court,
                })

        with patch("app.api.routes.vapi.sms_service.send_booking_confirmation") as mock_sms:
            mock_sms.return_value = False
            payload = {
                "message": {
                    "type": "function-call",
                    "call": SAMPLE_CALL,
                    "functionCall": {
                        "name": "create_booking",
                        "parameters": {
                            "booking_date": "2024-06-20",
                            "start_time": "19:00",
                            "end_time": "20:00",
                            "customer_name": "테스트",
                        },
                    },
                }
            }
            response = client.post("/vapi/webhook", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "예약 가능한 코트가 없습니다" in data["result"]

    def test_unknown_function_returns_error(self, client):
        payload = {
            "message": {
                "type": "function-call",
                "call": SAMPLE_CALL,
                "functionCall": {
                    "name": "unknown_function",
                    "parameters": {},
                },
            }
        }
        response = client.post("/vapi/webhook", json=payload)
        assert response.status_code == 200
        assert "처리할 수 없는" in response.json()["result"]


class TestVapiEndOfCall:
    def test_end_of_call_returns_ok(self, client):
        with patch("app.services.llm_service.genai") as mock_genai:
            mock_response = MagicMock()
            mock_response.text = json.dumps({
                "intent": "book",
                "booking_date": None,
                "start_time": None,
                "customer_name": None,
                "caller_phone": None,
                "court_number": None,
            })
            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_response
            mock_genai.GenerativeModel.return_value = mock_model
            mock_genai.GenerationConfig = MagicMock()
            mock_genai.configure = MagicMock()

            payload = {
                "message": {
                    "type": "end-of-call-report",
                    "call": SAMPLE_CALL,
                    "transcript": "고객: 예약하고 싶어요. AI: 네, 도와드리겠습니다.",
                    "summary": "예약 문의",
                }
            }
            response = client.post("/vapi/webhook", json=payload)

        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestBookingRestEndpoints:
    def test_create_booking_rest(self, client):
        with patch("app.api.routes.booking.calendar_service.create_calendar_event") as mock_cal, \
             patch("app.api.routes.booking.sms_service.send_booking_confirmation") as mock_sms:
            mock_cal.return_value = None
            mock_sms.return_value = False

            payload = {
                "caller_phone": "+821012345678",
                "customer_name": "홍길동",
                "facility_name": "테스트 테니스장",
                "court_number": 1,
                "booking_date": "2024-06-15",
                "start_time": "19:00",
                "end_time": "20:00",
            }
            response = client.post("/bookings/", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["caller_phone"] == "+821012345678"
        assert data["status"] == "confirmed"
        assert data["id"] is not None

    def test_get_booking_rest(self, client):
        with patch("app.api.routes.booking.calendar_service.create_calendar_event") as mock_cal, \
             patch("app.api.routes.booking.sms_service.send_booking_confirmation") as mock_sms:
            mock_cal.return_value = None
            mock_sms.return_value = False
            payload = {
                "caller_phone": "+821012345678",
                "facility_name": "테스트 테니스장",
                "booking_date": "2024-06-15",
                "start_time": "19:00",
                "end_time": "20:00",
            }
            create_resp = client.post("/bookings/", json=payload)
        booking_id = create_resp.json()["id"]

        response = client.get(f"/bookings/{booking_id}")
        assert response.status_code == 200
        assert response.json()["id"] == booking_id

    def test_get_nonexistent_booking_returns_404(self, client):
        response = client.get("/bookings/99999")
        assert response.status_code == 404

    def test_cancel_booking_rest(self, client):
        with patch("app.api.routes.booking.calendar_service.create_calendar_event") as mock_cal, \
             patch("app.api.routes.booking.sms_service.send_booking_confirmation") as mock_sms:
            mock_cal.return_value = None
            mock_sms.return_value = False
            payload = {
                "caller_phone": "+821012345678",
                "facility_name": "테스트 테니스장",
                "booking_date": "2024-06-15",
                "start_time": "19:00",
                "end_time": "20:00",
            }
            create_resp = client.post("/bookings/", json=payload)
        booking_id = create_resp.json()["id"]

        with patch("app.api.routes.booking.calendar_service.delete_calendar_event"):
            response = client.delete(f"/bookings/{booking_id}")

        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"

    def test_check_availability_rest(self, client):
        payload = {"booking_date": "2024-06-15"}
        response = client.post("/bookings/availability", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["booking_date"] == "2024-06-15"
        assert len(data["slots"]) > 0
