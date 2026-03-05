from functools import lru_cache
from typing import Optional

from pydantic import BaseSettings


class Settings(BaseSettings):
    # Application
    app_name: str = "Voice Booking AI Agent"
    facility_name: str = "OO 테니스장"
    debug: bool = False

    # Vapi
    vapi_key: str = ""
    vapi_webhook_secret: str = ""

    # Gemini (LLM)
    gemini_key: str = ""
    gemini_model: str = "gemini-1.5-flash"

    # ElevenLabs (TTS)
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""

    # Google Calendar
    google_calendar_id: str = ""
    google_calendar_secret: str = ""

    # Twilio (SMS)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # Make.com
    make_com_api_key: str = ""
    make_com_webhook_url: str = ""

    # Database
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "postgres"
    db_pass: str = ""
    db_name: str = "voice_booking"
    database_url: Optional[str] = None

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql://{self.db_user}:{self.db_pass}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
