"""
noah_cerebro.py — Inteligencia central de NOAH
================================================
Se llama desde ciclo_semanal.py entre optimizer y patrones_sesion.
Toma el estado del atleta y decide QUE entrenar y CON QUE dosificacion.

FLUJO:
  Optimizer (TSS, fase, carrera)
    → noah_cerebro.decidir_semana() ← ESTE ARCHIVO
      → patrones_sesion (construye bloques)
        → Intel (narra)
          → Aprendizaje (evalua)

4 FUNCIONES:
  1. evaluar_atleta() — diagnostico completo desde datos reales
  2. decidir_foco() — que sistema atacar esta semana
  3. elegir_dosificacion() — sesiones concretas con repeticiones, pausas, intensidad
  4. aprender() — comparar prescripcion vs resultado

REGLAS NO NEGOCIABLES (fisiologia humana):
  - Max 2-3 sesiones Z4+ por semana (Seiler 2010)
  - Min 75% del volumen en Z1-Z2
  - 48h entre sesiones intensas del mismo tipo
  - Ramp rate max 7% semanal (Gabbett 2016)
  - Descanso obligatorio con Hanna < 25
  - Progresion antes de intensidad para principiantes
  - Taper: vol -40-60%, mantener intensidad (Mujika 2003)

REFERENCIAS:
  Banister 1975, Coggan 2003, Coyle 1984, Seiler 2010, Billat 2001,
  Paavolainen 1999, Gabbett 2016, Mujika 2003, Plews 2013, Bompa 2009
"""

from datetime import date, timedelta
from collections import defaultdict

SISTEMAS = ['aerobico_central', 'aerobico_periferico', 'umbral', 'neuromuscular', 'anaerobico']

# Que zona trabaja que sistema (Seiler 2010, Issurin 2008)
ESTIMULO_ZONA = {
    1: {'aerobico_central':.4,'aerobico_periferico':.3,'umbral':.0,'neuromuscular':.0,'anaerobico':.0},
    2: {'aerobico_central':.8,'aerobico_periferico':.7,'umbral':.1,'neuromuscular':.0,'anaerobico':.0},
    3: {'aerobico_central':.5,'aerobico_periferico':.8,'umbral':.7,'neuromuscular':.2,'anaerobico':.1},
    4: {'aerobico_central':.3,'aerobico_periferico':.6,'umbral':1.,'neuromuscular':.5,'anaerobico':.3},
    5: {'aerobico_central':.2,'aerobico_periferico':.3,'umbral':.6,'neuromuscular':.9,'anaerobico':.8},
    6: {'aerobico_central':.1,'aerobico_periferico':.1,'umbral':.2,'neuromuscular':1.,'anaerobico':1.},
}

# Importancia de cada sistema por carrera (Joyner & Coyle 2008)
PESOS_CARRERA = {
    '5K':      {'aerobico_central':.20,'aerobico_periferico':.20,'umbral':.25,'neuromuscular':.20,'anaerobico':.15},
    '10K':     {'aerobico_central':.25,'aerobico_periferico':.25,'umbral':.25,'neuromuscular':.15,'anaerobico':.10},
    '21K':     {'aerobico_central':.30,'aerobico_periferico':.30,'umbral':.25,'neuromuscular':.10,'anaerobico':.05},
    'maraton': {'aerobico_central':.35,'aerobico_periferico':.30,'umbral':.25,'neuromuscular':.08,'anaerobico':.02},
    'sprint':  {'aerobico_central':.20,'aerobico_periferico':.25,'umbral':.25,'neuromuscular':.18,'anaerobico':.12},
    'olimpico':{'aerobico_central':.25,'aerobico_periferico':.30,'umbral':.25,'neuromuscular':.12,'anaerobico':.08},
    '70.3':    {'aerobico_central':.30,'aerobico_periferico':.30,'umbral':.25,'neuromuscular':.10,'anaerobico':.05},
    'ironman': {'aerobico_central':.35,'aerobico_periferico':.30,'umbral':.25,'neuromuscular':.08,'anaerobico':.02},
    'mtb':     {'aerobico_central':.20,'aerobico_periferico':.25,'umbral':.20,'neuromuscular':.20,'anaerobico':.15},
}

# ═══════════════════════════════════════════════════════════════
# FUNCION 1: EVALUAR AL ATLETA (datos reales)
# ═══════════════════════════════════════════════════════════════

