"""Ejecutar desde backend: python -m predictivo --help."""
import argparse
import csv
import json
from collections import Counter
from datetime import date
from pathlib import Path

from predictivo.features import VERSION, DESCRIPTIONS, FEATURE_NAMES, build_features, outcome, day
from predictivo.source import from_json, from_mysql, persist_cuts, register_model, digest, serialize


def prepare(tables, origin, month_day, observed_until):
    records = []
    for year in sorted(tables['gestiones'], key=lambda r: r['anio']):
        cutoff = date.fromisoformat(f"{year['anio']}-{month_day}")
        if cutoff > day(observed_until):
            continue
        rows = build_features(tables, cutoff, origin, year['id'])
        for row in rows:
            label, reason = outcome(tables, row, observed_until)
            # Fecha de disponibilidad de la etiqueta, nunca entrada del modelo.
            label_type = 'ABANDONO_CONFIRMADO' if label == 1 else 'CONTINUIDAD_CONFIRMADA'
            evidence = [s for s in tables['situaciones_escolares'] if s['matricula_id'] == row['matricula_id'] and s['tipo'] == label_type
                and day(s['fecha_efectiva']) <= day(row['horizonte']) and day(s['registrado_en']) <= day(observed_until)
                and day(s['observado_hasta']) <= day(observed_until)
                and (label == 1 or day(s['observado_hasta']) >= day(row['horizonte']))]
            available = min(max(day(s['registrado_en']), day(s['observado_hasta'])) for s in evidence).isoformat() if label is not None else None
            row.update(objetivo=label, motivo_etiqueta=reason, etiqueta_disponible_en=available)
        records.extend(rows)
    if not records:
        raise ValueError('No hay matrículas disponibles para este origen y corte.')
    return dict(version_variables=VERSION, origen=origin, corte_anual=month_day, observado_hasta=day(observed_until).isoformat(),
        fuente_sha256=digest(tables), registros=records,
        resumen={'registros': len(records), 'estados': dict(Counter(r['estado'] for r in records)),
            'etiquetas': dict(Counter(r['motivo_etiqueta'] for r in records)),
            'faltantes_por_variable': {k: sum(r['variables'][k] is None for r in records) for k in FEATURE_NAMES}})


def save_dataset(dataset, directory):
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=False)
    (out / 'dataset.json').write_text(json.dumps(dataset, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    meta = ['matricula_id', 'estudiante_id', 'gestion', 'origen', 'fecha_corte', 'estado', 'objetivo', 'motivo_etiqueta', 'etiqueta_disponible_en']
    with (out / 'indicadores.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=meta + FEATURE_NAMES)
        writer.writeheader()
        writer.writerows({**{k: r.get(k) for k in meta}, **r['variables']} for r in dataset['registros'])
    (out / 'diccionario.json').write_text(json.dumps(DESCRIPTIONS, indent=2, ensure_ascii=False), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description='Tareas 11 y 12: indicadores y modelo base. No activa predicciones.')
    commands = parser.add_subparsers(dest='command', required=True)
    prep = commands.add_parser('preparar', help='Preparar dataset, etiquetas y diccionario; no escribe en MySQL.')
    sources = prep.add_mutually_exclusive_group(required=True)
    sources.add_argument('--json', type=Path, help='JSON de tablas fuente, como el utilizado para generar el Excel simulado.')
    sources.add_argument('--mysql', action='store_true', help='Leer la conexión local configurada, sin modificarla.')
    prep.add_argument('--origen', choices=['REAL', 'SIMULADO'], required=True)
    prep.add_argument('--corte', default='03-31', help='Mes-día, por defecto 03-31.')
    prep.add_argument('--observado-hasta', type=date.fromisoformat, required=True)
    prep.add_argument('--salida', type=Path, required=True)
    train = commands.add_parser('entrenar', help='Entrenar XGBoost y guardar artefactos fuera de MySQL.')
    train.add_argument('--dataset', type=Path, required=True)
    train.add_argument('--gestion-evaluacion', type=int, required=True)
    train.add_argument('--salida', type=Path, required=True)
    cuts = commands.add_parser('cortes', help='Calcular desde MySQL; solo guarda con --guardar.')
    cuts.add_argument('--gestion-id', type=int, required=True)
    cuts.add_argument('--fecha', type=date.fromisoformat, required=True)
    cuts.add_argument('--origen', choices=['REAL', 'SIMULADO'], required=True)
    cuts.add_argument('--guardar', action='store_true')
    registry = commands.add_parser('registrar-modelo', help='Registrar metadatos; no activa el modelo ni genera alertas.')
    registry.add_argument('--directorio', type=Path, required=True)
    registry.add_argument('--umbral-medio', type=float, required=True)
    registry.add_argument('--umbral-alto', type=float, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'preparar':
            if args.observado_hasta > date.today():
                raise ValueError('La fecha de observación no puede ser futura.')
            if args.json:
                tables = from_json(args.json)
            else:
                from database import SessionLocal
                with SessionLocal() as db:
                    tables = from_mysql(db)
            dataset = prepare(tables, args.origen, args.corte, args.observado_hasta)
            save_dataset(dataset, args.salida)
            print(json.dumps(dataset['resumen'], ensure_ascii=False, indent=2))
        elif args.command == 'entrenar':
            from predictivo.training import train_baseline
            dataset = json.loads(args.dataset.read_text(encoding='utf-8-sig'))
            report = train_baseline(dataset, args.salida, args.gestion_evaluacion)
            print(json.dumps({k: report[k] for k in ('origen', 'entrenamiento', 'evaluacion', 'metricas', 'limitaciones')}, ensure_ascii=False, indent=2))
        elif args.command == 'cortes':
            if args.fecha > date.today():
                raise ValueError('No se permiten cortes futuros.')
            from database import SessionLocal
            with SessionLocal() as db:
                rows = build_features(from_mysql(db), args.fecha, args.origen, args.gestion_id)
                ids = persist_cuts(db, rows) if args.guardar else []
                if args.guardar:
                    db.commit()
                print(json.dumps({'registros': len(rows), 'estados': dict(Counter(r['estado'] for r in rows)), 'guardados': ids}, ensure_ascii=False))
        else:
            from database import SessionLocal
            report = json.loads((args.directorio / 'reporte.json').read_text(encoding='utf-8'))
            with SessionLocal() as db:
                model_id = register_model(db, report, args.directorio / 'modelo_xgboost.json', args.umbral_medio, args.umbral_alto)
                db.commit()
                print(json.dumps({'modelo_id': model_id, 'activado': False}))
    except (ValueError, FileExistsError, KeyError) as error:
        parser.exit(2, f'No se completó la operación: {error}\n')


if __name__ == '__main__':
    main()
