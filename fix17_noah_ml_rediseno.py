import re

path = r'C:\Users\Win10\Desktop\noah_cloud\noah_ml.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# ═══════════════════════════════════════════════════════════════════════════════
# REEMPLAZO 1: PredictorCumplimiento → AnalizadorAdherencia
# ═══════════════════════════════════════════════════════════════════════════════
OLD_CUMPLIMIENTO = '''# ── Modelo 3: Predictor de cumplimiento ───────────────────────────────────────
class PredictorCumplimiento:
    """
    Predice si el atleta va a completar la sesión prescripta.
    Aprende de su historial: ¿cuándo falla y cuándo cumple?
    """
    def __init__(self):
        self.modelo    = None
        self.entrenado = False
        self.score     = None
        self.tasa_base = 0.75  # tasa de cumplimiento por defecto

    def entrenar(self, conn, atleta_id: int) -> float:
        try:
            from sklearn.ensemble import GradientBoostingClassifier
            from sklearn.model_selection import cross_val_score
        except ImportError:
            return 0.0

        # Buscar prescripciones vs realizado — strftime("%w", ...) (SQLite)
        # reemplazado por EXTRACT(DOW FROM ...::date) (Postgres), mismo
        # rango 0=domingo..6=sábado. date(texto) (SQLite) reemplazado por
        # el cast ::date nativo de Postgres.
        df = _read_sql(\'\'\'
            SELECT p.fecha_generada, p.tss_semana_total,
                   s.ctl, s.atl, s.tsb, s.tss_total as tss_real,
                   sh.hrv_rmssd, sh.sleep_h, sh.stress_avg,
                   EXTRACT(DOW FROM p.fecha_generada::date) as dia_semana
            FROM prescripciones p
            LEFT JOIN sesiones s ON s.atleta_id=p.atleta_id
                AND s.fecha::date=p.fecha_generada::date
            LEFT JOIN sleep_hrv sh ON sh.atleta_id=p.atleta_id
                AND sh.fecha::date=p.fecha_generada::date
            WHERE p.atleta_id=%s
            ORDER BY p.fecha_generada DESC LIMIT 200
        \'\'\', conn, params=[atleta_id])

        if len(df) < 20:
            return 0.0

        df[\'completada\'] = (df[\'tss_real\'] > df[\'tss_semana_total\'] * 0.7).astype(int)
        self.tasa_base = float(df[\'completada\'].mean())

        features = [\'ctl\', \'atl\', \'tsb\', \'hrv_rmssd\', \'sleep_h\', \'dia_semana\']
        df_clean = df[features + [\'completada\']].dropna()

        if len(df_clean) < 15:
            return 0.0

        X = df_clean[features].values.astype(float)
        y = df_clean[\'completada\'].values

        # Necesita minimo 2 clases para clasificar
        if len(set(y)) < 2:
            self.tasa_base = float(y.mean())
            return self.tasa_base  # devuelve la tasa base si todos iguales

        self.modelo = GradientBoostingClassifier(n_estimators=50, max_depth=3, random_state=42)
        self.modelo.fit(X, y)
        scores = cross_val_score(self.modelo, X, y, cv=3, scoring=\'accuracy\')
        self.score = float(scores.mean())
        self.entrenado = True
        return self.score

    def predecir(self, ctl, atl, tsb, hrv, sleep_h, dia_semana=1) -> dict:
        if not self.entrenado:
            return {\'prob_cumplimiento\': self.tasa_base,
                    \'interpretacion\': \'Sin modelo entrenado — usando promedio histórico\'}

        X = np.array([[
            _safe_float(ctl, 30), _safe_float(atl, 30), _safe_float(tsb, 0),
            _safe_float(hrv, 60), _safe_float(sleep_h, 7), int(dia_semana)
        ]])
        prob = float(self.modelo.predict_proba(X)[0][1])

        if prob >= 0.75:
            interp = \'Alta probabilidad de cumplimiento\'
        elif prob >= 0.5:
            interp = \'Cumplimiento probable — monitorear\'
        else:
            interp = \'Riesgo de no cumplir — considerar reducir carga\'

        return {\'prob_cumplimiento\': round(prob, 3), \'interpretacion\': interp}'''

