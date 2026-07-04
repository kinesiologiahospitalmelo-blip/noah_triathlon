"""
ciclo_semanal.py
----------------
Genera la prescripcion semanal de entrenamiento para un atleta.
Soporta: running, cycling, swimming y triatlon (multideporte).
USO:
  python ciclo_semanal.py
  python ciclo_semanal.py --atleta 2
"""
import sys, json, argparse
import psycopg2
from datetime import date, timedelta
from pathlib import Path
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))
from noa_db import NOADatabase
from noa_estados import detectar_estado, get_plan_semana, imprimir_estado
from db_compat import asegurar_columnas
try:
    from noah_ml import NOAHMind
    NOAH_ML_DISPONIBLE = True
except ImportError:
    NOAH_ML_DISPONIBLE = False
from patrones_sesion import (
    generar_semana_completa, generar_semana_triatleta,
    mostrar_prescripcion, mostrar_zonas_atleta, ZONAS
)

# ── Fases A/T/R/Taper (nomenclatura correcta) ────────────────
def calcular_fase(semanas_a_carrera, perfil):
    taper = perfil.get('taper_semanas', 2)
    f3    = perfil.get('f3_semanas', 4)
    f2    = perfil.get('f2_semanas', 6)
    if semanas_a_carrera <= taper:            return 'Taper'
    if semanas_a_carrera <= taper + f3:       return 'R'
    if semanas_a_carrera <= taper + f3 + f2:  return 'T'
    return 'A'

def zonas_fase(fase, perfil):
    return {
        'A'    : (perfil.get('f1_z12_pct', 80), perfil.get('f1_z34_pct', 15), perfil.get('f1_z56_pct', 5)),
        'T'    : (perfil.get('f2_z12_pct', 68), perfil.get('f2_z34_pct', 22), perfil.get('f2_z56_pct', 10)),
        'R'    : (perfil.get('f3_z12_pct', 65), perfil.get('f3_z34_pct', 30), perfil.get('f3_z56_pct', 5)),
        'Taper': (90, 10, 0),
    }.get(fase, (80, 15, 5))

# ── Guardar bloques ───────────────────────────────────────────
def guardar_bloques(conn, prescripcion_id, atleta_id, sesiones):
    conn.execute('DELETE FROM prescripcion_bloques WHERE prescripcion_id=%s', (prescripcion_id,))
    # PRAGMA table_info (SQLite) reemplazado por el helper compartido. Las
    # comillas dobles en los defaults TEXT ("running", "") tampoco son
    # válidas en Postgres como literal de string — se cambian a simples.
    asegurar_columnas(conn, 'prescripcion_bloques', [
        ('sport',              "TEXT DEFAULT 'running'"),
        ('sesion_sport',       "TEXT DEFAULT 'running'"),
        ('sesion_nombre',      "TEXT DEFAULT ''"),
        ('sesion_fecha',       "TEXT DEFAULT ''"),
        ('sesion_duracion',    'REAL DEFAULT 0'),
        ('sesion_tss',         'REAL DEFAULT 0'),
        ('sesion_descripcion', "TEXT DEFAULT ''"),  # descripción a nivel SESIÓN (incluye nutrición, nivel de carga, etc.)
        ('watts_min',          'INTEGER'),
        ('watts_max',          'INTEGER'),
    ])
    conn.commit()
    for ses_num, ses in enumerate(sesiones, start=1):
        ses_sport       = getattr(ses, 'sport', 'running')
        ses_nombre      = getattr(ses, 'nombre', '')
        ses_fecha       = str(ses.fecha) if hasattr(ses, 'fecha') and ses.fecha else ''
        ses_duracion    = ses.duracion_total() if hasattr(ses, 'duracion_total') else 0
        ses_tss         = getattr(ses, 'tss_estimado', 0)
        ses_descripcion = getattr(ses, 'descripcion', '') or ''
        for bloque_num, b in enumerate(ses.bloques, start=1):
            zona_nombre  = ZONAS.get(b.zona, {}).get('nombre', b.zona)
            bloque_sport = getattr(b, 'sport', ses_sport)
            conn.execute('''
                INSERT INTO prescripcion_bloques
                (prescripcion_id, atleta_id, sesion_num, bloque_num,
                 nombre, zona, zona_nombre,
                 duracion_min, repeticiones, pausa_min, pausa_activa,
                 hr_min, hr_max, pace_ref, descripcion,
                 sport, sesion_sport, sesion_nombre, sesion_fecha,
                 sesion_duracion, sesion_tss, sesion_descripcion, watts_min, watts_max)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ''', (
                prescripcion_id, atleta_id, ses_num, bloque_num,
                b.nombre, b.zona, zona_nombre,
                b.duracion_min, b.repeticiones,
                b.pausa_min, int(b.pausa_activa),
                b.hr_min, b.hr_max, b.pace_ref, b.descripcion,
                bloque_sport, ses_sport, ses_nombre, ses_fecha,
                ses_duracion, ses_tss, ses_descripcion,
                getattr(b, 'watts_min', None), getattr(b, 'watts_max', None),
            ))
    conn.commit()
    total = sum(len(s.bloques) for s in sesiones)
    print(f'  Bloques guardados: {total} ({len(sesiones)} sesiones)')

