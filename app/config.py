from pydantic import BaseSettings


class Settings(BaseSettings):
    app_name: str = "market-data-aggregator"
    environment: str = "local"

    class Config:
        env_file = ".env"


settings = Settings()
