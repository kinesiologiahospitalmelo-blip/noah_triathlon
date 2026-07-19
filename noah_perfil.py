"""
noah_perfil.py
------------------
Motor de analisis para la seccion "Perfil": todo lo que NOAH aprendio
del atleta a partir de su historial real -- cada numero sale de una
consulta concreta a datos que ya existen.

USO:
    from noah_perfil import generar_perfil
    perfil = generar_perfil(conn, atleta_id)
"""

from datetime import datetime, timedelta


def _dia_semana_es(fecha_str):
    dias = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    try:
        d = datetime.strptime(fecha_str[:10], '%Y-%m-%d')
        return dias[d.weekday()]
    except Exception:
        return None


def _patron_semanal(conn, atleta_id, meses=6):
    desde = (datetime.now() - timedelta(days=meses*30)).strftime('%Y-%m-%d')
    filas = conn.execute("""
        SELECT fecha, tss_total, sport
        FROM sesiones
        WHERE atleta_id=%s AND fecha >= %s AND tss_total > 0
          AND (fuente IS NULL OR fuente NOT IN ('prescripcion','simulacion','generada'))
    """, (atleta_id, desde)).fetchall()

    por_dia = {d: {'n': 0, 'tss_total': 0} for d in
               ['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo']}
    for f in filas:
        dia = _dia_semana_es(f[0])
        if dia:
            por_dia[dia]['n'] += 1
            por_dia[dia]['tss_total'] += (f[1] or 0)

    resultado = {}
    for dia, v in por_dia.items():
        resultado[dia] = {
            'sesiones': v['n'],
            'tss_promedio': round(v['tss_total'] / v['n'], 1) if v['n'] > 0 else 0,
        }
    dia_mas_activo = max(resultado.items(), key=lambda x: x[1]['sesiones'])[0] if filas else None
    return {'por_dia': resultado, 'dia_mas_activo': dia_mas_activo, 'total_sesiones': len(filas)}


def _distribucion_zonas(conn, atleta_id, meses=6):
    desde = (datetime.now() - timedelta(days=meses*30)).strftime('%Y-%m-%d')
    fila = conn.execute("""
        SELECT SUM(tss_z12) as z12, SUM(tss_z34) as z34, SUM(tss_z56) as z56
        FROM sesiones
        WHERE atleta_id=%s AND fecha >= %s
          AND (fuente IS NULL OR fuente NOT IN ('prescripcion','simulacion','generada'))
    """, (atleta_id, desde)).fetchone()

    z12, z34, z56 = (fila[0] or 0), (fila[1] or 0), (fila[2] or 0)
    total = z12 + z34 + z56
    if total == 0:
        return {'z_baja_pct': None, 'z_media_pct': None, 'z_alta_pct': None, 'patron': None}

    z_baja_pct  = round(z12 / total * 100, 1)
    z_media_pct = round(z34 / total * 100, 1)
    z_alta_pct  = round(z56 / total * 100, 1)

    if z_baja_pct >= 70:
        patron = 'polarizado (mucho volumen suave, poco intenso)'
    elif z_media_pct >= 50:
        patron = 'piramidal con base en zona media (mucho tiempo en umbral)'
    elif z_alta_pct >= 30:
        patron = 'muy intenso para el volumen que maneja'
    else:
        patron = 'mixto, sin un patrón dominante claro'

    return {'z_baja_pct': z_baja_pct, 'z_media_pct': z_media_pct,
            'z_alta_pct': z_alta_pct, 'patron': patron}


def _ctl_atl_tsb_actual(conn, atleta_id):
    fila = conn.execute("""
        SELECT ctl, atl, tsb FROM sesiones
        WHERE atleta_id=%s AND ctl IS NOT NULL
        ORDER BY fecha DESC LIMIT 1
    """, (atleta_id,)).fetchone()
    if not fila:
        return {'ctl': None, 'atl': None, 'tsb': None, 'estado': None}

    ctl, atl, tsb = fila[0], fila[1], fila[2]
    if tsb is None:
        estado = None
    elif tsb < -20:
        estado = 'fatiga alta — riesgo de sobreentrenamiento'
    elif tsb < -10:
        estado = 'en carga, fatiga acumulada normal'
    elif tsb < 5:
        estado = 'equilibrado'
    elif tsb < 20:
        estado = 'fresco, buen momento para competir'
    else:
        estado = 'muy fresco — puede estar perdiendo forma por poco estímulo'

    return {'ctl': round(ctl,1) if ctl else None, 'atl': round(atl,1) if atl else None,
            'tsb': round(tsb,1) if tsb else None, 'estado': estado}


