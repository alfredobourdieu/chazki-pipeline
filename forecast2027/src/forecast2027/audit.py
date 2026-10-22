"""Auditor: los chequeos de la pestaña 'Auditoría 2027' convertidos en código que corre en cada corrida.

Cada hallazgo tiene severidad (alta / media / baja / ok), un título corto, el detalle y,
cuando aplica, el monto en juego. El coordinador decide qué escalar.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .config import NOMBRE_PAIS, PAISES, Hipotesis
from .growth import GrowthResultado
from .ingest import Cuenta, Snapshot
from .model import Resultado, totales_por_pais


@dataclass
class Hallazgo:
    severidad: str  # alta | media | baja | ok
    chequeo: str
    titulo: str
    detalle: str
    monto: float = 0.0
    cuentas: list[str] = field(default_factory=list)


def _fmt(x: float) -> str:
    return f"${x:,.0f}"


def auditar(snap: Snapshot, cuentas: list[Cuenta], resultados: list[Resultado], growth: GrowthResultado,
            h: Hipotesis, comparacion: dict) -> list[Hallazgo]:
    H: list[Hallazgo] = []
    mc = snap.meses_cerrados
    por_cuenta = {r.cuenta.key_vertical: r for r in resultados}
    tot27 = totales_por_pais(resultados)
    reglas = h.raw["reglas"]

    # 1. Reconciliación de la base 2026: filas de la pestaña vs totales del dashboard
    base_rows = {p: 0.0 for p in PAISES}
    for r in snap.base_rows:
        base_rows[r["p"]] += r["total"]
    for p in PAISES:
        ref = snap.base26_por_pais[p]["tot"]
        if abs(base_rows[p] - ref) > 100:
            H.append(Hallazgo("media", "reconciliacion_base", f"Base 2026 {NOMBRE_PAIS[p]} no cierra",
                              f"filas de 'Base 2026 real' {_fmt(base_rows[p])} vs resumen {_fmt(ref)}", base_rows[p] - ref))
    # 1b. Reproducción del manual
    d = comparacion
    sev = "ok" if abs(d["delta_total"]) < 5000 and d["wape_mensual"] < 0.002 else "alta"
    H.append(Hallazgo(sev, "reproduccion_manual", "Motor vs manual",
                      f"motor {_fmt(d['total_motor'])} · manual {_fmt(d['total_manual'])} · Δ {_fmt(d['delta_total'])} · "
                      f"WAPE mensual {d['wape_mensual']:.3%} · {len(d['cuentas_fuera_de_tolerancia'])} cuentas fuera de tolerancia",
                      d["delta_total"], [x.key for x in d["cuentas_fuera_de_tolerancia"][:10]]))

    # 2. Emparejamiento base ↔ manual
    sin = [c for c in cuentas if c.match26.startswith("SIN PAREJA")]
    resc = [c for c in cuentas if "reescalado" in c.match26]
    if sin:
        H.append(Hallazgo("media", "emparejamiento", f"{len(sin)} cuentas del manual sin base 2026",
                          "; ".join(f"{c.key} ({_fmt(c.t26)})" for c in sin), sum(c.t26 for c in sin), [c.key for c in sin]))
    if resc:
        H.append(Hallazgo("baja", "emparejamiento", f"{len(resc)} cuentas con perfil 2026 reescalado al total del manual",
                          "; ".join(f"{c.key}: {c.match26}" for c in resc), 0.0, [c.key for c in resc]))

    # 3. Duplicados
    vistos: dict[str, int] = {}
    for c in cuentas:
        vistos[c.key] = vistos.get(c.key, 0) + 1
    dup = [k for k, n in vistos.items() if n > 1]
    if dup:
        H.append(Hallazgo("baja", "duplicados", f"{len(dup)} cuentas repetidas en el manual (distinta vertical)", ", ".join(dup), 0.0, dup))

    # 4. Probabilidad < 100% que suma al 100%
    if not h.raw["base"].get("ponderar_probabilidad"):
        pr = [r for r in resultados if r.cuenta.prob < 1 and r.total > 0]
        if pr:
            en_riesgo = sum(r.total * (1 - r.cuenta.prob) for r in pr)
            H.append(Hallazgo("media", "probabilidad", f"{len(pr)} cuentas con probabilidad < 100% suman al 100%",
                              "; ".join(f"{r.cuenta.key} {r.cuenta.prob:.0%} ({_fmt(r.total)})" for r in pr) +
                              f". Si se pondera: −{_fmt(en_riesgo)}", -en_riesgo, [r.cuenta.key for r in pr]))

    # 5. Cuentas en rampa: ≤ 35% del 2026 es real
    umbral = float(reglas["rampa_umbral_real"])
    rampa = [r for r in resultados if r.cuenta.t26 > 0 and r.cuenta.real_ytd(mc) / r.cuenta.t26 <= umbral and r.total > 0]
    rampa.sort(key=lambda r: -r.total)
    if rampa:
        tot = sum(r.total for r in rampa)
        H.append(Hallazgo("alta", "rampa", f"{len(rampa)} cuentas en rampa sostienen {_fmt(tot)} del 2027",
                          "Su 2027 se apoya en 1–3 meses proyectados del 36M. Validar con la facturación real de octubre: " +
                          "; ".join(f"{r.cuenta.key} (real {_fmt(r.cuenta.real_ytd(mc))} / 2026 {_fmt(r.cuenta.t26)} → 2027 {_fmt(r.total)})" for r in rampa[:8]),
                          tot, [r.cuenta.key for r in rampa]))

    # 6. Caídas 2027 vs 2026 sin decisión registrada
    aceptadas = set(h.raw["piso"]["caidas_aceptadas"])
    caen = [r for r in resultados if r.cuenta.t26 > 0 and r.total < r.cuenta.t26 * 0.97 and not r.piso and r.cuenta.key not in aceptadas]
    if caen:
        caen.sort(key=lambda r: r.total - r.cuenta.t26)
        H.append(Hallazgo("media", "decrecimiento_sin_decision", f"{len(caen)} cuentas caen vs 2026 sin decisión en 'Auditoría decrecimientos'",
                          "; ".join(f"{r.cuenta.key} {_fmt(r.cuenta.t26)}→{_fmt(r.total)} ({r.total / r.cuenta.t26 - 1:+.0%})" for r in caen[:12]),
                          sum(r.total - r.cuenta.t26 for r in caen), [r.cuenta.key for r in caen]))

    # 7. Crecimiento asignado que no se ve en el resultado
    inv = [r for r in resultados if r.g > 0 and r.cuenta.t26 > 0 and r.total < r.cuenta.t26]
    if inv:
        H.append(Hallazgo("media", "crecimiento_invisible", f"{len(inv)} cuentas con % asignado terminan por debajo de 2026",
                          "El mes base está debajo de su promedio 2026: " +
                          "; ".join(f"{r.cuenta.key} (+{r.g:.0%} → {r.total / r.cuenta.t26 - 1:+.0%})" for r in inv),
                          0.0, [r.cuenta.key for r in inv]))

    # 8. Enero-27 / dic-26 vs historia ene-26 / dic-25
    for p in PAISES:
        dic26 = sum(c.m26[11] for c in cuentas if c.p == p)
        ene27 = tot27.get(p, [0.0] * 12)[0]
        dic25 = sum(c.m25[11] for c in cuentas if c.p == p and c.m25)
        ene26 = sum(c.m26[0] for c in cuentas if c.p == p and c.m25)
        if dic26 and dic25:
            r27, r26 = ene27 / dic26, ene26 / dic25
            if r27 < r26 - 0.10:
                H.append(Hallazgo("media", "enero_vs_historia", f"{NOMBRE_PAIS[p]}: enero cae más que en la historia",
                                  f"Ene-27/Dic-26 {r27:.0%} vs Ene-26/Dic-25 {r26:.0%} (mes base {h.mes_base[p]}). "
                                  f"El 2027 arranca conservador; +10 pts de ratio ≈ {_fmt(dic26 * 0.10 * 12)} al año.", 0.0))

    # 9. Reglas de crecimiento por país
    for p in PAISES:
        t26 = snap.base26_por_pais[p]["tot"]
        t27 = sum(tot27.get(p, [0.0] * 12)) + sum(growth.por_pais[p])
        var = t27 / t26 - 1 if t26 else 0.0
        minimo = reglas["minimo_crecimiento"].get(p)
        if minimo is None:
            H.append(Hallazgo("alta" if var < 0 else "ok", "regla_pais", f"{NOMBRE_PAIS[p]} {var:+.0%} vs 2026 (sin mínimo)",
                              f"2026 {_fmt(t26)} → 2027 {_fmt(t27)}", t27 - t26))
        else:
            H.append(Hallazgo("ok" if var >= minimo else "alta", "regla_pais",
                              f"{NOMBRE_PAIS[p]} {var:+.0%} vs 2026 (mínimo {minimo:+.0%})", f"2026 {_fmt(t26)} → 2027 {_fmt(t27)}", t27 - t26))

    # 10. Concentración
    rs = sorted(resultados, key=lambda r: -r.total)
    tot_cs = sum(r.total for r in resultados)
    top10 = sum(r.total for r in rs[:10]) / tot_cs if tot_cs else 0
    meli = sum(r.total for r in resultados if r.cuenta.nombre.upper().startswith("MELI"))
    H.append(Hallazgo("alta" if top10 > float(reglas["top10_share_max"]) else "baja", "concentracion",
                      f"Top 10 = {top10:.0%} del CS 2027 · MELI = {meli / tot_cs:.0%}",
                      "; ".join(f"{r.cuenta.key} {_fmt(r.total)}" for r in rs[:5]), meli))

    # 11. Churn implícito
    churn = [r for r in resultados if r.cuenta.t26 > 0 and r.total == 0]
    H.append(Hallazgo("baja", "churn_implicito", f"{len(churn)} cuentas 2026 quedan en 0 en 2027 ({_fmt(sum(r.cuenta.t26 for r in churn))})",
                      ", ".join(r.cuenta.key for r in churn), -sum(r.cuenta.t26 for r in churn), [r.cuenta.key for r in churn]))

    # 12. Proyección oct–dic plana en cuentas grandes (mes copiado)
    planas = [c for c in cuentas if c.t26 > 100000 and len({round(x) for x in c.m26[mc:]}) == 1 and c.m26[mc] > 0]
    if planas:
        H.append(Hallazgo("baja", "proyeccion_plana", f"{len(planas)} cuentas grandes con oct–dic 2026 idénticos (mes copiado)",
                          ", ".join(f"{c.key} ({_fmt(c.m26[mc])}/mes)" for c in planas), 0.0, [c.key for c in planas]))

    # 13. Inconsistencias de documentación (Inputs sección 1 vs manual)
    r = por_cuenta.get("AR|MELI FM|Primera Milla")
    if r and not r.enero_tipo.startswith("1"):
        H.append(Hallazgo("baja", "documentacion", "Inputs sección 1 dice 'MELI FM enero fijo $400K'; el manual usa sep-26 × factor",
                          f"Enero motor/manual {_fmt(r.m27[0])}; con $400K fijo el año sería {_fmt(r.total * 400000 / r.m27[0])}", 0.0))

    # 13b. Cuánto del forecast está cargado a mano (no lo calcula el método)
    mano = [r for r in resultados if r.enero_tipo.startswith("mensual")]
    if mano:
        tot_mano = sum(r.total for r in mano)
        tot_cs = sum(r.total for r in resultados)
        H.append(Hallazgo("media" if tot_mano / tot_cs > 0.25 else "baja", "cargado_a_mano",
                          f"{len(mano)} cuentas con los 12 meses cargados a mano = {_fmt(tot_mano)} ({tot_mano / tot_cs:.0%} del CS 2027)",
                          "No pasan por base, curva ni crecimiento: el backtest no las cubre y cada cambio hay que copiarlo al TOML. " +
                          "; ".join(f"{r.cuenta.key} {_fmt(r.total)}" for r in sorted(mano, key=lambda r: -r.total)[:8]),
                          tot_mano, [r.cuenta.key for r in mano]))

    # 14. Growth 2027 vs lo que facturan las altas 2026
    g26 = sum(snap.base26_por_pais[p]["g26"] for p in PAISES)
    H.append(Hallazgo("media" if growth.total < g26 else "ok", "growth_2027",
                      f"Growth 2027 {_fmt(growth.total)} vs altas 2026 facturando {_fmt(g26)}",
                      f"tickets: chica {_fmt(growth.detalle['ticket_chica'])} (n={growth.detalle['n_chicas']}), "
                      f"tanque {_fmt(growth.detalle['ticket_tanque'])} (n={growth.detalle['n_tanques']})", growth.total - g26))

    orden = {"alta": 0, "media": 1, "baja": 2, "ok": 3}
    H.sort(key=lambda x: orden[x.severidad])
    return H
