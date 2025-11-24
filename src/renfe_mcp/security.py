"""
Security module for Renfe MCP Server.

Provides authentication, authorization, rate limiting, and security logging.
"""

import hashlib
import logging
import os
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Optional, Dict, Any, Callable

logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================

class SecurityConfig:
    """Security configuration loaded from environment variables."""

    def __init__(self):
        """Initialize security configuration from environment."""
        # Authentication
        self.ENABLE_AUTH = os.getenv('RENFE_ENABLE_AUTH', 'true').lower() == 'true'
        self.API_KEY = os.getenv('RENFE_API_KEY', None)
        self.API_KEY_HASH = os.getenv('RENFE_API_KEY_HASH', None)

        # Rate limiting
        self.RATE_LIMIT_ENABLED = os.getenv('RENFE_RATE_LIMIT_ENABLED', 'true').lower() == 'true'
        self.MAX_REQUESTS_PER_MINUTE = int(os.getenv('RENFE_MAX_REQUESTS_PER_MINUTE', '30'))
        self.MAX_REQUESTS_PER_HOUR = int(os.getenv('RENFE_MAX_REQUESTS_PER_HOUR', '200'))

        # Price scraping limits (more restrictive)
        self.MAX_PRICE_REQUESTS_PER_MINUTE = int(os.getenv('RENFE_MAX_PRICE_REQUESTS_PER_MINUTE', '5'))
        self.MAX_PRICE_REQUESTS_PER_HOUR = int(os.getenv('RENFE_MAX_PRICE_REQUESTS_PER_HOUR', '30'))

        # Security logging
        self.LOG_SECURITY_EVENTS = os.getenv('RENFE_LOG_SECURITY_EVENTS', 'true').lower() == 'true'
        self.LOG_SENSITIVE_DATA = os.getenv('RENFE_LOG_SENSITIVE_DATA', 'false').lower() == 'true'

        # Session management
        self.SESSION_TIMEOUT = int(os.getenv('RENFE_SESSION_TIMEOUT', '3600'))  # 1 hour

        # Development mode (disables some security features)
        self.DEV_MODE = os.getenv('RENFE_DEV_MODE', 'false').lower() == 'true'

    def validate(self) -> tuple[bool, list[str]]:
        """
        Validate security configuration.

        Returns:
            Tuple of (is_valid, warnings)
        """
        warnings = []

        if self.ENABLE_AUTH and not self.API_KEY and not self.API_KEY_HASH:
            warnings.append(
                "Authentication is enabled but no API key configured. "
                "Set RENFE_API_KEY or RENFE_API_KEY_HASH environment variable."
            )

        if self.DEV_MODE:
            warnings.append(
                "DEV_MODE is enabled. Security features may be relaxed. "
                "DO NOT use in production!"
            )

        if not self.ENABLE_AUTH and not self.DEV_MODE:
            warnings.append(
                "Authentication is DISABLED in production mode. "
                "This is not recommended for production deployments."
            )

        return len(warnings) == 0, warnings


# Global security configuration
_security_config = SecurityConfig()


def get_security_config() -> SecurityConfig:
    """Get the global security configuration."""
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
            # Hash the API key for secure storage
            self._api_key_hash = self._hash_api_key(config.API_KEY)
        elif config.API_KEY_HASH:
            # Use pre-hashed API key
            self._api_key_hash = config.API_KEY_HASH

    @staticmethod
    def _hash_api_key(api_key: str) -> str:
        """
        Hash an API key using SHA-256.

        Args:
            api_key: Plain text API key

        Returns:
            Hex digest of the hash
        """
        return hashlib.sha256(api_key.encode()).hexdigest()

    def verify_api_key(self, api_key: Optional[str]) -> bool:
        """
        Verify an API key.

        Args:
            api_key: API key to verify

        Returns:
            True if valid, False otherwise
        """
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
        """
        Generate a secure random API key.

        Returns:
            32-character hexadecimal API key
        """
        return secrets.token_hex(32)


# Global authentication manager
_auth_manager = AuthenticationManager(_security_config)


def get_auth_manager() -> AuthenticationManager:
    """Get the global authentication manager."""
    return _auth_manager


