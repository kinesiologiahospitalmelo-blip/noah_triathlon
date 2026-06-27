"""
noah_optimizer.py — Proyecto NOAH
=====================================
Optimizador de prescripción basado en clustering de semanas
y predicción de respuesta individual.

TRES MODELOS:

Modelo 1 — Perfil del atleta (corre al inicio + mensual)
  Clustering no supervisado de semanas de entrenamiento.
  Identifica semanas "óptimas", "sobrecargadas", "desentrenamiento", etc.
  Extrae el patrón de entrenamiento que produjo mejor adaptación.

Modelo 2 — Predicción de respuesta (corre al prescribir)
  Dado el estado actual + receta candidata, predice:
  - delta_CTL esperado en 4 semanas
  - probabilidad de que HANNA LIFE se mantenga > umbral
  - probabilidad de completar la semana

Modelo 3 — Selector de receta (integrado con patrones_sesion)
  Usa los modelos 1 y 2 para elegir el tipo de semana óptimo.
  Tipo A: semana de volumen (más Z1/Z2, sesiones largas)
  Tipo B: semana de calidad (más Z4, series fraccionadas)
  Tipo C: semana mixta
  Tipo D: recuperación

REFERENCIAS:
  Banister 1975, Seiler 2010, Plews 2013,
  Issurin 2010 (bloques de entrenamiento)
"""

from __future__ import annotations
import psycopg2
import json
import numpy as np
import pandas as pd
from datetime import date, timedelta
from typing import Optional

try:
    from sklearn.preprocessing import StandardScaler
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA
    from sklearn.impute import SimpleImputer
    SKLEARN_OK = True
except ImportError:
    SKLEARN_OK = False