def _mejores_marcas(conn, atleta_id):
    fila = conn.execute("""
        SELECT
            MIN(bio_mejor_ritmo_5min) FILTER (WHERE sport='running')  as mejor_ritmo_run,
            MAX(bio_mejor_potencia_5min) FILTER (WHERE sport='cycling') as mejor_pot_5min,
            MAX(bio_potencia_20min) FILTER (WHERE sport='cycling')      as mejor_pot_20min,
            MIN(bio_mejor_ritmo_5min) FILTER (WHERE sport='swimming') as mejor_ritmo_swim
        FROM sesiones WHERE atleta_id=%s
    """, (atleta_id,)).fetchone()

    if not fila:
        return {}

    def _fmt_pace(v):
        if not v: return None
        m = int(v)
        s = round((v - m) * 60)
        return f'{m}:{s:02d}/km'

    return {
        'mejor_ritmo_5min_run': _fmt_pace(fila[0]),
        'mejor_potencia_5min': round(fila[1]) if fila[1] else None,
        'mejor_potencia_20min': round(fila[2]) if fila[2] else None,
        'mejor_ritmo_5min_swim': _fmt_pace(fila[3]),
    }


def _punto_quiebre_tsb(conn, atleta_id):
    filas = conn.execute("""
        SELECT tsb, bio_efficiency_factor
        FROM sesiones
        WHERE atleta_id=%s AND sport='running' AND tsb IS NOT NULL
          AND bio_efficiency_factor IS NOT NULL
    """, (atleta_id,)).fetchall()

    if len(filas) < 20:
        return {'disponible': False, 'motivo': 'no hay suficientes sesiones con TSB y eficiencia para calcularlo'}

    baldes = {'muy_fatigado': [], 'fatigado': [], 'equilibrado': [], 'fresco': []}
    for tsb, ef in filas:
        if tsb < -20: baldes['muy_fatigado'].append(ef)
        elif tsb < -5: baldes['fatigado'].append(ef)
        elif tsb < 10: baldes['equilibrado'].append(ef)
        else: baldes['fresco'].append(ef)

    promedios = {k: round(sum(v)/len(v), 5) for k, v in baldes.items() if len(v) >= 3}
    if len(promedios) < 2:
        return {'disponible': False, 'motivo': 'faltan datos en suficientes rangos de TSB'}

    mejor = max(promedios.items(), key=lambda x: x[1])
    peor  = min(promedios.items(), key=lambda x: x[1])

    return {'disponible': True, 'promedios_por_rango': promedios,
            'mejor_rango': mejor[0], 'peor_rango': peor[0]}


def _consistencia(conn, atleta_id, meses=6):
    desde = (datetime.now() - timedelta(days=meses*30)).strftime('%Y-%m-%d')
    filas = conn.execute("""
        SELECT fecha, tss_total FROM sesiones
        WHERE atleta_id=%s AND fecha >= %s AND tss_total > 0
          AND (fuente IS NULL OR fuente NOT IN ('prescripcion','simulacion','generada'))
    """, (atleta_id, desde)).fetchall()

    if not filas:
        return {'disponible': False}

    semanas = {}
    for fecha, tss in filas:
        try:
            d = datetime.strptime(fecha[:10], '%Y-%m-%d')
            semana_key = d.strftime('%Y-W%W')
        except Exception:
            continue
        semanas[semana_key] = semanas.get(semana_key, 0) + (tss or 0)

    valores = list(semanas.values())
    if len(valores) < 4:
        return {'disponible': False}

    promedio = sum(valores) / len(valores)
    desvio = (sum((v-promedio)**2 for v in valores) / len(valores)) ** 0.5
    cv = round((desvio / promedio) * 100, 1) if promedio > 0 else None

    if cv is None:
        nivel = None
    elif cv < 25:
        nivel = 'muy consistente'
    elif cv < 45:
        nivel = 'razonablemente consistente'
    else:
        nivel = 'irregular — semanas muy distintas entre sí'

    return {'disponible': True, 'semanas_analizadas': len(valores),
            'tss_semanal_promedio': round(promedio,1), 'coef_variacion_pct': cv, 'nivel': nivel}


