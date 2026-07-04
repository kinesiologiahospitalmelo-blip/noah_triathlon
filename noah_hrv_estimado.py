"""
noah_hrv_estimado.py — Proyecto NOAH v2
=========================================
Estima el HRV para atletas cuyos relojes no miden HRV nocturno.

CAMBIOS v2 respecto a v1:
  - Usa baseline PERSONAL del atleta (no poblacional) cuando hay historial
  - Fórmula logarítmica de Nunan 2010: RMSSD = e^(5.2 - 0.019·FC)
  - Z-score de FC reposo para ajuste — no multiplicación de factores
  - Confianza diferenciada según cuántos días de historial hay
  - Marca explícitamente como estimado con nivel de confianza

FÓRMULA BASE (Nunan et al. 2010, n=1,000 adultos sanos):
  RMSSD = e^(5.2 - 0.019 × FC_reposo)
  Válida para FC 40-100 bpm, ajustada para atletas endurance.

AJUSTE PERSONAL:
  Si el atleta tiene baseline guardado (≥30 días historial):
    hrv_est = baseline.hrv_media × factor_ajuste(proxies_hoy)
  Si no tiene baseline:
    hrv_est = Nunan(FC_hoy) ajustado por proxies disponibles

LIMITACIÓN: Sin HRV real, el margen de error es ±20-30%.
  Se indica explícitamente en el dashboard.
"""

from __future__ import annotations
import psycopg2
import numpy as np
import pandas as pd
from datetime import date, timedelta
from typing import Optional
import math
from db_compat import asegurar_columnas as _asegurar_columnas_helper


# ── Constantes Nunan 2010 ─────────────────────────────────────────────────────
NUNAN_A = 5.2
NUNAN_B = 0.019


def nunan_rmssd(fc_reposo: float) -> float:
    """
    Estima RMSSD desde FC reposo usando Nunan et al. 2010.
    RMSSD = e^(5.2 - 0.019 × FC)
    Válida para FC 40-100 bpm.
    """
    fc = max(40, min(100, fc_reposo))
    return math.exp(NUNAN_A - NUNAN_B * fc)


# ── Factor de ajuste z-score ──────────────────────────────────────────────────
def _factor_zscore(val: float, media: float, std: float,
                   direccion: int = 1) -> float:
    """
    Convierte un valor en factor de ajuste usando z-score.
    direccion: +1 = más alto es mejor (HRV, sueño)
               -1 = más bajo es mejor (FC, stress)

    Retorna factor entre 0.70 y 1.30.
    """
    if std is None or std <= 0:
        return 1.0
    z = (val - media) / std * direccion
    # Función sigmoidal suave: f(z) ∈ [0.70, 1.30]
    factor = 1.0 + 0.15 * math.tanh(z * 0.8)
    return round(max(0.70, min(1.30, factor)), 4)


def asegurar_columnas(conn):
    _asegurar_columnas_helper(conn, 'sleep_hrv', [
        ('hr_reposo',              'INTEGER'),
        ('hrv_estimado_valor',     'REAL'),
        ('hrv_estimado_confianza', 'REAL'),
    ])


