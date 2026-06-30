"""
sincronizar_activities.py - Proyecto NOAH (Postgres)
======================================================
Funciones de cálculo puro usadas por sincronizar_garmin.py para
clasificar y procesar actividades de Garmin (running/cycling/swimming).

Esta versión NO toca la base de datos directamente (a diferencia de la
version vieja que leia un Activities.csv y escribia en SQLite). Solo
calcula TSS, pace, tipo de sesion, IF, etc. a partir de los datos que
ya trae sincronizar_garmin.py desde la API de Garmin.

Las funciones de aqui:
  TIPO_A_SPORT       - mapeo de tipos de actividad de Garmin -> sport NOAH
  DEPORTES_VALIDOS   - set de deportes que se guardan en sesiones
  procesar_running   - calcula campos derivados para una sesion de running
  procesar_cycling   - calcula campos derivados para una sesion de cycling
  procesar_swimming  - calcula campos derivados para una sesion de swimming
  asegurar_columnas  - agrega columnas extra a `sesiones` si faltan (Postgres)
"""

import pandas as pd


# ── Mapeo tipos Garmin -> sport NOA ───────────────────────────────────────────
TIPO_A_SPORT = {
    'Carrera':                    'running',
    'Entrenamiento en cinta':     'running',
    'Senderismo':                 'running',
    'Ciclismo':                   'cycling',
    'Ciclismo en sala':           'cycling',
    'Ciclismo de montaña':        'cycling',
    'Natación en piscina':        'swimming',
    'Natación en aguas abiertas': 'swimming',
    'Multideporte':               'multisport',
    'Triatlón':                   'multisport',
    'Entreno de fuerza':          'strength',
    'HIIT':                       'hiit',
    'Caminar':                    'other',
    'Otros':                      'other',
}

# Deportes que se sincronizan a sesiones (ignoramos strength, other, etc.)
DEPORTES_VALIDOS = {'running', 'cycling', 'swimming'}


# ── Helpers de conversión ─────────────────────────────────────────────────────

def limpiar_float(v):
    if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() in ('--', '', 'None'):
        return None
    try:
        return float(str(v).replace(',', '.').replace(' ', ''))
    except ValueError:
        return None

def limpiar_int(v):
    f = limpiar_float(v)
    return int(f) if f is not None else None

def hms_a_min(v):
    """'01:27:00' -> 87.0 minutos"""
    if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() in ('--', ''):
        return None
    parts = str(v).strip().split(':')
    try:
        if len(parts) == 3:
            return int(parts[0]) * 60 + int(parts[1]) + float(parts[2]) / 60
        elif len(parts) == 2:
            return int(parts[0]) + float(parts[1]) / 60
    except ValueError:
        pass
    return None

def ritmo_a_pace(v, es_swim=False):
    """
    Running: '5:53' -> 5.883 (min/km)
    Swim:    '1:54' -> pace en min/100m
    """
    if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() in ('--', ''):
        return None
    parts = str(v).strip().split(':')
    try:
        if len(parts) == 2:
            return int(parts[0]) + int(parts[1]) / 60
    except ValueError:
        pass
    return None

def distancia_swim_km(v):
    """Swim: '2,500' metros -> 2.5 km"""
    f = limpiar_float(v)
    if f is None:
        return None
    if f > 100:
        return round(f / 1000, 3)
    return round(f, 3)

def calcular_tss_hr(hr_avg, duration_min, lthr):
    """TSS estimado por HR cuando no hay potencia"""
    if not hr_avg or not duration_min or not lthr:
        return None
    IF = hr_avg / lthr
    return round(IF ** 2 * (duration_min / 60) * 100, 2)

def calcular_tss_potencia(np_w, ftp, duration_min):
    """TSS por potencia normalizada (cycling)"""
    if not np_w or not ftp or not duration_min:
        return None
    IF = np_w / ftp
    return round(IF ** 2 * (duration_min / 60) * 100, 2)

def detectar_tipo_sesion_run(pace, hr_avg, lthr, n_vueltas):
    """Clasifica el tipo de sesión de running"""
    if not pace or not hr_avg or not lthr:
        return 'continuo'
    intensidad = hr_avg / lthr
    if intensidad < 0.80:
        return 'recuperacion'
    elif intensidad < 0.88:
        return 'continuo'
    elif intensidad < 0.95:
        return 'tempo'
    else:
        return 'intervalos'

def detectar_tipo_sesion_bike(hr_avg, lthr, np_w, ftp):
    if ftp and np_w:
        if_val = np_w / ftp
        if if_val < 0.65: return 'endurance'
        elif if_val < 0.80: return 'tempo'
        elif if_val < 0.90: return 'umbral'
        else: return 'vo2max'
    if hr_avg and lthr:
        r = hr_avg / lthr
        if r < 0.80: return 'endurance'
        elif r < 0.90: return 'tempo'
        else: return 'umbral'
    return 'continuo'

