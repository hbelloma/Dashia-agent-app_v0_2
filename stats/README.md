# stats

Lee los logs de auditoría que `binance_connector.gateway.TradingGateway`
(Binance/Bybit/Weex) y `solana_connector.gateway.SolanaTradingGateway`
**ya escriben** — no se agregó logging nuevo, esto lee el formato que
ya existía. Reconstruye operaciones cerradas con P&L real emparejando
apertura/cierre, calcula estadísticas, y exporta a CSV.

## Verificado contra el gateway real, no adivinado

`test_parses_a_real_audit_log_written_by_the_real_gateway` no arma un
`.jsonl` a mano — corre `TradingGateway` de verdad (con ccxt mockeado,
pero el gateway y su `_audit()` son el código real), deja que escriba
su propio archivo, y confirma que este parser lo lee bien. Es la
diferencia entre "debería funcionar con ese formato" y "funciona con
el formato real".

## Dos formatos distintos, confirmados leyendo cada gateway

| | CEX (Binance/Bybit/Weex) | Solana |
|---|---|---|
| Evento | `"event": "order"` | `"event": "swap"` |
| Apertura trae | `qty`, `price` | `usdc_in` |
| Cierre trae | `price` (la cantidad se asume igual a la apertura — no hay cierres parciales) | `usdc_out_atomic` |
| P&L | `(precio_salida - precio_entrada) * cantidad` | `usdc_out - usdc_in` directo |
| Lado | long o short | siempre long (Jupiter es spot-only) |

Para Solana, el CSV/las estadísticas muestran cantidad y precio de
entrada/salida como "N/D" — no se inventan calculando con los
decimales del token, que varían por token y no vienen en el log.

## ⚠️ Por qué el prototipo de React NO se conecta en vivo a esto

Estos logs `.jsonl` viven en el filesystem de donde corra el backend
real — algo que **todavía no está desplegado** (ver
`trading_backend/README.md`). El prototipo de React corre en el
navegador de quien lo abre: no tiene forma de leer un archivo del
servidor porque ese servidor no existe todavía. Esto es la misma
limitación de siempre en este proyecto (igual que con el formulario de
"conectar exchange" — ver el aviso amarillo en el prototipo).

Lo que sí hice del lado del prototipo: el botón de "Descargar CSV" en
la pestaña de Stats genera un CSV real, descargable, con el mismo
formato de columnas que `csv_export.py` — pero a partir de los datos de
ejemplo que ya tenía el prototipo, no de un log real (porque no hay
ninguno corriendo). El día que el backend esté desplegado con una API,
ese mismo botón apuntaría a un endpoint que llama a `load_trades()` +
`trades_to_csv()` de este paquete, y el CSV sería idéntico en formato.

## Uso

```python
from stats.parser import load_trades
from stats.aggregator import summarize
from stats.csv_export import write_csv

trades, open_positions = load_trades({
    "binance": "binance_audit.jsonl",
    "solana": "solana_audit.jsonl",
})
summary = summarize(trades, open_positions)
print(summary.total_pnl_usd, summary.win_rate_pct)

write_csv(trades, "mis_operaciones.csv", lang="es")
```
