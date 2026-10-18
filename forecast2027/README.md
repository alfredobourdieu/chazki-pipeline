# Forecast 2027 — motor en código

Versión en código del Forecast 2027 de Chazki. Toma los mismos datos y las mismas hipótesis
que el `Forecast 2027 Manual` de la planilla `CS+Growth [Proyección 2025-2026]`, reproduce su
resultado al dólar y, además, lo audita, lo compara y mide qué tan bien predice el método.

**Corre en paralelo.** No escribe en la planilla ni en el Apps Script; la planilla sigue siendo
la referencia oficial hasta que se decida lo contrario.

## Estado (snapshot 2026-10-18, hipótesis 17-oct)

| | Manual | Motor | Δ |
|---|---:|---:|---:|
| CS 2027 | $43.543.548 | $43.541.622 | −0,004 % |
| Growth 2027 | $1.963.940 | $1.963.940 | 0 |
| **Total operativo** | **$45.507.484** | **$45.505.562** | −$1.922 |
| Efecto FX (base) | −$737.339 | −$737.298 | −$41 |

WAPE mensual por cuenta: 0,005 %. Las diferencias que quedan son redondeo al dólar de la planilla.

## Estructura

```
forecast2027/
├── config/
│   ├── hipotesis_2027.toml   # TODOS los supuestos (base, curvas, crecimiento, overrides, piso, growth, FX, reglas)
│   └── curvas_2027.json      # estacionalidad pura exacta (derivada, no se edita a mano)
├── data/snapshots/<fecha>/   # datos inmutables: planilla (Base 2026 real) + JSON del dashboard
├── src/forecast2027/
│   ├── ingest.py    # snapshot → cuentas × mes (USD); emparejamiento base 2026 ↔ manual
│   ├── model.py     # CS: base → enero → estacionalidad × crecimiento; overrides; piso
│   ├── growth.py    # ventas nuevas 2027 (método homologado)
│   ├── fx.py        # erosión por tipo de cambio
│   ├── audit.py     # 14 chequeos (reconciliación, rampa, probabilidad, concentración, …)
│   ├── compare.py   # motor vs manual por cuenta y país
│   ├── backtest.py  # calibración: datos a dic-25 → real ene–sep 26
│   ├── report.py    # out/forecast_2027_motor.json + out/reporte_forecast_2027.md
│   └── cli.py
├── scripts/derivar_curvas.py
├── tests/
└── CLAUDE.md                 # reglas para los agentes
```

Los agentes están en `../.claude/agents/forecast-*.md` (raíz del repo).

## Uso

```bash
cd forecast2027
PYTHONPATH=src python3 -m forecast2027 run        # imprime el reporte y escribe out/
PYTHONPATH=src python3 -m forecast2027 compare
PYTHONPATH=src python3 -m forecast2027 audit
PYTHONPATH=src python3 -m forecast2027 backtest
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Sin dependencias externas (Python ≥ 3.11).

## Cómo se actualiza un dato

1. Nuevo snapshot: carpeta `data/snapshots/YYYY-MM-DD/` con `base_2026_real.json` y
   `dashboard_growth_forecast2027.json` (el agente de ingesta lo hace desde Drive / Sheets).
2. `python3 -m forecast2027 run --snapshot YYYY-MM-DD`.
3. El reporte dice qué cambió respecto del manual y qué hallazgos aparecieron.

## Cómo se cambia una hipótesis

Editá `config/hipotesis_2027.toml` (o copialo para un escenario) y corré los tests: si el
resultado se mueve, `test_reproduce_manual` lo va a decir. Ese es el punto: cada supuesto
tiene dueño, fecha y motivo en el historial de git.

## Pendiente (siguiente iteración)

- Ingesta en vivo desde Google Sheets (hoy: snapshots que arma el agente de ingesta).
- HubSpot como fuente del Growth 2027 (pipeline real en vez de promedio de altas).
- Publicar `out/forecast_2027_motor.json` para que el dashboard lo lea como segunda serie.
