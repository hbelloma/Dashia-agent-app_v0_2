"""
positions.py
=============
Antes de esto, `position` era un parámetro que había que pasar a mano
en cada llamada a run_agent_tick() — exactamente el tipo de "pieza
suelta que conectás vos" que se supone que el orquestador tiene que
dejar de requerir. Esto lo lleva de forma persistente (SQLite, mismo
patrón liviano que credentials_vault.store), por (agent_id, symbol).
"""

from __future__ import annotations
import sqlite3
from datetime import datetime, timezone

_SCHEMA = """
CREATE TABLE IF NOT EXISTS positions (
    agent_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    position TEXT NOT NULL DEFAULT 'none',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (agent_id, symbol)
);
"""

VALID_POSITIONS = {"none", "long", "short"}

# Cómo cambia la posición según la acción que el gateway realmente ejecutó
# (ver ExecutionOutcome.gateway_action en agent_sandbox/gateway_bridge.py)
_TRANSITIONS = {
    "open_long": "long", "open_short": "short",
    "close_long": "none", "close_short": "none",
}


class PositionStore:
    def __init__(self, db_path: str = "positions.db"):
        # check_same_thread=False: ver la misma nota en credentials_vault/store.py
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(_SCHEMA)
        self._conn.commit()

    def get_position(self, agent_id: str, symbol: str) -> str:
        row = self._conn.execute(
            "SELECT position FROM positions WHERE agent_id=? AND symbol=?", (agent_id, symbol)
        ).fetchone()
        return row[0] if row else "none"

    def set_position(self, agent_id: str, symbol: str, position: str) -> None:
        if position not in VALID_POSITIONS:
            raise ValueError(f"Posición inválida: {position!r} (debe ser {VALID_POSITIONS})")
        self._conn.execute(
            """INSERT INTO positions (agent_id, symbol, position, updated_at) VALUES (?, ?, ?, ?)
               ON CONFLICT(agent_id, symbol) DO UPDATE SET
                   position=excluded.position, updated_at=excluded.updated_at""",
            (agent_id, symbol, position, datetime.now(timezone.utc).isoformat()),
        )
        self._conn.commit()

    def apply_gateway_action(self, agent_id: str, symbol: str, gateway_action: str | None) -> None:
        """Traduce lo que el gateway ejecutó de verdad (ver ExecutionOutcome.gateway_action)
        al nuevo estado de posición, y lo guarda. No hace nada si gateway_action es None
        (el agente no ejecutó ninguna orden esta vez)."""
        new_position = _TRANSITIONS.get(gateway_action)
        if new_position is not None:
            self.set_position(agent_id, symbol, new_position)

    def close(self):
        self._conn.close()
