import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import booking, vapi
from app.core.config import get_settings
from app.database.database import Base, get_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.database.database import _get_engine

    Base.metadata.create_all(bind=_get_engine())
    logging.getLogger(__name__).info(
        "Database tables created. %s is ready.", settings.app_name
    )
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description=(
            "Voice-driven AI reservation system for sports facilities. "
            "Handles 24/7 phone bookings via Vapi → Gemini LLM → Google Calendar → Twilio SMS."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(
        vapi.router,
        prefix="/vapi",
        tags=["Vapi"],
    )
    app.include_router(
        booking.router,
        prefix="/bookings",
        tags=["Bookings"],
    )

    @app.get("/health", tags=["Health"])
    def health_check():
        return {"status": "ok", "service": settings.app_name}

    return app


app = create_app()
