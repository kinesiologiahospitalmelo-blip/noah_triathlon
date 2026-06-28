"""
swim_processor.py — Proyecto NOAH
===================================
Procesa laps y lengths de natación desde Garmin Connect.
Calcula CSS real, eficiencia técnica y distribución de zonas.

Métricas calculadas:
  - CSS (Critical Swim Speed) desde los mejores largos
  - SWOLF promedio y por zona
  - Paladas por largo y eficiencia de brazada
  - Distribución de intensidad por largo
  - Tendencia técnica (mejora/empeora con la fatiga)
"""

from __future__ import annotations
import psycopg2
import pandas as pd
import numpy as np
from datetime import date
from pathlib import Path
from dataclasses import dataclass, field


# ── Estructura de un largo (25m) ─────────────────────────────────────────────
@dataclass
class Largo:
    index:      int
    lap_num:    int
    tiempo_seg: float        # segundos para 25m
    paladas:    int
    swolf:      float        # tiempo + paladas (menor = más eficiente)
    hr:         float | None
    stroke:     str = 'FREESTYLE'

    @property
    def pace_100m(self) -> float:
        """Pace en min/100m"""
        return (self.tiempo_seg * 4) / 60

    @property
    def velocidad_ms(self) -> float:
        return 25 / self.tiempo_seg if self.tiempo_seg > 0 else 0


# ── Estructura de un lap (bloque de entrenamiento) ────────────────────────────
@dataclass
class LapSwim:
    index:        int
    distancia_m:  float
    duracion_seg: float
    hr_avg:       float | None
    hr_max:       float | None
    paladas:      int | None
    swolf:        float | None
    n_largos:     int
    largos:       list[Largo] = field(default_factory=list)

    @property
    def pace_100m(self) -> float:
        if self.duracion_seg > 0 and self.distancia_m > 0:
            return (self.duracion_seg / self.distancia_m * 100) / 60
        return 0


# ── Parser de splits de Garmin ────────────────────────────────────────────────
def parsear_splits_garmin(splits_data: dict) -> tuple[list[LapSwim], list[Largo]]:
    """
    Parsea la respuesta de client.get_activity_splits()
    Retorna (laps, todos_los_largos)
    """
    laps = []
    todos_largos = []
    largo_global = 0

    for lap_data in (splits_data.get('lapDTOs') or []):
        lap_idx = lap_data.get('lapIndex', len(laps) + 1)
        largos_lap = []

        for length_data in (lap_data.get('lengthDTOs') or []):
            largo_global += 1
            tiempo = length_data.get('duration', 0)
            paladas = length_data.get('totalNumberOfStrokes', 0)
            swolf_v = length_data.get('averageSWOLF', 0)
            hr = length_data.get('averageHR')

            if tiempo < 10 or tiempo > 120:  # descartar largos inválidos
                continue

            largo = Largo(
                index=largo_global,
                lap_num=lap_idx,
                tiempo_seg=round(tiempo, 2),
                paladas=int(paladas) if paladas else 0,
                swolf=round(swolf_v, 1) if swolf_v else 0,
                hr=round(hr, 0) if hr else None,
                stroke=length_data.get('swimStroke', 'FREESTYLE'),
            )
            largos_lap.append(largo)
            todos_largos.append(largo)

        lap = LapSwim(
            index=lap_idx,
            distancia_m=lap_data.get('distance', 0),
            duracion_seg=lap_data.get('duration', 0),
            hr_avg=lap_data.get('averageHR'),
            hr_max=lap_data.get('maxHR'),
            paladas=lap_data.get('totalNumberOfStrokes'),
            swolf=lap_data.get('averageSWOLF'),
            n_largos=lap_data.get('numberOfActiveLengths', len(largos_lap)),
            largos=largos_lap,
        )
        laps.append(lap)

    return laps, todos_largos


