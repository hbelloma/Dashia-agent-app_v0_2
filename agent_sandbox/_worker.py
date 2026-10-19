#!/usr/bin/env python3
"""
_worker.py
==========
Se ejecuta DENTRO del proceso hijo aislado (después de unshare --net y
con los rlimits ya aplicados vía preexec_fn en el proceso padre — esto
además se los re-aplica a sí mismo por si el padre no pudo). Lee un JSON
por stdin (código del agente + velas OHLCV + variables), calcula los
indicadores que el código realmente pida (vía LazyIndicatorMap, bajo
demanda — ver lazy_indicators.py) y corre el intérprete DSL. Escribe un
JSON por stdout.

Antes de esto, el worker recibía un diccionario de indicadores YA
calculado desde afuera — lo que obligaba a adivinar de antemano qué
períodos iba a pedir el agente. Ahora recibe las velas crudas y calcula
bajo demanda, así que rsi(14), rsi(9) o rsi(37) funcionan igual sin
tener que precomputar nada.
"""
import sys
import os
import json
import resource

# Defensa en profundidad: se re-aplica límites aunque el padre ya lo haya
# hecho vía preexec_fn — si por lo que sea no se aplicaron, esto es la
# segunda oportunidad de contenerlo antes de tocar el intérprete.
try:
    resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))       # no puede hacer fork/spawn
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))         # sin core dumps
except Exception:
    pass

# Cuando se corre bajo `unshare --net`, el drop de privilegios NO puede
# pasar en el preexec_fn del padre (unshare necesita ser root para poder
# crear el namespace de red) — así que este proceso, ya DENTRO del
# namespace de red aislado, se baja privilegios a sí mismo antes de tocar
# una sola línea de código del agente.
if os.environ.get("SANDBOX_DROP_PRIVILEGES") == "1" and os.getuid() == 0:
    os.setgroups([])
    os.setgid(65534)
    os.setuid(65534)

sys.path.insert(0, os.environ.get("SANDBOX_PKG_PATH", "."))
from agent_sandbox.dsl_interpreter import SafeInterpreter, SandboxSecurityError, SandboxRuntimeError
from agent_sandbox.lazy_indicators import LazyIndicatorMap, IndicatorUnavailableError


def main():
    try:
        payload = json.loads(sys.stdin.read())
    except Exception as e:
        print(json.dumps({"error": f"payload inválido: {e}", "type": "protocol"}))
        return

    source = payload.get("source", "")
    variables = payload.get("variables", {})
    ohlcv_rows = payload.get("ohlcv", [])  # lista de [open, high, low, close, volume]

    try:
        import pandas as pd
        df = pd.DataFrame(ohlcv_rows, columns=["open", "high", "low", "close", "volume"])
        indicators = LazyIndicatorMap(df)
    except IndicatorUnavailableError as e:
        print(json.dumps({"error": str(e), "type": "internal"}))
        return
    except Exception as e:
        print(json.dumps({"error": f"no se pudieron cargar las velas: {e}", "type": "protocol"}))
        return

    try:
        decision = SafeInterpreter(indicators=indicators, variables=variables).run(source)
        print(json.dumps({
            "action": decision.action, "size": decision.size, "reasons": decision.reasons,
        }))
    except SandboxSecurityError as e:
        print(json.dumps({"error": str(e), "type": "security"}))
    except SandboxRuntimeError as e:
        print(json.dumps({"error": str(e), "type": "runtime"}))
    except Exception as e:
        print(json.dumps({"error": f"error inesperado: {e}", "type": "unexpected"}))


if __name__ == "__main__":
    main()
