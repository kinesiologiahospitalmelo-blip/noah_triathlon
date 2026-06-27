"""
noa_estados.py — Proyecto NOAH
==============================
Detecta el estado actual del atleta y genera el plan correspondiente.

ESTADOS:
  NORMAL      → Entrenando regularmente. Plan completo con ramp 5-7%.
  REAJUSTE    → Faltó 1-3 sesiones. Ajuste de carga dentro del plan normal.
  REINICIO_A  → 2-3 semanas sin entrenar o entrenando muy poco.
                Plan de reintroducción suave 2 semanas.
  REINICIO_B  → Más de 1 mes sin entrenar, o atleta nuevo sin historial.
                Plan progresivo 4 semanas antes de planificación normal.

BASELINE:
  Se calcula desde la DB (CTL promedio de los últimos 90 días activos).
  Si no hay historial suficiente → tablas de referencia según edad/experiencia.
"""

from __future__ import annotations
import psycopg2
import pandas as pd
import numpy as np
from datetime import date, timedelta
from dataclasses import dataclass, field
from typing import Optional

# ── Tablas de referencia TrainingPeaks / literatura ──────────────────────────
# CTL objetivo según experiencia y horas disponibles por semana
# Fuente: Coggan/Allen, TrainingPeaks guidelines
CTL_REFERENCIA = {
    # (nivel, horas_semana) → CTL objetivo
    ('principiante',  6):  35,
    ('principiante',  8):  45,
    ('principiante', 10):  55,
    ('intermedio',    6):  50,
    ('intermedio',    8):  65,
    ('intermedio',   10):  80,
    ('intermedio',   12):  90,
    ('avanzado',      8):  75,
    ('avanzado',     10):  90,
    ('avanzado',     12): 105,
    ('avanzado',     15): 120,
    ('elite',        12): 110,
    ('elite',        15): 130,
    ('elite',        20): 150,
}

TSS_SEMANA_REFERENCIA = {
    # horas_semana → TSS semanal típico
    4:   150,
    6:   220,
    8:   300,
    10:  380,
    12:  450,
    15:  550,
    20:  700,
}


@dataclass
class EstadoAtleta:
    atleta_id:       int
    nombre:          str
    deporte:         str
    ctl_actual:      float
    ctl_baseline:    float       # CTL promedio 90 días activos
    ctl_peak:        float       # CTL máximo histórico
    dias_sin_entreno: int
    sesiones_ultima_semana: int
    sesiones_ultimas_2sem:  int
    drop_pct:        float       # % caída desde baseline
    estado:          str         # NORMAL | REAJUSTE | REINICIO_A | REINICIO_B
    semana_reinicio: int = 1     # Semana actual dentro del plan de reinicio
    notas:           list = field(default_factory=list)


def calcular_ctl_serie(conn, atleta_id: int) -> pd.DataFrame:
    """Retorna serie diaria de CTL para el atleta."""
    df = pd.read_sql("""
        SELECT fecha, SUM(tss_total) as tss
        FROM sesiones WHERE atleta_id=%s
        AND sport NOT IN ('swim', 'strength', 'other', 'hiit', 'multisport')
        AND tss_total IS NOT NULL AND tss_total > 0
        GROUP BY fecha ORDER BY fecha
    """, conn, params=[atleta_id])

    if len(df) == 0:
        return pd.DataFrame(columns=['fecha', 'tss', 'ctl'])

    df['fecha'] = pd.to_datetime(df['fecha'])
    idx = pd.date_range(df['fecha'].min(), df['fecha'].max(), freq='D')
    df = df.set_index('fecha').reindex(idx, fill_value=0).reset_index()
    df.columns = ['fecha', 'tss']
    df['tss'] = pd.to_numeric(df['tss'], errors='coerce').fillna(0)

    a = 2 / 43
    ctl = np.zeros(len(df))
    for i in range(len(df)):
        t = float(df.iloc[i]['tss'])
        ctl[i] = t if i == 0 else ctl[i-1] * (1 - a) + t * a
    df['ctl'] = ctl
    return df


