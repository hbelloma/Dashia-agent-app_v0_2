"""
trend.py
========
Deriva la variable `trend` (up/down/flat) que el DSL de agent_sandbox
puede consultar (ver ALLOWED_VARIABLES en dsl_interpreter.py), a partir
de velas reales. Regla deliberadamente simple, no una señal sofisticada:
comparar el precio contra su SMA de 50, con una banda muerta de 0.2%
para no "parpadear" entre up/down cuando el precio está pegado a la
media. Si algún agente necesita una definición de tendencia más
elaborada, que la calcule él mismo con sus propias condiciones sobre
sma()/ema() en el DSL — esto es solo un atajo de contexto razonable.
"""

from __future__ import annotations
import pandas as pd
from dashia_engine.indicators import sma

DEAD_BAND_PCT = 0.2  # % de margen alrededor de la SMA antes de llamarlo "up" o "down"


def derive_trend(df: pd.DataFrame, period: int = 50) -> str:
    if len(df) < period:
        return "flat"  # sin historial suficiente, no afirmar una tendencia que no se puede sustentar
    baseline = sma(df["close"], period).iloc[-1]
    if pd.isna(baseline) or baseline == 0:
        return "flat"
    price = df["close"].iloc[-1]
    pct_diff = (price - baseline) / baseline * 100
    if pct_diff > DEAD_BAND_PCT:
        return "up"
    if pct_diff < -DEAD_BAND_PCT:
        return "down"
    return "flat"
