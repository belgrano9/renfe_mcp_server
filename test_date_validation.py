"""
Test script for date validation security feature.

Tests:
1. Valid dates within bounds
2. Dates too far in the past
3. Dates too far in the future
4. Edge cases (today, yesterday, max future)
"""

import sys
from datetime import datetime, timedelta

from schedule_searcher import ScheduleSearcher, MAX_DAYS_PAST, MAX_DAYS_FUTURE


def test_valid_dates():
    """Test that valid dates within bounds are accepted."""
    print("=" * 60)
    print("TEST 1: Valid Dates Within Bounds")
    print("=" * 60)

    all_passed = True
    searcher = ScheduleSearcher

    # Test today
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        result = searcher.format_date(today)
        print(f"  [PASS] Today ({today}) accepted: {result}")
    except ValueError as e:
        print(f"  [FAIL] Today rejected: {e}")
        all_passed = False

    # Test tomorrow
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        result = searcher.format_date(tomorrow)
        print(f"  [PASS] Tomorrow ({tomorrow}) accepted: {result}")
    except ValueError as e:
        print(f"  [FAIL] Tomorrow rejected: {e}")
        all_passed = False

    # Test next week
    next_week = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    try:
        result = searcher.format_date(next_week)
        print(f"  [PASS] Next week ({next_week}) accepted: {result}")
    except ValueError as e:
        print(f"  [FAIL] Next week rejected: {e}")
        all_passed = False

    # Test None (defaults to today)
    try:
        result = searcher.format_date(None)
        print(f"  [PASS] None (defaults to today) accepted: {result}")
    except ValueError as e:
        print(f"  [FAIL] None rejected: {e}")
        all_passed = False

    return all_passed


def test_past_dates():
    """Test that dates too far in the past are rejected."""
    print()
    print("=" * 60)
    print("TEST 2: Dates Too Far in the Past")
    print("=" * 60)

    all_passed = True
    searcher = ScheduleSearcher

    # Test yesterday (should be allowed with MAX_DAYS_PAST=1)
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        result = searcher.format_date(yesterday)
        print(f"  [PASS] Yesterday ({yesterday}) accepted: {result}")
    except ValueError as e:
        print(f"  [FAIL] Yesterday should be allowed: {e}")
        all_passed = False

    # Test 2 days ago (should be rejected)
    two_days_ago = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    try:
        result = searcher.format_date(two_days_ago)
        print(f"  [FAIL] 2 days ago ({two_days_ago}) should be rejected, got: {result}")
        all_passed = False
    except ValueError as e:
        print(f"  [PASS] 2 days ago rejected correctly")

    # Test a week ago
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    try:
        result = searcher.format_date(week_ago)
        print(f"  [FAIL] Week ago ({week_ago}) should be rejected, got: {result}")
        all_passed = False
    except ValueError as e:
        print(f"  [PASS] Week ago rejected correctly")

    # Test year 2020
    try:
        result = searcher.format_date("2020-01-01")
        print(f"  [FAIL] Year 2020 should be rejected, got: {result}")
        all_passed = False
    except ValueError as e:
        print(f"  [PASS] Year 2020 rejected correctly")

    return all_passed


def test_future_dates():
    """Test that dates too far in the future are rejected."""
    print()
    print("=" * 60)
    print("TEST 3: Dates Too Far in the Future")
    print("=" * 60)

    all_passed = True
    searcher = ScheduleSearcher

    # Test max allowed date (should pass)
    max_date = (datetime.now() + timedelta(days=MAX_DAYS_FUTURE)).strftime("%Y-%m-%d")
    try:
        result = searcher.format_date(max_date)
        print(f"  [PASS] Max date ({max_date}) accepted: {result}")
    except ValueError as e:
        print(f"  [FAIL] Max date should be allowed: {e}")
        all_passed = False

    # Test one day past max (should fail)
    past_max = (datetime.now() + timedelta(days=MAX_DAYS_FUTURE + 1)).strftime("%Y-%m-%d")
    try:
        result = searcher.format_date(past_max)
        print(f"  [FAIL] Day past max ({past_max}) should be rejected, got: {result}")
        all_passed = False
    except ValueError as e:
        print(f"  [PASS] Day past max rejected correctly")

    # Test 2 years in future
    two_years = (datetime.now() + timedelta(days=730)).strftime("%Y-%m-%d")
    try:
        result = searcher.format_date(two_years)
        print(f"  [FAIL] 2 years ({two_years}) should be rejected, got: {result}")
        all_passed = False
    except ValueError as e:
        print(f"  [PASS] 2 years in future rejected correctly")

    # Test year 9999
    try:
        result = searcher.format_date("9999-12-31")
        print(f"  [FAIL] Year 9999 should be rejected, got: {result}")
        all_passed = False
    except ValueError as e:
        print(f"  [PASS] Year 9999 rejected correctly")

    return all_passed