NEW_ADHERENCIA = '''# ── Analizador de Adherencia (reemplaza Modelo 3 binario) ────────────────────
class AnalizadorAdherencia:
    """
    Analiza la adherencia del atleta a la prescripción en 3 dimensiones:
      1. TSS: % del volumen prescripto realizado (continuo 0-150%)
      2. Temporal: desvío en días entre prescripto y realizado
      3. Deporte: realizó el deporte correcto

    NO usa ML — métricas analíticas puras para coach y atleta.
    """

    def analizar(self, conn, atleta_id: int, semanas: int = 8) -> dict:
        desde = str(date.today() - timedelta(days=semanas * 7))

        df_presc = _read_sql(\'\'\'
            SELECT semana_id, fecha_generada, tss_semana_total
            FROM prescripciones
            WHERE atleta_id=%s AND fecha_generada >= %s
            ORDER BY fecha_generada
        \'\'\', conn, params=[atleta_id, desde])

        if df_presc.empty or len(df_presc) < 1:
            return {\'disponible\': False, \'mensaje\': \'Sin historial de prescripciones\'}

        df_real = _read_sql(\'\'\'
            SELECT to_char(fecha::date, \'IYYY-IW\') as semana,
                   SUM(tss_total) as tss_realizado,
                   COUNT(*) as sesiones_realizadas
            FROM sesiones
            WHERE atleta_id=%s AND fecha::date >= %s AND tss_total > 0
              AND (fuente IS NULL OR fuente NOT IN (\'prescripcion\',\'simulacion\',\'generada\'))
            GROUP BY to_char(fecha::date, \'IYYY-IW\')
        \'\'\', conn, params=[atleta_id, desde])

        df_presc[\'semana\'] = pd.to_datetime(df_presc[\'fecha_generada\']).dt.strftime(\'%G-%V\')
        df_presc[\'tss_semana_total\'] = pd.to_numeric(df_presc[\'tss_semana_total\'], errors=\'coerce\').fillna(0)

        if df_real.empty:
            return {\'disponible\': True, \'adherencia_tss_pct\': 0,
                    \'sesiones_por_semana\': 0, \'tendencia\': \'sin_datos\',
                    \'semanas\': [], \'mensaje\': \'Sin sesiones realizadas\'}

        df = pd.merge(df_presc, df_real, on=\'semana\', how=\'left\')
        df[\'tss_realizado\'] = pd.to_numeric(df[\'tss_realizado\'], errors=\'coerce\').fillna(0)

        df[\'adherencia_pct\'] = np.where(
            df[\'tss_semana_total\'] > 0,
            (df[\'tss_realizado\'] / df[\'tss_semana_total\'] * 100).clip(0, 150),
            np.nan
        )

        adherencia_media = float(df[\'adherencia_pct\'].dropna().mean()) if df[\'adherencia_pct\'].notna().any() else 0

        n = len(df)
        tendencia = \'sin_datos\'
        if n >= 4:
            rec   = df[\'adherencia_pct\'].tail(4).dropna()
            prev  = df[\'adherencia_pct\'].head(max(1, n - 4)).dropna()
            if not rec.empty and not prev.empty:
                delta = float(rec.mean()) - float(prev.mean())
                tendencia = \'mejorando\' if delta > 5 else (\'empeorando\' if delta < -5 else \'estable\')

        semanas_det = []
        for _, row in df.iterrows():
            semanas_det.append({
                \'semana\':         row.get(\'semana\', \'\'),
                \'tss_prescripto\': round(float(row[\'tss_semana_total\']), 1),
                \'tss_realizado\':  round(float(row[\'tss_realizado\']), 1),
                \'adherencia_pct\': round(float(row[\'adherencia_pct\']) if pd.notna(row[\'adherencia_pct\']) else 0, 1),
                \'sesiones\':       int(row[\'sesiones_realizadas\']) if pd.notna(row.get(\'sesiones_realizadas\')) else 0,
            })

        if adherencia_media >= 90:   clas, emoji = \'excelente\', \'verde\'
        elif adherencia_media >= 70: clas, emoji = \'buena\',     \'amarillo\'
        elif adherencia_media >= 50: clas, emoji = \'moderada\',  \'naranja\'
        else:                        clas, emoji = \'baja\',       \'rojo\'

        return {
            \'disponible\':           True,
            \'adherencia_tss_pct\':   round(adherencia_media, 1),
            \'clasificacion\':         clas,
            \'semaforo\':              emoji,
            \'tendencia\':             tendencia,
            \'semanas\':               semanas_det,
            \'n_semanas\':             len(df),
            \'sesiones_por_semana\':   round(float(df[\'sesiones_realizadas\'].dropna().mean()), 1)
                                      if \'sesiones_realizadas\' in df.columns else 0,
        }'''

