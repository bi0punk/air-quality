#!/usr/bin/env python3
from pathlib import Path
import argparse

from app.db import init_db
from app.legacy_import import import_legacy_csv, import_legacy_sqlite


def main() -> None:
    parser = argparse.ArgumentParser(description='Importa datos de proyectos legacy al proyecto unificado.')
    parser.add_argument('--csv', type=Path, help='Ruta a datos_calidad_aire.csv')
    parser.add_argument('--sqlite', type=Path, help='Ruta a mq135.db')
    args = parser.parse_args()

    init_db()
    total = 0
    if args.csv:
        total += import_legacy_csv(args.csv)
    if args.sqlite:
        total += import_legacy_sqlite(args.sqlite)
    print(f'Importación finalizada. Registros importados: {total}')


if __name__ == '__main__':
    main()
