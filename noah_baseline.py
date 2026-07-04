"""
noah_baseline.py — Proyecto NOAH
==================================
Calcula y guarda el baseline personal de cada atleta.

El baseline personal es la referencia individualizada que NOAH usa
para evaluar el estado autonómico del atleta — NO la población general.

FASES DE APRENDIZAJE:
  0-14 días  → Sin baseline (usa referencias poblacionales)
  15-29 días → Baseline provisional (±alta incertidumbre)
  30-89 días → Baseline básico (confiable para uso diario)
  90+ días   → Baseline consolidado (apto para modelo predictivo)

VARIABLES DEL BASELINE:
  HRV: media, std, percentiles 10/25/75/90
  FC reposo: media, std, mínimo histórico
  Sueño: media duración, media calidad
  Curva de recuperación: días promedio para volver al baseline tras carga alta
  Respuesta TSB: correlación TSB↔HRV individual

REENTRENAMIENTO:
  Se recalcula automáticamente cuando hay 30+ días nuevos sin recalcular
  o cuando se llama explícitamente con --recalcular

REFERENCIAS:
  Plews et al. 2013 — baseline 7d rolling en atletas endurance
  Buchheit 2014 — curvas de recuperación HRV post-carga
  Nunan et al. 2010 — fórmula RMSSD desde FC reposo
"""

from __future__ import annotations
import psycopg2
import json
import numpy as np
import pandas as pd
from datetime import date, timedelta, datetime
from typing import Optional


# ── Tabla baseline ────────────────────────────────────────────────────────────
DDL_BASELINE = """
CREATE TABLE IF NOT EXISTS atleta_baseline (
    id                    SERIAL PRIMARY KEY,
    atleta_id             INTEGER NOT NULL UNIQUE,
    fecha_calculo         TEXT NOT NULL,
    dias_historial        INTEGER,
    fase                  TEXT,        -- 'sin_datos','provisional','basico','consolidado'
    confianza             REAL,        -- 0-1

    -- HRV
    hrv_media             REAL,
    hrv_std               REAL,
    hrv_p10               REAL,        -- percentil 10 (zona roja personal)
    hrv_p25               REAL,        -- percentil 25
    hrv_p75               REAL,        -- percentil 75
    hrv_p90               REAL,        -- percentil 90 (zona óptima personal)
    hrv_tendencia         REAL,        -- slope regresión lineal últimos 30d (ms/día)

    -- FC reposo
    fc_media              REAL,
    fc_std                REAL,
    fc_min_historico      REAL,        -- el mínimo jamás registrado (= condición pico)

    -- Sueño
    sleep_media_h         REAL,
    sleep_std_h           REAL,
    sleep_calidad_media   REAL,        -- (deep+rem)/total

    -- Stress
    stress_media          REAL,
    stress_std            REAL,

    -- Curva de recuperación
    dias_recuperacion_p50 REAL,        -- días típicos para volver al baseline tras TSB < -15
    recuperacion_slope    REAL,        -- velocidad de recuperación (ms HRV/día)

    -- Respuesta a carga
    correlacion_tsb_hrv   REAL,        -- correlación Pearson entre TSB y HRV del atleta
    hrv_carga_alta        REAL,        -- HRV promedio cuando TSB < -10
    hrv_fresco            REAL,        -- HRV promedio cuando TSB > 5

    -- Metadata
    n_dias_hrv_real       INTEGER,     -- días con HRV medido (no estimado)
    n_dias_hrv_estimado   INTEGER,
    datos_extra           TEXT,        -- JSON con info adicional

    FOREIGN KEY (atleta_id) REFERENCES atletas(id)
)
"""


def _asegurar_tabla(conn):
    conn.execute(DDL_BASELINE)
    conn.commit()


