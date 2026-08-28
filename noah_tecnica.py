"""
noah_tecnica.py — Análisis biomecánico por deporte
=====================================================
RUNNING:
  - Cadencia óptima por zona de pace (180±5 spm para elite, Moore 2016)
  - Relación cadencia/pace (eficiencia: más rápido = más cadencia)
  - Cadencia drift (caída por fatiga, Williams & Cavanagh 1987)
  - Stride length vs speed (relación cuadrática, Weyand 2000)
  - GCT analysis (si hay datos: <250ms bueno, >300ms mejorar)
  - Vertical oscillation (<8cm bueno, >10cm ineficiente, Saunders 2004)

CYCLING:
  - L/R balance (50/50 ideal, >52/48 compensación, Bini 2014)
  - Torque effectiveness (>70% bueno, <50% pedaleo ineficiente)
  - Cadencia por zona de potencia (85-95rpm Z2-Z4, Faria 2005)
  - Power-cadence relationship (cadencia óptima para max potencia)

SWIMMING:
  - Stroke rate vs pace (SWOLF score, Toussaint 2006)
  - Eficiencia de brazada (distancia por brazada)
"""

import os, math
from collections import defaultdict

# ═══════════════════════════════════════════════════════════════
# RUNNING TECHNIQUE
# ═══════════════════════════════════════════════════════════════

# Cadencia óptima por nivel (Moore 2016, Heiderscheit 2011)
CADENCIA_REF = {
    'elite': {'min': 180, 'max': 190, 'desc': 'Elite: 180-190 spm'},
    'avanzado': {'min': 175, 'max': 185, 'desc': 'Avanzado: 175-185 spm'},
    'intermedio': {'min': 168, 'max': 178, 'desc': 'Intermedio: 168-178 spm'},
    'principiante': {'min': 160, 'max': 172, 'desc': 'Principiante: 160-172 spm'},
}

# GCT referencia (Nummela 2007)
GCT_REF = {'elite': 200, 'bueno': 240, 'promedio': 270, 'mejorar': 300}

# Vertical oscillation referencia (Saunders 2004)
VO_REF = {'elite': 6, 'bueno': 8, 'promedio': 9.5, 'mejorar': 11}


