# noah_vo2.py — Eficiencia metabólica (VO2max) y su correlación con biomarcadores
# -----------------------------------------------------------------------------
# Idea central (Rodri): mostrarle al atleta que el VO2max NO mejora solo por
# entrenar mucho. Si los biomarcadores (HANNA / estado autonómico) están bajos,
# el cuerpo no asimila el estímulo y el VO2 se estanca o cae. Correlacionamos la
# tendencia del VO2max con el nivel de biomarcadores y con el training_status de
# Garmin. Solo lee datos ya guardados (garmin_performance + sleep_hrv); no toca
# ningún algoritmo validado.
# -----------------------------------------------------------------------------
from datetime import date

_TS_LABEL = {
    'PRODUCTIVE':   'Productivo',
    'MAINTAINING':  'Manteniendo',
    'RECOVERY':     'Recuperando',
    'UNPRODUCTIVE': 'Improductivo',
    'OVERREACHING': 'Sobrecarga',
    'DETRAINING':   'Desentrenando',
    'PEAKING':      'En pico',
    'NO_STATUS':    'Sin estado',
}


def _tendencia(serie, ventana):
    """Media de los últimos `ventana` vs la media de los `ventana` previos."""
    vals = [v for _, v in serie if v is not None]
    if len(vals) < 4:
        return None
    rec = vals[-ventana:]
    prev = vals[-2 * ventana:-ventana] or vals[:-ventana]
    if not rec or not prev:
        return None
    return round(sum(rec) / len(rec) - sum(prev) / len(prev), 2)


def get_vo2_analisis(conn, atleta_id, dias=120):
    """Serie de VO2max alineada con biomarcadores + lectura de correlación."""
    import pandas as pd

    perf = pd.read_sql(
        "SELECT fecha, vo2max, training_status, load_balance "
        "FROM garmin_performance WHERE atleta_id=%s AND vo2max IS NOT NULL "
        "ORDER BY fecha DESC LIMIT %s",
        conn, params=[atleta_id, dias])
    if perf.empty:
        return {'disponible': False}

    perf = perf.sort_values('fecha')
    bio = pd.read_sql(
        "SELECT fecha, hanna_life, estado_autonomico "
        "FROM sleep_hrv WHERE atleta_id=%s ORDER BY fecha DESC LIMIT %s",
        conn, params=[atleta_id, dias])
    bio = bio.sort_values('fecha') if not bio.empty else bio

    # Merge por fecha (left: fechas con VO2)
    if not bio.empty:
        df = perf.merge(bio, on='fecha', how='left')
    else:
        df = perf.copy()
        df['hanna_life'] = None
        df['estado_autonomico'] = None

    serie = [{
        'fecha':  str(r['fecha'])[:10],
        'vo2':    float(r['vo2max']) if r['vo2max'] is not None else None,
        'hanna':  float(r['hanna_life']) if pd.notna(r['hanna_life']) else None,
        'cuerpo': float(r['estado_autonomico']) if pd.notna(r['estado_autonomico']) else None,
    } for _, r in df.iterrows()]

    vo2_serie = [(s['fecha'], s['vo2']) for s in serie]
    ult = perf.iloc[-1]
    vo2_actual = float(ult['vo2max'])
    ts_raw = ult['training_status']
    ts = _TS_LABEL.get(ts_raw, (ts_raw or '').title() or None)

    t30 = _tendencia(vo2_serie, 30)
    t90 = _tendencia(vo2_serie, 90)

    # ── Correlación VO2 ↔ biomarcadores ──────────────────────────────────────
    # Días con biomarcador alto vs bajo, y cómo se movió el VO2 en cada grupo.
    bio_vals = [s['cuerpo'] if s['cuerpo'] is not None else s['hanna'] for s in serie]
    pares = [(v, b) for v, b in zip([s['vo2'] for s in serie], bio_vals)
             if v is not None and b is not None]

    lectura = None
    corr = None
    if len(pares) >= 8:
        import numpy as np
        vo2_arr = np.array([p[0] for p in pares], dtype=float)
        bio_arr = np.array([p[1] for p in pares], dtype=float)
        # Cambio de VO2 día a día vs nivel de biomarcador del día previo
        dvo2 = np.diff(vo2_arr)
        bio_prev = bio_arr[:-1]
        if len(dvo2) >= 6 and np.std(bio_prev) > 0 and np.std(dvo2) > 0:
            corr = round(float(np.corrcoef(bio_prev, dvo2)[0, 1]), 2)
        # Subida media de VO2 cuando el biomarcador estaba alto vs bajo
        umbral_alto = float(np.percentile(bio_prev, 60))
        umbral_bajo = float(np.percentile(bio_prev, 40))
        d_alto = dvo2[bio_prev >= umbral_alto]
        d_bajo = dvo2[bio_prev <= umbral_bajo]
        delta_alto = round(float(d_alto.mean()), 3) if len(d_alto) else None
        delta_bajo = round(float(d_bajo.mean()), 3) if len(d_bajo) else None
        lectura = _redactar_lectura(t30, delta_alto, delta_bajo, corr, ts_raw)

    return {
        'disponible':      True,
        'vo2_actual':      vo2_actual,
        'vo2_fecha':       str(ult['fecha'])[:10],
        'training_status': ts,
        'training_status_raw': ts_raw,
        'load_balance':    ult['load_balance'],
        'tendencia_30d':   t30,
        'tendencia_90d':   t90,
        'correlacion':     corr,
        'serie':           serie,
        'lectura':         lectura,
    }


def _redactar_lectura(t30, delta_alto, delta_bajo, corr, ts_raw):
    """Texto concreto con la idea: el VO2 asimila cuando los biomarcadores
    acompañan; si están bajos, no sube por más que entrenes."""
    sube = (t30 or 0) > 0.3
    baja = (t30 or 0) < -0.3
    acompania = (delta_alto is not None and delta_bajo is not None
                 and delta_alto > delta_bajo + 0.02)

    if acompania and sube:
        tono, txt = 'ok', ('Tu VO2 mejora y lo hace sobre todo cuando tus biomarcadores '
                           'están altos: el estímulo está rindiendo porque el cuerpo asimila.')
    elif acompania and not sube:
        tono, txt = 'warn', ('Cuando tus biomarcadores están altos tu VO2 sube, pero últimamente '
                             'no vienen acompañando. No es falta de entrenamiento: el cuerpo no '
                             'está asimilando. Priorizá recuperar antes de sumar carga.')
    elif baja:
        tono, txt = 'warn', ('Tu VO2 viene cayendo. Revisá si estás entrenando con los '
                             'biomarcadores bajos — más carga ahí no sube el VO2, lo frena.')
    else:
        tono, txt = 'neutral', ('Tu VO2 se mantiene estable. La clave para que suba es entrenar '
                                'fuerte cuando los biomarcadores te acompañan, no cuando están bajos.')

    if ts_raw in ('OVERREACHING', 'UNPRODUCTIVE'):
        txt += ' Garmin marca el entrenamiento como poco productivo, lo que refuerza esta lectura.'
    return {'tono': tono, 'texto': txt,
            'delta_alto': delta_alto, 'delta_bajo': delta_bajo}
