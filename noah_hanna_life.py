"""
noah_hanna_life.py — Proyecto NOAH v3
=======================================
HANNA LIFE = "¿Cuánto podés cargar hoy?"

ARQUITECTURA MULTIPLICATIVA:
    HANNA LIFE = Estado_Autonómico × Modificador_Carga

    Estado_Autonómico (0-100):
        Posición del atleta en su distribución personal
        usando percentiles reales del baseline.
        Variables: HRV, FC reposo, sueño dur+cal, stress, SpO2
        Penalización exponencial por co-ocurrencia de señales bajas
        Ajuste por tendencia de 7 días (pendiente HRV)

    Modificador_Carga (0.60 - 1.10):
        Amplifica o reduce según carga acumulada
        Variables: ATL/CTL ratio, TSB, días sin entrenar
        Distingue "fresco por descanso" de "fresco por taper"

PRINCIPIOS:
    - Si el sistema autonómico está comprometido, la carga no puede rescatarlo
    - Los umbrales son PERSONALES (percentiles del baseline, no valores fijos)
    - SpO2 tiene umbral fisiológico real (< 94% es señal universal)
    - La tendencia de HRV pondera más que el valor puntual
    - Body battery NO entra — es redundante (ya integra HRV+sueño+actividad)

REFERENCIAS:
    Plews et al. 2013, Buchheit 2014, Flatt & Esco 2017,
    Banister 1991 (ATL/CTL), Foster 1998 (monotonía),
    Tedesco et al. 2023 (riesgo viral RMSSD)
"""

from __future__ import annotations
import json
import math
import numpy as np
import pandas as pd
from datetime import date, timedelta
from typing import Optional, List
from db_compat import asegurar_columnas


# ── Niveles HANNA LIFE ────────────────────────────────────────────────────────
HANNA_NIVELES = [
    (82, 100, 'Óptimo',   '#10B981', '🔋'),
    (65,  81, 'Bueno',    '#3B82F6', '🔋'),
    (48,  64, 'Moderado', '#F59E0B', '⚡'),
    (32,  47, 'Bajo',     '#F97316', '🪫'),
    (0,   31, 'Crítico',  '#EF4444', '🪫'),
]

def nivel_hanna(score: float) -> dict:
    for mn, mx, label, color, icon in HANNA_NIVELES:
        if mn <= score <= mx:
            return {'label': label, 'color': color, 'icon': icon}
    return {'label': 'Sin datos', 'color': '#6B7280', 'icon': '⚪'}


# ── Interpolación en percentiles personales ───────────────────────────────────
def _score_por_percentiles(
    val: float,
    p10: float, p25: float, p75: float, p90: float,
    direccion: int = 1,
) -> float:
    """Score 0-100 basado en posición en distribución personal del atleta."""
    if direccion == -1:
        val_inv = p10 + p90 - val
        return _score_por_percentiles(val_inv, p10, p25, p75, p90, direccion=1)

    # Proteger contra percentiles iguales (pocos datos o HRV muy constante)
    def safe_div(num, den, default=0.5):
        return num / den if den and den > 0 else default

    if val >= p90:
        rango = p90 - p10
        if rango <= 0: return 92.0
        exceso = min(val - p90, rango * 0.5)
        return min(100.0, 90.0 + safe_div(exceso, rango * 0.5) * 10.0)
    elif val >= p75:
        diff = p90 - p75
        if diff <= 0: return 80.0
        return 75.0 + safe_div(val - p75, diff) * 15.0
    elif val >= p25:
        diff = p75 - p25
        if diff <= 0: return 55.0
        return 40.0 + safe_div(val - p25, diff) * 35.0
    elif val >= p10:
        diff = p25 - p10
        if diff <= 0: return 25.0
        return 20.0 + safe_div(val - p10, diff) * 20.0
    else:
        rango = p25 - p10
        if rango <= 0: return 8.0
        caida = min(p10 - val, rango)
        return max(0.0, 20.0 - safe_div(caida, rango) * 20.0)


def _score_spo2(spo2: float) -> float:
    """
    SpO2 tiene umbral fisiológico universal + ajuste personal.
    < 94% es preocupante para cualquier atleta.
    > 97% es óptimo.
    """
    if spo2 is None:
        return 55.0  # sin dato → neutral
    if spo2 >= 98:   return 100.0
    if spo2 >= 97:   return 92.0
    if spo2 >= 96:   return 82.0
    if spo2 >= 95:   return 70.0
    if spo2 >= 94:   return 52.0
    if spo2 >= 93:   return 32.0
    if spo2 >= 92:   return 18.0
    return max(0.0, (spo2 - 85) / 7 * 18.0)


