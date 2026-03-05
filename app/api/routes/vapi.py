import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.database import get_db
from app.schemas.booking import BookingCreate, BookingUpdate
from app.schemas.vapi import (
    VapiAssistantConfig,
    VapiAssistantResponse,
    VapiFunctionResult,
    VapiWebhookPayload,
)
from app.services import booking_service, calendar_service, llm_service, sms_service

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


def _get_caller_phone(call: Dict[str, Any]) -> str:
    customer = call.get("customer", {})
    return customer.get("number", "unknown")


def _build_assistant_config() -> VapiAssistantConfig:
    return VapiAssistantConfig(
        firstMessage=(
            f"안녕하세요, {settings.facility_name}입니다. "
            "예약이나 문의 사항이 있으시면 말씀해 주세요."
        ),
        model={
            "provider": "google",
            "model": settings.gemini_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        f"당신은 {settings.facility_name}의 전화 예약 AI 비서입니다. "
                        "고객의 예약 요청을 친절하게 처리해 주세요."
                    ),
                }
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "check_availability",
                        "description": "특정 날짜의 예약 가능한 시간대를 확인합니다.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "booking_date": {
                                    "type": "string",
                                    "description": "조회할 날짜 (YYYY-MM-DD 형식)",
                                }
                            },
                            "required": ["booking_date"],
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "create_booking",
                        "description": "예약을 생성합니다.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "booking_date": {
                                    "type": "string",
                                    "description": "예약 날짜 (YYYY-MM-DD 형식)",
                                },
                                "start_time": {
                                    "type": "string",
                                    "description": "시작 시간 (HH:MM 형식)",
                                },
                                "end_time": {
                                    "type": "string",
                                    "description": "종료 시간 (HH:MM 형식)",
                                },
                                "customer_name": {
                                    "type": "string",
                                    "description": "고객 이름",
                                },
                                "court_number": {
                                    "type": "integer",
                                    "description": "코트 번호 (1-4)",
                                },
                            },
                            "required": [
                                "booking_date",
                                "start_time",
                                "end_time",
                                "customer_name",
                            ],
                        },
                    },
                },
            ],
        },
        voice={
            "provider": "11labs",
            "voiceId": settings.elevenlabs_voice_id or "21m00Tcm4TlvDq8ikWAM",
            "stability": 0.5,
            "similarityBoost": 0.75,
        },
    )


@router.post("/webhook")
async def vapi_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    message = body.get("message", {})
    msg_type = message.get("type", "")
    call = message.get("call", {})
    call_id = call.get("id", "")

    logger.info("Vapi webhook type=%s call_id=%s", msg_type, call_id)

    if msg_type == "assistant-request":
        return _build_assistant_config().dict()

    if msg_type == "function-call":
        return await _handle_function_call(message, call, db)

    if msg_type == "end-of-call-report":
        await _handle_end_of_call(message, call, db)
        return {"status": "ok"}

    if msg_type == "status-update":
        logger.info(
            "Call status update: call_id=%s status=%s",
            call_id,
            message.get("status"),
        )
        return {"status": "ok"}

    return {"status": "ok"}


async def _handle_function_call(
    message: Dict[str, Any],
    call: Dict[str, Any],
    db: Session,
) -> Dict[str, Any]:
    function_call = message.get("functionCall", {})
    function_name = function_call.get("name", "")
    parameters = function_call.get("parameters", {})
    call_id = call.get("id", "")
    caller_phone = _get_caller_phone(call)

    logger.info(
        "Function call: name=%s call_id=%s params=%s",
        function_name,
        call_id,
        parameters,
    )

    if function_name == "check_availability":
        booking_date = parameters.get("booking_date", "")
        availability = booking_service.check_availability(db, booking_date)
        slots_data = [s.dict() for s in availability.slots]
        summary = llm_service.generate_availability_summary(slots_data)
        return {"result": summary}

    if function_name == "create_booking":
        booking_date = parameters.get("booking_date", "")
        start_time = parameters.get("start_time", "")
        end_time = parameters.get("end_time", "")
        customer_name = parameters.get("customer_name", "")
        court_number = parameters.get("court_number")

        slot = booking_service.find_available_slot(db, booking_date, start_time)
        if not slot:
            return {
                "result": (
                    f"죄송합니다. {booking_date} {start_time}에는 "
                    "예약 가능한 코트가 없습니다. 다른 시간을 원하시나요?"
                )
            }

        effective_court = court_number or slot.court_number
        booking_data = BookingCreate(
            caller_phone=caller_phone,
            customer_name=customer_name,
            facility_name=settings.facility_name,
            court_number=effective_court,
            booking_date=booking_date,
            start_time=start_time,
            end_time=end_time,
            call_id=call_id,
        )
        booking = booking_service.create_booking(db, booking_data)

        calendar_event_id = None
        if settings.google_calendar_id and settings.google_calendar_secret:
            calendar_event_id = calendar_service.create_calendar_event(
                booking_date=booking_date,
                start_time=start_time,
                end_time=end_time,
                customer_name=customer_name,
                caller_phone=caller_phone,
                facility_name=settings.facility_name,
                court_number=effective_court,
            )
            if calendar_event_id:
                booking_service.update_booking(
                    db,
                    booking.id,
                    BookingUpdate(google_calendar_event_id=calendar_event_id),
                )

        sms_sent = False
        if caller_phone != "unknown" and settings.twilio_account_sid:
            sms_sent = sms_service.send_booking_confirmation(
                to_phone=caller_phone,
                customer_name=customer_name,
                facility_name=settings.facility_name,
                booking_date=booking_date,
                start_time=start_time,
                end_time=end_time,
                court_number=effective_court,
            )
            if sms_sent:
                booking_service.update_booking(
                    db, booking.id, BookingUpdate(sms_sent=1)
                )

        court_info = f" {effective_court}번 코트" if effective_court else ""
        return {
            "result": (
                f"예약이 완료되었습니다! "
                f"{booking_date} {start_time}~{end_time}{court_info} "
                f"({customer_name}님). "
                + ("확인 문자를 발송했습니다." if sms_sent else "")
            )
        }

    logger.warning("Unknown function call: %s", function_name)
    return {"result": "처리할 수 없는 요청입니다."}


async def _handle_end_of_call(
    message: Dict[str, Any],
    call: Dict[str, Any],
    db: Session,
) -> None:
    call_id = call.get("id", "")
    transcript = message.get("transcript", "")
    summary = message.get("summary", "")

    logger.info(
        "End of call: call_id=%s summary=%s",
        call_id,
        summary[:100] if summary else "",
    )

    if transcript:
        intent_data = llm_service.extract_booking_intent(transcript)
        logger.info("Post-call intent extraction: %s", intent_data)
