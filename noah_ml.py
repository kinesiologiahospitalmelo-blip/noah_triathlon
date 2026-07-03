"""
noah_ml.py — Proyecto NOAH
============================
Modelos de Machine Learning que aprenden del atleta específico.

MODELOS:
  1. Predictor de respuesta a la carga
     Input:  CTL, ATL, TSB, HRV, sueño, estrés, TSS del día
     Output: HRV al día siguiente (indica si absorbió bien la carga)

  2. Detector de adaptación (progresión)
     Input:  pace Z2 / FTP / CSS de últimas 8 semanas
     Output: pendiente de mejora por deporte

  3. Predictor de cumplimiento
     Input:  TSB, HRV, tipo sesión, día de la semana
     Output: probabilidad de que complete la sesión prescripta

  4. Detector de sobreentrenamiento temprano
     Input:  HRV ratio últimos 7 días, TSS acumulado, sueño
     Output: riesgo de sobreentrenamiento (0-100)

USO:
  from noah_ml import NOAHMind
  mind = NOAHMind(conn, atleta_id=1)
  mind.entrenar()
  prediccion = mind.predecir_respuesta(ctl=45, atl=50, tsb=-5, hrv=65, tss_hoy=85)
"""

from __future__ import annotations
import psycopg2
import numpy as np
import pandas as pd
import json
from datetime import date, timedelta
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


# ── Helpers ───────────────────────────────────────────────────────────────────
def _safe_float(v, default=None):
    try:
        f = float(v)
        return f if not np.isnan(f) else default
    except (TypeError, ValueError):
        return default


def _read_sql(sql, conn, params=None):
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        cur = conn.cursor()
        cur.execute(sql, params)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    return pd.DataFrame(rows, columns=cols)


# ── Dataset builder ───────────────────────────────────────────────────────────
def construir_dataset(conn, atleta_id: int) -> pd.DataFrame:
    """
    Construye el dataset completo para ML incluyendo:
    - Carga de entrenamiento (TSS, CTL, ATL, TSB)
    - Biomarcadores del día (sleep, stress, FC, HRV, HANNA_VFC)
    - Biomarcadores del día siguiente (targets para modelo impacto-respuesta)
    - Features derivados (variaciones, tendencias)
    """
    """
    Construye el dataset principal uniendo sesiones + biomarcadores.
    Cada fila = un día con sus métricas de carga y biomarcadores.
    """
    # Sesiones agrupadas por día — GROUP_CONCAT (SQLite) reemplazado por
    # STRING_AGG (Postgres), mismo resultado: lista de deportes separados
    # por coma para ese día.
    df_ses = _read_sql('''
        SELECT fecha,
               SUM(tss_total)         AS tss_dia,
               AVG(hr_avg)            AS hr_avg_dia,
               MAX(ctl)               AS ctl,
               MAX(atl)               AS atl,
               MAX(tsb)               AS tsb,
               STRING_AGG(sport, ',') AS deportes,
               COUNT(*)               AS n_sesiones
        FROM sesiones
        WHERE atleta_id=%s AND tss_total > 0
        GROUP BY fecha
        ORDER BY fecha
    ''', conn, params=[atleta_id])

    # Biomarcadores
    df_bio = _read_sql('''
        SELECT fecha, hrv_rmssd, hrv_ratio, hrv_flag,
               sleep_h, deep_h, rem_h, stress_avg, body_battery,
               fc_nocturna, sleep_stress_avg, resp_avg,
               hanna_vfc, hanna_vfc_ratio, hanna_vfc_flag,
               recovery_score, sleep_score, restless_count,
               spo2_avg, hr_reposo
        FROM sleep_hrv
        WHERE atleta_id=%s
        ORDER BY fecha
    ''', conn, params=[atleta_id])

    if df_ses.empty or df_bio.empty:
        return pd.DataFrame()

    # Merge por fecha
    df = pd.merge(df_ses, df_bio, on='fecha', how='outer').sort_values('fecha')
    df['fecha'] = pd.to_datetime(df['fecha'])
    df = df.set_index('fecha').asfreq('D').reset_index(drop=False)

    # Rellenar TSS 0 en días sin sesión
    df['tss_dia'] = df['tss_dia'].fillna(0)

    # Forward fill de CTL/ATL/TSB (cambian lentamente)
    for col in ['ctl', 'atl', 'tsb']:
        df[col] = df[col].ffill()

    # HRV del día siguiente (target del Modelo 1)
    # Features de biomarcadores completos
    # Renombrar columnas de la query expandida
    bio_cols = ['hrv_rmssd','hrv_ratio','hrv_flag','sleep_h','deep_h','rem_h',
                'stress_avg','body_battery','fc_nocturna','sleep_stress_avg',
                'resp_avg','hanna_vfc','hanna_vfc_ratio','hanna_vfc_flag',
                'recovery_score','sleep_score','restless_count','spo2_avg','hr_reposo']

    # Targets: biomarcadores del día siguiente (impacto-respuesta)
    df['hrv_mañana']          = df['hrv_rmssd'].shift(-1)
    df['stress_mañana']       = df['stress_avg'].shift(-1)
    df['sleep_mañana']        = df['sleep_h'].shift(-1)
    df['fc_reposo_mañana']    = df['hr_reposo'].shift(-1)
    df['hanna_vfc_mañana']    = df['hanna_vfc'].shift(-1)
    df['recovery_mañana']     = df['recovery_score'].shift(-1)

    # Convertir columnas a numérico antes de operar
    for col in ['hrv_rmssd','stress_avg','hr_reposo','hanna_vfc','hanna_vfc_ratio',
                'fc_nocturna','sleep_stress_avg','resp_avg','recovery_score',
                'sleep_score','restless_count','spo2_avg']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Variación de biomarcadores (delta día a día)
    df['delta_hrv']           = df['hrv_rmssd'].diff()
    df['delta_stress']        = df['stress_avg'].diff()
    df['delta_fc_reposo']     = df['hr_reposo'].diff()
    df['delta_hanna_vfc']     = df['hanna_vfc'].diff()

    # Tendencias 7 días
    df['hrv_7d_avg']          = df['hrv_rmssd'].rolling(7, min_periods=3).mean()
    df['stress_7d_avg']       = df['stress_avg'].rolling(7, min_periods=3).mean()
    df['sleep_7d_avg']        = df['sleep_h'].rolling(7, min_periods=3).mean()
    df['hanna_vfc_7d_avg']    = df['hanna_vfc'].rolling(7, min_periods=3).mean()

    # Ratios vs baseline personal
    df['hrv_ratio_7d']        = df['hrv_rmssd'] / df['hrv_7d_avg'].replace(0, np.nan)
    df['hanna_vfc_ratio_calc'] = df['hanna_vfc'] / df['hanna_vfc_7d_avg'].replace(0, np.nan)

    # Calidad de sueño (% restaurador)
    df['pct_deep_rem']        = ((df['deep_h'].fillna(0) + df['rem_h'].fillna(0)) /
                                  df['sleep_h'].replace(0, np.nan)).clip(0, 1)

    # Features derivadas
    df['tss_7d']     = df['tss_dia'].rolling(7, min_periods=1).sum()
    df['tss_14d']    = df['tss_dia'].rolling(14, min_periods=1).sum()
    df['hrv_7d_avg'] = df['hrv_rmssd'].rolling(7, min_periods=3).mean()
    df['hrv_ratio_7d'] = df['hrv_rmssd'] / df['hrv_7d_avg']
    df['dia_semana'] = df['fecha'].dt.dayofweek

    # Flag de sesión intensa (TSS > 80)
    df['sesion_intensa'] = (df['tss_dia'] > 80).astype(int)

    # Enriquecer con datos de feedback (cierre del ciclo prescripcion -> realizado -> respuesta)
    df = _enriquecer_con_feedback(df, conn, atleta_id)

    return df


def _enriquecer_con_feedback(df: pd.DataFrame, conn, atleta_id: int) -> pd.DataFrame:
    """
    Agrega features derivados de noah_feedback al dataset principal.
    Cierra el ciclo: lo que NOAH prescribio vs lo que el atleta hizo vs como respondio.

    Features que agrega:
      adherencia_7d       — promedio de cumplimiento_tss ultimos 7 dias
                            (>1 = hace mas de lo prescripto, <1 = hace menos)
      hrv_respuesta_7d    — promedio de impacto_hrv ultimos 7 dias
                            (indica si el atleta absorbe bien la carga prescripta)
      pct_sobrecarga_14d  — % sesiones con resultado 'sobrecarga' en 14 dias
      pct_optima_14d      — % sesiones con resultado 'optima' en 14 dias
      patron_carga        — indice personal: adherencia_7d * (1 + hrv_respuesta_7d/10)
                            captura si el atleta sobreejercita Y aguanta bien o no
    """
    try:
        tbl = conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name='noah_feedback'"
        ).fetchone()
        if not tbl:
            return df

        df_fb = _read_sql('''
            SELECT fecha, cumplimiento_tss, impacto_hrv, resultado
            FROM noah_feedback
            WHERE atleta_id=%s
            ORDER BY fecha
        ''', conn, params=[atleta_id])

        if df_fb.empty:
            return df

        df_fb['fecha'] = pd.to_datetime(df_fb['fecha'])
        df_fb['cumplimiento_tss'] = pd.to_numeric(df_fb['cumplimiento_tss'], errors='coerce')
        df_fb['impacto_hrv']      = pd.to_numeric(df_fb['impacto_hrv'],      errors='coerce')
        df_fb['es_sobrecarga']    = (df_fb['resultado'] == 'sobrecarga').astype(float)
        df_fb['es_optima']        = (df_fb['resultado'] == 'optima').astype(float)

        # Agrupar por dia (puede haber multiples sesiones)
        df_fb_dia = df_fb.groupby('fecha').agg(
            adherencia_dia    = ('cumplimiento_tss', 'mean'),
            hrv_resp_dia      = ('impacto_hrv',      'mean'),
            sobrecarga_dia    = ('es_sobrecarga',     'max'),
            optima_dia        = ('es_optima',         'max'),
        ).reset_index()

        # Merge con dataset principal
        df['fecha_dt'] = pd.to_datetime(df['fecha'])
        df = df.merge(df_fb_dia, left_on='fecha_dt', right_on='fecha',
                      how='left', suffixes=('', '_fb'))

        # Rolling features (ventana deslizante — no usa datos futuros)
        df = df.sort_values('fecha_dt').reset_index(drop=True)

        df['adherencia_7d']      = df['adherencia_dia'].rolling(7,  min_periods=1).mean()
        df['hrv_respuesta_7d']   = df['hrv_resp_dia'].rolling(7,    min_periods=1).mean()
        df['pct_sobrecarga_14d'] = df['sobrecarga_dia'].rolling(14, min_periods=1).mean()
        df['pct_optima_14d']     = df['optima_dia'].rolling(14,     min_periods=1).mean()

        # Patron de carga personal: combina adherencia con respuesta HRV
        # Si hace 162% y HRV baja poco → patron_carga alto = tolera bien la sobrecarga
        # Si hace 94% y HRV baja mucho → patron_carga bajo = sensible a la carga
        df['patron_carga'] = (
            df['adherencia_7d'].fillna(1.0) *
            (1 + df['hrv_respuesta_7d'].fillna(0) / 10)
        )

        # Limpiar columnas temporales
        df = df.drop(columns=[c for c in ['fecha_fb', 'fecha_dt',
                               'adherencia_dia', 'hrv_resp_dia',
                               'sobrecarga_dia', 'optima_dia'] if c in df.columns])

        n_dias_feedback = df['adherencia_7d'].notna().sum()
        print(f'  [Feedback] {n_dias_feedback} dias con datos de ciclo cerrado')

    except Exception as e:
        print(f'  [Feedback] Error enriqueciendo con feedback: {e}')

    return df