# ── Etiquetas de cluster ──────────────────────────────────────────────────────
def _etiquetar_semana(centroide: dict, df_cluster: pd.DataFrame = None) -> dict:
    """
    Etiqueta un cluster basándose en los features más discriminantes.
    La señal principal es delta_ctl_sig (adaptación real) + carga + autonomía.
    Umbrales calibrados empíricamente desde los rangos reales de los datos.
    """
    # Features clave
    delta_sig   = centroide.get('delta_ctl_sig')   # señal principal de adaptación
    delta_ctl   = centroide.get('delta_ctl', 0) or 0
    ramp        = centroide.get('ramp_rate', 0) or 0
    hrv_ratio   = centroide.get('hrv_rmssd_ratio', 1.0) or 1.0
    slope_hrv   = centroide.get('slope_hrv_7d', 0) or 0
    hanna       = centroide.get('hanna_life_media', 60) or 60
    pct_z12     = centroide.get('pct_z12', 70) or 70
    pct_z34     = centroide.get('pct_z34', 20) or 20
    pct_z56     = centroide.get('pct_z56', 10) or 10
    n_cal       = centroide.get('n_sesiones_calidad', 0) or 0
    tss_total   = centroide.get('tss_total_sem', 0) or 0
    fc_ratio    = centroide.get('fc_nocturna_ratio', 1.0) or 1.0
    hrv_sig     = centroide.get('hrv_ratio_sig', 1.0) or 1.0
    min_cont    = centroide.get('min_continuo_z12_max', 0) or 0
    ctl_inicio  = centroide.get('ctl_inicio', 30) or 30

    # ── Score autonómico ──────────────────────────────────────────────────────
    # HRVr típico en atletas: 0.75-1.05 (raramente supera 1.0 sostenido)
    # Referencia: HRVr=0.85 = estado normal para muchos atletas en carga
    # 0 = muy bajo, 5 = normal (0.85), 10 = muy bueno (>1.0)
    if hrv_ratio is not None and hrv_ratio > 0:
        # Normalizar: 0.75→0, 0.85→5, 1.0→8, 1.1→10
        score_auto = max(0, min(10, (hrv_ratio - 0.70) / 0.04))
    else:
        score_auto = 5.0  # sin dato = neutral

    # HANNA ajuste: rango típico 40-80
    if hanna:
        score_auto += (hanna - 55) / 8   # 55=neutral, cada 8pts mueve 1 punto
    if slope_hrv > 0.15:  score_auto += 0.5   # HRV mejorando
    elif slope_hrv < -0.3: score_auto -= 0.8  # HRV cayendo
    if fc_ratio and fc_ratio < 1.03:  score_auto += 0.5
    elif fc_ratio and fc_ratio > 1.08: score_auto -= 0.8
    score_auto = max(0, min(10, score_auto))

    # ── Score de carga ────────────────────────────────────────────────────────
    # ramp en % CTL/semana: típico -5% a +15%
    # score_carga 0=muy baja, 5=normal, 10=muy alta
    if ramp is not None:
        score_carga = max(0, min(10, 5.0 + ramp * 0.35))
    else:
        score_carga = 5.0
    score_carga += (pct_z34 - 20) / 10   # más umbral = algo más de carga
    score_carga += (pct_z56 - 10) / 8
    score_carga = max(0, min(10, score_carga))

    # ── Score de adaptación ───────────────────────────────────────────────────
    # delta_ctl_sig típico: -3 a +6 CTL/semana
    score_adapt = 5.0
    if delta_sig is not None:
        score_adapt += delta_sig * 0.8   # +6 CTL → +4.8 puntos
    if hrv_sig and hrv_sig > 1.02: score_adapt += 0.8
    elif hrv_sig and hrv_sig < 0.96: score_adapt -= 0.8
    score_adapt = max(0, min(10, score_adapt))

    # ── Clasificar ───────────────────────────────────────────────────────────
    # Usar delta_sig como señal primaria (objetiva)
    adapto_bien = delta_sig is not None and delta_sig >= 1.5
    adapto_mal  = delta_sig is not None and delta_sig <= 0.3

    # Autonomía: referencia ajustada a rangos reales
    auto_ok   = score_auto >= 4.5
    auto_bajo = score_auto < 3.5

    # Carga: ramp positivo y significativo
    carga_alta = score_carga >= 6.0
    carga_baja = score_carga <= 3.5

    # Clasificación por combinación de señales
    if adapto_bien and auto_ok and carga_alta:
        nombre, tipo, color, desc, receta = (
            'Semana Óptima', 'optima', '#10B981',
            'Carga alta + buena autonomía + máxima adaptación. El patrón ideal.',
            'volumen+calidad'
        )
    elif adapto_bien and auto_ok and not carga_alta:
        if pct_z12 > 70 or min_cont > 45:
            nombre, tipo, color, desc, receta = (
                'Acumulación Productiva', 'acumulacion', '#3B82F6',
                'Volumen aeróbico Z1/Z2 con buena adaptación. Base sólida.',
                'volumen'
            )
        else:
            nombre, tipo, color, desc, receta = (
                'Calidad Controlada', 'calidad', '#F59E0B',
                'Trabajo de calidad con buena respuesta adaptativa.',
                'calidad'
            )
    elif adapto_bien and auto_bajo:
        nombre, tipo, color, desc, receta = (
            'Carga Productiva con Estrés', 'productiva_estres', '#84CC16',
            'Adaptación positiva pero sistema autonómico bajo. Vigilar.',
            'mixta'
        )
    elif adapto_mal and carga_alta and auto_bajo:
        nombre, tipo, color, desc, receta = (
            'Sobreentrenamiento', 'sobre', '#EF4444',
            'Carga alta + autonomía comprometida + sin adaptación. Reducir carga.',
            'recuperacion'
        )
    elif adapto_mal and carga_alta and auto_ok:
        nombre, tipo, color, desc, receta = (
            'Carga Excesiva', 'excesiva', '#F97316',
            'Carga alta sin adaptación. El volumen supera la capacidad de absorción.',
            'reducir_carga'
        )
    elif adapto_mal and carga_baja:
        nombre, tipo, color, desc, receta = (
            'Subentrenamiento', 'sub', '#8B5CF6',
            'Carga insuficiente. No hay estímulo suficiente para adaptación.',
            'aumentar_carga'
        )
    elif not adapto_bien and not adapto_mal and auto_bajo:
        nombre, tipo, color, desc, receta = (
            'Fatiga No Deportiva', 'fatiga_extra', '#F97316',
            'Sistema autonómico bajo sin correlación con carga. Causa externa.',
            'recuperacion_activa'
        )
    elif adapto_mal is False and auto_ok and not carga_alta:
        nombre, tipo, color, desc, receta = (
            'Mantenimiento', 'mantener', '#94A3B8',
            'Carga moderada. CTL estable sin crecimiento ni caída.',
            'mantener'
        )
    else:
        nombre, tipo, color, desc, receta = (
            'Estado Mixto', 'mixto', '#6B7280',
            'Señales mixtas. Revisar individualmente.',
            'mixta'
        )

    return {
        'nombre':     nombre,
        'tipo':       tipo,
        'color':      color,
        'desc':       desc,
        'receta':     receta,
        'score_auto': round(score_auto, 1),
        'score_carga':round(score_carga, 1),
        'score_adapt':round(score_adapt, 1),
    }


