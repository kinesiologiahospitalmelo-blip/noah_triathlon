path = r'C:\Users\Win10\Desktop\noah_cloud\noah_optimizer.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# ── 1. Agregar ml_escenarios a seleccionar_receta() ──────────────────────────
OLD_SEL = """def seleccionar_receta(
    estado_actual: dict,
    cluster_historico: Optional[dict],
    fase: str = 'A',
    semanas_hasta_carrera: Optional[int] = None,
    k_params: Optional[dict] = None,
) -> dict:
    \"\"\"
    Selecciona el tipo de receta óptima para la próxima semana.

    Combina:
    - Estado autonómico actual (HANNA LIFE, HRV)
    - Cluster histórico del atleta (qué funcionó)
    - Fase del ciclo (A/T/R/Taper)
    - Urgencia temporal (semanas hasta carrera A)
    \"\"\""""

NEW_SEL = """def seleccionar_receta(
    estado_actual: dict,
    cluster_historico: Optional[dict],
    fase: str = 'A',
    semanas_hasta_carrera: Optional[int] = None,
    k_params: Optional[dict] = None,
    ml_escenarios: Optional[list] = None,
) -> dict:
    \"\"\"
    Selecciona el tipo de receta óptima para la próxima semana.

    Combina:
    - Estado autonómico actual (HANNA LIFE, HRV)
    - Cluster histórico del atleta (qué funcionó)
    - Fase del ciclo (A/T/R/Taper)
    - Urgencia temporal (semanas hasta carrera A)
    - Predicciones ML personalizadas (PredictorRespuestaFisiologica)
    \"\"\""""

if OLD_SEL in content:
    content = content.replace(OLD_SEL, NEW_SEL)
    print("OK 1 - seleccionar_receta acepta ml_escenarios")
else:
    print("ERROR 1 - no matcheo seleccionar_receta header")

# ── 2. Usar ml_escenarios para ajustar la receta final ───────────────────────
OLD_RETURN = """    # Simular las opciones para comparar
    opciones = {}
    for tipo in ['volumen', 'calidad', 'mixta', 'recuperacion']:
        opciones[tipo] = predecir_respuesta_receta(estado_actual, tipo, semanas=4, k_params=k_params)

    return {
        'receta_recomendada': receta,
        'razon':              razon,
        'fase':               fase,
        'semanas_carrera':    semanas_hasta_carrera,
        'opciones_simuladas': opciones,
        'receta_seleccionada': opciones.get(receta, {}),
    }"""

NEW_RETURN = """    # Simular las opciones con Banister (base)
    opciones = {}
    for tipo in ['volumen', 'calidad', 'mixta', 'recuperacion']:
        opciones[tipo] = predecir_respuesta_receta(estado_actual, tipo, semanas=4, k_params=k_params)

    # Enriquecer con predicciones ML si están disponibles
    ml_por_tss = {}
    if ml_escenarios:
        for esc in ml_escenarios:
            tss = esc.get('tss_plan', 0)
            ml_por_tss[tss] = esc

    ajuste_ml = None
    if ml_escenarios:
        # Encontrar el escenario ML con mejor balance: absorcion alta + riesgo bajo + delta_ctl positivo
        mejor_ml = None
        mejor_score_ml = -999
        for esc in ml_escenarios:
            if not esc.get('disponible'): continue
            score = (
                esc.get('prob_absorcion', 0.5) * 2       # absorcion pesa doble
                - esc.get('prob_riesgo_sobrecarga', 0.3)  # penalizar riesgo
                + max(0, esc.get('delta_ctl_predicho', 0)) * 0.5  # bonus CTL positivo
            )
            if score > mejor_score_ml:
                mejor_score_ml = score
                mejor_ml = esc

        # Ajustar receta si ML detecta conflicto con seleccion basada en reglas
        if mejor_ml:
            prob_riesgo = mejor_ml.get('prob_riesgo_sobrecarga', 0.3)
            prob_abs    = mejor_ml.get('prob_absorcion', 0.5)
            delta_ctl   = mejor_ml.get('delta_ctl_predicho', 0)

            if prob_riesgo >= 0.65 and receta in ('volumen', 'calidad', 'aumentar_carga'):
                receta_prev = receta
                receta = 'recuperacion_activa' if hanna >= 50 else 'recuperacion'
                razon  = f'ML detecta alto riesgo sobrecarga ({prob_riesgo:.0%}) — ajustando de {receta_prev} a {receta}'
                ajuste_ml = 'reducido_por_riesgo'
            elif prob_abs >= 0.75 and delta_ctl > 0 and receta == 'recuperacion':
                receta_prev = receta
                receta = 'mixta'
                razon  = f'ML predice buena absorcion ({prob_abs:.0%}) y CTL+{delta_ctl:.1f} — elevando de {receta_prev} a mixta'
                ajuste_ml = 'elevado_por_ml'

    return {
        'receta_recomendada':  receta,
        'razon':               razon,
        'fase':                fase,
        'semanas_carrera':     semanas_hasta_carrera,
        'opciones_simuladas':  opciones,
        'receta_seleccionada': opciones.get(receta, {}),
        'ml_escenarios':       ml_escenarios or [],
        'ajuste_ml':           ajuste_ml,
    }"""

