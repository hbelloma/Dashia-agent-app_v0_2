# agent_runtime

El pegamento que faltaba: `market_data` (velas reales) + `agent_sandbox`
(DSL restringido + aislamiento) + un gateway real, en una sola función.

## Cómo se resolvió "conectar los indicadores de verdad"

Antes: `agent_sandbox` esperaba un diccionario de indicadores YA
calculado desde afuera — `{("rsi", 14): 28.4}` — lo que obligaba a
adivinar de antemano qué período iba a pedir el código del agente. Si
alguien escribía `rsi(9)` y solo se había precalculado `rsi(14)`, fallaba.

Ahora: el proceso aislado recibe las **velas crudas** (las que trae
`market_data.get_ohlcv()`) y calcula cada indicador la primera vez que
el código lo pide, con las funciones clásicas ya construidas en
`dashia_engine.indicators` — ver `agent_sandbox/lazy_indicators.py`.
`rsi(14)`, `rsi(9)`, `rsi(37)` funcionan todos igual, sin precomputar nada.

```
market_data.get_ohlcv("BTC")          # velas reales (Binance/Bybit/Weex/Solana)
        │
        ▼
agent_runtime.derive_trend(df)        # variable `trend` para el DSL
        │
        ▼
agent_sandbox.evaluate_and_execute()  # Capa 1+2+3: DSL -> aislado -> gateway
  └─ dentro del proceso aislado: LazyIndicatorMap(df) calcula
     rsi()/sma()/ema() bajo demanda con dashia_engine.indicators
        │
        ▼
gateway.execute_signal()              # Binance/Bybit/Weex/Solana, orden real
```

## Un bug real que salió mientras se armaba esto (no cosmético)

Al escribir los tests con velas reales en vez de valores de indicador
declarados a mano, una serie puramente alcista (sin ninguna baja) debía
dar `rsi(14) > 70` y en cambio el sistema decidía `hold`. Investigando:
`dashia_engine.indicators.rsi()` tenía un bug real — cuando no hay
NINGUNA pérdida en la ventana (tendencia alcista pura), la división
`avg_gain/avg_loss` da `NaN` (por el `.replace(0, nan)`), y el
`.fillna(50)` que estaba pensado para el caso "sin ningún movimiento"
también atrapaba este caso, dejando el RSI en 50 (neutral) cuando el
valor correcto es 100 (fuerza alcista pura). Corregido en
`dashia_engine/indicators.py` — verificado que no cambió el resultado
del backtest de DASHIA sobre datos sintéticos (`python -m dashia_engine.demo`
da exactamente los mismos números de antes), porque una racha sin
ninguna baja en 14 velas seguidas es rara en datos con ruido real; el
bug solo se veía con series perfectamente monótonas como las que usan
estos tests.

## Qué se resolvió en esta vuelta: "para el usuario X", de verdad

`run_agent_tick()` (la versión original) ya conectaba market_data +
agent_sandbox + un gateway — pero todavía había que armarle el
market_data y el gateway a mano, y pasarle la posición actual vos
mismo en cada llamada. Eso seguía siendo "piezas sueltas que conectás
vos", solo que ahora en una función en vez de en tres.

`run_agent_tick_for_user()` es el nivel de arriba: le das `user_id`,
`agent_id`, el código del agente y el exchange, y arma todo solo:

- **`gateway_factory.py`** — arma el gateway real (Binance/Bybit/Weex
  comparten `TradingGateway`; Solana arma su propio wallet+RPC+Jupiter)
  directo desde lo que el usuario tiene conectado en la bóveda. Exige
  que la credencial ya esté verificada — no arma un gateway con una key
  que nunca confirmó no tener permiso de retiro.
- **`positions.py`** — registro persistente (SQLite) de qué posición
  tiene cada agente en cada símbolo. Antes esto era un parámetro que
  había que llevar a mano entre un tick y el siguiente.

La prueba que de verdad importa acá (`test_runner_for_user.py`): correr
**dos ticks seguidos**, el primero abre una posición, y el segundo —
sin que nadie le pase `position="long"` a mano — sabe solo que ya está
long, y por eso ejecuta `close_long` en vez de intentar abrir un short.
Eso es lo que separa "conecté las piezas a mano" de "hay un
orquestador de verdad".

## El scheduler (nuevo)