def detectar_tipo_sesion_swim(pace_100m, css):
    if not pace_100m:
        return 'continuo'
    if css:
        r = pace_100m / css
        if r > 1.15: return 'endurance'
        elif r > 1.05: return 'umbral'
        else: return 'vo2max'
    return 'continuo'


def calcular_IF(sport: str, np_w=None, ftp=None,
                pace=None, sftp_pace=None,
                css=None, pace_swim=None):
    """
    Calcula el Intensity Factor según el deporte.

    Bike:   IF = NP / FTP
    Run:    IF = NGP / sFTP  (pace normalizado / pace de umbral en min/km)
            Como pace es inverso a velocidad: IF = sFTP / NGP
            (pace más bajo = más rápido = mayor IF)
    Swim:   IF = CSS / pace_swim
            (CSS = ritmo crítico en min/100m)
    """
    if sport == 'cycling':
        if np_w and ftp and ftp > 0:
            return round(np_w / ftp, 3)
    elif sport == 'running':
        if pace and sftp_pace and sftp_pace > 0 and pace > 0:
            return round(sftp_pace / pace, 3)
    elif sport == 'swimming':
        if pace_swim and css and css > 0 and pace_swim > 0:
            return round(css / pace_swim, 3)
    return None


# ── Procesar una actividad (fila/dict con campos tipo Garmin) ────────────────

def procesar_running(row, atleta_cfg: dict) -> dict:
    lthr      = atleta_cfg.get('lthr_run', 162)
    hr_avg    = limpiar_int(row.get('Frecuencia cardiaca media'))
    dur_min   = hms_a_min(row.get('Tiempo'))
    dist_km   = limpiar_float(row.get('Distancia'))
    pace      = ritmo_a_pace(row.get('Ritmo medio'))
    n_vueltas = limpiar_int(row.get('Número de vueltas'))

    tss_garmin = limpiar_float(row.get('Training Stress Score®'))
    tss = tss_garmin if (tss_garmin and tss_garmin > 0) else calcular_tss_hr(hr_avg, dur_min, lthr)

    tipo = detectar_tipo_sesion_run(pace, hr_avg, lthr, n_vueltas)

    speed = round(dist_km / (dur_min / 60), 2) if dist_km and dur_min else None

    sftp_pace = atleta_cfg.get('sftp_pace')
    if_val = calcular_IF('running', pace=round(pace, 3) if pace else None, sftp_pace=sftp_pace)

    return {
        'sport':            'running',
        'distance_km':      round(dist_km, 3) if dist_km else None,
        'duration_min':     round(dur_min, 2) if dur_min else None,
        'hr_avg':           hr_avg,
        'hr_max':           limpiar_int(row.get('FC máxima')),
        'pace':             round(pace, 3) if pace else None,
        'speed_kmh':        speed,
        'tss_total':        tss,
        'tss_z12':          round(tss * 0.45, 2) if tss else None,
        'tss_z34':          round(tss * 0.45, 2) if tss else None,
        'tss_z56':          round(tss * 0.10, 2) if tss else None,
        'tipo_sesion':      tipo,
        'session_type':     tipo,
        'n_laps':           n_vueltas,
        'ascenso_m':        limpiar_int(row.get('Ascenso total')),
        'calorias':         limpiar_int(row.get('Calorías')),
        'te_aerobico':      limpiar_float(row.get('TE aeróbico')),
        'intensity_factor': if_val,
        'fuente':           'garmin_csv',
    }