def evaluar_atleta(conn, atleta_id, semanas=6):
    """
    Diagnostico completo desde datos reales.
    Retorna: sistemas (nivel 0-100), tendencias, readiness, historial de respuesta.
    """
    cur = conn.cursor()
    fecha_desde = (date.today() - timedelta(days=semanas * 7)).isoformat()

    # ── Sesiones recientes ──
    cur.execute("""
        SELECT fecha, sport, tss_total, duration_min, hr_avg, ctl, atl,
               tipo_sesion, tss_z12, tss_z34, tss_z56
        FROM sesiones
        WHERE atleta_id=%s AND fecha >= %s AND duration_min > 5
        ORDER BY fecha
    """, (atleta_id, fecha_desde))
    sesiones = cur.fetchall()

    # ── Biomarcadores recientes ──
    cur.execute("""
        SELECT fecha, hrv_rmssd, hanna_life, sleep_h, fc_nocturna
        FROM sleep_hrv
        WHERE atleta_id=%s AND fecha >= %s
        ORDER BY fecha
    """, (atleta_id, fecha_desde))
    bio = cur.fetchall()

    # ── Atleta ──
    cur.execute("""
        SELECT lthr_run, lthr_bike, ftp_watts, pace_umbral_run, deporte_ppal,
               anos_entrenamiento, ctl, atl
        FROM atletas a
        LEFT JOIN LATERAL (
            SELECT ctl, atl FROM sesiones WHERE atleta_id=a.id AND ctl IS NOT NULL
            ORDER BY fecha DESC LIMIT 1
        ) s ON true
        WHERE a.id=%s
    """, (atleta_id,))
    atleta_row = cur.fetchone()

    if not sesiones:
        return _evaluacion_default()

    # ── Calcular nivel de cada sistema desde las zonas de entrenamiento ──
    sistemas = {s: 30.0 for s in SISTEMAS}  # Base
    total_tss = sum(float(s[2] or 0) for s in sesiones)
    total_dur = sum(float(s[3] or 0) for s in sesiones)

    # Cuanto tiempo paso en cada zona (proxy desde tss_z12, tss_z34, tss_z56)
    tss_z12_total = sum(float(s[8] or 0) for s in sesiones)
    tss_z34_total = sum(float(s[9] or 0) for s in sesiones)
    tss_z56_total = sum(float(s[10] or 0) for s in sesiones)
    tss_zonas_total = tss_z12_total + tss_z34_total + tss_z56_total

    if tss_zonas_total > 0:
        pct_z12 = tss_z12_total / tss_zonas_total
        pct_z34 = tss_z34_total / tss_zonas_total
        pct_z56 = tss_z56_total / tss_zonas_total

        # Nivel de cada sistema basado en cuanto se estimulo
        # Z1-Z2 estimula aerobico central y periferico
        sistemas['aerobico_central'] = min(90, 30 + pct_z12 * 60 + total_dur / 100)
        sistemas['aerobico_periferico'] = min(90, 25 + pct_z12 * 50 + pct_z34 * 30)
        # Z3-Z4 estimula umbral
        sistemas['umbral'] = min(90, 20 + pct_z34 * 80)
        # Z5-Z6 estimula neuromuscular y anaerobico
        sistemas['neuromuscular'] = min(90, 20 + pct_z56 * 90)
        sistemas['anaerobico'] = min(90, 15 + pct_z56 * 95)

    # ── Tendencias (ultimas 3 sem vs anteriores 3 sem) ──
    mitad = len(sesiones) // 2
    tendencias = {}
    if mitad > 0:
        tss_primera = sum(float(s[2] or 0) for s in sesiones[:mitad]) / mitad
        tss_segunda = sum(float(s[2] or 0) for s in sesiones[mitad:]) / max(1, len(sesiones)-mitad)
        tendencias['carga'] = 'subiendo' if tss_segunda > tss_primera * 1.05 else (
            'bajando' if tss_segunda < tss_primera * 0.95 else 'estable')

    # ── FTP/pace tendencia ──
    cur.execute("""
        SELECT ftp_watts, pace_umbral_run FROM atletas WHERE id=%s
    """, (atleta_id,))
    at = cur.fetchone()
    ftp = float(at[0]) if at and at[0] else None
    pace = float(at[1]) if at and at[1] else None

    # ── Readiness ──
    hanna_actual = None
    hrv_actual = None
    sueno_actual = None
    if bio:
        ultimo_bio = bio[-1]
        hanna_actual = float(ultimo_bio[2]) if ultimo_bio[2] else None
        hrv_actual = float(ultimo_bio[1]) if ultimo_bio[1] else None
        sueno_actual = float(ultimo_bio[3]) if ultimo_bio[3] else None

    readiness = 'alto'
    if hanna_actual is not None:
        if hanna_actual < 25: readiness = 'critico'
        elif hanna_actual < 40: readiness = 'bajo'
        elif hanna_actual < 55: readiness = 'medio'

    # ── Historial de respuesta (que funciono y que no) ──
    respuesta = _analizar_respuesta(sesiones, bio)

    # ── CTL/ATL actual ──
    ctl_actual = float(atleta_row[6]) if atleta_row and atleta_row[6] else None
    atl_actual = float(atleta_row[7]) if atleta_row and atleta_row[7] else None
    tsb = (ctl_actual - atl_actual) if ctl_actual and atl_actual else None

    return {
        'sistemas': sistemas,
        'tendencias': tendencias,
        'readiness': readiness,
        'hanna': hanna_actual,
        'hrv': hrv_actual,
        'sueno': sueno_actual,
        'ctl': ctl_actual,
        'atl': atl_actual,
        'tsb': tsb,
        'ftp': ftp,
        'pace_umbral': pace,
        'n_sesiones': len(sesiones),
        'tss_semanal_avg': round(total_tss / max(1, semanas)),
        'pct_z12': round(pct_z12 * 100, 1) if tss_zonas_total > 0 else None,
        'pct_z34': round(pct_z34 * 100, 1) if tss_zonas_total > 0 else None,
        'pct_z56': round(pct_z56 * 100, 1) if tss_zonas_total > 0 else None,
        'respuesta_individual': respuesta,
    }


