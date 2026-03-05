import os

# Set test database URL before any app modules are imported
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
# Ensure other required env vars don't cause validation errors
os.environ.setdefault("GEMINI_KEY", "test-gemini-key")
os.environ.setdefault("TWILIO_ACCOUNT_SID", "")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "")
os.environ.setdefault("GOOGLE_CALENDAR_ID", "")
os.environ.setdefault("GOOGLE_CALENDAR_SECRET", "")