# ── Vista detallada ───────────────────────────────────────────
def mostrar_detallada(conn, prescripcion_id, sesiones):
    rows = conn.execute('''
        SELECT sesion_num, bloque_num, nombre, zona, zona_nombre,
               duracion_min, repeticiones, pausa_min, pausa_activa,
               hr_min, hr_max, pace_ref, descripcion
        FROM prescripcion_bloques
        WHERE prescripcion_id=%s
        ORDER BY sesion_num, bloque_num
    ''', (prescripcion_id,)).fetchall()
    ses_bloques = {}
    for r in rows:
        s = r[0]
        if s not in ses_bloques:
            ses_bloques[s] = []
        ses_bloques[s].append(r)
    sport_icon = {'running':'🏃','cycling':'🚴','swimming':'🏊'}
    DIA_SEMANA = ['LUN','MAR','MIÉ','JUE','VIE','SÁB','DOM']  # weekday(): 0=lunes
    print()
    print('=' * 62)
    print('  PRESCRIPCIÓN — SEMANA')
    print('=' * 62)
    # Pre-calcular cuántas sesiones hay por fecha, para poder etiquetar
    # AM/PM correctamente cuando hay 2 sesiones el mismo día (ej: triatleta MIÉ/VIE).
    conteo_por_fecha = {}
    for ses in sesiones:
        if hasattr(ses, 'fecha') and ses.fecha:
            fk = str(ses.fecha)
            conteo_por_fecha[fk] = conteo_por_fecha.get(fk, 0) + 1

    indice_en_fecha = {}
    for ses_num, ses in enumerate(sesiones, start=1):
        # Día de la semana calculado SIEMPRE desde la fecha real — nunca por
        # posición en un array fijo, que se rompe si el número de sesiones
        # cambia (ej: 7 en vez de 9 por ajuste de cumplimiento).
        if hasattr(ses, 'fecha') and ses.fecha:
            dia_base = DIA_SEMANA[ses.fecha.weekday()]
            fecha_key = str(ses.fecha)
        else:
            dia_base = f'Ses {ses_num}'
            fecha_key = None

        if fecha_key and conteo_por_fecha.get(fecha_key, 1) >= 2:
            indice_en_fecha[fecha_key] = indice_en_fecha.get(fecha_key, 0) + 1
            sufijo = 'AM' if indice_en_fecha[fecha_key] == 1 else 'PM'
            dia = f'{dia_base} {sufijo}'
        else:
            dia = dia_base

        icon = sport_icon.get(getattr(ses, 'sport', 'running'), '•')
        print(f'\n  {dia} {ses.fecha.strftime("%d/%m/%Y")} {icon}  {ses.nombre}')
        print(f'  {"─"*56}')
        for r in ses_bloques.get(ses_num, []):
            _, _, nombre, zona, zona_nombre, dur, reps, pausa, activa, hr_min, hr_max, pace, desc = r
            dur_str  = f'{int(dur*60)}"' if dur < 1 else f'{int(dur)}\''
            reps_str = f'{reps}×' if reps > 1 else ''
            hr_str   = f'  HR {hr_min}-{hr_max}' if hr_min else ''
            pace_str = ''
            if pace:
                pm = int(pace); ps = int((pace-pm)*60)
                pace_str = f'  ~{pm}:{ps:02d}/km'
            pausa_str = ''
            if reps > 1 and pausa:
                pd = f'{int(pausa*60)}"' if pausa < 1 else f'{int(pausa)}\''
                pausa_str = f'  / {pd} pausa {"activa" if activa else "pasiva"}'
            print(f'    {reps_str}{dur_str} {zona} — {zona_nombre}{hr_str}{pace_str}{pausa_str}')
        print(f'  {"─"*56}')
        print(f'  Total: {ses.duracion_total():.0f} min  TSS {ses.tss_estimado:.0f}')
        # Mostrar nutrición si la descripción de la sesión la incluye
        ses_desc = getattr(ses, 'descripcion', '') or ''
        if 'Nutrición:' in ses_desc:
            nutri_txt = ses_desc.split('Nutrición:', 1)[1].strip()
            print(f'  🍌 Nutrición: {nutri_txt}')
    print()
    print(f'  TOTAL: {sum(s.duracion_total() for s in sesiones):.0f} min  |  TSS {sum(s.tss_estimado for s in sesiones):.0f}')
    print('=' * 62)