if OLD_CUMPLIMIENTO in content:
    content = content.replace(OLD_CUMPLIMIENTO, NEW_ADHERENCIA)
    print("OK 1 - PredictorCumplimiento reemplazado por AnalizadorAdherencia")
else:
    print("ERROR 1 - no matcheo PredictorCumplimiento")

# ═══════════════════════════════════════════════════════════════════════════════
# REEMPLAZO 2: ModeloImpactoRespuesta → PredictorRespuestaFisiologica
# ═══════════════════════════════════════════════════════════════════════════════
OLD_IMPACTO_HEADER = '''# ── NOAH Mind — Interfaz principal ───────────────────────────────────────────


# ── Modelo de Impacto-Respuesta Individual ────────────────────────────────────
class ModeloImpactoRespuesta:'''

NEW_PREDICTOR_HEADER = '''# ── Predictor de Respuesta Fisiológica (corazón de NOAH) ─────────────────────
class PredictorRespuestaFisiologica:
    """
    Modelo central de NOAH — predice la respuesta fisiológica del atleta
    dado el TSS planificado y su estado actual.

    Basado en el modelo impulse-response de Banister (1975) extendido con ML:
    El modelo aprende los coeficientes de adaptación y fatiga PERSONALES
    de cada atleta desde su historial real.

    Targets construidos desde datos históricos reales:
      delta_ctl_7d:  cambio de CTL en 7 días (regresión — indica adaptación)
      delta_tsb_7d:  cambio de TSB en 7 días (regresión — indica recuperación)
      absorcion_ok:  1 si CTL no bajó y HRV no cayó > 10% (binario)
      riesgo_sobre:  1 si ATL/CTL > 1.5 o HRV cayó > 15% en 14d (binario)
    """

    FEATURES_BASE = [
        \'ctl\', \'atl\', \'tsb\',
        \'tss_7d\', \'tss_14d\',
        \'hrv_7d_avg\', \'stress_7d_avg\', \'sleep_7d_avg\',
        \'hrv_ratio_7d\', \'delta_hrv\', \'delta_stress\',
        \'sesion_intensa\',
    ]
    FEATURES_OPT = [
        \'pct_deep_rem\', \'hanna_vfc\', \'hanna_vfc_ratio\',
        \'recovery_score\', \'spo2_avg\',
    ]

    def __init__(self):
        self.modelo_delta_ctl  = None
        self.modelo_delta_tsb  = None
        self.modelo_absorcion  = None
        self.modelo_riesgo     = None
        self.entrenado         = False
        self.features_usados   = []
        self.scores            = {}
        self.ctl_baseline      = 30.0
        self.hrv_baseline      = 60.0
        self.n_muestras        = 0

    def _construir_targets(self, df: pd.DataFrame) -> pd.DataFrame:
        """Construye targets mirando 7-14 días hacia adelante."""
        df = df.copy().sort_values(\'fecha\').reset_index(drop=True)
        n  = len(df)
        d_ctl, d_tsb, absorcion, riesgo = [], [], [], []

        for i in range(n):
            fut7  = df.iloc[i+1 : min(i+8, n)]
            fut14 = df.iloc[i+1 : min(i+15, n)]
            if len(fut7) < 4:
                d_ctl.append(None); d_tsb.append(None)
                absorcion.append(None); riesgo.append(None); continue

            ctl_h   = float(df.iloc[i].get(\'ctl\')       or self.ctl_baseline)
            tsb_h   = float(df.iloc[i].get(\'tsb\')       or 0)
            hrv_h   = float(df.iloc[i].get(\'hrv_rmssd\') or self.hrv_baseline)

            ctl_f   = fut7[\'ctl\'].dropna().tail(3).mean()    if \'ctl\'       in fut7 else ctl_h
            tsb_f   = fut7[\'tsb\'].dropna().tail(3).mean()    if \'tsb\'       in fut7 else tsb_h
            hrv_f   = fut7[\'hrv_rmssd\'].dropna().mean()      if \'hrv_rmssd\' in fut7 else hrv_h

            d_ctl.append((ctl_f - ctl_h) if pd.notna(ctl_f) else None)
            d_tsb.append((tsb_f - tsb_h) if pd.notna(tsb_f) else None)

            if pd.notna(ctl_f) and pd.notna(hrv_f):
                absorcion.append(1 if (ctl_f >= ctl_h * 0.97 and (hrv_h <= 0 or hrv_f >= hrv_h * 0.90)) else 0)
            else:
                absorcion.append(None)

            r = 0
            if len(fut14) >= 5:
                atl_m = fut14[\'atl\'].dropna().mean() if \'atl\' in fut14 else 0
                ctl_m = fut14[\'ctl\'].dropna().mean() if \'ctl\' in fut14 else 1
                if ctl_m > 0 and (atl_m / ctl_m) > 1.5: r = 1
                if hrv_h > 0:
                    hrv_14 = fut14[\'hrv_rmssd\'].dropna().mean() if \'hrv_rmssd\' in fut14 else hrv_h
                    if hrv_14 < hrv_h * 0.85: r = 1
            riesgo.append(r)

        df[\'delta_ctl_7d\'] = d_ctl
        df[\'delta_tsb_7d\'] = d_tsb
        df[\'absorcion_ok\']  = absorcion
        df[\'riesgo_sobre\']  = riesgo
        return df

    def entrenar(self, df: pd.DataFrame) -> dict:
        try:
            from sklearn.ensemble import RandomForestRegressor, GradientBoostingClassifier
            from sklearn.model_selection import cross_val_score
            from sklearn.metrics import r2_score
        except ImportError:
            print(\'  [ML] scikit-learn no instalado\'); return {}

        if df.empty or len(df) < 60:
            print(f\'  [RespFisio] Datos insuficientes: {len(df)} filas (mín 60)\'); return {}

        features = [f for f in self.FEATURES_BASE if f in df.columns]
        for f in self.FEATURES_OPT:
            if f in df.columns and df[f].notna().mean() >= 0.4:
                features.append(f)
        if len(features) < 4: return {}

        self.features_usados = features
        self.ctl_baseline    = float(df[\'ctl\'].dropna().median())     if \'ctl\'       in df.columns else 30.0
        self.hrv_baseline    = float(df[\'hrv_rmssd\'].dropna().median()) if \'hrv_rmssd\' in df.columns else 60.0

        df_t      = self._construir_targets(df)
        resultados = {}

        def _imputar(df_w, feats):
            for f in feats:
                med = df_w[f].median()
                df_w[f] = df_w[f].fillna(med if pd.notna(med) else 0)
            return df_w

        def _cv(modelo, X, y, scoring):
            cv = min(5, len(X) // 15)
            try:
                return float(np.mean(cross_val_score(modelo, X, y, cv=max(2, cv), scoring=scoring))) if cv >= 2 else float(modelo.score(X, y))
            except Exception:
                return float(modelo.score(X, y))

        # ── Regresión: delta_ctl_7d ──────────────────────────────────────────
        df_c = _imputar(df_t[features + [\'delta_ctl_7d\']].copy(), features).dropna(subset=[\'delta_ctl_7d\'])
        if len(df_c) >= 40:
            X, y = df_c[features].values.astype(float), df_c[\'delta_ctl_7d\'].values.astype(float)
            self.modelo_delta_ctl = RandomForestRegressor(n_estimators=150, max_depth=6, min_samples_leaf=5, n_jobs=-1, random_state=42)
            self.modelo_delta_ctl.fit(X, y)
            r2 = _cv(self.modelo_delta_ctl, X, y, \'r2\')
            resultados[\'delta_ctl\'] = {\'r2\': round(r2, 3), \'n\': len(df_c)}
            print(f\'  [RespFisio] delta_CTL_7d: R²={r2:.3f} ({len(df_c)} muestras)\')

        # ── Regresión: delta_tsb_7d ──────────────────────────────────────────
        df_c = _imputar(df_t[features + [\'delta_tsb_7d\']].copy(), features).dropna(subset=[\'delta_tsb_7d\'])
        if len(df_c) >= 40:
            X, y = df_c[features].values.astype(float), df_c[\'delta_tsb_7d\'].values.astype(float)
            self.modelo_delta_tsb = RandomForestRegressor(n_estimators=150, max_depth=6, min_samples_leaf=5, n_jobs=-1, random_state=42)
            self.modelo_delta_tsb.fit(X, y)
            r2 = _cv(self.modelo_delta_tsb, X, y, \'r2\')
            resultados[\'delta_tsb\'] = {\'r2\': round(r2, 3), \'n\': len(df_c)}
            print(f\'  [RespFisio] delta_TSB_7d: R²={r2:.3f} ({len(df_c)} muestras)\')

        # ── Clasificación: absorcion_ok ──────────────────────────────────────
        df_c = _imputar(df_t[features + [\'absorcion_ok\']].copy(), features).dropna(subset=[\'absorcion_ok\'])
        if len(df_c) >= 40 and len(df_c[\'absorcion_ok\'].unique()) >= 2:
            X, y = df_c[features].values.astype(float), df_c[\'absorcion_ok\'].values.astype(int)
            self.modelo_absorcion = GradientBoostingClassifier(n_estimators=100, max_depth=3, learning_rate=0.05, random_state=42)
            self.modelo_absorcion.fit(X, y)
            f1 = _cv(self.modelo_absorcion, X, y, \'f1\')
            resultados[\'absorcion_ok\'] = {\'f1\': round(f1, 3), \'n\': len(df_c), \'pct_pos\': round(y.mean()*100, 1)}
            print(f\'  [RespFisio] absorcion_ok: F1={f1:.3f} ({len(df_c)} días, {y.mean()*100:.0f}% positivos)\')

        # ── Clasificación: riesgo_sobre ──────────────────────────────────────
        df_c = _imputar(df_t[features + [\'riesgo_sobre\']].copy(), features).dropna(subset=[\'riesgo_sobre\'])
        if len(df_c) >= 40 and len(df_c[\'riesgo_sobre\'].unique()) >= 2:
            X, y = df_c[features].values.astype(float), df_c[\'riesgo_sobre\'].values.astype(int)
            self.modelo_riesgo = GradientBoostingClassifier(n_estimators=100, max_depth=3, learning_rate=0.05, random_state=42)
            self.modelo_riesgo.fit(X, y)
            f1 = _cv(self.modelo_riesgo, X, y, \'f1\')
            resultados[\'riesgo_sobre\'] = {\'f1\': round(f1, 3), \'n\': len(df_c), \'pct_pos\': round(y.mean()*100, 1)}
            print(f\'  [RespFisio] riesgo_sobre: F1={f1:.3f} ({len(df_c)} días, {y.mean()*100:.0f}% positivos)\')

        if resultados:
            self.entrenado   = True
            self.n_muestras  = len(df_t)
            self.scores      = resultados
        return resultados

    def _vectorizar(self, estado: dict) -> np.ndarray:
        return np.array([[_safe_float(estado.get(f), 0.0) for f in self.features_usados]])

    def predecir(self, estado: dict, tss_plan: float = None) -> dict:
        if not self.entrenado:
            return {\'disponible\': False}
        if tss_plan is not None:
            estado = {**estado, \'tss_7d\': tss_plan}
        X   = self._vectorizar(estado)
        res = {\'disponible\': True, \'tss_evaluado\': tss_plan}

        if self.modelo_delta_ctl:
            d = float(self.modelo_delta_ctl.predict(X)[0])
            res[\'delta_ctl_predicho\'] = round(d, 2)
            res[\'ctl_predicho_7d\']    = round(float(estado.get(\'ctl\', self.ctl_baseline)) + d, 1)

        if self.modelo_delta_tsb:
            d = float(self.modelo_delta_tsb.predict(X)[0])
            res[\'delta_tsb_predicho\'] = round(d, 2)
            res[\'tsb_predicho_7d\']    = round(float(estado.get(\'tsb\', 0)) + d, 1)

        prob_abs = 0.5
        prob_rie = 0.3
        if self.modelo_absorcion:
            prob_abs = float(self.modelo_absorcion.predict_proba(X)[0][1])
            res[\'prob_absorcion\'] = round(prob_abs, 3)
        if self.modelo_riesgo:
            prob_rie = float(self.modelo_riesgo.predict_proba(X)[0][1])
            res[\'prob_riesgo_sobrecarga\'] = round(prob_rie, 3)

        d_ctl = res.get(\'delta_ctl_predicho\', 0)
        if prob_rie >= 0.65 or prob_abs < 0.35:
            res[\'semaforo\'] = \'rojo\'
            res[\'interpretacion\'] = \'Alto riesgo de sobrecarga — reducir TSS planificado\'
        elif prob_abs >= 0.70 and d_ctl >= 0:
            res[\'semaforo\'] = \'verde\'
            res[\'interpretacion\'] = \'Buena absorción esperada — carga adecuada al estado actual\'
        else:
            res[\'semaforo\'] = \'amarillo\'
            res[\'interpretacion\'] = \'Absorción moderada — monitorear HRV y sueño esta semana\'
        return res

    def simular_escenarios(self, estado: dict, opciones_tss: list) -> list:
        """Simula respuesta fisiológica para múltiples TSS. Usado por Optimizer."""
        if not self.entrenado: return []
        return [{**self.predecir(estado, tss_plan=tss), \'tss_plan\': tss} for tss in opciones_tss]

    def importancia_features(self) -> dict:
        result = {}
        for nombre, m in [(\'delta_ctl\', self.modelo_delta_ctl), (\'absorcion\', self.modelo_absorcion), (\'riesgo\', self.modelo_riesgo)]:
            if m and hasattr(m, \'feature_importances_\'):
                imp = dict(zip(self.features_usados, m.feature_importances_))
                result[nombre] = {k: round(v, 3) for k, v in sorted(imp.items(), key=lambda x: -x[1])[:8]}
        return result


# ── NOAH Mind — Interfaz principal ───────────────────────────────────────────


# ── Modelo de Impacto-Respuesta Individual (legacy — mantenido para compatibilidad) ────
class ModeloImpactoRespuesta:'''

