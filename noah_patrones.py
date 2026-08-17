"""
noah_patrones.py — Aprendizaje de patrones de entrenamiento del atleta
=======================================================================
Analiza las ultimas 12 semanas y extrae:
  1. Distribucion real por deporte (y calcula el ajuste hacia el objetivo)
  2. Duracion tipica por sesion, deporte y tipo (easy/quality/long)
  3. Dias preferidos (solo para running/single sport, no triatlon)
  4. Sesiones efectivas: cuales produjeron mejor adaptacion
  5. Frecuencia semanal real

Principios:
  - Triatlon: objetivo 45% bike, 35% run, 20% swim (Navarro)
  - Dias fijos para triatlon (combinacion de estimulos)
  - Dias aprendidos para running/single sport
  - Transicion gradual: max 3% de cambio por mesociclo hacia el objetivo
  - Aprender de lo que funciono (CTL sube + HRV estable = buena sesion)
"""

from datetime import date, timedelta
from collections import defaultdict
import math


# ── Distribuciones objetivo por deporte ──────────────────────────────────

DISTRIBUCION_OBJETIVO = {
    'triatlon': {'running': 0.35, 'cycling': 0.45, 'swimming': 0.20},
    'running':  {'running': 1.0},
    'cycling':  {'cycling': 1.0},
    'swimming': {'swimming': 1.0},
}

MAX_CAMBIO_POR_MESO = 0.03  # max 3% de shift por mesociclo (3-4 semanas)


def _normalizar_sport(sport):
    """Normaliza nombre de deporte a running/cycling/swimming."""
    s = (sport or '').lower()
    if 'run' in s or 'trail' in s:
        return 'running'
    if 'cycl' in s or 'bike' in s or 'ride' in s:
        return 'cycling'
    if 'swim' in s:
        return 'swimming'
    return s


def _clasificar_sesion(sport, tss, duration_min, hr_avg, lthr, zonas_txt=None):
    """Clasifica sesion en easy/quality/long."""
    sport = _normalizar_sport(sport)

    # Por duracion: long si supera el umbral por deporte
    umbrales_long = {'running': 60, 'cycling': 90, 'swimming': 45}
    umbral_long = umbrales_long.get(sport, 60)

    if duration_min and duration_min >= umbral_long:
        return 'long'

    # Por intensidad: quality si HR > 88% LTHR o TSS/min > umbral
    if hr_avg and lthr and hr_avg > lthr * 0.88:
        return 'quality'

    if tss and duration_min and duration_min > 0:
        tss_por_min = tss / duration_min
        if tss_por_min > 1.2:
            return 'quality'

    return 'easy'