# ── Modelo 1: Predictor de respuesta a la carga ───────────────────────────────
class PredictorRespuestaCarga:
    """
    Predice el HRV del día siguiente dado el estado actual y la carga.
    Un HRV alto mañana = buena absorción de la carga.
    Un HRV bajo mañana = estrés fisiológico, posible sobrecarga.
    """
    def __init__(self):
        self.modelo    = None
        self.features  = ['ctl', 'atl', 'tsb', 'hrv_rmssd', 'sleep_h',
                          'stress_avg', 'tss_dia', 'tss_7d', 'sesion_intensa']
        self.entrenado = False
        self.score     = None
        self.hrv_baseline = None

    def entrenar(self, df: pd.DataFrame) -> float:
        try:
            from sklearn.ensemble import RandomForestRegressor
            from sklearn.model_selection import cross_val_score
            from sklearn.preprocessing import StandardScaler
        except ImportError:
            print('  [ML] scikit-learn no instalado. Corré: pip install scikit-learn')
            return 0.0

        # Filtrar filas con datos completos
        cols_needed = self.features + ['hrv_mañana']
        df_clean = df[cols_needed].dropna()

        if len(df_clean) < 30:
            print(f'  [ML] Datos insuficientes para entrenar: {len(df_clean)} filas')
            return 0.0

        X = df_clean[self.features].values
        y = df_clean['hrv_mañana'].values

        self.hrv_baseline = float(np.median(y))

        # Modelo Random Forest — robusto para datos biológicos no lineales
        self.modelo = RandomForestRegressor(
            n_estimators=100,
            max_depth=6,
            min_samples_leaf=5,
            random_state=42,
        )
        self.modelo.fit(X, y)

        # Validación cruzada
        scores = cross_val_score(self.modelo, X, y, cv=5, scoring='r2')
        self.score = float(scores.mean())
        self.entrenado = True

        print(f'  [ML] Modelo respuesta carga: R²={self.score:.3f} ({len(df_clean)} muestras)')
        return self.score

    def predecir(self, ctl, atl, tsb, hrv_hoy, sleep_h,
                 stress, tss_hoy, tss_7d, sesion_intensa=0) -> dict:
        if not self.entrenado or self.modelo is None:
            return {}

        X = np.array([[
            _safe_float(ctl, 30),
            _safe_float(atl, 30),
            _safe_float(tsb, 0),
            _safe_float(hrv_hoy, self.hrv_baseline),
            _safe_float(sleep_h, 7),
            _safe_float(stress, 10),
            _safe_float(tss_hoy, 0),
            _safe_float(tss_7d, 0),
            int(sesion_intensa),
        ]])

        hrv_pred = float(self.modelo.predict(X)[0])
        baseline = self.hrv_baseline or 60

        # Interpretar
        ratio = hrv_pred / baseline
        if ratio >= 1.05:
            interpretacion = 'Buena absorción — atleta responde bien a esta carga'
            semaforo = 'verde'
        elif ratio >= 0.92:
            interpretacion = 'Absorción normal — monitorear mañana'
            semaforo = 'amarillo'
        else:
            interpretacion = 'Posible sobrecarga — reducir intensidad mañana'
            semaforo = 'rojo'

        return {
            'hrv_predicho':    round(hrv_pred, 1),
            'hrv_baseline':    round(baseline, 1),
            'ratio':           round(ratio, 3),
            'semaforo':        semaforo,
            'interpretacion':  interpretacion,
        }

    def importancia_features(self) -> dict:
        if not self.entrenado:
            return {}
        imp = self.modelo.feature_importances_
        return {f: round(float(i), 3)
                for f, i in zip(self.features, imp)}


# ── Modelo 2: Detector de adaptación ─────────────────────────────────────────
class DetectorAdaptacion:
    """
    Detecta si el atleta está mejorando en cada deporte.
    Usa regresión lineal sobre ventanas de 8 semanas.
    """

    def analizar(self, conn, atleta_id: int) -> dict:
        resultado = {}

        # Running — pace Z2
        resultado['running'] = self._analizar_running(conn, atleta_id)

        # Cycling — FTP estimado desde NP/HR
        resultado['cycling'] = self._analizar_cycling(conn, atleta_id)

        # Swimming — CSS / pace promedio
        resultado['swimming'] = self._analizar_swimming(conn, atleta_id)

        return resultado

    def _tendencia(self, valores: list, fechas: list = None) -> dict:
        """Calcula pendiente de mejora/empeora."""
        if len(valores) < 4:
            return {'tendencia': 'sin_datos', 'pendiente': 0, 'mejora_pct': 0}

        x = np.arange(len(valores), dtype=float)
        y = np.array(valores, dtype=float)
        mask = ~np.isnan(y)
        if mask.sum() < 4:
            return {'tendencia': 'sin_datos', 'pendiente': 0, 'mejora_pct': 0}

        coef = np.polyfit(x[mask], y[mask], 1)
        pendiente = float(coef[0])

        # Mejora % en 8 semanas
        rango = 8 * len(valores) / max(len(valores), 1)
        mejora_pct = round(pendiente * rango / float(np.mean(y[mask])) * 100, 1)

        if abs(mejora_pct) < 1.5:
            tendencia = 'estable'
        elif mejora_pct > 0:
            tendencia = 'mejorando'
        else:
            tendencia = 'empeorando'

        return {
            'tendencia':   tendencia,
            'pendiente':   round(pendiente, 4),
            'mejora_pct':  mejora_pct,
            'n_muestras':  int(mask.sum()),
        }

    def _analizar_running(self, conn, atleta_id) -> dict:
        df = _read_sql('''
            SELECT fecha, pace, hr_avg, tss_total, distance_km
            FROM sesiones
            WHERE atleta_id=%s AND sport='running'
            AND pace BETWEEN 4.5 AND 8.0
            AND hr_avg BETWEEN 110 AND 165
            AND tss_total > 20
            ORDER BY fecha DESC LIMIT 60
        ''', conn, params=[atleta_id])

        if df.empty:
            return {'tendencia': 'sin_datos'}

        # Pace ajustado por HR (pace relativo al esfuerzo)
        # Menor = más eficiente (mismo esfuerzo, más rápido)
        df['pace_hr_ratio'] = df['pace'] / (df['hr_avg'] / 162)

        tendencia = self._tendencia(df['pace_hr_ratio'].tolist())

        # Invertir: para pace, "mejorando" = bajando (más rápido)
        if tendencia['tendencia'] == 'mejorando':
            tendencia['tendencia'] = 'empeorando'
            tendencia['mejora_pct'] *= -1
        elif tendencia['tendencia'] == 'empeorando':
            tendencia['tendencia'] = 'mejorando'
            tendencia['mejora_pct'] *= -1

        tendencia['pace_ultimo']  = round(float(df['pace'].iloc[0]), 3) if len(df) else None
        tendencia['pace_prom_8s'] = round(float(df['pace'].tail(16).mean()), 3) if len(df) >= 4 else None
        return tendencia

    def _analizar_cycling(self, conn, atleta_id) -> dict:
        df = _read_sql('''
            SELECT fecha, tss_total, duration_min, hr_avg, np_watts
            FROM sesiones
            WHERE atleta_id=%s AND sport='cycling'
            AND tss_total > 30 AND duration_min > 30
            ORDER BY fecha DESC LIMIT 60
        ''', conn, params=[atleta_id])

        if df.empty:
            return {'tendencia': 'sin_datos'}

        # FTP estimado = NP × 0.95 si hay potencia, sino desde HR-TSS
        if df['np_watts'].notna().sum() > 5:
            df['ftp_est'] = df['np_watts'] * 0.95
            valores = df['ftp_est'].dropna().tolist()
            metrica = 'ftp_watts'
        else:
            # FTP estimado desde TSS y HR
            lthr = 160
            df['if_est'] = df['hr_avg'] / lthr
            df['ftp_hr'] = df['if_est'] * 200  # aproximación
            valores = df['ftp_hr'].dropna().tolist()
            metrica = 'ftp_estimado_hr'

        tendencia = self._tendencia(valores)
        tendencia['metrica'] = metrica
        tendencia['ftp_ultimo'] = round(float(df['np_watts'].iloc[0] * 0.95), 0) if df['np_watts'].iloc[0] else None
        return tendencia

    def _analizar_swimming(self, conn, atleta_id) -> dict:
        # Usar laps de largos si existen, sino pace de sesión
        try:
            df_laps = _read_sql('''
                SELECT l.fecha, l.pace
                FROM laps l
                JOIN sesiones s ON l.sesion_id=s.id
                WHERE s.atleta_id=%s AND s.sport='swimming'
                AND l.es_largo=1 AND l.pace BETWEEN 1.3 AND 2.5
                ORDER BY l.fecha DESC LIMIT 500
            ''', conn, params=[atleta_id])

            if len(df_laps) > 20:
                # CSS por semana (percentil 20 de cada semana)
                df_laps['fecha'] = pd.to_datetime(df_laps['fecha'])
                df_laps['semana'] = df_laps['fecha'].dt.to_period('W')
                css_semanal = df_laps.groupby('semana')['pace'].quantile(0.20).tail(16)
                valores = css_semanal.tolist()
                tendencia = self._tendencia(valores)
                # CSS mejora = pace baja
                if tendencia['tendencia'] == 'mejorando':
                    tendencia['tendencia'] = 'empeorando'
                elif tendencia['tendencia'] == 'empeorando':
                    tendencia['tendencia'] = 'mejorando'
                tendencia['metrica'] = 'css_min_100m'
                tendencia['css_actual'] = round(float(css_semanal.iloc[-1]), 3) if len(css_semanal) else None
                return tendencia
        except Exception:
            pass

        # Fallback: pace de sesión
        df = _read_sql('''
            SELECT fecha, pace FROM sesiones
            WHERE atleta_id=%s AND sport IN ('swimming','swim')
            AND pace > 0 ORDER BY fecha DESC LIMIT 30
        ''', conn, params=[atleta_id])

        if df.empty:
            return {'tendencia': 'sin_datos'}

        tendencia = self._tendencia(df['pace'].tolist())
        tendencia['metrica'] = 'pace_sesion_min_100m'
        return tendencia


# ── Analizador de Adherencia (reemplaza Modelo 3 binario) ────────────────────
class AnalizadorAdherencia:
    """
    Analiza la adherencia del atleta a la prescripción en 3 dimensiones:
      1. TSS: % del volumen prescripto realizado (continuo 0-150%)
      2. Temporal: desvío en días entre prescripto y realizado
      3. Deporte: realizó el deporte correcto

    NO usa ML — métricas analíticas puras para coach y atleta.
    """

    def analizar(self, conn, atleta_id: int, semanas: int = 8) -> dict:
        desde = str(date.today() - timedelta(days=semanas * 7))

        df_presc = _read_sql('''
            SELECT semana_id, fecha_generada, tss_semana_total
            FROM prescripciones
            WHERE atleta_id=%s AND fecha_generada >= %s
            ORDER BY fecha_generada
        ''', conn, params=[atleta_id, desde])

        if df_presc.empty or len(df_presc) < 1:
            return {'disponible': False, 'mensaje': 'Sin historial de prescripciones'}

        df_real = _read_sql('''
            SELECT to_char(fecha::date, 'IYYY-IW') as semana,
                   SUM(tss_total) as tss_realizado,
                   COUNT(*) as sesiones_realizadas
            FROM sesiones
            WHERE atleta_id=%s AND fecha::date >= %s AND tss_total > 0
              AND (fuente IS NULL OR fuente NOT IN ('prescripcion','simulacion','generada'))
            GROUP BY to_char(fecha::date, 'IYYY-IW')
        ''', conn, params=[atleta_id, desde])

        df_presc['semana'] = pd.to_datetime(df_presc['fecha_generada']).dt.strftime('%G-%V')
        df_presc['tss_semana_total'] = pd.to_numeric(df_presc['tss_semana_total'], errors='coerce').fillna(0)

        if df_real.empty:
            return {'disponible': True, 'adherencia_tss_pct': 0,
                    'sesiones_por_semana': 0, 'tendencia': 'sin_datos',
                    'semanas': [], 'mensaje': 'Sin sesiones realizadas'}

        df = pd.merge(df_presc, df_real, on='semana', how='left')
        df['tss_realizado'] = pd.to_numeric(df['tss_realizado'], errors='coerce').fillna(0)

        df['adherencia_pct'] = np.where(
            df['tss_semana_total'] > 0,
            (df['tss_realizado'] / df['tss_semana_total'] * 100).clip(0, 150),
            np.nan
        )

        adherencia_media = float(df['adherencia_pct'].dropna().mean()) if df['adherencia_pct'].notna().any() else 0

        n = len(df)
        tendencia = 'sin_datos'
        if n >= 4:
            rec   = df['adherencia_pct'].tail(4).dropna()
            prev  = df['adherencia_pct'].head(max(1, n - 4)).dropna()
            if not rec.empty and not prev.empty:
                delta = float(rec.mean()) - float(prev.mean())
                tendencia = 'mejorando' if delta > 5 else ('empeorando' if delta < -5 else 'estable')

        semanas_det = []
        for _, row in df.iterrows():
            semanas_det.append({
                'semana':         row.get('semana', ''),
                'tss_prescripto': round(float(row['tss_semana_total']), 1),
                'tss_realizado':  round(float(row['tss_realizado']), 1),
                'adherencia_pct': round(float(row['adherencia_pct']) if pd.notna(row['adherencia_pct']) else 0, 1),
                'sesiones':       int(row['sesiones_realizadas']) if pd.notna(row.get('sesiones_realizadas')) else 0,
            })

        if adherencia_media >= 90:   clas, emoji = 'excelente', 'verde'
        elif adherencia_media >= 70: clas, emoji = 'buena',     'amarillo'
        elif adherencia_media >= 50: clas, emoji = 'moderada',  'naranja'
        else:                        clas, emoji = 'baja',       'rojo'

        return {
            'disponible':           True,
            'adherencia_tss_pct':   round(adherencia_media, 1),
            'clasificacion':         clas,
            'semaforo':              emoji,
            'tendencia':             tendencia,
            'semanas':               semanas_det,
            'n_semanas':             len(df),
            'sesiones_por_semana':   round(float(df['sesiones_realizadas'].dropna().mean()), 1)
                                      if 'sesiones_realizadas' in df.columns else 0,
        }


