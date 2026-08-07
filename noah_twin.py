"""
noah_twin.py v5 — Calibracion final
=====================================
FIXES:
  - Taper anula mesociclo (no doble reduccion)
  - Taper por distancia de carrera (Mujika 2003/Bosquet 2007)
  - Adaptacion 3x mas rapida (~2-3%/mes con carga adecuada, Coyle 1988)
  - Semana R del mesociclo a 70% (era 60%)
  - TSS escala mejor: grow factor 1.08 (era 1.05)
"""

import math, random
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from datetime import date, timedelta


# Taper por tipo de carrera (Mujika 2003, Bosquet 2007)
TAPER_SEMANAS = {
    '5K': 1, '10K': 2, '21K': 3, 'half': 3, 'maraton': 3, 'marathon': 3,
    'sprint': 1, 'olimpico': 2, 'half_ironman': 3, 'ironman': 3,
    'mtb': 2, 'ruta': 2, 'crono': 1,
}


@dataclass
class PerfilTwin:
    nombre: str = 'Twin'
    edad: int = 30
    sexo: str = 'M'
    peso_kg: float = 70.0
    deporte: str = 'running'
    hr_max: int = 190
    hr_reposo: int = 55
    lthr_run: int = 160
    lthr_bike: int = 155
    lthr_swim: int = 145
    pace_umbral_run: float = 5.5
    ftp_watts: int = 200
    css_100m: float = 1.8
    ctl_inicial: float = 40.0
    resp_volumen: float = 1.0
    resp_intensidad: float = 1.0
    tasa_recuperacion: float = 1.0
    umbral_lesion: float = 1.5
    horas_sueno_base: float = 7.5
    calidad_sueno: float = 0.75
    estres_cronico: float = 0.3
    trabajo: str = 'sedentario'
    nutricion: float = 0.8
    anos_entrenamiento: int = 3
    zona_vulnerable: str = ''
    max_sesiones_semana: int = 6
    carrera_nombre: str = ''
    carrera_tipo: str = ''    # 5K, 10K, 21K, maraton, olimpico, sprint, mtb, etc
    carrera_semanas: int = 0


@dataclass
class EstadoDiario:
    fecha: date = field(default_factory=date.today)
    ctl: float = 40.0
    atl: float = 40.0
    tsb: float = 0.0
    tss_dia: float = 0.0
    hrv_rmssd: float = 55.0
    hrv_base: float = 55.0
    hanna_life: float = 65.0
    glucogeno_pct: float = 85.0
    dano_muscular: float = 0.0
    acwr: float = 1.0
    acwr_3d_high: int = 0
    lesionado: bool = False
    dias_lesion_rest: int = 0
    pace_actual: float = 5.5
    ftp_actual: float = 200.0
    entreno: bool = False
    tipo_sesion: str = ''


