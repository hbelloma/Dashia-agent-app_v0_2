"""
lazy_indicators.py
====================
El puente real entre agent_sandbox y dashia_engine. Antes de esto,
SafeInterpreter esperaba que alguien le pasara un dict ya calculado
como {("rsi", 14): 28.4} — pero eso obligaba a adivinar de antemano
qué periodos iba a pedir el código del agente (¿rsi(14)? ¿rsi(9)?
¿rsi(37)?). Este objeto se comporta como ese dict desde afuera
(implementa __contains__ y __getitem__, que es todo lo que
dsl_interpreter.py necesita — ver _eval() ahí), pero calcula cada
indicador la primera vez que se pide, con las funciones YA construidas
en dashia_engine.indicators — las clásicas en escala 0-100/precio real,
no las n_xxx normalizadas 0-1 que usa el motor ML de DASHIA para sus
features, que darían valores sin sentido para un `if rsi(14) < 30`
escrito por un humano.

Corre DENTRO del proceso aislado (Capa 2 de agent_sandbox). El código
del agente nunca ve este objeto ni el DataFrame — solo llega a un
valor escalar a través del despachador ya validado en
dsl_interpreter.py, que solo sabe hacer `indicators[("rsi", 14)]` o
`indicators["price"]`, nunca invocar un método arbitrario acá. Esto no
agranda la superficie de ataque de la Capa 1: la lista blanca de qué se
puede pedir sigue siendo la misma (rsi/sma/ema/price/volume).
"""

from __future__ import annotations
import pandas as pd

try:
    from dashia_engine.indicators import rsi as _rsi, sma as _sma, ema as _ema
    _IMPORT_ERROR = None
except ImportError as e:
    _rsi = _sma = _ema = None
    _IMPORT_ERROR = e

_FUNCS = {"rsi": lambda s, p: _rsi(s, p), "sma": lambda s, p: _sma(s, p), "ema": lambda s, p: _ema(s, p)}


class IndicatorUnavailableError(RuntimeError):
    """dashia_engine no se pudo importar dentro del worker — falla ruidoso,
    no en silencio, para no confundirlo con 'el agente pidió algo raro'."""


class LazyIndicatorMap:
    def __init__(self, df: pd.DataFrame):
        if _IMPORT_ERROR is not None:
            raise IndicatorUnavailableError(f"No se pudo importar dashia_engine.indicators: {_IMPORT_ERROR}")
        self.df = df
        self._cache: dict = {}

    def __contains__(self, key) -> bool:
        try:
            self[key]
            return True
        except KeyError:
            return False

    def __getitem__(self, key):
        if key in self._cache:
            return self._cache[key]
        value = self._compute(key)
        self._cache[key] = value
        return value

    def _compute(self, key):
        if key == "price":
            return float(self.df["close"].iloc[-1])
        if key == "volume":
            return float(self.df["volume"].iloc[-1])
        if isinstance(key, tuple) and len(key) == 2:
            name, period = key
            if not isinstance(period, int) or isinstance(period, bool) or period < 1:
                raise KeyError(key)
            if len(self.df) < period:
                raise KeyError(key)  # no hay suficiente historial todavía para esta vela
            func = _FUNCS.get(name)
            if func is None:
                raise KeyError(key)
            value = func(self.df["close"], period).iloc[-1]
            if pd.isna(value):
                raise KeyError(key)
            return float(value)
        raise KeyError(key)
