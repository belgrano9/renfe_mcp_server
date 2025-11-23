"""
Test script for privacy and cookie security features.

Tests:
1. Token sanitization (logging privacy)
2. Cookie value sanitization
3. Response text sanitization
4. Secure cookie cleanup
5. HTTPS-only cookie transmission
"""

import os
import sys
from unittest.mock import MagicMock, patch

# Ensure we're testing with sensitive data logging disabled
os.environ['RENFE_LOG_SENSITIVE_DATA'] = 'false'

# Import after setting environment
from renfe_scraper.scraper import (
    sanitize_token,
    sanitize_cookie_value,
    sanitize_response,
    LOG_SENSITIVE_DATA,
)


def test_token_sanitization():
    """Test that tokens are properly sanitized for logging."""
    print("=" * 60)
    print("TEST 1: Token Sanitization (Logging Privacy)")
    print("=" * 60)

    all_passed = True

    # Test 1: Normal token should be redacted
    token = "abc123xyz789secrettoken"
    sanitized = sanitize_token(token)

    if "secrettoken" not in sanitized and "abc1..." in sanitized:
        print(f"  [PASS] Normal token sanitized: {sanitized}")
    else:
        print(f"  [FAIL] Token not properly sanitized: {sanitized}")
        all_passed = False

    # Test 2: None token should be handled
    sanitized_none = sanitize_token(None)
    if sanitized_none == "[none]":
        print(f"  [PASS] None token handled: {sanitized_none}")
    else:
        print(f"  [FAIL] None token not handled: {sanitized_none}")
        all_passed = False

    # Test 3: Short token should be fully redacted
    short_token = "abc"
    sanitized_short = sanitize_token(short_token)
    if sanitized_short == "[redacted]":
        print(f"  [PASS] Short token fully redacted: {sanitized_short}")
    else:
        print(f"  [FAIL] Short token not redacted: {sanitized_short}")
        all_passed = False

    # Test 4: Sanitized tokens should include hash for correlation
    token1 = "same_prefix_different_suffix_1"
    token2 = "same_prefix_different_suffix_2"
    sanitized1 = sanitize_token(token1)
    sanitized2 = sanitize_token(token2)

    if sanitized1 != sanitized2 and "#" in sanitized1:
        print(f"  [PASS] Different tokens have different hashes")
        print(f"         Token1: {sanitized1}")
        print(f"         Token2: {sanitized2}")
    else:
        print(f"  [FAIL] Hash correlation not working")
        all_passed = False

    return all_passed


def test_cookie_sanitization():
    """Test that cookie values are properly sanitized."""
    print()
    print("=" * 60)
    print("TEST 2: Cookie Value Sanitization")
    print("=" * 60)

    all_passed = True

    # Test 1: Long cookie value should show length only
    long_cookie = "session_id=abc123; user_data=very_long_sensitive_value_here"
    sanitized = sanitize_cookie_value(long_cookie)

    if "sensitive" not in sanitized and "chars]" in sanitized:
        print(f"  [PASS] Long cookie sanitized: {sanitized}")
    else:
        print(f"  [FAIL] Cookie not sanitized: {sanitized}")
        all_passed = False

    # Test 2: Short cookie should be redacted
    short_cookie = "xyz"
    sanitized_short = sanitize_cookie_value(short_cookie)

    if sanitized_short == "[cookie:redacted]":
        print(f"  [PASS] Short cookie redacted: {sanitized_short}")
    else:
        print(f"  [FAIL] Short cookie not redacted: {sanitized_short}")
        all_passed = False

    return all_passed


def test_response_sanitization():
    """Test that response content is properly sanitized."""
    print()
    print("=" * 60)
    print("TEST 3: Response Text Sanitization")
    print("=" * 60)

    all_passed = True

    # Test response with sensitive data
    response = '{"token": "secret123", "user": "john@example.com", "data": "sensitive"}'
    sanitized = sanitize_response(response)

    if "secret" not in sanitized and "sensitive" not in sanitized:
        print(f"  [PASS] Response sanitized: {sanitized}")
    else:
        print(f"  [FAIL] Response contains sensitive data: {sanitized}")
        all_passed = False

    # Test that length is reported
    if "chars]" in sanitized:
        print(f"  [PASS] Response length reported in sanitized output")
    else:
        print(f"  [FAIL] Response length not reported")
        all_passed = False

    return all_passed