def _fase_y_confianza(dias: int, n_hrv_real: int) -> tuple[str, float]:
    """Determina la fase de aprendizaje y confianza del baseline."""
    if dias < 14:
        return 'sin_datos', 0.0
    elif dias < 30:
        return 'provisional', 0.25
    elif dias < 90:
        # Confianza crece con días y proporción de HRV real
        base = 0.5 + (dias - 30) / 120
        bonus_hrv = min(0.15, n_hrv_real / dias * 0.2)
        return 'basico', min(0.75, base + bonus_hrv)
    else:
        base = 0.75 + min(0.20, (dias - 90) / 500)
        bonus_hrv = min(0.05, n_hrv_real / dias * 0.1)
        return 'consolidado', min(1.0, base + bonus_hrv)


def calcular_baseline(
    conn,
    atleta_id: int,
    dias_max: int = 365,
) -> dict:
    """
    Calcula el baseline personal del atleta con los últimos `dias_max` días.
    Retorna un dict con todos los campos del baseline.
    """
    fecha_hasta = str(date.today())
    fecha_desde = str(date.today() - timedelta(days=dias_max))

    # ── Cargar HRV histórico ──────────────────────────────────────────────────
    df_hrv = pd.read_sql("""
        SELECT fecha, hrv_rmssd, hrv_estimado_valor, hrv_estimado,
               hr_reposo, sleep_h, deep_h, rem_h, stress_avg, body_battery
        FROM sleep_hrv
        WHERE atleta_id=%s AND fecha BETWEEN %s AND %s
        ORDER BY fecha
    """, conn, params=[atleta_id, fecha_desde, fecha_hasta])

    if len(df_hrv) < 7:
        return {'fase': 'sin_datos', 'confianza': 0.0, 'dias_historial': len(df_hrv)}

    df_hrv['fecha'] = pd.to_datetime(df_hrv['fecha'])
    df_hrv['hrv'] = df_hrv['hrv_rmssd'].combine_first(df_hrv['hrv_estimado_valor'])
    df_hrv['es_real'] = df_hrv['hrv_rmssd'].notna()

    # ── Cargar TSB histórico ──────────────────────────────────────────────────
    df_tsb = pd.read_sql("""
        SELECT fecha, ctl, atl
        FROM sesiones
        WHERE atleta_id=%s AND ctl IS NOT NULL AND fecha BETWEEN %s AND %s
        ORDER BY fecha
    """, conn, params=[atleta_id, fecha_desde, fecha_hasta])

    if len(df_tsb) > 0:
        df_tsb['fecha'] = pd.to_datetime(df_tsb['fecha'])
        df_tsb['tsb'] = df_tsb['ctl'].astype(float) - df_tsb['atl'].astype(float)
        df_merged = df_hrv.merge(df_tsb[['fecha','tsb']], on='fecha', how='left')
    else:
        df_merged = df_hrv.copy()
        df_merged['tsb'] = None

    dias = len(df_hrv)
    n_hrv_real = int(df_hrv['es_real'].sum())
    n_hrv_est = dias - n_hrv_real
    fase, confianza = _fase_y_confianza(dias, n_hrv_real)

    # ── Estadísticas HRV ─────────────────────────────────────────────────────
    hrv_vals = df_hrv['hrv'].dropna().values
    hrv_media = hrv_std = hrv_p10 = hrv_p25 = hrv_p75 = hrv_p90 = None
    hrv_tendencia = None

    if len(hrv_vals) >= 5:
        hrv_media = float(np.mean(hrv_vals))
        hrv_std   = float(np.std(hrv_vals))
        hrv_p10   = float(np.percentile(hrv_vals, 10))
        hrv_p25   = float(np.percentile(hrv_vals, 25))
        hrv_p75   = float(np.percentile(hrv_vals, 75))
        hrv_p90   = float(np.percentile(hrv_vals, 90))

        # Tendencia reciente (últimos 30 días)
        recientes = df_hrv[df_hrv['hrv'].notna()].tail(30)
        if len(recientes) >= 7:
            x = np.arange(len(recientes), dtype=float)
            y = recientes['hrv'].astype(float).values
            mask = ~np.isnan(y)
            if mask.sum() >= 5:
                slope = float(np.polyfit(x[mask], y[mask], 1)[0])
                hrv_tendencia = round(slope, 4)  # ms/día

    # ── Estadísticas FC reposo ────────────────────────────────────────────────
    fc_vals = df_hrv['hr_reposo'].dropna()
    fc_vals = fc_vals[fc_vals > 30].values
    fc_media = fc_std = fc_min = None
    if len(fc_vals) >= 5:
        fc_media = float(np.mean(fc_vals))
        fc_std   = float(np.std(fc_vals))
        fc_min   = float(np.min(fc_vals))

    # ── Estadísticas sueño ────────────────────────────────────────────────────
    sleep_vals = df_hrv['sleep_h'].dropna()
    sleep_vals = sleep_vals[sleep_vals > 0].values
    sleep_media = sleep_std = None
    if len(sleep_vals) >= 5:
        sleep_media = float(np.mean(sleep_vals))
        sleep_std   = float(np.std(sleep_vals))

    # Calidad sueño (deep + rem / total)
    df_cal = df_hrv.dropna(subset=['sleep_h'])
    df_cal = df_cal[df_cal['sleep_h'] > 0].copy()
    sleep_calidad_media = None
    if len(df_cal) >= 5:
        df_cal['calidad'] = (df_cal['deep_h'].fillna(0) + df_cal['rem_h'].fillna(0)) / df_cal['sleep_h']
        sleep_calidad_media = float(df_cal['calidad'].mean())

    # ── Estadísticas stress ───────────────────────────────────────────────────
    stress_vals = df_hrv['stress_avg'].dropna().values
    stress_media = stress_std = None
    if len(stress_vals) >= 5:
        stress_media = float(np.mean(stress_vals))
        stress_std   = float(np.std(stress_vals))

    # ── Correlación TSB ↔ HRV ────────────────────────────────────────────────
    correlacion_tsb_hrv = None
    hrv_carga_alta = None
    hrv_fresco = None

    if len(df_merged) >= 20 and df_merged['tsb'].notna().sum() >= 10:
        df_cor = df_merged[df_merged['hrv'].notna() & df_merged['tsb'].notna()]
        if len(df_cor) >= 10:
            try:
                correlacion_tsb_hrv = float(np.corrcoef(
                    df_cor['tsb'].values,
                    df_cor['hrv'].values
                )[0,1])
            except:
                pass

        # HRV promedio en distintos estados de carga
        carga_alta = df_merged[(df_merged['tsb'] < -10) & df_merged['hrv'].notna()]
        fresco = df_merged[(df_merged['tsb'] > 5) & df_merged['hrv'].notna()]
        if len(carga_alta) >= 3:
            hrv_carga_alta = float(carga_alta['hrv'].mean())
        if len(fresco) >= 3:
            hrv_fresco = float(fresco['hrv'].mean())

    # ── Curva de recuperación ─────────────────────────────────────────────────
    dias_recuperacion = None
    recuperacion_slope = None

    if hrv_media and len(df_merged) >= 30 and df_merged['tsb'].notna().sum() >= 10:
        # Detectar episodios de carga alta seguidos de recuperación
        episodios = []
        df_ep = df_merged[['fecha','hrv','tsb']].dropna().copy()
        df_ep = df_ep.sort_values('fecha').reset_index(drop=True)

        i = 0
        while i < len(df_ep) - 3:
            if df_ep.loc[i, 'tsb'] < -15:
                hrv_inicio = df_ep.loc[i, 'hrv']
                # Buscar cuántos días hasta volver al 95% del baseline
                for j in range(i+1, min(i+14, len(df_ep))):
                    if df_ep.loc[j, 'hrv'] >= hrv_media * 0.95:
                        episodios.append(j - i)
                        break
                i += 3
            else:
                i += 1

        if len(episodios) >= 3:
            dias_recuperacion = float(np.median(episodios))

        # Slope de recuperación (HRV ms/día durante recuperación)
        if hrv_carga_alta and hrv_fresco and dias_recuperacion and dias_recuperacion > 0:
            recuperacion_slope = (hrv_fresco - hrv_carga_alta) / dias_recuperacion

    return {
        'atleta_id':            atleta_id,
        'fecha_calculo':        str(date.today()),
        'dias_historial':       dias,
        'fase':                 fase,
        'confianza':            round(confianza, 3),

        'hrv_media':            round(hrv_media, 2) if hrv_media else None,
        'hrv_std':              round(hrv_std, 2) if hrv_std else None,
        'hrv_p10':              round(hrv_p10, 2) if hrv_p10 else None,
        'hrv_p25':              round(hrv_p25, 2) if hrv_p25 else None,
        'hrv_p75':              round(hrv_p75, 2) if hrv_p75 else None,
        'hrv_p90':              round(hrv_p90, 2) if hrv_p90 else None,
        'hrv_tendencia':        hrv_tendencia,

        'fc_media':             round(fc_media, 1) if fc_media else None,
        'fc_std':               round(fc_std, 2) if fc_std else None,
        'fc_min_historico':     round(fc_min, 1) if fc_min else None,

        'sleep_media_h':        round(sleep_media, 2) if sleep_media else None,
        'sleep_std_h':          round(sleep_std, 2) if sleep_std else None,
        'sleep_calidad_media':  round(sleep_calidad_media, 3) if sleep_calidad_media else None,

        'stress_media':         round(stress_media, 1) if stress_media else None,
        'stress_std':           round(stress_std, 2) if stress_std else None,

        'dias_recuperacion_p50':round(dias_recuperacion, 1) if dias_recuperacion else None,
        'recuperacion_slope':   round(recuperacion_slope, 3) if recuperacion_slope else None,

        'correlacion_tsb_hrv':  round(correlacion_tsb_hrv, 3) if correlacion_tsb_hrv else None,
        'hrv_carga_alta':       round(hrv_carga_alta, 2) if hrv_carga_alta else None,
        'hrv_fresco':           round(hrv_fresco, 2) if hrv_fresco else None,

        'n_dias_hrv_real':      n_hrv_real,
        'n_dias_hrv_estimado':  n_hrv_est,
    }


