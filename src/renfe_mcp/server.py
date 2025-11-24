"""
Renfe MCP Server - Train schedules and prices for Spanish railways.

This is the main entry point for the MCP server.
"""

from typing import Any

from dotenv import load_dotenv
from fastmcp import FastMCP

from renfe_mcp.price_checker import check_prices
from renfe_mcp.schedule_searcher import ScheduleSearcher
from renfe_mcp.station_service import get_station_service
from renfe_mcp.security import require_auth, initialize_security

# Load environment variables
load_dotenv()

# ============================================================================
# 1. Configuration & Setup
# ============================================================================

# Create the MCP server
mcp = FastMCP("Renfe Train Search")

# Initialize the schedule searcher (loads GTFS data)
searcher = None


# ============================================================================
# 2. Station Lookup Helper
# ============================================================================


def get_stops_for_city(city_name: str) -> dict[str, Any]:
    """
    Map a city name to all station IDs for that city.
    Returns a dict with: success, stop_ids, stations, context

    Now uses the unified StationService for consistent station lookups.
    """
    # Use unified station service
    station_service = get_station_service()
    unified_stations = station_service.find_stations(city_name)

    # Filter to only stations with GTFS data (needed for schedule search)
    gtfs_stations = [s for s in unified_stations if s.has_gtfs_data()]

    if not gtfs_stations:
        return {
            "success": False,
            "stop_ids": [],
            "stations": [],
            "context": f"No stations found for '{city_name}'. Please check the spelling or try a different city name.",
        }

    stop_ids = [s.gtfs_id for s in gtfs_stations]
    stations = [s.name for s in gtfs_stations]

    # Build context narrative
    context = f"Searched for '{city_name}':\n"
    for i, (sid, name) in enumerate(zip(stop_ids[:3], stations[:3])):
        marker = ">" if i == 0 else " "
        context += f"  {marker} {name} (ID: {sid})\n"

    if len(stations) == 1:
        context += f"\n-> Found 1 station"
    else:
        context += f"\n-> Found {len(stations)} stations"

    return {
        "success": True,
        "stop_ids": stop_ids,
        "stations": stations,
        "context": context,
    }


# ============================================================================
# 3. MCP Tools (The "Buttons" Claude Can Press)
# ============================================================================


@mcp.tool()
@require_auth(is_price_request=False)
def search_trains(origin: str, destination: str, date: str = None, page: int = 1, per_page: int = 10, api_key: str = None) -> str:
    """
    Search for train journeys between two cities on a specific date.

    Args:
        origin: Starting city name (e.g., "Madrid", "Barcelona", "Valencia")
        destination: Destination city name (e.g., "Madrid", "Barcelona", "Sevilla")
        date: Travel date. Accepts flexible formats:
              - ISO: "2025-11-28" (RECOMMENDED)
              - European: "28/11/2025"
              - Written: "November 28, 2025" or "28 November 2025"
              If not provided, searches for today's date.
        page: Page number to display (default: 1)
        per_page: Number of results per page (default: 10, max: 50)
        api_key: API key for authentication (optional if configured via environment)

    Returns:
        Formatted string with available train options including times and durations.
    """

    # Build up a story for Claude
    story = "===================================\n"
    story += "    RENFE TRAIN SEARCH\n"
    story += "===================================\n\n"

    # Format the date
    try:
        formatted_date = searcher.format_date(date)
    except ValueError as e:
        story += str(e)
        story += "\n===================================\n"
        return story

    if date:
        story += f"Searching for trains on: {formatted_date}\n\n"
    else:
        story += f"Searching for trains on: {formatted_date} (today)\n\n"

    # Validate pagination parameters
    page = max(1, page)  # Ensure page is at least 1
    per_page = min(max(1, per_page), 50)  # Ensure per_page is between 1 and 50

    # Get station IDs for both cities
    origin_result = get_stops_for_city(origin)
    if not origin_result["success"]:
        story += origin_result["context"]
        story += "\n===================================\n"
        return story

    dest_result = get_stops_for_city(destination)
    if not dest_result["success"]:
        story += dest_result["context"]
        story += "\n===================================\n"
        return story

    origin_stops = origin_result["stop_ids"]
    dest_stops = dest_result["stop_ids"]

    # Search for trains using the searcher
    search_result = searcher.search_trains(origin_stops, dest_stops, formatted_date, page, per_page)

    # Format the results
    story += "---------------------------------\n"
    story += "AVAILABLE TRAINS\n"
    story += "---------------------------------\n\n"

    if not search_result["success"]:
        story += search_result["message"]
    elif search_result["total_results"] == 0:
        story += f"No direct trains found from {origin} to {destination} on {formatted_date}. Try a different date or check for connecting routes."
    else:
        total_results = search_result["total_results"]
        total_pages = search_result["total_pages"]
        page = search_result["page"]
        results = search_result["results"]
        start_idx = search_result["start_idx"]

        story += f"Found {total_results} train(s) total\n"
        story += f"Showing page {page} of {total_pages} ({len(results)} trains)\n\n"

        for i, train in enumerate(results, start=start_idx + 1):
            story += f"  {i}. {train['train_type']}\n"
            story += f"     {train['origin_station']} -> {train['destination_station']}\n"
            story += f"     Departs: {train['departure_time']} | Arrives: {train['arrival_time']}\n"
            story += f"     Duration: {train['duration_hours']}h {train['duration_mins']}min\n\n"

        # Add pagination navigation hints
        if total_pages > 1:
            story += "---------------------------------\n"
            if page < total_pages:
                story += f"To see more trains, use page={page + 1}\n"
            if page > 1:
                story += f"To see previous trains, use page={page - 1}\n"
            story += f"Total pages: {total_pages}\n"

    story += "\n===================================\n"

    return story


