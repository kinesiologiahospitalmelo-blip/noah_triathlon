"""
migrate_twin.py — Crea tabla para que el Twin guarde, compare y aprenda.

Correr una sola vez:
  python migrate_twin.py
"""
import os, psycopg2

DB = os.environ.get('DATABASE_URL',
    'postgresql://postgres.jbsggrkzudeiekgmwcel:noah_triatlon'
    '@aws-1-us-west-2.pooler.supabase.com:6543/postgres')

conn = psycopg2.connect(DB)
cur = conn.cursor()

cur.execute('''
CREATE TABLE IF NOT EXISTS twin_predicciones (
    id              SERIAL PRIMARY KEY,
    atleta_id       INTEGER NOT NULL,
    fecha_gen       DATE NOT NULL DEFAULT CURRENT_DATE,
    semana_iso      VARCHAR(10) NOT NULL,

    -- Escenario generado
    escenario_rank  INTEGER,
    plan            JSONB,
    tss_predicho    FLOAT,
    riesgo_predicho FLOAT,
    score_predicho  FLOAT,
    elegido         BOOLEAN DEFAULT FALSE,

    -- Evaluación post-semana (se llena después)
    evaluado        BOOLEAN DEFAULT FALSE,
    tss_real        FLOAT,
    delta_perf_real FLOAT,
    hrv_ok          BOOLEAN,
    absorcion_ok    BOOLEAN,
    acierto         FLOAT,
    fecha_eval      DATE,

    UNIQUE(atleta_id, semana_iso, escenario_rank)
);

CREATE INDEX IF NOT EXISTS idx_twin_pred_atleta ON twin_predicciones(atleta_id, semana_iso);
''')

conn.commit()
print('✓ Tabla twin_predicciones creada')

# Verificar
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='twin_predicciones' ORDER BY ordinal_position")
cols = [r[0] for r in cur.fetchall()]
print(f'  Columnas: {cols}')

conn.close()
