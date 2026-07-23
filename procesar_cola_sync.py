"""
procesar_cola_sync.py - Proyecto NOAH
========================================
Lee la tabla `sync_log` (la misma que escribe el endpoint
POST /api/atletas/<id>/sincronizar en app.py con status='pendiente'), y
por cada pedido pendiente:

  1. Calcula desde que fecha faltan datos para ese atleta (mirando la
     ultima sesion guardada y el ultimo bio/sleep_hrv guardado en la
     base -- el mas antiguo de los dos, para no dejar ningun hueco).
  2. Baja TODOS los dias faltantes, uno por uno (--fecha puntual),
     no solo "hoy" -- asi si el atleta se olvido de sincronizar varios
     dias, se completa el historial entero al primer sync.
  3. Pausa unos segundos entre cada dia, para no golpear la API de
     Garmin de forma agresiva (ya vimos casos de "429 IP rate limited
     by Garmin" en los logs).
  4. Tope de seguridad: nunca baja mas de MAX_DIAS_BACKFILL dias de
     una sola vez, aunque el hueco calculado sea mayor (evita que un
     atleta nuevo o con mucho tiempo sin sincronizar deje el job
     corriendo demasiado tiempo). Si hace falta mas, el proximo sync
     sigue completando desde donde quedo.

No reimplementa la logica interna de sincronizar_garmin.py -- lo sigue
llamando como subproceso, exactamente como Rodrigo ya lo corre a mano,
solo que ahora con --fecha explicito por cada dia faltante en vez de
depender del default (que solo miraba "hoy").

Requiere la variable de entorno DATABASE_URL (la misma que usa app.py y
sincronizar_garmin.py).

USO:
    python procesar_cola_sync.py
"""

import os
import sys
import time
import subprocess
from datetime import datetime, date, timedelta

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("Falta psycopg2. Instalar con: pip install psycopg2-binary")
    sys.exit(1)

TIMEOUT_SEG          = 120   # tope por dia individual (antes era por atleta entero)
MAX_DETALLE          = 3000  # no guardar logs gigantes en sync_log.detalle
MAX_DIAS_BACKFILL    = 21    # tope de seguridad: nunca bajar mas de N dias por corrida
PAUSA_ENTRE_FECHAS_S = 3     # pausa entre cada dia, para no gatillar el rate-limit de Garmin


def get_conn():
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print('Falta la variable de entorno DATABASE_URL.')
        sys.exit(1)
    return psycopg2.connect(db_url, cursor_factory=psycopg2.extras.DictCursor)


