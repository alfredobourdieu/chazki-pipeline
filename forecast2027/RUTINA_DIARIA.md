# Rutina diaria del Forecast 2027

La corre la tarea programada **"Forecast 2027 · actualización diaria"** (días hábiles, 09:20 Buenos Aires,
después de los controles de cambios de la planilla de las 08:53 y 08:57). También se puede pedir a mano:
"corré la actualización diaria del forecast".

## Pasos

1. **Ingesta (solo lectura).** Traer las dos fuentes y guardarlas en `data/snapshots/<hoy>/`:
   - Planilla `CS+Growth [Proyección 2025-2026]` (id `1oZlNTtHxpj1z0l60fXklgGANt6uZIdga4IgQ7oDBtUM`),
     pestaña `Base 2026 real`, rango `A11:X700` → `base_2026_real.json` (esquema en `ingest.py`).
   - Drive: `dashboard_growth_forecast2027.json` (id `1fSe1DLM9PzVEWQeQc2bDLTqcVKLkbQNz`), con los escapes
     de markdown limpiados (`re.sub(r'\\(?!["\\/bfnrtu])', '', texto)`).
   - Validar: suma de la base por país = `base26[p].tot` del JSON (±$100) y total del JSON = `Total` de
     `Resumen análisis 2027` fila 9 (±$10). Si no cuadran, la planilla está a medio editar: no guardar,
     avisar y terminar.
   - Si el JSON y la base son idénticos al snapshot anterior, no hay novedades: no guardar nada y avisar en una línea.
2. **Qué cambió en el manual.** `python3 -m forecast2027 cambios` (contra el snapshot anterior).
3. **Reproducción.** `python3 -m forecast2027 compare --snapshot <hoy>`.
   - Si Δ total < 0,02% y no hay cuentas fuera de tolerancia → seguir.
   - Si no cuadra, el manual cambió una hipótesis. Leer `Hipótesis 2027` (filas nuevas), `Inputs manual 2027`
     y `Estacionalidad 2027` y **sincronizar `config/hipotesis_2027.toml` con lo que dice la planilla**
     (no es una decisión nueva: es copiar la decisión que ya tomó Alfredo, citando la fecha y la fila).
     Si la planilla cambió valores mensuales a mano, van como `mensual = [...]` con `fuente`.
     Si cambió la estacionalidad: `python3 scripts/derivar_curvas.py <hoy>`.
   - Si una diferencia no se puede explicar con la planilla, **no** forzar el TOML: dejarla en el reporte.
4. **Control.** Actualizar `snapshot` y `objetivo_total_2027` en el TOML y los números fijos de
   `tests/test_reproduce_manual.py`; correr `python3 -m unittest discover -s tests`. Todo en verde.
5. **Corrida y reporte.** `python3 -m forecast2027 run` → `out/reporte_forecast_2027.md`.
6. **Publicar.** Commit en la rama de trabajo con mensaje `forecast2027: actualización <hoy> · total $X (Δ $Y vs <anterior>)`
   y push. CI vuelve a correr los tests.
7. **Resumen para Alfredo** (5–10 líneas): total 2027 y Δ vs la corrida anterior · los 3–5 cambios del manual que
   más movieron · hipótesis sincronizadas · hallazgos nuevos del auditor con USD · lo que no cuadró, si algo.

## Lo que la rutina nunca hace

- Escribir en la planilla, en Drive o en el Apps Script.
- Cambiar una hipótesis que la planilla no cambió. Las propuestas (p. ej. el mes base que sugiere el backtest)
  van en el resumen, no en el TOML.
- Pisar un snapshot anterior.
