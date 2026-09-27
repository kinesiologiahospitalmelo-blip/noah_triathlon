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
        SELECT sport, duration_min, tss_total, calorias, distance_km
        FROM sesiones
        WHERE atleta_id=%s AND fecha=%s AND tss_total>0
          AND (fuente IS NULL OR fuente NOT IN %s)
    """, [atleta_id, fecha, FUENTES_NO_REAL])
    return [{'deporte': r[0], 'dur_min': _sf(r[1], 0), 'tss': _sf(r[2], 0),
             'kcal_real': _sf(r[3]), 'distancia_km': r[4]} for r in rows]


def _kcal_estimado_sesion(dur_min, tss, peso_kg):
    """Estimación de gasto por sesión cuando no hay calorías reales de
    Garmin. Reemplaza el cálculo de v3 (tss*peso*0.01, que para un TSS 70 en
    un atleta de 65kg daba ~45 kcal -- claramente roto). Se calibra por
    kcal/min según la intensidad implícita en el TSS (aprox. MET 5 a 12
    para deportes de resistencia, escalado por peso corporal), y se marca
    siempre como estimación."""
    if not dur_min or not peso_kg:
        return 0
    dur_h = dur_min / 60
    intensidad = min((tss / (dur_h * 100)) ** 0.5, 1.2) if tss and dur_h > 0 else 0.65
    kcal_min_por_kg = 0.08 + 0.08 * intensidad  # ~0.08 (suave) a ~0.176 (muy duro)
    return round(dur_min * peso_kg * kcal_min_por_kg)


def calcular_entreno_dia(planificadas, reales, peso_kg):
    def _resumen(rows, es_real):
        det, tot_kcal, tot_tss, tot_min = [], 0, 0, 0
        for r in rows:
            kcal = r.get('kcal_real') if es_real else None
            if not kcal or kcal <= 0:
                kcal = _kcal_estimado_sesion(r['dur_min'], r['tss'], peso_kg)
            det.append({'deporte': r['deporte'], 'dur_min': round(r['dur_min']),
                        'tss': round(r['tss']), 'kcal': round(kcal),
                        'kcal_estimado': not bool(r.get('kcal_real'))})
            tot_kcal += kcal; tot_tss += r['tss']; tot_min += r['dur_min']
        return {'detalle': det, 'dur_min': round(tot_min), 'tss': round(tot_tss), 'kcal': round(tot_kcal)}

    plan = _resumen(planificadas, False) if planificadas else None
    real = _resumen(reales, True) if reales else None
    usar = real or plan  # si ya entrenó, mandan los datos reales; si no, el plan
    n_sesiones = len(reales) if reales else len(planificadas)

    return {
        'planificado': plan, 'real': real, 'usar_para_calculo': usar,
        'doble_turno': n_sesiones >= 2, 'dia_descanso': n_sesiones == 0,
        'ya_entreno_hoy': bool(reales),
    }


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


def calcular_macros_dia(peso_kg, entreno, bio_eval, carrera, objetivo):
    if not peso_kg:
        return {'disponible': False, 'mensaje': 'Falta el peso del atleta.'}

    usar = entreno['usar_para_calculo'] or {}
    dur_h = usar.get('dur_min', 0) / 60
    tss = usar.get('tss', 0)
    intensidad = min((tss / (dur_h * 100)) ** 0.5, 1.2) if tss and dur_h > 0 else (0.6 if dur_h > 0 else 0)

    dias_carrera = carrera['dias_restantes'] if carrera else None
    prioridad_carrera = carrera['prioridad'] if carrera else None

    cho_clasif = clasificar_cho(dur_h, intensidad, entreno['dia_descanso'], dias_carrera, prioridad_carrera)
    cho_gkg = seleccionar_cho_gkg(cho_clasif['rango'], entreno['doble_turno'],
                                   recuperacion_pendiente=False,  # se ajusta afuera con el bonus de ayer
                                   prioridad_recuperacion=bio_eval['prioridad_recuperacion'])
    prot_gkg = seleccionar_prot_gkg(entreno['dia_descanso'], entreno['doble_turno'], dur_h)

    cho_g = round(peso_kg * cho_gkg)
    prot_g = round(peso_kg * prot_gkg)
    cho_kcal, prot_kcal = cho_g * 4, prot_g * 4

    piso_grasa_gkg = 0.7 if objetivo == 'composicion' else 0.9
    piso_grasa_g = peso_kg * piso_grasa_gkg
    gasto_estimado = (entreno.get('usar_para_calculo') or {}).get('kcal', 0)
    grasa_g = max(piso_grasa_g, piso_grasa_g)  # el piso manda; no se resta de nada más (ver nota abajo)
    grasa_g = round(max(piso_grasa_g, piso_grasa_g))

    total_kcal = cho_kcal + prot_kcal + round(grasa_g) * 9

    return {
        'disponible': True,
        'cho_g': cho_g, 'cho_gkg': cho_gkg, 'cho_fuente': 'Burke/Impey 2018', 'cho_clasificacion': cho_clasif['texto'], 'cho_rango': cho_clasif['rango'],
        'prot_g': prot_g, 'prot_gkg': prot_gkg, 'prot_fuente': 'ISSN 2017 (Kerksick et al.)', 'prot_rango': (1.4, 2.0),
        'grasa_g': round(grasa_g), 'grasa_gkg': round(grasa_g / peso_kg, 2), 'grasa_fuente': 'piso hormonal mínimo',
        'total_kcal': total_kcal,
        'intensidad_estimada': round(intensidad, 2),
    }


# ═══════════════════════════ 7. ENERGY AVAILABILITY (RED-S) ════════════════

def calcular_ea(macros, entreno, ffm, sexo):
    if not macros.get('disponible') or not ffm.get('kg'):
        return {'disponible': False}
    gasto_ejercicio = (entreno.get('usar_para_calculo') or {}).get('kcal', 0)
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
    'avena':            (60, 13, 7,   379),
    'banana':           (23, 1,  0.3, 89),
    'arroz_cocido':     (28, 2.7,0.3, 130),
    'arroz_integral_cocido': (23, 2.6, 0.9, 111),
    'pasta_cocida':     (25, 5,  1,   131),
    'quinoa_cocida':    (21, 4.4,1.9, 120),
    'batata':           (20, 2,  0.1, 86),
    'pan_integral':     (42, 9,  3,   247),
    'pan_sin_tacc':     (52, 3,  4,   260),
    'pollo_pechuga':    (0,  25, 3,   130),
    'salmon':           (0,  22, 13,  208),
    'atun_lata':        (0,  26, 1,   116),
    'carne_magra':      (0,  27, 5,   158),
    'huevo':            (1,  13, 11,  155),
    'tofu':             (2,  8,  4.8, 76),
    'lentejas_cocidas': (20, 9,  0.4, 116),
    'garbanzos_cocidos':(27, 8,  2.6, 164),
    'proteina_arveja':  (5,  78, 6,   380),
    'yogur_griego':     (4,  10, 5,   100),
    'yogur_coco':       (7,  1,  6,   90),
    'leche':            (5,  3.3,3.5, 65),
    'leche_almendras':  (1,  0.5,1.1, 15),
    'whey_protein':     (3,  80, 5,   400),
    'miel':             (82, 0.3,0,   304),
    'manteca_mani':     (20, 25, 50,  588),
    'aceite_oliva':     (0,  0,  100, 884),
    'granola':          (65, 10, 15,  450),
    'frutos_secos':     (15, 20, 50,  580),
    'queso_rallado':    (3,  28, 25,  350),
}

# medidas caseras en gramos, para mostrar "1 taza y 1/2" en vez de solo gramos
MEDIDAS_CASERAS = {
    'arroz_cocido': {'taza': 185}, 'arroz_integral_cocido': {'taza': 185},
    'pasta_cocida': {'plato': 200}, 'quinoa_cocida': {'taza': 185},
    'pollo_pechuga': {'unidad': 200, 'media unidad': 100}, 'banana': {'unidad': 120},
    'huevo': {'unidad': 60}, 'yogur_griego': {'pote': 170}, 'yogur_coco': {'pote': 170},
    'leche': {'vaso': 250}, 'leche_almendras': {'vaso': 250}, 'avena': {'taza': 80},
    'aceite_oliva': {'cucharada': 14}, 'miel': {'cucharada': 21},
    'pan_integral': {'rebanada': 30}, 'pan_sin_tacc': {'rebanada': 35},
    'queso_rallado': {'puñado': 30}, 'frutos_secos': {'puñado': 30}, 'manteca_mani': {'cucharada': 16},
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


def _medida_casera(alimento, gramos):
    medidas = MEDIDAS_CASERAS.get(alimento)
    if not medidas:
        return f'{gramos}g'
    unidad, base_g = next(iter(medidas.items()))
    cant = gramos / base_g
    if cant < 0.4:
        return f'{gramos}g'
    return f'{round(cant * 2) / 2:g} {unidad}{"s" if cant >= 1.5 and not unidad.endswith("a") else ""} ({gramos}g)'


def construir_plato(cho_g, prot_g, grasa_g, tipo, restricciones, seed, es_desayuno=False):
    """Arma un plato real optimizando hacia los macros target -- no divide
    el total entre 5 partes iguales. `seed` (día de la semana) rota la
    fuente de proteína/carbohidrato para variedad. `es_desayuno` usa un
    pool de alimentos de desayuno real (avena, tostadas, huevo) en vez de
    pollo+arroz a las 6 de la mañana."""
    variantes_prot_normal = ['pollo_pechuga', 'atun_lata', 'carne_magra']
    variantes_carb_normal = ['arroz_cocido', 'pasta_cocida', 'batata']
    variantes_prot_liviano = ['huevo', 'yogur_griego', 'atun_lata']
    variantes_desayuno_carb = ['avena', 'pan_integral', 'granola']
    variantes_desayuno_prot = ['yogur_griego', 'huevo', 'yogur_griego']

    if tipo == 'post_entreno':
        prot_base = _aplicar_restriccion('whey_protein', restricciones)
        carb_base = _aplicar_restriccion(variantes_carb_normal[seed % len(variantes_carb_normal)], restricciones)
    elif es_desayuno:
        prot_base = _aplicar_restriccion(variantes_desayuno_prot[seed % len(variantes_desayuno_prot)], restricciones)
        carb_base = _aplicar_restriccion(variantes_desayuno_carb[seed % len(variantes_desayuno_carb)], restricciones)
    elif tipo == 'liviano':
        prot_base = _aplicar_restriccion(variantes_prot_liviano[seed % len(variantes_prot_liviano)], restricciones)
        carb_base = _aplicar_restriccion(variantes_carb_normal[seed % len(variantes_carb_normal)], restricciones)
    else:
        prot_base = _aplicar_restriccion(variantes_prot_normal[seed % len(variantes_prot_normal)], restricciones)
        carb_base = _aplicar_restriccion(variantes_carb_normal[seed % len(variantes_carb_normal)], restricciones)

    if tipo == 'ventana_doble_turno':
        # Beelen 2010: CERO grasa/fibra en la ventana entre sesiones -> CHO simple
        carb_base = _aplicar_restriccion('arroz_cocido', restricciones)

    prot_100 = ALIMENTOS[prot_base]
    prot_gramos = round(prot_g / (prot_100[1] / 100)) if prot_100[1] > 0 else 0
    cho_cubierto = prot_100[0] * prot_gramos / 100

    carb_100 = ALIMENTOS[carb_base]
    cho_faltante = max(cho_g - cho_cubierto, 0)
    carb_gramos = round(cho_faltante / (carb_100[0] / 100)) if carb_100[0] > 0 else 0

    grasa_cubierta = prot_100[2] * prot_gramos / 100 + carb_100[2] * carb_gramos / 100
    grasa_faltante = max(grasa_g - grasa_cubierta, 0)

    items = [
        {'alimento': prot_base.replace('_', ' '), 'gramos': prot_gramos, 'medida': _medida_casera(prot_base, prot_gramos)},
        {'alimento': carb_base.replace('_', ' '), 'gramos': carb_gramos, 'medida': _medida_casera(carb_base, carb_gramos)},
    ]
    if tipo not in ('ventana_doble_turno',) and grasa_faltante > 4:
        aceite_g = round(grasa_faltante)
        items.append({'alimento': 'aceite de oliva', 'gramos': aceite_g, 'medida': _medida_casera('aceite_oliva', aceite_g)})
    if tipo == 'normal':
        items.append({'alimento': 'ensalada variada', 'gramos': None, 'medida': 'a gusto'})

    macros_reales = {
        'cho_g': round(cho_cubierto + carb_100[0] * carb_gramos / 100),
        'prot_g': round(prot_100[1] * prot_gramos / 100),
        'grasa_g': round(grasa_cubierta + (grasa_faltante if tipo not in ('ventana_doble_turno',) else 0)),
    }
    macros_reales['kcal'] = macros_reales['cho_g'] * 4 + macros_reales['prot_g'] * 4 + macros_reales['grasa_g'] * 9
    return {'items': items, 'macros': macros_reales}


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


def armar_comidas(macros, entreno, restricciones, fecha):
    if not macros.get('disponible'):
        return []
    cho, prot, grasa = macros['cho_g'], macros['prot_g'], macros['grasa_g']
    seed = date.fromisoformat(fecha).weekday()
    ya_entreno = entreno['ya_entreno_hoy']
    doble_turno = entreno['doble_turno']
    dia_descanso = entreno['dia_descanso']

    comidas = []

    def agregar(nombre, hora, pct, tipo):
        c_cho, c_prot, c_grasa = round(cho * pct), round(prot * pct), round(grasa * pct)
        plato = construir_plato(c_cho, c_prot, c_grasa, tipo, restricciones, seed, es_desayuno=(nombre == 'DESAYUNO'))
        comidas.append({
            'nombre': nombre, 'hora': hora,
            'alimentos': plato['items'],
            'cho_g': plato['macros']['cho_g'], 'prot_g': plato['macros']['prot_g'],
            'grasa_g': plato['macros']['grasa_g'], 'kcal': plato['macros']['kcal'],
            **_foto(nombre),
        })

    if doble_turno:
        # Ventana entre sesiones = lo más crítico (Beelen 2010): resíntesis
        # rápida, cero grasa/fibra, CHO simple + proteína, sin dividir en
        # "post normal" + "pre normal" por separado.
        agregar('DESAYUNO', '06:00', 0.15, 'liviano')
        agregar('PRE-ENTRENO', '07:00', 0.10, 'liviano')
        agregar('VENTANA', '10:30', 0.25, 'ventana_doble_turno')
        agregar('POST-ENTRENO', '17:30', 0.20, 'post_entreno')
        agregar('CENA', '21:00', 0.30, 'normal')
    elif ya_entreno:
        agregar('DESAYUNO', '07:00', 0.20, 'normal')
        agregar('POST-ENTRENO', '09:00', 0.15, 'post_entreno')
        agregar('ALMUERZO', '13:30', 0.27, 'normal')
        agregar('SNACK', '17:00', 0.10, 'liviano')
        agregar('CENA', '21:00', 0.28, 'normal')
    elif not dia_descanso:
        # entreno pendiente hoy (según prescripción), aún no ejecutado
        agregar('DESAYUNO', '07:30', 0.22, 'normal')
        agregar('ALMUERZO', '13:00', 0.25, 'normal')
        agregar('PRE-ENTRENO', '16:30', 0.13, 'liviano')
        agregar('POST-ENTRENO', '19:30', 0.15, 'post_entreno')
        agregar('CENA', '21:30', 0.25, 'normal')
    else:
        # día de descanso: comidas livianas, distribuidas uniformemente
        agregar('DESAYUNO', '08:00', 0.20, 'liviano')
        agregar('SNACK', '11:00', 0.10, 'liviano')
        agregar('ALMUERZO', '13:30', 0.28, 'normal')
        agregar('SNACK', '17:30', 0.10, 'liviano')
        agregar('CENA', '20:30', 0.32, 'normal')

    return comidas


# ═══════════════════════════ 11. SUPLEMENTOS ════════════════════════════════

CAFEINA_MAX_DIA_MG = 400  # EFSA 2015

def armar_suplementos(entreno, bio_eval, deporte_ppal):
    sup = []
    cafeina_acumulada = 0
    usar = entreno.get('usar_para_calculo') or {}
    detalle = usar.get('detalle') or []

    sesiones_intensas = [d for d in detalle if d.get('tss', 0) >= 50 or d.get('dur_min', 0) >= 60]
    for s in sesiones_intensas:
        dosis_mg = 200  # ~3mg/kg genérico si no hay peso a mano en esta capa
        if cafeina_acumulada + dosis_mg <= CAFEINA_MAX_DIA_MG:
            timing = '60min antes (nadadores: más anticipación por digestión + pileta)' if s.get('deporte') == 'swimming' else '30-60min antes'
            sup.append({'item': 'Cafeína', 'dosis': f'{dosis_mg}mg (~3-6mg/kg)', 'timing': timing,
                        'motivo': f'sesión de {s.get("deporte")} exigente', 'evidencia': 'STRONG EVIDENCE'})
            cafeina_acumulada += dosis_mg
        if s.get('dur_min', 0) >= 120:
            sup.append({'item': 'Electrolitos', 'dosis': '500-1000mg Na/h', 'timing': 'durante',
                        'motivo': 'sesión larga (>2h)', 'evidencia': 'STRONG EVIDENCE'})

    if detalle:
        sup.append({'item': 'Creatina', 'dosis': '3-5g/día', 'timing': 'con cualquier comida',
                    'motivo': 'día de entrenamiento', 'evidencia': 'STRONG EVIDENCE'})

    if bio_eval['hrv_bajo']:
        sup.append({'item': 'Omega-3', 'dosis': '2-3g EPA+DHA', 'timing': 'con la cena',
                    'motivo': 'HRV por debajo de tu baseline reciente', 'evidencia': 'MODERATE EVIDENCE'})
    if bio_eval['sleep_corto']:
        sup.append({'item': 'Magnesio', 'dosis': '200-400mg', 'timing': 'con la cena',
                    'motivo': 'sueño corto (<6.5h)', 'evidencia': 'MODERATE EVIDENCE'})

    if cafeina_acumulada > 0:
        sup.append({'item': '⚠ Cafeína acumulada hoy', 'dosis': f'{cafeina_acumulada}/{CAFEINA_MAX_DIA_MG}mg',
                    'timing': None, 'motivo': 'EFSA 2015 — no superar 400mg/día', 'evidencia': 'INFO'})

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
    entreno = calcular_entreno_dia(planificadas, reales, perfil['peso_kg'])

    carrera = obtener_carrera_proxima(conn, atleta_id, fecha)
    recuperacion_ayer = calcular_recuperacion_pendiente(conn, atleta_id, fecha)

    macros = calcular_macros_dia(perfil['peso_kg'], entreno, bio_eval, carrera, perfil['objetivo'])
    if recuperacion_ayer and macros.get('disponible'):
        extra_cho = round(macros['cho_g'] * recuperacion_ayer['ajuste_cho_pct'] / 100)
        macros['cho_g'] += extra_cho
        macros['total_kcal'] += extra_cho * 4
        macros['cho_gkg'] = round(macros['cho_g'] / perfil['peso_kg'], 1)

    compensacion = None
    if permitir_memoria and macros.get('disponible'):
        compensacion = calcular_compensacion_memoria(conn, atleta_id, fecha, macros['total_kcal'])
        if compensacion:
            extra_cho = round(compensacion['compensacion_kcal'] / 4)
            macros['cho_g'] += extra_cho
            macros['total_kcal'] += compensacion['compensacion_kcal']
            macros['cho_gkg'] = round(macros['cho_g'] / perfil['peso_kg'], 1)

    tmb = calcular_tmb(perfil['peso_kg'], perfil['altura_cm'], perfil['edad'], perfil['sexo'])
    neat = calcular_neat(tmb.get('kcal'))
    ffm = calcular_ffm(perfil['peso_kg'], perfil['altura_cm'], perfil['sexo'], perfil['body_fat_pct']) if perfil['peso_kg'] else {'kg': None, 'estimado': True}
    ea = calcular_ea(macros, entreno, ffm, perfil['sexo'])

    restricciones, prefs = obtener_restricciones(conn, atleta_id)
    comidas = armar_comidas(macros, entreno, restricciones, fecha)
    suplementos = armar_suplementos(entreno, bio_eval, perfil['deporte_ppal'])
    hidratacion = calcular_hidratacion(perfil['peso_kg'], entreno)

    onboarding = campos_faltantes(perfil)
    narrativa = generar_narrativa(entreno, bio_eval, carrera, recuperacion_ayer)
    alertas = calcular_alertas(ea, bio_eval, onboarding)

    entreno_kcal = (entreno.get('usar_para_calculo') or {}).get('kcal', 0)

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
            'suplementos': suplementos,
            'hidratacion_ml': hidratacion.get('total_ml'),
            'alertas': alertas,
        },
        'nivel2': {
            'gasto_desglose': {'tmb': tmb.get('kcal'), 'neat': neat.get('kcal'), 'entreno': entreno_kcal,
                               'total_gasto_estimado': (tmb.get('kcal') or 0) + (neat.get('kcal') or 0) + entreno_kcal},
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
