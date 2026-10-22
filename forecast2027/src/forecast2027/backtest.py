"""Backtest del método: ¿qué tan bien hubiera predicho el 2026 real con los datos a dic-2025?

Se toman las cuentas CS con venta en 2025 y se proyecta ene–sep 2026 con la misma mecánica
(mes base del país desestacionalizado con la curva pura + encadenado, g = 0, sin overrides).
Se comparan variantes de mes base y dos ingenuos (dic plano, promedio Q4 plano) contra el real.

Métricas por país: WAPE = Σ|pred − real| / Σ real; sesgo = Σ pred / Σ real − 1.
Advertencia: las curvas puras se estimaron con datos hasta sep-26, así que el test es
levemente optimista; sirve para comparar métodos entre sí, no para prometer un error.
"""
from __future__ import annotations

from dataclasses import dataclass

from .config import PAISES, Hipotesis
from .ingest import Cuenta

VARIANTES = {
    "sep": 9, "oct": 10, "nov": 11, "dic": 12,
    "manual (AR sep · CL/PE nov · CO oct · MX dic)": None,
}


@dataclass
class Metrica:
    variante: str
    pais: str
    wape: float
    sesgo: float
    n: int
    wape_enero: float


def _predecir(c: Cuenta, h: Hipotesis, mes_base: int, meses: int) -> list[float]:
    curva = h.curvas_pais[c.p]
    base = c.m25[mes_base - 1]
    enero = base * curva.nivel[0] / curva.nivel[mes_base - 1]
    acum = curva.acumulado
    return [enero * acum[i] for i in range(meses)]


def backtest(cuentas: list[Cuenta], h: Hipotesis, meses: int = 9) -> list[Metrica]:
    univ = [c for c in cuentas if c.m25 and sum(c.m25) > 0 and sum(c.m26[:meses]) > 0]
    out: list[Metrica] = []
    variantes = dict(VARIANTES)
    variantes["ingenuo: dic-25 plano"] = "flat_dic"
    variantes["ingenuo: promedio Q4-25 plano"] = "flat_q4"
    for nombre, mb in variantes.items():
        for p in PAISES + ["total"]:
            abs_err = real = pred_tot = 0.0
            abs_ene = real_ene = 0.0
            n = 0
            for c in univ:
                if p != "total" and c.p != p:
                    continue
                if mb == "flat_dic":
                    pred = [c.m25[11]] * meses
                elif mb == "flat_q4":
                    pred = [sum(c.m25[9:]) / 3] * meses
                else:
                    pred = _predecir(c, h, mb or h.mes_base[c.p], meses)
                realm = c.m26[:meses]
                abs_err += sum(abs(a - b) for a, b in zip(pred, realm))
                real += sum(realm)
                pred_tot += sum(pred)
                abs_ene += abs(pred[0] - realm[0])
                real_ene += realm[0]
                n += 1
            if real:
                out.append(Metrica(nombre, p, abs_err / real, pred_tot / real - 1, n, abs_ene / real_ene if real_ene else 0.0))
    return out


def mejor_por_pais(metricas: list[Metrica]) -> dict[str, Metrica]:
    best: dict[str, Metrica] = {}
    for m in metricas:
        if m.variante.startswith("ingenuo"):
            continue
        if m.pais not in best or m.wape < best[m.pais].wape:
            best[m.pais] = m
    return best