class ModeloFisiologico:
    TAU_CTL = 42.0
    TAU_ATL = 7.0

    def __init__(self, perfil):
        self.p = perfil
        hrv_b = 65 - (perfil.edad-25)*0.4
        if perfil.sexo == 'F': hrv_b *= 0.92
        hrv_b *= (0.85 + perfil.ctl_inicial/250)
        hrv_b = max(30, min(110, hrv_b))
        self.estado = EstadoDiario(
            ctl=perfil.ctl_inicial, atl=perfil.ctl_inicial,
            hrv_rmssd=hrv_b, hrv_base=hrv_b,
            pace_actual=perfil.pace_umbral_run,
            ftp_actual=float(perfil.ftp_watts))
        self.historial = []
        self.tss_7d = [perfil.ctl_inicial] * 7
        self.hrv_7d = [hrv_b] * 7

    def simular_dia(self, fecha, sesion=None):
        p, prev = self.p, self.estado
        e = EstadoDiario(fecha=fecha, ctl=prev.ctl, atl=prev.atl,
            glucogeno_pct=prev.glucogeno_pct, dano_muscular=prev.dano_muscular,
            hrv_base=prev.hrv_base, ftp_actual=prev.ftp_actual,
            pace_actual=prev.pace_actual, acwr_3d_high=prev.acwr_3d_high)

        if prev.lesionado and prev.dias_lesion_rest > 0:
            e.lesionado, e.dias_lesion_rest = True, prev.dias_lesion_rest - 1
            if e.dias_lesion_rest <= 0: e.lesionado = False
            sesion = None

        tss = 0.0
        zona = 2
        if sesion and sesion.get('cumplida', True):
            e.entreno = True
            e.tipo_sesion = sesion.get('tipo', 'easy')
            tss = sesion.get('tss', 0)
            zona = sesion.get('zona_principal', 2)
            dur = sesion.get('duracion_min', 45)
            g_rate = {1:.3,2:.5,3:1.0,4:1.8,5:2.2,6:2.8}
            e.glucogeno_pct = max(5, prev.glucogeno_pct - g_rate.get(zona,1)*dur/10)
            dano = max(0,(zona-2))*dur/80*2.5
            e.dano_muscular = min(70, prev.dano_muscular*0.60 + dano)
        else:
            e.dano_muscular = max(0, prev.dano_muscular*0.50)

        e.tss_dia = tss
        e.ctl = prev.ctl + (tss - prev.ctl) / self.TAU_CTL
        e.atl = prev.atl + (tss - prev.atl) / self.TAU_ATL
        e.tsb = e.ctl - e.atl

        self.tss_7d.pop(0); self.tss_7d.append(tss)
        e.acwr = round(sum(self.tss_7d)/7 / max(e.ctl, 10), 2)
        e.acwr_3d_high = (prev.acwr_3d_high+1) if e.acwr > p.umbral_lesion else 0

        # HRV aditivo
        d = -3*max(0, e.atl/max(e.ctl,20)-0.8) - 2*p.estres_cronico
        d += (1.0*p.tasa_recuperacion if not e.entreno else -0.5)
        e.hrv_rmssd = max(25, e.hrv_base + d + random.gauss(0, 2.5))
        e.hrv_base = prev.hrv_base + (e.ctl - prev.ctl) * 0.03

        e.glucogeno_pct = min(100, e.glucogeno_pct + 25*p.nutricion*(0.5 if e.entreno else 1.0))

        h_hrv = min(50, max(0, (e.hrv_rmssd/max(e.hrv_base,30))*25+15))
        h_carga = max(0, min(25, 25 - max(0, e.atl-e.ctl)*1.5))
        e.hanna_life = min(100, max(5, round(h_hrv + p.calidad_sueno*25 + h_carga)))

        # Lesion
        riesgo = 0.004
        if e.acwr_3d_high >= 3: riesgo += (e.acwr_3d_high-2)*0.015
        riesgo /= (1 + p.anos_entrenamiento*0.03)
        if random.random() < min(0.10, riesgo) and e.entreno and e.acwr_3d_high >= 3:
            e.lesionado = True; e.dias_lesion_rest = random.randint(5,14)

        # Adaptacion diferenciada por zona (~2-3%/mes, Coyle 1988)
        if e.entreno and e.hanna_life > 35:
            if zona >= 5:
                m = 0.0008 * p.resp_intensidad   # Z5+: alta mejora por intensidad
            elif zona >= 3:
                m = 0.0005 * (p.resp_intensidad*0.5 + p.resp_volumen*0.5)
            else:
                m = 0.0003 * p.resp_volumen       # Z1-Z2: mejora por volumen
            m *= min(1.3, p.calidad_sueno * p.nutricion * 1.6)
            e.pace_actual = max(3.0, prev.pace_actual * (1 - m))
            e.ftp_actual = min(450, prev.ftp_actual * (1 + m))
        elif not e.entreno:
            e.pace_actual = prev.pace_actual * 1.00015  # Detraining ~1%/semana
            e.ftp_actual = prev.ftp_actual * 0.99985

        self.historial.append(e)
        self.estado = e
        return e


