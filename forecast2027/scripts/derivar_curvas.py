"""Deriva las curvas de estacionalidad exactas a partir del snapshot del manual.

La pestaña 'Estacionalidad 2027' publica los índices redondeados al 1%. Para
reproducir el manual al dólar hace falta la cadena exacta (mes / mes anterior),
que se recupera de una cuenta "limpia" de cada país (curva país, sin crecimiento
asignado, sin overrides) y, para las curvas propias, dividiendo por la rampa de
crecimiento de la cuenta.

Uso:
    python scripts/derivar_curvas.py [YYYY-MM-DD]   # default: último snapshot
Escribe config/curvas_2027.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "data" / "snapshots"

# Cuenta de referencia por país (la más grande con curva país, para minimizar el redondeo
# al dólar de la planilla): (cuenta, crecimiento asignado, multiplicador de febrero).
REF_PAIS = {
    "AR": ("MELI FM", 0.05, 1.15),
    "MX": ("MELI LM MX", 0.05, 1.0),
    "CO": ("Sodimac Bogota CD", 2.0, 1.0),
    "PE": ("iMile SM +Trujillo", 0.10, 1.0),
    "CL": ("Fazil CL", 0.05, 1.0),
}
# Cuentas con curva propia significativa (p<0,10) o por decisión del 14-oct.
REF_CUENTA = {
    "MX|Liverpool": (0.05, 1.0),
    "CO|Bimbo": (0.0, 1.0),
    "CL|Adidas FM": (0.05, 1.0),
    "CO|Casa Luker": (0.0, 1.0),
    "AR|Nestlé": (0.10, 1.0),
}
# Unilever MX tiene curva propia pero el manual le aplica el piso (perfil 2026),
# así que no se puede derivar de la fila: se toma el encadenado publicado.
UNILEVER_MX = [0.99, 1.02, 1.16, 1.14, 0.96, 0.92, 1.07, 0.93, 0.96, 0.94, 0.70, 1.36]


def chain_from_row(m: list[float], g: float, feb_x: float = 1.0) -> list[float]:
    """Encadenado feb..dic (11 valores) neto de la rampa lineal de crecimiento y del ajuste de febrero."""
    ramp = [1 + g * i / 11 for i in range(12)]
    out = []
    for i in range(1, 12):
        if m[i - 1] <= 0:
            raise ValueError("mes en cero en la cuenta de referencia")
        c = (m[i] / m[i - 1]) / (ramp[i] / ramp[i - 1])
        if i == 1:
            c /= feb_x
        out.append(c)
    return out


def main(snapshot: str | None = None) -> None:
    snap = snapshot or sorted(p.name for p in SNAP.iterdir())[-1]
    d = json.loads((SNAP / snap / "dashboard_growth_forecast2027.json").read_text())
    rows = {(x["p"], x["c"].strip()): x for x in d["clients"] if x["ar"] == "CS"}

    pais = {}
    for p, (name, g, feb_x) in REF_PAIS.items():
        pais[p] = [round(v, 7) for v in chain_from_row(rows[(p, name)]["m"], g, feb_x)]
    cuenta = {}
    for key, (g, feb_x) in REF_CUENTA.items():
        p, name = key.split("|")
        cuenta[key] = [round(v, 7) for v in chain_from_row(rows[(p, name)]["m"], g, feb_x)]
    cuenta["MX|Unilever"] = UNILEVER_MX[1:]

    out = {
        "fuente": f"derivado del snapshot {snap} (Forecast 2027 Manual); método de 'Estacionalidad 2027' (14-oct-2026)",
        "nota": "encadenado = mes / mes anterior, feb..dic (11 valores); nivel = cadena acumulada normalizada a promedio 100",
        "referencias": {"pais": REF_PAIS, "cuenta": REF_CUENTA},
        "pais": pais,
        "cuenta": cuenta,
    }
    dest = ROOT / "config" / "curvas_2027.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"escrito {dest}")
    for p, ch in pais.items():
        print(p, [round(c, 3) for c in ch])


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
