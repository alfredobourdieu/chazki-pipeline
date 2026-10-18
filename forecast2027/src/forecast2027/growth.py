"""Growth 2027 (ventas nuevas): método homologado de la sección 4b de 'Inputs manual 2027'.

  venta del año de alta de cada cuenta Growth (2025 real + Growth 26 de la base), netas de mega deals
  chicas  = venta < umbral          → ticket regional medio
  tanques = venta ≥ umbral (tope)   → ticket regional medio con tope
  cuentas nuevas por país = promedio de altas 2025 y 2026
  Growth país = (prom. chicas × ticket chicas + prom. tanques × ticket tanques) × factor de mercado
  forma mensual 'escalonada': mes m = m/78 del anual (cohortes parejas)
"""
from __future__ import annotations

from dataclasses import dataclass

from .config import PAISES, Hipotesis
from .ingest import Cuenta


@dataclass
class GrowthResultado:
    por_pais: dict[str, list[float]]
    detalle: dict
    homologado_sin_factor: dict[str, float]

    @property
    def total(self) -> float:
        return sum(sum(v) for v in self.por_pais.values())


def _altas(cuentas: list[Cuenta], h: Hipotesis) -> dict[int, list[tuple[str, str, float]]]:
    excl = {(p, n, a) for p, n, a in h.raw["growth2027"]["exclusiones"]}
    altas: dict[int, list[tuple[str, str, float]]] = {2025: [], 2026: []}
    for c in cuentas:
        anio = 2025 if c.area == "Growth 2025" else 2026
        venta = sum(c.m25 or []) if anio == 2025 else sum(c.m26)
        if venta <= 0 or (c.p, c.nombre, anio) in excl:
            continue
        altas[anio].append((c.p, c.nombre, venta))
    return altas


def calcular_growth(cuentas_growth: list[Cuenta], h: Hipotesis) -> GrowthResultado:
    g = h.raw["growth2027"]
    umbral, tope = float(g["umbral_tanque"]), float(g["tope_tanque"])
    altas = _altas(cuentas_growth, h)

    chicas = [v for a in altas.values() for _, _, v in a if v < umbral]
    tanques = [min(v, tope) for a in altas.values() for _, _, v in a if v >= umbral]
    ticket_chica = sum(chicas) / len(chicas) if chicas else 0.0
    ticket_tanque = sum(tanques) / len(tanques) if tanques else 0.0

    detalle: dict = {"ticket_chica": ticket_chica, "ticket_tanque": ticket_tanque,
                     "n_chicas": len(chicas), "n_tanques": len(tanques), "pais": {}}
    homolog: dict[str, float] = {}
    aplicado: dict[str, float] = {}
    for p in PAISES:
        n_ch = {a: sum(1 for pp, _, v in altas[a] if pp == p and v < umbral) for a in (2025, 2026)}
        n_tq = {a: sum(1 for pp, _, v in altas[a] if pp == p and v >= umbral) for a in (2025, 2026)}
        prom_ch = (n_ch[2025] + n_ch[2026]) / 2
        prom_tq = (n_tq[2025] + n_tq[2026]) / 2
        base = prom_ch * ticket_chica + prom_tq * ticket_tanque
        homolog[p] = base
        factor = float(g["factor_mercado"].get(p, 1.0))
        aplicado[p] = base * factor
        detalle["pais"][p] = {"chicas": n_ch, "tanques": n_tq, "prom_chicas": prom_ch, "prom_tanques": prom_tq,
                              "homologado": base, "factor": factor}
    if g.get("mantener_total_regional"):
        tot_h, tot_a = sum(homolog.values()), sum(aplicado.values())
        aplicado = {p: v * tot_h / tot_a for p, v in aplicado.items()} if tot_a else aplicado

    if g.get("forma_mensual", "escalonada") == "escalonada":
        shape = [m / 78 for m in range(1, 13)]
    else:  # curva histórica regional de altas (share por mes de la sección 4)
        shape = [0.014, 0.014, 0.020, 0.038, 0.044, 0.043, 0.070, 0.065, 0.081, 0.164, 0.194, 0.253]
        s = sum(shape)
        shape = [x / s for x in shape]
    por_pais = {p: [aplicado[p] * s for s in shape] for p in PAISES}
    return GrowthResultado(por_pais=por_pais, detalle=detalle, homologado_sin_factor=homolog)
