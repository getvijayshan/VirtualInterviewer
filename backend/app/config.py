from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"

    # Database
    database_url: str = "postgresql://localhost:5432/candidate_true_companion"

    # File storage
    s3_bucket: str = ""
    s3_endpoint_url: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""

    # LLM (Anthropic, routed through Helicone)
    anthropic_api_key: str = ""
    helicone_base_url: str = "https://oai.helicone.ai/v1"  # self-hosted gateway; override per deployment
    helicone_api_key: str = ""

    # Speech-to-text — Whisper initially, Azure AI Foundry planned migration (see docs/Architecture-Decisions.md §4a)
    stt_provider: str = "whisper"  # "whisper" | "azure_foundry"
    whisper_model: str = "base"
    azure_foundry_endpoint: str = ""
    azure_foundry_api_key: str = ""

    # Session limits
    session_duration_min: int = 30


settings = Settings()
