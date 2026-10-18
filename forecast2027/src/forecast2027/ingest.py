"""Ingesta: del snapshot (planilla + JSON del dashboard) a una tabla cuenta × mes en USD.

Fuentes del snapshot (data/snapshots/<fecha>/):
  - dashboard_growth_forecast2027.json: salida del Apps Script 'Dashboard Growth'.
      clients = filas del 'Forecast 2027 Manual' (referencia a reproducir),
      h25 = 'Final 2025 YTD' (2025 real), h26 = 'Base 2026 real' agregada por cuenta.
  - base_2026_real.json: pestaña 'Base 2026 real' fila a fila (cliente real → cuenta forecast).

El universo de cuentas CS 2027 es el del manual; la base 2026 se le pega con reglas
explícitas (misma cuenta y vertical → misma cuenta → cuenta agrupada 'A + B' prorrateada).
Toda cuenta que no se pueda emparejar queda marcada para la auditoría.
"""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .config import SNAPSHOT_DIR


def norm(s: str) -> str:
    return " ".join((s or "").split()).casefold()


@dataclass
class Cuenta:
    p: str
    nombre: str
    vertical: str
    area: str                       # CS | Growth 26 | Growth 2027
    prob: float = 1.0
    m25: list[float] | None = None  # 2025 real
    m26: list[float] = field(default_factory=lambda: [0.0] * 12)  # base 2026 (real + proy.)
    t26: float = 0.0                # total 2026 según el manual (autoridad)
    manual27: list[float] | None = None
    meta: dict = field(default_factory=dict)
    match26: str = ""               # cómo se emparejó la base 2026

    @property
    def key(self) -> str:
        return f"{self.p}|{self.nombre}"

    @property
    def key_vertical(self) -> str:
        return f"{self.p}|{self.nombre}|{self.vertical}"

    def real_ytd(self, meses_cerrados: int) -> float:
        return sum(self.m26[:meses_cerrados])


@dataclass
class Snapshot:
    fecha: str
    dashboard: dict
    base_rows: list[dict]
    meses_cerrados: int

    @property
    def base26_por_pais(self) -> dict:
        return self.dashboard["base26"]


def ultimo_snapshot() -> str:
    return sorted(p.name for p in SNAPSHOT_DIR.iterdir() if p.is_dir())[-1]


def cargar_snapshot(fecha: str | None = None) -> Snapshot:
    fecha = fecha or ultimo_snapshot()
    d = SNAPSHOT_DIR / fecha
    dash = json.loads((d / "dashboard_growth_forecast2027.json").read_text(encoding="utf-8"))
    base = json.loads((d / "base_2026_real.json").read_text(encoding="utf-8"))
    return Snapshot(fecha=fecha, dashboard=dash, base_rows=base["rows"], meses_cerrados=base.get("meses_cerrados", 9))


def _agregar_base(rows: list[dict]) -> dict[tuple, list[float]]:
    agg: dict[tuple, list[float]] = defaultdict(lambda: [0.0] * 12)
    for r in rows:
        k = (r["p"], norm(r["cuenta"]), norm(r["vertical"]))
        for i in range(12):
            agg[k][i] += r["m"][i]
    return agg


def emparejar_base(c: Cuenta, agg: dict[tuple, list[float]]) -> None:
    """Pega la base 2026 mensual a la cuenta del manual. Deja constancia del método."""
    n, v = norm(c.nombre), norm(c.vertical)
    exact = [k for k in agg if k[0] == c.p and k[1] == n and k[2] == v]
    if exact:
        c.m26 = [sum(agg[k][i] for k in exact) for i in range(12)]
        c.match26 = "cuenta+vertical"
    else:
        same = [k for k in agg if k[0] == c.p and k[1] == n]
        if same:
            c.m26 = [sum(agg[k][i] for k in same) for i in range(12)]
            c.match26 = "cuenta (vertical distinta)"
        else:
            grupo = [k for k in agg if k[0] == c.p and " + " in k[1] and n in [norm(x) for x in k[1].split(" + ")]]
            if grupo and c.t26 > 0:
                tot = sum(sum(agg[k]) for k in grupo)
                share = c.t26 / tot if tot else 0.0
                c.m26 = [sum(agg[k][i] for k in grupo) * share for i in range(12)]
                c.match26 = f"agrupada prorrateada ({share:.0%})"
            else:
                c.m26 = [0.0] * 12
                c.match26 = "sin base 2026" if c.t26 == 0 else "SIN PAREJA (t26>0)"
                return
    tot = sum(c.m26)
    if c.t26 and tot and abs(tot - c.t26) / c.t26 > 0.01:
        # El manual manda: se reescala el perfil y se avisa.
        c.m26 = [x * c.t26 / tot for x in c.m26]
        c.match26 += f" · reescalado {tot:,.0f}→{c.t26:,.0f}"


def construir_cuentas(snap: Snapshot) -> list[Cuenta]:
    agg = _agregar_base(snap.base_rows)
    h25 = defaultdict(lambda: [0.0] * 12)
    for x in snap.dashboard["h25"]:
        for i in range(12):
            h25[(x["p"], norm(x["c"]))][i] += x["m"][i]

    cuentas: list[Cuenta] = []
    for x in snap.dashboard["clients"]:
        if x["ar"] != "CS":
            continue
        c = Cuenta(
            p=x["p"], nombre=x["c"].strip(), vertical=(x.get("v") or "").strip(), area="CS",
            prob=float(x.get("pr", 1) or 0), t26=float(x.get("t26") or 0), manual27=list(x["m"]),
            meta={"origen": x.get("or", ""), "curva_manual": x.get("cu", ""), "g_manual": x.get("g", 0)},
        )
        emparejar_base(c, agg)
        k25 = (c.p, norm(c.nombre))
        c.m25 = list(h25[k25]) if k25 in h25 else None
        cuentas.append(c)
    return cuentas


def cuentas_growth_historicas(snap: Snapshot) -> list[Cuenta]:
    """Altas Growth con su venta del año de alta: 2025 (Final 2025 YTD, Área Growth) y 2026 (Base, Growth 26)."""
    out = []
    for x in snap.dashboard["h25"]:
        if norm(x["ar"]).startswith("g"):
            out.append(Cuenta(p=x["p"], nombre=x["c"].strip(), vertical="", area="Growth 2025", m25=list(x["m"])))
    # Una alta por fila país + cuenta + vertical (así cuenta la sección 4b).
    agg: dict[tuple, list[float]] = defaultdict(lambda: [0.0] * 12)
    for r in snap.base_rows:
        if r["area"] == "Growth 26":
            k = (r["p"], r["cuenta"].strip(), r["vertical"].strip())
            for i in range(12):
                agg[k][i] += r["m"][i]
    for (p, n, v), m in agg.items():
        out.append(Cuenta(p=p, nombre=n, vertical=v, area="Growth 26", m26=m))
    return out
