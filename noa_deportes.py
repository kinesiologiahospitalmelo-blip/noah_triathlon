"""
noa_deportes.py
---------------
Modulo multideporte NOA.
Zonas, TSS y métricas para running, cycling y swimming.

RUNNING:
  Zonas por % LTHR (Friel / Seiler)
  TSS desde HR + pace

CYCLING:
  Zonas por % FTP (Coggan 7 zonas)
  TSS desde potencia (si hay) o HR
  Estimación de potencia sin potenciómetro
  NP, IF, W'bal, KJ, torque

SWIMMING:
  Zonas por % LTHR swim (pace cada 100m)
  TSS desde HR + pace_100m
  SWOLF, eficiencia de palada

USO:
  from noa_deportes import ZonasRunning, ZonasCycling, ZonasSwimming
  from noa_deportes import calcular_tss, calcular_np, estimar_potencia
"""

import math
from dataclasses import dataclass, field
from typing import Optional


# ─── CONSTANTES ───────────────────────────────────────────────────────────────

# Constante de tiempo CTL (42 días) y ATL (7 días) — modelo Banister
K_CTL = 1 - math.exp(-1 / 42)
K_ATL = 1 - math.exp(-1 / 7)

# W' estándar (capacidad anaeróbica) en joules — ajustable por atleta
W_PRIME_DEFAULT = 20000  # 20 kJ


# ─── DATACLASSES ──────────────────────────────────────────────────────────────

@dataclass
class Zona:
    nombre      : str
    codigo      : str
    pct_min     : float   # % de referencia mínimo
    pct_max     : float   # % de referencia máximo
    ref_min     : float   # valor absoluto mínimo
    ref_max     : float   # valor absoluto máximo
    lactato     : str
    vo2_pct     : str
    descripcion : str
    referencia  : str
    color       : str
    pace_ref    : Optional[float] = None   # pace de referencia (running/swim)
    pace_str    : Optional[str]   = None   # pace formateado


# ─── RUNNING ZONES ────────────────────────────────────────────────────────────

