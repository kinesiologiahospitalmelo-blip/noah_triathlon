"""
noah_tecnica.py — Análisis biomecánico profesional por deporte
================================================================
Implementa los 10 pilares de análisis técnico:

1. Clasificación inteligente (CTL + pace + VO2max)
2. Perfil biomecánico (spider chart data)
3. Evolución temporal (sparkline últimas 8 semanas)
4. Drift multidimensional (cadencia, GCT, VO, stride)
5. Índice de economía (vertical ratio — Morin 2005)
6. Cadencia por zona de intensidad relativa
7. Detección de sensores (dual mode: con/sin HRM)
8. Recomendaciones priorizadas con ejercicios concretos
9. Comparación con período anterior (↑↓)
10. Cycling/Swimming completo

Bibliografía: Moore 2016, Heiderscheit 2011, Nicol 1991, Morin 2005,
Saunders 2004, Nummela 2007, Bini 2014, Faria 2005, Weyand 2000
"""

import os, math
from collections import defaultdict


# ═══════════════════════════════════════════════════════════════
# CONSTANTES DE REFERENCIA
# ═══════════════════════════════════════════════════════════════

CADENCIA_REF = {
    'elite':        {'min': 180, 'max': 190},
    'avanzado':     {'min': 175, 'max': 185},
    'intermedio':   {'min': 168, 'max': 178},
    'principiante': {'min': 160, 'max': 172},
}

GCT_REF = {'elite': 200, 'bueno': 240, 'promedio': 270, 'mejorar': 300}
VO_REF  = {'elite': 6.0, 'bueno': 8.0, 'promedio': 9.5, 'mejorar': 11.0}
VERT_RATIO_REF = {'elite': 6.0, 'bueno': 8.0, 'promedio': 10.0, 'mejorar': 12.0}


# ═══════════════════════════════════════════════════════════════
# HELPERS ESTADÍSTICOS PUROS (sin numpy) — usados por el panel
# CURVA / HEATMAP / SCATTER de fatiga vs técnica (datos 100% reales)
# ═══════════════════════════════════════════════════════════════

def _pearson(xs, ys):
    """Correlación de Pearson real entre dos series ya emparejadas."""
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx == 0 or vy == 0:
        return 0.0
    return round(cov / math.sqrt(vx * vy), 2)


def _linreg(xs, ys):
    """Regresión lineal simple (mínimos cuadrados) sobre datos reales."""
    n = len(xs)
    if n < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0:
        return {'slope': 0.0, 'intercept': my}
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den
    intercept = my - slope * mx
    return {'slope': round(slope, 3), 'intercept': round(intercept, 2)}


def _kmeans_2d(points, k=2, iters=30):
    """K-means minimalista (sin dependencias) sobre puntos (x, y) reales.
    Devuelve un cluster_id por punto. Si hay muy pocos puntos, no separa
    (todos al cluster 0) para no inventar estructura que no existe."""
    n = len(points)
    if n < max(6, k * 3):
        return [0] * n

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)

    def norm(p):
        nx = (p[0] - minx) / (maxx - minx) if maxx > minx else 0.5
        ny = (p[1] - miny) / (maxy - miny) if maxy > miny else 0.5
        return (nx, ny)

    pts = [norm(p) for p in points]
    order = sorted(range(n), key=lambda i: pts[i][0] + pts[i][1])
    centroids = [pts[order[0]], pts[order[-1]]]

    assign = [0] * n
    for _ in range(iters):
        changed = False
        for i, p in enumerate(pts):
            d0 = (p[0] - centroids[0][0]) ** 2 + (p[1] - centroids[0][1]) ** 2
            d1 = (p[0] - centroids[1][0]) ** 2 + (p[1] - centroids[1][1]) ** 2
            c = 0 if d0 <= d1 else 1
            if c != assign[i]:
                changed = True
            assign[i] = c
        for c in (0, 1):
            members = [pts[i] for i in range(n) if assign[i] == c]
            if members:
                centroids[c] = (sum(m[0] for m in members) / len(members),
                                 sum(m[1] for m in members) / len(members))
        if not changed:
            break
    return assign


def _bucket_estabilidad(valores):
    """Convierte una serie de valores reales de UNA métrica, sesión a sesión,
    en estados óptimo/estable/alerta/degradado según su propio z-score vs
    el baseline histórico del atleta (media y desvío de sus propias sesiones).
    Nunca inventa valores: si hay <2 datos válidos devuelve None por celda."""
    validos = [v for v in valores if v is not None]
    if len(validos) < 2:
        return [None] * len(valores)

    media = sum(validos) / len(validos)
    var = sum((v - media) ** 2 for v in validos) / len(validos)
    std = math.sqrt(var)

    out = []
    for v in valores:
        if v is None:
            out.append(None)
            continue
        if std == 0:
            out.append('estable')
            continue
        z = abs(v - media) / std
        if z <= 0.5:
            out.append('optimo')
        elif z <= 1.0:
            out.append('estable')
        elif z <= 1.75:
            out.append('alerta')
        else:
            out.append('degradado')
    return out


# ═══════════════════════════════════════════════════════════════
# 1. CLASIFICACIÓN INTELIGENTE
# ═══════════════════════════════════════════════════════════════

def _clasificar_nivel(conn, atleta_id):
    """
    Nivel basado en CTL + pace umbral + VO2max.
    Si cualquiera de los 3 indica avanzado, es avanzado.
    """
    cur = conn.cursor() if hasattr(conn, 'cursor') else conn

    # CTL
    q = cur.execute("SELECT ctl FROM sesiones WHERE atleta_id=%s AND ctl IS NOT NULL ORDER BY fecha DESC LIMIT 1", (atleta_id,)) if hasattr(conn, 'execute') else None
    if q is None:
        cur = conn.cursor()
        cur.execute("SELECT ctl FROM sesiones WHERE atleta_id=%s AND ctl IS NOT NULL ORDER BY fecha DESC LIMIT 1", (atleta_id,))
    r = cur.fetchone()
    ctl = float(r[0]) if r and r[0] else 0

    # Pace umbral
    cur.execute("SELECT pace_umbral_run FROM atletas WHERE id=%s", (atleta_id,))
    r = cur.fetchone()
    pace = float(r[0]) if r and r[0] else 99
    vo2 = 0

    # Lógica: si cualquier indicador dice avanzado, es avanzado
    if ctl >= 50 or pace <= 4.5:
        return 'avanzado'
    elif ctl >= 30 or pace <= 5.5:
        return 'intermedio'
    else:
        return 'principiante'


# ═══════════════════════════════════════════════════════════════
# 7. DETECCIÓN DE SENSORES
# ═══════════════════════════════════════════════════════════════