def get_baseline_referencia(atleta: dict) -> float:
    """
    CTL de referencia desde tablas cuando no hay historial suficiente.
    Usa nivel, horas disponibles y edad del atleta.
    """
    nivel = atleta.get('nivel_experiencia', 'intermedio') or 'intermedio'
    horas = atleta.get('horas_semana', 8) or 8
    edad  = atleta.get('edad', 35) or 35

    # Buscar el más cercano en la tabla
    opciones = [(abs(h - horas), ctl)
                for (niv, h), ctl in CTL_REFERENCIA.items()
                if niv == nivel]

    if opciones:
        ctl_ref = sorted(opciones)[0][1]
    else:
        # Fallback: horas × 37 (TSS/semana estimado / 7)
        ctl_ref = horas * 37 / 7

    # Ajuste por edad: >45 años reducir 8%, >55 reducir 15%
    if edad > 55:
        ctl_ref *= 0.85
    elif edad > 45:
        ctl_ref *= 0.92

    return round(ctl_ref, 1)


def detectar_estado(conn, atleta: dict,
                    ctl_override: float = None,
                    atl_override: float = None,
                    tsb_override: float = None) -> EstadoAtleta:
    """
    Analiza la DB y detecta el estado actual del atleta.
    ctl_override: CTL ya calculado externamente — evita doble cálculo.
    """
    atleta_id = atleta['id']
    hoy = date.today()

    # Serie CTL histórica
    df_ctl = calcular_ctl_serie(conn, atleta_id)

    # Si hay CTL precalculado, usarlo directamente
    if ctl_override is not None and len(df_ctl) >= 14:
        ctl_actual = float(ctl_override)
    elif len(df_ctl) < 14:
        # Sin historial → REINICIO_B con baseline de referencia
        return EstadoAtleta(
            atleta_id=atleta_id,
            nombre=atleta.get('nombre', ''),
            deporte=atleta.get('deporte_ppal', 'running'),
            ctl_actual=0.0,
            ctl_baseline=get_baseline_referencia(atleta),
            ctl_peak=0.0,
            dias_sin_entreno=999,
            sesiones_ultima_semana=0,
            sesiones_ultimas_2sem=0,
            drop_pct=100.0,
            estado='REINICIO_B',
            semana_reinicio=1,
            notas=['Sin historial suficiente — plan de inicio desde cero'],
        )

    if ctl_override is not None:
        ctl_actual = float(ctl_override)
    else:
        ctl_actual = float(df_ctl['ctl'].iloc[-1])
    ctl_peak   = float(df_ctl['ctl'].max())

    # Baseline: promedio CTL de los últimos 42 días activos (6 semanas — bibliografía)
    # 42 días refleja la forma reciente real, no un pico lejano de hace meses
    fecha_42d = pd.Timestamp(hoy - timedelta(days=42))
    df_42 = df_ctl[df_ctl['fecha'] >= fecha_42d]
    activos_42 = df_42[df_42['ctl'] > 10]['ctl']
    if len(activos_42) >= 10:
        ctl_baseline = float(activos_42.mean())
    elif len(df_ctl[df_ctl['ctl'] > 10]) >= 14:
        # Usar todo el historial si los 42d no alcanzan
        ctl_baseline = float(df_ctl[df_ctl['ctl'] > 10]['ctl'].mean())
    else:
        ctl_baseline = get_baseline_referencia(atleta)

    # Último entrenamiento REAL (excluir sesiones de prescripción/simulación)
    df_ses = pd.read_sql("""
        SELECT fecha FROM sesiones
        WHERE atleta_id=%s AND tss_total > 0
        AND (fuente IS NULL OR fuente NOT IN ('prescripcion','simulacion','generada'))
        ORDER BY fecha DESC LIMIT 1
    """, conn, params=[atleta_id])

    if len(df_ses) > 0:
        ultimo = pd.to_datetime(df_ses.iloc[0]['fecha']).date()
        dias_sin = (hoy - ultimo).days
    else:
        dias_sin = 999

    # Sesiones recientes
    fecha_1sem = str(hoy - timedelta(days=7))
    fecha_2sem = str(hoy - timedelta(days=14))

    ses_1sem = conn.execute("""
        SELECT COUNT(DISTINCT fecha) FROM sesiones
        WHERE atleta_id=%s AND fecha >= %s AND tss_total > 0
    """, (atleta_id, fecha_1sem)).fetchone()[0]

    ses_2sem = conn.execute("""
        SELECT COUNT(DISTINCT fecha) FROM sesiones
        WHERE atleta_id=%s AND fecha >= %s AND tss_total > 0
    """, (atleta_id, fecha_2sem)).fetchone()[0]

    # Drop % desde baseline
    drop_pct = ((ctl_baseline - ctl_actual) / ctl_baseline * 100) if ctl_baseline > 0 else 100

    # ── Detectar semana de reinicio actual ────────────────────────────────────
    semana_reinicio = _detectar_semana_reinicio(conn, atleta_id, dias_sin)

    # ── Clasificar estado ─────────────────────────────────────────────────────
    notas = []

    if dias_sin <= 14:
        # Atleta entrenando regularmente (máx 2 semanas de pausa)
        # SIEMPRE plan NORMAL — el drop se maneja con carga ajustada
        # El CTL bajo lo compensa el ajuste adaptativo de noah_nivel_carga
        estado = 'NORMAL'
        if drop_pct >= 15:
            notas.append(f'Drop {drop_pct:.0f}% desde baseline 42d — carga ajustada por CTL actual.')
        elif dias_sin > 5:
            notas.append(f'{dias_sin} días sin entrenar — retomando gradualmente.')

    elif dias_sin <= 28:
        # 2-4 semanas sin entrenar → reintroducción suave
        estado = 'REINICIO_A'
        notas.append(f'{dias_sin} días sin entrenar. Reintroducción suave 2 semanas.')
        notas.append(f'CTL {ctl_actual:.0f} → objetivo recuperar {ctl_baseline:.0f} en ~4 semanas.')

    elif dias_sin <= 56 or (drop_pct >= 40 and drop_pct < 80):
        # 4-8 semanas sin entrenar o caída severa
        estado = 'REINICIO_B'
        notas.append(f'{dias_sin} días sin entrenar (drop {drop_pct:.0f}%).')
        notas.append(f'Plan progresivo 4 semanas antes de retomar planificación normal.')

    else:
        # Más de 8 semanas o atleta nuevo
        estado = 'REINICIO_B'
        notas.append(f'{dias_sin} días sin entrenar (drop {drop_pct:.0f}%).')
        notas.append(f'Plan progresivo 4 semanas antes de retomar planificación normal.')

    return EstadoAtleta(
        atleta_id=atleta_id,
        nombre=atleta.get('nombre', ''),
        deporte=atleta.get('deporte_ppal', 'running'),
        ctl_actual=round(ctl_actual, 1),
        ctl_baseline=round(ctl_baseline, 1),
        ctl_peak=round(ctl_peak, 1),
        dias_sin_entreno=dias_sin,
        sesiones_ultima_semana=ses_1sem,
        sesiones_ultimas_2sem=ses_2sem,
        drop_pct=round(drop_pct, 1),
        estado=estado,
        semana_reinicio=semana_reinicio,
        notas=notas,
    )


