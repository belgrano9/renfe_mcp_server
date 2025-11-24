"""Test logging implementation in the scraper."""

import logging
from datetime import datetime, timedelta
from renfe_mcp.price_checker import check_prices

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)

def test_logging():
    """Test that logging works correctly."""
    print("=" * 60)
    print("Testing Logging Implementation")
    print("=" * 60)
    print()

    # Use tomorrow's date
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    try:
        # Test successful price check
        print(f"[TEST] Checking prices Madrid -> Barcelona on {tomorrow}")
        print("-" * 60)

        results = check_prices("Madrid", "Barcelona", tomorrow, page=1, per_page=3)

        print()
        print(f"[SUCCESS] Got {len(results)} results")
        if results:
            print(f"First train: {results[0]['train_type']} at {results[0]['departure_time']}, {results[0]['price']} EUR")

    except Exception as e:
        print(f"\n[ERROR] {e}")

    print()
    print("=" * 60)
    print("Test completed - check log output above")
    print("=" * 60)

if __name__ == "__main__":
    test_logging()
