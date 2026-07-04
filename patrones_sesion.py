"""
patrones_sesion.py  v3
----------------------
Construye la estructura interna de cada sesion de entrenamiento.
Soporta: RUNNING, CYCLING, SWIMMING y combinaciones (TRIATLON).

ESTRUCTURA SEMANAL TRIATLETA:
  LUN  → Swim larga
  MAR  → Bike
  MIE  → Run + Swim
  JUE  → Bike
  VIE  → Run + Swim
  SAB  → Bike larga
  DOM  → Run larga

DISCIPLINAS INDIVIDUALES:
  Runner / Ciclista / Nadador → NOA decide distribucion

TAXONOMIA DE ZONAS (San Millan, Friel, Seiler, Coggan):
  Z1  Regenerativo          < 75% LTHR   Lactato < 1 mmol
  Z2  Endurance/Sub-umbral  75-87% LTHR  Lactato 1-2 mmol
  Z3  Umbral aerobico/Tempo 87-93% LTHR  Lactato 2-4 mmol
  Z4  VO2max/Umbral anaer.  93-100% LTHR Lactato 4-8 mmol
  Z5  VO2max puro           100-106% LTHR Lactato 8-12 mmol
  Z6  Neuromuscular/Sprint  >106% LTHR   Lactato >12 mmol
"""
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import date, timedelta

# ─── TAXONOMIA DE ZONAS ───────────────────────────────────────────────────────
ZONAS = {
    'Z1'  : {
        'nombre'     : 'Recuperación activa',
        'referencia' : 'Allen & Coggan / Seiler Zone 1',
        'lthr_min'   : 0.68, 'lthr_max': 0.75,
        'if_factor'  : 0.71,
        'lactato'    : '< 1 mmol',
        'vo2_pct'    : '< 55%',
        'descripcion': 'Muy suave. Favorece la recuperación sin estrés fisiológico.',
    },
    'Z1-Z2': {
        'nombre'     : 'Recuperación / Endurance suave',
        'referencia' : 'Zona de transición',
        'lthr_min'   : 0.72, 'lthr_max': 0.87,
        'if_factor'  : 0.82,
        'lactato'    : '1-2 mmol',
        'vo2_pct'    : '55-70%',
        'descripcion': 'Fondos largos. Sostenible por horas.',
    },
    'Z2'  : {
        'nombre'     : 'Resistencia aeróbica (Endurance)',
        'referencia' : 'San Millán Zone 2 / Friel Aerobic Endurance',
        'lthr_min'   : 0.75, 'lthr_max': 0.87,
        'if_factor'  : 0.83,
        'lactato'    : '1-2 mmol',
        'vo2_pct'    : '55-75%',
        'descripcion': 'La zona más importante para resistencia. Base mitocondrial.',
    },
    'Z3'  : {
        'nombre'     : 'Tempo / Umbral aeróbico',
        'referencia' : 'Friel Tempo / Maffetone Aerobic Threshold',
        'lthr_min'   : 0.87, 'lthr_max': 0.93,
        'if_factor'  : 0.90,
        'lactato'    : '2-4 mmol',
        'vo2_pct'    : '75-85%',
        'descripcion': 'Ritmo de larga distancia. Podés hablar con esfuerzo.',
    },
    'Z3-Z4': {
        'nombre'     : 'Tempo / Sub-umbral de lactato',
        'referencia' : 'Zona de transición umbral',
        'lthr_min'   : 0.90, 'lthr_max': 1.00,
        'if_factor'  : 0.95,
        'lactato'    : '3-6 mmol',
        'vo2_pct'    : '82-92%',
        'descripcion': 'Entre tempo y umbral de lactato.',
    },
    'Z4'  : {
        'nombre'     : 'Umbral de lactato / FTP',
        'referencia' : 'Friel Lactate Threshold / Allen-Coggan FTP Zone',
        'lthr_min'   : 0.93, 'lthr_max': 1.00,
        'if_factor'  : 0.96,
        'lactato'    : '4-8 mmol',
        'vo2_pct'    : '85-95%',
        'descripcion': 'Ritmo máximo sostenible ~60 min. Mejora el umbral anaeróbico.',
    },
    'Z5'  : {
        'nombre'     : 'VO2max',
        'referencia' : 'Seiler VO2max intervals / Billat / Coggan MAP',
        'lthr_min'   : 1.00, 'lthr_max': 1.06,
        'if_factor'  : 1.02,
        'lactato'    : '8-12 mmol',
        'vo2_pct'    : '95-100%',
        'descripcion': 'Intervalos de alta intensidad. Eleva el techo aeróbico.',
    },
    'Z6'  : {
        'nombre'     : 'Capacidad anaeróbica / Neuromuscular',
        'referencia' : 'Friel Anaerobic Capacity / Coggan Neuromuscular Power',
        'lthr_min'   : 1.06, 'lthr_max': 1.20,
        'if_factor'  : 1.10,
        'lactato'    : '> 12 mmol',
        'vo2_pct'    : '> 100%',
        'descripcion': 'Sprints y aceleraciones. Potencia pico.',
    },
}

# Zonas de potencia para ciclismo (Coggan)
ZONAS_BIKE = {
    'BZ1': {'nombre': 'Recuperación activa',   'ftp_min': 0.00, 'ftp_max': 0.55, 'if_factor': 0.50},
    'BZ2': {'nombre': 'Resistencia aeróbica',  'ftp_min': 0.55, 'ftp_max': 0.75, 'if_factor': 0.65},
    'BZ3': {'nombre': 'Tempo',                 'ftp_min': 0.75, 'ftp_max': 0.90, 'if_factor': 0.83},
    'BZ4': {'nombre': 'Umbral de lactato',     'ftp_min': 0.90, 'ftp_max': 1.05, 'if_factor': 0.97},
    'BZ5': {'nombre': 'VO2max',               'ftp_min': 1.05, 'ftp_max': 1.20, 'if_factor': 1.12},
    'BZ6': {'nombre': 'Capacidad anaeróbica',  'ftp_min': 1.20, 'ftp_max': 1.50, 'if_factor': 1.35},
    'BZ7': {'nombre': 'Neuromuscular',         'ftp_min': 1.50, 'ftp_max': 9.99, 'if_factor': 1.80},
}

PACE_FACTOR = {
    'Z1':1.18,'Z1-Z2':1.06,'Z2':1.00,'Z3':0.92,
    'Z3-Z4':0.86,'Z4':0.82,'Z5':0.74,'Z6':0.65,
}


# ─── DATACLASSES ──────────────────────────────────────────────────────────────

@dataclass
class Bloque:
    nombre      : str
    zona        : str
    duracion_min: float
    hr_min      : int
    hr_max      : int
    pace_ref    : float
    repeticiones: int = 1
    pausa_min   : float = 0.0
    pausa_activa: bool = True
    descripcion : str = ''
    sport       : str = 'running'  # running / cycling / swimming
    watts_min   : Optional[int] = None
    watts_max   : Optional[int] = None

    def duracion_total(self):
        return self.duracion_min*self.repeticiones + self.pausa_min*max(0,self.repeticiones-1)

    def fmt(self, v):
        return f'{int(v*60)}"' if v < 1 else f'{v:.0f}\''

    def __str__(self):
        dur = self.fmt(self.duracion_min)
        zona_nombre = ZONAS.get(self.zona, ZONAS_BIKE.get(self.zona, {})).get('nombre', self.zona)
        pace_str = ''
        if self.sport == 'running' and self.pace_ref:
            pm = int(self.pace_ref); ps = int((self.pace_ref-pm)*60)
            pace_str = f'  ~{pm}:{ps:02d} min/km'
        elif self.sport == 'cycling' and self.watts_min:
            pace_str = f'  {self.watts_min}-{self.watts_max}W'
        elif self.sport == 'swimming' and self.pace_ref:
            pm = int(self.pace_ref); ps = int((self.pace_ref-pm)*60)
            pace_str = f'  ~{pm}:{ps:02d}/100m'
        hr_str = f'  HR {self.hr_min}-{self.hr_max}' if self.hr_min else ''
        if self.repeticiones > 1:
            pau = self.fmt(self.pausa_min)
            tip = 'activa' if self.pausa_activa else 'pasiva'
            return f'{self.repeticiones}×{dur} {self.zona} — {zona_nombre}{hr_str}{pace_str}  / {pau} pausa {tip}'
        return f'{dur} {self.zona} — {zona_nombre}{hr_str}{pace_str}'


@dataclass
class Sesion:
    nombre      : str
    tipo        : int
    fase        : str
    fecha       : date
    sport       : str = 'running'
    bloques     : List[Bloque] = field(default_factory=list)
    tss_estimado: float = 0.0
    descripcion : str = ''

    def duracion_total(self):
        return sum(b.duracion_total() for b in self.bloques)

    def distancia_estimada(self):
        if self.sport == 'running':
            return round(sum(b.duracion_total()/b.pace_ref for b in self.bloques if b.pace_ref), 1)
        elif self.sport == 'cycling':
            return round(self.duracion_total() / 60 * 30, 1)  # ~30 km/h promedio
        elif self.sport == 'swimming':
            return round(self.duracion_total() / 60 * 2.5, 1)  # ~2.5 km/h promedio
        return 0


# ─── HELPERS RUNNING ──────────────────────────────────────────────────────────

def mk(zona, dur, lthr, pace_z2, reps=1, pausa=0.0, activa=True, nombre=None, desc='',
       hr_max_atleta=None):
    z = ZONAS[zona]
    hr_max_z = round(lthr * z['lthr_max'])
    if hr_max_atleta:
        hr_max_z = min(hr_max_z, hr_max_atleta)
    return Bloque(
        nombre=nombre or z['nombre'], zona=zona, sport='running',
        duracion_min=dur,
        hr_min=round(lthr*z['lthr_min']), hr_max=hr_max_z,
        pace_ref=round(pace_z2*PACE_FACTOR.get(zona,1.0), 2),
        repeticiones=reps, pausa_min=pausa, pausa_activa=activa,
        descripcion=desc or z['nombre'],
    )

# ─── NUTRICIÓN DURANTE EL ENTRENAMIENTO (todas las disciplinas) ──────────────