def test_env_setting():
    """Test that environment setting controls sanitization."""
    print()
    print("=" * 60)
    print("TEST 4: Environment Setting Control")
    print("=" * 60)

    # Verify LOG_SENSITIVE_DATA is False (as set at module load)
    if not LOG_SENSITIVE_DATA:
        print(f"  [PASS] LOG_SENSITIVE_DATA is False (privacy mode)")
    else:
        print(f"  [FAIL] LOG_SENSITIVE_DATA should be False for this test")
        return False

    # Test with sensitive data disabled
    token = "super_secret_token_value"
    sanitized = sanitize_token(token)

    if "super_secret" not in sanitized:
        print(f"  [PASS] Sensitive data is hidden when LOG_SENSITIVE_DATA=false")
    else:
        print(f"  [FAIL] Sensitive data exposed: {sanitized}")
        return False

    return True


def test_secure_cleanup_design():
    """Test that secure cleanup is properly designed."""
    print()
    print("=" * 60)
    print("TEST 5: Secure Cleanup Design Verification")
    print("=" * 60)

    from renfe_scraper.scraper import RenfeScraper

    all_passed = True

    # Check that SENSITIVE_COOKIES list exists
    if hasattr(RenfeScraper, 'SENSITIVE_COOKIES'):
        cookies = RenfeScraper.SENSITIVE_COOKIES
        print(f"  [PASS] SENSITIVE_COOKIES defined: {cookies}")
    else:
        print(f"  [FAIL] SENSITIVE_COOKIES not defined")
        all_passed = False

    # Check that _secure_cleanup method exists
    if hasattr(RenfeScraper, '_secure_cleanup'):
        print(f"  [PASS] _secure_cleanup method exists")
    else:
        print(f"  [FAIL] _secure_cleanup method missing")
        all_passed = False

    # Verify DWRSESSIONID is in sensitive cookies
    if 'DWRSESSIONID' in RenfeScraper.SENSITIVE_COOKIES:
        print(f"  [PASS] DWRSESSIONID marked as sensitive")
    else:
        print(f"  [FAIL] DWRSESSIONID not in sensitive cookies")
        all_passed = False

    return all_passed


def test_https_enforcement():
    """Test that cookies are only used with HTTPS."""
    print()
    print("=" * 60)
    print("TEST 6: HTTPS-Only Cookie Transmission")
    print("=" * 60)

    from renfe_scraper.scraper import ALLOWED_DOMAINS, validate_url, HTTPSecurityError

    all_passed = True

    # Test that HTTP URLs are rejected
    http_url = "http://venta.renfe.com/vol/test"
    try:
        validate_url(http_url)
        print(f"  [FAIL] HTTP URL should be rejected")
        all_passed = False
    except HTTPSecurityError:
        print(f"  [PASS] HTTP URL rejected (cookies only sent over HTTPS)")

    # Test that HTTPS URLs are allowed
    https_url = "https://venta.renfe.com/vol/test"
    try:
        validate_url(https_url)
        print(f"  [PASS] HTTPS URL allowed")
    except HTTPSecurityError as e:
        print(f"  [FAIL] HTTPS URL rejected: {e}")
        all_passed = False

    return all_passed


def run_all_tests():
    """Run all privacy and cookie security tests."""
    print("\n")
    print("+" + "=" * 58 + "+")
    print("|" + " " * 10 + "PRIVACY & COOKIE SECURITY TESTS" + " " * 17 + "|")
    print("+" + "=" * 58 + "+")
    print()

    results = []

    results.append(("Token Sanitization", test_token_sanitization()))
    results.append(("Cookie Sanitization", test_cookie_sanitization()))
    results.append(("Response Sanitization", test_response_sanitization()))
    results.append(("Environment Control", test_env_setting()))
    results.append(("Secure Cleanup Design", test_secure_cleanup_design()))
    results.append(("HTTPS Enforcement", test_https_enforcement()))

    # Summary
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print()

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status}: {name}")

    print()
    print(f"Results: {passed}/{total} tests passed")
    print()

    if passed == total:
        print("[OK] All privacy and cookie security tests passed!")
        print("     Sensitive data is properly protected in logs.")
        print("     Cookies are only transmitted over HTTPS.")
    else:
        print("[ERROR] Some tests failed!")
        print("        Review the implementation for security issues.")

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