def asegurar_tabla(conn):
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS sync_log
        (id SERIAL PRIMARY KEY, atleta_id INTEGER, ts TEXT,
         modo TEXT, status TEXT, detalle TEXT)""")
    conn.commit()


def marcar(conn, row_id, status, detalle=''):
    cur = conn.cursor()
    cur.execute(
        "UPDATE sync_log SET status=%s, detalle=%s WHERE id=%s",
        (status, (detalle or '')[:MAX_DETALLE], row_id)
    )
    conn.commit()


def calcular_fechas_faltantes(conn, atleta_id, max_dias=MAX_DIAS_BACKFILL):
    """
    Devuelve la lista de fechas (YYYY-MM-DD, ordenadas de mas vieja a
    mas nueva, terminando hoy) que hay que sincronizar para este atleta.

    Toma el mas antiguo entre "ultima sesion guardada" y "ultimo bio
    guardado" -- asi si por ejemplo las actividades estan al dia pero
    el bio quedo atrasado 3 dias, igualmente bajamos esos 3 dias.
    """
    cur = conn.cursor()
    cur.execute("SELECT MAX(fecha) FROM sesiones WHERE atleta_id=%s", (atleta_id,))
    max_ses = cur.fetchone()[0]
    cur.execute("SELECT MAX(fecha) FROM sleep_hrv WHERE atleta_id=%s", (atleta_id,))
    max_bio = cur.fetchone()[0]

    candidatos = [f[:10] for f in (max_ses, max_bio) if f]
    hoy = date.today()

    if not candidatos:
        # Nunca sincronizo nada -- limitamos a max_dias para no intentar
        # bajar el historial completo en una sola corrida.
        ultimo = hoy - timedelta(days=max_dias)
    else:
        ultimo = date.fromisoformat(min(candidatos))

    dias_atras = (hoy - ultimo).days
    dias_atras = max(1, min(dias_atras, max_dias))  # minimo "hoy", tope de seguridad

    return [(hoy - timedelta(days=i)).isoformat() for i in range(dias_atras - 1, -1, -1)]


def sync_un_dia(atleta_id, modo, fecha_str):
    cmd = [sys.executable, 'sincronizar_garmin.py',
           '--atleta', str(atleta_id), '--modo', modo, '--fecha', fecha_str]
    try:
        resultado = subprocess.run(
            cmd, capture_output=True, text=True, timeout=TIMEOUT_SEG,
            env=os.environ.copy()
        )
        salida = (resultado.stdout or '') + (resultado.stderr or '')
        return resultado.returncode == 0, salida
    except subprocess.TimeoutExpired:
        return False, f'[{fecha_str}] Timeout despues de {TIMEOUT_SEG}s'
    except Exception as e:
        return False, f'[{fecha_str}] {e}'


def sync_wahoo(atleta_id):
    """Wahoo no soporta sync por fecha puntual. Se llama a 2 scripts en
    secuencia: sincronizar_wahoo.py (actividades basicas) y despues
    backfill_wahoo_laps_streams.py (streams/laps detallados) -- mismo
    patron de 2 pasos que se uso todo el dia a mano."""
    cmd = [sys.executable, 'sincronizar_wahoo.py', '--atleta_id', str(atleta_id)]
    try:
        resultado = subprocess.run(
            cmd, capture_output=True, text=True, timeout=TIMEOUT_SEG * 3,
            env=os.environ.copy()
        )
        salida = (resultado.stdout or '') + (resultado.stderr or '')
        ok_general = resultado.returncode == 0
    except subprocess.TimeoutExpired:
        return False, f'Timeout Wahoo despues de {TIMEOUT_SEG*3}s'
    except Exception as e:
        return False, str(e)

    try:
        cmd2 = [sys.executable, 'backfill_wahoo_laps_streams.py', '--atleta_id', str(atleta_id)]
        resultado2 = subprocess.run(
            cmd2, capture_output=True, text=True, timeout=TIMEOUT_SEG * 3,
            env=os.environ.copy()
        )
        salida2 = (resultado2.stdout or '') + (resultado2.stderr or '')
        ok_streams = resultado2.returncode == 0
    except subprocess.TimeoutExpired:
        salida2 = f'Timeout backfill streams despues de {TIMEOUT_SEG*3}s'
        ok_streams = False
    except Exception as e:
        salida2 = str(e)
        ok_streams = False

    salida_total = salida + '\n--- backfill streams ---\n' + salida2
    return (ok_general and ok_streams), salida_total


def procesar_pendientes(conn):
    cur = conn.cursor()
    cur.execute(
        "SELECT id, atleta_id, modo, proveedor FROM sync_log WHERE status='pendiente' ORDER BY id"
    )
    pendientes = cur.fetchall()

    if not pendientes:
        print('[INFO] No hay pedidos pendientes en sync_log.')
        return

    print(f'[INFO] {len(pendientes)} pedido(s) pendiente(s) a procesar.')

    for row in pendientes:
        row_id, atleta_id, modo = row['id'], row['atleta_id'], row['modo'] or 'todo'
        proveedor = (row['proveedor'] if 'proveedor' in row.keys() else None) or 'garmin'
        marcar(conn, row_id, 'procesando')

        if proveedor == 'wahoo':
            print(f'  -> id={row_id} atleta_id={atleta_id} modo={modo} -- proveedor=WAHOO')
            ok, salida = sync_wahoo(atleta_id)
            # Detectar si el problema es el token (no seguir acumulando pedidos)
            token_muerto = ('INVALIDO' in salida or 'invalid_grant' in salida.lower()
                            or 're-conectar' in salida.lower()
                            or 'refresh_token' in salida.lower() and 'rechazo' in salida.lower())
            if ok:
                marcar(conn, row_id, 'completado', salida)
                print(f'     [OK] atleta_id={atleta_id} (Wahoo) completado')
            elif token_muerto:
                marcar(conn, row_id, 'error', salida)
                print(f'     [ERROR] atleta_id={atleta_id} (Wahoo) -- TOKEN INVALIDO, '
                      f'el atleta debe re-conectar Wahoo desde su perfil')
                # Cancelar todos los demas pedidos pendientes de este atleta
                cur.execute(
                    "UPDATE sync_log SET status='error', detalle='Token Wahoo invalido - re-conectar' "
                    "WHERE atleta_id=%s AND status='pendiente'",
                    (atleta_id,)
                )
                conn.commit()
            else:
                marcar(conn, row_id, 'parcial', salida)
                print(f'     [PARCIAL] atleta_id={atleta_id} (Wahoo) -- revisar detalle')
            continue

        fechas = calcular_fechas_faltantes(conn, atleta_id)
        print(f'  -> id={row_id} atleta_id={atleta_id} modo={modo} -- proveedor=GARMIN '
              f'-- {len(fechas)} dia(s) a sincronizar: {fechas[0]} .. {fechas[-1]}')

        salidas = []
        hubo_error = False
        for i, fecha_str in enumerate(fechas):
            ok, salida = sync_un_dia(atleta_id, modo, fecha_str)
            salidas.append(salida)
            if ok:
                print(f'     [OK] {fecha_str}')
            else:
                hubo_error = True
                print(f'     [ERROR] {fecha_str}')
            # Pausa entre dias (no hace falta pausar despues del ultimo)
            if i < len(fechas) - 1:
                time.sleep(PAUSA_ENTRE_FECHAS_S)

        detalle_final = '\n'.join(salidas)
        if not hubo_error:
            marcar(conn, row_id, 'completado', detalle_final)
            print(f'     [OK] atleta_id={atleta_id} -- {len(fechas)} dia(s) completados')
        else:
            marcar(conn, row_id, 'parcial', detalle_final)
            print(f'     [PARCIAL] atleta_id={atleta_id} -- algun dia fallo, revisar detalle')


def limpiar_viejos(conn, dias=7):
    """Borra registros de sync_log completados/con error de hace mas de N dias
    (housekeeping simple, para que la tabla no crezca sin limite)."""
    cur = conn.cursor()
    limite = (datetime.now() - timedelta(days=dias)).isoformat()
    cur.execute(
        "DELETE FROM sync_log WHERE status IN ('completado','error','parcial') AND ts < %s",
        (limite,)
    )
    conn.commit()


def main():
    conn = get_conn()
    try:
        asegurar_tabla(conn)
        procesar_pendientes(conn)
        limpiar_viejos(conn)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
