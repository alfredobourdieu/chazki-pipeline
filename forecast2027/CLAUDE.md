# Forecast 2027 · reglas para los agentes

Este directorio es el motor en código del **Forecast 2027 de Chazki** (CS + Growth, 5 países, USD).
Reemplaza, en paralelo y sin tocarla, la lógica que hoy vive en la planilla
`CS+Growth [Proyección 2025-2026]` (pestañas `Forecast 2027 Manual`, `Inputs manual 2027`,
`Hipótesis 2027`, `Base 2026 real`, `Estacionalidad 2027`).

## Qué es verdad y qué no

- **Las hipótesis viven en `config/hipotesis_2027.toml`.** Ningún agente inventa un supuesto: si
  falta uno, lo propone en el reporte y lo deja marcado como pendiente para Alfredo.
- **Las curvas viven en `config/curvas_2027.json`** y se derivan con `scripts/derivar_curvas.py`.
  No se editan a mano.
- **Los datos viven en `data/snapshots/<fecha>/`.** Un snapshot es inmutable: una corrida siempre
  se puede repetir. Un dato nuevo = un snapshot nuevo, nunca se pisa el anterior.
- **El manual sigue siendo la referencia oficial** hasta que Alfredo decida lo contrario. El motor
  lo reproduce (tests) y además audita, compara y mide. Nunca escribe en la planilla.
- `objetivo_total_2027` en el TOML es un control de reproducción, no una meta comercial.
  Las metas del año (36M / 40M / 47M según el documento) no están resueltas: no asumir una.

## Reglas del negocio que no se discuten (bloques K–N de 'Hipótesis 2027', 14–17 oct 2026)

1. 2026 oficial = `Base 2026 real` (real cerrado hasta el mes cerrado + proyección oct–dic del 36M).
2. Enero 2027 = mes base del país desestacionalizado con la curva **pura** (promedio 100, producto 100).
   AR septiembre, CL y PE noviembre, CO octubre, MX diciembre. Si el mes base está en 0, el siguiente con venta.
3. Feb–dic = encadenado × rampa **lineal** del crecimiento asignado (dic = ene × est. × (1+g)).
4. Curva propia sólo si es significativa (p<0,10) o por decisión registrada. Hoy: Liverpool, Bimbo,
   Adidas FM, Unilever MX, Casa Luker, Nestlé AR. Chile con mayo y noviembre neutralizados.
5. Piso 2026 para las 16 cuentas listadas; las otras caídas se aceptan (orgánicas o churn).
6. Growth 2027 = método homologado (altas × ticket regional, factor de mercado), forma escalonada.
7. FX = sólo erosión, % por país sobre dic-27 con rampa mes/12.
8. La probabilidad de cierre **no** pondera (hallazgo abierto #6). Cambiarlo es decisión de Alfredo.

## Cómo correr

```bash
cd forecast2027
PYTHONPATH=src python3 -m forecast2027 run            # reporte completo → out/
PYTHONPATH=src python3 -m forecast2027 compare        # motor vs manual por cuenta
PYTHONPATH=src python3 -m forecast2027 audit --json   # hallazgos para el coordinador
PYTHONPATH=src python3 -m forecast2027 backtest       # calibración del método
PYTHONPATH=src python3 -m unittest discover -s tests  # antes de cualquier push
```

Escenario alternativo: copiá el TOML, cambiá hipótesis, `--hipotesis mi_escenario.toml`.

## Qué hace cada agente (`.claude/agents/forecast-*.md`)

| Agente | Rol | Escribe |
|---|---|---|
| `forecast-ingesta` | Trae un snapshot nuevo de la planilla / Drive, valida esquema y totales | `data/snapshots/<fecha>/` |
| `forecast-auditor` | Corre `audit`, interpreta los hallazgos, decide qué escalar | nada (reporta) |
| `forecast-modelo` | Mantiene el motor; cualquier cambio con test que lo cubra | `src/`, `tests/` |
| `forecast-growth` | Ventas nuevas: HubSpot, altas, tickets, forma mensual | `growth.py`, hipótesis `[growth2027]` |
| `forecast-eventos` | Lee notas, memos y planes (Chile, Bavaria, MELI) y **propone** ajustes al TOML | un PR con la propuesta, nunca el TOML directo |
| `forecast-coordinador` | Orquesta: ingesta → run → audit → backtest → compara con la corrida anterior → resumen | `out/` y el mensaje a Alfredo |

Regla de oro: **el motor decide los números, los agentes deciden qué mirar y qué preguntar.**
Un agente no cambia una hipótesis por su cuenta; propone, con el impacto en USD, y espera.

## Actualización diaria

Ver `RUTINA_DIARIA.md`. Sincronizar el TOML con una decisión que **ya está en la planilla** es parte
de la rutina (citando fecha y fila); proponer una decisión nueva no lo es.

## Calibración

`backtest` corre el método con datos a dic-2025 contra el real ene–sep 2026. Es la vara:
un cambio en el modelo o en una hipótesis se acepta si no empeora el WAPE total y no rompe
`tests/test_reproduce_manual.py` (o se actualiza el test con una explicación).

## Convenciones

- Python 3.11+, sin dependencias externas (stdlib: `tomllib`, `json`, `unittest`).
- Nombres de cuenta exactamente como en el manual (`"PAIS|Cliente"`, vertical sólo si se repite).
- Montos en USD, meses 1..12, países AR CL CO MX PE.
- Commits en español, con el impacto en USD cuando cambia un número.
