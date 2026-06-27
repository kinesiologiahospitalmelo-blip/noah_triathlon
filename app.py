"""
app.py — NOA Backend API
-------------------------
Flask REST API que expone todos los módulos de NOA.
Punto de entrada para la futura app web y móvil.

USO:
  pip install flask flask-cors
  python app.py

ENDPOINTS:
  GET  /api/atletas
  POST /api/atletas
  GET  /api/atletas/<id>/estado
  GET  /api/atletas/<id>/prescripcion
  POST /api/atletas/<id>/ciclo
  POST /api/atletas/<id>/import
  GET  /api/atletas/<id>/zonas
  GET  /api/atletas/<id>/graficos
  GET  /api/atletas/<id>/health
  PUT  /api/prescripciones/<id>/bloque/<bloque_id>
"""

import sys, json, os
from pathlib import Path
from datetime import date, timedelta
from functools import wraps

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import psycopg2
import psycopg2.extras

from noa_db import NOADatabase
from patrones_sesion import (
    generar_semana_completa, calcular_zonas_atleta, ZONAS
)
from db_compat import ConexionCompat

app = Flask(__name__)
CORS(app)  # Permite requests desde React/app móvil

# Antes: archivo SQLite local (noa.db). Ahora: cadena de conexión a
# Postgres (Supabase) vía variable de entorno DATABASE_URL. Se mantiene
# el nombre DB_PATH para no renombrar todos los call-sites existentes.
DB_PATH = os.environ.get('DATABASE_URL', '')

# ── Cache en memoria de modelos ML (evita reentrenar en cada request) ─────────
_ML_CACHE = {}  # {atleta_id: NOAHMind}

def _get_mind(conn, atleta_id):
    """
    Retorna el modelo ML del atleta desde cache o disco.
    NUNCA reentrena automáticamente — eso es tarea del endpoint /entrenar.
    """
    global _ML_CACHE
    if atleta_id in _ML_CACHE:
        return _ML_CACHE[atleta_id]
    try:
        from noah_ml import NOAHMind
        mind = NOAHMind.cargar_modelos(conn, atleta_id)
        if mind is not None:
            _ML_CACHE[atleta_id] = mind
            return mind
    except Exception:
        pass
    return None


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def get_conn():
    # DictCursor: equivalente Postgres de sqlite3.Row (acceso por nombre Y
    # por índice numérico) — igual que en noa_db.py, para que el resto del
    # código (que accede a filas con row['col'] y con row[0] indistintamente)
    # siga funcionando sin cambios.
    conn = psycopg2.connect(DB_PATH, cursor_factory=psycopg2.extras.DictCursor)
    return ConexionCompat(conn)

def error(msg, code=400):
    return jsonify({'error': msg}), code

def ok(data):
    return jsonify({'ok': True, 'data': data})


# ─── AUTENTICACIÓN — login simple por atleta (usuario/contraseña dados por el coach) ──
#
# Tabla propia e independiente de NOADatabase/atletas — no se toca el esquema
# existente. Vinculada por atleta_id como clave foránea lógica.
#
# Contraseñas: hash SHA-256 + salt aleatorio por usuario (sin librerías nuevas).
# Sesiones: token aleatorio opaco guardado en una tabla con expiración.
#
# DOS ROLES:
#   - 'atleta' : el token está vinculado a un atleta_id concreto, solo puede
#                acceder a endpoints de ESE atleta.
#   - 'coach'  : el token no está vinculado a ningún atleta — puede acceder
#                a los endpoints de CUALQUIER atleta_id en la URL.

import hashlib, secrets
from datetime import datetime

TOKEN_DURACION_DIAS = 30

