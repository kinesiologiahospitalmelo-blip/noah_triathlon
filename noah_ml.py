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
    df_ses = pd.read_sql('''
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
    df_bio = pd.read_sql('''
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
        df = pd.read_sql('''
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
        df = pd.read_sql('''
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
            df_laps = pd.read_sql('''
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
        df = pd.read_sql('''
            SELECT fecha, pace FROM sesiones
            WHERE atleta_id=%s AND sport IN ('swimming','swim')
            AND pace > 0 ORDER BY fecha DESC LIMIT 30
        ''', conn, params=[atleta_id])

        if df.empty:
            return {'tendencia': 'sin_datos'}

        tendencia = self._tendencia(df['pace'].tolist())
        tendencia['metrica'] = 'pace_sesion_min_100m'
        return tendencia


# ── Modelo 3: Predictor de cumplimiento ───────────────────────────────────────
class PredictorCumplimiento:
    """
    Predice si el atleta va a completar la sesión prescripta.
    Aprende de su historial: ¿cuándo falla y cuándo cumple?
    """
    def __init__(self):
        self.modelo    = None
        self.entrenado = False
        self.score     = None
        self.tasa_base = 0.75  # tasa de cumplimiento por defecto

    def entrenar(self, conn, atleta_id: int) -> float:
        try:
            from sklearn.ensemble import GradientBoostingClassifier
            from sklearn.model_selection import cross_val_score
        except ImportError:
            return 0.0

        # Buscar prescripciones vs realizado — strftime("%w", ...) (SQLite)
        # reemplazado por EXTRACT(DOW FROM ...::date) (Postgres), mismo
        # rango 0=domingo..6=sábado. date(texto) (SQLite) reemplazado por
        # el cast ::date nativo de Postgres.
        df = pd.read_sql('''
            SELECT p.fecha_generada, p.tss_semana_total,
                   s.ctl, s.atl, s.tsb, s.tss_total as tss_real,
                   sh.hrv_rmssd, sh.sleep_h, sh.stress_avg,
                   EXTRACT(DOW FROM p.fecha_generada::date) as dia_semana
            FROM prescripciones p
            LEFT JOIN sesiones s ON s.atleta_id=p.atleta_id
                AND s.fecha=p.fecha_generada::date
            LEFT JOIN sleep_hrv sh ON sh.atleta_id=p.atleta_id
                AND sh.fecha=p.fecha_generada::date
            WHERE p.atleta_id=%s
            ORDER BY p.fecha_generada DESC LIMIT 200
        ''', conn, params=[atleta_id])

        if len(df) < 20:
            return 0.0

        df['completada'] = (df['tss_real'] > df['tss_semana_total'] * 0.7).astype(int)
        self.tasa_base = float(df['completada'].mean())

        features = ['ctl', 'atl', 'tsb', 'hrv_rmssd', 'sleep_h', 'dia_semana']
        df_clean = df[features + ['completada']].dropna()

        if len(df_clean) < 15:
            return 0.0

        X = df_clean[features].values.astype(float)
        y = df_clean['completada'].values

        self.modelo = GradientBoostingClassifier(n_estimators=50, max_depth=3, random_state=42)
        self.modelo.fit(X, y)
        scores = cross_val_score(self.modelo, X, y, cv=3, scoring='accuracy')
        self.score = float(scores.mean())
        self.entrenado = True
        return self.score

    def predecir(self, ctl, atl, tsb, hrv, sleep_h, dia_semana=1) -> dict:
        if not self.entrenado:
            return {'prob_cumplimiento': self.tasa_base,
                    'interpretacion': 'Sin modelo entrenado — usando promedio histórico'}

        X = np.array([[
            _safe_float(ctl, 30), _safe_float(atl, 30), _safe_float(tsb, 0),
            _safe_float(hrv, 60), _safe_float(sleep_h, 7), int(dia_semana)
        ]])
        prob = float(self.modelo.predict_proba(X)[0][1])

        if prob >= 0.75:
            interp = 'Alta probabilidad de cumplimiento'
        elif prob >= 0.5:
            interp = 'Cumplimiento probable — monitorear'
        else:
            interp = 'Riesgo de no cumplir — considerar reducir carga'

        return {'prob_cumplimiento': round(prob, 3), 'interpretacion': interp}


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
        df_hrv = pd.read_sql('''
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
        df_tss = pd.read_sql('''
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


# ── NOAH Mind — Interfaz principal ───────────────────────────────────────────


# ── Modelo de Impacto-Respuesta Individual ────────────────────────────────────
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


class NOAHMind:
    """
    Punto de entrada principal del sistema de ML de NOAH.
    Entrena y gestiona todos los modelos del atleta.
    """

    def __init__(self, conn, atleta_id: int):
        self.conn      = conn
        self.atleta_id = atleta_id
        self.df        = None
        self.modelo_carga        = PredictorRespuestaCarga()
        self.detector_adaptacion = DetectorAdaptacion()
        self.modelo_cumplimiento = PredictorCumplimiento()
        self.detector_sobre      = DetectorSobreentrenamiento()
        self.modelo_impacto      = ModeloImpactoRespuesta()
        self._modelos_guardados  = {}

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

        # Modelo 1: Respuesta a la carga
        score1 = self.modelo_carga.entrenar(self.df)
        resultados['respuesta_carga'] = {'score_r2': score1, 'ok': score1 > 0.2}

        # Modelo 3: Cumplimiento
        score3 = self.modelo_cumplimiento.entrenar(self.conn, self.atleta_id)
        resultados['cumplimiento'] = {'score_acc': score3, 'ok': score3 > 0.55}

        # Modelo 4: Impacto-Respuesta individual
        scores4 = self.modelo_impacto.entrenar(self.df)
        resultados['impacto_respuesta'] = {
            'targets': scores4,
            'ok': len(scores4) > 0,
            'n_targets': len(scores4),
        }
        if scores4:
            print(f'  [ML] Impacto-Respuesta: {len(scores4)} targets entrenados')
            for t, s in scores4.items():
                print(f'    {t}: F1={s.get("f1","--")} ({s.get("n","?")} días, {s.get("pct_pos","?")}% positivos)')

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

        # Cumplimiento
        if self.modelo_cumplimiento.entrenado:
            resultado['cumplimiento'] = self.modelo_cumplimiento.predecir(
                ctl, atl, tsb, hrv, sleep)

        # Impacto-Respuesta: predecir recuperación para el TSS de hoy
        if self.modelo_impacto.entrenado:
            tss_hoy = estado.get('tss_semana', ctl * 1.0) / 7
            resultado['impacto_respuesta'] = self.modelo_impacto.predecir_respuesta(
                estado, tss_planificado=tss_hoy)

        return resultado

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
        if self.modelo_cumplimiento.entrenado:
            joblib.dump(self.modelo_cumplimiento, f'{ruta}/modelo_cumplimiento.pkl')
        # Guardar fecha de entrenamiento
        with open(f'{ruta}/metadata.json', 'w') as f:
            import json
            json.dump({'fecha': str(date.today()), 'atleta_id': self.atleta_id}, f)
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
            mind.modelo_carga = joblib.load(f'{ruta}/modelo_carga.pkl')
            mind.modelo_cumplimiento = joblib.load(f'{ruta}/modelo_cumplimiento.pkl')
            print(f'  [NOAH ML] Modelos cargados (entrenados hace {dias} días)')
            return mind
        except Exception:
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