def _score_fallback_zscore(val: float, media: float, std: float,
                            direccion: int = 1) -> float:
    """Fallback cuando no hay percentiles — z-score con sigmoide."""
    if not std or std <= 0:
        return 50.0
    z = (val - media) / std * direccion
    return round(100.0 / (1.0 + math.exp(-1.2 * z)), 1)


# ── Estado Autonómico ─────────────────────────────────────────────────────────
def calcular_estado_autonomico(
    hrv_val:      Optional[float],
    fc_hoy:       Optional[float],
    stress_avg:   Optional[float],
    sleep_h:      Optional[float],
    deep_h:       Optional[float],
    rem_h:        Optional[float],
    spo2_avg:     Optional[float],
    historia_hrv: List[float],
    baseline:     Optional[dict],
    hrv_es_estimado: bool = False,
) -> dict:
    """
    Calcula el Estado Autonómico (0-100) usando percentiles personales.
    """
    tiene_baseline = (
        baseline and
        baseline.get('fase') not in ('sin_datos', None) and
        baseline.get('hrv_p10') is not None
    )

    scores = {}
    pesos_efectivos = {}

    # ── HRV (peso base 40%) ───────────────────────────────────────────────────
    if hrv_val and hrv_val > 0:
        if tiene_baseline and baseline.get('hrv_p10'):
            s = _score_por_percentiles(
                hrv_val,
                baseline['hrv_p10'], baseline['hrv_p25'],
                baseline['hrv_p75'], baseline['hrv_p90'],
                direccion=1
            )
        elif len(historia_hrv) >= 7:
            # Sin baseline completo — usar distribución de la historia disponible
            vals = sorted(historia_hrv)
            n = len(vals)
            p10 = vals[max(0, int(n*0.10))]
            p25 = vals[max(0, int(n*0.25))]
            p75 = vals[min(n-1, int(n*0.75))]
            p90 = vals[min(n-1, int(n*0.90))]
            s = _score_por_percentiles(hrv_val, p10, p25, p75, p90, 1)
        else:
            s = 50.0

        # Penalizar levemente si es estimado
        if hrv_es_estimado:
            s = s * 0.90 + 50.0 * 0.10

        # Ajuste por tendencia reciente (últimos 7 días)
        if len(historia_hrv) >= 7:
            x = np.arange(len(historia_hrv[-7:]), dtype=float)
            y = np.array(historia_hrv[-7:], dtype=float)
            mask = ~np.isnan(y)
            if mask.sum() >= 5:
                slope = float(np.polyfit(x[mask], y[mask], 1)[0])
                # Pendiente > +0.5ms/día = mejora → bonus
                # Pendiente < -0.5ms/día = descenso → penalización
                if slope > 0.5:
                    s = min(100.0, s + min(5.0, slope * 2))
                elif slope < -0.5:
                    s = max(0.0, s - min(10.0, abs(slope) * 3))

        scores['hrv'] = round(s, 1)
        pesos_efectivos['hrv'] = 0.40

    # ── FC reposo (peso base 20%) ─────────────────────────────────────────────
    if fc_hoy and fc_hoy > 30:
        if tiene_baseline and baseline.get('fc_media') and baseline.get('fc_std'):
            # FC: más bajo es mejor → dirección -1
            # Usamos media y std porque percentiles de FC no están en baseline
            s = _score_fallback_zscore(
                fc_hoy, baseline['fc_media'], baseline['fc_std'], -1)
        else:
            s = 50.0
        scores['fc'] = round(s, 1)
        pesos_efectivos['fc'] = 0.18

    # ── Sueño duración (peso 15%) ─────────────────────────────────────────────
    if sleep_h and sleep_h > 0:
        if tiene_baseline and baseline.get('sleep_media_h') and baseline.get('sleep_std_h'):
            s = _score_fallback_zscore(
                sleep_h, baseline['sleep_media_h'], baseline['sleep_std_h'], 1)
        else:
            # Tabla fisiológica básica cuando no hay baseline
            anchors = [(4.0,8),(5.0,18),(5.5,28),(6.0,42),(6.5,58),
                       (7.0,72),(7.5,82),(8.0,90),(8.5,96),(9.0,100)]
            s = 50.0
            for i in range(len(anchors)-1):
                h0,v0 = anchors[i]; h1,v1 = anchors[i+1]
                if h0 <= sleep_h <= h1:
                    s = v0 + (sleep_h-h0)/(h1-h0)*(v1-v0)
                    break
            else:
                s = 100.0 if sleep_h >= 9 else 8.0
        scores['sueno_dur'] = round(s, 1)
        pesos_efectivos['sueno_dur'] = 0.12

    # ── Sueño calidad: deep + REM (peso 10%) ──────────────────────────────────
    if sleep_h and sleep_h > 0 and (deep_h is not None or rem_h is not None):
        calidad = ((deep_h or 0) + (rem_h or 0)) / sleep_h
        ref_cal = baseline.get('sleep_calidad_media', 0.28) if tiene_baseline else 0.28
        std_cal = 0.08  # std típico de calidad sueño
        s = _score_fallback_zscore(calidad, ref_cal, std_cal, 1)
        scores['sueno_cal'] = round(s, 1)
        pesos_efectivos['sueno_cal'] = 0.08

    # ── Stress (peso 12%) ─────────────────────────────────────────────────────
    if stress_avg is not None:
        if tiene_baseline and baseline.get('stress_media') and baseline.get('stress_std'):
            s = _score_fallback_zscore(
                stress_avg, baseline['stress_media'], baseline['stress_std'], -1)
        else:
            anchors = [(0,100),(15,92),(25,80),(35,68),(45,55),
                       (55,42),(65,28),(75,16),(100,5)]
            s = 50.0
            for i in range(len(anchors)-1):
                s0,v0 = anchors[i]; s1,v1 = anchors[i+1]
                if s0 <= stress_avg <= s1:
                    s = v0 + (stress_avg-s0)/(s1-s0)*(v1-v0)
                    break
        scores['stress'] = round(s, 1)
        pesos_efectivos['stress'] = 0.12

    # ── SpO2 (peso variable — hasta 10%) ──────────────────────────────────────
    if spo2_avg and spo2_avg > 0:
        s = _score_spo2(spo2_avg)
        scores['spo2'] = round(s, 1)
        pesos_efectivos['spo2'] = 0.10

    if not scores:
        return {
            'estado_autonomico': 50.0,
            'scores': {},
            'pesos': {},
            'n_criticos': 0,
            'n_bajos': 0,
            'sin_datos': True,
        }

    # ── Normalizar pesos a 1.0 ────────────────────────────────────────────────
    total_peso = sum(pesos_efectivos.values())
    pesos_norm = {k: v/total_peso for k,v in pesos_efectivos.items()}

    # ── Suma ponderada ────────────────────────────────────────────────────────
    ea_base = sum(pesos_norm[k] * scores[k] for k in pesos_norm if k in scores)

    # ── Penalización exponencial por co-ocurrencia ────────────────────────────
    # Si múltiples variables caen simultáneamente, el efecto es peor que la suma
    n_criticos = sum(1 for s in scores.values() if s < 25)
    n_bajos    = sum(1 for s in scores.values() if s < 45)

    penalizacion = 1.0
    if n_criticos >= 2:
        penalizacion *= (0.82 ** n_criticos)   # exponencial — 2 críticos: ×0.67
    elif n_criticos == 1 and n_bajos >= 2:
        penalizacion *= 0.88
    elif n_bajos >= 3:
        penalizacion *= 0.93

    ea = round(max(0.0, min(100.0, ea_base * penalizacion)), 1)

    # Alias para compatibilidad con dashboard (espera ciertas claves)
    scores['tsb'] = None  # se llena desde el modificador de carga
    scores['hrv']      = scores.get('hrv', None)
    scores['fc']       = scores.get('fc', None)
    scores['stress']   = scores.get('stress', None)
    scores['sueno_dur'] = scores.get('sueno_dur', None)

    return {
        'estado_autonomico': ea,
        'scores':            scores,
        'pesos':             pesos_norm,
        'n_criticos':        n_criticos,
        'n_bajos':           n_bajos,
        'penalizacion':      round(penalizacion, 3),
    }


