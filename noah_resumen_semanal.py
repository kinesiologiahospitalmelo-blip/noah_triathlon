# -*- coding: utf-8 -*-
"""
noah_resumen_semanal.py — Resumen semanal EDUCATIVO de NOAH.
No tira números sueltos: cada dato viene con qué significa y qué hacer.
Bloques: titular · sistema nervioso (SNA: qué es HANNA/HRV, tu base, cortisol) ·
cómo entrenaste (80/20) · riesgos · energía · técnica por disciplina (interpretada) ·
tema de la semana (rota) + acciones.
API:
    construir_resumen(conn, atleta_id, fecha=None) -> dict | None
    render_html(resumen) -> str
"""
from datetime import date, timedelta

SPORT_LBL = {'running': 'Running', 'cycling': 'Bici', 'swimming': 'Natación'}

TEMAS = [
    {'t': 'Tu sistema nervioso: el jefe silencioso de tu entrenamiento',
     'c': 'El sistema nervioso autónomo (SNA) es el piloto automático que regula tu corazón, tu respiración y tus hormonas sin que '
          'lo pienses. Tiene dos ramas: una acelera (simpático, "pelear o huir") y otra frena y repara (parasimpático, "descansar '
          'y digerir"). Entrenar fuerte activa la primera; recuperar bien le devuelve el control a la segunda. '
          'El HRV mide ese equilibrio en milisegundos: cuando el parasimpático manda, tu HRV sube y estás listo para cargar; '
          'cuando el simpático queda dominando (fatiga, estrés), baja. Por eso NOAH mira tu SNA antes que tus ganas: entrenar '
          'fuerte con el sistema todavía en modo alerta no suma forma, suma desgaste.'},
    {'t': 'La regla 80/20: por qué menos intensidad te hace más rápido',
     'c': 'Los mejores del mundo —en resistencia— hacen cerca del 80% de su volumen FÁCIL (zona 1-2) y solo un 20% fuerte. '
          'Suena al revés de la intuición, pero tiene lógica: el entrenamiento fácil construye la base aeróbica (más mitocondrias, '
          'más capilares, mejor uso de la grasa) sin generar tanta fatiga, y eso deja energía para que el 20% duro rinda de verdad. '
          'El error más común es vivir en la "zona gris": correr siempre medio fuerte. Ahí acumulás cansancio sin el estímulo '
          'potente que mejora ni el descanso que adapta. Fácil muy fácil, y duro muy duro.'},
    {'t': 'ACWR: la matemática de por qué te lesionás',
     'c': 'El ACWR compara tu carga de esta semana (aguda) con tu promedio del último mes (crónica). La idea, respaldada por la '
          'investigación de Gabbett, es simple: el cuerpo tolera mucha carga si llegó entrenado para ella, pero se rompe cuando '
          'esa carga aparece DE GOLPE. Tendones, huesos y músculos adaptan más lento que tu corazón y tus pulmones. '
          'La zona segura es un ACWR entre 0.8 y 1.3. Por encima de 1.5 el riesgo de lesión se dispara. La conclusión no es '
          '"entrená menos", es "subí de a poco": la progresión es lo que te mantiene sano y mejorando.'},
    {'t': 'Energía disponible: el error silencioso que frena a muchos',
     'c': 'Tu cuerpo tiene un orden de prioridades: primero paga lo vital (respirar, latir, pensar, defenderte), y recién con lo que '
          'sobra invierte en adaptarte al entrenamiento. Si comés menos de lo que gastás de forma sostenida, esa energía para '
          'mejorar simplemente no existe. Lo peligroso es que al principio no se nota. Con el tiempo aparece: rendimiento que no '
          'sube, más resfríos, peor sueño, y en mujeres, alteraciones del ciclo (la famosa RED-S). Comer suficiente no es lo '
          'contrario de rendir: es la condición para rendir. Reponer es parte del plan, no un premio.'},
    {'t': 'Zona 2, Umbral y VO2máx: para qué sirve cada esfuerzo',
     'c': 'No todas las intensidades entrenan lo mismo. La Zona 2 (fácil, podés hablar) desarrolla tu motor aeróbico y te enseña a '
          'usar la grasa como combustible: es la base de todo. El Umbral/FTP (esfuerzo sostenible ~1 hora) eleva el techo al que '
          'podés rodar fuerte sin fundirte. El VO2máx (zona 5, casi sin aire) agranda tu cilindrada máxima. '
          'Cada una es una herramienta distinta; usar siempre la misma deja la mesa coja. Por eso NOAH mira tu distribución de '
          'zonas, no solo cuánto entrenaste: importa en qué "idioma" le hablaste a tu cuerpo.'},
    {'t': 'El sueño: el suplemento legal más potente que existe',
     'c': 'Dormir no es tiempo perdido: es cuando tu cuerpo hace el trabajo pesado. En el sueño profundo liberás la mayor parte de '
          'tu hormona de crecimiento, reparás fibras musculares y consolidás lo que aprendió tu técnica durante el día. '
          'Una sola noche corta ya baja tu HRV, sube tu cortisol y empeora la coordinación, el ánimo y las decisiones del día '
          'siguiente. Ningún gel, batido ni suplemento compensa dormir mal. Si tuvieras que elegir UNA cosa para mejorar tu '
          'rendimiento esta semana, apuntar a 7-9 horas de buen sueño le gana a casi todo lo demás.'},
    {'t': 'Mito "más es mejor": cómo funciona la supercompensación',
     'c': 'Acá va la idea que cambia todo: no mejorás mientras entrenás, mejorás mientras te recuperás DEL entrenamiento. '
          'El esfuerzo genera un daño controlado y baja tu rendimiento; durante el descanso el cuerpo no solo se repara, sino que '
          'reconstruye un poco más fuerte para la próxima (supercompensación). Si encadenás estímulos sin descanso, nunca llega '
          'esa reconstrucción: solo acumulás fatiga. Por eso una semana fácil cada 3-4 no es pereza ni perder forma: es cuando el '
          'cuerpo "cobra" todo lo que sembraste. Entrenar es sembrar; descansar es cosechar.'},
    {'t': 'Economía: gastar menos para ir igual de rápido',
     'c': 'Dos atletas pueden ir al mismo ritmo gastando muy distinto. La economía (o eficiencia) es cuánto rendimiento sacás por '
          'cada latido o cada watt: el que gasta menos, dura más y termina más fresco. Se mejora con técnica, cadencia, fuerza y, '
          'sobre todo, volumen aeróbico acumulado en el tiempo. Subir tu economía es como aligerar el peso de tu auto: el mismo '
          'motor te lleva más lejos con la misma nafta. Por eso NOAH la sigue junto a tu potencia y tu pace: podés estar '
          'mejorando aunque el cronómetro todavía no lo muestre.'},
]