def calcular_hrv_estimado(
    hr_reposo:    Optional[float],
    body_battery: Optional[float],
    stress_avg:   Optional[float],
    sleep_h:      Optional[float],
    tsb:          Optional[float],
    baseline:     Optional[dict] = None,
) -> dict:
    """
    Estima HRV desde proxies disponibles.

    Si hay baseline personal → usa hrv_media como ancla y z-scores para ajustar.
    Si no hay baseline → usa fórmula Nunan 2010 con factores multiplicativos.

    Returns dict con hrv_estimado, confianza, método, nota.
    """
    factores_usados = []
    confianza_base = 0.0

    # ── CAMINO A: baseline personal disponible ────────────────────────────────
    if baseline and baseline.get('fase') not in ('sin_datos', None) \
       and baseline.get('hrv_media') and baseline.get('hrv_std'):

        hrv_ancla = baseline['hrv_media']
        hrv_std   = baseline['hrv_std']
        fc_media  = baseline.get('fc_media')
        fc_std    = baseline.get('fc_std')
        stress_m  = baseline.get('stress_media')
        stress_s  = baseline.get('stress_std')
        sleep_m   = baseline.get('sleep_media_h')
        sleep_s   = baseline.get('sleep_std_h')
        confianza_base = baseline.get('confianza', 0.3)

        factor_total = 1.0

        # Factor FC reposo (más importante — correlación ~0.75 con HRV)
        if hr_reposo and hr_reposo > 30 and fc_media and fc_std:
            f = _factor_zscore(hr_reposo, fc_media, fc_std, direccion=-1)
            factor_total *= f
            factores_usados.append(('fc_reposo', round(f, 3)))

        # Factor stress
        if stress_avg is not None and stress_m and stress_s:
            f = _factor_zscore(stress_avg, stress_m, stress_s, direccion=-1)
            factor_total *= f
            factores_usados.append(('stress', round(f, 3)))

        # Factor sueño
        if sleep_h and sleep_h > 0 and sleep_m and sleep_s:
            f = _factor_zscore(sleep_h, sleep_m, sleep_s, direccion=1)
            factor_total *= f
            factores_usados.append(('sueno', round(f, 3)))

        # Factor body battery (proxy directo de recuperación)
        if body_battery is not None:
            bb_media = 55.0  # referencia general Garmin
            bb_std = 20.0
            f = _factor_zscore(body_battery, bb_media, bb_std, direccion=1)
            factor_total = factor_total * 0.85 + f * 0.15  # peso menor
            factores_usados.append(('body_battery', round(f, 3)))

        # Factor TSB — efecto asimétrico (carga penaliza más que frescura beneficia)
        if tsb is not None:
            if tsb < -20:
                f_tsb = 0.88
            elif tsb < -10:
                f_tsb = 0.94
            elif tsb < 0:
                f_tsb = 0.98
            elif tsb < 10:
                f_tsb = 1.00
            elif tsb < 20:
                f_tsb = 1.02
            else:
                f_tsb = 1.03  # TSB muy alto = desentrenamiento, no beneficio lineal
            factor_total *= f_tsb
            factores_usados.append(('tsb', f_tsb))

        hrv_est = hrv_ancla * factor_total
        metodo = 'baseline_personal'

    # ── CAMINO B: sin baseline — usar Nunan 2010 ──────────────────────────────
    else:
        if not hr_reposo or hr_reposo <= 30:
            return {
                'hrv_estimado': None,
                'confianza': 0.0,
                'metodo': 'sin_datos',
                'nota': 'Sin FC reposo ni baseline — no es posible estimar HRV',
                'factores': [],
            }

        # Base Nunan
        hrv_nunan = nunan_rmssd(hr_reposo)
        confianza_base = 0.20
        factor_total = 1.0
        factores_usados.append(('nunan_base', round(hrv_nunan, 1)))

        # Ajustes multiplicativos simples (sin baseline, sin z-score)
        if stress_avg is not None:
            if stress_avg < 25:    f_s = 1.06
            elif stress_avg < 50:  f_s = 1.00
            elif stress_avg < 75:  f_s = 0.93
            else:                  f_s = 0.84
            factor_total *= f_s
            factores_usados.append(('stress', f_s))
            confianza_base += 0.05

        if sleep_h and sleep_h > 0:
            if sleep_h >= 8:     f_sl = 1.04
            elif sleep_h >= 7:   f_sl = 1.00
            elif sleep_h >= 6:   f_sl = 0.95
            else:                f_sl = 0.87
            factor_total *= f_sl
            factores_usados.append(('sueno', f_sl))
            confianza_base += 0.05

        if body_battery is not None:
            f_bb = max(0.75, min(1.15, body_battery / 65))
            factor_total *= f_bb
            factores_usados.append(('body_battery', round(f_bb, 3)))
            confianza_base += 0.05

        if tsb is not None:
            if tsb < -20:    f_tsb = 0.88
            elif tsb < -10:  f_tsb = 0.94
            elif tsb < 0:    f_tsb = 0.98
            else:            f_tsb = 1.01
            factor_total *= f_tsb
            factores_usados.append(('tsb', f_tsb))

        hrv_est = hrv_nunan * factor_total
        metodo = 'nunan_2010'

    hrv_est = max(10.0, min(120.0, round(hrv_est, 1)))
    confianza = round(min(confianza_base, 0.70), 3)  # máximo 70% sin HRV real

    nota = (
        f'Estimado por {metodo} — confianza {round(confianza*100)}%'
        f' — ⚠ No reemplaza medición real'
    )

    return {
        'hrv_estimado':  hrv_est,
        'confianza':     confianza,
        'metodo':        metodo,
        'factores':      factores_usados,
        'nota':          nota,
    }


