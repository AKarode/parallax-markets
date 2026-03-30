from pydantic import BaseModel, field_validator


class SubActorRecommendation(BaseModel):
    agent_id: str
    action_type: str
    description: str
    reasoning: str
    intensity: float
    confidence: float
    significance: float  # 0-1, used to decide if country agent fires

    @field_validator("confidence", "significance", "intensity")
    @classmethod
    def clamp_zero_one(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Must be between 0 and 1, got {v}")
        return v


class AgentDecision(BaseModel):
    agent_id: str
    tick: int
    action_type: str
    target_h3_cells: list[int]
    intensity: float
    description: str
    reasoning: str
    confidence: float
    prompt_version: str

    @field_validator("confidence", "intensity")
    @classmethod
    def clamp_zero_one(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Must be between 0 and 1, got {v}")
        return v


class CountryDecision(BaseModel):
    """Synthesized decision from a country agent after resolving sub-actor conflicts."""
    country: str
    tick: int
    action_type: str
    target_h3_cells: list[int]
    intensity: float
    description: str
    reasoning: str
    confidence: float
    prompt_version: str
    contributing_agents: list[str]  # sub-actor IDs that contributed

    @field_validator("confidence", "intensity")
    @classmethod
    def clamp_zero_one(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Must be between 0 and 1, got {v}")
        return v


class AgentPrediction(BaseModel):
    """A structured prediction that can be scored against ground truth."""
    agent_id: str
    prediction_type: str
    direction: str  # "increase", "decrease", "stable"
    magnitude_range: list[float]  # [low, high]
    unit: str
    timeframe: str  # e.g. "7d", "24h"
    confidence: float
    reasoning: str
    prompt_version: str

    @field_validator("confidence")
    @classmethod
    def clamp_zero_one(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Must be between 0 and 1, got {v}")
        return v

    @field_validator("direction")
    @classmethod
    def valid_direction(cls, v: str) -> str:
        if v not in ("increase", "decrease", "stable"):
            raise ValueError(f"Direction must be increase/decrease/stable, got {v}")
        return v
