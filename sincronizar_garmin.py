import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
import json
"""
sincronizar_garmin.py - Proyecto NOAH v2
=========================================
Sincroniza datos completos de Garmin Connect para todos los atletas.

Descarga:
  ACTIVIDADES:
    - Resumen (TSS, HR, pace, potencia, calorías, TE aeróbico/anaeróbico)
    - Laps detallados (run/bike/swim)
    - Streams segundo a segundo (HR, velocidad, potencia, cadencia, altitud, GPS)
    - Métricas del summary (hrTimeInZone 1-5, activityTrainingLoad, splits rápidos)
    - Clima durante la actividad
  BIOMARCADORES:
    - HRV nocturno + estimado Nunan 2010
    - Sueño completo (fases, scores, series nocturnas)
    - Body Battery, Stress, FC reposo
    - SPO2 + Respiración nocturna
  MÉTRICAS DE RENDIMIENTO (diarias):
    - Training Status + VO2max actual
    - Race predictions (5k/10k/21k/42k)
    - Training load balance (agudo/crónico de Garmin)
    - Personal records
    - Respiration + SPO2 intraday

Modos de uso:
  python sincronizar_garmin.py                    # Todos los atletas, hoy
  python sincronizar_garmin.py --atleta 1         # Solo atleta 1
  python sincronizar_garmin.py --modo bio         # Solo biomarcadores
  python sincronizar_garmin.py --modo actividad   # Solo actividades
  python sincronizar_garmin.py --modo perf        # Solo métricas de rendimiento
  python sincronizar_garmin.py --fecha 2026-05-20 # Fecha específica
  python sincronizar_garmin.py --dias 7           # Últimos 7 días
  python sincronizar_garmin.py --config           # Configurar credenciales

Programación sugerida (Windows Task Scheduler):
  06:00 -> python sincronizar_garmin.py --modo bio
  21:00 -> python sincronizar_garmin.py --modo todo
  Domingo 08:00 -> python sincronizar_garmin.py --modo perf --dias 1
"""

import argparse
import psycopg2
import sys
import base64
import getpass
from datetime import date, timedelta, datetime, timezone
from pathlib import Path
from db_compat import asegurar_columnas as _asegurar_columnas_helper

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))


# ── Encriptación ──────────────────────────────────────────────────────────────
def _enc(t): return base64.b64encode(t.encode()).decode()
def _dec(c):
    try: return base64.b64decode(c.encode()).decode()
    except: return c


