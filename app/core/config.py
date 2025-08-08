from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False
    cors_origins: List[str] = ["*"]
    
    # Search Providers
    google_api_key: str = ""
    google_cx: str = ""
    bing_api_key: str = ""
    
    # LLM Providers
    openai_api_key: str = ""
    openrouter_api_key: str = ""
    
    # Cache & Storage
    redis_url: str = "redis://localhost:6379"
    database_url: str = ""
    
    # Rate Limiting & Caching
    rate_limit_per_minute: int = 60
    cache_ttl_search: int = 1800  # 30 minutes
    cache_ttl_crawl: int = 3600   # 1 hour
    
    # Timeouts
    http_timeout: int = 10
    llm_timeout: int = 30
    playwright_timeout: int = 15000
    
    # User Agent
    user_agent: str = "SearchAPI/1.0 (+https://example.com/bot)"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()