def _tss_semanal_target(perfil, semana):
    """TSS semanal. Taper ANULA mesociclo."""
    ctl_obj = perfil.ctl_inicial * 1.08  # Grow 8%

    # Semanas de taper segun tipo de carrera
    sem_taper = TAPER_SEMANAS.get(perfil.carrera_tipo, 2)
    sem_para_carrera = perfil.carrera_semanas - semana if perfil.carrera_semanas > 0 else 999

    if sem_para_carrera <= sem_taper and sem_para_carrera > 0:
        # Taper progresivo (Mujika): NO aplica mesociclo
        # Reduccion: 60% en ultima semana, progresivo hacia atras
        pct_taper = 0.60 + 0.40 * ((sem_para_carrera - 1) / max(sem_taper, 1))
        return round(ctl_obj * 7 * pct_taper)
    elif sem_para_carrera == 0:
        return round(ctl_obj * 7 * 0.50)  # Semana de carrera

    # Mesociclo normal: A-A-T-R
    sem_meso = semana % 4
    factor = {0: 1.0, 1: 1.05, 2: 1.10, 3: 0.70}[sem_meso]
    return round(ctl_obj * 7 * factor)


def plan_polarizado(perfil, estado, semana):
    """Seiler 2010: 80/0/20. Pocas sesiones Z5, mucho Z1-Z2."""
    tss = _tss_semanal_target(perfil, semana)
    return _distribuir(perfil, tss, pct_easy=0.80, z_hard=5, mult_hard=1.8, mult_easy=0.55)

def plan_piramidal(perfil, estado, semana):
    """Stoggl 2014: 70/25/5. Mas Z3, algo de Z5."""
    tss = _tss_semanal_target(perfil, semana)
    return _distribuir(perfil, tss, pct_easy=0.65, z_hard=3, mult_hard=1.3, mult_easy=0.65)

def plan_threshold(perfil, estado, semana):
    """Tradicional: 55/35/10. Mucho Z4."""
    tss = _tss_semanal_target(perfil, semana)
    return _distribuir(perfil, tss, pct_easy=0.50, z_hard=4, mult_hard=1.5, mult_easy=0.60)


def _distribuir(perfil, tss_sem, pct_easy, z_hard, mult_hard, mult_easy):
    n = perfil.max_sesiones_semana
    n_hard = max(1, round(n * (1 - pct_easy)))
    tss_per = tss_sem / max(n, 1)
    tss_hard = tss_per * mult_hard
    tss_easy = tss_per * mult_easy
    dur_hard = max(30, min(90, tss_hard / 1.2))
    dur_easy = max(30, min(65, tss_easy / 0.65))
    dur_long = max(60, min(210, tss_hard * 1.4 / 0.75))

    plan = {}
    if perfil.deporte == 'triatlon':
        sports = ['swimming','cycling','running','cycling','running','cycling','running']
        for i in range(min(7, n)):
            if i == 5:
                plan[i] = {'sport':sports[i],'tipo':'long','duracion_min':dur_long,'tss':tss_hard*1.5,'zona_principal':2}
            elif i == 6:
                plan[i] = {'sport':sports[i],'tipo':'long','duracion_min':dur_long*0.6,'tss':tss_hard*1.2,'zona_principal':2}
            elif i < n_hard:
                plan[i] = {'sport':sports[i],'tipo':'quality','duracion_min':dur_hard,'tss':tss_hard,'zona_principal':z_hard}
            else:
                plan[i] = {'sport':sports[i],'tipo':'easy','duracion_min':dur_easy,'tss':tss_easy,'zona_principal':2}
    elif perfil.deporte == 'cycling':
        for i in range(min(6, n)):
            if i == n-1:
                plan[5] = {'sport':'cycling','tipo':'long','duracion_min':dur_long*1.4,'tss':tss_hard*2.0,'zona_principal':2}
            elif i < n_hard:
                plan[i*2 if i<3 else i+2] = {'sport':'cycling','tipo':'quality','duracion_min':dur_hard,'tss':tss_hard,'zona_principal':z_hard}
            else:
                plan[i] = {'sport':'cycling','tipo':'easy','duracion_min':dur_easy,'tss':tss_easy,'zona_principal':2}
    else:
        dias = [0,2,4,5][:n]
        for j, d in enumerate(dias):
            if d == 5:
                plan[d] = {'sport':'running','tipo':'long','duracion_min':dur_long*0.7,'tss':tss_hard*1.5,'zona_principal':2}
            elif j < n_hard:
                plan[d] = {'sport':'running','tipo':'quality','duracion_min':dur_hard,'tss':tss_hard,'zona_principal':z_hard}
            else:
                plan[d] = {'sport':'running','tipo':'easy','duracion_min':dur_easy,'tss':tss_easy,'zona_principal':2}
    return plan


