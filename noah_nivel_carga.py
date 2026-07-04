"""
noah_nivel_carga.py — NOAH Nivel de Carga Diario
==================================================
Calcula el nivel de carga para una sesion especifica del dia.
Usa todos los biomarcadores disponibles + historial de feedback.

Niveles:
  ALTO     → atleta fresco, puede hacer el metodo mas exigente
  NORMAL   → puede entrenar bien, metodo estandar
  REDUCIDO → comprometido, volumen reducido, pausas mas largas
  MINIMO   → riesgo viral o muy comprometido, solo Z2/Z3

Uso desde patrones_sesion.py:
  from noah_nivel_carga import calcular_nivel_carga
  nivel = calcular_nivel_carga(conn, atleta_id, fecha, tsb, hrv_flag)
"""

import psycopg2
from datetime import date, timedelta
from pathlib import Path


def calcular_nivel_carga(conn, atleta_id: int, fecha: str = None,
                          tsb: float = None, hrv_flag: str = None) -> dict:
    """
    Calcula el nivel de carga para el dia dado.

    Args:
        conn:       conexion a la DB
        atleta_id:  ID del atleta
        fecha:      fecha del dia (default: hoy)
        tsb:        TSB calculado por ciclo_semanal (override si ya lo tiene)
        hrv_flag:   flag HRV calculado por ciclo_semanal (override)

    Returns:
        dict con:
          nivel:      'ALTO' | 'NORMAL' | 'REDUCIDO' | 'MINIMO'
          score:      0-100 (puntuacion interna)
          razon:      lista de strings explicando el nivel
          contexto:   dict con todos los valores usados
    """
    if fecha is None:
        fecha = str(date.today())

    razon = []
    score = 100  # Empezamos con score maximo y descontamos

    # ── 1. DATOS DE HRV Y BIOMARCADORES ──────────────────────────────────────
    ctx = _get_contexto_dia(conn, atleta_id, fecha)

    # Combinar con valores ya calculados por ciclo_semanal
    if tsb is not None:
        ctx['tsb'] = tsb
    if hrv_flag is not None:
        ctx['hrv_flag'] = hrv_flag

    # ── 2. RIESGO VIRAL — override inmediato ─────────────────────────────────
    if ctx.get('riesgo_viral') in ('alto', 'muy_alto'):
        return {
            'nivel': 'MINIMO',
            'score': 10,
            'razon': [f"Riesgo viral {ctx['riesgo_viral']} — solo Z1/Z2"],
            'contexto': ctx,
        }

    # ── 3. DIAS CONSECUTIVOS COMPROMETIDOS ───────────────────────────────────
    dias_comprometidos = _dias_hrv_comprometidos(conn, atleta_id, fecha)
    ctx['dias_hrv_comprometido'] = dias_comprometidos

    if dias_comprometidos >= 5:
        return {
            'nivel': 'MINIMO',
            'score': 15,
            'razon': [f'{dias_comprometidos} días seguidos con HRV comprometido'],
            'contexto': ctx,
        }

    if dias_comprometidos >= 3:
        score -= 40
        razon.append(f'{dias_comprometidos} días seguidos con HRV comprometido')

    # ── 4. HRV FLAG ──────────────────────────────────────────────────────────
    hrv_flag_val = ctx.get('hrv_flag', 'amarillo')
    if hrv_flag_val == 'rojo':
        score -= 35
        razon.append('HRV rojo')
    elif hrv_flag_val == 'amarillo':
        score -= 15
        razon.append('HRV amarillo')
    elif hrv_flag_val == 'verde':
        score += 5
        razon.append('HRV verde')

    # ── 5. HRV TENDENCIA (3d vs 7d) ──────────────────────────────────────────
    tendencia = ctx.get('hrv_tendencia', 'estable')
    if tendencia == 'empeorando':
        score -= 20
        razon.append('HRV empeorando (tendencia 3d < 7d)')
    elif tendencia == 'mejorando':
        score += 10
        razon.append('HRV mejorando')

    # ── 6. BODY BATTERY ──────────────────────────────────────────────────────
    bb = ctx.get('body_battery')
    if bb is not None:
        if bb < 25:
            score -= 35
            razon.append(f'Body Battery muy bajo ({bb})')
        elif bb < 45:
            score -= 20
            razon.append(f'Body Battery bajo ({bb})')
        elif bb >= 65:
            score += 10
            razon.append(f'Body Battery alto ({bb})')

    # ── 7. TSB (FRESCURA) ────────────────────────────────────────────────────
    tsb_val = ctx.get('tsb', 0)
    if tsb_val is not None:
        if tsb_val < -25:
            score -= 25
            razon.append(f'TSB muy negativo ({tsb_val:.1f}) — fatiga alta')
        elif tsb_val < -10:
            score -= 10
            razon.append(f'TSB negativo ({tsb_val:.1f})')
        elif tsb_val > 5:
            score += 10
            razon.append(f'TSB positivo ({tsb_val:.1f}) — fresco')

    # ── 8. HANNA PUEDE CARGAR ────────────────────────────────────────────────
    if ctx.get('hanna_puede_cargar') == 0:
        score -= 25
        razon.append('HANNA: no puede cargar')

    # ── 9. RIESGO VIRAL MEDIO ────────────────────────────────────────────────
    if ctx.get('riesgo_viral') == 'medio':
        score -= 20
        razon.append('Riesgo viral medio')

    # ── 10. FEEDBACK HISTORICO DEL ATLETA ────────────────────────────────────
    feedback_adj = _ajuste_por_feedback(conn, atleta_id)
    if feedback_adj != 0:
        score += feedback_adj
        if feedback_adj < 0:
            razon.append(f'Historial: patrón de sobrecarga reciente ({feedback_adj:+d} pts)')
        else:
            razon.append(f'Historial: buena absorción reciente ({feedback_adj:+d} pts)')

    # ── DETERMINAR NIVEL ─────────────────────────────────────────────────────
    score = max(0, min(100, score))

    if score >= 75:
        nivel = 'ALTO'
    elif score >= 50:
        nivel = 'NORMAL'
    elif score >= 25:
        nivel = 'REDUCIDO'
    else:
        nivel = 'MINIMO'

    ctx['score'] = score

    return {
        'nivel'   : nivel,
        'score'   : score,
        'razon'   : razon if razon else ['Sin factores de ajuste — nivel base'],
        'contexto': ctx,
    }


