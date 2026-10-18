"""Carga de hipótesis (TOML) y curvas (JSON). Todo supuesto del modelo vive acá."""
from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"
SNAPSHOT_DIR = ROOT / "data" / "snapshots"
PAISES = ["AR", "CL", "CO", "MX", "PE"]
NOMBRE_PAIS = {"AR": "Argentina", "CL": "Chile", "CO": "Colombia", "MX": "México", "PE": "Perú"}


@dataclass
class Curva:
    """Curva de estacionalidad pura: encadenado feb..dic y nivel (promedio = 100)."""

    encadenado: list[float]  # 11 valores: feb/ene, mar/feb, ..., dic/nov
    nivel: list[float] = field(default_factory=list)  # 12 valores, promedio 100

    def __post_init__(self) -> None:
        if len(self.encadenado) != 11:
            raise ValueError("encadenado debe tener 11 valores (feb..dic)")
        cum = [1.0]
        for c in self.encadenado:
            cum.append(cum[-1] * c)
        avg = sum(cum) / 12
        self.nivel = [c / avg * 100 for c in cum]

    @property
    def acumulado(self) -> list[float]:
        """Índice encadenado acumulado con enero = 1."""
        return [n / self.nivel[0] for n in self.nivel]


@dataclass
class Hipotesis:
    raw: dict
    curvas_pais: dict[str, Curva]
    curvas_cuenta: dict[str, Curva]

    @property
    def mes_base(self) -> dict[str, int]:
        return self.raw["base"]["mes_base"]

    def crecimiento(self, key: str) -> float:
        return float(self.raw["crecimiento"]["asignado"].get(key, 0.0))

    def override(self, key: str) -> dict:
        return self.raw.get("overrides", {}).get(key, {})

    def curva_para(self, key: str, pais: str) -> tuple[Curva, str]:
        est = self.raw["estacionalidad"]
        if key in est.get("cuentas_curva_pais_forzada", []):
            return self.curvas_pais[pais], "país (forzada)"
        if key in est.get("cuentas_curva_propia", []) and key in self.curvas_cuenta:
            return self.curvas_cuenta[key], "propia"
        return self.curvas_pais[pais], "país"


def cargar_hipotesis(path: Path | None = None) -> Hipotesis:
    path = path or CONFIG_DIR / "hipotesis_2027.toml"
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    curvas = json.loads((path.parent / raw["estacionalidad"]["curvas"]).read_text(encoding="utf-8"))
    return Hipotesis(
        raw=raw,
        curvas_pais={p: Curva(v) for p, v in curvas["pais"].items()},
        curvas_cuenta={k: Curva(v) for k, v in curvas["cuenta"].items()},
    )
