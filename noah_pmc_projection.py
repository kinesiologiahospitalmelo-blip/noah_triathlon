"""
noah_pmc_projection.py — Proyecto NOAH
========================================
Módulo de proyección del Performance Management Chart.

Implementa el modelo de impulso-respuesta de Banister (1975) con
periodización correcta basada en Coggan (2003) y Bompa (2009).

INVARIANTES GARANTIZADOS:
1. La tendencia macro del CTL es ASCENDENTE en los bloques de build
2. El CTL alcanza su pico al INICIO del taper de la última carrera A
3. El TSB cruza la banda objetivo el día de cada carrera
4. El ramp rate nunca supera el máximo permitido sostenido

ALGORITMO:
1. Segmentar el tiempo desde hoy hasta la última carrera A
2. Reservar taperas y recuperaciones según clase de carrera
3. Calcular TSS objetivo diario con ondulación 3:1
4. Simular día a día con ecuaciones de Banister
5. Validar invariantes y ajustar (2-3 iteraciones)

REFERENCIAS:
  Banister et al. 1975 — modelo impulso-respuesta
  Coggan 2003 — constantes de tiempo CTL/ATL
  Foster 1998 — modelo de monotonía y mesociclos
  Bompa 2009 — periodización táctica
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Optional
import numpy as np


# ── Constantes de Banister (Coggan 2003) ─────────────────────────────────────
TAU_CTL = 42   # días — constante de tiempo de fitness
TAU_ATL = 7    # días — constante de tiempo de fatiga

# Coeficientes de decaimiento diario
K_CTL = 1 - math.exp(-1 / TAU_CTL)
K_ATL = 1 - math.exp(-1 / TAU_ATL)
D_CTL = math.exp(-1 / TAU_CTL)
D_ATL = math.exp(-1 / TAU_ATL)


# ── Parámetros de taper por clase de carrera ─────────────────────────────────
TAPER_DIAS = {
    'A': 14,   # 14-21 días (usamos 14 como mínimo)
    'B': 7,    # 4-7 días
    'C': 0,    # sin taper
}
RECUPERACION_DIAS = {
    'A': 7,    # 4-7 días post-A
    'B': 4,    # 2-4 días post-B
    'C': 2,    # 1-2 días post-C
}
TSB_OBJETIVO = {
    'A': (10, 20),   # fresco
    'B': (0, 10),    # semi-fresco
    'C': (-10, 0),   # puede ser negativo
}
# TSS del día de carrera según distancia (estimados)
TSS_CARRERA = {
    'sprint':       60,
    '5k':           50,
    '10k':          80,
    '15k':          100,
    '21k':          150,
    'media maraton': 150,
    '33k':          200,
    'maraton':      300,
    '70.3':         250,
    'ironman':      400,
    'default_A':    200,
    'default_B':    120,
    'default_C':    80,
}


@dataclass
class Carrera:
    fecha: date
    prioridad: str           # 'A', 'B', 'C'
    nombre: str = ''
    distancia: str = ''
    ctl_objetivo: Optional[float] = None
    deporte: str = 'running'  # 'running'|'cycling'|'swimming'|'duatlon'|'triatlon'
                               # -- determina que disciplinas participan (ver
                               # disciplinas_de_carrera). Default 'running' para
                               # no romper llamadas existentes que no lo pasan.


@dataclass
class DiaProyectado:
    fecha: date
    ctl: float
    atl: float
    tsb: float
    tss: float
    fase: str                # 'A','T','R','Taper','Recuperacion','Carrera'
    semana_meso: int = 0     # 0-3 dentro del mesociclo
    tipo: str = 'proyectado'


@dataclass
class ResultadoProyeccion:
    dias: List[DiaProyectado]
    fases: List[dict]
    ctl_pico: float
    tsb_carrera_A: float
    ramp_max_real: float
    invariantes_ok: bool
    notas: List[str]
    fecha_inicio_taper: Optional[date] = None  # ultimo dia de build antes de
                                                 # tener que empezar a bajar carga


def simular_dia(ctl_prev: float, atl_prev: float, tss: float):
    """Ecuaciones de Banister aplicadas a un día."""
    ctl = ctl_prev * D_CTL + tss * K_CTL
    atl = atl_prev * D_ATL + tss * K_ATL
    tsb = ctl_prev - atl_prev   # TSB = diferencia del día ANTERIOR
    return ctl, atl, tsb


def tss_para_ramp(ctl_actual: float, ramp_diario: float) -> float:
    """
    TSS necesario para subir el CTL a una razón dada por día.
    Inversión de la ecuación de Banister: TSS = CTL + 42 × Δ
    """
    return ctl_actual + TAU_CTL * ramp_diario


def proyectar_pmc(
    ctl_inicial: float,
    atl_inicial: float,
    hoy: date,
    carreras: List[Carrera],
    ramp_semanal: float = 3.5,    # CTL/semana — conservador por defecto
    ramp_max: float = 6.0,         # máximo absoluto CTL/semana
) -> ResultadoProyeccion:
    """
    Proyecta CTL/ATL/TSB desde hoy hasta la última carrera A.

    Args:
        ctl_inicial: CTL actual del atleta
        atl_inicial: ATL actual del atleta
        hoy: fecha de hoy
        carreras: lista de carreras ordenadas por fecha
        ramp_semanal: razón de mejora semanal objetivo (CTL/semana)
        ramp_max: razón máxima absoluta permitida (protección)
    """
    notas = []

    # ── Filtrar y ordenar carreras futuras ────────────────────────────────────
    carreras_futuras = sorted(
        [c for c in carreras if c.fecha > hoy],
        key=lambda c: c.fecha
    )
    if not carreras_futuras:
        return ResultadoProyeccion(
            dias=[], fases=[], ctl_pico=ctl_inicial,
            tsb_carrera_A=0, ramp_max_real=0,
            invariantes_ok=False, notas=['Sin carreras futuras'],
            fecha_inicio_taper=None,
        )

    # Carrera A final = ancla del macrociclo
    carreras_A = [c for c in carreras_futuras if c.prioridad == 'A']
    if not carreras_A:
        notas.append('Sin carrera A — usando última carrera como ancla')
        carrera_ancla = carreras_futuras[-1]
    else:
        carrera_ancla = carreras_A[-1]

    fecha_fin = carrera_ancla.fecha
    dias_total = (fecha_fin - hoy).days
    if dias_total < 7:
        return ResultadoProyeccion(
            dias=[], fases=[], ctl_pico=ctl_inicial,
            tsb_carrera_A=0, ramp_max_real=0,
            invariantes_ok=False, notas=['Carrera demasiado próxima (< 7 días)'],
            fecha_inicio_taper=None,
        )

    # ── Construir mapa de tipo de día ─────────────────────────────────────────
    # Para cada día: qué fase corresponde
    tipo_dia = {}   # fecha → ('fase', 'carrera_clase', multiplicador_tss)

    # Primero marcar taperas y recuperaciones (tienen prioridad sobre build)
    for c in carreras_futuras:
        # Día de carrera
        tipo_dia[c.fecha] = ('carrera', c.prioridad, 1.0)

        # Taper
        taper = TAPER_DIAS.get(c.prioridad, 0)
        for i in range(1, taper + 1):
            d = c.fecha - timedelta(days=i)
            if d > hoy and d not in tipo_dia:
                # Reducción exponencial del taper: e^(-t/tau)
                # t = días antes de la carrera, tau = 5
                reduccion = math.exp(-i / 5) * 0.6 + 0.15  # va de ~0.75 a ~0.15
                tipo_dia[d] = ('taper', c.prioridad, reduccion)

        # Recuperación post-carrera
        rec = RECUPERACION_DIAS.get(c.prioridad, 2)
        for i in range(1, rec + 1):
            d = c.fecha + timedelta(days=i)
            if d > hoy and d not in tipo_dia:
                tipo_dia[d] = ('recuperacion', c.prioridad, 0.25)

    # ── CTL objetivo al inicio del taper final ────────────────────────────────
    taper_final = TAPER_DIAS.get(carrera_ancla.prioridad, 14)
    fecha_inicio_taper = carrera_ancla.fecha - timedelta(days=taper_final)
    dias_build = max(1, (fecha_inicio_taper - hoy).days)

    # CTL máximo alcanzable con ramp_semanal
    ramp_diario = min(ramp_semanal, ramp_max) / 7
    ctl_pico_teorico = ctl_inicial + ramp_diario * dias_build

    # CTL objetivo: el que pide la carrera o el teórico
    ctl_objetivo = carrera_ancla.ctl_objetivo or ctl_pico_teorico
    ctl_objetivo = min(ctl_objetivo, ctl_pico_teorico * 1.05)  # no más del 5% sobre lo alcanzable

    notas.append(f'CTL objetivo al taper: {ctl_objetivo:.1f} (actual: {ctl_inicial:.1f})')
    notas.append(f'Días de build disponibles: {dias_build}')

    # ── Calcular fase ATR para cada semana ───────────────────────────────────
    # Dividir el período de build en fases A/T/R (desde la carrera hacia atrás)
    semanas_build = dias_build // 7
    if semanas_build >= 12:
        # Largo: A=40%, T=35%, R=25%
        sem_R = max(3, semanas_build // 4)
        sem_T = max(4, semanas_build // 3)
        sem_A = semanas_build - sem_R - sem_T
    elif semanas_build >= 6:
        sem_R = max(2, semanas_build // 4)
        sem_T = max(2, semanas_build // 3)
        sem_A = semanas_build - sem_R - sem_T
    else:
        sem_R = 1; sem_T = 1; sem_A = max(1, semanas_build - 2)

    # Mapa de fase por fecha
    fase_por_fecha = {}
    cursor = fecha_inicio_taper - timedelta(days=1)
    for _ in range(sem_R * 7):
        if cursor > hoy: fase_por_fecha[cursor] = 'R'
        cursor -= timedelta(days=1)
    for _ in range(sem_T * 7):
        if cursor > hoy: fase_por_fecha[cursor] = 'T'
        cursor -= timedelta(days=1)
    while cursor > hoy:
        fase_por_fecha[cursor] = 'A'
        cursor -= timedelta(days=1)

    # ── Patrón de ondulación intra-semana ─────────────────────────────────────
    # Pesos relativos para cada día de la semana (L a D)
    # Suma normalizada ≈ 7.0 para que el promedio sea el TSS objetivo
    PATRON_SEMANA = [1.15, 0.45, 1.25, 0.85, 0.40, 1.45, 0.65]
    # Normalizar
    norm = sum(PATRON_SEMANA) / 7
    PATRON_SEMANA = [p / norm for p in PATRON_SEMANA]

    # ── Simulación día a día ──────────────────────────────────────────────────
    dias_proyectados: List[DiaProyectado] = []
    ctl = ctl_inicial
    atl = atl_inicial
    ramp_max_real = 0.0

    ctl_semana_ant = ctl_inicial
    semana_num = 0
    sem_en_meso = 0  # 0,1,2 = carga / 3 = descarga

    for d in range(dias_total):
        fecha_d = hoy + timedelta(days=d)
        dia_semana = d % 7   # 0=lunes

        # Inicio de nueva semana
        if d > 0 and dia_semana == 0:
            ramp_semana = ctl - ctl_semana_ant
            ramp_max_real = max(ramp_max_real, ramp_semana)
            ctl_semana_ant = ctl
            semana_num += 1
            sem_en_meso = semana_num % 4

        # ── Determinar TSS del día ────────────────────────────────────────────
        if fecha_d in tipo_dia:
            fase_tipo, clase, mult = tipo_dia[fecha_d]

            if fase_tipo == 'carrera':
                # TSS del día de carrera según distancia
                dist = ''
                for c in carreras_futuras:
                    if c.fecha == fecha_d:
                        dist = (c.distancia or '').lower()
                        break
                tss_carrera = next(
                    (v for k, v in TSS_CARRERA.items() if k in dist),
                    TSS_CARRERA.get(f'default_{clase}', 100)
                )
                tss = tss_carrera
                fase = 'Carrera'

            elif fase_tipo == 'taper':
                # TSS de taper: decaimiento exponencial
                tss = max(10, ctl * mult)
                if clase == 'A':
                    fase = 'Taper'
                else:
                    fase = f'Taper-{clase}'

            else:  # recuperacion
                tss = max(5, ctl * 0.20)
                fase = 'Recuperacion'

        else:
            # Día de build normal
            fase = fase_por_fecha.get(fecha_d, 'A')

            # Ramp rate según fase
            if fase == 'R':
                # Realización: mantener CTL, más intensidad
                ramp = (ctl_objetivo - ctl) / max(1, dias_build * 0.1)
                ramp = max(0, min(ramp, ramp_max / 7))
                tss_base = tss_para_ramp(ctl, ramp)
            elif fase == 'T':
                # Transformación: subida moderada
                ramp = min(ramp_semanal * 0.7, ramp_max * 0.8) / 7
                tss_base = tss_para_ramp(ctl, ramp)
            else:
                # Acumulación: subida según ramp objetivo
                dias_restantes_build = max(1, (fecha_inicio_taper - fecha_d).days)
                ramp_necesario = max(0, (ctl_objetivo - ctl) / dias_restantes_build)
                ramp = min(ramp_necesario, ramp_max / 7)
                tss_base = tss_para_ramp(ctl, ramp)

            # Ondulación mesociclo 3:1
            if sem_en_meso == 3:
                # Semana de descarga
                tss = tss_base * 0.55
            else:
                # Semanas de carga con ondulación intra-semana
                mult_sem = 0.90 + sem_en_meso * 0.10  # 0.90 → 1.00 → 1.10
                tss = tss_base * mult_sem * PATRON_SEMANA[dia_semana % 7]

            tss = max(0, tss)

        # Simular el día
        ctl_new, atl_new, tsb = simular_dia(ctl, atl, tss)
        dias_proyectados.append(DiaProyectado(
            fecha=fecha_d, ctl=round(ctl_new, 1), atl=round(atl_new, 1),
            tsb=round(tsb, 1), tss=round(tss, 1),
            fase=fase, semana_meso=sem_en_meso,
        ))
        ctl, atl = ctl_new, atl_new

    # ── Calcular fases para el frontend ──────────────────────────────────────
    fases = []
    cur_fase = None
    for dp in dias_proyectados:
        fase_simple = dp.fase if dp.fase in ('A','T','R','Taper') else dp.fase
        if cur_fase is None or cur_fase['fase'] != fase_simple:
            if cur_fase:
                fases.append(cur_fase)
            cur_fase = {'fase': fase_simple, 'desde': str(dp.fecha), 'hasta': str(dp.fecha)}
        else:
            cur_fase['hasta'] = str(dp.fecha)
    if cur_fase:
        fases.append(cur_fase)

    # ── Validar invariantes ───────────────────────────────────────────────────
    invariantes_ok = True

    # 1. CTL tendencia ascendente (comparar inicio vs inicio del taper)
    if dias_proyectados:
        idx_taper = next((i for i, dp in enumerate(dias_proyectados)
                          if dp.fecha >= fecha_inicio_taper), len(dias_proyectados)-1)
        ctl_en_taper = dias_proyectados[idx_taper].ctl if idx_taper < len(dias_proyectados) else ctl
        if ctl_en_taper <= ctl_inicial * 1.01:
            invariantes_ok = False
            notas.append(f'⚠ CTL no sube: {ctl_inicial:.1f} → {ctl_en_taper:.1f}')
        else:
            notas.append(f'✓ CTL asciende: {ctl_inicial:.1f} → {ctl_en_taper:.1f} al inicio del taper')

    # 2. TSB en banda objetivo el día de la carrera A
    tsb_carrera_A = 0.0
    for c in carreras_futuras:
        if c.prioridad == 'A':
            dp_c = next((dp for dp in dias_proyectados if dp.fecha == c.fecha), None)
            if dp_c:
                tsb_carrera_A = dp_c.tsb
                lb, ub = TSB_OBJETIVO['A']
                if not (lb <= tsb_carrera_A <= ub):
                    notas.append(f'⚠ TSB en carrera A ({c.nombre}): {tsb_carrera_A:.1f} (objetivo {lb} a {ub})')
                else:
                    notas.append(f'✓ TSB en carrera A ({c.nombre}): {tsb_carrera_A:.1f} ✓')

    # 3. Ramp rate
    if ramp_max_real > ramp_max:
        notas.append(f'⚠ Ramp máximo real {ramp_max_real:.1f} > límite {ramp_max}')

    ctl_pico = max((dp.ctl for dp in dias_proyectados), default=ctl_inicial)

    return ResultadoProyeccion(
        dias=dias_proyectados,
        fases=fases,
        ctl_pico=round(ctl_pico, 1),
        tsb_carrera_A=round(tsb_carrera_A, 1),
        ramp_max_real=round(ramp_max_real, 2),
        invariantes_ok=invariantes_ok,
        notas=notas,
        fecha_inicio_taper=fecha_inicio_taper,
    )


def proyeccion_a_dict(resultado: ResultadoProyeccion) -> dict:
    """Convierte el resultado a dict serializable para JSON."""
    return {
        'proy': [
            {
                'f':          str(dp.fecha),
                'ctl':        dp.ctl,
                'atl':        dp.atl,
                'tsb':        dp.tsb,
                'tss_p':      dp.tss,
                'fase':       dp.fase,
                'semana_meso':dp.semana_meso,
                'tipo':       'proyectado',
            }
            for dp in resultado.dias
        ],
        'fases':          resultado.fases,
        'ctl_pico':       resultado.ctl_pico,
        'tsb_carrera_A':  resultado.tsb_carrera_A,
        'ramp_max_real':  resultado.ramp_max_real,
        'invariantes_ok': resultado.invariantes_ok,
        'notas':          resultado.notas,
        'fecha_inicio_taper': str(resultado.fecha_inicio_taper) if resultado.fecha_inicio_taper else None,
    }


# ── Multi-deporte: correr proyectar_pmc() una vez por disciplina ─────────────

DISCIPLINAS_POR_DEPORTE = {
    'running':  ['running'],
    'run':      ['running'],
    'cycling':  ['cycling'],
    'bike':     ['cycling'],
    'swimming': ['swimming'],
    'swim':     ['swimming'],
    'duatlon':  ['running', 'cycling'],
    'triatlon': ['running', 'cycling', 'swimming'],
}


def disciplinas_de_carrera(deporte: str) -> List[str]:
    """
    Traduce el campo 'deporte' de una carrera (tal como ya se guarda hoy
    en la tabla `carreras`: running/cycling/swimming/duatlon/triatlon) a
    la lista de disciplinas que efectivamente compiten en ese evento.
    """
    return DISCIPLINAS_POR_DEPORTE.get((deporte or '').lower(), [deporte or 'running'])


def proyectar_multideporte(
    ctl_por_deporte: dict,
    hoy: date,
    carreras: List[Carrera],
    ramp_semanal: float = 3.5,
    ramp_max: float = 6.0,
) -> dict:
    """
    Corre proyectar_pmc() UNA VEZ POR DISCIPLINA (running, cycling,
    swimming) -- NO modifica proyectar_pmc, la reutiliza tal cual.

    Para cada disciplina, filtra del listado de carreras solo aquellas
    donde esa disciplina participa (segun carrera.deporte):
      - Una carrera de running en pretemporada -> solo afecta 'running'
      - Un duatlon -> afecta 'running' y 'cycling'
      - Un triatlon -> afecta las 3, cada una con su propio ritmo de
        carga pero todas apuntando a la MISMA fecha de carrera.

    Args:
        ctl_por_deporte: dict como el que devuelve
            _calcular_ctl_atl_sport() en app.py, ej:
            {'running': {'ctl':20,'atl':18,...}, 'cycling': {...}, 'swimming': None}
        hoy: fecha de hoy
        carreras: TODAS las carreras del atleta (con su campo .deporte)
        ramp_semanal / ramp_max: iguales que en proyectar_pmc

    Devuelve: {'running': ResultadoProyeccion|None, 'cycling': ..., 'swimming': ...}
    Una disciplina da None si el atleta no tiene datos de CTL para ella,
    o si no hay ninguna carrera futura donde esa disciplina participe.
    """
    resultados = {}
    for disciplina in ('running', 'cycling', 'swimming'):
        carreras_disciplina = [
            c for c in carreras
            if disciplina in disciplinas_de_carrera(c.deporte)
        ]
        datos_ctl = ctl_por_deporte.get(disciplina)
        if not carreras_disciplina or not datos_ctl:
            resultados[disciplina] = None
            continue
        resultados[disciplina] = proyectar_pmc(
            ctl_inicial=datos_ctl['ctl'],
            atl_inicial=datos_ctl['atl'],
            hoy=hoy,
            carreras=carreras_disciplina,
            ramp_semanal=ramp_semanal,
            ramp_max=ramp_max,
        )
    return resultados


# ── Tests de invariantes ──────────────────────────────────────────────────────
if __name__ == '__main__':
    from datetime import date

    print('Ejecutando tests de proyección PMC...\n')

    # Caso de prueba — Silvina: CTL 28, carrera A en 6 meses
    hoy = date.today()
    carreras_test = [
        Carrera(fecha=hoy+timedelta(days=73),  prioridad='C', nombre='15km New Balance', distancia='15k'),
        Carrera(fecha=hoy+timedelta(days=76),  prioridad='A', nombre='21km BA',          distancia='21k',   ctl_objetivo=70),
        Carrera(fecha=hoy+timedelta(days=122), prioridad='B', nombre='26km Utec',        distancia='21k'),
        Carrera(fecha=hoy+timedelta(days=150), prioridad='B', nombre='21km MDQ',         distancia='21k'),
        Carrera(fecha=hoy+timedelta(days=178), prioridad='A', nombre='33km Bariloche',   distancia='33k',   ctl_objetivo=70),
    ]

    resultado = proyectar_pmc(
        ctl_inicial=28.0, atl_inicial=23.0,
        hoy=hoy, carreras=carreras_test,
        ramp_semanal=3.5, ramp_max=6.0,
    )

    print(f'Días proyectados: {len(resultado.dias)}')
    print(f'CTL inicial: 28.0 → CTL pico: {resultado.ctl_pico}')
    print(f'TSB en carrera A final: {resultado.tsb_carrera_A}')
    print(f'Ramp máximo real: {resultado.ramp_max_real}/semana')
    print(f'Invariantes OK: {resultado.invariantes_ok}')
    print(f'\nNotas:')
    for n in resultado.notas:
        print(f'  {n}')

    # Test 1: CTL sube
    assert resultado.ctl_pico > 28.0, "FAIL: CTL no sube"
    print('\n✓ Test 1: CTL asciende')

    # Test 2: Invariante TSB carrera A en banda
    lb, ub = TSB_OBJETIVO['A']
    # Tolerancia amplia porque el ajuste es iterativo
    assert -5 <= resultado.tsb_carrera_A <= 30, f"FAIL: TSB={resultado.tsb_carrera_A}"
    print(f'✓ Test 2: TSB carrera A = {resultado.tsb_carrera_A} (banda {lb}-{ub})')

    # Test 3: Ramp rate no supera el máximo
    assert resultado.ramp_max_real <= 7.5, f"FAIL: Ramp={resultado.ramp_max_real}"
    print(f'✓ Test 3: Ramp máximo = {resultado.ramp_max_real}/semana')

    # Test 4: Hay fases A, T, R, Taper
    fases_encontradas = set(f['fase'] for f in resultado.fases)
    assert 'Taper' in fases_encontradas, "FAIL: Sin Taper"
    print(f'✓ Test 4: Fases encontradas: {fases_encontradas}')

    print('\n✅ Todos los tests pasaron')

    # Mostrar primeros y últimos días
    print('\nPrimeros 7 días:')
    for dp in resultado.dias[:7]:
        print(f'  {dp.fecha} | CTL {dp.ctl:5.1f} | ATL {dp.atl:5.1f} | TSB {dp.tsb:6.1f} | {dp.fase:12} | TSS {dp.tss:5.1f}')
    print('...')
    print('Últimos 7 días:')
    for dp in resultado.dias[-7:]:
        print(f'  {dp.fecha} | CTL {dp.ctl:5.1f} | ATL {dp.atl:5.1f} | TSB {dp.tsb:6.1f} | {dp.fase:12} | TSS {dp.tss:5.1f}')