def _f(v, d=0.0):
    try: return float(v)
    except Exception: return d

def _val(row, i):
    try: return row[i]
    except Exception: return None

def _fetch(conn, sql, params=()):
    if isinstance(params, list):
        params = tuple(params)
    try:
        return conn.execute(sql, params).fetchall()
    except Exception:
        try: conn.rollback()
        except Exception: pass
        return []

def _one(conn, sql, params=()):
    r = _fetch(conn, sql, params)
    return r[0] if r else None

def _pick(pool, semana):
    """Rota una redacción según el número de semana (misma idea, distinto matiz)."""
    try:
        return pool[int(semana) % len(pool)]
    except Exception:
        return pool[0]

# ── Variantes de redacción (misma info, distinto matiz cada semana) ─────────
QUE_ES = [
    'HANNA no es tu HRV a secas: NOAH cruza tu HRV con tu carga de entrenamiento (CTL/ATL/TSB), tu body battery, el sueño y el '
    'estrés, y de ahí arma un biomarcador propio (0-100) que relaciona cómo está tu cuerpo con lo que estás exigiéndole. '
    'El HRV mide los milisegundos que varían entre latido y latido —la mejor ventana a tu sistema nervioso—: alto = recuperado, '
    'bajo = todavía cansado. Y como el HRV se recarga durmiendo, una mala noche se ve al día siguiente.',

    'El HRV es la variación entre tus latidos, el termómetro más fino de tu recuperación; pero un HRV solo dice poco. Por eso '
    'HANNA lo combina con tu carga (CTL/ATL/TSB), tu body battery, tu sueño y tu estrés, y devuelve un índice propio de NOAH '
    '(0-100) que pone tu recuperación EN CONTEXTO con lo que entrenás. No te dice solo "cómo estás", sino cómo estás frente a lo '
    'que te pedís. El sueño es cuando ese HRV se recarga: dormir mal lo baja al otro día.',

    'Pensalo así: HANNA es el semáforo de NOAH (0-100). Toma tu HRV —la variación entre latidos, que refleja tu sistema '
    'nervioso— y lo cruza con tu carga de entrenamiento (CTL/ATL/TSB), tu body battery, el sueño y el estrés, para decirte no '
    'solo cómo estás sino cómo estás EN RELACIÓN a lo que te estás exigiendo. La clave que casi nadie mira: ese HRV se recupera, '
    'sobre todo, durmiendo.',
]
CORTISOL = [
    'El estrés —físico (entrenar fuerte, dormir poco) o emocional (trabajo, vida)— dispara cortisol. En su justa medida hace '
    'falta; el problema es cuando no baja y queda crónicamente alto. Ahí el cuerpo entra en modo supervivencia: se frena la '
    'hormona de crecimiento y la testosterona —las que reparan y construyen músculo de noche—, se altera la sensibilidad a la '
    'insulina (peor recarga de glucógeno, tu combustible), el lactato aparece a intensidades más bajas y se desregula el eje '
    'tiroides-suprarrenales que gobierna tu energía. Traducido: menos adaptación, peor recuperación, más fatiga y más riesgo de '
    'lesión o enfermedad. Por eso cuidar el SNA no es descansar de más: es lo que permite que el entrenamiento se convierta en mejora.',

    'La parte hormonal es la que casi no se cuenta. Cuando el cortisol se queda alto porque el estrés no afloja, apaga a las '
    'hormonas que te hacen mejorar: baja la hormona de crecimiento y la testosterona que reconstruyen el músculo mientras dormís, '
    'la insulina se vuelve menos eficiente para meter glucógeno al músculo, el lactato se acumula antes y las glándulas (tiroides, '
    'suprarrenales) se desregulan. El resultado es un cuerpo que entrena pero no adapta, se fatiga fácil y se enferma. Recuperar '
    'es, literalmente, bajar el cortisol para que esas hormonas vuelvan a trabajar a tu favor.',

    'Lo que pasa adentro: el estrés sostenido mantiene el cortisol elevado, y un cortisol crónico es catabólico —rompe en vez de '
    'construir—. Inhibe la hormona de crecimiento y la testosterona (reparación muscular), degrada el manejo de la insulina y el '
    'glucógeno, adelanta la aparición de lactato y presiona el eje tiroideo-suprarrenal que regula tu energía y tu ánimo. Por eso '
    'un atleta estresado "no levanta" aunque entrene igual: las hormonas que transforman el esfuerzo en forma están apagadas. '
    'Dormir, comer bien y bajar un cambio es lo que las vuelve a encender.',
]
TITULARES = {
    'alarma': ['Semana con señales de alarma — leé con atención',
               'Tu cuerpo te está avisando — vale la pena parar a leer',
               'Atención esta semana: hay señales para no dejar pasar'],
    'sna': ['Tu sistema nervioso viene pidiendo recuperar',
            'Esta semana tu cuerpo pide un respiro, no más gas',
            'Señal clara de recuperación pendiente'],
    'carga': ['Subiste la carga fuerte — ojo con no pasarte',
              'Semana exigente: cuidemos que el salto no te pase factura',
              'Mucha carga nueva — la clave ahora es administrarla'],
    'ok': ['Semana sólida — seguimos construyendo',
           'Buen trabajo esta semana — vamos por más',
           'Semana en orden — la constancia está haciendo lo suyo'],
}