def _detectar_semana_reinicio(conn,
                               atleta_id: int, dias_sin: int) -> int:
    """
    Detecta en qué semana del plan de reinicio está el atleta.
    Busca en prescripciones si ya tiene un plan de reinicio activo.
    """
    # Asegurar que la columna existe — PRAGMA table_info (SQLite)
    # reemplazado por el helper compartido.
    try:
        from db_compat import asegurar_columnas
        asegurar_columnas(conn, 'prescripciones', [('semana_reinicio', 'INTEGER DEFAULT 1')])
        conn.commit()
    except Exception:
        pass

    try:
        row = conn.execute("""
            SELECT semana_reinicio FROM prescripciones
            WHERE atleta_id=%s AND estado IN ('pendiente','reinicio')
            ORDER BY fecha_generada DESC LIMIT 1
        """, (atleta_id,)).fetchone()
        if row and row[0]:
            return int(row[0]) + 1
    except Exception:
        pass

    return 1  # primera semana


# ── Generadores de planes de reinicio ────────────────────────────────────────

def plan_reajuste(estado_atleta: EstadoAtleta, atleta_cfg: dict,
                   perfil: dict, fechas: list) -> tuple:
    """
    REAJUSTE: atleta que faltó 1-3 sesiones.
    Sesiones de calidad normal pero volumen reducido 10-15%.
    Sin sesiones dobles. Ramp conservador.
    """
    # Usar plan_reinicio_a semana 2 como base (un poco más de volumen que semana 1)
    # pero con ramp_rate al 3%
    sesiones = plan_reinicio_a(estado_atleta, atleta_cfg, perfil, fechas, semana=2)
    return sesiones, 'REAJUSTE', 'REAJUSTE' 


