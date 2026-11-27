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
    if val is None or media is None or not std or std <= 0:
        return 50.0
    z = (val - media) / std * direccion
    return round(100.0 / (1.0 + math.exp(-1.2 * z)), 1)


# ── Normas poblacionales por edad y sexo (ancla ABSOLUTA) ─────────────────────
# Por qué: el score por percentiles mide al atleta contra SU PROPIA distribución.
# Si su HRV viene deprimido, "normal para él" puntúa alto igual → sobreestima.
# Estas normas dan un piso fisiológico real: un valor bajo en términos absolutos
# no puede leerse como "óptimo" aunque sea habitual para ese atleta.
#
# rMSSD (ms) desciende con la edad. Valores de referencia de población sana en
# reposo (5 min), VALIDADOS contra datos poblacionales medidos:
#   Dantas et al. (2018), ELSA-Brasil, n≈2.800 — rMSSD medio por tramo:
#     35-44: 34.9 ms | 45-54: 30.0 | 55-64: 26.7 | 65-74: 27.7 (p10 ≈ 17/14/13)
#   Nunan, Sandercock & Brodie (2010) — revisión sistemática (media agrupada ~42 ms).
# Diferencia por sexo: pequeña y mixta en la literatura; Koenig & Thayer (2016)
# hallan rMSSD algo MAYOR en mujeres. Usamos un ajuste modesto (+3 ms), no fuerte.
# El "piso" (ref×0.52) queda cerca del percentil 10 sano de ELSA-Brasil → por
# debajo de eso es un HRV bajo en términos absolutos, no solo "bajo para uno".
def _norma_edad_sexo(edad: Optional[float], sexo: Optional[str]) -> dict:
    e = float(edad) if edad else 40.0
    s = (sexo or 'M').upper()[:1]
    # rMSSD medio de referencia por tramo etario (alineado a ELSA-Brasil 2018)
    if   e < 30: ref = 45.0   # <35 extrapolado hacia arriba (jóvenes ~40-50)
    elif e < 40: ref = 38.0   # ~30-39 (35-44 medido ≈ 35)
    elif e < 50: ref = 32.0   # ~40-49 (entre 35 y 30 medidos)
    elif e < 60: ref = 28.0   # ~50-59 (45-54≈30, 55-64≈27)
    else:        ref = 25.0   # 60+ (55-64≈27, 65-74≈28; conservador)
    if s == 'F':
        ref += 3.0            # Koenig & Thayer 2016 (modesto, evidencia mixta)
    # "piso" ≈ percentil 10 sano; "sano" = referencia. Interpolamos entre ambos.
    hrv_piso = ref * 0.52
    hrv_sano = ref
    return {
        'edad': e, 'sexo': s,
        'hrv_ref': ref, 'hrv_piso': hrv_piso, 'hrv_sano': hrv_sano,
        # FC reposo: norma poblacional adulta (más bajo = mejor).
        'fc_sana': 58.0, 'fc_alta': 75.0,
    }


def _score_absoluto_hrv(hrv: Optional[float], norma: dict) -> Optional[float]:
    """Score 0-100 del HRV contra la NORMA de edad/sexo (no contra uno mismo)."""
    if not hrv or hrv <= 0:
        return None
    piso, sano = norma['hrv_piso'], norma['hrv_sano']
    if hrv >= sano * 1.25:  return 100.0
    if hrv >= sano:         return 85.0 + (hrv - sano) / (sano * 0.25) * 15.0
    if hrv >= piso:         return 40.0 + (hrv - piso) / (sano - piso) * 45.0
    # por debajo del piso fisiológico para la edad
    return max(0.0, 40.0 * (hrv / piso))


def _score_absoluto_fc(fc: Optional[float], norma: dict) -> Optional[float]:
    """Score 0-100 de FC reposo contra norma poblacional (más bajo = mejor)."""
    if not fc or fc <= 30:
        return None
    sana, alta = norma['fc_sana'], norma['fc_alta']   # 58, 75
    if fc <= sana - 13: return 100.0                   # ≤45 lpm (muy entrenado)
    if fc <= sana:      return 85.0 + (sana - fc) / 13.0 * 15.0
    if fc <= alta:      return 40.0 + (alta - fc) / (alta - sana) * 45.0
    return max(0.0, 40.0 - (fc - alta) * 2.0)


