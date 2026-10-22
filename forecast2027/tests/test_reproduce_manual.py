"""Tests de regresión: el motor reproduce el 'Forecast 2027 Manual' del snapshot vigente.

El snapshot y el total de control salen de config/hipotesis_2027.toml (`snapshot`,
`objetivo_total_2027`). Cada actualización diaria que cambia hipótesis actualiza esos dos
campos y los números de abajo en el mismo commit, con el Δ en USD en el mensaje.
"""
import unittest

from forecast2027.cli import correr
from forecast2027.config import cargar_hipotesis


class ReproduceManual(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snap = cargar_hipotesis().raw["snapshot"]
        cls.r = correr(cls.snap)

    def test_total_cs_cuadra_con_manual(self):
        c = self.r["comparacion"]
        self.assertAlmostEqual(c["total_manual"], 42_235_351, delta=10)
        self.assertLess(abs(c["delta_total"]) / c["total_manual"], 0.0002)   # ±0,02%
        self.assertLess(c["wape_mensual"], 0.001)                              # 0,1% mensual
        self.assertEqual(c["cuentas_fuera_de_tolerancia"], [])

    def test_total_2027_operativo(self):
        total = self.r["comparacion"]["total_motor"] + self.r["growth"].total
        self.assertAlmostEqual(total, self.r["h"].raw["objetivo_total_2027"], delta=5000)

    def test_growth_homologado(self):
        g = self.r["growth"]
        self.assertEqual(g.detalle["n_chicas"], 137)
        self.assertEqual(g.detalle["n_tanques"], 22)
        self.assertAlmostEqual(g.detalle["ticket_chica"], 8_492, delta=5)
        self.assertAlmostEqual(g.detalle["ticket_tanque"], 111_955, delta=5)
        self.assertAlmostEqual(sum(g.homologado_sin_factor.values()), 1_813_183, delta=50)
        self.assertAlmostEqual(g.total, 1_876_205, delta=50)

    def test_fx_base(self):
        self.assertAlmostEqual(sum(self.r["fx"].values()), -743_363, delta=1500)

    def test_factores_mes_base(self):
        # Factores mes base → enero publicados en el manual (col. AA): AR 108%, CL 90%, CO 82%, MX 81%, PE 101%.
        h = self.r["h"]
        esperado = {"AR": 1.08, "CL": 0.90, "CO": 0.82, "MX": 0.81, "PE": 1.01}
        for p, f in esperado.items():
            cv = h.curvas_pais[p]
            m = h.mes_base[p]
            self.assertAlmostEqual(cv.nivel[0] / cv.nivel[m - 1], f, delta=0.006, msg=p)

    def test_curvas_puras_promedio_100(self):
        h = self.r["h"]
        for k, cv in {**h.curvas_pais, **h.curvas_cuenta}.items():
            self.assertAlmostEqual(sum(cv.nivel) / 12, 100.0, places=6, msg=k)

    def test_todas_las_cuentas_del_manual_tienen_base(self):
        sin = [c.key for c in self.r["cuentas"] if c.match26.startswith("SIN PAREJA")]
        self.assertEqual(sin, [])


class Escenarios(unittest.TestCase):
    def test_ponderar_probabilidad_baja_el_total(self):
        import copy
        from forecast2027.ingest import cargar_snapshot, construir_cuentas
        from forecast2027.model import proyectar_todas
        h = cargar_hipotesis()
        snap = h.raw["snapshot"]
        base = sum(r.total for r in proyectar_todas(construir_cuentas(cargar_snapshot(snap)), h))
        h2 = copy.deepcopy(h)
        h2.raw["base"]["ponderar_probabilidad"] = True
        pond = sum(r.total for r in proyectar_todas(construir_cuentas(cargar_snapshot(snap)), h2))
        # Estafeta 50% ($199K, presupuesto Roberto) + Salutare 25% ($31K) + Unimaq 25% ($16K) ≈ −$0,13M
        self.assertAlmostEqual(base - pond, 134_600, delta=2_000)


if __name__ == "__main__":
    unittest.main()
