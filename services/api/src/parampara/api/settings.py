"""Application settings loaded from environment (BUILD_PLAN 8.1 & 9.3).

All backend Gemini model IDs live exclusively in this module.
"""

from __future__ import annotations

import base64
import os
from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MODEL_PRICES_USD_PER_1M: dict[str, tuple[float, float]] = {
    "gemini-3.5-flash": (1.50, 9.00),
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-3.8-live": (0.75, 4.50),
    "gemini-3.8-flash-lite-tts": (0.50, 9.00),
}

DEFAULT_DEMO_ORG_ID = "10000000-0000-4000-8000-000000000002"
_EPHEMERAL_LOCAL_SEED_B64 = base64.b64encode(os.urandom(32)).decode("ascii")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["local", "staging", "production"] = "local"
    app_version: str = "0.1.0"
    public_web_origin: str = "http://localhost:3000"
    database_url: str = ""
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_issuer: str = ""
    supabase_jwt_secret: str = ""
    gemini_api_key: str = ""
    model_live: str = "gemini-3.8-live"
    model_flash: str = "gemini-3.5-flash"
    model_lite: str = "gemini-3.5-flash-lite"
    model_tts: str = "gemini-3.8-flash-lite-tts"
    tts_voice_name: str = "Orus"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"
    issuer_did: str = "did:web:localhost"
    issuer_key_id: str = "key-1"
    issuer_ed25519_seed_b64: str = ""
    payout_provider: Literal["razorpayx_test", "simulated"] = "simulated"
    demo_org_id: str = DEFAULT_DEMO_ORG_ID
    max_upload_mb: int = 150

    @field_validator("demo_org_id", mode="before")
    @classmethod
    def _default_demo_org(cls, v: object) -> str:
        return str(v).strip() if v and str(v).strip() else DEFAULT_DEMO_ORG_ID

    @field_validator("model_tts", mode="before")
    @classmethod
    def _default_tts(cls, v: object) -> str:
        return str(v).strip() if v and str(v).strip() else "gemini-3.8-flash-lite-tts"

    @model_validator(mode="after")
    def _validate_issuer_seed(self) -> Settings:
        raw = self.issuer_ed25519_seed_b64.strip()
        if not raw:
            if self.app_env != "local":
                raise ValueError("ISSUER_ED25519_SEED_B64 is required when APP_ENV != local")
            self.issuer_ed25519_seed_b64 = _EPHEMERAL_LOCAL_SEED_B64
            return self
        decoded = base64.b64decode(raw)
        if len(decoded) != 32 or decoded == bytes(32):
            raise ValueError("ISSUER_ED25519_SEED_B64 must decode to 32 non-zero bytes")
        self.issuer_ed25519_seed_b64 = raw
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
