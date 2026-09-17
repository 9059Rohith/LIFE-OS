from typing import Literal, Any
from pydantic import BaseModel, ConfigDict, Field, field_validator
from zoneinfo import ZoneInfo


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EventInput(Strict):
    text: str = Field(min_length=3, max_length=12000)
    simulation: bool = False
    source: Literal["text", "voice", "upload"] = "text"


class DemoInput(Strict):
    scenario: Literal["flight", "meeting"] = "flight"


class ApprovalInput(Strict):
    action_ids: list[str] = Field(max_length=20)
    version: int = Field(ge=1)


class EditInput(Strict):
    arguments: dict[str, Any]


class LoginInput(Strict):
    password: str = Field(min_length=1, max_length=1024)


class Preferences(Strict):
    name: str = Field(default="Your workspace", min_length=1, max_length=80)
    timezone: str = "Asia/Kolkata"
    retention_days: int = Field(default=30, ge=1, le=365)

    @field_validator("timezone")
    @classmethod
    def timezone_exists(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except Exception:
            raise ValueError("Unknown timezone") from None
        return v


class SpeakInput(Strict):
    text: str = Field(min_length=1, max_length=4000)
