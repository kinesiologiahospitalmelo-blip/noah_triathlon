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


def _patron_semanal(conn, atleta_id, meses=600):
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


def _distribucion_zonas(conn, atleta_id, meses=600):
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
    """
    Regresion lineal REAL (no baldes genericos): cuanto cae exactamente
    su eficiencia por cada 10 puntos que baja el TSB -- un numero propio
    de este atleta, calculado sobre TODO su historial disponible.
    """
    filas = conn.execute("""
        SELECT tsb, bio_efficiency_factor
        FROM sesiones
        WHERE atleta_id=%s AND sport='running' AND tsb IS NOT NULL
          AND bio_efficiency_factor IS NOT NULL
    """, (atleta_id,)).fetchall()

    if len(filas) < 20:
        return {'disponible': False, 'motivo': 'no hay suficientes sesiones con TSB y eficiencia para calcularlo'}

    try:
        import numpy as np
        from sklearn.linear_model import LinearRegression
    except ImportError:
        return {'disponible': False, 'motivo': 'falta scikit-learn'}

    X = np.array([[f[0]] for f in filas])
    y = np.array([f[1] for f in filas])
    modelo = LinearRegression()
    modelo.fit(X, y)
    pendiente = modelo.coef_[0]
    r2 = modelo.score(X, y)
    promedio_ef = y.mean()
    cambio_pct = round(float(pendiente * 10 / promedio_ef) * 100, 2) if promedio_ef else None

    return {
        'disponible': True,
        'cambio_eficiencia_por_10_tsb_pct': cambio_pct,
        'r2': round(float(r2), 3),
        'n_sesiones': len(filas),
        'confiable': r2 > 0.05,
    }


def _analisis_random_forest_rendimiento(conn, atleta_id):
    """
    Random Forest entrenado sobre TODO el historial de running: que
    factores predicen mejor su rendimiento (eficiencia) -- hallazgos
    reales de su propio historial, no obviedades genericas.
    """
    filas = conn.execute("""
        SELECT fecha, tsb, atl, ctl, bio_cadencia_deriva_pct, bio_efficiency_factor
        FROM sesiones
        WHERE atleta_id=%s AND sport='running'
          AND tsb IS NOT NULL AND atl IS NOT NULL AND ctl IS NOT NULL
          AND bio_efficiency_factor IS NOT NULL
    """, (atleta_id,)).fetchall()

    if len(filas) < 40:
        return {'disponible': False, 'motivo': 'se necesitan al menos 40 sesiones con datos completos'}

    try:
        import numpy as np
        from sklearn.ensemble import RandomForestRegressor
    except ImportError:
        return {'disponible': False, 'motivo': 'falta scikit-learn'}

    nombres_legibles = {
        'tsb': 'frescura (TSB)', 'atl': 'fatiga reciente (ATL)', 'ctl': 'fitness acumulado (CTL)',
        'dia_semana': 'día de la semana',
        'cadencia_deriva': 'deterioro de cadencia en la sesión',
    }

    X, y = [], []
    for fecha, tsb, atl, ctl, cad_deriva, ef in filas:
        dia_num = 0
        try:
            dia_num = datetime.strptime(fecha[:10], '%Y-%m-%d').weekday()
        except Exception:
            pass
        X.append([tsb, atl, ctl, dia_num, cad_deriva or 0])
        y.append(ef)

    X = np.array(X)
    y = np.array(y)

    modelo = RandomForestRegressor(n_estimators=200, max_depth=5, random_state=42, min_samples_leaf=5)
    modelo.fit(X, y)

    columnas = ['tsb', 'atl', 'ctl', 'dia_semana', 'cadencia_deriva']
    importancias = dict(zip(columnas, [float(v) for v in modelo.feature_importances_]))
    top3 = sorted(importancias.items(), key=lambda x: x[1], reverse=True)[:3]
    r2 = round(float(modelo.score(X, y)), 3)

    return {
        'disponible': True,
        'n_sesiones': len(filas),
        'r2_ajuste': r2,
        'factores_mas_importantes': [
            {'factor': nombres_legibles.get(k, k), 'importancia_pct': round(v*100, 1)}
            for k, v in top3
        ],
    }


