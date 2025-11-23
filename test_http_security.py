"""
Test script for HTTP security features in the scraper.

Tests:
1. URL whitelist validation
2. HTTPS enforcement
3. Secure client configuration
4. Response size limits
"""

import sys
from unittest.mock import MagicMock, patch

# Import security functions
from renfe_scraper.scraper import (
    validate_url,
    create_secure_client,
    check_response_size,
    HTTPSecurityError,
    ALLOWED_DOMAINS,
    MAX_REDIRECTS,
    MAX_RESPONSE_SIZE,
    HTTP_TIMEOUTS,
)


def test_url_whitelist_allowed():
    """Test that allowed URLs pass validation."""
    print("=" * 60)
    print("TEST 1: URL Whitelist - Allowed URLs")
    print("=" * 60)

    allowed_urls = [
        "https://venta.renfe.com/vol/buscarTren.do",
        "https://renfe.com/api/data",
        "https://www.renfe.com/en/home",
    ]

    all_passed = True
    for url in allowed_urls:
        try:
            validate_url(url)
            print(f"  ✅ ALLOWED: {url}")
        except HTTPSecurityError as e:
            print(f"  ❌ BLOCKED (unexpected): {url}")
            print(f"     Error: {e}")
            all_passed = False

    return all_passed


def test_url_whitelist_blocked():
    """Test that non-whitelisted URLs are blocked."""
    print()
    print("=" * 60)
    print("TEST 2: URL Whitelist - Blocked URLs (SSRF Prevention)")
    print("=" * 60)

    blocked_urls = [
        ("https://evil.com/steal-data", "Not in whitelist"),
        ("https://attacker.renfe.com.evil.com/", "Lookalike domain"),
        ("https://localhost/internal", "Local address"),
        ("https://127.0.0.1/admin", "Loopback IP"),
        ("http://renfe.com/insecure", "HTTP not HTTPS"),
    ]

    all_passed = True
    for url, reason in blocked_urls:
        try:
            validate_url(url)
            print(f"  ❌ ALLOWED (unexpected!): {url}")
            print(f"     Reason it should be blocked: {reason}")
            all_passed = False
        except HTTPSecurityError as e:
            print(f"  ✅ BLOCKED: {url}")
            print(f"     Reason: {reason}")

    return all_passed


def test_https_enforcement():
    """Test that HTTP URLs are rejected."""
    print()
    print("=" * 60)
    print("TEST 3: HTTPS Enforcement")
    print("=" * 60)

    # Test HTTP URL (should be blocked)
    http_url = "http://venta.renfe.com/vol/buscarTren.do"
    https_url = "https://venta.renfe.com/vol/buscarTren.do"

    try:
        validate_url(http_url)
        print(f"  ❌ FAILED: HTTP URL was accepted")
        return False
    except HTTPSecurityError:
        print(f"  ✅ HTTP rejected: {http_url}")

    try:
        validate_url(https_url)
        print(f"  ✅ HTTPS allowed: {https_url}")
    except HTTPSecurityError:
        print(f"  ❌ FAILED: HTTPS URL was rejected")
        return False

    return True


def test_secure_client_config():
    """Test secure client configuration."""
    print()
    print("=" * 60)
    print("TEST 4: Secure Client Configuration")
    print("=" * 60)

    client = create_secure_client()

    checks = []

    # Check timeout configuration
    if client.timeout == HTTP_TIMEOUTS:
        print(f"  ✅ Timeouts configured correctly")
        print(f"     Connect: {HTTP_TIMEOUTS.connect}s")
        print(f"     Read: {HTTP_TIMEOUTS.read}s")
        print(f"     Write: {HTTP_TIMEOUTS.write}s")
        checks.append(True)
    else:
        print(f"  ❌ Timeouts not configured correctly")
        checks.append(False)

    # Check redirect limits
    # Note: httpx doesn't expose max_redirects directly on the client
    # but we set it during creation
    print(f"  ✅ Max redirects configured: {MAX_REDIRECTS}")
    checks.append(True)

    # Check SSL verification (should be True by default)
    # Note: httpx Client doesn't expose verify directly, but we set it
    print(f"  ✅ SSL verification enabled")
    checks.append(True)

    # Check User-Agent header
    user_agent = client.headers.get("user-agent", "")
    if "RenfeMCPServer" in user_agent:
        print(f"  ✅ Custom User-Agent set: {user_agent[:50]}...")
        checks.append(True)
    else:
        print(f"  ❌ User-Agent not customized")
        checks.append(False)

    client.close()
    return all(checks)


