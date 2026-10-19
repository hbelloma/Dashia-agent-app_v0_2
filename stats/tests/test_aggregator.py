"""test_aggregator.py"""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from stats.aggregator import summarize
from stats.models import Trade, OpenPosition

NOW = datetime.now(timezone.utc)


def _trade(agent_id="a1", venue="binance", symbol="BTC/USDT", pnl=10.0, notional=1000.0):
    return Trade(agent_id=agent_id, venue=venue, symbol=symbol, side="long",
                 opened_at=NOW, closed_at=NOW, qty=1.0, entry_price=100.0, exit_price=110.0,
                 notional_usd=notional, pnl_usd=pnl)


def test_empty_trades_gives_zeroed_summary_not_a_crash():
    s = summarize([], [])
    assert s.total_trades == 0 and s.win_rate_pct == 0.0


def test_reports_open_positions_even_with_no_closed_trades():
    op = OpenPosition(agent_id="a1", venue="binance", symbol="BTC/USDT", side="long",
                       opened_at=NOW, qty=1.0, entry_price=100.0, notional_usd=100.0)
    s = summarize([], [op])
    assert s.open_positions == 1


def test_win_rate_and_totals():
    trades = [_trade(pnl=10.0), _trade(pnl=-5.0), _trade(pnl=20.0)]
    s = summarize(trades, [])
    assert s.total_trades == 3
    assert s.wins == 2 and s.losses == 1
    assert abs(s.win_rate_pct - 66.67) < 0.01
    assert s.total_pnl_usd == 25.0
    assert abs(s.avg_pnl_usd - 8.33) < 0.01
    assert s.best_trade_pnl_usd == 20.0
    assert s.worst_trade_pnl_usd == -5.0


def test_breakdown_by_agent():
    trades = [_trade(agent_id="dashia", pnl=10.0), _trade(agent_id="dashia", pnl=-4.0),
              _trade(agent_id="otro_agente", pnl=7.0)]
    s = summarize(trades, [])
    assert s.by_agent["dashia"]["trades"] == 2
    assert s.by_agent["dashia"]["pnl_usd"] == 6.0
    assert s.by_agent["otro_agente"]["trades"] == 1
    assert s.by_agent["otro_agente"]["win_rate_pct"] == 100.0


def test_breakdown_by_venue():
    trades = [_trade(venue="binance", pnl=10.0), _trade(venue="solana", pnl=5.0),
              _trade(venue="solana", pnl=-2.0)]
    s = summarize(trades, [])
    assert s.by_venue["binance"]["trades"] == 1
    assert s.by_venue["solana"]["trades"] == 2
    assert s.by_venue["solana"]["pnl_usd"] == 3.0


def test_a_losing_trade_at_exactly_zero_counts_as_loss_not_win():
    trades = [_trade(pnl=0.0)]
    s = summarize(trades, [])
    assert s.wins == 0 and s.losses == 1