def _analizar_respuesta(sesiones, bio):
    """Analiza que tipo de sesion produjo mejores resultados."""
    # Simplificado: comparar semanas con mas Z4+ vs semanas con mas Z2
    # y ver cuales produjeron mayor delta CTL
    respuesta = {
        'responde_mejor_a': 'volumen',  # default
        'z4_efectivo': True,
        'z5_efectivo': True,
        'max_calidad_semanal': 3,
    }

    # Si hay sesiones con Z5-Z6 y el CTL no subio, Z5 no es efectivo
    sesiones_z56 = [s for s in sesiones if float(s[10] or 0) > 10]
    if sesiones_z56 and len(sesiones_z56) >= 3:
        ctl_pre = float(sesiones_z56[0][5] or 0)
        ctl_post = float(sesiones_z56[-1][5] or 0)
        if ctl_post <= ctl_pre:
            respuesta['z5_efectivo'] = False
            respuesta['responde_mejor_a'] = 'volumen'
        else:
            respuesta['responde_mejor_a'] = 'intensidad'

    return respuesta


def _evaluacion_default():
    return {
        'sistemas': {s: 40.0 for s in SISTEMAS},
        'tendencias': {}, 'readiness': 'medio',
        'hanna': None, 'hrv': None, 'sueno': None,
        'ctl': None, 'atl': None, 'tsb': None,
        'ftp': None, 'pace_umbral': None,
        'n_sesiones': 0, 'tss_semanal_avg': 0,
        'pct_z12': None, 'pct_z34': None, 'pct_z56': None,
        'respuesta_individual': {},
    }


# ═══════════════════════════════════════════════════════════════
# FUNCION 2: DECIDIR EL FOCO DE LA SEMANA
# ═══════════════════════════════════════════════════════════════

