"""
noah_watch.py — API para el reloj Garmin (app NoahWatch).

Endpoints:
  POST   /api/watch/token          (sesión de login normal) crea el token del reloj (se muestra UNA vez)
  DELETE /api/watch/token          (sesión de login normal) revoca el token del reloj
  GET    /api/watch/summary        (token de reloj) readiness: Hanna Life, viral, ACWR, lesión
  GET    /api/watch/athlete_model  (token de reloj) parámetros del modelo de energía por atleta

Integración en app.py (después de definir ok, error, get_conn, etc.):

    from noah_watch import register_watch
    register_watch(app, dict(
        get_conn=get_conn, ok=ok, error=error,
        calcular_cs_dprime=_calcular_cs_dprime,
        sesion_de_token=_sesion_de_token, token_de_request=_token_de_request,
        limpiar_nan=_limpiar_nan,
    ))

El token del reloj es DISTINTO del token de sesión: solo sirve para /api/watch/*,
se guarda hasheado, es revocable y no expira hasta que se revoque.
"""
import hashlib
import math
import secrets
from datetime import datetime, date, timedelta
from functools import wraps

from flask import request, g

# ── Constantes del modelo (copiadas de get_dbal_running / get_torque_wbal) ──
# Si cambiás las fórmulas en app.py, cambialas acá también (el reloj las recibe de acá).
GLYC_FRAC = 0.55
RUN_GLYC_RATES = [  # (ratio_hasta, g/min) — ratio = velocidad/umbral (o FC/LTHR)
    (0.70, 1.0), (0.82, 1.5), (0.94, 2.5), (1.00, 3.0), (1.06, 3.5), (None, 4.0),
]
IF_FALLBACK = 0.80   # intensidad usada cuando no hay velocidad ni FC válidas
D_PRIME_RUN_DEFAULT = 150.0
W_PRIME_DEFAULT = 20000.0
CAD_OPT_DEFAULT = 85.0
FTP_DEFAULT = 200.0
STALE_HINT_MIN = 360


# ── Zonas de Noah para el reloj ────────────────────────────────────────────
# Usa las MISMAS clases que la web (noa_deportes.ZonasRunning / ZonasCycling), así que
# las zonas del reloj siempre coinciden con las de la app y cambian solas cuando el atleta
# mejora (LTHR, ritmo umbral, FTP). Cada lista son LÍMITES ordenados de menor a mayor
# intensidad: N zonas → N+1 valores (igual que UserProfile.getHeartRateZones de Garmin).
#   run.hr    : bpm            (6 zonas → 7 valores)
#   run.pace  : segundos/km    (del más lento al más rápido; menor número = más rápido)
#   bike.power: watts          (7 zonas → 8 valores; el último es un tope para dibujar Z7)
def zonas_para_reloj(lthr_run, hr_max, pace_umbral, peso, ftp, lthr_bike):
    from noa_deportes import ZonasRunning, ZonasCycling
    out = {}
    try:
        zr = ZonasRunning(lthr=lthr_run, hr_max=hr_max, pace_umbral=pace_umbral, peso_kg=peso)
        z = zr.calcular()
        defs = ZonasRunning.DEFINICIONES
        codes = [d[0] for d in defs]
        hr = [z[codes[0]]['hr_min']] + [z[c]['hr_max'] for c in codes]
        if hr_max and hr[-1] > hr_max:               # Z6 llega a 130 % LTHR: se topa en la FC máxima
            hr[-1] = max(int(hr_max), hr[-2] + 1)
        pcts = [d[2] for d in defs] + [defs[-1][3]]
        pace = [int(round(zr._pace_en_pct(p) * 60)) for p in pcts]
        out['run'] = {'hr': hr, 'pace': pace}
    except Exception:
        out['run'] = None
    try:
        zc = ZonasCycling(ftp=ftp, lthr_bike=lthr_bike, hr_max=hr_max or 185, peso_kg=peso)
        z = zc.calcular()
        codes = [d[0] for d in ZonasCycling.DEFINICIONES]
        power = [z[c]['w_min'] for c in codes] + [int(round(zc.ftp * 2.0))]
        out['bike'] = {'power': power, 'ftp': zc.ftp}
    except Exception:
        out['bike'] = None
    return out


# Misma regla que /api/atletas/<id>/zonas/<deporte> en app.py (según TSB).
# max_zona = zona más alta que Noah recomienda hoy.
def rec_zonas(tsb):
    if tsb is None:
        return None, None
    if tsb > 10:
        return 'optimo', 7
    if tsb >= -10:
        return 'normal', 7
    if tsb >= -20:
        return 'carga', 4
    return 'fatiga', 3