def _agregar_nutricion_durante(ses, atleta_id=None, conn=None):
    """
    Agrega nutrición DURANTE a una sesión ya armada, usando datos reales
    del atleta (peso). Aplica a las 3 disciplinas. Corre SIEMPRE.
    Usa noah_nutricion_completa.construir_recomendacion_durante(), que cita
    bibliografía exacta por cada rango (ISSN 2017, Jeukendrup, ACSM/Sawka 2007).

    Si no hay peso real registrado, NO inventa un valor — solo calcula
    el componente de CHO (que no depende del peso) y omite hidratación/sodio
    declarando la falta, en vez de asumir un peso promedio.
    """
    try:
        if not (conn and atleta_id):
            return ses

        from noah_nutricion_completa import construir_recomendacion_durante

        row = conn.execute(
            "SELECT peso_kg FROM atletas WHERE id=%s", (atleta_id,)
        ).fetchone()
        peso_kg = row[0] if row and row[0] else None

        dur_total = ses.duracion_total()
        # IF aproximado de la sesión: promedio ponderado por duración de TODOS
        # los bloques — más representativo que solo el bloque más largo
        # (que en sesiones tipo cal+cuerpo+enf puede subestimar la intensidad real).
        if_aprox = 0.80
        try:
            if ses.bloques and dur_total > 0:
                suma_ponderada = 0
                for b in ses.bloques:
                    if_b = ZONAS.get(b.zona, ZONAS_BIKE.get(b.zona, {})).get('if_factor', 0.75)
                    suma_ponderada += if_b * b.duracion_total()
                if_aprox = suma_ponderada / dur_total
        except Exception:
            pass

        rec = construir_recomendacion_durante(
            deporte=ses.sport, dur_min=dur_total, intensidad_if=if_aprox,
            peso_kg=peso_kg
        )

        cho = rec['cho']
        # Solo agregar texto si hay algo relevante que decir — siempre
        # informativo (incluso "no necesita CHO"), nunca silencioso.
        texto = rec['texto_corto']
        if texto:
            ses.descripcion = (ses.descripcion + ' | ' if ses.descripcion else '') + f'Nutrición: {texto}'

    except Exception:
        pass  # Silencioso — nutrición es complemento, no bloqueante

    return ses


def cal(lthr, pace_z2, dur=12.0):
    return mk('Z1', dur, lthr, pace_z2, nombre='Calentamiento Z1',
               desc='Progresivo. Activar sin forzar.')

def enf(lthr, pace_z2, dur=8.0):
    return mk('Z1', dur, lthr, pace_z2, nombre='Enfriamiento Z1',
               desc='Muy suave. Bajar HR gradualmente.')


# ─── HELPERS CYCLING ──────────────────────────────────────────────────────────

def mk_bike(zona_bike, dur, lthr_bike, ftp, reps=1, pausa=0.0, activa=True,
            nombre=None, desc=''):
    """Construye un bloque de ciclismo."""
    z = ZONAS_BIKE.get(zona_bike, ZONAS_BIKE['BZ2'])
    # HR estimado desde % LTHR bike (no desde % FTP para evitar inversiones)
    lthr_pct_map = {'BZ1': (0.60, 0.72), 'BZ2': (0.72, 0.82), 'BZ3': (0.82, 0.90),
                    'BZ4': (0.88, 0.98), 'BZ5': (0.98, 1.05), 'BZ6': (1.02, 1.10), 'BZ7': (1.08, 1.20)}
    pct_min_hr, pct_max_hr = lthr_pct_map.get(zona_bike, (0.72, 0.87))
    hr_min = round(lthr_bike * pct_min_hr)
    hr_max = round(lthr_bike * pct_max_hr)
    w_min  = round(ftp * z['ftp_min']) if ftp else None
    w_max  = round(ftp * z['ftp_max']) if ftp and z['ftp_max'] < 9 else None
    return Bloque(
        nombre=nombre or z['nombre'], zona=zona_bike, sport='cycling',
        duracion_min=dur,
        hr_min=hr_min, hr_max=hr_max,
        pace_ref=0,
        watts_min=w_min, watts_max=w_max,
        repeticiones=reps, pausa_min=pausa, pausa_activa=activa,
        descripcion=desc or z['nombre'],
    )

def cal_bike(lthr_bike, ftp, dur=10.0):
    return mk_bike('BZ1', dur, lthr_bike, ftp, nombre='Calentamiento BZ1',
                   desc='Suave. Activar piernas.')

def enf_bike(lthr_bike, ftp, dur=8.0):
    return mk_bike('BZ1', dur, lthr_bike, ftp, nombre='Enfriamiento BZ1',
                   desc='Bajar cadencia gradualmente.')


# ─── HELPERS SWIMMING ─────────────────────────────────────────────────────────

def mk_swim(zona, dur, lthr_swim, css_100m, reps=1, pausa=0.0, activa=True,
            nombre=None, desc=''):
    """Construye un bloque de natación."""
    z = ZONAS.get(zona, ZONAS['Z2'])
    hr_min = round(lthr_swim * z['lthr_min'])
    hr_max = round(lthr_swim * z['lthr_max'])
    pace   = round(css_100m / z['if_factor'], 3)
    return Bloque(
        nombre=nombre or z['nombre'], zona=zona, sport='swimming',
        duracion_min=dur,
        hr_min=hr_min, hr_max=hr_max, pace_ref=pace,
        repeticiones=reps, pausa_min=pausa, pausa_activa=activa,
        descripcion=desc or z['nombre'],
    )


# ─── DECISIONES SEMANALES ─────────────────────────────────────────────────────

def decidir_tipo_semana(ctl, atl, tsb, hrv_tend, ramp, sleep_p, ctl_obj, perfil):
    if hrv_tend == 'mala':                               return 'RECUPERACION'
    if tsb < -25:                                        return 'RECUPERACION'
    if ramp > perfil.get('ramp_rate_max', 1.25):         return 'RECUPERACION'
    # Sueño bajo reduce intensidad pero no cancela el plan — se maneja en HRV flag
    # Solo recuperación si sueño es críticamente bajo (<4h) Y HRV malo
    if sleep_p < 4.0 and hrv_tend == 'mala':            return 'RECUPERACION'
    if hrv_tend == 'buena' and tsb > -10 and (ctl_obj - ctl) > 3:
        return 'CARGA'
    return 'MANTENIMIENTO'

def decidir_prioridad(fase, ctl, ctl_obj, tipo_sem, hrv_tend):
    if tipo_sem == 'RECUPERACION': return 'RECUPERACION'
    if fase == 'A':
        return 'MIXTO' if (ctl_obj-ctl) <= 8 and hrv_tend == 'buena' else 'VOLUMEN'
    if fase in ('T','R'):        return 'INTENSIDAD'
    if fase == 'Taper':            return 'RECUPERACION'
    return 'VOLUMEN'


# ─── PATRONES RUNNING ─────────────────────────────────────────────────────────

def patron_s1(fase, sem, hrv_flag, laps_stats=None):
    avanzado = (laps_stats or {}).get('consistencia_series', 0.3) < 0.25
    if fase == 'A':
        if sem <= 3:
            return dict(zona='Z4', dur=2.0, n=6, pausa=3.0, activa=False,
                nombre='Intervalos Z4 — Umbral de lactato',
                desc='Pausa pasiva. Estímulo de umbral sin acumular lactato. Fase A temprana.')
        elif sem <= 5:
            return dict(zona='Z4', dur=3.0, n=5, pausa=3.0, activa=False,
                nombre='Intervalos Z4 — Umbral de lactato',
                desc='Progresión. Series más largas, pausa pasiva completa.')
        elif sem <= 7:
            return dict(zona='Z4', dur=3.0, n=5, pausa=2.5, activa=True,
                nombre='Intervalos Z4 — Umbral de lactato',
                desc='Pausa activa. El cuerpo aprende a recuperar en movimiento.')
        elif sem <= 9:
            return dict(zona='Z3-Z4', dur=5.0, n=4 if avanzado else 5, pausa=2.5, activa=True,
                nombre='Intervalos Z3-Z4 — Tempo / Umbral',
                desc='Trabajo de umbral. Empujamos el umbral anaeróbico hacia arriba.')
        else:
            return dict(zona='Z3', dur=6.0, n=4, pausa=2.0, activa=True,
                nombre='Tempo fraccionado Z3',
                desc='Tempo fraccionado. Prepara la transición a Transformación.')
    elif fase == 'T':
        if hrv_flag == 'verde':
            return dict(zona='Z4', dur=5.0, n=5, pausa=3.0, activa=True,
                nombre='Intervalos VO2max Z4',
                desc='Intervalos de umbral. HRV verde = podés exigirte.')
        else:
            return dict(zona='Z3', dur=8.0, n=4, pausa=2.0, activa=True,
                nombre='Tempo Z3',
                desc='Tempo fraccionado. HRV amarillo — moderado.')
    elif fase == 'R':
        return dict(zona='Z3', dur=10.0, n=3, pausa=2.0, activa=True,
            nombre='Bloques al ritmo de carrera',
            desc='Bloques largos al ritmo exacto de carrera.')
    elif fase == 'Taper':
        return dict(zona='Z4', dur=2.0, n=3, pausa=2.0, activa=True,
            nombre='Activación Taper Z4',
            desc='Mantiene el estímulo. Bajo volumen, preserva la intensidad.')
    return dict(zona='Z3', dur=5.0, n=4, pausa=2.0, activa=True,
        nombre='Intervalos Z3', desc='Intervalos tempo.')

# ── POOLS DE VARIANTES POR SESIÓN ────────────────────────────────────────────
# Regla: misma variante durante 3 semanas → cambia 1 por deporte en semana 4
# El sistema elige la que el atleta NO usó en las últimas 3 semanas

POOL_RUN_CALIDAD = [
    # Variantes de sesión de calidad run (LUN FTP / MIÉ PM calidad)
    {
        'id': 'run_q_intervalos_cortos',
        'nombre': 'Intervalos cortos umbral',
        'desc': '8×2min @Z4 c/90s activa — estímulo umbral con recuperación parcial',
        'zona': 'Z4', 'dur': 2.0, 'n': 8, 'pausa': 1.5, 'activa': True,
        'fases': ['A', 'T', 'R'],
    },
    {
        'id': 'run_q_intervalos_medios',
        'nombre': 'Intervalos medios umbral',
        'desc': '5×4min @Z4 c/2min activa — bloques medios, pausa completa',
        'zona': 'Z4', 'dur': 4.0, 'n': 5, 'pausa': 2.0, 'activa': True,
        'fases': ['A', 'T', 'R'],
    },
    {
        'id': 'run_q_tempo_largo',
        'nombre': 'Tempo continuo umbral',
        'desc': '3×8min @Z3-Z4 c/3min — bloques largos, umbral inferior',
        'zona': 'Z3-Z4', 'dur': 8.0, 'n': 3, 'pausa': 3.0, 'activa': True,
        'fases': ['A', 'T', 'R'],
    },
    {
        'id': 'run_q_escalera',
        'nombre': 'Escalera de ritmos',
        'desc': '4min+5min+6min+5min+4min @Z4 c/2min — variación de duración',
        'zona': 'Z4', 'dur': None, 'n': None, 'pausa': 2.0, 'activa': True,
        'especial': 'escalera', 'duraciones': [4.0, 5.0, 6.0, 5.0, 4.0],
        'fases': ['T', 'R'],
    },
    {
        'id': 'run_q_fartlek_umbral',
        'nombre': 'Fartlek de umbral',
        'desc': '6×(3min Z4 + 2min Z2) — fartlek estructurado, transiciones de ritmo',
        'zona': 'Z4', 'dur': 3.0, 'n': 6, 'pausa': 2.0, 'activa': True,
        'fases': ['A', 'T'],
    },
    {
        'id': 'run_q_vo2_corto',
        'nombre': 'Series VO2 cortas',
        'desc': '10×1min @Z5 c/2min — estímulo VO2max con recuperación completa',
        'zona': 'Z5', 'dur': 1.0, 'n': 10, 'pausa': 2.0, 'activa': False,
        'fases': ['T', 'R'],
    },
]