# ── Cálculo de CSS ────────────────────────────────────────────────────────────
def calcular_css(largos: list[Largo]) -> dict:
    """
    CSS (Critical Swim Speed) = velocidad sostenible al umbral de lactato.
    
    Método: percentil 10 de los tiempos (los mejores largos estables).
    Excluye el primer y último largo de cada lap (calentamiento/fatiga).
    También calcula CSS con método T400-T200 si hay suficientes largos.
    """
    if not largos:
        return {}

    # Solo freestyle, excluir outliers
    tiempos = [l.tiempo_seg for l in largos
               if l.stroke == 'FREESTYLE' and 14 < l.tiempo_seg < 60]

    if len(tiempos) < 4:
        return {}

    tiempos_arr = np.array(tiempos)

    # CSS = percentil 15 de los mejores largos (no el mínimo absoluto)
    css_seg_25 = float(np.percentile(tiempos_arr, 15))
    css_min_100 = round(float((css_seg_25 * 4) / 60), 3)

    # Estadísticas adicionales — float() explícito: np.mean/np.std/np.max/
    # np.min devuelven numpy.float64, que psycopg2 no serializa bien en
    # Postgres (mismo bug encontrado y corregido en noa_db.py).
    pace_promedio = round(float((np.mean(tiempos_arr) * 4) / 60), 3)
    pace_maximo   = round(float((np.max(tiempos_arr) * 4) / 60), 3)
    pace_minimo   = round(float((np.min(tiempos_arr) * 4) / 60), 3)

    # Variabilidad de pace (consistencia)
    cv = round(float(np.std(tiempos_arr) / np.mean(tiempos_arr) * 100), 1)

    return {
        'css_seg_25':      round(float(css_seg_25), 2),
        'css_min_100':     css_min_100,
        'pace_prom_100':   pace_promedio,
        'pace_min_100':    pace_minimo,
        'pace_max_100':    pace_maximo,
        'cv_pace_pct':     cv,           # <5% = muy consistente, >15% = variable
        'n_largos':        len(tiempos),
    }


# ── Eficiencia técnica ────────────────────────────────────────────────────────
def analizar_eficiencia(largos: list[Largo]) -> dict:
    """
    Analiza eficiencia técnica de la sesión.
    
    SWOLF = tiempo (seg) + paladas por largo
    Menor SWOLF = más eficiente (menos esfuerzo para misma velocidad)
    
    Tendencia de fatiga: ¿el SWOLF empeora con los largos? (sí = fatiga técnica)
    """
    if not largos:
        return {}

    swolfs   = [l.swolf for l in largos if l.swolf > 0]
    paladas  = [l.paladas for l in largos if l.paladas > 0]

    if not swolfs:
        return {}

    swolf_arr = np.array(swolfs)
    indices   = np.arange(len(swolfs))

    # Tendencia lineal del SWOLF (pendiente positiva = empeora con fatiga)
    if len(swolf_arr) > 4:
        pendiente = float(np.polyfit(indices, swolf_arr, 1)[0])
    else:
        pendiente = 0

    # Clasificación de eficiencia
    swolf_prom = float(swolf_arr.mean())
    if swolf_prom < 38:
        nivel_efic = 'elite'
    elif swolf_prom < 44:
        nivel_efic = 'avanzado'
    elif swolf_prom < 50:
        nivel_efic = 'intermedio'
    else:
        nivel_efic = 'basico'

    return {
        'swolf_promedio':  round(swolf_prom, 1),
        'swolf_mejor':     round(float(swolf_arr.min()), 1),
        'swolf_peor':      round(float(swolf_arr.max()), 1),
        'paladas_prom':    round(float(np.mean(paladas)), 1) if paladas else None,
        'tendencia_swolf': round(pendiente, 3),   # >0.1 = fatiga técnica notable
        'fatiga_tecnica':  pendiente > 0.15,
        'nivel_eficiencia': nivel_efic,
    }


# ── Distribución de zonas de natación ────────────────────────────────────────
def distribucion_zonas(largos: list[Largo], css_seg_25: float) -> dict:
    """
    Clasifica cada largo por zona según pace relativo al CSS.
    
    Z1: >120% CSS (recuperación)
    Z2: 115-120% CSS (endurance)
    Z3: 105-115% CSS (tempo)
    Z4: 98-105% CSS (umbral, CSS)
    Z5: <98% CSS (VO2max)
    """
    if not largos or not css_seg_25:
        return {}

    zonas = {'Z1': 0, 'Z2': 0, 'Z3': 0, 'Z4': 0, 'Z5': 0}

    for l in largos:
        if l.stroke != 'FREESTYLE' or l.tiempo_seg <= 0:
            continue
        ratio = l.tiempo_seg / css_seg_25  # >1 = más lento que CSS
        if ratio > 1.20:
            zonas['Z1'] += 1
        elif ratio > 1.15:
            zonas['Z2'] += 1
        elif ratio > 1.05:
            zonas['Z3'] += 1
        elif ratio > 0.98:
            zonas['Z4'] += 1
        else:
            zonas['Z5'] += 1

    total = sum(zonas.values())
    if total == 0:
        return {}

    return {
        zona: {
            'largos': n,
            'metros': n * 25,
            'pct':    round(n / total * 100, 1),
        }
        for zona, n in zonas.items()
    }


