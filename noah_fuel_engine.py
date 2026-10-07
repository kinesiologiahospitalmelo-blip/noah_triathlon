"""
noah_fuel_engine.py — Motor NOAH Fuel v4 (reescritura completa — Sesión 6)
============================================================================
Reescrito de cero según TRASPASO_SESION_5.md. Reemplaza noah_fuel_engine.py
v3, que tenía heurísticas inventadas (`+0.5 si intensidad>=0.85`) y varias
queries a columnas que NO EXISTEN en la base real (fc_media_dia, calories,
deporte_principal) -- por eso el motor devolvía error en producción.

Verificado contra app.py / db_compat.py real (no contra el schema que
describía el traspaso, que tenía nombres de columna incorrectos):
  - atletas.deporte_ppal          (NO "deporte_principal")
  - sesiones.calorias             (NO "calories")
  - sleep_hrv NO tiene fc_media_dia -> NEAT se estima como % de TMB (ACSM),
    marcado explícitamente como estimación.
  - Sesión planificada de HOY se lee de prescripcion_bloques (igual que el
    endpoint /prescripcion que ya funciona), no de twin_predicciones -- el
    JSON interno de twin_predicciones.plan no está confirmado en los
    archivos disponibles, así que no se asume su forma. Se puede conectar
    en una iteración futura con noah_twin_v2.py a la vista.
  - atletas.objetivo, atletas.body_fat_pct y las tablas nutricion_log /
    atleta_preferencias no existen todavía -> se crean en app.py con
    _init_nutricion_tables() (mismo patrón que _init_auth_tables()) y acá
    se leen siempre con fallback si no están.

DISEÑO (2 niveles, igual que v3, pero con datos reales):
  nivel1 ("hoy")   -> kcal, macros en g/kg, 5-6 comidas con alimentos REALES
                      en gramos + medida casera, suplementos, hidratación,
                      alertas. Nada de "sin dato": si falta algo, se estima
                      y se marca, o no se muestra.
  nivel2 ("porque")-> gasto desglosado, protocolo citado por fuente,
                      Energy Availability (RED-S), ajustes por biomarcador,
                      recuperación de ayer, carrera próxima / taper.

FUENTES: Mifflin-St Jeor 1990 [TMB] · Burke & Impey / Burke et al. 2018-2021
["Fuel for the Work Required", CHO g/kg] · Kerksick et al., ISSN 2017
[proteína] · piso de grasa hormonal (0.8-1.0 g/kg) · Mountjoy et al. IOC
2018 [RED-S / Energy Availability] · Boer 1984 [FFM estimada] · Beelen et
al. 2010 [resíntesis glucógeno doble turno] · Jeukendrup 2004/2011,
Stellingwerff et al. 2019 [CHO/h durante, taper] · Sawka / ACSM 2007,
Shirreffs & Sawka 2011 [hidratación y sodio] · Moore 2015 / Witard 2014
[proteína post-entreno] · Wall et al. 2015 [nutrición en lesión].

Misma API pública que v3 para no tocar app.py más de lo necesario:
  noah_fuel_dia(conn, atleta_id, fecha=None)
  noah_fuel_chat(atleta_contexto, pregunta_usuario)
Nuevas:
  noah_eat_registrar(conn, atleta_id, texto, fecha=None, momento=None)
  noah_eat_parsear(texto)  (se mantiene, usada por /nutricion/fuel/registrar)
"""
import os, json, math, re
from datetime import date, timedelta

# ═══════════════════════════ 0. UTILIDADES BASE ═════════════════════════════

def _sf(v, default=None):
    try:
        f = float(v)
        return f if math.isfinite(f) else default
    except Exception:
        return default

def _r(v, nd=0):
    if v is None:
        return None
    return round(v, nd) if nd else round(v)

def _rollback_safe(conn):
    # Postgres deja la conexión en estado "aborted" tras cualquier excepción
    # en una query -- hay que hacer rollback antes de la siguiente, o TODAS
    # las queries siguientes fallan aunque sean correctas. Bug real #3 del
    # traspaso.
    try:
        conn.rollback()
    except Exception:
        pass

def _query(conn, sql, params, fallback_sql=None, fallback_params=None, default=None):
    """Ejecuta una query; si la columna no existe en este entorno (o
    cualquier otro error), hace rollback y reintenta con una versión de
    respaldo más simple. Nunca deja la conexión rota para lo que sigue."""
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur.fetchall()
    except Exception:
        _rollback_safe(conn)
        if fallback_sql:
            try:
                cur = conn.cursor()
                cur.execute(fallback_sql, fallback_params if fallback_params is not None else params)
                return cur.fetchall()
            except Exception:
                _rollback_safe(conn)
        return default if default is not None else []

def _query_one(conn, sql, params, fallback_sql=None, fallback_params=None):
    rows = _query(conn, sql, params, fallback_sql, fallback_params, default=[])
    return rows[0] if rows else None


FUENTES_NO_REAL = ('prescripcion', 'simulacion', 'generada')  # no son sesión real ejecutada
FUENTES_PLANIFICADA = ('prescripcion', 'generada')


# ═══════════════════════════ 1. PERFIL DEL ATLETA ═══════════════════════════

def obtener_perfil(conn, atleta_id):
    row = _query_one(
        conn,
        """SELECT nombre, peso_kg, altura_cm, edad, sexo, deporte_ppal,
                  objetivo, body_fat_pct
           FROM atletas WHERE id=%s""", [atleta_id],
        fallback_sql="""SELECT nombre, peso_kg, altura_cm, edad, sexo, deporte_ppal
                         FROM atletas WHERE id=%s""",
        fallback_params=[atleta_id],
    )
    if not row:
        return None
    nombre, peso, altura, edad, sexo = row[0], row[1], row[2], row[3], row[4]
    deporte  = row[5] if len(row) > 5 else None
    objetivo = row[6] if len(row) > 6 else None
    body_fat = row[7] if len(row) > 7 else None

    altura_estimada = altura is None
    edad_estimada = edad is None
    if altura is None:
        altura = 170 if str(sexo or 'M').upper().startswith('M') else 162
    if edad is None:
        edad = 40

    return {
        'nombre': nombre, 'peso_kg': _sf(peso), 'altura_cm': _sf(altura), 'edad': _sf(edad),
        'sexo': (sexo or 'M'), 'deporte_ppal': deporte, 'objetivo': objetivo,
        'body_fat_pct': _sf(body_fat),
        'altura_estimada': altura_estimada, 'edad_estimada': edad_estimada,
    }


def calcular_ffm(peso_kg, altura_cm, sexo, body_fat_pct):
    """Masa libre de grasa. Si no hay body_fat medido, se estima con Boer
    1984 -- se marca `estimado=True` para que el frontend lo aclare."""
    if body_fat_pct:
        return {'kg': round(peso_kg * (1 - body_fat_pct / 100), 1),
                'fuente': 'medido (body_fat_pct)', 'estimado': False}
    es_hombre = str(sexo or 'M').upper().startswith('M')
    if es_hombre:
        ffm = 0.407 * peso_kg + 0.267 * altura_cm - 19.2
    else:
        ffm = 0.252 * peso_kg + 0.473 * altura_cm - 48.3
    ffm = max(ffm, peso_kg * 0.5)  # guard-rail: nunca menos de la mitad del peso
    return {'kg': round(ffm, 1), 'fuente': 'estimada (Boer 1984, sin body_fat medido)', 'estimado': True}


# ═══════════════════════════ 2. BASAL Y NEAT ════════════════════════════════

def calcular_tmb(peso_kg, altura_cm, edad, sexo):
    if not peso_kg:
        return {'disponible': False, 'kcal': None, 'faltantes': ['peso_kg']}
    base = 10 * peso_kg + 6.25 * altura_cm - 5 * edad
    tmb = base + 5 if str(sexo or 'M').upper().startswith('M') else base - 161
    return {'disponible': True, 'kcal': round(tmb), 'fuente': 'Mifflin-St Jeor 1990'}


def calcular_neat(tmb_kcal):
    """NEAT (actividad no estructurada del día). La base no tiene un dato
    real de FC media diaria (columna inexistente) -- se estima 20% del TMB
    (rango típico ACSM para adultos moderadamente activos) y se declara
    abiertamente como estimación, en vez de inventar un dato Garmin que no
    existe."""
    if not tmb_kcal:
        return {'disponible': False, 'kcal': None}
    return {'disponible': True, 'kcal': round(tmb_kcal * 0.20),
            'fuente': 'estimado en 20% del TMB (ACSM) — no hay FC media diaria en la base', 'estimado': True}


# ═══════════════════════════ 3. ENTRENO: PLANIFICADO vs REAL ═══════════════

def obtener_sesiones_planificadas_hoy(conn, atleta_id, fecha):
    """Lee la prescripción activa real (prescripciones + prescripcion_bloques
    -- la misma fuente que usa el endpoint /prescripcion) para saber qué
    entrena hoy el atleta según el plan. Si no hay prescripción activa o la
    tabla no tiene datos para hoy, devuelve lista vacía (día sin plan, no
    error)."""
    presc = _query_one(conn,
        "SELECT id FROM prescripciones WHERE atleta_id=%s AND estado IN ('pendiente','aprobada') "
        "ORDER BY id DESC LIMIT 1", [atleta_id])
    if not presc:
        return []
    presc_id = presc[0]

    try:
        from db_compat import columnas_de_tabla
        cols = set(columnas_de_tabla(conn, 'prescripcion_bloques'))
    except Exception:
        cols = set()
    extra = [c for c in ('sport', 'sesion_sport', 'sesion_duracion', 'sesion_tss') if c in cols]
    extra_sql = (', ' + ', '.join(extra)) if extra else ''

    rows = _query(conn, f"""
        SELECT sesion_num{extra_sql}
        FROM prescripcion_bloques
        WHERE prescripcion_id=%s AND sesion_fecha=%s
        ORDER BY sesion_num, bloque_num
    """, [presc_id, fecha])

    por_sesion = {}
    for row in rows:
        sn = row[0]
        d = por_sesion.setdefault(sn, {'deporte': None, 'dur_min': 0, 'tss': 0})
        for name in extra:
            val = row[1 + extra.index(name)]
            if not val:
                continue
            if name in ('sport', 'sesion_sport'):
                d['deporte'] = val
            elif name == 'sesion_duracion':
                d['dur_min'] = _sf(val, d['dur_min']) or d['dur_min']
            elif name == 'sesion_tss':
                d['tss'] = _sf(val, d['tss']) or d['tss']

    return [{'deporte': v['deporte'] or 'running', 'dur_min': v['dur_min'], 'tss': v['tss']}
            for v in por_sesion.values() if v['dur_min']]


