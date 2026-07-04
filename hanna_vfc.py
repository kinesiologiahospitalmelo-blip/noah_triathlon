"""
hanna_vfc.py — Proyecto NOAH
==============================
HANNA_VFC — Variabilidad de Frecuencia Cardíaca calculada desde datos Garmin.

METODOLOGÍA:
  1. Extraer serie de FC nocturna cada 2 min (sleepHeartRate)
  2. Convertir a intervalos RR: RR = 60000 / FC_bpm
  3. Calcular SDNN desde serie RR
  4. Ajustar por sleepStress (factor de corrección autonómica)
  5. Normalizar por baseline personal 30 días (ratio)

VALIDACIÓN:
  - Correlación inversa SDNN vs sleepStress (esperado r < -0.3)
  - Calibración futura con dataset ECG 24hs

REFERENCIAS:
  - Task Force ESC/NASPE 1996: estándares VFC
  - Plews et al. 2013: ratio vs baseline personal en atletas
  - Hernando et al. 2011: SDNN desde series de baja resolución r=0.71 vs RMSSD
  - Kiviniemi et al. 2010: baseline personal normalización
"""

from __future__ import annotations
import psycopg2
import json
import numpy as np
from datetime import date, timedelta
from typing import Optional, List
from db_compat import asegurar_columnas


def calcular_sdnn_desde_fc(hr_serie: List[float]) -> Optional[float]:
    """
    Calcula SDNN desde serie de FC en bpm.
    RR = 60000 / FC_bpm (ms)
    SDNN = desviación estándar de la serie RR.
    """
    if not hr_serie or len(hr_serie) < 5:
        return None
    rr = [60000 / fc for fc in hr_serie if fc > 0]
    if len(rr) < 5:
        return None
    return round(float(np.std(rr)), 2)


def calcular_hanna_vfc(
    hr_serie:      List[float],
    stress_serie:  List[float] = None,
    baseline_30d:  Optional[float] = None,
    std_30d:       Optional[float] = None,
) -> dict:
    """
    Calcula HANNA_VFC desde serie FC nocturna y stress nocturno.

    Retorna:
        sdnn:           SDNN calculado desde RR
        stress_factor:  factor de ajuste (1 - stress_avg/100)
        hanna_vfc:      SDNN × stress_factor
        hanna_vfc_ratio: hanna_vfc / baseline_30d (si disponible)
        flag:           verde/amarillo/rojo según ratio
        z_score:        desviación vs baseline (si std disponible)
    """
    sdnn = calcular_sdnn_desde_fc(hr_serie)
    if sdnn is None:
        return {'hanna_vfc': None, 'sdnn': None, 'flag': 'sin_datos'}

    # Factor stress (sleepStress bajo = SNA parasimpático = VFC alta)
    stress_avg = float(np.mean(stress_serie)) if stress_serie else None
    stress_factor = 1.0 - (stress_avg / 100) if stress_avg is not None else 0.85

    hanna_vfc = round(sdnn * stress_factor, 2)

    # Ratio vs baseline personal (Plews 2013, Kiviniemi 2010)
    ratio = None
    flag  = 'sin_baseline'
    z     = None

    if baseline_30d and baseline_30d > 0:
        ratio = round(hanna_vfc / baseline_30d, 3)
        flag  = ('verde'    if ratio >= 1.05 else
                 'amarillo' if ratio >= 0.95 else
                 'rojo')

        if std_30d and std_30d > 0:
            z = round((hanna_vfc - baseline_30d) / std_30d, 2)

    return {
        'sdnn':            sdnn,
        'stress_factor':   round(stress_factor, 3),
        'stress_avg':      round(stress_avg, 1) if stress_avg else None,
        'hanna_vfc':       hanna_vfc,
        'hanna_vfc_ratio': ratio,
        'hanna_vfc_flag':  flag,
        'hanna_vfc_z':     z,
        'n_puntos_hr':     len(hr_serie),
        'n_puntos_stress': len(stress_serie) if stress_serie else 0,
    }


def validar_correlacion(conn, atleta_id: int) -> dict:
    """
    Valida el modelo calculando la correlación entre HANNA_VFC y sleepStress.
    Esperado: correlación negativa (más stress = menos VFC).
    """
    rows = conn.execute('''
        SELECT hanna_vfc, sleep_stress_avg
        FROM sleep_hrv
        WHERE atleta_id=%s AND hanna_vfc IS NOT NULL AND sleep_stress_avg IS NOT NULL
        ORDER BY fecha DESC LIMIT 60
    ''', (atleta_id,)).fetchall()

    if len(rows) < 10:
        return {'valido': False, 'msg': f'Insuficientes datos ({len(rows)} días)'}

    vfc_vals    = [r[0] for r in rows]
    stress_vals = [r[1] for r in rows]
    corr = float(np.corrcoef(vfc_vals, stress_vals)[0, 1])

    return {
        'valido':      corr < -0.3,
        'correlacion': round(corr, 3),
        'n_dias':      len(rows),
        'interpretacion': (
            f'Correlación r={corr:.2f} — modelo VÁLIDO (inverso al stress)' if corr < -0.3 else
            f'Correlación r={corr:.2f} — débil, revisar datos'
        )
    }


