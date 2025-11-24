"""
Renfe Scraper - Modern DWR-based price scraper for Renfe trains.

This package provides a clean, maintainable interface for scraping train
prices from the Renfe website using their DWR (Direct Web Remoting) API.
"""

from .scraper import RenfeScraper, find_station, load_stations
from .models import Station, TrainRide
from .exceptions import (
    RenfeScraperException,
    RenfeNetworkError,
    RenfeDWRTokenError,
    RenfeStationNotFoundError,
    RenfeNoTrainsFoundError,
)

__version__ = "0.1.0"

__all__ = [
    "RenfeScraper",
    "find_station",
    "load_stations",
    "Station",
    "TrainRide",
    "RenfeScraperException",
    "RenfeNetworkError",
    "RenfeDWRTokenError",
    "RenfeStationNotFoundError",
    "RenfeNoTrainsFoundError",
]