def analizar_patrones_atleta(conn, atleta_id, semanas=12):
    """
    Analiza las ultimas N semanas del atleta y extrae patrones de entrenamiento.

    Returns dict con:
      distribucion_actual, distribucion_plan, duracion_tipica,
      dias_preferidos, sesiones_por_semana, sesiones_efectivas
    """
    cur = conn.cursor()

    # Datos del atleta
    cur.execute("SELECT deporte_ppal, lthr_run, lthr_bike, lthr_swim FROM atletas WHERE id=%s", (atleta_id,))
    atleta_row = cur.fetchone()
    if not atleta_row:
        return None
    deporte = (atleta_row[0] or 'running').lower()
    lthr_map = {
        'running': float(atleta_row[1] or 160),
        'cycling': float(atleta_row[2] or 150),
        'swimming': float(atleta_row[3] or round(float(atleta_row[1] or 160) * 0.92)),
    }

    # Sesiones de las ultimas N semanas
    fecha_desde = (date.today() - timedelta(days=semanas * 7)).isoformat()
    cur.execute("""
        SELECT id, fecha, sport, tss_total, duration_min, hr_avg, ctl,
               to_char(fecha::date, 'ID') as dia_semana
        FROM sesiones
        WHERE atleta_id=%s AND fecha >= %s AND duration_min > 5
        ORDER BY fecha
    """, (atleta_id, fecha_desde))
    sesiones = cur.fetchall()

    if not sesiones:
        return _patron_default(deporte)

    # ══════════════════════════════════════════════════════════════
    # 1. DISTRIBUCION POR DEPORTE (TSS y tiempo)
    # ══════════════════════════════════════════════════════════════
    tss_por_sport = defaultdict(float)
    dur_por_sport = defaultdict(float)
    total_tss = 0
    total_dur = 0

    for s in sesiones:
        sport = _normalizar_sport(s[2])
        tss = float(s[3] or 0)
        dur = float(s[4] or 0)
        tss_por_sport[sport] += tss
        dur_por_sport[sport] += dur
        total_tss += tss
        total_dur += dur

    # Distribucion actual (por TSS)
    distribucion_actual = {}
    for sport in ['running', 'cycling', 'swimming']:
        if total_tss > 0:
            distribucion_actual[sport] = round(tss_por_sport[sport] / total_tss, 3)
        else:
            distribucion_actual[sport] = 0

    # Distribucion plan: mover gradualmente hacia objetivo
    objetivo = DISTRIBUCION_OBJETIVO.get(deporte, DISTRIBUCION_OBJETIVO['running'])
    distribucion_plan = {}
    for sport in ['running', 'cycling', 'swimming']:
        actual = distribucion_actual.get(sport, 0)
        target = objetivo.get(sport, 0)
        delta = target - actual
        # Limitar cambio a MAX_CAMBIO_POR_MESO
        if abs(delta) > MAX_CAMBIO_POR_MESO:
            delta = MAX_CAMBIO_POR_MESO if delta > 0 else -MAX_CAMBIO_POR_MESO
        distribucion_plan[sport] = round(actual + delta, 3)

    # Normalizar para que sume 1.0
    total_plan = sum(distribucion_plan.values()) or 1
    distribucion_plan = {k: round(v / total_plan, 3) for k, v in distribucion_plan.items()}

    # ══════════════════════════════════════════════════════════════
    # 2. DURACION TIPICA POR DEPORTE Y TIPO
    # ══════════════════════════════════════════════════════════════
    duraciones = defaultdict(lambda: defaultdict(list))

    for s in sesiones:
        sport = _normalizar_sport(s[2])
        dur = float(s[4] or 0)
        tss = float(s[3] or 0)
        hr = float(s[5] or 0)
        lthr = lthr_map.get(sport, 160)
        tipo = _clasificar_sesion(s[2], tss, dur, hr, lthr)
        if dur > 5:
            duraciones[sport][tipo].append(dur)

    duracion_tipica = {}
    for sport in ['running', 'cycling', 'swimming']:
        duracion_tipica[sport] = {}
        for tipo in ['easy', 'quality', 'long']:
            vals = duraciones[sport][tipo]
            if vals:
                # Mediana para ser robusta ante outliers
                vals_sorted = sorted(vals)
                mid = len(vals_sorted) // 2
                mediana = vals_sorted[mid]
                duracion_tipica[sport][tipo] = round(mediana)
            else:
                # Defaults razonables
                defaults = {
                    'running':  {'easy': 45, 'quality': 45, 'long': 75},
                    'cycling':  {'easy': 60, 'quality': 70, 'long': 150},
                    'swimming': {'easy': 35, 'quality': 40, 'long': 45},
                }
                duracion_tipica[sport][tipo] = defaults.get(sport, {}).get(tipo, 45)

    # ══════════════════════════════════════════════════════════════
    # 3. DIAS PREFERIDOS (solo para single sport)
    # ══════════════════════════════════════════════════════════════
    dias_conteo = defaultdict(lambda: defaultdict(int))

    for s in sesiones:
        sport = _normalizar_sport(s[2])
        dia = int(s[7] or 1) - 1  # ISO day: 1=lun -> 0=lun
        dias_conteo[sport][dia] += 1

    dias_preferidos = {}
    for sport in ['running', 'cycling', 'swimming']:
        conteos = dias_conteo[sport]
        if conteos:
            # Ordenar por frecuencia, tomar los mas comunes
            ordenados = sorted(conteos.items(), key=lambda x: -x[1])
            dias_preferidos[sport] = [d for d, _ in ordenados[:5]]  # top 5 dias
        else:
            dias_preferidos[sport] = []

    # ══════════════════════════════════════════════════════════════
    # 4. FRECUENCIA SEMANAL
    # ══════════════════════════════════════════════════════════════
    semanas_set = set()
    for s in sesiones:
        f = str(s[1])[:10]
        try:
            d = date.fromisoformat(f)
            semanas_set.add(d.isocalendar()[1])
        except Exception:
            pass

    n_semanas_con_datos = len(semanas_set) or 1
    sesiones_por_semana = round(len(sesiones) / n_semanas_con_datos, 1)

    # Por deporte
    ses_por_sport_semana = {}
    for sport in ['running', 'cycling', 'swimming']:
        n_sport = sum(1 for s in sesiones if _normalizar_sport(s[2]) == sport)
        ses_por_sport_semana[sport] = round(n_sport / n_semanas_con_datos, 1)

    # ══════════════════════════════════════════════════════════════
    # 5. SESIONES EFECTIVAS (cuales produjeron mejor adaptacion)
    # ══════════════════════════════════════════════════════════════
    sesiones_efectivas = []

    # Buscar sesiones donde CTL subio y no hubo caida de HRV en los 3 dias siguientes
    for i, s in enumerate(sesiones):
        ctl_pre = float(s[6] or 0) if s[6] else None
        if not ctl_pre:
            continue

        # CTL post (buscar sesion siguiente)
        if i + 1 < len(sesiones):
            ctl_post = float(sesiones[i+1][6] or 0) if sesiones[i+1][6] else None
        else:
            ctl_post = None

        if ctl_pre and ctl_post and ctl_post > ctl_pre:
            sport = _normalizar_sport(s[2])
            tss = float(s[3] or 0)
            dur = float(s[4] or 0)
            hr = float(s[5] or 0)
            lthr = lthr_map.get(sport, 160)
            tipo = _clasificar_sesion(s[2], tss, dur, hr, lthr)

            # Verificar HRV post (si hay bio)
            fecha_ses = str(s[1])[:10]
            try:
                cur.execute("""
                    SELECT AVG(hrv_rmssd) FROM sleep_hrv
                    WHERE atleta_id=%s AND fecha::date > %s::date
                    AND fecha::date <= (%s::date + INTERVAL '3 days')
                    AND hrv_rmssd > 10
                """, (atleta_id, fecha_ses, fecha_ses))
                hrv_post = cur.fetchone()
                hrv_ok = True  # default si no hay bio
                if hrv_post and hrv_post[0]:
                    # Comparar con HRV pre
                    cur.execute("""
                        SELECT AVG(hrv_rmssd) FROM sleep_hrv
                        WHERE atleta_id=%s AND fecha::date <= %s::date
                        AND fecha::date > (%s::date - INTERVAL '3 days')
                        AND hrv_rmssd > 10
                    """, (atleta_id, fecha_ses, fecha_ses))
                    hrv_pre = cur.fetchone()
                    if hrv_pre and hrv_pre[0]:
                        # Si HRV no cayo mas de 15%, la sesion fue bien absorbida
                        hrv_ok = float(hrv_post[0]) >= float(hrv_pre[0]) * 0.85
            except Exception:
                hrv_ok = True

            if hrv_ok:
                sesiones_efectivas.append({
                    'sport': sport,
                    'tipo': tipo,
                    'tss': tss,
                    'duracion': dur,
                    'delta_ctl': round(ctl_post - ctl_pre, 2),
                })

    # Resumir sesiones efectivas por sport+tipo
    efectivas_resumen = defaultdict(lambda: {'count': 0, 'dur_avg': 0, 'tss_avg': 0})
    for se in sesiones_efectivas:
        key = f"{se['sport']}_{se['tipo']}"
        r = efectivas_resumen[key]
        r['count'] += 1
        r['dur_avg'] += se['duracion']
        r['tss_avg'] += se['tss']

    for key in efectivas_resumen:
        r = efectivas_resumen[key]
        if r['count'] > 0:
            r['dur_avg'] = round(r['dur_avg'] / r['count'])
            r['tss_avg'] = round(r['tss_avg'] / r['count'])

    return {
        'deporte': deporte,
        'distribucion_actual': distribucion_actual,
        'distribucion_plan': distribucion_plan,
        'distribucion_objetivo': objetivo,
        'duracion_tipica': duracion_tipica,
        'dias_preferidos': dias_preferidos,
        'sesiones_por_semana': sesiones_por_semana,
        'ses_por_sport_semana': ses_por_sport_semana,
        'sesiones_efectivas': dict(efectivas_resumen),
        'n_semanas_analizadas': n_semanas_con_datos,
        'n_sesiones_total': len(sesiones),
    }


