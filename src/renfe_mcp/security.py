"""
Security module for Renfe MCP Server.

Provides authentication, authorization, rate limiting, and security logging.
Uses the centralized AppConfig for configuration.
"""

import hashlib
import logging
import secrets
from collections import defaultdict, deque
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Optional, Dict, Any, Callable

from renfe_mcp.config import get_config, AppConfig

logger = logging.getLogger(__name__)


# ============================================================================
# Legacy Compatibility Layer
# ============================================================================

class SecurityConfig:
    """
    Legacy SecurityConfig wrapper around AppConfig.

    Provides backward compatibility with existing code while using
    the new centralized configuration.
    """

    def __init__(self, config: Optional[AppConfig] = None):
        """Initialize from AppConfig."""
        self._config = config or get_config()

    # Map old attribute names to new config
    @property
    def ENABLE_AUTH(self) -> bool:
        return self._config.enable_auth

    @property
    def API_KEY(self) -> Optional[str]:
        return self._config.api_key

    @property
    def API_KEY_HASH(self) -> Optional[str]:
        return self._config.api_key_hash

    @property
    def RATE_LIMIT_ENABLED(self) -> bool:
        return self._config.rate_limit_enabled

    @property
    def MAX_REQUESTS_PER_MINUTE(self) -> int:
        return self._config.max_requests_per_minute

    @property
    def MAX_REQUESTS_PER_HOUR(self) -> int:
        return self._config.max_requests_per_hour

    @property
    def MAX_PRICE_REQUESTS_PER_MINUTE(self) -> int:
        return self._config.max_price_requests_per_minute

    @property
    def MAX_PRICE_REQUESTS_PER_HOUR(self) -> int:
        return self._config.max_price_requests_per_hour

    @property
    def LOG_SECURITY_EVENTS(self) -> bool:
        return self._config.log_security_events

    @property
    def LOG_SENSITIVE_DATA(self) -> bool:
        return self._config.log_sensitive_data

    @property
    def SESSION_TIMEOUT(self) -> int:
        return self._config.session_timeout

    @property
    def DEV_MODE(self) -> bool:
        return self._config.dev_mode

    def validate(self) -> tuple[bool, list[str]]:
        """Validate security configuration."""
        return self._config.validate_config()


# Global security configuration
_security_config: Optional[SecurityConfig] = None


def get_security_config() -> SecurityConfig:
    """Get the global security configuration."""
    global _security_config
    if _security_config is None:
        _security_config = SecurityConfig()
    return _security_config


# ============================================================================
# Authentication
# ============================================================================

class AuthenticationManager:
    """Manages API key authentication."""

    def __init__(self, config: SecurityConfig):
        """Initialize authentication manager."""
        self.config = config
        self._api_key_hash = None

        if config.API_KEY:
            self._api_key_hash = self._hash_api_key(config.API_KEY)
        elif config.API_KEY_HASH:
            self._api_key_hash = config.API_KEY_HASH

    @staticmethod
    def _hash_api_key(api_key: str) -> str:
        """Hash an API key using SHA-256."""
        return hashlib.sha256(api_key.encode()).hexdigest()

    def verify_api_key(self, api_key: Optional[str]) -> bool:
        """Verify an API key."""
        # In dev mode with auth disabled, allow everything
        if self.config.DEV_MODE and not self.config.ENABLE_AUTH:
            return True

        # If auth is disabled but not in dev mode, warn but allow
        if not self.config.ENABLE_AUTH:
            logger.warning("Authentication is disabled - allowing access without API key")
            return True

        # Auth is enabled - require valid API key
        if not api_key:
            logger.warning("Authentication failed: No API key provided")
            return False

        if not self._api_key_hash:
            logger.error("Authentication failed: No API key configured on server")
            return False

        # Constant-time comparison to prevent timing attacks
        provided_hash = self._hash_api_key(api_key)
        is_valid = secrets.compare_digest(provided_hash, self._api_key_hash)

        if not is_valid:
            logger.warning("Authentication failed: Invalid API key")

        return is_valid

    @staticmethod
    def generate_api_key() -> str:
        """Generate a secure random API key."""
        return secrets.token_hex(32)


# Global authentication manager
_auth_manager: Optional[AuthenticationManager] = None


def get_auth_manager() -> AuthenticationManager:
    """Get the global authentication manager."""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthenticationManager(get_security_config())
    return _auth_manager


# ============================================================================
# Rate Limiting
# ============================================================================