# ── Migración DB ──────────────────────────────────────────────────────────────
def asegurar_columnas(conn):
    # Columnas de atletas — PRAGMA table_info (SQLite) reemplazado por el
    # helper compartido (information_schema.columns en Postgres).
    _asegurar_columnas_helper(conn, 'atletas', [
        ('garmin_user',  'TEXT'), ('garmin_pass', 'TEXT'),
        ('garmin_token', 'TEXT'), ('ultima_sync',  'TEXT'),
    ])

    # Columnas de sesiones - para streams y métricas extra
    _asegurar_columnas_helper(conn, 'sesiones', [
        ('garmin_activity_id',    'TEXT'),
        ('activity_training_load','REAL'),
        ('aerobic_te',           'REAL'),
        ('anaerobic_te',         'REAL'),
        ('hr_zone_1_s',          'REAL'),
        ('hr_zone_2_s',          'REAL'),
        ('hr_zone_3_s',          'REAL'),
        ('hr_zone_4_s',          'REAL'),
        ('hr_zone_5_s',          'REAL'),
        ('fastest_1k',           'REAL'),   # segundos
        ('fastest_5k',           'REAL'),
        ('fastest_10k',          'REAL'),
        ('avg_stride_length',    'REAL'),   # cm
        ('water_estimated',      'REAL'),   # ml
        ('temperatura_avg',      'REAL'),
        ('has_streams',          'INTEGER DEFAULT 0'),
    ])

    # Tabla garmin_performance - métricas diarias de rendimiento
    conn.execute('''
        CREATE TABLE IF NOT EXISTS garmin_performance (
            id              SERIAL PRIMARY KEY,
            atleta_id       INTEGER NOT NULL,
            fecha           TEXT NOT NULL,
            vo2max          REAL,
            training_status TEXT,
            load_balance    TEXT,       -- "BALANCED", "HIGH_AEROBIC", etc
            acute_load      REAL,
            chronic_load    REAL,
            race_5k_s       REAL,       -- predicción en segundos
            race_10k_s      REAL,
            race_half_s     REAL,
            race_marathon_s REAL,
            respiration_avg REAL,
            respiration_min REAL,
            spo2_avg        REAL,
            spo2_min        REAL,
            creado          TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(atleta_id, fecha)
        )
    ''')

    # Tabla activity_samples - streams punto a punto
    conn.execute('''
        CREATE TABLE IF NOT EXISTS activity_samples (
            id           SERIAL PRIMARY KEY,
            atleta_id    INTEGER NOT NULL,
            sesion_id    INTEGER NOT NULL,
            garmin_id    TEXT,
            ts_s         REAL,
            hr           INTEGER,
            speed_ms     REAL,
            cadence      INTEGER,
            altitude_m   REAL,
            distance_m   REAL,
            lat          REAL,
            lon          REAL,
            temperature  REAL,
            power_w      INTEGER,
            UNIQUE(sesion_id, ts_s)
        )
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_samp_sesion ON activity_samples(sesion_id)')

    # Log de sync
    conn.execute('''
        CREATE TABLE IF NOT EXISTS sync_log (
            id        SERIAL PRIMARY KEY,
            atleta_id INTEGER, fecha TEXT, modo TEXT,
            status TEXT, detalle TEXT,
            ts TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()


# ── Cliente Garmin ────────────────────────────────────────────────────────────
def get_client(user: str, pwd_enc: str):
    from garminconnect import Garmin
    try:
        client = Garmin(user, _dec(pwd_enc))
        client.login()
        return client
    except Exception as e:
        raise RuntimeError(f'Login Garmin ({user}): {e}')


# ── Parsear streams de get_activity_details ───────────────────────────────────
def _parsear_streams(details: dict, sport: str) -> list:
    """
    Parsea la estructura real de Garmin:
      metricDescriptors: [{metricsIndex, key, unit: {factor}}]
      activityDetailMetrics: [{metrics: [v0, v1, ..., v14]}]
    """
    if not details:
        return []

    descriptors = details.get('metricDescriptors', [])
    raw_metrics  = details.get('activityDetailMetrics', [])
    if not descriptors or not raw_metrics:
        return []

    KEY_MAP = {
        'sumDistance':                      ('distance_m',          100.0),
        'sumDuration':                      ('ts_s',                1000.0),
        'directHeartRate':                  ('hr',                   1.0),
        'directSpeed':                      ('speed_ms',             0.1),
        'directEnhancedSpeed':              ('speed_ms',             0.1),
        'directDoubleCadence':              ('cad_double',           1.0),
        'directRunCadence':                 ('cad_run',              1.0),
        'directBikeCadence':                ('cadence',              1.0),
        'directElevation':                  ('altitude_m',          100.0),
        'directEnhancedAltitude':           ('altitude_m',          100.0),
        'directLatitude':                   ('lat',                  1.0),
        'directLongitude':                  ('lon',                  1.0),
        'directAirTemperature':             ('temperature_c',          1.0),
        'directPower':                      ('power_w',              1.0),
        'sumAccumulatedPower':              ('power_acc',            1.0),
        # Running — dynamics
        'directGroundContactTime':          ('gct_ms',   1.0),
        'directVerticalOscillation':        ('vert_osc_mm',     1.0),
        'directStrideLength':               ('stride_cm',  1000.0),
        'directVerticalRatio':              ('vert_ratio',      1.0),
        'directGroundContactBalance':       ('gct_balance',    100.0),
        'directPerformanceCondition':       ('stress',    1.0),
        'directRespirationRate':            ('respiration',    1.0),
        # Cycling — dynamics
        'directLeftRightBalance':           ('left_right_pct',      1.0),
        'directPedalSmoothness':            ('pedal_smoothness',    1.0),
        'directTorqueEffectiveness':        ('torque_effectiveness', 1.0),
        # General
        'directSaturatedHemoglobinPercent': ('spo2_pct',            1.0),
        'directFractionalHemoglobinSaturation': ('spo2_pct',        1.0),
    }

    idx_map = {}
    for d in descriptors:
        key  = d.get('key', '')
        idx  = d.get('metricsIndex', -1)
        if key in KEY_MAP:
            name, factor = KEY_MAP[key]
            idx_map[idx] = (name, factor)

    if not idx_map:
        return []

    samples_raw = []
    for item in raw_metrics:
        flat = item.get('metrics', [])
        if not flat:
            continue
        s = {}
        for idx, (name, factor) in idx_map.items():
            if idx < len(flat) and flat[idx] is not None:
                v = flat[idx]
                if factor < 1.0:
                    v = v * factor      # speed: raw * 0.1
                elif factor > 1.0:
                    v = v / factor      # dist: raw / 100
                s[name] = v
        if s:
            samples_raw.append(s)

    if not samples_raw:
        return []

    # Normalizar ts_s desde inicio
    ts_min = min(s.get('ts_s', 0) for s in samples_raw)
    samples = []
    for s in samples_raw:
        hr    = s.get('hr')
        speed = s.get('speed_ms')
        power = s.get('power')

        if hr    and not (30 <= hr <= 250):    hr    = None
        if speed and not (0  < speed <= 20):   speed = None
        if power and not (0  < power <= 3000): power = None

        if hr is None and speed is None and power is None:
            continue

        # Cadencia: preferir double (spm), sino run*2, sino bike
        cadence = None
        if s.get('cad_double'): cadence = int(s['cad_double'])
        elif s.get('cad_run'):  cadence = int(s['cad_run'] * 2)
        elif s.get('cadence'):  cadence = int(s['cadence'])

        samples.append({
            'ts_s':                round(s.get('ts_s', 0) - ts_min, 1),
            'hr':                  int(hr)         if hr    else None,
            'speed_ms':            round(speed, 3) if speed else None,
            'cadence':             cadence,
            'altitude_m':          round(s['altitude_m'], 1)   if s.get('altitude_m')   else None,
            'distance_m':          round(s['distance_m'], 1)   if s.get('distance_m')   else None,
            'lat':                 round(s['lat'], 6)           if s.get('lat')          else None,
            'lon':                 round(s['lon'], 6)           if s.get('lon')          else None,
            'temperature':         round(s['temperature'], 1)  if s.get('temperature')  else None,
            'power_w':             int(power)      if power else None,
            # Running dynamics
            'gct_ms':   round(s['gct_ms'], 1)    if s.get('gct_ms')   else None,
            'vert_osc_mm':     round(s['vert_osc_mm'], 1)      if s.get('vert_osc_mm')     else None,
            'stride_cm':     round(s['stride_cm'], 3)      if s.get('stride_cm')     else None,
            'vert_ratio':      round(s['vert_ratio'], 2)       if s.get('vert_ratio')      else None,
            'gct_balance':      round(s['gct_balance'], 1)       if s.get('gct_balance')      else None,
            'stress':    int(s['stress'])          if s.get('stress')    else None,
            'respiration':    round(s['respiration'], 1)     if s.get('respiration')    else None,
            # Cycling dynamics
            'left_right_pct':      round(s['left_right_pct'], 1)       if s.get('left_right_pct')      else None,
            'pedal_smoothness':    round(s['pedal_smoothness'], 1)     if s.get('pedal_smoothness')    else None,
            'torque_effectiveness':round(s['torque_effectiveness'], 1) if s.get('torque_effectiveness') else None,
            # General
            'spo2_pct':            round(s['spo2_pct'], 1)             if s.get('spo2_pct')            else None,
        })

    return samples


def _guardar_streams(conn, atleta_id, sesion_id, garmin_id, samples):
    saved = 0
    for s in samples:
        try:
            conn.execute('''
                INSERT INTO activity_samples
                (atleta_id, sesion_id, garmin_id, ts_s, hr, speed_ms,
                 cadence, altitude_m, distance_m, lat, lon, temperature, power_w,
                 ground_contact_ms, vertical_osc_mm, stride_length_m, vertical_ratio,
                 ground_balance, performance_cond, respiration_rate,
                 left_right_pct, pedal_smoothness, torque_effectiveness, spo2_pct)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (sesion_id, ts_s) DO NOTHING
            ''', (atleta_id, sesion_id, str(garmin_id),
                  s['ts_s'], s['hr'], s['speed_ms'], s['cadence'],
                  s['altitude_m'], s['distance_m'], s['lat'], s['lon'],
                  s['temperature'], s['power_w'],
                  s['gct_ms'], s['vert_osc_mm'], s['stride_cm'],
                  s['vert_ratio'], s['gct_balance'], s['stress'],
                  s['respiration'], s['left_right_pct'], s['pedal_smoothness'],
                  s['torque_effectiveness'], s['spo2_pct']))
            saved += 1
        except Exception:
            # Rollback OBLIGATORIO: este insert corre en un loop de
            # potencialmente cientos de samples — sin rollback, un solo
            # fallo deja la transacción abortada para todos los siguientes
            # en Postgres (a diferencia de SQLite).
            conn.rollback()
    if saved:
        conn.execute('UPDATE sesiones SET has_streams=1 WHERE id=%s', (sesion_id,))
    conn.commit()
    return saved


# ── Descargar biomarcadores ───────────────────────────────────────────────────
def _rmssd_desde_fc(fc: float, stress: float = None) -> float:
    import math
    if not fc or fc <= 0: return None
    rmssd = math.exp(5.5 - 0.05 * fc)
    if stress is not None:
        f = 1.10 if stress < 15 else 1.05 if stress < 25 else 1.00 if stress < 40 else 0.90 if stress < 55 else 0.80
        rmssd *= f
    return round(max(10, min(120, rmssd)), 1)


def descargar_bio(client, fecha_str: str, atleta_id: int,
                  conn, db) -> dict:
    resultado = {}

    # HRV
    try:
        hrv = client.get_hrv_data(fecha_str)
        if hrv:
            summ = hrv.get('hrvSummary') or {}
            v = summ.get('lastNight') or summ.get('weeklyAvg') or hrv.get('lastNight')
            if v: resultado['hrv_rmssd'] = v; print(f'    HRV: {v}ms')
    except Exception as e: print(f'    HRV: {e}')

    # Sueño
    try:
        sd = client.get_sleep_data(fecha_str)
        s  = (sd or {}).get('dailySleepDTO') or sd or {}
        if s:
            def seg2h(k): v=s.get(k,0); return round(v/3600,2) if v else None
            resultado.update({
                'sleep_h':  seg2h('sleepTimeSeconds') or seg2h('sleepDuration'),
                'deep_h':   seg2h('deepSleepSeconds') or seg2h('deepSleepDuration'),
                'rem_h':    seg2h('remSleepSeconds')  or seg2h('remSleepDuration'),
                'light_h':  seg2h('lightSleepSeconds'),
                'awake_h':  seg2h('awakeSleepSeconds') or seg2h('awakeDuration'),
            })
            scores = s.get('sleepScores') or {}
            overall = scores.get('overall') or {}
            resultado['sleep_score']    = overall.get('value') if isinstance(overall, dict) else overall
            resultado['sleep_feedback'] = (s.get('sleepScoreFeedback') or '').replace('POSITIVE_','').replace('NEGATIVE_','').lower() or None
            resultado['sleep_stress']   = s.get('avgSleepStress')
            resultado['awake_count']    = s.get('awakeCount')
            spo2s = s.get('spo2SleepSummary') or {}
            resultado['fc_nocturna'] = spo2s.get('averageHR') or s.get('averageHR')
            resultado['spo2_avg']    = spo2s.get('averageSPO2') or s.get('averageSPO2')
            resultado['spo2_min']    = spo2s.get('lowestSPO2')  or s.get('lowestSPO2')
            resultado['resp_avg']    = s.get('averageRespirationValue') or s.get('averageRespiration')
            resultado['resp_min']    = s.get('lowestRespirationValue')
            resultado['resp_max']    = s.get('highestRespirationValue')
            # Series nocturnas para HANNA_VFC
            hr_serie = [x['value'] for x in sd.get('sleepHeartRate', []) if x.get('value', 0) > 0]
            if hr_serie: resultado['sleep_hr_serie'] = hr_serie
            stress_serie = [x['value'] for x in sd.get('sleepStress', []) if x.get('value') is not None]
            if stress_serie:
                resultado['sleep_stress_serie'] = stress_serie
                resultado['sleep_stress_avg']   = round(sum(stress_serie)/len(stress_serie), 2)
            resp_serie = [x['respirationValue'] for x in sd.get('wellnessEpochRespirationDataDTOList', []) if x.get('respirationValue')]
            if resp_serie: resultado['resp_serie'] = resp_serie
            restless = sd.get('sleepMovement') or []
            resultado['restless_count'] = sum(1 for m in restless if m.get('activityLevel', 0) > 3) if restless else s.get('restlessMomentCount')
            if resultado.get('fc_nocturna') and not resultado.get('hrv_rmssd'):
                est = _rmssd_desde_fc(resultado['fc_nocturna'], resultado.get('sleep_stress'))
                if est: resultado['hrv_rmssd_estimado'] = est
            print(f"    Sueño: {resultado.get('sleep_h')}h · REM: {resultado.get('rem_h')}h · Score: {resultado.get('sleep_score')}")
    except Exception as e: print(f'    Sueño: {e}')

    # Body Battery
    try:
        bb = client.get_body_battery(fecha_str)
        if isinstance(bb, list) and bb:
            vals = []
            for item in bb:
                for par in item.get('bodyBatteryValuesArray', []):
                    if isinstance(par, list) and len(par) >= 2 and par[1] is not None:
                        vals.append(par[1])
                if item.get('charged'): vals.append(item['charged'])
            resultado['body_battery'] = max(vals) if vals else None
            print(f"    Body Battery: {resultado['body_battery']}")
    except Exception as e: print(f'    Body Battery: {e}')

    # FC reposo
    try:
        hr_data = client.get_rhr_day(fecha_str)
        rhr = None
        if hr_data:
            try:
                rhr = hr_data.get('allMetrics',{}).get('metricsMap',{}).get('WELLNESS_RESTING_HEART_RATE',[{}])[0].get('value')
            except Exception: pass
            if not rhr: rhr = (hr_data.get('allDayHR') or {}).get('restingHeartRate')
        resultado['hr_reposo'] = int(rhr) if rhr else None
        if resultado['hr_reposo']: print(f"    FC reposo: {resultado['hr_reposo']}bpm")
        if resultado.get('hr_reposo') and not resultado.get('hrv_rmssd') and not resultado.get('fc_nocturna'):
            est = _rmssd_desde_fc(resultado['hr_reposo'], resultado.get('sleep_stress'))
            if est: resultado['hrv_rmssd_estimado'] = est
    except Exception as e: print(f'    FC reposo: {e}')

    # Stress
    try:
        st = client.get_stress_data(fecha_str)
        if st: resultado['stress_avg'] = st.get('avgStressLevel'); print(f"    Stress: {resultado['stress_avg']}")
    except Exception as e: print(f'    Stress: {e}')

    # Guardar
    if resultado:
        hrv_ms = resultado.get('hrv_rmssd')
        hrv_ratio = hrv_flag = None
        if hrv_ms:
            try:
                import pandas as pd
                df = db.get_sleep_hrv(atleta_id, ultimos_dias=30)
                if len(df) >= 3:
                    baseline = df['hrv_rmssd'].dropna().tail(7).mean()
                    if baseline and not pd.isna(baseline):
                        hrv_ratio = round(hrv_ms / baseline, 3)
                        hrv_flag  = 'verde' if hrv_ratio >= 1.05 else 'amarillo' if hrv_ratio >= 0.95 else 'rojo'
            except Exception: pass
        hrv_final    = hrv_ms or resultado.get('hrv_rmssd_estimado')
        es_estimado  = (not hrv_ms) and bool(resultado.get('hrv_rmssd_estimado'))
        try:
            db.agregar_sleep(atleta_id, {
                'fecha': fecha_str, 'hrv_rmssd': hrv_final, 'hrv_ratio': hrv_ratio,
                'hrv_flag': hrv_flag, 'hrv_estimado': 1 if es_estimado else 0,
                'stress_avg': resultado.get('stress_avg'), 'sleep_stress': resultado.get('sleep_stress'),
                'body_battery': resultado.get('body_battery'), 'sleep_h': resultado.get('sleep_h'),
                'deep_h': resultado.get('deep_h'), 'rem_h': resultado.get('rem_h'),
                'light_h': resultado.get('light_h'), 'awake_h': resultado.get('awake_h'),
                'sleep_score': resultado.get('sleep_score'), 'recovery_score': None,
                'sleep_feedback': resultado.get('sleep_feedback'), 'hr_reposo': resultado.get('hr_reposo'),
                'fc_nocturna': resultado.get('fc_nocturna'), 'spo2_avg': resultado.get('spo2_avg'),
                'spo2_min': resultado.get('spo2_min'), 'resp_avg': resultado.get('resp_avg'),
                'resp_min': resultado.get('resp_min'), 'resp_max': resultado.get('resp_max'),
                'restless_count': resultado.get('restless_count'), 'awake_count': resultado.get('awake_count'),
                'sleep_hr_serie':     json.dumps(resultado['sleep_hr_serie'])     if resultado.get('sleep_hr_serie')     else None,
                'sleep_stress_serie': json.dumps(resultado['sleep_stress_serie']) if resultado.get('sleep_stress_serie') else None,
                'sleep_stress_avg':   resultado.get('sleep_stress_avg'),
                'resp_serie':         json.dumps(resultado['resp_serie'])         if resultado.get('resp_serie')         else None,
            })
            print('    [OK] Bio guardado')
        except Exception as e: print(f'    Error bio DB: {e}')
    return resultado


# ── Descargar actividades ─────────────────────────────────────────────────────
def descargar_actividades(client, fecha_str: str, atleta_id: int,
                           conn, db) -> list:
    from sincronizar_activities import (
        TIPO_A_SPORT, DEPORTES_VALIDOS,
        procesar_running, procesar_cycling, procesar_swimming,
        asegurar_columnas as aseg_cols
    )
    atleta = dict(conn.execute('SELECT * FROM atletas WHERE id=%s', (atleta_id,)).fetchone())
    aseg_cols(conn)

    try:
        actividades = client.get_activities_by_date(fecha_str, fecha_str)
    except Exception as e:
        print(f'    Error actividades: {e}'); return []

    if not actividades:
        print(f'    Sin actividades para {fecha_str}'); return []

    TIPO_MAP = {
        'running': 'Carrera', 'treadmill_running': 'Entrenamiento en cinta',
        'indoor_cycling': 'Ciclismo en sala', 'cycling': 'Ciclismo',
        'open_water_swimming': 'Natación en aguas abiertas',
        'lap_swimming': 'Natación en piscina', 'pool_swimming': 'Natación en piscina',
    }

    sesiones_nuevas = []
    for act in actividades:
        tipo_raw    = act.get('activityType', {}).get('typeKey', '')
        tipo_garmin = TIPO_MAP.get(tipo_raw, 'Otros')
        sport       = TIPO_A_SPORT.get(tipo_garmin)
        if sport not in DEPORTES_VALIDOS:
            print(f'    Ignorando: {tipo_raw}'); continue

        row = {
            'Tipo de actividad':          tipo_garmin,
            'Tiempo':                     _seg_a_hms(act.get('duration', 0)),
            'Distancia':                  str(act.get('distance', 0)),
            'Frecuencia cardiaca media':  str(act.get('averageHR', '')),
            'FC máxima':                  str(act.get('maxHR', '')),
            'Ritmo medio':                _pace_a_str(act.get('averageSpeed', 0), sport),
            'Training Stress Score®':     str(act.get('trainingStressScore', 0) or 0),
            'Calorías':                   str(act.get('calories', '')),
            'TE aeróbico':                str(act.get('aerobicTrainingEffect', '')),
            'Número de vueltas':          str(act.get('lapCount', '')),
            'Normalized Power® (NP®)':   str(act.get('normPower', '')),
            'Potencia media':             str(act.get('avgPower', '')),
            'Potencia máxima':            str(act.get('maxPower', '')),
            'Paladas totales':            str(act.get('totalStrokes', '')),
            'Swolf medio':                str(act.get('avgSwolf', '')),
        }
        try:
            if sport == 'running':    datos = procesar_running(row, atleta)
            elif sport == 'cycling':  datos = procesar_cycling(row, atleta)
            elif sport == 'swimming': datos = procesar_swimming(row, atleta)

            existe = conn.execute(
                'SELECT id FROM sesiones WHERE atleta_id=%s AND fecha=%s AND sport=%s',
                (atleta_id, fecha_str, sport)
            ).fetchone()

            if not existe:
                cols = ['atleta_id', 'fecha'] + list(datos.keys())
                vals = [atleta_id, fecha_str] + list(datos.values())
                cur = conn.cursor()
                cur.execute(
                    f"INSERT INTO sesiones ({','.join(cols)}) VALUES ({','.join(['%s']*len(cols))}) RETURNING id",
                    vals
                )
                sesion_id = cur.fetchone()[0]
                sesiones_nuevas.append(sport)
                print(f'    [OK] {sport.upper()} - TSS {datos.get("tss_total","?")}')

                act_id = act.get('activityId')
                if act_id:
                    # Guardar garmin_activity_id
                    conn.execute('UPDATE sesiones SET garmin_activity_id=%s WHERE id=%s',
                                 (str(act_id), sesion_id))

                    # Guardar métricas extra del summary
                    _guardar_metricas_summary(conn, sesion_id, act)

                    # Bajar laps
                    _bajar_laps(client, act_id, atleta_id, fecha_str, sport,
                                sesion_id, conn, db)

                    # Bajar streams (punto a punto)
                    _bajar_streams(client, act_id, atleta_id, sesion_id, sport, conn)
            else:
                # Si ya existe: re-bajar laps si --relaps, o streams si no los tiene
                ses_row = conn.execute(
                    'SELECT id, garmin_activity_id, has_streams FROM sesiones '
                    'WHERE atleta_id=%s AND fecha=%s AND sport=%s',
                    (atleta_id, fecha_str, sport)
                ).fetchone()
                if ses_row:
                    gid = ses_row[1] or str(act.get('activityId', ''))
                    sesion_id_exist = ses_row[0]
                    if gid and False:  # --relaps no se usa en este flujo (bug: 'args' no existia aca)
                        # Borrar laps existentes y re-bajar
                        conn.execute('DELETE FROM laps WHERE atleta_id=%s AND sesion_id=%s',
                                     (atleta_id, sesion_id_exist))
                        conn.commit()
                        _bajar_laps(client, int(gid), atleta_id, fecha_str, sport,
                                    sesion_id_exist, conn, db)
                        print(f'    [OK] Laps re-descargados para sesión {sesion_id_exist}')
                if ses_row and not ses_row[2]:
                    gid = ses_row[1] or str(act.get('activityId', ''))
                    if gid:
                        if not ses_row[1]:
                            conn.execute('UPDATE sesiones SET garmin_activity_id=%s WHERE id=%s',
                                         (gid, ses_row[0]))
                        _bajar_streams(client, gid, atleta_id, ses_row[0], sport, conn)
                print(f'    {sport.upper()} ya existía para {fecha_str}')

        except Exception as e:
            print(f'    Error {sport}: {e}')

    if sesiones_nuevas:
        conn.commit()
        db.actualizar_ctl_atl_tsb(atleta_id)

    return sesiones_nuevas


def _guardar_metricas_summary(conn, sesion_id: int, act: dict):
    """Guarda métricas adicionales del summary de la actividad."""
    try:
        updates = {}
        # Zonas HR en segundos
        for i in range(1, 6):
            v = act.get(f'hrTimeInZone_{i}')
            if v: updates[f'hr_zone_{i}_s'] = round(v, 1)
        # Training load y TE
        if act.get('activityTrainingLoad'):
            updates['activity_training_load'] = act['activityTrainingLoad']
        if act.get('aerobicTrainingEffect'):
            updates['aerobic_te'] = act['aerobicTrainingEffect']
        if act.get('anaerobicTrainingEffect'):
            updates['anaerobic_te'] = act['anaerobicTrainingEffect']
        # Splits rápidos (running)
        for garmin_key, col in [
            ('fastestSplit_1000', 'fastest_1k'),
            ('fastestSplit_5000', 'fastest_5k'),
        ]:
            if act.get(garmin_key): updates[col] = act[garmin_key]
        # Otros
        if act.get('avgStrideLength'): updates['avg_stride_length'] = act['avgStrideLength']
        if act.get('waterEstimated'):  updates['water_estimated']    = act['waterEstimated']
        avg_temp = act.get('avgTemperature') or (
            (act.get('minTemperature', 0) + act.get('maxTemperature', 0)) / 2
            if act.get('minTemperature') else None
        )
        if avg_temp: updates['temperatura_avg'] = avg_temp

        if updates:
            set_clause = ', '.join(f'{k}=%s' for k in updates)
            conn.execute(
                f'UPDATE sesiones SET {set_clause} WHERE id=%s',
                list(updates.values()) + [sesion_id]
            )
            conn.commit()
    except Exception as e:
        print(f'    Métricas summary: {e}')


def _bajar_streams(client, activity_id, atleta_id, sesion_id, sport, conn):
    """Baja y guarda streams punto a punto."""
    try:
        details = client.get_activity_details(activity_id)
        samples = _parsear_streams(details, sport)
        if samples:
            n = _guardar_streams(conn, atleta_id, sesion_id, activity_id, samples)
            print(f'    [OK] Streams: {n} samples ({sport})')
        else:
            print(f'    Streams: sin datos válidos ({sport})')
    except Exception as e:
        print(f'    Streams error: {e}')


def _bajar_laps(client, activity_id, atleta_id, fecha, sport, sesion_id, conn, db):
    try:
        splits = client.get_activity_splits(activity_id)
        if not splits: return

        if sport == 'swimming':
            try:
                from swim_processor import parsear_splits_garmin, guardar_laps_swim, analizar_sesion_swim
                atleta_row = conn.execute('SELECT lthr_run FROM atletas WHERE id=%s', (atleta_id,)).fetchone()
                lthr_swim  = round((atleta_row[0] or 162) * 0.92)
                laps, largos = parsear_splits_garmin(splits)
                if laps:
                    n_laps, n_largos = guardar_laps_swim(conn, atleta_id, sesion_id, fecha, laps, largos)
                    print(f'    [OK] Swim: {n_laps} series, {n_largos} largos')
                    analisis = analizar_sesion_swim(splits, lthr_swim)
                    css = analisis.get('css', {}).get('css_min_100')
                    if css:
                        conn.execute('UPDATE atletas SET css_100m=%s WHERE id=%s', (round(css, 3), atleta_id))
                        conn.commit()
            except ImportError:
                _bajar_laps_basico(splits, atleta_id, fecha, sesion_id, db)
        else:
            _bajar_laps_basico(splits, atleta_id, fecha, sesion_id, db)
    except Exception as e:
        print(f'    Laps error: {e}')


def _bajar_laps_basico(splits, atleta_id, fecha, sesion_id, db):
    laps_raw = []
    for i, lap in enumerate(splits.get('lapDTOs', []), 1):
        dur  = lap.get('duration', 0) / 60
        dist = lap.get('distance', 0) / 1000
        hr   = lap.get('averageHR')
        pace = (dur / dist) if dist > 0.01 else None

        # Potencia
        avg_power = lap.get('avgPower') or lap.get('averagePower')
        max_power = lap.get('maxPower')
        norm_power = lap.get('normalizedPower') or lap.get('normPower')

        # Velocidad (cycling)
        avg_speed = None
        if dist > 0.01 and dur > 0:
            avg_speed = round((dist / (dur / 60)), 2)  # km/h
        max_speed_ms = lap.get('maxSpeed')
        max_speed = round(max_speed_ms * 3.6, 2) if max_speed_ms else None

        # Cadencia — bike vs run
        cadence = (lap.get('avgBikeCadence') or lap.get('averageBikeCadence') or
                   lap.get('averageRunCadence') or lap.get('avgCadence'))

        # Trabajo kJ
        total_work = lap.get('totalWork')  # en J → convertir a kJ
        work_kj = round(total_work / 1000, 2) if total_work else None

        # Temperatura
        temperature = lap.get('avgTemperature') or lap.get('averageTemperature')

        # TSS y IF del lap (si vienen de Garmin)
        lap_tss = lap.get('trainingStressScore') or lap.get('tss')
        lap_if  = lap.get('intensityFactor') or lap.get('if')

        # W/kg se calcula en el front si tiene FTP
        # w_balance si está disponible
        w_prime_balance = lap.get('wBalanceFinal') or lap.get('wPrimeBalance')

        laps_raw.append({
            'lap_num':      i,
            'duration_min': round(dur, 2),
            'distance_km':  round(dist, 3),
            'hr_avg':       hr,
            'hr_max':       lap.get('maxHR'),
            'pace':         round(pace, 3) if pace else None,
            'avg_power':    avg_power,
            'max_power':    max_power,
            'norm_power':   norm_power,
            'avg_speed':    avg_speed,
            'max_speed':    max_speed,
            'cadence':      cadence,
            'work_kj':      work_kj,
            'temperature':  temperature,
            'lap_tss':      lap_tss,
            'lap_if':       round(lap_if, 3) if lap_if else None,
            'w_balance':    round(w_prime_balance, 0) if w_prime_balance else None,
        })
    if laps_raw:
        n = db.agregar_laps(atleta_id, sesion_id, fecha, laps_raw)
        print(f'    [OK] {n} laps')


# ── Descargar métricas de rendimiento (diarias) ───────────────────────────────
def _init_fc_intradiaria(conn):
    conn.execute('''
        CREATE TABLE IF NOT EXISTS fc_intradiaria (
            id        SERIAL PRIMARY KEY,
            atleta_id INTEGER NOT NULL,
            fecha     TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            ts_epoch  INTEGER,
            hr_bpm    INTEGER,
            UNIQUE(atleta_id, timestamp),
            FOREIGN KEY (atleta_id) REFERENCES atletas(id)
        )
    ''')
    conn.commit()


def descargar_fc_intradiaria(client, fecha_str, atleta_id, conn):
    """Descarga FC intradiaria (cada ~2 min) y guarda en fc_intradiaria.
    
    Lógica de re-descarga:
    - Día de hoy: siempre re-descarga (el día no terminó, hay datos nuevos)
    - Días pasados: si ya tiene 50+ puntos, no re-descarga (está completo)
    """
    _init_fc_intradiaria(conn)
    from datetime import date as _date
    es_hoy = fecha_str == str(_date.today())
    
    n_ex = conn.execute('SELECT COUNT(*) FROM fc_intradiaria WHERE atleta_id=%s AND fecha=%s',
                        (atleta_id, fecha_str)).fetchone()[0]
    if n_ex > 50 and not es_hoy:
        print(f'    FC intradiaria ya ok ({n_ex} pts)'); return n_ex
    try:
        hr_data = client.get_heart_rates(fecha_str)
        if not hr_data: return 0
        values = hr_data.get('heartRateValues') or []
        if not values: return 0
        ins = 0
        from datetime import datetime, timezone
        for item in values:
            if not item or len(item) < 2: continue
            ts_ms, bpm = item[0], item[1]
            if bpm is None or bpm <= 0: continue
            ts_str = datetime.fromtimestamp(ts_ms/1000, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
            try:
                conn.execute(
                    'INSERT INTO fc_intradiaria (atleta_id,fecha,timestamp,ts_epoch,hr_bpm) VALUES (%s,%s,%s,%s,%s) '
                    'ON CONFLICT (atleta_id, timestamp) DO NOTHING',
                    (atleta_id, fecha_str, ts_str, int(ts_ms/1000), int(bpm))); ins += 1
            except Exception:
                # Rollback OBLIGATORIO: este insert corre en un loop de
                # potencialmente cientos de puntos de FC — sin rollback, un
                # solo fallo deja la transacción abortada para los siguientes.
                conn.rollback()
        conn.commit()
        print(f'    [OK] FC intradiaria: {ins} puntos'); return ins
    except Exception as e:
        print(f'    FC intradiaria error: {e}'); return 0


def calcular_stress_intradiario(conn, atleta_id, fecha_str):
    """Calcula stress score intradiario desde FC y lo guarda en sleep_hrv."""
    at = conn.execute('SELECT hr_max FROM atletas WHERE id=%s', (atleta_id,)).fetchone()
    hr_max = (at[0] if at else None) or 185
    rows = conn.execute('SELECT hr_bpm FROM fc_intradiaria WHERE atleta_id=%s AND fecha=%s AND hr_bpm>0',
                        (atleta_id, fecha_str)).fetchall()
    if not rows: return
    bpms = [r[0] for r in rows]
    umbral = hr_max * 0.55
    pct_alto = sum(1 for b in bpms if b > umbral) / len(bpms) * 100
    stress_intra = min(100, round(pct_alto * 1.6))
    fc_media_dia = round(sum(bpms)/len(bpms), 1)
    # PRAGMA table_info (SQLite) reemplazado por el helper compartido.
    _asegurar_columnas_helper(conn, 'sleep_hrv', [('stress_intra','REAL'),('fc_media_dia','REAL')])
    conn.execute('UPDATE sleep_hrv SET stress_intra=%s, fc_media_dia=%s WHERE atleta_id=%s AND fecha=%s',
                 (stress_intra, fc_media_dia, atleta_id, fecha_str))
    conn.commit()


def descargar_performance(client, fecha_str: str, atleta_id: int,
                           conn) -> dict:
    """
    Descarga métricas de rendimiento diarias:
    - VO2max + training status
    - Race predictions
    - Training load balance
    - Respiration + SPO2 intraday
    """
    resultado = {}
    print(f'  -> Performance {fecha_str}:')

    # Training status + VO2max + load balance
    try:
        ts = client.get_training_status(fecha_str)
        if ts:
            resultado['vo2max']          = ts.get('mostRecentVO2Max')
            resultado['training_status'] = (ts.get('mostRecentTrainingStatus') or {}).get('trainingStatusKey') or ts.get('mostRecentTrainingStatus')
            lb = ts.get('mostRecentTrainingLoadBalance') or {}
            resultado['load_balance']    = lb.get('loadBalanceMetricKey') or lb.get('balanceKey')
            resultado['acute_load']      = lb.get('acuteLoad')
            resultado['chronic_load']    = lb.get('chronicLoad')
            print(f"    VO2max: {resultado['vo2max']} | Status: {resultado['training_status']} | Balance: {resultado['load_balance']}")
    except Exception as e: print(f'    Training status: {e}')

    # Race predictions
    try:
        rp = client.get_race_predictions()
        if rp and isinstance(rp, dict):
            resultado['race_5k_s']       = rp.get('time5K')
            resultado['race_10k_s']      = rp.get('time10K')
            resultado['race_half_s']     = rp.get('timeHalfMarathon')
            resultado['race_marathon_s'] = rp.get('timeMarathon')
            def fmt(s):
                if not s: return '--'
                return f"{int(s//3600)}:{int((s%3600)//60):02d}:{int(s%60):02d}"
            print(f"    Predicciones: 5k={fmt(resultado['race_5k_s'])} 10k={fmt(resultado['race_10k_s'])} 21k={fmt(resultado['race_half_s'])}")
    except Exception as e: print(f'    Race predictions: {e}')

    # Respiración intraday
    try:
        resp = client.get_respiration_data(fecha_str)
        if resp:
            resultado['respiration_avg'] = resp.get('avgWakingRespirationValue') or resp.get('averageRespirationValue')
            resultado['respiration_min'] = resp.get('lowestRespirationValue')
    except Exception as e: print(f'    Respiración: {e}')

    # SPO2 intraday
    try:
        spo2 = client.get_spo2_data(fecha_str)
        if spo2:
            resultado['spo2_avg'] = spo2.get('averageSpO2') or spo2.get('avgSpo2')
            resultado['spo2_min'] = spo2.get('lowestSpO2') or spo2.get('minSpo2')
    except Exception as e: print(f'    SPO2: {e}')

    # Guardar en DB
    if any(v is not None for v in resultado.values()):
        try:
            conn.execute('''
                INSERT INTO garmin_performance
                (atleta_id, fecha, vo2max, training_status, load_balance,
                 acute_load, chronic_load, race_5k_s, race_10k_s,
                 race_half_s, race_marathon_s, respiration_avg,
                 respiration_min, spo2_avg, spo2_min)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (atleta_id, fecha) DO UPDATE SET
                    vo2max=excluded.vo2max, training_status=excluded.training_status,
                    load_balance=excluded.load_balance, acute_load=excluded.acute_load,
                    chronic_load=excluded.chronic_load, race_5k_s=excluded.race_5k_s,
                    race_10k_s=excluded.race_10k_s, race_half_s=excluded.race_half_s,
                    race_marathon_s=excluded.race_marathon_s,
                    respiration_avg=excluded.respiration_avg,
                    respiration_min=excluded.respiration_min,
                    spo2_avg=excluded.spo2_avg, spo2_min=excluded.spo2_min
            ''', (
                atleta_id, fecha_str,
                resultado.get('vo2max'), resultado.get('training_status'),
                resultado.get('load_balance'), resultado.get('acute_load'),
                resultado.get('chronic_load'), resultado.get('race_5k_s'),
                resultado.get('race_10k_s'), resultado.get('race_half_s'),
                resultado.get('race_marathon_s'), resultado.get('respiration_avg'),
                resultado.get('respiration_min'), resultado.get('spo2_avg'),
                resultado.get('spo2_min'),
            ))
            conn.commit()
            print('    [OK] Performance guardado')
        except Exception as e: print(f'    Error performance DB: {e}')


def descargar_umbrales(client, atleta_id: int, conn):
    """
    Trae el LTHR/pace de running y FTP de cycling directo de Garmin
    (cuando el reloj los tiene calculados) y los guarda en columnas
    separadas (*_garmin) -- nunca pisa directamente lthr_run/ftp_watts,
    porque esos son el valor final que decide actualizar_umbral_final()
    combinando esta fuente con el calculo propio de NOAH.

    Garmin no siempre tiene un valor reciente (el reloj solo lo detecta
    en ciertas sesiones y el usuario debe aceptarlo) -- por eso esto es
    "best effort": si no hay dato, simplemente no se actualiza nada.
    """
    print('  -> Umbrales (Garmin):')
    lthr_garmin  = None
    pace_garmin  = None
    ftp_garmin   = None

    try:
        lt = client.get_lactate_threshold(latest=True)
        shr = (lt or {}).get('speed_and_heart_rate') or {}
        hr    = shr.get('heartRate')
        speed = shr.get('speed')  # metros/segundo
        if hr:
            lthr_garmin = float(hr)
        if speed and speed > 0:
            # El campo 'speed' que devuelve este endpoint de Garmin NO esta
            # en m/s puros -- viene escalado x10 (confirmado empiricamente:
            # speed=0.336 correspondia a un pace real de 4:58/km, que solo
            # cuadra multiplicando por 10 antes de convertir). Sin este
            # factor, el calculo daba paces absurdos (~49 min/km).
            speed_ms = speed * 10
            pace_garmin = round(1000 / (speed_ms * 60), 3)
        if lthr_garmin or pace_garmin:
            print(f"    LTHR run: {lthr_garmin} bpm | Pace umbral: {pace_garmin} min/km")
    except Exception as e:
        print(f'    Lactate threshold: {e}')

    try:
        ftp_data = client.get_cycling_ftp()
        if isinstance(ftp_data, list) and ftp_data:
            ftp_data = ftp_data[0]
        if isinstance(ftp_data, dict):
            ftp_garmin = (
                ftp_data.get('functionalThresholdPower')
                or ftp_data.get('ftp')
                or ftp_data.get('value')
            )
            if ftp_garmin:
                ftp_garmin = float(ftp_garmin)
                print(f"    FTP bike: {ftp_garmin} W")
    except Exception as e:
        print(f'    Cycling FTP: {e}')

    if lthr_garmin or pace_garmin or ftp_garmin:
        try:
            from db_compat import asegurar_columnas as _aseg
            _aseg(conn, 'atletas', [
                ('lthr_run_garmin',        'REAL'),
                ('pace_umbral_run_garmin', 'REAL'),
                ('ftp_bike_garmin',        'REAL'),
                ('fecha_umbral_garmin',    'TEXT'),
            ])
            sets, params = [], []
            if lthr_garmin is not None:
                sets.append('lthr_run_garmin=%s'); params.append(lthr_garmin)
            if pace_garmin is not None:
                sets.append('pace_umbral_run_garmin=%s'); params.append(pace_garmin)
            if ftp_garmin is not None:
                sets.append('ftp_bike_garmin=%s'); params.append(ftp_garmin)
            sets.append('fecha_umbral_garmin=%s')
            params.append(datetime.now().date().isoformat())
            params.append(atleta_id)
            conn.execute(f"UPDATE atletas SET {', '.join(sets)} WHERE id=%s", params)
            conn.commit()
            print('    [OK] Umbrales Garmin guardados')
        except Exception as e:
            print(f'    Error guardando umbrales: {e}')
    else:
        print('    Sin umbrales nuevos de Garmin (normal si el reloj no detecto cambios)')


# ── Helpers ───────────────────────────────────────────────────────────────────
def _seg_a_hms(seg):
    if not seg: return '00:00:00'
    return f'{int(seg//3600):02d}:{int((seg%3600)//60):02d}:{int(seg%60):02d}'

def _pace_a_str(speed_ms, sport):
    if not speed_ms or speed_ms <= 0: return ''
    pace = (100 / speed_ms / 60) if sport == 'swimming' else (1000 / speed_ms / 60)
    return f'{int(pace)}:{int((pace % 1) * 60):02d}'


# ── Configurar credenciales ───────────────────────────────────────────────────
def configurar_credenciales(conn, atleta_id):
    atleta = conn.execute('SELECT nombre, garmin_user FROM atletas WHERE id=%s', (atleta_id,)).fetchone()
    if not atleta: print(f'Atleta {atleta_id} no encontrado'); return
    print(f'\n  Configurar Garmin: {atleta[0]} (actual: {atleta[1] or "no configurado"})')
    user = input('  Email Garmin: ').strip()
    pwd  = getpass.getpass('  Contraseña: ')
    if not user or not pwd: print('  Cancelado.'); return
    conn.execute('UPDATE atletas SET garmin_user=%s, garmin_pass=%s WHERE id=%s', (user, _enc(pwd), atleta_id))
    conn.commit()
    print(f'  [OK] Guardado para {atleta[0]}')


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description='NOAH - Sync Garmin')
    ap.add_argument('--atleta',   type=int, default=None)
    ap.add_argument('--modo',     default='todo', choices=['todo','bio','actividad','perf','intradiario'])
    ap.add_argument('--fecha',    default=None)
    ap.add_argument('--dias',     type=int, default=1)
    ap.add_argument('--rellenar', action='store_true')
    ap.add_argument('--relaps',   action='store_true', help='Forzar re-descarga de laps de sesiones existentes')
    ap.add_argument('--config',   action='store_true')
    ap.add_argument('--db',       default=None,
                     help='Cadena de conexión a Postgres/Supabase (default: variable de entorno DATABASE_URL)')
    args = ap.parse_args()

    import os
    db_url = args.db or os.environ.get('DATABASE_URL')
    if not db_url:
        print('Falta --db o la variable de entorno DATABASE_URL (cadena de conexión a Postgres/Supabase)')
        sys.exit(1)

    # Fechas
    if args.fecha:
        fechas = [args.fecha]
    elif args.rellenar:
        import psycopg2.extras
        from db_compat import ConexionCompat
        conn_tmp = ConexionCompat(psycopg2.connect(db_url, cursor_factory=psycopg2.extras.DictCursor))
        fechas = []
        for i in range(7, 0, -1):
            f = str(date.today() - timedelta(days=i))
            if not conn_tmp.execute(
                "SELECT id FROM sleep_hrv WHERE atleta_id=%s AND fecha=%s AND (sleep_h IS NOT NULL OR body_battery IS NOT NULL)",
                (args.atleta or 0, f)).fetchone():
                fechas.append(f)
        conn_tmp.close()
        if not fechas: fechas = [str(date.today())]
        print(f'  Rellenando {len(fechas)} días: {fechas}')
    else:
        fechas = [str(date.today() - timedelta(days=i)) for i in range(args.dias-1, -1, -1)]

    from noa_db import NOADatabase
    import psycopg2.extras
    from db_compat import ConexionCompat
    db   = NOADatabase(db_url)
    conn = ConexionCompat(psycopg2.connect(db_url, cursor_factory=psycopg2.extras.DictCursor))
    asegurar_columnas(conn)

    if args.config:
        atleta_id = args.atleta or int(input('ID atleta: '))
        configurar_credenciales(conn, atleta_id)
        conn.close(); return

    rows = conn.execute(
        'SELECT id, nombre, garmin_user, garmin_pass FROM atletas '
        'WHERE activo=1 AND garmin_user IS NOT NULL' +
        (f' AND id={args.atleta}' if args.atleta else '')
    ).fetchall()

    if not rows:
        print('Sin atletas con credenciales. Correr: python sincronizar_garmin.py --config --atleta 1')
        conn.close(); return

    fecha = fechas[0]
    print('=' * 60)
    print(f'  NOAH Sync | Fechas: {fechas} | Modo: {args.modo}')
    print('=' * 60)

    for row in rows:
        atleta_id, nombre, g_user, g_pass = row[0], row[1], row[2], row[3]
        if not g_user or not g_pass:
            print(f'\n  {nombre}: sin credenciales'); continue

        print(f'\n  Atleta: {nombre}')
        try:
            client = get_client(g_user, g_pass)
            print('  [OK] Conectado')
        except Exception as e:
            print(f'  [FAIL] {e}')
            conn.execute('INSERT INTO sync_log (atleta_id, fecha, modo, status, detalle) VALUES (%s,%s,%s,%s,%s)',
                         (atleta_id, fecha, args.modo, 'error', str(e)))
            conn.commit(); continue

        exito = True
        for fecha_iter in fechas:
            if args.modo in ('todo', 'bio'):
                try: descargar_bio(client, fecha_iter, atleta_id, conn, db)
                except Exception as e: print(f'  Bio error: {e}'); exito = False

            if args.modo in ('todo', 'actividad'):
                try:
                    nuevas = descargar_actividades(client, fecha_iter, atleta_id, conn, db)
                    if nuevas: print(f'  [OK] Nuevas: {", ".join(nuevas)}')
                except Exception as e: print(f'  Act error: {e}'); exito = False

            if args.modo in ('todo', 'perf'):
                try: descargar_performance(client, fecha_iter, atleta_id, conn)
                except Exception as e: print(f'  Perf error: {e}')

            if args.modo in ('todo', 'intradiario', 'bio'):
                try:
                    descargar_fc_intradiaria(client, fecha_iter, atleta_id, conn)
                    # Siempre recalcular stress — el día puede haber avanzado
                    calcular_stress_intradiario(conn, atleta_id, fecha_iter)
                except Exception as e: print(f'  FC intradiaria error: {e}')

        # Umbrales (LTHR run, pace umbral, FTP bike) -- una sola vez por
        # atleta, no por fecha (Garmin siempre da "el ultimo" valor).
        if args.modo in ('todo', 'perf'):
            try: descargar_umbrales(client, atleta_id, conn)
            except Exception as e: print(f'  Umbrales error: {e}')

            # Calculo propio desde el historial (solo corre si pasaron
            # 21+ dias desde el ultimo calculo, ver dentro de la funcion)
            # y resolucion del valor final que usan las zonas.
            try:
                db.calcular_umbral_desde_historial(atleta_id)
                db.actualizar_umbral_final(atleta_id)
            except Exception as e: print(f'  Umbral historial error: {e}')

        # Post-proceso
        for modulo, fn in [
            ('hanna_vfc',        ('calcular_y_guardar_hanna_vfc',  [conn, atleta_id])),
            ('noah_hrv_estimado',('calcular_y_guardar_hrv_estimado',[conn, atleta_id])),
            ('noah_hanna_life',  ('calcular_y_guardar_hanna_life', [conn, atleta_id])),
        ]:
            try:
                import importlib
                mod = importlib.import_module(modulo)
                n = getattr(mod, fn[0])(*fn[1])
                if n > 0: print(f'  [{modulo}] {n} días calculados')
            except Exception as e: print(f'  [{modulo}] {e}')

        conn.execute('UPDATE atletas SET ultima_sync=%s WHERE id=%s', (datetime.now().isoformat(), atleta_id))
        conn.execute('INSERT INTO sync_log (atleta_id, fecha, modo, status, detalle) VALUES (%s,%s,%s,%s,%s)',
                     (atleta_id, fecha, args.modo, 'ok' if exito else 'parcial', ''))
        conn.commit()

    conn.close()
    print('\n' + '=' * 60)
    print('  Sync completado')
    print('=' * 60)


if __name__ == '__main__':
    main()
