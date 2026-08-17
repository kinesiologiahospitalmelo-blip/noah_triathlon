"""
noah_twin.py v7 — Cerebro de NOAH
===================================
OBJETIVO: No prescribir carga. Prescribir SOLUCIONES.
"Tu limitante es X. Esto es lo que te hace mas rapido para el dia de la carrera."

CARRERAS SOPORTADAS:
  Running: 5K, 10K, 21K (media maraton), maraton (42K)
  Triatlon: sprint, olimpico, 70.3 (medio ironman), ironman
  Cycling: crono, ruta, mtb (Rio Pinto 120km), granfondo
  Aguas abiertas: 1.5K, 3K, 5K, 10K

MODELOS: Banister, Coggan, Coyle, Hickson, Seiler, Billat, Paavolainen,
         Tabata, Gabbett, Mujika, Bosquet, Plews, Foster, Romijn, Joyner
"""

import math, random
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import date, timedelta

# ═══════════════════════════════════════════════════════════════
# CONSTANTES CIENTIFICAS
# ═══════════════════════════════════════════════════════════════

TAU_CTL = 42.0  # Banister/Coggan
TAU_ATL = 7.0

SISTEMAS = ['aerobico_central', 'aerobico_periferico', 'umbral', 'neuromuscular', 'anaerobico']

# Coyle 1984: half-life de perdida
HALFLIFE_PERDIDA = {
    'aerobico_central': 56, 'aerobico_periferico': 12,
    'umbral': 21, 'neuromuscular': 10, 'anaerobico': 7}

# Hickson 1977 + Holloszy 1967 + Billat 2001 + Paavolainen 1999 + Tabata 1996
GANANCIA_SEMANAL = {
    'aerobico_central': 0.008, 'aerobico_periferico': 0.015,
    'umbral': 0.020, 'neuromuscular': 0.025, 'anaerobico': 0.030}

# Que zona estimula que sistema (Seiler 2010, Issurin 2008)
ESTIMULO = {
    1: {'aerobico_central':.4,'aerobico_periferico':.3,'umbral':.0,'neuromuscular':.0,'anaerobico':.0},
    2: {'aerobico_central':.8,'aerobico_periferico':.7,'umbral':.1,'neuromuscular':.0,'anaerobico':.0},
    3: {'aerobico_central':.5,'aerobico_periferico':.8,'umbral':.7,'neuromuscular':.2,'anaerobico':.1},
    4: {'aerobico_central':.3,'aerobico_periferico':.6,'umbral':1.,'neuromuscular':.5,'anaerobico':.3},
    5: {'aerobico_central':.2,'aerobico_periferico':.3,'umbral':.6,'neuromuscular':.9,'anaerobico':.8},
    6: {'aerobico_central':.1,'aerobico_periferico':.1,'umbral':.2,'neuromuscular':1.,'anaerobico':1.},
}

# Pesos de cada sistema por carrera (Joyner & Coyle 2008, Seiler 2010)
PESOS_CARRERA = {
    # Running
    '5K':       {'aerobico_central':.20,'aerobico_periferico':.20,'umbral':.25,'neuromuscular':.20,'anaerobico':.15},
    '10K':      {'aerobico_central':.25,'aerobico_periferico':.25,'umbral':.25,'neuromuscular':.15,'anaerobico':.10},
    '21K':      {'aerobico_central':.30,'aerobico_periferico':.30,'umbral':.25,'neuromuscular':.10,'anaerobico':.05},
    'maraton':  {'aerobico_central':.35,'aerobico_periferico':.30,'umbral':.25,'neuromuscular':.08,'anaerobico':.02},
    # Triatlon
    'sprint':   {'aerobico_central':.20,'aerobico_periferico':.25,'umbral':.25,'neuromuscular':.18,'anaerobico':.12},
    'olimpico': {'aerobico_central':.25,'aerobico_periferico':.30,'umbral':.25,'neuromuscular':.12,'anaerobico':.08},
    '70.3':     {'aerobico_central':.30,'aerobico_periferico':.30,'umbral':.25,'neuromuscular':.10,'anaerobico':.05},
    'ironman':  {'aerobico_central':.35,'aerobico_periferico':.30,'umbral':.25,'neuromuscular':.08,'anaerobico':.02},
    # Cycling
    'crono':    {'aerobico_central':.20,'aerobico_periferico':.20,'umbral':.30,'neuromuscular':.15,'anaerobico':.15},
    'ruta':     {'aerobico_central':.25,'aerobico_periferico':.25,'umbral':.25,'neuromuscular':.15,'anaerobico':.10},
    'mtb':      {'aerobico_central':.20,'aerobico_periferico':.25,'umbral':.20,'neuromuscular':.20,'anaerobico':.15},
    'granfondo':{'aerobico_central':.30,'aerobico_periferico':.30,'umbral':.25,'neuromuscular':.10,'anaerobico':.05},
    # Aguas abiertas
    'oa_1500':  {'aerobico_central':.25,'aerobico_periferico':.25,'umbral':.25,'neuromuscular':.15,'anaerobico':.10},
    'oa_3K':    {'aerobico_central':.30,'aerobico_periferico':.30,'umbral':.25,'neuromuscular':.10,'anaerobico':.05},
    'oa_5K':    {'aerobico_central':.30,'aerobico_periferico':.30,'umbral':.25,'neuromuscular':.10,'anaerobico':.05},
    'oa_10K':   {'aerobico_central':.35,'aerobico_periferico':.30,'umbral':.25,'neuromuscular':.07,'anaerobico':.03},
}