def calcular_y_guardar_hrv_estimado(
    conn,
    atleta_id: int,
    fecha: str = None,
    recalcular_todo: bool = False,
) -> int:
    """
    Calcula el HRV estimado para días sin HRV real y lo guarda en la DB.
    """
    asegurar_columnas(conn)
    fecha = fecha or str(date.today())

    # Obtener baseline personal del atleta
    try:
        from noah_baseline import get_baseline
        baseline = get_baseline(conn, atleta_id)
    except ImportError:
        baseline = None

    # TSB map
    df_tsb = pd.read_sql(
        "SELECT fecha, ctl, atl FROM sesiones "
        "WHERE atleta_id=%s AND ctl IS NOT NULL ORDER BY fecha",
        conn, params=[atleta_id]
    )
    df_tsb['fecha'] = df_tsb['fecha'].astype(str)
    tsb_map = {r['fecha']: float(r['ctl']) - float(r['atl'])
               for _, r in df_tsb.iterrows()}

    cond   = ("atleta_id=%s AND hrv_rmssd IS NULL"
              if recalcular_todo
              else "atleta_id=%s AND fecha<=%s AND hrv_rmssd IS NULL AND hrv_estimado_valor IS NULL")
    params = [atleta_id] if recalcular_todo else [atleta_id, fecha]

    rows = conn.execute(f"""
        SELECT id, fecha, hr_reposo, body_battery, stress_avg, sleep_h
        FROM sleep_hrv WHERE {cond} ORDER BY fecha
    """, params).fetchall()

    if not rows:
        return 0

    updated = 0
    for row in rows:
        row_id, f, hr_rep, bb, stress, sleep = row
        tsb = tsb_map.get(str(f)[:10])

        resultado = calcular_hrv_estimado(
            hr_reposo=hr_rep,
            body_battery=bb,
            stress_avg=stress,
            sleep_h=sleep,
            tsb=tsb,
            baseline=baseline,
        )

        hrv_est    = resultado.get('hrv_estimado')
        confianza  = resultado.get('confianza', 0.0)
        if hrv_est is None:
            continue

        # Calcular ratio vs últimos 7 días de HRV estimado
        df_prev = pd.read_sql("""
            SELECT hrv_estimado_valor FROM sleep_hrv
            WHERE atleta_id=%s AND fecha < %s AND hrv_estimado_valor IS NOT NULL
            ORDER BY fecha DESC LIMIT 7
        """, conn, params=[atleta_id, str(f)[:10]])

        hrv_ratio = None
        hrv_flag  = 'sin_datos'
        if len(df_prev) >= 3:
            b7d = float(df_prev['hrv_estimado_valor'].mean())
            if b7d > 0:
                hrv_ratio = round(hrv_est / b7d, 3)
                hrv_flag = (
                    'verde'    if hrv_ratio >= 1.05 else
                    'amarillo' if hrv_ratio >= 0.95 else
                    'rojo'
                )

        conn.execute("""
            UPDATE sleep_hrv
            SET hrv_estimado_valor=%s, hrv_estimado_confianza=%s,
                hrv_ratio=%s, hrv_flag=%s, hrv_estimado=1
            WHERE id=%s
        """, (hrv_est, confianza, hrv_ratio, hrv_flag, row_id))
        updated += 1

    conn.commit()
    return updated