def procesar_cycling(row, atleta_cfg: dict) -> dict:
    lthr_bike = atleta_cfg.get('lthr_bike', 150)
    ftp       = atleta_cfg.get('ftp_bike')
    peso      = atleta_cfg.get('peso_kg', 75) or 75
    hr_avg    = limpiar_int(row.get('Frecuencia cardiaca media'))
    dur_min   = hms_a_min(row.get('Tiempo'))
    np_w      = limpiar_int(row.get('Normalized Power® (NP®)'))
    pot_media = limpiar_int(row.get('Potencia media'))
    pot_max   = limpiar_int(row.get('Potencia máxima'))
    dist_raw  = limpiar_float(row.get('Distancia'))
    n_vueltas = limpiar_int(row.get('Número de vueltas'))

    dist_km = round(dist_raw, 3) if dist_raw and dist_raw > 0.1 else None

    ftp_efectivo = ftp or (round(np_w * 0.95) if np_w and np_w > 50 else None)

    tss_garmin = limpiar_float(row.get('Training Stress Score®'))
    tss = tss_garmin if (tss_garmin and tss_garmin > 0) else calcular_tss_potencia(np_w, ftp_efectivo, dur_min)
    if not tss:
        tss = calcular_tss_hr(hr_avg, dur_min, lthr_bike)

    tipo = detectar_tipo_sesion_bike(hr_avg, lthr_bike, np_w, ftp_efectivo)
    speed = round(dist_km / (dur_min / 60), 2) if dist_km and dur_min else None

    wkg = round(pot_media / peso, 2) if pot_media and peso else None

    if_val = calcular_IF('cycling', np_w=np_w, ftp=ftp_efectivo)

    return {
        'sport':          'cycling',
        'distance_km':    dist_km,
        'duration_min':   round(dur_min, 2) if dur_min else None,
        'hr_avg':         hr_avg,
        'hr_max':         limpiar_int(row.get('FC máxima')),
        'pace':           None,
        'speed_kmh':      speed,
        'tss_total':      tss,
        'tss_z12':        round(tss * 0.40, 2) if tss else None,
        'tss_z34':        round(tss * 0.45, 2) if tss else None,
        'tss_z56':        round(tss * 0.15, 2) if tss else None,
        'tipo_sesion':    tipo,
        'session_type':   tipo,
        'n_laps':         n_vueltas,
        'np_watts':       np_w,
        'potencia_media': pot_media,
        'potencia_max':   pot_max,
        'wkg':            wkg,
        'intensity_factor': if_val,
        'calorias':       limpiar_int(row.get('Calorías')),
        'te_aerobico':    limpiar_float(row.get('TE aeróbico')),
        'fuente':         'garmin_csv',
    }


def procesar_swimming(row, atleta_cfg: dict) -> dict:
    lthr_run  = atleta_cfg.get('lthr_run', 162)
    lthr_swim = atleta_cfg.get('lthr_swim') or round(lthr_run * 0.92)
    css       = atleta_cfg.get('css_100m', 1.75)
    hr_avg    = limpiar_int(row.get('Frecuencia cardiaca media'))
    dur_min   = hms_a_min(row.get('Tiempo'))
    dist_km   = distancia_swim_km(row.get('Distancia'))
    pace_100m = ritmo_a_pace(row.get('Ritmo medio'), es_swim=True)
    paladas   = limpiar_int(row.get('Paladas totales'))
    swolf     = limpiar_float(row.get('Swolf medio'))
    n_vueltas = limpiar_int(row.get('Número de vueltas'))

    tss_garmin = limpiar_float(row.get('Training Stress Score®'))
    tss = tss_garmin if (tss_garmin and tss_garmin > 0) else calcular_tss_hr(hr_avg, dur_min, lthr_swim)

    tipo = detectar_tipo_sesion_swim(pace_100m, css)

    speed = round((dist_km * 1000) / dur_min, 2) if dist_km and dur_min else None
    if_val = calcular_IF('swimming', css=css, pace_swim=pace_100m)

    return {
        'sport':            'swimming',
        'distance_km':      dist_km,
        'duration_min':     round(dur_min, 2) if dur_min else None,
        'hr_avg':           hr_avg,
        'hr_max':           limpiar_int(row.get('FC máxima')),
        'pace':             round(pace_100m, 3) if pace_100m else None,
        'speed_kmh':        speed,
        'tss_total':        tss,
        'tss_z12':          round(tss * 0.50, 2) if tss else None,
        'tss_z34':          round(tss * 0.40, 2) if tss else None,
        'tss_z56':          round(tss * 0.10, 2) if tss else None,
        'tipo_sesion':      tipo,
        'session_type':     tipo,
        'n_laps':           n_vueltas,
        'paladas':          paladas,
        'swolf':            swolf,
        'intensity_factor': if_val,
        'calorias':         limpiar_int(row.get('Calorías')),
        'te_aerobico':      limpiar_float(row.get('TE aeróbico')),
        'fuente':           'garmin_csv',
    }


# ── Migracion Postgres (equivalente al PRAGMA viejo de SQLite) ───────────────

def asegurar_columnas(conn):
    """
    Agrega columnas extra a `sesiones` si no existen (Postgres).
    Usa el helper compartido de db_compat (information_schema.columns)
    en vez del PRAGMA table_info de la version SQLite original.
    """
    from db_compat import asegurar_columnas as _aseg
    _aseg(conn, 'sesiones', [
        ('hr_max',           'INTEGER'),
        ('np_watts',         'INTEGER'),
        ('potencia_media',   'INTEGER'),
        ('potencia_max',     'INTEGER'),
        ('wkg',              'REAL'),
        ('paladas',          'INTEGER'),
        ('swolf',            'REAL'),
        ('ascenso_m',        'INTEGER'),
        ('calorias',         'INTEGER'),
        ('te_aerobico',      'REAL'),
        ('intensity_factor', 'REAL'),
    ])