def _consistencia(conn, atleta_id, meses=600):
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

    # FIX: se invierte el orden -- primero se prepara el dataset (pandas),
    # RECIEN DESPUES se carga el modelo con joblib. Se confirmo con pruebas
    # aisladas que construir_dataset() funciona perfecto solo, pero se
    # colgaba sin error cuando corria justo despues de joblib.load() --
    # un conflicto de hilos conocido entre joblib/sklearn y numpy/pandas
    # en Windows. Invertir el orden evita el conflicto.
    try:
        from noah_ml import construir_dataset
        df = construir_dataset(conn, atleta_id)
    except Exception as e:
        return {'disponible': False, 'motivo': f'error preparando datos: {e}'}

    if df is None or df.empty:
        return {'disponible': False, 'motivo': 'no hay datos suficientes para evaluar'}

    ultima_fila = df.iloc[-1]
    estado = {col: ultima_fila[col] for col in df.columns if col != 'fecha'}

    try:
        import joblib
    except ImportError:
        return {'disponible': False, 'motivo': 'falta la libreria joblib'}

    raiz = os.path.dirname(os.path.abspath(__file__))
    ruta_modelo = os.path.join(raiz, 'noah_modelos', f'atleta_{atleta_id}', 'predictor_respuesta.pkl')
    if not os.path.exists(ruta_modelo):
        return {'disponible': False, 'motivo': f'este atleta todavía no tiene un modelo entrenado (buscado en {ruta_modelo})'}

    try:
        modelo = joblib.load(ruta_modelo)
    except Exception as e:
        return {'disponible': False, 'motivo': f'error cargando el modelo: {e}'}

    if not getattr(modelo, 'entrenado', False):
        return {'disponible': False, 'motivo': 'el modelo de este atleta no llegó a entrenarse'}

    try:
        pred = modelo.predecir(estado)
    except Exception as e:
        return {'disponible': False, 'motivo': f'error en predecir(): {type(e).__name__}: {e}'}

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


def _acwr(conn, atleta_id, dias_historial=120):
    """
    Ratio Agudo:Cronico -- la metrica estandar en ciencias del deporte
    para riesgo de lesion por carga. agudo = TSS ultimos 7 dias.
    cronico = promedio semanal de los ultimos 28 dias. Fuera de
    0.8-1.3 se considera zona de mayor riesgo.
    """
    desde = (datetime.now() - timedelta(days=dias_historial+28)).strftime('%Y-%m-%d')
    filas = conn.execute("""
        SELECT fecha, tss_total FROM sesiones
        WHERE atleta_id=%s AND fecha >= %s AND tss_total > 0
          AND (fuente IS NULL OR fuente NOT IN ('prescripcion','simulacion','generada'))
    """, (atleta_id, desde)).fetchall()

    if not filas:
        return {'disponible': False}

    tss_por_dia = {}
    for fecha, tss in filas:
        d = fecha[:10]
        tss_por_dia[d] = tss_por_dia.get(d, 0) + (tss or 0)

    fechas_ordenadas = sorted(tss_por_dia.keys())
    fecha_ini = datetime.strptime(fechas_ordenadas[0], '%Y-%m-%d')
    fecha_fin = datetime.strptime(fechas_ordenadas[-1], '%Y-%m-%d')
    serie = []
    d = fecha_ini
    while d <= fecha_fin:
        serie.append(tss_por_dia.get(d.strftime('%Y-%m-%d'), 0))
        d += timedelta(days=1)

    if len(serie) < 28:
        return {'disponible': False, 'motivo': 'no hay suficiente historial continuo (se necesitan al menos 28 días)'}

    historial_acwr = []
    for i in range(27, len(serie)):
        agudo = sum(serie[i-6:i+1])
        cronico = sum(serie[i-27:i+1]) / 4
        historial_acwr.append(round(agudo / cronico, 2) if cronico > 0 else None)

    historial_grafico = historial_acwr[-90:]
    actual = historial_acwr[-1] if historial_acwr else None

    if actual is None:
        zona = None
    elif actual < 0.8:
        zona = 'bajo (posible desentrenamiento)'
    elif actual <= 1.3:
        zona = 'zona segura'
    elif actual <= 1.5:
        zona = 'elevado — precaución'
    else:
        zona = 'riesgo alto de lesión'

    return {'disponible': True, 'actual': actual, 'zona': zona, 'historial': historial_grafico}