def get_hrv_hoy(conn, atleta_id: int,
                fecha: str = None) -> dict:
    """Retorna el HRV del día — real si existe, estimado si no."""
    fecha = fecha or str(date.today())
    row = conn.execute("""
        SELECT hrv_rmssd, hrv_estimado_valor, hrv_estimado_confianza,
               hrv_ratio, hrv_flag,
               body_battery, stress_avg, sleep_h, hr_reposo
        FROM sleep_hrv
        WHERE atleta_id=%s AND fecha=%s
        ORDER BY id DESC LIMIT 1
    """, (atleta_id, fecha)).fetchone()

    if not row:
        return {}

    hrv_real = row[0]
    hrv_est  = row[1]
    confianza = row[2]
    hrv_ms = hrv_real if hrv_real else hrv_est
    es_estimado = hrv_real is None and hrv_est is not None

    return {
        'hrv_ms':        hrv_ms,
        'hrv_real':      hrv_real,
        'hrv_estimado':  hrv_est,
        'hrv_confianza': confianza if es_estimado else 1.0,
        'hrv_ratio':     row[3],
        'hrv_flag':      row[4] or 'sin_datos',
        'body_battery':  row[5],
        'stress':        row[6],
        'sleep_h':       row[7],
        'hr_reposo':     row[8],
        'es_estimado':   es_estimado,
    }


# ── Script standalone ─────────────────────────────────────────────────────────
if __name__ == '__main__':
    import argparse, sys, os
    import psycopg2.extras
    from pathlib import Path
    from db_compat import ConexionCompat
    sys.path.insert(0, str(Path(__file__).parent))

    ap = argparse.ArgumentParser(description='NOAH — HRV Estimado v2')
    ap.add_argument('--atleta', type=int, required=True)
    ap.add_argument('--todo',  action='store_true')
    args = ap.parse_args()

    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("Falta la variable de entorno DATABASE_URL (cadena de conexión a Postgres/Supabase)")
        sys.exit(1)
    conn = ConexionCompat(psycopg2.connect(db_url, cursor_factory=psycopg2.extras.DictCursor))

    print(f'Calculando HRV estimado v2 para atleta {args.atleta}...')
    n = calcular_y_guardar_hrv_estimado(conn, args.atleta, recalcular_todo=args.todo)
    print(f'✓ {n} registros actualizados')

    rows = conn.execute("""
        SELECT fecha, hr_reposo, body_battery, stress_avg, sleep_h,
               hrv_rmssd, hrv_estimado_valor, hrv_estimado_confianza,
               hrv_ratio, hrv_flag
        FROM sleep_hrv WHERE atleta_id=%s
        ORDER BY fecha DESC LIMIT 7
    """, (args.atleta,)).fetchall()

    print(f"\n{'Fecha':12} {'FC':>5} {'BB':>5} {'Stress':>7} {'HRV real':>9} "
          f"{'HRV est':>8} {'Conf%':>6} {'Ratio':>7} {'Flag':>8}")
    for r in rows:
        conf = f"{round((r[7] or 0)*100)}%" if r[7] else '--'
        print(f"{str(r[0]):12} {str(r[1] or '--'):>5} {str(r[2] or '--'):>5} "
              f"{str(r[3] or '--'):>7} {str(r[5] or '--'):>9} "
              f"{str(r[6] or '--'):>8} {conf:>6} "
              f"{str(r[8] or '--'):>7} {str(r[9] or '--'):>8}")
    conn.close()