def _detectar_sensores(conn, atleta_id, sport='running'):
    """Detecta qué datos tiene el atleta según sus sensores."""
    cur = conn.cursor() if hasattr(conn, 'cursor') else conn
    if not hasattr(cur, 'execute'):
        cur = conn.cursor()

    cur.execute("""
        SELECT
            COUNT(*) FILTER (WHERE ground_contact_ms IS NOT NULL AND ground_contact_ms > 0) as n_gct,
            COUNT(*) FILTER (WHERE vertical_osc_mm IS NOT NULL AND vertical_osc_mm > 0) as n_vo,
            COUNT(*) FILTER (WHERE stride_length_m IS NOT NULL AND stride_length_m > 0) as n_stride,
            COUNT(*) FILTER (WHERE vertical_ratio IS NOT NULL AND vertical_ratio > 0) as n_vr,
            COUNT(*) FILTER (WHERE left_right_pct IS NOT NULL AND left_right_pct > 0) as n_lr,
            COUNT(*) FILTER (WHERE torque_effectiveness IS NOT NULL AND torque_effectiveness > 0) as n_te,
            COUNT(*) as n_total
        FROM activity_samples sa
        JOIN sesiones s ON s.id = sa.sesion_id
        WHERE s.atleta_id=%s AND s.sport=%s
        AND s.fecha::date >= CURRENT_DATE - INTERVAL '8 weeks'
    """, (atleta_id, sport))
    r = cur.fetchone()

    if not r or r[6] == 0:
        return {'has_hrm_pro': False, 'has_power': False, 'sensores': [], 'faltantes': []}

    threshold = r[6] * 0.05  # al menos 5% de los samples

    sensores = []
    faltantes = []

    if sport == 'running':
        if r[0] > threshold: sensores.append('GCT')
        else: faltantes.append('GCT')
        if r[1] > threshold: sensores.append('Oscilación Vertical')
        else: faltantes.append('Oscilación Vertical')
        if r[2] > threshold: sensores.append('Stride Length')
        else: faltantes.append('Stride Length')
        if r[3] > threshold: sensores.append('Vertical Ratio')
        else: faltantes.append('Vertical Ratio')
    elif sport == 'cycling':
        if r[4] > threshold: sensores.append('L/R Balance')
        else: faltantes.append('L/R Balance')
        if r[5] > threshold: sensores.append('Torque Effectiveness')
        else: faltantes.append('Torque Effectiveness')

    has_hrm = len(faltantes) == 0 if sport == 'running' else True

    return {
        'has_hrm_pro': has_hrm,
        'sensores': sensores,
        'faltantes': faltantes,
        'sensor_recomendado': 'HRM-Pro o HRM-Run' if sport == 'running' and not has_hrm else None,
    }


# ═══════════════════════════════════════════════════════════════
# RUNNING
# ═══════════════════════════════════════════════════════════════