# ============================================================================
# Rate Limiting
# ============================================================================

class RateLimiter:
    """Token bucket rate limiter with per-client tracking."""

    def __init__(self, config: SecurityConfig):
        """Initialize rate limiter."""
        self.config = config
        # Track requests per client (keyed by API key or session ID)
        self._minute_requests: Dict[str, deque] = defaultdict(deque)
        self._hour_requests: Dict[str, deque] = defaultdict(deque)

        # Track price scraping separately (more restrictive)
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
        """
        Check if a request is within rate limits.

        Args:
            client_id: Unique identifier for the client
            is_price_request: True if this is a price scraping request

        Returns:
            Tuple of (is_allowed, error_message)
        """
        if not self.config.RATE_LIMIT_ENABLED:
            return True, None

        if self.config.DEV_MODE:
            # Relaxed limits in dev mode
            return True, None

        now = datetime.now()

        if is_price_request:
            # Price scraping has stricter limits
            minute_queue = self._price_minute_requests[client_id]
            hour_queue = self._price_hour_requests[client_id]
            max_per_minute = self.config.MAX_PRICE_REQUESTS_PER_MINUTE
            max_per_hour = self.config.MAX_PRICE_REQUESTS_PER_HOUR
        else:
            # Regular requests
            minute_queue = self._minute_requests[client_id]
            hour_queue = self._hour_requests[client_id]
            max_per_minute = self.config.MAX_REQUESTS_PER_MINUTE
            max_per_hour = self.config.MAX_REQUESTS_PER_HOUR

        # Clean old requests
        self._clean_old_requests(minute_queue, timedelta(minutes=1))
        self._clean_old_requests(hour_queue, timedelta(hours=1))

        # Check minute limit
        if len(minute_queue) >= max_per_minute:
            return False, (
                f"Rate limit exceeded: Maximum {max_per_minute} requests per minute. "
                f"Please wait before trying again."
            )

        # Check hour limit
        if len(hour_queue) >= max_per_hour:
            return False, (
                f"Rate limit exceeded: Maximum {max_per_hour} requests per hour. "
                f"Please wait before trying again."
            )

        # Record this request
        minute_queue.append(now)
        hour_queue.append(now)

        return True, None

    def get_rate_limit_status(self, client_id: str, is_price_request: bool = False) -> Dict[str, Any]:
        """
        Get current rate limit status for a client.

        Args:
            client_id: Unique identifier for the client
            is_price_request: True to check price scraping limits

        Returns:
            Dictionary with rate limit statistics
        """
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

        # Clean old requests
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
_rate_limiter = RateLimiter(_security_config)


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter."""
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
        # Create security-specific logger
        self.logger = logging.getLogger('renfe.security')

        # Only add handler if not already configured
        if not self.logger.handlers:
            # Create logs directory if needed
            log_dir = Path('logs')
            log_dir.mkdir(exist_ok=True)

            # File handler for security events
            handler = logging.FileHandler(log_dir / 'security.log')
            handler.setLevel(logging.INFO)

            # Format with timestamp and details
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
        """
        Log a security event.

        Args:
            event_type: Type of security event
            details: Event details
            level: Log level (INFO, WARNING, ERROR)
        """
        if not self.config.LOG_SECURITY_EVENTS:
            return

        # Sanitize details if needed
        if not self.config.LOG_SENSITIVE_DATA:
            details = self._sanitize_details(details)

        log_message = f"SECURITY EVENT: {event_type}"

        log_func = getattr(self.logger, level.lower(), self.logger.info)
        log_func(log_message, extra=details)

    @staticmethod
    def _sanitize_details(details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize sensitive data from log details.

        Args:
            details: Original details

        Returns:
            Sanitized details
        """
        sanitized = {}

        sensitive_keys = {'api_key', 'password', 'token', 'secret'}

        for key, value in details.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                sanitized[key] = '***REDACTED***'
            elif key in {'origin', 'destination', 'city_name'}:
                # Hash location data for privacy
                sanitized[key] = hashlib.sha256(str(value).encode()).hexdigest()[:8]
            else:
                sanitized[key] = value

        return sanitized


# Global security logger
_security_logger = SecurityLogger(_security_config)


