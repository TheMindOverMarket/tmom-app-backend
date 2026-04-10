from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "market-data-aggregator"
    environment: str = "local"
    alpaca_api_key: str = ""
    alpaca_api_secret: str = ""
    
    # Database
    database_url: str = ""
    run_db_migrations_on_startup: bool = True

    # External Services
    rule_engine_base_url: str = "https://rule-engine-rcg9.onrender.com"
    deviation_engine_base_url: str = ""

    # Auth
    jwt_secret: str = "local-secret-key-change-in-prod"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