POOL_SWIM_CALIDAD = [
    {
        'id': 'swim_q_series_100',
        'nombre': 'Series 100m FTP',
        'desc': '8×100m @CSS c/15s — umbral aeróbico con descanso mínimo',
        'zona': 'Z4', 'dist': 100, 'n': 8, 'pausa_s': 15,
        'fases': ['A', 'T', 'R'],
    },
    {
        'id': 'swim_q_series_200',
        'nombre': 'Series 200m umbral',
        'desc': '5×200m @CSS c/20s — bloques más largos, mayor lactato steady',
        'zona': 'Z4', 'dist': 200, 'n': 5, 'pausa_s': 20,
        'fases': ['A', 'T', 'R'],
    },
    {
        'id': 'swim_q_series_400',
        'nombre': 'Bloques 400m',
        'desc': '3×400m @CSS c/30s — continuo largo, máxima producción en estado estable',
        'zona': 'Z3-Z4', 'dist': 400, 'n': 3, 'pausa_s': 30,
        'fases': ['T', 'R'],
    },
    {
        'id': 'swim_q_vo2_50',
        'nombre': 'VO2 series 50m',
        'desc': '12×50m @Z5 c/20s — máxima velocidad aeróbica, descanso controlado',
        'zona': 'Z5', 'dist': 50, 'n': 12, 'pausa_s': 20,
        'fases': ['T', 'R'],
    },
    {
        'id': 'swim_q_piramide',
        'nombre': 'Pirámide de distancias',
        'desc': '50+100+150+200+150+100+50m @CSS c/15s — variación progresiva',
        'zona': 'Z4', 'especial': 'piramide',
        'distancias': [50, 100, 150, 200, 150, 100, 50],
        'pausa_s': 15,
        'fases': ['A', 'T'],
    },
]


def _get_variante_semana(conn, atleta_id, pool_id, semana_macro, fase):
    """
    Retorna la variante activa para esta semana según la regla de 3 semanas.
    - Semanas 1-3: misma variante
    - Semana 4: cambia a la siguiente (que el atleta no usó en 3 semanas)
    """
    if not conn or not atleta_id:
        return pool_id[0] if pool_id else None

    # Historial de variantes usadas (últimas 4 semanas)
    try:
        conn.execute(
            'CREATE TABLE IF NOT EXISTS variantes_sesion '
            '(id SERIAL PRIMARY KEY, atleta_id INTEGER, '
            'tipo TEXT, variante_id TEXT, fecha TEXT)'
        )
        rows = conn.execute(
            'SELECT variante_id, fecha FROM variantes_sesion '
            'WHERE atleta_id=%s AND tipo=%s ORDER BY fecha DESC LIMIT 4',
            (atleta_id, pool_id[0].get('id','').split('_')[0]+'_'+pool_id[0].get('id','').split('_')[1])
            if isinstance(pool_id, list) else (atleta_id, pool_id)
        ).fetchall()
        hist = [r[0] for r in rows]
    except:
        hist = []

    # Semanas 1-3: mantener la última usada si aún no pasaron 3 semanas
    if hist and len(hist) < 3:
        return next((v for v in pool_id if v['id'] == hist[0]), pool_id[0])

    # Cambiar: elegir la que no se usó en las últimas 3 semanas
    usadas_recientes = set(hist[:3])
    disponibles = [v for v in pool_id if v['id'] not in usadas_recientes]
    if not disponibles:
        disponibles = pool_id

    # Filtrar por fase actual
    disponibles_fase = [v for v in disponibles if fase in v.get('fases', [fase])]
    return (disponibles_fase or disponibles)[0]


def sesion_1(fase, sem, hrv_flag, lthr, pace_z2, tss_obj, fecha,
             laps_stats=None, atleta_id=None, conn=None):
    """
    Run calidad (LUN FTP).
    Usa noah_nivel_carga + sesiones_biblioteca.json para elegir el metodo optimo.
    Fallback a variantes hardcodeadas si la biblioteca no está disponible.
    """
    # ── Intentar usar biblioteca JSON + nivel de carga ────────────────────────
    try:
        import json
        from pathlib import Path
        from noah_nivel_carga import calcular_nivel_carga, seleccionar_metodo_biblioteca, parametrizar_sesion

        bib_path = Path(__file__).parent / 'sesiones_biblioteca.json'
        if conn and atleta_id and bib_path.exists():
            biblioteca = json.load(open(bib_path, encoding='utf-8'))

            # Calcular nivel de carga real del dia
            nivel_result = calcular_nivel_carga(conn, atleta_id,
                                                fecha=str(fecha) if fecha else None,
                                                tsb=None, hrv_flag=hrv_flag)
            nivel = nivel_result['nivel']

            # Seleccionar método de la biblioteca
            metodo = seleccionar_metodo_biblioteca(biblioteca, 'run', 'ftp', nivel, fase)

            if metodo:
                params = parametrizar_sesion(metodo, nivel, tss_obj)
                zona   = 'Z4' if 'ftp' in metodo['id'] or 'umbral' in metodo['id'] else 'Z3'
                dur    = params['dur_bloque_min']
                n      = params['reps']
                pausa  = params['pausa_min']
                activa = params['pausa_activa']
                nombre = params['nombre']

                bls = [
                    cal(lthr, pace_z2, params['calentamiento_min'] or 12.0),
                    mk(zona, dur, lthr, pace_z2, reps=n, pausa=pausa, activa=activa,
                       nombre=nombre, desc=metodo.get('fisiologia', '')[:80]),
                    enf(lthr, pace_z2, params['enfriamiento_min'] or 8.0),
                ]
                tss = round(ZONAS.get(zona, ZONAS['Z4']).get('if_factor', 0.95)**2
                            * ((dur * n + params['calentamiento_min'] + params['enfriamiento_min']) / 60) * 100)
                return Sesion(nombre=nombre, tipo='run_calidad', fase=fase,
                              fecha=fecha, sport='running', bloques=bls, tss_estimado=tss,
                              descripcion=f'Nivel {nivel} — {metodo["id"]}')
    except Exception:
        pass  # Silencioso — fallback a variantes hardcodeadas

    # ── Fallback: variantes hardcodeadas (comportamiento original) ────────────
    variantes_disponibles = [v for v in POOL_RUN_CALIDAD if fase in v.get('fases', [fase])]
    if not variantes_disponibles:
        variantes_disponibles = POOL_RUN_CALIDAD

    variante = _get_variante_semana(conn, atleta_id, variantes_disponibles, sem, fase)

    zona  = variante['zona']
    dur   = variante['dur'] or 3.0
    n     = variante['n'] or 5
    pausa = variante['pausa']
    activa = variante['activa']

    if hrv_flag == 'rojo':
        n   = max(3, n - 2)
        dur = max(1.5, dur - 0.5)
    elif hrv_flag == 'verde' and sem > 2:
        n = n + 1

    bls = [
        cal(lthr, pace_z2, 12.0),
        mk(zona, dur, lthr, pace_z2, reps=n, pausa=pausa, activa=activa,
           nombre=variante['nombre'], desc=variante['desc']),
        enf(lthr, pace_z2, 8.0),
    ]
    tss = round(ZONAS.get(zona, ZONAS.get('Z4', {})).get('if_factor', 0.95)**2
                * ((dur * n + 20) / 60) * 100)
    return Sesion(nombre=variante['nombre'], tipo='run_calidad', fase=fase,
                  fecha=fecha, sport='running', bloques=bls, tss_estimado=tss)

def sesion_1_rec(lthr, pace_z2, fecha, fase):
    bls = [
        cal(lthr, pace_z2, 8.0),
        mk('Z1-Z2', 25.0, lthr, pace_z2, nombre='Suave Z1-Z2',
           desc='Sin series. Solo mover las piernas suave.'),
        enf(lthr, pace_z2, 5.0),
    ]
    dur = sum(b.duracion_total() for b in bls)
    tss = round(0.78**2 * (dur/60) * 100)
    return Sesion(nombre='Recuperación activa', tipo=1, fase=fase, fecha=fecha, sport='running',
                  bloques=bls, tss_estimado=tss, descripcion='Semana de recuperación. Sin series.')

def sesion_2(fase, sem, hrv_flag, lthr, pace_z2, tss_obj, fecha,
             atleta_id=None, conn=None):
    """
    Run Z2 + Neuromuscular (MIÉ).
    Usa biblioteca v3 (run.neuro.run_neuro_en_z2): aceleraciones al 110% VO2
    integradas en fondo Z2. SIEMPRE Z2 (nunca fondo largo) — el neuro no
    altera la naturaleza de la sesión.
    Fallback a lógica hardcodeada si la biblioteca falla.
    """
    try:
        import json
        from pathlib import Path
        from noah_nivel_carga import calcular_nivel_carga, seleccionar_metodo_biblioteca, parametrizar_sesion

        bib_path = Path(__file__).parent / 'sesiones_biblioteca.json'
        if conn and atleta_id and bib_path.exists():
            biblioteca = json.load(open(bib_path, encoding='utf-8'))

            nivel_result = calcular_nivel_carga(conn, atleta_id,
                                                fecha=str(fecha) if fecha else None,
                                                tsb=None, hrv_flag=hrv_flag)
            nivel = nivel_result['nivel']

            metodo = seleccionar_metodo_biblioteca(biblioteca, 'run', 'neuro', nivel, fase)

            if metodo:
                params = parametrizar_sesion(metodo, nivel, tss_obj, hrv_flag=hrv_flag)
                n_neuro    = params['reps']
                dur_neuro  = params['dur_bloque_min']  # ya en minutos (seg/60)
                pausa_z2   = params['pausa_min']
                fondo_pre  = params['calentamiento_min'] or 15.0
                fondo_post = params['enfriamiento_min'] or 10.0
                nombre     = params['nombre']

                bls = [cal(lthr, pace_z2, fondo_pre)]
                if n_neuro > 0:
                    bls.append(mk('Z6', dur_neuro, lthr, pace_z2, reps=n_neuro,
                                   pausa=pausa_z2, activa=True,
                                   nombre='Capacidad anaeróbica / Neuromuscular',
                                   desc=params.get('descripcion_extra','') or '110% VO2 integrado en Z2'))
                bls.append(enf(lthr, pace_z2, fondo_post))

                dur = sum(b.duracion_total() for b in bls)
                tss = round(ZONAS['Z2']['if_factor']**2 * (dur/60) * 100)
                return Sesion(nombre=nombre, tipo=2, fase=fase, fecha=fecha, sport='running',
                              bloques=bls, tss_estimado=tss,
                              descripcion=f'Nivel {nivel} — {metodo["id"]}')
    except Exception:
        pass  # Silencioso — fallback a lógica hardcodeada

    # ── Fallback: lógica original ──────────────────────────────────────────
    modo = ('BLOQUES' if hrv_flag == 'verde' or (fase in ('T','R') and hrv_flag != 'rojo')
            else 'CONTINUO')
    if fase == 'A' and sem <= 3:
        modo = 'CONTINUO'
    if_z2  = ZONAS['Z2']['if_factor']
    dur_z2 = round(min(tss_obj / (if_z2**2 * 100) * 0.85 * 60, 45))
    n_neuro = 0 if hrv_flag == 'rojo' else (4 if hrv_flag == 'verde' else 3)
    bls = [cal(lthr, pace_z2, 10.0)]
    if modo == 'BLOQUES':
        db = round(dur_z2 / 3)
        bls.append(mk('Z2', db, lthr, pace_z2, reps=3, pausa=2.0, activa=True,
                       nombre='Bloques Z2', desc=f'3×{db}\' Z2 / 2\' Z1 activo.'))
    else:
        bls.append(mk('Z2', dur_z2, lthr, pace_z2, nombre='Endurance Z2',
                       desc='Z2 continuo. HR estable, ritmo conversacional.'))
    if n_neuro > 0:
        bls.append(mk('Z6', 0.5, lthr, pace_z2, reps=n_neuro,
                       pausa=2.0, activa=True, nombre='Capacidad anaeróbica / Neuromuscular',
                       desc=f'{n_neuro}×30" aceleración controlada.'))
    bls.append(enf(lthr, pace_z2, 5.0))
    dur = sum(b.duracion_total() for b in bls)
    tss = round(if_z2**2 * (dur/60) * 100)
    nombre = f'Endurance Z2 {"bloques" if modo=="BLOQUES" else "continuo"}'
    nombre += ' + Neuromusculares' if n_neuro > 0 else ''
    return Sesion(nombre=nombre, tipo=2, fase=fase, fecha=fecha, sport='running',
                  bloques=bls, tss_estimado=tss, descripcion=f'Z2 {modo.lower()}.')

