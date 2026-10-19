"""
runner.py
=========
El orquestador que faltaba. Hasta ahora, market_data (velas reales),
agent_sandbox (DSL restringido + aislamiento) y los gateways
(binance_connector/bybit_connector/weex_connector/solana_connector)
funcionaban cada uno correctamente por separado y probados — pero
conectarlos era trabajo manual de quien escribiera el runner de turno.

Hay dos niveles acá:

  - run_agent_tick(): un tick, con market_data/gateway/position ya
    armados por quien llama — el nivel de control fino.
  - run_agent_tick_for_user(): un tick completo "para el usuario X" —
    arma market_data y gateway solos desde la bóveda, y lleva la
    posición sola con PositionStore. Este es el que responde
    literalmente a "correr un tick de un agente para el usuario X sin
    conectar las piezas a mano".
"""

from __future__ import annotations
import logging

from agent_sandbox.gateway_bridge import evaluate_and_execute, ExecutionOutcome
from agent_sandbox.process_isolation import IsolationLimits
from .trend import derive_trend
from .gateway_factory import build_gateway_for_user

log = logging.getLogger("agent_runtime")


def run_agent_tick(agent_id: str, source: str, symbol: str, market_data, gateway,
                    equity_usd: float, position: str = "none", venue: str | None = None,
                    timeframe: str = "1h", limit: int = 300,
                    limits: IsolationLimits | None = None) -> ExecutionOutcome:
    """
    Un "tick" completo de un agente, con las piezas YA armadas por quien
    llama (ver run_agent_tick_for_user() más abajo si no las tenés
    armadas todavía):
      1. Trae velas reales de market_data.
      2. Deriva el contexto (`trend`) que el DSL puede consultar.
      3. Corre el código del agente en el sandbox aislado.
      4. Si decide comprar/vender, lo manda al gateway real.
    """
    try:
        df = market_data.get_ohlcv(symbol, timeframe=timeframe, limit=limit, venue=venue)
    except Exception as e:
        log.warning("Agente %s: no se pudieron obtener velas para %s: %s", agent_id, symbol, e)
        return ExecutionOutcome(executed=False, reason=f"sin datos de mercado: {e}")

    variables = {"trend": derive_trend(df), "position": position}
    log.info("Agente %s tick %s: trend=%s position=%s velas=%d",
              agent_id, symbol, variables["trend"], position, len(df))

    return evaluate_and_execute(
        agent_id=agent_id, source=source, symbol=symbol, ohlcv=df,
        variables=variables, equity_usd=equity_usd, gateway=gateway, limits=limits,
    )


def run_agent_tick_for_user(user_id: str, agent_id: str, source: str, symbol: str,
                             exchange: str, vault, equity_usd: float,
                             market_data=None, positions=None,
                             market_type: str = "spot", venue: str | None = None,
                             timeframe: str = "1h", limit: int = 300,
                             gateway_limits=None, risk_cfg=None,
                             limits: IsolationLimits | None = None) -> ExecutionOutcome:
    """
    La versión de un solo llamado: "correr un tick del agente `agent_id`
    para el usuario `user_id`, operando en `exchange`" — sin tener que
    armar market_data, el gateway, ni llevar la posición a mano.

    market_data: si no se pasa, se arma con
    market_data.vault_bridge.build_market_data_for_user(vault, user_id) —
    pasarlo ya armado si se va a llamar esto muchas veces seguidas (evita
    reconstruir los proveedores en cada tick).
    positions: PositionStore opcional. Sin esto, cada tick asume
    position="none" (sin memoria entre ticks) — pasar uno persistente
    para que el agente sepa si ya tiene una posición abierta.
    """
    if market_data is None:
        from market_data.vault_bridge import build_market_data_for_user
        market_data = build_market_data_for_user(vault, user_id)

    gateway = build_gateway_for_user(vault, user_id, exchange, market_type=market_type,
                                      limits=gateway_limits, risk_cfg=risk_cfg)

    position = positions.get_position(agent_id, symbol) if positions else "none"

    outcome = run_agent_tick(
        agent_id=agent_id, source=source, symbol=symbol, market_data=market_data,
        gateway=gateway, equity_usd=equity_usd, position=position, venue=venue or exchange,
        timeframe=timeframe, limit=limit, limits=limits,
    )

    if positions and outcome.executed:
        positions.apply_gateway_action(agent_id, symbol, outcome.gateway_action)

    return outcome