def _hacer_sesion_run(nombre, dur, lthr, pace_z2, fecha, semana, fase='F1'):
    """Crea una sesión de running suave para reinicio."""
    from patrones_sesion import Sesion, Bloque
    hr_z1_min = round(lthr * 0.72)
    hr_z1_max = round(lthr * 0.78)
    hr_z2_min = round(lthr * 0.82)
    hr_z2_max = round(lthr * 0.88)
    tss = round(0.82**2 * (dur/60) * 100)
    return Sesion(
        nombre=nombre, tipo=1, fase=fase, fecha=fecha, sport='running',
        bloques=[
            Bloque(zona='Z1', nombre='Entrada en calor', duracion_min=8,
                   hr_min=hr_z1_min, hr_max=hr_z1_max, pace_ref=pace_z2*1.1, sport='running'),
            Bloque(zona='Z2', nombre='Endurance Z2', duracion_min=dur-13,
                   hr_min=hr_z2_min, hr_max=hr_z2_max, pace_ref=pace_z2, sport='running',
                   descripcion=f'Ritmo conversacional. {pace_z2:.2f} min/km. Sin acelerar.'),
            Bloque(zona='Z1', nombre='Vuelta a la calma', duracion_min=5,
                   hr_min=round(lthr*0.70), hr_max=round(lthr*0.76),
                   pace_ref=pace_z2*1.15, sport='running'),
        ],
        tss_estimado=tss,
    )


def _hacer_sesion_bike(nombre, dur, lthr_bike, ftp, fecha, fase='F1'):
    """Crea una sesión de ciclismo suave para reinicio."""
    from patrones_sesion import Sesion, Bloque
    hr_bz2_min = round(lthr_bike * 0.76)
    hr_bz2_max = round(lthr_bike * 0.84)
    w_min = round(ftp * 0.60) if ftp else None
    w_max = round(ftp * 0.72) if ftp else None
    tss = round(0.76**2 * (dur/60) * 100)
    b = Bloque.__new__(Bloque)
    b.zona = 'BZ2'; b.nombre = 'Endurance aeróbico'; b.duracion_min = dur
    b.hr_min = hr_bz2_min; b.hr_max = hr_bz2_max; b.pace_ref = None
    b.repeticiones = 1; b.pausa_min = 0.0; b.pausa_activa = True
    b.descripcion = 'Pedaleo cómodo. Cadencia 85-90 rpm. Sin esfuerzo.'
    b.sport = 'cycling'; b.watts_min = w_min; b.watts_max = w_max
    return Sesion(nombre=nombre, tipo=1, fase=fase, fecha=fecha,
                  sport='cycling', bloques=[b], tss_estimado=tss)