# ── Técnica interpretada por disciplina (criollo, no números sueltos) ───────
def _tecnica(conn, aid, d7, d60, deportes):
    out = {}
    # RUNNING — cadencia / contacto suelo / oscilación
    if 'running' in deportes:
        w = _one(conn,
            "SELECT AVG(sa.cadence), AVG(sa.ground_contact_ms), AVG(sa.vertical_osc_mm), AVG(sa.stride_length_m) "
            "FROM activity_samples sa JOIN sesiones s ON s.id=sa.sesion_id "
            "WHERE s.atleta_id=%s AND s.sport='running' AND s.fecha > %s AND sa.cadence>140", (aid, d7))
        b = _one(conn,
            "SELECT AVG(sa.cadence), AVG(sa.ground_contact_ms) "
            "FROM activity_samples sa JOIN sesiones s ON s.id=sa.sesion_id "
            "WHERE s.atleta_id=%s AND s.sport='running' AND s.fecha > %s AND s.fecha <= %s AND sa.cadence>140",
            (aid, d60, d7))
        cad = _f(_val(w, 0)) if w else 0
        gct = _f(_val(w, 1)) if w else 0
        vo = _f(_val(w, 2)) if w else 0
        cad_b = _f(_val(b, 0)) if b else 0
        gct_b = _f(_val(b, 1)) if b else 0
        ins = []
        if cad:
            if cad_b and cad < cad_b - 3:
                ins.append(f'Tu cadencia bajó (de ~{round(cad_b)} a ~{round(cad)} pasos/min): suele ser señal de fatiga o pérdida de técnica — '
                           f'pisás más largo y frenás en cada apoyo. Buscá volver a tu frecuencia habitual pisando bajo el cuerpo.')
            elif cad < 162:
                ins.append(f'Cadencia baja ({round(cad)} pasos/min): acortá un poco el paso y subí la frecuencia (~170-180). '
                           f'Pisar debajo del cuerpo baja el impacto y el riesgo de lesión.')
            else:
                ins.append(f'Cadencia en buen rango ({round(cad)} pasos/min): seguís pisando eficiente.')
        if gct and gct_b and gct > gct_b + 8:
            ins.append('Más tiempo de contacto con el piso que tu promedio: menos reactividad, típico de fatiga acumulada.')
        if ins:
            out['running'] = ins[:2]
    # CYCLING — equilibrio L/R / cadencia
    if 'cycling' in deportes:
        w = _one(conn,
            "SELECT AVG(sa.cadence), AVG(sa.left_right_pct) "
            "FROM activity_samples sa JOIN sesiones s ON s.id=sa.sesion_id "
            "WHERE s.atleta_id=%s AND s.sport='cycling' AND s.fecha > %s AND sa.cadence>30", (aid, d7))
        cad = _f(_val(w, 0)) if w else 0
        lr = _f(_val(w, 1)) if w else 0
        ins = []
        if lr and abs(50 - lr) >= 4:
            fuerte = 'izquierda' if lr > 50 else 'derecha'
            ins.append(f'Desequilibrio de pedaleo (~{round(lr)}/{round(100 - lr)}): tu pierna {fuerte} hace más trabajo. '
                       f'Puede venir de fatiga, posición en la bici o una molestia — vale revisarlo antes de que se cronifique.')
        if cad:
            if cad < 75:
                ins.append(f'Cadencia baja ({round(cad)} rpm): pedaleás "pesado", mucha fuerza por pedalada que fatiga el músculo. '
                           f'Probá subir a 85-95 rpm para repartir el esfuerzo al sistema cardiovascular.')
            elif cad > 105:
                ins.append(f'Cadencia muy alta ({round(cad)} rpm): podés estar perdiendo estabilidad en la pelvis y eficiencia.')
        if ins:
            out['cycling'] = ins[:2]
    # SWIMMING — SWOLF (eficiencia)
    if 'swimming' in deportes:
        w = _one(conn,
            "SELECT AVG(l.swolf), AVG(l.paladas) FROM laps l JOIN sesiones s ON s.id=l.sesion_id "
            "WHERE s.atleta_id=%s AND s.sport='swimming' AND s.fecha > %s AND l.swolf>0", (aid, d7))
        b = _one(conn,
            "SELECT AVG(l.swolf) FROM laps l JOIN sesiones s ON s.id=l.sesion_id "
            "WHERE s.atleta_id=%s AND s.sport='swimming' AND s.fecha > %s AND s.fecha <= %s AND l.swolf>0",
            (aid, d60, d7))
        sw = _f(_val(w, 0)) if w else 0
        sw_b = _f(_val(b, 0)) if b else 0
        ins = []
        if sw:
            if sw_b and sw > sw_b + 1.5:
                ins.append(f'Tu SWOLF subió (de ~{round(sw_b)} a ~{round(sw)}): estás dando más brazadas o tardando más por largo — '
                           f'perdés eficiencia. Enfocá en el deslizamiento y el agarre del agua, no en apurar la brazada.')
            else:
                ins.append(f'Eficiencia de nado estable (SWOLF ~{round(sw)}): buen equilibrio entre brazadas y velocidad.')
        if ins:
            out['swimming'] = ins[:2]
    return out

