"""
noah_estrategia_carrera.py v2 — Estrategia de carrera con base cientifica
===========================================================================
CALCULOS (no estimaciones):
  Velocidad bike: P = 0.5*CdA*rho*v^3 + Crr*m*g*v (Newton-Raphson)
  BMR: Harris-Benedict revisado (Roza & Shizgal 1984)
  CHO oxidacion: funcion de intensidad relativa (Romijn 1993, Jeukendrup 2004)
  Sudoracion: funcion de temperatura y peso (Sawka 2007)
  Degradacion por calor: -1.5% rendimiento por cada °C > 20°C (Ely 2007)
  Fatiga bike→run: +5-10% segun distancia (Millet 2011)
  Negative split: 2% en run (Abbiss & Laursen 2008)
  Bike pacing: progressive power +3-5% segunda mitad (Atkinson 2007)

NUTRICION POR SEGMENTO:
  CHO necesario = CHO_oxidacion_rate × tiempo_segmento
  CHO_oxidacion_rate depende de %VO2max (Romijn 1993):
    40% VO2max: 0.3 g/min (Z1)
    55% VO2max: 0.7 g/min (Z2)  
    75% VO2max: 1.5 g/min (Z3-Z4)
    85% VO2max: 2.2 g/min (Z5)
  Ingesta recomendada = deficit entre oxidacion y reservas

HIDRATACION:
  Tasa sudoracion (Sawka 2007): peso_kg × factor_temp (ml/hr)
    <15°C: 0.4-0.6 L/hr
    15-25°C: 0.6-1.0 L/hr
    25-35°C: 0.8-1.4 L/hr
    >35°C: 1.0-1.8 L/hr
  Sodio: 500-1000 mg/L de sudor (Baker 2017)
  No superar 800ml/hr para evitar hiponatremia (Noakes 2012)
"""

import math
from datetime import date


def calcular_bmr(peso, altura, edad, sexo):
    """Harris-Benedict revisado (Roza & Shizgal 1984)."""
    if sexo == 'F':
        return round(447.593 + 9.247*peso + 3.098*altura - 4.330*edad)
    return round(88.362 + 13.397*peso + 4.799*altura - 5.677*edad)


# CHO oxidation rate por zona (Romijn 1993, Jeukendrup 2004) — g/min
# Calculado desde % contribucion de CHO al gasto total por intensidad
CHO_RATE = {1: 0.3, 2: 0.7, 3: 1.2, 4: 1.8, 5: 2.2, 6: 2.5}

# Gasto calorico por zona (kcal/min, atleta de 70kg, escala lineal con peso)
KCAL_MIN_70KG = {1: 5, 2: 8, 3: 11, 4: 14, 5: 16, 6: 18}

GLUCOGENO_TOTAL_G = 500  # 400 muscular + 100 hepatico

CARRERAS = {
    '5K':{'dist_km':5,'deportes':['running']},
    '10K':{'dist_km':10,'deportes':['running']},
    '21K':{'dist_km':21.1,'deportes':['running']},
    'maraton':{'dist_km':42.2,'deportes':['running']},
    'sprint':{'dist_km':25.75,'deportes':['swimming','cycling','running'],'swim_m':750,'bike_km':20,'run_km':5},
    'olimpico':{'dist_km':51.5,'deportes':['swimming','cycling','running'],'swim_m':1500,'bike_km':40,'run_km':10},
    '70.3':{'dist_km':113,'deportes':['swimming','cycling','running'],'swim_m':1900,'bike_km':90,'run_km':21.1},
    'ironman':{'dist_km':226,'deportes':['swimming','cycling','running'],'swim_m':3800,'bike_km':180,'run_km':42.2},
    'crono':{'dist_km':40,'deportes':['cycling']},
    'ruta':{'dist_km':160,'deportes':['cycling']},
    'mtb':{'dist_km':120,'deportes':['cycling']},
    'oa_1500':{'dist_km':1.5,'deportes':['swimming'],'swim_m':1500},
    'oa_3K':{'dist_km':3,'deportes':['swimming'],'swim_m':3000},
    'oa_5K':{'dist_km':5,'deportes':['swimming'],'swim_m':5000},
}