if OLD_RETURN in content:
    content = content.replace(OLD_RETURN, NEW_RETURN)
    print("OK 2 - seleccionar_receta usa ML para ajustar receta")
else:
    print("ERROR 2 - no matcheo return de seleccionar_receta")

# ── 3. En analizar_atleta, cargar modelo ML y pasarlo a seleccionar_receta ───
OLD_RECETA_CALL = """    # 7. Seleccionar receta
    receta = seleccionar_receta(
        estado_actual=estado_actual,
        cluster_historico=cluster_optimo,
        fase=fase_actual,
        semanas_hasta_carrera=sem_hasta_carrera,
        k_params=k_params,
    )"""

NEW_RECETA_CALL = """    # 7. Predicciones ML personalizadas (PredictorRespuestaFisiologica)
    ml_escenarios = []
    try:
        from noah_ml import NOAHMind
        mind = NOAHMind.cargar_modelos(conn, atleta_id)
        if mind and mind.predictor_respuesta.entrenado:
            # Calcular estado extendido con features de rolling
            if mind.df is None:
                mind.preparar_datos()
            # Tomar el estado del ultimo dia del dataset
            ultimo = mind.df.dropna(subset=['ctl']).tail(1)
            if not ultimo.empty:
                estado_ml = {}
                for col in mind.predictor_respuesta.features_usados:
                    v = ultimo[col].values[0] if col in ultimo.columns else None
                    estado_ml[col] = float(v) if v is not None and str(v) != 'nan' else 0.0
                # Simular 5 escenarios de TSS
                ctl_base = estado_actual.get('ctl', 30)
                tss_opciones = [round(ctl_base * f * 7) for f in [0.6, 0.8, 1.0, 1.1, 1.2]]
                ml_escenarios = mind.predictor_respuesta.simular_escenarios(estado_ml, tss_opciones)
                print(f'  [ML] {len(ml_escenarios)} escenarios ML calculados')
    except Exception as e:
        print(f'  [ML] Predicciones ML no disponibles: {e}')

    # 8. Seleccionar receta (Banister + ML)
    receta = seleccionar_receta(
        estado_actual=estado_actual,
        cluster_historico=cluster_optimo,
        fase=fase_actual,
        semanas_hasta_carrera=sem_hasta_carrera,
        k_params=k_params,
        ml_escenarios=ml_escenarios if ml_escenarios else None,
    )"""

if OLD_RECETA_CALL in content:
    content = content.replace(OLD_RECETA_CALL, NEW_RECETA_CALL)
    print("OK 3 - analizar_atleta carga ML y pasa escenarios a seleccionar_receta")
else:
    print("ERROR 3 - no matcheo llamada a seleccionar_receta en analizar_atleta")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("\nGUARDADO OK - noah_optimizer.py conectado con PredictorRespuestaFisiologica")
