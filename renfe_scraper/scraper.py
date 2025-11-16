"""Main Renfe scraper implementation using DWR protocol."""

import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List
import httpx
import json5

from .models import Station, TrainRide
from .exceptions import (
    RenfeNetworkError,
    RenfeDWRTokenError,
    RenfeParseError,
)
from . import dwr

logger = logging.getLogger(__name__)


class RenfeScraper:
    """
    Modern Renfe price scraper using DWR protocol.

    This scraper interacts with Renfe's DWR (Direct Web Remoting) API to
    fetch train schedules and prices.
    """

    # URLs
    SEARCH_URL = "https://venta.renfe.com/vol/buscarTren.do?Idioma=es&Pais=ES"
    DWR_BASE = "https://venta.renfe.com/vol/dwr/call/plaincall/"
    SYSTEM_ID_URL = f"{DWR_BASE}__System.generateId.dwr"
    UPDATE_SESSION_URL = f"{DWR_BASE}buyEnlacesManager.actualizaObjetosSesion.dwr"
    TRAIN_LIST_URL = f"{DWR_BASE}trainEnlacesManager.getTrainsList.dwr"

    def __init__(
        self,
        origin: Station,
        destination: Station,
        departure_date: datetime,
        return_date: Optional[datetime] = None
    ):
        """
        Initialize the scraper.

        Args:
            origin: Origin station
            destination: Destination station
            departure_date: Departure date and time
            return_date: Optional return date
        """
        self.origin = origin
        self.destination = destination
        self.departure_date = departure_date
        self.return_date = return_date

        # Session state
        self.search_id = dwr.create_search_id()
        self.batch_id = dwr.get_batch_id_generator()
        self.dwr_token: Optional[str] = None
        self.script_session_id: Optional[str] = None

        # HTTP client
        self.client = httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "*/*",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
            }
        )

    def get_trains(self) -> List[TrainRide]:
        """
        Fetch train rides with prices.

        Returns:
            List of TrainRide objects

        Raises:
            RenfeNetworkError: On network/HTTP errors
            RenfeDWRTokenError: On token generation failures
            RenfeParseError: On response parsing failures
        """
        start_time = time.time()
        logger.info(
            f"Starting scrape: {self.origin.code} → {self.destination.code}",
            extra={
                "origin": self.origin.code,
                "destination": self.destination.code,
                "date": self.departure_date.strftime("%Y-%m-%d"),
            }
        )

        try:
            # Step 1: Initialize search
            logger.debug("Step 1/4: Initializing search session")
            self._do_search()
            logger.debug("Step 1/4: Search session initialized")

            # Step 2: Get DWR token
            logger.debug("Step 2/4: Requesting DWR token")
            self._do_get_dwr_token()
            logger.debug(f"Step 2/4: DWR token obtained: {self.dwr_token[:20]}...")

            # Step 3: Update session
            logger.debug("Step 3/4: Updating session objects")
            self._do_update_session()
            logger.debug("Step 3/4: Session updated")

            # Step 4: Get train list
            logger.debug("Step 4/4: Fetching train list")
            trains_data = self._do_get_train_list()
            logger.debug(f"Step 4/4: Received {len(trains_data) if trains_data else 0} train records")

            # Step 5: Parse and return
            trains = self._parse_trains(trains_data)

            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.info(
                f"Scrape completed: {len(trains)} trains found",
                extra={
                    "trains_found": len(trains),
                    "duration_ms": elapsed_ms,
                    "origin": self.origin.code,
                    "destination": self.destination.code,
                }
            )

            return trains

        except httpx.TimeoutException as e:
            logger.error(f"Request timed out after {time.time() - start_time:.2f}s", exc_info=True)
            raise RenfeNetworkError(f"Request timed out: {e}") from e
        except httpx.HTTPError as e:
            logger.error(f"HTTP error occurred: {e}", exc_info=True)
            raise RenfeNetworkError(f"HTTP error: {e}") from e
        except RenfeDWRTokenError as e:
            logger.error(f"DWR token error: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error during scrape: {e}", exc_info=True)
            raise
        finally:
            self.client.close()

    def _do_search(self) -> None:
        """Initialize the search session."""
        # Create search cookie
        search_cookie = {
            "origen": {"code": self.origin.code, "name": self.origin.name},
            "destino": {"code": self.destination.code, "name": self.destination.name},
            "pasajerosAdultos": 1,
            "pasajerosNinos": 0,
            "pasajerosSpChild": 0,
        }

        self.client.cookies.set(
            "Search",
            str(search_cookie),
            domain=".renfe.com",
            path="/"
        )

        # Create search payload
        date_format = "%d/%m/%Y"
        return_date_str = "" if self.return_date is None else self.return_date.strftime(date_format)

        payload = {
            "tipoBusqueda": "autocomplete",
            "currenLocation": "menuBusqueda",
            "vengoderenfecom": "SI",
            "desOrigen": self.origin.name,
            "desDestino": self.destination.name,
            "cdgoOrigen": self.origin.code,
            "cdgoDestino": self.destination.code,
            "idiomaBusqueda": "ES",
            "FechaIdaSel": self.departure_date.strftime(date_format),
            "FechaVueltaSel": return_date_str,
            "_fechaIdaVisual": self.departure_date.strftime(date_format),
            "_fechaVueltaVisual": return_date_str,
            "adultos_": "1",
            "ninos_": "0",
            "ninosMenores": "0",
            "codPromocional": "",
            "plazaH": "false",
            "sinEnlace": "false",
            "asistencia": "false",
            "franjaHoraI": "",
            "franjaHoraV": "",
            "Idioma": "es",
            "Pais": "ES",
        }

        response = self.client.post(self.SEARCH_URL, data=payload)
        response.raise_for_status()

    def _do_get_dwr_token(self) -> None:
        """Generate and extract DWR token."""
        # First call (priming)
        payload1 = dwr.build_generate_id_payload(next(self.batch_id), None)
        self.client.post(self.SYSTEM_ID_URL, content=payload1)

        # Second call (get token)
        payload2 = dwr.build_generate_id_payload(next(self.batch_id), self.search_id)
        response = self.client.post(self.SYSTEM_ID_URL, content=payload2)
        response.raise_for_status()

        # Extract token
        self.dwr_token = self._extract_dwr_token(response.text)

        # Set DWR session cookie
        self.client.cookies.set(
            "DWRSESSIONID",
            self.dwr_token,
            path="/vol",
            domain="venta.renfe.com"
        )

        # Create script session ID
        self.script_session_id = dwr.create_session_script_id(self.dwr_token)

    def _do_update_session(self) -> None:
        """Update DWR session objects."""
        payload = dwr.build_update_session_payload(
            next(self.batch_id),
            self.search_id,
            self.script_session_id
        )

        response = self.client.post(self.UPDATE_SESSION_URL, content=payload)
        response.raise_for_status()

    def _do_get_train_list(self) -> dict:
        """Fetch the train list from DWR API."""
        date_format = "%d/%m/%Y"
        departure_date_str = self.departure_date.strftime(date_format)
        return_date_str = None if self.return_date is None else self.return_date.strftime(date_format)

        payload = dwr.build_train_list_payload(
            next(self.batch_id),
            self.search_id,
            self.script_session_id,
            departure_date_str,
            return_date_str
        )

        response = self.client.post(self.TRAIN_LIST_URL, content=payload)
        response.raise_for_status()

        return self._extract_train_list(response.text)

    def _extract_dwr_token(self, response_text: str) -> str:
        """Extract DWR token from response."""
        pattern = r'r\.handleCallback\("[^"]+","[^"]+","([^"]+)"\)'
        match = re.search(pattern, response_text)

        if not match:
            logger.warning(f"Failed to extract DWR token. Response length: {len(response_text)} chars")
            raise RenfeDWRTokenError("Failed to extract DWR token from response")

        token = match.group(1)
        logger.debug(f"Extracted DWR token successfully (length: {len(token)})")
        return token

    def _extract_train_list(self, response_text: str) -> dict:
        """Extract train list JSON from DWR response."""
        match = re.search(r"r\.handleCallback\([^,]+,\s*[^,]+,\s*(\{.*\})\);", response_text, re.DOTALL)

        if not match:
            logger.warning(f"Failed to extract train list. Response length: {len(response_text)} chars")
            raise RenfeParseError("Failed to extract train list from response")

        try:
            data = json5.loads(match.group(1))
            logger.debug(f"Parsed train list JSON successfully")
            return data
        except Exception as e:
            logger.error(f"JSON parsing error: {e}", exc_info=True)
            raise RenfeParseError(f"Failed to parse train list JSON: {e}") from e

    def _parse_trains(self, data: dict) -> List[TrainRide]:
        """Parse train data into TrainRide objects."""
        trains = []

        for idx, direction in enumerate(data.get("listadoTrenes", [])):
            # Determine origin/destination based on direction
            if idx == 0:
                origin_name = self.origin.name
                dest_name = self.destination.name
                date_ref = self.departure_date
            else:
                origin_name = self.destination.name
                dest_name = self.origin.name
                date_ref = self.return_date

            for train_data in direction.get("listviajeViewEnlaceBean", []):
                try:
                    # Parse price
                    price_str = train_data.get("tarifaMinima", "0")
                    if price_str:
                        price = float(price_str.replace(",", "."))
                    else:
                        price = 0.0

                    # Parse times
                    dep_time = self._parse_time(train_data["horaSalida"], date_ref)
                    arr_time = self._parse_time(train_data["horaLlegada"], date_ref)

                    # Check availability
                    available = self._is_available(train_data)

                    train = TrainRide(
                        train_type=train_data.get("tipoTrenUno", "N/A"),
                        origin=origin_name,
                        destination=dest_name,
                        departure_time=dep_time,
                        arrival_time=arr_time,
                        duration_minutes=train_data.get("duracionViajeTotalEnMinutos", 0),
                        price=price,
                        available=available
                    )

                    trains.append(train)

                except Exception as e:
                    # Skip invalid trains but continue parsing
                    continue

        return trains

    @staticmethod
    def _parse_time(time_str: str, date: datetime) -> datetime:
        """Parse time string and combine with date."""
        hours, minutes = map(int, time_str.split(":"))
        return date.replace(hour=hours, minute=minutes, second=0, microsecond=0)

    @staticmethod
    def _is_available(train_data: dict) -> bool:
        """Check if train is available for booking."""
        return (
            not train_data.get("completo", True) and
            train_data.get("razonNoDisponible", "") in ["", "8"] and
            train_data.get("tarifaMinima") is not None and
            not train_data.get("soloPlazaH", True)
        )


