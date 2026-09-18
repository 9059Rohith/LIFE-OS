from typing import Literal, Self, Any
import json
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, model_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LIFEOS_", env_file=".env", extra="ignore", hide_input_in_errors=True
    )
    mode: Literal["demo", "live"] = "live"
    environment: Literal["development", "production", "test"] = "development"
    database_url: str = "sqlite:///./lifeos.db"
    auth_password: str = ""
    user_registration: bool = False
    public_demo: bool = False
    encryption_key: str = ""
    allowed_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
    static_dir: str = "frontend/dist"
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/integrations/google/callback"
    discord_bot_token: str = ""
    discord_channel_id: str = ""
    drive_proposal_file_id: str = ""
    whatsapp_enabled: bool = False
    whatsapp_bridge_enabled: bool = False
    whatsapp_headless: bool = True
    whatsapp_profile_dir: str = ".private/whatsapp"
    whatsapp_contact: str = ""
    approval_seconds: int = 600
    session_seconds: int = 86400
    rate_limit: int = 120

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [x.strip() for x in v.split(",") if x.strip()]
        return v

    @model_validator(mode="after")
    def guard(self) -> Self:
        if self.user_registration and self.mode != "live":
            raise ValueError("User registration requires live mode")
        if self.whatsapp_bridge_enabled and (self.mode != "live" or not self.whatsapp_contact):
            raise ValueError("Desktop WhatsApp bridge requires live mode and an allowlisted contact")
        if self.public_demo and not (self.mode == "demo" and self.environment == "production"):
            raise ValueError("Public demo requires demo mode in production")
        if self.environment == "production" and (
            not self.allowed_origins or not all(o.startswith("https://") for o in self.allowed_origins)
        ):
            raise ValueError("Production requires HTTPS origins")
        if self.environment == "production" and self.mode == "demo" and not self.public_demo:
            raise ValueError("Production demo requires explicit public demo opt-in")
        if self.public_demo and len(self.auth_password) < 16:
            raise ValueError("Public demo requires a strong authentication password")
        if self.mode == "live" and (len(self.auth_password) < 16 or not self.encryption_key):
            raise ValueError("Live mode requires a strong authentication password and encryption key")
        if self.encryption_key:
            from cryptography.fernet import Fernet

            Fernet(self.encryption_key.encode())
        return self