class RateLimiter:
    """Token bucket rate limiter with per-client tracking."""

    def __init__(self, config: SecurityConfig):
        """Initialize rate limiter."""
        self.config = config
        self._minute_requests: Dict[str, deque] = defaultdict(deque)
        self._hour_requests: Dict[str, deque] = defaultdict(deque)
        self._price_minute_requests: Dict[str, deque] = defaultdict(deque)
        self._price_hour_requests: Dict[str, deque] = defaultdict(deque)

    def _clean_old_requests(self, request_queue: deque, time_window: timedelta) -> None:
        """Remove requests older than the time window."""
        cutoff_time = datetime.now() - time_window
        while request_queue and request_queue[0] < cutoff_time:
            request_queue.popleft()

    def check_rate_limit(
        self,
        client_id: str,
        is_price_request: bool = False
    ) -> tuple[bool, Optional[str]]:
        """Check if a request is within rate limits."""
        if not self.config.RATE_LIMIT_ENABLED:
            return True, None

        if self.config.DEV_MODE:
            return True, None

        now = datetime.now()

        if is_price_request:
            minute_queue = self._price_minute_requests[client_id]
            hour_queue = self._price_hour_requests[client_id]
            max_per_minute = self.config.MAX_PRICE_REQUESTS_PER_MINUTE
            max_per_hour = self.config.MAX_PRICE_REQUESTS_PER_HOUR
        else:
            minute_queue = self._minute_requests[client_id]
            hour_queue = self._hour_requests[client_id]
            max_per_minute = self.config.MAX_REQUESTS_PER_MINUTE
            max_per_hour = self.config.MAX_REQUESTS_PER_HOUR

        self._clean_old_requests(minute_queue, timedelta(minutes=1))
        self._clean_old_requests(hour_queue, timedelta(hours=1))

        if len(minute_queue) >= max_per_minute:
            return False, (
                f"Rate limit exceeded: Maximum {max_per_minute} requests per minute. "
                f"Please wait before trying again."
            )

        if len(hour_queue) >= max_per_hour:
            return False, (
                f"Rate limit exceeded: Maximum {max_per_hour} requests per hour. "
                f"Please wait before trying again."
            )

        minute_queue.append(now)
        hour_queue.append(now)

        return True, None

    def get_rate_limit_status(self, client_id: str, is_price_request: bool = False) -> Dict[str, Any]:
        """Get current rate limit status for a client."""
        if is_price_request:
            minute_queue = self._price_minute_requests[client_id]
            hour_queue = self._price_hour_requests[client_id]
            max_per_minute = self.config.MAX_PRICE_REQUESTS_PER_MINUTE
            max_per_hour = self.config.MAX_PRICE_REQUESTS_PER_HOUR
        else:
            minute_queue = self._minute_requests[client_id]
            hour_queue = self._hour_requests[client_id]
            max_per_minute = self.config.MAX_REQUESTS_PER_MINUTE
            max_per_hour = self.config.MAX_REQUESTS_PER_HOUR

        self._clean_old_requests(minute_queue, timedelta(minutes=1))
        self._clean_old_requests(hour_queue, timedelta(hours=1))

        return {
            'requests_last_minute': len(minute_queue),
            'requests_last_hour': len(hour_queue),
            'limit_per_minute': max_per_minute,
            'limit_per_hour': max_per_hour,
            'remaining_minute': max_per_minute - len(minute_queue),
            'remaining_hour': max_per_hour - len(hour_queue),
        }


# Global rate limiter
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(get_security_config())
    return _rate_limiter


# ============================================================================
# Security Logging
# ============================================================================

