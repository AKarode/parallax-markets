from dataclasses import dataclass


@dataclass(frozen=True)
class AgentInfo:
    agent_id: str
    country: str
    name: str
    role: str
    weight: float  # Influence weight within the country
    is_country_agent: bool = False


# Hardcoded Phase 1 roster -- Iran/Hormuz focused
_AGENTS: list[AgentInfo] = [
    # Iran
    AgentInfo("iran", "iran", "Iran", "Country Agent", 1.0, is_country_agent=True),
    AgentInfo("iran/supreme_leader", "iran", "Supreme Leader Khamenei", "Head of state, ultimate authority", 0.9),
    AgentInfo("iran/irgc", "iran", "IRGC", "Revolutionary Guard Corps", 0.8),
    AgentInfo("iran/irgc_navy", "iran", "IRGC Navy", "Naval warfare, Hormuz operations", 0.7),
    AgentInfo("iran/foreign_ministry", "iran", "Foreign Ministry", "Diplomacy, negotiations", 0.3),
    AgentInfo("iran/oil_ministry", "iran", "Oil Ministry", "Oil production, OPEC coordination", 0.4),
    # USA
    AgentInfo("usa", "usa", "USA", "Country Agent", 1.0, is_country_agent=True),
    AgentInfo("usa/trump", "usa", "Trump / White House", "President, executive decisions", 0.9),
    AgentInfo("usa/congress", "usa", "Congress", "Legislation, sanctions authorization", 0.4),
    AgentInfo("usa/centcom", "usa", "Pentagon / CENTCOM", "Military operations, Gulf presence", 0.7),
    AgentInfo("usa/state_dept", "usa", "State Department", "Diplomacy, coalition building", 0.3),
    AgentInfo("usa/treasury", "usa", "Treasury", "Sanctions enforcement", 0.6),
    # Saudi Arabia
    AgentInfo("saudi_arabia", "saudi_arabia", "Saudi Arabia", "Country Agent", 1.0, is_country_agent=True),
    AgentInfo("saudi_arabia/mbs", "saudi_arabia", "MBS / Crown Prince", "De facto ruler", 0.9),
    AgentInfo("saudi_arabia/aramco", "saudi_arabia", "Aramco", "Oil production, spare capacity", 0.7),
    AgentInfo("saudi_arabia/opec", "saudi_arabia", "OPEC Delegation", "Cartel coordination", 0.5),
    # China
    AgentInfo("china", "china", "China", "Country Agent", 1.0, is_country_agent=True),
    AgentInfo("china/xi", "china", "Xi / CCP", "Head of state", 0.9),
    AgentInfo("china/pla_navy", "china", "PLA Navy", "Naval presence, Gulf of Aden", 0.5),
    AgentInfo("china/cnooc_sinopec", "china", "CNOOC / Sinopec", "Energy imports, SPR", 0.6),
    # Russia
    AgentInfo("russia", "russia", "Russia", "Country Agent", 1.0, is_country_agent=True),
    AgentInfo("russia/putin", "russia", "Putin", "Head of state", 0.9),
    AgentInfo("russia/rosneft", "russia", "Rosneft", "Oil production, market share", 0.6),
    AgentInfo("russia/foreign_ministry", "russia", "Foreign Ministry", "Diplomacy, UN veto", 0.4),
    # UAE
    AgentInfo("uae", "uae", "UAE", "Country Agent", 1.0, is_country_agent=True),
    AgentInfo("uae/leadership", "uae", "UAE Leadership", "MBZ, executive", 0.9),
    AgentInfo("uae/adnoc", "uae", "ADNOC", "Oil production, Fujairah bypass", 0.7),
    AgentInfo("uae/fujairah", "uae", "Fujairah Port Authority", "Port ops, bypass terminal", 0.5),
    # India
    AgentInfo("india", "india", "India", "Country Agent", 1.0, is_country_agent=True),
    AgentInfo("india/pmo", "india", "PMO", "Prime Minister's Office", 0.8),
    AgentInfo("india/indian_oil", "india", "Indian Oil Corp", "Refining, imports", 0.6),
    AgentInfo("india/navy", "india", "Indian Navy", "Maritime security", 0.4),
    # Japan
    AgentInfo("japan", "japan", "Japan", "Country Agent", 1.0, is_country_agent=True),
    AgentInfo("japan/pm", "japan", "PM Office", "Executive decisions", 0.8),
    AgentInfo("japan/jera", "japan", "JERA / Refiners", "Energy imports", 0.6),
    # South Korea
    AgentInfo("south_korea", "south_korea", "South Korea", "Country Agent", 1.0, is_country_agent=True),
    AgentInfo("south_korea/blue_house", "south_korea", "Blue House", "Executive", 0.8),
    AgentInfo("south_korea/sk_energy", "south_korea", "SK Energy / Refiners", "Energy imports", 0.6),
    # EU
    AgentInfo("eu", "eu", "EU", "Country Agent", 1.0, is_country_agent=True),
    AgentInfo("eu/commission", "eu", "EU Commission", "Bloc policy", 0.7),
    AgentInfo("eu/energy_policy", "eu", "EU Energy Policy", "Energy security", 0.5),
    # Israel
    AgentInfo("israel", "israel", "Israel", "Country Agent", 1.0, is_country_agent=True),
    AgentInfo("israel/pm", "israel", "PM Office", "Executive", 0.8),
    AgentInfo("israel/idf", "israel", "IDF", "Military operations", 0.7),
    AgentInfo("israel/mossad", "israel", "Mossad", "Intelligence, covert ops", 0.6),
    # Iraq
    AgentInfo("iraq", "iraq", "Iraq", "Country Agent", 1.0, is_country_agent=True),
    AgentInfo("iraq/pm", "iraq", "PM Office", "Executive", 0.7),
    AgentInfo("iraq/oil_ministry", "iraq", "Oil Ministry", "Production, exports", 0.6),
]

_BY_ID = {a.agent_id: a for a in _AGENTS}
_BY_COUNTRY: dict[str, list[AgentInfo]] = {}
for _a in _AGENTS:
    _BY_COUNTRY.setdefault(_a.country, []).append(_a)


class AgentRegistry:
    def list_countries(self) -> list[str]:
        return sorted(set(a.country for a in _AGENTS if a.is_country_agent))

    def sub_actors(self, country: str) -> list[AgentInfo]:
        return [a for a in _BY_COUNTRY.get(country, []) if not a.is_country_agent]

    def get_agent(self, agent_id: str) -> AgentInfo | None:
        return _BY_ID.get(agent_id)

    def country_agent(self, country: str) -> AgentInfo | None:
        for a in _BY_COUNTRY.get(country, []):
            if a.is_country_agent:
                return a
        return None

    def all_agents(self) -> list[AgentInfo]:
        return list(_AGENTS)