# ── Pace Z2, FTP, CSS ─────────────────────────────────────────
def get_pace_z2(conn, atleta_id, lthr, perfil):
    pace_z2 = 5.55
    try:
        lthr_z2_min = round(lthr * 0.75)
        lthr_z2_max = round(lthr * 0.87)
        rp = conn.execute('''
            SELECT AVG(pace), COUNT(*) FROM laps
            WHERE atleta_id=%s AND hr_avg BETWEEN %s AND %s
            AND pace > 4.0 AND pace < 7.5 AND distance_km > 0.3
        ''', (atleta_id, lthr_z2_min, lthr_z2_max)).fetchone()
        if rp and rp[0] and rp[1] >= 5:
            pace_z2 = round(float(rp[0]), 2)
        else:
            rp = conn.execute('''
                SELECT AVG(pace), COUNT(*) FROM sesiones
                WHERE atleta_id=%s AND hr_avg BETWEEN %s AND %s
                AND pace > 4.5 AND pace < 7.5 AND duration_min > 30
                ORDER BY fecha DESC LIMIT 30
            ''', (atleta_id, lthr_z2_min, lthr_z2_max)).fetchone()
            if rp and rp[0] and rp[1] >= 3:
                pace_z2 = round(float(rp[0]), 2)
        pace_anterior = perfil.get('pace_z2_calculado')
        if pace_anterior:
            if abs(pace_z2 - pace_anterior) / pace_anterior * 100 <= 3:
                pace_z2 = pace_anterior
        perfil['pace_z2_calculado'] = pace_z2
        conn.execute('UPDATE perfiles_macro SET datos_json=%s WHERE atleta_id=%s AND activo=1',
                     (json.dumps(perfil), atleta_id))
        conn.commit()
    except Exception as e:
        print(f'  Pace Z2 error: {e}')
    print(f'  Pace Z2: {int(pace_z2)}:{int((pace_z2%1)*60):02d} min/km')
    return pace_z2

def get_ftp_bike(conn, atleta_id, atleta, perfil):
    ftp = perfil.get('ftp_bike') or atleta.get('ftp_bike')
    if ftp:
        return ftp
    lthr_bike = atleta.get('lthr_bike', 150)
    hr_max    = atleta.get('hr_max', 185)
    peso      = atleta.get('peso_kg', 75) or 75
    try:
        from noa_deportes import ZonasCycling
        zc  = ZonasCycling.desde_lthr(lthr_bike=lthr_bike, hr_max=hr_max, peso_kg=peso)
        ftp = zc.ftp
    except:
        ftp = round(lthr_bike * 1.8)
    print(f'  FTP bike: {ftp}W')
    return ftp

def get_css_swim(conn, atleta_id, perfil):
    css = perfil.get('css_100m')
    if css:
        return css
    try:
        row = conn.execute('SELECT css_100m FROM atletas WHERE id=%s', (atleta_id,)).fetchone()
        if row and row[0]:
            return float(row[0])
    except: pass
    return 1.75

