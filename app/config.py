from pydantic import BaseSettings


class Settings(BaseSettings):
    app_name: str = "market-data-aggregator"
    environment: str = "local"
    alpaca_api_key: str = ""
    alpaca_api_secret: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
