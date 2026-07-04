path = r'C:\Users\Win10\Desktop\noah_cloud\noah_ml.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# ── 1. Agregar funcion _enriquecer_con_feedback despues de construir_dataset ──
OLD_END = """    # Flag de sesión intensa (TSS > 80)
    df['sesion_intensa'] = (df['tss_dia'] > 80).astype(int)

    return df"""

NEW_END = """    # Flag de sesión intensa (TSS > 80)
    df['sesion_intensa'] = (df['tss_dia'] > 80).astype(int)

    # Enriquecer con datos de feedback (cierre del ciclo prescripcion -> realizado -> respuesta)
    df = _enriquecer_con_feedback(df, conn, atleta_id)

    return df


def _enriquecer_con_feedback(df: pd.DataFrame, conn, atleta_id: int) -> pd.DataFrame:
    \"\"\"
    Agrega features derivados de noah_feedback al dataset principal.
    Cierra el ciclo: lo que NOAH prescribio vs lo que el atleta hizo vs como respondio.

    Features que agrega:
      adherencia_7d       — promedio de cumplimiento_tss ultimos 7 dias
                            (>1 = hace mas de lo prescripto, <1 = hace menos)
      hrv_respuesta_7d    — promedio de impacto_hrv ultimos 7 dias
                            (indica si el atleta absorbe bien la carga prescripta)
      pct_sobrecarga_14d  — % sesiones con resultado 'sobrecarga' en 14 dias
      pct_optima_14d      — % sesiones con resultado 'optima' en 14 dias
      patron_carga        — indice personal: adherencia_7d * (1 + hrv_respuesta_7d/10)
                            captura si el atleta sobreejercita Y aguanta bien o no
    \"\"\"
    try:
        tbl = conn.execute(
            \"SELECT table_name FROM information_schema.tables \"
            \"WHERE table_schema='public' AND table_name='noah_feedback'\"
        ).fetchone()
        if not tbl:
            return df

        df_fb = _read_sql('''
            SELECT fecha, cumplimiento_tss, impacto_hrv, resultado
            FROM noah_feedback
            WHERE atleta_id=%s
            ORDER BY fecha
        ''', conn, params=[atleta_id])

        if df_fb.empty:
            return df

        df_fb['fecha'] = pd.to_datetime(df_fb['fecha'])
        df_fb['cumplimiento_tss'] = pd.to_numeric(df_fb['cumplimiento_tss'], errors='coerce')
        df_fb['impacto_hrv']      = pd.to_numeric(df_fb['impacto_hrv'],      errors='coerce')
        df_fb['es_sobrecarga']    = (df_fb['resultado'] == 'sobrecarga').astype(float)
        df_fb['es_optima']        = (df_fb['resultado'] == 'optima').astype(float)

        # Agrupar por dia (puede haber multiples sesiones)
        df_fb_dia = df_fb.groupby('fecha').agg(
            adherencia_dia    = ('cumplimiento_tss', 'mean'),
            hrv_resp_dia      = ('impacto_hrv',      'mean'),
            sobrecarga_dia    = ('es_sobrecarga',     'max'),
            optima_dia        = ('es_optima',         'max'),
        ).reset_index()

        # Merge con dataset principal
        df['fecha_dt'] = pd.to_datetime(df['fecha'])
        df = df.merge(df_fb_dia, left_on='fecha_dt', right_on='fecha',
                      how='left', suffixes=('', '_fb'))

        # Rolling features (ventana deslizante — no usa datos futuros)
        df = df.sort_values('fecha_dt').reset_index(drop=True)

        df['adherencia_7d']      = df['adherencia_dia'].rolling(7,  min_periods=1).mean()
        df['hrv_respuesta_7d']   = df['hrv_resp_dia'].rolling(7,    min_periods=1).mean()
        df['pct_sobrecarga_14d'] = df['sobrecarga_dia'].rolling(14, min_periods=1).mean()
        df['pct_optima_14d']     = df['optima_dia'].rolling(14,     min_periods=1).mean()

        # Patron de carga personal: combina adherencia con respuesta HRV
        # Si hace 162% y HRV baja poco → patron_carga alto = tolera bien la sobrecarga
        # Si hace 94% y HRV baja mucho → patron_carga bajo = sensible a la carga
        df['patron_carga'] = (
            df['adherencia_7d'].fillna(1.0) *
            (1 + df['hrv_respuesta_7d'].fillna(0) / 10)
        )

        # Limpiar columnas temporales
        df = df.drop(columns=[c for c in ['fecha_fb', 'fecha_dt',
                               'adherencia_dia', 'hrv_resp_dia',
                               'sobrecarga_dia', 'optima_dia'] if c in df.columns])

        n_dias_feedback = df['adherencia_7d'].notna().sum()
        print(f'  [Feedback] {n_dias_feedback} dias con datos de ciclo cerrado')

    except Exception as e:
        print(f'  [Feedback] Error enriqueciendo con feedback: {e}')

    return df"""

if OLD_END in content:
    content = content.replace(OLD_END, NEW_END)
    print("OK 1 - _enriquecer_con_feedback agregado a construir_dataset")
else:
    print("ERROR 1 - no matcheo el final de construir_dataset")

# ── 2. Agregar nuevas features a FEATURES_BASE de PredictorRespuestaFisiologica ──
OLD_FEATURES = """    FEATURES_BASE = [
        'ctl', 'atl', 'tsb',
        'tss_7d', 'tss_14d',
        'hrv_7d_avg', 'stress_7d_avg', 'sleep_7d_avg',
        'hrv_ratio_7d', 'delta_hrv', 'delta_stress',
        'sesion_intensa',
    ]
    FEATURES_OPT = [
        'pct_deep_rem', 'hanna_vfc', 'hanna_vfc_ratio',
        'recovery_score', 'spo2_avg',
    ]"""

NEW_FEATURES = """    FEATURES_BASE = [
        'ctl', 'atl', 'tsb',
        'tss_7d', 'tss_14d',
        'hrv_7d_avg', 'stress_7d_avg', 'sleep_7d_avg',
        'hrv_ratio_7d', 'delta_hrv', 'delta_stress',
        'sesion_intensa',
        # Ciclo cerrado: prescripcion -> realizado -> respuesta fisiologica
        'adherencia_7d',       # patron de cumplimiento personal (>1 sobreejercita)
        'hrv_respuesta_7d',    # como responde fisiologicamente a la carga prescripta
        'pct_sobrecarga_14d',  # % sesiones con sobrecarga reciente
        'patron_carga',        # indice integrado: adherencia x tolerancia HRV
    ]
    FEATURES_OPT = [
        'pct_deep_rem', 'hanna_vfc', 'hanna_vfc_ratio',
        'recovery_score', 'spo2_avg',
        'pct_optima_14d',      # % sesiones optimas recientes
    ]"""

if OLD_FEATURES in content:
    content = content.replace(OLD_FEATURES, NEW_FEATURES)
    print("OK 2 - FEATURES_BASE actualizado con features de ciclo cerrado")
else:
    print("ERROR 2 - no matcheo FEATURES_BASE")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("\nGUARDADO OK - noah_ml.py con ciclo cerrado")
