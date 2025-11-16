"""
GTFS Schedule Search Module

This module handles all GTFS data loading and train schedule searching logic.
It's separate from the MCP server to make the search functionality:
- Reusable in other contexts (CLI, REST API, etc.)
- Easier to unit test independently
- More maintainable with clear separation of concerns
"""

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from dateutil import parser as date_parser


class ScheduleSearcher:
    """
    Handles GTFS schedule data loading and train searching.

    This class encapsulates all the logic for:
    - Loading GTFS CSV files
    - Parsing and validating dates
    - Finding active service IDs
    - Searching for trains between stations
    """

    def __init__(self, data_dir: Path | str = "renfe_schedule"):
        """
        Initialize the searcher and load GTFS data.

        Args:
            data_dir: Path to directory containing GTFS CSV files
        """
        self.data_dir = Path(data_dir)

        # DataFrames for GTFS data
        self.stops_df = None
        self.routes_df = None
        self.trips_df = None
        self.stop_times_df = None
        self.calendar_df = None
        self.calendar_dates_df = None

        # Load all data on initialization
        self._load_gtfs_data()

    def _load_gtfs_data(self):
        """Load all GTFS CSV files into pandas DataFrames."""
        print("Loading GTFS data...")

        # Load CSV files and strip whitespace from column names
        self.stops_df = pd.read_csv(self.data_dir / "stops.txt")
        self.stops_df.columns = self.stops_df.columns.str.strip()

        self.routes_df = pd.read_csv(self.data_dir / "routes.txt")
        self.routes_df.columns = self.routes_df.columns.str.strip()

        self.trips_df = pd.read_csv(self.data_dir / "trips.txt")
        self.trips_df.columns = self.trips_df.columns.str.strip()

        self.stop_times_df = pd.read_csv(self.data_dir / "stop_times.txt")
        self.stop_times_df.columns = self.stop_times_df.columns.str.strip()

        self.calendar_df = pd.read_csv(self.data_dir / "calendar.txt")
        self.calendar_df.columns = self.calendar_df.columns.str.strip()

        self.calendar_dates_df = pd.read_csv(self.data_dir / "calendar_dates.txt")
        self.calendar_dates_df.columns = self.calendar_dates_df.columns.str.strip()

        print("GTFS data loaded successfully!")

    @staticmethod
    def format_date(date_str: str | None = None) -> str:
        """
        Flexible date parser that handles multiple formats.
        Returns date in YYYY-MM-DD format.

        Args:
            date_str: Date string in various formats, or None for today

        Returns:
            Date in YYYY-MM-DD format

        Raises:
            ValueError: If date_str cannot be parsed
        """
        if not date_str:
            dt_obj = datetime.now()
        else:
            try:
                # European date parsing (day-first)
                if "/" in date_str:
                    parts = date_str.split()[0].split("/")
                    if len(parts) >= 2 and parts[0].isdigit():
                        first_num = int(parts[0])
                        if first_num > 12:
                            # Must be day-first (e.g., 28/11/2025)
                            dt_obj = date_parser.parse(date_str, dayfirst=True)
                        else:
                            # Use European default for Renfe
                            dt_obj = date_parser.parse(date_str, dayfirst=True)
                    else:
                        dt_obj = date_parser.parse(date_str, dayfirst=True)
                else:
                    # For ISO and other formats
                    dt_obj = date_parser.parse(date_str)

            except (ValueError, date_parser.ParserError) as e:
                raise ValueError(
                    f"❌ Could not parse date '{date_str}'. "
                    f"Supported formats:\n"
                    f"  - ISO: '2025-11-28'\n"
                    f"  - European: '28/11/2025'\n"
                    f"  - Written: 'November 28, 2025' or '28 November 2025'\n"
                    f"Error: {str(e)}"
                )

        return dt_obj.strftime("%Y-%m-%d")

    @staticmethod
    def _get_day_of_week(date_str: str) -> str:
        """Convert date string to day of week name for GTFS calendar lookup."""
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        day_name = date_obj.strftime("%A").lower()
        return day_name

    def get_active_service_ids(self, date_str: str) -> set[str]:
        """
        Determine which service IDs are active on a specific date.
        Combines calendar.txt and calendar_dates.txt logic.

        Args:
            date_str: Date in YYYY-MM-DD format

        Returns:
            Set of active service IDs for this date
        """
        # Convert date to GTFS format (YYYYMMDD)
        gtfs_date = int(date_str.replace("-", ""))
        day_of_week = self._get_day_of_week(date_str)

        active_services = set()

        # Check calendar.txt for services running on this date
        for _, service in self.calendar_df.iterrows():
            service_id = service["service_id"]
            start_date = int(service["start_date"])
            end_date = int(service["end_date"])

            # Check if date is in range
            if start_date <= gtfs_date <= end_date:
                # Check if this day of week is active
                if service[day_of_week] == 1:
                    active_services.add(service_id)

        # Apply exceptions from calendar_dates.txt
        exceptions = self.calendar_dates_df[self.calendar_dates_df["date"] == gtfs_date]
        for _, exception in exceptions.iterrows():
            service_id = exception["service_id"]
            exception_type = exception["exception_type"]

            if exception_type == 1:
                # Service added on this date
                active_services.add(service_id)
            elif exception_type == 2:
                # Service removed on this date
                active_services.discard(service_id)

        return active_services

    def search_trains(
        self,
        origin_stops: list[str],
        dest_stops: list[str],
        date_str: str,
        page: int = 1,
        per_page: int = 10
    ) -> dict[str, Any]:
        """
        Find all trains traveling from origin stops to destination stops on a specific date.

        Args:
            origin_stops: List of origin stop IDs
            dest_stops: List of destination stop IDs
            date_str: Date in YYYY-MM-DD format
            page: Page number (1-indexed)
            per_page: Results per page

        Returns:
            Dictionary with:
                - success: bool
                - results: list of train dictionaries
                - total_results: int
                - page: int
                - total_pages: int
                - message: str (if error)
        """
        # Get active service IDs for this date
        active_services = self.get_active_service_ids(date_str)

        if not active_services:
            return {
                "success": False,
                "results": [],
                "total_results": 0,
                "page": page,
                "total_pages": 0,
                "message": f"❌ No train services running on {date_str}. This might be a special holiday or outside the schedule date range."
            }

        # Filter trips that run on this date
        active_trips = self.trips_df[self.trips_df["service_id"].isin(active_services)]

        results = []

        # For each active trip, check if it goes from origin to destination
        for _, trip in active_trips.iterrows():
            trip_id = trip["trip_id"]
            route_id = trip["route_id"]

            # Get all stops for this trip
            trip_stops = self.stop_times_df[self.stop_times_df["trip_id"] == trip_id].sort_values(
                "stop_sequence"
            )

            # Find origin and destination stops
            origin_stop = None
            dest_stop = None

            for _, stop in trip_stops.iterrows():
                # Check if this is an origin stop
                if stop["stop_id"] in origin_stops and origin_stop is None:
                    # Make sure passengers can board (pickup_type == 0)
                    if stop["pickup_type"] == 0:
                        origin_stop = stop

                # Check if this is a destination stop (must come after origin)
                if stop["stop_id"] in dest_stops and origin_stop is not None:
                    # Make sure passengers can alight (drop_off_type == 0)
                    if stop["drop_off_type"] == 0:
                        dest_stop = stop
                        break

            # If we found both origin and destination, add to results
            if origin_stop is not None and dest_stop is not None:
                # Get route information
                route = self.routes_df[self.routes_df["route_id"] == route_id].iloc[0]

                # Get stop names
                origin_name = self.stops_df[self.stops_df["stop_id"] == origin_stop["stop_id"]].iloc[0]["stop_name"]
                dest_name = self.stops_df[self.stops_df["stop_id"] == dest_stop["stop_id"]].iloc[0]["stop_name"]

                # Calculate duration
                def time_to_minutes(time_str):
                    parts = time_str.split(":")
                    return int(parts[0]) * 60 + int(parts[1])

                dep_minutes = time_to_minutes(origin_stop["departure_time"])
                arr_minutes = time_to_minutes(dest_stop["arrival_time"])
                duration_minutes = arr_minutes - dep_minutes
                duration_hours = duration_minutes // 60
                duration_mins = duration_minutes % 60

                results.append({
                    "train_type": route["route_short_name"],
                    "origin_station": origin_name,
                    "departure_time": origin_stop["departure_time"],
                    "destination_station": dest_name,
                    "arrival_time": dest_stop["arrival_time"],
                    "duration_hours": duration_hours,
                    "duration_mins": duration_mins,
                    "trip_id": trip_id,
                })

        # Sort by departure time
        def time_to_minutes_for_sort(time_str):
            parts = time_str.split(":")
            return int(parts[0]) * 60 + int(parts[1])

        results.sort(key=lambda x: time_to_minutes_for_sort(x["departure_time"]))

        # Calculate pagination
        total_results = len(results)
        total_pages = (total_results + per_page - 1) // per_page if total_results > 0 else 0

        # Ensure page is within valid range
        if page > total_pages and total_pages > 0:
            page = total_pages
        if page < 1:
            page = 1

        # Calculate slice indices
        start_idx = (page - 1) * per_page
        end_idx = min(start_idx + per_page, total_results)

        # Get the current page of results
        page_results = results[start_idx:end_idx]

        return {
            "success": True,
            "results": page_results,
            "total_results": total_results,
            "page": page,
            "total_pages": total_pages,
            "start_idx": start_idx,
        }

    def get_stops_dataframe(self) -> pd.DataFrame:
        """
        Get the stops DataFrame for station service initialization.

        Returns:
            The loaded stops DataFrame
        """
        return self.stops_df
