import json
import logging
from typing import Any, Dict, List, Optional

import google.generativeai as genai

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

SYSTEM_PROMPT = """
당신은 {facility_name}의 전화 예약 AI 비서입니다.
고객의 전화를 받아 예약을 도와드립니다.

다음 정보를 수집해야 합니다:
1. 예약 날짜 (예: 2024-01-15)
2. 원하는 시간대 (예: 19:00)
3. 고객 이름
4. 연락처 (전화번호)

운영 시간: 오전 7시 ~ 오후 10시 (1시간 단위)
코트 수: 4개

대화 시 다음 원칙을 따르세요:
- 항상 친절하고 자연스러운 한국어로 응대하세요
- 예약 완료 후 예약 내용을 요약하여 확인해 주세요
- 불명확한 정보가 있으면 다시 물어보세요
- 예약이 불가능한 시간은 대안을 제시하세요

현재 예약 상태 정보가 제공되면 이를 바탕으로 응대하세요.
"""

BOOKING_INTENT_PROMPT = """
다음 대화를 분석하여 예약 정보를 JSON 형식으로 추출하세요.
추출할 수 없는 정보는 null로 표시하세요.

대화:
{conversation}

다음 JSON 형식으로만 응답하세요:
{{
    "intent": "book|cancel|check|other",
    "booking_date": "YYYY-MM-DD 또는 null",
    "start_time": "HH:MM 또는 null",
    "customer_name": "이름 또는 null",
    "caller_phone": "전화번호 또는 null",
    "court_number": "코트번호(정수) 또는 null"
}}
"""


def _configure_genai() -> None:
    if settings.gemini_key:
        genai.configure(api_key=settings.gemini_key)


def generate_response(
    messages: List[Dict[str, str]],
    availability_context: Optional[str] = None,
    facility_name: Optional[str] = None,
) -> str:
    _configure_genai()

    fname = facility_name or settings.facility_name
    system = SYSTEM_PROMPT.format(facility_name=fname)

    if availability_context:
        system += f"\n\n현재 예약 가능 현황:\n{availability_context}"

    model = genai.GenerativeModel(
        model_name=settings.gemini_model,
        system_instruction=system,
    )

    history = []
    for msg in messages[:-1]:
        role = "user" if msg["role"] == "user" else "model"
        history.append({"role": role, "parts": [msg["content"]]})

    chat = model.start_chat(history=history)

    last_message = messages[-1]["content"] if messages else ""
    response = chat.send_message(last_message)

    return response.text


def extract_booking_intent(conversation: str) -> Dict[str, Any]:
    _configure_genai()

    model = genai.GenerativeModel(model_name=settings.gemini_model)
    prompt = BOOKING_INTENT_PROMPT.format(conversation=conversation)

    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json"
            ),
        )
        result = json.loads(response.text)
        return result
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning("Failed to extract booking intent: %s", exc)
        return {
            "intent": "other",
            "booking_date": None,
            "start_time": None,
            "customer_name": None,
            "caller_phone": None,
            "court_number": None,
        }


def generate_availability_summary(slots: List[Dict[str, Any]]) -> str:
    available = [s for s in slots if s.get("available")]
    if not available:
        return "죄송합니다. 해당 날짜에는 예약 가능한 시간이 없습니다."

    time_slots = sorted({s["start_time"] for s in available})
    slots_str = ", ".join(time_slots)
    return f"예약 가능한 시간대는 {slots_str} 입니다."