def _score_absoluto_tabla(val: Optional[float], anchors) -> Optional[float]:
    """Interpola un score por una tabla de anclas [(x,score),...] ascendente en x."""
    if val is None:
        return None
    if val <= anchors[0][0]:  return float(anchors[0][1])
    if val >= anchors[-1][0]: return float(anchors[-1][1])
    for i in range(len(anchors) - 1):
        x0, v0 = anchors[i]; x1, v1 = anchors[i+1]
        if x0 <= val <= x1:
            return v0 + (val - x0) / (x1 - x0) * (v1 - v0)
    return 50.0


# Tablas de referencia ABSOLUTA (independientes del atleta)
_ANCHOR_SUENO  = [(4.0,8),(5.0,18),(5.5,28),(6.0,42),(6.5,58),
                  (7.0,72),(7.5,82),(8.0,90),(8.5,96),(9.0,100)]
_ANCHOR_STRESS = [(0,100),(15,92),(25,80),(35,68),(45,55),
                  (55,42),(65,28),(75,16),(100,5)]
# Calidad de sueño (deep+REM)/total: ~0.28 típico; <0.15 pobre, >0.40 excelente
_ANCHOR_SUENO_CAL = [(0.10,15),(0.18,40),(0.25,62),(0.32,80),(0.40,92),(0.55,100)]


def _blend(personal: Optional[float], absoluto: Optional[float],
           w: float = 0.55) -> Optional[float]:
    """
    Mezcla el score por percentil PERSONAL con el score por norma ABSOLUTA.
    - Personaliza (filosofía Plews: cada atleta su normal) PERO ancla a la
      fisiología, así un baseline deprimido no infla ni uno sano subestima.
    - Sin baseline personal → vale el absoluto; sin absoluto → vale el personal.
    """
    if personal is None: return absoluto
    if absoluto is None: return personal
    return w * personal + (1.0 - w) * absoluto


# ── Calidad de sueño real (arquitectura del sueño) ────────────────────────────
# No alcanza con las horas: importa CÓMO se duerme. Usamos lo que Garmin ya nos
# da y que no estábamos usando: sueño profundo, REM, liviano y despertares.
# Normas de arquitectura del sueño en adultos sanos (Ohayon et al. 2004,
# meta-análisis de parámetros normativos del sueño):
#   - Profundo (N3): ~13-23% del total   - REM: ~20-25% del total
#   - Fragmentación (tiempo despierto): cuanto menos, mejor
# Cada sub-score es 0-100; se combinan (profundo 40% / REM 40% / fragmentación 20%).
_ANCHOR_DEEP = [(0.04,12),(0.08,38),(0.11,62),(0.14,82),(0.18,100),
                (0.24,95),(0.32,78),(0.45,55)]   # % del total en profundo
_ANCHOR_REM  = [(0.06,12),(0.12,42),(0.16,65),(0.20,88),(0.24,100),
                (0.30,92),(0.40,72)]              # % del total en REM
_ANCHOR_FRAG = [(0.0,100),(0.04,92),(0.08,78),(0.13,58),(0.20,38),(0.30,18),(0.45,5)]

