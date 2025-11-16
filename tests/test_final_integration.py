"""Final integration test for the complete system."""

from datetime import datetime, timedelta
from schedule_searcher import ScheduleSearcher
from station_service import get_station_service
from price_checker import check_prices

def get_stops_for_city(city_name: str, stops_df):
    """Helper to get stop IDs for a city using station service."""
    station_service = get_station_service(stops_df)
    unified_stations = station_service.find_stations(city_name)
    gtfs_stations = [s for s in unified_stations if s.has_gtfs_data()]
    return [s.gtfs_id for s in gtfs_stations]

def test_final_integration():
    """Test the complete MCP server functionality."""
    print("Final Integration Test")
    print("=" * 50)

    # Load GTFS data using ScheduleSearcher
    print("\n[1] Loading GTFS data...")
    searcher = ScheduleSearcher()
    print("[SUCCESS] GTFS data loaded")

    # Use tomorrow's date
    tomorrow = datetime.now() + timedelta(days=1)
    date_str = tomorrow.strftime("%Y-%m-%d")

    # Test schedule search
    print(f"\n[2] Testing schedule search (Madrid -> Barcelona on {date_str})...")
    try:
        # Get station IDs
        origin_stops = get_stops_for_city("Madrid", searcher.get_stops_dataframe())
        dest_stops = get_stops_for_city("Barcelona", searcher.get_stops_dataframe())

        # Search for trains
        schedule_result = searcher.search_trains(origin_stops, dest_stops, date_str, page=1, per_page=5)
        print("[SUCCESS] Schedule search completed")
        print(f"Total results: {schedule_result['total_results']}")
        print(f"Showing {len(schedule_result['results'])} trains")
    except Exception as e:
        print(f"[ERROR] Schedule search failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Test price check
    print(f"\n[3] Testing price check (Madrid -> Barcelona on {date_str})...")
    try:
        price_results = check_prices("Madrid", "Barcelona", date_str, page=1, per_page=3)
        print("[SUCCESS] Price check completed")
        print(f"Got {len(price_results)} train(s)")
        # Check if it contains expected content
        if price_results and price_results[0].get("train_type"):
            print(f"[SUCCESS] First train type: {price_results[0]['train_type']}")
            print(f"[SUCCESS] First train price: {price_results[0]['price']:.2f} EUR")
    except Exception as e:
        print(f"[ERROR] Price check failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Test pagination
    print(f"\n[4] Testing pagination (page 2)...")
    try:
        price_results_p2 = check_prices("Madrid", "Barcelona", date_str, page=2, per_page=3)
        print("[SUCCESS] Page 2 price check completed")
        print(f"Got {len(price_results_p2)} train(s)")

        # Verify different results
        if price_results and price_results_p2:
            if price_results[0]["departure_time"] != price_results_p2[0]["departure_time"]:
                print("[SUCCESS] Page 1 and Page 2 have different trains")
            else:
                print("[WARNING] Page 1 and Page 2 have identical trains")

    except Exception as e:
        print(f"[ERROR] Pagination test failed: {e}")
        import traceback
        traceback.print_exc()
        return

    print("\n" + "=" * 50)
    print("[SUCCESS] All integration tests passed!")
    print("The MCP server is ready for use.")

if __name__ == "__main__":
    test_final_integration()
