"""
Price checking wrapper for custom Renfe scraper.

This module provides a simplified interface to check train prices using the
custom renfe_scraper module with pagination support.

Now uses the unified StationService for consistent station lookups.
"""

import logging
from datetime import datetime
from typing import List, Dict, Any

from renfe_scraper import RenfeScraper
from station_service import get_station_service

logger = logging.getLogger(__name__)


def check_prices(
    origin: str,
    destination: str,
    date: str,
    page: int = 1,
    per_page: int = 5
) -> List[Dict[str, Any]]:
    """
    Check train prices using custom renfe_scraper with pagination support.

    Args:
        origin: Origin city/station name (e.g., "Madrid", "Barcelona")
        destination: Destination city/station name
        date: Date in YYYY-MM-DD format
        page: Page number (1-indexed, default: 1)
        per_page: Results per page (default: 5, max: 20)

    Returns:
        List of dictionaries with train information including prices

    Raises:
        ValueError: If stations not found or invalid date format
    """
    logger.info(f"Price check requested: {origin} → {destination} on {date}, page {page}")

    # Find origin and destination stations using unified service
    station_service = get_station_service()

    origin_unified = station_service.find_station(origin)
    if not origin_unified or not origin_unified.has_renfe_data():
        logger.warning(f"Station not found: '{origin}'")
        raise ValueError(
            f"Could not find station for '{origin}'. "
            f"Please check the station name or use find_station tool to see available stations."
        )

    dest_unified = station_service.find_station(destination)
    if not dest_unified or not dest_unified.has_renfe_data():
        logger.warning(f"Station not found: '{destination}'")
        raise ValueError(
            f"Could not find station for '{destination}'. "
            f"Please check the station name or use find_station tool to see available stations."
        )

    # Convert to Renfe format for scraper
    origin_station = origin_unified.to_renfe_format()
    dest_station = dest_unified.to_renfe_format()

    logger.debug(f"Stations resolved: {origin_station.code} → {dest_station.code}")

    # Parse date
    try:
        departure_date = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        logger.warning(f"Invalid date format: '{date}'")
        raise ValueError(f"Invalid date format '{date}'. Expected YYYY-MM-DD format.")

    # Create scraper and get train rides
    try:
        scraper = RenfeScraper(
            origin=origin_station,
            destination=dest_station,
            departure_date=departure_date,
            return_date=None  # One-way only for now
        )

        # Get train rides (all available trains)
        train_rides = scraper.get_trains()

        # Convert to dictionary format using TrainRide.to_dict()
        all_results = [ride.to_dict() for ride in train_rides]

        # Apply pagination
        per_page = min(max(1, per_page), 20)  # Limit between 1 and 20
        page = max(1, page)  # Ensure page is at least 1

        total_results = len(all_results)
        total_pages = (total_results + per_page - 1) // per_page  # Ceiling division

        # Ensure page is within valid range
        if page > total_pages and total_pages > 0:
            page = total_pages

        # Calculate slice indices
        start_idx = (page - 1) * per_page
        end_idx = min(start_idx + per_page, total_results)

        paginated_results = all_results[start_idx:end_idx]

        logger.info(
            f"Price check completed: returning {len(paginated_results)} trains (page {page}/{total_pages})",
            extra={"total_trains": total_results, "page": page, "total_pages": total_pages}
        )

        # Return paginated results
        return paginated_results

    except Exception as e:
        logger.error(f"Price check failed: {e}", exc_info=True)
        raise


def format_price_results(results: List[Dict[str, Any]], origin: str, destination: str, date: str) -> str:
    """
    Format price check results as a nice string.

    Args:
        results: List of train dictionaries from check_prices()
        origin: Origin city name
        destination: Destination city name
        date: Date string

    Returns:
        Formatted string with price information
    """
    if not results:
        return f"No trains found from {origin} to {destination} on {date}."

    output = f"PRICE CHECK RESULTS\n"
    output += f"From: {origin} -> {destination}\n"
    output += f"Date: {date}\n"
    output += f"Showing {len(results)} train(s)\n\n"

    for i, train in enumerate(results, 1):
        hours = train["duration_minutes"] // 60
        mins = train["duration_minutes"] % 60
        duration_str = f"{hours}h {mins}min"

        availability = "[Available]" if train["available"] else "[Sold out]"
        price_str = f"{train['price']:.2f} EUR" if train["available"] else "N/A"

        output += f"  {i}. {train['train_type']}\n"
        output += f"     Departs: {train['departure_time']} | Arrives: {train['arrival_time']}\n"
        output += f"     Duration: {duration_str}\n"
        output += f"     Price: {price_str} | {availability}\n\n"

    return output