def sesion_3(fase, hrv_flag, lthr, pace_z2, tss_obj, fecha, dur_max_min=None):
    """
    Fondo largo (SÁB/finde).
    REGLA DEL COACH: NUNCA puro Z1-Z2. Siempre con bloques de Z3
    (piso si HRV amarillo, techo si HRV verde/fresco). Aplica en TODAS las fases.
    Taper NO es una fase de sesión — es un ciclo macro de descarga.
    """
    if_b  = ZONAS['Z1-Z2']['if_factor']
    dur_t = round(min(tss_obj / (if_b**2 * 100) * 60, dur_max_min if dur_max_min else 120))
    dur_t = max(dur_t, 40)  # mínimo razonable para un largo

    # Piso o techo de Z3 según HRV — nunca eliminar el Z3 salvo HRV rojo
    piso_techo = 'techo' if hrv_flag == 'verde' else 'piso'

    fase_ef = fase if fase in ('A', 'T', 'R') else 'A'  # Taper u otros → A

    if hrv_flag == 'rojo':
        # Único caso donde se reduce a Z1-Z2 sin bloques Z3 — atleta comprometido
        cuerpo = max(15, dur_t - 20)
        bls = [cal(lthr, pace_z2, 15.0),
               mk('Z1-Z2', cuerpo, lthr, pace_z2, nombre='Fondo suave Z1-Z2',
                  desc='HRV rojo — sin bloques Z3. Conversacional, sin estrés añadido.'),
               enf(lthr, pace_z2, 5.0)]
        nombre = 'Fondo suave Z1-Z2'
        desc   = 'HRV rojo — largo reducido sin Z3.'

    elif fase_ef == 'A':
        # Estructura base acordada: Z1 entrada + bloques alternados Z2/Z3 + Z1 salida
        cuerpo = max(20, dur_t - 20)
        n_bloques = 3 if cuerpo >= 70 else 2
        dz3_total = round(cuerpo * 0.30)   # ~30% del cuerpo en Z3
        dz2_total = cuerpo - dz3_total
        dz3_bloque = round(dz3_total / n_bloques, 1)
        dz2_bloque = round(dz2_total / n_bloques, 1)

        bls = [cal(lthr, pace_z2, 15.0)]
        for i in range(n_bloques):
            bls.append(mk('Z2', dz2_bloque, lthr, pace_z2, nombre='Fondo Z2',
                           desc='Base aeróbica conversacional.'))
            bls.append(mk('Z3', dz3_bloque, lthr, pace_z2, nombre=f'Bloque Z3 ({piso_techo})',
                           desc=f'Z3 en {piso_techo} — estímulo de umbral aeróbico dentro del largo.'))
        bls.append(enf(lthr, pace_z2, 5.0))
        nombre = f'Fondo largo Z1-Z2 + bloques Z3 ({piso_techo})'
        desc   = f'El fondo largo nunca es puro. {n_bloques} bloques de Z3 {piso_techo} intercalados con Z2.'

    elif fase_ef == 'T':
        dz2 = round((dur_t-20)*0.65); dz3 = round((dur_t-20)*0.35)
        bls = [cal(lthr, pace_z2, 12.0),
               mk('Z2', dz2, lthr, pace_z2, nombre='Fondo Z2', desc='Base Z2.'),
               mk('Z3', dz3, lthr, pace_z2, nombre=f'Progresión Z3 ({piso_techo})',
                  desc=f'Subí gradualmente en los últimos {dz3}\' — Z3 {piso_techo}.'),
               enf(lthr, pace_z2, 8.0)]
        nombre, desc = 'Fondo progresivo Z2→Z3', f'Fondo con progresión Z3 {piso_techo}. Aprendés a correr cansado.'

    else:  # R
        dz2 = round((dur_t-20)*0.45); dz3 = round((dur_t-20)*0.40); dc = round((dur_t-20)*0.15)
        bls = [cal(lthr, pace_z2, 12.0),
               mk('Z2', dz2, lthr, pace_z2, nombre='Fondo Z2', desc='Base Z2.'),
               mk('Z3', dz3, lthr, pace_z2, nombre=f'Bloque ritmo carrera ({piso_techo})',
                  desc=f'{dz3}\' al ritmo de carrera — Z3 {piso_techo}.'),
               mk('Z1-Z2', dc, lthr, pace_z2, nombre='Vuelta a la calma', desc='Bajar ritmo gradualmente.'),
               enf(lthr, pace_z2, 8.0)]
        nombre, desc = 'Fondo específico con sección Z3', f'Fondo R. Base Z2 + ritmo de carrera Z3 {piso_techo}.'

    tss = round(if_b**2 * (sum(b.duracion_total() for b in bls)/60) * 100)
    return Sesion(nombre=nombre, tipo=3, fase=fase, fecha=fecha, sport='running',
                  bloques=bls, tss_estimado=tss, descripcion=desc)


# ─── PATRONES CYCLING ─────────────────────────────────────────────────────────

import random as _random

def _elegir_variante(pool, historial):
    ids_recientes = [h.get('variante_id') for h in (historial or [])[-2:]]
    disponibles = [v for v in pool if v['id'] not in ids_recientes]
    if not disponibles:
        disponibles = pool
    return _random.choice(disponibles)

def _get_historial_variantes(conn, atleta_id, tipo, n=4):
    if not conn:
        return []
    try:
        rows = conn.execute(
            "SELECT variante_id, fecha FROM variantes_sesion "
            "WHERE atleta_id=%s AND tipo=%s ORDER BY fecha DESC LIMIT %s",
            (atleta_id, tipo, n)).fetchall()
        return [{"variante_id": r[0], "fecha": r[1]} for r in rows]
    except Exception:
        return []

def _guardar_variante(conn, atleta_id, tipo, variante_id, fecha):
    if not conn:
        return
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS variantes_sesion "
            "(id SERIAL PRIMARY KEY, atleta_id INTEGER, "
            "tipo TEXT, variante_id TEXT, fecha TEXT)"
        )
        conn.execute(
            "INSERT INTO variantes_sesion (atleta_id, tipo, variante_id, fecha) VALUES (%s,%s,%s,%s)",
            (atleta_id, tipo, variante_id, str(fecha))
        )
        conn.commit()
    except Exception:
        pass

POOL_BIKE_UMBRAL = [
    {"id": "bz4_clasico",
     "nombre": "Intervalos BZ4 — Umbral clásico",
     "bloques_fn": "clasico"},
    {"id": "bz4_largo",
     "nombre": "Bloques BZ4 — Series largas",
     "bloques_fn": "largo"},
    {"id": "over_under",
     "nombre": "Over-Under BZ3/BZ4",
     "bloques_fn": "over_under"},
    {"id": "tempo_continuo",
     "nombre": "Tempo BZ3 + Bloque BZ4",
     "bloques_fn": "tempo"},
    {"id": "piramide_bz4",
     "nombre": "Pirámide BZ4",
     "bloques_fn": "piramide"},
]

POOL_RUN_UMBRAL = [
    {"id": "z4_clasico",   "zona": "Z4", "dur": 2.0, "n": 6, "pausa": 3.0, "activa": False,
     "nombre": "Intervalos Z4 — Umbral clásico",
     "desc": "6x2 al umbral con pausa pasiva. Estimulo limpio."},
    {"id": "z4_largo",     "zona": "Z4", "dur": 4.0, "n": 4, "pausa": 3.0, "activa": True,
     "nombre": "Series largas Z4",
     "desc": "4x4 al umbral. Series mas largas para sostener el ritmo."},
    {"id": "tempo_frac",   "zona": "Z3", "dur": 8.0, "n": 3, "pausa": 2.0, "activa": True,
     "nombre": "Tempo fraccionado Z3-Z4",
     "desc": "3x8 al tempo. Umbral aerobico. Base de resistencia."},
    {"id": "crucero",      "zona": "Z3", "dur": 10.0, "n": 2, "pausa": 2.0, "activa": True,
     "nombre": "Intervalos crucero Z3",
     "desc": "2x10 tempo. Bloques largos para desarrollar el motor aerobico."},
    {"id": "progresion",   "zona": "Z2", "dur": 15.0, "n": 1, "pausa": 0, "activa": True,
     "nombre": "Progresion Z2 a Z4",
     "desc": "15 Z2 + 10 Z3 + 5 Z4. Progresion natural de intensidad."},
]

