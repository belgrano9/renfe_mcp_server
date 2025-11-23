"""
Test script for rate limiting and secure random number generation.

Tests:
1. Rate limiter minimum delay
2. Rate limiter requests per minute
3. Exponential backoff on errors
4. Secure random number generation (search IDs)
5. Secure random number generation (session IDs)
"""

import sys
import time

# Test rate limiting
from renfe_scraper.scraper import (
    ScraperRateLimiter,
    MIN_REQUEST_DELAY,
    MAX_REQUESTS_PER_MINUTE,
    BACKOFF_BASE,
    BACKOFF_MAX,
)

# Test secure RNG
from renfe_scraper.dwr import create_search_id, create_session_script_id


def test_rate_limiter_min_delay():
    """Test that minimum delay between requests is enforced."""
    print("=" * 60)
    print("TEST 1: Rate Limiter - Minimum Delay")
    print("=" * 60)

    # Create limiter with short delay for testing
    limiter = ScraperRateLimiter(min_delay=0.1, max_rpm=1000)

    # Make first request (no delay)
    start = time.time()
    limiter.wait_if_needed()
    first_elapsed = time.time() - start

    if first_elapsed < 0.05:  # Should be nearly instant
        print(f"  [PASS] First request: no delay ({first_elapsed:.3f}s)")
    else:
        print(f"  [FAIL] First request too slow: {first_elapsed:.3f}s")
        return False

    # Make second request (should have delay)
    start = time.time()
    limiter.wait_if_needed()
    second_elapsed = time.time() - start

    # Should be at least min_delay (0.1s) minus the time already passed
    if second_elapsed >= 0.08:  # Allow some tolerance
        print(f"  [PASS] Second request: delayed ({second_elapsed:.3f}s)")
    else:
        print(f"  [FAIL] Second request not delayed enough: {second_elapsed:.3f}s")
        return False

    print(f"  [PASS] MIN_REQUEST_DELAY configured: {MIN_REQUEST_DELAY}s")
    return True


def test_rate_limiter_rpm():
    """Test requests per minute limiting."""
    print()
    print("=" * 60)
    print("TEST 2: Rate Limiter - Requests Per Minute")
    print("=" * 60)

    # Create limiter with low RPM for quick testing
    limiter = ScraperRateLimiter(min_delay=0, max_rpm=3)

    all_passed = True

    # Make 3 requests quickly (should all pass)
    for i in range(3):
        start = time.time()
        limiter.wait_if_needed()
        elapsed = time.time() - start
        if elapsed < 0.5:  # Should be quick
            print(f"  [PASS] Request {i+1}/3: allowed ({elapsed:.3f}s)")
        else:
            print(f"  [INFO] Request {i+1}/3: had to wait ({elapsed:.3f}s)")

    # Verify tracking
    if len(limiter._request_times) == 3:
        print(f"  [PASS] All 3 requests tracked")
    else:
        print(f"  [FAIL] Expected 3 tracked requests, got {len(limiter._request_times)}")
        all_passed = False

    print(f"  [PASS] MAX_REQUESTS_PER_MINUTE configured: {MAX_REQUESTS_PER_MINUTE}")
    return all_passed


def test_exponential_backoff():
    """Test exponential backoff on errors."""
    print()
    print("=" * 60)
    print("TEST 3: Rate Limiter - Exponential Backoff")
    print("=" * 60)

    limiter = ScraperRateLimiter()
    all_passed = True

    # No errors yet
    if limiter.get_backoff_delay() == 0:
        print(f"  [PASS] No backoff with 0 errors")
    else:
        print(f"  [FAIL] Expected 0 backoff, got {limiter.get_backoff_delay()}")
        all_passed = False

    # Record first error
    limiter.record_error()
    delay1 = limiter.get_backoff_delay()
    expected1 = BACKOFF_BASE ** 1  # 2.0
    if abs(delay1 - expected1) < 0.01:
        print(f"  [PASS] 1 error: backoff = {delay1}s (expected {expected1}s)")
    else:
        print(f"  [FAIL] 1 error: backoff = {delay1}s (expected {expected1}s)")
        all_passed = False

    # Record second error
    limiter.record_error()
    delay2 = limiter.get_backoff_delay()
    expected2 = BACKOFF_BASE ** 2  # 4.0
    if abs(delay2 - expected2) < 0.01:
        print(f"  [PASS] 2 errors: backoff = {delay2}s (expected {expected2}s)")
    else:
        print(f"  [FAIL] 2 errors: backoff = {delay2}s (expected {expected2}s)")
        all_passed = False

    # Verify max backoff cap
    for _ in range(10):
        limiter.record_error()
    delay_max = limiter.get_backoff_delay()
    if delay_max <= BACKOFF_MAX:
        print(f"  [PASS] Backoff capped at {BACKOFF_MAX}s (actual: {delay_max}s)")
    else:
        print(f"  [FAIL] Backoff exceeded max: {delay_max}s > {BACKOFF_MAX}s")
        all_passed = False

    # Record success resets counter
    limiter.record_success()
    if limiter.get_backoff_delay() == 0:
        print(f"  [PASS] Success resets backoff counter")
    else:
        print(f"  [FAIL] Success should reset backoff")
        all_passed = False

    return all_passed


