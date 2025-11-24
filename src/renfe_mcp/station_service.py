"""
Unified station data service.

This module provides a single source of truth for station information by combining:
1. GTFS stops.txt (primary source, auto-updated)
2. scraper/stations.json (Renfe-specific codes needed for price API)

The service uses GTFS as the canonical data source and augments it with Renfe
codes when available, enabling both schedule search and price checking.
"""

import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

import pandas as pd


@dataclass
class UnifiedStation:
    """
    Unified station representation combining GTFS and Renfe data.

    Attributes:
        name: Station display name (from GTFS or Renfe)
        gtfs_id: GTFS stop_id (if available)
        renfe_code: Renfe cdgoEstacion code (if available)
        renfe_uic: Renfe cdgoUic code (if available)
        source: Data source ('gtfs', 'renfe', or 'both')
    """
    name: str
    gtfs_id: Optional[str] = None
    renfe_code: Optional[str] = None
    renfe_uic: Optional[str] = None
    source: str = 'unknown'

    def has_gtfs_data(self) -> bool:
        """Check if station has GTFS data for schedule search."""
        return self.gtfs_id is not None

    def has_renfe_data(self) -> bool:
        """Check if station has Renfe codes for price checking."""
        return self.renfe_code is not None

    def to_gtfs_format(self) -> Dict[str, Any]:
        """Convert to format expected by main.py (GTFS-based)."""
        return {
            'stop_id': self.gtfs_id,
            'stop_name': self.name
        }

    def to_renfe_format(self):
        """Convert to format expected by scraper (Station object)."""
        from renfe_mcp.scraper.models import Station
        if not self.has_renfe_data():
            raise ValueError(f"Station '{self.name}' lacks Renfe codes for price checking")
        return Station(name=self.name, code=self.renfe_code)