def guardar_baseline(conn, baseline: dict) -> bool:
    """Guarda o actualiza el baseline del atleta en la DB."""
    _asegurar_tabla(conn)
    if baseline.get('fase') == 'sin_datos':
        return False

    campos = [
        'atleta_id','fecha_calculo','dias_historial','fase','confianza',
        'hrv_media','hrv_std','hrv_p10','hrv_p25','hrv_p75','hrv_p90','hrv_tendencia',
        'fc_media','fc_std','fc_min_historico',
        'sleep_media_h','sleep_std_h','sleep_calidad_media',
        'stress_media','stress_std',
        'dias_recuperacion_p50','recuperacion_slope',
        'correlacion_tsb_hrv','hrv_carga_alta','hrv_fresco',
        'n_dias_hrv_real','n_dias_hrv_estimado',
    ]
    vals = [baseline.get(c) for c in campos]
    placeholders = ','.join(['%s' for _ in campos])
    updates = ','.join([f'{c}=excluded.{c}' for c in campos if c != 'atleta_id'])

    conn.execute(f"""
        INSERT INTO atleta_baseline ({','.join(campos)})
        VALUES ({placeholders})
        ON CONFLICT(atleta_id) DO UPDATE SET {updates}
    """, vals)
    conn.commit()
    return True