def obtener_sesiones_reales(conn, atleta_id, fecha):
    """Sesiones REALMENTE ejecutadas ese día (sincronizadas de Garmin/Wahoo,
    no prescripción/simulación/generada)."""
    rows = _query(conn, """
        SELECT sport, duration_min, tss_total, calorias, distance_km, intensity_factor
        FROM sesiones
        WHERE atleta_id=%s AND fecha=%s AND tss_total>0
          AND (fuente IS NULL OR fuente NOT IN %s)
    """, [atleta_id, fecha, FUENTES_NO_REAL])
    return [{'deporte': r[0], 'dur_min': _sf(r[1], 0), 'tss': _sf(r[2], 0),
             'kcal_real': _sf(r[3]), 'distancia_km': r[4], 'if_real': _sf(r[5])} for r in rows]


# MET base por deporte a intensidad moderada (Compendium of Physical Activities 2011)
_MET_BASE = {'running': 9.0, 'cycling': 7.0, 'swimming': 6.0, 'otro': 7.0}

def _kcal_estimado_sesion(dur_min, tss, peso_kg, deporte='running', if_real=None):
    """Gasto del ejercicio estimado (sesion planificada, sin kcal de Garmin).
    Usa TSS como base: integra duracion x intensidad real (incluye picos de
    intervalos, a diferencia de la HR media). Validado contra TrainingPeaks:
    ~1 kcal por kg por punto de TSS/100 por hora equivalente.
    kcal_ejercicio = TSS/100 * peso * 11 (aprox 1h a umbral = ~11 kcal/kg).
    Si no hay TSS, cae a MET por duracion."""
    if not peso_kg:
        return 0
    if tss and tss > 0:
        return round(tss / 100 * peso_kg * 11)
    # Fallback sin TSS: MET moderado por deporte
    if not dur_min:
        return 0
    met = {'running': 8.5, 'cycling': 7.0, 'swimming': 6.0}.get(deporte, 7.0)
    return round(met * 3.5 * peso_kg / 200 * dur_min)

def _kcal_reposo(dur_min, tmb_kcal):
    """kcal que el cuerpo quema en reposo durante la sesión. Garmin y la
    fórmula MET dan gasto BRUTO (incluye el reposo); como el basal ya está
    contado aparte, hay que restarlo o se cuenta dos veces."""
    return (tmb_kcal or 0) / 1440.0 * (dur_min or 0)


def calcular_entreno_dia(planificadas, reales, peso_kg, tmb_kcal=None):
    def _resumen(rows, es_real):
        det, tot_kcal, tot_neto, tot_tss, tot_min = [], 0, 0, 0, 0
        for r in rows:
            kcal = r.get('kcal_real') if es_real else None
            estimado = not (kcal and kcal > 0)
            if estimado:
                kcal = _kcal_estimado_sesion(r['dur_min'], r['tss'], peso_kg,
                                             r.get('deporte','running'), r.get('if_real'))
            neto = max(kcal - _kcal_reposo(r['dur_min'], tmb_kcal), kcal * 0.70)
            det.append({'deporte': r['deporte'], 'dur_min': round(r['dur_min']),
                        'tss': round(r['tss']), 'kcal': round(kcal), 'kcal_neto': round(neto),
                        'kcal_estimado': estimado})
            tot_kcal += kcal; tot_neto += neto; tot_tss += r['tss']; tot_min += r['dur_min']
        return {'detalle': det, 'dur_min': round(tot_min), 'tss': round(tot_tss),
                'kcal': round(tot_kcal), 'kcal_neto': round(tot_neto)}

    plan = _resumen(planificadas, False) if planificadas else None
    real = _resumen(reales, True) if reales else None
    usar = real or plan  # si ya entrenó, mandan los datos reales; si no, el plan
    n_sesiones = len(reales) if reales else len(planificadas)

    return {
        'planificado': plan, 'real': real, 'usar_para_calculo': usar,
        'doble_turno': n_sesiones >= 2, 'dia_descanso': n_sesiones == 0,
        'ya_entreno_hoy': bool(reales),
    }


def calcular_cho_durante(entreno):
    """CHO que el atleta toma DURANTE las sesiones (geles, bebida). Es parte
    de lo que come en el día: se descuenta de las comidas para que
    comidas + durante = objetivo (si no, los días largos se pasan)."""
    usar = entreno.get('usar_para_calculo') or {}
    det, total = [], 0
    for s in usar.get('detalle', []):
        dur = s.get('dur_min', 0) or 0
        if dur < 60:
            tasa = 0
        elif dur < 90:
            tasa = 30
        elif dur < 150:
            tasa = 45
        else:
            tasa = 60
        if s.get('deporte') == 'swimming':
            tasa = min(tasa, 30)   # en pileta se toma menos
        g = int(round(tasa * dur / 60.0 / 5.0) * 5)
        det.append({'deporte': s.get('deporte'), 'dur_min': dur, 'cho_g_hora': tasa, 'cho_g': g})
        total += g
    return {'total_g': total, 'kcal': total * 4, 'detalle': det,
            'fuente': 'Jeukendrup 2011 / Burke 2019 (30-60 g/h según duración)'}


# ═══════════════════════════ 4. BIOMARCADORES Y CARGA ═══════════════════════

def obtener_bio(conn, atleta_id, fecha):
    """Último biomarcador disponible ANTES o EN la fecha (no exige que haya
    dato de hoy puntualmente)."""
    row = _query_one(conn, """
        SELECT hrv_rmssd, sleep_h, stress_avg, body_battery, hr_reposo, fecha
        FROM sleep_hrv WHERE atleta_id=%s AND fecha<=%s
        ORDER BY fecha DESC LIMIT 1
    """, [atleta_id, fecha])
    if not row:
        return {}
    return {'hrv_rmssd': _sf(row[0]), 'sleep_h': _sf(row[1]), 'stress_avg': _sf(row[2]),
            'body_battery': _sf(row[3]), 'hr_reposo': _sf(row[4]), 'fecha_dato': str(row[5])}


def obtener_bio_promedio_7d(conn, atleta_id, fecha):
    desde = str(date.fromisoformat(fecha) - timedelta(days=7))
    row = _query_one(conn, """
        SELECT AVG(hrv_rmssd), AVG(sleep_h) FROM sleep_hrv
        WHERE atleta_id=%s AND fecha BETWEEN %s AND %s
    """, [atleta_id, desde, fecha])
    if not row:
        return {'hrv_avg': None, 'sleep_avg': None}
    return {'hrv_avg': _sf(row[0]), 'sleep_avg': _sf(row[1])}


def calcular_carga_aguda_cronica(conn, atleta_id, fecha):
    agudo = _query_one(conn, """
        SELECT COALESCE(SUM(tss_total),0) FROM sesiones WHERE atleta_id=%s AND fecha >= %s
        AND (fuente IS NULL OR fuente NOT IN %s)
    """, [atleta_id, str(date.fromisoformat(fecha) - timedelta(days=3)), FUENTES_NO_REAL])
    cronico = _query_one(conn, """
        SELECT COALESCE(SUM(tss_total),0) FROM sesiones WHERE atleta_id=%s AND fecha >= %s
        AND (fuente IS NULL OR fuente NOT IN %s)
    """, [atleta_id, str(date.fromisoformat(fecha) - timedelta(days=28)), FUENTES_NO_REAL])
    tss_agudo = _sf(agudo[0]) if agudo else 0
    tss_cronico = _sf(cronico[0]) if cronico else 0
    if not tss_cronico:
        return None
    return round((tss_agudo / 3) / max(tss_cronico / 28, 1), 2)


def evaluar_biomarcadores(bio, bio_7d, carga_ratio):
    """Compara HOY contra el propio baseline de 7 días del atleta (no un
    umbral fijo para todo el mundo) -- así 'HRV baja' significa 'baja para
    ESTE atleta', no un número mágico universal."""
    ajustes = []
    hrv_bajo = sleep_corto = bb_bajo = carga_alta = False

    hrv, hrv_avg = bio.get('hrv_rmssd'), bio_7d.get('hrv_avg')
    if hrv is not None and hrv_avg:
        if hrv < hrv_avg * 0.90:
            hrv_bajo = True
            ajustes.append({'factor': 'HRV', 'valor': hrv, 'baseline_7d': round(hrv_avg, 1),
                            'interpretacion': f'HRV {hrv} por debajo de tu media reciente ({round(hrv_avg,1)})',
                            'accion': 'omega-3 y magnesio en la cena, alimentos antiinflamatorios'})

    sleep_h = bio.get('sleep_h')
    if sleep_h is not None and sleep_h < 6.5:
        sleep_corto = True
        ajustes.append({'factor': 'Sueño', 'valor': sleep_h,
                        'interpretacion': f'{sleep_h}h de sueño (<6.5h)',
                        'accion': 'magnesio + alimentos con triptófano en la cena (banana, leche, nueces)'})

    bb = bio.get('body_battery')
    if bb is not None and bb < 30:
        bb_bajo = True
        ajustes.append({'factor': 'Body Battery', 'valor': bb,
                        'interpretacion': f'Body battery {bb} (<30)',
                        'accion': 'sin ajuste calórico agresivo, priorizar CHO de fácil digestión'})

    if carga_ratio is not None and carga_ratio >= 1.3:
        carga_alta = True
        ajustes.append({'factor': 'Carga aguda:crónica', 'valor': carga_ratio,
                        'interpretacion': f'Ratio {carga_ratio} (>1.3, riesgo de sobrecarga)',
                        'accion': 'mantener disponibilidad de CHO alta para sostener la carga'})

    return {'ajustes': ajustes, 'hrv_bajo': hrv_bajo, 'sleep_corto': sleep_corto,
            'bb_bajo': bb_bajo, 'carga_alta': carga_alta,
            'prioridad_recuperacion': hrv_bajo or sleep_corto or carga_alta}


# ═══════════════════════════ 5. CARRERA PRÓXIMA (taper) ═════════════════════

def obtener_carrera_proxima(conn, atleta_id, fecha):
    row = _query_one(conn, """
        SELECT nombre, fecha, prioridad FROM carreras
        WHERE atleta_id=%s AND estado != 'cancelada' AND fecha >= %s
        ORDER BY fecha LIMIT 1
    """, [atleta_id, fecha])
    if not row:
        return None
    nombre, fecha_carrera, prioridad = row[0], row[1], row[2]
    try:
        dias = (date.fromisoformat(str(fecha_carrera)[:10]) - date.fromisoformat(fecha)).days
    except Exception:
        return None
    return {'nombre': nombre, 'fecha': str(fecha_carrera)[:10], 'prioridad': prioridad or 'B', 'dias_restantes': dias}


# ═══════════════════════════ 6. PROTOCOLOS: CHO / PROT / GRASA ══════════════