class ZonasRunning:
    """
    Zonas de running basadas en % LTHR.
    Bibliografía: Friel, Seiler, San Millán, Allen & Coggan.
    """

    DEFINICIONES = [
        ('Z1', 'Recuperación activa',          0.00, 0.75, '#0',  '#<1',  '< 55%',  'Friel Z1 / Seiler Z1',           '#94C4F5'),
        ('Z2', 'Resistencia aeróbica',          0.75, 0.87, '1-2', '55-75%', '75-87% LTHR', 'San Millán Z2 / Friel Endurance', '#00A651'),
        ('Z3', 'Tempo / Umbral aeróbico',       0.87, 0.93, '2-4', '75-85%', '87-93% LTHR', 'Friel Tempo / Maffetone',         '#F7C325'),
        ('Z4', 'Umbral de lactato / FTP',       0.93, 1.00, '4-8', '85-95%', '93-100% LTHR','Friel LT / Allen-Coggan FTP',     '#F26522'),
        ('Z5', 'VO2max',                        1.00, 1.06, '8-12','95-100%','100-106% LTHR','Seiler VO2max / Billat',          '#E82B3E'),
        ('Z6', 'Capacidad anaeróbica',          1.06, 1.30, '>12', '>100%', '>106% LTHR',   'Friel Anaerobic / Coggan',        '#6B21A8'),
    ]

    def __init__(self, lthr: float, hr_max: float, pace_z2_real: float = None,
                 peso_kg: float = 75, pace_umbral: float = None):
        # Si no hay LTHR real, estimarlo desde hr_max (85% es aprox estandar de umbral)
        self.lthr        = lthr or (hr_max * 0.85 if hr_max else 160)
        self.hr_max      = hr_max
        self.peso_kg     = peso_kg
        # pace_umbral (Z4) es la referencia principal para calcular todas las zonas.
        # Si no viene, estimar desde el LTHR usando la funcion anterior.
        # Si viene pace_z2_real pero no pace_umbral, convertir Z2 a umbral
        # multiplicando por 0.81/1.0 = 0.81 (Z2 center es ~81% LTHR, Z4 es ~97%).
        if pace_umbral:
            self.pace_umbral = pace_umbral
        elif pace_z2_real:
            # Z2 es aprox 5-7% mas lento que el umbral
            self.pace_umbral = pace_z2_real * 0.92
        else:
            self.pace_umbral = self._estimar_pace_umbral()
        # Mantener pace_z2 para compatibilidad con codigo existente
        self.pace_z2 = self.pace_umbral / 0.92

    def _estimar_pace_umbral(self) -> float:
        """
        Estima el pace de umbral (Z4) desde el LTHR cuando no hay
        datos reales de Garmin ni test de campo.
        Aproximacion empirica: LTHR 160 bpm -> pace umbral ~4:58/km.
        Cada bpm de diferencia cambia el pace ~0.05 min/km.
        """
        return 4.98 + (160 - self.lthr) * 0.05

    def _estimar_pace_z2(self) -> float:
        # Mantener por compatibilidad; calcula Z2 desde el umbral estimado
        return self._estimar_pace_umbral() / 0.92

    def _pace_en_pct(self, pct: float) -> float:
        """
        Pace exacto en un limite de %LTHR puntual (sin margen
        artificial). Usada para los bordes pct_min/pct_max de cada
        zona -- asi el borde superior de una zona y el borde inferior
        de la siguiente dan EXACTAMENTE el mismo pace (continuidad
        garantizada, sin huecos entre zonas).
        """
        z4_center = 0.965  # centro de Z4 (umbral)
        if pct <= 0:
            pct = 0.50  # piso para Z1, que arranca en 0% LTHR
        return self.pace_umbral * (z4_center / pct)

    def _pace_para_zona(self, pct_min: float, pct_max: float) -> tuple:
        """
        Calcula pace minimo y maximo para una zona usando los limites
        REALES de la zona (pct_min, pct_max) -- no un margen inventado
        alrededor de un centro. Esto garantiza que las zonas sean
        continuas y que las zonas lentas tengan un rango de pace mas
        ancho de forma natural.
        """
        pace_slow = self._pace_en_pct(pct_min)
        pace_fast = self._pace_en_pct(pct_max)
        return pace_fast, pace_slow

    def _fmt_pace(self, p: float) -> str:
        if not p: return '--'
        m = int(p)
        s = int((p - m) * 60)
        return f'{m}:{s:02d}'

    def calcular(self) -> dict:
        zonas = {}
        for codigo, nombre, pct_min, pct_max, lactato, vo2, ref_desc, biblio, color in self.DEFINICIONES:
            hr_min = round(self.lthr * pct_min) if pct_min > 0 else round(self.lthr * 0.55)
            hr_max = round(self.lthr * pct_max)

            pace_slow, pace_fast = self._pace_para_zona(pct_min, pct_max)
            pace_ref = (pace_slow + pace_fast) / 2

            zonas[codigo] = {
                'nombre'    : nombre,
                'hr_min'    : hr_min,
                'hr_max'    : hr_max,
                'pct_lthr'  : f'{round(pct_min*100)}-{round(pct_max*100)}%',
                'lactato'   : lactato,
                'vo2_pct'   : vo2,
                'referencia': biblio,
                'color'     : color,
                'pace_ref'  : round(pace_ref, 2),
                'pace_min'  : self._fmt_pace(pace_fast),
                'pace_max'  : self._fmt_pace(pace_slow),
                'pace_rango': f'{self._fmt_pace(pace_fast)} – {self._fmt_pace(pace_slow)} /km',
            }
        return zonas

    def tss_desde_hr(self, hr_avg: float, duracion_min: float) -> float:
        """Calcula TSS de running desde HR promedio."""
        if not hr_avg or not duracion_min: return 0
        if_factor = hr_avg / self.lthr
        return round(if_factor ** 2 * (duracion_min / 60) * 100, 1)


# ─── CYCLING ZONES ────────────────────────────────────────────────────────────

