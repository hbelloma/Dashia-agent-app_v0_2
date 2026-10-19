"""
indicator_requirements.py
===========================
La pieza que faltaba para no tener que adivinar qué indicadores
calcular: antes de correr un agente hace falta saber qué pide
(rsi(14)? sma(50)? price()?) para traer solo esos datos, no un menú fijo
de "por si acaso".

Reutiliza el MISMO validador de dsl_interpreter.py (_validate) — el
código pasa por la validación de seguridad real antes de siquiera mirar
qué indicadores pide. Si el código es inválido, esto falla acá, antes de
gastar una sola llamada a un exchange o a Birdeye/GeckoTerminal.
"""

from __future__ import annotations
import ast

from .dsl_interpreter import _validate, INDICATOR_FUNCS, ZERO_ARG_FUNCS, SandboxSecurityError


class IndicatorRequirements:
    def __init__(self, with_period: set[tuple[str, int]], without_period: set[str]):
        self.with_period = with_period      # {("rsi", 14), ("sma", 50), ...}
        self.without_period = without_period  # {"price", "volume"}

    @property
    def max_period(self) -> int:
        return max((p for _, p in self.with_period), default=0)

    def __repr__(self):
        return f"IndicatorRequirements(with_period={self.with_period}, without_period={self.without_period})"


def extract_required_indicators(source: str) -> IndicatorRequirements:
    """
    Lanza SandboxSecurityError si el código no es válido — mismo error,
    mismo mensaje, que lanzaría SafeInterpreter.run() más adelante. No
    hay una versión "más permisiva" de la validación acá.
    """
    try:
        tree = ast.parse(source, mode="exec")
    except SyntaxError as e:
        raise SandboxSecurityError(f"Error de sintaxis: {e}") from e

    _validate(tree)  # sobre TODO el árbol — igual que en dsl_interpreter.py

    with_period: set[tuple[str, int]] = set()
    without_period: set[str] = set()

    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        name = node.func.id
        if name in INDICATOR_FUNCS:
            period = None
            if node.args:
                period = node.args[0].value
            else:
                for kw in node.keywords:
                    if kw.arg == "period":
                        period = kw.value.value
            if isinstance(period, int) and not isinstance(period, bool):
                with_period.add((name, period))
            # si el periodo no es un entero literal, SafeInterpreter lo va a
            # rechazar en tiempo de ejecución igual (ver test_dsl_interpreter.py)
            # — acá simplemente no lo agregamos a la lista de requerimientos.
        elif name in ZERO_ARG_FUNCS:
            without_period.add(name)

    return IndicatorRequirements(with_period, without_period)