def register_watch(app, deps):
    get_conn = deps['get_conn']
    ok = deps['ok']
    error = deps['error']
    calc_cs = deps['calcular_cs_dprime']
    sesion_de_token = deps['sesion_de_token']
    token_de_request = deps['token_de_request']
    limpiar_nan = deps.get('limpiar_nan', lambda x: x)

    # ── tabla ──────────────────────────────────────────────────────────────
    def _init_watch_table():
        conn = get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS watch_tokens (
                token_hash TEXT PRIMARY KEY,
                atleta_id  INTEGER NOT NULL,
                creado     TEXT NOT NULL,
                ultimo_uso TEXT,
                revocado   INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()

    def _hash(token):
        return hashlib.sha256(token.encode('utf-8')).hexdigest()

    def requiere_watch(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            auth = request.headers.get('Authorization', '')
            token = auth[7:] if auth.startswith('Bearer ') else None
            if not token:
                return error('Token de reloj requerido', 401)
            _init_watch_table()
            conn = get_conn()
            try:
                row = conn.execute(
                    "SELECT atleta_id FROM watch_tokens WHERE token_hash=%s AND revocado=0",
                    (_hash(token),)
                ).fetchone()
                if not row:
                    return error('Token de reloj inválido o revocado', 401)
                conn.execute("UPDATE watch_tokens SET ultimo_uso=%s WHERE token_hash=%s",
                             (datetime.utcnow().isoformat(), _hash(token)))
                conn.commit()
            finally:
                conn.close()
            g.watch_atleta_id = int(row[0])
            return f(*args, **kwargs)
        return wrapper

    # ── token del reloj ────────────────────────────────────────────────────
    @app.route('/api/watch/token', methods=['POST'])
    def watch_crear_token():
        sesion = sesion_de_token(token_de_request())
        if sesion is None:
            return error('No autenticado o sesión expirada', 401)
        if sesion['rol'] == 'coach':
            atleta_id = (request.get_json(silent=True) or {}).get('atleta_id')
            if not atleta_id:
                return error('El coach debe indicar atleta_id')
        else:
            atleta_id = sesion['atleta_id']
        _init_watch_table()
        token = 'nw_' + secrets.token_urlsafe(32)
        conn = get_conn()
        try:
            conn.execute("UPDATE watch_tokens SET revocado=1 WHERE atleta_id=%s", (int(atleta_id),))
            conn.execute(
                "INSERT INTO watch_tokens (token_hash, atleta_id, creado) VALUES (%s,%s,%s)",
                (_hash(token), int(atleta_id), datetime.utcnow().isoformat()))
            conn.commit()
        finally:
            conn.close()
        # Se muestra una sola vez: en la web, mostrarlo + botón copiar (y/o QR).
        return ok({'token': token, 'atleta_id': int(atleta_id)})

    @app.route('/api/watch/token', methods=['DELETE'])
    def watch_revocar_token():
        sesion = sesion_de_token(token_de_request())
        if sesion is None:
            return error('No autenticado o sesión expirada', 401)
        if sesion['rol'] == 'coach':
            atleta_id = request.args.get('atleta_id')
            if not atleta_id:
                return error('El coach debe indicar atleta_id')
        else:
            atleta_id = sesion['atleta_id']
        _init_watch_table()
        conn = get_conn()
        try:
            conn.execute("UPDATE watch_tokens SET revocado=1 WHERE atleta_id=%s", (int(atleta_id),))
            conn.commit()
        finally:
            conn.close()
        return ok({'mensaje': 'token de reloj revocado'})

    # ── helpers de datos ───────────────────────────────────────────────────
    def _pick(d, *names):
        """Busca la primera clave existente (también un nivel adentro) — defensivo
        porque noah_riesgo_lesion.py no estaba en el material recibido."""
        if not isinstance(d, dict):
            return None
        for n in names:
            if n in d and d[n] is not None:
                v = d[n]
                if isinstance(v, dict):
                    for sub in ('valor', 'value', 'acwr', 'nivel', 'label'):
                        if sub in v and v[sub] is not None:
                            return v[sub]
                return v
        return None

    def _color_hanna(valor):
        # Mismos cortes que usaba el widget: <45 rojo, <70 amarillo, resto verde.
        if valor is None:
            return None
        return 'EF4444' if valor < 45 else ('F59E0B' if valor < 70 else '22C55E')

    def _acwr_directo(conn, atleta_id):
        """Mismo cálculo que el histórico de /riesgo_lesion (7d/28d), solo para hoy."""
        hoy = date.today()
        rows = conn.execute(
            "SELECT fecha, SUM(tss_total) FROM sesiones "
            "WHERE atleta_id=%s AND fecha > %s AND fecha <= %s GROUP BY fecha",
            (atleta_id, str(hoy - timedelta(days=28)), str(hoy))).fetchall()
        def _d(f):
            return f if isinstance(f, date) else date.fromisoformat(str(f)[:10])
        tss = {_d(r[0]): (r[1] or 0) for r in rows}
        aguda = sum(v for f, v in tss.items() if hoy - timedelta(days=7) < f <= hoy) / 7
        cronica = sum(tss.values()) / 28
        if len(tss) < 7 or cronica == 0:
            return None
        return round(aguda / cronica, 2)

    def _readiness(conn, atleta_id, fecha, modo):
        """Misma lógica que dbal_running (modo='run') y dbal_swimming (modo='swim')."""
        hl = conn.execute(
            "SELECT hanna_life FROM sleep_hrv WHERE atleta_id=%s AND fecha::date=%s::date",
            (atleta_id, fecha)).fetchone()
        hanna_hoy = float(hl[0]) if hl and hl[0] else None
        bl = conn.execute(
            "SELECT AVG(hanna_life), STDDEV(hanna_life) FROM sleep_hrv "
            "WHERE atleta_id=%s AND hanna_life IS NOT NULL "
            "AND fecha::date >= (%s::date - INTERVAL '21 days') AND fecha::date < %s::date",
            (atleta_id, fecha, fecha)).fetchone()
        r_norm = 1.0
        if bl and bl[0] and bl[1] and float(bl[1]) > 0:
            z = (hanna_hoy - float(bl[0])) / float(bl[1]) if hanna_hoy else 0
            r_norm = 0.70 + 0.30 * (1.0 / (1.0 + math.exp(-z)))
        elif hanna_hoy is not None:
            if modo == 'run':
                r_norm = min(1.0, max(0.2, hanna_hoy / 100.0))
            else:
                r_norm = min(1.0, 0.70 + 0.30 * (hanna_hoy / 100.0))
        return r_norm

    # ── GET /api/watch/summary ─────────────────────────────────────────────
    @app.route('/api/watch/summary', methods=['GET'])
    @requiere_watch
    def watch_summary():
        atleta_id = g.watch_atleta_id
        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT fecha, hanna_life, hanna_nivel, riesgo_viral, riesgo_viral_nivel "
                "FROM sleep_hrv WHERE atleta_id=%s AND hanna_life IS NOT NULL "
                "ORDER BY fecha DESC LIMIT 1", (atleta_id,)).fetchone()
            hanna = float(row[1]) if row and row[1] is not None else None

            lesion_raw = None
            try:
                from noah_riesgo_lesion import resumen_riesgo_lesion
                lesion_raw = resumen_riesgo_lesion(conn, atleta_id, None)
            except Exception:
                lesion_raw = None

            acwr = _pick(lesion_raw, 'acwr', 'acwr_valor')
            if acwr is None:
                try:
                    acwr = _acwr_directo(conn, atleta_id)
                except Exception:
                    acwr = None
            injury = _pick(lesion_raw, 'nivel', 'riesgo_nivel', 'riesgo', 'nivel_riesgo', 'injury_risk')

            # Banda "tipo HRV": promedio y desvío de Hanna Life de los 21 días previos
            # (misma ventana que usa readiness en dbal_running).
            baseline = sd = None
            if row:
                bl = conn.execute(
                    "SELECT AVG(hanna_life), STDDEV(hanna_life) FROM sleep_hrv "
                    "WHERE atleta_id=%s AND hanna_life IS NOT NULL "
                    "AND fecha::date >= (%s::date - INTERVAL '21 days') AND fecha::date < %s::date",
                    (atleta_id, str(row[0])[:10], str(row[0])[:10])).fetchone()
                if bl and bl[0] is not None:
                    baseline = round(float(bl[0]), 1)
                    sd = round(float(bl[1]), 1) if bl[1] is not None else None

            # Recomendación de zonas de Noah (por TSB). Si no se puede calcular, queda en None.
            rec_nivel = rec_max = None
            try:
                from noa_pmf import calcular_ctl_atl_tsb_atleta
                estado = calcular_ctl_atl_tsb_atleta(conn, atleta_id)
                rec_nivel, rec_max = rec_zonas(float(estado.get('tsb', 0)))
            except Exception:
                rec_nivel = rec_max = None

            out = {
                'rec_nivel': rec_nivel,
                'rec_max_zona': rec_max,
                'hanna_baseline': baseline,
                'hanna_sd': sd,
                'fecha': str(row[0])[:10] if row else None,
                'hanna_life': round(hanna) if hanna is not None else None,
                'hanna_nivel': row[2] if row else None,
                'hanna_color': _color_hanna(hanna),
                'viral_risk': (row[4] or (row[3] if row else None)) if row else None,
                'acwr': acwr,
                'injury_risk': injury,
                # TODO: no tengo de dónde sale la "recomendación" del día en NOAH.
                'recommendation': None,
                'server_time': int(datetime.utcnow().timestamp()),
            }
            if request.args.get('debug') == '1':
                out['_debug'] = {'lesion_raw': lesion_raw, 'viral_cols': [row[3], row[4]] if row else None}
            return ok(limpiar_nan(out))
        except Exception as e:
            return error(str(e))
        finally:
            conn.close()

    # ── GET /api/watch/athlete_model ───────────────────────────────────────
    @app.route('/api/watch/athlete_model', methods=['GET'])
    @requiere_watch
    def watch_athlete_model():
        atleta_id = g.watch_atleta_id
        fecha = request.args.get('fecha') or str(date.today())
        conn = get_conn()
        try:
            at = conn.execute(
                "SELECT pace_umbral_run, lthr_run, peso_kg, css_100m, ftp_watts, w_prime, cadencia_optima "
                "FROM atletas WHERE id=%s", (atleta_id,)).fetchone()
            if not at:
                return error('Atleta no encontrado', 404)
            pace_umbral, lthr_run, peso, css, ftp, w_prime, cad_opt = at
            peso = float(peso) if peso else 70.0

            cs = None
            try:
                cs = calc_cs(conn, atleta_id)
            except Exception:
                cs = None

            # ── RUN (idéntico a get_dbal_running) ──
            if not pace_umbral and cs:
                pace_umbral = cs.get('cs_pace_min_km')
            run = {'disponible': False}
            if pace_umbral and float(pace_umbral) > 0:
                d_prime = D_PRIME_RUN_DEFAULT
                if cs and cs.get('d_prime_m', 0) > 10:
                    d_prime = cs['d_prime_m']
                run = {
                    'disponible': True,
                    'umbral_speed': 1000.0 / (float(pace_umbral) * 60),   # m/s
                    'umbral_pace_min_km': float(pace_umbral),
                    'd_prime': float(d_prime),
                    'lthr': float(lthr_run) if lthr_run else None,
                    'glyc_total_g': peso * 7.0,
                    'readiness': _readiness(conn, atleta_id, fecha, 'run'),
                }

            # ── BIKE (idéntico a get_torque_wbal) ──
            ftp_f = float(ftp or FTP_DEFAULT)
            bike = {
                'disponible': True,
                'ftp': ftp_f,
                'cp': ftp_f * 0.97,
                'w_prime': float(w_prime or W_PRIME_DEFAULT),
                'cad_opt': float(cad_opt or CAD_OPT_DEFAULT),
            }

            # ── SWIM (parámetros de get_dbal_swimming; el reloj aún no lo corre en vivo) ──
            swim = {'disponible': False}
            if css:
                swim = {
                    'disponible': True,
                    'css_speed': 100.0 / (float(css) * 60),
                    'd_prime': 75.0,
                    'lthr': round(float(lthr_run) * 0.92) if lthr_run else None,
                    'glyc_total_g': peso * 7.0,
                    'readiness': _readiness(conn, atleta_id, fecha, 'swim'),
                }

            # FC máx y LTHR de bici (columnas opcionales: si no existen, las clases estiman)
            hr_max_at = lthr_bike_at = None
            try:
                r2 = conn.execute("SELECT hr_max, lthr_bike FROM atletas WHERE id=%s", (atleta_id,)).fetchone()
                if r2:
                    hr_max_at = float(r2[0]) if r2[0] else None
                    lthr_bike_at = float(r2[1]) if r2[1] else None
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
            zonas = zonas_para_reloj(
                float(lthr_run) if lthr_run else None, hr_max_at,
                float(pace_umbral) if pace_umbral else None,
                peso, float(ftp) if ftp else None, lthr_bike_at)

            return ok(limpiar_nan({
                'fecha': fecha,
                'peso_kg': peso,
                'zonas': zonas,
                'run': run,
                'bike': bike,
                'swim': swim,
                'constants': {
                    'glyc_frac': GLYC_FRAC,
                    'if_fallback': IF_FALLBACK,
                    'run_glyc_rates': RUN_GLYC_RATES,
                },
                'server_time': int(datetime.utcnow().timestamp()),
            }))
        except Exception as e:
            return error(str(e))
        finally:
            conn.close()