def construir_resumen(conn, atleta_id, fecha=None):
    hoy = fecha or date.today()
    if isinstance(hoy, str):
        hoy = date.fromisoformat(hoy[:10])
    d7 = str(hoy - timedelta(days=7))
    d14 = str(hoy - timedelta(days=14))
    d28 = str(hoy - timedelta(days=28))
    d60 = str(hoy - timedelta(days=60))

    a = _fetch(conn, "SELECT * FROM atletas WHERE id=%s", (atleta_id,))
    if not a:
        return None
    row = a[0]
    def _col(*names):
        for n in names:
            try:
                v = row[n]
            except Exception:
                continue
            if v is not None:
                return v
        return None
    nombre = _col('nombre'); email = _col('email')
    peso = _f(_col('peso_kg', 'peso'), 0) or None
    edad = _f(_col('edad'), 0) or None
    altura = _f(_col('altura_cm', 'altura', 'estatura_cm', 'estatura'), 0) or None
    sexo = (str(_col('sexo', 'genero', 'sex', 'genero_bio') or '').strip().lower() or None)

    # Sesiones de la semana
    rows = _fetch(conn,
        "SELECT sport, COALESCE(tss_total,0), COALESCE(duration_min,0), "
        "COALESCE(tss_z12,0), COALESCE(tss_z34,0), COALESCE(tss_z56,0), COALESCE(calorias,0) "
        "FROM sesiones WHERE atleta_id=%s AND fecha > %s AND COALESCE(tss_total,0) > 0", (atleta_id, d7))
    n_ses = len(rows)
    tss_total = sum(_f(_val(r, 1)) for r in rows)
    min_total = sum(_f(_val(r, 2)) for r in rows)
    z12 = sum(_f(_val(r, 3)) for r in rows); z34 = sum(_f(_val(r, 4)) for r in rows); z56 = sum(_f(_val(r, 5)) for r in rows)
    kcal_entreno = sum(_f(_val(r, 6)) for r in rows)
    zt = (z12 + z34 + z56) or 1
    dist = {'facil': round(z12 / zt * 100), 'umbral': round(z34 / zt * 100), 'vo2': round(z56 / zt * 100)}
    por_deporte = {}
    for r in rows:
        dep = _val(r, 0) or 'otro'
        d = por_deporte.setdefault(dep, {'n': 0, 'min': 0.0, 'kcal': 0.0})
        d['n'] += 1; d['min'] += _f(_val(r, 2)); d['kcal'] += _f(_val(r, 6))

    prev = _one(conn, "SELECT COALESCE(SUM(tss_total),0) FROM sesiones "
                "WHERE atleta_id=%s AND fecha > %s AND fecha <= %s AND COALESCE(tss_total,0) > 0", (atleta_id, d14, d7))
    tss_prev = _f(_val(prev, 0)) if prev else 0.0
    delta_tss = round((tss_total / tss_prev - 1) * 100) if tss_prev > 0 else None

    # SNA semana + BASE (28-60 días) para decir "tu ideal"
    sna = _one(conn,
        "SELECT AVG(hanna_life), AVG(sleep_h), AVG(stress_avg), AVG(COALESCE(hrv_rmssd, hrv_estimado_valor)) "
        "FROM sleep_hrv WHERE atleta_id=%s AND fecha::date > %s::date", (atleta_id, d7))
    hanna_avg = _f(_val(sna, 0)) if sna and _val(sna, 0) is not None else None
    sueno_avg = _f(_val(sna, 1)) if sna and _val(sna, 1) is not None else None
    stress_avg = _f(_val(sna, 2)) if sna and _val(sna, 2) is not None else None
    hrv_avg = _f(_val(sna, 3)) if sna and _val(sna, 3) is not None else None
    base = _one(conn,
        "SELECT AVG(hanna_life), AVG(COALESCE(hrv_rmssd, hrv_estimado_valor)) "
        "FROM sleep_hrv WHERE atleta_id=%s AND fecha::date > %s::date AND fecha::date <= %s::date", (atleta_id, d60, d7))
    hanna_base = _f(_val(base, 0)) if base and _val(base, 0) is not None else None
    hrv_base = _f(_val(base, 1)) if base and _val(base, 1) is not None else None
    ult = _one(conn, "SELECT hanna_nivel, riesgo_viral_nivel, riesgo_viral FROM sleep_hrv "
               "WHERE atleta_id=%s AND hanna_life IS NOT NULL ORDER BY fecha DESC LIMIT 1", (atleta_id,))
    hanna_nivel = _val(ult, 0) if ult else None
    viral_nivel = _val(ult, 1) if ult else None
    viral_val = _f(_val(ult, 2)) if ult and _val(ult, 2) is not None else None

    acwr = None
    try:
        from noah_riesgo_lesion import resumen_riesgo_lesion
        rl = resumen_riesgo_lesion(conn, atleta_id, str(hoy))
        if rl and rl.get('acwr', {}).get('disponible'):
            acwr = _f(rl['acwr'].get('acwr'))
    except Exception:
        pass

    # Energía
    basal = None; basal_metodo = 'estimado'
    es_hombre = bool(sexo and sexo.startswith('m') and not sexo.startswith('muj'))
    if peso and altura and edad and sexo:
        basal = (10 * peso + 6.25 * altura - 5 * edad + (5 if es_hombre else -161))
        basal_metodo = 'Mifflin-St Jeor'
    elif peso:
        basal = (24 if es_hombre else 22) * peso
    basal = round(basal) if basal else None
    diario_vida = round(basal * 1.4) if basal else None
    kcal_entreno_dia = round(kcal_entreno / 7) if kcal_entreno else 0
    total_dia = (diario_vida + kcal_entreno_dia) if diario_vida else None

    # Técnica interpretada
    tecnica = _tecnica(conn, atleta_id, d7, d60, por_deporte)

    alertas = []
    try:
        from noah_alertas import calcular_alertas
        ra = calcular_alertas(conn, atleta_id, dias=7, fecha=str(hoy))
        alertas = (ra or {}).get('alertas', [])
    except Exception:
        pass

    tema = TEMAS[hoy.isocalendar()[1] % len(TEMAS)]

    return {
        'nombre': nombre, 'email': email, 'desde': d7, 'hasta': str(hoy),
        'n_ses': n_ses, 'horas': round(min_total / 60, 1),
        'tss_total': round(tss_total), 'tss_prev': round(tss_prev), 'delta_tss': delta_tss,
        'dist': dist,
        'por_deporte': {k: {'n': v['n'], 'horas': round(v['min'] / 60, 1), 'kcal': round(v['kcal'])}
                        for k, v in por_deporte.items()},
        'hanna_avg': round(hanna_avg) if hanna_avg is not None else None, 'hanna_nivel': hanna_nivel,
        'hanna_base': round(hanna_base) if hanna_base is not None else None,
        'sueno_avg': round(sueno_avg, 1) if sueno_avg is not None else None,
        'stress_avg': round(stress_avg) if stress_avg is not None else None,
        'hrv_avg': round(hrv_avg) if hrv_avg is not None else None,
        'hrv_base': round(hrv_base) if hrv_base is not None else None,
        'viral_nivel': viral_nivel, 'viral_val': round(viral_val) if viral_val is not None else None,
        'acwr': round(acwr, 2) if acwr is not None else None,
        'basal': basal, 'basal_metodo': basal_metodo, 'diario_vida': diario_vida,
        'kcal_entreno': round(kcal_entreno), 'kcal_entreno_dia': kcal_entreno_dia, 'total_dia': total_dia,
        'tecnica': tecnica, 'alertas': alertas, 'tema': tema,
        'semana': hoy.isocalendar()[1],
    }

