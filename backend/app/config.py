from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"

    # Database
    database_url: str = "postgresql://candidate_true_companion:candidate_true_companion@localhost:5432/candidate_true_companion"

    # File storage (Azure Blob Storage — switched from S3, 2026-09-20, see
    # docs/Architecture-Decisions.md §4d)
    azure_storage_connection_string: str = ""
    azure_storage_container: str = ""

    # LLM (Azure OpenAI, routed through self-hosted Helicone — see docs/Architecture-Decisions.md §4c/§5)
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    # Azure identifies models by a deployment name you choose in the Azure portal,
    # not a published model id — set these to whatever the deployments are named.
    azure_openai_deployment_extraction: str = ""  # resume parsing, structured extraction
    azure_openai_deployment_interview: str = ""  # live interview loop, cost/latency balance (#7)
    azure_openai_deployment_report: str = ""  # final report generation, once per session (#10)
    # Self-hosted Helicone gateway URL for Azure OpenAI traffic. Empty string = call
    # Azure OpenAI directly (e.g. local dev without a Helicone instance running).
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
