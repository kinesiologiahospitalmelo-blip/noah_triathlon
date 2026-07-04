"""
agregar_columnas_umbrales.py
------------------------------
Agrega a la tabla `atletas` las columnas necesarias para guardar los
umbrales reales (de Garmin y calculados por NOAH desde el historial),
con su fecha de actualizacion. Se corre una sola vez.
"""
import os
import psycopg2

db_url = os.environ.get('DATABASE_URL')
if not db_url:
    print('Falta DATABASE_URL')
    raise SystemExit(1)

conn = psycopg2.connect(db_url)
conn.autocommit = True
cur = conn.cursor()

columnas = [
    ('lthr_run_garmin',        'REAL'),
    ('pace_umbral_run_garmin', 'REAL'),   # min/km
    ('ftp_bike_garmin',        'REAL'),
    ('fecha_umbral_garmin',    'TEXT'),

    ('lthr_run_calculado',        'REAL'),
    ('pace_umbral_run_calculado', 'REAL'),
    ('ftp_bike_calculado',        'REAL'),
    ('fecha_umbral_calculado',    'TEXT'),

    ('pace_umbral_run', 'REAL'),  # valor FINAL ya resuelto (garmin o calculado)
]

cur.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_schema='public' AND table_name='atletas'
""")
existentes = {r[0] for r in cur.fetchall()}

agregadas = 0
for col, tipo in columnas:
    if col not in existentes:
        cur.execute(f'ALTER TABLE atletas ADD COLUMN {col} {tipo}')
        agregadas += 1
        print(f'  + {col} ({tipo})')
    else:
        print(f'  = {col} ya existia')

conn.close()
print(f'\nColumnas agregadas: {agregadas}')
