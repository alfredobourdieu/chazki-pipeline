"""Modelo CS 2027: base → enero → estacionalidad pura × crecimiento asignado, con overrides y piso.

Reglas (pestaña 'Hipótesis 2027', bloques B, C, K, L, M):
  1. Enero 2027 = mes base del país (Base 2026 real) desestacionalizado:
       nivel = base[m] / índice[m];  enero = nivel × índice[enero]
     Excepciones por cuenta: enero fijo (sin estacionalidad), nivel mensual dado,
     dic-26 o sep-26 como mes base.
  2. Feb–dic = enero × encadenado acumulado × rampa de crecimiento
       rampa lineal: mes m = 1 + g·(m−1)/11  →  dic = enero × est. × (1+g)
  3. Piso 2026 (16 cuentas): 2027 = perfil mensual 2026 × (1+g).
  4. Las caídas no cubiertas por el piso se aceptan: si el mes base es 0, el 2027 es 0.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .config import Hipotesis
from .ingest import Cuenta


@dataclass
class Resultado:
    cuenta: Cuenta
    m27: list[float]
    enero_tipo: str
    curva: str
    g: float
    piso: bool
    notas: list[str] = field(default_factory=list)

    @property
    def total(self) -> float:
        return sum(self.m27)


def rampa(g: float, modo: str) -> list[float]:
    if modo == "compuesta":
        return [(1 + g) ** (i / 11) for i in range(12)]
    return [1 + g * i / 11 for i in range(12)]


def enero_2027(c: Cuenta, h: Hipotesis, nivel_idx: list[float], ov: dict) -> tuple[float, str, list[str]]:
    notas: list[str] = []
    if "enero_fijo" in ov:
        return float(ov["enero_fijo"]), "1 (fijo)", notas
    if "nivel" in ov:
        nivel = ov["nivel"]
        if nivel == "promedio2026":
            nivel = sum(c.m26) / 12
        return float(nivel) * nivel_idx[0] / 100, "0 (nivel)", notas
    tipo = str(ov.get("tipo_enero", "ENE"))
    if tipo == "12":
        m = 12
    elif tipo == "9":
        m = 9
    else:
        m = h.mes_base[c.p]
        tipo = "ENE"
    base = c.m26[m - 1]
    factor = nivel_idx[0] / nivel_idx[m - 1]
    if base == 0 and c.t26 > 0:
        # Regla del manual: si el mes base está en 0, toma el primer mes posterior con venta
        # (altas de Q4-26) y le aplica el mismo factor del mes base del país.
        sig = next((i for i in range(m, 12) if c.m26[i] > 0), None)
        if sig is None:
            notas.append(f"mes base ({m}) y los siguientes en 0 con total 2026 {c.t26:,.0f}: el 2027 sale en 0 (caída aceptada)")
        else:
            base = c.m26[sig]
            notas.append(f"mes base ({m}) en 0: se usa el mes {sig + 1} ({base:,.0f}) con el factor del mes base ({factor:.3f})")
            tipo = f"{tipo}→{sig + 1}"
    return base * factor, f"{tipo} (mes {m}, factor {factor:.3f})", notas


def proyectar(c: Cuenta, h: Hipotesis) -> Resultado:
    ov = h.override(c.key_vertical) or h.override(c.key)
    g = h.crecimiento(c.key_vertical) if c.key_vertical in h.raw["crecimiento"]["asignado"] else h.crecimiento(c.key)
    curva, curva_tipo = h.curva_para(c.key, c.p)
    r = rampa(g, h.raw["crecimiento"].get("rampa", "lineal"))
    piso = c.key in h.raw["piso"]["cuentas"]

    if piso or ov.get("perfil2026"):
        m27 = [x * (1 + g) for x in c.m26]
        tipo = "perfil 2026 × (1+g)"
        notas = []
    else:
        enero, tipo, notas = enero_2027(c, h, curva.nivel, ov)
        acum = curva.acumulado
        m27 = [enero * acum[i] * r[i] for i in range(12)]
        if "feb_x" in ov:
            fx = float(ov["feb_x"])
            m27 = [m27[0]] + [v * fx for v in m27[1:]]
            notas.append(f"febrero × {fx} (ajuste de precio, se arrastra)")
    for mes, val in (ov.get("meses_fijos") or {}).items():
        m27[int(mes) - 1] = float(val)
    if h.raw["base"].get("ponderar_probabilidad") and c.prob < 1:
        m27 = [v * c.prob for v in m27]
        notas.append(f"ponderado por probabilidad {c.prob:.0%}")
    return Resultado(cuenta=c, m27=m27, enero_tipo=tipo, curva=curva_tipo, g=g, piso=piso or bool(ov.get("perfil2026")), notas=notas)


def proyectar_todas(cuentas: list[Cuenta], h: Hipotesis) -> list[Resultado]:
    return [proyectar(c, h) for c in cuentas]


def totales_por_pais(resultados: list[Resultado]) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    for r in resultados:
        acc = out.setdefault(r.cuenta.p, [0.0] * 12)
        for i in range(12):
            acc[i] += r.m27[i]
    return out