# Taper en dias (Mujika 2003, Bosquet 2007)
TAPER_DIAS = {
    '5K':7, '10K':14, '21K':18, 'maraton':21,
    'sprint':7, 'olimpico':14, '70.3':18, 'ironman':21,
    'crono':7, 'ruta':14, 'mtb':14, 'granfondo':14,
    'oa_1500':7, 'oa_3K':10, 'oa_5K':14, 'oa_10K':18}

# Distancia de carrera en km (para referencia)
DISTANCIA_CARRERA = {
    '5K':5, '10K':10, '21K':21.1, 'maraton':42.2,
    'sprint':25.75, 'olimpico':51.5, '70.3':113, 'ironman':226,
    'crono':40, 'ruta':160, 'mtb':120, 'granfondo':160,
    'oa_1500':1.5, 'oa_3K':3, 'oa_5K':5, 'oa_10K':10}


# ═══════════════════════════════════════════════════════════════
# PERFIL Y ESTADO
# ═══════════════════════════════════════════════════════════════

@dataclass
class PerfilTwin:
    nombre: str = 'Twin'
    edad: int = 30
    sexo: str = 'M'
    peso_kg: float = 70.0
    deporte: str = 'running'
    lthr_run: int = 160
    lthr_bike: int = 155
    lthr_swim: int = 145
    pace_umbral_run: float = 5.5
    ftp_watts: int = 200
    css_100m: float = 1.8
    ctl_inicial: float = 40.0
    sistemas_ini: Dict[str,float] = field(default_factory=lambda:{s:50 for s in SISTEMAS})
    resp_volumen: float = 1.0
    resp_intensidad: float = 1.0
    tasa_recuperacion: float = 1.0
    umbral_lesion: float = 1.5
    horas_sueno: float = 7.5
    calidad_sueno: float = 0.75
    estres: float = 0.3
    nutricion: float = 0.8
    anos_exp: int = 3
    zona_vulnerable: str = ''
    max_ses_semana: int = 6
    horas_disp: float = 10.0
    carrera: str = ''
    carrera_tipo: str = ''
    carrera_semanas: int = 0


@dataclass
class Estado:
    fecha: date = field(default_factory=date.today)
    ctl: float = 40.0
    atl: float = 40.0
    tsb: float = 0.0
    tss: float = 0.0
    sist: Dict[str,float] = field(default_factory=lambda:{s:50.0 for s in SISTEMAS})
    limitante: str = ''
    hrv: float = 55.0
    hrv_base: float = 55.0
    hanna: float = 65.0
    gluc: float = 85.0
    acwr: float = 1.0
    acwr_n: int = 0
    lesionado: bool = False
    dias_les: int = 0
    pace: float = 5.5
    ftp: float = 200.0
    rend: float = 50.0
    entreno: bool = False
    desc: str = ''


# ═══════════════════════════════════════════════════════════════
# DIAGNOSTICO DE LIMITANTES
# ═══════════════════════════════════════════════════════════════

def diagnosticar_limitante(sistemas, carrera_tipo, perfil=None):
    """
    Identifica el sistema fisiologico que mas frena al atleta para su carrera.
    Retorna: (limitante, deficit, explicacion)
    """
    pesos = PESOS_CARRERA.get(carrera_tipo, {s: 0.2 for s in SISTEMAS})
    deficits = {}
    for s in SISTEMAS:
        deficit = (100 - sistemas[s]) * pesos.get(s, 0.2)
        deficits[s] = deficit

    lim = max(deficits, key=deficits.get)

    explicaciones = {
        'aerobico_central': 'El corazon no bombea suficiente sangre. Necesita volumen Z2 largo.',
        'aerobico_periferico': 'Las mitocondrias no extraen suficiente O2. Necesita volumen Z2 + algo de Z3.',
        'umbral': 'No puede sostener el ritmo de carrera. Necesita trabajo Z3-Z4 (sweet spot, tempo).',
        'neuromuscular': 'Le falta economia y potencia. Necesita series cortas Z5 y fuerza.',
        'anaerobico': 'No tolera esfuerzos sobre umbral. Necesita repeticiones Z5-Z6.',
    }

    return lim, round(deficits[lim], 1), explicaciones.get(lim, '')