POOL_SWIM_SERIES = [
    {"id": "series_100",   "dist": 100, "reps": 10, "pausa_seg": 15,
     "nombre": "10x100m CSS", "desc": "10x100m al CSS. Pausa 15s. Umbral aerobico."},
    {"id": "series_200",   "dist": 200, "reps": 5,  "pausa_seg": 30,
     "nombre": "5x200m CSS", "desc": "5x200m al CSS. Pausa 30s. Series largas de umbral."},
    {"id": "piramide",     "dist": 0,   "reps": 0,  "pausa_seg": 20,
     "nombre": "Piramide 100-200-300-200-100",
     "desc": "Piramide de distancias. Variacion de estimulo y duracion."},
    {"id": "velocidad_50", "dist": 50,  "reps": 8,  "pausa_seg": 30,
     "nombre": "8x50m velocidad", "desc": "8x50m al maximo. Tecnica y velocidad maxima."},
    {"id": "mixto",        "dist": 150, "reps": 6,  "pausa_seg": 20,
     "nombre": "6x150m mixto", "desc": "6x150m entre Z3 y Z4. Estimulo variado."},
]


def sesion_bike_calidad(fase, sem, hrv_flag, lthr_bike, ftp, tss_obj, fecha,
                        atleta_id=None, conn=None):
    """
    Sesion de calidad en bike (MAR FTP).
    Usa biblioteca v4 (bike.ftp): Sweet Spot en fase A, FTP puro en T/R,
    over-under solo ALTO+T/R. Calcula vatios reales desde FTP del atleta.
    Fallback a pool hardcodeado si la biblioteca falla.
    """
    try:
        import json
        from pathlib import Path
        from noah_nivel_carga import calcular_nivel_carga, seleccionar_metodo_biblioteca, parametrizar_sesion

        bib_path = Path(__file__).parent / 'sesiones_biblioteca.json'
        if conn and atleta_id and bib_path.exists() and ftp:
            biblioteca = json.load(open(bib_path, encoding='utf-8'))

            nivel_result = calcular_nivel_carga(conn, atleta_id,
                                                fecha=str(fecha) if fecha else None,
                                                tsb=None, hrv_flag=hrv_flag)
            nivel = nivel_result['nivel']

            metodo = seleccionar_metodo_biblioteca(biblioteca, 'bike', 'ftp', nivel, fase)

            if metodo:
                params = parametrizar_sesion(metodo, nivel, tss_obj, hrv_flag=hrv_flag)
                zona   = params.get('zona') or metodo.get('zona_objetivo', 'BZ4')
                zona_b = zona.split('-')[0] if '-' in zona else zona  # 'BZ3-BZ4' -> 'BZ3'
                dur    = params['dur_bloque_min']
                n      = params['reps']
                pausa  = params['pausa_min']
                activa = params['pausa_activa']
                nombre = params['nombre']

                bls = [
                    cal_bike(lthr_bike, ftp, params['calentamiento_min'] or 15.0),
                    mk_bike(zona_b, dur, lthr_bike, ftp, reps=n, pausa=pausa, activa=activa,
                            nombre=nombre, desc=metodo.get('fisiologia', '')[:90]),
                    enf_bike(lthr_bike, ftp, params['enfriamiento_min'] or 8.0),
                ]
                dur_total = sum(b.duracion_total() for b in bls)
                if_val = 0.95 if zona_b == 'BZ4' else 0.90
                tss = round(if_val**2 * (dur_total/60) * 100)
                return Sesion(nombre=nombre, tipo='bike_calidad', fase=fase, fecha=fecha,
                              sport='cycling', bloques=bls, tss_estimado=tss,
                              descripcion=f'Nivel {nivel} — {metodo["id"]}')
    except Exception:
        pass  # Silencioso — fallback al pool hardcodeado

    # ── Fallback: pool hardcodeado (comportamiento original) ──────────────────
    hist = _get_historial_variantes(conn, atleta_id, 'bike_umbral')
    v    = _elegir_variante(POOL_BIKE_UMBRAL, hist)
    _guardar_variante(conn, atleta_id, 'bike_umbral', v['id'], fecha)

    fn = v.get('bloques_fn', 'clasico')

    if fn == 'largo':
        bls = [cal_bike(lthr_bike, ftp, 15),
               mk_bike('BZ4', 7.0, lthr_bike, ftp, reps=3, pausa=3.0, activa=True,
                       nombre='Bloques BZ4 largos',
                       desc='3x7 al umbral. Desarrolla la capacidad de sostener el FTP.'),
               enf_bike(lthr_bike, ftp, 8)]
    elif fn == 'over_under':
        bls = [cal_bike(lthr_bike, ftp, 12),
               mk_bike('BZ3', 2.0, lthr_bike, ftp, reps=6, pausa=0, activa=True,
                       nombre='Under BZ3', desc='Alternancia 2min BZ3 + 1min BZ4 x6.'),
               mk_bike('BZ4', 1.0, lthr_bike, ftp, reps=6, pausa=0, activa=True,
                       nombre='Over BZ4', desc=''),
               enf_bike(lthr_bike, ftp, 8)]
    elif fn == 'tempo':
        bls = [cal_bike(lthr_bike, ftp, 12),
               mk_bike('BZ3', 20, lthr_bike, ftp, nombre='Tempo BZ3',
                       desc='20min tempo continuo. Techo del aerobico.'),
               mk_bike('BZ4', 10, lthr_bike, ftp, nombre='Bloque BZ4',
                       desc='10min al umbral sin pausa. Estimulo final.'),
               enf_bike(lthr_bike, ftp, 8)]
    elif fn == 'piramide':
        bls = [cal_bike(lthr_bike, ftp, 12),
               mk_bike('BZ4', 3.0, lthr_bike, ftp, pausa=2.0, activa=True, nombre='BZ4 3min'),
               mk_bike('BZ4', 5.0, lthr_bike, ftp, pausa=2.0, activa=True, nombre='BZ4 5min'),
               mk_bike('BZ4', 7.0, lthr_bike, ftp, pausa=2.0, activa=True, nombre='BZ4 7min cima'),
               mk_bike('BZ4', 5.0, lthr_bike, ftp, pausa=2.0, activa=True, nombre='BZ4 5min baja'),
               mk_bike('BZ4', 3.0, lthr_bike, ftp, pausa=0,   activa=True, nombre='BZ4 3min final'),
               enf_bike(lthr_bike, ftp, 8)]
    else:  # clasico
        bls = [cal_bike(lthr_bike, ftp, 15),
               mk_bike('BZ4', 3.0, lthr_bike, ftp, reps=5, pausa=3.0, activa=False,
                       nombre='Intervalos BZ4', desc='5x3 al umbral. Pausa pasiva.'),
               enf_bike(lthr_bike, ftp, 10)]

    nombre = v['nombre']
    dur = sum(b.duracion_total() for b in bls)
    # Calcular TSS estimado desde duración e IF de BZ4
    if_val = 0.97  # IF típico de sesión de umbral
    tss = round(if_val**2 * (dur/60) * 100) if dur > 0 else (tss_obj or 80)

    return Sesion(nombre=nombre, tipo='bike_calidad', fase=fase, fecha=fecha, sport='cycling',
                  bloques=bls, tss_estimado=tss)

def sesion_bike_endurance(fase, hrv_flag, lthr_bike, ftp, tss_obj, fecha, larga=False,
                          atleta_id=None, conn=None):
    """
    Sesion de endurance en bike.
    JUE (larga=False): usa biblioteca v4 bike.endurance_neuro — Z1-Z2 + bloques
      de potencia a cadencia media-baja. NO regenerativo, NO sprint.
    SÁB (larga=True): usa biblioteca v4 bike.long — NUNCA puro BZ2, siempre con
      bloques BZ3 piso/techo según HRV.
    Fallback a lógica hardcodeada si la biblioteca falla.
    """
    categoria = 'long' if larga else 'endurance_neuro'

    try:
        import json
        from pathlib import Path
        from noah_nivel_carga import (calcular_nivel_carga, seleccionar_metodo_biblioteca,
                                       parametrizar_sesion, piso_techo_zona)

        bib_path = Path(__file__).parent / 'sesiones_biblioteca.json'
        if conn and atleta_id and bib_path.exists() and ftp:
            biblioteca = json.load(open(bib_path, encoding='utf-8'))

            nivel_result = calcular_nivel_carga(conn, atleta_id,
                                                fecha=str(fecha) if fecha else None,
                                                tsb=None, hrv_flag=hrv_flag)
            nivel = nivel_result['nivel']

            metodo = seleccionar_metodo_biblioteca(biblioteca, 'bike', categoria, nivel, fase)

            if metodo:
                if not larga:
                    # ── JUE: endurance_neuro ───────────────────────────────────
                    params = parametrizar_sesion(metodo, nivel, tss_obj, hrv_flag=hrv_flag)
                    fondo_min  = params['calentamiento_min'] or 25.0
                    n_pot      = params['reps']
                    dur_pot    = params['dur_bloque_min']
                    pausa_pot  = params['pausa_min']
                    nombre     = params['nombre']

                    bls = [cal_bike(lthr_bike, ftp, 10.0),
                           mk_bike('BZ2', fondo_min, lthr_bike, ftp,
                                   nombre='Endurance BZ2', desc='Base aeróbica.')]
                    if n_pot > 0:
                        bls.append(mk_bike('BZ5', dur_pot, lthr_bike, ftp, reps=n_pot,
                                            pausa=pausa_pot, activa=True,
                                            nombre='Bloques potencia (cadencia media-baja)',
                                            desc='Carga alta, NO sprint, cadencia media-baja.'))
                    bls.append(enf_bike(lthr_bike, ftp, 5.0))

                    dur_total = sum(b.duracion_total() for b in bls)
                    tss = round(ZONAS_BIKE['BZ2']['if_factor']**2 * (dur_total/60) * 100)
                    return Sesion(nombre=nombre, tipo='bike_endurance', fase=fase, fecha=fecha,
                                  sport='cycling', bloques=bls, tss_estimado=tss,
                                  descripcion=f'Nivel {nivel} — {metodo["id"]}')
                else:
                    # ── SÁB: long con bloques BZ3 piso/techo ───────────────────
                    dur_max = metodo.get('dur_rango_min', {})
                    dur_max_min = dur_max.get('max', 180) if isinstance(dur_max, dict) else 180
                    if_bz2 = ZONAS_BIKE['BZ2']['if_factor']
                    dur_t  = round(min(tss_obj / (if_bz2**2 * 100) * 60, dur_max_min))
                    dur_t  = max(dur_t, 60)

                    pt = piso_techo_zona(hrv_flag, nivel)

                    if hrv_flag == 'rojo':
                        # Único caso sin BZ3 — atleta comprometido
                        cuerpo = max(20, dur_t - 23)
                        bls = [cal_bike(lthr_bike, ftp, 15.0),
                               mk_bike('BZ2', cuerpo, lthr_bike, ftp,
                                       nombre='Endurance BZ2', desc='HRV rojo — sin bloques BZ3.'),
                               enf_bike(lthr_bike, ftp, 8.0)]
                        nombre = 'Fondo suave BZ1-BZ2'
                    else:
                        cuerpo = max(30, dur_t - 25)
                        n_bloques = 4 if cuerpo >= 90 else (3 if cuerpo >= 50 else 2)
                        dz3_total = round(cuerpo * 0.30)
                        dz2_total = cuerpo - dz3_total
                        dz3_b = round(dz3_total / n_bloques, 1)
                        dz2_b = round(dz2_total / n_bloques, 1)

                        bls = [cal_bike(lthr_bike, ftp, 15.0)]
                        for i in range(n_bloques):
                            bls.append(mk_bike('BZ2', dz2_b, lthr_bike, ftp,
                                                nombre='Endurance BZ2', desc='Base aeróbica.'))
                            bls.append(mk_bike('BZ3', dz3_b, lthr_bike, ftp,
                                                nombre=f'Bloque BZ3 ({pt})',
                                                desc=f'BZ3 en {pt} — nunca largo puro BZ2.'))
                        bls.append(enf_bike(lthr_bike, ftp, 10.0))
                        nombre = f'Fondo largo BZ2 + bloques BZ3 ({pt})'

                    dur_total = sum(b.duracion_total() for b in bls)
                    tss = round(if_bz2**2 * (dur_total/60) * 100)

                    return Sesion(nombre=nombre, tipo='bike_endurance', fase=fase, fecha=fecha,
                                  sport='cycling', bloques=bls, tss_estimado=tss,
                                  descripcion=f'Nivel {nivel} — {metodo["id"]} ({pt})')
    except Exception:
        pass  # Silencioso — fallback a lógica hardcodeada

    # ── Fallback: lógica original ──────────────────────────────────────────
    if_bz2 = ZONAS_BIKE['BZ2']['if_factor']
    dur = round(min(tss_obj / (if_bz2**2 * 100) * 60, 180 if larga else 90))
    if hrv_flag == 'rojo':
        dur = round(dur * 0.6)

    if fase in ('T', 'R') and larga and hrv_flag != 'rojo':
        dz2 = round(dur * 0.70); dz3 = round(dur * 0.25); dc = round(dur * 0.05)
        bls = [cal_bike(lthr_bike, ftp, 15),
               mk_bike('BZ2', dz2, lthr_bike, ftp, nombre='Endurance BZ2', desc='Base aeróbica.'),
               mk_bike('BZ3', dz3, lthr_bike, ftp, nombre='Progresión BZ3', desc='Subí gradualmente.'),
               mk_bike('BZ1', dc, lthr_bike, ftp, nombre='Vuelta calma', desc='Suave.'),
               enf_bike(lthr_bike, ftp, 8)]
        nombre = 'Fondo largo BZ2→BZ3'
    else:
        bls = [cal_bike(lthr_bike, ftp, 15),
               mk_bike('BZ2', dur, lthr_bike, ftp, nombre='Endurance BZ2', desc='Z2 continuo en bici.'),
               enf_bike(lthr_bike, ftp, 8)]
        nombre = 'Endurance BZ2' + (' largo' if larga else '')

    dur_total = sum(b.duracion_total() for b in bls)
    tss = round(if_bz2**2 * (dur_total/60) * 100)
    return Sesion(nombre=nombre, tipo='bike_endurance', fase=fase, fecha=fecha, sport='cycling',
                  bloques=bls, tss_estimado=tss)


