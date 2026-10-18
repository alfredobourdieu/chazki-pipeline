"""Salidas de una corrida: JSON (mismo esquema que el dashboard) y reporte Markdown para el coordinador."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .audit import Hallazgo
from .backtest import Metrica, mejor_por_pais
from .config import NOMBRE_PAIS, PAISES, Hipotesis
from .growth import GrowthResultado
from .ingest import Snapshot
from .model import Resultado, totales_por_pais

MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def _f(x: float) -> str:
    return f"${x:,.0f}"


def _pct(x: float) -> str:
    return f"{x:+.1%}"


def armar_json(snap: Snapshot, resultados: list[Resultado], growth: GrowthResultado, fx: dict, h: Hipotesis) -> dict:
    clients = []
    for r in resultados:
        clients.append({"p": r.cuenta.p, "ar": "CS", "c": r.cuenta.nombre, "v": r.cuenta.vertical, "pr": r.cuenta.prob,
                        "m": [round(x) for x in r.m27], "t26": round(r.cuenta.t26), "g": r.g, "cu": r.curva,
                        "enero": r.enero_tipo, "piso": r.piso, "match26": r.cuenta.match26, "notas": r.notas,
                        "manual": [round(x) for x in (r.cuenta.manual27 or [])]})
    for p in PAISES:
        clients.append({"p": p, "ar": "G27", "c": "Nuevas cuentas 2027", "v": "", "pr": 1,
                        "m": [round(x) for x in growth.por_pais[p]], "t26": 0, "g": 0, "cu": "", "enero": "", "piso": False})
    tot = totales_por_pais(resultados)
    return {
        "year": 2027, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "source": "forecast2027 motor",
        "snapshot": snap.fecha, "hipotesis_version": h.raw["version"],
        "clients": clients,
        "fx": h.raw["fx"]["ajuste_dic27"], "fxScenario": h.raw["fx"]["escenario"], "fxEffect": {p: round(v) for p, v in fx.items()},
        "base26": snap.base26_por_pais,
        "totales": {p: {"cs27": round(sum(tot.get(p, [0] * 12))), "g27": round(sum(growth.por_pais[p])),
                        "tot27": round(sum(tot.get(p, [0] * 12)) + sum(growth.por_pais[p])),
                        "tot27_fx": round(sum(tot.get(p, [0] * 12)) + sum(growth.por_pais[p]) + fx[p])} for p in PAISES},
        "growth_detalle": growth.detalle,
    }


def armar_markdown(snap: Snapshot, resultados: list[Resultado], growth: GrowthResultado, fx: dict, h: Hipotesis,
                   comparacion: dict, hallazgos: list[Hallazgo], metricas: list[Metrica]) -> str:
    tot = totales_por_pais(resultados)
    L: list[str] = []
    L.append(f"# Forecast 2027 · corrida del motor\n")
    L.append(f"Snapshot `{snap.fecha}` · hipótesis `{h.raw['version']}` · generado {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC\n")

    L.append("## 1. Resultado por país (USD)\n")
    L.append("| País | 2026 base | CS 2027 | Growth 2027 | Total 2027 | Var | Efecto FX | Total ajustado | Var ajustada |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    T = {k: 0.0 for k in ("26", "cs", "g", "tot", "fx")}
    for p in PAISES:
        t26 = snap.base26_por_pais[p]["tot"]
        cs = sum(tot.get(p, [0] * 12)); g = sum(growth.por_pais[p]); t = cs + g
        L.append(f"| {NOMBRE_PAIS[p]} | {_f(t26)} | {_f(cs)} | {_f(g)} | {_f(t)} | {_pct(t / t26 - 1)} | {_f(fx[p])} | {_f(t + fx[p])} | {_pct((t + fx[p]) / t26 - 1)} |")
        T["26"] += t26; T["cs"] += cs; T["g"] += g; T["tot"] += t; T["fx"] += fx[p]
    L.append(f"| **Total** | {_f(T['26'])} | {_f(T['cs'])} | {_f(T['g'])} | **{_f(T['tot'])}** | {_pct(T['tot'] / T['26'] - 1)} | {_f(T['fx'])} | {_f(T['tot'] + T['fx'])} | {_pct((T['tot'] + T['fx']) / T['26'] - 1)} |\n")

    L.append("## 2. Reproducción del manual\n")
    c = comparacion
    L.append(f"Motor {_f(c['total_motor'])} vs manual {_f(c['total_manual'])} → Δ {_f(c['delta_total'])} ({c['delta_total'] / c['total_manual']:+.3%}); WAPE mensual {c['wape_mensual']:.3%}.\n")
    if c["cuentas_fuera_de_tolerancia"]:
        L.append("Cuentas fuera de tolerancia (|Δ| > $500 y > 0,5%):\n")
        L.append("| Cuenta | Motor | Manual | Δ |")
        L.append("|---|---:|---:|---:|")
        for d in c["cuentas_fuera_de_tolerancia"][:20]:
            L.append(f"| {d.key} | {_f(d.motor)} | {_f(d.manual)} | {_f(d.delta)} |")
        L.append("")
    else:
        L.append("Todas las cuentas dentro de tolerancia.\n")

    L.append("## 3. Hallazgos del auditor\n")
    icon = {"alta": "🔴", "media": "🟠", "baja": "🟡", "ok": "🟢"}
    for x in hallazgos:
        monto = f" · {_f(x.monto)}" if x.monto else ""
        L.append(f"- {icon[x.severidad]} **{x.titulo}**{monto}  \n  {x.detalle}")
    L.append("")

    L.append("## 4. Growth 2027 (ventas nuevas, método homologado)\n")
    d = growth.detalle
    L.append(f"Tickets regionales: chica {_f(d['ticket_chica'])} (n={d['n_chicas']}), tanque {_f(d['ticket_tanque'])} con tope (n={d['n_tanques']}).\n")
    L.append("| País | Chicas 25/26 | Tanques 25/26 | Homologado | Factor | Aplicado |")
    L.append("|---|---|---|---:|---:|---:|")
    for p in PAISES:
        dp = d["pais"][p]
        L.append(f"| {NOMBRE_PAIS[p]} | {dp['chicas'][2025]}/{dp['chicas'][2026]} | {dp['tanques'][2025]}/{dp['tanques'][2026]} | {_f(dp['homologado'])} | {dp['factor']:.2f} | {_f(sum(growth.por_pais[p]))} |")
    L.append(f"| **Total** | | | {_f(sum(growth.homologado_sin_factor.values()))} | | **{_f(growth.total)}** |\n")

    L.append("## 5. Backtest del método (datos a dic-25 → real ene–sep 2026)\n")
    L.append("WAPE mensual por variante de mes base (menor es mejor). Sesgo = Σpred/Σreal − 1.\n")
    variantes = sorted({m.variante for m in metricas}, key=lambda v: (v.startswith("ingenuo"), v))
    L.append("| Variante | " + " | ".join(NOMBRE_PAIS[p] for p in PAISES) + " | Total |")
    L.append("|---|" + "---|" * (len(PAISES) + 1))
    idx = {(m.variante, m.pais): m for m in metricas}
    for v in variantes:
        cells = []
        for p in PAISES + ["total"]:
            m = idx.get((v, p))
            cells.append(f"{m.wape:.0%} ({m.sesgo:+.0%})" if m else "–")
        L.append(f"| {v} | " + " | ".join(cells) + " |")
    best = mejor_por_pais(metricas)
    L.append("\nMejor mes base por país según el backtest: " + "; ".join(f"{NOMBRE_PAIS.get(p, p)}: **{m.variante}** ({m.wape:.0%})" for p, m in best.items() if p != "total") + ".\n")
    L.append("> Las curvas puras se estimaron con datos hasta sep-26: el test es levemente optimista y sirve para comparar variantes, no para prometer un error.\n")

    L.append("## 6. Mensual consolidado CS + Growth 2027\n")
    L.append("| País | " + " | ".join(MESES) + " | Total |")
    L.append("|---|" + "---:|" * 13)
    for p in PAISES:
        row = [tot.get(p, [0] * 12)[i] + growth.por_pais[p][i] for i in range(12)]
        L.append(f"| {NOMBRE_PAIS[p]} | " + " | ".join(f"{x / 1000:,.0f}K" for x in row) + f" | {_f(sum(row))} |")
    return "\n".join(L) + "\n"


def escribir(out_dir: Path, data: dict, md: str) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    pj = out_dir / "forecast_2027_motor.json"
    pm = out_dir / "reporte_forecast_2027.md"
    pj.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    pm.write_text(md, encoding="utf-8")
    return pj, pm
