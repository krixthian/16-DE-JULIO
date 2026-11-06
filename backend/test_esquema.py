"""El diseño de la base (models.py), el script SQL y el diagrama Mermaid deben coincidir: 28 tablas, 47 FK, 40 CHECK."""
import re
import unittest
from pathlib import Path

from sqlalchemy import CheckConstraint

import models as m

ROOT = Path(__file__).resolve().parents[1]


def foreign_keys():
    return {(fk.referred_table.name, t.name, ', '.join(fk.column_keys)) for t in m.Base.metadata.tables.values()
        for fk in t.foreign_key_constraints}


class EsquemaTests(unittest.TestCase):
    def test_models_match_thesis_counts(self):
        tables = m.Base.metadata.tables.values()
        self.assertEqual(len(tables), 28)
        self.assertEqual(len(foreign_keys()), 47)
        self.assertEqual(sum(isinstance(c, CheckConstraint) for t in tables for c in t.constraints), 40)

    def test_sql_script_matches_models(self):
        sql = (ROOT / 'database_schema_actual.sql').read_text(encoding='utf-8')
        self.assertEqual(set(re.findall(r'CREATE TABLE (\w+) \(', sql)), set(m.Base.metadata.tables))
        self.assertEqual(sql.count('FOREIGN KEY'), 47)
        self.assertEqual(sql.count('CHECK ('), 40)

    def test_mermaid_diagram_has_every_foreign_key(self):
        mmd = (ROOT / 'docs' / 'diagrama_relaciones.mmd').read_text(encoding='utf-8')
        relations = set(re.findall(r'^\s*(\w+) \|\|--o[|{] (\w+) : "([\w, ]+)"', mmd, re.M))
        self.assertEqual(relations, foreign_keys())

    def test_proposed_adjustment_is_not_destructive(self):
        script = (ROOT / 'docs' / 'AJUSTE_ESQUEMA_PROPUESTO.sql').read_text(encoding='utf-8')
        active = '\n'.join(line for line in script.splitlines() if not line.lstrip().startswith('--'))
        self.assertNotRegex(active.upper(), r'\b(DROP|DELETE|TRUNCATE|ALTER\s+TABLE|UPDATE)\b')
        self.assertEqual(active.count('CREATE INDEX'), 3)


if __name__ == '__main__':
    unittest.main()
