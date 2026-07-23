"""
sincronizar_wahoo.py
------------------------
Baja entrenamientos de Wahoo (via su Cloud API oficial) y los guarda
en la tabla sesiones, reutilizando EXACTAMENTE las mismas funciones
de calculo de TSS/zonas que ya usa Garmin (procesar_running,
procesar_cycling, procesar_swimming de sincronizar_activities.py).

Requiere que el atleta ya haya conectado su cuenta de Wahoo (boton
"Conectar con Wahoo" en su perfil) -- usa el token guardado en la
tabla wahoo_tokens.

USO (en la raiz del repo, con DATABASE_URL, WAHOO_CLIENT_ID y
WAHOO_CLIENT_SECRET seteadas):
    python sincronizar_wahoo.py --atleta_id 4
"""

import os
import sys
import argparse
from datetime import datetime, timedelta

try:
    import requests
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("Falta alguna libreria. Instalar con:")
    print("  pip install requests psycopg2-binary --break-system-packages")
    sys.exit(1)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sincronizar_activities import procesar_running, procesar_cycling, procesar_swimming
from sincronizar_garmin import _seg_a_hms, _pace_a_str, _guardar_streams
from noa_db import NOADatabase

try:
    import fitparse
except ImportError:
    fitparse = None


def _parsear_fit_samples(fit_bytes):
    from io import BytesIO
    fitfile = fitparse.FitFile(BytesIO(fit_bytes))
    samples = []
    t0 = None
    for record in fitfile.get_messages('record'):
        vals = {d.name: d.value for d in record if d.value is not None}
        ts = vals.get('timestamp')
        if ts is None:
            continue
        if t0 is None:
            t0 = ts
        ts_s = int((ts - t0).total_seconds())

        lat_raw = vals.get('position_lat')
        lon_raw = vals.get('position_long')
        lat = lat_raw * (180 / 2**31) if lat_raw is not None else None
        lon = lon_raw * (180 / 2**31) if lon_raw is not None else None

        samples.append({
            'ts_s': ts_s,
            'hr': vals.get('heart_rate'),
            'speed_ms': vals.get('enhanced_speed') or vals.get('speed'),
            'cadence': vals.get('cadence'),
            'altitude_m': vals.get('enhanced_altitude') or vals.get('altitude'),
            'distance_m': vals.get('distance'),
            'lat': lat,
            'lon': lon,
            'temperature': vals.get('temperature'),
            'power_w': vals.get('power'),
            'gct_ms': vals.get('stance_time'),
            'vert_osc_mm': vals.get('vertical_oscillation'),
            'stride_cm': None,
            'vert_ratio': vals.get('vertical_ratio'),
            'gct_balance': vals.get('stance_time_balance'),
            'stress': None,
            'respiration': None,
            'left_right_pct': vals.get('left_right_balance'),
            'pedal_smoothness': vals.get('combined_pedal_smoothness'),
            'torque_effectiveness': (vals.get('combined_torque_effectiveness')
                                      or vals.get('left_torque_effectiveness')),
            'spo2_pct': None,
        })
    return samples


def _parsear_fit_laps(fit_bytes):
    from io import BytesIO
    fitfile = fitparse.FitFile(BytesIO(fit_bytes))
    laps_raw = []
    for i, lap in enumerate(fitfile.get_messages('lap'), start=1):
        vals = {d.name: d.value for d in lap if d.value is not None}
        dur_min  = (vals.get('total_elapsed_time') or 0) / 60
        dist_km  = (vals.get('total_distance') or 0) / 1000
        pace     = (dur_min / dist_km) if dist_km > 0.01 else None
        laps_raw.append({
            'lap_num':      i,
            'duration_min': round(dur_min, 2),
            'distance_km':  round(dist_km, 3),
            'hr_avg':       vals.get('avg_heart_rate'),
            'hr_max':       vals.get('max_heart_rate'),
            'pace':         round(pace, 3) if pace else None,
            'avg_power':    vals.get('avg_power'),
            'max_power':    vals.get('max_power'),
            'norm_power':   vals.get('normalized_power'),
            'avg_speed':    round((vals.get('enhanced_avg_speed') or vals.get('avg_speed') or 0) * 3.6, 2) or None,
            'max_speed':    round((vals.get('enhanced_max_speed') or vals.get('max_speed') or 0) * 3.6, 2) or None,
            'cadence':      vals.get('avg_cadence'),
            'work_kj':      round(vals.get('total_work')/1000, 2) if vals.get('total_work') else None,
            'temperature':  vals.get('avg_temperature'),
            'lap_tss':      None,
            'lap_if':       None,
            'w_balance':    None,
        })
    return laps_raw


