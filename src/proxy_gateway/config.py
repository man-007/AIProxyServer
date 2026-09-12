import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from dotenv import load_dotenv

from proxy_gateway.utils.logging import normalize_log_level, get_logger

logger = get_logger("config")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env", override=False)
logger.debug("config::_env environment loaded from .env file")


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    """Read one environment setting while preserving an explicit default."""
    value = os.getenv(name)
    if value is None:
        return default
    return value


def _validated_https_url(value: str) -> str:
    """Validate that the configured upstream is an HTTPS host root."""
    if not value:
        raise ValueError("Upstream URL cannot be empty.")
    if not value.startswith("https://"):
        raise ValueError("UPSTREAM_BASE_URL must use HTTPS for secure transport.")
    parsed = urlparse(value)
    if not parsed.netloc or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("UPSTREAM_BASE_URL must be an HTTPS host root; configure API paths separately.")
    return value.rstrip("/")


def _split_csv(value: Optional[str], default: Optional[str] = None) -> list[str]:
    """Convert a comma-separated environment value into trimmed entries."""
    raw = value if value is not None else default or ""
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass
class Settings:
    """Represent proxy and upstream configuration loaded from the environment."""

    host: str = _env("PROXY_HOST", "127.0.0.1") or "127.0.0.1"
    port: int = int(_env("PROXY_PORT", "8080") or "8080")
    upstream_base_url: str = _validated_https_url(_env("UPSTREAM_BASE_URL", "https://integrate.api.nvidia.com") or "https://integrate.api.nvidia.com")
    upstream_api_key: str = _env("UPSTREAM_API_KEY", "") or ""
    models_path: str = _env("UPSTREAM_MODELS_PATH", "/v1/models") or "/v1/models"
    chat_path: str = _env("UPSTREAM_CHAT_COMPLETIONS_PATH", "/v1/chat/completions") or "/v1/chat/completions"
    upstream_client: str = (_env("UPSTREAM_CLIENT", "httpx") or "httpx").lower()
    upstream_timeout_seconds: float = float(_env("UPSTREAM_TIMEOUT_SECONDS", "120") or "120")
    model_discovery_enabled: bool = (_env("MODEL_DISCOVERY_ENABLED", "false") or "false").lower() == "true"
    default_model: str = _env("DEFAULT_MODEL", "") or ""
    model_cache_ttl_seconds: int = int(_env("MODEL_CACHE_TTL_SECONDS", "300") or "300")
    log_level: str = _env("LOG_LEVEL", "info") or "info"
    proxy_auth_enabled: bool = (_env("PROXY_AUTH_ENABLED", "false") or "false").lower() == "true"
    proxy_api_key: str = _env("PROXY_API_KEY", "") or ""
    cors_allowed_origins: list[str] = field(
        default_factory=lambda: _split_csv(
            _env(
                "CORS_ALLOWED_ORIGINS",
                "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173",
            )
        )
    )
    rate_limit_enabled: bool = (_env("RATE_LIMIT_ENABLED", "false") or "false").lower() == "true"
    rate_limit_requests_per_minute: int = int(_env("RATE_LIMIT_REQUESTS_PER_MINUTE", "120") or "120")
    redis_url: str = _env("REDIS_URL", "") or ""
    trust_proxy_headers: bool = (_env("TRUST_PROXY_HEADERS", "false") or "false").lower() == "true"

    def validate(self, require_upstream_api_key: bool = False) -> None:
        """Reject unsafe or inconsistent settings before the server starts."""
        logger.debug("Settings::validate validating settings", extra={"require_upstream_api_key": require_upstream_api_key})
        normalize_log_level(self.log_level)
        if not 1 <= self.port <= 65535:
            raise ValueError("PROXY_PORT must be between 1 and 65535.")
        if self.model_cache_ttl_seconds < 0:
            raise ValueError("MODEL_CACHE_TTL_SECONDS cannot be negative.")
        if self.upstream_timeout_seconds <= 0:
            raise ValueError("UPSTREAM_TIMEOUT_SECONDS must be positive.")
        if self.upstream_client not in {"httpx", "openai"}:
            raise ValueError("UPSTREAM_CLIENT must be either 'httpx' or 'openai'.")
        if self.rate_limit_enabled and self.rate_limit_requests_per_minute <= 0:
            raise ValueError("RATE_LIMIT_REQUESTS_PER_MINUTE must be positive.")
        if self.proxy_auth_enabled and not self.proxy_api_key:
            raise ValueError("PROXY_API_KEY is required when PROXY_AUTH_ENABLED=true.")
        if self.host not in {"127.0.0.1", "localhost", "::1"} and not self.proxy_auth_enabled:
            raise ValueError("PROXY_AUTH_ENABLED=true is required when PROXY_HOST is not loopback.")
        if require_upstream_api_key and not self.upstream_api_key:
            raise ValueError("UPSTREAM_API_KEY is required for upstream access.")
        for origin in self.cors_allowed_origins:
            if origin == "*":
                raise ValueError("Wildcard CORS origins are not allowed.")


settings = Settings()
logger.debug("Settings::module instantiated settings", extra={"log_level": settings.log_level, "proxy_auth_enabled": settings.proxy_auth_enabled})


def get_settings() -> Settings:
    """Return the process-wide settings instance used by application wiring."""
    logger.debug("config::get_settings returning settings")
    return settings