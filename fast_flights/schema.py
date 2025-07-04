from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional


@dataclass
class Result:
    current_price: Literal["low", "typical", "high"]
    flights: List[Flight]
    has_error: bool


@dataclass
class Flight:
    is_best: bool
    name: str
    flight_number: str
    aircraft_model: str
    departure: str
    arrival: str
    arrival_time_ahead: str
    duration: str
    stops: int
    delay: Optional[str]
    price: str
    logo: dict