# ── Modelo 4: Detector de sobreentrenamiento ──────────────────────────────────
class DetectorSobreentrenamiento:
    """
    Detecta señales tempranas de sobreentrenamiento usando reglas
    derivadas del historial del atleta (no requiere ML pesado).
    """

    def analizar(self, conn, atleta_id: int,
                 ctl: float, atl: float, tsb: float) -> dict:
        alertas = []
        riesgo   = 0

        # HRV últimos 7 días
        df_hrv = _read_sql('''
            SELECT hrv_rmssd, hrv_flag, sleep_h, stress_avg
            FROM sleep_hrv WHERE atleta_id=%s
            ORDER BY fecha DESC LIMIT 7
        ''', conn, params=[atleta_id])

        if len(df_hrv) >= 5:
            dias_rojo    = (df_hrv['hrv_flag'] == 'rojo').sum()
            hrv_trend    = df_hrv['hrv_rmssd'].dropna()
            sleep_avg    = df_hrv['sleep_h'].dropna().mean()

            if dias_rojo >= 3:
                alertas.append({'nivel': 'alto', 'msg': f'{dias_rojo} días con HRV rojo en 7 días'})
                riesgo += 40

            if len(hrv_trend) >= 4:
                pendiente = float(np.polyfit(range(len(hrv_trend)), hrv_trend.values, 1)[0])
                if pendiente < -2:
                    alertas.append({'nivel': 'moderado', 'msg': f'HRV en caída ({pendiente:.1f} ms/día)'})
                    riesgo += 20

            if sleep_avg < 6.0:
                alertas.append({'nivel': 'moderado', 'msg': f'Sueño insuficiente: {sleep_avg:.1f}h promedio'})
                riesgo += 15

        # TSB muy negativo
        if tsb is not None:
            if tsb < -30:
                alertas.append({'nivel': 'alto', 'msg': f'TSB={tsb:.1f} — fatiga acumulada muy alta'})
                riesgo += 30
            elif tsb < -20:
                alertas.append({'nivel': 'moderado', 'msg': f'TSB={tsb:.1f} — fatiga elevada'})
                riesgo += 15

        # Ramp rate — carga semanal vs semana anterior. strftime("%Y-W%W",...)
        # (SQLite) reemplazado por to_char(...,'IYYY-IW') (formato semana
        # ISO de Postgres). date("now","-21 days") reemplazado por fecha
        # calculada en Python, mismo patrón usado en el resto de la migración.
        fecha_lim_21 = str(date.today() - timedelta(days=21))
        df_tss = _read_sql('''
            SELECT to_char(fecha::date, 'IYYY-IW') as semana, SUM(tss_total) as tss
            FROM sesiones WHERE atleta_id=%s AND fecha >= %s
            GROUP BY semana ORDER BY semana
        ''', conn, params=[atleta_id, fecha_lim_21])

        if len(df_tss) >= 2:
            tss_actual   = float(df_tss.iloc[-1]['tss'])
            tss_anterior = float(df_tss.iloc[-2]['tss'])
            if tss_anterior > 0:
                ramp = (tss_actual - tss_anterior) / tss_anterior * 100
                if ramp > 15:
                    alertas.append({'nivel': 'moderado',
                                    'msg': f'Carga subió {ramp:.0f}% vs semana anterior'})
                    riesgo += 15

        riesgo = min(100, riesgo)

        if riesgo >= 60:
            nivel_global = 'alto'
        elif riesgo >= 30:
            nivel_global = 'moderado'
        else:
            nivel_global = 'bajo'

        return {
            'riesgo_pct':   riesgo,
            'nivel':        nivel_global,
            'alertas':      alertas,
            'recomendacion': (
                'Reducir carga 30-50% esta semana y priorizar recuperación'
                if riesgo >= 60 else
                'Monitorear HRV y sueño. Evitar aumentar carga esta semana'
                if riesgo >= 30 else
                'Sin señales de sobreentrenamiento'
            ),
        }