def _progreso_tecnico(conn, atleta_id, meses=600):
    """Evolucion mensual de eficiencia y decoupling en running -- progreso real, no solo volumen."""
    desde = (datetime.now() - timedelta(days=meses*30)).strftime('%Y-%m-%d')
    filas = conn.execute("""
        SELECT fecha, bio_efficiency_factor, bio_decoupling_pct
        FROM sesiones
        WHERE atleta_id=%s AND sport='running' AND fecha >= %s
          AND (bio_efficiency_factor IS NOT NULL OR bio_decoupling_pct IS NOT NULL)
    """, (atleta_id, desde)).fetchall()

    if len(filas) < 10:
        return {'disponible': False, 'motivo': 'no hay suficientes sesiones con biomarcadores calculados'}

    por_mes_ef, por_mes_dec = {}, {}
    for fecha, ef, dec in filas:
        mes = fecha[:7]
        if ef is not None:
            por_mes_ef.setdefault(mes, []).append(ef)
        if dec is not None:
            por_mes_dec.setdefault(mes, []).append(dec)

    meses_ordenados = sorted(set(list(por_mes_ef.keys()) + list(por_mes_dec.keys())))
    serie_ef  = [round(sum(por_mes_ef[m])/len(por_mes_ef[m]), 5) if m in por_mes_ef else None for m in meses_ordenados]
    serie_dec = [round(sum(por_mes_dec[m])/len(por_mes_dec[m]), 2) if m in por_mes_dec else None for m in meses_ordenados]

    ef_validos = [v for v in serie_ef if v is not None]
    tendencia_ef = None
    if len(ef_validos) >= 4:
        mitad = len(ef_validos)//2
        primera = sum(ef_validos[:mitad])/mitad
        segunda = sum(ef_validos[mitad:])/(len(ef_validos)-mitad)
        if primera:
            cambio_pct = round(((segunda-primera)/primera)*100, 1)
            tendencia_ef = 'mejorando' if cambio_pct > 3 else ('empeorando' if cambio_pct < -3 else 'estable')

    return {'disponible': True, 'meses': meses_ordenados,
            'efficiency_factor': serie_ef, 'decoupling_pct': serie_dec,
            'tendencia_eficiencia': tendencia_ef}


def _marcas_con_contexto(conn, atleta_id):
    """Su mejor marca, cruzada con el TSB de ese dia -- para saber si fue genuina o 'prestada'."""
    fila = conn.execute("""
        SELECT fecha, bio_mejor_ritmo_5min, tsb
        FROM sesiones
        WHERE atleta_id=%s AND sport='running' AND bio_mejor_ritmo_5min IS NOT NULL AND tsb IS NOT NULL
        ORDER BY bio_mejor_ritmo_5min ASC LIMIT 1
    """, (atleta_id,)).fetchone()

    if not fila:
        return {'disponible': False}

    fecha, ritmo, tsb = fila
    m = int(ritmo); s = round((ritmo - m) * 60)
    ritmo_str = f'{m}:{s:02d}/km'

    if tsb > 5:
        contexto = 'con el cuerpo fresco — marca confiable, refleja su fitness real'
    elif tsb > -10:
        contexto = 'en un estado normal de carga'
    else:
        contexto = 'con fatiga acumulada alta — marca "prestada", cuidado si se repite el patrón'

    return {'disponible': True, 'fecha': fecha, 'ritmo': ritmo_str,
            'tsb_ese_dia': round(tsb, 1), 'contexto': contexto}


def _rachas_fatiga(conn, atleta_id, umbral=-20, meses=600):
    """Rachas de TSB muy negativo sostenido -- distinto de un mal dia puntual."""
    desde = (datetime.now() - timedelta(days=meses*30)).strftime('%Y-%m-%d')
    filas = conn.execute("""
        SELECT fecha, tsb FROM sesiones
        WHERE atleta_id=%s AND fecha >= %s AND tsb IS NOT NULL
        ORDER BY fecha
    """, (atleta_id, desde)).fetchall()

    if not filas:
        return {'disponible': False}

    tsb_por_dia = {}
    for fecha, tsb in filas:
        tsb_por_dia[fecha[:10]] = tsb

    fechas_ordenadas = sorted(tsb_por_dia.keys())
    rachas, racha_actual = [], []
    for f in fechas_ordenadas:
        if tsb_por_dia[f] < umbral:
            racha_actual.append(f)
        else:
            if len(racha_actual) >= 5:
                rachas.append({'inicio': racha_actual[0], 'fin': racha_actual[-1], 'dias': len(racha_actual)})
            racha_actual = []
    if len(racha_actual) >= 5:
        rachas.append({'inicio': racha_actual[0], 'fin': racha_actual[-1], 'dias': len(racha_actual)})

    return {'disponible': True, 'rachas': rachas[-5:], 'total_rachas': len(rachas)}


