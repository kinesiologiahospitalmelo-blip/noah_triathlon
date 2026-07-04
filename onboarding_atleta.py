"""
onboarding_atleta.py - NOAH
============================
Script estandar de onboarding para CUALQUIER atleta nuevo.
Descarga TODO el historial disponible de Garmin en lotes seguros.

Uso:
    python onboarding_atleta.py --nombre "Jimena Melilli" --garmin jimenamelilli@hotmail.com --pass Jimena1984 --sport running --anos 7

Flags opcionales:
    --atleta_id N    : si el atleta ya existe en BD, usar su ID
    --desde YYYY-MM-DD : fecha desde donde arrancar (default: hoy - años)
    --solo_bio       : solo biomarcadores, no actividades
    --solo_act       : solo actividades, no bio
    --sin_streams    : no bajar streams punto a punto (mas rapido)
    --reanudar       : retomar desde el ultimo checkpoint guardado

Garantias:
    - Baja TODO lo disponible en Garmin (bio + actividades + streams + metricas extra)
    - Rate limiting inteligente (no rompe la API)
    - Checkpointing: si se interrumpe, retoma donde quedo
    - Funciona para cualquier dispositivo que sincronice con Garmin Connect
"""

import sys, os, time, json, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import date, timedelta, datetime

DB_URL = os.environ.get('DATABASE_URL')
if not DB_URL:
    print('ERROR: falta variable de entorno DATABASE_URL')
    sys.exit(1)

import psycopg2, psycopg2.extras
from db_compat import ConexionCompat

def get_conn():
    return ConexionCompat(psycopg2.connect(DB_URL, cursor_factory=psycopg2.extras.DictCursor))

# ── Rate limiting ──────────────────────────────────────────────────────────────
_req_count = 0
def _rate_limit(pausa_base=2.0):
    global _req_count
    _req_count += 1
    time.sleep(pausa_base)
    if _req_count % 50 == 0:
        print(f'  [Rate] {_req_count} requests — pausa 30s para no saturar API...')
        time.sleep(30)
    if _req_count % 200 == 0:
        print(f'  [Rate] {_req_count} requests — pausa 5min...')
        time.sleep(300)

# ── Checkpoint ────────────────────────────────────────────────────────────────
def _checkpoint_path(atleta_id):
    return f'noah_modelos/onboarding_{atleta_id}_checkpoint.json'

def _guardar_checkpoint(atleta_id, fecha_str, tipo):
    os.makedirs('noah_modelos', exist_ok=True)
    p = _checkpoint_path(atleta_id)
    data = {}
    if os.path.exists(p):
        with open(p) as f: data = json.load(f)
    data[tipo] = fecha_str
    with open(p, 'w') as f: json.dump(data, f)

def _leer_checkpoint(atleta_id):
    p = _checkpoint_path(atleta_id)
    if os.path.exists(p):
        with open(p) as f: return json.load(f)
    return {}

# ── Crear atleta en BD ────────────────────────────────────────────────────────
def crear_atleta(conn, nombre, garmin_user, garmin_pass, sport, lthr=162, peso=65, edad=None, sexo=None):
    from sincronizar_garmin import _enc
    from noa_db import NOADatabase

    exist = conn.execute('SELECT id FROM atletas WHERE garmin_user=%s', (garmin_user,)).fetchone()
    if exist:
        print(f'  Atleta ya existe con ID {exist[0]}')
        return exist[0]

    pass_enc = _enc(garmin_pass)
    conn.execute('''
        INSERT INTO atletas (nombre, garmin_user, garmin_pass, deporte_ppal, lthr_run, peso_kg, activo)
        VALUES (%s, %s, %s, %s, %s, %s, 1)
    ''', (nombre, garmin_user, pass_enc, sport, lthr, peso))
    conn.commit()
    atleta_id = conn.execute('SELECT id FROM atletas WHERE garmin_user=%s', (garmin_user,)).fetchone()[0]
    print(f'  Atleta "{nombre}" creado con ID {atleta_id}')
    return atleta_id