def _get_contexto_dia(conn, atleta_id: int, fecha: str) -> dict:
    """
    Lee todos los biomarcadores del dia desde sleep_hrv.
    También calcula la tendencia HRV 3d vs 7d.
    """
    ctx = {}

    # Datos del dia
    row = conn.execute("""
        SELECT hrv_rmssd, hrv_flag, hrv_baseline_7d, hrv_baseline_30d,
               body_battery, recovery_score, stress_avg,
               hanna_puede_cargar, riesgo_viral_nivel,
               modificador_carga, sleep_h, deep_h,
               hanna_semaforo, estado_autonomico
        FROM sleep_hrv
        WHERE atleta_id=%s AND fecha=%s
    """, (atleta_id, fecha)).fetchone()

    if row:
        ctx['hrv_rmssd']          = row[0]
        ctx['hrv_flag']           = row[1]
        ctx['hrv_baseline_7d']    = row[2]
        ctx['body_battery']       = row[4]
        ctx['recovery_score']     = row[5]
        ctx['hanna_puede_cargar'] = row[7]
        ctx['riesgo_viral']       = row[8]
        ctx['modificador_carga']  = row[9]
        ctx['sleep_h']            = row[10]
        ctx['hanna_semaforo']     = row[12]
    else:
        ctx['hrv_flag'] = 'amarillo'  # default conservador

    # Calcular tendencia HRV: promedio 3d vs promedio 7d
    try:
        fecha_dt  = date.fromisoformat(fecha)
        fecha_3d  = str(fecha_dt - timedelta(days=3))
        fecha_7d  = str(fecha_dt - timedelta(days=7))

        avg_3d = conn.execute("""
            SELECT AVG(hrv_rmssd) FROM sleep_hrv
            WHERE atleta_id=%s AND fecha > %s AND fecha <= %s AND hrv_rmssd IS NOT NULL
        """, (atleta_id, fecha_3d, fecha)).fetchone()[0]

        avg_7d = conn.execute("""
            SELECT AVG(hrv_rmssd) FROM sleep_hrv
            WHERE atleta_id=%s AND fecha > %s AND fecha <= %s AND hrv_rmssd IS NOT NULL
        """, (atleta_id, fecha_7d, fecha)).fetchone()[0]

        if avg_3d and avg_7d and avg_7d > 0:
            ratio = avg_3d / avg_7d
            if ratio >= 1.05:
                ctx['hrv_tendencia'] = 'mejorando'
            elif ratio <= 0.95:
                ctx['hrv_tendencia'] = 'empeorando'
            else:
                ctx['hrv_tendencia'] = 'estable'
            ctx['hrv_ratio_3d_7d'] = round(ratio, 3)
        else:
            ctx['hrv_tendencia'] = 'estable'
    except Exception:
        ctx['hrv_tendencia'] = 'estable'

    return ctx