def prescribir_sesion(limitante, fase, deporte, nivel_sist):
    """
    Dado el sistema limitante y la fase, prescribe la sesion especifica.
    No TSS generico — sesiones concretas.
    """
    prescripciones = {
        'aerobico_central': {
            'A': {'desc': 'Fondo largo Z2 (el mas largo posible)', 'zona': 2, 'tipo': 'long'},
            'T': {'desc': 'Fondo medio Z2 con 10min Z3 al final', 'zona': 2, 'tipo': 'long'},
            'R': {'desc': 'Fondo corto Z2 regenerativo', 'zona': 1, 'tipo': 'easy'},
        },
        'aerobico_periferico': {
            'A': {'desc': 'Tempo Z2-Z3 progresivo 50-60min', 'zona': 3, 'tipo': 'quality'},
            'T': {'desc': 'Intervalos Z3 (3x15min rec 3min)', 'zona': 3, 'tipo': 'quality'},
            'R': {'desc': 'Z2 suave 40min', 'zona': 2, 'tipo': 'easy'},
        },
        'umbral': {
            'A': {'desc': 'Sweet spot Z4 progresivo (2x20min)', 'zona': 4, 'tipo': 'quality'},
            'T': {'desc': 'Intervalos Z4 (4x8min rec 3min)', 'zona': 4, 'tipo': 'quality'},
            'R': {'desc': 'Z2 con 2x5min Z3', 'zona': 2, 'tipo': 'easy'},
        },
        'neuromuscular': {
            'A': {'desc': 'Strides + cuestas cortas al final de Z2', 'zona': 2, 'tipo': 'quality'},
            'T': {'desc': 'Series Z5 (5x1000m rec 2min)', 'zona': 5, 'tipo': 'quality'},
            'R': {'desc': 'Z2 con 6x100m activaciones', 'zona': 2, 'tipo': 'easy'},
        },
        'anaerobico': {
            'A': {'desc': 'No priorizar en acumulacion', 'zona': 2, 'tipo': 'easy'},
            'T': {'desc': 'Repeticiones Z6 (8x400m rec 3min)', 'zona': 6, 'tipo': 'quality'},
            'R': {'desc': 'Descanso completo', 'zona': 0, 'tipo': 'rest'},
        },
    }

    p = prescripciones.get(limitante, prescripciones['umbral'])
    return p.get(fase, p['A'])


# ═══════════════════════════════════════════════════════════════
# MODELO FISIOLOGICO
# ═══════════════════════════════════════════════════════════════

