# noah_calibracion.py — NOAH · Aprendizaje: percepción del atleta vs HANNA
# -----------------------------------------------------------------------------
# Cierra el círculo del modelo: el check-in de 5 caras (verdad subjetiva) se
# compara con lo que HANNA marcó ese día. Mide concordancia y sesgo por atleta y
# devuelve una lectura. Es la base para afinar HANNA con datos reales de cada
# persona — SIN tocar los algoritmos validados: acá solo se MIDE el acuerdo, no
# se modifica ningún número de HANNA.
#
# Mapa de caras (1..5) a escala 0-100 comparable con HANNA:
#   1 muy mal=10 · 2 flojo=30 · 3 normal=50 · 4 bien=70 · 5 muy bien=90
# -----------------------------------------------------------------------------
from datetime import date

CARA_A_SCORE = {1: 10, 2: 30, 3: 50, 4: 70, 5: 90}


def get_calibracion(conn, atleta_id, dias=90):
    """Compara el check-in subjetivo con HANNA. Devuelve métricas + lectura."""
    import pandas as pd
    import numpy as np

    chk = pd.read_sql(
        "SELECT fecha, checkin_cara FROM registro_diario "
        "WHERE atleta_id=%s AND checkin_cara IS NOT NULL ORDER BY fecha DESC LIMIT %s",
        conn, params=[atleta_id, dias])
    if chk.empty:
        return {'disponible': False, 'n': 0,
                'msg': 'Todavía no hay check-ins. Cada vez que registrás cómo te sentís, '
                       'NOAH aprende a leerte mejor.'}

    bio = pd.read_sql(
        "SELECT fecha, hanna_life, estado_autonomico FROM sleep_hrv "
        "WHERE atleta_id=%s AND hanna_life IS NOT NULL ORDER BY fecha DESC LIMIT %s",
        conn, params=[atleta_id, dias * 2])

    if bio.empty:
        return {'disponible': False, 'n': int(len(chk)),
                'msg': 'Hay check-ins pero todavía no suficientes datos de HANNA para comparar.'}

    df = chk.merge(bio, on='fecha', how='inner')
    df = df[df['checkin_cara'].notna() & df['hanna_life'].notna()]
    n = int(len(df))
    if n < 4:
        return {'disponible': False, 'n': n,
                'msg': f'Van {n} check-ins con HANNA al lado. Con unos pocos más ya te puedo '
                       f'mostrar qué tan afinada está la lectura para vos.'}

    subj = df['checkin_cara'].map(CARA_A_SCORE).astype(float).values
    hanna = df['hanna_life'].astype(float).values

    bias = float(np.mean(subj - hanna))            # + = se siente mejor que HANNA
    # Concordancia: ambos del mismo lado del punto medio (ambos "bien" o "bajo")
    concord = float(np.mean(np.sign(subj - 50) == np.sign(hanna - 50))) * 100
    corr = None
    if n >= 8 and np.std(subj) > 0 and np.std(hanna) > 0:
        corr = round(float(np.corrcoef(subj, hanna)[0, 1]), 2)

    lectura = _redactar(n, bias, concord, corr)
    return {
        'disponible':  True,
        'n':           n,
        'concordancia': round(concord),
        'sesgo':       round(bias, 1),
        'correlacion': corr,
        'tono':        lectura['tono'],
        'msg':         lectura['texto'],
        'titulo':      lectura['titulo'],
    }


def _redactar(n, bias, concord, corr):
    # Sesgo fuerte = el atleta siente distinto a lo que HANNA marca
    if concord >= 70 and abs(bias) <= 12:
        return {'tono': 'ok', 'titulo': 'HANNA te está leyendo bien',
                'texto': f'Tu percepción coincide con HANNA el {concord:.0f}% de las veces. '
                         f'El modelo está calibrado para vos — cuando marca bajo, lo sentís.'}
    if bias >= 15:
        return {'tono': 'azul', 'titulo': 'Te sentís mejor de lo que marca HANNA',
                'texto': f'En promedio te sentís {bias:+.0f} puntos por encima de HANNA. '
                         f'Puede que toleres cargas que a otros los hunden, o que HANNA te '
                         f'esté sobre-penalizando algo. Seguimos registrando para ajustarlo a vos.'}
    if bias <= -15:
        return {'tono': 'warn', 'titulo': 'Te sentís peor de lo que marca HANNA',
                'texto': f'En promedio te sentís {bias:.0f} puntos por debajo de HANNA. '
                         f'Suele ser algo que el reloj no ve: estrés, mala alimentación, '
                         f'poco descanso real o el comienzo de una enfermedad. Vale la pena mirarlo.'}
    return {'tono': 'neutral', 'titulo': 'Afinando la lectura',
            'texto': f'Tu percepción y HANNA coinciden el {concord:.0f}% de las veces ({n} registros). '
                     f'Seguí marcando cómo te sentís: es justo eso lo que afina el modelo para vos.'}
