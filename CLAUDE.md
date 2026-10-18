# chazki-pipeline

Dos proyectos conviven en este repo:

- **`index.html` + `data.json`** — dashboard "Pipeline Intelligence" (HubSpot), datos inyectados
  por Apps Script (`LIVE_DATA`). Sin código de actualización en el repo; último update 2026-04-22.
- **`forecast2027/`** — motor en código del Forecast 2027 (CS + Growth + FX) con auditoría,
  backtest y agentes. Reglas y contexto en `forecast2027/CLAUDE.md`. Los agentes están en
  `.claude/agents/forecast-*.md`; el coordinador es `forecast-coordinador`.

Para cualquier tarea de forecast, empezá por `forecast2027/CLAUDE.md`.
