"""Custom exceptions for the Renfe scraper."""


class RenfeScraperException(Exception):
    """Base exception for all Renfe scraper errors."""
    pass


class RenfeNetworkError(RenfeScraperException):
    """Raised when network/HTTP errors occur."""
    pass


class RenfeDWRTokenError(RenfeScraperException):
    """Raised when DWR token generation or extraction fails."""
    pass


class RenfeStationNotFoundError(RenfeScraperException):
    """Raised when a station cannot be found."""
    pass


class RenfeNoTrainsFoundError(RenfeScraperException):
    """Raised when no trains are found (may be expected in some cases)."""
    pass


class RenfeParseError(RenfeScraperException):
    """Raised when response parsing fails."""
    pass
