import sys
sys.path.insert(0, '.')
from app import get_conn

conn = get_conn()

# Columnas que noah_streams.py necesita en activity_samples
# (nombres exactos de migrate_db y leer_samples_db en noah_streams.py)
columnas_correctas = [
    ('temperature_c',  'REAL'),
    ('vert_osc_mm',    'REAL'),
    ('gct_ms',         'REAL'),
    ('gct_balance',    'REAL'),
    ('stride_cm',      'REAL'),
    ('vert_ratio',     'REAL'),
    ('respiration',    'REAL'),
    ('stress',         'INTEGER'),
    ('power_acc_j',    'REAL'),
    ('ts_s_mov',       'INTEGER'),
    ('stroke_type',    'INTEGER'),
    ('cadence_swim',   'INTEGER'),
]

existentes = set(r[0] for r in conn.execute(
    "SELECT column_name FROM information_schema.columns "
    "WHERE table_schema='public' AND table_name='activity_samples'"
).fetchall())

print("Columnas actuales:", sorted(existentes))
print()

agregadas = []
for col, tipo in columnas_correctas:
    if col not in existentes:
        conn.execute(f'ALTER TABLE activity_samples ADD COLUMN {col} {tipo}')
        agregadas.append(col)
        print(f"OK - '{col}' agregada ({tipo})")
    else:
        print(f"-- '{col}' ya existe, skip")

conn.commit()
conn.close()

print()
if agregadas:
    print(f"LISTO - {len(agregadas)} columnas agregadas con nombres correctos")
else:
    print("LISTO - todas las columnas ya existian")
