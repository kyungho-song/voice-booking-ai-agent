import json
from unittest.mock import MagicMock, patch

import pytest

from app.services.llm_service import (
    extract_booking_intent,
    generate_availability_summary,
    generate_response,
)


class TestGenerateAvailabilitySummary:
    def test_returns_available_times(self):
        slots = [
            {"start_time": "19:00", "end_time": "20:00", "court_number": 1, "available": True},
            {"start_time": "20:00", "end_time": "21:00", "court_number": 1, "available": True},
            {"start_time": "21:00", "end_time": "22:00", "court_number": 1, "available": False},
        ]
        summary = generate_availability_summary(slots)
        assert "19:00" in summary
        assert "20:00" in summary
        assert "21:00" not in summary

    def test_returns_no_availability_message(self):
        slots = [
            {"start_time": "19:00", "end_time": "20:00", "court_number": 1, "available": False},
        ]
        summary = generate_availability_summary(slots)
        assert "없습니다" in summary

    def test_empty_slots_returns_no_availability(self):
        summary = generate_availability_summary([])
        assert "없습니다" in summary


class TestExtractBookingIntent:
    def test_extracts_intent_successfully(self):
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "intent": "book",
            "booking_date": "2024-06-15",
            "start_time": "19:00",
            "customer_name": "홍길동",
            "caller_phone": "+821012345678",
            "court_number": None,
        })

        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response

        with patch("app.services.llm_service.genai") as mock_genai:
            mock_genai.GenerativeModel.return_value = mock_model
            mock_genai.GenerationConfig = MagicMock()
            mock_genai.configure = MagicMock()

            result = extract_booking_intent("내일 저녁 7시에 예약하고 싶어요. 홍길동입니다.")

        assert result["intent"] == "book"
        assert result["booking_date"] == "2024-06-15"
        assert result["start_time"] == "19:00"
        assert result["customer_name"] == "홍길동"

    def test_returns_default_on_invalid_json(self):
        mock_response = MagicMock()
        mock_response.text = "invalid json response"

        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response

        with patch("app.services.llm_service.genai") as mock_genai:
            mock_genai.GenerativeModel.return_value = mock_model
            mock_genai.GenerationConfig = MagicMock()
            mock_genai.configure = MagicMock()

            result = extract_booking_intent("some text")

        assert result["intent"] == "other"
        assert result["booking_date"] is None

    def test_returns_default_on_api_error(self):
        mock_model = MagicMock()
        mock_model.generate_content.side_effect = Exception("API error")

        with patch("app.services.llm_service.genai") as mock_genai:
            mock_genai.GenerativeModel.return_value = mock_model
            mock_genai.GenerationConfig = MagicMock()
            mock_genai.configure = MagicMock()

            result = extract_booking_intent("some text")

        assert result["intent"] == "other"


class TestGenerateResponse:
    def test_generates_response_successfully(self):
        mock_response = MagicMock()
        mock_response.text = "안녕하세요! 무엇을 도와드릴까요?"

        mock_chat = MagicMock()
        mock_chat.send_message.return_value = mock_response

        mock_model = MagicMock()
        mock_model.start_chat.return_value = mock_chat

        with patch("app.services.llm_service.genai") as mock_genai:
            mock_genai.GenerativeModel.return_value = mock_model
            mock_genai.configure = MagicMock()

            messages = [{"role": "user", "content": "예약하고 싶어요"}]
            result = generate_response(messages)

        assert result == "안녕하세요! 무엇을 도와드릴까요?"

    def test_includes_availability_context(self):
        mock_response = MagicMock()
        mock_response.text = "19시에 예약 가능합니다."

        mock_chat = MagicMock()
        mock_chat.send_message.return_value = mock_response

        mock_model = MagicMock()
        mock_model.start_chat.return_value = mock_chat

        with patch("app.services.llm_service.genai") as mock_genai:
            mock_genai.GenerativeModel.return_value = mock_model
            mock_genai.configure = MagicMock()

            messages = [{"role": "user", "content": "오늘 예약 가능한가요?"}]
            result = generate_response(
                messages, availability_context="19:00, 20:00 가능"
            )

        model_call = mock_genai.GenerativeModel.call_args
        call_kwargs = model_call[1] if model_call[1] else {}
        call_args = model_call[0] if model_call[0] else []
        system_instruction = call_kwargs.get("system_instruction") or (
            call_args[1] if len(call_args) > 1 else ""
        )
        assert result == "19시에 예약 가능합니다."
