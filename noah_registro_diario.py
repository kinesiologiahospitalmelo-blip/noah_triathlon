# noah_registro_diario.py — Registro diario del atleta (NOAH)
# -----------------------------------------------------------------------------
# Captura la "verdad subjetiva" y la carga que el reloj no ve, SIN tocar los
# algoritmos validados (riesgo viral, ACWR, monotonía, HANNA LIFE):
#
#   • Check-in de 5 caras  -> confirma lo que HANNA muestra (aprendizaje futuro).
#   • Toggle de fuerza/cross-> registra carga complementaria por sRPE (sesión x
#                              RPE). Se guarda APARTE; no modifica el TSS/CTL/ATL
#                              de Garmin que usan ACWR y monotonía.
#   • Ciclo menstrual       -> para atletas femeninas (hoy 3/4/5 y las que vengan).
#
# Todo vive en Postgres (vía db_compat.ConexionCompat, placeholders %s).
# -----------------------------------------------------------------------------
from datetime import date, timedelta

_TABLES_OK = False


def asegurar_tablas(conn):
    """Crea las tablas si no existen. Idempotente y barato."""
    global _TABLES_OK
    if _TABLES_OK:
        return
    conn.execute("""
        CREATE TABLE IF NOT EXISTS registro_diario (
            atleta_id   INTEGER NOT NULL,
            fecha       TEXT    NOT NULL,
            checkin_cara    INTEGER,         -- 1..5 (1 muy mal, 5 muy bien)
            fuerza          INTEGER,         -- 0/1 entrenó fuerza
            cross_tipo      VARCHAR(40),     -- 'crossfit','gym','hyrox','otro', NULL
            fuerza_rpe      INTEGER,         -- 1..10 (opcional)
            fuerza_min      INTEGER,         -- duración en minutos (opcional)
            srpe            REAL,            -- carga complementaria = rpe * min
            nota            TEXT,
            created_at  TIMESTAMP DEFAULT NOW(),
            updated_at  TIMESTAMP DEFAULT NOW(),
            PRIMARY KEY (atleta_id, fecha)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ciclo_menstrual (
            id          SERIAL PRIMARY KEY,
            atleta_id   INTEGER NOT NULL,
            fecha_inicio TEXT   NOT NULL,     -- primer día del período
            duracion_dias INTEGER,           -- días de sangrado (opcional)
            sintomas    TEXT,                 -- lista separada por comas (opcional)
            nota        TEXT,
            created_at  TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    _TABLES_OK = True


# ── Registro diario: check-in + fuerza ────────────────────────────────────────
def guardar_checkin(conn, atleta_id, cara, fecha=None, nota=None):
    """Guarda (o actualiza) el check-in de 5 caras del día."""
    asegurar_tablas(conn)
    fecha = fecha or str(date.today())
    cara = int(cara)
    if cara < 1 or cara > 5:
        raise ValueError('cara fuera de rango (1..5)')
    conn.execute("""
        INSERT INTO registro_diario (atleta_id, fecha, checkin_cara, nota, updated_at)
        VALUES (%s, %s, %s, %s, NOW())
        ON CONFLICT (atleta_id, fecha) DO UPDATE
          SET checkin_cara = EXCLUDED.checkin_cara,
              nota = COALESCE(EXCLUDED.nota, registro_diario.nota),
              updated_at = NOW()
    """, (atleta_id, fecha, cara, nota))
    conn.commit()
    return {'ok': True, 'fecha': fecha, 'checkin_cara': cara}


def guardar_fuerza(conn, atleta_id, fuerza, cross_tipo=None,
                   rpe=None, minutos=None, fecha=None):
    """Registra si entrenó fuerza/cross hoy. Calcula sRPE (carga complementaria)
    solo si hay rpe y minutos; no toca el TSS validado."""
    asegurar_tablas(conn)
    fecha = fecha or str(date.today())
    fuerza = 1 if fuerza else 0
    rpe = int(rpe) if rpe not in (None, '') else None
    minutos = int(minutos) if minutos not in (None, '') else None
    srpe = float(rpe * minutos) if (fuerza and rpe and minutos) else (0.0 if not fuerza else None)
    conn.execute("""
        INSERT INTO registro_diario
            (atleta_id, fecha, fuerza, cross_tipo, fuerza_rpe, fuerza_min, srpe, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (atleta_id, fecha) DO UPDATE
          SET fuerza     = EXCLUDED.fuerza,
              cross_tipo = EXCLUDED.cross_tipo,
              fuerza_rpe = EXCLUDED.fuerza_rpe,
              fuerza_min = EXCLUDED.fuerza_min,
              srpe       = EXCLUDED.srpe,
              updated_at = NOW()
    """, (atleta_id, fecha, fuerza, cross_tipo, rpe, minutos, srpe))
    conn.commit()
    return {'ok': True, 'fecha': fecha, 'fuerza': bool(fuerza), 'srpe': srpe}


def get_registro(conn, atleta_id, fecha=None):
    """Registro del día (check-in + fuerza) + carga complementaria de 7 días."""
    asegurar_tablas(conn)
    fecha = fecha or str(date.today())
    row = conn.execute("""
        SELECT checkin_cara, fuerza, cross_tipo, fuerza_rpe, fuerza_min, srpe, nota
        FROM registro_diario WHERE atleta_id=%s AND fecha=%s
    """, (atleta_id, fecha)).fetchone()

    desde = str(date.fromisoformat(fecha) - timedelta(days=6))
    comp = conn.execute("""
        SELECT COALESCE(SUM(srpe), 0), COUNT(*) FILTER (WHERE fuerza=1)
        FROM registro_diario
        WHERE atleta_id=%s AND fecha BETWEEN %s AND %s
    """, (atleta_id, desde, fecha)).fetchone()

    return {
        'fecha':         fecha,
        'checkin_cara':  row[0] if row else None,
        'fuerza':        bool(row[1]) if row and row[1] is not None else None,
        'cross_tipo':    row[2] if row else None,
        'fuerza_rpe':    row[3] if row else None,
        'fuerza_min':    row[4] if row else None,
        'srpe':          row[5] if row else None,
        'nota':          row[6] if row else None,
        'srpe_semana':   float(comp[0]) if comp and comp[0] is not None else 0.0,
        'sesiones_fuerza_semana': int(comp[1]) if comp and comp[1] is not None else 0,
    }


# ── Ciclo menstrual ───────────────────────────────────────────────────────────
_FASES = {
    'menstrual': {
        'label': 'Menstrual',
        'nota':  'Energía puede estar baja. Priorizá sesiones suaves si lo necesitás; '
                 'no hay contraindicación para entrenar si te sentís bien.',
    },
    'folicular': {
        'label': 'Folicular',
        'nota':  'Suele ser la fase de mejor tolerancia a la carga y a la intensidad. '
                 'Buen momento para bloques fuertes o tests.',
    },
    'ovulatoria': {
        'label': 'Ovulatoria',
        'nota':  'Pico de fuerza y potencia en muchas atletas. Atención a la laxitud '
                 'articular en gestos explosivos.',
    },
    'lutea': {
        'label': 'Lútea',
        'nota':  'Puede subir la FC y la percepción de esfuerzo. Hidratación y descanso '
                 'cuentan más; ajustá expectativas si aparece el síndrome premenstrual.',
    },
}


def _fases_desde(dia_ciclo, largo):
    """Clasifica la fase por día del ciclo. Ovulación estimada en largo-14."""
    if dia_ciclo is None:
        return None
    ovul = max(11, largo - 14)
    if dia_ciclo <= 5:
        return 'menstrual'
    if dia_ciclo < ovul - 1:
        return 'folicular'
    if ovul - 1 <= dia_ciclo <= ovul + 1:
        return 'ovulatoria'
    return 'lutea'


def guardar_ciclo(conn, atleta_id, fecha_inicio, duracion=None,
                  sintomas=None, nota=None):
    asegurar_tablas(conn)
    conn.execute("""
        INSERT INTO ciclo_menstrual (atleta_id, fecha_inicio, duracion_dias, sintomas, nota)
        VALUES (%s, %s, %s, %s, %s)
    """, (atleta_id, fecha_inicio,
          int(duracion) if duracion not in (None, '') else None,
          sintomas, nota))
    conn.commit()
    return {'ok': True, 'fecha_inicio': fecha_inicio}


def get_ciclo(conn, atleta_id, fecha=None):
    """Estado del ciclo: fase actual, día, próximo período estimado e historial.
    Si no hay registros, devuelve disponible=False (el frontend ofrece cargar)."""
    asegurar_tablas(conn)
    hoy = date.fromisoformat(fecha) if fecha else date.today()

    rows = conn.execute("""
        SELECT fecha_inicio, duracion_dias, sintomas, nota
        FROM ciclo_menstrual WHERE atleta_id=%s ORDER BY fecha_inicio DESC LIMIT 12
    """, (atleta_id,)).fetchall()

    historial = [{
        'fecha_inicio': str(r[0])[:10],
        'duracion_dias': r[1],
        'sintomas': r[2],
        'nota': r[3],
    } for r in rows]

    if not rows:
        return {'disponible': False, 'historial': []}

    inicios = sorted([date.fromisoformat(str(r[0])[:10]) for r in rows])
    # Largo del ciclo: mediana de los gaps entre inicios (si hay 2+), si no 28.
    gaps = [(inicios[i + 1] - inicios[i]).days for i in range(len(inicios) - 1)]
    gaps = [g for g in gaps if 18 <= g <= 45]  # descartar outliers
    if gaps:
        gaps_ord = sorted(gaps)
        m = len(gaps_ord) // 2
        largo = gaps_ord[m] if len(gaps_ord) % 2 else round((gaps_ord[m - 1] + gaps_ord[m]) / 2)
    else:
        largo = 28

    ultimo = inicios[-1]
    dia_ciclo = (hoy - ultimo).days + 1
    # Si ya pasó más de un ciclo sin registrar, estimamos el día dentro del ciclo.
    if dia_ciclo > largo:
        dia_ciclo = ((hoy - ultimo).days % largo) + 1
    fase = _fases_desde(dia_ciclo, largo)
    prox = ultimo + timedelta(days=largo)
    while prox < hoy:
        prox = prox + timedelta(days=largo)
    dias_para_prox = (prox - hoy).days

    info = _FASES.get(fase, {})
    return {
        'disponible':      True,
        'dia_ciclo':       dia_ciclo,
        'largo_ciclo':     largo,
        'fase':            fase,
        'fase_label':      info.get('label'),
        'fase_nota':       info.get('nota'),
        'ultimo_inicio':   str(ultimo),
        'proximo_inicio':  str(prox),
        'dias_para_proximo': dias_para_prox,
        'historial':       historial,
    }