def _dias_hrv_comprometidos(conn, atleta_id: int, fecha: str) -> int:
    """
    Cuenta cuántos días consecutivos anteriores tiene el atleta
    con hanna_puede_cargar=0 (HRV comprometido).
    """
    try:
        fecha_dt = date.fromisoformat(fecha)
        dias = 0
        for i in range(1, 15):  # máximo 14 días hacia atrás
            f = str(fecha_dt - timedelta(days=i))
            row = conn.execute(
                "SELECT hanna_puede_cargar FROM sleep_hrv WHERE atleta_id=%s AND fecha=%s",
                (atleta_id, f)
            ).fetchone()
            if row is None:
                break  # sin datos = paramos
            if row[0] == 0:
                dias += 1
            else:
                break  # día bueno = corta la racha
        return dias
    except Exception:
        return 0


def _ajuste_por_feedback(conn, atleta_id: int) -> int:
    """
    Ajusta el score según el historial de feedback reciente del atleta.
    Si viene de sobrecargas repetidas → baja el score (prescribir menos)
    Si viene de buena absorción → sube el score (puede más)

    Retorna un ajuste de -20 a +15
    """
    try:
        # Últimas 4 semanas — fecha calculada en Python (date('now','-N days')
        # de SQLite no existe en Postgres).
        fecha_lim = str(date.today() - timedelta(days=28))
        rows = conn.execute("""
            SELECT resultado, cumplimiento_tss, impacto_hrv
            FROM noah_feedback
            WHERE atleta_id=%s AND fecha >= %s
            ORDER BY fecha DESC
            LIMIT 10
        """, (atleta_id, fecha_lim)).fetchall()

        if not rows:
            return 0

        sobrecargas = sum(1 for r in rows if r[0] == 'sobrecarga')
        optimas     = sum(1 for r in rows if r[0] == 'optima')
        hrv_neg     = sum(1 for r in rows if r[2] is not None and r[2] < -3)

        # Patrón de sobrecarga con impacto HRV negativo → reducir
        if sobrecargas >= 2 and hrv_neg >= 2:
            return -20
        if sobrecargas >= 3:
            return -15

        # Sobrecarga pero HRV positivo → el atleta absorbe bien
        # (como Silvina: sobrecarga pero HRV +1.1)
        if sobrecargas >= 2 and hrv_neg == 0:
            return 5  # puede un poco más de lo planificado

        # Patrón óptimo consistente
        if optimas >= 3 and sobrecargas == 0:
            return 10

        return 0

    except Exception:
        return 0


def seleccionar_metodo_biblioteca(biblioteca: dict, deporte: str,
                                   tipo_sesion: str, nivel: str,
                                   fase: str) -> dict | None:
    """
    Selecciona el método óptimo de la biblioteca JSON según nivel y fase.

    Args:
        biblioteca:  dict cargado desde sesiones_biblioteca.json
        deporte:     'run' | 'bike' | 'swim'
        tipo_sesion: 'ftp' | 'vo2' | 'neuro' | 'long' | 'recuperacion'
        nivel:       'ALTO' | 'NORMAL' | 'REDUCIDO' | 'MINIMO'
        fase:        'A' | 'T' | 'R' | 'Taper'

    Returns:
        dict del método seleccionado o None si no hay disponible
    """
    try:
        cat = biblioteca.get(deporte, {}).get(tipo_sesion, {})
        reglas = cat.get('seleccion_automatica', [])
        metodos = {m['id']: m for m in cat.get('metodos', [])}

        for regla in reglas:
            condicion = regla.get('si', '')
            usar_id   = regla.get('usar')

            if usar_id is None:
                continue  # método nulo = no prescribir ese tipo hoy

            # Evaluar condición simple
            if _evaluar_condicion(condicion, nivel, fase):
                metodo = metodos.get(usar_id)
                if metodo and nivel in metodo.get('nivel_carga_requerido', []):
                    return metodo

        # Fallback: primer método que acepta el nivel
        for m in cat.get('metodos', []):
            if nivel in m.get('nivel_carga_requerido', []):
                return m

        return None

    except Exception:
        return None


def _evaluar_condicion(condicion: str, nivel: str, fase: str) -> bool:
    """
    Evalúa condiciones simples del tipo:
      'nivel=ALTO AND fase=T'
      'nivel=ALTO AND fase in [T,R]'
      'nivel=REDUCIDO OR nivel=MINIMO'
    """
    condicion = condicion.strip()
    if not condicion:
        return True

    # OR de alto nivel
    if ' OR ' in condicion:
        partes = condicion.split(' OR ')
        return any(_evaluar_condicion(p.strip(), nivel, fase) for p in partes)

    # AND de condiciones
    partes = condicion.split(' AND ')
    for parte in partes:
        parte = parte.strip()
        if parte.startswith('nivel='):
            val = parte.split('=')[1].strip()
            if nivel != val:
                return False
        elif parte.startswith('fase='):
            val = parte.split('=')[1].strip()
            if fase != val:
                return False
        elif 'fase in' in parte:
            # 'fase in [T,R]'
            vals = parte.split('[')[1].rstrip(']').split(',')
            vals = [v.strip() for v in vals]
            if fase not in vals:
                return False

    return True