def _score_calidad_sueno(deep_h, rem_h, light_h, awake_h, sleep_h) -> Optional[float]:
    """Score 0-100 de calidad de sueño por arquitectura. None si no hay datos."""
    if not sleep_h or sleep_h <= 0:
        return None
    partes, pesos = [], []
    if deep_h is not None:
        partes.append(_score_absoluto_tabla(deep_h / sleep_h, _ANCHOR_DEEP)); pesos.append(0.40)
    if rem_h is not None:
        partes.append(_score_absoluto_tabla(rem_h / sleep_h, _ANCHOR_REM)); pesos.append(0.40)
    if awake_h is not None:
        total = sleep_h + (awake_h or 0)
        frag = (awake_h or 0) / total if total > 0 else 0
        partes.append(_score_absoluto_tabla(frag, _ANCHOR_FRAG)); pesos.append(0.20)
    if not partes:
        return None
    tot = sum(pesos)
    return round(sum(p * w for p, w in zip(partes, pesos)) / tot, 1)


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
    edad:         Optional[float] = None,
    sexo:         Optional[str] = None,
    light_h:      Optional[float] = None,
    awake_h:      Optional[float] = None,
    body_battery: Optional[float] = None,
) -> dict:
    """
    Calcula el Estado Autonómico (0-100) usando percentiles personales,
    con TECHO por norma absoluta de edad/sexo para no sobreestimar cuando
    el baseline personal viene deprimido.
    """
    tiene_baseline = (
        baseline and
        baseline.get('fase') not in ('sin_datos', None) and
        baseline.get('hrv_p10') is not None
    )
    norma = _norma_edad_sexo(edad, sexo)

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

        # Mezcla con norma absoluta edad/sexo (Nunan 2010): el HRV bajo para su
        # edad no se infla por percentil; el sano no se subestima.
        s_abs_hrv = _score_absoluto_hrv(hrv_val, norma)
        s_personal = s
        s = _blend(s_personal, s_abs_hrv)

        scores['hrv'] = round(s, 1)
        scores['hrv_abs'] = round(s_abs_hrv, 1) if s_abs_hrv is not None else None
        pesos_efectivos['hrv'] = 0.40

    # ── FC reposo (peso base 20%) ─────────────────────────────────────────────
    if fc_hoy and fc_hoy > 30:
        s_pers = None
        if tiene_baseline and baseline.get('fc_media') and baseline.get('fc_std'):
            # FC: más bajo es mejor → dirección -1
            s_pers = _score_fallback_zscore(
                fc_hoy, baseline['fc_media'], baseline['fc_std'], -1)
        # Mezcla con norma poblacional de FC reposo
        s_abs_fc = _score_absoluto_fc(fc_hoy, norma)
        s = _blend(s_pers, s_abs_fc)
        if s is None:
            s = 50.0
        scores['fc'] = round(s, 1)
        pesos_efectivos['fc'] = 0.18

    # ── Sueño duración (peso 15%) ─────────────────────────────────────────────
    if sleep_h and sleep_h > 0:
        # Score absoluto por norma fisiológica (National Sleep Foundation,
        # Hirshkowitz 2015: 7-9h adulto).
        s_abs_sleep = _score_absoluto_tabla(sleep_h, _ANCHOR_SUENO)
        s_pers = None
        if tiene_baseline and baseline.get('sleep_media_h') and baseline.get('sleep_std_h'):
            s_pers = _score_fallback_zscore(
                sleep_h, baseline['sleep_media_h'], baseline['sleep_std_h'], 1)
        # Mezcla: dormir poco en absoluto no se lee como óptimo aunque sea lo
        # habitual; y el absoluto aporta aunque no haya baseline.
        s = _blend(s_pers, s_abs_sleep)
        scores['sueno_dur'] = round(s, 1)
        pesos_efectivos['sueno_dur'] = 0.12

    # ── Sueño calidad: arquitectura (profundo + REM + fragmentación) ──────────
    if sleep_h and sleep_h > 0 and (deep_h is not None or rem_h is not None):
        s_arq = _score_calidad_sueno(deep_h, rem_h, light_h, awake_h, sleep_h)
        if s_arq is not None:
            # Mezcla leve con la referencia personal de calidad si existe
            if tiene_baseline and baseline.get('sleep_calidad_media'):
                calidad = ((deep_h or 0) + (rem_h or 0)) / sleep_h
                s_pers = _score_fallback_zscore(
                    calidad, baseline['sleep_calidad_media'], 0.08, 1)
                s_arq = _blend(s_arq, s_pers, w=0.65)
            scores['sueno_cal'] = round(s_arq, 1)
            pesos_efectivos['sueno_cal'] = 0.10

    # ── Stress (peso 12%) ─────────────────────────────────────────────────────
    if stress_avg is not None:
        s_pers = None
        if tiene_baseline and baseline.get('stress_media') and baseline.get('stress_std'):
            s_pers = _score_fallback_zscore(
                stress_avg, baseline['stress_media'], baseline['stress_std'], -1)
        # Stress de Garmin ya es 0-100 absoluto; lo mezclamos con el personal.
        s_abs = _score_absoluto_tabla(stress_avg, _ANCHOR_STRESS)
        s = _blend(s_pers, s_abs)
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
    # Si múltiples variables caen simultáneamente, el efecto es peor que la suma.
    # Solo biomarcadores ponderados (no diagnósticos como hrv_abs).
    sc_bio = [scores[k] for k in pesos_efectivos if scores.get(k) is not None]
    n_criticos = sum(1 for s in sc_bio if s < 25)
    n_bajos    = sum(1 for s in sc_bio if s < 45)

    penalizacion = 1.0
    if n_criticos >= 2:
        penalizacion *= (0.82 ** n_criticos)   # exponencial — 2 críticos: ×0.67
    elif n_criticos == 1 and n_bajos >= 2:
        penalizacion *= 0.88
    elif n_bajos >= 3:
        penalizacion *= 0.93

    ea = round(max(0.0, min(100.0, ea_base * penalizacion)), 1)

    # ── Chequeo de divergencia con Body Battery (NO entra al cálculo) ─────────
    # Body battery ya integra HRV+sueño+actividad; sumarlo sería contar dos veces.
    # Pero sirve de CONTROL: si el cuerpo (EA) y el body battery discrepan mucho,
    # algo no cierra (dato raro o lógica a revisar) → aviso para coach/programador.
    bb_alerta = None
    if body_battery is not None and 0 <= body_battery <= 100:
        bb_gap = ea - float(body_battery)
        if abs(bb_gap) >= 30:
            bb_alerta = {
                'body_battery': round(float(body_battery), 0),
                'ea': ea,
                'gap': round(bb_gap, 0),
                'msg': (f'EA {ea:.0f} vs Body Battery {body_battery:.0f}: '
                        f'discrepan {abs(bb_gap):.0f} pts — revisar dato o lógica.'),
            }

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
        'bb_alerta':         bb_alerta,
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

    # ── Estado de carga: SEPARA sobrecarga de desentrenamiento ────────────────
    # Clave para no mentir en el texto: un modificador <1 puede ser por carga
    # (te está pesando) O por no entrenar (venís frenado). No es lo mismo.
    ratio = (atl / ctl) if (ctl and atl and ctl > 0) else None
    if dias_sin_entrenar > 7 or (ratio is not None and ratio < 0.80 and (tsb or 0) > 8):
        carga_estado = 'desentrenamiento'
        carga_label  = 'Venís frenado — la falta de carga, no la carga, explica el bajón'
    elif (ratio is not None and ratio >= 1.35) or (tsb is not None and tsb < -25):
        carga_estado = 'sobrecarga'
        carga_label  = 'La carga te está pesando — fatiga acumulada'
    elif (ratio is not None and ratio >= 1.05) or (tsb is not None and tsb <= -8):
        carga_estado = 'carga'
        carga_label  = 'En carga de entrenamiento'
    elif tsb is not None and tsb > 15 and dias_sin_entrenar <= 3:
        carga_estado = 'fresco'
        carga_label  = 'Fresco por descanso planificado — hay margen para cargar'
    else:
        carga_estado = 'equilibrio'
        carga_label  = 'Carga y recuperación en equilibrio'

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
        'modificador':  mod,
        'factores':     factores,
        'score_tsb':    s_tsb,
        'carga_estado': carga_estado,
        'carga_label':  carga_label,
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
    edad:             Optional[float] = None,
    sexo:             Optional[str] = None,
    light_h:          Optional[float] = None,
    awake_h:          Optional[float] = None,
    body_battery:     Optional[float] = None,
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
        edad=edad,
        sexo=sexo,
        light_h=light_h,
        awake_h=awake_h,
        body_battery=body_battery,
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

    carga_estado = mc_result.get('carga_estado')
    # El impacto de la carga = cuánto el modificador mueve al cuerpo (HL - EA).
    # Negativo = la carga/estado resta; positivo = aporta frescura.
    impacto = round(hl - ea, 1)

    if hl < 30:
        semaforo = 'rojo'
        msg = 'Sistema comprometido — solo recuperación'
    elif hl < 45 and hrv_en_zona_baja:
        semaforo = 'rojo'
        msg = 'HRV bajo tu zona + fatiga — no entrenar'
    elif hl < 45:
        semaforo = 'amarillo'
        msg = ('Venís frenado — reactivá progresivo' if carga_estado == 'desentrenamiento'
               else 'Carga reducida — monitoreá recuperación')
    elif hl < 62:
        semaforo = 'amarillo'
        if carga_estado == 'sobrecarga':
            msg = 'La carga te pesa — bajá volumen e intensidad'
        elif carga_estado == 'desentrenamiento':
            msg = 'Venís frenado — reactivá progresivo, sin exigir'
        else:
            msg = 'Cuerpo moderado — entrená suave y observá'
    elif hl >= 62 and mc >= 0.95:
        semaforo = 'verde'
        msg = 'Sistema preparado — cargá normal'
    elif hl >= 62 and carga_estado == 'desentrenamiento':
        semaforo = 'amarillo'
        msg = 'Cuerpo bien pero venís frenado — reactivá sin exigir'
    elif hl >= 62 and mc < 0.95:
        semaforo = 'amarillo'
        msg = 'Cuerpo bien pero la carga pesa — ajustá volumen'
    else:
        semaforo = 'amarillo'
        msg = 'Monitorear — datos insuficientes'

    # Veredicto del día (lo que pidió el coach): cargar / reducir / revisar
    veredicto = ('cargar' if semaforo == 'verde'
                 else 'revisar' if semaforo == 'rojo'
                 else 'reducir')
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
        'impacto_carga':      impacto,
        'carga_estado':       carga_estado,
        'carga_label':        mc_result.get('carga_label'),
        'nivel':              nivel['label'],
        'color':              nivel['color'],
        'icon':               nivel['icon'],
        'puede_cargar':       puede_cargar,
        'veredicto':          veredicto,
        'semaforo':           semaforo,
        'semaforo_msg':       msg,
        'scores':             scores_dashboard,
        'ea_scores':          ea_result['scores'],
        'mc_factores':        mc_result['factores'],
        'n_criticos':         ea_result['n_criticos'],
        'bb_alerta':          ea_result.get('bb_alerta'),
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
        # Sin HRV suficiente NO es "riesgo 0": es "no evaluable". Devolvemos None
        # para no mostrar un 0% engañoso; el frontend muestra "sin datos".
        return {'riesgo_pct': None, 'nivel': 'sin_datos', 'alertas': [],
                'recomendacion': 'Sin HRV suficiente para evaluar riesgo viral'}

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


