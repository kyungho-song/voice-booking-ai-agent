import logging

from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


def _get_twilio_client() -> Client:
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        raise ValueError("Twilio credentials are not configured")
    return Client(settings.twilio_account_sid, settings.twilio_auth_token)


def send_booking_confirmation(
    to_phone: str,
    customer_name: str,
    facility_name: str,
    booking_date: str,
    start_time: str,
    end_time: str,
    court_number: int = None,
) -> bool:
    court_info = f" {court_number}번 코트" if court_number else ""
    message_body = (
        f"[{facility_name}] 예약 확정 안내\n"
        f"예약자: {customer_name or '고객'}\n"
        f"일시: {booking_date} {start_time} ~ {end_time}{court_info}\n"
        f"예약이 확정되었습니다. 감사합니다!"
    )

    try:
        client = _get_twilio_client()
        message = client.messages.create(
            body=message_body,
            from_=settings.twilio_phone_number,
            to=to_phone,
        )
        logger.info(
            "SMS sent to %s, sid=%s", to_phone, message.sid
        )
        return True
    except TwilioRestException as exc:
        logger.error("Twilio SMS error for %s: %s", to_phone, exc)
        return False
    except Exception as exc:
        logger.error("Unexpected SMS error for %s: %s", to_phone, exc)
        return False


def send_reminder(
    to_phone: str,
    customer_name: str,
    facility_name: str,
    booking_date: str,
    start_time: str,
) -> bool:
    message_body = (
        f"[{facility_name}] 예약 리마인드\n"
        f"{customer_name or '고객'}님, 오늘 {start_time} 예약 잊지 않으셨죠? "
        f"즐거운 시간 되세요! 😊"
    )

    try:
        client = _get_twilio_client()
        message = client.messages.create(
            body=message_body,
            from_=settings.twilio_phone_number,
            to=to_phone,
        )
        logger.info(
            "Reminder SMS sent to %s, sid=%s", to_phone, message.sid
        )
        return True
    except TwilioRestException as exc:
        logger.error("Twilio reminder SMS error for %s: %s", to_phone, exc)
        return False
    except Exception as exc:
        logger.error("Unexpected reminder SMS error for %s: %s", to_phone, exc)
        return False
