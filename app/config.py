from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "market-data-aggregator"
    environment: str = "local"
    alpaca_api_key: str = ""
    alpaca_api_secret: str = ""

    # Aliases for Render visibility and SDK standard compatibility
    @property
    def apca_api_key(self) -> str:
        import os
        return self.alpaca_api_key or os.getenv("APCA_API_KEY_ID") or os.getenv("API_KEY") or ""

    @property
    def apca_api_secret(self) -> str:
        import os
        return self.alpaca_api_secret or os.getenv("APCA_API_SECRET_KEY") or os.getenv("SECRET_KEY") or ""
    
    # Database
    database_url: str = ""
    run_db_migrations_on_startup: bool = True

    # External Services
    rule_engine_base_url: str = "https://rule-engine-rcg9.onrender.com"
    deviation_engine_base_url: str = ""

    # Runtime feature flags
    enable_live_market_streams: bool = True
    enable_runtime_recovery: bool = True
    session_event_queue_maxsize: int = 1000
    alpaca_ws_max_queue: int = 256

    # Auth
    jwt_secret: str = "local-secret-key-change-in-prod"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