def calcular_y_guardar_hanna_vfc(
    conn,
    atleta_id: int,
    fecha: str = None,
    recalcular_todo: bool = False,
) -> int:
    """
    Calcula HANNA_VFC para los registros que tienen serie FC nocturna.
    """
    fecha = fecha or str(date.today())

    # Asegurar columnas — PRAGMA table_info (SQLite) reemplazado por el
    # helper compartido (information_schema.columns en Postgres).
    asegurar_columnas(conn, 'sleep_hrv', [
        ('hanna_vfc',       'REAL'),
        ('hanna_vfc_ratio', 'REAL'),
        ('hanna_vfc_flag',  'TEXT'),
        ('hanna_vfc_z',     'REAL'),
        ('sdnn_nocturno',   'REAL'),
        ('sleep_hr_serie',  'TEXT'),  # JSON de la serie FC nocturna
        ('sleep_stress_serie', 'TEXT'),  # JSON de la serie stress nocturna
        ('sleep_stress_avg',  'REAL'),  # promedio stress nocturno
        ('resp_serie',      'TEXT'),  # JSON respiración
    ])
    conn.commit()

    # Baseline 30 días de HANNA_VFC
    df_base = conn.execute('''
        SELECT hanna_vfc FROM sleep_hrv
        WHERE atleta_id=%s AND hanna_vfc IS NOT NULL AND hanna_vfc > 0
        ORDER BY fecha DESC LIMIT 30
    ''', (atleta_id,)).fetchall()

    baseline_30d = float(np.mean([r[0] for r in df_base])) if len(df_base) >= 5 else None
    std_30d      = float(np.std([r[0] for r in df_base]))  if len(df_base) >= 5 else None

    # Rows a procesar — solo los que tienen serie FC guardada
    cond = "atleta_id=%s AND sleep_hr_serie IS NOT NULL" if recalcular_todo else \
           "atleta_id=%s AND sleep_hr_serie IS NOT NULL AND fecha<=%s AND hanna_vfc IS NULL"
    params = [atleta_id] if recalcular_todo else [atleta_id, fecha]

    rows = conn.execute(f'''
        SELECT id, fecha, sleep_hr_serie, sleep_stress_serie
        FROM sleep_hrv WHERE {cond} ORDER BY fecha
    ''', params).fetchall()

    if not rows:
        return 0

    updated = 0
    for row in rows:
        rid, f, hr_json, stress_json = row
        try:
            hr_serie     = json.loads(hr_json)     if hr_json     else []
            stress_serie = json.loads(stress_json) if stress_json else []
        except Exception:
            continue

        if not hr_serie:
            continue

        result = calcular_hanna_vfc(
            hr_serie=hr_serie,
            stress_serie=stress_serie,
            baseline_30d=baseline_30d,
            std_30d=std_30d,
        )

        if result.get('hanna_vfc') is None:
            continue

        conn.execute('''
            UPDATE sleep_hrv SET
                hanna_vfc=%s, hanna_vfc_ratio=%s, hanna_vfc_flag=%s,
                hanna_vfc_z=%s, sdnn_nocturno=%s, sleep_stress_avg=%s
            WHERE id=%s
        ''', (
            result['hanna_vfc'],
            result['hanna_vfc_ratio'],
            result['hanna_vfc_flag'],
            result['hanna_vfc_z'],
            result['sdnn'],
            result['stress_avg'],
            rid,
        ))

        # Actualizar baseline
        if baseline_30d is None:
            baseline_30d = result['hanna_vfc']
            std_30d = 0
        else:
            # Media móvil simple
            all_vfc = [r[0] for r in conn.execute(
                'SELECT hanna_vfc FROM sleep_hrv WHERE atleta_id=%s AND hanna_vfc IS NOT NULL ORDER BY fecha DESC LIMIT 30',
                (atleta_id,)
            ).fetchall()]
            if all_vfc:
                baseline_30d = float(np.mean(all_vfc))
                std_30d      = float(np.std(all_vfc))

        updated += 1

    conn.commit()
    return updated


if __name__ == '__main__':
    import argparse, sys, os
    import psycopg2.extras
    from pathlib import Path
    from db_compat import ConexionCompat
    sys.path.insert(0, str(Path(__file__).parent))

    ap = argparse.ArgumentParser(description='NOAH — HANNA VFC')
    ap.add_argument('--atleta', type=int, required=True)
    ap.add_argument('--todo',   action='store_true')
    ap.add_argument('--validar', action='store_true', help='Validar correlación VFC vs stress')
    args = ap.parse_args()

    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("Falta la variable de entorno DATABASE_URL (cadena de conexión a Postgres/Supabase)")
        sys.exit(1)
    conn = ConexionCompat(psycopg2.connect(db_url, cursor_factory=psycopg2.extras.DictCursor))

    if args.validar:
        v = validar_correlacion(conn, args.atleta)
        print(v['interpretacion'])
    else:
        print(f'Calculando HANNA_VFC para atleta {args.atleta}...')
        n = calcular_y_guardar_hanna_vfc(conn, args.atleta, recalcular_todo=args.todo)
        print(f'✓ {n} días calculados')

        rows = conn.execute('''
            SELECT fecha, hanna_vfc, hanna_vfc_ratio, hanna_vfc_flag,
                   sdnn_nocturno, sleep_stress_avg, sleep_h
            FROM sleep_hrv WHERE atleta_id=%s
            AND hanna_vfc IS NOT NULL
            ORDER BY fecha DESC LIMIT 7
        ''', (args.atleta,)).fetchall()

        print(f'\n{"Fecha":12}{"VFC":>8}{"Ratio":>8}{"Flag":>10}{"SDNN":>8}{"Stress":>8}{"Sueño":>7}')
        for r in rows:
            print(f"{str(r[0]):12}{str(r[1] or '--'):>8}{str(r[2] or '--'):>8}"
                  f"{str(r[3] or '--'):>10}{str(r[4] or '--'):>8}"
                  f"{str(r[5] or '--'):>8}{str(r[6] or '--'):>7}")

    conn.close()
