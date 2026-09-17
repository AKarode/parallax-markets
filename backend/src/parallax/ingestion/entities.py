"""Named-entity override list for GDELT noise filtering.

Events mentioning these entities bypass volume-gate thresholds because
they are directly relevant to the Iran/Hormuz scenario regardless of
global media attention.
"""

import re

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

# Sort longest-first so multi-word patterns are preferred by the alternation
# (e.g., "strait of hormuz" before "hormuz"). Word boundaries (\b) sit at
# word/non-word transitions, so hyphenated entities like "al-quds" still match.
_ENTITY_REGEX = re.compile(
    r"\b(?:" + "|".join(re.escape(e) for e in sorted(_ENTITY_LOWER, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def matches_critical_entity(text: str) -> bool:
    """Return True if *text* contains any critical entity (case-insensitive).

    Uses word-boundary matching so "oil" does not match inside "boil" and
    "iran" does not match inside "iranian".
    """
    return _ENTITY_REGEX.search(text) is not None