class StationService:
    """
    Unified station data service combining GTFS and Renfe sources.

    This service provides a single interface for station lookups, automatically
    reconciling data from GTFS stops.txt and scraper/stations.json.
    """

    def __init__(self, gtfs_stops_df: Optional[pd.DataFrame] = None):
        """
        Initialize the station service.

        Args:
            gtfs_stops_df: Optional pre-loaded GTFS stops DataFrame.
                          If None, will attempt to load from renfe_schedule/stops.txt
        """
        self.gtfs_stops_df = gtfs_stops_df
        self.renfe_stations = self._load_renfe_stations()
        self._station_cache: Dict[str, List[UnifiedStation]] = {}

    def _load_renfe_stations(self) -> Dict[str, Dict]:
        """Load Renfe station data from stations.json."""
        # Try package location first
        stations_file = Path(__file__).parent / "scraper" / "stations.json"
        if not stations_file.exists():
            # Fallback to old location for compatibility
            stations_file = Path(__file__).parent.parent.parent / "renfe_scraper" / "stations.json"
        try:
            with open(stations_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load stations.json: {e}")
            return {}

    def _normalize_name(self, name: str) -> str:
        """Normalize station name for matching (lowercase, no accents)."""
        import unicodedata
        # Remove accents
        normalized = unicodedata.normalize('NFD', name)
        normalized = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
        return normalized.lower().strip()

    def _match_stations(self, gtfs_name: str, gtfs_id: str) -> Optional[Dict]:
        """
        Try to match a GTFS station with Renfe station data.

        Args:
            gtfs_name: Station name from GTFS
            gtfs_id: Station ID from GTFS

        Returns:
            Matching Renfe station dict if found, None otherwise
        """
        gtfs_normalized = self._normalize_name(gtfs_name)

        # Try exact match first
        for renfe_name, renfe_data in self.renfe_stations.items():
            renfe_normalized = self._normalize_name(renfe_name)
            if gtfs_normalized == renfe_normalized:
                return renfe_data

        # Try partial match (contains)
        for renfe_name, renfe_data in self.renfe_stations.items():
            renfe_normalized = self._normalize_name(renfe_name)
            if gtfs_normalized in renfe_normalized or renfe_normalized in gtfs_normalized:
                return renfe_data

        # Try matching by GTFS ID to Renfe UIC code
        for renfe_name, renfe_data in self.renfe_stations.items():
            if renfe_data.get('cdgoUic') == gtfs_id or renfe_data.get('cdgoEstacion') == gtfs_id:
                return renfe_data

        return None

    def _find_in_gtfs(self, city_name: str) -> List[UnifiedStation]:
        """Find stations in GTFS data."""
        if self.gtfs_stops_df is None:
            return []

        city_name_lower = city_name.lower()
        matching_stops = self.gtfs_stops_df[
            self.gtfs_stops_df["stop_name"].str.lower().str.contains(city_name_lower, na=False)
        ]

        stations = []
        for _, stop in matching_stops.iterrows():
            gtfs_name = stop["stop_name"]
            gtfs_id = stop["stop_id"]

            # Try to match with Renfe data
            renfe_match = self._match_stations(gtfs_name, str(gtfs_id))

            if renfe_match:
                # Both GTFS and Renfe data available
                station = UnifiedStation(
                    name=gtfs_name,  # Prefer GTFS name (more canonical)
                    gtfs_id=gtfs_id,
                    renfe_code=renfe_match.get('cdgoEstacion'),
                    renfe_uic=renfe_match.get('cdgoUic'),
                    source='both'
                )
            else:
                # Only GTFS data available
                station = UnifiedStation(
                    name=gtfs_name,
                    gtfs_id=gtfs_id,
                    source='gtfs'
                )

            stations.append(station)

        return stations

    def _find_in_renfe(self, city_name: str) -> List[UnifiedStation]:
        """Find stations in Renfe data (fallback when GTFS unavailable)."""
        city_name_upper = city_name.upper()
        city_name_normalized = self._normalize_name(city_name)

        stations = []
        for station_name, data in self.renfe_stations.items():
            # Try multiple matching strategies
            matches = (
                city_name_upper in station_name.upper() or
                city_name_normalized in self._normalize_name(station_name)
            )

            if matches:
                station = UnifiedStation(
                    name=station_name,
                    renfe_code=data.get('cdgoEstacion'),
                    renfe_uic=data.get('cdgoUic'),
                    source='renfe'
                )
                stations.append(station)

        return stations

    def find_stations(self, city_name: str) -> List[UnifiedStation]:
        """
        Find all stations matching a city name.

        This is the primary interface for station lookups. It will:
        1. First try GTFS data (if available) and augment with Renfe codes
        2. Fall back to Renfe data if GTFS is unavailable
        3. Cache results for performance

        Args:
            city_name: City or station name to search for

        Returns:
            List of UnifiedStation objects (may be empty if no matches)
        """
        # Check cache
        cache_key = city_name.lower()
        if cache_key in self._station_cache:
            return self._station_cache[cache_key]

        # Try GTFS first (primary source)
        stations = self._find_in_gtfs(city_name)

        # If no GTFS results, fall back to Renfe data
        if not stations:
            stations = self._find_in_renfe(city_name)

        # Cache and return
        self._station_cache[cache_key] = stations
        return stations

    def find_station(self, city_name: str) -> Optional[UnifiedStation]:
        """
        Find a single station matching a city name (convenience method).

        Returns the first matching station, or None if no matches found.
        For cities with multiple stations, use find_stations() instead.

        Args:
            city_name: City or station name to search for

        Returns:
            UnifiedStation or None
        """
        stations = self.find_stations(city_name)
        return stations[0] if stations else None

    def get_gtfs_stop_ids(self, city_name: str) -> List[str]:
        """
        Get all GTFS stop IDs for a city (for backward compatibility with main.py).

        Args:
            city_name: City name to search for

        Returns:
            List of GTFS stop_id strings
        """
        stations = self.find_stations(city_name)
        return [s.gtfs_id for s in stations if s.has_gtfs_data()]

    def get_renfe_station(self, city_name: str):
        """
        Get Renfe Station object for price checking (for backward compatibility).

        Args:
            city_name: City name to search for

        Returns:
            scraper.models.Station object or None

        Raises:
            ValueError: If station lacks Renfe codes
        """
        station = self.find_station(city_name)
        if not station:
            return None
        return station.to_renfe_format()

    def validate_coverage(self) -> Dict[str, Any]:
        """
        Validate data coverage and identify potential issues.

        Returns:
            Dictionary with coverage statistics and warnings
        """
        stats = {
            'gtfs_available': self.gtfs_stops_df is not None,
            'renfe_stations_count': len(self.renfe_stations),
            'gtfs_stations_count': len(self.gtfs_stops_df) if self.gtfs_stops_df is not None else 0,
            'warnings': []
        }

        if not stats['gtfs_available']:
            stats['warnings'].append('GTFS data not available - using Renfe data only')

        if not self.renfe_stations:
            stats['warnings'].append('Renfe station codes not available - price checking may fail')

        return stats


# Singleton instance (initialized when GTFS data is loaded)
_station_service: Optional[StationService] = None


def get_station_service(gtfs_stops_df: Optional[pd.DataFrame] = None) -> StationService:
    """
    Get or create the global StationService instance.

    Args:
        gtfs_stops_df: Optional GTFS stops DataFrame (only needed on first call)

    Returns:
        StationService singleton instance
    """
    global _station_service

    if _station_service is None:
        _station_service = StationService(gtfs_stops_df)
    elif gtfs_stops_df is not None and _station_service.gtfs_stops_df is None:
        # Update with GTFS data if it becomes available
        _station_service.gtfs_stops_df = gtfs_stops_df
        _station_service._station_cache.clear()  # Clear cache

    return _station_service