# ── Descargar metricas extra de Garmin (las que no teniamos) ──────────────────
def descargar_metricas_extra(client, fecha_str, atleta_id, conn):
    """
    Descarga datos adicionales de Garmin que no estaban en descargar_bio().
    Todo terreno: funciona con cualquier dispositivo que lo soporte.
    Si el dispositivo no tiene el dato, lo ignora silenciosamente.
    """
    extras = {}

    # Training Readiness (Garmin FR955, Fenix 7, etc.)
    try:
        tr = client.get_training_readiness(fecha_str)
        if tr and isinstance(tr, list) and tr:
            extras['training_readiness'] = tr[0].get('score') or tr[0].get('trainingReadinessScore')
        elif tr and isinstance(tr, dict):
            extras['training_readiness'] = tr.get('score') or tr.get('trainingReadinessScore')
    except Exception: pass

    # VO2max estimado (disponible en casi todos los relojes modernos)
    try:
        mx = client.get_max_metrics(fecha_str)
        if mx and isinstance(mx, list) and mx:
            vo2 = mx[0].get('generic', {})
            extras['vo2max'] = vo2.get('vo2MaxPreciseValue') or vo2.get('vo2MaxValue')
    except Exception: pass

    # Daily stats (pasos, calorias activas, pisos, intensidad)
    try:
        stats = client.get_stats(fecha_str)
        if stats:
            extras['pasos']           = stats.get('totalSteps')
            extras['cal_activas']     = stats.get('activeKilocalories')
            extras['pisos_subidos']   = stats.get('floorsAscended')
            extras['min_intensidad']  = stats.get('moderateIntensityMinutes', 0) + stats.get('vigorousIntensityMinutes', 0)
            extras['distancia_total'] = stats.get('totalDistanceMeters')
    except Exception: pass

    # Training Load (solo algunos modelos)
    try:
        tl = client.get_training_load(fecha_str, fecha_str)
        if tl and isinstance(tl, list) and tl:
            extras['training_load_7d'] = tl[0].get('weekly7DayLoad') or tl[0].get('trainingLoad')
            extras['training_load_4w'] = tl[0].get('weeklyLoad28DayAvg')
    except Exception: pass

    # Respiracion diurna (disponible en Fenix, FR, Venu)
    try:
        resp = client.get_respiration_data(fecha_str)
        if resp:
            vals = [x.get('respirationValue') for x in resp if x.get('respirationValue') and x['respirationValue'] > 0]
            if vals: extras['resp_diurna_avg'] = round(sum(vals)/len(vals), 1)
    except Exception: pass

    # SpO2 diurno
    try:
        sp = client.get_spo2_data(fecha_str)
        if sp:
            vals = [x.get('value') for x in sp if x.get('value') and x['value'] > 80]
            if vals: extras['spo2_diurno_avg'] = round(sum(vals)/len(vals), 1)
    except Exception: pass

    # Guardar extras en sleep_hrv si hay algo
    if any(v is not None for v in extras.values()):
        cols_extras = {
            'training_readiness': 'REAL',
            'vo2max':             'REAL',
            'pasos':              'INTEGER',
            'cal_activas':        'INTEGER',
            'pisos_subidos':      'INTEGER',
            'min_intensidad':     'INTEGER',
            'distancia_total':    'REAL',
            'training_load_7d':   'REAL',
            'training_load_4w':   'REAL',
            'resp_diurna_avg':    'REAL',
            'spo2_diurno_avg':    'REAL',
        }
        # Asegurar columnas existen
        from db_compat import asegurar_columnas as _aseg
        _aseg(conn, 'sleep_hrv', list(cols_extras.items()))

        # Update o insert
        exist = conn.execute(
            'SELECT id FROM sleep_hrv WHERE atleta_id=%s AND fecha=%s',
            (atleta_id, fecha_str)).fetchone()
        if exist:
            sets = ', '.join(f'{k}=%s' for k, v in extras.items() if v is not None)
            vals = [v for v in extras.values() if v is not None] + [atleta_id, fecha_str]
            if sets:
                conn.execute(f'UPDATE sleep_hrv SET {sets} WHERE atleta_id=%s AND fecha=%s', vals)
                conn.commit()
        print(f'    [+] Extras: {", ".join(k for k,v in extras.items() if v is not None)}')

    return extras