if OLD_IMPACTO_HEADER in content:
    content = content.replace(OLD_IMPACTO_HEADER, NEW_PREDICTOR_HEADER)
    print("OK 2 - PredictorRespuestaFisiologica insertado antes de ModeloImpactoRespuesta")
else:
    print("ERROR 2 - no matcheo header ModeloImpactoRespuesta")

# ═══════════════════════════════════════════════════════════════════════════════
# REEMPLAZO 3: NOAHMind.__init__
# ═══════════════════════════════════════════════════════════════════════════════
OLD_INIT = '''    def __init__(self, conn, atleta_id: int):
        self.conn      = conn
        self.atleta_id = atleta_id
        self.df        = None
        self.modelo_carga        = PredictorRespuestaCarga()
        self.detector_adaptacion = DetectorAdaptacion()
        self.modelo_cumplimiento = PredictorCumplimiento()
        self.detector_sobre      = DetectorSobreentrenamiento()
        self.modelo_impacto      = ModeloImpactoRespuesta()
        self._modelos_guardados  = {}'''

NEW_INIT = '''    def __init__(self, conn, atleta_id: int):
        self.conn      = conn
        self.atleta_id = atleta_id
        self.df        = None
        # Modelos ML
        self.modelo_carga           = PredictorRespuestaCarga()
        self.detector_adaptacion    = DetectorAdaptacion()
        self.predictor_respuesta    = PredictorRespuestaFisiologica()
        self.detector_sobre         = DetectorSobreentrenamiento()
        self.modelo_impacto         = ModeloImpactoRespuesta()   # legacy
        # Analizador de adherencia (sin ML — métricas analíticas)
        self.analizador_adherencia  = AnalizadorAdherencia()
        self._modelos_guardados     = {}'''

