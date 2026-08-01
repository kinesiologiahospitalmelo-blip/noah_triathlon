"""
noah_vector_semanal.py — Proyecto NOAH
=========================================
Extrae el vector de estado semanal de cada atleta para clustering
y predicción de respuesta al entrenamiento.

VECTOR DE ESTADO SEMANAL (25 features):
  Biomarcadores HRV (5)
  FC — tres fuentes (3)
  Sueño y recuperación (4)
  Carga Banister + K1/K2 (6)
  Distribución de carga por zona (6)
  Tipo de sesión (4)
  Contexto temporal (2)
  Respuesta semana siguiente (4) — etiqueta natural

FILOSOFÍA:
  - Features normalizados al baseline personal (no poblacional)
  - Ratios en lugar de valores absolutos donde es posible
  - Duración continua Z1/Z2 como feature propio
  - K1/K2 estimados desde el historial individual

REFERENCIAS:
  Banister et al. 1975, Coggan 2003, Seiler 2010,
  Plews et al. 2013, Stöggl & Sperlich 2014
"""

from __future__ import annotations
import psycopg2
import numpy as np
import pandas as pd
from datetime import date, timedelta
from typing import Optional


# ─── Helper pd.read_sql → _read_sql (pandas 2.x no soporta DBAPI2 directo) ────


# ── Deteccion de fase del mesociclo ──────────────────────────────────────
# Modelo fisiologico:
#   Issurin 2008/2010  — Block Periodization (A/T/R)
#   Banister 1975      — Fitness-Fatigue (CTL/ATL/TSB)
#   Mujika 2003/2010   — Taper optimo
#   Plews/Buchheit 2013 — HRV como proxy de absorcion
#   Gabbett 2016       — ACWR zona segura