# ── Modificador de Carga ──────────────────────────────────────────────────────
def calcular_modificador_carga(
    tsb:              Optional[float],
    ctl:              Optional[float],
    atl:              Optional[float],
    dias_sin_entrenar: int = 0,
    tss_7d:           Optional[List[float]] = None,
) -> dict:
    """
    Modificador de carga (0.60 - 1.10).
    Amplifica o reduce el Estado Autonómico según la carga acumulada.

    Distingue:
      - "Fresco por taper/descanso planificado" → pequeño boost
      - "Fresco por desentrenamiento (>7 días)" → penaliza
      - "En carga progresiva" → neutro a boost leve
      - "Sobrecargado" → penaliza
    """
    mod = 1.0
    factores = {}

    # ── ATL/CTL ratio (Banister) ──────────────────────────────────────────────
    if ctl and atl and ctl > 0:
        ratio = atl / ctl
        if ratio < 0.70:
            f = 0.88   # desentrenamiento severo
        elif ratio < 0.85:
            f = 0.94   # desentrenamiento leve
        elif ratio < 1.05:
            f = 1.00   # mantenimiento — neutro
        elif ratio < 1.20:
            f = 1.03   # carga progresiva óptima — leve boost
        elif ratio < 1.35:
            f = 0.96   # carga alta
        elif ratio < 1.50:
            f = 0.88   # sobrecarga
        else:
            f = 0.78   # sobrecarga severa
        mod *= f
        factores['atl_ctl_ratio'] = {'valor': round(ratio, 3), 'factor': f}

    # ── TSB ───────────────────────────────────────────────────────────────────
    if tsb is not None:
        if dias_sin_entrenar > 7:
            # TSB positivo por no entrenar → penaliza (no es mérito)
            if tsb > 10:
                f = 0.88
            elif tsb > 5:
                f = 0.94
            else:
                f = 0.97
        else:
            # TSB normal dentro del ciclo
            if tsb > 20:
                f = 1.05   # muy fresco → taper o descanso planificado
            elif tsb > 5:
                f = 1.03   # fresco
            elif tsb > -5:
                f = 1.00   # neutro
            elif tsb > -15:
                f = 0.97   # carga moderada
            elif tsb > -25:
                f = 0.90   # carga alta
            elif tsb > -35:
                f = 0.82   # carga muy alta
            else:
                f = 0.72   # fatiga severa
        mod *= f
        factores['tsb'] = {'valor': round(tsb, 1), 'factor': f,
                           'dias_sin_entrenar': dias_sin_entrenar}

    # ── Monotonía (Foster 1998) ───────────────────────────────────────────────
    vals = [v for v in (tss_7d or []) if v > 0]
    if len(vals) >= 4:
        media = np.mean(vals)
        if media > 0:
            mono = np.std(vals) / media
            # Monotonía alta = poca variabilidad = riesgo sobreentrenamiento
            if mono < 0.20:
                f = 0.94   # muy monótono
            elif mono < 0.35:
                f = 0.97
            else:
                f = 1.00   # buena variabilidad
            mod *= f
            factores['monotonia'] = {'valor': round(mono, 3), 'factor': f}

    # Limitar el modificador al rango permitido
    mod = round(max(0.60, min(1.10, mod)), 3)

    # Score TSB para mostrar en dashboard (0-100)
    s_tsb = None
    if tsb is not None:
        anchors = [(-40,5),(-30,12),(-20,25),(-10,48),(0,65),
                   (5,80),(10,90),(15,95),(20,85),(25,75),(30,62),(40,48)]
        if tsb <= -40: s_tsb = 5.0
        elif tsb >= 40: s_tsb = 48.0
        else:
            for i in range(len(anchors)-1):
                t0,v0 = anchors[i]; t1,v1 = anchors[i+1]
                if t0 <= tsb <= t1:
                    s_tsb = round(v0+(tsb-t0)/(t1-t0)*(v1-v0),1)
                    break

    return {
        'modificador': mod,
        'factores':    factores,
        'score_tsb':   s_tsb,
    }