def clasificar_cho(dur_h_total, intensidad_media, dia_descanso, dias_para_carrera, prioridad_carrera):
    """Burke & Impey / Burke et al. 2018-2021 — 'Fuel for the Work Required'."""
    if dias_para_carrera is not None and 0 <= dias_para_carrera <= 3 and (prioridad_carrera or 'B') in ('A', 'B'):
        return {'rango': (10, 12), 'texto': 'Pre-competencia (48-72h antes) — carb loading activo'}
    if dia_descanso:
        return {'rango': (3, 5), 'texto': 'Día de descanso — sin sesión planificada ni ejecutada'}
    if dur_h_total >= 4:
        return {'rango': (8, 12), 'texto': 'Muy alto volumen (>4h/día)'}
    if dur_h_total >= 1 and intensidad_media >= 0.75:
        return {'rango': (6, 10), 'texto': 'Moderado-alto (1-3h/día, intensidad media-alta)'}
    if dur_h_total >= 0.75:
        return {'rango': (5, 7), 'texto': 'Moderado (~1h/día)'}
    return {'rango': (3, 5), 'texto': 'Liviano/técnico'}


def seleccionar_cho_gkg(rango, doble_turno, recuperacion_pendiente, prioridad_recuperacion):
    lo, hi = rango
    valor = lo + (hi - lo) * 0.5
    if doble_turno:
        valor += (hi - lo) * 0.25
    if recuperacion_pendiente:
        valor += (hi - lo) * 0.15
    if prioridad_recuperacion:
        valor -= (hi - lo) * 0.15  # fatiga real -> no ir al tope del rango
    return round(min(max(valor, lo), hi), 1)


def seleccionar_prot_gkg(dia_descanso, doble_turno, dur_h_total):
    """ISSN Position Stand (Kerksick et al. 2017): 1.4-2.0 g/kg/día. En
    descanso se mantiene alta (no se recorta) para no perder masa magra."""
    if dia_descanso:
        return 1.7
    if doble_turno or dur_h_total >= 1.5:
        return 2.0
    if dur_h_total >= 0.75:
        return 1.8
    return 1.6


TEF_PCT = 0.08   # efecto térmico de los alimentos (~8-10%)


def _tipo_objetivo(objetivo):
    o = (objetivo or '').lower()
    if 'compos' in o:
        return 'composicion'
    if any(k in o for k in ('bajar', 'perd', 'defic', 'adelg', 'grasa')):
        return 'bajar'
    if any(k in o for k in ('subir', 'ganar', 'masa', 'volumen')):
        return 'subir'
    return 'mantener'


def calcular_macros_dia(peso_kg, entreno, bio_eval, carrera, objetivo,
                        base_kcal=None, recuperacion_pendiente=False):
    """v5: LA ENERGÍA MANDA. Entrada = salida (±objetivo).
      1) gasto = (basal + NEAT + entreno NETO) + TEF
      2) kcal objetivo = gasto x factor (déficit solo en días fáciles)
      3) proteína (g/kg) y grasa (piso + 20-25% kcal) se fijan
      4) el CHO es lo que falta para cerrar las kcal, validado contra el
         rango de Burke (piso = no subalimentar el trabajo; techo = no pasarse)
    Antes cada macro salía de su propia tabla y las kcal eran solo la suma,
    sin relación con el gasto."""
    if not peso_kg:
        return {'disponible': False, 'mensaje': 'Falta el peso del atleta.'}

    usar = entreno['usar_para_calculo'] or {}
    dur_h = usar.get('dur_min', 0) / 60
    tss = usar.get('tss', 0)
    _if_real = usar.get('if_real') or usar.get('intensity_factor')
    if _if_real and _if_real > 0:
        intensidad = min(_if_real, 1.15)
    elif tss and dur_h > 0:
        intensidad = min(tss / (dur_h * 100), 1.1)  # sin raiz que infla cortas
    else:
        intensidad = 0.6 if dur_h > 0 else 0

    dias_carrera = carrera['dias_restantes'] if carrera else None
    prioridad_carrera = carrera['prioridad'] if carrera else None
    cho_clasif = clasificar_cho(dur_h, intensidad, entreno['dia_descanso'], dias_carrera, prioridad_carrera)
    lo, hi = cho_clasif['rango']
    es_carga = (dias_carrera is not None and 0 <= dias_carrera <= 3
                and (prioridad_carrera or 'B') in ('A', 'B'))

    # 1) ENERGÍA QUE SALE
    if not base_kcal:
        base_kcal = round(peso_kg * 25)
    entreno_neto = usar.get('kcal_neto', usar.get('kcal', 0)) or 0
    tef = round((base_kcal + entreno_neto) * TEF_PCT)
    gasto_total = round(base_kcal + entreno_neto + tef)

    # 2) ENERGÍA QUE DEBE ENTRAR (según objetivo)
    tipo = _tipo_objetivo(objetivo)
    dia_duro = (dur_h >= 2) or entreno['doble_turno'] or es_carga
    protegido = dia_duro or recuperacion_pendiente or bio_eval.get('prioridad_recuperacion')
    if tipo == 'bajar':
        factor = 1.0 if protegido else 0.90
    elif tipo == 'composicion':
        factor = 1.0 if protegido else 0.95
    elif tipo == 'subir':
        factor = 1.07
    else:
        factor = 1.0
    kcal_obj = round(gasto_total * factor)

    # 3) PROTEÍNA y GRASA
    prot_gkg = seleccionar_prot_gkg(entreno['dia_descanso'], entreno['doble_turno'], dur_h)
    if factor < 1.0:
        prot_gkg = min(prot_gkg + 0.2, 2.2)   # en déficit, más proteína (ISSN)
    prot_g = round(peso_kg * prot_gkg)
    prot_kcal = prot_g * 4

    piso_grasa_g = peso_kg * (0.7 if tipo == 'composicion' else 0.9)
    pct_grasa = 0.20 if hi >= 8 else 0.25
    grasa_g = round(max(piso_grasa_g, pct_grasa * kcal_obj / 9))

    # 4) CHO = lo que falta, validado contra Burke
    cho_energia = (kcal_obj - prot_kcal - grasa_g * 9) / 4
    if es_carga:
        cho_g = max(cho_energia, lo * peso_kg)          # carga: puede superar el gasto a propósito
    else:
        cho_g = max(min(cho_energia, hi * peso_kg), lo * peso_kg)
    cho_g = round(cho_g)
    if not es_carga:
        sobrante = kcal_obj - (prot_kcal + grasa_g * 9 + cho_g * 4)
        if sobrante > 0:    # el techo de CHO cortó: el resto va a grasa (hasta 35% kcal)
            tope = 0.35 * kcal_obj / 9
            grasa_g = round(grasa_g + max(0, min(sobrante / 9, tope - grasa_g)))

    total_kcal = cho_g * 4 + prot_kcal + grasa_g * 9

    return {
        'disponible': True,
        'cho_g': cho_g, 'cho_gkg': round(cho_g / peso_kg, 1), 'cho_fuente': 'Burke/Impey 2018 (rango) + balance energético',
        'cho_clasificacion': cho_clasif['texto'], 'cho_rango': cho_clasif['rango'],
        'prot_g': prot_g, 'prot_gkg': round(prot_gkg, 2), 'prot_fuente': 'ISSN 2017 (Kerksick et al.)', 'prot_rango': (1.4, 2.0),
        'grasa_g': grasa_g, 'grasa_gkg': round(grasa_g / peso_kg, 2), 'grasa_fuente': 'piso hormonal + 20-25% de las kcal',
        'total_kcal': total_kcal,
        'intensidad_estimada': round(intensidad, 2),
        'gasto_total_kcal': gasto_total, 'tef_kcal': tef, 'entreno_neto_kcal': round(entreno_neto),
        'objetivo_tipo': tipo, 'factor_objetivo': factor,
        'balance_kcal': total_kcal - gasto_total,
        'balance_pct': round((total_kcal - gasto_total) / max(gasto_total, 1) * 100, 1),
    }


# ═══════════════════════════ 7. ENERGY AVAILABILITY (RED-S) ════════════════

def calcular_ea(macros, entreno, ffm, sexo):
    if not macros.get('disponible') or not ffm.get('kg'):
        return {'disponible': False}
    _u = entreno.get('usar_para_calculo') or {}
    gasto_ejercicio = _u.get('kcal_neto', _u.get('kcal', 0))
    ea = (macros['total_kcal'] - gasto_ejercicio) / ffm['kg']
    if ea < 30:
        status = 'alarma'
    elif ea < 45:
        status = 'atencion'
    else:
        status = 'safe'
    resultado = {
        'disponible': True, 'valor': round(ea, 1), 'status': status,
        'ffm_kg': ffm['kg'], 'ffm_estimado': ffm['estimado'],
        'fuente': 'Mountjoy et al. IOC 2018 (RED-S)',
    }
    if str(sexo or 'M').upper().startswith('F'):
        resultado['nota_sexo'] = ('El riesgo de RED-S es significativamente mayor en mujeres atletas de '
                                   'resistencia (Mountjoy 2018, Melin et al. 2019). No hay dato de ciclo '
                                   'menstrual cargado — si la atleta lo trackea, mejora la precisión de este número.')
    return resultado


# ═══════════════════════════ 8. RECUPERACIÓN DE AYER (memoria) ═════════════

def calcular_recuperacion_pendiente(conn, atleta_id, fecha):
    """Sesión de ayer -> si fue exigente, hoy sube CHO para resíntesis de
    glucógeno (Beelen et al. 2010)."""
    ayer = str(date.fromisoformat(fecha) - timedelta(days=1))
    rows = _query(conn, """
        SELECT sport, duration_min, tss_total, calorias FROM sesiones
        WHERE atleta_id=%s AND fecha=%s AND tss_total>0
        AND (fuente IS NULL OR fuente NOT IN %s)
        ORDER BY tss_total DESC LIMIT 1
    """, [atleta_id, ayer, FUENTES_NO_REAL])
    if not rows:
        return None
    sport, dur, tss, kcal = rows[0]
    if _sf(tss, 0) < 60 and _sf(dur, 0) < 75:
        return None  # sesión de ayer liviana, no amerita ajuste
    return {'sesion': f'{sport} {round(_sf(dur,0))}min, TSS {round(_sf(tss,0))}',
            'kcal': _sf(kcal), 'ajuste_cho_pct': 15,
            'fuente': 'Beelen et al. 2010 (resíntesis de glucógeno)'}


def calcular_compensacion_memoria(conn, atleta_id, fecha, objetivo_kcal_hoy):
    """Si ayer el atleta registró comida (nutricion_log) y comió bastante
    menos de lo que el motor le hubiese recomendado, hoy se sube una
    fracción del déficit -- nunca de golpe (malestar GI)."""
    ayer = str(date.fromisoformat(fecha) - timedelta(days=1))
    real = _query_one(conn, "SELECT COALESCE(SUM(kcal),0), COUNT(*) FROM nutricion_log WHERE atleta_id=%s AND fecha=%s",
                       [atleta_id, ayer])
    if not real or not real[1]:
        return None  # no registró nada ayer -> no hay con qué comparar
    kcal_real_ayer = _sf(real[0], 0)
    if kcal_real_ayer <= 0:
        return None
    deficit = objetivo_kcal_hoy - kcal_real_ayer  # aproximación: usamos el objetivo de hoy como proxy del de ayer
    if deficit < 300:
        return None
    compensar = min(round(deficit * 0.4), 300)  # compensar máximo 300kcal, y no todo de una
    return {'kcal_ayer_registradas': round(kcal_real_ayer), 'deficit_estimado': round(deficit),
            'compensacion_kcal': compensar, 'nota': 'Compensación parcial — no se sube todo de golpe para evitar malestar GI.'}


