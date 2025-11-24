"""
Test script for authentication and security system.

This script demonstrates:
1. API key authentication
2. Rate limiting
3. Security logging
4. Configuration validation
"""

import os
from dotenv import load_dotenv

# Load environment
load_dotenv()

from renfe_mcp.security import (
    get_security_config,
    get_auth_manager,
    get_rate_limiter,
    get_security_logger,
    AuthenticationManager,
)

def test_authentication():
    """Test API key authentication."""
    print("=" * 70)
    print("  TESTING AUTHENTICATION")
    print("=" * 70)
    print()

    auth_manager = get_auth_manager()
    config = get_security_config()

    # Test with correct API key
    if config.API_KEY:
        print(f"✓ Testing with configured API key...")
        is_valid = auth_manager.verify_api_key(config.API_KEY)
        print(f"  Result: {'✅ VALID' if is_valid else '❌ INVALID'}")
        print()

    # Test with incorrect API key
    print("✓ Testing with incorrect API key...")
    is_valid = auth_manager.verify_api_key("wrong-api-key")
    print(f"  Result: {'❌ ACCEPTED (BUG!)' if is_valid else '✅ REJECTED (correct)'}")
    print()

    # Test with no API key
    print("✓ Testing with no API key...")
    is_valid = auth_manager.verify_api_key(None)
    print(f"  Result: {'✅ ACCEPTED (auth disabled)' if is_valid else '❌ REJECTED'}")
    print()


def test_rate_limiting():
    """Test rate limiting."""
    print("=" * 70)
    print("  TESTING RATE LIMITING")
    print("=" * 70)
    print()

    rate_limiter = get_rate_limiter()
    config = get_security_config()

    if not config.RATE_LIMIT_ENABLED:
        print("⚠️  Rate limiting is DISABLED")
        print()
        return

    # Test regular requests
    print("✓ Testing regular request rate limits...")
    client_id = "test_client_123"

    for i in range(5):
        is_allowed, error = rate_limiter.check_rate_limit(client_id, is_price_request=False)
        status = "✅ ALLOWED" if is_allowed else f"❌ BLOCKED: {error}"
        print(f"  Request {i+1}: {status}")

    print()

    # Test price requests (stricter limits)
    print("✓ Testing price request rate limits...")
    price_client = "test_price_client_456"

    for i in range(5):
        is_allowed, error = rate_limiter.check_rate_limit(price_client, is_price_request=True)
        status = "✅ ALLOWED" if is_allowed else f"❌ BLOCKED: {error}"
        print(f"  Price request {i+1}: {status}")

    print()

    # Show rate limit status
    print("✓ Rate limit status:")
    status = rate_limiter.get_rate_limit_status(client_id, is_price_request=False)
    print(f"  Regular requests: {status['requests_last_minute']}/{status['limit_per_minute']} per minute")
    print(f"                    {status['requests_last_hour']}/{status['limit_per_hour']} per hour")

    price_status = rate_limiter.get_rate_limit_status(price_client, is_price_request=True)
    print(f"  Price requests:   {price_status['requests_last_minute']}/{price_status['limit_per_minute']} per minute")
    print(f"                    {price_status['requests_last_hour']}/{price_status['limit_per_hour']} per hour")
    print()


def test_security_logging():
    """Test security logging."""
    print("=" * 70)
    print("  TESTING SECURITY LOGGING")
    print("=" * 70)
    print()

    security_logger = get_security_logger()
    config = get_security_config()

    if not config.LOG_SECURITY_EVENTS:
        print("⚠️  Security logging is DISABLED")
        print()
        return

    print("✓ Testing security event logging...")

    # Log various events
    security_logger.log_event(
        'AUTH_SUCCESS',
        {
            'client_id': 'test_client_123',
            'function': 'search_trains',
            'origin': 'Madrid',
            'destination': 'Barcelona',
        },
        level='INFO'
    )
    print("  ✅ Logged AUTH_SUCCESS event")

    security_logger.log_event(
        'AUTH_FAILURE',
        {
            'client_id': 'suspicious_client',
            'function': 'search_trains',
            'reason': 'Invalid API key',
            'api_key': 'should-be-redacted'
        },
        level='WARNING'
    )
    print("  ✅ Logged AUTH_FAILURE event")

    security_logger.log_event(
        'RATE_LIMIT_EXCEEDED',
        {
            'client_id': 'abusive_client',
            'function': 'get_train_prices',
            'requests': 100
        },
        level='WARNING'
    )
    print("  ✅ Logged RATE_LIMIT_EXCEEDED event")

    print()
    print(f"  📝 Security logs are written to: logs/security.log")
    print(f"     Sensitive data logging: {'ENABLED' if config.LOG_SENSITIVE_DATA else 'DISABLED'}")
    print()


def test_configuration():
    """Test configuration validation."""
    print("=" * 70)
    print("  TESTING CONFIGURATION")
    print("=" * 70)
    print()

    config = get_security_config()
    is_valid, warnings = config.validate()

    print(f"Configuration status: {'✅ VALID' if is_valid else '⚠️  HAS WARNINGS'}")
    print()

    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"  ⚠️  {warning}")
    else:
        print("✅ No configuration warnings")

    print()


def main():
    """Run all tests."""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "RENFE MCP SECURITY TEST SUITE" + " " * 24 + "║")
    print("╚" + "=" * 68 + "╝")
    print()

    test_configuration()
    test_authentication()
    test_rate_limiting()
    test_security_logging()

    print("=" * 70)
    print("  TEST SUITE COMPLETE")
    print("=" * 70)
    print()
    print("Next steps:")
    print("  1. Review logs/security.log for security events")
    print("  2. Configure .env with your production settings")
    print("  3. Test the MCP server with authentication enabled")
    print()


if __name__ == "__main__":
    main()