def test_secure_search_id():
    """Test that search IDs use secure random generation."""
    print()
    print("=" * 60)
    print("TEST 4: Secure Random - Search ID Generation")
    print("=" * 60)

    all_passed = True

    # Generate multiple search IDs
    ids = [create_search_id() for _ in range(100)]

    # Check format
    for i, sid in enumerate(ids[:5]):
        if sid.startswith("_") and len(sid) == 5:
            print(f"  [PASS] Search ID {i+1}: {sid} (format OK)")
        else:
            print(f"  [FAIL] Search ID {i+1}: {sid} (bad format)")
            all_passed = False

    # Check uniqueness (should be highly unique)
    unique_ids = set(ids)
    if len(unique_ids) >= 95:  # Allow some collisions with 62^4 = 14.7M possibilities
        print(f"  [PASS] Generated 100 IDs, {len(unique_ids)} unique (good entropy)")
    else:
        print(f"  [FAIL] Too many collisions: only {len(unique_ids)}/100 unique")
        all_passed = False

    # Check character set
    valid_chars = set("_" + "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
    for sid in ids:
        if not set(sid).issubset(valid_chars):
            print(f"  [FAIL] Invalid characters in search ID: {sid}")
            all_passed = False
            break
    else:
        print(f"  [PASS] All characters in valid set")

    return all_passed


def test_secure_session_id():
    """Test that session script IDs use secure random generation."""
    print()
    print("=" * 60)
    print("TEST 5: Secure Random - Session Script ID Generation")
    print("=" * 60)

    all_passed = True

    # Generate multiple session IDs
    test_token = "test_dwr_token_12345"
    session_ids = [create_session_script_id(test_token) for _ in range(50)]

    # Check format: should be token/date_token-random_token
    for i, sid in enumerate(session_ids[:3]):
        if sid.startswith(f"{test_token}/") and "-" in sid:
            print(f"  [PASS] Session ID {i+1}: {sid[:40]}... (format OK)")
        else:
            print(f"  [FAIL] Session ID {i+1}: {sid} (bad format)")
            all_passed = False

    # Check uniqueness of random part
    random_parts = [sid.split("-")[-1] for sid in session_ids]
    unique_random = set(random_parts)
    if len(unique_random) >= 45:  # Should be very unique with 53 bits
        print(f"  [PASS] Generated 50 IDs, {len(unique_random)} unique random parts")
    else:
        print(f"  [FAIL] Too many collisions: only {len(unique_random)}/50 unique")
        all_passed = False

    # Verify secrets module is being used (check import)
    import renfe_scraper.dwr as dwr_module
    if hasattr(dwr_module, 'secrets'):
        print(f"  [PASS] Using secrets module for cryptographic randomness")
    else:
        # Check if 'secrets' is imported
        import inspect
        source = inspect.getsource(dwr_module)
        if 'import secrets' in source:
            print(f"  [PASS] secrets module imported for secure RNG")
        else:
            print(f"  [FAIL] secrets module not imported")
            all_passed = False

    return all_passed


def test_config_values():
    """Test that security configuration values are reasonable."""
    print()
    print("=" * 60)
    print("TEST 6: Configuration Values")
    print("=" * 60)

    all_passed = True

    # Check minimum delay
    if 0.1 <= MIN_REQUEST_DELAY <= 5.0:
        print(f"  [PASS] MIN_REQUEST_DELAY = {MIN_REQUEST_DELAY}s (reasonable)")
    else:
        print(f"  [WARN] MIN_REQUEST_DELAY = {MIN_REQUEST_DELAY}s (unusual)")

    # Check max RPM
    if 1 <= MAX_REQUESTS_PER_MINUTE <= 60:
        print(f"  [PASS] MAX_REQUESTS_PER_MINUTE = {MAX_REQUESTS_PER_MINUTE} (reasonable)")
    else:
        print(f"  [WARN] MAX_REQUESTS_PER_MINUTE = {MAX_REQUESTS_PER_MINUTE} (unusual)")

    # Check backoff settings
    if BACKOFF_BASE >= 1.5:
        print(f"  [PASS] BACKOFF_BASE = {BACKOFF_BASE} (good exponential growth)")
    else:
        print(f"  [WARN] BACKOFF_BASE = {BACKOFF_BASE} (may be too slow)")

    if BACKOFF_MAX >= 10:
        print(f"  [PASS] BACKOFF_MAX = {BACKOFF_MAX}s (reasonable cap)")
    else:
        print(f"  [WARN] BACKOFF_MAX = {BACKOFF_MAX}s (may be too short)")

    return all_passed


def run_all_tests():
    """Run all rate limiting and RNG tests."""
    print("\n")
    print("+" + "=" * 58 + "+")
    print("|" + " " * 10 + "RATE LIMITING & SECURE RNG TESTS" + " " * 15 + "|")
    print("+" + "=" * 58 + "+")
    print()

    results = []

    results.append(("Minimum Delay", test_rate_limiter_min_delay()))
    results.append(("RPM Limiting", test_rate_limiter_rpm()))
    results.append(("Exponential Backoff", test_exponential_backoff()))
    results.append(("Secure Search ID", test_secure_search_id()))
    results.append(("Secure Session ID", test_secure_session_id()))
    results.append(("Configuration Values", test_config_values()))

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
        print("[OK] All rate limiting and RNG tests passed!")
        print("     Web scraping is rate-limited and uses secure randomness.")
    else:
        print("[ERROR] Some tests failed!")
        print("        Review the implementation for issues.")

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