# ═══════════════════════════ 9. ALIMENTOS REALES Y PLATOS ═══════════════════

# nombre: (CHO g/100g, Prot g/100g, Grasa g/100g, kcal/100g)
ALIMENTOS = {
    # ═══ CEREALES Y GRANOS (crudo/seco por 100g) ═══
    'avena':              (66, 13, 7,   389),
    'arroz_blanco':       (78, 7,  0.9, 360),
    'arroz_integral':     (76, 8,  2.5, 362),
    'pasta':              (75, 13, 1.5, 371),
    'pasta_integral':     (71, 14, 2.5, 348),
    'quinoa':             (64, 14, 6,   368),
    'polenta':            (79, 8,  1.5, 362),
    'cuscus':             (77, 13, 0.6, 376),
    'cebada':             (73, 12, 2,   354),
    'pan_integral':       (42, 9,  3,   247),
    'pan_blanco':         (50, 9,  3,   265),
    'pan_sin_tacc':       (52, 3,  4,   260),
    'tortilla_trigo':     (55, 8,  7,   310),
    'galletas_arroz':     (82, 8,  3,   387),
    'granola':            (64, 10, 15,  471),
    'cereal_integral':    (72, 10, 5,   360),
    # ═══ TUBERCULOS ═══
    'papa':               (17, 2,  0.1, 77),
    'batata':             (20, 1.6,0.1, 86),
    'mandioca':           (38, 1.4,0.3, 160),
    # ═══ LEGUMBRES (seco por 100g) ═══
    'lentejas':           (60, 25, 1,   352),
    'garbanzos':          (61, 19, 6,   364),
    'porotos':            (60, 21, 1.2, 333),
    'arvejas':            (60, 25, 2,   364),
    'soja':               (30, 36, 20,  446),
    # ═══ PROTEINAS ANIMALES (crudo por 100g) ═══
    'pollo_pechuga':      (0,  23, 2,   110),
    'pollo_muslo':        (0,  19, 8,   155),
    'pavo':               (0,  22, 2,   105),
    'carne_magra':        (0,  22, 6,   140),
    'carne_picada_magra': (0,  21, 9,   170),
    'cerdo_magro':        (0,  21, 6,   143),
    'salmon':             (0,  20, 13,  208),
    'atun_fresco':        (0,  23, 1,   108),
    'atun_lata_agua':     (0,  26, 1,   116),
    'merluza':            (0,  18, 1,   82),
    'trucha':             (0,  20, 6,   140),
    'camaron':            (0,  24, 0.3, 99),
    'huevo':              (1,  13, 11,  155),
    'clara_huevo':        (0.7,11, 0.2, 52),
    # ═══ LACTEOS ═══
    'leche_entera':       (5,  3.3,3.5, 65),
    'leche_descremada':   (5,  3.4,0.1, 35),
    'leche_almendras':    (1,  0.5,1.1, 15),
    'yogur_natural':      (5,  4,  3,   61),
    'yogur_griego':       (4,  10, 5,   100),
    'yogur_descremado':   (6,  4,  0.1, 42),
    'queso_fresco':       (3,  18, 20,  260),
    'queso_port_salut':   (1,  24, 26,  340),
    'queso_rallado':      (3,  28, 25,  350),
    'ricota':             (3,  11, 13,  174),
    'queso_untable_light':(4,  8,  10,  140),
    # ═══ FRUTAS (por 100g) ═══
    'banana':             (23, 1,  0.3, 89),
    'manzana':            (14, 0.3,0.2, 52),
    'pera':               (15, 0.4,0.1, 57),
    'naranja':            (12, 0.9,0.1, 47),
    'mandarina':          (13, 0.8,0.3, 53),
    'frutilla':           (8,  0.7,0.3, 32),
    'arandanos':          (14, 0.7,0.3, 57),
    'uva':                (18, 0.6,0.2, 69),
    'kiwi':               (15, 1.1,0.5, 61),
    'durazno':            (10, 0.9,0.3, 39),
    'ananá':              (13, 0.5,0.1, 50),
    'melon':              (8,  0.8,0.2, 34),
    'sandia':             (8,  0.6,0.2, 30),
    'ciruela':            (11, 0.7,0.3, 46),
    'higo':               (19, 0.8,0.3, 74),
    'pasas':              (79, 3,  0.5, 299),
    'datil':              (75, 2,  0.4, 282),
    # ═══ VERDURAS (por 100g) ═══
    'lechuga':            (3,  1.4,0.2, 15),
    'tomate':             (4,  0.9,0.2, 18),
    'zanahoria':          (10, 0.9,0.2, 41),
    'brocoli':            (7,  2.8,0.4, 34),
    'espinaca':           (4,  2.9,0.4, 23),
    'zapallo':            (7,  1,  0.1, 26),
    'zucchini':           (3,  1.2,0.3, 17),
    'morron':             (6,  1,  0.3, 31),
    'cebolla':            (9,  1.1,0.1, 40),
    'pepino':             (4,  0.7,0.1, 16),
    'berenjena':          (6,  1,  0.2, 25),
    'coliflor':           (5,  1.9,0.3, 25),
    'chaucha':            (7,  1.8,0.1, 31),
    'remolacha':          (10, 1.6,0.2, 43),
    'choclo':             (19, 3.3,1.5, 96),
    'verduras_mix':       (7,  2,  0.3, 35),
    'palta':              (9,  2,  15,  160),
    # ═══ FRUTOS SECOS Y SEMILLAS ═══
    'almendras':          (22, 21, 49,  579),
    'nueces':             (14, 15, 65,  654),
    'mani':               (16, 26, 49,  567),
    'castañas_caju':      (30, 18, 44,  553),
    'pistachos':          (28, 20, 45,  560),
    'semillas_chia':      (42, 17, 31,  486),
    'semillas_girasol':   (20, 21, 51,  584),
    'semillas_zapallo':   (54, 19, 19,  446),
    'manteca_mani':       (20, 25, 50,  588),
    # ═══ GRASAS Y ACEITES ═══
    'aceite_oliva':       (0,  0,  100, 884),
    'aceite_girasol':     (0,  0,  100, 884),
    'manteca':            (0,  0.9,81,  717),
    'palta_aceite':       (0,  0,  100, 884),
    # ═══ SUPLEMENTOS / OTROS ═══
    'whey_protein':       (8,  78, 7,   400),
    'proteina_vegetal':   (10, 75, 6,   380),
    'miel':               (82, 0.3,0,   304),
    'mermelada_sin_azucar':(30,0.5,0.1, 120),
    'dulce_batata':       (74, 1,  0.2, 300),
    'cacao_amargo':       (58, 20, 14,  400),
    'barrita_cereal':     (65, 8,  12,  380),
    'tofu':               (2,  8,  4.8, 76),
    # compat con recetas viejas (mapear cocido -> crudo equivalente)
    'arroz_cocido':       (78, 7,  0.9, 360),
    'arroz_integral_cocido': (76, 8, 2.5, 362),
    'pasta_cocida':       (75, 13, 1.5, 371),
    'quinoa_cocida':      (64, 14, 6,   368),
    'leche':              (5,  3.3,3.5, 65),
    'yogur_coco':         (7,  1,  6,   90),
    'frutos_secos':       (15, 20, 50,  580),
    'lentejas_cocidas':   (60, 25, 1,   352),
    'garbanzos_cocidos':  (61, 19, 6,   364),
    'proteina_arveja':    (10, 75, 6,   380),
}

# medidas caseras en gramos, para mostrar "1 taza y 1/2" en vez de solo gramos
MEDIDAS_CASERAS = {
    # cereales/granos crudos
    'arroz_blanco':{'taza':200,'cucharada':15},'arroz_integral':{'taza':190},
    'arroz_cocido':{'taza':200},'arroz_integral_cocido':{'taza':190},
    'pasta':{'plato':100},'pasta_integral':{'plato':100},'pasta_cocida':{'plato':100},
    'quinoa':{'taza':170},'quinoa_cocida':{'taza':170},'avena':{'taza':80,'cucharada':15},
    'polenta':{'taza':160},'cuscus':{'taza':175},'granola':{'puñado':40,'taza':60},
    'pan_integral':{'rebanada':30},'pan_blanco':{'rebanada':30},'pan_sin_tacc':{'rebanada':35},
    'galletas_arroz':{'unidad':8},'cereal_integral':{'taza':40},
    # tuberculos
    'papa':{'unidad':150},'batata':{'unidad':130},'mandioca':{'porción':150},
    # legumbres secas
    'lentejas':{'taza':180},'garbanzos':{'taza':180},'porotos':{'taza':180},'arvejas':{'taza':150},
    # proteinas
    'pollo_pechuga':{'unidad':150,'media unidad':75},'pollo_muslo':{'unidad':120},
    'carne_magra':{'bife':150},'carne_picada_magra':{'porción':120},'pavo':{'porción':120},
    'salmon':{'filet':140},'atun_fresco':{'filet':140},'atun_lata_agua':{'lata':120},
    'merluza':{'filet':150},'trucha':{'filet':140},'huevo':{'unidad':55},'clara_huevo':{'unidad':33},
    # lacteos
    'leche_entera':{'vaso':200},'leche_descremada':{'vaso':200},'leche':{'vaso':200},
    'leche_almendras':{'vaso':200},'yogur_natural':{'pote':190},'yogur_griego':{'pote':150},
    'yogur_descremado':{'pote':190},'queso_fresco':{'porción':40},'ricota':{'porción':50},
    'queso_port_salut':{'feta':30},'queso_rallado':{'cucharada':10},'queso_untable_light':{'cucharada':20},
    # frutas
    'banana':{'unidad':120},'manzana':{'unidad':150},'pera':{'unidad':160},'naranja':{'unidad':180},
    'mandarina':{'unidad':90},'frutilla':{'taza':150},'arandanos':{'puñado':40},'uva':{'taza':100},
    'kiwi':{'unidad':75},'durazno':{'unidad':150},'ananá':{'rodaja':80},'melon':{'porción':150},
    'sandia':{'porción':200},'ciruela':{'unidad':65},'higo':{'unidad':50},'pasas':{'puñado':40},'datil':{'unidad':8},
    # verduras
    'lechuga':{'porción':50},'tomate':{'unidad':120},'zanahoria':{'unidad':70},'brocoli':{'porción':100},
    'espinaca':{'porción':80},'zapallo':{'porción':120},'zucchini':{'unidad':150},'morron':{'unidad':120},
    'cebolla':{'unidad':110},'pepino':{'unidad':150},'berenjena':{'unidad':200},'coliflor':{'porción':100},
    'chaucha':{'porción':90},'remolacha':{'unidad':80},'choclo':{'unidad':100},'verduras_mix':{'porción':150},
    'palta':{'media unidad':70,'unidad':140},
    # frutos secos
    'almendras':{'puñado':30},'nueces':{'puñado':30},'mani':{'puñado':30},'castañas_caju':{'puñado':30},
    'pistachos':{'puñado':30},'semillas_chia':{'cucharada':12},'semillas_girasol':{'cucharada':12},
    'semillas_zapallo':{'cucharada':12},'manteca_mani':{'cucharada':16},'frutos_secos':{'puñado':30},
    # grasas
    'aceite_oliva':{'cucharada':14},'aceite_girasol':{'cucharada':14},'manteca':{'cucharada':14},
    # otros
    'whey_protein':{'scoop':30},'proteina_vegetal':{'scoop':30},'proteina_arveja':{'scoop':30},
    'miel':{'cucharada':21},'mermelada_sin_azucar':{'cucharada':20},'dulce_batata':{'porción':40},
    'cacao_amargo':{'cucharada':10},'barrita_cereal':{'unidad':40},'tofu':{'porción':100},
    'yogur_coco':{'pote':150},'lentejas_cocidas':{'taza':180},'garbanzos_cocidos':{'taza':180},
}