def _volumen_historico(conn, atleta_id, meses=600):
    """Volumen (km) mes a mes -- para ver si crece o se estanca en el tiempo."""
    desde = (datetime.now() - timedelta(days=meses*30)).strftime('%Y-%m-%d')
    filas = conn.execute("""
        SELECT fecha, distance_km, duration_min FROM sesiones
        WHERE atleta_id=%s AND fecha >= %s
          AND (fuente IS NULL OR fuente NOT IN ('prescripcion','simulacion','generada'))
    """, (atleta_id, desde)).fetchall()
    if not filas:
        return {'disponible': False}
    por_mes = {}
    for fecha, km, dur in filas:
        mes = fecha[:7]
        por_mes.setdefault(mes, {'km': 0, 'min': 0})
        por_mes[mes]['km'] += (km or 0)
        por_mes[mes]['min'] += (dur or 0)
    meses_ordenados = sorted(por_mes.keys())
    return {'disponible': True, 'meses': meses_ordenados,
            'km_por_mes': [round(por_mes[m]['km'], 1) for m in meses_ordenados]}


def _sesiones_anomalas(conn, atleta_id, meses=600):
    """Sesiones con decoupling muy fuera de lo normal para este atleta -- posible enfermedad, mal dia, o error del reloj."""
    desde = (datetime.now() - timedelta(days=meses*30)).strftime('%Y-%m-%d')
    filas = conn.execute("""
        SELECT fecha, sport, bio_decoupling_pct FROM sesiones
        WHERE atleta_id=%s AND fecha >= %s AND bio_decoupling_pct IS NOT NULL
    """, (atleta_id, desde)).fetchall()
    if len(filas) < 15:
        return {'disponible': False}
    valores = [f[2] for f in filas]
    media = sum(valores) / len(valores)
    desvio = (sum((v-media)**2 for v in valores) / len(valores)) ** 0.5
    anomalas = []
    if desvio > 0:
        for fecha, sport, dec in filas:
            if (dec - media) / desvio > 2.5:
                anomalas.append({'fecha': fecha, 'sport': sport, 'decoupling_pct': dec})
    anomalas.sort(key=lambda x: x['fecha'], reverse=True)
    return {'disponible': True, 'anomalas': anomalas[:5], 'total': len(anomalas)}


def _umbral_tss_tecnica(conn, atleta_id, meses=600):
    """
    Regresion lineal REAL (no baldes): cuanto se deteriora exactamente
    su decoupling del dia siguiente por cada 100 puntos de TSS del dia
    anterior -- numero propio de este atleta, con R2 de confiabilidad,
    sobre todo su historial disponible.
    """
    desde = (datetime.now() - timedelta(days=meses*30)).strftime('%Y-%m-%d')
    filas_tss = conn.execute("""
        SELECT fecha, tss_total FROM sesiones WHERE atleta_id=%s AND fecha >= %s
    """, (atleta_id, desde)).fetchall()
    filas_dec = conn.execute("""
        SELECT fecha, bio_decoupling_pct FROM sesiones
        WHERE atleta_id=%s AND fecha >= %s AND sport='running' AND bio_decoupling_pct IS NOT NULL
    """, (atleta_id, desde)).fetchall()
    if len(filas_tss) < 10 or len(filas_dec) < 10:
        return {'disponible': False}

    tss_por_dia = {}
    for f, t in filas_tss:
        d = f[:10]
        tss_por_dia[d] = tss_por_dia.get(d, 0) + (t or 0)

    pares = []
    for fecha_dec, dec in filas_dec:
        d = datetime.strptime(fecha_dec[:10], '%Y-%m-%d')
        anterior = (d - timedelta(days=1)).strftime('%Y-%m-%d')
        if anterior in tss_por_dia:
            pares.append((tss_por_dia[anterior], dec))

    if len(pares) < 15:
        return {'disponible': False, 'motivo': 'no hay suficientes pares dia-consecutivo para calcularlo'}

    try:
        import numpy as np
        from sklearn.linear_model import LinearRegression
    except ImportError:
        return {'disponible': False, 'motivo': 'falta scikit-learn'}

    X = np.array([[p[0]] for p in pares])
    y = np.array([p[1] for p in pares])
    modelo = LinearRegression()
    modelo.fit(X, y)
    pendiente = float(modelo.coef_[0])
    r2 = round(float(modelo.score(X, y)), 3)

    return {
        'disponible': True,
        'deterioro_decoupling_por_100_tss_previo': round(pendiente * 100, 3),
        'r2': r2,
        'n_sesiones': len(pares),
        'confiable': r2 > 0.05,
    }


