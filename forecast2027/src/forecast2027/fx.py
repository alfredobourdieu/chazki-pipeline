"""Efecto tipo de cambio (sección 7): % por país sobre la venta a dic-27, rampa lineal mes/12, sólo erosión."""
from __future__ import annotations

from .config import PAISES, Hipotesis


def efecto_fx(total_por_pais: dict[str, list[float]], h: Hipotesis, escenario: str | None = None) -> dict[str, float]:
    esc = escenario or h.raw["fx"].get("escenario", "base")
    pct = h.raw["fx"]["ajuste_dic27_alto"] if esc == "alto" else h.raw["fx"]["ajuste_dic27"]
    out: dict[str, float] = {}
    for p in PAISES:
        meses = total_por_pais.get(p, [0.0] * 12)
        out[p] = sum(meses[m - 1] * float(pct.get(p, 0.0)) * m / 12 for m in range(1, 13))
    return out