class ZonasCycling:
    """
    Zonas de ciclismo basadas en % FTP (Coggan 7 zonas).
    Con soporte para estimación de potencia sin potenciómetro.
    Bibliografía: Allen & Coggan, Training and Racing with a Power Meter.
    """

    DEFINICIONES = [
        ('Z1', 'Recuperación activa',    0.00, 0.55, '<1',   '<55%',   'Allen & Coggan Z1',  '#94C4F5'),
        ('Z2', 'Resistencia aeróbica',   0.55, 0.75, '1-2',  '55-75%', 'Allen & Coggan Z2',  '#00A651'),
        ('Z3', 'Tempo',                  0.75, 0.90, '2-4',  '75-90%', 'Allen & Coggan Z3',  '#F7C325'),
        ('Z4', 'Umbral de lactato',      0.90, 1.05, '4-8',  '90-105%','Allen & Coggan Z4',  '#F26522'),
        ('Z5', 'VO2max',                 1.05, 1.20, '8-12', '105-120%','Allen & Coggan Z5', '#E82B3E'),
        ('Z6', 'Capacidad anaeróbica',   1.20, 1.50, '>12',  '120-150%','Allen & Coggan Z6', '#6B21A8'),
        ('Z7', 'Neuromuscular',          1.50, 9.99, '>12',  '>150%',  'Allen & Coggan Z7',  '#0A0A0A'),
    ]

    def __init__(self, ftp: float, lthr_bike: float = None, hr_max: float = 185,
                 peso_kg: float = 75, w_prime: float = W_PRIME_DEFAULT):
        # Si no hay FTP real cargado, estimar conservador desde LTHR/peso
        # (mismo criterio que desde_lthr() mas abajo) en vez de dejar None.
        lthr_bike_efectivo = lthr_bike or (hr_max * 0.85 if hr_max else 150)
        self.ftp        = ftp or round((lthr_bike_efectivo / (hr_max or 185)) * (peso_kg or 75) * 2.8)
        self.lthr_bike  = lthr_bike_efectivo
        self.hr_max     = hr_max
        self.peso_kg    = peso_kg
        self.w_prime    = w_prime
        self.w_kg       = round(self.ftp / peso_kg, 2) if peso_kg else None

    @classmethod
    def desde_lthr(cls, lthr_bike: float, hr_max: float, peso_kg: float = 75) -> 'ZonasCycling':
        """
        Estima FTP desde LTHR cuando no hay potenciómetro.
        Ecuación aproximada: FTP ≈ (LTHR/HR_max) × VO2max_estimado × peso
        Simplificación práctica: FTP ≈ 2.5 × peso para atleta amateur.
        """
        # Estimación conservadora basada en nivel de fitness
        pct_lthr = lthr_bike / hr_max
        ftp_estimado = round(pct_lthr * peso_kg * 2.8)
        return cls(ftp=ftp_estimado, lthr_bike=lthr_bike, hr_max=hr_max, peso_kg=peso_kg)

    def calcular(self) -> dict:
        zonas = {}
        for codigo, nombre, pct_min, pct_max, lactato, vo2, biblio, color in self.DEFINICIONES:
            w_min = round(self.ftp * pct_min)
            w_max = round(self.ftp * pct_max) if pct_max < 9 else None
            hr_estimado_min = round(self.lthr_bike * pct_min) if pct_min > 0.4 else None
            hr_estimado_max = round(self.lthr_bike * min(pct_max, 1.1))

            zonas[codigo] = {
                'nombre'     : nombre,
                'w_min'      : w_min,
                'w_max'      : w_max,
                'w_rango'    : f'{w_min}–{w_max}W' if w_max else f'>{w_min}W',
                'pct_ftp'    : f'{round(pct_min*100)}-{round(pct_max*100)}%' if pct_max < 9 else f'>{round(pct_min*100)}%',
                'hr_min'     : hr_estimado_min,
                'hr_max'     : hr_estimado_max,
                'lactato'    : lactato,
                'vo2_pct'    : vo2,
                'referencia' : biblio,
                'color'      : color,
                'wkg_min'    : round(w_min / self.peso_kg, 1) if self.peso_kg else None,
                'wkg_max'    : round(w_max / self.peso_kg, 1) if w_max and self.peso_kg else None,
            }
        return zonas

    def tss_desde_potencia(self, np_watts: float, duracion_seg: float) -> float:
        """
        TSS desde Normalized Power.
        TSS = (seg × NP × IF) / (FTP × 3600) × 100
        """
        if not np_watts or not duracion_seg or not self.ftp: return 0
        if_factor = np_watts / self.ftp
        tss = (duracion_seg * np_watts * if_factor) / (self.ftp * 3600) * 100
        return round(tss, 1)

    def tss_desde_hr(self, hr_avg: float, duracion_min: float) -> float:
        """TSS estimado desde HR cuando no hay potenciómetro."""
        if not hr_avg or not duracion_min: return 0
        if_factor = hr_avg / self.lthr_bike
        return round(if_factor ** 2 * (duracion_min / 60) * 100, 1)

    def calcular_if(self, np_watts: float) -> float:
        """Intensity Factor = NP / FTP"""
        if not np_watts or not self.ftp: return 0
        return round(np_watts / self.ftp, 3)

    def calcular_wbal(self, potencias: list, intervalo_seg: int = 1) -> list:
        """
        W' balance — energía anaeróbica restante durante la sesión.
        Modelo Skiba (2012): W'bal = W' - integral(max(0, P-FTP)dt) + recuperación
        """
        if not potencias: return []
        wbal = self.w_prime
        wbal_serie = []
        tau = 546 * math.exp(-0.01 * (self.ftp - 100)) + 316  # constante de recuperación

        for p in potencias:
            if p > self.ftp:
                # Gasto anaeróbico
                wbal -= (p - self.ftp) * intervalo_seg
            else:
                # Recuperación
                recuperacion = (self.w_prime - wbal) * (1 - math.exp(-intervalo_seg / tau))
                wbal += recuperacion
            wbal = max(0, min(self.w_prime, wbal))
            wbal_serie.append(round(wbal))

        return wbal_serie

    def calcular_np(self, potencias: list, intervalo_seg: int = 1) -> float:
        """
        Normalized Power — potencia normalizada (Coggan).
        NP = (media de (media móvil 30s)^4) ^ 0.25
        """
        if len(potencias) < 30: return 0
        window = 30 // intervalo_seg
        rolling = []
        for i in range(window, len(potencias) + 1):
            rolling.append(sum(potencias[i-window:i]) / window)
        if not rolling: return 0
        np_val = (sum(p**4 for p in rolling) / len(rolling)) ** 0.25
        return round(np_val, 1)

    def calcular_torque(self, potencia_w: float, cadencia_rpm: float) -> float:
        """Torque = Potencia / (2π × cadencia/60)"""
        if not potencia_w or not cadencia_rpm or cadencia_rpm == 0: return 0
        torque = potencia_w / (2 * math.pi * cadencia_rpm / 60)
        return round(torque, 2)

    def estimar_potencia_sin_medidor(self, velocidad_kmh: float, pendiente_pct: float = 0,
                                      peso_total_kg: float = 85, cda: float = 0.35,
                                      rho: float = 1.2) -> float:
        """
        Estimación de potencia desde velocidad + pendiente.
        Modelo ciclismo: P = P_aero + P_rodadura + P_gravedad

        velocidad_kmh: velocidad en km/h
        pendiente_pct: pendiente en % (positivo = subida)
        peso_total_kg: peso atleta + bici (~85kg)
        cda: coeficiente aerodinámico (0.30 TT, 0.35 ruta, 0.50 MTB)
        rho: densidad del aire (1.2 kg/m³ nivel del mar)
        """
        if not velocidad_kmh: return 0
        v = velocidad_kmh / 3.6  # m/s
        g = 9.81
        crr = 0.004  # coeficiente de rodadura (ruta)

        p_aero    = 0.5 * cda * rho * v**3
        p_rodadura = crr * peso_total_kg * g * v
        p_gravedad = peso_total_kg * g * (pendiente_pct / 100) * v

        potencia = p_aero + p_rodadura + p_gravedad
        return round(max(0, potencia), 1)

    def zona_desde_potencia(self, potencia_w: float) -> str:
        """Determina la zona desde la potencia instantánea."""
        if not potencia_w or not self.ftp: return 'Z1'
        pct = potencia_w / self.ftp
        for codigo, _, pct_min, pct_max, *_ in self.DEFINICIONES:
            if pct_min <= pct < pct_max:
                return codigo
        return 'Z7'


