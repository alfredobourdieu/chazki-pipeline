"""Tests unitarios de las reglas del modelo con cuentas sintéticas."""
import unittest

from forecast2027.config import Curva, cargar_hipotesis
from forecast2027.ingest import Cuenta
from forecast2027.model import proyectar, rampa


def cuenta(p="AR", nombre="X", m26=None, **kw):
    return Cuenta(p=p, nombre=nombre, vertical="Next Day", area="CS", m26=m26 or [1000.0] * 12, t26=sum(m26 or [1000.0] * 12), **kw)


class Reglas(unittest.TestCase):
    def setUp(self):
        self.h = cargar_hipotesis()

    def test_rampa_lineal_y_compuesta(self):
        lin = rampa(0.10, "lineal")
        self.assertEqual(lin[0], 1.0)
        self.assertAlmostEqual(lin[11], 1.10)
        self.assertAlmostEqual(lin[6] - lin[5], 0.10 / 11)
        comp = rampa(0.10, "compuesta")
        self.assertAlmostEqual(comp[11], 1.10)
        self.assertLess(comp[5], lin[5])  # la compuesta carga más a fin de año

    def test_curva_plana_sin_crecimiento_mantiene_el_nivel(self):
        self.h.curvas_pais["AR"] = Curva([1.0] * 11)
        r = proyectar(cuenta(m26=[1000.0] * 12), self.h)
        self.assertEqual([round(x) for x in r.m27], [1000] * 12)

    def test_mes_base_desestacionalizado(self):
        # Curva: septiembre al 80% del nivel y enero al 120% → un sep de 800 es nivel 1000 y enero 1200.
        chain = [1.0] * 11
        cv = Curva(chain)
        self.h.curvas_pais["AR"] = cv
        m26 = [0.0] * 12
        m26[8] = 800.0  # septiembre
        r = proyectar(cuenta(m26=m26), self.h)
        self.assertAlmostEqual(r.m27[0], 800.0 * cv.nivel[0] / cv.nivel[8])

    def test_mes_base_en_cero_toma_el_siguiente_con_venta(self):
        self.h.curvas_pais["AR"] = Curva([1.0] * 11)
        m26 = [0.0] * 12
        m26[10] = 500.0  # sólo noviembre (AR mes base = septiembre)
        r = proyectar(cuenta(m26=m26), self.h)
        self.assertAlmostEqual(r.m27[0], 500.0)
        self.assertTrue(any("se usa el mes 11" in n for n in r.notas))

    def test_sin_venta_desde_el_mes_base_da_cero(self):
        m26 = [100.0] * 8 + [0.0] * 4
        r = proyectar(cuenta(m26=m26), self.h)
        self.assertEqual(r.total, 0.0)

    def test_piso_perfil_cliente(self):
        m26 = [float(i * 100) for i in range(1, 13)]
        c = cuenta(nombre="Prota", m26=m26)  # AR|Prota está en la lista de piso
        r = proyectar(c, self.h)
        self.assertTrue(r.piso)
        self.assertEqual(r.m27, m26)

    def test_override_enero_fijo_y_crecimiento(self):
        self.h.curvas_pais["MX"] = Curva([1.0] * 11)
        self.h.raw["overrides"]["MX|Sintetica"] = {"enero_fijo": 120000}
        self.h.raw["crecimiento"]["asignado"]["MX|Sintetica"] = 0.10
        r = proyectar(cuenta(p="MX", nombre="Sintetica", m26=[50000.0] * 12), self.h)
        self.assertEqual(r.m27[0], 120000.0)  # enero fijo, sin estacionalidad
        self.assertAlmostEqual(r.m27[11], 132000.0)  # dic = ene × (1 + g)

    def test_override_mensual_y_churn(self):
        vals = [float(i) for i in range(1, 13)]
        self.h.raw["overrides"]["MX|Sintetica"] = {"mensual": vals}
        r = proyectar(cuenta(p="MX", nombre="Sintetica"), self.h)
        self.assertEqual(r.m27, vals)
        self.h.raw["overrides"]["MX|Sintetica"] = {"churn": True}
        self.assertEqual(proyectar(cuenta(p="MX", nombre="Sintetica"), self.h).total, 0.0)

    def test_feb_x_se_arrastra(self):
        self.h.curvas_pais["AR"] = Curva([1.0] * 11)
        self.h.raw["overrides"]["AR|Sintetica"] = {"feb_x": 1.15}
        c = cuenta(nombre="Sintetica", m26=[1000.0] * 12)
        r = proyectar(c, self.h)
        self.assertAlmostEqual(r.m27[1] / r.m27[0], 1.15)
        self.assertAlmostEqual(r.m27[11] / r.m27[0], 1.15)

    def test_probabilidad_pondera_si_se_activa(self):
        self.h.raw["base"]["ponderar_probabilidad"] = True
        self.h.curvas_pais["AR"] = Curva([1.0] * 11)
        r = proyectar(cuenta(m26=[1000.0] * 12, prob=0.5), self.h)
        self.assertAlmostEqual(r.total, 6000.0)


if __name__ == "__main__":
    unittest.main()