# ── Centinela de aviso temprano ───────────────────────────────────────────────
def calcular_centinela_enfermedad(
    historia_hrv:  List[float],
    historia_fc:   List[float],
    fc_baseline:   Optional[float] = None,
) -> dict:
    """
    Aviso TEMPRANO de enfermedad / sobrecarga, COMPLEMENTARIO al riesgo viral.
    No reemplaza ni modifica el riesgo viral (algoritmo validado de caída de HRV):
    mira dos señales que el riesgo viral no evalúa de forma directa y que suelen
    ADELANTARSE a la caída de la media de HRV:
      1) FC en reposo en ALZA sostenida sobre la base personal — pródromo clásico
         de infección (Flatt & Esco 2017; Buchheit 2014).
      2) Variabilidad de la HRV (coeficiente de variación) en AUMENTO = pérdida de
         estabilidad autonómica, que precede a la caída de la media (Flatt 2016).
    Solo usa FC-reposo e HRV reales ya guardados; no inventa datos.
    """
    out = {'nivel': 'ok', 'delta_fc': None, 'hrv_cv': None,
           'hrv_cv_base': None, 'senales': [],
           'msg': 'Sin señales tempranas.'}
    senales = []
    puntos = 0

    # 1) Tendencia de FC en reposo (media reciente vs base personal)
    fc_rec = [float(v) for v in (historia_fc or [])[-5:] if v]
    fc_base = fc_baseline
    if fc_base is None and historia_fc:
        prev = [float(v) for v in historia_fc[:-5] if v] or [float(v) for v in historia_fc if v]
        fc_base = float(np.mean(prev)) if prev else None
    if fc_rec and fc_base:
        delta = float(np.mean(fc_rec)) - float(fc_base)
        out['delta_fc'] = round(delta, 1)
        if delta >= 5:
            puntos += 2
            senales.append({'nivel': 'alto', 'msg': f'FC reposo +{delta:.0f} lpm sobre tu base'})
        elif delta >= 3:
            puntos += 1
            senales.append({'nivel': 'moderado', 'msg': f'FC reposo +{delta:.0f} lpm sobre tu base'})

    # 2) Variabilidad de la HRV (CV = desvío / media, en %)
    hrv_rec = [float(v) for v in (historia_hrv or [])[-7:] if v]
    if len(hrv_rec) >= 4:
        m = float(np.mean(hrv_rec)); s = float(np.std(hrv_rec))
        cv = (s / m * 100.0) if m else None
        out['hrv_cv'] = round(cv, 1) if cv is not None else None
        hrv_prev = [float(v) for v in (historia_hrv or [])[-14:-7] if v]
        if len(hrv_prev) >= 4:
            mp = float(np.mean(hrv_prev)); sp = float(np.std(hrv_prev))
            cv_base = (sp / mp * 100.0) if mp else None
            out['hrv_cv_base'] = round(cv_base, 1) if cv_base is not None else None
            if cv is not None and cv_base and cv >= cv_base * 1.5 and cv >= 10:
                puntos += 1
                senales.append({'nivel': 'moderado',
                                'msg': 'Variabilidad de HRV en aumento (inestabilidad autonómica)'})

    nivel = 'alto' if puntos >= 3 else 'alerta' if puntos == 2 else 'leve' if puntos == 1 else 'ok'
    out['nivel'] = nivel
    out['senales'] = senales
    out['msg'] = (
        'Sin señales tempranas. FC reposo y variabilidad estables.' if nivel == 'ok' else
        'Una señal temprana leve. Observá sueño y estrés de hoy.'   if nivel == 'leve' else
        'Dos señales tempranas: cuidá la carga y observá síntomas.' if nivel == 'alerta' else
        'Señales tempranas marcadas: priorizá recuperación y controlá síntomas.'
    )
    return out