# ── Predictor de Respuesta Fisiológica (corazón de NOAH) ─────────────────────
class PredictorRespuestaFisiologica:
    """
    Modelo central de NOAH — predice la respuesta fisiológica del atleta
    dado el TSS planificado y su estado actual.

    Basado en el modelo impulse-response de Banister (1975) extendido con ML:
    El modelo aprende los coeficientes de adaptación y fatiga PERSONALES
    de cada atleta desde su historial real.

    Targets construidos desde datos históricos reales:
      delta_ctl_7d:  cambio de CTL en 7 días (regresión — indica adaptación)
      delta_tsb_7d:  cambio de TSB en 7 días (regresión — indica recuperación)
      absorcion_ok:  1 si CTL no bajó y HRV no cayó > 10% (binario)
      riesgo_sobre:  1 si ATL/CTL > 1.5 o HRV cayó > 15% en 14d (binario)
    """

    FEATURES_BASE = [
        'ctl', 'atl', 'tsb',
        'tss_7d', 'tss_14d',
        'hrv_7d_avg', 'stress_7d_avg', 'sleep_7d_avg',
        'hrv_ratio_7d', 'delta_hrv', 'delta_stress',
        'sesion_intensa',
        # Ciclo cerrado: prescripcion -> realizado -> respuesta fisiologica
        'adherencia_7d',       # patron de cumplimiento personal (>1 sobreejercita)
        'hrv_respuesta_7d',    # como responde fisiologicamente a la carga prescripta
        'pct_sobrecarga_14d',  # % sesiones con sobrecarga reciente
        'patron_carga',        # indice integrado: adherencia x tolerancia HRV
    ]
    FEATURES_OPT = [
        'pct_deep_rem', 'hanna_vfc', 'hanna_vfc_ratio',
        'recovery_score', 'spo2_avg',
        'pct_optima_14d',      # % sesiones optimas recientes
    ]

    def __init__(self):
        self.modelo_delta_ctl  = None
        self.modelo_delta_tsb  = None
        self.modelo_absorcion  = None
        self.modelo_riesgo     = None
        self.entrenado         = False
        self.features_usados   = []
        self.scores            = {}
        self.ctl_baseline      = 30.0
        self.hrv_baseline      = 60.0
        self.n_muestras        = 0

    def _construir_targets(self, df: pd.DataFrame) -> pd.DataFrame:
        """Construye targets mirando 7-14 días hacia adelante."""
        df = df.copy().sort_values('fecha').reset_index(drop=True)
        n  = len(df)
        d_ctl, d_tsb, absorcion, riesgo = [], [], [], []

        for i in range(n):
            fut7  = df.iloc[i+1 : min(i+8, n)]
            fut14 = df.iloc[i+1 : min(i+15, n)]
            if len(fut7) < 4:
                d_ctl.append(None); d_tsb.append(None)
                absorcion.append(None); riesgo.append(None); continue

            ctl_h   = float(df.iloc[i].get('ctl')       or self.ctl_baseline)
            tsb_h   = float(df.iloc[i].get('tsb')       or 0)
            hrv_h   = float(df.iloc[i].get('hrv_rmssd') or self.hrv_baseline)

            ctl_f   = fut7['ctl'].dropna().tail(3).mean()    if 'ctl'       in fut7 else ctl_h
            tsb_f   = fut7['tsb'].dropna().tail(3).mean()    if 'tsb'       in fut7 else tsb_h
            hrv_f   = fut7['hrv_rmssd'].dropna().mean()      if 'hrv_rmssd' in fut7 else hrv_h

            d_ctl.append((ctl_f - ctl_h) if pd.notna(ctl_f) else None)
            d_tsb.append((tsb_f - tsb_h) if pd.notna(tsb_f) else None)

            if pd.notna(ctl_f) and pd.notna(hrv_f):
                absorcion.append(1 if (ctl_f >= ctl_h * 0.97 and (hrv_h <= 0 or hrv_f >= hrv_h * 0.90)) else 0)
            else:
                absorcion.append(None)

            r = 0
            if len(fut14) >= 5:
                atl_m = fut14['atl'].dropna().mean() if 'atl' in fut14 else 0
                ctl_m = fut14['ctl'].dropna().mean() if 'ctl' in fut14 else 1
                if ctl_m > 0 and (atl_m / ctl_m) > 1.5: r = 1
                if hrv_h > 0:
                    hrv_14 = fut14['hrv_rmssd'].dropna().mean() if 'hrv_rmssd' in fut14 else hrv_h
                    if hrv_14 < hrv_h * 0.85: r = 1
            riesgo.append(r)

        df['delta_ctl_7d'] = d_ctl
        df['delta_tsb_7d'] = d_tsb
        df['absorcion_ok']  = absorcion
        df['riesgo_sobre']  = riesgo
        return df

    def entrenar(self, df: pd.DataFrame) -> dict:
        try:
            from sklearn.ensemble import RandomForestRegressor, GradientBoostingClassifier
            from sklearn.model_selection import cross_val_score
            from sklearn.metrics import r2_score
        except ImportError:
            print('  [ML] scikit-learn no instalado'); return {}

        if df.empty or len(df) < 60:
            print(f'  [RespFisio] Datos insuficientes: {len(df)} filas (mín 60)'); return {}

        features = [f for f in self.FEATURES_BASE if f in df.columns]
        for f in self.FEATURES_OPT:
            if f in df.columns and df[f].notna().mean() >= 0.4:
                features.append(f)
        if len(features) < 4: return {}

        self.features_usados = features
        self.ctl_baseline    = float(df['ctl'].dropna().median())     if 'ctl'       in df.columns else 30.0
        self.hrv_baseline    = float(df['hrv_rmssd'].dropna().median()) if 'hrv_rmssd' in df.columns else 60.0

        df_t      = self._construir_targets(df)
        resultados = {}

        def _imputar(df_w, feats):
            for f in feats:
                med = df_w[f].median()
                df_w[f] = df_w[f].fillna(med if pd.notna(med) else 0)
            return df_w

        def _cv(modelo, X, y, scoring):
            cv = min(5, len(X) // 15)
            try:
                return float(np.mean(cross_val_score(modelo, X, y, cv=max(2, cv), scoring=scoring))) if cv >= 2 else float(modelo.score(X, y))
            except Exception:
                return float(modelo.score(X, y))

        # ── Regresión: delta_ctl_7d ──────────────────────────────────────────
        df_c = _imputar(df_t[features + ['delta_ctl_7d']].copy(), features).dropna(subset=['delta_ctl_7d'])
        if len(df_c) >= 40:
            X, y = df_c[features].values.astype(float), df_c['delta_ctl_7d'].values.astype(float)
            self.modelo_delta_ctl = RandomForestRegressor(n_estimators=150, max_depth=6, min_samples_leaf=5, n_jobs=-1, random_state=42)
            self.modelo_delta_ctl.fit(X, y)
            r2 = _cv(self.modelo_delta_ctl, X, y, 'r2')
            resultados['delta_ctl'] = {'r2': round(r2, 3), 'n': len(df_c)}
            print(f'  [RespFisio] delta_CTL_7d: R²={r2:.3f} ({len(df_c)} muestras)')

        # ── Regresión: delta_tsb_7d ──────────────────────────────────────────
        df_c = _imputar(df_t[features + ['delta_tsb_7d']].copy(), features).dropna(subset=['delta_tsb_7d'])
        if len(df_c) >= 40:
            X, y = df_c[features].values.astype(float), df_c['delta_tsb_7d'].values.astype(float)
            self.modelo_delta_tsb = RandomForestRegressor(n_estimators=150, max_depth=6, min_samples_leaf=5, n_jobs=-1, random_state=42)
            self.modelo_delta_tsb.fit(X, y)
            r2 = _cv(self.modelo_delta_tsb, X, y, 'r2')
            resultados['delta_tsb'] = {'r2': round(r2, 3), 'n': len(df_c)}
            print(f'  [RespFisio] delta_TSB_7d: R²={r2:.3f} ({len(df_c)} muestras)')

        # ── Clasificación: absorcion_ok ──────────────────────────────────────
        df_c = _imputar(df_t[features + ['absorcion_ok']].copy(), features).dropna(subset=['absorcion_ok'])
        if len(df_c) >= 40 and len(df_c['absorcion_ok'].unique()) >= 2:
            X, y = df_c[features].values.astype(float), df_c['absorcion_ok'].values.astype(int)
            self.modelo_absorcion = GradientBoostingClassifier(n_estimators=100, max_depth=3, learning_rate=0.05, random_state=42)
            self.modelo_absorcion.fit(X, y)
            f1 = _cv(self.modelo_absorcion, X, y, 'f1')
            resultados['absorcion_ok'] = {'f1': round(f1, 3), 'n': len(df_c), 'pct_pos': round(y.mean()*100, 1)}
            print(f'  [RespFisio] absorcion_ok: F1={f1:.3f} ({len(df_c)} días, {y.mean()*100:.0f}% positivos)')

        # ── Clasificación: riesgo_sobre ──────────────────────────────────────
        df_c = _imputar(df_t[features + ['riesgo_sobre']].copy(), features).dropna(subset=['riesgo_sobre'])
        if len(df_c) >= 40 and len(df_c['riesgo_sobre'].unique()) >= 2:
            X, y = df_c[features].values.astype(float), df_c['riesgo_sobre'].values.astype(int)
            self.modelo_riesgo = GradientBoostingClassifier(n_estimators=100, max_depth=3, learning_rate=0.05, random_state=42)
            self.modelo_riesgo.fit(X, y)
            f1 = _cv(self.modelo_riesgo, X, y, 'f1')
            resultados['riesgo_sobre'] = {'f1': round(f1, 3), 'n': len(df_c), 'pct_pos': round(y.mean()*100, 1)}
            print(f'  [RespFisio] riesgo_sobre: F1={f1:.3f} ({len(df_c)} días, {y.mean()*100:.0f}% positivos)')

        if resultados:
            self.entrenado   = True
            self.n_muestras  = len(df_t)
            self.scores      = resultados
        return resultados

    def _vectorizar(self, estado: dict) -> np.ndarray:
        return np.array([[_safe_float(estado.get(f), 0.0) for f in self.features_usados]])

    def predecir(self, estado: dict, tss_plan: float = None) -> dict:
        if not self.entrenado:
            return {'disponible': False}
        if tss_plan is not None:
            estado = {**estado, 'tss_7d': tss_plan}
        X   = self._vectorizar(estado)
        res = {'disponible': True, 'tss_evaluado': tss_plan}

        if self.modelo_delta_ctl:
            d = float(self.modelo_delta_ctl.predict(X)[0])
            res['delta_ctl_predicho'] = round(d, 2)
            res['ctl_predicho_7d']    = round(float(estado.get('ctl', self.ctl_baseline)) + d, 1)

        if self.modelo_delta_tsb:
            d = float(self.modelo_delta_tsb.predict(X)[0])
            res['delta_tsb_predicho'] = round(d, 2)
            res['tsb_predicho_7d']    = round(float(estado.get('tsb', 0)) + d, 1)

        prob_abs = 0.5
        prob_rie = 0.3
        if self.modelo_absorcion:
            prob_abs = float(self.modelo_absorcion.predict_proba(X)[0][1])
            res['prob_absorcion'] = round(prob_abs, 3)
        if self.modelo_riesgo:
            prob_rie = float(self.modelo_riesgo.predict_proba(X)[0][1])
            res['prob_riesgo_sobrecarga'] = round(prob_rie, 3)

        d_ctl = res.get('delta_ctl_predicho', 0)
        if prob_rie >= 0.65 or prob_abs < 0.35:
            res['semaforo'] = 'rojo'
            res['interpretacion'] = 'Alto riesgo de sobrecarga — reducir TSS planificado'
        elif prob_abs >= 0.70 and d_ctl >= 0:
            res['semaforo'] = 'verde'
            res['interpretacion'] = 'Buena absorción esperada — carga adecuada al estado actual'
        else:
            res['semaforo'] = 'amarillo'
            res['interpretacion'] = 'Absorción moderada — monitorear HRV y sueño esta semana'
        return res

    def simular_escenarios(self, estado: dict, opciones_tss: list) -> list:
        """Simula respuesta fisiológica para múltiples TSS. Usado por Optimizer."""
        if not self.entrenado: return []
        return [{**self.predecir(estado, tss_plan=tss), 'tss_plan': tss} for tss in opciones_tss]

    def importancia_features(self) -> dict:
        result = {}
        for nombre, m in [('delta_ctl', self.modelo_delta_ctl), ('absorcion', self.modelo_absorcion), ('riesgo', self.modelo_riesgo)]:
            if m and hasattr(m, 'feature_importances_'):
                imp = dict(zip(self.features_usados, m.feature_importances_))
                result[nombre] = {k: round(v, 3) for k, v in sorted(imp.items(), key=lambda x: -x[1])[:8]}
        return result


# ── NOAH Mind — Interfaz principal ───────────────────────────────────────────


# ── Modelo de Impacto-Respuesta Individual (legacy — mantenido para compatibilidad) ────
class ModeloImpactoRespuesta:
    """
    Evalúa si la carga de entrenamiento fue adecuada para el atleta
    dado su estado de biomarcadores previos.

    NO predice biomarcadores futuros.
    EVALÚA si la carga fue correcta dado el estado del atleta.

    Targets construidos desde datos históricos:
      absorcion_ok: en los 7 días siguientes CTL no bajó, stress no se disparó
      riesgo_sobre: en los 14 días siguientes ATL/CTL > 1.5 o stress sostenido alto
    """

    # Features base — todos deben estar disponibles para la mayoría de atletas
    FEATURES = [
        'tss_dia', 'sesion_intensa', 'ctl', 'atl', 'tsb', 'tss_7d',
        'stress_avg', 'sleep_h', 'pct_deep_rem',
        'stress_7d_avg', 'sleep_7d_avg', 'delta_stress',
    ]
    # Features opcionales — se agregan si tienen suficientes datos
    FEATURES_OPT = ['fc_nocturna', 'recovery_score', 'hanna_vfc']

    def __init__(self):
        self.modelo_absorcion = None
        self.modelo_riesgo    = None
        self.entrenado        = False
        self.n_muestras       = 0
        self.scores           = {}
        self.features_usados  = []

    def _construir_labels(self, df):
        import numpy as np
        df = df.copy().reset_index(drop=True)
        n = len(df)
        absorcion, riesgo = [], []

        for i in range(n):
            fut7  = df.iloc[i+1:min(i+8,n)]
            fut14 = df.iloc[i+1:min(i+15,n)]

            if len(fut7) < 3:
                absorcion.append(None)
                riesgo.append(None)
                continue

            ctl_h    = float(df.iloc[i].get('ctl')       or 0)
            stress_h = float(df.iloc[i].get('stress_avg') or 30)
            sleep_h  = float(df.iloc[i].get('sleep_h')   or 7)

            ctl_f    = fut7['ctl'].dropna().mean()    if 'ctl'       in fut7 else ctl_h
            stress_f = fut7['stress_avg'].dropna().mean() if 'stress_avg' in fut7 else stress_h
            sleep_f  = fut7['sleep_h'].dropna().mean()    if 'sleep_h'    in fut7 else sleep_h

            ok = (ctl_f    >= ctl_h    * 0.95 if ctl_h    > 0 else True) and                  (stress_f <= stress_h * 1.30 if stress_h > 0 else True) and                  (sleep_f  >= sleep_h  * 0.85 if sleep_h  > 0 else True)
            absorcion.append(1 if ok else 0)

            if len(fut14) < 5:
                riesgo.append(None)
                continue

            atl_m = fut14['atl'].dropna().mean() if 'atl' in fut14 else 0
            ctl_m = fut14['ctl'].dropna().mean() if 'ctl' in fut14 else 1
            r_atl = (atl_m / max(ctl_m, 1)) > 1.5

            if 'stress_avg' in fut14:
                dias_alto = (fut14['stress_avg'].dropna() > stress_h * 1.3).sum()
                r_stress  = dias_alto >= 3
            else:
                r_stress = False

            riesgo.append(1 if (r_atl or r_stress) else 0)

        df['absorcion_ok'] = absorcion
        df['riesgo_sobre'] = riesgo
        return df

    def entrenar(self, df) -> dict:
        try:
            from sklearn.ensemble import GradientBoostingClassifier
            from sklearn.model_selection import cross_val_score
            import numpy as np
        except ImportError:
            return {}

        df_lab   = self._construir_labels(df)
        # Features base disponibles
        features = [f for f in self.FEATURES if f in df_lab.columns]
        # Agregar opcionales si tienen >50% de datos no nulos
        for f in self.FEATURES_OPT:
            if f in df_lab.columns:
                pct = df_lab[f].notna().mean()
                if pct >= 0.5:
                    features.append(f)
        print(f'    [Impacto] Features: {len(features)} | Filas totales: {len(df_lab)} | Con TSS: {(df_lab.get("tss_dia",pd.Series()).fillna(0)>0).sum()}')
        if len(features) < 4:
            return {}

        self.features_usados = features
        resultados = {}

        for target in ['absorcion_ok', 'riesgo_sobre']:
            if target not in df_lab.columns:
                continue

            # Usar solo features con suficientes datos para este atleta
            features_ok = [f for f in features
                          if f in df_lab.columns and df_lab[f].notna().mean() >= 0.3]
            if len(features_ok) < 4:
                continue

            # Imputar NaN con mediana para features disponibles
            df_work = df_lab[features_ok + [target]].copy()
            for f in features_ok:
                med = df_work[f].median()
                df_work[f] = df_work[f].fillna(med if pd.notna(med) else 0)

            df_c = df_work.dropna(subset=[target])
            df_c = df_c[df_c[target].notna()]

            if len(df_c) < 30 or len(df_c[target].unique()) < 2:
                continue

            X = df_c[features_ok].values.astype(float)
            y = df_c[target].values.astype(int)
            features = features_ok  # usar los features válidos para este atleta

            m = GradientBoostingClassifier(
                n_estimators=100, max_depth=3, learning_rate=0.05, random_state=42)
            m.fit(X, y)

            try:
                cv = min(5, len(X)//10)
                f1 = float(np.mean(cross_val_score(m, X, y, cv=max(2,cv), scoring='f1'))) if cv >= 2 else float(m.score(X, y))
            except Exception:
                f1 = float(m.score(X, y))

            if target == 'absorcion_ok':
                self.modelo_absorcion = m
                self.features_usados  = features_ok
            else:
                self.modelo_riesgo = m
                if not self.features_usados:
                    self.features_usados = features_ok

            resultados[target] = {'f1': round(f1,3), 'n': len(df_c),
                                   'pct_pos': round(y.mean()*100,1)}
            print(f'    {target}: F1={f1:.3f} ({len(df_c)} días, {y.mean()*100:.0f}% positivos)')

        self.entrenado  = self.modelo_absorcion is not None
        self.n_muestras = len(df)
        self.scores     = resultados
        return resultados


    @staticmethod
    def evaluar_por_reglas(estado: dict, tss_sesion: float,
                           sesion_intensa: bool = False) -> dict:
        # Foster 1998, Halson 2014, Meeusen et al. 2013
        est    = estado.get('estado', estado)
        tsb    = float(est.get('tsb')        or 0)
        sleep  = float(est.get('sleep_h')    or 7)
        stress = float(est.get('stress_avg') or 25)
        atl    = float(est.get('atl')        or 0)
        ctl    = float(est.get('ctl')        or 1)
        ratio  = atl / max(ctl, 1)

        factores = []
        puntos   = 0

        # TSB — Banister 1991
        if tsb < -30:   puntos += 3; factores.append(f"TSB muy negativo ({tsb:.0f}) — sobrecarga acumulada")
        elif tsb < -20: puntos += 2; factores.append(f"TSB negativo ({tsb:.0f}) — fatiga acumulada")
        elif tsb < -10: puntos += 1

        # Sueño — Halson 2014
        if sleep < 6:   puntos += 2; factores.append(f"Sueño insuficiente ({sleep:.1f}h)")
        elif sleep < 6.5: puntos += 1; factores.append(f"Sueño bajo ({sleep:.1f}h)")

        # Stress — Foster 1998
        if stress > 50:   puntos += 2; factores.append(f"Stress elevado ({stress:.0f})")
        elif stress > 35: puntos += 1

        # ATL/CTL — Meeusen 2013
        if ratio > 1.5:   puntos += 3; factores.append(f"Fatiga aguda muy alta (ATL/CTL={ratio:.2f})")
        elif ratio > 1.3: puntos += 2; factores.append(f"Fatiga aguda alta (ATL/CTL={ratio:.2f})")

        if sesion_intensa and puntos >= 2:
            puntos += 1

        if puntos == 0:
            clas, emoji, msg = 'adecuada', '🟢', 'Estado optimo para cargar.'
        elif puntos <= 2:
            clas, emoji, msg = 'moderada', '🟡', 'Carga posible. Monitorear biomarcadores post-sesion.'
        else:
            clas, emoji, msg = 'excesiva', '🔴', 'Riesgo de sobreentrenamiento. Reducir TSS.'

        return {
            'evaluado':       True,
            'metodo':         'reglas_bibliograficas',
            'clasificacion':  clas,
            'emoji':          emoji,
            'mensaje':        msg,
            'prob_absorcion': round(max(0.0, 1.0 - puntos * 0.15), 2),
            'prob_riesgo':    round(min(1.0, puntos * 0.15), 2),
            'factores':       factores,
            'tss_evaluado':   tss_sesion,
            'nota':           'Reglas: Foster 1998, Halson 2014, Meeusen 2013. ML activo con >200 dias de datos.',
        }

    def evaluar_sesion(self, estado: dict, tss_sesion: float,
                       sesion_intensa: bool = False) -> dict:
        if not self.entrenado:
            return self.evaluar_por_reglas(estado, tss_sesion, sesion_intensa)

        est  = estado.get('estado', estado)
        sleep = float(est.get('sleep_h') or 7)
        deep  = float(est.get('deep_h')  or 0)
        rem   = float(est.get('rem_h')   or 0)

        vals = []
        for f in self.features_usados:
            if f == 'tss_dia':          vals.append(tss_sesion)
            elif f == 'sesion_intensa': vals.append(1.0 if sesion_intensa else 0.0)
            elif f == 'pct_deep_rem':   vals.append((deep+rem)/max(sleep,1))
            else:                       vals.append(float(est.get(f) or 0))

        X = [vals]
        prob_abs   = float(self.modelo_absorcion.predict_proba(X)[0][1]) if self.modelo_absorcion else 0.5
        prob_riesgo = float(self.modelo_riesgo.predict_proba(X)[0][1])   if self.modelo_riesgo    else 0.0

        if   prob_abs >= 0.70 and prob_riesgo < 0.30:
            clas, emoji, msg = 'adecuada',  '🟢', 'Atleta en condiciones de absorber esta carga.'
        elif prob_abs >= 0.50 and prob_riesgo < 0.50:
            clas, emoji, msg = 'moderada',  '🟡', 'Carga posible. Monitorear biomarcadores post-sesión.'
        else:
            clas, emoji, msg = 'excesiva',  '🔴', 'Riesgo de sobreentrenamiento. Reducir TSS.'

        factores = []
        if (est.get('stress_avg') or 0) > 40:     factores.append(f'Stress elevado ({est.get("stress_avg"):.0f})')
        if sleep < 6:                               factores.append(f'Sueño insuficiente ({sleep:.1f}h)')
        if (est.get('tsb') or 0) < -20:            factores.append(f'TSB negativo ({est.get("tsb"):.1f})')
        atl = est.get('atl') or 0
        ctl = est.get('ctl') or 1
        if atl > ctl * 1.4:                        factores.append(f'Fatiga aguda alta (ATL/CTL={atl/max(ctl,1):.2f})')

        return {
            'evaluado':       True,
            'clasificacion':  clas,
            'emoji':          emoji,
            'mensaje':        msg,
            'prob_absorcion': round(prob_abs, 2),
            'prob_riesgo':    round(prob_riesgo, 2),
            'factores':       factores,
            'tss_evaluado':   tss_sesion,
        }

    def importancia_features(self) -> dict:
        result = {}
        for nombre, m in [('absorcion', self.modelo_absorcion), ('riesgo', self.modelo_riesgo)]:
            if m and hasattr(m, 'feature_importances_'):
                imp = dict(zip(self.features_usados, m.feature_importances_))
                result[nombre] = {k: round(v,3) for k,v in sorted(imp.items(), key=lambda x:-x[1])[:6]}
        return result



# ── Predictor GRU con Atención Temporal ──────────────────────────────────────
class _GRUEncoder(object):
    """
    Marcador para identificar el encoder compartido del Foundation Model.
    La arquitectura real vive en PredictorLSTM._build_model().
    """
    pass


class PredictorLSTM:
    """
    Red neuronal GRU con mecanismo de atención temporal.
    
    Por qué GRU + Atención sobre LSTM puro:
    - GRU: menos parámetros que LSTM, igual performance con 1500-3000 días
    - Atención: aprende QUÉ días de los últimos 28 importan más
      (ej: el día post-carrera pesa más que un martes normal)
    - Ideal para datos biológicos con patrones cíclicos (mesociclos)

    Arquitectura:
      Input:  [batch, 28 días, 17 features]
          ↓
      GRU(64, bidireccional=True) → [batch, 28, 128]
          ↓
      Attention Layer → [batch, 128]  (aprende pesos por día)
          ↓
      Dense(64, relu) → Dropout(0.3)
          ↓
      Dense(32, relu) → Dropout(0.2)
          ↓
      Output(4): [delta_ctl_7d, delta_tsb_7d, prob_absorcion, prob_riesgo]
    """

    SEQ_LEN  = 28   # días de historia que ve el modelo
    FEATURES = [
        'ctl', 'atl', 'tsb', 'tss_dia',
        'hrv_rmssd', 'stress_avg', 'sleep_h',
        'hrv_7d_avg', 'stress_7d_avg', 'sleep_7d_avg',
        'hrv_ratio_7d', 'delta_hrv', 'tss_7d',
        'adherencia_7d', 'hrv_respuesta_7d', 'patron_carga',
        'sesion_intensa',
    ]
    TARGETS  = ['delta_ctl_7d', 'delta_tsb_7d', 'absorcion_ok', 'riesgo_sobre']

    def __init__(self):
        self.modelo       = None
        self.scaler_X     = None
        self.scaler_y     = None
        self.entrenado    = False
        self.score        = {}
        self.features_ok  = []
        self.n_muestras   = 0
        self.ctl_baseline = 30.0

    def _verificar_pytorch(self) -> bool:
        try:
            import torch
            return True
        except ImportError:
            print('  [GRU] PyTorch no instalado. Correr: pip install torch --break-system-packages')
            return False

    def _construir_targets(self, df: pd.DataFrame) -> pd.DataFrame:
        """Mismo metodo que PredictorRespuestaFisiologica."""
        df = df.copy().sort_values('fecha').reset_index(drop=True)
        n  = len(df)
        d_ctl, d_tsb, absorcion, riesgo = [], [], [], []

        for i in range(n):
            fut7  = df.iloc[i+1 : min(i+8, n)]
            fut14 = df.iloc[i+1 : min(i+15, n)]
            if len(fut7) < 4:
                d_ctl.append(None); d_tsb.append(None)
                absorcion.append(None); riesgo.append(None); continue

            ctl_h = float(df.iloc[i].get('ctl') or self.ctl_baseline)
            tsb_h = float(df.iloc[i].get('tsb') or 0)
            hrv_h = float(df.iloc[i].get('hrv_rmssd') or 60)

            ctl_f = fut7['ctl'].dropna().tail(3).mean()    if 'ctl'       in fut7 else ctl_h
            tsb_f = fut7['tsb'].dropna().tail(3).mean()    if 'tsb'       in fut7 else tsb_h
            hrv_f = fut7['hrv_rmssd'].dropna().mean()      if 'hrv_rmssd' in fut7 else hrv_h

            d_ctl.append((ctl_f - ctl_h) if pd.notna(ctl_f) else None)
            d_tsb.append((tsb_f - tsb_h) if pd.notna(tsb_f) else None)

            if pd.notna(ctl_f) and pd.notna(hrv_f):
                absorcion.append(1 if (ctl_f >= ctl_h * 0.97 and
                                       (hrv_h <= 0 or hrv_f >= hrv_h * 0.90)) else 0)
            else:
                absorcion.append(None)

            r = 0
            if len(fut14) >= 5:
                atl_m = fut14['atl'].dropna().mean() if 'atl' in fut14 else 0
                ctl_m = fut14['ctl'].dropna().mean() if 'ctl' in fut14 else 1
                if ctl_m > 0 and (atl_m / ctl_m) > 1.5: r = 1
                if hrv_h > 0:
                    hrv_14 = fut14['hrv_rmssd'].dropna().mean() if 'hrv_rmssd' in fut14 else hrv_h
                    if hrv_14 < hrv_h * 0.85: r = 1
            riesgo.append(r)

        df['delta_ctl_7d'] = d_ctl
        df['delta_tsb_7d'] = d_tsb
        df['absorcion_ok']  = absorcion
        df['riesgo_sobre']  = riesgo
        return df

    def _construir_secuencias(self, df: pd.DataFrame):
        """
        Convierte el dataframe en secuencias de SEQ_LEN dias.
        Cada secuencia [X_t-28..t] predice [y_t+7].
        """
        import numpy as np
        features = [f for f in self.FEATURES if f in df.columns]
        self.features_ok = features

        df_t = self._construir_targets(df)
        df_t = df_t.sort_values('fecha').reset_index(drop=True)

        # Imputar NaN con mediana por columna
        for f in features:
            med = df_t[f].median()
            df_t[f] = df_t[f].fillna(med if pd.notna(med) else 0)

        X_seqs, y_seqs = [], []
        n = len(df_t)

        for i in range(self.SEQ_LEN, n):
            # Targets del dia i (mirando 7 dias al futuro)
            row = df_t.iloc[i]
            targets = [
                row.get('delta_ctl_7d'),
                row.get('delta_tsb_7d'),
                row.get('absorcion_ok'),
                row.get('riesgo_sobre'),
            ]
            if any(t is None or (isinstance(t, float) and np.isnan(t)) for t in targets):
                continue

            # Secuencia de los 28 dias anteriores
            seq = df_t.iloc[i - self.SEQ_LEN : i][features].values.astype(float)
            if seq.shape[0] != self.SEQ_LEN:
                continue

            X_seqs.append(seq)
            y_seqs.append(targets)

        if not X_seqs:
            return None, None

        return np.array(X_seqs, dtype=np.float32), np.array(y_seqs, dtype=np.float32)

    def entrenar(self, df: pd.DataFrame, epochs: int = 80, lr: float = 1e-3) -> dict:
        if not self._verificar_pytorch():
            return {}

        import torch
        import torch.nn as nn
        from sklearn.preprocessing import StandardScaler

        if df.empty or len(df) < self.SEQ_LEN + 30:
            print(f'  [GRU] Datos insuficientes: {len(df)} filas (min {self.SEQ_LEN + 30})')
            return {}

        self.ctl_baseline = float(df['ctl'].dropna().median()) if 'ctl' in df.columns else 30.0

        print(f'  [GRU] Construyendo secuencias de {self.SEQ_LEN} dias...')
        X, y = self._construir_secuencias(df)
        if X is None or len(X) < 50:
            print(f'  [GRU] Secuencias insuficientes: {0 if X is None else len(X)}')
            return {}

        print(f'  [GRU] {len(X)} secuencias | {X.shape[2]} features | 4 targets')

        # Normalizar features (por feature, no por secuencia)
        n_seq, seq_len, n_feat = X.shape
        X_2d = X.reshape(-1, n_feat)
        self.scaler_X = StandardScaler()
        X_2d_norm = self.scaler_X.fit_transform(X_2d)
        X_norm = X_2d_norm.reshape(n_seq, seq_len, n_feat)

        # Normalizar targets continuos (delta_ctl, delta_tsb), dejar binarios igual
        self.scaler_y = StandardScaler()
        y_cont = self.scaler_y.fit_transform(y[:, :2])
        y_norm = np.concatenate([y_cont, y[:, 2:]], axis=1)

        # Split train/val 85/15
        split = int(len(X_norm) * 0.85)
        X_tr, X_val = X_norm[:split], X_norm[split:]
        y_tr, y_val = y_norm[:split], y_norm[split:]

        X_tr  = torch.tensor(X_tr,  dtype=torch.float32)
        y_tr  = torch.tensor(y_tr,  dtype=torch.float32)
        X_val = torch.tensor(X_val, dtype=torch.float32)
        y_val = torch.tensor(y_val, dtype=torch.float32)

        # ── Arquitectura GRU + Atención ──────────────────────────────────────
        class AttentionLayer(nn.Module):
            def __init__(self, hidden_dim):
                super().__init__()
                self.attn = nn.Linear(hidden_dim, 1)

            def forward(self, gru_out):
                # gru_out: [batch, seq, hidden]
                scores = self.attn(gru_out).squeeze(-1)         # [batch, seq]
                weights = torch.softmax(scores, dim=1)           # [batch, seq]
                context = (gru_out * weights.unsqueeze(-1)).sum(dim=1)  # [batch, hidden]
                return context, weights

        class GRUAttnModel(nn.Module):
            def __init__(self, n_feat):
                super().__init__()
                self.gru1  = nn.GRU(n_feat, 64, batch_first=True, bidirectional=True)
                self.attn  = AttentionLayer(128)  # 64*2 bidireccional
                self.gru2  = nn.GRU(128, 32, batch_first=True)
                self.drop1 = nn.Dropout(0.3)
                self.fc1   = nn.Linear(32, 64)
                self.drop2 = nn.Dropout(0.2)
                self.fc2   = nn.Linear(64, 32)
                self.out   = nn.Linear(32, 4)
                self.relu  = nn.ReLU()

            def forward(self, x):
                out, _ = self.gru1(x)            # [batch, seq, 128]
                ctx, _ = self.attn(out)          # [batch, 128]
                ctx    = ctx.unsqueeze(1)        # [batch, 1, 128]
                out, _ = self.gru2(ctx)          # [batch, 1, 32]
                out    = out.squeeze(1)          # [batch, 32]
                out    = self.drop1(out)
                out    = self.relu(self.fc1(out))
                out    = self.drop2(out)
                out    = self.relu(self.fc2(out))
                return self.out(out)             # [batch, 4]

            def get_attention_weights(self, x):
                out, _ = self.gru1(x)
                _, weights = self.attn(out)
                return weights

        modelo = GRUAttnModel(n_feat)
        optimizer = torch.optim.Adam(modelo.parameters(), lr=lr, weight_decay=1e-5)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=8, factor=0.5)

        # Loss mixta: MSE para deltas (continuos) + BCE para clasificacion (binarios)
        mse  = nn.MSELoss()
        bce  = nn.BCEWithLogitsLoss()

        def loss_fn(pred, target):
            loss_reg  = mse(pred[:, :2], target[:, :2])          # delta_ctl, delta_tsb
            loss_cls  = bce(pred[:, 2:], target[:, 2:].clamp(0, 1))  # absorcion, riesgo
            return loss_reg * 0.6 + loss_cls * 0.4

        # Training con early stopping
        mejor_val   = float('inf')
        paciencia   = 15
        sin_mejora  = 0
        mejor_estado = None

        print(f'  [GRU] Entrenando {epochs} épocas...')
        for ep in range(epochs):
            modelo.train()
            pred_tr  = modelo(X_tr)
            loss_tr  = loss_fn(pred_tr, y_tr)
            optimizer.zero_grad()
            loss_tr.backward()
            torch.nn.utils.clip_grad_norm_(modelo.parameters(), 1.0)
            optimizer.step()

            modelo.eval()
            with torch.no_grad():
                pred_val = modelo(X_val)
                loss_val = loss_fn(pred_val, y_val).item()

            scheduler.step(loss_val)

            if loss_val < mejor_val:
                mejor_val    = loss_val
                sin_mejora   = 0
                mejor_estado = {k: v.clone() for k, v in modelo.state_dict().items()}
            else:
                sin_mejora += 1
                if sin_mejora >= paciencia:
                    print(f'  [GRU] Early stopping en época {ep+1} (val_loss={mejor_val:.4f})')
                    break

            if (ep + 1) % 20 == 0:
                print(f'  [GRU] Época {ep+1:3d} | train={loss_tr.item():.4f} | val={loss_val:.4f}')

        # Cargar mejor modelo
        if mejor_estado:
            modelo.load_state_dict(mejor_estado)

        self.modelo    = modelo
        self.entrenado = True
        self.n_muestras = len(X)
        self.score     = {'val_loss': round(mejor_val, 4), 'n_seq': len(X), 'n_feat': n_feat}

        print(f'  [GRU] Entrenado: val_loss={mejor_val:.4f} | {len(X)} secuencias | {n_feat} features')
        return self.score

    def predecir(self, df_reciente: pd.DataFrame) -> dict:
        """
        Predice usando los ultimos SEQ_LEN dias del dataframe.
        """
        if not self.entrenado or self.modelo is None:
            return {'disponible': False}
        if not self._verificar_pytorch():
            return {'disponible': False}

        import torch
        import numpy as np

        features = self.features_ok
        if len(df_reciente) < self.SEQ_LEN:
            return {'disponible': False, 'razon': f'Necesita {self.SEQ_LEN} dias, tiene {len(df_reciente)}'}

        df_seq = df_reciente.tail(self.SEQ_LEN).copy()
        for f in features:
            med = df_seq[f].median()
            df_seq[f] = df_seq[f].fillna(med if pd.notna(med) else 0)

        X = df_seq[features].values.astype(np.float32)

        # Normalizar
        n_feat = X.shape[1]
        X_norm = self.scaler_X.transform(X)
        X_tensor = torch.tensor(X_norm[np.newaxis, :, :], dtype=torch.float32)

        self.modelo.eval()
        with torch.no_grad():
            pred   = self.modelo(X_tensor).numpy()[0]
            pesos  = self.modelo.get_attention_weights(X_tensor).numpy()[0]

        # Desnormalizar outputs continuos
        cont = self.scaler_y.inverse_transform(pred[:2].reshape(1, -1))[0]

        prob_abs = float(torch.sigmoid(torch.tensor(pred[2])).item())
        prob_rie = float(torch.sigmoid(torch.tensor(pred[3])).item())

        # Dias mas importantes (top 5 por peso de atencion)
        top_dias = sorted(enumerate(pesos), key=lambda x: -x[1])[:5]
        dias_clave = [{'dia_atras': self.SEQ_LEN - i, 'peso': round(float(w), 3)}
                      for i, w in top_dias]

        if prob_rie >= 0.65 or prob_abs < 0.35:
            semaforo = 'rojo'
            msg = 'GRU detecta alto riesgo — reducir carga'
        elif prob_abs >= 0.70 and cont[0] >= 0:
            semaforo = 'verde'
            msg = 'GRU predice buena absorcion y adaptacion positiva'
        else:
            semaforo = 'amarillo'
            msg = 'GRU predice absorcion moderada — monitorear'

        return {
            'disponible':            True,
            'delta_ctl_predicho':    round(float(cont[0]), 2),
            'delta_tsb_predicho':    round(float(cont[1]), 2),
            'prob_absorcion':        round(prob_abs, 3),
            'prob_riesgo':           round(prob_rie, 3),
            'semaforo':              semaforo,
            'interpretacion':        msg,
            'dias_clave_atencion':   dias_clave,
        }

    def guardar(self, ruta: str):
        if not self.entrenado: return
        try:
            import torch, joblib, os
            os.makedirs(ruta, exist_ok=True)
            torch.save(self.modelo.state_dict(), f'{ruta}/gru_model.pth')
            joblib.dump(self.scaler_X,  f'{ruta}/gru_scaler_X.pkl')
            joblib.dump(self.scaler_y,  f'{ruta}/gru_scaler_y.pkl')
            joblib.dump({
                'features_ok':  self.features_ok,
                'score':        self.score,
                'ctl_baseline': self.ctl_baseline,
            }, f'{ruta}/gru_meta.pkl')
            print(f'  [GRU] Modelo guardado en {ruta}/')
        except Exception as e:
            print(f'  [GRU] Error guardando: {e}')

    def fine_tune_from(self, foundation_path: str, df: pd.DataFrame,
                       epochs: int = 30, lr: float = 5e-4) -> dict:
        """
        Fine-tune desde un Foundation Model pre-entrenado.

        Fase 2/3 de la arquitectura NOAH:
        - Carga el encoder pre-entrenado (congelado — no se modifica)
        - Entrena solo el head (decoder) con datos del atleta especifico
        - Convergencia rapida: 30 epocas vs 80 del entrenamiento completo
        - El atleta nuevo hereda todo el conocimiento fisiologico general
        """
        if not self._verificar_pytorch():
            return {}
        import torch, joblib, os
        import torch.nn as nn

        # Cargar foundation encoder
        meta_path = f'{foundation_path}/foundation_meta.pkl'
        if not os.path.exists(meta_path):
            print('  [GRU] Foundation model no encontrado — entrenar desde cero')
            return self.entrenar(df, epochs=epochs*2, lr=lr)

        meta = joblib.load(meta_path)
        self.features_ok  = meta['features_ok']
        self.ctl_baseline = meta.get('ctl_baseline', 30.0)
        self.scaler_X     = joblib.load(f'{foundation_path}/foundation_scaler_X.pkl')
        self.scaler_y     = joblib.load(f'{foundation_path}/foundation_scaler_y.pkl')

        X, y = self._construir_secuencias(df)
        if X is None or len(X) < 20:
            print('  [GRU] Datos insuficientes para fine-tune')
            return {}

        n_seq, seq_len, n_feat = X.shape
        from sklearn.preprocessing import StandardScaler
        X_2d_norm = self.scaler_X.transform(X.reshape(-1, n_feat))
        X_norm    = X_2d_norm.reshape(n_seq, seq_len, n_feat)
        y_cont    = self.scaler_y.transform(y[:, :2])
        y_norm    = np.concatenate([y_cont, y[:, 2:]], axis=1)

        split   = int(len(X_norm) * 0.85)
        X_tr    = torch.tensor(X_norm[:split],  dtype=torch.float32)
        y_tr    = torch.tensor(y_norm[:split],  dtype=torch.float32)
        X_val   = torch.tensor(X_norm[split:],  dtype=torch.float32)
        y_val   = torch.tensor(y_norm[split:],  dtype=torch.float32)

        # Construir modelo y cargar encoder pre-entrenado
        modelo = self._build_model(n_feat)
        state  = torch.load(f'{foundation_path}/foundation_encoder.pth', map_location='cpu')
        modelo.load_state_dict(state, strict=False)  # carga lo que matchea

        # Congelar encoder (GRU1 + Attention), solo entrenar head
        for name, param in modelo.named_parameters():
            if 'gru1' in name or 'attn' in name:
                param.requires_grad = False  # encoder congelado
            else:
                param.requires_grad = True   # head se entrena

        n_trainable = sum(p.numel() for p in modelo.parameters() if p.requires_grad)
        n_total     = sum(p.numel() for p in modelo.parameters())
        print(f'  [GRU] Fine-tune: {n_trainable}/{n_total} params libres ({n_trainable/n_total*100:.0f}%)')

        optimizer = torch.optim.Adam(
            [p for p in modelo.parameters() if p.requires_grad], lr=lr)
        mse = nn.MSELoss()
        bce = nn.BCEWithLogitsLoss()
        def loss_fn(pred, target):
            return mse(pred[:, :2], target[:, :2]) * 0.6 + bce(pred[:, 2:], target[:, 2:].clamp(0,1)) * 0.4

        mejor_val, mejor_estado = float('inf'), None
        for ep in range(epochs):
            modelo.train()
            pred  = modelo(X_tr)
            loss  = loss_fn(pred, y_tr)
            optimizer.zero_grad(); loss.backward(); optimizer.step()
            modelo.eval()
            with torch.no_grad():
                val_loss = loss_fn(modelo(X_val), y_val).item()
            if val_loss < mejor_val:
                mejor_val    = val_loss
                mejor_estado = {k: v.clone() for k, v in modelo.state_dict().items()}

        if mejor_estado:
            modelo.load_state_dict(mejor_estado)
        self.modelo    = modelo
        self.entrenado = True
        self.score     = {'val_loss': round(mejor_val, 4), 'n_seq': len(X), 'modo': 'fine_tune'}
        print(f'  [GRU] Fine-tune completado: val_loss={mejor_val:.4f} ({len(X)} seq)')
        return self.score

    def _build_model(self, n_feat: int):
        """Construye la arquitectura GRU+Atencion. Separada para reusar en cargar/fine-tune."""
        import torch.nn as nn
        import torch

        class AttentionLayer(nn.Module):
            def __init__(self, hidden_dim):
                super().__init__()
                self.attn = nn.Linear(hidden_dim, 1)
            def forward(self, gru_out):
                scores  = self.attn(gru_out).squeeze(-1)
                weights = torch.softmax(scores, dim=1)
                context = (gru_out * weights.unsqueeze(-1)).sum(dim=1)
                return context, weights

        class GRUAttnModel(nn.Module):
            def __init__(self, n_feat):
                super().__init__()
                self.gru1  = nn.GRU(n_feat, 64, batch_first=True, bidirectional=True)
                self.attn  = AttentionLayer(128)
                self.gru2  = nn.GRU(128, 32, batch_first=True)
                self.drop1 = nn.Dropout(0.3)
                self.fc1   = nn.Linear(32, 64)
                self.drop2 = nn.Dropout(0.2)
                self.fc2   = nn.Linear(64, 32)
                self.out   = nn.Linear(32, 4)
                self.relu  = nn.ReLU()
            def forward(self, x):
                out, _ = self.gru1(x)
                ctx, _ = self.attn(out)
                ctx    = ctx.unsqueeze(1)
                out, _ = self.gru2(ctx)
                out    = out.squeeze(1)
                out    = self.drop1(out)
                out    = self.relu(self.fc1(out))
                out    = self.drop2(out)
                out    = self.relu(self.fc2(out))
                return self.out(out)
            def get_attention_weights(self, x):
                out, _ = self.gru1(x)
                _, weights = self.attn(out)
                return weights

        return GRUAttnModel(n_feat)

    def cargar(self, ruta: str) -> bool:
        try:
            import torch, joblib, os
            import torch.nn as nn
            if not os.path.exists(f'{ruta}/gru_model.pth'):
                return False
            meta = joblib.load(f'{ruta}/gru_meta.pkl')
            self.features_ok  = meta['features_ok']
            self.score        = meta['score']
            self.ctl_baseline = meta.get('ctl_baseline', 30.0)
            self.scaler_X     = joblib.load(f'{ruta}/gru_scaler_X.pkl')
            self.scaler_y     = joblib.load(f'{ruta}/gru_scaler_y.pkl')

            # Reconstruir arquitectura
            n_feat = len(self.features_ok)

            class AttentionLayer(nn.Module):
                def __init__(self, hidden_dim):
                    super().__init__()
                    self.attn = nn.Linear(hidden_dim, 1)
                def forward(self, gru_out):
                    scores  = self.attn(gru_out).squeeze(-1)
                    weights = torch.softmax(scores, dim=1)
                    context = (gru_out * weights.unsqueeze(-1)).sum(dim=1)
                    return context, weights

            class GRUAttnModel(nn.Module):
                def __init__(self, n_feat):
                    super().__init__()
                    self.gru1  = nn.GRU(n_feat, 64, batch_first=True, bidirectional=True)
                    self.attn  = AttentionLayer(128)
                    self.gru2  = nn.GRU(128, 32, batch_first=True)
                    self.drop1 = nn.Dropout(0.3)
                    self.fc1   = nn.Linear(32, 64)
                    self.drop2 = nn.Dropout(0.2)
                    self.fc2   = nn.Linear(64, 32)
                    self.out   = nn.Linear(32, 4)
                    self.relu  = nn.ReLU()
                def forward(self, x):
                    out, _ = self.gru1(x)
                    ctx, _ = self.attn(out)
                    ctx    = ctx.unsqueeze(1)
                    out, _ = self.gru2(ctx)
                    out    = out.squeeze(1)
                    out    = self.drop1(out)
                    out    = self.relu(self.fc1(out))
                    out    = self.drop2(out)
                    out    = self.relu(self.fc2(out))
                    return self.out(out)
                def get_attention_weights(self, x):
                    out, _ = self.gru1(x)
                    _, weights = self.attn(out)
                    return weights

            m = GRUAttnModel(n_feat)
            m.load_state_dict(torch.load(f'{ruta}/gru_model.pth', map_location='cpu'))
            m.eval()
            self.modelo   = m
            self.entrenado = True
            print(f'  [GRU] Modelo cargado (val_loss={self.score.get("val_loss","?")})')
            return True
        except Exception as e:
            print(f'  [GRU] Error cargando: {e}')
            return False



# ── Foundation Model — pre-entrenamiento multi-atleta ─────────────────────────
class NOAHFoundationModel:
    """
    Foundation Model de NOAH — aprende patrones fisiologicos universales
    del deporte de resistencia entrenando en TODOS los atletas.

    Arquitectura de 3 fases:
      Fase 1: Cada atleta entrena su GRU independiente
      Fase 2: Foundation pre-entrena en todos los atletas combinados
      Fase 3: Fine-tune rapido (30 epocas) por atleta individual

    Ventajas vs modelo individual:
      - Atleta nuevo converge en 2 semanas en vez de 6 meses
      - Captura patrones universales (respuesta carga, recuperacion)
      - Cada atleta nuevo MEJORA el modelo base para todos
      - Robusto a datos faltantes (aprende a interpolar)

    Analogia: GPT aprende lenguaje general, fine-tune aprende dominio especifico.
    Aqui: Foundation aprende fisiologia general, fine-tune aprende al atleta.
    """

    MODEL_DIR = 'noah_modelos/foundation'
    FEATURES   = PredictorLSTM.FEATURES
    SEQ_LEN    = PredictorLSTM.SEQ_LEN

    def __init__(self):
        self.modelo      = None
        self.entrenado   = False
        self.score       = {}
        self.scaler_X    = None
        self.scaler_y    = None
        self.features_ok = []
        self.n_atletas   = 0
        self.n_seq_total = 0

    @classmethod
    def construir_dataset_multiatleta(cls, conn, atleta_ids: list) -> pd.DataFrame:
        """
        Combina datos de multiples atletas agregando un ID de atleta
        como feature categorico codificado.
        """
        dfs = []
        for aid in atleta_ids:
            try:
                df_a = construir_dataset(conn, aid)
                if df_a.empty or len(df_a) < cls.SEQ_LEN + 30:
                    continue
                df_a['atleta_id_enc'] = aid  # identificador del atleta
                # Normalizar CTL/ATL relativo al baseline del atleta
                # (permite comparar atletas con distintos niveles de fitness)
                ctl_med = df_a['ctl'].dropna().median()
                if ctl_med and ctl_med > 0:
                    df_a['ctl_rel'] = df_a['ctl'] / ctl_med
                    df_a['atl_rel'] = df_a['atl'] / ctl_med
                else:
                    df_a['ctl_rel'] = df_a['ctl']
                    df_a['atl_rel'] = df_a['atl']
                dfs.append(df_a)
                print(f'    [Foundation] Atleta {aid}: {len(df_a)} dias')
            except Exception as e:
                print(f'    [Foundation] Error atleta {aid}: {e}')
        if not dfs:
            return pd.DataFrame()
        return pd.concat(dfs, ignore_index=True)

    def pretrain(self, conn, atleta_ids: list, epochs: int = 100) -> dict:
        """
        Pre-entrena el Foundation Model en todos los atletas.
        Guarda el encoder para fine-tuning posterior.
        """
        if not PredictorLSTM().__class__._verificar_pytorch(PredictorLSTM()):
            return {}
        import torch, torch.nn as nn, joblib, os
        from sklearn.preprocessing import StandardScaler

        print(f'\n  [Foundation] Pre-entrenando en {len(atleta_ids)} atletas...')
        df_all = self.construir_dataset_multiatleta(conn, atleta_ids)
        if df_all.empty:
            print('  [Foundation] Sin datos suficientes')
            return {}

        # Construir secuencias de todos los atletas
        all_X, all_y = [], []
        for aid in atleta_ids:
            df_a = df_all[df_all['atleta_id_enc'] == aid].copy()
            tmp = PredictorLSTM()
            X, y = tmp._construir_secuencias(df_a)
            if X is not None and len(X) >= 20:
                all_X.append(X)
                all_y.append(y)

        if not all_X:
            return {}

        X_all = np.concatenate(all_X, axis=0).astype(np.float32)
        y_all = np.concatenate(all_y, axis=0).astype(np.float32)
        self.features_ok = tmp.features_ok
        self.n_atletas   = len(atleta_ids)
        self.n_seq_total = len(X_all)

        print(f'  [Foundation] Total: {len(X_all)} secuencias | {X_all.shape[2]} features')

        # Normalizar
        n_seq, seq_len, n_feat = X_all.shape
        self.scaler_X = StandardScaler()
        X_2d_norm = self.scaler_X.fit_transform(X_all.reshape(-1, n_feat))
        X_norm    = X_2d_norm.reshape(n_seq, seq_len, n_feat)
        self.scaler_y = StandardScaler()
        y_cont    = self.scaler_y.fit_transform(y_all[:, :2])
        y_norm    = np.concatenate([y_cont, y_all[:, 2:]], axis=1)

        # Shuffle y split 85/15
        idx   = np.random.permutation(len(X_norm))
        split = int(len(idx) * 0.85)
        X_tr  = torch.tensor(X_norm[idx[:split]], dtype=torch.float32)
        y_tr  = torch.tensor(y_norm[idx[:split]], dtype=torch.float32)
        X_val = torch.tensor(X_norm[idx[split:]], dtype=torch.float32)
        y_val = torch.tensor(y_norm[idx[split:]], dtype=torch.float32)

        modelo = PredictorLSTM()._build_model(n_feat)
        opt    = torch.optim.AdamW(modelo.parameters(), lr=1e-3, weight_decay=1e-4)
        sched  = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)
        mse    = nn.MSELoss()
        bce    = nn.BCEWithLogitsLoss()

        def loss_fn(pred, target):
            return mse(pred[:, :2], target[:, :2]) * 0.6 + bce(pred[:, 2:], target[:, 2:].clamp(0,1)) * 0.4

        mejor_val, mejor_estado = float('inf'), None
        paciencia, sin_mejora   = 20, 0
        BATCH = 64

        print(f'  [Foundation] Entrenando {epochs} epocas (batch={BATCH})...')
        for ep in range(epochs):
            modelo.train()
            # Mini-batch training
            perm  = torch.randperm(len(X_tr))
            for i in range(0, len(X_tr), BATCH):
                idx_b = perm[i:i+BATCH]
                pred  = modelo(X_tr[idx_b])
                loss  = loss_fn(pred, y_tr[idx_b])
                opt.zero_grad(); loss.backward(); opt.step()

            modelo.eval()
            with torch.no_grad():
                val_loss = loss_fn(modelo(X_val), y_val).item()

            sched.step()
            if val_loss < mejor_val:
                mejor_val    = val_loss
                sin_mejora   = 0
                mejor_estado = {k: v.clone() for k, v in modelo.state_dict().items()}
            else:
                sin_mejora += 1
                if sin_mejora >= paciencia:
                    print(f'  [Foundation] Early stopping ep {ep+1} (val={mejor_val:.4f})')
                    break

            if (ep + 1) % 25 == 0:
                print(f'  [Foundation] Ep {ep+1:3d} | val_loss={val_loss:.4f} | best={mejor_val:.4f}')

        if mejor_estado:
            modelo.load_state_dict(mejor_estado)

        self.modelo    = modelo
        self.entrenado = True
        self.score     = {'val_loss': round(mejor_val, 4), 'n_atletas': self.n_atletas, 'n_seq': self.n_seq_total}

        # Guardar
        os.makedirs(self.MODEL_DIR, exist_ok=True)
        torch.save(modelo.state_dict(), f'{self.MODEL_DIR}/foundation_encoder.pth')
        joblib.dump(self.scaler_X, f'{self.MODEL_DIR}/foundation_scaler_X.pkl')
        joblib.dump(self.scaler_y, f'{self.MODEL_DIR}/foundation_scaler_y.pkl')
        joblib.dump({
            'features_ok':  self.features_ok,
            'score':        self.score,
            'ctl_baseline': 30.0,
        }, f'{self.MODEL_DIR}/foundation_meta.pkl')
        import json
        with open(f'{self.MODEL_DIR}/metadata.json', 'w') as f:
            json.dump({
                'fecha':     str(date.today()),
                'n_atletas': self.n_atletas,
                'n_seq':     self.n_seq_total,
                'val_loss':  mejor_val,
            }, f)
        print(f'  [Foundation] Guardado en {self.MODEL_DIR}/ (val_loss={mejor_val:.4f})')
        return self.score

    @classmethod
    def disponible(cls) -> bool:
        import os
        return os.path.exists(f'{cls.MODEL_DIR}/foundation_encoder.pth')

    @classmethod
    def info(cls) -> dict:
        import os, json
        meta_path = f'{cls.MODEL_DIR}/metadata.json'
        if not os.path.exists(meta_path):
            return {'disponible': False}
        with open(meta_path) as f:
            meta = json.load(f)
        meta['disponible'] = True
        return meta