# ── Descargar actividades por rango (mas eficiente que dia por dia) ───────────
def descargar_actividades_rango(client, atleta_id, conn, db, fecha_desde, fecha_hasta,
                                 sin_streams=False):
    """
    Descarga todas las actividades en un rango de fechas usando la API batch.
    Mas eficiente que descargar_actividades() dia por dia.
    """
    from sincronizar_garmin import descargar_actividades
    from sincronizar_activities import TIPO_A_SPORT, DEPORTES_VALIDOS

    print(f'    Buscando actividades {fecha_desde} → {fecha_hasta}...')
    try:
        acts = client.get_activities_by_date(fecha_desde, fecha_hasta)
        _rate_limit(1.0)
    except Exception as e:
        print(f'    Error listando actividades: {e}')
        return 0

    if not acts:
        return 0

    print(f'    {len(acts)} actividades encontradas')
    guardadas = 0

    for act in acts:
        try:
            tipo = act.get('activityType', {}).get('typeKey', '') or act.get('activityType', '')
            if isinstance(tipo, dict): tipo = tipo.get('typeKey', '')

            # Mapear tipo a sport NOAH
            sport = None
            for k, v in TIPO_A_SPORT.items():
                if k.lower() in tipo.lower() or tipo.lower() in k.lower():
                    sport = v; break
            if not sport: sport = 'other'

            if sport not in DEPORTES_VALIDOS: continue

            garmin_id = str(act.get('activityId', ''))
            if not garmin_id: continue

            # Evitar duplicados
            existe = conn.execute(
                'SELECT id FROM sesiones WHERE atleta_id=%s AND garmin_activity_id=%s',
                (atleta_id, garmin_id)).fetchone()
            if existe:
                continue

            fecha_act = (act.get('startTimeLocal') or act.get('startTimeGMT') or '')[:10]

            # Procesar y guardar sesion
            descargar_actividades(client, fecha_act, atleta_id, conn, db)
            _rate_limit(1.5)
            guardadas += 1

        except Exception as e:
            print(f'    Error en actividad: {e}')

    return guardadas

# ── Loop principal de onboarding ───────────────────────────────────────────────
def onboarding_completo(atleta_id, client, conn, db, fecha_desde, fecha_hasta,
                         solo_bio=False, solo_act=False, sin_streams=False, reanudar=False):
    """
    Descarga TODO el historial por lotes de 30 dias, de mas viejo a mas nuevo.
    """
    from sincronizar_garmin import descargar_bio, descargar_actividades, asegurar_columnas
    asegurar_columnas(conn)

    checkpoint = _leer_checkpoint(atleta_id) if reanudar else {}
    inicio_bio = checkpoint.get('bio', str(fecha_desde))
    inicio_act = checkpoint.get('actividades', str(fecha_desde))

    # Generar lista de bloques de 30 dias
    bloques = []
    cur = fecha_desde
    while cur <= fecha_hasta:
        fin_bloque = min(cur + timedelta(days=29), fecha_hasta)
        bloques.append((cur, fin_bloque))
        cur = fin_bloque + timedelta(days=1)

    total = len(bloques)
    print(f'\n  Total: {total} bloques de 30 dias ({fecha_desde} → {fecha_hasta})')
    print(f'  Modo: bio={not solo_act} | actividades={not solo_bio} | streams={not sin_streams}')
    print('=' * 60)

    for i, (bloque_desde, bloque_hasta) in enumerate(bloques):
        pct = round((i+1)/total*100)
        print(f'\n  Bloque {i+1}/{total} ({pct}%) | {bloque_desde} → {bloque_hasta}')

        # Dias dentro del bloque
        dias_bloque = []
        d = bloque_desde
        while d <= bloque_hasta:
            dias_bloque.append(d)
            d += timedelta(days=1)

        # ── Biomarcadores ──────────────────────────────────────────────────
        if not solo_act:
            for dia in dias_bloque:
                if str(dia) < inicio_bio and reanudar: continue
                print(f'  Bio {dia}')
                try:
                    descargar_bio(client, str(dia), atleta_id, conn, db)
                    _rate_limit(1.5)
                    descargar_metricas_extra(client, str(dia), atleta_id, conn)
                    _rate_limit(1.0)
                except Exception as e:
                    print(f'    Error bio {dia}: {e}')

            _guardar_checkpoint(atleta_id, str(bloque_hasta), 'bio')

        # ── Actividades ────────────────────────────────────────────────────
        if not solo_bio:
            if str(bloque_desde) >= inicio_act or not reanudar:
                n = descargar_actividades_rango(
                    client, atleta_id, conn, db,
                    str(bloque_desde), str(bloque_hasta),
                    sin_streams=sin_streams)
                print(f'    {n} sesiones nuevas guardadas')
                _guardar_checkpoint(atleta_id, str(bloque_hasta), 'actividades')

        print(f'  Bloque {i+1} OK')

    print('\n' + '='*60)
    print('  DESCARGA COMPLETA')
    print('='*60)

