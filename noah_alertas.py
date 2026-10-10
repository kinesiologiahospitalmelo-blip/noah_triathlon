# -*- coding: utf-8 -*-
"""
noah_alertas.py — Motor de alertas de carga / intensidad / zonas de NOAH
========================================================================
Detecta cuándo un atleta se "pasó" respecto a límites de seguridad o a su
propia línea de base, a partir de las sesiones REALES sincronizadas y del
ACWR (noah_riesgo_lesion). No reemplaza al coach: le da señales tempranas.

Señales que evalúa (cada una con severidad alta/media):
  1. INTENSIDAD   — sesión con IF muy alto (esfuerzo sostenido excesivo).
  2. ZONAS        — mucha proporción del estímulo en zona muy alta (Z5-6).
  3. VOLUMEN SEM. — TSS de los últimos 7 días muy por encima del promedio
                    de las 4 semanas previas.
  4. ACWR         — ratio carga aguda:crónica en zona de riesgo (Gabbett 2016).
  5. MONOTONÍA    — poca variación día a día (Foster 1998), si está disponible.

FUENTES: Coggan (IF/TSS) · Seiler (distribución de intensidad) ·
Gabbett 2016 (ACWR) · Foster 1998 (monotonía/strain).

API pública:
  calcular_alertas(conn, atleta_id, dias=7)  -> {'disponible', 'alertas':[...], 'resumen':{...}}
"""
from datetime import date, timedelta

FUENTES_NO_REAL = ('prescripcion', 'simulacion', 'generada')

# ── Umbrales (defaults de coach; ajustables) ────────────────────────────────
IF_ALTO       = 0.95   # IF >= esto en sesión larga -> intensidad muy alta
IF_MEDIO      = 0.90
DUR_MIN_IF    = 60     # min: solo marca intensidad si la sesión fue de fondo
FRAC_Z56_ALTA = 0.35   # >=35% del TSS de la sesión en Z5-6 -> zona muy alta
FRAC_Z56_MED  = 0.25
TSS_MIN_SESION = 40    # ignora micro-sesiones para la alerta de zonas
VOL_RATIO_ALTO = 1.5   # TSS 7d / promedio semanal 4 sem previas
VOL_RATIO_MED  = 1.3
ACWR_ALTO      = 1.5
ACWR_MED       = 1.3


def _sf(v, d=0.0):
    try:
        return float(v)
    except Exception:
        return d


def _nivel(valor, umbral_med, umbral_alto):
    if valor >= umbral_alto:
        return 'alta'
    if valor >= umbral_med:
        return 'media'
    return None


def evaluar_alertas(sesiones, tss_7d, tss_prev_sem_avg, acwr=None, monotonia=None):
    """Núcleo PURO (sin DB) — así se puede testear con datos de ejemplo.
    `sesiones`: lista de dicts con fecha, deporte, tss, if_, z56_frac, dur_min.
    Devuelve lista de alertas ordenadas por severidad."""
    alertas = []

    # 1 y 2 — por sesión (intensidad y zonas)
    for s in sesiones:
        dep = s.get('deporte') or 'sesión'
        f = s.get('fecha')
        iff = _sf(s.get('if_'))
        dur = _sf(s.get('dur_min'))
        tss = _sf(s.get('tss'))
        z56 = _sf(s.get('z56_frac'))

        if iff and dur >= DUR_MIN_IF:
            nv = _nivel(iff, IF_MEDIO, IF_ALTO)
            if nv:
                alertas.append({
                    'tipo': 'intensidad', 'severidad': nv, 'fecha': f, 'deporte': dep,
                    'titulo': 'Intensidad alta',
                    'detalle': f'{dep} con IF {iff:.2f} durante {round(dur)}min — esfuerzo sostenido exigente.'
                })

        if tss >= TSS_MIN_SESION and z56 > 0:
            nv = _nivel(z56, FRAC_Z56_MED, FRAC_Z56_ALTA)
            if nv:
                alertas.append({
                    'tipo': 'zonas', 'severidad': nv, 'fecha': f, 'deporte': dep,
                    'titulo': 'Mucho tiempo en zona alta',
                    'detalle': f'{dep}: {round(z56*100)}% del estímulo en zona 5-6 (muy alta).'
                })

    # 3 — volumen semanal vs promedio de las 4 semanas previas
    if tss_prev_sem_avg and tss_prev_sem_avg > 0:
        ratio = tss_7d / tss_prev_sem_avg
        nv = _nivel(ratio, VOL_RATIO_MED, VOL_RATIO_ALTO)
        if nv:
            alertas.append({
                'tipo': 'volumen', 'severidad': nv, 'fecha': None, 'deporte': None,
                'titulo': 'Carga semanal elevada',
                'detalle': f'TSS de los últimos 7 días {round((ratio-1)*100)}% por encima de tu promedio reciente.'
            })

    # 4 — ACWR
    if acwr is not None:
        nv = _nivel(acwr, ACWR_MED, ACWR_ALTO)
        if nv:
            alertas.append({
                'tipo': 'acwr', 'severidad': nv, 'fecha': None, 'deporte': None,
                'titulo': 'ACWR en zona de riesgo',
                'detalle': f'Ratio carga aguda:crónica {acwr:.2f} (óptimo 0.8-1.3). Riesgo de sobrecarga.'
            })

    # 5 — monotonía
    if monotonia and monotonia.get('nivel_riesgo') in ('alto', 'atencion'):
        alertas.append({
            'tipo': 'monotonia', 'severidad': 'alta' if monotonia['nivel_riesgo'] == 'alto' else 'media',
            'fecha': None, 'deporte': None,
            'titulo': 'Monotonía alta',
            'detalle': monotonia.get('mensaje') or 'Poca variación de carga día a día — sumá un día fácil real.'
        })

    orden = {'alta': 0, 'media': 1}
    alertas.sort(key=lambda a: orden.get(a['severidad'], 9))
    return alertas