def get_baseline(conn, atleta_id: int) -> Optional[dict]:
    """
    Obtiene el baseline guardado del atleta.
    Retorna None si no existe o está desactualizado (>30 días).
    """
    _asegurar_tabla(conn)
    row = conn.execute("""
        SELECT * FROM atleta_baseline WHERE atleta_id=%s
    """, (atleta_id,)).fetchone()

    if not row:
        return None

    from db_compat import columnas_de_tabla
    cols = columnas_de_tabla(conn, 'atleta_baseline')
    d = dict(zip(cols, row))

    # Verificar frescura — si tiene más de 30 días, avisar
    if d.get('fecha_calculo'):
        dias_desde_calculo = (date.today() - date.fromisoformat(d['fecha_calculo'])).days
        d['dias_desde_calculo'] = dias_desde_calculo
        d['necesita_recalculo'] = dias_desde_calculo > 30
    return d


def calcular_y_guardar_baseline(
    conn,
    atleta_id: int,
    forzar: bool = False,
) -> dict:
    """
    Calcula y guarda el baseline. Solo recalcula si:
    - No existe
    - Tiene más de 30 días
    - forzar=True
    """
    existente = get_baseline(conn, atleta_id)

    if existente and not forzar and not existente.get('necesita_recalculo'):
        return existente

    baseline = calcular_baseline(conn, atleta_id)
    guardado = guardar_baseline(conn, baseline)
    baseline['guardado'] = guardado
    return baseline