# ── Modelo 1 — Clustering de semanas ─────────────────────────────────────────
class ClusterizadorSemanas:
    """
    Clustering no supervisado de semanas de entrenamiento.
    Identifica patrones históricos y los caracteriza.
    """

    # Features usados para clustering (los más informativos)
    FEATURES = [
        'hrv_rmssd_ratio', 'slope_hrv_7d', 'slope_hrv_28d',
        'ratio_hrv_carga', 'fc_nocturna_ratio', 'slope_fc_7d',
        'sleep_h_media', 'sleep_calidad', 'hanna_life_media',
        'ctl_inicio', 'delta_ctl', 'ramp_rate',
        'pct_z12', 'pct_z34', 'pct_z56',
        'min_continuo_z12_max', 'n_sesiones_calidad',
        'n_sesiones_continuo_umbral', 'n_sesiones_fraccionado_umbral',
        'delta_ctl_sig', 'hrv_ratio_sig',
    ]

    def __init__(self, n_clusters: int = 6):
        self.n_clusters = n_clusters
        self.scaler     = None
        self.imputer    = None
        self.kmeans     = None
        self.pca        = None
        self.clusters   = []
        self.entrenado  = False

    def entrenar(self, df: pd.DataFrame) -> dict:
        """Entrena el clustering sobre el dataset de semanas."""
        if not SKLEARN_OK:
            return {'error': 'sklearn no instalado'}
        if len(df) < self.n_clusters * 3:
            return {'error': f'Datos insuficientes ({len(df)} semanas, necesito {self.n_clusters*3}+)'}

        # Seleccionar features disponibles
        feats_disp = [f for f in self.FEATURES if f in df.columns]
        X_raw = df[feats_disp].copy()

        # Imputar NaN con mediana
        self.imputer = SimpleImputer(strategy='median')
        X_imp = self.imputer.fit_transform(X_raw)

        # Escalar
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X_imp)

        # Ajustar n_clusters al tamaño del dataset
        n_k = min(self.n_clusters, len(df) // 4)
        n_k = max(3, n_k)

        # KMeans
        self.kmeans = KMeans(n_clusters=n_k, random_state=42, n_init=15)
        labels = self.kmeans.fit_predict(X_scaled)

        # PCA 2D
        self.pca = PCA(n_components=2, random_state=42)
        X_2d = self.pca.fit_transform(X_scaled)
        var_explicada = float(sum(self.pca.explained_variance_ratio_) * 100)

        # Construir clusters
        centroides_orig = self.scaler.inverse_transform(self.kmeans.cluster_centers_)
        self.clusters = []

        for k in range(n_k):
            mask = labels == k
            if mask.sum() == 0:
                continue

            cent_dict = dict(zip(feats_disp, centroides_orig[k]))
            etiqueta  = _etiquetar_semana(cent_dict)

            # Semanas en este cluster
            semanas_k = df[mask]['fecha_lunes'].tolist() if 'fecha_lunes' in df else []

            # HRV y delta_ctl_sig promedio real del cluster
            delta_sig_real = float(df[mask]['delta_ctl_sig'].dropna().mean()) if 'delta_ctl_sig' in df else None
            hrv_media_real = float(df[mask]['hrv_rmssd_media'].dropna().mean()) if 'hrv_rmssd_media' in df else None
            hanna_real     = float(df[mask]['hanna_life_media'].dropna().mean()) if 'hanna_life_media' in df else None

            # PCA centroide
            cent_2d = self.pca.transform(self.kmeans.cluster_centers_[k:k+1])[0]

            self.clusters.append({
                'id':            k,
                'nombre':        etiqueta['nombre'],
                'tipo':          etiqueta['tipo'],
                'color':         etiqueta['color'],
                'desc':          etiqueta['desc'],
                'receta':        etiqueta['receta'],
                'score_auto':    etiqueta['score_auto'],
                'score_carga':   etiqueta['score_carga'],
                'score_adapt':   etiqueta.get('score_adapt', 0),
                'n_semanas':     int(mask.sum()),
                'pct_semanas':   round(mask.sum() / len(labels) * 100, 1),
                'delta_ctl_sig': round(delta_sig_real, 2) if delta_sig_real is not None else None,
                'hrv_media':     round(hrv_media_real, 1) if hrv_media_real else None,
                'hanna_media':   round(hanna_real, 1) if hanna_real else None,
                'centroide':     {k: round(v, 3) for k, v in cent_dict.items()},
                'pca_x':         round(float(cent_2d[0]), 3),
                'pca_y':         round(float(cent_2d[1]), 3),
                'semanas':       semanas_k[-5:],  # últimas 5 semanas del cluster
            })

        # Ordenar por delta_ctl_sig descendente (mejores primeros)
        self.clusters.sort(
            key=lambda c: c['delta_ctl_sig'] if c['delta_ctl_sig'] is not None else -99,
            reverse=True
        )

        # Historia para el frontend
        historia = [
            {
                'fecha':      df.iloc[i]['fecha_lunes'] if 'fecha_lunes' in df else '',
                'cluster_id': int(labels[i]),
                'pca_x':      round(float(X_2d[i, 0]), 3),
                'pca_y':      round(float(X_2d[i, 1]), 3),
                'delta_ctl':  float(df.iloc[i]['delta_ctl']) if pd.notna(df.iloc[i].get('delta_ctl')) else None,
            }
            for i in range(len(labels))
        ]

        self.entrenado = True
        self._labels   = labels
        self._df       = df
        self._X_scaled = X_scaled
        self._feats    = feats_disp

        return {
            'clusters':          self.clusters,
            'n_clusters':        len(self.clusters),
            'n_semanas':         len(labels),
            'var_explicada_pca': round(var_explicada, 1),
            'historia':          historia,
            'cluster_optimo':    self.clusters[0] if self.clusters else None,
        }

    def predecir_cluster(self, vector: dict) -> Optional[dict]:
        """Predice a qué cluster pertenece un vector nuevo (semana actual)."""
        if not self.entrenado or not self.scaler:
            return None
        try:
            import warnings
            # Pasar DataFrame para evitar warning de feature names
            X_df = pd.DataFrame([[vector.get(f, np.nan) for f in self._feats]],
                                  columns=self._feats)
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                X_imp = self.imputer.transform(X_df)
                X_sc  = self.scaler.transform(X_imp)
            label = int(self.kmeans.predict(X_sc)[0])
            pca_2d = self.pca.transform(X_sc)[0]
            cluster = next((c for c in self.clusters if c['id'] == label), None)
            if cluster:
                cluster = {**cluster,
                    'pca_x_hoy': round(float(pca_2d[0]), 3),
                    'pca_y_hoy': round(float(pca_2d[1]), 3),
                }
            return cluster
        except:
            return None


# ── Modelo 2 — Predicción de respuesta ───────────────────────────────────────
def predecir_respuesta_receta(
    estado_actual: dict,
    tipo_receta: str,   # 'volumen' | 'calidad' | 'mixta' | 'recuperacion'
    semanas: int = 4,
    k_params: Optional[dict] = None,
) -> dict:
    """
    Predice el delta_CTL y estado autonómico esperado si se aplica
    un tipo de receta durante N semanas.

    Usa el modelo de Banister con K1/K2 individuales si están disponibles.
    """
    ctl = estado_actual.get('ctl', 30)
    atl = estado_actual.get('atl', 30)
    hrv_ratio = estado_actual.get('hrv_rmssd_ratio', 1.0) or 1.0
    hanna = estado_actual.get('hanna_life', 60) or 60

    # K1/K2 individuales o estándar
    tau_ctl = k_params.get('tau_ctl', 42) if k_params else 42
    tau_atl = k_params.get('tau_atl', 7)  if k_params else 7
    k1 = 1 / tau_ctl
    k2 = 1 / tau_atl
    d1 = 1 - k1
    d2 = 1 - k2

    # TSS diario según tipo de receta
    # Para MANTENER CTL: TSS_diario = CTL (ecuación de Banister)
    # Para SUBIR CTL: TSS_diario = CTL + TAU_CTL * ramp_deseado
    # Ramp objetivo conservador: +3 CTL/semana → +3/7 por día = 0.43/día
    # TSS para +3/semana: CTL + 42 * (3/7) = CTL + 18
    tau = k_params.get('tau_ctl', 42) if k_params else 42
    ramp_obj_dia = 3.0 / 7  # +3 CTL/semana objetivo conservador
    tss_build = ctl + tau * ramp_obj_dia

    tss_recetas = {
        'volumen':        tss_build * 1.0,   # build con Z1/Z2
        'calidad':        tss_build * 0.95,  # build con más Z4, algo menos TSS total
        'mixta':          tss_build * 0.97,
        'recuperacion':   ctl * 0.50,        # recuperación: 50% CTL
        'recuperacion_activa': ctl * 0.65,
        'aumentar_carga': tss_build * 1.10,  # build más agresivo
        'reducir_carga':  ctl * 0.80,
        'mantener':       ctl * 1.0,         # exactamente el mínimo para mantener
    }
    tss_diario = tss_recetas.get(tipo_receta, tss_build)

    # Simular N semanas
    ctl_sim, atl_sim = float(ctl), float(atl)
    trayectoria = []

    for d in range(semanas * 7):
        sem_en_meso = (d // 7) % 4
        # Ondulación mesociclo 3:1
        if sem_en_meso == 3:
            tss_d = tss_diario * 0.55  # descarga
        else:
            mult = 0.90 + sem_en_meso * 0.10
            tss_d = tss_diario * mult

        ctl_sim = ctl_sim * d1 + tss_d * k1
        atl_sim = atl_sim * d2 + tss_d * k2
        tsb_sim = ctl_sim - atl_sim

        if d % 7 == 6:  # fin de semana
            trayectoria.append({
                'semana': d // 7 + 1,
                'ctl':    round(ctl_sim, 1),
                'atl':    round(atl_sim, 1),
                'tsb':    round(tsb_sim, 1),
            })

    delta_ctl_pred = ctl_sim - ctl
    tsb_final = ctl_sim - atl_sim

    # Predicción de HANNA LIFE (heurística basada en carga)
    if tipo_receta == 'recuperacion':
        hanna_pred = min(85, hanna + 10)
    elif tipo_receta == 'volumen':
        hanna_pred = max(45, hanna - 5)
    elif tipo_receta == 'calidad':
        hanna_pred = max(40, hanna - 8)
    else:
        hanna_pred = hanna

    # Probabilidad de completar la semana (basa en HANNA_LIFE actual)
    prob_completar = min(0.95, max(0.30, hanna / 100 * 0.9 + 0.1))

    return {
        'tipo_receta':    tipo_receta,
        'delta_ctl_pred': round(delta_ctl_pred, 1),
        'ctl_final_pred': round(ctl_sim, 1),
        'tsb_final_pred': round(tsb_final, 1),
        'hanna_pred':     round(hanna_pred, 1),
        'prob_completar': round(prob_completar, 2),
        'trayectoria':    trayectoria,
        'semanas':        semanas,
    }


# ── Modelo 3 — Selector de receta ────────────────────────────────────────────
def seleccionar_receta(
    estado_actual: dict,
    cluster_historico: Optional[dict],
    fase: str = 'A',
    semanas_hasta_carrera: Optional[int] = None,
    k_params: Optional[dict] = None,
) -> dict:
    """
    Selecciona el tipo de receta óptima para la próxima semana.

    Combina:
    - Estado autonómico actual (HANNA LIFE, HRV)
    - Cluster histórico del atleta (qué funcionó)
    - Fase del ciclo (A/T/R/Taper)
    - Urgencia temporal (semanas hasta carrera A)
    """
    hanna     = estado_actual.get('hanna_life', 60) or 60
    tsb       = estado_actual.get('tsb', 0) or 0
    hrv_ratio = estado_actual.get('hrv_rmssd_ratio', 1.0) or 1.0

    # Reglas de prioridad (el orden importa)

    # 1. Si HANNA LIFE muy bajo → siempre recuperación
    if hanna < 35:
        receta = 'recuperacion'
        razon  = 'HANNA LIFE crítico — sistema autonómico comprometido'

    # 2. Taper
    elif fase == 'Taper':
        receta = 'recuperacion'
        razon  = 'Fase Taper — reducción de carga para pico de forma'

    # 3. Si hay carrera en menos de 2 semanas
    elif semanas_hasta_carrera and semanas_hasta_carrera <= 2:
        receta = 'recuperacion'
        razon  = f'Carrera en {semanas_hasta_carrera} semanas — preservar forma'

    # 4. Fase R (Realización) → calidad específica
    elif fase == 'R':
        if hanna >= 55:
            receta = 'calidad'
            razon  = 'Fase R + buena autonomía — trabajo específico de carrera'
        else:
            receta = 'mixta'
            razon  = 'Fase R pero autonomía comprometida — calidad moderada'

    # 5. Fase T (Transformación) → mezcla calidad + algo de volumen
    elif fase == 'T':
        if hanna >= 60 and tsb > -10:
            receta = 'mixta'
            razon  = 'Fase T — umbral + VO2, sin sobrecargar'
        elif hanna < 50:
            receta = 'volumen'
            razon  = 'Fase T pero HANNA bajo — priorizar recuperación con volumen suave'
        else:
            receta = 'calidad'
            razon  = 'Fase T — trabajo de calidad'

    # 6. Fase A (Acumulación) → según perfil histórico real
    elif fase == 'A':
        if cluster_historico:
            receta_hist  = cluster_historico.get('receta', 'volumen')
            tipo_hist    = cluster_historico.get('tipo', '')
            delta_optimo = cluster_historico.get('delta_ctl_sig', 0) or 0
            pct_z12_opt  = cluster_historico.get('centroide', {}).get('pct_z12', 70) or 70
            pct_z34_opt  = cluster_historico.get('centroide', {}).get('pct_z34', 20) or 20

            # Usar el patrón del cluster óptimo como guía
            if tipo_hist in ('optima', 'acumulacion', 'productiva_estres'):
                if pct_z12_opt > 65:
                    receta = 'volumen'
                    razon  = f'Fase A — historial muestra mejor adaptación con volumen Z1/Z2 (ΔCTLnxt={delta_optimo:.1f})'
                elif pct_z34_opt > 25:
                    receta = 'calidad'
                    razon  = f'Fase A — historial muestra mejor adaptación con trabajo umbral (ΔCTLnxt={delta_optimo:.1f})'
                else:
                    receta = 'mixta'
                    razon  = f'Fase A — patrón mixto (ΔCTLnxt={delta_optimo:.1f})'
            elif tipo_hist in ('sobre', 'excesiva'):
                # El atleta tiende a sobrecargar — ser más conservador
                receta = 'volumen' if hanna >= 50 else 'recuperacion_activa'
                razon  = 'Fase A — historial muestra tendencia a sobrecarga, priorizando volumen controlado'
            elif tipo_hist == 'sub':
                receta = 'aumentar_carga'
                razon  = 'Fase A — historial muestra subentrenamiento, aumentar carga gradualmente'
            else:
                receta = 'mixta'
                razon  = f'Fase A — cluster histórico: {cluster_historico["nombre"]}'
        else:
            receta = 'volumen' if hanna >= 55 else 'recuperacion_activa'
            razon  = 'Fase A — sin historial suficiente, receta conservadora'

    else:
        receta = 'mixta'
        razon  = 'Estado indefinido — receta mixta por defecto'

    # Simular las opciones para comparar
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
    }


# ── Guardar y cargar resultado ────────────────────────────────────────────────
def guardar_optimizador(conn, atleta_id: int,
                         resultado: dict) -> bool:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS noah_optimizer (
            atleta_id    INTEGER PRIMARY KEY,
            fecha        TEXT,
            resultado    TEXT,
            FOREIGN KEY (atleta_id) REFERENCES atletas(id)
        )
    """)
    conn.execute("""
        INSERT INTO noah_optimizer (atleta_id, fecha, resultado)
        VALUES (%s,%s,%s)
        ON CONFLICT(atleta_id) DO UPDATE SET
            fecha=excluded.fecha, resultado=excluded.resultado
    """, (atleta_id, str(date.today()), json.dumps(resultado)))
    conn.commit()
    return True


def cargar_optimizador(conn, atleta_id: int) -> Optional[dict]:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS noah_optimizer (
            atleta_id INTEGER PRIMARY KEY, fecha TEXT, resultado TEXT)
    """)
    row = conn.execute(
        'SELECT resultado, fecha FROM noah_optimizer WHERE atleta_id=%s',
        (atleta_id,)
    ).fetchone()
    if not row:
        return None
    try:
        r = json.loads(row[0])
        r['fecha_calculo'] = row[1]
        dias = (date.today() - date.fromisoformat(row[1])).days
        r['necesita_recalculo'] = dias > 30
        return r
    except:
        return None


