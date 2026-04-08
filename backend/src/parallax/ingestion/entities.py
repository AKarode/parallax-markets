"""Named-entity override list for GDELT noise filtering.

Events mentioning these entities bypass volume-gate thresholds because
they are directly relevant to the Iran/Hormuz scenario regardless of
global media attention.
"""

CRITICAL_ENTITIES: list[str] = [
    # Actors
    "IRGC", "IRGC Navy", "CENTCOM", "Aramco", "ADNOC",
    "Khamenei", "Rouhani", "Trump", "MBS", "Mohammad bin Salman",
    "PLA Navy", "CNOOC", "Sinopec",
    # Locations
    "Hormuz", "Strait of Hormuz", "Bandar Abbas", "Fujairah",
    "Ras Tanura", "Yanbu", "Gulf of Oman", "Persian Gulf",
    # Keywords
    "tanker seizure", "naval blockade", "shipping lane",
    "oil sanctions", "strait closure", "mine laying", "naval exercise",
    "carrier group", "maritime security", "oil embargo",
]

_ENTITY_LOWER = [e.lower() for e in CRITICAL_ENTITIES]


def matches_critical_entity(text: str) -> bool:
    """Return True if *text* contains any critical entity (case-insensitive)."""
    text_lower = text.lower()
    return any(entity in text_lower for entity in _ENTITY_LOWER)
