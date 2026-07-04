import sys
sys.path.insert(0, '.')
from app import get_conn

conn = get_conn()

nuevas_columnas = [
    ('ground_contact_ms',    'REAL'),
    ('vertical_osc_mm',      'REAL'),
    ('stride_length_m',      'REAL'),
    ('vertical_ratio',       'REAL'),
    ('ground_balance',       'REAL'),
    ('performance_cond',     'INTEGER'),
    ('respiration_rate',     'REAL'),
    ('left_right_pct',       'REAL'),
    ('pedal_smoothness',     'REAL'),
    ('torque_effectiveness', 'REAL'),
    ('spo2_pct',             'REAL'),
]

existentes = set(r[0] for r in conn.execute(
    "SELECT column_name FROM information_schema.columns "
    "WHERE table_schema='public' AND table_name='activity_samples'"
).fetchall())

print("Columnas actuales en activity_samples:", sorted(existentes))
print()

agregadas = []
for col, tipo in nuevas_columnas:
    if col not in existentes:
        conn.execute(f'ALTER TABLE activity_samples ADD COLUMN {col} {tipo}')
        agregadas.append(col)
        print(f"OK - columna '{col}' agregada ({tipo})")
    else:
        print(f"-- columna '{col}' ya existe, skip")

conn.commit()
conn.close()

print()
if agregadas:
    print(f"LISTO - {len(agregadas)} columnas nuevas agregadas a activity_samples")
else:
    print("LISTO - activity_samples ya tenia todas las columnas")
