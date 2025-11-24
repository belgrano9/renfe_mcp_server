"""
Centralized configuration for Renfe MCP Server.

Uses Pydantic BaseSettings for validated, typed configuration from environment variables.
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """
    Application configuration loaded from environment variables.

    All settings can be overridden via environment variables prefixed with RENFE_.
    """

    model_config = SettingsConfigDict(
        env_prefix="RENFE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # =========================================================================
    # Authentication
    # =========================================================================

    enable_auth: bool = Field(
        default=True,
        description="Enable API key authentication"
    )
    api_key: Optional[str] = Field(
        default=None,
        description="Plain text API key (use api_key_hash for production)"
    )
    api_key_hash: Optional[str] = Field(
        default=None,
        description="SHA-256 hash of API key (more secure)"
    )

    # =========================================================================
    # Rate Limiting
    # =========================================================================

    rate_limit_enabled: bool = Field(
        default=True,
        description="Enable rate limiting"
    )
    max_requests_per_minute: int = Field(
        default=30,
        ge=1,
        le=1000,
        description="Max regular requests per minute"
    )
    max_requests_per_hour: int = Field(
        default=200,
        ge=1,
        le=10000,
        description="Max regular requests per hour"
    )
    max_price_requests_per_minute: int = Field(
        default=5,
        ge=1,
        le=100,
        description="Max price scraping requests per minute"
    )
    max_price_requests_per_hour: int = Field(
        default=30,
        ge=1,
        le=1000,
        description="Max price scraping requests per hour"
    )

    # =========================================================================
    # Logging
    # =========================================================================

    log_security_events: bool = Field(
        default=True,
        description="Log security events to file"
    )
    log_sensitive_data: bool = Field(
        default=False,
        description="Include sensitive data in logs (privacy risk)"
    )
    log_level: str = Field(
        default="INFO",
        description="Application log level"
    )

    # =========================================================================
    # Session & Timeouts
    # =========================================================================

    session_timeout: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="Session timeout in seconds"
    )

    # =========================================================================
    # Development
    # =========================================================================

    dev_mode: bool = Field(
        default=False,
        description="Enable development mode (relaxed security)"
    )

    # =========================================================================
    # Data Paths
    # =========================================================================

    gtfs_data_dir: Path = Field(
        default=Path("renfe_schedule"),
        description="Directory containing GTFS data files"
    )

    # =========================================================================
    # Validators
    # =========================================================================

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return upper

    # =========================================================================
    # Computed Properties
    # =========================================================================

    @property
    def has_api_key(self) -> bool:
        """Check if any API key is configured."""
        return bool(self.api_key or self.api_key_hash)

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return not self.dev_mode and self.enable_auth

    # =========================================================================
    # Validation
    # =========================================================================

    def validate_config(self) -> tuple[bool, list[str]]:
        """
        Validate configuration and return warnings.

        Returns:
            Tuple of (is_valid, list_of_warnings)
        """
        warnings = []

        if self.enable_auth and not self.has_api_key:
            warnings.append(
                "Authentication enabled but no API key configured. "
                "Set RENFE_API_KEY or RENFE_API_KEY_HASH."
            )

        if self.dev_mode:
            warnings.append(
                "Development mode enabled - security features relaxed. "
                "Do not use in production!"
            )

        if not self.enable_auth and not self.dev_mode:
            warnings.append(
                "Authentication disabled in non-dev mode. "
                "Not recommended for production."
            )

        if self.log_sensitive_data:
            warnings.append(
                "Sensitive data logging enabled - may violate privacy requirements."
            )

        return len(warnings) == 0, warnings

    def print_config_summary(self) -> None:
        """Print configuration summary to console."""
        print("=" * 60)
        print("  CONFIGURATION")
        print("=" * 60)
        print()
        print(f"Authentication:     {'ENABLED' if self.enable_auth else 'DISABLED'}")
        print(f"API Key Configured: {'YES' if self.has_api_key else 'NO'}")
        print(f"Rate Limiting:      {'ENABLED' if self.rate_limit_enabled else 'DISABLED'}")
        print(f"Security Logging:   {'ENABLED' if self.log_security_events else 'DISABLED'}")
        print(f"Development Mode:   {'YES' if self.dev_mode else 'NO'}")
        print(f"Log Level:          {self.log_level}")
        print()

        if self.rate_limit_enabled:
            print("Rate Limits:")
            print(f"  Regular:  {self.max_requests_per_minute}/min, {self.max_requests_per_hour}/hour")
            print(f"  Price:    {self.max_price_requests_per_minute}/min, {self.max_price_requests_per_hour}/hour")
            print()

        is_valid, warnings = self.validate_config()
        if warnings:
            print("Warnings:")
            for warning in warnings:
                print(f"  - {warning}")
            print()

        print("=" * 60)


@lru_cache()
def get_config() -> AppConfig:
    """
    Get the application configuration (cached singleton).

    Returns:
        AppConfig instance
    """
    return AppConfig()


def reset_config() -> None:
    """Reset the cached configuration (useful for testing)."""
    get_config.cache_clear()
