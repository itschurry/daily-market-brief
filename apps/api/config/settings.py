"""Runtime settings for the simplified apps/api layout."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


_CURRENT_FILE = Path(__file__).resolve()
_API_DIR_CANDIDATE = _CURRENT_FILE.parents[1]

if _API_DIR_CANDIDATE.name == "api" and _API_DIR_CANDIDATE.parent.name == "apps":
    API_DIR = _API_DIR_CANDIDATE
    REPO_ROOT = API_DIR.parent.parent
else:
    API_DIR = _API_DIR_CANDIDATE
    REPO_ROOT = API_DIR

APPS_DIR = REPO_ROOT / "apps"
WEB_DIR = APPS_DIR / "web"
STORAGE_DIR = REPO_ROOT / "storage"
REPORTS_DIR = STORAGE_DIR / "reports"
LOGS_DIR = STORAGE_DIR / "logs"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(API_DIR / ".env"), str(REPO_ROOT / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: str = Field(default="openai", alias="LLM_PROVIDER")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    openai_signal_model: str | None = Field(default=None, alias="OPENAI_SIGNAL_MODEL")
    openai_playbook_model: str | None = Field(default=None, alias="OPENAI_PLAYBOOK_MODEL")
    ollama_model: str = Field(default="nemotron-3-super", alias="OLLAMA_MODEL")
    ollama_host: str = Field(default="http://127.0.0.1:11434", alias="OLLAMA_HOST")

    fred_api_key: str = Field(default="", alias="FRED_API_KEY")
    fred_key: str = Field(default="", alias="FRED_KEY")
    fred_api: str = Field(default="", alias="FRED_API")

    ecos_api_key: str = Field(default="", alias="ECOS_API_KEY")
    bok_ecos_api_key: str = Field(default="", alias="BOK_ECOS_API_KEY")
    ecos_key: str = Field(default="", alias="ECOS_KEY")

    dart_api_key: str = Field(default="", alias="DART_API_KEY")
    opendart_api_key: str = Field(default="", alias="OPENDART_API_KEY")

    kis_app_key: str = Field(default="", alias="KIS_APP_KEY")
    kis_app_secret: str = Field(default="", alias="KIS_APP_SECRET")
    kis_account_cano: str = Field(default="", alias="KIS_ACCOUNT_CANO")
    kis_account_acnt_prdt_cd: str = Field(default="", alias="KIS_ACCOUNT_ACNT_PRDT_CD")
    kis_base_url: str = Field(
        default="https://openapi.koreainvestment.com:9443",
        alias="KIS_BASE_URL",
    )

    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(default="", alias="TELEGRAM_CHAT_ID")
    telegram_enabled: bool = Field(default=False, alias="TELEGRAM_ENABLED")
    report_web_url: str = Field(default="http://localhost:8081", alias="REPORT_WEB_URL")

    smtp_host: str = Field(default="smtp.gmail.com", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: str = Field(default="", alias="SMTP_USER")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    report_recipient: str = Field(default="", alias="REPORT_RECIPIENT")

    delivery_method: str = Field(default="none", alias="DELIVERY_METHOD")
    report_output_dir: Path = Field(default=REPORTS_DIR, alias="REPORT_OUTPUT_DIR")
    logs_dir: Path = Field(default=LOGS_DIR, alias="LOGS_DIR")

    @property
    def effective_openai_signal_model(self) -> str:
        return self.openai_signal_model or self.openai_model

    @property
    def effective_openai_playbook_model(self) -> str:
        return self.openai_playbook_model or self.openai_model

    @property
    def effective_fred_api_key(self) -> str:
        return self.fred_api_key or self.fred_key or self.fred_api

    @property
    def effective_ecos_api_key(self) -> str:
        return self.ecos_api_key or self.bok_ecos_api_key or self.ecos_key

    @property
    def effective_dart_api_key(self) -> str:
        return self.dart_api_key or self.opendart_api_key


settings = Settings()


def _ensure_directory(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass


_ensure_directory(settings.report_output_dir)
_ensure_directory(settings.logs_dir)

BASE_DIR = REPO_ROOT

LLM_PROVIDER = settings.llm_provider
OPENAI_API_KEY = settings.openai_api_key
OPENAI_MODEL = settings.openai_model
OPENAI_SIGNAL_MODEL = settings.effective_openai_signal_model
OPENAI_PLAYBOOK_MODEL = settings.effective_openai_playbook_model
OLLAMA_MODEL = settings.ollama_model
OLLAMA_HOST = settings.ollama_host

FRED_API_KEY = settings.effective_fred_api_key
ECOS_API_KEY = settings.effective_ecos_api_key
DART_API_KEY = settings.effective_dart_api_key

KIS_APP_KEY = settings.kis_app_key
KIS_APP_SECRET = settings.kis_app_secret
KIS_ACCOUNT_CANO = settings.kis_account_cano
KIS_ACCOUNT_ACNT_PRDT_CD = settings.kis_account_acnt_prdt_cd
KIS_BASE_URL = settings.kis_base_url

TELEGRAM_BOT_TOKEN = settings.telegram_bot_token
TELEGRAM_CHAT_ID = settings.telegram_chat_id
TELEGRAM_ENABLED = settings.telegram_enabled
REPORT_WEB_URL = settings.report_web_url

SMTP_HOST = settings.smtp_host
SMTP_PORT = settings.smtp_port
SMTP_USER = settings.smtp_user
SMTP_PASSWORD = settings.smtp_password
REPORT_RECIPIENT = settings.report_recipient

DELIVERY_METHOD = settings.delivery_method
REPORT_OUTPUT_DIR = settings.report_output_dir
LOGS_DIR = settings.logs_dir