def _vel_bike(potencia, peso, cda=0.32, crr=0.005):
    """Resuelve v desde P = 0.5*CdA*rho*v^3 + Crr*m*g*v (Newton-Raphson)."""
    rho = 1.225
    v = 8.0
    for _ in range(20):
        f = 0.5*cda*rho*v**3 + crr*peso*9.81*v - potencia
        df = 1.5*cda*rho*v**2 + crr*peso*9.81
        v = max(2, v - f/df)
    return v  # m/s


def _factor_temp(temp):
    """Factor de degradacion por calor (Ely 2007): ~0.3%/°C arriba de 20°C."""
    if temp <= 20: return 1.0
    return 1.0 + (temp - 20) * 0.003  # pace multiplier (mas lento)


def _tasa_sudoracion(peso, temp):
    """Tasa de sudoracion en ml/hr (Sawka 2007)."""
    if temp >= 35: factor = 15
    elif temp >= 25: factor = 12
    elif temp >= 15: factor = 9
    else: factor = 6
    return round(min(1400, peso * factor))  # cap 1400 ml/hr


def _sodio_por_litro(temp):
    """Sodio perdido en mg/L de sudor (Baker 2017)."""
    if temp >= 30: return 900
    if temp >= 25: return 750
    return 600


def generar_estrategia(atleta, carrera_tipo, condiciones=None):
    dist_override = float(condiciones.get('dist_km', 0)) if condiciones else 0

    if carrera_tipo == 'custom' and dist_override > 0:
        # Distancia custom: NO usar diccionario
        carrera = {'dist_km': dist_override, 'deportes': ['running'], 'run_km': dist_override}
    elif carrera_tipo in CARRERAS:
        carrera = dict(CARRERAS[carrera_tipo])
        # Override distancia si viene
        if dist_override > 0 and len(carrera.get('deportes', [])) <= 1:
            carrera['dist_km'] = dist_override
            carrera['run_km'] = dist_override
    else:
        return {'error': f'Carrera {carrera_tipo} no soportada'}

    cond = condiciones or {}
    temp = cond.get('temperatura', 20)
    peso = float(atleta.get('peso_kg') or 70)
    edad = int(atleta.get('edad') or 30)
    sexo = atleta.get('sexo') or 'M'
    altura = float(atleta.get('altura_cm') or 170)

    bmr = calcular_bmr(peso, altura, edad, sexo)
    ft = _factor_temp(temp)
    sudor_hr = _tasa_sudoracion(peso, temp)
    sodio_l = _sodio_por_litro(temp)

    segmentos = []
    if len(carrera.get('deportes', [])) > 1:
        segmentos = _tri(atleta, carrera, carrera_tipo, cond, ft)
    elif 'running' in carrera['deportes']:
        segmentos = _run(atleta, carrera, carrera_tipo, cond, ft)
    elif 'cycling' in carrera['deportes']:
        segmentos = _bike(atleta, carrera, carrera_tipo, cond, ft)
    elif 'swimming' in carrera['deportes']:
        segmentos = _swim(atleta, carrera, carrera_tipo, cond, ft)

    # Totales
    t_min = sum(s.get('tiempo_min', 0) for s in segmentos)
    kcal_t = sum(s.get('kcal', 0) for s in segmentos)
    cho_quemado = sum(s.get('cho_quemado_g', 0) for s in segmentos)
    t_hr = t_min / 60
    dist = carrera['dist_km']

    # ── NUTRICION por distancia y deporte (Burke 2011, Jeukendrup 2014) ──
    deportes = carrera.get('deportes', ['running'])
    es_tri = len(deportes) > 1
    es_bike = 'cycling' in deportes and not es_tri

    if dist <= 10 and not es_tri:
        # 5K-10K running: no necesita geles
        nutricion = {
            'cho_hr_g': 0, 'cho_total_g': 0,
            'geles': [], 'tipo': 'No necesita geles ni CHO. Hidratarse en puestos.',
            'primer_gel_min': None, 'freq_gel_min': None,
            'pre_carrera': f'Desayuno normal 2-3h antes. {round(peso*5)}ml agua.',
        }
    elif dist <= 21.1 and not es_tri:
        # 21K running: 1-2 geles, no más
        gel_1_km = round(dist * 0.4)  # ~km 8
        gel_2_km = round(dist * 0.7)  # ~km 15
        nutricion = {
            'cho_hr_g': 30, 'cho_total_g': 50,
            'geles': [
                {'km': gel_1_km, 'tipo': '1 gel (25g CHO)'},
                {'km': gel_2_km, 'tipo': '1 gel (25g CHO)'},
            ],
            'tipo': f'2 geles: km {gel_1_km} y km {gel_2_km}. No más.',
            'primer_gel_min': None, 'freq_gel_min': None,
            'pre_carrera': f'{round(peso*1.5)}g CHO 3h antes. {round(peso*5)}ml agua 2h antes.',
        }
    elif dist <= 42.2 and not es_tri:
        # Maratón running: gel cada 35-40min desde km 8
        n_geles = max(3, int((t_min - 30) / 35))
        geles = []
        for g in range(n_geles):
            km_gel = round(8 + g * (dist - 8) / n_geles)
            geles.append({'km': km_gel, 'tipo': 'gel 25g CHO' if g % 2 == 0 else 'gel + electrolitos'})
        nutricion = {
            'cho_hr_g': 60, 'cho_total_g': round(60 * t_hr),
            'geles': geles,
            'tipo': f'{n_geles} geles desde km 8, cada ~{round((dist-8)/n_geles)}km (~35-40min). Alternar gel simple y con electrolitos.',
            'primer_gel_min': None, 'freq_gel_min': None,
            'pre_carrera': f'{round(peso*2)}g CHO 3h antes. {round(peso*7)}ml agua.',
        }
    elif es_bike:
        # Ciclismo: más fácil comer, gel/barrita cada 30-45min
        freq = 30 if t_hr > 3 else 45
        n_ingestas = max(1, int(t_min / freq))
        nutricion = {
            'cho_hr_g': 60 if t_hr > 2 else 30,
            'cho_total_g': round((60 if t_hr > 2 else 30) * t_hr),
            'geles': [],
            'tipo': f'Cada {freq}min: gel o barrita (25-30g CHO). Isotónica en caramañola. Total {n_ingestas} ingestas.',
            'primer_gel_min': 30, 'freq_gel_min': freq,
            'pre_carrera': f'{round(peso*2)}g CHO 3h antes.',
        }
    else:
        # Triatlón: swim nada, bike come, run geles
        bike_km = carrera.get('bike_km', 40)
        run_km = carrera.get('run_km', 10)
        freq_bike = 20 if t_hr > 4 else 30
        n_geles_run = max(0, int(run_km / 7) - 1) if run_km > 10 else 0
        cho_bike = 60 if t_hr > 3 else 45
        nutricion = {
            'cho_hr_g': cho_bike,
            'cho_total_g': round(cho_bike * t_hr * 0.7),
            'geles': [],
            'tipo': (f'Swim: nada. '
                     f'Bike: {cho_bike}g CHO/hr cada {freq_bike}min (gel+isotónica+barrita). '
                     f'Run: {n_geles_run} geles (cada ~7km desde km 5). '
                     f'T1/T2: trago de isotónica.'),
            'primer_gel_min': None, 'freq_gel_min': None,
            'pre_carrera': f'{round(peso*2)}g CHO 3h antes. {round(peso*7)}ml agua.',
        }

    # ── HIDRATACION por deporte y distancia (ACSM 2007, Noakes 2012) ──
    if not es_tri and not es_bike:
        # Running: beber en puestos de hidratación (cada 3-5km)
        km_entre_puestos = 5 if dist > 15 else 3
        n_puestos = max(1, int(dist / km_entre_puestos))
        ml_por_puesto = 150 if temp < 25 else 200
        ml_total = n_puestos * ml_por_puesto
        hidratacion = {
            'ml_hr': round(ml_total / max(t_hr, 0.5)),
            'ml_total': ml_total,
            'ml_por_toma': ml_por_puesto,
            'freq_min': None,
            'freq_km': km_entre_puestos,
            'n_puestos': n_puestos,
            'sodio_mg_hr': round(_sodio_por_litro(temp) * ml_total / 1000 / max(t_hr, 0.5)),
            'sudor_estimado_ml_hr': sudor_hr,
            'tipo': f'{n_puestos} puestos cada ~{km_entre_puestos}km. {ml_por_puesto}ml por puesto (agua o isotónica). Total ~{ml_total}ml. Temp {temp}°C.',
        }
    elif es_bike:
        # Ciclismo: caramañola, beber cada 15-20min
        ml_hr_bike = min(750, sudor_hr)
        hidratacion = {
            'ml_hr': ml_hr_bike,
            'ml_total': round(ml_hr_bike * t_hr),
            'ml_por_toma': round(ml_hr_bike / 3),
            'freq_min': 20,
            'freq_km': None,
            'sodio_mg_hr': round(_sodio_por_litro(temp) * ml_hr_bike / 1000),
            'sudor_estimado_ml_hr': sudor_hr,
            'tipo': f'{ml_hr_bike}ml/hr. Caramañola: trago cada 20min (~{round(ml_hr_bike/3)}ml). Temp {temp}°C.',
        }
    else:
        # Triatlón: swim nada, bike caramañola, run puestos
        ml_hr_bike = min(700, sudor_hr)
        ml_puesto_run = 150 if temp < 28 else 200
        run_km = carrera.get('run_km', 10)
        n_puestos_run = max(1, int(run_km / 3))
        hidratacion = {
            'ml_hr': ml_hr_bike,
            'ml_total': round(ml_hr_bike * t_hr * 0.6 + n_puestos_run * ml_puesto_run),
            'ml_por_toma': round(ml_hr_bike / 3),
            'freq_min': 20,
            'freq_km': 3,
            'sodio_mg_hr': round(_sodio_por_litro(temp) * ml_hr_bike / 1000),
            'sudor_estimado_ml_hr': sudor_hr,
            'tipo': (f'Swim: nada. '
                     f'Bike: {ml_hr_bike}ml/hr (caramañola cada 20min). '
                     f'Run: {ml_puesto_run}ml cada puesto (~{n_puestos_run} puestos). '
                     f'Temp {temp}°C.'),
        }

    deficit = max(0, cho_quemado - GLUCOGENO_TOTAL_G)

    return {
        'carrera': carrera_tipo,
        'distancia_km': carrera['dist_km'],
        'bmr': bmr,
        'condiciones': {'temp': temp, 'humedad': cond.get('humedad', 50), 'altitud': cond.get('altitud', 0), 'desnivel': cond.get('desnivel', 0)},
        'atleta': {'peso_kg': peso, 'edad': edad, 'sexo': sexo,
                   'pace_umbral': float(atleta.get('pace_umbral_run') or 5.5),
                   'ftp': int(atleta.get('ftp_watts') or 200)},
        'segmentos': segmentos,
        'tiempo_estimado': {
            'total_min': round(t_min, 1),
            'total_hms': f"{int(t_min//60)}h {int(t_min%60):02d}min",
        },
        'energia': {
            'kcal_total': round(kcal_t),
            'cho_quemado_g': round(cho_quemado),
            'glucogeno_inicio_g': GLUCOGENO_TOTAL_G,
            'cho_ingerir_g': nutricion['cho_total_g'],
            'deficit_g': round(deficit),
        },
        'nutricion': nutricion,
        'hidratacion': hidratacion,
    }