def analizar_running(conn, atleta_id, sesion_id=None, semanas=4):
    """
    Analiza técnica de running desde activity_samples.
    Si sesion_id es None, analiza últimas N semanas.
    """
    cur = conn.cursor()

    # Nivel del atleta por CTL
    cur.execute("SELECT ctl FROM sesiones WHERE atleta_id=%s AND ctl IS NOT NULL ORDER BY fecha DESC LIMIT 1", (atleta_id,))
    r = cur.fetchone()
    ctl = float(r[0]) if r and r[0] else 30
    if ctl >= 60: nivel = 'avanzado'
    elif ctl >= 40: nivel = 'intermedio'
    else: nivel = 'principiante'

    # Obtener samples
    if sesion_id:
        cur.execute("""
            SELECT cadence, speed_ms, hr, ground_contact_ms, vertical_osc_mm,
                   stride_length_m, vertical_ratio, ts_s
            FROM activity_samples
            WHERE sesion_id=%s AND cadence > 0
            ORDER BY ts_s
        """, (sesion_id,))
    else:
        cur.execute("""
            SELECT sa.cadence, sa.speed_ms, sa.hr, sa.ground_contact_ms, sa.vertical_osc_mm,
                   sa.stride_length_m, sa.vertical_ratio, sa.ts_s
            FROM activity_samples sa
            JOIN sesiones s ON s.id = sa.sesion_id
            WHERE s.atleta_id=%s AND s.sport='running'
            AND s.fecha::date >= CURRENT_DATE - INTERVAL '%s weeks'
            AND sa.cadence > 0
            ORDER BY s.fecha, sa.ts_s
        """ % (atleta_id, semanas))

    samples = cur.fetchall()
    if not samples:
        return {'error': 'Sin datos de running'}

    # Extraer datos
    cadencias = [float(s[0]) for s in samples if s[0] and float(s[0]) > 100]
    speeds = [float(s[1]) for s in samples if s[1] and float(s[1]) > 0.5]
    hrs = [float(s[2]) for s in samples if s[2] and float(s[2]) > 60]
    gcts = [float(s[3]) for s in samples if s[3] and float(s[3]) > 100]
    vos = [float(s[4]) for s in samples if s[4] and float(s[4]) > 0]
    strides = [float(s[5]) for s in samples if s[5] and float(s[5]) > 0.3]

    resultado = {
        'deporte': 'running',
        'nivel': nivel,
        'n_muestras': len(samples),
        'analisis': [],
        'metricas': {},
        'recomendaciones': [],
    }

    # ── 1. Cadencia ──
    if cadencias:
        cad_avg = round(sum(cadencias) / len(cadencias))
        cad_ref = CADENCIA_REF[nivel]

        # Cadencia por cuartos de la sesión (drift analysis)
        n = len(cadencias)
        q1 = round(sum(cadencias[:n//4]) / max(1, n//4))
        q4 = round(sum(cadencias[3*n//4:]) / max(1, n - 3*n//4))
        drift = round((q4 - q1) / q1 * 100, 1) if q1 > 0 else 0

        estado_cad = 'optima' if cad_ref['min'] <= cad_avg <= cad_ref['max'] else (
            'baja' if cad_avg < cad_ref['min'] else 'alta')

        resultado['metricas']['cadencia'] = {
            'promedio': cad_avg,
            'referencia': cad_ref,
            'estado': estado_cad,
            'drift_pct': drift,
            'q1': q1, 'q4': q4,
        }

        if estado_cad == 'baja':
            resultado['recomendaciones'].append(
                f'Cadencia baja ({cad_avg} spm). Objetivo: {cad_ref["min"]}-{cad_ref["max"]} spm. '
                f'Incluir drills de cadencia (strides, metrónomo) 2x/semana.')
        if drift < -3:
            resultado['recomendaciones'].append(
                f'Cadencia cae {abs(drift)}% al final de la sesión (fatiga neuromuscular). '
                f'Trabajar fuerza específica y economía de carrera.')

    # ── 2. Relación cadencia/pace (eficiencia) ──
    if cadencias and speeds:
        # Agrupar por zonas de velocidad
        zonas_vel = defaultdict(list)
        for i in range(min(len(cadencias), len(speeds))):
            pace = 1000 / speeds[i] / 60 if speeds[i] > 0.5 else 0
            if pace > 3 and pace < 10:
                if pace < 5: zona = 'rapido'
                elif pace < 6: zona = 'medio'
                else: zona = 'lento'
                zonas_vel[zona].append(cadencias[i])

        cad_por_zona = {}
        for z, cads in zonas_vel.items():
            cad_por_zona[z] = round(sum(cads) / len(cads)) if cads else 0

        resultado['metricas']['cadencia_por_pace'] = cad_por_zona

        # Eficiencia: la cadencia debe subir con el pace
        if 'rapido' in cad_por_zona and 'lento' in cad_por_zona:
            diff = cad_por_zona['rapido'] - cad_por_zona['lento']
            if diff < 3:
                resultado['recomendaciones'].append(
                    'Cadencia no aumenta con la velocidad. Falta respuesta neuromuscular. '
                    'Incluir strides y fartlek con cambios de cadencia.')

    # ── 3. GCT (si hay datos) ──
    if gcts and len(gcts) > 5:
        gct_avg = round(sum(gcts) / len(gcts))
        estado_gct = ('elite' if gct_avg < GCT_REF['elite'] else
                      'bueno' if gct_avg < GCT_REF['bueno'] else
                      'promedio' if gct_avg < GCT_REF['promedio'] else 'mejorar')
        resultado['metricas']['gct'] = {
            'promedio_ms': gct_avg,
            'estado': estado_gct,
            'referencia': GCT_REF,
        }
        if estado_gct == 'mejorar':
            resultado['recomendaciones'].append(
                f'Tiempo de contacto alto ({gct_avg}ms). Objetivo: <270ms. '
                f'Ejercicios de pliometría y fuerza reactiva (saltos, skipping).')

    # ── 4. Vertical oscillation (si hay datos) ──
    if vos and len(vos) > 5:
        vo_avg = round(sum(vos) / len(vos), 1)
        estado_vo = ('elite' if vo_avg < VO_REF['elite'] else
                     'bueno' if vo_avg < VO_REF['bueno'] else
                     'promedio' if vo_avg < VO_REF['promedio'] else 'mejorar')
        resultado['metricas']['vertical_osc'] = {
            'promedio_cm': vo_avg,
            'estado': estado_vo,
            'referencia': VO_REF,
        }
        if estado_vo == 'mejorar':
            resultado['recomendaciones'].append(
                f'Oscilación vertical alta ({vo_avg}cm). Objetivo: <9cm. '
                f'Correr más "pegado al piso". Strides enfocados en contacto rápido.')

    # ── 5. Stride length (si hay datos) ──
    if strides and len(strides) > 5:
        stride_avg = round(sum(strides) / len(strides), 2)
        resultado['metricas']['stride_length'] = {
            'promedio_m': stride_avg,
            'desc': f'{stride_avg}m por zancada',
        }

    if not resultado['recomendaciones']:
        resultado['recomendaciones'].append('Técnica dentro de parámetros normales para tu nivel.')

    return resultado


# ═══════════════════════════════════════════════════════════════
# CYCLING TECHNIQUE
# ═══════════════════════════════════════════════════════════════

def analizar_cycling(conn, atleta_id, sesion_id=None, semanas=4):
    """Analiza técnica de ciclismo."""
    cur = conn.cursor()

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
                   sa.torque_effectiveness, sa.speed_ms, sa.ts_s
            FROM activity_samples sa
            JOIN sesiones s ON s.id = sa.sesion_id
            WHERE s.atleta_id=%s AND s.sport='cycling'
            AND s.fecha::date >= CURRENT_DATE - INTERVAL '%s weeks'
            AND (sa.cadence > 0 OR sa.power_w > 0)
            ORDER BY s.fecha, sa.ts_s
        """ % (atleta_id, semanas))

    samples = cur.fetchall()
    if not samples:
        return {'error': 'Sin datos de cycling'}

    cadencias = [float(s[0]) for s in samples if s[0] and float(s[0]) > 30]
    powers = [float(s[1]) for s in samples if s[1] and float(s[1]) > 0]
    lrs = [float(s[3]) for s in samples if s[3] and float(s[3]) > 0]
    torques = [float(s[4]) for s in samples if s[4] and float(s[4]) > 0]

    # FTP del atleta
    cur.execute("SELECT ftp_watts FROM atletas WHERE id=%s", (atleta_id,))
    r = cur.fetchone()
    ftp = float(r[0]) if r and r[0] else 200

    resultado = {
        'deporte': 'cycling',
        'n_muestras': len(samples),
        'ftp': ftp,
        'analisis': [],
        'metricas': {},
        'recomendaciones': [],
    }

    # ── 1. Cadencia ──
    if cadencias:
        cad_avg = round(sum(cadencias) / len(cadencias))
        estado = 'optima' if 80 <= cad_avg <= 95 else ('baja' if cad_avg < 80 else 'alta')

        resultado['metricas']['cadencia'] = {
            'promedio': cad_avg,
            'estado': estado,
            'referencia': '80-95 rpm (Faria 2005)',
        }
        if cad_avg < 75:
            resultado['recomendaciones'].append(
                f'Cadencia baja ({cad_avg} rpm). Pedalear a <75rpm genera más estrés muscular. '
                f'Objetivo: 85-90rpm. Incluir drills de cadencia alta (100rpm+ en Z2).')

    # ── 2. L/R Balance ──
    if lrs and len(lrs) > 50:
        lr_avg = round(sum(lrs) / len(lrs), 1)
        desbalance = abs(lr_avg - 50)
        estado = 'equilibrado' if desbalance < 2 else ('leve' if desbalance < 4 else 'significativo')

        resultado['metricas']['lr_balance'] = {
            'promedio_pct': lr_avg,
            'desbalance': round(desbalance, 1),
            'estado': estado,
            'referencia': '48-52% normal (Bini 2014)',
            'pierna_dominante': 'izquierda' if lr_avg > 50 else 'derecha',
        }
        if desbalance >= 4:
            dom = 'izquierda' if lr_avg > 50 else 'derecha'
            resultado['recomendaciones'].append(
                f'Desbalance L/R significativo ({lr_avg}% / {round(100-lr_avg, 1)}%). '
                f'Pierna {dom} dominante. Incluir trabajo unilateral (single leg drills) '
                f'y verificar posición en la bici (bike fitting).')

    # ── 3. Torque Effectiveness ──
    if torques and len(torques) > 50:
        te_avg = round(sum(torques) / len(torques), 1)
        estado = 'bueno' if te_avg >= 70 else ('aceptable' if te_avg >= 50 else 'mejorar')

        resultado['metricas']['torque_effectiveness'] = {
            'promedio_pct': te_avg,
            'estado': estado,
            'referencia': '>70% bueno, >80% excelente',
        }
        if te_avg < 60:
            resultado['recomendaciones'].append(
                f'Torque effectiveness bajo ({te_avg}%). Pedaleo ineficiente — '
                f'mucha fuerza desperdiciada en el upstroke. '
                f'Drills de pedaleo redondo (single leg, scraping).')

    # ── 4. Cadencia por zona de potencia ──
    if cadencias and powers and len(cadencias) == len(powers):
        zonas_power = defaultdict(list)
        for i in range(len(powers)):
            if powers[i] > 0 and cadencias[i] > 30:
                pct_ftp = powers[i] / ftp * 100
                if pct_ftp < 55: z = 'Z1'
                elif pct_ftp < 75: z = 'Z2'
                elif pct_ftp < 90: z = 'Z3'
                elif pct_ftp < 105: z = 'Z4'
                else: z = 'Z5+'
                zonas_power[z].append(cadencias[i])

        cad_por_zona = {}
        for z in ['Z1','Z2','Z3','Z4','Z5+']:
            if z in zonas_power:
                cad_por_zona[z] = round(sum(zonas_power[z]) / len(zonas_power[z]))

        resultado['metricas']['cadencia_por_zona'] = cad_por_zona

    if not resultado['recomendaciones']:
        resultado['recomendaciones'].append('Técnica de pedaleo dentro de parámetros normales.')

    return resultado


# ═══════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    import psycopg2, psycopg2.extras, sys
    db_url = os.environ.get('DATABASE_URL')
    if not db_url: print("ERROR: DATABASE_URL"); sys.exit(1)
    conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.DictCursor)

    for aid, nombre in [(1,'Rodrigo'), (3,'Silvina'), (4,'Jimena')]:
        print(f'\n{"="*60}')
        print(f'  TÉCNICA: {nombre}')
        print(f'{"="*60}')

        # Running
        r = analizar_running(conn, aid, semanas=8)
        if 'error' not in r:
            print(f'\n  🏃 RUNNING ({r["n_muestras"]} muestras, nivel {r["nivel"]})')
            for k, v in r['metricas'].items():
                if isinstance(v, dict):
                    print(f'    {k}: {v.get("promedio", v.get("promedio_ms", v.get("promedio_cm", v.get("promedio_m", ""))))} — {v.get("estado", v.get("desc", ""))}')
                else:
                    print(f'    {k}: {v}')
            for rec in r['recomendaciones']:
                print(f'    → {rec}')

        # Cycling
        c = analizar_cycling(conn, aid, semanas=8)
        if 'error' not in c:
            print(f'\n  🚴 CYCLING ({c["n_muestras"]} muestras, FTP {c["ftp"]}W)')
            for k, v in c['metricas'].items():
                if isinstance(v, dict) and 'promedio' in str(v):
                    print(f'    {k}: {v.get("promedio", v.get("promedio_pct", ""))} — {v.get("estado", "")}')
                elif isinstance(v, dict):
                    print(f'    {k}: {v}')
            for rec in c['recomendaciones']:
                print(f'    → {rec}')

    conn.close()
