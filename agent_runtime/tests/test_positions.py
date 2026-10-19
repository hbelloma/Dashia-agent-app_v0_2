"""test_positions.py"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agent_runtime.positions import PositionStore


@pytest.fixture
def store(tmp_path):
    s = PositionStore(db_path=str(tmp_path / "positions.db"))
    yield s
    s.close()


def test_new_agent_symbol_starts_at_none(store):
    assert store.get_position("agent1", "BTC/USDT") == "none"


def test_set_and_get_roundtrip(store):
    store.set_position("agent1", "BTC/USDT", "long")
    assert store.get_position("agent1", "BTC/USDT") == "long"


def test_rejects_invalid_position_value(store):
    with pytest.raises(ValueError):
        store.set_position("agent1", "BTC/USDT", "sideways")


def test_persists_across_store_instances(tmp_path):
    db_path = str(tmp_path / "shared.db")
    s1 = PositionStore(db_path=db_path)
    s1.set_position("agent1", "SOL", "short")
    s1.close()

    s2 = PositionStore(db_path=db_path)
    assert s2.get_position("agent1", "SOL") == "short"
    s2.close()


def test_agents_and_symbols_are_isolated_from_each_other(store):
    store.set_position("agent1", "BTC/USDT", "long")
    store.set_position("agent2", "BTC/USDT", "short")
    store.set_position("agent1", "ETH/USDT", "none")

    assert store.get_position("agent1", "BTC/USDT") == "long"
    assert store.get_position("agent2", "BTC/USDT") == "short"
    assert store.get_position("agent1", "ETH/USDT") == "none"


@pytest.mark.parametrize("action,expected", [
    ("open_long", "long"), ("open_short", "short"),
    ("close_long", "none"), ("close_short", "none"),
])
def test_apply_gateway_action_transitions_correctly(store, action, expected):
    store.apply_gateway_action("agent1", "BTC/USDT", action)
    assert store.get_position("agent1", "BTC/USDT") == expected


def test_apply_gateway_action_none_does_not_change_position(store):
    store.set_position("agent1", "BTC/USDT", "long")
    store.apply_gateway_action("agent1", "BTC/USDT", None)  # hold, o acción rechazada
    assert store.get_position("agent1", "BTC/USDT") == "long"


def test_updating_position_overwrites_not_duplicates(store):
    store.set_position("agent1", "BTC/USDT", "long")
    store.set_position("agent1", "BTC/USDT", "none")
    store.set_position("agent1", "BTC/USDT", "short")
    assert store.get_position("agent1", "BTC/USDT") == "short"