def _run(atleta, carrera, tipo, cond, ft):
    pace_u = float(atleta.get('pace_umbral_run', 5.5))
    peso = float(atleta.get('peso_kg', 70))
    dist = carrera.get('run_km', carrera['dist_km'])
    fatiga_extra = float(atleta.get('_fatiga_bike', 1.0))

    # Factor de intensidad segun distancia (Daniels VDOT, tablas publicadas)
    fi = {'5K':0.97, '10K':1.00, '21K':1.03, 'maraton':1.08}.get(tipo, 1.03)
    # Distancias custom
    if tipo not in ('5K','10K','21K','maraton') and dist > 0:
        if dist <= 5: fi = 0.97
        elif dist <= 10: fi = 1.00
        elif dist <= 15: fi = 1.03
        elif dist <= 21.1: fi = 1.03
        elif dist <= 30: fi = 1.05
        else: fi = 1.08
    pace_base = pace_u * fi * ft * fatiga_extra

    n = max(3, int(dist / 3))
    km_seg = dist / n
    gluc = GLUCOGENO_TOTAL_G
    segs = []

    for i in range(n):
        # Negative split: arrancar 1% lento, terminar 1% rapido
        prog = -0.01 + 0.02 * (i / max(n-1, 1))
        pace = pace_base * (1 - prog)
        t = pace * km_seg
        zona = 4 if fi <= 1.0 else (3 if fi <= 1.05 else 2)
        cho = CHO_RATE[zona] * t
        kcal = KCAL_MIN_70KG[zona] * (peso/70) * t
        gluc = max(0, gluc - cho)

        segs.append({
            'segmento': i+1, 'deporte': 'running',
            'km_inicio': round(i*km_seg, 1), 'km_fin': round((i+1)*km_seg, 1),
            'distancia_km': round(km_seg, 1),
            'pace': f"{int(pace)}:{int((pace%1)*60):02d}",
            'pace_decimal': round(pace, 2),
            'zona': zona, 'tiempo_min': round(t, 1),
            'cho_quemado_g': round(cho), 'kcal': round(kcal),
            'glucogeno_pct': round(gluc/GLUCOGENO_TOTAL_G*100),
            'ingesta_cho_g': round(cho * 0.6) if t > 3 else 0,  # Reponer 60% de lo quemado
            'hidratacion_ml': round(_tasa_sudoracion(peso, cond.get('temperatura',20))/60*t),
        })
    return segs


