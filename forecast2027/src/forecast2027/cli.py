"""CLI: python -m forecast2027 <run|compare|cambios|audit|backtest|growth> [--snapshot F] [--contra F] [--out DIR] [--json]"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from . import audit as audit_mod
from . import backtest as bt
from .compare import cambios_entre, comparar
from .config import ROOT, cargar_hipotesis
from .fx import efecto_fx
from .growth import calcular_growth
from .ingest import cargar_snapshot, construir_cuentas, cuentas_growth_historicas, snapshot_anterior
from .model import proyectar_todas, totales_por_pais
from .report import armar_json, armar_markdown, escribir


def correr(snapshot: str | None = None, hipotesis: Path | None = None, contra: str | None = None) -> dict:
    """Una corrida completa y determinista. Devuelve todos los objetos para que el coordinador los use."""
    h = cargar_hipotesis(hipotesis)
    snap = cargar_snapshot(snapshot)
    cuentas = construir_cuentas(snap)
    resultados = proyectar_todas(cuentas, h)
    growth = calcular_growth(cuentas_growth_historicas(snap), h)
    tot = totales_por_pais(resultados)
    consolidado = {p: [tot.get(p, [0.0] * 12)[i] + growth.por_pais[p][i] for i in range(12)] for p in growth.por_pais}
    fx = efecto_fx(consolidado, h)
    comparacion = comparar(resultados)
    hallazgos = audit_mod.auditar(snap, cuentas, resultados, growth, h, comparacion)
    metricas = bt.backtest(cuentas, h)
    previo = contra or snapshot_anterior(snap.fecha)
    cambios = cambios_entre(cargar_snapshot(previo).dashboard, snap.dashboard) if previo else None
    if cambios is not None:
        cambios["desde"] = previo
    return dict(h=h, snap=snap, cuentas=cuentas, resultados=resultados, growth=growth, fx=fx,
                comparacion=comparacion, hallazgos=hallazgos, metricas=metricas, cambios=cambios)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="forecast2027")
    ap.add_argument("cmd", choices=["run", "compare", "cambios", "audit", "backtest", "growth"], nargs="?", default="run")
    ap.add_argument("--snapshot", help="fecha del snapshot (default: el último)")
    ap.add_argument("--contra", help="snapshot con el que comparar los cambios (default: el anterior)")
    ap.add_argument("--hipotesis", type=Path, help="TOML alternativo de hipótesis (escenarios)")
    ap.add_argument("--out", type=Path, default=ROOT / "out")
    ap.add_argument("--json", action="store_true", help="salida JSON por stdout (para agentes)")
    a = ap.parse_args(argv)

    r = correr(a.snapshot, a.hipotesis, a.contra)
    if a.cmd == "run":
        data = armar_json(r["snap"], r["resultados"], r["growth"], r["fx"], r["h"])
        md = armar_markdown(r["snap"], r["resultados"], r["growth"], r["fx"], r["h"], r["comparacion"], r["hallazgos"], r["metricas"], r["cambios"])
        pj, pm = escribir(a.out, data, md)
        if a.json:
            print(json.dumps(data["totales"], ensure_ascii=False))
        else:
            print(md)
            print(f"\n→ {pj}\n→ {pm}", file=sys.stderr)
    elif a.cmd == "compare":
        c = r["comparacion"]
        if a.json:
            print(json.dumps({k: (v if not isinstance(v, list) else [asdict(x) if hasattr(x, "__dataclass_fields__") else x for x in v]) for k, v in c.items()}, ensure_ascii=False, default=str))
        else:
            print(f"motor {c['total_motor']:,.0f} · manual {c['total_manual']:,.0f} · Δ {c['delta_total']:,.0f} · WAPE {c['wape_mensual']:.3%}")
            for d in c["top_diferencias"]:
                print(f"  {d.key:55s} motor {d.motor:>12,.0f} manual {d.manual:>12,.0f} Δ {d.delta:>10,.0f}")
    elif a.cmd == "cambios":
        c = r["cambios"]
        if c is None:
            print("no hay snapshot anterior con el que comparar")
        elif a.json:
            print(json.dumps({**c, "movimientos": [asdict(m) for m in c["movimientos"]]}, ensure_ascii=False))
        else:
            print(f"manual {c['desde']} → {r['snap'].fecha}: {c['total_anterior']:,.0f} → {c['total_actual']:,.0f} (Δ {c['delta_total']:+,.0f})")
            for p, v in c["por_pais"].items():
                print(f"  {p}: {v['anterior']:>12,.0f} → {v['actual']:>12,.0f}  Δ {v['delta']:>+11,.0f}")
            for m in c["movimientos"][:25]:
                print(f"  {m.key:55s} {m.manual:>12,.0f} → {m.motor:>12,.0f}  Δ {m.delta:>+11,.0f}")
    elif a.cmd == "audit":
        hs = r["hallazgos"]
        if a.json:
            print(json.dumps([asdict(x) for x in hs], ensure_ascii=False))
        else:
            for x in hs:
                print(f"[{x.severidad:5s}] {x.titulo}\n        {x.detalle}")
    elif a.cmd == "backtest":
        ms = r["metricas"]
        if a.json:
            print(json.dumps([asdict(m) for m in ms], ensure_ascii=False))
        else:
            for m in ms:
                print(f"{m.variante:45s} {m.pais:6s} WAPE {m.wape:6.1%} sesgo {m.sesgo:+6.1%} ene {m.wape_enero:6.1%} n={m.n}")
    elif a.cmd == "growth":
        g = r["growth"]
        print(json.dumps({"total": g.total, "por_pais": {p: sum(v) for p, v in g.por_pais.items()}, "detalle": g.detalle}, ensure_ascii=False, indent=1))
    return 0