def decidir_foco(evaluacion, fase, carrera_tipo, tss_objetivo):
    """
    Decide QUE entrenar esta semana.
    Retorna: limitante, n_sesiones_calidad, zona_calidad, explicacion
    """
    sistemas = evaluacion['sistemas']
    readiness = evaluacion['readiness']

    # ── Regla NO NEGOCIABLE: descanso con readiness critico ──
    if readiness == 'critico':
        return {
            'limitante': 'recuperacion',
            'n_calidad': 0,
            'zona_calidad': 0,
            'foco': 'DESCANSO TOTAL — Hanna critico, el cuerpo necesita recuperar',
            'explicacion': 'No prescribir carga. Descanso activo o total. '
                          'Un dia de descanso vale mas que 3 de carga reducida.',
            'tss_ajustado': 0,
        }

    # ── Identificar limitante ──
    pesos = PESOS_CARRERA.get(carrera_tipo, {s: 0.2 for s in SISTEMAS})
    deficits = {s: (100 - sistemas[s]) * pesos.get(s, 0.2) for s in SISTEMAS}
    limitante = max(deficits, key=deficits.get)

    # ── Regla: max sesiones calidad segun readiness (Seiler 2010) ──
    max_calidad = {'alto': 3, 'medio': 2, 'bajo': 1, 'critico': 0}
    n_calidad = max_calidad[readiness]

    # ── Regla: principiante (CTL < 25) no hace Z5 las primeras semanas ──
    ctl = evaluacion.get('ctl') or 0
    zona_map = {
        'aerobico_central': 2, 'aerobico_periferico': 3,
        'umbral': 4, 'neuromuscular': 5, 'anaerobico': 6}
    zona = zona_map.get(limitante, 4)

    if ctl < 25 and zona >= 5:
        zona = 3  # Principiante: Z3 maximo
        limitante = 'aerobico_periferico'

    # ── Regla: fase R reduce calidad ──
    if fase == 'R':
        n_calidad = min(n_calidad, 1)
        tss_objetivo = round(tss_objetivo * 0.70)

    # ── Regla: taper mantiene intensidad baja volumen ──
    if fase == 'Taper':
        n_calidad = min(n_calidad, 2)
        tss_objetivo = round(tss_objetivo * 0.55)

    # ── Explicacion ──
    nombres_sist = {
        'aerobico_central': 'capacidad cardiovascular (corazon)',
        'aerobico_periferico': 'capacidad aerobica muscular (mitocondrias)',
        'umbral': 'umbral de lactato (FTP/pace)',
        'neuromuscular': 'potencia neuromuscular (economia)',
        'anaerobico': 'tolerancia anaerobica (W\'bal)',
    }
    desc_zona = {2:'Z2 largo', 3:'Z3 tempo', 4:'Z4 sweet spot', 5:'Z5 intervalos', 6:'Z6 repeticiones'}

    explicacion = (
        f'Limitante: {nombres_sist.get(limitante, limitante)} '
        f'(nivel {sistemas[limitante]:.0f}/100). '
        f'Foco: {n_calidad} sesiones de calidad en {desc_zona.get(zona, f"Z{zona}")}. '
        f'Resto Z1-Z2.'
    )

    return {
        'limitante': limitante,
        'n_calidad': n_calidad,
        'zona_calidad': zona,
        'foco': f'{limitante} → {desc_zona.get(zona, f"Z{zona}")}',
        'explicacion': explicacion,
        'tss_ajustado': tss_objetivo,
    }


# ═══════════════════════════════════════════════════════════════
# FUNCION 3: ELEGIR DOSIFICACION
# ═══════════════════════════════════════════════════════════════