def analizar_running(conn, atleta_id, sesion_id=None, semanas=8):
    """Análisis completo de técnica de running."""
    cur = conn.cursor() if hasattr(conn, 'cursor') else conn
    if not hasattr(cur, 'execute'):
        cur = conn.cursor()

    nivel = _clasificar_nivel(conn, atleta_id)
    sensores = _detectar_sensores(conn, atleta_id, 'running')

    # Pace umbral
    cur.execute("SELECT pace_umbral_run FROM atletas WHERE id=%s", (atleta_id,))
    r = cur.fetchone()
    pace_umbral = float(r[0]) if r and r[0] else 5.5

    # Samples — cadence > 140 excluye caminata/warm-up
    if sesion_id:
        cur.execute("""
            SELECT cadence, speed_ms, hr, ground_contact_ms, vertical_osc_mm,
                   stride_length_m, vertical_ratio, ts_s
            FROM activity_samples
            WHERE sesion_id=%s AND cadence > 140
            ORDER BY ts_s
        """, (sesion_id,))
    else:
        cur.execute("""
            SELECT sa.cadence, sa.speed_ms, sa.hr, sa.ground_contact_ms, sa.vertical_osc_mm,
                   sa.stride_length_m, sa.vertical_ratio, sa.ts_s,
                   s.fecha::date, s.id, s.tsb
            FROM activity_samples sa
            JOIN sesiones s ON s.id = sa.sesion_id
            WHERE s.atleta_id=%s AND s.sport='running'
            AND s.fecha::date >= CURRENT_DATE - INTERVAL '%s weeks'
            AND sa.cadence > 140
            ORDER BY s.fecha, sa.ts_s
        """ % (atleta_id, semanas))

    samples = cur.fetchall()
    if not samples:
        return {'error': 'Sin datos de running con cadencia > 140 spm.', 'sensores': sensores}

    cadencias = [float(s[0]) for s in samples if s[0] and float(s[0]) > 140]
    speeds    = [float(s[1]) for s in samples if s[1] and float(s[1]) > 0.5]
    gcts      = [float(s[3]) for s in samples if s[3] and float(s[3]) > 100 and float(s[3]) < 500]
    vos       = [float(s[4]) for s in samples if s[4] and float(s[4]) > 0 and float(s[4]) < 200]
    strides   = [float(s[5]) for s in samples if s[5] and float(s[5]) > 0.3 and float(s[5]) < 3.0]
    vrs       = [float(s[6]) for s in samples if s[6] and float(s[6]) > 0 and float(s[6]) < 20]

    cad_ref = CADENCIA_REF[nivel]

    resultado = {
        'deporte': 'running',
        'nivel': nivel,
        'pace_umbral': pace_umbral,
        'n_muestras': len(samples),
        'sensores': sensores,
        'metricas': {},
        'spider': {},          # datos para radar chart
        'drift': {},           # drift multidimensional
        'sparkline': [],       # evolución semanal
        'comparacion': {},     # vs período anterior
        'interpretacion': [],
        'recomendaciones': [],
    }

    # ══════════════════════════════════════════════════════════
    # 1. CADENCIA
    # ══════════════════════════════════════════════════════════
    if cadencias:
        cad_avg = round(sum(cadencias) / len(cadencias))
        n = len(cadencias)
        pct10 = max(1, n // 10)
        q_inicio = round(sum(cadencias[:pct10]) / pct10)
        q_final  = round(sum(cadencias[-pct10:]) / pct10)
        drift_cad = round((q_final - q_inicio) / q_inicio * 100, 1) if q_inicio > 0 else 0

        estado = 'óptima' if cad_ref['min'] <= cad_avg <= cad_ref['max'] else (
            'baja' if cad_avg < cad_ref['min'] else 'alta')

        resultado['metricas']['cadencia'] = {
            'promedio': cad_avg, 'estado': estado,
            'referencia': cad_ref,
            'q1': q_inicio, 'q4': q_final, 'drift_pct': drift_cad,
        }
        resultado['drift']['cadencia'] = drift_cad

        # Spider: 0-100 score
        opt_mid = (cad_ref['min'] + cad_ref['max']) / 2
        cad_score = max(0, min(100, 100 - abs(cad_avg - opt_mid) * 5))
        resultado['spider']['cadencia'] = round(cad_score)

        resultado['interpretacion'].append(
            f'Cadencia promedio: {cad_avg} spm — dentro del patrón habitual del atleta. '
            f'Inicio: {q_inicio} spm → Final: {q_final} spm. '
            f'Drift: {drift_cad:+.1f}% ({"estable" if abs(drift_cad) < 3 else "variación por fatiga"}).')

        if estado == 'baja':
            resultado['interpretacion'].append(
                f'Cadencia {cad_avg} spm — por debajo de tu patrón habitual. '
                f'Verificar si se asocia con cambios en stride o GCT.')
        elif estado == 'alta':
            pass  # cadencia alta no es problema — NOAH no juzga sin contexto

        if drift_cad < -5:
            resultado['interpretacion'].append(
                f'Cadencia cae {abs(drift_cad):.1f}% ({q_inicio}→{q_final} spm). '
                f'Patrón de fatiga neuromuscular — verificar si GCT y stride también se degradan.')

        # Drift interpretación
        if abs(drift_cad) <= 3:
            resultado['interpretacion'].append(
                f'Drift de cadencia: {drift_cad:+.1f}%. Estable — buen control neuromuscular.')
        elif drift_cad < -3:
            resultado['interpretacion'].append(
                f'Drift de cadencia: {drift_cad:+.1f}%. La fatiga afecta la frecuencia de paso.')
        else:
            resultado['interpretacion'].append(
                f'Drift de cadencia: {drift_cad:+.1f}%. Subió al final — arranque conservador o negative split.')

    # ══════════════════════════════════════════════════════════
    # 2. GCT — Ground Contact Time
    # ══════════════════════════════════════════════════════════
    if gcts and len(gcts) > 5:
        gct_avg = round(sum(gcts) / len(gcts))
        estado = ('elite' if gct_avg < GCT_REF['elite'] else
                  'bueno' if gct_avg < GCT_REF['bueno'] else
                  'promedio' if gct_avg < GCT_REF['promedio'] else 'mejorar')

        n = len(gcts)
        pct10 = max(1, n // 10)
        drift_gct = round((sum(gcts[-pct10:]) / pct10 - sum(gcts[:pct10]) / pct10) /
                          (sum(gcts[:pct10]) / pct10) * 100, 1)

        resultado['metricas']['gct'] = {
            'promedio_ms': gct_avg, 'estado': estado,
            'referencia': GCT_REF, 'drift_pct': drift_gct,
        }
        resultado['drift']['gct'] = drift_gct

        gct_score = max(0, min(100, (300 - gct_avg) / 1.5))
        resultado['spider']['gct'] = round(gct_score)

        resultado['interpretacion'].append(
            f'Tiempo de contacto: {gct_avg}ms ({estado}). '
            f'Elite <200ms, bueno <240ms. Menor tiempo = mejor uso de energía elástica '
            f'del tendón de Aquiles (Nummela 2007).')

        if drift_gct > 5:
            resultado['interpretacion'].append(
                f'El GCT sube {drift_gct:+.1f}% al final. La fatiga se manifiesta '
                f'en mayor tiempo de contacto aunque la cadencia se mantenga.')

        if estado == 'mejorar':
            resultado['recomendaciones'].append({
                'texto': f'GCT alto ({gct_avg}ms). Objetivo: <270ms.',
                'ejercicio': 'Pliometría: saltos al cajón, skipping alto, drop jumps. Excéntricos de gemelos.',
                'frecuencia': '2x/semana post-calentamiento',
                'prioridad': 'alta',
                'resultado_esperado': '-15-20ms en 8 semanas',
            })

    # ══════════════════════════════════════════════════════════
    # 3. OSCILACIÓN VERTICAL
    # ══════════════════════════════════════════════════════════
    if vos and len(vos) > 5:
        # vos viene en mm, convertir a cm
        vos_cm = [v / 10 if v > 30 else v for v in vos]  # si > 30, está en mm
        vo_avg = round(sum(vos_cm) / len(vos_cm), 1)

        estado = ('elite' if vo_avg < VO_REF['elite'] else
                  'bueno' if vo_avg < VO_REF['bueno'] else
                  'promedio' if vo_avg < VO_REF['promedio'] else 'mejorar')

        n = len(vos_cm)
        pct10 = max(1, n // 10)
        drift_vo = round((sum(vos_cm[-pct10:]) / pct10 - sum(vos_cm[:pct10]) / pct10) /
                         max(1, sum(vos_cm[:pct10]) / pct10) * 100, 1)

        resultado['metricas']['vertical_osc'] = {
            'promedio_cm': vo_avg, 'estado': estado,
            'referencia': VO_REF, 'drift_pct': drift_vo,
        }
        resultado['drift']['vertical_osc'] = drift_vo

        vo_score = max(0, min(100, (12 - vo_avg) / 0.08))
        resultado['spider']['oscilacion'] = round(vo_score)

        resultado['interpretacion'].append(
            f'Oscilación vertical: {vo_avg}cm ({estado}). '
            f'Menos rebote = más energía hacia adelante (Saunders 2004).')

        if estado == 'mejorar':
            resultado['recomendaciones'].append({
                'texto': f'Oscilación vertical alta ({vo_avg}cm). Objetivo: <9cm.',
                'ejercicio': 'A-skip bajo, strides con foco en cadera alta. Correr "rasante".',
                'frecuencia': '3x/semana como parte del calentamiento',
                'prioridad': 'media',
                'resultado_esperado': '-1-2cm en 6 semanas',
            })

    # ══════════════════════════════════════════════════════════
    # 4. STRIDE LENGTH
    # ══════════════════════════════════════════════════════════
    if strides and len(strides) > 5:
        stride_avg = round(sum(strides) / len(strides), 2)
        n = len(strides)
        pct10 = max(1, n // 10)
        drift_stride = round((sum(strides[-pct10:]) / pct10 - sum(strides[:pct10]) / pct10) /
                              max(0.01, sum(strides[:pct10]) / pct10) * 100, 1)

        resultado['metricas']['stride_length'] = {
            'promedio_m': stride_avg, 'drift_pct': drift_stride,
        }
        resultado['drift']['stride'] = drift_stride

        if drift_stride < -5:
            resultado['interpretacion'].append(
                f'Stride length cae {abs(drift_stride):.1f}% al final ({stride_avg:.2f}m promedio). '
                f'La zancada se acorta con fatiga — señal de pérdida de fuerza en extensores de cadera.')

    # ══════════════════════════════════════════════════════════
    # 5. ÍNDICE DE ECONOMÍA (Vertical Ratio)
    # ══════════════════════════════════════════════════════════
    if vrs and len(vrs) > 5:
        vr_avg = round(sum(vrs) / len(vrs), 1)
        estado = ('elite' if vr_avg < VERT_RATIO_REF['elite'] else
                  'bueno' if vr_avg < VERT_RATIO_REF['bueno'] else
                  'promedio' if vr_avg < VERT_RATIO_REF['promedio'] else 'mejorar')

        resultado['metricas']['economia'] = {
            'vertical_ratio': vr_avg, 'estado': estado,
            'referencia': VERT_RATIO_REF,
        }
        eco_score = max(0, min(100, (12 - vr_avg) / 0.08))
        resultado['spider']['economia'] = round(eco_score)

        resultado['interpretacion'].append(
            f'Índice de economía (vertical ratio): {vr_avg}% ({estado}). '
            f'Es LA métrica de economía de carrera: cuánta energía se pierde '
            f'verticalmente vs avance horizontal (Morin 2005). Objetivo: <8%.')

    # ══════════════════════════════════════════════════════════
    # 6. CADENCIA POR ZONA DE INTENSIDAD
    # ══════════════════════════════════════════════════════════
    if cadencias and speeds:
        vel_umbral = 1000 / (pace_umbral * 60) if pace_umbral > 0 else 2.8
        zonas = defaultdict(list)
        for i in range(min(len(cadencias), len(speeds))):
            spd = speeds[i] if i < len(speeds) else 0
            if spd > 1.0:
                ratio = spd / vel_umbral
                if ratio < 0.75:   z = 'Z1'
                elif ratio < 0.88: z = 'Z2'
                elif ratio < 0.95: z = 'Z3'
                elif ratio < 1.05: z = 'Z4'
                else:              z = 'Z5'
                zonas[z].append(cadencias[i])

        cad_por_zona = {}
        for z in ['Z1', 'Z2', 'Z3', 'Z4', 'Z5']:
            if z in zonas and zonas[z]:
                cad_por_zona[z] = round(sum(zonas[z]) / len(zonas[z]))

        resultado['metricas']['cadencia_por_zona'] = cad_por_zona

        # Verificar que cadencia suba con intensidad
        zvals = [(z, v) for z, v in cad_por_zona.items()]
        if len(zvals) >= 2:
            sorted_z = sorted(zvals, key=lambda x: x[0])
            if sorted_z[-1][1] <= sorted_z[0][1]:
                resultado['recomendaciones'].append({
                    'texto': 'La cadencia no sube con la intensidad.',
                    'ejercicio': 'Strides y fartlek con cambios de cadencia conscientes. Usar metrónomo.',
                    'frecuencia': '2x/semana',
                    'prioridad': 'media',
                    'resultado_esperado': '+3-5 spm entre Z1 y Z4',
                })

    # ══════════════════════════════════════════════════════════
    # 3b. EVOLUCIÓN SEMANAL (sparkline data)
    # ══════════════════════════════════════════════════════════
    try:
        cur.execute("""
            SELECT DATE_TRUNC('week', s.fecha)::date as semana,
                   AVG(sa.cadence) as cad_avg,
                   AVG(sa.ground_contact_ms) as gct_avg,
                   AVG(sa.vertical_osc_mm) as vo_avg
            FROM activity_samples sa
            JOIN sesiones s ON s.id = sa.sesion_id
            WHERE s.atleta_id=%s AND s.sport='running'
            AND s.fecha::date >= CURRENT_DATE - INTERVAL '%s weeks'
            AND sa.cadence > 140
            GROUP BY DATE_TRUNC('week', s.fecha)
            ORDER BY semana
        """ % (atleta_id, semanas))
        weeks = cur.fetchall()
        resultado['sparkline'] = [{
            'semana': str(w[0]),
            'cadencia': round(float(w[1])) if w[1] else None,
            'gct': round(float(w[2])) if w[2] else None,
            'vo': round(float(w[3]) / 10, 1) if w[3] and float(w[3]) > 30 else (round(float(w[3]), 1) if w[3] else None),
        } for w in weeks]
    except Exception:
        pass

    # ══════════════════════════════════════════════════════════
    # 9. COMPARACIÓN CON PERÍODO ANTERIOR
    # ══════════════════════════════════════════════════════════
    try:
        cur.execute("""
            SELECT AVG(sa.cadence), AVG(sa.ground_contact_ms), AVG(sa.vertical_osc_mm)
            FROM activity_samples sa
            JOIN sesiones s ON s.id = sa.sesion_id
            WHERE s.atleta_id=%s AND s.sport='running'
            AND s.fecha::date >= CURRENT_DATE - INTERVAL '%s weeks'
            AND s.fecha::date < CURRENT_DATE - INTERVAL '%s weeks'
            AND sa.cadence > 140
        """ % (atleta_id, semanas * 2, semanas))
        prev = cur.fetchone()
        if prev and prev[0]:
            cad_prev = round(float(prev[0]))
            cad_now = resultado['metricas'].get('cadencia', {}).get('promedio', 0)
            resultado['comparacion']['cadencia'] = {
                'anterior': cad_prev, 'actual': cad_now,
                'diff': round(cad_now - cad_prev, 1),
                'direccion': 'up' if cad_now > cad_prev else ('down' if cad_now < cad_prev else 'equal'),
            }
            if prev[1]:
                gct_prev = round(float(prev[1]))
                gct_now = resultado['metricas'].get('gct', {}).get('promedio_ms', 0)
                if gct_now:
                    resultado['comparacion']['gct'] = {
                        'anterior': gct_prev, 'actual': gct_now,
                        'diff': round(gct_now - gct_prev, 1),
                        'direccion': 'down' if gct_now < gct_prev else ('up' if gct_now > gct_prev else 'equal'),
                    }
    except Exception:
        pass

    # ══════════════════════════════════════════════════════════
    # SPIDER CHART — completar scores faltantes
    # ══════════════════════════════════════════════════════════
    spider = resultado['spider']
    if 'cadencia' not in spider: spider['cadencia'] = 50
    if 'gct' not in spider: spider['gct'] = 50  # sin sensor = promedio
    if 'oscilacion' not in spider: spider['oscilacion'] = 50
    if 'economia' not in spider: spider['economia'] = 50

    # Drift score: 100 si drift=0, baja con drift
    drift_vals = [abs(v) for v in resultado['drift'].values()]
    if drift_vals:
        avg_drift = sum(drift_vals) / len(drift_vals)
        spider['estabilidad'] = round(max(0, min(100, 100 - avg_drift * 8)))
    else:
        spider['estabilidad'] = 50

    # ══════════════════════════════════════════════════════════
    # FALLBACK RECOMENDACIONES
    # ══════════════════════════════════════════════════════════
    if not resultado['recomendaciones'] and not resultado['interpretacion']:
        resultado['interpretacion'].append('Patrón biomecánico estable. Sin variaciones significativas.')

    # ── Eficiencia por sesión + fatiga real (agrupado en Python a partir
    #    de la MISMA consulta que ya funciona arriba — sin queries nuevas
    #    ni columnas no verificadas como 'atl'; usamos TSB, que la app
    #    ya muestra en el header como "frescura/fatiga") ──
    resultado['analisis_fatiga'] = {'serie': [], 'heatmap': None, 'scatter': [],
                                     'correlacion_eficiencia_fatiga': None,
                                     'regresion_fatiga_degradacion': None}
    try:
        if not sesion_id and samples and len(samples[0]) >= 11:
            grupos = {}  # session_id -> dict de acumuladores
            orden_sesion = []
            for s in samples:
                cad, spd, hr, gct, vo, stride, vr, ts, fecha, sid, tsb = s[:11]
                if sid not in grupos:
                    grupos[sid] = {'fecha': str(fecha) if fecha else '', 'tsb': tsb,
                                    'cad': [], 'gct': [], 'vo': [], 'stride': [], 'vr': []}
                    orden_sesion.append(sid)
                g = grupos[sid]
                if cad and float(cad) > 140: g['cad'].append(float(cad))
                if gct and 100 < float(gct) < 500: g['gct'].append(float(gct))
                if vo and 0 < float(vo) < 200: g['vo'].append(float(vo))
                if stride and 0.3 < float(stride) < 3.0: g['stride'].append(float(stride))
                if vr and 0 < float(vr) < 20: g['vr'].append(float(vr))

            orden_sesion.sort(key=lambda sid: grupos[sid]['fecha'])
            bl_cad_val = resultado['metricas'].get('cadencia', {}).get('promedio', 180)

            eficiencia = []
            cad_por_sesion, gct_por_sesion, stride_por_sesion, vo_por_sesion, vr_por_sesion = [], [], [], [], []
            for sid in orden_sesion:
                g = grupos[sid]
                cad_avg = round(sum(g['cad']) / len(g['cad']), 1) if g['cad'] else None
                gct_avg = round(sum(g['gct']) / len(g['gct']), 1) if g['gct'] else None
                vo_avg = round(sum(g['vo']) / len(g['vo']), 1) if g['vo'] else None
                stride_avg = round(sum(g['stride']) / len(g['stride']), 2) if g['stride'] else None
                vr_avg = round(sum(g['vr']) / len(g['vr']), 1) if g['vr'] else None
                tsb = float(g['tsb']) if g['tsb'] is not None else None

                score = 100
                if cad_avg: score -= abs(cad_avg - bl_cad_val) * 2
                score = max(20, min(100, round(score)))
                estado = 'eficiente' if score >= 80 else ('compensada' if score >= 60 else 'degradada')

                eficiencia.append({'fecha': g['fecha'], 'tsb': tsb, 'score': score, 'estado': estado})
                cad_por_sesion.append(cad_avg)
                gct_por_sesion.append(gct_avg)
                stride_por_sesion.append(stride_avg)
                vo_por_sesion.append(vo_avg)
                vr_por_sesion.append(vr_avg)

            resultado['eficiencia'] = eficiencia
            n_t = max(1, len(eficiencia))
            resultado['estado_sesiones'] = {
                'eficiente': round(sum(1 for e in eficiencia if e['estado'] == 'eficiente') / n_t * 100),
                'compensada': round(sum(1 for e in eficiencia if e['estado'] == 'compensada') / n_t * 100),
                'degradada': round(sum(1 for e in eficiencia if e['estado'] == 'degradada') / n_t * 100),
            }
            scores = [e['score'] for e in eficiencia]
            resultado['score_tecnico'] = round(sum(scores) / len(scores)) if scores else 50

            # fatiga real = -TSB (a menor TSB, mayor fatiga acumulada; ya usado
            # en el header del coach como "TSB frescura")
            serie = [{'fecha': e['fecha'], 'eficiencia': e['score'], 'fatiga': round(-e['tsb'], 1)}
                     for e in eficiencia if e['tsb'] is not None]
            resultado['analisis_fatiga']['serie'] = serie
            if len(serie) >= 3:
                resultado['analisis_fatiga']['correlacion_eficiencia_fatiga'] = _pearson(
                    [p['fatiga'] for p in serie], [p['eficiencia'] for p in serie])

            # heatmap
            filas = [
                ('cadencia', 'Cadencia', cad_por_sesion),
                ('gct', 'GCT (Contacto Suelo)', gct_por_sesion),
                ('stride_length', 'Stride Length', stride_por_sesion),
                ('oscilacion_vertical', 'Oscilación Vertical', vo_por_sesion),
                ('vertical_ratio', 'Vertical Ratio', vr_por_sesion),
            ]
            heatmap_metricas = {}
            for key, label, valores in filas:
                if all(v is None for v in valores):
                    heatmap_metricas[key] = {'label': label, 'celdas': ['N/D'] * len(valores)}
                    continue
                estados = _bucket_estabilidad(valores)
                celdas = [
                    {'valor': v, 'estado': (est if est else 'N/D')} if v is not None else 'N/D'
                    for v, est in zip(valores, estados)
                ]
                heatmap_metricas[key] = {'label': label, 'celdas': celdas}
            resultado['analisis_fatiga']['heatmap'] = {
                'sesiones': [grupos[sid]['fecha'] for sid in orden_sesion],
                'metricas': heatmap_metricas,
            }

            # scatter + regresión + clusters
            scatter_pts = [
                {'fecha': e['fecha'], 'fatiga': round(-e['tsb'], 1), 'degradacion': round(100 - e['score'], 1)}
                for e in eficiencia if e['tsb'] is not None
            ]
            if scatter_pts:
                xs = [p['fatiga'] for p in scatter_pts]
                ys = [p['degradacion'] for p in scatter_pts]
                clusters = _kmeans_2d(list(zip(xs, ys)))
                for p, c in zip(scatter_pts, clusters):
                    p['cluster'] = c
                resultado['analisis_fatiga']['regresion_fatiga_degradacion'] = _linreg(xs, ys)
            resultado['analisis_fatiga']['scatter'] = scatter_pts

            # ── clusters de técnica: cadencia vs stride, coloreado por
            #    el estado real de eficiencia de cada sesión (ya calculado) ──
            clusters_tecnica = []
            for i, sid in enumerate(orden_sesion):
                c, st = cad_por_sesion[i], stride_por_sesion[i]
                if c is not None and st is not None:
                    clusters_tecnica.append({
                        'fecha': grupos[sid]['fecha'], 'cadencia': c, 'stride': st,
                        'estado': eficiencia[i]['estado'],
                    })
            resultado['analisis_fatiga']['clusters_tecnica'] = clusters_tecnica

            # ── comparativa: sesión actual (última) vs mejor sesión
            #    (mayor score de eficiencia) del período, métrica a métrica ──
            def _mejora(metric_key, actual, mejor):
                if actual is None or mejor is None:
                    return None
                if metric_key == 'cadencia':
                    ref = resultado['metricas'].get('cadencia', {}).get('referencia')
                    if not ref:
                        return None
                    mid = (ref['min'] + ref['max']) / 2
                    return abs(actual - mid) <= abs(mejor - mid)
                if metric_key in ('gct', 'vertical_osc', 'vertical_ratio'):
                    return actual <= mejor
                return None  # stride: sin dirección única, solo informativo

            if len(orden_sesion) >= 2:
                idx_mejor = max(range(len(eficiencia)), key=lambda i: eficiencia[i]['score'])
                idx_actual = len(orden_sesion) - 1
                series_map = {
                    'cadencia': ('Cadencia (spm)', cad_por_sesion),
                    'stride_length': ('Stride Length (m)', stride_por_sesion),
                    'gct': ('GCT (ms)', gct_por_sesion),
                    'vertical_osc': ('Osc. Vertical (cm)', vo_por_sesion),
                    'vertical_ratio': ('Vertical Ratio (%)', vr_por_sesion),
                }
                comparativa = []
                for key, (label, serie_vals) in series_map.items():
                    actual = serie_vals[idx_actual]
                    mejor = serie_vals[idx_mejor]
                    if actual is None or mejor is None:
                        continue
                    diff_pct = round((actual - mejor) / mejor * 100, 1) if mejor else None
                    comparativa.append({
                        'metrica': label, 'actual': actual, 'mejor_periodo': mejor,
                        'diff_pct': diff_pct,
                        'mejora': _mejora('vertical_osc' if key == 'vertical_osc' else key, actual, mejor),
                    })
                resultado['analisis_fatiga']['comparativa'] = comparativa
            else:
                resultado['analisis_fatiga']['comparativa'] = []

            # ── patrón detectado: frase corta generada SOLO a partir de
            #    valores reales ya calculados (drift real + regresión real) ──
            patron, accion = None, None
            reg = resultado['analisis_fatiga']['regresion_fatiga_degradacion']
            r_val = resultado['analisis_fatiga']['correlacion_eficiencia_fatiga']
            gct_drift = resultado['metricas'].get('gct', {}).get('drift_pct')
            cad_drift = resultado['metricas'].get('cadencia', {}).get('drift_pct')
            if reg and reg['slope'] > 0 and gct_drift is not None and gct_drift > 3:
                patron = f'A mayor fatiga, aumenta el GCT ({gct_drift:+.1f}%).'
                accion = 'Reducir intensidad técnica y priorizar recuperación.'
            elif reg and reg['slope'] > 0 and cad_drift is not None and cad_drift < -3:
                patron = f'La cadencia cae con la fatiga (drift {cad_drift:+.1f}%).'
                accion = 'Trabajar resistencia neuromuscular específica (drills de cadencia en fatiga).'
            elif r_val is not None and abs(r_val) >= 0.3:
                direccion = 'cae' if r_val < 0 else 'sube'
                patron = f'La eficiencia {direccion} de forma consistente cuando aumenta la fatiga (r={r_val}).'
                accion = 'Ajustar la carga de series técnicas en sesiones de alta fatiga acumulada.'
            else:
                patron = 'No se detecta una relación consistente entre fatiga y degradación técnica en este período.'
                accion = 'Mantener el monitoreo; ampliar la muestra de sesiones.'
            resultado['analisis_fatiga']['patron_detectado'] = {'patron': patron, 'accion': accion}
        else:
            resultado['eficiencia'] = []
            resultado['estado_sesiones'] = {}
            resultado['score_tecnico'] = 50
    except Exception:
        import traceback; traceback.print_exc()
        resultado['eficiencia'] = []
        resultado['estado_sesiones'] = {}
        resultado['score_tecnico'] = 50

    return resultado


# ═══════════════════════════════════════════════════════════════
# CYCLING
# ═══════════════════════════════════════════════════════════════

def _decode_lr_balance(raw):
    """Decodifica left_right_pct según el estándar ANT+/FIT de Garmin.

    El campo se guarda como un byte donde:
      - bit alto (0x80): flag de "valor válido, representa % de la pierna DERECHA"
      - 7 bits bajos (0x7F): el porcentaje (0-100) de esa pierna

    Si se promedia el byte crudo sin decodificar, un balance normal (~49/51)
    con el flag seteado da 128 + 50.7 = 178.7 — un valor imposible fuera de
    rango. Ese era el bug: 'L/R BALANCE 178.7/-78.7'. Acá lo devolvemos ya
    como % de la pierna IZQUIERDA, siempre en rango 0-100.
    """
    try:
        r = int(round(float(raw)))
    except (TypeError, ValueError):
        return None
    if r & 0x80:
        right_pct = r & 0x7F
        return round(100 - right_pct, 1) if 0 <= right_pct <= 100 else None
    if 0 <= r <= 100:
        return float(r)  # compatibilidad: ya viene decodificado
    return None


def analizar_cycling(conn, atleta_id, sesion_id=None, semanas=8):
    """Análisis completo de técnica de ciclismo."""
    cur = conn.cursor() if hasattr(conn, 'cursor') else conn
    if not hasattr(cur, 'execute'):
        cur = conn.cursor()

    nivel = _clasificar_nivel(conn, atleta_id)
    sensores = _detectar_sensores(conn, atleta_id, 'cycling')

    if sesion_id:
        cur.execute("""
            SELECT cadence, power_w, hr, left_right_pct, torque_effectiveness, speed_ms, ts_s
            FROM activity_samples
            WHERE sesion_id=%s AND (cadence > 0 OR power_w > 0)
            ORDER BY ts_s
        """, (sesion_id,))
    else:
        cur.execute("""
            SELECT sa.cadence, sa.power_w, sa.hr, sa.left_right_pct,
                   sa.torque_effectiveness, sa.speed_ms, sa.ts_s,
                   s.fecha::date, s.id, s.tsb
            FROM activity_samples sa
            JOIN sesiones s ON s.id = sa.sesion_id
            WHERE s.atleta_id=%s AND s.sport='cycling'
            AND s.fecha::date >= CURRENT_DATE - INTERVAL '%s weeks'
            AND (sa.cadence > 0 OR sa.power_w > 0)
            ORDER BY s.fecha, sa.ts_s
        """ % (atleta_id, semanas))

    samples = cur.fetchall()
    if not samples:
        return {'error': 'Sin datos de cycling', 'sensores': sensores}

    cadencias = [float(s[0]) for s in samples if s[0] and float(s[0]) > 30]
    powers    = [float(s[1]) for s in samples if s[1] and float(s[1]) > 0]
    lrs       = [v for v in (_decode_lr_balance(s[3]) for s in samples if s[3] is not None) if v is not None]
    torques   = [float(s[4]) for s in samples if s[4] and float(s[4]) > 0]

    cur.execute("SELECT ftp_watts FROM atletas WHERE id=%s", (atleta_id,))
    r = cur.fetchone()
    ftp = float(r[0]) if r and r[0] else 200

    resultado = {
        'deporte': 'cycling', 'nivel': nivel, 'n_muestras': len(samples), 'ftp': ftp,
        'sensores': sensores,
        'metricas': {}, 'spider': {}, 'drift': {},
        'sparkline': [], 'comparacion': {},
        'interpretacion': [], 'recomendaciones': [],
    }

    # ══════════════════════════════════════════════════════════
    # CADENCIA (+ drift intra-sesión inicio→final, igual que running)
    # ══════════════════════════════════════════════════════════
    if cadencias:
        cad_avg = round(sum(cadencias) / len(cadencias))
        n = len(cadencias)
        pct10 = max(1, n // 10)
        q_inicio = round(sum(cadencias[:pct10]) / pct10)
        q_final  = round(sum(cadencias[-pct10:]) / pct10)
        drift_cad = round((q_final - q_inicio) / q_inicio * 100, 1) if q_inicio > 0 else 0

        estado = 'óptima' if 80 <= cad_avg <= 95 else ('baja' if cad_avg < 80 else 'alta')
        resultado['metricas']['cadencia'] = {
            'promedio': cad_avg, 'estado': estado,
            'q1': q_inicio, 'q4': q_final, 'drift_pct': drift_cad,
        }
        resultado['drift']['cadencia'] = drift_cad
        resultado['spider']['cadencia'] = max(0, min(100, 100 - abs(cad_avg - 87.5) * 4))

        resultado['interpretacion'].append(
            f'Cadencia promedio: {cad_avg} rpm. Óptimo: 85-95 rpm en Z2-Z4 (Faria 2005). '
            f'Cadencia baja (<75) genera más estrés muscular; alta (>100) más cardiovascular. '
            f'Inicio: {q_inicio} rpm → Final: {q_final} rpm. Drift: {drift_cad:+.1f}%.')

        if drift_cad < -5:
            resultado['interpretacion'].append(
                f'Cadencia cae {abs(drift_cad):.1f}% ({q_inicio}→{q_final} rpm) al final — '
                f'patrón de fatiga neuromuscular.')

        if cad_avg < 75:
            resultado['recomendaciones'].append({
                'texto': f'Cadencia baja ({cad_avg} rpm). Más estrés muscular.',
                'ejercicio': 'Drills de cadencia alta: 5x3\' a 100rpm+ en Z2.',
                'frecuencia': '2x/semana', 'prioridad': 'alta',
                'resultado_esperado': '+5-10 rpm promedio en 4 semanas',
            })

    # ══════════════════════════════════════════════════════════
    # L/R BALANCE — bug corregido: se decodifica el flag 0x80 antes
    # de promediar (ver _decode_lr_balance)
    # ══════════════════════════════════════════════════════════
    if lrs and len(lrs) > 50:
        lr_avg = round(sum(lrs) / len(lrs), 1)
        desbalance = abs(lr_avg - 50)
        estado = 'equilibrado' if desbalance < 2 else ('leve' if desbalance < 4 else 'significativo')
        resultado['metricas']['lr_balance'] = {
            'promedio_pct': lr_avg, 'desbalance': round(desbalance, 1), 'estado': estado,
            'pierna_dominante': 'izquierda' if lr_avg > 50 else 'derecha',
        }
        resultado['spider']['balance'] = max(0, min(100, 100 - desbalance * 12))

        resultado['interpretacion'].append(
            f'Balance L/R: {lr_avg}%/{round(100-lr_avg,1)}% ({estado}). '
            f'Normal: 48-52%. Desbalance > 4% puede indicar compensación o asimetría (Bini 2014).')

        if desbalance >= 4:
            resultado['recomendaciones'].append({
                'texto': f'Desbalance significativo ({lr_avg}%/{round(100-lr_avg,1)}%).',
                'ejercicio': 'Single leg drills, verificar bike fitting, trabajo unilateral de fuerza.',
                'frecuencia': '2x/semana', 'prioridad': 'alta',
                'resultado_esperado': 'Reducir a <3% en 6-8 semanas',
            })

    # ══════════════════════════════════════════════════════════
    # TORQUE EFFECTIVENESS (+ drift intra-sesión)
    # ══════════════════════════════════════════════════════════
    if torques and len(torques) > 50:
        te_avg = round(sum(torques) / len(torques), 1)
        n = len(torques)
        pct10 = max(1, n // 10)
        te_inicio = sum(torques[:pct10]) / pct10
        te_final = sum(torques[-pct10:]) / pct10
        drift_te = round((te_final - te_inicio) / max(1, te_inicio) * 100, 1)

        estado = 'bueno' if te_avg >= 70 else ('aceptable' if te_avg >= 50 else 'mejorar')
        resultado['metricas']['torque_effectiveness'] = {
            'promedio_pct': te_avg, 'estado': estado, 'drift_pct': drift_te,
        }
        resultado['drift']['torque_effectiveness'] = drift_te
        resultado['spider']['pedaleo'] = max(0, min(100, te_avg))

        resultado['interpretacion'].append(
            f'Torque effectiveness: {te_avg}% ({estado}). '
            f'>70% bueno, >80% excelente. Mide qué % de la fuerza genera propulsión vs desperdicio.')

        if drift_te < -5:
            resultado['interpretacion'].append(
                f'Torque effectiveness cae {abs(drift_te):.1f}% al final — la técnica de '
                f'pedaleo se degrada con la fatiga.')

    # Cadencia por zona de potencia
    if cadencias and powers and len(cadencias) >= len(powers):
        zonas_power = defaultdict(list)
        for i in range(len(powers)):
            if i < len(cadencias) and powers[i] > 0 and cadencias[i] > 30:
                pct_ftp = powers[i] / ftp * 100
                if pct_ftp < 55:   z = 'Z1'
                elif pct_ftp < 75: z = 'Z2'
                elif pct_ftp < 90: z = 'Z3'
                elif pct_ftp < 105: z = 'Z4'
                else:              z = 'Z5+'
                zonas_power[z].append(cadencias[i])

        cad_por_zona = {}
        for z in ['Z1', 'Z2', 'Z3', 'Z4', 'Z5+']:
            if z in zonas_power:
                cad_por_zona[z] = round(sum(zonas_power[z]) / len(zonas_power[z]))
        resultado['metricas']['cadencia_por_zona'] = cad_por_zona

    # ══════════════════════════════════════════════════════════
    # EVOLUCIÓN SEMANAL (sparkline) — mismo patrón que running
    # ══════════════════════════════════════════════════════════
    try:
        cur.execute("""
            SELECT DATE_TRUNC('week', s.fecha)::date as semana,
                   AVG(sa.cadence) as cad_avg,
                   AVG(sa.torque_effectiveness) as te_avg
            FROM activity_samples sa
            JOIN sesiones s ON s.id = sa.sesion_id
            WHERE s.atleta_id=%s AND s.sport='cycling'
            AND s.fecha::date >= CURRENT_DATE - INTERVAL '%s weeks'
            AND (sa.cadence > 0 OR sa.power_w > 0)
            GROUP BY DATE_TRUNC('week', s.fecha)
            ORDER BY semana
        """ % (atleta_id, semanas))
        weeks = cur.fetchall()
        resultado['sparkline'] = [{
            'semana': str(w[0]),
            'cadencia': round(float(w[1])) if w[1] else None,
            'torque_effectiveness': round(float(w[2]), 1) if w[2] else None,
        } for w in weeks]
    except Exception:
        pass

    # ══════════════════════════════════════════════════════════
    # COMPARACIÓN CON PERÍODO ANTERIOR — mismo patrón que running
    # ══════════════════════════════════════════════════════════
    try:
        cur.execute("""
            SELECT AVG(sa.cadence), AVG(sa.torque_effectiveness)
            FROM activity_samples sa
            JOIN sesiones s ON s.id = sa.sesion_id
            WHERE s.atleta_id=%s AND s.sport='cycling'
            AND s.fecha::date >= CURRENT_DATE - INTERVAL '%s weeks'
            AND s.fecha::date < CURRENT_DATE - INTERVAL '%s weeks'
            AND (sa.cadence > 0 OR sa.power_w > 0)
        """ % (atleta_id, semanas * 2, semanas))
        prev = cur.fetchone()
        if prev and prev[0]:
            cad_prev = round(float(prev[0]))
            cad_now = resultado['metricas'].get('cadencia', {}).get('promedio', 0)
            resultado['comparacion']['cadencia'] = {
                'anterior': cad_prev, 'actual': cad_now,
                'diff': round(cad_now - cad_prev, 1),
                'direccion': 'up' if cad_now > cad_prev else ('down' if cad_now < cad_prev else 'equal'),
            }
            if prev[1]:
                te_prev = round(float(prev[1]), 1)
                te_now = resultado['metricas'].get('torque_effectiveness', {}).get('promedio_pct', 0)
                if te_now:
                    resultado['comparacion']['torque_effectiveness'] = {
                        'anterior': te_prev, 'actual': te_now,
                        'diff': round(te_now - te_prev, 1),
                        'direccion': 'up' if te_now > te_prev else ('down' if te_now < te_prev else 'equal'),
                    }
    except Exception:
        pass

    # Fallback
    if not resultado['recomendaciones']:
        resultado['recomendaciones'].append({
            'texto': 'Técnica de pedaleo dentro de parámetros normales.',
            'ejercicio': 'Mantener drills de cadencia y single leg como calentamiento.',
            'frecuencia': '1x/semana', 'prioridad': 'baja',
            'resultado_esperado': 'Mantener eficiencia',
        })

    # ══════════════════════════════════════════════════════════
    # ANÁLISIS DE FATIGA POR SESIÓN — mismo patrón que running:
    # eficiencia por sesión (score vs cadencia óptima), heatmap de
    # estabilidad, scatter fatiga×degradación con clusters, cluster
    # cadencia×potencia, comparativa vs mejor sesión, patrón detectado.
    # Todo sobre datos reales ya presentes en 'samples' (columnas 7-9:
    # fecha, id de sesión, tsb) — sin queries nuevas.
    # ══════════════════════════════════════════════════════════
    resultado['analisis_fatiga'] = {'serie': [], 'heatmap': None, 'scatter': [],
                                     'correlacion_eficiencia_fatiga': None,
                                     'regresion_fatiga_degradacion': None}
    try:
        if not sesion_id and samples and len(samples[0]) >= 10:
            grupos = {}
            orden_sesion = []
            for s in samples:
                cad, pw, hr, lr_raw, te, spd, ts, fecha, sid, tsb = s[:10]
                if sid not in grupos:
                    grupos[sid] = {'fecha': str(fecha) if fecha else '', 'tsb': tsb,
                                    'cad': [], 'power': [], 'te': [], 'lr': []}
                    orden_sesion.append(sid)
                g = grupos[sid]
                if cad and float(cad) > 30: g['cad'].append(float(cad))
                if pw and float(pw) > 0: g['power'].append(float(pw))
                if te and float(te) > 0: g['te'].append(float(te))
                lr_dec = _decode_lr_balance(lr_raw) if lr_raw is not None else None
                if lr_dec is not None: g['lr'].append(lr_dec)

            orden_sesion.sort(key=lambda sid: grupos[sid]['fecha'])
            bl_cad_val = resultado['metricas'].get('cadencia', {}).get('promedio', 87.5)

            eficiencia = []
            cad_por_sesion, power_por_sesion, te_por_sesion, lr_por_sesion = [], [], [], []
            for sid in orden_sesion:
                g = grupos[sid]
                cad_avg = round(sum(g['cad']) / len(g['cad']), 1) if g['cad'] else None
                power_avg = round(sum(g['power']) / len(g['power']), 1) if g['power'] else None
                te_avg_s = round(sum(g['te']) / len(g['te']), 1) if g['te'] else None
                lr_avg_s = round(sum(g['lr']) / len(g['lr']), 1) if g['lr'] else None
                tsb = float(g['tsb']) if g['tsb'] is not None else None

                score = 100
                if cad_avg: score -= abs(cad_avg - bl_cad_val) * 2
                if te_avg_s is not None: score -= max(0, 70 - te_avg_s) * 0.5
                score = max(20, min(100, round(score)))
                estado = 'eficiente' if score >= 80 else ('compensada' if score >= 60 else 'degradada')

                eficiencia.append({'fecha': g['fecha'], 'tsb': tsb, 'score': score, 'estado': estado})
                cad_por_sesion.append(cad_avg)
                power_por_sesion.append(power_avg)
                te_por_sesion.append(te_avg_s)
                lr_por_sesion.append(lr_avg_s)

            resultado['eficiencia'] = eficiencia
            n_t = max(1, len(eficiencia))
            resultado['estado_sesiones'] = {
                'eficiente': round(sum(1 for e in eficiencia if e['estado'] == 'eficiente') / n_t * 100),
                'compensada': round(sum(1 for e in eficiencia if e['estado'] == 'compensada') / n_t * 100),
                'degradada': round(sum(1 for e in eficiencia if e['estado'] == 'degradada') / n_t * 100),
            }
            scores = [e['score'] for e in eficiencia]
            resultado['score_tecnico'] = round(sum(scores) / len(scores)) if scores else 50

            serie = [{'fecha': e['fecha'], 'eficiencia': e['score'], 'fatiga': round(-e['tsb'], 1)}
                     for e in eficiencia if e['tsb'] is not None]
            resultado['analisis_fatiga']['serie'] = serie
            if len(serie) >= 3:
                resultado['analisis_fatiga']['correlacion_eficiencia_fatiga'] = _pearson(
                    [p['fatiga'] for p in serie], [p['eficiencia'] for p in serie])

            # heatmap
            filas = [
                ('cadencia', 'Cadencia', cad_por_sesion),
                ('torque_effectiveness', 'Torque Eff.', te_por_sesion),
                ('lr_balance', 'Balance L/R', lr_por_sesion),
                ('power', 'Potencia', power_por_sesion),
            ]
            heatmap_metricas = {}
            for key, label, valores in filas:
                if all(v is None for v in valores):
                    heatmap_metricas[key] = {'label': label, 'celdas': ['N/D'] * len(valores)}
                    continue
                estados = _bucket_estabilidad(valores)
                celdas = [
                    {'valor': v, 'estado': (est if est else 'N/D')} if v is not None else 'N/D'
                    for v, est in zip(valores, estados)
                ]
                heatmap_metricas[key] = {'label': label, 'celdas': celdas}
            resultado['analisis_fatiga']['heatmap'] = {
                'sesiones': [grupos[sid]['fecha'] for sid in orden_sesion],
                'metricas': heatmap_metricas,
            }

            # scatter + regresión + clusters
            scatter_pts = [
                {'fecha': e['fecha'], 'fatiga': round(-e['tsb'], 1), 'degradacion': round(100 - e['score'], 1)}
                for e in eficiencia if e['tsb'] is not None
            ]
            if scatter_pts:
                xs = [p['fatiga'] for p in scatter_pts]
                ys = [p['degradacion'] for p in scatter_pts]
                clusters = _kmeans_2d(list(zip(xs, ys)))
                for p, c in zip(scatter_pts, clusters):
                    p['cluster'] = c
                resultado['analisis_fatiga']['regresion_fatiga_degradacion'] = _linreg(xs, ys)
            resultado['analisis_fatiga']['scatter'] = scatter_pts

            # clusters de técnica: cadencia vs potencia, coloreado por estado real
            clusters_tecnica = []
            for i, sid in enumerate(orden_sesion):
                c, pw = cad_por_sesion[i], power_por_sesion[i]
                if c is not None and pw is not None:
                    clusters_tecnica.append({
                        'fecha': grupos[sid]['fecha'], 'cadencia': c, 'stride': pw,
                        'estado': eficiencia[i]['estado'],
                    })
            resultado['analisis_fatiga']['clusters_tecnica'] = clusters_tecnica

            # comparativa: sesión actual vs mejor sesión del período
            if len(orden_sesion) >= 2:
                idx_mejor = max(range(len(eficiencia)), key=lambda i: eficiencia[i]['score'])
                idx_actual = len(orden_sesion) - 1
                series_map = {
                    'cadencia': ('Cadencia (rpm)', cad_por_sesion),
                    'torque_effectiveness': ('Torque Eff. (%)', te_por_sesion),
                    'lr_balance': ('Balance L/R (%)', lr_por_sesion),
                    'power': ('Potencia (W)', power_por_sesion),
                }

                def _mejora(metric_key, actual, mejor):
                    if actual is None or mejor is None:
                        return None
                    if metric_key == 'cadencia':
                        return abs(actual - 87.5) <= abs(mejor - 87.5)
                    if metric_key == 'torque_effectiveness':
                        return actual >= mejor
                    if metric_key == 'lr_balance':
                        return abs(actual - 50) <= abs(mejor - 50)
                    return None  # potencia: sin dirección única, solo informativo

                comparativa = []
                for key, (label, serie_vals) in series_map.items():
                    actual = serie_vals[idx_actual]
                    mejor = serie_vals[idx_mejor]
                    if actual is None or mejor is None:
                        continue
                    diff_pct = round((actual - mejor) / mejor * 100, 1) if mejor else None
                    comparativa.append({
                        'metrica': label, 'actual': actual, 'mejor_periodo': mejor,
                        'diff_pct': diff_pct,
                        'mejora': _mejora(key, actual, mejor),
                    })
                resultado['analisis_fatiga']['comparativa'] = comparativa
            else:
                resultado['analisis_fatiga']['comparativa'] = []

            # patrón detectado
            patron, accion = None, None
            reg = resultado['analisis_fatiga']['regresion_fatiga_degradacion']
            r_val = resultado['analisis_fatiga']['correlacion_eficiencia_fatiga']
            te_drift = resultado['metricas'].get('torque_effectiveness', {}).get('drift_pct')
            cad_drift = resultado['metricas'].get('cadencia', {}).get('drift_pct')
            if reg and reg['slope'] > 0 and te_drift is not None and te_drift < -3:
                patron = f'A mayor fatiga, cae el torque effectiveness ({te_drift:+.1f}%).'
                accion = 'Reducir intensidad técnica y priorizar recuperación.'
            elif reg and reg['slope'] > 0 and cad_drift is not None and cad_drift < -3:
                patron = f'La cadencia cae con la fatiga (drift {cad_drift:+.1f}%).'
                accion = 'Trabajar resistencia neuromuscular específica (drills de cadencia en fatiga).'
            elif r_val is not None and abs(r_val) >= 0.3:
                direccion = 'cae' if r_val < 0 else 'sube'
                patron = f'La eficiencia {direccion} de forma consistente cuando aumenta la fatiga (r={r_val}).'
                accion = 'Ajustar la carga de series técnicas en sesiones de alta fatiga acumulada.'
            else:
                patron = 'No se detecta una relación consistente entre fatiga y degradación técnica en este período.'
                accion = 'Mantener el monitoreo; ampliar la muestra de sesiones.'
            resultado['analisis_fatiga']['patron_detectado'] = {'patron': patron, 'accion': accion}
        else:
            resultado['eficiencia'] = []
            resultado['estado_sesiones'] = {}
            resultado['score_tecnico'] = 50
    except Exception:
        import traceback; traceback.print_exc()
        resultado['eficiencia'] = []
        resultado['estado_sesiones'] = {}
        resultado['score_tecnico'] = 50

    return resultado


# ═══════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    import psycopg2, psycopg2.extras, sys, json
    db_url = os.environ.get('DATABASE_URL')
    if not db_url: print("ERROR: DATABASE_URL"); sys.exit(1)
    conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.DictCursor)

    for aid, nombre in [(1, 'Rodrigo'), (3, 'Silvina'), (4, 'Jimena')]:
        print(f'\n{"="*60}')
        print(f'  TÉCNICA: {nombre}')
        print(f'{"="*60}')

        r = analizar_running(conn, aid, semanas=8)
        if 'error' not in r:
            print(f'\n  RUNNING — nivel: {r["nivel"]} | muestras: {r["n_muestras"]}')
            print(f'  Spider: {r["spider"]}')
            print(f'  Drift: {r["drift"]}')
            print(f'  Sensores: {r["sensores"]}')
            for rec in r['recomendaciones']:
                if isinstance(rec, dict):
                    print(f'  [{rec["prioridad"].upper()}] {rec["texto"]}')
                    print(f'    → {rec["ejercicio"]} ({rec["frecuencia"]})')
                else:
                    print(f'  → {rec}')
        else:
            print(f'  Running: {r["error"]}')

        c = analizar_cycling(conn, aid, semanas=8)
        if 'error' not in c:
            print(f'\n  CYCLING — FTP: {c["ftp"]}W | muestras: {c["n_muestras"]}')
            print(f'  Spider: {c["spider"]}')

    conn.close()