def piso_techo_zona(hrv_flag: str, nivel: str) -> str:
    """
    Decide si trabajar en piso o techo de la zona según HRV y nivel.
    Piso = límite inferior de la zona (más suave, recuperación más rápida)
    Techo = límite superior (estímulo máximo dentro de la zona)
    """
    if hrv_flag == 'verde' and nivel == 'ALTO':
        return 'techo'
    elif hrv_flag == 'rojo' or nivel in ('REDUCIDO', 'MINIMO'):
        return 'piso'
    else:
        return 'piso'  # default conservador: piso


def verificar_vo2_permitido(semanas_a_carrera: float, deporte: str) -> bool:
    """
    Verifica si está permitido hacer VO2 según las semanas a la carrera A.
    Runners: detener 3 semanas antes.
    Ciclistas: detener 2 semanas antes.
    Nadadores: detener 1 semana antes.
    """
    TAPER_VO2 = {'running': 3, 'cycling': 2, 'swimming': 1, 'triatlon': 2}
    semanas_taper = TAPER_VO2.get(deporte, 3)
    return semanas_a_carrera > semanas_taper


def _get_reps(trabajo: dict, nivel: str) -> tuple:
    """Extrae reps_min y reps_max del trabajo según nivel."""
    reps_cfg = trabajo.get('reps', {})
    if isinstance(reps_cfg, dict):
        rango = reps_cfg.get(nivel, {})
        if isinstance(rango, dict):
            return rango.get('min', 1), rango.get('max', 1)
        return rango, rango
    return trabajo.get('reps_min', 1), trabajo.get('reps_max', 1)


def _get_dur_bloque(trabajo: dict, nivel: str) -> tuple:
    """Extrae dur_min y dur_max del bloque según nivel."""
    dur_cfg = trabajo.get('dur_bloque', {})
    if isinstance(dur_cfg, dict):
        rango = dur_cfg.get(nivel, {})
        if isinstance(rango, dict):
            return rango.get('min', 2), rango.get('max', 2)
        return rango, rango
    # Fallback: dur_bloque_min/max planos
    d = trabajo.get('dur_bloque_min', trabajo.get('dur_bloque_seg', 2))
    return d, trabajo.get('dur_bloque_max', d)


def _get_pausa_ratio(trabajo: dict, nivel: str) -> float:
    """Extrae el ratio de pausa según nivel."""
    cfg = trabajo.get('pausa_ratio', {})
    if isinstance(cfg, dict):
        val = cfg.get(nivel, 0.5)
        # Si es dict con min/max (pausa_ratio para VO2)
        if isinstance(val, dict):
            return (val.get('min', 0.5) + val.get('max', 0.5)) / 2
        return val
    return cfg or 0.5