def get_security_logger() -> SecurityLogger:
    """Get the global security logger."""
    return _security_logger


# ============================================================================
# Authentication Decorator
# ============================================================================

def require_auth(is_price_request: bool = False):
    """
    Decorator to require authentication and rate limiting for MCP tools.

    Args:
        is_price_request: True if this is a price scraping request (stricter limits)

    Usage:
        @mcp.tool()
        @require_auth()
        def my_tool(arg1: str, api_key: str = None):
            # Tool implementation
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            config = get_security_config()
            auth_manager = get_auth_manager()
            rate_limiter = get_rate_limiter()
            security_logger = get_security_logger()

            # Extract API key from kwargs
            api_key = kwargs.get('api_key', None)

            # Generate client ID (use API key hash if available, otherwise 'anonymous')
            if api_key:
                client_id = hashlib.sha256(api_key.encode()).hexdigest()[:16]
            else:
                client_id = 'anonymous'

            # Check authentication
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

            # Check rate limits
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

            # Log successful access
            security_logger.log_event(
                'ACCESS_GRANTED',
                {
                    'function': func.__name__,
                    'client_id': client_id,
                    'is_price_request': is_price_request
                }
            )

            # Remove api_key from kwargs before calling the actual function
            # (unless the function explicitly needs it)
            if 'api_key' in func.__code__.co_varnames:
                # Function expects api_key, keep it
                pass
            else:
                # Function doesn't need api_key, remove it
                kwargs.pop('api_key', None)

            # Call the actual function
            return func(*args, **kwargs)

        return wrapper
    return decorator


# ============================================================================
# Initialization
# ============================================================================

def initialize_security() -> None:
    """
    Initialize and validate security configuration.

    Prints warnings and errors if configuration is invalid.
    """
    config = get_security_config()
    is_valid, warnings = config.validate()

    print("=" * 70)
    print("  SECURITY CONFIGURATION")
    print("=" * 70)
    print()

    print(f"Authentication:     {'ENABLED' if config.ENABLE_AUTH else 'DISABLED'}")
    print(f"Rate Limiting:      {'ENABLED' if config.RATE_LIMIT_ENABLED else 'DISABLED'}")
    print(f"Security Logging:   {'ENABLED' if config.LOG_SECURITY_EVENTS else 'DISABLED'}")
    print(f"Development Mode:   {'YES' if config.DEV_MODE else 'NO'}")

    if config.ENABLE_AUTH:
        has_key = bool(config.API_KEY or config.API_KEY_HASH)
        print(f"API Key Configured: {'YES' if has_key else 'NO'}")

    if config.RATE_LIMIT_ENABLED:
        print()
        print(f"Rate Limits:")
        print(f"  - Regular requests:  {config.MAX_REQUESTS_PER_MINUTE}/min, {config.MAX_REQUESTS_PER_HOUR}/hour")
        print(f"  - Price requests:    {config.MAX_PRICE_REQUESTS_PER_MINUTE}/min, {config.MAX_PRICE_REQUESTS_PER_HOUR}/hour")

    print()

    if warnings:
        print("SECURITY WARNINGS:")
        for warning in warnings:
            print(f"  - {warning}")
        print()

    if is_valid:
        print("Security configuration validated")
    else:
        print("Security configuration has warnings - review before production use")

    print()
    print("=" * 70)
    print()


# ============================================================================
# Utility Functions
# ============================================================================

def generate_api_key_file(output_path: str = ".env") -> None:
    """
    Generate a new API key and save it to a file.

    Args:
        output_path: Path to save the API key (default: .env)
    """
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
        # Create backup
        backup_file = output_file.with_suffix('.env.backup')
        output_file.rename(backup_file)
        print(f"Existing file backed up to: {backup_file}")

    output_file.write_text(env_content)

    print(f"API key generated and saved to: {output_path}")
    print(f"   API Key: {api_key}")
    print(f"   Hash:    {api_key_hash}")
    print()
    print("Keep this API key secure! Do not commit it to version control.")
    print("   Add .env to your .gitignore file.")


if __name__ == "__main__":
    # Generate API key when run as script
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "generate-key":
        generate_api_key_file()
    else:
        initialize_security()
