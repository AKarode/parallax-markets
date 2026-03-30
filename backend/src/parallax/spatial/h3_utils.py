from dataclasses import dataclass

import h3


@dataclass(frozen=True)
class ResolutionBand:
    name: str
    resolution: int
    description: str


RESOLUTION_BANDS = [
    ResolutionBand("ocean", 4, "Open ocean / distant routes"),
    ResolutionBand("regional", 6, "Persian Gulf, Gulf of Oman"),
    ResolutionBand("chokepoint", 7, "Hormuz strait + chokepoints"),
    ResolutionBand("infrastructure", 9, "Ports and terminals"),
]

_BAND_MAP = {b.name: b for b in RESOLUTION_BANDS}


def lat_lng_to_cell_for_zone(lat: float, lng: float, zone: str) -> int:
    band = _BAND_MAP[zone]
    return h3.latlng_to_cell(lat, lng, band.resolution)


def route_to_h3_chain(
    coords: list[tuple[float, float]], resolution: int
) -> list[int]:
    """Convert a list of (lng, lat) coordinate pairs to an ordered, deduplicated H3 cell chain."""
    cells: list[int] = []
    seen: set[int] = set()
    for lng, lat in coords:
        cell = h3.latlng_to_cell(lat, lng, resolution)
        if cell not in seen:
            cells.append(cell)
            seen.add(cell)
    return cells