def parametrizar_sesion(metodo: dict, nivel: str, tss_objetivo: float,
                         dur_max_min: float = None,
                         hrv_flag: str = 'amarillo') -> dict:
    """
    Dado un método de la biblioteca v3, calcula los parámetros exactos
    de la sesión según nivel de carga, TSS objetivo y HRV.

    Maneja:
    - Métodos fraccionados estándar (FTP, VO2)
    - Métodos con bloques alternados (over-under, long con Z3)
    - Métodos neuro integrados en Z2
    - Piso/techo de zona según HRV

    Retorna dict con todos los parámetros necesarios para generar la sesión.
    """
    estructura  = metodo.get('estructura', {})
    trabajo     = estructura.get('trabajo', {})
    pt          = piso_techo_zona(hrv_flag, nivel)

    resultado = {
        'nombre'             : metodo.get('nombre', ''),
        'biblioteca_id'      : metodo.get('id', ''),
        'nivel_usado'        : nivel,
        'piso_techo'         : pt,
        'hrv_flag'           : hrv_flag,
        'calentamiento_min'  : (estructura.get('calentamiento_min') or
                                estructura.get('calentamiento_z2_min') or
                                estructura.get('fondo_z2_inicial_min') or
                                estructura.get('calentamiento_tecnica_min') or 12),
        'enfriamiento_min'   : (estructura.get('enfriamiento_min') or
                                estructura.get('fondo_z2_post_min') or 8),
        'reps'               : 1,
        'dur_bloque_min'     : 0,
        'pausa_min'          : 0,
        'pausa_activa'       : trabajo.get('pausa_activa', True),
        'zona'               : trabajo.get('zona', 'Z4'),
        'dur_total_estimada' : 0,
        'descripcion_extra'  : '',
    }

    # ── Detectar tipo de método ───────────────────────────────────────────────
    metodo_id = metodo.get('id', '')

    # Método con bloques alternados (over-under, long con Z3)
    if trabajo.get('metodo') == 'alternancia_continua' or 'bloques_alternados' in estructura:
        resultado['tipo_estructura'] = 'alternancia'
        series = trabajo.get('series_max') or trabajo.get('series_min') or 4
        bajo_dur = trabajo.get('bajo_dur_min', 3)
        alto_dur = trabajo.get('alto_dur_min', 2)
        dur_por_serie = bajo_dur + alto_dur
        dur_trabajo = series * dur_por_serie
        pausa_series = trabajo.get('pausa_entre_series_min', 3)
        resultado['reps'] = series
        resultado['dur_bloque_min'] = dur_por_serie
        resultado['pausa_min'] = pausa_series
        resultado['descripcion_extra'] = f"{series}×({bajo_dur}' {trabajo.get('bajo_zona','Z3')} + {alto_dur}' {trabajo.get('alto_zona','Z4')})"

    # Método neuro en Z2 (aceleraciones integradas)
    elif 'neuro' in metodo_id or trabajo.get('intensidad_pct_vo2') == 110:
        resultado['tipo_estructura'] = 'neuro_en_z2'
        reps_min, reps_max = _get_reps(trabajo, nivel)
        dur_seg_cfg = trabajo.get('dur_bloque_seg', {})
        if isinstance(dur_seg_cfg, dict):
            rango = dur_seg_cfg.get(nivel, {})
            dur_seg = (rango.get('min', 30) + rango.get('max', 60)) / 2 if isinstance(rango, dict) else 45
        else:
            dur_seg = dur_seg_cfg or 45
        pausa_z2 = trabajo.get('pausa_z2_entre_reps_min', {})
        pausa_z2 = pausa_z2.get(nivel, 3) if isinstance(pausa_z2, dict) else pausa_z2 or 3
        reps = round((reps_min + reps_max) / 2)
        resultado['reps'] = reps
        resultado['dur_bloque_min'] = round(dur_seg / 60, 2)
        resultado['pausa_min'] = pausa_z2
        resultado['pausa_activa'] = True
        resultado['descripcion_extra'] = f"{reps}x{int(dur_seg)}seg al 110pct VO2 + {pausa_z2}min Z2"

    # Método estándar fraccionado (FTP, VO2, Neuro)
    else:
        resultado['tipo_estructura'] = 'fraccionado'
        reps_min, reps_max = _get_reps(trabajo, nivel)
        dur_min, dur_max   = _get_dur_bloque(trabajo, nivel)
        pausa_ratio        = _get_pausa_ratio(trabajo, nivel)

        reps       = round((reps_min + reps_max) / 2)
        dur_bloque = round((dur_min + dur_max) / 2, 1)
        pausa      = round(dur_bloque * pausa_ratio, 1)

        resultado['reps']           = reps
        resultado['dur_bloque_min'] = dur_bloque
        resultado['pausa_min']      = pausa
        resultado['descripcion_extra'] = f"{reps}×{dur_bloque}' {trabajo.get('zona','Z4')} + {pausa}' pausa"

    # ── Calcular duración total ───────────────────────────────────────────────
    dur_trabajo = resultado['reps'] * (resultado['dur_bloque_min'] + resultado['pausa_min']) - resultado['pausa_min']
    dur_total   = resultado['calentamiento_min'] + max(dur_trabajo, 0) + resultado['enfriamiento_min']

    # Respetar duración máxima del atleta
    if dur_max_min and dur_total > dur_max_min:
        factor = dur_max_min / dur_total
        resultado['reps'] = max(1, round(resultado['reps'] * factor))
        dur_trabajo = resultado['reps'] * (resultado['dur_bloque_min'] + resultado['pausa_min']) - resultado['pausa_min']
        dur_total   = resultado['calentamiento_min'] + max(dur_trabajo, 0) + resultado['enfriamiento_min']

    resultado['dur_total_estimada'] = round(dur_total)
    resultado['piso_techo_descripcion'] = f"Trabajar en {pt} de {trabajo.get('zona','Z4')}"

    return resultado