# ── Función principal ─────────────────────────────────────────────────────────
def analizar_atleta(
    conn,
    atleta_id: int,
    forzar: bool = False,
) -> dict:
    """
    Corre el análisis completo del atleta:
    1. Construye el dataset de semanas
    2. Clusteriza las semanas
    3. Identifica el patrón óptimo histórico
    4. Genera recomendación de receta para la próxima semana

    Retorna el resultado completo para guardar en DB y mostrar en el dashboard.
    """
    # Ver si hay resultado reciente
    if not forzar:
        cached = cargar_optimizador(conn, atleta_id)
        if cached and not cached.get('necesita_recalculo'):
            return cached

    from noah_vector_semanal import construir_dataset_completo, estimar_k1_k2

    print(f'  Analizando atleta {atleta_id}...')

    # 1. Dataset
    df = construir_dataset_completo(conn, atleta_id)
    if df.empty or len(df) < 6:
        return {'error': 'Historial insuficiente (mínimo 6 semanas)', 'atleta_id': atleta_id}

    # 2. K1/K2
    k_params = estimar_k1_k2(conn, atleta_id)
    print(f'  K params: tau_CTL={k_params["tau_ctl"]}d tau_ATL={k_params["tau_atl"]}d')

    # 3. Clustering
    clust = ClusterizadorSemanas(n_clusters=min(6, len(df)//4))
    resultado_clust = clust.entrenar(df)

    if 'error' in resultado_clust:
        return {**resultado_clust, 'atleta_id': atleta_id, 'k_params': k_params}

    # 4. Cluster de la semana actual
    lunes_actual = date.today() - timedelta(days=date.today().weekday())
    from noah_vector_semanal import extraer_vector_semana
    try:
        from noah_baseline import get_baseline
        baseline = get_baseline(conn, atleta_id)
    except:
        baseline = None

    vector_actual = extraer_vector_semana(conn, atleta_id, lunes_actual,
                                           baseline=baseline, k_params=k_params)
    cluster_actual = clust.predecir_cluster(vector_actual) if vector_actual else None

    # 5. Estado actual del atleta
    estado_db = conn.execute("""
        SELECT MAX(ctl) as ctl, MAX(atl) as atl
        FROM sesiones WHERE atleta_id=%s AND fecha = %s
    """, (atleta_id, str(date.today()))).fetchone()

    bio_db = conn.execute("""
        SELECT hanna_life, hrv_rmssd, hrv_estimado_valor
        FROM sleep_hrv WHERE atleta_id=%s ORDER BY fecha DESC LIMIT 1
    """, (atleta_id,)).fetchone()

    hrv_ms = None
    if bio_db:
        hrv_ms = bio_db[1] or bio_db[2]

    hrv_ratio = None
    if hrv_ms and baseline and baseline.get('hrv_media'):
        hrv_ratio = hrv_ms / baseline['hrv_media']

    estado_actual = {
        'ctl':               float(estado_db[0]) if estado_db and estado_db[0] else 30.0,
        'atl':               float(estado_db[1]) if estado_db and estado_db[1] else 30.0,
        'tsb':               (float(estado_db[0]) - float(estado_db[1])) if estado_db and all(estado_db) else 0.0,
        'hanna_life':        float(bio_db[0]) if bio_db and bio_db[0] else 60.0,
        'hrv_ms':            hrv_ms,
        'hrv_rmssd_ratio':   hrv_ratio,
    }

    # Fase actual (desde fases)
    # Semanas hasta carrera A — calcular PRIMERO
    carrera_A = conn.execute("""
        SELECT fecha FROM carreras
        WHERE atleta_id=%s AND prioridad='A' AND estado='pendiente' AND fecha > %s
        ORDER BY fecha ASC LIMIT 1
    """, (atleta_id, str(date.today()))).fetchone()
    sem_hasta_carrera = None
    if carrera_A:
        sem_hasta_carrera = (date.fromisoformat(carrera_A[0]) - date.today()).days // 7

    # Fase actual — desde prescripciones o inferida desde semanas hasta carrera
    fase_actual = 'A'
    try:
        fase_row = conn.execute(
            "SELECT fase FROM prescripciones WHERE atleta_id=%s ORDER BY fecha_generada DESC LIMIT 1",
            (atleta_id,)
        ).fetchone()
        if fase_row and fase_row[0]:
            f = fase_row[0]
            fase_actual = {'F1':'A','F2':'T','F3':'R','TAPER':'Taper'}.get(f, f)
    except:
        pass

    # Inferir desde semanas hasta carrera si la DB tiene fase vieja o indefinida
    if sem_hasta_carrera is not None:
        if sem_hasta_carrera <= 2:
            fase_actual = 'Taper'
        elif sem_hasta_carrera <= 6:
            fase_actual = 'R'
        elif sem_hasta_carrera <= 12:
            fase_actual = 'T'

    # 6. Cluster óptimo histórico (mayor delta_ctl_sig Y que adaptó bien)
    clusters_lista = resultado_clust.get('clusters', [])
    # Buscar el cluster con mejor adaptación Y mayor porcentaje (más representativo)
    cluster_optimo = None
    mejor_score = -999
    for c in clusters_lista:
        d = c.get('delta_ctl_sig') or 0
        pct = c.get('pct_semanas', 0)
        # Score combinado: adapatación × representatividad
        score = d * 0.7 + (pct / 100) * 3
        if d > 0 and score > mejor_score:
            mejor_score = score
            cluster_optimo = c

    if not cluster_optimo and clusters_lista:
        cluster_optimo = clusters_lista[0]  # fallback al primero

    # 7. Seleccionar receta
    receta = seleccionar_receta(
        estado_actual=estado_actual,
        cluster_historico=cluster_optimo,
        fase=fase_actual,
        semanas_hasta_carrera=sem_hasta_carrera,
        k_params=k_params,
    )

    resultado = {
        'atleta_id':          atleta_id,
        'fecha':              str(date.today()),
        'k_params':           k_params,
        'estado_actual':      estado_actual,
        'fase_actual':        fase_actual,
        'sem_hasta_carrera':  sem_hasta_carrera,
        'n_semanas_analizadas': len(df),
        'clustering':         resultado_clust,
        'cluster_actual':     cluster_actual,
        'cluster_optimo':     cluster_optimo,
        'receta':             receta,
    }

    guardar_optimizador(conn, atleta_id, resultado)
    print(f'  ✓ Receta recomendada: {receta["receta_recomendada"]}')
    print(f'  ✓ Razón: {receta["razon"]}')

    return resultado


# ── Script standalone ─────────────────────────────────────────────────────────
if __name__ == '__main__':
    import argparse, sys, os
    import psycopg2.extras
    from pathlib import Path
    from db_compat import ConexionCompat
    sys.path.insert(0, str(Path(__file__).parent))

    ap = argparse.ArgumentParser(description='NOAH Optimizer')
    ap.add_argument('--atleta', type=int, required=True)
    ap.add_argument('--forzar', action='store_true')
    args = ap.parse_args()

    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("Falta la variable de entorno DATABASE_URL (cadena de conexión a Postgres/Supabase)")
        sys.exit(1)
    conn = ConexionCompat(psycopg2.connect(db_url, cursor_factory=psycopg2.extras.DictCursor))

    nombre = conn.execute('SELECT nombre FROM atletas WHERE id=%s', (args.atleta,)).fetchone()
    print(f'\n{"="*60}')
    print(f'  NOAH Optimizer — {nombre[0] if nombre else args.atleta}')
    print(f'{"="*60}')

    resultado = analizar_atleta(conn, args.atleta, forzar=args.forzar)

    if 'error' in resultado:
        print(f'  Error: {resultado["error"]}')
    else:
        print(f'\n  K params: tau_CTL={resultado["k_params"]["tau_ctl"]}d | '
              f'tau_ATL={resultado["k_params"]["tau_atl"]}d | '
              f'confianza={resultado["k_params"]["confianza"]}')
        print(f'  Semanas analizadas: {resultado["n_semanas_analizadas"]}')
        print(f'  Fase actual: {resultado["fase_actual"]}')

        clust = resultado.get('clustering', {})
        print(f'\n  Clusters ({clust.get("n_clusters")} | PCA {clust.get("var_explicada_pca")}%):')
        for c in (clust.get('clusters') or []):
            cent  = c.get('centroide', {})
            hrv_r  = cent.get('hrv_rmssd_ratio')
            hanna_c= cent.get('hanna_life_media')
            ramp_c = cent.get('ramp_rate')
            print(f'    {c["color"][-6:]} {c["nombre"]:30} {c["pct_semanas"]:5.1f}% | '
                  f'auto={c["score_auto"]:.1f} carga={c["score_carga"]:.1f} adapt={c["score_adapt"]:.1f} | '
                  f'ΔCTLnxt={str(c["delta_ctl_sig"] or "--"):>6} | '
                  f'HRVr={"{0:.2f}".format(hrv_r) if hrv_r else "?"} '
                  f'HANNA={"{0:.0f}".format(hanna_c) if hanna_c else "?"} '
                  f'ramp={"{0:.3f}".format(ramp_c) if ramp_c else "?"}')  
        ca = resultado.get('cluster_actual')
        if ca:
            print(f'\n  Semana actual → cluster: {ca["nombre"]}')

        rec = resultado.get('receta', {})
        print(f'\n  Receta recomendada: {rec.get("receta_recomendada")}')
        print(f'  Razón: {rec.get("razon")}')
        sim = rec.get('receta_seleccionada', {})
        if sim:
            print(f'  Predicción 4 semanas: CTL {sim.get("ctl_final_pred")} | '
                  f'ΔCTL {sim.get("delta_ctl_pred")} | '
                  f'prob_completar {sim.get("prob_completar")*100:.0f}%')

    conn.close()