@mcp.tool()
@require_auth(is_price_request=False)
def find_station(city_name: str, api_key: str = None) -> str:
    """
    Search for train stations in a city and return matching options.

    Useful for checking what stations are available in a city before
    searching for journeys.

    Args:
        city_name: City name to search for (e.g., "Madrid", "Barcelona", "Valencia")
        api_key: API key for authentication (optional if configured via environment)

    Returns:
        A formatted string showing all matching stations with their IDs and full names.
    """

    result = get_stops_for_city(city_name)

    story = "===================================\n"
    story += "    STATION SEARCH\n"
    story += "===================================\n\n"

    story += result["context"] + "\n"

    if result["success"]:
        story += "\nAll stations found:\n"
        for i, (sid, name) in enumerate(
            zip(result["stop_ids"], result["stations"]), 1
        ):
            story += f"  {i}. {name}\n"
            story += f"     ID: {sid}\n"

    story += "\n===================================\n"

    return story


@mcp.tool()
@require_auth(is_price_request=True)
def get_train_prices(origin: str, destination: str, date: str = None, page: int = 1, per_page: int = 5, api_key: str = None) -> str:
    """
    Check actual ticket prices for trains between two cities using web scraping with pagination.

    NOTE: This tool scrapes the Renfe website and may take a few seconds to complete.
    It complements the search_trains tool by providing real-time price information.
    This endpoint has stricter rate limits due to web scraping.

    Args:
        origin: Starting city name (e.g., "Madrid", "Barcelona", "Valencia")
        destination: Destination city name (e.g., "Madrid", "Barcelona", "Sevilla")
        date: Travel date. Accepts flexible formats:
              - ISO: "2025-11-28" (RECOMMENDED)
              - European: "28/11/2025"
              - Written: "November 28, 2025" or "28 November 2025"
              If not provided, checks prices for today's date.
        page: Page number to display (default: 1)
        per_page: Number of results per page (default: 5, max: 20)
        api_key: API key for authentication (optional if configured via environment)

    Returns:
        Formatted string with train prices, availability, and booking information.
    """
    story = "===================================\n"
    story += "    RENFE PRICE CHECK\n"
    story += "===================================\n\n"

    # Format the date
    try:
        formatted_date = searcher.format_date(date)
    except ValueError as e:
        story += str(e)
        story += "\n===================================\n"
        return story

    if date:
        story += f"Checking prices for: {formatted_date}\n"
    else:
        story += f"Checking prices for: {formatted_date} (today)\n"

    story += f"Scraping Renfe website for live prices...\n\n"

    # Validate pagination parameters
    page = max(1, page)  # Ensure page is at least 1
    per_page = min(max(1, per_page), 20)  # Ensure per_page is between 1 and 20

    try:
        # Call the price checker with pagination
        results = check_prices(origin, destination, formatted_date, page=page, per_page=per_page)

        # Format results
        story += "---------------------------------\n"
        story += "PRICE RESULTS\n"
        story += "---------------------------------\n\n"

        if results:
            story += f"Showing page {page} ({len(results)} trains)\n\n"

            for i, train in enumerate(results, 1):
                hours = train["duration_minutes"] // 60
                mins = train["duration_minutes"] % 60
                duration_str = f"{hours}h {mins}min"

                availability = "[Available]" if train["available"] else "[Sold out]"
                price_str = f"{train['price']:.2f} EUR" if train["available"] else "N/A"

                story += f"  {i}. {train['train_type']}\n"
                story += f"     Departs: {train['departure_time']} | Arrives: {train['arrival_time']}\n"
                story += f"     Duration: {duration_str}\n"
                story += f"     Price: {price_str} | {availability}\n\n"

            story += "---------------------------------\n"
            story += f"To see more prices, try page={page + 1}\n"
        else:
            story += "No trains available for this page.\n"

        story += "\nTIP: Use search_trains to see the complete schedule without prices.\n"

    except ValueError as e:
        story += f"Error: {str(e)}\n"
    except Exception as e:
        story += f"Failed to check prices: {str(e)}\n"
        story += "\nThe Renfe website may be temporarily unavailable or the station names may not match.\n"
        story += "   Try using exact station names like 'MADRID PTA. ATOCHA - ALMUDENA GRANDES' or 'BARCELONA-SANTS'.\n"

    story += "\n===================================\n"

    return story


# ============================================================================
# 4. Server Startup
# ============================================================================

def initialize():
    """Initialize the server components."""
    global searcher

    # Initialize security system
    initialize_security()

    # Check for data updates before loading (optional - comment out to disable)
    try:
        from renfe_mcp.update_data import update_if_needed
        update_if_needed()
    except Exception as e:
        print(f"Could not check for updates: {e}")

    # Initialize the schedule searcher (loads GTFS data)
    searcher = ScheduleSearcher()

    # Initialize station service with GTFS data
    station_service = get_station_service(searcher.get_stops_dataframe())
    coverage = station_service.validate_coverage()
    if coverage['warnings']:
        for warning in coverage['warnings']:
            print(f"Warning: {warning}")


# Run initialization on module load
initialize()


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
