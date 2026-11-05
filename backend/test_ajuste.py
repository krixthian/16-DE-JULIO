"""Ajuste anidado de hiperparámetros sobre datos ficticios: sin MySQL ni datos reales."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from predictivo import ajuste_real as aj
from predictivo.real_t1 import load
from test_alertas import excel_fixture

SMALL = [dict(aj.BASE), {**aj.BASE, 'max_depth': 2}, {**aj.BASE, 'n_estimators': 50}]


class AjusteTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        excel_fixture(Path(self.directory.name) / 'd.xlsx', rows=120)
        self.excel = Path(self.directory.name) / 'd.xlsx'
        self.frame = load(self.excel)

    def tearDown(self):
        self.directory.cleanup()

    def test_grid_is_small_and_contains_base(self):
        self.assertEqual(len(aj.GRID), 108)
        self.assertIn(aj.key(aj.BASE), {aj.key(p) for p in aj.GRID})
        self.assertFalse([n for n in aj.FEATURE_NAMES if n.startswith('POST_')])

    def test_truncated_rounds_match_a_model_trained_with_fewer_trees(self):
        x, y = aj.features(self.frame), self.frame[aj.TARGET].astype(int).to_numpy()
        long = aj.fit_xgb(x, y, {**aj.BASE, 'n_estimators': 150})
        short = aj.fit_xgb(x, y, {**aj.BASE, 'n_estimators': 50})
        np.testing.assert_allclose(aj.predict(long, x, 50), aj.predict(short, x), rtol=1e-5)

    def test_selection_prefers_simpler_on_ties(self):
        y = np.array([0, 0, 1, 1])
        oof = {aj.key(p): np.array([.1, .2, .8, .9]) for p in aj.GRID}
        best = aj.select(oof, y)
        self.assertEqual((best['max_depth'], best['n_estimators']), (2, 50))

    def test_calibration_is_monotone_and_bounded(self):
        rng = np.random.default_rng(1)
        raw = rng.uniform(0, 1, 200)
        y = (rng.uniform(0, 1, 200) < raw / 3).astype(int)
        sig, iso = aj.calibrators(raw, y)
        grid = np.linspace(0, 1, 50)
        for f in (sig, iso):
            out = f(grid)
            self.assertTrue(((out >= 0) & (out <= 1)).all())
            self.assertTrue((np.diff(out) >= -1e-12).all())

    def test_nested_uses_only_outer_training_and_reports_choices(self):
        seen = []
        original = aj.inner_oof

        def spy(x, y, groups, seed, folds=4):
            seen.append(set(groups))
            return original(x, y, groups, seed, folds)

        with patch.object(aj, 'GRID', SMALL), patch.object(aj, 'inner_oof', spy):
            data, y, groups, runs, chosen = aj.nested(self.frame, repetitions=1)
        self.assertEqual(len(chosen), 5)
        all_students = set(groups)
        for students in seen:
            self.assertLess(len(students), len(all_students))
        self.assertTrue({aj.key(c) for c in chosen} <= {aj.key(p) for p in SMALL})
        for name in aj.PROB_MODELS:
            scores = runs[name][0][0]
            self.assertTrue(((scores >= 0) & (scores <= 1)).all())
        summary, pairs = aj.summarize(y, groups, runs, boots=50)
        decision = aj.decide(pairs, summary)
        self.assertIn('adoptar_ajustado', decision)
        self.assertIn('xgboost_ajustado - xgboost_base', pairs)


if __name__ == '__main__':
    unittest.main()