# Base de dosificaciones por limitante × zona
# Cada una tiene: reps, duracion, pausa, descripcion
DOSIFICACIONES = {
    'umbral': {
        'A': [
            {'desc': 'Sweet spot progresivo', 'zona': 'Z3-Z4', 'reps': 2, 'dur_min': 20, 'pausa_min': 5, 'activa': True},
            {'desc': 'Tempo sostenido', 'zona': 'Z3', 'reps': 1, 'dur_min': 30, 'pausa_min': 0, 'activa': True},
        ],
        'T': [
            {'desc': 'Intervalos umbral', 'zona': 'Z4', 'reps': 4, 'dur_min': 8, 'pausa_min': 3, 'activa': True},
            {'desc': 'Cruise intervals', 'zona': 'Z4', 'reps': 3, 'dur_min': 12, 'pausa_min': 3, 'activa': True},
            {'desc': 'Over-under', 'zona': 'Z3-Z4', 'reps': 5, 'dur_min': 6, 'pausa_min': 2, 'activa': True},
        ],
        'R': [
            {'desc': 'Recordatorio umbral', 'zona': 'Z3-Z4', 'reps': 2, 'dur_min': 8, 'pausa_min': 5, 'activa': True},
        ],
    },
    'aerobico_central': {
        'A': [
            {'desc': 'Fondo largo Z2', 'zona': 'Z2', 'reps': 1, 'dur_min': 90, 'pausa_min': 0, 'activa': False},
            {'desc': 'Fondo largo Z1-Z2', 'zona': 'Z1-Z2', 'reps': 1, 'dur_min': 120, 'pausa_min': 0, 'activa': False},
        ],
        'T': [
            {'desc': 'Fondo medio con cierre Z3', 'zona': 'Z2', 'reps': 1, 'dur_min': 60, 'pausa_min': 0, 'activa': False},
        ],
        'R': [
            {'desc': 'Fondo corto regenerativo', 'zona': 'Z1', 'reps': 1, 'dur_min': 40, 'pausa_min': 0, 'activa': False},
        ],
    },
    'aerobico_periferico': {
        'A': [
            {'desc': 'Tempo Z2-Z3 progresivo', 'zona': 'Z2', 'reps': 1, 'dur_min': 50, 'pausa_min': 0, 'activa': False},
        ],
        'T': [
            {'desc': 'Intervalos Z3', 'zona': 'Z3', 'reps': 3, 'dur_min': 15, 'pausa_min': 3, 'activa': True},
            {'desc': 'Fartlek Z2/Z3', 'zona': 'Z3', 'reps': 6, 'dur_min': 5, 'pausa_min': 3, 'activa': True},
        ],
        'R': [
            {'desc': 'Z2 suave', 'zona': 'Z2', 'reps': 1, 'dur_min': 40, 'pausa_min': 0, 'activa': False},
        ],
    },
    'neuromuscular': {
        'A': [
            {'desc': 'Strides al final de Z2', 'zona': 'Z5', 'reps': 6, 'dur_min': 0.5, 'pausa_min': 1.5, 'activa': True},
        ],
        'T': [
            {'desc': 'Series 1000m', 'zona': 'Z5', 'reps': 5, 'dur_min': 4, 'pausa_min': 2.5, 'activa': True},
            {'desc': 'Series 600m', 'zona': 'Z5', 'reps': 8, 'dur_min': 2.5, 'pausa_min': 2.5, 'activa': True},
            {'desc': 'Cuestas cortas', 'zona': 'Z5', 'reps': 8, 'dur_min': 1.5, 'pausa_min': 3, 'activa': True},
        ],
        'R': [
            {'desc': 'Activaciones cortas', 'zona': 'Z5', 'reps': 4, 'dur_min': 0.5, 'pausa_min': 2, 'activa': True},
        ],
    },
    'anaerobico': {
        'A': [
            {'desc': 'No priorizar en A', 'zona': 'Z2', 'reps': 1, 'dur_min': 45, 'pausa_min': 0, 'activa': False},
        ],
        'T': [
            {'desc': 'Repeticiones 400m', 'zona': 'Z6', 'reps': 8, 'dur_min': 1.5, 'pausa_min': 3, 'activa': False},
            {'desc': 'Repeticiones 200m', 'zona': 'Z6', 'reps': 10, 'dur_min': 0.75, 'pausa_min': 3, 'activa': False},
        ],
        'R': [
            {'desc': 'Descanso', 'zona': 'Z1', 'reps': 0, 'dur_min': 0, 'pausa_min': 0, 'activa': False},
        ],
    },
}


def elegir_dosificacion(limitante, fase, respuesta_individual=None):
    """
    Elige la dosificacion optima para la limitante y la fase.
    Si hay historial de respuesta, prioriza lo que funciono.
    """
    opciones = DOSIFICACIONES.get(limitante, DOSIFICACIONES['umbral'])
    fase_key = fase if fase in opciones else 'A'
    dosis_disponibles = opciones[fase_key]

    if not dosis_disponibles:
        return DOSIFICACIONES['aerobico_periferico']['A'][0]

    # Si hay respuesta individual, priorizar lo que funciono
    if respuesta_individual:
        if not respuesta_individual.get('z5_efectivo', True) and limitante == 'neuromuscular':
            # Z5 no funciona para este atleta, buscar alternativa Z3-Z4
            dosis_disponibles = DOSIFICACIONES['umbral'][fase_key]

    # Por ahora elegir la primera opcion (despues el ML elige la mejor)
    return dosis_disponibles[0]


# ═══════════════════════════════════════════════════════════════
# FUNCION 4: APRENDER
# ═══════════════════════════════════════════════════════════════