def _hacer_sesion_swim(nombre, dist_m, css, lthr_swim, fecha, fase='F1'):
    """Crea una sesión de natación suave para reinicio."""
    from patrones_sesion import Sesion, Bloque
    hr_sz2_min = round(lthr_swim * 0.80)
    hr_sz2_max = round(lthr_swim * 0.88)
    dur = round((dist_m / 100) * css * 1.1)
    tss = round(0.80**2 * (dur/60) * 100)
    b = Bloque.__new__(Bloque)
    b.zona = 'Z2'; b.nombre = f'Endurance {dist_m}m'; b.duracion_min = dur
    b.hr_min = hr_sz2_min; b.hr_max = hr_sz2_max; b.pace_ref = None
    b.repeticiones = 1; b.pausa_min = 0.0; b.pausa_activa = True
    b.descripcion = f'{dist_m}m continuos. Sin series. Técnica y respiración.'
    b.sport = 'swimming'; b.watts_min = None; b.watts_max = None
    return Sesion(nombre=nombre, tipo=1, fase=fase, fecha=fecha,
                  sport='swimming', bloques=[b], tss_estimado=tss)


def plan_reinicio_a(estado_atleta: EstadoAtleta, atleta_cfg: dict,
                     perfil: dict, fechas: list, semana: int = 1) -> list:
    """
    REINICIO A: 2-3 semanas sin entrenar.
    Semana 1: Run 35min, Bike 45min, Swim 1000m, Bike 50min, Run 35min
    Semana 2: Run 40min, Bike 50min, Swim 1500m, Bike 60min, Run 40min
    Sin dobles turnos. Sin calidad. Zonas ya ajustadas por ctl en atleta_cfg.
    """
    lthr      = atleta_cfg.get('lthr', 162)
    lthr_bike = atleta_cfg.get('lthr_bike', 150)
    lthr_swim = atleta_cfg.get('lthr_swim', round(lthr * 0.92))
    ftp       = atleta_cfg.get('ftp', 180)
    css       = atleta_cfg.get('css_100m', 1.75)
    pace_z2   = atleta_cfg.get('pace_z2_real', 6.0)
    deporte   = estado_atleta.deporte
    fase      = perfil.get('fase_actual', 'F1')

    dur_run  = 35 if semana == 1 else 40
    dur_bk1  = 45 if semana == 1 else 50
    dur_bk2  = 50 if semana == 1 else 60
    dist_sw  = 1000 if semana == 1 else 1500

    sesiones = []
    f = fechas

    if deporte in ('running', 'duatlon', 'triatlon'):
        sesiones.append(_hacer_sesion_run(
            f'Run Reinicio S{semana} — Endurance {dur_run}\'',
            dur_run, lthr, pace_z2, f[0], semana, fase))

    if deporte in ('cycling', 'duatlon', 'triatlon'):
        sesiones.append(_hacer_sesion_bike(
            f'Bike Reinicio S{semana} — Endurance {dur_bk1}\'',
            dur_bk1, lthr_bike, ftp, f[1] if len(f)>1 else f[0], fase))

    if deporte in ('swimming', 'triatlon'):
        sesiones.append(_hacer_sesion_swim(
            f'Swim Reinicio S{semana} — {dist_sw}m',
            dist_sw, css, lthr_swim, f[2] if len(f)>2 else f[0], fase))

    if deporte in ('cycling', 'duatlon', 'triatlon'):
        sesiones.append(_hacer_sesion_bike(
            f'Bike Reinicio S{semana} — Endurance {dur_bk2}\'',
            dur_bk2, lthr_bike, ftp, f[3] if len(f)>3 else f[1], fase))

    if deporte in ('running', 'duatlon', 'triatlon'):
        sesiones.append(_hacer_sesion_run(
            f'Run Reinicio S{semana} — Endurance {dur_run}\'',
            dur_run, lthr, pace_z2, f[4] if len(f)>4 else f[2], semana, fase))

    # SÁB: Bike largo suave (si es triatleta o ciclista)
    if deporte in ('cycling', 'duatlon', 'triatlon'):
        dur_bk_sab = 60 if semana == 1 else 75
        sesiones.append(_hacer_sesion_bike(
            f'Bike Reinicio S{semana} — Endurance largo {dur_bk_sab}\'',
            dur_bk_sab, lthr_bike, ftp, f[5] if len(f)>5 else f[1], fase))

    # DOM: Run largo suave
    if deporte in ('running', 'duatlon', 'triatlon'):
        dur_run_dom = 45 if semana == 1 else 55
        sesiones.append(_hacer_sesion_run(
            f'Run Reinicio S{semana} — Fondo largo {dur_run_dom}\'',
            dur_run_dom, lthr, pace_z2, f[6] if len(f)>6 else f[2], semana, fase))

    return sesiones


