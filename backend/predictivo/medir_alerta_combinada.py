"""Cuenta la alerta combinada a fin de cada mes en 2021-2025, según abandono confirmado. Solo lectura de la base.

Retrospectivo y circular: el abandono se definió con la asistencia. Las gestiones pasadas usan el modelo entrenado sin ellas.
Uso (desde backend): python -m predictivo.medir_alerta_combinada
"""
import json
from calendar import monthrange
from collections import Counter
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from database import engine
from predictivo import perfil as pf, seguimiento as sg
import models as m

SALIDA = Path(__file__).resolve().parents[2] / 'docs' / 'alerta_combinada_por_mes.json'
GESTIONES = range(2021, 2026)


def medir():
    meses = {}
    with Session(engine) as db:
        abandonos = set(db.scalars(select(m.SituacionEscolar.matricula_id).where(m.SituacionEscolar.tipo == 'ABANDONO_CONFIRMADO')))
        for mes in range(2, 11):
            grupos = {'abandonaron': Counter(), 'continuaron': Counter()}
            for g in GESTIONES:
                for a in sg.calcular(db, g, date(g, mes, monthrange(g, mes)[1]))['alertas']:
                    grupos['abandonaron' if a['matricula_id'] in abandonos else 'continuaron'][a['perfil']['nivel']] += 1
            meses[sg.NOMBRE_MES[mes]] = {k: {n: c[n] for n in pf.NIVELES} for k, c in grupos.items()}
            print(sg.NOMBRE_MES[mes], meses[sg.NOMBRE_MES[mes]], flush=True)
    return meses


if __name__ == '__main__':
    SALIDA.write_text(json.dumps(dict(version=sg.VERSION, generado=date.today().isoformat(), gestiones=list(GESTIONES), meses=medir()),
        ensure_ascii=False, indent=1), encoding='utf8')
