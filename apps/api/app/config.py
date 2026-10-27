from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded exclusively from environment variables or .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./sowo.db"
    # Neon (and other hosts with a connection pooler): the app uses the pooled DATABASE_URL, but migrations should
    # not run through PgBouncer, so give them the direct (unpooled) URL here. Empty means "use DATABASE_URL".
    database_url_direct: str = ""
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    whatsapp_verify_token: str = ""
    whatsapp_app_secret: str = ""
    # One token for the platform's Meta app. Which number a message came in on, and so which vendor it belongs
    # to, is stored per vendor in the database (vendors.whatsapp_phone_number_id), not here.
    whatsapp_access_token: str = ""
    whatsapp_echo_mode: bool = False
    paystack_secret_key: str = ""
    public_base_url: str = "http://localhost:8000"
    reply_delay_seconds: int = Field(default=3, ge=0)
    stock_hold_minutes: int = Field(default=15, ge=1)

    # The /simulator/* endpoints power the demo page. Turn them off on a deployment that serves real buyers.
    simulator_enabled: bool = True

    # Qwen3 through Ollama
    ollama_timeout_seconds: float = Field(default=120.0, gt=0)
    ollama_temperature: float = Field(default=0.3, ge=0, le=2)
    agent_max_tool_rounds: int = Field(default=6, ge=1, le=12)
    agent_history_messages: int = Field(default=24, ge=2)

    # WhatsApp Cloud API (Graph API version is configurable because Meta retires old ones)
    whatsapp_graph_version: str = "v23.0"

    # How long stock stays held for a bank-transfer order. People take hours to pay by transfer. (Whether a vendor
    # takes Paystack or bank transfers, and their bank details and alert phone, live on the vendor's row.)
    manual_payment_hold_minutes: int = Field(default=180, ge=1)

    # The demo shop that the unauthenticated /simulator endpoints talk to.
    simulator_vendor_name: str = "Ada's Footwear"

    # Paystack. Buyers on WhatsApp have no email, so one is generated as <phone>@<domain>.
    paystack_base_url: str = "https://api.paystack.co"
    paystack_callback_url: str = ""
    paystack_customer_email_domain: str = "customers.sowo.invalid"
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