# ── HANNA LIFE principal ──────────────────────────────────────────────────────
def calcular_hanna_life(
    hrv_val:          Optional[float],
    hrv_baseline_7d:  Optional[float],
    fc_hoy:           Optional[float],
    stress_avg:       Optional[float],
    sleep_h:          Optional[float],
    deep_h:           Optional[float],
    rem_h:            Optional[float],
    spo2_avg:         Optional[float],
    tsb:              Optional[float],
    ctl:              Optional[float],
    atl:              Optional[float],
    tss_7d:           Optional[List[float]] = None,
    historia_hrv:     Optional[List[float]] = None,
    dias_sin_entrenar: int = 0,
    hrv_es_estimado:  bool = False,
    baseline:         Optional[dict] = None,
) -> dict:
    """
    HANNA LIFE = Estado_Autonómico × Modificador_Carga
    """
    historia_hrv = historia_hrv or []

    # ── Estado Autonómico ─────────────────────────────────────────────────────
    ea_result = calcular_estado_autonomico(
        hrv_val=hrv_val,
        fc_hoy=fc_hoy,
        stress_avg=stress_avg,
        sleep_h=sleep_h,
        deep_h=deep_h,
        rem_h=rem_h,
        spo2_avg=spo2_avg,
        historia_hrv=historia_hrv,
        baseline=baseline,
        hrv_es_estimado=hrv_es_estimado,
    )

    # ── Modificador de Carga ──────────────────────────────────────────────────
    mc_result = calcular_modificador_carga(
        tsb=tsb,
        ctl=ctl,
        atl=atl,
        dias_sin_entrenar=dias_sin_entrenar,
        tss_7d=tss_7d,
    )

    # ── HANNA LIFE = EA × MC ──────────────────────────────────────────────────
    ea  = ea_result['estado_autonomico']
    mc  = mc_result['modificador']
    hl  = round(max(0.0, min(100.0, ea * mc)), 1)

    # ── Semáforo basado en HL + contexto ─────────────────────────────────────
    # Umbrales dinámicos basados en baseline personal si disponible
    if baseline and baseline.get('hrv_media') and baseline.get('hrv_p25'):
        # El p25 del atleta define su "zona baja normal"
        # Si hoy está bajo el p25, eso es señal autonómica real
        hrv_en_zona_baja = hrv_val and hrv_val < baseline['hrv_p25'] if hrv_val else False
    else:
        hrv_en_zona_baja = False

    if hl < 30:
        semaforo = 'rojo'
        msg = 'Sistema autonómico comprometido — solo recuperación'
    elif hl < 45 and hrv_en_zona_baja:
        semaforo = 'rojo'
        msg = 'HRV bajo zona personal + carga — no entrenar'
    elif hl < 45:
        semaforo = 'amarillo'
        msg = 'Carga reducida — monitorear recuperación'
    elif hl < 62:
        semaforo = 'amarillo'
        msg = 'Entrenamiento moderado — evitar intensidad máxima'
    elif hl >= 62 and mc >= 0.95:
        semaforo = 'verde'
        msg = 'Sistema preparado — podés cargar'
    elif hl >= 62 and mc < 0.95:
        semaforo = 'amarillo'
        msg = 'Vitalidad buena pero carga acumulada — ajustar volumen'
    else:
        semaforo = 'amarillo'
        msg = 'Monitorear — datos insuficientes'

    puede_cargar = semaforo == 'verde'
    nivel = nivel_hanna(hl)

    # Scores para el dashboard — valores reales, no scores
    scores_dashboard = {
        'hrv':       ea_result['scores'].get('hrv'),
        'fc':        ea_result['scores'].get('fc'),
        'stress':    ea_result['scores'].get('stress'),
        'sueno_dur': ea_result['scores'].get('sueno_dur'),
        'sueno_cal': ea_result['scores'].get('sueno_cal'),
        'spo2':      ea_result['scores'].get('spo2'),
        'tsb':       mc_result.get('score_tsb'),
    }

    return {
        'hanna_life':         hl,
        'estado_autonomico':  ea,
        'modificador_carga':  mc,
        'nivel':              nivel['label'],
        'color':              nivel['color'],
        'icon':               nivel['icon'],
        'puede_cargar':       puede_cargar,
        'semaforo':           semaforo,
        'semaforo_msg':       msg,
        'scores':             scores_dashboard,
        'ea_scores':          ea_result['scores'],
        'mc_factores':        mc_result['factores'],
        'n_criticos':         ea_result['n_criticos'],
        'tiene_baseline':     bool(baseline and baseline.get('hrv_p10')),
        'hrv_es_estimado':    hrv_es_estimado,
    }