from patrones_sesion import Sesion, Bloque, sesion_1_rec, sesion_3


def plan_reinicio_b(estado_atleta: EstadoAtleta, atleta_cfg: dict,
                     perfil: dict, fechas: list, semana: int = 1) -> list:
    """
    REINICIO B: más de 1 mes sin entrenar o atleta nuevo.

    Semana 1: 2run + 2swim + 2bike (sin calidad)
    Semana 2: 3run + 2swim + 2bike (intro a ritmo Z2 real)
    Semana 3: 3run + 2swim + 3bike (subida gradual)
    Semana 4: → planificación normal
    """
    if semana >= 4:
        # Semana 4 en adelante: planificación normal
        return None  # señal para usar plan normal

    # Semanas 1-3: usar plan_reinicio_a con progresión
    # La diferencia es el número de sesiones y si hay algo de calidad
    sesiones_base = plan_reinicio_a(estado_atleta, atleta_cfg, perfil, fechas, semana)

    if semana == 1:
        # Solo 2 run + 2 bike + 2 swim = 6 sesiones
        return sesiones_base

    elif semana == 2:
        # 3 run + 2 bike + 2 swim — agregar run extra liviano
        lthr    = atleta_cfg.get('lthr', 162)
        pace_z2 = atleta_cfg.get('pace_z2_real', 5.85)
        run_extra = Sesion(
            nombre='Run Reinicio — Recuperación activa 30\'',
            tipo='run_regen', fase='A',
            sport='running',
            fecha=fechas[5] if len(fechas) > 5 else fechas[-1],
            bloques=[
                Bloque(zona='Z1',nombre='Trote muy suave',duracion_min=30,
                       hr_min=round(lthr*0.70),hr_max=round(lthr*0.78),
                       pace_ref=pace_z2*1.12, sport='running',
                       descripcion='Muy suave. Si hay molestias, cortar.'),
            ],
            tss_estimado=round(0.74**2 * 0.5 * 100),
        )
        sesiones_base.append(run_extra)
        return sesiones_base

    elif semana == 3:
        # 3 run + 2 swim + 3 bike — agregar bike extra
        lthr_bike = atleta_cfg.get('lthr_bike', 150)
        ftp       = atleta_cfg.get('ftp')
        bike_extra = Sesion(
            nombre='Bike Reinicio — Endurance 60\'',
            tipo='bike_regen', fase='A',
            sport='cycling',
            fecha=fechas[5] if len(fechas) > 5 else fechas[-1],
            bloques=[
                Bloque('BZ2','Endurance largo',60,1,
                       hr_min=round(lthr_bike*0.76),hr_max=round(lthr_bike*0.84),
                       pace_ref=None,
                       watts_min=round(ftp*0.65) if ftp else None,
                       watts_max=round(ftp*0.75) if ftp else None,
                       descripcion='60\' continuos. Primera sesión larga de vuelta.'),
            ],
            tss_estimado=round(0.76**2 * 1.0 * 100),
        )
        sesiones_base.append(bike_extra)
        return sesiones_base



