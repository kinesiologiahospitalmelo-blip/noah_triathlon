"""
noah_clustering.py — Proyecto NOAH
=====================================
Clustering de estados del atleta para el dashboard del coach.

Identifica patrones recurrentes en los biomarcadores + carga
y los agrupa en clusters con nombre y recomendación.

ALGORITMO:
    K-Means sobre features normalizadas del atleta:
    - HRV relativo al baseline personal
    - FC relativo al baseline
    - Sueño relativo al baseline
    - Stress
    - SpO2
    - ATL/CTL ratio
    - TSB

CLUSTERS TÍPICOS:
    El algoritmo aprende los clusters del historial propio del atleta.
    No son fijos — emergen de sus datos.
    Se etiquetan automáticamente según sus características.

USO:
    python noah_clustering.py --atleta 1
    O desde app.py: GET /api/atletas/:id/clustering
"""

from __future__ import annotations
import psycopg2
import json
import numpy as np
import pandas as pd
from datetime import date, timedelta
from typing import Optional
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
import warnings
warnings.filterwarnings('ignore')


# ── Etiquetas automáticas de clusters ────────────────────────────────────────
def _etiquetar_cluster(centroide: dict, rank: int = 0) -> dict:
    """
    Etiqueta un cluster según sus características cuantitativas.
    Usa scores numéricos para diferenciar clusters similares.
    rank = posición del cluster por tamaño (0=mayor)
    """
    hrv_rel   = centroide.get('hrv_rel', 1.0)
    fc_rel    = centroide.get('fc_rel', 1.0)
    sleep_rel = centroide.get('sleep_rel', 1.0)
    stress    = centroide.get('stress_avg', centroide.get('stress', 40))
    spo2      = centroide.get('spo2_avg', centroide.get('spo2', 97))
    atl_ctl   = centroide.get('atl_ctl', 1.0)
    tsb       = centroide.get('tsb', 0)

    # Score autonómico (0-10): más alto = mejor estado
    score_auto = 0
    score_auto += 3.5 * max(0, min(1, (hrv_rel - 0.80) / 0.40))   # HRV (peso mayor)
    score_auto += 2.0 * max(0, min(1, (1.10 - fc_rel) / 0.30))    # FC baja = bueno
    score_auto += 2.0 * max(0, min(1, (sleep_rel - 0.70) / 0.60)) # Sueño
    score_auto += 1.5 * max(0, min(1, (80 - stress) / 60))         # Stress bajo
    score_auto += 1.0 * max(0, min(1, (spo2 - 92) / 8))            # SpO2

    # Score de carga (0-10): más alto = carga más alta/problemática
    score_carga = 0
    if atl_ctl:
        if atl_ctl > 1.3:   score_carga += 4.0
        elif atl_ctl > 1.15: score_carga += 2.5
        elif atl_ctl > 1.0:  score_carga += 1.0
        elif atl_ctl < 0.75: score_carga += 2.0  # desentrenamiento tb es problema
    if tsb < -25:    score_carga += 4.0
    elif tsb < -15:  score_carga += 2.5
    elif tsb < -5:   score_carga += 1.0
    elif tsb > 20:   score_carga += 1.5  # desentrenado

    # Clasificación por combinación de scores
    # Auto: alto≥7, medio 4-7, bajo<4
    # Carga: alta≥5, media 2-5, baja<2

    if score_auto >= 7.0 and score_carga < 2.0:
        return {'nombre':'Forma Óptima','color':'#10B981','icono':'🔋',
                'score_auto':round(score_auto,1),'score_carga':round(score_carga,1),
                'desc':'HRV alto, FC baja, sueño bueno, carga controlada.',
                'accion':'Aprovechar para sesiones de calidad e intensidad.'}

    elif score_auto >= 7.0 and 2.0 <= score_carga < 5.0:
        return {'nombre':'Adaptación Activa','color':'#3B82F6','icono':'⚡',
                'score_auto':round(score_auto,1),'score_carga':round(score_carga,1),
                'desc':'Sistema autonómico sólido absorbiendo carga moderada-alta.',
                'accion':'Continuar plan. Monitorear HRV diariamente.'}

    elif score_auto >= 7.0 and score_carga >= 5.0:
        return {'nombre':'Límite de Carga','color':'#F59E0B','icono':'⚠️',
                'score_auto':round(score_auto,1),'score_carga':round(score_carga,1),
                'desc':'Buena autonomía pero carga muy alta — en el límite.',
                'accion':'Reducir volumen 20%. Mantener calidad de sueño.'}

    elif 4.0 <= score_auto < 7.0 and score_carga < 2.0:
        return {'nombre':'Recuperación','color':'#8B5CF6','icono':'✨',
                'score_auto':round(score_auto,1),'score_carga':round(score_carga,1),
                'desc':'Carga baja con sistema autonómico en recuperación.',
                'accion':'Sesiones regenerativas. Esperar HRV > baseline para cargar.'}

    elif 4.0 <= score_auto < 7.0 and 2.0 <= score_carga < 5.0:
        # Diferenciar por HRV relativo para evitar duplicados
        if hrv_rel >= 1.0:
            return {'nombre':'Carga Progresiva','color':'#60A5FA','icono':'📈',
                    'score_auto':round(score_auto,1),'score_carga':round(score_carga,1),
                    'desc':'HRV normal con carga en aumento — fase de construcción.',
                    'accion':'Plan en curso. Vigilar tendencia HRV semanal.'}
        else:
            return {'nombre':'Fatiga Moderada','color':'#FBBF24','icono':'🔻',
                    'score_auto':round(score_auto,1),'score_carga':round(score_carga,1),
                    'desc':'HRV por debajo del baseline personal con carga acumulada.',
                    'accion':'Reducir intensidad. Priorizar recuperación nocturna.'}

    elif 4.0 <= score_auto < 7.0 and score_carga >= 5.0:
        return {'nombre':'Fatiga Alta','color':'#F97316','icono':'🔴',
                'score_auto':round(score_auto,1),'score_carga':round(score_carga,1),
                'desc':'Carga muy alta con señales autonómicas comprometidas.',
                'accion':'Reducir carga 30-40%. Mínimo 2 días regenerativos.'}

    elif score_auto < 4.0 and score_carga >= 5.0:
        return {'nombre':'Sobrecarga','color':'#EF4444','icono':'🚨',
                'score_auto':round(score_auto,1),'score_carga':round(score_carga,1),
                'desc':'Sistema autonómico comprometido + carga muy alta.',
                'accion':'Parar. Recuperación activa 3-5 días mínimo.'}

    elif score_auto < 4.0 and score_carga < 2.0:
        return {'nombre':'Estrés No Deportivo','color':'#A78BFA','icono':'😴',
                'score_auto':round(score_auto,1),'score_carga':round(score_carga,1),
                'desc':'Señales autonómicas bajas sin alta carga deportiva.',
                'accion':'Revisar sueño, estrés laboral, hidratación, enfermedad.'}

    else:
        return {'nombre':'Fatiga Acumulada','color':'#94A3B8','icono':'😓',
                'score_auto':round(score_auto,1),'score_carga':round(score_carga,1),
                'desc':'Estado de desgaste con múltiples señales comprometidas.',
                'accion':'Semana de recuperación. Evaluar carga del mesociclo.'}