class Modelo:
    def __init__(self, perfil):
        self.p = perfil
        hb = 65 - (perfil.edad-25)*0.4
        if perfil.sexo == 'F': hb *= 0.92
        hb *= (0.85 + perfil.ctl_inicial/250)
        hb = max(30, min(110, hb))
        self.estado = Estado(
            ctl=perfil.ctl_inicial, atl=perfil.ctl_inicial,
            sist=dict(perfil.sistemas_ini), hrv=hb, hrv_base=hb,
            pace=perfil.pace_umbral_run, ftp=float(perfil.ftp_watts))
        self.historial = []
        self.tss_7d = [perfil.ctl_inicial] * 7
        self.aprendizaje = []  # Registro de decisiones y resultados

    def simular_dia(self, fecha, sesion=None):
        p, prev = self.p, self.estado
        e = Estado(fecha=fecha, ctl=prev.ctl, atl=prev.atl,
            sist=dict(prev.sist), hrv_base=prev.hrv_base,
            gluc=prev.gluc, pace=prev.pace, ftp=prev.ftp, acwr_n=prev.acwr_n)

        if prev.lesionado and prev.dias_les > 0:
            e.lesionado, e.dias_les = True, prev.dias_les - 1
            if e.dias_les <= 0: e.lesionado = False
            sesion = None

        tss = 0.0
        zona = 0
        if sesion and sesion.get('cumplida', True) and sesion.get('zona', 0) > 0:
            e.entreno = True
            e.desc = sesion.get('desc', '')
            tss = sesion.get('tss', 0)
            zona = sesion.get('zona', 2)
            dur = sesion.get('dur', 45)

            g_r = {1:.2,2:.5,3:1,4:1.6,5:2,6:2.5}
            e.gluc = max(5, prev.gluc - g_r.get(zona, 1) * dur / 10)

            est = ESTIMULO.get(zona, ESTIMULO[2])
            for s in SISTEMAS:
                if est[s] > 0:
                    gain = GANANCIA_SEMANAL[s] / 7
                    indiv = p.resp_intensidad if zona >= 4 else p.resp_volumen
                    headroom = (100 - prev.sist[s]) / 100
                    dur_f = min(1.5, dur / 45) if zona <= 2 else 1.0
                    g = gain * est[s] * indiv * headroom * p.nutricion * p.calidad_sueno * dur_f
                    e.sist[s] = min(100, prev.sist[s] + g * 100)
        else:
            e.entreno = False
            baseline = 20 + p.anos_exp * 2
            for s in SISTEMAS:
                hl = HALFLIFE_PERDIDA[s]
                if prev.sist[s] > baseline:
                    e.sist[s] = max(baseline, prev.sist[s] - (prev.sist[s]-baseline)*math.log(2)/hl)

        e.tss = tss
        e.ctl = prev.ctl + (tss - prev.ctl) / TAU_CTL
        e.atl = prev.atl + (tss - prev.atl) / TAU_ATL
        e.tsb = e.ctl - e.atl
        self.tss_7d.pop(0); self.tss_7d.append(tss)
        e.acwr = round(sum(self.tss_7d)/7/max(e.ctl,10), 2)
        e.acwr_n = (prev.acwr_n+1) if e.acwr > p.umbral_lesion else 0

        d = -3*max(0, e.atl/max(e.ctl,20)-0.8) - 2*p.estres
        d += (p.tasa_recuperacion if not e.entreno else -0.5)
        e.hrv = max(25, e.hrv_base + d + random.gauss(0, 2.5))
        e.hrv_base = prev.hrv_base + (e.ctl - prev.ctl) * 0.02
        e.gluc = min(100, e.gluc + 25*p.nutricion*(0.5 if e.entreno else 1))
        h1 = min(50, max(0, (e.hrv/max(e.hrv_base,30))*25+15))
        h2 = max(0, min(25, 25 - max(0, e.atl-e.ctl)*1.5))
        e.hanna = min(100, max(5, round(h1 + p.calidad_sueno*25 + h2)))

        r = 0.003
        if e.acwr_n >= 3: r += (e.acwr_n-2)*0.015
        r /= (1+p.anos_exp*0.03)
        if random.random() < min(0.1, r) and e.entreno and e.acwr_n >= 3:
            e.lesionado = True; e.dias_les = random.randint(7,21)

        pesos = PESOS_CARRERA.get(p.carrera_tipo, {s:.2 for s in SISTEMAS})
        deficits = {s: (100-e.sist[s])*pesos.get(s,.2) for s in SISTEMAS}
        e.limitante = max(deficits, key=deficits.get)
        e.rend = sum(e.sist[s]*pesos.get(s,.2) for s in SISTEMAS)

        rr = e.rend / max(prev.rend, 1)
        e.pace = max(3, prev.pace / max(rr, 0.95))
        e.ftp = min(450, prev.ftp * min(rr, 1.05))

        self.historial.append(e)
        self.estado = e
        return e


# ═══════════════════════════════════════════════════════════════
# PLAN POR LIMITANTE (el cerebro de NOAH)
# ═══════════════════════════════════════════════════════════════

