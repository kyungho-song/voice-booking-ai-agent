import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _get_calendar_service():
    import json

    if not settings.google_calendar_secret:
        raise ValueError("Google Calendar secret is not configured")

    try:
        service_account_info = json.loads(settings.google_calendar_secret)
        credentials = Credentials.from_service_account_info(
            service_account_info, scopes=SCOPES
        )
        service = build("calendar", "v3", credentials=credentials)
        return service
    except Exception as exc:
        logger.error("Failed to create Google Calendar service: %s", exc)
        raise


def create_calendar_event(
    booking_date: str,
    start_time: str,
    end_time: str,
    customer_name: str,
    caller_phone: str,
    facility_name: str,
    court_number: Optional[int] = None,
    notes: Optional[str] = None,
) -> Optional[str]:
    try:
        service = _get_calendar_service()

        start_dt = datetime.fromisoformat(f"{booking_date}T{start_time}:00")
        end_dt = datetime.fromisoformat(f"{booking_date}T{end_time}:00")

        court_info = f" (코트 {court_number}번)" if court_number else ""
        summary = f"[예약] {customer_name or caller_phone}{court_info}"

        description_parts = [
            f"예약자: {customer_name or '미확인'}",
            f"전화번호: {caller_phone}",
            f"시설: {facility_name}{court_info}",
        ]
        if notes:
            description_parts.append(f"메모: {notes}")

        event = {
            "summary": summary,
            "description": "\n".join(description_parts),
            "start": {
                "dateTime": start_dt.isoformat(),
                "timeZone": "Asia/Seoul",
            },
            "end": {
                "dateTime": end_dt.isoformat(),
                "timeZone": "Asia/Seoul",
            },
        }

        created = (
            service.events()
            .insert(calendarId=settings.google_calendar_id, body=event)
            .execute()
        )
        event_id = created.get("id")
        logger.info("Created Google Calendar event id=%s", event_id)
        return event_id

    except HttpError as exc:
        logger.error("Google Calendar API error: %s", exc)
        return None
    except Exception as exc:
        logger.error("Failed to create calendar event: %s", exc)
        return None


def delete_calendar_event(event_id: str) -> bool:
    try:
        service = _get_calendar_service()
        service.events().delete(
            calendarId=settings.google_calendar_id, eventId=event_id
        ).execute()
        logger.info("Deleted Google Calendar event id=%s", event_id)
        return True
    except HttpError as exc:
        logger.error("Google Calendar delete error: %s", exc)
        return False


def list_calendar_events(
    booking_date: str,
) -> List[Dict[str, Any]]:
    try:
        service = _get_calendar_service()

        time_min = datetime.fromisoformat(f"{booking_date}T00:00:00")
        time_max = time_min + timedelta(days=1)

        result = (
            service.events()
            .list(
                calendarId=settings.google_calendar_id,
                timeMin=time_min.isoformat() + "+09:00",
                timeMax=time_max.isoformat() + "+09:00",
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        return result.get("items", [])
    except Exception as exc:
        logger.error("Failed to list calendar events: %s", exc)
        return []