def _predicciones_ml(conn, atleta_id):
    """
    Carga el modelo YA ENTRENADO de este atleta (predictor_respuesta.pkl)
    y le pide predicciones reales sobre su estado actual -- no
    estadistica descriptiva, es el modelo de ML aplicado en vivo.
    """
    import os
    try:
        import joblib
    except ImportError:
        return {'disponible': False, 'motivo': 'falta la libreria joblib'}

    ruta_modelo = os.path.join('noah_modelos', f'atleta_{atleta_id}', 'predictor_respuesta.pkl')
    if not os.path.exists(ruta_modelo):
        return {'disponible': False, 'motivo': 'este atleta todavía no tiene un modelo entrenado'}

    try:
        modelo = joblib.load(ruta_modelo)
    except Exception as e:
        return {'disponible': False, 'motivo': f'error cargando el modelo: {e}'}

    if not getattr(modelo, 'entrenado', False):
        return {'disponible': False, 'motivo': 'el modelo de este atleta no llegó a entrenarse'}

    fila = conn.execute("""
        SELECT ctl, atl, tsb, tss_dia, hrv_rmssd, stress_avg, sleep_h,
               hrv_7d_avg, stress_7d_avg, sleep_7d_avg, hrv_ratio_7d,
               delta_hrv, tss_7d, sesion_intensa
        FROM sesiones
        WHERE atleta_id=%s AND ctl IS NOT NULL
        ORDER BY fecha DESC LIMIT 1
    """, (atleta_id,)).fetchone()

    if not fila:
        return {'disponible': False, 'motivo': 'no hay datos recientes para evaluar'}

    campos = ['ctl','atl','tsb','tss_dia','hrv_rmssd','stress_avg','sleep_h',
              'hrv_7d_avg','stress_7d_avg','sleep_7d_avg','hrv_ratio_7d',
              'delta_hrv','tss_7d','sesion_intensa']
    estado = dict(zip(campos, fila))

    pred = modelo.predecir(estado)
    if not pred.get('disponible'):
        return {'disponible': False, 'motivo': 'el modelo no pudo generar una predicción'}

    importancias = {}
    try:
        importancias = modelo.importancia_features()
    except Exception:
        pass

    # Traducir los nombres tecnicos de features a texto legible
    NOMBRES_LEGIBLES = {
        'ctl': 'fitness acumulado (CTL)', 'atl': 'fatiga reciente (ATL)',
        'tsb': 'frescura (TSB)', 'tss_7d': 'carga de la semana',
        'hrv_7d_avg': 'HRV promedio semanal', 'stress_7d_avg': 'estrés promedio semanal',
        'sleep_7d_avg': 'sueño promedio semanal', 'hrv_ratio_7d': 'relación de HRV semanal',
        'delta_hrv': 'variación diaria de HRV', 'sesion_intensa': 'sesiones intensas recientes',
        'tss_dia': 'carga del día', 'hrv_rmssd': 'HRV del día', 'stress_avg': 'estrés del día',
        'sleep_h': 'horas de sueño',
    }
    factores_riesgo = []
    if importancias.get('riesgo'):
        top3 = list(importancias['riesgo'].items())[:3]
        factores_riesgo = [NOMBRES_LEGIBLES.get(k, k) for k, v in top3]

    return {
        'disponible': True,
        'semaforo': pred.get('semaforo'),
        'interpretacion': pred.get('interpretacion'),
        'prob_riesgo_sobrecarga_pct': round(pred.get('prob_riesgo_sobrecarga', 0) * 100, 1) if pred.get('prob_riesgo_sobrecarga') is not None else None,
        'prob_buena_absorcion_pct': round(pred.get('prob_absorcion', 0) * 100, 1) if pred.get('prob_absorcion') is not None else None,
        'ctl_predicho_7d': pred.get('ctl_predicho_7d'),
        'tsb_predicho_7d': pred.get('tsb_predicho_7d'),
        'factores_que_mas_pesan_en_su_riesgo': factores_riesgo,
    }


def generar_perfil(conn, atleta_id):
    return {
        'patron_semanal':    _patron_semanal(conn, atleta_id),
        'distribucion_zonas': _distribucion_zonas(conn, atleta_id),
        'mejores_marcas':    _mejores_marcas(conn, atleta_id),
        'punto_quiebre_tsb': _punto_quiebre_tsb(conn, atleta_id),
        'consistencia':      _consistencia(conn, atleta_id),
        'predicciones_ml':   _predicciones_ml(conn, atleta_id),
    }