RESTRICCION_EXCLUYE = {
    'vegetariano': {'pollo_pechuga', 'salmon', 'atun_lata', 'carne_magra'},
    'vegano': {'pollo_pechuga', 'salmon', 'atun_lata', 'carne_magra', 'huevo', 'yogur_griego',
               'leche', 'whey_protein', 'queso_rallado', 'miel'},
    'celiaco': {'pan_integral', 'pasta_cocida', 'avena'},
    'sin_lactosa': {'leche', 'yogur_griego', 'queso_rallado'},
}
RESTRICCION_REEMPLAZO = {
    'vegano': {'pollo_pechuga': 'proteina_arveja', 'salmon': 'tofu', 'atun_lata': 'lentejas_cocidas',
               'carne_magra': 'garbanzos_cocidos', 'huevo': 'tofu', 'yogur_griego': 'yogur_coco',
               'leche': 'leche_almendras', 'whey_protein': 'proteina_arveja', 'queso_rallado': 'tofu',
               'miel': 'arroz_integral_cocido'},
    'vegetariano': {'pollo_pechuga': 'huevo', 'salmon': 'tofu', 'atun_lata': 'lentejas_cocidas', 'carne_magra': 'huevo'},
    'celiaco': {'pan_integral': 'pan_sin_tacc', 'pasta_cocida': 'quinoa_cocida', 'avena': 'quinoa_cocida'},
    'sin_lactosa': {'leche': 'leche_almendras', 'yogur_griego': 'yogur_coco', 'queso_rallado': 'tofu'},
}


def _aplicar_restriccion(alimento, restricciones):
    for r in restricciones:
        if alimento in RESTRICCION_EXCLUYE.get(r, set()):
            return RESTRICCION_REEMPLAZO.get(r, {}).get(alimento, alimento)
    return alimento


_PLURAL = {'unidad': 'unidades', 'porción': 'porciones', 'rebanada': 'rebanadas', 'taza': 'tazas',
           'cucharada': 'cucharadas', 'puñado': 'puñados', 'vaso': 'vasos', 'pote': 'potes',
           'plato': 'platos', 'scoop': 'scoops'}


def _medida_casera(alimento, gramos):
    medidas = MEDIDAS_CASERAS.get(alimento)
    if not medidas:
        return f'{gramos}g'
    unidad, base_g = next(iter(medidas.items()))
    cant = gramos / base_g
    if cant < 0.4:
        return f'{gramos}g'
    n = round(cant * 2) / 2
    if n > 1 and unidad in _PLURAL:
        unidad = _PLURAL[unidad]
    return f'{n:g} {unidad} ({gramos}g)'


# ═══════════ RECETAS COMPLETAS Y COHERENTES ═══════════
# Cada item: (alimento, rol). rol: prot/carb/grasa/fruta/libre/verdura
# verdura: el alimento ES el texto a mostrar (no escala)

RECETAS_DESAYUNO = [
    [('avena','carb'),('yogur_griego','prot'),('banana','fruta'),('miel','libre')],
    [('huevo','prot'),('pan_integral','carb'),('palta','grasa')],
    [('yogur_griego','prot'),('granola','carb'),('nueces','grasa')],
    [('pan_integral','carb'),('manteca_mani','grasa'),('banana','fruta')],
    [('pan_integral','carb'),('queso_fresco','prot'),('palta','grasa'),('naranja','fruta')],
    [('avena','carb'),('leche','prot'),('almendras','grasa'),('manzana','fruta')],
    [('huevo','prot'),('pan_integral','carb'),('queso_fresco','libre')],
    [('yogur_griego','prot'),('avena','carb'),('pera','fruta'),('nueces','grasa')],
]

RECETAS_ALMUERZO = [
    [('pollo_pechuga','prot'),('arroz_integral','carb'),('aceite_oliva','grasa'),('Ensalada cruda variada','verdura')],
    [('salmon','prot'),('batata','carb'),('Verduras al vapor','verdura')],
    [('carne_magra','prot'),('quinoa','carb'),('aceite_oliva','grasa'),('Verduras asadas al horno','verdura')],
    [('merluza','prot'),('arroz_blanco','carb'),('aceite_oliva','grasa'),('Vegetales grillados','verdura')],
    [('pollo_pechuga','prot'),('batata','carb'),('Verduras salteadas al wok','verdura')],
    [('cerdo_magro','prot'),('papa','carb'),('palta','grasa'),('Brócoli y zanahoria al vapor','verdura')],
    [('salmon','prot'),('quinoa','carb'),('Ensalada cruda variada','verdura')],
    [('carne_magra','prot'),('arroz_integral','carb'),('Verduras al vapor','verdura')],
    [('atun_fresco','prot'),('pasta_integral','carb'),('aceite_oliva','grasa'),('Ensalada cruda variada','verdura')],
    [('pavo','prot'),('batata','carb'),('Verduras asadas al horno','verdura')],
    [('trucha','prot'),('arroz_integral','carb'),('aceite_oliva','grasa'),('Vegetales grillados','verdura')],
    [('pollo_muslo','prot'),('quinoa','carb'),('Verduras al vapor','verdura')],
]

RECETAS_SNACK = [
    [('banana','fruta'),('almendras','grasa')],
    [('manzana','fruta'),('yogur_griego','prot')],
    [('barrita_cereal','libre'),('banana','fruta')],
    [('pera','fruta'),('nueces','grasa')],
    [('yogur_griego','prot'),('pasas','fruta')],
    [('naranja','fruta'),('queso_fresco','prot')],
]

CANT_FRUTA = {'banana': 120, 'manzana': 180, 'pera': 170, 'naranja': 180, 'pasas': 40}
CANT_LIBRE = {'miel': 15, 'barrita_cereal': 40, 'queso_fresco': 40, 'palta': 50}

MEDIDAS_CASERAS.update({'whey_protein': {'scoop': 30}, 'batata': {'unidad': 150}, 'granola': {'puñado': 40}})

RECETAS_SNACK.extend([
    [('pan_integral', 'carb'), ('miel', 'libre'), ('banana', 'fruta')],
    [('avena', 'carb'), ('leche', 'prot'), ('banana', 'fruta')],
    [('yogur_griego', 'prot'), ('granola', 'carb'), ('banana', 'fruta')],
    [('pan_integral', 'carb'), ('manteca_mani', 'grasa'), ('banana', 'fruta')],
    [('arroz_cocido', 'carb'), ('huevo', 'prot')],
])

RECETAS_POST = [
    [('whey_protein', 'prot'), ('banana', 'fruta'), ('avena', 'carb'), ('miel', 'libre')],
    [('yogur_griego', 'prot'), ('banana', 'fruta'), ('granola', 'carb')],
    [('leche', 'prot'), ('banana', 'fruta'), ('pan_integral', 'carb'), ('miel', 'libre')],
    [('whey_protein', 'prot'), ('banana', 'fruta'), ('arroz_cocido', 'carb')],
]

RECETAS_VENTANA = [   # entre sesiones: CHO simple + proteína, casi sin grasa
    [('arroz_cocido', 'carb'), ('pollo_pechuga', 'prot'), ('banana', 'fruta')],
    [('pasta_cocida', 'carb'), ('atun_lata', 'prot'), ('miel', 'libre')],
    [('arroz_cocido', 'carb'), ('huevo', 'prot'), ('banana', 'fruta')],
]

# Porción máxima razonable por alimento (g). Evita "9 rebanadas" o "3 bananas".
PORCION_MAX_G = {
    'pollo_pechuga': 250, 'carne_magra': 250, 'salmon': 220, 'atun_lata': 170, 'huevo': 180, 'tofu': 250,
    'arroz_cocido': 450, 'arroz_integral_cocido': 450, 'pasta_cocida': 400, 'quinoa_cocida': 400, 'batata': 400,
    'avena': 100, 'pan_integral': 120, 'pan_sin_tacc': 140, 'granola': 80,
    'yogur_griego': 300, 'yogur_coco': 300, 'leche': 400, 'leche_almendras': 400, 'queso_fresco': 100,
    'queso_rallado': 30, 'whey_protein': 40, 'proteina_arveja': 45, 'lentejas_cocidas': 300,
    'garbanzos_cocidos': 250, 'aceite_oliva': 20, 'palta': 100, 'nueces': 40, 'almendras': 40,
    'frutos_secos': 40, 'manteca_mani': 32,
}
MAX_DEFAULT = {'prot': 250, 'carb': 400, 'grasa': 40}
_E = (4.0, 4.0, 9.0)      # kcal por gramo de cada macro
_W = (1.0, 1.6, 0.7)      # peso del error: la proteína importa más, la grasa menos


def _redondear_porcion(alim, g):
    if alim == 'huevo':
        return max(1, round(g / 60.0)) * 60 if g >= 30 else 0
    if g >= 25:
        return int(round(g / 5.0) * 5)
    return int(round(g))