def aprender(conn, atleta_id, semana_pasada_fecha):
    """
    Compara la prescripcion de la semana pasada con lo que paso.
    Retorna: que funciono, que no, ajustes para la proxima.
    """
    cur = conn.cursor()
    fecha_fin = (date.fromisoformat(str(semana_pasada_fecha)) + timedelta(days=7)).isoformat()

    # Que se prescribio
    cur.execute("""
        SELECT datos FROM prescripciones
        WHERE atleta_id=%s AND semana_id=%s
        ORDER BY id DESC LIMIT 1
    """, (atleta_id, f"{date.fromisoformat(str(semana_pasada_fecha)).year}-W{date.fromisoformat(str(semana_pasada_fecha)).isocalendar()[1]:02d}"))
    presc = cur.fetchone()

    # Que hizo realmente
    cur.execute("""
        SELECT sport, tss_total, duration_min, hr_avg, tipo_sesion
        FROM sesiones
        WHERE atleta_id=%s AND fecha >= %s AND fecha < %s
        ORDER BY fecha
    """, (atleta_id, str(semana_pasada_fecha), fecha_fin))
    reales = cur.fetchall()

    # CTL antes y despues
    cur.execute("""
        SELECT ctl FROM sesiones
        WHERE atleta_id=%s AND fecha < %s AND ctl IS NOT NULL
        ORDER BY fecha DESC LIMIT 1
    """, (atleta_id, str(semana_pasada_fecha)))
    ctl_antes = cur.fetchone()

    cur.execute("""
        SELECT ctl FROM sesiones
        WHERE atleta_id=%s AND fecha >= %s AND fecha < %s AND ctl IS NOT NULL
        ORDER BY fecha DESC LIMIT 1
    """, (atleta_id, str(semana_pasada_fecha), fecha_fin))
    ctl_despues = cur.fetchone()

    delta_ctl = None
    if ctl_antes and ctl_despues and ctl_antes[0] and ctl_despues[0]:
        delta_ctl = round(float(ctl_despues[0]) - float(ctl_antes[0]), 2)

    return {
        'prescripto': presc[0] if presc else None,
        'sesiones_reales': len(reales),
        'tss_real': round(sum(float(r[1] or 0) for r in reales)),
        'delta_ctl': delta_ctl,
        'mejoro': delta_ctl > 0 if delta_ctl is not None else None,
    }


# ═══════════════════════════════════════════════════════════════
# FUNCION PRINCIPAL: DECIDIR SEMANA COMPLETA
# ═══════════════════════════════════════════════════════════════

def decidir_semana(conn, atleta_id, fase, carrera_tipo, tss_objetivo):
    """
    Funcion principal que se llama desde ciclo_semanal.py.
    Retorna todo lo que patrones_sesion necesita para armar las sesiones.
    """
    # 1. Evaluar
    evaluacion = evaluar_atleta(conn, atleta_id)

    # 2. Decidir foco
    foco = decidir_foco(evaluacion, fase, carrera_tipo, tss_objetivo)

    # 3. Elegir dosificacion
    dosificacion = elegir_dosificacion(
        foco['limitante'], fase,
        evaluacion.get('respuesta_individual'))

    # 4. Aprender de la semana pasada
    try:
        aprendizaje = aprender(conn, atleta_id,
            (date.today() - timedelta(days=7)).isoformat())
    except Exception:
        aprendizaje = None

    # Imprimir decision
    print(f'\n  [CEREBRO NOAH]')
    print(f'    Readiness: {evaluacion["readiness"]} (Hanna {evaluacion["hanna"]})')
    print(f'    Sistemas: {" | ".join(f"{s[:5]}={evaluacion["sistemas"][s]:.0f}" for s in SISTEMAS)}')
    print(f'    {foco["explicacion"]}')
    print(f'    Dosificacion: {dosificacion["desc"]} ({dosificacion["zona"]})')
    if dosificacion['reps'] > 1:
        print(f'    → {dosificacion["reps"]}×{dosificacion["dur_min"]}\' rec {dosificacion["pausa_min"]}\'')
    if aprendizaje and aprendizaje.get('delta_ctl') is not None:
        estado = '✓ funciono' if aprendizaje['mejoro'] else '✗ no mejoro'
        print(f'    Semana pasada: ΔCTL {aprendizaje["delta_ctl"]:+.2f} {estado}')

    return {
        'evaluacion': evaluacion,
        'foco': foco,
        'dosificacion': dosificacion,
        'aprendizaje': aprendizaje,
    }
