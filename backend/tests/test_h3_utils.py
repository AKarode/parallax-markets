import h3
from parallax.spatial.h3_utils import (
    ResolutionBand,
    RESOLUTION_BANDS,
    lat_lng_to_cell_for_zone,
    route_to_h3_chain,
)


def test_resolution_bands_defined():
    assert len(RESOLUTION_BANDS) == 4
    assert RESOLUTION_BANDS[0].name == "ocean"
    assert RESOLUTION_BANDS[0].resolution in (3, 4)
    assert RESOLUTION_BANDS[3].name == "infrastructure"
    assert RESOLUTION_BANDS[3].resolution == 9


def test_lat_lng_to_cell_hormuz():
    """Hormuz strait center should map to the chokepoint band (res 7-8)."""
    cell = lat_lng_to_cell_for_zone(26.5, 56.25, "chokepoint")
    assert h3.get_resolution(cell) in (7, 8)


def test_route_to_h3_chain():
    """A simple 2-point line should produce a list of H3 cells."""
    coords = [(56.0, 26.0), (56.5, 26.5)]  # (lng, lat) pairs
    chain = route_to_h3_chain(coords, resolution=7)
    assert len(chain) > 0
    assert all(h3.is_valid_cell(c) for c in chain)


def test_route_to_h3_chain_deduplicates():
    """Two very close points should not produce duplicate cells."""
    coords = [(56.0, 26.0), (56.0001, 26.0001)]
    chain = route_to_h3_chain(coords, resolution=4)
    assert len(chain) == len(set(chain))