class MotorTwin:
    def __init__(self, perfil):
        self.perfil = perfil
        self.modelo = ModeloFisiologico(perfil)
        self.sem = 0

    def simular(self, semanas=12, plan_func=None, verbose=True):
        f = plan_func or plan_polarizado
        if verbose:
            cr = f' → {self.perfil.carrera_nombre} sem {self.perfil.carrera_semanas}' if self.perfil.carrera_semanas else ''
            print(f'\n{"="*65}')
            print(f'  {self.perfil.nombre} [{getattr(f,"__name__","?")}]{cr}')
            print(f'  CTL {self.perfil.ctl_inicial} | {self.perfil.deporte}')
            print(f'{"="*65}')

        fecha = date.today()
        for s in range(semanas):
            self.sem = s + 1
            sesiones = f(self.perfil, self.modelo.estado, s)
            tss_s = 0
            for d in range(7):
                ses = sesiones.get(d)
                if ses:
                    p = 0.93 if self.modelo.estado.hanna_life > 40 else 0.72
                    ses['cumplida'] = random.random() < p
                self.modelo.simular_dia(fecha + timedelta(days=s*7+d), ses)
                tss_s += self.modelo.estado.tss_dia
            if verbose:
                e = self.modelo.estado
                l = ' LES' if e.lesionado else ''
                t = ''
                if self.perfil.carrera_semanas > 0:
                    r = self.perfil.carrera_semanas - s
                    if r > 0: t = f' [{r}sem]'
                    elif r == 0: t = ' [CARRERA]'
                print(f'  S{s+1:2d} CTL={e.ctl:5.1f} TSB={e.tsb:+5.1f} HL={e.hanna_life:3.0f} '
                      f'ACWR={e.acwr:.2f} TSS={tss_s:4.0f} P={e.pace_actual:.2f} FTP={e.ftp_actual:.0f}{l}{t}')
        return self._rep()

    def _rep(self):
        h = self.modelo.historial
        if not h: return {}
        i, f = h[0], h[-1]
        # TSB en semana de carrera (si hay)
        tsb_carrera = None
        if self.perfil.carrera_semanas > 0:
            dia_carrera = self.perfil.carrera_semanas * 7
            if dia_carrera < len(h):
                tsb_carrera = round(h[dia_carrera-1].tsb, 1)
        return {
            'nombre': self.perfil.nombre, 'delta_ctl': round(f.ctl-i.ctl,1),
            'ctl_f': round(f.ctl,1), 'pace_i': round(i.pace_actual,2),
            'pace_f': round(f.pace_actual,2), 'delta_pace': round(f.pace_actual-i.pace_actual,2),
            'ftp_i': round(i.ftp_actual), 'ftp_f': round(f.ftp_actual),
            'hanna_avg': round(sum(e.hanna_life for e in h)/len(h)),
            'lesiones': any(e.lesionado for e in h),
            'tss_total': round(sum(e.tss_dia for e in h)),
            'tsb_carrera': tsb_carrera,
        }


def comparar(perfil, semanas=12, seed=42):
    ests = {'polarizado': plan_polarizado, 'piramidal': plan_piramidal, 'threshold': plan_threshold}
    res = {}
    for n, f in ests.items():
        random.seed(seed)
        res[n] = MotorTwin(perfil).simular(semanas, f, verbose=True)

    print(f'\n{"="*65}')
    print(f'  COMPARATIVA: {perfil.nombre}')
    if perfil.carrera_nombre:
        print(f'  Carrera: {perfil.carrera_nombre} ({perfil.carrera_tipo})')
    print(f'{"="*65}')
    print(f'  {"Est":<13s} {"ΔCTL":>6s} {"Pace":>6s} {"ΔPace":>7s} {"FTP":>5s} {"HL":>4s} {"TSB_car":>8s} {"Les":>4s}')
    print(f'  {"-"*55}')
    for n, r in res.items():
        tsb_c = f'{r["tsb_carrera"]:>+6.1f}' if r.get('tsb_carrera') is not None else '   --'
        print(f'  {n:<13s} {r["delta_ctl"]:>+5.1f} {r["pace_f"]:>5.2f} {r["delta_pace"]:>+6.2f} '
              f'{r["ftp_f"]:>4.0f} {r["hanna_avg"]:>3.0f} {tsb_c:>8s} {"SI" if r["lesiones"] else "no":>4s}')
    mejor = max(res.items(), key=lambda x: x[1]['delta_ctl'])
    print(f'\n  MEJOR para fitness: {mejor[0]} (ΔCTL {mejor[1]["delta_ctl"]:+.1f})')
    if perfil.carrera_semanas > 0:
        mejor_car = max(res.items(), key=lambda x: x[1].get('tsb_carrera') or -99)
        if mejor_car[1].get('tsb_carrera') is not None:
            print(f'  MEJOR para carrera: {mejor_car[0]} (TSB {mejor_car[1]["tsb_carrera"]:+.1f} el dia de carrera)')
    return res