# ── Wrapper con acceso a DB ─────────────────────────────────────────────────

def _fetch(conn, sql, params):
    try:
        return conn.execute(sql, params).fetchall()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return []


def calcular_alertas(conn, atleta_id, dias=7, fecha=None):
    hoy = fecha or str(date.today())
    try:
        hoy_d = date.fromisoformat(hoy)
    except Exception:
        hoy_d = date.today(); hoy = str(hoy_d)
    desde_7 = str(hoy_d - timedelta(days=dias))
    desde_35 = str(hoy_d - timedelta(days=dias + 28))

    # Sesiones reales de la ventana (con split de zona si existe)
    rows = _fetch(conn, """
        SELECT fecha, sport, tss_total, tss_z56, intensity_factor, duration_min
        FROM sesiones
        WHERE atleta_id=%s AND fecha > %s AND tss_total > 0
          AND (fuente IS NULL OR fuente NOT IN %s)
        ORDER BY fecha
    """, [atleta_id, desde_7, FUENTES_NO_REAL])

    sesiones = []
    tss_7d = 0.0
    for r in rows:
        tss = _sf(r['tss_total']) if hasattr(r, 'keys') else _sf(r[2])
        z56 = _sf(r['tss_z56']) if hasattr(r, 'keys') else _sf(r[3])
        iff = _sf(r['intensity_factor']) if hasattr(r, 'keys') else _sf(r[4])
        dur = _sf(r['duration_min']) if hasattr(r, 'keys') else _sf(r[5])
        dep = (r['sport'] if hasattr(r, 'keys') else r[1]) or 'sesión'
        f   = str(r['fecha'] if hasattr(r, 'keys') else r[0])
        tss_7d += tss
        sesiones.append({'fecha': f, 'deporte': dep, 'tss': tss,
                         'z56_frac': (z56 / tss) if tss > 0 else 0,
                         'if_': iff, 'dur_min': dur})

    # Promedio semanal de las 4 semanas previas (día -35 a -7)
    prev = _fetch(conn, """
        SELECT COALESCE(SUM(tss_total),0)
        FROM sesiones
        WHERE atleta_id=%s AND fecha > %s AND fecha <= %s AND tss_total > 0
          AND (fuente IS NULL OR fuente NOT IN %s)
    """, [atleta_id, desde_35, desde_7, FUENTES_NO_REAL])
    tss_prev_total = _sf(prev[0][0]) if prev else 0.0
    tss_prev_sem_avg = tss_prev_total / 4.0

    # ACWR / monotonía desde noah_riesgo_lesion (si está disponible)
    acwr = None
    monotonia = None
    try:
        from noah_riesgo_lesion import resumen_riesgo_lesion
        rl = resumen_riesgo_lesion(conn, atleta_id, hoy)
        if rl and rl.get('acwr', {}).get('disponible'):
            acwr = _sf(rl['acwr'].get('acwr'))
        monotonia = rl.get('monotonia_strain') if rl else None
    except Exception:
        pass

    alertas = evaluar_alertas(sesiones, tss_7d, tss_prev_sem_avg, acwr, monotonia)

    return {
        'disponible': True,
        'fecha': hoy,
        'ventana_dias': dias,
        'alertas': alertas,
        'resumen': {
            'total': len(alertas),
            'altas': sum(1 for a in alertas if a['severidad'] == 'alta'),
            'tss_7d': round(tss_7d),
            'tss_prev_sem_avg': round(tss_prev_sem_avg),
            'acwr': round(acwr, 2) if acwr is not None else None,
        },
    }