# ── Riesgo de enfermedad UNIFICADO (viral + centinela) ────────────────────────
def calcular_riesgo_enfermedad(
    viral: dict, centinela: dict,
    hrv_es_estimado: bool = False, hrv_rellenado: bool = False,
) -> dict:
    """
    Un solo indicador de enfermedad, combinando:
      - Riesgo viral (caída sostenida de HRV; Buchheit 2014, Tedesco 2023)
      - Centinela de aviso temprano (FC reposo en alza + HRV inestable;
        Flatt & Esco 2017) que se ADELANTA a la caída de la media de HRV.
    Etiqueta la FUENTE del dato para no mostrar un número con falsa precisión:
      - 'medido'       → HRV real de reloj
      - 'estimado'     → HRV estimado (sin reloj de noche) → leer con cautela
      - 'no_evaluable' → sin señales ni HRV utilizable
    """
    cent_nivel = (centinela or {}).get('nivel', 'ok')
    cent_pts = {'ok': 0, 'leve': 10, 'alerta': 25, 'alto': 40}.get(cent_nivel, 0)
    base = (viral or {}).get('riesgo_pct')

    if base is None:
        # Sin HRV utilizable para el algoritmo viral: solo vale el centinela.
        pct = cent_pts
        evaluable = cent_pts > 0
    else:
        # El centinela REFUERZA el viral (se adelanta), con medio peso.
        pct = min(100, int(round(base + cent_pts * 0.5)))
        evaluable = True

    if not evaluable:
        fuente = 'no_evaluable'
    elif hrv_es_estimado or hrv_rellenado:
        fuente = 'estimado'
    else:
        fuente = 'medido'

    nivel = ('alto' if pct >= 60 else 'moderado' if pct >= 30 else
             'bajo' if evaluable else 'sin_datos')

    senales = list((viral or {}).get('alertas', [])) + list((centinela or {}).get('senales', []))

    nota_fuente = {
        'medido': '',
        'estimado': ' (HRV estimado — leer como orientativo)',
        'no_evaluable': '',
    }[fuente]
    if fuente == 'no_evaluable':
        msg = 'Sin HRV de reloj ni señales tempranas — no evaluable con confianza.'
    elif nivel == 'alto':
        msg = 'Riesgo alto — descanso y controlar síntomas.' + nota_fuente
    elif nivel == 'moderado':
        msg = 'Señales de alerta — reducí carga y observá.' + nota_fuente
    else:
        msg = 'Sin señales relevantes.' + nota_fuente

    return {
        'pct': pct if evaluable else None,
        'nivel': nivel,
        'fuente': fuente,
        'senales': senales,
        'msg': msg,
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
        ('centinela_nivel','TEXT'),   ('centinela_msg','TEXT'),
        ('fc_reposo_delta','REAL'),   ('hrv_cv','REAL'),
        # Nuevos (Parte 1-3): impacto de carga, veredicto, riesgo unificado
        ('impacto_carga','REAL'),     ('carga_estado','TEXT'),
        ('hanna_veredicto','TEXT'),
        ('riesgo_enf_pct','REAL'),    ('riesgo_enf_nivel','TEXT'),
        ('riesgo_enf_fuente','TEXT'), ('bb_alerta_msg','TEXT'),
    ])
    conn.commit()

    # Baseline personal
    try:
        from noah_baseline import calcular_y_guardar_baseline
        baseline = calcular_y_guardar_baseline(conn, atleta_id)
    except ImportError:
        baseline = None

    # Edad y sexo (para el piso por norma poblacional)
    edad_at, sexo_at = None, None
    try:
        prow = conn.execute(
            "SELECT edad, sexo FROM atletas WHERE id=%s", (atleta_id,)).fetchone()
        if prow:
            edad_at = prow[0]
            sexo_at = prow[1] or 'M'
    except Exception:
        pass

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

    # Base personal de FC en reposo (30 días) para el centinela de aviso temprano
    df_fc30 = pd.read_sql(
        "SELECT hr_reposo FROM sleep_hrv "
        "WHERE atleta_id=%s AND hr_reposo>0 ORDER BY fecha DESC LIMIT 30",
        conn, params=[atleta_id]
    )
    fc30 = df_fc30['hr_reposo'].dropna().values
    fc_baseline_30d = float(fc30.mean()) if len(fc30) >= 5 else None

    cond   = "atleta_id=%s" if recalcular_todo else \
             "atleta_id=%s AND fecha<=%s AND hanna_life IS NULL"
    params = [atleta_id] if recalcular_todo else [atleta_id, fecha]

    rows = conn.execute(f"""
        SELECT id, fecha, hrv_rmssd, hrv_estimado_valor, hrv_estimado,
               sleep_h, deep_h, rem_h, hr_reposo, stress_avg, spo2_avg,
               light_h, awake_h, body_battery
        FROM sleep_hrv WHERE {cond} ORDER BY fecha
    """, params).fetchall()

    if not rows:
        return 0

    historia_hrv   = []
    historia_hanna = []
    historia_fc    = []

    hist = conn.execute("""
        SELECT hrv_rmssd, hrv_estimado_valor, hanna_life, hr_reposo FROM sleep_hrv
        WHERE atleta_id=%s AND fecha < %s ORDER BY fecha DESC LIMIT 14
    """, (atleta_id, str(rows[0][1])[:10])).fetchall()
    for h in reversed(hist):
        v = h[0] or h[1]
        if v: historia_hrv.append(float(v))
        if h[2]: historia_hanna.append(float(h[2]))
        historia_fc.append(float(h[3]) if h[3] else None)

    # Calcular días sin entrenar por fecha
    fechas_entrenamiento = set(df_ses['fecha'].tolist())

    updated = 0
    for row in rows:
        (rid, f, hrv_r, hrv_e, es_est, sleep, deep, rem, fc, stress, spo2,
         light, awake, bbatt) = row
        f = str(f)[:10]

        # HRV del día: real > estimado > relleno por vecino cercano (último
        # día con dato). Marcamos si vino rellenado para etiquetar la confianza.
        hrv_val = hrv_r or hrv_e
        hrv_rellenado = False
        if not hrv_val and historia_hrv:
            hrv_val = historia_hrv[-1]      # vecino temporal más cercano hacia atrás
            hrv_rellenado = True
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
            hrv_es_estimado=bool((es_est and not hrv_r) or hrv_rellenado),
            baseline=baseline,
            edad=edad_at,
            sexo=sexo_at,
            light_h=light,
            awake_h=awake,
            body_battery=bbatt,
        )

        riesgo = calcular_riesgo_viral(
            historia_hrv=historia_hrv[-14:],
            baseline=baseline,
            historia_hanna=historia_hanna[-14:],
        )

        # Centinela de aviso temprano (FC reposo + variabilidad HRV). Incluye el
        # día de hoy en la ventana reciente de FC.
        centinela = calcular_centinela_enfermedad(
            historia_hrv=(historia_hrv[-14:] + ([float(hrv_val)] if hrv_val else [])),
            historia_fc=(historia_fc[-14:] + [float(fc) if fc else None]),
            fc_baseline=fc_baseline_30d,
        )

        # Riesgo de enfermedad UNIFICADO (viral + centinela), con fuente.
        enf = calcular_riesgo_enfermedad(
            riesgo, centinela,
            hrv_es_estimado=bool((es_est and not hrv_r)),
            hrv_rellenado=hrv_rellenado,
        )

        # Suavizado EMA (α=0.30) — reduce variación abrupta
        hl_final = result['hanna_life']
        if len(historia_hanna) >= 3:
            hl_final = round(0.30 * hl_final + 0.70 * historia_hanna[-1], 1)
            hl_final = max(0.0, min(100.0, hl_final))

        bb_msg = (result.get('bb_alerta') or {}).get('msg')
        conn.execute("""
            UPDATE sleep_hrv SET
                hanna_life=%s, hanna_nivel=%s, hanna_scores=%s,
                hanna_puede_cargar=%s, hanna_semaforo=%s, hanna_semaforo_msg=%s,
                estado_autonomico=%s, modificador_carga=%s,
                riesgo_viral=%s, riesgo_viral_nivel=%s, riesgo_viral_alertas=%s,
                centinela_nivel=%s, centinela_msg=%s,
                fc_reposo_delta=%s, hrv_cv=%s,
                impacto_carga=%s, carga_estado=%s, hanna_veredicto=%s,
                riesgo_enf_pct=%s, riesgo_enf_nivel=%s, riesgo_enf_fuente=%s,
                bb_alerta_msg=%s
            WHERE id=%s
        """, (
            hl_final, result['nivel'],
            json.dumps(result['scores']),
            1 if result['puede_cargar'] else 0,
            result['semaforo'], result['semaforo_msg'],
            result['estado_autonomico'], result['modificador_carga'],
            riesgo['riesgo_pct'], riesgo['nivel'],
            json.dumps(riesgo['alertas']),
            centinela['nivel'], centinela['msg'],
            centinela['delta_fc'], centinela['hrv_cv'],
            round(hl_final - result['estado_autonomico'], 1), result.get('carga_estado'),
            result.get('veredicto'),
            enf['pct'], enf['nivel'], enf['fuente'],
            bb_msg,
            rid,
        ))

        if hrv_val: historia_hrv.append(float(hrv_val))
        historia_hanna.append(hl_final)
        historia_fc.append(float(fc) if fc else None)
        historia_hrv   = historia_hrv[-14:]
        historia_hanna = historia_hanna[-14:]
        historia_fc    = historia_fc[-14:]
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
               body_battery, stress_avg, sleep_h, hr_reposo, spo2_avg,
               centinela_nivel, centinela_msg, fc_reposo_delta, hrv_cv,
               impacto_carga, carga_estado, hanna_veredicto,
               riesgo_enf_pct, riesgo_enf_nivel, riesgo_enf_fuente, bb_alerta_msg,
               deep_h, rem_h, light_h, awake_h
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
        'cuerpo':               row[6],   # alias explícito para el frontend
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
        'centinela_nivel':      row[19],
        'centinela_msg':        row[20],
        'fc_reposo_delta':      row[21],
        'hrv_cv':               row[22],
        'impacto_carga':        row[23],
        'carga_estado':         row[24],
        'veredicto':            row[25],
        'riesgo_enf_pct':       row[26],
        'riesgo_enf_nivel':     row[27],
        'riesgo_enf_fuente':    row[28],
        'bb_alerta_msg':        row[29],
        'deep_h':               row[30],
        'rem_h':                row[31],
        'light_h':              row[32],
        'awake_h':              row[33],
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
