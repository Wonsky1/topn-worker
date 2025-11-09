"""Define configuration settings using Pydantic and manage environment variables."""

from logging import getLogger
from typing import Optional

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from pydantic import ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = getLogger(__name__)

load_dotenv("dev.env")


class Settings(BaseSettings):
    """Class defining configuration settings using Pydantic."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True
    )

    TOPN_DB_BASE_URL: str

    # Logging Configuration
    LOG_LEVEL: str = "INFO"

    # Model Configuration
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL_NAME: Optional[str] = None

    GENERATIVE_MODEL: Optional[ChatGroq] = None

    CYCLE_FREQUENCY_SECONDS: int = 10

    DEFAULT_LAST_MINUTES_GETTING: int = 45

    @field_validator("LOG_LEVEL")
    def validate_log_level(cls, value: str) -> str:
        """Validate that LOG_LEVEL is a valid logging level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        value_upper = value.upper()
        if value_upper not in valid_levels:
            logger.warning(
                "Invalid LOG_LEVEL '%s', defaulting to INFO. Valid levels: %s",
                value,
                ", ".join(valid_levels),
            )
            return "INFO"
        return value_upper

    @field_validator("GENERATIVE_MODEL")
    def generative_model(
        cls, value: Optional[ChatGroq], info: ValidationInfo
    ) -> Optional[ChatGroq]:
        env_data = info.data

        model_name = env_data.get("GROQ_MODEL_NAME")
        api_key = env_data.get("GROQ_API_KEY")

        if model_name:
            return ChatGroq(model_name=model_name, api_key=api_key)
        else:
            raise ValueError("GROQ_MODEL_NAME must be set")


settings = Settings()
