from parallax.agents.registry import AgentInfo, AgentRegistry

# Map keywords/actor names to countries
_ACTOR_COUNTRY_MAP: dict[str, str] = {
    "iran": "iran", "irgc": "iran", "khamenei": "iran", "tehran": "iran",
    "usa": "usa", "united states": "usa", "trump": "usa", "centcom": "usa",
    "pentagon": "usa", "white house": "usa",
    "saudi": "saudi_arabia", "aramco": "saudi_arabia", "mbs": "saudi_arabia",
    "riyadh": "saudi_arabia",
    "china": "china", "beijing": "china", "pla": "china", "cnooc": "china",
    "sinopec": "china", "xi": "china",
    "russia": "russia", "moscow": "russia", "putin": "russia", "rosneft": "russia",
    "russia": "russia",
    "uae": "uae", "emirates": "uae", "adnoc": "uae", "fujairah": "uae",
    "abu dhabi": "uae",
    "india": "india", "delhi": "india", "indian oil": "india",
    "japan": "japan", "tokyo": "japan", "jera": "japan",
    "south korea": "south_korea", "seoul": "south_korea", "sk energy": "south_korea",
    "eu": "eu", "european": "eu", "brussels": "eu",
    "israel": "israel", "idf": "israel", "mossad": "israel", "tel aviv": "israel",
    "iraq": "iraq", "baghdad": "iraq",
    "opec": "saudi_arabia",  # Route OPEC events to Saudi as primary
}


class AgentRouter:
    def __init__(self, registry: AgentRegistry) -> None:
        self._registry = registry

    def route(self, event: dict, relevance_threshold: float = 0.5) -> list[AgentInfo]:
        if event.get("relevance_score", 0) < relevance_threshold:
            return []

        # Find mentioned countries
        searchable = " ".join(
            str(event.get(k, "")) for k in ("actor1", "actor2", "summary")
        ).lower()

        matched_countries: set[str] = set()
        for keyword, country in _ACTOR_COUNTRY_MAP.items():
            if keyword in searchable:
                matched_countries.add(country)

        # Return sub-actors (not country agents) for matched countries
        agents: list[AgentInfo] = []
        for country in matched_countries:
            agents.extend(self._registry.sub_actors(country))

        return agents