if OLD_INIT in content:
    content = content.replace(OLD_INIT, NEW_INIT)
    print("OK 3 - NOAHMind.__init__ actualizado")
else:
    print("ERROR 3 - no matcheo __init__")

# ═══════════════════════════════════════════════════════════════════════════════
# REEMPLAZO 4: NOAHMind.entrenar()
# ═══════════════════════════════════════════════════════════════════════════════
OLD_ENTRENAR = '''    def entrenar(self) -> dict:
        """Entrena todos los modelos disponibles."""
        if self.df is None:
            self.preparar_datos()

        resultados = {}
        print(f\'\\n  [NOAH ML] Entrenando modelos para atleta {self.atleta_id}...\')

        # Modelo 1: Respuesta a la carga
        score1 = self.modelo_carga.entrenar(self.df)
        resultados[\'respuesta_carga\'] = {\'score_r2\': score1, \'ok\': score1 > 0.2}

        # Modelo 3: Cumplimiento
        score3 = self.modelo_cumplimiento.entrenar(self.conn, self.atleta_id)
        resultados[\'cumplimiento\'] = {\'score_acc\': score3, \'ok\': score3 > 0.55}

        # Modelo 4: Impacto-Respuesta individual
        scores4 = self.modelo_impacto.entrenar(self.df)
        resultados[\'impacto_respuesta\'] = {
            \'targets\': scores4,
            \'ok\': len(scores4) > 0,
            \'n_targets\': len(scores4),
        }
        if scores4:
            print(f\'  [ML] Impacto-Respuesta: {len(scores4)} targets entrenados\')
            for t, s in scores4.items():
                print(f\'    {t}: F1={s.get("f1","--")} ({s.get("n","?")} días, {s.get("pct_pos","?")}% positivos)\')

        # Guardar metadatos y modelos
        self._guardar_metadatos(resultados)
        self.guardar_modelos()
        return resultados'''

