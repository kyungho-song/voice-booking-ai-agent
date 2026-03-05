# Voice Booking AI Agent

## Overview

The Voice Booking AI Agent is a 24/7 AI-driven phone reservation system for sports facilities (tennis courts, futsal fields, etc.). It automates the full booking flow:

**📞 Phone Call → 🎤 STT (Vapi) → 🧠 LLM (Gemini) → 📅 Google Calendar → 📱 SMS (Twilio)**

Operators can focus on their work while the AI handles all incoming reservation calls around the clock.

## Features

- **24/7 Phone Reservation Handling** – AI answers calls and manages bookings even when staff are unavailable.
- **Real-time Availability Check** – Queries the local database to show open time slots instantly.
- **Gemini LLM Reasoning** – Uses Google Gemini to understand customer intent and guide multi-turn conversations in Korean.
- **Google Calendar Sync** – Every confirmed booking is saved as a Google Calendar event.
- **SMS Confirmation** – Sends an automatic confirmation SMS (via Twilio) after booking.
- **No-Show Reminder** – Reminder SMS can be triggered before the booking time.
- **REST API** – Full CRUD booking endpoints for integration with other systems.

## Architecture

```
Incoming Call (Vapi)
      │
      ▼
FastAPI Webhook  ◄──── /vapi/webhook
      │
      ├─► Gemini LLM (intent / response generation)
      ├─► Booking Service (availability check / create / cancel)
      ├─► Google Calendar (create / delete events)
      └─► Twilio SMS (booking confirmation)
```

## Tech Stack

| Layer | Technology |
|---|---|
| Phone & STT/TTS | [Vapi](https://vapi.ai) |
| LLM | [Google Gemini 1.5 Flash/Pro](https://ai.google.dev) |
| TTS Voice | [ElevenLabs](https://elevenlabs.io) |
| Database | PostgreSQL + SQLAlchemy |
| SMS | [Twilio](https://twilio.com) |
| Calendar | [Google Calendar API](https://developers.google.com/calendar) |
| Framework | [FastAPI](https://fastapi.tiangolo.com) |

## Project Structure

```
voice-booking-ai-agent/
├── app/
│   ├── main.py                   # FastAPI application entry point
│   ├── core/
│   │   └── config.py             # Settings (loaded from .env)
│   ├── database/
│   │   └── database.py           # SQLAlchemy engine & session
│   ├── models/
│   │   └── booking.py            # Booking ORM model
│   ├── schemas/
│   │   ├── booking.py            # Pydantic request/response schemas
│   │   └── vapi.py               # Vapi webhook payload schemas
│   ├── services/
│   │   ├── booking_service.py    # Booking CRUD & availability logic
│   │   ├── llm_service.py        # Gemini LLM integration
│   │   ├── calendar_service.py   # Google Calendar integration
│   │   └── sms_service.py        # Twilio SMS integration
│   └── api/
│       └── routes/
│           ├── vapi.py           # Vapi webhook endpoint
│           └── booking.py        # REST booking endpoints
└── tests/
    ├── test_booking_service.py
    ├── test_llm_service.py
    └── test_vapi_routes.py
```

## Getting Started

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment variables

Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
```

### 3. Run the server

```bash
uvicorn app.main:app --reload --port 8000
```

### 4. Expose the webhook (for local development)

Use [ngrok](https://ngrok.com) to expose your local server:

```bash
ngrok http 8000
```

Then configure the Vapi assistant's **Server URL** to:
```
https://<your-ngrok-subdomain>.ngrok.io/vapi/webhook
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/vapi/webhook` | Vapi webhook handler (call flow) |
| `POST` | `/bookings/` | Create a booking |
| `GET` | `/bookings/{id}` | Get a booking by ID |
| `PATCH` | `/bookings/{id}` | Update a booking |
| `DELETE` | `/bookings/{id}` | Cancel a booking |
| `GET` | `/bookings/?phone=...` | List bookings by phone number |
| `POST` | `/bookings/availability` | Check available time slots |
| `GET` | `/health` | Health check |

## Running Tests

```bash
pytest tests/ -v
```

## Environment Variables

| Variable | Description |
|---|---|
| `VAPI_KEY` | Vapi API key |
| `GEMINI_KEY` | Google Gemini API key |
| `GEMINI_MODEL` | Gemini model name (default: `gemini-1.5-flash`) |
| `ELEVENLABS_API_KEY` | ElevenLabs API key |
| `ELEVENLABS_VOICE_ID` | ElevenLabs voice ID |
| `GOOGLE_CALENDAR_ID` | Google Calendar ID |
| `GOOGLE_CALENDAR_SECRET` | Google service account JSON (stringified) |
| `TWILIO_ACCOUNT_SID` | Twilio Account SID |
| `TWILIO_AUTH_TOKEN` | Twilio Auth Token |
| `TWILIO_PHONE_NUMBER` | Twilio sender phone number |
| `DB_HOST` | PostgreSQL host |
| `DB_PORT` | PostgreSQL port (default: `5432`) |
| `DB_USER` | PostgreSQL username |
| `DB_PASS` | PostgreSQL password |
| `DB_NAME` | PostgreSQL database name |
| `DATABASE_URL` | Full database URL (overrides individual DB settings) |
| `FACILITY_NAME` | Facility name shown to callers (default: `OO 테니스장`) |

## Business Expansion

- **White-labeling**: Package the booking module as an API for sports associations or venue management platforms.
- **No-show prevention**: Use the reminder SMS feature to call customers 1 hour before their reservation.