def _dias_recuperacion(conn, atleta_id, meses=600):
    """Cuantos dias tarda en volver el TSB a un nivel razonable tras una sesion fuerte."""
    desde = (datetime.now() - timedelta(days=meses*30)).strftime('%Y-%m-%d')
    filas = conn.execute("""
        SELECT fecha, tsb, tss_total FROM sesiones
        WHERE atleta_id=%s AND fecha >= %s AND tsb IS NOT NULL
        ORDER BY fecha
    """, (atleta_id, desde)).fetchall()
    if len(filas) < 20:
        return {'disponible': False}
    por_dia = {}
    for fecha, tsb, tss in filas:
        d = fecha[:10]
        por_dia.setdefault(d, {'tsb': tsb, 'tss': 0})
        por_dia[d]['tsb'] = tsb
        por_dia[d]['tss'] += (tss or 0)
    dias = sorted(por_dia.keys())
    tss_vals = sorted(v['tss'] for v in por_dia.values())
    if not tss_vals:
        return {'disponible': False}
    p80 = tss_vals[int(len(tss_vals)*0.8)]
    recuperaciones = []
    for i, d in enumerate(dias):
        if p80 > 0 and por_dia[d]['tss'] > p80:
            for j in range(i+1, min(i+15, len(dias))):
                if por_dia[dias[j]]['tsb'] is not None and por_dia[dias[j]]['tsb'] >= -5:
                    recuperaciones.append(j - i)
                    break
    if not recuperaciones:
        return {'disponible': False}
    return {'disponible': True, 'dias_promedio_recuperacion': round(sum(recuperaciones)/len(recuperaciones), 1),
            'muestras': len(recuperaciones)}


def _disciplina_mas_desgaste(conn, atleta_id, meses=600):
    """Que disciplina acumula mas señales de sobrecarga (deriva de decoupling), para triatletas."""
    desde = (datetime.now() - timedelta(days=meses*30)).strftime('%Y-%m-%d')
    resultado = {}
    for sport in ['running', 'cycling', 'swimming']:
        filas = conn.execute("""
            SELECT bio_decoupling_pct FROM sesiones
            WHERE atleta_id=%s AND fecha >= %s AND sport=%s AND bio_decoupling_pct IS NOT NULL
        """, (atleta_id, desde, sport)).fetchall()
        valores = [f[0] for f in filas if f[0] is not None]
        if len(valores) >= 5:
            resultado[sport] = round(sum(valores)/len(valores), 2)
    if not resultado:
        return {'disponible': False}
    peor = max(resultado.items(), key=lambda x: x[1])
    return {'disponible': True, 'decoupling_promedio_por_deporte': resultado, 'disciplina_mas_desgaste': peor[0]}


def _fase_actual(conn, atleta_id):
    """Si esta en mejora, meseta o declive, comparando el CTL reciente contra el previo."""
    filas = conn.execute("""
        SELECT fecha, ctl FROM sesiones
        WHERE atleta_id=%s AND ctl IS NOT NULL
        ORDER BY fecha DESC LIMIT 60
    """, (atleta_id,)).fetchall()
    if len(filas) < 30:
        return {'disponible': False}
    filas = list(reversed(filas))
    ctl_reciente = [f[1] for f in filas[-14:]]
    ctl_previo = [f[1] for f in filas[-30:-14]]
    if not ctl_reciente or not ctl_previo:
        return {'disponible': False}
    prom_reciente = sum(ctl_reciente) / len(ctl_reciente)
    prom_previo = sum(ctl_previo) / len(ctl_previo)
    cambio_pct = round(((prom_reciente-prom_previo)/prom_previo)*100, 1) if prom_previo else 0
    fase = 'mejora' if cambio_pct > 3 else ('declive' if cambio_pct < -3 else 'meseta')
    return {'disponible': True, 'fase': fase, 'cambio_ctl_pct': cambio_pct}


