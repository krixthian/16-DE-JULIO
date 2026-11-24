import unittest

from predictivo import perfil as pf

OK = dict(n_areas_bajo_51_T1=0, promedio_T1=75, promedio_T2=None, bajas_T1=0, saber_T1=75, cambio_saber_hacer=None, ser_T1=80, decidir_T1=80,
    prop_faltas=.01, racha_actual=0, faltas_ult20=0, prop_retrasos=.01)


class PerfilTests(unittest.TestCase):
    def test_niveles(self):
        n = lambda **k: pf.alerta({**OK, **k})['nivel']
        self.assertEqual(n(), 'VERDE')
        self.assertEqual(n(n_areas_bajo_51_T1=2, bajas_T1=5, ser_T1=40), 'ROJO', 'Sin faltas, las notas solas alertan y no se cuentan tres veces.')
        self.assertEqual(n(prop_faltas=.12), 'ROJO')
        a = pf.alerta({**OK, 'n_areas_bajo_51_T1': 2, 'prop_faltas': .06})
        self.assertEqual((a['nivel'], a['notas_y_asistencia']), ('ROJO', True))
        self.assertFalse(pf.alerta({**OK, 'prop_faltas': .12})['notas_y_asistencia'])
        self.assertEqual(n(bajas_T1=1, prop_faltas=.06), 'AMARILLO', 'Dos amarillos no hacen un rojo.')
        self.assertEqual(n(racha_actual=5), 'URGENTE', 'Las 5 faltas no dependen de las notas.')
        self.assertFalse(pf.alerta({**OK, 'n_areas_bajo_51_T1': 2, 'racha_actual': 5})['notas_y_asistencia'], 'En urgente no cambia el orden.')
        self.assertEqual(n(promedio_T2=65), 'AMARILLO')
        self.assertEqual(n(ser_T1=55), 'AMARILLO')

    def test_sin_dato_y_modelo(self):
        sin = {**OK, **{k: None for k in ('n_areas_bajo_51_T1', 'promedio_T1', 'bajas_T1', 'saber_T1', 'ser_T1', 'decidir_T1')}}
        a = pf.alerta(sin)
        self.assertEqual((a['nivel'], a['colores']['Académica'], a['colores']['Asistencia']), ('VERDE', None, 'VERDE'), 'Sin dato no es rojo ni verde.')
        self.assertEqual(pf.alerta({**sin, 'promedio_T1': float('nan')})['colores']['Académica'], None)
        a = pf.alerta(OK, 'ALTO')
        self.assertEqual((a['nivel'], a['motivos'][0]['dimension']), ('AMARILLO', 'Modelo XGBoost'))


class RecomendacionesPorDimensionTests(unittest.TestCase):
    def test_cada_dimension_tiene_su_accion(self):
        from predictivo import recomendaciones as rp
        c = lambda nivel='MEDIO', **k: [x['codigo'] for x in rp.evaluar({**OK, **k}, nivel)]
        self.assertEqual(c(), ['RP05'])
        self.assertEqual(c(bajas_T1=1), ['RP06'], 'Un amarillo no llama a reunión de caso.')
        self.assertEqual(c(decidir_T1=55), ['RP07'])
        self.assertEqual(c(prop_faltas=.06), ['RP08'])
        self.assertEqual(c(prop_faltas=.06, faltas_ult20=3), ['RP03'], 'Faltas leves no repite a Inasistencia.')
        self.assertEqual(c(promedio_T2=60), ['RP01'])
        self.assertEqual(c('ALTO', n_areas_bajo_51_T1=6, promedio_T1=47, bajas_T1=10, ser_T1=40), ['RP01', 'RP02', 'RP06', 'RP07', 'RP05'])
        self.assertEqual(c('ALTO', prop_faltas=.6, racha_actual=9, faltas_ult20=9), ['RP00', 'RP03', 'RP05'])

    def test_explicacion(self):
        v = {**OK, 'n_areas_bajo_51_T1': 1, 'ser_T1': 40, 'decidir_T1': 55}
        self.assertEqual(pf.explicacion(pf.alerta(v), v), 'Académica (amarillo): 1 área bajo 51. Actitud (rojo): Ser 40, Decidir 55.')


class MismosNumerosTests(unittest.TestCase):
    def test_panel_y_reportes_cuentan_como_alertas(self):
        """Solo lectura sobre la base en uso."""
        from collections import Counter
        from sqlalchemy.orm import Session
        from api import dashboard, reportes
        from database import engine
        from predictivo import seguimiento as sg
        with Session(engine) as db:
            r = sg.calcular(db, 2026)
            esperado = {k: Counter(a['perfil']['nivel'] for a in r['alertas'])[k] for k in pf.NIVELES}
            panel = dashboard.semaforo(2026, db)
            _, filas, (total, niveles, _), _ = reportes.datos(db, 2026, None)
            self.assertEqual((panel['total'], panel['niveles']), (r['total'], esperado))
            self.assertEqual((total, niveles), (r['total'], esperado))
            con_alerta = {reportes.etiqueta(a['estudiante']) for a in r['alertas'] if a['perfil']['nivel'] != 'VERDE'}
            self.assertEqual(con_alerta, {f['etiqueta'] for f in filas if f['nivel'] in ('URGENTE', 'ROJO', 'AMARILLO')})


    def test_dataset_usa_todas_las_matriculas(self):
        """Solo lectura sobre la base en uso: ni los casos guardados ni la gestión simulada."""
        from sqlalchemy.orm import Session
        from api import dashboard
        from database import engine
        with Session(engine) as db:
            d = dashboard.dataset(db)
            self.assertEqual((d['resumen']['matriculas'], d['resumen']['abandonos']), (1889, 11))
            self.assertEqual({g['valor'] for g in d['por_gestion']}, set(range(2021, 2026)))
            for x in d['materias']:
                self.assertEqual(sum(b['matriculas'] for b in x['bandas']), 1889, x['materia'])


if __name__ == '__main__':
    unittest.main()