# ── Script standalone ─────────────────────────────────────────────────────────
if __name__ == '__main__':
    import argparse, sys, os
    import psycopg2.extras
    from pathlib import Path
    from db_compat import ConexionCompat
    sys.path.insert(0, str(Path(__file__).parent))

    ap = argparse.ArgumentParser(description='NOAH — Baseline personal del atleta')
    ap.add_argument('--atleta', type=int, default=None)
    ap.add_argument('--todos', action='store_true')
    ap.add_argument('--forzar', action='store_true')
    args = ap.parse_args()

    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("Falta la variable de entorno DATABASE_URL (cadena de conexión a Postgres/Supabase)")
        sys.exit(1)
    conn = ConexionCompat(psycopg2.connect(db_url, cursor_factory=psycopg2.extras.DictCursor))

    if args.todos:
        atletas = [r[0] for r in conn.execute(
            "SELECT id FROM atletas WHERE activo=1").fetchall()]
    elif args.atleta:
        atletas = [args.atleta]
    else:
        print("Usar --atleta N o --todos")
        conn.close(); exit(1)

    for aid in atletas:
        nombre = conn.execute("SELECT nombre FROM atletas WHERE id=%s", (aid,)).fetchone()
        nombre = nombre[0] if nombre else f'Atleta {aid}'
        print(f'\n── {nombre} ──')

        b = calcular_y_guardar_baseline(conn, aid, forzar=args.forzar)

        print(f"  Fase:        {b.get('fase')} (confianza {b.get('confianza',0)*100:.0f}%)")
        print(f"  Historial:   {b.get('dias_historial')} días")
        print(f"  HRV:         media={b.get('hrv_media')} ± {b.get('hrv_std')} ms")
        print(f"  HRV rango:   p10={b.get('hrv_p10')} | p25={b.get('hrv_p25')} | p75={b.get('hrv_p75')} | p90={b.get('hrv_p90')}")
        print(f"  HRV tend.:   {b.get('hrv_tendencia')} ms/día")
        print(f"  FC reposo:   media={b.get('fc_media')} | mín histórico={b.get('fc_min_historico')}")
        print(f"  Sueño:       {b.get('sleep_media_h')}h ± {b.get('sleep_std_h')}")
        print(f"  Recuperac.:  {b.get('dias_recuperacion_p50')} días típicos")
        print(f"  Corr TSB↔HRV:{b.get('correlacion_tsb_hrv')}")
        print(f"  HRV fresco:  {b.get('hrv_fresco')} ms | carga alta: {b.get('hrv_carga_alta')} ms")
        if b.get('hrv_tendencia') is not None:
            tend = b['hrv_tendencia']
            if tend > 0.05:
                print(f"  ✓ HRV en mejora (+{tend*30:.1f}ms/mes)")
            elif tend < -0.05:
                print(f"  ⚠ HRV en descenso ({tend*30:.1f}ms/mes)")
            else:
                print(f"  → HRV estable")

    conn.close()