def _bike(atleta, carrera, tipo, cond, ft):
    ftp = float(atleta.get('ftp_watts', 200))
    peso = float(atleta.get('peso_kg', 70))
    dist = carrera.get('bike_km', carrera['dist_km'])

    # IF segun distancia (Coggan 2003)
    if_base = atleta.get('_if_override',
        {'crono':0.95,'ruta':0.75,'mtb':0.82,'granfondo':0.72,
         'sprint':0.88,'olimpico':0.82,'70.3':0.76,'ironman':0.70}.get(tipo, 0.80))

    cda = 0.45 if tipo=='mtb' else (0.32 if tipo in ('crono','70.3','ironman','olimpico','sprint') else 0.35)
    crr = 0.008 if tipo=='mtb' else 0.005

    n = max(4, int(dist/20))
    km_seg = dist / n
    gluc = GLUCOGENO_TOTAL_G
    segs = []

    for i in range(n):
        # Progressive pacing bike: +3% segunda mitad (Atkinson 2007)
        if i < n * 0.5:
            pwr = ftp * if_base * 0.97  # Primera mitad: -3%
        else:
            pwr = ftp * if_base * 1.03  # Segunda mitad: +3%
        pwr = round(pwr)

        # Degradacion por calor en bike (menor que run, hay viento)
        pwr_real = pwr  # En bike el calor afecta menos por conveccion

        v = _vel_bike(pwr_real, peso, cda, crr)
        vel_kmh = round(v * 3.6, 1)
        t = (km_seg / vel_kmh) * 60  # minutos

        zona = 4 if if_base >= 0.90 else (3 if if_base >= 0.76 else 2)
        cho = CHO_RATE[zona] * t
        kcal = KCAL_MIN_70KG[zona] * (peso/70) * t
        gluc = max(0, gluc - cho)

        segs.append({
            'segmento': i+1, 'deporte': 'cycling',
            'km_inicio': round(i*km_seg, 1), 'km_fin': round((i+1)*km_seg, 1),
            'distancia_km': round(km_seg, 1),
            'potencia_w': pwr, 'if': round(pwr/ftp, 2),
            'vel_kmh': vel_kmh, 'cadencia_rpm': 80 if tipo=='mtb' else 88,
            'zona': zona, 'tiempo_min': round(t, 1),
            'cho_quemado_g': round(cho), 'kcal': round(kcal),
            'glucogeno_pct': round(gluc/GLUCOGENO_TOTAL_G*100),
            'ingesta_cho_g': round(cho * 0.7),  # Reponer 70% en bike (mas facil comer)
            'hidratacion_ml': round(_tasa_sudoracion(peso, cond.get('temperatura',20))/60*t),
        })
    return segs