# ─── SWIMMING ZONES ───────────────────────────────────────────────────────────

class ZonasSwimming:
    """
    Zonas de natación basadas en % CSS (Critical Swim Speed) o LTHR swim.
    CSS = equivalente al FTP en natación (pace cada 100m sostenible ~1h).
    Bibliografía: Pyne et al., Maglischo, Olbrecht.
    """

    DEFINICIONES = [
        ('Z1', 'Recuperación activa',   0.00, 0.78, '<1',  '<55%',  'Recuperación. Técnica.'),
        ('Z2', 'Aeróbico extensivo',    0.78, 0.88, '1-2', '55-75%','Base aeróbica. Volumen.'),
        ('Z3', 'Aeróbico intensivo',    0.88, 0.94, '2-4', '75-85%','Umbral aeróbico. Series largas.'),
        ('Z4', 'Umbral anaeróbico',     0.94, 1.00, '4-8', '85-95%','CSS. Series medias.'),
        ('Z5', 'VO2max',                1.00, 1.06, '8-12','95-100%','Series cortas. Alta intensidad.'),
        ('Z6', 'Velocidad / Sprint',    1.06, 9.99, '>12', '>100%', 'Sprints. Máxima velocidad.'),
    ]

    def __init__(self, css_100m: float, lthr_swim: float = None, hr_max: float = 185):
        """
        css_100m: Critical Swim Speed en min/100m
                  Si no se conoce, estimar desde test 400m y 200m.
        lthr_swim: LTHR en agua (generalmente 5-10 bpm menor que en tierra)
        """
        # Si el atleta no tiene CSS cargado (ej: no es nadador / sin test de
        # natacion), usar un valor de referencia generico en vez de None,
        # que rompia la division en calcular() con TypeError.
        self.css      = css_100m or 1.75   # 1:45/100m como referencia generica
        self.lthr     = lthr_swim or (hr_max * 0.82 if hr_max else 150)
        self.hr_max   = hr_max

    @classmethod
    def estimar_css(cls, tiempo_400m_seg: float, tiempo_200m_seg: float) -> float:
        """
        CSS = (400 - 200) / (tiempo_400 - tiempo_200) segundos/metro
        → convertir a min/100m
        """
        css_seg_m = (400 - 200) / (tiempo_400m_seg - tiempo_200m_seg)
        css_100m_seg = 100 / css_seg_m
        return css_100m_seg / 60  # en minutos decimales

    def _fmt_pace_swim(self, p: float) -> str:
        """Formato min:seg/100m"""
        if not p: return '--'
        m = int(p)
        s = int((p - m) * 60)
        return f'{m}:{s:02d}/100m'

    def calcular(self) -> dict:
        zonas = {}
        for codigo, nombre, pct_min, pct_max, lactato, vo2, descripcion in self.DEFINICIONES:
            # En natación: mayor % CSS = pace más rápido (menor número)
            # Evitar división por cero
            pace_min = (self.css / pct_max) if (pct_max and pct_max > 0 and pct_max < 9) else self.css * 0.85
            pace_max = (self.css / pct_min) if (pct_min and pct_min > 0) else self.css * 1.40
            pace_ref = (pace_min + pace_max) / 2

            hr_min = round(self.lthr * pct_min) if pct_min > 0.4 else None
            hr_max = round(self.lthr * min(pct_max, 1.1))

            zonas[codigo] = {
                'nombre'     : nombre,
                'pace_100m_min': self._fmt_pace_swim(pace_min),
                'pace_100m_max': self._fmt_pace_swim(pace_max),
                'pace_rango' : f'{self._fmt_pace_swim(pace_min)} – {self._fmt_pace_swim(pace_max)}',
                'pace_ref'   : round(pace_ref, 3),
                'hr_min'     : hr_min,
                'hr_max'     : hr_max,
                'pct_css'    : f'{round(pct_min*100)}-{round(pct_max*100)}%' if pct_max < 9 else f'>{round(pct_min*100)}%',
                'lactato'    : lactato,
                'vo2_pct'    : vo2,
                'descripcion': descripcion,
            }
        return zonas

    def tss_desde_hr(self, hr_avg: float, duracion_min: float) -> float:
        """TSS de natación desde HR."""
        if not hr_avg or not duracion_min: return 0
        if_factor = hr_avg / self.lthr
        return round(if_factor ** 2 * (duracion_min / 60) * 100, 1)

    def calcular_swolf(self, tiempo_25m_seg: float, paladas_25m: int) -> int:
        """SWOLF = tiempo (seg) + paladas por largo. Menor = más eficiente."""
        return round(tiempo_25m_seg + paladas_25m)