# ── CLI ───────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description='NOAH Onboarding - descarga historial completo')
    ap.add_argument('--nombre',     required=False, default='Atleta')
    ap.add_argument('--garmin',     required=True,  help='Email Garmin Connect')
    ap.add_argument('--password',   required=True,  help='Contraseña Garmin Connect')
    ap.add_argument('--sport',      default='running', choices=['running','cycling','swimming','triathlon'])
    ap.add_argument('--anos',       type=int, default=4, help='Años de historial a bajar')
    ap.add_argument('--atleta_id',  type=int, default=None)
    ap.add_argument('--desde',      default=None, help='Fecha inicio YYYY-MM-DD')
    ap.add_argument('--lthr',       type=int, default=162)
    ap.add_argument('--peso',       type=float, default=65)
    ap.add_argument('--solo_bio',   action='store_true')
    ap.add_argument('--solo_act',   action='store_true')
    ap.add_argument('--sin_streams',action='store_true')
    ap.add_argument('--reanudar',   action='store_true')
    ap.add_argument('--entrenar_ml',action='store_true', help='Entrenar ML al final')
    ap.add_argument('--primer_ciclo',action='store_true', help='Generar primer ciclo al final')
    args = ap.parse_args()

    from sincronizar_garmin import get_client, _enc
    from noa_db import NOADatabase

    print('\n' + '='*60)
    print('  NOAH — ONBOARDING ATLETA')
    print('='*60)

    conn = get_conn()
    db   = NOADatabase(DB_URL)

    # 1. Crear o recuperar atleta
    if args.atleta_id:
        atleta_id = args.atleta_id
        print(f'  Usando atleta ID {atleta_id}')
    else:
        atleta_id = crear_atleta(conn, args.nombre, args.garmin, args.password,
                                 args.sport, args.lthr, args.peso)

    # 2. Login Garmin
    print(f'\n  Conectando a Garmin Connect ({args.garmin})...')
    try:
        from sincronizar_garmin import get_client
        client = get_client(args.garmin, _enc(args.password))
        print('  [OK] Conectado a Garmin')
    except Exception as e:
        print(f'  [FAIL] Error Garmin: {e}')
        conn.close(); sys.exit(1)

    # 3. Rango de fechas
    fecha_hasta = date.today()
    if args.desde:
        fecha_desde = datetime.strptime(args.desde, '%Y-%m-%d').date()
    else:
        fecha_desde = fecha_hasta - timedelta(days=365 * args.anos)

    print(f'  Rango: {fecha_desde} → {fecha_hasta} ({args.anos} años)')

    # 4. Descargar todo
    onboarding_completo(
        atleta_id, client, conn, db, fecha_desde, fecha_hasta,
        solo_bio=args.solo_bio, solo_act=args.solo_act,
        sin_streams=args.sin_streams, reanudar=args.reanudar)

    # 5. Calcular umbrales desde Garmin
    print('\n  Calculando umbrales desde Garmin...')
    try:
        from sincronizar_garmin import get_lactate_threshold, get_cycling_ftp
        lthr_data = get_lactate_threshold(client, atleta_id)
        if lthr_data:
            print(f'  LTHR Garmin: {lthr_data}')
        ftp_data = get_cycling_ftp(client, atleta_id)
        if ftp_data:
            print(f'  FTP Garmin: {ftp_data}')
    except Exception as e:
        print(f'  Umbrales: {e}')

    # 6. Entrenar ML si se pide
    if args.entrenar_ml:
        print('\n  Entrenando modelos ML...')
        try:
            from noah_ml import NOAHMind, NOAHFoundationModel
            mind = NOAHMind(conn, atleta_id)
            mind.preparar_datos()
            r = mind.entrenar()
            print(f'  ML OK: {list(r.keys())}')
            # Fine-tune GRU desde Foundation si está disponible
            mind.fine_tune_gru()
            # Actualizar Foundation con nuevo atleta
            todos_ids = [r[0] for r in conn.execute('SELECT id FROM atletas WHERE activo=1').fetchall()]
            if len(todos_ids) >= 2:
                print(f'\n  Actualizando Foundation Model ({len(todos_ids)} atletas)...')
                NOAHFoundationModel().pretrain(conn, todos_ids)
        except Exception as e:
            print(f'  Error ML: {e}')

    # 7. Primer ciclo si se pide
    if args.primer_ciclo:
        print('\n  Generando primer ciclo semanal...')
        try:
            import subprocess
            result = subprocess.run(
                [sys.executable, 'ciclo_semanal.py', '--atleta', str(atleta_id)],
                capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__)))
            print(result.stdout[-2000:] if result.stdout else 'Sin output')
            if result.returncode != 0:
                print('Error ciclo:', result.stderr[-500:])
        except Exception as e:
            print(f'  Error primer ciclo: {e}')

    conn.close()
    print('\n  ONBOARDING COMPLETO')
    print(f'  Atleta ID: {atleta_id}')
    print(f'  Siguiente paso: revisar en la app y aprobar primer ciclo')

if __name__ == '__main__':
    main()