# ── Riesgo Viral ──────────────────────────────────────────────────────────────
def calcular_riesgo_viral(
    historia_hrv:      List[float],
    baseline:          Optional[dict] = None,
    historia_hanna:    Optional[List[float]] = None,
) -> dict:
    """
    Riesgo viral basado en caída sostenida de HRV (Buchheit 2014, Tedesco 2023).
    Usa percentiles personales si disponibles.
    """
    if not historia_hrv or len(historia_hrv) < 3:
        return {'riesgo_pct': 0, 'nivel': 'bajo', 'alertas': [],
                'recomendacion': 'Sin suficientes datos de HRV'}

    riesgo = 0
    alertas = []

    # Umbral personal si hay baseline
    if baseline and baseline.get('hrv_p10'):
        umbral_critico = baseline['hrv_p10']
        umbral_bajo    = baseline['hrv_p25']
    else:
        media = float(np.mean(historia_hrv))
        std   = float(np.std(historia_hrv)) or 8.0
        umbral_critico = media - 1.5 * std
        umbral_bajo    = media - 0.8 * std

    # 1. Días recientes bajo umbral crítico personal
    recientes = historia_hrv[-3:]
    dias_criticos = sum(1 for v in recientes if v < umbral_critico)
    dias_bajos    = sum(1 for v in recientes if v < umbral_bajo)

    if dias_criticos >= 2:
        riesgo += 35
        alertas.append({'nivel':'alto',
            'msg': f'HRV bajo p10 personal {dias_criticos} días seguidos'})
    elif dias_criticos == 1:
        riesgo += 15
        alertas.append({'nivel':'moderado', 'msg': 'HRV bajo p10 personal ayer'})
    elif dias_bajos >= 2:
        riesgo += 10
        alertas.append({'nivel':'leve', 'msg': 'HRV en zona baja personal'})

    # 2. Tendencia descendente sostenida (5+ días)
    if len(historia_hrv) >= 5:
        x = np.arange(len(historia_hrv[-5:]), dtype=float)
        y = np.array(historia_hrv[-5:], dtype=float)
        mask = ~np.isnan(y)
        if mask.sum() >= 4:
            slope = float(np.polyfit(x[mask], y[mask], 1)[0])
            if slope < -1.0:
                riesgo += 25
                alertas.append({'nivel':'alto',
                    'msg': f'Tendencia HRV descendente ({slope:.1f}ms/día)'})
            elif slope < -0.5:
                riesgo += 12
                alertas.append({'nivel':'moderado',
                    'msg': f'HRV en descenso ({slope:.1f}ms/día)'})

    # 3. HANNA LIFE bajo sostenido
    if historia_hanna and len(historia_hanna) >= 3:
        if all(v < 38 for v in historia_hanna[-3:]):
            riesgo += 20
            alertas.append({'nivel':'moderado',
                'msg': 'HANNA LIFE bajo (<38) 3 días seguidos'})

    riesgo = min(100, riesgo)
    nivel  = 'alto' if riesgo >= 60 else 'moderado' if riesgo >= 30 else 'bajo'

    return {
        'riesgo_pct':    riesgo,
        'nivel':         nivel,
        'alertas':       alertas,
        'recomendacion': (
            'Descanso absoluto. Consultar médico si hay síntomas.' if riesgo >= 60 else
            'Reducir carga 30-50%. Monitorear síntomas.'          if riesgo >= 30 else
            'Sin señales de alerta. Continuar plan.'
        )
    }