def _init_auth_tables():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usuarios_login (
            atleta_id     INTEGER UNIQUE,
            usuario       TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt          TEXT NOT NULL,
            rol           TEXT NOT NULL DEFAULT 'atleta',
            creado        TEXT NOT NULL,
            activo        INTEGER NOT NULL DEFAULT 1
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sesiones_login (
            token      TEXT PRIMARY KEY,
            atleta_id  INTEGER,
            rol        TEXT NOT NULL DEFAULT 'atleta',
            creado     TEXT NOT NULL,
            expira     TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def _hash_password(password, salt):
    return hashlib.sha256((salt + password).encode('utf-8')).hexdigest()

def _verificar_password(password, salt, password_hash):
    return _hash_password(password, salt) == password_hash

def _crear_token(atleta_id, rol='atleta'):
    conn = get_conn()
    token = secrets.token_urlsafe(32)
    ahora = datetime.utcnow()
    expira = ahora + timedelta(days=TOKEN_DURACION_DIAS)
    conn.execute(
        "INSERT INTO sesiones_login (token, atleta_id, rol, creado, expira) VALUES (%s,%s,%s,%s,%s)",
        (token, atleta_id, rol, ahora.isoformat(), expira.isoformat())
    )
    conn.commit()
    conn.close()
    return token

def _sesion_de_token(token):
    """Devuelve {'atleta_id':..., 'rol':...} si el token es válido y no
    expiró, None si no. atleta_id es None cuando rol=='coach'."""
    if not token:
        return None
    conn = get_conn()
    row = conn.execute(
        "SELECT atleta_id, rol, expira FROM sesiones_login WHERE token=%s", (token,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    atleta_id, rol, expira_str = row
    if datetime.utcnow() > datetime.fromisoformat(expira_str):
        return None
    return {'atleta_id': atleta_id, 'rol': rol}

def _token_de_request():
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        return auth[7:]
    return request.args.get('token')  # fallback para casos donde no se puede mandar header

def requiere_login(f):
    """
    Decorador para endpoints con <int:atleta_id> en la URL. Exige un token
    válido en el header Authorization: Bearer <token>.
      - Si la sesión es de rol 'coach' → acceso permitido a cualquier atleta_id.
      - Si es de rol 'atleta' → solo puede acceder al atleta_id de su propia
        sesión; si la URL pide otro atleta_id, se rechaza con 403. Esto es lo
        que impide que un alumno vea el dashboard de otro cambiando el
        número en /atleta/2 a mano.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = _token_de_request()
        sesion = _sesion_de_token(token)
        if sesion is None:
            return error('No autenticado o sesión expirada', 401)
        if sesion['rol'] == 'coach':
            return f(*args, **kwargs)
        atleta_id_pedido = kwargs.get('atleta_id')
        if atleta_id_pedido is not None and int(atleta_id_pedido) != sesion['atleta_id']:
            return error('No autorizado para ver este atleta', 403)
        return f(*args, **kwargs)
    return wrapper

def requiere_coach(f):
    """Decorador para endpoints exclusivos del coach (crear atletas, gestionar
    usuarios de login, etc.) — rechaza cualquier sesión de rol 'atleta'."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = _token_de_request()
        sesion = _sesion_de_token(token)
        if sesion is None or sesion['rol'] != 'coach':
            return error('Requiere acceso de coach', 403)
        return f(*args, **kwargs)
    return wrapper


@app.route('/api/login', methods=['POST'])
def login():
    """
    Body: { usuario, password }
    Devuelve: { token, atleta_id, nombre, rol }
    Sirve tanto para atletas como para el coach — el rol determina a qué
    puede acceder cada token (ver requiere_login).
    """
    _init_auth_tables()
    body = request.get_json() or {}
    usuario = (body.get('usuario') or '').strip()
    password = body.get('password') or ''
    if not usuario or not password:
        return error('Usuario y contraseña requeridos')

    conn = get_conn()
    row = conn.execute(
        "SELECT atleta_id, password_hash, salt, rol, activo FROM usuarios_login WHERE usuario=%s",
        (usuario,)
    ).fetchone()
    conn.close()

    if not row:
        return error('Usuario o contraseña incorrectos', 401)
    atleta_id, password_hash, salt, rol, activo = row
    if not activo:
        return error('Usuario deshabilitado', 401)
    if not _verificar_password(password, salt, password_hash):
        return error('Usuario o contraseña incorrectos', 401)

    token = _crear_token(atleta_id, rol)

    nombre = 'Coach' if rol == 'coach' else ''
    if rol != 'coach':
        db = NOADatabase(DB_PATH)
        atletas = db.get_atletas()
        fila = atletas[atletas['id'] == atleta_id]
        nombre = fila.iloc[0]['nombre'] if len(fila) else ''

    return ok({'token': token, 'atleta_id': (int(atleta_id) if atleta_id is not None else None),
               'nombre': nombre, 'rol': rol})


@app.route('/api/logout', methods=['POST'])
def logout():
    token = _token_de_request()
    if token:
        conn = get_conn()
        conn.execute("DELETE FROM sesiones_login WHERE token=%s", (token,))
        conn.commit()
        conn.close()
    return ok({'mensaje': 'sesión cerrada'})


@app.route('/api/me', methods=['GET'])
def me():
    """Devuelve el atleta_id/nombre/rol asociado al token actual."""
    token = _token_de_request()
    sesion = _sesion_de_token(token)
    if sesion is None:
        return error('No autenticado o sesión expirada', 401)
    if sesion['rol'] == 'coach':
        return ok({'atleta_id': None, 'nombre': 'Coach', 'rol': 'coach'})
    db = NOADatabase(DB_PATH)
    atletas = db.get_atletas()
    fila = atletas[atletas['id'] == sesion['atleta_id']]
    nombre = fila.iloc[0]['nombre'] if len(fila) else ''
    return ok({'atleta_id': int(sesion['atleta_id']), 'nombre': nombre, 'rol': 'atleta'})


@app.route('/api/admin/crear_usuario_login', methods=['POST'])
@requiere_coach
def admin_crear_usuario_login():
    """
    Endpoint para que EL COACH cree el usuario/contraseña de un atleta.
    Body: { atleta_id, usuario, password }
    Protegido con @requiere_coach — solo una sesión de coach ya logueada
    puede crear o actualizar credenciales de atletas.
    """
    _init_auth_tables()
    body = request.get_json() or {}
    atleta_id = body.get('atleta_id')
    usuario = (body.get('usuario') or '').strip()
    password = body.get('password') or ''
    if not atleta_id or not usuario or not password:
        return error('atleta_id, usuario y password son requeridos')
    if len(password) < 4:
        return error('La contraseña debe tener al menos 4 caracteres')

    salt = secrets.token_hex(16)
    password_hash = _hash_password(password, salt)
    ahora = datetime.utcnow().isoformat()

    conn = get_conn()
    try:
        conn.execute("""
            INSERT INTO usuarios_login (atleta_id, usuario, password_hash, salt, rol, creado, activo)
            VALUES (%s,%s,%s,%s,'atleta',%s,1)
            ON CONFLICT(atleta_id) DO UPDATE SET
                usuario=excluded.usuario,
                password_hash=excluded.password_hash,
                salt=excluded.salt
        """, (atleta_id, usuario, password_hash, salt, ahora))
        conn.commit()
    except psycopg2.IntegrityError:
        conn.close()
        return error('Ese nombre de usuario ya está en uso por otro atleta')
    conn.close()
    return ok({'atleta_id': atleta_id, 'usuario': usuario})


@app.route('/api/admin/bootstrap_coach', methods=['POST'])
def bootstrap_coach():
    """
    Crea el usuario del COACH — pensado para usarse UNA SOLA VEZ al
    configurar el sistema. Una vez que existe un usuario con rol='coach',
    este endpoint se desactiva solo (devuelve 403) para que no quede una
    puerta abierta indefinidamente sin protección.

    Body: { usuario, password }
    """
    _init_auth_tables()
    conn = get_conn()
    ya_existe = conn.execute(
        "SELECT COUNT(*) FROM usuarios_login WHERE rol='coach'"
    ).fetchone()[0]
    if ya_existe > 0:
        conn.close()
        return error('Ya existe un usuario coach — este endpoint solo funciona una vez. '
                      'Para cambiar la contraseña del coach, hacelo directo en la base de datos.', 403)

    body = request.get_json() or {}
    usuario = (body.get('usuario') or '').strip()
    password = body.get('password') or ''
    if not usuario or not password:
        conn.close()
        return error('Usuario y contraseña requeridos')
    if len(password) < 4:
        conn.close()
        return error('La contraseña debe tener al menos 4 caracteres')

    salt = secrets.token_hex(16)
    password_hash = _hash_password(password, salt)
    ahora = datetime.utcnow().isoformat()
    try:
        conn.execute("""
            INSERT INTO usuarios_login (atleta_id, usuario, password_hash, salt, rol, creado, activo)
            VALUES (NULL, %s, %s, %s, 'coach', %s, 1)
        """, (usuario, password_hash, salt, ahora))
        conn.commit()
    except psycopg2.IntegrityError:
        conn.close()
        return error('Ese nombre de usuario ya está en uso')
    conn.close()
    return ok({'usuario': usuario, 'rol': 'coach'})


_init_auth_tables()


# ─── ATLETAS ──────────────────────────────────────────────────────────────────

@app.route('/api/atletas', methods=['GET'])
def listar_atletas():
    """Lista todos los atletas activos."""
    db = NOADatabase(DB_PATH)
    atletas = db.get_atletas()
    result = []
    for _, a in atletas.iterrows():
        estado = db.get_estado_actual(int(a['id']))
        result.append({
            'id'          : int(a['id']),
            'nombre'      : a['nombre'],
            'email'       : a['email'],
            'deporte'     : a['deporte_ppal'],
            'lthr_run'    : a['lthr_run'],
            'ctl'         : estado.get('ctl'),
            'tsb'         : estado.get('tsb'),
            'hrv_flag'    : estado.get('hrv_flag'),
            'km_semana'   : estado.get('km_semana'),
        })
    return ok(result)


@app.route('/api/atletas', methods=['POST'])
def crear_atleta():
    """Crea un atleta nuevo."""
    d = request.json or {}
    required = ['nombre', 'email']
    for f in required:
        if not d.get(f):
            return error(f'Campo requerido: {f}')

    db = NOADatabase(DB_PATH)
    atleta_id = db.crear_atleta({
        'nombre':           d['nombre'],
        'email':            d['email'],
        'garmin_user':      d.get('garmin_email') or d.get('garmin_user') or d['email'],
        'garmin_pass':      d.get('garmin_password') or d.get('garmin_pass'),
        'lthr_run':         d.get('lthr_run'),
        'lthr_bike':        d.get('lthr_bike'),
        'lthr_swim':        d.get('lthr_swim'),
        'ftp_watts':        d.get('ftp') or d.get('ftp_watts'),
        'hr_max':           d.get('hr_max'),
        'peso_kg':          d.get('peso') or d.get('peso_kg'),
        'altura_cm':        d.get('altura_cm'),
        'edad':             d.get('edad'),
        'sexo':             d.get('sexo', 'M'),
        'deporte_ppal':     d.get('deporte_ppal', 'running'),
        'css_100m':         d.get('css'),
        'nivel_experiencia':d.get('nivel'),
        'horas_semana':     d.get('horas_semana'),
    })
    return ok({'id': atleta_id, 'atleta_id': atleta_id}), 201


@app.route('/api/atletas/<int:atleta_id>', methods=['GET'])
@requiere_login
def get_atleta(atleta_id):
    """Retorna datos completos de un atleta."""
    db = NOADatabase(DB_PATH)
    atleta = db.get_atleta(atleta_id)
    if not atleta:
        return error('Atleta no encontrado', 404)
    return ok(atleta)


# ─── ESTADO ACTUAL ────────────────────────────────────────────────────────────

@app.route('/api/atletas/<int:atleta_id>/estado', methods=['GET'])
@requiere_login
def get_estado(atleta_id):
    """Estado actual del atleta: CTL, ATL, TSB, HRV, sueño."""
    db = NOADatabase(DB_PATH)
    # Recalcular CTL fresco antes de devolver
    db.actualizar_ctl_atl_tsb(atleta_id)
    estado = db.get_estado_actual(atleta_id)
    atleta_check = estado.get('atleta') or {}
    if not atleta_check.get('id'):
        return error('Atleta no encontrado', 404)

    # Agregar datos de graficos
    graficos = db.get_datos_graficos(atleta_id, dias=90)

    return ok(_limpiar_nan({
        'estado'  : estado,
        'training': graficos['training'][-30:],
        'sleep'   : graficos['sleep'][-14:],
    }))


# ─── ZONAS ────────────────────────────────────────────────────────────────────

@app.route('/api/atletas/<int:atleta_id>/zonas', methods=['GET'])
@requiere_login
def get_zonas(atleta_id):
    """Zonas de entrenamiento personalizadas del atleta."""
    db = NOADatabase(DB_PATH)
    atleta = db.get_atleta(atleta_id)
    if not atleta:
        return error('Atleta no encontrado', 404)

    lthr    = atleta.get('lthr_run', 162)
    hr_max  = atleta.get('hr_max', 190)
    edad    = atleta.get('edad', 40)

    # Obtener pace Z2 real
    conn = get_conn()
    pace_z2 = 5.55
    try:
        lthr_z2_min = round(lthr * 0.75)
        lthr_z2_max = round(lthr * 0.87)
        rp = conn.execute('''
            SELECT AVG(pace) FROM sesiones
            WHERE atleta_id=%s AND hr_avg BETWEEN %s AND %s
            AND pace > 4.0 AND pace < 7.5
            AND duration_min > 20
        ''', (atleta_id, lthr_z2_min, lthr_z2_max)).fetchone()
        if rp and rp[0]:
            pace_z2 = round(float(rp[0]), 2)
    except Exception:
        # Rollback defensivo: si la conexión se reutilizara más abajo
        # (hoy no es el caso, se cierra enseguida) quedaría "envenenada"
        # en Postgres tras cualquier error dentro de una transacción.
        conn.rollback()
    conn.close()

    zonas = calcular_zonas_atleta(lthr, hr_max, pace_z2)

    return ok({
        'atleta_id' : atleta_id,
        'lthr'      : lthr,
        'hr_max'    : hr_max,
        'pace_z2'   : pace_z2,
        'zonas'     : zonas,
    })


# ─── PRESCRIPCIÓN ─────────────────────────────────────────────────────────────

@app.route('/api/atletas/<int:atleta_id>/prescripcion', methods=['GET'])
@requiere_login
def get_prescripcion(atleta_id):
    """Prescripción activa del atleta con bloques detallados — multideporte."""
    conn = get_conn()

    row = conn.execute('''
        SELECT id, fase, tss_semana_total, fecha_generada, estado
        FROM prescripciones
        WHERE atleta_id=%s AND estado IN ('pendiente','aprobada')
        ORDER BY id DESC LIMIT 1
    ''', (atleta_id,)).fetchone()

    if not row:
        conn.close()
        return ok({'prescripcion': None,
                   'mensaje': 'Sin prescripción activa. Ejecutar ciclo semanal.'})

    presc_id = row[0]

    # Leer columnas disponibles en prescripcion_bloques
    from db_compat import columnas_de_tabla
    cols = columnas_de_tabla(conn, 'prescripcion_bloques')

    # Query dinámica según columnas existentes
    extra_cols = []
    if 'sport'          in cols: extra_cols.append('sport')
    if 'sesion_sport'   in cols: extra_cols.append('sesion_sport')
    if 'sesion_nombre'  in cols: extra_cols.append('sesion_nombre')
    if 'sesion_fecha'   in cols: extra_cols.append('sesion_fecha')
    if 'sesion_duracion'in cols: extra_cols.append('sesion_duracion')
    if 'sesion_tss'     in cols: extra_cols.append('sesion_tss')
    if 'watts_min'      in cols: extra_cols.append('watts_min')
    if 'watts_max'      in cols: extra_cols.append('watts_max')
    if 'completada'     in cols: extra_cols.append('completada')
    if 'sesion_descripcion' in cols: extra_cols.append('sesion_descripcion')

    extra_select = (', ' + ', '.join(extra_cols)) if extra_cols else ''

    bloques = conn.execute(f'''
        SELECT sesion_num, bloque_num, nombre, zona, zona_nombre,
               duracion_min, repeticiones, pausa_min, pausa_activa,
               hr_min, hr_max, pace_ref, descripcion{extra_select}
        FROM prescripcion_bloques
        WHERE prescripcion_id=%s
          AND sesion_fecha IS NOT NULL AND sesion_fecha != ''
        ORDER BY sesion_num, bloque_num
    ''', (presc_id,)).fetchall()

    conn.close()

    # Índices de columnas extra (base = 13)
    def get_extra(b, name):
        if name in extra_cols:
            return b[13 + extra_cols.index(name)]
        return None

    # Agrupar bloques por sesión y extraer metadata de sesión
    ses_bloques  = {}
    ses_metadata = {}  # sesion_num → {sport, nombre, fecha, duracion, tss}

    for b in bloques:
        sn = b[0]
        if sn not in ses_bloques:
            ses_bloques[sn] = []
            # Metadata de la sesión — tomada del primer bloque
            ses_sport    = get_extra(b, 'sesion_sport') or get_extra(b, 'sport') or 'running'
            ses_nombre   = get_extra(b, 'sesion_nombre') or f'Sesión {sn}'
            ses_fecha    = get_extra(b, 'sesion_fecha') or ''
            ses_duracion = get_extra(b, 'sesion_duracion') or 0
            ses_tss      = get_extra(b, 'sesion_tss') or 0
            ses_metadata[sn] = {
                'sport'   : ses_sport,
                'nombre'  : ses_nombre,
                'fecha'   : ses_fecha,
                'duracion': ses_duracion,
                'tss'     : ses_tss,
            }

        ses_bloques[sn].append({
            'bloque_num'  : b[1],
            'nombre'      : b[2],
            'zona'        : b[3],
            'zona_nombre' : b[4],
            'duracion_min': b[5],
            'repeticiones': b[6],
            'pausa_min'   : b[7],
            'pausa_activa': bool(b[8]),
            'hr_min'      : b[9],
            'hr_max'      : b[10],
            'pace_ref'    : b[11],
            'descripcion' : b[12],
            'sport'       : get_extra(b, 'sport') or get_extra(b, 'sesion_sport') or 'running',
            'watts_min'   : get_extra(b, 'watts_min'),
            'watts_max'   : get_extra(b, 'watts_max'),
            'completada'  : get_extra(b, 'completada'),
            'sesion_descripcion': get_extra(b, 'sesion_descripcion'),
        })

    # Armar lista de sesiones a partir de los bloques (dinámica, soporta 3 o 9)
    sesiones = []
    for sn in sorted(ses_bloques.keys()):
        meta = ses_metadata.get(sn, {})
        bloques_ses = ses_bloques[sn]

        # HR del bloque principal (el de mayor intensidad o el segundo)
        b_ref = bloques_ses[1] if len(bloques_ses) > 1 else bloques_ses[0]

        # completada se guarda igual en todos los bloques de la sesión —
        # tomamos el primero que tenga un valor no nulo
        completada_ses  = next((b.get('completada') for b in bloques_ses if b.get('completada')), None)
        descripcion_ses = next((b.get('sesion_descripcion') for b in bloques_ses if b.get('sesion_descripcion')), '')

        sesiones.append({
            'sesion_num': sn,           # CRÍTICO: el frontend lo usa para PATCH/DELETE
            'id'        : sn,           # alias por compatibilidad (ses.sesion_num||ses.id)
            'sport'   : meta.get('sport', 'running'),
            'nombre'  : meta.get('nombre', f'Sesión {sn}'),
            'fecha'   : meta.get('fecha', ''),
            'duracion': meta.get('duracion', 0),
            'tss'     : meta.get('tss', 0),
            'hr_min'  : b_ref.get('hr_min'),
            'hr_max'  : b_ref.get('hr_max'),
            'completada': completada_ses,   # 'done' | 'partial' | 'miss' | None — usado por getEstado() en el frontend
            'descripcion': descripcion_ses, # incluye nivel de carga + nutrición cuando aplica
            'bloques' : bloques_ses,
        })

    return ok({
        'prescripcion': {
            'id'            : presc_id,
            'fase'          : row[1],
            'tss_total'     : row[2],
            'fecha_generada': row[3],
            'estado'        : row[4],
            'sesiones'      : sesiones,
        }
    })


@app.route('/api/atletas/<int:atleta_id>/sesiones/<int:sesion_id>', methods=['PATCH'])
@requiere_login
def actualizar_estado_sesion(atleta_id, sesion_id):
    """Marca una sesión como done/partial/miss O actualiza sus bloques."""
    d = request.json or {}
    conn = get_conn()

    # Asegurar que la columna 'completada' existe (defensivo — no rompe nada si ya existe)
    from db_compat import asegurar_columnas
    asegurar_columnas(conn, 'prescripcion_bloques', [('completada', 'TEXT')])
    conn.commit()

    # Caso 1: actualizar estado
    estado = d.get('estado')
    if estado and estado in ('done', 'partial', 'miss'):
        conn.execute('''
            UPDATE prescripcion_bloques SET completada=%s
            WHERE prescripcion_id IN (
                SELECT id FROM prescripciones WHERE atleta_id=%s AND estado IN ('pendiente','aprobada')
                ORDER BY id DESC LIMIT 1
            ) AND sesion_num=%s
        ''', (estado, atleta_id, sesion_id))
        conn.commit()
        conn.close()
        return ok({'actualizado': True, 'estado': estado})

    # Caso 2: actualizar bloques (edición desde el coach)
    bloques = d.get('bloques')
    if bloques:
        presc = conn.execute('''
            SELECT id FROM prescripciones WHERE atleta_id=%s AND estado IN ('pendiente','aprobada')
            ORDER BY id DESC LIMIT 1
        ''', (atleta_id,)).fetchone()
        if not presc:
            conn.close()
            return error('Sin prescripción activa')
        presc_id = presc[0]

        # Obtener columnas disponibles
        from db_compat import columnas_de_tabla
        cols = columnas_de_tabla(conn, 'prescripcion_bloques')

        # ── CRÍTICO: leer los metadatos de sesión (fecha, nombre, sport, etc.)
        # de los bloques ORIGINALES que ya están en la DB, ANTES de borrarlos.
        # Estos campos viven a nivel SESIÓN, no vienen en cada bloque que manda
        # el frontend al editar — si se buscan ahí, siempre son None y se
        # pierde la fecha/nombre de la sesión al guardar una edición.
        META_COLS = ['sport','sesion_sport','sesion_nombre','sesion_fecha',
                     'sesion_duracion','sesion_tss','sesion_descripcion']
        meta_existente = {}
        fila_original = conn.execute(f'''
            SELECT {','.join(c for c in META_COLS if c in cols)}
            FROM prescripcion_bloques
            WHERE prescripcion_id=%s AND sesion_num=%s
            LIMIT 1
        ''', (presc_id, sesion_id)).fetchone()
        cols_meta_presentes = [c for c in META_COLS if c in cols]
        if fila_original:
            meta_existente = dict(zip(cols_meta_presentes, fila_original))

        # El payload puede mandar overrides a nivel sesión (ej. nueva fecha
        # si el coach mueve la sesión de día) — si vienen, tienen prioridad.
        for k, payload_key in [('sesion_fecha','fecha'), ('sesion_nombre','nombre'),
                                ('sesion_sport','sport'), ('sesion_duracion','duracion'),
                                ('sesion_tss','tss')]:
            if d.get(payload_key) is not None:
                meta_existente[k] = d.get(payload_key)

        # Si después de todo esto sigue sin haber fecha, no se puede guardar —
        # mejor rechazar con error claro que perder el dato silenciosamente.
        if not meta_existente.get('sesion_fecha'):
            conn.close()
            return error('No se encontró la fecha original de la sesión — no se puede guardar la edición sin fecha.')

        # ── Recalcular nutrición SIEMPRE al guardar, sin importar si la sesión
        # se generó automáticamente o la editó el coach a mano. La nutrición
        # es una función matemática de duración+intensidad+peso real — no
        # depende del origen de la sesión.
        try:
            from noah_nutricion_completa import construir_recomendacion_durante

            sport_real = meta_existente.get('sesion_sport') or meta_existente.get('sport') or 'running'

            # Duración total real, incluyendo pausas entre repeticiones —
            # misma fórmula que usa el frontend para mostrar el total.
            dur_total = 0.0
            suma_if_x_dur = 0.0
            ZONA_IF = {'Z1':0.65,'Z2':0.80,'Z3':0.88,'Z4':0.95,'Z5':1.02,'Z6':1.10,
                       'BZ1':0.55,'BZ2':0.80,'BZ3':0.88,'BZ4':0.95,'BZ5':1.05,'BZ6':1.20,'BZ7':1.40}
            for b in bloques:
                reps    = b.get('repeticiones', 1) or 1
                dur     = b.get('duracion_min', 0) or 0
                pausa   = b.get('pausa_min', 0) or 0
                n_pausas = max(0, reps - 1)
                dur_bloque_total = dur*reps + pausa*n_pausas
                dur_total += dur_bloque_total
                if_zona = ZONA_IF.get(b.get('zona', 'Z2'), 0.75)
                suma_if_x_dur += if_zona * dur_bloque_total

            if_promedio = (suma_if_x_dur / dur_total) if dur_total > 0 else 0.75

            peso_row = conn.execute("SELECT peso_kg FROM atletas WHERE id=%s", (atleta_id,)).fetchone()
            peso_kg = peso_row[0] if peso_row and peso_row[0] else None

            rec = construir_recomendacion_durante(
                deporte=sport_real, dur_min=dur_total, intensidad_if=if_promedio, peso_kg=peso_kg
            )
            texto_nutricion = rec.get('texto_corto', '')

            # Preservar cualquier otro contenido de la descripción (ej. "Nivel ALTO — metodo")
            # que no sea la nutrición vieja, y reemplazar solo la parte de nutrición.
            desc_previa = meta_existente.get('sesion_descripcion') or ''
            desc_sin_nutricion = desc_previa.split(' | Nutrición:')[0].split('Nutrición:')[0].strip(' |')
            nueva_desc = (f'{desc_sin_nutricion} | Nutrición: {texto_nutricion}'
                          if desc_sin_nutricion else f'Nutrición: {texto_nutricion}')
            if 'sesion_descripcion' in cols_meta_presentes:
                meta_existente['sesion_descripcion'] = nueva_desc
        except Exception:
            # Rollback OBLIGATORIO acá: la conexión sigue usándose más abajo
            # (DELETE/INSERT de prescripcion_bloques) — si el SELECT de arriba
            # falló dentro de una transacción Postgres y no se hace rollback,
            # esas consultas posteriores fallarían en cascada con
            # "current transaction is aborted". Nutrición sigue siendo
            # silenciosa/no bloqueante — el rollback no cambia ese comportamiento,
            # solo evita que el error se propague a operaciones no relacionadas.
            conn.rollback()

        # Borrar bloques actuales de esa sesión
        conn.execute(
            'DELETE FROM prescripcion_bloques WHERE prescripcion_id=%s AND sesion_num=%s',
            (presc_id, sesion_id)
        )

        # Insertar bloques nuevos, aplicando los metadatos de sesión a TODOS
        for i, b in enumerate(bloques, start=1):
            datos = {
                'prescripcion_id': presc_id, 'atleta_id': atleta_id,
                'sesion_num': sesion_id, 'bloque_num': i,
                'nombre': b.get('nombre',''), 'zona': b.get('zona','Z2'),
                'zona_nombre': b.get('zona_nombre',''),
                'duracion_min': b.get('duracion_min', 10),
                'repeticiones': b.get('repeticiones', 1),
                'pausa_min': b.get('pausa_min', 0),
                'pausa_activa': int(b.get('pausa_activa', True)),
                'hr_min': b.get('hr_min'), 'hr_max': b.get('hr_max'),
                'pace_ref': b.get('pace_ref'), 'descripcion': b.get('descripcion',''),
            }
            if 'watts_min' in cols: datos['watts_min'] = b.get('watts_min')
            if 'watts_max' in cols: datos['watts_max'] = b.get('watts_max')

            # Metadatos de sesión — SIEMPRE desde meta_existente, nunca desde
            # el bloque individual (que no los tiene).
            for col in cols_meta_presentes:
                datos[col] = meta_existente.get(col)

            ks = list(datos.keys())
            conn.execute(
                f"INSERT INTO prescripcion_bloques ({','.join(ks)}) VALUES ({','.join(['%s']*len(ks))})",
                list(datos.values())
            )

        conn.commit()
        conn.close()
        return ok({'actualizado': True, 'bloques': len(bloques), 'tss': d.get('tss'),
                   'fecha': meta_existente.get('sesion_fecha')})

    conn.close()
    return error('Nada que actualizar')


@app.route('/api/atletas/<int:atleta_id>/sesiones/<int:sesion_id>', methods=['DELETE'])
@requiere_login
def borrar_sesion(atleta_id, sesion_id):
    """Borra todos los bloques de una sesión de la prescripción activa."""
    conn = get_conn()
    conn.execute('''
        DELETE FROM prescripcion_bloques
        WHERE prescripcion_id IN (
            SELECT id FROM prescripciones WHERE atleta_id=%s AND estado IN ('pendiente','aprobada')
            ORDER BY id DESC LIMIT 1
        )
        AND sesion_num=%s
    ''', (atleta_id, sesion_id))
    conn.commit()
    conn.close()
    return ok({'borrado': True})


@app.route('/api/atletas/<int:atleta_id>/ciclo', methods=['POST'])
@requiere_login
def generar_ciclo(atleta_id):
    """
    Genera la prescripción semanal del atleta.

    Flujo completo:
      1. Marca todas las prescripciones anteriores como 'vencida'
      2. Lee receta del Optimizer (si fue aplicada en los últimos 28 días)
      3. Corre NOAH Intel internamente para calcular TSS del día
      4. Llama a ciclo_semanal.py con los parámetros enriquecidos
      5. Devuelve la nueva prescripción activa

    Body JSON opcional:
      { "forzar": true }   → genera aunque ya haya una activa esta semana
    """
    import subprocess
    from datetime import datetime

    # Acepta requests con o sin body/Content-Type
    try:
        datos = request.get_json(force=True, silent=True) or {}
    except Exception:
        datos = {}
    forzar = datos.get('forzar', False)
    conn   = get_conn()
    pasos  = []

    try:
        # ── 1. INVALIDAR PRESCRIPCIONES ANTERIORES ───────────────────────────
        rows_previas = conn.execute(
            "SELECT id FROM prescripciones WHERE atleta_id=%s AND estado IN ('pendiente','aprobada')",
            (atleta_id,)
        ).fetchall()

        if rows_previas:
            ids_previos = [r[0] for r in rows_previas]
            conn.execute(
                "UPDATE prescripciones SET estado='vencida' WHERE atleta_id=%s AND estado IN ('pendiente','aprobada')",
                (atleta_id,)
            )
            conn.commit()
            pasos.append({
                'paso'   : 'invalidar_previas',
                'ok'     : True,
                'detalle': f'{len(ids_previos)} prescripción(es) marcadas como vencida',
            })
        else:
            pasos.append({'paso': 'invalidar_previas', 'ok': True, 'detalle': 'Sin prescripciones previas activas'})

        # ── 2. LEER RECETA DEL OPTIMIZER ─────────────────────────────────────
        receta_optimizer = None
        receta_fecha     = None
        try:
            row_perfil = conn.execute(
                'SELECT datos_json FROM perfiles_macro WHERE atleta_id=%s AND activo=1',
                (atleta_id,)
            ).fetchone()
            if row_perfil:
                perfil = json.loads(row_perfil[0])
                receta_raw   = perfil.get('receta_optimizer')
                receta_fecha = perfil.get('receta_fecha')

                # Solo usar la receta si fue aplicada en los últimos 28 días
                if receta_raw and receta_fecha:
                    try:
                        dias_receta = (date.today() - date.fromisoformat(receta_fecha)).days
                        if dias_receta <= 28:
                            receta_optimizer = receta_raw
                    except Exception:
                        receta_optimizer = receta_raw  # si falla el parse, la usamos igual

            pasos.append({
                'paso'          : 'leer_optimizer',
                'ok'            : True,
                'receta'        : receta_optimizer,
                'receta_fecha'  : receta_fecha,
                'detalle'       : f'Receta "{receta_optimizer}" activa' if receta_optimizer else 'Sin receta del optimizer (se usará lógica por defecto)',
            })
        except Exception as e:
            pasos.append({'paso': 'leer_optimizer', 'ok': False, 'detalle': str(e)})

        # ── 3. NOAH INTEL — TSS del día (diagnóstico interno) ────────────────
        tss_hoy    = None
        intel_data = {}
        try:
            # Intentar importar el módulo de intel/diagnóstico
            try:
                from noah_intel import calcular_intel_diario
                intel_data = calcular_intel_diario(conn, atleta_id) or {}
                tss_hoy    = intel_data.get('tss_hoy') or intel_data.get('tss_dia')
            except ImportError:
                pass

            # Fallback: leer TSS directamente desde sesiones del día
            if tss_hoy is None:
                row_tss = conn.execute(
                    "SELECT SUM(tss_total) FROM sesiones WHERE atleta_id=%s AND fecha=%s AND tss_total > 0",
                    (atleta_id, str(date.today()))
                ).fetchone()
                tss_hoy = round(float(row_tss[0]), 1) if row_tss and row_tss[0] else 0.0

            pasos.append({
                'paso'   : 'noah_intel',
                'ok'     : True,
                'tss_hoy': tss_hoy,
                'detalle': f'TSS hoy: {tss_hoy}',
            })
        except Exception as e:
            tss_hoy = 0.0
            pasos.append({'paso': 'noah_intel', 'ok': False, 'detalle': str(e)})

        conn.close()
        conn = None

        # ── 4. LLAMAR A ciclo_semanal.py ─────────────────────────────────────
        # ciclo_semanal.py lee la receta del optimizer directamente desde
        # perfiles_macro (ya guardada por /optimizer/aplicar) y calcula
        # el TSS internamente con ML. Solo necesita --atleta.
        cmd = [
            sys.executable,
            str(BASE_DIR / 'ciclo_semanal.py'),
            '--atleta', str(atleta_id),
        ]

        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        result = subprocess.run(
            cmd,
            capture_output=True, text=True,
            cwd=str(BASE_DIR),
            encoding='utf-8', errors='replace',
            timeout=180,
            env=env,
        )

        if result.returncode != 0:
            stderr_full = result.stderr.strip()
            stdout_full = result.stdout.strip()
            pasos.append({'paso': 'ciclo_semanal', 'ok': False, 'detalle': stderr_full})
            return jsonify({
                'ok'    : False,
                'error' : f'Error en ciclo_semanal: {stderr_full}',
                'stdout': stdout_full,
                'pasos' : pasos,
            }), 500

        pasos.append({
            'paso'   : 'ciclo_semanal',
            'ok'     : True,
            'detalle': result.stdout[-200:].strip() or 'Prescripción generada',
        })

        # ── Matching automático post-ciclo ────────────────────────────────────
        try:
            from noah_matching import get_conn as match_conn, migrar_tabla_feedback, matching_atleta
            c2 = match_conn()
            migrar_tabla_feedback(c2)
            n_matched = matching_atleta(c2, atleta_id, dias=60, verbose=False)
            c2.close()
            pasos.append({'paso': 'matching', 'ok': True, 'sesiones_matcheadas': n_matched})
        except Exception as e_match:
            pasos.append({'paso': 'matching', 'ok': False, 'detalle': str(e_match)})

        # ── 5. DEVOLVER LA PRESCRIPCIÓN NUEVA ────────────────────────────────
        resp = get_prescripcion(atleta_id)

        # Inyectar log de pasos en la respuesta
        try:
            body = resp.get_json()
            if body and body.get('ok'):
                body['pasos'] = pasos
                body['receta_aplicada'] = receta_optimizer
                body['tss_hoy']         = tss_hoy
                return jsonify(body)
        except Exception:
            pass

        return resp

    except Exception as e:
        import traceback
        if conn:
            try: conn.close()
            except: pass
        return jsonify({
            'ok'   : False,
            'error': str(e),
            'trace': traceback.format_exc()[-400:],
            'pasos': pasos,
        }), 500


# ─── EDITAR PRESCRIPCIÓN ──────────────────────────────────────────────────────

@app.route('/api/prescripciones/<int:presc_id>/sesion/<int:ses_num>', methods=['PUT'])
def editar_sesion(presc_id, ses_num):
    """Edita el nombre de una sesión."""
    d = request.json or {}
    col = f'ses{ses_num}_tipo'
    conn = get_conn()
    conn.execute(f'UPDATE prescripciones SET {col}=%s WHERE id=%s',
                 (d.get('nombre'), presc_id))
    conn.commit()
    conn.close()
    return ok({'actualizado': True})


@app.route('/api/prescripciones/<int:presc_id>/bloque/<int:bloque_id>', methods=['PUT'])
def editar_bloque(presc_id, bloque_id):
    """Edita un bloque específico de la prescripción."""
    d = request.json or {}
    conn = get_conn()
    conn.execute('''
        UPDATE prescripcion_bloques SET
            nombre=%s, duracion_min=%s, repeticiones=%s,
            pausa_min=%s, hr_min=%s, hr_max=%s, descripcion=%s
        WHERE id=%s AND prescripcion_id=%s
    ''', (
        d.get('nombre'), d.get('duracion_min'), d.get('repeticiones'),
        d.get('pausa_min'), d.get('hr_min'), d.get('hr_max'),
        d.get('descripcion'), bloque_id, presc_id
    ))
    conn.commit()
    conn.close()
    return ok({'actualizado': True})


# ─── IMPORTAR ACTIVIDADES ─────────────────────────────────────────────────────

@app.route('/api/atletas/<int:atleta_id>/import', methods=['POST'])
@requiere_login
def importar_actividades(atleta_id):
    """Recibe un Activities.csv y lo importa para el atleta."""
    if 'file' not in request.files:
        return error('Se requiere un archivo CSV')

    f = request.files['file']
    tmp_path = BASE_DIR / f'tmp_import_{atleta_id}.csv'
    f.save(str(tmp_path))

    import subprocess
    result = subprocess.run(
        [sys.executable, str(BASE_DIR / 'importar_activities.py'),
         '--atleta', str(atleta_id), '--csv', str(tmp_path)],
        capture_output=True, text=True, cwd=str(BASE_DIR), encoding='utf-8', errors='replace'
    )
    tmp_path.unlink(missing_ok=True)

    if result.returncode != 0:
        return error(f'Error importando: {result.stderr[:200]}')

    return ok({'mensaje': 'Importación completada', 'output': result.stdout[-500:]})


# ─── PERFIL MACRO ─────────────────────────────────────────────────────────────

@app.route('/api/atletas/<int:atleta_id>/perfil', methods=['GET'])
@requiere_login
def get_perfil(atleta_id):
    """Retorna el perfil de macrociclo activo."""
    conn = get_conn()
    row = conn.execute(
        'SELECT datos_json, fecha_generado FROM perfiles_macro WHERE atleta_id=%s AND activo=1',
        (atleta_id,)
    ).fetchone()
    conn.close()
    if not row:
        return ok({'perfil': None})
    return ok({'perfil': json.loads(row[0]), 'fecha': row[1]})


@app.route('/api/atletas/<int:atleta_id>/perfil', methods=['POST'])
@requiere_login
def crear_perfil(atleta_id):
    """Crea o actualiza el perfil de macrociclo."""
    d = request.json or {}
    conn = get_conn()
    conn.execute('UPDATE perfiles_macro SET activo=0 WHERE atleta_id=%s', (atleta_id,))
    conn.execute(
        'INSERT INTO perfiles_macro (atleta_id, fecha_generado, datos_json, activo) VALUES (%s,%s,%s,1)',
        (atleta_id, str(date.today()), json.dumps(d))
    )
    conn.commit()
    conn.close()
    return ok({'guardado': True}), 201


# ─── NUTRICIÓN POST-ENTRENAMIENTO ────────────────────────────────────────────

@app.route('/api/atletas/<int:atleta_id>/nutricion_post', methods=['GET'])
@requiere_login
def get_nutricion_post(atleta_id):
    """
    Calcula la recomendación de nutrición POST-entrenamiento usando datos
    REALES de la actividad sincronizada de Garmin (no la planificada).
    Aplica a las 3 disciplinas. Bibliografía: ISSN 2017, Moore 2015,
    Witard 2014, Shirreffs & Sawka 2011 (ver noah_nutricion_completa.py).

    Si falta el peso del atleta, lo declara explícitamente — no asume
    un valor promedio.

    Query params:
      fecha: fecha de la actividad (default hoy)
      sesion_id: id específico en 'sesiones' (opcional, si hay varias el mismo día)
      proxima_24h: 'true'/'false' si hay otra sesión exigente en <24h (opcional)
    """
    try:
        fecha       = request.args.get('fecha', str(date.today()))
        sesion_id   = request.args.get('sesion_id')
        proxima_str = request.args.get('proxima_24h')
        proxima_24h = (proxima_str.lower() == 'true') if proxima_str is not None else None

        conn = get_conn()

        atleta_row = conn.execute(
            "SELECT peso_kg FROM atletas WHERE id=%s", (atleta_id,)
        ).fetchone()
        peso_kg = atleta_row[0] if atleta_row and atleta_row[0] else None

        if sesion_id:
            act = conn.execute("""
                SELECT sport, duration_min, tss_total, calories, intensity_factor,
                       if_sesion, temperatura_avg
                FROM sesiones WHERE id=%s
            """, (sesion_id,)).fetchone()
        else:
            act = conn.execute("""
                SELECT sport, duration_min, tss_total, calories, intensity_factor,
                       if_sesion, temperatura_avg
                FROM sesiones WHERE atleta_id=%s AND fecha=%s
                ORDER BY duration_min DESC LIMIT 1
            """, (atleta_id, fecha)).fetchone()

        conn.close()

        if not act:
            return ok({'sin_actividad': True, 'mensaje': 'Sin actividad real registrada ese día.'})

        sport, dur_min, tss_total, calorias, if_intensity, if_sesion, temp = act
        intensidad_if = if_sesion or if_intensity or 0.75

        if not dur_min or dur_min <= 0:
            return ok({'sin_actividad': True, 'mensaje': 'Actividad sin duración válida.'})

        if not peso_kg:
            return ok({
                'sin_datos_atleta': True,
                'faltantes': ['peso_kg'],
                'mensaje': 'Falta el peso del atleta en su perfil — no se puede calcular '
                           'la recuperación post-entreno (proteína y CHO dependen del peso '
                           'corporal según ISSN 2017). Completar el dato en el perfil.',
                'sport': sport, 'duracion_real_min': dur_min,
            })

        from noah_nutricion_completa import construir_recomendacion_post

        rec = construir_recomendacion_post(
            peso_kg=peso_kg, dur_real_min=dur_min, intensidad_if_real=intensidad_if,
            proxima_sesion_exigente_24h=proxima_24h
        )
        rec['sport'] = sport
        rec['duracion_real_min'] = dur_min
        rec['calorias_reales'] = calorias

        return ok(rec)

    except Exception as e:
        return error(str(e))


# ─── APROBAR PRESCRIPCIÓN ─────────────────────────────────────────────────────


@app.route('/api/atletas/<int:atleta_id>/prescripcion/aprobar', methods=['POST'])
@requiere_login
def aprobar_prescripcion(atleta_id):
    """Marca la prescripción activa como aprobada por el coach."""
    conn = None
    try:
        conn = get_conn()
        row = conn.execute(
            "SELECT id FROM prescripciones WHERE atleta_id=%s AND estado IN ('pendiente','aprobada') ORDER BY id DESC LIMIT 1",
            (atleta_id,)
        ).fetchone()
        if not row:
            conn.close()
            return error('Sin prescripción pendiente')
        conn.execute(
            "UPDATE prescripciones SET estado='aprobada' WHERE id=%s",
            (row[0],)
        )
        conn.commit()
        conn.close()
        return ok({'aprobada': True, 'prescripcion_id': row[0]})
    except Exception as e:
        # Cierre explícito en el path de error — el código original dejaba
        # la conexión abierta si algo fallaba (fuga de conexión, no
        # específico de Postgres pero más grave ahí por el límite bajo de
        # conexiones simultáneas del plan gratuito de Supabase).
        if conn:
            try: conn.close()
            except Exception: pass
        return error(str(e))




# ─── SESIÓN MANUAL DEL COACH ──────────────────────────────────────────────────

@app.route('/api/atletas/<int:atleta_id>/prescripcion/sesion', methods=['POST'])
@requiere_login
def agregar_sesion_manual(atleta_id):
    """
    Agrega una sesión manual a la prescripción activa.
    Usa la biblioteca v3 (sesiones_biblioteca.json) + noah_nivel_carga para
    generar bloques fisiológicamente correctos (piso/techo, reps, pausas).
    Fallback a lógica simple de un solo bloque si la biblioteca no aplica.
    """
    try:
        d        = request.get_json(force=True, silent=True) or {}
        sport    = d.get('sport', 'running')
        tipo     = d.get('tipo', 'aerobico')      # aerobico|long|ftp|vo2|neuro|recuperacion
        fecha    = d.get('fecha', '')
        dur_min  = int(d.get('duracion_min', 45))
        nombre_d = d.get('nombre', '')

        # Validación dura: la fecha es obligatoria y debe tener formato YYYY-MM-DD.
        # Si llega vacía o mal formada, se rechaza la petición en vez de guardar
        # un bloque con sesion_fecha=NULL que después aparece como "INVALID DATE".
        if not fecha:
            return error('Falta la fecha de la sesión. No se puede agregar sin fecha.')
        try:
            from datetime import datetime as _dt
            _dt.strptime(fecha, '%Y-%m-%d')
        except ValueError:
            return error(f'Fecha inválida: "{fecha}". Formato esperado: YYYY-MM-DD.')

        conn = get_conn()

        row = conn.execute(
            "SELECT id FROM prescripciones WHERE atleta_id=%s AND estado IN ('pendiente','aprobada') ORDER BY id DESC LIMIT 1",
            (atleta_id,)
        ).fetchone()
        if not row:
            conn.close()
            return error('Sin prescripción activa')
        presc_id = row[0]

        atleta_row = conn.execute(
            "SELECT lthr_run, lthr_bike, ftp_watts FROM atletas WHERE id=%s", (atleta_id,)
        ).fetchone()
        lthr      = (atleta_row[0] if atleta_row else None) or 162
        lthr_bike = (atleta_row[1] if atleta_row else None) or 150
        ftp_watts = (atleta_row[2] if atleta_row else None)

        # Leer fase activa del perfil macro (si existe)
        fase = 'A'
        perfil_row = conn.execute(
            "SELECT datos_json FROM perfiles_macro WHERE atleta_id=%s AND activo=1", (atleta_id,)
        ).fetchone()
        if perfil_row:
            try:
                pdat = json.loads(perfil_row[0])
                fase = pdat.get('fase_actual', 'A')
            except Exception:
                pass

        # HRV flag del día (para piso/techo y nivel de carga)
        hrv_flag = 'amarillo'
        hrv_row = conn.execute(
            "SELECT hrv_flag FROM sleep_hrv WHERE atleta_id=%s AND fecha<=%s ORDER BY fecha DESC LIMIT 1",
            (atleta_id, fecha)
        ).fetchone()
        if hrv_row and hrv_row[0]:
            hrv_flag = hrv_row[0]

        # Mapear tipo (UI) → categoría de biblioteca + deporte
        DEPORTE_MAP = {'running':'run', 'cycling':'bike', 'swimming':'swim'}
        TIPO_MAP    = {'aerobico':'long', 'long':'long', 'ftp':'ftp', 'vo2':'vo2',
                       'neuro':'neuro', 'recuperacion':'recuperacion'}
        deporte_bib = DEPORTE_MAP.get(sport, 'run')
        categoria   = TIPO_MAP.get(tipo, 'long')

        bloques_generados = None
        tss_est = None
        nombre  = nombre_d

        # ── Intentar usar biblioteca v3 + nivel de carga ──────────────────────
        try:
            bib_path = Path(__file__).parent / 'sesiones_biblioteca.json'
            if bib_path.exists():
                from noah_nivel_carga import (calcular_nivel_carga,
                                               seleccionar_metodo_biblioteca,
                                               parametrizar_sesion)
                biblioteca = json.load(open(bib_path, encoding='utf-8'))

                nivel_result = calcular_nivel_carga(conn, atleta_id, fecha=fecha,
                                                     tsb=None, hrv_flag=hrv_flag)
                nivel = nivel_result['nivel']

                metodo = seleccionar_metodo_biblioteca(biblioteca, deporte_bib, categoria, nivel, fase)

                if metodo:
                    params = parametrizar_sesion(metodo, nivel, tss_objetivo=None,
                                                  dur_max_min=dur_min, hrv_flag=hrv_flag)
                    if not nombre:
                        nombre = params['nombre']

                    lthr_ref = lthr_bike if sport == 'cycling' else lthr
                    zona_base = params.get('zona') or metodo.get('zona_objetivo', 'Z2')
                    # Tomar solo la primera zona si viene compuesta (ej "Z1-Z2")
                    zona_principal = zona_base.split('-')[0] if '-' in zona_base else zona_base

                    bloques_generados = []
                    cal_min = params['calentamiento_min'] or 10
                    enf_min = params['enfriamiento_min'] or 8
                    reps    = params['reps']
                    dur_b   = params['dur_bloque_min']
                    pausa_b = params['pausa_min']

                    # Factores por zona — para BIKE se usan sobre FTP (vatios reales),
                    # para RUN/SWIM se usan sobre LTHR (HR). Bike NUNCA usa HR como
                    # métrica principal — siempre potencia, según indicación del coach.
                    ZONA_FACTOR = {'Z1':(0.68,0.75),'Z2':(0.75,0.87),'Z3':(0.87,0.93),
                                    'Z4':(0.93,1.00),'Z5':(1.00,1.06),'Z6':(1.06,1.20)}

                    def metrica_de(zona):
                        """Retorna (hr_min, hr_max, watts_min, watts_max) según deporte."""
                        f = ZONA_FACTOR.get(zona, (0.75, 0.87))
                        if sport == 'cycling' and ftp_watts:
                            return None, None, round(ftp_watts*f[0]), round(ftp_watts*f[1])
                        lthr_ref = lthr_bike if sport == 'cycling' else lthr
                        return round(lthr_ref*f[0]), round(lthr_ref*f[1]), None, None

                    hr1, hr2, w1, w2 = metrica_de('Z1')
                    bloques_generados.append({
                        'nombre':'Calentamiento','zona':'Z1','zona_nombre':'Z1',
                        'duracion_min':cal_min,'repeticiones':1,'pausa_min':0,'pausa_activa':False,
                        'hr_min':hr1,'hr_max':hr2,'watts_min':w1,'watts_max':w2,
                    })
                    hr1, hr2, w1, w2 = metrica_de(zona_principal)
                    bloques_generados.append({
                        'nombre':nombre,'zona':zona_principal,'zona_nombre':zona_principal,
                        'duracion_min':dur_b,'repeticiones':reps,'pausa_min':pausa_b,
                        'pausa_activa':params['pausa_activa'],
                        'hr_min':hr1,'hr_max':hr2,'watts_min':w1,'watts_max':w2,
                    })
                    hr1, hr2, w1, w2 = metrica_de('Z1')
                    bloques_generados.append({
                        'nombre':'Enfriamiento','zona':'Z1','zona_nombre':'Z1',
                        'duracion_min':enf_min,'repeticiones':1,'pausa_min':0,'pausa_activa':False,
                        'hr_min':hr1,'hr_max':hr2,'watts_min':w1,'watts_max':w2,
                    })
                    dur_min = params['dur_total_estimada'] or dur_min
                    # IF aproximado por zona para estimar TSS de la sesión completa
                    IF_ZONA = {'Z1':0.65,'Z2':0.80,'Z3':0.88,'Z4':0.95,'Z5':1.02,'Z6':1.10}
                    if_aprox = IF_ZONA.get(zona_principal, 0.80)
                    tss_est = round(if_aprox**2 * (dur_min/60) * 100)
        except Exception:
            # Rollback defensivo: calcular_nivel_carga (noah_nivel_carga.py)
            # recibe la misma conexión y puede ejecutar consultas propias —
            # si falla a mitad de una transacción, hay que limpiar el estado
            # antes de seguir usando `conn` más abajo en esta función.
            conn.rollback()
            bloques_generados = None  # Fallback abajo

        # ── Fallback: un solo bloque simple (comportamiento original) ─────────
        if not bloques_generados:
            IF_MAP = {'aerobico':0.75,'long':0.78,'ftp':0.95,'vo2':1.02,'neuro':0.80,'recuperacion':0.60}
            if_val = IF_MAP.get(tipo, 0.75)
            tss_est = round(if_val**2 * (dur_min/60) * 100)

            NOMBRES = {
                'aerobico'    : f"Aeróbico Z1-Z2 {dur_min}'",
                'long'        : f"Fondo largo Z1-Z2 {dur_min}'",
                'ftp'         : f"FTP / Umbral {dur_min}'",
                'vo2'         : f"VO2max {dur_min}'",
                'neuro'       : f"Neuromuscular {dur_min}'",
                'recuperacion': f"Recuperación activa {dur_min}'",
            }
            if not nombre:
                nombre = NOMBRES.get(tipo, f"Sesión {dur_min}'")

            ZONA_MAP = {
                'aerobico'    : ('Z1-Z2', 0.75, 0.87),
                'long'        : ('Z1-Z2', 0.75, 0.87),
                'ftp'         : ('Z4',    0.93, 1.00),
                'vo2'         : ('Z5',    1.00, 1.06),
                'neuro'       : ('Z6',    1.06, 1.20),
                'recuperacion': ('Z1',    0.68, 0.75),
            }
            lthr_ref = lthr_bike if sport == 'cycling' else lthr
            zona, hr_f_min, hr_f_max = ZONA_MAP.get(tipo, ('Z1-Z2', 0.75, 0.87))
            if sport == 'cycling' and ftp_watts:
                bloques_generados = [{
                    'nombre': nombre, 'zona': zona, 'zona_nombre': zona,
                    'duracion_min': dur_min, 'repeticiones': 1, 'pausa_min': 0, 'pausa_activa': True,
                    'hr_min': None, 'hr_max': None,
                    'watts_min': round(ftp_watts*hr_f_min), 'watts_max': round(ftp_watts*hr_f_max),
                }]
            else:
                bloques_generados = [{
                    'nombre': nombre, 'zona': zona, 'zona_nombre': zona,
                    'duracion_min': dur_min, 'repeticiones': 1, 'pausa_min': 0, 'pausa_activa': True,
                    'hr_min': round(lthr_ref*hr_f_min), 'hr_max': round(lthr_ref*hr_f_max),
                    'watts_min': None, 'watts_max': None,
                }]

        if tss_est is None:
            tss_est = round(0.80**2 * (dur_min/60) * 100)

        # Calcular nutrición para la sesión recién creada — misma fórmula que
        # se usa al editar, sin importar que sea creación manual.
        nutricion_desc = ''
        try:
            from noah_nutricion_completa import construir_recomendacion_durante
            ZONA_IF = {'Z1':0.65,'Z2':0.80,'Z3':0.88,'Z4':0.95,'Z5':1.02,'Z6':1.10,
                       'BZ1':0.55,'BZ2':0.80,'BZ3':0.88,'BZ4':0.95,'BZ5':1.05,'BZ6':1.20,'BZ7':1.40}
            dur_total_real = 0.0
            suma_if_x_dur = 0.0
            for b in bloques_generados:
                reps  = b.get('repeticiones', 1) or 1
                dur   = b.get('duracion_min', 0) or 0
                pausa = b.get('pausa_min', 0) or 0
                n_pausas = max(0, reps - 1)
                dt = dur*reps + pausa*n_pausas
                dur_total_real += dt
                suma_if_x_dur += ZONA_IF.get(b.get('zona','Z2'), 0.75) * dt
            if_prom = (suma_if_x_dur/dur_total_real) if dur_total_real > 0 else 0.75

            peso_row2 = conn.execute("SELECT peso_kg FROM atletas WHERE id=%s", (atleta_id,)).fetchone()
            peso_kg2 = peso_row2[0] if peso_row2 and peso_row2[0] else None

            rec = construir_recomendacion_durante(deporte=sport, dur_min=dur_total_real,
                                                   intensidad_if=if_prom, peso_kg=peso_kg2)
            nutricion_desc = f" | Nutrición: {rec.get('texto_corto','')}"
        except Exception:
            # Rollback defensivo: la conexión sigue usándose justo después
            # (MAX(sesion_num) e INSERT de bloques) — si el SELECT de peso_kg
            # falló a mitad de transacción, hay que limpiar antes de seguir.
            conn.rollback()

        max_num = conn.execute(
            "SELECT MAX(sesion_num) FROM prescripcion_bloques WHERE prescripcion_id=%s", (presc_id,)
        ).fetchone()[0] or 0
        ses_num = max_num + 1

        for i, b in enumerate(bloques_generados, start=1):
            conn.execute("""
                INSERT INTO prescripcion_bloques
                (prescripcion_id, atleta_id, sesion_num, bloque_num,
                 nombre, zona, zona_nombre, duracion_min, repeticiones,
                 pausa_min, pausa_activa, hr_min, hr_max, watts_min, watts_max,
                 sport, sesion_sport, sesion_nombre, sesion_fecha,
                 sesion_duracion, sesion_tss, sesion_descripcion)
                VALUES (%s,%s,%s,%s, %s,%s,%s, %s,%s, %s,%s, %s,%s,%s,%s,
                        %s,%s,%s,%s, %s,%s,%s)
            """, (
                presc_id, atleta_id, ses_num, i,
                b['nombre'], b['zona'], b['zona_nombre'], b['duracion_min'], b['repeticiones'],
                b['pausa_min'], int(b['pausa_activa']), b.get('hr_min'), b.get('hr_max'),
                b.get('watts_min'), b.get('watts_max'),
                sport, sport, nombre, fecha,
                dur_min, tss_est, nutricion_desc.lstrip(' |')
            ))
        conn.commit()
        conn.close()
        return ok({'agregada':True,'sesion_num':ses_num,'nombre':nombre,'fecha':fecha,
                   'tss':tss_est,'bloques':len(bloques_generados)})
    except Exception as e:
        import traceback
        return error(f'{e} :: {traceback.format_exc()[-300:]}')

# ─── FEEDBACK / APRENDIZAJE NOAH ─────────────────────────────────────────────

@app.route('/api/atletas/<int:atleta_id>/feedback', methods=['GET'])
@requiere_login
def get_feedback(atleta_id):
    """
    Retorna el resumen de lo que NOAH aprendió para este atleta.
    Incluye: cumplimiento por tipo de sesión, impacto HRV, alertas, tendencias.
    """
    try:
        dias = int(request.args.get('dias', 60))
        conn = get_conn()

        # Verificar que existe la tabla — sqlite_master (SQLite) no existe
        # en Postgres, el equivalente es information_schema.tables.
        tbl = conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name='noah_feedback'"
        ).fetchone()
        if not tbl:
            conn.close()
            return ok({'sin_datos': True, 'mensaje': 'Sin historial de feedback todavía. Generá ciclos y el sistema aprenderá.'})

        # Fechas límite calculadas en Python — más simple y legible que
        # traducir date('now', '-N days') a sintaxis de INTERVAL de Postgres
        # en cada consulta, y evita cualquier diferencia de comportamiento
        # entre ambos motores en el cálculo de fechas relativas.
        fecha_lim_dias  = str(date.today() - timedelta(days=dias))
        fecha_lim_30    = str(date.today() - timedelta(days=30))
        fecha_lim_14    = str(date.today() - timedelta(days=14))

        # Resumen general
        resumen = conn.execute("""
            SELECT resultado, COUNT(*) as n,
                   ROUND(AVG(cumplimiento_tss)::numeric,3) as cumpl_avg,
                   ROUND(AVG(impacto_hrv)::numeric,2) as hrv_avg,
                   ROUND(AVG(consistencia_series)::numeric,3) as cons_avg
            FROM noah_feedback
            WHERE atleta_id=%s AND fecha >= %s
            GROUP BY resultado ORDER BY n DESC
        """, (atleta_id, fecha_lim_dias)).fetchall()

        # Por deporte
        por_deporte = conn.execute("""
            SELECT sport, resultado, COUNT(*) as n,
                   ROUND(AVG(cumplimiento_tss)::numeric,3) as cumpl_avg
            FROM noah_feedback
            WHERE atleta_id=%s AND fecha >= %s
            GROUP BY sport, resultado ORDER BY sport, n DESC
        """, (atleta_id, fecha_lim_dias)).fetchall()

        # Últimas 10 sesiones
        ultimas = conn.execute("""
            SELECT fecha, sport, sesion_nombre_presc, tss_planificado,
                   tss_real, cumplimiento_tss, impacto_hrv,
                   consistencia_series, resultado
            FROM noah_feedback
            WHERE atleta_id=%s
            ORDER BY fecha DESC LIMIT 10
        """, (atleta_id,)).fetchall()

        # Alertas
        alertas = []
        sobrecargas = conn.execute("""
            SELECT COUNT(*) FROM noah_feedback
            WHERE atleta_id=%s AND resultado='sobrecarga'
            AND fecha >= %s
        """, (atleta_id, fecha_lim_30)).fetchone()[0]
        if sobrecargas >= 2:
            alertas.append({'tipo':'advertencia','msg':f'{sobrecargas} sobrecargas en 30 días — el atleta hace más de lo prescripto'})

        hrv_neg = conn.execute("""
            SELECT COUNT(*) FROM noah_feedback
            WHERE atleta_id=%s AND impacto_hrv < -3
            AND fecha >= %s
        """, (atleta_id, fecha_lim_30)).fetchone()[0]
        if hrv_neg >= 3:
            alertas.append({'tipo':'alerta','msg':f'{hrv_neg} sesiones con HRV negativo en 30 días — posible acumulación de fatiga'})

        incompletas = conn.execute("""
            SELECT COUNT(*) FROM noah_feedback
            WHERE atleta_id=%s AND resultado='incompleta'
            AND fecha >= %s
        """, (atleta_id, fecha_lim_14)).fetchone()[0]
        if incompletas >= 2:
            alertas.append({'tipo':'advertencia','msg':f'{incompletas} sesiones incompletas en 14 días — revisar carga o disponibilidad'})

        # Patrón de absorción
        absorcion = conn.execute("""
            SELECT ROUND(AVG(CASE WHEN resultado IN ('optima','buena') THEN 1.0 ELSE 0.0 END)::numeric*100,1)
            FROM noah_feedback WHERE atleta_id=%s
            AND fecha >= %s
        """, (atleta_id, fecha_lim_30)).fetchone()[0]

        conn.close()

        return ok({
            'resumen'    : [dict(zip(['resultado','n','cumpl_avg','hrv_avg','cons_avg'], r)) for r in resumen],
            'por_deporte': [dict(zip(['sport','resultado','n','cumpl_avg'], r)) for r in por_deporte],
            'ultimas'    : [dict(zip(['fecha','sport','nombre','tss_plan','tss_real',
                                      'cumplimiento','impacto_hrv','consistencia','resultado'], r))
                            for r in ultimas],
            'alertas'    : alertas,
            'absorcion_pct': absorcion,
            'dias'       : dias,
        })
    except Exception as e:
        return error(str(e))


# ─── DISPONIBILIDAD DEL ATLETA ────────────────────────────────────────────────

@app.route('/api/atletas/<int:atleta_id>/perfil_macro', methods=['GET'])
@requiere_login
def get_perfil_macro(atleta_id):
    """Retorna el perfil macro activo con disponibilidad incluida."""
    conn = get_conn()
    row = conn.execute(
        'SELECT datos_json FROM perfiles_macro WHERE atleta_id=%s AND activo=1',
        (atleta_id,)
    ).fetchone()
    conn.close()
    if not row:
        return ok({'disponibilidad': None})
    datos = json.loads(row[0])
    return ok({'disponibilidad': datos.get('disponibilidad'), 'perfil': datos})


@app.route('/api/atletas/<int:atleta_id>/disponibilidad', methods=['POST'])
@requiere_login
def guardar_disponibilidad(atleta_id):
    """Guarda la disponibilidad del atleta dentro del perfil macro activo."""
    try:
        d = request.get_json(force=True, silent=True) or {}
        conn = get_conn()
        row = conn.execute(
            'SELECT id, datos_json FROM perfiles_macro WHERE atleta_id=%s AND activo=1',
            (atleta_id,)
        ).fetchone()
        disponibilidad = {
            'sesiones_semana_min': int(d.get('sesiones_semana_min', 3)),
            'sesiones_semana_max': int(d.get('sesiones_semana_max', 5)),
            'dur_max_semana_min' : int(d.get('dur_max_semana_min', 60)),
            'dur_max_finde_min'  : int(d.get('dur_max_finde_min', 120)),
        }
        if row:
            datos = json.loads(row[1])
            datos['disponibilidad'] = disponibilidad
            conn.execute('UPDATE perfiles_macro SET datos_json=%s WHERE id=%s',
                         (json.dumps(datos), row[0]))
        else:
            datos = {'disponibilidad': disponibilidad}
            conn.execute(
                'INSERT INTO perfiles_macro (atleta_id, fecha_generado, datos_json, activo) VALUES (%s,%s,%s,1)',
                (atleta_id, str(date.today()), json.dumps(datos))
            )
        conn.commit()
        conn.close()
        return ok({'guardado': True, 'disponibilidad': disponibilidad})
    except Exception as e:
        return error(str(e))


# ─── NOA HEALTH SCORE ─────────────────────────────────────────────────────────

@app.route('/api/atletas/<int:atleta_id>/health', methods=['GET'])
@requiere_login
def get_health(atleta_id):
    """NOA Health Score del atleta."""
    try:
        from noa_health import NOAHealth
        db = NOADatabase(DB_PATH)
        atleta = db.get_atleta(atleta_id)
        edad = atleta.get('edad') or 40

        health = NOAHealth(atleta_id, DB_PATH, edad=edad, es_deportista=True)
        score  = health.calcular_noa_score()
        health.close()
        return ok(score)
    except Exception as e:
        return ok({'error': str(e), 'noa_score': 0, 'noa_score_nivel': 'sin_datos'})


# ─── GRAFICOS ─────────────────────────────────────────────────────────────────

@app.route('/api/atletas/<int:atleta_id>/graficos', methods=['GET'])
@requiere_login
def get_graficos(atleta_id):
    """Datos para los gráficos del dashboard."""
    dias = int(request.args.get('dias', 180))
    db   = NOADatabase(DB_PATH)
    data = db.get_datos_graficos(atleta_id, dias=dias)
    return ok(data)


# ─── SESIONES ─────────────────────────────────────────────────────────────────

@app.route('/api/atletas/<int:atleta_id>/sesiones', methods=['GET'])
@requiere_login
def get_sesiones(atleta_id):
    """Últimas N sesiones del atleta."""
    limit = int(request.args.get('limit', 20))
    conn  = get_conn()
    rows  = conn.execute('''
        SELECT fecha, sport, distance_km, duration_min,
               hr_avg, tss_total, ctl, atl, tsb, tipo_sesion
        FROM sesiones WHERE atleta_id=%s
        ORDER BY fecha DESC LIMIT %s
    ''', (atleta_id, limit)).fetchall()
    conn.close()

    sesiones = [{
        'fecha'     : r[0], 'sport': r[1],
        'distance'  : r[2], 'duration': r[3],
        'hr_avg'    : r[4], 'tss': r[5],
        'ctl'       : r[6], 'atl': r[7], 'tsb': r[8],
        'tipo'      : r[9],
    } for r in rows]

    return ok(sesiones)


# ─── DIAGNÓSTICO NOA ─────────────────────────────────────────────────────────

@app.route('/api/atletas/<int:atleta_id>/diagnostico', methods=['GET'])
@requiere_login
def get_diagnostico(atleta_id):
    """Diagnostico de distribucion de zonas y proyeccion CTL."""
    try:
        from noa_analisis import NOAAnalisis
        analisis = NOAAnalisis(atleta_id=atleta_id, db_path=DB_PATH)
        d = analisis.generar_diagnostico()
        analisis.close()
        return ok(d)
    except Exception as e:
        return ok({'error': str(e), 'score_general': 0, 'color': 'sin_datos',
                   'resumen_coach': 'Sin datos suficientes.',
                   'resumen_atleta': 'Seguimos recopilando datos.',
                   'alertas': [], 'distribucion': {}, 'proyeccion': {}})



# ─── ZONAS POR DEPORTE ────────────────────────────────────────────────────────

@app.route('/api/atletas/<int:atleta_id>/zonas/<deporte>', methods=['GET'])
@requiere_login
def get_zonas_deporte(atleta_id, deporte):
    """
    Zonas por deporte con ajuste inteligente según estado del atleta.
    Considera TSB, CTL y fase para dar contexto adaptativo.
    """
    from noa_deportes import ZonasRunning, ZonasCycling, ZonasSwimming
    db    = NOADatabase(DB_PATH)
    atleta = db.get_atleta(atleta_id)
    if not atleta:
        return error('Atleta no encontrado', 404)

    lthr_run  = atleta.get('lthr_run',  162)
    lthr_bike = atleta.get('lthr_bike', 150)
    hr_max    = atleta.get('hr_max',    190)
    peso      = atleta.get('peso_kg',    75) or 75
    ftp       = atleta.get('ftp_bike')
    conn      = get_conn()

    # ── Estado actual del atleta (TSB, CTL) ──────────────────────────────────
    try:
        from noa_pmf import calcular_ctl_atl_tsb_atleta
        estado = calcular_ctl_atl_tsb_atleta(conn, atleta_id)
        tsb = round(estado.get('tsb', 0), 1)
        ctl = round(estado.get('ctl', 0), 1)
    except Exception:
        tsb, ctl = 0.0, 0.0

    # ── Recomendación adaptativa según TSB ───────────────────────────────────
    # TSB > 10: forma óptima → zonas altas OK
    # TSB 0-10: carga normal → todas las zonas disponibles
    # TSB -10 a -20: carga moderada → cuidado con Z5-Z6
    # TSB < -20: fatiga alta → solo Z1-Z2-Z3
    if tsb > 10:
        recomendacion = {'nivel': 'optimo',   'color': '#10B981',
                         'msg': f'Forma óptima (TSB {tsb}) — todas las zonas disponibles.',
                         'zonas_ok': ['Z1','Z2','Z3','Z4','Z5','Z6','Z7']}
    elif tsb >= -10:
        recomendacion = {'nivel': 'normal',   'color': '#6366F1',
                         'msg': f'Carga normal (TSB {tsb}) — entrenamiento estándar.',
                         'zonas_ok': ['Z1','Z2','Z3','Z4','Z5','Z6','Z7']}
    elif tsb >= -20:
        recomendacion = {'nivel': 'carga',    'color': '#F59E0B',
                         'msg': f'En carga (TSB {tsb}) — reducir volumen en Z5-Z6.',
                         'zonas_ok': ['Z1','Z2','Z3','Z4']}
    else:
        recomendacion = {'nivel': 'fatiga',   'color': '#EF4444',
                         'msg': f'Alta fatiga (TSB {tsb}) — priorizar recuperación Z1-Z2.',
                         'zonas_ok': ['Z1','Z2','Z3']}

    if deporte == 'running':
        pace_z2 = 5.55
        try:
            rp = conn.execute("""
                SELECT AVG(pace) FROM sesiones
                WHERE atleta_id=%s AND hr_avg BETWEEN %s AND %s
                AND pace > 4.0 AND pace < 7.5 AND duration_min > 20
                ORDER BY fecha DESC LIMIT 20
            """, (atleta_id, round(lthr_run*0.75), round(lthr_run*0.87))).fetchone()
            if rp and rp[0]: pace_z2 = round(float(rp[0]), 2)
        except Exception:
            conn.rollback()  # defensivo — la conexión se cierra justo después
        z = ZonasRunning(lthr=lthr_run, hr_max=hr_max, pace_z2_real=pace_z2, peso_kg=peso)
        conn.close()
        return ok({'deporte':'running','referencia':lthr_run,
                   'zonas':z.calcular(), 'tsb':tsb, 'ctl':ctl,
                   'recomendacion':recomendacion})

    elif deporte == 'cycling':
        if ftp:
            z = ZonasCycling(ftp=ftp, lthr_bike=lthr_bike, hr_max=hr_max, peso_kg=peso)
        else:
            z = ZonasCycling.desde_lthr(lthr_bike=lthr_bike, hr_max=hr_max, peso_kg=peso)
        conn.close()
        return ok({'deporte':'cycling','ftp':z.ftp,'w_kg':z.w_kg,
                   'zonas':z.calcular(), 'tsb':tsb, 'ctl':ctl,
                   'recomendacion':recomendacion})

    elif deporte == 'swimming':
        css       = atleta.get('css_100m', 1.75)
        lthr_swim = atleta.get('lthr_swim') or round(lthr_run * 0.92)
        z = ZonasSwimming(css_100m=css, lthr_swim=lthr_swim, hr_max=hr_max)
        conn.close()
        return ok({'deporte':'swimming','css':css,
                   'zonas':z.calcular(), 'tsb':tsb, 'ctl':ctl,
                   'recomendacion':recomendacion})

    conn.close()
    return error(f'Deporte no soportado: {deporte}')

# ─── HEALTH CHECK ─────────────────────────────────────────────────────────────

@app.route('/api/ping', methods=['GET'])
def ping():
    return ok({'status': 'NOA API running', 'date': str(date.today())})


# ─── MAIN ─────────────────────────────────────────────────────────────────────


@app.route('/api/atletas/<int:atleta_id>/sesion_real', methods=['GET'])
@requiere_login
def get_sesion_real(atleta_id):
    fecha = request.args.get('fecha', str(date.today()))
    sport = request.args.get('sport', 'running')
    conn  = get_conn()
    row   = conn.execute(
        "SELECT id, fecha, sport, distance_km, duration_min, hr_avg, hr_max, "
        "pace, tss_total, np_watts, potencia_media, swolf, paladas, tipo_sesion, fuente "
        "FROM sesiones WHERE atleta_id=%s AND fecha=%s AND sport=%s "
        "AND (fuente IS NULL OR fuente IN ('garmin_csv','garmin_auto','garmin_api','manual')) "
        "ORDER BY id DESC LIMIT 1",
        (atleta_id, fecha, sport)
    ).fetchone()
    conn.close()
    if not row:
        return ok({'sesion_real': None})
    return ok({'sesion_real': {
        'id': row[0], 'fecha': row[1], 'sport': row[2],
        'distance_km': row[3], 'duration_min': row[4],
        'hr_avg': row[5], 'hr_max': row[6], 'pace': row[7],
        'tss_total': row[8], 'np_watts': row[9],
        'potencia_media': row[10], 'swolf': row[11],
        'paladas': row[12], 'tipo_sesion': row[13], 'fuente': row[14],
    }})


@app.route('/api/atletas/<int:atleta_id>/sincronizar', methods=['POST'])
@requiere_login
def sincronizar_garmin_endpoint(atleta_id):
    """
    Sincroniza datos de Garmin y recalcula todos los modelos derivados.

    modo='bio'       → baja biomarcadores + recalcula HANNA LIFE
    modo='actividad' → baja actividades  + recalcula PMC
    modo='todo'      → bio + actividad   + recalcula todo
    """
    import subprocess, sys
    from pathlib import Path
    datos  = request.json or {}
    modo   = datos.get('modo', 'todo')
    fecha  = datos.get('fecha', None)  # None = calcular dias pendientes
    base   = Path(__file__).parent

    # Calcular fechas pendientes desde el ultimo dato hasta hoy
    from datetime import timedelta
    def _fechas_pendientes(atleta_id, tipo):
        conn_t = get_conn()
        try:
            if tipo == 'bio':
                row = conn_t.execute(
                    "SELECT fecha FROM sleep_hrv WHERE atleta_id=%s AND (sleep_h IS NOT NULL OR body_battery IS NOT NULL) ORDER BY fecha DESC LIMIT 1",
                    (atleta_id,)).fetchone()
            else:
                row = conn_t.execute(
                    "SELECT fecha FROM sesiones WHERE atleta_id=%s AND tss_total>0 AND (fuente IS NULL OR fuente NOT IN ('prescripcion','simulacion','generada')) ORDER BY fecha DESC LIMIT 1",
                    (atleta_id,)).fetchone()
        finally:
            conn_t.close()
        from datetime import datetime
        ultima = str(row[0]) if row else str(date.today() - timedelta(days=3))
        try:
            d = datetime.strptime(ultima, '%Y-%m-%d').date() + timedelta(days=1)
        except:
            d = date.today() - timedelta(days=3)
        fechas = []
        while d <= date.today():
            fechas.append(str(d))
            d += timedelta(days=1)
        return fechas if fechas else [str(date.today())]
    script = base / 'sincronizar_garmin.py'
    if not script.exists():
        return error('Script sincronizar_garmin.py no encontrado')

    resp   = {'exito': False, 'modo': modo, 'pasos': []}
    output_total = []

    def run(args, timeout=90):
        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
            output_total.append((args[-1] if args else '?', r.stdout[-500:]+r.stderr[-200:]))
            return r.returncode == 0
        except subprocess.TimeoutExpired:
            output_total.append(('timeout', str(args)))
            return False
        except Exception as e:
            output_total.append(('error', str(e)))
            return False

    # ── 1. Bajar datos de Garmin ──────────────────────────────────────────
    if modo in ('bio', 'todo'):
        fechas_bio = [fecha] if fecha else _fechas_pendientes(atleta_id, 'bio')
        ok_garmin = False
        for f_bio in fechas_bio:
            if run([sys.executable, str(script),
                    '--atleta', str(atleta_id), '--modo', 'bio', '--fecha', f_bio]):
                ok_garmin = True
        resp['pasos'].append({'paso': 'garmin_bio', 'ok': ok_garmin})

        # ── 2. Recalcular HANNA LIFE ──────────────────────────────────────
        hl_script = base / 'noah_hanna_life.py'
        if hl_script.exists() and ok_garmin:
            ok_hl = run([sys.executable, str(hl_script),
                         '--atleta', str(atleta_id), '--todo'])
            resp['pasos'].append({'paso': 'hanna_life', 'ok': ok_hl})
        elif not hl_script.exists():
            resp['pasos'].append({'paso': 'hanna_life', 'ok': False, 'msg': 'script no encontrado'})

    if modo in ('actividad', 'todo'):
        fechas_act = [fecha] if fecha else _fechas_pendientes(atleta_id, 'actividad')
        ok_act = False
        for f_act in fechas_act:
            if run([sys.executable, str(script),
                    '--atleta', str(atleta_id), '--modo', 'actividad', '--fecha', f_act]):
                ok_act = True
        resp['pasos'].append({'paso': 'garmin_actividad', 'ok': ok_act})

        # ── 3. Recalcular PMC (CTL/ATL/TSB) ──────────────────────────────
        pmc_script = base / 'noah_pmc.py'
        if pmc_script.exists() and ok_act:
            ok_pmc = run([sys.executable, str(pmc_script),
                          '--atleta', str(atleta_id), '--db', 'noa.db'])
            resp['pasos'].append({'paso': 'pmc', 'ok': ok_pmc})

    resp['exito'] = any(p['ok'] for p in resp['pasos'])
    resp['output'] = str(output_total)[-1000:]

    # ── 4. Leer datos frescos para devolver al dashboard ─────────────────
    conn2 = get_conn()
    try:
        if modo in ('bio', 'todo'):
            row_bio = conn2.execute("""
                SELECT sleep_h, hr_reposo, body_battery, stress_avg,
                       hrv_rmssd, hrv_estimado_valor, hrv_flag, hanna_life, hanna_nivel
                FROM sleep_hrv WHERE atleta_id=%s AND fecha=%s
                ORDER BY id DESC LIMIT 1
            """, (atleta_id, fecha)).fetchone()
            if not row_bio:
                # Buscar el más reciente si no hay de hoy
                row_bio = conn2.execute("""
                    SELECT sleep_h, hr_reposo, body_battery, stress_avg,
                           hrv_rmssd, hrv_estimado_valor, hrv_flag, hanna_life, hanna_nivel
                    FROM sleep_hrv WHERE atleta_id=%s
                    ORDER BY fecha DESC, id DESC LIMIT 1
                """, (atleta_id,)).fetchone()
            if row_bio:
                hrv_real = row_bio[4]
                hrv_est  = row_bio[5]
                resp.update({
                    'sleep_h':      row_bio[0],
                    'hr_reposo':    row_bio[1],
                    'body_battery': row_bio[2],
                    'stress_avg':   row_bio[3],
                    'hrv_ms':       hrv_real or hrv_est,
                    'hrv_estimado': hrv_real is None and hrv_est is not None,
                    'hrv_flag':     row_bio[6],
                    'hanna_life':   row_bio[7],
                    'hanna_nivel':  row_bio[8],
                })
    finally:
        conn2.close()

    # ── 5. Log ────────────────────────────────────────────────────────────
    try:
        conn3 = get_conn()
        # SERIAL en vez de INTEGER PRIMARY KEY — el INSERT de abajo no
        # especifica id, así que la tabla necesita autogenerar el valor
        # (en SQLite, INTEGER PRIMARY KEY ya autoincrementaba solo; en
        # Postgres hace falta SERIAL para el mismo comportamiento).
        conn3.execute("""CREATE TABLE IF NOT EXISTS sync_log
            (id SERIAL PRIMARY KEY, atleta_id INTEGER, ts TEXT,
             modo TEXT, status TEXT, detalle TEXT)""")
        conn3.execute(
            'INSERT INTO sync_log (atleta_id, ts, modo, status, detalle) VALUES (%s,%s,%s,%s,%s)',
            (atleta_id, datetime.now().isoformat(), modo,
             'ok' if resp['exito'] else 'error', str(resp['pasos']))
        )
        conn3.commit()
        conn3.close()
    except Exception:
        pass

    return ok(_limpiar_nan(resp))


def _limpiar_nan(obj):
    """Reemplaza NaN/Inf por None para JSON válido."""
    import math
    if isinstance(obj, dict):
        return {k: _limpiar_nan(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_limpiar_nan(v) for v in obj]
    elif isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


@app.route('/api/atletas/<int:atleta_id>/noah_intel', methods=['GET'])
@requiere_login
def get_noah_intel(atleta_id):
    """Análisis ML de NOAH — usa modelo guardado para respuesta rápida."""
    conn = get_conn()
    try:
        from noah_ml import NOAHMind
        from noa_db import NOADatabase
        db     = NOADatabase()
        estado = db.get_estado_actual(atleta_id)

        # Cargar modelo desde cache o disco (NUNCA reentrena aquí)
        mind = _get_mind(conn, atleta_id)
        if mind is None:
            conn.close()
            return ok({'error': 'Modelo no entrenado — usar /entrenar primero',
                       'entrenado': False})

        analisis = mind.analisis_completo(estado)
        tss_rec  = mind.tss_recomendado(estado)

        # Evaluación de impacto para el TSS planificado hoy
        tss_hoy = request.args.get('tss', None)
        intensa  = request.args.get('intensa', '0') == '1'
        evaluacion_carga = None
        if mind.modelo_impacto.entrenado:
            tss_eval = float(tss_hoy) if tss_hoy else tss_rec.get('tss_recomendado', 50)
            evaluacion_carga = mind.modelo_impacto.evaluar_sesion(
                estado, tss_eval, sesion_intensa=intensa)

        conn.close()
        resultado = _limpiar_nan({
            'adaptacion':         analisis.get('adaptacion', {}),
            'sobreentrenamiento': analisis.get('sobreentrenamiento', {}),
            'tss_recomendado':    tss_rec,
            'cumplimiento':       analisis.get('cumplimiento', {}),
            'respuesta_carga':    analisis.get('respuesta_carga', {}),
            'impacto_respuesta':  analisis.get('impacto_respuesta', {}),
            'evaluacion_carga':   evaluacion_carga,
        })
        return ok(resultado)
    except ImportError:
        conn.close()
        return ok({'error': 'ML no disponible — instalar scikit-learn y joblib'})
    except Exception as e:
        conn.close()
        return error(str(e))


@app.route('/api/atletas/<int:atleta_id>/noah_intel/entrenar', methods=['POST'])
@requiere_login
def entrenar_noah_intel(atleta_id):
    # Limpiar cache para forzar recarga del modelo nuevo
    _ML_CACHE.pop(atleta_id, None)
    """Re-entrena el modelo ML del atleta (operación lenta — correr manualmente)."""
    conn = get_conn()
    try:
        from noah_ml import NOAHMind
        mind = NOAHMind(conn, atleta_id)
        mind.preparar_datos()
        resultados = mind.entrenar()  # guarda en disco automáticamente
        conn.close()
        return ok({'entrenado': True, 'resultados': resultados})
    except Exception as e:
        conn.close()
        return error(str(e))


@app.route('/api/atletas/<int:atleta_id>/periodizacion', methods=['GET'])
@requiere_login
def get_periodizacion(atleta_id):
    """
    Retorna la curva CTL proyectada hasta la carrera con fases A/T/R/Taper.
    Incluye CTL histórico real + proyección futura.
    """
    import numpy as np
    from datetime import date, timedelta

    conn = get_conn()
    try:
        # Perfil del macrociclo
        row = conn.execute(
            'SELECT datos_json FROM perfiles_macro WHERE atleta_id=%s AND activo=1',
            (atleta_id,)
        ).fetchone()
        if not row:
            return error('Sin perfil de macrociclo')

        import json
        perfil = json.loads(row[0])
        fecha_carrera = perfil.get('carrera_fecha', '')
        if not fecha_carrera:
            return error('Sin fecha de carrera en perfil')

        carrera = date.fromisoformat(fecha_carrera)
        hoy     = date.today()

        # CTL histórico real (últimos 90 días)
        df_ctl = conn.execute('''
            SELECT fecha, SUM(tss_total) as tss
            FROM sesiones WHERE atleta_id=%s AND tss_total > 0
            GROUP BY fecha ORDER BY fecha
        ''', (atleta_id,)).fetchall()

        # Calcular CTL día a día
        tss_dict = {r[0]: float(r[1]) for r in df_ctl}
        a_ctl = 2/43
        ctl_actual = 0
        fecha_iter = hoy - timedelta(days=180)
        ctl_hist = []

        while fecha_iter <= hoy:
            fs = str(fecha_iter)
            tss = tss_dict.get(fs, 0)
            ctl_actual = ctl_actual*(1-a_ctl) + tss*a_ctl
            ctl_hist.append({'fecha': fs, 'ctl': round(ctl_actual, 1), 'tipo': 'real'})
            fecha_iter += timedelta(days=1)

        # Fases (con nombres Navarro)
        FASE_NOMBRES = {'F1': 'A', 'F2': 'T', 'F3': 'R', 'TAPER': 'Taper'}
        FASE_COLORES = {'A': '#6366f1', 'T': '#f59e0b', 'R': '#ef4444', 'Taper': '#22c55e'}

        taper = perfil.get('taper_semanas', 2)
        f3    = perfil.get('f3_semanas', 4)
        f2    = perfil.get('f2_semanas', 6)
        f1    = perfil.get('f1_semanas', 11)

        def get_fase(semanas_a_carrera):
            if semanas_a_carrera <= taper:              return 'Taper'
            if semanas_a_carrera <= taper+f3:           return 'R'
            if semanas_a_carrera <= taper+f3+f2:        return 'T'
            return 'A'

        # TSS semanal objetivo por fase
        tss_por_fase = {
            'A':     perfil.get('tss_semana_f1_max', 300),
            'T':     perfil.get('tss_semana_f2_max', 350),
            'R':     perfil.get('tss_semana_f3_max', perfil.get('tss_semana_f2_max', 350)),
            'Taper': perfil.get('tss_semana_f1_max', 300) * 0.5,
        }

        # Proyección futura hasta la carrera
        ctl_proy = ctl_actual
        ctl_proyectado = []
        fecha_iter = hoy + timedelta(days=1)

        while fecha_iter <= carrera:
            semanas = (carrera - fecha_iter).days / 7
            fase = get_fase(semanas)
            tss_semana = tss_por_fase.get(fase, 200)
            tss_dia = tss_semana / 7
            ctl_proy = ctl_proy*(1-a_ctl) + tss_dia*a_ctl
            ctl_proyectado.append({
                'fecha': str(fecha_iter),
                'ctl':   round(ctl_proy, 1),
                'fase':  fase,
                'tipo':  'proyectado'
            })
            fecha_iter += timedelta(days=1)

        # Bloques de fases para colorear el gráfico
        fases_bloques = []
        fase_actual_bloque = None
        for punto in ctl_proyectado:
            if punto['fase'] != fase_actual_bloque:
                fases_bloques.append({
                    'fase':  punto['fase'],
                    'desde': punto['fecha'],
                    'hasta': punto['fecha'],
                    'color': FASE_COLORES.get(punto['fase'], '#666'),
                })
                fase_actual_bloque = punto['fase']
            else:
                fases_bloques[-1]['hasta'] = punto['fecha']

        conn.close()
        return ok({
            'historico':    ctl_hist[-90:],  # últimos 90 días
            'proyectado':   ctl_proyectado,
            'fases':        fases_bloques,
            'carrera':      {'fecha': fecha_carrera, 'nombre': perfil.get('carrera_nombre','')},
            'ctl_actual':   round(ctl_actual, 1),
            'ctl_objetivo': perfil.get('ctl_objetivo', 80),
        })
    except Exception as e:
        conn.close()
        return error(str(e))



@app.route('/api/atletas/<int:atleta_id>/ultima_actividad', methods=['GET'])
@requiere_login
def get_ultima_actividad(atleta_id):
    """Retorna la última actividad real del atleta con detalle."""
    conn = get_conn()
    row = conn.execute('''
        SELECT id, fecha, sport, distance_km, duration_min, hr_avg, hr_max,
               pace, tss_total, np_watts, fuente, tipo_sesion
        FROM sesiones
        WHERE atleta_id=%s AND tss_total > 0
        AND (fuente IS NULL OR fuente NOT IN ('prescripcion','simulacion','generada'))
        ORDER BY fecha DESC LIMIT 1
    ''', (atleta_id,)).fetchone()
    conn.close()
    if not row:
        return ok({'actividad': None})
    cols = ['id','fecha','sport','distance_km','duration_min','hr_avg','hr_max',
            'pace','tss_total','np_watts','fuente','tipo_sesion']
    return ok({'actividad': dict(zip(cols, row))})


@app.route('/api/atletas/<int:atleta_id>/sync_status', methods=['GET'])
@requiere_login
def get_sync_status(atleta_id):
    conn = get_conn()
    from datetime import date, datetime
    hoy = str(date.today())
    row_sync = conn.execute(
        "SELECT ts FROM sync_log WHERE atleta_id=%s AND status IN ('ok','parcial') ORDER BY ts DESC LIMIT 1",
        (atleta_id,)).fetchone()
    row_bio = conn.execute(
        "SELECT fecha, sleep_h, hr_reposo, body_battery, hrv_rmssd, stress_avg FROM sleep_hrv WHERE atleta_id=%s AND (sleep_h IS NOT NULL OR body_battery IS NOT NULL) ORDER BY fecha DESC LIMIT 1",
        (atleta_id,)).fetchone()
    row_act = conn.execute(
        "SELECT fecha FROM sesiones WHERE atleta_id=%s AND tss_total > 0 AND (fuente IS NULL OR fuente NOT IN ('prescripcion','simulacion','generada')) ORDER BY fecha DESC LIMIT 1",
        (atleta_id,)).fetchone()
    horas_sin_sync = 999
    ultima_sync_ts = None
    if row_sync:
        try:
            ts = datetime.fromisoformat(str(row_sync[0])[:19])
            horas_sin_sync = (datetime.now() - ts).total_seconds() / 3600
            ultima_sync_ts = str(row_sync[0])[:16]
        except: pass
    fecha_bio = str(row_bio[0]) if row_bio else None
    fecha_act = str(row_act[0]) if row_act else None
    def dias(f):
        if not f: return 999
        try: return (date.today() - date.fromisoformat(f)).days
        except: return 999
    conn.close()
    return ok({
        'ultima_sync': ultima_sync_ts, 'horas_sin_sync': round(horas_sin_sync, 1),
        'alerta': horas_sin_sync > 20,
        'fecha_bio': fecha_bio, 'bio_es_hoy': fecha_bio == hoy, 'bio_dias_atras': dias(fecha_bio),
        'fecha_act': fecha_act, 'act_es_hoy': fecha_act == hoy, 'act_dias_atras': dias(fecha_act),
        'bio_data': {'sleep_h': row_bio[1], 'hr_reposo': row_bio[2], 'body_battery': row_bio[3],
                     'hrv_rmssd': row_bio[4], 'stress_avg': row_bio[5]} if row_bio else None,
    })

@app.route('/api/atletas/<int:atleta_id>/fases', methods=['GET'])
@requiere_login
def get_fases(atleta_id):
    import numpy as np, json, pandas as pd
    from datetime import date, timedelta
    conn = get_conn()
    try:
        # ── Cargar perfil macro (para parámetros de fases) ────────────────────
        row = conn.execute(
            "SELECT datos_json FROM perfiles_macro WHERE atleta_id=%s AND activo=1",
            (atleta_id,)).fetchone()
        perfil = json.loads(row[0]) if row else {}

        # ── Cargar carreras reales de la DB ───────────────────────────────────
        _init_carreras_table(conn)
        carreras_rows = conn.execute(
            "SELECT id, nombre, fecha, prioridad, deporte, ctl_objetivo, estado "
            "FROM carreras WHERE atleta_id=%s AND estado != 'cancelada' "
            "ORDER BY fecha ASC", (atleta_id,)).fetchall()
        carreras_db = [dict(zip(['id','nombre','fecha','prioridad','deporte',
                                  'ctl_objetivo','estado'], r))
                       for r in carreras_rows]

        hoy = date.today()

        # Carrera A principal = la ÚLTIMA A del período (ancla del macrociclo)
        # Si hay varias A, tomamos la más lejana — es la principal
        # La primera A puede ser un objetivo intermedio
        carreras_A_futuras = [c for c in carreras_db
                              if c['prioridad']=='A'
                              and date.fromisoformat(c['fecha']) > hoy]
        carrera_A = carreras_A_futuras[-1] if carreras_A_futuras else None

        # Fallback al perfil macro si no hay carrera A en DB
        if not carrera_A and perfil.get('carrera_fecha'):
            carrera_A = {
                'nombre':      perfil.get('carrera_nombre','Carrera A'),
                'fecha':       perfil.get('carrera_fecha'),
                'prioridad':   'A',
                'ctl_objetivo': perfil.get('ctl_objetivo', 60),
            }

        fecha_carrera  = carrera_A['fecha'] if carrera_A else ''
        carrera_nombre = carrera_A['nombre'] if carrera_A else ''

        # ── Rangos de fecha de cada fase (A/T/R/Taper) — calculados ANTES del
        # loop de deportes para poder etiquetar también los días históricos,
        # no solo la proyección futura. Misma fórmula que ya existía, solo
        # se adelanta en el archivo para que esté disponible más temprano.
        taper = perfil.get("taper_semanas", 2)
        f3    = perfil.get("f3_semanas", 4)
        f2    = perfil.get("f2_semanas", 6)
        f1    = perfil.get("f1_semanas", 12)
        fases = []
        if fecha_carrera:
            fc = date.fromisoformat(fecha_carrera)
            fases = [
                {"fase":"A",    "label":"Acumulación",    "color":"#6366F1",
                 "desde":str(fc-timedelta(weeks=taper+f3+f2+f1)), "hasta":str(fc-timedelta(weeks=taper+f3+f2))},
                {"fase":"T",    "label":"Transformación",  "color":"#F59E0B",
                 "desde":str(fc-timedelta(weeks=taper+f3+f2)),    "hasta":str(fc-timedelta(weeks=taper+f3))},
                {"fase":"R",    "label":"Realización",     "color":"#EF4444",
                 "desde":str(fc-timedelta(weeks=taper+f3)),        "hasta":str(fc-timedelta(weeks=taper))},
                {"fase":"Taper","label":"Taper",           "color":"#10B981",
                 "desde":str(fc-timedelta(weeks=taper)),            "hasta":fecha_carrera},
            ]

        def _fase_de_fecha(fecha_str):
            """Devuelve la fase (A/T/R/Taper) a la que pertenece una fecha histórica,
            según los rangos ya calculados arriba. None si está antes de la fase A
            (días muy viejos, anteriores al inicio del macrociclo actual) o si no
            hay carrera definida — esos días simplemente no se pintan."""
            if not fases:
                return None
            for f in fases:
                if f["desde"] <= fecha_str <= f["hasta"]:
                    return f["fase"]
            return None

        TAU = {
            "running":  {"t1": 42, "t2": 7,  "label": "Running",  "color": "#8B5CF6"},
            "cycling":  {"t1": 42, "t2": 7,  "label": "Ciclismo", "color": "#38BDF8"},
            "swimming": {"t1": 28, "t2": 5,  "label": "Natacion",  "color": "#34D399"},
        }

        resultado = {}
        for sport, tau in TAU.items():
            sq = "swimming,swim" if sport == "swimming" else sport
            rows = conn.execute(
                "SELECT fecha, SUM(tss_total) as tss FROM sesiones "
                "WHERE atleta_id=%s AND sport IN ({}) AND tss_total > 0 "
                "GROUP BY fecha ORDER BY fecha".format(
                    ",".join(f"'{s}'" for s in sq.split(","))),
                (atleta_id,)).fetchall()
            if not rows:
                continue

            df = pd.DataFrame(rows, columns=["fecha","tss"])
            df["fecha"] = pd.to_datetime(df["fecha"])
            idx_all = pd.date_range(df["fecha"].min(), pd.Timestamp(hoy), freq="D")
            df_d = df.groupby("fecha")["tss"].sum().reindex(idx_all, fill_value=0)

            t1, t2 = tau["t1"], tau["t2"]
            k1, k2 = 1-np.exp(-1/t1), 1-np.exp(-1/t2)
            d1, d2 = np.exp(-1/t1), np.exp(-1/t2)
            ctl_a = np.zeros(len(df_d))
            atl_a = np.zeros(len(df_d))
            for i in range(len(df_d)):
                tss = float(df_d.iloc[i])
                if i > 0:
                    ctl_a[i] = ctl_a[i-1]*d1 + tss*k1
                    atl_a[i] = atl_a[i-1]*d2 + tss*k2
                else:
                    ctl_a[i] = tss*k1
                    atl_a[i] = tss*k2

            n = min(90, len(ctl_a))
            hist = [{"f": str(idx_all[-n+i].date()), "ctl": round(float(ctl_a[-n+i]),1),
                     "atl": round(float(atl_a[-n+i]),1), "tsb": round(float(ctl_a[-n+i]-atl_a[-n+i]),1),
                     "fase": _fase_de_fecha(str(idx_all[-n+i].date()))}
                    for i in range(n)]

            ctl_now = float(ctl_a[-1])
            atl_now = float(atl_a[-1])

            # ── Proyección con módulo noah_pmc_projection ──────────────────
            proy = []
            _proy_ok = False
            if carreras_db:
                try:
                    import sys as _sys, os as _os
                    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
                    from noah_pmc_projection import proyectar_pmc, proyeccion_a_dict, Carrera as CarreraObj
                    _carreras_obj = []
                    for _c in carreras_db:
                        try:
                            _fc = date.fromisoformat(_c["fecha"])
                            if _fc > hoy:
                                _carreras_obj.append(CarreraObj(
                                    fecha=_fc, prioridad=_c.get("prioridad","B"),
                                    nombre=_c.get("nombre",""), distancia=_c.get("distancia",""),
                                    ctl_objetivo=_c.get("ctl_objetivo"),
                                ))
                        except: pass
                    if _carreras_obj:
                        _res = proyectar_pmc(
                            ctl_inicial=float(ctl_now), atl_inicial=float(atl_now),
                            hoy=hoy, carreras=_carreras_obj,
                            ramp_semanal=float(perfil.get("ramp_rate_max", 3.5)),
                            ramp_max=6.0,
                        )
                        proy = proyeccion_a_dict(_res)["proy"]
                        _proy_ok = True
                except Exception as _e_proy:
                    pass


            # Performance real (eficiencia)
            perf = []
            if sport == "running":
                lthr = conn.execute("SELECT lthr_run FROM atletas WHERE id=%s", (atleta_id,)).fetchone()[0] or 162
                rs = conn.execute(
                    "SELECT fecha, pace, hr_avg FROM sesiones WHERE atleta_id=%s "
                    "AND sport=%s AND pace BETWEEN 4.5 AND 8.0 AND hr_avg BETWEEN 110 AND 165 "
                    "AND tss_total > 20 ORDER BY fecha DESC LIMIT 40", (atleta_id, sport)).fetchall()
                for r in rs:
                    if r[1] and r[2]:
                        perf.append({"f": str(r[0])[:10], "v": round(float(r[1])/(float(r[2])/lthr),3)})
            elif sport == "cycling":
                lthr_b = conn.execute("SELECT lthr_bike FROM atletas WHERE id=%s", (atleta_id,)).fetchone()[0] or 160
                rs = conn.execute(
                    "SELECT fecha, np_watts, hr_avg FROM sesiones WHERE atleta_id=%s "
                    "AND sport=%s AND np_watts>0 AND hr_avg>0 ORDER BY fecha DESC LIMIT 30", (atleta_id, sport)).fetchall()
                for r in rs:
                    if r[1] and r[2]:
                        perf.append({"f": str(r[0])[:10], "v": round(float(r[1])/(float(r[2])/lthr_b),1)})

            # Regresion
            reg = None
            if len(perf) >= 5:
                vals = [p["v"] for p in perf]
                coef = np.polyfit(range(len(vals)), vals, 1)
                mejora = (coef[0] < 0 and sport in ("running","swimming")) or (coef[0] > 0 and sport == "cycling")
                reg = {"tend": "mejorando" if mejora else "empeorando" if abs(coef[0])>0.005 else "estable",
                       "n": len(vals)}

            resultado[sport] = {
                "label": tau["label"], "color": tau["color"],
                "tau": {"t1": t1, "t2": t2},
                "hist": hist, "proy": proy,
                "actual": {"ctl": round(ctl_now,1), "atl": round(float(atl_now),1),
                           "tsb": round(ctl_now-float(atl_now),1), "peak": round(float(ctl_a.max()),1)},
                "perf": perf[-20:], "reg": reg,
            }

        # TSB objetivo por carrera
        tsb_objetivo = {
            'A': (10, 20),   # fresco para carrera A
            'B': (5, 12),    # semifresco para B
            'C': (0, 8),     # levemente fresco para C
        }

        conn.close()
        return ok(_limpiar_nan({
            "deportes":       resultado,
            "fases":          fases,
            "carrera_fecha":  fecha_carrera,
            "carrera_nombre": carrera_nombre,
            "carreras":       carreras_db,
            "tsb_objetivo":   tsb_objetivo,
        }))
    except Exception as e:
        conn.close()
        import traceback
        return error(str(e) + " | " + traceback.format_exc()[-300:])



@app.route('/api/atletas/<int:atleta_id>/actividad_detalle', methods=['GET'])
@requiere_login
def get_actividad_detalle(atleta_id):
    """Detalle completo de una actividad: métricas + laps para vista tipo Garmin/TP."""
    fecha = request.args.get('fecha', str(date.today()))
    sport = request.args.get('sport', 'running')
    conn  = get_conn()

    # Sesión principal
    row = conn.execute(
        "SELECT id, fecha, sport, distance_km, duration_min, hr_avg, hr_max, "
        "pace, tss_total, np_watts, potencia_media, swolf, paladas, tipo_sesion, fuente, "
        "cadencia, ascenso_m, calorias "
        "FROM sesiones WHERE atleta_id=%s AND fecha=%s AND sport=%s "
        "AND (fuente IS NULL OR fuente NOT IN ('prescripcion','simulacion','generada')) "
        "ORDER BY id DESC LIMIT 1",
        (atleta_id, fecha, sport)
    ).fetchone()

    if not row:
        conn.close()
        return ok({'actividad': None})

    ses_id = row[0]
    cols = ['id','fecha','sport','distance_km','duration_min','hr_avg','hr_max',
            'pace','tss_total','np_watts','potencia_media','swolf','paladas',
            'tipo_sesion','fuente','cadencia','ascenso_m','calorias']
    sesion = dict(zip(cols, row))

    # Laps de la sesión
    laps_rows = conn.execute(
        "SELECT lap_num, distance_km, duration_min, hr_avg, hr_max, pace, "
        "avg_power, cadence, ascent_m, paladas, swolf, swim_stroke, es_largo "
        "FROM laps WHERE atleta_id=%s AND sesion_id=%s AND (es_largo IS NULL OR es_largo=0) "
        "ORDER BY lap_num",
        (atleta_id, ses_id)
    ).fetchall()

    laps = []
    for l in laps_rows:
        laps.append({
            'lap':         l[0],
            'distance_km': l[1],
            'duration_min':l[2],
            'hr_avg':      l[3],
            'hr_max':      l[4],
            'pace':        l[5],
            'watts':       l[6],
            'cadencia':    l[7],
            'ascenso_m':   l[8],
            'paladas':     l[9],
            'swolf':       l[10],
            'stroke':      l[11],
        })

    # Distribución de zonas (si hay laps con HR)
    zonas_dist = None
    atleta_row = conn.execute('SELECT lthr_run, lthr_bike FROM atletas WHERE id=%s', (atleta_id,)).fetchone()
    if atleta_row and laps:
        lthr = atleta_row[0] if sport == 'running' else atleta_row[1]
        if lthr:
            zonas = {'Z1':0,'Z2':0,'Z3':0,'Z4':0,'Z5':0,'Z6':0}
            total_min = sum(l['duration_min'] or 0 for l in laps)
            for lap in laps:
                hr = lap.get('hr_avg') or 0
                dur = lap.get('duration_min') or 0
                if hr and dur:
                    ratio = hr / lthr
                    if ratio < 0.82:   zonas['Z1'] += dur
                    elif ratio < 0.88: zonas['Z2'] += dur
                    elif ratio < 0.94: zonas['Z3'] += dur
                    elif ratio < 1.00: zonas['Z4'] += dur
                    elif ratio < 1.06: zonas['Z5'] += dur
                    else:               zonas['Z6'] += dur
            if total_min > 0:
                zonas_dist = {z: {'min': round(t,1), 'pct': round(t/total_min*100,1)}
                              for z, t in zonas.items()}

    conn.close()
    return ok(_limpiar_nan({
        'actividad': sesion,
        'laps':      laps,
        'zonas':     zonas_dist,
    }))


@app.route('/api/atletas/<int:atleta_id>/hrv_historia', methods=['GET'])
@requiere_login
def get_hrv_historia(atleta_id):
    """
    Historial de HRV/biomarcadores + baseline dinámico + riesgo de enfermedad.
    Basado en: Plews et al. 2013, Flatt & Esco 2017, Buchheit 2014.
    """
    import numpy as np
    conn = get_conn()
    try:
        dias = int(request.args.get('dias', 60))
        fecha_limite = str(date.today() - timedelta(days=dias))

        rows = conn.execute('''
            SELECT fecha, hrv_rmssd, hrv_estimado_valor, hrv_ratio, hrv_flag,
                   body_battery, stress_avg, sleep_h, hr_reposo,
                   hrv_estimado
            FROM sleep_hrv
            WHERE atleta_id=%s
            AND fecha >= %s
            ORDER BY fecha ASC
        ''', (atleta_id, fecha_limite)).fetchall()

        if not rows:
            conn.close()
            return ok({'puntos': [], 'baseline': None, 'riesgo': None})

        import pandas as pd
        df = pd.DataFrame(rows, columns=[
            'fecha','hrv_real','hrv_est','hrv_ratio','hrv_flag',
            'bb','stress','sleep','hr_reposo','es_estimado'
        ])

        # HRV efectivo: real si existe, estimado si no
        df['hrv'] = df['hrv_real'].combine_first(df['hrv_est'])
        df_hrv = df[df['hrv'].notna()].copy()

        puntos = []
        baseline_vals = []
        riesgo_actual = None

        for i, row in df_hrv.iterrows():
            # Baseline dinámico: media móvil 7 días hacia atrás
            prev = df_hrv[df_hrv['fecha'] < row['fecha']].tail(7)
            baseline_7d = float(prev['hrv'].mean()) if len(prev) >= 3 else None
            baseline_30d = float(df_hrv[df_hrv['fecha'] < row['fecha']].tail(30)['hrv'].mean()) if len(df_hrv[df_hrv['fecha'] < row['fecha']]) >= 7 else None

            hrv_val = float(row['hrv'])

            # Riesgo de enfermedad (Flatt & Esco 2017 + Buchheit 2014)
            riesgo_score = 0
            alertas = []

            if baseline_7d and baseline_7d > 0:
                ratio = hrv_val / baseline_7d
                if ratio < 0.85:
                    riesgo_score += 40
                    alertas.append('HRV muy por debajo del baseline (-15%)')
                elif ratio < 0.92:
                    riesgo_score += 20
                    alertas.append('HRV por debajo del baseline (-8%)')

            # Tendencia descendente 3 días consecutivos
            if i >= 2:
                ultimos3 = df_hrv.iloc[max(0,list(df_hrv.index).index(i)-2):list(df_hrv.index).index(i)+1]['hrv'].values
                if len(ultimos3) == 3 and all(ultimos3[j] > ultimos3[j+1] for j in range(2)):
                    riesgo_score += 25
                    alertas.append('Tendencia descendente 3 días')

            # Body Battery muy baja
            if row['bb'] and float(row['bb']) < 30:
                riesgo_score += 20
                alertas.append(f'Body Battery muy baja ({int(row["bb"])})')

            # Stress alto
            if row['stress'] and float(row['stress']) > 65:
                riesgo_score += 15
                alertas.append(f'Estrés elevado ({int(row["stress"])})')

            # Sueño insuficiente
            if row['sleep'] and float(row['sleep']) < 6:
                riesgo_score += 15
                alertas.append(f'Sueño insuficiente ({row["sleep"]:.1f}h)')

            riesgo_score = min(100, riesgo_score)
            nivel_riesgo = 'alto' if riesgo_score >= 60 else 'moderado' if riesgo_score >= 30 else 'bajo'

            punto = {
                'fecha':       str(row['fecha'])[:10],
                'hrv':         round(hrv_val, 1),
                'hrv_real':    float(row['hrv_real']) if row['hrv_real'] else None,
                'hrv_est':     float(row['hrv_est']) if row['hrv_est'] else None,
                'es_estimado': bool(row['es_estimado']),
                'baseline_7d': round(baseline_7d, 1) if baseline_7d else None,
                'baseline_30d':round(baseline_30d, 1) if baseline_30d else None,
                'bb':          float(row['bb']) if row['bb'] else None,
                'stress':      float(row['stress']) if row['stress'] else None,
                'sleep':       float(row['sleep']) if row['sleep'] else None,
                'riesgo':      riesgo_score,
                'nivel':       nivel_riesgo,
                'alertas':     alertas,
            }
            puntos.append(punto)
            riesgo_actual = punto

        # Calcular pendiente de la tendencia reciente (área bajo la curva)
        tendencia = None
        if len(df_hrv) >= 7:
            ultimos = df_hrv.tail(7)['hrv'].values
            coef = np.polyfit(range(len(ultimos)), ultimos, 1)
            pendiente = float(coef[0])
            tendencia = {
                'pendiente':  round(pendiente, 3),
                'direccion':  'bajando' if pendiente < -0.5 else 'subiendo' if pendiente > 0.5 else 'estable',
                'advertencia': pendiente < -1.0,
            }

        conn.close()
        return ok(_limpiar_nan({
            'puntos':   puntos,
            'riesgo_actual': riesgo_actual,
            'tendencia': tendencia,
            'n_puntos':  len(puntos),
        }))
    except Exception as e:
        conn.close()
        import traceback
        return error(str(e) + '\n' + traceback.format_exc()[-300:])


@app.route('/api/atletas/<int:atleta_id>/hanna_life', methods=['GET'])
@requiere_login
def get_hanna_life(atleta_id):
    """Historial de HANNA LIFE + riesgo viral para el gráfico."""
    conn = get_conn()
    try:
        import json
        dias = int(request.args.get('dias', 60))
        fecha_limite = str(date.today() - timedelta(days=dias))
        rows = conn.execute('''
            SELECT fecha, hanna_life, hanna_nivel, hanna_scores,
                   riesgo_viral, riesgo_viral_nivel, riesgo_viral_alertas,
                   hrv_rmssd, hrv_estimado_valor, body_battery,
                   stress_avg, sleep_h, hr_reposo
            FROM sleep_hrv
            WHERE atleta_id=%s AND fecha >= %s
            ORDER BY fecha ASC
        ''', (atleta_id, fecha_limite)).fetchall()

        puntos = []
        for r in rows:
            try:
                alertas = json.loads(r[6]) if r[6] else []
                scores  = json.loads(r[3]) if r[3] else {}
            except Exception:
                alertas, scores = [], {}
            puntos.append({
                'fecha':        str(r[0])[:10],
                'hanna_life':   r[1],
                'hanna_nivel':  r[2],
                'hanna_scores': scores,
                'riesgo_viral': r[4],
                'riesgo_nivel': r[5],
                'alertas':      alertas,
                'hrv':          r[7] or r[8],
                'bb':           r[9],
                'stress':       r[10],
                'sleep':        r[11],
                'hr_reposo':    r[12],
            })

        # Hanna hoy — tomar el último punto calculado
        try:
            from noah_hanna_life import get_hanna_hoy
            hanna_hoy = get_hanna_hoy(conn, atleta_id)
            # Si no hay dato de hoy, tomar el último disponible
            if not hanna_hoy and puntos:
                hanna_hoy = puntos[-1]
        except Exception:
            hanna_hoy = puntos[-1] if puntos else {}

        conn.close()
        return ok(_limpiar_nan({
            'puntos':    puntos,
            'hanna_hoy': hanna_hoy,
        }))
    except Exception as e:
        conn.close()
        return error(str(e))


@app.route('/api/atletas/<int:atleta_id>/riesgo_lesion', methods=['GET'])
@requiere_login
def get_riesgo_lesion(atleta_id):
    """
    Riesgo de lesión musculoesquelética — ACWR (Gabbett 2016) y
    Monotonía/Strain (Foster 1998), indicadores INDEPENDIENTES de HANNA
    LIFE (que mide vitalidad autonómica). No se fusionan en un único
    score — ver noah_riesgo_lesion.py para la justificación metodológica.

    Devuelve:
      - 'acwr' / 'monotonia_strain': valor de HOY (vía noah_riesgo_lesion.py,
        sin duplicar esa lógica — es la fuente de verdad para el día actual).
      - 'historico': serie día por día de ACWR para los últimos `dias` días,
        para graficar la tendencia junto a HANNA LIFE. Se calcula con la
        MISMA fórmula que noah_riesgo_lesion.calcular_acwr (promedio diario
        7d / promedio diario 28d), pero de forma vectorizada: una sola
        consulta SQL trae todo el rango necesario y el resto se calcula en
        memoria — evita re-conectar y re-consultar la DB una vez por día,
        que sería costoso corriendo todos los días con datos reales.
    """
    conn = get_conn()
    try:
        from noah_riesgo_lesion import resumen_riesgo_lesion
        fecha_param = request.args.get('fecha')  # None → hoy, manejado dentro del módulo
        dias = int(request.args.get('dias', 90))

        resultado = resumen_riesgo_lesion(conn, atleta_id, fecha_param)

        # ── Histórico de ACWR — mismo cálculo, vectorizado ──────────────────
        fecha_ref = date.fromisoformat(fecha_param) if fecha_param else date.today()
        # Rango total a traer: período pedido + 28 días previos de contexto
        # crónico, necesarios para poder calcular ACWR del primer día del período.
        fecha_inicio_query = str(fecha_ref - timedelta(days=dias + 28))
        fecha_fin_query = str(fecha_ref)

        rows = conn.execute("""
            SELECT fecha, SUM(tss_total) as tss_dia
            FROM sesiones
            WHERE atleta_id=%s AND fecha > %s AND fecha <= %s
            GROUP BY fecha
        """, (atleta_id, fecha_inicio_query, fecha_fin_query)).fetchall()
        tss_por_fecha = {r[0]: (r[1] or 0) for r in rows}

        historico = []
        for offset in range(dias, -1, -1):
            d = fecha_ref - timedelta(days=offset)
            d_str = str(d)
            fecha_7d_inicio  = d - timedelta(days=7)
            fecha_28d_inicio = d - timedelta(days=28)

            suma_aguda  = sum(v for f, v in tss_por_fecha.items()
                               if fecha_7d_inicio < date.fromisoformat(f) <= d)
            suma_cronica = sum(v for f, v in tss_por_fecha.items()
                                if fecha_28d_inicio < date.fromisoformat(f) <= d)
            dias_con_datos = sum(1 for f in tss_por_fecha
                                  if fecha_28d_inicio < date.fromisoformat(f) <= d)

            carga_aguda_diaria  = suma_aguda / 7
            carga_cronica_diaria = suma_cronica / 28

            if dias_con_datos < 10 or carga_cronica_diaria == 0:
                historico.append({'fecha': d_str, 'acwr': None, 'disponible': False})
                continue

            acwr_dia = round(carga_aguda_diaria / carga_cronica_diaria, 2)
            historico.append({'fecha': d_str, 'acwr': acwr_dia, 'disponible': True})

        resultado['historico_acwr'] = historico

        conn.close()
        return ok(_limpiar_nan(resultado))
    except Exception as e:
        conn.close()
        import traceback
        return error(str(e) + ' | ' + traceback.format_exc()[-300:])


@app.route('/api/atletas/<int:atleta_id>/evaluar_carga', methods=['POST'])
@requiere_login
def evaluar_carga(atleta_id):
    """
    Evalúa si una carga planificada es adecuada para el atleta ahora.
    Body: { tss: float, intensa: bool, sport: str }
    Retorna: clasificacion, prob_absorcion, prob_riesgo, factores
    """
    conn = get_conn()
    try:
        from noah_ml import NOAHMind
        from noa_db import NOADatabase

        body    = request.get_json() or {}
        tss     = float(body.get('tss', 50))
        intensa = bool(body.get('intensa', False))

        db     = NOADatabase()
        estado = db.get_estado_actual(atleta_id)

        mind = _get_mind(conn, atleta_id)
        if mind is None or not mind.modelo_impacto.entrenado:
            conn.close()
            return ok({'evaluado': False,
                       'msg': 'Modelo no entrenado — ir a NOAH Intel → Reentrenar'})

        result = mind.modelo_impacto.evaluar_sesion(estado, tss, sesion_intensa=intensa)
        conn.close()
        return ok(_limpiar_nan(result))

    except Exception as e:
        conn.close()
        return error(str(e))


@app.route('/api/atletas/<int:atleta_id>/actividades_dia', methods=['GET'])
@requiere_login
def get_actividades_dia(atleta_id):
    """
    Actividades de un día. Si la fecha pedida no tiene datos,
    busca automáticamente hasta 2 días atrás (retrospectivo).
    """
    fecha_pedida = request.args.get('fecha', str(date.today()))
    conn  = get_conn()

    # Verificar si garmin_activity_id existe en la tabla
    from db_compat import columnas_de_tabla
    _cols_ses = set(columnas_de_tabla(conn, 'sesiones'))
    _gid_col  = "COALESCE(garmin_activity_id,'') as garmin_activity_id" if 'garmin_activity_id' in _cols_ses else "'' as garmin_activity_id"

    def _query_fecha(f):
        return conn.execute(
            "SELECT id, fecha, sport, distance_km, duration_min, hr_avg, hr_max, "
            "pace, tss_total, np_watts, potencia_media, potencia_max, wkg, "
            "tss_z12, tss_z34, tss_z56, calorias, te_aerobico, tipo_sesion, "
            f"id as sesion_id, {_gid_col} "
            "FROM sesiones WHERE atleta_id=%s AND fecha=%s "
            "AND tss_total > 0 "
            "AND (fuente IS NULL OR fuente NOT IN ('prescripcion','simulacion','generada')) "
            "ORDER BY id",
            (atleta_id, f)
        ).fetchall()

    # exacto=true: solo esa fecha (para el calendario)
    # exacto=false (default): busca hasta 7 días atrás (para vista principal)
    exacto = request.args.get('exacto', 'false').lower() == 'true'

    rows  = []
    fecha = fecha_pedida
    from datetime import datetime, timedelta

    if exacto:
        # Solo la fecha exacta pedida — no buscar atrás
        rows = _query_fecha(fecha_pedida)
    else:
        # Buscar hacia atrás hasta encontrar actividad (máx 7 días)
        for dias_atras in range(8):
            f = str((datetime.strptime(fecha_pedida, '%Y-%m-%d') - timedelta(days=dias_atras)).date())
            rows = _query_fecha(f)
            if rows:
                fecha = f
                break
    cols = ['id','fecha','sport','distance_km','duration_min','hr_avg','hr_max',
            'pace','tss_total','np_watts','potencia_media','potencia_max','wkg',
            'tss_z12','tss_z34','tss_z56','calorias','te_aerobico','session_type',
            'sesion_id','garmin_activity_id']
    actividades = []
    for row in rows:
        ses_id = row[0]
        act = dict(zip(cols, row))
        # Laps de cada actividad
        # Ver qué columnas tiene laps
        lap_cols = set(columnas_de_tabla(conn, 'laps'))
        lap_extra = []
        if 'avg_power' in lap_cols: lap_extra.append('avg_power')
        elif 'potencia_media' in lap_cols: lap_extra.append('potencia_media')
        else: lap_extra.append('NULL')
        if 'cadence' in lap_cols: lap_extra.append('cadence')
        else: lap_extra.append('NULL')
        if 'ascent_m' in lap_cols: lap_extra.append('ascent_m')
        else: lap_extra.append('NULL')

        laps_rows = conn.execute(
            f"SELECT lap_num, distance_km, duration_min, hr_avg, hr_max, pace, "
            f"{','.join(lap_extra)} FROM laps "
            "WHERE atleta_id=%s AND sesion_id=%s AND (es_largo IS NULL OR es_largo=0) "
            "ORDER BY lap_num",
            (atleta_id, ses_id)
        ).fetchall()
        laps = [{'lap':l[0],'distance_km':l[1],'duration_min':l[2],
                 'hr_avg':l[3],'hr_max':l[4],'pace':l[5],
                 'watts':l[6],'cadencia':l[7],'ascenso_m':l[8]} for l in laps_rows]
        # Zonas HR
        atleta_row = conn.execute('SELECT lthr_run, lthr_bike FROM atletas WHERE id=%s', (atleta_id,)).fetchone()
        zonas_dist = None
        if atleta_row and laps:
            lthr = atleta_row[0] if act['sport'] == 'running' else atleta_row[1]
            if lthr:
                zonas = {'Z1':0,'Z2':0,'Z3':0,'Z4':0,'Z5':0,'Z6':0}
                total_min = sum(l['duration_min'] or 0 for l in laps)
                for lap in laps:
                    hr = lap.get('hr_avg') or 0
                    dur = lap.get('duration_min') or 0
                    if hr and dur:
                        r = hr / lthr
                        z = 'Z1' if r<0.82 else 'Z2' if r<0.88 else 'Z3' if r<0.94 else 'Z4' if r<1.00 else 'Z5' if r<1.06 else 'Z6'
                        zonas[z] += dur
                if total_min > 0:
                    zonas_dist = {z:{'min':round(t,1),'pct':round(t/total_min*100,1)} for z,t in zonas.items()}
        act['laps']  = laps
        act['zonas'] = zonas_dist
        actividades.append(act)
    conn.close()
    return ok(_limpiar_nan({'actividades': actividades, 'fecha': fecha, 'n': len(actividades)}))


@app.route('/api/atletas/<int:atleta_id>/auto_sync', methods=['POST'])
@requiere_login
def auto_sync(atleta_id):
    import subprocess, sys
    from datetime import date, timedelta
    conn = get_conn()
    try:
        hoy = date.today()
        fechas_sin_datos = []
        for i in range(7, 0, -1):
            f = str(hoy - timedelta(days=i))
            tiene_act = conn.execute(
                "SELECT id FROM sesiones WHERE atleta_id=%s AND fecha=%s AND tss_total>0 AND (fuente IS NULL OR fuente NOT IN ('prescripcion','simulacion','generada'))",
                (atleta_id, f)).fetchone()
            tiene_bio = conn.execute(
                "SELECT id FROM sleep_hrv WHERE atleta_id=%s AND fecha=%s AND (sleep_h IS NOT NULL OR body_battery IS NOT NULL)",
                (atleta_id, f)).fetchone()
            if not tiene_act or not tiene_bio:
                fechas_sin_datos.append(f)
        if not fechas_sin_datos:
            conn.close()
            return ok({'sincronizado': False, 'msg': 'Todo al dia', 'fechas': []})
        sincronizadas = []
        errores = []
        script = BASE_DIR / 'sincronizar_garmin.py'
        for fecha in fechas_sin_datos[:3]:
            try:
                result = subprocess.run(
                    [sys.executable, str(script), '--atleta', str(atleta_id), '--modo', 'todo', '--fecha', fecha],
                    capture_output=True, text=True, timeout=60)
                if result.returncode == 0:
                    sincronizadas.append(fecha)
                else:
                    errores.append(fecha)
            except Exception as e:
                errores.append(str(e)[:30])
        conn.close()
        return ok(_limpiar_nan({'sincronizado': len(sincronizadas) > 0, 'fechas_sync': sincronizadas, 'fechas_error': errores, 'msg': f'{len(sincronizadas)} dias sincronizados'}))
    except Exception as e:
        conn.close()
        return error(str(e))


@app.route('/api/atletas/<int:atleta_id>/actividades_rango', methods=['GET'])
@requiere_login
def get_actividades_rango(atleta_id):
    desde = request.args.get('desde', str(date.today().replace(day=1)))
    hasta = request.args.get('hasta', str(date.today()))
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT fecha, sport, distance_km, duration_min, hr_avg, tss_total, tipo_sesion FROM sesiones WHERE atleta_id=%s AND fecha BETWEEN %s AND %s AND tss_total>0 AND (fuente IS NULL OR fuente NOT IN ('prescripcion','simulacion','generada')) ORDER BY fecha, sport",
            (atleta_id, desde, hasta)).fetchall()
        actividades = {}
        for r in rows:
            f = str(r[0])[:10]
            if f not in actividades: actividades[f] = []
            actividades[f].append({'fecha':f,'sport':r[1],'distance_km':r[2],'duration_min':r[3],'hr_avg':r[4],'tss':r[5],'tipo':r[6]})
        presc_rows = conn.execute(
            "SELECT pb.sesion_fecha, pb.sesion_sport, pb.sesion_tss, pb.sesion_nombre, pb.sesion_duracion, NULL as completada FROM prescripcion_bloques pb JOIN prescripciones p ON p.id=pb.prescripcion_id WHERE p.atleta_id=%s AND p.estado IN ('pendiente','aprobada') AND pb.sesion_fecha BETWEEN %s AND %s AND pb.bloque_num=1 ORDER BY pb.sesion_fecha",
            (atleta_id, desde, hasta)).fetchall()
        prescripciones = {}
        for r in presc_rows:
            f = str(r[0])[:10] if r[0] else None
            if not f: continue
            if f not in prescripciones: prescripciones[f] = []
            prescripciones[f].append({'fecha':f,'sport':r[1],'tss':r[2],'nombre':r[3],'duracion':r[4],'estado':r[5] or 'planificada'})
        conn.close()
        return ok(_limpiar_nan({'actividades':actividades,'prescripciones':prescripciones,'desde':desde,'hasta':hasta}))
    except Exception as e:
        conn.close()
        return error(str(e))


@app.route('/api/atletas/<int:atleta_id>/activity_streams', methods=['GET'])
@requiere_login
def get_activity_streams(atleta_id):
    """
    Streams punto a punto de una actividad.
    Cache-first: si ya están en DB los sirve rápido.
    Si no, los baja de Garmin API (una sola vez, luego queda en cache).
    Params: sesion_id (int, requerido), force (bool)
    """
    sesion_id = request.args.get('sesion_id', type=int)
    force     = request.args.get('force', 'false').lower() == 'true'
    if not sesion_id:
        return error('sesion_id requerido')
    conn = get_conn()
    try:
        from noah_streams import obtener_streams, migrate_db
        migrate_db(conn)
        # pragma_table_info() (SQLite) no existe en Postgres — el equivalente
        # es una subconsulta a information_schema.columns. Mismo resultado:
        # devuelve garmin_activity_id si la columna existe en la tabla, o
        # NULL si la tabla todavía no la tiene (esquemas viejos sin migrar).
        row = conn.execute(
            "SELECT sport, duration_min, "
            "CASE WHEN EXISTS(SELECT 1 FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='sesiones' AND column_name='garmin_activity_id') "
            "THEN garmin_activity_id ELSE NULL END "
            "FROM sesiones WHERE id=%s AND atleta_id=%s",
            (sesion_id, atleta_id)
        ).fetchone()
        if not row:
            conn.close()
            return ok({'disponible': False, 'n': 0, 'msg': 'Sesión no encontrada'})
        sport, dur_min, garmin_id = row[0], row[1], row[2]
        lthr_row = conn.execute(
            "SELECT lthr_run, lthr_bike FROM atletas WHERE id=%s", (atleta_id,)
        ).fetchone()
        lthr = 162
        if lthr_row:
            lthr = lthr_row[1] if sport == 'cycling' else lthr_row[0] or 162
        resultado = obtener_streams(conn, atleta_id, sesion_id, garmin_id,
                                    sport, dur_min, lthr, force)
        conn.close()
        if not resultado:
            return ok({'disponible': False, 'n': 0,
                       'msg': 'Sin streams — sincronizá primero o verificá garmin_activity_id'})
        return ok(_limpiar_nan({'disponible': True, 'sport': sport,
                                'lthr': lthr, **resultado}))
    except ImportError:
        conn.close()
        return ok({'disponible': False, 'n': 0,
                   'msg': 'noah_streams.py no encontrado en el pipeline'})
    except Exception as e:
        conn.close()
        return error(str(e))



# ─── CARRERAS ─────────────────────────────────────────────────────────────────

def _init_carreras_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS carreras (
            id                  SERIAL PRIMARY KEY,
            atleta_id           INTEGER NOT NULL,
            nombre              TEXT NOT NULL,
            fecha               TEXT NOT NULL,
            deporte             TEXT DEFAULT 'running',
            distancia           TEXT,
            modalidad           TEXT,
            ciudad              TEXT,
            prioridad           TEXT DEFAULT 'B',
            ctl_objetivo        REAL,
            resultado_tiempo    TEXT,
            resultado_posicion  INTEGER,
            resultado_categoria TEXT,
            notas_coach         TEXT,
            estado              TEXT DEFAULT 'pendiente',
            created_at          TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (atleta_id) REFERENCES atletas(id)
        )
    """)
    # Migración: agregar columnas faltantes
    from db_compat import asegurar_columnas
    asegurar_columnas(conn, 'carreras', [
        ('deporte',             "TEXT DEFAULT 'running'"),
        ('distancia',           'TEXT'),
        ('modalidad',           'TEXT'),
        ('ciudad',              'TEXT'),
        ('ctl_objetivo',        'REAL'),
        ('resultado_tiempo',    'TEXT'),
        ('resultado_posicion',  'INTEGER'),
        ('resultado_categoria', 'TEXT'),
        ('notas_coach',         'TEXT'),
        ('estado',              "TEXT DEFAULT 'pendiente'"),
    ])
    conn.commit()


@app.route('/api/atletas/<int:atleta_id>/carreras', methods=['GET'])
@requiere_login
def get_carreras(atleta_id):
    conn = get_conn()
    try:
        _init_carreras_table(conn)
        rows = conn.execute("""
            SELECT id, atleta_id, nombre, fecha, deporte, distancia, modalidad,
                   ciudad, prioridad, ctl_objetivo, resultado_tiempo,
                   resultado_posicion, resultado_categoria, notas_coach, estado
            FROM carreras
            WHERE atleta_id = %s
            ORDER BY fecha ASC
        """, (atleta_id,)).fetchall()
        cols = ['id','atleta_id','nombre','fecha','deporte','distancia','modalidad',
                'ciudad','prioridad','ctl_objetivo','resultado_tiempo',
                'resultado_posicion','resultado_categoria','notas_coach','estado']
        carreras = [dict(zip(cols, r)) for r in rows]
        return ok({'carreras': carreras, 'n': len(carreras)})
    except Exception as e:
        return error(str(e))
    finally:
        conn.close()


@app.route('/api/atletas/<int:atleta_id>/carreras', methods=['POST'])
@requiere_login
def crear_carrera(atleta_id):
    conn = get_conn()
    try:
        _init_carreras_table(conn)
        d = request.json or {}
        nombre   = d.get('nombre', '').strip()
        fecha    = d.get('fecha', '')
        if not nombre or not fecha:
            return error('nombre y fecha son requeridos')
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO carreras
                (atleta_id, nombre, fecha, deporte, distancia, modalidad,
                 ciudad, prioridad, ctl_objetivo, notas_coach, estado)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (
            atleta_id, nombre, fecha,
            d.get('deporte', 'running'),
            d.get('distancia', ''),
            d.get('modalidad', ''),
            d.get('ciudad', ''),
            d.get('prioridad', 'B'),
            d.get('ctl_objetivo'),
            d.get('notas_coach', ''),
            d.get('estado', 'pendiente'),
        ))
        # last_insert_rowid() (SQLite) no existe en Postgres — RETURNING id
        # en el propio INSERT es el equivalente correcto y más directo.
        carrera_id = cur.fetchone()[0]
        conn.commit()
        return ok({'id': carrera_id, 'msg': 'Carrera creada'})
    except Exception as e:
        return error(str(e))
    finally:
        conn.close()


@app.route('/api/atletas/<int:atleta_id>/carreras/<int:carrera_id>', methods=['PATCH'])
@requiere_login
def actualizar_carrera(atleta_id, carrera_id):
    conn = get_conn()
    try:
        _init_carreras_table(conn)
        d = request.json or {}
        campos = ['nombre','fecha','deporte','distancia','modalidad','ciudad',
                  'prioridad','ctl_objetivo','resultado_tiempo','resultado_posicion',
                  'resultado_categoria','notas_coach','estado']
        sets, vals = [], []
        for c in campos:
            if c in d:
                sets.append(f'{c}=%s')
                vals.append(d[c])
        if not sets:
            return error('Nada que actualizar')
        vals += [carrera_id, atleta_id]
        conn.execute(
            f"UPDATE carreras SET {', '.join(sets)} WHERE id=%s AND atleta_id=%s",
            vals
        )
        conn.commit()
        return ok({'msg': 'Carrera actualizada'})
    except Exception as e:
        return error(str(e))
    finally:
        conn.close()


@app.route('/api/atletas/<int:atleta_id>/carreras/<int:carrera_id>', methods=['DELETE'])
@requiere_login
def borrar_carrera(atleta_id, carrera_id):
    conn = get_conn()
    try:
        conn.execute(
            'DELETE FROM carreras WHERE id=%s AND atleta_id=%s',
            (carrera_id, atleta_id)
        )
        conn.commit()
        return ok({'msg': 'Carrera eliminada'})
    except Exception as e:
        return error(str(e))
    finally:
        conn.close()


@app.route('/api/carreras', methods=['GET'])
def get_todas_carreras():
    """Todas las carreras de todos los atletas — para vista global del coach"""
    conn = get_conn()
    try:
        _init_carreras_table(conn)
        rows = conn.execute("""
            SELECT c.id, c.atleta_id, a.nombre as atleta_nombre,
                   c.nombre, c.fecha, c.deporte, c.distancia, c.modalidad,
                   c.ciudad, c.prioridad, c.ctl_objetivo, c.resultado_tiempo,
                   c.resultado_posicion, c.resultado_categoria, c.notas_coach, c.estado
            FROM carreras c
            JOIN atletas a ON a.id = c.atleta_id
            ORDER BY c.fecha ASC
        """).fetchall()
        cols = ['id','atleta_id','atleta_nombre','nombre','fecha','deporte','distancia',
                'modalidad','ciudad','prioridad','ctl_objetivo','resultado_tiempo',
                'resultado_posicion','resultado_categoria','notas_coach','estado']
        carreras = [dict(zip(cols, r)) for r in rows]
        return ok({'carreras': carreras, 'n': len(carreras)})
    except Exception as e:
        return error(str(e))
    finally:
        conn.close()


# ─── TESTS DE UMBRAL ──────────────────────────────────────────────────────────

def _init_tests_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tests_umbral (
            id                SERIAL PRIMARY KEY,
            atleta_id         INTEGER NOT NULL,
            tipo              TEXT NOT NULL,
            fecha             TEXT NOT NULL,
            protocolo         TEXT,
            datos             TEXT DEFAULT '{}',
            actualizar_perfil INTEGER DEFAULT 1,
            created_at        TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (atleta_id) REFERENCES atletas(id)
        )
    """)
    conn.commit()


@app.route('/api/atletas/<int:atleta_id>/tests', methods=['GET'])
@requiere_login
def get_tests(atleta_id):
    import json
    conn = get_conn()
    try:
        _init_tests_table(conn)
        rows = conn.execute("""
            SELECT id, atleta_id, tipo, fecha, protocolo, datos, actualizar_perfil
            FROM tests_umbral WHERE atleta_id = %s ORDER BY fecha DESC
        """, (atleta_id,)).fetchall()
        cols = ['id','atleta_id','tipo','fecha','protocolo','datos','actualizar_perfil']
        tests = []
        for r in rows:
            t = dict(zip(cols, r))
            try: t['datos'] = json.loads(t['datos'] or '{}')
            except: t['datos'] = {}
            tests.append(t)
        return ok({'tests': tests, 'n': len(tests)})
    except Exception as e:
        return error(str(e))
    finally:
        conn.close()


@app.route('/api/atletas/<int:atleta_id>/tests', methods=['POST'])
@requiere_login
def crear_test(atleta_id):
    import json
    conn = get_conn()
    try:
        _init_tests_table(conn)
        d = request.json or {}
        if not d.get('fecha') or not d.get('tipo'):
            return error('fecha y tipo son requeridos')
        datos = json.dumps(d.get('datos', {}))
        act = 1 if d.get('actualizar_perfil', True) else 0
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO tests_umbral (atleta_id, tipo, fecha, protocolo, datos, actualizar_perfil)
            VALUES (%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (atleta_id, d['tipo'], d['fecha'], d.get('protocolo',''), datos, act))
        test_id = cur.fetchone()[0]
        conn.commit()

        # Actualizar perfil del atleta si corresponde
        if act:
            datos_dict = d.get('datos', {})
            updates = {}
            if d['tipo'] == 'umbral_run':
                if datos_dict.get('hr_umbral'): updates['lthr_run'] = datos_dict['hr_umbral']
            elif d['tipo'] == 'umbral_bike':
                if datos_dict.get('hr_umbral'): updates['lthr_bike'] = datos_dict['hr_umbral']
                if datos_dict.get('potencia_ftp'): updates['ftp'] = datos_dict['potencia_ftp']
            elif d['tipo'] == 'umbral_swim':
                if datos_dict.get('css_calculado'): updates['css'] = datos_dict['css_calculado']
            if updates:
                sets = ', '.join([f'{k}=%s' for k in updates])
                vals = list(updates.values()) + [atleta_id]
                try:
                    conn.execute(f'UPDATE atletas SET {sets} WHERE id=%s', vals)
                    conn.commit()
                except Exception:
                    conn.rollback()  # defensivo — columna puede no existir todavía

        return ok({'id': test_id, 'msg': 'Test registrado'})
    except Exception as e:
        return error(str(e))
    finally:
        conn.close()


@app.route('/api/atletas/<int:atleta_id>/tests/<int:test_id>', methods=['PATCH'])
@requiere_login
def actualizar_test(atleta_id, test_id):
    import json
    conn = get_conn()
    try:
        _init_tests_table(conn)
        d = request.json or {}
        sets, vals = [], []
        for c in ['tipo','fecha','protocolo','actualizar_perfil']:
            if c in d:
                sets.append(f'{c}=%s')
                vals.append(d[c])
        if 'datos' in d:
            sets.append('datos=%s')
            vals.append(json.dumps(d['datos']))
        if not sets:
            return error('Nada que actualizar')
        vals += [test_id, atleta_id]
        conn.execute(f"UPDATE tests_umbral SET {', '.join(sets)} WHERE id=%s AND atleta_id=%s", vals)
        conn.commit()
        return ok({'msg': 'Test actualizado'})
    except Exception as e:
        return error(str(e))
    finally:
        conn.close()


@app.route('/api/atletas/<int:atleta_id>/tests/<int:test_id>', methods=['DELETE'])
@requiere_login
def borrar_test(atleta_id, test_id):
    conn = get_conn()
    try:
        conn.execute('DELETE FROM tests_umbral WHERE id=%s AND atleta_id=%s', (test_id, atleta_id))
        conn.commit()
        return ok({'msg': 'Test eliminado'})
    except Exception as e:
        return error(str(e))
    finally:
        conn.close()


# ─── CLUSTERING ───────────────────────────────────────────────────────────────

@app.route('/api/atletas/<int:atleta_id>/clustering', methods=['GET'])
@requiere_login
def get_clustering(atleta_id):
    """Clustering de estados del atleta para el dashboard coach."""
    conn = get_conn()
    try:
        from noah_clustering import calcular_clustering, guardar_clustering
        dias      = int(request.args.get('dias', 180))
        clusters  = int(request.args.get('clusters', 5))
        resultado = calcular_clustering(conn, atleta_id, clusters, dias)
        if 'error' not in resultado:
            guardar_clustering(conn, atleta_id, resultado)
        return ok(_limpiar_nan(resultado))
    except Exception as e:
        return error(str(e))
    finally:
        conn.close()

# ─── NOAH OPTIMIZER ──────────────────────────────────────────────────────────
@app.route('/api/atletas/<int:atleta_id>/optimizer', methods=['GET'])
@requiere_login
def get_optimizer(atleta_id):
    """
    Análisis de optimización del atleta.
    Clustering de bloques de 4 semanas + predicción de respuesta + receta.
    Params:
      forzar=true  → recalcula aunque haya cache
    """
    conn = get_conn()
    try:
        from noah_optimizer import analizar_atleta, cargar_optimizador
        forzar = request.args.get('forzar', 'false').lower() == 'true'

        # Intentar desde cache primero
        if not forzar:
            cached = cargar_optimizador(conn, atleta_id)
            if cached and not cached.get('necesita_recalculo'):
                conn.close()
                return ok(_limpiar_nan(cached))

        # Recalcular
        resultado = analizar_atleta(conn, atleta_id, forzar=True)
        conn.close()
        return ok(_limpiar_nan(resultado))

    except ImportError as e:
        conn.close()
        return ok({
            'error': f'Módulo no disponible: {e}. Instalar scikit-learn.',
            'disponible': False,
        })
    except Exception as e:
        conn.close()
        import traceback
        return error(str(e) + ' | ' + traceback.format_exc()[-300:])


@app.route('/api/atletas/<int:atleta_id>/optimizer/aplicar', methods=['POST'])
@requiere_login
def aplicar_receta_optimizer(atleta_id):
    """
    Aplica la receta recomendada por el optimizer.
    Guarda el tipo de receta en el perfil macro para que
    generar_semana_completa la use en la próxima prescripción.
    Body: { receta: 'volumen' | 'calidad' | 'mixta' | 'recuperacion' }
    """
    conn = get_conn()
    try:
        d = request.json or {}
        receta = d.get('receta', 'mixta')
        recetas_validas = ['volumen', 'calidad', 'mixta', 'recuperacion',
                           'recuperacion_activa', 'aumentar_carga', 'reducir_carga', 'mantener']
        if receta not in recetas_validas:
            return error(f'Receta inválida: {receta}')

        # Guardar en perfil macro como override de receta
        row = conn.execute(
            'SELECT datos_json FROM perfiles_macro WHERE atleta_id=%s AND activo=1',
            (atleta_id,)
        ).fetchone()

        if row:
            perfil = json.loads(row[0])
            perfil['receta_optimizer'] = receta
            perfil['receta_fecha'] = str(date.today())
            conn.execute(
                'UPDATE perfiles_macro SET datos_json=%s WHERE atleta_id=%s AND activo=1',
                (json.dumps(perfil), atleta_id)
            )
        else:
            conn.execute(
                'INSERT INTO perfiles_macro (atleta_id, fecha_generado, datos_json, activo) VALUES (%s,%s,%s,1)',
                (atleta_id, str(date.today()), json.dumps({'receta_optimizer': receta}))
            )
        conn.commit()
        conn.close()
        return ok({'aplicado': True, 'receta': receta,
                   'msg': f'Receta "{receta}" aplicada. Se usará en la próxima prescripción semanal.'})

    except Exception as e:
        conn.close()
        return error(str(e))


if __name__ == '__main__':
    print('=' * 50)
    print('  NOA API — Backend Flask')
    print('=' * 50)
    print(f'  DB: {DB_PATH}')
    print(f'  URL: http://localhost:5000')
    print(f'  Docs: http://localhost:5000/api/ping')
    print('=' * 50)
    app.run(debug=True, port=5000, host='0.0.0.0')