def detectar_fase_mesociclo(conn, atleta_id, fecha_referencia):
    """
    Detecta la fase del mesociclo usando multiples senales fisiologicas.

    Senales de carga (todos los atletas):
      - CTL trend y ramp rate (Banister)
      - ACWR: ratio ATL/CTL (Gabbett) — zona segura 0.8-1.3
      - TSB: forma/frescura
      - Distribucion por zonas: Z1-Z2 vs Z3+ (Issurin)
      - Sesiones de calidad (Z4+): indicador de transmutacion
      - Eficiencia cardiaca: HR vs pace para mismo esfuerzo

    Senales de recuperacion (atletas con biomarcadores):
      - HRV RMSSD trend + CV (Plews/Buchheit)
      - Hanna Life (proxy integrado de readiness)
      - Sueno (horas y calidad)
      - FC nocturna (drift = fatiga acumulada)

    Contexto:
      - Con carrera A a <=3 semanas -> taper (Mujika 2003)
      - Con carrera A a >3 semanas -> preparacion
      - Sin carrera -> mejora_general (progresion sostenible de CTL)

    Returns dict con:
      fase, confianza, en_taper, semanas_para_carrera, contexto,
      acwr, ramp_rate_pct, absorcion (solo si hay bio)
    """
    from datetime import date, timedelta
    import numpy as _np

    if isinstance(fecha_referencia, str):
        fecha_referencia = date.fromisoformat(fecha_referencia[:10])

    resultado = {
        'fase': 'A', 'confianza': 0.3, 'semana_en_bloque': 1,
        'en_taper': False, 'semanas_para_carrera': None,
        'contexto': 'mejora_general', 'acwr': None,
        'ramp_rate_pct': None, 'absorcion': None,
    }

    # ── 1. TSS semanal + CTL/ATL de las ultimas 8 semanas ────────────────
    fecha_desde = fecha_referencia - timedelta(days=8 * 7)
    rows_tss = conn.execute("""
        SELECT to_char(fecha::date, 'IYYY-IW') as sem,
               SUM(COALESCE(tss_total, 0)) as tss,
               COUNT(*) as n_ses,
               SUM(CASE WHEN tss_z56 > 0 OR tipo_sesion ILIKE '%%umbral%%'
                    OR tipo_sesion ILIKE '%%vo2%%' OR tipo_sesion ILIKE '%%calidad%%'
                    OR tipo_sesion ILIKE '%%series%%' THEN 1 ELSE 0 END) as n_calidad,
               SUM(COALESCE(tss_z12, 0)) as sum_z12,
               SUM(COALESCE(tss_z34, 0)) as sum_z34,
               SUM(COALESCE(tss_z56, 0)) as sum_z56
        FROM sesiones
        WHERE atleta_id=%s AND fecha >= %s AND fecha <= %s
        GROUP BY sem ORDER BY sem
    """, (atleta_id, str(fecha_desde), str(fecha_referencia))).fetchall()

    if len(rows_tss) < 2:
        return resultado

    tss_vals = [float(r[1]) for r in rows_tss]
    n_calidad_vals = [int(r[3] or 0) for r in rows_tss]
    z12_vals = [float(r[4] or 0) for r in rows_tss]
    z56_vals = [float(r[6] or 0) for r in rows_tss]

    # ── 2. CTL / ATL actual ──────────────────────────────────────────────
    row_ctl = conn.execute("""
        SELECT ctl, atl, tsb FROM sesiones
        WHERE atleta_id=%s AND ctl IS NOT NULL
        ORDER BY fecha DESC, id DESC LIMIT 1
    """, (atleta_id,)).fetchone()

    ctl_actual = float(row_ctl[0]) if row_ctl and row_ctl[0] else None
    atl_actual = float(row_ctl[1]) if row_ctl and row_ctl[1] else None
    tsb_actual = float(row_ctl[2]) if row_ctl and row_ctl[2] else None

    # ACWR (Gabbett 2016): ATL/CTL, zona segura 0.8-1.3
    acwr = None
    if ctl_actual and ctl_actual > 0 and atl_actual is not None:
        acwr = round(atl_actual / ctl_actual, 2)
        resultado['acwr'] = acwr

    # Ramp rate: delta CTL ultima semana vs CTL (>5-7% = riesgo)
    ramp_rate_pct = None
    if len(tss_vals) >= 2 and ctl_actual and ctl_actual > 10:
        # CTL de hace 1 semana (aproximado desde TSS)
        row_ctl_prev = conn.execute("""
            SELECT ctl FROM sesiones
            WHERE atleta_id=%s AND ctl IS NOT NULL
            AND fecha <= %s
            ORDER BY fecha DESC, id DESC LIMIT 1
        """, (atleta_id, str(fecha_referencia - timedelta(days=7)))).fetchone()
        if row_ctl_prev and row_ctl_prev[0]:
            delta = ctl_actual - float(row_ctl_prev[0])
            ramp_rate_pct = round(delta / ctl_actual * 100, 1)
            resultado['ramp_rate_pct'] = ramp_rate_pct

    # ── 3. Carrera y taper (Mujika 2003) ─────────────────────────────────
    carrera_row = conn.execute("""
        SELECT fecha FROM carreras
        WHERE atleta_id=%s AND prioridad='A' AND estado='pendiente'
        AND fecha > %s ORDER BY fecha ASC LIMIT 1
    """, (atleta_id, str(fecha_referencia))).fetchone()

    if carrera_row:
        dias = (date.fromisoformat(str(carrera_row[0])[:10]) - fecha_referencia).days
        resultado['semanas_para_carrera'] = max(0, dias // 7)
        if resultado['semanas_para_carrera'] <= 3:
            resultado['en_taper'] = True
            resultado['contexto'] = 'taper'
        else:
            resultado['contexto'] = 'preparacion_carrera'
    else:
        resultado['contexto'] = 'mejora_general'

    # ── 4. Senales de recuperacion (si hay bio) ──────────────────────────
    absorcion = None
    fecha_bio_desde = fecha_referencia - timedelta(days=21)
    rows_bio = conn.execute("""
        SELECT hrv_rmssd, hanna_life, fc_nocturna, sleep_h
        FROM sleep_hrv
        WHERE atleta_id=%s AND fecha >= %s AND fecha <= %s
        ORDER BY fecha
    """, (atleta_id, str(fecha_bio_desde), str(fecha_referencia))).fetchall()

    tiene_bio = len(rows_bio) >= 5
    hrv_trend = None
    hrv_cv = None

    if tiene_bio:
        hrv_vals = [float(r[0]) for r in rows_bio if r[0] and float(r[0]) > 10]
        if len(hrv_vals) >= 5:
            # Plews/Buchheit: media semanal + CV
            hrv_media = _np.mean(hrv_vals)
            hrv_cv = round(float(_np.std(hrv_vals) / hrv_media * 100), 1) if hrv_media > 0 else None

            # Trend: slope de los ultimos valores
            x = _np.arange(len(hrv_vals), dtype=float)
            slope = float(_np.polyfit(x, hrv_vals, 1)[0])
            hrv_trend = 'subiendo' if slope > 0.3 else ('bajando' if slope < -0.3 else 'estable')

            # Absorcion (Plews 2013):
            #   HRV estable/subiendo + CV moderado (5-10%) = buena absorcion
            #   HRV bajando + CV bajo (<3%) = overreaching no funcional
            #   HRV bajando + CV alto (>12%) = fatiga aguda (recuperable)
            if hrv_trend == 'bajando' and hrv_cv is not None and hrv_cv < 3:
                absorcion = 'overreaching'
            elif hrv_trend == 'bajando' and hrv_cv is not None and hrv_cv > 12:
                absorcion = 'fatiga_aguda'
            elif hrv_trend in ('estable', 'subiendo'):
                absorcion = 'buena'
            else:
                absorcion = 'moderada'

        # Hanna Life como factor adicional
        hanna_vals = [float(r[1]) for r in rows_bio if r[1]]
        if hanna_vals:
            hanna_media = _np.mean(hanna_vals)
            if hanna_media < 35:
                absorcion = 'overreaching' if absorcion != 'overreaching' else absorcion

        resultado['absorcion'] = absorcion

    # ── 5. Clasificacion de fase (Issurin 2008) ──────────────────────────
    avg_tss = sum(tss_vals) / len(tss_vals) if tss_vals else 1
    if avg_tss == 0:
        avg_tss = 1
    current_tss = tss_vals[-1]
    ratio_tss = current_tss / avg_tss

    # Distribucion de zonas de la ultima semana
    z12_last = z12_vals[-1] if z12_vals else 0
    z56_last = z56_vals[-1] if z56_vals else 0
    tss_last = tss_vals[-1] if tss_vals else 1
    pct_z12 = (z12_last / tss_last * 100) if tss_last > 0 else 50
    pct_z56 = (z56_last / tss_last * 100) if tss_last > 0 else 0
    n_calidad_last = n_calidad_vals[-1] if n_calidad_vals else 0

    # Tendencia TSS (subiendo/bajando)
    if len(tss_vals) >= 3:
        tendencia_tss = tss_vals[-1] - _np.mean(tss_vals[-3:-1])
    elif len(tss_vals) >= 2:
        tendencia_tss = tss_vals[-1] - tss_vals[-2]
    else:
        tendencia_tss = 0

    # Semanas consecutivas subiendo
    semanas_subiendo = 0
    for j in range(len(tss_vals) - 1, 0, -1):
        if tss_vals[j] >= tss_vals[j-1] * 0.85:
            semanas_subiendo += 1
        else:
            break

    # --- TAPER: forzar R si estamos en ventana de taper ---
    if resultado['en_taper']:
        resultado['fase'] = 'R'
        resultado['confianza'] = 0.9
        resultado['semana_en_bloque'] = 4
        return resultado

    # --- CLASIFICACION MULTISENIAL ---
    score_A = 0  # acumulacion
    score_T = 0  # transmutacion
    score_R = 0  # recuperacion/realizacion

    # Senal 1: Volumen (TSS relativo al promedio)
    if ratio_tss >= 0.85:
        score_A += 2
    if ratio_tss >= 1.10:
        score_T += 2
    if ratio_tss < 0.65:
        score_R += 3

    # Senal 2: Distribucion por zonas (Issurin)
    # A = Z1-Z2 dominante (>70%), T = Z3-Z5 dominante, R = bajo volumen
    if pct_z12 > 70:
        score_A += 2
    if pct_z56 > 15 or n_calidad_last >= 2:
        score_T += 2
    if n_calidad_last == 0 and ratio_tss < 0.75:
        score_R += 2

    # Senal 3: ACWR (Gabbett 2016)
    if acwr is not None:
        if 0.8 <= acwr <= 1.3:
            score_A += 1  # zona segura, puede acumular
        elif acwr > 1.5:
            score_R += 2  # peligro, necesita bajar
            score_T += 1  # o esta en pico de transmutacion

    # Senal 4: Ramp rate (Banister)
    if ramp_rate_pct is not None:
        if ramp_rate_pct > 7:
            score_R += 2  # riesgo, deberia descargar
        elif ramp_rate_pct > 5:
            score_T += 1  # carga alta, posible transmutacion
        elif 0 < ramp_rate_pct <= 5:
            score_A += 1  # progresion saludable

    # Senal 5: TSB (forma)
    if tsb_actual is not None:
        if tsb_actual < -20:
            score_R += 2  # fatiga profunda
        elif tsb_actual < -10:
            score_T += 1  # carga funcional
        elif tsb_actual > 5:
            score_R += 1  # fresco (post-recovery o detraining)

    # Senal 6: Tendencia de TSS
    if tendencia_tss > 0:
        score_A += 1  # construyendo
    elif tendencia_tss < -avg_tss * 0.3:
        score_R += 1  # bajando significativamente

    # Senal 7: Bio (si disponible) — Plews/Buchheit
    if tiene_bio and absorcion:
        if absorcion == 'overreaching':
            score_R += 3  # senal fuerte de que necesita descargar
            score_A -= 1
        elif absorcion == 'fatiga_aguda':
            score_R += 1
        elif absorcion == 'buena':
            score_A += 1  # absorbiendo bien, puede seguir acumulando

    # Determinar fase por score maximo
    scores = {'A': score_A, 'T': score_T, 'R': score_R}
    fase = max(scores, key=scores.get)
    score_max = scores[fase]
    score_total = sum(scores.values()) or 1
    confianza = round(min(0.95, score_max / score_total), 2)

    # Semana en bloque
    if fase == 'A':
        semana_en_bloque = min(semanas_subiendo + 1, 3)
    elif fase == 'T':
        semana_en_bloque = 3
    else:
        semana_en_bloque = 4

    resultado['fase'] = fase
    resultado['confianza'] = confianza
    resultado['semana_en_bloque'] = semana_en_bloque

    return resultado


def _read_sql(sql, conn, params=None):
    import pandas as pd
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
    except Exception:
        # Transaccion abortada por error previo — hacer rollback y reintentar
        try:
            conn.rollback()
        except Exception:
            pass
        cur = conn.cursor()
        cur.execute(sql, params)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    return pd.DataFrame(rows, columns=cols)


# ── Constantes de Banister estándar (punto de partida) ───────────────────────
TAU_CTL_STD = 42
TAU_ATL_STD = 7


def _safe(v, default=0.0):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return default
    return float(v)


def estimar_k1_k2(conn, atleta_id: int,
                   semanas: int = 16) -> dict:
    """
    Estima K1 (ganancia de fitness) y K2 (ganancia de fatiga) individuales
    desde el historial de CTL/ATL del atleta.

    Método: regresión lineal sobre la relación TSS → delta_CTL y TSS → delta_ATL
    en ventanas de tiempo donde el atleta entrenó consistentemente.

    Confianza baja si hay menos de 8 semanas de datos consistentes.
    """
    df = _read_sql("""
        SELECT fecha, ctl, atl, tss_total
        FROM sesiones
        WHERE atleta_id=%s AND ctl IS NOT NULL AND tss_total > 0
        ORDER BY fecha
    """, conn, params=[atleta_id])

    if len(df) < 14:
        return {'k1': None, 'k2': None, 'tau_ctl': TAU_CTL_STD,
                'tau_atl': TAU_ATL_STD, 'confianza': 0.0, 'n': len(df)}

    df['fecha'] = pd.to_datetime(df['fecha'])
    df = df.sort_values('fecha').reset_index(drop=True)

    # Calcular delta CTL y delta ATL día a día
    df['delta_ctl'] = df['ctl'].diff()
    df['delta_atl'] = df['atl'].diff()
    df = df.dropna()

    # K1: pendiente de la regresión TSS → delta_CTL
    # Teórico: delta_CTL = TSS/TAU_CTL - CTL/TAU_CTL → K1 = 1/TAU_CTL individual
    from numpy.polynomial import polynomial as P
    try:
        # Usar últimas `semanas` semanas para que sea relevante
        n_dias = semanas * 7
        df_rec = df.tail(n_dias)

        if len(df_rec) < 14:
            raise ValueError("Datos insuficientes")

        # Estimar tau_CTL desde la autocorrelación de CTL
        ctl_vals = df_rec['ctl'].values
        if len(ctl_vals) > 20:
            # Usar todos los puntos disponibles para mejor estimación
            r1 = np.corrcoef(ctl_vals[:-1], ctl_vals[1:])[0, 1]
            # tau = -1/ln(r) pero solo si r es válido y positivo
            if r1 > 0.5 and r1 < 1.0:  # correlación mínima para ser confiable
                tau_ctl_est = -1 / np.log(r1)
                # Rango fisiológico estricto (Banister): 28-56 días
                tau_ctl_est = max(28, min(56, tau_ctl_est))
            else:
                tau_ctl_est = TAU_CTL_STD
        else:
            tau_ctl_est = TAU_CTL_STD

        atl_vals = df_rec['atl'].values
        if len(atl_vals) > 14:
            r2 = np.corrcoef(atl_vals[:-1], atl_vals[1:])[0, 1]
            if r2 > 0.3 and r2 < 1.0:
                tau_atl_est = -1 / np.log(r2)
                # Rango fisiológico: 5-14 días
                tau_atl_est = max(5, min(14, tau_atl_est))
            else:
                tau_atl_est = TAU_ATL_STD
        else:
            tau_atl_est = TAU_ATL_STD

        # K1 y K2 como sensibilidad al TSS
        k1 = 1.0 / tau_ctl_est
        k2 = 1.0 / tau_atl_est

        confianza = min(1.0, len(df_rec) / (semanas * 7 * 0.7))

        return {
            'k1':        round(k1, 5),
            'k2':        round(k2, 5),
            'tau_ctl':   round(tau_ctl_est, 1),
            'tau_atl':   round(tau_atl_est, 1),
            'confianza': round(confianza, 2),
            'n':         len(df_rec),
        }
    except Exception as e:
        return {'k1': None, 'k2': None, 'tau_ctl': TAU_CTL_STD,
                'tau_atl': TAU_ATL_STD, 'confianza': 0.0, 'n': 0}


def extraer_vector_semana(
    conn,
    atleta_id: int,
    fecha_lunes: date,
    baseline: Optional[dict] = None,
    k_params: Optional[dict] = None,
    semanas_hasta_carrera: Optional[int] = None,
    semana_del_mesociclo: Optional[int] = None,
) -> Optional[dict]:
    """
    Extrae el vector de estado semanal para una semana específica.

    Args:
        fecha_lunes: primer día de la semana (lunes)
        baseline: baseline personal del atleta (de noah_baseline)
        k_params: parámetros K1/K2/tau estimados
        semanas_hasta_carrera: contexto temporal
        semana_del_mesociclo: 1-4 dentro del mesociclo 3+1

    Returns:
        dict con 34 features + metadata
    """
    fecha_dom = fecha_lunes + timedelta(days=6)
    fecha_sig_lun = fecha_lunes + timedelta(days=7)
    fecha_sig_dom = fecha_lunes + timedelta(days=13)

    # ── Cargar biomarcadores de la semana ─────────────────────────────────────
    df_bio = _read_sql("""
        SELECT fecha, hrv_rmssd, hrv_estimado_valor, hrv_estimado,
               fc_nocturna as hr_reposo,
               sleep_h, deep_h, rem_h, stress_avg, sleep_stress_avg,
               spo2_avg, body_battery, hanna_life,
               stress_intra, fc_media_dia,
               hanna_vfc_ratio, estado_autonomico
        FROM sleep_hrv
        WHERE atleta_id=%s AND fecha BETWEEN %s AND %s
        ORDER BY fecha
    """, conn, params=[atleta_id, str(fecha_lunes), str(fecha_dom)])

    # (bio puede estar vacio — atletas sin wearable de sueño/HRV)

    # Crear columnas hrv (funciona OK con DataFrame vacio)
    df_bio['hrv'] = df_bio['hrv_rmssd'].combine_first(df_bio['hrv_estimado_valor'])
    df_bio['hrv_real'] = df_bio['hrv_rmssd'].notna()

    # ── Cargar sesiones de la semana ──────────────────────────────────────────
    df_ses = _read_sql("""
        SELECT id, fecha, sport, ctl, atl, tss_total,
               tss_z12, tss_z34, tss_z56,
               tipo_sesion, session_type, duration_min, distance_km,
               hr_avg, np_watts, intensity_factor, if_sesion,
               hr_zone_1_s, hr_zone_2_s, hr_zone_3_s,
               hr_zone_4_s, hr_zone_5_s,
               power_avg, power_np, ftp_sesion,
               n_laps, n_series, cumplimiento_pct
        FROM sesiones
        WHERE atleta_id=%s AND fecha BETWEEN %s AND %s
        ORDER BY fecha
    """, conn, params=[atleta_id, str(fecha_lunes), str(fecha_dom)])

    # ── Cargar laps para calcular duración continua ───────────────────────────
    df_laps = _read_sql("""
        SELECT l.sesion_id, l.duration_min, l.hr_avg, l.avg_power,
               s.fecha, s.sport
        FROM laps l
        JOIN sesiones s ON l.sesion_id = s.id
        WHERE s.atleta_id=%s AND s.fecha BETWEEN %s AND %s
        ORDER BY s.fecha, l.lap_num
    """, conn, params=[atleta_id, str(fecha_lunes), str(fecha_dom)])

    # ── Cargar FC intradiaria ─────────────────────────────────────────────────
    df_intra = _read_sql("""
        SELECT fecha, AVG(hr_bpm) as fc_intra_media
        FROM fc_intradiaria
        WHERE atleta_id=%s AND fecha BETWEEN %s AND %s
        GROUP BY fecha
    """, conn, params=[atleta_id, str(fecha_lunes), str(fecha_dom)])

    # ── Cargar semana siguiente (etiqueta natural) ────────────────────────────
    df_bio_sig = _read_sql("""
        SELECT hrv_rmssd, hrv_estimado_valor, hanna_life
        FROM sleep_hrv
        WHERE atleta_id=%s AND fecha BETWEEN %s AND %s
    """, conn, params=[atleta_id, str(fecha_sig_lun), str(fecha_sig_dom)])

    df_ses_sig = _read_sql("""
        SELECT MAX(ctl) as ctl_fin FROM sesiones
        WHERE atleta_id=%s AND fecha BETWEEN %s AND %s
    """, conn, params=[atleta_id, str(fecha_sig_lun), str(fecha_sig_dom)])

    # ── Baseline personal ─────────────────────────────────────────────────────
    hrv_baseline = baseline.get('hrv_media') if baseline else None
    hrv_std      = baseline.get('hrv_std', 10) if baseline else 10
    fc_min_hist  = baseline.get('fc_min_historico') if baseline else None
    sleep_base   = baseline.get('sleep_media_h') if baseline else None
    hanna_base   = 60.0

    # Fallback: calcular baseline directo desde DB si no viene del módulo
    if not hrv_baseline:
        # Fecha relativa calculada en Python — date('now','-30 days')
        # (SQLite) no existe en Postgres.
        fecha_lim_30 = str(date.today() - timedelta(days=30))
        r_bl = conn.execute("""
            SELECT AVG(hrv_rmssd), MIN(fc_nocturna), AVG(sleep_h)
            FROM sleep_hrv
            WHERE atleta_id=%s AND hrv_rmssd > 10
            AND fecha < %s
        """, (atleta_id, fecha_lim_30)).fetchone()
        if r_bl and r_bl[0]:
            hrv_baseline = float(r_bl[0])
        if not fc_min_hist and r_bl and r_bl[1]:
            # fc_nocturna mínima histórica (percentil 5 aproximado)
            fc_p5 = conn.execute("""
                SELECT hrv_rmssd FROM (
                    SELECT fc_nocturna as hrv_rmssd FROM sleep_hrv
                    WHERE atleta_id=%s AND fc_nocturna > 30
                    ORDER BY fc_nocturna ASC LIMIT 10
                ) sub
            """, (atleta_id,)).fetchall()
            if fc_p5:
                fc_min_hist = float(np.mean([r[0] for r in fc_p5]))                    if len(fc_p5) > 0 else None

    # ── K1/K2 ─────────────────────────────────────────────────────────────────
    k1 = k_params.get('k1') if k_params else None
    k2 = k_params.get('k2') if k_params else None

    # ── CTL inicio y fin de semana ────────────────────────────────────────────
    ctl_inicio = None
    ctl_fin    = None
    if not df_ses.empty and 'ctl' in df_ses.columns:
        ctls_validos = df_ses['ctl'].dropna()
        if len(ctls_validos) > 0:
            ctl_inicio = float(ctls_validos.iloc[0])
            ctl_fin    = float(ctls_validos.iloc[-1])
    delta_ctl = (ctl_fin - ctl_inicio) if (ctl_inicio and ctl_fin) else None

    atl_vals = df_ses['atl'].dropna() if not df_ses.empty else pd.Series()
    atl_media = float(atl_vals.mean()) if len(atl_vals) > 0 else None
    tsb_inicio = (ctl_inicio - atl_media) if (ctl_inicio and atl_media) else None
    ramp_rate  = (delta_ctl / ctl_inicio * 100) if (delta_ctl and ctl_inicio) else None

    # ── HRV features ──────────────────────────────────────────────────────────
    hrv_vals = df_bio['hrv'].dropna().values
    hrv_media_sem = float(np.mean(hrv_vals)) if len(hrv_vals) > 0 else None
    hrv_ratio = (hrv_media_sem / hrv_baseline) if (hrv_media_sem and hrv_baseline) else None

    # Slope HRV 7 días (esta semana)
    slope_hrv_7d = None
    if len(hrv_vals) >= 4:
        x = np.arange(len(hrv_vals), dtype=float)
        y = hrv_vals.astype(float)
        mask = ~np.isnan(y)
        if mask.sum() >= 3:
            slope_hrv_7d = float(np.polyfit(x[mask], y[mask], 1)[0])

    # Slope HRV 28 días (desde 3 semanas antes)
    slope_hrv_28d = None
    fecha_28 = fecha_lunes - timedelta(days=21)
    df_hrv_28 = _read_sql("""
        SELECT hrv_rmssd, hrv_estimado_valor FROM sleep_hrv
        WHERE atleta_id=%s AND fecha BETWEEN %s AND %s
        ORDER BY fecha
    """, conn, params=[atleta_id, str(fecha_28), str(fecha_dom)])
    if len(df_hrv_28) >= 10:
        hrv_28 = df_hrv_28['hrv_rmssd'].combine_first(df_hrv_28['hrv_estimado_valor']).dropna().values
        if len(hrv_28) >= 10:
            x28 = np.arange(len(hrv_28), dtype=float)
            slope_hrv_28d = float(np.polyfit(x28, hrv_28.astype(float), 1)[0])

    # Ratio HRV/ATL — tolerancia a la carga
    ratio_hrv_carga = (hrv_media_sem / atl_media) if (hrv_media_sem and atl_media and atl_media > 0) else None

    # ── FC features ───────────────────────────────────────────────────────────
    # FC nocturna — viene como fc_nocturna en sleep_hrv (alias hr_reposo en query)
    fc_vals = df_bio['hr_reposo'].dropna() if 'hr_reposo' in df_bio.columns else pd.Series()
    fc_vals = fc_vals[fc_vals > 30]
    # Fallback a hr_reposo si fc_nocturna está vacía
    if len(fc_vals) == 0 and 'fc_nocturna' in df_bio.columns:
        fc_vals = df_bio['fc_nocturna'].dropna()
        fc_vals = fc_vals[fc_vals > 30]
    fc_nocturna_media = float(fc_vals.mean()) if len(fc_vals) > 0 else None
    # fc_min_hist viene del baseline (mínimo histórico de FC en reposo)
    fc_nocturna_ratio = (fc_nocturna_media / fc_min_hist) if (fc_nocturna_media and fc_min_hist) else None

    # FC intradiaria
    fc_intra_media = None
    if not df_intra.empty:
        fc_intra_media = float(df_intra['fc_intra_media'].mean())

    # Slope FC reposo 7 días
    slope_fc_7d = None
    if len(fc_vals) >= 4:
        x = np.arange(len(fc_vals), dtype=float)
        slope_fc_7d = float(np.polyfit(x, fc_vals.values.astype(float), 1)[0])

    # ── Sueño y recuperación ──────────────────────────────────────────────────
    sleep_vals = df_bio['sleep_h'].dropna()
    sleep_vals = sleep_vals[sleep_vals > 0]
    sleep_media = float(sleep_vals.mean()) if len(sleep_vals) > 0 else None

    # Calidad sueño (deep + rem / total)
    sleep_cal = None
    if 'deep_h' in df_bio.columns and 'rem_h' in df_bio.columns:
        df_sleep_q = df_bio[(df_bio['sleep_h'] > 0) &
                            (df_bio['deep_h'].notna() | df_bio['rem_h'].notna())]
        if len(df_sleep_q) > 0:
            deep  = df_sleep_q['deep_h'].fillna(0)
            rem   = df_sleep_q['rem_h'].fillna(0)
            total = df_sleep_q['sleep_h']
            valid = total > 0
            if valid.any():
                sleep_cal = float(((deep + rem) / total)[valid].mean())

    hanna_vals = df_bio['hanna_life'].dropna()
    hanna_media = float(hanna_vals.mean()) if len(hanna_vals) > 0 else None

    spo2_vals = df_bio['spo2_avg'].dropna()
    spo2_media = float(spo2_vals.mean()) if len(spo2_vals) > 0 else None

    # ── Carga por zona ────────────────────────────────────────────────────────
    tss_total_sem = 0.0
    tss_z12 = tss_z34 = tss_z56 = 0.0
    seg_z12 = seg_z34 = seg_z56 = 0.0

    if not df_ses.empty:
        tss_total_sem = float(df_ses['tss_total'].fillna(0).sum())

        # TSS por zona desde tabla
        tss_z12 = float(df_ses['tss_z12'].fillna(0).sum()) if 'tss_z12' in df_ses.columns else 0.0
        tss_z34 = float(df_ses['tss_z34'].fillna(0).sum()) if 'tss_z34' in df_ses.columns else 0.0
        tss_z56 = float(df_ses['tss_z56'].fillna(0).sum()) if 'tss_z56' in df_ses.columns else 0.0

        # Si no hay TSS por zona, calcular desde segundos por zona de FC
        if tss_z12 == 0 and 'hr_zone_1_s' in df_ses.columns:
            seg_z12 = float(df_ses[['hr_zone_1_s','hr_zone_2_s']].fillna(0).sum().sum())
            seg_z34 = float(df_ses[['hr_zone_3_s','hr_zone_4_s']].fillna(0).sum().sum())
            seg_z56 = float(df_ses['hr_zone_5_s'].fillna(0).sum())
            seg_total = seg_z12 + seg_z34 + seg_z56
            if seg_total > 0 and tss_total_sem > 0:
                # Distribuir TSS proporcionalmente a los segundos por zona
                # con factor de intensidad: Z1/Z2 × 0.5, Z3/Z4 × 1.0, Z5/Z6 × 1.5
                peso_z12 = seg_z12 * 0.5
                peso_z34 = seg_z34 * 1.0
                peso_z56 = seg_z56 * 1.5
                peso_total = peso_z12 + peso_z34 + peso_z56
                if peso_total > 0:
                    tss_z12 = tss_total_sem * peso_z12 / peso_total
                    tss_z34 = tss_total_sem * peso_z34 / peso_total
                    tss_z56 = tss_total_sem * peso_z56 / peso_total

    pct_z12 = (tss_z12 / tss_total_sem * 100) if tss_total_sem > 0 else 0
    pct_z34 = (tss_z34 / tss_total_sem * 100) if tss_total_sem > 0 else 0
    pct_z56 = (tss_z56 / tss_total_sem * 100) if tss_total_sem > 0 else 0

    # ── Duración continua en Z1/Z2 ────────────────────────────────────────────
    # Sesiones de más de 45min donde el HR promedio estuvo en Z1/Z2
    min_continuo_z12_max = 0.0
    n_sesiones_z12_45plus = 0

    if not df_ses.empty:
        lthr = conn.execute('SELECT lthr_run FROM atletas WHERE id=%s',
                           (atleta_id,)).fetchone()
        lthr_val = lthr[0] if lthr and lthr[0] else 162

        for _, ses in df_ses.iterrows():
            dur = _safe(ses.get('duration_min', 0))
            hr  = _safe(ses.get('hr_avg', 0))
            if dur > 0 and hr > 0:
                # Z1/Z2: < 88% LTHR
                if hr < lthr_val * 0.88 and dur >= 30:
                    min_continuo_z12_max = max(min_continuo_z12_max, dur)
                    if dur >= 45:
                        n_sesiones_z12_45plus += 1

    # ── Tipo de sesión ────────────────────────────────────────────────────────
    n_sesiones_calidad = 0    # Z4+
    n_sesiones_continuo_umbral = 0
    n_sesiones_fraccionado_umbral = 0
    n_sesiones_vo2 = 0
    n_sesiones_neuro = 0

    if not df_ses.empty:
        for _, ses in df_ses.iterrows():
            tipo = (str(ses.get('tipo_sesion', '') or '') +
                    ' ' + str(ses.get('session_type', '') or '')).lower()
            ses_id = ses.get('id') or ses.name
            laps_ses = df_laps[df_laps['sesion_id'] == ses_id] if not df_laps.empty else pd.DataFrame()
            n_laps_ses = len(laps_ses)

            if any(k in tipo for k in ['ftp', 'umbral', 'z4', 'threshold', 'tempo', 'calidad']):
                n_sesiones_calidad += 1
                # Continuo: 1-2 laps; fraccionado: 3+ laps (series)
                if n_laps_ses <= 2:
                    n_sesiones_continuo_umbral += 1
                else:
                    n_sesiones_fraccionado_umbral += 1
            elif any(k in tipo for k in ['vo2', 'z5', 'velocidad', 'intervals']):
                n_sesiones_calidad += 1
                n_sesiones_vo2 += 1
            elif any(k in tipo for k in ['neuro', 'z6', 'sprint', 'atp', 'neuromuscular']):
                n_sesiones_calidad += 1
                n_sesiones_neuro += 1
            elif any(k in tipo for k in ['z4', 'series', 'series_400', 'intervalos']):
                n_sesiones_calidad += 1
                n_sesiones_fraccionado_umbral += 1

    # ── Contexto temporal ─────────────────────────────────────────────────────
    sem_hasta_carrera = semanas_hasta_carrera
    sem_mesociclo     = semana_del_mesociclo

    # Si no se pasan, intentar calcularlos desde la DB
    if sem_hasta_carrera is None:
        carrera_A = conn.execute("""
            SELECT fecha FROM carreras
            WHERE atleta_id=%s AND prioridad='A' AND estado='pendiente'
            AND fecha > %s
            ORDER BY fecha ASC LIMIT 1
        """, (atleta_id, str(fecha_dom))).fetchone()
        if carrera_A:
            sem_hasta_carrera = (date.fromisoformat(carrera_A[0]) - fecha_dom).days // 7

    if sem_mesociclo is None:
        # Estimar desde el historial de semanas — strftime("%Y-W%W",...)
        # (SQLite) reemplazado por to_char(...,'IYYY-IW') (formato semana
        # ISO de Postgres), mismo patrón usado en el resto del proyecto.
        n_sem_desde_inicio = conn.execute("""
            SELECT COUNT(DISTINCT to_char(fecha::date, 'IYYY-IW'))
            FROM sesiones WHERE atleta_id=%s AND fecha <= %s
        """, (atleta_id, str(fecha_dom))).fetchone()
        if n_sem_desde_inicio:
            sem_mesociclo = (n_sem_desde_inicio[0] % 4) + 1

    # ── Respuesta semana siguiente (etiqueta natural) ─────────────────────────
    delta_ctl_sig = None
    hrv_ratio_sig = None
    hanna_sig     = None

    if not df_ses_sig.empty and ctl_fin:
        ctl_sig = df_ses_sig['ctl_fin'].iloc[0]
        if ctl_sig:
            delta_ctl_sig = float(ctl_sig) - ctl_fin

    if not df_bio_sig.empty:
        hrv_sig_vals = df_bio_sig['hrv_rmssd'].combine_first(
            df_bio_sig['hrv_estimado_valor']).dropna().values
        if len(hrv_sig_vals) > 0 and hrv_media_sem:
            hrv_ratio_sig = float(np.mean(hrv_sig_vals)) / hrv_media_sem

        hl_sig = df_bio_sig['hanna_life'].dropna()
        if len(hl_sig) > 0:
            hanna_sig = float(hl_sig.mean())

    # ── Construir vector final ────────────────────────────────────────────────
    vector = {
        # Metadata
        'atleta_id':    atleta_id,
        'fecha_lunes':  str(fecha_lunes),
        'n_dias_bio':   len(df_bio),
        'n_sesiones':   len(df_ses),
        'hrv_real_pct': float(df_bio['hrv_real'].mean()) if not df_bio.empty else 0.0,

        # Biomarcadores HRV
        'hrv_rmssd_media':   round(hrv_media_sem, 2) if hrv_media_sem else None,
        'hrv_rmssd_ratio':   round(hrv_ratio, 3) if hrv_ratio else None,
        'slope_hrv_7d':      round(slope_hrv_7d, 4) if slope_hrv_7d is not None else None,
        'slope_hrv_28d':     round(slope_hrv_28d, 4) if slope_hrv_28d is not None else None,
        'ratio_hrv_carga':   round(ratio_hrv_carga, 3) if ratio_hrv_carga else None,

        # FC — tres fuentes
        'fc_nocturna_ratio': round(fc_nocturna_ratio, 3) if fc_nocturna_ratio else None,
        'fc_intradiaria':    round(fc_intra_media, 1) if fc_intra_media else None,
        'slope_fc_7d':       round(slope_fc_7d, 4) if slope_fc_7d is not None else None,

        # Sueño y recuperación
        'sleep_h_media':     round(sleep_media, 2) if sleep_media else None,
        'sleep_calidad':     round(sleep_cal, 3) if sleep_cal else None,
        'hanna_life_media':  round(hanna_media, 1) if hanna_media else None,
        'spo2_media':        round(spo2_media, 1) if spo2_media else None,

        # Carga Banister
        'ctl_inicio':        round(ctl_inicio, 1) if ctl_inicio else None,
        'delta_ctl':         round(delta_ctl, 2) if delta_ctl is not None else None,
        'atl_media':         round(atl_media, 1) if atl_media else None,
        'tsb_inicio':        round(tsb_inicio, 1) if tsb_inicio else None,
        'tss_total_sem':     round(tss_total_sem, 1),
        'ramp_rate':         round(ramp_rate / 100, 4) if ramp_rate else None,  # fracción (0.05 = +5%/sem)

        # K1/K2 individuales
        'k1_individual':     round(k1, 5) if k1 else None,
        'k2_individual':     round(k2, 5) if k2 else None,

        # Distribución por zona
        'tss_z12':           round(tss_z12, 1),
        'tss_z34':           round(tss_z34, 1),
        'tss_z56':           round(tss_z56, 1),
        'pct_z12':           round(pct_z12, 1),
        'pct_z34':           round(pct_z34, 1),
        'pct_z56':           round(pct_z56, 1),

        # Duración continua Z1/Z2
        'min_continuo_z12_max':    round(min_continuo_z12_max, 1),
        'n_sesiones_z12_45plus':   n_sesiones_z12_45plus,

        # Tipo de sesión
        'n_sesiones_calidad':              n_sesiones_calidad,
        'n_sesiones_continuo_umbral':      n_sesiones_continuo_umbral,
        'n_sesiones_fraccionado_umbral':   n_sesiones_fraccionado_umbral,
        'n_sesiones_vo2':                  n_sesiones_vo2,
        'n_sesiones_neuro':                n_sesiones_neuro,

        # Contexto temporal
        'semanas_hasta_carrera':   sem_hasta_carrera,
        'semana_del_mesociclo':    sem_mesociclo,

        # Respuesta semana siguiente (etiqueta natural)
        'delta_ctl_sig':   round(delta_ctl_sig, 2) if delta_ctl_sig is not None else None,
        'hrv_ratio_sig':   round(hrv_ratio_sig, 3) if hrv_ratio_sig is not None else None,
        'hanna_sig':       round(hanna_sig, 1) if hanna_sig is not None else None,
    }

    return vector


def construir_dataset_completo(
    conn,
    atleta_id: int,
    semanas_max: int = 12,
) -> pd.DataFrame:
    """
    Construye el dataset completo de vectores semanales para un atleta.
    Una fila = una semana de entrenamiento.
    """
    # Baseline personal
    try:
        from noah_baseline import get_baseline
        baseline = get_baseline(conn, atleta_id)
    except:
        baseline = None

    # K1/K2 individuales
    k_params = estimar_k1_k2(conn, atleta_id)

    # Rango de fechas
    r = conn.execute(
        'SELECT MIN(fecha), MAX(fecha) FROM sesiones WHERE atleta_id=%s',
        (atleta_id,)
    ).fetchone()
    if not r or not r[0]:
        return pd.DataFrame()

    fecha_min = date.fromisoformat(r[0])
    fecha_max = date.fromisoformat(r[1])

    # Ir al lunes de la primera semana
    dias_al_lunes = fecha_min.weekday()
    # Arrancar desde las ultimas semanas_max semanas
    fecha_inicio = max(fecha_min, fecha_max - timedelta(days=semanas_max * 7))
    fecha_lunes = fecha_inicio - timedelta(days=fecha_inicio.weekday())

    # Ultimas semanas_max semanas (las mas recientes)
    vectores = []
    semana = 0
    while fecha_lunes <= fecha_max and semana < semanas_max:
        # Deteccion real de fase (Issurin/Banister/Plews/Mujika)
        fase_info = detectar_fase_mesociclo(conn, atleta_id, fecha_lunes + timedelta(days=6))
        sem_mesociclo = fase_info['semana_en_bloque']
        v = extraer_vector_semana(
            conn, atleta_id, fecha_lunes,
            baseline=baseline, k_params=k_params,
            semana_del_mesociclo=sem_mesociclo,
        )
        if v and v['n_sesiones'] > 0:
            # Inyectar fase real (Issurin/Banister/Plews/Mujika)
            v['fase_mesociclo'] = fase_info.get('fase')
            v['confianza_fase'] = fase_info.get('confianza')
            v['en_taper'] = fase_info.get('en_taper', False)
            v['contexto_planificacion'] = fase_info.get('contexto', 'mejora_general')
            v['semanas_para_carrera'] = fase_info.get('semanas_para_carrera')
            v['acwr'] = fase_info.get('acwr')
            v['absorcion'] = fase_info.get('absorcion')
            vectores.append(v)
        fecha_lunes += timedelta(days=7)
        semana += 1

    if not vectores:
        return pd.DataFrame()

    df = pd.DataFrame(vectores)
    # Contar features con al menos un valor no nulo
    feats_con_datos = df.notna().any().sum()
    feats_total = len(df.columns)
    print(f'  Dataset: {len(df)} semanas | {feats_total} features total | {feats_con_datos} con datos')
    # Mostrar features vacíos para debug
    vacios = [c for c in df.columns if df[c].isna().all()]
    if vacios:
        print(f'  Features vacíos: {vacios}')
    return df


# ── Script standalone ─────────────────────────────────────────────────────────
if __name__ == '__main__':
    import argparse, sys, os
    import psycopg2.extras
    from pathlib import Path
    from db_compat import ConexionCompat
    sys.path.insert(0, str(Path(__file__).parent))

    ap = argparse.ArgumentParser(description='NOAH — Vector semanal')
    ap.add_argument('--atleta', type=int, required=True)
    ap.add_argument('--semanas', type=int, default=8)
    args = ap.parse_args()

    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("Falta la variable de entorno DATABASE_URL (cadena de conexión a Postgres/Supabase)")
        sys.exit(1)
    conn = ConexionCompat(psycopg2.connect(db_url, cursor_factory=psycopg2.extras.DictCursor))

    nombre = conn.execute('SELECT nombre FROM atletas WHERE id=%s', (args.atleta,)).fetchone()
    print(f'\nVectores semanales — {nombre[0] if nombre else args.atleta}')
    print('─' * 60)

    # K1/K2
    k = estimar_k1_k2(conn, args.atleta)
    print(f'K1={k["k1"]} K2={k["k2"]} tau_CTL={k["tau_ctl"]}d tau_ATL={k["tau_atl"]}d (conf={k["confianza"]})')
    print()

    # Últimas N semanas
    hoy = date.today()
    for i in range(args.semanas, 0, -1):
        lunes = hoy - timedelta(days=hoy.weekday()) - timedelta(weeks=i-1)
        v = extraer_vector_semana(conn, args.atleta, lunes)
        if v:
            print(f'{v["fecha_lunes"]} | CTL {v["ctl_inicio"] or "--":>5} '
                  f'Δ{v["delta_ctl"] or "--":>5} | '
                  f'HRV {v["hrv_rmssd_media"] or "--":>5}ms '
                  f'ratio {v["hrv_rmssd_ratio"] or "--":.2f} | '
                  f'Z12:{v["pct_z12"]:.0f}% Z34:{v["pct_z34"]:.0f}% Z56:{v["pct_z56"]:.0f}% | '
                  f'HL {v["hanna_life_media"] or "--"} | '
                  f'Δnxt {v["delta_ctl_sig"] or "--"}')

    conn.close()