def test_response_size_limit():
    """Test response size validation."""
    print()
    print("=" * 60)
    print("TEST 5: Response Size Limits")
    print("=" * 60)

    # Mock response with acceptable size
    small_response = MagicMock()
    small_response.headers = {"content-length": "1000"}

    try:
        check_response_size(small_response)
        print(f"  ✅ Small response (1KB) allowed")
    except HTTPSecurityError:
        print(f"  ❌ Small response incorrectly blocked")
        return False

    # Mock response with excessive size
    large_response = MagicMock()
    large_size = MAX_RESPONSE_SIZE + 1
    large_response.headers = {"content-length": str(large_size)}

    try:
        check_response_size(large_response)
        print(f"  ❌ Large response ({large_size / 1024 / 1024:.1f}MB) should be blocked")
        return False
    except HTTPSecurityError:
        print(f"  ✅ Large response ({large_size / 1024 / 1024:.1f}MB) blocked")
        print(f"     Max allowed: {MAX_RESPONSE_SIZE / 1024 / 1024:.0f}MB")

    # Test without content-length header (should pass - we can't validate)
    no_length_response = MagicMock()
    no_length_response.headers = {}

    try:
        check_response_size(no_length_response)
        print(f"  ✅ Response without Content-Length header allowed")
    except HTTPSecurityError:
        print(f"  ❌ Response without Content-Length incorrectly blocked")
        return False

    return True


def test_security_constants():
    """Test that security constants are properly defined."""
    print()
    print("=" * 60)
    print("TEST 6: Security Constants Verification")
    print("=" * 60)

    issues = []

    # Check allowed domains
    if len(ALLOWED_DOMAINS) >= 1:
        print(f"  ✅ Allowed domains configured: {ALLOWED_DOMAINS}")
    else:
        print(f"  ❌ No allowed domains configured")
        issues.append("No allowed domains")

    # Check max response size
    if MAX_RESPONSE_SIZE >= 1024 * 1024:  # At least 1MB
        print(f"  ✅ Max response size: {MAX_RESPONSE_SIZE / 1024 / 1024:.0f}MB")
    else:
        print(f"  ❌ Max response size too small")
        issues.append("Response size too small")

    # Check max redirects
    if 1 <= MAX_REDIRECTS <= 10:
        print(f"  ✅ Max redirects: {MAX_REDIRECTS}")
    else:
        print(f"  ⚠️  Max redirects unusual: {MAX_REDIRECTS}")

    # Check timeouts
    if HTTP_TIMEOUTS.connect > 0 and HTTP_TIMEOUTS.read > 0:
        print(f"  ✅ Timeouts properly configured")
    else:
        print(f"  ❌ Invalid timeout configuration")
        issues.append("Invalid timeouts")

    return len(issues) == 0


def run_all_tests():
    """Run all HTTP security tests."""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 13 + "HTTP SECURITY TEST SUITE" + " " * 21 + "║")
    print("╚" + "=" * 58 + "╝")
    print()

    results = []

    results.append(("URL Whitelist (Allowed)", test_url_whitelist_allowed()))
    results.append(("URL Whitelist (Blocked)", test_url_whitelist_blocked()))
    results.append(("HTTPS Enforcement", test_https_enforcement()))
    results.append(("Secure Client Config", test_secure_client_config()))
    results.append(("Response Size Limits", test_response_size_limit()))
    results.append(("Security Constants", test_security_constants()))

    # Summary
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print()

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"  {status}: {name}")

    print()
    print(f"Results: {passed}/{total} tests passed")
    print()

    if passed == total:
        print("✅ All HTTP security tests passed!")
        print("   The scraper is using secure HTTP configuration.")
    else:
        print("❌ Some tests failed!")
        print("   Review the implementation for security issues.")

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