def _rendimiento_por_dia_controlado(conn, atleta_id, meses=600):
    """Rendimiento por dia de semana, SOLO comparando dias con TSB similar (control justo)."""
    desde = (datetime.now() - timedelta(days=meses*30)).strftime('%Y-%m-%d')
    filas = conn.execute("""
        SELECT fecha, bio_efficiency_factor, tsb FROM sesiones
        WHERE atleta_id=%s AND sport='running' AND fecha >= %s
          AND bio_efficiency_factor IS NOT NULL AND tsb IS NOT NULL
          AND tsb BETWEEN -10 AND 10
    """, (atleta_id, desde)).fetchall()
    if len(filas) < 15:
        return {'disponible': False}
    por_dia = {}
    for fecha, ef, tsb in filas:
        dia = _dia_semana_es(fecha)
        if dia:
            por_dia.setdefault(dia, []).append(ef)
    promedios = {d: round(sum(v)/len(v), 5) for d, v in por_dia.items() if len(v) >= 2}
    if len(promedios) < 3:
        return {'disponible': False}
    mejor = max(promedios.items(), key=lambda x: x[1])
    return {'disponible': True, 'promedios_por_dia': promedios, 'mejor_dia': mejor[0]}


def _firma_recuperacion(conn, atleta_id, meses=600):
    """HRV nocturno tras cargas suaves vs fuertes -- su propia cinetica de recuperacion."""
    desde = (datetime.now() - timedelta(days=meses*30)).strftime('%Y-%m-%d')
    filas_tss = conn.execute("""
        SELECT fecha, tss_total FROM sesiones WHERE atleta_id=%s AND fecha >= %s
    """, (atleta_id, desde)).fetchall()
    try:
        filas_hrv = conn.execute("""
            SELECT fecha, hrv_rmssd FROM sleep_hrv
            WHERE atleta_id=%s AND fecha >= %s AND hrv_rmssd IS NOT NULL
        """, (atleta_id, desde)).fetchall()
    except Exception:
        return {'disponible': False, 'motivo': 'este atleta no tiene biomarcadores de 24hs'}

    if len(filas_tss) < 10 or len(filas_hrv) < 10:
        return {'disponible': False}
    tss_por_dia = {}
    for f, t in filas_tss:
        d = f[:10]
        tss_por_dia[d] = tss_por_dia.get(d, 0) + (t or 0)
    hrv_por_dia = {f[:10]: h for f, h in filas_hrv}
    pares = []
    for d, tss in tss_por_dia.items():
        sig = (datetime.strptime(d, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
        if sig in hrv_por_dia:
            pares.append((tss, hrv_por_dia[sig]))
    if len(pares) < 10:
        return {'disponible': False}
    pares.sort()
    mitad = len(pares) // 2
    hrv_bajo = [p[1] for p in pares[:mitad]]
    hrv_alto = [p[1] for p in pares[mitad:]]
    return {'disponible': True,
            'hrv_tras_carga_suave': round(sum(hrv_bajo)/len(hrv_bajo), 1),
            'hrv_tras_carga_fuerte': round(sum(hrv_alto)/len(hrv_alto), 1)}


def generar_perfil(conn, atleta_id):
    return {
        'patron_semanal':    _patron_semanal(conn, atleta_id),
        'distribucion_zonas': _distribucion_zonas(conn, atleta_id),
        'mejores_marcas':    _mejores_marcas(conn, atleta_id),
        'punto_quiebre_tsb': _punto_quiebre_tsb(conn, atleta_id),
        'consistencia':      _consistencia(conn, atleta_id),
        'predicciones_ml':   _predicciones_ml(conn, atleta_id),
        'acwr':              _acwr(conn, atleta_id),
        'progreso_tecnico':  _progreso_tecnico(conn, atleta_id),
        'marca_con_contexto': _marcas_con_contexto(conn, atleta_id),
        'rachas_fatiga':     _rachas_fatiga(conn, atleta_id),
        'volumen_historico': _volumen_historico(conn, atleta_id),
        'sesiones_anomalas': _sesiones_anomalas(conn, atleta_id),
        'umbral_tss_tecnica': _umbral_tss_tecnica(conn, atleta_id),
        'dias_recuperacion': _dias_recuperacion(conn, atleta_id),
        'disciplina_mas_desgaste': _disciplina_mas_desgaste(conn, atleta_id),
        'fase_actual':       _fase_actual(conn, atleta_id),
        'rendimiento_por_dia': _rendimiento_por_dia_controlado(conn, atleta_id),
        'firma_recuperacion': _firma_recuperacion(conn, atleta_id),
        'analisis_random_forest': _analisis_random_forest_rendimiento(conn, atleta_id),
    }