# ─── PATRONES SWIMMING ────────────────────────────────────────────────────────

def sesion_swim_endurance(fase, hrv_flag, lthr_swim, css_100m, tss_obj, fecha, larga=False):
    """Sesion de natación endurance."""
    if_z2 = ZONAS['Z2']['if_factor']
    dur   = round(min(tss_obj / (if_z2**2 * 100) * 60, 90 if larga else 50))
    if hrv_flag == 'rojo':
        dur = round(dur * 0.6)

    if fase in ('T','R') and larga:
        d2 = round(dur * 0.60); d3 = round(dur * 0.30); d1 = round(dur * 0.10)
        bls = [mk_swim('Z1', 10, lthr_swim, css_100m, nombre='Entrada al agua', desc='Técnica. Activar.'),
               mk_swim('Z2', d2, lthr_swim, css_100m, nombre='Fondos Z2', desc='Aeróbico base.'),
               mk_swim('Z3', d3, lthr_swim, css_100m, nombre='Progresión Z3', desc='Subí el ritmo.'),
               mk_swim('Z1', d1, lthr_swim, css_100m, nombre='Vuelta calma', desc='Técnica al final.')]
        nombre = 'Swim fondo largo Z2→Z3'
    else:
        bls = [mk_swim('Z1', 10, lthr_swim, css_100m, nombre='Entrada al agua', desc='Activar.'),
               mk_swim('Z2', dur, lthr_swim, css_100m, nombre='Fondos Z2', desc='Z2 continuo.'),
               mk_swim('Z1', 5, lthr_swim, css_100m, nombre='Vuelta calma', desc='Técnica.')]
        nombre = 'Swim Endurance Z2'

    dur_total = sum(b.duracion_total() for b in bls)
    tss = round(if_z2**2 * (dur_total/60) * 100)
    return Sesion(nombre=nombre, tipo='swim_endurance', fase=fase, fecha=fecha, sport='swimming',
                  bloques=bls, tss_estimado=tss)

def sesion_swim_series(fase, hrv_flag, lthr_swim, css_100m, tss_obj, fecha,
                       atleta_id=None, conn=None):
    """Series de natacion — elige variante del pool para no repetir."""
    hist = _get_historial_variantes(conn, atleta_id, 'swim_series')
    v = _elegir_variante(POOL_SWIM_SERIES, hist)
    _guardar_variante(conn, atleta_id, 'swim_series', v['id'], fecha)

    pausa_min = round(v['pausa_seg'] / 60, 2)

    if v['id'] == 'piramide':
        css = css_100m
        bls = [
            mk_swim('Z2', 10, lthr_swim, css, nombre='Calentamiento'),
            mk_swim('Z3', css*4*100/60/100, lthr_swim, css, nombre='100m Z3'),
            mk_swim('Z4', css*4*200/60/100, lthr_swim, css, nombre='200m CSS'),
            mk_swim('Z4', css*4*300/60/100, lthr_swim, css, nombre='300m CSS cima'),
            mk_swim('Z4', css*4*200/60/100, lthr_swim, css, nombre='200m CSS'),
            mk_swim('Z3', css*4*100/60/100, lthr_swim, css, nombre='100m Z3'),
            mk_swim('Z2', 5, lthr_swim, css, nombre='Enfriamiento'),
        ]
        nombre = v['nombre']
        return Sesion(nombre=nombre, tipo=4, fase=fase, fecha=fecha, sport='swimming',
                      bloques=bls, tss_estimado=tss_obj)

    dur_largo = round(v['dist'] * css_100m / 100, 2)
    bls = [
        mk_swim('Z2', 10, lthr_swim, css_100m, nombre='Calentamiento'),
        mk_swim('Z4' if v['dist'] >= 100 else 'Z5',
                dur_largo, lthr_swim, css_100m,
                reps=v['reps'], pausa=pausa_min, activa=False,
                nombre=v['nombre'], desc=v['desc']),
        mk_swim('Z2', 5, lthr_swim, css_100m, nombre='Enfriamiento'),
    ]
    return Sesion(nombre=v['nombre'], tipo=4, fase=fase, fecha=fecha, sport='swimming',
                  bloques=bls, tss_estimado=tss_obj)


def sesion_swim_series_original(fase, hrv_flag, lthr_swim, css_100m, tss_obj, fecha):
    """Sesion de natación con series."""
    if fase == 'A':
        bls = [mk_swim('Z1', 10, lthr_swim, css_100m, nombre='Entrada', desc='Activar.'),
               mk_swim('Z4', 2.0, lthr_swim, css_100m, reps=8, pausa=0.5, activa=True,
                       nombre='Series Z4', desc='8×2\' Z4. Pausa 30".'),
               mk_swim('Z1', 5, lthr_swim, css_100m, nombre='Vuelta calma', desc='Técnica.')]
        nombre = 'Series Z4 — Natación'
    elif fase in ('T','R'):
        bls = [mk_swim('Z1', 10, lthr_swim, css_100m, nombre='Entrada', desc='Activar.'),
               mk_swim('Z4', 4.0, lthr_swim, css_100m, reps=5, pausa=1.0, activa=True,
                       nombre='Series Z4', desc='5×4\' Z4.'),
               mk_swim('Z1', 5, lthr_swim, css_100m, nombre='Vuelta calma', desc='Técnica.')]
        nombre = 'Series Z4 — Natación'
    else:  # TAPER
        bls = [mk_swim('Z1', 10, lthr_swim, css_100m, nombre='Entrada', desc='Activar.'),
               mk_swim('Z4', 2.0, lthr_swim, css_100m, reps=4, pausa=1.0, activa=True,
                       nombre='Series Z4', desc='4×2\' activación.'),
               mk_swim('Z1', 5, lthr_swim, css_100m, nombre='Vuelta calma', desc='Técnica.')]
        nombre = 'Activación Swim Taper'

    dur_total = sum(b.duracion_total() for b in bls)
    tss = round(ZONAS['Z4']['if_factor']**2 * (dur_total/60) * 100)
    return Sesion(nombre=nombre, tipo='swim_series', fase=fase, fecha=fecha, sport='swimming',
                  bloques=bls, tss_estimado=tss)


# ─── GENERADOR MULTIDEPORTE ───────────────────────────────────────────────────


