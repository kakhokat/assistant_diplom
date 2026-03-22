from typing import Any
from typing import Literal

from pydantic import BaseModel
from pydantic import Field


class AskRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    session_id: str | None = Field(default=None, min_length=3, max_length=128)


class AssistantFeedbackRequest(BaseModel):
    session_id: str = Field(min_length=3, max_length=128)
    query: str = Field(min_length=2, max_length=500)
    reaction: Literal['up', 'down']
    intent: str | None = Field(default=None, max_length=64)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssistantFeedbackResponse(BaseModel):
    status: str


class AssistantResponse(BaseModel):
    query: str
    session_id: str
    intent: str
    answer: str
    answer_text: str
    speak_text: str
    requires_auth: bool = False
    confidence: float = Field(ge=0.0, le=1.0)
    used_services: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    result: Any = None
    alternatives: list[dict[str, Any]] = Field(default_factory=list)