def calcular_ajuste_carga_semanal(conn, atleta_id: int,
                                   ctl: float = 0, tsb: float = 0,
                                   hrv_flag: str = 'amarillo') -> dict:
    """
    Calcula el factor de ajuste de carga para la próxima semana.
    Basado en la respuesta REAL del atleta — no en semanas fijas.

    Lee:
    - Feedback de las últimas 2 semanas (noah_feedback)
    - Tendencia HRV 7 días (sleep_hrv)
    - TSB actual (frescura)

    Retorna:
      factor:   0.75 a 1.05 (multiplica el TSS base)
      decision: 'aumentar' | 'mantener' | 'reducir' | 'recuperacion'
      razon:    lista de strings explicando la decisión
      tss_ajuste_pct: porcentaje de ajuste (-25% a +5%)
    """
    razon   = []
    score   = 0   # score acumulado: positivo = puede más, negativo = bajar carga

    # ── 1. FEEDBACK DE LAS ÚLTIMAS 2 SEMANAS ─────────────────────────────────
    try:
        # sqlite_master (SQLite) no existe en Postgres — el equivalente es
        # information_schema.tables.
        tbl = conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name='noah_feedback'"
        ).fetchone()

        if tbl:
            fecha_lim_14 = str(date.today() - timedelta(days=14))
            rows = conn.execute("""
                SELECT resultado, cumplimiento_tss, impacto_hrv, consistencia_series
                FROM noah_feedback
                WHERE atleta_id=%s AND fecha >= %s
                ORDER BY fecha DESC LIMIT 8
            """, (atleta_id, fecha_lim_14)).fetchall()

            if rows:
                n = len(rows)
                optimas      = sum(1 for r in rows if r[0] == 'optima')
                buenas       = sum(1 for r in rows if r[0] == 'buena')
                sobrecargas  = sum(1 for r in rows if r[0] == 'sobrecarga')
                incompletas  = sum(1 for r in rows if r[0] == 'incompleta')
                hrv_neg      = sum(1 for r in rows if r[2] is not None and r[2] < -3)
                hrv_pos      = sum(1 for r in rows if r[2] is not None and r[2] > 1)
                cumpl_avg    = sum(r[1] for r in rows if r[1]) / max(1, sum(1 for r in rows if r[1]))
                cons_avg     = sum(r[3] for r in rows if r[3]) / max(1, sum(1 for r in rows if r[3]))

                # Absorción óptima → puede más
                if optimas >= 2 and sobrecargas == 0 and hrv_neg == 0:
                    score += 2
                    razon.append(f'Buena absorción: {optimas} sesiones óptimas sin HRV negativo')

                # Sobrecarga + HRV positivo → puede más de lo planificado
                if sobrecargas >= 1 and hrv_neg == 0 and cumpl_avg > 1.10:
                    score += 1
                    razon.append(f'Sobrecarga bien absorbida (cumpl {cumpl_avg:.0%}, HRV positivo)')

                # Sobrecarga + HRV negativo → bajar
                if sobrecargas >= 1 and hrv_neg >= 1:
                    score -= 3
                    razon.append(f'Sobrecarga con impacto HRV negativo — reducir carga')

                # Incompletas → bajar
                if incompletas >= 2:
                    score -= 2
                    razon.append(f'{incompletas} sesiones incompletas — carga excesiva o disponibilidad')

                # Consistencia baja → mantener o bajar
                if cons_avg > 0 and cons_avg < 0.70:
                    score -= 2
                    razon.append(f'Consistencia baja en series ({cons_avg:.0%}) — no puede sostener la intensidad')
                elif cons_avg >= 0.85:
                    score += 1
                    razon.append(f'Alta consistencia en series ({cons_avg:.0%})')

    except Exception:
        pass  # Sin feedback = score 0

    # ── 2. TENDENCIA HRV 7 DÍAS ───────────────────────────────────────────────
    try:
        from datetime import date, timedelta
        hoy = date.today()

        avg_3d = conn.execute("""
            SELECT AVG(hrv_rmssd) FROM sleep_hrv
            WHERE atleta_id=%s AND fecha > %s AND hrv_rmssd IS NOT NULL
        """, (atleta_id, str(hoy - timedelta(days=3)))).fetchone()[0]

        avg_7d = conn.execute("""
            SELECT AVG(hrv_rmssd) FROM sleep_hrv
            WHERE atleta_id=%s AND fecha > %s AND hrv_rmssd IS NOT NULL
        """, (atleta_id, str(hoy - timedelta(days=7)))).fetchone()[0]

        if avg_3d and avg_7d and avg_7d > 0:
            ratio = avg_3d / avg_7d
            if ratio >= 1.08:
                score += 2
                razon.append(f'HRV mejorando (3d/7d = {ratio:.2f}) — recuperación activa')
            elif ratio <= 0.92:
                score -= 2
                razon.append(f'HRV empeorando (3d/7d = {ratio:.2f}) — acumulación de fatiga')
            else:
                razon.append(f'HRV estable (3d/7d = {ratio:.2f})')
    except Exception:
        pass

    # ── 3. HRV FLAG ACTUAL ───────────────────────────────────────────────────
    if hrv_flag == 'verde':
        score += 1
        razon.append('HRV verde hoy')
    elif hrv_flag == 'rojo':
        score -= 3
        razon.append('HRV rojo hoy — reducir carga esta semana')

    # ── 4. TSB (FRESCURA) ────────────────────────────────────────────────────
    if tsb is not None:
        if tsb > 5:
            score += 1
            razon.append(f'TSB positivo ({tsb:.1f}) — atleta fresco')
        elif tsb < -20:
            score -= 2
            razon.append(f'TSB muy negativo ({tsb:.1f}) — fatiga alta')
        elif tsb < -10:
            score -= 1
            razon.append(f'TSB negativo ({tsb:.1f})')

    # ── TRADUCIR SCORE A FACTOR ───────────────────────────────────────────────
    #
    # score >= 4  → absorbe muy bien → +5%
    # score 2-3   → absorbe bien     → +3%
    # score 0-1   → equilibrio       → mantener
    # score -1,-2 → señales mixtas   → -5%
    # score -3,-4 → fatiga moderada  → -10%
    # score <= -5 → fatiga alta      → semana recuperación (-20 a -25%)

    if score >= 4:
        factor    = 1.05
        decision  = 'aumentar'
        ajuste_pct = +5
    elif score >= 2:
        factor    = 1.03
        decision  = 'aumentar'
        ajuste_pct = +3
    elif score >= 0:
        factor    = 1.00
        decision  = 'mantener'
        ajuste_pct = 0
    elif score >= -2:
        factor    = 0.95
        decision  = 'reducir'
        ajuste_pct = -5
    elif score >= -4:
        factor    = 0.90
        decision  = 'reducir'
        ajuste_pct = -10
    else:
        factor    = 0.80
        decision  = 'recuperacion'
        ajuste_pct = -20

    if not razon:
        razon = ['Sin datos suficientes — manteniendo carga base']

    return {
        'factor'       : factor,
        'decision'     : decision,
        'ajuste_pct'   : ajuste_pct,
        'score'        : score,
        'razon'        : razon,
    }



