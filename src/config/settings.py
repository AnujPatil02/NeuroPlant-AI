"""
Centralized app configuration.
Loads values from .env using pydantic-settings — validates types at startup
so a missing/malformed env var fails immediately instead of deep in some layer.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App
    app_env: str = "development"
    app_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # PostgreSQL
    postgres_host: str
    postgres_port: int = 5432
    postgres_db: str
    postgres_user: str
    postgres_password: str

    # InfluxDB
    influxdb_url: str
    influxdb_token: str
    influxdb_org: str
    influxdb_bucket: str

    # Redis
    redis_host: str
    redis_port: int = 6379

    # MQTT
    mqtt_broker_host: str
    mqtt_broker_port: int = 1883

    # OPC-UA
    opcua_server_url: str

    # MLflow
    mlflow_tracking_uri: str

    # GenAI
    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    gemini_api_key: str | None = None

    # Prometheus
    prometheus_metrics_port: int = 8001

    # Web Push
    vapid_public_key: str | None = None
    vapid_private_key: str | None = None
    vapid_claim_email: str | None = None

    @property
    def postgres_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


# Single shared instance — import this everywhere instead of re-instantiating
settings = Settings()