def plan_noah(perfil, estado, semana):
    """
    NOAH prescribe por limitante. No por carga generica.
    Mira que sistema frena al atleta y prescribe la solucion.
    """
    # Determinar fase
    taper_d = TAPER_DIAS.get(perfil.carrera_tipo, 14)
    taper_s = max(1, taper_d // 7)
    sem_para = perfil.carrera_semanas - semana if perfil.carrera_semanas > 0 else 999

    if 0 < sem_para <= taper_s:
        fase = 'R'  # Taper = reduccion
    elif sem_para == 0:
        fase = 'R'
    else:
        sem_meso = semana % 4
        fase = {0:'A', 1:'A', 2:'T', 3:'R'}[sem_meso]

    # DECISION: no entrenes si Hanna < 25
    if estado.hanna < 25:
        return {0: {'desc':'DESCANSO — Hanna critico','zona':0,'tss':0,'dur':0,'tipo':'rest'}}

    # Diagnosticar limitante
    lim, deficit, explicacion = diagnosticar_limitante(estado.sist, perfil.carrera_tipo)

    # TSS semanal
    ctl_obj = perfil.ctl_inicial * 1.08
    if fase == 'R' and sem_para <= taper_s:
        pct = 0.55 + 0.45 * ((sem_para-1)/max(taper_s,1)) if sem_para > 0 else 0.45
        tss_sem = round(ctl_obj * 7 * pct)
    else:
        f = {'A':1.0, 'T':1.10, 'R':0.70}[fase]
        tss_sem = round(ctl_obj * 7 * f)

    # Prescribir sesion clave (ataca la limitante)
    sesion_clave = prescribir_sesion(lim, fase, perfil.deporte, estado.sist)
    n = perfil.max_ses_semana
    tss_per = tss_sem / max(n, 1)

    plan = {}
    if perfil.deporte == 'triatlon':
        sports = ['swimming','cycling','running','cycling','running','cycling','running']
        for i in range(min(7, n)):
            if i in (1, 2):  # Sesiones clave
                plan[i] = {'sport':sports[i], 'desc':f'{sports[i]}: {sesion_clave["desc"]}',
                    'zona':sesion_clave['zona'], 'tss':round(tss_per*1.4), 'dur':60, 'tipo':'quality'}
            elif i == 5:  # Bike largo
                plan[i] = {'sport':'cycling', 'desc':'Bike largo Z2 (base aerobica)',
                    'zona':2, 'tss':round(tss_per*2.0), 'dur':150, 'tipo':'long'}
            elif i == 6:  # Run largo
                plan[i] = {'sport':'running', 'desc':'Run largo Z2',
                    'zona':2, 'tss':round(tss_per*1.6), 'dur':80, 'tipo':'long'}
            else:
                plan[i] = {'sport':sports[i], 'desc':f'{sports[i]}: Z2 facil',
                    'zona':2, 'tss':round(tss_per*0.5), 'dur':40, 'tipo':'easy'}
    elif perfil.deporte == 'cycling':
        for i in range(min(6, n)):
            if i in (1, 3):
                plan[i] = {'sport':'cycling', 'desc':sesion_clave['desc'],
                    'zona':sesion_clave['zona'], 'tss':round(tss_per*1.4), 'dur':75, 'tipo':'quality'}
            elif i == 5:
                plan[5] = {'sport':'cycling', 'desc':'Fondo largo Z2',
                    'zona':2, 'tss':round(tss_per*2.5), 'dur':180, 'tipo':'long'}
            else:
                plan[i] = {'sport':'cycling', 'desc':'Rodaje Z2',
                    'zona':2, 'tss':round(tss_per*0.6), 'dur':60, 'tipo':'easy'}
    else:  # running
        dias = [0,2,4,5][:n]
        for j, d in enumerate(dias):
            if j == 1:
                plan[d] = {'sport':'running', 'desc':sesion_clave['desc'],
                    'zona':sesion_clave['zona'], 'tss':round(tss_per*1.4), 'dur':50, 'tipo':'quality'}
            elif d == 5:
                plan[d] = {'sport':'running', 'desc':'Fondo largo Z2',
                    'zona':2, 'tss':round(tss_per*1.8), 'dur':80, 'tipo':'long'}
            else:
                plan[d] = {'sport':'running', 'desc':'Facil Z2',
                    'zona':2, 'tss':round(tss_per*0.6), 'dur':45, 'tipo':'easy'}

    return plan


# Estrategias genericas para comparar
def plan_polarizado(p, e, s):
    return _plan_generico(p, e, s, z_hard=5, pct_easy=0.80, desc='Intervalos Z5')
def plan_piramidal(p, e, s):
    return _plan_generico(p, e, s, z_hard=3, pct_easy=0.65, desc='Tempo Z3')
def plan_threshold(p, e, s):
    return _plan_generico(p, e, s, z_hard=4, pct_easy=0.50, desc='Sweet spot Z4')

def _plan_generico(perfil, estado, semana, z_hard, pct_easy, desc):
    ctl_obj = perfil.ctl_inicial * 1.08
    td = TAPER_DIAS.get(perfil.carrera_tipo, 14)
    ts = max(1, td//7)
    sp = perfil.carrera_semanas - semana if perfil.carrera_semanas > 0 else 999
    if 0 < sp <= ts:
        f = 0.55 + 0.45*((sp-1)/max(ts,1))
    elif sp == 0:
        f = 0.45
    else:
        f = {0:1,1:1.05,2:1.1,3:.7}[semana%4]
    tss_sem = round(ctl_obj*7*f)
    n = perfil.max_ses_semana
    tp = tss_sem/max(n,1)
    n_hard = max(1, round(n*(1-pct_easy)))

    plan = {}
    if perfil.deporte == 'triatlon':
        sp_list = ['swimming','cycling','running','cycling','running','cycling','running']
        for i in range(min(7, n)):
            if i == 5:
                plan[i] = {'sport':sp_list[i],'desc':'Largo Z2','zona':2,'tss':round(tp*2),'dur':150,'tipo':'long'}
            elif i == 6:
                plan[i] = {'sport':sp_list[i],'desc':'Largo Z2','zona':2,'tss':round(tp*1.6),'dur':80,'tipo':'long'}
            elif i < n_hard:
                plan[i] = {'sport':sp_list[i],'desc':desc,'zona':z_hard,'tss':round(tp*1.4),'dur':60,'tipo':'quality'}
            else:
                plan[i] = {'sport':sp_list[i],'desc':'Z2 facil','zona':2,'tss':round(tp*0.5),'dur':40,'tipo':'easy'}
    elif perfil.deporte == 'cycling':
        for i in range(min(6, n)):
            if i == n-1:
                plan[5] = {'sport':'cycling','desc':'Largo Z2','zona':2,'tss':round(tp*2.5),'dur':180,'tipo':'long'}
            elif i < n_hard:
                plan[i] = {'sport':'cycling','desc':desc,'zona':z_hard,'tss':round(tp*1.4),'dur':75,'tipo':'quality'}
            else:
                plan[i] = {'sport':'cycling','desc':'Z2','zona':2,'tss':round(tp*0.6),'dur':60,'tipo':'easy'}
    else:
        dias = [0,2,4,5][:n]
        for j, d in enumerate(dias):
            if d == 5:
                plan[d] = {'sport':'running','desc':'Largo Z2','zona':2,'tss':round(tp*1.8),'dur':80,'tipo':'long'}
            elif j < n_hard:
                plan[d] = {'sport':'running','desc':desc,'zona':z_hard,'tss':round(tp*1.4),'dur':50,'tipo':'quality'}
            else:
                plan[d] = {'sport':'running','desc':'Z2','zona':2,'tss':round(tp*0.6),'dur':45,'tipo':'easy'}
    return plan


# ═══════════════════════════════════════════════════════════════
# MOTOR + APRENDIZAJE
# ═══════════════════════════════════════════════════════════════

class Motor:
    def __init__(self, perfil):
        self.perfil = perfil
        self.modelo = Modelo(perfil)
        self.sem = 0
        self.log_semanal = []

    def simular(self, semanas=12, plan_func=None, verbose=True):
        f = plan_func or plan_noah
        nom = getattr(f,'__name__','?')
        if verbose:
            cr = f' → {self.perfil.carrera}({self.perfil.carrera_tipo}, {DISTANCIA_CARRERA.get(self.perfil.carrera_tipo,"?")}km)' if self.perfil.carrera else ''
            print(f'\n{"="*80}')
            print(f'  {self.perfil.nombre} [{nom}]{cr}')
            print(f'  Sistemas: {" ".join(f"{s[:4]}={v:.0f}" for s,v in self.perfil.sistemas_ini.items())}')
            print(f'{"="*80}')

        fecha = date.today()
        for s in range(semanas):
            self.sem = s + 1
            plan = f(self.perfil, self.modelo.estado, s)
            tss_s = 0
            for d in range(7):
                ses = plan.get(d)
                if ses:
                    p = 0.93 if self.modelo.estado.hanna > 40 else 0.70
                    ses['cumplida'] = random.random() < p
                self.modelo.simular_dia(fecha+timedelta(days=s*7+d), ses)
                tss_s += self.modelo.estado.tss

            # Aprendizaje: registrar que hizo y que paso
            e = self.modelo.estado
            self.log_semanal.append({
                'sem': s+1, 'limitante': e.limitante,
                'rend': e.rend, 'ctl': e.ctl, 'hanna': e.hanna,
                'sist': dict(e.sist), 'tss': tss_s,
            })

            if verbose:
                ss = ' '.join(f'{s[:3]}={e.sist[s]:.0f}' for s in SISTEMAS)
                l = ' LES' if e.lesionado else ''
                t = ''
                if self.perfil.carrera_semanas > 0:
                    r = self.perfil.carrera_semanas - s
                    if r > 0: t = f' [{r}s]'
                    elif r == 0: t = ' [CARRERA]'
                print(f'  S{s+1:2d} Lim={e.limitante[:5]:5s} Rend={e.rend:5.1f} '
                      f'CTL={e.ctl:5.1f} TSB={e.tsb:+5.1f} HL={e.hanna:3.0f} '
                      f'TSS={tss_s:4.0f} {ss}{l}{t}')

        # Evaluacion final
        if verbose:
            self._evaluar()

        return self._rep()

    def _evaluar(self):
        """Evalua semana a semana: la limitante mejoro?"""
        if len(self.log_semanal) < 2: return
        print(f'\n  APRENDIZAJE SEMANAL:')
        for i in range(1, len(self.log_semanal)):
            prev, curr = self.log_semanal[i-1], self.log_semanal[i]
            lim = prev['limitante']
            antes = prev['sist'][lim]
            despues = curr['sist'][lim]
            delta = despues - antes
            ok = '✓' if delta > 0 else '✗'
            print(f'    S{curr["sem"]:2d}: Limitante era {lim[:8]:8s} ({antes:.0f}→{despues:.0f} {delta:+.1f}) {ok}')

    def _rep(self):
        h = self.modelo.historial
        if not h: return {}
        i, f = h[0], h[-1]
        tc = None
        if self.perfil.carrera_semanas > 0:
            dc = self.perfil.carrera_semanas * 7
            if dc < len(h): tc = round(h[dc-1].tsb, 1)
        return {
            'nombre': self.perfil.nombre,
            'delta_ctl': round(f.ctl-i.ctl,1),
            'rend_i': round(i.rend,1), 'rend_f': round(f.rend,1),
            'delta_rend': round(f.rend-i.rend,1),
            'pace_f': round(f.pace,2), 'ftp_f': round(f.ftp),
            'limitante_f': f.limitante,
            'sist_f': {s:round(f.sist[s],1) for s in SISTEMAS},
            'hanna_avg': round(sum(e.hanna for e in h)/len(h)),
            'lesiones': any(e.lesionado for e in h),
            'tsb_carrera': tc}


def comparar(perfil, semanas=12, seed=42):
    ests = {'NOAH(limitante)':plan_noah, 'polarizado':plan_polarizado,
            'piramidal':plan_piramidal, 'threshold':plan_threshold}
    res = {}
    for n, f in ests.items():
        random.seed(seed)
        res[n] = Motor(perfil).simular(semanas, f, verbose=False)

    dist_km = DISTANCIA_CARRERA.get(perfil.carrera_tipo, 0)
    print(f'\n{"="*80}')
    print(f'  COMPARATIVA: {perfil.nombre}')
    if perfil.carrera:
        print(f'  Carrera: {perfil.carrera} ({perfil.carrera_tipo}, {dist_km}km)')
    print(f'{"="*80}')
    print(f'  {"Estrategia":<18s} {"ΔRend":>6s} {"ΔCTL":>6s} {"Pace":>6s} {"FTP":>5s} {"HL":>4s} {"TSB_c":>6s} {"Limitante":>8s} {"Les":>4s}')
    print(f'  {"-"*65}')
    for n, r in res.items():
        tc = f'{r["tsb_carrera"]:>+5.1f}' if r.get("tsb_carrera") is not None else '   --'
        print(f'  {n:<18s} {r["delta_rend"]:>+5.1f} {r["delta_ctl"]:>+5.1f} {r["pace_f"]:>5.2f} '
              f'{r["ftp_f"]:>4.0f} {r["hanna_avg"]:>3.0f} {tc:>6s} {r["limitante_f"][:8]:>8s} '
              f'{"SI" if r["lesiones"] else "no":>4s}')

    mejor = max(res.items(), key=lambda x: x[1]['delta_rend'])
    print(f'\n  MEJOR: {mejor[0]} (ΔRend {mejor[1]["delta_rend"]:+.1f})')
    if perfil.carrera_semanas > 0:
        mc = max(res.items(), key=lambda x: x[1].get('tsb_carrera') or -99)
        if mc[1].get('tsb_carrera') is not None:
            print(f'  MEJOR carrera: {mc[0]} (TSB {mc[1]["tsb_carrera"]:+.1f})')

    print(f'\n  SISTEMAS FINALES ({mejor[0]}):')
    for s in SISTEMAS:
        v = mejor[1]['sist_f'][s]
        bar = '█'*int(v/5) + '░'*(20-int(v/5))
        print(f'    {s:<22s} {bar} {v:.0f}')
    return res


# ═══════════════════════════════════════════════════════════════
# PERFILES
# ═══════════════════════════════════════════════════════════════

def crear_twins():
    return {
        'rodrigo': PerfilTwin(
            nombre='Rodrigo', edad=40, sexo='M', peso_kg=80,
            deporte='triatlon', lthr_run=160, lthr_bike=160,
            pace_umbral_run=5.71, ftp_watts=156, css_100m=1.8, ctl_inicial=68,
            sistemas_ini={'aerobico_central':65,'aerobico_periferico':60,'umbral':55,'neuromuscular':50,'anaerobico':45},
            resp_volumen=1.0, resp_intensidad=1.0, tasa_recuperacion=0.9,
            calidad_sueno=0.75, estres=0.3, nutricion=0.8, anos_exp=8, max_ses_semana=6),
        'silvina': PerfilTwin(
            nombre='Silvina', edad=45, sexo='F', peso_kg=60,
            deporte='running', lthr_run=157, pace_umbral_run=6.75, ctl_inicial=30,
            sistemas_ini={'aerobico_central':45,'aerobico_periferico':40,'umbral':35,'neuromuscular':30,'anaerobico':25},
            resp_volumen=1.1, resp_intensidad=0.8, tasa_recuperacion=0.85,
            calidad_sueno=0.7, estres=0.35, nutricion=0.75, anos_exp=5, max_ses_semana=5,
            carrera='10K Otono', carrera_tipo='10K', carrera_semanas=8),
        'jimena': PerfilTwin(
            nombre='Jimena', edad=35, sexo='F', peso_kg=65,
            deporte='triatlon', lthr_run=176, lthr_bike=160, lthr_swim=162,
            pace_umbral_run=5.09, ftp_watts=151, css_100m=1.85, ctl_inicial=68,
            sistemas_ini={'aerobico_central':60,'aerobico_periferico':65,'umbral':55,'neuromuscular':50,'anaerobico':45},
            resp_volumen=1.0, resp_intensidad=1.1, tasa_recuperacion=1.0,
            calidad_sueno=0.8, estres=0.25, nutricion=0.85, anos_exp=6, max_ses_semana=7,
            carrera='70.3 Mar del Plata', carrera_tipo='70.3', carrera_semanas=16),
        'silvina_21k': PerfilTwin(
            nombre='Silvina (21K)', edad=45, sexo='F', peso_kg=60,
            deporte='running', lthr_run=157, pace_umbral_run=6.75, ctl_inicial=35,
            sistemas_ini={'aerobico_central':50,'aerobico_periferico':45,'umbral':40,'neuromuscular':30,'anaerobico':25},
            resp_volumen=1.1, resp_intensidad=0.8, tasa_recuperacion=0.85,
            calidad_sueno=0.7, estres=0.35, nutricion=0.75, anos_exp=5, max_ses_semana=5,
            carrera='Media Maraton', carrera_tipo='21K', carrera_semanas=16),
        'principiante': PerfilTwin(
            nombre='Ana (5K)', edad=35, sexo='F', peso_kg=62,
            deporte='running', lthr_run=155, pace_umbral_run=6.8, ctl_inicial=20,
            sistemas_ini={'aerobico_central':30,'aerobico_periferico':25,'umbral':20,'neuromuscular':20,'anaerobico':15},
            resp_volumen=1.1, resp_intensidad=0.7, tasa_recuperacion=0.8,
            horas_sueno=6.5, calidad_sueno=0.65, estres=0.5, nutricion=0.65,
            anos_exp=1, zona_vulnerable='rodilla', max_ses_semana=4,
            carrera='5K', carrera_tipo='5K', carrera_semanas=12),
        'ciclista': PerfilTwin(
            nombre='Gonzalo (Rio Pinto)', edad=30, sexo='M', peso_kg=72,
            deporte='cycling', lthr_bike=172, pace_umbral_run=4.3, ftp_watts=310, ctl_inicial=85,
            sistemas_ini={'aerobico_central':80,'aerobico_periferico':75,'umbral':70,'neuromuscular':65,'anaerobico':60},
            resp_volumen=1.3, resp_intensidad=1.3, tasa_recuperacion=1.3,
            horas_sueno=8.5, calidad_sueno=0.9, estres=0.1, nutricion=0.95,
            anos_exp=12, max_ses_semana=6,
            carrera='Rio Pinto MTB', carrera_tipo='mtb', carrera_semanas=10),
        'ironman': PerfilTwin(
            nombre='Jimena (Ironman)', edad=35, sexo='F', peso_kg=65,
            deporte='triatlon', lthr_run=176, lthr_bike=160, lthr_swim=162,
            pace_umbral_run=5.09, ftp_watts=151, css_100m=1.85, ctl_inicial=70,
            sistemas_ini={'aerobico_central':62,'aerobico_periferico':65,'umbral':55,'neuromuscular':48,'anaerobico':40},
            resp_volumen=1.0, resp_intensidad=1.1, tasa_recuperacion=1.0,
            calidad_sueno=0.8, estres=0.25, nutricion=0.85, anos_exp=6, max_ses_semana=8,
            horas_disp=14,
            carrera='Ironman', carrera_tipo='ironman', carrera_semanas=24),
    }


if __name__ == '__main__':
    twins = crear_twins()

    # Simulacion detallada NOAH para Jimena 70.3
    random.seed(42)
    Motor(twins['jimena']).simular(semanas=16, plan_func=plan_noah, verbose=True)

    # Comparativas
    for nombre in ['jimena', 'silvina', 'silvina_21k', 'ciclista', 'principiante', 'ironman']:
        comparar(twins[nombre], semanas=min(16, twins[nombre].carrera_semanas or 12))