# ── Guardar en DB ─────────────────────────────────────────────────────────────
def calcular_y_guardar_hanna_life(
    conn,
    atleta_id:        int,
    fecha:            str = None,
    recalcular_todo:  bool = False,
) -> int:
    fecha = fecha or str(date.today())

    # Asegurar columnas
    asegurar_columnas(conn, 'sleep_hrv', [
        ('hanna_life','REAL'),        ('hanna_nivel','TEXT'),
        ('hanna_scores','TEXT'),      ('hanna_puede_cargar','INTEGER'),
        ('hanna_semaforo','TEXT'),    ('hanna_semaforo_msg','TEXT'),
        ('estado_autonomico','REAL'), ('modificador_carga','REAL'),
        ('riesgo_viral','REAL'),      ('riesgo_viral_nivel','TEXT'),
        ('riesgo_viral_alertas','TEXT'),
    ])
    conn.commit()

    # Baseline personal
    try:
        from noah_baseline import calcular_y_guardar_baseline
        baseline = calcular_y_guardar_baseline(conn, atleta_id)
    except ImportError:
        baseline = None

    # TSS, TSB, CTL, ATL maps
    df_ses = pd.read_sql(
        "SELECT fecha, SUM(tss_total) as tss, MAX(ctl) as ctl, MAX(atl) as atl "
        "FROM sesiones WHERE atleta_id=%s AND tss_total>0 GROUP BY fecha ORDER BY fecha",
        conn, params=[atleta_id]
    )
    df_ses['fecha'] = df_ses['fecha'].astype(str)
    tss_map = dict(zip(df_ses['fecha'], df_ses['tss'].astype(float)))
    ctl_map = dict(zip(df_ses['fecha'], df_ses['ctl'].astype(float)))
    atl_map = dict(zip(df_ses['fecha'], df_ses['atl'].astype(float)))

    df_tsb = pd.read_sql(
        "SELECT fecha, ctl, atl FROM sesiones "
        "WHERE atleta_id=%s AND ctl IS NOT NULL",
        conn, params=[atleta_id]
    )
    df_tsb['fecha'] = df_tsb['fecha'].astype(str)
    tsb_map = {r['fecha']: float(r['ctl'])-float(r['atl'])
               for _,r in df_tsb.iterrows()}

    # HRV baseline 30d
    df_hrv30 = pd.read_sql(
        "SELECT hrv_rmssd, hrv_estimado_valor FROM sleep_hrv "
        "WHERE atleta_id=%s ORDER BY fecha DESC LIMIT 30",
        conn, params=[atleta_id]
    )
    df_hrv30['hrv'] = df_hrv30['hrv_rmssd'].combine_first(df_hrv30['hrv_estimado_valor'])
    hrv30 = df_hrv30['hrv'].dropna().values
    baseline_30d = float(hrv30.mean()) if len(hrv30) >= 5 else None

    cond   = "atleta_id=%s" if recalcular_todo else \
             "atleta_id=%s AND fecha<=%s AND hanna_life IS NULL"
    params = [atleta_id] if recalcular_todo else [atleta_id, fecha]

    rows = conn.execute(f"""
        SELECT id, fecha, hrv_rmssd, hrv_estimado_valor, hrv_estimado,
               sleep_h, deep_h, rem_h, hr_reposo, stress_avg, spo2_avg
        FROM sleep_hrv WHERE {cond} ORDER BY fecha
    """, params).fetchall()

    if not rows:
        return 0

    historia_hrv   = []
    historia_hanna = []

    hist = conn.execute("""
        SELECT hrv_rmssd, hrv_estimado_valor, hanna_life FROM sleep_hrv
        WHERE atleta_id=%s AND fecha < %s ORDER BY fecha DESC LIMIT 14
    """, (atleta_id, str(rows[0][1])[:10])).fetchall()
    for h in reversed(hist):
        v = h[0] or h[1]
        if v: historia_hrv.append(float(v))
        if h[2]: historia_hanna.append(float(h[2]))

    # Calcular días sin entrenar por fecha
    fechas_entrenamiento = set(df_ses['fecha'].tolist())

    updated = 0
    for row in rows:
        rid, f, hrv_r, hrv_e, es_est, sleep, deep, rem, fc, stress, spo2 = row
        f = str(f)[:10]

        hrv_val = hrv_r or hrv_e
        tsb = tsb_map.get(f)
        ctl = ctl_map.get(f)
        atl = atl_map.get(f)
        tss_7d = [tss_map.get(str(date.fromisoformat(f)-timedelta(days=i)), 0)
                  for i in range(7)]

        # Días sin entrenar
        dias_sin = 0
        for i in range(1, 15):
            fd = str(date.fromisoformat(f) - timedelta(days=i))
            if fd in fechas_entrenamiento:
                break
            dias_sin += 1

        result = calcular_hanna_life(
            hrv_val=hrv_val,
            hrv_baseline_7d=float(np.mean(historia_hrv[-7:])) if len(historia_hrv)>=3 else baseline_30d,
            fc_hoy=fc,
            stress_avg=stress,
            sleep_h=sleep,
            deep_h=deep,
            rem_h=rem,
            spo2_avg=spo2,
            tsb=tsb,
            ctl=ctl,
            atl=atl,
            tss_7d=tss_7d,
            historia_hrv=historia_hrv[-14:],
            dias_sin_entrenar=dias_sin,
            hrv_es_estimado=bool(es_est and not hrv_r),
            baseline=baseline,
        )

        riesgo = calcular_riesgo_viral(
            historia_hrv=historia_hrv[-14:],
            baseline=baseline,
            historia_hanna=historia_hanna[-14:],
        )

        # Suavizado EMA (α=0.30) — reduce variación abrupta
        hl_final = result['hanna_life']
        if len(historia_hanna) >= 3:
            hl_final = round(0.30 * hl_final + 0.70 * historia_hanna[-1], 1)
            hl_final = max(0.0, min(100.0, hl_final))

        conn.execute("""
            UPDATE sleep_hrv SET
                hanna_life=%s, hanna_nivel=%s, hanna_scores=%s,
                hanna_puede_cargar=%s, hanna_semaforo=%s, hanna_semaforo_msg=%s,
                estado_autonomico=%s, modificador_carga=%s,
                riesgo_viral=%s, riesgo_viral_nivel=%s, riesgo_viral_alertas=%s
            WHERE id=%s
        """, (
            hl_final, result['nivel'],
            json.dumps(result['scores']),
            1 if result['puede_cargar'] else 0,
            result['semaforo'], result['semaforo_msg'],
            result['estado_autonomico'], result['modificador_carga'],
            riesgo['riesgo_pct'], riesgo['nivel'],
            json.dumps(riesgo['alertas']),
            rid,
        ))

        if hrv_val: historia_hrv.append(float(hrv_val))
        historia_hanna.append(hl_final)
        historia_hrv   = historia_hrv[-14:]
        historia_hanna = historia_hanna[-14:]
        updated += 1

    conn.commit()
    return updated