def _swim(atleta, carrera, tipo, cond, ft):
    css = float(atleta.get('css_100m', 1.85))
    dist_m = carrera.get('swim_m', int(carrera['dist_km']*1000))
    peso = float(atleta.get('peso_kg', 70))

    pace_100 = css * 1.03  # Aguas abiertas +3%
    n = max(3, dist_m // 400)
    m_seg = dist_m / n
    segs = []

    for i in range(n):
        t = pace_100 * (m_seg / 100)
        cho = CHO_RATE[3] * t * 0.5  # Swim usa menos CHO (Chatard 2001)
        kcal = KCAL_MIN_70KG[3] * (peso/70) * t * 0.7  # Termoregulacion en agua es menor

        segs.append({
            'segmento': i+1, 'deporte': 'swimming',
            'distancia_m': round(m_seg),
            'pace_100m': f"{int(pace_100)}:{int((pace_100%1)*60):02d}",
            'pace_decimal': round(pace_100, 2),
            'zona': 3, 'tiempo_min': round(t, 1),
            'cho_quemado_g': round(cho), 'kcal': round(kcal),
            'spm': 55,
            'ingesta_cho_g': 0,  # No se come nadando
            'hidratacion_ml': 0,  # No se bebe nadando
        })
    return segs


def _tri(atleta, carrera, tipo, cond, ft):
    segs = []
    # SWIM
    sc = {'dist_km':carrera['swim_m']/1000, 'swim_m':carrera['swim_m'], 'deportes':['swimming']}
    segs += _swim(atleta, sc, tipo, cond, ft)
    segs.append({'segmento':len(segs)+1,'deporte':'transicion','nombre':'T1','tiempo_min':3,'cho_quemado_g':0,'kcal':0})

    # BIKE
    bc = {'dist_km':carrera['bike_km'], 'bike_km':carrera['bike_km'], 'deportes':['cycling']}
    segs += _bike(atleta, bc, tipo, cond, ft)
    segs.append({'segmento':len(segs)+1,'deporte':'transicion','nombre':'T2','tiempo_min':2,'cho_quemado_g':0,'kcal':0})

    # RUN (con fatiga de bike, Millet 2011)
    fatiga = {'sprint':1.03,'olimpico':1.05,'70.3':1.08,'ironman':1.12}.get(tipo, 1.05)
    atleta_run = dict(atleta)
    atleta_run['_fatiga_bike'] = fatiga
    rc = {'dist_km':carrera['run_km'], 'run_km':carrera['run_km'], 'deportes':['running']}
    segs += _run(atleta_run, rc, tipo, cond, ft)

    return segs


if __name__ == '__main__':
    atleta = {
        'nombre':'Jimena', 'peso_kg':65, 'altura_cm':165, 'edad':35, 'sexo':'F',
        'pace_umbral_run':5.09, 'ftp_watts':151, 'css_100m':1.85,
    }

    for tipo in ['70.3', 'olimpico', 'ironman']:
        est = generar_estrategia(atleta, tipo, {'temperatura': 28, 'humedad': 65})
        print(f"\n{'='*70}")
        print(f"  {tipo.upper()} — {est['tiempo_estimado']['total_hms']} | {est['energia']['kcal_total']} kcal")
        print(f"{'='*70}")
        for s in est['segmentos']:
            d = s['deporte'][:4]
            if d == 'tran': print(f"  {s['nombre']} ({s['tiempo_min']}min)")
            elif d == 'swim': print(f"  Swim {s['distancia_m']}m: {s['pace_100m']}/100m | CHO -{s['cho_quemado_g']}g")
            elif d == 'cycl': print(f"  Bike km{s['km_inicio']}-{s['km_fin']}: {s['potencia_w']}W IF{s['if']} {s['vel_kmh']}km/h | CHO -{s['cho_quemado_g']}g +{s['ingesta_cho_g']}g | {s['hidratacion_ml']}ml")
            elif d == 'runn': print(f"  Run km{s['km_inicio']}-{s['km_fin']}: {s['pace']} | Gluc {s['glucogeno_pct']}% | CHO -{s['cho_quemado_g']}g +{s['ingesta_cho_g']}g | {s['hidratacion_ml']}ml")

        print(f"\n  Nutricion: {est['nutricion']['tipo']}")
        print(f"  Hidratacion: {est['hidratacion']['tipo']}")
        print(f"  Energia: {est['energia']['cho_quemado_g']}g quemados, ingerir {est['nutricion']['cho_total_g']}g")
        if est['energia']['deficit_g'] > 0:
            print(f"  ⚠️ Sin ingesta: deficit de {est['energia']['deficit_g']}g CHO → bonking")