# ─── FUNCIÓN UNIFICADA TSS ────────────────────────────────────────────────────

def calcular_tss_sesion(sesion: dict, atleta: dict) -> float:
    """
    Calcula TSS de una sesión según el deporte.

    sesion dict keys: sport, duration_min, hr_avg, power_np, power_avg, pace
    atleta dict keys: lthr_run, lthr_bike, ftp, hr_max, peso_kg
    """
    sport    = sesion.get('sport', 'running')
    dur_min  = sesion.get('duration_min', 0)
    hr_avg   = sesion.get('hr_avg')
    np_watts = sesion.get('power_np') or sesion.get('power_avg')

    if sport == 'running':
        lthr = atleta.get('lthr_run', 162)
        z = ZonasRunning(lthr=lthr, hr_max=atleta.get('hr_max', 190))
        return z.tss_desde_hr(hr_avg, dur_min)

    elif sport == 'cycling':
        ftp      = atleta.get('ftp') or atleta.get('ftp_bike')
        lthr_bike = atleta.get('lthr_bike', 150)
        hr_max   = atleta.get('hr_max', 185)
        peso     = atleta.get('peso_kg', 75)

        if ftp:
            z = ZonasCycling(ftp=ftp, lthr_bike=lthr_bike, hr_max=hr_max, peso_kg=peso)
            if np_watts:
                dur_seg = dur_min * 60
                return z.tss_desde_potencia(np_watts, dur_seg)
            else:
                return z.tss_desde_hr(hr_avg, dur_min)
        else:
            z = ZonasCycling.desde_lthr(lthr_bike, hr_max, peso)
            return z.tss_desde_hr(hr_avg, dur_min)

    elif sport == 'swim':
        css  = atleta.get('css_100m', 1.75)
        lthr = atleta.get('lthr_swim') or atleta.get('lthr_run', 155)
        z = ZonasSwimming(css_100m=css, lthr_swim=lthr, hr_max=atleta.get('hr_max', 185))
        return z.tss_desde_hr(hr_avg, dur_min)

    else:
        # Otros deportes — IF conservador
        lthr = atleta.get('lthr_run', 162)
        if hr_avg and lthr:
            if_factor = min(hr_avg / lthr, 1.2)
            return round(if_factor ** 2 * (dur_min / 60) * 100, 1)
        return round(0.65 ** 2 * (dur_min / 60) * 100, 1)