def crear_twins():
    return {
        'rodrigo': PerfilTwin(
            nombre='Rodrigo (real)', edad=40, sexo='M', peso_kg=80,
            deporte='triatlon', lthr_run=160, lthr_bike=160,
            pace_umbral_run=5.71, ftp_watts=156, css_100m=1.8,
            ctl_inicial=68, resp_volumen=1.0, resp_intensidad=1.0,
            tasa_recuperacion=0.9, umbral_lesion=1.5,
            calidad_sueno=0.75, estres_cronico=0.3, nutricion=0.8,
            anos_entrenamiento=8, max_sesiones_semana=6),
        'silvina': PerfilTwin(
            nombre='Silvina (real)', edad=45, sexo='F', peso_kg=60,
            deporte='running', lthr_run=157,
            pace_umbral_run=6.75, ftp_watts=100,
            ctl_inicial=30, resp_volumen=1.1, resp_intensidad=0.8,
            tasa_recuperacion=0.85, umbral_lesion=1.4,
            calidad_sueno=0.7, estres_cronico=0.35, nutricion=0.75,
            anos_entrenamiento=5, max_sesiones_semana=5,
            carrera_nombre='10K Otoño', carrera_tipo='10K', carrera_semanas=8),
        'jimena': PerfilTwin(
            nombre='Jimena (real)', edad=35, sexo='F', peso_kg=65,
            deporte='triatlon', lthr_run=176, lthr_bike=160, lthr_swim=162,
            pace_umbral_run=5.09, ftp_watts=151, css_100m=1.85,
            ctl_inicial=68, resp_volumen=1.0, resp_intensidad=1.1,
            tasa_recuperacion=1.0, umbral_lesion=1.5,
            calidad_sueno=0.8, estres_cronico=0.25, nutricion=0.85,
            anos_entrenamiento=6, max_sesiones_semana=7,
            carrera_nombre='Olímpico', carrera_tipo='olimpico', carrera_semanas=10),
        'principiante': PerfilTwin(
            nombre='Ana (ficticia)', edad=35, sexo='F', peso_kg=62,
            deporte='running', lthr_run=155,
            pace_umbral_run=6.8, ftp_watts=120,
            ctl_inicial=20, resp_volumen=1.1, resp_intensidad=0.7,
            tasa_recuperacion=0.8, umbral_lesion=1.3,
            horas_sueno_base=6.5, calidad_sueno=0.65, estres_cronico=0.5,
            nutricion=0.65, anos_entrenamiento=1, zona_vulnerable='rodilla',
            max_sesiones_semana=4,
            carrera_nombre='5K', carrera_tipo='5K', carrera_semanas=12),
        'ciclista_pro': PerfilTwin(
            nombre='Gonzalo (ficticio)', edad=30, sexo='M', peso_kg=72,
            deporte='cycling', lthr_bike=172,
            pace_umbral_run=4.3, ftp_watts=310,
            ctl_inicial=85, resp_volumen=1.3, resp_intensidad=1.3,
            tasa_recuperacion=1.3, umbral_lesion=1.7,
            horas_sueno_base=8.5, calidad_sueno=0.9, estres_cronico=0.1,
            nutricion=0.95, anos_entrenamiento=12, max_sesiones_semana=6,
            carrera_nombre='Río Pinto MTB', carrera_tipo='mtb', carrera_semanas=10),
    }


if __name__ == '__main__':
    twins = crear_twins()
    # Comparativa para cada atleta
    for nombre, perfil in twins.items():
        comparar(perfil, semanas=12)