def get_hanna_hoy(conn, atleta_id: int,
                  fecha: str = None) -> dict:
    fecha = fecha or str(date.today())
    row = conn.execute("""
        SELECT hanna_life, hanna_nivel, hanna_scores, hanna_puede_cargar,
               hanna_semaforo, hanna_semaforo_msg,
               estado_autonomico, modificador_carga,
               riesgo_viral, riesgo_viral_nivel, riesgo_viral_alertas,
               hrv_rmssd, hrv_estimado_valor, hrv_estimado,
               body_battery, stress_avg, sleep_h, hr_reposo, spo2_avg
        FROM sleep_hrv WHERE atleta_id=%s
        AND fecha <= %s AND hanna_life IS NOT NULL
        ORDER BY fecha DESC LIMIT 1
    """, (atleta_id, fecha)).fetchone()

    if not row:
        return {}

    try: scores = json.loads(row[2]) if row[2] else {}
    except: scores = {}
    try: alertas = json.loads(row[10]) if row[10] else []
    except: alertas = []

    hrv_ms = row[11] or row[12]
    return {
        'hanna_life':           row[0],
        'hanna_nivel':          row[1],
        'hanna_scores':         scores,
        'puede_cargar':         bool(row[3]),
        'semaforo':             row[4],
        'semaforo_msg':         row[5],
        'estado_autonomico':    row[6],
        'modificador_carga':    row[7],
        'riesgo_viral':         row[8],
        'riesgo_viral_nivel':   row[9],
        'riesgo_viral_alertas': alertas,
        'hrv_ms':               hrv_ms,
        'hrv_estimado':         bool(row[13] and not row[11]),
        'body_battery':         row[14],
        'stress':               row[15],
        'sleep_h':              row[16],
        'hr_reposo':            row[17],
        'spo2':                 row[18],
    }


