# trading_backend

Nueve paquetes pensados para vivir juntos en el backend:

- `dashia_engine/` — port del algoritmo DASHIA (features, ANN Lorentziano, kernel, backtest)
- `credentials_vault/` — bóveda multiusuario de API keys, cifrado real
- `binance_connector/` — Binance (ccxt, spot+futuros) + gateway de límites duros
- `bybit_connector/` — Bybit (ccxt, spot+futuros linear) — reutiliza el gateway de Binance
- `weex_connector/` — Weex (ccxt, spot+swap) — sin verificación automática de permisos, confirmación manual
- `solana_connector/` — Jupiter v1+v2, wallet operativa, RPC
- `market_data/` — capa unificada de precios/velas, con Birdeye/GeckoTerminal de respaldo
- `agent_sandbox/` — DSL restringido + aislamiento de proceso real + gateway + **cálculo de indicadores bajo demanda**
- `agent_runtime/` — **el orquestador**: un solo llamado (`run_agent_tick_for_user`) arma market_data, el gateway y la posición del agente automáticamente desde la bóveda
- `stats/` — lee los logs de auditoría reales que los gateways ya escriben, reconstruye operaciones con P&L, y exporta a CSV
- `auth/` — registro/login/sesiones con scrypt, bloqueo por intentos y defensa contra enumeración por tiempo (ver `auth/README.md` para sus límites)
- `agent_runtime/scheduler.py` — el scheduler: corre `run_agent_tick_for_user()` cada N minutos, para cada agente activo de cada usuario, solo

## Instalación conjunta

```bash
pip install ccxt solders solana base58 requests pandas numpy matplotlib pytest cryptography
python -m pytest binance_connector/tests/ bybit_connector/tests/ weex_connector/tests/ \
                  solana_connector/tests/ agent_sandbox/tests/ credentials_vault/tests/ \
                  market_data/tests/ agent_runtime/tests/ -v
python -m dashia_engine.demo
```

## El flujo completo, de punta a punta

```
Usuario conecta sus exchanges (credentials_vault, cifrado real)
        │
        ▼
market_data.build_market_data_for_user() -> UnifiedMarketData
        │
        ▼
agent_runtime.run_agent_tick(source, symbol, market_data, gateway, ...)
        │
        ├─ market_data.get_ohlcv() -> velas reales
        ├─ agent_runtime.derive_trend() -> variable `trend`
        ├─ agent_sandbox.evaluate_and_execute():
        │     Capa 1 (DSL restringido) -> Capa 2 (proceso aislado,
        │     indicadores calculados bajo demanda con dashia_engine) ->
        │     Capa 3 (gateway con límites duros)
        │
        ▼
binance_connector / bybit_connector / weex_connector / solana_connector
        │
        ▼
Orden real en el exchange
```

262 tests (última corrida completa, 15-sep) + 40 de `auth` (corridos con unittest), corriendo de verdad (no mocks donde importa: cifrado real,
procesos reales con límites de memoria/CPU/red reales, indicadores
calculados contra dashia_engine real).