def calcular_clustering(
    conn,
    atleta_id: int,
    n_clusters: int = 5,
    dias:       int = 180,
) -> dict:
    """
    Calcula el clustering de estados del atleta.

    Returns dict con:
        clusters: lista de clusters con nombre, color, % de días, centroide
        estado_hoy: qué cluster es el estado actual
        historia: serie temporal de cluster_id por fecha
        varianza_explicada: % varianza explicada por los primeros 2 PCs
    """
    fecha_desde = str(date.today() - timedelta(days=dias))

    # ── Cargar datos ──────────────────────────────────────────────────────────
    df = pd.read_sql("""
        SELECT s.fecha,
               s.hrv_rmssd, s.hrv_estimado_valor,
               s.hr_reposo, s.sleep_h, s.stress_avg, s.spo2_avg,
               s.hanna_life
        FROM sleep_hrv s
        WHERE s.atleta_id=%s AND s.fecha >= %s
        ORDER BY s.fecha
    """, conn, params=[atleta_id, fecha_desde])

    df_tsb = pd.read_sql("""
        SELECT fecha, ctl, atl
        FROM sesiones
        WHERE atleta_id=%s AND ctl IS NOT NULL AND fecha >= %s
        ORDER BY fecha
    """, conn, params=[atleta_id, fecha_desde])

    if len(df) < 20:
        return {'error': 'Datos insuficientes (mínimo 20 días)', 'clusters': []}

    df['fecha'] = df['fecha'].astype(str)
    df['hrv'] = df['hrv_rmssd'].combine_first(df['hrv_estimado_valor'])

    # Merge con TSB
    if len(df_tsb) > 0:
        df_tsb['fecha'] = df_tsb['fecha'].astype(str)
        df_tsb['tsb'] = df_tsb['ctl'].astype(float) - df_tsb['atl'].astype(float)
        df_tsb['atl_ctl'] = df_tsb['atl'].astype(float) / df_tsb['ctl'].astype(float).replace(0, np.nan)
        df = df.merge(df_tsb[['fecha','tsb','atl_ctl']], on='fecha', how='left')
    else:
        df['tsb'] = np.nan
        df['atl_ctl'] = np.nan

    # ── Baseline personal ─────────────────────────────────────────────────────
    try:
        from noah_baseline import get_baseline
        baseline = get_baseline(conn, atleta_id)
    except ImportError:
        baseline = None

    hrv_media  = baseline.get('hrv_media',  float(df['hrv'].dropna().mean()) if df['hrv'].notna().any() else 50) if baseline else float(df['hrv'].dropna().mean()) if df['hrv'].notna().any() else 50
    fc_media   = baseline.get('fc_media',   float(df['hr_reposo'].dropna().mean()) if df['hr_reposo'].notna().any() else 55) if baseline else float(df['hr_reposo'].dropna().mean()) if df['hr_reposo'].notna().any() else 55
    sleep_media = baseline.get('sleep_media_h', float(df['sleep_h'].dropna().mean()) if df['sleep_h'].notna().any() else 7) if baseline else 7

    # ── Features normalizadas al baseline ────────────────────────────────────
    df['hrv_rel']   = df['hrv'] / hrv_media if hrv_media > 0 else 1.0
    df['fc_rel']    = df['hr_reposo'] / fc_media if fc_media > 0 else 1.0
    df['sleep_rel'] = df['sleep_h'] / sleep_media if sleep_media > 0 else 1.0

    feature_cols = ['hrv_rel', 'fc_rel', 'sleep_rel', 'stress_avg',
                    'spo2_avg', 'atl_ctl', 'tsb']

    # Imputar NaN con mediana de la columna
    df_feat = df[feature_cols].copy()
    for col in feature_cols:
        med = df_feat[col].median()
        df_feat[col] = df_feat[col].fillna(med if not np.isnan(med) else 0)

    # Filas con demasiados NaN
    df_feat = df_feat.dropna()
    df_valid = df.loc[df_feat.index]

    if len(df_feat) < 15:
        return {'error': 'Datos insuficientes después de limpiar NaN', 'clusters': []}

    # ── Escalar ───────────────────────────────────────────────────────────────
    scaler = StandardScaler()
    X = scaler.fit_transform(df_feat.values)

    # ── KMeans ────────────────────────────────────────────────────────────────
    n_clusters = min(n_clusters, len(df_feat) // 5)  # no más clusters que datos/5
    n_clusters = max(3, n_clusters)

    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X)

    # ── PCA para visualización 2D ─────────────────────────────────────────────
    pca = PCA(n_components=2, random_state=42)
    X_2d = pca.fit_transform(X)
    varianza_explicada = float(sum(pca.explained_variance_ratio_) * 100)

    # ── Centroides desescalados ───────────────────────────────────────────────
    centroides_scaled = kmeans.cluster_centers_
    centroides_orig   = scaler.inverse_transform(centroides_scaled)

    # ── Construir clusters ────────────────────────────────────────────────────
    clusters = []
    for k in range(n_clusters):
        mask = labels == k
        n_dias = int(mask.sum())
        if n_dias == 0:
            continue

        cent_dict = dict(zip(feature_cols, centroides_orig[k]))
        etiqueta  = _etiquetar_cluster(cent_dict, rank=k)

        # Fechas en este cluster
        fechas_cluster = df_valid['fecha'].iloc[np.where(mask)[0]].tolist()

        # HANNA LIFE promedio en este cluster
        hl_vals = df_valid['hanna_life'].iloc[np.where(mask)[0]].dropna()
        hl_media = float(hl_vals.mean()) if len(hl_vals) > 0 else None

        # Posición PCA del centroide
        cent_2d = pca.transform(centroides_scaled[k:k+1])[0]

        # Métricas reales del cluster para mostrar en dashboard
        hrv_media_cluster = float(df_valid['hrv'].iloc[np.where(mask)[0]].dropna().mean()) if df_valid['hrv'].iloc[np.where(mask)[0]].notna().any() else None
        fc_media_cluster  = float(df_valid['hr_reposo'].iloc[np.where(mask)[0]].dropna().mean()) if 'hr_reposo' in df_valid and df_valid['hr_reposo'].iloc[np.where(mask)[0]].notna().any() else None
        sleep_media_cluster = float(df_valid['sleep_h'].iloc[np.where(mask)[0]].dropna().mean()) if 'sleep_h' in df_valid and df_valid['sleep_h'].iloc[np.where(mask)[0]].notna().any() else None
        stress_media_cluster = float(df_valid['stress_avg'].iloc[np.where(mask)[0]].dropna().mean()) if 'stress_avg' in df_valid and df_valid['stress_avg'].iloc[np.where(mask)[0]].notna().any() else None
        tsb_media_cluster = round(cent_dict.get('tsb', 0), 1)

        clusters.append({
            'id':          k,
            'nombre':      etiqueta['nombre'],
            'color':       etiqueta['color'],
            'icono':       etiqueta['icono'],
            'desc':        etiqueta['desc'],
            'accion':      etiqueta['accion'],
            'score_auto':  etiqueta.get('score_auto'),
            'score_carga': etiqueta.get('score_carga'),
            'n_dias':      n_dias,
            'pct_dias':    round(n_dias / len(labels) * 100, 1),
            'hl_media':    round(hl_media, 1) if hl_media else None,
            'hrv_media':   round(hrv_media_cluster, 1) if hrv_media_cluster else None,
            'fc_media':    round(fc_media_cluster, 1) if fc_media_cluster else None,
            'sleep_media': round(sleep_media_cluster, 2) if sleep_media_cluster else None,
            'stress_media':round(stress_media_cluster, 1) if stress_media_cluster else None,
            'tsb_media':   tsb_media_cluster,
            'centroide':   {k: round(v, 3) for k,v in cent_dict.items()},
            'pca_x':       round(float(cent_2d[0]), 3),
            'pca_y':       round(float(cent_2d[1]), 3),
            'fechas':      fechas_cluster[-10:],
        })

    # Ordenar por % de días descendente
    clusters.sort(key=lambda c: c['pct_dias'], reverse=True)

    # Asignar colores únicos por posición — independiente del nombre
    PALETA = ['#F59E0B', '#EF4444', '#3B82F6', '#10B981', '#8B5CF6', '#F97316', '#06B6D4']
    for i, c in enumerate(clusters):
        c['color'] = PALETA[i % len(PALETA)]

    # Desambiguar clusters con mismo nombre usando la diferencia más notable
    from collections import Counter
    nombres_count = Counter(c['nombre'] for c in clusters)
    nombres_vistos = {}
    for c in clusters:
        n = c['nombre']
        if nombres_count[n] > 1:
            nombres_vistos[n] = nombres_vistos.get(n, 0) + 1
            rank = nombres_vistos[n]
            # Diferenciar por la característica más distintiva
            hrv  = c.get('hrv_media')
            tsb  = c.get('tsb_media')
            sleep = c.get('sleep_media')
            if hrv is not None and rank == 1:
                sufijo = f'(HRV {hrv:.0f}ms · mejor)'
            elif tsb is not None and tsb < -15:
                sufijo = f'(TSB {tsb:.0f} · carga alta)'
            elif sleep is not None and sleep < 6.5:
                sufijo = f'(sueño {sleep:.1f}h)'
            elif hrv is not None:
                sufijo = f'(HRV {hrv:.0f}ms)'
            else:
                sufijo = f'(variante {rank})'
            c['nombre'] = f'{n} {sufijo}'

    # ── Estado hoy ────────────────────────────────────────────────────────────
    estado_hoy = None
    hoy_str = str(date.today())
    idx_hoy = df_valid[df_valid['fecha'] == hoy_str].index
    if len(idx_hoy) > 0:
        pos_hoy = df_valid.index.get_loc(idx_hoy[0])
        if pos_hoy < len(labels):
            cluster_hoy = int(labels[pos_hoy])
            estado_hoy  = next((c for c in clusters if c['id'] == cluster_hoy), None)
            # Agregar coordenadas PCA del punto de hoy
            if estado_hoy:
                estado_hoy = {**estado_hoy,
                    'pca_x_hoy': round(float(X_2d[pos_hoy, 0]), 3),
                    'pca_y_hoy': round(float(X_2d[pos_hoy, 1]), 3)}

    # ── Serie temporal ────────────────────────────────────────────────────────
    historia = [
        {
            'fecha':      str(df_valid['fecha'].iloc[i]),
            'cluster_id': int(labels[i]),
            'pca_x':      round(float(X_2d[i, 0]), 3),
            'pca_y':      round(float(X_2d[i, 1]), 3),
            'hanna_life': float(df_valid['hanna_life'].iloc[i]) if not pd.isna(df_valid['hanna_life'].iloc[i]) else None,
        }
        for i in range(len(labels))
    ]

    return {
        'clusters':            clusters,
        'estado_hoy':          estado_hoy,
        'historia':            historia,
        'varianza_explicada':  round(varianza_explicada, 1),
        'n_dias_analizados':   len(labels),
        'n_clusters':          len(clusters),
        'features_usadas':     feature_cols,
        'baseline_usado':      bool(baseline and baseline.get('hrv_media')),
    }