# ── Script standalone ─────────────────────────────────────────────────────────
if __name__ == '__main__':
    import argparse, sys, os
    import psycopg2
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))

    ap = argparse.ArgumentParser(description='NOAH — HANNA LIFE v3')
    ap.add_argument('--atleta', type=int, default=None)
    ap.add_argument('--todos',  action='store_true')
    ap.add_argument('--todo',   action='store_true')
    args = ap.parse_args()

    # Conexión a Postgres (Supabase) vía variable de entorno DATABASE_URL —
    # mismo patrón que usa app.py en producción. Antes conectaba a un
    # archivo noa.db local (SQLite); ahora todo vive en la misma base
    # Postgres, así que este script de prueba manual usa la misma fuente.
    # ConexionCompat agrega el método .execute() directo que psycopg2 no
    # tiene de fábrica (ver db_compat.py) — sin esto, conn.execute(...)
    # más abajo fallaría con AttributeError.
    from db_compat import ConexionCompat
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("Falta la variable de entorno DATABASE_URL (cadena de conexión a Postgres/Supabase)")
        sys.exit(1)
    conn = ConexionCompat(psycopg2.connect(db_url))

    if args.todos:
        atletas = [r[0] for r in conn.execute(
            "SELECT id FROM atletas WHERE activo=1").fetchall()]
    elif args.atleta:
        atletas = [args.atleta]
    else:
        print("Usar --atleta N o --todos")
        conn.close(); exit(1)

    for aid in atletas:
        nombre = conn.execute(
            "SELECT nombre FROM atletas WHERE id=%s", (aid,)).fetchone()
        nombre = nombre[0] if nombre else f'Atleta {aid}'
        print(f'\nCalculando HANNA LIFE v3 para {nombre}...')
        n = calcular_y_guardar_hanna_life(conn, aid, recalcular_todo=args.todo)
        print(f'✓ {n} días calculados')

        hoy = get_hanna_hoy(conn, aid)
        if hoy:
            sem = {'verde':'🟢','amarillo':'🟡','rojo':'🔴'}.get(hoy.get('semaforo'),'?')
            print(f"  HANNA LIFE: {hoy.get('hanna_life')} — {hoy.get('hanna_nivel')}")
            print(f"  EA: {hoy.get('estado_autonomico')} | MC: {hoy.get('modificador_carga')}")
            print(f"  Semáforo: {sem} {hoy.get('semaforo_msg')}")
            print(f"  HRV: {hoy.get('hrv_ms')}ms | SpO2: {hoy.get('spo2')}% | Sueño: {hoy.get('sleep_h')}h")

    conn.close()
