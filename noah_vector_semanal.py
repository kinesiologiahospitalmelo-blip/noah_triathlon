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
    df = pd.read_sql("""
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
    df_bio = pd.read_sql("""
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

    if df_bio.empty:
        return None

    df_bio['hrv'] = df_bio['hrv_rmssd'].combine_first(df_bio['hrv_estimado_valor'])
    df_bio['hrv_real'] = df_bio['hrv_rmssd'].notna()

    # ── Cargar sesiones de la semana ──────────────────────────────────────────
    df_ses = pd.read_sql("""
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
    df_laps = pd.read_sql("""
        SELECT l.sesion_id, l.duration_min, l.hr_avg, l.avg_power,
               s.fecha, s.sport
        FROM laps l
        JOIN sesiones s ON l.sesion_id = s.id
        WHERE s.atleta_id=%s AND s.fecha BETWEEN %s AND %s
        ORDER BY s.fecha, l.lap_num
    """, conn, params=[atleta_id, str(fecha_lunes), str(fecha_dom)])

    # ── Cargar FC intradiaria ─────────────────────────────────────────────────
    df_intra = pd.read_sql("""
        SELECT fecha, AVG(hr_bpm) as fc_intra_media
        FROM fc_intradiaria
        WHERE atleta_id=%s AND fecha BETWEEN %s AND %s
        GROUP BY fecha
    """, conn, params=[atleta_id, str(fecha_lunes), str(fecha_dom)])

    # ── Cargar semana siguiente (etiqueta natural) ────────────────────────────
    df_bio_sig = pd.read_sql("""
        SELECT hrv_rmssd, hrv_estimado_valor, hanna_life
        FROM sleep_hrv
        WHERE atleta_id=%s AND fecha BETWEEN %s AND %s
    """, conn, params=[atleta_id, str(fecha_sig_lun), str(fecha_sig_dom)])

    df_ses_sig = pd.read_sql("""
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
    df_hrv_28 = pd.read_sql("""
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
    semanas_max: int = 200,
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
        'SELECT MIN(fecha), MAX(fecha) FROM sesiones WHERE atleta_id=%s AND ctl IS NOT NULL',
        (atleta_id,)
    ).fetchone()
    if not r or not r[0]:
        return pd.DataFrame()

    fecha_min = date.fromisoformat(r[0])
    fecha_max = date.fromisoformat(r[1])

    # Ir al lunes de la primera semana
    dias_al_lunes = fecha_min.weekday()
    fecha_lunes = fecha_min - timedelta(days=dias_al_lunes)

    vectores = []
    semana = 0
    while fecha_lunes <= fecha_max and semana < semanas_max:
        sem_mesociclo = (semana % 4) + 1
        v = extraer_vector_semana(
            conn, atleta_id, fecha_lunes,
            baseline=baseline, k_params=k_params,
            semana_del_mesociclo=sem_mesociclo,
        )
        if v and v['n_sesiones'] > 0:
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