def calcular_sesiones_semanales_optimas(conn, atleta_id: int, deporte: str,
                                          sesiones_objetivo_max: int = 9) -> dict:
    """
    Calcula cuántas sesiones por semana debe prescribir NOAH, basado en el
    CUMPLIMIENTO REAL del atleta — NO en CTL. El CTL es consecuencia de
    entrenar, no causa. Un atleta puede tener CTL bajo y cumplir perfecto
    las sesiones cortas que se le dan; otro puede tener CTL alto y faltar
    sistemáticamente.

    Lógica:
    1. Mirar cumplimiento real de las últimas 4-8 semanas (noah_feedback +
       conteo de sesiones reales en 'sesiones' vs prescriptas).
    2. Si cumple consistentemente (>=80% de las sesiones objetivo) → mantener
       el máximo de sesiones, ajustar solo volumen/TSS por sesión.
    3. Si cumple parcialmente (55-80%) durante 4+ semanas → reducir el número
       de sesiones al rango que sí viene completando, no agregar más carga
       de la que asimila.
    4. Si cumple poco (<55%) durante 8+ semanas → reducir más agresivamente.
    5. Sin historial suficiente → default conservador (mantener máximo,
       el coach ajusta manualmente con criterio).

    Retorna:
      n_sesiones: número de sesiones a generar esta semana
      decision: 'completo' | 'reducido' | 'minimo' | 'sin_datos'
      cumplimiento_pct: % de cumplimiento histórico calculado
      razon: explicación de la decisión
    """
    from datetime import date, timedelta

    razon = []

    try:
        # Contar sesiones reales completadas vs prescriptas en las últimas 8 semanas
        fecha_8sem = str(date.today() - timedelta(weeks=8))
        fecha_4sem = str(date.today() - timedelta(weeks=4))

        # Sesiones prescriptas por DÍA ÚNICO (no por fila — evita contar 10x
        # la misma sesión si el ciclo se corrió varias veces el mismo día,
        # como pasa durante testing/desarrollo).
        presc_rows = conn.execute("""
            SELECT DISTINCT pb.sesion_fecha, pb.sesion_sport
            FROM prescripcion_bloques pb
            JOIN prescripciones p ON p.id = pb.prescripcion_id
            WHERE pb.atleta_id=%s AND pb.bloque_num=1 AND pb.sesion_fecha >= %s
        """, (atleta_id, fecha_8sem)).fetchall()

        if not presc_rows or len(presc_rows) < 4:
            return {
                'n_sesiones': sesiones_objetivo_max,
                'decision': 'sin_datos',
                'cumplimiento_pct': None,
                'razon': ['Sin historial suficiente — manteniendo esquema completo. Ajustar manualmente si corresponde.']
            }

        total_prescriptas = len(presc_rows)

        # Sesiones reales completadas — contar por día único también, para
        # comparar manzanas con manzanas (días con sesión prescripta vs
        # días con actividad real, no número crudo de filas)
        real_rows = conn.execute("""
            SELECT COUNT(DISTINCT fecha) FROM sesiones
            WHERE atleta_id=%s AND fecha >= %s
        """, (atleta_id, fecha_8sem)).fetchone()

        total_reales = real_rows[0] if real_rows else 0

        cumplimiento_pct = round((total_reales / total_prescriptas) * 100, 1) if total_prescriptas > 0 else 0

        # Cumplimiento más reciente (últimas 4 semanas) — pesa más para detectar mejora/empeoramiento
        presc_4sem = conn.execute("""
            SELECT COUNT(DISTINCT pb.sesion_fecha) FROM prescripcion_bloques pb
            JOIN prescripciones p ON p.id = pb.prescripcion_id
            WHERE pb.atleta_id=%s AND pb.bloque_num=1 AND pb.sesion_fecha >= %s
        """, (atleta_id, fecha_4sem)).fetchone()[0]

        real_4sem = conn.execute("""
            SELECT COUNT(DISTINCT fecha) FROM sesiones
            WHERE atleta_id=%s AND fecha >= %s
        """, (atleta_id, fecha_4sem)).fetchone()[0]

        cumplimiento_4sem_pct = round((real_4sem / presc_4sem) * 100, 1) if presc_4sem > 0 else cumplimiento_pct

        # Decisión basada en cumplimiento reciente (más relevante) y el de 8 semanas (tendencia)
        if cumplimiento_4sem_pct >= 80:
            n_sesiones = sesiones_objetivo_max
            decision = 'completo'
            razon.append(f'Cumplimiento {cumplimiento_4sem_pct}% últimas 4 semanas — mantiene esquema completo, ajustar solo volumen.')

        elif cumplimiento_4sem_pct >= 55:
            # Reducir proporcionalmente al cumplimiento real, redondeando hacia arriba
            n_sesiones = max(5, round(sesiones_objetivo_max * (cumplimiento_4sem_pct / 100)))
            decision = 'reducido'
            razon.append(f'Cumplimiento {cumplimiento_4sem_pct}% (4 sem) / {cumplimiento_pct}% (8 sem) — reduciendo a {n_sesiones} sesiones, no agregar más carga de la que asimila.')

        else:
            # Cumplimiento bajo sostenido — verificar que sea consistente (8 semanas), no solo un bache puntual
            if cumplimiento_pct < 55:
                n_sesiones = max(3, round(sesiones_objetivo_max * 0.5))
                decision = 'minimo'
                razon.append(f'Cumplimiento bajo sostenido: {cumplimiento_4sem_pct}% (4 sem) y {cumplimiento_pct}% (8 sem) — reducción a {n_sesiones} sesiones. Revisar disponibilidad real o causa (lesión/enfermedad/carga laboral).')
            else:
                # Bache reciente pero buen historial de 8 semanas — no sobre-reaccionar
                n_sesiones = max(6, round(sesiones_objetivo_max * 0.75))
                decision = 'reducido'
                razon.append(f'Bache reciente ({cumplimiento_4sem_pct}% en 4 sem) pero historial de 8 sem ok ({cumplimiento_pct}%) — reducción moderada a {n_sesiones}, no agresiva.')

        return {
            'n_sesiones': n_sesiones,
            'decision': decision,
            'cumplimiento_pct': cumplimiento_4sem_pct,
            'cumplimiento_8sem_pct': cumplimiento_pct,
            'razon': razon,
        }

    except Exception as e:
        return {
            'n_sesiones': sesiones_objetivo_max,
            'decision': 'sin_datos',
            'cumplimiento_pct': None,
            'razon': [f'Error calculando cumplimiento ({e}) — manteniendo esquema completo por defecto.']
        }