def _resolver_receta(receta, cho_t, prot_t, grasa_t, restricciones, cap_scale=1.0):
    """Arma UN plato desde una receta: fruta/libre/verdura van fijas y los
    demás alimentos se ajustan (mínimos cuadrados con topes por porción)
    para que el TOTAL del plato (incluyendo lo que aporta cada alimento,
    no solo su macro 'principal') se acerque al objetivo."""
    ent = []
    c0 = p0 = g0 = 0.0
    for alim, rol in receta:
        if rol == 'verdura':
            v = ALIMENTOS['verduras_mix']
            c0 += v[0] * 1.5; p0 += v[1] * 1.5; g0 += v[2] * 1.5
            ent.append({'a': alim, 'n': alim, 'rol': rol, 'info': None, 'g': 150, 'hi': 150, 'fijo': True, 'verdura': True})
            continue
        a = _aplicar_restriccion(alim, restricciones)
        info = ALIMENTOS.get(a, (0, 0, 0, 0))
        if rol in ('fruta', 'libre'):
            g = CANT_FRUTA.get(a, 120) if rol == 'fruta' else CANT_LIBRE.get(a, 30)
            c0 += info[0] * g / 100; p0 += info[1] * g / 100; g0 += info[2] * g / 100
            ent.append({'a': a, 'n': a, 'rol': rol, 'info': info, 'g': g, 'hi': g, 'fijo': True})
        else:
            hi = PORCION_MAX_G.get(a, MAX_DEFAULT.get(rol, 200)) * cap_scale
            ent.append({'a': a, 'n': a, 'rol': rol, 'info': info, 'g': 0.0, 'hi': hi, 'fijo': False})

    flex = [e for e in ent if not e['fijo']]
    t = (cho_t, prot_t, grasa_t)
    for _ in range(300):
        movido = 0.0
        for e in flex:
            tot = [c0, p0, g0]
            for x in flex:
                for m in range(3):
                    tot[m] += x['info'][m] * x['g'] / 100.0
            num = sum(_W[m] * _E[m] ** 2 * (tot[m] - t[m]) * (e['info'][m] / 100.0) for m in range(3))
            den = sum(_W[m] * _E[m] ** 2 * (e['info'][m] / 100.0) ** 2 for m in range(3))
            if den <= 0:
                continue
            nuevo = min(max(e['g'] - num / den, 0.0), e['hi'])
            movido += abs(nuevo - e['g'])
            e['g'] = nuevo
        if movido < 0.01:
            break

    items = []
    cho_t2 = c0; prot_t2 = p0; gra_t2 = g0
    for e in ent:
        if e.get('verdura'):
            items.append({'alimento': e['a'], 'gramos': 150, 'medida': '1 porción grande'})
            continue
        g = e['g'] if e['fijo'] else _redondear_porcion(e['a'], e['g'])
        if not e['fijo']:
            if g < 10:
                continue    # ingrediente innecesario para este plato
            cho_t2 += e['info'][0] * g / 100; prot_t2 += e['info'][1] * g / 100; gra_t2 += e['info'][2] * g / 100
        items.append({'alimento': e['a'].replace('_', ' '), 'gramos': g, 'medida': _medida_casera(e['a'], g)})
    cho_r, prot_r, gra_r = round(cho_t2), round(prot_t2), round(gra_t2)
    return {'items': items, 'macros': {'cho_g': cho_r, 'prot_g': prot_r, 'grasa_g': gra_r,
                                       'kcal': cho_r * 4 + prot_r * 4 + gra_r * 9}}


def _plato_desde_pool(pool, seed, cho_t, prot_t, grasa_t, restricciones, cap_scale):
    """Prueba las recetas del pool (rotando por `seed` para dar variedad) y
    se queda con la primera que cierra el objetivo (+-8% kcal, +-20% CHO/prot);
    si ninguna cierra, la que menos error tenga."""
    kcal_t = cho_t * 4 + prot_t * 4 + grasa_t * 9
    mejor, mejor_score = None, None
    n = len(pool)
    for k in range(n):
        plato = _resolver_receta(pool[(seed + k) % n], cho_t, prot_t, grasa_t, restricciones, cap_scale)
        m = plato['macros']
        e_k = abs(m['kcal'] - kcal_t) / max(kcal_t, 100)
        e_c = abs(m['cho_g'] - cho_t) / max(cho_t, 20)
        e_p = abs(m['prot_g'] - prot_t) / max(prot_t, 15)
        if e_k <= 0.08 and max(e_c, e_p) <= 0.20:
            return plato
        score = e_k + 0.5 * max(e_c, e_p)
        if mejor is None or score < mejor_score:
            mejor, mejor_score = plato, score
    return mejor


def construir_plato(cho_g, prot_g, grasa_g, tipo, restricciones, seed, es_desayuno=False, cap_scale=1.0):
    """Arma un plato real que cierra los macros objetivo con porciones
    razonables. `seed` rota las recetas para variedad."""
    if tipo == 'post_entreno':
        pool = RECETAS_POST
    elif es_desayuno:
        pool = RECETAS_DESAYUNO
    elif tipo == 'merienda':
        pool, seed = RECETAS_DESAYUNO, seed + 3
    elif tipo == 'liviano':
        pool = RECETAS_SNACK
    elif tipo == 'ventana_doble_turno':
        pool = RECETAS_VENTANA
    else:
        pool = RECETAS_ALMUERZO
    return _plato_desde_pool(pool, seed, cho_g, prot_g, grasa_g, restricciones, cap_scale)


# ═══════════════════════════ 10. ARMADO DE COMIDAS DEL DÍA ══════════════════

FOTO_BUSQUEDA = {
    'DESAYUNO': 'oatmeal banana yogurt breakfast bowl food photography',
    'ALMUERZO': 'grilled chicken rice salad plate food photography',
    'CENA': 'grilled salmon sweet potato vegetables plate food photography',
    'PRE-ENTRENO': 'banana toast honey coffee food photography',
    'POST-ENTRENO': 'protein shake banana smoothie food photography',
    'VENTANA': 'rice banana protein shake food photography',
    'SNACK': 'greek yogurt nuts fruit snack food photography',
}


def _foto(nombre_comida):
    key = nombre_comida.lower().replace('-', '_').replace(' ', '_')
    busqueda = FOTO_BUSQUEDA.get(nombre_comida, 'healthy food photography')
    try:
        from noah_fuel_images import resolver_foto
        r = resolver_foto(key, busqueda)
    except Exception:
        r = {'disponible': False, 'url': None}
    return {'foto_key': key, 'foto_url': r.get('url'), 'foto_disponible': r.get('disponible', False)}


def armar_comidas(macros, entreno, restricciones, fecha, peso_kg=70):
    if not macros.get('disponible'):
        return []
    # Porciones proporcionales al peso real (70kg = referencia).
    # Mujer 50kg -> 0.71 (porciones menores), hombre 90kg -> 1.28 (mayores).
    # Universal: se adapta a cualquier atleta sin valores fijos.
    _cap_scale = max(0.6, min(1.5, (peso_kg or 70) / 70.0))
    cho, prot, grasa = macros['cho_g'], macros['prot_g'], macros['grasa_g']
    seed = date.fromisoformat(fecha).weekday()
    ya_entreno = entreno['ya_entreno_hoy']
    doble_turno = entreno['doble_turno']
    dia_descanso = entreno['dia_descanso']

    # (nombre, hora, % del día, tipo, snack_idx, factor de grasa)
    # Los % SUMAN 100 (antes sumaban 108 en dos de los escenarios) y la grasa
    # se concentra en las comidas lejos del entreno.
    if doble_turno:
        plan = [('DESAYUNO', '06:00', 0.15, 'liviano', 0, 1.0),
                ('PRE-ENTRENO', '07:00', 0.10, 'liviano', 0, 0.3),
                ('VENTANA', '10:30', 0.25, 'ventana_doble_turno', 0, 0.1),
                ('POST-ENTRENO', '17:30', 0.20, 'post_entreno', 0, 0.3),
                ('CENA', '21:00', 0.30, 'normal', 2, 1.0)]
    elif ya_entreno:
        plan = [('DESAYUNO', '07:00', 0.22, 'normal', 0, 1.0),
                ('POST-ENTRENO', '09:00', 0.13, 'post_entreno', 0, 0.3),
                ('ALMUERZO', '13:30', 0.27, 'normal', 0, 1.0),
                ('MERIENDA', '17:00', 0.13, 'merienda', 3, 1.0),
                ('CENA', '21:00', 0.25, 'normal', 2, 1.0)]
    elif not dia_descanso:
        plan = [('DESAYUNO', '07:30', 0.22, 'normal', 0, 1.0),
                ('ALMUERZO', '13:00', 0.25, 'normal', 0, 1.0),
                ('PRE-ENTRENO', '16:30', 0.13, 'liviano', 0, 0.3),
                ('POST-ENTRENO', '19:30', 0.15, 'post_entreno', 0, 0.3),
                ('CENA', '21:30', 0.25, 'normal', 2, 1.0)]
    else:
        plan = [('DESAYUNO', '08:00', 0.22, 'liviano', 0, 1.0),
                ('SNACK', '11:00', 0.10, 'liviano', 0, 1.0),
                ('ALMUERZO', '13:30', 0.28, 'normal', 0, 1.0),
                ('MERIENDA', '17:30', 0.12, 'merienda', 3, 1.0),
                ('CENA', '20:30', 0.28, 'normal', 2, 1.0)]

    suma_pct = sum(p[2] for p in plan)
    suma_grasa_w = sum(p[2] * p[5] for p in plan)
    kcal_total = cho * 4 + prot * 4 + grasa * 9

    comidas = []
    for nombre, hora, pct, tipo, snack_idx, ff in plan:
        pct_n = pct / suma_pct
        c_cho, c_prot = cho * pct_n, prot * pct_n
        c_grasa = grasa * (pct * ff) / suma_grasa_w
        kcal_t = c_cho * 4 + c_prot * 4 + c_grasa * 9
        cap = min(1.7, max(1.0, kcal_t / 800.0))     # días enormes -> porciones algo mayores
        plato = construir_plato(round(c_cho), round(c_prot), round(c_grasa), tipo, restricciones,
                                seed + snack_idx, es_desayuno=(nombre == 'DESAYUNO'), cap_scale=_cap_scale)
        comidas.append({
            'nombre': nombre, 'hora': hora,
            'alimentos': plato['items'],
            'cho_g': plato['macros']['cho_g'], 'prot_g': plato['macros']['prot_g'],
            'grasa_g': plato['macros']['grasa_g'], 'kcal': plato['macros']['kcal'],
            'kcal_objetivo': round(kcal_t),
            **_foto(nombre),
        })
    return comidas


# ═══════════════════════════ 11. SUPLEMENTOS ════════════════════════════════

CAFEINA_MAX_DIA_MG = 400  # EFSA 2015