# ── Main ──────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description='NOAH — Ciclo semanal')
    ap.add_argument('--atleta', default=1, type=int)
    ap.add_argument('--tss-manual', type=int, default=None)
    args = ap.parse_args()
    atleta_id = args.atleta

    print('=' * 60)
    print('  NOAH — CICLO SEMANAL')
    print('=' * 60)

    db     = NOADatabase()
    atleta = db.get_atleta(atleta_id)
    if not atleta:
        print(f'ERROR: Atleta {atleta_id} no encontrado')
        sys.exit(1)

    print(f'\nAtleta : {atleta["nombre"]}')
    deporte   = atleta.get('deporte_ppal', 'running')
    lthr      = atleta.get('lthr_run', 162)
    lthr_bike = atleta.get('lthr_bike', 150)
    hr_max    = atleta.get('hr_max', 190)
    print(f'Deporte : {deporte}')

    import os
    db_url = os.environ.get('DATABASE_URL', '')
    if not db_url:
        print('ERROR: Falta la variable de entorno DATABASE_URL (cadena de conexión a Postgres/Supabase)')
        sys.exit(1)
    conn = psycopg2.connect(db_url)
    from db_compat import ConexionCompat
    conn = ConexionCompat(conn)

    # ── Perfil macro ──────────────────────────────────────────
    row = conn.execute(
        'SELECT datos_json FROM perfiles_macro WHERE atleta_id=%s AND activo=1',
        (atleta_id,)).fetchone()
    if not row:
        print('ERROR: Sin perfil de macrociclo.')
        conn.close(); sys.exit(1)
    perfil = json.loads(row[0])

    # ── Estado actual ─────────────────────────────────────────
    resultado_ctl = db.actualizar_ctl_atl_tsb(atleta_id)
    estado   = db.get_estado_actual(atleta_id)
    ctl      = resultado_ctl.get('ctl') if resultado_ctl else estado.get('ctl') or 0.0
    atl      = resultado_ctl.get('atl') if resultado_ctl else estado.get('atl') or 0.0
    tsb      = resultado_ctl.get('tsb') if resultado_ctl else estado.get('tsb') or 0.0
    hrv_flag = estado.get('hrv_flag') or 'amarillo'
    sleep_h  = estado.get('sleep_h') or 7.0

    hrv_7d = conn.execute(
        'SELECT hrv_flag FROM sleep_hrv WHERE atleta_id=%s ORDER BY fecha DESC LIMIT 7',
        (atleta_id,)).fetchall()
    dias_rojo     = sum(1 for r in hrv_7d if r[0] == 'rojo')
    hrv_tendencia = ('mala' if dias_rojo >= perfil.get('dias_hrv_rojo_max', 3)
                     else 'precaucion' if dias_rojo >= 2
                     else 'buena')

    print(f'\n  CTL: {ctl:.1f}  ATL: {atl:.1f}  TSB: {tsb:.1f}')
    print(f'  HRV: [{hrv_flag}]  Sueño: {sleep_h}h  Tendencia 7d: {hrv_tendencia}')

    # ── Fase A/T/R/Taper ─────────────────────────────────────
    carrera           = date.fromisoformat(perfil['carrera_fecha'])
    hoy               = date.today()
    semanas_a_carrera = (carrera - hoy).days / 7
    fase              = calcular_fase(semanas_a_carrera, perfil)
    z12, z34, z56     = zonas_fase(fase, perfil)
    semana_macro      = max(1, perfil.get('f1_semanas', 11) - round(semanas_a_carrera) + 1)

    print(f'\n  Fase: {fase}  ({semanas_a_carrera:.1f} sem hasta {perfil.get("carrera_nombre","")})')
    print(f'  Semana {semana_macro}  |  Z1-Z2={z12}%  Z3-Z4={z34}%  Z5={z56}%')

    # ── Pace Z2 / FTP / CSS ───────────────────────────────────
    pace_z2 = get_pace_z2(conn, atleta_id, lthr, perfil)
    ftp     = None
    css     = None
    lthr_swim = round(lthr * 0.92)
    if deporte in ('triatlon', 'cycling'):
        ftp = get_ftp_bike(conn, atleta_id, atleta, perfil)
    if deporte in ('triatlon', 'swimming'):
        css       = get_css_swim(conn, atleta_id, perfil)
        lthr_swim = atleta.get('lthr_swim') or round(lthr * 0.92)

    # ── Fechas de la semana ───────────────────────────────────
    def prox(dow):
        """Retorna la fecha del próximo día dow (0=lun..6=dom).
        Si hoy ES ese día, empieza hoy (no salta a la semana siguiente)."""
        d = (dow - hoy.weekday()) % 7
        return hoy + timedelta(days=d)

    lun = prox(0)  # Este lunes (o hoy si hoy es lunes)

    # Triatleta: 9 sesiones fijas LUN→DOM
    fechas_9 = [
        lun,                         # LUN: Swim long
        lun + timedelta(days=1),     # MAR: Bike FTP
        lun + timedelta(days=2),     # MIÉ AM: Swim FTP
        lun + timedelta(days=2),     # MIÉ PM: Run VO2
        lun + timedelta(days=3),     # JUE: Bike neuro+regen
        lun + timedelta(days=4),     # VIE AM: Swim VO2
        lun + timedelta(days=4),     # VIE PM: Run FTP
        lun + timedelta(days=5),     # SÁB: Bike long
        lun + timedelta(days=6),     # DOM: Run long
    ]

    # Runner/ciclista/nadador: 3 fechas (LUN FTP / MIÉ VO2 / SÁB Long)
    fechas_run = [
        lun,                         # LUN: FTP/umbral
        lun + timedelta(days=2),     # MIÉ: VO2/calidad
        lun + timedelta(days=5),     # SÁB: Long (SIEMPRE)
    ]

    fechas_plan = fechas_9 if deporte == 'triatlon' else fechas_run

    # ── Receta del Optimizer ──────────────────────────────────
    # Si el coach aplicó una receta desde el tab Optimizer en los últimos 7 días,
    # se usa para dirigir el tipo de semana
    receta_optimizer = perfil.get('receta_optimizer')
    receta_fecha     = perfil.get('receta_fecha', '')
    # ── Disponibilidad del atleta ────────────────────────────
    disponibilidad = perfil.get('disponibilidad') or {}
    DISP_DEFAULTS = {
        'running' : {'sesMin':3,'sesMax':5,'durSem':60, 'durFin':120},
        'triatlon': {'sesMin':6,'sesMax':9,'durSem':90, 'durFin':300},
        'cycling' : {'sesMin':3,'sesMax':5,'durSem':90, 'durFin':300},
        'swimming': {'sesMin':3,'sesMax':5,'durSem':60, 'durFin':90 },
    }
    disp_def = DISP_DEFAULTS.get(deporte, DISP_DEFAULTS['running'])
    ses_min      = disponibilidad.get('sesiones_semana_min', disp_def['sesMin'])
    ses_max      = disponibilidad.get('sesiones_semana_max', disp_def['sesMax'])
    dur_max_sem  = disponibilidad.get('dur_max_semana_min',  disp_def['durSem'])
    dur_max_fin  = disponibilidad.get('dur_max_finde_min',   disp_def['durFin'])

    atleta_cfg = {
        'lthr'        : lthr,
        'pace_z2_real': pace_z2,
        'lthr_bike'   : lthr_bike,
        'ftp'         : ftp,
        'lthr_swim'   : lthr_swim,
        'css_100m'    : css or perfil.get('css_100m', 1.75),
        'deporte'     : deporte,
        'fase'        : fase,
        'hrv_flag'    : hrv_flag,
        'atl'         : atl,
        'tsb'         : tsb,
        'sleep_h'     : sleep_h or 7.0,
        'ctl_calculado': ctl,
        'atl_calculado': atl,
        'tsb_calculado': tsb,
        'atleta_id'   : atleta_id,
        'conn'        : conn,
        # Disponibilidad del atleta
        'ses_min'     : ses_min,
        'ses_max'     : ses_max,
        'dur_max_sem' : dur_max_sem,
        'dur_max_fin' : dur_max_fin,
    }

    if receta_optimizer and receta_fecha:
        try:
            dias_receta = (hoy - date.fromisoformat(receta_fecha)).days
            if dias_receta <= 7:
                atleta_cfg['receta_optimizer'] = receta_optimizer
                print(f'\n  [Optimizer] Receta activa: {receta_optimizer}')
            else:
                print(f'\n  [Optimizer] Receta expirada ({dias_receta}d) — lógica automática')
        except: pass

    # ── NOAH ML — TSS recomendado ─────────────────────────────
    tss_manual = args.tss_manual
    if NOAH_ML_DISPONIBLE and not tss_manual:
        try:
            mind = NOAHMind(conn, atleta_id)
            mind.preparar_datos()
            # Entrenar con timeout implícito — si sklearn tarda demasiado
            # o falla (datos insuficientes, cross_val error) se salta sin romper
            try:
                mind.entrenar()
                tss_rec = mind.tss_recomendado({
                    'ctl': ctl, 'atl': atl, 'tsb': tsb,
                    'hrv_ms': estado.get('hrv_ms'),
                    'sleep_h': sleep_h, 'tss_semana': 0,
                })
                tss_manual = tss_rec['tss_recomendado']
                print(f'  [ML] TSS recomendado: {tss_manual} — {tss_rec["explicacion"]}')
            except (Exception, KeyboardInterrupt, SystemExit):
                print('  [ML] Entrenamiento ML saltado — usando lógica CTL/TSB')
                tss_manual = None
        except Exception as e:
            print(f'  [ML] {e}')

    # ── Ajuste adaptativo de carga ────────────────────────────
    # NOAH evalúa la respuesta real del atleta y ajusta el TSS
    # No es progresión lineal — es adaptación basada en biomarcadores y feedback
    try:
        from noah_nivel_carga import calcular_ajuste_carga_semanal
        ajuste = calcular_ajuste_carga_semanal(
            conn, atleta_id,
            ctl=ctl, tsb=tsb, hrv_flag=hrv_flag
        )
        factor    = ajuste['factor']
        decision  = ajuste['decision']
        ajuste_pct = ajuste['ajuste_pct']

        print(f'\n  [NOAH Adaptativo] {decision.upper()} ({ajuste_pct:+d}%) — score={ajuste["score"]}')
        for r in ajuste['razon']:
            print(f'    → {r}')

        # Aplicar el factor al TSS recomendado por ML (o al base de CTL)
        if tss_manual:
            tss_ajustado = round(tss_manual * factor)
            if tss_ajustado != tss_manual:
                print(f'  [NOAH Adaptativo] TSS {tss_manual} → {tss_ajustado} ({ajuste_pct:+d}%)')
            tss_manual = tss_ajustado

    except Exception as e:
        pass  # Silencioso — no rompe el ciclo si falla

    # ── Generar sesiones ──────────────────────────────────────
    sesiones, estado_atleta, tipo_plan = get_plan_semana(
        conn, atleta, atleta_cfg, perfil,
        fechas=fechas_plan, tss_manual=tss_manual,
        ctl_override=ctl, atl_override=atl, tsb_override=tsb,
    )
    imprimir_estado(estado_atleta)
    print(f'  Tipo plan: {tipo_plan}')

    # ── Guardar prescripción ──────────────────────────────────
    semana_id = f"{hoy.year}-W{hoy.isocalendar()[1]:02d}"
    n_ses     = len(sesiones)
    ses_datos = {}
    for i, s in enumerate(sesiones, start=1):
        b1 = s.bloques[1] if len(s.bloques) > 1 else s.bloques[0]
        ses_datos[f'ses{i}_fecha']    = str(s.fecha)
        ses_datos[f'ses{i}_tipo']     = s.nombre
        ses_datos[f'ses{i}_sport']    = getattr(s, 'sport', 'running')
        ses_datos[f'ses{i}_duracion'] = s.duracion_total()
        ses_datos[f'ses{i}_tss']      = s.tss_estimado

    presc_datos = {
        'fase': fase,  # ya en nomenclatura A/T/R/Taper
        **ses_datos,
        'tss_semana_total': sum(s.tss_estimado for s in sesiones),
    }
    presc_id = db.guardar_prescripcion(atleta_id, semana_id, presc_datos)
    guardar_bloques(conn, presc_id, atleta_id, sesiones)
    mostrar_detallada(conn, presc_id, sesiones)
    mostrar_zonas_atleta(atleta.get('nombre',''), lthr=lthr, hr_max=hr_max, pace_z2_real=pace_z2)

    conn.close()
    print(f'\n  Prescripción guardada — ID: {presc_id}  Semana: {semana_id}')

    # ── Matching automático: unir sesiones reales con prescripciones ─────────
    try:
        from noah_matching import get_conn as match_conn, migrar_tabla_feedback, matching_atleta
        c2 = match_conn()
        migrar_tabla_feedback(c2)
        n = matching_atleta(c2, atleta_id, dias=60, verbose=False)
        if n > 0:
            print(f'  [Feedback] {n} sesion(es) matcheadas con historial real')
        c2.close()
    except Exception as e:
        pass  # El matching es opcional — no rompe el ciclo si falla

    print('=' * 60)

if __name__ == '__main__':
    main()
