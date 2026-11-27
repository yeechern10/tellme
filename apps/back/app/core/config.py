import os
from pathlib import Path
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
import logging

from .paths import ENV_PATH 


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file= ENV_PATH,
        env_file_encoding="utf-8",
        extra="ignore",
    )
    # global settings
    PROJECT_NAME: str = "tellme_backend"
    VERSION: str = "0.1.0"
    DESCRIPTION: str = "Backend API for TellMe application"
    LOG_LEVEL: int = logging.INFO 
    
    # ---------- embedding ----------
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_BATCH_SIZE: int = 16

    # ---------- token limits ----------
    MAX_ARTICLE_TOKENS: int = 8000
    UNCERTAIN_ARTICLE_REANALYSIS_CONTENT_TRUNCATE: int = 2000
    EVENT_SUMMARY_MAX_OUTPUT_TOKENS:int = 1000

    # ---------- postgres ----------
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: SecretStr = SecretStr("postgres")
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "tellme_db"

    # ---------- search ----------
    SEARCH_API: str = "brave"             # 'brave' | 'serper'
    BRAVE_SEARCH_API_KEY: SecretStr | None = None
    SERPER_API_KEY: SecretStr | None = None

    # ---------- llm ----------
    CHAT_AGENT_BASE_URL: str = "http://localhost:11434/v1/"
    CHAT_AGENT_MODEL: str = "maternion/minicpm5:2b"
    CHAT_AGENT_API_KEY: SecretStr = SecretStr("null")

    ARTICLE_EVENT_GROUPING_AGENT_SOURCE: str = "ollama"
    ARTICLE_EVENT_GROUPING_AGENT_MODEL: str = "gemma4:e4b"
    ARTICLE_EVENT_GROUPING_AGENT_API_KEY: SecretStr | None = None

    EVENT_RESOLUTION_AGENT_SOURCE: str = "ollama"
    EVENT_RESOLUTION_AGENT_MODEL: str = "gemma4:e4b"
    EVENT_RESOLUTION_AGENT_API_KEY: SecretStr | None = None

    EVENT_SUMMARY_AGENT_SOURCE: str = "ollama"
    EVENT_SUMMARY_AGENT_MODEL: str = "gemma4:e4b"
    EVENT_SUMMARY_AGENT_API_KEY: SecretStr | None = None
    EVENT_SUMMARY_AGENT_MAX_OUTPUT_TOKENS: int = 1000

    EVENT_KEYWORD_MATCHING_MODEL_SOURCE: str = "ollama"
    EVENT_KEYWORD_MATCHING_MODEL: str = "gemma4:e4b"
    EVENT_KEYWORD_MATCHING_MODEL_API_KEY: SecretStr | None = None

    # ---------- misc ----------
    HF_TOKEN: SecretStr | None = None

    @property
    def pg_connection_string(self) -> str:
        pwd = self.POSTGRES_PASSWORD.get_secret_value()
        return (
            f"postgresql://{self.POSTGRES_USER}:{pwd}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


    # if no specific agent api key, fallback to chat agent api key
    @property
    def search_api_key(self) -> SecretStr :
        return {
            "brave": self.BRAVE_SEARCH_API_KEY,
            "serper": self.SERPER_API_KEY,
        }.get(self.SEARCH_API)

    def _fallback(self, specific: SecretStr | None) -> SecretStr:
        return specific or self.CHAT_AGENT_API_KEY
    
    @property
    def chat_agent_api_key(self) -> SecretStr:
        return self.CHAT_AGENT_API_KEY

    @property
    def article_event_grouping_api_key(self) -> SecretStr:
        return self._fallback(self.ARTICLE_EVENT_GROUPING_AGENT_API_KEY)

    @property
    def event_resolution_api_key(self) -> SecretStr:
        return self._fallback(self.EVENT_RESOLUTION_AGENT_API_KEY)

    @property
    def event_summary_api_key(self) -> SecretStr:
        return self._fallback(self.EVENT_SUMMARY_AGENT_API_KEY)

    @property
    def event_keyword_matching_api_key(self) -> SecretStr:
        return self._fallback(self.EVENT_KEYWORD_MATCHING_MODEL_API_KEY)

    def check_required_keys(self) -> bool:
        required_keys = [
            self.search_api_key,
            self.article_event_grouping_api_key,
            self.event_resolution_api_key,
            self.event_summary_api_key,
            self.event_keyword_matching_api_key,
        ]
        return all(key is not None for key in required_keys)

settings = Settings()