# ── Análisis completo de sesión ───────────────────────────────────────────────
def analizar_sesion_swim(splits_data: dict, lthr_swim: float = None) -> dict:
    """
    Análisis completo de una sesión de natación.
    Retorna dict con todos los indicadores para guardar en DB y mostrar en dashboard.
    """
    laps, largos = parsear_splits_garmin(splits_data)

    if not largos:
        return {'error': 'Sin datos de largos'}

    css_data  = calcular_css(largos)
    efic_data = analizar_eficiencia(largos)
    css_seg   = css_data.get('css_seg_25', 0)
    zonas     = distribucion_zonas(largos, css_seg) if css_seg else {}

    # TSS estimado por HR si hay LTHR
    tss = None
    if lthr_swim:
        hrs = [l.hr for l in largos if l.hr]
        if hrs:
            hr_prom = float(np.mean(hrs))
            dur_min = sum(l.tiempo_seg for l in largos) / 60
            IF = hr_prom / lthr_swim
            tss = round(IF**2 * (dur_min/60) * 100, 1)

    return {
        'n_largos':     len(largos),
        'n_laps':       len(laps),
        'distancia_m':  len(largos) * 25,
        'duracion_min': round(sum(l.tiempo_seg for l in largos) / 60, 1),
        'css':          css_data,
        'eficiencia':   efic_data,
        'zonas':        zonas,
        'tss_estimado': tss,
        'laps_resumen': [
            {
                'lap':        lap.index,
                'dist_m':     lap.distancia_m,
                'pace_100m':  round(lap.pace_100m, 3),
                'hr_avg':     lap.hr_avg,
                'swolf':      lap.swolf,
                'n_largos':   lap.n_largos,
            }
            for lap in laps
        ],
    }


# ── Guardar laps en DB ────────────────────────────────────────────────────────
def guardar_laps_swim(conn, atleta_id: int,
                       sesion_id: int, fecha: str,
                       laps: list[LapSwim], largos: list[Largo]):
    """Guarda laps y lengths de natación en la DB."""

    # Asegurar columnas de swim en tabla laps — PRAGMA table_info (SQLite)
    # reemplazado por el helper compartido.
    from db_compat import asegurar_columnas
    asegurar_columnas(conn, 'laps', [
        ('paladas',      'INTEGER'),
        ('swolf',        'REAL'),
        ('swim_stroke',  'TEXT'),
        ('n_largos',     'INTEGER'),
        ('es_largo',     'INTEGER'),  # 1 = length individual de 25m
        ('lap_padre',    'INTEGER'),  # lap al que pertenece este largo
    ])
    conn.commit()

    # Insertar laps (bloques). NOTA: el original usaba INSERT OR IGNORE,
    # pero la tabla "laps" no tiene ninguna restricción UNIQUE real (
    # confirmado contra el esquema real de noa.db) — "OR IGNORE" nunca
    # deduplicaba nada en la práctica, era un INSERT normal. Se mantiene
    # ese mismo comportamiento aquí, sin inventar un ON CONFLICT que no
    # existía antes.
    for lap in laps:
        conn.execute('''
            INSERT INTO laps
            (atleta_id, sesion_id, fecha, lap_num, distance_km, duration_min,
             hr_avg, pace, paladas, swolf, n_largos, es_largo)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0)
        ''', (
            atleta_id, sesion_id, fecha, lap.index,
            round(lap.distancia_m / 1000, 3),
            round(lap.duracion_seg / 60, 2),
            lap.hr_avg,
            round(lap.pace_100m, 3),
            lap.paladas, lap.swolf, lap.n_largos,
        ))

    # Insertar largos individuales (25m cada uno)
    for largo in largos:
        conn.execute('''
            INSERT INTO laps
            (atleta_id, sesion_id, fecha, lap_num, distance_km, duration_min,
             hr_avg, pace, paladas, swolf, swim_stroke, es_largo, lap_padre)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1,%s)
        ''', (
            atleta_id, sesion_id, fecha,
            largo.index,                          # index global del largo
            0.025,                                # 25m
            round(largo.tiempo_seg / 60, 3),
            largo.hr,
            round(largo.pace_100m, 3),
            largo.paladas, largo.swolf,
            largo.stroke,
            largo.lap_num,
        ))

    conn.commit()
    return len(laps), len(largos)


