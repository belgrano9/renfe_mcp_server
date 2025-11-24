"""Data models for the Renfe scraper."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class Station(BaseModel):
    """Represents a Renfe train station."""

    model_config = ConfigDict(frozen=True)  # Make immutable

    name: str = Field(description="Station name")
    code: str = Field(description="Renfe station code")


class TrainRide(BaseModel):
    """Represents a train ride with pricing and schedule information."""

    train_type: str = Field(description="Train type (e.g., AVE, ALVIA)")
    origin: str = Field(description="Origin station name")
    destination: str = Field(description="Destination station name")
    departure_time: datetime = Field(description="Departure date and time")
    arrival_time: datetime = Field(description="Arrival date and time")
    duration_minutes: int = Field(description="Journey duration in minutes")
    price: float = Field(description="Ticket price in euros")
    available: bool = Field(description="Whether tickets are available")

    def to_dict(self) -> dict:
        """Convert to dictionary format compatible with existing code."""
        return {
            "train_type": self.train_type,
            "origin": self.origin,
            "destination": self.destination,
            "departure_time": self.departure_time.strftime("%H:%M"),
            "arrival_time": self.arrival_time.strftime("%H:%M"),
            "duration_minutes": self.duration_minutes,
            "price": self.price,
            "available": self.available,
        }
