"""
test_gateway_factory.py
=========================
"""
import os
import sys
from unittest.mock import MagicMock, patch
import pytest
import base58
from solders.keypair import Keypair

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from credentials_vault.crypto import EnvelopeCipher
from credentials_vault.store import CredentialsVault
from agent_runtime.gateway_factory import build_gateway_for_user, GatewayNotReadyError

from binance_connector.gateway import TradingGateway
from binance_connector.client import BinanceConnector
from bybit_connector.client import BybitConnector
from weex_connector.client import WeexConnector
from solana_connector.gateway import SolanaTradingGateway


@pytest.fixture
def vault(tmp_path):
    cipher = EnvelopeCipher(EnvelopeCipher.generate_master_key())
    v = CredentialsVault(db_path=str(tmp_path / "vault.db"), cipher=cipher)
    yield v
    v.close()


def test_unverified_credential_is_rejected_before_touching_the_exchange(vault):
    vault.save_credential("user_1", "binance", "K", "S")  # nunca se marcó como verificada
    with pytest.raises(GatewayNotReadyError):
        build_gateway_for_user(vault, "user_1", "binance")


@patch("binance_connector.client.ccxt.binance")
def test_binance_builds_trading_gateway_with_binance_connector(mock_cls, vault):
    mock_cls.return_value = MagicMock()
    vault.save_credential("user_1", "binance", "K", "S")
    vault.mark_permissions_verified("user_1", "binance")

    gw = build_gateway_for_user(vault, "user_1", "binance", audit_log_path="/tmp/gwf_binance.jsonl")
    assert isinstance(gw, TradingGateway)
    assert isinstance(gw.connector, BinanceConnector)


@patch("bybit_connector.client.ccxt.bybit")
def test_bybit_reuses_the_same_trading_gateway_class(mock_cls, vault):
    mock_cls.return_value = MagicMock()
    vault.save_credential("user_1", "bybit", "K", "S")
    vault.mark_permissions_verified("user_1", "bybit")

    gw = build_gateway_for_user(vault, "user_1", "bybit", audit_log_path="/tmp/gwf_bybit.jsonl")
    assert isinstance(gw, TradingGateway)  # el MISMO gateway que Binance, no uno propio
    assert isinstance(gw.connector, BybitConnector)


@patch("weex_connector.client.ccxt.weex")
def test_weex_also_reuses_trading_gateway(mock_cls, vault):
    mock_cls.return_value = MagicMock()
    vault.save_credential("user_1", "weex", "K", "S")
    vault.mark_permissions_verified("user_1", "weex")  # simula que ya se confirmó manual

    gw = build_gateway_for_user(vault, "user_1", "weex", audit_log_path="/tmp/gwf_weex.jsonl")
    assert isinstance(gw, TradingGateway)
    assert isinstance(gw.connector, WeexConnector)


def test_solana_builds_solana_trading_gateway(vault):
    kp = Keypair()
    secret_b58 = base58.b58encode(bytes(kp)).decode()
    vault.save_credential("user_1", "solana", str(kp.pubkey()), secret_b58)
    vault.mark_permissions_verified("user_1", "solana")

    gw = build_gateway_for_user(vault, "user_1", "solana", audit_log_path="/tmp/gwf_solana.jsonl")
    assert isinstance(gw, SolanaTradingGateway)
    assert gw.wallet.pubkey_str == str(kp.pubkey())


def test_solana_with_corrupted_secret_raises_not_silently_ignored(vault):
    vault.save_credential("user_1", "solana", "algun_pubkey", "esto-no-es-base58-valido")
    vault.mark_permissions_verified("user_1", "solana")
    with pytest.raises(Exception):
        build_gateway_for_user(vault, "user_1", "solana")


def test_unsupported_exchange_raises_value_error(vault):
    vault.save_credential("user_1", "coinbase", "K", "S")
    vault.mark_permissions_verified("user_1", "coinbase")
    with pytest.raises(ValueError):
        build_gateway_for_user(vault, "user_1", "coinbase")


@patch("binance_connector.client.ccxt.binance")
def test_custom_limits_are_passed_through(mock_cls, vault):
    mock_cls.return_value = MagicMock()
    vault.save_credential("user_1", "binance", "K", "S")
    vault.mark_permissions_verified("user_1", "binance")

    from binance_connector.config import GatewayLimits
    custom_limits = GatewayLimits(max_position_usd=42, allowed_symbols=("BTC/USDT",))
    gw = build_gateway_for_user(vault, "user_1", "binance", limits=custom_limits,
                                 audit_log_path="/tmp/gwf_custom.jsonl")
    assert gw.limits.max_position_usd == 42
