from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"

    # Database
    database_url: str = "postgresql://candidate_true_companion:candidate_true_companion@localhost:5432/candidate_true_companion"

    # File storage
    s3_bucket: str = ""
    s3_endpoint_url: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""

    # LLM (Anthropic, routed through self-hosted Helicone — see docs/Architecture-Decisions.md §5)
    anthropic_api_key: str = ""
    anthropic_model_extraction: str = "claude-sonnet-5"  # resume parsing, structured extraction
    anthropic_model_interview: str = "claude-sonnet-5"  # live interview loop, cost/latency balance (#7)
    anthropic_model_report: str = "claude-opus-5"  # final report generation, once per session (#10)
    # Self-hosted Helicone gateway URL for Anthropic traffic. Empty string = call
    # Anthropic directly (e.g. local dev without a Helicone instance running).
    helicone_base_url: str = ""
    helicone_api_key: str = ""

    # Speech-to-text — Deepgram initially, Azure AI Foundry planned migration (see docs/Architecture-Decisions.md §4a)
    stt_provider: str = "deepgram"  # "deepgram" | "azure_foundry"
    deepgram_api_key: str = ""
    deepgram_model: str = "nova-2"
    azure_foundry_endpoint: str = ""
    azure_foundry_api_key: str = ""

    # Session limits
    session_duration_min: int = 30


settings = Settings()
