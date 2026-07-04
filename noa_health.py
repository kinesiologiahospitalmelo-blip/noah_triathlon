"""
noa_health.py
-------------
Modulo de salud y prediccion de riesgo autonomico para NOA.

Basado en:
- Quer et al. 2021 (Nature Medicine/Scripps) — prediccion infeccion viral
- Thayer et al. 2010/2012 — HRV e inflamacion cronica
- Meeusen et al. 2013 — sobreentrenamiento (ECSS consensus)
- Altini & Kinnunen 2021 — HRV4Training methodology
- Hallman et al. 2011 — carga aloestatica y dolor

DIFERENCIAS CLAVE deportista vs clinico:
  - Umbral caida HRV: >=15% (vs >=8% clinico)
  - Dias consecutivos bajo: >=4 (vs >=3 clinico)
  - Subida FC preocupante: >=10% (vs >=8% clinico)
  - Baseline: semana de descarga reciente (no promedio global)

USO:
  from noa_health import NOAHealth
  health = NOAHealth(atleta_id=1, db_path='noa.db')
  score = health.calcular_noa_score()
  print(score)
"""

import psycopg2
import numpy as np
from datetime import date, timedelta
from pathlib import Path
from typing import Optional
from db_compat import ConexionCompat


# ─── REFERENCIAS POR EDAD (RMSSD nocturno) ────────────────────────────────────

RMSSD_REFERENCIA_EDAD = {
    (20, 30): (50, 90),
    (30, 40): (40, 75),
    (40, 50): (30, 62),
    (50, 99): (22, 50),
}

# Factor de ajuste para deportistas de resistencia
# Sistemáticamente 20-35% más alto que sedentarios
FACTOR_DEPORTISTA = 1.25


# ─── CLASE PRINCIPAL ──────────────────────────────────────────────────────────