def guardar_clustering(conn, atleta_id: int,
                       resultado: dict) -> bool:
    """Guarda el resultado del clustering en la DB para no recalcular siempre."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS atleta_clustering (
            id          SERIAL PRIMARY KEY,
            atleta_id   INTEGER NOT NULL UNIQUE,
            fecha       TEXT,
            resultado   TEXT,
            FOREIGN KEY (atleta_id) REFERENCES atletas(id)
        )
    """)
    conn.execute("""
        INSERT INTO atleta_clustering (atleta_id, fecha, resultado)
        VALUES (%s,%s,%s)
        ON CONFLICT(atleta_id) DO UPDATE SET fecha=excluded.fecha, resultado=excluded.resultado
    """, (atleta_id, str(date.today()), json.dumps(resultado)))
    conn.commit()
    return True


# ── Script standalone ─────────────────────────────────────────────────────────
if __name__ == '__main__':
    import argparse, sys, os
    from pathlib import Path
    from db_compat import ConexionCompat
    sys.path.insert(0, str(Path(__file__).parent))

    ap = argparse.ArgumentParser(description='NOAH — Clustering de estados')
    ap.add_argument('--atleta',    type=int, required=True)
    ap.add_argument('--clusters',  type=int, default=5)
    ap.add_argument('--dias',      type=int, default=180)
    args = ap.parse_args()

    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("Falta la variable de entorno DATABASE_URL (cadena de conexión a Postgres/Supabase)")
        sys.exit(1)
    import psycopg2.extras
    conn = ConexionCompat(psycopg2.connect(db_url, cursor_factory=psycopg2.extras.DictCursor))

    nombre = conn.execute(
        "SELECT nombre FROM atletas WHERE id=%s", (args.atleta,)).fetchone()
    print(f'\nClustering para {nombre[0] if nombre else args.atleta}...')

    result = calcular_clustering(conn, args.atleta, args.clusters, args.dias)

    if 'error' in result:
        print(f'Error: {result["error"]}')
    else:
        print(f'\n{result["n_clusters"]} clusters en {result["n_dias_analizados"]} días')
        print(f'Varianza explicada por PCA: {result["varianza_explicada"]}%\n')
        for c in result['clusters']:
            print(f'{c["icono"]} {c["nombre"]:20} {c["pct_dias"]:5.1f}% ({c["n_dias"]} días)'
                  f'  HL media: {c["hl_media"]}')
            print(f'   → {c["accion"]}')
        if result['estado_hoy']:
            e = result['estado_hoy']
            print(f'\nHOY: {e["icono"]} {e["nombre"]} — {e["desc"]}')

        guardar_clustering(conn, args.atleta, result)
        print('\nGuardado en DB ✓')

    conn.close()