def armar_suplementos(entreno, bio_eval, deporte_ppal, peso_kg=None):
    """Lista corta, sin duplicados y con cada item marcado como opcional: la
    base es la comida. `categoria`: rendimiento / salud / situacional."""
    sup = []

    def add(item, dosis, timing, motivo, evidencia, categoria):
        sup.append({'item': item, 'dosis': dosis, 'timing': timing, 'motivo': motivo,
                    'evidencia': evidencia, 'categoria': categoria, 'opcional': True})

    usar = entreno.get('usar_para_calculo') or {}
    detalle = usar.get('detalle') or []

    add('Creatina monohidrato', '3-5g/día', 'Diario, cualquier hora',
        'Fuerza y esfuerzos repetidos. Beneficio menor en resistencia pura; puede sumar 1-2 kg de agua.',
        'GOOD EVIDENCE', 'rendimiento')
    add('Proteína whey', '20-40g', 'Post-entreno o para llegar a la proteína del día',
        'Práctico si con comida no llegás al objetivo.', 'STRONG EVIDENCE', 'rendimiento')
    add('Vitamina D3', '1000-2000 UI/día (confirmar con análisis)', 'Con comida con grasa',
        'Solo si tu análisis de sangre muestra déficit.', 'GOOD EVIDENCE', 'salud')

    dosis_cafe = int(round((3 * peso_kg) / 10.0) * 10) if peso_kg else 200
    dosis_cafe = min(max(dosis_cafe, 100), 300)
    sesiones_intensas = [d for d in detalle if d.get('tss', 0) >= 50 or d.get('dur_min', 0) >= 60]
    if sesiones_intensas:
        s = max(sesiones_intensas, key=lambda d: d.get('tss', 0))
        timing = '60min antes (nadadores: más anticipación)' if s.get('deporte') == 'swimming' else '30-60min antes'
        add('Cafeína', f'{dosis_cafe}mg (~3mg/kg)', timing + ' de la sesión clave',
            f'sesión de {s.get("deporte")} exigente. Una sola toma al día; tope {CAFEINA_MAX_DIA_MG}mg/día (EFSA 2015).',
            'STRONG EVIDENCE', 'situacional')

    if any(d.get('dur_min', 0) >= 120 for d in detalle):
        add('Electrolitos', '500-1000mg Na/h', 'Durante la sesión', 'sesión larga (>2h)', 'STRONG EVIDENCE', 'situacional')
    if bio_eval['hrv_bajo']:
        add('Omega-3 (EPA/DHA)', '2-3g/día', 'Con la cena', 'HRV por debajo de tu baseline reciente',
            'MODERATE EVIDENCE', 'situacional')
    if bio_eval['sleep_corto']:
        add('Magnesio', '200-400mg', 'Con la cena', 'sueño corto (<6.5h)', 'MODERATE EVIDENCE', 'situacional')

    return sup


# ═══════════════════════════ 12. HIDRATACIÓN ════════════════════════════════

SUDORACION_L_H = {'swimming': 0.4, 'running': 1.0, 'cycling': 0.75}

def calcular_hidratacion(peso_kg, entreno):
    if not peso_kg:
        return {'disponible': False}
    base_ml = round(peso_kg * 35)
    usar = entreno.get('usar_para_calculo') or {}
    entreno_ml = 0
    for s in usar.get('detalle', []):
        tasa = SUDORACION_L_H.get(s.get('deporte'), 0.6)
        entreno_ml += tasa * (s.get('dur_min', 0) / 60) * 1000
    total_ml = round(base_ml + entreno_ml)
    return {'disponible': True, 'total_ml': total_ml, 'base_ml': base_ml, 'entreno_ml': round(entreno_ml),
            'sodio_nota': '500-1000mg Na/L de sudor en sesiones largas o con calor (Shirreffs & Sawka 2011)',
            'fuente': 'ACSM Position Stand 2007 — 35ml/kg base + sudoración estimada por deporte/duración'}


# ═══════════════════════════ 13. RESTRICCIONES / PREFERENCIAS ═══════════════

def obtener_restricciones(conn, atleta_id):
    rows = _query(conn, "SELECT key, value FROM atleta_preferencias WHERE atleta_id=%s", [atleta_id])
    prefs = {k: v for k, v in rows}
    restricciones = [k for k in ('vegetariano', 'vegano', 'celiaco', 'sin_lactosa') if prefs.get(k) == 'true' or k in prefs]
    return restricciones, prefs


# ═══════════════════════════ 14. ONBOARDING ═════════════════════════════════

CAMPOS_REQUERIDOS = ['peso_kg', 'altura_cm', 'edad', 'sexo']
QUICK_ACTIONS = [
    {'id': 'pre_workout', 'label': '¿Qué como antes de entrenar?'},
    {'id': 'post_workout', 'label': '¿Qué como después de entrenar?'},
    {'id': 'change_meal', 'label': 'Cambiar una comida'},
    {'id': 'why_carbs', 'label': '¿Por qué este nivel de carbohidratos?'},
    {'id': 'portions', 'label': 'Mostrar porciones en medidas caseras'},
]

def campos_faltantes(perfil):
    faltan = [c for c in CAMPOS_REQUERIDOS if not perfil.get(c)]
    return {'requeridos_faltantes': faltan, 'onboarding_completo': len(faltan) == 0}


# ═══════════════════════════ 15. NOAH EAT — PARSEO Y MEMORIA ═══════════════

PROMPT_EAT = """Sos un calculador nutricional. El usuario dice qué comió en lenguaje natural
argentino/latino. Respondé SOLO JSON sin backticks ni texto extra:
{"alimentos":[{"nombre":"...","cantidad_g":200,"cho_g":0,"prot_g":50,"grasa_g":6,"kcal":254}],
"total":{"cho_g":0,"prot_g":50,"grasa_g":6,"kcal":254}}
Si no dice cantidad, estimá una porción normal argentina. Tabla USDA/ARGENFOODS."""

PROMPT_FUEL_CHAT = """Sos NOAH, el asistente nutricional deportivo dentro de la app NOAH.
Contexto real del atleta hoy:
{contexto_atleta}

Reglas:
- No sos nutricionista ni médico; ante dudas clínicas, sugerí consultar un profesional.
- Distinguí dato / interpretación / recomendación cuando uses biomarcadores. Nunca diagnostiques.
- Si falta un dato imprescindible, pedilo puntualmente (no una lista larga).
- Respuestas cortas, concretas y en español informal — como hablaría un coach, no un manual."""

# Fallback si Groq no responde: parser básico por regex para los alimentos
# más comunes (doc pide esto explícitamente para no dejar a NOAH Eat sin
# funcionar si la API cae).
_PATRONES_FALLBACK = [
    (r'pechuga|pollo', 'pollo_pechuga', 200),
    (r'arroz', 'arroz_cocido', 200),
    (r'fideos|pasta', 'pasta_cocida', 200),
    (r'banana', 'banana', 120),
    (r'huevo', 'huevo', 60),
    (r'yogur', 'yogur_griego', 170),
    (r'atun', 'atun_lata', 120),
    (r'salm[oó]n', 'salmon', 150),
    (r'batata', 'batata', 200),
    (r'avena', 'avena', 60),
]

def _parsear_fallback(texto):
    texto_l = texto.lower()
    alimentos, total = [], {'cho_g': 0, 'prot_g': 0, 'grasa_g': 0, 'kcal': 0}
    for patron, alimento, gramos_default in _PATRONES_FALLBACK:
        if re.search(patron, texto_l):
            cho, prot, gr, kcal100 = ALIMENTOS[alimento]
            f = gramos_default / 100
            item = {'nombre': alimento.replace('_', ' '), 'cantidad_g': gramos_default,
                    'cho_g': round(cho * f), 'prot_g': round(prot * f), 'grasa_g': round(gr * f), 'kcal': round(kcal100 * f)}
            alimentos.append(item)
            for k in ('cho_g', 'prot_g', 'grasa_g', 'kcal'):
                total[k] += item[k]
    if not alimentos:
        return {'ok': False, 'error': 'No reconocí alimentos en el texto. Para mayor precisión, ingresá las cantidades.'}
    return {'ok': True, 'alimentos': alimentos, 'total': total,
            'aproximado': True, 'nota': 'Calculado con datos aproximados (Groq no disponible).'}


def _llamar_groq(system_prompt, user_text, max_tokens=500):
    import requests
    key = os.environ.get('GROQ_API_KEY')
    if not key:
        return {'ok': False, 'error': 'GROQ_API_KEY no configurada'}
    try:
        r = requests.post('https://api.groq.com/openai/v1/chat/completions',
            headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
            json={'model': os.environ.get('GROQ_MODEL', 'openai/gpt-oss-120b'),
                  'messages': [{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_text}],
                  'max_tokens': max_tokens, 'temperature': 0.2}, timeout=20)
        if r.status_code != 200:
            return {'ok': False, 'error': f'Error {r.status_code}'}
        return {'ok': True, 'texto': r.json()['choices'][0]['message']['content'].strip()}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def noah_eat_parsear(texto):
    r = _llamar_groq(PROMPT_EAT, texto, max_tokens=800)
    if not r['ok']:
        return _parsear_fallback(texto)
    t = r['texto']
    if t.startswith('```'):
        t = t.split('\n', 1)[1]
    if t.endswith('```'):
        t = t[:-3]
    try:
        p = json.loads(t.strip())
        p['ok'] = True
        return p
    except Exception:
        return _parsear_fallback(texto)


