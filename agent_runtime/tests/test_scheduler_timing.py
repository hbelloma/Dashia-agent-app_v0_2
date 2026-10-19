"""test_scheduler_timing.py — la lógica pura, sin ningún sleep real."""
import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agent_runtime.scheduler import agents_due_to_run
from agent_runtime.registry import AgentConfig

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def _agent(agent_id, interval_minutes=60, last_run_at=None, active=True):
    return AgentConfig(agent_id=agent_id, user_id="u1", name=agent_id, source="hold()",
                        symbol="BTC/USDT", exchange="binance", equity_usd=1000.0,
                        interval_minutes=interval_minutes, active=active,
                        last_run_at=last_run_at, created_at=NOW)


def test_agent_that_never_ran_is_always_due():
    a = _agent("a1", last_run_at=None)
    assert agents_due_to_run([a], NOW) == [a]


def test_agent_run_recently_is_not_due():
    a = _agent("a1", interval_minutes=60, last_run_at=NOW - timedelta(minutes=10))
    assert agents_due_to_run([a], NOW) == []


def test_agent_run_exactly_at_interval_is_due():
    a = _agent("a1", interval_minutes=60, last_run_at=NOW - timedelta(minutes=60))
    assert agents_due_to_run([a], NOW) == [a]


def test_agent_run_past_interval_is_due():
    a = _agent("a1", interval_minutes=60, last_run_at=NOW - timedelta(minutes=90))
    assert agents_due_to_run([a], NOW) == [a]


def test_inactive_agent_is_never_due_regardless_of_timing():
    a = _agent("a1", active=False, last_run_at=None)
    assert agents_due_to_run([a], NOW) == []


def test_different_agents_have_independent_intervals():
    fast = _agent("fast", interval_minutes=5, last_run_at=NOW - timedelta(minutes=6))
    slow = _agent("slow", interval_minutes=60, last_run_at=NOW - timedelta(minutes=6))
    due = agents_due_to_run([fast, slow], NOW)
    assert due == [fast]


def test_mixed_batch_returns_only_the_due_ones_in_order():
    a1 = _agent("a1", last_run_at=None)                                   # due (nunca corrió)
    a2 = _agent("a2", interval_minutes=60, last_run_at=NOW - timedelta(minutes=10))  # no due
    a3 = _agent("a3", interval_minutes=15, last_run_at=NOW - timedelta(minutes=20))  # due
    a4 = _agent("a4", active=False, last_run_at=None)                     # inactivo, nunca due
    due_ids = [a.agent_id for a in agents_due_to_run([a1, a2, a3, a4], NOW)]
    assert due_ids == ["a1", "a3"]
