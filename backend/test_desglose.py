import unittest

from predictivo import desglose as dg


class DesgloseTests(unittest.TestCase):
    def test_variables(self):
        t1 = [('MAT', 'Saber', 40), ('MAT', 'Saber', 60), ('LCO', 'Saber', 90), ('MAT', 'Hacer', 50), ('LCO', 'Hacer', 70),
            ('MAT', 'Ser', 100), ('MAT', 'Decidir', 80), ('MAT', 'Autoevaluación', 20), ('MAT', 'Saber', None), ('MAT', None, 0)]
        v = dg.variables(t1)
        self.assertEqual(set(v), set(dg.VARIABLES))
        self.assertEqual((v['saber_T1'], v['hacer_T1'], v['ser_T1'], v['decidir_T1'], v['autoevaluacion_T1']), (70, 60, 100, 80, 20))
        self.assertEqual((v['dimension_minima_T1'], v['bajas_T1']), (60, 2))  # la autoevaluación no define la más baja
        self.assertIsNone(v['cambio_saber_hacer'], 'Sin T2 no hay cambio.')
        v = dg.variables(t1, [('MAT', 'Saber', 60), ('MAT', 'Hacer', 60)])
        self.assertEqual(v['cambio_saber_hacer'], -5)
        self.assertTrue(all(x is None for x in dg.variables(None).values()))
        self.assertFalse(any('T3' in k or 'POST' in k for k in dg.VARIABLES))

    def test_dimensiones_no_cambian_la_nota_del_area(self):
        r = [(1, 'Nota del 1.er trimestre - MAT', 80), (1, 'Cierre del 1.er trimestre - Saber - MAT', 10), (1, 'Prueba', 20),
            (2, 'Prueba', 30), (2, 'Trabajo', 50), (3, 'Nota parcial del 3.er trimestre - VER', 60)]
        self.assertEqual(sorted(dg.notas_de_area(r)), [(1, 80), (2, 30), (2, 50), (3, 60)])


if __name__ == '__main__':
    unittest.main()