def ajustar_zonas_por_ctl(atleta_cfg: dict, ctl_actual: float,
                            ctl_baseline: float) -> dict:
    """
    Ajusta ritmos y watts según el nivel de fitness actual vs baseline.

    Cuando el CTL baja, el atleta no puede sostener los mismos ritmos/watts
    que en su estado óptimo. Los ritmos se hacen más lentos y los watts bajan.

    Factor de ajuste: sqrt(CTL_actual / CTL_baseline)
    Usando sqrt porque la relación potencia-velocidad no es lineal.

    Ejemplo:
      CTL actual=15, baseline=40 → factor=sqrt(15/40)=0.61
      Pace Z2 de 5:30 → ajustado a 5:30 / 0.61 = 9:01 min/km (muy suave)

    En la práctica se limita el ajuste a máximo 20% más lento/menos watts.
    """
    if ctl_baseline <= 0 or ctl_actual >= ctl_baseline:
        return atleta_cfg  # sin ajuste necesario

    ratio = ctl_actual / ctl_baseline
    # Factor de ajuste: entre 0.80 y 1.0 (max 20% de degradación)
    factor = max(0.80, min(1.0, ratio ** 0.5))

    cfg_ajustado = dict(atleta_cfg)

    # Ajustar pace Z2 (pace más lento = número más alto)
    if atleta_cfg.get('pace_z2_real'):
        pace_original = atleta_cfg['pace_z2_real']
        # Si factor=0.85 → pace 15% más lento → pace_ajustado = pace / 0.85
        cfg_ajustado['pace_z2_real'] = round(pace_original / factor, 3)

    # Ajustar FTP (watts bajan con el fitness)
    if atleta_cfg.get('ftp'):
        cfg_ajustado['ftp'] = round(atleta_cfg['ftp'] * factor)

    # Ajustar CSS natación (más lento)
    if atleta_cfg.get('css_100m'):
        cfg_ajustado['css_100m'] = round(atleta_cfg['css_100m'] / factor, 3)

    pct_ajuste = round((1 - factor) * 100, 1)
    if pct_ajuste > 2:
        print(f'  [ZONAS] Ajuste por desentrenamiento: -{pct_ajuste}% '
              f'(CTL {ctl_actual:.0f}/{ctl_baseline:.0f})')
        print(f'  [ZONAS] Pace Z2: {atleta_cfg.get("pace_z2_real",0):.2f} → '
              f'{cfg_ajustado.get("pace_z2_real",0):.2f} min/km')
        if atleta_cfg.get('ftp'):
            print(f'  [ZONAS] FTP: {atleta_cfg["ftp"]}W → {cfg_ajustado["ftp"]}W')

    return cfg_ajustado

