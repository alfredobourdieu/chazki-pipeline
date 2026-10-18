"""Comparación motor vs manual, por cuenta y por país."""
from __future__ import annotations

from dataclasses import dataclass

from .config import PAISES
from .model import Resultado


@dataclass
class Diferencia:
    key: str
    motor: float
    manual: float

    @property
    def delta(self) -> float:
        return self.motor - self.manual

    @property
    def pct(self) -> float:
        return self.delta / self.manual if self.manual else (0.0 if not self.motor else float("inf"))


def comparar(resultados: list[Resultado]) -> dict:
    difs: list[Diferencia] = []
    por_pais = {p: {"motor": 0.0, "manual": 0.0, "abs": 0.0} for p in PAISES}
    for r in resultados:
        man = sum(r.cuenta.manual27 or [0.0] * 12)
        difs.append(Diferencia(r.cuenta.key_vertical, r.total, man))
        pp = por_pais[r.cuenta.p]
        pp["motor"] += r.total
        pp["manual"] += man
        pp["abs"] += sum(abs(a - b) for a, b in zip(r.m27, r.cuenta.manual27 or [0.0] * 12))
    tot_motor = sum(v["motor"] for v in por_pais.values())
    tot_manual = sum(v["manual"] for v in por_pais.values())
    tot_abs = sum(v["abs"] for v in por_pais.values())
    difs.sort(key=lambda d: -abs(d.delta))
    return {
        "total_motor": tot_motor,
        "total_manual": tot_manual,
        "delta_total": tot_motor - tot_manual,
        "wape_mensual": tot_abs / tot_manual if tot_manual else 0.0,
        "por_pais": {p: {**v, "wape_mensual": (v["abs"] / v["manual"] if v["manual"] else 0.0)} for p, v in por_pais.items()},
        "cuentas_fuera_de_tolerancia": [d for d in difs if abs(d.delta) > 500 and abs(d.pct) > 0.005],
        "top_diferencias": difs[:15],
    }