def _patron_default(deporte):
    """Retorna patron default cuando no hay historial."""
    objetivo = DISTRIBUCION_OBJETIVO.get(deporte, DISTRIBUCION_OBJETIVO['running'])
    return {
        'deporte': deporte,
        'distribucion_actual': objetivo,
        'distribucion_plan': objetivo,
        'distribucion_objetivo': objetivo,
        'duracion_tipica': {
            'running':  {'easy': 45, 'quality': 45, 'long': 75},
            'cycling':  {'easy': 60, 'quality': 70, 'long': 150},
            'swimming': {'easy': 35, 'quality': 40, 'long': 45},
        },
        'dias_preferidos': {},
        'sesiones_por_semana': 5,
        'ses_por_sport_semana': {},
        'sesiones_efectivas': {},
        'n_semanas_analizadas': 0,
        'n_sesiones_total': 0,
    }


def aplicar_patrones_a_tss(tss_base, patrones, fase='A'):
    """
    Distribuye el TSS semanal por deporte usando los patrones aprendidos.
    Ajusta por fase: en R baja volumen proporcional, en T sube calidad.

    Returns: {'running': tss_run, 'cycling': tss_bike, 'swimming': tss_swim}
    """
    dist = patrones.get('distribucion_plan', {})

    # Ajuste por fase
    factor_fase = {'A': 1.0, 'T': 0.95, 'R': 0.65, 'Taper': 0.55}
    factor = factor_fase.get(fase, 1.0)

    tss_ajustado = round(tss_base * factor)

    resultado = {}
    for sport in ['running', 'cycling', 'swimming']:
        pct = dist.get(sport, 0)
        resultado[sport] = round(tss_ajustado * pct)

    return resultado


def aplicar_duracion_sesion(sport, tipo, patrones, dur_override=None):
    """
    Retorna la duracion en minutos para una sesion basada en los patrones.
    Si hay dur_override (de perfil/optimizer), lo respeta pero avisa si
    difiere mucho del patron.
    """
    dur_tipica = patrones.get('duracion_tipica', {}).get(sport, {}).get(tipo, 45)

    if dur_override:
        return dur_override

    return dur_tipica