`scheduler.py` cierra el último hueco: llama a `run_agent_tick_for_user()`
cada N minutos, para cada agente activo de cada usuario — sin que nadie
tenga que disparar cada tick a mano.

```
run_scheduler_loop()  — el while True real, con sleep entre pasadas
        │
        ▼
run_scheduler_pass()  — UNA pasada: sin sleep, 100% testeable
        │
        ├─ agents_due_to_run()  — lógica pura: ¿a quién le toca correr?
        │                          (probada con fechas fabricadas, sin
        │                          esperar tiempo real)
        │
        └─ run_due_agent()  — por cada agente que le toca:
              ├─ MarketDataCache — reutiliza el UnifiedMarketData del
              │                    usuario entre agentes, no lo arma
              │                    de nuevo en cada tick
              ├─ run_agent_tick_for_user()
              └─ aísla el error si el agente falla — el resto de la
                 pasada sigue igual, y last_run_at se actualiza aunque
                 haya fallado (para que no quede reintentando sin
                 respiro en cada pasada)
```

`AgentRegistry` (nuevo, `registry.py`) es el registro persistente de
"qué agentes existen, de qué usuario, con qué código, cada cuántos
minutos" — antes no había ningún lugar donde viviera esa lista.

### Un bug real que salió al escribir el test del loop (no cosmético)

El primer test que hace correr el loop de verdad en un thread aparte
falló con `sqlite3.ProgrammingError: SQLite objects created in a thread
can only be used in that same thread`. `AgentRegistry`, `PositionStore`
y `CredentialsVault` se crean en el thread principal, pero el scheduler
corre en su propio thread de fondo — y sqlite3 bloquea eso por defecto.
Se corrigió agregando `check_same_thread=False` a las tres conexiones
(un solo thread las usa por vez, secuencial, así que es seguro — no
habilita escrituras concurrentes desde varios threads a la vez, que es
un problema distinto y no resuelto acá, ver abajo).

Dos bugs más aparecieron en los TESTS (no en el scheduler) al probar
esto de punta a punta: un test registraba un agente con `hold()` y
esperaba que operara (nunca iba a pasar, `hold()` no opera por
diseño), y otro esperaba múltiples órdenes reales de un agente que,
correctamente, no vuelve a comprar si ya está long. Ambos corregidos.

## Qué sigue pendiente (no se resolvió acá, a propósito)

- **Concurrencia real entre agentes.** Hoy `run_scheduler_pass` corre
  los agentes secuencialmente, uno por uno. Con pocos agentes está
  bien; con muchos, la pasada completa tarda la suma de todos. Un pool
  de threads/procesos lo aceleraría, pero abre el problema real de
  SQLite con escrituras concurrentes desde varios threads a la vez
  (distinto del problema de arriba, que era un solo thread de fondo)
  — necesitaría un lock por conexión o migrar a Postgres.
- **Quién arranca el proceso que corre `run_scheduler_loop()`.** Esto
  es la función, no el servicio — falta el `systemd`/contenedor/lo que
  sea que la mantenga viva en producción, reinicie si se cae, etc.

## Uso

```python
from agent_runtime.runner import run_agent_tick

outcome = run_agent_tick(
    agent_id="user123-agent1",
    source='if rsi(14) < 30 and trend == "up":\n    buy(size=risk.default)',
    symbol="BTC/USDT",
    market_data=umd,       # market_data.vault_bridge.build_market_data_for_user(...)
    gateway=gateway,        # TradingGateway o SolanaTradingGateway
    equity_usd=1000,
    position="none",
)
print(outcome.executed, outcome.reason)
```

### Corriendo el scheduler de verdad

```python
from agent_runtime.registry import AgentRegistry
from agent_runtime.positions import PositionStore
from agent_runtime.scheduler import run_scheduler_loop

registry = AgentRegistry(db_path="agents.db")
registry.register_agent(
    agent_id="user123-dashia", user_id="user123", name="DASHIA",
    source='if rsi(14) < 30 and trend == "up":\n    buy(size=risk.default)',
    symbol="BTC/USDT", exchange="binance", equity_usd=1000.0, interval_minutes=60,
)

run_scheduler_loop(registry, vault, PositionStore(db_path="positions.db"), poll_interval_s=30)
# corre para siempre, revisando cada 30s quién le toca correr — parar con un threading.Event
```