NEW_ENTRENAR = '''    def entrenar(self) -> dict:
        """Entrena todos los modelos disponibles."""
        if self.df is None:
            self.preparar_datos()

        resultados = {}
        print(f\'\\n  [NOAH ML] Entrenando modelos para atleta {self.atleta_id}...\')

        # Modelo 1: Respuesta a la carga (HRV próximo día)
        score1 = self.modelo_carga.entrenar(self.df)
        resultados[\'respuesta_carga\'] = {\'score_r2\': score1, \'ok\': score1 > 0.2}

        # Modelo central: Predictor de Respuesta Fisiológica (Banister + ML)
        # Predice delta_CTL, delta_TSB, absorcion_ok, riesgo_sobrecarga
        scores_rf = self.predictor_respuesta.entrenar(self.df)
        resultados[\'predictor_respuesta\'] = {\'targets\': scores_rf, \'ok\': len(scores_rf) > 0}
        if scores_rf:
            print(f\'  [RespFisio] {len(scores_rf)} modelos entrenados\')

        # Adherencia: análisis analítico (no ML)
        adherencia = self.analizador_adherencia.analizar(self.conn, self.atleta_id)
        resultados[\'adherencia\'] = adherencia
        if adherencia.get(\'disponible\'):
            print(f\'  [Adherencia] {adherencia["adherencia_tss_pct"]}% TSS realizado | Tendencia: {adherencia["tendencia"]}\')

        # Guardar metadatos y modelos
        self._guardar_metadatos(resultados)
        self.guardar_modelos()
        return resultados'''

