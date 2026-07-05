"""Configuration management for Video-Generate backend."""
from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @model_validator(mode="after")
    def _sync_complex_model(self):
        # If complex_model wasn't overridden by env, mirror llm_model
        # (When env var LLM_COMPLEX_MODEL is not set, pydantic-settings keeps the default
        #  value, which is "deepseek-v4-pro". If llm_model is different and was set via env,
        #  we want complex_model to follow it.)
        if self.llm_complex_model == "deepseek-v4-pro" and self.llm_model != "deepseek-v4-pro":
            self.llm_complex_model = self.llm_model
        return self

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/video_generate"
    redis_url: str = "redis://localhost:6379/0"

    # LLM / AI
    llm_api_key: str = "sk-orx...Y5hm"
    llm_api_url: str = "http://10.190.0.214:8080/v1"
    llm_model: str = "deepseek-v4-pro"
    llm_complex_model: str = "deepseek-v4-pro"

    # External services
    comfyui_url: str = "http://10.190.0.222:8188"
    cosyvoice_url: str = "http://10.190.0.222:8000"
    sd_api_url: str = "http://10.190.0.222:7860"

    # SiliconFlow Video Generation API
    siliconflow_api_key: str = "sk-ekw...lukp"

    # Paths
    upload_dir: str = "/data/uploads"
    output_dir: str = "/data/output"

    # JWT
    jwt_secret: str = "change-me-to-random-secret"
    jwt_algorithm: str = "HS256"
    jwt_expiration: int = 86400  # 24 hours in seconds

    # CORS
    cors_origins: str = "*"

    # Rate limiting
    rate_limit_per_minute: int = 60

    # Usage tracking
    free_tier_credits: int = 100
    pro_tier_credits: int = 10000
    enterprise_tier_credits: int = 100000

    # Image generation
    image_generation_api_url: str = ""
    image_generation_model: str = "sdxl"

    # Face swap
    face_swap_model: str = "insightface"


settings = Settings()