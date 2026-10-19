"""
gateway_factory.py
====================
El equivalente, del lado de ejecución, a
market_data.vault_bridge.build_market_data_for_user(): arma un gateway
real y verificado directo desde lo que un usuario tiene conectado en la
bóveda, sin que quien llama tenga que saber los detalles de cada
exchange (Binance/Bybit/Weex comparten TradingGateway; Solana necesita
su propio ensamblado con wallet+RPC+Jupiter).

Diferencia importante con connect_and_verify() de credentials_vault:
esto NO vuelve a verificar los permisos contra el exchange en cada
llamada — eso pasa una sola vez, cuando el usuario conecta la cuenta
(ver credentials_vault/README.md). Acá solo se arma el gateway a partir
de una credencial que YA quedó marcada como verificada; si no lo está,
se rechaza con un error claro en vez de operar sin haber confirmado los
permisos.
"""

from __future__ import annotations
import logging

log = logging.getLogger("agent_runtime.gateway_factory")

CEX_EXCHANGES = ("binance", "bybit", "weex")


class GatewayNotReadyError(RuntimeError):
    pass


def build_gateway_for_user(vault, user_id: str, exchange: str, market_type: str = "spot",
                            label: str = "default", limits=None, risk_cfg=None,
                            audit_log_path: str | None = None):
    exchange = exchange.lower()
    cred = vault.get_credential(user_id, exchange, label)

    if not cred.permissions_verified:
        raise GatewayNotReadyError(
            f"La credencial de {exchange} para este usuario todavía no está verificada "
            f"(ver credentials_vault.connector_factory.connect_and_verify) — no se arma "
            f"un gateway con una key que no confirmó tener sin permiso de retiro."
        )

    if exchange in CEX_EXCHANGES:
        from credentials_vault.connector_factory import get_connector
        from binance_connector.config import GatewayLimits
        from binance_connector.gateway import TradingGateway

        connector = get_connector(vault, user_id, exchange, market_type=market_type, label=label)
        kwargs = {"risk_cfg": risk_cfg}
        if audit_log_path:
            kwargs["audit_log_path"] = audit_log_path
        return TradingGateway(connector, limits or GatewayLimits(), **kwargs)

    if exchange == "solana":
        from solana_connector.config import SolanaSettings, SolanaGatewayLimits, TradingWalletCredentials
        from solana_connector.jupiter_client import JupiterClient
        from solana_connector.wallet import TradingWallet
        from solana_connector.rpc import SolanaRPC
        from solana_connector.gateway import SolanaTradingGateway

        settings = SolanaSettings.from_env()
        wallet = TradingWallet(TradingWalletCredentials(secret_key_b58=cred.api_secret))
        kwargs = {"risk_cfg": risk_cfg}
        if audit_log_path:
            kwargs["audit_log_path"] = audit_log_path
        return SolanaTradingGateway(JupiterClient(settings), wallet, SolanaRPC(settings),
                                     limits or SolanaGatewayLimits(), **kwargs)

    raise ValueError(f"Exchange no soportado para gateway: {exchange}")
