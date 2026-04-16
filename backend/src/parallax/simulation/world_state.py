import copy
from dataclasses import dataclass


@dataclass
class CellState:
    cell_id: int
    influence: str | None = None
    threat_level: float = 0.0
    flow: float = 0.0
    status: str = "open"


class WorldState:
    """In-memory world state with delta tracking for efficient persistence."""

    def __init__(self) -> None:
        self._cells: dict[int, CellState] = {}
        self._dirty: set[int] = set()
        self._tick: int = 0

    @property
    def tick(self) -> int:
        return self._tick

    def copy(self) -> "WorldState":
        """Deep copy for safe mutation in cascade operations."""
        return copy.deepcopy(self)

    def get_cell(self, cell_id: int) -> dict | None:
        cell = self._cells.get(cell_id)
        if cell is None:
            return None
        return {
            "cell_id": cell.cell_id,
            "influence": cell.influence,
            "threat_level": cell.threat_level,
            "flow": cell.flow,
            "status": cell.status,
        }

    def update_cell(
        self,
        cell_id: int,
        influence: str | None = None,
        threat_level: float | None = None,
        flow: float | None = None,
        status: str | None = None,
    ) -> None:
        if cell_id not in self._cells:
            self._cells[cell_id] = CellState(cell_id=cell_id)
        cell = self._cells[cell_id]
        if influence is not None:
            cell.influence = influence
        if threat_level is not None:
            cell.threat_level = threat_level
        if flow is not None:
            cell.flow = flow
        if status is not None:
            cell.status = status
        self._dirty.add(cell_id)

    def advance_tick(self) -> None:
        self._tick += 1

    def flush_deltas(self) -> list[dict]:
        deltas = []
        for cell_id in self._dirty:
            cell = self._cells[cell_id]
            deltas.append({
                "cell_id": cell.cell_id,
                "tick": self._tick,
                "influence": cell.influence,
                "threat_level": cell.threat_level,
                "flow": cell.flow,
                "status": cell.status,
            })
        self._dirty.clear()
        return deltas

    def snapshot(self) -> list[dict]:
        return [
            {
                "cell_id": c.cell_id,
                "influence": c.influence,
                "threat_level": c.threat_level,
                "flow": c.flow,
                "status": c.status,
            }
            for c in self._cells.values()
        ]

    def load_snapshot(self, data: list[dict], tick: int) -> None:
        self._cells.clear()
        self._dirty.clear()
        self._tick = tick
        for row in data:
            self._cells[row["cell_id"]] = CellState(
                cell_id=row["cell_id"],
                influence=row.get("influence"),
                threat_level=row.get("threat_level", 0.0),
                flow=row.get("flow", 0.0),
                status=row.get("status", "open"),
            )