class SecurityLogger:
    """Centralized security event logging."""

    def __init__(self, config: SecurityConfig):
        """Initialize security logger."""
        self.config = config
        self._setup_logger()

    def _setup_logger(self):
        """Set up security event logger."""
        self.logger = logging.getLogger('renfe.security')

        if not self.logger.handlers:
            log_dir = Path('logs')
            log_dir.mkdir(exist_ok=True)

            handler = logging.FileHandler(log_dir / 'security.log')
            handler.setLevel(logging.INFO)

            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)

            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def log_event(
        self,
        event_type: str,
        details: Dict[str, Any],
        level: str = 'INFO'
    ) -> None:
        """Log a security event."""
        if not self.config.LOG_SECURITY_EVENTS:
            return

        if not self.config.LOG_SENSITIVE_DATA:
            details = self._sanitize_details(details)

        log_message = f"SECURITY EVENT: {event_type}"
        log_func = getattr(self.logger, level.lower(), self.logger.info)
        log_func(log_message, extra=details)

    @staticmethod
    def _sanitize_details(details: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize sensitive data from log details."""
        sanitized = {}
        sensitive_keys = {'api_key', 'password', 'token', 'secret'}

        for key, value in details.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                sanitized[key] = '***REDACTED***'
            elif key in {'origin', 'destination', 'city_name'}:
                sanitized[key] = hashlib.sha256(str(value).encode()).hexdigest()[:8]
            else:
                sanitized[key] = value

        return sanitized


# Global security logger
_security_logger: Optional[SecurityLogger] = None


def get_security_logger() -> SecurityLogger:
    """Get the global security logger."""
    global _security_logger
    if _security_logger is None:
        _security_logger = SecurityLogger(get_security_config())
    return _security_logger


# ============================================================================
# Authentication Decorator
# ============================================================================

def require_auth(is_price_request: bool = False):
    """
    Decorator to require authentication and rate limiting for MCP tools.

    Args:
        is_price_request: True if this is a price scraping request (stricter limits)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            auth_manager = get_auth_manager()
            rate_limiter = get_rate_limiter()
            security_logger = get_security_logger()

            api_key = kwargs.get('api_key', None)

            if api_key:
                client_id = hashlib.sha256(api_key.encode()).hexdigest()[:16]
            else:
                client_id = 'anonymous'

            if not auth_manager.verify_api_key(api_key):
                security_logger.log_event(
                    'AUTH_FAILURE',
                    {
                        'function': func.__name__,
                        'client_id': client_id,
                        'reason': 'Invalid or missing API key'
                    },
                    level='WARNING'
                )
                return (
                    "Authentication failed. Please provide a valid API key.\n"
                    "Set the 'api_key' parameter or configure RENFE_API_KEY environment variable."
                )

            is_allowed, error_message = rate_limiter.check_rate_limit(
                client_id,
                is_price_request
            )

            if not is_allowed:
                security_logger.log_event(
                    'RATE_LIMIT_EXCEEDED',
                    {
                        'function': func.__name__,
                        'client_id': client_id,
                        'is_price_request': is_price_request
                    },
                    level='WARNING'
                )
                return f"{error_message}"

            security_logger.log_event(
                'ACCESS_GRANTED',
                {
                    'function': func.__name__,
                    'client_id': client_id,
                    'is_price_request': is_price_request
                }
            )

            if 'api_key' not in func.__code__.co_varnames:
                kwargs.pop('api_key', None)

            return func(*args, **kwargs)

        return wrapper
    return decorator


# ============================================================================
# Initialization
# ============================================================================

def initialize_security() -> None:
    """Initialize and validate security configuration."""
    config = get_config()
    config.print_config_summary()


def generate_api_key_file(output_path: str = ".env") -> None:
    """Generate a new API key and save it to a file."""
    api_key = AuthenticationManager.generate_api_key()
    api_key_hash = AuthenticationManager._hash_api_key(api_key)

    env_content = f"""# Renfe MCP Server Security Configuration
# Generated: {datetime.now().isoformat()}

# API Key (keep this secret!)
RENFE_API_KEY={api_key}

# API Key Hash (alternative to storing plain key)
# RENFE_API_KEY_HASH={api_key_hash}

# Authentication
RENFE_ENABLE_AUTH=true

# Rate Limiting
RENFE_RATE_LIMIT_ENABLED=true
RENFE_MAX_REQUESTS_PER_MINUTE=30
RENFE_MAX_REQUESTS_PER_HOUR=200
RENFE_MAX_PRICE_REQUESTS_PER_MINUTE=5
RENFE_MAX_PRICE_REQUESTS_PER_HOUR=30

# Security Logging
RENFE_LOG_SECURITY_EVENTS=true
RENFE_LOG_SENSITIVE_DATA=false

# Development Mode (disable in production!)
RENFE_DEV_MODE=false
"""

    output_file = Path(output_path)

    if output_file.exists():
        backup_file = output_file.with_suffix('.env.backup')
        output_file.rename(backup_file)
        print(f"Existing file backed up to: {backup_file}")

    output_file.write_text(env_content)

    print(f"API key generated and saved to: {output_path}")
    print(f"   API Key: {api_key}")
    print(f"   Hash:    {api_key_hash}")
    print()
    print("Keep this API key secure! Do not commit it to version control.")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "generate-key":
        generate_api_key_file()
    else:
        initialize_security()