# ── Render ──────────────────────────────────────────────────────────────────
C = {'bg': '#0C0C12', 'card': '#16161F', 'card2': '#1C1C27', 'ink': '#F5F5F7',
     'ink2': '#A1A1AA', 'ink3': '#6B6B76', 'line': '#262630', 'acc': '#38BDF8',
     'ok': '#34D399', 'warn': '#F59E0B', 'bad': '#F87171', 'vi': '#A78BFA'}

def _semaforo(nivel):
    n = (nivel or '').lower()
    if any(b in n for b in ('alto', 'riesgo', 'crítico', 'critico', 'rojo')): return C['bad']
    if any(b in n for b in ('medio', 'atencion', 'atención', 'moderado', 'amarillo')): return C['warn']
    return C['ok']

def _bloque(titulo, cuerpo):
    return (f'<div style="margin-top:14px;padding:16px 18px;background:{C["card"]};border-radius:14px;">'
            f'<div style="color:{C["ink"]};font-size:14px;font-weight:800;margin-bottom:8px;">{titulo}</div>{cuerpo}</div>')

def _p(txt, color=None, size=13):
    return f'<div style="color:{color or C["ink2"]};font-size:{size}px;line-height:1.55;margin-top:4px;">{txt}</div>'

def render_html(r):
    if not r:
        return ''
    sem = r.get('semana', 0)
    if r['alertas'] and any(a.get('severidad') == 'alta' for a in r['alertas']):
        titular = _pick(TITULARES['alarma'], sem)
    elif r['hanna_nivel'] and 'baj' in str(r['hanna_nivel']).lower():
        titular = _pick(TITULARES['sna'], sem)
    elif r['delta_tss'] is not None and r['delta_tss'] >= 25:
        titular = _pick(TITULARES['carga'], sem)
    else:
        titular = _pick(TITULARES['ok'], sem)

    # ── SNA (educativo + personalizado) ──
    bits = []
    if r['hanna_avg'] is not None:
        hc = C['ok'] if r['hanna_avg'] >= 60 else (C['warn'] if r['hanna_avg'] >= 45 else C['bad'])
        bits.append(f'<b style="color:{hc}">HANNA {r["hanna_avg"]}</b>')
    if r['sueno_avg'] is not None:
        sc = C['ok'] if r['sueno_avg'] >= 7 else (C['warn'] if r['sueno_avg'] >= 6 else C['bad'])
        bits.append(f'sueño <b style="color:{sc}">{r["sueno_avg"]} h</b>')
    if r['hrv_avg'] is not None:
        bits.append(f'HRV <b style="color:{C["ink"]}">{r["hrv_avg"]}</b>')
    if r['stress_avg'] is not None:
        bits.append(f'estrés <b style="color:{C["ink"]}">{r["stress_avg"]}</b>')
    linea = ' · '.join(bits) if bits else 'Sin datos de recuperación esta semana.'

    qué = '<b>Qué es esto.</b> ' + _pick(QUE_ES, sem)

    base_txt = ''
    if r['hanna_base'] is not None or r['hrv_base'] is not None:
        partes = []
        if r['hanna_base'] is not None:
            partes.append(f'HANNA ~{r["hanna_base"]}')
        if r['hrv_base'] is not None:
            partes.append(f'HRV ~{r["hrv_base"]}')
        comp = ''
        if r['hrv_avg'] is not None and r['hrv_base']:
            dif = round((r['hrv_avg'] / r['hrv_base'] - 1) * 100)
            if dif <= -8:
                comp = f' Esta semana tu HRV estuvo ~{abs(dif)}% por debajo de tu base: tu cuerpo pide recuperar.'
            elif dif >= 8:
                comp = f' Esta semana tu HRV estuvo ~{dif}% por encima de tu base: muy buena señal de recuperación.'
            else:
                comp = ' Esta semana te mantuviste cerca de tu base, que es lo que buscamos.'
        base_txt = (f'<b>Tu ideal es el TUYO.</b> No hay un número universal: el HRV sano es individual. Según tu historia, '
                    f'tu base saludable ronda {" y ".join(partes)}.' + comp)

    cortisol = '<b>Por qué importa.</b> ' + _pick(CORTISOL, sem)

    sna_html = _bloque('Tu sistema nervioso esta semana',
        _p(linea, C['ink'], 14) + '<div style="height:8px"></div>' +
        _p(qué) + '<div style="height:6px"></div>' +
        (_p(base_txt) + '<div style="height:6px"></div>' if base_txt else '') +
        _p(cortisol))

    # ── Intensidad 80/20 ──
    d = r['dist']; dur = d['umbral'] + d['vo2']
    if dur > 35:
        vint = (f'Hiciste <b style="color:{C["bad"]}">{dur}%</b> de trabajo fuerte (umbral+VO2), bastante más que el ~20% ideal: '
                f'demasiada intensidad sin suficiente base fácil acumula fatiga sin la adaptación que buscás.')
    elif dur < 12 and r['n_ses'] >= 3:
        vint = (f'Casi todo fue fácil ({d["facil"]}% zona 1-2). Buena base; si querés subir el techo, sumá algo de calidad.')
    else:
        vint = f'Distribución equilibrada: ~{d["facil"]}% fácil y ~{dur}% fuerte, cerca del 80/20 ideal. Bien ahí.'
    barra = (f'<div style="display:flex;height:10px;border-radius:5px;overflow:hidden;margin:8px 0;">'
             f'<div style="width:{d["facil"]}%;background:{C["ok"]}"></div>'
             f'<div style="width:{d["umbral"]}%;background:{C["warn"]}"></div>'
             f'<div style="width:{d["vo2"]}%;background:{C["bad"]}"></div></div>'
             f'<div style="font-size:11px;color:{C["ink3"]}">'
             f'<span style="color:{C["ok"]}">■</span> Fácil {d["facil"]}% &nbsp; '
             f'<span style="color:{C["warn"]}">■</span> Umbral/FTP {d["umbral"]}% &nbsp; '
             f'<span style="color:{C["bad"]}">■</span> VO2/Sprint {d["vo2"]}%</div>')
    dep_rows = ''
    for dep, v in r['por_deporte'].items():
        dep_rows += (f'<tr><td style="padding:4px 0;color:{C["ink2"]};font-size:13px;">{SPORT_LBL.get(dep, dep)}</td>'
                     f'<td style="padding:4px 0;text-align:right;color:{C["ink"]};font-size:13px;font-weight:600;">'
                     f'{v["n"]} ses · {v["horas"]} h</td></tr>')
    delta_txt = ''
    if r['delta_tss'] is not None:
        dc = C['bad'] if r['delta_tss'] >= 30 else (C['warn'] if r['delta_tss'] >= 15 else C['ink2'])
        s = '+' if r['delta_tss'] >= 0 else ''
        delta_txt = f' <span style="color:{dc}">({s}{r["delta_tss"]}% vs semana previa)</span>'
    ent_html = _bloque('Cómo entrenaste',
        _p(f'<b>{r["horas"]} h</b> en <b>{r["n_ses"]}</b> sesiones · carga <b>{r["tss_total"]} TSS</b>{delta_txt}', C['ink'], 14) +
        f'<table style="width:100%;border-collapse:collapse;margin:6px 0">{dep_rows}</table>' + barra +
        '<div style="height:4px"></div>' + _p(vint))

    # ── Riesgos ──
    riesgos = []
    if r['acwr'] is not None:
        col = C['bad'] if r['acwr'] >= 1.5 else (C['warn'] if (r['acwr'] >= 1.3 or r['acwr'] < 0.8) else C['ok'])
        msg = ('en zona de riesgo — bajá un cambio' if r['acwr'] >= 1.3 else
               ('poca carga, podés progresar' if r['acwr'] < 0.8 else 'en zona óptima'))
        riesgos.append(f'<b style="color:{col}">Lesión (ACWR {r["acwr"]})</b>: {msg}.')
    if r['viral_nivel'] or r['viral_val'] is not None:
        col = _semaforo(r['viral_nivel'])
        extra = f' ({r["viral_val"]}%)' if r['viral_val'] is not None else ''
        msg = ('defensas bajas — si hay síntomas, no entrenar' if col == C['bad'] else
               ('vigilá síntomas en 48 h' if col == C['warn'] else 'sin señales de enfermedad'))
        riesgos.append(f'<b style="color:{col}">Viral{extra}</b>: {msg}.')
    riesgos_html = _bloque('Riesgos', ''.join(_p(x) for x in riesgos) if riesgos else _p('Sin datos de riesgo esta semana.'))

    # ── Energía ──
    if r['basal']:
        aclara = '' if r['basal_metodo'] == 'Mifflin-St Jeor' else f' <span style="color:{C["ink3"]}">(estimado)</span>'
        energia_html = _bloque('Energía y nutrición',
            _p(f'Basal (en reposo): <b style="color:{C["ink"]}">{r["basal"]} kcal/día</b>{aclara}') +
            _p(f'Con tu vida diaria sin entrenar: <b style="color:{C["ink"]}">~{r["diario_vida"]} kcal/día</b> '
               f'<span style="color:{C["ink3"]}">(estimado)</span>') +
            _p(f'Entrenamiento esta semana: <b style="color:{C["acc"]}">{r["kcal_entreno"]} kcal</b> '
               f'<span style="color:{C["ink3"]}">(real, de tu reloj)</span> → ~{r["kcal_entreno_dia"]} kcal/día') +
            (_p(f'Gasto total aproximado: <b style="color:{C["ink"]}">~{r["total_dia"]} kcal/día</b>') if r['total_dia'] else '') +
            '<div style="height:6px"></div>' +
            _p('NOAH calcula el gasto de cada sesión con tu FC, ritmo/potencia y duración. Comer sostenidamente por debajo de '
               'esto frena las adaptaciones y baja las defensas: reponer es parte del plan.'))
    else:
        energia_html = _bloque('Energía y nutrición',
            _p('Faltan datos de peso/altura en tu perfil para estimar el gasto. Cargalos y la próxima semana te lo muestro.'))

    # ── Técnica por disciplina (interpretada) ──
    tec = r.get('tecnica') or {}
    if tec:
        cuerpo = ''
        for dep, ins in tec.items():
            cuerpo += (f'<div style="margin-top:8px"><span style="color:{C["acc"]};font-size:12px;font-weight:800;">'
                       f'{SPORT_LBL.get(dep, dep).upper()}</span>')
            for x in ins:
                cuerpo += _p(x)
            cuerpo += '</div>'
        tecnica_html = _bloque('Tu técnica esta semana', cuerpo)
    else:
        tecnica_html = ''

    # ── Tema + acciones ──
    tema = r['tema']
    tema_html = (f'<div style="margin-top:14px;padding:18px;background:linear-gradient(135deg,{C["card2"]},{C["card"]});'
                 f'border-radius:14px;border:1px solid {C["line"]};">'
                 f'<div style="color:{C["acc"]};font-size:11px;font-weight:800;letter-spacing:1px;">TEMA DE LA SEMANA</div>'
                 f'<div style="color:{C["ink"]};font-size:15px;font-weight:800;margin:6px 0 8px;">{tema["t"]}</div>'
                 f'{_p(tema["c"], C["ink2"])}</div>')
    acciones = []
    if r['hanna_avg'] is not None and r['hanna_avg'] < 50:
        acciones.append('Priorizá sueño (7-8 h) y bajá la intensidad hasta que HANNA se recupere.')
    if (r['dist']['umbral'] + r['dist']['vo2']) > 35:
        acciones.append('Sumá volumen fácil (zona 1-2) y recortá una sesión dura.')
    if r['acwr'] is not None and r['acwr'] >= 1.3:
        acciones.append('No subas la carga hasta que el ACWR vuelva a 0.8-1.3.')
    if not acciones:
        acciones.append('Mantené el rumbo: la constancia es lo que construye forma.')
    acc_html = _bloque('Tu foco para esta semana',
        ''.join(f'<div style="color:{C["ink"]};font-size:13px;line-height:1.6;">• {x}</div>' for x in acciones))

    return f'''<!doctype html><html><body style="margin:0;padding:0;background:{C["bg"]};">
<div style="max-width:600px;margin:0 auto;padding:26px 20px;font-family:Arial,Helvetica,sans-serif;">
  <div style="color:{C["acc"]};font-size:12px;font-weight:800;letter-spacing:2px;">NOAH · RESUMEN SEMANAL</div>
  <div style="color:{C["ink"]};font-size:21px;font-weight:800;margin-top:8px;line-height:1.25;">{titular}</div>
  <div style="color:{C["ink3"]};font-size:12px;margin-top:4px;">{r["nombre"]} · {r["desde"]} al {r["hasta"]}</div>
  {sna_html}
  {ent_html}
  {riesgos_html}
  {energia_html}
  {tecnica_html}
  {tema_html}
  {acc_html}
  <div style="margin-top:22px;color:{C["ink3"]};font-size:11px;line-height:1.5;">
    Resumen automático de NOAH · todos los lunes. Entrá a la app para ver el detalle de cada número.
  </div>
</div></body></html>'''
