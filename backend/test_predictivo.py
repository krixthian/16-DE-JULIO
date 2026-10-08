"""Pruebas unitarias: no requieren MySQL ni escriben en la base escolar."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from predictivo.features import build_features, outcome, VERSION, FEATURE_NAMES
from predictivo.cli import prepare
from predictivo.source import TABLES
from predictivo.training import split_rows, train_baseline


def fixture():
    data = {k: [] for k in TABLES}
    data['gestiones'] = [dict(id=1, anio=2023, fecha_inicio='2023-02-01', fecha_fin='2023-11-30')]
    data['cursos'] = [dict(id=1, gestion_id=1, grado=2)]
    data['matriculas'] = [dict(id=1, estudiante_id=1, curso_id=1, fecha_ingreso='2023-02-01', fecha_fin=None, origen='SIMULADO', creado_en='2023-02-01T09:00:00')]
    data['asignaciones_docentes'] = [dict(id=1, materia_id=1)]
    for i in range(1, 6):
        data['jornadas_clase'].append(dict(id=i, curso_id=1, fecha=f'2023-03-{i:02}', es_lectiva=True))
        data['asistencias'].append(dict(id=i, matricula_id=1, jornada_id=i, curso_id=1, estado='PRESENTE', justificada=None, registrado_en=f'2023-03-{i:02}T10:00:00'))
    data['evaluaciones'] = [dict(id=1, curso_id=1, asignacion_id=1, fecha_aplicacion='2023-03-10', puntaje_maximo=50, registrado_en='2023-03-01T10:00:00')]
    data['calificaciones'] = [dict(id=1, matricula_id=1, curso_id=1, evaluacion_id=1, estado='CALIFICADA', puntaje=40, registrado_en='2023-03-10T10:00:00')]
    data['tareas'] = [dict(id=1, curso_id=1, fecha_asignacion='2023-03-01T10:00:00', fecha_limite='2023-03-10T10:00:00', registrado_en='2023-03-01T10:00:00')]
    data['entregas_tareas'] = [dict(id=1, curso_id=1, matricula_id=1, tarea_id=1, estado='ENTREGADA', fecha_entrega='2023-03-11T10:00:00', registrado_en='2023-03-11T10:00:00')]
    data['situaciones_escolares'] = [dict(id=1, matricula_id=1, tipo='CONTINUIDAD_CONFIRMADA', fecha_efectiva='2023-11-30', observado_hasta='2023-11-30', fuente_verificacion='SIMULACION', registrado_en='2023-11-30T12:00:00')]
    return data


class FeaturesTests(unittest.TestCase):
    def setUp(self):
        self.data = fixture()

    def build(self):
        return build_features(self.data, '2023-03-31', 'SIMULADO')[0]

    def test_scales_missing_and_future_records(self):
        row = self.build()
        self.assertEqual(row['estado'], 'ELEGIBLE')
        self.assertEqual(row['variables']['promedio_notas'], 80)
        self.assertEqual(row['variables']['proporcion_entregas_tardias'], 1)
        self.assertIsNone(row['variables']['contexto_acoso_reportado'])
        self.data['calificaciones'][0]['registrado_en'] = '2023-04-01T10:00:00'
        self.data['asistencias'].pop()
        values = self.build()['variables']
        self.assertIsNone(values['promedio_notas'])
        self.assertEqual(values['cobertura_asistencia'], .8)
        self.assertEqual(values['proporcion_faltas'], 0)
        self.assertEqual(self.build()['estado'], 'DATOS_INSUFICIENTES')

    def test_pending_and_exempt_are_not_failures(self):
        self.data['entregas_tareas'][0].update(estado='PENDIENTE', fecha_entrega=None)
        values = self.build()['variables']
        self.assertIsNone(values['proporcion_no_entregadas'])
        self.assertEqual(values['tareas_por_revisar'], 1)
        self.data['entregas_tareas'][0]['estado'] = 'EXENTA'
        self.assertEqual(self.build()['variables']['tareas_vencidas'], 0)

    def test_late_correction_reconstructs_original_value(self):
        before = copy.deepcopy(self.data['calificaciones'][0])
        self.data['calificaciones'][0].update(puntaje=0, registrado_en='2023-04-02T10:00:00')
        self.data['auditoria_cambios'] = [dict(id=1, tabla_afectada='calificaciones', registro_id=1, antes=before, registrado_en='2023-04-02T10:00:00')]
        self.assertEqual(self.build()['variables']['promedio_notas'], 80)
        self.data['auditoria_cambios'][0]['antes'] = None
        self.assertIsNone(self.build()['variables']['promedio_notas'])

    def test_context_uses_latest_full_form_without_fill_from_previous(self):
        common = dict(matricula_id=1, origen='SIMULADO', registrado_en='2023-03-20T12:00:00')
        self.data['contextos_permanencia'] = [dict(common, id=1, fecha_observacion='2023-03-10', acoso_reportado=True),
            dict(common, id=2, fecha_observacion='2023-03-20', acoso_reportado=None),
            dict(common, id=3, fecha_observacion='2023-04-01', acoso_reportado=True)]
        self.assertIsNone(self.build()['variables']['contexto_acoso_reportado'])
        self.assertEqual(self.build()['variables']['antiguedad_contexto_dias'], 11)

    def test_unknown_breaks_absence_streak_and_non_schoolday_excluded(self):
        for a in self.data['asistencias']:
            a['estado'] = 'FALTA'
        self.data['asistencias'].pop(2)
        self.assertEqual(self.build()['variables']['racha_faltas'], 2)
        self.data['jornadas_clase'][0]['es_lectiva'] = False
        self.assertEqual(self.build()['variables']['jornadas_registradas'], 4)

    def test_enrollment_origin_and_start_boundary(self):
        self.assertEqual(build_features(self.data, '2023-03-31', 'REAL'), [])
        self.data['matriculas'][0]['fecha_ingreso'] = '2023-04-01'
        self.assertEqual(build_features(self.data, '2023-03-31', 'SIMULADO'), [])

    def test_later_enrollment_does_not_require_unavailable_past_calendar(self):
        self.data['matriculas'][0]['creado_en'] = '2023-09-01T10:00:00'
        self.data['gestiones'][0].update(fecha_inicio=None, fecha_fin=None)
        self.assertEqual(build_features(self.data, '2023-03-31', 'SIMULADO'), [])

    def test_invalid_grades_and_duplicates_rejected(self):
        self.data['calificaciones'][0]['puntaje'] = 51
        with self.assertRaises(ValueError):
            self.build()
        self.data['calificaciones'][0]['puntaje'] = 40
        self.data['asistencias'].append(dict(self.data['asistencias'][0], id=99))
        with self.assertRaises(ValueError):
            self.build()

    def test_outcomes_require_complete_followup_and_exclude_transfers(self):
        row = self.build()
        self.assertEqual(outcome(self.data, row, '2023-12-31')[0], 0)
        self.assertIsNone(outcome(self.data, row, '2023-09-01')[0])
        self.data['situaciones_escolares'][0]['tipo'] = 'TRASLADO'
        self.assertIsNone(outcome(self.data, row, '2023-12-31')[0])
        self.data['situaciones_escolares'][0].update(tipo='ABANDONO_CONFIRMADO', fecha_efectiva='2023-09-01')
        self.assertEqual(outcome(self.data, row, '2023-12-31')[0], 1)
        self.data['situaciones_escolares'][0]['fecha_efectiva'] = '2023-03-01'
        self.assertIsNone(outcome(self.data, row, '2023-12-31')[0])

    def test_labels_do_not_enter_feature_contract(self):
        result = prepare(self.data, 'SIMULADO', '03-31', '2023-12-31')
        row = result['registros'][0]
        self.assertEqual(row['objetivo'], 0)
        self.assertNotIn('objetivo', row['variables'])
        self.assertNotIn('estudiante_id', FEATURE_NAMES)
        self.assertEqual(row['etiqueta_disponible_en'], '2023-11-30')


def training_fixture():
    rows = []
    for year in (2022, 2023):
        for i in range(40):
            row = dict(matricula_id=year * 100 + i, estudiante_id=year * 100 + i, gestion=year, origen='SIMULADO',
                fecha_corte=f'{year}-03-31', horizonte=f'{year}-11-30', etiqueta_disponible_en=f'{year}-11-30',
                version_variables=VERSION, estado='ELEGIBLE', objetivo=i % 2,
                variables={name: None for name in FEATURE_NAMES})
            row['variables'].update(grado=2, promedio_notas=30 if i % 2 else 90)
            rows.append(row)
    return dict(version_variables=VERSION, origen='SIMULADO', registros=rows)


class TrainingTests(unittest.TestCase):
    def test_temporal_student_and_label_availability_separation(self):
        rows = training_fixture()['registros']
        rows[0]['estudiante_id'] = rows[-1]['estudiante_id']
        rows[1]['etiqueta_disponible_en'] = '2023-04-01'
        train, test, purged = split_rows(rows, 2023)
        self.assertEqual(purged, 2)
        self.assertFalse({r['estudiante_id'] for r in train} & {r['estudiante_id'] for r in test})
        self.assertTrue(all(r['gestion'] == 2022 for r in train))

    def test_one_class_rejected(self):
        rows = training_fixture()['registros']
        for row in rows:
            row['objetivo'] = 0
        with self.assertRaises(ValueError):
            split_rows(rows, 2023)

    def test_training_save_reload_and_origin_guard(self):
        dataset = training_fixture()
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'model'
            report = train_baseline(dataset, out, 2023)
            self.assertTrue((out / 'modelo_xgboost.json').exists())
            self.assertEqual(report['origen'], 'SIMULADO')
            self.assertEqual(report['estudiantes_compartidos'], 0)
            self.assertEqual(json.loads((out / 'reporte.json').read_text(encoding='utf-8'))['variables'], FEATURE_NAMES)
            with self.assertRaises(FileExistsError):
                train_baseline(dataset, out, 2023)
            dataset['registros'][0]['origen'] = 'REAL'
            with self.assertRaises(ValueError):
                train_baseline(dataset, Path(directory) / 'mixed', 2023)


if __name__ == '__main__':
    unittest.main()