def test_date_formats():
    """Test that various date formats are properly validated."""
    print()
    print("=" * 60)
    print("TEST 4: Various Date Formats")
    print("=" * 60)

    all_passed = True
    searcher = ScheduleSearcher

    # Valid date in various formats (using a date 30 days from now)
    target = datetime.now() + timedelta(days=30)

    # ISO format
    iso_date = target.strftime("%Y-%m-%d")
    try:
        result = searcher.format_date(iso_date)
        print(f"  [PASS] ISO format ({iso_date}) accepted: {result}")
    except ValueError as e:
        print(f"  [FAIL] ISO format rejected: {e}")
        all_passed = False

    # European format
    euro_date = target.strftime("%d/%m/%Y")
    try:
        result = searcher.format_date(euro_date)
        print(f"  [PASS] European format ({euro_date}) accepted: {result}")
    except ValueError as e:
        print(f"  [FAIL] European format rejected: {e}")
        all_passed = False

    # Written format
    written_date = target.strftime("%B %d, %Y")
    try:
        result = searcher.format_date(written_date)
        print(f"  [PASS] Written format ({written_date}) accepted: {result}")
    except ValueError as e:
        print(f"  [FAIL] Written format rejected: {e}")
        all_passed = False

    return all_passed


def test_constants():
    """Test that security constants are properly configured."""
    print()
    print("=" * 60)
    print("TEST 5: Security Constants")
    print("=" * 60)

    all_passed = True

    if MAX_DAYS_PAST == 1:
        print(f"  [PASS] MAX_DAYS_PAST = {MAX_DAYS_PAST} (allows yesterday)")
    else:
        print(f"  [INFO] MAX_DAYS_PAST = {MAX_DAYS_PAST}")

    if MAX_DAYS_FUTURE == 365:
        print(f"  [PASS] MAX_DAYS_FUTURE = {MAX_DAYS_FUTURE} (1 year ahead)")
    else:
        print(f"  [INFO] MAX_DAYS_FUTURE = {MAX_DAYS_FUTURE}")

    if MAX_DAYS_PAST >= 0:
        print(f"  [PASS] MAX_DAYS_PAST is non-negative")
    else:
        print(f"  [FAIL] MAX_DAYS_PAST should be non-negative")
        all_passed = False

    if MAX_DAYS_FUTURE > 0:
        print(f"  [PASS] MAX_DAYS_FUTURE is positive")
    else:
        print(f"  [FAIL] MAX_DAYS_FUTURE should be positive")
        all_passed = False

    return all_passed


def run_all_tests():
    """Run all date validation tests."""
    print("\n")
    print("+" + "=" * 58 + "+")
    print("|" + " " * 14 + "DATE VALIDATION SECURITY TESTS" + " " * 14 + "|")
    print("+" + "=" * 58 + "+")
    print()

    results = []

    results.append(("Valid Dates", test_valid_dates()))
    results.append(("Past Dates Rejection", test_past_dates()))
    results.append(("Future Dates Rejection", test_future_dates()))
    results.append(("Date Formats", test_date_formats()))
    results.append(("Security Constants", test_constants()))

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
        print("[OK] All date validation tests passed!")
        print("     Dates are properly validated against security bounds.")
    else:
        print("[ERROR] Some tests failed!")
        print("        Review the implementation for issues.")

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