def _bajar_laps_y_streams_wahoo(conn, db, atleta_id, sesion_id, fecha, file_url, headers):
    if not fitparse:
        print("    [AVISO] Falta instalar fitparse (pip install fitparse --break-system-packages) -- se salta laps/streams.")
        return
    if not file_url:
        return
    try:
        # FIX: el CDN de archivos de Wahoo (tipo S3) RECHAZA el header
        # "Authorization: Bearer ..." (ese token es solo para la API de
        # Wahoo, no para el CDN) -- la url del archivo ya es autosuficiente.
        r = requests.get(file_url, timeout=30)
        if r.status_code != 200:
            print(f"    [AVISO] No se pudo bajar el .FIT: {r.status_code} {r.text[:200]}")
            return
        fit_bytes = r.content

        laps_raw = _parsear_fit_laps(fit_bytes)
        if laps_raw:
            n = db.agregar_laps(atleta_id, sesion_id, fecha, laps_raw)
            print(f"    [OK] {n} laps")

        samples = _parsear_fit_samples(fit_bytes)
        if samples:
            n = _guardar_streams(conn, atleta_id, sesion_id, f'wahoo_{sesion_id}', samples)
            print(f"    [OK] Streams: {n} muestras")

            try:
                from guardar_biomarcadores import calcular_y_guardar_biomarcadores
                sport_row = conn.execute(
                    'SELECT sport FROM sesiones WHERE id=%s', (sesion_id,)
                ).fetchone()
                sport = sport_row[0] if sport_row else None
                ftp_watts = None
                if sport == 'cycling':
                    row_ftp = conn.execute(
                        'SELECT ftp_watts FROM atletas WHERE id=%s', (atleta_id,)
                    ).fetchone()
                    ftp_watts = row_ftp[0] if row_ftp else None
                calcular_y_guardar_biomarcadores(conn, sesion_id, sport, samples, ftp_watts=ftp_watts)
            except Exception as e_bio:
                print(f"    [AVISO] No se pudieron calcular biomarcadores: {e_bio}")
    except Exception as e:
        print(f"    [AVISO] Error bajando laps/streams: {e}")

WAHOO_TOKEN_URL = 'https://api.wahooligan.com/oauth/token'
WAHOO_API_BASE  = 'https://api.wahooligan.com/v1'

WORKOUT_TYPE_A_SPORT = {
    0: 'cycling', 11: 'cycling', 12: 'cycling', 13: 'cycling', 14: 'cycling',
    15: 'cycling', 16: 'cycling', 17: 'cycling', 49: 'cycling', 61: 'cycling',
    64: 'cycling', 68: 'cycling', 70: 'cycling',
    1: 'running', 3: 'running', 4: 'running', 5: 'running', 67: 'running',
    71: 'running',
    25: 'swimming', 26: 'swimming',
}


def get_conn():
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("Falta la variable de entorno DATABASE_URL.")
        sys.exit(1)
    from db_compat import ConexionCompat
    return ConexionCompat(psycopg2.connect(db_url, cursor_factory=psycopg2.extras.DictCursor))


