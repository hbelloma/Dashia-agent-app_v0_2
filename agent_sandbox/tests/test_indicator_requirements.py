"""
test_indicator_requirements.py
================================
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agent_sandbox.indicator_requirements import extract_required_indicators
from agent_sandbox.dsl_interpreter import SandboxSecurityError


def test_extracts_single_indicator_with_period():
    req = extract_required_indicators("if rsi(14) < 30:\n    buy(size=1)")
    assert req.with_period == {("rsi", 14)}
    assert req.without_period == set()


def test_extracts_multiple_indicators_across_multiple_rules():
    source = '''if rsi(14) < 30 and price() > sma(50):
    buy(size=risk.default)
if trend == "up" and volume() > 100:
    sell(size=risk.small)'''
    req = extract_required_indicators(source)
    assert req.with_period == {("rsi", 14), ("sma", 50)}
    assert req.without_period == {"price", "volume"}


def test_deduplicates_repeated_indicator_calls():
    source = "if rsi(14) < 30:\n    buy(size=1)\nif rsi(14) > 70:\n    sell(size=1)"
    req = extract_required_indicators(source)
    assert req.with_period == {("rsi", 14)}  # una sola vez, no dos


def test_different_periods_of_same_indicator_are_both_captured():
    source = "if rsi(9) < rsi(21):\n    buy(size=1)"
    req = extract_required_indicators(source)
    assert req.with_period == {("rsi", 9), ("rsi", 21)}


def test_max_period_reflects_the_largest_requested():
    req = extract_required_indicators("if sma(200) < ema(50):\n    buy(size=1)")
    assert req.max_period == 200


def test_no_indicators_at_all_returns_empty_sets():
    req = extract_required_indicators('if trend == "up":\n    buy(size=1)')
    assert req.with_period == set()
    assert req.without_period == set()


def test_invalid_code_is_rejected_before_extracting_anything():
    with pytest.raises(SandboxSecurityError):
        extract_required_indicators("import os\nbuy(size=1)")


def test_malicious_code_disguised_as_needing_indicators_is_still_rejected():
    # el intento de fuga se rechaza igual, aunque también "pida" un indicador válido
    with pytest.raises(SandboxSecurityError):
        extract_required_indicators("if rsi(14) < 30:\n    eval('1')\nbuy(size=1)")