class NOAHMind:
    """
    Punto de entrada principal del sistema de ML de NOAH.
    Entrena y gestiona todos los modelos del atleta.
    """

    def __init__(self, conn, atleta_id: int):
        self.conn      = conn
        self.atleta_id = atleta_id
        self.df        = None
        # Modelos ML
        self.modelo_carga           = PredictorRespuestaCarga()
        self.detector_adaptacion    = DetectorAdaptacion()
        self.predictor_respuesta    = PredictorRespuestaFisiologica()
        self.detector_sobre         = DetectorSobreentrenamiento()
        self.modelo_impacto         = ModeloImpactoRespuesta()   # legacy
        # Analizador de adherencia (sin ML — métricas analíticas)
        self.analizador_adherencia  = AnalizadorAdherencia()
        self.predictor_lstm         = PredictorLSTM()   # GRU + Atención temporal
        self._modelos_guardados     = {}

    def preparar_datos(self) -> pd.DataFrame:
        print(f'  [ML] Preparando datos para atleta {self.atleta_id}...')
        self.df = construir_dataset(self.conn, self.atleta_id)
        print(f'  [ML] Dataset: {len(self.df)} días')
        return self.df

    def entrenar(self) -> dict:
        """Entrena todos los modelos disponibles."""
        if self.df is None:
            self.preparar_datos()

        resultados = {}
        print(f'\n  [NOAH ML] Entrenando modelos para atleta {self.atleta_id}...')

        # Modelo 1: Respuesta a la carga (HRV próximo día)
        score1 = self.modelo_carga.entrenar(self.df)
        resultados['respuesta_carga'] = {'score_r2': score1, 'ok': score1 > 0.2}

        # Modelo central: Predictor de Respuesta Fisiológica (Banister + ML)
        # Predice delta_CTL, delta_TSB, absorcion_ok, riesgo_sobrecarga
        scores_rf = self.predictor_respuesta.entrenar(self.df)
        resultados['predictor_respuesta'] = {'targets': scores_rf, 'ok': len(scores_rf) > 0}
        if scores_rf:
            print(f'  [RespFisio] {len(scores_rf)} modelos entrenados')

        # Adherencia: análisis analítico (no ML)
        adherencia = self.analizador_adherencia.analizar(self.conn, self.atleta_id)
        resultados['adherencia'] = adherencia
        if adherencia.get('disponible'):
            print(f'  [Adherencia] {adherencia["adherencia_tss_pct"]}% TSS realizado | Tendencia: {adherencia["tendencia"]}')

        # Modelo GRU + Atencion temporal (requiere PyTorch)
        try:
            import torch
            scores_gru = self.predictor_lstm.entrenar(self.df)
            if scores_gru:
                resultados['gru_attention'] = scores_gru
                print(f'  [GRU] val_loss={scores_gru.get("val_loss","?")} | {scores_gru.get("n_seq","?")} secuencias')
        except ImportError:
            print('  [GRU] PyTorch no disponible — saltando GRU')
        except Exception as e:
            print(f'  [GRU] Error entrenando GRU: {e}')

        # Guardar metadatos y modelos
        self._guardar_metadatos(resultados)
        self.guardar_modelos()
        return resultados

    def analisis_completo(self, estado: dict) -> dict:
        """
        Análisis completo del atleta en este momento.
        Combina todos los modelos para dar una visión integral.
        """
        ctl   = estado.get('ctl', 0)
        atl   = estado.get('atl', 0)
        tsb   = estado.get('tsb', 0)
        hrv   = estado.get('hrv_ms')
        sleep = estado.get('sleep_h')
        stress = estado.get('stress')
        tss_7d = estado.get('tss_semana', 0)

        resultado = {}

        # Adaptación por deporte
        resultado['adaptacion'] = self.detector_adaptacion.analizar(
            self.conn, self.atleta_id)

        # Sobreentrenamiento
        resultado['sobreentrenamiento'] = self.detector_sobre.analizar(
            self.conn, self.atleta_id, ctl, atl, tsb)

        # Predicción de respuesta si hay HRV
        if hrv and self.modelo_carga.entrenado:
            resultado['respuesta_carga'] = self.modelo_carga.predecir(
                ctl, atl, tsb, hrv, sleep, stress, 0, tss_7d)

        # Predictor de Respuesta Fisiológica (modelo central)
        if self.predictor_respuesta.entrenado:
            tss_plan = estado.get('tss_semana', ctl * 7)
            resultado['predictor_respuesta'] = self.predictor_respuesta.predecir(estado, tss_plan=tss_plan)

        # Adherencia al entrenamiento (analítico, no ML)
        resultado['adherencia'] = self.analizador_adherencia.analizar(self.conn, self.atleta_id)

        # Escenarios para Optimizer
        if self.predictor_respuesta.entrenado:
            tss_base = round(ctl * 7)
            opciones = [round(tss_base * f) for f in [0.6, 0.8, 1.0, 1.1, 1.2]]
            resultado['escenarios_tss'] = self.predictor_respuesta.simular_escenarios(estado, opciones)

        # GRU + Atención temporal (usa secuencia de ultimos 28 dias)
        if self.predictor_lstm.entrenado and self.df is not None:
            try:
                pred_gru = self.predictor_lstm.predecir(self.df)
                resultado['gru_prediccion'] = pred_gru
                # Ensemble RF + GRU (promedio ponderado por val_loss inverso)
                if pred_gru.get('disponible') and self.predictor_respuesta.entrenado:
                    pred_rf = resultado.get('predictor_respuesta', {})
                    # Peso por calidad: mejor val_loss = más peso
                    w_gru = 1 / (self.predictor_lstm.score.get('val_loss', 0.5) + 0.01)
                    w_rf  = 1 / (1 - min(0.99, abs(
                        self.predictor_respuesta.scores.get('absorcion_ok', {}).get('f1', 0.5) - 1
                    )) + 0.01)
                    w_total = w_gru + w_rf
                    resultado['ensemble'] = {
                        'prob_absorcion': round(
                            (pred_gru.get('prob_absorcion', 0.5) * w_gru +
                             pred_rf.get('prob_absorcion', 0.5) * w_rf) / w_total, 3),
                        'prob_riesgo': round(
                            (pred_gru.get('prob_riesgo', 0.3) * w_gru +
                             pred_rf.get('prob_riesgo_sobrecarga', 0.3) * w_rf) / w_total, 3),
                        'delta_ctl': round(
                            (pred_gru.get('delta_ctl_predicho', 0) * w_gru +
                             pred_rf.get('delta_ctl_predicho', 0) * w_rf) / w_total, 2),
                        'pesos': {'gru': round(w_gru/w_total, 2), 'rf': round(w_rf/w_total, 2)},
                        'dias_clave': pred_gru.get('dias_clave_atencion', []),
                    }
                    # Semaforo del ensemble
                    p_r = resultado['ensemble']['prob_riesgo']
                    p_a = resultado['ensemble']['prob_absorcion']
                    d_c = resultado['ensemble']['delta_ctl']
                    if p_r >= 0.60 or p_a < 0.35:
                        resultado['ensemble']['semaforo'] = 'rojo'
                        resultado['ensemble']['interpretacion'] = f'Ensemble detecta alto riesgo ({p_r:.0%}) — reducir carga'
                    elif p_a >= 0.68 and d_c >= 0:
                        resultado['ensemble']['semaforo'] = 'verde'
                        resultado['ensemble']['interpretacion'] = f'Ensemble predice buena absorcion ({p_a:.0%}) y CTL+{d_c:.1f}'
                    else:
                        resultado['ensemble']['semaforo'] = 'amarillo'
                        resultado['ensemble']['interpretacion'] = f'Absorcion moderada ({p_a:.0%}) — monitorear esta semana'
            except Exception as e:
                print(f'  [GRU] Error en prediccion GRU: {e}')

        # Foundation Model status
        resultado['foundation_disponible'] = NOAHFoundationModel.disponible()
        resultado['foundation_info']       = NOAHFoundationModel.info()

        return resultado

    def fine_tune_gru(self) -> dict:
        """
        Fine-tune del GRU desde el Foundation Model si esta disponible.
        Si no, entrena desde cero. Llamar despues de preparar_datos().
        """
        if self.df is None:
            self.preparar_datos()
        if NOAHFoundationModel.disponible():
            print(f'  [GRU] Foundation disponible — fine-tuning para atleta {self.atleta_id}')
            return self.predictor_lstm.fine_tune_from(
                NOAHFoundationModel.MODEL_DIR, self.df)
        else:
            print(f'  [GRU] Sin Foundation — entrenando GRU desde cero')
            return self.predictor_lstm.entrenar(self.df)

    def tss_recomendado(self, estado: dict) -> dict:
        """
        Recomienda el TSS semanal basado en el estado actual y el historial.
        Combina el modelo clásico con las predicciones de ML.
        """
        ctl   = estado.get('ctl', 0)
        tsb   = estado.get('tsb', 0)
        hrv   = estado.get('hrv_ms')

        # Base: CTL × 7 (mantenimiento)
        tss_base = round(ctl * 7)

        # Ajuste por TSB
        if tsb > 10:
            factor_tsb = 1.07  # fresco → puede cargar más
        elif tsb > 0:
            factor_tsb = 1.03
        elif tsb > -15:
            factor_tsb = 1.00
        elif tsb > -25:
            factor_tsb = 0.90  # fatigado → reducir
        else:
            factor_tsb = 0.75  # muy fatigado → reducir mucho

        # Ajuste por HRV
        factor_hrv = 1.0
        if hrv:
            hrv_baseline = self.modelo_carga.hrv_baseline or 60
            ratio = hrv / hrv_baseline
            if ratio >= 1.05:
                factor_hrv = 1.05
            elif ratio < 0.92:
                factor_hrv = 0.90

        # Ajuste por sobreentrenamiento
        sobre = self.detector_sobre.analizar(self.conn, self.atleta_id, ctl, ctl*1.1, tsb)
        factor_sobre = 1.0
        if sobre['nivel'] == 'alto':
            factor_sobre = 0.60
        elif sobre['nivel'] == 'moderado':
            factor_sobre = 0.85

        tss_recomendado = round(tss_base * factor_tsb * factor_hrv * factor_sobre)

        return {
            'tss_recomendado': tss_recomendado,
            'tss_base':        tss_base,
            'factor_tsb':      factor_tsb,
            'factor_hrv':      factor_hrv,
            'factor_sobre':    factor_sobre,
            'explicacion':     f'CTL×7={tss_base} × TSB({factor_tsb}) × HRV({factor_hrv}) × Sobre({factor_sobre})',
        }

    def guardar_modelos(self, directorio: str = 'noah_modelos'):
        """Guarda los modelos entrenados en disco."""
        import joblib, os
        os.makedirs(directorio, exist_ok=True)
        ruta = f'{directorio}/atleta_{self.atleta_id}'
        os.makedirs(ruta, exist_ok=True)
        if self.modelo_carga.entrenado:
            joblib.dump(self.modelo_carga, f'{ruta}/modelo_carga.pkl')
        if self.predictor_respuesta.entrenado:
            joblib.dump(self.predictor_respuesta, f'{ruta}/predictor_respuesta.pkl')
        if self.modelo_impacto.entrenado:
            joblib.dump(self.modelo_impacto, f'{ruta}/modelo_impacto.pkl')
        ruta_gru = f'{directorio}/atleta_{self.atleta_id}'
        self.predictor_lstm.guardar(ruta_gru)
        meta = {
            'fecha':      str(date.today()),
            'atleta_id':  self.atleta_id,
            'modelos':    {
                'respuesta_carga':       self.modelo_carga.entrenado,
                'predictor_respuesta':   self.predictor_respuesta.entrenado,
                'scores_predictor':      self.predictor_respuesta.scores,
            }
        }
        with open(f'{ruta}/metadata.json', 'w') as f:
            json.dump(meta, f, default=str)
        print(f'  [NOAH ML] Modelos guardados en {ruta}/')

    @classmethod
    def cargar_modelos(cls, conn, atleta_id: int,
                       directorio: str = 'noah_modelos') -> 'NOAHMind':
        """Carga modelos desde disco si existen y son recientes (< 7 días)."""
        import joblib, os, json
        ruta = f'{directorio}/atleta_{atleta_id}'
        meta_path = f'{ruta}/metadata.json'

        if not os.path.exists(meta_path):
            return None

        with open(meta_path) as f:
            meta = json.load(f)

        # Verificar que el modelo no sea muy viejo
        from datetime import datetime
        fecha_mod = datetime.strptime(meta['fecha'], '%Y-%m-%d').date()
        dias = (date.today() - fecha_mod).days
        if dias > 7:
            return None  # Re-entrenar si tiene más de 7 días

        mind = cls(conn, atleta_id)
        try:
            if os.path.exists(f'{ruta}/modelo_carga.pkl'):
                mind.modelo_carga = joblib.load(f'{ruta}/modelo_carga.pkl')
            if os.path.exists(f'{ruta}/predictor_respuesta.pkl'):
                mind.predictor_respuesta = joblib.load(f'{ruta}/predictor_respuesta.pkl')
            if os.path.exists(f'{ruta}/modelo_impacto.pkl'):
                mind.modelo_impacto = joblib.load(f'{ruta}/modelo_impacto.pkl')
            ruta_gru = f'{ruta}'
            mind.predictor_lstm.cargar(ruta_gru)
            print(f'  [NOAH ML] Modelos cargados (entrenados hace {dias} días)')
            return mind
        except Exception as e:
            print(f'  [NOAH ML] Error cargando modelos: {e}')
            return None

    def _guardar_metadatos(self, resultados: dict):
        """Guarda metadatos del entrenamiento en la DB."""
        try:
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS ml_modelos (
                    id          SERIAL PRIMARY KEY,
                    atleta_id   INTEGER,
                    fecha       TEXT,
                    modelo      TEXT,
                    score       REAL,
                    params_json TEXT
                )
            ''')
            for modelo, datos in resultados.items():
                self.conn.execute('''
                    INSERT INTO ml_modelos (atleta_id, fecha, modelo, score, params_json)
                    VALUES (%s,%s,%s,%s,%s)
                ''', (self.atleta_id, str(date.today()), modelo,
                      datos.get('score_r2') or datos.get('score_acc', 0),
                      json.dumps(datos)))
            self.conn.commit()
        except Exception as e:
            print(f'  [ML] Error guardando metadatos: {e}')


# ── Script standalone ─────────────────────────────────────────────────────────
if __name__ == '__main__':
    import argparse, sys, os
    import psycopg2.extras
    from db_compat import ConexionCompat
    sys.path.insert(0, str(Path(__file__).parent))

    ap = argparse.ArgumentParser(description='NOAH ML — Entrenar modelos del atleta')
    ap.add_argument('--atleta', type=int, default=1)
    args = ap.parse_args()

    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("Falta la variable de entorno DATABASE_URL (cadena de conexión a Postgres/Supabase)")
        sys.exit(1)
    conn = ConexionCompat(psycopg2.connect(db_url, cursor_factory=psycopg2.extras.DictCursor))

    mind = NOAHMind(conn, args.atleta)
    mind.preparar_datos()
    resultados = mind.entrenar()

    print('\n  Importancia de features (Modelo 1):')
    for f, imp in sorted(mind.modelo_carga.importancia_features().items(),
                         key=lambda x: -x[1]):
        bar = '█' * int(imp * 50)
        print(f'    {f:20} {bar} {imp:.3f}')

    print('\n  Adaptación por deporte:')
    adaptacion = mind.detector_adaptacion.analizar(conn, args.atleta)
    for deporte, datos in adaptacion.items():
        t = datos.get('tendencia', 'sin_datos')
        pct = datos.get('mejora_pct', 0)
        icon = '📈' if t == 'mejorando' else '📉' if t == 'empeorando' else '➡'
        print(f'    {deporte:12} {icon} {t:12} {pct:+.1f}%')

    # Estado actual para TSS recomendado
    from noa_db import NOADatabase
    db = NOADatabase(db_url)
    estado_actual = db.get_estado_actual(args.atleta)
    tss_rec = mind.tss_recomendado(estado_actual)
    print(f'\n  TSS semanal recomendado por ML: {tss_rec["tss_recomendado"]}')
    print(f'  Explicación: {tss_rec["explicacion"]}')

    conn.close()