def calcular_tss_objetivo(ctl, ctl_obj, tipo_sem, perfil, fase, semana_macro,
                           tss_key_max, tss_key_min, tss_default_max, tss_default_min,
                           tss_manual=None):
    """
    Calcula el TSS semanal objetivo de forma inteligente.

    Lógica:
    1. Si el coach pasó un tss_manual → usar ese (override total).
    2. TSS_base = CTL_actual × 7 (carga de mantenimiento del fitness actual).
    3. Aplicar ramp_rate según tipo_sem:
       - CARGA:         +7% (ramp seguro)
       - MANTENIMIENTO: +0% (mantener CTL)
       - RECUPERACION:  -40% (bajar carga)
    4. Clampear entre tss_min_absoluto y tss_max del perfil.
    5. Si el atleta está muy desentrenado (CTL < 30% del objetivo),
       aplicar rampa conservadora de reintroducción (max 15% sobre CTL×7).

    Args:
        ctl:           CTL actual proyectado a hoy
        ctl_obj:       CTL objetivo del macrociclo
        tipo_sem:      'CARGA' | 'MANTENIMIENTO' | 'RECUPERACION'
        perfil:        dict del macrociclo
        fase:          'A' | 'T' | 'R' | 'Taper'
        semana_macro:  número de semana dentro de la fase
        tss_key_max:   key en perfil para TSS máximo (ej: 'tss_semana_f1_max')
        tss_key_min:   key en perfil para TSS mínimo
        tss_default_max: valor por defecto si no está en perfil
        tss_default_min: valor por defecto si no está en perfil
        tss_manual:    override del coach (None = usar lógica automática)
    """
    # 0. Override manual del coach
    if tss_manual and tss_manual > 0:
        return int(tss_manual)

    # 1. Tss de mantenimiento = CTL × 7 (TSS diario promedio × 7 días)
    tss_mantenimiento = round(ctl * 7)

    # 2. Ramp según tipo de semana
    ramp = {
        'CARGA':         1.07,   # +7% sobre mantenimiento
        'MANTENIMIENTO': 1.00,   # neutro
        'RECUPERACION':  0.60,   # -40% recovery
    }.get(tipo_sem, 1.00)

    tss_objetivo = round(tss_mantenimiento * ramp)

    # 3. Detección de desentrenamiento
    #    Si CTL < 35% del objetivo → atleta desentrenado, reintroducir con calma
    umbral_detren = ctl_obj * 0.35
    if ctl < umbral_detren and tipo_sem == 'CARGA':
        # Limitar el incremento a 15% sobre el mantenimiento actual
        tss_objetivo = round(tss_mantenimiento * 1.15)

    # 4. Ajuste por semana dentro de la fase (progresión gradual al inicio)
    if semana_macro == 1:
        tss_objetivo = round(tss_objetivo * 0.85)  # semana 1 más conservadora
    elif semana_macro == 2:
        tss_objetivo = round(tss_objetivo * 0.92)

    # 5. Techo absoluto del perfil (nunca superar lo planificado en el macro)
    tss_max_perfil = perfil.get(tss_key_max, tss_default_max)
    tss_min_perfil = perfil.get(tss_key_min, tss_default_min)
    tss_min_abs    = round(tss_min_perfil * 0.40)  # mínimo = 40% del piso del perfil

    # 6. Clampear
    tss_objetivo = max(tss_min_abs, min(tss_objetivo, tss_max_perfil))

    return tss_objetivo