# ── Calcular CSS histórico del atleta ─────────────────────────────────────────
def calcular_css_historico(conn, atleta_id: int) -> dict:
    """
    Calcula el CSS del atleta desde todos los largos históricos.
    Usa los mejores largos de las últimas 12 sesiones de natación.
    """
    # Buscar largos históricos de piscina
    df = pd.read_sql('''
        SELECT l.fecha, l.duration_min, l.distance_km, l.swolf, l.paladas
        FROM laps l
        JOIN sesiones s ON l.sesion_id = s.id
        WHERE s.atleta_id=%s AND s.sport='swimming'
        AND l.es_largo=1 AND l.distance_km < 0.05
        AND l.duration_min > 0
        ORDER BY l.fecha DESC
        LIMIT 500
    ''', conn, params=[atleta_id])

    if len(df) < 10:
        return {}

    # Tiempo en segundos por largo
    df['tiempo_seg'] = df['duration_min'] * 60
    df = df[(df['tiempo_seg'] > 14) & (df['tiempo_seg'] < 60)]

    if len(df) < 5:
        return {}

    css_seg = float(np.percentile(df['tiempo_seg'], 15))
    css_min_100 = round((css_seg * 4) / 60, 3)

    return {
        'css_seg_25':   round(css_seg, 2),
        'css_min_100':  css_min_100,
        'n_largos':     len(df),
        'swolf_prom':   round(df['swolf'].dropna().mean(), 1) if 'swolf' in df else None,
    }


# ── Imprimir resumen de sesión ────────────────────────────────────────────────
def imprimir_resumen(analisis: dict):
    print('\n' + '='*55)
    print('  ANÁLISIS SESIÓN NATACIÓN — NOAH')
    print('='*55)
    print(f'  Distancia: {analisis["distancia_m"]}m  ({analisis["n_largos"]} largos, {analisis["n_laps"]} series)')
    print(f'  Duración:  {analisis["duracion_min"]} min')

    css = analisis.get('css', {})
    if css:
        m = int(css['css_min_100'])
        s = int((css['css_min_100'] - m) * 60)
        print(f'\n  CSS estimado:  {m}:{s:02d} /100m')
        pm = int(css['pace_prom_100'])
        ps = int((css['pace_prom_100'] - pm) * 60)
        print(f'  Pace promedio: {pm}:{ps:02d} /100m')
        print(f'  Consistencia:  CV={css["cv_pace_pct"]}% ', end='')
        print('✓ muy consistente' if css['cv_pace_pct'] < 5 else
              '~ aceptable' if css['cv_pace_pct'] < 10 else '✗ muy variable')

    efic = analisis.get('eficiencia', {})
    if efic:
        print(f'\n  SWOLF prom:    {efic["swolf_promedio"]} ({efic["nivel_eficiencia"]})')
        print(f'  Paladas/largo: {efic["paladas_prom"]}')
        if efic.get('fatiga_tecnica'):
            print('  ⚠ Fatiga técnica detectada (SWOLF empeora con la sesión)')

    zonas = analisis.get('zonas', {})
    if zonas:
        print(f'\n  Distribución de intensidad:')
        for zona, data in zonas.items():
            bar = '█' * int(data['pct'] / 5)
            print(f'    {zona}: {bar} {data["pct"]}% ({data["metros"]}m)')

    if analisis.get('tss_estimado'):
        print(f'\n  TSS estimado:  {analisis["tss_estimado"]}')
    print('='*55)


if __name__ == '__main__':
    # Test con datos reales de Garmin
    import sys, base64, os
    import psycopg2.extras
    from db_compat import ConexionCompat
    sys.path.insert(0, str(Path(__file__).parent))

    def _dec(c):
        try: return base64.b64decode(c.encode()).decode()
        except: return c

    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("Falta la variable de entorno DATABASE_URL (cadena de conexión a Postgres/Supabase)")
        sys.exit(1)
    conn = ConexionCompat(psycopg2.connect(db_url, cursor_factory=psycopg2.extras.DictCursor))
    row = conn.execute('SELECT garmin_user, garmin_pass, lthr_run FROM atletas WHERE id=1').fetchone()

    from garminconnect import Garmin
    print("Conectando a Garmin...")
    client = Garmin(row['garmin_user'], _dec(row['garmin_pass']))
    client.login()
    print("✓ Conectado\n")

    # Buscar última sesión de natación
    from datetime import timedelta
    acts = client.get_activities_by_date('2025-05-01', '2025-06-30')
    swim_acts = [a for a in (acts or [])
                 if a.get('activityType', {}).get('typeKey', '') in
                 ('lap_swimming', 'pool_swimming', 'swimming')]

    if not swim_acts:
        print("Sin actividades de natación en ese período")
        conn.close()
        sys.exit(0)

    act = swim_acts[0]
    act_id = act.get('activityId')
    print(f"Analizando: {act.get('activityName')} — {act.get('startTimeLocal')[:10]}")

    splits = client.get_activity_splits(act_id)
    lthr_swim = round((row['lthr_run'] or 162) * 0.92)
    analisis = analizar_sesion_swim(splits, lthr_swim)
    imprimir_resumen(analisis)

    conn.close()