def _asegurar_columna_wahoo_id(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name='sesiones' AND column_name='wahoo_workout_id'
    """)
    if not cur.fetchone():
        cur.execute("ALTER TABLE sesiones ADD COLUMN wahoo_workout_id TEXT")
        conn.commit()
        print("  [OK] Columna wahoo_workout_id agregada a sesiones.")


def obtener_access_token(conn, atleta_id):
    cur = conn.cursor()
    cur.execute("SELECT access_token, refresh_token, expires_at FROM wahoo_tokens WHERE atleta_id=%s", (atleta_id,))
    row = cur.fetchone()
    if not row:
        print(f"  [ERROR] Atleta {atleta_id} no tiene Wahoo conectado todavia.")
        return None

    # Chequear si el token todavia es valido
    try:
        expires_at = datetime.fromisoformat(row['expires_at'])
    except (ValueError, TypeError):
        expires_at = datetime.utcnow()  # forzar refresh si el formato esta roto

    if datetime.utcnow() < expires_at - timedelta(minutes=5):
        # Token todavia vigente — verificar que realmente funciona
        # (puede haber sido invalidado por otra autorizacion)
        test = requests.get(f'{WAHOO_API_BASE}/user', headers={
            'Authorization': f'Bearer {row["access_token"]}'
        }, timeout=10)
        if test.status_code == 200:
            return row['access_token']
        print(f"  [AVISO] Token dice vigente pero Wahoo lo rechazo ({test.status_code}). Refrescando...")

    # Refrescar token
    print("  Token vencido o invalido, refrescando...")
    client_id = os.environ.get('WAHOO_CLIENT_ID')
    client_secret = os.environ.get('WAHOO_CLIENT_SECRET')
    if not client_id or not client_secret:
        print("  [ERROR] Faltan WAHOO_CLIENT_ID o WAHOO_CLIENT_SECRET en las variables de entorno.")
        return None

    r = requests.post(WAHOO_TOKEN_URL, data={
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'refresh_token',
        'refresh_token': row['refresh_token'],
    }, timeout=15)

    if r.status_code != 200:
        error_body = r.text[:300]
        print(f"  [ERROR] Wahoo rechazo el refresh_token: {r.status_code} {error_body}")
        if 'invalid_grant' in error_body.lower() or r.status_code == 401:
            print("  [!!] El refresh_token ya no es valido. Probable causa: autorizacion")
            print("       duplicada en Wahoo, o el atleta revoco el acceso.")
            print("       -> El atleta debe re-conectar Wahoo desde su perfil en NOAH.")
            # Marcar el token como invalido para no seguir intentando
            cur.execute(
                "UPDATE wahoo_tokens SET access_token='INVALIDO', expires_at=%s WHERE atleta_id=%s",
                (datetime.utcnow().isoformat(), atleta_id)
            )
            conn.commit()
        return None

    tok = r.json()
    nuevo_access  = tok.get('access_token')
    nuevo_refresh = tok.get('refresh_token')
    expires_in    = tok.get('expires_in', 7200)
    nueva_exp = (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat()

    if not nuevo_access:
        print(f"  [ERROR] Wahoo respondio OK pero no devolvio access_token: {tok}")
        return None

    cur.execute(
        "UPDATE wahoo_tokens SET access_token=%s, refresh_token=%s, expires_at=%s, actualizado=%s WHERE atleta_id=%s",
        (nuevo_access, nuevo_refresh, nueva_exp, datetime.utcnow().isoformat(), atleta_id)
    )
    conn.commit()
    print("  [OK] Token refrescado correctamente.")
    return nuevo_access


def sincronizar(atleta_id, max_paginas=5):
    conn = get_conn()
    _asegurar_columna_wahoo_id(conn)
    db = NOADatabase(os.environ.get('DATABASE_URL'))

    access_token = obtener_access_token(conn, atleta_id)
    if not access_token:
        return

    atleta = conn.execute(
        "SELECT lthr_run, lthr_bike, lthr_swim, ftp_watts, css_100m, pace_umbral_run, peso_kg "
        "FROM atletas WHERE id=%s", (atleta_id,)
    ).fetchone()
    if not atleta:
        print(f"No existe el atleta {atleta_id}")
        return
    atleta_cfg = dict(atleta)
    atleta_cfg['sftp_pace'] = atleta_cfg.get('pace_umbral_run')

    headers = {'Authorization': f'Bearer {access_token}'}
    guardadas = 0

    for pagina in range(1, max_paginas + 1):
        r = requests.get(f'{WAHOO_API_BASE}/workouts', headers=headers,
                          params={'page': pagina, 'per_page': 30})
        if r.status_code != 200:
            print(f"  Error bajando workouts (pagina {pagina}): {r.status_code} {r.text}")
            break

        data = r.json()
        workouts = data.get('workouts', [])
        if not workouts:
            break

        for w in workouts:
            summary = w.get('workout_summary')
            if not summary:
                continue

            # FIX: reconectar antes de cada workout -- la conexion se corta
            # durante la descarga del .FIT (puede tardar varios segundos)
            try:
                conn.close()
            except Exception:
                pass
            conn = get_conn()

            wahoo_id = str(w.get('id'))
            existe = conn.execute(
                'SELECT id FROM sesiones WHERE atleta_id=%s AND wahoo_workout_id=%s',
                (atleta_id, wahoo_id)).fetchone()
            if existe:
                continue

            sport = WORKOUT_TYPE_A_SPORT.get(w.get('workout_type_id'))
            if not sport:
                continue

            fecha = (w.get('starts') or '')[:10]
            if not fecha:
                continue

            dur_seg   = float(summary.get('duration_active_accum') or 0)
            dist_m    = float(summary.get('distance_accum') or 0)
            speed_avg = float(summary.get('speed_avg') or 0)

            dur_pausada_seg = float(summary.get('duration_paused_accum') or 0)
            work_j = float(summary.get('work_accum') or 0)

            row = {
                'Tiempo':                    _seg_a_hms(dur_seg),
                'Distancia':                 str(round(dist_m / 1000, 4)) if sport != 'swimming' else str(dist_m),
                'Frecuencia cardiaca media': str(summary.get('heart_rate_avg') or ''),
                'FC máxima':                 '',
                'Ritmo medio':               _pace_a_str(speed_avg, sport),
                'Training Stress Score®':    str(summary.get('power_bike_tss_last') or 0),
                'Calorías':                  str(summary.get('calories_accum') or ''),
                'TE aeróbico':               '',
                'Número de vueltas':         '',
                'Normalized Power® (NP®)':  str(summary.get('power_bike_np_last') or ''),
                'Potencia media':            str(summary.get('power_avg') or ''),
                'Potencia máxima':           '',
                'Paladas totales':           '',
                'Swolf medio':               '',
                'Ascenso total':             str(summary.get('ascent_accum') or ''),
                'Cadencia media':            str(summary.get('cadence_avg') or ''),
                'Tiempo pausado':            _seg_a_hms(dur_pausada_seg) if dur_pausada_seg else '',
                'Trabajo total':             str(round(work_j / 1000, 2)) if work_j else '',
            }

            if sport == 'running':    datos = procesar_running(row, atleta_cfg)
            elif sport == 'cycling':  datos = procesar_cycling(row, atleta_cfg)
            elif sport == 'swimming': datos = procesar_swimming(row, atleta_cfg)
            else: continue

            datos['fuente'] = 'wahoo'

            cols = ['atleta_id', 'fecha', 'wahoo_workout_id'] + list(datos.keys())
            vals = [atleta_id, fecha, wahoo_id] + list(datos.values())
            cur = conn.cursor()
            try:
                cur.execute(
                    f"INSERT INTO sesiones ({','.join(cols)}) VALUES ({','.join(['%s']*len(cols))}) RETURNING id",
                    vals)
                sesion_id = cur.fetchone()[0]
                conn.commit()
                guardadas += 1
                print(f"  [OK] {sport.upper()} {fecha} TSS {datos.get('tss_total','?')}")

                file_url = summary.get('file', {}).get('url') if isinstance(summary.get('file'), dict) else None
                _bajar_laps_y_streams_wahoo(conn, db, atleta_id, sesion_id, fecha, file_url, headers)
            except Exception as e:
                conn.rollback()
                if 'unique' in str(e).lower() or 'duplicate' in str(e).lower():
                    print(f"  [SALTEADO] {sport.upper()} {fecha} -- ya existe una sesion de otro origen ese dia")
                else:
                    print(f"  [ERROR] {sport.upper()} {fecha}: {e}")

        if data.get('page', pagina) * data.get('per_page', 30) >= data.get('total', 0):
            break

    print(f"\n  Total guardadas: {guardadas}")
    conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--atleta_id', type=int, required=True)
    ap.add_argument('--paginas', type=int, default=5)
    args = ap.parse_args()
    sincronizar(args.atleta_id, max_paginas=args.paginas)


if __name__ == '__main__':
    main()