def generar_semana_triatleta(atleta_config, estado, perfil, semana_macro, fechas_9):
    """
    Genera semana completa de 9 sesiones para triatleta.
    fechas_9: [lun, mar, mie, mie_swim, jue, vie, vie_swim, sab, dom]
    """
    lthr     = atleta_config.get('lthr', 162)
    pace_z2  = atleta_config.get('pace_z2_real', 5.55)
    lthr_bike = atleta_config.get('lthr_bike', 150)
    ftp       = atleta_config.get('ftp', None)
    lthr_swim = atleta_config.get('lthr_swim', round(lthr * 0.92))
    css_100m  = atleta_config.get('css_100m', 1.75)

    fase    = estado.get('fase', 'A')
    hrv_f   = estado.get('hrv_flag', 'amarillo')
    ctl     = estado.get('ctl', 60.0)
    atl     = estado.get('atl', 60.0)
    tsb     = estado.get('tsb', 0.0)
    hrv_t   = estado.get('hrv_tendencia', 'buena')
    sleep_p = estado.get('sleep_promedio', 7.0)
    ramp    = estado.get('ramp_rate', 1.05)
    ctl_obj = perfil.get('ctl_objetivo', 90)

    tipo_sem  = decidir_tipo_semana(ctl, atl, tsb, hrv_t, ramp, sleep_p, ctl_obj, perfil)
    prioridad = decidir_prioridad(fase, ctl, ctl_obj, tipo_sem, hrv_t)

    # ── TSS semanal inteligente basado en CTL actual ──────────────────────────
    # Regla fisiológica: TSS_semana = CTL_actual × 7 para mantener fitness.
    # Para crecer: aplicar ramp_rate (máx 7% seguro, 10% agresivo).
    # Nunca superar el tss_semana_f1_max del perfil (techo absoluto).
    # Si CTL es muy bajo (desentrenamiento), aplicar rampa conservadora.
    tss_manual = estado.get('tss_manual')
    tss_base = calcular_tss_objetivo(
        ctl=ctl, ctl_obj=ctl_obj, tipo_sem=tipo_sem,
        perfil=perfil, fase=fase, semana_macro=semana_macro,
        tss_key_max='tss_semana_f1_max', tss_key_min='tss_semana_f1_min',
        tss_default_max=500, tss_default_min=420,
        tss_manual=tss_manual,
    )

    tss_run  = round(tss_base * 0.35)
    tss_bike = round(tss_base * 0.40)
    tss_swim = round(tss_base * 0.25)

    # Esquema semanal triatleta (Navarro):
    # LUN: Swim | MAR: Bike | MIÉ: Swim+Run | JUE: Bike | VIE: Swim+Run | SÁB: Bike largo | DOM: Run largo
    lun, mar, mie, mie_s, jue, vie, vie_s, sab, dom = fechas_9

    aid  = atleta_config.get('atleta_id') or estado.get('atleta_id')
    conn = atleta_config.get('conn') or estado.get('conn')

    # ── Estructura semanal FIJA triatleta ────────────────────────────────────
    # Objetivos por día son ESTÁTICOS — solo cambia la variante y la carga
    # LUN: Swim long (Z2 volumen — día de recuperación activa)
    # MAR: Bike FTP (umbral en bike)
    # MIÉ AM: Swim FTP (umbral en swim)
    # MIÉ PM: Run VO2 (calidad run)
    # JUE: Bike Neuro + Z1/Z2 regen
    # VIE AM: Swim VO2
    # VIE PM: Run FTP (umbral run)
    # SÁB: Bike Long (volumen)
    # DOM: Run Long (volumen)

    # Recuperación: reemplaza calidad por regenerativo
    es_rec = (prioridad == 'RECUPERACION')

    # Todas las sesiones con fecha correcta — sin solapamientos
    todas = [
        # LUN — Swim long (Z2, volumen)
        sesion_swim_endurance(fase, hrv_f, lthr_swim, css_100m, tss_swim, lun, larga=True),
        # MAR — Bike FTP (umbral)
        sesion_bike_calidad(fase, semana_macro, hrv_f, lthr_bike, ftp,
                            tss_bike//3, mar, atleta_id=aid, conn=conn),
        # MIÉ AM — Swim FTP (umbral swim)
        sesion_swim_series(fase, hrv_f, lthr_swim, css_100m,
                           tss_swim//2, mie, atleta_id=aid, conn=conn),
        # MIÉ PM — Run VO2 (calidad run)
        (sesion_1_rec(lthr, pace_z2, mie_s, fase) if es_rec
         else sesion_1(fase, semana_macro, hrv_f, lthr, pace_z2,
                       tss_run//3, mie_s, atleta_id=aid, conn=conn)),
        # JUE — Bike Neuro + Z1/Z2 regen
        sesion_bike_endurance(fase, hrv_f, lthr_bike, ftp, tss_bike//3, jue,
                            atleta_id=aid, conn=conn),
        # VIE AM — Swim VO2
        sesion_swim_series(fase, hrv_f, lthr_swim, css_100m,
                           tss_swim//2, vie, atleta_id=aid, conn=conn),
        # VIE PM — Run FTP (umbral run)
        sesion_2(fase, semana_macro, hrv_f, lthr, pace_z2, tss_run//3, vie_s,
                 atleta_id=aid, conn=conn),
        # SÁB — Bike Long (volumen)
        sesion_bike_endurance(fase, hrv_f, lthr_bike, ftp, tss_bike//3, sab, larga=True,
                            atleta_id=aid, conn=conn),
        # DOM — Run Long (volumen)
        sesion_3(fase, hrv_f, lthr, pace_z2, tss_run//3, dom),
    ]

    # ── Ajustar número de sesiones según CUMPLIMIENTO REAL (NO CTL) ──────────
    # SÁB (Bike long) y DOM (Run long) son SIEMPRE obligatorias.
    # El criterio es cuánto y cómo viene cumpliendo el atleta el plan real —
    # no su CTL. Un atleta con CTL bajo puede cumplir perfecto sesiones cortas;
    # otro con CTL alto puede faltar sistemáticamente. Primero se ajusta
    # volumen/carga por sesión; solo se reduce la CANTIDAD de sesiones si el
    # bajo cumplimiento es sostenido en el tiempo (4-8 semanas).
    n_sesiones_obj = 9
    decision_sesiones = 'completo'
    try:
        if conn and aid:
            from noah_nivel_carga import calcular_sesiones_semanales_optimas
            resultado_ses = calcular_sesiones_semanales_optimas(conn, aid, 'triatlon',
                                                                  sesiones_objetivo_max=9)
            n_sesiones_obj = resultado_ses['n_sesiones']
            decision_sesiones = resultado_ses['decision']
    except Exception:
        pass  # Default conservador: 9 sesiones

    # Mapeo de cuántas sesiones corresponden a cada nivel, preservando
    # SÁB y DOM (índices 7, 8) siempre, y priorizando el orden semanal natural
    if n_sesiones_obj >= 9:
        sesiones = todas
    elif n_sesiones_obj >= 7:
        # 7 sesiones: LUN, MAR, MIÉ AM+PM, JUE, SÁB, DOM (sin doble en VIE)
        sesiones = [todas[0], todas[1], todas[2], todas[3],
                    todas[4], todas[7], todas[8]]
    elif n_sesiones_obj >= 6:
        # 6 sesiones: LUN, MAR, MIÉ PM, JUE, SÁB, DOM
        sesiones = [todas[0], todas[1], todas[3], todas[4], todas[7], todas[8]]
    else:
        # Mínimo: 1 por deporte + SÁB + DOM
        sesiones = [todas[0], todas[1], todas[3], todas[7], todas[8]]

    # Nutrición durante — aplica a las 3 disciplinas, en TODAS las sesiones
    sesiones = [_agregar_nutricion_durante(s, atleta_id=aid, conn=conn) for s in sesiones]

    return sesiones, tipo_sem, prioridad


def generar_semana_completa(atleta_config, estado, perfil,
                             semana_macro, fechas, laps_stats=None):
    """
    Generador principal. Detecta el deporte del atleta y genera la semana.
    Para running: 3 sesiones (compatibilidad con ciclo_semanal.py)
    Para triatleta: usa generar_semana_triatleta
    Para ciclista: 3 sesiones de bike
    """
    deporte = atleta_config.get('deporte', 'running')
    lthr     = atleta_config.get('lthr', 162)
    pace_z2  = atleta_config.get('pace_z2_real', 5.55)
    fase     = estado.get('fase', 'A')
    hrv_f    = estado.get('hrv_flag', 'amarillo')
    ctl      = estado.get('ctl', 56.0)
    atl      = estado.get('atl', 60.0)
    tsb      = estado.get('tsb', 0.0)
    hrv_t    = estado.get('hrv_tendencia', 'buena')
    sleep_p  = estado.get('sleep_promedio', 7.0)
    ramp     = estado.get('ramp_rate', 1.05)
    ctl_obj  = perfil.get('ctl_objetivo', 70)

    tipo_sem  = decidir_tipo_semana(ctl, atl, tsb, hrv_t, ramp, sleep_p, ctl_obj, perfil)
    prioridad = decidir_prioridad(fase, ctl, ctl_obj, tipo_sem, hrv_t)

    tss_manual = estado.get('tss_manual')
    tss_base = calcular_tss_objetivo(
        ctl=ctl, ctl_obj=ctl_obj, tipo_sem=tipo_sem,
        perfil=perfil, fase=fase, semana_macro=semana_macro,
        tss_key_max='tss_semana_f1_max', tss_key_min='tss_semana_f1_min',
        tss_default_max=200, tss_default_min=180,
        tss_manual=tss_manual,
    )

    tss1 = round(tss_base * 0.33)
    tss2 = round(tss_base * 0.25)
    tss3 = round(tss_base * 0.42)

    aid  = atleta_config.get('atleta_id') or estado.get('atleta_id')
    conn = atleta_config.get('conn') or estado.get('conn')
    es_rec = (prioridad == 'RECUPERACION')

    if deporte == 'cycling':
        # ── Ciclista: LUN FTP / MIÉ VO2 / VIE Neuro+Regen / SÁB o DOM Long ──
        lthr_bike = atleta_config.get('lthr_bike', 150)
        ftp       = atleta_config.get('ftp', None)
        tss1c = round(tss_base * 0.33)
        tss2c = round(tss_base * 0.25)
        tss3c = round(tss_base * 0.42)
        sesiones = [
            sesion_bike_calidad(fase, semana_macro, hrv_f, lthr_bike, ftp,
                                tss1c, fechas[0], atleta_id=aid, conn=conn),
            sesion_bike_calidad(fase, semana_macro, hrv_f, lthr_bike, ftp,
                                tss2c, fechas[1], atleta_id=aid, conn=conn),
            sesion_bike_endurance(fase, hrv_f, lthr_bike, ftp, tss3c, fechas[2], larga=True,
                                  atleta_id=aid, conn=conn),
        ]
        if len(fechas) >= 4:
            sesiones.append(
                sesion_bike_endurance(fase, hrv_f, lthr_bike, ftp,
                                      round(tss_base*0.35), fechas[3], larga=True,
                                      atleta_id=aid, conn=conn)
            )
        sesiones = [_agregar_nutricion_durante(s, atleta_id=aid, conn=conn) for s in sesiones]
        return sesiones, tipo_sem, prioridad

    elif deporte == 'swimming':
        # ── Nadador: LUN VO2 / MIÉ FTP / VIE VO2 / SÁB Long ──
        lthr_swim = atleta_config.get('lthr_swim', round(lthr * 0.92))
        css_100m  = atleta_config.get('css_100m', 1.75)
        tss1s = round(tss_base * 0.28)
        tss2s = round(tss_base * 0.28)
        tss3s = round(tss_base * 0.44)
        sesiones = [
            sesion_swim_series(fase, hrv_f, lthr_swim, css_100m,
                               tss1s, fechas[0], atleta_id=aid, conn=conn),
            sesion_swim_series(fase, hrv_f, lthr_swim, css_100m,
                               tss2s, fechas[1], atleta_id=aid, conn=conn),
            sesion_swim_endurance(fase, hrv_f, lthr_swim, css_100m,
                                  tss3s, fechas[2], larga=True),
        ]
        if len(fechas) >= 4:
            sesiones.append(
                sesion_swim_endurance(fase, hrv_f, lthr_swim, css_100m,
                                      round(tss_base*0.3), fechas[3], larga=True)
            )
        sesiones = [_agregar_nutricion_durante(s, atleta_id=aid, conn=conn) for s in sesiones]
        return sesiones, tipo_sem, prioridad

    else:
        # ── Runner: estructura semanal FIJA (4-5 sesiones) ──────────────────
        # LUN: Run FTP (umbral/calidad)
        # MIÉ: Run VO2 (calidad)
        # VIE: Run Neuro + Z1/Z2 regen
        # SÁB: Run Long (volumen largo)
        # DOM: Run fácil recuperación (opcional si hay 5 fechas)
        #
        # El CTL bajo NO elimina sesiones — reduce duración/TSS pero mantiene objetivo

        tss_ftp   = round(tss_base * 0.28)   # LUN: FTP — calidad
        tss_vo2   = round(tss_base * 0.22)   # MIÉ: VO2 — calidad
        tss_neuro = round(tss_base * 0.18)   # VIE: Neuro+Regen
        tss_long  = round(tss_base * 0.32)   # SÁB: Long — volumen

        # Factor de escala por CTL bajo (no elimina sesiones, reduce carga)
        if ctl < 25:
            escala = 0.65
        elif ctl < 35:
            escala = 0.80
        else:
            escala = 1.0

        tss_ftp   = round(tss_ftp   * escala)
        tss_vo2   = round(tss_vo2   * escala)
        tss_neuro = round(tss_neuro * escala)
        tss_long  = round(tss_long  * escala)

        # LUN — FTP / umbral (siempre)
        ses_lun = (sesion_1_rec(lthr, pace_z2, fechas[0], fase) if es_rec
                   else sesion_1(fase, semana_macro, hrv_f, lthr, pace_z2,
                                 tss_ftp, fechas[0], laps_stats, atleta_id=aid, conn=conn))

        # MIÉ — Z2 + Neuro (siempre)
        ses_mie = sesion_2(fase, semana_macro, hrv_f, lthr, pace_z2, tss_vo2,
                           fechas[1], atleta_id=aid, conn=conn)

        # SÁB — Long run (siempre — fecha[2])
        # Respetar duración máxima de finde del atleta
        dur_max_fin = atleta_config.get('dur_max_fin')
        if not dur_max_fin:
            disp_fin = _get_disponibilidad(perfil, 'running', es_finde=True)
            dur_max_fin = disp_fin['dur_max']
        ses_sab = sesion_3(fase, hrv_f, lthr, pace_z2, tss_long, fechas[2],
                           dur_max_min=dur_max_fin)

        # 3 sesiones base: LUN / MIÉ / SÁB
        sesiones = [ses_lun, ses_mie, ses_sab]
        sesiones = [_agregar_nutricion_durante(s, atleta_id=aid, conn=conn) for s in sesiones]

        return sesiones, tipo_sem, prioridad


# ─── DISPLAY ──────────────────────────────────────────────────────────────────

def mostrar_prescripcion(sesiones, tipo_sem, prioridad,
                          fase, semana_macro, perfil, semanas_a_carrera):
    print()
    print('=' * 62)
    print('  NOA — PRESCRIPCIÓN SEMANAL')
    print('=' * 62)
    print(f'  Fase    : {fase}  |  Semana {semana_macro} de la fase')
    print(f'  Carrera : {semanas_a_carrera:.1f} semanas restantes')
    print(f'  Semana  : {tipo_sem}  |  Prioridad: {prioridad}')
    print()
    dias = ['LUN','MAR','MIÉ','JUE','VIE','SÁB','DOM']
    km_t = min_t = tss_t = 0
    for ses in sesiones:
        dia_idx = ses.fecha.weekday()
        dia = dias[dia_idx]
        sport_icon = {'running':'🏃','cycling':'🚴','swimming':'🏊'}.get(ses.sport,'•')
        print(f'  ── {dia} {ses.fecha.strftime("%d/%m/%Y")} {sport_icon} ───────────────────────────')
        print(f'  {ses.nombre}')
        for b in ses.bloques:
            print(f'    {b}')
        dur = ses.duracion_total(); dist = ses.distancia_estimada()
        print(f'  → {dur:.0f} min  ~{dist} km  TSS {ses.tss_estimado:.0f}')
        print()
        km_t += dist; min_t += dur; tss_t += ses.tss_estimado
    print('=' * 62)
    print(f'  TOTAL: {km_t:.1f} km  |  {min_t:.0f} min  |  TSS {tss_t:.0f}')
    print('=' * 62)


def calcular_zonas_atleta(lthr, hr_max=None, pace_z2_real=None):
    zonas_atleta = {}
    for clave, z in ZONAS.items():
        if '-' in clave: continue
        hr_min  = round(lthr * z['lthr_min'])
        hr_max_z = round(lthr * z['lthr_max'])
        if hr_max:
            hr_max_z = min(hr_max_z, hr_max)
        entry = {
            'nombre'     : z['nombre'],
            'referencia' : z.get('referencia',''),
            'hr_min'     : hr_min,
            'hr_max'     : hr_max_z,
            'lactato'    : z.get('lactato',''),
            'vo2_pct'    : z.get('vo2_pct',''),
            'descripcion': z.get('descripcion',''),
        }
        if pace_z2_real:
            pf    = PACE_FACTOR.get(clave, 1.0)
            pace  = round(pace_z2_real * pf, 2)
            pm    = int(pace); ps = int((pace - pm)*60)
            entry['pace_ref'] = f'{pm}:{ps:02d} min/km'
        zonas_atleta[clave] = entry
    return zonas_atleta


def mostrar_zonas_atleta(nombre, lthr, hr_max=None, pace_z2_real=None):
    zonas = calcular_zonas_atleta(lthr, hr_max, pace_z2_real)
    print()
    print('=' * 62)
    print(f'  ZONAS DE ENTRENAMIENTO — {nombre}')
    print(f'  LTHR: {lthr} bpm' + (f'  |  FC máx: {hr_max} bpm' if hr_max else ''))
    print('=' * 62)
    for clave, z in zonas.items():
        pace_str = f'  |  pace: {z["pace_ref"]}' if 'pace_ref' in z else ''
        print(f'  {clave}  {z["nombre"]}')
        print(f'      HR: {z["hr_min"]}–{z["hr_max"]} bpm'
              f'  |  VO2: {z["vo2_pct"]}'
              f'  |  Lactato: {z["lactato"]}'
              f'{pace_str}')
        print()
    print('=' * 62)


if __name__ == '__main__':
    from datetime import date, timedelta
    atleta = {'lthr': 162, 'pace_z2_real': 5.55, 'deporte': 'running'}
    estado = {'fase': 'A', 'hrv_flag': 'amarillo', 'ctl': 53.8, 'atl': 45.1,
              'tsb': 8.7, 'hrv_tendencia': 'buena', 'sleep_promedio': 6.5, 'ramp_rate': 1.05}
    perfil = {'ctl_objetivo': 71, 'tss_semana_f1_min': 185, 'tss_semana_f1_max': 210,
              'ramp_rate_max': 1.25, 'sleep_minimo_h': 6.0, 'dias_hrv_rojo_max': 3,
              'f1_z12_pct': 80, 'f1_z34_pct': 15, 'f1_z56_pct': 5}
    hoy = date.today()
    def prox(dow):
        d = (dow - hoy.weekday()) % 7
        if d == 0: d = 7
        return hoy + timedelta(days=d)
    mie = prox(2)
    fechas = [mie, mie + timedelta(days=2), mie + timedelta(days=4)]
    sesiones, tipo_sem, prioridad = generar_semana_completa(atleta, estado, perfil, 1, fechas)
    mostrar_prescripcion(sesiones, tipo_sem, prioridad, 'A', 1, perfil, 25.0)
