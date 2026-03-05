from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class VapiMessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"


class VapiMessage(BaseModel):
    role: VapiMessageRole
    content: str


class VapiCallStatus(str, Enum):
    RINGING = "ringing"
    IN_PROGRESS = "in-progress"
    FORWARDING = "forwarding"
    ENDED = "ended"


class VapiCall(BaseModel):
    id: str
    status: Optional[VapiCallStatus] = None
    customer: Optional[Dict[str, Any]] = None
    phoneNumber: Optional[Dict[str, Any]] = None


class VapiWebhookType(str, Enum):
    ASSISTANT_REQUEST = "assistant-request"
    STATUS_UPDATE = "status-update"
    END_OF_CALL_REPORT = "end-of-call-report"
    HANG = "hang"
    SPEECH_UPDATE = "speech-update"
    TRANSCRIPT = "transcript"
    FUNCTION_CALL = "function-call"


class VapiWebhookPayload(BaseModel):
    message: Dict[str, Any]


class VapiAssistantRequestPayload(BaseModel):
    type: str
    call: VapiCall


class VapiStatusUpdatePayload(BaseModel):
    type: str
    call: VapiCall
    status: VapiCallStatus
    messages: Optional[List[VapiMessage]] = None


class VapiEndOfCallPayload(BaseModel):
    type: str
    call: VapiCall
    messages: Optional[List[VapiMessage]] = None
    summary: Optional[str] = None
    transcript: Optional[str] = None


class VapiFunctionCallPayload(BaseModel):
    type: str
    call: VapiCall
    functionCall: Dict[str, Any]


class VapiAssistantConfig(BaseModel):
    firstMessage: str
    model: Dict[str, Any]
    voice: Dict[str, Any]


class VapiAssistantResponse(BaseModel):
    assistant: VapiAssistantConfig


class VapiFunctionResult(BaseModel):
    result: str


class VapiResponse(BaseModel):
    pass
