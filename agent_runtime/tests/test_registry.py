"""test_registry.py"""
import os
import sys
from datetime import datetime, timezone
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agent_runtime.registry import AgentRegistry, AgentNotFoundError


@pytest.fixture
def registry(tmp_path):
    r = AgentRegistry(db_path=str(tmp_path / "agents.db"))
    yield r
    r.close()


def test_register_and_get_roundtrip(registry):
    registry.register_agent("a1", "user1", "DASHIA", "hold()", "BTC/USDT", "binance", 1000.0)
    cfg = registry.get_agent("a1")
    assert cfg.user_id == "user1" and cfg.symbol == "BTC/USDT" and cfg.active is True
    assert cfg.last_run_at is None


def test_get_nonexistent_agent_raises(registry):
    with pytest.raises(AgentNotFoundError):
        registry.get_agent("no-existe")


def test_list_active_agents_excludes_inactive(registry):
    registry.register_agent("a1", "user1", "A1", "hold()", "BTC/USDT", "binance", 1000.0, active=True)
    registry.register_agent("a2", "user1", "A2", "hold()", "ETH/USDT", "binance", 1000.0, active=False)
    active = registry.list_active_agents()
    assert [a.agent_id for a in active] == ["a1"]


def test_set_active_toggles_visibility_in_list(registry):
    registry.register_agent("a1", "user1", "A1", "hold()", "BTC/USDT", "binance", 1000.0)
    registry.set_active("a1", False)
    assert registry.list_active_agents() == []
    registry.set_active("a1", True)
    assert len(registry.list_active_agents()) == 1


def test_mark_run_updates_last_run_at(registry):
    registry.register_agent("a1", "user1", "A1", "hold()", "BTC/USDT", "binance", 1000.0)
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    registry.mark_run("a1", now)
    assert registry.get_agent("a1").last_run_at == now


def test_list_agents_for_user_only_returns_that_users_agents(registry):
    registry.register_agent("a1", "user1", "A1", "hold()", "BTC/USDT", "binance", 1000.0)
    registry.register_agent("a2", "user2", "A2", "hold()", "ETH/USDT", "binance", 1000.0)
    assert [a.agent_id for a in registry.list_agents_for_user("user1")] == ["a1"]


def test_registering_same_agent_id_again_updates_instead_of_duplicating(registry):
    registry.register_agent("a1", "user1", "A1", "hold()", "BTC/USDT", "binance", 1000.0, interval_minutes=60)
    registry.register_agent("a1", "user1", "A1 renombrado", "sell(size=1)", "BTC/USDT", "binance",
                             2000.0, interval_minutes=15)
    cfg = registry.get_agent("a1")
    assert cfg.name == "A1 renombrado" and cfg.equity_usd == 2000.0 and cfg.interval_minutes == 15


def test_delete_agent(registry):
    registry.register_agent("a1", "user1", "A1", "hold()", "BTC/USDT", "binance", 1000.0)
    registry.delete_agent("a1")
    with pytest.raises(AgentNotFoundError):
        registry.get_agent("a1")


def test_persists_across_instances(tmp_path):
    db_path = str(tmp_path / "shared.db")
    r1 = AgentRegistry(db_path=db_path)
    r1.register_agent("a1", "user1", "A1", "hold()", "BTC/USDT", "binance", 1000.0)
    r1.close()

    r2 = AgentRegistry(db_path=db_path)
    assert r2.get_agent("a1").name == "A1"
    r2.close()
