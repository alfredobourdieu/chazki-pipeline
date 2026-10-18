"""Tests de regresión: el motor reproduce el 'Forecast 2027 Manual' auditado el 17-oct-2026.

Si un cambio de hipótesis o de código mueve estos números, el test lo dice. Para cambiar
el resultado a propósito, actualizá las tolerancias y explicá por qué en el commit.
"""
import unittest

from forecast2027.cli import correr
from forecast2027.config import cargar_hipotesis


class ReproduceManual(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = correr("2026-10-18")

    def test_total_cs_cuadra_con_manual(self):
        c = self.r["comparacion"]
        self.assertAlmostEqual(c["total_manual"], 43_543_548, delta=10)
        self.assertLess(abs(c["delta_total"]) / c["total_manual"], 0.0002)   # ±0,02%
        self.assertLess(c["wape_mensual"], 0.001)                              # 0,1% mensual
        self.assertEqual(c["cuentas_fuera_de_tolerancia"], [])

    def test_total_2027_operativo(self):
        total = self.r["comparacion"]["total_motor"] + self.r["growth"].total
        self.assertAlmostEqual(total, self.r["h"].raw["objetivo_total_2027"], delta=5000)

    def test_growth_homologado(self):
        g = self.r["growth"]
        self.assertEqual(g.detalle["n_chicas"], 134)
        self.assertEqual(g.detalle["n_tanques"], 22)
        self.assertAlmostEqual(g.detalle["ticket_chica"], 8_944, delta=5)
        self.assertAlmostEqual(g.detalle["ticket_tanque"], 117_789, delta=5)
        self.assertAlmostEqual(sum(g.homologado_sin_factor.values()), 1_894_945, delta=50)
        self.assertAlmostEqual(g.total, 1_963_940, delta=50)

    def test_fx_base(self):
        self.assertAlmostEqual(sum(self.r["fx"].values()), -737_339, delta=1500)

    def test_factores_mes_base(self):
        # Factores mes base → enero publicados en el manual (col. AA): AR 107%, CL 96%, CO 76%, MX 82%, PE 101%.
        h = self.r["h"]
        esperado = {"AR": 1.07, "CL": 0.96, "CO": 0.76, "MX": 0.82, "PE": 1.01}
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
        base = sum(r.total for r in proyectar_todas(construir_cuentas(cargar_snapshot("2026-10-18")), h))
        h2 = copy.deepcopy(h)
        h2.raw["base"]["ponderar_probabilidad"] = True
        pond = sum(r.total for r in proyectar_todas(construir_cuentas(cargar_snapshot("2026-10-18")), h2))
        # Estafeta 50% ($694K) + Salutare 25% + Unimaq 25% ≈ −$0,38M (Auditoría 2027, tarea 7: −$0,35M)
        self.assertAlmostEqual(base - pond, 382_000, delta=15_000)


if __name__ == "__main__":
    unittest.main()
