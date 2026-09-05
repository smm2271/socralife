from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, AliasChoices

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)
    environment: str = "development"
    database_url: str = "postgresql+psycopg://socralife:socralife@localhost/socralife"
    enable_dev_auth: bool = False
    session_secret: str = Field(default="", validation_alias=AliasChoices("SESSION_SECRET", "SECRET_KEY", "session_secret"))
    public_url: str = Field(default="http://localhost:4200", validation_alias=AliasChoices("PUBLIC_URL", "APP_ORIGIN", "public_url"))
    google_redirect_uri: str = ""
    deletion_ledger_path: str = "./data/deletions.jsonl"
    google_client_id: str = ""
    google_client_secret: str = ""
    ai_provider: str = "fake"
    chat_base_url: str = "https://api.openai.com/v1"
    chat_model: str = ""
    chat_api_key: str = ""
    embedding_base_url: str = "https://api.openai.com/v1"
    embedding_model: str = ""
    embedding_api_key: str = ""
    embedding_dimension: int = 1536
    model_timeout_seconds: int = 60
    max_output_tokens: int = 2000
    storage_root: str = "./data/files"
    storage_provider: str = "local"
    s3_bucket: str = ""
    s3_endpoint_url: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    clamav_host: str = "localhost"
    clamav_port: int = 3310
    daily_generation_limit: int = 30
    global_model_limit: int = Field(default=1000, validation_alias=AliasChoices("GLOBAL_MODEL_LIMIT", "GLOBAL_DAILY_MODEL_LIMIT", "global_model_limit"))
    storage_limit_bytes: int = 500 * 1024 * 1024
    max_file_bytes: int = 50 * 1024 * 1024

    def validate_runtime(self):
        if self.environment == "production":
            if self.enable_dev_auth or self.ai_provider == "fake":
                raise RuntimeError("Production forbids dev auth and fake AI")
            if not all([len(self.session_secret) >= 32, self.google_client_id, self.google_client_secret, self.chat_api_key, self.embedding_api_key, self.chat_model, self.embedding_model, self.public_url.startswith("https://")]):
                raise RuntimeError("Production credentials and HTTPS are required")
            if not self.database_url.startswith("postgresql"):
                raise RuntimeError("Production requires PostgreSQL")