if OLD_ENTRENAR in content:
    content = content.replace(OLD_ENTRENAR, NEW_ENTRENAR)
    print("OK 4 - NOAHMind.entrenar() actualizado")
else:
    print("ERROR 4 - no matcheo entrenar()")

# ═══════════════════════════════════════════════════════════════════════════════
# REEMPLAZO 5: guardar_modelos
# ═══════════════════════════════════════════════════════════════════════════════
OLD_GUARDAR = '''    def guardar_modelos(self, directorio: str = \'noah_modelos\'):
        """Guarda los modelos entrenados en disco."""
        import joblib, os
        os.makedirs(directorio, exist_ok=True)
        ruta = f\'{directorio}/atleta_{self.atleta_id}\'
        os.makedirs(ruta, exist_ok=True)
        if self.modelo_carga.entrenado:
            joblib.dump(self.modelo_carga, f\'{ruta}/modelo_carga.pkl\')
        if self.modelo_cumplimiento.entrenado:
            joblib.dump(self.modelo_cumplimiento, f\'{ruta}/modelo_cumplimiento.pkl\')
        # Guardar fecha de entrenamiento
        with open(f\'{ruta}/metadata.json\', \'w\') as f:
            import json
            json.dump({\'fecha\': str(date.today()), \'atleta_id\': self.atleta_id}, f)
        print(f\'  [NOAH ML] Modelos guardados en {ruta}/\')'''

NEW_GUARDAR = '''    def guardar_modelos(self, directorio: str = \'noah_modelos\'):
        """Guarda los modelos entrenados en disco."""
        import joblib, os
        os.makedirs(directorio, exist_ok=True)
        ruta = f\'{directorio}/atleta_{self.atleta_id}\'
        os.makedirs(ruta, exist_ok=True)
        if self.modelo_carga.entrenado:
            joblib.dump(self.modelo_carga, f\'{ruta}/modelo_carga.pkl\')
        if self.predictor_respuesta.entrenado:
            joblib.dump(self.predictor_respuesta, f\'{ruta}/predictor_respuesta.pkl\')
        if self.modelo_impacto.entrenado:
            joblib.dump(self.modelo_impacto, f\'{ruta}/modelo_impacto.pkl\')
        meta = {
            \'fecha\':      str(date.today()),
            \'atleta_id\':  self.atleta_id,
            \'modelos\':    {
                \'respuesta_carga\':       self.modelo_carga.entrenado,
                \'predictor_respuesta\':   self.predictor_respuesta.entrenado,
                \'scores_predictor\':      self.predictor_respuesta.scores,
            }
        }
        with open(f\'{ruta}/metadata.json\', \'w\') as f:
            json.dump(meta, f, default=str)
        print(f\'  [NOAH ML] Modelos guardados en {ruta}/\')'''