def load_stations() -> dict:
    """
    Load station data from JSON file.

    DEPRECATED: This function is kept for backward compatibility.
    New code should use station_service.get_station_service() instead.
    """
    stations_file = Path(__file__).parent / "stations.json"
    with open(stations_file, "r", encoding="utf-8") as f:
        return json.load(f)


def find_station(name: str) -> Optional[Station]:
    """
    Find a station by name (case-insensitive).

    Now uses the unified StationService for consistent lookups across
    schedule search and price checking.

    Args:
        name: Station or city name to search for

    Returns:
        Station object if found, None otherwise
    """
    try:
        # Try to use unified station service
        from station_service import get_station_service

        station_service = get_station_service()
        unified_station = station_service.find_station(name)

        if unified_station and unified_station.has_renfe_data():
            return unified_station.to_renfe_format()

        # If no match in unified service or missing Renfe data, return None
        return None

    except Exception:
        # Fallback to legacy implementation if station_service unavailable
        stations = load_stations()
        name_upper = name.upper()

        # Try exact match first
        for station_name, data in stations.items():
            if station_name.upper() == name_upper:
                return Station(name=station_name, code=data["cdgoEstacion"])

        # Try partial match
        for station_name, data in stations.items():
            if name_upper in station_name.upper():
                return Station(name=station_name, code=data["cdgoEstacion"])

        return None
