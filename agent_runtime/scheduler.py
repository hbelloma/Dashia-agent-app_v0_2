"""
scheduler.py
=============
Llama a run_agent_tick_for_user() cada N minutos, para cada agente
activo de cada usuario — la pieza que faltaba para que "correr un tick"
pase de ser algo que alguien dispara a mano a algo que corre solo.

Diseño deliberado en dos niveles, para que la parte que importa se
pueda probar sin esperar tiempo real:

  - agents_due_to_run(): función pura, sin I/O — dada una lista de
    agentes y una hora, dice cuáles ya deberían correr. Se prueba con
    fechas fabricadas, sin ningún sleep().
  - run_scheduler_pass(): UNA pasada completa (encuentra a quién le
    toca, corre cada uno, aísla errores). Tampoco duerme — se puede
    correr y probar de punta a punta las veces que haga falta.
  - run_scheduler_loop(): el while True real, que sí duerme entre
    pasadas. Es deliberadamente el archivo más chico y menos probado
    de los tres — es solo "llamar a run_scheduler_pass y dormir",
    envuelto alrededor de la lógica que sí importa verificar.

Corre los agentes SECUENCIALMENTE, uno por uno. Para producción con
muchos agentes activos a la vez, conviene un pool de threads/procesos —
pero eso trae temas de concurrencia con SQLite (AgentRegistry,
PositionStore, CredentialsVault usan conexiones no pensadas para
compartirse entre threads) que quedan fuera de este alcance. Ver README.
"""

from __future__ import annotations
import logging
import time
import threading
from datetime import datetime, timezone, timedelta

from .registry import AgentRegistry, AgentConfig
from .positions import PositionStore
from .runner import run_agent_tick_for_user
from agent_sandbox.process_isolation import IsolationLimits

log = logging.getLogger("agent_runtime.scheduler")


def agents_due_to_run(agents: list[AgentConfig], now: datetime) -> list[AgentConfig]:
    """Pura, sin I/O. Un agente le toca correr si nunca corrió, o si ya
    pasaron al menos `interval_minutes` desde su última corrida."""
    due = []
    for a in agents:
        if not a.active:
            continue
        if a.last_run_at is None:
            due.append(a)
            continue
        elapsed = now - a.last_run_at
        if elapsed >= timedelta(minutes=a.interval_minutes):
            due.append(a)
    return due


class MarketDataCache:
    """Evita reconstruir los proveedores de market_data (uno por exchange
    conectado) en cada tick de cada agente — varios agentes del mismo
    usuario reutilizan el mismo UnifiedMarketData mientras no venza el TTL."""
    def __init__(self, vault, ttl_minutes: float = 30):
        self.vault = vault
        self.ttl = timedelta(minutes=ttl_minutes)
        self._cache: dict[str, tuple] = {}  # user_id -> (market_data, built_at)

    def get(self, user_id: str):
        cached = self._cache.get(user_id)
        now = datetime.now(timezone.utc)
        if cached and (now - cached[1]) < self.ttl:
            return cached[0]
        from market_data.vault_bridge import build_market_data_for_user
        market_data = build_market_data_for_user(self.vault, user_id)
        self._cache[user_id] = (market_data, now)
        return market_data

    def invalidate(self, user_id: str):
        self._cache.pop(user_id, None)


def run_due_agent(agent: AgentConfig, vault, registry: AgentRegistry,
                   market_data_cache: MarketDataCache, positions: PositionStore,
                   limits: IsolationLimits | None = None):
    """
    Corre un tick de un agente. Un agente que falla (mercado sin datos,
    gateway no verificado, error inesperado) NUNCA debe tumbar el resto
    de la pasada — se loguea y se sigue con el próximo. `last_run_at` se
    actualiza siempre, incluso si falló, para que un agente roto no
    quede reintentando en cada pasada sin ningún respiro.
    """
    try:
        market_data = market_data_cache.get(agent.user_id)
        outcome = run_agent_tick_for_user(
            user_id=agent.user_id, agent_id=agent.agent_id, source=agent.source,
            symbol=agent.symbol, exchange=agent.exchange, vault=vault,
            equity_usd=agent.equity_usd, market_data=market_data, positions=positions,
            limits=limits,
        )
        log.info("Agente %s (%s): ejecutado=%s razón=%s", agent.agent_id, agent.name,
                  outcome.executed, outcome.reason)
        return outcome
    except Exception as e:
        log.error("Agente %s (%s) falló esta pasada: %s", agent.agent_id, agent.name, e)
        return None
    finally:
        registry.mark_run(agent.agent_id, datetime.now(timezone.utc))


def run_scheduler_pass(registry: AgentRegistry, vault, positions: PositionStore,
                        market_data_cache: MarketDataCache, now: datetime | None = None,
                        limits: IsolationLimits | None = None) -> dict:
    """UNA pasada: encuentra a quién le toca correr y los corre a todos.
    Sin sleep, sin loop — completamente testeable."""
    now = now or datetime.now(timezone.utc)
    due = agents_due_to_run(registry.list_active_agents(), now)
    results = {}
    for agent in due:
        results[agent.agent_id] = run_due_agent(agent, vault, registry, market_data_cache, positions, limits)
    return results


def run_scheduler_loop(registry: AgentRegistry, vault, positions: PositionStore,
                        poll_interval_s: float = 30.0, stop_event: threading.Event | None = None,
                        limits: IsolationLimits | None = None) -> None:
    """
    El loop real. Se fija cada `poll_interval_s` segundos si algún
    agente ya cumplió su intervalo — el intervalo de cada agente
    (interval_minutes) es independiente de este poll_interval_s, que
    solo controla cada cuánto se REVISA la lista, no cada cuánto corre
    cada agente.
    """
    market_data_cache = MarketDataCache(vault)
    stop_event = stop_event or threading.Event()
    log.info("Scheduler iniciado (poll cada %ss)", poll_interval_s)
    while not stop_event.is_set():
        try:
            run_scheduler_pass(registry, vault, positions, market_data_cache, limits=limits)
        except Exception as e:
            log.error("Error inesperado en la pasada del scheduler: %s", e)
        stop_event.wait(poll_interval_s)
    log.info("Scheduler detenido")