class NOAHealth:

    def __init__(self, atleta_id: int, db_path: str,
                 edad: int = 40, es_deportista: bool = True):
        self.atleta_id    = atleta_id
        self.db_path      = db_path
        self.edad         = edad
        self.es_deportista = es_deportista
        self._conn        = None

    def conn(self):
        if not self._conn:
            self._conn = ConexionCompat(psycopg2.connect(self.db_path))
        return self._conn

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    # ── DATOS HISTÓRICOS ──────────────────────────────────────────────────────

    def get_series(self, dias: int = 14) -> dict:
        """
        Retorna series temporales de los últimos N días.
        Incluye HRV, FC reposo, sueño REM, Body Battery.
        """
        desde = str(date.today() - timedelta(days=dias))
        rows  = self.conn().execute('''
            SELECT fecha, hrv_rmssd, hrv_ratio, hrv_flag,
                   sleep_h, rem_h, deep_h,
                   recovery_score, stress_avg, body_battery
            FROM sleep_hrv
            WHERE atleta_id=%s AND fecha >= %s
            ORDER BY fecha ASC
        ''', (self.atleta_id, desde)).fetchall()

        # FC reposo desde sesiones (mínimo diario)
        fc_rows = self.conn().execute('''
            SELECT fecha, MIN(hr_avg) as fc_reposo
            FROM sesiones
            WHERE atleta_id=%s AND fecha >= %s
            AND hr_avg IS NOT NULL AND hr_avg > 35
            GROUP BY fecha
            ORDER BY fecha ASC
        ''', (self.atleta_id, desde)).fetchall()
        fc_dict = {r[0]: r[1] for r in fc_rows}

        series = {
            'fechas'  : [],
            'hrv_ms'  : [],
            'hrv_ratio': [],
            'hrv_flag': [],
            'sleep_h' : [],
            'rem_h'   : [],
            'deep_h'  : [],
            'recovery': [],
            'stress'  : [],
            'bb'      : [],
            'fc'      : [],
        }

        for r in rows:
            fecha = r[0]
            series['fechas'].append(fecha)
            series['hrv_ms'].append(r[1] or 0)
            series['hrv_ratio'].append(r[2] or 1.0)
            series['hrv_flag'].append(r[3] or 'amarillo')
            series['sleep_h'].append(r[4] or 0)
            series['rem_h'].append(r[5] or 0)
            series['deep_h'].append(r[6] or 0)
            series['recovery'].append(r[7] or 80)
            series['stress'].append(r[8] or 30)
            series['bb'].append(r[9] or 50)
            series['fc'].append(fc_dict.get(fecha, 0))

        return series

    def get_sesiones_recientes(self, dias: int = 7) -> list:
        """Retorna sesiones recientes para detectar sobreentrenamiento."""
        desde = str(date.today() - timedelta(days=dias))
        return self.conn().execute('''
            SELECT fecha, tss_total, hr_avg, duration_min, tipo_sesion
            FROM sesiones
            WHERE atleta_id=%s AND fecha >= %s
            ORDER BY fecha DESC
        ''', (self.atleta_id, desde)).fetchall()

    # ── NORMALIZACIÓN ─────────────────────────────────────────────────────────

    def rmssd_referencia(self) -> tuple:
        """Retorna el rango de referencia de RMSSD para la edad del atleta."""
        for (edad_min, edad_max), rango in RMSSD_REFERENCIA_EDAD.items():
            if edad_min <= self.edad < edad_max:
                if self.es_deportista:
                    return (int(rango[0] * FACTOR_DEPORTISTA),
                            int(rango[1] * FACTOR_DEPORTISTA))
                return rango
        return (22, 50)

    def normalizar_hrv(self, hrv_ms: float) -> str:
        """
        Clasifica el HRV absoluto respecto a la referencia por edad.
        Retorna: 'alto', 'normal', 'bajo', 'muy_bajo'
        """
        ref_min, ref_max = self.rmssd_referencia()
        if hrv_ms >= ref_max:          return 'alto'
        if hrv_ms >= ref_min:          return 'normal'
        if hrv_ms >= ref_min * 0.75:   return 'bajo'
        return 'muy_bajo'

    # ── BASELINE PERSONAL ─────────────────────────────────────────────────────

    def calcular_baseline(self, series: dict) -> dict:
        """
        Baseline personal: promedio de los días 8-14 (semana anterior).
        Para deportistas: usar semana de descarga si disponible.
        """
        hrv  = [v for v in series['hrv_ms'] if v > 0]
        fc   = [v for v in series['fc'] if v > 0]
        rem  = [v for v in series['rem_h'] if v > 0]
        bb   = [v for v in series['bb'] if v > 0]

        n = len(hrv)

        if n >= 10:
            # Usar la primera mitad como baseline (días más antiguos)
            mitad = n // 2
            hrv_base = float(np.mean(hrv[:mitad]))
            fc_base  = float(np.mean([v for v in fc[:mitad] if v > 0] or fc or [70]))
            rem_base = float(np.mean(rem[:mitad] or rem or [1.5]))
        elif n >= 5:
            hrv_base = float(np.mean(hrv[:max(1, n-3)]))
            fc_base  = float(np.mean([v for v in fc if v > 0] or [70]))
            rem_base = float(np.mean(rem or [1.5]))
        else:
            hrv_base = float(np.mean(hrv)) if hrv else 60.0
            fc_base  = float(np.mean([v for v in fc if v > 0])) if fc else 60.0
            rem_base = float(np.mean(rem)) if rem else 1.5

        return {
            'hrv_ms'  : round(hrv_base, 1),
            'fc'      : round(fc_base, 1),
            'rem_h'   : round(rem_base, 2),
            'dias_datos': n,
        }

    # ── DETECCIÓN DE ACUMULACIÓN AUTONÓMICA ───────────────────────────────────

    def detectar_acumulacion(self, series: dict) -> dict:
        """
        Detecta acumulación autonómica por tendencias de media móvil.
        MA7 < MA21 → carga sostenida.
        Alta variabilidad del score → inestabilidad autonómica.
        """
        hrv = [v for v in series['hrv_ratio'] if v > 0]
        if len(hrv) < 7:
            return {'flag': False, 'tipo': None, 'detalle': 'insuficientes datos'}

        # Media móvil 7 días (recientes) vs 21 días (si disponible)
        ma7  = float(np.mean(hrv[-7:]))
        ma21 = float(np.mean(hrv)) if len(hrv) >= 14 else ma7

        # Días consecutivos con HRV bajo
        dias_bajo = 0
        for flag in reversed(series['hrv_flag']):
            if flag == 'rojo':
                dias_bajo += 1
            else:
                break

        # Variabilidad del score (inestabilidad)
        variabilidad = float(np.std(hrv[-7:])) if len(hrv) >= 7 else 0

        flags = []
        if ma7 < ma21 * 0.93:
            flags.append('carga_sostenida')
        if dias_bajo >= 4:  # umbral deportista
            flags.append(f'{dias_bajo}_dias_consecutivos_bajo')
        if variabilidad > 0.12:
            flags.append('inestabilidad_autonomica')

        return {
            'flag'        : len(flags) > 0,
            'flags'       : flags,
            'ma7'         : round(ma7, 3),
            'ma21'        : round(ma21, 3),
            'dias_bajo'   : dias_bajo,
            'variabilidad': round(variabilidad, 3),
        }

    # ── DISTINCIÓN SOBREENTRENAMIENTO VS ENFERMEDAD ───────────────────────────

    def distinguir_sobreentrenamiento_enfermedad(self,
                                                   series: dict,
                                                   sesiones: list) -> dict:
        """
        Clave para deportistas: el HRV baja por entrenamiento (normal)
        pero debe subir en días de descanso.
        Si baja y NO sube en 48-72h de descanso → sobreentrenamiento/enfermedad.
        """
        if len(series['hrv_ratio']) < 4:
            return {'conclusion': 'insuficientes_datos'}

        hrv_reciente = series['hrv_ratio'][-3:]
        hrv_promedio = float(np.mean(hrv_reciente))

        # ¿Hubo sesiones intensas en los últimos 3 días?
        fechas_3d = set()
        hoy = date.today()
        for i in range(3):
            fechas_3d.add(str(hoy - timedelta(days=i)))

        sesiones_recientes = [s for s in sesiones if s[0] in fechas_3d]
        tss_reciente = sum(s[1] or 0 for s in sesiones_recientes)
        hubo_carga = tss_reciente > 60

        # ¿El HRV está bajo?
        hrv_bajo = hrv_promedio < 0.93  # umbral deportista

        if not hrv_bajo:
            return {'conclusion': 'normal', 'detalle': 'HRV dentro del rango esperado'}

        if hubo_carga and hrv_bajo:
            # HRV bajo con carga reciente → puede ser adaptación
            # Verificar si hay días de descanso en los últimos 4 días
            fechas_4d = set(str(hoy - timedelta(days=i)) for i in range(4))
            dias_descanso = len(fechas_4d - {s[0] for s in sesiones})

            if dias_descanso >= 1:
                return {
                    'conclusion': 'sobreentrenamiento_probable',
                    'detalle'   : f'HRV bajo después de {dias_descanso} día(s) de descanso — no se recuperó',
                    'accion'    : 'Reducir carga. Evaluar síntomas sistémicos.',
                }
            else:
                return {
                    'conclusion': 'adaptacion_posible',
                    'detalle'   : 'HRV bajo con carga reciente — observar recuperación en descanso',
                    'accion'    : 'Esperar día de descanso. Si no sube → sobreentrenamiento.',
                }
        else:
            # HRV bajo sin carga reciente → proceso sistémico
            return {
                'conclusion': 'proceso_sistemico_probable',
                'detalle'   : 'HRV bajo sin carga de entrenamiento que lo justifique',
                'accion'    : 'Posible proceso infeccioso o inflamatorio. Reducir carga.',
            }

    # ── ALGORITMO DE PREDICCIÓN DE RIESGO ─────────────────────────────────────

    def predict_health_risk(self, series: dict, baseline: dict) -> dict:
        """
        Predicción de riesgo de evento de salud en los próximos 3-5 días.
        Basado en Quer et al. 2021 y adaptado para deportistas.

        Umbrales deportistas (sección 6 del prompt):
          - Caída HRV preocupante: >=15% (vs >=8% clínico)
          - Subida FC: >=10% (vs >=8% clínico)
          - Caída REM: >=15%
        """
        if len(series['hrv_ms']) < 5:
            return {
                'risk_level'  : 'insuficiente',
                'risk_score'  : 0,
                'flags'       : [],
                'message'     : 'Se necesitan al menos 5 días de datos para predecir.',
                'confidence'  : 'ninguna',
            }

        hrv_ms    = [v for v in series['hrv_ms'] if v > 0]
        fc_series = [v for v in series['fc'] if v > 0]
        rem       = [v for v in series['rem_h'] if v > 0]
        bb        = [v for v in series['bb'] if v > 0]

        # Valores recientes (promedio últimos 3 días)
        hrv_reciente = float(np.mean(hrv_ms[-3:])) if len(hrv_ms) >= 3 else float(np.mean(hrv_ms))
        fc_reciente  = float(np.mean(fc_series[-3:])) if len(fc_series) >= 3 else float(np.mean(fc_series)) if fc_series else baseline['fc']
        rem_reciente = float(np.mean(rem[-3:])) if len(rem) >= 3 else float(np.mean(rem)) if rem else baseline['rem_h']
        bb_reciente  = float(np.mean(bb[-3:])) if len(bb) >= 3 else float(np.mean(bb)) if bb else 50

        hrv_base = baseline['hrv_ms']
        fc_base  = baseline['fc']
        rem_base = baseline['rem_h']

        flags = []
        risk_score = 0.0

        # ── FLAG HRV (peso 0.35) ──────────────────────────────────────────────
        if hrv_base > 0:
            hrv_drop = (hrv_base - hrv_reciente) / hrv_base
            umbral_hrv = 0.15 if self.es_deportista else 0.08
            if hrv_drop >= umbral_hrv:
                peso = 0.35
                risk_score += peso
                flags.append({
                    'signal'     : 'hrv_drop',
                    'valor'      : round(hrv_drop * 100, 1),
                    'umbral'     : round(umbral_hrv * 100, 1),
                    'peso'       : peso,
                    'descripcion': f'HRV bajó {hrv_drop*100:.1f}% del baseline ({hrv_base:.0f}ms → {hrv_reciente:.0f}ms)',
                })

        # ── FLAG FC (peso 0.25) ───────────────────────────────────────────────
        if fc_base > 0 and fc_reciente > 0:
            fc_rise = (fc_reciente - fc_base) / fc_base
            umbral_fc = 0.10 if self.es_deportista else 0.08
            if fc_rise >= umbral_fc:
                peso = 0.25
                risk_score += peso
                flags.append({
                    'signal'     : 'hr_rise',
                    'valor'      : round(fc_rise * 100, 1),
                    'umbral'     : round(umbral_fc * 100, 1),
                    'peso'       : peso,
                    'descripcion': f'FC reposo subió {fc_rise*100:.1f}% ({fc_base:.0f} → {fc_reciente:.0f} bpm)',
                })

        # ── FLAG REM (peso 0.20) ──────────────────────────────────────────────
        if rem_base > 0:
            rem_drop = (rem_base - rem_reciente) / rem_base
            if rem_drop >= 0.15:
                peso = 0.20
                risk_score += peso
                flags.append({
                    'signal'     : 'rem_drop',
                    'valor'      : round(rem_drop * 100, 1),
                    'umbral'     : 15,
                    'peso'       : peso,
                    'descripcion': f'Sueño REM cayó {rem_drop*100:.1f}% ({rem_base:.1f}h → {rem_reciente:.1f}h)',
                })

        # ── FLAG BODY BATTERY (peso 0.10) ─────────────────────────────────────
        if bb_reciente < 30:
            peso = 0.10
            risk_score += peso
            flags.append({
                'signal'     : 'bb_bajo',
                'valor'      : round(bb_reciente, 0),
                'umbral'     : 30,
                'peso'       : peso,
                'descripcion': f'Body Battery promedio muy bajo: {bb_reciente:.0f}',
            })

        # ── FLAG SUEÑO TOTAL (peso 0.10) ──────────────────────────────────────
        sleep_reciente = float(np.mean(series['sleep_h'][-3:])) if len(series['sleep_h']) >= 3 else 7.0
        if sleep_reciente < 5.5:
            peso = 0.10
            risk_score += peso
            flags.append({
                'signal'     : 'sleep_insuficiente',
                'valor'      : round(sleep_reciente, 1),
                'umbral'     : 5.5,
                'peso'       : peso,
                'descripcion': f'Sueño promedio insuficiente: {sleep_reciente:.1f}h',
            })

        # ── TENDENCIA HRV (regresión lineal 7 días) ───────────────────────────
        if len(hrv_ms) >= 7:
            x = np.arange(min(7, len(hrv_ms)))
            y = np.array(hrv_ms[-7:])
            slope = float(np.polyfit(x, y, 1)[0])
            if slope < -0.5:  # caída sostenida ≥ 0.5ms/día
                risk_score = min(1.0, risk_score * 1.3)
                flags.append({
                    'signal'     : 'tendencia_hrv_negativa',
                    'valor'      : round(slope, 2),
                    'descripcion': f'Tendencia HRV descendente: {slope:.2f}ms/día (amplifica riesgo 30%)',
                    'peso'       : 0,
                })
        else:
            slope = 0.0

        risk_score = min(1.0, risk_score)

        # ── NIVEL DE RIESGO ───────────────────────────────────────────────────
        if risk_score >= 0.70:
            level   = 'alto'
            color   = 'rojo'
            message = ('Múltiples señales de alerta. Posible proceso infeccioso '
                       'o sobrecarga severa en los próximos 3-5 días. '
                       'Reducir carga de entrenamiento. Evaluar síntomas.')
        elif risk_score >= 0.40:
            level   = 'moderado'
            color   = 'naranja'
            message = ('Carga autonómica elevada. Priorizar recuperación. '
                       'Monitorear evolución en las próximas 48h.')
        elif risk_score >= 0.20:
            level   = 'bajo_moderado'
            color   = 'amarillo'
            message = 'Leve tensión autonómica. Plan estándar con atención.'
        else:
            level   = 'bajo'
            color   = 'verde'
            message = 'Sin señales de alerta. Sistema autonómico estable.'

        confidence = ('alta' if baseline['dias_datos'] >= 14
                      else 'moderada' if baseline['dias_datos'] >= 7
                      else 'baja — período de calibración')

        return {
            'risk_level'    : level,
            'risk_score'    : round(risk_score, 2),
            'risk_color'    : color,
            'flags'         : flags,
            'hrv_trend_slope': round(slope, 3),
            'message'       : message,
            'confidence'    : confidence,
            'hrv_reciente'  : round(hrv_reciente, 1),
            'hrv_baseline'  : round(hrv_base, 1),
            'hrv_norm'      : self.normalizar_hrv(hrv_reciente),
            'ref_edad'      : self.rmssd_referencia(),
        }

    # ── NOA SCORE — INTEGRACIÓN COMPLETA ─────────────────────────────────────

    def calcular_noa_score(self) -> dict:
        """
        Calcula el NOA Score completo del atleta.
        Integra: riesgo de salud + acumulación autonómica +
                 distinción sobreentrenamiento/enfermedad.

        Retorna un dict completo listo para mostrar en el dashboard
        y para que ciclo_semanal.py tome decisiones de carga.
        """
        series   = self.get_series(dias=21)
        baseline = self.calcular_baseline(series)
        sesiones = self.get_sesiones_recientes(dias=7)

        riesgo       = self.predict_health_risk(series, baseline)
        acumulacion  = self.detectar_acumulacion(series)
        distincion   = self.distinguir_sobreentrenamiento_enfermedad(series, sesiones)

        # Score final combinado
        score_final = riesgo['risk_score']
        if acumulacion['flag']:
            score_final = min(1.0, score_final + 0.15)

        # Recomendación de carga para ciclo_semanal
        if score_final >= 0.70 or distincion['conclusion'] == 'proceso_sistemico_probable':
            recomendacion_carga = 'RECUPERACION'
            recomendacion_desc  = 'NOA recomienda semana de recuperación por señales de salud.'
        elif score_final >= 0.40 or distincion['conclusion'] == 'sobreentrenamiento_probable':
            recomendacion_carga = 'REDUCIR'
            recomendacion_desc  = 'NOA recomienda reducir carga 20-30% esta semana.'
        elif acumulacion['flag'] and 'inestabilidad_autonomica' in acumulacion.get('flags', []):
            recomendacion_carga = 'MANTENIMIENTO'
            recomendacion_desc  = 'Inestabilidad autonómica — mantener carga, no aumentar.'
        else:
            recomendacion_carga = 'NORMAL'
            recomendacion_desc  = 'Sin restricciones de salud. Seguir plan.'

        return {
            # Score principal
            'noa_score'          : round(score_final, 2),
            'noa_score_color'    : riesgo.get('risk_color','amarillo'),
            'noa_score_nivel'    : riesgo['risk_level'],

            # Predicción de riesgo
            'riesgo'             : riesgo,

            # Acumulación autonómica
            'acumulacion'        : acumulacion,

            # Sobreentrenamiento vs enfermedad
            'distincion'         : distincion,

            # Baseline y normalización
            'baseline'           : baseline,
            'hrv_norm_edad'      : riesgo.get('hrv_norm', 'normal'),
            'rmssd_ref_edad'     : riesgo.get('ref_edad', (30, 62)),

            # Recomendación para prescripción
            'recomendacion_carga': recomendacion_carga,
            'recomendacion_desc' : recomendacion_desc,

            # Metadata
            'dias_datos'         : baseline['dias_datos'],
            'fecha_calculo'      : str(date.today()),
            'confidence'         : riesgo['confidence'],
        }

    def mostrar_noa_score(self, score: dict = None):
        """Muestra el NOA Score en consola de forma legible."""
        if not score:
            score = self.calcular_noa_score()

        colores = {'verde': '✓', 'amarillo': '~', 'naranja': '⚠', 'rojo': '✗'}
        icono = colores.get(score['noa_score_color'], '?')

        print()
        print('=' * 62)
        print('  NOA HEALTH SCORE')
        print('=' * 62)
        print(f'  Score    : {score["noa_score"]:.2f} / 1.00  {icono} {score["noa_score_nivel"].upper()}')
        print(f'  Confianza: {score["confidence"]}  ({score["dias_datos"]} días de datos)')
        print()

        r = score['riesgo']
        print(f'  HRV reciente : {r.get("hrv_reciente", "--")} ms  '
              f'(baseline: {r.get("hrv_baseline", "--")} ms)')
        print(f'  Nivel HRV    : {r.get("hrv_norm", "--")} para edad '
              f'(ref: {r.get("ref_edad", ("--","--"))[0]}-{r.get("ref_edad", ("--","--"))[1]} ms)')
        print()

        if score['riesgo']['flags']:
            print('  SEÑALES DETECTADAS:')
            for f in score['riesgo']['flags']:
                if f.get('peso', 0) > 0:
                    print(f'    → {f["descripcion"]}')
            print()

        if score['acumulacion']['flag']:
            print('  ACUMULACIÓN AUTONÓMICA:')
            for f in score['acumulacion'].get('flags', []):
                print(f'    → {f.replace("_", " ")}')
            print()

        d = score['distincion']
        if d['conclusion'] not in ('normal', 'insuficientes_datos'):
            print(f'  DIAGNÓSTICO: {d["detalle"]}')
            if d.get('accion'):
                print(f'  ACCIÓN: {d["accion"]}')
            print()

        print(f'  MENSAJE: {score["riesgo"]["message"]}')
        print()
        print(f'  RECOMENDACIÓN CARGA: {score["recomendacion_carga"]}')
        print(f'  {score["recomendacion_desc"]}')
        print('=' * 62)

        return score


# ─── USO DIRECTO ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import sys, os
    import psycopg2

    db_path = os.environ.get('DATABASE_URL', '')
    if not db_path:
        print("Falta la variable de entorno DATABASE_URL (cadena de conexión a Postgres/Supabase)")
        sys.exit(1)

    # Obtener edad del atleta
    conn = psycopg2.connect(db_path)
    cur = conn.cursor()
    cur.execute('SELECT edad, nombre FROM atletas WHERE id=1')
    atleta = cur.fetchone()
    conn.close()

    edad   = atleta[0] or 47
    nombre = atleta[1] or 'Rodrigo'

    print(f'\nCalculando NOA Score para {nombre} (edad {edad})...')

    health = NOAHealth(
        atleta_id=1,
        db_path=db_path,
        edad=edad,
        es_deportista=True,
    )

    score = health.calcular_noa_score()
    health.mostrar_noa_score(score)
    health.close()
