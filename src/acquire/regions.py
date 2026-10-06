"""Bounding boxes for planned demonstration areas."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Region:
    """Geographic bounding box in west, south, east, north order (decimal degrees)."""

    name: str
    west: float
    south: float
    east: float
    north: float

    def as_firms_area(self) -> str:
        return f"{self.west},{self.south},{self.east},{self.north}"


# Approximate national extent for the Bangladesh demonstration area.
BANGLADESH_BBOX = Region(
    name="bangladesh",
    west=88.0,
    south=20.5,
    east=92.7,
    north=26.7,
)