if __name__ == '__main__':
    # Test rápido
    import json, os, sys
    import psycopg2.extras
    from pathlib import Path
    from db_compat import ConexionCompat

    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("Falta la variable de entorno DATABASE_URL (cadena de conexión a Postgres/Supabase)")
        sys.exit(1)
    conn = ConexionCompat(psycopg2.connect(db_url, cursor_factory=psycopg2.extras.DictCursor))

    print("Test calcular_nivel_carga para atleta 3 (Silvina):")
    resultado = calcular_nivel_carga(conn, atleta_id=3)
    print(f"  Nivel: {resultado['nivel']} (score={resultado['score']})")
    print(f"  Razones: {resultado['razon']}")
    print(f"  Contexto: {resultado['contexto']}")

    # Test selección de método
    bib_path = Path(__file__).parent / 'sesiones_biblioteca.json'
    if bib_path.exists():
        biblioteca = json.load(open(bib_path, encoding='utf-8'))
        nivel = resultado['nivel']
        metodo = seleccionar_metodo_biblioteca(biblioteca, 'run', 'ftp', nivel, 'A')
        if metodo:
            print(f"\n  Método seleccionado para run/ftp/fase A/{nivel}:")
            print(f"    {metodo['id']} — {metodo['nombre']}")
            params = parametrizar_sesion(metodo, nivel, tss_objetivo=55)
            print(f"    Params: {params}")

    conn.close()