# ─── USO DIRECTO / DEMO ───────────────────────────────────────────────────────

if __name__ == '__main__':
    print('\n' + '='*60)
    print('  NOA DEPORTES — Demo de zonas')
    print('='*60)

    # RUNNING — Rodrigo
    print('\n📍 RUNNING — Rodrigo (LTHR 162, pace Z2 5:50/km)')
    zr = ZonasRunning(lthr=162, hr_max=190, pace_z2_real=5.833)
    for zona, z in zr.calcular().items():
        print(f'  {zona} {z["nombre"]:<30} HR {z["hr_min"]}-{z["hr_max"]}  {z["pace_rango"]}')

    # CYCLING — con potenciómetro (FTP 250W)
    print('\n🚴 CYCLING — con potenciómetro (FTP 250W, 75kg)')
    zc = ZonasCycling(ftp=250, lthr_bike=150, peso_kg=75)
    for zona, z in zc.calcular().items():
        print(f'  {zona} {z["nombre"]:<30} {z["w_rango"]:<12}  {z["pct_ftp"]}  {z["wkg_min"]} W/kg')

    # CYCLING — sin potenciómetro
    print('\n🚴 CYCLING — sin potenciómetro (LTHR 150, 75kg) FTP estimado')
    zc2 = ZonasCycling.desde_lthr(lthr_bike=150, hr_max=185, peso_kg=75)
    print(f'  FTP estimado: {zc2.ftp}W  ({zc2.w_kg} W/kg)')
    for zona, z in zc2.calcular().items():
        print(f'  {zona} {z["nombre"]:<30} {z["w_rango"]:<12}  HR {z["hr_min"]}-{z["hr_max"]}')

    # SWIMMING — CSS 1:45/100m
    print('\n🏊 SWIMMING — CSS 1:45/100m')
    zs = ZonasSwimming(css_100m=1.75, lthr_swim=148, hr_max=185)
    for zona, z in zs.calcular().items():
        print(f'  {zona} {z["nombre"]:<30} {z["pace_rango"]}')

    # TSS demo
    print('\n📊 TSS DEMO')
    sesion_run = {'sport': 'running', 'duration_min': 60, 'hr_avg': 140}
    sesion_bike = {'sport': 'cycling', 'duration_min': 90, 'hr_avg': 145, 'power_np': 230}
    atleta = {'lthr_run': 162, 'lthr_bike': 150, 'ftp': 250, 'hr_max': 190, 'peso_kg': 75}
    print(f'  Running 60min HR140: TSS {calcular_tss_sesion(sesion_run, atleta)}')
    print(f'  Cycling 90min NP230W: TSS {calcular_tss_sesion(sesion_bike, atleta)}')

    # Estimación potencia
    print('\n⚡ POTENCIA ESTIMADA SIN MEDIDOR')
    zc3 = ZonasCycling(ftp=250, peso_kg=75)
    for vel, pct in [(25, 0), (30, 0), (35, 0), (25, 5), (30, -3)]:
        p = zc3.estimar_potencia_sin_medidor(vel, pct)
        zona = zc3.zona_desde_potencia(p)
        print(f'  {vel}km/h pendiente {pct:+}%  → {p}W  ({zona})')