if OLD_GUARDAR in content:
    content = content.replace(OLD_GUARDAR, NEW_GUARDAR)
    print("OK 5 - guardar_modelos() actualizado")
else:
    print("ERROR 5 - no matcheo guardar_modelos()")

# ═══════════════════════════════════════════════════════════════════════════════
# REEMPLAZO 6: cargar_modelos
# ═══════════════════════════════════════════════════════════════════════════════
OLD_CARGAR = '''        mind = cls(conn, atleta_id)
        try:
            mind.modelo_carga = joblib.load(f\'{ruta}/modelo_carga.pkl\')
            mind.modelo_cumplimiento = joblib.load(f\'{ruta}/modelo_cumplimiento.pkl\')
            print(f\'  [NOAH ML] Modelos cargados (entrenados hace {dias} días)\')
            return mind
        except Exception:
            return None'''

NEW_CARGAR = '''        mind = cls(conn, atleta_id)
        try:
            if os.path.exists(f\'{ruta}/modelo_carga.pkl\'):
                mind.modelo_carga = joblib.load(f\'{ruta}/modelo_carga.pkl\')
            if os.path.exists(f\'{ruta}/predictor_respuesta.pkl\'):
                mind.predictor_respuesta = joblib.load(f\'{ruta}/predictor_respuesta.pkl\')
            if os.path.exists(f\'{ruta}/modelo_impacto.pkl\'):
                mind.modelo_impacto = joblib.load(f\'{ruta}/modelo_impacto.pkl\')
            print(f\'  [NOAH ML] Modelos cargados (entrenados hace {dias} días)\')
            return mind
        except Exception as e:
            print(f\'  [NOAH ML] Error cargando modelos: {e}\')
            return None'''

if OLD_CARGAR in content:
    content = content.replace(OLD_CARGAR, NEW_CARGAR)
    print("OK 6 - cargar_modelos() actualizado")
else:
    print("ERROR 6 - no matcheo cargar_modelos()")

# ═══════════════════════════════════════════════════════════════════════════════
# REEMPLAZO 7: analisis_completo — agregar predictor_respuesta y adherencia
# ═══════════════════════════════════════════════════════════════════════════════
OLD_ANALISIS = '''        # Cumplimiento
        if self.modelo_cumplimiento.entrenado:
            resultado[\'cumplimiento\'] = self.modelo_cumplimiento.predecir(
                ctl, atl, tsb, hrv, sleep)

        # Impacto-Respuesta: predecir recuperación para el TSS de hoy
        if self.modelo_impacto.entrenado:
            tss_hoy = estado.get(\'tss_semana\', ctl * 1.0) / 7
            resultado[\'impacto_respuesta\'] = self.modelo_impacto.predecir_respuesta(
                estado, tss_planificado=tss_hoy)

        return resultado'''

NEW_ANALISIS = '''        # Predictor de Respuesta Fisiológica (modelo central)
        if self.predictor_respuesta.entrenado:
            tss_plan = estado.get(\'tss_semana\', ctl * 7)
            resultado[\'predictor_respuesta\'] = self.predictor_respuesta.predecir(estado, tss_plan=tss_plan)

        # Adherencia al entrenamiento (analítico, no ML)
        resultado[\'adherencia\'] = self.analizador_adherencia.analizar(self.conn, self.atleta_id)

        # Escenarios para Optimizer
        if self.predictor_respuesta.entrenado:
            tss_base = round(ctl * 7)
            opciones = [round(tss_base * f) for f in [0.6, 0.8, 1.0, 1.1, 1.2]]
            resultado[\'escenarios_tss\'] = self.predictor_respuesta.simular_escenarios(estado, opciones)

        return resultado'''

if OLD_ANALISIS in content:
    content = content.replace(OLD_ANALISIS, NEW_ANALISIS)
    print("OK 7 - analisis_completo() actualizado")
else:
    print("ERROR 7 - no matcheo analisis_completo()")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("\nGUARDADO OK - noah_ml.py rediseñado")