def get_plan_semana(conn, atleta: dict,
                    atleta_cfg: dict, perfil: dict,
                    fechas: list, tss_manual: int = None,
                    ctl_override: float = None,
                    atl_override: float = None,
                    tsb_override: float = None) -> tuple:
    """
    Punto de entrada principal. Detecta el estado y retorna el plan correcto.

    ctl_override: si se pasa, usa este CTL en lugar de recalcular desde DB.
    Returns:
        (sesiones, estado_atleta, tipo_plan)
    """
    ea = detectar_estado(conn, atleta, ctl_override=ctl_override,
                         atl_override=atl_override, tsb_override=tsb_override)

    # Override manual del coach
    if tss_manual:
        atleta_cfg['tss_manual'] = tss_manual

    # Ajustar ritmos/watts según fitness actual
    if ea.estado != 'NORMAL':
        atleta_cfg = ajustar_zonas_por_ctl(atleta_cfg, ea.ctl_actual, ea.ctl_baseline)

    if ea.estado == 'NORMAL':
        from patrones_sesion import generar_semana_completa, generar_semana_triatleta
        estado_p = _build_estado_p(ea, atleta_cfg, perfil, tss_manual)
        if ea.deporte == 'triatlon' and len(fechas) >= 9:
            sesiones, tipo, _ = generar_semana_triatleta(atleta_cfg, estado_p, perfil, 1, fechas)
        else:
            # Runner/ciclista/nadador: siempre 3 fechas (LUN FTP / MIÉ VO2 / SÁB Long)
            sesiones, tipo, _ = generar_semana_completa(atleta_cfg, estado_p, perfil, 1, fechas[:3])
        return sesiones, ea, 'NORMAL'

    elif ea.estado == 'REAJUSTE':
        sesiones, _, _ = plan_reajuste(ea, atleta_cfg, perfil, fechas)
        return sesiones, ea, 'REAJUSTE'

    elif ea.estado == 'REINICIO_A':
        # Pasar fechas de toda la semana (lun a dom)
        lun = fechas[0] if fechas else date.today()
        fechas_semana = [lun + timedelta(days=i) for i in range(7)]
        sesiones = plan_reinicio_a(ea, atleta_cfg, perfil, fechas_semana, ea.semana_reinicio)
        return sesiones, ea, f'REINICIO_A_S{ea.semana_reinicio}'

    elif ea.estado == 'REINICIO_B':
        if ea.semana_reinicio >= 4:
            # Semana 4: volver a normal
            from patrones_sesion import generar_semana_completa, generar_semana_triatleta
            estado_p = _build_estado_p(ea, atleta_cfg, perfil, tss_manual)
            if ea.deporte == 'triatlon' and len(fechas) >= 9:
                sesiones, _, _ = generar_semana_triatleta(atleta_cfg, estado_p, perfil, 1, fechas)
            else:
                sesiones, _, _ = generar_semana_completa(atleta_cfg, estado_p, perfil, 1, fechas)
            return sesiones, ea, 'NORMAL'
        else:
            lun = fechas[0] if fechas else date.today()
            fechas_semana = [lun + timedelta(days=i) for i in range(7)]
            sesiones = plan_reinicio_b(ea, atleta_cfg, perfil, fechas_semana, ea.semana_reinicio)
            if sesiones is None:
                # Señal para usar plan normal
                from patrones_sesion import generar_semana_completa, generar_semana_triatleta
                estado_p = _build_estado_p(ea, atleta_cfg, perfil, tss_manual)
                if ea.deporte == 'triatlon' and len(fechas) >= 9:
                    sesiones, _, _ = generar_semana_triatleta(atleta_cfg, estado_p, perfil, 1, fechas)
                else:
                    sesiones, _, _ = generar_semana_completa(atleta_cfg, estado_p, perfil, 1, fechas[:3])
            return sesiones, ea, f'REINICIO_B_S{ea.semana_reinicio}'

    # Fallback
    return [], ea, 'DESCONOCIDO'


def _build_estado_p(ea: EstadoAtleta, atleta_cfg: dict,
                     perfil: dict, tss_manual: int = None) -> dict:
    return {
        'fase'          : perfil.get('fase_actual', 'F1'),
        'hrv_flag'      : atleta_cfg.get('hrv_flag', 'amarillo'),
        'ctl'           : ea.ctl_actual,
        'atl'           : atleta_cfg.get('atl', 0),
        'tsb'           : atleta_cfg.get('tsb', 0),
        'hrv_tendencia' : 'buena',
        'sleep_promedio': atleta_cfg.get('sleep_h', 7.0),
        'ramp_rate'     : 1.05,
        'tss_manual'    : tss_manual,
    }


def imprimir_estado(ea: EstadoAtleta):
    icons = {
        'NORMAL':     '✓',
        'REAJUSTE':   '~',
        'REINICIO_A': '↑',
        'REINICIO_B': '↑↑',
    }
    print(f'\n  ESTADO NOA: {icons.get(ea.estado,"")} {ea.estado}')
    print(f'  CTL actual:   {ea.ctl_actual:.1f}  |  Baseline 90d: {ea.ctl_baseline:.1f}  |  Peak: {ea.ctl_peak:.1f}')
    print(f'  Drop:         {ea.drop_pct:.0f}%  |  Días sin entrenar: {ea.dias_sin_entreno}')
    if ea.estado != 'NORMAL':
        print(f'  Semana del plan: {ea.semana_reinicio}')
    for nota in ea.notas:
        print(f'  → {nota}')
