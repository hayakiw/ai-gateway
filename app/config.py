from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Gemini API
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    gemini_api_timeout: int = 60

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_mapping_ttl: int = 3600  # seconds

    # Server
    gateway_host: str = "0.0.0.0"
    gateway_port: int = 8080

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