def noah_eat_registrar(conn, atleta_id, texto, fecha=None, momento=None):
    """Parsea lo que comió el atleta y lo guarda en nutricion_log (memoria
    para el día siguiente)."""
    fecha = fecha or str(date.today())
    comido = noah_eat_parsear(texto)
    if not comido.get('ok'):
        return comido
    total = comido.get('total', {})
    try:
        cur = conn.cursor()
        cur.execute("""INSERT INTO nutricion_log (atleta_id, fecha, momento, texto_libre, alimentos, cho_g, prot_g, grasa_g, kcal)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    [atleta_id, fecha, momento, texto, json.dumps(comido.get('alimentos', []), ensure_ascii=False),
                     _sf(total.get('cho_g'), 0), _sf(total.get('prot_g'), 0), _sf(total.get('grasa_g'), 0), _sf(total.get('kcal'), 0)])
        conn.commit()
    except Exception:
        _rollback_safe(conn)
        return {'ok': False, 'error': 'No se pudo guardar el registro.'}
    return {'ok': True, 'comido': comido}


def noah_eat_balance(macros_objetivo, comido):
    if not comido.get('ok') or not macros_objetivo:
        return None
    t = comido.get('total', {})
    cho_c, prot_c, grasa_c = _sf(t.get('cho_g'), 0), _sf(t.get('prot_g'), 0), _sf(t.get('grasa_g'), 0)
    cho_o, prot_o, grasa_o = macros_objetivo['cho_g'], macros_objetivo['prot_g'], macros_objetivo['grasa_g']
    fc, fp, fg = max(0, cho_o - cho_c), max(0, prot_o - prot_c), max(0, grasa_o - grasa_c)
    sug = []
    if fp > 15:
        sug.append(f'Falta {round(fp)}g proteína → {round(fp/0.25)}g pollo o {round(fp/0.8)}g whey')
    if fc > 30:
        sug.append(f'Falta {round(fc)}g CHO → {round(fc/0.28)}g arroz o {round(fc/0.23)}g banana')
    if fg > 10:
        sug.append(f'Falta {round(fg)}g grasa → {round(fg/0.50)}g frutos secos')
    return {'comido': {'cho_g': cho_c, 'prot_g': prot_c, 'grasa_g': grasa_c, 'kcal': _sf(t.get('kcal'), 0)},
            'objetivo': {'cho_g': cho_o, 'prot_g': prot_o, 'grasa_g': grasa_o},
            'falta': {'cho_g': fc, 'prot_g': fp, 'grasa_g': fg}, 'sugerencias': sug}


def noah_fuel_chat(atleta_contexto, pregunta_usuario):
    contexto_txt = json.dumps(atleta_contexto, ensure_ascii=False, default=str)[:4000]
    return _llamar_groq(PROMPT_FUEL_CHAT.format(contexto_atleta=contexto_txt), pregunta_usuario)


# ═══════════════════════════ 16. NARRATIVA ══════════════════════════════════

def generar_narrativa(entreno, bio_eval, carrera, recuperacion_ayer):
    if carrera and carrera['dias_restantes'] is not None and 0 <= carrera['dias_restantes'] <= 3:
        return f"Carb loading activo — {carrera['nombre']} en {carrera['dias_restantes']} día(s)."
    if entreno['doble_turno']:
        return 'Doble turno hoy: la ventana entre sesiones es la comida más importante del día.'
    if recuperacion_ayer:
        return f"Ayer entrenaste fuerte ({recuperacion_ayer['sesion']}) — hoy subo carbohidratos para la resíntesis."
    if bio_eval['prioridad_recuperacion']:
        return 'Tus señales de recuperación están bajas — prioricé disponibilidad de carbohidratos y descanso.'
    if entreno['dia_descanso']:
        return 'Día sin entrenamiento planificado — carbohidratos moderados, proteína alta para mantener masa magra.'
    if entreno['ya_entreno_hoy']:
        return 'Plan construido con los datos reales de tu entrenamiento de hoy.'
    return 'Tus señales están equilibradas — plan alineado a tu entrenamiento planificado de hoy.'


def calcular_alertas(ea, bio_eval, onboarding):
    alertas = []
    if ea.get('disponible') and ea['status'] == 'alarma':
        alertas.append({'tipo': 'ea_baja', 'severidad': 'alta',
                        'texto': f"Energy Availability {ea['valor']} kcal/kg FFM — por debajo de 30, riesgo de RED-S (Mountjoy 2018)."})
    elif ea.get('disponible') and ea['status'] == 'atencion':
        alertas.append({'tipo': 'ea_atencion', 'severidad': 'media',
                        'texto': f"Energy Availability {ea['valor']} kcal/kg FFM — zona de atención."})
    if bio_eval['carga_alta']:
        alertas.append({'tipo': 'carga_alta', 'severidad': 'media', 'texto': 'Ratio de carga aguda:crónica elevado.'})
    if not onboarding['onboarding_completo']:
        alertas.append({'tipo': 'onboarding', 'severidad': 'baja',
                        'texto': f"Faltan datos del perfil: {', '.join(onboarding['requeridos_faltantes'])}."})
    return alertas


# ═══════════════════════════ 17. ORQUESTADOR ════════════════════════════════

def calcular_dia(conn, atleta_id, fecha, permitir_memoria=True):
    """Corazón del motor. `permitir_memoria=False` evita la recursión al
    calcular el objetivo de AYER (solo se necesita para comparar, no hace
    falta que ese cálculo compense contra el día anterior al anterior)."""
    perfil = obtener_perfil(conn, atleta_id)
    if not perfil:
        return {'disponible': False, 'error': 'Atleta no encontrado'}

    bio = obtener_bio(conn, atleta_id, fecha)
    bio_7d = obtener_bio_promedio_7d(conn, atleta_id, fecha)
    carga_ratio = calcular_carga_aguda_cronica(conn, atleta_id, fecha)
    bio_eval = evaluar_biomarcadores(bio, bio_7d, carga_ratio)

    planificadas = obtener_sesiones_planificadas_hoy(conn, atleta_id, fecha)
    reales = obtener_sesiones_reales(conn, atleta_id, fecha)
    tmb = calcular_tmb(perfil['peso_kg'], perfil['altura_cm'], perfil['edad'], perfil['sexo'])
    neat = calcular_neat(tmb.get('kcal'))
    entreno = calcular_entreno_dia(planificadas, reales, perfil['peso_kg'], tmb.get('kcal'))

    carrera = obtener_carrera_proxima(conn, atleta_id, fecha)
    recuperacion_ayer = calcular_recuperacion_pendiente(conn, atleta_id, fecha)

    base_kcal = (tmb.get('kcal') or 0) + (neat.get('kcal') or 0)
    macros = calcular_macros_dia(perfil['peso_kg'], entreno, bio_eval, carrera, perfil['objetivo'],
                                 base_kcal=base_kcal, recuperacion_pendiente=bool(recuperacion_ayer))

    compensacion = None
    if permitir_memoria and macros.get('disponible'):
        compensacion = calcular_compensacion_memoria(conn, atleta_id, fecha, macros['total_kcal'])
        if compensacion:
            extra_cho = round(compensacion['compensacion_kcal'] / 4)
            macros['cho_g'] += extra_cho
            macros['total_kcal'] += compensacion['compensacion_kcal']
            macros['cho_gkg'] = round(macros['cho_g'] / perfil['peso_kg'], 1)

    ffm = calcular_ffm(perfil['peso_kg'], perfil['altura_cm'], perfil['sexo'], perfil['body_fat_pct']) if perfil['peso_kg'] else {'kg': None, 'estimado': True}
    ea = calcular_ea(macros, entreno, ffm, perfil['sexo'])

    restricciones, prefs = obtener_restricciones(conn, atleta_id)
    cho_durante = calcular_cho_durante(entreno)
    macros_comidas = dict(macros)
    if macros.get('disponible'):
        macros_comidas['cho_g'] = max(0, macros['cho_g'] - cho_durante['total_g'])
    comidas = armar_comidas(macros_comidas, entreno, restricciones, fecha, perfil.get('peso_kg', 70))
    kcal_comidas = sum(c['kcal'] for c in comidas)
    suplementos = armar_suplementos(entreno, bio_eval, perfil['deporte_ppal'], perfil['peso_kg'])
    hidratacion = calcular_hidratacion(perfil['peso_kg'], entreno)

    onboarding = campos_faltantes(perfil)
    narrativa = generar_narrativa(entreno, bio_eval, carrera, recuperacion_ayer)
    alertas = calcular_alertas(ea, bio_eval, onboarding)

    _u = entreno.get('usar_para_calculo') or {}
    entreno_kcal = _u.get('kcal_neto', _u.get('kcal', 0))

    return {
        'disponible': True, 'atleta': perfil['nombre'], 'fecha': fecha,
        'nivel1': {
            'narrativa': narrativa,
            'kcal_dia': macros.get('total_kcal'),
            'macros': {
                'cho_g': macros.get('cho_g'), 'cho_gkg': macros.get('cho_gkg'),
                'prot_g': macros.get('prot_g'), 'prot_gkg': macros.get('prot_gkg'),
                'grasa_g': macros.get('grasa_g'), 'grasa_gkg': macros.get('grasa_gkg'),
            } if macros.get('disponible') else None,
            'entreno_hoy': entreno.get('usar_para_calculo'),
            'doble_turno': entreno['doble_turno'], 'dia_descanso': entreno['dia_descanso'],
            'comidas': comidas,
            'cho_durante_g': cho_durante['total_g'],
            'durante': cho_durante['detalle'],
            'suplementos': suplementos,
            'hidratacion_ml': hidratacion.get('total_ml'),
            'alertas': alertas,
        },
        'nivel2': {
            'gasto_desglose': {'tmb': tmb.get('kcal'), 'neat': neat.get('kcal'), 'entreno': entreno_kcal,
                               'tef': macros.get('tef_kcal'),
                               'total_gasto_estimado': macros.get('gasto_total_kcal'),
                               'objetivo_kcal': macros.get('total_kcal'),
                               'balance_kcal': macros.get('balance_kcal'),
                               'balance_pct': macros.get('balance_pct'),
                               'objetivo_tipo': macros.get('objetivo_tipo')},
            'chequeo_energia': {'kcal_dia': macros.get('total_kcal'), 'kcal_comidas': kcal_comidas,
                                'kcal_durante': cho_durante['kcal'],
                                'diferencia_pct': round(((kcal_comidas + cho_durante['kcal']) - (macros.get('total_kcal') or 0))
                                                        / max(macros.get('total_kcal') or 1, 1) * 100, 1)},
            'protocolo_cho': {'fuente': macros.get('cho_fuente'), 'clasificacion': macros.get('cho_clasificacion'),
                              'rango': macros.get('cho_rango'), 'seleccionado_gkg': macros.get('cho_gkg')},
            'protocolo_prot': {'fuente': macros.get('prot_fuente'), 'rango': macros.get('prot_rango'),
                               'seleccionado_gkg': macros.get('prot_gkg')},
            'protocolo_grasa': {'fuente': macros.get('grasa_fuente'), 'seleccionado_gkg': macros.get('grasa_gkg')},
            'ea': ea,
            'ajustes_bio': bio_eval['ajustes'],
            'carga_aguda_cronica': carga_ratio,
            'recuperacion_ayer': recuperacion_ayer,
            'compensacion_memoria': compensacion,
            'carrera_proxima': carrera,
            'hidratacion_detalle': hidratacion,
        },
        'onboarding': onboarding,
        'restricciones_aplicadas': restricciones,
        'quick_actions': QUICK_ACTIONS,
        'limitaciones': [
            'NEAT estimado (sin dato real de actividad diaria de wearable).',
            'Gasto = basal + NEAT + entreno neto (sin el reposo ya contado) + 8% efecto térmico. Entrada = salida salvo objetivo.',
            'Gasto calórico por sesión estimado cuando no hay calorías reales de Garmin.',
            'FFM ' + ('estimada (Boer 1984, sin % de grasa medido).' if ffm.get('estimado') else 'medida.'),
            'Sin dato de ciclo menstrual (si aplica, cargarlo mejora la precisión de EA).',
            'Horarios de comida son bloques típicos, no están atados a la hora real de la sesión (la prescripción no guarda hora de sesión todavía).',
        ],
    }


def noah_fuel_dia(conn, atleta_id, fecha=None):
    fecha = fecha or str(date.today())
    try:
        return calcular_dia(conn, atleta_id, fecha, permitir_memoria=True)
    except Exception as e:
        _rollback_safe(conn)
        import traceback; traceback.print_exc()
        return {'disponible': False, 'error': str(e)}
