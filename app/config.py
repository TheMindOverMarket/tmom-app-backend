from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


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

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
